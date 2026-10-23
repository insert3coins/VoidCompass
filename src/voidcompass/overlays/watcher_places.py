"""Places the Watcher asks to be taken (5.6.1): pilgrimages.

At points in Book Four a chapter waits for a kind of place, never a fixed
system. The Watcher asks to be taken there; an expedition can make it an
objective; the journal says when you've arrived. Each kind is read from the
journal alone.
"""

from __future__ import annotations

import math

# Sagittarius A*, the heart of the galaxy.
CORE = (25.21875, -20.90625, 25899.96875)
CORE_LY = 1000.0
# Far out on the rim: Beagle Point is about 39,400 ly from the core.
EDGE_LY = 38000.0
BLACK_HOLES = {"H", "SUPERMASSIVEBLACKHOLE"}

# kind: (how the Watcher says it, how you find it)
PLACES = {
    "black_hole": ("a black hole", "Any black hole: a star of class H on the galaxy map"),
    "core": ("the heart of the galaxy", "Within 1,000 ly of Sagittarius A*"),
    "edge": ("the edge of the galaxy", "38,000 ly or more from the galactic core, like Beagle Point"),
    "first_place": ("where you first switched me on", "The system the Watcher first woke in"),
    "undiscovered": ("somewhere nobody has ever been", "A system whose main star nobody had discovered"),
}


def _position(value):
    try:
        return [float(value[index]) for index in range(3)]
    except (TypeError, ValueError, IndexError):
        return None


def place_of(event, raw):
    """The kind of place this journal event shows you've reached, or None.
    (Where it first woke is the mind's to know: it remembers the system.)"""
    raw = raw if isinstance(raw, dict) else {}
    if event == "Scan":
        star = str(raw.get("StarType") or "").upper()
        if star in BLACK_HOLES:
            return "black_hole"
        try:
            main_star = float(raw.get("DistanceFromArrivalLS") or 0) == 0 and star
        except (TypeError, ValueError):
            main_star = False
        if main_star and raw.get("WasDiscovered") is False:
            return "undiscovered"
        return None
    if event in {"FSDJump", "Location", "CarrierJump"}:
        here = _position(raw.get("StarPos"))
        if here is None:
            return None
        far = math.dist(here, CORE)
        if far <= CORE_LY:
            return "core"
        if far >= EDGE_LY:
            return "edge"
    return None


def words(kind):
    return PLACES.get(kind, ("somewhere", ""))[0]


def how(kind):
    return PLACES.get(kind, ("", ""))[1]
