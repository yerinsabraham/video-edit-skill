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
FADE_TAG = "{\\fad(140,90)}"

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


def caption_style(recipe: dict, look: dict | None = None) -> dict:
    style = dict(DEFAULTS)
    preset = look if look is not None else recipe.get("lookPreset", {})
    style.update({k: v for k, v in preset.get("captions", {}).items() if v not in (None, "")})
    style["look"] = preset.get("style", {})
    brand = recipe.get("brand") or {}
    if brand.get("font") and brand["font"] != "Arial":  # Arial is brand.py's default, not a choice
        style["font"] = brand["font"]
    if brand.get("accent") and look is None:
        style["punchColor"] = brand["accent"]
    style.update({k: v for k, v in recipe.get("captions", {}).get("style", {}).items() if v})
    return style


def is_punch(word: str, punch: set[str]) -> bool:
    bare = re.sub(r"[^\w$%']+", "", word).lower()
    return bool(re.search(r"\d", word)) or "$" in word or "%" in word or bare in punch


def style_set(style: dict, suffix: str, width: int, height: int, mode: str) -> tuple[list[str], dict]:
    """ASS style lines for one look, plus the values its events need."""
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
    spacing = int(style.get("spacing", 1))
    outline_w = max(3, round(short_size * (0.05 if style["case"] == "lower" else 0.08)))
    raised = margin_v + (round(short_size * 1.3) if alignment == 2 else 0)
    lines = [
        f"Style: Short{suffix},{style['font']},{short_size},{primary},{primary},{outline},&H80000000,-1,0,0,0,100,100,{spacing},0,1,{outline_w},2,{alignment},{margin_side},{margin_side},{margin_v},1",
        f"Style: Elegant{suffix},{style['elegantFont']},{round(emph_size * 1.05)},{ass_color(style['elegantColor'])},{primary},{outline},&H70000000,0,1,0,0,100,100,0,0,1,2,4,{alignment},{margin_side},{margin_side},{raised},1",
        f"Style: Emph{suffix},{emph_font},{emph_size},{ass_color(style['punchColor'])},{primary},{outline},&H80000000,-1,0,0,0,100,100,1,0,1,{max(6, round(emph_size * 0.07))},3,{alignment},{margin_side},{margin_side},{raised},1",
        f"Style: Long{suffix},{style['font']},{round(base * 0.05)},{primary},{primary},{box},{box},0,0,0,0,100,100,0,0,3,{max(6, round(base * 0.0125))},0,{alignment},{margin_side},{margin_side},{margin_v},1",
    ]
    values = {
        "primary": primary, "lit": ass_color(style["highlightColor"]), "punch": ass_color(style["punchColor"]),
        "case": (lambda t: t.lower()) if style["case"] == "lower" else (lambda t: t.upper()),
        "animation": style.get("animation", "pop"), "emphasis": style["look"].get("emphasis", "bold"),
        "sparkles": bool(style["look"].get("sparkles")), "suffix": suffix, "short_size": short_size,
    }
    return lines, values


def build_ass(recipe: dict, data: dict) -> str:
    from apply_look import load_look

    width = int(recipe["output"]["width"])
    height = int(recipe["output"]["height"])
    mode = data.get("mode", "short")
    captions = data.get("captions", [])
    punch = {p.lower() for p in recipe.get("captions", {}).get("punchWords", [])}
    main_style = caption_style(recipe)

    # Sections can switch look ("use soft when I say the cool aesthetic").
    sections = [(float(sec["start"]), float(sec["end"]), sec["look"]) for sec in recipe.get("sections", [])]
    sets: dict[str, dict] = {}
    style_lines: list[str] = []
    lines_main, sets[""] = style_set(main_style, "", width, height, mode)
    style_lines += lines_main
    for look_id in sorted({sec[2] for sec in sections}):
        try:
            look_style = caption_style(recipe, load_look(look_id))
        except SkillError:
            continue
        extra, sets[look_id] = style_set(look_style, f"_{look_id.replace('-', '_')}", width, height, mode)
        style_lines += extra

    def values_at(t: float) -> dict:
        for lo, hi, look_id in sections:
            if lo <= t < hi and look_id in sets:
                return sets[look_id]
        return sets[""]

    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *style_lines, "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    # Windows where a graphic covers the middle: captions move to the top.
    top_windows = [(float(w["start"]), float(w["end"])) for w in recipe.get("captions", {}).get("topWindows", [])]
    top_pos = f"{{\\an8\\pos({width // 2},{int(main_style['safeTopPx']) + 40})}}"

    def placed(start: float, text: str) -> str:
        return (top_pos + text) if any(lo <= start < hi for lo, hi in top_windows) else text

    dim = "&H60&"
    for cap in captions:
        v = values_at(float(cap["start"]))
        sfx, case, primary, lit, punch_color = v["suffix"], v["case"], v["primary"], v["lit"], v["punch"]
        t0, t1 = ass_time(cap["start"]), ass_time(cap["end"])
        words = cap.get("words") or []
        if mode == "long" or not words:
            name = ("Long" if mode == "long" else "Short") + sfx
            text = cap["text"] if mode == "long" else case(cap["text"])
            lines.append(f"Dialogue: 0,{t0},{t1},{name},,0,0,0,,{escape(text)}")
            continue
        tokens = [case(w["text"]) for w in words]
        if cap.get("emphasis") and (cap.get("elegant") or v["emphasis"] == "elegant"):
            # Feeling words (and every key word in soft/studio): elegant italic serif that
            # eases in; soft adds twinkling sparkles either side.
            text = escape(cap["text"].lower())
            ease = "{\\fad(120,150)\\fscx94\\fscy94\\t(0,260,\\fscx100\\fscy100)}"
            if v["sparkles"]:
                star = "{\\fs%d\\alpha&H40&\\t(0,300,\\alpha&H00&)\\t(300,600,\\alpha&H60&)}✦{\\r}" % round(v["short_size"] * 0.9)
                text = f"{star} {ease}{text} {star}"
                ease = ""
            lines.append(f"Dialogue: 1,{t0},{t1},Elegant{sfx},,0,0,0,,{placed(cap['start'], ease + text)}")
            continue
        if cap.get("emphasis"):
            # Key word: its own big card, punched in with an overshoot and a slight tilt.
            text = escape(case(cap["text"]))
            pop = "{\\frz-3\\fscx35\\fscy35\\t(0,110,\\fscx118\\fscy118)\\t(110,200,\\fscx100\\fscy100)}"
            lines.append(f"Dialogue: 1,{t0},{t1},Emph{sfx},,0,0,0,,{placed(cap['start'], pop + text)}")
            continue
        if v["animation"] == "fade":
            # Calm: the whole card fades in and out, no bounce.
            faded = placed(cap["start"], FADE_TAG + escape(" ".join(tokens)))
            lines.append(f"Dialogue: 0,{t0},{t1},Short{sfx},,0,0,0,,{faded}")
            continue
        if v["animation"] == "pop":
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
                lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Short{sfx},,0,0,0,,{placed(cap['start'], lead + ' '.join(parts))}")
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
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Short{sfx},,0,0,0,,{pop}{' '.join(parts)}")
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
