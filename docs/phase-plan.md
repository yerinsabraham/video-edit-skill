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

### Phase 7b: Creator feedback on the first real clip (2026-10-04)

- [x] Captions wait for speech after a pause: `align.py` re-times Whisper words
      onto the speech actually present in the audio (silences are reliable,
      Whisper's word times drift up to a second around pauses).
- [x] Pause handling in the edit: pauses over 0.5 s become cuts; `--keep-pauses`
      for footage that is already edited.
- [x] Captions that are not basic: Anton display font (OFL, bundled), words
      appear as spoken with a bounce, key words get their own big tilted card
      that lingers above the running captions (`captions.py --emphasis`).
- [x] The skill asks for real media: `assets.py suggest` finds moments
      ("everyone is talking about...", "something like this", how-to steps) and
      asks for screenshots/clips; `provide`/`skip`/`apply`.
- [x] Layouts: `pop` framed cards placed around the face, `split` speaker on one
      half and media on the other, `cover` full-frame B-roll.
- [x] Face detection and person masks with Apple Vision (`vision.py`, macOS):
      graphics clear the face wherever it moves during their window.
- [x] Text behind the person: `motion.py big-text --behind` (any overlay can be
      marked behind).
- [x] Colour grade: `grade.py` natural grade judged on the face (never darkens a
      bright room), presets, `--lut`, `--match <still>`; before/after still.
- [x] Reference video analysis: cuts, pacing, contact sheets, colour, loudness,
      and a map from what the reference does to the skill's tools.
- [x] Intake questions in `SKILL.md`: raw or edited, reference, brand, colour.

### Phase 7c: Default style from a reference edit (2026-10-04)

- [x] `shared/references/editing-rules.md`: the default creative rules, modelled
      on a high-performing creator edit, applied without being asked.
- [x] `autoedit.py`: plans and builds the beats (hook word behind the speaker,
      logos on product names, code window on "skill", UI demo on a described
      workflow, comment sheet on a CTA, claims behind the speaker, stats, zooms
      every few seconds); `--plan`, `--skip`, `--only`; manual items untouched.
- [x] Zooms: punch-ins and push-ins centred on the face (`recipe.zooms`).
- [x] Templates: `app-demo` (cursor drag, typing, checklist), `code-window`,
      `social-cta`, `logo-pop`; each with sound cues.
- [x] Sound: synthesized SFX library, auto cues, optional ducked music, voice
      clean-up, -14/-16 LUFS loudness (`sound.py`).
- [x] `creator-pro` look: small lowercase mid-frame captions, bold yellow key
      words, elegant italic serif feeling words; captions move to the top when a
      graphic covers the middle.
- [x] Logos fetched per project from Simple Icons, never bundled (`logos.py`).

### Phase 7d: Owner review round 2 (2026-10-04)

- [x] `cut.py`: remove a spoken line and shift every later item to stay in sync.
- [x] "Something like this" with no example footage: the video shrinks into a
      phone labelled "this video" (`phone-frame`, `render.py` phone layout);
      the second "or something like this" is cut.
- [x] UI realism standard in the rules; `app-demo` rebuilt (window controls,
      sidebar with recents and user, file chips with sizes, skill suggestion,
      conversation with the skill running, camera follow) and `social-cta`
      rebuilt (pinned author comment, keyword comments with likes, emoji bar,
      iOS keyboard with key pops).

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
- [ ] The owner's raw clips (before their own edit) end to end, plus their real
      screenshots and example videos for the asset requests.
- [ ] Two more real clips, including one with fillers, retakes, and a pause.
- [ ] Faster final renders (3 min for 36 s with five layers on an Intel Mac):
      hardware final encode option is there (`VIDEO_EDIT_HWENC=all`); consider
      pre-compositing static layers.
- [ ] Person masks on Windows/Linux (MediaPipe or a small ONNX matting model).
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
