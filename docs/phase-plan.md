# Phase Plan

Implementation checklist. `[x]` is done and covered by `proof.py` or a real
run; `[ ]` is open. Rules that drive the later phases come from
`shared/references/production-playbook.md`; each item names the section.

## Done

### Phase 0-3: Approval, local core, revision safety, agent skills

- [x] Setup, ingest, transcription adapter, EDL, recipe and validation.
- [x] ffmpeg assembly, caption sidecars (SRT, VTT, JSON), QA contact sheet.
- [x] `state.json`, `commands.jsonl`, snapshot/restore, proof renders, NLE handoff.
- [x] Claude and Codex `SKILL.md`, Codex `agents/openai.yaml`, `install.py`.

### Phase 4-5: Editorial and design quality

- [x] Filler/gap/repeat analysis and transcript-first deletion.
- [x] Look presets, brand kit, local title/CTA cards, still-image inserts.

### Phase 6: Production rules from the playbook

- [x] whisper.cpp engine with word timings (`-ml 1`), CPU fallback on Intel
      Macs and when the GPU returns nonsense (playbook §2).
- [x] `fix_transcript.py`: drop Whisper credits and trailing "you", rejoin
      split words and numbers, per-project `corrections.json`, lowercase "i"
      fixed last (§2).
- [x] `qa/transcript-review.md`: on-camera promises, meaning-inverter watch
      list, never-appear names (§2).
- [x] Filler removal only cuts "so"/"like" when Whisper marks them as asides,
      and every deleted word forces a cut with no handle overlap.
- [x] Short-form captions: 2-4 words, at most 20 characters, cut on 0.32 s
      pauses, 0.34 s minimum hold (§4).
- [x] Long-form captions: 34/80 character and 5 s flush, merge short cues,
      split past 84 characters, two balanced 42-character lines (§3).
- [x] Captions computed on the edit timeline, so intro cards shift them (§3).
- [x] `chapters.py`: snap to cues, first at 0:00, VTT plus description text,
      search-phrase title warnings (§5).
- [x] QA: video/audio durations agree, full decode, captions actually burned
      in, caption length/hold rules, stale-assembly guard in `render.py` (§7).
- [x] Long-form encode: CRF 21, 2 s GOP, `+faststart` (§7).

### Phase 7: Motion tier

Decision record: `docs/motion-graphics.md`.

- [x] Kinetic captions with libass (ASS): spoken word lit, rest dimmed, punch
      words coloured, pop-in per card. No new dependency (§4).
- [x] `overlay.py`: timed PNG or alpha-video overlays, faded by ffmpeg (§8).
- [x] `motion.py`: HyperFrames (Apache-2.0) templates rendered to ProRes 4444
      with alpha, telemetry off, version pinned (§8).
- [x] Templates: `stat` (a number), `callout` (a promise), `lower-third`.
- [x] `render.py --frame T`: one composited still to check placement (§4, §8).

## Open

### Phase 8: Real-footage validation (next)

- [x] Real speech through whisper.cpp on this machine (synthetic voice).
- [x] First real talking-head clip (36 s, iPhone, 1080x1920) end to end:
      transcribed in 17 s on CPU; found and fixed overlapping EDL handles
      (duplicated words), Codex/Claude Code mishearings, missed promises
      ("something like this", "I'll send it"); CTA callout placed above the head.
- [x] Speed: inputs seek to their cut (assembly 24 s to 11 s on the real clip);
      Apple VideoToolbox for work and review encodes (about 6x less CPU).
- [x] QA no longer flags deliberately dark title cards as black frames.
- [ ] Two more real clips, including one with fillers, retakes, and a pause.
- [ ] Loudness: normalise to about -14 LUFS for social (the real clip sat at
      -21 dB mean).
- [ ] Burned-in kinetic captions verified on an ffmpeg with libass.
- [ ] Fix whatever the real run breaks; record it in `shared/references/troubleshooting.md`.
- [ ] Face-aware caption placement: find the face band on a sample frame and
      move captions above or below it (§4). macOS Vision or OpenCV, optional.

### Phase 9: Docs and packaging

- [x] `shared/references/troubleshooting.md`.
- [ ] Screenshots and a before/after GIF from the real-footage run
      (`hyperframes render --format gif` or ffmpeg palette GIF).
- [ ] `VERSION`, `CHANGELOG.md`, installer runs `setup.py` after install.
- [ ] Release zip per agent (`video-edit-claude.zip`, `video-edit-codex.zip`).

### Phase 10: v1.0 release

- [ ] Full `RELEASING.md` checklist, tag `v1.0.0`, GitHub release with zips.
- [ ] Push only after explicit approval.

## Later (v1.x)

- [ ] Privacy sweep for screen recordings: OCR the source (Apple Vision on
      macOS, tesseract elsewhere), mask-and-blur render, then OCR the output
      until clean (§9). The largest single item; needed before any paid
      screen-share lesson ships.
- [ ] Companion document generator for teaching videos (§11).
- [ ] Publishing helpers: presigned upload, read-back verification (§10).
- [ ] Reference-video analysis beyond `analyze_reference.py`.
- [ ] Out of scope for now: hosted UI, generated B-roll, background cutout.
