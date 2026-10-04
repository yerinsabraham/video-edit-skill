#!/usr/bin/env python3
"""Remove a spoken line from the edit and keep everything else in sync.

    cut.py <project> --text "or something like this"
    cut.py <project> --text "like this" --occurrence 2

Finds the phrase in the transcript, cuts it out of edl.json together with the
pause around it (leaving a natural gap), rebuilds recipe.json, and shifts every
later overlay, layout, zoom, SFX cue and caption window back by the removed
time. Run assemble.py afterwards. Undo with state.py restore before-cut-<n>.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, snapshot_project, write_json

KEEP_GAP = 0.18  # seconds of breath left on each side of the cut


def norm(text: str) -> str:
    return re.sub(r"[^\w']+", "", text.lower())


def find_phrase(words: list[dict], phrase: str, occurrence: int) -> tuple[int, int]:
    target = [norm(t) for t in phrase.split() if norm(t)]
    tokens = [norm(w["text"]) for w in words]
    hits = [i for i in range(len(tokens) - len(target) + 1) if tokens[i : i + len(target)] == target]
    if len(hits) < occurrence:
        raise SkillError(f"'{phrase}' found {len(hits)} time(s); occurrence {occurrence} does not exist")
    start = hits[occurrence - 1]
    return start, start + len(target) - 1


def source_to_timeline(segments: list[dict], media_id: str, t: float) -> float | None:
    cursor = 0.0
    for seg in segments:
        a, b = float(seg["in"]), float(seg["out"])
        if seg.get("mediaId") == media_id and a <= t <= b:
            return cursor + t - a
        cursor += b - a
    return None


def shift_items(recipe: dict, cut_at: float, removed: float) -> int:
    """Move timed items after the cut back by `removed`; trim items that span it."""
    moved = 0

    def shift(item: dict, start_key: str, end_key: str | None) -> bool:
        nonlocal moved
        s = float(item[start_key])
        e = float(item[end_key]) if end_key else s
        if s >= cut_at + removed:
            item[start_key] = round(s - removed, 3)
            if end_key:
                item[end_key] = round(e - removed, 3)
            moved += 1
        elif end_key and e > cut_at:
            item[end_key] = round(max(cut_at, e - removed), 3) if e >= cut_at + removed else round(cut_at, 3)
        elif not end_key and cut_at <= s < cut_at + removed:
            return False  # a cue inside the removed part goes
        return not end_key or float(item[end_key]) - float(item[start_key]) > 0.05

    for key in ["overlays", "layouts", "zooms"]:
        recipe[key] = [i for i in recipe.get(key, []) if shift(i, "start", "end")]
    recipe["sfx"] = [c for c in recipe.get("sfx", []) if shift(c, "at", None)]
    captions = recipe.get("captions", {})
    captions["topWindows"] = [w for w in captions.get("topWindows", []) if shift(w, "start", "end")]
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut a spoken line and keep the edit in sync.")
    parser.add_argument("project")
    parser.add_argument("--text", required=True, help="The words to remove, as spoken.")
    parser.add_argument("--occurrence", type=int, default=1, help="Which occurrence if the phrase repeats.")
    args = parser.parse_args()
    try:
        project = ensure_project(Path(args.project))
        transcript = read_json(project / "transcript.json")
        edl = read_json(project / "edl.json")
        recipe = read_json(project / "recipe.json")
        words = transcript["words"]
        first, last = find_phrase(words, args.text, args.occurrence)
        media_id = words[first]["mediaId"]
        prev_end = float(words[first - 1]["end"]) if first > 0 and words[first - 1]["mediaId"] == media_id else float(words[first]["start"]) - KEEP_GAP
        next_start = float(words[last + 1]["start"]) if last + 1 < len(words) and words[last + 1]["mediaId"] == media_id else float(words[last]["end"]) + KEEP_GAP
        cut_in = round(min(float(words[first]["start"]), prev_end + KEEP_GAP), 3)
        cut_out = round(max(float(words[last]["end"]), next_start - KEEP_GAP), 3)

        timeline_at = source_to_timeline(edl["segments"], media_id, cut_in)
        if timeline_at is None:
            fail("That line is not in the current edit.")
        n = len([h for h in read_json(project / "state.json", {}).get("history", []) if h.get("name", "").startswith("before-cut")]) + 1
        snapshot_project(project, f"before-cut-{n}", f"before cutting '{args.text}'")

        segments = []
        removed = 0.0
        for seg in edl["segments"]:
            a, b = float(seg["in"]), float(seg["out"])
            if seg.get("mediaId") != media_id or b <= cut_in or a >= cut_out:
                segments.append(seg)
                continue
            removed += min(b, cut_out) - max(a, cut_in)
            if a < cut_in:
                segments.append({**seg, "out": cut_in})
            if b > cut_out:
                segments.append({**seg, "in": cut_out})
        for i, seg in enumerate(segments, 1):
            seg["id"] = f"s{i}"
        write_json(project / "edl.json", {"segments": segments})

        moved = shift_items(recipe, timeline_at, removed)
        write_json(project / "recipe.json", recipe)
        sys.argv = ["recipe.py", str(project), "--name", recipe.get("name", "v1")]
        from recipe import main as recipe_main

        recipe_main()
        print(f"Cut '{' '.join(w['text'] for w in words[first:last + 1])}' ({removed:.2f}s at {timeline_at:.2f}s); shifted {moved} item(s). Run assemble.py.")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
