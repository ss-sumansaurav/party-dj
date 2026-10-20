"""Entry point for the Android app: the same party DJ, run inside the phone.

The app's screen is a web view of the same DJ page the Mac uses. There's no Terminal on the
phone, so nothing here asks questions: it plans the night, makes the announcements and
starts the page, reporting progress through status() for the app's loading screen.
"""
from __future__ import annotations

import json
import os
import shutil
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

STATUS = {"text": "Starting the DJ…", "ready": False, "error": None, "url": None}
HERE = Path(__file__).parent


def status() -> str:
    return json.dumps(STATUS)


def _say(text: str):
    print(text)
    STATUS["text"] = text


def start(files_dir: str):
    try:
        _start(files_dir)
    except Exception as e:  # shown on the app's loading screen
        traceback.print_exc()
        STATUS["error"] = f"{type(e).__name__}: {e}"


def _start(files_dir: str):
    os.chdir(files_dir)
    # config.yaml comes with the app; songs.yaml is copied once so songs-page edits are kept.
    shutil.copy(HERE / "config.yaml", "config.yaml")
    if not Path("songs.yaml").exists():
        shutil.copy(HERE / "songs.yaml", "songs.yaml")

    from . import announcer, live, planner, resolver, runsheet
    from .config import load_config
    from .songs import Song, load_pool

    cfg = load_config("config.yaml")
    announcer.DJ_VOICE = cfg.dj_voice
    announcer.SAY_AS.update(cfg.name_pronunciations)
    announcer.HINDI_VOICE = cfg.hindi_voice

    from ytmusicapi import YTMusic

    yt = None
    if Path("browser.json").exists():
        try:
            from .ytm import client

            yt = client()
        except Exception:
            yt = None
    yt = yt or YTMusic()  # song search works without signing in

    Song.play_cap = (cfg.song_play_min_seconds + cfg.song_play_max_seconds) // 2  # for planning
    Song.crossfade = cfg.crossfade_seconds
    pool, birthday = load_pool("songs.yaml", cfg)
    total = len(pool) + 1
    _say(f"Finding {total} songs on YouTube Music…")
    def progress(msg):  # msg is like "  looked up 40/138"
        _say("Finding songs on YouTube Music… " + msg.split()[-1].replace("/", " of "))

    resolver.resolve_all(yt, pool + [birthday], progress=progress)
    found = [s for s in pool if s.video_id]
    plan = planner.build_plan(found, birthday, cfg)
    runsheet.timeline(plan, cfg)
    _say("Warming up the DJ voice…")

    def ready(url):
        STATUS["url"] = url
        STATUS["ready"] = True
        _say("Ready")

    live.run(cfg, yt, plan, None, "config.yaml", "songs.yaml", open_browser=False, on_ready=ready,
             public=False, resume=live.saved_party(cfg))  # Android can't run the tunnel program; guests use the Wi-Fi
