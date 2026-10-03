"""What the journal has said about the system you are in (5.5.2.1): its scans,
barycentres, signals, stations docked at and how far the FSS has got.

Colonisation uses it to send your own scans to Raven Colonial as the
system's bodies (SrvSurvey's "Update system bodies") and for the station
identifier. Only the current system is kept; it starts over on each jump.
"""

from __future__ import annotations

# Raven Colonial body types from a planet class (SrvSurvey's map).
_PLANET_TYPES = {
    "ammonia world": "aw", "earthlike body": "elw", "high metal content body": "hmc", "icy body": "ib",
    "metal rich body": "mrb", "rocky body": "rb", "rocky ice body": "ri", "water giant": "wg", "water world": "ww",
}
_STAR_NAMES = {
    "O": "O (Blue-White) Star", "B": "B (Blue-White) Star", "A": "A (Blue-White) Star", "F": "F (White) Star",
    "G": "G (White-Yellow) Star", "K": "K (Yellow-Orange) Star", "M": "M (Red dwarf) Star", "L": "L (Brown dwarf) Star",
    "T": "T (Brown dwarf) Star", "Y": "Y (Brown dwarf) Star", "TTS": "T Tauri Star", "MS": "MS-type Star",
    "S": "S-type star", "N": "Neutron Star", "H": "Black Hole", "SupermassiveBlackHole": "Supermassive Black Hole",
}
_LIGHT_SECOND_M = 299_792_458
_G = 9.80665


def _ring_class(value):
    """``eRingClass_MetalRich`` -> ``Metal Rich``."""
    text = str(value or "").replace("eRingClass_", "")
    out = ""
    for index, char in enumerate(text):
        if index and char.isupper() and not text[index - 1].isupper():
            out += " "
        out += char
    return out or "Unknown"


def _parents(raw):
    ids = []
    for item in raw.get("Parents") or ():
        if isinstance(item, dict):
            ids.extend(int(value) for value in item.values() if value is not None)
    return ids


def _star_body_type(star_type):
    star_type = str(star_type or "")
    if star_type in ("H", "SupermassiveBlackHole"):
        return "bh"
    if star_type == "N":
        return "ns"
    if star_type.startswith("D"):
        return "wd"
    return "st"


def _star_sub_type(star_type):
    star_type = str(star_type or "")
    if star_type.startswith("D"):
        return f"White Dwarf ({star_type}) Star"
    if star_type.startswith("W"):
        return f"Wolf-Rayet ({star_type}) Star"
    if star_type.startswith("C"):
        return f"C ({star_type}) Star"
    return _STAR_NAMES.get(star_type, f"{star_type} Star" if star_type else "Star")


class SystemJournal:
    def __init__(self):
        self.reset(None, "")

    def reset(self, address, name):
        self.address = address
        self.name = name or ""
        self.scans = {}            # BodyID -> raw Scan
        self.barycentres = {}      # BodyID -> raw ScanBaryCentre
        self.body_signals = {}     # BodyID -> {"bio": n, "geo": n}
        self.signals = {}          # SignalName -> raw FSSSignalDiscovered
        self.docks = {}            # MarketID -> raw Docked
        self.honk = None           # raw FSSDiscoveryScan
        self.all_bodies = None     # raw FSSAllBodiesFound
        self.nav_beacon = None     # raw NavBeaconScan
        self.revision = 0

    # -- the journal -----------------------------------------------------
    def observe(self, event, raw):
        """Record one raw journal event; True when it changed something."""
        address = raw.get("SystemAddress")
        if event in ("FSDJump", "Location", "CarrierJump"):
            if address != self.address:
                self.reset(address, raw.get("StarSystem"))
            else:
                self.name = raw.get("StarSystem") or self.name
            return True
        if address is not None and self.address is not None and address != self.address:
            return False
        if event == "Scan" and raw.get("BodyID") is not None:
            self.scans[int(raw["BodyID"])] = raw
        elif event == "ScanBaryCentre" and raw.get("BodyID") is not None:
            self.barycentres[int(raw["BodyID"])] = raw
        elif event in ("FSSBodySignals", "SAASignalsFound") and raw.get("BodyID") is not None:
            counts = self.body_signals.setdefault(int(raw["BodyID"]), {"bio": 0, "geo": 0})
            for signal in raw.get("Signals") or ():
                kind = str((signal or {}).get("Type") or "")
                if "Biological" in kind:
                    counts["bio"] = max(counts["bio"], int(signal.get("Count") or 0))
                elif "Geological" in kind:
                    counts["geo"] = max(counts["geo"], int(signal.get("Count") or 0))
        elif event == "FSSSignalDiscovered" and raw.get("SignalName"):
            self.signals[str(raw["SignalName"])] = raw
        elif event == "Docked" and raw.get("MarketID") is not None:
            self.docks[raw["MarketID"]] = raw
        elif event == "FSSDiscoveryScan":
            self.honk = raw
        elif event == "FSSAllBodiesFound":
            self.all_bodies = raw
        elif event == "NavBeaconScan":
            self.nav_beacon = raw
        else:
            return False
        self.revision += 1
        return True

    # -- how far the scans have got --------------------------------------
    @property
    def body_count(self):
        """Bodies in the system, as the FSS or nav beacon reported them."""
        for raw, key in ((self.all_bodies, "Count"), (self.honk, "BodyCount"), (self.nav_beacon, "NumBodies")):
            if raw and raw.get(key) is not None:
                return int(raw[key])
        return None

    @property
    def fss_complete(self):
        return bool(self.all_bodies) or bool(self.honk and float(self.honk.get("Progress") or 0) >= 1)

    @property
    def scanned_count(self):
        return len({*self.scans, *self.barycentres})

    def status(self):
        return {"system": self.name, "address": self.address, "body_count": self.body_count,
                "scanned": len([raw for raw in self.scans.values() if raw.get("StarType") or raw.get("PlanetClass")]),
                "fss_complete": self.fss_complete, "ready": self.ready_to_upload()}

    def ready_to_upload(self):
        count = self.body_count
        planets_and_stars = [raw for raw in self.scans.values() if raw.get("StarType") or raw.get("PlanetClass")]
        return bool(self.fss_complete and count and len(planets_and_stars) >= count)

    # -- Raven Colonial bodies (SrvSurvey's updateSysBodies) -------------
    def raven_bodies(self):
        """The system's bodies in Raven Colonial's form, from your scans."""
        bods = []
        for body_id, raw in sorted(self.scans.items()):
            if not (raw.get("StarType") or raw.get("PlanetClass")):
                continue  # belt clusters and rings come from their star
            name = str(raw.get("BodyName") or "")
            dist = float(raw.get("DistanceFromArrivalLS") or 0)
            bod = {"num": body_id, "name": name, "distLS": dist, "parents": _parents(raw), "type": "un",
                   "subType": None, "features": [], "radius": round(float(raw.get("Radius") or 0) / 1000, 3) or -1,
                   "temp": float(raw.get("SurfaceTemperature") or -1),
                   "gravity": round(float(raw.get("SurfaceGravity") or 0) / _G, 6) if raw.get("SurfaceGravity") is not None else -1}
            if raw.get("StarType"):
                bod["type"] = _star_body_type(raw["StarType"])
                bod["subType"] = _star_sub_type(raw["StarType"])
                for index, ring in enumerate(raw.get("Rings") or ()):
                    bods.append({
                        "num": 100_000 + body_id * 100 + index, "name": str(ring.get("Name") or ""),
                        "distLS": float(ring.get("InnerRad") or 0) / _LIGHT_SECOND_M + dist, "parents": [body_id, *_parents(raw)],
                        "type": "ac", "subType": _ring_class(ring.get("RingClass")), "features": [],
                        "radius": -1, "temp": -1, "gravity": -1,
                    })
            else:
                planet_class = str(raw.get("PlanetClass") or "")
                sub_type = planet_class.replace("Sudarsky ", "")
                bod["subType"] = sub_type[:1].upper() + sub_type[1:]
                if "gas giant" in planet_class.casefold():
                    bod["type"] = "gg"
                else:
                    bod["type"] = _PLANET_TYPES.get(planet_class.casefold(), "un")
                if raw.get("TidalLock"):
                    bod["features"].append("tidal")
            if bod["type"] == "un":
                continue
            signals = self.body_signals.get(body_id, {})
            features = bod["features"]
            if int(signals.get("bio") or 0) > 0:
                features.append("bio")
            if int(signals.get("geo") or 0) > 0:
                features.append("geo")
            if raw.get("PlanetClass") and raw.get("Rings"):
                features.append("rings")
            volcanism = str(raw.get("Volcanism") or "")
            if volcanism and volcanism.casefold() not in ("no volcanism", "none"):
                features.append("volcanism")
            if str(raw.get("TerraformState") or "").casefold() in ("terraformable", "terraforming", "terraformed"):
                features.append("terraformable")
            if raw.get("Landable"):
                features.append("landable")
            atmosphere = str(raw.get("AtmosphereType") or raw.get("Atmosphere") or "")
            if raw.get("PlanetClass") and atmosphere and atmosphere.casefold() not in ("none", "no atmosphere"):
                features.append("atmosphere")
            bods.append(bod)
        for body_id, raw in sorted(self.barycentres.items()):
            bods.append({"num": body_id, "name": f"{self.name} barycentre {body_id}", "distLS": 0, "parents": [],
                         "type": "bc", "subType": None, "features": [], "radius": -1, "temp": -1, "gravity": -1})
        bods.sort(key=lambda bod: bod["num"])
        return _belts_in_order(bods)


def _belts_in_order(bods):
    """Put each asteroid belt beside the bodies of its star by distance."""
    belts = [bod for bod in bods if bod["type"] == "ac"]
    for belt in belts:
        prefix = belt["name"][:-7] if len(belt["name"]) > 7 else belt["name"]
        bods.remove(belt)
        index = next((i for i, bod in enumerate(bods)
                      if bod["type"] != "ac" and bod["name"].startswith(prefix) and bod["distLS"] > belt["distLS"]), -1)
        if index == -1:
            index = next((i for i, bod in enumerate(bods)
                          if bod["name"].startswith(prefix) and bod["type"] in ("st", "bh", "ns", "wd")), -1)
            if index >= 0:
                index += 1
        if index < 0:
            index = 1
        bods.insert(index, belt)
    return bods
