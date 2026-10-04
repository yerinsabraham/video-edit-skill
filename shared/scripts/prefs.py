#!/usr/bin/env python3
"""The creator's saved preferences, asked once on the first run.

    prefs.py show
    prefs.py set name="Yerins" handle=yerins.ai look=bold clips=~/Downloads
    prefs.py path

Stored in ~/.config/video-edit/profile.json (override with VIDEO_EDIT_CONFIG).
Keys: name, handle (no @), look (bold, soft, studio, or any look id), clips
(folder new clips land in), projects (where edits are saved), apifyToken
(optional, to pull reels and profile stats), music (optional default track).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

DEFAULTS = {
    "name": "",
    "handle": "",
    "look": "bold",
    "clips": "~/Downloads",
    "projects": "~/Movies/Video Edit",
}


def profile_path() -> Path:
    return Path(os.environ.get("VIDEO_EDIT_CONFIG", "~/.config/video-edit/profile.json")).expanduser()


def load() -> dict:
    path = profile_path()
    data = dict(DEFAULTS)
    if path.exists():
        data.update(json.loads(path.read_text(encoding="utf-8")))
    data["configured"] = path.exists()
    return data


def save(data: dict) -> Path:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in data.items() if k != "configured"}
    path.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)  # may hold an API token
    except OSError:
        pass
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Show or set the creator profile.")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show")
    sub.add_parser("path")
    setp = sub.add_parser("set")
    setp.add_argument("pairs", nargs="+", help="key=value")
    args = parser.parse_args()
    if args.action == "path":
        print(profile_path())
        return 0
    data = load()
    if args.action == "set":
        for pair in args.pairs:
            key, _, value = pair.partition("=")
            if key == "handle":
                value = value.lstrip("@")
            data[key.strip()] = value.strip()
        print(f"Saved {save(data)}")
    shown = {k: ("•••" if k.lower().endswith("token") and v else v) for k, v in data.items()}
    print(json.dumps(shown, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
