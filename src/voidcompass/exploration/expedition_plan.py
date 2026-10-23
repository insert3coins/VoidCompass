"""Expedition planning (5.6.1): the sums behind the Expeditions page.

An expedition's route is its legs, in order after the start: stops, the
destination and the way home. These helpers work out how far along you are,
what a plotted leg asks of your fuel, how long the rest will take at your own
pace, and what to bring in from a community expedition's waypoint list.
They take plain data and keep no state; the expedition manager holds that.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from datetime import datetime, timezone

from voidcompass.overlays.rig_tracker import bearing_deg, surface_distance_m

LEG_KINDS = ("stop", "destination", "home", "carrier")
# A neutron chain this long, each reached in one jump, has no star to scoop.
FUEL_RUN = 4
# Gaps longer than this between jumps are breaks, not flying.
ACTIVE_GAP_S = 15 * 60
# A Fleet Carrier jump: the countdown, the jump and the cooldown.
CARRIER_JUMP_MIN = 20
CARRIER_JUMP_LY = 500.0
# Tonnes of tritium a full-range carrier jump burns, roughly (Spansh plots the exact figure).
CARRIER_TRITIUM_PER_JUMP = 133
# The Spansh plotter's links: .../plotter/results/<job>, .../exact-plotter/results/<job> and so on.
SPANSH_JOB = re.compile(r"spansh\.co\.uk/[\w-]+/results/([0-9A-Fa-f-]{8,})")


def position(value):
    """[x, y, z] as floats, or None."""
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        point = [float(value[index]) for index in range(3)]
    except (TypeError, ValueError):
        return None
    return point if all(math.isfinite(axis) for axis in point) else None


def distance(left, right):
    left, right = position(left), position(right)
    if left is None or right is None:
        return None
    return math.dist(left, right)


def path_progress(start, legs, current=None):
    """How far along the planned route you are, by straight-line distance.

    ``start`` is the starting [x, y, z]; ``legs`` the legs in order, each with
    ``coords`` and ``reached``. Returns total, done and to-go light years (None
    where a leg's place isn't known), the next leg and its index."""
    points = [position(start)] + [position(leg.get("coords")) for leg in legs or ()]
    total = 0.0
    known = points[0] is not None
    for left, right in zip(points, points[1:]):
        if left is None or right is None:
            known = False
            continue
        total += math.dist(left, right)
    upcoming = next((index for index, leg in enumerate(legs or ()) if not leg.get("reached")), None)
    if upcoming is None:
        return {"total_ly": round(total, 1) if known else None, "done_ly": round(total, 1) if known else None,
                "to_go_ly": 0.0, "next": None, "next_index": None, "share": 1.0 if legs else None}
    here = position(current) or points[upcoming]
    remaining = [here] + points[upcoming + 1:]
    to_go = 0.0
    for left, right in zip(remaining, remaining[1:]):
        if left is None or right is None:
            to_go = None
            break
        to_go += math.dist(left, right)
    if not known or to_go is None or total <= 0:
        share = sum(1 for leg in legs if leg.get("reached")) / len(legs)
        return {"total_ly": round(total, 1) if known else None, "done_ly": None, "to_go_ly": round(to_go, 1) if to_go is not None else None,
                "next": legs[upcoming], "next_index": upcoming, "share": round(share, 3)}
    done = max(0.0, total - to_go)
    return {"total_ly": round(total, 1), "done_ly": round(done, 1), "to_go_ly": round(to_go, 1),
            "next": legs[upcoming], "next_index": upcoming, "share": round(max(0.0, min(1.0, done / total)), 3)}


def fuel_runs(waypoints, run=FUEL_RUN):
    """Neutron chains with nothing to scoop: ``run`` or more neutron stops in
    a row, each reached in a single jump, so no ordinary star in between."""
    found, chain = [], []
    for row in waypoints or ():
        if row.get("neutron") and int(row.get("jumps") or 0) <= 1:
            chain.append(row)
            continue
        if len(chain) >= run:
            found.append({"from": chain[0].get("system"), "to": chain[-1].get("system"), "jumps": len(chain)})
        chain = [row] if row.get("neutron") else []
    if len(chain) >= run:
        found.append({"from": chain[0].get("system"), "to": chain[-1].get("system"), "jumps": len(chain)})
    return found


def pace(jump_times, distances=(), sessions=()):
    """Your pace from your own jumps: jumps an hour of flying, light years a
    jump and hours a session. ``jump_times`` are epoch seconds."""
    times = sorted(float(value) for value in jump_times or () if value)
    active = sum(gap for gap in (b - a for a, b in zip(times, times[1:])) if 0 < gap <= ACTIVE_GAP_S)
    jumps = len(times)
    per_hour = (jumps - 1) / (active / 3600.0) if jumps > 4 and active > 600 else None
    hops = [float(value) for value in distances or () if value]
    per_jump = sum(hops) / len(hops) if hops else None
    lengths = [float(length) for length in sessions or () if length and float(length) > 600]
    per_session = sum(lengths) / len(lengths) / 3600.0 if lengths else None
    return {"jumps_per_hour": round(per_hour, 1) if per_hour else None,
            "ly_per_jump": round(per_jump, 1) if per_jump else None,
            "hours_per_session": round(per_session, 1) if per_session else None}


def eta(to_go_ly, measured):
    """Hours of flying left at your pace, and roughly how many sessions."""
    measured = measured or {}
    if not to_go_ly or not measured.get("jumps_per_hour") or not measured.get("ly_per_jump"):
        return None
    jumps = to_go_ly / measured["ly_per_jump"]
    hours = jumps / measured["jumps_per_hour"]
    sessions = math.ceil(hours / measured["hours_per_session"]) if measured.get("hours_per_session") else None
    return {"jumps": math.ceil(jumps), "hours": round(hours, 1), "sessions": sessions}


def carrier_leg(distance_ly, tritium_aboard=None):
    """What a carrier leg asks for: jumps, tritium and time, before Spansh
    has plotted it exactly."""
    if not distance_ly:
        return None
    jumps = math.ceil(float(distance_ly) / CARRIER_JUMP_LY)
    needed = jumps * CARRIER_TRITIUM_PER_JUMP
    return {"jumps": jumps, "tritium": needed, "minutes": jumps * CARRIER_JUMP_MIN,
            "short": None if tritium_aboard is None else max(0, needed - int(tritium_aboard))}


def streak(stats, now=None):
    """Since the last death or hull scare: jumps, light years and days."""
    stats = stats or {}
    since = stats.get("last_incident")
    days = None
    if since:
        try:
            then = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
            if then.tzinfo is None:
                then = then.replace(tzinfo=timezone.utc)
            days = max(0, ((now or datetime.now(timezone.utc)) - then).days)
        except ValueError:
            days = None
    return {"jumps": int(stats.get("streak_jumps") or 0), "ly": round(float(stats.get("streak_ly") or 0), 1),
            "days": days, "since": since, "best_jumps": int(stats.get("best_streak_jumps") or 0),
            "deaths": int(stats.get("deaths") or 0), "scares": int(stats.get("scares") or 0)}


def supplies(endurance=None, limpets=None, repair_controller=None, raw_materials=None):
    """Hull, the AFMU, limpets and FSD injections: what's left, what's low,
    and what you could synthesise from the materials aboard."""
    endurance = endurance or {}
    raw = {str(key).casefold(): int((value.get("count") if isinstance(value, dict) else value) or 0)
           for key, value in (raw_materials or {}).items()}
    rows = []
    hull = endurance.get("hull_percent")
    if hull is not None:
        rows.append({"name": "Hull", "value": f"{float(hull):.0f}%", "low": float(hull) < 70, "detail": "Repair at a station"})
    if endurance.get("afmu_installed"):
        ammo = endurance.get("afmu_ammo")
        rows.append({"name": "AFMU", "value": "—" if ammo is None else f"{int(ammo)} ammo", "low": ammo is not None and int(ammo) < 200,
                     "detail": "Refills at stations"})
    if limpets is not None or repair_controller:
        can = min(raw.get("iron", 0) // 10, raw.get("nickel", 0) // 10) * 4 if raw else None
        rows.append({"name": "Limpets", "value": str(int(limpets or 0)), "low": bool(repair_controller) and int(limpets or 0) < 4,
                     "detail": f"Synthesis: {can} more from iron and nickel" if can else "Synthesis needs 10 iron, 10 nickel"})
    injections = endurance.get("injections")
    if injections:
        made = ", ".join(f"{count} {tier}" for tier, count in injections.items() if count)
        rows.append({"name": "FSD injections", "value": made or "none", "low": not any(injections.values()),
                     "detail": "From raw materials: carbon, vanadium, germanium and more"})
    fsd = endurance.get("fsd_health_percent")
    if fsd is not None:
        rows.append({"name": "FSD", "value": f"{float(fsd):.0f}%", "low": float(fsd) < 80,
                     "detail": "Neutron boosts wear it; an AFMU repairs it"})
    return {"rows": rows, "low": [row["name"] for row in rows if row["low"]]}


# The columns a community list may use, each in its several spellings.
_COLUMNS = {
    "system": {"system", "system name", "systemname", "star system", "starsystem", "galmapsearch"},
    "body": {"body", "body name", "bodyname", "planet"},
    "lat": {"lat", "latitude"},
    "lon": {"lon", "long", "longitude"},
    "kind": {"type", "kind", "category"},
    "title": {"title", "poi", "place", "poi name"},
    "note": {"notes", "note", "description", "comment", "comments", "summary"},
}


def latitude(value):
    return _angle(value, 90.0)


def longitude(value):
    return _angle(value, 180.0)


def _angle(value, limit):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return round(number, 5) if math.isfinite(number) and -limit <= number <= limit else None


def _json_rows(value):
    """Rows from a JSON list: our own fields, EDAstro's (galMapSearch,
    coordinates, summary), or a list under waypoints/systems/route."""
    if isinstance(value, dict):
        for key in ("waypoints", "systems", "route", "result", "places", "pois"):
            if isinstance(value.get(key), list):
                return _json_rows(value[key])
        return []
    rows = []
    for item in value if isinstance(value, list) else ():
        if isinstance(item, str):
            rows.append({"system": item})
            continue
        if not isinstance(item, dict):
            continue
        lowered = {str(key).casefold().replace("_", " "): field for key, field in item.items()}
        row = {}
        for name, spellings in _COLUMNS.items():
            row[name] = next((lowered[key] for key in spellings if lowered.get(key) not in (None, "")), None)
        if not row["system"]:
            row["system"] = lowered.get("name")
        elif lowered.get("name") and not row["title"]:
            row["title"] = lowered.get("name")
        coords = lowered.get("coordinates") or lowered.get("coords") or lowered.get("starpos")
        if coords is None and all(axis in lowered for axis in "xyz"):
            coords = [lowered["x"], lowered["y"], lowered["z"]]
        row["coords"] = coords
        rows.append(row)
    return rows


def parse_import(text):
    """What a community expedition publishes, as places to go: a CSV (a
    System column, and Body, Latitude, Longitude, Type, Name and Notes if it
    has them), a JSON list, a pasted list one per line, or a Spansh results
    link. A Void Compass expedition file comes back whole, as ``payload``.
    Returns {"systems": [{name, coords, body, lat, lon, kind, title, note}],
    "spansh_job", "payload"}."""
    text = str(text or "").strip().lstrip("﻿")
    job = SPANSH_JOB.search(text)
    if job and len(text.split()) <= 3:
        return {"systems": [], "spansh_job": job.group(1), "payload": None}
    systems, seen = [], set()

    def add(name, coords=None, body=None, lat=None, lon=None, kind=None, title=None, note=None):
        name = str(name or "").strip().strip('"').strip()
        body = str(body or "").strip()[:160]
        lat, lon = latitude(lat), longitude(lon)
        # The same system twice is one stop; two sites on one planet are two.
        key = (name.casefold(), body.casefold(), lat, lon)
        if not name or len(name) > 120 or key in seen:
            return
        seen.add(key)
        systems.append({"name": name, "coords": position(coords), "body": body, "lat": lat, "lon": lon,
                        "kind": str(kind or "").strip()[:40], "title": str(title or "").strip()[:200],
                        "note": str(note or "").strip()[:400]})

    if text[:1] in "[{":
        try:
            value = json.loads(text)
        except ValueError:
            value = None
        if isinstance(value, dict) and value.get("format") == "voidcompass-expedition":
            return {"systems": [], "spansh_job": None, "payload": value}
        if value is not None:
            for row in _json_rows(value):
                add(row.get("system"), row.get("coords"), row.get("body"), row.get("lat"), row.get("lon"),
                    row.get("kind"), row.get("title"), row.get("note"))
            return {"systems": systems, "spansh_job": None, "payload": None}

    lines = [line for line in text.splitlines() if line.strip()]
    if lines and ("," in lines[0] or "\t" in lines[0]):
        dialect = "excel-tab" if "\t" in lines[0] else "excel"
        rows = list(csv.reader(io.StringIO("\n".join(lines)), dialect=dialect))
        header = [cell.strip().casefold() for cell in rows[0]]
        columns = {name: next((index for index, cell in enumerate(header) if cell in spellings), None)
                   for name, spellings in _COLUMNS.items()}
        if columns["system"] is None and "name" in header:
            columns["system"] = header.index("name")
        elif columns["title"] is None and "name" in header:
            columns["title"] = header.index("name")
        axes = [next((index for index, cell in enumerate(header) if cell == axis), None) for axis in ("x", "y", "z")]
        if columns["system"] is not None:
            def cell(row, name):
                index = columns[name]
                return row[index] if index is not None and index < len(row) else None
            for row in rows[1:]:
                coords = [row[index] for index in axes] if all(index is not None and index < len(row) for index in axes) else None
                add(cell(row, "system"), coords, cell(row, "body"), cell(row, "lat"), cell(row, "lon"),
                    cell(row, "kind"), cell(row, "title"), cell(row, "note"))
            return {"systems": systems, "spansh_job": None, "payload": None}
        for row in rows:
            if row:
                add(row[0])
        return {"systems": systems, "spansh_job": None, "payload": None}
    for line in lines:
        # "1. Colonia" or "- Sagittarius A*": a numbered or bulleted list.
        add(re.sub(r"^\s*(?:\d+[.)]|[-*•])\s+", "", line))
    return {"systems": systems, "spansh_job": None, "payload": None}


def milestone_due(progress, stats):
    """Halfway, once, when the planned route passes it."""
    return "halfway" if progress and (progress.get("share") or 0) >= 0.5 and "halfway" not in (stats.get("facts") or {}).get("milestones", {}) else None


# -- places along the way (Part 5) -----------------------------------------------------------------
# Within this of a surface site, you're there.
ARRIVE_M = 1000.0
# A body's radius when nobody has said: about a mid-sized moon.
GUESS_RADIUS_M = 1_500_000.0


def surface_distance(lat1, lon1, lat2, lon2, radius_m=None):
    """Metres between two points on a body, or None if one isn't known."""
    if any(value is None for value in (lat1, lon1, lat2, lon2)):
        return None
    return surface_distance_m(float(lat1), float(lon1), float(lat2), float(lon2), float(radius_m or 0) or GUESS_RADIUS_M)


def surface_target(lat, lon, heading, target_lat, target_lon, radius_m=None):
    """The way to a surface site from where you are: its bearing and
    distance, and how far to turn from your heading (negative is left)."""
    metres = surface_distance(lat, lon, target_lat, target_lon, radius_m)
    if metres is None:
        return None
    bearing = bearing_deg(float(lat), float(lon), float(target_lat), float(target_lon))
    turn = None if heading is None else ((bearing - float(heading) + 540.0) % 360.0) - 180.0
    return {"distance_m": round(metres, 1), "bearing": round(bearing) % 360, "turn": None if turn is None else round(turn),
            "arrived": metres <= ARRIVE_M}


def near_route(points, path, max_ly, limit=60):
    """Points (each with ``coords``) within ``max_ly`` of the route's line,
    in the order you'd pass them, each with how far off the line it is
    (``off_ly``) and how far along (``along_ly``)."""
    line = [point for point in (position(row) for row in path or ()) if point is not None]
    if not line:
        return []
    segments, along = [], 0.0
    for left, right in (zip(line, line[1:]) if len(line) > 1 else [(line[0], line[0])]):
        segments.append((left, right, along))
        along += math.dist(left, right)
    out = []
    for row in points or ():
        point = position(row.get("coords"))
        if point is None:
            continue
        best = None
        for left, right, start in segments:
            span = [b - a for a, b in zip(left, right)]
            length = sum(axis * axis for axis in span)
            share = 0.0 if length <= 0 else max(0.0, min(1.0, sum((p - a) * s for p, a, s in zip(point, left, span)) / length))
            nearest = [a + s * share for a, s in zip(left, span)]
            off = math.dist(point, nearest)
            if best is None or off < best[0]:
                best = (off, start + share * math.sqrt(length))
        if best[0] <= max_ly:
            out.append({**row, "off_ly": round(best[0], 1), "along_ly": round(best[1], 1)})
    out.sort(key=lambda row: (row["along_ly"], row["off_ly"]))
    return out[:limit]


def places_csv(rows):
    """The route and the places as a CSV any spreadsheet (or this importer)
    reads: System, Body, Latitude, Longitude, Type, Name, Notes, X, Y, Z."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["System", "Body", "Latitude", "Longitude", "Type", "Name", "Notes", "X", "Y", "Z"])
    for row in rows:
        coords = position(row.get("coords"))
        writer.writerow([row.get("system") or "", row.get("body") or "",
                         "" if row.get("lat") is None else row["lat"], "" if row.get("lon") is None else row["lon"],
                         row.get("kind") or "", row.get("title") or "", row.get("note") or "",
                         *([round(axis, 5) for axis in coords] if coords else ["", "", ""])])
    return out.getvalue()
