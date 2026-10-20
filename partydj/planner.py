"""Turn the song pool into an ordered, timed set that follows the party's phases."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .songs import Song

# Which energy tiers each phase draws from, and which eras it leans on.
PHASE_RULES = {
    "Warm-up":   {"energies": (1, 2, 3), "eras": ("60s", "70s", "80s"), "ramp": "up"},
    "Build":     {"energies": (3, 4),    "eras": ("80s", "90s"),        "ramp": "up"},
    "Peak":      {"energies": (4, 5),    "eras": ("90s", "2000s", "2010s", "2020s"), "ramp": None},
    "Peak 2":    {"energies": (4, 5),    "eras": ("80s", "90s", "2000s", "2010s", "2020s"), "ramp": None},
    "Wind-down": {"energies": (3, 4),    "eras": ("60s", "70s", "90s", "2000s"), "ramp": "down"},
}
BIRTHDAY_BLOCK_MINUTES = 10  # intro cue, birthday song, cake cue, shout-out


@dataclass
class Phase:
    name: str
    start: int  # minutes from party start
    end: int


@dataclass
class Slot:
    song: Song
    phase: str
    start: int = 0  # seconds from party start, filled by timeline()


@dataclass
class SetPlan:
    phases: list[Phase]
    slots: list[Slot] = field(default_factory=list)
    birthday_index: int | None = None  # index into slots of the birthday song
    reserve: list[Song] = field(default_factory=list)  # extra songs added after the timed set

    @property
    def songs(self) -> list[Song]:
        return [s.song for s in self.slots]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def phases_for(duration: int, birthday_at: int) -> list[Phase]:
    """Scale the 3-hour template to any length, with the birthday block where the config puts it."""
    warm = _clamp(round(duration * 0.15), 20, 45)
    wind = _clamp(round(duration * 0.15), 20, 45)
    peak = _clamp(round((birthday_at - warm) * 0.35), 15, 45)
    out = [Phase("Warm-up", 0, warm)]
    if birthday_at - peak > warm:
        out.append(Phase("Build", warm, birthday_at - peak))
    out.append(Phase("Peak", out[-1].end, birthday_at))
    out.append(Phase("Birthday", birthday_at, birthday_at + BIRTHDAY_BLOCK_MINUTES))
    after = birthday_at + BIRTHDAY_BLOCK_MINUTES
    if duration - after > wind + 15:
        out.append(Phase("Peak 2", after, duration - wind))
        out.append(Phase("Wind-down", duration - wind, duration))
    else:
        out.append(Phase("Wind-down", after, duration))
    return out


class Picker:
    """Chooses songs one at a time, keeping the language share and avoiding repeats."""

    def __init__(self, pool: list[Song], english_ratio: float, seed: str):
        self.left = list(pool)
        self.english_ratio = english_ratio
        self.rng = random.Random(seed)
        self.used = 0
        self.english = 0
        self.last_artist = ""

    def english_allowed(self) -> bool:
        return (self.english + 1) / (self.used + 1) <= self.english_ratio + 1e-9

    def score(self, s: Song, energies, eras) -> float:
        if s.energy not in energies:
            return -1
        sc = self.rng.random()
        sc += 3 if s.requested else 0
        sc += 0.6 if s.era in eras else 0
        sc += 0.4 if s.lang == "pa" and max(energies) >= 5 else 0
        sc -= 1 if s.lead_artist == self.last_artist else 0
        return sc

    def pick(self, energies, eras, max_len: int | None = None) -> Song | None:
        options = [s for s in self.left if not s.is_english or self.english_allowed()]
        if max_len is not None:
            options = [s for s in options if s.length <= max_len]
        scored = [(self.score(s, energies, eras), s) for s in options]
        scored = [x for x in scored if x[0] >= -0.99]
        if not scored:
            return None
        song = max(scored, key=lambda x: x[0])[1]
        self.take(song)
        return song

    def take(self, song: Song):
        self.left.remove(song)
        self.used += 1
        self.english += song.is_english
        self.last_artist = song.lead_artist


def build_plan(pool: list[Song], birthday_song: Song, cfg) -> SetPlan:
    playable = [s for s in pool if not s.explicit]
    phases = phases_for(cfg.duration_minutes, cfg.birthday_offset_minutes)
    plan = SetPlan(phases)
    picker = Picker(playable, cfg.english_ratio, seed=str(cfg.party_date))

    for ph in phases:
        if ph.name == "Birthday":
            plan.birthday_index = len(plan.slots)
            plan.slots.append(Slot(birthday_song, ph.name))
            continue
        rule = PHASE_RULES[ph.name]
        budget = (ph.end - ph.start) * 60
        chosen: list[Song] = []
        while budget > 60:
            # Near the end of a phase, prefer a song that fits, so the birthday block starts on time.
            song = picker.pick(rule["energies"], rule["eras"], max_len=budget + 60 if budget < 420 else None)
            if song is None:
                break
            chosen.append(song)
            budget -= song.length
        if rule["ramp"] == "up":
            chosen.sort(key=lambda s: s.energy)
        elif rule["ramp"] == "down":
            chosen.sort(key=lambda s: -s.energy)
        plan.slots += [Slot(s, ph.name) for s in chosen]
    # Everything else in the pool goes on the end of the playlist, liveliest first,
    # so it's there for requests, energy boosts or if the party runs late.
    plan.reserve = sorted(unused(plan, playable), key=lambda s: -s.energy)
    return plan


def unused(plan: SetPlan, pool: list[Song]) -> list[Song]:
    keys = {s.key for s in plan.songs}
    return [s for s in pool if s.key not in keys and not s.explicit]
