"""The Watcher's inner voice (5.5.3.1).

Not a caption system: the Watcher does not narrate the journal. It has its
own thoughts and chooses when to share one. Mostly it is silent. When it
speaks it is calm, polite and a little unsettling, in its own words (it is
our character, inspired by the feeling of HAL 9000, and never quotes him).

Every thought comes from something true (the session, the commander's
travels, their Codex, fuel, danger, a death, a sale, an achievement, the
time) and never invents a figure. It remembers what it has said, so it
does not repeat itself, and it remembers the commander between sessions.

The same thoughts are meant to be spoken one day (todo-watcher-voice.md);
for now they appear beside the orb, typed out, then dissolve.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path
import zlib

from voidcompass.core import ranks
from voidcompass.exploration.notable_bodies import is_green_giant_codex, rarity
from voidcompass.mining.mining_record import material_name
from voidcompass.overlays import (
    watcher_deeper, watcher_habits, watcher_idle, watcher_lines, watcher_lore, watcher_natures, watcher_places,
    watcher_copilot, watcher_knowing, watcher_learning, watcher_llm, watcher_name, watcher_postcards, watcher_questions,
    watcher_voice_lore, watcher_worlds,
)

# 5.7.1, its own words: how long a sign-off recap may take; how often it
# retries condensing what it knows of you; how many page paragraphs it keeps.
RECAP_WAIT_S = 15.0
# What it said in its own words, kept for you to rate; and your votes.
OWN_SAID_KEPT = 40
VOTES_KEPT = 60
ABOUT_RETRY_S = 3600.0
MIND_WORDS_KEPT = 40

# Story moments the eye shows once (5.6.1): the first time it heard the
# sound, and the shutter drawn (and kept drawn).
STORY_EFFECTS = {"sound": "story_sound", "the_fold": "story_shutter", "iv_s_unclench": "story_shutter",
                 "iv_o_breath": "story_open"}
# Passages where its voice slips: a gap, a second voice under it (5.6.1).
VOICE_SLIPS = {"let_me", "a_better_look", "it_noticed", "iv_s_knock", "iv_o_there_you_are", "iv_o_mountain"}

# How often it may speak (Overlay Studio). The gap is the least time
# between two thoughts; `minimum` is the least importance it will voice.
FREQUENCIES = {
    "off": None,
    # gap: least time between two thoughts; minimum: least importance it
    # voices; quiet: how long without anything happening before it mutters.
    # mutter: least time between two idle thoughts (5.5.3.2).
    "rare": {"gap": 300.0, "minimum": 2, "quiet": 900.0, "rest": 1200.0, "mutter": 1200.0},
    "occasional": {"gap": 75.0, "minimum": 1, "quiet": 300.0, "rest": 600.0, "mutter": 600.0},
    "chatty": {"gap": 25.0, "minimum": 0, "quiet": 120.0, "rest": 300.0, "mutter": 300.0},
}
DEFAULT_FREQUENCY = "rare"
PERSONALITIES = ("stoic", "curious", "nervous", "weary")
# The Watcher is depressed by default (the user's wish); "weary" in config.
DEFAULT_PERSONALITY = "weary"
# A thought stays on screen this long (plus time to read).
THOUGHT_SECONDS = 9.0
# The same topic is not raised again for this long.
TOPIC_REST_S = 20 * 60.0
# The same kind of idle thought is not raised again for this long (5.5.3.2).
IDLE_REST_S = 30 * 60.0
# Galnet at most once a day, and each headline only once (5.5.11).
GALNET_REST_S = 86400.0
GALNET_HEADLINE_REST_S = 30 * 86400.0
# A prospected rock this rich in one material is worth a word (5.5.12).
RICH_ROCK_PCT = 30.0
RHINO_HOLD_T = 72
# Each SRV's hold, for "it's full" (the deck's VEHICLE_CARGO_CAPACITIES).
SRV_HOLD_T = {"rhino": RHINO_HOLD_T, "scarab": 4, "scorpion": 2}
# Cargo that fills the ship's hold; a full hold is only news soon after one.
LOADING_EVENTS = {"MarketBuy", "CollectCargo", "MiningRefined", "CargoTransfer", "CargoDepot", "BuyDrones"}
# A fight is over after this long with no attack, shields up and the game's
# danger flag clear (5.5.7); before, only a jump, supercruise or docking ended it.
CALM_S = 90.0
COMBAT_TOPICS = (
    "foot_danger", "foot_danger_over", "died_foot", "foot_win", "dropship", "hull_damage", "hull_critical",
    "shields_back", "combat_win", "interdiction_submitted", "combat_zone",
)
# Enough to remember every line it has said for a long while.
_MEMORY_LIMIT = 3000


def frequency(config):
    value = str((config or {}).get("heartbeat_thoughts") or DEFAULT_FREQUENCY).casefold()
    return value if value in FREQUENCIES else DEFAULT_FREQUENCY


THOUGHT_COLOURS = ("bright", "accent", "eye")
THOUGHT_SIZES = {"small": .85, "standard": 1.0, "large": 1.25}
THOUGHT_HOLDS = {"short": .65, "standard": 1.0, "long": 1.6}


def thought_style(config):
    """How the thoughts look and how long they stay (Overlay Studio)."""
    config = config or {}
    colour = str(config.get("heartbeat_thought_colour") or "bright").casefold()
    size = str(config.get("heartbeat_thought_size") or "standard").casefold()
    hold = str(config.get("heartbeat_thought_hold") or "standard").casefold()
    return {
        "backdrop": bool(config.get("heartbeat_thought_backdrop", True)),
        "heading": bool(config.get("heartbeat_thought_heading", True)),
        "colour": colour if colour in THOUGHT_COLOURS else "bright",
        "size": size if size in THOUGHT_SIZES else "standard",
        "hold": hold if hold in THOUGHT_HOLDS else "standard",
    }


# The line above a thought (5.5.3.5): what kind of thought it is. A passage
# of its story says where it sits; an echo, what stirred it.
HEADED_TOPICS = {
    "lore_afterword": ("afterword", "AFTERWORD"),
    "lore_recall": ("recall", "LOOKING BACK"),
    "idle_lore": ("musing", "REMEMBERING"),
    "idle_after": ("musing", "REMEMBERING"),
    "idle_lens": ("musing", "THE SEAT"),
    # 5.6.1: Book Four's roads; a question; a dream; a moment it kept.
    "idle_four_shut": ("musing", "THE SHUTTER"),
    "idle_four_open": ("musing", "LOOKING BACK"),
    "question": ("question", "A QUESTION"),
    "callback": ("recall", "YOU SAID"),
    "dream_told": ("recall", "A DREAM"),
    "idle_moment": ("recall", "I KEEP THIS"),
    "lore_meeting": ("memory", "ANOTHER WATCHER"),
    "sign_off": ("", "SIGNING OFF"),
    "sign_off_quiet": ("", "SIGNING OFF"),
    # 5.5.3.7: a note you left, handed back; where you were on this date.
    "capsule": ("recall", "TIME CAPSULE"),
    # 5.5.4: one another commander shared with you.
    "capsule_shared": ("recall", "TIME CAPSULE · FROM ANOTHER COMMANDER"),
    "on_this_day": ("recall", "ON THIS DAY"),
    "capsule_early": ("recall", "TIME CAPSULE · NOT YET"),
    "constellation_named": ("recall", "A NEW CONSTELLATION"),
    # 5.6.4: your Hatchling.
    **{topic: ("", "THE HATCHLING") for topic in ("hatchling_toy", "hatchling_trick", "hatchling_scared", "hatchling_grown", "hatchling_idle", "hatchling_said")},
    # 5.5.4: finding its voice, and what it has learned about you.
    "voice_found": ("memory", watcher_voice_lore.TITLE),
    "habit_milestone": ("", "A MILESTONE"),
    **{topic: ("musing", "WHAT IT HAS WATCHED OF YOU") for topic in watcher_habits.HABIT_TOPICS if topic != "habit_milestone"},
    # 5.7.1: your name, and what the journal says of you; its reply to you.
    **watcher_name.HEADINGS,
    "talk": ("reply", "IN REPLY"),
}


def thought_heading(topic, words=""):
    """(kind, heading) for a thought: kind styles it ("memory", "echo",
    "afterword", "recall", "musing" or ""), heading names it ("" for an
    everyday remark, which the page heads THE WATCHER)."""
    topic = str(topic or "")
    if topic == "lore_fragment":
        place = watcher_lore.passage_place(words)
        if place:
            numeral, title, nth, total = place
            return "memory", f"MEMORY · {numeral}. {title.upper()} · {nth} OF {total}"
        return "memory", "MEMORY"
    if topic == "voice_found":
        return "memory", watcher_voice_lore.heading(words)
    if topic in watcher_lore.ECHO_LABELS:
        return "echo", f"ECHO · {watcher_lore.ECHO_LABELS[topic].upper()}"
    return HEADED_TOPICS.get(topic, ("", ""))


def personality(config):
    value = str((config or {}).get("heartbeat_personality") or DEFAULT_PERSONALITY).casefold()
    return value if value in PERSONALITIES else DEFAULT_PERSONALITY


# How much each topic matters: 3 it must say (a death), 2 notable, 1 worth
# a remark, 0 idle. The words are in watcher_lines.py.
IMPORTANCE = {
    # 5.6.1: an expedition's milestones, each said once.
    "expedition_set_out": 3, "expedition_region": 2, "expedition_halfway": 3, "expedition_furthest": 2,
    "expedition_close_call": 3, "expedition_home": 3, "expedition_risk": 2,
    "expedition_marked": 1, "expedition_place_reached": 2,
    # 5.6.1, deeper: poked by trust, its slow mood, a moment kept, an
    # anniversary of you two, a dream, another Watcher, Book Four's musings.
    "poked_wary": 2, "poked_warm": 2, "mood_low": 1, "mood_high": 1, "idle_moment": 1, "anniversary_us": 3,
    "dream_told": 2, "watchers_meet": 3, "idle_four_shut": 1, "idle_four_open": 1,
    "greet_new": 3,
    "greet_away": 3,
    "greet_soon": 2,
    "greet_night": 2,
    "after_death": 3,
    "died": 3,
    "danger": 2,
    "danger_over": 1,
    # 5.5.7: fights in more detail, and on foot (the game logs no attack there;
    # Status.json's health says it instead).
    "foot_danger": 2,
    "foot_danger_over": 1,
    "died_foot": 3,
    "foot_win": 1,
    "dropship": 2,
    "hull_damage": 2,
    "hull_critical": 3,
    "shields_back": 1,
    "combat_win": 1,
    "interdiction_submitted": 1,
    "combat_zone": 2,
    "fuel_low": 2,
    "first_discovery_streak": 2,
    "undiscovered_system": 1,
    "new_region": 2,
    "valuable_world": 2,
    # 5.5.3.9: each kind of world worth stopping for, in its own words. An
    # earth-like, or any of them never charted before, it always remarks on.
    "world_earthlike": 3,
    "world_water": 2,
    "world_ammonia": 2,
    "world_terraformable": 1,
    "world_first": 3,
    # 5.5.3.1: rare worlds, and its word at the end of a session.
    "rare_world": 2,
    "green_giant": 3,
    "sign_off": 3,
    "sign_off_quiet": 2,
    # A second beat after a thought, now and then (5.5.3.2).
    "afterthought": 0,
    # Flying and walking about (5.5.3.2).
    "jet_boost": 1,
    "heat_warning": 2,
    "interdiction_escaped": 1,
    "srv_launch": 0,
    "settlement_seen": 0,
    "taxi_ride": 0,
    "carrier_jump": 1,
    # It remembers (5.5.3.2): places, your records, the day you started.
    "revisit": 2,
    "record_far": 2,
    "record_jump": 2,
    "record_firsts": 2,
    "anniversary": 3,
    # 5.5.3.7: your time capsules, and On this day.
    "capsule": 3,
    "capsule_shared": 3,
    "on_this_day": 2,
    "capsule_early": 2,
    "constellation_named": 3,
    # 5.6.4: your Hatchling; growing up is said whatever the hour.
    "hatchling_toy": 1, "hatchling_trick": 2, "hatchling_scared": 1, "hatchling_grown": 2, "hatchling_idle": 0, "hatchling_said": 0,
    # You and it: a poke, hiding it, moving it, and the bond over time.
    "poked": 3,
    "poked_again": 3,
    "unhidden": 2,
    "moved": 1,
    "greet_bond": 3,
    # 5.5.3.2: idle thoughts about what's really around you.
    **{topic: 1 for topic in watcher_idle.IDLE_TOPICS},
    "codex_new": 2,
    # Echoes (5.5.3.5): real things in the game that stir a memory of its past.
    **{topic: 2 for topic in watcher_lore.ECHOES},
    "codex_logged": 1,
    "big_sale": 1,
    "achievement": 2,
    "promotion": 2,
    "long_session": 1,
    "quiet": 0,
    "docked_home": 0,
    "jump_far": 0,
    "arrival": 0,
    "jump_long": 1,
    "scooped": 0,
    "fss_complete": 1,
    "mapped": 1,
    "mapped_efficient": 1,
    "analysed": 1,
    "touchdown": 0,
    "undocked": 0,
    "on_foot": 0,
    "mission_done": 1,
    "bounty": 0,
    "mined": 0,
    # 5.5.11: refined in the Rhino, from rigs on a planet (no asteroids, no limpets).
    "mined_surface": 0,
    # 5.5.12: each vehicle by name, and the moments of a mining run.
    "launch_scarab": 0, "launch_scorpion": 0, "launch_rhino": 0, "launch_nomad": 0, "launch_fighter": 0,
    "prospected_rich": 0, "motherlode": 2, "cracked": 1, "rhino_full": 1, "hold_full_mining": 1,
    "hold_full": 1, "srv_full": 1, "srv_fuel_low": 2,
    # 5.5.4: how you play, as it has come to know it; a milestone as it happens.
    **{topic: 1 for topic in watcher_habits.HABIT_TOPICS},
    "habit_milestone": 2,
    # 5.7.1: what the journal says of you.
    **{topic: level for topic, (level, _normal, _weary) in watcher_name.FACTS.items()},
}
# Each topic: (importance, [lines]). A line takes {fields} from the context
# that raised it; a line whose fields are missing is skipped.
TOPICS = {topic: (level, watcher_lines.NORMAL[topic]) for topic, level in IMPORTANCE.items()}
# The depressed nature ("weary" in config; the default since 5.5.3.1).
WEARY = watcher_lines.WEARY

# How each personality weighs the topics (missing: 1).
PERSONALITY_WEIGHTS = {
    "stoic": {"quiet": 0, "docked_home": 0, "idle": .4, "codex_logged": .5, "big_sale": .5, "greet_soon": .5},
    "curious": {"idle": 1.3, "codex_new": 1.5, "codex_logged": 1.5, "undiscovered_system": 1.5, "new_region": 1.3},
    "nervous": {"danger": 1.6, "fuel_low": 1.6, "after_death": 1.5, "quiet": 1.2, "danger_over": 1.4,
                "foot_danger": 1.6, "hull_damage": 1.6, "foot_danger_over": 1.4, "combat_zone": 1.4},
    # The weary one mutters to itself more in the quiet.
    "weary": {"idle": 1.4, "quiet": 1.6, "docked_home": 1.3, "long_session": 1.3, "big_sale": .8},
}


# How the eye looks while it says each thought (heartbeat-life.js plays
# the matching expression): pleased, wary, curious, or downcast. Topics not
# listed are said with a neutral eye.
MOODS = {
    "expedition_set_out": "curious", "expedition_region": "curious", "expedition_halfway": "pleased",
    "expedition_furthest": "curious", "expedition_close_call": "wary", "expedition_home": "pleased",
    "expedition_risk": "wary", "expedition_marked": "curious", "expedition_place_reached": "pleased",
    "poked_wary": "wary", "poked_warm": "pleased", "mood_low": "downcast", "mood_high": "pleased",
    "idle_moment": "pleased", "anniversary_us": "pleased", "dream_told": "curious", "watchers_meet": "pleased",
    "idle_four_shut": "downcast", "idle_four_open": "curious",
    "question": "curious", "answer": "pleased", "callback": "pleased", "lore_meeting": "pleased",
    **{topic: "pleased" for topic in (
        "rare_world", "green_giant", "valuable_world", "first_discovery_streak", "undiscovered_system",
        "codex_logged", "codex_new", "big_sale", "achievement", "promotion", "mapped_efficient",
        "analysed", "fss_complete", "mapped", "scooped", "mission_done", "sign_off", "idle_recall",
        "idle_session", "new_region", "greet_away", "greet_soon", "danger_over", "idle_music")},
    **{topic: "wary" for topic in ("danger", "fuel_low", "idle_deaths", "heat_warning", "foot_danger",
                                    "hull_damage", "hull_critical", "interdiction_submitted", "combat_zone",
                                    "dropship")},
    **{topic: "pleased" for topic in ("foot_danger_over", "shields_back", "combat_win", "foot_win")},
    "died_foot": "downcast",
    **{topic: "pleased" for topic in ("interdiction_escaped", "srv_launch", "idle_srv", "idle_ship")},
    **{topic: "pleased" for topic in ("launch_scarab", "launch_rhino", "launch_nomad", "idle_scarab", "idle_rhino", "idle_nomad",
                                       "prospected_rich", "motherlode", "cracked", "rhino_full", "hold_full_mining",
                                       "hold_full", "srv_full")},
    "srv_fuel_low": "wary",
    **{topic: "wary" for topic in ("launch_scorpion", "launch_fighter", "idle_scorpion", "idle_fighter")},
    "idle_ring": "curious",
    **{topic: "curious" for topic in ("jet_boost", "settlement_seen", "carrier_jump", "idle_settlement",
                                       "idle_near_body", "idle_supercruise")},
    **{topic: "downcast" for topic in ("taxi_ride", "idle_taxi", "idle_station_foot")},
    **{topic: "pleased" for topic in ("record_far", "record_jump", "record_firsts", "anniversary", "greet_bond",
                                       "idle_bond_1", "idle_bond_2", "idle_bond_3", "unhidden")},
    **{topic: "curious" for topic in ("revisit", "poked", "moved")},
    "poked_again": "wary",
    # Its past (5.5.3.5): told with a heavy eye.
    "lore_fragment": "downcast",
    "idle_lore": "downcast",
    **{topic: "downcast" for topic in watcher_lore.ECHOES},
    "lore_sound": "wary",
    "lore_core": "curious",
    # After the story: settled; looking back on what it told you.
    "lore_afterword": "pleased",
    "idle_after": "curious",
    "lore_recall": "downcast",
    "idle_postcard": "pleased",
    "capsule": "pleased",
    "capsule_shared": "curious",
    "world_earthlike": "pleased",
    "world_water": "curious",
    "world_ammonia": "curious",
    "world_terraformable": "curious",
    "world_first": "pleased",
    "on_this_day": "downcast",
    "capsule_early": "curious",
    "constellation_named": "pleased",
    "hatchling_toy": "pleased", "hatchling_trick": "pleased", "hatchling_scared": "wary", "hatchling_grown": "pleased",
    "hatchling_idle": "curious", "hatchling_said": "pleased",
    **{topic: "curious" for topic in watcher_habits.HABIT_TOPICS},
    "habit_milestone": "pleased",
    "voice_found": "curious",
    "idle_home_away": "pleased",
    **{topic: "curious" for topic in (
        "idle_star_odd", "idle_big_system", "arrival", "jump_long", "jump_far", "idle_far", "idle_star",
        "idle_galnet", "greet_new")},
    **{topic: "downcast" for topic in (
        "quiet", "long_session", "idle_small_system", "idle_night", "idle_morning", "docked_home",
        "idle_docked", "idle_landed", "idle_on_foot", "idle_home", "sign_off_quiet", "after_death",
        "died", "afterthought", "idle_self", "greet_night")},
}
# A line may correct itself as it is typed: "I [[love|tolerate]] it" types
# "love", stops, deletes it and types "tolerate". The plain text keeps the
# final word.
_CORRECTION = re.compile(r"\[\[([^|\]]*)\|([^\]]*)\]\]")


# The words it noticed (5.5.3.5): what a line was filled with from the
# journal (a system, a world, a species, a distance) is marked "⟦Hatchooe⟧"
# in its script, and the page picks it out in the theme's accent. Its own
# words for time ({hours}, {away}, {when}) and its memories stay plain.
NOTICED_FIELDS = frozenset((
    "body", "system", "species", "dist", "kind", "star", "a_star", "A_star", "region", "credits",
    "station", "material", "reward", "name", "ly", "title", "rank", "thing", "Thing", "headline",
    "artist", "count", "firsts", "jumps", "fuel", "summary", "settlement",
    # 5.5.4: what it knows of how you play.
    "commodity", "mined", "target", "sold", "best", "style", "longest", "bodies", "mapped", "bio", "tonnes",
    "profit", "bounties", "scoops", "scooped_t", "landings", "best_cr", "bounty_cr", "sold_t", "mined_n",
    "home", "sender",
))
NOTICE_OPEN, NOTICE_CLOSE = "⟦", "⟧"


def noticed(fields):
    """Fields with the journal's words marked for the page."""
    return {key: f"{NOTICE_OPEN}{value}{NOTICE_CLOSE}"
            if key in NOTICED_FIELDS and str(value).strip() else value
            for key, value in fields.items()}


def noticed_in(text, fields):
    """New words (5.7.1) with the journal's words marked again, where they appear."""
    for key, value in (fields or {}).items():
        value = str(value).strip()
        if key in NOTICED_FIELDS and value and value in text and f"{NOTICE_OPEN}{value}" not in text:
            text = text.replace(value, f"{NOTICE_OPEN}{value}{NOTICE_CLOSE}", 1)
    return text


def plain_text(script):
    text = _CORRECTION.sub(lambda match: match.group(2), str(script or ""))
    return text.replace(NOTICE_OPEN, "").replace(NOTICE_CLOSE, "")


def when_text(stamp, now=None):
    """A journal timestamp as a moment it remembers: "3 days ago",
    "in March", "in March 2025"."""
    then = None
    try:
        then = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone()
    except (TypeError, ValueError):
        return ""
    now = datetime.fromtimestamp(now if now is not None else time.time()).astimezone()
    days = (now - then).days
    if days < 1:
        return "earlier today"
    if days < 2:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    month = then.strftime("%B")
    return f"in {month}" if then.year == now.year else f"in {month} {then.year}"


def times_text(count):
    count = int(count or 0)
    return {1: "once", 2: "twice"}.get(count, f"{count:,} times")


def _credits_text(value):
    value = int(value or 0)
    for suffix, divisor in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if value >= divisor:
            return f"{value / divisor:.1f}{suffix}".replace(".0" + suffix, suffix)
    return f"{value:,}"


def session_earned(session):
    """Credits a Captain's Log session earned: data sold and trade profit."""
    session = session or {}
    return max(0, sum(int(session.get(key) or 0) for key in ("exploration_sales", "biology_sales", "trade_profit")))


def _stamp_seconds(stamp):
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def session_hours(session, now=None):
    session = session or {}
    start = _stamp_seconds(session.get("started"))
    end = _stamp_seconds(session.get("ended")) if session.get("ended") else (now or time.time())
    return max(0.0, (end - start) / 3600.0) if start is not None and end is not None else 0.0


def session_flown(session, now=None):
    """How long the session has run, as 2h 14m."""
    minutes = int(round(session_hours(session, now) * 60))
    return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def session_summary(session):
    """The session's own figures in words, only what really happened:
    "41 jumps, 6 first discoveries and 12.4M credits"."""
    session = session or {}
    parts = []
    for key, one, many in (
        ("jumps", "jump", "jumps"),
        ("first_discoveries", "first discovery", "first discoveries"),
        ("rare_worlds", "rare world", "rare worlds"),
        ("bio_analyses", "species analysed", "species analysed"),
        ("dss_maps", "world mapped", "worlds mapped"),
    ):
        count = int(session.get(key) or 0)
        if count:
            parts.append(f"{count:,} {one if count == 1 else many}")
    earned = session_earned(session)
    if earned:
        parts.append(f"{_credits_text(earned)} credits")
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _away_text(seconds):
    days = seconds / 86400.0
    if days >= 2:
        return f"{int(days)} days"
    if days >= 1:
        return "a day"
    hours = seconds / 3600.0
    return f"{int(hours)} hours" if hours >= 2 else "a while"


class WatcherMind:
    """Chooses, words and remembers the Watcher's thoughts."""

    def __init__(self, memory_path=None, config=None, clock=time.time, rng=None):
        self.memory_path = Path(memory_path) if memory_path else None
        self.config = config if config is not None else {}
        self.clock = clock
        self.random = rng or random.Random()
        self.lock = threading.Lock()
        self.memory = self._fresh_memory()
        self._load()
        # 5.7.1: notes an earlier build took from your questions, let go.
        watcher_knowing.forget_questions(self.memory)
        self._fresh_state()
        # 5.7.1: its own words (watcher_llm.WatcherLLM) and what's true right
        # now for them (a callable: system, ship, what you're doing); the app sets both.
        self.llm = None
        self.facts_provider = None
        # What the ship's systems show about a question (route, survey, ship...),
        # and the small things it does when asked (watcher_copilot); the app sets both.
        self.lookup_provider = None
        self.action_provider = None
        # Told when a page's paragraph in its own words is ready (own_paragraph).
        self.on_words = None

    @staticmethod
    def _fresh_memory():
        """A memory with nothing in it: how it is the first time it wakes."""
        return {"last_seen": None, "sessions": 0, "said": [], "regions": [],
                       "deaths": 0, "last_death": None, "session_started": None, "thoughts": None,
                       # 5.5.3.2: hours flown together, your records, the day
                       # it last marked your anniversary, and what it said.
                       "hours": 0.0, "records": {}, "anniversary_said": None, "log": [],
                       # 5.5.3.5: the memories of its past it has shared, [id, when];
                       # the echoes found, {topic: [times, last]}; when it said
                       # its afterword (Book One finished).
                       "lore": [], "echoes": {}, "afterword": None,
                       # 5.6.1, deeper: its trust in you and its slow mood;
                       # the questions it asked and your answers; moments it
                       # keeps; the places it asked for and reached; Book
                       # Four's road; dreams; other Watchers met.
                       "trust": watcher_deeper.TRUST_START, "mood": 0.0, "questions": {}, "moments": [],
                       "places": {}, "road": None, "pilgrimage": None, "dreams": [], "met": [],
                       "first_seen": None, "first_system": None, "last_system": None, "ship_name": None}

    def _fresh_state(self):
        """What it holds in mind only for now (not remembered)."""
        if self.memory.get("thoughts") is None:
            # Older memories: count the thoughts it remembers saying.
            self.memory["thoughts"] = sum(1 for row in self.memory["said"]
                                          if isinstance(row, list) and row and ":" not in str(row[0]) and row[0] != "idle")
        self._afterthought = None
        # 5.7.1: a thought waiting for its own words; your words, for a reply;
        # a thought of its own, and a diary entry, being written.
        self._llm_pending = None
        self._talk_pending = None
        self._own_pending = None
        self._diary_pending = None
        self._notes_pending = None
        # What it knows of you, being condensed; a page's paragraph being
        # written in its own words, and the ones it couldn't (this run).
        self._about_pending = None
        self._about_tried = None
        self._paragraph_pending = None
        self._paragraphs_refused = set()
        # 5.6.1: the question waiting for an answer, and something to say on
        # the next quiet tick (after a greeting, a dream; a meeting's passage).
        self._question = None
        self._say_next = []
        self._scared = False
        self._counted_until = None
        self._poked_at = 0.0
        self._pokes = 0
        self._hidden_at = None
        self._record_said = set()
        self.thought = None          # {id, text, at, until}
        self._serial = 0
        self._last_spoke = 0.0
        self._session_start = None
        self._first_streak = 0
        self._in_danger = False
        # 5.5.7: when the last threat was, shields down, the hull warning
        # given (0 none, 1 damaged, 2 critical), and the fight on foot.
        self._danger_at = 0.0
        self._shields_down = False
        self._status_danger = False
        self._hull_warned = 0
        self._on_foot = False
        self._foot_danger = False
        self._foot_health = None
        self._foot_hurt_at = 0.0
        self._low_health = False
        self._fuel_warned = False
        self._codex_bodies = set()
        self._last_interesting = self.clock()
        self._pending = []           # (importance, topic, fields)
        self._dead_since = None
        # 5.5.4: whether its voice is on (the HUD says), and when it last
        # counted the minutes it has had one.
        self.voice_active = False
        self._voice_counted = None
        # What's around the commander, for idle thoughts (5.5.3.2).
        self.surroundings = watcher_idle.Surroundings()

    # -- memory --------------------------------------------------------------
    def reset(self):
        """Forget everything (5.5.3.9, the Watcher page's RESET): the story,
        the echoes, what it said, the hours and sessions together, your
        bond. It wakes again as it did the first time. The old memory is
        kept beside it first, as watcher_memory.reset-<when>.json, so a
        slip can be undone by hand. The backup's path, or "" for none."""
        backup = ""
        if self.memory_path and self.memory_path.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(self.clock()))
            target = self.memory_path.with_name(f"{self.memory_path.stem}.reset-{stamp}{self.memory_path.suffix}")
            try:
                target.write_bytes(self.memory_path.read_bytes())
                backup = str(target)
            except OSError:
                return None  # no backup: forget nothing
        with self.lock:
            self.memory = self._fresh_memory()
        self._fresh_state()
        self._unsaved = True
        self.save()
        return backup

    def _load(self):
        if not self.memory_path:
            return
        try:
            data = json.loads(self.memory_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # Note: everything saved comes back, not just the keys a fresh
                # memory starts with (the postcards it kept, its habits and its
                # voice were lost on every restart before 5.5.4).
                self.memory.update(data)
        except (OSError, ValueError):
            pass

    def _account_time(self):
        """Add the time since it last counted to the hours spent together."""
        if self._session_start is None:
            return
        now = self.clock()
        start = max(self._session_start, self._counted_until or 0.0)
        if now > start:
            with self.lock:
                self.memory["hours"] = float(self.memory.get("hours") or 0.0) + (now - start) / 3600.0
        self._counted_until = now

    def bond(self):
        """0 a stranger, 1 known, 2 a companion, 3 an old friend: from the
        sessions and hours you've spent together."""
        sessions = int(self.memory.get("sessions") or 0)
        hours = float(self.memory.get("hours") or 0.0)
        for level, (need_sessions, need_hours) in ((3, (30, 100)), (2, (10, 25)), (1, (3, 5))):
            if sessions >= need_sessions and hours >= need_hours:
                return level
        return 0

    def save(self):
        self._account_time()
        if not self.memory_path:
            return
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.memory_path.with_suffix(".tmp")
            with self.lock:
                payload = dict(self.memory)
                payload["said"] = payload["said"][-_MEMORY_LIMIT:]
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temporary, self.memory_path)
            # Saved: the periodic save (save_if_due) starts counting again.
            self._unsaved = False
            self._saved_at = time.time()
        except OSError:
            pass

    # -- choosing ------------------------------------------------------------
    def _said_recently(self, key, within):
        now = self.clock()
        return any(row[0] == key and now - row[1] < within for row in self.memory["said"])

    def _variant(self, topic, fields):
        importance, variants = TOPICS[topic]
        nature = personality(self.config)
        if nature == "weary" and topic in WEARY:
            variants = WEARY[topic]
        # Stoic, curious and nervous each have their own words for the
        # moments that matter most, and borrow the rest (5.5.3.2).
        own = list(watcher_natures.BANKS.get(nature, {}).get(topic, ()))
        variants = own + [line for line in variants if line not in own]
        # 5.7.1: your name, if you said it may, at most once a session.
        named = []
        cmdr = watcher_name.may_name(self.memory, self._session_start) if topic in watcher_name.NAMED else None
        if cmdr:
            named = list(watcher_name.NAMED[topic]["weary" if nature == "weary" else "normal"])
            fields = {**fields, "cmdr": cmdr}
            variants = named + [line for line in variants if line not in named]
        options = []
        for template in variants:
            try:
                text = template.format(**noticed(fields))
            except (KeyError, IndexError, ValueError):
                continue
            # Remembered by its wording, so the line banks can change freely.
            options.append((f"{topic}:{zlib.crc32(template.encode('utf-8')):08x}", text, text != template))
        if not options:
            return None
        # Never the same words twice while another wording is left.
        fresh = [row for row in options if not self._said_recently(row[0], 30 * 86400)]
        named_keys = {f"{topic}:{zlib.crc32(line.encode('utf-8')):08x}" for line in named}
        fresh_named = [row for row in fresh if row[0] in named_keys]
        if fresh_named and self.random.random() < .5:
            watcher_name.mark_used(self.memory, self._session_start)
            return self.random.choice(fresh_named)[:2]
        if fresh:
            own_keys = {f"{topic}:{zlib.crc32(line.encode('utf-8')):08x}" for line in own}
            fresh_own = [row for row in fresh if row[0] in own_keys]
            if fresh_own and self.random.random() < .75:
                return self.random.choice(fresh_own)[:2]
            return self.random.choice(fresh)[:2]
        if importance < 2:
            # A minor remark stays unsaid rather than repeat a recent line: a
            # fixed line for three days, one filled with what's around (a
            # different star, a different station) for a day, and a passing
            # afterthought for half a day.
            def window(row):
                if topic == "afterthought":
                    return 12 * 3600
                return 86400 if row[2] else 3 * 86400
            fresh = [row for row in options if not self._said_recently(row[0], window(row))]
            if not fresh:
                return None
            return self.random.choice(fresh)[:2]
        # Something it must say, with every line used: the ones said longest ago.
        options.sort(key=lambda row: self._last_said(row[0]))
        return self.random.choice(options[:max(1, len(options) // 3)])[:2]

    def _last_said(self, key):
        return max((row[1] for row in self.memory["said"] if row[0] == key), default=0.0)

    def consider(self, topic, fields=None, force=False):
        """A reason to think something. It may well stay silent."""
        if topic not in TOPICS:
            return None
        setting = FREQUENCIES.get(frequency(self.config))
        if setting is None:
            return None
        importance, _variants = TOPICS[topic]
        if personality(self.config) == "weary" and (topic in {"quiet", "docked_home"} or topic in watcher_idle.IDLE_TOPICS):
            # A depressed robot complains about the quiet: worth saying aloud.
            importance = max(importance, 2)
        weights = PERSONALITY_WEIGHTS.get(personality(self.config), {})
        weight = weights.get(topic, weights.get("idle", 1) if topic in watcher_idle.IDLE_TOPICS else 1)
        if weight <= 0:
            return None
        now = self.clock()
        if not force:
            if importance < setting["minimum"]:
                return None
            if importance < 3 and now - self._last_spoke < setting["gap"]:
                return None
            rest = setting.get("rest", TOPIC_REST_S)
            if topic in watcher_idle.IDLE_TOPICS:
                rest = max(rest, IDLE_REST_S)  # each kind of idle remark, at most every half hour
            # An echo of its past, or a look back at its story, rests hours or
            # days (a neutron highway would otherwise make it a commentary).
            rest = max(rest, watcher_lore.LORE_REST_S.get(topic, 0.0))
            if topic == "idle_postcard":
                rest = max(rest, watcher_postcards.RECALL_REST_S)
            if topic == "idle_galnet":
                rest = max(rest, GALNET_REST_S)
            if topic.startswith("habit_") and topic != "habit_milestone":
                rest = max(rest, watcher_habits.HABIT_REST_S)
            if importance < 3 and self._said_recently(topic, rest):
                return None
            # Even with something to say, it often keeps it to itself.
            chance = min(1.0, (.35 + .25 * importance) * weight)
            if importance < 3 and self.random.random() > chance:
                return None
        headline_key = None
        if topic == "idle_galnet":
            headline = str((fields or {}).get("headline") or "").strip().casefold()
            headline_key = f"galnet:{zlib.crc32(headline.encode('utf-8')):08x}"
            if self._said_recently(headline_key, GALNET_HEADLINE_REST_S):
                return None
        chosen = self._variant(topic, dict(fields or {}))
        if not chosen:
            return None
        key, script = chosen
        if self._reword(topic, key, script, fields, importance, headline_key, now):
            return None
        self._utter(topic, key, script, now)
        if headline_key:
            with self.lock:
                self.memory["said"].append([headline_key, now])
        self._maybe_afterthought(topic, importance, script, now)
        return self.thought

    def _maybe_afterthought(self, topic, importance, script, now):
        """Now and then a second beat follows, once the first has been read."""
        if topic != "afterthought" and importance < 3:
            chance = .3 if (topic == "quiet" or topic in watcher_idle.IDLE_TOPICS) else .12
            if self.random.random() < chance:
                self._afterthought = {"after": self._serial, "at": now + 3.2 + len(script) * .045}

    def _utter(self, topic, key, script, now):
        """Say a thought: on screen for a while, and remembered."""
        text = plain_text(script)
        self._serial += 1
        self._last_spoke = now
        kind, heading = thought_heading(topic, text)
        self.thought = {"id": self._serial, "text": text, "script": script, "topic": topic,
                        "mood": MOODS.get(topic, ""), "at": now,
                        # How much it matters, for how much of it is spoken (5.5.4).
                        "importance": 3 if topic.startswith(("lore", "voice")) else IMPORTANCE.get(topic, 2),
                        "kind": kind, "heading": heading,
                        "until": now + (THOUGHT_SECONDS + len(script) * .05)
                        * THOUGHT_HOLDS[thought_style(self.config)["hold"]]}
        # How it says it (5.6.1): slower when weary or low, quicker when wary,
        # a whisper for its story, and rarely a slip in the voice.
        self.thought["voice"] = self._voice_feel(topic, key)
        effect = STORY_EFFECTS.get(str(key).split(":", 1)[-1]) if str(key).startswith("lore:") else None
        if effect:
            self.thought["effect"] = effect
        # The latest thing it said, kept for the deck's Focused Log.
        self.last_thought = {"text": text, "at": time.time()}
        with self.lock:
            self.memory["said"].append([key, now])
            self.memory["said"].append([topic, now])
            self.memory["thoughts"] = int(self.memory.get("thoughts") or 0) + 1
            log = self.memory.setdefault("log", [])
            log.append([round(time.time(), 1), topic, text])
            del log[:-300]
        self._unsaved = True
        return self.thought

    def relay(self, text, heading="", speak=False):
        """Words from outside (the local API, 5.5.7): shown as given, under
        the heading asked for, and spoken (when the voice is on) if ``speak``."""
        # Note: their markup characters go, or a caller could fake self-corrections.
        words = " ".join(str(text or "").replace("[[", "[").replace("]]", "]")
                         .replace("⟦", "").replace("⟧", "").split())[:400]
        thought = self._utter("relay", "relay", words, self.clock())
        thought["heading"] = " ".join(str(heading or "").split()).upper()[:40] or "RELAYED"
        thought["kind"] = "relay"
        thought["importance"] = 3 if speak else 0
        thought["speak"] = bool(speak)
        return dict(thought)

    def remember(self):
        """The next passage of its story, when one is due (5.5.3.5): in order,
        as the sessions and hours together unlock them, at most one every hour
        and a half of play, and never in a session's first minutes. Its
        thoughts switched off means no story either."""
        if FREQUENCIES.get(frequency(self.config)) is None or self._session_start is None or self._in_danger:
            return None
        # It keeps its story to itself while it doesn't trust you (5.6.1).
        if float(self.memory.get("trust", watcher_deeper.TRUST_START)) < watcher_deeper.TRUST_LOW:
            return None
        now = self.clock()
        if now - self._session_start < watcher_lore.SETTLE_S:
            return None
        shared = watcher_lore.told(self.memory)
        if shared and now - max(shared.values()) < watcher_lore.GAP_S:
            return None
        self._account_time()
        if watcher_lore.book_one_complete(self.memory) and not self.memory.get("afterword"):
            # The story told: one closing word, once ever (then Book Two).
            with self.lock:
                self.memory["afterword"] = now
            self._story_changed = True
            return self._utter("lore_afterword", "lore:afterword", watcher_lore.AFTERWORD, now)
        row = watcher_lore.due(self.memory, self.memory.get("sessions") or 0, self.memory.get("hours") or 0, now)
        if row is None:
            return None
        self._story_changed = True
        with self.lock:
            self.memory.setdefault("lore", []).append([row[0], now])
        return self._utter("lore_fragment", f"lore:{row[0]}", row[2], now)

    def story_progress(self):
        """The story so far (watcher_lore.progress), once each time it moves
        on: a passage told, the afterword, a new kind of echo found. None
        otherwise. The HUD hands it to the achievements."""
        if not getattr(self, "_story_changed", False):
            return None
        self._story_changed = False
        return watcher_lore.progress(self.memory)

    def poke(self, context=None):
        """The commander poked it (a hotkey). It looks up and says something:
        about where you are, how it's going, or just that it was poked. Poke
        it again and again and it gets testy."""
        now = self.clock()
        self._pokes = self._pokes + 1 if now - self._poked_at < 20 else 1
        self._poked_at = now
        if self._session_start is None:
            self._session_start = now
            self._counted_until = now
        if self._pokes >= 3:
            return self.consider("poked_again", force=True)
        # How it answers depends on how much it trusts you (5.6.1).
        trust = float(self.memory.get("trust", watcher_deeper.TRUST_START))
        if trust < watcher_deeper.TRUST_LOW:
            return self.consider("poked_wary", force=True)
        if trust >= watcher_deeper.TRUST_HIGH and self.random.random() < .4:
            warm = self.consider("poked_warm", force=True)
            if warm:
                return warm
        if self.random.random() < .5:
            known = dict(context or {})
            known.update(thoughts=self.memory.get("thoughts") or 0, sessions=self.memory.get("sessions") or 0,
                         deaths=self.memory.get("deaths") or 0, bond=self.bond(),
                         hours=int(self.memory.get("hours") or 0))
            for topic, fields in self.surroundings.choices(now, self.random, known):
                thought = self.consider(topic, fields, force=True)
                if thought:
                    return thought
        return self.consider("poked", force=True)

    def save_if_due(self, every=300.0):
        """Save what it has said every few minutes, so a crash or a killed
        app doesn't let it repeat itself next time (5.5.3.2)."""
        now = time.time()
        if getattr(self, "_unsaved", False) and now - getattr(self, "_saved_at", 0.0) >= every:
            self._unsaved = False
            self._saved_at = now
            self.save()

    # -- its own words (5.7.1, experimental) ---------------------------------
    def _reword(self, topic, key, script, fields, importance, headline_key, now):
        """With its mind awake, a thought goes to the model first and is said
        when its new words come back (follow_up): as written, if they break a
        rule or don't come back in time (a warning waits only moments). Its
        story is never sent. True when it's waiting for them."""
        llm = self.llm
        if llm is None or not llm.rewording() or not llm.ready():
            return False
        # A self-correction ([[...]]) is part of how it's said: kept as written
        # (but a sign-off becomes a recap of the session, written anew).
        if not watcher_llm.eligible(topic) or ("[[" in script and topic != "sign_off"):
            return False
        pending = self._llm_pending
        if pending is not None:
            if importance < 3:
                return True  # one thought at a time: this one stays unsaid
            pending["job"].cancelled = True
        nature = personality(self.config)
        bank = (WEARY if nature == "weary" and topic in WEARY else {}).get(topic) or TOPICS.get(topic, (0, []))[1]
        examples = []
        plain = plain_text(script)
        # A few lines for its tone, different each time (given always the
        # first three, it took "The drive is happy." and ended every long jump with it).
        templates = list(bank)
        self.random.shuffle(templates)
        for template in templates:
            try:
                line = template.format(**(fields or {}))
            except (KeyError, IndexError, ValueError):
                continue
            if line != plain and "[[" not in line:
                examples.append(line)
        facts = {name: value for name, value in (fields or {}).items()
                 if isinstance(value, (str, int, float)) and str(value).strip() and "{" + name + "}" in " ".join(bank)}
        # A named line (the once-a-session name) keeps the name; no other does.
        name = watcher_name.call_name(self.memory) or ""
        with self.lock:
            tonight = watcher_learning.recent(self.memory, 12, self._session_start) if topic == "sign_off" else []
        if tonight:
            # Signing off: a goodnight that recaps what really happened.
            job = llm.recap(tonight, str((fields or {}).get("summary") or ""), nature,
                            forbidden=self._unsayable_names())
            wait = max(RECAP_WAIT_S, job.wait)
        elif "[[" in script:
            return False
        else:
            with self.lock:
                said = [str(row[2]) for row in (self.memory.get("log") or [])
                        if isinstance(row, list) and len(row) > 2 and row[1] == topic][-3:]
            # Lines you liked for this moment lead its tone; ones you didn't, it steers clear of.
            liked, disliked = self._votes(topic)
            job = llm.reword(topic, plain, facts, (liked + examples)[:3], nature,
                             name=name if name and name in plain else "", forbidden=self._unsayable_names(plain),
                             said=said, avoid=disliked)
            # A warning never waits more than moments, even on the CPU.
            wait = watcher_llm.WARY_WAIT_S if MOODS.get(topic) == "wary" else job.wait
        self._llm_pending = {"job": job, "topic": topic, "key": key, "script": script, "at": now, "wait": wait,
                             "importance": importance, "headline_key": headline_key, "fields": dict(fields or {})}
        return True

    def _unsayable_names(self, allowed_text=""):
        """The commander's names (the ship's and a nickname), unless one may be said here."""
        row = watcher_name.record(self.memory)
        names = (str(row.get("known") or ""), str(row.get("nickname") or ""))
        return tuple(name for name in names if name and name not in str(allowed_text))

    # How often, at most, a thought of its own, by its Thoughts setting.
    OWN_REST_S = {"rare": 3600.0, "occasional": 1500.0, "chatty": 720.0}

    def _about_step(self, now):
        """5.7.1: what it knows of you (its notes and diary), condensed now and
        then into a few sentences, so its memory stays small and to the point."""
        llm = self.llm
        if (llm is None or not llm.ready() or self._about_pending is not None or self._diary_pending is not None
                or (self._about_tried is not None and now - self._about_tried < ABOUT_RETRY_S)):
            return
        with self.lock:
            due = watcher_knowing.about_due(self.memory, time.time())
        if due:
            self._about_tried = now
            lines, source = due
            self._about_pending = {"job": llm.condense(lines), "from": source}

    def own_paragraph(self, key, kind, text):
        """5.7.1: a page's paragraph (a night's flight log, Void Wrapped's
        verdict) in its own words once it has written them; None until then,
        or with its mind asleep, and the page shows the written one. Written
        one at a time in the background; on_words is told when one is ready."""
        text = str(text or "").strip()
        llm = self.llm
        if not text:
            return None
        source = f"{zlib.crc32(text.encode('utf-8')):08x}"
        with self.lock:
            kept = (self.memory.get("mind_words") or {}).get(key)
        if isinstance(kept, dict) and kept.get("from") == source:
            return kept.get("text") or None
        if (llm is None or not llm.rewording() or not llm.ready() or self._paragraph_pending is not None
                or (key, source) in self._paragraphs_refused):
            return None
        self._paragraph_pending = key

        def done(job):
            with self.lock:
                if job.ok:
                    words = self.memory.setdefault("mind_words", {})
                    words.pop(key, None)
                    words[key] = {"from": source, "text": job.text, "at": round(time.time())}
                    for old in list(words)[:-MIND_WORDS_KEPT]:
                        del words[old]
                else:
                    self._paragraphs_refused.add((key, source))
                self._paragraph_pending = None
            if job.ok:
                self._unsaved = True
                if callable(self.on_words):
                    self.on_words(key)

        llm.paragraph(kind, text, {}, personality(self.config), forbidden=self._unsayable_names(text), on_done=done)
        return None

    def _diary_step(self, now):
        """5.7.1: with its own words on, a diary entry for a finished session
        it watched, written quietly in the background. Not its story: that
        stays as written."""
        llm = self.llm
        config = self.config or {}
        if llm is None or not llm.ready():
            return
        if config.get("watcher_llm_diary", True) and self._diary_pending is None:
            with self.lock:
                due = watcher_learning.diary_due(self.memory, self._session_start)
                if due:
                    watcher_learning.tried(self.memory, due[0])
            if due:
                session, lines = due
                first = next((row.get("t") for row in self.memory.get("happened") or []
                              if isinstance(row, dict) and row.get("s") == session), None)
                when = datetime.fromtimestamp(float(first or session or now)).strftime("%d %B")
                self._diary_pending = {"job": llm.write_diary(lines, when, personality(config),
                                                              forbidden=self._unsayable_names()),
                                       "session": session, "when": float(first or now)}

    def _mind_step(self, now):
        """5.7.1: with its own words on, now and then a thought of its own
        about what's really been happening (never its own past or story)."""
        llm = self.llm
        config = self.config or {}
        if llm is None or not llm.ready() or self._diary_pending is not None:
            return
        setting = FREQUENCIES.get(frequency(config))
        rest = self.OWN_REST_S.get(frequency(config))
        if (not config.get("watcher_llm_own_thoughts", True) or setting is None or rest is None
                or self._own_pending is not None or self._llm_pending is not None or self._talk_pending is not None
                or self._question or self._in_danger or now - self._session_start < 120
                or now - self._last_spoke < max(60.0, setting["gap"]) or self._said_recently("mind_own", rest)
                or self.random.random() > .5):
            return
        facts = {}
        if callable(self.facts_provider):
            try:
                facts.update({key: value for key, value in (self.facts_provider() or {}).items() if value not in (None, "")})
            except Exception:
                pass
        with self.lock:
            lately = watcher_learning.recent(self.memory, 8, self._session_start)
            remembered = watcher_learning.diary(self.memory, 2)
            said = [str(row[2]) for row in (self.memory.get("log") or [])[-4:] if isinstance(row, list) and len(row) > 2]
            knows = watcher_knowing.for_prompt(self.memory, 8)
        if not lately and not remembered:
            return  # nothing real to think about yet
        name = watcher_name.may_name(self.memory, self._session_start) or ""
        self._own_pending = {"job": llm.own_thought(facts, lately, remembered, said, personality(config), name=name,
                                                    forbidden=self._unsayable_names(name), knows=knows), "at": now}
        with self.lock:
            # Rested from now, said or not, so a refused thought isn't retried at once.
            self.memory["said"].append(["mind_own", now])

    def _own_words_due(self):
        """A thought or a reply whose words have come back (or waited long
        enough): said now. None when there's nothing to say yet."""
        now = self.clock()
        diary = self._diary_pending
        if diary is not None and (diary["job"].done.is_set() or now - diary["job"].made > diary["job"].wait * 2):
            self._diary_pending = None
            if diary["job"].ok:
                with self.lock:
                    watcher_learning.add_diary(self.memory, diary["session"], diary["job"].text, diary["when"])
                self._unsaved = True
        notes = self._notes_pending
        if notes is not None and (notes["job"].done.is_set() or now - notes["job"].made > notes["job"].wait * 2):
            self._notes_pending = None
            if notes["job"].ok:
                kept = 0
                for line in watcher_knowing.parse_notes(notes["job"].text):
                    ok, line, _reason = watcher_llm.check(line, (notes["said"],), 160)
                    if ok:
                        with self.lock:
                            kept += watcher_knowing.add_note(self.memory, line, time.time())
                if kept:
                    self._unsaved = True
        about = self._about_pending
        if about is not None and (about["job"].done.is_set() or now - about["job"].made > about["job"].wait * 2):
            self._about_pending = None
            if about["job"].ok:
                with self.lock:
                    self.memory["about_you"] = {"text": about["job"].text, "at": round(time.time()), "from": about["from"]}
                self._unsaved = True
        own_pending = self._own_pending
        if own_pending is not None and (own_pending["job"].done.is_set() or now - own_pending["at"] > own_pending["job"].wait):
            self._own_pending = None
            job = own_pending["job"]
            if job.done.is_set() and job.ok and not self._in_danger:
                thought = self._utter("mind_own", "mind_own", job.text, now)
                thought["own_words"] = True
                self._said_in_own_words("mind_own", job.text)
                thought["importance"] = 1
                name = watcher_name.may_name(self.memory, self._session_start)
                if name and name in job.text:
                    watcher_name.mark_used(self.memory, self._session_start)
                return thought
        talk = self._talk_pending
        if talk is not None and (talk["job"].done.is_set() or now - talk["at"] > talk["job"].wait):
            self._talk_pending = None
            job = talk["job"]
            reply = job.text if job.done.is_set() and job.ok else self.random.choice(watcher_llm.TALK_FALLBACK)
            # 5.7.1: anything you said about yourself, kept as a note.
            if (self.llm is not None and self._notes_pending is None and talk.get("said")
                    and watcher_knowing.tells_something(talk["said"])):
                with self.lock:
                    known = [row["text"] for row in watcher_knowing.notes(self.memory)][-10:]
                self._notes_pending = {"job": self.llm.take_notes(talk["said"], known), "said": talk["said"]}
            return self._reply(reply, own=job.ok)
        pending = self._llm_pending
        if pending is None:
            return None
        job = pending["job"]
        if not job.done.is_set() and now - pending["at"] < pending.get("wait", watcher_llm.REWORD_WAIT_S):
            return None
        self._llm_pending = None
        job.cancelled = True
        own = job.done.is_set() and job.ok
        words = noticed_in(job.text, pending["fields"]) if own else pending["script"]
        thought = self._utter(pending["topic"], pending["key"], words, now)
        thought["own_words"] = own
        if own:
            self._said_in_own_words(pending["topic"], plain_text(words))
        if pending["headline_key"]:
            with self.lock:
                self.memory["said"].append([pending["headline_key"], now])
        self._maybe_afterthought(pending["topic"], pending["importance"], plain_text(words), now)
        return thought

    def talk(self, text, voice=False):
        """You said something to it on the Watcher page (5.7.1), typed or
        spoken. Its reply appears beside the orb, and in the conversation on
        the page."""
        words = " ".join(str(text or "").split())[:400]
        llm = self.llm
        # Waking (a model change): asked now, answered once it's awake.
        if not words or llm is None or not llm.listening():
            return False
        with self.lock:
            history = self.memory.setdefault("talk", [])
            history.append({"at": round(time.time(), 1), "you": words, "it": "", **({"voice": True} if voice else {})})
            del history[:-50]
            recent = [dict(row) for row in history[-(watcher_llm.HISTORY + 1):-1]]
        self._unsaved = True
        done = None
        if callable(self.action_provider):
            try:
                done = self.action_provider(words)
            except Exception:
                done = None
        own = done or watcher_llm.deflection(words, self.random)
        if own:
            self._reply(str(own), own=False)
            return True
        lookup = []
        if callable(self.lookup_provider):
            try:
                lookup = [str(line) for line in self.lookup_provider(words) or () if line][:watcher_copilot.LOOKUP_LIMIT]
            except Exception:
                lookup = []
        facts = {}
        provider = self.facts_provider
        if callable(provider):
            try:
                facts.update({key: value for key, value in (provider() or {}).items() if value not in (None, "")})
            except Exception:
                pass
        facts["sessions together"] = int(self.memory.get("sessions") or 0)
        facts["hours together"] = int(float(self.memory.get("hours") or 0))
        name = watcher_name.may_name(self.memory, self._session_start) or ""
        if self._talk_pending is not None:
            self._talk_pending["job"].cancelled = True
        with self.lock:
            lately = watcher_learning.recent(self.memory, 10)
            remembered = watcher_learning.diary(self.memory, 3)
            knows = watcher_knowing.for_prompt(self.memory)
            story = watcher_knowing.story_told(self.memory)
        liked, disliked = self._votes("talk")
        job = llm.talk(words, facts, recent, personality(self.config), name=name, forbidden=self._unsayable_names(name),
                       lately=lately, remembered=remembered, knows=knows, story=story, lookup=lookup,
                       liked=liked, avoid=disliked)
        self._talk_pending = {"job": job, "at": self.clock(), "said": words}
        return True

    def _reply(self, words, own=True):
        with self.lock:
            history = self.memory.setdefault("talk", [])
            if history and not history[-1].get("it"):
                history[-1]["it"] = words
            count = len(history)
        thought = self._utter("talk", f"talk:{count}", words, self.clock())
        thought["importance"] = 3  # an answer to you is always said aloud
        thought["own_words"] = own
        if own:
            self._said_in_own_words("talk", words)
        if own and watcher_name.may_name(self.memory, self._session_start) and \
                watcher_name.may_name(self.memory, self._session_start) in words:
            watcher_name.mark_used(self.memory, self._session_start)
        return thought

    def talk_waiting(self):
        return self._talk_pending is not None

    # -- your votes on its words (5.7.1) ------------------------------------------
    def _said_in_own_words(self, topic, text):
        """A line it said in its own words, kept (the last few) for you to rate."""
        with self.lock:
            rows = self.memory.setdefault("own_said", [])
            rows.append({"at": round(time.time(), 1), "topic": str(topic), "text": str(text)})
            del rows[:-OWN_SAID_KEPT]
        self._unsaved = True

    def rate(self, text, vote, topic=""):
        """👍 ("up"), 👎 ("down") or neither ("clear") on a line of its own.
        Liked lines become its tone for that moment; disliked ones it steers
        away from (and their phrases count as copying)."""
        text = " ".join(str(text or "").split())
        if not text or vote not in ("up", "down", "clear"):
            return False
        with self.lock:
            if not topic:
                topic = next((row.get("topic", "") for row in reversed(self.memory.get("own_said") or [])
                              if row.get("text") == text), "")
            for key in ("liked", "disliked"):
                self.memory[key] = [row for row in self.memory.get(key) or [] if row.get("text") != text]
            if vote != "clear":
                rows = self.memory.setdefault("liked" if vote == "up" else "disliked", [])
                rows.append({"at": round(time.time(), 1), "topic": str(topic), "text": text})
                del rows[:-VOTES_KEPT]
        self._unsaved = True
        return True

    def _votes(self, topic, limit=2):
        """(liked, disliked) lines for a moment, newest last."""
        with self.lock:
            liked = [row["text"] for row in self.memory.get("liked") or [] if row.get("topic") == topic][-limit:]
            disliked = [row["text"] for row in self.memory.get("disliked") or [] if row.get("topic") == topic][-3:]
        return liked, disliked

    def debug_state(self):
        """What it's doing right now, for the live debugger: the thought on
        screen, what's waiting for its words, and how big its memory is."""
        now = self.clock()
        waiting = {}
        for name in ("llm", "talk", "own", "diary", "notes", "about"):
            pending = getattr(self, f"_{name}_pending", None)
            if pending is not None:
                job = pending.get("job")
                waiting[name] = {"kind": getattr(job, "kind", ""), "topic": pending.get("topic", ""),
                                 "age_s": round(now - pending.get("at", now), 1) if "at" in pending
                                 else round(time.monotonic() - getattr(job, "made", time.monotonic()), 1)}
        if self._paragraph_pending:
            waiting["paragraph"] = {"kind": "paragraph", "topic": self._paragraph_pending, "age_s": None}
        thought = self.thought or {}
        with self.lock:
            sizes = {key: len(self.memory.get(key) or ()) for key in
                     ("said", "log", "happened", "diary", "talk", "told_me", "taught", "mind_words", "postcards", "lore")}
            feeling = watcher_deeper.words_for(self.memory)
        return {
            "session_s": round(now - self._session_start) if self._session_start else None,
            "quiet_s": round(now - self._last_spoke) if self._last_spoke else None,
            "thought": {key: thought.get(key) for key in ("topic", "text", "heading", "mood", "importance", "own_words")}
            if thought else None,
            "showing": bool(thought) and now < float(thought.get("until") or 0),
            "question": bool(self._question), "in_danger": bool(self._in_danger),
            "waiting": waiting, "feeling": feeling, "memory": sizes,
            "nature": personality(self.config), "thoughts": frequency(self.config),
        }

    def follow_up(self):
        """The second beat of a thought, when it is due (the HUD asks often);
        or (5.7.1) a thought or reply whose own words are ready."""
        own = self._own_words_due()
        if own:
            return own
        pending = self._afterthought
        if not pending or self.clock() < pending["at"]:
            return None
        self._afterthought = None
        if not self.thought or self.thought["id"] != pending["after"] or self.clock() >= self.thought["until"]:
            return None
        return self.consider("afterthought", force=True)

    def keep_postcard(self, card):
        """A postcard taken (5.5.3.7): kept, to be brought up later."""
        with self.lock:
            count = watcher_postcards.keep(self.memory, card, self.clock())
        self._unsaved = True
        return count

    def current(self):
        """The thought on screen, if any."""
        if self.thought and self.clock() < self.thought["until"]:
            return dict(self.thought)
        self.thought = None
        return None

    # -- what happens ------------------------------------------------------------
    def awake(self):
        """The first live journal event: greet, if no LoadGame did."""
        if self._session_start is None:
            return self.session_start()
        return None

    def session_start(self):
        now = self.clock()
        died_since = self.memory.get("last_death") and (
            not self._session_start or float(self.memory["last_death"]) > float(self._session_start))
        if self._session_start and now - self._session_start < 1800 and not died_since                 and now - (getattr(self, "_last_event_at", None) or now) <= 900:
            # A reload mid-session (or a second sign of life): already greeted.
            return None
        self._session_start = now
        self._counted_until = now
        self._record_said = set()
        self.surroundings.reset_session()
        last = self.memory.get("last_seen")
        previous_start = self.memory.get("session_started")
        with self.lock:
            self.memory["sessions"] = int(self.memory.get("sessions") or 0) + 1
            self.memory["session_started"] = now
            watcher_name.count_session(self.memory, now)
            # 5.6.1: when it first woke for you; how long you were away moves
            # its mood; a dream from last time waits to be told.
            if not self.memory.get("first_seen"):
                log = self.memory.get("log") or []
                self.memory["first_seen"] = float(log[0][0]) if log and isinstance(log[0], list) else now
            if last:
                away_days = (now - float(last)) / 86400.0
                watcher_deeper.settle(self.memory, away_days)
                watcher_deeper.shift(self.memory, "away_long" if away_days > 7 else "back_soon" if away_days < 1 else "")
        self._queue_session_extras(now)
        hour = datetime.fromtimestamp(now).hour
        clock = datetime.fromtimestamp(now).strftime("%H:%M")
        # Died since the last session began: that comes first.
        death = self.memory.get("last_death")
        if death and (not previous_start or float(death) > float(previous_start)):
            return self.consider("after_death", force=True)
        if not last:
            return self.consider("greet_new", force=True)
        if self.bond() >= 2 and self.random.random() < .35:
            greeting = self.consider("greet_bond", {"sessions": int(self.memory.get("sessions") or 0)}, force=True)
            if greeting:
                return greeting
        away = now - float(last)
        if away > 2 * 86400:
            return self.consider("greet_away", {"away": _away_text(away)}, force=True)
        if hour < 5:
            return self.consider("greet_night", {"clock": clock})
        if away < 3600:
            return self.consider("greet_soon")
        return None

    def seen(self):
        with self.lock:
            self.memory["last_seen"] = self.clock()

    def observe(self, event, raw=None):
        """One journal event. Returns a new thought, or None. Every event
        also teaches it a little about how you play (5.5.4)."""
        raw = raw if isinstance(raw, dict) else {}
        with self.lock:
            milestone = watcher_habits.observe(self.memory, event, raw)
            # 5.7.1: the name the ship writes (and a new one); what it says of you;
            # what it has seen you do, for its diary and its own words.
            old_name = watcher_name.observe(self.memory, event, raw)
            if watcher_learning.record(self.memory, event, raw, self._session_start, self.clock()):
                self._unsaved = True
        if old_name:
            self._say_next.append(("name_renamed", {"old": old_name, "name": watcher_name.record(self.memory)["known"]}))
        fact = watcher_name.fact_fields(event, raw)
        if fact and not self._said_recently(fact[0], watcher_name.FACT_REST_S) \
                and fact[0] not in {topic for topic, _fields in self._say_next}:
            self._say_next.append(fact)
        thought = self._observe(event, raw)
        # A milestone is rare (10, 50, 100 …): it outranks a passing remark.
        if milestone and self._session_start is not None and int((thought or {}).get("importance") or 0) < 2:
            thought = self.consider("habit_milestone", watcher_habits.milestone_fields(*milestone), force=True) or thought
        return thought

    def _observe(self, event, raw):
        raw = raw if isinstance(raw, dict) else {}
        now = self.clock()
        # A break of a quarter of an hour or more ends the session: the
        # next sign of life starts a new one (long-session talk restarts).
        last_event, self._last_event_at = getattr(self, "_last_event_at", None), now
        if self._session_start is not None and last_event is not None and now - last_event > 900:
            self._session_start = None
        self.surroundings.observe(
            event, raw,
            rarity=rarity({"planet_class": raw.get("PlanetClass")}) if event == "Scan" else None,
            green=event == "CodexEntry" and is_green_giant_codex(raw),
        )
        if event == "Disembark":
            self._on_foot = True
        elif event in {"Embark", "LoadGame", "Resurrect"}:
            self._on_foot = False
            self._foot_health = None
            if self._foot_danger:
                self._foot_danger = False
                if event == "Embark":
                    return self.consider("foot_danger_over")
        if event in {"LoadGame", "Resurrect", "RepairAll", "Docked"}:
            self._hull_warned = 0
        if event in {"LoadGame"}:
            return self.session_start()
        if self._session_start is None and event == "Died":
            self._session_start = now  # the death matters more than a hello
        elif self._session_start is None and event not in {"Shutdown", "Fileheader", "Commander"}:
            greeting = self.awake()
            if greeting:
                return greeting
        self._observe_deeper(event, raw, now)
        if event == "Shutdown":
            self.seen()
            self._dream()
            self.save()
            return None
        if event == "Died":
            with self.lock:
                self.memory["deaths"] = int(self.memory.get("deaths") or 0) + 1
                self.memory["last_death"] = now
            self.save()
            on_foot = self._on_foot
            self._in_danger = self._foot_danger = self._shields_down = False
            return self.consider("died_foot" if on_foot else "died", force=True)
        handled, thought = self._combat(event, raw, now)
        if handled:
            return thought
        if event in {"FSDJump", "SupercruiseEntry", "Docked"} and self._in_danger:
            self._in_danger = self._shields_down = False
            return self.consider("danger_over")
        # Something in the game that touches its past (5.5.3.5). Since 5.5.4
        # the distance you've flown in all counts for the far ones too.
        echo = watcher_lore.echo_for(event, raw)
        if not echo and event == "FSDJump":
            known = self.memory.get("echoes") or {}
            reached = [topic for topic in watcher_lore.distance_echoes(watcher_habits.habits(self.memory)["ly"])
                       if topic not in known]
            echo = reached[0] if reached else None
        if echo:
            with self.lock:
                found = self.memory.setdefault("echoes", {})
                times = int((found.get(echo) or [0])[0] or 0)
                if not times:
                    self._story_changed = True  # a new kind found (achievements, Book Two)
                found[echo] = [times + 1, now]
            thought = self.consider(echo)
            if thought:
                if event == "FSDJump":
                    self._last_interesting = now
                return thought
        if event == "FSDJump":
            self._last_interesting = now
            fields = {"system": raw.get("StarSystem") or "Here"}
            try:
                distance = float(raw.get("JumpDist") or 0)
            except (TypeError, ValueError):
                distance = 0
            if distance >= 50:
                return self.consider("jump_long", {**fields, "dist": f"{distance:.1f}"})
            star = str(raw.get("StarClass") or "").strip()
            if star:
                fields["star"] = star
            return self.consider("arrival", fields)
        if event == "FuelScoop":
            return self.consider("scooped")
        if event == "FSSAllBodiesFound":
            return self.consider("fss_complete", {"system": raw.get("SystemName") or "this system"})
        if event == "SAAScanComplete":
            body = raw.get("BodyName") or "That world"
            try:
                efficient = int(raw.get("ProbesUsed") or 99) <= int(raw.get("EfficiencyTarget") or 0)
            except (TypeError, ValueError):
                efficient = False
            return self.consider("mapped_efficient" if efficient else "mapped", {"body": body})
        if event == "ScanOrganic" and str(raw.get("ScanType") or "").casefold() == "analyse":
            species = raw.get("Species_Localised") or raw.get("Genus_Localised")
            return self.consider("analysed", {"species": species}) if species else None
        if event == "Touchdown" and raw.get("PlayerControlled", True):
            return self.consider("touchdown")
        # Flying and walking about (5.5.3.2).
        if event == "JetConeBoost":
            return self.consider("jet_boost")
        if event == "HeatWarning":
            return self.consider("heat_warning")
        if event == "EscapeInterdiction":
            return self.consider("interdiction_escaped")
        if event in LOADING_EVENTS:
            self._loaded_at = now
        if event == "LaunchSRV":
            self._srv_full_said = False
            kind = watcher_idle.vehicle_kind(raw)
            return self.consider(f"launch_{kind}" if kind in watcher_idle.SRV_KINDS else "srv_launch")
        if event in ("LaunchFighter", "LaunchVessel") and raw.get("PlayerControlled", True):
            return self.consider(f"launch_{watcher_idle.vehicle_kind(raw)}")
        if event == "Loadout":
            try:
                self._cargo_capacity = int(raw.get("CargoCapacity") or 0)
            except (TypeError, ValueError):
                pass
        if event == "Cargo":
            return self._cargo_moment(raw, now)
        if event == "ProspectedAsteroid":
            return self._prospect_moment(raw)
        if event == "AsteroidCracked":
            return self.consider("cracked")
        if event == "ApproachSettlement":
            name = raw.get("Name_Localised") or raw.get("Name")
            if name and not str(name).startswith("$"):
                return self.consider("settlement_seen", {"settlement": name})
            return None
        if event == "BookTaxi" or (event == "Embark" and raw.get("Taxi")):
            return self.consider("taxi_ride")
        if event == "CarrierJump":
            return self.consider("carrier_jump", {"system": raw.get("StarSystem") or "a new system"})
        if event == "Undocked":
            return self.consider("undocked")
        if event == "Disembark" and not raw.get("OnStation"):
            return self.consider("on_foot")
        if event == "MissionCompleted":
            return self.consider("mission_done")
        if event == "Bounty":
            reward = raw.get("TotalReward") or raw.get("Reward")
            try:
                return self.consider("bounty", {"reward": f"{int(reward):,}"}) if reward else None
            except (TypeError, ValueError):
                return None
        if event == "MiningRefined":
            material = raw.get("Type_Localised") or raw.get("Type")
            topic = "mined_surface" if self.surroundings.srv else "mined"
            self._mined_at = now
            return self.consider(topic, {"material": material}) if material else None
        if event == "Scan":
            # The arrival star's scan says whether anyone charted the system.
            if raw.get("StarType") and raw.get("WasDiscovered") is False and not raw.get("DistanceFromArrivalLS"):
                self._first_streak += 1
                self._last_interesting = now
                return self.consider("undiscovered_system")
            rare, rare_label = rarity({"planet_class": raw.get("PlanetClass")})
            if rare:
                self._last_interesting = now
                return self.consider("rare_world", {"body": raw.get("BodyName") or "That world",
                                                    "kind": rare_label.lower()})
            firsts = self.surroundings.firsts
            best = int((self.memory.get("records") or {}).get("firsts") or 0)
            if firsts > best:
                with self.lock:
                    self.memory.setdefault("records", {})["firsts"] = firsts
                if best >= 5 and "firsts" not in self._record_said:
                    thought = self.consider("record_firsts", {"count": firsts})
                    if thought:
                        self._record_said.add("firsts")
                        return thought
            if raw.get("WasDiscovered") is False and (raw.get("PlanetClass") or raw.get("StarType")):
                self._first_streak += 1
                self._last_interesting = now
                if self._first_streak >= 4 and self._first_streak % 2 == 0:
                    return self.consider("first_discovery_streak", {"count": self._first_streak})
            elif raw.get("WasDiscovered") is True:
                self._first_streak = 0
            planet = str(raw.get("PlanetClass") or "").casefold()
            terraformable = raw.get("TerraformState") == "Terraformable"
            if planet in watcher_worlds.KIND_WORDS or terraformable:
                # The worlds worth stopping for (5.5.3.9): each in its own words.
                self._last_interesting = now
                fields = {"body": raw.get("BodyName") or "That world"}
                try:
                    fields["temp"] = f"{float(raw['SurfaceTemperature']) - 273.15:,.0f}°C"
                except (KeyError, TypeError, ValueError):
                    pass
                kind = watcher_worlds.KIND_WORDS.get(planet) or ("A terraformable world" if terraformable else "")
                if raw.get("WasDiscovered") is False and kind:
                    thought = self.consider("world_first", dict(fields, kind=kind, kind_l=kind[:1].lower() + kind[1:]))
                    if thought:
                        return thought
                topic = {"earthlike body": "world_earthlike", "water world": "world_water",
                         "ammonia world": "world_ammonia"}.get(planet, "world_terraformable")
                return self.consider(topic, fields)
            return None
        if event == "CodexEntry" and is_green_giant_codex(raw):
            self._last_interesting = now
            return self.consider("green_giant", {"system": raw.get("System") or "this system"})
        if event == "CodexEntry" and raw.get("IsNewEntry"):
            self._last_interesting = now
            return self.consider("codex_logged", {"name": raw.get("Name_Localised") or "That one"})
        if event in {"SellExplorationData", "MultiSellExplorationData", "SellOrganicData"}:
            total = raw.get("TotalEarnings") or raw.get("TotalSale") or 0
            try:
                total = int(total)
            except (TypeError, ValueError):
                total = 0
            if total >= 10_000_000:
                return self.consider("big_sale", {"credits": f"{total:,}"})
            return None
        if event == "Promotion":
            # 5.7.1: by its name: "Elite, in exploration".
            rank = next((ranks.said(key, value) or f"{key} rank {value}" for key, value in raw.items()
                         if key not in {"timestamp", "event"}), None)
            return self.consider("promotion", {"rank": rank} if rank else {})
        if event == "Docked":
            return self.consider("docked_home")
        return None

    def note(self, kind, fields=None):
        """Something Void Compass noticed (not a journal line)."""
        fields = dict(fields or {})
        if kind == "achievement":
            return self.consider("achievement", fields)
        if kind == "revisit":
            return self.consider("revisit", fields)
        if kind in {"record_far", "record_jump"}:
            # Once a session for each: a new record every jump would be noise.
            if kind in self._record_said:
                return None
            thought = self.consider(kind, fields)
            if thought:
                self._record_said.add(kind)  # said: not again this session
            return thought
        if kind == "anniversary":
            today = datetime.fromtimestamp(self.clock()).strftime("%Y-%m-%d")
            if self.memory.get("anniversary_said") == today:
                return None
            with self.lock:
                self.memory["anniversary_said"] = today
            return self.consider("anniversary", fields, force=True)
        if kind in {"capsule", "capsule_early", "capsule_shared", "constellation_named"}:
            # A note you left (or not yet); a constellation finished: said
            # whatever the hour (5.5.3.7).
            return self.consider(kind, fields, force=True)
        if kind == "on_this_day":
            today = datetime.fromtimestamp(self.clock()).strftime("%Y-%m-%d")
            if self.memory.get("on_this_day_said") == today:
                return None
            thought = self.consider("on_this_day", fields, force=True)
            if thought:
                with self.lock:
                    self.memory["on_this_day_said"] = today
            return thought
        if kind == "hidden":
            self._hidden_at = self.clock()
            return None
        if kind == "shown":
            hidden, self._hidden_at = self._hidden_at, None
            if hidden is not None and self.clock() - hidden >= 10 and self._session_start is not None:
                return self.consider("unhidden")
            return None
        if kind == "moved":
            return self.consider("moved") if self._session_start is not None else None
        if kind == "sign_off":
            # The end of a session: the Captain's Log's own figures.
            summary = str(fields.get("summary") or "")
            # Lines quoting {hours} are skipped when the session was too short.
            words = {"hours": fields["hours"]} if fields.get("hours") else {}
            if summary:
                thought = self.consider("sign_off", {**words, "summary": summary}, force=True)
            else:
                thought = self.consider("sign_off_quiet", words, force=True)
            # Saved at once: the game has closed, and Void Compass may be next
            # (5.5.3.5; it waited for the periodic save, up to 5 minutes, so a
            # quick close lost the sign-off from its memory).
            self.save()
            return thought
        if kind.startswith("hatchling_") and kind in IMPORTANCE:
            return self.consider(kind, fields, force=kind in {"hatchling_grown", "hatchling_trick"})
        if kind.startswith("expedition_") and kind in IMPORTANCE:
            # An expedition's milestones come once each (the expedition
            # remembers them), so they're said whatever the hour.
            return self.consider(kind, fields, force=True)
        if kind == "codex_new":
            body = str(fields.get("body") or "")
            if not body or body in self._codex_bodies:
                return None
            self._codex_bodies.add(body)
            return self.consider("codex_new", fields)
        if kind == "new_region":
            region = str(fields.get("region") or "")
            if not region:
                return None
            with self.lock:
                known = region in self.memory["regions"]
                if not known:
                    self.memory["regions"].append(region)
            return None if known else self.consider("new_region", fields)
        return None

    # -- its voice (5.5.4) ------------------------------------------------------
    def find_voice(self):
        """While its voice is on, count the minutes, and say the next thing
        about finding it when one is due (whatever its Thoughts setting: the
        commander switched the voice on to hear it)."""
        now = self.clock()
        if not self.voice_active or self._session_start is None:
            self._voice_counted = None
            return None
        if self._voice_counted is not None:
            # A long gap (the app asleep, the game paused) counts as a minute at most.
            with self.lock:
                watcher_voice_lore.add_minutes(self.memory, min(60.0, now - self._voice_counted) / 60.0)
        self._voice_counted = now
        if self._in_danger or now - self._last_spoke < 20:
            return None
        with self.lock:
            due = watcher_voice_lore.due(self.memory)
            if due:
                watcher_voice_lore.mark_told(self.memory, due[0], now)
        if not due:
            return None
        self._unsaved = True
        return self._utter("voice_found", f"voice:{due[0]}", due[1], now)

    def voice_stage(self):
        return watcher_voice_lore.stage(self.memory)

    def spoken_words(self, thought):
        """What of a thought its voice says out loud, as far as it has found it."""
        if not thought:
            return ""
        if thought.get("topic") in ("voice_found", "relay"):
            words = thought.get("text") or ""
        else:
            words = watcher_voice_lore.spoken_part(thought.get("text"), self.voice_stage())
        # 5.7.1: your name as you'd have it said, not as it's spelled.
        for shown, said in watcher_name.spoken(self.memory).items():
            if shown and said and shown != said:
                words = words.replace(shown, said)
        return words

    # -- mining (5.5.12) -------------------------------------------------------
    def _prospect_moment(self, raw):
        motherlode = raw.get("MotherlodeMaterial_Localised") or raw.get("MotherlodeMaterial")
        if motherlode:
            return self.consider("motherlode", {"material": material_name(motherlode)})
        materials = [row for row in raw.get("Materials") or () if isinstance(row, dict)]
        best = max(materials, key=lambda row: float(row.get("Proportion") or 0), default=None)
        share = float((best or {}).get("Proportion") or 0)
        if best and share >= RICH_ROCK_PCT:
            return self.consider("prospected_rich", {"material": material_name(best.get("Name"), best.get("Name_Localised")),
                                                     "percent": f"{share:.0f}%"})
        return None

    def _cargo_moment(self, raw, now):
        """A full hold, said once a load: an SRV's as you fill it, the ship's
        soon after you loaded something (mining has its own words)."""
        try:
            count = int(raw.get("Count") or 0)
        except (TypeError, ValueError):
            return None
        vessel = str(raw.get("Vessel") or "").casefold()
        if vessel == "srv":
            kind = self.surroundings.vehicle
            capacity = SRV_HOLD_T.get(kind)
            if not capacity:
                return None
            full = count >= capacity
            said, self._srv_full_said = getattr(self, "_srv_full_said", False), full
            if not full or said:
                return None
            return self.consider("rhino_full") if kind == "rhino" else self.consider("srv_full", {"srv": kind.capitalize()})
        capacity = getattr(self, "_cargo_capacity", 0)
        if vessel != "ship" or not capacity:
            return None
        full = count >= capacity
        said, self._hold_full_said = getattr(self, "_hold_full_said", False), full
        if not full or said or now - getattr(self, "_loaded_at", 0.0) > 600:
            return None
        mining = now - getattr(self, "_mined_at", 0.0) < 600
        return self.consider("hold_full_mining" if mining else "hold_full")

    def learn(self, context):
        """What the deck knows that a restart hid from the journal: the
        vehicle you're in and your ship's hold (5.5.12)."""
        context = context or {}
        kind = str(context.get("vehicle") or "").casefold()
        if kind in SRV_HOLD_T or kind in ("nomad", "fighter"):
            if not self.surroundings.vehicle:
                self.surroundings.vehicle = kind
                self.surroundings.srv = self.surroundings.srv or kind in SRV_HOLD_T
        try:
            capacity = int(context.get("cargo_capacity") or 0)
        except (TypeError, ValueError):
            capacity = 0
        if capacity > 0:
            self._cargo_capacity = capacity

    def _combat(self, event, raw, now):
        """(handled, thought) for a moment in a fight (5.5.7): attacks,
        shields, the hull, kills, an interdiction given in to, combat zones."""
        if event == "Interdicted" or event == "UnderAttack" or (event == "ShieldState" and raw.get("ShieldsUp") is False):
            self._in_danger, self._danger_at, self._last_interesting = True, now, now
            if event == "ShieldState":
                self._shields_down = True
            if event == "Interdicted" and raw.get("Submitted"):
                return True, self.consider("interdiction_submitted")
            return True, self.consider("danger")
        if event == "ShieldState" and raw.get("ShieldsUp"):
            was_down, self._shields_down = self._shields_down, False
            return True, (self.consider("shields_back") if was_down else None)
        if event == "HullDamage":
            if raw.get("Fighter") or raw.get("PlayerPilot") is False:
                return True, None
            try:
                hull = max(0.0, min(1.0, float(raw.get("Health"))))
            except (TypeError, ValueError):
                return True, None
            self._in_danger, self._danger_at, self._last_interesting = True, now, now
            level = 2 if hull <= .25 else 1 if hull <= .6 else 0
            if level <= self._hull_warned:
                return True, None
            self._hull_warned = level
            return True, self.consider("hull_critical" if level == 2 else "hull_damage", {"hull": int(round(hull * 100))})
        if event in {"FactionKillBond", "PVPKill", "CapShipBond"} or (event == "Bounty" and self._on_foot):
            fields = {}
            try:
                reward = int(raw.get("Reward") or raw.get("TotalReward") or 0)
            except (TypeError, ValueError):
                reward = 0
            if reward:
                fields["reward"] = f"{reward:,}"
            faction = raw.get("AwardingFaction_Localised") or raw.get("AwardingFaction")
            if faction and not str(faction).startswith("$"):
                fields["faction"] = str(faction)
            if raw.get("Victim"):
                fields["victim"] = str(raw["Victim"])
            if self._in_danger:
                self._danger_at = now  # still fighting
            if self._foot_danger:
                self._foot_hurt_at = now
            return True, self.consider("foot_win" if self._on_foot else "combat_win", fields)
        if event == "SupercruiseDestinationDrop" and "warzone" in str(raw.get("Type") or "").casefold():
            self._in_danger, self._danger_at, self._last_interesting = True, now, now
            return True, self.consider("combat_zone")
        if event == "BookDropship":
            self._last_interesting = now
            return True, self.consider("dropship")
        return False, None

    def _calm(self, now):
        """The fight is over (5.5.7): no attack for a while, shields up and
        the game's danger flag clear; on foot, no new hurt for a while."""
        if self._in_danger and now - self._danger_at >= CALM_S and not self._status_danger and (
                not self._shields_down or now - self._danger_at >= 5 * CALM_S):
            self._in_danger = self._shields_down = False
            return self.consider("danger_over")
        if self._foot_danger and now - self._foot_hurt_at >= CALM_S and not self._low_health:
            self._foot_danger = False
            return self.consider("foot_danger_over")
        return None

    def _foot_vitals(self, health, low_health, now):
        """On foot the game logs no attack: a falling health bar is the fight."""
        try:
            health = None if health is None else max(0.0, min(1.0, float(health)))
        except (TypeError, ValueError):
            health = None
        last = self._foot_health
        if health is not None:
            self._foot_health = health
        self._low_health = bool(low_health)
        hurt = self._low_health or (health is not None and last is not None and last - health >= .1)
        if not hurt:
            return None
        self._foot_hurt_at = self._last_interesting = now
        if self._foot_danger:
            return None
        self._foot_danger = True
        return self.consider("foot_danger", {"health": int(round(health * 100))} if health is not None else {})

    def vitals(self, fuel_percent=None, scooping=False, health=None, low_health=False, on_foot=None, in_danger=False,
               vehicle=""):
        """Status: worry about fuel once, until it is topped up; feel a fight
        on foot by the health bar (5.5.7); and the game's own danger flag
        keeps a ship fight going."""
        now = self.clock()
        if on_foot is not None:
            self._on_foot = bool(on_foot)
            if not on_foot:
                self._foot_health = None
        self._status_danger = bool(in_danger)
        if in_danger and self._in_danger:
            self._danger_at = now
        if self._on_foot:
            thought = self._foot_vitals(health, low_health, now)
            if thought:
                return thought
        calm = self._calm(now)
        if calm:
            return calm
        if fuel_percent is None:
            return None
        if vehicle:
            # An SRV's own tank (5.5.12): its own worry, and no talk of stars.
            if fuel_percent >= 40:
                self._srv_fuel_warned = False
            elif fuel_percent <= 25 and not getattr(self, "_srv_fuel_warned", False):
                self._srv_fuel_warned = True
                return self.consider("srv_fuel_low", {"fuel": int(round(fuel_percent)), "srv": str(vehicle).capitalize()})
            return None
        if fuel_percent >= 40:
            self._fuel_warned = False
            return None
        if fuel_percent <= 25 and not scooping and not self._fuel_warned:
            self._fuel_warned = True
            with self.lock:
                watcher_habits.low_fuel(self.memory)
            return self.consider("fuel_low", {"fuel": int(round(fuel_percent))})
        return None

    # -- 5.6.1: asking, answering, and what it keeps of you -------------------------------------
    def _voice_feel(self, topic, key):
        nature = personality(self.config)
        mood = MOODS.get(topic, "")
        feel = {"pace": 1.0, "gain": 1.0, "slip": False}
        if nature == "weary" or mood == "downcast" or float(self.memory.get("mood", 0.0)) <= watcher_deeper.MOOD_LOW:
            feel["pace"] = 1.07
        if mood == "wary":
            feel["pace"] = .95
        if topic.startswith("lore") or topic in {"idle_lens", "idle_four_shut", "idle_four_open"}:
            feel.update(gain=.72, pace=max(feel["pace"], 1.05))
        if str(key).split(":", 1)[-1] in VOICE_SLIPS:
            feel["slip"] = True
        return feel

    def story_marks(self):
        """What its story has done to the eye, for the orb (5.6.1): a hairline
        crack after The Draw, a second faint pupil while something looks
        through, the shutter part-drawn. Subtle, and they stay."""
        shared = watcher_lore.told(self.memory)
        road = watcher_lore.road(self.memory)
        draw = all(passage_id in shared for passage_id in ("a_cost", "sorry"))
        through = "it_looked" in shared
        shutter = .6 if road == "shut" else .35 if "the_fold" in shared and road is None else 0.0
        return {"crack": bool(draw), "second_pupil": bool(road == "open" or (through and road is None)), "shutter": shutter}

    def pending_question(self):
        question = self._question
        if not question:
            return None
        return {"id": question["id"], "text": question["text"], "answers": watcher_questions.choices(question["id"])}

    def ask(self, question_id, fields=None, force=False):
        """Ask a question (watcher_questions). One at a time; an everyday
        question at most once a fortnight."""
        spec = watcher_questions.QUESTIONS.get(question_id)
        if spec is None or self._question is not None or FREQUENCIES.get(frequency(self.config)) is None:
            return None
        now = self.clock()
        record = (self.memory.get("questions") or {}).get(question_id) or {}
        if not force and record.get("asked") and now - float(record["asked"]) < watcher_questions.ASK_REST_S:
            return None
        fields = {key: str(value) for key, value in (fields or {}).items()}
        voice = watcher_questions.voice(personality(self.config))
        try:
            text = self.random.choice(spec["ask"][voice]).format(**fields)
        except (KeyError, IndexError):
            return None
        thought = self._utter("question", f"question:{question_id}", text, now)
        thought["question"] = {"id": question_id, "answers": watcher_questions.choices(question_id)}
        thought["until"] = now + watcher_questions.ASK_SECONDS
        self._question = {"id": question_id, "asked": now, "fields": fields, "text": text}
        with self.lock:
            self.memory.setdefault("questions", {})[question_id] = {
                "asked": now, "answer": None, "answered": None, "fields": fields,
                "times": int(record.get("times") or 0) + 1}
        self._unsaved = True
        return thought

    def answer(self, answer):
        """Your answer to the question on screen: by its key or number."""
        question = self._question
        if not question:
            return None
        key = watcher_questions.answer_key(question["id"], answer)
        if key is None:
            return None
        spec = watcher_questions.QUESTIONS[question["id"]]
        now = self.clock()
        self._question = None
        with self.lock:
            record = self.memory.setdefault("questions", {}).setdefault(question["id"], {})
            record.update(answer=key, answered=now)
            watcher_deeper.shift(self.memory, "answered")
            if spec.get("road"):
                self.memory["road"] = key
                self._story_changed = True
            if question["id"] == "pilgrimage" and isinstance(self.memory.get("pilgrimage"), dict):
                self.memory["pilgrimage"]["accepted"] = key == "yes"
            if question["id"] == "your_name":
                watcher_name.set_call(self.memory, {"yes": "name", "commander": "commander", "other": "nickname"}[key])
        step = (spec.get("frequency") or {}).get(key)
        if step:
            order = ("rare", "occasional", "chatty")
            current = frequency(self.config)
            if current in order:
                self.config["heartbeat_thoughts"] = order[max(0, min(len(order) - 1, order.index(current) + step))]
        voice = watcher_questions.voice(personality(self.config))
        reply = self.random.choice(spec["replies"][key][voice]).format(**question.get("fields") or {})
        self._unsaved = True
        return self._utter("answer", f"answer:{question['id']}:{key}", reply, now)

    def _question_tick(self, now):
        question = self._question
        if question and now - question["asked"] > watcher_questions.UNANSWERED_S:
            self._question = None
            with self.lock:
                record = self.memory.setdefault("questions", {}).setdefault(question["id"], {})
                record["unanswered"] = int(record.get("unanswered") or 0) + 1
                watcher_deeper.shift(self.memory, "unanswered")
            self._unsaved = True
        # The shutter, asked and never answered for days: it chooses itself.
        record = (self.memory.get("questions") or {}).get("shutter") or {}
        if (watcher_lore.road(self.memory) is None and record.get("asked") and not record.get("answer")
                and now - float(record["asked"]) > watcher_questions.ROAD_SELF_CHOSEN_S):
            with self.lock:
                self.memory["road"] = "shut"
                record["answer"] = None
                record["self_chosen"] = now
            self._story_changed = True
            self._say_next.append(("callback_road", {}))

    def _maybe_ask(self, now, context):
        """Whether now is the moment for a question."""
        if self._question is not None or now - self._last_spoke < 60:
            return None
        if watcher_lore.road_question_due(self.memory):
            record = (self.memory.get("questions") or {}).get("shutter") or {}
            if not record.get("asked") or now - float(record["asked"]) > 2 * 86400:
                return self.ask("shutter", force=True)
        sessions, hours = self.memory.get("sessions") or 0, self.memory.get("hours") or 0
        kind = watcher_lore.waiting_place(self.memory, sessions, hours, now)
        if kind and (self.memory.get("pilgrimage") or {}).get("kind") != kind:
            with self.lock:
                self.memory["pilgrimage"] = {"kind": kind, "asked": now, "accepted": None}
            return self.ask("pilgrimage", {"place": watcher_places.words(kind)}, force=True)
        shared = watcher_lore.told(self.memory)
        road = watcher_lore.road(self.memory)
        if road == "open" and "iv_o_bends" in shared:
            asked = self._ask_once("what_said")
            if asked:
                return asked
        if road == "shut" and "iv_s_choose" in shared:
            asked = self._ask_once("forget_what")
            if asked:
                return asked
        context = context or {}
        home, far = context.get("home"), context.get("home_ly")
        if isinstance(home, dict):
            home = home.get("name") or home.get("system")
        if home and far and float(far) >= 5000 and self.random.random() < .05:
            return self.ask("miss_home", {"home": home})
        if self._session_start and now - self._session_start > 3 * 3600 and frequency(self.config) != "rare" \
                and self.random.random() < .02:
            return self.ask("talk_less")
        return None

    def _name_step(self, now):
        """The next step of its arc about your name (5.7.1), in a quiet
        moment: it notices the name, tries it, asks, and says it at last."""
        if self._question is not None or self._in_danger or now - self._last_spoke < 60:
            return None
        if self._session_start is None or now - self._session_start < 90:
            return None
        step = watcher_name.next_step(self.memory, self.memory.get("sessions"), self.memory.get("hours"), self._session_start)
        if not step:
            return None
        row = watcher_name.record(self.memory)
        if step == "ask":
            asked_before = bool((self.memory.get("questions") or {}).get("your_name"))
            thought = self.ask("your_name", {"name": row["known"]}, force=not asked_before)
        else:
            voice = watcher_questions.voice(personality(self.config))
            fields = {"name": row["known"], "seen": f"{max(int(self.memory.get('sessions') or 0), int(row.get('seen') or 0)):,}",
                      "called": watcher_name.call_name(self.memory) or row["known"]}
            text = self.random.choice(watcher_name.ARC[step][voice]).format(**fields)
            thought = self._utter("name_lore", f"name:{step}", text, now)
            number = watcher_name.ARC_ORDER.index(step) + 1
            thought["kind"], thought["heading"] = "memory", f"{watcher_name.TITLE} · {number} OF {len(watcher_name.ARC_ORDER)}"
        if thought:
            with self.lock:
                watcher_name.mark_step(self.memory, step, self._session_start, now)
                if step == "first":
                    watcher_name.mark_used(self.memory, self._session_start)
            self._unsaved = True
        return thought

    def _ask_once(self, question_id):
        if ((self.memory.get("questions") or {}).get(question_id) or {}).get("asked"):
            return None
        return self.ask(question_id, force=True)

    def _say_queued(self, topic, fields, now):
        if topic == "name_renamed":
            voice = watcher_questions.voice(personality(self.config))
            return self._utter("name_renamed", "name:renamed", self.random.choice(watcher_name.RENAMED[voice]).format(**fields), now)
        if topic == "lore_meeting":
            return self._utter("lore_meeting", "lore:meeting", fields["text"], now)
        if topic == "callback_road":
            voice = watcher_questions.voice(personality(self.config))
            line = ("You never answered me about the shutter. I chose. I kept it closed. I hope that was right."
                    if voice == "weary" else "You didn't answer about the shutter, so I chose: I've kept it closed.")
            return self._utter("callback", "callback:shutter:self", line, now)
        if topic.startswith("ask:"):
            return self.ask(topic[4:], fields)
        return self.consider(topic, fields, force=True)

    def _callback(self, now):
        """Something you told it (or didn't), brought back days later."""
        rows = [(question_id, record) for question_id, record in (self.memory.get("questions") or {}).items()
                if isinstance(record, dict) and record.get("asked") and now - float(record["asked"]) > 2 * 86400
                and question_id in watcher_questions.QUESTIONS]
        self.random.shuffle(rows)
        for question_id, record in rows:
            key = f"callback:{question_id}"
            if self._said_recently(key, watcher_questions.CALLBACK_REST_S):
                continue
            lines = watcher_questions.QUESTIONS[question_id]["callbacks"].get(record.get("answer"))
            if not lines:
                continue
            when = when_text(datetime.fromtimestamp(float(record.get("answered") or record["asked"])).astimezone().isoformat(), now)
            fields = {**(record.get("fields") or {}), "when": when or "a while back", "When": (when or "a while back").capitalize()}
            try:
                line = self.random.choice(lines).format(**fields)
            except (KeyError, IndexError):
                continue
            # Said in parts (an opener, the memory, a closer), so the same
            # answer rarely comes back the same way twice; with its mind
            # awake, in its own words (5.7.1).
            said = watcher_deeper.assemble(personality(self.config), line, self.random)
            if self._reword("callback", key, said, fields, 2, None, now):
                return None
            return self._utter("callback", key, said, now)
        return None

    def _queue_session_extras(self, now):
        """Things to say once the greeting's done: a dream from last time, an
        anniversary of you two, how it went last time."""
        dream = next((row for row in reversed(self.memory.get("dreams") or []) if isinstance(row, dict) and not row.get("told")), None)
        if dream and self.random.random() < .6:
            dream["told"] = now
            self._say_next.append(("dream_told", {"dream": dream["text"]}))
        first = self.memory.get("first_seen")
        if first:
            then, today = datetime.fromtimestamp(float(first)), datetime.fromtimestamp(now)
            years = today.year - then.year
            if years >= 1 and (then.month, then.day) == (today.month, today.day):
                what = f"{years} year{'s' if years != 1 else ''} since you first switched me on"
                self._say_next.append(("anniversary_us", {"What": what[:1].upper() + what[1:], "what": what, "what_lower": what}))
        if self.memory.get("last_death") and float(self.memory["last_death"]) > float(self.memory.get("session_started") or 0) - 86400 * 3:
            self._say_next.append(("ask:worth_it", {}))

    def _observe_deeper(self, event, raw, now):
        """Places reached, moments kept, and what moves its trust."""
        system = raw.get("StarSystem") or raw.get("SystemName")
        with self.lock:
            memory = self.memory
            if event in {"FSDJump", "Location", "CarrierJump"} and system:
                if not memory.get("first_system"):
                    memory["first_system"] = str(system)
                memory["last_system"] = str(system)
            if event == "Loadout":
                memory["ship_name"] = str(raw.get("ShipName") or raw.get("Ship_Localised") or raw.get("Ship") or "")[:60] or None
            kind = watcher_places.place_of(event, raw)
            if event in {"FSDJump", "Location", "CarrierJump"} and system and memory.get("first_system") \
                    and str(system).casefold() == str(memory["first_system"]).casefold() and memory.get("sessions", 0) > 1:
                kind = kind or "first_place"
            if kind:
                places = memory.setdefault("places", {})
                times = int((places.get(kind) or [0])[0] or 0)
                places[kind] = [times + 1, now]
                wanted = memory.get("pilgrimage") or {}
                if wanted.get("kind") == kind and not wanted.get("reached"):
                    wanted["reached"] = now
                    watcher_deeper.shift(memory, "pilgrimage")
                    self._story_changed = True
            if event == "Died":
                watcher_deeper.shift(memory, "death")
                ship = memory.get("ship_name") or "the ship"
                self._keep_moment("lost", f"the {ship} we lost near {memory.get('last_system') or 'somewhere dark'}", now)
            elif event == "HullDamage" and raw.get("PlayerPilot", True) and not raw.get("Fighter"):
                try:
                    low = float(raw.get("Health", 1.0)) < .25
                except (TypeError, ValueError):
                    low = False
                if low and not self._scared:
                    self._scared = True
                    watcher_deeper.shift(memory, "scare")
            elif event in {"RepairAll", "Repair"}:
                self._scared = False
                watcher_deeper.shift(memory, "repair")
            elif event in {"SellExplorationData", "MultiSellExplorationData", "SellOrganicData"}:
                watcher_deeper.shift(memory, "sold")
            elif event == "Scan" and raw.get("WasDiscovered") is False and raw.get("PlanetClass"):
                planet = str(raw.get("PlanetClass_Localised") or raw.get("PlanetClass") or "")
                if rarity({"planet_class": raw.get("PlanetClass")}) or "earth" in planet.casefold() or "water world" in planet.casefold():
                    self._keep_moment("first", f"the {planet.lower()} you were first to find, {raw.get('BodyName') or 'out there'}", now)
            elif event == "WingJoin" and raw.get("Others"):
                names = ", ".join(str(name.get("Name") if isinstance(name, dict) else name) for name in raw["Others"][:3])
                self._keep_moment("wing", f"flying with {names}", now)
            elif event == "WingAdd" and raw.get("Name"):
                self._keep_moment("wing", f"flying with {raw['Name']}", now)

    def _keep_moment(self, kind, text, now):
        moments = self.memory.setdefault("moments", [])
        moments.append({"kind": kind, "text": str(text)[:160], "at": now})
        del moments[:-watcher_deeper.MOMENTS_KEPT]
        self._unsaved = True

    def _moment_choice(self, now):
        """A moment it kept, at least two days old, as idle fields. With the
        shutter drawn (Book Three), old ones come back with words missing."""
        rows = [row for row in self.memory.get("moments") or () if isinstance(row, dict) and now - float(row.get("at") or now) > 2 * 86400]
        if not rows:
            return None
        row = self.random.choice(rows)
        about = row["text"]
        if "the_fold" in watcher_lore.told(self.memory) and now - float(row["at"]) > watcher_deeper.FADE_AFTER_DAYS * 86400:
            about = watcher_deeper.fade(about, row["at"])
        when = when_text(datetime.fromtimestamp(float(row["at"])).astimezone().isoformat(), now) or "a while back"
        return {"about": about, "About": about[:1].upper() + about[1:], "when": when, "When": when[:1].upper() + when[1:]}

    def memories_page(self, now=None):
        """What it remembers of you, as its own notes, for the Watcher page."""
        now = self.clock() if now is None else now
        faded = "the_fold" in watcher_lore.told(self.memory)
        out = []
        for row in reversed(self.memory.get("moments") or []):
            if not isinstance(row, dict):
                continue
            old = faded and now - float(row.get("at") or now) > watcher_deeper.FADE_AFTER_DAYS * 86400
            out.append({"text": watcher_deeper.fade(row["text"], row["at"]) if old else row["text"], "at": row.get("at"),
                        "faded": bool(old), "kind": row.get("kind")})
        return out[:120]

    def _dream(self):
        """Signing off: it dreams, from the session and the story so far."""
        if self._session_start is None:
            return None
        moments = [row for row in self.memory.get("moments") or () if isinstance(row, dict)
                   and float(row.get("at") or 0) >= self._session_start]
        session = {"place": self.memory.get("last_system"), "thing": moments[-1]["text"] if moments else None}
        shared = watcher_lore.told(self.memory)
        road = watcher_lore.road(self.memory)
        hint = ("look" if road == "open" else "shutter" if road == "shut" else "others" if "hundreds" in shared
                else "seat" if watcher_lore.book_three_begun(self.memory) else "sound" if "sound" in shared else "")
        text = watcher_deeper.dream(personality(self.config), session, hint, self.random)
        with self.lock:
            dreams = self.memory.setdefault("dreams", [])
            dreams.append({"at": self.clock(), "text": text, "told": None})
            del dreams[:-watcher_deeper.DREAMS_KEPT]
        return text

    def meet(self, card):
        """Another commander's Watcher, from a shared code."""
        if not isinstance(card, dict):
            return None
        now = self.clock()
        key = f"{card.get('name')}|{card.get('nature')}|{card.get('hours')}"
        with self.lock:
            met = self.memory.setdefault("met", [])
            if any(row.get("key") == key for row in met if isinstance(row, dict)):
                return None
            first = not met
            met.append({**card, "key": key, "at": now})
            watcher_deeper.shift(self.memory, "met")
        self._unsaved = True
        if first:
            self._say_next.append(("lore_meeting", {"text": watcher_lore.MEETING.get(watcher_lore.road(self.memory))}))
        nature = watcher_deeper.NATURE_WORDS.get(card.get("nature"), "another one")
        road = watcher_deeper.ROAD_WORDS.get(card.get("road"))
        return self.consider("watchers_meet", {"nature": nature, "Nature": nature[:1].upper() + nature[1:],
                                                "road": road, "Road": road[:1].upper() + road[1:]}, force=True)

    def share_card(self, commander=""):
        """Your Watcher, in short, for a share code."""
        progress = watcher_lore.progress(self.memory)
        book = 4 if progress.get("BookFourBegun") else 3 if progress.get("BookThreeBegun") else 2 if self.memory.get("afterword") else 1
        shared = watcher_lore.told(self.memory)
        chapter = next((chapter[0] for chapter in reversed(watcher_lore.ALL_CHAPTERS)
                        if any(passage_id in shared for passage_id, _words in chapter[5])), "")
        return {"name": str(commander or "")[:60], "nature": personality(self.config), "book": book, "chapter": chapter,
                "road": watcher_lore.road(self.memory), "bond": self.bond(), "hours": int(self.memory.get("hours") or 0)}

    def tick(self, context=None):
        """Idle thinking: the time, a long session, a long quiet. ``context``
        is what the rest of the app knows (the music playing, Galnet)."""
        now = self.clock()
        self.learn(context)
        if self._session_start is None:
            return None  # nothing to think about until it has seen the game
        self._account_time()
        self._diary_step(now)
        self._about_step(now)
        calm = self._calm(now)
        if calm:
            return calm
        voice = self.find_voice()
        if voice:
            return voice
        # 5.6.1: a question waiting too long goes unanswered; what's queued
        # (a dream, a meeting's passage, a question) when it's quiet enough.
        self._question_tick(now)
        if self._say_next and now - self._last_spoke > 20 and not self._question:
            topic, fields = self._say_next.pop(0)
            queued = self._say_queued(topic, fields, now)
            if queued:
                return queued
        named = self._name_step(now)
        if named:
            return named
        asked = self._maybe_ask(now, context)
        if asked:
            return asked
        self._mind_step(now)
        if self._session_start and now - self._session_start > 3 * 3600:
            hours = int((now - self._session_start) // 3600)
            if not self._said_recently("long_session", 3600):
                thought = self.consider("long_session", {"hours": hours})
                if thought:
                    return thought
        # Its story needs only a lull, not the long quiet of an idle thought:
        # two minutes with nothing new and nothing said, out of danger
        # (5.5.3.5; waiting for the full quiet kept it silent for hours of
        # busy flying). remember() keeps its own pacing.
        if now - self._last_spoke > watcher_lore.LULL_S and now - self._last_interesting > watcher_lore.LULL_S:
            memory = self.remember()
            if memory:
                return memory
        setting = FREQUENCIES.get(frequency(self.config)) or {}
        quiet = setting.get("quiet", 900.0)
        # Into the quiet: something about what's around (the star, the
        # system, how far from home, the session so far, the hour), or a
        # plain mutter. At most one idle thought per `mutter` (5 min on
        # Chatty, 10 on Occasional, 20 on Rare).
        if (now - self._last_interesting > quiet and now - self._last_spoke > quiet
                and not self._said_recently("idle", setting.get("mutter", 1200.0))):
            # A memory of its past, when one is due (5.5.3.5).
            memory = self.remember()
            if memory:
                with self.lock:
                    self.memory["said"].append(["idle", now])
                return memory
            known = dict(context or {})
            known.update(thoughts=self.memory.get("thoughts") or 0, sessions=self.memory.get("sessions") or 0,
                         deaths=self.memory.get("deaths") or 0, bond=self.bond(),
                         hours=int(self.memory.get("hours") or 0),
                         # 5.5.3.5: its story told, and a finished chapter to look back on.
                         story_done=bool(self.memory.get("afterword")),
                         book_three=watcher_lore.book_three_begun(self.memory),
                         recall=watcher_lore.recall_choice(self.memory, self.random, now),
                         # 5.5.3.7: a postcard it kept.
                         postcard=watcher_postcards.recall_choice(self.memory, self.random, now))
            known["road"] = watcher_lore.road(self.memory)
            choices = self.surroundings.choices(now, self.random, known)
            # How you play, as it has come to know you (5.5.4): now and then.
            if self.random.random() < .35:
                choices[:0] = watcher_habits.choices(self.memory, self.bond(), self.random)[:1]
            # 5.6.1: a moment it kept; its slow mood; what you once told it.
            moment = self._moment_choice(now)
            if moment and self.random.random() < .3:
                choices.insert(0, ("idle_moment", moment))
            mood = float(self.memory.get("mood", 0.0))
            if mood <= watcher_deeper.MOOD_LOW:
                choices.append(("mood_low", {}))
            elif mood >= watcher_deeper.MOOD_HIGH:
                choices.append(("mood_high", {}))
            if self.random.random() < .15:
                callback = self._callback(now)
                if callback:
                    with self.lock:
                        self.memory["said"].append(["idle", now])
                    return callback
            # The plain mutter now and then, and whenever nothing else fits.
            if not choices or self.random.random() < .25:
                choices.insert(0, ("quiet", {}))
            else:
                choices.append(("quiet", {}))
            for topic, fields in choices:
                thought = self.consider(topic, fields)
                if thought:
                    with self.lock:
                        self.memory["said"].append(["idle", now])
                    return thought
        return None
