# QA Reference

The render is not complete until QA has run.

Phase 1 checks:

- Render exists and is non-empty.
- Render duration is close to expected timeline duration.
- Contact sheet is created for quick visual review.
- Caption sidecars exist.
- Video stream and audio stream exist.
- Render is vertical.
- Black frames and frozen frames are flagged when ffmpeg supports the filters.
- Audio volume observations are recorded.

Manual review still matters:

- Watch the proof copy.
- Check captions for names, product terms, and timing.
- Check no caption covers the face.
- Check cuts do not feel robotic.
- Check audio is intelligible and not clipped.

If `qa.py` returns `REVIEW`, fix or explain the finding before delivering.
