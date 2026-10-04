#!/usr/bin/env python3
"""Clean Whisper artefacts, apply per-project corrections, and flag risky lines.

Reads transcript.raw.json (written once by transcribe.py) and writes
transcript.json plus qa/transcript-review.md. Safe to re-run after editing
corrections.json; the raw transcript is never modified.
"""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, write_json


PUNCT_ONLY = re.compile(r"^[\s.,!?;:…\-–—\"'”“’]+$")
BRACKETED = re.compile(r"^\s*[\[(].*[\])]\s*$")
SENTENCE_END = re.compile(r"[.!?…][\"'”’)]*$")

# Phrases Whisper emits over silence or outros that nobody said.
HALLUCINATIONS = [
    r"thanks? (you )?for watching",
    r"transcribed by",
    r"subtitles? by",
    r"captions? by",
    r"please subscribe",
    r"like and subscribe",
    r"see you (in the )?next (video|time)",
    r"amara\.org",
]

# Words that read as valid English but invert or change meaning when misheard.
DEFAULT_WATCH = ["fill", "tax", "state party"]

# Lines where the video promises something the edit or the deliverables must keep.
PROMISE_PATTERNS = [
    r"on (the )?screen",
    r"in the (description|pdf|doc|document|notes|link|comments|bio)",
    r"link (is )?(below|in)",
    r"i'?ll (show|put|share|link|send)",
    r"you can see (here|this)",
    r"(something )?like this\b",
    r"look at this",
    r"comment \w+",
    r"download",
]


def default_corrections() -> dict:
    return {
        "replacements": [
            {"pattern": r"\bcloud code\b", "replace": "Claude Code", "note": "product name"},
            {"pattern": r"\b(?:chat|chad) ?[dg] ?p ?t\b", "replace": "ChatGPT", "note": "product name"},
            {"pattern": r"\bclaws? code\b", "replace": "Claude Code", "note": "product name"},
            {"pattern": r"\bclaude (could|cold|coat)\b", "replace": "Claude Code", "note": "product name"},
            {"pattern": r"\bcould ?x\b", "replace": "Codex", "note": "product name"},
        ],
        "watch": ["codecs"],
        "neverAppear": [],
    }


def word_text(word: dict) -> str:
    return str(word.get("text", "")).strip()


def rejoin_fragments(words: list[dict]) -> list[dict]:
    """Attach lone punctuation and split fragments to the previous word."""
    out: list[dict] = []
    for word in words:
        text = word_text(word)
        if not text:
            continue
        prev = out[-1] if out else None
        same_media = prev is not None and prev.get("mediaId") == word.get("mediaId")
        joins = same_media and (
            PUNCT_ONLY.match(text)
            or word.get("join")
            or re.match(r"^['’](s|t|re|ve|ll|d|m)\b", text, re.I)
            or (re.search(r"\d[,.]$", word_text(prev)) and re.match(r"^\d", text))
        )
        if joins:
            prev["text"] = word_text(prev) + text
            prev["end"] = max(float(prev["end"]), float(word["end"]))
            continue
        item = {k: v for k, v in word.items() if k != "join"}
        item["text"] = text
        out.append(item)
    return out


def drop_artefacts(segments: list[dict]) -> tuple[list[dict], list[str]]:
    removed: list[str] = []
    kept: list[dict] = []
    pattern = re.compile("|".join(HALLUCINATIONS), re.I)
    for segment in segments:
        text = segment.get("text", "").strip()
        if not text or BRACKETED.match(text) or PUNCT_ONLY.match(text):
            removed.append(f"{segment.get('start', 0):.2f}s empty/bracketed: {text!r}")
            continue
        if pattern.search(text) and len(text) < 80:
            removed.append(f"{segment.get('start', 0):.2f}s credit/outro: {text!r}")
            continue
        kept.append(segment)
    # A run of "you" segments after the last real speech, per media.
    by_media: dict[str, int] = {}
    for index, segment in enumerate(kept):
        if not re.fullmatch(r"\s*you\.?\s*", segment.get("text", ""), re.I):
            by_media[segment["mediaId"]] = index
    final = []
    for index, segment in enumerate(kept):
        if index > by_media.get(segment["mediaId"], -1):
            removed.append(f"{segment.get('start', 0):.2f}s trailing 'you'")
            continue
        final.append(segment)
    return final, removed


def apply_replacements(text: str, replacements: list[dict]) -> str:
    for rule in replacements:
        flags = 0 if rule.get("caseSensitive") else re.I
        text = re.sub(rule["pattern"], rule["replace"], text, flags=flags)
    # A quote glued to the previous word: comment"skill" -> comment "skill".
    text = re.sub(r"(\w)([\"“])(\w)", r"\1 \2\3", text)
    # First person last, so it cannot fire inside a word another fix produced.
    return re.sub(r"(?<![\w'’])i(?=$|[\s'’.,!?;:])", "I", text)


def retime_words(old: list[dict], new_tokens: list[str]) -> list[dict]:
    """Map corrected tokens back onto word timings, spreading replaced runs by length."""
    old_tokens = [word_text(w) for w in old]
    out: list[dict] = []
    matcher = difflib.SequenceMatcher(a=[t.lower() for t in old_tokens], b=[t.lower() for t in new_tokens], autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "equal":
            for offset in range(a1 - a0):
                out.append({**old[a0 + offset], "text": new_tokens[b0 + offset]})
            continue
        if b1 == b0:
            continue
        if a1 > a0:
            start, end = float(old[a0]["start"]), float(old[a1 - 1]["end"])
            base = old[a0]
        else:
            anchor = old[a0 - 1] if a0 > 0 else old[0]
            start = end = float(anchor["end"])
            base = anchor
        tokens = new_tokens[b0:b1]
        total = sum(len(t) for t in tokens) or 1
        cursor = start
        for token in tokens:
            span = (end - start) * len(token) / total
            out.append({**base, "text": token, "start": round(cursor, 3), "end": round(cursor + span, 3)})
            cursor += span
    return out


def find_lines(segments: list[dict], patterns: list[str], terms: list[str] | None = None) -> list[tuple[dict, str]]:
    """Return (segment, label) for the first pattern each segment matches."""
    if terms is not None:
        patterns = [rf"\b{re.escape(t)}\b" for t in terms]
    labels = terms if terms is not None else patterns
    hits = []
    for segment in segments:
        text = segment.get("text", "")
        for pattern, label in zip(patterns, labels):
            if re.search(pattern, text, re.I):
                hits.append((segment, label))
                break
    return hits


def fix(project: Path) -> dict:
    raw_path = project / "transcript.raw.json"
    current = project / "transcript.json"
    if not raw_path.exists():
        if not current.exists():
            raise SkillError("Missing transcript.json. Run transcribe.py first.")
        write_json(raw_path, read_json(current))
    raw = read_json(raw_path)

    corrections_path = project / "corrections.json"
    if not corrections_path.exists():
        write_json(corrections_path, default_corrections())
    corrections = read_json(corrections_path)
    replacements = corrections.get("replacements", [])

    words = rejoin_fragments(raw.get("words", []))
    # Each word belongs to exactly one segment: the last one starting at or before it.
    segments = [{**segment, "words": []} for segment in raw.get("segments", [])]
    for word in words:
        owner = None
        for segment in segments:
            if segment.get("mediaId") != word.get("mediaId"):
                continue
            if owner is None or float(segment["start"]) <= float(word["start"]) + 0.01:
                owner = segment
        if owner is not None:
            owner["words"].append(word)
    segments, removed = drop_artefacts(segments)

    fixed_segments = []
    all_words = []
    changed = 0
    for segment in segments:
        text = apply_replacements(" ".join(word_text(w) for w in segment["words"]) or segment.get("text", ""), replacements)
        new_words = retime_words(segment["words"], text.split()) if segment["words"] else []
        if text != segment.get("text", "").strip():
            changed += 1
        fixed_segments.append({**segment, "text": text, "words": [{k: v for k, v in w.items() if k != "mediaId"} for w in new_words]})
        all_words.extend({**w, "mediaId": segment["mediaId"]} for w in new_words)

    transcript = {**raw, "segments": fixed_segments, "words": all_words, "fixed": True}
    write_json(current, transcript)

    watch = DEFAULT_WATCH + corrections.get("watch", [])
    watch_hits = find_lines(fixed_segments, [], terms=watch)
    never = find_lines(fixed_segments, [], terms=corrections.get("neverAppear", []))
    promises = find_lines(fixed_segments, PROMISE_PATTERNS)

    lines = ["# Transcript Review", "", f"Engine: {raw.get('engine', 'unknown')}", ""]
    if raw.get("engine") == "placeholder":
        lines += ["**Placeholder transcript: captions are not from speech.**", ""]
    lines += ["## Read the transcript", "", "Read `transcript.json` end to end before planning cuts, captions or graphics.", ""]
    lines += ["## Removed artefacts", ""] + ([f"- {item}" for item in removed] or ["- None"])
    lines += ["", "## Must never appear", ""] + ([f"- {s['start']:.2f}s `{s['mediaId']}`: {s['text']}" for s, _ in never] or ["- None"])
    lines += ["", "## Promises to keep", "", "The speaker says something will be shown or provided. Make it true or cut it.", ""]
    lines += [f"- {s['start']:.2f}s `{s['mediaId']}`: {s['text']}" for s, _ in promises] or ["- None"]
    lines += ["", "## Check for misheard meaning", "", "Real words that may be wrong. Add a rule to `corrections.json` if misheard.", ""]
    lines += [f"- {s['start']:.2f}s `{s['mediaId']}` ({p}): {s['text']}" for s, p in watch_hits] or ["- None"]
    review = project / "qa" / "transcript-review.md"
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"segments": len(fixed_segments), "changed": changed, "removed": len(removed), "never": len(never), "promises": len(promises)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean and correct transcript.json from transcript.raw.json.")
    parser.add_argument("project", help="Project directory.")
    args = parser.parse_args()
    try:
        project = ensure_project(Path(args.project))
        result = fix(project)
        print(
            f"Fixed transcript: {result['segments']} segment(s), {result['changed']} corrected, "
            f"{result['removed']} artefact(s) removed, {result['promises']} promise(s) to check"
        )
        if result["never"]:
            print(f"WARNING: {result['never']} line(s) contain a neverAppear term; see qa/transcript-review.md")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
