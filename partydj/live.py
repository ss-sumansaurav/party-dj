"""Party-night mode: announcements on cue, the birthday block, vibe checks, blocks and requests.

The host plays the playlist in YouTube Music. This follows along by checking the account's
listening history, so each announcement plays when the song it introduces starts. If the
history can't be read, it falls back to the run-sheet's estimated times.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import http.server
import json
import queue
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

from . import announcer
from .config import load_config
from .songs import is_blocked, parse_request

MOOD_LOG = Path("mood_log.csv")
POLL_SECONDS = 15


class Speaker:
    """Plays announcements one at a time in the background, so nothing overlaps."""

    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, path: Path, label: str):
        print(f"  🎤 {label}")
        self.q.put(path)

    def say_text(self, text: str, name: str):
        try:
            self.say(announcer.speak_to_file(text, Path("announcements") / name), text)
        except RuntimeError as e:
            print(f"  (couldn't make that announcement: {e})")

    def _run(self):
        while True:
            path = self.q.get()
            try:
                announcer.play(path)
            except RuntimeError as e:
                print(f"  {e}")


class Host:
    """What the host's control page shows, and what it sends back."""

    def __init__(self):
        self.lock = threading.Lock()
        self.now = "Waiting for the first song..."
        self.notices: list[str] = []
        self.vibe_due = False
        self.scores: list[int] = []
        self.pending_scores: list[int] = []
        self.announce_now = False

    def notice(self, text: str):
        print(f"  ➜ {text}")
        with self.lock:
            self.notices = ([f"{dt.datetime.now():%I:%M %p}: {text}"] + self.notices)[:8]

    def state(self) -> dict:
        with self.lock:
            return {"now": self.now, "notices": self.notices, "vibe_due": self.vibe_due,
                    "scores": self.scores[-6:]}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Party DJ</title>
<style>
 body{font-family:-apple-system,sans-serif;background:#111;color:#eee;text-align:center;margin:0;padding:16px}
 .row{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin:14px 0}
 .v{font-size:40px;width:110px;height:110px;border-radius:20px;border:0;color:#fff;cursor:pointer}
 .v small{display:block;font-size:14px}
 #due{background:#e91e63;padding:12px;border-radius:12px;font-size:22px}
 #now{font-size:22px;margin:10px} ul{list-style:none;padding:0;text-align:left;max-width:640px;margin:auto}
 li{background:#222;margin:6px 0;padding:10px;border-radius:8px} .a{font-size:18px;padding:12px 22px;border-radius:12px;border:0;background:#444;color:#fff}
</style></head><body>
<h1>🎧 Party DJ</h1><div id="now"></div>
<div id="due" hidden>Vibe check! How's the crowd?</div>
<div class="row">
 <button class="v" style="background:#3949ab" onclick="vibe(1)">1<small>chill</small></button>
 <button class="v" style="background:#00897b" onclick="vibe(2)">2</button>
 <button class="v" style="background:#7cb342" onclick="vibe(3)">3</button>
 <button class="v" style="background:#fb8c00" onclick="vibe(4)">4</button>
 <button class="v" style="background:#e53935" onclick="vibe(5)">5<small>on fire</small></button>
</div>
<div class="row"><button class="a" onclick="fetch('/announce',{method:'POST'})">🎤 Say something now</button></div>
<div id="scores"></div><h3>For you</h3><ul id="notices"></ul>
<script>
function vibe(n){ fetch('/vibe?score='+n,{method:'POST'}).then(load); }
function load(){ fetch('/state').then(r=>r.json()).then(s=>{
  document.getElementById('now').textContent = s.now;
  document.getElementById('due').hidden = !s.vibe_due;
  document.getElementById('scores').textContent = s.scores.length ? 'Recent vibe scores: ' + s.scores.join(', ') : '';
  document.getElementById('notices').innerHTML = s.notices.map(n=>'<li>'+n+'</li>').join('');
});}
load(); setInterval(load, 4000);
</script></body></html>"""


def serve_page(host: Host) -> str:
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body=b"", kind="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/state"):
                self._send(200, json.dumps(host.state()).encode(), "application/json")
            else:
                self._send(200, PAGE.encode())

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            if u.path == "/vibe":
                score = int(urllib.parse.parse_qs(u.query).get("score", ["0"])[0])
                if 1 <= score <= 5:
                    with host.lock:
                        host.pending_scores.append(score)
            elif u.path == "/announce":
                with host.lock:
                    host.announce_now = True
            self._send(204)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return "http://localhost:8765/"


def log_mood(score: int, playing: str, decision: str):
    new = not MOOD_LOG.exists()
    with MOOD_LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "score", "now_playing", "decision"])
        w.writerow([dt.datetime.now().isoformat(timespec="seconds"), score, playing, decision])


def decide(scores: list[int]) -> str:
    """The vibe rule: two lows in a row means lift the energy; two highs means hold it."""
    last = scores[-2:]
    if len(last) == 2 and all(s <= 2 for s in last):
        return "up"
    if len(last) == 2 and all(s >= 4 for s in last):
        return "hold"
    return "plan"


def run(cfg, yt, plan, cue_list, playlist_link: str | None, config_path: str):
    slots = plan.slots
    everything = plan.songs + plan.reserve
    position = {s.video_id: i for i, s in enumerate(everything) if s.video_id}
    by_slot: dict[int, list] = {}
    for c in cue_list:
        if c.kind not in ("opening", "birthday_intro"):
            by_slot.setdefault(c.before, []).append(c)
    birthday_intro = next((c for c in cue_list if c.kind == "birthday_intro"), None)

    print("Making announcement audio...")
    audio = {}
    for n, c in enumerate(cue_list):
        try:
            audio[id(c)] = announcer.speak_to_file(c.text, Path("announcements") / f"cue_{n:02d}_{c.kind}")
        except RuntimeError as e:
            print(f"  {e}")
    announcer.make_horn()

    host = Host()
    speaker = Speaker()
    page = serve_page(host)
    webbrowser.open(page)
    print(f"\nControl page: {page}  (vibe buttons and messages for you)")
    if playlist_link:
        print(f"Playlist:     {playlist_link}")
    print("\n1. Open the playlist in YouTube Music, but don't press play yet.")
    print("2. Make sure shuffle is OFF, so it plays in order.")
    try:
        input("3. Press Enter here at the same moment you press play on song 1... ")
    except EOFError:
        pass

    started = dt.datetime.now()
    scheduled_start = cfg.start
    on_party_day = started.date() == scheduled_start.date()
    if on_party_day:
        birthday_at = scheduled_start + dt.timedelta(minutes=cfg.birthday_offset_minutes)
    else:  # a rehearsal on another day: keep the same gap from the start
        birthday_at = started + dt.timedelta(minutes=cfg.birthday_offset_minutes)
    end_at = started + dt.timedelta(minutes=cfg.duration_minutes + 15)
    print(f"Started {started:%I:%M %p}. Birthday block at {birthday_at:%I:%M %p}. Ctrl-C to stop.\n")

    first = next(c for c in cue_list if c.kind == "opening")
    if id(first) in audio:
        speaker.say(audio[id(first)], first.text)

    played_cues: set[int] = set()
    current = -1           # index into `everything`
    history_ok = True
    history_failures = 0
    next_vibe = started + dt.timedelta(minutes=cfg.vibe_check_minutes)
    birthday_done = False
    boost_for: str | None = None   # video id of a song chosen to lift the energy
    seen_requests = set(cfg.requested_tracks)
    blocked_warned: set[str] = set()
    last_reload = time.monotonic()

    def play_cues_for(index: int):
        for c in by_slot.get(index, []):
            if id(c) not in played_cues and id(c) in audio:
                played_cues.add(id(c))
                speaker.say(audio[id(c)], c.text)

    def now_playing() -> str:
        return everything[current].label() if 0 <= current < len(everything) else "unknown"

    while dt.datetime.now() < end_at:
        now = dt.datetime.now()

        # 1. Which song is on? Ask YouTube Music's history; fall back to the clock.
        index = None
        if history_ok:
            try:
                hist = yt.get_history()
                vid = hist[0].get("videoId") if hist else None
                index = position.get(vid)
                history_failures = 0
            except Exception:
                history_failures += 1
                if history_failures >= 4:
                    history_ok = False
                    host.notice("Can't read YouTube Music history; timing announcements by the clock.")
        if index is None and not history_ok:
            elapsed = (now - started).total_seconds()
            index = max((i for i, s in enumerate(slots) if s.start <= elapsed), default=0)

        if index is not None and index != current:
            current = index
            with host.lock:
                host.now = f"Now playing #{current + 1}: {now_playing()}"
            print(f"{now:%I:%M %p}  #{current + 1} {now_playing()}")
            if boost_for and everything[current].video_id == boost_for:
                speaker.say_text(announcer.Writer(cfg.birthday_person_name, cfg.host_name,
                                                  seed=str(now)).line("vibe_up", everything[current].title),
                                 f"vibe_up_{now:%H%M}")
                boost_for = None
            elif current < len(slots):
                play_cues_for(current)

        # 2. Birthday block, on the clock.
        if not birthday_done and now >= birthday_at:
            birthday_done = True
            b = plan.birthday_index
            if birthday_intro and id(birthday_intro) in audio:
                speaker.say(audio[id(birthday_intro)], birthday_intro.text)
            if b is not None and current != b:
                host.notice(f"🎂 Birthday time! In YouTube Music, play song #{b + 1} "
                            f"'{slots[b].song.title}' now. The cake cue follows it.")

        # 3. Vibe check every few minutes.
        if now >= next_vibe:
            next_vibe = now + dt.timedelta(minutes=cfg.vibe_check_minutes)
            with host.lock:
                host.vibe_due = True
            print("\a  📊 Vibe check! Tap a score on the control page.")
        with host.lock:
            new_scores, host.pending_scores = host.pending_scores, []
            say_now, host.announce_now = host.announce_now, False
        for score in new_scores:
            with host.lock:
                host.scores.append(score)
                host.vibe_due = False
                scores = list(host.scores)
            choice = decide(scores)
            decision = {"up": "energy up one tier", "hold": "hold the energy", "plan": "keep the plan"}[choice]
            if choice == "up":
                boost = pick_boost(everything, current, slots)
                if boost is not None:
                    boost_for = everything[boost].video_id
                    decision += f": play #{boost + 1} {everything[boost].label()} next"
                    host.notice(f"Crowd's quiet. In YouTube Music, find #{boost + 1} "
                                f"'{everything[boost].title}', click ⋮ and choose Play next.")
            elif choice == "hold":
                host.notice("Crowd's on fire 🔥 Holding the energy, no changes.")
            log_mood(score, now_playing(), decision)
            print(f"  Vibe {score}: {decision}")
        if say_now:
            upcoming = next((c for i in range(current + 1, len(slots)) for c in by_slot.get(i, [])
                             if id(c) not in played_cues and c.kind in
                             ("Warm-up", "Build", "Peak", "Peak 2", "Wind-down")), None)
            if upcoming:
                played_cues.add(id(upcoming))
                text = upcoming.text
            else:
                text = announcer.Writer(cfg.birthday_person_name, cfg.host_name, seed=str(now)).line(
                    "Peak 2", everything[current + 1].title if current + 1 < len(everything) else "the next one")
            speaker.say_text(text, f"now_{now:%H%M%S}")

        # 4. Every minute, re-read config.yaml for new blocks and requests.
        if time.monotonic() - last_reload > 60:
            last_reload = time.monotonic()
            try:
                fresh = load_config(config_path)
            except Exception as e:
                host.notice(f"config.yaml has a problem, ignoring changes: {e}")
            else:
                for i in range(max(current, 0), min(current + 4, len(everything))):
                    s = everything[i]
                    if is_blocked(s, fresh.blocked_artists, fresh.blocked_tracks) and s.key not in blocked_warned:
                        blocked_warned.add(s.key)
                        when = "now" if i == current else "when it comes on"
                        host.notice(f"🚫 '{s.title}' is blocked. Skip it {when} in YouTube Music.")
                for text in fresh.requested_tracks:
                    if text in seen_requests:
                        continue
                    seen_requests.add(text)
                    handle_request(yt, text, everything, position, plan, playlist_link, host)

        time.sleep(POLL_SECONDS)

    print("\nParty's over. Mood scores are in mood_log.csv. Good night!")


def pick_boost(everything, current: int, slots) -> int | None:
    """Pick an unplayed song one energy tier above the current one, extras first."""
    if not 0 <= current < len(everything):
        return None
    target = min(5, everything[current].energy + 1)
    later = range(current + 2, len(everything))  # not the very next song; that's already coming
    for tier in (target, 5):
        extras = [i for i in later if i >= len(slots) and everything[i].energy == tier]
        planned = [i for i in later if i < len(slots) and everything[i].energy == tier]
        if extras or planned:
            return (extras or planned)[0]
    return None


def handle_request(yt, text, everything, position, plan, playlist_link, host):
    req = parse_request(text)
    for i, s in enumerate(everything):
        if s.key == req.key:
            host.notice(f"🙋 Request '{s.title}' is #{i + 1} in the playlist: click ⋮ on it, then Play next.")
            return
    try:
        results = yt.search(f"{req.title} {req.artist}".strip(), filter="songs", limit=3)
    except Exception:
        results = []
    hit = next((r for r in results if r.get("videoId") and not r.get("isExplicit")), None)
    if not hit:
        host.notice(f"🙋 Couldn't find '{html.escape(req.title)}' on YouTube Music. Try adding it by hand.")
        return
    if playlist_link:
        pid = urllib.parse.parse_qs(urllib.parse.urlparse(playlist_link).query).get("list", [None])[0]
        try:
            yt.add_playlist_items(pid, [hit["videoId"]], duplicates=False)
        except Exception:
            pid = None
        if pid:
            req.video_id = hit["videoId"]
            everything.append(req)
            plan.reserve.append(req)
            position[req.video_id] = len(everything) - 1
            host.notice(f"🙋 Added '{html.escape(hit.get('title', req.title))}' to the end of the playlist "
                        f"(#{len(everything)}). Click ⋮ on it, then Play next.")
            return
    host.notice(f"🙋 Found '{html.escape(hit.get('title', req.title))}': "
                f"https://music.youtube.com/watch?v={hit['videoId']}")
