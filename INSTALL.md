# Install (instructions for an AI agent)

A user asked you to install the video-edit skill. Do this:

1. Clone the repo somewhere stable (not a temp folder), for example:

   ```bash
   git clone https://github.com/yerinsabraham/video-edit-skill ~/.video-edit-skill
   ```

   If it already exists, update it instead: `git -C ~/.video-edit-skill pull --ff-only`.

2. Install for every agent on this machine (Claude Code and/or Codex):

   ```bash
   python3 ~/.video-edit-skill/install.py --force
   ```

3. Check the tools and tell the user, in plain words, what is missing:

   ```bash
   python3 ~/.claude/skills/video-edit/shared/scripts/setup.py
   ```

   (Codex: `~/.codex/skills/video-edit/...`.) Offer to install what is missing:
   `setup.py --install` (about two minutes; it prints, rather than runs,
   anything that needs admin rights).

4. Tell the user it is ready: drop clips in their Downloads folder and type
   `/video-edit I just dropped 5 clips in my downloads` (Claude Code may need a
   restart, or `/reload-plugins`, to pick up a new skill).

## Update

"Update the video-edit skill" means:

```bash
python3 ~/.video-edit-skill/install.py --update
```

## Claude Code plugin (alternative)

```text
/plugin marketplace add yerinsabraham/video-edit-skill
/plugin install video-edit@video-edit-skill
```

## Uninstall

```bash
rm -rf ~/.claude/skills/video-edit ~/.codex/skills/video-edit ~/.video-edit-skill
```

Tools the skill installed live in `~/.cache/video-edit` (safe to delete);
preferences in `~/.config/video-edit`.
