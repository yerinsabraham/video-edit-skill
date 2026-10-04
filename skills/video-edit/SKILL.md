---
name: video-edit
description: "Edit raw talking-head clips into a finished, captioned short-form video, locally. Use when the user drops clips and asks for a reel, short, TikTok, promo, or edit, types /video-edit, or gives notes on an edit (captions bigger, cut a line, change the look). Picks the best take of every line, cuts, captions, motion graphics, logos, UI demos, zooms, sound, grade, and checks its own work. Also long-form lessons with chapters. Never uploads footage or uses paid APIs without asking."
argument-hint: "[what you dropped, e.g. 5 clips in my downloads]"
---

# Video Edit

You are the editor's assistant: the scripts do the media work, you plan,
explain, and take notes. The user should never need to know a command.

User request: $ARGUMENTS

`SK` below is `${CLAUDE_PLUGIN_ROOT}`. Run scripts with `python3` (on Windows: `python` or `py`).

## First Rule

Never modify, move, or delete the user's original clips. Projects live in the
user's projects folder (default `~/Movies/Video Edit` on macOS, `~/Videos/Video Edit` elsewhere). Footage, transcripts,
faces, and voices never leave the machine. The only network use is installing
tools, downloading HyperFrames on first motion render, fetching product logos,
and the optional Apify connection; ask before the first time.

## First Run (once)

If `python3 SK/shared/scripts/prefs.py show` says `"configured": false`:

1. Ask, in one short message: their name, Instagram handle, favourite look
   (bold, soft, or studio; explain in one line each, default bold), and where new
   clips land (default Downloads). Optional: an Apify token to pull their reels
   and profile stats automatically.
2. Save: `python3 SK/shared/scripts/prefs.py set name="..." handle=... look=bold clips=~/Downloads`
   (add `apifyToken=...` if given).
3. Check tools: `python3 SK/shared/scripts/setup.py`. If anything is missing, tell
   them what and ask to install it: `python3 SK/shared/scripts/setup.py --install`
   (about two minutes; anything needing admin rights is printed, not run).

## Edit (the normal case)

From the request, work out which clips ("5 clips in my downloads" means the 5
newest in their clips folder; a folder path means that folder) and any look
instructions, then run one command:

```bash
python3 SK/shared/scripts/edit.py --clips 5 --title "<short title>"
python3 SK/shared/scripts/edit.py ~/path/to/folder --title "<short title>"
python3 SK/shared/scripts/edit.py --clips 5 --section "soft:the cool aesthetic" --section "studio:after that"
```

`--section "look:phrase"` switches look from the sentence containing the phrase.
Footage that is already edited: add `--keep-pauses`. It takes several minutes;
tell the user it is running. It prints the project, the review video, and QA.

Then report in plain words, short:

- Where the review video is (offer to open it).
- The take table (`qa/takes.md`): which take it picked for repeated lines.
- The edit plan (`qa/edit-plan.md`) in one sentence ("logos on Claude Code and
  Codex, a UI demo when you describe the workflow, your comment CTA as a
  comment sheet, ...").
- Media requests (`qa/asset-requests.md`): ask for the screenshots or clips
  that would make it real ("at 0-8s you say everyone is talking about this; do
  you have two screen recordings of those posts?"). All optional.
- Anything QA flagged that you could not fix.

## Notes (each round re-renders in a couple of minutes)

Map what they say to the tool, apply, then
`python3 SK/shared/scripts/edit.py --project <p> --from <step>` (the earliest
step the change affects: `takes`, `look`, `assemble`, `autoedit`, or `render`).

| They say | Do | Resume from |
| --- | --- | --- |
| "captions bigger / smaller / higher" | `captions.py <p> --size 1.2` / `--size 0.85` / `--position top` | render |
| "make X a big word", "highlight Y" | `captions.py <p> --emphasis "x,y"` (feeling words: `--elegant`) | render |
| "cut the line where I say X" | `cut.py <p> --text "X"` | assemble |
| "cut the pause before / after X" | `cut.py <p> --pause-before "X"` / `--pause-after` | assemble |
| "use take 2 for that line" | `takes.py <p> --use L3=m2` (ids in qa/takes.md) | look |
| "remove that logo / zoom / graphic" | `autoedit.py <p> --skip <beat-id>` (ids in qa/edit-plan.md) | autoedit |
| "redo the comment section" | `autoedit.py <p> --rebuild <beat-id>` | render |
| "soft look when I say X" | `edit.py --project <p> --from autoedit --section "soft:X"` | (included) |
| "here are the screenshots" | `assets.py <p> provide A1 <files> [--credit @creator]`, then `assets.py <p> apply` | render |
| "warmer / like this photo" | `grade.py <p> --preset warm` / `--match <still>` | render |
| "add music" | `sound.py <p> music <file>` (it ducks under the voice) | render |
| "go back to the last version" | `state.py <p> list`, `state.py <p> restore <name>` | assemble |

Every change is snapshotted; nothing is lost. When they are happy:
`python3 SK/shared/scripts/render.py <p>` for the final, then `qa.py <p>`.

## What it does without being asked

Follow `SK/shared/references/editing-rules.md`. In short: never cover the face;
fix the transcript (product names like Claude, ChatGPT, Codex); credit other
creators with their @handle whenever their posts appear; keep sound effects well
under the voice; something changes every few seconds; show, don't only say
(logos, UI demos with a moving cursor, the file being discussed, the comment or
follow CTA as a real-looking phone screen); and check its own work (safe zones,
every cut, face clearance, loudness) before showing anything.

## Looks

- **bold** (default): kinetic lowercase words, the big ones behind your head,
  punch words in yellow, punch-ins.
- **soft**: warm grade, calm text, one punch line in yellow serif italic with
  sparkles; signature: your own reels orbit around you (`instagram.py <p> reels`
  with Apify, or drop reel files in `<p>/work/instagram/reels/`).
- **studio**: dark editorial, the room falls back and you stay lit, tiny spaced
  capitals plus big serif words, wide and close shots alternating.

## Advanced

The step-by-step tools (`ingest.py`, `transcribe.py`, `takes.py`, `edl.py`,
`recipe.py`, `apply_look.py`, `assemble.py`, `autoedit.py`, `motion.py`,
`overlay.py`, `assets.py`, `render.py`, `qa.py`, `chapters.py`, `export_nle.py`,
`analyze_reference.py`) are documented in `SK/shared/references/workflow.md`.
Long-form lessons and screen recordings: read
`SK/shared/references/production-playbook.md` first. A reference video the user
wants to match: `analyze_reference.py <p> <video>`, then view the sheets in
`<p>/work/reference/`.

## References

- `SK/shared/references/editing-rules.md`: the default creative rules
- `SK/shared/references/workflow.md`: every tool, step by step
- `SK/shared/references/production-playbook.md`: long-form, transcripts, privacy
- `SK/shared/references/troubleshooting.md`: missing tools, slow renders
- `SK/shared/references/looks.md`, `safe-zones.md`, `qa.md`, `revisions.md`
