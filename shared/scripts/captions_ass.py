#!/usr/bin/env python3
"""Build an ASS subtitle file for burned-in captions (rendered by libass in ffmpeg).

Short-form: kinetic cards. The word being spoken is lit, the rest of the card
is dimmed, punch words (numbers, product, claim) get a stronger colour, and each
card pops in. Long-form: plain two-line cues on a translucent box.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json


FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"

DEFAULTS = {
    "font": "Anton",
    "animation": "pop",
    "primaryColor": "#ffffff",
    "outlineColor": "#000000",
    "highlightColor": "#ffe14d",
    "punchColor": "#22c55e",
    "safeBottomPx": 420,
    "safeTopPx": 220,
    "position": "bottom",
    "case": "upper",
    "sizeScale": 1.0,
    "elegantFont": "DM Serif Display",
    "elegantColor": "#fff4e0",
}


def ass_color(hex_color: str, alpha: int = 0) -> str:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise SkillError(f"Bad colour {hex_color}")
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(value: float) -> str:
    cs = max(0, round(value * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def caption_style(recipe: dict) -> dict:
    style = dict(DEFAULTS)
    style.update({k: v for k, v in recipe.get("lookPreset", {}).get("captions", {}).items() if v})
    brand = recipe.get("brand") or {}
    if brand.get("font") and brand["font"] != "Arial":  # Arial is brand.py's default, not a choice
        style["font"] = brand["font"]
    if brand.get("accent"):
        style["punchColor"] = brand["accent"]
    style.update({k: v for k, v in recipe.get("captions", {}).get("style", {}).items() if v})
    return style


def is_punch(word: str, punch: set[str]) -> bool:
    bare = re.sub(r"[^\w$%']+", "", word).lower()
    return bool(re.search(r"\d", word)) or "$" in word or "%" in word or bare in punch


def build_ass(recipe: dict, data: dict) -> str:
    width = int(recipe["output"]["width"])
    height = int(recipe["output"]["height"])
    style = caption_style(recipe)
    mode = data.get("mode", "short")
    captions = data.get("captions", [])
    punch = {p.lower() for p in recipe.get("captions", {}).get("punchWords", [])}
    base = min(width, height)
    margin_side = max(48, round(width * 0.06))
    if style["position"] == "top":
        alignment, margin_v = 8, int(style["safeTopPx"])
    elif style["position"] == "lower-middle":
        alignment, margin_v = 2, round(height * 0.38)
    elif style["position"] == "middle":
        alignment, margin_v = 5, 0
    else:
        alignment, margin_v = 2, int(style["safeBottomPx"])
    if mode == "long" and width > height:
        margin_v = round(height * 0.06)

    primary = ass_color(style["primaryColor"])
    outline = ass_color(style["outlineColor"])
    box = ass_color(style["outlineColor"], 0x60)
    short_size = round(base * (0.095 if style["font"] == "Anton" else 0.085) * float(style["sizeScale"]))
    emph_size = round(base * 0.17)
    emph_font = style.get("emphasisFont") or style["font"]
    case = (lambda t: t.lower()) if style["case"] == "lower" else (lambda t: t.upper())
    outline_w = max(3, round(short_size * (0.05 if style["case"] == "lower" else 0.08)))
    long_size = round(base * 0.05)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Short,{style['font']},{short_size},{primary},{primary},{outline},&H80000000,-1,0,0,0,100,100,1,0,1,{outline_w},2,{alignment},{margin_side},{margin_side},{margin_v},1",
        f"Style: Elegant,{style['elegantFont']},{round(emph_size * 1.05)},{ass_color(style['elegantColor'])},{primary},{outline},&H70000000,0,1,0,0,100,100,0,0,1,2,4,{alignment},{margin_side},{margin_side},{margin_v + (round(short_size * 1.3) if alignment == 2 else 0)},1",
        f"Style: Emph,{emph_font},{emph_size},{ass_color(style['punchColor'])},{primary},{outline},&H80000000,-1,0,0,0,100,100,1,0,1,{max(6, round(emph_size * 0.07))},3,{alignment},{margin_side},{margin_side},{margin_v + (round(short_size * 1.3) if alignment == 2 else 0)},1",
        f"Style: Long,{style['font']},{long_size},{primary},{primary},{box},{box},0,0,0,0,100,100,0,0,3,{max(6, round(long_size * 0.25))},0,{alignment},{margin_side},{margin_side},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    # Windows where a graphic covers the middle: captions move to the top.
    top_windows = [(float(w["start"]), float(w["end"])) for w in recipe.get("captions", {}).get("topWindows", [])]
    top_pos = f"{{\\an8\\pos({width // 2},{int(style['safeTopPx']) + 40})}}"

    def placed(start: float, text: str) -> str:
        return (top_pos + text) if any(lo <= start < hi for lo, hi in top_windows) else text

    lit = ass_color(style["highlightColor"])
    punch_color = ass_color(style["punchColor"])
    dim = "&H60&"
    for cap in captions:
        words = cap.get("words") or []
        if mode == "long" or not words:
            name = "Long" if mode == "long" else "Short"
            text = cap["text"] if mode == "long" else case(cap["text"])
            lines.append(f"Dialogue: 0,{ass_time(cap['start'])},{ass_time(cap['end'])},{name},,0,0,0,,{escape(text)}")
            continue
        tokens = [case(w["text"]) for w in words]
        if cap.get("emphasis") and cap.get("elegant"):
            # Feeling words: elegant italic serif that eases in rather than punching.
            text = escape(cap["text"].lower())
            ease = "{\\fad(120,150)\\fscx94\\fscy94\\t(0,260,\\fscx100\\fscy100)}"
            lines.append(f"Dialogue: 1,{ass_time(cap['start'])},{ass_time(cap['end'])},Elegant,,0,0,0,,{placed(cap['start'], ease + text)}")
            continue
        if cap.get("emphasis"):
            # Key word: its own big card, punched in with an overshoot and a slight tilt.
            text = escape(case(cap["text"]))
            pop = "{\\frz-3\\fscx35\\fscy35\\t(0,110,\\fscx118\\fscy118)\\t(110,200,\\fscx100\\fscy100)}"
            lines.append(f"Dialogue: 1,{ass_time(cap['start'])},{ass_time(cap['end'])},Emph,,0,0,0,,{placed(cap['start'], pop + text)}")
            continue
        if style.get("animation") == "pop":
            # Words appear as they are spoken; the current word is lit and bounces.
            # Unspoken words are drawn fully transparent so the line never reflows.
            for i, word in enumerate(words):
                start = cap["start"] if i == 0 else float(word["start"])
                end = float(words[i + 1]["start"]) if i + 1 < len(words) else cap["end"]
                if end <= start:
                    continue
                parts = []
                for j, token in enumerate(tokens):
                    if j < i:
                        colour = punch_color if is_punch(token, punch) else primary
                        parts.append(f"{{\\1c{colour}\\alpha&H00&\\fscx100\\fscy100}}{escape(token)}")
                    elif j == i:
                        colour = punch_color if is_punch(token, punch) else lit
                        parts.append(f"{{\\1c{colour}\\alpha&H00&\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}}{escape(token)}")
                    else:
                        parts.append(f"{{\\alpha&HFF&\\fscx100\\fscy100}}{escape(token)}")
                lead = "{\\fscx92\\fscy92\\t(0,80,\\fscx100\\fscy100)}" if i == 0 else ""
                lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Short,,0,0,0,,{placed(cap['start'], lead + ' '.join(parts))}")
            continue
        for i, word in enumerate(words):
            start = cap["start"] if i == 0 else float(word["start"])
            end = float(words[i + 1]["start"]) if i + 1 < len(words) else cap["end"]
            if end <= start:
                continue
            parts = []
            for j, token in enumerate(tokens):
                if j == i:
                    colour = punch_color if is_punch(token, punch) else lit
                    parts.append(f"{{\\1c{colour}\\1a&H00&}}{escape(token)}")
                elif is_punch(token, punch):
                    parts.append(f"{{\\1c{punch_color}\\1a{dim}}}{escape(token)}")
                else:
                    parts.append(f"{{\\1c{primary}\\1a{dim}}}{escape(token)}")
            pop = "{\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Short,,0,0,0,,{pop}{' '.join(parts)}")
    return "\n".join(lines) + "\n"


def write_ass(project: Path) -> Path:
    recipe = read_json(project / "recipe.json")
    data = read_json(project / recipe["captions"]["json"])
    if isinstance(data, list):
        data = {"mode": "short", "captions": data}
    out = project / recipe["captions"].get("ass", f"exports/{recipe['name']}.ass")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_ass(recipe, data), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the burn-in ASS file from caption JSON.")
    parser.add_argument("project", help="Project directory.")
    args = parser.parse_args()
    try:
        out = write_ass(ensure_project(Path(args.project)))
        print(f"Wrote {out}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
