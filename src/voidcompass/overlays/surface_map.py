"""The Rhino map (5.5.17): the Galaxy Minimap turns into a map of the ground
round you while you drive the Rhino on a planet (or any SRV, by choice).

You, which way you face and your trail; the ship; your rigs, with the
HERE ring, what each is working and the order to collect them; the deposits
you've marked (the journal gives no deposit positions), numbered in the
order to drive them; where your drills refined, away from them; a traced rig
plan, the planning circle, saved sites and the compass target. Everything is
in metres east and north of the ship, the frame the Planetary page's map
already uses.
"""

from __future__ import annotations

import math

# When the Rhino Map shows (5.5.18: switching it off is its Enabled switch).
MODES = ("rhino", "srv")
DEFAULT_MODE = "rhino"
ORIENTATIONS = ("heading", "north")
# Pulses this close together are the same deposit.
DEPOSIT_RADIUS_M = 40.0
MAX_DEPOSITS = 60
# The map never zooms in tighter than this each side of you, or out wider.
MIN_HALF_M = 150.0
MAX_HALF_M = 6000.0
# Its own zoom (5.5.18), apart from the minimap's: "auto" fits your rigs and
# refining spots near you; the rest are fixed ranges, metres each side of you.
RANGES = ("auto", "300", "600", "1200", "2500")
# Auto looks this far for rigs and deposits to fit; the ship, a target and
# anything further sit on the map's edge as pointers instead.
FOCUS_M = 1500.0


RANGE_NAMES = {"auto": "YOUR RIGS", "300": "300 M", "600": "600 M", "1200": "1.2 KM", "2500": "2.5 KM"}


def next_range(current):
    """The Rhino map range hotkey: round the ranges, back to Your rigs."""
    return RANGES[(RANGES.index(current) + 1) % len(RANGES)] if current in RANGES else RANGES[0]


def surface_options(config):
    config = config or {}
    mode = str(config.get("rhino_map_show") or DEFAULT_MODE).casefold()
    facing = str(config.get("rhino_map_up") or "heading").casefold()
    reach = str(config.get("rhino_map_range") or "auto").casefold()
    return {"mode": mode if mode in MODES else DEFAULT_MODE,
            "up": facing if facing in ORIENTATIONS else "heading",
            "range": reach if reach in RANGES else "auto"}


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


def map_half(you, points, reach="auto"):
    """Half the map's width in metres. A fixed range, or room for your rigs
    and deposits near you: a ship parked far off no longer zooms it out until
    the spacing rings vanish (5.5.18); it gets an edge pointer instead."""
    if reach != "auto":
        return float(reach)
    if not you:
        return MIN_HALF_M
    near = [distance for distance in (math.hypot(point[0] - you[0], point[1] - you[1]) for point in points)
            if distance <= FOCUS_M]
    return round(max(MIN_HALF_M, min(MAX_HALF_M, max(near, default=0.0) * 1.15)), 1)


SCANNER_M = 2000.0
SLOTS = 6
# A pulse spot this close to a rig or a marked deposit is that one's yield.
REFINED_OWNED_M = 250.0
DEPOSIT_OWNED_M = 60.0
# Marked deposits this close together are one patch.
PATCH_M = 150.0
DEPOSIT_FOCUS_M = 3000.0
MAX_MARKED = 40


def legal_spot(you, rigs, spacing, polygon=None):
    """The nearest place a rig can go: here if you're clear of every rig's
    spacing (and on the traced deposit), else the nearest spot that is."""
    from voidcompass.overlays.rig_planner import nearest_legal
    if not you:
        return None
    found = nearest_legal(you, rigs, spacing, polygon)
    if found is None:
        return None
    distance = math.hypot(found[0] - you[0], found[1] - you[1])
    if distance < .5:
        return {"at": list(you), "distance": 0, "here": True}
    return {"at": [round(found[0], 1), round(found[1], 1)], "distance": max(1, round(distance)), "here": False,
            "bearing": _bearing(you, found)}


def primary_material(materials):
    """The deposit's commodity: the first of its materials."""
    if isinstance(materials, (list, tuple)):
        materials = ", ".join(str(item) for item in materials)
    return str(materials or "").replace(";", ",").split(",", 1)[0].strip()


def marked_deposits(sites, plane, you=None):
    """Your marked deposits on this body, nearest first, the live ones
    numbered in the order to drive them."""
    out = []
    for row in sites or ():
        try:
            point = plane((float(row["latitude"]), float(row["longitude"])))
        except (KeyError, TypeError, ValueError):
            continue
        commodity = primary_material(row.get("materials"))
        if not commodity or str(row.get("site_type") or "site") != "site":
            continue
        depleted = bool(row.get("depleted")) or str(row.get("amount") or "") == "Depleted"
        item = {"id": row.get("id"), "at": point, "commodity": commodity, "rigs": int(row.get("rigs") or 0),
                "amount": str(row.get("amount") or ""), "density": str(row.get("density") or ""), "depleted": depleted,
                "signal": row.get("location_index")}
        if depleted:
            from voidcompass.mining.regrowth import standing
            info = standing(row)
            item.update(due=info["due"], regrowth=info["text"])
        if you:
            item["distance"] = round(math.hypot(point[0] - you[0], point[1] - you[1]))
            item["bearing"] = _bearing(you, point)
        out.append(item)
    if you:
        out.sort(key=lambda item: item["distance"])
        here, left = you, [item for item in out if not item["depleted"] and item["distance"] <= DEPOSIT_FOCUS_M]
        number = 1
        while left:
            nearest = min(left, key=lambda item: math.hypot(item["at"][0] - here[0], item["at"][1] - here[1]))
            nearest["n"] = number
            number += 1
            here = nearest["at"]
            left.remove(nearest)
    return out[:MAX_MARKED]


def deposit_patch(deposits, you=None):
    """The best group of marked deposits: the most rigs, then the most
    different commodities, within PATCH_M of each other."""
    live = [item for item in deposits or () if not item.get("depleted")]
    best = None
    for seed in live:
        group = [item for item in live if math.hypot(item["at"][0] - seed["at"][0], item["at"][1] - seed["at"][1]) <= PATCH_M]
        rigs = sum(max(1, item["rigs"]) for item in group)
        kinds = []
        for item in group:
            if item["commodity"] not in kinds:
                kinds.append(item["commodity"])
        key = (rigs, len(kinds), len(group))
        if len(group) >= 2 and (best is None or key > best[0]):
            x = sum(item["at"][0] for item in group) / len(group)
            y = sum(item["at"][1] for item in group) / len(group)
            best = (key, {"at": [round(x, 1), round(y, 1)], "rigs": rigs, "deposits": len(group),
                          "materials": kinds[:4], "marked": True})
    if not best:
        return None
    patch = best[1]
    if you:
        patch["distance"] = round(math.hypot(patch["at"][0] - you[0], patch["at"][1] - you[1]))
        patch["bearing"] = _bearing(you, patch["at"])
    return patch


def traced_plan(record, plane, rigs, spacing, you=None):
    """A kept rig plan in the map's frame: its edge, and its pins in order,
    each filled once a rig is down within half the spacing of it."""
    if not record:
        return None, []
    outline = [plane(tuple(point)) for point in record.get("outline") or ()]
    pins, waiting = [], None
    for number, point in enumerate(record.get("pins") or (), start=1):
        at = plane(tuple(point))
        filled = any(math.hypot(at[0] - rig[0], at[1] - rig[1]) <= spacing / 2 for rig in rigs)
        pin = {"n": number, "at": at, "filled": filled}
        if you:
            pin["distance"] = round(math.hypot(at[0] - you[0], at[1] - you[1]))
            pin["bearing"] = _bearing(you, at)
        if not filled and waiting is None:
            waiting = pin
            pin["next"] = True
        pins.append(pin)
    return {"outline": outline, "fits": int(record.get("fits") or len(pins)), "middle": record.get("middle")}, pins


def build_surface_map(plane_map, plane, *, rig_model=None, rig_points=None, here_m=40.0, spots=(),
                      signals=0, vehicle="", options=None, spacing_m=78.0, warn_m=3500.0, survey=None,
                      sites=(), plan_record=None, circle=None, trace=None, signal=None, prices=None, per_rig=None):
    """The Rhino map's model. ``plane_map`` is the Planetary page's map
    (``_planetary_map``), ``plane`` its lat/lon → metres frame, ``rig_points``
    ``{slot: (lat, lon)}``, ``spots`` the refining pulses on this body,
    ``survey`` the body's survey (rhino_survey.SurveyStore.survey), ``sites``
    the marked deposits (planet-materials rows), ``plan_record`` the kept
    rig plan here, ``circle`` the planning circle's (lat, lon) and ``trace``
    the edge being traced, as (lat, lon) points."""
    from voidcompass.overlays import rhino_survey
    from voidcompass.overlays.rig_planner import CIRCLE_M, radar
    from voidcompass.overlays.rig_tracker import rig_advice
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
                     "nearest": bool(row.get("nearest")), "age_s": row.get("age_s"),
                     "commodity": row.get("commodity") or "", "tonnes": int(row.get("tonnes") or 0)})
    order = list((rig_model or {}).get("order") or [])
    advice = rig_advice((rig_model or {}).get("slots"), spacing_m, warn_m)
    for rig in rigs:
        rig["ready"] = rig["slot"] in advice["ready"]
    centres = [rig["at"] for rig in rigs]
    deposits = marked_deposits(sites, plane, you)
    for item in deposits:
        item["value"] = deposit_value(item, prices, per_rig)
    # A rig on a marked deposit is working that deposit.
    for rig in rigs:
        if not rig["commodity"]:
            home = min(deposits, key=lambda item: math.hypot(item["at"][0] - rig["at"][0], item["at"][1] - rig["at"][1]), default=None)
            if home and math.hypot(home["at"][0] - rig["at"][0], home["at"][1] - rig["at"][1]) <= DEPOSIT_OWNED_M:
                rig["commodity"] = home["commodity"]
    refined = [item for item in cluster_deposits(spots, plane)
               if not any(math.hypot(item["at"][0] - point[0], item["at"][1] - point[1]) <= REFINED_OWNED_M for point in centres)
               and not any(math.hypot(item["at"][0] - other["at"][0], item["at"][1] - other["at"][1]) <= DEPOSIT_OWNED_M
                           for other in deposits)]
    target = plane_map.get("target")
    sites_left = [site for site in list(plane_map.get("sites") or [])
                  if not any(site.get("id") is not None and site.get("id") == item["id"] for item in deposits)][:30]
    patch = deposit_patch(deposits, you) or rhino_survey.best_patch(cluster_deposits(spots, plane), you)
    traced, pins = traced_plan(plan_record, plane, centres, spacing_m, you)
    polygon = traced["outline"] if traced and len(traced["outline"]) >= 3 else None
    if pins:
        plan = pins
    else:
        first = next((rig["at"] for slot in order for rig in rigs if rig["slot"] == slot), None) or (centres[0] if centres else None)
        anchor = first or (patch or {}).get("at")
        plan = rhino_survey.rig_plan(anchor, centres, spacing_m, you, warn_m=warn_m) if anchor else []
    verdict = radar(you, centres, spacing_m, polygon) if you and (rigs or polygon) else None
    spot = None
    if verdict and verdict["state"] in ("close",):
        spot = {"at": verdict["legal"], "distance": verdict["need_m"], "here": False, "bearing": verdict["bearing"]}
    elif verdict and verdict["state"] in ("ok", "edge") and rigs:
        spot = {"at": list(you), "distance": 0, "here": True}
    planned = next((row for row in plan if row.get("next")), None)
    if planned and (rigs or pins) and "distance" in planned:
        spot = {"at": planned["at"], "distance": planned["distance"], "here": planned["distance"] < spacing_m / 4,
                "bearing": planned["bearing"], "planned": True, "pin": planned.get("n")}
    area = rhino_survey.survey_model(survey, plane, you) if survey else None
    ring = None
    if circle:
        centre = plane(tuple(circle))
        room = CIRCLE_M - (math.hypot(centre[0] - you[0], centre[1] - you[1]) if you else 0.0)
        ring = {"at": centre, "radius_m": CIRCLE_M, "room": round(room)}
    focus = centres + [item["at"] for item in refined[:12]] + [item["at"] for item in deposits[:12] if not item["depleted"]]
    focus += [pin["at"] for pin in pins]
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
        "next_deposit": next((item for item in deposits if item.get("n") == 1), None),
        "refined": refined,
        "sites": sites_left,
        "target": target,
        "here_m": float(here_m),
        "spacing_m": float(spacing_m),
        "warn_m": float(warn_m),
        "too_close": advice["too_close"],
        "too_far": advice["too_far"],
        "radar": {"state": verdict["state"], "rings": [row["state"] for row in verdict["rings"]]} if verdict else None,
        "next_spot": spot,
        "best_patch": patch,
        "groups": golden_groups(deposits, prices, per_rig, you),
        "lines": nearest_lines(deposits, prices, next((rig["commodity"] for rig in rigs if rig["commodity"]), "")),
        "value": patch_value(deposits, prices, per_rig, you),
        "plan": plan,
        "traced": traced,
        "tracing": [plane(tuple(point)) for point in trace or ()][-600:] or None,
        "circle": ring,
        "survey": area,
        "scanner_m": SCANNER_M,
        "signals": int(signals or 0),
        "signal": signal,
        "half_m": map_half(you, focus, options.get("range", "auto")),
        "range": RANGE_NAMES.get(options.get("range", "auto"), "YOUR RIGS"),
        "up": options["up"],
    }
    return model


def _metres_text(value):
    value = float(value or 0)
    return f"{value / 1000:.1f} KM" if value >= 1000 else f"{round(value)} M"


def rig_words(surface):
    """(text, tone) for where the next rig can go, as every Rhino view says it;
    None when there's nothing to say. Tones: red, accent, green, yellow, text."""
    if not surface:
        return None
    rigs = surface.get("rigs") or []
    far = (surface.get("too_far") or [None])[0]
    if far:
        return f"RIG {far['slot']} {float(far['distance']) / 1000:.1f} KM · LOST AT 5 KM", "red"
    ready = next((rig for rig in rigs if rig.get("ready")), None)
    if ready:
        return f"COLLECT RIG {ready['slot']}", "accent"
    state = (surface.get("radar") or {}).get("state")
    spot = surface.get("next_spot") or {}
    if state == "full" or len(rigs) >= SLOTS:
        return f"ALL {SLOTS} RIGS DOWN", "text"
    if state == "close" and spot:
        return f"TOO CLOSE · NEXT RIG {_metres_text(spot.get('distance'))} · {round(float(spot.get('bearing') or 0)) % 360:03d}°", "yellow"
    if state == "none":
        return "NO ROOM FOR A RIG HERE", "red"
    if spot.get("planned") and not spot.get("here"):
        return f"RIG P{spot.get('pin') or ''} {_metres_text(spot.get('distance'))} · {round(float(spot.get('bearing') or 0)) % 360:03d}°", "text"
    if state == "edge":
        return "RIG OK HERE · JUST", "yellow"
    if state == "ok" or spot.get("here"):
        return "RIG OK HERE", "green"
    return None


# -- what a patch is worth --------------------------------------------------------
# A deposit's worth is its rigs x what a worked rig gives you (measured from
# your own collected rigs) x what that commodity sells for. With no measured
# figure yet there is no value: an invented number is worse than none.
GROUP_RADIUS_M = 1250.0
GROUP_RIGS = 5
GROUP_RIGS_FALLBACK = 4
GROUPS_SHOWN = 3
SPOT_S = 300.0
DRIVE_KMH = 25.0
LINE_SKIP_M = 20.0


def _fold(name):
    return "".join(char for char in str(name or "").casefold() if char.isalnum())


def price_of(name, prices):
    if not name or not prices:
        return None
    if name in prices:
        return float(prices[name] or 0) or None
    wanted = _fold(name)
    for key, value in prices.items():
        if _fold(key) == wanted:
            return float(value or 0) or None
    return None


def deposit_value(item, prices, per_rig):
    """Credits for one live deposit, or None when there's no pricing it."""
    if item.get("depleted") or not per_rig or not item.get("rigs"):
        return None
    price = price_of(item.get("commodity"), prices)
    return round(min(6, int(item["rigs"])) * per_rig * price) if price else None


def drive_route(items, start):
    """Nearest-next through the live deposits: (order, metres)."""
    left = [item for item in items if not item.get("depleted")]
    here, order, total = start, [], 0.0
    while left:
        nearest = min(left, key=lambda item: math.hypot(item["at"][0] - here[0], item["at"][1] - here[1]))
        total += math.hypot(nearest["at"][0] - here[0], nearest["at"][1] - here[1])
        here = nearest["at"]
        order.append(nearest)
        left.remove(nearest)
    return order, total


def golden_groups(deposits, prices, per_rig, you, radius_m=GROUP_RADIUS_M, limit=GROUPS_SHOWN):
    """The best knots of live deposits: five rigs' worth or more within
    ``radius_m`` of one of them (four when none reach five), each site in one
    group. Each says its rigs, what it's worth and what that comes to an hour
    (five minutes at every deposit plus the drive at 25 km/h). The best by
    Cr/h are kept (by rigs before there's a value), then listed most rigs first."""
    live = [item for item in deposits or () if not item.get("depleted") and item.get("rigs")]
    if not live or not you:
        return []
    near = [[(i, 0.0)] for i in range(len(live))]
    for i, first in enumerate(live):
        for j in range(i + 1, len(live)):
            apart = math.hypot(live[j]["at"][0] - first["at"][0], live[j]["at"][1] - first["at"][1])
            if apart <= radius_m:
                near[i].append((j, apart))
                near[j].append((i, apart))
    left, groups = set(range(len(live))), []
    rigs_of = lambda index: min(6, int(live[index]["rigs"]))
    while left:
        best = None
        for i in sorted(left):
            members = [(j, apart) for j, apart in near[i] if j in left]
            key = (-sum(rigs_of(j) for j, _apart in members), max(apart for _j, apart in members), i)
            if best is None or key < best[0]:
                best = (key, i, [j for j, _apart in members])
        if -best[0][0] < GROUP_RIGS_FALLBACK:
            break
        groups.append((best[1], best[2], -best[0][0]))
        left -= set(best[2])
    floor = GROUP_RIGS if any(rigs >= GROUP_RIGS for _c, _m, rigs in groups) else GROUP_RIGS_FALLBACK
    found = []
    for centre, members, rigs in groups:
        if rigs < floor:
            continue
        items = [live[index] for index in members]
        values = [deposit_value(item, prices, per_rig) for item in items]
        credits = sum(value for value in values if value)
        _order, metres = drive_route(items, you)
        seconds = SPOT_S * len(items) + metres / (DRIVE_KMH / 3.6)
        middle = live[centre]["at"]
        reach = max(math.hypot(item["at"][0] - middle[0], item["at"][1] - middle[1]) for item in items)
        kinds = []
        for item in items:
            if item["commodity"] not in kinds:
                kinds.append(item["commodity"])
        found.append({"at": list(middle), "reach_m": round(reach), "rigs": rigs, "deposits": len(items),
                      "credits": credits or None, "unpriced": sum(1 for value in values if not value),
                      "cr_per_h": round(credits * 3600 / seconds) if credits and seconds else None,
                      "distance": round(math.hypot(middle[0] - you[0], middle[1] - you[1])),
                      "bearing": _bearing(you, middle), "materials": kinds[:4]})
    if any(group["cr_per_h"] for group in found):
        found.sort(key=lambda group: (-(group["cr_per_h"] or 0), -group["rigs"], group["distance"]))
    else:
        found.sort(key=lambda group: (-group["rigs"], group["distance"]))
    found = found[:limit]
    found.sort(key=lambda group: (-group["rigs"], -(group["cr_per_h"] or 0), group["distance"]))
    for number, group in enumerate(found, start=1):
        group["n"] = number
    return found


def nearest_lines(deposits, prices, focus=""):
    """From you: the nearest deposit of ``focus`` (or the best-paying
    commodity in view), and the nearest of the next cheaper commodity.
    {"commodity", "same": {"at", "distance", "commodity"} or None, "cheaper": the same}."""
    out = {"commodity": "", "same": None, "cheaper": None}
    live = [item for item in deposits or () if not item.get("depleted") and item.get("commodity") and "distance" in item]
    if not live:
        return out
    names = {}
    for item in live:
        names.setdefault(_fold(item["commodity"]), item["commodity"])
    wanted = _fold(focus)
    if not wanted or wanted not in names:
        priced = [(price_of(name, prices) or 0, flat) for flat, name in names.items()]
        best = max(priced) if priced else (0, "")
        wanted = best[1] if best[0] else ""
    if not wanted:
        return out
    out["commodity"] = names[wanted]

    def nearest(flat):
        pool = [item for item in live if _fold(item["commodity"]) == flat and item["distance"] >= LINE_SKIP_M]
        item = min(pool, key=lambda row: row["distance"]) if pool else None
        return {"at": item["at"], "distance": item["distance"], "commodity": item["commodity"]} if item else None

    out["same"] = nearest(wanted)
    base = price_of(names[wanted], prices)
    if base:
        cheaper = sorted(((price_of(name, prices) or 0, flat) for flat, name in names.items() if flat != wanted), reverse=True)
        for price, flat in cheaper:
            if 0 < price < base:
                found = nearest(flat)
                if found:
                    out["cheaper"] = found
                    break
    return out


def patch_value(deposits, prices, per_rig, you):
    """The whole picture: live deposits, their rigs, an estimate of what
    they're worth (and how many had no price) and the drive through them."""
    live = [item for item in deposits or () if not item.get("depleted")]
    values = [deposit_value(item, prices, per_rig) for item in live]
    _order, metres = drive_route(live, you) if you else ([], 0.0)
    return {"deposits": len(live), "rigs": sum(min(6, int(item.get("rigs") or 0)) for item in live),
            "credits": sum(value for value in values if value) or None,
            "unpriced": sum(1 for value in values if not value), "route_m": round(metres),
            "per_rig": per_rig}
