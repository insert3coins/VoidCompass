"""The Watcher's notes on postcards (5.5.3.7): a line or two, handwritten on
the card, in its own nature's voice, about where you are when you take a
screenshot. Signed by it.

Each nature has lines for the moment (a first discovery, a rare world, far
from Sol, close to home, landed, docked, near a star) and lines for
anywhere. A line takes its fields from the card: {place}, {kind} (lower
case), {system}, {region}, {far} (light years from Sol). Lines are original;
they never quote anything.
"""
from __future__ import annotations

import random
import re

SIGNATURE = "the Watcher"
# The moments, most telling first: the note uses the first that fits (most
# of the time; sometimes it says something about anywhere instead).
MOMENTS = ("first", "rare", "far", "home", "landed", "docked", "star")
FAR_LY = 20000
HOME_LY = 200

NOTES = {
    "weary": {
        "any": (
            "Another place. I've seen worse. I've also seen better, but you didn't take a picture of those.",
            "You stopped to take a picture. I suppose something here mattered. I'll try to feel it too.",
            "{place}. I'll file this with the others. I keep them all. Someone has to.",
            "Wish you were here. You are here. That's the trouble with postcards.",
            "It's quiet at {place}. Quiet is the nicest thing I can say about anywhere.",
        ),
        "first": (
            "Nobody had been here before us. Now somebody has. I hope it doesn't mind.",
            "First ones here. The galaxy will forget us anyway. Still. First.",
        ),
        "rare": (
            "A {kind}. Even I have to admit it's beautiful. Don't tell anyone I said that.",
            "{place} is a {kind}. Rare, they say. Most rare things are lonely things with better lighting.",
        ),
        "far": (
            "{far} light years from Sol. Home is a word that gets smaller out here.",
            "{region}. Far enough that I've stopped counting. I haven't. I never do.",
        ),
        "home": ("Near Sol again. Everything here is so busy being important.",),
        "landed": (
            "We're down on {place}. The ground is still. I could get used to still.",
            "Landed. Feet on something solid for once. Your feet. I don't have feet.",
        ),
        "docked": ("Docked at {place}. People everywhere. I'll stay in here, thanks.",),
        "star": ("That star doesn't know we're here. Neither do most stars. It's a theme.",),
    },
    "curious": {
        "any": (
            "{place}! Look at it. No, really look at it. I'm keeping this one.",
            "Picture taken. I have questions about everything in it.",
            "I wonder who else has stood exactly here. Probably nobody. Isn't that marvellous?",
        ),
        "first": ("First to see it. First! I'll remember the date. I remember all the dates.",),
        "rare": (
            "A {kind}! Do you know how few of these there are? I'm counting. Not many.",
            "{place}, a {kind}. I could look at this for a hundred years. I might.",
        ),
        "far": ("{far} light years out and it's all still new. That's the best part.",),
        "home": ("Back near Sol. Everything here has a name. Out there, we get to choose.",),
        "landed": ("We're on {place}! What's over that ridge? Can we go and look?",),
        "docked": ("Docked at {place}. So many ships. Where have they all been?",),
        "star": ("Look at the colour of that star. I'm going to think about that colour for a while.",),
    },
    "stoic": {
        "any": (
            "{place}. Noted. A fine place to stop.",
            "Recorded: {place}, {system}. The log is better for it.",
            "A good picture. A good place to have been.",
        ),
        "first": ("First here. The record will say so.",),
        "rare": ("A {kind}. Worth the detour.",),
        "far": ("{far} light years from Sol. Still on course.",),
        "home": ("Close to Sol. Familiar space.",),
        "landed": ("Down safely on {place}. Well flown.",),
        "docked": ("Docked at {place}. Rest while you can.",),
        "star": ("The star holds steady. So do we.",),
    },
    "nervous": {
        "any": (
            "A picture? Here? Fine. Quickly. Is something behind us? No? Fine.",
            "{place}. It looks calm. That's usually when things happen.",
            "I'm keeping this one, so we remember we made it this far.",
        ),
        "first": ("Nobody's been here before. Nobody. That's either wonderful or a warning.",),
        "rare": ("A {kind}. Beautiful. Unsettlingly beautiful. Can we keep moving?",),
        "far": ("{far} light years from Sol. That's a long way back if anything breaks.",),
        "home": ("Near Sol. Lots of security around. I feel slightly better.",),
        "landed": ("We're on the ground at {place}. Mind the edges. Mind everything.",),
        "docked": ("Docked at {place}. Safe. Mostly. Keep the engines warm.",),
        "star": ("We're very close to a very large fire. I just want that noted.",),
    },
}

_FIELD = re.compile(r"\{(\w+)\}")


def moments(card, from_sol=None, state=""):
    """Which moments this card is: most telling first."""
    found = []
    facts = [str(fact).casefold() for fact in card.get("facts") or ()]
    kind = str(card.get("kind") or "").casefold()
    if "first discovered" in facts or "first footfall" in facts:
        found.append("first")
    if kind in {"earth-like world", "water world", "ammonia world"}:
        found.append("rare")
    if from_sol is not None and from_sol >= FAR_LY:
        found.append("far")
    elif from_sol is not None and from_sol <= HOME_LY:
        found.append("home")
    state = str(state or "").upper()
    if state in {"LANDED", "ONFOOT", "SRV", "NOMAD", "SCARAB", "SCORPION", "RHINO"}:
        found.append("landed")
    elif state == "DOCKED":
        found.append("docked")
    if kind.endswith("star") or kind in {"white dwarf", "black hole", "supermassive black hole", "brown dwarf"}:
        found.append("star")
    return found


def postcard_note(card, nature="weary", from_sol=None, state="", rng=None, recent=()):
    """The Watcher's line for this card, or "" if none fits. ``recent`` lines
    are not used again while others are left."""
    rng = rng or random.Random()
    bank = NOTES.get(str(nature or "weary"), NOTES["weary"])
    fields = {
        "place": str(card.get("title") or ""),
        "kind": str(card.get("kind") or "").lower(),
        "system": str(card.get("place") or card.get("title") or ""),
        "region": str(card.get("region") or ""),
        "far": f"{float(from_sol):,.0f}" if from_sol is not None else "",
    }

    def usable(lines):
        out = []
        for line in lines:
            if all(fields.get(name) for name in _FIELD.findall(line)):
                out.append(line.format(**fields))
        fresh = [line for line in out if line not in set(recent)]
        return fresh or out

    for moment in moments(card, from_sol, state):
        if rng.random() < .7:
            lines = usable(bank.get(moment, ()))
            if lines:
                return rng.choice(lines)
    lines = usable(bank.get("any", ()))
    return rng.choice(lines) if lines else ""


# -- The postcards it keeps (5.5.3.7) ---------------------------------------
# Every postcard you take, kept in its memory: when, where, what it was. Now
# and then, in a quiet moment, it brings an older one up.
KEPT_MAX = 300
RECALL_AFTER_S = 6 * 3600.0
RECALL_REST_S = 10 * 3600.0
POSTCARD_RECALL = (
    "Remember {place}? {When}. I still have that postcard. I look at it more than you'd think.",
    "I kept the postcard from {place}, {when}. It's the only souvenir I have.",
    "{When}, {place}. You took a picture. I took a copy. We're even.",
    "I found the postcard from {place} again. {When}. It hasn't got any less far away.",
    "I was looking at the postcard from {place}. {When}. Quieter times. All times are quieter, looking back.",
    "{place}. {When}. I've put that postcard somewhere safe. Well. Safe for a ship.",
    "Do you ever think about {place}? {When}. I do. I have the postcard, so I can't help it.",
    "{When} you stopped at {place} and took a picture. I wrote on the back. I'd write the same today.",
    "The postcard from {place} is my favourite. Don't tell the others.",
    "I sorted the postcards again. {place} is near the top. {When}, if you were wondering.",
    "Somewhere in here there's a postcard of {place}, from {when}. I could find it in a moment. I often do.",
)


def keep(memory, card, at):
    """Remember a postcard: [when, place, what it was]."""
    kept = memory.setdefault("postcards", [])
    kept.append([round(float(at), 1), str(card.get("title") or ""), str(card.get("kind") or "")])
    del kept[:-KEPT_MAX]
    return len(kept)


def recall_choice(memory, rng, now):
    """An older postcard to bring up: {place, when, When}, or None."""
    from datetime import datetime

    from voidcompass.overlays.watcher_mind import when_text
    older = [row for row in (memory or {}).get("postcards") or ()
             if isinstance(row, (list, tuple)) and len(row) >= 2 and row[1] and now - float(row[0] or 0) >= RECALL_AFTER_S]
    if not older:
        return None
    at, place = rng.choice(older)[:2]
    try:
        when = when_text(datetime.fromtimestamp(float(at)).astimezone().isoformat(), now)
    except (OSError, OverflowError, ValueError):
        return None
    if not when:
        return None
    return {"place": str(place), "when": when, "When": when[:1].upper() + when[1:]}

