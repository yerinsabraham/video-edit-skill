#!/usr/bin/env python3
"""Optional: pull the creator's reels and profile stats from Instagram via Apify.

    instagram.py <project> profile [--handle yourhandle]
    instagram.py <project> reels [--handle yourhandle] [--limit 6]

Needs a free Apify account token, saved once with
`prefs.py set apifyToken=...` or exported as APIFY_TOKEN. Uses Apify's public
Instagram scraper actor. Results land in the project (work/instagram/), never in
the skill. Without a token, drop reel files into work/instagram/reels/ yourself.

This is the only feature that sends anything to a third party: the handle (a
public profile) goes to Apify. No footage or transcript ever leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from _common import SkillError, download, ensure_project, fail, write_json
from prefs import load as load_profile

ACTOR = "apify~instagram-scraper"
ENDPOINT = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}&timeout=240"


def token() -> str:
    value = os.environ.get("APIFY_TOKEN") or load_profile().get("apifyToken", "")
    if not value:
        raise SkillError("No Apify token. Save one with: prefs.py set apifyToken=<token> (free at apify.com), or drop reel files into work/instagram/reels/.")
    return value


def run_actor(payload: dict) -> list[dict]:
    request = urllib.request.Request(
        ENDPOINT.format(actor=ACTOR, token=token()),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # python.org builds on macOS may lack CA certificates; retry through curl.
        import subprocess

        from _common import find_exe

        curl = find_exe("curl")
        if not curl:
            raise SkillError(f"Apify request failed: {exc}") from exc
        result = subprocess.run(
            [curl, "-sf", "-X", "POST", "-H", "Content-Type: application/json", "--max-time", "300",
             "-d", json.dumps(payload), ENDPOINT.format(actor=ACTOR, token=token())],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            raise SkillError(f"Apify request failed: {exc}") from exc
        return json.loads(result.stdout or "[]")


def handle_of(arg: str | None) -> str:
    h = (arg or load_profile().get("handle", "")).lstrip("@")
    if not h:
        raise SkillError("No Instagram handle. Pass --handle or run prefs.py set handle=<yours>.")
    return h


def fetch_profile(project: Path, handle: str) -> dict:
    items = run_actor({"directUrls": [f"https://www.instagram.com/{handle}/"], "resultsType": "details", "resultsLimit": 1})
    if not items:
        raise SkillError(f"Apify returned nothing for @{handle}")
    d = items[0]
    out_dir = project / "work" / "instagram"
    out_dir.mkdir(parents=True, exist_ok=True)
    avatar = ""
    if d.get("profilePicUrlHD") or d.get("profilePicUrl"):
        try:
            avatar = str(download(d.get("profilePicUrlHD") or d["profilePicUrl"], out_dir / "avatar.jpg"))
        except SkillError:
            pass
    info = {
        "handle": handle,
        "name": d.get("fullName") or handle,
        "bio": (d.get("biography") or "").split("\n")[0][:80],
        "followers": int(d.get("followersCount") or 0),
        "following": int(d.get("followsCount") or 0),
        "posts": int(d.get("postsCount") or 0),
        "avatar": avatar,
    }
    write_json(out_dir / "profile.json", info)
    return info


def fetch_reels(project: Path, handle: str, limit: int) -> list[str]:
    items = run_actor({"directUrls": [f"https://www.instagram.com/{handle}/"], "resultsType": "posts", "resultsLimit": limit * 3})
    out_dir = project / "work" / "instagram" / "reels"
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for item in items:
        url = item.get("videoUrl")
        if not url:
            continue
        target = out_dir / f"{item.get('shortCode') or len(saved)}.mp4"
        try:
            saved.append(str(download(url, target)))
        except SkillError:
            continue
        if len(saved) >= limit:
            break
    return saved


def local_reels(project: Path) -> list[str]:
    folder = project / "work" / "instagram" / "reels"
    return sorted(str(p) for p in folder.glob("*") if p.suffix.lower() in {".mp4", ".mov", ".m4v", ".jpg", ".png"}) if folder.exists() else []


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull reels and profile stats from Instagram via Apify (optional).")
    parser.add_argument("project")
    parser.add_argument("what", choices=["profile", "reels"])
    parser.add_argument("--handle")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    try:
        project = ensure_project(Path(args.project))
        handle = handle_of(args.handle)
        if args.what == "profile":
            info = fetch_profile(project, handle)
            print(f"@{handle}: {info['followers']} followers, {info['posts']} posts")
        else:
            saved = fetch_reels(project, handle, args.limit)
            print(f"Saved {len(saved)} reel(s) to work/instagram/reels/")
        return 0
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
