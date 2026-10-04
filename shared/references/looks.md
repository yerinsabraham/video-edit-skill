# Looks

A look sets the captions, the grade, how the camera moves, and a signature
move. Pick one for the whole edit (`apply_look.py <project> <look>`, or the
saved default) and switch sections with `autoedit.py --section "look:phrase"`
(or `edit.py --section`).

## bold (default)

Kinetic lowercase captions word by word; key words on their own big yellow
card; the hook word behind the speaker; punch-ins alternating with push-ins.

## soft

Warm grade, calm lowercase captions that fade rather than bounce, one punch
line per section in a yellow serif italic with sparkles. Signature: the
creator's own reels orbit around them (needs reels in
`<project>/work/instagram/reels/`, from `instagram.py` or dropped in).

## studio

Dark editorial grade with a vignette, so the room falls back and the speaker
stays lit. Tiny spaced capitals, big white serif words, wide and close shots
alternating line by line like a two-camera interview.

## Others

- `creator-pro`: bold without the depth-word signature (the original default).
- `clean-creator`: conservative captions for a reliable first draft.
- `bold-kinetic`: uppercase Anton captions, strong highlight colours.
- `course-promo`: pairs with `brand.py` for a course or product brand, plus
  `card.py` title/CTA cards and `insert_image.py` stills.
- `editorial-dark`: darker grade for well-lit footage.

Per-project caption overrides live in `recipe.json` `captions.style`
(`position`, `sizeScale`, `highlightColor`, `punchColor`) and are set by
`captions.py --size` and `--position`. A brand kit's `accent` becomes the punch
colour.
