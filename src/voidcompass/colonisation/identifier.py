"""The station identifier (5.5.2.1): put a system's existing stations and
settlements into its Raven Colonial site plan, as you fly it.

After SrvSurvey's Raven updater (FormRavenUpdater): stations found by the
FSS become sites; targeting each installation, orbital port and settlement
in the game sets the body it belongs to; docking fills in its market id and,
for outposts, which outpost it is. It works on the planner's draft, so
nothing reaches Raven Colonial until the plan is saved.
"""

from __future__ import annotations

import time

from voidcompass.colonisation import planner

# FSS signal types that are stations, and the build type they start as.
SIGNAL_BUILD_TYPES = {
    "Installation": "installation?", "Outpost": "outpost?", "StationCoriolis": "no_truss?",
    "StationBernalSphere": "ocellus", "StationONeilOrbis": "orbis?", "StationAsteroid": "asteroid",
    "StationDodec": "dodec?",
}
PHASES = ("scanning", "bodies", "installations", "orbitals", "surface", "done")

_OUTPOST_ECONOMIES = {"$economy_HighTech;": "prometheus", "$economy_Industrial;": "vulcan",
                      "$economy_Military;": "nemesis", "$economy_Service;": "dysnomia"}


def _new_id(prefix="y"):
    _new_id.counter = getattr(_new_id, "counter", 0) + 1
    return f"{prefix}{int(time.time() * 1000)}{_new_id.counter % 1000:03d}"


def _bare(build_type):
    return str(build_type or "").rstrip("?").casefold()


def is_installation(site):
    return _bare(site.get("buildType")) == "installation" or planner.site_type(site.get("buildType"))["buildClass"] == "installation"


def is_orbital_port(site):
    if _bare(site.get("buildType")) in ("outpost", "orbis"):
        return True
    row = planner.site_type(site.get("buildType"))
    return bool(row["orbital"] and row["buildClass"] in ("starport", "outpost"))


def start(state):
    state["identify"] = {"active": True, "phase": "scanning", "message": "", "pending": None, "log": []}
    return state["identify"]


def stop(state):
    state["identify"] = {"active": False}


def _note(ident, text):
    ident["log"] = ([text] + list(ident.get("log") or ()))[:8]


def _insert_site(state, site):
    """A new site goes in just above the cut line, so it counts."""
    sites = state["sites"]
    limit = state.get("idx_calc_limit")
    if limit is None or limit >= len(sites):
        sites.append(site)
        if limit is not None:
            state["idx_calc_limit"] = len(sites)
    else:
        sites.insert(limit, site)
        state["idx_calc_limit"] = limit + 1
    state["dirty"].add(site["id"])


def _touch(state, site):
    state["dirty"].add(site["id"])


def step(state, journal):
    """Work out the next instruction from the journal and the draft."""
    ident = state.get("identify") or {}
    if not ident.get("active"):
        return ident
    if journal.address is None or str(journal.address) != str(state.get("id64")):
        ident.update(phase="scanning", message="Fly to this system to identify its stations.")
        return ident
    if not journal.fss_complete:
        ident.update(phase="scanning", message="Honk the discovery scanner and complete the FSS (or scan the nav beacon).")
        return ident
    total = journal.body_count or 0
    if journal.scanned_count < total:
        ident.update(phase="scanning", message=f"Scan the nav beacon: the journal has {journal.scanned_count} of {total} bodies.")
        return ident
    if len(state.get("bodies") or ()) < total:
        ident.update(phase="bodies", message=f"Raven Colonial knows {len(state.get('bodies') or ())} of {total} bodies: upload your scans first.")
        return ident
    added = _sites_from_signals(state, journal)
    if added:
        _note(ident, f"Added {added} station{'s' if added != 1 else ''} from the FSS.")
    for raw in journal.docks.values():
        apply_docked(state, raw)
    if any(site.get("bodyNum", -1) in (-1, None) and is_installation(site) for site in state["sites"]):
        ident.update(phase="installations", message="In the left panel, filter to Points of Interest (or use the system map) and target each installation below.")
        return ident
    if any(site.get("bodyNum", -1) in (-1, None) and is_orbital_port(site) for site in state["sites"]):
        pending = ident.get("pending")
        pending_site = next((site for site in state["sites"] if site["id"] == pending), None)
        ident.update(phase="orbitals", message=(f"Now target the body {pending_site['name']} orbits." if pending_site else
                                               "Open the system map: target each orbital port below, then the body it orbits."))
        return ident
    if PHASES.index(ident.get("phase") or "scanning") < PHASES.index("surface"):
        ident.update(phase="surface", message="In the left panel, filter to settlements and target each one. Press FINISHED when every settlement is in the list.")
    elif ident.get("phase") == "done":
        ident.update(message="Save the plan to Raven Colonial. Dock at settlements and outposts to identify their types.")
    return ident


def finish(state):
    ident = state.get("identify") or {}
    if ident.get("active"):
        ident.update(phase="done", message="Save the plan to Raven Colonial. Dock at settlements and outposts to identify their types.")
    return ident


def _sites_from_signals(state, journal):
    added = 0
    names = {str(site.get("name") or "").casefold() for site in state["sites"]}
    for raw in journal.signals.values():
        name = str(raw.get("SignalName") or "")
        kind = str(raw.get("SignalType") or "")
        if (not name or name.startswith("$") or raw.get("SignalName_Localised") or kind in ("FleetCarrier", "SquadronCarrier")
                or "construction site" in name.casefold() or name.casefold() in names):
            continue
        if kind not in SIGNAL_BUILD_TYPES and not raw.get("IsStation"):
            continue
        _insert_site(state, {"id": _new_id(), "name": name, "bodyNum": -1, "buildType": SIGNAL_BUILD_TYPES.get(kind, ""),
                             "status": "complete", "buildId": None, "marketId": None})
        names.add(name.casefold())
        added += 1
    return added


def apply_docked(state, raw):
    """Docking at a station of the plan: its market id, and outpost types."""
    site = next((item for item in state["sites"] if item.get("name") == raw.get("StationName")), None)
    if site is None:
        return False
    changed = False
    if not site.get("marketId"):
        site["marketId"] = raw.get("MarketID")
        changed = True
    station_type = str(raw.get("StationType") or "")
    if station_type == "Outpost":
        pads = raw.get("LandingPads") or {}
        build_type = None
        if pads.get("Small") == 3 and pads.get("Medium") == 1:
            build_type = "plutus"
        elif pads.get("Small") == 4 and pads.get("Medium") == 1:
            build_type = "vesta"
        else:
            strong = [item for item in raw.get("StationEconomies") or () if float(item.get("Proportion") or 0) >= 1]
            if len(strong) == 1:
                build_type = _OUTPOST_ECONOMIES.get(raw.get("StationEconomy"))
        if build_type and site.get("buildType") != build_type:
            site["buildType"] = build_type
            changed = True
    elif station_type == "CraterPort" and not site.get("buildType"):
        site["buildType"] = "aphrodite?"
        changed = True
    if site.get("status") != "complete":
        site["status"] = "complete"
        changed = True
    if changed:
        _touch(state, site)
    return changed


def on_destination(state, journal, destination):
    """Status.json's Destination changed while identifying."""
    ident = state.get("identify") or {}
    if not ident.get("active") or not isinstance(destination, dict):
        return False
    if str(destination.get("System")) != str(state.get("id64")):
        return False
    name = str(destination.get("Name") or "").strip()
    body_num = destination.get("Body")
    if not name or name.startswith("$"):
        return False
    system_name = str(state.get("name") or "")
    known_bodies = {body.get("num") for body in state.get("bodies") or ()}
    phase = ident.get("phase")
    by_name = next((site for site in state["sites"] if site.get("name") == name), None)
    if phase == "installations" and not name.startswith(system_name):
        if by_name and by_name.get("bodyNum", -1) in (-1, None):
            if body_num in known_bodies:
                by_name["bodyNum"] = body_num
                _touch(state, by_name)
                _note(ident, f"{name}: body set.")
            else:
                _note(ident, f"{name}: the game gave no known body, set it by hand.")
            return True
    elif phase == "orbitals":
        pending = next((site for site in state["sites"] if site["id"] == ident.get("pending")), None)
        if pending is not None and name.startswith(system_name) and body_num in known_bodies:
            pending["bodyNum"] = body_num
            _touch(state, pending)
            ident["pending"] = None
            _note(ident, f"{pending['name']}: orbits {name}.")
            return True
        if by_name and by_name.get("bodyNum", -1) in (-1, None) and is_orbital_port(by_name):
            ident["pending"] = by_name["id"]
            return True
    elif phase in ("surface", "done") and not name.startswith(system_name) and "construction site" not in name.casefold():
        if any(str(raw.get("SignalName") or "").casefold() == name.casefold() for raw in journal.signals.values()):
            return False  # an orbital signal, not a settlement
        if by_name is None:
            if body_num not in known_bodies:
                return False
            _insert_site(state, {"id": _new_id(), "name": name, "bodyNum": body_num, "buildType": "settlement?",
                                 "status": "complete", "buildId": None, "marketId": None})
            _note(ident, f"Added settlement {name}.")
        else:
            if by_name.get("bodyNum", -1) in (-1, None) and body_num in known_bodies:
                by_name["bodyNum"] = body_num
            by_name["status"] = "complete"
            _touch(state, by_name)
            _note(ident, f"{name}: confirmed.")
        return True
    return False
