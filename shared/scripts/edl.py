#!/usr/bin/env python3
"""Create a first-pass edit decision list from transcript segments."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, write_json


def segment_score(segment: dict) -> tuple[int, float]:
    text = str(segment.get("text", "")).strip()
    complete = int(len(text.split()) >= 3)
    return (complete, float(segment.get("end", 0)) - float(segment.get("start", 0)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create edl.json from transcript.json.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--max-segment", type=float, default=12.0, help="Warn when a segment is longer than this; speech is never truncated.")
    parser.add_argument("--handle", type=float, default=0.08, help="Seconds of cut handle before and after speech.")
    parser.add_argument("--last-repeat", action="store_true", help="When identical lines repeat, keep the last one.")
    parser.add_argument("--max-pause", type=float, default=0.5, help="Keep pauses up to this long; cut longer ones.")
    parser.add_argument("--keep-pauses", action="store_true", help="Keep every pause between lines (no pause cuts).")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        transcript = read_json(project / "transcript.json")
        media = {item["id"]: item for item in read_json(project / "media.json")["sources"]}
        edl = []
        index = 1
        source_segments = transcript.get("segments", [])
        if args.last_repeat:
            chosen: dict[str, dict] = {}
            passthrough = []
            for segment in source_segments:
                key = " ".join(str(segment.get("text", "")).lower().split())
                if key:
                    previous = chosen.get(key)
                    if previous is None or segment_score(segment) >= segment_score(previous):
                        chosen[key] = segment
                else:
                    passthrough.append(segment)
            source_segments = sorted([*chosen.values(), *passthrough], key=lambda s: (s.get("mediaId", ""), float(s.get("start", 0))))

        for segment in source_segments:
            media_id = segment["mediaId"]
            source = media[media_id]
            start = max(0.0, float(segment["start"]) - args.handle)
            end = min(float(source["duration"]), float(segment["end"]) + args.handle)
            previous = edl[-1] if edl else None
            if previous and previous["mediaId"] == media_id and start < previous["out"]:
                # Handles must not overlap, or the overlap plays twice.
                start = previous["out"]
            if end <= start:
                continue
            if end - start > args.max_segment:
                print(f"WARNING: s{index} runs {end - start:.1f}s; consider splitting it in edl.json")
            edl.append(
                {
                    "id": f"s{index}",
                    "mediaId": media_id,
                    "clip": source["path"],
                    "in": round(start, 3),
                    "out": round(end, 3),
                    "line": segment.get("text", ""),
                    "look": "clean-creator",
                    "zoom": 1.0,
                    "cx": 0.5,
                    "cy": 0.5,
                }
            )
            index += 1
        # Join lines separated by a short pause; only longer pauses become cuts.
        limit = float("inf") if args.keep_pauses else args.max_pause
        merged: list[dict] = []
        cut = 0.0
        for item in edl:
            prev = merged[-1] if merged else None
            if prev and prev["mediaId"] == item["mediaId"] and 0 <= item["in"] - prev["out"] <= limit:
                prev["out"] = item["out"]
                prev["line"] = f"{prev['line']} {item['line']}".strip()
                continue
            if prev and prev["mediaId"] == item["mediaId"] and item["in"] > prev["out"]:
                cut += item["in"] - prev["out"]
            merged.append(item)
        for number, item in enumerate(merged, 1):
            item["id"] = f"s{number}"
        write_json(project / "edl.json", {"segments": merged})
        note = f", cut {cut:.1f}s of pauses over {args.max_pause}s" if cut else ""
        print(f"Wrote {len(merged)} EDL segment(s){note}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
