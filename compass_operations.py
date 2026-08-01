"""Low-noise operational state for the local Compass cognition engine.

The journal can be extremely chatty.  This module aggregates routine events
into compact verified facts; it never emits UI or speech itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
import time


MAX_NOTABLE_SIGNALS = 16
RESCUE_TERMS = (
    "escape pod", "occupied cryopod", "damaged escape pod", "personal effects",
    "black box", "wreckage component", "survival equipment", "hostage",
    "escapepod", "occupiedcryopod", "damagedescapepod", "personaleffects",
    "blackbox", "wreckagecomponents", "survivalequipment",
)
SALVAGE_TERMS = (
    "salvage", "black box", "wreckage", "personal effects", "trade data",
    "encrypted data", "rebel transmissions", "military plans",
)

ACTIVITY_EVENTS = {
    "exploration": {
        "FSSDiscoveryScan", "FSSAllBodiesFound", "FSSBodySignals",
        "FSSSignalDiscovered", "Scan", "SAAScanComplete", "ScanOrganic",
        "CodexEntry", "NavBeaconScan",
    },
    "mining": {"ProspectedAsteroid", "MiningRefined", "AsteroidCracked"},
    "trade": {"MarketBuy", "MarketSell", "BuyTradeData"},
    "combat": {
        "Bounty", "FactionKillBond", "CapShipBond", "UnderAttack",
        "Interdicted", "Interdiction", "EscapeInterdiction", "Died",
        "FighterDestroyed", "PVPKill", "ShipTargeted", "SystemsShutdown",
        "SelfDestruct",
    },
    "ground": {
        "Disembark", "SuitLoadout", "ApproachSettlement", "CollectItems",
        "DropItems", "Backpack", "BackpackChange", "BookDropship",
    },
    "engineering": {"EngineerCraft", "MaterialTrade", "TechnologyBroker"},
    "powerplay": {
        "Powerplay", "PowerplayCollect", "PowerplayDeliver", "PowerplayDefect",
        "PowerplayFastTrack", "PowerplayJoin", "PowerplayLeave", "PowerplayMerits",
        "PowerplayRank", "PowerplaySalary", "PowerplayVote",
    },
    "carrier": {
        "CarrierBuy", "CarrierJump", "CarrierJumpCancelled", "CarrierJumpRequest",
        "CarrierStats", "CarrierTradeOrder", "CarrierBankTransfer",
    },
    "colonisation": {
        "ColonisationConstructionDepot", "ColonisationContribution",
        "ColonisationSystemClaim", "ColonisationSystemClaimRelease",
        "ColonisationBeaconDeployed", "CompleteConstruction",
    },
    "station": {"Docked"},
}


def _activity_for_event(event):
    for mode, events in ACTIVITY_EVENTS.items():
        if event in events:
            return mode
    return None


def classify_important_message(raw):
    """Return a bounded actionable NPC/game message; discard routine/player chat."""
    if not isinstance(raw, dict):
        return None
    channel = str(raw.get("Channel") or "").casefold()
    sender_raw = str(raw.get("From") or "")
    sender = _clean(raw.get("From_Localised") or sender_raw, "Game communication")
    text = str(raw.get("Message_Localised") or raw.get("Message") or "").strip()
    if not text:
        return None
    internal_sender = sender_raw.startswith("$") or channel in {
        "npc", "missions", "station", "system", "squadronleadership",
    }
    if channel in {"player", "wing", "friend", "squadron", "starsystem", "local"}:
        return None
    combined = f"{sender} {text}".casefold()
    groups = (
        ("distress", 92, ("mayday", "distress", "under attack", "evacuat", "need assistance")),
        ("access", 88, ("docking request denied", "access denied", "docking denied", "permission denied")),
        ("mission", 84, ("mission updated", "mission redirected", "objective updated", "mission failed", "urgent objective")),
        ("security", 82, ("security alert", "scan detected", "hostile scan", "wanted status", "trespass warning")),
    )
    match = next(((kind, severity) for kind, severity, terms in groups
                  if any(term in combined for term in terms)), None)
    if not match or not internal_sender:
        return None
    clean_text = re.sub(r"\s+", " ", text).strip()[:180]
    return {
        "kind": match[0], "priority": match[1], "sender": sender,
        "message": clean_text, "timestamp": raw.get("timestamp"),
    }


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
        or row.get("Commodity_Localised") or row.get("Name")
        or row.get("Type") or row.get("Commodity"),
        fallback,
    )


def fresh_runtime_state():
    return {
        "activity": {
            "mode": "general", "since": time.time(), "last_event": None,
            "confidence": 0.4,
        },
        "communications": {"last_important": None, "recent": []},
        "ship": {
            "loadout_context": None,
            "fuel_scoop_events": 0,
            "fuel_scooped_t": 0.0,
            "reservoir_refills": 0,
            "drones_launched": {},
            "repairs": 0,
            "refuels": 0,
            "synthesis": {},
            "cargo_ejected_t": 0,
            "systems_shutdowns": 0,
            "last_systems_shutdown": None,
            "self_destructs": 0,
        },
        "signals": {
            "system": None,
            "total": 0,
            "by_type": {},
            "highest_threat": 0,
            "notable": [],
            "data_scans": {},
            "last_drop": None,
            "last_summary": None,
        },
        "ground": {
            "suit": None,
            "loadout": None,
            "suit_mods": [],
            "weapons": [],
            "backpack": {"items": {}, "components": {}, "consumables": {}, "data": {}},
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
        "legal": {
            "crimes": 0,
            "fines_received": 0,
            "fines_paid_cr": 0,
            "bounties_paid_cr": 0,
            "impounds_cleared": 0,
            "last_crime": None,
        },
        "missions": {
            "accepted": 0,
            "completed": 0,
            "failed": 0,
            "abandoned": 0,
            "rewards_cr": 0,
        },
    }


def _reset_signals(state, system):
    previous = state.get("signals") or {}
    last_summary = previous.get("last_summary")
    if previous.get("system"):
        last_summary = {
            "system": previous.get("system"),
            "total": int(previous.get("total") or 0),
            "by_type": dict(previous.get("by_type") or {}),
            "highest_threat": int(previous.get("highest_threat") or 0),
            "notable": list(previous.get("notable") or []),
            "data_scans": dict(previous.get("data_scans") or {}),
        }
    state["signals"] = {
        "system": system,
        "total": 0,
        "by_type": {},
        "highest_threat": 0,
        "notable": [],
        "data_scans": {},
        "last_drop": None,
        "last_summary": last_summary,
    }


def _notable_signal(raw):
    signal_type = _clean(raw.get("SignalType"), "Unknown signal")
    name = _clean(raw.get("SignalName") or raw.get("SignalName_Localised"), signal_type)
    threat = _integer(raw.get("ThreatLevel"), 0)
    combined = f"{signal_type} {name}".casefold()
    routine = signal_type.casefold() in {"fleetcarrier", "fleet carrier"}
    interesting = threat > 0 or any(term in combined for term in (
        "distress", "weapons fire", "non human", "nonhuman", "notable",
        "encoded", "degraded", "high grade", "highgrade", "salvage",
        "combat aftermath", "combat aftermath", "combataftermath",
        "megaship", "installation",
    ))
    if routine or not interesting:
        return None
    return {
        "name": name,
        "type": signal_type,
        "threat": threat,
        "is_station": bool(raw.get("IsStation")),
        "timestamp": raw.get("timestamp"),
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
    """Fold one journal event into the current operational state."""
    if not isinstance(state, dict):
        return False
    raw = raw if isinstance(raw, dict) else {}
    event = str(event or "")
    if event == "LoadGame" and not historical:
        state.clear()
        state.update(fresh_runtime_state())
    ship = state.setdefault("ship", fresh_runtime_state()["ship"])
    signals = state.setdefault("signals", fresh_runtime_state()["signals"])
    ground = state.setdefault("ground", fresh_runtime_state()["ground"])
    legal = state.setdefault("legal", fresh_runtime_state()["legal"])
    missions = state.setdefault("missions", fresh_runtime_state()["missions"])
    activity = state.setdefault("activity", fresh_runtime_state()["activity"])
    communications = state.setdefault("communications", fresh_runtime_state()["communications"])
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
                "mode": mode, "last_event": event, "last_event_at": now,
                "confidence": 1.0,
            })
            changed = True
        if event == "ReceiveText":
            important = classify_important_message(raw)
            if important:
                important["observed_at"] = time.time()
                communications["last_important"] = important
                recent = list(communications.get("recent") or [])
                marker = (important["kind"], important["sender"], important["message"])
                if not any((row.get("kind"), row.get("sender"), row.get("message")) == marker
                           for row in recent if isinstance(row, dict)):
                    recent.append(important)
                communications["recent"] = recent[-8:]
                changed = True

    if event in ("Location", "FSDJump", "CarrierJump"):
        system = raw.get("StarSystem") or current_system
        if system and str(system).casefold() != str(signals.get("system") or "").casefold():
            _reset_signals(state, system)
            signals = state["signals"]
            changed = True

    if event == "FSSSignalDiscovered":
        signal_type = _clean(raw.get("SignalType"), "Unknown signal")
        signals["total"] = int(signals.get("total") or 0) + 1
        by_type = signals.setdefault("by_type", {})
        by_type[signal_type] = int(by_type.get(signal_type) or 0) + 1
        threat = _integer(raw.get("ThreatLevel"), 0)
        signals["highest_threat"] = max(int(signals.get("highest_threat") or 0), threat)
        notable = _notable_signal(raw)
        if notable:
            rows = list(signals.get("notable") or [])
            marker = (notable["name"].casefold(), notable["type"].casefold(), notable["threat"])
            if not any((str(row.get("name") or "").casefold(), str(row.get("type") or "").casefold(), int(row.get("threat") or 0)) == marker for row in rows):
                rows.append(notable)
                signals["notable"] = rows[-MAX_NOTABLE_SIGNALS:]
        changed = True
    elif event in ("DataScanned", "Scanned"):
        scan_type = _event_name(raw, "Data scan")
        scans = signals.setdefault("data_scans", {})
        scans[scan_type] = int(scans.get(scan_type) or 0) + 1
        changed = True
    elif event in ("SupercruiseDestinationDrop", "USSDrop"):
        threat = _integer(
            raw.get("USSThreat") if event == "USSDrop" else raw.get("Threat"), 0
        )
        signals["last_drop"] = {
            "type": (
                raw.get("USSType_Localised") or raw.get("USSType")
                if event == "USSDrop" else raw.get("Type")
            ),
            "threat": threat,
            "timestamp": raw.get("timestamp"),
        }
        signals["highest_threat"] = max(int(signals.get("highest_threat") or 0), threat)
        changed = True

    if not historical:
        if event == "FuelScoop":
            ship["fuel_scoop_events"] = int(ship.get("fuel_scoop_events") or 0) + 1
            ship["fuel_scooped_t"] = round(float(ship.get("fuel_scooped_t") or 0) + _number(raw.get("Scooped")), 2)
            changed = True
        elif event == "ReservoirReplenished":
            ship["reservoir_refills"] = int(ship.get("reservoir_refills") or 0) + 1
            changed = True
        elif event == "LaunchDrone":
            kind = _clean(raw.get("Type"), "Drone")
            launched = ship.setdefault("drones_launched", {})
            launched[kind] = int(launched.get(kind) or 0) + 1
            changed = True
        elif event in ("Repair", "RepairAll"):
            ship["repairs"] = int(ship.get("repairs") or 0) + 1
            changed = True
        elif event in ("RefuelAll", "RefuelPartial"):
            ship["refuels"] = int(ship.get("refuels") or 0) + 1
            changed = True
        elif event == "Synthesis":
            recipe = _clean(raw.get("Name"), "Synthesis")
            recipes = ship.setdefault("synthesis", {})
            recipes[recipe] = int(recipes.get(recipe) or 0) + 1
            changed = True
        elif event == "EjectCargo":
            ship["cargo_ejected_t"] = int(ship.get("cargo_ejected_t") or 0) + _integer(raw.get("Count"), 0)
            changed = True
        elif event == "SystemsShutdown":
            ship["systems_shutdowns"] = int(ship.get("systems_shutdowns") or 0) + 1
            ship["last_systems_shutdown"] = raw.get("timestamp") or time.time()
            changed = True
        elif event == "SelfDestruct":
            ship["self_destructs"] = int(ship.get("self_destructs") or 0) + 1
            changed = True

        if event == "MissionAccepted":
            missions["accepted"] = int(missions.get("accepted") or 0) + 1
            changed = True
        elif event == "MissionCompleted":
            missions["completed"] = int(missions.get("completed") or 0) + 1
            missions["rewards_cr"] = int(missions.get("rewards_cr") or 0) + _integer(raw.get("Reward"), 0)
            changed = True
        elif event == "MissionFailed":
            missions["failed"] = int(missions.get("failed") or 0) + 1
            changed = True
        elif event == "MissionAbandoned":
            missions["abandoned"] = int(missions.get("abandoned") or 0) + 1
            changed = True

    if event == "Loadout":
        ship["loadout_context"] = classify_loadout(raw)
        changed = True

    if event == "SuitLoadout":
        ground["suit"] = _clean(raw.get("SuitName_Localised") or raw.get("SuitName"), "Suit")
        ground["loadout"] = raw.get("LoadoutName")
        ground["suit_mods"] = [_clean(value) for value in raw.get("SuitMods") or []]
        ground["weapons"] = [
            {
                "name": _clean(row.get("ModuleName_Localised") or row.get("ModuleName"), "Weapon"),
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
            bucket[name] = max(0, int(bucket.get(name) or 0) - _integer(row.get("Count"), 1))
        changed = True
    elif event == "ApproachSettlement":
        ground["settlement"] = {
            "name": raw.get("Name"), "system": raw.get("StarSystem") or current_system,
            "body": raw.get("BodyName") or raw.get("Body"),
            "market_id": raw.get("MarketID"),
        }
        changed = True
    elif event == "Disembark":
        ground["on_foot"] = True
        ground["in_taxi"] = bool(raw.get("Taxi"))
        ground["in_multicrew"] = bool(raw.get("Multicrew"))
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
        destination = _clean(raw.get("To"), "Mothership")
        ground["vehicle_control"] = destination
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
            ground["stolen_items"] = int(ground.get("stolen_items") or 0) + (count if event == "CollectItems" else -count)
            ground["stolen_items"] = max(0, ground["stolen_items"])
        changed = True

    if not historical:
        if event == "CommitCrime":
            legal["crimes"] = int(legal.get("crimes") or 0) + 1
            legal["last_crime"] = _clean(raw.get("CrimeType_Localised") or raw.get("CrimeType"), "Crime")
            changed = True
        elif event == "Fine":
            legal["fines_received"] = int(legal.get("fines_received") or 0) + 1
            changed = True
        elif event == "PayFines":
            legal["fines_paid_cr"] = int(legal.get("fines_paid_cr") or 0) + _integer(raw.get("Amount") or raw.get("Cost"), 0)
            changed = True
        elif event == "PayBounties":
            legal["bounties_paid_cr"] = int(legal.get("bounties_paid_cr") or 0) + _integer(raw.get("Amount") or raw.get("Cost"), 0)
            changed = True
        elif event == "ClearImpound":
            legal["impounds_cleared"] = int(legal.get("impounds_cleared") or 0) + 1
            changed = True
    return changed


def observe_status(state, data):
    """Capture frequently-changing suit/vehicle facts without generating chatter."""
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


def classify_loadout(loadout):
    """Infer a broad ship role and verified capabilities from a Loadout event."""
    loadout = loadout if isinstance(loadout, dict) else {}
    modules = [row for row in loadout.get("Modules") or [] if isinstance(row, dict)]
    texts = [
        " ".join(str(row.get(key) or "") for key in ("Slot", "Item", "Item_Localised")).casefold()
        for row in modules
    ]

    def has(*needles):
        return any(any(needle in text for needle in needles) for text in texts)

    capabilities = {
        "fuel_scoop": has("fuelscoop"),
        "afmu": has("modulerepairer", "field maintenance"),
        "srv": has("vehiclebay", "planetary vehicle"),
        "fighter": has("fighterbay", "fighter hangar"),
        "shield": has("shieldgenerator", "shield generator"),
        "refinery": has("refinery"),
        "prospector": has("prospector"),
        "collector": has("collection", "collector"),
        "repair_limpet": has("repairer", "repair limpet"),
        "fuel_transfer": has("fueltransfer", "fuel transfer"),
        "hatch_breaker": has("hatchbreaker", "hatch breaker"),
        "recon_limpet": has("recon"),
        "dss": has("detailedsurfacescanner", "detailed surface scanner"),
        "interdictor": has("fsdinterdictor", "interdictor"),
    }
    mining_tools = sum(int(has(needle)) for needle in (
        "mininglaser", "seismiccharge", "abrasionblaster", "subsurfacedisplacement",
    ))
    hardpoints = sum(1 for text in texts if "hardpoint" in text or "hpt_" in text)
    scores = {
        "Exploration": 3 * int(capabilities["fuel_scoop"]) + 2 * int(capabilities["dss"]) + int(capabilities["afmu"]) + int(capabilities["srv"]),
        "Mining": 3 * int(capabilities["refinery"]) + 2 * int(capabilities["prospector"]) + 2 * int(capabilities["collector"]) + mining_tools * 2,
        "Combat": min(5, hardpoints) + 2 * int(capabilities["fighter"]) + int(capabilities["shield"]) + int(capabilities["interdictor"]),
        "Trade": (3 if _integer(loadout.get("CargoCapacity"), 0) >= 64 else 1 if _integer(loadout.get("CargoCapacity"), 0) >= 16 else 0) + int(capabilities["fuel_scoop"]),
    }
    best_role, best_score = max(scores.items(), key=lambda pair: pair[1])
    if best_score <= 1:
        best_role = "General"
    ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    if len(ordered) > 1 and ordered[0][1] >= 3 and ordered[1][1] == ordered[0][1]:
        best_role = "Multi-role"
    return {
        "role": best_role,
        "role_scores": scores,
        "capabilities": capabilities,
        "hardpoints": hardpoints,
        "ship": loadout.get("ShipName") or loadout.get("Ship_Localised") or loadout.get("Ship"),
        "cargo_capacity_t": _integer(loadout.get("CargoCapacity"), 0),
        "max_jump_range_ly": round(_number(loadout.get("MaxJumpRange")), 1),
        "rebuy_cr": _integer(loadout.get("Rebuy"), 0),
    }


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
    ground_count = 0
    passenger_count = 0
    illegal_count = 0
    expired_count = 0
    for mission in rows:
        if not isinstance(mission, dict):
            continue
        expiry = _parse_expiry(mission.get("expiry"))
        minutes = round((expiry - now).total_seconds() / 60) if expiry else None
        system = mission.get("destination_system")
        settlement = mission.get("destination_settlement")
        internal = str(mission.get("internal_name") or "").casefold()
        kind = mission.get("kind") or "other"
        illegal = bool(mission.get("illegal")) or any(term in internal for term in ("illegal", "smuggl", "covert"))
        passenger = kind == "passenger" or "passenger" in internal
        if minutes is not None and minutes <= 0:
            expired_count += 1
            continue
        if settlement:
            ground_count += 1
        passenger_count += int(passenger)
        illegal_count += int(illegal)
        if system:
            by_system[system] = int(by_system.get(system) or 0) + 1
        required = _integer(mission.get("to_deliver") or mission.get("count"), 0)
        delivered = _integer(mission.get("delivered"), 0)
        row = {
            "id": mission.get("id"), "name": mission.get("name") or "Mission",
            "kind": kind, "system": system, "station": mission.get("destination_station"),
            "settlement": settlement, "expiry_minutes": minutes,
            "urgent": minutes is not None and minutes <= 60,
            "expired": False,
            "illegal": illegal, "passenger": passenger, "wing": bool(mission.get("wing")),
            "commodity": mission.get("commodity"), "required": required,
            "delivered": delivered, "remaining": max(0, required - delivered),
            "reward_cr": _integer(mission.get("reward"), 0),
        }
        output.append(row)
        if row["urgent"]:
            urgent.append(row)
    output.sort(key=lambda row: (row["expiry_minutes"] is None, row["expiry_minutes"] or 10**9))
    return {
        "active": len(output), "rows": output[:16], "urgent": urgent[:8],
        "by_system": by_system, "grouped_destinations": [
            {"system": system, "missions": count}
            for system, count in sorted(by_system.items(), key=lambda pair: (-pair[1], pair[0]))
            if count >= 2
        ],
        "ground": ground_count, "passengers": passenger_count, "illegal": illegal_count,
        "expired_count": expired_count,
    }


def _cargo_snapshot(inventory):
    rescue = []
    salvage = []
    stolen_units = 0
    mission_units = 0
    for row in inventory or ():
        if not isinstance(row, dict):
            continue
        name = _event_name(row, "Cargo")
        count = _integer(row.get("Count", row.get("count")), 0)
        lowered = name.casefold()
        if any(term in lowered for term in RESCUE_TERMS):
            rescue.append({"name": name, "count": count})
        elif any(term in lowered for term in SALVAGE_TERMS):
            salvage.append({"name": name, "count": count})
        stolen = row.get("Stolen")
        if stolen:
            stolen_units += min(count, _integer(stolen, count))
        mission_units += count if row.get("MissionID") else 0
    return {
        "rescue": rescue, "rescue_units": sum(row["count"] for row in rescue),
        "salvage": salvage, "salvage_units": sum(row["count"] for row in salvage),
        "stolen_units": stolen_units, "mission_units": mission_units,
    }


def build_snapshot(runtime, *, companion_state=None, cargo_inventory=None,
                   engineer_materials=None, carrier_data=None,
                   colonisation_projects=None, current_system=None,
                   legal_state=None):
    """Build the verified operational context consumed by CompassCognition."""
    runtime = runtime if isinstance(runtime, dict) else fresh_runtime_state()
    companion_state = companion_state if isinstance(companion_state, dict) else {}
    cached_loadout = (runtime.get("ship") or {}).get("loadout_context")
    loadout = dict(cached_loadout or classify_loadout(companion_state.get("loadout")))
    loadout["capabilities"] = dict(loadout.get("capabilities") or {})
    loadout["role_scores"] = dict(loadout.get("role_scores") or {})
    cargo = _cargo_snapshot(cargo_inventory)
    limpets = sum(
        _integer(row.get("Count", row.get("count")), 0)
        for row in cargo_inventory or () if isinstance(row, dict)
        and any(term in _event_name(row).casefold() for term in ("limpet", "drone"))
    )
    raw_counts = {
        symbol: _integer(item.get("count") if isinstance(item, dict) else item, 0)
        for symbol, item in ((engineer_materials or {}).get("raw") or {}).items()
    }
    loadout["limpets"] = limpets
    loadout["raw_material_types"] = sum(1 for value in raw_counts.values() if value > 0)
    loadout["session_logistics"] = dict(runtime.get("ship") or {})

    ground = dict(runtime.get("ground") or {})
    backpack = ground.get("backpack") or {}
    consumables = backpack.get("consumables") or {}
    ground["medkits"] = sum(value for name, value in consumables.items() if "med" in name.casefold() or "health" in name.casefold())
    ground["energy_cells"] = sum(value for name, value in consumables.items() if "energy" in name.casefold())
    ground["backpack_units"] = sum(
        sum(_integer(value) for value in (backpack.get(bucket) or {}).values())
        for bucket in ("items", "components", "consumables", "data")
    )

    missions = mission_snapshot(companion_state.get("missions") or {})
    missions["session"] = dict(runtime.get("missions") or {})
    signals = dict(runtime.get("signals") or {})
    legal = dict(runtime.get("legal") or {})
    legal.update(cargo)
    legal["legal_state"] = legal_state

    activity = dict(runtime.get("activity") or {})
    last_activity = _number(activity.get("last_event_at") or activity.get("since"), 0)
    if last_activity and time.time() - last_activity > 1800:
        activity.update({"mode": "general", "confidence": 0.35})
    communications = dict(runtime.get("communications") or {})
    communications["recent"] = list(communications.get("recent") or [])[-8:]

    watched = set(companion_state.get("watched_factions") or [])
    factions = [row for row in companion_state.get("factions") or [] if isinstance(row, dict)]
    watched_here = [row for row in factions if row.get("name") in watched]
    conflicts = [row for row in companion_state.get("conflicts") or [] if isinstance(row, dict)]
    active_projects = []
    matching_cargo = []
    cargo_by_name = {_event_name(row).casefold(): _integer(row.get("Count", row.get("count")), 0)
                     for row in cargo_inventory or () if isinstance(row, dict)}
    for project in (colonisation_projects or {}).values():
        if not isinstance(project, dict) or project.get("complete") or project.get("failed"):
            continue
        remaining = 0
        matched = []
        for resource in project.get("resources") or ():
            if not isinstance(resource, dict):
                continue
            needed = max(0, _integer(resource.get("required")) - _integer(resource.get("provided")))
            remaining += needed
            name = _clean(resource.get("display") or resource.get("name"), "Commodity")
            aboard = cargo_by_name.get(name.casefold(), 0)
            if needed and aboard:
                matched.append({"name": name, "aboard": min(aboard, needed), "remaining": needed})
        row = {
            "market_id": project.get("market_id"), "system": project.get("system_name"),
            "body": project.get("body_name"), "progress": _number(project.get("progress")),
            "remaining_units": remaining, "matched_cargo": matched,
        }
        active_projects.append(row)
        matching_cargo.extend(matched)

    carrier = dict(carrier_data or {})
    carrier_route = [
        row for row in (carrier.get("expedition_route") or [])
        if isinstance(row, dict) and row.get("system")
    ]
    carrier_route_done = sum(1 for row in carrier_route if row.get("visited"))
    carrier_system = _clean(carrier.get("system")).casefold()
    carrier_route_next = next(
        (
            row for row in carrier_route
            if not row.get("visited")
            and _clean(row.get("system")).casefold() != carrier_system
        ), None,
    )
    carrier_used_capacity = None
    try:
        carrier_used_capacity = max(
            0, int(carrier.get("space_total")) - int(carrier.get("space_free")),
        )
    except (TypeError, ValueError):
        pass
    next_stop = None
    if carrier_route_next:
        next_stop = {
            key: carrier_route_next.get(key)
            for key in (
                "system", "id64", "distance_ly", "fuel_used_t",
                "fuel_remaining_t", "tritium_market_t", "must_restock",
            )
        }
        try:
            distance = float(carrier_route_next.get("distance_ly"))
            fuel = int(carrier.get("fuel_level"))
            if carrier_used_capacity is not None:
                # Match the in-game Fleet Carrier burn, rather than a Spansh
                # plan produced with an older/different carrier load.
                calculated = int(math.floor(
                    5.0 + (distance / 8.0)
                    * (1.0 + (carrier_used_capacity + fuel) / 25000.0)
                    + 0.5
                ))
                calculated = max(0, min(fuel, calculated))
                next_stop["calculated_fuel_t"] = calculated
                next_stop["projected_fuel_t"] = fuel - calculated
        except (TypeError, ValueError):
            pass
    strategy = {
        "watched_factions_here": watched_here,
        "conflicts": conflicts[:8],
        "community_goals": list((companion_state.get("community_goals") or {}).values())[:8],
        "squadron": dict(companion_state.get("squadron") or {}),
        "carrier": {
            "name": carrier.get("name"), "callsign": carrier.get("callsign"),
            "system": carrier.get("system"), "status": carrier.get("status"),
            "fuel_level": carrier.get("fuel_level"), "fuel_capacity": carrier.get("fuel_capacity"),
            "fuel_level_estimated": bool(carrier.get("fuel_level_estimated")),
            "jump_destination": carrier.get("jump_destination"),
            "trade_orders": len(carrier.get("trade_orders") or []),
            "available_balance": carrier.get("available_balance"),
            "space_total": carrier.get("space_total"),
            "space_free": carrier.get("space_free"),
            "space_used": carrier_used_capacity,
            "route_name": carrier.get("expedition_name"),
            "route_completed": carrier_route_done,
            "route_total": len(carrier_route),
            "route_remaining": max(0, len(carrier_route) - carrier_route_done),
            "route_next": next_stop,
            "route_reserve_fuel": carrier.get("expedition_reserve_fuel"),
        } if carrier.get("carrier_id") else None,
        "colonisation_projects": active_projects[:12],
        "colonisation_matching_cargo": matching_cargo[:12],
        "current_system": current_system,
    }
    return {
        "ship_operations": loadout,
        "signals": signals,
        "ground_operations": ground,
        "missions": missions,
        "strategy": strategy,
        "rescue_legal": legal,
        "activity": activity,
        "communications": communications,
    }
