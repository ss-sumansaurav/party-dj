"""Short English DJ lines and text-to-speech."""
from __future__ import annotations

import random
import re
import shutil
import subprocess
from pathlib import Path

MAX_WORDS = 32  # about 15 seconds of speech

LINES = {
    "opening": [
        "Yo Mumbai, what's good! Welcome to {name}'s birthday party. I'm your DJ tonight, and {host} said no holding back. So let's get this party started!",
    ],
    "Warm-up": [
        "Alright alright, we're easing into it. Got a real classic for you. Sing it loud, this is {next}!",
        "Feeling that throwback? Yeah, me too. Here's a timeless one, {next}!",
        "Smooth start, good people, great vibes. Keep it rolling with {next}!",
        "Old school, gold school. Turn it up, this is {next}!",
    ],
    "Build": [
        "Ooh, I see you moving! The floor is warming up. Let's keep it going, {next}!",
        "Now we're talking! Eighties, nineties, all the hits. Get up, it's {next}!",
        "{host}, get your crew on the floor. This one's {next}. Let's go!",
        "The energy's building and I love it! Here comes {next}!",
    ],
    "Peak": [
        "Okay, this is it! Hands up, all the way up! It's {next}!",
        "Turn it up! Louder! This one goes hard. Let's go, {next}!",
        "{name}, this one's for you, birthday legend! Everybody, {next}!",
        "Dhol's coming in, you know what time it is! Balle balle, {next}!",
    ],
    "Peak 2": [
        "You thought we were done? Not even close! Let's go, {next}!",
        "This party is on another level. Don't stop now, it's {next}!",
        "Let me hear you, Mumbai! Everybody on the floor for {next}!",
        "No slowing down tonight! Bring it back, {next}!",
    ],
    "Wind-down": [
        "Alright, let's slow it down. Grab someone special. This is {next}.",
        "Take a breath, sing along with me. Here's {next}.",
        "Easy now, feel this one. It's {next}.",
    ],
    "vibe_up": [
        "Hold up, hold up. I need more energy than that! Wake up, Mumbai, it's {next}!",
        "Come on, I know you've got more! Let's turn it up, it's {next}!",
    ],
    "request": [
        "We got a request coming in, and it's a good one! This is {next}!",
        "Somebody's got great taste! By request, here's {next}!",
    ],
    "hype": [
        "Make some noise for {name}! Louder! Let me hear you!",
        "Everybody, hands up! Give it up for {host}, what a party!",
        "Mumbai, are you with me? Let me hear you scream!",
    ],
    "birthday_intro": [
        "Alright everybody, can I get your attention? Lights down, cake out. It's {name}'s moment. Make some noise!",
    ],
    "cake": [
        "Three, two, one! Cut that cake, {name}! Everybody together, happy birthday!",
    ],
    "shoutout": [
        "Happy birthday {name}, you legend! Here's to an amazing year. And a huge shoutout to {host} for this incredible party!",
    ],
    "closing": [
        "Mumbai, you were amazing tonight! Happy birthday once again, {name}. {host}, thank you for this party. Good night, everybody!",
    ],
}

# How hyped each kind of line sounds (1 calm .. 5 full hype). Song lines use the song's energy.
KIND_ENERGY = {"opening": 4, "Warm-up": 3, "Build": 4, "Peak": 5, "Peak 2": 5, "Wind-down": 2,
               "vibe_up": 5, "request": 4, "hype": 5, "birthday_intro": 4, "cake": 5,
               "shoutout": 4, "closing": 3}


# Hindi and Hinglish lines, spoken by the Hindi voice. English words stay in English letters.
LINES_HI = {
    "Warm-up": [
        "क्या बात है, क्या माहौल है! अब आ रहा है एक evergreen गाना, {next}!",
        "पुरानी यादें, नए vibes. ज़ोर से गाइए, ये है {next}!",
        "Mumbai, आवाज़ ऊँची करो! चलो, {next}!",
    ],
    "Build": [
        "अरे वाह, dance floor गरम हो रहा है! रुकना नहीं है, ये है {next}!",
        "{host} जी, सबको floor पे लाइए! आ गया {next}!",
        "Energy बढ़ रही है, मज़ा आ रहा है! चलो, {next}!",
    ],
    "Peak": [
        "हाथ ऊपर, पूरे ऊपर! ये है {next}!",
        "{name}, ये गाना आपके लिए! सब लोग, {next}!",
        "ढोल बजेगा, सब नाचेंगे! बल्ले बल्ले, {next}!",
    ],
    "Peak 2": [
        "पार्टी अभी ख़त्म नहीं हुई, दोस्तों! Let's go, {next}!",
        "क्या बात है Mumbai! फिर से, सब floor पे, {next}!",
    ],
    "Wind-down": [
        "अब थोड़ा धीरे चलते हैं. किसी ख़ास के साथ, ये है {next}.",
        "आँखें बंद, दिल खोलो. ये है {next}.",
    ],
    "vibe_up": [
        "अरे, इतनी शांति क्यों? मुझे energy चाहिए! चलो, {next}!",
    ],
    "request": [
        "Request आई है, और क्या कमाल की choice है! ये है {next}!",
    ],
    "hype": [
        "{name} के लिए ज़ोरदार तालियाँ! और ज़ोर से!",
        "Mumbai, आवाज़ नहीं आई! और ज़ोर से!",
    ],
    "cake": [
        "तीन, दो, एक! केक काटो, {name}! सब मिलकर, happy birthday!",
    ],
    "shoutout": [
        "जन्मदिन मुबारक हो {name}! साल भर ख़ुशियाँ ही ख़ुशियाँ. और {host} जी, इस शानदार पार्टी के लिए thank you!",
    ],
}
HINDI_NAMES = {"Ketan": "केतन", "Poonam": "पूनम"}  # names as the Hindi voice should read them


class Writer:
    """Picks a line for each cue without repeating until a list is used up.
    About `hindi_share` of lines come out in Hindi or Hinglish, where one exists."""

    def __init__(self, name: str, host: str, seed: str, hindi_share: float = 0.0):
        self.name, self.host = name, host
        self.hindi_share = hindi_share
        self.rng = random.Random(seed)
        self.decks: dict[tuple[str, str], list[str]] = {}

    def line(self, kind: str, next_title: str = "") -> str:
        hindi = kind in LINES_HI and self.rng.random() < self.hindi_share
        source = LINES_HI if hindi else LINES
        deck = self.decks.get((kind, hindi))
        if not deck:
            deck = list(source[kind])
            self.rng.shuffle(deck)
            self.decks[(kind, hindi)] = deck
        name, host = (HINDI_NAMES.get(self.name, self.name), HINDI_NAMES.get(self.host, self.host)) if hindi \
            else (self.name, self.host)
        text = deck.pop().format(name=name, host=host, next=next_title)
        if len(text.split()) > MAX_WORDS:
            raise ValueError(f"Announcement too long for 15 seconds: {text}")
        return text


def is_hindi(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", text))


DJ_VOICE = "en-US-AndrewNeural"  # young American male voice; change in config.yaml (dj_voice)
HINDI_VOICE = "hi-IN-MadhurNeural"  # young Hindi male voice for Hindi and Hinglish lines
SAY_AS = {"Ketan": "Kaytun", "Poonam": "Poonum"}  # spelled the way the voice should say them
_warned = False

# Voice settings per energy level: speed, pitch, loudness.
PROSODY = {1: (-2, -3, 0), 2: (2, 0, 5), 3: (8, 3, 10), 4: (12, 6, 20), 5: (16, 10, 30)}


def sentences(text: str) -> list[str]:
    return [p for p in re.split(r"(?<=[.!?।])\s+", text.strip()) if p]


def prosody(sentence: str, i: int, n: int, energy: int) -> tuple[str, str, str]:
    """Modulate each sentence like a DJ: hyped lines climb towards the drop,
    calm lines settle, and exclamations get extra punch."""
    rate, pitch, vol = PROSODY[max(1, min(5, energy))]
    if energy >= 3:
        pitch += 2 * i            # build up through the line
        if i == n - 1 and n > 1:  # the drop: the song name, loud and quick
            rate += 4
            pitch += 3
            vol += 10
    else:
        pitch -= i                # soft, settling delivery
    if sentence.endswith("!"):
        pitch += 3
        vol += 5
    elif sentence.endswith("?"):
        pitch += 2
    return f"{rate:+d}%", f"{min(pitch, 14):+d}Hz", f"{min(vol, 50):+d}%"


def for_voice(text: str, voice: str) -> str:
    """Respell Indian names for non-Indian voices so they're said right."""
    if voice.startswith(("en-IN", "hi-IN")):
        return text
    for name, said in SAY_AS.items():
        text = re.sub(rf"\b{re.escape(name)}\b", said, text)
    return text


def _edge_tts(text: str, out: Path, voice: str, energy: int):
    import asyncio

    import edge_tts

    parts = sentences(for_voice(text, voice))

    async def go():
        audio = bytearray()
        for i, part in enumerate(parts):
            rate, pitch, volume = prosody(part, i, len(parts), energy)
            async for chunk in edge_tts.Communicate(part, voice, rate=rate, pitch=pitch, volume=volume).stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
        out.write_bytes(bytes(audio))

    asyncio.run(go())
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("edge-tts returned no audio")


def speak_to_file(text: str, path: Path, voice: str | None = None, energy: int = 3) -> Path:
    """Write speech audio in a young American DJ voice (edge-tts), with the delivery
    modulated to the energy (1 calm .. 5 full hype). Falls back to gTTS, then the Mac's `say`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out = path.with_suffix(".mp3")
        _edge_tts(text, out, voice or (HINDI_VOICE if is_hindi(text) else DJ_VOICE), energy)
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
        if is_hindi(text):
            gTTS(text, lang="hi").save(str(out))
        else:
            gTTS(for_voice(text, ""), lang="en", tld="com").save(str(out))
        return out
    except Exception as gtts_error:
        if shutil.which("say"):
            out = path.with_suffix(".aiff")
            want = "Lekha" if is_hindi(text) else "Alex"
            voice = ["-v", want] if _has_voice(want) else []
            subprocess.run(["say", *voice, "-r", "205", "-o", str(out), for_voice(text, "")], check=True)
            return out
        raise RuntimeError(f"Couldn't make speech audio: {gtts_error}") from gtts_error


def _has_voice(name: str) -> bool:
    try:
        voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    except OSError:
        return False
    return any(line.split()[0] == name for line in voices.splitlines() if line.strip())


SPEED = "1.0"  # the voice already speeds up with the energy


def play(path: Path):
    """Play an announcement through the Mac's current output (the party speaker)."""
    player = shutil.which("afplay")
    if not player:
        raise RuntimeError("afplay not found; announcements play on macOS only.")
    subprocess.run([player, "-r", SPEED, "-q", "1", str(path)], check=False)
