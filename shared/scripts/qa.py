#!/usr/bin/env python3
"""Run QA checks on a rendered video."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, ffprobe, find_exe, read_json, run_cmd


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a QA report for the current render.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--render", help="Render path. Defaults to recipe final output.")
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
            if "black_start" in black:
                findings.append("black frames detected; inspect render")
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
