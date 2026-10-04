#!/usr/bin/env python3
"""Add, list, or remove timed graphic overlays in recipe.json.

An overlay is a transparent PNG (faded in and out by ffmpeg) or an alpha video
such as a HyperFrames ProRes 4444 render from motion.py. Times are timeline
seconds. Place overlays in the bands above or below the face, never across it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, ffprobe, read_json, snapshot_project, write_json


VIDEO_EXTS = {".mov", ".webm", ".mp4", ".mkv"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage timed overlays in recipe.json.")
    parser.add_argument("project", help="Project directory.")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add", help="Add an overlay.")
    add.add_argument("file", help="PNG or alpha video (.mov ProRes 4444, .webm VP9 alpha).")
    add.add_argument("--start", type=float, required=True, help="Timeline second the overlay appears.")
    add.add_argument("--end", type=float, help="Timeline second it disappears. Defaults to start + video length.")
    add.add_argument("--x", default="center", help="Pixels from left, or 'center'.")
    add.add_argument("--y", default="220", help="Pixels from top, or 'center'. Default clears the top safe zone.")
    add.add_argument("--width", type=int, help="Scale overlay to this width.")
    add.add_argument("--fade", type=float, default=0.3, help="PNG fade in/out seconds.")
    add.add_argument("--label", default="", help="Why this graphic earns its place.")
    add.add_argument("--behind", action="store_true", help="Place behind the speaker (person mask via Apple Vision, macOS).")
    sub.add_parser("list", help="List overlays.")
    rm = sub.add_parser("remove", help="Remove overlay by index.")
    rm.add_argument("index", type=int)
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        recipe_path = project / "recipe.json"
        recipe = read_json(recipe_path)
        overlays = recipe.setdefault("overlays", [])
        if args.action == "list":
            for i, item in enumerate(overlays):
                print(f"{i}: {item['start']:.2f}-{item['end']:.2f}s {Path(item['file']).name} {item.get('label', '')}")
            if not overlays:
                print("No overlays.")
            return 0
        snapshot_project(project, f"before-overlay-{len(overlays)}", f"before overlay {args.action}")
        if args.action == "remove":
            if not 0 <= args.index < len(overlays):
                fail(f"No overlay {args.index}")
            removed = overlays.pop(args.index)
            write_json(recipe_path, recipe)
            print(f"Removed {Path(removed['file']).name}")
            return 0

        path = Path(args.file).expanduser().resolve()
        if not path.exists():
            fail(f"Overlay file does not exist: {path}")
        kind = "video" if path.suffix.lower() in VIDEO_EXTS else "image"
        end = args.end
        if end is None:
            if kind != "video":
                fail("--end is required for image overlays")
            end = args.start + float(ffprobe(path).get("format", {}).get("duration") or 0)
        timeline = sum(float(s["out"]) - float(s["in"]) for s in recipe.get("segments", []))
        if not 0 <= args.start < end <= timeline + 0.05:
            fail(f"Overlay window {args.start}-{end} must sit inside the timeline (0-{timeline:.2f}s)")
        coerce = lambda v: v if v == "center" else int(v)
        overlays.append(
            {
                "file": str(path),
                "kind": kind,
                "start": round(args.start, 3),
                "end": round(end, 3),
                "x": coerce(args.x),
                "y": coerce(args.y),
                "width": args.width,
                "fade": args.fade,
                "label": args.label,
                "behind": args.behind,
            }
        )
        write_json(recipe_path, recipe)
        print(f"Added {kind} overlay {path.name} at {args.start:.2f}-{end:.2f}s. Check it with render.py --frame {args.start + 0.5:.1f}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
