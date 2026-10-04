#!/usr/bin/env python3
"""Render review and final videos from a recipe."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _common import SkillError, ensure_project, fail, ffmpeg_filters, find_exe, h264_args, load_state, log_command, read_json, run_cmd, save_state
from captions import main as captions_main
from captions_ass import FONTS_DIR, write_ass


NO_LIBASS = (
    "WARNING: this ffmpeg has no libass, so captions are sidecar files only (not burned in). "
    "Install an ffmpeg with libass (see shared/references/troubleshooting.md) or set VIDEO_EDIT_FFMPEG."
)


def escape_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(" ", "\\ ").replace(",", "\\,")


def position(value, axis: str) -> str:
    if value in (None, "center"):
        return f"({axis.upper()}-{axis})/2"
    return str(value)


VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def layout_graph(recipe: dict, first_input: int, base: str = "0:v") -> tuple[list[str], list[str], str, int]:
    """Split-screen and full-cover layouts. Split: the speaker, cropped around the
    face, fills one half and the media fills the other. Cover: media fills the frame
    while the speaker's audio continues. Returns (inputs, parts, label, next input)."""
    width, height = int(recipe["output"]["width"]), int(recipe["output"]["height"])
    fps = int(recipe["output"]["fps"])
    inputs: list[str] = []
    parts: list[str] = []
    current = base
    idx = first_input
    for n, item in enumerate(recipe.get("layouts", [])):
        start, end = float(item["start"]), float(item["end"])
        is_video = Path(item["file"]).suffix.lower() in VIDEO_EXTS
        if is_video:
            inputs += ["-stream_loop", "-1", "-t", f"{end:.3f}", "-itsoffset", f"{start:.3f}", "-i", item["file"]]
        else:
            inputs += ["-loop", "1", "-t", f"{end:.3f}", "-i", item["file"]]
        half = height // 2
        box_h = half if item.get("type", "split") == "split" else height
        parts.append(
            f"[{idx}:v]scale={width}:{box_h}:force_original_aspect_ratio=increase,crop={width}:{box_h},fps={fps},setsar=1,format=yuv420p[lm{n}]"
        )
        if item.get("type", "split") == "split":
            focus = float(item.get("focusY", 0.37))
            y0 = int(min(max(focus * height - half * 0.42, 0), height - half))
            parts.append(f"[{current}]split=2[lb{n}][ls{n}]")
            parts.append(f"[ls{n}]crop={width}:{half}:0:{y0}[sp{n}]")
            order = f"[lm{n}][sp{n}]" if item.get("mediaSide", "top") == "top" else f"[sp{n}][lm{n}]"
            parts.append(f"{order}vstack=inputs=2[lv{n}]")
            parts.append(f"[lb{n}][lv{n}]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[lay{n}]")
        else:
            parts.append(f"[{current}][lm{n}]overlay=0:0:eof_action=pass:enable='between(t,{start:.3f},{end:.3f})'[lay{n}]")
        current = f"lay{n}"
        idx += 1
    return inputs, parts, current, idx


def behind_graph(project: Path, recipe: dict, first_input: int, base: str) -> tuple[list[str], list[str], str, int]:
    """Graphics marked behind=true sit between the background and the speaker: draw
    them on the frame, then lay a cut-out of the person (Apple Vision mask) back on
    top for the same window."""
    items = [o for o in recipe.get("overlays", []) if o.get("behind")]
    if not items:
        return [], [], base, first_input
    from vision import mask

    width, height = int(recipe["output"]["width"]), int(recipe["output"]["height"])
    sub = {**recipe, "overlays": items}
    inputs, parts, current = overlay_graph(sub, first_input, f"bk_bg", prefix="bk")
    idx = first_input + len(items)
    parts.insert(0, f"[{base}]split={len(items) + 1}[bk_bg]" + "".join(f"[bk_fg{n}]" for n in range(len(items))))
    for n, item in enumerate(items):
        start, end = float(item["start"]), float(item["end"])
        matte = mask(project, start, end)
        inputs += ["-i", str(matte)]
        # Limited-range white is 235; stretch to 255 or the background shows through.
        parts.append(f"[{idx}:v]format=gray,scale={width}:{height},lut=y='clip((val-16)*255/219,0,255)',setpts=PTS-STARTPTS[bk_m{n}]")
        parts.append(f"[bk_fg{n}]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,format=yuva420p[bk_f{n}]")
        parts.append(f"[bk_f{n}][bk_m{n}]alphamerge,setpts=PTS+{start:.3f}/TB[bk_p{n}]")
        parts.append(f"[{current}][bk_p{n}]overlay=0:0:eof_action=pass:enable='between(t,{start:.3f},{end:.3f})'[bk_o{n}]")
        current = f"bk_o{n}"
        idx += 1
    return inputs, parts, current, idx


def overlay_graph(recipe: dict, first_input: int, base: str = "0:v", prefix: str = "") -> tuple[list[str], list[str], str]:
    """Return (input args, filter parts, output label) compositing recipe overlays onto base."""
    inputs: list[str] = []
    parts: list[str] = []
    current = base
    items = recipe.get("overlays", [])
    if not prefix:
        items = [o for o in items if not o.get("behind")]
    for n, item in enumerate(items):
        idx = first_input + n
        start, end = float(item["start"]), float(item["end"])
        fade = float(item.get("fade", 0.3))
        scale = f",scale={int(item['width'])}:-1" if item.get("width") else ""
        if item.get("kind", "image") == "image":
            inputs += ["-loop", "1", "-t", f"{end:.3f}", "-i", item["file"]]
            src = f"[{idx}:v]format=rgba{scale},fade=t=in:st={start:.3f}:d={fade}:alpha=1,fade=t=out:st={max(start, end - fade):.3f}:d={fade}:alpha=1[{prefix}ov{n}]"
        else:
            inputs += ["-i", item["file"]]
            src = f"[{idx}:v]format=yuva420p{scale},setpts=PTS-STARTPTS+{start:.3f}/TB[{prefix}ov{n}]"
        parts.append(src)
        x, y = position(item.get("x"), "w"), position(item.get("y", 220), "h")
        parts.append(f"[{current}][{prefix}ov{n}]overlay=x={x}:y={y}:eof_action=pass:enable='between(t,{start:.3f},{end:.3f})'[{prefix}base{n}]")
        current = f"{prefix}base{n}"
    return inputs, parts, current


def main() -> int:
    parser = argparse.ArgumentParser(description="Render captioned review/final videos.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--review", action="store_true", help="Render only the low-res review copy.")
    parser.add_argument("--frame", type=float, help="Write one composited still at this timeline second to qa/frame.jpg and stop.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        ffmpeg = find_exe("ffmpeg")
        if not ffmpeg:
            fail("ffmpeg is missing")
        recipe = read_json(project / "recipe.json")
        aroll = project / "work" / "aroll.mp4"
        if not aroll.exists():
            fail("Missing work/aroll.mp4. Run assemble.py first.")
        assembled = read_json(project / "segments.json", {"segments": []})["segments"]
        key = lambda segs: [(s.get("clip"), float(s["in"]), float(s["out"])) for s in segs]
        if key(assembled) != key(recipe["segments"]):
            fail("work/aroll.mp4 is stale: recipe.json changed since the last assemble. Run assemble.py first.")

        old_argv = sys.argv
        sys.argv = ["captions.py", str(project)]
        try:
            captions_main()
        finally:
            sys.argv = old_argv

        filters = ffmpeg_filters(ffmpeg)
        burn = recipe.get("captions", {}).get("burnIn", True)
        if burn and "ass" in filters:
            ass = write_ass(project)
            caption_filter = f"ass=filename={escape_filter_path(ass)}:fontsdir={escape_filter_path(FONTS_DIR)}"
            caption_detail = "burned-in kinetic captions (libass)"
        elif burn and "subtitles" in filters:
            caption_filter = f"subtitles=filename={escape_filter_path(project / recipe['captions']['srt'])}"
            caption_detail = "burned-in captions (subtitles)"
        else:
            caption_filter = ""
            caption_detail = "sidecar captions only" + ("" if not burn else "; ffmpeg lacks libass")
            if burn:
                print(NO_LIBASS, file=sys.stderr)

        # The grade touches only the footage, before any graphics or captions.
        grade_parts = [f"[0:v]{recipe['grade']['filter']}[graded]"] if recipe.get("grade", {}).get("filter") else []
        layout_inputs, layout_parts, base_label, next_input = layout_graph(recipe, 1, "graded" if grade_parts else "0:v")
        behind_inputs, behind_parts, base_label, next_input = behind_graph(project, recipe, next_input, base_label)
        overlay_inputs, parts, label = overlay_graph(recipe, next_input, base_label)
        parts = grade_parts + layout_parts + behind_parts + parts
        overlay_inputs = layout_inputs + behind_inputs + overlay_inputs
        chain = f"[{label}]" + (caption_filter if caption_filter else "null")

        def graph(tail: str) -> str:
            return ";".join(parts + [f"{chain}{tail}[out]"])

        base_cmd = [ffmpeg, "-y", "-hide_banner", "-i", str(aroll), *overlay_inputs]
        fps = int(recipe["output"]["fps"])
        long_form = read_json(project / recipe["captions"]["json"], {}).get("mode") == "long"

        if args.frame is not None:
            frame_out = project / "qa" / "frame.jpg"
            cmd = base_cmd + ["-filter_complex", graph(""), "-map", "[out]", "-ss", f"{args.frame:.3f}", "-frames:v", "1", str(frame_out)]
            run_cmd(cmd, capture=True)
            print(f"Wrote {frame_out}. Look at it before rendering: no caption or graphic over the face.")
            return 0

        review_out = project / recipe["output"]["review"]
        review_cmd = base_cmd + [
            "-filter_complex", graph(""),
            "-map", "[out]", "-map", "0:a?",
            *h264_args(ffmpeg, "review"),
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(review_out),
        ]
        review_out.parent.mkdir(parents=True, exist_ok=True)
        run_cmd(review_cmd, capture=True)
        log_command(project, "render-review", review_cmd, "ok", caption_detail)

        if not args.review:
            final_out = project / recipe["output"]["final"]
            # Long-form: CRF 21 and a 2 s GOP keep screen text sharp at a size mobile viewers can stream.
            video = h264_args(ffmpeg, "final")
            if long_form and "libx264" in video:
                video[video.index("-crf") + 1] = "21"
            if long_form:
                video += ["-g", str(fps * 2)]
            final_cmd = base_cmd + [
                "-filter_complex", graph(""),
                "-map", "[out]", "-map", "0:a?",
                *video,
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                str(final_out),
            ]
            run_cmd(final_cmd, capture=True)
            log_command(project, "render-final", final_cmd, "ok", caption_detail)
            state = load_state(project)
            state.setdefault("renders", []).append(
                {
                    "name": recipe["name"],
                    "review": recipe["output"]["review"],
                    "final": recipe["output"]["final"],
                    "captionMode": caption_detail,
                }
            )
            save_state(project, state)
            print(f"Wrote {review_out} and {final_out} ({caption_detail})")
        else:
            print(f"Wrote {review_out} ({caption_detail})")
        return 0
    except SkillError as exc:
        fail(str(exc))
    except subprocess.CalledProcessError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
