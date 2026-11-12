"""Where your landing pad is (NEXT-VERSION #12): the pad layouts of starports and carriers, what to call a pad's place
("at the back, up on your right") and what the pad diagrams draw. Pure.

The layouts are taken from bgol's LandingPad plugin for EDMC (https://github.com/bgol/LandingPad, Copyright (c)
2018-2026 Bernd Gollesch, GNU GPL version 2 or later), used here under GPL-3.0-or-later: the starport pattern (which of
the 12 wall sectors and which depth band each of the 45 pads is in), its sector directions and depth shells, the
carriers' pad boxes, the station types each layout covers and the colonisation ships' market ids. The words, the
assumption they are said under (you come through the slot with the green lights on your right, the plugin's default)
and the drawing code are Outrider's own.

Not checked in game yet beyond the plugin's own use (DESIGN_NOTES: "Not yet tried in a live game")."""
import math
import re

# ---- which layout a station has ----

STARPORT_TYPES = frozenset({"bernal", "coriolis", "orbis", "asteroidbase", "ocellus", "dodec"})   # the journal's StationType, lower case
CARRIER_TYPES = frozenset({"fleetcarrier"})
COLONISATION_SHIP_NAME = "$EXT_PANEL_ColonisationShip"
COLONISATION_SHIP_MARKETS = frozenset({
    129032183,   # Trailblazer Dream
    129032283,   # Surveyor's Reach
    129032439,   # Trailblazer Song
    129032695,   # Trailblazer Wish
    129032951,   # Trailblazer Star
    129033207,   # Trailblazer Promise
    129033463,   # Trailblazer Faith
})
KINDS = ("starport", "fleet", "squadron", "colonisation")


def layout(station_type, station_name="", market_id=None):
    """The layout of a station a DockingGranted names: "starport", "fleet" (a fleet carrier), "squadron" (a squadron
    carrier: a four-letter name, as the plugin tells them), "colonisation" (a colonisation ship: a surface-station or
    unknown type with one of their market ids or names), or None (outposts, ports, settlements: number only)."""
    typ = str(station_type or "unknown").lower()
    name = str(station_name or "")
    if typ in ("surfacestation", "unknown") and (market_id in COLONISATION_SHIP_MARKETS
                                                 or name.startswith(COLONISATION_SHIP_NAME)):
        return "colonisation"
    if typ in STARPORT_TYPES:
        return "starport"
    if typ in CARRIER_TYPES:
        return "squadron" if len(name) == 4 else "fleet"
    return None


# ---- the starport: 45 pads round a 12-sided wall, 3 depths deep (the plugin's tables) ----

# (sector 0-3, depth 0-2) of 15 pads; pads 16-30 and 31-45 repeat it four sectors on each time
STARPORT_PATTERN = ((0, 0), (0, 0), (0, 2), (0, 2), (1, 0), (1, 0), (1, 1), (1, 2), (2, 0), (2, 2),
                    (3, 0), (3, 0), (3, 1), (3, 2), (3, 2))
STARPORT_PADS = 45
# each sector's direction as seen coming through the slot, green lights on your right: (right, down), y pointing down
_S60 = math.sqrt(3) / 2
SECTORS = ((0, 1), (-0.5, _S60), (-_S60, 0.5), (-1, 0), (-_S60, -0.5), (-0.5, -_S60),
           (0, -1), (0.5, -_S60), (_S60, -0.5), (1, 0), (_S60, 0.5), (0.5, _S60))
SHELLS = (1, 0.625, 0.455, 0.25)   # the wall's depth shells in the drawing: outside near the slot, inside the back
DEPTH_WORDS = ("near the slot", "halfway in", "at the back")


def starport_pad(n):
    """(sector 0-11, depth 0-2) of starport pad n (1-45), or None."""
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= STARPORT_PADS:
        return None
    s, d = STARPORT_PATTERN[(n - 1) % 15]
    return s + (n - 1) // 15 * 4, d


def starport_pads():
    """Every pad's [sector, depth, place, count]: place 1..count among the pads sharing that sector and depth (two
    side by side), for the drawings."""
    out, seen = [], {}
    for n in range(1, STARPORT_PADS + 1):
        s, d = starport_pad(n)
        seen[(s, d)] = seen.get((s, d), 0) + 1
        out.append([s, d, seen[(s, d)], STARPORT_PATTERN.count((s - s // 4 * 4, d))])
    return out


def side_words(sector):
    """Where a sector lies, as you look in: "up on your right", "on your left", "above you"..."""
    dx, dy = SECTORS[sector]
    up = "up" if dy < -0.3 else "down" if dy > 0.3 else ""
    if abs(dx) <= 0.3:
        return "above you" if dy < 0 else "below you"
    return f"{up} on your {'right' if dx > 0 else 'left'}".strip()


# ---- carriers: 16 pads on the deck, seen from above with the bow up (the plugin's boxes, in its units) ----

# the deck's outline around them (one per deck), bow up: Kurbo26 (2026-10-15) saw pads 7 and 8's outer corners poke
# out of the old one (its bow ran from (0, -44) to (26, -30), crossing x = 12 at y = -37.5, above the pads' top at -38);
# the peak higher and the shoulders flatter leave every pad inside with room for the line (tests/test_pads.py)
CARRIER_OUTLINE = ((-26, 40), (-26, -34), (0, -46), (26, -34), (26, 40))


def carrier_boxes(kind):
    """The pads' boxes [x, y, w, h], pad 1 first: 8 large, 4 medium, 4 small; a squadron carrier has two decks (pads
    1-16 on the starboard one as drawn, 17-32 on the port one)."""
    offsets = (26, -26) if kind == "squadron" else (0,)
    small = (-24, 14, 20, -18) if kind == "fleet" else (-24, -18, 14, 20)
    out = []
    for xo in offsets:
        out += [[x + xo, y, 10, 16] for y in (22, 2, -18, -38) for x in (-12, 2)]
        out += [[x + xo, y, 7, 11] for x in (-22, 15) for y in (25, 10)]
        out += [[x + xo, 0, 4, 6] for x in small]
    return out


def carrier_words(kind, n):
    """Where carrier pad n is on the deck: "port side, toward the bow" (a squadron carrier: which deck first). None for
    a pad the layout has not."""
    boxes = carrier_boxes(kind)
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= len(boxes):
        return None
    x, y, w, h = boxes[n - 1]
    cx, cy = x + w / 2, y + h / 2
    deck = ""
    if kind == "squadron":
        deck = "starboard deck, " if cx > 0 else "port deck, "
        cx -= 26 if cx > 0 else -26
    side = "port side" if cx < -1 else "starboard side" if cx > 1 else "on the centre line"
    end = "toward the bow" if cy < -12 else "toward the stern" if cy > 12 else "amidships"
    return f"{deck}{side}, {end}"


# ---- the words and what the drawings need ----

def where(kind, n):
    """{words (shown: "at the back · up on your right"), say (the spoken sentence, without the green lights), map (what
    the diagrams draw: {kind, pad, pads})} for pad n at a station of this layout, or None (no layout, or no such pad)."""
    if kind == "starport":
        sd = starport_pad(n)
        if not sd:
            return None
        depth, side = DEPTH_WORDS[sd[1]], side_words(sd[0])
        return {"words": f"{depth} · {side}", "say": f"{depth}, {side}",
                "map": {"kind": kind, "pad": n, "pads": starport_pads()}}
    if kind in ("fleet", "squadron", "colonisation"):
        w = carrier_words(kind, n)
        if not w:
            return None
        return {"words": w, "say": w, "map": {"kind": kind, "pad": n, "pads": carrier_boxes(kind),
                                              "outline": [list(p) for p in CARRIER_OUTLINE]}}
    return None


def spoken(info, green):
    """The sentence said after the pad's own line: "At the back, up on your right."; at a starport with `green` (the first
    docking of a session, then every GREEN_EVERY-th) the assumption first: "With the green lights on your right, it's
    at the back, up on your right." None without a place."""
    if not info or not info.get("say"):
        return None
    say = info["say"]
    if green and info["map"]["kind"] == "starport":
        return f"With the green lights on your right, it's {say}."
    return say[0].upper() + say[1:] + "."


GREEN_EVERY = 4   # the green-lights assumption is said at the first docking of a session, then every 4th (the author)

# the plugin's chat commands, typed in game to try a pad without docking: "!sppad 34" (Solo or a private group: local
# chat reaches other players)
TEST_COMMAND = re.compile(r"^!(sp|fc|sc|cs)pad\s*(\d{1,2})$", re.IGNORECASE)
TEST_KINDS = {"sp": "starport", "fc": "fleet", "sc": "squadron", "cs": "colonisation"}
TEST_NAMES = {"starport": "Test starport", "fleet": "Test fleet carrier", "squadron": "Test squadron carrier",
              "colonisation": "Test colonisation ship"}


def test_command(message):
    """(kind, pad) for a chat message that is one of the test commands, else None."""
    m = TEST_COMMAND.match(str(message or "").strip())
    return (TEST_KINDS[m.group(1).lower()], int(m.group(2))) if m else None
