#!/usr/bin/env python3
"""Convert edl.json into a declarative render recipe."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, load_state, read_json, save_state, snapshot_project, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Create recipe.json from edl.json.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--name", default="v1", help="Render version name.")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        edl = read_json(project / "edl.json")["segments"]
        project_config = read_json(project / "project.json")
        recipe = {
            "version": 1,
            "name": args.name,
            "createdBy": "video-edit skill",
            "project": project_config,
            "output": {
                "width": args.width,
                "height": args.height,
                "fps": args.fps,
                "review": f"renders/{args.name}-review.mp4",
                "final": f"renders/{args.name}.mp4",
            },
            "captions": {
                "json": f"exports/{args.name}.captions.json",
                "srt": f"exports/{args.name}.srt",
                "vtt": f"exports/{args.name}.vtt",
                "burnIn": True,
            },
            "segments": edl,
        }
        write_json(project / "recipe.json", recipe)
        state = load_state(project)
        state["current"] = "recipe.json"
        state.setdefault("renders", [])
        state.setdefault("notes", [])
        save_state(project, state)
        snapshot_project(project, args.name, "recipe created")
        print(f"Wrote recipe for {len(edl)} segment(s)")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
