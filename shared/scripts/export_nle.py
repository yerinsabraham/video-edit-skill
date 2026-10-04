#!/usr/bin/env python3
"""Export a simple rough-cut EDL for NLE handoff."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a simple text EDL handoff.")
    parser.add_argument("project", help="Project directory.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        recipe = read_json(project / "recipe.json")
        out = project / "exports" / f"{recipe['name']}.edl.txt"
        cursor = 0.0
        lines = ["TITLE: video-edit rough cut", "FCM: NON-DROP FRAME", ""]
        for index, segment in enumerate(recipe["segments"], 1):
            duration = float(segment["out"]) - float(segment["in"])
            lines.append(f"{index:03}  AX       V     C        {segment['in']:.3f} {segment['out']:.3f} {cursor:.3f} {cursor + duration:.3f}")
            lines.append(f"* FROM CLIP NAME: {Path(segment['clip']).name}")
            lines.append(f"* COMMENT: {segment.get('line', '')}")
            lines.append("")
            cursor += duration
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {out}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

