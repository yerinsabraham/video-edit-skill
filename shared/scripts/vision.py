#!/usr/bin/env python3
"""Face boxes and person masks: Apple Vision on macOS, MediaPipe elsewhere.

    vision.py <project> faces            # writes work/faces.json from work/aroll.mp4
    vision.py <project> mask START END   # writes work/masks/<start>-<end>.mov

The Swift helper compiles on first use (needs Xcode command line tools) into
~/.cache/video-edit/bin/vision-helper. Everything runs on the machine.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, read_json, tool_home, write_json

SOURCE = Path(__file__).resolve().parent / "vision" / "VisionHelper.swift"


def use_mediapipe() -> bool:
    forced = os.environ.get("VIDEO_EDIT_VISION", "")
    if forced:
        return forced == "mediapipe"
    return not (platform.system() == "Darwin" and (helper_path().exists() or bool(find_exe("swiftc"))))


def available() -> bool:
    if use_mediapipe():
        from vision_mp import available as mp_available

        return mp_available()
    return True


def helper_path() -> Path:
    return tool_home() / "bin" / "vision-helper"


def helper() -> str:
    exe = helper_path()
    if exe.exists() and exe.stat().st_mtime >= SOURCE.stat().st_mtime:
        return str(exe)
    if platform.system() != "Darwin":
        raise SkillError("Face detection and person masks use Apple Vision and need macOS.")
    swiftc = find_exe("swiftc")
    if not swiftc:
        raise SkillError("swiftc not found. Install the Xcode command line tools: xcode-select --install")
    exe.parent.mkdir(parents=True, exist_ok=True)
    print("Compiling the Vision helper (one time)...")
    result = subprocess.run([swiftc, "-O", "-suppress-warnings", str(SOURCE), "-o", str(exe)], text=True, capture_output=True)
    if result.returncode != 0:
        raise SkillError(f"Vision helper failed to compile:\n{result.stderr[-1500:]}")
    return str(exe)


def extent(boxes: list[dict]) -> dict:
    x0, y0 = min(b["x"] for b in boxes), min(b["y"] for b in boxes)
    x1, y1 = max(b["x"] + b["w"] for b in boxes), max(b["y"] + b["h"] for b in boxes)
    return {"x": round(x0, 4), "y": round(y0, 4), "w": round(x1 - x0, 4), "h": round(y1 - y0, 4)}


def faces(project: Path, samples: int = 0) -> dict:
    """Median face box across the edit, normalised, origin top-left."""
    cache = project / "work" / "faces.json"
    aroll = project / "work" / "aroll.mp4"
    if not aroll.exists():
        raise SkillError("Missing work/aroll.mp4. Run assemble.py first.")
    if cache.exists() and cache.stat().st_mtime >= aroll.stat().st_mtime:
        return read_json(cache)
    if not samples:
        duration = read_json(project / "segments.json", {}).get("duration", 30)
        samples = int(min(240, max(12, duration)))  # about one per second
    if use_mediapipe():
        from vision_mp import faces as mp_faces

        boxes = mp_faces(aroll, samples)
    else:
        result = subprocess.run([helper(), "faces", str(aroll), str(samples)], text=True, capture_output=True)
        if result.returncode != 0:
            raise SkillError(f"Face detection failed: {result.stderr[-500:]}")
        boxes = json.loads(result.stdout or "[]")
    summary = {"samples": boxes, "found": bool(boxes)}
    if boxes:
        summary["face"] = {k: round(statistics.median(b[k] for b in boxes), 4) for k in ["x", "y", "w", "h"]}
        summary["extent"] = extent(boxes)
    write_json(cache, summary)
    return summary


def mask(project: Path, start: float, end: float, quality: str = "balanced") -> Path:
    aroll = project / "work" / "aroll.mp4"
    out = project / "work" / "masks" / f"{start:.2f}-{end:.2f}.mov"
    if out.exists() and out.stat().st_mtime >= aroll.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    if use_mediapipe():
        from vision_mp import mask as mp_mask

        mp_mask(aroll, out, start, end - start)
        return out
    result = subprocess.run(
        [helper(), "mask", str(aroll), str(out), quality, f"{start:.3f}", f"{end - start:.3f}"], text=True, capture_output=True
    )
    if result.returncode != 0 or not out.exists():
        raise SkillError(f"Person mask failed: {result.stderr[-500:]}")
    return out


def face_or_default(project: Path, start: float | None = None, end: float | None = None) -> dict:
    """Where the face is between start and end (all of it, so graphics clear every
    position), from Vision if available, else the typical talking-head position."""
    try:
        data = faces(project) if available() else {}
    except SkillError:
        data = {}
    boxes = data.get("samples", [])
    if start is not None and end is not None:
        window = [b for b in boxes if start - 0.5 <= b["t"] <= end + 0.5]
        if window:
            return extent(window)
    return data.get("extent") or data.get("face") or {"x": 0.33, "y": 0.31, "w": 0.34, "h": 0.2}


def main() -> int:
    parser = argparse.ArgumentParser(description="Face boxes and person masks (macOS Vision).")
    parser.add_argument("project")
    sub = parser.add_subparsers(dest="action", required=True)
    f = sub.add_parser("faces")
    f.add_argument("--samples", type=int, default=12)
    m = sub.add_parser("mask")
    m.add_argument("start", type=float)
    m.add_argument("end", type=float)
    m.add_argument("--quality", choices=["fast", "balanced", "accurate"], default="balanced")
    args = parser.parse_args()
    try:
        project = ensure_project(Path(args.project))
        if args.action == "faces":
            data = faces(project, args.samples)
            print(json.dumps(data.get("face") or "no face found"))
        else:
            print(mask(project, args.start, args.end, args.quality))
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
