"""Your mining, all of it, from the journals (5.5.12): what you refined in the
ship and hauled in the Rhino, the rocks you prospected and the best of them,
motherlodes, limpets, and where you mined, month by month.

Ship refining is a tonne per MiningRefined. The Rhino's MiningRefined are
processing pulses (two or three a tonne), so its tonnes come from the SRV
hold's count climbing; a deployment's tonnes are shared out between the
materials by their pulses. Each journal is read once and kept until it
changes, like the Wrapped record.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
import re
import threading

from voidcompass.exploration.travel_history import commander_matches

EVENTS = ("MiningRefined", "ProspectedAsteroid", "AsteroidCracked", "LaunchDrone", "LaunchSRV", "DockSRV",
          "SRVDestroyed", "Cargo", "CargoTransfer", "Location", "FSDJump", "CarrierJump", "SupercruiseExit",
          "ApproachBody", "Touchdown", "SAASignalsFound", "Commander", "LoadGame")
MARKERS = tuple(marker for event in EVENTS for marker in (f'"event":"{event}"', f'"event": "{event}"'))
# A drop this big in the Rhino's hold is cargo moved to the ship, not a wobble.
UNLOAD_T = 5


def _epoch(stamp):
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _key(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").casefold())


_ALIASES = {"opal": "Void Opals", "lowtemperaturediamond": "Low Temperature Diamonds",
            "lowtemperaturediamonds": "Low Temperature Diamonds"}


def material_name(raw_name, localised=None):
    """A display name for a mined material, however the journal spelled it."""
    if localised and not str(localised).startswith("$"):
        return str(localised).strip()[:60]
    text = str(raw_name or "").strip().strip("$;").replace("_name", "")
    key = _key(text)
    if key in _ALIASES:
        return _ALIASES[key]
    from voidcompass.mining.planet_materials import mining_material_catalogue
    for name in mining_material_catalogue():
        if _key(name) == key:
            return name
    return text[:1].upper() + text[1:] if text else ""


def _new():
    return {"first": None, "last": None, "days": set(), "ship": Counter(), "rhino": Counter(), "pulses": 0,
            "deployments": 0, "prospected": 0, "content": Counter(), "best": {}, "motherlodes": Counter(),
            "cracked": 0, "limpets": Counter(), "rings_scanned": 0, "months": {}, "places": {}}


class _Reader:
    """One journal file's mining, read in order."""

    def __init__(self):
        self.out = _new()
        self.system = ""
        self.body = ""
        self.rhino = False
        self.peak = None
        self.pulses = Counter()
        self.tonnes = 0
        self.deploy_place = None
        self.deploy_month = None

    def _when(self, at):
        out = self.out
        out["first"] = at if out["first"] is None else min(out["first"], at)
        out["last"] = at if out["last"] is None else max(out["last"], at)
        moment = datetime.fromtimestamp(at, timezone.utc)
        out["days"].add(moment.strftime("%Y-%m-%d"))
        return moment.strftime("%Y-%m")

    def _add(self, month, mode, place, tonnes, at):
        months = self.out["months"].setdefault(month, {"ship": 0.0, "rhino": 0.0})
        months[mode] += tonnes
        row = self.out["places"].setdefault((mode,) + place, {"tonnes": 0.0, "last": 0})
        row["tonnes"] += tonnes
        row["last"] = max(row["last"], at)

    def _close_deployment(self, at):
        if not self.rhino:
            return
        self.rhino = False
        tonnes, pulses = self.tonnes, self.pulses
        if tonnes > 0:
            self.out["deployments"] += 1
            total = sum(pulses.values())
            for name, share in (pulses.items() if total else (("Unknown", 1),)):
                self.out["rhino"][name] += tonnes * share / (total or 1)
            self._add(self.deploy_month or self._when(at), "rhino", self.deploy_place or (self.system, self.body), tonnes, at)
        self.peak, self.pulses, self.tonnes = None, Counter(), 0

    def feed(self, raw):
        event = raw.get("event")
        at = _epoch(raw.get("timestamp"))
        if at is None:
            return
        if event in ("Location", "FSDJump", "CarrierJump"):
            self.system = str(raw.get("StarSystem") or self.system)
            self.body = str(raw.get("Body") or "") if event == "Location" else ""
        elif event in ("SupercruiseExit", "ApproachBody", "Touchdown"):
            self.body = str(raw.get("Body") or self.body)
        elif event == "LaunchSRV":
            self._close_deployment(at)
            if "rhino" in str(raw.get("SRVType") or raw.get("SRVType_Localised") or "").casefold():
                self.rhino = True
                self.deploy_place = (self.system, self.body)
                self.deploy_month = self._when(at)
        elif event in ("DockSRV", "SRVDestroyed"):
            self._close_deployment(at)
        elif event == "Cargo" and self.rhino and str(raw.get("Vessel") or "").casefold() == "srv":
            try:
                count = int(raw.get("Count") or 0)
            except (TypeError, ValueError):
                return
            if self.peak is None or self.peak - count >= UNLOAD_T:
                self.peak = count
            elif count > self.peak:
                self.tonnes += count - self.peak
                self.peak = count
        elif event == "CargoTransfer" and self.rhino:
            self.peak = None
        elif event == "MiningRefined":
            name = material_name(raw.get("Type"), raw.get("Type_Localised"))
            month = self._when(at)
            if self.rhino:
                self.pulses[name] += 1
                self.out["pulses"] += 1
            else:
                self.out["ship"][name] += 1
                self._add(month, "ship", (self.system, self.body), 1.0, at)
        elif event == "ProspectedAsteroid":
            self._when(at)
            out = self.out
            out["prospected"] += 1
            content = str(raw.get("Content_Localised") or raw.get("Content") or "")
            level = next((word for word in ("High", "Medium", "Low") if word.casefold() in content.casefold()), "")
            if level:
                out["content"][level] += 1
            for row in raw.get("Materials") or ():
                if not isinstance(row, dict):
                    continue
                name = material_name(row.get("Name"), row.get("Name_Localised"))
                try:
                    share = float(row.get("Proportion") or 0)
                except (TypeError, ValueError):
                    continue
                if name and share > out["best"].get(name, 0):
                    out["best"][name] = share
            if raw.get("MotherlodeMaterial"):
                out["motherlodes"][material_name(raw.get("MotherlodeMaterial"), raw.get("MotherlodeMaterial_Localised"))] += 1
        elif event == "AsteroidCracked":
            self.out["cracked"] += 1
        elif event == "LaunchDrone":
            kind = str(raw.get("Type") or "")
            if kind:
                self.out["limpets"][kind] += 1
        elif event == "SAASignalsFound" and "ring" in str(raw.get("BodyName") or "").casefold():
            self.out["rings_scanned"] += 1

    def finish(self):
        self._close_deployment(self.out["last"] or 0)
        return self.out


def read_journal(path, commander=None, fid=None):
    reader = _Reader()
    active = not bool(commander or fid)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not any(marker in line for marker in MARKERS):
                    continue
                try:
                    raw = json.loads(line)
                except ValueError:
                    continue
                event = raw.get("event")
                if event in ("Commander", "LoadGame"):
                    active = commander_matches(raw, commander, fid)
                    if event == "LoadGame":
                        reader._close_deployment(_epoch(raw.get("timestamp")) or 0)
                    continue
                if active:
                    reader.feed(raw)
    except OSError:
        pass
    return reader.finish()


def merge(parts):
    """All the files' mining as one summary, ready for the page."""
    total = _new()
    for part in parts:
        if part["first"] is not None:
            total["first"] = part["first"] if total["first"] is None else min(total["first"], part["first"])
            total["last"] = part["last"] if total["last"] is None else max(total["last"], part["last"])
        total["days"] |= part["days"]
        for key in ("ship", "rhino", "content", "motherlodes", "limpets"):
            total[key].update(part[key])
        for key in ("pulses", "deployments", "prospected", "cracked", "rings_scanned"):
            total[key] += part[key]
        for name, share in part["best"].items():
            total["best"][name] = max(share, total["best"].get(name, 0))
        for month, row in part["months"].items():
            held = total["months"].setdefault(month, {"ship": 0.0, "rhino": 0.0})
            held["ship"] += row["ship"]
            held["rhino"] += row["rhino"]
        for place, row in part["places"].items():
            held = total["places"].setdefault(place, {"tonnes": 0.0, "last": 0})
            held["tonnes"] += row["tonnes"]
            held["last"] = max(held["last"], row["last"])
    names = set(total["ship"]) | set(total["rhino"])
    materials = sorted(({"name": name, "ship": round(total["ship"][name]), "rhino": round(total["rhino"][name])}
                        for name in names), key=lambda row: (-(row["ship"] + row["rhino"]), row["name"]))
    return {
        "first": total["first"], "last": total["last"], "days": len(total["days"]),
        "ship_t": round(sum(total["ship"].values())), "rhino_t": round(sum(total["rhino"].values())),
        "pulses": total["pulses"], "deployments": total["deployments"],
        "materials": [row for row in materials if row["ship"] or row["rhino"]][:40],
        "months": [{"month": month, "ship": round(row["ship"]), "rhino": round(row["rhino"])}
                   for month, row in sorted(total["months"].items())],
        "places": [{"mode": place[0], "system": place[1], "body": place[2], "tonnes": round(row["tonnes"]), "last": row["last"]}
                   for place, row in sorted(total["places"].items(), key=lambda item: -item[1]["tonnes"])[:12]],
        "prospected": total["prospected"], "content": dict(total["content"]),
        "best": [{"name": name, "percent": round(share, 1)}
                 for name, share in sorted(total["best"].items(), key=lambda item: -item[1])[:16]],
        "motherlodes": [{"name": name, "count": count} for name, count in total["motherlodes"].most_common()],
        "cracked": total["cracked"], "limpets": dict(total["limpets"]), "rings_scanned": total["rings_scanned"],
    }


class MiningRecord:
    """Every journal's mining for one commander, kept per file until it changes."""

    def __init__(self):
        self.lock = threading.Lock()
        self._files = {}

    def summary(self, journal_path, commander=None, fid=None):
        if not journal_path or not os.path.isdir(journal_path):
            return merge([])
        parts = []
        for name in os.listdir(journal_path):
            if not (name.startswith("Journal.") and name.endswith(".log")):
                continue
            path = os.path.join(journal_path, name)
            try:
                signature = (os.path.getsize(path), int(os.path.getmtime(path)), commander or "", fid or "")
            except OSError:
                continue
            with self.lock:
                held = self._files.get(name)
            if held is None or held[0] != signature:
                held = (signature, read_journal(path, commander, fid))
                with self.lock:
                    self._files[name] = held
            parts.append(held[1])
        return merge(parts)
