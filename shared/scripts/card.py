#!/usr/bin/env python3
"""Generate a simple local title/CTA card and insert it into the EDL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, read_json, snapshot_project, write_json
from recipe import main as recipe_main


FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        raise SkillError(f"Invalid color: {hex_color}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def wrap(text: str, width: int) -> list[str]:
    words = text.upper().split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def draw_text(pixels: list[list[tuple[int, int, int]]], text: str, x: int, y: int, scale: int, color: tuple[int, int, int]) -> None:
    for char in text.upper():
        glyph = FONT.get(char, FONT[" "])
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    for sy in range(scale):
                        for sx in range(scale):
                            py = y + gy * scale + sy
                            px = x + gx * scale + sx
                            if 0 <= py < len(pixels) and 0 <= px < len(pixels[0]):
                                pixels[py][px] = color
        x += 6 * scale


def write_ppm(path: Path, width: int, height: int, pixels: list[list[tuple[int, int, int]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        for row in pixels:
            for r, g, b in row:
                fh.write(bytes((r, g, b)))


def make_card(path: Path, title: str, subtitle: str, width: int, height: int, bg: str, fg: str, accent: str) -> None:
    bgc = rgb(bg)
    fgc = rgb(fg)
    acc = rgb(accent)
    pixels = [[bgc for _ in range(width)] for _ in range(height)]
    band_h = max(20, height // 90)
    for y in range(height - band_h * 8, height - band_h * 5):
        for x in range(width // 8, width - width // 8):
            pixels[y][x] = acc
    title_scale = max(8, width // 115)
    subtitle_scale = max(5, width // 170)
    title_lines = wrap(title, max(8, width // (6 * title_scale) - 2))[:4]
    subtitle_lines = wrap(subtitle, max(10, width // (6 * subtitle_scale) - 2))[:3]
    block_h = len(title_lines) * 8 * title_scale + len(subtitle_lines) * 8 * subtitle_scale
    y = max(height // 5, (height - block_h) // 2)
    for line in title_lines:
        line_w = len(line) * 6 * title_scale
        draw_text(pixels, line, max(0, (width - line_w) // 2), y, title_scale, fgc)
        y += 8 * title_scale
    y += subtitle_scale * 3
    for line in subtitle_lines:
        line_w = len(line) * 6 * subtitle_scale
        draw_text(pixels, line, max(0, (width - line_w) // 2), y, subtitle_scale, fgc)
        y += 8 * subtitle_scale
    write_ppm(path, width, height, pixels)


def insert_segment(edl: dict, segment: dict, position: str) -> dict:
    segments = edl.setdefault("segments", [])
    if position == "start":
        segments.insert(0, segment)
    elif position == "end":
        segments.append(segment)
    else:
        raise SkillError("position must be start or end")
    for index, item in enumerate(segments, 1):
        item["id"] = f"s{index}"
    return edl


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a title/CTA card and insert it into edl.json.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--position", choices=["start", "end"], default="start")
    parser.add_argument("--duration", type=float, default=1.5)
    parser.add_argument("--name", default="card")
    parser.add_argument("--background", default="#0f172a")
    parser.add_argument("--foreground", default="#ffffff")
    parser.add_argument("--accent", default="#2563eb")
    parser.add_argument("--update-recipe", action="store_true")
    parser.add_argument("--recipe-name", default="v-card")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        snapshot_project(project, f"before-card-{args.name}", f"before adding card {args.name}")
        config = read_json(project / "project.json")
        width = int(config.get("width", 1080))
        height = int(config.get("height", 1920))
        out = project / "work" / "cards" / f"{args.name}.ppm"
        make_card(out, args.title, args.subtitle, width, height, args.background, args.foreground, args.accent)
        edl = read_json(project / "edl.json")
        segment = {
            "id": "card",
            "type": "image",
            "mediaId": f"card-{args.name}",
            "clip": str(out),
            "in": 0,
            "out": round(float(args.duration), 3),
            "line": " ".join(part for part in [args.title, args.subtitle] if part),
            "look": config.get("look", "clean-creator"),
            "zoom": 1.0,
            "cx": 0.5,
            "cy": 0.5,
        }
        write_json(project / "edl.json", insert_segment(edl, segment, args.position))
        if args.update_recipe:
            old_argv = sys.argv
            sys.argv = ["recipe.py", str(project), "--name", args.recipe_name, "--width", str(width), "--height", str(height)]
            try:
                recipe_main()
            finally:
                sys.argv = old_argv
        print(f"Wrote {out}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

