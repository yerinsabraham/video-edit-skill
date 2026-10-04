# Claude Install Plan

For local development from this repository:

```bash
python3 install.py --target claude --mode symlink --force
```

For a lean install package, copy:

- `SKILL.md`
- `shared/references/`
- `shared/scripts/`
- `shared/assets/`

Then run:

```bash
python3 ~/.claude/skills/video-edit/shared/scripts/setup.py
```

Do not publish or push until reviewed.
