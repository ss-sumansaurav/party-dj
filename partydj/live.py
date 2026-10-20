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
import random
import re
import socket
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

from . import announcer, cuts, fx
from .config import load_config
from .planner import PHASE_RULES, Slot
from .songbook import Songbook
from .songs import Song, is_blocked, parse_request, title_looks_explicit

MOOD_LOG = Path("mood_log.csv")
REQUEST_LOG = Path("requests.csv")
AUDIO_DIR = Path("announcements")
PORT = 8765
TIERS = {1: "Chill", 2: "Groove", 3: "Dance", 4: "Bangers", 5: "On fire"}
GUEST_PORT = 8766          # request page only, for the public link
PUBLIC = {"url": None}     # the public link, once it's open
DANCE_CALL_GAP = 20 * 60
SINGALONG_GAP = 15 * 60       # at most one sing-along drop every 15 minutes   # seconds between "come to the dance floor" call-outs
TIER_LINES = {1: "Wind-down", 2: "Warm-up", 3: "Build", 4: "Peak", 5: "Peak 2"}


def clean_name(name: str) -> str:
    """A guest's name, safe to show and say: letters, spaces and a little punctuation."""
    name = re.sub(r"<[^>]*>", "", name)
    name = re.sub(r"[^\w\u0900-\u097F .'-]", "", name, flags=re.UNICODE)
    name = " ".join(re.sub(r"[\d_]", "", name).split())[:24]
    return "" if title_looks_explicit(name) else name


def who_all(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def who(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return f"{names[0]}, {names[1]} and {len(names) - 2} more"


def lan_ip() -> str | None:
    """This device's address on the Wi-Fi, so guests' phones can reach the request page."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def guest_url() -> str | None:
    if PUBLIC["url"]:
        return PUBLIC["url"] + "/req"
    ip = lan_ip()
    return f"http://{ip}:{PORT}/req" if ip else None


def qr_svg(text: str) -> bytes:
    import io

    import segno

    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="svg", scale=6, border=2, dark="#000", light="#fff")
    return buf.getvalue()


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
        self.current_reason: str | None = None
        self.request_log: dict[str, dict] = {}   # song key -> title, artist, names, first time
        self._playlist_warned = False
        self.vibe_due = False
        self.cam_on = False                # crowd camera scores the vibe instead of the host
        self.guest_reqs: dict[str, dict] = {}   # song key -> song, names, ips, first asked
        self.last_dance_call = 0.0
        self.dance_call_pending = False
        self.singalong: dict | None = None  # a sing-along drop offered to the DJ page
        self.singalong_pending = False      # on fire, but the drop moves to the next song
        self.last_singalong = -SINGALONG_GAP
        self.n_sing = 0
        self._search_yt = None                # signed-out client just for guest searches
        self.fx: list[str] = []             # scratch sounds made at start-up
        self.rng = random.Random(f"{cfg.party_date}-fx")
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
        """Make the fixed announcements before the party starts, and look up mix points."""
        def warm():
            for s in self.plan.songs + self.plan.reserve:
                if s.video_id:
                    cuts.lyric_lines(self.yt, s.video_id)
        threading.Thread(target=warm, daemon=True).start()
        try:
            self.fx = fx.make_all(AUDIO_DIR)
        except Exception as e:  # the party still works, just without the effects
            print(f"  (couldn't make the DJ effects: {e})")
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
        for r in self.guest_queue():
            if self.playable(r["song"]):
                return r["song"], "guest"
        if self.one_shot_tier:
            song = self.pick_by_tier(self.one_shot_tier)
            if song:
                up = self.current and self.one_shot_tier > self.current.energy
                return song, "boost" if up else "hold"
        return (self.pick_by_tier(self.mode) if self.mode != "auto" else self.pick_auto()), None

    def up_next(self) -> dict | None:
        with self.lock:
            song, _ = self.choose()
        if not song:
            return None
        req = self.guest_reqs.get(song.key)
        tier = f"Requested by {who(req['names'])}" if req else TIERS[song.energy]
        return {"title": song.title, "artist": song.lead_artist, "tier": tier}

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
                elif why == "guest":
                    names = self.guest_reqs.pop(song.key)["names"]
                elif why in ("boost", "hold"):
                    self.one_shot_tier = None
            if song is None:
                return {"done": True}

            self.played.add(song.key)
            prev, self.current = self.current, song
            self.current_reason = reason
            # What the DJ says over the intro.
            if not self.opened:
                self.opened = True
                a = self.speak("opening", self.fixed["opening"])
                announce += [a] if a else []
                self.since_announce = 0
            elif reason == "guest" and not announce:
                a = self.speak("guest_request", self.writer.line("guest_request", song.title, who=who(names)))
                announce += [a] if a else []
                self.since_announce = 0
            elif reason == "request" and not announce:
                a = self.speak("request", self.writer.line("request", song.title))
                announce += [a] if a else []
                self.since_announce = 0
            elif self.dance_call_pending and not announce:
                # The floor's quiet: call people up, but not over and over.
                self.dance_call_pending = False
                if self.dance_call_ok():
                    a = self.speak("dance_floor", self.writer.line("dance_floor", song.title))
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
            sing = None
            if self.singalong_pending and not song.full:
                self.singalong_pending = False
                sing = self.make_singalong(song)
            start = start_offset(song)
            play = cuts.best_play(song.full_length, start, cuts.lyric_lines(self.yt, song.video_id),
                                  self.cfg.song_play_min_seconds, self.cfg.song_play_max_seconds,
                                  self.cfg.crossfade_seconds)
            return {
                "vid": song.video_id, "title": song.title, "artist": song.lead_artist,
                "tier": TIERS[song.energy], "start": start, "play": play,
                "full": song.full, "announce": announce, "req": reason in ("guest", "request"),
                "fx": self.pick_fx(prev, song, reason), "sing": sing,
            }

    def pick_fx(self, prev: Song | None, song: Song, reason: str | None) -> str:
        """How to mix into the next song. Mostly a smooth blend; now and then a trance-style
        build-up and drop when the energy climbs, or a quick scratch between two bangers."""
        if not self.fx or prev is None or prev.full or song.full or reason == "birthday":
            return ""
        r = self.rng.random()
        if song.energy > prev.energy and song.energy >= 4 and r < 0.45:
            return "riser"
        if min(song.energy, prev.energy) >= 4 and r < 0.3:
            return "scratch:" + self.rng.choice(self.fx)
        return ""

    def make_singalong(self, song: Song) -> dict:
        """The music drops away on the hook and the crowd sings it. The page picks the moment:
        the next time the chorus comes round, or a few seconds from now without lyrics."""
        self.n_sing += 1
        at, words = cuts.chorus(cuts.lyric_text(self.yt, song.video_id))
        return {"id": self.n_sing, "vid": song.video_id, "at": at, "words": words,
                "announce": self.speak("sing_along", self.writer.line("sing_along", song.title))}

    def singalong_done(self, sing_id: str, ok: bool):
        with self.lock:
            live = bool(self.singalong and str(self.singalong["id"]) == sing_id)
            if live:
                self.singalong = None
            if ok:
                self.last_singalong = time.monotonic()
                self.notice("🎤 Sing-along! The crowd took the hook.")
            elif live:
                self.singalong_pending = True  # too late in this song, so it goes on the next one

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

    def add_score(self, score: int, source: str = "host"):
        with self.lock:
            self.scores.append(score)
            self.vibe_due = False
            choice = decide(self.scores)
            cur = self.current
            decision = {"up": "energy up one tier", "hold": "hold the energy", "plan": "keep the plan"}[choice]
            if source == "camera":
                decision += " (crowd camera)"
            if choice == "up":
                self.dance_call_pending = True
            if choice == "up" and cur:
                self.one_shot_tier = min(5, cur.energy + 1)
                self.notice(f"Crowd's quiet. Next song goes up to {TIERS[self.one_shot_tier]}.")
            elif choice == "hold" and cur:
                self.one_shot_tier = cur.energy
                self.notice("Crowd's on fire 🔥 Holding the energy.")
            fire = score >= 5 and cur is not None and not cur.full and self.singalong is None \
                and not self.singalong_pending and time.monotonic() - self.last_singalong > SINGALONG_GAP
            if fire:
                self.singalong = self.make_singalong(cur)
                self.last_singalong = time.monotonic()  # no second drop while this one is on
        log_mood(score, cur.label() if cur else "", decision)

    def dance_call_ok(self) -> bool:
        now = time.monotonic()
        if self.last_dance_call and now - self.last_dance_call < DANCE_CALL_GAP:
            return False
        self.last_dance_call = now
        return True

    def set_cam(self, on: bool):
        with self.lock:
            self.cam_on = on
            if on:
                self.vibe_due = False
        self.notice("📷 Crowd camera on: it scores the dance floor every 2 minutes." if on
                    else "📷 Crowd camera off: back to asking you for vibe scores.")

    def find_song(self, text: str) -> Song | None:
        """A song from tonight's list, or else the best clean match on YouTube Music."""
        req = parse_request(text)
        match = self.local_match(req)
        if match is None:
            hit = self.search_youtube(f"{req.title} {req.artist}".strip())
            if not hit:
                return None
            req.video_id = hit["videoId"]
            req.seconds = hit.get("duration_seconds")
            req.title = hit.get("title") or req.title
            req.artist = ", ".join(a["name"] for a in hit.get("artists") or []) or req.artist
            match = next((s for s in self.everything if s.key == req.key), None)
            if match is None:
                match = req
                with self.lock:
                    self.everything.append(req)
                self.add_to_playlist(req)
        return match

    def local_match(self, req: Song) -> Song | None:
        """A song on tonight's list: the exact title, or one the guest only typed part of."""
        exact = next((s for s in self.everything if s.key == req.key), None)
        if exact or len(req.key) < 4:
            return exact
        return next((s for s in self.everything if s.video_id and req.key in s.key), None)

    def search_youtube(self, query: str) -> dict | None:
        """The best clean match on YouTube Music. Tries a fresh signed-out search first (the
        saved sign-in can expire mid-party), then the signed-in one, then music videos."""
        if self._search_yt is None:
            try:
                from ytmusicapi import YTMusic
                self._search_yt = YTMusic()
            except Exception:
                self._search_yt = self.yt
        clean = lambda r: r.get("videoId") and not r.get("isExplicit") \
            and not title_looks_explicit(r.get("title") or "")
        for yt in dict.fromkeys([self._search_yt, self.yt]):
            for kind in ("songs", "videos"):
                for attempt in (1, 2):
                    try:
                        hit = next((r for r in yt.search(query, filter=kind, limit=5) or [] if clean(r)), None)
                        if hit:
                            return hit
                        break
                    except Exception as e:
                        print(f"  (song search for '{query}' failed: {type(e).__name__}, retrying)")
                        time.sleep(0.5)
        return None

    def request(self, text: str):
        text = text.strip()
        if not text:
            return
        match = self.find_song(text)
        if match is None:
            self.notice(f"🙋 Couldn't find '{parse_request(text).title}' on YouTube Music.")
            return
        with self.lock:
            self.played.discard(match.key)
            self.inserts.append((match, "request"))
        self.log_request(match, "the host")
        self.notice(f"🙋 Request '{match.title}' " + ("is coming up now." if self.request_now() else "plays next."))

    def guest_request(self, name: str, text: str, ip: str) -> tuple[bool, str]:
        """A request from a guest's phone. The most-requested song plays first; on a tie,
        the one asked for first."""
        name = clean_name(name)
        text = " ".join(text.split())[:80]
        if not name:
            return False, "Please write your name."
        if not text:
            return False, "Please write the song name."
        song = self.find_song(text)
        if song is None:
            return False, "Couldn't find that song. Try adding the singer's name."
        with self.lock:
            if is_blocked(song, *self.blocked) or song.full:
                return False, f"Sorry, '{song.title}' isn't on tonight's list."
            if self.current and song.key == self.current.key:
                return False, f"'{song.title}' is playing right now! 🎉"
            r = self.guest_reqs.setdefault(song.key, {"song": song, "names": [], "ips": set(), "first": time.time()})
            if ip in r["ips"]:
                return False, f"You've already asked for '{song.title}'."
            r["ips"].add(ip)
            if name not in r["names"]:
                r["names"].append(name)
            self.played.discard(song.key)
            pos = [q["song"].key for q in self.guest_queue()].index(song.key) + 1
        others = len(r["names"]) - 1
        self.notice(f"📱 {name} requested '{song.title}'" + (f" (+{others} more)" if others else ""))
        self.log_request(song, name)
        if self.request_now() and pos == 1:
            return True, f"Got it, {name}! '{song.title}' starts in a few seconds 🎉"
        return True, f"Got it, {name}! '{song.title}' is number {pos} in the request queue."

    def guest_queue(self) -> list[dict]:
        return sorted(self.guest_reqs.values(), key=lambda r: (-len(r["names"]), r["first"]))

    def queue_view(self) -> list[dict]:
        with self.lock:
            return [{"title": r["song"].title, "artist": r["song"].lead_artist, "count": len(r["names"]),
                     "who": who(r["names"])} for r in self.guest_queue()][:10]

    def request_now(self) -> bool:
        """Mix into the request straight away, unless a request or the birthday song is playing."""
        with self.lock:
            cur = self.current
            if not self.started or not cur or cur.full or self.current_reason in ("guest", "request", "birthday"):
                return False
            self.force_next = True
            return True

    def putback(self, video_id: str):
        """The page dropped a song it had lined up; let it play later."""
        with self.lock:
            for s in self.everything:
                if s.video_id == video_id and (not self.current or s.key != self.current.key):
                    self.played.discard(s.key)

    def log_request(self, song: Song, name: str):
        """Keep every request with who asked, in requests.csv and the playlist's description."""
        with self.lock:
            r = self.request_log.setdefault(song.key, {"song": song, "names": [], "at": dt.datetime.now()})
            if name not in r["names"]:
                r["names"].append(name)
        new = not REQUEST_LOG.exists()
        with REQUEST_LOG.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "song", "artist", "requested_by"])
            w.writerow([dt.datetime.now().isoformat(timespec="seconds"), song.title, song.artist, name])
        threading.Thread(target=self._update_playlist, args=(song,), daemon=True).start()

    def _update_playlist(self, song: Song):
        pid = self.playlist_id()
        if not pid:
            return
        with self.lock:
            rows = sorted(self.request_log.values(), key=lambda r: r["at"])
            lines = [f"{r['at']:%I:%M %p}".lstrip("0") + f"  {r['song'].title} – requested by {who_all(r['names'])}"
                     for r in rows]
        head = f"Songs requested at {self.cfg.birthday_person_name}'s party:"
        while lines and len(head) + sum(len(l) + 1 for l in lines) > 4900:
            lines.pop(0)  # the description has a size limit; keep the latest
        try:
            self.yt.add_playlist_items(pid, [song.video_id], duplicates=False)
        except Exception:
            pass  # usually: already in the playlist
        try:
            self.yt.edit_playlist(pid, description="\n".join([head] + lines))
        except Exception as e:
            if not self._playlist_warned:
                self._playlist_warned = True
                self.notice(f"Couldn't write requests into the playlist ({type(e).__name__}); "
                            "they're saved in requests.csv on this computer.")

    def playlist_id(self) -> str | None:
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.playlist_link or "").query).get("list", [None])[0]

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
                self.vibe_due = not self.cam_on
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
                "up_next": self.up_next(), "queue": self.queue_view(), "guest_url": guest_url(),
                "singalong": self.singalong,
            }


def serve(director: Director, songbook: Songbook, public: bool = True) -> str:
    title = html.escape(f"{director.cfg.birthday_person_name}'s Birthday Party DJ")
    page = PAGE.replace("__FADE__", str(director.cfg.crossfade_seconds)).replace("__TITLE__", title)
    guest_page = GUEST_PAGE.replace("__TITLE__", html.escape(f"{director.cfg.birthday_person_name}'s Birthday Party"))

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body=b"", kind="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj):
            self._send(200, json.dumps(obj).encode(), "application/json")

        public = False  # True on the server behind the public link

        def _guest(self, method: str, u) -> bool:
            """Guests' phones reach only the request page; everything else is for this device."""
            ip = (self.headers.get("Cf-Connecting-Ip") or "public") if self.public else self.client_address[0]
            if not self.public and (ip.startswith("127.") or ip == "::1"):
                if not (u.path in ("/req", "/api/queue") or (method == "POST" and u.path == "/api/req")):
                    return False
            if method == "GET" and u.path == "/req":
                self._send(200, guest_page.encode())
            elif method == "GET" and u.path == "/api/queue":
                self._json({"queue": director.queue_view(), "now": director.current.title if director.current else None})
            elif method == "POST" and u.path == "/api/req":
                q = urllib.parse.parse_qs(u.query)
                ok, msg = director.guest_request(q.get("name", [""])[0], q.get("song", [""])[0], ip)
                self._json({"ok": ok, "msg": msg})
            else:
                self._send(403, b"This page is only for the DJ's device.", "text/plain")
            return True

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            if self._guest("GET", u):
                return
            if songbook.handle(self, "GET", u.path, {}):
                return
            if u.path == "/state":
                return self._json(director.state())
            if u.path == "/qr.svg":
                return self._send(200, qr_svg(guest_url() or ""), "image/svg+xml")
            if u.path.startswith("/audio/"):
                f = AUDIO_DIR / Path(urllib.parse.unquote(u.path[7:])).name
                if f.exists():
                    kind = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".aiff": "audio/aiff"}.get(f.suffix, "application/octet-stream")
                    return self._send(200, f.read_bytes(), kind)
                return self._send(404)
            self._send(200, page.encode())

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            if self._guest("POST", u):
                return
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
                director.add_score(int(arg), "camera" if q.get("src") == ["cam"] else "host")
            elif u.path == "/singalong":
                director.singalong_done(arg, q.get("ok") == ["1"])
            elif u.path == "/putback":
                director.putback(arg)
            elif u.path == "/cam":
                director.set_cam(arg == "on")
            elif u.path == "/request":
                threading.Thread(target=director.request, args=(arg,), daemon=True).start()
            elif u.path == "/block":
                return self._json({"skip": director.block(arg)})
            self._json({"ok": True})

        def log_message(self, *args):
            pass

    class GuestHandler(Handler):
        public = True

    # Open to the Wi-Fi so guests can scan the QR code; only the request page is shared.
    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
        guests = http.server.ThreadingHTTPServer(("127.0.0.1", GUEST_PORT), GuestHandler)
    except OSError:
        raise SystemExit("The DJ is already running in another Terminal window. Close that one first "
                         "(press Ctrl-C in it), then run python dj.py again.") from None
    for srv in (server, guests):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    if public:
        threading.Thread(target=open_public_link, args=(director,), daemon=True).start()
    return f"http://localhost:{PORT}/"


def open_public_link(director: Director):
    """Give the request page a public web address, so guests on mobile data can use it too.
    Only the request page is behind it, and it closes when the DJ stops."""
    try:
        from pycloudflared import try_cloudflare

        urls = try_cloudflare(port=GUEST_PORT, verbose=False)
    except Exception as e:
        director.notice(f"📱 Couldn't open the public request link ({type(e).__name__}); "
                        "guests can still use the QR code on the Wi-Fi.")
        return
    # Keep reading the tunnel's log so it never stalls on a full pipe.
    threading.Thread(target=lambda: [None for _ in urls.process.stderr], daemon=True).start()
    PUBLIC["url"] = urls.tunnel
    director.notice("📱 Guests can now request songs from any network: the QR code has the public link.")


def run(cfg, yt, plan, playlist_link: str | None, config_path: str, songs_path: str = "songs.yaml",
        open_browser: bool = True, on_ready=None, public: bool = True):
    AUDIO_DIR.mkdir(exist_ok=True)
    director = Director(cfg, yt, plan, playlist_link, config_path)
    director.prepare()
    book = Songbook(songs_path, yt, director)
    book.page_title = f"{cfg.birthday_person_name}'s party songs"
    url = serve(director, book, public)
    if on_ready:
        on_ready(url)
    if open_browser:
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
 #sing{display:none;font-size:30px;font-weight:800;color:#ffd54f;margin:10px 0;animation:pulse .6s infinite alternate}
 #sing div{font-size:22px;color:var(--txt);font-weight:600}
 @keyframes pulse{to{transform:scale(1.06)}}
 .snd{display:block;margin-top:10px;color:var(--dim);font-size:14px} .snd span{float:right;color:var(--txt)}
 .snd input{width:100%;padding:0;accent-color:var(--pink)}
</style></head><body><main>
<div id="toast"></div>
<h1>🎧 __TITLE__</h1>
<div style="margin-bottom:8px"><a href="/songs" id="songslink" style="color:var(--pink);font-size:18px">🎵 See, add or remove party songs</a> <small style="color:var(--dim)">(the music keeps playing)</small></div>
<div id="songsbox" style="position:fixed;inset:0;background:var(--bg);z-index:50;display:none;flex-direction:column">
 <div style="text-align:right;padding:8px"><button class="act" id="songsclose">✕ Back to the DJ</button></div>
 <iframe id="songsframe" style="flex:1;border:0;width:100%"></iframe></div>
<div id="down">The DJ program isn't running. In Terminal run: <b>python dj.py</b></div>
<button id="start">▶ START THE PARTY</button>
<div id="players"><div id="p0"></div><div id="p1"></div></div>
<div id="ui" hidden><div id="left">
 <div class="card"><div id="phase" style="color:var(--dim)"></div>
  <div id="title">…</div><div id="artist"></div><div id="voice"></div><div id="sing"></div><div id="bar"><div id="fill"></div></div></div>
 <div class="card" id="camcard"><div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center;justify-content:center">
  <div style="flex:1;min-width:240px"><div style="font-size:22px;font-weight:700">📷 Crowd camera</div>
   <div id="camlabel" style="font-size:26px;font-weight:700;margin:10px 0;color:var(--pink)">Off</div>
   <div style="height:14px;background:#333;border-radius:7px;overflow:hidden;margin-bottom:12px"><div id="camfill" style="height:100%;width:0;background:#7cb342;transition:width .4s"></div></div>
   <button class="act" id="cam" style="background:var(--pink);font-size:20px;padding:14px 26px">📷 Turn camera on</button>
   <div style="color:var(--dim);font-size:13px;margin-top:10px">Point it at the dance floor. It measures how much people move and steers the music. Only a movement number is kept: no video or photos are saved or sent, and no faces are looked at.</div></div>
  <div style="flex:1.2;min-width:260px"><video id="camv" autoplay muted playsinline style="width:100%;max-height:300px;background:#000;border-radius:14px;transform:scaleX(-1)"></video></div>
 </div></div>
 <div class="card"><b>Pick the vibe</b><div class="row" style="margin-top:10px">
  <button class="mode" data-m="auto" style="background:#455a64">🤖 Auto</button>
  <button class="mode" data-m="1" style="background:#3949ab">😌 Chill</button>
  <button class="mode" data-m="2" style="background:#00897b">🙂 Groove</button>
  <button class="mode" data-m="3" style="background:#7cb342">💃 Dance</button>
  <button class="mode" data-m="4" style="background:#fb8c00">🔥 Bangers</button>
  <button class="mode" data-m="5" style="background:#e53935">🚀 On fire</button></div></div>
 <div class="card row">
  <button class="act" id="stop">⏹ Stop music</button>
  <button class="act" id="mute">🔇 DJ voice off</button>
  <button class="act" id="skip">⏭ Next song</button>
  <button class="act" id="hype">🎤 Hype the crowd</button>
  <button class="act" id="blk">🚫 Block this song</button>
  <button class="act" id="blka">🚫 Block this artist</button></div>
 <div class="card"><b>Request a song</b><div style="margin-top:10px">
  <button class="act" id="mic" title="Say the song name">🎙 Speak</button>
  <input id="req" placeholder="Song name - Artist"> <button class="act" id="reqb">Add</button></div></div>
 <div class="card"><b>For you</b><div id="scores" style="color:var(--dim)"></div><ul id="notices"></ul></div>
</div>
<div id="side"><div class="card"><b>⏭ Up next</b><div id="nxtitle">…</div><div id="nxartist"></div></div>
 <div class="card"><b>📱 Guests: scan to request a song</b>
  <div id="qr" style="background:#fff;padding:10px;border-radius:12px;width:fit-content;margin:10px auto"></div>
  <div id="qrurl" style="color:var(--dim);font-size:13px;word-break:break-all"></div>
  <div style="color:var(--dim);font-size:12px;margin-top:4px">Guests need to be on the same Wi-Fi.</div></div>
 <div class="card"><b>🙋 Request queue</b><div style="color:var(--dim);font-size:12px">Most asked-for first, then whoever asked first</div><ol id="queue" style="text-align:left;padding-left:22px;margin:8px 0"></ol></div>
 <div class="card" style="text-align:left"><b>🎚 Sound</b>
  <label class="snd">Music volume <span id="vmusic"></span><input type="range" id="smusic" min="0" max="100"></label>
  <label class="snd">DJ voice volume <span id="vvoice"></span><input type="range" id="svoice" min="0" max="100"></label>
  <label class="snd">Music under the DJ voice <span id="vduck"></span><input type="range" id="sduck" min="5" max="60"></label>
  <div style="color:var(--dim);font-size:12px;margin-top:6px">Bass and treble: YouTube's player doesn't let web pages change them, so set those on the speaker (or its app).</div></div>
</div>
</div>
<div id="overlay"><h2>📊 Vibe check! How's the crowd?</h2><div class="row">
 <button class="mode" style="background:#3949ab" onclick="score(1)">1<br><small>chill</small></button>
 <button class="mode" style="background:#00897b" onclick="score(2)">2</button>
 <button class="mode" style="background:#7cb342" onclick="score(3)">3</button>
 <button class="mode" style="background:#fb8c00" onclick="score(4)">4</button>
 <button class="mode" style="background:#e53935" onclick="score(5)">5<br><small>on fire</small></button></div></div>
</main>
<script>
const FADE = __FADE__, PREP = 25;
// Sound controls (kept on this computer between runs).
const SOUND = Object.assign({music: 100, voice: 100, duck: 22}, (()=>{ try { return JSON.parse(localStorage.getItem('dj-sound')||'{}'); } catch(e){ return {}; } })());
let DUCK = SOUND.duck, pendingForce = false;
let stopped = false, P = [null, null], ready = 0, active = 0, cur = null, upcoming = null, busy = false, fetching = false;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let shownQR = null;
function toast(t){ const e=$('toast'); e.textContent=t; e.style.display='block'; clearTimeout(e.t); e.t=setTimeout(()=>e.style.display='none',2500); }
async function post(path){ const r = await fetch(path,{method:'POST'}); if(!r.ok) throw 0; return r.json(); }
function ramp(p, from, to, secs){ return new Promise(res=>{ const steps=Math.max(1,Math.round(secs*10)); let i=0;
  p.setVolume(from); const t=setInterval(()=>{ i++; p.setVolume(from+(to-from)*i/steps); if(i>=steps){clearInterval(t); res();} },100); }); }
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
function fxAudio(name){ const a=new Audio('/audio/'+name); a.volume=SOUND.voice/100; a.play().catch(()=>{}); return a; }
function playAudio(url, rate){ return new Promise(res=>{ const a=new Audio(url); a.volume=SOUND.voice/100; a.playbackRate=rate||1; a.onended=res; a.onerror=res; a.play().catch(res); }); }
async function talk(list, p){
  if(!list || !list.length || SOUND.mute) return;
  if(p) await ramp(p, 100, DUCK, 1);
  for(const a of list){ $('voice').textContent='🎤 '+a.text; await playAudio(a.url); }
  $('voice').textContent=''; if(p) ramp(p, DUCK, 100, 1.5);
}
function onYouTubeIframeAPIReady(){
  for(const i of [0,1]) P[i] = new YT.Player('p'+i,{height:'180',width:'320',playerVars:{origin:location.origin,playsinline:1,controls:0,disablekb:1},
    events:{onReady:()=>{ const raw = P[i].setVolume.bind(P[i]);   // every level is scaled by the music volume
              P[i].setVolume = v => { P[i]._v = v; raw(Math.round(v*SOUND.music/100)); }; ready++; }, onError:()=>{ if(i===active && cur) next(true); },
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
    if(SOUND.mute) t.announce = [];   // DJ voice switched off: music only
    const target = (t.announce && t.announce.length) ? DUCK : 100;
    const fxk = (!err && old && t.fx) ? t.fx : '';
    if(fxk === 'riser'){            // trance-style build-up over the old song, then the drop
      $('voice').textContent = '🚀 Build-up…'; fxAudio('fx_riser.wav');
      await ramp(old, old._v ?? 100, 55, 4);
      fxAudio('fx_impact.wav'); $('voice').textContent = '';
      await Promise.all([ramp(p, 0, target, 0.3), ramp(old, old._v ?? 55, 0, 0.8).then(()=>old.stopVideo())]);
    } else if(fxk.startsWith('scratch:')){   // scratch out of the old song, cut into the new one
      fxAudio(fxk.slice(8)); await ramp(old, old._v ?? 100, 0, 0.7); old.stopVideo();
      await ramp(p, 0, target, 1);
    } else {
      const fades = [ramp(p, 0, target, err||!old ? 1.5 : FADE)];
      if(old) fades.push(ramp(old, old._v ?? 100, 0, FADE).then(()=>old.stopVideo()));
      await Promise.all(fades);
    }
    if(target===DUCK){ for(const a of t.announce){ $('voice').textContent='🎤 '+a.text; await playAudio(a.url);} $('voice').textContent=''; ramp(p, DUCK, 100, 1.5); }
  } catch(e){ console.log(e); } finally { busy=false; }
}
setInterval(()=>{   // the DJ's ear: when to fetch the next song and when to mix
  if(!cur || busy || stopped) return; const p=P[active]; if(!p || !p.getCurrentTime) return;
  const t=p.getCurrentTime(), d=p.getDuration()||0, end=Math.min(cur.until, d ? d-0.5 : cur.until), left=end-t;
  if(d) $('fill').style.width=Math.min(100,100*(t-cur.start)/Math.max(1,end-cur.start))+'%';
  if(singing) return;
  const sg = cur.sing;   // a sing-along drop is waiting: find the hook, then drop the music
  if(sg && t >= cur.start){
    if(sg.when === undefined){
      const fit = (sg.at||[]).find(x => x >= t+6 && x <= end-22);
      sg.when = fit !== undefined ? fit : (!(sg.at||[]).length && end-t > 32 ? t+6 : null);
      if(sg.when === null){ cur.sing = null; post('/singalong?v='+sg.id+'&ok=0'); }
    } else if(t >= sg.when-4){ cur.sing = null; singAlong(sg, p); return; }
  }
  if(pendingForce){ pendingForce = false; forceNow(); return; }
  if(left < PREP && !upcoming && !fetching) fetchNext(false);
  if(left < FADE && upcoming) next(false);
}, 300);
let singing = false, seenSing = 0;
async function singAlong(sg, p){   // the crowd's on fire: music down, everybody sings the hook
  singing = true;
  try{
    await ramp(p, p._v ?? 100, DUCK, 0.8);
    if(sg.announce && !SOUND.mute){ $('voice').textContent='🎤 '+sg.announce.text; await playAudio(sg.announce.url); $('voice').textContent=''; }
    $('sing').innerHTML = '🎤 Everybody sing!' + (sg.words ? '<div>“'+esc(sg.words)+'”</div>' : ''); $('sing').style.display='block';
    await ramp(p, DUCK, Math.min(DUCK, 12), 0.6);
    await sleep(8000);
    $('sing').style.display='none';
    if(!stopped && p === P[active]) await ramp(p, p._v, 100, 1.5);
    post('/singalong?v='+sg.id+'&ok=1');
  } catch(e){ console.log(e); } finally { singing = false; }
}
function offerSing(o){   // the vibe hit 5: the drop goes on whichever song it was made for
  if(!o || o.id === seenSing) return; seenSing = o.id;
  if(cur && cur.vid === o.vid && !cur.sing) cur.sing = o;
  else if(upcoming && upcoming.vid === o.vid && !upcoming.sing) upcoming.sing = o;
  else post('/singalong?v='+o.id+'&ok=0');
}
async function load(){
  try{ const s = await (await fetch('/state')).json(); $('down').style.display='none';
    document.querySelectorAll('.mode[data-m]').forEach(b=>b.classList.toggle('on', String(s.mode)===b.dataset.m));
    $('overlay').style.display = s.vibe_due ? 'flex' : 'none';
    $('phase').textContent = s.started ? (s.phase+(s.birthday?'  ·  🎂 birthday at '+s.birthday:'')) : '';
    $('scores').textContent = s.scores.length ? 'Vibe scores: '+s.scores.join(', ') : '';
    $('notices').innerHTML = s.notices.map(n=>'<li>'+n.replace(/</g,'&lt;')+'</li>').join('');
    const n = upcoming && !upcoming.done ? upcoming : s.up_next;
    $('nxtitle').textContent = n ? n.title : 'Nothing left to play'; $('nxartist').textContent = n ? n.artist+'  ·  '+n.tier : '';
    $('queue').innerHTML = s.queue.length ? s.queue.map(q=>'<li>'+esc(q.title)+' <small style="color:var(--dim)">· '+esc(q.who)+(q.count>1?' ('+q.count+')':'')+'</small></li>').join('')
      : '<li style="list-style:none;margin-left:-22px;color:var(--dim)">No requests yet</li>';
    if(s.guest_url && s.guest_url !== shownQR){ shownQR = s.guest_url; $('qrurl').textContent = s.guest_url;
      $('qr').innerHTML = '<img alt="QR code" width="180" height="180" src="/qr.svg?'+Date.now()+'">'; }
    if(s.force_next && cur) pendingForce = true;
    offerSing(s.singalong);
  } catch(e){ $('down').style.display='block'; }
}
setInterval(load, 1000); load();
// A request came in: mix into it now. A request already lined up goes first.
async function forceNow(){
  if(busy || fetching){ pendingForce = true; return; }
  if(upcoming && !upcoming.req){ post('/putback?v='+upcoming.vid);
    if(upcoming.sing) post('/singalong?v='+upcoming.sing.id+'&ok=0'); upcoming = null; }
  next(false);
}
function applySound(){
  try { localStorage.setItem('dj-sound', JSON.stringify(SOUND)); } catch(e){}
  DUCK = SOUND.duck; P.forEach(p => { if(p && p._v !== undefined) p.setVolume(p._v); });
  $('vmusic').textContent = SOUND.music+'%'; $('vvoice').textContent = SOUND.voice+'%'; $('vduck').textContent = SOUND.duck+'%';
}
for(const k of ['music','voice','duck']){ const el = $('s'+k); el.value = SOUND[k]; el.oninput = ()=>{ SOUND[k] = +el.value; applySound(); }; }
applySound();
$('start').onclick = async ()=>{
  if(ready<2){ toast('Loading the player, one moment…'); return; }
  await post('/start'); $('start').remove(); $('ui').hidden=false; next(false);
};
document.querySelectorAll('.mode[data-m]').forEach(b=>b.onclick=()=>post('/mode?v='+b.dataset.m).then(()=>{toast('Vibe: '+b.textContent.trim()); load();}).catch(()=>$('down').style.display='block'));
window.score = n => post('/score?v='+n).then(()=>{toast('Vibe '+n+' saved ✓'); load();});
function setStopped(v){ stopped=v; $('stop').textContent = v ? '▶ Play music' : '⏹ Stop music'; }
$('stop').onclick = async ()=>{
  if(!cur || busy) return; const p=P[active];
  if(!stopped){ setStopped(true); await ramp(p, p._v ?? 100, 0, 1.5); p.pauseVideo(); toast('Music stopped'); }
  else { setStopped(false); p.playVideo(); ramp(p, 0, 100, 1.5); toast('Music back on'); }
};
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
$('songslink').onclick = e => { e.preventDefault(); $('songsframe').src='/songs'; $('songsbox').style.display='flex'; };
$('songsclose').onclick = () => { $('songsbox').style.display='none'; $('songsframe').src='about:blank'; load(); };
function heard(said){ $('req').value = said; toast('Heard: '+said); setTimeout(()=>$('reqb').click(), 600); }
$('mic').onclick = ()=>{
  const p = P[active], wasStopped = stopped;
  const done = ()=>{ $('mic').classList.remove('on'); $('mic').textContent='🎙 Speak'; if(p && cur && !wasStopped) ramp(p, 15, 100, 1); };
  if(window.AndroidSpeech){   // inside the phone app: the phone's own speech recogniser
    window.onAndroidSpeech = said => { done(); if(said) heard(said); else toast("Didn't catch that, try again"); };
    $('mic').classList.add('on'); $('mic').textContent='🎙 Listening…';
    if(p && cur && !stopped) p.setVolume(15);
    AndroidSpeech.listen(); return;
  }
  if(!SR){ toast('The mic needs Google Chrome'); return; }
  const r = new SR(); r.lang='en-IN'; r.interimResults=false; r.maxAlternatives=1;
  $('mic').classList.add('on'); $('mic').textContent='🎙 Listening…';
  if(p && cur && !stopped) p.setVolume(15);   // turn the music down so it can hear you
  r.onresult = e=>heard(e.results[0][0].transcript.trim());
  r.onerror = e=>{ toast(e.error==='not-allowed' ? 'Allow the microphone for this page, then try again' : "Didn't catch that, try again"); };
  r.onend = done; r.start();
};
// Crowd camera: compares tiny grey frames to measure movement. Nothing leaves this page.
const CAM_EVERY = 120, CAM_LEVELS = [1.5, 3, 5, 8], CAM_NAMES = ['','Quiet','Swaying','Grooving','Dancing','Going wild'];
let cam = null, camPrev = null, camHist = [], camTimer = null, camSend = null;
const camCanvas = document.createElement('canvas'); camCanvas.width = 64; camCanvas.height = 48;
const camCtx = camCanvas.getContext('2d', {willReadFrequently: true});
const camScore = m => 1 + CAM_LEVELS.filter(t => m >= t).length;
function camTick(){
  camCtx.drawImage($('camv'), 0, 0, 64, 48);
  const px = camCtx.getImageData(0, 0, 64, 48).data, g = new Float32Array(64*48);
  for(let i=0;i<g.length;i++) g[i] = (px[4*i]+px[4*i+1]+px[4*i+2])/3;
  if(camPrev){ let d=0; for(let i=0;i<g.length;i++) d += Math.abs(g[i]-camPrev[i]); camHist.push(d/g.length); }
  camPrev = g; if(camHist.length > CAM_EVERY*2) camHist.shift();
  const recent = camHist.slice(-20), m = recent.reduce((a,b)=>a+b,0)/Math.max(1,recent.length), sc = camScore(m);
  $('camfill').style.width = Math.min(100, m/10*100)+'%'; $('camlabel').textContent = 'Right now: '+CAM_NAMES[sc]+' ('+sc+'/5)';
}
async function camOn(){
  try { cam = await navigator.mediaDevices.getUserMedia({video:{width:320,height:240}, audio:false}); }
  catch(e){ toast('Allow the camera for this page, then try again'); return; }
  $('camv').srcObject = cam;
  $('cam').textContent = 'Turn camera off'; $('cam').style.background = '#333'; camHist = []; camPrev = null;
  camTimer = setInterval(camTick, 500);
  camSend = setInterval(()=>{ if(!camHist.length) return;
    const avg = camHist.reduce((a,b)=>a+b,0)/camHist.length; camHist = [];
    post('/score?src=cam&v='+camScore(avg)).then(load); }, CAM_EVERY*1000);
  post('/cam?v=on').then(load);
}
function camOff(){
  clearInterval(camTimer); clearInterval(camSend); if(cam) cam.getTracks().forEach(t=>t.stop()); cam = null;
  $('camv').srcObject = null; $('camlabel').textContent = 'Off'; $('camfill').style.width = '0';
  $('cam').textContent = '📷 Turn camera on'; $('cam').style.background = 'var(--pink)'; post('/cam?v=off').then(load);
}
$('cam').onclick = () => cam ? camOff() : camOn();
$('skip').onclick = ()=>{ upcoming=null; next(false); };
function showMute(){ $('mute').textContent = SOUND.mute ? '🔊 DJ voice on' : '🔇 DJ voice off';
  $('mute').style.background = SOUND.mute ? '#b71c1c' : ''; }
$('mute').onclick = ()=>{ SOUND.mute = !SOUND.mute; applySound(); showMute();
  toast(SOUND.mute ? 'DJ voice off: no announcements, just music' : 'DJ voice back on'); };
showMute();
$('hype').onclick = async ()=>{ const r = await post('/hype'); talk(r.announce, P[active]); };
$('blk').onclick = async ()=>{ const r = await post('/block?v=song'); if(r.skip){ upcoming=null; next(false);} load(); };
$('blka').onclick = async ()=>{ const r = await post('/block?v=artist'); if(r.skip){ upcoming=null; next(false);} load(); };
$('reqb').onclick = ()=>{ const v=$('req').value.trim(); if(!v) return; post('/request?v='+encodeURIComponent(v)).then(()=>{toast('Looking for it…'); $('req').value='';}); };
</script>
<script src="https://www.youtube.com/iframe_api"></script>
</body></html>"""


GUEST_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Request a song</title>
<style>
 :root{--bg:#0d0d12;--card:#1b1b24;--pink:#ff2d7a;--txt:#f4f4f8;--dim:#a0a0b0}
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--txt);text-align:center}
 main{max-width:520px;margin:auto;padding:16px} h1{font-size:26px;margin:10px 0 2px} .sub{color:var(--dim);margin-bottom:12px}
 .card{background:var(--card);border-radius:16px;padding:16px;margin:12px 0;text-align:left}
 label{display:block;color:var(--dim);font-size:14px;margin:10px 0 4px}
 input{width:100%;font-size:18px;padding:13px;border-radius:12px;border:0}
 button{font-size:19px;padding:14px;border-radius:14px;border:0;background:var(--pink);color:#fff;width:100%;margin-top:14px;cursor:pointer}
 button:disabled{opacity:.6} .small{width:auto;font-size:14px;padding:7px 12px;margin:0;background:#333}
 #msg{min-height:24px;margin-top:12px;font-size:17px} .ok{color:#7cdb7c} .bad{color:#ff8a80}
 .q{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #2a2a35}
 .q div{flex:1} .q small{color:var(--dim)} .n{color:var(--pink);font-weight:700;width:26px}
</style></head><body><main>
<h1>🎉 __TITLE__</h1><div class="sub">Ask the DJ for a song!</div>
<div id="now" class="sub"></div>
<div class="card">
 <label for="name">Your name (the DJ will say it)</label><input id="name" maxlength="24" placeholder="e.g. Riya" autocomplete="given-name">
 <label for="song">Song</label><input id="song" maxlength="80" placeholder="Song name, and singer if you know">
 <button id="go">🎶 Request it</button><div id="msg"></div></div>
<div class="card"><b>Request queue</b> <small style="color:var(--dim)">Most asked-for plays first</small><div id="queue"></div></div>
</main><script>
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
try { $('name').value = localStorage.getItem('dj-name') || ''; } catch(e){}
async function ask(song){
  const name = $('name').value.trim();
  if(!name){ $('msg').className='bad'; $('msg').textContent='Please write your name first.'; $('name').focus(); return; }
  try { localStorage.setItem('dj-name', name); } catch(e){}
  $('go').disabled = true; $('msg').className=''; $('msg').textContent = 'Finding it…';
  try {
    const r = await (await fetch('/api/req?'+new URLSearchParams({name, song}), {method:'POST'})).json();
    $('msg').className = r.ok ? 'ok' : 'bad'; $('msg').textContent = r.msg; if(r.ok) $('song').value = '';
  } catch(e){ $('msg').className='bad'; $('msg').textContent = "The DJ isn't taking requests right now."; }
  $('go').disabled = false; load();
}
$('go').onclick = () => { const s = $('song').value.trim(); if(!s){ $('msg').className='bad'; $('msg').textContent='Write a song name.'; return; } ask(s); };
$('song').onkeydown = e => { if(e.key==='Enter') $('go').click(); };
async function load(){
  try {
    const r = await (await fetch('/api/queue')).json();
    $('now').textContent = r.now ? '▶ Now playing: '+r.now : '';
    $('queue').innerHTML = r.queue.length ? r.queue.map((q,i)=>`<div class="q"><span class="n">${i+1}</span><div>${esc(q.title)}<br>
      <small>${esc(q.artist)} · asked by ${esc(q.who)}</small></div><button class="small" data-t="${esc(q.title)}">+ Me too</button></div>`).join('')
      : '<div style="color:var(--dim);padding:10px 0">No requests yet. Be the first!</div>';
    document.querySelectorAll('.small').forEach(b => b.onclick = () => ask(b.dataset.t));
  } catch(e){}
}
load(); setInterval(load, 5000);
</script></body></html>"""
