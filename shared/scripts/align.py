#!/usr/bin/env python3
"""Re-time Whisper words onto the speech actually present in the audio.

whisper.cpp word timings run back to back through pauses and drift by up to a
second around them, so captions appear before the speaker talks. The audio's
real silences are reliable. This splits the audio into speech chunks between
silences and assigns each word to one chunk with a small dynamic program:
words stay in order, stay near their Whisper time, fill each chunk at a
plausible speaking rate, and prefer chunk boundaries after punctuation. Within
a chunk, Whisper's relative rhythm is kept and mapped onto the chunk.

With no usable silences the words are returned unchanged.
"""

from __future__ import annotations

import re

PUNCT = re.compile(r"[.!?,;:…][\"'”’)]*$")
SENTENCE = re.compile(r"[.!?…][\"'”’)]*$")
WINDOW = 4.0


def speech_chunks(silences: list[list[float]], duration: float) -> list[tuple[float, float]]:
    chunks, cursor = [], 0.0
    for lo, hi in sorted(silences):
        if lo - cursor > 0.08:
            chunks.append((cursor, lo))
        cursor = max(cursor, hi)
    if duration - cursor > 0.08:
        chunks.append((cursor, duration))
    return chunks


def align_words(words: list[dict], silences: list[list[float]], duration: float) -> list[dict]:
    if not words or not silences:
        return words
    chunks = speech_chunks(silences, duration)
    if len(chunks) < 2:
        return words
    n, m = len(words), len(chunks)
    mids = [(float(w["start"]) + float(w["end"])) / 2 for w in words]
    chars = [len(str(w["text"])) + 1 for w in words]
    speech = sum(b - a for a, b in chunks)
    rate = sum(chars) / max(speech, 0.1)
    prefix = [0]
    for c in chars:
        prefix.append(prefix[-1] + c)

    def time_cost(i: int, j: int) -> float:
        a, b = chunks[j]
        mid = mids[i]
        return 0.0 if a <= mid <= b else min(abs(mid - a), abs(mid - b))

    tc_prefix = [[0.0] * (n + 1) for _ in range(m)]
    for j in range(m):
        for i in range(n):
            tc_prefix[j][i + 1] = tc_prefix[j][i] + time_cost(i, j)

    def group_cost(k: int, i: int, j: int) -> float:
        a, b = chunks[j]
        dur = b - a
        if k == i:
            return dur * 0.8  # speech with no words: a breath, a laugh, noise
        expected = (prefix[i] - prefix[k]) / rate
        cost = tc_prefix[j][i] - tc_prefix[j][k]
        cost += abs(expected - dur) * 0.7
        last = str(words[i - 1]["text"])
        cost += -0.4 if SENTENCE.search(last) else (-0.2 if PUNCT.search(last) else 0.25)
        return cost

    inf = float("inf")
    best = [[inf] * (n + 1) for _ in range(m + 1)]
    back = [[-1] * (n + 1) for _ in range(m + 1)]
    best[0][0] = 0.0
    for j in range(1, m + 1):
        a, b = chunks[j - 1]
        prev, row, brow = best[j - 1], best[j], back[j]
        # Empty chunk: no words spoken here.
        for i in range(n + 1):
            if prev[i] < inf:
                row[i] = prev[i] + group_cost(i, i, j - 1)
                brow[i] = i
        # Words k..i-1 in this chunk, only those whose Whisper time is nearby.
        lo = next((x for x in range(n) if mids[x] >= a - WINDOW), n)
        hi = next((x for x in range(lo, n) if mids[x] > b + WINDOW), n)
        for k in range(lo, hi):
            if prev[k] == inf:
                continue
            for i in range(k + 1, hi + 1):
                cost = prev[k] + group_cost(k, i, j - 1)
                if cost < row[i]:
                    row[i] = cost
                    brow[i] = k
    if best[m][n] == inf:
        return words

    groups: list[tuple[int, int, int]] = []
    i = n
    for j in range(m, 0, -1):
        k = back[j][i]
        if k < i:
            groups.append((k, i, j - 1))
        i = k
    out = [dict(w) for w in words]
    for k, i, j in groups:
        a, b = chunks[j]
        ws, we = float(words[k]["start"]), float(words[i - 1]["end"])
        if we - ws > 0.2:
            scale = (b - a) / (we - ws)
            for idx in range(k, i):
                out[idx]["start"] = round(a + (float(words[idx]["start"]) - ws) * scale, 3)
                out[idx]["end"] = round(a + (float(words[idx]["end"]) - ws) * scale, 3)
        else:
            cursor = a
            span = (b - a) / max(1, prefix[i] - prefix[k])
            for idx in range(k, i):
                out[idx]["start"] = round(cursor, 3)
                cursor += chars[idx] * span
                out[idx]["end"] = round(cursor, 3)
    return out
