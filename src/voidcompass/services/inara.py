"""Inara (inara.cz) sync, 5.5.4.

Void Compass is whitelisted with Inara as "VoidCompass". With the commander's
own Inara API key it sends what Inara keeps for a commander: credits, ranks,
reputation, ships and loadouts, materials and cargo, missions, the flight
log, combat log and community goals, stored modules, suit loadouts and
friends: every commander event the API takes. It never asks Inara about
anyone else.

Inara's rules (inara.cz/elite/inara-api-devguide): batch events rather than
send them one by one, send at session start, on docking and on jumps rather
than constantly, never resend the same data, only live game data (no
Legacy, no beta), and nothing older than 30 days. This follows them: events
queue up, a batch goes at most once a minute, unchanged state is never sent
twice, and a rejected key stops the uploads until the settings change.

What Inara has taken is remembered across restarts (5.5.7): restarting Void
Compass mid-session re-reads the journal, and the unchanged credits, ranks,
ship and materials used to go again each time. A new game session (LoadGame
while running) still sends the whole state once, as Inara asks.

Each piece of state has a slot of its own (5.5.9): a ship, a suit loadout, a
mission, each inventory category (its set and its reset share one). The
locker's categories once shared a slot, so the game's frequent ShipLocker
rewrites sent Items and Data resets over and over, and one category could
replace another still waiting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
import re
import sys
import threading
import time

import requests

API_URL = "https://inara.cz/inapi/v1/"
APP_NAME = "VoidCompass"
MAX_BATCH = 100
MIN_GAP_S = 60.0
TIMER_S = 15.0
MAX_AGE = timedelta(days=30)
# The remembered-state file's layout; an older one is ignored (5.5.9).
SENT_VERSION = 2
# Journal events after which a batch should go (Inara asks for these).
FLUSH_AFTER = frozenset({"LoadGame", "Docked", "FSDJump", "CarrierJump", "Shutdown"})

PILOT_RANKS = {"Combat": "combat", "Trade": "trade", "Explore": "explore", "CQC": "cqc", "Soldier": "soldier",
               "Exobiologist": "exobiologist", "Federation": "federation", "Empire": "empire"}
MATERIAL_TYPES = ("Raw", "Manufactured", "Encoded")
# The stages Inara takes for an engineer (the journal also has "Known").
ENGINEER_STAGES = frozenset({"Invited", "Acquainted", "Unlocked", "Barred"})
LOCKER_TYPES = {"Items": "Item", "Components": "Component", "Consumables": "Consumable", "Data": "Data"}


def _stamp(raw):
    return str((raw or {}).get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def _recent(stamp):
    try:
        when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - when <= MAX_AGE


def _name(raw, key):
    return str(raw.get(key) or "")


def _number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def app_version(version):
    """The docs ask for '1.2.4' style versions; a hotfix's 5.5.3.9.3 goes as 5.5.3."""
    parts = [part for part in str(version or "").split(".") if part.isdigit()][:3]
    return ".".join(parts + ["0"] * (3 - len(parts))) if parts else "0.0.0"


def live_game(version):
    """Only the Live game's data may go to Inara: not Legacy (3.x), not beta."""
    text = str(version or "").strip().casefold()
    if not text:
        return True
    return not text.startswith("3.") and "beta" not in text and "alpha" not in text


def _modifier(item):
    """One engineering modifier. Numbers carry their original value; a text
    one (DamageType: "$Thermic;") goes as the journal's ValueStr."""
    if not isinstance(item, dict) or not item.get("Label"):
        return None
    if item.get("OriginalValue") is not None:
        return {"name": str(item["Label"]), "value": item.get("Value"), "originalValue": item["OriginalValue"],
                "lessIsGood": bool(item.get("LessIsGood"))}
    value = item.get("ValueStr") if item.get("ValueStr") is not None else item.get("Value")
    return {"name": str(item["Label"]), "value": value} if value is not None else None


# Cosmetics the Loadout lists beside the modules: Inara's loadouts are modules
# only, and answers "unknown modules" (204) when these are sent.
COSMETIC_SLOT = re.compile(r"^(PaintJob|Decal\d+|ShipName\d+|ShipID\d+|Bobble\d+|ShipKit\w*|WeaponColour|EngineColour"
                           r"|StringLights|VesselVoice|Hologram\w*)$", re.I)
COSMETIC_ITEM = ("paintjob_", "decal_", "nameplate_", "bobble_", "weaponcustomisation_", "enginecustomisation_",
                 "voicepack_", "string_lights_")


def is_cosmetic(module):
    item = str(module.get("Item") or "").casefold()
    return bool(COSMETIC_SLOT.match(str(module.get("Slot") or ""))) or item.startswith(COSMETIC_ITEM) or "_shipkit" in item


def ship_loadout(modules, hot=False):
    """The journal's Loadout modules in Inara's own shape (cosmetics left out)."""
    out = []
    for module in modules or ():
        if not isinstance(module, dict) or not module.get("Slot") or not module.get("Item") or is_cosmetic(module):
            continue
        row = {"slotName": str(module["Slot"]), "itemName": str(module["Item"]),
               "itemHealth": round(_number(module.get("Health"), 1.0), 4), "isOn": bool(module.get("On", True)),
               "itemPriority": int(_number(module.get("Priority"))),
               # A module's own heat if the journal gives it, else the ship's.
               "isHot": bool(module.get("Hot", hot))}
        if module.get("Value") is not None:
            row["itemValue"] = int(_number(module["Value"]))
        if module.get("AmmoInClip") is not None:
            row["itemAmmoClip"] = int(_number(module["AmmoInClip"]))
        if module.get("AmmoInHopper") is not None:
            row["itemAmmoHopper"] = int(_number(module["AmmoInHopper"]))
        engineering = module.get("Engineering")
        if isinstance(engineering, dict) and engineering.get("BlueprintName"):
            blueprint = {"blueprintName": str(engineering["BlueprintName"]),
                         "blueprintLevel": int(_number(engineering.get("Level"))),
                         "blueprintQuality": round(_number(engineering.get("Quality")), 4)}
            if engineering.get("ExperimentalEffect"):
                blueprint["experimentalEffect"] = str(engineering["ExperimentalEffect"])
            blueprint["modifiers"] = [row for row in map(_modifier, engineering.get("Modifiers") or ()) if row]
            row["engineering"] = blueprint
        out.append(row)
    return out


def _here(raw, context):
    """Where the commander is: the station they're docked at."""
    where = {"starsystemName": str(context.get("system") or ""), "stationName": str(context.get("station") or ""),
             "marketID": raw.get("MarketID")}
    return {key: value for key, value in where.items() if value not in ("", None)}


def _opponent(raw, key):
    """The other ship's name, or (as the spec says) its Power or Faction."""
    return _name(raw, key) or _name(raw, "Power") or _name(raw, "Faction") or "Unknown"


def _materials(event_name, rows, name_key="Name", count_key="Count"):
    """One Inara event per material (they take a single item each)."""
    out = []
    for row in rows or ():
        if isinstance(row, dict) and row.get(name_key) and _number(row.get(count_key), 0) > 0:
            out.append((event_name, {"itemName": str(row[name_key]), "itemCount": int(_number(row[count_key]))}))
    return out


def _faction_effects(effects):
    """A mission's FactionEffects as Inara's minorfactionEffects."""
    out = []
    for effect in effects or ():
        if not isinstance(effect, dict) or not effect.get("Faction"):
            continue
        influence = "".join(str(row.get("Influence") or "") for row in effect.get("Influence") or () if isinstance(row, dict))
        row = {"minorfactionName": str(effect["Faction"]), "influenceGain": influence[:5],
               "reputationGain": str(effect.get("Reputation") or "")}
        out.append({key: value for key, value in row.items() if value})
    return out


def _suit_module(row):
    """One weapon slot of a suit loadout, as Inara's example has it."""
    out = {"slotName": _name(row, "SlotName"), "itemName": _name(row, "ModuleName"),
           "itemClass": int(_number(row.get("Class"), 1)), "itemGameID": row.get("SuitModuleID")}
    mods = [{"blueprintName": str(mod)} for mod in row.get("WeaponMods") or () if mod]
    if mods:
        out["engineering"] = mods
    return {key: value for key, value in out.items() if value not in ("", None)}


def suit_loadout(raw):
    """A SuitLoadout or CreateSuitLoadout journal event as Inara's suit loadout."""
    return {"loadoutGameID": raw.get("LoadoutID"), "loadoutName": _name(raw, "LoadoutName"),
            "suitGameID": raw.get("SuitID"), "suitType": _name(raw, "SuitName"),
            "suitMods": [str(mod) for mod in raw.get("SuitMods") or () if mod],
            "suitLoadout": [_suit_module(row) for row in raw.get("Modules") or () if isinstance(row, dict) and row.get("SlotName")]}


def stored_modules(raw):
    """StoredModules as Inara's storage list; a module in transit has no place."""
    out = []
    for item in raw.get("Items") or ():
        if not isinstance(item, dict) or not item.get("Name"):
            continue
        row = {"itemName": str(item["Name"]).rstrip(";"), "itemValue": int(_number(item.get("BuyPrice"))),
               "isHot": bool(item.get("Hot"))}
        if not item.get("InTransit"):
            market = item.get("MarketID", raw.get("MarketID"))
            row.update(starsystemName=_name(item, "StarSystem") or _name(raw, "StarSystem"), marketID=market)
            if market == raw.get("MarketID") and raw.get("StationName"):
                row["stationName"] = _name(raw, "StationName")
        if item.get("EngineerModifications"):
            row["engineering"] = {"blueprintName": str(item["EngineerModifications"]),
                                  "blueprintLevel": int(_number(item.get("Level"))),
                                  "blueprintQuality": round(_number(item.get("Quality")), 4)}
        out.append({key: value for key, value in row.items() if value not in ("", None)})
    return out


def stored_ships(raw):
    """Where every stored ship is, from StoredShips."""
    out = []
    for ship in raw.get("ShipsHere") or ():
        if isinstance(ship, dict) and ship.get("ShipID") is not None:
            row = {"shipType": _name(ship, "ShipType"), "shipGameID": ship["ShipID"], "shipName": _name(ship, "Name"),
                   "starsystemName": _name(raw, "StarSystem"), "stationName": _name(raw, "StationName"),
                   "marketID": raw.get("MarketID"), "isHot": bool(ship.get("Hot"))}
            out.append(("setCommanderShip", {key: value for key, value in row.items() if value not in ("", None)}))
    for ship in raw.get("ShipsRemote") or ():
        if isinstance(ship, dict) and ship.get("ShipID") is not None:
            row = {"shipType": _name(ship, "ShipType"), "shipGameID": ship["ShipID"], "shipName": _name(ship, "Name"),
                   "isHot": bool(ship.get("Hot"))}
            if not ship.get("InTransit"):
                row.update(starsystemName=_name(ship, "StarSystem"), marketID=ship.get("ShipMarketID"))
            out.append(("setCommanderShip", {key: value for key, value in row.items() if value not in ("", None)}))
    return out


def _minor_factions(raw):
    """Your reputation with the system's factions (MyReputation, -100..100)."""
    rows = [{"minorfactionName": str(row["Name"]), "minorfactionReputation": round(_number(row.get("MyReputation")) / 100.0, 4)}
            for row in raw.get("Factions") or () if isinstance(row, dict) and row.get("Name") and row.get("MyReputation") is not None]
    return [("setCommanderReputationMinorFaction", rows)] if rows else []


def map_event(event, raw, context=None):
    """Inara events for one journal event: [(eventName, eventData)]."""
    raw = raw if isinstance(raw, dict) else {}
    context = context or {}
    ship = {"shipType": str(context.get("ship_type") or ""), "shipGameID": context.get("ship_id")}
    ship = {key: value for key, value in ship.items() if value not in ("", None)}
    out = []
    if event == "LoadGame":
        out.append(("setCommanderCredits", {"commanderCredits": int(_number(raw.get("Credits"))),
                                            "commanderLoan": int(_number(raw.get("Loan")))}))
        if raw.get("ShipID") is not None and raw.get("Ship") and not str(raw.get("Ship")).casefold().endswith("suit_class1"):
            out.append(("setCommanderShip", {"shipType": _name(raw, "Ship"), "shipGameID": raw.get("ShipID"),
                                             "shipName": _name(raw, "ShipName"), "shipIdent": _name(raw, "ShipIdent"),
                                             "isCurrentShip": True}))
    elif event == "Location":
        data = {"starsystemName": _name(raw, "StarSystem"), "starsystemCoords": raw.get("StarPos")}
        if raw.get("Docked"):
            data.update(stationName=_name(raw, "StationName"), marketID=raw.get("MarketID"))
        if raw.get("Body") and raw.get("BodyType") != "Star":
            data["starsystemBodyName"] = _name(raw, "Body")
            if raw.get("Latitude") is not None and raw.get("Longitude") is not None:
                data["starsystemBodyCoords"] = [raw["Latitude"], raw["Longitude"]]
        out.append(("setCommanderTravelLocation", data))
        out.extend(_minor_factions(raw))
    elif event == "FSDJump":
        out.append(("addCommanderTravelFSDJump", {
            "starsystemName": _name(raw, "StarSystem"), "starsystemCoords": raw.get("StarPos"),
            "jumpDistance": round(_number(raw.get("JumpDist")), 2), "isTaxiShuttle": bool(raw.get("Taxi")), **ship}))
        out.extend(_minor_factions(raw))
    elif event == "CarrierJump":
        out.append(("addCommanderTravelCarrierJump", {
            "starsystemName": _name(raw, "StarSystem"), "starsystemCoords": raw.get("StarPos"),
            "stationName": _name(raw, "StationName"), "marketID": raw.get("MarketID"), **ship}))
    elif event == "Docked":
        out.append(("addCommanderTravelDock", {
            "starsystemName": _name(raw, "StarSystem"), "stationName": _name(raw, "StationName"),
            "marketID": raw.get("MarketID"), "isTaxiShuttle": bool(raw.get("Taxi")), **ship}))
    elif event == "Touchdown" and raw.get("PlayerControlled", True) and raw.get("Body"):
        data = {"starsystemName": _name(raw, "StarSystem"), "starsystemBodyName": _name(raw, "Body"), **ship}
        if raw.get("Latitude") is not None and raw.get("Longitude") is not None:
            data["starsystemBodyCoords"] = [raw.get("Latitude"), raw.get("Longitude")]
        out.append(("addCommanderTravelLand", data))
    elif event == "DropShipDeploy" and raw.get("StarSystem"):
        data = {"starsystemName": _name(raw, "StarSystem"), "isTaxiDropship": True}
        if raw.get("Body"):
            data["starsystemBodyName"] = _name(raw, "Body")
        out.append(("addCommanderTravelLand", data))
    elif event in ("Rank", "Progress"):
        rows = []
        for key, rank in PILOT_RANKS.items():
            if key in raw:
                value = int(_number(raw[key]))
                rows.append({"rankName": rank, **({"rankValue": value} if event == "Rank" else {"rankProgress": value / 100.0})})
        if rows:
            out.append(("setCommanderRankPilot", rows))
    elif event == "Promotion":
        rows = [{"rankName": rank, "rankValue": int(_number(raw[key])), "rankProgress": 0}
                for key, rank in PILOT_RANKS.items() if key in raw]
        if rows:
            out.append(("setCommanderRankPilot", rows))
    elif event == "Reputation":
        rows = [{"majorfactionName": key.casefold(), "majorfactionReputation": round(_number(raw[key]) / 100.0, 4)}
                for key in ("Empire", "Federation", "Independent", "Alliance") if key in raw]
        if rows:
            out.append(("setCommanderReputationMajorFaction", rows))
    elif event == "Powerplay":
        out.append(("setCommanderRankPower", {"powerName": _name(raw, "Power"), "rankValue": int(_number(raw.get("Rank"))),
                                              "meritsValue": int(_number(raw.get("Merits")))}))
    elif event == "PowerplayLeave":
        out.append(("setCommanderRankPower", {"powerName": _name(raw, "Power"), "rankValue": -1}))
    elif event == "PowerplayRank" and raw.get("Power") and raw.get("Rank") is not None:
        out.append(("setCommanderRankPower", {"powerName": _name(raw, "Power"), "rankValue": int(_number(raw["Rank"]))}))
    elif event == "PowerplayMerits" and raw.get("Power") and context.get("power_rank") is not None:
        out.append(("setCommanderRankPower", {"powerName": _name(raw, "Power"), "rankValue": context["power_rank"],
                                              "meritsValue": int(_number(raw.get("TotalMerits")))}))
    elif event == "EngineerProgress":
        rows = []
        engineers = raw["Engineers"] if isinstance(raw.get("Engineers"), list) else [raw]
        for engineer in engineers:
            if not isinstance(engineer, dict) or not engineer.get("Engineer"):
                continue
            row = {"engineerName": str(engineer["Engineer"])}
            if engineer.get("Progress") in ENGINEER_STAGES:
                row["rankStage"] = str(engineer["Progress"])
            if engineer.get("Rank") is not None:
                row["rankValue"] = int(_number(engineer["Rank"]))
            if len(row) > 1:
                rows.append(row)
        if rows:
            out.append(("setCommanderRankEngineer", rows))
    elif event == "Statistics":
        stats = {key: value for key, value in raw.items() if key not in ("timestamp", "event")}
        out.append(("setCommanderGameStatistics", stats))
    elif event == "Loadout" and raw.get("ShipID") is not None:
        out.append(("setCommanderShip", {
            "shipType": _name(raw, "Ship"), "shipGameID": raw.get("ShipID"), "shipName": _name(raw, "ShipName"),
            "shipIdent": _name(raw, "ShipIdent"), "isCurrentShip": True, "isHot": bool(raw.get("Hot")),
            "shipHullValue": int(_number(raw.get("HullValue"))), "shipModulesValue": int(_number(raw.get("ModulesValue"))),
            "shipRebuyCost": int(_number(raw.get("Rebuy"))), "shipMaxJumpRange": round(_number(raw.get("MaxJumpRange")), 2),
            "shipCargoCapacity": int(_number(raw.get("CargoCapacity")))}))
        # After the ship itself: Inara files a loadout under a ship it knows.
        out.append(("setCommanderShipLoadout", {"shipType": _name(raw, "Ship"), "shipGameID": raw.get("ShipID"),
                                                "shipLoadout": ship_loadout(raw.get("Modules"), bool(raw.get("Hot")))}))
    elif event == "ShipyardNew":
        out.append(("addCommanderShip", {"shipType": _name(raw, "ShipType"), "shipGameID": raw.get("NewShipID")}))
    elif event in ("ShipyardSwap", "ShipyardBuy"):
        # The old ship: sold, or stored where the commander is.
        if raw.get("SellShipID") is not None:
            out.append(("delCommanderShip", {"shipType": _name(raw, "SellOldShip"), "shipGameID": raw.get("SellShipID")}))
        elif raw.get("StoreShipID") is not None:
            out.append(("setCommanderShip", {"shipType": _name(raw, "StoreOldShip"), "shipGameID": raw.get("StoreShipID"),
                                             **_here(raw, context)}))
        if event == "ShipyardSwap":
            out.append(("setCommanderShip", {"shipType": _name(raw, "ShipType"), "shipGameID": raw.get("ShipID"),
                                             "isCurrentShip": True}))
    elif event == "ShipyardSell" and raw.get("SellShipID") is not None:
        out.append(("delCommanderShip", {"shipType": _name(raw, "ShipType"), "shipGameID": raw.get("SellShipID")}))
    elif event == "SellShipOnRebuy" and (raw.get("SellShipId") is not None or raw.get("SellShipID") is not None):
        out.append(("delCommanderShip", {"shipType": _name(raw, "ShipType"),
                                         "shipGameID": raw.get("SellShipId", raw.get("SellShipID"))}))
    elif event == "SetUserShipName" and raw.get("ShipID") is not None:
        out.append(("setCommanderShip", {"shipType": _name(raw, "Ship"), "shipGameID": raw.get("ShipID"),
                                         "shipName": _name(raw, "UserShipName"), "shipIdent": _name(raw, "UserShipId")}))
    elif event == "ShipyardTransfer":
        out.append(("setCommanderShipTransfer", {
            "shipType": _name(raw, "ShipType"), "shipGameID": raw.get("ShipID"), **_here(raw, context),
            "transferTime": int(_number(raw.get("TransferTime")))}))
    elif event == "Materials":
        rows = [{"itemName": _name(item, "Name"), "itemCount": int(_number(item.get("Count")))}
                for group in MATERIAL_TYPES for item in (raw.get(group) or []) if isinstance(item, dict) and item.get("Name")]
        out.append(("setCommanderInventoryMaterials", rows))
    elif event == "MaterialCollected" and raw.get("Name"):
        out.append(("addCommanderInventoryMaterialsItem", {"itemName": _name(raw, "Name"), "itemCount": int(_number(raw.get("Count"), 1))}))
    elif event == "MaterialDiscarded" and raw.get("Name"):
        out.append(("delCommanderInventoryMaterialsItem", {"itemName": _name(raw, "Name"), "itemCount": int(_number(raw.get("Count"), 1))}))
    elif event == "MaterialTrade":
        paid, received = raw.get("Paid") or {}, raw.get("Received") or {}
        out += _materials("delCommanderInventoryMaterialsItem", [paid], "Material", "Quantity")
        out += _materials("addCommanderInventoryMaterialsItem", [received], "Material", "Quantity")
    elif event == "Synthesis":
        out += _materials("delCommanderInventoryMaterialsItem", raw.get("Materials"))
    elif event == "EngineerCraft":
        out += _materials("delCommanderInventoryMaterialsItem", raw.get("Ingredients"))
    elif event == "TechnologyBroker":
        out += _materials("delCommanderInventoryMaterialsItem", raw.get("Materials"))
    elif event == "ScientificResearch" and raw.get("Name"):
        out += _materials("delCommanderInventoryMaterialsItem", [raw])
    elif event == "EngineerContribution" and raw.get("Type") == "Materials" and raw.get("Material"):
        out += _materials("delCommanderInventoryMaterialsItem", [raw], "Material", "Quantity")
    elif event == "Cargo" and str(raw.get("Vessel") or "Ship") == "Ship" and isinstance(raw.get("Inventory"), list):
        rows = []
        for item in raw["Inventory"]:
            if not isinstance(item, dict) or not item.get("Name"):
                continue
            row = {"itemName": _name(item, "Name"), "itemCount": int(_number(item.get("Count")))}
            if item.get("Stolen"):
                row["isStolen"] = True
            if item.get("MissionID"):
                row["missionGameID"] = item["MissionID"]
            rows.append(row)
        # An empty list wouldn't clear the hold on Inara; a reset does.
        out.append(("setCommanderInventoryCargo", rows) if rows else ("resetCommanderInventory", {"itemType": "Commodity"}))
    elif event == "ShipLocker" and any(key in raw for key in LOCKER_TYPES):
        for group, kind in LOCKER_TYPES.items():
            rows = [{"itemName": _name(item, "Name"), "itemCount": int(_number(item.get("Count"))), "itemType": kind,
                     "itemLocation": "ShipLocker"}
                    for item in (raw.get(group) or []) if isinstance(item, dict) and item.get("Name")]
            if rows:
                out.append(("setCommanderInventory", rows))
            else:
                out.append(("resetCommanderInventory", {"itemType": kind, "itemLocation": "ShipLocker"}))
    elif event == "MissionAccepted":
        data = {"missionName": _name(raw, "Name"), "missionGameID": raw.get("MissionID"),
                "missionExpiry": raw.get("Expiry"), "influenceGain": _name(raw, "Influence"),
                "reputationGain": _name(raw, "Reputation"), "starsystemNameOrigin": context.get("system") or "",
                "stationNameOrigin": context.get("station") or "", "minorfactionNameOrigin": _name(raw, "Faction"),
                "starsystemNameTarget": _name(raw, "DestinationSystem"), "stationNameTarget": _name(raw, "DestinationStation"),
                "minorfactionNameTarget": _name(raw, "TargetFaction"), "commodityName": _name(raw, "Commodity"),
                "commodityCount": raw.get("Count"), "targetName": _name(raw, "Target"), "targetType": _name(raw, "TargetType"),
                "killCount": raw.get("KillCount"), "passengerType": _name(raw, "PassengerType"),
                "passengerCount": raw.get("PassengerCount"), "passengerIsVIP": raw.get("PassengerVIPs"),
                "passengerIsWanted": raw.get("PassengerWanted")}
        out.append(("addCommanderMission", {key: value for key, value in data.items() if value not in ("", None)}))
    elif event == "MissionCompleted":
        data = {"missionGameID": raw.get("MissionID"), "rewardCredits": raw.get("Reward"), "donationCredits": raw.get("Donated"),
                "rewardCommodities": [{"itemName": _name(row, "Name"), "itemCount": row.get("Count")}
                                      for row in raw.get("CommodityReward") or [] if isinstance(row, dict)] or None,
                "rewardMaterials": [{"itemName": _name(row, "Name"), "itemCount": row.get("Count")}
                                    for row in raw.get("MaterialsReward") or [] if isinstance(row, dict)] or None,
                "rewardPermits": [{"starsystemName": str(name)} for name in raw.get("PermitsAwarded") or [] if name] or None,
                "minorfactionEffects": _faction_effects(raw.get("FactionEffects")) or None}
        out.append(("setCommanderMissionCompleted", {key: value for key, value in data.items() if value is not None}))
        out += _materials("addCommanderInventoryMaterialsItem", raw.get("MaterialsReward"))
        out += [("addCommanderPermit", {"starsystemName": str(name)}) for name in raw.get("PermitsAwarded") or () if name]
    elif event == "MissionFailed":
        out.append(("setCommanderMissionFailed", {"missionGameID": raw.get("MissionID")}))
    elif event == "MissionAbandoned":
        out.append(("setCommanderMissionAbandoned", {"missionGameID": raw.get("MissionID")}))
    elif event == "Died":
        killers = [str(row.get("Name") or "") for row in raw.get("Killers") or [] if isinstance(row, dict)]
        data = {"starsystemName": context.get("system") or ""}
        if raw.get("KillerName"):
            data["opponentName"] = _name(raw, "KillerName")
        elif killers:
            data["wingOpponentNames"] = killers
        else:
            return out
        out.append(("addCommanderCombatDeath", data))
    elif event == "Interdicted":
        out.append(("addCommanderCombatInterdicted", {
            "starsystemName": context.get("system") or "", "opponentName": _opponent(raw, "Interdictor"),
            "isPlayer": bool(raw.get("IsPlayer")), "isSubmit": bool(raw.get("Submitted"))}))
    elif event == "Interdiction":
        out.append(("addCommanderCombatInterdiction", {
            "starsystemName": context.get("system") or "", "opponentName": _opponent(raw, "Interdicted"),
            "isPlayer": bool(raw.get("IsPlayer")), "isSuccess": bool(raw.get("Success"))}))
    elif event == "EscapeInterdiction":
        out.append(("addCommanderCombatInterdictionEscape", {
            "starsystemName": context.get("system") or "", "opponentName": _opponent(raw, "Interdictor"),
            "isPlayer": bool(raw.get("IsPlayer"))}))
    elif event == "PVPKill":
        out.append(("addCommanderCombatKill", {"starsystemName": context.get("system") or "", "opponentName": _name(raw, "Victim")}))
    elif event == "CommunityGoal" and isinstance(raw.get("CurrentGoals"), list):
        for goal in raw["CurrentGoals"]:
            if not isinstance(goal, dict) or goal.get("CGID") is None:
                continue
            tier = str(goal.get("TierReached") or "").replace("Tier", "").strip()
            details = {"communitygoalGameID": goal["CGID"], "communitygoalName": _name(goal, "Title"),
                       "starsystemName": _name(goal, "SystemName"), "stationName": _name(goal, "MarketName"),
                       "goalExpiry": goal.get("Expiry"), "tierReached": int(tier) if tier.isdigit() else None,
                       "topRankSize": goal.get("TopRankSize"), "isCompleted": bool(goal.get("IsComplete")),
                       "contributorsNum": goal.get("NumContributors"), "contributionsTotal": goal.get("CurrentTotal")}
            # Note: held back for now (5.6.5). Inara only keeps the goal itself
            # from apps it has approved for it and answers 204 "development
            # mode" otherwise; your own progress below is still sent.
            # out.append(("setCommunityGoal", {key: value for key, value in details.items() if value not in ("", None)}))
            progress = {"communitygoalGameID": goal["CGID"], "contribution": goal.get("PlayerContribution"),
                        "percentileBand": goal.get("PlayerPercentileBand"), "percentileBandReward": goal.get("Bonus"),
                        "isTopRank": bool(goal.get("PlayerInTopRank"))}
            out.append(("setCommanderCommunityGoalProgress", {key: value for key, value in progress.items() if value is not None}))
    elif event == "StoredModules" and isinstance(raw.get("Items"), list):
        out.append(("setCommanderStorageModules", stored_modules(raw)))
    elif event == "StoredShips":
        out += stored_ships(raw)
    elif event in ("SuitLoadout", "CreateSuitLoadout") and raw.get("LoadoutID") is not None:
        out.append(("setCommanderSuitLoadout", suit_loadout(raw)))
    elif event in ("LoadoutEquipModule", "LoadoutRemoveModule") and raw.get("LoadoutID") is not None:
        # The whole loadout as it now is, kept from its last full event.
        known = (context.get("suits") or {}).get(raw["LoadoutID"])
        if known:
            out.append(("updateCommanderSuitLoadout", known))
    elif event == "RenameSuitLoadout" and raw.get("LoadoutID") is not None:
        out.append(("updateCommanderSuitLoadout", {"loadoutGameID": raw["LoadoutID"], "loadoutName": _name(raw, "LoadoutName")}))
    elif event == "DeleteSuitLoadout" and raw.get("LoadoutID") is not None:
        out.append(("delCommanderSuitLoadout", {"loadoutGameID": raw["LoadoutID"]}))
    elif event == "Friends" and raw.get("Name"):
        # Note: on Inara this sends a friend request, so never for "Online".
        if raw.get("Status") == "Added":
            out.append(("addCommanderFriend", {"commanderName": _name(raw, "Name"), "gamePlatform": "pc"}))
        elif raw.get("Status") in ("Declined", "Lost"):
            out.append(("delCommanderFriend", {"commanderName": _name(raw, "Name"), "gamePlatform": "pc"}))
    return out


class InaraUploader:
    """Queues Inara events and sends them in polite batches on its own thread."""

    def __init__(self, config, version="", session=None, clock=time.time, queue_path=None, sent_path=None):
        self.config = config
        self.version = app_version(version)
        self._session = session or requests.Session()
        self._clock = clock
        self._lock = threading.Lock()
        self._queue = []
        self._sent_state = {}
        self._last_send = 0.0
        self._last_queued = 0.0
        self._stopped = False
        self._sending = False
        self._log = None
        self._blocked_key = None
        self.game_version = ""
        # Where the waiting events are kept over a restart (a callable: it follows the commander).
        self._queue_path = queue_path
        # What Inara has accepted, kept over a restart: {state key: signature}.
        self._sent_path = sent_path
        self._delivered = {}
        self._timer = None
        # Where the commander is and in what, from the journal itself.
        self.context = {}
        # Rank and Progress arrive apart; Inara takes them together.
        self._ranks = {}
        self.stats = {"sent": 0, "failed": 0, "last": None, "status": "idle", "detail": ""}

    def set_log_callback(self, callback):
        self._log = callback

    def _say(self, message, severity="INFO"):
        logging.info("Inara: %s", message)
        if callable(self._log):
            try:
                self._log("INARA", message, severity)
            except Exception:
                logging.debug("Inara log callback failed", exc_info=True)

    def credentials(self):
        key = str(self.config.get("inara_api_key") or "").strip()
        name = str(self.context.get("commander") or self.config.get("active_commander_name")
                   or self.config.get("inara_cmdr_name") or "").strip()
        return key, name

    def enabled(self):
        key, name = self.credentials()
        return bool(self.config.get("inara_upload_enabled")) and bool(key) and bool(name) \
            and key != self._blocked_key and live_game(self.game_version)

    def note_game_version(self, version):
        self.game_version = str(version or "")
        if not live_game(self.game_version):
            self.stats.update(status="paused", detail="Not the Live game: Inara takes no Legacy or beta data.")

    # -- queueing ------------------------------------------------------------
    def _follow(self, event, raw):
        """Keep track of the ship, system and station for later events."""
        if event in ("LoadGame", "Loadout") and raw.get("ShipID") is not None and raw.get("Ship"):
            if not str(raw["Ship"]).casefold().endswith(("suit_class1", "suit_class2", "suit_class3", "suit_class4", "suit_class5")):
                self.context.update(ship_type=str(raw["Ship"]).casefold(), ship_id=raw["ShipID"])
        elif event == "ShipyardSwap" or event == "ShipyardNew":
            self.context.update(ship_type=str(raw.get("ShipType") or "").casefold(),
                                ship_id=raw.get("ShipID") if event == "ShipyardSwap" else raw.get("NewShipID"))
        if raw.get("StarSystem") and event in ("Location", "FSDJump", "CarrierJump", "Docked"):
            self.context["system"] = str(raw["StarSystem"])
        if event in ("Docked", "Location"):
            self.context["station"] = str(raw.get("StationName") or "") if (event == "Docked" or raw.get("Docked")) else ""
        elif event == "Undocked":
            self.context["station"] = ""
        elif event in ("Commander", "LoadGame") and raw.get("Commander") and                 str(raw.get("Commander")) != str(self.context.get("commander") or raw.get("Commander")):
            # Another commander: their own state starts afresh.
            self._sent_state.clear()
            self._delivered.clear()
            self._ranks.clear()
        if event in ("Commander", "LoadGame") and raw.get("Commander"):
            self.context["commander"] = str(raw["Commander"])
        if event in ("Powerplay", "PowerplayRank") and raw.get("Rank") is not None:
            self.context["power_rank"] = int(_number(raw["Rank"]))
        elif event == "PowerplayLeave":
            self.context.pop("power_rank", None)
        self._follow_suits(event, raw)

    def _follow_suits(self, event, raw):
        """Suit loadouts as they are now, so a single slot changed can be
        sent as the whole loadout."""
        suits = self.context.setdefault("suits", {})
        loadout = raw.get("LoadoutID")
        if loadout is None:
            return
        if event in ("SuitLoadout", "CreateSuitLoadout"):
            suits[loadout] = suit_loadout(raw)
        elif event == "DeleteSuitLoadout":
            suits.pop(loadout, None)
        elif loadout in suits and event == "RenameSuitLoadout":
            suits[loadout] = {**suits[loadout], "loadoutName": _name(raw, "LoadoutName")}
        elif loadout in suits and event in ("LoadoutEquipModule", "LoadoutRemoveModule"):
            slots = [row for row in suits[loadout]["suitLoadout"] if row.get("slotName") != raw.get("SlotName")]
            if event == "LoadoutEquipModule":
                slots.append(_suit_module(raw))
            suits[loadout] = {**suits[loadout], "suitLoadout": slots}

    def observe(self, event, raw, context=None, startup=False):
        """One journal event. During a startup catch-up only the state of
        this session goes (credits, ranks, ship…), never old travel."""
        if not isinstance(raw, dict):
            return 0
        self._follow(event, raw)
        if event == "LoadGame" and not startup:
            # A new game session: Inara gets the whole state once, as it asks.
            self._sent_state.clear()
            with self._lock:
                self._delivered.clear()
        if not self.enabled():
            return 0
        context = {**self.context, **(context or {})}
        stamp = _stamp(raw)
        if not _recent(stamp):
            return 0
        queued = 0
        for name, data in map_event(event, raw, context):
            if startup and not name.startswith(("set", "reset")):
                continue
            if self._queue_event(name, data, stamp):
                queued += 1
        if event in FLUSH_AFTER and not startup:
            self.flush()
        return queued

    def _queue_event(self, name, data, stamp):
        if name == "setCommanderRankPilot":
            for row in data:
                self._ranks.setdefault(row["rankName"], {}).update(row)
            data = [dict(row) for row in self._ranks.values()]
        key = None
        if name.startswith(("set", "reset")):
            key = self._state_key(name, data)
            signature = self._signature(name, data)
            with self._lock:
                delivered = self._delivered.get(key)
            if signature == delivered:
                # Inara has this already: an older copy still waiting is out of date.
                self._sent_state[key] = signature
                with self._lock:
                    self._queue = [row for row in self._queue if self._row_key(row) != key]
                return False
            if self._sent_state.get(key) == signature:
                return False  # unchanged since it was queued
            self._sent_state[key] = signature
        with self._lock:
            if key is not None:
                # A newer copy of the same state replaces one still waiting.
                self._queue = [row for row in self._queue if self._row_key(row) != key]
            self._queue.append({"eventName": name, "eventTimestamp": stamp, "eventData": data})
            self._last_queued = self._clock()
        return True

    @staticmethod
    def _signature(name, data):
        return f"{name} {json.dumps(data, sort_keys=True, default=str)}"

    @classmethod
    def _row_key(cls, row):
        name = row.get("eventName") or ""
        return cls._state_key(name, row.get("eventData")) if name.startswith(("set", "reset")) else None

    @staticmethod
    def _state_key(name, data):
        """Which piece of state an event is: one per ship, goal, suit loadout,
        mission, inventory category…"""
        if name in ("setCommanderInventory", "setCommanderInventoryCargo", "resetCommanderInventory"):
            # A category's list and its reset share a slot: the later one stands.
            first = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
            kind = first.get("itemType") or ("Commodity" if name == "setCommanderInventoryCargo" else "")
            return f"inventory:{kind}:{first.get('itemLocation') or ''}"
        if name in ("setCommanderMissionCompleted", "setCommanderMissionFailed", "setCommanderMissionAbandoned"):
            return f"{name}:{(data or {}).get('missionGameID')}"
        if name in ("setCommanderShip", "setCommanderShipLoadout", "setCommanderShipTransfer"):
            return f"{name}:{(data or {}).get('shipGameID')}"
        if name in ("setCommunityGoal", "setCommanderCommunityGoalProgress"):
            return f"{name}:{(data or {}).get('communitygoalGameID')}"
        if name == "setCommanderSuitLoadout":
            return f"{name}:{(data or {}).get('loadoutGameID')}"
        if name == "setCommanderReputationMinorFaction":
            return f"{name}:{','.join(sorted(row['minorfactionName'] for row in data))}"
        return name

    def pending(self):
        with self._lock:
            return len(self._queue)

    def tick(self):
        """Send what's waiting once the minute between batches has passed."""
        if self.pending() and self._clock() - self._last_send >= MIN_GAP_S:
            self.flush()

    def start(self):
        """A quiet timer: whatever is waiting goes about once a minute, so an
        explorer who never docks still gets their jumps on Inara."""
        if self._timer is not None and self._timer.is_alive():
            return
        self._load_queue()
        self._load_sent()

        def run():
            while not self._stopped:
                time.sleep(TIMER_S)
                try:
                    self.tick()
                except Exception:
                    logging.debug("Inara timer tick failed", exc_info=True)
        self._timer = threading.Thread(target=run, name="inara-timer", daemon=True)
        self._timer.start()

    def _queue_file(self):
        try:
            return self._queue_path() if callable(self._queue_path) else self._queue_path
        except Exception:
            return None

    def _load_queue(self):
        path = self._queue_file()
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
        except (OSError, ValueError):
            return
        rows = [row for row in saved if isinstance(row, dict) and row.get("eventName") and _recent(row.get("eventTimestamp"))]             if isinstance(saved, list) else []
        if rows:
            with self._lock:
                self._queue[:0] = rows
            logging.info("Inara: %d event(s) left over from last time, sending soon", len(rows))
        try:
            os.remove(path)
        except OSError:
            pass

    def _sent_file(self):
        try:
            return self._sent_path() if callable(self._sent_path) else self._sent_path
        except Exception:
            return None

    def _load_sent(self):
        path = self._sent_file()
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
        except (OSError, ValueError):
            return
        state = saved.get("state") if isinstance(saved, dict) and saved.get("version") == SENT_VERSION else None
        if isinstance(state, dict):
            with self._lock:
                self._delivered = {str(key): str(value) for key, value in state.items()}
            # Unchanged since Inara took it: it doesn't go again after a restart.
            self._sent_state.update(self._delivered)

    def _save_sent(self):
        path = self._sent_file()
        if not path:
            return
        with self._lock:
            payload = {"version": SENT_VERSION, "state": dict(self._delivered)}
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temporary = f"{path}.tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            os.replace(temporary, path)
        except OSError:
            logging.debug("Inara: couldn't save what was sent", exc_info=True)

    # -- sending -------------------------------------------------------------
    def flush(self, force=False):
        if self._stopped or self._sending or not self.enabled():
            return False
        if not force and self._clock() - self._last_send < MIN_GAP_S:
            return False
        with self._lock:
            batch, self._queue = self._queue[:MAX_BATCH], self._queue[MAX_BATCH:]
        if not batch:
            return False
        self._sending = True
        self._last_send = self._clock()
        threading.Thread(target=self._send, args=(batch,), name="inara-send", daemon=True).start()
        return True

    def _header(self):
        key, name = self.credentials()
        header = {"appName": APP_NAME, "appVersion": self.version, "isBeingDeveloped": not getattr(sys, "frozen", False),
                  "APIkey": key, "commanderName": name}
        fid = str(self.config.get("active_commander_fid") or "").strip()
        if fid:
            header["commanderFrontierID"] = fid
        return header

    def request(self, events, timeout=30):
        """POST a batch; the decoded reply (raises on transport errors)."""
        for number, row in enumerate(events, 1):
            row.setdefault("eventCustomID", number)
        response = self._session.post(API_URL, json={"header": self._header(), "events": events}, timeout=timeout,
                                      headers={"User-Agent": f"{APP_NAME}/{self.version}"})
        response.raise_for_status()
        return response.json()

    def _send(self, batch):
        try:
            reply = self.request(batch)
            header = reply.get("header") or {}
            status = int(header.get("eventStatus") or 0)
            if status == 400:
                self._blocked_key = self.credentials()[0]
                self.stats.update(status="rejected", detail=str(header.get("eventStatusText") or "Inara rejected the key"))
                self._say(f"Inara rejected this API key: {self.stats['detail']}. Uploads stop until it changes.", "ERROR")
                return
            # Each reply matches its event by order: say which were refused
            # (400) or found nothing to change (204), and why.
            answers = list(zip(batch, reply.get("events") or []))
            failed = [(sent, row) for sent, row in answers if int((row or {}).get("eventStatus") or 0) == 400]
            soft = [(sent, row) for sent, row in answers if int((row or {}).get("eventStatus") or 0) == 204]
            refused = {id(sent) for sent, _row in failed}
            with self._lock:
                for sent in batch:
                    if sent["eventName"].startswith(("set", "reset")) and id(sent) not in refused:
                        self._delivered[self._row_key(sent)] = self._signature(sent["eventName"], sent["eventData"])
            self._save_sent()
            self.stats["sent"] += len(batch) - len(failed)
            self.stats["failed"] += len(failed)
            self.stats.update(last=time.time(), status="ok", detail="")
            self._say(f"Sent {len(batch) - len(failed)} event(s) to Inara", "INFO")
            for (sent, row), severity in [*((item, "WARN") for item in failed), *((item, "INFO") for item in soft)]:
                verdict = "refused" if severity == "WARN" else "flagged part of"
                self._say(f"Inara {verdict} {sent['eventName']}: {row.get('eventStatusText') or 'no reason given'}", severity)
        except Exception as exc:
            # Transport trouble: put the batch back for the next attempt.
            with self._lock:
                self._queue[:0] = batch
            self.stats.update(status="error", detail=str(exc))
            self._say(f"Couldn't reach Inara ({exc}); will try again later.", "WARN")
        finally:
            self._sending = False

    def test(self):
        """Check the key: (ok, words). Asks Inara for this commander's own profile."""
        key, name = self.credentials()
        if not key or not name:
            return False, "Enter your Inara API key and commander name first."
        try:
            reply = self.request([{"eventName": "getCommanderProfile",
                                   "eventTimestamp": _stamp({}), "eventData": {"searchName": name}}])
        except Exception as exc:
            return False, f"Couldn't reach Inara: {exc}"
        header = reply.get("header") or {}
        if int(header.get("eventStatus") or 0) == 400:
            return False, f"Inara refused: {header.get('eventStatusText') or 'the key was rejected'}"
        user = (header.get("eventData") or {}).get("userName") or name
        self._blocked_key = None
        return True, f"Inara accepted the key ({user})."

    def reset_block(self):
        self._blocked_key = None

    def stop(self):
        """App shutdown: what's still waiting is kept for next time rather
        than sent now (sending made closing Void Compass wait on Inara)."""
        self._stopped = True
        with self._lock:
            waiting, self._queue = list(self._queue), []
        path = self._queue_file()
        if not waiting or not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(waiting[-1000:], handle)
        except OSError as exc:
            logging.info("Inara: waiting events not kept (%s)", exc)
