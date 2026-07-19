"""Shared state and helpers for native companion features.

This module intentionally contains no Tk code so journal handling, persistence,
and regression tests can exercise the same logic used by the dashboard.
"""

from __future__ import annotations

import base64
import gzip
import io
import json
import math
import os

from version import APP_VERSION
from persistence_queue import persistence_queue


DEFAULT_STATE = {
    "loadout": None,
    "stored_ships": None,
    "missions": {},
    "faction_kills": {},
    "powerplay": None,
    "pp_system": None,
    "galaxy_system": None,
    "galaxy_updated": None,
    "galaxy_system_updated": None,
    "galaxy_source": None,
    "galaxy_system_source": None,
    "controlling_faction": None,
    "factions": [],
    "conflicts": [],
    "watched_factions": [],
    "faction_watch_snapshots": {},
    "community_goals": {},
    "squadron": None,
    "squadron_application": None,
    "squadron_invitation": None,
    "squadron_activity": [],
    "squadron_trophies": [],
    "squadron_bookmarks": [],
    "statistics": None,
    "statistics_updated": None,
    "unsold_exploration_cr": 0,
    "unsold_bio_cr": 0,
    "unsold_bio_bonus_potential_cr": 0,
    "unsold_scan_keys": [],
}

SQUADRON_ACTIVITY_LIMIT = 60
SQUADRON_ITEM_LIMIT = 30

MISSION_KINDS = (
    ("delivery", "delivery"), ("collect", "collect"), ("salvage", "salvage"),
    ("mining", "mining"), ("courier", "courier"), ("passenger", "passenger"),
    ("massacre", "combat"), ("assassin", "combat"), ("hack", "combat"),
    ("piracy", "piracy"), ("rescue", "rescue"), ("donation", "donation"),
)

FSD_INJECTION_RECIPES = {
    "basic": {"carbon": 1, "vanadium": 1, "germanium": 1},
    "standard": {"carbon": 1, "vanadium": 1, "germanium": 1, "cadmium": 1, "niobium": 1},
    "premium": {"carbon": 1, "germanium": 1, "niobium": 1, "arsenic": 1,
                "polonium": 1, "yttrium": 1},
}
FSD_INJECTION_BOOST = {"basic": 25, "standard": 50, "premium": 100}

SHIP_CHANGE_EVENTS = {"ShipyardBuy", "ShipyardNew", "ShipyardSwap"}
SHIP_COMPANION_EVENTS = SHIP_CHANGE_EVENTS | {"SetUserShipName", "ShipyardSell"}
SHIP_DETAIL_FIELDS = {
    "ModulesValue": "modules_value",
    "HullHealth": "hull_health",
    "MaxJumpRange": "max_jump_range",
    "Rebuy": "rebuy",
    "CargoCapacity": "cargo_capacity",
    "FuelLevel": "fuel_level",
    "FuelCapacity": "fuel_capacity",
    "GameMode": "game_mode",
    "Group": "group",
}
SHIP_RESET_FIELDS = {
    "ship", "ship_localised", "ship_id", "ship_name", "ship_ident",
    *SHIP_DETAIL_FIELDS.values(),
}


def fresh_state():
    return json.loads(json.dumps(DEFAULT_STATE))


def load_state(path):
    state = fresh_state()
    if not path or not os.path.exists(path):
        return state
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            state.update(loaded)
            # Older builds stored a single biology estimate that sometimes
            # included a presumed 5x first-footfall bonus. Its exact split
            # cannot be reconstructed, so migrate it to a conservative range.
            if ("unsold_bio_bonus_potential_cr" not in loaded
                    and int(loaded.get("unsold_bio_cr") or 0) > 0):
                legacy = int(loaded.get("unsold_bio_cr") or 0)
                base = (legacy + 4) // 5
                state["unsold_bio_cr"] = base
                state["unsold_bio_bonus_potential_cr"] = legacy - base
    except Exception:
        pass
    return state


def save_state(path, state):
    if not path:
        return
    try:
        persistence_queue().submit_json(path, state, indent=2, delay_s=0.75)
    except Exception:
        pass


def record_squadron_activity(state, event, squadron_name=None, timestamp=None,
                              detail=None, limit=SQUADRON_ACTIVITY_LIMIT):
    """Record one bounded, de-duplicated squadron journal action."""
    entry = {
        "event": str(event or "SquadronEvent"),
        "squadron": str(squadron_name or "").strip() or None,
        "timestamp": timestamp,
        "detail": str(detail or "").strip() or None,
    }
    key = (entry["event"], entry["squadron"], entry["timestamp"], entry["detail"])
    activity = [row for row in state.get("squadron_activity") or [] if isinstance(row, dict)]
    if any((row.get("event"), row.get("squadron"), row.get("timestamp"), row.get("detail")) == key
           for row in activity):
        return False
    activity.insert(0, entry)
    state["squadron_activity"] = activity[:max(1, int(limit or SQUADRON_ACTIVITY_LIMIT))]
    return True


def record_squadron_item(state, key, event, squadron_name=None, timestamp=None,
                         detail=None, limit=SQUADRON_ITEM_LIMIT):
    """Record a bounded trophy/bookmark fact without inventing unavailable details."""
    entry = {
        "event": str(event or "SquadronEvent"),
        "squadron": str(squadron_name or "").strip() or None,
        "timestamp": timestamp,
        "detail": str(detail or "").strip() or None,
    }
    rows = [row for row in state.get(key) or [] if isinstance(row, dict)]
    identity = (entry["event"], entry["squadron"], entry["timestamp"])
    if not any((row.get("event"), row.get("squadron"), row.get("timestamp")) == identity
               for row in rows):
        rows.insert(0, entry)
    state[key] = rows[:max(1, int(limit or SQUADRON_ITEM_LIMIT))]
    return entry


def toggle_faction_watch(state, faction_name):
    """Toggle a faction watch and return its new watched state."""
    name = str(faction_name or "").strip()
    if not name:
        return False
    watched = {str(value) for value in state.get("watched_factions") or [] if value}
    if name in watched:
        watched.remove(name)
        snapshots = state.setdefault("faction_watch_snapshots", {})
        suffix = f"\n{name}"
        for key in [key for key in snapshots if key.endswith(suffix)]:
            snapshots.pop(key, None)
        enabled = False
    else:
        watched.add(name)
        enabled = True
    state["watched_factions"] = sorted(watched, key=str.casefold)
    return enabled


def update_faction_watch_snapshots(state, system_name, factions, controlling_faction,
                                   min_delta=0.01, notify=True):
    """Update persistent watched-faction baselines and return concise changes.

    Each returned item is ``(faction_name, detail_text)``. A faction generates at
    most one item per journal update so influence, state, and control changes do
    not turn into a burst of separate alerts.
    """
    system = str(system_name or "").strip()
    watched = {str(value) for value in state.get("watched_factions") or [] if value}
    snapshots = state.setdefault("faction_watch_snapshots", {})
    if not system or not watched:
        return []
    changes = []
    for faction in factions or []:
        name = str(faction.get("name") or "").strip()
        if not name or name not in watched:
            continue
        key = f"{system}\n{name}"
        current = {
            "influence": float(faction.get("influence") or 0),
            "active_states": sorted(str(value) for value in faction.get("active_states") or []),
            "controls": name == controlling_faction,
        }
        previous = snapshots.get(key)
        details = []
        if notify and isinstance(previous, dict):
            delta = current["influence"] - float(previous.get("influence") or 0)
            if abs(delta) >= float(min_delta):
                details.append(f"influence {delta * 100:+.1f}%")
            old_states = set(previous.get("active_states") or [])
            new_states = set(current["active_states"])
            if old_states != new_states:
                entered = sorted(new_states - old_states)
                ended = sorted(old_states - new_states)
                if entered:
                    details.append("state " + ", ".join(entered))
                if ended:
                    details.append("ended " + ", ".join(ended))
            if bool(previous.get("controls")) != current["controls"]:
                details.append("now controls system" if current["controls"] else "lost system control")
        snapshots[key] = current
        if details:
            changes.append((name, " · ".join(details)))
    return changes


def edsy_url(loadout):
    compact = json.dumps(loadout, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="w") as archive:
        archive.write(compact)
    encoded = base64.urlsafe_b64encode(buf.getvalue()).decode().replace("=", "%3D")
    return "https://edsy.org/#/I=" + encoded


def slef(loadout):
    return json.dumps([{
        "header": {"appName": "VoidCompass", "appVersion": APP_VERSION},
        "data": loadout,
    }], ensure_ascii=False)


def fsd_injections(raw_counts):
    return {
        tier: min(int(raw_counts.get(symbol, 0)) // needed
                  for symbol, needed in recipe.items())
        for tier, recipe in FSD_INJECTION_RECIPES.items()
    }


def surface_distance_m(lat1, lon1, lat2, lon2, radius_m):
    if None in (lat1, lon1, lat2, lon2) or not radius_m:
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(a))


def sample_clearance(points, position, colony_m):
    if not points or not position:
        return None
    distances = []
    for point in points:
        if point.get("body") != position.get("body"):
            continue
        distance = surface_distance_m(
            point.get("lat"), point.get("lon"), position.get("lat"),
            position.get("lon"), position.get("radius_m"),
        )
        if distance is not None:
            distances.append(distance)
    if not distances:
        return None
    minimum = min(distances)
    return {
        "distances_m": [round(value) for value in distances],
        "min_distance_m": round(minimum),
        "clear": minimum >= colony_m if colony_m else None,
    }


def mission_kind(name):
    lowered = (name or "").lower()
    return next((kind for needle, kind in MISSION_KINDS if needle in lowered), "other")


def mission_from_event(event):
    mission_id = event.get("MissionID")
    if mission_id is None:
        return None
    internal_name = event.get("Name") or ""
    commodity = (event.get("Commodity") or "").strip("$;")
    commodity = commodity.removesuffix("_Name").removesuffix("_name").lower()
    return {
        "id": mission_id,
        "name": event.get("LocalisedName") or event.get("Name_Localised") or internal_name,
        "internal_name": internal_name,
        "kind": mission_kind(internal_name),
        "faction": event.get("Faction"),
        "commodity": event.get("Commodity_Localised") or commodity or None,
        "commodity_symbol": commodity or None,
        "count": event.get("Count"),
        "destination_system": event.get("DestinationSystem"),
        "destination_station": event.get("DestinationStation"),
        "destination_settlement": event.get("DestinationSettlement"),
        "target": event.get("Target") or event.get("Target_Localised"),
        "target_type": event.get("TargetType") or event.get("TargetType_Localised"),
        "target_faction": event.get("TargetFaction"),
        "kill_count": event.get("KillCount"),
        "reward": event.get("Reward") or 0,
        "wing": bool(event.get("Wing")),
        "illegal": bool(event.get("Illegal")) or any(
            marker in internal_name.casefold()
            for marker in ("illegal", "smuggl", "covert")
        ),
        "passenger_count": event.get("PassengerCount"),
        "passenger_vips": bool(event.get("PassengerVIPs")),
        "passenger_wanted": bool(event.get("PassengerWanted")),
        "passenger_type": event.get("PassengerType"),
        "expiry": event.get("Expiry"),
        "accepted": event.get("timestamp"),
    }


def massacre_stacks(state):
    stacks = {}
    for mission in (state.get("missions") or {}).values():
        if (mission.get("kind") != "combat" or not mission.get("target_faction")
                or not mission.get("kill_count")
                or "massacre" not in (mission.get("internal_name") or "").lower()):
            continue
        target = mission["target_faction"]
        row = stacks.setdefault(target, {"missions": 0, "reward": 0, "by_giver": {}})
        row["missions"] += 1
        row["reward"] += int(mission.get("reward") or 0)
        giver = mission.get("faction") or "?"
        row["by_giver"][giver] = row["by_giver"].get(giver, 0) + int(mission["kill_count"])
    output = []
    kills = state.get("faction_kills") or {}
    for target, row in stacks.items():
        needed = max(row["by_giver"].values())
        done = int(kills.get(target, 0))
        output.append({
            "faction": target, "missions": row["missions"], "givers": len(row["by_giver"]),
            "reward": row["reward"], "kills_needed": needed,
            "kills_done": min(done, needed), "complete": done >= needed,
        })
    return sorted(output, key=lambda row: -row["reward"])


def normalise_stored_ship(record):
    return {
        "type": record.get("ShipType_Localised") or record.get("ShipType") or "Unknown ship",
        "type_symbol": record.get("ShipType"), "ship_id": record.get("ShipID"),
        "name": record.get("Name"), "value": record.get("Value"),
        "hot": bool(record.get("Hot")), "system": record.get("StarSystem"),
        "transfer_cr": record.get("TransferPrice"), "transfer_s": record.get("TransferTime"),
        "in_transit": bool(record.get("InTransit")),
    }


def _same_ship_id(left, right):
    if left is None or right is None:
        return False
    return str(left) == str(right)


def _same_ship_symbol(left, right):
    if not left or not right:
        return False
    return str(left).casefold() == str(right).casefold()


def update_active_ship(current, event, raw):
    """Reduce one journal ship event into the active mothership identity."""
    ship = dict(current or {})
    raw = raw if isinstance(raw, dict) else {}
    before = dict(ship)

    if event == "SetUserShipName":
        # Elite also emits this event for SRVs. Only the active ship ID may
        # update the mothership shown throughout the Commander Profile.
        if not _same_ship_id(ship.get("ship_id"), raw.get("ShipID")):
            return ship, False
        if "UserShipName" in raw:
            ship["ship_name"] = raw.get("UserShipName")
        if "UserShipId" in raw:
            ship["ship_ident"] = raw.get("UserShipId")
        return ship, ship != before

    if event not in ("Loadout", "LoadGame") and event not in SHIP_CHANGE_EVENTS:
        return ship, False

    if event in ("ShipyardBuy", "ShipyardSwap"):
        incoming_type = raw.get("ShipType")
        incoming_localised = raw.get("ShipType_Localised")
        incoming_id = raw.get("ShipID") if event == "ShipyardSwap" else None
        identity_changed = True
    elif event == "ShipyardNew":
        incoming_type = raw.get("ShipType")
        incoming_localised = raw.get("ShipType_Localised")
        incoming_id = raw.get("NewShipID")
        identity_changed = True
    else:
        incoming_type = raw.get("Ship")
        incoming_localised = raw.get("Ship_Localised")
        incoming_id = raw.get("ShipID")
        current_id = ship.get("ship_id")
        current_type = ship.get("ship")
        identity_changed = bool(
            (incoming_id is not None and current_id is not None
             and not _same_ship_id(incoming_id, current_id))
            or (incoming_type and current_type
                and not _same_ship_symbol(incoming_type, current_type))
        )

    if identity_changed:
        for key in SHIP_RESET_FIELDS:
            ship.pop(key, None)

    if incoming_type is not None:
        ship["ship"] = incoming_type
    if incoming_localised is not None:
        ship["ship_localised"] = incoming_localised
    if incoming_id is not None:
        ship["ship_id"] = incoming_id

    if event in ("Loadout", "LoadGame"):
        # Empty names and identifiers are real values for newly purchased
        # ships; never retain the outgoing vessel's identity in their place.
        if "ShipName" in raw:
            ship["ship_name"] = raw.get("ShipName")
        if "ShipIdent" in raw:
            ship["ship_ident"] = raw.get("ShipIdent")
        for source, target in SHIP_DETAIL_FIELDS.items():
            if source in raw:
                ship[target] = raw.get(source)

    return ship, ship != before


def _remove_stored_ship(rows, ship_id):
    if ship_id is None:
        return list(rows or []), False
    filtered = [row for row in rows or []
                if not _same_ship_id((row or {}).get("ship_id"), ship_id)]
    return filtered, len(filtered) != len(rows or [])


def update_ship_companion_state(state, event, raw):
    """Keep the cached loadout and stored fleet aligned with shipyard events."""
    raw = raw if isinstance(raw, dict) else {}
    changed = False

    if event in SHIP_CHANGE_EVENTS and state.get("loadout") is not None:
        state["loadout"] = None
        changed = True
    elif event == "SetUserShipName" and isinstance(state.get("loadout"), dict):
        loadout = state["loadout"]
        if _same_ship_id(loadout.get("ShipID"), raw.get("ShipID")):
            if "UserShipName" in raw and loadout.get("ShipName") != raw.get("UserShipName"):
                loadout["ShipName"] = raw.get("UserShipName")
                changed = True
            if "UserShipId" in raw and loadout.get("ShipIdent") != raw.get("UserShipId"):
                loadout["ShipIdent"] = raw.get("UserShipId")
                changed = True

    fleet = state.get("stored_ships")
    if not isinstance(fleet, dict):
        return changed

    fleet_changed = False
    here = list(fleet.get("here") or [])
    remote = list(fleet.get("remote") or [])
    target_id = {
        "ShipyardNew": raw.get("NewShipID"),
        "ShipyardSwap": raw.get("ShipID"),
        "ShipyardSell": raw.get("SellShipID") or raw.get("ShipID"),
    }.get(event)
    if target_id is not None:
        here, here_changed = _remove_stored_ship(here, target_id)
        remote, remote_changed = _remove_stored_ship(remote, target_id)
        fleet_changed = fleet_changed or here_changed or remote_changed

    if event in ("ShipyardBuy", "ShipyardSwap") and raw.get("StoreShipID") is not None:
        stored_id = raw.get("StoreShipID")
        here, _ = _remove_stored_ship(here, stored_id)
        remote, _ = _remove_stored_ship(remote, stored_id)
        here.append(normalise_stored_ship({
            "ShipID": stored_id,
            "ShipType": raw.get("StoreOldShip"),
            "StarSystem": raw.get("StarSystem"),
        }))
        fleet_changed = True

    if fleet_changed:
        fleet["here"] = here
        fleet["remote"] = remote
        fleet["updated"] = raw.get("timestamp") or fleet.get("updated")
    return changed or fleet_changed
