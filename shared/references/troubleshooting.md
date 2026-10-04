# Troubleshooting

Start with `python3 shared/scripts/setup.py`. It reports which ffmpeg,
transcription engine and motion tier the skill will use.

## Captions are not burned in

`setup.py` says `captions: SIDECAR ONLY`, render prints a libass warning, and
QA reports "captions were not burned in".

Your ffmpeg was built without libass. Homebrew's default `ffmpeg` formula is
one of these builds. Pick one fix:

- **Apple Silicon Mac:** `brew install ffmpeg-full`. It is keg-only, so it
  does not replace your `ffmpeg`; the skill finds it automatically under
  `/opt/homebrew/opt/ffmpeg-full/bin`.
- **Intel Mac:** Homebrew has no `ffmpeg-full` bottle (Tier 3). Download a
  static build that includes libass (for example from evermeet.cx), then put
  `ffmpeg` and `ffprobe` in `~/.cache/video-edit/bin/`, or point at them:
  `export VIDEO_EDIT_FFMPEG=/path/to/ffmpeg VIDEO_EDIT_FFPROBE=/path/to/ffprobe`.
- **Linux:** `sudo apt install ffmpeg`. The distro build includes libass.
- **Windows:** `winget install Gyan.FFmpeg` (the full build includes libass).

Check: `ffmpeg -hide_banner -filters | grep -w ass`.

Tool lookup order for every script: `VIDEO_EDIT_*` env var, then
`~/.cache/video-edit/bin`, then a Homebrew `ffmpeg-full` keg, then `PATH`.

## Does ffmpeg slow the computer down?

Only while it is encoding. ffmpeg is a command-line tool, not a background app:
it runs when a script calls it and exits when the render is done. Encoding is
heavy work for any tool, so a render uses most of the CPU for its duration.

The skill keeps that short:

- Each segment is read from its cut point instead of decoding the whole file
  once per segment.
- On Macs, assembly and review copies use Apple's hardware encoder
  (VideoToolbox), the same native path phone apps use: about six times less
  CPU. Finals use libx264 for a smaller, better file. `VIDEO_EDIT_HWENC=all`
  uses hardware for finals too; `VIDEO_EDIT_HWENC=0` turns it off.
- Run one heavy job at a time (transcription, render, motion graphics).

## Transcription

### No engine

The skill prefers whisper.cpp (`whisper-cli`) with the `small.en` model, which
is much better than `base` and fast enough on a laptop CPU.

- **Apple Silicon:** `brew install whisper-cpp`.
- **Intel Mac or Linux:** build it (about five minutes):

```bash
git clone --depth 1 https://github.com/ggml-org/whisper.cpp ~/.cache/video-edit/whisper.cpp
cd ~/.cache/video-edit/whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 4 --target whisper-cli
mkdir -p ~/.cache/video-edit/bin && cp build/bin/whisper-cli ~/.cache/video-edit/bin/
```

No `cmake`? `python3 -m pip install cmake` works without Homebrew.

Then download the model: `python3 shared/scripts/setup.py --download-model`
(about 470 MB, saved to `~/.cache/video-edit/models`).

openai-whisper (`pip install openai-whisper`) also works as a fallback.

### The transcript is one or two words of nonsense

The whisper.cpp GPU (Metal) path returns garbage on some Macs. On one Intel
MacBook Pro a 13-second clip came back as the single word "JO". The skill runs
on CPU automatically on Intel Macs and retries on CPU when a clip returns far
too few words. Force it with `transcribe.py --no-gpu`. CPU was also faster on
that machine.

### Names and products are wrong

Expected. "Cloud code" for Claude Code, "versatile" for Vercel. Add rules to
the project's `corrections.json` and re-run `fix_transcript.py`; the raw
transcript is kept in `transcript.raw.json`, so fixes are repeatable:

```json
{"replacements": [{"pattern": "\\bversatile\\b", "replace": "Vercel"}],
 "watch": ["fill"], "neverAppear": ["my-private-email"]}
```

Then read `qa/transcript-review.md`.

### Transcription is slow

Budget roughly two thirds of the clip length on a modern CPU, and up to twice
the clip length on an older laptop doing other work. Run one heavy job at a
time; transcription, OCR and rendering each want the whole CPU.

## Rendering

### "aroll.mp4 is stale"

The recipe changed after the last `assemble.py`. Run `assemble.py` again. This
guard exists because rendering an old assembly passes every step until QA
catches the duration mismatch.

### QA: duration mismatch or video/audio drift

Usually a stale assembly (above), or a card whose audio runs longer than its
video. Re-assemble; if it persists, check `segments.json` against
`recipe.json`.

### Captions or graphics cover the face

Write one composited frame and look at it: `render.py <project> --frame 3.5`
writes `qa/frame.jpg`. Move captions with the recipe's
`captions.style.position` (`top`, `middle`, `bottom`) or `safeBottomPx`, and
overlays with `overlay.py add --y`.

## Motion graphics (HyperFrames)

### "Chrome cannot start"

The first launch of HyperFrames' bundled Chrome can time out while macOS scans
the new binary. Run the same `motion.py` command again. If it keeps failing:
`npx hyperframes browser ensure --force`, or set `HYPERFRAMES_BROWSER_PATH` to
an installed Chrome.

### "needs Node.js 22"

Install a current Node LTS. The rest of the skill does not need Node; use a
PNG with `overlay.py` instead.

### Offline

Templates load GSAP from jsDelivr, so the first render needs a connection. To
work offline, save `gsap.min.js` next to the template's `index.html` and change
the script `src` to the local file.

## Face detection and text behind the person

These use Apple's Vision framework through a small Swift helper that compiles
the first time it is needed (`~/.cache/video-edit/bin/vision-helper`). It needs
macOS and the Xcode command line tools (`xcode-select --install`). On other
systems, graphics fall back to the typical talking-head face position and
`--behind` is unavailable.

A person mask takes roughly eight seconds per second of video on an Intel Mac,
so keep behind-the-person moments short (one or two seconds each).

## Captions appear before the speaker talks

`transcribe.py` re-times words onto real speech using the audio's silences. If
the room is noisy, silence detection finds nothing and the original Whisper
times are kept. Re-run after recording in a quieter space, or check
`transcript.raw.json` `silences`.

## Windows

- Use `python` (or `py`) instead of `python3`.
- `python setup.py --install` downloads ffmpeg (gyan.dev essentials build, with
  libass) and whisper.cpp (official release) into
  `%USERPROFILE%\.cache\video-edit\bin`, installs Node.js LTS with `winget`
  if it is missing (restart the terminal afterwards), and MediaPipe for the
  background cut-out.
- Projects are saved in `%USERPROFILE%\Videos\Video Edit`.
- Fast previews use NVIDIA NVENC, Intel Quick Sync, or AMD AMF when the machine
  has one; otherwise the software encoder.
- If a console prints garbled symbols, set `PYTHONUTF8=1` (the scripts set it
  for themselves and each other).
