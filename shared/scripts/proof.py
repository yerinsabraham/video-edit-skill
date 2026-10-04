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
    parser.add_argument("--extended", action="store_true", help="Also render a HyperFrames motion graphic and run face detection and a person mask.")
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
        # Whisper artefacts the cleanup must handle: a misheard product name, a lone
        # comma, a split contraction, and an outro credit nobody said.
        words[3:5] = [
            {"mediaId": "m1", "start": 1.3, "end": 1.5, "text": "cloud"},
            {"mediaId": "m1", "start": 1.5, "end": 1.7, "text": "code"},
            {"mediaId": "m1", "start": 1.7, "end": 1.72, "text": ","},
            {"mediaId": "m1", "start": 1.75, "end": 1.9, "text": "isn"},
            {"mediaId": "m1", "start": 1.9, "end": 2.05, "text": "'t"},
        ]
        transcript["segments"][0]["text"] = " ".join(w["text"] for w in words)
        credit = {"mediaId": "m1", "start": 3.3, "end": 3.9, "text": "Thanks for watching."}
        transcript["segments"].append({"id": "m1-s2", "mediaId": "m1", "start": 3.3, "end": 3.9, "text": credit["text"], "words": [credit]})
        transcript["words"] = words + [credit]
        (project / "transcript.raw.json").write_text(json.dumps(transcript, indent=2) + "\n", encoding="utf-8")
        run_cmd(py("fix_transcript.py", str(project)))
        fixed = json.loads((project / "transcript.json").read_text(encoding="utf-8"))
        tokens = [w["text"] for w in fixed["words"]]
        if "Claude" not in tokens or "code," in tokens or "," in tokens or "isn't" not in tokens:
            fail(f"proof failed: transcript cleanup produced {tokens}")
        if any("watching" in s["text"].lower() for s in fixed["segments"]):
            fail("proof failed: outro credit was not removed")

        # Takes: a retake later in the clip must win over the flubbed first attempt.
        takes_project = temp / "takes-project"
        run_cmd(py("ingest.py", str(takes_project), str(source_dir), "--title", "Takes proof"))
        tw = [("All", 0.1), ("you", 0.3), ("need", 0.5), ("is", 0.7), ("a", 0.8), ("good", 0.9), ("skilk.", 1.1),
              ("All", 2.0), ("you", 2.2), ("need", 2.4), ("is", 2.6), ("a", 2.7), ("good", 2.8), ("skill.", 3.0)]
        twords = [{"mediaId": "m1", "start": t, "end": t + 0.18, "text": w} for w, t in tw]
        (takes_project / "transcript.json").write_text(json.dumps({"engine": "synthetic", "words": twords,
            "segments": [{"id": "m1-s1", "mediaId": "m1", "start": 0.1, "end": 3.2, "text": " ".join(w for w, _ in tw), "words": twords}]}), encoding="utf-8")
        run_cmd(py("takes.py", str(takes_project)))
        takes_data = json.loads((takes_project / "takes.json").read_text(encoding="utf-8"))
        if len(takes_data["lines"]) != 1 or takes_data["lines"][0]["pick"]["start"] < 1.9:
            fail(f"proof failed: take selection did not pick the retake: {takes_data['lines']}")

        # Order: a call to action recorded first still ends the video.
        cta = [("Comment", 0.1), ("skill", 0.3), ("for", 0.5), ("the", 0.6), ("link.", 0.7),
               ("This", 2.0), ("edits", 2.2), ("your", 2.4), ("videos", 2.6), ("for", 2.8), ("you.", 3.0)]
        cwords = [{"mediaId": "m1", "start": t, "end": t + 0.18, "text": w} for w, t in cta]
        (takes_project / "transcript.json").write_text(json.dumps({"engine": "synthetic", "words": cwords,
            "segments": [{"id": "m1-s1", "mediaId": "m1", "start": 0.1, "end": 3.2, "text": " ".join(w for w, _ in cta), "words": cwords}]}), encoding="utf-8")
        run_cmd(py("takes.py", str(takes_project)))
        order = [l["text"] for l in json.loads((takes_project / "takes.json").read_text(encoding="utf-8"))["lines"]]
        if not order or not order[-1].lower().startswith("comment"):
            fail(f"proof failed: call to action was not moved to the end: {order}")

        run_cmd(py("analyze.py", str(project)))
        run_cmd(py("edl.py", str(project), "--last-repeat"))
        run_cmd(
            py(
                "card.py",
                str(project),
                "--title",
                "VIDEO EDIT",
                "--subtitle",
                "LOCAL PROOF",
                "--duration",
                "1.0",
                "--name",
                "intro",
            )
        )
        run_cmd(py("recipe.py", str(project), "--name", "v1"))
        run_cmd(py("brand.py", str(project), "--name", "Proof Brand", "--primary", "#2563eb"))
        run_cmd(py("apply_look.py", str(project), "course-promo", "--name", "v2"))
        run_cmd(py("validate_recipe.py", str(project)))
        # Aligner: words that Whisper ran through a pause must move to where speech resumes.
        from align import align_words

        timed = [{"start": 0.0, "end": 0.5, "text": "one."}, {"start": 0.5, "end": 0.9, "text": "two"}, {"start": 0.9, "end": 1.2, "text": "three."}]
        aligned = align_words(timed, [[0.45, 1.3]], 2.0)
        if not aligned[1]["start"] >= 1.29:
            fail(f"proof failed: aligner left a word in a pause: {aligned}")

        run_cmd(py("assets.py", str(project), "suggest"))

        overlay_png = temp / "badge.png"
        run_cmd([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x2563eb@0.8:s=400x120,format=rgba", "-frames:v", "1", str(overlay_png)])
        run_cmd(py("overlay.py", str(project), "add", str(overlay_png), "--start", "1.2", "--end", "2.4", "--label", "proof badge"))
        plan = json.loads((project / "assets.json").read_text(encoding="utf-8"))
        plan["requests"].append({"id": "T1", "start": 1.4, "end": 2.4, "line": "proof", "kind": "example", "layout": "split",
                                 "corner": "top-right", "ask": "test", "status": "provided", "files": [str(overlay_png)]})
        (project / "assets.json").write_text(json.dumps(plan), encoding="utf-8")
        run_cmd(py("assets.py", str(project), "apply"))
        run_cmd(py("captions.py", str(project), "--emphasis", "working"))
        try:
            run_cmd(py("render.py", str(project), "--review"))
            fail("proof failed: render.py accepted a stale assembly")
        except SkillError:
            pass
        run_cmd(py("assemble.py", str(project)))
        run_cmd(py("grade.py", str(project), "--preset", "warm"))
        if "eq=" not in json.loads((project / "recipe.json").read_text(encoding="utf-8")).get("grade", {}).get("filter", ""):
            fail("proof failed: grade was not written")
        run_cmd(py("render.py", str(project), "--review"))
        run_cmd(py("captions_ass.py", str(project)))
        caps = json.loads((project / "exports" / "v2.captions.json").read_text(encoding="utf-8"))
        if caps["mode"] != "short" or any(len(c["text"]) > 20 and len(c["text"].split()) > 1 for c in caps["captions"]):
            fail(f"proof failed: short-form caption rules broken: {caps}")
        if not any(c.get("emphasis") and c["text"].upper() == "WORKING" for c in caps["captions"]):
            fail(f"proof failed: emphasis card missing: {[c['text'] for c in caps['captions']]}")
        if "Dialogue:" not in (project / "exports" / "v2.ass").read_text(encoding="utf-8"):
            fail("proof failed: ASS captions were not written")
        before = len(json.loads((project / "recipe.json").read_text(encoding="utf-8"))["segments"])
        run_cmd(py("cut.py", str(project), "--text", "isn't"))
        after = json.loads((project / "recipe.json").read_text(encoding="utf-8"))["segments"]
        if len(after) <= before:
            fail("proof failed: cut.py did not split the edit")
        run_cmd(py("assemble.py", str(project)))
        run_cmd(py("captions.py", str(project), "--size", "1.2", "--position", "top"))
        if json.loads((project / "recipe.json").read_text(encoding="utf-8"))["captions"]["style"].get("position") != "top":
            fail("proof failed: caption notes were not saved")
        run_cmd(py("autoedit.py", str(project), "--plan"))
        run_cmd(py("autoedit.py", str(project), "--only", "zooms,sound"))
        run_cmd(py("render.py", str(project), "--review"))
        run_cmd(py("qa.py", str(project), "--render", str(project / "renders" / "v2-review.mp4"), "--allow-sidecar-captions"))
        (project / "chapters.json").write_text(json.dumps([{"at": 0, "title": "What the proof edit covers"}, {"at": 1.4, "title": "How the main point lands"}]), encoding="utf-8")
        run_cmd(py("chapters.py", str(project)))
        if not (project / "exports" / "v2.chapters.vtt").exists():
            fail("proof failed: chapters were not written")
        run_cmd(py("transcript_edit.py", str(project), "--name", "v3", "--remove-fillers"))

        edl = json.loads((project / "edl.json").read_text(encoding="utf-8"))
        text = " ".join(segment.get("line", "") for segment in edl["segments"]).lower()
        if " um " in f" {text} " or " uh " in f" {text} ":
            fail("proof failed: filler words remained in transcript edit")
        if args.extended:
            # Motion graphics through npx (npx.cmd on Windows) and the cut-out engine.
            run_cmd(py("motion.py", str(project), "callout", "--name", "proof-callout", "--duration", "1.2",
                       "--var", "eyebrow=PROOF", "--var", "text=motion works", "--start", "0.5", "--workers", "1"))
            if not (project / "work" / "motion" / "proof-callout.mov").exists():
                fail("proof failed: motion graphic was not rendered")
            run_cmd(py("vision.py", str(project), "faces", "--samples", "3"))
            run_cmd(py("vision.py", str(project), "mask", "0.5", "1.5"))
            if not any((project / "work" / "masks").glob("*.mov")):
                fail("proof failed: person mask was not written")
            run_cmd(py("assemble.py", str(project)))
            run_cmd(py("render.py", str(project), "--review"))
            print("extended proof OK: motion graphics and cut-out")
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
