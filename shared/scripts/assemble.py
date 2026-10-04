#!/usr/bin/env python3
"""Assemble recipe segments into a single edit."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, log_command, read_json, run_cmd, write_json
from validate_recipe import validate


def build_filter(recipe: dict) -> tuple[list[dict], str]:
    width = int(recipe["output"]["width"])
    height = int(recipe["output"]["height"])
    fps = int(recipe["output"]["fps"])
    parts: list[str] = []
    labels: list[str] = []
    for i, segment in enumerate(recipe["segments"]):
        kind = segment.get("type", "video")
        start = float(segment.get("in", 0))
        end = float(segment.get("out", 0))
        duration = end - start
        parts.append(
            f"[{i}:v]trim=start={0 if kind == 'image' else start}:end={duration if kind == 'image' else end},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},setsar=1[v{i}]"
        )
        if kind == "image":
            parts.append(f"anullsrc=channel_layout=mono:sample_rate=44100,atrim=duration={duration},asetpts=PTS-STARTPTS[a{i}]")
        else:
            parts.append(f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=1[v][a]")
    return recipe["segments"], ";".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble recipe segments into work/aroll.mp4.")
    parser.add_argument("project", help="Project directory.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        errors = validate(project)
        if errors:
            fail("; ".join(errors))
        ffmpeg = find_exe("ffmpeg")
        if not ffmpeg:
            fail("ffmpeg is missing")
        recipe = read_json(project / "recipe.json")
        segments, filtergraph = build_filter(recipe)
        out = project / "work" / "aroll.mp4"
        command = [ffmpeg, "-y", "-hide_banner"]
        for segment in segments:
            if segment.get("type") == "image":
                duration = float(segment["out"]) - float(segment.get("in", 0))
                command.extend(["-loop", "1", "-t", str(duration), "-i", segment["clip"]])
            else:
                command.extend(["-i", segment["clip"]])
        command.extend(
            [
                "-filter_complex",
                filtergraph,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(out),
            ]
        )
        run_cmd(command, capture=True)
        cursor = 0.0
        rendered_segments = []
        for segment in recipe["segments"]:
            duration = float(segment["out"]) - float(segment["in"])
            rendered_segments.append({**segment, "timelineIn": round(cursor, 3), "timelineOut": round(cursor + duration, 3)})
            cursor += duration
        write_json(project / "segments.json", {"duration": cursor, "segments": rendered_segments})
        log_command(project, "assemble", command, "ok")
        print(f"Wrote {out}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
