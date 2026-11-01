"""What kind of party it is (a birthday or Diwali), and the words that change with it."""
from __future__ import annotations

from . import announcer

# The DJ's lines for a Diwali party. {hosts} is "Host and Co-host", {city} where the party is.
DIWALI_LINES = {
    "opening": [
        "Happy Diwali, everybody! Welcome to {hosts}'s Diwali party{in_city}. I'm your DJ tonight. Lights on, diyas on, let's get this party started!",
    ],
    "Warm-up": [
        "Easing into the festive vibe with a real classic. Sing it loud, this is {next}!",
        "Diyas are glowing and so is this one. Here's a timeless song, {next}!",
        "Good food, great people, Diwali vibes. Keep it rolling with {next}!",
        "Old school, gold school. Turn it up, this is {next}!",
    ],
    "Build": [
        "Ooh, I see you moving! The floor is warming up. Let's keep it going, {next}!",
        "Now we're talking! All the hits tonight. Get up, it's {next}!",
        "{host}, get everyone on the floor. This one's {next}. Let's go!",
        "The festive energy is building and I love it! Here comes {next}!",
    ],
    "Peak": [
        "Okay, this is it! Hands up, all the way up! It's {next}!",
        "Turn it up! Louder! This one goes hard. Let's go, {next}!",
        "Brighter than the fireworks! Everybody, {next}!",
        "Dhol's coming in, you know what time it is! Balle balle, {next}!",
    ],
    "Peak 2": [
        "You thought we were done? Not even close! Let's go, {next}!",
        "This Diwali party is on another level. Don't stop now, it's {next}!",
        "Let me hear you{city_shout}! Everybody on the floor for {next}!",
        "No slowing down tonight! Bring it back, {next}!",
    ],
    "Wind-down": [
        "Alright, let's slow it down. Grab someone special. This is {next}.",
        "Take a breath, sing along with me. Here's {next}.",
        "Easy now, feel this one. It's {next}.",
    ],
    "vibe_up": [
        "Hold up, hold up. I need more energy than that! It's Diwali, it's {next}!",
        "Come on, I know you've got more! Let's turn it up, it's {next}!",
    ],
    "request": [
        "We got a request coming in, and it's a good one! This is {next}!",
        "Somebody's got great taste! By request, here's {next}!",
    ],
    "guest_request": [
        "This one's a request from {who}! Great choice. Let's go, {next}!",
        "Shoutout to {who}, you asked for it, you got it! It's {next}!",
        "Request coming up for {who}! Everybody, this is {next}!",
    ],
    "dedication": [
        "This one goes out to {to}, with love from {who}! It's {next}!",
        "Special dedication! From {who}, for {to}. Here's {next}!",
    ],
    "dance_floor": [
        "Hey, I see a lot of people sitting down! Come on, everybody on the dance floor. It's {next}!",
        "Dance floor's looking lonely! Grab a friend and get up here. This is {next}!",
    ],
    "karaoke": [
        "Karaoke time! Everybody, the words are on the screen. Sing it loud, this is {next}!",
        "It's your turn to be the singer! Everybody sing along to {next}!",
    ],
    "sing_along": [
        "This one's yours! Everybody sing!",
        "I can't hear you! Sing it with me, everybody!",
    ],
    "hype": [
        "Make some noise for {hosts}! Louder! Let me hear you!",
        "Everybody, hands up! Happy Diwali, what a party!",
    ],
    "cake_10": [
        "Ten minutes to our Diwali moment! Find your family and friends and get ready!",
    ],
    "cake_5": [
        "Five minutes to go! Everybody gather round, it's almost our Diwali moment!",
    ],
    "birthday_intro": [
        "Alright everybody, can I get your attention? Gather round, diyas ready. It's our Diwali moment with {hosts}!",
    ],
    "cake": [
        "Three, two, one! Happy Diwali, everybody! Shubh Deepavali!",
    ],
    "shoutout": [
        "Happy Diwali{city_shout}! A huge thank you to {hosts} for bringing everyone together tonight!",
    ],
    "closing": [
        "You were amazing tonight! Happy Diwali once again. {hosts}, thank you for this party. Good night, everybody!",
    ],
}

DIWALI_LINES_HI = {
    "opening": [
        "Happy Diwali, everybody! {hosts_hi} की Diwali party{in_city_hi} में आप सबका स्वागत है. मैं हूँ आपका DJ. तो चलो, party शुरू करते हैं!",
    ],
    "Warm-up": [
        "शुभ दीपावली! अब आ रहा है एक evergreen गाना, {next}!",
        "दीये जल रहे हैं, माहौल बन रहा है. ज़ोर से गाइए, ये है {next}!",
    ],
    "Build": [
        "अरे वाह, dance floor गरम हो रहा है! रुकना नहीं है, ये है {next}!",
        "{host} जी, सबको floor पे लाइए! आ गया {next}!",
    ],
    "Peak": [
        "हाथ ऊपर, पूरे ऊपर! ये है {next}!",
        "ढोल बजेगा, सब नाचेंगे! बल्ले बल्ले, {next}!",
    ],
    "Peak 2": [
        "पार्टी अभी ख़त्म नहीं हुई, दोस्तों! Let's go, {next}!",
        "आज रुकना मना है! सब floor पे, ये है {next}!",
    ],
    "Wind-down": [
        "अब थोड़ा धीरे चलते हैं. ये है {next}.",
        "थोड़ा साँस ले लो, और साथ में गाओ. ये है {next}.",
    ],
    "vibe_up": [
        "अरे, इतनी शांति क्यों? आज Diwali है! चलो, {next}!",
    ],
    "request": [
        "Request आई है, और क्या कमाल की choice है! ये है {next}!",
    ],
    "guest_request": [
        "{who} की फ़रमाइश पर, ये है {next}! Let's go!",
        "ये गाना {who} के लिए, जिन्होंने request किया! चलो, {next}!",
    ],
    "dedication": [
        "ये गाना {to} के लिए, {who} की तरफ़ से, ढेर सारे प्यार के साथ! चलो, {next}!",
    ],
    "dance_floor": [
        "अरे, सब बैठे क्यों हो? चलो dance floor पे! ये है {next}!",
    ],
    "karaoke": [
        "Karaoke time! Screen पे words हैं, सब मिलकर गाओ! ये है {next}!",
    ],
    "sing_along": [
        "सब मिलकर गाओ! ज़ोर से!",
    ],
    "hype": [
        "{hosts_hi} के लिए ज़ोरदार तालियाँ! और ज़ोर से!",
        "हाथ ऊपर! Happy Diwali, क्या party है!",
    ],
    "cake_10": [
        "दस मिनट में हमारा Diwali moment है! अपने family और friends को पास बुला लो!",
    ],
    "cake_5": [
        "बस पाँच मिनट! सब लोग पास आ जाओ, Diwali moment आने वाला है!",
    ],
    "birthday_intro": [
        "सब लोग ध्यान दीजिए! पास आ जाइए, दीये तैयार रखिए. {hosts_hi} के साथ हमारा Diwali moment!",
    ],
    "cake": [
        "तीन, दो, एक! सबको दीपावली की हार्दिक शुभकामनाएँ! Happy Diwali!",
    ],
    "shoutout": [
        "दीपावली मुबारक! {hosts_hi}, इस शानदार पार्टी के लिए thank you!",
    ],
    "closing": [
        "आप सब कमाल के थे! एक बार फिर, Happy Diwali. {hosts_hi}, thank you. Good night, everybody!",
    ],
}

WORDS = {
    "birthday": {"moment": "🎂 Cake time", "moment_icon": "🎂", "wish": "birthday wish", "wishes": "Birthday wishes",
                 "wish_hint": "Happy birthday! …", "moment_notice": "🎂 Birthday time! The DJ is starting the birthday song."},
    "diwali": {"moment": "🪔 Diwali moment", "moment_icon": "🪔", "wish": "Diwali wish", "wishes": "Diwali wishes",
               "wish_hint": "Happy Diwali! …", "moment_notice": "🪔 Diwali moment! The DJ is starting the Diwali song."},
}


def words(cfg) -> dict:
    return WORDS[cfg.party_type]


def hosts(cfg) -> str:
    return f"{cfg.host_name} and {cfg.co_host_name}" if cfg.co_host_name else cfg.host_name


def title(cfg) -> str:
    if cfg.party_type == "diwali":
        return f"{hosts(cfg)}'s Diwali Party"
    return f"{cfg.birthday_person_name}'s Birthday Party"


def writer(cfg, seed: str) -> announcer.Writer:
    if cfg.party_type != "diwali":
        return announcer.Writer(cfg.birthday_person_name, cfg.host_name, seed=seed,
                                hindi_share=cfg.hindi_announcement_share)
    city = cfg.city.strip()
    return announcer.Writer(hosts(cfg), cfg.host_name, seed=seed, hindi_share=cfg.hindi_announcement_share,
                            lines=DIWALI_LINES, lines_hi=DIWALI_LINES_HI,
                            extra={"hosts": hosts(cfg), "in_city": f" in {city}" if city else "",
                                   "city_shout": f", {city}" if city else "",
                                   "hosts_hi": hosts(cfg).replace(" and ", " और "),
                                   "in_city_hi": f", {city}" if city else ""})


def wish_line(cfg, rng, name: str, text: str) -> str:
    if cfg.party_type == "diwali":
        return rng.choice([f"A Diwali wish from {name}: {text}",
                           f"{name} says: {text} Happy Diwali, everybody!"])
    p = cfg.birthday_person_name
    return rng.choice([f"Got a birthday message for {p} from {name}. {text}",
                       f"{name} says: {text} Happy birthday, {p}!"])


def party_settings(base: dict, diwali: bool, host: str, co_host: str, person: str, city: str,
                   date: str, start: str, minutes: int, moment: str, auth_file: str = "") -> dict:
    """A new party's settings: the usual config, with this party's answers in place of the old ones."""
    cfg = {k: v for k, v in (base or {}).items()
           if k not in ("birthday_person_name", "host_name", "name_pronunciations", "party_date", "start_time",
                        "duration_minutes", "birthday_block_time", "diwali_moment_time", "requested_tracks",
                        "party_type", "co_host_name", "city", "youtube_auth_file")}
    cfg.update({"party_type": "diwali" if diwali else "birthday", "host_name": host, "co_host_name": co_host,
                "city": city, "party_date": date, "start_time": start, "duration_minutes": minutes,
                "requested_tracks": []})
    if auth_file:
        cfg["youtube_auth_file"] = auth_file
    if diwali:
        cfg.update({"diwali_moment_time": moment, "birthday_song_start_seconds": 0})
    else:
        cfg.update({"birthday_person_name": person, "birthday_block_time": "00:00"})
    return cfg
