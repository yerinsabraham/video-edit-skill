# Video Edit Skill Architecture

Goal: build a dual Claude Code and Codex skill that turns raw vertical
talking-head clips into finished short-form videos for Instagram Reels,
TikTok, YouTube Shorts, and course marketing.

Status: Phase 1 plus the first Phase 2 revision-safety tools are implemented.
Local scripts now cover setup, ingest, transcription, EDL, recipe validation,
assembly, captions, render, QA, rough NLE handoff, snapshots, restore, notes,
targeted EDL revisions, filler/gap/repeat analysis, and transcript-first edits.
The first design-quality tools now add look presets, brand kits, local title/CTA
cards, still-image inserts, and stronger render QA without introducing paid APIs
or heavy motion dependencies.

## Product Shape

The skill should help a creator drop raw clips into a folder and ask an agent
to make a finished reel. The agent should find the clips, understand the
spoken lines, pick the best take, remove dead air, apply a chosen look, render
captions and motion elements, check the result, and produce a phone-ready copy.

The skill must work in two agent environments:

| Environment | Entry point | Notes |
| --- | --- | --- |
| Claude Code | `claude/SKILL.md` | Claude-compatible skill package, suitable for `~/.claude/skills/video-edit` |
| Codex | `codex/SKILL.md` | Codex-compatible skill package, suitable for `~/.codex/skills/video-edit` |

Shared logic lives under `shared/` so the two entrypoints stay thin and do not
drift.

The installable skill folders should stay lean. This repository-level package
may keep `README.md`, `docs/`, and architecture notes for human review, but the
final `~/.claude/skills/video-edit` and `~/.codex/skills/video-edit` packages
should include only the relevant `SKILL.md`, `agents/openai.yaml` where needed,
and the shared `scripts/`, `references/`, and `assets/` resources.

## External Audit

I compared this plan against open-source video-editing agents, transcript
editors, programmatic video engines, and skill authoring guidance:

| Project or source | Useful pattern | Architecture change |
| --- | --- | --- |
| `browser-use/video-use` | Multi-agent install flow, one shared repo symlinked into Claude/Codex, outputs beside footage | Add source-package vs install-package split, keep generated outputs out of the skill folder |
| `AKMessi/vex` | LLM plans, deterministic tools execute; safe working copy, project state, undo/redo, export validation | Add project state layer, manifest, snapshot/restore, and recipe validation before render |
| `WizardofTryout/openmontage` | Reference-video analysis, production plan, cost/tool path before production | Add reference ingest, concept plan, estimated render cost/time, and approval gate |
| `wyattblue/auto-editor` | Tunable silence/motion cutting and NLE handoff | Add cut modes, padding/handles, and Premiere/Resolve/FCP handoff exports |
| `mifi/editly` | Declarative non-linear editing with JSON/JS specs over ffmpeg | Add a declarative render recipe and validation schema |
| `floomhq/opencut` | Timeline-as-code, Whisper word captions, Remotion rendering, asset validation | Add optional renderer tier and timeline validation before render |
| `wassgha/rescript` | Local transcript editing, word-level cut regions, speaker labels, export hub | Add transcript-first revision model, diarization path, and export formats |
| OpenAI skill guidance | Progressive disclosure, scripts/references/assets, no clutter in install package | Split human planning docs from installable skill contents |
| Reddit/video editor feedback | Users value local-first ffmpeg workflows, QA loops, and human review more than black-box AI edits | Add privacy, local-first default, QA rejection, and manual review points |

The main lesson: this should not be "an agent writing ffmpeg commands." It
should be an agent planning edits into a durable project state, then deterministic
tools render and verify the result.

## Principles From Trackline

Trackline's local repos shaped this plan in four ways:

- Keep authorship personal: package metadata and future commits must use Yerins
  Abraham / `yerinssaibs@gmail.com`, not a company identity and not an agent
  identity.
- Preserve Trackline's professional-record rule: no AI co-author trailers,
  generated-with footers, or assistant contributor metadata in any future
  commits, pull requests, docs, or package manifests.
- Scope changes tightly: skill work lives under `Skills/video-edit/` until
  explicitly installed elsewhere.
- Write short, literal instructions. The skill should say what to do and what
  must be checked, not sell the idea to the agent.
- Treat review gates as part of the product. Architecture review comes before
  implementation, and rendered video QA comes before delivery.
- Before a future publish or release session, check for stray agent refs and
  remove anything outside normal branch, remote, and tag refs.

## Non-Goals

- Do not copy source files, prose, or templates from `tenfoldmarc/video-edit-skill`.
- Do not push to GitHub in this phase.
- Do not install into Claude or Codex user skill folders in this phase.
- Do not build a hosted video editor UI yet.
- Do not rely on a paid cloud API for the core path unless the user chooses it.
- Do not make irreversible edits to source media.
- Do not upload raw footage, transcripts, faces, or voices to third-party
  services unless the user explicitly chooses that path.
- Do not pretend an automated edit is final before it has passed render QA.
- Do not make the first release depend on background cutout, complex motion
  graphics, or generative video.

## Runtime Workflow

1. Intake
   - Read user intent, target platform, desired look, clip folder, and output
     length.
   - If not specified, prefer newest vertical video files in the configured
     raw-clips folder.
   - Create a project directory outside the skill folder. Originals are read
     only; all edits use a working copy, proxy, or references to original files.
   - If a reference video or URL is supplied, analyze it for structure, pacing,
     scenes, captions, hook style, and reusable patterns before proposing an
     edit.

2. Setup Check
   - Detect OS, CPU, Python, Node, `ffmpeg`, `ffprobe`, and available
     transcription backend.
   - Write a local platform report for repeatable commands.
   - Stop with exact install instructions when a required dependency is absent.
   - Detect optional tools separately: Whisper variants, Remotion/Chrome, MoviePy,
     background removal, diarization, OCR, and NLE export helpers.

3. Ingest
   - Probe media metadata.
   - Generate contact sheets.
   - Generate lightweight proxy files for fast review when sources are large.
   - Extract audio.
   - Transcribe with word timestamps.
   - Produce a readable transcript and a machine-readable speech map.
   - Detect silence, filler words, repeated lines, speech rate, scene changes,
     black frames, loudness, and obvious bad takes.
   - Record all source hashes and probe metadata in `media.json` for
     reproducibility.

4. Take Selection
   - Reconstruct the intended script from repeated takes.
   - Prefer the last complete clean take unless the user points to another.
   - Create an EDL with clip id, in/out, line text, zoom, crop center, and look.
   - Keep handles around every cut so the edit can be relaxed later.
   - Show a short edit plan with estimated duration, render path, and any
     expensive/optional tools. Continue automatically only for the cheap local
     draft path; ask before paid APIs, uploads, or long renders.

5. Timeline and Recipe
   - Convert the EDL into a declarative render recipe.
   - Validate that every source, time range, transcript word, asset, font, and
     output path exists before rendering.
   - Store a command log and snapshot points so revisions can be restored.
   - Keep the recipe diffable so the user or agent can inspect exactly what
     changed between versions.

6. Assembly
   - Cut from originals using `ffmpeg`.
   - Normalize to constant frame rate and target resolution.
   - Add punch-ins when adjacent sections use the same angle.
   - Keep an editable `segments.json` for later revisions.
   - Preserve sync for multi-track video and external microphones.
   - Allow a rough-cut-only mode that exports XML/EDL/FCPXML for human finish
     work in DaVinci Resolve, Premiere Pro, or Final Cut.

7. Design Pass
   - Apply the selected visual look.
   - Render captions from the verified transcript, not the first rough
     transcript.
   - Place text inside safe zones.
   - Add simple overlays only when the spoken content calls for them.
   - Choose renderer by complexity:
     - `ffmpeg` for fast cuts, crops, captions, cards, and simple overlays.
     - Remotion or equivalent only for frame-accurate kinetic captions, UI
       callouts, complex motion, or reusable branded templates.
   - Keep all caption text editable in a sidecar file, not only burned into the
     render.

8. Render
   - Produce full-quality output.
   - Produce a smaller phone-review copy.
   - Keep all versions in `renders/`.
   - Render low-resolution proofs before expensive full-quality output.
   - Cache transcription, proxies, derived audio, and stable overlay assets.

9. QA
   - Check cut frames from the final render.
   - Check audio peak and loudness.
   - Check caption timing and safe-zone collisions.
   - Generate a QA report with thumbnails and actionable findings.
   - Reject the render when required checks fail. Do not deliver a failing video
     as complete.
   - Compare expected timeline duration against rendered duration.
   - Check black frames, frozen frames, missing media, clipped audio, subtitle
     overflow, unreadable contrast, face/text collision, and output codec.
   - Produce contact sheets at cuts, caption-heavy moments, and platform UI
     danger zones.

10. Revision
   - Accept precise user notes such as smaller captions, remove a pause, change
     a take, change look after a line, or add/remove an overlay.
   - Preserve prior versions and record what changed.
   - Support transcript-first edits: delete words, restore words, remove filler,
     relax a cut, split at playhead time, and retime captions.
   - Support snapshot/restore at the recipe level.
   - Keep human notes and accepted/rejected automated QA findings in the project
     log.

11. Export
   - Export final MP4 for the target platform.
   - Export captions as SRT, VTT, and JSON.
   - Export timeline handoff formats when possible: EDL/XML/FCPXML/Resolve
     import package.
   - Export a review report with thumbnail contact sheets, transcript, source
     manifest, and version history.

## Proposed Package Structure

```text
Skills/video-edit/
├── README.md
├── ARCHITECTURE.md
├── claude/
│   ├── SKILL.md
│   └── INSTALL.md
├── codex/
│   ├── SKILL.md
│   └── agents/openai.yaml
├── shared/
│   ├── references/
│   │   ├── workflow.md
│   │   ├── looks.md
│   │   ├── safe-zones.md
│   │   ├── qa.md
│   │   └── revisions.md
│   ├── scripts/
│   │   ├── setup.py
│   │   ├── ingest.py
│   │   ├── transcribe.py
│   │   ├── analyze_reference.py
│   │   ├── analyze.py
│   │   ├── brand.py
│   │   ├── apply_look.py
│   │   ├── card.py
│   │   ├── insert_image.py
│   │   ├── plan.py
│   │   ├── edl.py
│   │   ├── recipe.py
│   │   ├── validate_recipe.py
│   │   ├── assemble.py
│   │   ├── captions.py
│   │   ├── render.py
│   │   ├── qa.py
│   │   ├── export_nle.py
│   │   ├── state.py
│   │   ├── revise.py
│   │   └── transcript_edit.py
│   └── assets/
│       ├── looks/
│       ├── fonts/
│       ├── sfx/
│       ├── templates/
│       └── schemas/
└── docs/
    ├── phase-plan.md
    ├── compatibility.md
    └── clean-room-notes.md
```

The current scaffold includes the directories and planning docs. Placeholder
scripts should be added only when implementation starts.

## Tooling Choices

| Job | Preferred tool | Reason |
| --- | --- | --- |
| Probe/cut/render media | `ffmpeg` / `ffprobe` | Reliable, local, cross-platform |
| Transcription | Whisper-compatible backend | Word timings and local fallback |
| Metadata and orchestration | Python | Portable scripts and simple JSON |
| Edit state | JSON manifest and recipe files | Diffable, inspectable, undoable |
| Silence/motion cuts | Local analyzer plus user-tunable thresholds | Avoid brittle flat cuts |
| HTML/canvas graphics | Node only if needed | Useful for designed overlays, avoid early complexity |
| Complex motion | Optional Remotion tier | Frame-accurate templates when `ffmpeg` is too blunt |
| Handoff export | EDL/XML/FCPXML where practical | Lets a human finish in an NLE |
| QA contact sheets | Python plus `ffmpeg` | Deterministic thumbnails and reports |

Open question: whether the first build should use pure `ffmpeg` overlays for
captions or a browser-rendered overlay stack. Pure `ffmpeg` is faster to ship;
browser overlays give richer motion design.

Recommendation after audit: ship Phase 1 with `ffmpeg` captions and a strict
recipe schema, then add a Remotion renderer in Phase 4 for premium templates.
The schema boundary matters more than the first renderer.

## Data Model

Each project should be file-based:

| File | Purpose |
| --- | --- |
| `project.json` | Project settings, target platform, aspect ratio, selected look |
| `media.json` | Source files and probe metadata |
| `transcript.json` | Word-level transcript and confidence data |
| `edl.json` | Human-editable take selection |
| `recipe.json` | Declarative render plan validated before execution |
| `segments.json` | Exact assembled timeline after rendering |
| `state.json` | Version history, accepted notes, current render |
| `commands.jsonl` | Commands run, tool versions, exit codes, outputs |
| `exports/` | Captions, NLE handoff files, review manifests |
| `qa/report.md` | QA findings and final checks |

This keeps the skill inspectable and easy to revise without a database.

## Loopholes Found and Closed

| Loophole in earlier draft | Risk | Fix in this revision |
| --- | --- | --- |
| "Pick takes and render" skipped durable edit state | Agent could lose why a render changed | Add `recipe.json`, `state.json`, command log, snapshot/restore |
| No distinction between source package and install package | Final skill could include review docs and clutter | Define lean install package and repo-level planning docs |
| No NLE handoff | Users who want human finishing are trapped in the script | Add EDL/XML/FCPXML export target |
| No reference-video path | User may ask "make it like this" and skill has no process | Add reference analysis and concept plan |
| No cost/time gate | Agent might trigger long or paid operations casually | Add proof render and approval gate |
| Silence removal too simple | Flat thresholds can eat useful pauses and breaths | Add handles, tunable thresholds, transcript-aware review |
| Captions only implied as burned-in | User cannot repair text without rerender pain | Keep sidecar SRT/VTT/JSON and editable caption source |
| QA too narrow | A technically rendered MP4 can still be unusable | Add black/frozen frame, contrast, collision, duration, codec checks |
| Privacy not explicit | Raw media could be uploaded by accident | Local-first default and explicit upload consent |
| No multi-track/audio sync note | External mic projects can desync | Add multi-track sync preservation |
| No cache/proxy layer | Large 4K footage makes iteration slow | Add proxies and caching |

## Phases

### Phase 0: Review and Alignment

- Review this architecture.
- Decide default platform: Instagram Reel, TikTok, or YouTube Shorts.
- Decide default look set and whether Creovine Academy gets a branded preset.
- Decide whether the first implementation should be Claude-first, Codex-first,
  or both together.

Exit: approved architecture and selected defaults.

### Phase 1: Minimal Local Pipeline

- Add setup, ingest, transcription, EDL, recipe validation, assembly, and basic
  QA scripts.
- Support one look: clean captions, subtle punch-ins, 9:16 output.
- Test with one short folder of sample clips.
- Export sidecar SRT/VTT/JSON captions.

Exit: a raw clip folder can become a watchable captioned draft.

### Phase 2: Project State and Revision Safety

- Add `state.json`, `commands.jsonl`, and snapshot/restore.
- Add proof render before full render.
- Add targeted transcript-first revisions.
- Add NLE handoff export for rough cuts.

Exit: edits are inspectable, reversible, and handoff-friendly.

### Phase 3: Agent Entrypoints

- Write `claude/SKILL.md` and `codex/SKILL.md`.
- Keep both entrypoints pointed at the same shared scripts.
- Validate Codex skill metadata and Claude install instructions.

Exit: both agents can run the same minimal pipeline.

### Phase 4: Better Editorial Decisions

- Improve take selection from repeated lines.
- Add silence trimming with guardrails.
- Add punch-in and crop-center logic.
- Add manual EDL override instructions.
- Add reference-video analysis for pacing, hook structure, and caption style.

Exit: drafts require fewer manual notes.

### Phase 5: Looks and Brand Kits

- Add multiple look presets.
- Add Creovine Academy defaults for course promos.
- Add optional brand kit fields: logo, font, colors, CTA style.
- Add optional Remotion renderer for premium motion and reusable templates.

Exit: a user can ask for a named style and get consistent output.

### Phase 6: Overlays and Inserts

- Add support for simple app screenshots, profile cards, slides, or document
  scrolls.
- Keep overlays deterministic and safe-zone checked.

Exit: videos can include useful inserts without turning into a full editor.

### Phase 7: Advanced QA and Batch Work

- Add batch processing for repeated formats.
- Add benchmark sample clips and expected outputs.
- Add self-review/reject thresholds.
- Add visual regression snapshots for templates.

Exit: the skill is safe for repeated content workflows.

### Phase 8: Revision Loop

- Add version tracking.
- Add targeted revision commands.
- Preserve prior renders and QA reports.

Exit: user notes can be applied without rebuilding the project from scratch.

### Phase 9: Distribution

- Package for Claude Code and Codex.
- Add install/update docs.
- Decide GitHub repository and license.
- Push only after explicit approval.

Exit: reviewed public or private repo with correct authorship.

## Decisions Needed

1. Should the skill be named `video-edit`, `reel-edit`, or something more
   Creovine-specific?
2. Should the default preset be general creator style or Creovine Academy
   course-promo style?
3. Should captions prioritize speed and legibility or premium kinetic motion in
   the first release?
4. Should we include background cutout in the first implementation, or defer it
   until the base pipeline is stable?
5. Should the public repo mention Creovine, or should it ship as a personal
   open-source skill by Yerins Abraham?
6. Should the first release include NLE handoff export, or is MP4 + captions
   enough?
7. Should the first release support reference-video analysis, or should it wait
   until after the local core works?

## Recommended First Build

Build the boring but reliable core first:

- `ffmpeg` assembly
- Whisper transcription
- JSON EDL
- declarative `recipe.json`
- recipe validation
- clean captions
- sidecar caption exports
- safe-zone and audio QA
- low-res proof render
- versioned project state
- dual Claude/Codex instructions

Defer background removal, orbiting reels, advanced motion graphics, generated
B-roll, hosted UI, and paid cloud APIs until a simple reel can be produced,
audited, revised, and exported reliably.
