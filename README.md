# Party DJ

An "AI DJ" for a home birthday party. One command plans the night, makes a private YouTube
Music playlist and a timed run-sheet, then mixes the party in a browser page: each song plays
for a couple of minutes, songs crossfade smoothly into each other, and a Gen Z DJ voice talks
over the intros with the music turned down.

It never downloads or re-hosts audio, and never types your Google password anywhere.

## Setup (Mac)

1. **Python 3.9+.** Check with `python3 --version`. If missing: `brew install python`.
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
4. In the filter box type `browse`. Right-click any row named `browse?...` and choose
   **Copy > Copy as cURL** (on a Mac it may say *Copy as cURL (bash)*).
5. Nothing to paste: the next step reads it from your clipboard.
6. In the Terminal, in the `party-dj` folder, run:
   ```bash
   python dj.py --sign-in
   ```
   This reads the headers straight from your clipboard, saves them to `browser.json`
   without printing them, and checks they work by printing your account name.

The headers stay valid as long as that browser session stays signed in (usually weeks).
If `python dj.py --check-auth` starts failing, repeat steps 1 to 6. Re-check the day of the party.

## Config (`config.yaml`)

| Key | Meaning |
| --- | --- |
| `party_date`, `start_time`, `duration_minutes` | When the party runs (default 9 PM, 300 min) |
| `birthday_person_name`, `host_name` | Used in announcements |
| `birthday_block_time` | When the Happy Birthday song and cake-cutting cue happen |
| `language_ratio` | Hindi share must be at least 0.7 |
| `announcement_interval_songs` | 3 or 4 |
| `vibe_check_minutes` | How often to ask for a 1 to 5 vibe score |
| `song_play_seconds` | How long each song plays before the DJ mixes into the next (default 165; the birthday song plays in full) |
| `crossfade_seconds` | Length of the smooth blend between songs (default 6) |
| `dj_voice` | The DJ's voice (a young male neural voice by default; needs internet when announcements are made) |
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

It takes a few minutes, plus about half an hour if you listen to every song, and:

1. Looks up every song on YouTube Music (search only; results are cached in `.cache/`).
2. Plans the night into Warm-up, Build, Peak, the Birthday block, Peak 2 and Wind-down,
   scaled to `duration_minutes`, with the birthday song pinned to `birthday_block_time`.
3. Asks before creating the **private** playlist (or before replacing the tracks of an
   existing one with the same name). Say no and nothing is created.
4. Writes `run_sheet.md` with times, tracks, announcement cues and vibe checks, and prints it.
5. Makes two sample announcements in `announcements/`, and asks before playing them.
6. Asks before playing 30 seconds of **every** song (about half a minute per song). It opens
   a local browser page: click **Play previews**, use **Skip** to move on early, and press
   Enter in Terminal when it's done. Songs whose label blocks playback outside YouTube are
   listed in the report with a link; they still play normally in YouTube Music.
7. Prints a report: playlist link, files created, and any song it couldn't find.

Run it again after changing `config.yaml` or `songs.yaml`; the same date gives the same plan.

## Party night: one command

Connect the Mac to the speaker, then in Terminal:

```bash
cd ~/party-dj
source .venv/bin/activate
python dj.py
```

1. If the YouTube Music sign-in has expired, it walks you through signing in again.
2. It plans the set, checks the playlist (it asks before creating one) and opens the
   **DJ page** in your browser (http://localhost:8765).
3. Click **▶ START THE PARTY**. The DJ says hello and the music starts. Leave the page open.
4. **DJ mixing:** each song plays for about 2¾ minutes (`song_play_seconds`), skipping a few
   seconds of long intros, then blends into the next song over `crossfade_seconds`.
5. **Announcements** every few songs, spoken over the start of a song with the music turned
   down, in an upbeat Indian English voice so Ketan's and Poonam's names sound right.
6. **Pick the vibe:** Auto follows the plan for the time of night. Chill, Groove, Dance,
   Bangers or On fire switch the music to that energy from the next song, until you pick
   Auto again.
7. **Birthday block:** at `birthday_block_time` the DJ blends straight into the birthday
   intro and plays the birthday song in full, then the cake cue and the shout-out.
8. **Vibe check** every 15 minutes: the page asks for a score from 1 to 5. Two scores of 1–2
   in a row lift the next song one energy level; two of 4–5 hold the energy. Scores go to
   `mood_log.csv` on the Mac and nowhere else. No camera is used, and the microphone is only
   used when you press 🎙 Speak (see below).
9. **Buttons:** ⏹ Stop music (fades out; press again to play), ⏭ Next song, 🎤 Hype the crowd, 🚫 Block this song, 🚫 Block this artist,
   and a box to request a song ("Song name - Artist"). Or press **🎙 Speak** and say the song
   name: the music dips while it listens, then the request is added. This uses Chrome's speech
   recognition, which sends that short clip to Google to turn it into text; the first time,
   Chrome asks to allow the microphone. Requests play next. The **Up next** panel on the right
   shows what plays after the current song. Edits to
   `blocked_*` and `requested_tracks` in `config.yaml` are also picked up within a minute.

Stop with Ctrl-C in Terminal. You can rehearse on any day: it runs the same way, with the
birthday block the same distance from when you click START. (`python dj.py --live` does the
same thing as `python dj.py`.)
