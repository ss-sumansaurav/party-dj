"""A human-sounding DJ voice: about 40 lines recorded once with ElevenLabs (free tier), saved as
clips in partydj/voice_pack/, and played on the night instead of the robot voice.

    python3 dj.py --config party-diwali-amit.yaml --voice-pack

asks for your ElevenLabs API key (typed, not shown, kept in .env, never printed), lets you pick a
voice, records the lines and plays you a sample. The clips go into the phone app too.

The lines never name a song (the screen shows that), so they work for any song. Lines that must
say something new on the night, like a guest's wish, still use the free voice.
"""
from __future__ import annotations

import getpass
import json
import os
import random
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

PACK = Path(__file__).parent / "voice_pack"
API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"
# Lively and expressive: low stability lets the voice move, high style pushes the delivery.
SETTINGS = {"stability": 0.3, "similarity_boost": 0.8, "style": 0.7, "use_speaker_boost": True}
DEFAULT_VOICE = ("TX3LPaxmHKxFdv7VOQHJ", "Liam")   # a lively built-in voice, if listing voices isn't allowed
LIKED = ("Liam", "Will", "Chris", "Josh", "Eric", "Charlie", "Brian", "Adam")

# {hosts} = "Amit and Priya", {host} = "Amit", {city} = "Melbourne" (from the party's settings).
DIWALI = {
    "opening": ["Happy Diwali, everybody! Welcome to {hosts}'s Diwali party{in_city}! I'm your DJ tonight, the diyas are lit, the vibe is set... so chalo, let's get this party started!"],
    "Warm-up": [
        "Ohhh, this one's a classic! Sing along, everybody!",
        "Diyas glowing, food is ready, and the music is ON! Let's go!",
        "Old is gold, my friends! Volume up!",
    ],
    "Build": [
        "Arre wah! I see some moves already! Keep it going!",
        "{host}, get everyone on the floor! Come on, come on!",
        "The energy is building, and I LOVE it!",
        "Full josh now, everybody! Let's gooo!",
    ],
    "Peak": [
        "Okay, THIS is the moment! Haath upar, hands all the way up!",
        "Turn it up, louder! This one is a total banger!",
        "Brighter than the fireworks outside! Everybody, jump!",
        "Dhol is coming in, you know what time it is! Balle balle!",
    ],
    "Peak 2": [
        "Thought we were done? No way! The night is still young!",
        "This Diwali party is next level! Don't stop now!",
        "Let me hear you{city_shout}! Make some noise!",
        "Ekdum full power! Here we go again!",
    ],
    "Wind-down": [
        "Alright, let's slow it down a little... grab someone special.",
        "Take a breather, and sing along with me.",
    ],
    "vibe_up": [
        "Arre, why so quiet? It's Diwali! I need more energy!",
        "Come on, I know you've got more than that! Let's turn it up!",
    ],
    "request": ["We have a request, and what a choice! Let's go!",
                "Somebody has great taste! Coming right up!"],
    "guest_request": ["Request from the crowd! Great choice, this one's for you!",
                      "You asked for it, you got it! Let's go!"],
    "dedication": ["A special dedication, with lots of love! This one's for you!"],
    "dance_floor": ["I see too many people sitting down! Chalo, everybody on the dance floor!",
                    "The dance floor is looking lonely! Grab a friend and come on up!"],
    "karaoke": ["Karaoke time! The words are on the screen, so sing it LOUD!",
                "Tonight, YOU are the singer! Everybody, sing along!"],
    "sing_along": ["This one is yours! Everybody sing!", "I can't hear you! Sing it with me!"],
    "hype": ["Make some noise for {hosts}! Louder! Let me hear you!",
             "Everybody, haath upar! Happy Diwali, what a party!"],
    "cake_10": ["Ten minutes to our Diwali moment! Find your family and friends, and get ready!"],
    "cake_5": ["Just five minutes to go! Everybody gather round, our Diwali moment is almost here!"],
    "birthday_intro": ["Can I have everyone's attention, please? Gather round, diyas ready... it's our Diwali moment with {hosts}!"],
    "cake": ["Three... two... one... HAPPY DIWALI, everybody! Shubh Deepavali!"],
    "shoutout": ["Happy Diwali{city_shout}! A big, big thank you to {hosts} for bringing everyone together tonight!"],
    "closing": ["You were all amazing tonight! Happy Diwali once again. {hosts}, thank you for this lovely party. Good night, everybody!"],
}


def _hosts(cfg) -> str:
    return f"{cfg.host_name} and {cfg.co_host_name}" if getattr(cfg, "co_host_name", "") else cfg.host_name


def _first(name: str) -> str:
    return (str(name).lower().split() or [""])[0]


def _first_names(hosts: str) -> set[str]:
    """'AMIT and APARNA' -> {'amit', 'aparna'}"""
    return {_first(h) for h in str(hosts).lower().replace(" & ", " and ").split(" and ") if h.strip()}


def lines_for(cfg) -> list[tuple[str, str]]:
    """(kind, words) for this party, names filled in."""
    hosts = _hosts(cfg)
    city = (getattr(cfg, "city", "") or "").strip()
    words = {"hosts": hosts, "host": cfg.host_name, "in_city": f" in {city}" if city else "",
             "city_shout": f", {city}" if city else ""}
    return [(kind, text.format(**words)) for kind, texts in DIWALI.items() for text in texts]


# ---------- playing them on the night ----------
class Pack:
    """The recorded clips, by kind. Each kind's clips take turns so none repeats back to back."""

    def __init__(self, folder: Path = PACK, cfg=None):
        self.folder = folder
        try:
            data = json.loads((folder / "lines.json").read_text())
        except (OSError, ValueError):
            data = {}
        self.clips: dict[str, list[dict]] = data.get("clips", {})
        self.hosts = str(data.get("hosts", ""))
        self.why_not = ""
        if cfg is not None and self.clips:
            if getattr(cfg, "party_type", "") != "diwali":
                self.why_not = "it was recorded for a Diwali party"
            elif _first(cfg.host_name) not in _first_names(self.hosts):
                # recorded for another party: its names would be wrong
                self.why_not = f"it was recorded for {' and '.join(h.strip().title() for h in self.hosts.split(' and '))}'s party; this party's host is {cfg.host_name}"
            if self.why_not:
                self.clips = {}
        self.clips = {k: [c for c in v if (folder / c["file"]).exists()] for k, v in self.clips.items()}
        self.turn: dict[str, int] = {}
        self.rng = random.Random()

    def __bool__(self):
        return any(self.clips.values())

    def pick(self, kind: str) -> dict | None:
        clips = self.clips.get(kind)
        if not clips:
            return None
        if kind not in self.turn:
            self.turn[kind] = self.rng.randrange(len(clips))
        c = clips[self.turn[kind] % len(clips)]
        self.turn[kind] += 1
        return c


# ---------- recording them (on the Mac, once) ----------
def _call(path: str, key: str, body: dict | None = None) -> bytes:
    headers = {"xi-api-key": key, "Accept": "application/json" if body is None else "audio/mpeg"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        e.why = _why(e)
        raise


def _why(e: urllib.error.HTTPError) -> str:
    """ElevenLabs' own reason (never includes the key)."""
    try:
        d = json.loads(e.read().decode("utf-8", "replace")).get("detail")
        if isinstance(d, dict):
            return " ".join(str(x) for x in (d.get("status"), d.get("message")) if x)
        return str(d or "")[:300]
    except Exception:
        return ""


def _clean(key: str) -> str:
    """Nothing shows while you paste, so people paste twice or three times: keep one copy."""
    key = "".join(key.split())
    for n in range(2, 5):
        if len(key) % n == 0 and key == key[: len(key) // n] * n:
            return key[: len(key) // n]
    return key


def _save(key: str | None):
    """Put the key in .env (or take it out when key is None)."""
    env = Path(".env")
    lines = [l for l in (env.read_text().splitlines() if env.exists() else [])
             if not l.startswith("ELEVENLABS_API_KEY=")]
    if key:
        lines.append(f"ELEVENLABS_API_KEY={key}")
    env.write_text("\n".join(lines) + ("\n" if lines else ""))


def _ask_key() -> str:
    print("Paste your ElevenLabs API key (from elevenlabs.io > your profile > API Keys).")
    print("Nothing shows while you paste: paste it ONCE, then press Return.")
    key = _clean(getpass.getpass("API key: "))
    while key and not key.startswith("sk_"):
        print("That isn't the secret key. It must start with sk_ (the shorter 'key ID' won't work).")
        print("On elevenlabs.io > API Keys, press 'Create API key' and copy the sk_... value it shows once.")
        key = _clean(getpass.getpass("API key: "))
    if key and input("Keep it on this Mac for next time? [y/N] ").strip().lower() == "y":
        _save(key)
        print("Saved in .env (it's never uploaded or shared).")
    return key


def _key() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    key = _clean(os.environ.get("ELEVENLABS_API_KEY", ""))
    if key and not key.startswith("sk_"):
        print("The key saved on this Mac is a key ID, not the secret key, so I've removed it.")
        _save(None)
        key = ""
    return key or _ask_key()


def _choose_voice(key: str) -> tuple[str, str]:
    voices = json.loads(_call("/voices", key)).get("voices", [])
    if not voices:
        raise SystemExit("ElevenLabs returned no voices for this key.")
    mine = [v for v in voices if v.get("category") != "premade"]   # ones you added from the Voice Library
    built = sorted([v for v in voices if v.get("category") == "premade"],
                   key=lambda v: LIKED.index(v["name"].split()[0]) if v["name"].split()[0] in LIKED else 99)
    shown = (mine + built)[:12]
    print("\nVoices:")
    for i, v in enumerate(shown, 1):
        labels = v.get("labels") or {}
        about = ", ".join(x for x in (labels.get("accent"), labels.get("description") or labels.get("descriptive"),
                                      labels.get("use_case") or labels.get("use case")) if x)
        print(f"  {i}. {v['name']}" + (f"  ({about})" if about else "") + ("  ← yours" if v in mine else ""))
    got = input("Pick a voice number [1]: ").strip()
    v = shown[int(got) - 1] if got.isdigit() and 1 <= int(got) <= len(shown) else shown[0]
    return v["voice_id"], v["name"]


def record(cfg) -> int:
    if getattr(cfg, "party_type", "") != "diwali":
        print("The recorded voice is written for the Diwali party. Run it with the Diwali party file, e.g.")
        print("  python3 dj.py --config party-diwali-amit.yaml --voice-pack")
        return 1
    lines = lines_for(cfg)
    chars = sum(len(t) for _, t in lines)
    key = _key()
    if not key:
        print("No key, nothing recorded.")
        return 1
    try:
        sub = json.loads(_call("/user/subscription", key))
        left = sub.get("character_limit", 0) - sub.get("character_count", 0)
        print(f"These {len(lines)} lines use about {chars:,} characters; your account has {left:,} left this month.")
        if left < chars:
            print("Not enough left this month. Try again when it resets, or shorten the list.")
            return 1
    except urllib.error.HTTPError:
        print(f"These {len(lines)} lines use about {chars:,} characters (the free tier gives 10,000 a month).")
    for attempt in (1, 2):
        try:
            voice_id, name = _choose_voice(key)
            break
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 1:
                print("\nElevenLabs didn't accept that key. Usually it was pasted twice, or the key's")
                print("permissions are switched off. Let's try once more.")
                _save(None)
                key = _ask_key()
                if key:
                    continue
            print(f"Couldn't list the voices ({e.code}: {getattr(e, 'why', '') or 'no reason given'}).")
            voice_id, name = DEFAULT_VOICE
            print(f"Trying ElevenLabs' built-in voice {name} instead…")
            break
    tmp = PACK.with_name("voice_pack_new")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    index: dict[str, list[dict]] = {}
    print(f"\nRecording {len(lines)} lines in {name}'s voice…")
    for i, (kind, text) in enumerate(lines, 1):
        fname = f"{i:02d}_{kind.replace(' ', '_').lower()}.mp3"
        try:
            audio = _call(f"/text-to-speech/{voice_id}?output_format=mp3_44100_128", key,
                          {"text": text, "model_id": MODEL, "voice_settings": SETTINGS})
        except urllib.error.HTTPError as e:
            print(f"  ✗ line {i} failed ({e.code}: {getattr(e, 'why', '') or 'no reason given'}). Nothing was changed.")
            print("  If it's about the key: on elevenlabs.io open API Keys, make a new key with")
            print("  'Text to Speech' and 'Voices' allowed (or no restrictions), then run this again.")
            shutil.rmtree(tmp, ignore_errors=True)
            return 1
        (tmp / fname).write_bytes(audio)
        index.setdefault(kind, []).append({"file": fname, "text": text})
        print(f"  ✓ {i}/{len(lines)}  {text[:60]}")
    (tmp / "lines.json").write_text(json.dumps({"voice": name, "hosts": _hosts(cfg), "clips": index},
                                               ensure_ascii=False, indent=1))
    shutil.rmtree(PACK, ignore_errors=True)
    tmp.rename(PACK)
    print(f"\nDone: {len(lines)} clips in partydj/voice_pack/. The DJ uses them from now on.")
    sample = PACK / index["opening"][0]["file"]
    if shutil.which("afplay"):
        print("Playing the opening line…")
        subprocess.run(["afplay", str(sample)], check=False)
    return 0
