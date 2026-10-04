#!/usr/bin/env python3
"""Write chapter sidecars for long-form edits.

The agent reads the transcript and writes chapters.json:

    [{"at": 0, "title": "Why the editor is the bottleneck"},
     {"at": 184.2, "title": "How to cut filler words from the transcript"}]

`at` is a timeline second (the edit, including any intro card). Starts snap to
the nearest caption cue, so a chapter never opens mid-sentence. Titles should
name the question somebody would search for, not the section.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, seconds_to_vtt, write_json


def clock(value: float) -> str:
    total = int(round(value))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Snap chapters to cues and write VTT plus description text.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--file", default="chapters.json", help="Chapter list relative to the project.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        recipe = read_json(project / "recipe.json")
        chapters = read_json(project / args.file)
        captions = read_json(project / recipe["captions"]["json"], {"captions": []})
        cues = captions["captions"] if isinstance(captions, dict) else captions
        starts = sorted({0.0, *(float(c["start"]) for c in cues)})
        duration = sum(float(s["out"]) - float(s["in"]) for s in recipe["segments"])

        snapped = []
        for item in sorted(chapters, key=lambda c: float(c["at"])):
            at = min(starts, key=lambda t: abs(t - float(item["at"]))) if starts else float(item["at"])
            snapped.append({"at": round(at, 3), "title": item["title"].strip()})
        if not snapped:
            fail("chapters.json is empty")
        snapped[0]["at"] = 0.0

        warnings = []
        if len(snapped) < 3:
            warnings.append("YouTube needs at least 3 chapters")
        for a, b in zip(snapped, snapped[1:]):
            if b["at"] - a["at"] < 10:
                warnings.append(f"'{a['title']}' is under 10 s")
            elif b["at"] - a["at"] > 300:
                warnings.append(f"'{a['title']}' runs over 5 min; consider splitting")
        for item in snapped:
            if len(item["title"].split()) < 3:
                warnings.append(f"'{item['title']}' is a label; name the question a viewer would search for")

        name = recipe["name"]
        vtt = ["WEBVTT", ""]
        for i, item in enumerate(snapped):
            end = snapped[i + 1]["at"] if i + 1 < len(snapped) else duration
            vtt += [f"{seconds_to_vtt(item['at'])} --> {seconds_to_vtt(end)}", item["title"], ""]
        out_vtt = project / "exports" / f"{name}.chapters.vtt"
        out_vtt.write_text("\n".join(vtt), encoding="utf-8")
        out_txt = project / "exports" / f"{name}.chapters.txt"
        out_txt.write_text("\n".join(f"{clock(c['at'])} {c['title']}" for c in snapped) + "\n", encoding="utf-8")
        write_json(project / "exports" / f"{name}.chapters.json", snapped)
        print(f"Wrote {len(snapped)} chapter(s): {out_vtt.name}, {out_txt.name}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
