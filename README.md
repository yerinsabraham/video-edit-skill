# Video Edit Skill

[![ci](https://github.com/yerinsabraham/video-edit-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/yerinsabraham/video-edit-skill/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Local-first video editing skill for Claude Code and Codex.

Turn raw vertical talking-head clips into a captioned short-form video with a
deterministic pipeline: ingest, transcribe, create an EDL, validate a recipe,
assemble with ffmpeg, render captions, run QA, and export captions/NLE handoff
files.

The core idea is simple: let the agent plan and review, while deterministic
local scripts do the media work. Source files are never modified, and raw media
is not uploaded by default.

## Status

Usable local proof pipeline:

- Local ingest and media probing
- Local transcription with whisper.cpp word timings (openai-whisper fallback,
  placeholder mode for tests)
- Transcript cleanup: Whisper artefacts, split words, per-project corrections,
  and a review of on-camera promises
- Editorial analysis for fillers, gaps, repeats, and speech rate
- EDL and validated recipe files
- ffmpeg assembly and render
- Sidecar captions: JSON, SRT, VTT
- Snapshot/restore and targeted revisions
- Transcript-first filler removal
- Look presets and brand kit support
- Local title/CTA cards and still image inserts
- QA report with contact sheet, duration, stream, black-frame, freeze, and
  audio-volume checks
- Rough NLE handoff export
- Short-form kinetic captions (word-lit, punch colours) and long-form
  two-line captions, both from the playbook rules
- Chapters for long-form edits
- Optional motion graphics with HyperFrames: stat bars, callouts, lower thirds,
  big text, and framed media pop-ins
- Asks for real media: suggests moments for screenshots and clips, then places
  them as corner pop-ins, split screen, or full-screen B-roll, clear of the face
- Text behind the speaker and face-aware placement (Apple Vision, macOS)
- Colour grading: natural grade judged on the face, presets, LUTs, or match a still
- Reference-video analysis: pacing, cuts, look, and loudness to match

Deferred: privacy sweep for screen recordings, hosted UI, generated B-roll,
and background cutout. See `docs/phase-plan.md`.

## Why

Most agent video workflows fail in one of two ways: the agent invents brittle
ffmpeg commands, or a black-box service makes a video that is hard to inspect
and revise. This skill keeps the edit as files you can review:

- `media.json`
- `transcript.json`
- `analysis.json`
- `edl.json`
- `recipe.json`
- `state.json`
- `qa/report.md`

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe`
- ffmpeg with libass for burned-in captions (Homebrew's default `ffmpeg` lacks
  it; see `shared/references/troubleshooting.md`)
- Recommended: whisper.cpp (`whisper-cli`) and the `small.en` model
  (`python3 shared/scripts/setup.py --download-model`)
- Optional: Node.js 22+ for HyperFrames motion graphics

Install ffmpeg on macOS:

```bash
brew install ffmpeg
```

## Quick Start

From this repository:

```bash
python3 shared/scripts/setup.py
python3 shared/scripts/ingest.py ~/video-edit-demo ~/Downloads/my-clips --title "Demo edit"
python3 shared/scripts/transcribe.py ~/video-edit-demo   # then read qa/transcript-review.md
python3 shared/scripts/analyze.py ~/video-edit-demo
python3 shared/scripts/edl.py ~/video-edit-demo --last-repeat
python3 shared/scripts/card.py ~/video-edit-demo --title "My Reel" --subtitle "Edited locally" --position start
python3 shared/scripts/recipe.py ~/video-edit-demo --name v1
python3 shared/scripts/apply_look.py ~/video-edit-demo clean-creator
python3 shared/scripts/validate_recipe.py ~/video-edit-demo
python3 shared/scripts/assemble.py ~/video-edit-demo
python3 shared/scripts/render.py ~/video-edit-demo --review
python3 shared/scripts/qa.py ~/video-edit-demo --render ~/video-edit-demo/renders/v1-review.mp4
```

Render final:

```bash
python3 shared/scripts/render.py ~/video-edit-demo
python3 shared/scripts/qa.py ~/video-edit-demo
python3 shared/scripts/export_nle.py ~/video-edit-demo
```

Outputs live in the project folder, not in the skill folder.

## Revisions

Create a targeted v2 without losing v1:

```bash
python3 shared/scripts/revise.py ~/video-edit-demo --name v2 --trim-start s1 0.2 --note "tighten opening"
python3 shared/scripts/validate_recipe.py ~/video-edit-demo
python3 shared/scripts/assemble.py ~/video-edit-demo
python3 shared/scripts/render.py ~/video-edit-demo --review
```

Inspect or restore state:

```bash
python3 shared/scripts/state.py ~/video-edit-demo list
python3 shared/scripts/state.py ~/video-edit-demo restore v1
```

Transcript-first filler removal:

```bash
python3 shared/scripts/transcript_edit.py ~/video-edit-demo --name v2 --remove-fillers --note "remove fillers"
python3 shared/scripts/validate_recipe.py ~/video-edit-demo
python3 shared/scripts/assemble.py ~/video-edit-demo
python3 shared/scripts/render.py ~/video-edit-demo --review
```

Brand kit and looks:

```bash
python3 shared/scripts/brand.py ~/video-edit-demo --name "My Course" --primary "#2563eb" --accent "#22c55e"
python3 shared/scripts/apply_look.py ~/video-edit-demo course-promo --name v2
```

Image or screenshot insert:

```bash
python3 shared/scripts/insert_image.py ~/video-edit-demo ~/Desktop/screenshot.png --position end --duration 2 --label "Product screen"
python3 shared/scripts/recipe.py ~/video-edit-demo --name v3
```

Fix misheard names, then rebuild the clean transcript from the raw one:

```bash
# edit ~/video-edit-demo/corrections.json
python3 shared/scripts/fix_transcript.py ~/video-edit-demo
```

Motion graphics, only where they earn their place (a number, a promise, a name):

```bash
python3 shared/scripts/motion.py ~/video-edit-demo --list
python3 shared/scripts/motion.py ~/video-edit-demo stat --duration 3 \
  --var 'value=$12,000' --var 'label=a year for an editor' --var percent=80 --start 2.8
python3 shared/scripts/render.py ~/video-edit-demo --frame 3.5   # look at qa/frame.jpg first
```

A static PNG works without Node:

```bash
python3 shared/scripts/overlay.py ~/video-edit-demo add ~/Desktop/link.png --start 5 --end 9
```

Real media, colour, and a reference look:

```bash
python3 shared/scripts/assets.py ~/video-edit-demo suggest          # see qa/asset-requests.md
python3 shared/scripts/assets.py ~/video-edit-demo provide A1 ~/Desktop/post1.png ~/Desktop/post2.png
python3 shared/scripts/assets.py ~/video-edit-demo apply
python3 shared/scripts/grade.py ~/video-edit-demo                   # or --lut look.cube / --match still.jpg
python3 shared/scripts/analyze_reference.py ~/video-edit-demo ~/Downloads/reference.mp4
python3 shared/scripts/captions.py ~/video-edit-demo --emphasis "skill,free"
python3 shared/scripts/motion.py ~/video-edit-demo big-text --duration 2 --var "text=NO CODE" --start 20.7 --behind
```

Long-form lessons get two-line captions automatically past five minutes. Write
`chapters.json` from the transcript, then:

```bash
python3 shared/scripts/chapters.py ~/video-edit-demo
```

Run the synthetic proof test:

```bash
python3 shared/scripts/proof.py
```

Something not working? See `shared/references/troubleshooting.md`.

## Folder Map

| Path | Purpose |
| --- | --- |
| `ARCHITECTURE.md` | Review document for the build plan and phases |
| `claude/` | Claude Code skill entrypoint and packaging notes |
| `codex/` | Codex skill entrypoint and packaging notes |
| `shared/references/` | Runtime guidance used by both agents |
| `shared/scripts/` | Deterministic tooling for ingest, analysis, edit, render, revision, and QA |
| `shared/assets/` | Schemas, look presets, and HyperFrames motion templates |
| `docs/` | Design notes that support the architecture but are not runtime instructions |

## Claude and Codex

Claude and Codex have separate `SKILL.md` entrypoints so each runtime can load
the same shared scripts without drifting.

Install both locally:

```bash
python3 install.py --target both --mode symlink --force
```

Install only one runtime:

```bash
python3 install.py --target claude --mode symlink --force
python3 install.py --target codex --mode symlink --force
```

Use `--mode copy` for a self-contained install instead of symlinks.

## Repository Rules

- Author as Yerins Abraham / `yerinssaibs@gmail.com`.
- Do not add AI co-author trailers or generated-with footers.
- Do not copy unlicensed code or prose from other repositories.
- Keep raw footage and generated renders out of git.

## Roadmap

See `docs/phase-plan.md` for the full checklist. Remaining before v1.0:

1. Real-world testing on supplied talking-head footage.
2. Screenshots and a demo GIF from that run; versioned release zips.
3. v1.0 release pass: tag, GitHub release, final QA.

Production rules live in `shared/references/production-playbook.md`; the
motion renderer decision is in `docs/motion-graphics.md`.

## License

Apache-2.0. See `LICENSE` and `NOTICE`.
