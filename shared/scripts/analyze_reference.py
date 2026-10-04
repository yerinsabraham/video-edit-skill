#!/usr/bin/env python3
"""Create a lightweight reference-video analysis manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, media_info, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a local reference video.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("reference", help="Reference video path.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        ref = Path(args.reference).expanduser().resolve()
        if not ref.exists():
            fail(f"Reference not found: {ref}")
        info = media_info(ref, "reference")
        notes = {
            "reference": info,
            "reviewPrompts": [
                "Describe hook timing, first caption, and first visual change.",
                "List pacing patterns to keep and what should change for this user's topic.",
                "Note caption placement, size, contrast, and safe-zone risks.",
            ],
        }
        write_json(project / "work" / "reference-analysis.json", notes)
        print(f"Wrote {project / 'work' / 'reference-analysis.json'}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

