#!/usr/bin/env python3
"""Run QA checks on a rendered video."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, ffmpeg_filters, ffprobe, find_exe, read_json, run_cmd
from captions import LONG, SHORT


def ffmpeg_detect(ffmpeg: str, render: Path, detector: str) -> str:
    result = run_cmd(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(render),
            "-vf",
            detector,
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture=True,
    )
    return (result.stderr or "") + (result.stdout or "")


def audio_volume(ffmpeg: str, render: Path) -> str:
    result = run_cmd(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(render),
            "-af",
            "volumedetect",
            "-vn",
            "-sn",
            "-dn",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture=True,
    )
    return (result.stderr or "") + (result.stdout or "")


def caption_findings(project: Path, recipe: dict, ffmpeg: str | None, allow_sidecar: bool, observations: list[str]) -> list[str]:
    findings: list[str] = []
    captions = recipe.get("captions", {})
    for key in ["srt", "vtt", "json"]:
        if captions.get(key) and not (project / captions[key]).exists():
            findings.append(f"missing caption sidecar: {captions[key]}")
    if captions.get("burnIn", True) and not allow_sidecar:
        filters = ffmpeg_filters(ffmpeg)
        if "ass" not in filters and "subtitles" not in filters:
            findings.append("captions were not burned in: this ffmpeg has no libass (see shared/references/troubleshooting.md)")
    transcript = read_json(project / "transcript.json", {})
    if transcript.get("engine") == "placeholder":
        observations.append("placeholder transcript: captions are not from speech")
    data = read_json(project / captions["json"], {}) if captions.get("json") else {}
    if isinstance(data, list):
        data = {"mode": "short", "captions": data}
    mode = data.get("mode", "short")
    bad_punct, too_long, too_fast = 0, 0, 0
    for cap in data.get("captions", []):
        text = cap.get("text", "")
        if not any(ch.isalnum() for ch in text):
            bad_punct += 1
        if mode == "short":
            if len(text) > SHORT["maxChars"] and len(text.split()) > 1:
                too_long += 1
            if float(cap["end"]) - float(cap["start"]) < SHORT["minHold"] - 0.011:
                too_fast += 1
        elif len(text.replace("\n", " ")) > LONG["splitChars"] or text.count("\n") > 1:
            too_long += 1
    if bad_punct:
        findings.append(f"{bad_punct} caption(s) contain only punctuation")
    if too_long:
        findings.append(f"{too_long} {mode}-form caption(s) exceed the length rule")
    if too_fast:
        findings.append(f"{too_fast} caption(s) shorter than {SHORT['minHold']}s read as glitches")
    review = project / "qa" / "transcript-review.md"
    if review.exists() and "## Promises to keep\n\nThe speaker" in review.read_text(encoding="utf-8"):
        text = review.read_text(encoding="utf-8").split("## Promises to keep")[1].split("##")[0]
        promises = [line for line in text.splitlines() if line.startswith("- ") and line != "- None"]
        if promises:
            observations.append(f"{len(promises)} on-camera promise(s) to verify; see qa/transcript-review.md")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a QA report for the current render.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--render", help="Render path. Defaults to recipe final output.")
    parser.add_argument("--fast", action="store_true", help="Skip the full-decode check (slow on long renders).")
    parser.add_argument("--allow-sidecar-captions", action="store_true", help="Do not flag captions that were not burned in.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        recipe = read_json(project / "recipe.json")
        render = Path(args.render) if args.render else project / recipe["output"]["final"]
        if not render.exists():
            fail(f"Missing render: {render}")
        has_image_segments = any(segment.get("type") == "image" for segment in recipe.get("segments", []))
        probe = ffprobe(render)
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration") or 0)
        expected = sum(float(s["out"]) - float(s["in"]) for s in recipe["segments"])
        findings: list[str] = []
        if abs(duration - expected) > 0.35:
            findings.append(f"duration mismatch: expected {expected:.2f}s, got {duration:.2f}s")
        if int(fmt.get("size") or 0) <= 0:
            findings.append("render has zero size")
        streams = probe.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        if not video:
            findings.append("render has no video stream")
        if not audio:
            findings.append("render has no audio stream")
        if video:
            width = int(video.get("width") or 0)
            height = int(video.get("height") or 0)
            if width <= 0 or height <= 0:
                findings.append("render has invalid dimensions")
            elif height < width:
                findings.append(f"render is landscape ({width}x{height}); expected vertical for this workflow")

        ffmpeg = find_exe("ffmpeg")
        sheet = project / "qa" / "cut-check.jpg"
        observations: list[str] = []

        # A file existing is not a file finished: streams must agree and it must decode end to end.
        if video and audio and video.get("duration") and audio.get("duration"):
            drift = abs(float(video["duration"]) - float(audio["duration"]))
            if drift > 0.1:
                findings.append(f"video/audio durations differ by {drift:.3f}s; check joins and card audio")
        if ffmpeg and not args.fast:
            decode = run_cmd([ffmpeg, "-v", "error", "-i", str(render), "-f", "null", "-"], check=False, capture=True)
            if decode.returncode != 0 or (decode.stderr or "").strip():
                findings.append("full decode reported errors: " + (decode.stderr or "").strip().splitlines()[0][:160] if (decode.stderr or "").strip() else "full decode failed")

        findings.extend(caption_findings(project, recipe, ffmpeg, args.allow_sidecar_captions, observations))
        if ffmpeg:
            try:
                run_cmd(
                    [
                        ffmpeg,
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(render),
                        "-vf",
                        "fps=1/2,scale=240:-1,tile=5x5",
                        "-frames:v",
                        "1",
                        str(sheet),
                    ]
                )
            except SkillError as exc:
                findings.append(f"could not create contact sheet: {exc}")
            black = ffmpeg_detect(ffmpeg, render, "blackdetect=d=0.18:pic_th=0.96")
            # Dark title cards are deliberate; only flag black outside card/image windows.
            windows, cursor = [], 0.0
            for segment in recipe.get("segments", []):
                length = float(segment["out"]) - float(segment["in"])
                if segment.get("type") == "image":
                    windows.append((cursor - 0.05, cursor + length + 0.05))
                cursor += length
            runs = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", black)]
            stray = [run for run in runs if not any(lo <= run[0] and run[1] <= hi for lo, hi in windows)]
            if stray:
                findings.append(f"black frames at {stray[0][0]:.2f}-{stray[0][1]:.2f}s; inspect render")
            elif runs:
                observations.append("dark frames detected only inside card/image segments")
            freeze = ffmpeg_detect(ffmpeg, render, "freezedetect=n=-60dB:d=1.0")
            if "freeze_start" in freeze:
                if has_image_segments:
                    observations.append("frozen-frame detector triggered; static image/card segments are present")
                else:
                    findings.append("frozen frames detected; inspect render")
            volume = audio_volume(ffmpeg, render)
            for line in volume.splitlines():
                if "max_volume:" in line or "mean_volume:" in line:
                    observations.append(line.strip())
            if "max_volume: 0.0 dB" in volume:
                findings.append("audio may be clipping at 0.0 dB")

        status = "PASS" if not findings else "REVIEW"
        report = project / "qa" / "report.md"
        lines = [
            "# QA Report",
            "",
            f"Render: `{render}`",
            f"Status: **{status}**",
            f"Duration: {duration:.2f}s",
            f"Expected: {expected:.2f}s",
            "",
            "## Findings",
            "",
        ]
        if findings:
            lines.extend(f"- {item}" for item in findings)
        else:
            lines.append("- No blocking findings from automated checks.")
        lines.extend(["", "## Observations", ""])
        if observations:
            lines.extend(f"- `{item}`" for item in observations)
        else:
            lines.append("- No extra observations.")
        lines.extend(["", "## Artifacts", "", f"- Contact sheet: `{sheet}`"])
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{status}: wrote {report}")
        return 0 if not findings else 2
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
