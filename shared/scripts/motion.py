#!/usr/bin/env python3
"""Render a transparent motion graphic with HyperFrames and optionally place it.

Optional tier: needs Node 22+ and downloads HyperFrames (Apache-2.0) and a
headless Chrome via npx on first use. Output is ProRes 4444 with alpha, which
render.py composites over the edit. Telemetry is disabled for every render.

Templates live in shared/assets/motion/<name>/index.html. An agent may also
author its own composition folder and pass its path instead of a template name.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, log_command, read_json, run_cmd, skill_root


HYPERFRAMES = os.environ.get("VIDEO_EDIT_HYPERFRAMES", "hyperframes@0.8.123")
TEMPLATES = skill_root() / "shared" / "assets" / "motion"


def node_major(node: str) -> int:
    out = run_cmd([node, "--version"], check=False).stdout or ""
    match = re.match(r"v(\d+)", out.strip())
    return int(match.group(1)) if match else 0


def parse_vars(items: list[str]) -> dict:
    values: dict = {}
    for item in items:
        if "=" not in item:
            raise SkillError(f"--var expects key=value, got {item!r}")
        key, value = item.split("=", 1)
        try:
            values[key] = json.loads(value) if re.fullmatch(r"-?\d+(\.\d+)?", value) else value
        except json.JSONDecodeError:
            values[key] = value
    return values


def brand_vars(project: Path) -> dict:
    recipe = read_json(project / "recipe.json", {})
    brand = recipe.get("brand") or read_json(project / "brand.json", {})
    out = {}
    if brand.get("accent"):
        out["accent"] = brand["accent"]
    if brand.get("background"):
        out["panel"] = brand["background"]
    if brand.get("font") and brand["font"] != "Arial":
        out["font"] = f"{brand['font']}, Arial, sans-serif"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a HyperFrames motion graphic with alpha.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("template", nargs="?", help="Template name or path to a composition folder. Omit with --list.")
    parser.add_argument("--list", action="store_true", help="List built-in templates.")
    parser.add_argument("--name", help="Output name (default: template name).")
    parser.add_argument("--duration", type=float, default=4.0, help="Seconds.")
    parser.add_argument("--var", action="append", default=[], help="Template variable key=value (repeatable).")
    parser.add_argument("--start", type=float, help="Also add as an overlay starting at this timeline second.")
    parser.add_argument("--label", default="", help="Why this graphic earns its place.")
    args = parser.parse_args()

    try:
        if args.list or not args.template:
            for folder in sorted(p for p in TEMPLATES.iterdir() if (p / "index.html").exists()):
                first = (folder / "index.html").read_text(encoding="utf-8").split("-->")[0]
                note = " ".join(first.split("<!--")[-1].split()) if "<!--" in first else ""
                print(f"{folder.name}: {note}")
            return 0

        project = ensure_project(Path(args.project))
        npx, node = find_exe("npx"), find_exe("node")
        if not npx or not node:
            fail("Motion graphics need Node.js 22+ (npx). Install Node, or use a PNG overlay with overlay.py.")
        if node_major(node) < 22:
            fail("HyperFrames needs Node.js 22 or newer.")

        recipe = read_json(project / "recipe.json")
        width, height, fps = int(recipe["output"]["width"]), int(recipe["output"]["height"]), int(recipe["output"]["fps"])
        source = Path(args.template).expanduser()
        if not (source / "index.html").exists():
            source = TEMPLATES / args.template
        if not (source / "index.html").exists():
            fail(f"Unknown template {args.template}. Run motion.py --list.")

        name = args.name or source.name
        work = project / "work" / "motion" / name
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(source, work)
        index = work / "index.html"
        html = index.read_text(encoding="utf-8")
        html = html.replace("{{WIDTH}}", str(width)).replace("{{HEIGHT}}", str(height)).replace("{{DURATION}}", f"{args.duration:g}")
        index.write_text(html, encoding="utf-8")

        variables = {**brand_vars(project), **parse_vars(args.var)}
        vars_file = work / "variables.json"
        vars_file.write_text(json.dumps(variables, indent=2), encoding="utf-8")
        out = project / "work" / "motion" / f"{name}.mov"
        command = [
            npx, "--yes", HYPERFRAMES, "render", str(work),
            "--format", "mov", "--fps", str(fps), "--output", str(out),
            "--variables-file", str(vars_file), "--quiet",
        ]
        env = {**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_SKIP_SKILLS": "1"}
        print(f"Rendering {name} ({args.duration:g}s, {width}x{height}) with {HYPERFRAMES}...")
        result = subprocess.run(command, env=env, text=True, capture_output=True)
        if result.returncode != 0 or not out.exists():
            raise SkillError(f"HyperFrames render failed:\n{(result.stderr or result.stdout)[-2000:]}")
        log_command(project, "motion", command, "ok", name)
        print(f"Wrote {out}")

        if args.start is not None:
            run_cmd(
                [
                    sys.executable, str(Path(__file__).with_name("overlay.py")), str(project), "add", str(out),
                    "--start", str(args.start), "--x", "0", "--y", "0", "--label", args.label or name,
                ],
                capture=False,
            )
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
