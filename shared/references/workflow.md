# Workflow Reference

Use this workflow for a normal local edit.

## Intake

Ask only for what is missing:

- Source clip folder or files.
- Project folder.
- Target platform if not obvious.
- Desired look if not obvious.

Default to a local project folder named after the edit. Never write outputs into
the skill folder.

## Commands

Run setup first:

```bash
python3 SK/shared/scripts/setup.py
```

Create the project:

```bash
python3 SK/shared/scripts/ingest.py <project> <clips-or-folder> --title "<title>"
python3 SK/shared/scripts/transcribe.py <project> --allow-empty
python3 SK/shared/scripts/edl.py <project>
python3 SK/shared/scripts/plan.py <project>
python3 SK/shared/scripts/recipe.py <project> --name v1
python3 SK/shared/scripts/validate_recipe.py <project>
```

Build a proof:

```bash
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/render.py <project> --review
python3 SK/shared/scripts/qa.py <project> --render <project>/renders/v1-review.mp4
```

Build final after review:

```bash
python3 SK/shared/scripts/render.py <project>
python3 SK/shared/scripts/qa.py <project>
python3 SK/shared/scripts/export_nle.py <project>
```

## Output Files

- `renders/v1-review.mp4`: smaller proof copy.
- `renders/v1.mp4`: final render.
- `exports/v1.srt`, `exports/v1.vtt`, `exports/v1.captions.json`: captions.
- `exports/v1.edl.txt`: rough NLE handoff.
- `qa/report.md`: automated QA.

## Stop Conditions

Stop and ask before:

- Uploading media or transcript data.
- Calling a paid API.
- Running a long render after a review copy has not been approved.
- Deleting or overwriting source media.
