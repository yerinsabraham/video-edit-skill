# Releasing

Only release after explicit approval.

## Checklist

- Confirm git identity is `yerinssaibs@gmail.com`.
- Run `python -m py_compile shared/scripts/*.py`.
- Run `python shared/scripts/setup.py`.
- Run `python shared/scripts/proof.py`.
- Run `python install.py --target both --mode copy --home /tmp/video-edit-home --force`.
- Check no generated media or project files are staged.
- Check no AI co-author or generated-with lines are in commit or release text.
- Check stray refs:

```bash
git for-each-ref --format='%(refname)' \
  | grep -v '^refs/heads/\|^refs/remotes/\|^refs/tags/'
```

Delete unexpected refs before pushing.
