#!/usr/bin/env python3
"""Check local requirements for the video-edit skill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import platform_report, run_cmd, skill_root, write_json


def has_ffmpeg_filter(ffmpeg: str | None, name: str) -> bool:
    if not ffmpeg:
        return False
    result = run_cmd([ffmpeg, "-hide_banner", "-filters"], check=False, capture=True)
    return name in (result.stdout or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check video-edit skill dependencies.")
    parser.add_argument("--json", action="store_true", help="Print the platform report as JSON.")
    args = parser.parse_args()

    report = platform_report()
    report["ffmpegFilters"] = {
        "subtitles": has_ffmpeg_filter(report.get("ffmpeg"), "subtitles"),
        "drawtext": has_ffmpeg_filter(report.get("ffmpeg"), "drawtext"),
    }
    root = skill_root()
    write_json(root / ".platform.json", report)

    missing = [name for name in ["ffmpeg", "ffprobe"] if not report.get(name)]
    optional = [name for name in ["whisper", "node", "npm"] if not report.get(name)]

    if args.json:
        import json

        print(json.dumps(report, indent=2))
    else:
        print("video-edit setup")
        print(f"  platform: {report['os']} {report['machine']}")
        print(f"  python:   {report['pythonVersion']} ({report['python']})")
        print(f"  ffmpeg:   {report.get('ffmpeg') or 'MISSING'}")
        print(f"  ffprobe:  {report.get('ffprobe') or 'MISSING'}")
        print(f"  whisper:  {report.get('whisper') or 'optional'}")
        print(f"  node:     {report.get('node') or 'optional'}")
        print(f"  captions: {'burn-in' if report['ffmpegFilters']['subtitles'] else 'sidecar only'}")

    if missing:
        print("\nMissing required tools: " + ", ".join(missing), file=sys.stderr)
        if sys.platform == "darwin":
            print("Install with: brew install ffmpeg", file=sys.stderr)
        elif sys.platform.startswith("linux"):
            print("Install with: sudo apt install ffmpeg", file=sys.stderr)
        elif sys.platform.startswith("win"):
            print("Install with: winget install Gyan.FFmpeg", file=sys.stderr)
        return 1

    if optional and not args.json:
        print("Optional tools missing: " + ", ".join(optional))
    print("READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
