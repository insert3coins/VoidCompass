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
import threading
import time
from datetime import datetime
from pathlib import Path
import zlib

from voidcompass.exploration.notable_bodies import is_green_giant_codex, rarity
from voidcompass.overlays import watcher_lines

# How often it may speak (Overlay Studio). The gap is the least time
# between two thoughts; `minimum` is the least importance it will voice.
FREQUENCIES = {
    "off": None,
    # gap: least time between two thoughts; minimum: least importance it
    # voices; quiet: how long without anything happening before it mutters.
    "rare": {"gap": 300.0, "minimum": 2, "quiet": 900.0, "rest": 1200.0},
    "occasional": {"gap": 75.0, "minimum": 1, "quiet": 300.0, "rest": 600.0},
    "chatty": {"gap": 25.0, "minimum": 0, "quiet": 120.0, "rest": 300.0},
}
DEFAULT_FREQUENCY = "rare"
PERSONALITIES = ("stoic", "curious", "nervous", "weary")
# The Watcher is depressed by default (the user's wish); "weary" in config.
DEFAULT_PERSONALITY = "weary"
# A thought stays on screen this long (plus time to read).
THOUGHT_SECONDS = 9.0
# The same topic is not raised again for this long.
TOPIC_REST_S = 20 * 60.0
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
        "colour": colour if colour in THOUGHT_COLOURS else "bright",
        "size": size if size in THOUGHT_SIZES else "standard",
        "hold": hold if hold in THOUGHT_HOLDS else "standard",
    }


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
    "codex_new": 2,
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
    "stoic": {"quiet": 0, "docked_home": 0, "codex_logged": .5, "big_sale": .5, "greet_soon": .5},
    "curious": {"codex_new": 1.5, "codex_logged": 1.5, "undiscovered_system": 1.5, "new_region": 1.3},
    "nervous": {"danger": 1.6, "fuel_low": 1.6, "after_death": 1.5, "quiet": 1.2, "danger_over": 1.4},
    # The weary one mutters to itself more in the quiet.
    "weary": {"quiet": 1.6, "docked_home": 1.3, "long_session": 1.3, "big_sale": .8},
}


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
                       "deaths": 0, "last_death": None, "session_started": None}
        self._load()
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

    def save(self):
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
        except OSError:
            pass

    # -- choosing ------------------------------------------------------------
    def _said_recently(self, key, within):
        now = self.clock()
        return any(row[0] == key and now - row[1] < within for row in self.memory["said"])

    def _variant(self, topic, fields):
        importance, variants = TOPICS[topic]
        if personality(self.config) == "weary" and topic in WEARY:
            variants = WEARY[topic]
        options = []
        for template in variants:
            try:
                text = template.format(**fields)
            except (KeyError, IndexError, ValueError):
                continue
            # Remembered by its wording, so the line banks can change freely.
            options.append((f"{topic}:{zlib.crc32(template.encode('utf-8')):08x}", text))
        if not options:
            return None
        # Never the same words twice while another wording is left.
        fresh = [row for row in options if not self._said_recently(row[0], 30 * 86400)]
        if fresh:
            return self.random.choice(fresh)
        if importance < 2:
            # A minor remark stays unsaid rather than repeat a recent line.
            fresh = [row for row in options if not self._said_recently(row[0], 3 * 86400)]
            if not fresh:
                return None
            return self.random.choice(fresh)
        # Something it must say, with every line used: the ones said longest ago.
        options.sort(key=lambda row: self._last_said(row[0]))
        return self.random.choice(options[:max(1, len(options) // 3)])

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
        if personality(self.config) == "weary" and topic in {"quiet", "docked_home"}:
            # A depressed robot complains about the quiet: worth saying aloud.
            importance = max(importance, 2)
        weight = PERSONALITY_WEIGHTS.get(personality(self.config), {}).get(topic, 1)
        if weight <= 0:
            return None
        now = self.clock()
        if not force:
            if importance < setting["minimum"]:
                return None
            if importance < 3 and now - self._last_spoke < setting["gap"]:
                return None
            if importance < 3 and self._said_recently(topic, setting.get("rest", TOPIC_REST_S)):
                return None
            # Even with something to say, it often keeps it to itself.
            chance = min(1.0, (.35 + .25 * importance) * weight)
            if importance < 3 and self.random.random() > chance:
                return None
        chosen = self._variant(topic, dict(fields or {}))
        if not chosen:
            return None
        key, text = chosen
        self._serial += 1
        self._last_spoke = now
        self.thought = {"id": self._serial, "text": text, "topic": topic, "at": now,
                        "until": now + (THOUGHT_SECONDS + len(text) * .05)
                        * THOUGHT_HOLDS[thought_style(self.config)["hold"]]}
        # The latest thing it said, kept for the deck's Focused Log.
        self.last_thought = {"text": text, "at": time.time()}
        with self.lock:
            self.memory["said"].append([key, now])
            self.memory["said"].append([topic, now])
        return self.thought

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
        if kind == "sign_off":
            # The end of a session: the Captain's Log's own figures.
            summary = str(fields.get("summary") or "")
            # Lines quoting {hours} are skipped when the session was too short.
            words = {"hours": fields["hours"]} if fields.get("hours") else {}
            if summary:
                return self.consider("sign_off", {**words, "summary": summary}, force=True)
            return self.consider("sign_off_quiet", words, force=True)
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

    def tick(self):
        """Idle thinking: the time, a long session, a long quiet."""
        now = self.clock()
        if self._session_start is None:
            return None  # nothing to think about until it has seen the game
        if self._session_start and now - self._session_start > 3 * 3600:
            hours = int((now - self._session_start) // 3600)
            if not self._said_recently("long_session", 3600):
                thought = self.consider("long_session", {"hours": hours})
                if thought:
                    return thought
        setting = FREQUENCIES.get(frequency(self.config)) or {}
        quiet = setting.get("quiet", 900.0)
        # Muttering into the quiet: at most every 15 minutes, whatever the setting.
        if (now - self._last_interesting > quiet and now - self._last_spoke > quiet
                and not self._said_recently("quiet", max(900.0, setting.get("rest", 900.0)))):
            return self.consider("quiet")
        return None
