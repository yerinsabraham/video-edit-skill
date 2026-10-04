# Contributing

Keep contributions focused on the local-first video editing workflow.

## Rules

- Do not add AI co-author trailers, generated-with footers, or bot contributor
  metadata.
- Do not add paid API dependencies to the core path.
- Do not upload user media by default.
- Do not copy unlicensed code, templates, or prose from other repositories.
- Keep installable skill packages lean: `SKILL.md`, `agents/openai.yaml` where
  needed, and shared resources only.

## Before a Pull Request

- Run `python3 shared/scripts/setup.py`.
- Run `python3 -m py_compile shared/scripts/*.py`.
- Test the pipeline on a short local clip when changing render logic.
- Update `ARCHITECTURE.md` when changing phases or core design.
