#!/usr/bin/env python3
"""Insert a still image or screenshot into the EDL."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, snapshot_project, write_json
from card import insert_segment
from recipe import main as recipe_main


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert an image segment into edl.json.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("image", help="Image path supported by ffmpeg.")
    parser.add_argument("--position", choices=["start", "end"], default="end")
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--label", default="")
    parser.add_argument("--name", default="insert")
    parser.add_argument("--update-recipe", action="store_true")
    parser.add_argument("--recipe-name", default="v-insert")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        image = Path(args.image).expanduser().resolve()
        if not image.exists():
            fail(f"Image does not exist: {image}")
        snapshot_project(project, f"before-insert-{args.name}", f"before inserting image {args.name}")
        target = project / "work" / "inserts" / f"{args.name}{image.suffix.lower()}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, target)
        config = read_json(project / "project.json")
        edl = read_json(project / "edl.json")
        segment = {
            "id": "insert",
            "type": "image",
            "mediaId": f"insert-{args.name}",
            "clip": str(target),
            "in": 0,
            "out": round(float(args.duration), 3),
            "line": args.label,
            "look": config.get("look", "clean-creator"),
            "zoom": 1.0,
            "cx": 0.5,
            "cy": 0.5,
        }
        write_json(project / "edl.json", insert_segment(edl, segment, args.position))
        if args.update_recipe:
            old_argv = sys.argv
            sys.argv = ["recipe.py", str(project), "--name", args.recipe_name]
            try:
                recipe_main()
            finally:
                sys.argv = old_argv
        print(f"Inserted {target}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
