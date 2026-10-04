# Production Playbook

Hard-won rules from shipping real videos: hour-long screen-share lessons for a
paid course, and 60 to 90 second vertical clips for social media. The other
references say how to run the scripts. This one says what goes wrong, why, and
what to do instead.

Read it before any edit that is longer than a few minutes, contains a screen
recording, or will be seen by people who paid for it.

---

## 1. Two kinds of video, two sets of rules

| | Long-form (lesson, tutorial, talk) | Short-form (reel, short, ad) |
| --- | --- | --- |
| Length | 20 to 90 minutes | 30 to 90 seconds |
| Captions | Sentences, two lines, read while watching something else | Two to four words, the thing being watched |
| Graphics | Almost none; the screen is the content | Many, but never over the face |
| Chapters | Required past about five minutes | None |
| The risk | Private information on a screen recording | Captions or graphics covering the speaker |
| Output | Sidecar captions and chapters, a companion document | One burned-in file |

Decide which one you are making before touching anything. Most mistakes come
from applying one set of rules to the other.

---

## 2. Transcription

### Getting the words

Extract mono 16 kHz audio and run Whisper locally:

```bash
ffmpeg -y -i source.mp4 -map 0:a:0 -ar 16000 -ac 1 -c:a pcm_s16le work/audio.wav
whisper-cli -m ggml-small.en.bin -f work/audio.wav -oj -of work/transcript
```

- `small.en` is the right default for English speech: much better than `base`,
  fast enough on a laptop CPU. Use `-ng` (no GPU) on machines where the GPU path
  fails.
- Budget roughly two thirds of the runtime on a modern CPU, and up to twice the
  runtime on an older laptop that is also doing other work. A 45 minute lesson
  took about 30 minutes alone and over an hour when sharing the CPU.
- For short-form captions that light up word by word, add `-ml 1` (max segment
  length one), which forces one word per segment and gives word timings.

### Read the transcript before anything else

Chapter points, graphics placement, the companion document and the title all
come from it. It is also the only chance to catch the video promising
something:

- "It's going to be shown on the screen" means somebody must put it on the
  screen.
- "The steps are in the PDF" means the PDF must contain those steps.
- A rule stated on camera ("you can retake once") must be true of the real
  product.

### Fix what Whisper misheard

Not optional, and the list is per speaker and per topic, not generic. Keep it in
the project as a list of regex substitutions applied before cueing.

- **Product and tool names** are almost always wrong: "versatile" for Vercel,
  "cloud code" for Claude Code, "codecs" for Codex, "chat dpt" for ChatGPT.
  The dangerous ones are real English words, because the caption still reads as
  a sentence and the viewer is confidently wrong rather than confused.
- **Meaning inverters** are worse than misspellings. "Fail" heard as "fill"
  turns "you may fail five" into "you may fill five". "Tasks" as "tax" turns
  homework into a charge. "Third party" as "state party". Search for them.
- **The speaker's own name** comes back mangled. Fix it once, everywhere.
- **The first person** comes back as lowercase "i". Fix it last, so it cannot
  fire inside a word another fix produced.
- **Phrases that straddle a cue boundary** do not match a fix written as one
  phrase. Write fixes against the shortest unambiguous fragment.

Leave genuinely ambiguous lines alone. A caption says what was said, and a
confident guess is worse than a clumsy line.

### Whisper artefacts to remove

- A credit nobody said ("transcribed by", "thanks for watching") after the last
  real sentence.
- A run of "you" over silence or an outro card. Drop "you" segments after the
  last real word.
- A lone comma or full stop emitted as its own word with its own timestamp.
  Attach it to the previous word, or it becomes a caption card reading ",".
- With `-ml 1`: numbers split at the separator ("12," then "000"),
  contractions split ("isn" then "'t"), and brand names split into syllables.
  Rejoin them, keeping the first fragment's start and the last fragment's end.

---

## 3. Long-form captions

Rules that produced readable captions for a fast speaker:

- Build cues from segments: flush at a sentence end once there are at least 34
  characters, or at 80 characters, or at 5 seconds, whichever comes first.
- Merge any cue shorter than 1.2 seconds or 12 characters into a neighbour.
- Split anything longer than about 84 characters into whole cues at word
  boundaries, sharing the segment's time in proportion to character count. A
  170 character cue covers a third of the frame and outruns the reader.
- Wrap each cue to two balanced lines of about 42 characters.
- Shift every timestamp by the length of anything prepended (an intro card).
  Captions written against the raw recording run early for the whole video.
- Capitalise after sentence ends; tighten spaces before punctuation, but only
  where the mark ends something, or ".gitignore" loses its dot.

Delivery rules for a web player:

- Captions on by default. Much of an audience watches muted or in a second
  language, and a menu they have to find is one most never open.
- **Safari ignores `<track default>`.** If captions matter on iPhone, draw them
  yourself from the cue events (set the track to `hidden`, which keeps firing
  `cuechange`) instead of trusting the browser.
- **Serve caption files from the same origin as the page.** A `<track>` is
  CORS-restricted in a way `<video src>` is not; a redirect to a storage bucket
  fails silently with no error anywhere.
- Name sidecars from the video's own id (`captions/<id>.vtt`,
  `chapters/<id>.vtt`), so they follow the file wherever it is reused.

---

## 4. Short-form captions

These are not lesson captions. A lesson caption is read while watching
something else; these are the thing being watched.

- Two to four words per card, uppercase, at most about 20 characters.
- Cut a card on a real pause (a gap over about 0.32 seconds), not on a
  character count.
- The word being spoken is lit; the rest of the card is dimmed.
- A short list of punch words (the numbers, the product, the claim) gets a
  stronger colour.
- Hold any card for at least 0.34 seconds. Shorter reads as a glitch and the eye
  gives up on the whole line.

Placement:

- Find where the face is first. In a typical vertical talking head the face sits
  in the middle third; captions and graphics go above it or below the chin, and
  never across the mouth.
- Respect platform UI: see `safe-zones.md`.
- Composite one real frame with the graphic on it and look at it before
  rendering anything long. A layout that looked right in the abstract sat on
  the speaker's shoulder in the real frame, because switching a flex container
  to `row` swapped which axis `alignItems` and `justifyContent` control.

---

## 5. Chapters and explainers

- One chapter every three to five minutes for a lesson. People do not rewatch
  an hour straight through; the second visit is someone looking for one part.
- **A chapter title names the question somebody would search for**, not the
  section: "How to report a bug to the agent", not "Debugging".
- Snap chapter starts to transcript segment starts.
- Apply the same intro shift as the captions, once, in the same function.
- If the player shows per-chapter notes keyed by start second, generate the keys
  from the shifted chapter track and check them against the chapters actually
  being served. A key one second off is not an error anywhere: the note simply
  never opens. That happened to seven of thirteen notes on one video.

Writing the notes: where a chapter turns on an idea, explain the idea in plain
words. Where it is a demonstration, say what is being shown and why, so
somebody who looked away for two minutes can rejoin.

---

## 6. Titles, intros and outros

- **A title names the thing.** Noun phrase, often `Tool: what is covered`.
  "GitHub: repositories, commits, and branches", not "Get your work off your
  laptop". A sentence goes in the summary underneath.
- **Name the skill, never the demo project.** A lesson titled after the sample
  app tells everyone building something else that it is not for them.
- **Nothing baked into a video may name where it currently sits.** An intro that
  says "Course X, lesson 2" makes that recording lesson 2 of course X forever.
  Make course, eyebrow, title and note props of one reusable card component.
- Keep the intro to about three seconds. Longer teaches viewers to skip the
  first ten seconds of everything.
- **Check whether an outro is already there** before making one. Extract the
  last frames and look:

```bash
ffmpeg -ss <duration-6> -i source.mp4 -frames:v 1 work/end.jpg
```

- The title is in the pixels. Renaming after publishing means re-rendering the
  card and re-joining, so settle the title first.

---

## 7. Assembly

### Match the body exactly

An intro card joined to a recording must match it in every parameter that ends
up in the stream header: codec, profile, level, pixel format, resolution,
frame rate (often `30000/1001`, not 30), timescale, audio codec, sample rate and
channel count. Read them from the source first:

```bash
ffprobe -v error -show_entries stream=codec_name,profile,level,pix_fmt,width,height,r_frame_rate,time_base,sample_rate,channels -of compact source.mp4
```

- Give silent cards a silent audio track
  (`-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 -shortest`),
  or the sound stops at the join.
- Audio on a card must not run longer than its video. A 47 ms overhang left a
  gap at the join.

### Stream copy only when headers are identical

Joining two H.264 files with the concat demuxer and `-c copy` writes one header
for both. It works only if the SPS and PPS are byte-identical, which needs the
same encoder and the same settings, including the CRF (the PPS carries an
initial QP derived from it). Compare them rather than assuming:

```bash
ffmpeg -v error -i a.mp4 -map 0:v -c copy -bsf:v h264_mp4toannexb -frames:v 1 -f h264 - | xxd | head
```

If they differ, re-encode the short piece (the card) with exactly the body's
settings.

### Do not splice by duration

Cutting a stream-copied piece with `-ss K -t D` includes a couple of extra
frames per cut, and the timestamps of re-encoded and copied pieces do not line
up. One attempt to patch a few seconds into a finished film came out 23 frames
long and 10 seconds short. If a fix touches more than one or two places, **one
clean full render is safer than clever splicing.** If you must splice, cut by
exact frame count (`-frames:v N`), keep the audio untouched from the source,
and verify the total frame count equals the source's.

### Verify every file

A file existing is not a file finished. Before using any render:

```bash
ffprobe -v error -show_entries stream=codec_type,duration,nb_frames -of compact file.mp4
ffmpeg -v error -i file.mp4 -f null - && echo decodes
```

Video and audio durations should agree within a few milliseconds, and the frame
count should equal the parts added together.

### Size

Screen recordings arrive at 5 to 10 Mbps, far more than they need. CRF 21 to 23
with a 2 second GOP brought a 45 minute 1080p lesson from 1.9 GB to under 500 MB
(about 1.5 Mbps) with screen text still sharp. For audiences on mobile data that
is the difference between a video that plays and one that does not. Measure the
result rather than assuming it.

---

## 8. Motion graphics

**Only where they earn their place.**

- A passage carrying a number gets a graphic: arithmetic spoken in one breath is
  hard to hold, and a bar that fills holds it for you.
- Something the speaker promises is on screen ("the link is on the screen") gets
  exactly that, for as long as they talk about it.
- Passages about mindset, story or community get nothing. A graphic there is
  decoration competing with a face.
- **A screen-share gets almost nothing**: the screen is the content, and a
  panel covers it. A small card in an unused corner is the most it should get.

Technique:

- Place graphics against the real footage, not against the last video. A layout
  that suited a speaker on the left covered one sitting in the centre.
- A static card (a link, a name) is cheapest as one transparent PNG faded in and
  out by ffmpeg: `fade=t=in:alpha=1` on a looped image, then `overlay` with
  `enable='between(t,a,b)'`.
- Animated overlays rendered with Remotion: transparent output needs ProRes 4444
  (`yuva444p10le`) **and** `--image-format=png`; without the PNG flag the render
  fails with a pixel-format error.
- Overlays for vertical video live in the bands above and below the face. Keep a
  margin from every edge for platform UI.

---

## 9. The privacy sweep

The section that cost the most. A screen recording shows far more than the
person recording remembers, and once a paying viewer has seen a frame it is too
late.

### What leaks

All of these appeared in one 45 minute recording:

- Email addresses printed by command-line logins (`vercel login`,
  `firebase login`), including inside OAuth URLs as `login_hint=name%40gmail.com`.
- Tables an AI agent prints when asked "which accounts am I logged in with",
  naming every account and project.
- An employer's or another business's email address and project names.
- The signed-in email in the app's own header, on every page.
- Browser bookmark bars and new-tab shortcuts ("Webmail <company>").
- Recent chat titles on an AI assistant's home screen, including a job search.
- A real document uploaded as test data, then previewed full screen.
- Folder names in a file picker's sidebar.

### Prevent it

- Record in a separate browser profile with no bookmarks, history or saved
  accounts.
- Use fixture files made for the purpose, never a real document "just to test".
- Sign command-line tools in before recording, off camera.

### Find it

Eyeballing sampled frames does not work. Text scrolls, and an address that is in
one place at 10.0 s is elsewhere at 10.5 s. Use OCR on the video itself.

- **Apple Vision** (via a small Swift tool) reads screen text far better than
  tesseract. Its `.fast` mode is quick and good at large text; `.accurate` is
  needed for small UI text such as an email under a name in a header. Use fast
  to find, accurate to box.
- Read frames straight off the video (`AVAssetReader`) instead of writing
  thousands of PNGs to disk. Give each worker its own `timeRange` so a worker on
  the last quarter does not decode the first three quarters to get there.
- Run three or four workers in parallel; one worker at 2 to 10 seconds per dense
  frame takes hours.
- Match emails with a regex, plus a list of names that must never appear, plus
  OCR misreadings (`@` often reads as `Q` or `&`). Match private chat titles as
  whole lines.
- **Classify screens cheaply first.** Average brightness per second separates a
  white browser page, a dark editor and a camera shot almost perfectly. Spend
  the slow accurate OCR only on the screens that need it.
- Filter known false positives: the word "Gmail" on a bookmark, the speaker's
  public handle.

### Blur it

One render, a mask, and a blurred copy of the frame:

```
[0:v]split=2[o][pre]
[pre]scale=128:72:flags=area,scale=1920:1080:flags=bicubic,format=yuva420p[bl]
color=c=black:s=1920x1080:r=30000/1001:d=<dur>,format=gray,
  drawbox=x=..:y=..:w=..:h=..:color=white:t=fill:enable='between(t,a,b)', ...
  ,lut=y='if(gt(val,100),255,0)'[m]
[bl][m]alphamerge[bla]
[o][bla]overlay=format=auto[out]
```

- Downscale-then-upscale blurs text beyond recovery and costs almost nothing.
- Force the mask to pure 255 with `lut`. "White" in a limited-range gray frame is
  235, which leaves the original showing through at about 8 percent.
- **Track each detection by identity and position**, not identity alone. When
  the same email jumped from a page header to a form field, tracking by "this
  email" treated it as one run and the new position never got its lead-in.
- Between two samples of the same thing, blur the union of both boxes, so text
  that scrolled between them stays covered at every position it passed.
- At the start and end of a run, hold the box about 3 seconds further and
  stretch it a few hundred pixels **both up and down**. Text in a chat or
  terminal can move either way.
- **Anything that sits in the same place on every page** (a signed-in email in a
  header) should be blurred whenever that screen is visible, not left to OCR.
  OCR misses small text on the odd frame, and each miss is a leak.
- A whole document previewed full screen gets its whole area blurred for the
  whole preview.

### Prove it

**Never trust the box list. OCR the rendered output.** Run fast mode every 0.25
to 0.5 seconds across every blurred stretch, and accurate mode across the
screens with small text. Feed every leak back in as a detection, re-render, and
check again. It took three rounds before one 45 minute lesson came back clean,
and every round found something real.

Test fixes on short clips first (`-ss T -t 8` with every filter time shifted by
`T`), OCR them at ten frames a second, and only then commit to a full render.

---

## 10. Publishing

- Upload large files with `curl --upload-file`, not a language HTTP client.
  Some clients time out waiting for response headers after a few minutes.
- With a presigned PUT, send **every header the signer returned**, verbatim.
  Sending only `content-type` is a signature mismatch, reported as a bare 403
  that reads like wrong credentials.
- S3-compatible stores do not all implement S3. Cloudflare R2 has no object
  tagging at all (`NotImplemented`); use object metadata. And keep
  `x-amz-meta-*` out of the presigned query string, where R2 silently ignores
  it.
- Read every object back after upload (size and metadata). A 200 that landed
  nothing has happened.
- Treat the video as a reusable asset with its own id, not as part of the page
  or course that first shows it. Captions, chapters and notes hang off the id.

---

## 11. The companion document

For any teaching video, a written companion is worth as much as the video.

- **It is not a transcript.** Same ground, in an order somebody can follow at a
  keyboard, plus everything that did not fit in the recording.
- **Cover the paths the video did not take.** If the demo is a web app, write the
  mobile steps too; if the video runs a command through an agent, write the
  command. In one lesson that meant full setup steps for a mobile testing tool
  that was only mentioned on camera.
- Every command in a copyable block with what it does on the line above.
- Name the mistakes. The thing that stops a beginner is almost never the happy
  path.
- Plain words, the way you would explain it to a friend.
- A clickable table of contents, generated from the headings, never typed.
- Print through a real browser (Playwright `page.pdf`) so web fonts render, and
  wait for `document.fonts.ready` or it falls back to Times.
- **Turn off ligatures in code** (`font-variant-ligatures: none`). Fonts such as
  JetBrains Mono draw `--` as one long dash and space out `://`, which reads and
  copies wrongly.
- Look at every page. Let long tables break across pages so a section does not
  leave half a page blank, and avoid a final page holding one line.

---

## 12. Working on a small machine

Most of this was done on an 8 GB laptop.

- One heavy job at a time. Transcription, OCR and a full render each want the
  whole CPU; two at once made each several times slower and pushed swap close
  to full.
- Run long jobs in the background and wait on a completion condition rather than
  polling every few seconds.
- Keep large intermediates out of the way and delete them when done; disk ran
  under 5 GB free.
- Render at roughly real time with `-preset fast`. A 45 minute 1080p film took
  about 35 minutes.

---

## Before calling it done

- [ ] Transcript read end to end; every promise it makes is kept.
- [ ] Correction list applied; names, products and meaning-inverters checked.
- [ ] Captions shifted by the intro; spot-checked on lines the fixes touched.
- [ ] Chapters snapped to segments; any per-chapter notes keyed to the served track.
- [ ] Title names the skill; nothing in the pixels names where it is published.
- [ ] Join verified: durations agree, frame count adds up, full decode clean.
- [ ] Graphics checked on a real frame; none over the face or the content.
- [ ] Privacy sweep run on the source, blurs applied, **and the rendered film OCR'd clean.**
- [ ] Uploads read back.
- [ ] Companion document looked at page by page.
