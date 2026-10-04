# Workflow Reference

`SK` is the skill folder. Normally one command does everything:

```bash
python3 SK/shared/scripts/edit.py --clips 5 --title "<title>"
```

This page is for running or adjusting individual steps.

## Setup

```bash
python3 SK/shared/scripts/setup.py              # what is installed
python3 SK/shared/scripts/setup.py --install    # install what is missing
python3 SK/shared/scripts/prefs.py show         # saved name, handle, look, folders
python3 SK/shared/scripts/prefs.py set name="..." handle=... look=bold clips=~/Downloads
```

## The pipeline, step by step

```bash
python3 SK/shared/scripts/ingest.py <p> <clips-or-folder> --title "<title>"
python3 SK/shared/scripts/transcribe.py <p>           # whisper.cpp, aligned, cleaned
python3 SK/shared/scripts/takes.py <p>                # best take of every line -> edl.json
python3 SK/shared/scripts/recipe.py <p> --name v1
python3 SK/shared/scripts/apply_look.py <p> bold
python3 SK/shared/scripts/validate_recipe.py <p>
python3 SK/shared/scripts/assemble.py <p>
python3 SK/shared/scripts/assets.py <p> suggest       # media to ask the user for
python3 SK/shared/scripts/autoedit.py <p> --plan      # read qa/edit-plan.md
python3 SK/shared/scripts/autoedit.py <p>             # build the beats
python3 SK/shared/scripts/render.py <p> --frame 3.0   # one composited still
python3 SK/shared/scripts/render.py <p> --review
python3 SK/shared/scripts/qa.py <p> --render <p>/renders/v1-review.mp4
python3 SK/shared/scripts/render.py <p>               # final
```

Already-edited footage: `edl.py <p> --last-repeat --keep-pauses` instead of
`takes.py`. Resume any run with `edit.py --project <p> --from <step>`.

## Every tool

| Script | What it does |
| --- | --- |
| `edit.py` | The whole pipeline in one command; resumable |
| `setup.py` | Check tools; `--install` installs them; `--download-model` |
| `prefs.py` | The creator's saved preferences |
| `ingest.py` | Project folder, media probe, contact sheets |
| `transcribe.py` | whisper.cpp (or openai-whisper), alignment, cleanup; `--import` |
| `fix_transcript.py` | Re-apply `corrections.json`; writes `qa/transcript-review.md` |
| `takes.py` | Best take per line; `--use L3=m2`, `--drop L5` |
| `edl.py` | First-pass EDL from transcript segments (no take selection) |
| `transcript_edit.py` | Remove fillers or words from the EDL |
| `analyze.py` | Filler, gap, repeat, and speech-rate signals |
| `recipe.py` | Render recipe from the EDL (keeps creative settings) |
| `apply_look.py`, `brand.py` | Looks and brand kit |
| `assemble.py` | Cut the A-roll from the originals at native resolution |
| `autoedit.py` | Apply the editing rules: `--plan`, `--skip`, `--rebuild`, `--section`, `--only` |
| `motion.py` | Render a HyperFrames template (`--list`) with alpha |
| `overlay.py` | Place a PNG or alpha video; `--behind` puts it behind the person |
| `assets.py` | Ask for real media, attach files (`--credit @handle`), place them |
| `logos.py` | Fetch a product logo into the project |
| `instagram.py` | Optional: reels and profile stats via Apify |
| `vision.py` | Face boxes and person masks (Apple Vision or MediaPipe) |
| `captions.py` | Captions; `--emphasis`, `--elegant`, `--size`, `--position`, `--mode` |
| `captions_ass.py` | The burn-in ASS file (per-look styles) |
| `grade.py` | Natural grade, `--preset`, `--lut`, `--match` |
| `sound.py` | SFX cues, music bed, loudness |
| `cut.py` | Remove a line, or tighten a pause, keeping everything in sync |
| `revise.py`, `state.py` | Trim segments; snapshots and restore |
| `card.py`, `insert_image.py` | Title/CTA cards and still inserts |
| `render.py` | Review and final renders; `--frame` |
| `qa.py` | Automated checks; `qa/report.md`, `qa/cuts.jpg` |
| `chapters.py` | Long-form chapters (VTT and description text) |
| `analyze_reference.py` | Study a video the user wants to match |
| `export_nle.py` | Rough EDL handoff |
| `proof.py` | The synthetic end-to-end test |
| `align.py`, `vision_mp.py`, `_common.py` | Internal modules |

## Output files

- `renders/v1-review.mp4`: fast full-resolution preview. `renders/v1.mp4`: final.
- `exports/v1.srt`, `.vtt`, `.captions.json`, `.ass`: captions.
- `qa/report.md`, `qa/cuts.jpg`, `qa/frame.jpg`: checks.
- `qa/takes.md`, `qa/edit-plan.md`, `qa/asset-requests.md`, `qa/transcript-review.md`.
- `transcript.raw.json` (engine output), `transcript.json` (cleaned), `corrections.json`.
- `work/aroll.mp4`, `work/motion/`, `work/masks/`, `work/faces.json`, `work/instagram/`.
- `versions/`: every snapshot. `summary.json`: the last `edit.py` result.

## Stop conditions

Ask before: installing tools; the first motion render (downloads HyperFrames);
using Apify; delivering a screen recording without the privacy sweep in the
production playbook; deleting or overwriting anything the user made.
