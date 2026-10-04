# Editing Rules

The default creative rules for short-form talking-head edits. They are applied
automatically by `autoedit.py`; the agent follows them without being asked and
only departs from them when the user says so ("no zooms", "remove the logo",
"keep it calm"). Every rule names the tool that implements it.

They come from studying edits that hold attention: something changes every few
seconds, every claim is shown rather than only said, and nothing ever covers the
speaker's face.

## 1. The hook (first 3 seconds)

- Something moves in the first second. Never open on a static frame.
- If the speaker names a product or topic in the first sentence, put it **behind
  the speaker** as a huge word with a low boom (`motion.py big-text --behind`).
- If the first line is "everyone is talking about X", ask for screen recordings
  or screenshots of those posts and pop them in on both sides of the face
  (`assets.py`, pop layout).

## 2. Pacing: a visual change every 3-5 seconds

A change is any of: a cut, a zoom, a layout switch, a graphic entering.

- Zooms fill the gaps (`recipe.zooms`, rendered by `render.py`):
  - **Punch-in** (instant 1.15-1.2x) on a key word or the start of a punchline.
  - **Push-in** (slow 1.0 to 1.1x) across a longer sentence.
  - Back to wide on the next sentence. Alternate; never two punch-ins in a row.
- Zooms are centred on the face and never exceed 1.25x on 1080p footage.
- No zoom while a pop-in card, logo, or split screen is on screen.

## 3. Captions

- Look `creator-pro`: small lowercase captions at mid-frame, word by word.
- Key words get their own big card (`captions.py --emphasis`): the claim, the
  product, the number, the payoff. Roughly one every 3-6 seconds.
- Feeling words get the elegant italic serif (`captions.py --elegant`): words
  that describe a vibe or an aesthetic ("clean", "cinematic", "cozy").
- A caption never appears during a pause (`align.py`).
- When a graphic covers the middle of the frame, captions move to the top
  (`captions.topWindows`).

## 4. Show, don't only say

| The speaker says | Show | Tool |
| --- | --- | --- |
| A product name (Claude, ChatGPT, Codex...) | Its logo tile beside the face, first mention only | `logos.py` + `motion.py logo-pop` |
| "a skill", "a prompt", "the file", "the template" | The file floating as a code window | `motion.py code-window` |
| A workflow ("drop in your clips", "install", "type", "trigger") | A UI demo with a moving cursor, as a split screen | `motion.py app-demo --place split` |
| "Comment X", "DM me X" | A comment sheet where X is typed and posted | `motion.py social-cta --place split` |
| A number | A stat graphic | `motion.py stat` |
| "Like this", "for example", "look at this" | Ask for the real example; split or cover | `assets.py` |
| "Everyone is talking about..." | Ask for screen recordings or screenshots; pop cards | `assets.py` |
| A strong claim ("no code", "for free") | The claim as big text behind the speaker | `motion.py big-text --behind` |

Real media beats generated graphics. Always ask for it (`assets.py suggest`);
generate a graphic only when the user has nothing.

## 5. Placement

- Never cover the face. Pop-ins and logos are placed around where the face is
  during their window (`vision.py`, Apple Vision on macOS).
- At most two graphics on screen at once, plus captions.
- Split screens put the media on top and the speaker, cropped around the face,
  below.

## 6. Sound

- Whoosh or swipe when a layout or graphic enters, pop on logos and key-word
  cards, click on UI clicks, ding on checklist ticks, boom under a depth word.
  The templates carry these cues (`cues.json`); `motion.py` adds them.
- SFX sit 12-20 dB under the voice. Never more than one SFX per half second.
- Music only if the user provides a track they have rights to; it ducks under
  the voice automatically (`sound.py music`). Ask once.
- Voice is cleaned (rumble filter, gentle compression) and the mix is
  normalised to -14 LUFS for short-form, -16 for long-form.

## 7. Colour

- Natural grade by default, judged on the face (`grade.py`). Offer a LUT or a
  reference still if the user has a look in mind.

## 8. Never

- Never cover the face or the mouth.
- Never put a graphic in the platform UI zones (top 220 px, bottom 420 px,
  right-hand action rail).
- Never invent facts in a graphic. Numbers, names, and quotes come from the
  transcript.
- Never bundle or alter third-party logos; fetch them per project and show them
  only when the product is being discussed.
- Never imitate a real app's interface exactly; UI demos are generic.
- Never use music or footage the user has not provided or cleared.

## Overrides

The user is the director. Anything above changes on request, and the change is
kept for the rest of the project: remove a beat with
`autoedit.py <project> --skip <beat-id>`, or edit `recipe.json` directly.
