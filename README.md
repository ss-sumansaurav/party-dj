# Party DJ

A playlist-driven "AI DJ" for a home birthday party: it builds a private YouTube Music
playlist and a timed run-sheet, and speaks short Hinglish announcements through the speaker
while the host plays the playlist in the YouTube Music app or website.

It never downloads or re-hosts audio, and never types your Google password anywhere.

## Setup (Mac)

1. **Python 3.10+.** Check with `python3 --version`. If missing: `brew install python`.
2. **Get the code and install:**
   ```bash
   git clone <your repo url> party-dj && cd party-dj
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```
3. **Check the config:** edit `config.yaml`, then run `python dj.py --check-config`.

## Sign in to YouTube Music

This uses ytmusicapi's browser-header sign-in: you copy request headers from your own
signed-in browser, and they're saved to `browser.json` on your Mac. Git ignores that file,
and the app sets it to be readable by you only. Treat it like a password.

1. Open Chrome or Firefox, go to <https://music.youtube.com> and sign in.
2. Open developer tools (Cmd+Option+I) and go to the **Network** tab.
3. In YouTube Music, click **Library** (or scroll) so new requests appear.
4. In the filter box type `browse` and click any row named `browse?...`.
5. On the right, open **Headers** and scroll to **Request Headers**. Turn on the **Raw**
   switch next to that title, click inside the text, press Cmd+A, then Cmd+C.
   (Firefox: right-click the request, *Copy Value*, *Copy Request Headers*.)
6. In the Terminal, in the `party-dj` folder, run:
   ```bash
   pbpaste | ytmusicapi browser --file browser.json
   ```
   This reads the headers straight from your clipboard.
7. Confirm it worked: `python dj.py --check-auth` should print your account name.

The headers stay valid as long as that browser session stays signed in (usually weeks).
If `check-auth` starts failing, repeat steps 1 to 6. Re-check the day of the party.

## Config (`config.yaml`)

| Key | Meaning |
| --- | --- |
| `party_date`, `start_time`, `duration_minutes` | When the party runs (default 9 PM, 300 min) |
| `birthday_person_name`, `host_name` | Used in announcements |
| `birthday_block_time` | When the Happy Birthday song and cake-cutting cue happen |
| `language_ratio` | Hindi share must be at least 0.7 |
| `announcement_interval_songs` | 3 or 4 |
| `vibe_check_minutes` | How often to ask for a 1 to 5 vibe score |
| `blocked_artists`, `blocked_tracks`, `requested_tracks` | Edit any time, before or during the party |

## Songs (`songs.yaml`)

The pool the DJ picks from: title, artist, language (`hi`, `pa`, `en`), era and an energy
score from 1 (mellow) to 5 (floor-filler). Add or remove lines freely. The planner never
repeats a song, keeps English at or under the configured share, skips anything YouTube Music
flags as explicit (or whose title looks explicit), and drops blocked artists and tracks.

## Test mode (run this before the party)

```bash
python dj.py --test
```

It takes a few minutes and:

1. Looks up every song on YouTube Music (search only; results are cached in `.cache/`).
2. Plans the night into Warm-up, Build, Peak, the Birthday block, Peak 2 and Wind-down,
   scaled to `duration_minutes`, with the birthday song pinned to `birthday_block_time`.
3. Asks before creating the **private** playlist (or before replacing the tracks of an
   existing one with the same name). Say no and nothing is created.
4. Writes `run_sheet.md` with times, tracks, announcement cues and vibe checks, and prints it.
5. Makes two sample announcements in `announcements/`.
6. Asks before playing anything. If you say yes, it plays the two samples and opens two
   30-second song previews in your browser.
7. Prints a report: playlist link, files created, and any song it couldn't find.

Run it again after changing `config.yaml` or `songs.yaml`; the same date gives the same plan.

## Live run

Coming next: announcements on cue, the vibe-score prompt and `mood_log.csv`.
