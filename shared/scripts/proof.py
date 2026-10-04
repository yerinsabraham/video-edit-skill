#!/usr/bin/env python3
"""Run a synthetic end-to-end proof of the video-edit pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from _common import SkillError, fail, find_exe, run_cmd


ROOT = Path(__file__).resolve().parents[2]


def py(script: str, *args: str) -> list[str]:
    import sys

    return [sys.executable, str(ROOT / "shared" / "scripts" / script), *args]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a synthetic video-edit proof.")
    parser.add_argument("--keep", action="store_true", help="Keep temporary project after the run.")
    args = parser.parse_args()

    ffmpeg = find_exe("ffmpeg")
    if not ffmpeg:
        fail("ffmpeg is required for proof.py")

    temp = Path(tempfile.mkdtemp(prefix="video-edit-proof-"))
    source_dir = temp / "source"
    project = temp / "project"
    source_dir.mkdir(parents=True)
    clip = source_dir / "clip1.mp4"

    try:
        run_cmd(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=720x1280:rate=30:duration=4",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=4",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(clip),
            ]
        )

        run_cmd(py("ingest.py", str(project), str(source_dir), "--title", "Proof edit"))

        words = [
            {"mediaId": "m1", "start": 0.2, "end": 0.45, "text": "um"},
            {"mediaId": "m1", "start": 0.55, "end": 0.9, "text": "this"},
            {"mediaId": "m1", "start": 0.95, "end": 1.25, "text": "is"},
            {"mediaId": "m1", "start": 1.3, "end": 1.7, "text": "video"},
            {"mediaId": "m1", "start": 1.75, "end": 2.05, "text": "edit"},
            {"mediaId": "m1", "start": 2.3, "end": 2.55, "text": "uh"},
            {"mediaId": "m1", "start": 2.7, "end": 3.0, "text": "working"},
        ]
        transcript = {
            "engine": "synthetic",
            "segments": [
                {
                    "id": "m1-s1",
                    "mediaId": "m1",
                    "start": 0.2,
                    "end": 3.0,
                    "text": "um this is video edit uh working",
                    "words": words,
                }
            ],
            "words": words,
        }
        (project / "transcript.json").write_text(json.dumps(transcript, indent=2) + "\n", encoding="utf-8")

        run_cmd(py("analyze.py", str(project)))
        run_cmd(py("edl.py", str(project), "--last-repeat"))
        run_cmd(py("recipe.py", str(project), "--name", "v1"))
        run_cmd(py("brand.py", str(project), "--name", "Proof Brand", "--primary", "#2563eb"))
        run_cmd(py("apply_look.py", str(project), "course-promo", "--name", "v2"))
        run_cmd(py("validate_recipe.py", str(project)))
        run_cmd(py("assemble.py", str(project)))
        run_cmd(py("render.py", str(project), "--review"))
        run_cmd(py("qa.py", str(project), "--render", str(project / "renders" / "v2-review.mp4")))
        run_cmd(py("transcript_edit.py", str(project), "--name", "v3", "--remove-fillers"))

        edl = json.loads((project / "edl.json").read_text(encoding="utf-8"))
        text = " ".join(segment.get("line", "") for segment in edl["segments"]).lower()
        if " um " in f" {text} " or " uh " in f" {text} ":
            fail("proof failed: filler words remained in transcript edit")
        print(f"proof OK: {project}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    finally:
        if not args.keep:
            shutil.rmtree(temp, ignore_errors=True)
        else:
            print(f"kept proof directory: {temp}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
