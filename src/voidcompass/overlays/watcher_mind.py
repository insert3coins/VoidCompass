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

from voidcompass.exploration.notable_bodies import is_green_giant_codex, rarity
from voidcompass.overlays import watcher_idle, watcher_lines, watcher_lore, watcher_natures

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
    "sign_off": ("", "SIGNING OFF"),
    "sign_off_quiet": ("", "SIGNING OFF"),
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
    if topic in watcher_lore.ECHO_LABELS:
        return "echo", f"ECHO · {watcher_lore.ECHO_LABELS[topic].upper()}"
    return HEADED_TOPICS.get(topic, ("", ""))


def personality(config):
    value = str((config or {}).get("heartbeat_personality") or DEFAULT_PERSONALITY).casefold()
    return value if value in PERSONALITIES else DEFAULT_PERSONALITY


# How much each topic matters: 3 it must say (a death), 2 notable, 1 worth
# a remark, 0 idle. The words are in watcher_lines.py.
IMPORTANCE = {
    "greet_new": 3,
    "greet_away": 3,
    "greet_soon": 2,
    "greet_night": 2,
    "after_death": 3,
    "died": 3,
    "danger": 2,
    "danger_over": 1,
    "fuel_low": 2,
    "first_discovery_streak": 2,
    "undiscovered_system": 1,
    "new_region": 2,
    "valuable_world": 2,
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
    "nervous": {"danger": 1.6, "fuel_low": 1.6, "after_death": 1.5, "quiet": 1.2, "danger_over": 1.4},
    # The weary one mutters to itself more in the quiet.
    "weary": {"idle": 1.4, "quiet": 1.6, "docked_home": 1.3, "long_session": 1.3, "big_sale": .8},
}


# How the eye looks while it says each thought (heartbeat-life.js plays
# the matching expression): pleased, wary, curious, or downcast. Topics not
# listed are said with a neutral eye.
MOODS = {
    **{topic: "pleased" for topic in (
        "rare_world", "green_giant", "valuable_world", "first_discovery_streak", "undiscovered_system",
        "codex_logged", "codex_new", "big_sale", "achievement", "promotion", "mapped_efficient",
        "analysed", "fss_complete", "mapped", "scooped", "mission_done", "sign_off", "idle_recall",
        "idle_session", "new_region", "greet_away", "greet_soon", "danger_over", "idle_music")},
    **{topic: "wary" for topic in ("danger", "fuel_low", "idle_deaths", "heat_warning")},
    **{topic: "pleased" for topic in ("interdiction_escaped", "srv_launch", "idle_srv", "idle_ship")},
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
))
NOTICE_OPEN, NOTICE_CLOSE = "⟦", "⟧"


def noticed(fields):
    """Fields with the journal's words marked for the page."""
    return {key: f"{NOTICE_OPEN}{value}{NOTICE_CLOSE}"
            if key in NOTICED_FIELDS and str(value).strip() else value
            for key, value in fields.items()}


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
        self.memory = {"last_seen": None, "sessions": 0, "said": [], "regions": [],
                       "deaths": 0, "last_death": None, "session_started": None, "thoughts": None,
                       # 5.5.3.2: hours flown together, your records, the day
                       # it last marked your anniversary, and what it said.
                       "hours": 0.0, "records": {}, "anniversary_said": None, "log": [],
                       # 5.5.3.5: the memories of its past it has shared, [id, when];
                       # the echoes found, {topic: [times, last]}; when it said
                       # its afterword (Book One finished).
                       "lore": [], "echoes": {}, "afterword": None}
        self._load()
        if self.memory.get("thoughts") is None:
            # Older memories: count the thoughts it remembers saying.
            self.memory["thoughts"] = sum(1 for row in self.memory["said"]
                                          if isinstance(row, list) and row and ":" not in str(row[0]) and row[0] != "idle")
        self._afterthought = None
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
        self._fuel_warned = False
        self._codex_bodies = set()
        self._last_interesting = self.clock()
        self._pending = []           # (importance, topic, fields)
        self._dead_since = None
        # What's around the commander, for idle thoughts (5.5.3.2).
        self.surroundings = watcher_idle.Surroundings()

    # -- memory --------------------------------------------------------------
    def _load(self):
        if not self.memory_path:
            return
        try:
            data = json.loads(self.memory_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.memory.update({key: data[key] for key in self.memory if key in data})
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
            if importance < 3 and self._said_recently(topic, rest):
                return None
            # Even with something to say, it often keeps it to itself.
            chance = min(1.0, (.35 + .25 * importance) * weight)
            if importance < 3 and self.random.random() > chance:
                return None
        chosen = self._variant(topic, dict(fields or {}))
        if not chosen:
            return None
        key, script = chosen
        self._utter(topic, key, script, now)
        # Now and then a second beat follows, once the first has been read.
        if topic != "afterthought" and importance < 3:
            chance = .3 if (topic == "quiet" or topic in watcher_idle.IDLE_TOPICS) else .12
            if self.random.random() < chance:
                self._afterthought = {"after": self._serial, "at": now + 3.2 + len(script) * .045}
        return self.thought

    def _utter(self, topic, key, script, now):
        """Say a thought: on screen for a while, and remembered."""
        text = plain_text(script)
        self._serial += 1
        self._last_spoke = now
        kind, heading = thought_heading(topic, text)
        self.thought = {"id": self._serial, "text": text, "script": script, "topic": topic,
                        "mood": MOODS.get(topic, ""), "at": now,
                        "kind": kind, "heading": heading,
                        "until": now + (THOUGHT_SECONDS + len(script) * .05)
                        * THOUGHT_HOLDS[thought_style(self.config)["hold"]]}
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

    def remember(self):
        """The next passage of its story, when one is due (5.5.3.5): in order,
        as the sessions and hours together unlock them, at most one every hour
        and a half of play, and never in a session's first minutes. Its
        thoughts switched off means no story either."""
        if FREQUENCIES.get(frequency(self.config)) is None or self._session_start is None or self._in_danger:
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
        row = watcher_lore.due(self.memory, self.memory.get("sessions") or 0, self.memory.get("hours") or 0)
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

    def follow_up(self):
        """The second beat of a thought, when it is due (the HUD asks often)."""
        pending = self._afterthought
        if not pending or self.clock() < pending["at"]:
            return None
        self._afterthought = None
        if not self.thought or self.thought["id"] != pending["after"] or self.clock() >= self.thought["until"]:
            return None
        return self.consider("afterthought", force=True)

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
        """One journal event. Returns a new thought, or None."""
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
        if event in {"LoadGame"}:
            return self.session_start()
        if self._session_start is None and event == "Died":
            self._session_start = now  # the death matters more than a hello
        elif self._session_start is None and event not in {"Shutdown", "Fileheader", "Commander"}:
            greeting = self.awake()
            if greeting:
                return greeting
        if event == "Shutdown":
            self.seen()
            self.save()
            return None
        if event == "Died":
            with self.lock:
                self.memory["deaths"] = int(self.memory.get("deaths") or 0) + 1
                self.memory["last_death"] = now
            self.save()
            return self.consider("died", force=True)
        if event in {"Interdicted", "UnderAttack"} or (event == "ShieldState" and raw.get("ShieldsUp") is False):
            self._in_danger = True
            return self.consider("danger")
        if event in {"FSDJump", "SupercruiseEntry", "Docked"} and self._in_danger:
            self._in_danger = False
            return self.consider("danger_over")
        # Something in the game that touches its past (5.5.3.5).
        echo = watcher_lore.echo_for(event, raw)
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
        if event == "LaunchSRV":
            return self.consider("srv_launch")
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
            return self.consider("mined", {"material": material}) if material else None
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
            if planet in {"earthlike body", "water world", "ammonia world"} or raw.get("TerraformState") == "Terraformable":
                self._last_interesting = now
                return self.consider("valuable_world", {"body": raw.get("BodyName") or "That world"})
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
            rank = next((f"{key} rank {value}" for key, value in raw.items() if key not in {"timestamp", "event"}), None)
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

    def vitals(self, fuel_percent=None, scooping=False):
        """Status: worry about fuel once, until it is topped up."""
        if fuel_percent is None:
            return None
        if fuel_percent >= 40:
            self._fuel_warned = False
            return None
        if fuel_percent <= 25 and not scooping and not self._fuel_warned:
            self._fuel_warned = True
            return self.consider("fuel_low", {"fuel": int(round(fuel_percent))})
        return None

    def tick(self, context=None):
        """Idle thinking: the time, a long session, a long quiet. ``context``
        is what the rest of the app knows (the music playing, Galnet)."""
        now = self.clock()
        if self._session_start is None:
            return None  # nothing to think about until it has seen the game
        self._account_time()
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
                         recall=watcher_lore.recall_choice(self.memory, self.random, now))
            choices = self.surroundings.choices(now, self.random, known)
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
