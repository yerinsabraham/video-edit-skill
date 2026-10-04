#!/usr/bin/env python3
"""Study a reference video ("make mine look like this") so the agent can match it.

The agent cannot watch video, but it can read images and numbers. This extracts:

- pacing: scene cuts, cuts per minute, average shot length
- a contact sheet at every cut (what the edit does visually) and an even sheet
  over the whole video (caption style, graphics, layouts)
- colour and brightness stats plus a representative still for grade.py --match
- loudness, and words per minute if a transcription engine is available

Writes work/reference/ and work/reference/reference.md. The agent then views the
sheets and maps what it sees onto looks, captions, motion.py, assets.py layouts,
and grade.py.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import SkillError, ensure_project, fail, find_exe, media_info, run_cmd, write_json


def cuts(ffmpeg: str, ref: Path, threshold: float) -> list[float]:
    result = run_cmd(
        [ffmpeg, "-hide_banner", "-i", str(ref), "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"],
        check=False,
    )
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", result.stderr or "")]


def sheet(ffmpeg: str, ref: Path, times: list[float], out: Path, cols: int = 6) -> None:
    times = times[:30]
    if not times:
        return
    rows = (len(times) + cols - 1) // cols
    expr = "+".join(f"between(t,{t:.2f},{t + 0.04:.2f})" for t in times)
    run_cmd(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(ref), "-vf",
         f"select='{expr}',scale=240:-2,tile={cols}x{rows}:padding=4:color=white", "-fps_mode", "vfr", "-frames:v", "1", str(out)],
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse a reference video for pacing, look, and style.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("reference", help="Reference video path.")
    parser.add_argument("--threshold", type=float, default=0.32, help="Scene-cut sensitivity (lower finds more cuts).")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        ref = Path(args.reference).expanduser().resolve()
        if not ref.exists():
            fail(f"Reference not found: {ref}")
        ffmpeg = find_exe("ffmpeg")
        if not ffmpeg:
            fail("ffmpeg is missing")
        out = project / "work" / "reference"
        out.mkdir(parents=True, exist_ok=True)
        info = media_info(ref, "reference")
        duration = float(info["duration"] or 0)

        cut_times = cuts(ffmpeg, ref, args.threshold)
        shots = [b - a for a, b in zip([0.0] + cut_times, cut_times + [duration]) if b > a]
        sheet(ffmpeg, ref, [0.1] + [t + 0.15 for t in cut_times], out / "cuts.jpg")
        even = [duration * (i + 0.5) / 18 for i in range(18)]
        sheet(ffmpeg, ref, even, out / "overview.jpg")
        run_cmd([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{duration / 2:.2f}", "-i", str(ref), "-frames:v", "1", str(out / "still.jpg")], check=False)

        from grade import stats

        look = stats(ffmpeg, str(ref))
        loud = run_cmd([ffmpeg, "-hide_banner", "-i", str(ref), "-af", "ebur128", "-vn", "-f", "null", "-"], check=False)
        lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", loud.stderr or "")

        summary = {
            "reference": info,
            "cuts": cut_times,
            "cutsPerMinute": round(len(cut_times) / max(duration, 1) * 60, 1),
            "averageShot": round(sum(shots) / len(shots), 2) if shots else duration,
            "look": {k: round(v, 1) for k, v in look.items()},
            "loudnessLUFS": float(lufs[-1]) if lufs else None,
        }
        write_json(out / "reference.json", summary)
        lines = [
            "# Reference Analysis",
            "",
            f"Source: `{ref.name}` ({duration:.1f}s, {info['width']}x{info['height']})",
            f"Pacing: {len(cut_times)} cuts, {summary['cutsPerMinute']} per minute, average shot {summary['averageShot']}s",
            f"Look: brightness {look['luma']:.0f}/255, saturation {look['sat']:.0f}, cast u{look['u']:+.1f} v{look['v']:+.1f}",
            f"Loudness: {summary['loudnessLUFS']} LUFS" if lufs else "Loudness: unknown",
            "",
            "## View these images, then decide",
            "",
            "- `work/reference/cuts.jpg`: one frame after every cut. What changes at each cut: zoom, B-roll, split screen, graphic?",
            "- `work/reference/overview.jpg`: frames across the whole video. Caption font, size, colour, position, words per card, emphasis style; where graphics sit.",
            "- `work/reference/still.jpg`: use with `grade.py <project> --match work/reference/still.jpg` to borrow its colour.",
            "",
            "## Map what you see onto this skill",
            "",
            "| Reference does | Use |",
            "| --- | --- |",
            "| Big single-word captions | `captions.py --emphasis` with the key words |",
            "| Screenshots / clips popping in | `assets.py` pop layout |",
            "| Half speaker, half visual | `assets.py` split layout |",
            "| Full-screen B-roll | `assets.py` cover layout |",
            "| Text behind the person | `motion.py big-text --behind` |",
            "| Numbers animated | `motion.py stat` |",
            "| Fast cuts (over ~20/min) | `edl.py --max-pause 0.3`; tighter takes |",
            "| Particular colour | `grade.py --match work/reference/still.jpg` |",
            "",
            "Do not copy the reference's content, branding, or footage; borrow its pacing and style.",
        ]
        (out / "reference.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {out / 'reference.md'}: {len(cut_times)} cuts ({summary['cutsPerMinute']}/min). View cuts.jpg and overview.jpg.")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
