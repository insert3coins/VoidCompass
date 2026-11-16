"""Landing pads at surface stations, learnt from your own landings (5.8.3).

Orbital starports and carriers have one layout each (outrider/pads.py), but
planetary ports, surface outposts and Odyssey settlements don't, and nobody
has mapped which numbered pad is where. So the app learns them: docking is
granted with a pad number, and when you've landed and docked on it, Status.json
has exactly where that pad is. Next time you're given that pad there, the
planet compass can take you to it.

Kept per station (its MarketID), per pad: where it is, which way a ship
faces on it, and how many times you've landed on it (later landings refine it).

Stations of one design share a layout, each copy turned its own way. So each
design (its type, its pads by size, and for settlements its economy) keeps
where its pads lie relative to one another and which way each faces. One
landing at another copy then says how that copy is turned and where it sits,
and with that, where all its other pads are. Each later landing checks the
design: one whose predictions keep missing isn't used."""
from __future__ import annotations

import json
import math
import os
import threading
import time

from voidcompass.core.persistence_queue import persistence_queue

# A landing that far from what's known of a pad isn't the same pad (a moved
# settlement, a mislabelled grant): it starts the pad again.
SAME_PAD_M = 120.0
# A design's prediction this close to where you landed is right; further off,
# a miss. A design with more misses than hits (two at least) isn't used.
PREDICT_OK_M = 30.0
TURNS = ("ahead", "ahead-right", "right", "behind-right", "behind", "behind-left", "left", "ahead-left")


def distance_m(lat1, lon1, lat2, lon2, radius_m):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.cos(p2) * math.sin(dl)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def way_words(distance, bearing, heading=None):
    """'380 m ahead-left' (or a compass point without a heading)."""
    far = f"{distance / 1000:.1f} km" if distance >= 1000 else f"{round(distance / 10) * 10:.0f} m" if distance >= 100 else f"{distance:.0f} m"
    if heading is None:
        points = ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")
        return f"{far} {points[int(((bearing + 22.5) % 360) // 45)]}"
    offset = (bearing - heading + 360.0) % 360.0
    return f"{far} {TURNS[int(((offset + 22.5) % 360) // 45)]}"


def _local(origin, lat, lon, radius_m):
    """(east, north) metres of (lat, lon) from ``origin`` (a few km at most)."""
    scale = math.pi / 180.0 * radius_m
    return ((lon - origin[1] + 540.0) % 360.0 - 180.0) * scale * math.cos(math.radians(origin[0])), (lat - origin[0]) * scale


def _global(origin, east, north, radius_m):
    scale = math.pi / 180.0 * radius_m
    lat = origin[0] + north / scale
    lon = origin[1] + east / (scale * max(1e-9, math.cos(math.radians(origin[0]))))
    return lat, (lon + 540.0) % 360.0 - 180.0


def _turn(x, y, degrees):
    """(x, y) (east, north) turned clockwise by ``degrees``, as a heading turns."""
    a = math.radians(degrees)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def _angle(value):
    return float(value) % 360.0


def _mean_angle(a, b, weight_a):
    """The mean of two headings, ``a`` counted ``weight_a`` times."""
    x = math.cos(math.radians(a)) * weight_a + math.cos(math.radians(b))
    y = math.sin(math.radians(a)) * weight_a + math.sin(math.radians(b))
    return math.degrees(math.atan2(y, x)) % 360.0


def design_of(kind, counts, economy=""):
    """A station design's key: its type and pads by size (and a settlement's
    economy, as settlement designs go by it). "" without its pad counts."""
    if not isinstance(counts, dict) or not any(int(counts.get(size) or 0) for size in ("Small", "Medium", "Large")):
        return ""
    key = f"{str(kind or '').casefold()}|S{int(counts.get('Small') or 0)}M{int(counts.get('Medium') or 0)}L{int(counts.get('Large') or 0)}"
    if "settlement" in str(kind or "").casefold() and economy:
        key += "|" + str(economy).casefold().strip("$;").replace("economy_", "")
    return key


class SurfacePadStore:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.stations = {}
        self.designs = {}
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        stations = data.get("stations") if isinstance(data, dict) else None
        if isinstance(stations, dict):
            with self.lock:
                self.stations = {str(key): value for key, value in stations.items() if isinstance(value, dict)}
        designs = data.get("designs") if isinstance(data, dict) else None
        if isinstance(designs, dict):
            with self.lock:
                self.designs = {str(key): value for key, value in designs.items() if isinstance(value, dict)}

    def _payload(self):
        with self.lock:
            return {"schema": 2, "stations": json.loads(json.dumps(self.stations)), "designs": json.loads(json.dumps(self.designs))}

    def save(self):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None, delay_s=0.5)

    def pad(self, market_id, pad):
        """{"lat", "lon", "landings"} for a pad you've landed on, or None."""
        with self.lock:
            found = ((self.stations.get(str(market_id)) or {}).get("pads") or {}).get(str(int(pad)))
            return dict(found) if isinstance(found, dict) else None

    def station(self, market_id):
        with self.lock:
            found = self.stations.get(str(market_id))
            return json.loads(json.dumps(found)) if isinstance(found, dict) else None

    def learn(self, market_id, pad, lat, lon, radius_m, *, name="", system="", body="", kind="", heading=None,
              counts=None, economy="", now=None):
        """You've landed on ``pad`` there: keep where it is and which way you
        faced on it (refined by each landing), check the station's design
        against it, and teach the design. The pad as kept."""
        now = time.time() if now is None else now
        with self.lock:
            entry = self.stations.setdefault(str(market_id), {"pads": {}})
            entry.update({key: value for key, value in (("name", name), ("system", system), ("body", body), ("type", kind)) if value})
            if radius_m:
                entry["radius"] = float(radius_m)
            design = design_of(kind or entry.get("type"), counts if counts is not None else entry.get("counts"), economy)
            if counts is not None:
                entry["counts"] = {size: int((counts or {}).get(size) or 0) for size in ("Small", "Medium", "Large")}
            if design:
                entry["design"] = design
            # The design's word on a pad you'd not landed on here: right, or a miss.
            first_here = str(int(pad)) not in (entry.get("pads") or {})
            guess = self._predict(entry, pad) if first_here else None
            if guess and radius_m and entry.get("design"):
                checks = self.designs.setdefault(entry["design"], {}).setdefault("checks", {"ok": 0, "miss": 0})
                checks["ok" if distance_m(guess["lat"], guess["lon"], lat, lon, radius_m) <= PREDICT_OK_M else "miss"] += 1
            pads = entry.setdefault("pads", {})
            known = pads.get(str(int(pad)))
            if isinstance(known, dict) and radius_m and \
                    distance_m(known["lat"], known["lon"], lat, lon, radius_m) <= SAME_PAD_M:
                count = int(known.get("landings") or 1)
                known["lat"] = round((known["lat"] * count + lat) / (count + 1), 7)
                known["lon"] = round((known["lon"] * count + lon) / (count + 1), 7)
                if heading is not None:
                    known["heading"] = round(_mean_angle(known["heading"], _angle(heading), count)
                                             if known.get("heading") is not None else _angle(heading), 1)
                known["landings"], known["at"] = count + 1, round(now, 1)
            else:
                pads[str(int(pad))] = {"lat": round(float(lat), 7), "lon": round(float(lon), 7), "landings": 1, "at": round(now, 1)}
                if heading is not None:
                    pads[str(int(pad))]["heading"] = round(_angle(heading), 1)
            self._teach(entry)
        self.save()
        return self.pad(market_id, pad)

    # -- designs ----------------------------------------------------------------------------
    def _placement(self, entry, layout):
        """(origin (lat, lon), turn) of a station's copy of a design, from a pad
        landed on there that the design knows; None without one."""
        radius = entry.get("radius")
        pads = entry.get("pads") or {}
        shared = [(int(here.get("landings") or 1), key) for key, here in pads.items()
                  if key in layout and here.get("heading") is not None and layout[key].get("heading") is not None]
        if not shared or not radius:
            return None
        key = max(shared)[1]
        here, model = pads[key], layout[key]
        turn = (here["heading"] - model["heading"]) % 360.0
        dx, dy = _turn(model["x"], model["y"], turn)
        anchor = (here["lat"], here["lon"])
        origin = _global(anchor, -dx, -dy, radius)
        return origin, turn

    def _teach(self, entry):
        """What this station's landed pads say about its design's layout."""
        design = entry.get("design")
        pads = {key: here for key, here in (entry.get("pads") or {}).items() if here.get("heading") is not None}
        radius = entry.get("radius")
        if not design or not pads or not radius:
            return
        record = self.designs.setdefault(design, {})
        layout = record.setdefault("pads", {})
        if not layout:
            # The first copy seen: its most-landed pad is the design's origin, facing north.
            key = max((int(here.get("landings") or 1), key) for key, here in pads.items())[1]
            layout[key] = {"x": 0.0, "y": 0.0, "heading": 0.0, "n": 1}
        placed = self._placement(entry, layout)
        if placed is None:
            return
        origin, turn = placed
        for key, here in pads.items():
            east, north = _local(origin, here["lat"], here["lon"], radius)
            x, y = _turn(east, north, -turn)
            heading = (here["heading"] - turn) % 360.0
            model = layout.get(key)
            if model is None:
                layout[key] = {"x": round(x, 2), "y": round(y, 2), "heading": round(heading, 1), "n": 1}
            elif math.hypot(model["x"] - x, model["y"] - y) <= PREDICT_OK_M:
                n = int(model.get("n") or 1)
                model.update(x=round((model["x"] * n + x) / (n + 1), 2), y=round((model["y"] * n + y) / (n + 1), 2),
                             heading=round(_mean_angle(model["heading"], heading, n), 1), n=n + 1)
        record["stations"] = len({market for market, station in self.stations.items() if station.get("design") == design})

    def design_ok(self, design):
        checks = (self.designs.get(design) or {}).get("checks") or {}
        miss = int(checks.get("miss") or 0)
        return not (miss >= 2 and miss > int(checks.get("ok") or 0))

    def _predict(self, entry, pad):
        """Where ``pad`` is at this station by its design, or None."""
        design = entry.get("design")
        record = self.designs.get(design or "") or {}
        layout = record.get("pads") or {}
        model = layout.get(str(int(pad)))
        if not design or not model or not self.design_ok(design):
            return None
        placed = self._placement(entry, layout)
        if placed is None:
            return None
        origin, turn = placed
        east, north = _turn(model["x"], model["y"], turn)
        lat, lon = _global(origin, east, north, entry["radius"])
        return {"lat": round(lat, 7), "lon": round(lon, 7), "heading": round((model["heading"] + turn) % 360.0, 1),
                "predicted": True, "design": design}

    def find(self, market_id, pad):
        """Where a pad is: landed on there, or worked out from the station's
        design (then "predicted" is set). None when neither knows."""
        known = self.pad(market_id, pad)
        if known:
            return known
        with self.lock:
            entry = self.stations.get(str(market_id))
            return self._predict(entry, pad) if isinstance(entry, dict) else None

    def note_settlement(self, market_id, lat, lon, *, name="", system="", body="", radius_m=None):
        """Approaching it (ApproachSettlement): where the settlement is."""
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return
        with self.lock:
            entry = self.stations.setdefault(str(market_id), {"pads": {}})
            entry.update({key: value for key, value in (("name", name), ("system", system), ("body", body)) if value})
            entry["centre"] = [round(lat, 7), round(lon, 7)]
            if radius_m and not entry.get("radius"):
                entry["radius"] = float(radius_m)
        self.save()

    def known_pads(self, market_id):
        """What's known of a station's pads before you're given one:
        {"landed": [pad numbers], "worked_out": [pad numbers its design
        places here], "pads": how many it has, if known}, or None if it's
        never been seen."""
        with self.lock:
            entry = self.stations.get(str(market_id))
            if not isinstance(entry, dict):
                return None
            landed = sorted(int(key) for key in entry.get("pads") or {})
            design = entry.get("design") or ""
            layout = (self.designs.get(design) or {}).get("pads") or {}
            worked = []
            if design and layout and self.design_ok(design) and self._placement(entry, layout) is not None:
                worked = sorted(int(key) for key in layout if int(key) not in landed)
            counts = entry.get("counts") or {}
            total = sum(int(counts.get(size) or 0) for size in ("Small", "Medium", "Large")) or None
            return {"landed": landed, "worked_out": worked, "pads": total}

    def note_counts(self, market_id, counts):
        """The station's pads by size, from the Docked event's LandingPads."""
        if not isinstance(counts, dict):
            return
        with self.lock:
            entry = self.stations.get(str(market_id))
            if entry is not None:
                entry["counts"] = {size: int(counts.get(size) or 0) for size in ("Small", "Medium", "Large")}
        self.save()

    # -- sharing ------------------------------------------------------------------------------
    def summary(self):
        """How much has been learnt, for Settings."""
        with self.lock:
            stations = [entry for entry in self.stations.values() if entry.get("pads")]
            designs = [key for key, record in self.designs.items() if record.get("pads")]
            return {"stations": len(stations), "pads": sum(len(entry["pads"]) for entry in stations),
                    "designs": len(designs), "trusted": sum(1 for key in designs if self.design_ok(key))}

    def export(self, app="VoidCompass"):
        """What's been learnt, for other commanders and other apps: a plain,
        versioned file without the store's own bookkeeping. Designs give each
        pad's place in metres (x east, y north) and the heading a ship faces on
        it, with the design turned to face north on its first pad; stations
        give each pad landed on, by latitude and longitude."""
        with self.lock:
            designs = []
            for key, record in sorted(self.designs.items()):
                layout = record.get("pads") or {}
                if not layout:
                    continue
                kind, sizes, *economy = key.split("|")
                checks = record.get("checks") or {}
                designs.append({
                    "design": key, "station_type": kind, "pads_by_size": sizes, "economy": economy[0] if economy else "",
                    "pads": [{"pad": int(pad), "x_m": round(model["x"], 1), "y_m": round(model["y"], 1),
                              "heading": round(model["heading"], 1)} for pad, model in sorted(layout.items(), key=lambda item: int(item[0]))],
                    "stations_seen": int(record.get("stations") or 0),
                    "checks": {"right": int(checks.get("ok") or 0), "missed": int(checks.get("miss") or 0)},
                    "trusted": self.design_ok(key),
                })
            stations = []
            for market, entry in sorted(self.stations.items()):
                if not entry.get("pads"):
                    continue
                stations.append({
                    "market_id": int(market) if str(market).isdigit() else market, "name": entry.get("name", ""),
                    "system": entry.get("system", ""), "body": entry.get("body", ""), "station_type": entry.get("type", ""),
                    "design": entry.get("design", ""), "pads_by_size": entry.get("counts"),
                    "planet_radius_m": round(float(entry["radius"]), 1) if entry.get("radius") else None,
                    "pads": [{"pad": int(pad), "lat": here["lat"], "lon": here["lon"],
                              **({"heading": here["heading"]} if here.get("heading") is not None else {})}
                             for pad, here in sorted(entry["pads"].items(), key=lambda item: int(item[0]))],
                })
        return {"format": "voidcompass-surface-pads", "version": 1, "exported": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "app": app, "designs": designs, "stations": stations}

    def merge(self, data, now=None):
        """Another commander's export (or another app's, in this format),
        pooled with yours. Pads you've landed on keep your landings; others
        are added. A design you know takes their pads only through a pad you
        both know (each copy sets its own origin); one you don't is taken as
        theirs. {"pads", "stations", "designs"} added, or None if it isn't one."""
        if not isinstance(data, dict) or data.get("format") != "voidcompass-surface-pads" or int(data.get("version") or 0) != 1:
            return None
        now = time.time() if now is None else now
        added = {"pads": 0, "stations": 0, "designs": 0}
        with self.lock:
            for station in data.get("stations") or ():
                if not isinstance(station, dict) or station.get("market_id") in (None, ""):
                    continue
                key = str(station["market_id"])
                if key not in self.stations:
                    added["stations"] += 1
                entry = self.stations.setdefault(key, {"pads": {}})
                for field, value in (("name", station.get("name")), ("system", station.get("system")), ("body", station.get("body")),
                                     ("type", station.get("station_type")), ("design", station.get("design")),
                                     ("counts", station.get("pads_by_size")), ("radius", station.get("planet_radius_m"))):
                    if value and not entry.get(field):
                        entry[field] = value
                pads = entry.setdefault("pads", {})
                for row in station.get("pads") or ():
                    try:
                        pad, lat, lon = str(int(row["pad"])), float(row["lat"]), float(row["lon"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if pad in pads:
                        continue
                    pads[pad] = {"lat": round(lat, 7), "lon": round(lon, 7), "landings": 1, "at": round(now, 1), "shared": True}
                    if row.get("heading") is not None:
                        pads[pad]["heading"] = round(_angle(row["heading"]), 1)
                    added["pads"] += 1
            for design in data.get("designs") or ():
                if not isinstance(design, dict) or not design.get("design"):
                    continue
                try:
                    theirs = {str(int(row["pad"])): (float(row["x_m"]), float(row["y_m"]), _angle(row["heading"]))
                              for row in design.get("pads") or ()}
                except (KeyError, TypeError, ValueError):
                    continue
                if not theirs:
                    continue
                record = self.designs.setdefault(str(design["design"]), {})
                layout = record.setdefault("pads", {})
                if not layout:
                    for pad, (x, y, heading) in theirs.items():
                        layout[pad] = {"x": round(x, 2), "y": round(y, 2), "heading": round(heading, 1), "n": 1}
                    checks = design.get("checks") or {}
                    record["checks"] = {"ok": int(checks.get("right") or 0), "miss": int(checks.get("missed") or 0)}
                    added["designs"] += 1
                    continue
                common = next((pad for pad in theirs if pad in layout), None)
                if common is None:
                    continue
                # Their frame onto ours, through the pad you both know.
                turn = (layout[common]["heading"] - theirs[common][2]) % 360.0
                for pad, (x, y, heading) in theirs.items():
                    if pad in layout:
                        continue
                    dx, dy = _turn(x - theirs[common][0], y - theirs[common][1], turn)
                    layout[pad] = {"x": round(layout[common]["x"] + dx, 2), "y": round(layout[common]["y"] + dy, 2),
                                   "heading": round((heading + turn) % 360.0, 1), "n": 1}
        self.save()
        return added
