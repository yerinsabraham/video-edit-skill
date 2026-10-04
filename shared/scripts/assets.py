#!/usr/bin/env python3
"""Plan, request, and place real media (screenshots, photos, clips) in the edit.

    assets.py <project> suggest                 # read the script, propose moments
    assets.py <project> list                    # show requests and their status
    assets.py <project> provide A1 <file> [--layout pop|split|cover] [--corner top-left]
    assets.py <project> skip A1
    assets.py <project> apply                   # place everything provided

`suggest` writes assets.json and qa/asset-requests.md. The agent reads the
requests to the user, who provides files or skips. Moments that need no file
(numbers, calls to action) are listed as motion graphics instead.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, ffprobe, read_json, snapshot_project, write_json
from captions import SENTENCE_END, timeline_words

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

RULES = [
    # (pattern, kind, layout, request to the user)
    (r"\b(everyone|everybody|people|they)( is| are|'re)? (talking|saying|posting)\b|\byou'?ve (probably )?seen\b|\bon (tiktok|instagram|youtube|twitter|x|linkedin)\b",
     "screenshots", "pop", "Screenshots of other people's posts or videos about this (2 is ideal)."),
    (r"\b(something )?like this\b|\blook at this\b|\bhere'?s (what|how|an example)\b|\bfor example\b|\bthis is what\b",
     "example", "split", "The example you are pointing at: a finished video, a screen recording, or a screenshot."),
    (r"\b(install|download|drop in|drag|open|click|type|run|trigger|set up|sign up)\b",
     "demo", "split", "A screen recording of doing this step."),
    (r"\b(before|after|result|results|transformation)\b",
     "result", "cover", "A before/after or result clip."),
]
AUTO_RULES = [
    (r"\$?\d[\d,.]*\s*(%|percent|k|million|billion|dollars|hours|minutes|days|x)?", "stat", "A number graphic (motion.py stat)."),
    (r"\bcomment\b|\blink in (my )?bio\b|\bfollow\b|\bsubscribe\b|\bdm me\b", "callout", "A call-to-action graphic (motion.py callout)."),
]
MIN_GAP = 4.0


def sentences(project: Path, recipe: dict) -> list[dict]:
    words, _, _ = timeline_words(project, recipe)
    out, current = [], []
    for word in words:
        current.append(word)
        if SENTENCE_END.search(word["text"]):
            out.append(current)
            current = []
    if current:
        out.append(current)
    return [{"start": s[0]["start"], "end": s[-1]["end"], "text": " ".join(w["text"] for w in s)} for s in out]


def suggest(project: Path) -> dict:
    recipe = read_json(project / "recipe.json")
    lines = sentences(project, recipe)
    requests: list[dict] = []
    graphics: list[dict] = []
    last = -MIN_GAP
    corners = ["top-right", "top-left"]
    for line in lines:
        for pattern, kind, note in AUTO_RULES:
            if re.search(pattern, line["text"], re.I) and (kind != "stat" or re.search(r"\d", line["text"])):
                graphics.append({"at": round(line["start"], 2), "kind": kind, "line": line["text"], "note": note})
                break
        if line["start"] - last < MIN_GAP:
            continue
        for pattern, kind, layout, ask in RULES:
            if re.search(pattern, line["text"], re.I):
                rid = f"A{len(requests) + 1}"
                requests.append(
                    {
                        "id": rid,
                        "start": round(line["start"], 2),
                        "end": round(line["end"], 2),
                        "line": line["text"],
                        "kind": kind,
                        "layout": layout,
                        "corner": corners[len(requests) % 2],
                        "ask": ask,
                        "status": "needed",
                        "files": [],
                    }
                )
                last = line["start"]
                break
    if lines and (not requests or requests[0]["start"] > 3):
        requests.insert(
            0,
            {
                "id": "A0", "start": round(lines[0]["start"], 2), "end": round(min(lines[0]["end"], 3.0), 2),
                "line": lines[0]["text"], "kind": "hook", "layout": "pop", "corner": "top-right",
                "ask": "Optional: one striking image or clip for the first 3 seconds (the hook).",
                "status": "needed", "files": [],
            },
        )
    plan = {"requests": requests, "graphics": graphics}
    write_json(project / "assets.json", plan)
    write_report(project, plan)
    return plan


def write_report(project: Path, plan: dict) -> None:
    lines = [
        "# Asset Requests",
        "",
        "Real media makes the edit feel real. Ask the user for each item; every one is optional.",
        "",
        "| ID | When | They say | Ask for | Layout | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in plan["requests"]:
        files = ", ".join(Path(f).name for f in r["files"])
        status = r["status"] + (f" ({files})" if files else "")
        lines.append(f"| {r['id']} | {r['start']:.1f}-{r['end']:.1f}s | {r['line'][:70]} | {r['ask']} | {r['layout']} | {status} |")
    lines += ["", "## Graphics that need no file", ""]
    lines += [f"- {g['at']:.1f}s {g['kind']}: \"{g['line'][:70]}\" - {g['note']}" for g in plan["graphics"]] or ["- None"]
    lines += [
        "",
        "Layouts: `pop` = framed card pops in at a corner; `split` = speaker on one half, media on the other;",
        "`cover` = media fills the screen while the voice continues.",
    ]
    (project / "qa").mkdir(exist_ok=True)
    (project / "qa" / "asset-requests.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def find(plan: dict, rid: str) -> dict:
    for r in plan["requests"]:
        if r["id"].lower() == rid.lower():
            return r
    raise SkillError(f"No request {rid}. Run assets.py list.")


def pop_slots(project: Path, frame_w: int, frame_h: int, aspects: list[float], start: float | None = None, end: float | None = None) -> list[tuple[float, float, float, int]]:
    """(x, y, card width, tilt) for up to two cards, keeping clear of the face."""
    from vision import face_or_default

    face = face_or_default(project, start, end)
    fx0, fx1 = face["x"] * frame_w, (face["x"] + face["w"]) * frame_w
    fy0, fy1 = face["y"] * frame_h, (face["y"] + face["h"]) * frame_h
    head_top = max(0.0, fy0 - face["h"] * frame_h * 0.6)
    margin, gap, safe_top, safe_bottom = frame_w * 0.04, frame_w * 0.03, 220.0, frame_h - 420.0
    left_room, right_room = fx0 - margin - gap, frame_w - fx1 - margin - gap
    centre_y = (fy0 + fy1) / 2
    slots: list[tuple[float, float, float, int]] = []
    if min(left_room, right_room) >= frame_w * 0.22:
        # Flank the face: right first, then left.
        for n, aspect in enumerate(aspects or [1.0]):
            side = "right" if n % 2 == 0 else "left"
            width = min(right_room if side == "right" else left_room, frame_w * 0.42)
            height = width / aspect
            y = min(max(centre_y - height / 2, safe_top), safe_bottom - height)
            x = fx1 + gap if side == "right" else margin + (left_room - width)
            slots.append((x, y, width, 4 if side == "right" else -4))
        return slots
    band = head_top - safe_top - gap
    for n, aspect in enumerate(aspects or [1.0]):
        if band >= frame_h * 0.14:
            height = band
            width = min(height * aspect, frame_w * (0.44 if len(aspects) > 1 else 0.7))
            y = safe_top
        else:
            top = fy1 + gap
            height = max(frame_h * 0.12, safe_bottom - 260 - top)
            width = min(height * aspect, frame_w * 0.44)
            y = top
        x = (frame_w / 2 - width - gap / 2) if len(aspects) > 1 and n == 0 else (frame_w / 2 + gap / 2 if len(aspects) > 1 else (frame_w - width) / 2)
        slots.append((x, y, width, -4 if n == 0 else 4))
    return slots


def media_aspect(path: Path) -> float:
    video = next((st for st in ffprobe(path).get("streams", []) if st.get("codec_type") == "video"), {})
    w, h = int(video.get("width") or 16), int(video.get("height") or 9)
    return w / h if h else 16 / 9


def media_duration(path: Path) -> float:
    return float(ffprobe(path).get("format", {}).get("duration") or 0)


def apply(project: Path) -> int:
    plan = read_json(project / "assets.json")
    recipe = read_json(project / "recipe.json")
    snapshot_project(project, "before-assets", "before placing assets")
    script_dir = Path(__file__).parent
    recipe["layouts"] = [l for l in recipe.get("layouts", []) if not l.get("assetId")]
    recipe["overlays"] = [o for o in recipe.get("overlays", []) if not o.get("assetId")]
    write_json(project / "recipe.json", recipe)
    placed = 0
    for r in plan["requests"]:
        if r["status"] != "provided" or not r["files"]:
            continue
        start, end = float(r["start"]), max(float(r["end"]), float(r["start"]) + 2.0)
        if r["layout"] in {"split", "cover"}:
            recipe = read_json(project / "recipe.json")
            recipe.setdefault("layouts", []).append(
                {"assetId": r["id"], "type": r["layout"], "file": r["files"][0], "start": start, "end": end,
                 "mediaSide": r.get("mediaSide", "top"), "focusY": r.get("focusY", 0.37)}
            )
            write_json(project / "recipe.json", recipe)
            placed += 1
            continue
        # pop: one HyperFrames card per file, staggered. Cards are placed around the face
        # (Vision face box): flanking it when the sides have room, else above the head,
        # else below the chin. Each renders on a canvas just big enough for it.
        frame_w, frame_h = int(recipe["output"]["width"]), int(recipe["output"]["height"])
        slots = pop_slots(project, frame_w, frame_h, [media_aspect(Path(f)) for f in r["files"][:2]], start, end)
        for n, file in enumerate(r["files"][:2]):
            offset = n * 0.6
            duration = max(1.5, end - start - offset)
            name = f"{r['id'].lower()}-{n + 1}"
            aspect = media_aspect(Path(file))
            x0, y0, card_w, tilt = slots[n]
            card_h = card_w / aspect + 20
            pad = 120
            canvas_w, canvas_h = int(card_w + 2 * pad) // 2 * 2, int(card_h + 2 * pad) // 2 * 2
            x, y = int(x0 - pad), int(y0 - pad)
            cmd = [
                sys.executable, str(script_dir / "motion.py"), str(project), "media-pop", "--name", name,
                "--duration", f"{duration:.2f}", "--asset", file, "--size", f"{canvas_w}x{canvas_h}",
                "--var", "corner=canvas", "--var", f"width={card_w / canvas_w * 100:.2f}",
                "--var", f"aspect={aspect:.4f}", "--var", f"tilt={tilt}",
            ]
            credits = r.get("credits", [])
            if n < len(credits) and credits[n]:
                cmd += ["--var", f"caption=@{credits[n]}"]  # other creators are always credited on screen
            subprocess.run(cmd, check=True)
            out = project / "work" / "motion" / f"{name}.mov"
            recipe = read_json(project / "recipe.json")
            recipe.setdefault("overlays", []).append(
                {"assetId": r["id"], "file": str(out), "kind": "video", "start": round(start + offset, 3),
                 "end": round(start + offset + duration, 3), "x": x, "y": y, "width": None, "fade": 0, "label": r["kind"]}
            )
            write_json(project / "recipe.json", recipe)
            placed += 1
    return placed


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan, request, and place real media in the edit.")
    parser.add_argument("project", help="Project directory.")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("suggest", help="Propose moments that want real media.")
    sub.add_parser("list", help="Show requests.")
    pv = sub.add_parser("provide", help="Attach file(s) to a request.")
    pv.add_argument("id")
    pv.add_argument("files", nargs="+")
    pv.add_argument("--layout", choices=["pop", "split", "cover"])
    pv.add_argument("--corner", choices=["top-left", "top-right", "middle-left", "middle-right", "bottom-left", "bottom-right", "center"])
    pv.add_argument("--start", type=float)
    pv.add_argument("--end", type=float)
    pv.add_argument("--media-side", choices=["top", "bottom"], help="Split: which half shows the media.")
    pv.add_argument("--credit", help="@handle of the creator whose post this is (comma-separated per file). Shown on screen.")
    sk = sub.add_parser("skip", help="Skip a request.")
    sk.add_argument("id")
    sub.add_parser("apply", help="Place provided media into recipe.json.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        if args.action == "suggest":
            plan = suggest(project)
            print(f"{len(plan['requests'])} media request(s), {len(plan['graphics'])} graphic idea(s). See qa/asset-requests.md")
            return 0
        plan = read_json(project / "assets.json")
        if args.action == "list":
            for r in plan["requests"]:
                print(f"{r['id']}: {r['start']:.1f}s [{r['layout']}] {r['status']} - {r['ask']}")
            return 0
        if args.action == "apply":
            placed = apply(project)
            print(f"Placed {placed} media item(s). Run assemble.py (if the EDL changed), then render.py --frame to check.")
            return 0
        request = find(plan, args.id)
        if args.action == "skip":
            request["status"] = "skipped"
        else:
            files = [str(Path(f).expanduser().resolve()) for f in args.files]
            for f in files:
                if not Path(f).exists():
                    fail(f"File not found: {f}")
            request.update(status="provided", files=files)
            if args.credit:
                request["credits"] = [c.strip().lstrip("@") for c in args.credit.split(",")]
            for key, value in [("layout", args.layout), ("corner", args.corner), ("start", args.start), ("end", args.end), ("mediaSide", args.media_side)]:
                if value is not None:
                    request[key] = value
            if request["layout"] in {"split", "cover"} and Path(files[0]).suffix.lower() in VIDEO_EXTS and args.end is None:
                request["end"] = round(min(float(request["end"]) + 3, float(request["start"]) + media_duration(Path(files[0]))), 2)
        write_json(project / "assets.json", plan)
        write_report(project, plan)
        print(f"{request['id']}: {request['status']}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    except subprocess.CalledProcessError as exc:
        fail(f"motion render failed: {exc}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
