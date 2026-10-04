---
name: video-edit
description: "Turn raw vertical talking-head clips into a local-first finished short-form video. Use when Codex is asked to edit clips into a reel, short, TikTok, course promo, launch video, captioned talking-head edit, or rough cut. Runs deterministic scripts for ingest, transcription, EDL, recipe validation, ffmpeg assembly, captions, render, QA, and NLE handoff. Never upload raw media or use paid APIs without explicit approval."
---

# Video Edit

Use this skill to turn local footage into a captioned short-form video. Keep
the agent as planner and reviewer; the scripts do the editing.

## First Rule

Never modify source media. Work inside a project directory and write outputs to
that project. Do not upload footage, transcripts, faces, voices, or reference
videos unless the user explicitly asks for that path.

## Paths

`SK` is this skill folder. In this repository package, scripts are under
`SK/shared/scripts`. In an installed package, use the same relative path if the
shared folder is copied or symlinked beside this file.

Run scripts with the current Python:

```bash
python3 SK/shared/scripts/setup.py
```

If `python3` is unavailable, try `python`.

## Core Workflow

Read `shared/references/workflow.md` before running an edit.

Fast path:

```bash
python3 SK/shared/scripts/setup.py
python3 SK/shared/scripts/ingest.py <project> <clips-or-folder> --title "<title>"
python3 SK/shared/scripts/transcribe.py <project> --allow-empty
python3 SK/shared/scripts/analyze.py <project>
python3 SK/shared/scripts/edl.py <project> --last-repeat
python3 SK/shared/scripts/plan.py <project>
python3 SK/shared/scripts/recipe.py <project> --name v1
python3 SK/shared/scripts/apply_look.py <project> clean-creator
python3 SK/shared/scripts/validate_recipe.py <project>
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/render.py <project> --review
python3 SK/shared/scripts/qa.py <project> --render <project>/renders/v1-review.mp4
```

Render the final only after the proof looks acceptable:

```bash
python3 SK/shared/scripts/render.py <project>
python3 SK/shared/scripts/qa.py <project>
python3 SK/shared/scripts/export_nle.py <project>
```

## Revisions

Use `state.py` before risky edits and `revise.py` for targeted changes:

```bash
python3 SK/shared/scripts/state.py <project> snapshot before-v2 --note "before revision"
python3 SK/shared/scripts/revise.py <project> --name v2 --trim-start s1 0.2 --note "tighten opening"
python3 SK/shared/scripts/validate_recipe.py <project>
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/render.py <project> --review
```

Restore if needed:

```bash
python3 SK/shared/scripts/state.py <project> restore before-v2
```

For transcript-first edits:

```bash
python3 SK/shared/scripts/transcript_edit.py <project> --name v2 --remove-fillers --note "remove fillers"
python3 SK/shared/scripts/validate_recipe.py <project>
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/render.py <project> --review
```

For branded course or promo work:

```bash
python3 SK/shared/scripts/brand.py <project> --name "<brand>" --primary "#2563eb" --accent "#22c55e"
python3 SK/shared/scripts/apply_look.py <project> course-promo --name v2
```

## Review Before Delivery

Report the review copy, final render, caption sidecars, and QA report. If QA
returns `REVIEW`, say what failed and fix it before calling the edit complete.

## References

- `shared/references/workflow.md`: runtime procedure
- `shared/references/looks.md`: style presets
- `shared/references/safe-zones.md`: platform safety rules
- `shared/references/qa.md`: render checks
- `shared/references/revisions.md`: revision language
