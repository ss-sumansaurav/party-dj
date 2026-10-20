"""Short English DJ lines and text-to-speech."""
from __future__ import annotations

import random
import shutil
import struct
import subprocess
import wave
from pathlib import Path

MAX_WORDS = 32  # about 15 seconds of speech

LINES = {
    "opening": [
        "Yo yo yo, what's up Mumbai! Welcome to {name}'s birthday bash, and no cap, {host} absolutely understood the assignment. Main character energy only tonight. Let's gooo!",
    ],
    "Warm-up": [
        "Okay okay, the vibes are already immaculate, fr fr. Up next, a total classic, {next}. Sing it, besties!",
        "Lowkey this one is pure nostalgia, highkey a banger. It's {next}, let's vibe!",
        "Sheesh, this crowd's got aura! Turn it up for {next}!",
        "It's giving retro, it's giving iconic. Here comes {next}!",
    ],
    "Build": [
        "Okayyy, the dance floor is heating up and I'm here for it! Let's go, {next}!",
        "Eighties and nineties are back and honestly? Goated. It's {next}, no skips!",
        "{host}, get the squad on the floor, it's literally {next}. We move!",
        "Vibe check: passed! Keep that energy, here comes {next}!",
    ],
    "Peak": [
        "Bro, this is where it gets unreal! Hands up for {next}!",
        "No cap, this one slaps so hard. Full volume, it's {next}!",
        "{name}, this one's for you, birthday legend! Absolute W incoming, {next}!",
        "The dhol is about to drop and it's gonna be bussin! Balle balle, {next}!",
    ],
    "Peak 2": [
        "You thought we were done? Not a chance, bestie! It's {next}!",
        "This party is straight up legendary. Keep it going, {next}!",
        "We are so back! Everyone on the floor for {next}!",
        "The energy is unmatched, fr fr. Let's go, {next}!",
    ],
    "Wind-down": [
        "Okay, slowing it down, but the vibes stay elite. Here's {next}.",
        "Grab your favourite person, it's a soft-launch moment. Here's {next}.",
        "Big feels incoming, no cap. Sing along, it's {next}.",
    ],
    "vibe_up": [
        "Hold up, the vibe's a little sleepy. We don't do that here! Wake up, it's {next}!",
        "Okay squad, I need more energy, like right now! Here comes {next}, let's goooo!",
    ],
    "request": [
        "Ayo, we got a request and it's a certified banger! This one's {next}, let's gooo!",
        "Request unlocked! Somebody here has elite taste. It's {next}!",
    ],
    "hype": [
        "Make some noise for {name}! Louder! This party is absolutely bussin!",
        "Everybody hands up, this is the moment! {host}, you ate with this party, no crumbs!",
        "Is this the best party in Mumbai tonight? No cap, it is! Let's gooo!",
    ],
    "birthday_intro": [
        "Okay everybody, attention please! Lights down, cake out. It's {name}'s main character moment, so make some noise!",
    ],
    "cake": [
        "Three, two, one! Cut that cake, {name}! Everybody together, happy birthday!",
    ],
    "shoutout": [
        "Happy birthday {name}, you absolute legend! Another year of pure W energy. Huge shoutout to {host}, this party ate and left no crumbs!",
    ],
    "closing": [
        "Mumbai, you were iconic tonight, no cap! Happy birthday again, {name}, and {host}, this party was goated. Peace out, love you all!",
    ],
}


class Writer:
    """Picks a line for each cue without repeating until a list is used up."""

    def __init__(self, name: str, host: str, seed: str):
        self.name, self.host = name, host
        self.rng = random.Random(seed)
        self.decks: dict[str, list[str]] = {}

    def line(self, kind: str, next_title: str = "") -> str:
        deck = self.decks.get(kind)
        if not deck:
            deck = list(LINES[kind])
            self.rng.shuffle(deck)
            self.decks[kind] = deck
        text = deck.pop().format(name=self.name, host=self.host, next=next_title)
        if len(text.split()) > MAX_WORDS:
            raise ValueError(f"Announcement too long for 15 seconds: {text}")
        return text


DJ_VOICE = "en-US-BrianNeural"  # young, casual male neural voice; change in config.yaml (dj_voice)
_warned = False


def _edge_tts(text: str, out: Path, voice: str):
    import asyncio

    import edge_tts

    async def go():
        await edge_tts.Communicate(text, voice, rate="+5%", pitch="+4Hz").save(str(out))

    asyncio.run(go())
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("edge-tts returned no audio")


def speak_to_file(text: str, path: Path, voice: str | None = None) -> Path:
    """Write speech audio with a young male neural voice (edge-tts).
    Falls back to gTTS, then to the Mac's `say`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out = path.with_suffix(".mp3")
        _edge_tts(text, out, voice or DJ_VOICE)
        return out
    except Exception as e:
        global _warned
        if not _warned:
            _warned = True
            print(f"  (DJ voice unavailable, using the backup voice: {type(e).__name__}. "
                  "Check the internet connection and run: pip install -r requirements.txt)")
    try:
        from gtts import gTTS

        out = path.with_suffix(".mp3")
        gTTS(text, lang="en", tld="co.in").save(str(out))
        return out
    except Exception as gtts_error:
        if shutil.which("say"):
            out = path.with_suffix(".aiff")
            voice = ["-v", "Rishi"] if _has_voice("Rishi") else (["-v", "Daniel"] if _has_voice("Daniel") else [])
            subprocess.run(["say", *voice, "-r", "205", "-o", str(out), text], check=True)
            return out
        raise RuntimeError(f"Couldn't make speech audio: {gtts_error}") from gtts_error


def _has_voice(name: str) -> bool:
    try:
        voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    except OSError:
        return False
    return any(line.split()[0] == name for line in voices.splitlines() if line.strip())


SPEED = "1.12"  # play speech a little faster for DJ energy
HORN = Path(__file__).with_name("horn.wav")


def make_horn(path: Path = HORN) -> Path:
    """Synthesise a short party air-horn sting (no recorded audio involved)."""
    if path.exists():
        return path
    rate = 22050
    frames = bytearray()
    for start_hz, length in ((480, 0.16), (480, 0.16), (480, 0.55)):
        n = int(rate * length)
        for i in range(n):
            t = i / rate
            hz = start_hz * (1 - 0.04 * i / n)  # slight droop, like a real horn
            # Buzzy chord: sawtooth waves a major third and a fifth apart
            v = sum(((t * hz * k) % 1.0) * 2 - 1 for k in (1, 1.26, 1.5)) / 3
            env = min(1.0, i / 300, (n - i) / 600)
            frames += struct.pack("<h", int(v * env * 0.45 * 32767))
        frames += bytes(2 * int(rate * 0.06))  # gap between blasts
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


def play(path: Path, horn: bool = True):
    """Play an announcement through the Mac's current output (the party speaker),
    with an air-horn sting first and slightly faster, punchier speech."""
    player = shutil.which("afplay")
    if not player:
        raise RuntimeError("afplay not found; announcements play on macOS only.")
    if horn:
        subprocess.run([player, str(make_horn())], check=False)
    subprocess.run([player, "-r", SPEED, "-q", "1", str(path)], check=False)
