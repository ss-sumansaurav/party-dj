#!/usr/bin/env python3
"""Party DJ command line.

  python dj.py --setup          set up a new party (birthday or Diwali), its hosts and its YouTube account
  python dj.py --check-config   validate config.yaml and show the party timeline
  python dj.py --sign-in        save YouTube Music sign-in from headers on the clipboard
  python dj.py --no-sign-in     play without a YouTube account (no playlist is saved)
  python dj.py --check-auth     confirm YouTube Music sign-in works
  python dj.py --test           dry run before the party
  python dj.py --songs          see, add or remove the party's songs
  python dj.py                  party night: the whole party, DJ-mixed, in one command
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


def party_files() -> list[tuple[str, str]]:
    """Every party set up here, newest first: (file, "Name, date")."""
    from partydj import event

    files = sorted(Path(".").glob("party-*.yaml"), key=lambda f: f.stat().st_mtime, reverse=True)
    if Path("config.yaml").exists():
        files.append(Path("config.yaml"))
    parties = []
    for f in files:
        try:
            cfg = load_config(f)
        except (ConfigError, OSError):
            continue
        parties.append((str(f), f"{event.title(cfg)}, {cfg.party_date}"))
    return parties


def choose_party() -> str | None:
    """No party file given: ask which party (each set up with --setup), or set up a new one.
    Returns the file, or None to set up a new party."""
    parties = party_files()
    if not parties:
        return None
    print("Which party?")
    for i, (f, name) in enumerate(parties, 1):
        print(f"  {i}. {name}   ({f})")
    print(f"  {len(parties) + 1}. Set up a new party")
    while True:
        try:
            got = input(f"Type 1 to {len(parties) + 1} and press Return [1]: ").strip() or "1"
        except EOFError:
            got = "1"
        if got.isdigit() and 1 <= int(got) <= len(parties) + 1:
            break
    if int(got) == len(parties) + 1:
        return None
    f = parties[int(got) - 1][0]
    print(f"\nNext time you can skip this question with:  python3 dj.py --config {f}\n")
    return f


def cmd_check_config(cfg) -> int:
    from partydj import event

    bday = cfg.start + dt.timedelta(minutes=cfg.birthday_offset_minutes)
    print(f"{event.title(cfg)}, hosted by {event.hosts(cfg)}" + (f", in {cfg.city}" if cfg.city else ""))
    print(f"  {cfg.start:%a %d %b, %I:%M %p} to {cfg.end:%a %d %b, %I:%M %p} ({cfg.duration_minutes} min)")
    print(f"  {'Diwali moment' if cfg.party_type == 'diwali' else 'Birthday block'} at {bday:%I:%M %p}")
    from partydj.ytm import auth_file
    print(f"  YouTube Music sign-in: {auth_file()}")
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

    from partydj.songs import Song

    Song.play_cap = (cfg.song_play_min_seconds + cfg.song_play_max_seconds) // 2  # for planning
    Song.crossfade = cfg.crossfade_seconds
    pool, birthday = load_pool(songs_file, cfg)
    print(f"Looking up {len(pool) + 1} songs on YouTube Music (cached after the first run)...")
    missing = resolver.resolve_all(yt, pool + [birthday] + ([birthday.before] if birthday.before else []))
    found = [s for s in pool if s.video_id]
    if not birthday.video_id:
        print(f"  Birthday song not found: {birthday.label()}. Edit birthday_song in {songs_file}.")
    plan = planner.build_plan(found, birthday, cfg)
    runsheet.timeline(plan, cfg)
    return plan, runsheet.cues(plan, cfg), missing


def save_playlist(yt, cfg, plan) -> str | None:
    """Create (or refill) the private playlist, only after the host says yes."""
    from partydj.playlist import find_existing, fill_playlist

    ids = [s.video_id for s in plan.songs + plan.reserve if s.video_id]
    existing = find_existing(yt, cfg.playlist_title)
    if existing:
        print(f"A playlist called '{cfg.playlist_title}' already exists.")
        if not ask(f"Replace its tracks with this set of {len(ids)} songs?"):
            return None
    elif not ask(f"Create PRIVATE playlist '{cfg.playlist_title}' with {len(ids)} songs?"):
        return None
    return fill_playlist(yt, cfg.playlist_title, ids, existing)


def playlist_matches(yt, playlist_id: str, plan) -> bool:
    """Whether the saved playlist still has the same songs as tonight's list. When songs were
    added or removed since, the host is asked whether to update it."""
    ids = {s.video_id for s in plan.songs + plan.reserve if s.video_id}
    try:
        tracks = yt.get_playlist(playlist_id, limit=None).get("tracks") or []
    except Exception:
        return True  # can't check, so leave it alone
    have = {t.get("videoId") for t in tracks}
    if not (have - ids) and not (ids - have):
        return True
    print(f"The playlist has {len(have - ids)} songs no longer on the list and is missing {len(ids - have)}.")
    return False


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
    everything = plan.songs + plan.reserve
    minutes = len(everything) * 33 // 60
    if ask(f"Play 30 seconds of every song ({len(everything)} songs, about {minutes} minutes)?"):
        from partydj.preview import serve_previews

        blocked = serve_previews(everything)

    songs = plan.songs
    print("\n=== Report ===")
    print(f"Playlist:      {playlist_url or 'not created'}")
    print(f"Run-sheet:     {OUT_RUNSHEET.resolve()}")
    print(f"Songs:         {len(songs)} in the timed set + {len(plan.reserve)} extra at the end"
          f" = {len(songs) + len(plan.reserve)} in the playlist")
    print(f"Announcements: {', '.join(str(p) for p in samples) or 'none'}")
    english = sum(s.is_english for s in songs)
    print(f"Language mix:  {len(songs) - english} Hindi/Punjabi, {english} English (timed set)")
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


SKIP = "skip"   # play without a YouTube account: everything works except saving the private playlist


def sign_in_if_needed(allow_skip: bool = False):
    """Make sure YouTube Music sign-in works, walking the host through it if not.
    Returns True when signed in, False when it failed, or SKIP when the host chose to go without."""
    from partydj.ytm import AuthError, check_auth

    from partydj import ytm

    try:
        name = check_auth()
        print(f"Signed in to YouTube Music as: {name}")
        if not ytm.PARTY_AUTH_FILE or ask(f"Use {name}'s YouTube account for this party?"):
            return True
        print("\nOK, let's sign in with the right account.")
    except AuthError as e:
        print(f"\nYouTube Music sign-in needed ({e})")
    from partydj import ytm
    if ytm.PARTY_AUTH_FILE:
        print("   This party uses its own YouTube account. In Chrome, sign in with THAT account first.")
    if allow_skip:
        print("\nYou can also play WITHOUT signing in. The DJ works exactly the same (songs, voice,")
        print("requests, everything), like the phone app. The only thing missing is the private")
        print("YouTube Music playlist of the night's songs.")
        try:
            pick = input("Press Return to play WITHOUT signing in, or type Y and press Return to sign in: ")
        except EOFError:
            pick = ""
        if pick.strip().lower() not in ("y", "yes"):
            return SKIP
    print("1. In Chrome, open music.youtube.com (signed in).")
    print("2. Press Option-Command-I, click the Network tab, then click Home on the page.")
    print("3. Type browse in the filter box, right-click the first 'browse' row, Copy > Copy as cURL.")
    try:
        input("4. Come back here and press Enter. ")
    except EOFError:
        return False
    return cmd_sign_in() == 0


def cmd_party(cfg, args) -> int:
    """The whole party in one command: sign in, plan, playlist, then the DJ page."""
    from partydj import live, runsheet
    from partydj.playlist import find_existing, url
    from partydj.ytm import client

    from partydj import event

    print(f"=== {event.title(cfg)} DJ ===")
    print(f"Hosts: {event.hosts(cfg)}" + (f"  ·  {cfg.city}" if cfg.city else "") + "\n")
    signed = SKIP if args.no_sign_in else sign_in_if_needed(allow_skip=True)
    if not signed:
        print("Sign-in didn't work, so the DJ plays without signing in (no playlist is saved).")
        signed = SKIP
    if signed == SKIP:
        from ytmusicapi import YTMusic

        print("Playing without a YouTube account (no playlist will be saved).")
        yt = YTMusic()   # finding songs works signed out
    else:
        yt = client()
    plan, cue_list, missing = build_set(cfg, yt, args.songs)
    if signed == SKIP:
        link = None
    else:
        existing = find_existing(yt, cfg.playlist_title)
        link = url(existing) if existing and playlist_matches(yt, existing, plan) else save_playlist(yt, cfg, plan)
    OUT_RUNSHEET.write_text(runsheet.to_markdown(plan, cue_list, cfg, link), encoding="utf-8")
    if missing:
        print(f"{len(missing)} songs weren't found on YouTube Music and are left out.")
    try:
        saved = live.saved_party(cfg)
        resume = None
        if saved and saved.get("started"):
            played = len(saved.get("history", []))
            if getattr(args, "app", False) or ask(
                    f"The DJ stopped a few minutes ago after {played} songs. Pick up where it left off?"):
                resume = saved
        live.run(cfg, yt, plan, link, args.config, args.songs, resume=resume)
    except KeyboardInterrupt:
        print("\nParty over! Vibe scores are in mood_log.csv.")
    return 0


def cmd_songs(cfg, args) -> int:
    """Open the songs page on its own, to see, add or remove songs before the party."""
    import webbrowser

    from partydj import live
    from partydj.songbook import Songbook, serve_alone
    from partydj.ytm import AuthError, client

    try:
        yt = client()
    except AuthError:
        from ytmusicapi import YTMusic

        yt = YTMusic()  # searching works signed out
    book = Songbook(args.songs, yt)
    from partydj import event

    book.page_title = f"{event.title(cfg)} songs"
    try:
        link = serve_alone(book, live.PORT)
    except OSError:  # the party is running: its page has the songs list too
        link = f"http://localhost:{live.PORT}/songs"
        webbrowser.open(link)
        print(f"The DJ is running, so the songs page opened from it: {link}")
        return 0
    webbrowser.open(link)
    print(f"The songs page is open: {link}\nPress Ctrl-C here when you're done.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSaved. Your changes are in songs.yaml and are used the next time you run python dj.py.")
    return 0


def _answer(question: str, default: str = "") -> str:
    try:
        got = input(f"{question}" + (f" [{default}]" if default else "") + ": ").strip()
    except EOFError:
        got = ""
    return got or default


def cmd_setup(args) -> int:
    """Ask about a new party and save its own settings file (and, if wanted, its own YouTube sign-in)."""
    import re

    import yaml

    from partydj import ytm

    print("Let's set up a new party. Press Enter to keep the answer in [brackets].\n")
    kind = _answer("What kind of party? 1 = Birthday, 2 = Diwali", "2")
    diwali = kind.strip().lower() in ("2", "diwali", "d")
    host = _answer("Host's name")
    while not host:
        host = _answer("Host's name (needed)")
    co_host = _answer("Co-host's name (Enter if none)")
    person = "" if diwali else _answer("Whose birthday is it?")
    city = _answer("Which city is the party in? (e.g. Melbourne)")
    while True:
        date = _answer("Party date, like 2026-11-08", f"{dt.date.today():%Y-%m-%d}")
        start = _answer("Start time, 24-hour clock like 19:00", "19:00")
        hours = _answer("How many hours?", "5")
        moment = _answer("Time for the Diwali moment (diyas, wishes, the Diwali songs), like 21:00", "21:00") \
            if diwali else "00:00"
        try:
            dt.date.fromisoformat(date)
            for t in (start, moment):
                dt.datetime.strptime(t, "%H:%M")
            minutes = int(float(hours) * 60)
            break
        except ValueError:
            print("Something didn't look right there. Let's try those again.\n")

    base = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8")) if Path("config.yaml").exists() else {}
    slug = re.sub(r"[^a-z0-9]+", "-", f"{'diwali' if diwali else 'birthday'} {host}".lower()).strip("-")
    from partydj.event import party_settings

    cfg = party_settings(base, diwali, host, co_host, person, city, date, start, minutes, moment,
                         auth_file=f"browser-{slug}.json")
    out = Path(f"party-{slug}.yaml")
    out.write_text("# Made by: python dj.py --setup. Edit freely.\n" + yaml.safe_dump(cfg, sort_keys=False,
                   allow_unicode=True), encoding="utf-8")
    try:
        load_config(out)
    except ConfigError as e:
        print(f"\nSaved {out}, but it needs a fix: {e}\nOpen {out} in TextEdit, fix it, and run: python dj.py --config {out} --check-config")
        return 1
    print(f"\nSaved this party's settings in {out}.")
    print(f"It has its own YouTube Music sign-in ({cfg['youtube_auth_file']}); your usual account isn't used.")
    ytm.PARTY_AUTH_FILE = cfg["youtube_auth_file"]
    if ask("Sign in to the YouTube Music account for this party now?"):
        if not sign_in_if_needed():
            print("Sign-in didn't work. It will ask again when you start the party.")
    print(f"\nOn party night, run:\n  python dj.py --config {out}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AI DJ for a home party: a birthday or Diwali")
    p.add_argument("--config", default=None, help="the party's file; left out, it asks which party")
    p.add_argument("--songs-file", dest="songs", default="songs.yaml")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--setup", action="store_true", help="set up a new party: birthday or Diwali")
    mode.add_argument("--check-config", action="store_true")
    mode.add_argument("--sign-in", action="store_true")
    mode.add_argument("--check-auth", action="store_true")
    mode.add_argument("--test", action="store_true", help="dry run before the party")
    mode.add_argument("--songs", dest="songs_page", action="store_true", help="see, add or remove party songs")
    mode.add_argument("--live", action="store_true", help="same as no option: run the party")
    p.add_argument("--app", action="store_true",
                   help="started by the Party DJ Mac app: no questions (plays without signing in, "
                        "and carries on a party that stopped in the last 30 minutes)")
    mode.add_argument("--list-parties", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--no-sign-in", action="store_true",
                   help="play without a YouTube account (everything works; no playlist is saved)")
    mode.add_argument("--voice-pack", action="store_true", help="record the DJ's lines in a human voice (ElevenLabs)")
    args = p.parse_args(argv)
    if args.setup:
        return cmd_setup(args)
    if args.list_parties:   # for the Mac app: one party per line, "file<TAB>name"
        for f, name in party_files():
            print(f"{f}\t{name}")
        return 0
    if args.app:
        args.no_sign_in = True
        import signal   # the app runs the DJ in the background, where Stop must still end it neatly

        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, signal.default_int_handler)
    if args.config is None:
        args.config = choose_party()
        if args.config is None:
            return cmd_setup(args)

    try:
        cfg = load_config(args.config)
    except (ConfigError, OSError) as e:
        if args.sign_in:
            return cmd_sign_in()
        print(f"Config problem: {e}")
        return 1
    from partydj import ytm

    ytm.PARTY_AUTH_FILE = cfg.youtube_auth_file or None  # this party's own account, if it has one
    if args.sign_in:
        return cmd_sign_in()
    from partydj import announcer

    announcer.DJ_VOICE = cfg.dj_voice
    announcer.SAY_AS.update(cfg.name_pronunciations)
    announcer.HINDI_VOICE = cfg.hindi_voice
    if args.voice_pack:
        from partydj import voicepack

        return voicepack.record(cfg)
    if args.check_config:
        return cmd_check_config(cfg)
    if args.check_auth:
        return cmd_check_auth(cfg)
    if args.songs_page:
        return cmd_songs(cfg, args)
    if args.test:
        return cmd_test(cfg, args)
    return cmd_party(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
