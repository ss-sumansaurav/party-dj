"""Short English DJ lines and text-to-speech."""
from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

MAX_WORDS = 32  # about 15 seconds of speech

LINES = {
    "opening": [
        "Good evening everyone, and welcome to {name}'s birthday party! {host} has set up a fantastic night, so let's kick things off with the classics!",
    ],
    "Warm-up": [
        "What a lovely crowd tonight! Keep singing along, because up next is {next}.",
        "Old songs, new memories. Coming up, {next}. Everybody sing along!",
        "Turn it up a little, friends, here comes {next}!",
        "This one takes us straight back to college days. Next up, {next}!",
    ],
    "Build": [
        "The dance floor is warming up! Let's keep moving with {next}.",
        "Feeling those eighties and nineties vibes? Next up, {next}. Dancing shoes on!",
        "{host}, get everyone on the floor, because {next} is coming up!",
        "Time to clap and move! Next up, {next}.",
    ],
    "Peak": [
        "Nobody stays seated now! Full power, it's {next}!",
        "Hands up, Mumbai! Here comes {next}!",
        "{name}, this one's for you! {next}, full volume!",
        "Get ready, the dhol is about to drop! Next up, {next}.",
    ],
    "Peak 2": [
        "The party is far from over, friends! Next up, {next}!",
        "Keep that energy going! Here comes {next}!",
        "The night is still young! Full on, {next}!",
        "Everybody on the dance floor! Next up, {next}.",
    ],
    "Wind-down": [
        "The night is slowing down, but the memories are just beginning. Here's {next}.",
        "Nice and easy now, straight from the heart. Next up, {next}.",
        "Grab your partner's hand, here comes {next}.",
    ],
    "vibe_up": [
        "Looks like we need a little more energy! Turning it up with {next}!",
        "Come on everyone, on your feet! Here comes {next}!",
    ],
    "birthday_intro": [
        "Attention please! Dim the lights and bring out the cake. This moment belongs to {name}!",
    ],
    "cake": [
        "Three, two, one! Cut the cake, {name}, and everyone together, happy birthday!",
    ],
    "shoutout": [
        "Happy birthday, {name}! Wishing you lots of joy and love. And thank you, {host}, for this wonderful party!",
    ],
    "closing": [
        "Friends, what a memorable night. Happy birthday once again, {name}, and thank you, {host}! Good night, Mumbai!",
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
            subprocess.run(["say", *voice, "-o", str(out), text], check=True)
            return out
        raise RuntimeError(f"Couldn't make speech audio: {gtts_error}") from gtts_error


def _has_voice(name: str) -> bool:
    try:
        voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    except OSError:
        return False
    return any(line.split()[0] == name for line in voices.splitlines() if line.strip())


def play(path: Path):
    """Play an audio file through the Mac's current output (the party speaker)."""
    player = shutil.which("afplay")
    if not player:
        raise RuntimeError("afplay not found; announcements play on macOS only.")
    subprocess.run([player, str(path)], check=False)
