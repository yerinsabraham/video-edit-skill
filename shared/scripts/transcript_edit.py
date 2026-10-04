#!/usr/bin/env python3
"""Create a new EDL by deleting transcript words or fillers."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, is_filler, read_json, snapshot_project, write_json
from recipe import main as recipe_main


def clean(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def should_delete(word: dict, delete_texts: list[str], remove_fillers: bool) -> bool:
    text = clean(str(word.get("text", "")))
    if remove_fillers and is_filler(word.get("text", "")):
        return True
    return any(text == clean(item) for item in delete_texts)


def group_words(words: list[dict], max_gap: float, max_segment: float) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if not current:
            current = [word]
            continue
        gap = float(word["start"]) - float(current[-1]["end"])
        duration = float(word["end"]) - float(current[0]["start"])
        if gap > max_gap or duration > max_segment or word["mediaId"] != current[-1]["mediaId"] or word.get("_cut"):
            groups.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        groups.append(current)
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a revised EDL from transcript word edits.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--name", required=True, help="New recipe/render version name.")
    parser.add_argument("--remove-fillers", action="store_true", help="Remove common filler words.")
    parser.add_argument("--delete-word", action="append", default=[], help="Delete exact normalized word.")
    parser.add_argument("--max-gap", type=float, default=0.45, help="Maximum gap inside a kept word group.")
    parser.add_argument("--max-segment", type=float, default=10.0, help="Maximum seconds per EDL segment.")
    parser.add_argument("--handle", type=float, default=0.06, help="Seconds of handle around kept groups.")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        transcript = read_json(project / "transcript.json")
        media = {item["id"]: item for item in read_json(project / "media.json")["sources"]}
        # A deleted word always forces a cut, and handles never reach into it.
        words = []
        deleted_end = None
        for word in transcript.get("words", []):
            if should_delete(word, args.delete_word, args.remove_fillers):
                deleted_end = (word["mediaId"], float(word["end"]))
                if words and words[-1]["mediaId"] == word["mediaId"]:
                    words[-1]["_limit"] = float(word["start"])
                continue
            item = dict(word)
            if deleted_end and deleted_end[0] == word["mediaId"]:
                item["_cut"] = True
                item["_floor"] = deleted_end[1]
            deleted_end = None
            words.append(item)
        if not words:
            fail("Transcript edit removed every word.")

        snapshot_project(project, f"before-{args.name}", f"before transcript edit {args.name}")
        edl_segments = []
        for index, group in enumerate(group_words(words, args.max_gap, args.max_segment), 1):
            media_id = group[0]["mediaId"]
            source = media[media_id]
            start = max(0.0, group[0].get("_floor", 0.0), float(group[0]["start"]) - args.handle)
            end = min(float(source["duration"]), group[-1].get("_limit", float("inf")), float(group[-1]["end"]) + args.handle)
            previous = edl_segments[-1] if edl_segments else None
            if previous and previous["mediaId"] == media_id and start < previous["out"] <= end:
                start = previous["out"]
            if end <= start:
                continue
            edl_segments.append(
                {
                    "id": f"s{index}",
                    "mediaId": media_id,
                    "clip": source["path"],
                    "in": round(start, 3),
                    "out": round(end, 3),
                    "line": " ".join(str(word.get("text", "")).strip() for word in group).strip(),
                    "look": "clean-creator",
                    "zoom": 1.0,
                    "cx": 0.5,
                    "cy": 0.5,
                }
            )

        write_json(project / "edl.json", {"segments": edl_segments})
        old_argv = sys.argv
        sys.argv = ["recipe.py", str(project), "--name", args.name]
        try:
            recipe_main()
        finally:
            sys.argv = old_argv
        snapshot_project(project, args.name, args.note or "transcript edit applied")
        print(f"Created transcript edit {args.name} with {len(edl_segments)} segment(s)")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

