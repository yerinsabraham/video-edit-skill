# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Ground rules

- Keep it local-first: no feature may upload footage, transcripts, faces, or
  voices, or require a paid API.
- Original work only. Do not copy code, prose, templates, or look values from
  other projects unless their licence allows it, and credit them when it does.
- The agent plans; scripts do the media work. New behaviour belongs in a
  script with a `--help`, documented in `shared/references/workflow.md`.
- New creative defaults go in `shared/references/editing-rules.md` and, where
  they can be automated, in `autoedit.py`.
- UI templates meet the realism standard in `editing-rules.md` and pass
  `npx hyperframes check`.

## Before a pull request

```bash
python3 -m py_compile shared/scripts/*.py
python3 shared/scripts/proof.py
python3 install.py --target both --home /tmp/video-edit-home
```

CI runs the same on Python 3.10 and 3.12. Do not commit footage, renders, or
project folders.

## Layout

- `skills/video-edit/SKILL.md`: the skill entrypoint (plugin and installs).
- `shared/scripts/`: the tools. `shared/references/`: guidance the agent reads.
- `shared/assets/`: looks, fonts (OFL), HyperFrames motion templates.
- `codex/agents/openai.yaml`: Codex metadata. `.claude-plugin/`: plugin manifests.
