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
    parser.add_argument("--max-segment", type=float, default=12.0, help="Maximum seconds per transcript segment.")
    parser.add_argument("--handle", type=float, default=0.08, help="Seconds of cut handle before and after speech.")
    parser.add_argument("--last-repeat", action="store_true", help="When identical lines repeat, keep the last one.")
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
            if end <= start:
                continue
            if end - start > args.max_segment:
                end = start + args.max_segment
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
        write_json(project / "edl.json", {"segments": edl})
        print(f"Wrote {len(edl)} EDL segment(s)")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
