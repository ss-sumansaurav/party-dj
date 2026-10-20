#!/usr/bin/env python3
"""Party DJ command line.

  python dj.py --check-config   validate config.yaml and show the party timeline
  python dj.py --sign-in        save YouTube Music sign-in from headers on the clipboard
  python dj.py --check-auth     confirm YouTube Music sign-in works
  python dj.py --test           10-minute dry run before the party
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
import warnings
from pathlib import Path

# The Mac's built-in Python uses LibreSSL; urllib3 warns about it but works fine.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

from partydj.config import ConfigError, load_config

OUT_RUNSHEET = Path("run_sheet.md")
OUT_ANNOUNCE = Path("announcements")


def ask(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def cmd_check_config(cfg) -> int:
    bday = cfg.start + dt.timedelta(minutes=cfg.birthday_offset_minutes)
    print(f"Party for {cfg.birthday_person_name}, hosted by {cfg.host_name}")
    print(f"  {cfg.start:%a %d %b, %I:%M %p} to {cfg.end:%a %d %b, %I:%M %p} ({cfg.duration_minutes} min)")
    print(f"  Birthday block at {bday:%I:%M %p}")
    print(f"  Hindi {cfg.hindi_ratio:.0%} / English {cfg.english_ratio:.0%}")
    print(f"  Announcement every {cfg.announcement_interval_songs} songs, vibe check every {cfg.vibe_check_minutes} min")
    print(f"  Playlist title: {cfg.playlist_title}")
    if cfg.blocked_artists or cfg.blocked_tracks:
        print(f"  Blocked: {len(cfg.blocked_artists)} artists, {len(cfg.blocked_tracks)} tracks")
    return 0


def headers_from_curl(text: str) -> str:
    """Turn Chrome's 'Copy as cURL' into 'name: value' header lines."""
    import shlex

    words = shlex.split(text.replace("\\\n", " "))
    lines = []
    for flag, value in zip(words, words[1:]):
        if flag in ("-H", "--header"):
            lines.append(value)
        elif flag in ("-b", "--cookie"):
            lines.append(f"cookie: {value}")
    return "\n".join(lines)


def cmd_sign_in() -> int:
    """Read copied request headers from the Mac clipboard and save them, without printing them."""
    import subprocess

    from ytmusicapi.setup import setup_browser

    from partydj.ytm import auth_file

    try:
        headers = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print("Couldn't read the clipboard (pbpaste). Run: ytmusicapi browser --file browser.json")
        return 1
    if headers.lstrip().startswith("curl "):
        headers = headers_from_curl(headers)
    if "cookie" not in headers.lower():
        print("The clipboard doesn't hold the right headers yet. In the browser's Network tab,\n"
              "right-click a 'browse' request, choose Copy > Copy as cURL, and try again.")
        return 1
    if "sapisidhash" not in headers.lower():
        print("Those headers have no sign-in in them. Make sure you're signed in to YouTube Music,\n"
              "then copy the headers of a 'browse' request (method POST) and try again.")
        return 1
    path = auth_file()
    try:
        setup_browser(str(path), headers)
    except Exception as e:
        print(f"Couldn't read those headers ({type(e).__name__}). Copy them again and retry.")
        return 1
    path.chmod(0o600)
    print(f"Saved sign-in to {path}. Checking it...")
    return cmd_check_auth(None)


def cmd_check_auth(cfg) -> int:
    from partydj.ytm import AuthError, check_auth

    try:
        name = check_auth()
    except AuthError as e:
        print(e)
        return 1
    print(f"Signed in to YouTube Music as: {name}")
    return 0


def build_set(cfg, yt, songs_file: str):
    """Resolve the pool on YouTube Music and plan the night. Returns (plan, cues, missing)."""
    from partydj import planner, resolver, runsheet
    from partydj.songs import load_pool

    pool, birthday = load_pool(songs_file, cfg)
    print(f"Looking up {len(pool) + 1} songs on YouTube Music (cached after the first run)...")
    missing = resolver.resolve_all(yt, pool + [birthday])
    found = [s for s in pool if s.video_id]
    if not birthday.video_id:
        print(f"  Birthday song not found: {birthday.label()}. Edit birthday_song in {songs_file}.")
    plan = planner.build_plan(found, birthday, cfg)
    runsheet.timeline(plan, cfg)
    return plan, runsheet.cues(plan, cfg), missing


def save_playlist(yt, cfg, plan) -> str | None:
    """Create (or refill) the private playlist, only after the host says yes."""
    from partydj.playlist import find_existing, fill_playlist

    ids = [s.video_id for s in plan.songs if s.video_id]
    existing = find_existing(yt, cfg.playlist_title)
    if existing:
        print(f"A playlist called '{cfg.playlist_title}' already exists.")
        if not ask(f"Replace its tracks with this set of {len(ids)} songs?"):
            return None
    elif not ask(f"Create PRIVATE playlist '{cfg.playlist_title}' with {len(ids)} songs?"):
        return None
    return fill_playlist(yt, cfg.playlist_title, ids, existing)


def cmd_test(cfg, args) -> int:
    from partydj import announcer, runsheet
    from partydj.ytm import AuthError, check_auth, client

    started = time.monotonic()
    print("=== Party DJ test run ===\n")
    signed_in = True
    try:
        print(f"Signed in as: {check_auth()}")
        yt = client()
    except AuthError as e:
        print(f"Not signed in ({e})\nContinuing without a playlist: search works signed out.")
        from ytmusicapi import YTMusic

        yt, signed_in = YTMusic(), False

    plan, cue_list, missing = build_set(cfg, yt, args.songs)

    playlist_url = save_playlist(yt, cfg, plan) if signed_in else None
    OUT_RUNSHEET.write_text(runsheet.to_markdown(plan, cue_list, cfg, playlist_url), encoding="utf-8")
    print("\n" + OUT_RUNSHEET.read_text(encoding="utf-8"))

    print("Making two sample announcements...")
    samples = []
    for name, cue in (("sample_opening", cue_list[0]),
                      ("sample_shoutout", next(c for c in cue_list if c.kind == "shoutout"))):
        try:
            samples.append(announcer.speak_to_file(cue.text, OUT_ANNOUNCE / name))
        except RuntimeError as e:
            print(f"  {e}")

    blocked = []
    if samples and ask("Play the two sample announcements on the speaker now?"):
        for path in samples:
            print(f"  Playing {path.name}")
            announcer.play(path)
    minutes = len(plan.songs) * 33 // 60
    if ask(f"Play 30 seconds of every song ({len(plan.songs)} songs, about {minutes} minutes)?"):
        from partydj.preview import serve_previews

        blocked = serve_previews(plan.songs)

    songs = plan.songs
    print("\n=== Report ===")
    print(f"Playlist:      {playlist_url or 'not created'}")
    print(f"Run-sheet:     {OUT_RUNSHEET.resolve()}  ({len(songs)} songs)")
    print(f"Announcements: {', '.join(str(p) for p in samples) or 'none'}")
    english = sum(s.is_english for s in songs)
    print(f"Language mix:  {len(songs) - english} Hindi/Punjabi, {english} English")
    if missing:
        print(f"Not found on YouTube Music ({len(missing)}), left out:")
        for s in missing:
            print(f"  - {s.label()}")
    else:
        print("Every song was found.")
    if blocked:
        print(f"Wouldn't play on the preview page ({len(blocked)}); they still play in YouTube Music:")
        for s in blocked:
            print(f"  - {s.label()}  {s.url}")
    print(f"Took {time.monotonic() - started:.0f} s.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AI DJ for a home birthday party")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--songs", default="songs.yaml")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-config", action="store_true")
    mode.add_argument("--sign-in", action="store_true")
    mode.add_argument("--check-auth", action="store_true")
    mode.add_argument("--test", action="store_true", help="10-minute dry run")
    args = p.parse_args(argv)
    if args.sign_in:
        return cmd_sign_in()

    try:
        cfg = load_config(args.config)
    except (ConfigError, OSError) as e:
        print(f"Config problem: {e}")
        return 1
    if args.check_config:
        return cmd_check_config(cfg)
    if args.check_auth:
        return cmd_check_auth(cfg)
    return cmd_test(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
