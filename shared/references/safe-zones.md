# Safe Zones Reference

Phase 1 target is 1080x1920.

Keep captions and important graphics away from common platform UI:

- Top: reserve 220 px.
- Bottom: reserve 420 px.
- Left and right: reserve 48 px.
- Avoid the lower-right action rail on Reels/TikTok.

The first implementation uses conservative bottom-centered captions. Later
looks can add top text, CTAs, or animated words only after snapshot QA exists.
