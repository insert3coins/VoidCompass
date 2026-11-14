"""Rhino survey tools (5.7.6).

- **The survey:** mark its centre where you stand, then drive to its edge
  and mark that. Until there's an edge nothing is painted or counted: the
  drive is kept as a trail, and the edge lays the grid out and sweeps the
  trail into it, so the ground covered on the way out still counts. An edge
  pressed within a quarter of the scanner's reach of the centre is the key
  pressed twice, and is refused. Everything
  your SRV's scanner has reached (2 km round you) inside that circle counts
  as covered, kept per planet, so the coverage % survives a restart. Cells
  are 50 m or more (up to 160 across), the path between two fixes is swept
  too, and the % only reads 100 when every cell is. Sweep
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
from voidcompass.overlays.rig_planner import PLAN_SAME_M
from voidcompass.overlays.rig_tracker import local_offset, surface_distance_m

SCANNER_M = 2000.0
DEFAULT_RADIUS_M = 3000.0      # until you mark the edge
RADIUS_RANGE_M = (300.0, 20000.0)
LEGACY_GRID = 48               # surveys kept before the grid followed the radius
MAX_GRID = 160
MIN_CELL_M = 50.0
PAINT_STEP_M = 100.0
PAINT_GAP_M = 5000.0           # further than this between fixes is a jump, not a drive
MIN_EDGE_M = SCANNER_M / 4     # an edge nearer the centre than this is the key pressed twice
MAX_TRAIL = 4000
MAX_PLANS = 20
# A saved mining location: the same one again (its signal, or this close to
# its middle) is updated, not added twice.
SITE_SAME_M = 2000.0
MAX_SITES = 40
MAX_RUNS = 50
# The mining location you're working: what's within this of you. Further off
# is somewhere else on the body; drive or fly this far from a survey (or a
# planning circle) and you've moved on, so it's saved and put away.
LOCATION_REACH_M = 8000.0
# While you work a location its site is kept up to date at least this often.
SITE_KEEP_S = 120.0
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
    return local_offset(origin, point, radius_m)


def grid_for(radius_m):
    """Cells across a survey of this radius: 50 m cells, or fewer for a big one."""
    return max(1, min(MAX_GRID, int(math.ceil(2 * float(radius_m) / MIN_CELL_M))))


def bits_text(covered):
    bits = 0
    for index in covered:
        bits |= 1 << int(index)
    return format(bits, "x") if covered else ""


def bits_set(text):
    try:
        bits = int(str(text or "0"), 16)
    except ValueError:
        return set()
    out, index = set(), 0
    while bits:
        if bits & 1:
            out.add(index)
        bits >>= 1
        index += 1
    return out


def _bearing(origin, point):
    return round(math.degrees(math.atan2(point[0] - origin[0], point[1] - origin[1])) % 360.0)


@functools.lru_cache(maxsize=8)
def cells(radius_m, grid=LEGACY_GRID):
    """((index, x, y), ...) for every coverage cell inside the circle."""
    size = 2 * radius_m / grid
    out = []
    for row in range(grid):
        for column in range(grid):
            x, y = -radius_m + (column + .5) * size, -radius_m + (row + .5) * size
            if math.hypot(x, y) <= radius_m:
                out.append((row * grid + column, x, y))
    return tuple(out)


def cover(covered, radius_m, you, reach=SCANNER_M, grid=LEGACY_GRID):
    """Add the cells within ``reach`` of ``you`` to ``covered``; returns how many were new."""
    size = 2 * radius_m / grid
    x0, y0 = you
    if math.hypot(x0, y0) > radius_m + reach:
        return 0
    low = lambda value: max(0, int((value - reach + radius_m) / size))
    high = lambda value: min(grid - 1, int((value + reach + radius_m) / size))
    added = 0
    for row in range(low(y0), high(y0) + 1):
        y = -radius_m + (row + .5) * size
        for column in range(low(x0), high(x0) + 1):
            index = row * grid + column
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
def _members(radius_m, reach=SCANNER_M, grid=LEGACY_GRID):
    """For each sweep stop, the cells its scanner circle should reach."""
    return tuple(frozenset(index for index, x, y in cells(radius_m, grid) if math.hypot(x - px, y - py) <= reach)
                 for px, py in sweep_points(radius_m, reach))


def paint(covered, radius_m, points, reach=SCANNER_M, grid=LEGACY_GRID, last=None):
    """Sweep a drive (fixes in metres from the centre) into ``covered``, the
    way between two fixes as well. Returns how many cells were new."""
    added = 0
    for point in points:
        stops = [point]
        if last is not None:
            gap = math.hypot(point[0] - last[0], point[1] - last[1])
            if PAINT_STEP_M < gap <= PAINT_GAP_M:
                steps = int(gap // PAINT_STEP_M)
                stops = [(last[0] + (point[0] - last[0]) * n / (steps + 1), last[1] + (point[1] - last[1]) * n / (steps + 1))
                         for n in range(1, steps + 1)] + [point]
        added += sum(cover(covered, radius_m, stop, reach, grid) for stop in stops)
        last = point
    return added


def progress(covered, radius_m, grid=LEGACY_GRID):
    """(percent covered, [swept per sweep stop]). Never rounded up: 100 only
    when every cell is covered."""
    inside = cells(radius_m, grid)
    percent = 100.0 * len(covered) / len(inside) if inside else 0.0
    percent = 100.0 if inside and len(covered) >= len(inside) else min(99.9, math.floor(percent * 10) / 10)
    swept = [bool(members) and len(members & covered) >= SWEPT_SHARE * len(members)
             for members in _members(radius_m, SCANNER_M, grid)]
    return percent, swept


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
    """Surveys, refining pulses, rig plans and the planning circle per body:
    ``{key: {"system", "body", "centre": [lat, lon], "radius_m", "edge", "grid", "bits", "said": [...],
    "pulses": [...], "plans": [...], "circle": [lat, lon], "at"}}``."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.bodies = {}
        self._covered = {}
        self._last = {}
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
                # A planet with saved sites is kept for good; the rest go after a month.
                self.bodies = {str(key): value for key, value in bodies.items()
                               if isinstance(value, dict) and (value.get("sites") or now - float(value.get("at") or 0) < FORGET_S)}

    def _payload(self):
        with self.lock:
            for key, covered in self._covered.items():
                if key in self.bodies:
                    self.bodies[key]["bits"] = bits_text(covered)
                    self.bodies[key].pop("covered", None)
            return {"schema": 2, "bodies": json.loads(json.dumps(self.bodies))}

    def save(self, delay_s=0.5):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None, delay_s=delay_s)

    def _entry(self, system, body, create=False):
        key = _key(system, body)
        entry = self.bodies.get(key)
        if entry is None and create:
            entry = self.bodies[key] = {"system": str(system or ""), "body": str(body or "")}
        return key, entry

    def _drop_if_empty(self, key):
        entry = self.bodies.get(key) or {}
        if not any(entry.get(name) for name in ("centre", "pulses", "plans", "circle", "sites")):
            self.bodies.pop(key, None)

    def survey(self, system, body):
        """The survey on this body, or None: {centre, radius_m, edge, grid, covered (a set)}."""
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry or not entry.get("centre"):
                return None
            covered = self._covered.get(key)
            if covered is None:
                covered = bits_set(entry["bits"]) if entry.get("bits") else {int(index) for index in entry.get("covered") or ()}
                self._covered[key] = covered
            return {"centre": list(entry["centre"]), "radius_m": float(entry.get("radius_m") or DEFAULT_RADIUS_M),
                    "edge": bool(entry.get("edge")), "grid": int(entry.get("grid") or LEGACY_GRID),
                    "covered": covered, "said": list(entry.get("said") or ()), "signal": entry.get("signal"),
                    "trail": [list(point) for point in entry.get("trail") or ()]}

    def planet_radius(self, system, body):
        with self.lock:
            _key_, entry = self._entry(system, body)
            return float((entry or {}).get("planet_radius") or 0) or None

    def mark_centre(self, system, body, lat, lon, now=None, signal=None, planet_radius_m=None):
        with self.lock:
            key, entry = self._entry(system, body, create=True)
            if planet_radius_m:
                entry["planet_radius"] = round(float(planet_radius_m), 1)
            entry.update(centre=[round(float(lat), 6), round(float(lon), 6)], radius_m=DEFAULT_RADIUS_M, edge=False,
                         grid=grid_for(DEFAULT_RADIUS_M), bits="", said=[], trail=[[0, 0]], at=round(now or time.time(), 1))
            entry.pop("covered", None)
            if signal is not None:
                entry["signal"] = int(signal)
            else:
                entry.pop("signal", None)
            self._covered[key] = set()
            self._last.pop(key, None)
        self.save()

    def mark_edge(self, system, body, lat, lon, planet_radius_m, now=None):
        """The edge of the survey: its radius is how far you are from the
        centre. None without a centre; 0 when you're still by the centre (the
        key pressed twice). The grid is laid out for the radius and the trail
        driven so far is swept into it."""
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry or not entry.get("centre"):
                return None
            east, north = offset_m(entry["centre"], (lat, lon), planet_radius_m)
            if math.hypot(east, north) < MIN_EDGE_M:
                return 0
            low, high = RADIUS_RANGE_M
            radius = round(max(low, min(high, math.hypot(east, north))))
            self._trail_add(entry, (east, north))
            if radius != entry.get("radius_m") or not entry.get("edge") or not entry.get("grid"):
                grid = grid_for(radius)
                covered = set()
                paint(covered, radius, [tuple(point) for point in entry.get("trail") or ()], grid=grid)
                self._covered[key] = covered
                entry.update(said=[], grid=grid, bits=bits_text(covered))
                entry.pop("covered", None)
            entry.update(radius_m=radius, edge=True, at=round(now or time.time(), 1))
        self.save()
        return radius

    @staticmethod
    def _trail_add(entry, point):
        """The drive, kept every PAINT_STEP_M in metres from the centre."""
        trail = entry.setdefault("trail", [])
        if trail and math.hypot(point[0] - trail[-1][0], point[1] - trail[-1][1]) < PAINT_STEP_M:
            return False
        trail.append([round(point[0]), round(point[1])])
        del trail[:-MAX_TRAIL]
        return True

    def clear(self, system, body):
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry or not entry.get("centre"):
                return False
            for name in ("centre", "radius_m", "edge", "covered", "bits", "grid", "said", "signal", "trail"):
                entry.pop(name, None)
            self._covered.pop(key, None)
            self._last.pop(key, None)
            self._drop_if_empty(key)
        self.save()
        return True

    def drive(self, system, body, lat, lon, planet_radius_m, reach=SCANNER_M, now=None):
        """You're here in the SRV: cover what the scanner reaches, and along
        the way from your last fix. Returns (new cells, percent) or None
        without a survey."""
        survey = self.survey(system, body)
        if survey is None:
            return None
        key = _key(system, body)
        you = offset_m(survey["centre"], (lat, lon), planet_radius_m)
        radius, grid = survey["radius_m"], survey["grid"]
        with self.lock:
            last = self._last.get(key)
            self._last[key] = you
            if planet_radius_m:
                self.bodies[key]["planet_radius"] = round(float(planet_radius_m), 1)
            kept = self._trail_add(self.bodies[key], you)
            # Nothing is painted until the edge is marked: the trail keeps the drive for then.
            added = paint(survey["covered"], radius, [you], reach, grid, last) if survey["edge"] else 0
            if added or kept:
                self.bodies[key]["at"] = round(now or time.time(), 1)
        if added or kept:
            self.save(delay_s=5.0)
        return added, progress(survey["covered"], radius, grid)[0] if survey["edge"] else 0.0

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

    # -- rig plans from a traced edge -------------------------------------------------
    def plans(self, system, body):
        with self.lock:
            _key_, entry = self._entry(system, body)
            return [dict(row) for row in (entry or {}).get("plans") or () if isinstance(row, dict)]

    def add_plan(self, system, body, record, planet_radius_m, now=None):
        """Keep a plan; one traced within PLAN_SAME_M of a kept one replaces it."""
        middle = record.get("middle") or (0.0, 0.0)
        with self.lock:
            _key_, entry = self._entry(system, body, create=True)
            kept = [row for row in entry.get("plans") or () if isinstance(row, dict) and len(row.get("middle") or ()) == 2
                    and surface_distance_m(middle[0], middle[1], row["middle"][0], row["middle"][1], planet_radius_m) > PLAN_SAME_M]
            entry["plans"] = (kept + [dict(record)])[-MAX_PLANS:]
            entry["at"] = round(now or time.time(), 1)
        self.save()

    def forget_plan(self, system, body, middle):
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry:
                return False
            before = len(entry.get("plans") or ())
            entry["plans"] = [row for row in entry.get("plans") or () if list(row.get("middle") or ()) != list(middle)]
            removed = len(entry["plans"]) < before
            self._drop_if_empty(key)
        if removed:
            self.save()
        return removed

    # -- saved mining locations ----------------------------------------------------------
    def sites(self, system, body):
        with self.lock:
            _key_, entry = self._entry(system, body)
            return [dict(row) for row in (entry or {}).get("sites") or () if isinstance(row, dict)]

    def all_sites(self):
        """Every saved site, on every planet: [{..., "system", "body"}], newest first."""
        with self.lock:
            out = [{**row, "system": entry.get("system", ""), "body": entry.get("body", "")}
                   for entry in self.bodies.values() for row in entry.get("sites") or () if isinstance(row, dict)]
        return sorted(out, key=lambda row: -float(row.get("updated") or 0))

    def save_site(self, system, body, record, planet_radius_m, now=None):
        """Keep a mining location, or bring the one it matches up to date (its
        name and notes stay yours). Returns the site kept."""
        now = now or time.time()
        with self.lock:
            _key_, entry = self._entry(system, body, create=True)
            sites = [row for row in entry.get("sites") or () if isinstance(row, dict)]
            centre = record.get("centre") or (0.0, 0.0)

            def same(row):
                # The same signal number at the same location: a number alone
                # isn't enough, as the game can still have the last one targeted.
                middle = row.get("centre") or ()
                apart = surface_distance_m(centre[0], centre[1], middle[0], middle[1], planet_radius_m) \
                    if len(middle) == 2 and planet_radius_m else None
                if record.get("signal") is not None and row.get("signal") is not None:
                    return int(row["signal"]) == int(record["signal"]) and (apart is None or apart <= LOCATION_REACH_M)
                return apart is not None and apart <= SITE_SAME_M

            match = next((row for row in sites if same(row)), None)
            if match is None:
                match = {"id": f"{int(now * 1000):x}", "saved": round(now, 1), "name": record.get("name") or "", "note": ""}
                sites.append(match)
            keep = {key: match.get(key) for key in ("id", "saved", "name", "note", "runs") if match.get(key) is not None}
            match.clear()
            match.update({**record, **keep, "updated": round(now, 1)})
            if not match.get("name"):
                match["name"] = record.get("name") or "Mining location"
            entry["sites"] = sites[-MAX_SITES:]
            entry["at"] = round(now, 1)
            saved = dict(match)
        self.save()
        return saved

    def add_run(self, system, body, site_id, run):
        """A Rhino run worked at a saved site: {"launched", "docked", "minutes",
        "refined_t", "taken": {commodity: t}}. The same run again (its launch)
        replaces itself."""
        with self.lock:
            _key_, entry = self._entry(system, body)
            row = next((row for row in (entry or {}).get("sites") or () if row.get("id") == site_id), None)
            if row is None:
                return False
            runs = [kept for kept in row.get("runs") or () if kept.get("launched") != run.get("launched")]
            row["runs"] = sorted(runs + [dict(run)], key=lambda kept: float(kept.get("docked") or 0))[-MAX_RUNS:]
        self.save()
        return True

    def change_site(self, system, body, site_id, name=None, note=None):
        with self.lock:
            _key_, entry = self._entry(system, body)
            row = next((row for row in (entry or {}).get("sites") or () if row.get("id") == site_id), None)
            if row is None:
                return False
            if name is not None:
                row["name"] = str(name).strip()[:80] or row.get("name")
            if note is not None:
                row["note"] = str(note).strip()[:400]
        self.save()
        return True

    def forget_site(self, system, body, site_id):
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry:
                return False
            before = len(entry.get("sites") or ())
            entry["sites"] = [row for row in entry.get("sites") or () if row.get("id") != site_id]
            removed = len(entry["sites"]) < before
            self._drop_if_empty(key)
        if removed:
            self.save()
        return removed

    def resume_site(self, system, body, site_id):
        """Carry a saved site's survey on: its centre, edge and what was swept."""
        with self.lock:
            key, entry = self._entry(system, body)
            row = next((row for row in (entry or {}).get("sites") or () if row.get("id") == site_id), None)
            survey = (row or {}).get("survey") or {}
            if not survey.get("centre"):
                return False
            entry.update(centre=list(survey["centre"]), radius_m=float(survey.get("radius_m") or DEFAULT_RADIUS_M),
                         edge=bool(survey.get("edge")), grid=int(survey.get("grid") or LEGACY_GRID),
                         bits=str(survey.get("bits") or ""), said=[], trail=list(survey.get("trail") or ()),
                         at=round(time.time(), 1))
            entry.pop("covered", None)
            if row.get("signal") is not None:
                entry["signal"] = int(row["signal"])
            self._covered[key] = bits_set(entry["bits"])
            self._last.pop(key, None)
        self.save()
        return True

    # -- the planning circle ------------------------------------------------------------
    def circle(self, system, body):
        with self.lock:
            _key_, entry = self._entry(system, body)
            centre = (entry or {}).get("circle")
            return list(centre) if centre and len(centre) == 2 else None

    def set_circle(self, system, body, lat, lon, now=None):
        with self.lock:
            _key_, entry = self._entry(system, body, create=True)
            entry["circle"] = [round(float(lat), 6), round(float(lon), 6)]
            entry["at"] = round(now or time.time(), 1)
        self.save()

    def clear_circle(self, system, body):
        with self.lock:
            key, entry = self._entry(system, body)
            if not entry or not entry.get("circle"):
                return False
            entry.pop("circle", None)
            self._drop_if_empty(key)
        self.save()
        return True


def survey_model(survey, plane, you=None):
    """The map's view of a survey, in the map's frame (``plane`` turns lat/lon
    into its metres): the circle, the covered cells, the sweep stops and the
    next one to drive to."""
    if not survey:
        return None
    origin = plane(tuple(survey["centre"]))
    radius = survey["radius_m"]
    grid = int(survey.get("grid") or LEGACY_GRID)
    away = round(math.hypot(you[0] - origin[0], you[1] - origin[1])) if you else None
    if not survey["edge"]:
        # Only the centre until the edge is marked: no plate of a guessed
        # area over the map, nothing swept, no stops.
        return {"at": origin, "radius_m": radius, "edge": False, "percent": 0.0, "grid": grid, "covered": "",
                "stops": [], "swept": 0, "next": None, "scanner_m": SCANNER_M, "signal": survey.get("signal"),
                "inside": False, "centre_m": away, "centre_bearing": _bearing(you, origin) if you and away else None,
                "edge_ok": bool(away is not None and away >= MIN_EDGE_M)}
    percent, swept = progress(survey["covered"], radius, grid)
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
    width = (grid * grid + 3) // 4
    return {"at": origin, "radius_m": radius, "edge": survey["edge"], "percent": percent, "grid": grid,
            "covered": format(bits, f"0{width}x")[::-1] if survey["covered"] else "", "stops": stops,
            "swept": sum(swept), "next": following, "scanner_m": SCANNER_M, "signal": survey.get("signal"),
            "inside": bool(you) and math.hypot(you[0] - origin[0], you[1] - origin[1]) <= radius,
            "centre_m": away, "centre_bearing": _bearing(you, origin) if you and away else None, "edge_ok": True}
