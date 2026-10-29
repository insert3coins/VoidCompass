"""System-map presentation data. Public catalogue rows never become discoveries."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import math
import threading
import time

from voidcompass.services import spansh

AU_M = 149_597_870_700.0
SOLAR_RADIUS_M = 695_700_000.0
BODY_FIELDS = frozenset({
    "bodyId", "id64", "name", "type", "subType", "spectralClass", "luminosity", "mainStar",
    "solarRadius", "solarMasses", "earthMasses", "radius", "parents", "rings", "belts",
    "semiMajorAxis", "orbitalPeriod", "orbitalEccentricity", "orbitalInclination", "argOfPeriapsis",
    "ascendingNode", "meanAnomaly", "timestamps", "updateTime", "axialTilt", "rotationalPeriod",
    "rotationalPeriodTidallyLocked", "surfaceTemperature", "surfacePressure", "gravity",
    "distanceToArrival", "atmosphereType", "atmosphereComposition", "solidComposition", "isLandable", "volcanismType",
})


def finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def identifier(value):
    text = str(value or "").strip()
    return text if text.isascii() and text.isdigit() and len(text) <= 20 else ""


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError, TypeError, OverflowError):
        return 0.0


STATION_FIELDS = ("id", "name", "type", "distanceToArrival", "updateTime", "carrierName", "carrierDockingAccess",
                  "primaryEconomy", "government")


def _station(row, **extra):
    """A public station, trimmed to what the map shows (Spansh rows carry whole markets)."""
    out = {key: row[key] for key in STATION_FIELDS if row.get(key) is not None}
    pads = row.get("landingPads")
    if isinstance(pads, dict):
        out["pads"] = {size: int(finite(pads.get(size)) or 0) for size in ("large", "medium", "small")}
    out.update({key: value for key, value in extra.items() if value is not None})
    return out


def _composition(value):
    if isinstance(value, dict):
        return {str(key): number for key, raw in value.items() if (number := finite(raw)) is not None}
    return {str(row["Name"]): number for row in value or () if isinstance(row, dict)
            and row.get("Name") and (number := finite(row.get("Percent"))) is not None}


def journal_body(item, *, barycentre=False):
    body_id = finite(item.get("body_id"))
    if body_id is None or body_id < 0 or body_id != int(body_id):
        return None
    star = bool(item.get("is_star") or item.get("star_type"))
    kind = "Barycentre" if barycentre else "Star" if star else "Planet"
    radius = finite(item.get("radius"))
    star_type = str(item.get("star_type") or "")
    subtype = {"N": "Neutron Star", "H": "Black Hole", "SupermassiveBlackHole": "Black Hole"}.get(star_type)
    if not subtype and star_type.startswith("D"):
        subtype = "White Dwarf"
    if not subtype:
        subtype = f"{star_type} Star" if star else item.get("planet_class") or item.get("class")
    subtype = {"Earthlike body": "Earth-like world", "Metal rich body": "Metal-rich body"}.get(subtype, subtype)
    result = {
        "bodyId": int(body_id), "name": item.get("name") or item.get("full_name"), "type": kind,
        "subType": subtype, "spectralClass": star_type or None, "luminosity": item.get("luminosity"),
        "solarRadius": radius / SOLAR_RADIUS_M if star and radius is not None else None,
        "solarMasses": finite(item.get("mass")) if star else None,
        "earthMasses": finite(item.get("mass")) if not star else None,
        "radius": radius / 1000.0 if not star and radius is not None else None,
        "semiMajorAxis": (axis / AU_M) if (axis := finite(item.get("semi_major_axis"))) is not None else None,
        "orbitalPeriod": (period / 86400.0) if (period := finite(item.get("orbital_period"))) is not None else None,
        "rotationalPeriod": (period / 86400.0) if (period := finite(item.get("rotation_period"))) is not None else None,
        "orbitalEccentricity": finite(item.get("eccentricity")),
        "orbitalInclination": finite(item.get("orbital_inclination")), "argOfPeriapsis": finite(item.get("periapsis")),
        "ascendingNode": finite(item.get("ascending_node")), "meanAnomaly": finite(item.get("mean_anomaly")),
        "axialTilt": finite(item.get("axial_tilt")), "surfaceTemperature": finite(item.get("surface_temp")),
        "surfacePressure": finite(item.get("surface_pressure")), "gravity": finite(item.get("gravity_g")),
        "distanceToArrival": finite(item.get("distance_to_arrival")), "atmosphereType": item.get("atmosphere_type") or item.get("atmosphere"),
        "rotationalPeriodTidallyLocked": item.get("tidal_lock"), "isLandable": item.get("landable"),
        "volcanismType": item.get("volcanism"),
    }
    if item.get("parents"):
        result["parents"] = deepcopy(item["parents"])
    if item.get("rings") is not None:
        result["rings"] = [{"name": row.get("Name") or row.get("name"),
                            "type": str(row.get("RingClass") or row.get("type") or "Rocky").removeprefix("eRingClass_").replace("MetalRich", "Metal Rich").replace("Metalic", "Metallic"),
                            "innerRadius": finite(row.get("InnerRad", row.get("innerRadius"))),
                            "outerRadius": finite(row.get("OuterRad", row.get("outerRadius")))}
                           for row in item.get("rings") or () if isinstance(row, dict)]
    for key, source in (("atmosphereComposition", "atmosphere_composition"), ("solidComposition", "composition")):
        if item.get(source):
            result[key] = _composition(item[source])
    stamp = item.get("scan_timestamp") or item.get("timestamp")
    if result.get("meanAnomaly") is not None and _stamp(stamp):
        result["timestamps"] = {"meanAnomaly": str(stamp)}
    result["_survey"] = {
        "scanned": not barycentre and not item.get("signal_only", False), "mapped": bool(item.get("dss_complete")),
        "wasDiscovered": item.get("was_discovered"), "wasMapped": item.get("was_mapped"),
        "wasFootfalled": item.get("was_footfalled"), "firstFootfall": bool(item.get("first_footfall")),
        "bio": int(finite(item.get("bio_count")) or 0), "geo": int(finite(item.get("geo_count")) or 0),
        "value": finite(item.get("dss_reward")) or finite(item.get("reward")),
    }
    return {key: value for key, value in result.items() if value is not None}


def merge_system(name, address, scans, barycentres=(), public=None, target=None, expected=None):
    """Merge by journal BodyID, retaining each mean anomaly's own epoch."""
    public = public if isinstance(public, dict) else {}
    same_name = str(public.get("name") or "").casefold() == str(name or "").casefold()
    same_address = not address or identifier(public.get("id64")) == identifier(address)
    if not same_name or not same_address:
        public = {}
    rows = {}
    for raw in public.get("bodies") or ():
        if not isinstance(raw, dict) or finite(raw.get("bodyId")) is None:
            continue
        body_id = int(raw["bodyId"])
        if body_id < 0:
            continue
        row = {key: deepcopy(value) for key, value in raw.items() if key in BODY_FIELDS}
        if row.get("id64") is not None:
            row["id64"] = identifier(row["id64"])
        row["bodyId"] = body_id
        row["_source"] = "spansh"
        row["_survey"] = {"scanned": False, "mapped": False}
        surface = [_station(st, latitude=finite(st.get("latitude")), longitude=finite(st.get("longitude")))
                   for st in raw.get("stations") or () if isinstance(st, dict) and st.get("name")]
        if surface:
            row["surfaceStations"] = surface[:40]
        rows[body_id] = row
    for raw, bary in [*((row, False) for row in scans or ()), *((row, True) for row in barycentres or ())]:
        if not isinstance(raw, dict):
            continue
        if raw.get("system_address") and address and identifier(raw["system_address"]) != identifier(address):
            continue
        row = journal_body(raw, barycentre=bary)
        if row is None:
            continue
        old = rows.get(row["bodyId"], {})
        # A phase and its epoch are one measurement; a partial scan cannot split them.
        if "timestamps" not in row:
            row.pop("meanAnomaly", None)
        rows[row["bodyId"]] = {**old, **row, "_source": "journal+spansh" if old else "journal"}
    bodies = list(rows.values())
    for row in bodies:
        row.setdefault("name", f"{name} {row['bodyId']}")
        if row["bodyId"] == 0:
            row["parents"] = []
        row["rings"] = [r for r in row.get("rings") or () if isinstance(r, dict)
                        and (finite(r.get("innerRadius")) or 0) > 0
                        and (finite(r.get("outerRadius")) or 0) > float(r["innerRadius"])]
        phase = (row.get("timestamps") or {}).get("meanAnomaly")
        row["_epoch"] = _stamp(phase)
        row["_resolved"] = row["bodyId"] == 0 or bool(
            row.get("parents") and (finite(row.get("semiMajorAxis")) or 0) > 0
            and (finite(row.get("orbitalPeriod")) or 0) > 0 and row["_epoch"]
            and finite(row.get("meanAnomaly")) is not None and finite(row.get("ascendingNode")) is not None
            and finite(row.get("orbitalInclination")) is not None and finite(row.get("argOfPeriapsis")) is not None)
        # Size and parent known but not the whole orbit: drawn on a circle at its real distance, phase unknown.
        row["_approx"] = not row["_resolved"] and row.get("type") != "Barycentre" and bool(row.get("parents")) \
            and (finite(row.get("semiMajorAxis")) or 0) > 0
    return {
        "name": str(name or ""), "id64": identifier(address) or identifier(public.get("id64")),
        "bodies": sorted(bodies, key=lambda row: row["bodyId"]),
        "bodyCount": expected if expected is not None else public.get("bodyCount"),
        "stations": [_station(row) for row in public.get("stations") or () if isinstance(row, dict)][:80], "target": target or {},
        "date": public.get("date") or public.get("updateTime"),
    }


class SystemMapCatalogue:
    """Small public cache; requests never hold the journal/UI thread."""

    def __init__(self, fetch=None, clock=time.monotonic):
        self.fetch = fetch or spansh.system_body_dump
        self.clock = clock
        self.lock = threading.RLock()
        self.entries = OrderedDict()
        self.inflight = set()

    def request(self, name, address=None):
        key = (str(name or "").strip().casefold(), identifier(address))
        if not key[0]:
            return {"status": "waiting", "detail": "Waiting for your journal's current system.", "system": {}}
        with self.lock:
            entry = self.entries.setdefault(key, {"status": "loading", "detail": "Requesting system bodies from Spansh…", "system": {}, "next": 0})
            self.entries.move_to_end(key)
            if self.clock() >= entry["next"] and key not in self.inflight and len(self.inflight) < 2:
                self.inflight.add(key)
                threading.Thread(target=self._load, args=(key, str(name).strip()), name="system-map-catalogue", daemon=True).start()
            while len(self.entries) > 16:
                removable = next((old for old in self.entries if old not in self.inflight and old != key), None)
                if removable is None:
                    break
                self.entries.pop(removable)
            return {k: v for k, v in entry.items() if k != "next"}

    def _load(self, key, name):
        try:
            body = self.fetch(name, key[1] or None)
            if str(body.get("name") or "").casefold() != key[0] or (key[1] and identifier(body.get("id64")) != key[1]):
                raise spansh.SpanshError("Spansh returned a different system; keeping your journal data.")
            answer = {"status": "ready", "detail": "Spansh catalogue linked. Your journal scans take priority.", "system": body, "next": self.clock() + 600}
        except Exception as exc:
            with self.lock:
                kept = self.entries.get(key, {}).get("system") or {}
            answer = {"status": "cached" if kept else "unavailable", "detail": f"Spansh unavailable: {str(exc)[:180]} Using available journal and cached bodies.", "system": kept, "next": self.clock() + 60}
        with self.lock:
            self.entries[key] = answer
            self.inflight.discard(key)
