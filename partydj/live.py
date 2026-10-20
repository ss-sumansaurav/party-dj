"""Party-night DJ: a browser page that mixes the night like a DJ.

Python (the "director") decides what plays next: the plan for the time of night, the vibe the
host picks, requests, blocks, the birthday block and the vibe-check rule. The page plays each
song through YouTube's own player (nothing is downloaded), trims it DJ-style, crossfades
between two players, and talks over the intro with the music turned down, like a real DJ.
"""
from __future__ import annotations

import csv
import html
import datetime as dt
import http.server
import json
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

from . import announcer
from .config import load_config
from .planner import PHASE_RULES, Slot
from .songbook import Songbook
from .songs import Song, is_blocked, parse_request

MOOD_LOG = Path("mood_log.csv")
AUDIO_DIR = Path("announcements")
PORT = 8765
TIERS = {1: "Chill", 2: "Groove", 3: "Dance", 4: "Bangers", 5: "On fire"}
TIER_LINES = {1: "Wind-down", 2: "Warm-up", 3: "Build", 4: "Peak", 5: "Peak 2"}


def log_mood(score: int, playing: str, decision: str):
    new = not MOOD_LOG.exists()
    with MOOD_LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "score", "now_playing", "decision"])
        w.writerow([dt.datetime.now().isoformat(timespec="seconds"), score, playing, decision])


def decide(scores: list[int]) -> str:
    """The vibe rule: two lows in a row lifts the energy one tier; two highs holds it."""
    last = scores[-2:]
    if len(last) == 2 and all(s <= 2 for s in last):
        return "up"
    if len(last) == 2 and all(s >= 4 for s in last):
        return "hold"
    return "plan"


def start_offset(song: Song) -> int:
    """Skip a little of the intro on longer songs, like a DJ mixing in."""
    if song.full or not song.seconds or song.seconds < 200:
        return 0
    return 10


class Director:
    def __init__(self, cfg, yt, plan, playlist_link: str | None, config_path: str):
        self.cfg, self.yt, self.plan = cfg, yt, plan
        self.playlist_link, self.config_path = playlist_link, config_path
        self.lock = threading.RLock()
        self.slots = plan.slots
        self.everything: list[Song] = plan.songs + plan.reserve
        self.phase_of = {s.song.key: s.phase for s in plan.slots}
        self.played: set[str] = set()
        self.current: Song | None = None
        self.mode = "auto"                 # or a tier 1..5 the host picked
        self.inserts: list[tuple[Song, str]] = []   # (song, reason) to play next
        self.one_shot_tier: int | None = None        # from the vibe rule
        self.blocked = (list(cfg.blocked_artists), list(cfg.blocked_tracks))
        self.seen_requests = set(cfg.requested_tracks)
        self.scores: list[int] = []
        self.notices: list[str] = []
        self.started: dt.datetime | None = None
        self.birthday_at: dt.datetime | None = None
        self.birthday_state = "pending"    # pending -> due -> playing -> done
        self.force_next = False
        self.vibe_due = False
        self.next_vibe: dt.datetime | None = None
        self.since_announce = 0
        self.closing_done = False
        self.opened = False
        self.writer = announcer.Writer(cfg.birthday_person_name, cfg.host_name, seed=f"{cfg.party_date}-live",
                                       hindi_share=cfg.hindi_announcement_share)
        self.fixed: dict[str, str] = {}    # kind -> audio file name, made at start-up
        self.n_audio = 0

    # ---------- helpers ----------
    def notice(self, text: str):
        print(f"  ➜ {text}")
        with self.lock:
            self.notices = ([f"{dt.datetime.now():%I:%M %p}  {text}"] + self.notices)[:10]

    def speak(self, kind: str, text: str, energy: int | None = None) -> dict | None:
        self.n_audio += 1
        name = f"live_{self.n_audio:03d}_{kind.replace(' ', '_')}"
        try:
            path = announcer.speak_to_file(text, AUDIO_DIR / name,
                                           energy=energy or announcer.KIND_ENERGY.get(kind, 3))
        except RuntimeError as e:
            print(f"  (couldn't make an announcement: {e})")
            return None
        print(f"  🎤 {text}")
        return {"url": f"/audio/{path.name}", "text": text}

    def prepare(self):
        """Make the fixed announcements before the party starts."""
        print("Making announcements...")
        w = self.writer
        for kind in ("opening", "birthday_intro", "cake", "shoutout", "closing"):
            self.fixed[kind] = w.line(kind)

    def elapsed_min(self) -> float:
        return (dt.datetime.now() - self.started).total_seconds() / 60 if self.started else 0

    def phase_now(self) -> str:
        m = self.elapsed_min()
        for ph in self.plan.phases:
            if ph.start <= m < ph.end and ph.name != "Birthday":
                return ph.name
        if self.birthday_state in ("playing",):
            return "Peak 2"
        return "Wind-down" if m >= self.cfg.duration_minutes - 45 else "Peak 2"

    def playable(self, s: Song) -> bool:
        return bool(s.video_id) and s.key not in self.played and not is_blocked(s, *self.blocked) \
            and not (s.full and self.birthday_state != "due")

    def pick_by_tier(self, tier: int) -> Song | None:
        pool = [s for s in self.everything if self.playable(s)]
        for t in (tier, tier - 1 if tier > 1 else 2, tier + 1):
            same = [s for s in pool if s.energy == t]
            if same:
                return same[0]
        return pool[0] if pool else None

    def pick_auto(self) -> Song | None:
        phase = self.phase_now()
        planned = [s.song for s in self.slots if s.phase == phase and self.playable(s.song)]
        if planned:
            return planned[0]
        energies = PHASE_RULES[phase]["energies"]
        fits = [s for s in self.everything if self.playable(s) and s.energy in energies]
        if fits:
            return fits[0]
        rest = [s for s in self.everything if self.playable(s)]
        return rest[0] if rest else None

    def choose(self) -> tuple[Song | None, str | None]:
        """What plays next (without changing anything), and why."""
        if self.birthday_state == "due":
            return next((s.song for s in self.slots if s.song.full), None), "birthday"
        for cand, why in self.inserts:
            if self.playable(cand):
                return cand, why
        if self.one_shot_tier:
            song = self.pick_by_tier(self.one_shot_tier)
            if song:
                up = self.current and self.one_shot_tier > self.current.energy
                return song, "boost" if up else "hold"
        return (self.pick_by_tier(self.mode) if self.mode != "auto" else self.pick_auto()), None

    def up_next(self) -> dict | None:
        with self.lock:
            song, _ = self.choose()
        return {"title": song.title, "artist": song.lead_artist, "tier": TIERS[song.energy]} if song else None

    # ---------- the main decision ----------
    def next_track(self, error: bool = False) -> dict:
        with self.lock:
            if error and self.current:
                self.notice(f"'{self.current.title}' won't play here, moving on.")
            announce: list = []
            reason = None
            song = None
            if self.birthday_state == "due":
                song = next((s.song for s in self.slots if s.song.full), None)
                self.birthday_state = "playing"
                a = self.speak("birthday_intro", self.fixed["birthday_intro"])
                announce += [a] if a else []
                reason = "birthday"
            elif self.birthday_state == "playing":
                self.birthday_state = "done"
                for kind in ("cake", "shoutout"):
                    a = self.speak(kind, self.fixed[kind])
                    announce += [a] if a else []
                self.since_announce = 0
            if song is None:
                song, why = self.choose()
                reason = reason or why
                while self.inserts and not self.playable(self.inserts[0][0]):
                    self.inserts.pop(0)
                if why == "request":
                    self.inserts.pop(0)
                elif why in ("boost", "hold"):
                    self.one_shot_tier = None
            if song is None:
                return {"done": True}

            self.played.add(song.key)
            self.current = song
            # What the DJ says over the intro.
            if not self.opened:
                self.opened = True
                a = self.speak("opening", self.fixed["opening"])
                announce += [a] if a else []
                self.since_announce = 0
            elif reason in ("boost", "request") and not announce:
                a = self.speak("vibe_up" if reason == "boost" else "request",
                               self.writer.line("vibe_up" if reason == "boost" else "request", song.title))
                announce += [a] if a else []
                self.since_announce = 0
            elif not announce:
                self.since_announce += 1
                closing_time = self.elapsed_min() >= self.cfg.duration_minutes - 4
                if closing_time and not self.closing_done:
                    self.closing_done = True
                    a = self.speak("closing", self.fixed["closing"])
                    announce += [a] if a else []
                elif self.since_announce >= self.cfg.announcement_interval_songs:
                    phase = self.phase_now() if self.mode == "auto" else TIER_LINES[self.mode]
                    a = self.speak(phase, self.writer.line(phase, song.title), song.energy)
                    announce += [a] if a else []
                    self.since_announce = 0
            print(f"{dt.datetime.now():%I:%M %p}  ▶ {song.label()}  [{TIERS[song.energy]}]")
            play = song.full_length if song.full else min(song.full_length, self.cfg.song_play_seconds)
            return {
                "vid": song.video_id, "title": song.title, "artist": song.lead_artist,
                "tier": TIERS[song.energy], "start": start_offset(song), "play": play,
                "full": song.full, "announce": announce,
            }

    # ---------- the songs page ----------
    def song_states(self) -> dict[str, str]:
        with self.lock:
            nxt, _ = self.choose()
            out = {}
            for s in self.everything:
                if is_blocked(s, *self.blocked):
                    out[s.key] = "Removed / blocked"
                elif self.current and s.key == self.current.key:
                    out[s.key] = "▶ Playing now"
                elif s.key in self.played:
                    out[s.key] = "played"
                elif nxt and s.key == nxt.key:
                    out[s.key] = "⏭ Up next"
                elif not s.video_id:
                    out[s.key] = "Not found on YouTube Music"
            for slot in self.slots:
                out.setdefault(slot.song.key, f"Planned: {slot.phase}")
            for s in self.plan.reserve:
                out.setdefault(s.key, "Extra (plays if picked by vibe)")
            return out

    def add_song(self, song: Song):
        """A song added on the songs page joins the plan in the next phase that suits its energy."""
        with self.lock:
            self.everything.append(song)
            now = self.elapsed_min() if self.started else 0
            phase = next((ph.name for ph in self.plan.phases if ph.end > now and ph.name in PHASE_RULES
                          and song.energy in PHASE_RULES[ph.name]["energies"]), None)
            if phase:
                last = max((i for i, s in enumerate(self.slots) if s.phase == phase), default=len(self.slots) - 1)
                self.slots.insert(last + 1, Slot(song, phase))
        self.add_to_playlist(song)
        self.notice(f"🎵 Added '{song.title}'" + (f" to the {phase} part of the night." if phase else "."))

    def remove_song(self, title: str):
        with self.lock:
            self.blocked[1].append(title)
        self.notice(f"🎵 Removed '{title}'. It won't play tonight.")

    def hype_now(self) -> list:
        with self.lock:
            a = self.speak("hype", self.writer.line("hype"))
            self.since_announce = 0
            return [a] if a else []

    def set_mode(self, mode: str):
        with self.lock:
            self.mode = int(mode) if mode in ("1", "2", "3", "4", "5") else "auto"
        label = TIERS.get(self.mode, "Auto (follow the plan)") if self.mode != "auto" else "Auto (follow the plan)"
        self.notice(f"Vibe set to {label}. It starts with the next song.")

    def add_score(self, score: int):
        with self.lock:
            self.scores.append(score)
            self.vibe_due = False
            choice = decide(self.scores)
            cur = self.current
            decision = {"up": "energy up one tier", "hold": "hold the energy", "plan": "keep the plan"}[choice]
            if choice == "up" and cur:
                self.one_shot_tier = min(5, cur.energy + 1)
                self.notice(f"Crowd's quiet. Next song goes up to {TIERS[self.one_shot_tier]}.")
            elif choice == "hold" and cur:
                self.one_shot_tier = cur.energy
                self.notice("Crowd's on fire 🔥 Holding the energy.")
        log_mood(score, cur.label() if cur else "", decision)

    def request(self, text: str):
        text = text.strip()
        if not text:
            return
        req = parse_request(text)
        match = next((s for s in self.everything if s.key == req.key), None)
        if match is None:
            try:
                results = self.yt.search(f"{req.title} {req.artist}".strip(), filter="songs", limit=3)
            except Exception:
                results = []
            hit = next((r for r in results if r.get("videoId") and not r.get("isExplicit")), None)
            if not hit:
                self.notice(f"🙋 Couldn't find '{req.title}' on YouTube Music.")
                return
            req.video_id = hit["videoId"]
            req.seconds = hit.get("duration_seconds")
            req.title = hit.get("title") or req.title
            match = req
            with self.lock:
                self.everything.append(req)
            self.add_to_playlist(req)
        with self.lock:
            self.played.discard(match.key)
            self.inserts.append((match, "request"))
        self.notice(f"🙋 Request '{match.title}' plays next.")

    def add_to_playlist(self, song: Song):
        pid = urllib.parse.parse_qs(urllib.parse.urlparse(self.playlist_link or "").query).get("list", [None])[0]
        if pid:
            try:
                self.yt.add_playlist_items(pid, [song.video_id], duplicates=False)
            except Exception:
                pass

    def block(self, what: str) -> bool:
        with self.lock:
            cur = self.current
            if not cur:
                return False
            if what == "artist":
                self.blocked[0].append(cur.lead_artist)
                self.notice(f"🚫 Blocked {cur.lead_artist} for the rest of the night.")
            else:
                self.blocked[1].append(cur.title)
                self.notice(f"🚫 Blocked '{cur.title}'.")
            return True

    def reload_config(self):
        try:
            fresh = load_config(self.config_path)
        except Exception as e:
            self.notice(f"config.yaml has a problem, ignoring changes: {e}")
            return
        with self.lock:
            for a in fresh.blocked_artists:
                if a not in self.blocked[0]:
                    self.blocked[0].append(a)
            for t in fresh.blocked_tracks:
                if t not in self.blocked[1]:
                    self.blocked[1].append(t)
            new = [t for t in fresh.requested_tracks if t not in self.seen_requests]
            self.seen_requests.update(new)
        for t in new:
            self.request(t)

    def tick(self):
        """Clock work: birthday block, vibe checks, config changes."""
        now = dt.datetime.now()
        with self.lock:
            if not self.started:
                return
            if self.birthday_state == "pending" and self.birthday_at and now >= self.birthday_at:
                self.birthday_state = "due"
                self.force_next = True
                self.notice("🎂 Birthday time! The DJ is starting the birthday song.")
            if self.next_vibe and now >= self.next_vibe:
                self.next_vibe = now + dt.timedelta(minutes=self.cfg.vibe_check_minutes)
                self.vibe_due = True
                print("\a  📊 Vibe check! Tap a score on the DJ page.")

    def begin(self):
        with self.lock:
            if self.started:
                return
            self.started = dt.datetime.now()
            if self.started.date() == self.cfg.start.date():
                self.birthday_at = self.cfg.start + dt.timedelta(minutes=self.cfg.birthday_offset_minutes)
            else:  # rehearsal on another day: same gap from the start
                self.birthday_at = self.started + dt.timedelta(minutes=self.cfg.birthday_offset_minutes)
            self.next_vibe = self.started + dt.timedelta(minutes=self.cfg.vibe_check_minutes)
        print(f"\n🎉 Party started {self.started:%I:%M %p}. Birthday block at {self.birthday_at:%I:%M %p}.\n")

    def state(self) -> dict:
        with self.lock:
            force, self.force_next = self.force_next, False
            return {
                "mode": self.mode, "notices": self.notices, "vibe_due": self.vibe_due,
                "scores": self.scores[-6:], "force_next": force,
                "birthday": self.birthday_at.strftime("%I:%M %p").lstrip("0") if self.birthday_at else None,
                "started": bool(self.started), "phase": self.phase_now() if self.started else None,
                "up_next": self.up_next(),
            }


def serve(director: Director, songbook: Songbook) -> str:
    title = html.escape(f"{director.cfg.birthday_person_name}'s Birthday Party DJ")
    page = PAGE.replace("__FADE__", str(director.cfg.crossfade_seconds)).replace("__TITLE__", title)

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body=b"", kind="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj):
            self._send(200, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            if songbook.handle(self, "GET", u.path, {}):
                return
            if u.path == "/state":
                return self._json(director.state())
            if u.path.startswith("/audio/"):
                f = AUDIO_DIR / Path(urllib.parse.unquote(u.path[7:])).name
                if f.exists():
                    kind = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".aiff": "audio/aiff"}.get(f.suffix, "application/octet-stream")
                    return self._send(200, f.read_bytes(), kind)
                return self._send(404)
            self._send(200, page.encode())

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            if songbook.handle(self, "POST", u.path, q):
                return
            arg = q.get("v", [""])[0]
            if u.path == "/start":
                director.begin()
                return self._json({"ok": True})
            if u.path == "/next":
                return self._json(director.next_track(error=arg == "error"))
            if u.path == "/hype":
                return self._json({"announce": director.hype_now()})
            if u.path == "/mode":
                director.set_mode(arg)
            elif u.path == "/score" and arg.isdigit() and 1 <= int(arg) <= 5:
                director.add_score(int(arg))
            elif u.path == "/request":
                threading.Thread(target=director.request, args=(arg,), daemon=True).start()
            elif u.path == "/block":
                return self._json({"skip": director.block(arg)})
            self._json({"ok": True})

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://localhost:{PORT}/"


def run(cfg, yt, plan, playlist_link: str | None, config_path: str, songs_path: str = "songs.yaml"):
    AUDIO_DIR.mkdir(exist_ok=True)
    director = Director(cfg, yt, plan, playlist_link, config_path)
    director.prepare()
    book = Songbook(songs_path, yt, director)
    book.page_title = f"{cfg.birthday_person_name}'s party songs"
    url = serve(director, book)
    webbrowser.open(url)
    print(f"\nThe DJ page is open: {url}")
    print("Click the big START button on it. Keep this window and that page open all night.")
    print("Press Ctrl-C here to finish.\n")
    last_reload = time.monotonic()
    end = None
    while True:
        director.tick()
        if director.started and end is None:
            end = director.started + dt.timedelta(minutes=cfg.duration_minutes + 30)
        if end and dt.datetime.now() > end:
            print("The party time is over; the DJ keeps playing extras until you press Ctrl-C.")
            end = dt.datetime.max
        if time.monotonic() - last_reload > 60:
            last_reload = time.monotonic()
            director.reload_config()
        time.sleep(1)


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="strict-origin-when-cross-origin"><title>__TITLE__</title>
<style>
 :root{--bg:#0d0d12;--card:#1b1b24;--pink:#ff2d7a;--txt:#f4f4f8;--dim:#a0a0b0}
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--txt);text-align:center}
 main{max-width:1180px;margin:auto;padding:16px}
 #ui:not([hidden]){display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;align-items:start}
 #side{position:sticky;top:12px} #side .card{margin-top:0}
 #nxtitle{font-size:22px;font-weight:700;margin-top:8px} #nxartist{color:var(--dim)}
 @media (max-width:820px){#ui:not([hidden]){grid-template-columns:1fr} #side{position:static}}
 #stop{background:#b71c1c} #mic.on{background:var(--pink);animation:pulse 1s infinite}
 @keyframes pulse{50%{opacity:.6}}
 h1{margin:8px 0} .card{background:var(--card);border-radius:16px;padding:16px;margin:12px 0}
 #start{font-size:34px;padding:22px 60px;border-radius:20px;border:0;background:var(--pink);color:#fff;cursor:pointer;margin:30px}
 #title{font-size:28px;font-weight:700} #artist{color:var(--dim);font-size:18px}
 #bar{height:8px;background:#333;border-radius:4px;margin-top:12px;overflow:hidden} #fill{height:100%;width:0;background:var(--pink)}
 .row{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
 .mode{font-size:18px;padding:16px 18px;border-radius:14px;border:2px solid transparent;color:#fff;cursor:pointer;min-width:110px}
 .mode.on{border-color:#fff;box-shadow:0 0 18px rgba(255,255,255,.5)}
 .act{font-size:17px;padding:12px 18px;border-radius:12px;border:0;background:#333;color:#fff;cursor:pointer}
 button:active{transform:scale(.95)}
 input{font-size:17px;padding:12px;border-radius:10px;border:0;width:min(420px,100%)}
 ul{list-style:none;padding:0;text-align:left} li{padding:8px 10px;border-bottom:1px solid #2a2a35;color:var(--dim)}
 #overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;align-items:center;justify-content:center;flex-direction:column}
 #overlay .mode{font-size:30px;min-width:90px}
 #toast{position:fixed;left:50%;top:14px;transform:translateX(-50%);background:#2e7d32;padding:12px 22px;border-radius:12px;display:none;font-size:18px}
 #down{background:#b71c1c;padding:12px;border-radius:12px;display:none}
 #players{position:relative;width:320px;height:180px;margin:12px auto 0;border-radius:10px;overflow:hidden;background:#000}
 #players iframe{position:absolute;left:0;top:0;width:320px;height:180px;pointer-events:none}
 #voice{color:var(--pink);min-height:22px;margin-top:8px}
</style></head><body><main>
<div id="toast"></div>
<h1>🎧 __TITLE__</h1>
<div style="margin-bottom:8px"><a href="/songs" target="_blank" style="color:var(--pink);font-size:18px">🎵 See, add or remove party songs</a> <small style="color:var(--dim)">(opens in a new tab, the music keeps playing)</small></div>
<div id="down">The DJ program isn't running. In Terminal run: <b>python dj.py</b></div>
<button id="start">▶ START THE PARTY</button>
<div id="players"><div id="p0"></div><div id="p1"></div></div>
<div id="ui" hidden><div id="left">
 <div class="card"><div id="phase" style="color:var(--dim)"></div>
  <div id="title">…</div><div id="artist"></div><div id="voice"></div><div id="bar"><div id="fill"></div></div></div>
 <div class="card"><b>Pick the vibe</b><div class="row" style="margin-top:10px">
  <button class="mode" data-m="auto" style="background:#455a64">🤖 Auto</button>
  <button class="mode" data-m="1" style="background:#3949ab">😌 Chill</button>
  <button class="mode" data-m="2" style="background:#00897b">🙂 Groove</button>
  <button class="mode" data-m="3" style="background:#7cb342">💃 Dance</button>
  <button class="mode" data-m="4" style="background:#fb8c00">🔥 Bangers</button>
  <button class="mode" data-m="5" style="background:#e53935">🚀 On fire</button></div></div>
 <div class="card row">
  <button class="act" id="stop">⏹ Stop music</button>
  <button class="act" id="skip">⏭ Next song</button>
  <button class="act" id="hype">🎤 Hype the crowd</button>
  <button class="act" id="blk">🚫 Block this song</button>
  <button class="act" id="blka">🚫 Block this artist</button></div>
 <div class="card"><b>Request a song</b><div style="margin-top:10px">
  <button class="act" id="mic" title="Say the song name">🎙 Speak</button>
  <input id="req" placeholder="Song name - Artist"> <button class="act" id="reqb">Add</button></div></div>
 <div class="card"><b>For you</b><div id="scores" style="color:var(--dim)"></div><ul id="notices"></ul></div>
</div>
<div id="side"><div class="card"><b>⏭ Up next</b><div id="nxtitle">…</div><div id="nxartist"></div></div></div>
</div>
<div id="overlay"><h2>📊 Vibe check! How's the crowd?</h2><div class="row">
 <button class="mode" style="background:#3949ab" onclick="score(1)">1<br><small>chill</small></button>
 <button class="mode" style="background:#00897b" onclick="score(2)">2</button>
 <button class="mode" style="background:#7cb342" onclick="score(3)">3</button>
 <button class="mode" style="background:#fb8c00" onclick="score(4)">4</button>
 <button class="mode" style="background:#e53935" onclick="score(5)">5<br><small>on fire</small></button></div></div>
</main>
<script>
const FADE = __FADE__, DUCK = 22, PREP = 25;
let stopped = false, P = [null, null], ready = 0, active = 0, cur = null, upcoming = null, busy = false, fetching = false;
const $ = id => document.getElementById(id);
function toast(t){ const e=$('toast'); e.textContent=t; e.style.display='block'; clearTimeout(e.t); e.t=setTimeout(()=>e.style.display='none',2500); }
async function post(path){ const r = await fetch(path,{method:'POST'}); if(!r.ok) throw 0; return r.json(); }
function ramp(p, from, to, secs){ return new Promise(res=>{ const steps=Math.max(1,Math.round(secs*10)); let i=0;
  p.setVolume(from); const t=setInterval(()=>{ i++; p.setVolume(from+(to-from)*i/steps); if(i>=steps){clearInterval(t); res();} },100); }); }
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
function playAudio(url, rate){ return new Promise(res=>{ const a=new Audio(url); a.playbackRate=rate||1; a.onended=res; a.onerror=res; a.play().catch(res); }); }
async function talk(list, p){
  if(!list || !list.length) return;
  if(p) await ramp(p, 100, DUCK, 1);
  for(const a of list){ $('voice').textContent='🎤 '+a.text; await playAudio(a.url); }
  $('voice').textContent=''; if(p) ramp(p, DUCK, 100, 1.5);
}
function onYouTubeIframeAPIReady(){
  for(const i of [0,1]) P[i] = new YT.Player('p'+i,{height:'180',width:'320',playerVars:{origin:location.origin,playsinline:1,controls:0,disablekb:1},
    events:{onReady:()=>{ready++;}, onError:()=>{ if(i===active && cur) next(true); },
            onStateChange:e=>{ if(i===active && e.data===YT.PlayerState.ENDED && !busy) next(false); }}});
}
async function fetchNext(err){ fetching=true; try{ upcoming = await post('/next'+(err?'?v=error':'')); } finally { fetching=false; } }
async function next(err){
  if(busy) return; busy=true; setStopped(false);
  try{
    if(err || !upcoming) await fetchNext(err);
    const t = upcoming; upcoming = null;
    if(!t || t.done){ $('title').textContent='That was the last song!'; busy=false; return; }
    const old = cur ? P[active] : null, ni = cur ? 1-active : active, p = P[ni];
    p.setVolume(0); p.loadVideoById({videoId:t.vid, startSeconds:t.start});
    cur = t; active = ni; cur.until = t.start + t.play;
    P[ni].getIframe().style.zIndex = 2; if(old) P[1-ni].getIframe().style.zIndex = 1;
    $('title').textContent=t.title; $('artist').textContent=t.artist+'  ·  '+t.tier; $('fill').style.width='0';
    load();
    const target = (t.announce && t.announce.length) ? DUCK : 100;
    const fades = [ramp(p, 0, target, err||!old ? 1.5 : FADE)];
    if(old) fades.push(ramp(old, 100, 0, FADE).then(()=>old.stopVideo()));
    await Promise.all(fades);
    if(target===DUCK){ for(const a of t.announce){ $('voice').textContent='🎤 '+a.text; await playAudio(a.url);} $('voice').textContent=''; ramp(p, DUCK, 100, 1.5); }
  } catch(e){ console.log(e); } finally { busy=false; }
}
setInterval(()=>{   // the DJ's ear: when to fetch the next song and when to mix
  if(!cur || busy || stopped) return; const p=P[active]; if(!p || !p.getCurrentTime) return;
  const t=p.getCurrentTime(), d=p.getDuration()||0, end=Math.min(cur.until, d ? d-0.5 : cur.until), left=end-t;
  if(d) $('fill').style.width=Math.min(100,100*(t-cur.start)/Math.max(1,end-cur.start))+'%';
  if(left < PREP && !upcoming && !fetching) fetchNext(false);
  if(left < FADE && upcoming) next(false);
}, 300);
async function load(){
  try{ const s = await (await fetch('/state')).json(); $('down').style.display='none';
    document.querySelectorAll('.mode[data-m]').forEach(b=>b.classList.toggle('on', String(s.mode)===b.dataset.m));
    $('overlay').style.display = s.vibe_due ? 'flex' : 'none';
    $('phase').textContent = s.started ? (s.phase+(s.birthday?'  ·  🎂 birthday at '+s.birthday:'')) : '';
    $('scores').textContent = s.scores.length ? 'Vibe scores: '+s.scores.join(', ') : '';
    $('notices').innerHTML = s.notices.map(n=>'<li>'+n.replace(/</g,'&lt;')+'</li>').join('');
    const n = upcoming && !upcoming.done ? upcoming : s.up_next;
    $('nxtitle').textContent = n ? n.title : 'Nothing left to play'; $('nxartist').textContent = n ? n.artist+'  ·  '+n.tier : '';
    if(s.force_next && cur){ upcoming=null; next(false); }
  } catch(e){ $('down').style.display='block'; }
}
setInterval(load, 2000); load();
$('start').onclick = async ()=>{
  if(ready<2){ toast('Loading the player, one moment…'); return; }
  await post('/start'); $('start').remove(); $('ui').hidden=false; next(false);
};
document.querySelectorAll('.mode[data-m]').forEach(b=>b.onclick=()=>post('/mode?v='+b.dataset.m).then(()=>{toast('Vibe: '+b.textContent.trim()); load();}).catch(()=>$('down').style.display='block'));
window.score = n => post('/score?v='+n).then(()=>{toast('Vibe '+n+' saved ✓'); load();});
function setStopped(v){ stopped=v; $('stop').textContent = v ? '▶ Play music' : '⏹ Stop music'; }
$('stop').onclick = async ()=>{
  if(!cur || busy) return; const p=P[active];
  if(!stopped){ setStopped(true); await ramp(p, p.getVolume(), 0, 1.5); p.pauseVideo(); toast('Music stopped'); }
  else { setStopped(false); p.playVideo(); ramp(p, 0, 100, 1.5); toast('Music back on'); }
};
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
$('mic').onclick = ()=>{
  if(!SR){ toast('The mic needs Google Chrome'); return; }
  const r = new SR(); r.lang='en-IN'; r.interimResults=false; r.maxAlternatives=1;
  const p = P[active], wasStopped = stopped;
  $('mic').classList.add('on'); $('mic').textContent='🎙 Listening…';
  if(p && cur && !stopped) p.setVolume(15);   // turn the music down so it can hear you
  const done = ()=>{ $('mic').classList.remove('on'); $('mic').textContent='🎙 Speak'; if(p && cur && !wasStopped) ramp(p, 15, 100, 1); };
  r.onresult = e=>{ const said = e.results[0][0].transcript.trim(); $('req').value = said; toast('Heard: '+said); setTimeout(()=>$('reqb').click(), 600); };
  r.onerror = e=>{ toast(e.error==='not-allowed' ? 'Allow the microphone for this page, then try again' : "Didn't catch that, try again"); };
  r.onend = done; r.start();
};
$('skip').onclick = ()=>{ upcoming=null; next(false); };
$('hype').onclick = async ()=>{ const r = await post('/hype'); talk(r.announce, P[active]); };
$('blk').onclick = async ()=>{ const r = await post('/block?v=song'); if(r.skip){ upcoming=null; next(false);} load(); };
$('blka').onclick = async ()=>{ const r = await post('/block?v=artist'); if(r.skip){ upcoming=null; next(false);} load(); };
$('reqb').onclick = ()=>{ const v=$('req').value.trim(); if(!v) return; post('/request?v='+encodeURIComponent(v)).then(()=>{toast('Looking for it…'); $('req').value='';}); };
</script>
<script src="https://www.youtube.com/iframe_api"></script>
</body></html>"""
