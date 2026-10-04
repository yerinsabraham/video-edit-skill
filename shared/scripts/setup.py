#!/usr/bin/env python3
"""Check local requirements for the video-edit skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import download, ffmpeg_filters, platform_report, run_cmd, skill_root, tool_home, whisper_model, write_json


MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin"


def download_model(name: str) -> Path:
    target = tool_home() / "models" / f"ggml-{name}.bin"
    print(f"Downloading {name} to {target} ...")
    return download(MODEL_URL.format(name=name), target, timeout=120)


def install_tools(report: dict, only: set[str] | None = None) -> list[str]:
    """Install what is missing, the right way for this machine. Returns notes for
    anything that needs the user (admin rights, Node)."""
    import platform
    import shutil
    import subprocess
    import tarfile
    import zipfile

    notes: list[str] = []
    system, machine = platform.system(), platform.machine().lower()
    bin_dir = tool_home() / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    brew = shutil.which("brew")

    def step(label: str) -> None:
        print(f"- {label}", flush=True)

    want = lambda part: only is None or part in only
    filters = ffmpeg_filters(report.get("ffmpeg"))
    if want("ffmpeg") and "ass" not in filters:
        if system == "Darwin" and machine == "arm64" and brew:
            step("ffmpeg with libass: brew install ffmpeg-full (keg-only, does not replace your ffmpeg)")
            subprocess.run([brew, "install", "ffmpeg-full"], check=False)
        elif system == "Darwin":
            step("ffmpeg with libass: static build from evermeet.cx into ~/.cache/video-edit/bin")
            for name in ["ffmpeg", "ffprobe"]:
                archive = download(f"https://evermeet.cx/ffmpeg/getrelease/{name}/zip", bin_dir / f"{name}.zip", timeout=120)
                with zipfile.ZipFile(archive) as z:
                    z.extract(name, bin_dir)
                archive.unlink()
                (bin_dir / name).chmod(0o755)
                subprocess.run(["xattr", "-d", "com.apple.quarantine", str(bin_dir / name)], check=False, capture_output=True)
        elif system == "Linux":
            arch = "arm64" if machine in {"aarch64", "arm64"} else "amd64"
            step(f"ffmpeg with libass: static build ({arch}) into ~/.cache/video-edit/bin")
            archive = download(f"https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch}-static.tar.xz", bin_dir / "ffmpeg.tar.xz", timeout=300)
            with tarfile.open(archive) as t:
                for member in t.getmembers():
                    if member.name.endswith(("/ffmpeg", "/ffprobe")):
                        member.name = Path(member.name).name
                        t.extract(member, bin_dir)
            archive.unlink()
        elif system == "Windows":
            step("ffmpeg with libass: gyan.dev essentials build into %USERPROFILE%\\.cache\\video-edit\\bin")
            archive = download("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", bin_dir / "ffmpeg.zip", timeout=600)
            with zipfile.ZipFile(archive) as z:
                for member in z.namelist():
                    if member.endswith(("/bin/ffmpeg.exe", "/bin/ffprobe.exe")):
                        (bin_dir / Path(member).name).write_bytes(z.read(member))
            archive.unlink()

    if want("whisper") and not report.get("whisperCli"):
        if system == "Darwin" and machine == "arm64" and brew:
            step("whisper.cpp: brew install whisper-cpp")
            subprocess.run([brew, "install", "whisper-cpp"], check=False)
        elif system in {"Darwin", "Linux"}:
            step("whisper.cpp: building from source (about 5 minutes)")
            src = tool_home() / "whisper.cpp"
            if not src.exists():
                subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ggml-org/whisper.cpp", str(src)], check=True)
            cmake = shutil.which("cmake")
            if not cmake:
                venv = tool_home() / "venv"
                subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
                subprocess.run([str(venv / "bin" / "pip"), "-q", "install", "cmake"], check=True)
                cmake = str(venv / "bin" / "cmake")
            subprocess.run([cmake, "-B", "build", "-DCMAKE_BUILD_TYPE=Release", "-DWHISPER_BUILD_TESTS=OFF"], cwd=src, check=True, capture_output=True)
            subprocess.run([cmake, "--build", "build", "-j", "4", "--config", "Release", "--target", "whisper-cli"], cwd=src, check=True, capture_output=True)
            shutil.copy2(src / "build" / "bin" / "whisper-cli", bin_dir / "whisper-cli")
        elif system == "Windows":
            step("whisper.cpp: official Windows release")
            import json as _json

            # Not every release ships binaries; take the newest one that has a build for this
            # machine. The GitHub API is rate-limited for anonymous callers, so fall back to
            # a known release that has one.
            import os as _os
            import urllib.request as _ur

            arm = machine in {"arm64", "aarch64"}
            wanted_name = "whisper-bin-win-cpu-arm64.zip" if arm else "whisper-bin-x64.zip"
            fallback = ("https://github.com/ggml-org/whisper.cpp/releases/download/b5130/whisper-bin-win-cpu-arm64.zip" if arm
                        else "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-bin-x64.zip")
            asset = None
            try:
                req = _ur.Request("https://api.github.com/repos/ggml-org/whisper.cpp/releases?per_page=20",
                                  headers={"Accept": "application/vnd.github+json"})
                token = _os.environ.get("GITHUB_TOKEN") or _os.environ.get("GH_TOKEN")
                if token:
                    req.add_header("Authorization", f"Bearer {token}")
                with _ur.urlopen(req, timeout=30) as response:
                    releases = _json.loads(response.read().decode("utf-8"))
                asset = next((a for r in releases for a in r.get("assets", []) if a.get("name") == wanted_name), None)
            except Exception:
                asset = None
            asset = asset or {"browser_download_url": fallback}
            if asset:
                print(f"  using {asset['browser_download_url'].split('/download/')[1].split('/')[0]}")
                archive = download(asset["browser_download_url"], bin_dir / "whisper.zip", timeout=600)
                with zipfile.ZipFile(archive) as z:
                    for member in z.namelist():
                        if member.lower().endswith((".exe", ".dll")):
                            (bin_dir / Path(member).name).write_bytes(z.read(member))
                archive.unlink()
            else:
                notes.append("Windows: download whisper-bin-x64.zip from github.com/ggml-org/whisper.cpp/releases into %USERPROFILE%\\.cache\\video-edit\\bin")

    if want("model") and not whisper_model():
        step("speech model: small.en (about 470 MB)")
        download_model("small.en")

    node = report.get("node")
    if not want("motion"):
        pass
    elif node_major(node) >= 22:
        step("motion graphics engine: HyperFrames and its headless Chrome (first time only)")
        npx = shutil.which("npx")
        if npx:
            env = {**__import__("os").environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_SKIP_SKILLS": "1"}
            subprocess.run([npx, "--yes", "hyperframes@0.8.123", "browser", "ensure"], env=env, check=False, capture_output=True)
    else:
        winget = shutil.which("winget")
        if system == "Windows" and winget:
            step("Node.js LTS: winget install OpenJS.NodeJS.LTS (restart the terminal afterwards)")
            subprocess.run([winget, "install", "-e", "--id", "OpenJS.NodeJS.LTS", "--accept-source-agreements", "--accept-package-agreements"], check=False)
        else:
            notes.append("Motion graphics need Node.js 22+: " + ("brew install node" if brew else "https://nodejs.org (LTS)"))

    if want("mediapipe") and system == "Linux":
        import ctypes.util

        if not ctypes.util.find_library("EGL"):
            notes.append("Background cut-out needs libEGL: sudo apt install libegl1 libgl1 (Fedora: sudo dnf install mesa-libEGL)")
    if want("mediapipe") and system != "Darwin":
        try:
            import mediapipe  # noqa: F401
        except ImportError:
            step("person masks and face detection: pip install mediapipe opencv-python-headless")
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", "mediapipe", "opencv-python-headless"], check=False)
    return notes


def node_major(node: str | None) -> int:
    if not node:
        return 0
    match = re.match(r"v(\d+)", (run_cmd([node, "--version"], check=False).stdout or "").strip())
    return int(match.group(1)) if match else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check video-edit skill dependencies.")
    parser.add_argument("--json", action="store_true", help="Print the platform report as JSON.")
    parser.add_argument("--download-model", nargs="?", const="small.en", help="Download a whisper.cpp model (default small.en).")
    parser.add_argument("--install", action="store_true", help="Install everything missing (ffmpeg with libass, whisper.cpp, model, HyperFrames, MediaPipe off macOS).")
    parser.add_argument("--only", help="With --install: comma list of ffmpeg, whisper, model, motion, mediapipe.")
    args = parser.parse_args()

    if args.download_model:
        download_model(args.download_model)
    if args.install:
        print("Installing what is missing...")
        parts = set(args.only.split(",")) if args.only else {"ffmpeg", "whisper", "model", "motion", "mediapipe"}
        for part in ["ffmpeg", "whisper", "model", "motion", "mediapipe"]:
            if part not in parts:
                continue
            try:
                notes = install_tools(platform_report(), {part})
            except Exception as exc:  # one tool failing must not stop the others
                notes = [f"{part}: {exc}"]
            for note in notes:
                print(f"  ! {note}")

    report = platform_report()
    filters = ffmpeg_filters(report.get("ffmpeg"))
    report["ffmpegFilters"] = {name: name in filters for name in ["ass", "subtitles", "drawtext"]}
    report["whisperModel"] = str(whisper_model() or "")
    report["nodeMajor"] = node_major(report.get("node"))
    write_json(skill_root() / ".platform.json", report)

    missing = [name for name in ["ffmpeg", "ffprobe"] if not report.get(name)]
    burn = report["ffmpegFilters"]["ass"] or report["ffmpegFilters"]["subtitles"]
    engine = "whisper.cpp" if report.get("whisperCli") and report["whisperModel"] else ("whisper" if report.get("whisper") else "")
    motion = report["nodeMajor"] >= 22

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("video-edit setup")
        print(f"  platform:   {report['os']} {report['machine']}")
        print(f"  python:     {report['pythonVersion']} ({report['python']})")
        print(f"  ffmpeg:     {report.get('ffmpeg') or 'MISSING'}")
        print(f"  ffprobe:    {report.get('ffprobe') or 'MISSING'}")
        print(f"  captions:   {'burn-in (libass)' if burn else 'SIDECAR ONLY - ffmpeg has no libass'}")
        print(f"  transcribe: {engine or 'none (placeholder transcripts only)'}")
        if report.get("whisperCli"):
            print(f"  model:      {report['whisperModel'] or 'MISSING - run setup.py --download-model'}")
        print(f"  motion:     {'HyperFrames via npx (Node ' + str(report['nodeMajor']) + ')' if motion else 'off - needs Node 22+'}")
        try:
            from vision import available as vision_ok, use_mediapipe

            engine = "MediaPipe" if use_mediapipe() else "Apple Vision"
            print(f"  cut-out:    {engine + ' (face detection, text behind you)' if vision_ok() else 'off - run setup.py --install'}")
        except Exception:
            pass

    if missing:
        print("\nMissing required tools: " + ", ".join(missing), file=sys.stderr)
        if sys.platform == "darwin":
            print("Install with: brew install ffmpeg", file=sys.stderr)
        elif sys.platform.startswith("linux"):
            print("Install with: sudo apt install ffmpeg", file=sys.stderr)
        elif sys.platform.startswith("win"):
            print("Install with: python setup.py --install (or winget install Gyan.FFmpeg)", file=sys.stderr)
        return 1

    if not args.json and (not burn or not engine):
        print("\nRun `python3 setup.py --install` to install what is missing.")
    if not args.json:
        if not burn:
            print("\nCaptions will not be burned in. See shared/references/troubleshooting.md (captions)")
        if not engine:
            print("No transcription engine. See shared/references/troubleshooting.md (transcription)")
    print("READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
