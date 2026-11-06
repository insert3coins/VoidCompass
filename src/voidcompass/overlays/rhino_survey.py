"""Rhino survey tools (5.7.6), after EDSMT.

- **The survey:** mark its centre where you stand, then its edge. Everything
  your SRV's scanner has reached (2 km round you) inside that circle counts
  as covered, kept per planet, so the coverage % survives a restart. Sweep
  stops are laid out so their scanner circles cover the area between them
  (centres a little under √3 × 2 km apart); one is swept once nine tenths of what it should
  reach is covered, and the nearest unswept one is where to drive next.
- **The best patch:** where refining pulses gathered thickest. Elite gives no
  deposit positions, so these are only the places you stood for each pulse,
  grouped within 150 m. Never anything invented.
- **The rig planner:** a hex pattern at the rig spacing (78 m) round your
  first rig, or round the best patch before any rig is down: the free spots
  nearest that anchor, one for each rig still to place.

Survey work is in metres east and north of the survey's centre.
"""
from __future__ import annotations

import functools
import json
import math
import os
import threading
import time

from voidcompass.core.persistence_queue import persistence_queue

SCANNER_M = 2000.0
DEFAULT_RADIUS_M = 3000.0      # until you mark the edge
RADIUS_RANGE_M = (300.0, 20000.0)
GRID = 48                      # coverage cells across the survey
SWEPT_SHARE = .9
HALF_PERCENT, DONE_PERCENT = 50, 95
PATCH_M = 150.0
MIN_PATCH_PULSES = 3
MAX_PULSES = 2000
FORGET_S = 30 * 86400
SLOTS = 6


def _key(system, body):
    return f"{str(system or '').strip()}|{str(body or '').strip()}".casefold()


def offset_m(origin, point, radius_m):
    """(east, north) metres of ``point`` from ``origin`` (both lat/lon)."""
    lat0, lon0 = origin
    lat, lon = point
    dlon = (float(lon) - float(lon0) + 540.0) % 360.0 - 180.0
    return (math.radians(dlon) * radius_m * math.cos(math.radians(float(lat0))),
            math.radians(float(lat) - float(lat0)) * radius_m)


def _bearing(origin, point):
    return round(math.degrees(math.atan2(point[0] - origin[0], point[1] - origin[1])) % 360.0)


@functools.lru_cache(maxsize=8)
def cells(radius_m):
    """((index, x, y), ...) for every coverage cell inside the circle."""
    size = 2 * radius_m / GRID
    out = []
    for row in range(GRID):
        for column in range(GRID):
            x, y = -radius_m + (column + .5) * size, -radius_m + (row + .5) * size
            if math.hypot(x, y) <= radius_m:
                out.append((row * GRID + column, x, y))
    return tuple(out)


def cover(covered, radius_m, you, reach=SCANNER_M):
    """Add the cells within ``reach`` of ``you`` to ``covered``; returns how many were new."""
    size = 2 * radius_m / GRID
    x0, y0 = you
    if math.hypot(x0, y0) > radius_m + reach:
        return 0
    low = lambda value: max(0, int((value - reach + radius_m) / size))
    high = lambda value: min(GRID - 1, int((value + reach + radius_m) / size))
    added = 0
    for row in range(low(y0), high(y0) + 1):
        y = -radius_m + (row + .5) * size
        for column in range(low(x0), high(x0) + 1):
            index = row * GRID + column
            if index in covered:
                continue
            x = -radius_m + (column + .5) * size
            if math.hypot(x, y) <= radius_m and math.hypot(x - x0, y - y0) <= reach:
                covered.add(index)
                added += 1
    return added


@functools.lru_cache(maxsize=8)
def sweep_points(radius_m, reach=SCANNER_M):
    """Where to stop so the scanner circles cover the whole area: a hex
    lattice √3 × reach apart; stops outside the edge are pulled in onto it."""
    if radius_m <= reach * .8:
        return ((0.0, 0.0),)
    spacing = reach * math.sqrt(3) * .98  # a little overlap, so rounding leaves no gaps
    rows = int((radius_m + reach) / (spacing * math.sqrt(3) / 2)) + 1
    points = []
    for row in range(-rows, rows + 1):
        y = row * spacing * math.sqrt(3) / 2
        shift = spacing / 2 if row % 2 else 0.0
        columns = int((radius_m + reach) / spacing) + 1
        for column in range(-columns, columns + 1):
            x = column * spacing + shift
            distance = math.hypot(x, y)
            if distance >= radius_m + reach:
                continue
            pull = radius_m / distance if distance > radius_m else 1.0
            points.append((round(x * pull, 1), round(y * pull, 1)))
    points.sort(key=lambda point: (math.hypot(*point), math.atan2(point[1], point[0])))
    return tuple(points)


@functools.lru_cache(maxsize=8)
def _members(radius_m, reach=SCANNER_M):
    """For each sweep stop, the cells its scanner circle should reach."""
    return tuple(frozenset(index for index, x, y in cells(radius_m) if math.hypot(x - px, y - py) <= reach)
                 for px, py in sweep_points(radius_m, reach))


def progress(covered, radius_m):
    """(percent covered, [swept per sweep stop])."""
    inside = cells(radius_m)
    percent = 100.0 * len(covered) / len(inside) if inside else 0.0
    swept = [bool(members) and len(members & covered) >= SWEPT_SHARE * len(members) for members in _members(radius_m)]
    return round(percent, 1), swept


def best_patch(deposits, you=None):
    """The richest patch from the map's deposits ({"at", "pulses", "materials"}),
    or None before there are MIN_PATCH_PULSES pulses together."""
    patches = []
    for deposit in sorted(deposits or (), key=lambda item: -int(item.get("pulses") or 0)):
        at = deposit.get("at")
        if not at:
            continue
        home = next((patch for patch in patches if math.hypot(patch["seed"][0] - at[0], patch["seed"][1] - at[1]) <= PATCH_M), None)
        if home is None:
            patches.append({"seed": list(at), "parts": [deposit]})
        else:
            home["parts"].append(deposit)
    best = None
    for patch in patches:
        pulses = sum(int(part.get("pulses") or 0) for part in patch["parts"])
        if pulses >= MIN_PATCH_PULSES and (best is None or pulses > best["pulses"]):
            x = sum(part["at"][0] * int(part.get("pulses") or 0) for part in patch["parts"]) / pulses
            y = sum(part["at"][1] * int(part.get("pulses") or 0) for part in patch["parts"]) / pulses
            materials = []
            for part in patch["parts"]:
                materials += [name for name in part.get("materials") or () if name not in materials]
            best = {"at": [round(x, 1), round(y, 1)], "pulses": pulses, "deposits": len(patch["parts"]), "materials": materials[:4]}
    if best and you:
        best["distance"] = round(math.hypot(best["at"][0] - you[0], best["at"][1] - you[1]))
        best["bearing"] = _bearing(you, best["at"])
    return best


def rig_plan(anchor, rigs, spacing, you=None, slots=SLOTS, warn_m=0.0):
    """Spots for the rigs still to place: hex points ``spacing`` apart round
    ``anchor``, nearest it first, skipping any a rig already fills (within half
    the spacing) or is too close to. [{"at", "distance", "bearing", "next"}]."""
    if not anchor or len(rigs) >= slots or spacing <= 0:
        return []
    candidates = []
    for ring in range(3):
        if ring == 0:
            candidates.append((0.0, 0.0))
            continue
        for side in range(6):
            corner = math.radians(60 * side)
            following = math.radians(60 * (side + 1))
            for step in range(ring):
                share = step / ring
                x = ring * ((1 - share) * math.cos(corner) + share * math.cos(following))
                y = ring * ((1 - share) * math.sin(corner) + share * math.sin(following))
                candidates.append((x * spacing, y * spacing))
    plan = []
    for dx, dy in candidates:
        point = (anchor[0] + dx, anchor[1] + dy)
        near = [math.hypot(point[0] - rig[0], point[1] - rig[1]) for rig in rigs]
        if any(distance < spacing - .5 for distance in near):
            continue
        plan.append(point)
        if len(plan) >= slots - len(rigs):
            break
    out = [{"at": [round(x, 1), round(y, 1)]} for x, y in plan]
    if you:
        for spot in out:
            spot["distance"] = round(math.hypot(spot["at"][0] - you[0], spot["at"][1] - you[1]))
            spot["bearing"] = _bearing(you, spot["at"])
        if out:
            min(out, key=lambda spot: spot["distance"])["next"] = True
    if warn_m and rigs:
        for spot in out:
            spot["far"] = any(math.hypot(spot["at"][0] - rig[0], spot["at"][1] - rig[1]) > warn_m for rig in rigs)
    return out


class SurveyStore:
    """Surveys and refining pulses per body:
    ``{key: {"system", "body", "centre": [lat, lon], "radius_m", "edge", "covered": [...], "said": [...], "pulses": [...], "at"}}``."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.bodies = {}
        self._covered = {}
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        bodies = data.get("bodies") if isinstance(data, dict) else None
        if isinstance(bodies, dict):
            now = time.time()
            with self.lock:
                self.bodies = {str(key): value for key, value in bodies.items()
                               if isinstance(value, dict) and now - float(value.get("at") or 0) < FORGET_S}

    def _payload(self):
        with self.lock:
            for key, covered in self._covered.items():
                if key in self.bodies:
                    self.bodies[key]["covered"] = sorted(covered)
            return {"schema": 1, "bodies": json.loads(json.dumps(self.bodies))}

    def save(self, delay_s=0.5):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None, delay_s=delay_s)

    def _entry(self, system, body, create=False):
        key = _key(system, body)
        entry = self.bodies.get(key)
        if entry is None and create:
            entry = self.bodies[key] = {"system": str(system or ""), "body": str(body or "")}
        return key, entry

    def survey(self, system, body):
        """The survey on this body, or None: {centre, radius_m, edge, covered (a set)}."""
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry or not entry.get("centre"):
                return None
            covered = self._covered.get(key)
            if covered is None:
                covered = self._covered[key] = {int(index) for index in entry.get("covered") or ()}
            return {"centre": list(entry["centre"]), "radius_m": float(entry.get("radius_m") or DEFAULT_RADIUS_M),
                    "edge": bool(entry.get("edge")), "covered": covered, "said": list(entry.get("said") or ())}

    def mark_centre(self, system, body, lat, lon, now=None):
        with self.lock:
            key, entry = self._entry(system, body, create=True)
            entry.update(centre=[round(float(lat), 6), round(float(lon), 6)], radius_m=DEFAULT_RADIUS_M, edge=False,
                         covered=[], said=[], at=round(now or time.time(), 1))
            self._covered[key] = set()
        self.save()

    def mark_edge(self, system, body, lat, lon, planet_radius_m, now=None):
        """The edge of the survey: its radius is how far you are from the
        centre. None without a centre."""
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry or not entry.get("centre"):
                return None
            east, north = offset_m(entry["centre"], (lat, lon), planet_radius_m)
            low, high = RADIUS_RANGE_M
            radius = round(max(low, min(high, math.hypot(east, north))))
            if radius != entry.get("radius_m"):
                # The grid is laid out for the radius: coverage starts again.
                self._covered[key] = set()
                entry.update(covered=[], said=[])
            entry.update(radius_m=radius, edge=True, at=round(now or time.time(), 1))
        self.save()
        return radius

    def clear(self, system, body):
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry or not entry.get("centre"):
                return False
            for name in ("centre", "radius_m", "edge", "covered", "said"):
                entry.pop(name, None)
            self._covered.pop(key, None)
            if not entry.get("pulses"):
                self.bodies.pop(key, None)
        self.save()
        return True

    def drive(self, system, body, lat, lon, planet_radius_m, reach=SCANNER_M, now=None):
        """You're here in the SRV: cover what the scanner reaches. Returns
        (new cells, percent) or None without a survey."""
        survey = self.survey(system, body)
        if survey is None:
            return None
        you = offset_m(survey["centre"], (lat, lon), planet_radius_m)
        with self.lock:
            added = cover(survey["covered"], survey["radius_m"], you, reach)
            if added:
                self.bodies[_key(system, body)]["at"] = round(now or time.time(), 1)
        if added:
            self.save(delay_s=5.0)
        return added, progress(survey["covered"], survey["radius_m"])[0]

    def said(self, system, body, milestone):
        """True the first time a coverage milestone is passed (for the companion)."""
        with self.lock:
            _key_, entry = self._entry(system, body)
            if not entry or milestone in (entry.get("said") or ()):
                return False
            entry.setdefault("said", []).append(milestone)
        self.save()
        return True

    def note_pulse(self, system, body, lat, lon, material="", now=None):
        with self.lock:
            _key_, entry = self._entry(system, body, create=True)
            pulses = entry.setdefault("pulses", [])
            pulses.append([round(float(lat), 6), round(float(lon), 6), str(material or "")[:40]])
            del pulses[:-MAX_PULSES]
            entry["at"] = round(now or time.time(), 1)
        self.save(delay_s=2.0)

    def pulses(self, system, body):
        with self.lock:
            _key_, entry = self._entry(system, body)
            return [tuple(row) for row in (entry or {}).get("pulses") or () if isinstance(row, list) and len(row) >= 2]


def survey_model(survey, plane, you=None):
    """The map's view of a survey, in the map's frame (``plane`` turns lat/lon
    into its metres): the circle, the covered cells, the sweep stops and the
    next one to drive to."""
    if not survey:
        return None
    origin = plane(tuple(survey["centre"]))
    radius = survey["radius_m"]
    percent, swept = progress(survey["covered"], radius)
    stops = [{"at": [round(origin[0] + x, 1), round(origin[1] + y, 1)], "swept": done}
             for (x, y), done in zip(sweep_points(radius), swept)]
    following = None
    if you:
        waiting = [stop for stop in stops if not stop["swept"]]
        if waiting:
            stop = min(waiting, key=lambda item: math.hypot(item["at"][0] - you[0], item["at"][1] - you[1]))
            following = {"at": stop["at"], "distance": round(math.hypot(stop["at"][0] - you[0], stop["at"][1] - you[1])),
                         "bearing": _bearing(you, stop["at"])}
    # Covered cells as a hex string of bits (cell index order), for the map to shade.
    bits = 0
    for index in survey["covered"]:
        bits |= 1 << index
    width = GRID * GRID // 4
    return {"at": origin, "radius_m": radius, "edge": survey["edge"], "percent": percent, "grid": GRID,
            "covered": format(bits, f"0{width}x")[::-1] if survey["covered"] else "", "stops": stops,
            "swept": sum(swept), "next": following, "scanner_m": SCANNER_M,
            "inside": bool(you) and math.hypot(you[0] - origin[0], you[1] - origin[1]) <= radius}
