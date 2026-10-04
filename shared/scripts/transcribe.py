#!/usr/bin/env python3
"""Transcribe project media or import a transcript."""

from __future__ import annotations

import argparse
import json
import platform
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, read_json, run_cmd, whisper_model, write_json
from fix_transcript import fix


SENTENCE_END = re.compile(r"[.!?…][\"'”’)]*$")


def normalize_whisper_json(path: Path, media_id: str) -> dict:
    """openai-whisper JSON (segments with optional words)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    segments = []
    words = []
    for s_index, segment in enumerate(raw.get("segments", [])):
        seg_words = []
        for word in segment.get("words", []) or []:
            item = {
                "start": float(word.get("start", segment.get("start", 0))),
                "end": float(word.get("end", segment.get("end", 0))),
                "text": str(word.get("word", "")).strip(),
            }
            if item["text"]:
                seg_words.append(item)
                words.append({**item, "mediaId": media_id})
        segments.append(
            {
                "id": f"{media_id}-s{s_index + 1}",
                "mediaId": media_id,
                "start": float(segment.get("start", 0)),
                "end": float(segment.get("end", 0)),
                "text": str(segment.get("text", "")).strip(),
                "words": seg_words,
            }
        )
    return {"segments": segments, "words": words}


def normalize_whisper_cpp_json(path: Path, media_id: str, max_gap: float = 0.8, max_len: float = 12.0) -> dict:
    """whisper.cpp -oj output run with -ml 1: one word (or fragment) per entry.

    A fragment without a leading space continues the previous word; it is marked
    with join=True so fix_transcript.py can rejoin it.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    words: list[dict] = []
    for entry in raw.get("transcription", []):
        text = str(entry.get("text", ""))
        if not text.strip():
            continue
        offsets = entry.get("offsets", {})
        words.append(
            {
                "mediaId": media_id,
                "start": round(float(offsets.get("from", 0)) / 1000, 3),
                "end": round(float(offsets.get("to", 0)) / 1000, 3),
                "text": text.strip(),
                "join": bool(words) and not text.startswith(" "),
            }
        )
    segments: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        if not current:
            return
        text = ""
        for w in current:
            text += w["text"] if w.get("join") or not text else " " + w["text"]
        segments.append(
            {
                "id": f"{media_id}-s{len(segments) + 1}",
                "mediaId": media_id,
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": text,
                "words": [],
            }
        )
        current.clear()

    for word in words:
        if current and not word.get("join"):
            gap = word["start"] - current[-1]["end"]
            if gap > max_gap or word["start"] - current[0]["start"] > max_len or SENTENCE_END.search(current[-1]["text"]):
                flush()
        current.append(word)
    flush()
    return {"segments": segments, "words": words}


def extract_audio(ffmpeg: str, source: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    run_cmd([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", source, "-map", "0:a:0", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(out)])
    return out


def empty_transcript(media: dict) -> dict:
    duration = float(media.get("duration") or 0)
    text = media.get("filename", media["id"])
    return {
        "segments": [
            {
                "id": f"{media['id']}-s1",
                "mediaId": media["id"],
                "start": 0,
                "end": duration,
                "text": text,
                "words": [],
            }
        ],
        "words": [],
    }


def import_transcript(path: Path, media_id: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "transcription" in data:
        return normalize_whisper_cpp_json(path, media_id)
    if "segments" in data and data.get("segments") and "mediaId" in data["segments"][0]:
        return {"segments": data["segments"], "words": data.get("words", [])}
    return normalize_whisper_json(path, media_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe project videos with whisper.cpp or Whisper.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--engine", choices=["auto", "whisper-cpp", "whisper"], default="auto")
    parser.add_argument("--model", default="small.en", help="Model name (small.en) or path to a ggml model.")
    parser.add_argument("--language", default=None, help="Optional language code.")
    parser.add_argument("--threads", type=int, default=4, help="whisper.cpp CPU threads.")
    parser.add_argument("--no-gpu", action="store_true", help="whisper.cpp: disable GPU (use when the GPU path fails).")
    parser.add_argument("--import", dest="import_path", help="Import an existing whisper.cpp/Whisper JSON for a single source.")
    parser.add_argument("--allow-empty", action="store_true", help="Create placeholder transcript if no engine is available.")
    parser.add_argument("--no-fix", action="store_true", help="Skip fix_transcript.py cleanup.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        media = read_json(project / "media.json")["sources"]
        out_dir = project / "work" / "transcripts"
        out_dir.mkdir(parents=True, exist_ok=True)
        all_segments: list[dict] = []
        all_words: list[dict] = []

        if args.import_path:
            if len(media) != 1:
                fail("--import supports a single source; import per source by editing transcript.json instead.")
            normalized = import_transcript(Path(args.import_path).expanduser(), media[0]["id"])
            engine = "imported"
            all_segments, all_words = normalized["segments"], normalized["words"]
        else:
            cli = find_exe("whisper-cli") if args.engine in {"auto", "whisper-cpp"} else None
            model = whisper_model(args.model) if cli else None
            whisper = find_exe("whisper") if args.engine in {"auto", "whisper"} and not (cli and model) else None
            ffmpeg = find_exe("ffmpeg")
            if cli and model:
                engine = "whisper.cpp"
            elif whisper:
                engine = "whisper"
            elif args.allow_empty:
                engine = "placeholder"
            else:
                hint = ""
                if cli and not model:
                    hint = f" whisper-cli found but model '{args.model}' is missing; run setup.py --download-model."
                fail("No transcription engine. Install whisper.cpp (whisper-cli) or openai-whisper, or rerun with --allow-empty." + hint)

            # Metal output is unreliable on Intel Macs; CPU is also faster there.
            no_gpu = args.no_gpu or (platform.system() == "Darwin" and platform.machine() == "x86_64")
            for item in media:
                if engine == "whisper.cpp":
                    if not ffmpeg:
                        fail("ffmpeg is missing")
                    wav = extract_audio(ffmpeg, item["path"], project / "work" / "audio" / f"{item['id']}.wav")
                    stem = out_dir / item["id"]
                    command = [cli, "-m", str(model), "-f", str(wav), "-oj", "-of", str(stem), "-ml", "1", "-t", str(args.threads)]
                    if args.language:
                        command.extend(["-l", args.language])
                    if no_gpu:
                        command.append("-ng")
                    print(f"Transcribing {item['filename']} with whisper.cpp ({model.name}{', CPU' if no_gpu else ''})...")
                    run_cmd(command, capture=True)
                    normalized = normalize_whisper_cpp_json(stem.with_suffix(".json"), item["id"])
                    duration = float(item.get("duration") or 0)
                    if not no_gpu and duration > 8 and len(normalized["words"]) < duration / 6:
                        # The GPU path can return a token or two for a whole clip; retry on CPU.
                        print(f"Only {len(normalized['words'])} word(s) for {duration:.0f}s; retrying on CPU (-ng).")
                        run_cmd(command + ["-ng"], capture=True)
                        normalized = normalize_whisper_cpp_json(stem.with_suffix(".json"), item["id"])
                elif engine == "whisper":
                    command = [whisper, item["path"], "--model", "small" if args.model == "small.en" else args.model, "--output_format", "json", "--word_timestamps", "True", "--output_dir", str(out_dir)]
                    if args.language:
                        command.extend(["--language", args.language])
                    run_cmd(command, capture=True)
                    normalized = normalize_whisper_json(out_dir / (Path(item["path"]).stem + ".json"), item["id"])
                else:
                    normalized = empty_transcript(item)
                all_segments.extend(normalized["segments"])
                all_words.extend(normalized["words"])

        transcript = {"engine": engine, "segments": all_segments, "words": all_words}
        write_json(project / "transcript.raw.json", transcript)
        write_json(project / "transcript.json", transcript)
        print(f"Wrote transcript for {len(media)} source(s) using {engine}")
        if not args.no_fix and engine != "placeholder":
            result = fix(project)
            print(f"Cleaned transcript: {result['removed']} artefact(s) removed, {result['changed']} line(s) corrected")
            print("Read qa/transcript-review.md before planning the edit.")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
