#!/usr/bin/env python3
"""Party DJ command line.

  python dj.py check-config   validate config.yaml and show the party timeline
  python dj.py check-auth     confirm YouTube Music sign-in works
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from partydj.config import ConfigError, load_config


def cmd_check_config(args) -> int:
    try:
        cfg = load_config(args.config)
    except (ConfigError, OSError) as e:
        print(f"Config problem: {e}")
        return 1
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


def cmd_check_auth(args) -> int:
    from partydj.ytm import AuthError, check_auth

    try:
        name = check_auth()
    except AuthError as e:
        print(e)
        return 1
    print(f"Signed in to YouTube Music as: {name}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="AI DJ for a home birthday party")
    p.add_argument("--config", default="config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-config").set_defaults(func=cmd_check_config)
    sub.add_parser("check-auth").set_defaults(func=cmd_check_auth)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
