# Video Edit

Local-first video editing skill for Claude Code and Codex.

Turn raw vertical talking-head clips into a captioned short-form video with a
deterministic pipeline: ingest, transcribe, create an EDL, validate a recipe,
assemble with ffmpeg, render captions, run QA, and export captions/NLE handoff
files.

This is a clean-room open-source package. It is inspired by the category of
agentic video-editing tools, not copied from any existing skill.

## Status

Phase 1 and the first revision-safety tools are usable locally. Advanced
motion graphics, background cutout, generated B-roll, and hosted UI are
intentionally deferred.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe`
- Optional: Whisper CLI for real transcription

Install ffmpeg on macOS:

```bash
brew install ffmpeg
```

## Quick Start

From this repository:

```bash
python3 shared/scripts/setup.py
python3 shared/scripts/ingest.py ~/video-edit-demo ~/Downloads/my-clips --title "Demo edit"
python3 shared/scripts/transcribe.py ~/video-edit-demo --allow-empty
python3 shared/scripts/analyze.py ~/video-edit-demo
python3 shared/scripts/edl.py ~/video-edit-demo
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

## Folder Map

| Path | Purpose |
| --- | --- |
| `ARCHITECTURE.md` | Review document for the build plan and phases |
| `claude/` | Claude Code skill entrypoint and packaging notes |
| `codex/` | Codex skill entrypoint and packaging notes |
| `shared/references/` | Runtime guidance used by both agents |
| `shared/scripts/` | Deterministic tooling for ingest, analysis, edit, render, revision, and QA |
| `shared/assets/` | Schemas, look presets, and future templates/fonts/SFX manifests |
| `docs/` | Design notes that support the architecture but are not runtime instructions |

## Claude and Codex

Claude and Codex have separate `SKILL.md` entrypoints so each runtime can load
the same shared scripts without drifting.

Manual symlink install after review:

```bash
ln -sfn "$PWD" ~/.claude/skills/video-edit
ln -sfn "$PWD" ~/.codex/skills/video-edit
```

For a lean install package, copy only the relevant entrypoint plus `shared/`.

## Open Source Rules

- Author as Yerins Abraham / `yerinssaibs@gmail.com`.
- Do not add AI co-author trailers or generated-with footers.
- Do not copy unlicensed code or prose from other repositories.
- Do not push to GitHub until the package is reviewed.

## License

MIT. See `LICENSE`.
