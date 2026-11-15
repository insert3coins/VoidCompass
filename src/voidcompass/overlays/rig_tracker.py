"""Rig Tracker (5.5.10): the mining rigs you've set down on a planet, after
SrvSurvey's rig tracker for Rhino mining.

The game writes nothing to the journal when a rig is deployed or collected,
so you tell Void Compass with a hotkey: rig 1's key as you deploy rig 1 marks
it where you stand (Status.json's latitude and longitude); the same key again
as you collect it stops tracking it. The overlay shows a dial for each rig,
pointing the way it lies from where you're facing, with how far it is, how
long it has been down, which one is nearest, and the order to collect them
in. (The hold is the Cargo overlay's.)

Rigs are kept per planet for each commander, so they outlast a restart and
are there again when you come back to that body. The overlay is up as soon
as you're out in the Rhino, before any rig is down.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time

from voidcompass.core.persistence_queue import persistence_queue
from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer

SLOTS = 6
# Closer than this, you're at the rig (Studio can change it, 10 to 200 m).
HERE_M = 40.0
HERE_RANGE_M = (10, 200)
# Rigs want room between them (78 m, the community's working figure); the
# game destroys a rig left 5 km behind, so warn well before; and a rig
# that's worked its time (learnt from your own rigs) is worth collecting.
SPACING_M = 78.0
SPACING_RANGE_M = (20, 300)
WARN_M = 3500.0
WARN_RANGE_M = (0, 4900)
LOST_M = 5000.0
LAST_WARNING_M = 4800.0
# How long a rig takes isn't published and the journal doesn't say; it's
# learnt from your own: from a rig's key down to the first tonne refined round
# it (you only start collecting once it's ready), by the density of the
# deposit it was on. The lower quartile, so a rig left a while doesn't stretch
# it. Key down to key up is no measure: a rig often stays down all run.
MIN_TIMED = 2
TIMED_RANGE_S = (30, 1800)
MAX_TIMINGS = 60
# Rigs left untouched this long are forgotten.
FORGET_S = 7 * 86400
# The rig lands behind the Rhino's cockpit, which is where Status.json puts you.
DROP_M = 7.0
DROP_RANGE_M = (0, 20)
# Refined tonnes land round the rig that threw them up, not on it.
BOOK_WITHIN_M = 250.0
# What collected rigs gave: kept to put a value on deposits. No figure until
# a few rigs have been worked; one rig is an anecdote.
MAX_YIELDS = 60
MIN_YIELDS = 3


def rig_here_m(config):
    """How close counts as HERE, from the commander's Studio setting."""
    low, high = HERE_RANGE_M
    try:
        value = float((config or {}).get("rig_tracker_here_m", HERE_M))
    except (TypeError, ValueError):
        value = HERE_M
    return int(round(max(low, min(high, value))))


def _key(system, body):
    return f"{str(system or '').strip()}|{str(body or '').strip()}".casefold()


def surface_distance_m(lat1, lon1, lat2, lon2, radius_m):
    """Great-circle distance between two points on a body of ``radius_m``."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1, lon1, lat2, lon2):
    """The initial bearing from one point to another, 0-360 (0 is north)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.cos(p2) * math.sin(dl)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def local_offset(origin, point, radius_m):
    """(east, north) metres of ``point`` from ``origin`` (both lat/lon), measured
    as the great-circle range along its bearing. A flat lat/lon grid stretches
    east-west away from the anchor's latitude, badly near a pole."""
    lat0, lon0 = float(origin[0]), float(origin[1])
    lat, lon = float(point[0]), float(point[1])
    metres = surface_distance_m(lat0, lon0, lat, lon, radius_m)
    if metres <= 0:
        return 0.0, 0.0
    theta = math.radians(bearing_deg(lat0, lon0, lat, lon))
    return metres * math.sin(theta), metres * math.cos(theta)


def destination(lat, lon, bearing, metres, radius_m):
    """The point ``metres`` along ``bearing`` from (lat, lon)."""
    if not radius_m or not metres:
        return float(lat), float(lon)
    p1, l1 = math.radians(float(lat)), math.radians(float(lon))
    th, d = math.radians(float(bearing)), float(metres) / float(radius_m)
    p2 = math.asin(max(-1.0, min(1.0, math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(th))))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540.0) % 360.0 - 180.0


class RigStore:
    """Rigs per body: ``{key: {"system", "body", "rigs": {slot: {"lat", "lon", "at"}}}}``."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.bodies = {}
        self.yields = []
        self.timings = []
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
            with self.lock:
                self.bodies = {str(key): value for key, value in bodies.items() if isinstance(value, dict)}
        yields = data.get("yields") if isinstance(data, dict) else None
        if isinstance(yields, list):
            with self.lock:
                self.yields = [row for row in yields if isinstance(row, dict)][-MAX_YIELDS:]
        timings = data.get("timings") if isinstance(data, dict) else None
        if isinstance(timings, list):
            with self.lock:
                self.timings = [row for row in timings if isinstance(row, dict)][-MAX_TIMINGS:]

    def _payload(self):
        with self.lock:
            return {"schema": 1, "bodies": json.loads(json.dumps(self.bodies)), "yields": list(self.yields),
                    "timings": list(self.timings)}

    def save(self):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None, delay_s=0.5)

    def rigs(self, system, body, now=None):
        """The rigs on a body, by slot (forgetting old ones)."""
        now = now if now is not None else time.time()
        with self.lock:
            entry = self.bodies.get(_key(system, body)) or {}
            rigs = {int(slot): dict(rig) for slot, rig in (entry.get("rigs") or {}).items()
                    if isinstance(rig, dict) and now - float(rig.get("at") or 0) < FORGET_S}
        return rigs

    def mark(self, slot, system, body, lat, lon, now=None, commodity="", density=""):
        """The rig hotkey: "placed" (now tracked here) or "collected" (no longer)."""
        slot = int(slot)
        if not 1 <= slot <= SLOTS:
            raise ValueError(slot)
        now = now if now is not None else time.time()
        key = _key(system, body)
        with self.lock:
            entry = self.bodies.setdefault(key, {"system": str(system or ""), "body": str(body or ""), "rigs": {}})
            rigs = entry.setdefault("rigs", {})
            if str(slot) in rigs:
                collected = rigs.pop(str(slot))
                tonnes = sum(int(value or 0) for value in (collected.get("tonnes") or {}).values())
                if tonnes > 0:
                    # What a worked rig gave, for the value of the deposits still to work.
                    self.yields = (self.yields + [{"t": tonnes, "commodity": rig_commodity(collected),
                                                   "at": round(now, 1), "body": key,
                                                   "down_s": round(now - float(collected.get("at") or now)),
                                                   "density": str(collected.get("density") or "")}])[-MAX_YIELDS:]
                outcome = "collected"
            else:
                # One rig per number: a rig of that number elsewhere was left behind.
                for other_key, other in self.bodies.items():
                    if other_key != key:
                        (other.get("rigs") or {}).pop(str(slot), None)
                rigs[str(slot)] = {"lat": round(float(lat), 6), "lon": round(float(lon), 6), "at": round(now, 1)}
                if commodity:
                    rigs[str(slot)]["commodity"] = str(commodity)[:40]
                if density:
                    rigs[str(slot)]["density"] = str(density)[:20]
                outcome = "placed"
            self.bodies = {name: value for name, value in self.bodies.items() if value.get("rigs")}
        self.save()
        return outcome

    def book(self, system, body, slot, commodity, now=None):
        """A refined tonne the rig threw up."""
        name = str(commodity or "").strip()[:40]
        if not name:
            return False
        with self.lock:
            rig = ((self.bodies.get(_key(system, body)) or {}).get("rigs") or {}).get(str(int(slot)))
            if not isinstance(rig, dict):
                return False
            tonnes = rig.setdefault("tonnes", {})
            first = not any(int(value or 0) for value in tonnes.values())
            tonnes[name] = int(tonnes.get(name) or 0) + 1
            if first and rig.get("at") is not None:
                # Its first tonne: collecting started, so it was ready by now.
                now = time.time() if now is None else now
                rig["ready_at"] = round(now, 1)
                self.timings = (self.timings + [{"s": round(now - float(rig["at"])), "density": str(rig.get("density") or ""),
                                                 "at": round(now, 1)}])[-MAX_TIMINGS:]
        self.save()
        return True

    def ready_s(self, density=""):
        """How long your rigs take to be ready, in seconds, learnt from the ones
        you've collected: on deposits of this density once there are a few,
        else on any; None before there are MIN_TIMED."""
        low, high = TIMED_RANGE_S
        with self.lock:
            timed = [(int(row["s"]), str(row.get("density") or "")) for row in self.timings
                     if row.get("s") is not None and low <= int(row["s"]) <= high]
        same = sorted(seconds for seconds, kind in timed if density and kind.casefold() == str(density).casefold())
        values = same if len(same) >= MIN_TIMED else sorted(seconds for seconds, _kind in timed)
        if len(values) < MIN_TIMED:
            return None
        return int(round(values[len(values) // 4] / 5.0) * 5)

    def tonnes_per_rig(self, minimum=MIN_YIELDS):
        """(median tonnes a worked rig gave, rigs measured), or (None, n) before ``minimum``."""
        with self.lock:
            values = sorted(int(row.get("t") or 0) for row in self.yields[-30:] if int(row.get("t") or 0) > 0)
        if len(values) < minimum:
            return None, len(values)
        middle = len(values) // 2
        median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
        return float(median), len(values)

    def tonnes_on(self, system, body, since=None):
        """{commodity: tonnes} your rigs have given on this body: the ones
        collected, and what the ones still down have refined so far; with
        ``since``, only from then (one Rhino run)."""
        key = _key(system, body)
        out = {}
        since = None if since is None else float(since) - 1.0  # times are kept to a tenth of a second
        with self.lock:
            for row in self.yields:
                if row.get("body") == key and row.get("commodity") and (since is None or float(row.get("at") or 0) >= since):
                    out[row["commodity"]] = out.get(row["commodity"], 0) + int(row.get("t") or 0)
            for rig in ((self.bodies.get(key) or {}).get("rigs") or {}).values():
                if since is not None and float(rig.get("at") or 0) < since:
                    continue
                for name, tonnes in (rig.get("tonnes") or {}).items():
                    out[name] = out.get(name, 0) + int(tonnes or 0)
        return out

    def everywhere(self, now=None):
        """Every planet with rigs on it: [{system, body, rigs}]."""
        now = now if now is not None else time.time()
        with self.lock:
            entries = [(entry.get("system") or "", entry.get("body") or "") for entry in self.bodies.values()]
        out = []
        for system, body in entries:
            rigs = self.rigs(system, body, now)
            if rigs:
                out.append({"system": system, "body": body, "rigs": rigs})
        return out

    def forget(self, system, body, slot):
        """A rig the game has destroyed (left 5 km behind)."""
        with self.lock:
            entry = self.bodies.get(_key(system, body)) or {}
            gone = (entry.get("rigs") or {}).pop(str(int(slot)), None)
            self.bodies = {name: value for name, value in self.bodies.items() if value.get("rigs")}
        if gone:
            self.save()
        return bool(gone)

    def clear(self, system, body):
        with self.lock:
            removed = self.bodies.pop(_key(system, body), None)
        self.save()
        return bool(removed and removed.get("rigs"))


def collect_order(here, rigs, radius_m):
    """Nearest first, then nearest to that one: the order to collect them."""
    order, at, left = [], here, dict(rigs)
    while left:
        slot = min(left, key=lambda key: surface_distance_m(at[0], at[1], left[key]["lat"], left[key]["lon"], radius_m))
        order.append(slot)
        at = (left[slot]["lat"], left[slot]["lon"])
        del left[slot]
    return order


def _setting(config, key, default, low, high):
    try:
        value = float((config or {}).get(key, default))
    except (TypeError, ValueError):
        value = default
    return int(round(max(low, min(high, value))))


def rig_spacing_m(config):
    return _setting(config, "rig_tracker_spacing_m", SPACING_M, *SPACING_RANGE_M)


def rig_warn_m(config):
    """How far a rig may be before the warning (0: never warn)."""
    return _setting(config, "rig_tracker_warn_m", WARN_M, *WARN_RANGE_M)


def rig_drop_m(config):
    """How far behind you a rig lands (0: under you)."""
    return _setting(config, "rig_tracker_drop_m", DROP_M, *DROP_RANGE_M)


def drop_point(lat, lon, heading, radius_m, metres):
    """Where a rig lands: ``metres`` behind you when your heading is known."""
    if heading is None or not metres:
        return float(lat), float(lon)
    return destination(lat, lon, (float(heading) + 180.0) % 360.0, metres, radius_m)


def rig_commodity(rig):
    """What a rig is working: the deposit it was dropped on, else what it has
    refined most of (by-products come out in smaller numbers)."""
    if rig.get("commodity") and str(rig["commodity"]).casefold() != "unknown":
        return str(rig["commodity"])
    tonnes = rig.get("tonnes") or {}
    return max(tonnes, key=lambda name: (int(tonnes[name] or 0), name)) if tonnes else ""


def booking_rig(rigs, lat, lon, radius_m, within_m=BOOK_WITHIN_M):
    """The rig a tonne refined here came from: the nearest one within reach."""
    best = None
    for slot, rig in (rigs or {}).items():
        distance = surface_distance_m(lat, lon, rig["lat"], rig["lon"], radius_m)
        if distance <= within_m and (best is None or distance < best[0]):
            best = (distance, slot)
    return best[1] if best else None


def rig_advice(rows, spacing_m=SPACING_M, warn_m=WARN_M):
    """What to tell you about your rigs, from the model's rows: too close to
    place another, too far (lost at 5 km), ready to collect."""
    tracked = [row for row in rows or () if row.get("tracked") and row.get("distance_m") is not None]
    close = sorted((row for row in tracked if row["distance_m"] < spacing_m), key=lambda row: row["distance_m"])
    far = sorted((row for row in tracked if warn_m and row["distance_m"] >= warn_m), key=lambda row: -row["distance_m"])
    ready = [row["slot"] for row in tracked if row.get("here") and row.get("ready")]
    return {
        "too_close": close[0]["slot"] if close else None,
        "too_far": [{"slot": row["slot"], "distance": round(row["distance_m"]),
                     "last": row["distance_m"] >= LAST_WARNING_M} for row in far],
        "ready": ready,
    }


def placed_order(rigs):
    """The order to collect them: the order they went down (5.5.17)."""
    return [slot for slot, _rig in sorted(rigs.items(), key=lambda item: (float(item[1].get("at") or 0), item[0]))]


def hold_row(name, used, capacity, partial=False):
    """One hold as the tracker shows it: how full, never what's in it. A
    partial ship hold only knows what was unloaded into it this trip."""
    used, capacity = max(0, int(used or 0)), max(0, int(capacity or 0))
    return {"name": str(name), "used": used, "capacity": capacity,
            "free": None if partial else max(0, capacity - used), "partial": bool(partial)}


def build_rig_model(rigs, lat, lon, heading, radius_m, body="", now=None, in_rhino=False, hint="", holds=(),
                    here_m=HERE_M, ready_for=None):
    """The overlay's model, or None when there are no rigs here and you're
    not out in the Rhino (then: six empty dials and the key to press)."""
    if lat is None or lon is None or not radius_m or not (rigs or in_rhino):
        return None
    now = now if now is not None else time.time()
    slots, nearest = [], None
    for slot in range(1, SLOTS + 1):
        rig = rigs.get(slot)
        if not rig:
            slots.append({"slot": slot, "tracked": False})
            continue
        distance = surface_distance_m(lat, lon, rig["lat"], rig["lon"], radius_m)
        bearing = bearing_deg(lat, lon, rig["lat"], rig["lon"])
        relative = (bearing - heading) % 360.0 if heading is not None else bearing
        row = {"slot": slot, "tracked": True, "distance_m": round(distance, 1), "bearing": round(bearing, 1),
               "relative": round(relative, 1), "here": distance <= here_m, "at": float(rig["at"]),
               "age_s": round(max(0.0, now - float(rig["at"]))), "commodity": rig_commodity(rig),
               "tonnes": sum(int(value or 0) for value in (rig.get("tonnes") or {}).values())}
        # When it's ready, if your rigs have taught us (``ready_for(rig)``).
        row["ready_s"] = ready_for(rig) if ready_for else None
        row["ready"] = bool(row["ready_s"]) and row["age_s"] >= row["ready_s"]
        slots.append(row)
        if nearest is None or distance < nearest["distance_m"]:
            nearest = row
    if nearest:
        nearest["nearest"] = True
    order = placed_order(rigs)
    for row in slots:
        if order and row.get("slot") == order[0] and row.get("tracked"):
            row["next"] = True
    return {"body": str(body or ""), "slots": slots, "tracked": len(rigs), "order": order,
            "heading_known": heading is not None, "hint": "" if rigs else str(hint or ""),
            "holds": [dict(row) for row in holds or () if row.get("capacity")]}


class RigTrackerHUD(ColonyNeedsHUD):
    """Native window proxy for the Rig Tracker page: shown while there are
    rigs on the body you're on."""

    def _position(self):
        return (_integer(self.config.get("rig_tracker_hud_x"), 1320),
                _integer(self.config.get("rig_tracker_hud_y"), 400))
