#!/usr/bin/env python3
"""Create or inspect a project brand kit."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, write_json


HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_color(value: str, name: str) -> str:
    if not HEX.match(value):
        raise SkillError(f"{name} must be a hex color like #2563eb")
    return value.lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or inspect brand.json.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--name", help="Brand name.")
    parser.add_argument("--primary", default="#2563eb", help="Primary brand color.")
    parser.add_argument("--accent", default="#22c55e", help="Accent brand color.")
    parser.add_argument("--background", default="#0f172a", help="Background color.")
    parser.add_argument("--font", default="Arial", help="Preferred font family.")
    parser.add_argument("--logo", help="Optional local logo path.")
    parser.add_argument("--show", action="store_true", help="Print the current brand kit.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        brand_path = project / "brand.json"
        if args.show:
            print(read_json(brand_path, {}))
            return 0
        logo = str(Path(args.logo).expanduser().resolve()) if args.logo else None
        if logo and not Path(logo).exists():
            fail(f"Logo does not exist: {logo}")
        brand = {
            "name": args.name or read_json(project / "project.json", {}).get("title", "Untitled brand"),
            "primary": validate_color(args.primary, "primary"),
            "accent": validate_color(args.accent, "accent"),
            "background": validate_color(args.background, "background"),
            "font": args.font,
            "logo": logo,
        }
        write_json(brand_path, brand)
        print(f"Wrote {brand_path}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

