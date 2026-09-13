"""Focused operational state for the adaptive exploration command deck.

The journal is chatty, so this module keeps only the live context consumed by
the current dashboard: activity mode, ground operations, missions and Fleet
Carrier route state. It deliberately has no UI or persistence of its own.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
import time


ACTIVITY_EVENTS = {
    "exploration": {
        "CodexEntry", "FSDJump", "FSSAllBodiesFound", "FSSBodySignals",
        "FSSDiscoveryScan", "FSSSignalDiscovered", "NavBeaconScan", "Scan",
        "ScanOrganic", "SAAScanComplete", "StartJump",
    },
    "mining": {
        "AsteroidCracked", "MiningRefined", "ProspectedAsteroid",
    },
    "ground": {
        "ApproachSettlement", "Backpack", "BackpackChange", "BookDropship",
        "BookTaxi", "CollectItems", "Disembark", "DropItems", "ShipLocker",
        "SuitLoadout",
    },
    "carrier": {
        "CarrierBankTransfer", "CarrierBuy", "CarrierCrewServices",
        "CarrierFinance", "CarrierJump", "CarrierJumpCancelled",
        "CarrierJumpRequest", "CarrierModulePack", "CarrierNameChange",
        "CarrierStats", "CarrierTradeOrder", "CarrierShipPack",
    },
    "station": {
        "Docked", "SellExplorationData", "MultiSellExplorationData",
        "SellOrganicData", "SellOrganicDataDirect",
    },
}


def _activity_for_event(event):
    for mode, events in ACTIVITY_EVENTS.items():
        if event in events:
            return mode
    return None


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clean(value, fallback=""):
    text = str(value or "").strip().strip("$;")
    text = re.sub(r"_(name|name_localised)$", "", text, flags=re.I)
    return text.replace("_", " ").strip() or fallback


def _event_name(row, fallback="Item"):
    if not isinstance(row, dict):
        return fallback
    return _clean(
        row.get("Name_Localised") or row.get("Type_Localised")
        or row.get("Name") or row.get("Type"),
        fallback,
    )


def fresh_runtime_state():
    return {
        "activity": {
            "mode": "general", "since": time.time(), "last_event": None,
            "confidence": 0.4,
        },
        "ground": {
            "suit": None,
            "loadout": None,
            "suit_mods": [],
            "weapons": [],
            "backpack": {
                "items": {}, "components": {}, "consumables": {}, "data": {},
            },
            "settlement": None,
            "on_foot": False,
            "in_taxi": False,
            "in_multicrew": False,
            "crew_captain": None,
            "vehicle_control": "Mothership",
            "oxygen_percent": None,
            "health_percent": None,
            "temperature_k": None,
            "gravity_g": None,
            "selected_weapon": None,
            "items_collected": 0,
            "items_dropped": 0,
            "stolen_items": 0,
        },
        "missions": {
            "accepted": 0,
            "completed": 0,
            "failed": 0,
            "abandoned": 0,
            "rewards_cr": 0,
        },
    }


def _inventory_bucket(rows):
    output = {}
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        name = _event_name(row)
        output[name] = output.get(name, 0) + _integer(row.get("Count"), 1)
    return output


def observe_event(state, event, raw=None, current_system=None, historical=False):
    """Fold one relevant journal event into the current operational state."""
    del current_system
    if not isinstance(state, dict):
        return False
    raw = raw if isinstance(raw, dict) else {}
    event = str(event or "")
    if event == "LoadGame" and not historical:
        state.clear()
        state.update(fresh_runtime_state())

    defaults = fresh_runtime_state()
    ground = state.setdefault("ground", defaults["ground"])
    missions = state.setdefault("missions", defaults["missions"])
    activity = state.setdefault("activity", defaults["activity"])
    changed = False

    if not historical:
        mode = _activity_for_event(event)
        if event in ("LoadGame", "Undocked"):
            mode = "general"
        elif event == "Embark" and activity.get("mode") == "ground":
            mode = "general"
        if mode:
            now = time.time()
            if mode != activity.get("mode"):
                activity["since"] = now
            activity.update({
                "mode": mode,
                "last_event": event,
                "last_event_at": now,
                "confidence": 1.0,
            })
            changed = True

        if event == "MissionAccepted":
            missions["accepted"] = int(missions.get("accepted") or 0) + 1
            changed = True
        elif event == "MissionCompleted":
            missions["completed"] = int(missions.get("completed") or 0) + 1
            missions["rewards_cr"] = (
                int(missions.get("rewards_cr") or 0) + _integer(raw.get("Reward"))
            )
            changed = True
        elif event == "MissionFailed":
            missions["failed"] = int(missions.get("failed") or 0) + 1
            changed = True
        elif event == "MissionAbandoned":
            missions["abandoned"] = int(missions.get("abandoned") or 0) + 1
            changed = True

    if event == "SuitLoadout":
        ground["suit"] = _clean(
            raw.get("SuitName_Localised") or raw.get("SuitName"), "Suit",
        )
        ground["loadout"] = raw.get("LoadoutName")
        ground["suit_mods"] = [_clean(value) for value in raw.get("SuitMods") or []]
        ground["weapons"] = [
            {
                "name": _clean(
                    row.get("ModuleName_Localised") or row.get("ModuleName"),
                    "Weapon",
                ),
                "class": row.get("Class"),
                "mods": [_clean(value) for value in row.get("WeaponMods") or []],
            }
            for row in raw.get("Modules") or [] if isinstance(row, dict)
        ]
        changed = True
    elif event in ("Backpack", "ShipLocker"):
        ground["backpack"] = {
            "items": _inventory_bucket(raw.get("Items")),
            "components": _inventory_bucket(raw.get("Components")),
            "consumables": _inventory_bucket(raw.get("Consumables")),
            "data": _inventory_bucket(raw.get("Data")),
        }
        changed = True
    elif event == "BackpackChange":
        bucket = ground.setdefault("backpack", {}).setdefault("items", {})
        for row in raw.get("Added") or ():
            name = _event_name(row)
            bucket[name] = int(bucket.get(name) or 0) + _integer(row.get("Count"), 1)
        for row in raw.get("Removed") or ():
            name = _event_name(row)
            bucket[name] = max(
                0, int(bucket.get(name) or 0) - _integer(row.get("Count"), 1),
            )
        changed = True
    elif event == "ApproachSettlement":
        ground["settlement"] = {
            "name": raw.get("Name"),
            "system": raw.get("StarSystem"),
            "body": raw.get("BodyName") or raw.get("Body"),
            "market_id": raw.get("MarketID"),
        }
        changed = True
    elif event == "Disembark":
        ground["on_foot"] = True
        ground["in_taxi"] = bool(raw.get("Taxi"))
        ground["in_multicrew"] = bool(raw.get("Multicrew"))
        ground["vehicle_control"] = "On foot"
        changed = True
    elif event == "Embark":
        ground["on_foot"] = False
        ground["in_taxi"] = bool(raw.get("Taxi"))
        ground["in_multicrew"] = bool(raw.get("Multicrew"))
        changed = True
    elif event in ("BookTaxi", "BookDropship"):
        ground["in_taxi"] = True
        changed = True
    elif event == "VehicleSwitch":
        ground["vehicle_control"] = _clean(raw.get("To"), "Mothership")
        ground["on_foot"] = False
        changed = True
    elif event == "JoinACrew":
        ground["in_multicrew"] = True
        ground["crew_captain"] = raw.get("Captain")
        changed = True
    elif event == "QuitACrew":
        ground["in_multicrew"] = False
        ground["crew_captain"] = None
        changed = True
    elif event in ("CollectItems", "DropItems") and not historical:
        count = max(1, _integer(raw.get("Count"), 1))
        key = "items_collected" if event == "CollectItems" else "items_dropped"
        ground[key] = int(ground.get(key) or 0) + count
        if raw.get("Stolen"):
            delta = count if event == "CollectItems" else -count
            ground["stolen_items"] = max(
                0, int(ground.get("stolen_items") or 0) + delta,
            )
        changed = True
    return changed


def observe_status(state, data):
    """Capture frequently-changing suit facts without triggering UI work."""
    if not isinstance(state, dict) or not isinstance(data, dict):
        return False
    ground = state.setdefault("ground", fresh_runtime_state()["ground"])
    flags2 = data.get("Flags2")
    if isinstance(flags2, int):
        ground["on_foot"] = bool(flags2 & 0x0001)
        ground["in_taxi"] = bool(flags2 & 0x0002)
        ground["in_multicrew"] = bool(flags2 & 0x0004)
    for source, target in (("Oxygen", "oxygen_percent"), ("Health", "health_percent")):
        if data.get(source) is not None:
            ground[target] = round(_number(data.get(source)) * 100)
    if data.get("Temperature") is not None:
        ground["temperature_k"] = round(_number(data.get("Temperature")), 1)
    if data.get("Gravity") is not None:
        ground["gravity_g"] = round(_number(data.get("Gravity")), 2)
    if data.get("SelectedWeapon") is not None:
        weapon = data.get("SelectedWeapon")
        ground["selected_weapon"] = _clean(
            (weapon.get("Name_Localised") or weapon.get("Name"))
            if isinstance(weapon, dict) else weapon,
            "Weapon",
        )
    return True


def _parse_expiry(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def mission_snapshot(missions, now=None):
    rows = list(missions.values()) if isinstance(missions, dict) else list(missions or [])
    now = now or datetime.now(timezone.utc)
    output = []
    by_system = {}
    urgent = []
    ground_count = passenger_count = illegal_count = expired_count = 0
    for mission in rows:
        if not isinstance(mission, dict):
            continue
        expiry = _parse_expiry(mission.get("expiry"))
        minutes = round((expiry - now).total_seconds() / 60) if expiry else None
        if minutes is not None and minutes <= 0:
            expired_count += 1
            continue
        system = mission.get("destination_system")
        settlement = mission.get("destination_settlement")
        internal = str(mission.get("internal_name") or "").casefold()
        kind = mission.get("kind") or "other"
        illegal = bool(mission.get("illegal")) or any(
            term in internal for term in ("illegal", "smuggl", "covert")
        )
        passenger = kind == "passenger" or "passenger" in internal
        ground_count += int(bool(settlement))
        passenger_count += int(passenger)
        illegal_count += int(illegal)
        if system:
            by_system[system] = int(by_system.get(system) or 0) + 1
        required = _integer(mission.get("to_deliver") or mission.get("count"))
        delivered = _integer(mission.get("delivered"))
        row = {
            "id": mission.get("id"),
            "name": mission.get("name") or "Mission",
            "kind": kind,
            "system": system,
            "station": mission.get("destination_station"),
            "settlement": settlement,
            "expiry_minutes": minutes,
            "urgent": minutes is not None and minutes <= 60,
            "expired": False,
            "illegal": illegal,
            "passenger": passenger,
            "wing": bool(mission.get("wing")),
            "commodity": mission.get("commodity"),
            "required": required,
            "delivered": delivered,
            "remaining": max(0, required - delivered),
            "reward_cr": _integer(mission.get("reward")),
        }
        output.append(row)
        if row["urgent"]:
            urgent.append(row)
    output.sort(
        key=lambda row: (
            row["expiry_minutes"] is None,
            row["expiry_minutes"] if row["expiry_minutes"] is not None else 10**9,
        )
    )
    return {
        "active": len(output),
        "rows": output[:16],
        "urgent": urgent[:8],
        "by_system": by_system,
        "grouped_destinations": [
            {"system": system, "missions": count}
            for system, count in sorted(
                by_system.items(), key=lambda pair: (-pair[1], pair[0]),
            )
            if count >= 2
        ],
        "ground": ground_count,
        "passengers": passenger_count,
        "illegal": illegal_count,
        "expired_count": expired_count,
    }


def _carrier_snapshot(carrier_data):
    carrier = dict(carrier_data or {})
    if not carrier.get("carrier_id"):
        return None
    route = [
        row for row in carrier.get("expedition_route") or []
        if isinstance(row, dict) and row.get("system")
    ]
    route_done = sum(1 for row in route if row.get("visited"))
    carrier_system = _clean(carrier.get("system")).casefold()
    route_next = next(
        (
            row for row in route
            if not row.get("visited")
            and _clean(row.get("system")).casefold() != carrier_system
        ),
        None,
    )
    used_capacity = None
    try:
        used_capacity = max(
            0, int(carrier.get("space_total")) - int(carrier.get("space_free")),
        )
    except (TypeError, ValueError):
        pass
    next_stop = None
    if route_next:
        next_stop = {
            key: route_next.get(key)
            for key in (
                "system", "id64", "distance_ly", "fuel_used_t",
                "fuel_remaining_t", "tritium_market_t", "must_restock",
            )
        }
        try:
            distance = float(route_next.get("distance_ly"))
            fuel = int(carrier.get("fuel_level"))
            if used_capacity is not None:
                calculated = int(math.floor(
                    5.0 + (distance / 8.0)
                    * (1.0 + (used_capacity + fuel) / 25000.0)
                    + 0.5
                ))
                calculated = max(0, min(fuel, calculated))
                next_stop["calculated_fuel_t"] = calculated
                next_stop["projected_fuel_t"] = fuel - calculated
        except (TypeError, ValueError):
            pass
    return {
        "name": carrier.get("name"),
        "callsign": carrier.get("callsign"),
        "system": carrier.get("system"),
        "status": carrier.get("status"),
        "fuel_level": carrier.get("fuel_level"),
        "fuel_capacity": carrier.get("fuel_capacity"),
        "fuel_level_estimated": bool(carrier.get("fuel_level_estimated")),
        "jump_destination": carrier.get("jump_destination"),
        "trade_orders": len(carrier.get("trade_orders") or []),
        "available_balance": carrier.get("available_balance"),
        "space_total": carrier.get("space_total"),
        "space_free": carrier.get("space_free"),
        "space_used": used_capacity,
        "route_name": carrier.get("expedition_name"),
        "route_completed": route_done,
        "route_total": len(route),
        "route_remaining": max(0, len(route) - route_done),
        "route_next": next_stop,
        "route_reserve_fuel": carrier.get("expedition_reserve_fuel"),
    }


def build_snapshot(
    runtime, *, companion_state=None, carrier_data=None, current_system=None,
):
    """Build the compact context consumed by the current command deck."""
    runtime = runtime if isinstance(runtime, dict) else fresh_runtime_state()
    companion_state = companion_state if isinstance(companion_state, dict) else {}
    ground = dict(runtime.get("ground") or {})
    backpack = ground.get("backpack") or {}
    consumables = backpack.get("consumables") or {}
    ground["medkits"] = sum(
        value for name, value in consumables.items()
        if "med" in name.casefold() or "health" in name.casefold()
    )
    ground["energy_cells"] = sum(
        value for name, value in consumables.items() if "energy" in name.casefold()
    )
    ground["backpack_units"] = sum(
        sum(_integer(value) for value in (backpack.get(bucket) or {}).values())
        for bucket in ("items", "components", "consumables", "data")
    )
    missions = mission_snapshot(companion_state.get("missions") or {})
    missions["session"] = dict(runtime.get("missions") or {})
    activity = dict(runtime.get("activity") or {})
    last_activity = _number(activity.get("last_event_at") or activity.get("since"))
    if last_activity and time.time() - last_activity > 1800:
        activity.update({"mode": "general", "confidence": 0.35})
    return {
        "ground_operations": ground,
        "missions": missions,
        "strategy": {
            "carrier": _carrier_snapshot(carrier_data),
            "current_system": current_system,
        },
        "activity": activity,
    }
