---
name: video-edit
description: "Turn raw vertical talking-head clips into a local-first finished short-form video. Use when Codex is asked to edit clips into a reel, short, TikTok, course promo, launch video, captioned talking-head edit, rough cut, or a captioned long-form lesson with chapters. Runs deterministic scripts for ingest, whisper.cpp transcription and cleanup, EDL, recipe validation, ffmpeg assembly, kinetic captions, optional motion graphics, render, QA, and NLE handoff. Never upload raw media or use paid APIs without explicit approval."
---

# Video Edit

Use this skill to turn local footage into a captioned video. Keep the agent as
planner and reviewer; the scripts do the editing.

Before any edit longer than a few minutes, containing a screen recording, or
going to people who paid for it, read `shared/references/production-playbook.md`.
It holds the rules the scripts cannot enforce on their own.

## First Rule

Never modify source media. Work inside a project directory and write outputs to
that project. Do not upload footage, transcripts, faces, voices, or reference
videos unless the user explicitly asks for that path.

## Paths

`SK` is this skill folder. In this repository package, scripts are under
`SK/shared/scripts`. In an installed package, use the same relative path if the
shared folder is copied or symlinked beside this file.

Run scripts with the current Python:

```bash
python3 SK/shared/scripts/setup.py
```

If `python3` is unavailable, try `python`.

## Core Workflow

Read `shared/references/workflow.md` and `shared/references/editing-rules.md`
before running an edit.

Fast path:

```bash
python3 SK/shared/scripts/setup.py
python3 SK/shared/scripts/ingest.py <project> <clips-or-folder> --title "<title>"
python3 SK/shared/scripts/transcribe.py <project>
python3 SK/shared/scripts/analyze.py <project>
python3 SK/shared/scripts/edl.py <project> --last-repeat
python3 SK/shared/scripts/card.py <project> --title "<title>" --subtitle "<subtitle>" --position start
python3 SK/shared/scripts/plan.py <project>
python3 SK/shared/scripts/recipe.py <project> --name v1
python3 SK/shared/scripts/apply_look.py <project> clean-creator
python3 SK/shared/scripts/validate_recipe.py <project>
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/grade.py <project>
python3 SK/shared/scripts/render.py <project> --frame 2.0
python3 SK/shared/scripts/render.py <project> --review
python3 SK/shared/scripts/qa.py <project> --render <project>/renders/v1-review.mp4
```

Use `--allow-empty` on `transcribe.py` only when no engine is installed and the
user accepts captions that are not from speech.

## Default Style: Apply The Editing Rules

Every short-form edit follows `shared/references/editing-rules.md` unless the
user says otherwise. Do not wait to be asked for zooms, logos, UI demos, depth
words, sound, or grade: they are the default. After the transcript, EDL and
recipe exist:

```bash
python3 SK/shared/scripts/autoedit.py <project> --plan   # read qa/edit-plan.md
python3 SK/shared/scripts/autoedit.py <project>          # build every beat
```

Tell the user what the plan contains in plain words. When they ask to remove
something, drop it for good with `autoedit.py <project> --skip <beat-id>`. Items
placed by hand (overlays, assets) are never touched by `autoedit.py`.

## Intake: Ask Before Editing

Ask these in one short message before the first command, then proceed with
defaults for anything the user skips:

1. **Raw clips or already edited?** Raw: full cutting (takes, pauses, fillers).
   Already edited: keep the cut, run `edl.py --keep-pauses`, and focus on
   captions, graphics, media, and grade.
2. **A reference video they want it to look like?** Run
   `analyze_reference.py <project> <video>`, view `work/reference/cuts.jpg` and
   `overview.jpg`, and follow `work/reference/reference.md`.
3. **Brand colours, font, or logo?** `brand.py`.
4. **Colour:** recommend the natural grade (`grade.py <project>`); offer a LUT
   they use (`--lut`) or a still whose look they like (`--match`).
5. **Music:** a track they have the rights to? It ducks under the voice
   (`sound.py <project> music <file>`). Without one, the edit uses SFX only.

## Ask For Real Media

Real screenshots and clips make the edit feel real; motion graphics alone look
generic. After the transcript is clean and `edl.py`/`recipe.py` have run:

```bash
python3 SK/shared/scripts/assets.py <project> suggest
```

Show the user the table in `qa/asset-requests.md` as plain questions, for
example: "At 0-8s you say everyone is talking about this. Do you have 2
screenshots of those posts? At 12s you say 'something like this'. Do you have
that example video?" Every item is optional. Then:

```bash
python3 SK/shared/scripts/assets.py <project> provide A1 <file> [<file2>] [--layout pop|split|cover]
python3 SK/shared/scripts/assets.py <project> skip A2
python3 SK/shared/scripts/assets.py <project> apply
```

`pop` cards are placed around the face automatically (Apple Vision on macOS);
`split` puts the speaker on one half and the media on the other; `cover` fills
the frame while the voice continues.

## Read The Transcript First

After `transcribe.py`, read `transcript.json` end to end and
`qa/transcript-review.md` before planning cuts, captions, or graphics:

- **Promises to keep**: lines like "the link is on the screen". Put it on the
  screen (see Motion Graphics), or cut the line.
- **Misheard meaning**: product names and real words that invert meaning. Add
  rules to `<project>/corrections.json`, then run `fix_transcript.py <project>`.
- **Must never appear**: names in `corrections.json` `neverAppear`.

## Captions

Pick 4-8 key words from the transcript (the claim, the product, the number,
the payoff) and give them their own big card:

```bash
python3 SK/shared/scripts/captions.py <project> --emphasis "skill,free,no code"
```

Captions are built on the edit timeline from word timings, re-timed onto the
real speech so a caption never appears during a pause. Edits up to five
minutes get short-form cards (2-4 words, spoken word lit, numbers and
`captions.punchWords` coloured); longer edits get two-line long-form cues. Force
a mode with `"captions": {"mode": "short" | "long"}` in `recipe.json`.

Before any full render, write one composited frame with `render.py --frame <t>`
and look at `qa/frame.jpg`: no caption or graphic may cross the face or the
mouth. Move captions with `captions.style.position` (`top`, `middle`,
`bottom`).

If `setup.py` says `SIDECAR ONLY`, captions will not be burned in. Tell the user
and point to `shared/references/troubleshooting.md`; do not call the edit finished.

## Motion Graphics

Only where they earn their place: a number spoken in one breath, a promise made
on camera, the speaker's name once. Nothing over mindset or story passages, and
almost nothing over screen recordings.

```bash
python3 SK/shared/scripts/motion.py <project> --list
python3 SK/shared/scripts/motion.py <project> stat --duration 3 --var 'value=$12,000' --var 'label=a year' --var percent=80 --start <t>
python3 SK/shared/scripts/motion.py <project> callout --duration 4 --var eyebrow=LINK --var text=example.com --start <t>
python3 SK/shared/scripts/overlay.py <project> add <image.png> --start <t> --end <t2>
python3 SK/shared/scripts/overlay.py <project> list
```

Text behind the speaker (macOS; uses an Apple Vision person mask), for one or
two strong moments:

```bash
python3 SK/shared/scripts/motion.py <project> big-text --duration 2 --var "text=NO CODE" --start <t> --behind
```

`motion.py` needs Node 22+ and downloads HyperFrames on first use; ask before
the first run if the user has not approved network installs. You may write a
custom HyperFrames composition folder and pass its path instead of a template
name. Media never leaves the machine.

## Long-Form Lessons

Read the playbook first. Then, after the review render:

```bash
python3 SK/shared/scripts/chapters.py <project>
```

`chapters.json` is yours to write from the transcript: one chapter every three to
five minutes, `at` in timeline seconds, and titles that name the question a
viewer would search for ("How to report a bug to the agent", not "Debugging").

Screen recordings can leak private information. There is no automated privacy
sweep yet; warn the user and follow playbook section 9 before delivering.

Render the final only after the proof looks acceptable:

```bash
python3 SK/shared/scripts/render.py <project>
python3 SK/shared/scripts/qa.py <project>
python3 SK/shared/scripts/export_nle.py <project>
```

## Revisions

Use `state.py` before risky edits and `revise.py` for targeted changes:

```bash
python3 SK/shared/scripts/state.py <project> snapshot before-v2 --note "before revision"
python3 SK/shared/scripts/revise.py <project> --name v2 --trim-start s1 0.2 --note "tighten opening"
python3 SK/shared/scripts/validate_recipe.py <project>
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/render.py <project> --review
```

Restore if needed:

```bash
python3 SK/shared/scripts/state.py <project> restore before-v2
```

For transcript-first edits:

```bash
python3 SK/shared/scripts/transcript_edit.py <project> --name v2 --remove-fillers --note "remove fillers"
python3 SK/shared/scripts/validate_recipe.py <project>
python3 SK/shared/scripts/assemble.py <project>
python3 SK/shared/scripts/render.py <project> --review
```

For branded course or promo work:

```bash
python3 SK/shared/scripts/brand.py <project> --name "<brand>" --primary "#2563eb" --accent "#22c55e"
python3 SK/shared/scripts/apply_look.py <project> course-promo --name v2
```

For still image or screenshot inserts:

```bash
python3 SK/shared/scripts/insert_image.py <project> <image> --position end --duration 2 --label "<label>"
python3 SK/shared/scripts/recipe.py <project> --name v3
```

## Review Before Delivery

Report the review copy, final render, caption sidecars, chapters if any, and QA
report. If QA returns `REVIEW`, say what failed and fix it before calling the
edit complete. Mention any on-camera promise from `qa/transcript-review.md` that
the edit does not keep.

## References

- `shared/references/editing-rules.md`: the default creative rules (read before every short-form edit)
- `shared/references/workflow.md`: runtime procedure
- `shared/references/looks.md`: style presets
- `shared/references/safe-zones.md`: platform safety rules
- `shared/references/qa.md`: render checks
- `shared/references/revisions.md`: revision language
- `shared/references/production-playbook.md`: what goes wrong in real edits (long-form lessons, transcripts, chapters, assembly, graphics, privacy sweep, publishing). Read before any edit longer than a few minutes or containing a screen recording
- `shared/references/troubleshooting.md`: missing libass, transcription engines, HyperFrames
