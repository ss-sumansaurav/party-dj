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
        "Ladies and gentlemen, make some noise! Welcome to {name}'s birthday bash! {host} has cooked up one massive night, so let's go, let's go, let's go!",
    ],
    "Warm-up": [
        "Ohhh, I hear you singing out there! Louder, Mumbai! Up next, the legend, {next}!",
        "Golden oldies, golden people! Everybody sing with me, here comes {next}!",
        "Volume up, hands up, voices up! It's {next}!",
        "Throwback time, baby! Take a trip down memory lane with {next}!",
    ],
    "Build": [
        "The floor is heating up! Are you ready? I said, are you ready? Here comes {next}!",
        "Eighties and nineties in the house! Dancing shoes on, it's {next}!",
        "{host}, grab everybody and hit that floor! {next}, let's go!",
        "Clap your hands, move those feet! Disco fever is here with {next}!",
    ],
    "Peak": [
        "Nobody sits down now! Full power, full volume, it's {next}!",
        "Hands in the air, Mumbai! Make some noise for {next}!",
        "{name}, this one is all for you! Turn it up, it's {next}!",
        "Get ready, the dhol is about to drop! Balle balle, here comes {next}!",
    ],
    "Peak 2": [
        "Did you think we were done? No way! The party just got bigger with {next}!",
        "Keep that fire burning! Jump with me, it's {next}!",
        "The night is young and so are we! Full on, {next}!",
        "Everybody on the dance floor, right now! Here comes {next}!",
    ],
    "Wind-down": [
        "What a night, what a crowd! Slow it down and sway with me to {next}.",
        "Grab someone you love, hold them close, here comes {next}.",
        "From the heart, for all of you. Sing it together, it's {next}!",
    ],
    "vibe_up": [
        "Oh, I think we need more energy! Get up, get up, get up! It's {next}!",
        "Come on, Mumbai, I can't hear you! Let's go, here comes {next}!",
    ],
    "birthday_intro": [
        "Attention, attention! Lights down, cake out! It's the moment we've all been waiting for. Everybody, make some noise for {name}!",
    ],
    "cake": [
        "Three, two, one! Cut that cake, {name}! Everybody together, happy birthday!",
    ],
    "shoutout": [
        "Happy birthday, {name}! You are a superstar! A huge round of applause, and big love to {host} for this amazing party!",
    ],
    "closing": [
        "What a night, Mumbai! You were incredible! Happy birthday once again, {name}, and thank you, {host}! Good night, and party on!",
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


def speak_to_file(text: str, path: Path) -> Path:
    """Write speech audio. Uses gTTS (Indian English voice); falls back to the Mac's `say`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from gtts import gTTS

        out = path.with_suffix(".mp3")
        gTTS(text, lang="en", tld="co.in").save(str(out))
        return out
    except Exception as gtts_error:
        if shutil.which("say"):
            out = path.with_suffix(".aiff")
            voice = ["-v", "Rishi"] if _has_voice("Rishi") else []
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
