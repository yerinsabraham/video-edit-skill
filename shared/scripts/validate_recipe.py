#!/usr/bin/env python3
"""Validate a video-edit recipe before rendering."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json


def validate(project: Path) -> list[str]:
    errors: list[str] = []
    recipe = read_json(project / "recipe.json")
    if not recipe.get("segments"):
        errors.append("recipe has no segments")
    output = recipe.get("output", {})
    if output.get("width", 0) <= 0 or output.get("height", 0) <= 0:
        errors.append("output width/height must be positive")
    for segment in recipe.get("segments", []):
        clip = Path(segment.get("clip", ""))
        if not clip.exists():
            errors.append(f"missing source clip: {clip}")
        if float(segment.get("out", 0)) <= float(segment.get("in", 0)):
            errors.append(f"segment {segment.get('id')} has invalid in/out")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate recipe.json.")
    parser.add_argument("project", help="Project directory.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        errors = validate(project)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("recipe OK")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

