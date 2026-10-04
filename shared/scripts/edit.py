#!/usr/bin/env python3
"""One command: raw clips in, finished review video out.

    edit.py --clips 5                       # newest 5 clips in your clips folder
    edit.py ~/Downloads/raw-clips --title "Launch reel"
    edit.py --clips 5 --section "soft:the cool aesthetic" --section "studio:tech bro"
    edit.py --project <existing> --from render    # resume from a step

Steps: find clips, ingest, transcribe (whisper.cpp, cleaned), pick the best take
of every line, apply the look, assemble from the original files, auto-edit with
the editing rules (motion graphics render in parallel), grade, sound, render a
full-resolution review copy, QA. Prints what to look at and how to give notes.

Projects are saved in your projects folder (prefs.py; default ~/Movies/Video
Edit on macOS, ~/Videos/Video Edit elsewhere), never inside the skill, and your original clips are never modified.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from _common import SkillError, default_projects, discover_videos, fail, read_json, write_json
from prefs import load as load_prefs

SCRIPTS = Path(__file__).resolve().parent
STEPS = ["ingest", "transcribe", "takes", "look", "assemble", "autoedit", "render", "qa"]
REDUNDANT = re.compile(r"^or (?:something |stuff |one )?like (?:this|that)\W*$", re.I)


def run(script: str, *args: str, quiet: bool = True) -> str:
    result = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise SkillError(f"{script} failed: {detail[-1] if detail else 'no output'}")
    return result.stdout


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "edit"


def find_clips(args: argparse.Namespace, prefs: dict) -> list[Path]:
    if args.sources:
        listed_files = all(Path(s).expanduser().is_file() for s in args.sources)
        clips = discover_videos(args.sources, args.clips, keep_order=args.keep_order or (listed_files and len(args.sources) > 1))
    else:
        folder = Path(prefs.get("clips") or "~/Downloads").expanduser()
        clips = discover_videos([str(folder)], args.clips or None)
        if not args.clips:
            # No count given: take the newest burst (clips recorded within 30 minutes of each other).
            from _common import recorded_at

            stamps = [(recorded_at(c), c) for c in clips]
            stamps.sort()
            burst = []
            for t, c in reversed(stamps):
                if burst and burst[-1][0] - t > 1800:
                    break
                burst.append((t, c))
            clips = [c for _, c in reversed(burst)]
    if not clips:
        raise SkillError("No video clips found. Tell me the folder, or how many of the newest clips to use.")
    return clips


def prune_repeats(project: Path) -> list[str]:
    """Without example footage, a second "or something like this" points at nothing.
    The video itself is shown on the first one (editing rules); drop the repeat."""
    takes = read_json(project / "takes.json", {"lines": []})["lines"]
    provided = [r for r in read_json(project / "assets.json", {"requests": []}).get("requests", []) if r.get("status") == "provided" and r["kind"] == "example"]
    if provided:
        return []
    drops = []
    for prev, line in zip(takes, takes[1:]):
        if REDUNDANT.match(line["text"].strip()) and "like this" in prev["text"].lower() and not line["dropped"]:
            drops.append(line["id"])
    if drops:
        run("takes.py", project, *sum((["--drop", d] for d in drops), []))
    return drops


def main() -> int:
    parser = argparse.ArgumentParser(description="Raw clips in, finished review video out.")
    parser.add_argument("sources", nargs="*", help="Clip files or folders (default: your clips folder).")
    parser.add_argument("--clips", type=int, help="Use the newest N clips.")
    parser.add_argument("--title", help="Project title.")
    parser.add_argument("--project", help="Existing project folder (to resume).")
    parser.add_argument("--from", dest="from_step", choices=STEPS, help="Resume from this step.")
    parser.add_argument("--until", choices=STEPS, help="Stop after this step (e.g. takes, to confirm the line order first).")
    parser.add_argument("--look", help="Look for the whole edit (bold, soft, studio, ...). Default: your saved look.")
    parser.add_argument("--section", action="append", default=[], help='Switch look for a section: "soft:the cool aesthetic".')
    parser.add_argument("--keep-pauses", action="store_true", help="Already-edited footage: keep its pacing.")
    parser.add_argument("--keep-order", action="store_true", help="Use the clips in the order given (default: listed files keep their order; folders go by recording time).")
    parser.add_argument("--no-motion", action="store_true", help="Skip motion graphics (faster draft).")
    args = parser.parse_args()

    prefs = load_prefs()
    started = time.time()
    try:
        if args.project:
            project = Path(args.project).expanduser().resolve()
        else:
            clips = find_clips(args, prefs)
            title = args.title or f"Edit {datetime.now():%b %d %H%M}"
            root = Path(prefs.get("projects") or default_projects()).expanduser()
            project = root / f"{datetime.now():%Y-%m-%d} {slug(title)}"
            print(f"Using {len(clips)} clip(s): " + ", ".join(c.name for c in clips))
        print(f"Project: {project}")
        first = STEPS.index(args.from_step) if args.from_step else 0

        last = STEPS.index(args.until) if args.until else len(STEPS) - 1

        def step(name: str) -> bool:
            if STEPS.index(name) < first or STEPS.index(name) > last:
                return False
            print(f"[{STEPS.index(name) + 1}/{len(STEPS)}] {name}...", flush=True)
            return True

        if step("ingest"):
            run("ingest.py", project, *[str(c) for c in clips], "--title", args.title or project.name, "--keep-order")
        if step("transcribe"):
            run("transcribe.py", project)
        if step("takes"):
            if args.keep_pauses:
                run("edl.py", project, "--last-repeat", "--keep-pauses")
            else:
                print("   " + run("takes.py", project).strip())
                dropped = prune_repeats(project)
                if dropped:
                    print(f"   dropped repeated 'or something like this' ({', '.join(dropped)}): the video itself is the example")
        if step("look"):
            recipe_existing = read_json(project / "recipe.json", {})
            run("recipe.py", project, "--name", recipe_existing.get("name", "v1"))
            run("apply_look.py", project, args.look or prefs.get("look") or "bold")
        if step("assemble"):
            run("validate_recipe.py", project)
            print("   " + run("assemble.py", project).strip().splitlines()[-1])
        if step("autoedit"):
            extra = ["--user", prefs["name"]] if prefs.get("name") else []
            extra += ["--handle", prefs["handle"]] if prefs.get("handle") else []
            for sec in args.section:
                extra += ["--section", sec]
            if args.no_motion:
                extra += ["--only", "zooms,sound,grade"]
            run("assets.py", project, "suggest")
            print("   " + run("autoedit.py", project, *extra).strip().splitlines()[0])
        if step("render"):
            run("render.py", project, "--review")
        if args.until and STEPS.index(args.until) < STEPS.index("render"):
            takes = read_json(project / "takes.json", {"lines": []})["lines"]
            print("\nLine order (qa/takes.md):")
            for n, line in enumerate((l for l in takes if not l["dropped"]), 1):
                note = " (moved to the end: call to action)" if "call to action" in line["reason"] else ""
                print(f"  {n}. [{line['id']}] {line['text'][:70]}{note}")
            print(f"\nStopped after {args.until}. Continue with: edit.py --project \"{project}\" --from {STEPS[STEPS.index(args.until) + 1]}")
            return 0
        if step("qa"):
            qa = subprocess.run([sys.executable, str(SCRIPTS / "qa.py"), str(project), "--render",
                                 str(project / read_json(project / "recipe.json")["output"]["review"])], text=True, encoding="utf-8", errors="replace", capture_output=True)
            status = (qa.stdout or "").strip().split(":")[0] or "REVIEW"
        else:
            status = "skipped"

        recipe = read_json(project / "recipe.json")
        review = project / recipe["output"]["review"]
        requests = [r for r in read_json(project / "assets.json", {"requests": []}).get("requests", []) if r.get("status") == "needed"]
        minutes = (time.time() - started) / 60
        summary = {
            "project": str(project), "review": str(review), "qa": status, "minutes": round(minutes, 1),
            "takes": str(project / "qa" / "takes.md"), "plan": str(project / "qa" / "edit-plan.md"),
            "transcriptReview": str(project / "qa" / "transcript-review.md"), "mediaRequests": len(requests),
        }
        write_json(project / "summary.json", summary)
        print()
        print(f"Done in {minutes:.1f} min. QA: {status}")
        print(f"Watch:  {review}")
        print(f"Takes:  {summary['takes']}")
        print(f"Plan:   {summary['plan']}")
        if requests:
            print(f"Media:  {len(requests)} moment(s) would look better with your own screenshot or clip (qa/asset-requests.md)")
        print("Notes:  tell me what to change, e.g. \"captions bigger\", \"cut the pause before 'or you can'\", \"no zoom at the start\".")
        return 0 if status in {"PASS", "skipped"} else 2
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
