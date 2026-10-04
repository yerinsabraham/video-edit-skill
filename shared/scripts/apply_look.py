#!/usr/bin/env python3
"""Apply a look preset and optional brand kit to project files."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, skill_root, snapshot_project, write_json


def load_look(name: str) -> dict:
    path = skill_root() / "shared" / "assets" / "looks" / f"{name}.json"
    if not path.exists():
        available = sorted(p.stem for p in (skill_root() / "shared" / "assets" / "looks").glob("*.json"))
        raise SkillError(f"Unknown look '{name}'. Available: {', '.join(available)}")
    return read_json(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a look preset to project.json and recipe.json.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("look", help="Look id, e.g. clean-creator.")
    parser.add_argument("--name", help="Optional new recipe version name.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        look = load_look(args.look)
        snapshot_project(project, f"before-look-{args.look}", f"before applying look {args.look}")

        project_config = read_json(project / "project.json")
        project_config["look"] = look["id"]
        project_config["width"] = look["output"]["width"]
        project_config["height"] = look["output"]["height"]
        write_json(project / "project.json", project_config)

        recipe_path = project / "recipe.json"
        if recipe_path.exists():
            recipe = read_json(recipe_path)
            if args.name:
                recipe["name"] = args.name
                recipe["output"]["review"] = f"renders/{args.name}-review.mp4"
                recipe["output"]["final"] = f"renders/{args.name}.mp4"
                recipe["captions"]["json"] = f"exports/{args.name}.captions.json"
                recipe["captions"]["srt"] = f"exports/{args.name}.srt"
                recipe["captions"]["vtt"] = f"exports/{args.name}.vtt"
            recipe["project"]["look"] = look["id"]
            recipe["output"]["width"] = look["output"]["width"]
            recipe["output"]["height"] = look["output"]["height"]
            recipe["output"]["fps"] = look["output"]["fps"]
            recipe["lookPreset"] = look
            brand_path = project / "brand.json"
            if brand_path.exists():
                recipe["brand"] = read_json(brand_path)
            for segment in recipe.get("segments", []):
                segment["look"] = look["id"]
            write_json(recipe_path, recipe)

        print(f"Applied look {look['id']}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
