# Looks Reference

The first implementation ships deterministic look presets in
`shared/assets/looks/`. Apply one with:

```bash
python3 SK/shared/scripts/apply_look.py <project> clean-creator
```

## clean-creator

- Use for the first implementation.
- 9:16 output.
- Center-bottom captions inside platform safe zones.
- White text with dark outline.
- Subtle punch-ins only.
- No background replacement.
- No generated B-roll.

## course-promo

For Creovine Academy clips, course teasers, lesson excerpts, and launch videos.

Pair it with `brand.py`:

```bash
python3 SK/shared/scripts/brand.py <project> --name "Creovine Academy" --primary "#2563eb"
python3 SK/shared/scripts/apply_look.py <project> course-promo --name v2
```

Simple title/CTA cards are generated locally:

```bash
python3 SK/shared/scripts/card.py <project> --title "START HERE" --subtitle "AI SOFTWARE ENGINEERING"
```

Still screenshots or image inserts use:

```bash
python3 SK/shared/scripts/insert_image.py <project> <image> --position end --duration 2 --label "Product screen"
```

## bold-kinetic

Planned for richer motion. In the current ffmpeg-only pipeline it remains a
simple preset and does not add kinetic typography.

## editorial-dark

Use only when source footage is well lit enough to handle a darker grade.
