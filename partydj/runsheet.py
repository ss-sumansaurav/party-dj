"""Timed run-sheet: when each song starts and where each announcement goes."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .announcer import Writer
from .planner import BIRTHDAY_BLOCK_MINUTES, SetPlan

INTRO_SECONDS = 45  # birthday intro cue before the birthday song


@dataclass
class Cue:
    at: int        # seconds from party start
    kind: str      # opening, phase name, birthday_intro, cake, shoutout, closing, vibe
    text: str
    before: int    # index of the slot this cue comes before (len(slots) = after the last one)


def timeline(plan: SetPlan, cfg) -> None:
    """Fill slot.start, pinning the birthday song to the configured time."""
    t = 0
    for i, slot in enumerate(plan.slots):
        if i == plan.birthday_index:
            t = cfg.birthday_offset_minutes * 60 + INTRO_SECONDS
        elif plan.birthday_index is not None and i == plan.birthday_index + 1:
            t = (cfg.birthday_offset_minutes + BIRTHDAY_BLOCK_MINUTES) * 60
        slot.start = t
        t += slot.song.length


def cues(plan: SetPlan, cfg) -> list[Cue]:
    w = Writer(cfg.birthday_person_name, cfg.host_name, seed=f"{cfg.party_date}-lines")
    slots, b = plan.slots, plan.birthday_index
    out = [Cue(0, "opening", w.line("opening"), 0)]
    every = cfg.announcement_interval_songs
    since = 0
    for i in range(1, len(slots)):
        since += 1
        near_birthday = b is not None and i in (b - 1, b, b + 1)
        if since >= every and not near_birthday and i != len(slots) - 1:
            ph = slots[i].phase
            out.append(Cue(slots[i].start, ph, w.line(ph, slots[i].song.title), i))
            since = 0
    if b is not None:
        bday = slots[b]
        out.append(Cue(bday.start - INTRO_SECONDS, "birthday_intro", w.line("birthday_intro"), b))
        after = bday.start + bday.song.length
        out.append(Cue(after, "cake", w.line("cake"), b + 1))
        out.append(Cue(after + 90, "shoutout", w.line("shoutout"), b + 1))
        since = 0
    last = slots[-1]
    out.append(Cue(last.start, "closing", w.line("closing"), len(slots) - 1))
    out.sort(key=lambda c: (c.at, c.before))
    return out


def vibe_checks(cfg) -> list[int]:
    step = cfg.vibe_check_minutes * 60
    return list(range(step, cfg.duration_minutes * 60, step))


def _clock(cfg, seconds: int) -> str:
    return (cfg.start + dt.timedelta(seconds=seconds)).strftime("%I:%M %p").lstrip("0")


def _mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def to_markdown(plan: SetPlan, cue_list: list[Cue], cfg, playlist_url: str | None = None) -> str:
    songs = plan.songs
    hindi = sum(not s.is_english for s in songs)
    total = plan.slots[-1].start + plan.slots[-1].song.length
    lines = [
        f"# Run-sheet: {cfg.birthday_person_name}'s birthday party",
        "",
        f"{cfg.start:%A %d %B %Y}, {_clock(cfg, 0)} to {_clock(cfg, cfg.duration_minutes * 60)}. "
        f"Host: {cfg.host_name}.",
        "",
        f"- **{len(songs)} songs**, about {total // 60} minutes of music",
        f"- **Language:** {hindi} Hindi/Punjabi ({hindi / len(songs):.0%}), "
        f"{len(songs) - hindi} English ({(len(songs) - hindi) / len(songs):.0%})",
        f"- **Announcements:** {len(cue_list)} cues; vibe check every {cfg.vibe_check_minutes} min",
    ]
    if playlist_url:
        lines.append(f"- **Playlist:** {playlist_url}")
    lines += ["", "Times are estimates from track lengths, except the birthday block, which starts on the clock.", ""]

    by_slot: dict[int, list[Cue]] = {}
    for c in cue_list:
        by_slot.setdefault(c.before, []).append(c)
    checks = vibe_checks(cfg)
    phase = None
    n = 0
    for i, slot in enumerate(plan.slots):
        if slot.phase != phase:
            phase = slot.phase
            ph = next(p for p in plan.phases if p.name == phase)
            lines += ["", f"## {phase} ({_clock(cfg, ph.start * 60)} to {_clock(cfg, ph.end * 60)})", "",
                      "| Time | # | Track | Artist | Lang | Energy |", "| --- | --- | --- | --- | --- | --- |"]
        while checks and checks[0] <= slot.start:
            lines.append(f"| {_clock(cfg, checks.pop(0))} | 📊 | *Vibe check: score 1 to 5* | | | |")
        for c in by_slot.get(i, []):
            lines.append(f"| {_clock(cfg, c.at)} | 🎤 | *{c.text}* | | | |")
        n += 1
        s = slot.song
        title = f"[{s.title}]({s.url})" if s.url else s.title
        req = " (request)" if s.requested else ""
        lines.append(f"| {_clock(cfg, slot.start)} | {n} | {title}{req} | {s.artist} | {s.lang} | {'●' * s.energy} |")
    for c in by_slot.get(len(plan.slots), []):
        lines.append(f"| {_clock(cfg, c.at)} | 🎤 | *{c.text}* | | | |")
    return "\n".join(lines) + "\n"
