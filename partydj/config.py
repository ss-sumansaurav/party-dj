"""Load and validate config.yaml."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    party_date: dt.date
    start_time: dt.time
    duration_minutes: int
    birthday_person_name: str
    host_name: str
    birthday_block_time: dt.time
    hindi_ratio: float
    english_ratio: float
    announcement_interval_songs: int
    vibe_check_minutes: int
    blocked_artists: list[str] = field(default_factory=list)
    blocked_tracks: list[str] = field(default_factory=list)
    requested_tracks: list[str] = field(default_factory=list)
    dj_voice: str = "en-US-AndrewNeural"
    name_pronunciations: dict = field(default_factory=dict)
    song_play_seconds: int = 165
    crossfade_seconds: int = 6

    @property
    def start(self) -> dt.datetime:
        return dt.datetime.combine(self.party_date, self.start_time)

    @property
    def end(self) -> dt.datetime:
        return self.start + dt.timedelta(minutes=self.duration_minutes)

    @property
    def birthday_offset_minutes(self) -> int:
        """Minutes from the start of the party to the birthday block."""
        at = dt.datetime.combine(self.party_date, self.birthday_block_time)
        if at < self.start:  # e.g. midnight after a 9 PM start
            at += dt.timedelta(days=1)
        return int((at - self.start).total_seconds() // 60)

    @property
    def playlist_title(self) -> str:
        # ytmusic rejects "<" and ">" in titles
        return f"Birthday Party – {self.party_date:%d %b %Y}"


def _time(value, name: str) -> dt.time:
    try:
        return dt.datetime.strptime(str(value), "%H:%M").time()
    except ValueError as e:
        raise ConfigError(f"{name} must look like 21:00, got {value!r}") from e


def load_config(path: str | Path = "config.yaml") -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    required = [
        "party_date", "duration_minutes", "birthday_person_name", "host_name",
        "language_ratio", "announcement_interval_songs",
    ]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ConfigError(f"config.yaml is missing: {', '.join(missing)}")

    party_date = raw["party_date"]
    if isinstance(party_date, str):
        party_date = dt.date.fromisoformat(party_date)

    ratio = raw["language_ratio"] or {}
    hindi = float(ratio.get("hindi", 0.7))
    english = float(ratio.get("english", 1 - hindi))
    if hindi < 0.7:
        raise ConfigError("language_ratio.hindi must be at least 0.7")
    if abs(hindi + english - 1) > 0.01:
        raise ConfigError("language_ratio.hindi + english must add up to 1")

    cfg = Config(
        party_date=party_date,
        start_time=_time(raw.get("start_time", "21:00"), "start_time"),
        duration_minutes=int(raw["duration_minutes"]),
        birthday_person_name=str(raw["birthday_person_name"]).strip(),
        host_name=str(raw["host_name"]).strip(),
        birthday_block_time=_time(raw.get("birthday_block_time", "00:00"), "birthday_block_time"),
        hindi_ratio=hindi,
        english_ratio=english,
        announcement_interval_songs=int(raw["announcement_interval_songs"]),
        vibe_check_minutes=int(raw.get("vibe_check_minutes", 15)),
        blocked_artists=[str(x) for x in raw.get("blocked_artists") or []],
        blocked_tracks=[str(x) for x in raw.get("blocked_tracks") or []],
        requested_tracks=[str(x) for x in raw.get("requested_tracks") or []],
        dj_voice=str(raw.get("dj_voice") or "en-US-AndrewNeural"),
        name_pronunciations={str(k): str(v) for k, v in (raw.get("name_pronunciations") or {}).items()},
        song_play_seconds=int(raw.get("song_play_seconds", 165)),
        crossfade_seconds=int(raw.get("crossfade_seconds", 6)),
    )

    if not 30 <= cfg.duration_minutes <= 600:
        raise ConfigError("duration_minutes should be between 30 and 600")
    if not 3 <= cfg.announcement_interval_songs <= 4:
        raise ConfigError("announcement_interval_songs should be 3 or 4")
    if not 60 <= cfg.song_play_seconds <= 600:
        raise ConfigError("song_play_seconds should be between 60 and 600")
    if not 0 <= cfg.crossfade_seconds <= 15:
        raise ConfigError("crossfade_seconds should be between 0 and 15")
    if not cfg.birthday_person_name or not cfg.host_name:
        raise ConfigError("birthday_person_name and host_name can't be empty")
    if not 0 < cfg.birthday_offset_minutes < cfg.duration_minutes:
        raise ConfigError("birthday_block_time must fall inside the party")
    return cfg
