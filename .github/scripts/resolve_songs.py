"""Look up every song in songs.yaml on YouTube Music once, at build time, so the phone app
starts in seconds instead of searching for hundreds of songs on first launch.
Writes the resolver's cache (song -> video id) to the path given."""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from partydj import resolver  # noqa: E402
from partydj.songs import _song  # noqa: E402
from ytmusicapi import YTMusic  # noqa: E402

out = Path(sys.argv[1])
raw = yaml.safe_load(Path("songs.yaml").read_text(encoding="utf-8"))
rows = list(raw.get("songs") or [])
for k in ("diwali_first_song", "diwali_song", "happy_birthday_song", "birthday_song"):
    if raw.get(k):
        rows.append(raw[k])
songs = [_song(r) for r in rows]
resolver.CACHE = out
missing = resolver.resolve_all(YTMusic(), songs, progress=lambda m: print(m, flush=True))
print(f"Looked up {len(songs)} songs; {len(missing)} not found; cache has {len(json.loads(out.read_text()))} entries")
