"""Where to mix out of each song, like a DJ: somewhere between the shortest and longest play
time, at the best moment for the next song to come in.

The best moment is a pause in the vocals: the end of a sung line with the longest gap before
the next one (YouTube Music's timed lyrics give us those). Without timed lyrics, the mix
comes a little past the middle of the song. Nothing is downloaded or analysed: only the
lyric timings are read.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

CACHE = Path(".cache/cuts.json")
_lock = threading.Lock()
_cache: dict[str, list] | None = None


def _load() -> dict[str, list]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE.read_text())
        except (OSError, ValueError):
            _cache = {}
    return _cache


def lyric_lines(yt, video_id: str) -> list[tuple[float, float]]:
    """(start, end) seconds of each sung line, or [] when the song has no timed lyrics."""
    with _lock:
        cache = _load()
        if video_id in cache:
            return [tuple(x) for x in cache[video_id]]
    lines: list[tuple[float, float]] = []
    try:
        browse = yt.get_watch_playlist(videoId=video_id, limit=1).get("lyrics")
        lyr = yt.get_lyrics(browse, timestamps=True) if browse else None
        if lyr and lyr.get("hasTimestamps"):
            lines = [(l.start_time / 1000, l.end_time / 1000) for l in lyr["lyrics"] if l.text.strip()]
    except Exception:
        return []  # not cached, so it's tried again next time
    with _lock:
        cache = _load()
        cache[video_id] = lines
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache))
    return lines


def best_play(song_seconds: int, start: int, lines: list[tuple[float, float]],
              lo: int, hi: int, fade: int) -> int:
    """Seconds to play from `start`. The crossfade begins `fade` seconds before the end."""
    left = song_seconds - start
    if left <= lo:
        return max(30, left)
    best, best_score = None, -1.0
    ends = [(a[1], b[0] - a[1]) for a, b in zip(lines, lines[1:])]
    if lines:
        ends.append((lines[-1][1], song_seconds - lines[-1][1]))  # after the last line
    for end, gap in ends:
        play = end - start + fade  # the fade starts as the singer finishes the line
        if lo <= play <= min(hi, left) and gap >= 1.0:
            # Longer pauses mix better; a pause that covers the whole fade is ideal.
            score = min(gap, 8) + (3 if gap >= fade else 0) + play / 100
            if score > best_score:
                best, best_score = play, score
    if best is not None:
        return round(best)
    return round(min(max(left * 0.55, lo), hi, left))
