"""Entry point for the Android app: the same party DJ, run inside the phone.

The app's screen is a web view of the same DJ page the Mac uses. There's no Terminal on the
phone, so it first shows a setup page (birthday or Diwali, the hosts, the times), then plans
the night, makes the announcements and starts the page, reporting progress through status()
for the app's loading screen.
"""
from __future__ import annotations

import json
import os
import shutil
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

STATUS = {"text": "Starting the DJ…", "ready": False, "error": None, "url": None, "setup": None}
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


SETUP_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Set up the party</title><style>
body{margin:0;background:#0D0D12;color:#fff;font-family:system-ui,sans-serif}
main{max-width:520px;margin:0 auto;padding:20px 16px 40px}
h1{color:#FF2D7A;font-size:24px;margin:8px 0 4px} p{color:#aab}
label{display:block;margin:14px 0 4px;color:#ccd;font-size:15px}
input{width:100%;box-sizing:border-box;font-size:18px;padding:12px;border-radius:10px;border:0;background:#1d1d27;color:#fff}
.kind{display:flex;gap:10px} .kind label{flex:1;margin:0;padding:14px;border-radius:12px;background:#1d1d27;text-align:center;font-size:18px}
.kind input{width:auto;margin-right:8px} .row{display:flex;gap:10px} .row>div{flex:1}
button{margin-top:22px;width:100%;font-size:20px;padding:16px;border:0;border-radius:14px;background:#FF2D7A;color:#fff;font-weight:700}
.err{background:#5a1a2a;padding:12px;border-radius:10px;margin-top:12px}
</style></head><body><main>
<h1>🎧 Set up the party</h1><p>Fill this in, then tap Start. The app remembers it for next time.</p>
__ERROR__
<form method="post" action="/setup">
<div class="kind"><label><input type="radio" name="kind" value="birthday" __BDAY__>🎂 Birthday</label>
<label><input type="radio" name="kind" value="diwali" __DIWALI__>🪔 Diwali</label></div>
<label>Host's name</label><input name="host" required value="__HOST__">
<label>Co-host's name (optional)</label><input name="co_host" value="__CO_HOST__">
<div id="bd"><label>Whose birthday is it?</label><input name="person" value="__PERSON__"></div>
<label>City (optional, the DJ says it)</label><input name="city" value="__CITY__" placeholder="e.g. Melbourne">
<label>Party date</label><input type="date" name="date" required value="__DATE__">
<div class="row"><div><label>Starts at</label><input type="time" name="start" required value="__START__"></div>
<div><label>How many hours</label><input type="number" name="hours" min="1" max="10" step="0.5" required value="__HOURS__"></div></div>
<div id="dw"><label>🪔 Diwali moment (countdown and the Diwali songs)</label><input type="time" name="moment" value="__MOMENT__"></div>
<p id="bdnote">🎂 The cake cutting is at 12 midnight.</p>
<button type="submit">▶ Start the DJ</button></form></main>
<script>
function show(){ const d = document.querySelector('input[value=diwali]').checked;
  document.getElementById('dw').style.display = d ? '' : 'none';
  document.getElementById('bd').style.display = d ? 'none' : '';
  document.getElementById('bdnote').style.display = d ? 'none' : ''; }
document.querySelectorAll('input[name=kind]').forEach(r => r.onchange = show); show();
</script></body></html>"""


def _ask_party() -> str:
    """Show the setup page on the phone and wait for Start. Returns the party's settings file."""
    import datetime as dt
    import html
    import http.server
    import threading
    import urllib.parse

    import yaml

    from .config import ConfigError, load_config
    from .event import party_settings

    base = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8")) or {}
    saved = Path("party.yaml")
    last = yaml.safe_load(saved.read_text(encoding="utf-8")) if saved.exists() else {}
    last = last or {}
    done = threading.Event()

    def form(error: str = "", a: dict | None = None) -> bytes:
        a = a or {}
        get = lambda k, d="": html.escape(str(a.get(k, d)))
        diwali = a.get("kind", last.get("party_type", "diwali")) == "diwali"
        hours = round(int(last.get("duration_minutes", 300)) / 60, 1)
        page = SETUP_PAGE
        for k, v in (("__ERROR__", f'<div class="err">{html.escape(error)}</div>' if error else ""),
                     ("__BDAY__", "" if diwali else "checked"), ("__DIWALI__", "checked" if diwali else ""),
                     ("__HOST__", get("host", last.get("host_name", ""))),
                     ("__CO_HOST__", get("co_host", last.get("co_host_name", ""))),
                     ("__PERSON__", get("person", last.get("birthday_person_name", ""))),
                     ("__CITY__", get("city", last.get("city", ""))),
                     ("__DATE__", get("date", f"{dt.date.today():%Y-%m-%d}")),
                     ("__START__", get("start", last.get("start_time", "19:00"))),
                     ("__HOURS__", get("hours", f"{hours:g}")),
                     ("__MOMENT__", get("moment", last.get("diwali_moment_time", "21:00")))):
            page = page.replace(k, v)
        return page.encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def _page(self, body: bytes):
            from . import remote

            body = remote.add(body)   # TV remote: arrow keys move between the boxes and buttons
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._page(form())

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            a = {k: v[0].strip() for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode()).items()}
            diwali = a.get("kind") == "diwali"
            try:
                minutes = int(float(a.get("hours") or 5) * 60)
                if not a.get("host"):
                    raise ConfigError("Please fill in the host's name.")
                if not diwali and not a.get("person"):
                    raise ConfigError("Please fill in whose birthday it is.")
                cfg = party_settings(base, diwali, a["host"], a.get("co_host", ""), a.get("person", ""),
                                     a.get("city", ""), a.get("date", ""), a.get("start", ""), minutes,
                                     a.get("moment", ""))
                saved.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
                load_config(saved)
            except (ConfigError, ValueError) as e:
                self._page(form(str(e), a))
                return
            self._page(b"<body style='background:#0D0D12;color:#fff;font:20px system-ui;padding:40px'>Starting the DJ...</body>")
            done.set()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    STATUS["setup"] = "http://127.0.0.1:8765/"
    print("Setup page is open")
    done.wait()
    server.shutdown()
    server.server_close()
    STATUS["setup"] = None
    return str(saved)


def _seed_tracks():
    """Add the app's bundled song look-ups to the phone's own cache (the phone's own entries win)."""
    import json

    from . import resolver

    try:
        bundled = json.loads((HERE / "tracks.json").read_text())
    except (OSError, ValueError):
        return
    try:
        mine = json.loads(resolver.CACHE.read_text()) if resolver.CACHE.exists() else {}
    except ValueError:
        mine = {}
    resolver.CACHE.parent.mkdir(exist_ok=True)
    resolver.CACHE.write_text(json.dumps({**bundled, **mine}, indent=1))


def _start(files_dir: str):
    os.chdir(files_dir)
    # config.yaml comes with the app; songs.yaml is copied once so songs-page edits are kept.
    shutil.copy(HERE / "config.yaml", "config.yaml")
    if not Path("songs.yaml").exists():
        shutil.copy(HERE / "songs.yaml", "songs.yaml")
    else:  # an app update: bring in its new songs, keeping the host's own changes
        from .songbook import Songbook
        try:
            added = Songbook("songs.yaml").merge_from(HERE / "songs.yaml")
            if added:
                print(f"Added {added} new songs from the app update.")
        except Exception as e:
            print(f"(couldn't bring in the new songs: {e})")

    from . import announcer, live, planner, resolver, runsheet
    from .config import load_config
    from .songs import Song, load_pool

    config_file = _ask_party()  # birthday or Diwali, the hosts and the times, asked on the phone
    _say("Starting the DJ…")
    cfg = load_config(config_file)
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

    _seed_tracks()  # songs looked up when the app was built: no need to search for them again
    resolver.resolve_all(yt, pool + [birthday] + ([birthday.before] if birthday.before else []), progress=progress)
    found = [s for s in pool if s.video_id]
    plan = planner.build_plan(found, birthday, cfg)
    runsheet.timeline(plan, cfg)
    _say("Warming up the DJ voice…")

    def ready(url):
        STATUS["url"] = url
        STATUS["ready"] = True
        _say("Ready")

    live.run(cfg, yt, plan, None, config_file, "songs.yaml", open_browser=False, on_ready=ready,
             public=False, resume=live.saved_party(cfg))  # Android can't run the tunnel program; guests use the Wi-Fi
