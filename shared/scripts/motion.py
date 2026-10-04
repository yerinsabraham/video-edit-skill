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

from _common import SkillError, ensure_project, fail, find_exe, log_command, read_json, run_cmd, skill_root, write_json


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


def add_cues(project: Path, template: Path, start: float, duration: float, source: str = "") -> None:
    """Add the template's sound effects (cues.json) at the right moments."""
    cues_file = template / "cues.json"
    if not cues_file.exists():
        return
    spec = json.loads(cues_file.read_text(encoding="utf-8"))
    k = duration / float(spec.get("baseDuration", duration) or duration)
    recipe = read_json(project / "recipe.json")
    sfx = recipe.setdefault("sfx", [])
    for cue in spec.get("cues", []):
        for r in range(int(cue.get("repeat", 1))):
            at = start + (float(cue["t"]) + r * float(cue.get("every", 0))) * k
            if at < start + duration:
                sfx.append({"at": round(at, 3), "kind": cue["kind"], "gain": float(cue.get("gain", -12)), "source": source})
    sfx.sort(key=lambda c: c["at"])
    write_json(project / "recipe.json", recipe)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a HyperFrames motion graphic with alpha.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("template", nargs="?", help="Template name or path to a composition folder. Omit with --list.")
    parser.add_argument("--list", action="store_true", help="List built-in templates.")
    parser.add_argument("--name", help="Output name (default: template name).")
    parser.add_argument("--duration", type=float, default=4.0, help="Seconds.")
    parser.add_argument("--var", action="append", default=[], help="Template variable key=value (repeatable).")
    parser.add_argument("--asset", help="Image or video to place inside the composition (sets src and kind).")
    parser.add_argument("--size", help="Canvas WxH instead of the full frame (smaller renders faster).")
    parser.add_argument("--files", help="Comma-separated files copied into the composition (sets var files).")
    parser.add_argument("--place", choices=["overlay", "split", "cover", "phone"], default="overlay", help="With --start: overlay, top half of a split screen, full cover, or phone (footage shrinks into the frame).")
    parser.add_argument("--x", default="0", help="With --start: overlay x position.")
    parser.add_argument("--y", default="0", help="With --start: overlay y position.")
    parser.add_argument("--no-sfx", action="store_true", help="Do not add the template's sound effects.")
    parser.add_argument("--start", type=float, help="Also add as an overlay starting at this timeline second.")
    parser.add_argument("--label", default="", help="Why this graphic earns its place.")
    parser.add_argument("--behind", action="store_true", help="With --start: place behind the speaker (macOS person mask).")
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
        if args.size:
            width, height = (int(x) for x in args.size.lower().split("x"))
        elif args.place == "split":
            height //= 2
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
        for font in (skill_root() / "shared" / "assets" / "fonts").glob("*.ttf"):
            shutil.copy2(font, work / font.name)  # templates load bundled fonts locally
        index = work / "index.html"
        html = index.read_text(encoding="utf-8")
        html = html.replace("{{WIDTH}}", str(width)).replace("{{HEIGHT}}", str(height)).replace("{{DURATION}}", f"{args.duration:g}")
        index.write_text(html, encoding="utf-8")

        variables = {**brand_vars(project), **parse_vars(args.var)}
        if args.asset:
            asset = Path(args.asset).expanduser().resolve()
            if not asset.exists():
                fail(f"Asset not found: {asset}")
            target = work / f"asset{asset.suffix.lower()}"
            shutil.copy2(asset, target)
            variables["src"] = target.name
            variables["kind"] = "video" if asset.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm"} else "image"
        if args.files:
            names = []
            for i, item in enumerate(f for f in args.files.split(",") if f.strip()):
                src = Path(item.strip()).expanduser().resolve()
                if not src.exists():
                    fail(f"File not found: {src}")
                target = work / f"file{i + 1}{src.suffix.lower()}"
                shutil.copy2(src, target)
                names.append(target.name)
            variables["files"] = ",".join(names)
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
        # A composition with a script error renders as an empty transparent video; catch it.
        ffmpeg = find_exe("ffmpeg")
        if ffmpeg:
            probe = run_cmd(
                [ffmpeg, "-hide_banner", "-ss", f"{args.duration / 2:.2f}", "-i", str(out), "-frames:v", "1",
                 "-vf", "alphaextract,signalstats,metadata=print", "-f", "null", "-"],
                check=False,
            )
            log = (probe.stderr or "") + (probe.stdout or "")
            hi, lo = re.search(r"YMAX=(\d+)", log), re.search(r"YMIN=(\d+)", log)
            if hi and lo and int(hi.group(1)) - int(lo.group(1)) < 8:
                raise SkillError(f"{name} rendered empty. Run: npx {HYPERFRAMES} check {work}")
        log_command(project, "motion", command, "ok", name)
        print(f"Wrote {out}")

        if args.start is not None:
            if args.place == "overlay":
                run_cmd(
                    [
                        sys.executable, str(Path(__file__).with_name("overlay.py")), str(project), "add", str(out),
                        "--start", str(args.start), "--x", str(args.x), "--y", str(args.y), "--label", args.label or name,
                        *(["--behind"] if args.behind else []),
                    ],
                    capture=False,
                )
            else:
                recipe = read_json(project / "recipe.json")
                recipe.setdefault("layouts", []).append(
                    {"type": args.place, "file": str(out), "start": round(args.start, 3), "end": round(args.start + args.duration, 3),
                     "mediaSide": "top", "label": args.label or name, "motion": name}
                )
                write_json(project / "recipe.json", recipe)
                print(f"Placed {name} as {args.place} at {args.start:.2f}-{args.start + args.duration:.2f}s")
            if not args.no_sfx:
                add_cues(project, source, args.start, args.duration, name)
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
