"""Target a system from the deck (5.8.3): the galaxy map, driven with your own
Elite key bindings, plots a route to it, and Status.json says whether it took.

The steps, at the pace of a commander doing it by hand, each one checked
against Status.json as it goes:

1. open the galaxy map (if it isn't already), wait for it (GuiFocus 6) and
   give it time to finish loading: keys pressed while it loads are lost
2. UI_Up highlights the search box and UI_Select goes into it
3. paste the name (it was put on the clipboard first)
4. UI_Select takes the first suggestion and flies the map there; that
   flight takes longer the further it is
5. a touch of zoom gives the map the focus back, and a held UI_Select plots
6. close the map with UI_Back (twice if it's still there), if it was opened
   for this, and wait for the cockpit
7. the plotted route (NavRoute.json) ends at the system, or Status.json's
   Destination is it

It stops as soon as anything else happens: another screen, the drive
charging, a jump, danger, an interdiction, or the game losing the front.
"""
from __future__ import annotations

GUI_COCKPIT, GUI_GALAXY_MAP = 0, 6
MAP_ACTIONS = {"ship": "GalaxyMapOpen", "srv": "GalaxyMapOpen_Buggy", "foot": "GalaxyMapOpen_Humanoid"}
NEEDED = ("UI_Up", "UI_Select", "UI_Back", "CamZoomIn")

MAP_WAIT_S = 5.0          # for the map to open or close (GuiFocus)
SETTLE_S = 2.0            # the map, just open, still loading: it ignores keys until it's done
OPEN_SETTLE_S = 0.4       # the map you already had open
STEP_PAUSE_S = 0.25       # between keys: back to back the map can miss one
INTO_SEARCH_S = 1.2       # after UI_Up, for the search box to light
TYPING_S = 1.3            # after going into the search box
SUGGEST_WAIT_S = 1.5      # the search lists its suggestion a moment after the name goes in
SEARCH_WAIT_S = 4.0       # the map's flight to the system, for a near one
SEARCH_WAIT_MAX_S = 8.0
SEARCH_WAIT_PER_LY = 200.0  # a second more for each this many light years
PLOT_HOLD_S = 1.2         # UI_Select held this long plots the route
PLOTTED_WAIT_S = 3.0      # the route being worked out before the map closes
VERIFY_WAIT_S = 5.0       # for NavRoute.json / Status.json after the map closes

FLAG_FSD_CHARGING, FLAG_IN_DANGER, FLAG_INTERDICTED, FLAG_FSD_JUMP = 1 << 17, 1 << 22, 1 << 23, 1 << 30
STOPPERS = ((FLAG_FSD_JUMP, "jumping"), (FLAG_FSD_CHARGING, "drive_charging"), (FLAG_INTERDICTED, "interdicted"),
            (FLAG_IN_DANGER, "danger"))

WHY = {
    "jumping": "a jump started", "drive_charging": "the drive is charging", "interdicted": "you're being interdicted",
    "danger": "you're in danger", "screen": "another screen is open", "map_stuck": "the galaxy map didn't open",
    "map_left": "the galaxy map closed part way", "cockpit_stuck": "the galaxy map didn't close",
    "lost_front": "Elite lost the front", "focus_failed": "Elite couldn't be brought to the front",
    "place_changed": "you moved between ship, SRV and on foot", "not_taken": "the game's destination didn't change to it",
    "cancelled": "it was cancelled", "binding_changed": "a key binding changed", "paste_failed": "the name couldn't be pasted",
}


def search_wait(distance_ly=None):
    """How long to let the map fly to a system ``distance_ly`` away."""
    if distance_ly is None or distance_ly < 0:
        return SEARCH_WAIT_S
    return max(SEARCH_WAIT_S, min(SEARCH_WAIT_MAX_S, SEARCH_WAIT_S + int(distance_ly // SEARCH_WAIT_PER_LY)))


def steps(where="ship", map_open=False, distance_ly=None):
    """The sequence: [{"do", ...}]. do: press/hold (action, seconds), keys
    (key, modifiers), focus (value, timeout), wait (seconds), verify."""
    out = []
    if not map_open:
        out += [{"do": "press", "action": MAP_ACTIONS[where], "label": "open the galaxy map"},
                {"do": "focus", "value": GUI_GALAXY_MAP, "timeout": MAP_WAIT_S, "label": "wait for the galaxy map"}]
    out += [{"do": "wait", "seconds": OPEN_SETTLE_S if map_open else SETTLE_S, "label": "let the map load"},
            {"do": "press", "action": "UI_Up", "label": "highlight the search"},
            {"do": "wait", "seconds": INTO_SEARCH_S, "label": "wait for the search box"},
            {"do": "press", "action": "UI_Select", "label": "into the search"},
            {"do": "wait", "seconds": TYPING_S, "label": "wait to type"},
            {"do": "keys", "key": "V", "modifiers": ("LeftControl",), "label": "paste the name"},
            {"do": "wait", "seconds": SUGGEST_WAIT_S, "label": "wait for the suggestion"},
            {"do": "press", "action": "UI_Select", "label": "fly the map there"},
            {"do": "wait", "seconds": search_wait(distance_ly), "label": "wait for the map to find it"},
            {"do": "hold", "action": "CamZoomIn", "seconds": 0.2, "label": "back to the map"},
            {"do": "wait", "seconds": 0.8, "label": "let the map take it"},
            {"do": "hold", "action": "UI_Select", "seconds": PLOT_HOLD_S, "label": "plot the route"},
            {"do": "wait", "seconds": PLOTTED_WAIT_S, "label": "let the route be worked out"}]
    if not map_open:
        out += [{"do": "press", "action": "UI_Back", "label": "close the galaxy map", "closing": True},
                {"do": "wait", "seconds": 0.6, "label": "let it close", "closing": True},
                {"do": "back_if_map", "action": "UI_Back", "label": "close the galaxy map again", "closing": True},
                {"do": "focus", "value": GUI_COCKPIT, "timeout": MAP_WAIT_S, "label": "wait for the cockpit"}]
    out.append({"do": "verify", "timeout": VERIFY_WAIT_S, "label": "check the destination"})
    return out


def actions_needed(where="ship"):
    """The Elite actions the sequence presses here (each needs a keyboard key)."""
    return (MAP_ACTIONS[where], *NEEDED)


def stopped(flags):
    """Why the flags say to stop now, or ""."""
    for flag, why in STOPPERS:
        if int(flags or 0) & flag:
            return why
    return ""


def _name(text):
    return " ".join(str(text or "").split()).casefold()


def taken(status, system, address=None):
    """Whether Status.json's Destination is the system (its address if known,
    else its name)."""
    destination = (status or {}).get("Destination") or {}
    if address is not None and destination.get("System") is not None:
        try:
            return int(destination["System"]) == int(address)
        except (TypeError, ValueError):
            pass
    return bool(destination) and _name(destination.get("Name")) == _name(system)


def route_end(navroute):
    """The last system of the route plotted in the game (NavRoute.json), or ""."""
    for hop in reversed((navroute or {}).get("Route") or ()):
        name = hop.get("StarSystem") if isinstance(hop, dict) else None
        if isinstance(name, str) and name.strip():
            return name.strip()
    return ""


def plotted(status, navroute, system, address=None):
    """The route now ends at the system (NavRoute.json, where a route of many
    jumps puts its end), or the game's destination is it (Status.json)."""
    rows = [hop for hop in (navroute or {}).get("Route") or () if isinstance(hop, dict)]
    if rows and address is not None and rows[-1].get("SystemAddress") is not None:
        try:
            if int(rows[-1]["SystemAddress"]) == int(address):
                return True
        except (TypeError, ValueError):
            pass
    end = route_end(navroute)
    return (bool(end) and _name(end) == _name(system)) or taken(status, system, address)


def clean_system(text):
    """A system name worth searching for, or ""."""
    name = " ".join(str(text or "").split())
    return name if 0 < len(name) <= 80 and not any(char in name for char in "\r\n\t") else ""
