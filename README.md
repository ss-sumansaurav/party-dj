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
3. **Check the config:** edit `config.yaml`, then run `python dj.py check-config`.

## Sign in to YouTube Music

This uses ytmusicapi's browser-header sign-in: you copy request headers from your own
signed-in browser, and they're saved to `browser.json` on your Mac. Git ignores that file,
and the app sets it to be readable by you only. Treat it like a password.

1. Open Chrome or Firefox, go to <https://music.youtube.com> and sign in.
2. Open developer tools (Cmd+Option+I) and go to the **Network** tab.
3. In YouTube Music, click **Library** (or scroll) so new requests appear.
4. In the filter box type `browse`, click a request named `browse?...` whose method is **POST**.
5. Copy its **request headers**:
   - Chrome: Headers tab, scroll to *Request Headers*, select all of it from `accept: */*`
     down to the end, and copy.
   - Firefox: right-click the request, *Copy Value*, *Copy Request Headers*.
6. In the Terminal, in the `party-dj` folder, run:
   ```bash
   ytmusicapi browser --file browser.json
   ```
   paste the headers, press Enter, then **Ctrl-D**.
7. Confirm it worked: `python dj.py check-auth` should print your account name.

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

## Running

Test mode and the live run are being built next; this section will cover them.
