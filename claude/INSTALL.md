# Claude Install Plan

For local development from this repository, symlink the package:

```bash
ln -sfn /path/to/video-edit ~/.claude/skills/video-edit
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
