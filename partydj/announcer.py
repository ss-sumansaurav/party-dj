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
        "Yo NaAhAr, what's good! Welcome to {name}'s birthday party. I'm your DJ tonight, and I was told no holding back. So let's get this party started!",
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
        "Everybody, get your crew on the floor. This one's {next}. Let's go!",
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
        "Let me hear you, Nahar Folks! Everybody on the floor for {next}!",
        "No slowing down tonight! Bring it back, {next}!",
    ],
    "Wind-down": [
        "Alright, let's slow it down. Grab someone special. This is {next}.",
        "Take a breath, sing along with me. Here's {next}.",
        "Easy now, feel this one. It's {next}.",
    ],
    "vibe_up": [
        "Hold up, hold up. I need more energy than that! Wake up, Nahar Folks, it's {next}!",
        "Come on, I know you've got more! Let's turn it up, it's {next}!",
    ],
    "request": [
        "We got a request coming in, and it's a good one! This is {next}!",
        "Somebody's got great taste! By request, here's {next}!",
    ],
    "guest_request": [
        "This one's a request from {who}! Great choice. Let's go, {next}!",
        "Shoutout to {who}, you asked for it, you got it! It's {next}!",
        "Request coming up for {who}! Everybody, this is {next}!",
    ],
    "dance_floor": [
        "Hey, I see a lot of people sitting down! Come on, everybody on the dance floor. It's {next}!",
        "Dance floor's looking lonely! Grab a friend and get up here. This is {next}!",
        "No more standing around! Everybody to the dance floor, right now. It's {next}!",
    ],
    "karaoke": [
        "Karaoke time! Everybody, the words are on the screen. Sing it loud, this is {next}!",
        "Nahar Folks, it's your turn to be the singer! Everybody sing along to {next}!",
    ],
    "dedication": [
        "This one goes out to {to}, with love from {who}! It's {next}!",
        "Special dedication! From {who}, for {to}. Here's {next}!",
    ],
    "cake_10": [
        "Ten minutes to cake time for {name}! Get your phones ready and keep that energy up!",
        "Heads up, Nahar Folks! Cake time for {name} in ten minutes!",
    ],
    "cake_5": [
        "Five minutes to go! Everybody start making your way over, it's almost cake time for {name}!",
    ],
    "sing_along": [
        "Nahar guys and gals, this one's yours! Everybody sing!",
        "I can't hear you! Sing it with me, everybody!",
        "Hands up and sing it loud! Let me hear you!",
    ],
    "hype": [
        "Make some noise for {name}! Louder! Let me hear you!",
        "Everybody, hands up! Give it up for our hosts, what a party!",
        "Nahar guys and gals, are you with me? Let me hear you scream!",
    ],
    "birthday_intro": [
        "Alright everybody, can I get your attention? Lights down, cake out. It's {name}'s moment. Make some noise!",
    ],
    "cake": [
        "Three, two, one! Cut that cake, {name}! Everybody together, happy birthday!",
    ],
    "shoutout": [
        "Happy birthday {name}, you legend! Here's to an amazing year. And a huge shoutout to our hosts for this incredible party!",
    ],
    "closing": [
        "NAHAR guys and gals, you were amazing tonight! Happy birthday once again, {name}, and thank you to our hosts for this party. Good night, everybody!",
    ],
}

# How hyped each kind of line sounds (1 calm .. 5 full hype). Song lines use the song's energy.
KIND_ENERGY = {"opening": 4, "Warm-up": 3, "Build": 4, "Peak": 5, "Peak 2": 5, "Wind-down": 2,
               "vibe_up": 5, "request": 4, "hype": 5, "birthday_intro": 4, "cake": 5,
               "shoutout": 4, "closing": 3, "guest_request": 4, "dance_floor": 5, "sing_along": 5,
               "dedication": 4, "karaoke": 5, "cake_10": 4, "cake_5": 5, "wish": 3}


# Hindi and Hinglish lines, spoken by the Hindi voice. English words stay in English letters.
LINES_HI = {
    "Warm-up": [
        "क्या बात है, क्या माहौल है! अब आ रहा है एक evergreen गाना, {next}!",
        "पुरानी यादें, नए vibes. ज़ोर से गाइए, ये है {next}!",
        "NAHAR WALO, आवाज़ ऊँची करो! चलो, {next}!",
    ],
    "Build": [
        "अरे वाह, dance floor गरम हो रहा है! रुकना नहीं है, ये है {next}!",
        "चलो, सब floor पे आइए! आ गया {next}!",
        "Energy बढ़ रही है, मज़ा आ रहा है! चलो, {next}!",
    ],
    "Peak": [
        "हाथ ऊपर, पूरे ऊपर! ये है {next}!",
        "{name}, ये गाना आपके लिए! सब लोग, {next}!",
        "ढोल बजेगा, सब नाचेंगे! बल्ले बल्ले, {next}!",
    ],
    "Peak 2": [
        "पार्टी अभी ख़त्म नहीं हुई, दोस्तों! Let's go, {next}!",
        "क्या बात है NAHAR WALO! फिर से, सब floor पे, {next}!",
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
    "guest_request": [
        "{who} की फ़रमाइश पर, ये है {next}! Let's go!",
        "ये गाना {who} के लिए, जिन्होंने request किया! चलो, {next}!",
    ],
    "dance_floor": [
        "अरे, सब बैठे क्यों हो? चलो dance floor पे! ये है {next}!",
        "Dance floor खाली क्यों है? सब लोग आ जाओ! चलो, {next}!",
    ],
    "karaoke": [
        "Karaoke time! सब लोग मिलकर गाओ, ये है {next}!",
    ],
    "dedication": [
        "ये गाना {to} के लिए, {who} की तरफ़ से, ढेर सारे प्यार के साथ! चलो, {next}!",
    ],
    "cake_10": [
        "दस मिनट में केक कटेगा! {name} के लिए तैयार हो जाओ!",
    ],
    "cake_5": [
        "बस पाँच मिनट! सब लोग पास आ जाओ, केक आने वाला है!",
    ],
    "birthday_intro": [
        "सब लोग ध्यान दीजिए! पास आ जाइए, {name} का केक कटने वाला है!",
    ],
    "opening": [
        "Hello everybody! {name} की birthday party में आप सबका स्वागत है. मैं हूँ आपका DJ. चलो, party शुरू करते हैं!",
    ],
    "closing": [
        "आप सब कमाल के थे! {name}, एक बार फिर happy birthday. Good night, everybody!",
    ],
    "sing_along": [
        "सब मिलकर गाओ! ज़ोर से!",
        "NAHAR WALO, आवाज़ ऊँची करो, सब साथ में गाओ!",
    ],
    "hype": [
        "{name} के लिए ज़ोरदार तालियाँ! और ज़ोर से!",
        "NAHAR WALO, आवाज़ नहीं आई! और ज़ोर से!",
    ],
    "cake": [
        "तीन, दो, एक! केक काटो, {name}! सब मिलकर, happy birthday!",
    ],
    "shoutout": [
        "जन्मदिन मुबारक हो {name}! साल भर ख़ुशियाँ ही ख़ुशियाँ. और hosts को इस शानदार पार्टी के लिए thank you!",
    ],
}
HINDI_NAMES = {"Ketan": "केतन", "Poonam": "पूनम"}  # names as the Hindi voice should read them


class Writer:
    """Picks a line for each cue without repeating until a list is used up.
    About `hindi_share` of lines come out in Hindi or Hinglish, where one exists."""

    def __init__(self, name: str, host: str, seed: str, hindi_share: float = 0.0,
                 lines: dict | None = None, lines_hi: dict | None = None, extra: dict | None = None):
        self.name, self.host = name, host
        self.hindi_share = hindi_share
        self.lines, self.lines_hi = lines or LINES, lines_hi if lines_hi is not None else LINES_HI
        self.extra = extra or {}  # more {words} the lines can use, e.g. a Diwali party's {hosts}
        self.rng = random.Random(seed)
        self.decks: dict[tuple[str, str], list[str]] = {}

    def line(self, kind: str, next_title: str = "", who: str = "", **extra: str) -> str:
        hindi = kind in self.lines_hi and self.rng.random() < self.hindi_share
        source = self.lines_hi if hindi else self.lines
        deck = self.decks.get((kind, hindi))
        if not deck:
            deck = list(source[kind])
            self.rng.shuffle(deck)
            self.decks[(kind, hindi)] = deck
        name, host = (HINDI_NAMES.get(self.name, self.name), HINDI_NAMES.get(self.host, self.host)) if hindi \
            else (self.name, self.host)
        text = deck.pop().format(name=name, host=host, next=next_title, who=who, **{**self.extra, **extra})
        if len(text.split()) > MAX_WORDS:
            raise ValueError(f"Announcement too long for 15 seconds: {text}")
        return text


def is_hindi(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", text))


DJ_VOICE = "en-IN-PrabhatNeural"  # Indian English male voice, like a desi club DJ; change in config.yaml (dj_voice)
HINDI_VOICE = "hi-IN-MadhurNeural"  # young Hindi male voice for Hindi and Hinglish lines
SAY_AS = {"Ketan": "Kaytun", "Poonam": "Poonum"}  # spelled the way the voice should say them
_warned = False

BACKUP_VOICE = "en-US-AndrewNeural"   # used if the chosen voice isn't available

# Voice settings per energy level: speed, pitch, loudness. Kept gentle: big pitch and speed
# jumps are what make a synthetic voice sound robotic.
PROSODY = {1: (-4, -1, 0), 2: (0, 0, 0), 3: (4, 0, 5), 4: (6, 1, 10), 5: (8, 2, 15)}


def sentences(text: str) -> list[str]:
    return [p for p in re.split(r"(?<=[.!?।])\s+", text.strip()) if p]


def prosody(text: str, energy: int) -> tuple[str, str, str]:
    """A little faster and brighter for hype lines, a little slower for calm ones. The whole
    line is spoken in one go, so the voice keeps its own natural rise and fall."""
    rate, pitch, vol = PROSODY[max(1, min(5, energy))]
    if text.rstrip().endswith("!") and energy >= 3:
        vol += 5
    return f"{rate:+d}%", f"{pitch:+d}Hz", f"{vol:+d}%"


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

    said = " ".join(sentences(for_voice(text, voice)))
    rate, pitch, volume = prosody(said, energy)

    async def go(v: str):
        audio = bytearray()
        async for chunk in edge_tts.Communicate(said, v, rate=rate, pitch=pitch, volume=volume).stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return bytes(audio)

    audio = b""
    try:
        audio = asyncio.run(go(voice))
    except Exception:
        if voice in (BACKUP_VOICE, HINDI_VOICE):
            raise
    if len(audio) < 1000 and voice not in (BACKUP_VOICE, HINDI_VOICE):
        audio = asyncio.run(go(BACKUP_VOICE))
    if len(audio) < 1000:
        raise RuntimeError("edge-tts returned no audio")
    out.write_bytes(audio)


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
