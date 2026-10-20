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
| `song_play_min_seconds`, `song_play_max_seconds` | Every song plays between these lengths (default 90 to 150 seconds); the DJ mixes out at a pause in the singing |
| `crossfade_seconds` | Length of the smooth blend between songs (default 6) |
| `dj_voice` | The DJ's voice (a young male neural voice by default; needs internet when announcements are made) |
| `hindi_voice`, `hindi_announcement_share` | Voice for the Hindi and Hinglish announcements, and how many of them (0.35 = about a third) |
| `name_pronunciations` | How the voice should say names (e.g. `Ketan: Kaytun`) |
| `blocked_artists`, `blocked_tracks`, `requested_tracks` | Edit any time, before or during the party |

## Songs (`songs.yaml`)

The pool the DJ picks from: title, artist, language (`hi`, `pa`, `en`), era and an energy
score from 1 (mellow) to 5 (floor-filler). Add or remove lines freely. The planner never
repeats a song, keeps English at or under the configured share, skips anything YouTube Music
flags as explicit (or whose title looks explicit), and drops blocked artists and tracks.
Every song on the list is energy 3 or more (Suman cut the slow ones). Songs with energy 1 (one dot) are never played, unless someone requests
one. The last block of songs is party bangers in the style Bollywood club DJs like DJ Akhil
Talreja and DJ Suketu are known for.

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

## Android phone app

The same DJ also runs as an Android app (`android/`). GitHub builds it on every push to
`main` (Actions > "Android app" > the `party-dj-apk` download). Install `party-dj.apk` on the
phone (allow "install unknown apps" when asked), open **Ketan's Party DJ**, wait while it finds
the songs, then tap **▶ START THE PARTY**. Connect the phone to the speaker by Bluetooth or cable.

- Everything on the DJ page works: vibe buttons, requests with 🎙 Speak, Stop, Up next,
  blocks, the songs page and the crowd camera. Announcements need the internet.
- Guest requests by QR code work for guests on the same Wi-Fi as the phone (the public link
  is Mac only).
- The app finds songs without signing in. It doesn't create or change the YouTube Music
  playlist; make that from the Mac with `python dj.py --test`.
- Keep the app open with the phone on charge. The screen stays on by itself; leaving the
  app pauses the music. The back button asks before ending the party.

## Songs page: see, add or remove songs

```bash
python dj.py --songs
```

This opens a page listing every song picked for the party, with a search box.

- **Add a song:** type the song name and singer, pick the language and energy, then click Add.
  It checks that YouTube Music has the song first.
- **Remove a song:** click Remove next to it.

Changes are saved in `songs.yaml`. During the party, the DJ page has a **🎵 See, add or remove
party songs** link that opens the same list in a new tab, so the music keeps playing. There,
it also shows what's playing, what's next and what's already played. An added song joins the
next part of the night that suits its energy, and a removed song won't play.

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
4. **DJ mixing:** each song plays for 90 to 150 seconds. The DJ picks the mix point at a pause
   in the singing (from YouTube Music's timed lyrics), skipping a few
   seconds of long intros, then blends into the next song over `crossfade_seconds`.
   Now and then it mixes like a club DJ instead: when the energy climbs, a trance-style
   build-up (a rising sweep over the old song, then a deep boom as the new one drops in);
   between two bangers, a quick vinyl scratch and a cut. The effects are made by the program
   itself (no recorded sounds) and play at the DJ voice volume. YouTube's player can't be
   filtered, chopped or looped from a web page, so the Armin van Buuren and Fred again..
   touches come through build-ups, drops, scratches and sing-along moments rather than
   remixing the songs themselves.
5. **Announcements** every few songs, spoken over the start of a song with the music turned
   down, in a young American DJ voice. Its speed, pitch and loudness follow the energy: calm
   and smooth for slow songs, building up and punchy for the big ones. If a name sounds off,
   change its spelling under `name_pronunciations` in `config.yaml`. About a third of the
   announcements come out in Hindi or Hinglish in a Hindi voice (`hindi_announcement_share`).
6. **Pick the vibe:** Auto follows the plan for the time of night. Chill, Groove, Dance,
   Bangers or On fire switch the music to that energy from the next song, until you pick
   Auto again.
7. **Birthday block:** at `birthday_block_time` the DJ blends straight into the birthday
   intro and plays the birthday song, then the cake cue and the shout-out.
8. **Vibe check** every 15 minutes: the page asks for a score from 1 to 5. Two scores of 1–2
   in a row lift the next song one energy level; two of 4–5 hold the energy. Scores go to
   `mood_log.csv` on the Mac and nowhere else. The microphone is only used when you press
   🎙 Speak (see below).
   **📷 Crowd camera (optional):** press *Turn camera on* on the DJ page and point the laptop at
   the dance floor. It measures how much the room is moving (Quiet, Swaying, Grooving, Dancing,
   Going wild) and sends that as the vibe score every 2 minutes instead of asking you, so a
   quiet floor gets livelier songs. It only works out a movement number from tiny grey frames
   inside the page: no video or photos are saved or sent anywhere, and no faces are looked at.
   The Mac's green camera light shows guests it's on. Press *Turn camera off* to stop.
9. **Buttons:** ⏹ Stop music (fades out; press again to play), ⏭ Next song, 🎤 Hype the crowd, 🚫 Block this song, 🚫 Block this artist,
   and a box to request a song ("Song name - Artist"). Or press **🎙 Speak** and say the song
   name: the music dips while it listens, then the request is added. This uses Chrome's speech
   recognition, which sends that short clip to Google to turn it into text; the first time,
   Chrome asks to allow the microphone. Requests play next. The **Up next** panel on the right
   shows what plays after the current song. Edits to
   `blocked_*` and `requested_tracks` in `config.yaml` are also picked up within a minute.

10. **Guest requests by QR code:** the DJ page shows a QR code. Guests scan it, type their name
    and a song, and the DJ plays it next and says who asked for it. The song most people asked
    for plays first; on a tie, whoever asked first. "+ Me too" adds a vote. The QR code is a
    public link (a free Cloudflare tunnel, set up by itself the first time), so it works on
    mobile data or any Wi-Fi. Only the request page is behind it; the DJ controls stay on this
    device. When you stop the DJ the link closes and no more requests get through. If the link
    can't open, the QR code falls back to the home Wi-Fi address. The first time, the Mac may
    ask whether Python can accept incoming connections: click **Allow**.
    A request starts within a few seconds, blending out of the current song, unless a
    requested song (or the birthday song) is playing: then it plays right after. Every request
    is added to the YouTube Music playlist, with who asked for it in the playlist's
    description, and saved in `requests.csv`.
11. **🎚 Sound** (under the request queue): sliders for the music volume, the DJ voice volume, and how far the music dips
    under the voice. Bass and treble can't be changed from the page (YouTube's player doesn't
    allow it): use the speaker's own controls.
13. **Dance-floor call-out:** when the crowd camera (or your vibe scores) says people aren't
    dancing, the DJ calls everyone to the dance floor before the next song, at most once
    every 20 minutes.
14. **Sing-along:** when the vibe score is 5 (On fire, from you or the camera), the DJ waits for
    the song's hook (the line that repeats most in the timed lyrics), shouts "Everybody sing!",
    drops the music right down for about 8 seconds so the room sings it, then brings it back.
    The hook's words show on the DJ page. If the current song is nearly over it happens on the
    next one; at most once every 15 minutes.

Stop with Ctrl-C in Terminal. You can rehearse on any day: it runs the same way, with the
birthday block the same distance from when you click START. (`python dj.py --live` does the
same thing as `python dj.py`.)
