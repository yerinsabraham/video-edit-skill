# Security

Please report security issues privately through GitHub's
[security advisories](https://github.com/yerinsabraham/video-edit-skill/security/advisories/new)
rather than a public issue.

## What the skill does with your data

- Footage, transcripts, faces, and voices stay on your computer.
- Network use: installing tools (Homebrew, evermeet.cx or johnvansickle.com
  static ffmpeg, the whisper.cpp model from Hugging Face), HyperFrames and a
  headless Chrome from npm on the first motion render (with telemetry disabled),
  product logos from Simple Icons via jsDelivr, and, only with your token, Apify
  for your public Instagram reels and profile stats.
- An Apify token is stored in `~/.config/video-edit/profile.json` with
  owner-only permissions.
