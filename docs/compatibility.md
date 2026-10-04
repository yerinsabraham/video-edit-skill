# Claude and Codex Compatibility

The package should keep one shared runtime and two agent-specific entrypoints.

## Claude Code

Claude Code expects a skill folder with `SKILL.md` and optional resources.
The Claude entrypoint should be installable as:

```bash
~/.claude/skills/video-edit
```

For local development, copy or symlink `claude/SKILL.md` plus `shared/` into
that target only after review.

## Codex

Codex expects a skill folder with `SKILL.md`, optional `agents/openai.yaml`,
and optional resources.

The Codex entrypoint should be installable as:

```bash
~/.codex/skills/video-edit
```

For local development, copy or symlink `codex/SKILL.md`, `codex/agents/`, and
`shared/` into that target only after review.

## Shared Runtime

Both agents should call the same scripts and read the same reference files.
Agent-specific files should explain how to invoke the runtime, not fork the
runtime behavior.
