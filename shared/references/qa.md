# QA Reference

The render is not complete until QA has run.

Automated checks:

- Render exists and is non-empty.
- Render duration is close to expected timeline duration.
- Contact sheet is created for quick visual review.
- Caption sidecars exist.
- Video stream and audio stream exist.
- Render is vertical.
- Black frames and frozen frames are flagged when ffmpeg supports the filters.
- Audio volume observations are recorded.
- Video and audio stream durations agree within 0.1 s.
- The render decodes end to end without errors (skip with `--fast`).
- Captions were actually burned in (the ffmpeg has libass).
- Caption rules hold: no punctuation-only cards; short-form cards at most 20
  characters and held at least 0.34 s; long-form cues at most 84 characters
  on two lines.
- On-camera promises from `qa/transcript-review.md` are listed for review.

`render.py` also refuses to render a stale assembly (recipe changed since
`assemble.py`).

Manual review still matters:

- Watch the proof copy.
- Check captions for names, product terms, and timing.
- Check no caption or graphic covers the face (`render.py --frame <t>`).
- Check cuts do not feel robotic.
- Check audio is intelligible and not clipped.

If `qa.py` returns `REVIEW`, fix or explain the finding before delivering.
