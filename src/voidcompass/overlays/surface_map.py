"""The Rhino map (5.5.17): the Galaxy Minimap turns into a map of the ground
round you while you drive the Rhino on a planet (or any SRV, by choice).

You, which way you face and your trail; the ship; your rigs, with the
HERE ring and the order to collect them; where your drills have refined
(the journal gives no deposit positions, so it's where you were for each
pulse); saved sites and the compass target. Everything is in metres east and
north of the ship, the frame the Planetary page's map already uses.
"""

from __future__ import annotations

import math

MODES = ("rhino", "srv", "off")
DEFAULT_MODE = "rhino"
ORIENTATIONS = ("heading", "north")
# Pulses this close together are the same deposit.
DEPOSIT_RADIUS_M = 40.0
MAX_DEPOSITS = 60
# The map never zooms in tighter than this each side of you, or out wider.
MIN_HALF_M = 150.0
MAX_HALF_M = 6000.0


def surface_options(config):
    config = config or {}
    mode = str(config.get("galaxy_minimap_surface") or DEFAULT_MODE).casefold()
    facing = str(config.get("galaxy_minimap_surface_up") or "heading").casefold()
    return {"mode": mode if mode in MODES else DEFAULT_MODE,
            "up": facing if facing in ORIENTATIONS else "heading"}


def wants_surface(mode, *, on_planet, in_srv, vehicle="", on_foot=False, rigs_here=False):
    """Whether the minimap should be the ground map right now: in the Rhino
    (or any SRV), and whenever your rigs are out on this planet, on foot or
    in the ship."""
    if not on_planet or mode == "off":
        return False
    if rigs_here:
        return True
    if mode == "srv":
        return bool(in_srv or on_foot)
    return bool(in_srv) and str(vehicle or "").upper() == "RHINO"


def cluster_deposits(spots, plane, radius_m=DEPOSIT_RADIUS_M):
    """Refining pulses ``[(lat, lon, material), ...]`` gathered into
    deposits: ``[{"at": [x, y], "pulses": n, "materials": [...]}]``."""
    deposits = []
    for lat, lon, material in spots:
        point = plane((lat, lon))
        home = next((item for item in deposits
                     if math.hypot(item["at"][0] - point[0], item["at"][1] - point[1]) <= radius_m), None)
        if home is None:
            deposits.append({"at": list(point), "pulses": 1, "materials": [material] if material else []})
            continue
        count = home["pulses"]
        home["at"] = [round((home["at"][0] * count + point[0]) / (count + 1), 1),
                      round((home["at"][1] * count + point[1]) / (count + 1), 1)]
        home["pulses"] = count + 1
        if material and material not in home["materials"]:
            home["materials"].append(material)
    deposits.sort(key=lambda item: -item["pulses"])
    return deposits[:MAX_DEPOSITS]


def _bearing(origin, point):
    return round(math.degrees(math.atan2(point[0] - origin[0], point[1] - origin[1])) % 360.0, 1)


def map_half(you, points):
    """Half the map's width in metres: room for what matters round you."""
    if not you:
        return MIN_HALF_M
    far = max((math.hypot(point[0] - you[0], point[1] - you[1]) for point in points), default=0.0)
    return round(max(MIN_HALF_M, min(MAX_HALF_M, far * 1.15)), 1)


SCANNER_M = 2000.0
SLOTS = 6


def legal_spot(you, rigs, spacing):
    """The nearest place a rig can go: here if you're clear of every rig's
    spacing, else the nearest point just outside the rings (after EDSMT)."""
    if not you:
        return None
    clear = lambda point: all(math.hypot(point[0] - rig[0], point[1] - rig[1]) >= spacing - .5 for rig in rigs)
    if clear(you):
        return {"at": list(you), "distance": 0, "here": True}
    best = None
    for rig in rigs:
        for step in range(72):
            angle = step * math.tau / 72
            point = [rig[0] + math.cos(angle) * (spacing + 1), rig[1] + math.sin(angle) * (spacing + 1)]
            if not clear(point):
                continue
            distance = math.hypot(point[0] - you[0], point[1] - you[1])
            if best is None or distance < best[0]:
                best = (distance, point)
    if best is None:
        return None
    return {"at": [round(best[1][0], 1), round(best[1][1], 1)], "distance": round(best[0]), "here": False,
            "bearing": _bearing(you, best[1])}


def build_surface_map(plane_map, plane, *, rig_model=None, rig_points=None, here_m=40.0, spots=(),
                      signals=0, vehicle="", options=None, spacing_m=78.0, warn_m=3500.0):
    """The minimap's ground view. ``plane_map`` is the Planetary page's map
    (``_planetary_map``), ``plane`` its lat/lon → metres frame, ``rig_points``
    ``{slot: (lat, lon)}``, ``spots`` the refining pulses on this body."""
    options = dict(options or surface_options({}))
    you = (plane_map.get("you") or {}).get("at")
    heading = (plane_map.get("you") or {}).get("heading")
    # In the ship, you are the ship: no second marker where it last landed.
    ship = None if str(vehicle or "").upper() == "SHIP" else (plane_map.get("ship") or {}).get("at")
    rows = {row["slot"]: row for row in (rig_model or {}).get("slots") or () if row.get("tracked")}
    rigs = []
    for slot, point in sorted((rig_points or {}).items()):
        row = rows.get(slot) or {}
        rigs.append({"slot": int(slot), "at": plane(point), "distance": row.get("distance_m"), "here": bool(row.get("here")),
                     "nearest": bool(row.get("nearest")), "age_s": row.get("age_s")})
    order = list((rig_model or {}).get("order") or [])
    from voidcompass.overlays.rig_tracker import rig_advice
    advice = rig_advice((rig_model or {}).get("slots"), spacing_m, warn_m)
    for rig in rigs:
        rig["ready"] = rig["slot"] in advice["ready"]
    # Where the next rig can go, while there's one left to put down.
    spot = legal_spot(you, [rig["at"] for rig in rigs], spacing_m) if rigs and len(rigs) < SLOTS else None
    deposits = cluster_deposits(spots, plane)
    target = plane_map.get("target")
    sites = list(plane_map.get("sites") or [])[:30]
    focus = [ship] if ship else []
    focus += [rig["at"] for rig in rigs] + [item["at"] for item in deposits[:12]]
    if target:
        focus.append(target["at"])
    model = {
        "body": str(plane_map.get("body") or ""),
        "vehicle": str(vehicle or "").upper(),
        "you": {"at": you, "heading": heading} if you else None,
        "ship": {"at": ship, "distance": round(math.hypot(ship[0] - you[0], ship[1] - you[1])) if you else None,
                 "bearing": _bearing(you, ship) if you else None} if ship else None,
        "trail": list(plane_map.get("trail") or [])[-400:],
        "rigs": rigs,
        "next_rig": order[0] if order else None,
        "order": order,
        "deposits": deposits,
        "sites": sites,
        "target": target,
        "here_m": float(here_m),
        "spacing_m": float(spacing_m),
        "warn_m": float(warn_m),
        "too_close": advice["too_close"],
        "too_far": advice["too_far"],
        "next_spot": spot,
        "scanner_m": SCANNER_M,
        "signals": int(signals or 0),
        "half_m": map_half(you, focus),
        "up": options["up"],
    }
    return model
