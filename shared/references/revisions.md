# Revisions Reference

Prefer targeted revisions over rebuilding from scratch.

Good revision notes:

- "Cut the pause before 'here is the problem'."
- "Make captions smaller."
- "Use the second take for the intro."
- "Remove the caption on the last line."
- "Render this as v2."

Current behavior:

- Use `revise.py` for timing, line, and look changes.
- Use `state.py snapshot` before manual edits.
- Re-run `validate_recipe.py`, `assemble.py`, `render.py`, and `qa.py`.
- Keep old renders in `renders/`.

Examples:

```bash
python3 SK/shared/scripts/revise.py <project> --name v2 --trim-start s1 0.2
python3 SK/shared/scripts/revise.py <project> --name v3 --line s2 "Corrected caption text"
python3 SK/shared/scripts/state.py <project> restore v1
```

Future behavior:

- Apply transcript-first delete/restore operations.
- Keep accepted and rejected QA findings in the project log.
