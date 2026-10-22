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
    return [(a, b) for a, b, _ in lyric_text(yt, video_id)]


def lyric_text(yt, video_id: str) -> list[tuple[float, float, str]]:
    """(start, end, words) of each sung line. Older cache entries have no words ("")."""
    with _lock:
        cache = _load()
        if video_id in cache:
            return [(x[0], x[1], x[2] if len(x) > 2 else "") for x in cache[video_id]]
    lines: list[tuple[float, float, str]] = []
    try:
        browse = yt.get_watch_playlist(videoId=video_id, limit=1).get("lyrics")
        lyr = yt.get_lyrics(browse, timestamps=True) if browse else None
        if lyr and lyr.get("hasTimestamps"):
            lines = [(l.start_time / 1000, l.end_time / 1000, l.text.strip())
                     for l in lyr["lyrics"] if l.text.strip()]
    except Exception:
        return []  # not cached, so it's tried again next time
    with _lock:
        cache = _load()
        cache[video_id] = lines
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache))
    return lines


def chorus(lines: list[tuple[float, float, str]]) -> tuple[list[float], str]:
    """When the hook comes round: start times of the most repeated sung line, and its words.
    That's the line a crowd knows, so it's where the DJ drops the music for a sing-along."""
    count: dict[str, list[float]] = {}
    words: dict[str, str] = {}
    for start, _, text in lines:
        key = "".join(c for c in text.lower() if c.isalnum())
        if len(key) >= 6:
            count.setdefault(key, []).append(start)
            words.setdefault(key, text)
    if not count:
        return [], ""
    key = max(count, key=lambda k: (len(count[k]), -count[k][0]))
    if len(count[key]) < 2:
        return [], ""
    return count[key], words[key]


def best_play(song_seconds: int, start: int, lines: list, lo: int, hi: int, fade: int) -> tuple[int, float]:
    """(seconds to play from `start`, crossfade seconds). The fade starts as the singer finishes
    a line and is over before the next line begins, so a mix never cuts into the singing. The
    best spot is the end of the hook (the chorus line, when the next line moves on), else the
    longest pause in the vocals."""
    left = song_seconds - start
    if left <= lo:
        return max(30, left), fade
    words = [(x[2] if len(x) > 2 else "") for x in lines]
    hook = _key(chorus([(x[0], x[1], w) for x, w in zip(lines, words)])[1])
    ends = [(a[1], b[0] - a[1], _key(wa) == hook != _key(wb)) for a, b, wa, wb
            in zip(lines, lines[1:], words, words[1:])]
    if lines:
        ends.append((lines[-1][1], song_seconds - lines[-1][1], False))  # after the last line
    best, best_score = None, -1.0
    for end, gap, after_hook in ends:
        f = min(fade, max(1.5, gap - 0.2))  # finish the fade inside the pause
        play = end - start + f
        if lo <= play <= min(hi, left) and gap >= 0.8:
            score = min(gap, 8) + (3 if gap >= fade else 0) + (5 if hook and after_hook and gap >= 1.5 else 0) + play / 100
            if score > best_score:
                best, best_score = (round(play), f), score
    if best is not None:
        return best
    return round(min(max(left * 0.55, lo), hi, left)), fade


def _key(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())
