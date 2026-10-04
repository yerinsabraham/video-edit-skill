#!/usr/bin/env python3
"""Analyze transcript timing for editorial decisions."""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, write_json


FILLERS = {
    "um",
    "uh",
    "erm",
    "ah",
    "like",
    "you know",
    "i mean",
    "so",
}


def clean(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze transcript timing and edit signals.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--gap", type=float, default=0.7, help="Silence gap threshold in seconds.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        transcript = read_json(project / "transcript.json")
        words = sorted(transcript.get("words", []), key=lambda w: (w.get("mediaId", ""), float(w.get("start", 0))))
        segments = transcript.get("segments", [])

        fillers = []
        gaps = []
        by_media: dict[str, list[dict]] = defaultdict(list)
        for word in words:
            by_media[word.get("mediaId", "")].append(word)
            text = clean(str(word.get("text", "")))
            if text in FILLERS:
                fillers.append(word)

        for media_id, media_words in by_media.items():
            for prev, current in zip(media_words, media_words[1:]):
                gap = float(current.get("start", 0)) - float(prev.get("end", 0))
                if gap >= args.gap:
                    gaps.append(
                        {
                            "mediaId": media_id,
                            "start": round(float(prev.get("end", 0)), 3),
                            "end": round(float(current.get("start", 0)), 3),
                            "duration": round(gap, 3),
                        }
                    )

        normalized_segments = [clean(str(segment.get("text", ""))) for segment in segments]
        repeats = [
            {"text": text, "count": count}
            for text, count in Counter(t for t in normalized_segments if t).items()
            if count > 1
        ]

        speech_rates = []
        for segment in segments:
            duration = max(0.001, float(segment.get("end", 0)) - float(segment.get("start", 0)))
            count = len(segment.get("words", []) or str(segment.get("text", "")).split())
            speech_rates.append(
                {
                    "segmentId": segment.get("id"),
                    "mediaId": segment.get("mediaId"),
                    "wordsPerMinute": round((count / duration) * 60, 1),
                }
            )

        analysis = {
            "fillers": fillers,
            "gaps": gaps,
            "repeatedLines": repeats,
            "speechRates": speech_rates,
            "summary": {
                "wordCount": len(words),
                "segmentCount": len(segments),
                "fillerCount": len(fillers),
                "gapCount": len(gaps),
                "repeatCount": len(repeats),
            },
        }
        write_json(project / "analysis.json", analysis)
        print(
            "analysis: "
            f"{analysis['summary']['wordCount']} words, "
            f"{analysis['summary']['fillerCount']} fillers, "
            f"{analysis['summary']['gapCount']} gaps"
        )
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

