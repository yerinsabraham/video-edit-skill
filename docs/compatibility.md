# Agent Compatibility

One shared runtime (`shared/`), one skill entrypoint
(`skills/video-edit/SKILL.md`).

| Agent | Install | Invoke |
| --- | --- | --- |
| Claude Code (plugin) | `/plugin marketplace add yerinsabraham/video-edit-skill`, then `/plugin install video-edit@video-edit-skill` | `/video-edit:video-edit ...` or plain words |
| Claude Code (copy) | `python3 install.py --target claude` → `~/.claude/skills/video-edit` | `/video-edit ...` or plain words |
| Codex | `python3 install.py --target codex` → `~/.codex/skills/video-edit` (with `agents/openai.yaml`) | ask Codex to edit your clips |

The plugin entrypoint refers to scripts through `${CLAUDE_PLUGIN_ROOT}`;
`install.py` writes a copy with that variable replaced by the install folder.
Both agents run the same scripts and read the same references.
