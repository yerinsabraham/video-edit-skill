#!/usr/bin/env python3
"""Transcribe project media or import a transcript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, read_json, run_cmd, write_json


def normalize_whisper_json(path: Path, media_id: str) -> dict:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe project videos with Whisper.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--model", default="base", help="Whisper model name.")
    parser.add_argument("--language", default=None, help="Optional language code.")
    parser.add_argument("--allow-empty", action="store_true", help="Create placeholder transcript if Whisper is missing.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        media = read_json(project / "media.json")["sources"]
        whisper = find_exe("whisper")
        all_segments = []
        all_words = []
        out_dir = project / "work" / "transcripts"
        out_dir.mkdir(parents=True, exist_ok=True)

        if not whisper and not args.allow_empty:
            fail("Whisper CLI is missing. Install openai-whisper or rerun with --allow-empty.")

        for item in media:
            if whisper:
                command = [
                    whisper,
                    item["path"],
                    "--model",
                    args.model,
                    "--output_format",
                    "json",
                    "--output_dir",
                    str(out_dir),
                ]
                if args.language:
                    command.extend(["--language", args.language])
                run_cmd(command, capture=True)
                json_path = out_dir / (Path(item["path"]).stem + ".json")
                normalized = normalize_whisper_json(json_path, item["id"])
            else:
                normalized = empty_transcript(item)
            all_segments.extend(normalized["segments"])
            all_words.extend(normalized["words"])

        write_json(
            project / "transcript.json",
            {"engine": "whisper" if whisper else "placeholder", "segments": all_segments, "words": all_words},
        )
        print(f"Wrote transcript for {len(media)} source(s)")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

