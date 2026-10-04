#!/usr/bin/env python3
"""Apply targeted EDL revisions and create a new recipe version."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, snapshot_project, write_json
from recipe import main as recipe_main


def find_segment(segments: list[dict], segment_id: str) -> dict:
    for segment in segments:
        if segment.get("id") == segment_id:
            return segment
    raise SkillError(f"Unknown segment id: {segment_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Revise edl.json and write a new recipe version.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--name", required=True, help="New recipe/render version name, e.g. v2.")
    parser.add_argument("--trim-start", nargs=2, action="append", metavar=("SEGMENT", "SECONDS"), default=[])
    parser.add_argument("--trim-end", nargs=2, action="append", metavar=("SEGMENT", "SECONDS"), default=[])
    parser.add_argument("--shift", nargs=2, action="append", metavar=("SEGMENT", "SECONDS"), default=[])
    parser.add_argument("--line", nargs=2, action="append", metavar=("SEGMENT", "TEXT"), default=[])
    parser.add_argument("--look", nargs=2, action="append", metavar=("SEGMENT", "LOOK"), default=[])
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        snapshot_project(project, f"before-{args.name}", f"before revise {args.name}")
        edl = read_json(project / "edl.json")
        segments = edl["segments"]

        for segment_id, seconds in args.trim_start:
            segment = find_segment(segments, segment_id)
            segment["in"] = round(float(segment["in"]) + float(seconds), 3)
        for segment_id, seconds in args.trim_end:
            segment = find_segment(segments, segment_id)
            segment["out"] = round(float(segment["out"]) - float(seconds), 3)
        for segment_id, seconds in args.shift:
            segment = find_segment(segments, segment_id)
            delta = float(seconds)
            segment["in"] = round(float(segment["in"]) + delta, 3)
            segment["out"] = round(float(segment["out"]) + delta, 3)
        for segment_id, text in args.line:
            find_segment(segments, segment_id)["line"] = text
        for segment_id, look in args.look:
            find_segment(segments, segment_id)["look"] = look

        for segment in segments:
            if float(segment["out"]) <= float(segment["in"]):
                fail(f"Revision made segment {segment['id']} invalid")

        write_json(project / "edl.json", edl)

        old_argv = sys.argv
        sys.argv = ["recipe.py", str(project), "--name", args.name]
        try:
            recipe_main()
        finally:
            sys.argv = old_argv
        snapshot_project(project, args.name, args.note or "revision applied")
        print(f"Created revision {args.name}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

