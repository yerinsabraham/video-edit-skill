#!/usr/bin/env python3
"""Shared helpers for the video-edit skill scripts."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


class SkillError(RuntimeError):
    pass


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise SkillError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_project(project: Path) -> Path:
    project = project.expanduser().resolve()
    for name in ["work", "renders", "exports", "qa", "logs"]:
        (project / name).mkdir(parents=True, exist_ok=True)
    return project


TOOL_ENV = {
    "ffmpeg": "VIDEO_EDIT_FFMPEG",
    "ffprobe": "VIDEO_EDIT_FFPROBE",
    "whisper-cli": "VIDEO_EDIT_WHISPER_CLI",
}

# Homebrew's default ffmpeg ships without libass; the keg-only ffmpeg-full has it.
FFMPEG_KEGS = [Path("/opt/homebrew/opt/ffmpeg-full/bin"), Path("/usr/local/opt/ffmpeg-full/bin")]


def tool_home() -> Path:
    return Path(os.environ.get("VIDEO_EDIT_HOME", "~/.cache/video-edit")).expanduser()


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find_exe(name: str) -> str | None:
    """Resolve a tool: env override, then the skill tool cache, then ffmpeg-full, then PATH."""
    env = TOOL_ENV.get(name)
    if env and os.environ.get(env):
        path = Path(os.environ[env]).expanduser()
        return str(path) if _executable(path) else None
    candidates = [tool_home() / "bin" / name]
    if name in {"ffmpeg", "ffprobe"}:
        candidates.extend(keg / name for keg in FFMPEG_KEGS)
    for candidate in candidates:
        if _executable(candidate):
            return str(candidate)
    return shutil.which(name)


def ffmpeg_filters(ffmpeg: str | None) -> set[str]:
    if not ffmpeg:
        return set()
    result = subprocess.run([ffmpeg, "-hide_banner", "-filters"], text=True, capture_output=True, check=False)
    names = set()
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:
            names.add(parts[1])
    return names


def ffmpeg_encoders(ffmpeg: str | None) -> set[str]:
    if not ffmpeg:
        return set()
    result = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], text=True, capture_output=True, check=False)
    return {parts[1] for parts in (line.split() for line in (result.stdout or "").splitlines()) if len(parts) >= 2}


def h264_args(ffmpeg: str | None, purpose: str) -> list[str]:
    """Encoder args. Work and review copies use Apple's hardware encoder when present
    (about 6x less CPU); finals stay on libx264 for size and quality unless
    VIDEO_EDIT_HWENC=all. VIDEO_EDIT_HWENC=0 disables hardware encoding."""
    mode = os.environ.get("VIDEO_EDIT_HWENC", "auto")
    hardware = mode != "0" and (purpose != "final" or mode == "all") and "h264_videotoolbox" in ffmpeg_encoders(ffmpeg)
    if hardware:
        bitrate = {"work": "12M", "review": "8M", "final": "10M"}[purpose]
        return ["-c:v", "h264_videotoolbox", "-b:v", bitrate, "-pix_fmt", "yuv420p"]
    preset, crf = {"work": ("veryfast", "20"), "review": ("veryfast", "21"), "final": ("medium", "18")}[purpose]
    return ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p"]


def whisper_model(name: str = "small.en") -> Path | None:
    """Find a whisper.cpp ggml model by name or path."""
    direct = Path(name).expanduser()
    if direct.is_file():
        return direct
    env = os.environ.get("VIDEO_EDIT_WHISPER_MODEL")
    if env and Path(env).expanduser().is_file():
        return Path(env).expanduser()
    for folder in [tool_home() / "models", Path("~/.cache/whisper.cpp").expanduser(), Path("~/whisper.cpp/models").expanduser()]:
        candidate = folder / f"ggml-{name}.bin"
        if candidate.is_file():
            return candidate
    return None


def run_cmd(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=check,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except FileNotFoundError as exc:
        raise SkillError(f"Command not found: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise SkillError(f"Command failed: {' '.join(args)}\n{detail}") from exc


def ffprobe(path: Path) -> dict[str, Any]:
    exe = find_exe("ffprobe")
    if not exe:
        raise SkillError("ffprobe is missing. Install ffmpeg first.")
    result = run_cmd(
        [
            exe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def media_info(path: Path, media_id: str) -> dict[str, Any]:
    data = ffprobe(path)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    return {
        "id": media_id,
        "path": str(path.resolve()),
        "filename": path.name,
        "duration": duration,
        "width": width,
        "height": height,
        "fps": video.get("r_frame_rate"),
        "has_audio": bool(audio),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "size_bytes": int(data.get("format", {}).get("size") or 0),
    }


def discover_videos(paths: list[str], newest: int | None = None) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            found.extend(p for p in path.iterdir() if p.suffix.lower() in VIDEO_EXTS and p.is_file())
        elif path.suffix.lower() in VIDEO_EXTS and path.exists():
            found.append(path)
    found = sorted({p.resolve() for p in found}, key=lambda p: p.stat().st_mtime, reverse=True)
    if newest:
        found = found[:newest]
    return list(reversed(found))


def seconds_to_srt(value: float) -> str:
    millis = max(0, round(value * 1000))
    hours, rem = divmod(millis, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def seconds_to_vtt(value: float) -> str:
    return seconds_to_srt(value).replace(",", ".")


def write_srt(path: Path, captions: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for index, caption in enumerate(captions, 1):
        lines.extend(
            [
                str(index),
                f"{seconds_to_srt(caption['start'])} --> {seconds_to_srt(caption['end'])}",
                caption["text"],
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_vtt(path: Path, captions: list[dict[str, Any]]) -> None:
    lines = ["WEBVTT", ""]
    for caption in captions:
        lines.extend(
            [
                f"{seconds_to_vtt(caption['start'])} --> {seconds_to_vtt(caption['end'])}",
                caption["text"],
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def log_command(project: Path, name: str, args: list[str], status: str, detail: str = "") -> None:
    entry = {
        "at": now_iso(),
        "name": name,
        "args": args,
        "status": status,
        "detail": detail,
    }
    log = project / "commands.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_state(project: Path) -> dict[str, Any]:
    return read_json(
        project / "state.json",
        {
            "version": 1,
            "current": "recipe.json",
            "renders": [],
            "history": [],
            "notes": [],
        },
    )


def save_state(project: Path, state: dict[str, Any]) -> None:
    state.setdefault("version", 1)
    state.setdefault("current", "recipe.json")
    state.setdefault("renders", [])
    state.setdefault("history", [])
    state.setdefault("notes", [])
    write_json(project / "state.json", state)


def snapshot_project(project: Path, name: str, note: str = "") -> dict[str, Any]:
    versions = project / "versions" / name
    versions.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for filename in ["edl.json", "recipe.json", "segments.json", "transcript.json"]:
        src = project / filename
        if src.exists():
            dst = versions / filename
            shutil.copy2(src, dst)
            copied.append(filename)
    entry = {"name": name, "at": now_iso(), "note": note, "files": copied}
    state = load_state(project)
    history = [item for item in state.get("history", []) if item.get("name") != name]
    history.append(entry)
    state["history"] = history
    state["current"] = "recipe.json"
    save_state(project, state)
    return entry


def platform_report() -> dict[str, Any]:
    return {
        "createdAt": now_iso(),
        "os": platform.system().lower(),
        "machine": platform.machine(),
        "python": sys.executable,
        "pythonVersion": platform.python_version(),
        "ffmpeg": find_exe("ffmpeg"),
        "ffprobe": find_exe("ffprobe"),
        "whisperCli": find_exe("whisper-cli"),
        "whisperModel": str(whisper_model() or ""),
        "whisper": find_exe("whisper"),
        "node": find_exe("node"),
        "npm": find_exe("npm"),
        "cwd": os.getcwd(),
    }


HESITATIONS = {"um", "uh", "erm", "er", "ah", "hmm", "mm", "uhm"}
SOFT_FILLERS = {"so", "like", "well", "basically", "actually"}


def is_filler(text: str) -> bool:
    """Hesitations always count; soft fillers only when set off by a comma ("so," "like,")."""
    raw = str(text).strip().lower()
    word = re.sub(r"[^a-z]+", "", raw)
    if word in HESITATIONS:
        return True
    return word in SOFT_FILLERS and raw.endswith(",")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)
