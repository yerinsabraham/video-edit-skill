#!/usr/bin/env python3
"""Inspect and restore video-edit project state."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from _common import SkillError, ensure_project, fail, load_state, now_iso, save_state, snapshot_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage video-edit project state.")
    parser.add_argument("project", help="Project directory.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List snapshots, renders, and notes.")

    snap = sub.add_parser("snapshot", help="Save current edit files into versions/<name>.")
    snap.add_argument("name")
    snap.add_argument("--note", default="")

    note = sub.add_parser("note", help="Append a human note.")
    note.add_argument("text")

    restore = sub.add_parser("restore", help="Restore a saved snapshot.")
    restore.add_argument("name")

    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        state = load_state(project)

        if args.cmd == "list":
            print("# State")
            print("Snapshots:")
            for item in state.get("history", []):
                print(f"- {item['name']}  {item.get('at', '')}  {item.get('note', '')}")
            print("Renders:")
            for item in state.get("renders", []):
                print(f"- {item.get('name')}  {item.get('final')}  {item.get('captionMode', '')}")
            print("Notes:")
            for item in state.get("notes", []):
                print(f"- {item.get('at', '')}  {item.get('text', '')}")
            return 0

        if args.cmd == "snapshot":
            entry = snapshot_project(project, args.name, args.note)
            print(f"Saved snapshot {entry['name']}")
            return 0

        if args.cmd == "note":
            state.setdefault("notes", []).append({"at": now_iso(), "text": args.text})
            save_state(project, state)
            print("Saved note")
            return 0

        if args.cmd == "restore":
            src_dir = project / "versions" / args.name
            if not src_dir.exists():
                fail(f"Unknown snapshot: {args.name}")
            backup_name = f"before-restore-{now_iso().replace(':', '-')}"
            snapshot_project(project, backup_name, f"before restoring {args.name}")
            for src in src_dir.iterdir():
                if src.is_file():
                    shutil.copy2(src, project / src.name)
            state = load_state(project)
            state["current"] = "recipe.json"
            state.setdefault("notes", []).append({"at": now_iso(), "text": f"restored {args.name}"})
            save_state(project, state)
            print(f"Restored {args.name}")
            return 0

    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

