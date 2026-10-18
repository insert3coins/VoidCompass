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
# Rigs left untouched this long are forgotten.
FORGET_S = 7 * 86400


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


class RigStore:
    """Rigs per body: ``{key: {"system", "body", "rigs": {slot: {"lat", "lon", "at"}}}}``."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.bodies = {}
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

    def _payload(self):
        with self.lock:
            return {"schema": 1, "bodies": json.loads(json.dumps(self.bodies))}

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

    def mark(self, slot, system, body, lat, lon, now=None):
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
                del rigs[str(slot)]
                outcome = "collected"
            else:
                # One rig per number: a rig of that number elsewhere was left behind.
                for other_key, other in self.bodies.items():
                    if other_key != key:
                        (other.get("rigs") or {}).pop(str(slot), None)
                rigs[str(slot)] = {"lat": round(float(lat), 6), "lon": round(float(lon), 6), "at": round(now, 1)}
                outcome = "placed"
            self.bodies = {name: value for name, value in self.bodies.items() if value.get("rigs")}
        self.save()
        return outcome

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


def hold_row(name, used, capacity, partial=False):
    """One hold as the tracker shows it: how full, never what's in it. A
    partial ship hold only knows what was unloaded into it this trip."""
    used, capacity = max(0, int(used or 0)), max(0, int(capacity or 0))
    return {"name": str(name), "used": used, "capacity": capacity,
            "free": None if partial else max(0, capacity - used), "partial": bool(partial)}


def build_rig_model(rigs, lat, lon, heading, radius_m, body="", now=None, in_rhino=False, hint="", holds=(),
                    here_m=HERE_M):
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
               "age_s": round(max(0.0, now - float(rig["at"])))}
        slots.append(row)
        if nearest is None or distance < nearest["distance_m"]:
            nearest = row
    if nearest:
        nearest["nearest"] = True
    order = collect_order((lat, lon), rigs, radius_m)
    return {"body": str(body or ""), "slots": slots, "tracked": len(rigs), "order": order,
            "heading_known": heading is not None, "hint": "" if rigs else str(hint or ""),
            "holds": [dict(row) for row in holds or () if row.get("capacity")]}


class RigTrackerHUD(ColonyNeedsHUD):
    """Native window proxy for the Rig Tracker page: shown while there are
    rigs on the body you're on."""

    def _position(self):
        return (_integer(self.config.get("rig_tracker_hud_x"), 1320),
                _integer(self.config.get("rig_tracker_hud_y"), 400))
