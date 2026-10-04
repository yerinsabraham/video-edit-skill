# Safe Zones Reference

Default target is 1080x1920.

Keep captions and important graphics away from common platform UI:

- Top: reserve 220 px.
- Bottom: reserve 420 px.
- Left and right: reserve 48 px.
- Avoid the lower-right action rail on Reels/TikTok.

Captions default to bottom-centre above the 420 px band. Find the face first:
in a typical vertical talking head it sits in the middle third, so captions go
below the chin and graphics go in the band above the head (overlays default to
y = 220). Never across the mouth. Check with `render.py --frame <t>`.
