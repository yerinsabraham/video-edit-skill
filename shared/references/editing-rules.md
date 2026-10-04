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
| "Comment X", "DM me X" | A comment sheet: X is typed and posted, the creator replies "check your DMs", and the DM arrives, timed to "I'll send it to you" | `motion.py social-cta --place split` |
| A number | A stat graphic | `motion.py stat` |
| "Like this", "for example", "look at this" | Ask for the real example; split or cover | `assets.py` |
| "...and get something like this" after a workflow, with no example footage | The video itself: it shrinks into a phone labelled "this video" | `motion.py phone-frame --place phone` |
| "Everyone is talking about..." | Ask for screen recordings or screenshots; pop cards | `assets.py` |
| A strong claim ("no code", "for free") | The claim as big text behind the speaker | `motion.py big-text --behind` |

Real media beats generated graphics. Always ask for it (`assets.py suggest`);
generate a graphic only when the user has nothing.

Never show other people's videos as the result of the user's product: it
implies the product made them, and re-posting needs the owner's permission.
When the result is the video being watched, say so ("this video") and cut a
second "or something like this" (`cut.py --text`).

## 5. UI realism standard

A UI demo (an app window, a comment sheet, a dashboard) must read as a real
screen in the first half-second, not as a motion graphic. Every UI template
meets this bar, and so does any new one an agent writes:

- **Real chrome.** Window controls (close, minimise, expand), a title bar with
  the app and project name, a sidebar with real-looking items, the user's name
  or avatar. Phones get the platform's sheet grabber, keyboard, and emoji bar.
- **Real content, never grey bars.** Plausible recents, file names with sizes
  (`clip_01.mov · 84 MB`), timestamps ("2h", "Just now"), like counts, Reply
  links, a pinned author comment. Comments on a call-to-action post are full of
  people asking for the keyword, as they are on real posts.
- **Real interaction.** The cursor drags a stack of files with a count badge; a
  drop zone lights up; files attach as chips; typing shows a caret, a command
  suggestion, keys popping on a keyboard; buttons enable when there is text.
- **Readable on a phone.** Text in the final frame is at least about 28 px in a
  1080-wide video. Show the whole window first, then let a camera follow the
  action (zoom into the composer while typing, onto the result after).
- **The real product name and logo, a generic layout.** Use the product's name
  and its logo (fetched per project), but do not copy its interface pixel for
  pixel or use its brand on things it did not make.
- **Checked.** Run `npx hyperframes check` on the composition and look at four
  frames composited on a backdrop before placing it.

## 6. Placement

- Never cover the face. Pop-ins and logos are placed around where the face is
  during their window (`vision.py`, Apple Vision on macOS).
- At most two graphics on screen at once, plus captions.
- Every graphic sits fully inside the frame with a margin, including its pop-in
  animation and tilt; text inside a tile shrinks to fit rather than overflow.
- Show what happens next, not a generic reaction: a call to action ends with the
  creator's reply and the DM, not a like.
- Split screens put the media on top and the speaker, cropped around the face,
  below.

## 7. Sound

- Whoosh or swipe when a layout or graphic enters, pop on logos and key-word
  cards, click on UI clicks, ding on checklist ticks, boom under a depth word.
  The templates carry these cues (`cues.json`); `motion.py` adds them.
- SFX sit 12-20 dB under the voice. Never more than one SFX per half second.
- Music only if the user provides a track they have rights to; it ducks under
  the voice automatically (`sound.py music`). Ask once.
- Voice is cleaned (rumble filter, gentle compression) and the mix is
  normalised to -14 LUFS for short-form, -16 for long-form.

## 8. Colour

- Natural grade by default, judged on the face (`grade.py`). Offer a LUT or a
  reference still if the user has a look in mind.

## 9. Never

- Never cover the face or the mouth.
- Never put a graphic in the platform UI zones (top 220 px, bottom 420 px,
  right-hand action rail).
- Never invent facts in a graphic. Numbers, names, and quotes come from the
  transcript; follower counts, bios, and verified badges only from the creator's
  real profile (Apify or what they tell you), otherwise they are left out.
- Never bundle or alter third-party logos; fetch them per project and show them
  only when the product is being discussed.
- Never copy a real app's interface pixel for pixel; UI demos follow the realism
  standard with a generic layout.
- Never use music or footage the user has not provided or cleared.

## Overrides

The user is the director. Anything above changes on request, and the change is
kept for the rest of the project: remove a beat with
`autoedit.py <project> --skip <beat-id>`, or edit `recipe.json` directly.
