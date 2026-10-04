# Architecture

How the skill is built and why. For using it, see the README; for every tool,
`shared/references/workflow.md`.

## Principle

The agent plans, explains, and takes notes. Deterministic Python scripts do the
media work with ffmpeg, and every step writes a file the agent (and you) can
read: `transcript.json`, `takes.json`, `edl.json`, `recipe.json`,
`qa/report.md`. Nothing is a black box, every change is snapshotted, and the
original clips are never modified. Nothing leaves the machine.

## Pipeline

`edit.py` runs the whole thing; each stage is also its own script.

| Stage | Script | Output |
| --- | --- | --- |
| Find clips (newest burst, by recording time) | `edit.py` | |
| Ingest, contact sheets | `ingest.py` | `media.json`, `work/sheets/` |
| Transcribe (whisper.cpp), align to speech, clean | `transcribe.py`, `align.py`, `fix_transcript.py` | `transcript.json`, `qa/transcript-review.md` |
| Best take of every line | `takes.py` | `takes.json`, `edl.json`, `qa/takes.md` |
| Recipe and look | `recipe.py`, `apply_look.py` | `recipe.json` |
| Assemble at native resolution | `assemble.py` | `work/aroll.mp4` |
| Plan and build beats (rules) | `autoedit.py`, `motion.py`, `logos.py`, `vision.py` | `qa/edit-plan.md`, `work/motion/` |
| Media requests | `assets.py` | `qa/asset-requests.md` |
| Grade, sound | `grade.py`, `sound.py` | recipe entries |
| Render | `render.py`, `captions.py`, `captions_ass.py` | `renders/`, `exports/` |
| Check | `qa.py` | `qa/report.md`, `qa/cuts.jpg` |

## Render graph

One ffmpeg filter graph per render, in this order:

1. Footage: grade, section grades, zooms (cropping the native-resolution
   assembly), scale to the output size.
2. Layouts: split screen, full cover, phone frame (the footage shrinks into a
   phone), each on a blurred backdrop.
3. Behind-the-person graphics: drawn on the frame, then a cut-out of the person
   (Apple Vision or MediaPipe mask) laid back on top.
4. Overlays: motion graphics and images.
5. Captions: an ASS file rendered by libass, one style set per look.
6. Audio: voice clean-up, synthesised SFX cues, ducked music, loudness.

## Decisions

- **libass for captions**: built into ffmpeg, deterministic, fast, and ASS has
  per-word colour, transforms, and fades. See `docs/motion-graphics.md`.
- **HyperFrames for motion graphics**: Apache-2.0 (Remotion's licence charges
  larger companies), plain HTML that agents write reliably, alpha output.
  Telemetry is disabled; the version is pinned.
- **whisper.cpp small.en**: accurate and fast on a laptop CPU. The GPU path is
  disabled on Intel Macs, where it returns garbage. Word timings drift around
  pauses, so `align.py` re-times words onto the speech found by silence
  detection.
- **Takes by clause similarity**: clips arrive out of order and lines are
  repeated; grouping similar clauses and keeping first-appearance order
  rebuilds the script without one.
- **Native-resolution assembly**: punch-ins crop real pixels from 4K sources;
  the frame is scaled to 1080x1920 last.
- **Face-aware placement**: graphics are placed around where the face is during
  their window, and QA checks it.
- **Logos fetched per project** (Simple Icons), never bundled.
- **Synthesised SFX**: no samples to license.

## Packaging

`skills/video-edit/SKILL.md` is the single entrypoint. As a Claude Code plugin
it refers to `${CLAUDE_PLUGIN_ROOT}/shared/...`; `install.py` copies `shared/`
next to a rendered copy for Claude Code or Codex, replacing that variable with
the install path. User preferences live in `~/.config/video-edit`, installed
tools in `~/.cache/video-edit`, projects in `~/Movies/Video Edit` by default.
