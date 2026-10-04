# Changelog

## 0.9.2 (2026-10-05)

- Clip order: calls to action ("comment X", "follow me", "link in bio") move to
  the end with the rest of their sentence; `takes.py --move L7=end|start|after:L3`,
  `--clips m2,m1,m3`, `--order`, `--no-cta-last`, `--reset-order`.
- Files listed one by one keep their order (`ingest.py --keep-order`); folders
  still go by recording time.
- The take recorded last wins a tie, whatever the play order.
- `edit.py --until takes` prints the numbered line order to confirm before the
  long render.
- The skill tells the agent never to wrap scripts in `timeout` (missing on macOS
  and Windows).

## 0.9.1 (2026-10-04) - Windows

- Windows support: `setup.py --install` installs ffmpeg with libass and
  whisper.cpp, and Node via winget; UTF-8 safe output; projects in
  `~/Videos/Video Edit`; CI on Windows and macOS as well as Linux.
- Hardware previews on NVIDIA (NVENC), Intel (Quick Sync), and AMD (AMF), each
  verified with a test encode before use.
- `setup.py --install --only ffmpeg,whisper,model,motion,mediapipe`; each tool
  installs independently, and the whisper.cpp download survives GitHub API
  rate limits.
- File paths in ffmpeg filters are quoted, so Windows drive letters work.
- HyperFrames is handed the skill's own ffmpeg, so it works when ffmpeg lives
  only in the skill's tool folder.
- MediaPipe Tasks API (current releases), with the legacy API as a fallback;
  a clear message when Linux lacks libEGL/libGLESv2.
- CI: core tests on Linux (3.10, 3.12), Windows, and macOS; motion graphics and
  the background cut-out tested on all three.

## 0.9.0 (2026-10-04) - public preview

First public release.

- One command: `/video-edit I just dropped 5 clips in my downloads` (`edit.py`).
- First-run setup: preferences (name, handle, look, clips folder) and
  `setup.py --install` for ffmpeg with libass, whisper.cpp, the speech model,
  HyperFrames, and MediaPipe on Linux.
- Best take of every line across clips, with a take table (`takes.py`).
- whisper.cpp transcription; word timings re-aligned to the real speech;
  transcript cleanup and per-project corrections.
- Editing rules applied automatically (`autoedit.py`): hook word behind the
  speaker, logos, app demo, code window, comment and follow CTAs, claims, stats,
  zooms, sound; parallel motion renders; `--skip` and `--rebuild` beats.
- Three looks (bold, soft, studio) with per-section switching.
- Motion templates (HyperFrames): app-demo, social-cta, social-profile,
  code-window, logo-pop, media-pop, big-text, orbit, phone-frame, stat,
  callout, lower-third.
- Background cut-out and face-aware placement: Apple Vision on macOS,
  MediaPipe elsewhere.
- Punch-ins from the original resolution (up to 2x the output).
- Sound: synthesised SFX, ducked music, voice clean-up, -14/-16 LUFS.
- Grade: natural grade judged on the face, presets, LUTs, match a still.
- Real media requests (`assets.py`) with on-screen creator credits.
- Optional Instagram reels and profile stats via Apify (`instagram.py`).
- QA: face clearance, safe zones, every cut, sync, decode, caption timing.
- Notes commands: caption size and position, cut a line, tighten a pause.
- Claude Code plugin and marketplace; `install.py` for Claude Code and Codex.
