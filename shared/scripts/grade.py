#!/usr/bin/env python3
"""Colour grade the footage: measure it, recommend a natural correction, or match a look.

    grade.py <project>                       # recommended natural grade (default)
    grade.py <project> --preset warm|cool|punchy|cinematic|natural|none
    grade.py <project> --lut look.cube        # a LUT you already use
    grade.py <project> --match still.jpg      # move toward a reference image's look
    grade.py <project> --strength 0.6         # soften any grade

Writes recipe["grade"] and qa/grade-before-after.jpg. Only the footage is graded,
never captions or graphics. Renders pick it up; no re-assembly needed.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, filter_path, find_exe, read_json, run_cmd, snapshot_project, write_json

PRESETS = {
    # (contrast, brightness, saturation, gamma, colorbalance shadows/mids/highlights rgb)
    "warm": dict(contrast=1.06, saturation=1.10, balance="rm=0.04:bm=-0.04:rh=0.03:bh=-0.03"),
    "cool": dict(contrast=1.06, saturation=1.04, balance="rm=-0.03:bm=0.04:bh=0.03"),
    "punchy": dict(contrast=1.12, saturation=1.22, balance=""),
    "cinematic": dict(contrast=1.10, saturation=0.95, balance="rs=-0.05:bs=0.06:rh=0.05:bh=-0.05"),
}


def stats(ffmpeg: str, source: str, is_image: bool = False) -> dict:
    """Average luma, luma range, saturation, and colour cast across sampled frames."""
    vf = "scale=480:-2,signalstats,metadata=print" if is_image else "fps=1,scale=480:-2,signalstats,metadata=print"
    result = run_cmd([ffmpeg, "-hide_banner", "-i", source, "-vf", vf, "-f", "null", "-"], check=False)
    log = result.stderr or ""

    def avg(key: str) -> float:
        values = [float(v) for v in re.findall(rf"lavfi\.signalstats\.{key}=([\d.]+)", log)]
        if not values:
            raise SkillError(f"Could not measure {key} on {source}")
        return sum(values) / len(values)

    return {
        "luma": avg("YAVG"), "low": avg("YLOW"), "high": avg("YHIGH"),
        "sat": avg("SATAVG"), "u": avg("UAVG") - 128, "v": avg("VAVG") - 128,
    }


def natural(s: dict, face_luma: float | None = None) -> dict:
    """Gentle, social-ready correction judged on the face, not the whole frame:
    a bright white room should stay bright. Lift the midtones if the face is
    underexposed, never darken unless highlights clip, add a little contrast,
    vibrance (protects skin) and warmth, and pull out half of any colour cast."""
    brightness = 0.0
    if s["luma"] < 100:
        brightness = min(0.06, (100 - s["luma"]) / 255 * 0.6)
    elif s["high"] > 240:
        brightness = -0.02
    gamma = 1.0
    if face_luma is not None and face_luma < 110:
        gamma = 1.0 + min(0.14, (110 - face_luma) / 255 * 0.8)
    spread = s["high"] - s["low"]
    contrast = 1.06 if spread < 150 else 1.03
    rm = max(-0.06, min(0.06, -s["v"] / 128 * 0.5)) + 0.012
    bm = max(-0.06, min(0.06, -s["u"] / 128 * 0.5)) - 0.012
    return dict(contrast=contrast, brightness=brightness, gamma=gamma, saturation=1.03, vibrance=0.18,
                balance=f"rm={rm:.3f}:bm={bm:.3f}")


def face_luma(ffmpeg: str, aroll: Path, project: Path) -> float | None:
    try:
        from vision import available, faces

        f = faces(project).get("face") if available() else None  # typical position, not the full range
    except Exception:
        return None
    if not f:
        return None
    # Inner part of the face box: skin, not hair or background.
    f = {"x": f["x"] + f["w"] * 0.2, "y": f["y"] + f["h"] * 0.25, "w": f["w"] * 0.6, "h": f["h"] * 0.6}
    crop = f"crop=iw*{f['w']:.3f}:ih*{f['h']:.3f}:iw*{f['x']:.3f}:ih*{f['y']:.3f}"
    result = run_cmd([ffmpeg, "-hide_banner", "-i", str(aroll), "-vf", f"fps=1,{crop},signalstats,metadata=print", "-f", "null", "-"], check=False)
    values = [float(v) for v in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", result.stderr or "")]
    return sum(values) / len(values) if values else None


def match(src: dict, ref: dict) -> dict:
    brightness = max(-0.1, min(0.1, (ref["luma"] - src["luma"]) / 255))
    contrast = max(0.85, min(1.25, (ref["high"] - ref["low"]) / max(1.0, src["high"] - src["low"])))
    saturation = max(0.6, min(1.5, ref["sat"] / max(1.0, src["sat"])))
    rm = max(-0.1, min(0.1, (ref["v"] - src["v"]) / 128))
    bm = max(-0.1, min(0.1, (ref["u"] - src["u"]) / 128))
    return dict(contrast=contrast, brightness=brightness, saturation=saturation, balance=f"rm={rm:.3f}:bm={bm:.3f}")


def build_filter(params: dict, strength: float) -> str:
    def soften(value: float, neutral: float) -> float:
        return neutral + (value - neutral) * strength

    parts = [
        "eq=contrast={:.3f}:brightness={:.3f}:saturation={:.3f}:gamma={:.3f}".format(
            soften(params.get("contrast", 1.0), 1.0), soften(params.get("brightness", 0.0), 0.0),
            soften(params.get("saturation", 1.0), 1.0), soften(params.get("gamma", 1.0), 1.0),
        )
    ]
    if params.get("vibrance"):
        parts.append(f"vibrance=intensity={params['vibrance'] * strength:.3f}")
    if params.get("balance"):
        scaled = ":".join(f"{k}={float(v) * strength:.3f}" for k, v in (item.split("=") for item in params["balance"].split(":")))
        parts.append(f"colorbalance={scaled}")
    return ",".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Colour grade the footage.")
    parser.add_argument("project")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preset", choices=["natural", "warm", "cool", "punchy", "cinematic", "none"])
    group.add_argument("--lut", help=".cube LUT file")
    group.add_argument("--match", help="Reference image (a still from a video whose look you want)")
    parser.add_argument("--strength", type=float, default=1.0, help="0-1, softens the grade (not LUTs).")
    parser.add_argument("--at", type=float, default=None, help="Timeline second for the before/after still.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        ffmpeg = find_exe("ffmpeg")
        if not ffmpeg:
            fail("ffmpeg is missing")
        aroll = project / "work" / "aroll.mp4"
        if not aroll.exists():
            fail("Missing work/aroll.mp4. Run assemble.py first.")
        recipe = read_json(project / "recipe.json")
        snapshot_project(project, "before-grade", "before colour grade")
        source = stats(ffmpeg, str(aroll))
        preset = args.preset or ("lut" if args.lut else "match" if args.match else "natural")
        if preset == "none":
            recipe.pop("grade", None)
            write_json(project / "recipe.json", recipe)
            print("Removed colour grade.")
            return 0
        if args.lut:
            lut = Path(args.lut).expanduser().resolve()
            if not lut.exists():
                fail(f"LUT not found: {lut}")
            filt = f"lut3d=file={filter_path(lut)}"
        elif args.match:
            ref = Path(args.match).expanduser().resolve()
            filt = build_filter(match(source, stats(ffmpeg, str(ref), is_image=True)), args.strength)
        elif preset == "natural":
            filt = build_filter(natural(source, face_luma(ffmpeg, aroll, project)), args.strength)
        else:
            base = natural(source, face_luma(ffmpeg, aroll, project))
            base.update({k: v for k, v in PRESETS[preset].items()})
            filt = build_filter(base, args.strength)
        recipe["grade"] = {"name": preset, "filter": filt, "measured": {k: round(v, 1) for k, v in source.items()}}
        write_json(project / "recipe.json", recipe)

        at = args.at if args.at is not None else float(read_json(project / "segments.json", {}).get("duration", 4)) / 2
        out = project / "qa" / "grade-before-after.jpg"
        graph = f"[0:v]scale=540:-2,split[a][b0];[b0]{filt}[b];[a][b]hstack"
        run_cmd([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(aroll), "-filter_complex", graph, "-frames:v", "1", str(out)])
        m = source
        print(f"Measured: brightness {m['luma']:.0f}/255, range {m['low']:.0f}-{m['high']:.0f}, saturation {m['sat']:.0f}, cast u{m['u']:+.1f} v{m['v']:+.1f}")
        print(f"Grade '{preset}': {filt}")
        print(f"Before (left) / after (right): {out}")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
