# Phase Plan

This is the implementation checklist after architecture review.

## Phase 0: Approval

- Confirm package name.
- Confirm default output platform.
- Confirm first visual preset.
- Confirm install targets for Claude and Codex.
- Confirm whether GitHub release will be personal or Creovine-branded.

## Phase 1: Local Core

- Implement `shared/scripts/setup.py`.
- Implement `shared/scripts/ingest.py`.
- Implement transcription adapter.
- Implement JSON EDL creation.
- Implement declarative `recipe.json` creation and validation.
- Implement simple assembly and caption burn-in.
- Export sidecar captions as SRT, VTT, and JSON.
- Implement QA contact sheet and audio checks.

## Phase 2: Revision Safety

- Implement `state.json`.
- Implement `commands.jsonl`.
- Implement snapshot/restore for recipe-level changes.
- Implement low-resolution proof renders.
- Implement NLE handoff export where practical.
- Implement targeted `revise.py` timing/text/look revisions.

## Phase 3: Agent Skills

- Implement Claude `SKILL.md`.
- Implement Codex `SKILL.md`.
- Add Codex `agents/openai.yaml`.
- Validate entrypoints against the skill rules.

## Phase 4: Editorial Quality

- Add take selection heuristics.
- Add silence trimming checks.
- Add punch-in rules.
- Add targeted revision support.
- Add reference-video analysis.
- Add filler/gap/repeat analysis and transcript-first deletion.

## Phase 5: Design Quality

- Add multiple look presets.
- Add brand-kit configuration.
- Add overlay support.
- Add advanced QA checks.
- Add optional Remotion renderer for premium templates.
- Add deterministic `brand.py` and `apply_look.py` before optional motion work.

## Phase 6: Publish

- Pick license.
- Prepare repository metadata.
- Push only after explicit approval.
