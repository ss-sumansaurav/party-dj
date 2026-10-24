"""Song pool: load songs.yaml, apply blocks and requests, filter explicit titles."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

MIN_ENERGY = 2  # songs below this energy aren't played
DEFAULT_SECONDS = 270  # used until YouTube Music tells us the real length

# Titles containing these words are skipped when no explicit flag is available.
_EXPLICIT_WORDS = re.compile(
    r"\b(explicit|nsfw|sexy|fuck\w*|shit\w*|bitch\w*|nigga\w*|motherf\w*)\b", re.I
)


def norm(text: str) -> str:
    """Lowercase, strip accents, punctuation and bracketed bits, for matching."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[\(\[].*?[\)\]]", " ", text.lower())
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


@dataclass
class Song:
    title: str
    artist: str
    lang: str          # hi, pa or en
    era: str
    energy: int        # 1 mellow .. 5 floor-filler
    requested: bool = False
    video_id: str | None = None
    seconds: int | None = None
    explicit: bool = False
    full: bool = False  # play the whole song (the birthday song)
    karaoke: bool = False  # everyone sings it: the DJ calls it and the words show on screen
    old: bool = False      # plays only while the "Old songs" button is on (or when requested)
    before: "Song | None" = None  # birthday song only: the Happy Birthday song that plays first

    # DJ mode plays only part of each song; set from config (song_play_min/max_seconds).
    play_cap = None
    crossfade = 0

    @property
    def key(self) -> str:
        return norm(self.title)

    @property
    def is_english(self) -> bool:
        return self.lang == "en"

    @property
    def lead_artist(self) -> str:
        return self.artist.split(",")[0].strip()

    @property
    def full_length(self) -> int:
        return self.seconds or DEFAULT_SECONDS

    @property
    def length(self) -> int:
        """How long this song takes in the set, after DJ trimming and the crossfade overlap."""
        n = self.full_length
        if self.play_cap:
            n = min(n, self.play_cap)
        return max(30, n - self.crossfade)

    @property
    def url(self) -> str | None:
        return f"https://music.youtube.com/watch?v={self.video_id}" if self.video_id else None

    def label(self) -> str:
        return f"{self.title} – {self.lead_artist}"


def _song(row) -> Song:
    title, artist, lang, era, energy = row[:5]
    tags = [str(t).lower() for t in row[5:]]
    return Song(str(title), str(artist), str(lang), str(era), int(energy),
                karaoke="karaoke" in tags, old="old" in tags)


def title_looks_explicit(title: str) -> bool:
    return bool(_EXPLICIT_WORDS.search(title))


def is_blocked(song: Song, blocked_artists: list[str], blocked_tracks: list[str]) -> bool:
    artists = norm(song.artist)
    if any(norm(a) and norm(a) in artists for a in blocked_artists):
        return True
    return any(norm(t) == song.key for t in blocked_tracks)


def parse_request(text: str) -> Song:
    """'Title - Artist' (artist optional). Unknown requests are treated as Hindi dance tracks."""
    parts = re.split(r"\s+[-–]\s+", text.strip(), maxsplit=1)
    title = parts[0]
    artist = parts[1] if len(parts) > 1 else ""
    return Song(title, artist, "hi", "?", 4, requested=True)


def load_pool(path: str | Path, cfg) -> tuple[list[Song], Song]:
    """Return (usable songs, birthday song) after blocks, requests and de-duplication."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    birthday = _song(raw["birthday_song"])
    birthday.full = True
    if raw.get("happy_birthday_song"):
        birthday.before = _song(raw["happy_birthday_song"])
        birthday.before.full = True
    songs: dict[str, Song] = {}
    for row in raw.get("songs") or []:
        s = _song(row)
        songs.setdefault(s.key, s)  # no repeats even if the file lists a song twice

    for text in cfg.requested_tracks:
        req = parse_request(text)
        if req.key in songs:
            songs[req.key].requested = True
        else:
            songs[req.key] = req

    usable = [
        s for s in songs.values()
        if s.key != birthday.key
        and not is_blocked(s, cfg.blocked_artists, cfg.blocked_tracks)
        and not title_looks_explicit(s.title)
        and (s.energy >= MIN_ENERGY or s.requested)  # 1-dot songs are too slow for this party
    ]
    return usable, birthday
