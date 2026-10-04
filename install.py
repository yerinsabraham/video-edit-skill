#!/usr/bin/env python3
"""Install the video-edit skill into Claude Code and/or Codex."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent


TARGETS = {
    "claude": {
        "home_path": ".claude/skills/video-edit",
        "skill": ROOT / "claude" / "SKILL.md",
        "agents": None,
    },
    "codex": {
        "home_path": ".codex/skills/video-edit",
        "skill": ROOT / "codex" / "SKILL.md",
        "agents": ROOT / "codex" / "agents",
    },
}


def remove_existing(path: Path, force: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if not force:
        raise SystemExit(f"Refusing to overwrite {path}. Re-run with --force.")
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def copy_or_link(src: Path, dst: Path, mode: str) -> None:
    if mode == "symlink":
        dst.symlink_to(src, target_is_directory=src.is_dir())
    else:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def install_one(name: str, home: Path, mode: str, force: bool) -> Path:
    config = TARGETS[name]
    target = home / config["home_path"]
    remove_existing(target, force)
    target.mkdir(parents=True, exist_ok=True)

    copy_or_link(config["skill"], target / "SKILL.md", "copy")
    copy_or_link(ROOT / "shared", target / "shared", mode)
    if config["agents"]:
        copy_or_link(config["agents"], target / "agents", mode)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Install video-edit skill for Claude Code and/or Codex.")
    parser.add_argument("--target", choices=["claude", "codex", "both"], default="both")
    parser.add_argument("--mode", choices=["symlink", "copy"], default="symlink")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory for installation.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing install target.")
    args = parser.parse_args()

    targets = ["claude", "codex"] if args.target == "both" else [args.target]
    installed = []
    for name in targets:
        installed.append(install_one(name, args.home.expanduser().resolve(), args.mode, args.force))

    for path in installed:
        print(f"installed {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
