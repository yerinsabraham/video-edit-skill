# Motion Graphics: Decision Record

Date: 2026-10-04. Status: adopted.

## Decision

Two tiers, both composited by the existing ffmpeg render:

1. **Captions: libass (ASS subtitles), built in.** Kinetic word-lit captions
   are generated as an `.ass` file and burned in with ffmpeg's `ass` filter.
2. **Graphics: HyperFrames, optional.** Stat bars, callouts and lower thirds
   are HTML + GSAP compositions rendered by HyperFrames to ProRes 4444 with
   alpha, then placed with `overlay.py`. Static cards stay as PNGs.

Remotion, which the playbook's earlier work used, is no longer the
recommendation.

## Why captions use libass

- Already inside ffmpeg; no Node, no browser, no extra install.
- Deterministic and fast: captions cost nothing beyond the render.
- ASS has what short-form captions need: per-word colour and alpha,
  scale transforms for a pop-in, outline and box styles, exact timing.
- The playbook's short-form rules (2-4 words, lit word, punch colour,
  minimum hold) map directly onto ASS events.

The catch: some ffmpeg builds ship without libass (Homebrew's default
`ffmpeg` formula, for one). `setup.py` reports it and QA flags it. See
`shared/references/troubleshooting.md`.

## Why HyperFrames over Remotion

| | HyperFrames | Remotion | Revideo / Motion Canvas |
| --- | --- | --- | --- |
| Licence | Apache-2.0, same as this repo | Business Source; companies over 3 people need a paid licence | MIT |
| Authoring | Plain HTML, CSS, GSAP | React components | TypeScript generators |
| Agent fit | Agents write HTML reliably; no build step | Needs a React project | Needs a TS project |
| Alpha output | `--format mov` (ProRes 4444) or WebM | ProRes 4444 needs `--image-format=png` too | Varies |
| Variables | `--variables` JSON per render | Props via CLI | Code |

The deciding points: an open-source skill that "every team" should be able to
adopt cannot depend on a renderer whose licence charges teams over three
people, and HTML is the format agents produce most reliably. HyperFrames was
released by HeyGen in April 2026, renders deterministically, and supports
transparent output natively.

## Guard rails in `motion.py`

- Telemetry is disabled for every render (`DO_NOT_TRACK=1`). HyperFrames
  collects anonymous usage data by default, which conflicts with this skill's
  local-first rule.
- The version is pinned (`hyperframes@0.8.123`); override with
  `VIDEO_EDIT_HYPERFRAMES`.
- Templates load GSAP from jsDelivr, so the first render needs a network
  connection. Media and project files never leave the machine.
- Output is composited by ffmpeg, so the motion tier never touches the A-roll
  or the audio.

## When a graphic earns its place

From playbook §8, enforced by review rather than code:

- A number spoken in one breath: `stat`.
- A promise ("the link is on the screen"): `callout`, for as long as they talk
  about it. `qa/transcript-review.md` lists these lines.
- Who is speaking, once: `lower-third`.
- Mindset, story, community: nothing.
- Screen recordings: almost nothing; a small card in an unused corner at most.

Always check one composited frame (`render.py --frame <t>`) before a full
render. Overlays sit in the bands above or below the face, never across it.

## Sources

- HyperFrames: https://github.com/heygen-com/hyperframes
- HyperFrames rendering guide: https://hyperframes.app/docs/3-guides/4-rendering
- Remotion licensing: https://www.remotion.dev/docs/license
