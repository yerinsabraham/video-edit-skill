#!/usr/bin/env python3
"""Generate sidecar captions from recipe and transcript."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, write_json, write_srt, write_vtt


def captions_from_recipe(project: Path) -> list[dict]:
    recipe = read_json(project / "recipe.json")
    transcript = read_json(project / "transcript.json", {"words": []})
    words = transcript.get("words", [])
    captions: list[dict] = []
    cursor = 0.0
    for segment in recipe.get("segments", []):
        media_id = segment["mediaId"]
        start = float(segment["in"])
        end = float(segment["out"])
        segment_words = [
            w
            for w in words
            if w.get("mediaId") == media_id and start <= float(w.get("start", 0)) <= end
        ]
        if not segment_words:
            text = segment.get("line") or ""
            if text:
                captions.append({"start": cursor, "end": cursor + (end - start), "text": text[:90]})
        else:
            chunk: list[dict] = []
            for word in segment_words:
                chunk.append(word)
                duration = float(chunk[-1]["end"]) - float(chunk[0]["start"])
                if len(chunk) >= 7 or duration >= 2.8:
                    captions.append(
                        {
                            "start": cursor + float(chunk[0]["start"]) - start,
                            "end": cursor + float(chunk[-1]["end"]) - start,
                            "text": " ".join(w["text"] for w in chunk),
                        }
                    )
                    chunk = []
            if chunk:
                captions.append(
                    {
                        "start": cursor + float(chunk[0]["start"]) - start,
                        "end": cursor + float(chunk[-1]["end"]) - start,
                        "text": " ".join(w["text"] for w in chunk),
                    }
                )
        cursor += end - start
    return captions


def main() -> int:
    parser = argparse.ArgumentParser(description="Write SRT, VTT and JSON captions.")
    parser.add_argument("project", help="Project directory.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        recipe = read_json(project / "recipe.json")
        caps = captions_from_recipe(project)
        write_json(project / recipe["captions"]["json"], caps)
        write_srt(project / recipe["captions"]["srt"], caps)
        write_vtt(project / recipe["captions"]["vtt"], caps)
        print(f"Wrote {len(caps)} caption(s)")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

