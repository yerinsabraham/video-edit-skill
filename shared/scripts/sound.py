#!/usr/bin/env python3
"""Sound design: synthesized SFX, a ducked music bed, voice polish, and loudness.

    sound.py <project> sfx add --at 3.2 --kind pop [--gain -12]
    sound.py <project> sfx clear
    sound.py <project> music <file> [--gain -18]     # ducks under the voice
    sound.py <project> music none
    sound.py <project> list

SFX are generated locally from maths (no samples, no licences): whoosh, swipe,
pop, click, ding, boom. render.py mixes everything, cleans the voice (rumble
filter, gentle compression) and normalises to the platform loudness target
(-14 LUFS short-form, -16 long-form). Music is never invented: ask the user for
a track they have the rights to.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, read_json, run_cmd, tool_home, write_json

# aevalsrc expressions; random(0) gives noise. Durations in seconds.
SFX = {
    "whoosh": (0.5, "(random(0)*2-1)*pow(sin(PI*t/0.5),2)*0.9", "highpass=f=250,lowpass=f=3200"),
    "swipe": (0.28, "(random(0)*2-1)*pow(sin(PI*t/0.28),2)*0.8", "highpass=f=900,lowpass=f=6000"),
    "pop": (0.14, "sin(2*PI*t*(950-5200*t))*exp(-t*32)*0.9", "highpass=f=120"),
    "click": (0.04, "(random(0)*2-1)*exp(-t*380)*0.8", "highpass=f=1800"),
    "ding": (0.6, "(sin(2*PI*1318*t)*0.6+sin(2*PI*1976*t)*0.3)*exp(-t*7)", "highpass=f=300"),
    "boom": (0.8, "sin(2*PI*t*(110-70*t))*exp(-t*5)*0.95", "lowpass=f=400"),
}


def sfx_path(kind: str) -> Path:
    if kind not in SFX:
        raise SkillError(f"Unknown SFX '{kind}'. Choose: {', '.join(SFX)}")
    out = tool_home() / "sfx" / f"{kind}.wav"
    if out.exists():
        return out
    ffmpeg = find_exe("ffmpeg")
    if not ffmpeg:
        raise SkillError("ffmpeg is missing")
    out.parent.mkdir(parents=True, exist_ok=True)
    duration, expr, shape = SFX[kind]
    run_cmd([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             f"aevalsrc='{expr}':s=48000:d={duration}", "-af", f"{shape},aformat=channel_layouts=stereo", str(out)])
    return out


def audio_graph(recipe: dict, first_input: int, duration: float) -> tuple[list[str], list[str], str]:
    """Inputs and filter parts producing [aout] from [0:a], SFX cues, and music."""
    settings = recipe.get("audio", {})
    long_form = duration > 300
    target = settings.get("loudness", -16 if long_form else -14)
    inputs: list[str] = []
    parts = ["[0:a]highpass=f=80,acompressor=threshold=-20dB:ratio=2.5:attack=15:release=200:makeup=2,aformat=sample_rates=48000:channel_layouts=stereo[voice]"]
    mix = []
    idx = first_input
    music = recipe.get("music")
    if music and Path(music["file"]).exists():
        inputs += ["-stream_loop", "-1", "-t", f"{duration:.3f}", "-i", music["file"]]
        parts.append("[voice]asplit=2[voice][key]")
        parts.append(
            f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={float(music.get('gain', -18))}dB,"
            f"afade=t=in:d=0.6,afade=t=out:st={max(0.0, duration - 1.2):.2f}:d=1.2[mus]"
        )
        parts.append("[mus][key]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[ducked]")
        mix.append("[ducked]")
        idx += 1
    for n, cue in enumerate(recipe.get("sfx", [])):
        path = sfx_path(cue["kind"])
        inputs += ["-i", str(path)]
        delay = max(0, int(float(cue["at"]) * 1000))
        parts.append(f"[{idx}:a]volume={float(cue.get('gain', -12))}dB,adelay={delay}|{delay}[sfx{n}]")
        mix.append(f"[sfx{n}]")
        idx += 1
    if mix:
        parts.append(f"[voice]{''.join(mix)}amix=inputs={len(mix) + 1}:duration=first:normalize=0[mixed]")
        last = "mixed"
    else:
        last = "voice"
    parts.append(f"[{last}]loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000[aout]")
    return inputs, parts, "aout"


def main() -> int:
    parser = argparse.ArgumentParser(description="SFX cues, music bed, and loudness.")
    parser.add_argument("project")
    sub = parser.add_subparsers(dest="action", required=True)
    sfx = sub.add_parser("sfx")
    sfx_sub = sfx.add_subparsers(dest="sfx_action", required=True)
    add = sfx_sub.add_parser("add")
    add.add_argument("--at", type=float, required=True)
    add.add_argument("--kind", choices=list(SFX), required=True)
    add.add_argument("--gain", type=float, default=-12.0)
    sfx_sub.add_parser("clear")
    mus = sub.add_parser("music")
    mus.add_argument("file", help="Music file, or 'none' to remove.")
    mus.add_argument("--gain", type=float, default=-18.0)
    sub.add_parser("list")
    sub.add_parser("preview", help="Generate all SFX into the tool cache.")
    args = parser.parse_args()
    try:
        project = ensure_project(Path(args.project))
        recipe_path = project / "recipe.json"
        recipe = read_json(recipe_path)
        if args.action == "preview":
            for kind in SFX:
                print(sfx_path(kind))
            return 0
        if args.action == "list":
            m = recipe.get("music")
            print(f"music: {Path(m['file']).name} at {m['gain']} dB (ducked)" if m else "music: none")
            for cue in recipe.get("sfx", []):
                print(f"{cue['at']:.2f}s {cue['kind']} {cue.get('gain', -12)} dB")
            return 0
        if args.action == "music":
            if args.file == "none":
                recipe.pop("music", None)
            else:
                path = Path(args.file).expanduser().resolve()
                if not path.exists():
                    fail(f"Music not found: {path}")
                recipe["music"] = {"file": str(path), "gain": args.gain}
        elif args.sfx_action == "clear":
            recipe["sfx"] = []
        else:
            sfx_path(args.kind)
            recipe.setdefault("sfx", []).append({"at": round(args.at, 3), "kind": args.kind, "gain": args.gain, "manual": True})
            recipe["sfx"].sort(key=lambda c: c["at"])
        write_json(recipe_path, recipe)
        print("ok")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
