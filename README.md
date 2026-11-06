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

## A new party: Diwali (or another birthday)

```
python dj.py --setup
```

It asks what kind of party (Birthday or Diwali), the host's and co-host's names (shown on screen;
the DJ never says them, so any party can use the same recordings), the city,
the date, start time, how long, and for Diwali the time of the **Diwali moment**. It saves
everything in its own file, like `party-diwali-anita.yaml`, and gives the party **its own
YouTube Music sign-in** (`browser-diwali-anita.json`), so your usual account is never used.
Sign in with that party's account when it asks (open YouTube Music in Chrome with *that*
account first). On party night:

```
python dj.py --config party-diwali-anita.yaml
```

At a Diwali party the DJ talks about Diwali and the hosts instead of a birthday, guests send
Diwali wishes from the QR page, and at the Diwali moment the countdown ends with "Three, two,
one! Happy Diwali!" and *Happy Diwali* then *Aayi Hai Diwali* play (change them with
`diwali_first_song` / `diwali_song` in `songs.yaml`). Everything else works the same.
The party runs on the laptop's own clock, so in Australia just use local times.

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
| `hindi_voice`, `hindi_announcement_share` | Voice for Hindi announcements, and how many of them (0 = English only) |
| `name_pronunciations` | How the voice should say names (e.g. `Ketan: Kaytun`) |
| `blocked_artists`, `blocked_tracks`, `requested_tracks` | Edit any time, before or during the party |

## Songs (`songs.yaml`)

The pool the DJ picks from: title, artist, language (`hi`, `pa`, `en`), era and an energy
score from 1 (mellow) to 5 (floor-filler). Add or remove lines freely. The planner never
repeats a song, keeps English at or under the configured share, skips anything YouTube Music
flags as explicit (or whose title looks explicit), and drops blocked artists and tracks.
About 460 songs: Hindi, Punjabi and English (Spanish and other international hits, tagged
`intl`, count as English). Every song on the list is energy 3 or more (Suman cut the slow ones). Songs with energy 1 (one dot) are never played, unless someone requests
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

When the app opens it asks for the party first: Birthday or Diwali, the host and co-host, the
city, the date and times (and the Diwali moment). It remembers the answers for next time. The
phone uses no YouTube account at all.

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
- **Change a song's stars (1–5) or language:** pick from the drop-downs on its row. The change
  is saved in `songs.yaml` and the DJ uses it straight away, for example for 🔥 Crescendo.

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
4. **DJ mixing:** each song plays for 40 to 60 seconds (`song_play_min_seconds` and `song_play_max_seconds`). The DJ picks the mix point at a pause
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
   down, in English, in an Indian English voice (en-IN-PrabhatNeural) with the lingo of a desi
   club DJ ("chalo", "haath upar", "balle balle"). Each line is said in one go. If a name
   sounds off, change its spelling under `name_pronunciations` in `config.yaml`. Hindi
   announcements are off (`hindi_announcement_share: 0`).
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
11. **🎚 Sound** (under the request queue). The **🔇 DJ voice off** button next to Stop music silences every announcement (music and effects keep going); press it again to bring the DJ back. Also: sliders for the music volume, the DJ voice volume, and how far the music dips
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

15. **Birthday at midnight:** the birthday block is always at 12 midnight, whatever time you
    click START. A countdown shows on the DJ page, the big screen and guests' phones, and the
    DJ calls it out at 10 and 5 minutes to go.
16. **Guests' phones** can also dedicate a request ("for Ketan"), send a birthday wish that the
    DJ reads out between songs (rude words are refused; press *Don't read* on the DJ page to
    drop one), and tap 👍 on the song that's playing. The DJ leans towards the singers and eras
    people like.
17. **📺 Big screen:** a full-screen view for a TV with now playing, the countdown, the QR code,
    the request queue and wishes. On the Mac press 📺 Big screen; a smart TV on the same Wi-Fi
    can open `http://<the Mac's Wi-Fi address>:8765/tv` (the QR code shows that address).
    Opened from the DJ page it has its own 🎵 Play full song and ⏭ Next song buttons. On the
    phone it opens over the DJ page: ✕ Back to the DJ (or the phone's back button) returns.
18. **Safety net:** if a song won't play or gets stuck, the DJ moves on. If the internet drops,
    the page says so and carries on by itself when it's back, without burning through songs.
    If the DJ program or the laptop restarts mid-party, run `python dj.py` again: it offers to
    pick up where it stopped, with no repeats and the same birthday time. Press
    ▶ CONTINUE THE PARTY on the page.
19. **📜 Party recap:** every song, who requested what, the crowd favourites and the wishes.
    Open it any time with the 📜 Party recap button; it's also saved as `party_recap.html` when
    you stop the DJ.

20. **Karaoke songs** (marked `karaoke` at the end of their line in `songs.yaml`, like Koi Kahe
    Kehta Rahe and Pretty Woman): the DJ asks everyone to sing, the song starts just before the
    chorus and the words show on the DJ page line by line.
21. **Themes:** Dark, Light or Party (top right of the DJ page); the page remembers your choice.
22. Mixes are plain smooth blends: the scratch and build-up effects are switched off.
23. **Requests play at least 150 seconds** (guest and karaoke too); other songs stay 40–60 s.
24. **🎵 Play full song:** tap it and the song that's on now plays to its very end.
25. **🎤 Karaoke:** plays one of the 10 karaoke songs straight away, from the top, with the
    words in big letters on the DJ page (and the next line under them). A request that was
    already lined up plays right after it.
26. **Midnight, to the second** (the Mac's own clock): a minute before, the DJ asks for lights
    down and cake out. "Three, two, one! Cut that cake!" ends at exactly 12:00:00, then
    *Happy Birthday To You* plays (up to 60 s), then Baar Baar Din Yeh Aaye from 1:00 for 90 s.
    Change them with `happy_birthday_song` in `songs.yaml` and `happy_birthday_play_seconds`,
    `birthday_song_start_seconds`, `birthday_song_play_seconds` in `config.yaml`.
27. **📻 Old songs:** the songs marked `old` in `songs.yaml` (the first 40, the 60s–90s classics)
    play only while this button is on. Tap it and they start straight away; tap again to go back
    to the party mix. A guest can still request one.
28. **Main buttons up top:** ⏹ Stop music, 🎵 Play full song and ⏭ Next song sit in one big
    row right under what's playing. Below them is **What to play** (Crescendo, languages, Old
    songs, Karaoke, the vibe), then requests, then everything else.
29. **Hindi / Punjabi / English & international buttons:** tap one (or two) and only songs in
    those languages play, until you tap it again. If a language runs out, the DJ carries on with
    the others. With none on, the DJ mixes all three (about 45% Hindi, 25% Punjabi, 30% English
    and international). Spanish and other international hits (tagged `intl`) count as English.
30. **🔥 Crescendo:** only 5-star songs, starting straight away, to take the party to its peak.
    Guest requests below 5 stars wait until you tap it off.
31. **🎯 Play songs like…:** type the kind of songs you want in your own words ("hit English
    dance songs from 2000 to 2010", "Dance songs from Bollywood movies", "Diljit", "90s
    Bollywood", "Diwali songs"), or tap a quick pick. The DJ reads the words for languages,
    years, energy and singers, plays the songs on the list that fit, and when there are fewer
    than 15 it adds tracks from a matching YouTube Music playlist. ✕ goes back to the normal mix.
32. **Stars and 👎 on the main screen:** tap 1–5 stars under the song that's playing to rate it.
    **👎 Remove song** takes it off the list, skips to the next song, and remembers: that singer
    isn't picked again and songs of the same language and decade come up less. The songs page
    lists them, with **Forget these** to undo.
33. **Diwali songs:** the songs tagged `diwali` (Jalte Diye, Kabhi Khushi Kabhie Gham, Ram
    Aayenge, Mere Ghar Ram Aaye Hain) play in the mix and with the 🪔 Diwali songs pick.
34. **Comes in on the beat:** songs skip the slow intro. With YouTube Music's timed lyrics the
    DJ starts a few seconds before the first chorus (when it comes within 20–110 seconds);
    otherwise about 15 seconds in. Requests start near the top (at most 15 seconds in).

Stop with Ctrl-C in Terminal. You can rehearse on any day: it runs the same way, with the
birthday block the same distance from when you click START. (`python dj.py --live` does the
same thing as `python dj.py`.)

## Recorded DJ voice (optional)

`python3 dj.py --config <your Diwali party file> --voice-pack` records the DJ's fixed Diwali lines
with ElevenLabs (free tier is enough; it asks for your `sk_…` API key and never prints it). The lines
name no one, so the recording works for any Diwali party. Lines already recorded in the same voice are
kept, so a re-run only records new or changed lines. Song names, requesters and wishes are still read
by the computer voice.

## Play without signing in

Signing in to YouTube Music is only needed to save the night's songs as a private playlist.
To skip it, type **S** when the DJ asks you to sign in, or start with:

```
python3 dj.py --config <your party file> --no-sign-in
```

Everything else (finding and playing songs, the DJ voice, requests, the big screen) works the same.
