"""Crew Orders in the crew's own words (5.7.7).

Each speaker has two styles: the officers plain or voiced (their humour
setting), the Watcher normal or weary (its nature). Offers are said by the
officer who gives them; the rest by whoever the order belongs to. A wording
isn't used again until every other wording of that topic has been.
"""

from __future__ import annotations

import random
import string
import zlib

from voidcompass.overlays import (order_overtaken_words, order_relay_words, order_words_aster, order_words_axiom,
                                  order_words_lyra, order_words_meridian, order_words_watcher)

WORDS = {
    "watcher": order_words_watcher.WORDS,
    "aster": order_words_aster.WORDS,
    "axiom": order_words_axiom.WORDS,
    "meridian": order_words_meridian.WORDS,
    "lyra": order_words_lyra.WORDS,
}
SPEAKERS = tuple(WORDS)
# Passing an order on when its officer's voice is off (order_relay_words).
for _speaker, _styles in [*order_relay_words.RELAY.items(), *order_overtaken_words.OVERTAKEN.items()]:
    for _style, _topics in _styles.items():
        WORDS[_speaker].setdefault(_style, {}).update(_topics)
RELAY_TOPICS = ("relay_offer", "relay_done", "relay_news")
NAMES = {"watcher": "the Watcher", "aster": "Aster", "axiom": "Axiom", "meridian": "Meridian", "lyra": "Lyra"}

# Said about any order, by every speaker.
TOPICS = ("floor", "accepted", "declined", "muted", "later", "step", "halfway", "done", "abandoned", "paused",
          "lapsed", "waiting", "stage", "ribbon", "full", "reminder", "standing", "overtaken")
# Offers, by the officer who gives that kind.
OFFERS = {
    "lyra": ("bio_hunt", "cash_bio"),
    "axiom": ("map_worlds", "first_discoveries", "finish_system"),
    "meridian": ("neutron", "new_region", "record_far"),
    "aster": ("sell_price", "cash_carto", "colony", "merits"),
    "watcher": ("place", "errand"),
}
_FORMAT = string.Formatter()


def style(speaker, config):
    config = config or {}
    if speaker == "watcher":
        return "weary" if str(config.get("heartbeat_personality") or "weary").casefold() == "weary" else "normal"
    return "plain" if config.get(f"{speaker}_humour", "dry") == "off" else "voiced"


def fields_used(line):
    return {name for _text, name, _spec, _conv in _FORMAT.parse(line) if name}


def lines_for(speaker, topic, config=None):
    banks = WORDS.get(speaker) or {}
    chosen = banks.get(style(speaker, config)) or {}
    lines = chosen.get(topic)
    if not lines:
        # A topic missing from one style borrows the other's.
        for other in banks.values():
            if other.get(topic):
                return tuple(other[topic])
        return ()
    return tuple(lines)


def _fingerprint(line):
    return f"{zlib.crc32(line.encode('utf-8')):08x}"


def pick(speaker, topic, fields=None, config=None, memory=None, rng=None):
    """One line, formatted, or None when nothing fits the facts given."""
    fields = {key: value for key, value in (fields or {}).items() if value not in (None, "")}
    # Capitalised copies for sentence starts: {What}, {Words}.
    for key, value in list(fields.items()):
        if isinstance(value, str) and key[:1].islower():
            fields.setdefault(key[:1].upper() + key[1:], value[:1].upper() + value[1:])
    usable = []
    for line in lines_for(speaker, topic, config):
        if not fields_used(line) <= set(fields):
            continue
        try:
            usable.append((line, line.format(**fields)))
        except (KeyError, IndexError, ValueError):
            continue
    if not usable:
        return None
    memory = memory if memory is not None else {}
    slot = f"{speaker}:{topic}"
    heard = memory.setdefault(slot, [])
    fresh = [row for row in usable if _fingerprint(row[0]) not in heard]
    if not fresh:
        last = heard[-1:] if heard else []
        heard[:] = last
        fresh = [row for row in usable if _fingerprint(row[0]) not in heard] or usable
    line, text = (rng or random).choice(fresh)
    heard.append(_fingerprint(line))
    del heard[:-64]
    return text


def heading(speaker, topic):
    """The thought's heading for an order line."""
    if topic.startswith("offer_"):
        return "NEW ORDER"
    return {"done": "ORDER COMPLETE", "ribbon": "COMMENDATION", "stage": "CAMPAIGN", "standing": "SERVICE RECORD",
            "overtaken": "OVERTAKEN",
            "abandoned": "ORDER CANCELLED", "lapsed": "ORDER LAPSED", "reminder": "STANDING ORDERS"}.get(topic, "ORDERS")
