"""Crew banter (5.7.7): the crew talking to each other.

A moment in the game (low fuel, a first discovery, docking, a quiet stretch)
starts a short exchange between the companion on watch and a crewmate or
two, each in their own voice; the overlay shows whoever is speaking. Only
companions whose voice is on take part, so it's heard, not read. Each line
waits for the last one's voice to finish.

The words are in banter_words_*.py: {moment: (exchange, ...)}, an exchange
being ((speaker, line), ...). No exchange is heard again until every other
one for its moment has been, across sessions.
"""

from __future__ import annotations

import random
import string
import zlib

from voidcompass.overlays import (banter_words_explore, banter_words_flight, banter_words_idle, banter_words_pairs,
                                  banter_words_port)

SPEAKERS = ("watcher", "aster", "axiom", "meridian", "lyra")
NAMES = {"watcher": "THE WATCHER", "aster": "ASTER", "axiom": "AXIOM", "meridian": "MERIDIAN", "lyra": "LYRA"}

# How often, and the least time between two exchanges (Its thoughts › Crew banter).
FREQUENCIES = {"off": None, "sometimes": {"chance": .4, "label": "Now and then"},
               "often": {"chance": .75, "label": "Often"}}
DEFAULT_FREQUENCY = "sometimes"
GAPS = (10, 20, 30, 60)
DEFAULT_GAP = 20
SIZES = {"two": 2, "three": 3}
DEFAULT_SIZE = "three"
# 8 November: whole exchanges ran long. Short is a line and its answer.
LENGTHS = {"short": 2, "full": None}
DEFAULT_LENGTH = "short"
SETTLE_S = 6 * 60.0          # not in a session's first minutes
MOMENT_REST_S = 45 * 60.0    # the same moment isn't talked over again within this
IDLE_AFTER_S = 15 * 60.0     # this long with nothing said makes a quiet stretch

# When they talk: each moment belongs to one of these, and each can be switched off.
GROUPS = {
    "flight": ("In flight", "Fuel, a full scoop, long jump runs, heat, a narrow escape, launch, distance records, black holes and neutron stars."),
    "exploring": ("Exploring", "First discoveries, worlds worth mapping, the Codex, samples, landings, footfalls and data sold."),
    "port": ("In port", "Docking, trade and mining."),
    "crew": ("Crew moments", "A crew order done, a ship lost, a long session."),
    "quiet": ("Quiet stretches", "When nothing has been said for a while."),
}
MOMENTS = {
    "low_fuel": "flight", "scooped": "flight", "jump_run": "flight", "heat": "flight", "escaped": "flight",
    "launch": "flight", "far_record": "flight", "black_hole": "flight", "neutron": "flight",
    "first_discovery": "exploring", "worthy_world": "exploring", "codex": "exploring", "bio_done": "exploring",
    "landing": "exploring", "footfall": "exploring", "data_sold": "exploring",
    "docked": "port", "trade_profit": "port", "mined": "port",
    "order_done": "crew", "ship_lost": "crew", "long_session": "crew",
    "idle": "quiet",
}

BANTER = {}
for _module in (banter_words_flight, banter_words_explore, banter_words_port, banter_words_idle, banter_words_pairs):
    for _moment, _exchanges in _module.BANTER.items():
        BANTER.setdefault(_moment, []).extend(_exchanges)

_FORMAT = string.Formatter()


def frequency(config):
    value = str((config or {}).get("crew_banter") or DEFAULT_FREQUENCY).casefold()
    return value if value in FREQUENCIES else DEFAULT_FREQUENCY


def gap_s(config):
    try:
        minutes = int(float((config or {}).get("crew_banter_gap") or DEFAULT_GAP))
    except (TypeError, ValueError):
        minutes = DEFAULT_GAP
    return (minutes if minutes in GAPS else DEFAULT_GAP) * 60.0


def size(config):
    value = str((config or {}).get("crew_banter_size") or DEFAULT_SIZE).casefold()
    return SIZES.get(value, SIZES[DEFAULT_SIZE])


def length(config):
    value = str((config or {}).get("crew_banter_length") or DEFAULT_LENGTH).casefold()
    return value if value in LENGTHS else DEFAULT_LENGTH


def group_on(config, moment):
    group = MOMENTS.get(moment)
    return bool(group) and (config or {}).get(f"crew_banter_{group}", True) is not False


def exchange_id(exchange):
    return f"{zlib.crc32(repr(tuple(exchange)).encode('utf-8')):08x}"


def _fields(line):
    return {name for _text, name, _spec, _conv in _FORMAT.parse(line) if name}


def choose(moment, available, on_watch, heard=None, rng=None, fields=None, most=3, lines=None):
    """An exchange for this moment that the companions available can have:
    (id, [(speaker, text), ...]) or None. ``heard`` is {id: when}; one
    already heard waits until the rest of its moment have been. The one on
    watch takes part where it can, and leads where it can. ``lines`` cuts
    each exchange to its first few (the Short length)."""
    rng = rng or random
    heard = heard if heard is not None else {}
    available = set(available or ())
    fields = {key: value for key, value in (fields or {}).items() if value not in (None, "")}
    usable = []
    for exchange in BANTER.get(moment, ()):
        if lines:
            exchange = tuple(exchange[:lines])
        speakers = {speaker for speaker, _line in exchange}
        if not speakers <= available or len(speakers) > most or len(speakers) < 2:
            continue
        if any(not _fields(line) <= set(fields) for _speaker, line in exchange):
            continue
        usable.append(exchange)
    if not usable:
        return None
    fresh = [exchange for exchange in usable if exchange_id(exchange) not in heard]
    if not fresh:
        # Every one heard: start again, but not with the latest few.
        latest = sorted(usable, key=lambda exchange: -float(heard.get(exchange_id(exchange)) or 0))[:max(1, len(usable) // 3)]
        fresh = [exchange for exchange in usable if exchange not in latest] or usable
    leads = [exchange for exchange in fresh if exchange[0][0] == on_watch]
    joins = [exchange for exchange in fresh if any(speaker == on_watch for speaker, _line in exchange)]
    pool = leads or joins or fresh
    exchange = rng.choice(pool)
    try:
        said = [(speaker, line.format(**fields)) for speaker, line in exchange]
    except (KeyError, IndexError, ValueError):
        return None
    return exchange_id(exchange), said


def may_talk(config, moment, now, state, facts):
    """(True, "") or (False, why not). ``state``: last, moments {moment: when}.
    ``facts``: session_start, in_danger, speakers (how many can take part)."""
    setting = FREQUENCIES.get(frequency(config))
    if setting is None:
        return False, "Banter is off"
    if not group_on(config, moment):
        return False, "Not for this kind of moment"
    if int(facts.get("speakers") or 0) < 2:
        return False, "Needs two companions with their voices on"
    started = facts.get("session_start")
    if not started or now - float(started) < SETTLE_S:
        return False, "Settling in"
    if facts.get("in_danger"):
        return False, "Not in a fight"
    if now - float(state.get("last") or 0) < gap_s(config):
        return False, "Too soon"
    if now - float((state.get("moments") or {}).get(moment) or 0) < MOMENT_REST_S:
        return False, "Talked about that lately"
    return True, ""


def chance(config):
    setting = FREQUENCIES.get(frequency(config))
    return setting["chance"] if setting else 0.0
