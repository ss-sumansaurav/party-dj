"""Find each song on YouTube Music (search only, no downloads) and cache the result."""
from __future__ import annotations

import difflib
import json
from pathlib import Path

from .songs import Song, norm

CACHE = Path(".cache/tracks.json")

# Versions we don't want unless the requested title asks for them.
_AVOID = ("remix", "cover", "karaoke", "instrumental", "lofi", "lo fi", "slowed", "reverb",
          "reprise", "unplugged", "mashup", "live", "8d", "female version", "sad version")


def _artists(result: dict) -> str:
    return norm(" ".join(a.get("name", "") for a in result.get("artists") or []))


def _score(song: Song, result: dict) -> float:
    want, got = song.key, norm(result.get("title", ""))
    if not got:
        return 0.0
    if any(w in got and w not in want for w in _AVOID):
        return 0.0
    title = 1.0 if want and want in got else difflib.SequenceMatcher(None, want, got).ratio()
    if title < 0.6:
        return 0.0
    leads = [norm(a).split(" ")[-1] for a in song.artist.split(",") if a.strip()]
    hay = _artists(result) + " " + got
    artist = 1.0 if not leads or any(l and l in hay for l in leads) else 0.0
    return title + 0.5 * artist


def _best(song: Song, results: list[dict]) -> dict | None:
    scored = [(_score(song, r), i, r) for i, r in enumerate(results) if r.get("videoId")]
    scored = [s for s in scored if s[0] >= 0.9]
    return max(scored, key=lambda s: (s[0], -s[1]))[2] if scored else None


def resolve_one(yt, song: Song) -> bool:
    """Fill video_id, seconds and explicit on `song`. Returns False if nothing matched."""
    query = f"{song.title} {song.artist}".strip()
    for kind in ("songs", "videos"):
        try:
            results = yt.search(query, filter=kind, limit=5)
        except Exception:
            results = []
        hit = _best(song, results)
        if hit:
            song.video_id = hit["videoId"]
            song.seconds = hit.get("duration_seconds")
            song.explicit = bool(hit.get("isExplicit"))
            return True
    return False


def resolve_all(yt, songs: list[Song], progress=print) -> list[Song]:
    """Resolve every song, using the cache when possible. Returns songs that weren't found."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    missing = []
    for i, song in enumerate(songs, 1):
        key = f"{song.key}|{norm(song.artist)}"
        hit = cache.get(key)
        if hit:
            song.video_id, song.seconds, song.explicit = hit["video_id"], hit["seconds"], hit["explicit"]
        else:  # misses aren't cached, so a later run tries again
            if resolve_one(yt, song):
                cache[key] = {"video_id": song.video_id, "seconds": song.seconds, "explicit": song.explicit}
            if i % 10 == 0:
                progress(f"  looked up {i}/{len(songs)}")
        if not song.video_id:
            missing.append(song)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1))
    return missing
