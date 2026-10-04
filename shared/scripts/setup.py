#!/usr/bin/env python3
"""Check local requirements for the video-edit skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from _common import ffmpeg_filters, platform_report, run_cmd, skill_root, tool_home, whisper_model, write_json


MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin"


def download_model(name: str) -> Path:
    target = tool_home() / "models" / f"ggml-{name}.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    print(f"Downloading {name} to {target} ...")
    urllib.request.urlretrieve(MODEL_URL.format(name=name), partial)
    partial.rename(target)
    return target


def node_major(node: str | None) -> int:
    if not node:
        return 0
    match = re.match(r"v(\d+)", (run_cmd([node, "--version"], check=False).stdout or "").strip())
    return int(match.group(1)) if match else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check video-edit skill dependencies.")
    parser.add_argument("--json", action="store_true", help="Print the platform report as JSON.")
    parser.add_argument("--download-model", nargs="?", const="small.en", help="Download a whisper.cpp model (default small.en).")
    args = parser.parse_args()

    if args.download_model:
        download_model(args.download_model)

    report = platform_report()
    filters = ffmpeg_filters(report.get("ffmpeg"))
    report["ffmpegFilters"] = {name: name in filters for name in ["ass", "subtitles", "drawtext"]}
    report["whisperModel"] = str(whisper_model() or "")
    report["nodeMajor"] = node_major(report.get("node"))
    write_json(skill_root() / ".platform.json", report)

    missing = [name for name in ["ffmpeg", "ffprobe"] if not report.get(name)]
    burn = report["ffmpegFilters"]["ass"] or report["ffmpegFilters"]["subtitles"]
    engine = "whisper.cpp" if report.get("whisperCli") and report["whisperModel"] else ("whisper" if report.get("whisper") else "")
    motion = report["nodeMajor"] >= 22

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("video-edit setup")
        print(f"  platform:   {report['os']} {report['machine']}")
        print(f"  python:     {report['pythonVersion']} ({report['python']})")
        print(f"  ffmpeg:     {report.get('ffmpeg') or 'MISSING'}")
        print(f"  ffprobe:    {report.get('ffprobe') or 'MISSING'}")
        print(f"  captions:   {'burn-in (libass)' if burn else 'SIDECAR ONLY - ffmpeg has no libass'}")
        print(f"  transcribe: {engine or 'none (placeholder transcripts only)'}")
        if report.get("whisperCli"):
            print(f"  model:      {report['whisperModel'] or 'MISSING - run setup.py --download-model'}")
        print(f"  motion:     {'HyperFrames via npx (Node ' + str(report['nodeMajor']) + ')' if motion else 'off - needs Node 22+'}")

    if missing:
        print("\nMissing required tools: " + ", ".join(missing), file=sys.stderr)
        if sys.platform == "darwin":
            print("Install with: brew install ffmpeg", file=sys.stderr)
        elif sys.platform.startswith("linux"):
            print("Install with: sudo apt install ffmpeg", file=sys.stderr)
        elif sys.platform.startswith("win"):
            print("Install with: winget install Gyan.FFmpeg", file=sys.stderr)
        return 1

    if not args.json:
        if not burn:
            print("\nCaptions will not be burned in. See shared/references/troubleshooting.md (captions)")
        if not engine:
            print("No transcription engine. See shared/references/troubleshooting.md (transcription)")
    print("READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
