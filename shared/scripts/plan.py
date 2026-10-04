#!/usr/bin/env python3
"""Print a concise edit plan from the current project files."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the current edit plan.")
    parser.add_argument("project", help="Project directory.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        media = read_json(project / "media.json")["sources"]
        edl = read_json(project / "edl.json", {"segments": []})["segments"]
        duration = sum(float(s["out"]) - float(s["in"]) for s in edl)
        print("# Edit Plan")
        print(f"Project: {project}")
        print(f"Sources: {len(media)}")
        print(f"Segments: {len(edl)}")
        print(f"Estimated duration: {duration:.1f}s")
        print("Render path: local ffmpeg draft, no uploads, no paid APIs")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

