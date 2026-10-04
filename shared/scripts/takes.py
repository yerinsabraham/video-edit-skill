#!/usr/bin/env python3
"""Pick the best take of every line across raw clips and build the EDL.

    takes.py <project>                    # writes takes.json, qa/takes.md, edl.json
    takes.py <project> --use L3=m2        # force a take for a line, then rebuild
    takes.py <project> --drop L5          # leave a line out

Creators repeat a line until it lands, across one clip or several, and the
clips rarely arrive in order. This splits every clip into clauses, groups the
clauses that say the same thing, keeps the lines in script order (where each
line first appears), and picks one take per line: complete, fluent (no stumbles
or fillers), and the later take on a tie, because a retake is usually the fix.
Consecutive picks from the same clip are joined so the edit cuts only where it
must. The table in qa/takes.md shows every choice.
"""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, is_filler, read_json, snapshot_project, write_json

CLAUSE_END = re.compile(r"[.!?,;:…][\"'”’)]*$")
SAME_LINE = 0.62      # similarity to count as another take of a line
MIN_WORDS = 3
HANDLE = 0.08
MAX_PAUSE = 0.5        # gap that becomes a cut between lines
INNER_PAUSE = 0.7      # a breath inside a phrase stays unless it is longer than this


def norm(text: str) -> str:
    return re.sub(r"[^\w']+", "", text.lower())


def clauses(words: list[dict]) -> list[list[dict]]:
    """Split one clip's words at punctuation; tiny fragments join a neighbour."""
    out: list[list[dict]] = []
    current: list[dict] = []
    for w in words:
        current.append(w)
        if CLAUSE_END.search(w["text"]):
            out.append(current)
            current = []
    if current:
        out.append(current)
    merged: list[list[dict]] = []
    for c in out:
        if merged and (len(c) < MIN_WORDS or len(merged[-1]) < MIN_WORDS):
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    return merged


def similarity(a: list[str], b: list[str]) -> float:
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def fluency(unit: dict) -> float:
    """Higher is cleaner: penalise fillers, stutters (a word repeated back to back),
    long internal pauses, and clauses cut off before their end."""
    toks = unit["tokens"]
    score = 0.0
    score -= 0.6 * sum(1 for w in unit["words"] if is_filler(w["text"]))
    score -= 0.8 * sum(1 for a, b in zip(toks, toks[1:]) if a == b)
    gaps = [b["start"] - a["end"] for a, b in zip(unit["words"], unit["words"][1:])]
    score -= 0.5 * sum(1 for g in gaps if g > 0.9)
    if not CLAUSE_END.search(unit["words"][-1]["text"]):
        score -= 0.3
    return score


CTA = re.compile(r"\b(comment|dm me|message me|link in (?:my )?bio|follow (?:me|for)|drop me a follow|subscribe|send it to you)\b", re.I)
SENTENCE_END = re.compile(r"[.!?…][\"'”’)]*$")


def build(project: Path, forced: dict[str, str], dropped: set[str], clip_order: list[str] | None = None) -> dict:
    transcript = read_json(project / "transcript.json")
    media = read_json(project / "media.json")["sources"]
    # Clips are read in recording order unless the user gives an order.
    ids = [m["id"] for m in media]
    preferred = [c for c in (clip_order or []) if c in ids]
    ranked_ids = preferred + [i for i in ids if i not in preferred]
    order = {m: i for i, m in enumerate(ranked_ids)}
    by_media: dict[str, list[dict]] = {}
    for w in transcript.get("words", []):
        by_media.setdefault(w["mediaId"], []).append(w)

    units: list[dict] = []
    for media_id in sorted(by_media, key=lambda m: order.get(m, 99)):
        ws = sorted(by_media[media_id], key=lambda w: w["start"])
        for c in clauses(ws):
            toks = [norm(w["text"]) for w in c if norm(w["text"]) and not is_filler(w["text"])]
            if not toks:
                continue
            units.append({"media": media_id, "start": c[0]["start"], "end": c[-1]["end"], "words": c,
                          "tokens": toks, "text": " ".join(w["text"] for w in c), "seq": len(units),
                          "recorded": (ids.index(media_id), c[0]["start"])})

    groups: list[dict] = []
    for u in units:
        best, best_sim = None, 0.0
        for g in groups:
            if any(t["media"] == u["media"] and t["end"] > u["start"] - 0.01 and t is not u for t in g["takes"]) and \
                    g["takes"][-1]["media"] == u["media"] and g["takes"][-1]["seq"] == u["seq"] - 1:
                continue  # the next clause of the same take is a new line, not a retake
            sim = max(similarity(u["tokens"], t["tokens"]) for t in g["takes"])
            if sim > best_sim:
                best, best_sim = g, sim
        if best is not None and best_sim >= SAME_LINE:
            best["takes"].append(u)
        else:
            groups.append({"id": f"L{len(groups) + 1}", "takes": [u]})

    lines = []
    prev_pick = None
    for g in groups:
        takes = g["takes"]
        longest = max(len(t["tokens"]) for t in takes)

        def score(t: dict) -> float:
            s = fluency(t) - 1.2 * (1 - len(t["tokens"]) / longest)
            rank = sorted(t2["recorded"] for t2 in takes).index(t["recorded"])
            s += 0.15 * rank / max(1, len(takes) - 1)  # the take recorded last wins a tie, whatever the play order
            if prev_pick and prev_pick["media"] == t["media"] and 0 <= t["start"] - prev_pick["end"] < 2.5:
                s += 0.35  # keep running in the same take when it is just as good
            return s

        ranked = sorted(takes, key=score, reverse=True)
        pick = ranked[0]
        reason = "only take" if len(takes) == 1 else ("later retake" if pick["recorded"] == max(t["recorded"] for t in takes) else "cleanest take")
        if g["id"] in forced:
            chosen = [t for t in takes if t["media"] == forced[g["id"]]]
            if chosen:
                pick, reason = chosen[0], "chosen by you"
        if g["id"] in dropped:
            reason = "dropped by you"
        lines.append({"id": g["id"], "text": pick["text"], "pick": pick, "takes": takes, "reason": reason, "dropped": g["id"] in dropped})
        if g["id"] not in dropped:
            prev_pick = pick
    return {"lines": lines, "media": {m["id"]: m for m in media}}


def arrange(lines: list[dict], line_order: list[str], moves: list[str], cta_last: bool) -> list[dict]:
    """Final line order. A call to action ("comment X", "follow me") goes last,
    with the rest of its sentence, because that is where it belongs even when it
    was recorded first. An explicit order or moves from the user win."""
    by_id = {l["id"]: l for l in lines}
    if line_order:
        first = [by_id[i] for i in line_order if i in by_id]
        lines = first + [l for l in lines if l["id"] not in line_order]
    elif cta_last:
        groups: list[list[dict]] = []
        for l in lines:
            if groups and not SENTENCE_END.search(groups[-1][-1]["text"]):
                groups[-1].append(l)  # still the same sentence
            else:
                groups.append([l])
        cta = [g for g in groups if any(CTA.search(l["text"]) for l in g)]
        if cta and groups[-len(cta):] != cta:
            for g in cta:
                for l in g:
                    l["reason"] += "; moved to the end (call to action)"
            lines = [l for g in groups if g not in cta for l in g] + [l for g in cta for l in g]
    for move in moves:
        line_id, _, where = move.partition("=")
        line = next((l for l in lines if l["id"] == line_id), None)
        if not line:
            continue
        lines = [l for l in lines if l is not line]
        if where == "start":
            lines.insert(0, line)
        elif where.startswith(("after:", "before:")):
            kind, _, anchor = where.partition(":")
            idx = next((i for i, l in enumerate(lines) if l["id"] == anchor.upper()), len(lines) - 1)
            lines.insert(idx + 1 if kind == "after" else idx, line)
        else:
            lines.append(line)
        line["reason"] += f"; moved by you ({where})"
    return lines


def write_outputs(project: Path, result: dict) -> int:
    media = result["media"]
    segments: list[dict] = []
    for line in result["lines"]:
        if line["dropped"]:
            continue
        p = line["pick"]
        src = media[p["media"]]
        # A long pause inside a take is cut too ("Everyone ... is talking").
        runs: list[list[dict]] = [[p["words"][0]]]
        for a, b in zip(p["words"], p["words"][1:]):
            if b["start"] - a["end"] > INNER_PAUSE:
                runs.append([])
            runs[-1].append(b)
        for run in runs:
            start = max(0.0, run[0]["start"] - HANDLE)
            end = min(float(src["duration"]), run[-1]["end"] + HANDLE)
            text = " ".join(w["text"] for w in run)
            prev = segments[-1] if segments else None
            if prev and prev["mediaId"] == p["media"] and start - prev["out"] <= MAX_PAUSE and end > prev["out"]:
                prev["out"] = round(end, 3)
                prev["line"] += " " + text
                continue
            segments.append({"id": "", "mediaId": p["media"], "clip": src["path"], "in": round(start, 3), "out": round(end, 3),
                             "line": text, "look": "clean-creator", "zoom": 1.0, "cx": 0.5, "cy": 0.5})
    for i, s in enumerate(segments, 1):
        s["id"] = f"s{i}"
    write_json(project / "edl.json", {"segments": segments})

    write_json(project / "takes.json", {"lines": [
        {"id": l["id"], "text": l["text"], "reason": l["reason"], "dropped": l["dropped"],
         "pick": {"media": l["pick"]["media"], "start": round(l["pick"]["start"], 2), "end": round(l["pick"]["end"], 2)},
         "takes": [{"media": t["media"], "start": round(t["start"], 2), "text": t["text"]} for t in l["takes"]]}
        for l in result["lines"]]})
    rows = ["# Takes", "", "One row per line, in the order the video plays. Change a pick with `takes.py <project> --use L3=m2`;",
            "leave a line out with `--drop L5`; move one with `--move L7=end` (or start, after:L3, before:L3);",
            "set the clip order with `--clips m2,m1,m3`.", "", "| # | Line | Picked | Takes | Why | Text |", "| --- | --- | --- | --- | --- | --- |"]
    for n, l in enumerate(result["lines"], 1):
        others = ", ".join(f"{t['media']}@{t['start']:.1f}s" for t in l["takes"])
        picked = "dropped" if l["dropped"] else f"{l['pick']['media']}@{l['pick']['start']:.1f}s"
        rows.append(f"| {n} | {l['id']} | {picked} | {others} | {l['reason']} | {l['text'][:80]} |")
    (project / "qa").mkdir(exist_ok=True)
    (project / "qa" / "takes.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return len(segments)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pick the best take of every line and build edl.json.")
    parser.add_argument("project")
    parser.add_argument("--use", action="append", default=[], help="Force a take: L3=m2 (saved).")
    parser.add_argument("--drop", action="append", default=[], help="Leave a line out: L5 (saved).")
    parser.add_argument("--move", action="append", default=[], help="Move a line: L7=end, L7=start, L7=after:L3, L7=before:L3 (saved).")
    parser.add_argument("--order", help="Line order, e.g. L1,L2,L5,L3 (lines not listed follow in their current order; saved).")
    parser.add_argument("--clips", help="Clip order for reading the script, e.g. m2,m1,m3 (saved). Default: recording time.")
    parser.add_argument("--no-cta-last", action="store_true", help="Do not move calls to action to the end (saved).")
    parser.add_argument("--reset-order", action="store_true", help="Forget saved order, moves, and clip order.")
    args = parser.parse_args()
    try:
        project = ensure_project(Path(args.project))
        settings = read_json(project / "takes-settings.json", {"use": {}, "drop": []})
        for item in args.use:
            line, _, media_id = item.partition("=")
            settings["use"][line.upper()] = media_id
        settings["drop"] = sorted(set(settings["drop"]) | {d.upper() for d in args.drop})
        if args.reset_order:
            for key in ["moves", "order", "clips", "ctaLast"]:
                settings.pop(key, None)
        settings.setdefault("moves", [])
        settings["moves"] += [m.upper().replace("=END", "=end").replace("=START", "=start").replace("=AFTER:", "=after:").replace("=BEFORE:", "=before:") for m in args.move]
        if args.order:
            settings["order"] = [x.strip().upper() for x in args.order.split(",") if x.strip()]
        if args.clips:
            settings["clips"] = [x.strip() for x in args.clips.split(",") if x.strip()]
        if args.no_cta_last:
            settings["ctaLast"] = False
        write_json(project / "takes-settings.json", settings)
        if (project / "edl.json").exists():
            snapshot_project(project, "before-takes", "before take selection")
        result = build(project, settings["use"], set(settings["drop"]), settings.get("clips"))
        result["lines"] = arrange(result["lines"], settings.get("order", []), settings["moves"], settings.get("ctaLast", True))
        count = write_outputs(project, result)
        retakes = sum(1 for l in result["lines"] if len(l["takes"]) > 1)
        print(f"{len(result['lines'])} line(s), {retakes} with retakes; edit has {count} segment(s). See qa/takes.md")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
