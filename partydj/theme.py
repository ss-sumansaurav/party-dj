"""The "Play songs like…" box: the host types the kind of songs they want, in their own words
("hit English dance songs from 2000 to 2010", "Bollywood dance songs", "Punjabi singers",
"Diljit", "90s retro", "Diwali songs"), and the DJ plays only songs that fit until it's cleared.

The words are read for languages, decades, energy, singers and themes. Songs on the list that
fit come first; when the list has few, the DJ also brings in tracks from a matching YouTube
Music playlist (nothing is downloaded).
"""
from __future__ import annotations

import re

from .songs import Song, norm

DECADES = ("60s", "70s", "80s", "90s", "2000s", "2010s", "2020s")
_LANG_WORDS = {
    "en": ("english", "hollywood", "western", "international", "american", "british", "pop"),
    "intl": ("spanish", "latin", "latino", "reggaeton", "salsa", "french", "korean", "kpop", "k pop",
             "international", "foreign", "other language"),
    "hi": ("hindi", "bollywood", "bolly", "filmi", "movie", "movies", "film"),
    "pa": ("punjabi", "bhangra", "panjabi"),
}
_UP = ("dance", "dancing", "party", "club", "banger", "bangers", "floor", "upbeat", "peppy", "jump")
_TOP = ("crescendo", "high energy", "on fire", "hardest", "biggest bangers", "full power", "peak")
_SLOW = ("slow", "romantic", "chill", "soft", "calm", "mellow", "sad", "love songs", "unplugged")
_OLD = ("old", "retro", "classic", "classics", "evergreen", "golden")
_COMMON = {"singh", "kaur", "khan", "kumar", "sharma", "music", "band", "dance", "party", "songs", "song",
           "hits", "best", "king", "queen", "boys", "girls", "love", "sound", "beat", "beats", "rock", "star",
           "with", "from", "some", "more", "only", "play", "hindi", "punjabi", "english", "diwali", "remix",
           "club", "jazz", "aamir", "ranveer", "hrithik"}
_WORD_DECADES = {"sixties": "60s", "seventies": "70s", "eighties": "80s", "nineties": "90s"}


def _has(text: str, words) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def _decade(year: int) -> str:
    d = year // 10 * 10
    return f"{d % 100:02d}s" if d < 2000 else f"{d}s"


def parse(text: str, artists: list[str] = ()) -> dict:
    """What the words ask for: languages, decades, an energy range, singers and tags."""
    t = " " + " ".join(norm(text).split()) + " "
    spec: dict = {"text": " ".join(text.split()), "langs": set(), "eras": set(), "lo": 1, "hi": 5,
                  "artists": [], "tags": set()}
    for lang, words in _LANG_WORDS.items():
        if _has(t, words):
            if lang == "intl":
                spec["langs"].add("en")
                if not _has(t, ("english", "hollywood", "american", "british")):
                    spec["tags"].add("intl")
            else:
                spec["langs"].add(lang)
    # Years: "2000 to 2010", "2000-2010", "from 2015", "90s", "nineties"
    years = [int(y) for y in re.findall(r"\b(19[5-9]\d|20[0-2]\d)\b", t)]
    if len(years) >= 2:
        a, b = min(years[:2]), max(years[:2])
        if b % 10 == 0 and b > a:
            b -= 1  # "2000 to 2010" means the 2000s
        spec["eras"] = {_decade(y) for y in range(a, b + 1)}
    elif years:
        y = years[0]
        spec["eras"] = {d for d in DECADES if DECADES.index(d) >= DECADES.index(_decade(y))} \
            if re.search(rf"\b(from|after|since)\s+{y}\b", t) else {_decade(y)}
    for m in re.findall(r"\b(?:19)?([6-9]0)s\b|\b(20[0-2]0)s\b", t):
        spec["eras"].add(f"{m[0]}s" if m[0] else f"{m[1]}s")
    for w, d in _WORD_DECADES.items():
        if w in t:
            spec["eras"].add(d)
    if _has(t, _OLD) and not spec["eras"]:
        spec["eras"] = {"60s", "70s", "80s", "90s"}
    if _has(t, _TOP):
        spec["lo"] = 5
    elif _has(t, _UP):
        spec["lo"] = 4
    if _has(t, _SLOW):
        spec["lo"], spec["hi"] = 1, 3
    if _has(t, ("diwali", "deepawali", "deepavali", "festive", "festival", "lakshmi", "ram")):
        spec["tags"].add("diwali")
    # Singers: any artist on the list whose name is in the words ("Diljit", "Honey Singh")
    seen, loose = set(), []
    for full in artists:
        for name in [a.strip() for a in full.split(",")]:
            n = norm(name)
            if n in seen:
                continue
            seen.add(n)
            w = n.split()
            phrases = [" ".join(w[i:j]) for i in range(len(w)) for j in range(i + 2, len(w) + 1)]
            if any(f" {p} " in t for p in phrases):
                spec["artists"].append(n)
            elif any(f" {x} " in t for x in w if len(x) >= 4 and x not in _COMMON):
                loose.append(n)
    # "Neha Kakkar" means her, not every Neha or Kakkar; "Diljit" on its own means Diljit.
    words_used = " ".join(spec["artists"]).split()
    spec["artists"] += [n for n in loose if not set(n.split()) & set(words_used)]
    spec["understood"] = bool(spec["langs"] or spec["eras"] or spec["artists"] or spec["tags"]
                              or spec["lo"] > 1 or spec["hi"] < 5)
    return spec


def fits(spec: dict, s: Song) -> bool:
    if spec["artists"]:
        if not any(a in norm(s.artist) for a in spec["artists"]):
            return False
    elif spec["langs"] and s.lang not in spec["langs"]:
        return False
    if spec["eras"] and s.era not in spec["eras"] and s.era not in ("new", "?"):
        return False
    if not spec["lo"] <= s.energy <= spec["hi"]:
        return False
    if "intl" in spec["tags"] and "intl" not in s.tags:
        return False
    if "diwali" in spec["tags"] and "diwali" not in s.tags:
        return False
    return True


def describe(spec: dict) -> str:
    """The DJ's reading of the words, so the host can see what it understood."""
    bits = []
    if spec["artists"]:
        bits.append(" / ".join(a.title() for a in spec["artists"][:3]))
    names = {"hi": "Hindi", "pa": "Punjabi", "en": "English"}
    if spec["langs"] and not spec["artists"]:
        bits.append(" + ".join(names[x] for x in sorted(spec["langs"])))
    if "intl" in spec["tags"]:
        bits.append("international")
    if "diwali" in spec["tags"]:
        bits.append("Diwali")
    if spec["eras"]:
        bits.append(", ".join(d for d in DECADES if d in spec["eras"]))
    if spec["lo"] == 5:
        bits.append("5★ only")
    elif spec["lo"] == 4:
        bits.append("dance (4–5★)")
    elif spec["hi"] <= 3:
        bits.append("slower (up to 3★)")
    return " · ".join(bits) or "anything that matches the words"
