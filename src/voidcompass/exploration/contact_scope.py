"""Deep Space Contacts: the non-body signals of the system you are in, from
the journal alone (5.5.2.3 rewrite).

Everything here comes from what the game logs:

* ``FSSSignalDiscovered`` names each signal and gives its ``SignalType``
  (FleetCarrier, StationCoriolis, Installation, NavBeacon, Combat, USS...).
  The game logs the stations and carriers of a system you arrive in a moment
  *before* the ``FSDJump`` for it, so signals for an address you have not
  arrived at yet are held, then taken up when you arrive there.
* ``FSSDiscoveryScan`` (the honk) gives ``NonBodyCount``: every non-body
  signal in the system, carriers included. What the FSS has not resolved is
  that count less what the journal has named.
* A USS lasts ``TimeRemaining`` seconds from its event; once that has passed
  it is gone from the game, and from here.

The game re-logs stations, carriers and conflict zones each time you drop
into or leave supercruise, so a signal is one contact however often it is
logged.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time

# SignalType -> (kind, label, priority). Lower priority sorts first.
_KINDS = {
    "USS": ("uss", "Unidentified signal", 0),
    "Codex": ("phenomena", "Stellar phenomena", 1),
    "Titan": ("titan", "Titan", 1),
    "Generic": ("poi", "Point of interest", 2),
    "TouristBeacon": ("tourist", "Tourist beacon", 3),
    "Megaship": ("megaship", "Megaship", 4),
    "Combat": ("combat", "Conflict zone", 5),
    "ResourceExtraction": ("res", "Resource extraction", 6),
    "StationCoriolis": ("station", "Coriolis starport", 7),
    "StationONeilOrbis": ("station", "Orbis starport", 7),
    "StationONeilCylinder": ("station", "Cylinder starport", 7),
    "StationBernalSphere": ("station", "Ocellus starport", 7),
    "StationAsteroid": ("station", "Asteroid base", 7),
    "StationDodec": ("station", "Dodec starport", 7),
    "StationMegaShip": ("station", "Megaship station", 7),
    "Outpost": ("outpost", "Outpost", 8),
    "Installation": ("installation", "Installation", 9),
    "NavBeacon": ("beacon", "Nav beacon", 10),
    "FleetCarrier": ("carrier", "Fleet carrier", 11),
    "SquadronCarrier": ("carrier", "Squadron carrier", 11),
}
KIND_NAMES = {
    "uss": "USS", "phenomena": "PHENOMENA", "titan": "TITAN", "poi": "POINTS OF INTEREST",
    "tourist": "TOURIST BEACONS", "megaship": "MEGASHIPS", "combat": "CONFLICT ZONES",
    "res": "EXTRACTION SITES", "station": "STATIONS", "outpost": "OUTPOSTS",
    "installation": "INSTALLATIONS", "beacon": "NAV BEACONS", "carrier": "CARRIERS", "signal": "SIGNALS",
}
KIND_NAMES_ONE = {
    "uss": "USS", "phenomena": "PHENOMENON", "titan": "TITAN", "poi": "POINT OF INTEREST",
    "tourist": "TOURIST BEACON", "megaship": "MEGASHIP", "combat": "CONFLICT ZONE",
    "res": "EXTRACTION SITE", "station": "STATION", "outpost": "OUTPOST",
    "installation": "INSTALLATION", "beacon": "NAV BEACON", "carrier": "CARRIER", "signal": "SIGNAL",
}
_ARRIVALS = ("FSDJump", "Location", "CarrierJump")
_PENDING_LIMIT = 400
_CONTACT_LIMIT = 600


def _epoch(timestamp, fallback=None):
    try:
        return datetime.strptime(str(timestamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return fallback


def _clean(value):
    text = str(value or "").strip()
    if text.startswith("$") and text.endswith(";"):
        text = text[1:-1].split(":")[0].replace("_Name", "").replace("_", " ").strip()
    return " ".join(text.split())


def classify(raw):
    """What a FSSSignalDiscovered event is: kind, label, name, details."""
    signal_type = str(raw.get("SignalType") or "")
    kind, label, priority = _KINDS.get(signal_type, ("signal", _clean(signal_type) or "Signal", 12))
    if not signal_type:
        # Older journals: no SignalType. Fall back to what the event says.
        if raw.get("USSType"):
            kind, label, priority = _KINDS["USS"]
        elif raw.get("IsStation"):
            kind, label, priority = "station", "Station", 7
    name = str(raw.get("SignalName_Localised") or "").strip() or _clean(raw.get("SignalName")) or label
    detail = ""
    if kind == "uss":
        detail = str(raw.get("USSType_Localised") or "").strip() or _clean(raw.get("USSType"))
        name = detail or name
    if kind == "carrier":
        # "NAME | CALLSIGN" for squadron carriers, "NAME CALLSIGN" for others.
        detail = name.split("|")[-1].strip() if "|" in name else (name.split()[-1] if " " in name else "")
    return {
        "kind": kind, "label": label, "priority": priority, "name": name, "detail": detail,
        "signal_type": signal_type, "faction": _clean(raw.get("SpawningFaction_Localised") or raw.get("SpawningFaction")),
        "threat": int(raw.get("ThreatLevel") or 0) if kind == "uss" else 0,
    }


class ContactLedger:
    """The current system's contacts, rebuilt from journal events."""

    def __init__(self):
        self.reset(None, "")
        self._pending = {}

    def reset(self, address, name):
        self.address = address
        self.system = name or ""
        self.contacts = {}
        self.non_body_count = None
        self.fss_progress = None
        self.revision = getattr(self, "revision", 0) + 1

    # -- the journal -----------------------------------------------------
    def observe(self, event, raw):
        """Take one raw journal event; True when the scope changed."""
        if not isinstance(raw, dict):
            return False
        if event in _ARRIVALS:
            if event == "CarrierJump" and not raw.get("Docked") and not raw.get("OnFoot"):
                return False  # someone else's carrier jumping, not us
            address = raw.get("SystemAddress")
            if address is None:
                return False
            if address != self.address:
                self.reset(address, raw.get("StarSystem"))
            else:
                self.system = raw.get("StarSystem") or self.system
            for held in self._pending.pop(address, ()):
                self._add(held)
            self._pending.clear()
            self.revision += 1
            return True
        if event == "FSSSignalDiscovered":
            address = raw.get("SystemAddress")
            if address is not None and self.address is not None and address != self.address:
                # The system being arrived at: its arrival event follows.
                held = self._pending.setdefault(address, [])
                if len(held) < _PENDING_LIMIT:
                    held.append(raw)
                return False
            return self._add(raw)
        if event == "FSSDiscoveryScan" and raw.get("SystemAddress") in (None, self.address):
            self.non_body_count = int(raw.get("NonBodyCount") or 0)
            self.fss_progress = float(raw.get("Progress") or 0)
            self.revision += 1
            return True
        return False

    def _add(self, raw):
        row = classify(raw)
        at = _epoch(raw.get("timestamp"), time.time())
        remaining = raw.get("TimeRemaining")
        expires_at = None
        if remaining is not None and at is not None:
            try:
                expires_at = at + float(remaining)
            except (TypeError, ValueError):
                expires_at = None
        if row["kind"] == "uss":
            # Several of the same USS can be up at once: each spawn is its own.
            key = f"uss|{row['name']}|{raw.get('SignalName')}|{int(expires_at or at or 0) // 20}"
        else:
            key = f"{row['signal_type'] or row['kind']}|{str(raw.get('SignalName') or row['name']).casefold()}"
        known = self.contacts.get(key)
        if known is not None:
            known["last_seen"] = at
            return False
        if len(self.contacts) >= _CONTACT_LIMIT:
            return False
        self.contacts[key] = {**row, "key": key, "first_seen": at, "last_seen": at, "expires_at": expires_at}
        self.revision += 1
        return True

    # -- what the scope shows --------------------------------------------
    def model(self, now=None, max_rows=14, carrier_names=6):
        """The overlay's model, or None when there is nothing to show."""
        now = time.time() if now is None else now
        live = [row for row in self.contacts.values() if not row["expires_at"] or row["expires_at"] > now]
        if not live and not self.non_body_count:
            return None
        counts = {}
        for row in live:
            counts[row["kind"]] = counts.get(row["kind"], 0) + 1
        carriers = sorted((row for row in live if row["kind"] == "carrier"), key=lambda row: row["name"].casefold())
        others = sorted((row for row in live if row["kind"] != "carrier"),
                        key=lambda row: (row["priority"], -row["threat"], row["name"].casefold()))
        # Same-named contacts (a dozen alike conflict zones) share a row with
        # a count; each USS keeps its own, with its own timer and threat.
        merged = []
        by_name = {}
        for row in others:
            same = None if row["kind"] == "uss" else by_name.get((row["kind"], row["name"].casefold()))
            if same is not None:
                same["count"] += 1
                continue
            entry = {"key": row["key"], "kind": row["kind"], "label": row["label"], "name": row["name"],
                     "detail": row["detail"], "faction": row["faction"], "threat": row["threat"],
                     "expires_at": row["expires_at"], "count": 1}
            merged.append(entry)
            if row["kind"] != "uss":
                by_name[(row["kind"], row["name"].casefold())] = entry
        rows = merged[:max_rows]
        expected = self.non_body_count
        named = len(live)
        return {
            "system": self.system,
            "expected": expected,
            "named": named,
            "unresolved": max(0, expected - named) if expected is not None else None,
            "honked": expected is not None,
            "fss_progress": self.fss_progress,
            "groups": [{"kind": kind, "count": counts[kind],
                        "name": (KIND_NAMES_ONE if counts[kind] == 1 else KIND_NAMES).get(kind, kind.upper())}
                       for kind in sorted(counts, key=lambda kind: min(row["priority"] for row in live if row["kind"] == kind))],
            "rows": rows, "more": sum(entry["count"] for entry in merged[max_rows:]),
            "carriers": {"count": len(carriers), "names": [row["name"] for row in carriers[:carrier_names]],
                         "more": max(0, len(carriers) - carrier_names)} if carriers else None,
            "threat": max((row["threat"] for row in live), default=0),
            "timed": sum(1 for row in live if row["expires_at"]),
        }

    def names(self):
        """Every contact name heard here (other features look carriers up)."""
        return [row["name"] for row in self.contacts.values()]
