"""What kind of party it is (a birthday or Diwali), and the words that change with it."""
from __future__ import annotations

from . import announcer

# The DJ's lines for a Diwali party. They never name the hosts (Suman: the app must work for any party);
# {city} is where the party is.
DIWALI_LINES = {
    # Said like a smart Indian club DJ: English, with the odd Hindi word everyone at the party uses.
    "opening": [
        "Happy Diwali, everybody! Welcome to the Diwali party{in_city}. I'm your DJ for tonight. Diyas are lit, the vibe is set, so chalo, let's get this party started!",
    ],
    "Warm-up": [
        "Easing into the festive mood with a proper classic. Sing along, this is {next}!",
        "Diyas glowing, food is ready, and the music is on. Here's {next}!",
        "Old is gold, my friends. Volume up, this is {next}!",
        "Good food, great company, Diwali vibes. Keep it rolling with {next}!",
    ],
    "Build": [
        "Arre wah, I see some moves already! Let's keep it going, this is {next}!",
        "Now we're talking! Chalo, everyone on the floor. This one's {next}!",
        "The energy is building, I love it! Coming up, {next}!",
        "Full josh now, everybody! Let's go, {next}!",
    ],
    "Peak": [
        "Okay, this is the moment! Haath upar, hands all the way up! It's {next}!",
        "Turn it up, louder! This one is a total banger. Let's go, {next}!",
        "Brighter than the fireworks outside! Everybody, {next}!",
        "Dhol is coming in, you know what time it is! Balle balle, {next}!",
    ],
    "Peak 2": [
        "Thought we were done? No way! The night is still young. Here's {next}!",
        "This Diwali party is next level! Don't stop now, it's {next}!",
        "Let me hear you{city_shout}! Everybody on the floor for {next}!",
        "Ekdum full power! Bring it back, {next}!",
    ],
    "Wind-down": [
        "Alright, let's slow it down a little. Grab someone special. This is {next}.",
        "Take a breather and sing along with me. Here's {next}.",
        "Easy now, feel this one. It's {next}.",
    ],
    "vibe_up": [
        "Arre, why so quiet? It's Diwali, I need more energy! Here's {next}!",
        "Come on, I know you've got more! Let's turn it up, it's {next}!",
    ],
    "request": [
        "We have a request, and what a choice! This is {next}!",
        "Somebody has great taste! By request, here's {next}!",
    ],
    "guest_request": [
        "This one is a request from {who}! Great choice. Let's go, {next}!",
        "Shout-out to {who}, you asked for it, you got it! It's {next}!",
        "Request coming up for {who}! Everybody, this is {next}!",
    ],
    "dedication": [
        "This one goes out to {to}, with lots of love from {who}! It's {next}!",
        "Special dedication! From {who}, for {to}. Here's {next}!",
    ],
    "dance_floor": [
        "I see too many people sitting down! Chalo, everybody on the dance floor. It's {next}!",
        "The dance floor is looking lonely! Grab a friend and come on up. This is {next}!",
    ],
    "karaoke": [
        "Karaoke time! The words are on the screen, so sing it loud. This is {next}!",
        "Tonight you are the singer! Everybody sing along to {next}!",
    ],
    "sing_along": [
        "This one is yours! Everybody sing!",
        "I can't hear you! Sing it with me, everybody!",
    ],
    "hype": [
        "Make some noise for our amazing hosts! Louder! Let me hear you!",
        "Everybody, haath upar! Happy Diwali, what a party!",
    ],
    "cake_10": [
        "Ten minutes to our Diwali moment! Find your family and friends and get ready!",
    ],
    "cake_5": [
        "Just five minutes to go! Everybody gather round, our Diwali moment is almost here!",
    ],
    "birthday_intro": [
        "Can I have everyone's attention, please? Gather round, diyas ready. It's our Diwali moment!",
    ],
    "cake": [
        "Three, two, one! Happy Diwali, everybody! Shubh Deepavali!",
    ],
    "shoutout": [
        "Happy Diwali{city_shout}! A big thank you to our hosts for bringing everyone together tonight!",
    ],
    "closing": [
        "You were all amazing tonight! Happy Diwali once again, and a big thank you to our hosts for this lovely party. Good night, everybody!",
    ],
}

DIWALI_LINES_HI = {
    "opening": [
        "Happy Diwali, everybody! Diwali party{in_city_hi} में आप सबका स्वागत है. मैं हूँ आपका DJ. तो चलो, party शुरू करते हैं!",
    ],
    "Warm-up": [
        "शुभ दीपावली! अब आ रहा है एक evergreen गाना, {next}!",
        "दीये जल रहे हैं, माहौल बन रहा है. ज़ोर से गाइए, ये है {next}!",
    ],
    "Build": [
        "अरे वाह, dance floor गरम हो रहा है! रुकना नहीं है, ये है {next}!",
        "चलो, सब floor पे आइए! आ गया {next}!",
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
        "हमारे hosts के लिए ज़ोरदार तालियाँ! और ज़ोर से!",
        "हाथ ऊपर! Happy Diwali, क्या party है!",
    ],
    "cake_10": [
        "दस मिनट में हमारा Diwali moment है! अपने family और friends को पास बुला लो!",
    ],
    "cake_5": [
        "बस पाँच मिनट! सब लोग पास आ जाओ, Diwali moment आने वाला है!",
    ],
    "birthday_intro": [
        "सब लोग ध्यान दीजिए! पास आ जाइए, दीये तैयार रखिए. हमारा Diwali moment आ गया!",
    ],
    "cake": [
        "तीन, दो, एक! सबको दीपावली की हार्दिक शुभकामनाएँ! Happy Diwali!",
    ],
    "shoutout": [
        "दीपावली मुबारक! हमारे hosts को इस शानदार पार्टी के लिए thank you!",
    ],
    "closing": [
        "आप सब कमाल के थे! एक बार फिर, Happy Diwali, और hosts को thank you. Good night, everybody!",
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
