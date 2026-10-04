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
python3 SK/shared/scripts/transcribe.py <project>
python3 SK/shared/scripts/analyze.py <project>
python3 SK/shared/scripts/edl.py <project> --last-repeat
python3 SK/shared/scripts/card.py <project> --title "<title>" --subtitle "<subtitle>" --position start
python3 SK/shared/scripts/plan.py <project>
python3 SK/shared/scripts/recipe.py <project> --name v1
python3 SK/shared/scripts/apply_look.py <project> clean-creator
python3 SK/shared/scripts/validate_recipe.py <project>
```

Read `transcript.json` and `qa/transcript-review.md` now. Fix misheard names in
`corrections.json` and re-run `fix_transcript.py <project>`.

Optional graphics, only where a number, promise, or name earns one:

```bash
python3 SK/shared/scripts/motion.py <project> stat --duration 3 --var 'value=<number>' --var 'label=<what>' --start <t>
python3 SK/shared/scripts/overlay.py <project> add <image.png> --start <t> --end <t2>
```

Build a proof:

```bash
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/render.py <project> --frame 2.0
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

- `renders/v1-review.mp4`: fast full-resolution preview (hardware-encoded on Macs).
- `renders/v1.mp4`: final render.
- `exports/v1.srt`, `exports/v1.vtt`, `exports/v1.captions.json`: captions.
- `exports/v1.ass`: burn-in captions (kinetic for short-form).
- `exports/v1.chapters.vtt`, `exports/v1.chapters.txt`: chapters (long-form).
- `transcript.raw.json`: untouched engine output; `transcript.json` is cleaned.
- `corrections.json`: per-project misheard-word rules.
- `qa/transcript-review.md`: promises, watch words, removed artefacts.
- `qa/frame.jpg`: one composited frame for placement review.
- `work/motion/`: HyperFrames compositions and alpha renders.
- `exports/v1.edl.txt`: rough NLE handoff.
- `qa/report.md`: automated QA.
- `analysis.json`: filler, gap, repeated-line, and speech-rate signals.
- `brand.json`: optional brand kit.
- `work/cards/`: generated local title/CTA cards.
- `work/inserts/`: copied still-image inserts.

## Stop Conditions

Stop and ask before:

- Uploading media or transcript data.
- The first `motion.py` run, which downloads HyperFrames and Chrome via npx.
- Delivering a screen recording without the playbook section 9 privacy sweep.
- Calling a paid API.
- Running a long render after a review copy has not been approved.
- Deleting or overwriting source media.
