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
python3 SK/shared/scripts/transcript_edit.py <project> --name v4 --remove-fillers
python3 SK/shared/scripts/state.py <project> restore v1
```

## Notes, mapped to tools

| Note | Tool |
| --- | --- |
| captions bigger / smaller / higher | `captions.py --size 1.2` / `--size 0.85` / `--position top` |
| cut a line | `cut.py --text "..."` |
| cut a pause | `cut.py --pause-before "..."` / `--pause-after "..."` |
| a different take | `takes.py --use L3=m2` |
| move a line / reorder clips | `takes.py --move L7=end`, `--clips m2,m1,m3`, `--order L1,L4,L2` |
| remove or redo a graphic | `autoedit.py --skip <id>` / `--rebuild <id>` |
| different look for a section | `autoedit.py --section "soft:phrase"` |
| warmer, cooler, like this photo | `grade.py --preset warm` / `--match still.jpg` |
| go back | `state.py list`, `state.py restore <name>` |

Resume the pipeline from the earliest affected step with
`edit.py --project <p> --from <step>`.
