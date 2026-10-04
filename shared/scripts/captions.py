#!/usr/bin/env python3
"""Generate sidecar captions from recipe and transcript.

Two modes, from production-playbook.md:

- short: 2-4 uppercase words per card, cut on real pauses, word timings kept
  for kinetic (word-lit) burn-in.
- long: sentence cues wrapped to two balanced lines, for lessons and talks.

Times are on the edit timeline, so anything prepended (an intro card) shifts
every caption automatically.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, write_json, write_srt, write_vtt


SHORT = {"maxWords": 4, "maxChars": 20, "pauseGap": 0.32, "minHold": 0.34, "emphasisHold": 0.6}
LONG = {"minChars": 34, "flushChars": 80, "maxSeconds": 5.0, "mergeSeconds": 1.2, "mergeChars": 12, "splitChars": 84, "lineChars": 42}
LONG_MODE_AFTER = 300.0
SENTENCE_END = re.compile(r"[.!?…][\"'”’)]*$")


POWER_WORDS = {
    "free", "secret", "crazy", "never", "always", "best", "worst", "mistake", "stop", "money",
    "million", "billion", "fast", "faster", "easy", "simple", "instantly", "everyone", "nobody",
    "exactly", "huge", "insane", "wrong", "truth", "results", "proof", "why", "how",
}
EMPHASIS_SPACING = 2.5
REPEAT_SPACING = 8.0


def mark_emphasis(words: list[dict], terms: list[str], auto: bool = True) -> list[tuple[int, int]]:
    """Return (start, end) word spans that get their own big card.

    Explicit terms (chosen by the agent from the transcript) win; then numbers,
    then strong words, then product names. Spans are kept at least
    EMPHASIS_SPACING apart so emphasis stays special."""
    bare = [re.sub(r"[^\w$%']+", "", w["text"]).lower() for w in words]
    phrases = [t.lower().split() for t in terms if t.strip()]
    candidates: list[tuple[int, int, int]] = []  # (priority, start, end)
    for i in range(len(words)):
        for phrase in phrases:
            if bare[i : i + len(phrase)] == phrase:
                candidates.append((0, i, i + len(phrase)))
        if not auto:
            continue
        text = words[i]["text"]
        after_sentence = i == 0 or SENTENCE_END.search(words[i - 1]["text"])
        if re.search(r"\d", text) or "$" in text or "%" in text:
            candidates.append((1, i, i + 1))
        elif bare[i] in POWER_WORDS:
            candidates.append((2, i, i + 1))
        elif text[:1].isupper() and not after_sentence and len(bare[i]) > 2 and not bare[i].startswith("i'"):
            candidates.append((3, i, i + 1))
    chosen: list[tuple[int, int]] = []
    for _, a, b in sorted(candidates):
        t = float(words[a]["start"])
        if any(not (b <= x or a >= y) for x, y in chosen):
            continue
        if any(abs(t - float(words[x]["start"])) < EMPHASIS_SPACING for x, _ in chosen):
            continue
        if any(bare[x:y] == bare[a:b] and abs(t - float(words[x]["start"])) < REPEAT_SPACING for x, y in chosen):
            continue
        chosen.append((a, b))
    return sorted(chosen)


def timeline_words(project: Path, recipe: dict) -> tuple[list[dict], list[dict], list[tuple[float, float]]]:
    """Map transcript words and real pauses into timeline time."""
    transcript = read_json(project / "transcript.json", {"words": []})
    words = transcript.get("words", [])
    out: list[dict] = []
    fallback: list[dict] = []
    pauses: list[tuple[float, float]] = []
    source_silences = transcript.get("silences", {})
    cursor = 0.0
    for segment in recipe.get("segments", []):
        start = float(segment.get("in", 0))
        end = float(segment.get("out", 0))
        if segment.get("type", "video") == "video":
            seg_words = [
                w
                for w in words
                if w.get("mediaId") == segment.get("mediaId") and start <= float(w.get("start", 0)) < end
            ]
            for w in seg_words:
                out.append(
                    {
                        "start": round(cursor + float(w["start"]) - start, 3),
                        "end": round(cursor + min(float(w["end"]), end) - start, 3),
                        "text": str(w["text"]).strip(),
                    }
                )
            for lo, hi in source_silences.get(segment.get("mediaId"), []):
                lo, hi = max(lo, start), min(hi, end)
                if hi - lo > 0.15:
                    pauses.append((round(cursor + lo - start, 3), round(cursor + hi - start, 3)))
            if not seg_words and segment.get("line"):
                fallback.append({"start": cursor, "end": cursor + (end - start), "text": segment["line"][:90]})
        cursor += end - start
    return out, fallback, pauses


def tidy(text: str) -> str:
    # Tighten space before punctuation only where it ends something, so ".gitignore" keeps its dot.
    text = re.sub(r"\s+([,.!?;:])(?=\s|$)", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def short_cards(words: list[dict], pauses: list[tuple[float, float]] | None = None, emphasis: list[tuple[int, int]] | None = None) -> list[dict]:
    cards: list[dict] = []
    current: list[dict] = []
    starts = {a: b for a, b in emphasis or []}
    skip_until = -1

    def flush(emph: bool = False) -> None:
        if current:
            cards.append({"start": current[0]["start"], "end": current[-1]["end"], "words": list(current), "emphasis": emph})
            current.clear()

    for index, word in enumerate(words):
        if index < skip_until:
            continue
        if index in starts:
            # A key word gets a card of its own.
            flush()
            current.extend(words[index : starts[index]])
            flush(emph=True)
            skip_until = starts[index]
            continue
        if current:
            text = " ".join(w["text"] for w in current + [word]).upper()
            if (
                word["start"] - current[-1]["end"] > SHORT["pauseGap"]
                or len(current) >= SHORT["maxWords"]
                or len(text) > SHORT["maxChars"]
                or SENTENCE_END.search(current[-1]["text"])
                or any(current[-1]["start"] < (lo + hi) / 2 < word["end"] for lo, hi in pauses or [])
            ):
                flush()
        current.append(word)
    flush()

    # Hold every card long enough to read; bridge short gaps so cards do not flicker.
    for i, card in enumerate(cards):
        nxt = cards[i + 1]["start"] if i + 1 < len(cards) else None
        if nxt is not None and nxt - card["end"] <= SHORT["pauseGap"]:
            card["end"] = nxt
        if card["end"] - card["start"] < SHORT["minHold"]:
            card["end"] = card["start"] + SHORT["minHold"] if nxt is None else min(nxt, card["start"] + SHORT["minHold"])
    merged: list[dict] = []
    for card in cards:
        too_short = card["end"] - card["start"] < SHORT["minHold"] - 1e-6
        fits = merged and len(" ".join(w["text"] for w in merged[-1]["words"] + card["words"])) <= SHORT["maxChars"]
        plain = merged and not card["emphasis"] and not merged[-1]["emphasis"]
        if merged and too_short and fits and plain:
            merged[-1]["end"] = card["end"]
            merged[-1]["words"].extend(card["words"])
        else:
            merged.append(card)
    for card in merged:
        card["text"] = tidy(" ".join(w["text"] for w in card["words"]))
        if card["emphasis"]:
            card["text"] = card["text"].rstrip(".,!?;:")
            # Key words linger above the running captions, which carry on underneath.
            card["end"] = max(card["end"], card["start"] + SHORT["emphasisHold"])
    return merged


def wrap_two_lines(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    words = text.split()
    best, best_score = text, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = max(len(a), len(b))
        if best_score is None or score < best_score:
            best, best_score = f"{a}\n{b}", score
    return best


def long_cues(words: list[dict]) -> list[dict]:
    cues: list[dict] = []
    current: list[dict] = []

    def text_of(items: list[dict]) -> str:
        return tidy(" ".join(w["text"] for w in items))

    def flush() -> None:
        if current:
            cues.append({"start": current[0]["start"], "end": current[-1]["end"], "words": list(current)})
            current.clear()

    for word in words:
        if current and word["start"] - current[-1]["end"] > 1.5:
            flush()
        current.append(word)
        chars = len(text_of(current))
        duration = current[-1]["end"] - current[0]["start"]
        if (SENTENCE_END.search(word["text"]) and chars >= LONG["minChars"]) or chars >= LONG["flushChars"] or duration >= LONG["maxSeconds"]:
            flush()
    flush()

    merged: list[dict] = []
    for cue in cues:
        short = cue["end"] - cue["start"] < LONG["mergeSeconds"] or len(text_of(cue["words"])) < LONG["mergeChars"]
        if merged and short and len(text_of(merged[-1]["words"] + cue["words"])) <= LONG["splitChars"] and cue["start"] - merged[-1]["end"] < 1.0:
            merged[-1]["end"] = cue["end"]
            merged[-1]["words"].extend(cue["words"])
        else:
            merged.append(cue)

    final: list[dict] = []
    for cue in merged:
        pending = cue["words"]
        while len(text_of(pending)) > LONG["splitChars"]:
            # Split at the word boundary nearest the middle, keeping real word timings.
            half = len(text_of(pending)) / 2
            run, cut = 0, 1
            for i, w in enumerate(pending[:-1]):
                run += len(w["text"]) + 1
                if run >= half:
                    cut = i + 1
                    break
            final.append({"start": pending[0]["start"], "end": pending[cut - 1]["end"], "words": pending[:cut]})
            pending = pending[cut:]
        final.append({"start": pending[0]["start"], "end": cue["end"], "words": pending})

    capitalize = True
    for cue in final:
        text = text_of(cue["words"])
        if capitalize and text:
            text = text[0].upper() + text[1:]
        text = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
        capitalize = bool(SENTENCE_END.search(text))
        cue["text"] = wrap_two_lines(text, LONG["lineChars"])
    return final


def respect_pauses(caps: list[dict], pauses: list[tuple[float, float]]) -> list[dict]:
    """A caption appears when speech starts and leaves when it stops.

    Word timings run through pauses, so a card can start during silence or hang
    on through it. Delay a card that starts inside a pause to the pause end
    (shifting its words with it) and end a card where a pause begins."""
    for cap in caps:
        for lo, hi in pauses:
            if lo - 0.02 <= cap["start"] < hi and hi < cap["end"] + 1.5:
                delta = hi - cap["start"]
                cap["start"] = hi
                for w in cap.get("words", []):
                    w["start"] = round(w["start"] + delta, 3)
                    w["end"] = round(w["end"] + delta, 3)
                cap["end"] = max(cap["end"] + delta if cap.get("words") else cap["end"], hi + SHORT["minHold"])
                break
        for lo, hi in pauses:
            if cap["start"] + SHORT["minHold"] <= lo < cap["end"]:
                cap["end"] = lo + 0.1
                break
    for a, b in zip(caps, caps[1:]):
        if a["end"] > b["start"] and not a.get("emphasis"):
            a["end"] = b["start"]
    return caps


def caption_mode(recipe: dict) -> str:
    mode = recipe.get("captions", {}).get("mode", "auto")
    if mode in {"short", "long"}:
        return mode
    duration = sum(float(s["out"]) - float(s["in"]) for s in recipe.get("segments", []))
    return "long" if duration > LONG_MODE_AFTER else "short"


def captions_from_recipe(project: Path, mode: str | None = None) -> list[dict]:
    recipe = read_json(project / "recipe.json")
    mode = mode or caption_mode(recipe)
    words, fallback, pauses = timeline_words(project, recipe)
    if mode == "short":
        settings = recipe.get("captions", {})
        elegant = [t.lower() for t in settings.get("elegant", [])]
        spans = mark_emphasis(words, settings.get("emphasis", []) + elegant, settings.get("autoEmphasis", True))
        caps = short_cards(words, pauses, spans)
        for cap in caps:
            if cap.get("emphasis") and re.sub(r"[^\w' ]+", "", cap["text"]).lower() in elegant:
                cap["elegant"] = True
    else:
        caps = long_cues(words)
    caps = respect_pauses(caps, pauses)
    caps.extend(fallback)
    caps.sort(key=lambda c: c["start"])
    for cap in caps:
        cap["start"] = round(cap["start"], 3)
        cap["end"] = round(cap["end"], 3)
    return caps


def main() -> int:
    parser = argparse.ArgumentParser(description="Write SRT, VTT and JSON captions.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--mode", choices=["short", "long"], help="Override recipe captions.mode.")
    parser.add_argument("--emphasis", help="Comma-separated key words/phrases that get their own big card; saved to recipe.json.")
    parser.add_argument("--no-auto-emphasis", action="store_true", help="Only emphasise the --emphasis terms.")
    parser.add_argument("--elegant", help="Comma-separated feeling words shown big in elegant italic serif; saved to recipe.json.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        recipe = read_json(project / "recipe.json")
        if args.elegant is not None:
            recipe["captions"]["elegant"] = [t.strip() for t in args.elegant.split(",") if t.strip()]
            write_json(project / "recipe.json", recipe)
        if args.emphasis is not None or args.no_auto_emphasis:
            if args.emphasis is not None:
                recipe["captions"]["emphasis"] = [t.strip() for t in args.emphasis.split(",") if t.strip()]
            if args.no_auto_emphasis:
                recipe["captions"]["autoEmphasis"] = False
            write_json(project / "recipe.json", recipe)
        mode = args.mode or caption_mode(recipe)
        caps = captions_from_recipe(project, mode)
        write_json(project / recipe["captions"]["json"], {"mode": mode, "captions": caps})
        write_srt(project / recipe["captions"]["srt"], caps)
        write_vtt(project / recipe["captions"]["vtt"], caps)
        print(f"Wrote {len(caps)} {mode}-form caption(s)")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
