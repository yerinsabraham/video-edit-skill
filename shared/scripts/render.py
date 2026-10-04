#!/usr/bin/env python3
"""Render review and final videos from a recipe."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, load_state, log_command, read_json, run_cmd, save_state
from captions import main as captions_main


def escape_subtitle_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(" ", "\\ ")
    )


def escape_force_style(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,")


def ffmpeg_has_filter(ffmpeg: str, name: str) -> bool:
    result = run_cmd([ffmpeg, "-hide_banner", "-filters"], check=False, capture=True)
    return name in (result.stdout or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render captioned review/final videos.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--review", action="store_true", help="Render only the low-res review copy.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        ffmpeg = find_exe("ffmpeg")
        if not ffmpeg:
            fail("ffmpeg is missing")
        recipe = read_json(project / "recipe.json")
        aroll = project / "work" / "aroll.mp4"
        if not aroll.exists():
            fail("Missing work/aroll.mp4. Run assemble.py first.")

        captions_main_args = ["captions.py", str(project)]
        import sys

        old_argv = sys.argv
        sys.argv = captions_main_args
        try:
            captions_main()
        finally:
            sys.argv = old_argv

        srt = project / recipe["captions"]["srt"]
        if ffmpeg_has_filter(ffmpeg, "subtitles"):
            style = escape_force_style(
                "FontName=Arial,FontSize=18,Alignment=2,MarginV=160,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2"
            )
            caption_filter = f"subtitles=filename={escape_subtitle_path(srt)}:force_style={style}"
            review_vf = f"scale=720:-2,{caption_filter}"
            final_vf = caption_filter
            caption_detail = "burned-in captions"
        else:
            review_vf = "scale=720:-2"
            final_vf = f"scale={int(recipe['output']['width'])}:{int(recipe['output']['height'])}"
            caption_detail = "sidecar captions only; ffmpeg lacks subtitles filter"

        review_out = project / recipe["output"]["review"]
        review_cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-i",
            str(aroll),
            "-vf",
            review_vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(review_out),
        ]
        review_out.parent.mkdir(parents=True, exist_ok=True)
        run_cmd(review_cmd, capture=True)
        log_command(project, "render-review", review_cmd, "ok", caption_detail)

        if not args.review:
            final_out = project / recipe["output"]["final"]
            final_cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-i",
                str(aroll),
                "-vf",
                final_vf,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(final_out),
            ]
            run_cmd(final_cmd, capture=True)
            log_command(project, "render-final", final_cmd, "ok", caption_detail)
            state = load_state(project)
            state.setdefault("renders", []).append(
                {
                    "name": recipe["name"],
                    "review": recipe["output"]["review"],
                    "final": recipe["output"]["final"],
                    "captionMode": caption_detail,
                }
            )
            save_state(project, state)
            print(f"Wrote {review_out} and {final_out}")
        else:
            print(f"Wrote {review_out}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    except subprocess.CalledProcessError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
