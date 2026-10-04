#!/usr/bin/env python3
"""Apply the default editing rules (shared/references/editing-rules.md) to a project.

    autoedit.py <project> --plan          # write qa/edit-plan.md, change nothing
    autoedit.py <project>                 # plan and build every beat
    autoedit.py <project> --skip logo-2.1 # drop a beat for good, then rebuild
    autoedit.py <project> --only zooms,captions,sound  # cheap passes, no motion renders

Reads the timeline transcript and finds the beats the rules call for: the hook,
logos on product names, a code window on "skill", a UI demo on a described
workflow, a comment sheet on a call to action, claims as big text behind the
speaker, numbers as stats, and zooms to keep a change every few seconds. It
builds them with motion.py, places them around the face, adds the sound cues,
and sets captions, grade and loudness. Everything it adds is tagged auto and
replaced on the next run; anything placed by hand is left alone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, read_json, run_cmd, skill_root, write_json
from assets import pop_slots, sentences
from captions import POWER_WORDS, timeline_words
from logos import PRODUCTS, fetch, find_products

SCRIPTS = Path(__file__).resolve().parent
WORKFLOW = re.compile(r"\b(drop|drag|upload|install|trigger|type|paste|click|run|open|import|connect)\b", re.I)
ARTIFACT = re.compile(r"\b(skill|prompt|file|template|script|workflow file|config)\b", re.I)
CTA = re.compile(r"\b(comment|dm me|message me)\b\W+(?:me\W+)?[\"'“]?(\w+)", re.I)
CLAIMS = [
    (re.compile(r"\b(?:don'?t|do not|never) need to (?:know how to )?code\b", re.I), "NO CODE"),
    (re.compile(r"\bfor free\b", re.I), "FREE"),
    (re.compile(r"\b(?:don'?t|do not) need to be an? editor\b", re.I), "NO EDITOR"),
    (re.compile(r"\bin (\d+) (seconds|minutes)\b", re.I), None),
]
FOLLOW = re.compile(r"\b(drop me a follow|follow me|follow for more|hit (?:the )?follow|give me a follow)\b", re.I)
LIKE_THIS = re.compile(r"\b(?:something )?like this\b|\bthis video\b", re.I)
NUMBER = re.compile(r"\$?\d[\d,.]*\s*(%|k|x|million|billion)?")


def look_style(look_id: str) -> dict:
    try:
        from apply_look import load_look

        return load_look(look_id).get("style", {})
    except SkillError:
        return {}


def compute_sections(project: Path, recipe: dict, spec: list[str]) -> list[dict]:
    """"soft:cool aesthetic" switches to soft from the sentence containing the phrase
    until the next switch or the end of the following sentence."""
    lines = sentences(project, recipe)
    marks = []
    for item in spec:
        look, _, phrase = item.partition(":")
        phrase = phrase.strip().lower()
        for i, line in enumerate(lines):
            if phrase and phrase in line["text"].lower():
                marks.append((line["start"], i, look.strip()))
                break
    marks.sort()
    out = []
    for n, (start, i, look) in enumerate(marks):
        end = lines[min(i + 1, len(lines) - 1)]["end"]
        if n + 1 < len(marks):
            end = min(end, marks[n + 1][0])
        out.append({"start": round(start, 2), "end": round(end, 2), "look": look})
    return out


def overlaps(a: tuple[float, float], b: tuple[float, float], pad: float = 0.0) -> bool:
    return a[0] < b[1] + pad and b[0] < a[1] + pad


def beat(rule: str, start: float, end: float, **params) -> dict:
    return {"id": f"{rule}-{start:.1f}", "rule": rule, "start": round(start, 2), "end": round(end, 2), **params}


def word_time(words: list[dict], text_index: int, sentence_words: list[dict]) -> float:
    return sentence_words[min(text_index, len(sentence_words) - 1)]["start"] if sentence_words else 0.0


def plan(project: Path) -> tuple[list[dict], dict]:
    recipe = read_json(project / "recipe.json")
    words, _, _ = timeline_words(project, recipe)
    lines = sentences(project, recipe)
    duration = float(read_json(project / "segments.json", {}).get("duration", 0)) or (words[-1]["end"] if words else 0)
    manual_layouts = [(float(o["start"]), float(o["end"])) for o in recipe.get("layouts", []) if not o.get("auto")]
    manual_overlays = [(float(o["start"]), float(o["end"])) for o in recipe.get("overlays", []) if not o.get("auto")]
    skip = set(recipe.get("autoedit", {}).get("skip", []))
    beats: list[dict] = []

    def free(span: tuple[float, float], kinds: set[str] | None = None, pad: float = 0.2, share_overlays: bool = False) -> bool:
        blockers = manual_layouts + ([] if share_overlays else manual_overlays)
        if any(overlaps(span, m, pad) for m in blockers):
            return False
        return not any(overlaps(span, (b["start"], b["end"]), pad) for b in beats if kinds is None or b["rule"] in kinds)

    provided = [r for r in read_json(project / "assets.json", {"requests": []}).get("requests", []) if r.get("status") == "provided"]
    from instagram import local_reels

    has_reels = bool(local_reels(project))
    default_look = (recipe.get("lookPreset") or {}).get("id", "bold")

    def look_at(t: float) -> str:
        for sec in recipe.get("sections", []):
            if float(sec["start"]) <= t < float(sec["end"]):
                return sec["look"]
        return default_look

    def example_provided(line: dict) -> bool:
        return any(r["kind"] == "example" and overlaps((r["start"], r["end"]), (line["start"], line["end"])) for r in provided)

    def words_in(line: dict) -> list[dict]:
        return [w for w in words if line["start"] - 0.01 <= w["start"] <= line["end"] + 0.01]

    def at_phrase(line: dict, phrase_start: int) -> float:
        """Timeline time of the word at character offset phrase_start in the line text."""
        ws = words_in(line)
        pos = 0
        for w in ws:
            if pos >= phrase_start:
                return w["start"]
            pos += len(w["text"]) + 1
        return ws[-1]["start"] if ws else line["start"]

    # Layout beats first: they own the frame.
    for line in lines:
        text = line["text"]
        span = (line["start"], line["end"])
        follow = FOLLOW.search(text)
        if follow:
            t = at_phrase(line, follow.start())
            end = min(duration - 0.1, max(t + 3.2, line["end"]))
            if free((t, end)):
                beats.append(beat("follow", t, end))
                continue
        cta = CTA.search(text)
        if cta:
            t = at_phrase(line, cta.start())
            end = min(duration - 0.1, max(t + 3.5, line["end"]))
            if free((t, end)):
                beats.append(beat("cta", t, end, keyword=cta.group(2).upper()))
            continue
        recent_demo = any(b["rule"] == "workflow" and line["start"] - b["start"] < 20 for b in beats)
        if WORKFLOW.search(text) and line["end"] - line["start"] >= 2.0 and not recent_demo and free(span):
            end = min(duration - 0.1, max(line["start"] + 3.8, line["end"]))
            like = LIKE_THIS.search(text)
            if like and not example_provided(line):
                # "...and get something like this": the demo ends, and the video itself is
                # the example. It shrinks into a phone labelled "this video".
                t = at_phrase(line, like.start())
                if t - line["start"] >= 2.4:
                    beats.append(beat("workflow", line["start"], round(t - 0.05, 2)))
                    beats.append(beat("self", t, min(duration - 0.1, t + 1.7)))
                    continue
            beats.append(beat("workflow", line["start"], end))
            continue
        like = LIKE_THIS.search(text)
        demo_before = any(b["rule"] in {"workflow", "self"} and 0 <= line["start"] - b["end"] < 3 for b in beats)
        if like and demo_before and not example_provided(line) and not any(b["rule"] == "self" for b in beats):
            t = at_phrase(line, like.start())
            if free((t, t + 1.7)):
                beats.append(beat("self", t, min(duration - 0.1, t + 1.7)))
    # Products: hook depth word for the first product in the opening, logos for first mentions.
    seen: set[str] = set()
    last_logo = -10.0
    for line in lines:
        mentions = [(name, at_phrase(line, offset)) for name, offset in find_products(line["text"])]
        groups: list[list[tuple[str, float]]] = []
        for name, t in mentions:
            # Products named together ("Claude Code or Codex") appear together.
            if groups and t - groups[-1][-1][1] <= 1.5 and len(groups[-1]) < 2:
                groups[-1].append((name, t))
            else:
                groups.append([(name, t)])
        for group in groups:
            t = group[0][1]
            if t < 4.0 and not any(b["rule"] == "hook" for b in beats):
                if free((t, t + 1.6), {"workflow", "cta"}, share_overlays=True):
                    beats.append(beat("hook", t, t + 1.6, text=group[0][0].split()[0].upper()))
                    continue
            fresh = [name for name, _ in group if PRODUCTS[name][0] not in seen or len(group) > 1]
            if not fresh or t - last_logo < 2.5:
                continue
            end = max(t + 1.6, group[-1][1] + 1.2)
            if free((t, end)):
                beats.append(beat("logo", t, end, products=fresh))
                seen.update(PRODUCTS[name][0] for name in fresh)
                last_logo = t
    # Artifact: show the file being talked about.
    for line in lines:
        m = ARTIFACT.search(line["text"])
        if m and not WORKFLOW.search(line["text"]) and not CTA.search(line["text"]):
            t = max(line["start"], at_phrase(line, m.start()) - 1.0)
            following = [b["start"] for b in beats if b["start"] > t]
            end = min([t + 2.4] + [x - 0.15 for x in following])
            if end - t >= 1.2 and free((t, end), None, 0.05):
                beats.append(beat("artifact", t, end, noun=m.group(1).lower()))
                break
    # Claims as big text behind the speaker; numbers as stats.
    last_claim = -10.0
    for line in lines:
        for pattern, label in CLAIMS:
            m = pattern.search(line["text"])
            if not m or not label:
                continue
            t = at_phrase(line, m.start())
            if t - last_claim > 6 and free((t, t + 2.0)) and not any(b["rule"] == "hook" and abs(b["start"] - t) < 6 for b in beats):
                beats.append(beat("claim", t, t + 2.0, text=label))
                last_claim = t
        num = NUMBER.search(line["text"])
        if num and re.search(r"\d", num.group(0)) and free(span := (line["start"], min(line["end"], line["start"] + 3.0))):
            rest = " ".join(line["text"][num.end():].split()[:4])
            beats.append(beat("stat", span[0], span[1], value=num.group(0).strip(), label=rest))
    # Zooms keep a change every few seconds where nothing else is happening.
    def free_part(span: tuple[float, float]) -> tuple[float, float] | None:
        """Longest part of span not touched by any beat or manual item."""
        blocked = sorted(manual_layouts + manual_overlays + [(b["start"], b["end"]) for b in beats])
        parts, cursor = [], span[0]
        for lo, hi in blocked:
            if hi + 0.1 <= cursor or lo - 0.1 >= span[1]:
                continue
            if lo - 0.1 > cursor:
                parts.append((cursor, lo - 0.1))
            cursor = max(cursor, hi + 0.1)
        if cursor < span[1]:
            parts.append((cursor, span[1]))
        best = max(parts, key=lambda p: p[1] - p[0], default=None)
        return best if best and best[1] - best[0] >= 1.2 else None

    # Soft sections: the creator's reels orbit around them (their signature move).
    for sec in recipe.get("sections", []):
        if look_style(sec["look"]).get("signature") == "orbit" and has_reels:
            span = free_part((float(sec["start"]), min(float(sec["end"]), float(sec["start"]) + 4.0)))
            if span:
                beats.append(beat("orbit", span[0], span[1]))

    punch = True
    for line in lines:
        span = free_part((line["start"], line["end"]))
        if not span:
            continue
        style = look_style(look_at(span[0])).get("zoom", "punch")
        ws = [w for w in words_in(line) if span[0] <= w["start"] < span[1]]
        key = next((w for w in ws if re.sub(r"[^\w]", "", w["text"]).lower() in POWER_WORDS or re.search(r"\d", w["text"])), None)
        if style == "gentle":
            # Soft: slow push-ins only.
            if span[1] - span[0] >= 2.0:
                beats.append(beat("zoom", span[0], span[1], ease="smooth", to=1.06))
        elif style == "alternate":
            # Studio: wide and close alternate line by line, like a two-camera interview.
            if punch:
                beats.append(beat("zoom", span[0], span[1], ease="cut", to=1.32))
        elif punch:
            t = key["start"] if key else span[0] + (span[1] - span[0]) * 0.35
            beats.append(beat("zoom", t, span[1], ease="cut", to=1.17))
        elif span[1] - span[0] >= 2.5:
            beats.append(beat("zoom", span[0], span[1], ease="smooth", to=1.1))
        punch = not punch
    beats = [b for b in beats if b["id"] not in skip]
    beats.sort(key=lambda b: b["start"])
    return beats, {"duration": duration, "skipped": sorted(skip)}


def write_plan(project: Path, beats: list[dict], meta: dict) -> Path:
    labels = {
        "hook": "Hook: big word behind the speaker", "logo": "Logo tile beside the face", "workflow": "UI demo (split screen)",
        "artifact": "File as a floating code window", "cta": "Comment sheet with the keyword (split screen)",
        "claim": "Claim as big text behind the speaker", "stat": "Number graphic", "zoom": "Zoom",
        "self": "The video shrinks into a phone: 'this video' is the example",
        "follow": "Profile card: Follow gets tapped (split screen)", "orbit": "The creator's reels orbit around them",
    }
    lines = ["# Edit Plan", "", "Built from shared/references/editing-rules.md. Remove a beat with",
             "`autoedit.py <project> --skip <id>`.", "", "| ID | When | Beat | Detail |", "| --- | --- | --- | --- |"]
    for b in beats:
        detail = {k: v for k, v in b.items() if k not in {"id", "rule", "start", "end"}}
        lines.append(f"| {b['id']} | {b['start']:.1f}-{b['end']:.1f}s | {labels.get(b['rule'], b['rule'])} | {json.dumps(detail) if detail else ''} |")
    if meta["skipped"]:
        lines += ["", "Skipped by request: " + ", ".join(meta["skipped"])]
    out = project / "qa" / "edit-plan.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def motion(project: Path, *args: str) -> None:
    result = subprocess.run([sys.executable, str(SCRIPTS / "motion.py"), str(project), *args], text=True, capture_output=True)
    if result.returncode != 0:
        raise SkillError(result.stderr.strip() or result.stdout.strip())


def thumbs(project: Path, count: int = 4) -> list[str]:
    ffmpeg = find_exe("ffmpeg")
    duration = float(read_json(project / "segments.json", {}).get("duration", 10))
    out = []
    for i in range(count):
        path = project / "work" / "thumbs" / f"thumb{i + 1}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        run_cmd([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{duration * (i + 0.5) / count:.2f}", "-i",
                 str(project / "work" / "aroll.mp4"), "-frames:v", "1", "-vf", "scale=360:-2", str(path)])
        out.append(str(path))
    return out


def skill_excerpt() -> str:
    root = skill_root()
    source = next((c for c in [root / "SKILL.md", root / "skills" / "video-edit" / "SKILL.md", root / "claude" / "SKILL.md"] if c.exists()), None)
    if source is None:
        return "---\nname: video-edit\n---\n# Video Edit\nTurn raw clips into a finished video."
    text = source.read_text(encoding="utf-8").splitlines()
    skip = ("argument-hint", "$ARGUMENTS", "User request", "`SK`", "CLAUDE_PLUGIN_ROOT")
    keep = [line[:46] for line in text if line.strip() and not any(k in line for k in skip)][:26]
    keep = ["description: Turn raw clips into a finished video." if l.startswith("description:") else l for l in keep]
    return "\n".join(keep)


def workers() -> int:
    """Motion renders run in parallel; each starts headless Chrome, so size to RAM."""
    try:
        ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError, AttributeError):
        ram = 8
    return 3 if ram >= 15 else 2


def jobs_for(project: Path, b: dict, ctx: dict) -> list[dict]:
    """Motion renders (and how to place each) for one beat."""
    width, height = ctx["width"], ctx["height"]
    dur = round(b["end"] - b["start"], 2)
    settings = ctx["settings"]

    def job(template: str, name: str, duration: float, args: list[str], **place) -> dict:
        return {"beat": b["id"], "template": template, "name": name, "duration": round(duration, 2), "args": args,
                "place": {"kind": "overlay", "start": b["start"], "x": 0, "y": 0, "behind": False, **place}}

    if b["rule"] in {"hook", "claim"}:
        return [job("big-text", b["id"], dur, ["--var", f"text={b['text']}", "--var", "centerY=29"], behind=True)]
    if b["rule"] == "logo":
        names = b.get("products") or [b["product"]]
        slots = pop_slots(project, width, height, [0.8] * len(names), b["start"], b["end"])
        out = []
        for n, (name, (x, y, card_w, tilt)) in enumerate(zip(names, slots)):
            logo = fetch(project, name)
            tile_w = min(card_w, width * 0.26)
            canvas_w = int(tile_w / 0.62) // 2 * 2
            canvas_h = int(canvas_w * 1.25) // 2 * 2
            pad = (canvas_w - tile_w) / 2
            margin = width * 0.03
            ox = int(min(max(x + card_w / 2 - canvas_w / 2, margin - pad), width - margin - tile_w - pad))
            label = {"chatgpt": "ChatGPT", "openai": "OpenAI"}.get(name, name.title())
            offset = n * 0.35  # the second logo lands a beat after the first
            out.append(job("logo-pop", f"{b['id']}-{n + 1}", dur - offset,
                           ["--asset", str(logo), "--size", f"{canvas_w}x{canvas_h}", "--var", f"name={label}", "--var", f"tilt={tilt}"],
                           start=round(b["start"] + offset, 2), x=ox, y=int(y + 40)))
        return out
    if b["rule"] == "workflow":
        extra = []
        try:
            extra = ["--asset", str(fetch(project, ctx["app_name"]))]
        except SkillError:
            pass
        return [job("app-demo", b["id"], dur, ["--files", ",".join(thumbs(project)), *extra, "--var", f"appName={ctx['app_name']}",
                                               "--var", f"user={settings.get('user', 'You')}", "--size", f"{width}x{height // 2}"], kind="split")]
    if b["rule"] == "self":
        return [job("phone-frame", b["id"], dur, ["--var", "label=this video ↓"], kind="phone")]
    if b["rule"] == "cta":
        return [job("social-cta", b["id"], dur, ["--var", f"keyword={b['keyword']}", "--var", f"handle={settings.get('handle') or 'yourhandle'}",
                                                 "--size", f"{width}x{height // 2}"], kind="split")]
    if b["rule"] == "follow":
        info = read_json(project / "work" / "instagram" / "profile.json", {})
        handle = info.get("handle") or settings.get("handle") or "yourhandle"
        args = ["--var", f"handle={handle}", "--var", f"name={info.get('name') or settings.get('user') or handle}", "--size", f"{width}x{height // 2}"]
        if info.get("followers"):
            args += ["--var", f"followers={info['followers']}", "--var", f"posts={info['posts']}", "--var", f"following={info['following']}"]
        else:
            args += ["--var", "followers=0"]  # unknown counts are hidden, never invented
        if info.get("bio"):
            args += ["--var", f"bio={info['bio']}"]
        if info.get("avatar"):
            args += ["--asset", info["avatar"]]
        reels = ctx["reels"][:9]
        if reels:
            args += ["--files", ",".join(reels)]
        return [job("social-profile", b["id"], dur, args, kind="split")]
    if b["rule"] == "orbit":
        from vision import face_or_default

        f = face_or_default(project, b["start"], b["end"])
        # Tilted orbit: the back arc passes behind the head, the front arc in front of
        # the chest, so a card never crosses the face.
        card_h = 0.24 * width * 16 / 9 / height
        back_y = f["y"] + f["h"] * 0.4
        front_y = f["y"] + f["h"] + card_h * 0.55 + 0.01
        cx, cy, ry = f["x"] + f["w"] / 2, (back_y + front_y) / 2, (front_y - back_y) / 2
        common = ["--files", ",".join(ctx["reels"][:5]), "--var", f"cx={cx:.3f}", "--var", f"cy={cy:.3f}", "--var", f"ry={ry:.3f}"]
        return [job("orbit", f"{b['id']}-back", dur, [*common, "--var", "layer=back"], behind=True),
                job("orbit", f"{b['id']}-front", dur, [*common, "--var", "layer=front"])]
    if b["rule"] == "artifact":
        from vision import face_or_default

        f = face_or_default(project, b["start"], b["end"])
        body = 330
        top = (f["y"] + f["h"]) * height + 30
        centre = (top + (body + 70) / 2) / height * 100
        return [job("code-window", b["id"], dur, ["--var", "title=SKILL.md" if b["noun"] == "skill" else f"title={b['noun']}",
                                                  "--var", f"text={skill_excerpt()}", "--var", f"bodyHeight={body}", "--var", f"centerY={centre:.1f}"],
                    topWindow=True)]
    if b["rule"] == "stat":
        return [job("stat", b["id"], dur, ["--var", f"value={b['value']}", "--var", f"label={b['label']}"])]
    return []


def render_job(project: Path, j: dict, chrome_workers: int) -> tuple[dict, str | None]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "motion.py"), str(project), j["template"], "--name", j["name"], "--duration", str(j["duration"]),
         "--workers", str(chrome_workers), *j["args"]],
        text=True, capture_output=True,
    )
    if result.returncode != 0:
        return j, (result.stderr.strip() or result.stdout.strip()).splitlines()[-1][:200]
    return j, None


def place(project: Path, j: dict) -> None:
    from motion import TEMPLATES, add_cues

    recipe = read_json(project / "recipe.json")
    out = str(project / "work" / "motion" / f"{j['name']}.mov")
    pl = j["place"]
    start, end = float(pl["start"]), round(float(pl["start"]) + j["duration"], 3)
    tag = {"auto": True, "beat": j["beat"], "motion": j["name"]}
    if pl["kind"] == "overlay":
        recipe.setdefault("overlays", []).append({"file": out, "kind": "video", "start": start, "end": end, "x": pl["x"], "y": pl["y"],
                                                  "width": None, "fade": 0, "label": j["template"], "behind": pl["behind"], **tag})
    else:
        recipe.setdefault("layouts", []).append({"type": pl["kind"], "file": out, "start": start, "end": end, "mediaSide": "top",
                                                 "label": j["template"], **tag})
    if pl.get("topWindow"):
        recipe["captions"].setdefault("topWindows", []).append({"start": start, "end": end, **tag})
    write_json(project / "recipe.json", recipe)
    add_cues(project, TEMPLATES / j["template"], start, j["duration"], j["name"])


def build(project: Path, beats: list[dict], only: set[str] | None, rebuild: set[str] | None = None) -> None:
    recipe = read_json(project / "recipe.json")
    if rebuild:
        # Redo only the named beats; everything else stays as built.
        mine = lambda item: item.get("beat") in rebuild
        recipe["overlays"] = [o for o in recipe.get("overlays", []) if not mine(o)]
        recipe["layouts"] = [o for o in recipe.get("layouts", []) if not mine(o)]
        recipe["sfx"] = [c for c in recipe.get("sfx", []) if not any(str(c.get("source", "")).startswith(b) for b in rebuild)]
        recipe["zooms"] = [z for z in recipe.get("zooms", []) if not mine(z)]
        recipe["captions"]["topWindows"] = [w for w in recipe["captions"].get("topWindows", []) if not mine(w)]
        beats = [b for b in beats if b["id"] in rebuild]
        only = (only or set()) | {"zooms", "motion"}
    else:
        recipe["overlays"] = [o for o in recipe.get("overlays", []) if not o.get("auto")]
        recipe["layouts"] = [o for o in recipe.get("layouts", []) if not o.get("auto")]
        recipe["sfx"] = [c for c in recipe.get("sfx", []) if c.get("manual")]
        recipe["zooms"] = [z for z in recipe.get("zooms", []) if not z.get("auto")]
        recipe["captions"]["topWindows"] = [w for w in recipe["captions"].get("topWindows", []) if not w.get("auto")]
    write_json(project / "recipe.json", recipe)
    width, height = int(recipe["output"]["width"]), int(recipe["output"]["height"])
    product_names = [n for n, _ in find_products(" ".join(s["text"] for s in sentences(project, recipe)))]
    display = {"claude code": "Claude Code", "codex": "Codex", "chatgpt": "ChatGPT", "cursor": "Cursor", "claude": "Claude"}
    from instagram import local_reels

    ctx = {
        "width": width, "height": height, "settings": recipe.get("autoedit", {}),
        "app_name": next((display[n] for n in ["claude code", "codex", "claude", "chatgpt", "cursor"] if n in product_names), "Claude Code"),
        "reels": local_reels(project),
    }
    wanted = (lambda kind: only is None or kind in only)

    if wanted("zooms"):
        from vision import face_or_default

        face = face_or_default(project)
        recipe = read_json(project / "recipe.json")
        for b in beats:
            if b["rule"] == "zoom":
                recipe.setdefault("zooms", []).append({"auto": True, "beat": b["id"], "start": b["start"], "end": b["end"], "ease": b["ease"],
                                                       "to": b["to"], "from": b.get("from", 1.0),
                                                       "cx": round(face["x"] + face["w"] / 2, 3), "cy": round(face["y"] + face["h"] / 2, 3)})
        write_json(project / "recipe.json", recipe)

    if wanted("motion"):
        jobs = []
        for b in beats:
            if b["rule"] == "zoom":
                continue
            try:
                jobs.extend(jobs_for(project, b, ctx))
            except SkillError as exc:
                print(f"  skipped {b['id']}: {str(exc).splitlines()[-1][:160]}")
        if jobs:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            parallel = workers()
            print(f"Rendering {len(jobs)} motion graphic(s), {parallel} at a time...")
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                futures = [pool.submit(render_job, project, j, 2) for j in jobs]
                for future in as_completed(futures):
                    j, error = future.result()
                    if error:
                        print(f"  skipped {j['name']}: {error}")
                        continue
                    place(project, j)  # recipe writes stay on this thread
                    print(f"  built {j['name']}")

    if wanted("sound"):
        # A soft pop on every key-word card, never within half a second of another cue.
        sys.argv = ["captions.py", str(project)]
        from captions import captions_from_recipe

        recipe = read_json(project / "recipe.json")
        cues = recipe.setdefault("sfx", [])
        for cap in captions_from_recipe(project):
            if cap.get("emphasis") and all(abs(c["at"] - cap["start"]) > 0.5 for c in cues):
                cues.append({"at": round(cap["start"], 3), "kind": "pop", "gain": -18})
        cues.sort(key=lambda c: c["at"])
        thinned = []
        for c in cues:
            if c.get("manual") or not thinned or c["at"] - thinned[-1]["at"] >= 0.12:
                thinned.append(c)
        recipe["sfx"] = thinned
        write_json(project / "recipe.json", recipe)
    if wanted("grade") and not read_json(project / "recipe.json").get("grade"):
        subprocess.run([sys.executable, str(SCRIPTS / "grade.py"), str(project)], check=False, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the default editing rules to a project.")
    parser.add_argument("project")
    parser.add_argument("--plan", action="store_true", help="Only write qa/edit-plan.md.")
    parser.add_argument("--skip", action="append", default=[], help="Beat id to drop (kept for future runs).")
    parser.add_argument("--only", help="Comma list of passes: zooms,motion,sound,grade.")
    parser.add_argument("--rebuild", help="Comma list of beat ids to rebuild; the rest stays as built.")
    parser.add_argument("--look", default="creator-pro", help="Look to apply if the project has none (default creator-pro).")
    parser.add_argument("--user", help="Name shown in UI demos (saved).")
    parser.add_argument("--handle", help="Creator handle for the comment sheet, no @ (saved).")
    parser.add_argument("--section", action="append", default=[], help='Switch look for a section: "soft:the cool aesthetic" (saved).')
    args = parser.parse_args()
    try:
        project = ensure_project(Path(args.project))
        recipe = read_json(project / "recipe.json")
        settings = recipe.setdefault("autoedit", {})
        if args.skip:
            settings["skip"] = sorted(set(settings.get("skip", [])) | set(args.skip))
        if args.user:
            settings["user"] = args.user
        if args.handle:
            settings["handle"] = args.handle.lstrip("@")
        if args.section:
            settings["sections"] = args.section
        recipe["sections"] = compute_sections(project, recipe, settings.get("sections", []))
        write_json(project / "recipe.json", recipe)
        if not recipe.get("lookPreset") and args.look:
            subprocess.run([sys.executable, str(SCRIPTS / "apply_look.py"), str(project), args.look], check=True, capture_output=True)
        beats, meta = plan(project)
        out = write_plan(project, beats, meta)
        print(f"{len(beats)} beat(s): {', '.join(sorted({b['rule'] for b in beats}))}. Plan: {out}")
        if args.plan:
            return 0
        build(project, beats, set(args.only.split(",")) if args.only else None, set(args.rebuild.split(",")) if args.rebuild else None)
        print("Done. Run render.py --review, then look at the frames.")
        return 0
    except SkillError as exc:
        fail(str(exc))
    except subprocess.CalledProcessError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
