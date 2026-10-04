#!/usr/bin/env python3
"""Assemble recipe segments into a single edit."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, h264_args, log_command, read_json, run_cmd, write_json
from validate_recipe import validate


def work_size(recipe: dict, media: list[dict]) -> tuple[int, int]:
    """Assemble at the sources' native resolution (up to 2x the output) so punch-ins
    crop real pixels from 4K originals; render.py scales to the output size last."""
    width, height = int(recipe["output"]["width"]), int(recipe["output"]["height"])
    used = {s.get("clip") for s in recipe["segments"] if s.get("type", "video") == "video"}
    factors = []
    for m in media:
        if m["path"] in used and m.get("width") and m.get("height"):
            w, h = (m["width"], m["height"]) if (m["height"] >= m["width"]) == (height >= width) else (m["height"], m["width"])
            factors.append(min(w / width, h / height))
    factor = max(1.0, min(2.0, min(factors) if factors else 1.0))
    return int(width * factor) // 2 * 2, int(height * factor) // 2 * 2


def build_filter(recipe: dict, size: tuple[int, int] | None = None) -> tuple[list[dict], str]:
    width, height = size or (int(recipe["output"]["width"]), int(recipe["output"]["height"]))
    fps = int(recipe["output"]["fps"])
    parts: list[str] = []
    labels: list[str] = []
    for i, segment in enumerate(recipe["segments"]):
        kind = segment.get("type", "video")
        start = float(segment.get("in", 0))
        end = float(segment.get("out", 0))
        duration = end - start
        # Inputs are pre-seeked with -ss/-t, so every stream starts at its cut point.
        parts.append(
            f"[{i}:v]trim=duration={duration},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},setsar=1[v{i}]"
        )
        if kind == "image":
            parts.append(f"anullsrc=channel_layout=mono:sample_rate=44100,atrim=duration={duration},asetpts=PTS-STARTPTS[a{i}]")
        else:
            parts.append(f"[{i}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
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
        media = read_json(project / "media.json", {"sources": []})["sources"]
        size = work_size(recipe, media)
        segments, filtergraph = build_filter(recipe, size)
        out = project / "work" / "aroll.mp4"
        command = [ffmpeg, "-y", "-hide_banner"]
        for segment in segments:
            if segment.get("type") == "image":
                duration = float(segment["out"]) - float(segment.get("in", 0))
                command.extend(["-loop", "1", "-t", str(duration), "-i", segment["clip"]])
            else:
                # Seek each input to its cut instead of decoding the whole file once per segment.
                start = float(segment["in"])
                command.extend(["-ss", f"{start:.3f}", "-t", f"{float(segment['out']) - start:.3f}", "-i", segment["clip"]])
        command.extend(
            [
                "-filter_complex",
                filtergraph,
                "-map",
                "[v]",
                "-map",
                "[a]",
                *h264_args(ffmpeg, "work"),
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
        write_json(project / "segments.json", {"duration": cursor, "segments": rendered_segments, "work": {"width": size[0], "height": size[1]}})
        log_command(project, "assemble", command, "ok")
        print(f"Wrote {out} ({size[0]}x{size[1]})")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
