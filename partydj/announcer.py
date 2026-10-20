"""Short Hinglish DJ lines and text-to-speech."""
from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

MAX_WORDS = 32  # about 15 seconds of speech

LINES = {
    "opening": [
        "Namaste doston, aur welcome to {name} ki birthday party! {host} ne aaj ki raat full set kar di hai, toh shuru karte hain classic style mein!",
    ],
    "Warm-up": [
        "Kya mehfil jami hai! Gaate rahiye, kyunki ab aa raha hai {next}.",
        "Purane gaane, nayi yaadein. Next up, {next}. Sab saath mein gaana!",
        "Volume thoda badhao doston, aa raha hai {next}!",
        "Yeh gaana sunke college ke din yaad aa jayenge. Next, {next}!",
    ],
    "Build": [
        "Dance floor garam ho raha hai! Chaliye, {next} ke saath thoda aur move karte hain.",
        "Eighties aur nineties wali feeling aa rahi hai? Next up, {next}. Jootey taiyaar!",
        "{host}, sabko floor pe laao, kyunki {next} aa raha hai!",
        "Ab sirf taali nahi, thoda thumka bhi! Next up, {next}.",
    ],
    "Peak": [
        "Ab koi baitha nahi rahega! Full power mein, {next}!",
        "Haath upar, Mumbai! Aa raha hai {next}!",
        "{name}, yeh wala aapke liye! {next}, full volume!",
        "Dhol bajne wala hai, ready ho jao! Next up, {next}.",
    ],
    "Peak 2": [
        "Party abhi khatam nahi hui, doston! Next up, {next}!",
        "Energy kam nahi honi chahiye! Balle balle, aa raha hai {next}!",
        "Raat abhi jawaan hai doston! Full on, {next}!",
        "Sab ek saath, floor pe! Next up, {next}.",
    ],
    "Wind-down": [
        "Raat thodi dheemi ho rahi hai, par yaadein abhi baaki hain. Suniye {next}.",
        "Thoda aaram se, dil se. Agla gaana, {next}.",
        "Apne partner ka haath pakdiye, aa raha hai {next}.",
    ],
    "vibe_up": [
        "Lagta hai thoda josh chahiye! Toh lijiye, energy upar, {next}!",
        "Chalo chalo, sab uth jao! Ab aa raha hai {next}!",
    ],
    "birthday_intro": [
        "Attention please! Lights thodi dim karo aur cake le aao. Yeh pal hai {name} ka!",
    ],
    "cake": [
        "Teen, do, ek! Cake kaatiye {name}, aur sab milke bolo, happy birthday!",
    ],
    "shoutout": [
        "{name}, happy birthday! Dher saari khushiyaan aur pyaar. Aur thank you {host}, is shaandaar party ke liye!",
    ],
    "closing": [
        "Doston, aaj ki raat yaadgaar rahi. {name}, happy birthday once again, aur {host}, thank you! Good night, Mumbai!",
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
