#!/usr/bin/env python3
"""Create a project manifest from source videos."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import (
    SkillError,
    discover_videos,
    ensure_project,
    fail,
    find_exe,
    log_command,
    media_info,
    run_cmd,
    write_json,
)


def make_contact_sheet(project: Path, media: list[dict]) -> None:
    ffmpeg = find_exe("ffmpeg")
    if not ffmpeg:
        return
    thumbs = project / "work" / "sheets"
    thumbs.mkdir(parents=True, exist_ok=True)
    for item in media:
        src = Path(item["path"])
        out = thumbs / f"{item['id']}.jpg"
        try:
            run_cmd(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(src),
                    "-vf",
                    "fps=1/3,scale=320:-1,tile=5x4",
                    "-frames:v",
                    "1",
                    str(out),
                ]
            )
        except SkillError as exc:
            log_command(project, "contact_sheet", [str(src)], "warn", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest videos into a video-edit project.")
    parser.add_argument("project", help="Project directory to create or update.")
    parser.add_argument("sources", nargs="+", help="Video files or folders.")
    parser.add_argument("--newest", type=int, help="Use newest N videos from folders.")
    parser.add_argument("--keep-order", action="store_true", help="Keep the order the files are listed in (default: recording time).")
    parser.add_argument("--title", default="Untitled edit", help="Project title.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        videos = discover_videos(args.sources, args.newest, args.keep_order)
        if not videos:
            fail("No source videos found.")

        media = [media_info(path, f"m{index + 1}") for index, path in enumerate(videos)]
        write_json(
            project / "project.json",
            {
                "title": args.title,
                "target": "reel",
                "aspect": "9:16",
                "width": 1080,
                "height": 1920,
                "look": "clean-creator",
                "version": 1,
            },
        )
        write_json(project / "media.json", {"sources": media})
        make_contact_sheet(project, media)
        log_command(project, "ingest", [str(v) for v in videos], "ok")
        print(f"Ingested {len(media)} video(s) into {project}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

