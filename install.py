#!/usr/bin/env python3
"""Install or update the video-edit skill for Claude Code and/or Codex.

    python3 install.py                 # every agent found on this machine
    python3 install.py --target claude # or codex, or both
    python3 install.py --update        # pull the latest version, then reinstall

Claude Code users can instead add it as a plugin:
    /plugin marketplace add yerinsabraham/video-edit-skill
    /plugin install video-edit@video-edit-skill
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "skills" / "video-edit" / "SKILL.md"
PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"

TARGETS = {
    "claude": {"home_path": ".claude/skills/video-edit", "agents": None},
    "codex": {"home_path": ".codex/skills/video-edit", "agents": ROOT / "codex" / "agents"},
}


def render_skill(target: Path, name: str) -> str:
    """The plugin SKILL.md refers to ${CLAUDE_PLUGIN_ROOT}; a copied install points
    at its own folder instead."""
    text = SOURCE.read_text(encoding="utf-8").replace(PLACEHOLDER, str(target))
    if name == "codex":
        text = text.replace("types /video-edit, or gives notes", "asks Codex to edit them, or gives notes")
        text = text.replace("User request: $ARGUMENTS\n\n", "")  # Codex has no argument substitution
    return text


def remove_existing(path: Path, force: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if not force:
        raise SystemExit(f"{path} already exists. Re-run with --force (or --update).")
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def link_or_copy(src: Path, dst: Path, mode: str) -> None:
    if mode == "symlink":
        dst.symlink_to(src, target_is_directory=src.is_dir())
    elif src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".platform.json"))
    else:
        shutil.copy2(src, dst)


def install_one(name: str, home: Path, mode: str, force: bool) -> Path:
    config = TARGETS[name]
    target = home / config["home_path"]
    remove_existing(target, force)
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(render_skill(target, name), encoding="utf-8")
    link_or_copy(ROOT / "shared", target / "shared", mode)
    if config["agents"]:
        link_or_copy(config["agents"], target / "agents", mode)
    (target / "VERSION").write_text((ROOT / "VERSION").read_text(encoding="utf-8") if (ROOT / "VERSION").exists() else "dev\n", encoding="utf-8")
    return target


def detect(home: Path) -> list[str]:
    found = [name for name, dot in [("claude", ".claude"), ("codex", ".codex")] if (home / dot).exists()]
    return found or ["claude"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the video-edit skill for Claude Code and/or Codex.")
    parser.add_argument("--target", choices=["auto", "claude", "codex", "both"], default="auto")
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy", help="symlink keeps the install live-linked to this checkout (for development).")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory to install into.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing install.")
    parser.add_argument("--update", action="store_true", help="git pull this checkout, then reinstall over the old version.")
    args = parser.parse_args()

    if args.update:
        if (ROOT / ".git").exists():
            subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"], check=True)
        args.force = True
    home = args.home.expanduser().resolve()
    targets = {"both": ["claude", "codex"], "auto": detect(home)}.get(args.target, [args.target])
    for name in targets:
        print(f"installed {install_one(name, home, args.mode, args.force)}")
    print("Next: open your agent and type /video-edit (it sets itself up on the first run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
