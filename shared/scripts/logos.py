#!/usr/bin/env python3
"""Fetch a product logo into the project (never into the skill) for logo-pop.

    logos.py <project> "Claude Code"      # -> work/logos/claude.svg
    logos.py <project> --list             # names the auto-editor recognises

Logos come from Simple Icons (https://simpleicons.org, CC0 SVGs). The marks
themselves are trademarks of their owners: show them only when the video is
talking about that product, and never imply endorsement. A user-provided logo
file always wins (logos.py <project> "Name" --file logo.png).
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from _common import SkillError, download, ensure_project, fail

CDN = "https://cdn.jsdelivr.net/npm/simple-icons@{version}/icons/{slug}.svg"
VERSIONS = ["latest", "15"]  # icons occasionally move between releases

# Spoken name -> (Simple Icons slug, brand colour). Several products share a mark.
PRODUCTS = {
    "claude code": ("claude", "#D97757"),
    "claude": ("claude", "#D97757"),
    "anthropic": ("anthropic", "#191919"),
    "chatgpt": ("openai", "#111111"),
    "codex": ("openai", "#111111"),
    "openai": ("openai", "#111111"),
    "gemini": ("googlegemini", "#8E75B2"),
    "cursor": ("cursor", "#111111"),
    "notion": ("notion", "#111111"),
    "figma": ("figma", "#F24E1E"),
    "youtube": ("youtube", "#FF0000"),
    "instagram": ("instagram", "#E4405F"),
    "tiktok": ("tiktok", "#111111"),
    "capcut": ("capcut", "#111111"),
    "github": ("github", "#181717"),
    "vercel": ("vercel", "#111111"),
    "davinci resolve": ("davinciresolve", "#233A51"),
    "premiere": ("adobepremierepro", "#9999FF"),
}


def find_products(text: str) -> list[tuple[str, int]]:
    """Product names in text with their character offsets, longest names first."""
    found: list[tuple[str, int]] = []
    taken: list[range] = []
    for name in sorted(PRODUCTS, key=len, reverse=True):
        for m in re.finditer(rf"\b{re.escape(name)}\b", text, re.I):
            if any(m.start() in r for r in taken):
                continue
            taken.append(range(m.start(), m.end()))
            found.append((name, m.start()))
    return sorted(found, key=lambda x: x[1])


def fetch(project: Path, name: str, file: str | None = None) -> Path:
    key = name.lower().strip()
    out_dir = project / "work" / "logos"
    out_dir.mkdir(parents=True, exist_ok=True)
    if file:
        src = Path(file).expanduser().resolve()
        if not src.exists():
            raise SkillError(f"Logo file not found: {src}")
        out = out_dir / f"{re.sub(r'[^a-z0-9]+', '-', key)}{src.suffix.lower()}"
        shutil.copy2(src, out)
        return out
    slug, colour = PRODUCTS.get(key, (re.sub(r"[^a-z0-9]+", "", key), "#111111"))
    out = out_dir / f"{slug}.svg"
    if out.exists():
        return out
    svg = ""
    for version in VERSIONS:
        try:
            raw = download(CDN.format(version=version, slug=slug), out_dir / f"{slug}.raw.svg", timeout=20)
            svg = raw.read_text(encoding="utf-8")
            raw.unlink()
            break
        except SkillError:
            continue
    if "<svg" not in svg:
        raise SkillError(f"No logo for '{name}' ({slug}). Pass --file with the user's logo.")
    out.write_text(svg.replace("<svg ", f'<svg fill="{colour}" ', 1), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a product logo into the project.")
    parser.add_argument("project")
    parser.add_argument("name", nargs="?")
    parser.add_argument("--file", help="Use this logo file instead of downloading.")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    try:
        if args.list or not args.name:
            print(", ".join(sorted(PRODUCTS)))
            return 0
        print(fetch(ensure_project(Path(args.project)), args.name, args.file))
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
