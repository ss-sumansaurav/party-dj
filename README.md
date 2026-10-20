# Party DJ

A playlist-driven "AI DJ" for a home birthday party: it builds a private YouTube Music
playlist and a timed run-sheet, and speaks short, high-energy English announcements in a Gen Z DJ voice through the speaker
while the host plays the playlist in the YouTube Music app or website.

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

## Party night (live run)

**One-time Chrome setting:** play YouTube Music in Google Chrome, and in Chrome's menu bar
turn on **View > Developer > Allow JavaScript from Apple Events**. This lets the DJ pause the
music for each announcement and start the next song itself. The first time, macOS asks
whether Terminal may control Google Chrome: click **OK**.

Connect the Mac to the speaker, then in Terminal:

```bash
cd ~/party-dj
source .venv/bin/activate
python dj.py --check-auth
python dj.py --live
```

1. It makes the night's announcements and opens a **control page** in your browser
   (http://localhost:8765) with five big vibe buttons and messages for you.
2. Open music.youtube.com in a Chrome tab (shuffle off). Don't press play.
3. Press Enter in Terminal. The DJ says hello, then starts song 1 of the playlist.
4. When a song with an announcement comes on, the DJ **pauses it, plays the announcement
   (air horn, then the voice), then lets the song play**.
5. **Birthday block:** at `birthday_block_time` it pauses the music, plays the birthday
   intro and starts the birthday song. The cake cue and shout-out follow it.
6. **Vibe check** every 15 minutes: Terminal beeps and the page asks for a score. Tap 1 to 5.
   Two scores of 1–2 in a row: the DJ plays a livelier song next, then returns to the plan.
   Two scores of 4–5: it holds the energy. Scores go to `mood_log.csv` on the Mac and
   nowhere else. No camera or microphone is used.
7. **Blocks and requests:** edit `blocked_artists`, `blocked_tracks` or `requested_tracks`
   in `config.yaml` at any time. Within a minute, blocked songs are skipped and a request
   plays next (it's added to the end of the playlist if it wasn't there).
8. **🎤 Say something now** on the page pauses the music for an announcement straight away.

If Chrome can't be controlled, the DJ says what to fix; type `s` to carry on without it.
Announcements then play over the music and the control page tells you what to click.

Stop any time with Ctrl-C. You can rehearse on any day: it runs the same way, with the
birthday block the same distance from when you start.
