"""A ship's build as an EDSY or Coriolis link, pure: the CMDR tab's "EDSY ↗" / "Coriolis ↗" beside each ship with a
Loadout on record (fleet_loadouts' `loadout`, the latest one the game wrote for that ship).

The format is EDMC's (EDMarketConnector, GPL-2.0-or-later: plugins/edsy.py, plugins/coriolis.py and their shared
plugins/common_coreutils.py `shipyard_url_common`, read at its main branch 2026-10-14; nothing copied, the steps
matched). `loadout` reshapes the journal's Loadout as EDMC's `monitor.ship()` does (the one difference: EDMC stamps
the time of the click, this keeps the Loadout's own, so a link is the same at every read); `encode` is EDMC's encoding
(compact JSON with sorted keys, gzip, URL-safe base64, '=' as '%3D') with the gzip header's time set to 0, so one build
always gives the same text. EDSY reads the build from the URL's fragment (after '#': the browser never sends it to a
server), Coriolis from a query parameter (sent to coriolis.io with the page request)."""
import base64
import gzip
import io
import json
import re

EDSY_URL = "https://edsy.org/#/I="
CORIOLIS_URL = "https://coriolis.io/import?data="

# EDMC's order for the core slots (monitor.ship's standard_order): hardpoints first, then these, then the rest by name
STANDARD_ORDER = ("ShipCockpit", "CargoHatch", "Armour", "PowerPlant", "MainEngines", "FrameShiftDrive", "LifeSupport",
                  "PowerDistributor", "Radar", "FuelTank")


def canonical(name):
    """EDMC's canonicalise: lower case, "$int_cargorack_size6_class1_name;" -> "int_cargorack_size6_class1"."""
    if not name:
        return ""
    name = str(name).lower()
    m = re.match(r"\$(.+)_name;", name)
    return m.group(1) if m else name


def _slot_key(slot):
    return ("Hardpoint" not in slot, STANDARD_ORDER.index(slot) if slot in STANDARD_ORDER else len(STANDARD_ORDER),
            "Slot" not in slot, slot)


def loadout(ev):
    """A journal Loadout as EDMC hands it to its EDSY and Coriolis plugins: timestamp, event, Ship and each module's
    Item in canonical form, ShipID, ShipName (not a blank "" or " ") and ShipIdent when set, the modules one per slot
    in EDMC's order, without Health and Value, a laser's AmmoInClip/AmmoInHopper of 1 and 1 dropped (not on a tiny
    hardpoint). The hull's figures (values, masses, fuel, rebuy) are left out, as EDMC leaves them. None without a
    module list."""
    mods = ev.get("Modules")
    if not isinstance(mods, list):
        return None
    by_slot = {}
    for m in mods:
        if not isinstance(m, dict) or not isinstance(m.get("Slot"), str):
            continue
        m = dict(m)
        m["Item"] = canonical(m.get("Item"))
        if ("Hardpoint" in m["Slot"] and not m["Slot"].startswith("TinyHardpoint")
                and m.get("AmmoInClip") == m.get("AmmoInHopper") == 1):          # lasers
            m.pop("AmmoInClip")
            m.pop("AmmoInHopper")
        m.pop("Health", None)
        m.pop("Value", None)
        by_slot[m["Slot"]] = m
    d = {"timestamp": ev.get("timestamp"), "event": "Loadout", "Ship": canonical(ev.get("Ship")), "ShipID": ev.get("ShipID")}
    if ev.get("ShipName") and ev["ShipName"] not in ("", " "):
        d["ShipName"] = ev["ShipName"]
    if ev.get("ShipIdent"):
        d["ShipIdent"] = ev["ShipIdent"]
    d["Modules"] = [by_slot[s] for s in sorted(by_slot, key=_slot_key)]
    return d


def encode(build):
    """EDMC's shipyard_url_common: the build as compact JSON (sorted keys, not ASCII-escaped), gzipped, URL-safe
    base64 with '=' written '%3D'. The gzip header's time is 0 (EDMC's is the moment of the click)."""
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0) as f:
        f.write(json.dumps(build, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return base64.urlsafe_b64encode(out.getvalue()).decode().replace("=", "%3D")


def decode(data):
    """encode's reverse (the tests' check): the build from a link's data."""
    return json.loads(gzip.decompress(base64.urlsafe_b64decode(data.replace("%3D", "="))).decode("utf-8"))


def links(ev):
    """{edsy, coriolis}: the two links that open this Loadout's build, or None (no Loadout, or no module list)."""
    build = loadout(ev) if isinstance(ev, dict) else None
    if not build:
        return None
    data = encode(build)
    return {"edsy": EDSY_URL + data, "coriolis": CORIOLIS_URL + data}
