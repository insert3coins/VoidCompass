"""HTML Engineering Companion model built from live VoidCompass profile state.

Reference catalogues and workflow semantics are adapted from ED Engineering
Companion (GPL-3.0).  Journal reduction and persistence remain owned by the
VoidCompass Python runtime.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re
import sys
from typing import Any


ROLLS_PER_GRADE = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


def _resource_root() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "data" / "engineering_companion"


@lru_cache(maxsize=None)
def _load(name: str) -> Any:
    try:
        return json.loads((_resource_root() / name).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return None


@lru_cache(maxsize=1)
def reference_catalogues() -> dict[str, Any]:
    return {
        "blueprints": _load("blueprints.json") or [],
        "experimentals": _load("experimental_effects.json") or [],
        "materials": (_load("engineering_materials.json") or {}).get("materials", []),
        "unlocks": (_load("engineer_unlocks.json") or {}).get("engineers", {}),
        "entries": _load("entryData.json") or [],
        "module_display": (_load("module_display.json") or {}).get("modules", {}),
        "ships": _load("ships.json") or [],
        "tech_brokers": _load("tech_broker_unlocks.json") or {},
    }


def key(value: Any) -> str:
    text = str(value or "").strip().strip("$;")
    text = re.sub(r"_(name|name_localised)$", "", text, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", text.casefold())


@lru_cache(maxsize=1)
def _material_index() -> dict[str, dict]:
    result = {}
    entries = {
        key(row.get("FormattedName") or row.get("Name")): row
        for row in reference_catalogues()["entries"] if isinstance(row, dict)
    }
    for source in reference_catalogues()["materials"]:
        if not isinstance(source, dict):
            continue
        row = dict(source)
        entry = entries.get(key(row.get("canonical_key") or row.get("name")), {})
        row["origins"] = list(row.get("origin_details") or entry.get("OriginDetails") or [])
        aliases = {
            key(row.get("name")), key(row.get("journal_name")),
            key(row.get("canonical_key")), key(entry.get("FormattedName")),
        }
        for alias in aliases:
            if alias:
                result[alias] = row
    return result


def material_record(value: Any) -> dict:
    normalised = key(value)
    return _material_index().get(normalised, {
        "name": str(value or "Unknown material"), "canonical_key": normalised,
        "journal_name": normalised, "category": "Unknown", "grade": 0,
        "max_capacity": 0, "origin_details": [], "origins": [], "used_in": [],
    })


@lru_cache(maxsize=1)
def blueprint_groups() -> dict[tuple[str, str], list[dict]]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in reference_catalogues()["blueprints"]:
        if not isinstance(row, dict) or row.get("Grade") is None:
            continue
        groups[(str(row.get("Type") or ""), str(row.get("Name") or ""))].append(row)
    for rows in groups.values():
        rows.sort(key=lambda item: int(item.get("Grade") or 0))
    return dict(groups)


@lru_cache(maxsize=1)
def experimental_groups() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in reference_catalogues()["experimentals"]:
        if not isinstance(row, dict):
            continue
        for module_type in row.get("ModuleTypes") or [row.get("Type")]:
            if module_type:
                groups[str(module_type)].append(row)
    return dict(groups)


def _ingredient_rows(items: Any, multiplier: int = 1) -> list[dict]:
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        info = material_record(item.get("Name_Localised") or item.get("Name"))
        rows.append({
            "key": key(info.get("canonical_key") or info.get("journal_name") or item.get("Name")),
            "name": str(info.get("name") or item.get("Name_Localised") or item.get("Name") or "Unknown"),
            "amount": max(0, int(item.get("Size") or item.get("Count") or 0)) * multiplier,
            "category": str(info.get("category") or "Unknown"),
            "grade": int(info.get("grade") or 0),
        })
    return rows


def _inventory(state: dict) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for category in ("raw", "manufactured", "encoded"):
        for symbol, value in (state.get(category) or {}).items():
            count = value.get("count") if isinstance(value, dict) else value
            result[key(symbol)] += max(0, int(count or 0))
    return dict(result)


def _module_identity(value: Any) -> str:
    return str(value or "").strip().strip("$;")


@lru_cache(maxsize=None)
def _module_display(item: str) -> tuple[str, str]:
    catalogue = reference_catalogues()["module_display"]
    candidates = [item, item.casefold(), item.casefold().replace("$", "").replace(";", "")]
    for candidate in candidates:
        row = catalogue.get(candidate)
        if isinstance(row, list) and row:
            return str(row[0]).title(), str(row[1] if len(row) > 1 else "")
    raw = _module_identity(item)
    readable = re.sub(r"^(int|hpt)_?", "", raw, flags=re.I)
    readable = re.sub(r"[_-]+", " ", readable)
    return readable.title() or "Unknown module", ""


def module_matches_type(module_id: Any, module_type: Any) -> bool:
    display, _rating = _module_display(_module_identity(module_id))
    left, right = key(display), key(module_type)
    aliases = {
        "frameshiftdrive": ("hyperdrive", "frameshiftdrive"),
        "thrusters": ("engine", "thrusters"),
        "powerplant": ("powerplant",), "powerdistributor": ("powerdistributor",),
        "surfacescanner": ("detailedsurfacescanner", "surfacescanner"),
        "multicannon": ("multicannon",), "fragmentcannon": ("slugshot", "fragmentcannon"),
        "railgun": ("railgun",), "shieldgenerator": ("shieldgenerator",),
        "shieldbooster": ("shieldbooster",), "armour": ("armour",),
    }
    raw = key(module_id)
    return left == right or right in left or left in right or any(x in raw for x in aliases.get(right, (right,)))


def _slot_category(slot: str) -> str:
    value = slot.casefold()
    if value == "armour" or any(x in value for x in ("powerplant", "mainengines", "frameshiftdrive", "lifesupport", "powerdistributor", "radar")):
        return "Core Internals"
    if "hardpoint" in value:
        return "Hardpoints"
    if "utility" in value:
        return "Utility Mounts"
    if value == "fueltank":
        return "Fuel Tank"
    return "Optional Internals"


def loadout_slots(loadout: dict) -> list[dict]:
    rows = []
    for index, source in enumerate(loadout.get("Modules") or []):
        if not isinstance(source, dict):
            continue
        slot = str(source.get("Slot") or f"Slot{index + 1:02d}")
        item = _module_identity(source.get("Item"))
        planned_type = str(source.get("PlannedModuleType") or "")
        display, rating = _module_display(item)
        if planned_type:
            display = planned_type
        slot_size = int(source.get("SlotSize") or 0)
        if source.get("PlannedEmpty"):
            display = f"Empty class {slot_size} slot" if slot_size else "Empty slot"
        if slot_size > 0:
            rating = f"{slot_size}{rating[-1:] if rating else ''}"
        engineering = source.get("Engineering") if isinstance(source.get("Engineering"), dict) else {}
        rows.append({
            "slot": slot, "category": _slot_category(slot), "moduleId": item,
            "name": display, "rating": rating, "enabled": bool(source.get("On", True)),
            "priority": int(source.get("Priority") or 0),
            "engineeringBlueprint": str(engineering.get("BlueprintName") or ""),
            "engineeringGrade": int(engineering.get("Level") or 0),
            "engineeringQuality": float(engineering.get("Quality") or 0),
            "engineeringQualityKnown": engineering.get("Quality") is not None,
            "experimentalEffect": str(engineering.get("ExperimentalEffect_Localised") or engineering.get("ExperimentalEffect") or ""),
            "planned": bool(loadout.get("Planned")),
            "empty": bool(source.get("PlannedEmpty")),
            "assigned": bool(source.get("PlannedAssigned")),
            "size": slot_size,
            "engineerable": source.get("Engineerable") is not False,
            "allowedTypes": list(source.get("AllowedTypes") or []),
        })
    order = {name: index for index, name in enumerate(("Core Internals", "Fuel Tank", "Optional Internals", "Hardpoints", "Utility Mounts"))}
    rows.sort(key=lambda row: (order.get(row["category"], 99), row["slot"]))
    return rows


@lru_cache(maxsize=None)
def _ship_asset(symbol: str) -> str:
    wanted = key(symbol)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for path in (base / "web" / "dashboard" / "assets" / "engineering" / "ships").glob("*.svg"):
        if key(path.stem) == wanted:
            return f"assets/engineering/ships/{path.name}"
    return ""


@lru_cache(maxsize=None)
def _ship_catalog_row(symbol: str) -> dict:
    wanted = key(symbol)
    return next((row for row in reference_catalogues()["ships"] if key(row.get("symbol")) == wanted or key(row.get("name")) == wanted), {})


@lru_cache(maxsize=1)
def ship_catalogue() -> list[dict]:
    return [{
        "symbol": str(row.get("symbol") or ""),
        "name": str(row.get("name") or row.get("symbol") or "Unknown ship"),
        "manufacturer": str(row.get("manufacturer") or ""),
        "size": str(row.get("size") or ""),
        "asset": _ship_asset(str(row.get("symbol") or "")),
    } for row in reference_catalogues()["ships"] if isinstance(row, dict)]


_PLANNED_CORE_SLOTS = {
    "powerPlant": ("PowerPlant", "Power Plant"),
    "thrusters": ("MainEngines", "Thrusters"),
    "frameShiftDrive": ("FrameShiftDrive", "Frame Shift Drive"),
    "lifeSupport": ("LifeSupport", "Life Support"),
    "powerDistributor": ("PowerDistributor", "Power Distributor"),
    "sensors": ("Radar", "Sensors"),
    "fuelTank": ("FuelTank", "Fuel Tank"),
}

_PLANNED_HARDPOINT_TYPES = (
    "Beam Laser", "Burst Laser", "Cannon", "Fragment Cannon", "Mine Launcher",
    "Missile Rack", "Multi-cannon", "Plasma Accelerator", "Pulse Laser",
    "Rail Gun", "Torpedo Pylon", "Weapon",
)
_PLANNED_UTILITY_TYPES = (
    "Chaff Launcher", "Electronic Countermeasure", "Heat Sink Launcher",
    "Kill Warrant Scanner", "Manifest Scanner", "Point Defence",
    "Shield Booster", "Wake Scanner",
)
_PLANNED_OPTIONAL_TYPES = (
    "Auto Field-Maintenance Unit", "Collector Limpet Controller",
    "Frame Shift Drive Interdictor", "Fuel Scoop", "Fuel Transfer Limpet Controller",
    "Hatch Breaker Limpet Controller", "Hull Reinforcement Package",
    "Prospector Limpet Controller", "Refinery", "Shield Cell Bank",
    "Shield Generator", "Surface Scanner",
)


def _planned_build_loadout(build: dict) -> dict:
    symbol = str(build.get("ship_symbol") or build.get("symbol") or "")
    info = _ship_catalog_row(symbol)
    assignments = build.get("slots") if isinstance(build.get("slots"), dict) else {}
    modules = []

    def add(slot: str, size: Any, default_type: str = "", *, allowed_types=(), engineerable=True):
        assignment = assignments.get(slot)
        if isinstance(assignment, str):
            assignment = {"module_type": assignment}
        assignment = assignment if isinstance(assignment, dict) else {}
        module_type = str(assignment.get("module_type") or default_type)
        modules.append({
            "Slot": slot, "Item": "", "PlannedModuleType": module_type,
            "PlannedEmpty": not bool(module_type), "SlotSize": int(size or 0),
            "PlannedAssigned": bool(assignment.get("module_type")),
            "AllowedTypes": list(allowed_types), "Engineerable": engineerable,
            "On": True, "Priority": 1,
        })

    add("Armour", 0, "Armour", allowed_types=("Armour",))
    for source, (slot, module_type) in _PLANNED_CORE_SLOTS.items():
        add(
            slot, (info.get("core") or {}).get(source), module_type,
            allowed_types=(module_type,), engineerable=module_type != "Fuel Tank",
        )
    size_names = {1: "Small", 2: "Medium", 3: "Large", 4: "Huge"}
    hardpoint_counts: dict[int, int] = defaultdict(int)
    for row in info.get("hardpoints") or []:
        size = int((row or {}).get("size") or 0)
        hardpoint_counts[size] += 1
        add(
            f"{size_names.get(size, 'Class')}Hardpoint{hardpoint_counts[size]}", size,
            allowed_types=_PLANNED_HARDPOINT_TYPES,
        )
    for index in range(int(info.get("utility") or 0)):
        add(f"UtilityMount{index + 1}", 0, allowed_types=_PLANNED_UTILITY_TYPES)
    for index, row in enumerate(info.get("optional") or []):
        restricted = str((row or {}).get("restriction") or "")
        add(
            str((row or {}).get("name") or f"OptionalInternal{index + 1:02d}"),
            (row or {}).get("size"), allowed_types=_PLANNED_OPTIONAL_TYPES,
            engineerable=restricted != "planetaryApproachSuite",
        )
    return {
        "ShipID": str(build.get("id") or ""), "Ship": symbol,
        "ShipName": str(build.get("name") or f"{info.get('name') or symbol} build"),
        "ShipIdent": "PLANNED", "Planned": True, "Modules": modules,
    }


def fleet_rows(companion: dict, selected_ship_id: str = "", planned_builds: Any = None) -> tuple[list[dict], dict]:
    loadouts = dict(companion.get("fleet_loadouts") or {})
    current = companion.get("loadout") if isinstance(companion.get("loadout"), dict) else {}
    if current.get("ShipID") is not None:
        loadouts[str(current.get("ShipID"))] = current
    stored = companion.get("stored_ships") if isinstance(companion.get("stored_ships"), dict) else {}
    fleet: dict[str, dict] = {}
    planned_loadouts: dict[str, dict] = {}
    for location_key in ("here", "remote"):
        for row in stored.get(location_key) or []:
            if not isinstance(row, dict) or row.get("ship_id") is None:
                continue
            ship_id = str(row.get("ship_id"))
            fleet[ship_id] = {
                "id": ship_id, "symbol": str(row.get("type_symbol") or row.get("type") or ""),
                "name": str(row.get("name") or row.get("type") or "Unknown ship"),
                "location": str(row.get("system") or stored.get("system") or "Stored"),
                "current": False, "planned": False,
            }
    for ship_id, loadout in loadouts.items():
        if not isinstance(loadout, dict):
            continue
        symbol = str(loadout.get("Ship") or loadout.get("ShipType") or "")
        fleet[str(ship_id)] = {
            **fleet.get(str(ship_id), {}), "id": str(ship_id), "symbol": symbol,
            "name": str(loadout.get("ShipName") or loadout.get("Ship_Localised") or symbol or "Unknown ship"),
            "ident": str(loadout.get("ShipIdent") or ""), "location": "Current" if loadout is current else fleet.get(str(ship_id), {}).get("location", "Observed"),
            "current": loadout is current, "planned": False, "loadout": loadout,
        }
    for source in planned_builds or []:
        if not isinstance(source, dict) or not source.get("id") or not source.get("ship_symbol"):
            continue
        ship_id = str(source["id"])
        loadout = _planned_build_loadout(source)
        planned_loadouts[ship_id] = loadout
        fleet[ship_id] = {
            "id": ship_id, "symbol": str(source.get("ship_symbol") or ""),
            "name": str(source.get("name") or "Planned build"),
            "location": "Engineering workshop", "current": False,
            "planned": True, "loadout": loadout,
        }
    rows = []
    for ship_id, row in fleet.items():
        loadout = loadouts.get(ship_id) if isinstance(loadouts.get(ship_id), dict) else row.get("loadout")
        symbol = str(row.get("symbol") or (loadout or {}).get("Ship") or "")
        info = _ship_catalog_row(symbol)
        label = str(row.get("name") or info.get("name") or symbol or f"Ship {ship_id}")
        rows.append({
            "id": ship_id, "label": label, "symbol": symbol,
            "type": str(info.get("name") or symbol), "manufacturer": str(info.get("manufacturer") or ""),
            "size": str(info.get("size") or ""), "location": str(row.get("location") or ""),
            "ident": str(row.get("ident") or ""), "current": bool(row.get("current")),
            "planned": bool(row.get("planned")),
            "observed": bool(loadout and loadout.get("Modules") and not row.get("planned")), "asset": _ship_asset(symbol),
        })
    rows.sort(key=lambda row: (not row["current"], row["label"].casefold(), row["id"]))
    if not rows and current:
        rows.append({"id": str(current.get("ShipID") or "current"), "label": str(current.get("ShipName") or current.get("Ship") or "Current ship"), "symbol": str(current.get("Ship") or ""), "current": True, "observed": True, "asset": _ship_asset(str(current.get("Ship") or ""))})
    selected = next((row for row in rows if row["id"] == str(selected_ship_id)), None)
    selected = selected or next((row for row in rows if row.get("current")), None) or (rows[0] if rows else {})
    selected_loadout = planned_loadouts.get(str(selected.get("id"))) or loadouts.get(str(selected.get("id"))) or (current if selected.get("current") else {})
    return rows, dict(selected_loadout or {})


def _plan_requirements(pin: dict) -> list[dict]:
    module_type = str(pin.get("type") or pin.get("module_type") or "")
    name = str(pin.get("name") or "")
    target = max(1, min(5, int(pin.get("target_grade", pin.get("grade", 5)) or 5)))
    current = max(0, min(target, int(pin.get("current_grade") or 0)))
    quantity = max(1, int(pin.get("quantity") or 1))
    groups = blueprint_groups()
    group = groups.get((module_type, name))
    if group is None:
        matches = [(pair, rows) for pair, rows in groups.items() if key(pair[1]) == key(name)]
        if len(matches) == 1:
            (module_type, name), group = matches[0]
    result: dict[str, dict] = {}
    if not group:
        # Preserve pre-5.4.3 VoidCompass pins while new plans use the complete
        # EDEC type/name catalogue and physical-slot identity.
        try:
            import engineering_data
            legacy = engineering_data.requirements(
                name, target, current_grade=current, quantity=quantity,
            )
        except (ImportError, KeyError, TypeError, ValueError):
            legacy = {}
        for symbol, amount in legacy.items():
            info = material_record(symbol)
            material_key = key(info.get("canonical_key") or info.get("journal_name") or symbol)
            result[material_key] = {
                "key": material_key, "name": str(info.get("name") or symbol),
                "amount": int(amount), "category": str(info.get("category") or "Unknown"),
                "grade": int(info.get("grade") or 0),
            }
    for record in group or []:
        grade = int(record.get("Grade") or 0)
        if not current < grade <= target:
            continue
        for item in _ingredient_rows(record.get("Ingredients"), ROLLS_PER_GRADE.get(grade, grade) * quantity):
            bucket = result.setdefault(item["key"], dict(item, amount=0))
            bucket["amount"] += item["amount"]
    experimental = str(pin.get("experimental") or "")
    if experimental:
        effect = next((row for row in experimental_groups().get(module_type, []) if key(row.get("Name")) == key(experimental)), None)
        for item in _ingredient_rows((effect or {}).get("Ingredients"), quantity):
            bucket = result.setdefault(item["key"], dict(item, amount=0))
            bucket["amount"] += item["amount"]
    return sorted(result.values(), key=lambda row: (row["category"], row["grade"], row["name"]))


@lru_cache(maxsize=1)
def _blueprint_catalogue() -> list[dict]:
    result = []
    for (module_type, name), rows in sorted(blueprint_groups().items()):
        last = rows[-1]
        result.append({
            "type": module_type, "name": name, "max_grade": int(last.get("Grade") or 1),
            "engineers": sorted({str(engineer) for row in rows for engineer in row.get("Engineers") or [] if engineer and not str(engineer).startswith("@")}),
            "ingredients": _ingredient_rows(last.get("Ingredients")),
            "effects": [{"property": str(item.get("Property") or ""), "effect": str(item.get("Effect") or ""), "good": bool(item.get("IsGood"))} for item in last.get("Effects") or []],
        })
    return result


@lru_cache(maxsize=1)
def _experimental_catalogue() -> list[dict]:
    return [{
        "type": str(row.get("Type") or ""), "name": str(row.get("Name") or ""),
        "module_types": list(row.get("ModuleTypes") or []),
        "engineers": [str(name) for name in row.get("Engineers") or [] if name and not str(name).startswith("@")],
        "ingredients": _ingredient_rows(row.get("Ingredients")),
        "effects": [{"property": str(item.get("Property") or ""), "effect": str(item.get("Effect") or ""), "good": bool(item.get("IsGood"))} for item in row.get("Effects") or []],
    } for row in reference_catalogues()["experimentals"] if isinstance(row, dict)]


def _portrait(name: str) -> str:
    aliases = {"todtheblastermcquinn": "tod_mcquinn"}
    stem = aliases.get(key(name), re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_"))
    return f"assets/engineering/engineers/{stem}.jpg"


@lru_cache(maxsize=1)
def _engineer_offers() -> dict[str, list[dict]]:
    offers: dict[str, list[dict]] = defaultdict(list)
    for (module_type, blueprint), rows in blueprint_groups().items():
        grades: dict[str, int] = defaultdict(int)
        for row in rows:
            grade = int(row.get("Grade") or 0)
            for name in row.get("Engineers") or []:
                if name and not str(name).startswith("@"):
                    grades[str(name)] = max(grades[str(name)], grade)
        for name, grade in grades.items():
            offers[key(name)].append({"type": module_type, "name": blueprint, "grade": grade})
    return {
        engineer: sorted(rows, key=lambda row: (row["type"], row["name"]))
        for engineer, rows in offers.items()
    }


def _engineers(state: dict) -> list[dict]:
    progress_index = {key(name): row if isinstance(row, dict) else {"rank": row} for name, row in (state.get("engineers") or {}).items()}
    offers = _engineer_offers()
    result = []
    for name, unlock in reference_catalogues()["unlocks"].items():
        progress = progress_index.get(key(name), {})
        status = str(progress.get("progress") or progress.get("Progress") or "Unknown")
        rank = int(progress.get("rank") or progress.get("Rank") or 0)
        status_key = status.casefold()
        steps = [
            {"label": "Discovery", "detail": str(unlock.get("discovery") or ""), "done": status_key in {"known", "invited", "unlocked"}},
            {"label": "Invitation", "detail": str(unlock.get("meeting") or ""), "done": status_key in {"invited", "unlocked"}},
            {"label": "Access", "detail": str(unlock.get("unlock") or ""), "done": status_key == "unlocked"},
        ]
        result.append({
            "name": name, "system": str(unlock.get("system") or ""), "station": str(unlock.get("station") or ""),
            "prerequisite": str(unlock.get("prerequisite") or ""), "progress": status, "rank": rank,
            "portrait": _portrait(name), "steps": steps, "offers": offers.get(key(name), []),
            "discipline": str(unlock.get("discipline") or "ship"),
        })
    return sorted(result, key=lambda row: (row["progress"].casefold() != "unlocked", row["name"]))


@lru_cache(maxsize=1)
def _tech_broker_recipes() -> dict[tuple[str, str], dict[str, dict]]:
    recipes: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for material in reference_catalogues()["materials"]:
        if not isinstance(material, dict):
            continue
        material_key = key(material.get("canonical_key") or material.get("name"))
        for use in material.get("used_in") or []:
            if "@Technology" not in (use.get("engineers") or []):
                continue
            recipe_key = (str(use.get("type") or "Technology"), str(use.get("blueprint") or "Unlock"))
            recipes[recipe_key][material_key] = {
                "key": material_key, "name": str(material.get("name") or material_key),
                "need": int(use.get("amount") or 0),
                "category": str(material.get("category") or "Material"),
            }
    return dict(recipes)


def _tech_brokers(inventory: dict[str, int]) -> list[dict]:
    result = []
    for (broker, name), materials in sorted(_tech_broker_recipes().items()):
        rows = [{**row, "have": inventory.get(material_key, 0)} for material_key, row in materials.items()]
        result.append({
            "broker": broker, "name": name, "materials": rows,
            "ready": bool(rows) and all(row["have"] >= row["need"] for row in rows),
        })
    return result


def nearest_material_traders(position: Any, current_system: str = "", limit_per_category: int = 5) -> list[dict]:
    try:
        point = [float(value) for value in position]
        if len(point) != 3:
            raise ValueError
    except (TypeError, ValueError):
        point = []
    return _nearest_material_traders_cached(tuple(point), str(current_system or ""), int(limit_per_category))


@lru_cache(maxsize=32)
def _nearest_material_traders_cached(point: tuple[float, ...], current_system: str, limit_per_category: int) -> list[dict]:
    rows = []
    catalogue = _load("material_trader_catalog.json") or {}
    for station in catalogue.get("stations", []) if isinstance(catalogue, dict) else []:
        if not isinstance(station, dict):
            continue
        coordinates = station.get("coordinates")
        distance = None
        if point and isinstance(coordinates, list) and len(coordinates) == 3:
            try:
                distance = sum((float(coordinates[i]) - point[i]) ** 2 for i in range(3)) ** 0.5
            except (TypeError, ValueError):
                distance = None
        rows.append({
            "category": str(station.get("category") or ""), "system": str(station.get("system") or ""),
            "station": str(station.get("station") or ""), "distance": round(distance, 1) if distance is not None else None,
            "distance_ls": station.get("distance_ls"), "pad": str(station.get("pad") or ""),
            "verified": str(station.get("verified") or ""), "current": str(station.get("system") or "").casefold() == str(current_system or "").casefold(),
        })
    chosen = []
    for category in ("Raw", "Manufactured", "Encoded"):
        matching = [row for row in rows if row["category"] == category]
        matching.sort(key=lambda row: (not row["current"], row["distance"] is None, row["distance"] or 0, row["distance_ls"] or 0))
        chosen.extend(matching[:limit_per_category])
    return chosen


@lru_cache(maxsize=1)
def _material_catalogue_rows() -> list[dict]:
    return [{
        "key": material_key,
        "name": str(info.get("name") or material_key),
        "category": str(info.get("category") or "Unknown"),
        "grade": int(info.get("grade") or 0),
        "rarity": str(info.get("rarity") or ""),
        "capacity": int(info.get("max_capacity") or 0),
        "tradeable": str(info.get("category")) in {"Raw", "Manufactured", "Encoded"},
        "origins": list(info.get("origin_details") or []),
        "usage_count": int(info.get("blueprint_usage_count") or 0),
    } for material_key, info in {
        key(row.get("canonical_key") or row.get("name")): row
        for row in reference_catalogues()["materials"] if isinstance(row, dict)
    }.items()]


def build_workspace(state: dict, companion: dict, *, selected_ship_id: str = "", tool_state: dict | None = None,
                    current_system: str = "", current_coords: Any = None) -> dict:
    state = state if isinstance(state, dict) else {}
    companion = companion if isinstance(companion, dict) else {}
    inventory = _inventory(state)
    fleet, loadout = fleet_rows(
        companion, selected_ship_id or state.get("engineering_selected_ship"),
        state.get("engineering_builds") or [],
    )
    selected_id = next((row["id"] for row in fleet if row.get("id") == str(selected_ship_id or state.get("engineering_selected_ship"))), "")
    if not selected_id:
        selected_id = next((row["id"] for row in fleet if row.get("current")), fleet[0]["id"] if fleet else "")
    slots = loadout_slots(loadout)
    pins = []
    required: dict[str, dict] = {}
    for index, source in enumerate(state.get("pinned_blueprints") or []):
        if not isinstance(source, dict):
            continue
        pin = dict(source)
        pin["id"] = str(pin.get("id") or f"plan-{index}")
        pin["name"] = str(pin.get("name") or "")
        pin["type"] = str(pin.get("type") or pin.get("module_type") or "")
        pin["grade"] = max(1, min(5, int(pin.get("target_grade", pin.get("grade", 5)) or 5)))
        pin["current_grade"] = max(0, min(pin["grade"], int(pin.get("current_grade") or 0)))
        pin["quantity"] = max(1, int(pin.get("quantity") or 1))
        ingredients = _plan_requirements(pin)
        pin["materials"] = []
        for item in ingredients:
            have = inventory.get(item["key"], 0)
            enriched = {**item, "have": have, "missing": max(0, item["amount"] - have)}
            pin["materials"].append(enriched)
            bucket = required.setdefault(item["key"], {**item, "need": 0})
            bucket["need"] += item["amount"]
        pin["craftable"] = bool(ingredients) and all(item["missing"] == 0 for item in pin["materials"])
        pins.append(pin)
    material_rows = []
    for base_row in _material_catalogue_rows():
        material_key = base_row["key"]
        need = int(required.get(material_key, {}).get("need", 0))
        have = inventory.get(material_key, 0)
        material_rows.append({
            **base_row,
            "have": have, "need": need, "missing": max(0, need - have), "surplus": max(0, have - need),
        })
    missing_total = sum(max(0, row["need"] - inventory.get(material_key, 0)) for material_key, row in required.items())
    ship_info = next((row for row in fleet if row.get("id") == selected_id), {})
    stats = {
        "jump_range": loadout.get("MaxJumpRange"), "unladen_mass": loadout.get("UnladenMass"),
        "cargo": loadout.get("CargoCapacity"), "fuel": (loadout.get("FuelCapacity") or {}).get("Main") if isinstance(loadout.get("FuelCapacity"), dict) else loadout.get("FuelCapacity"),
        "engineerable": sum(bool(
            row.get("engineerable") and (
                row.get("engineeringBlueprint")
                or row.get("allowedTypes")
                or any(module_matches_type(row.get("moduleId"), module_type) for module_type, _name in blueprint_groups())
            )
        ) for row in slots),
    }
    return {
        "source": "ED Engineering Companion · adapted for VoidCompass HTML",
        "fleet": fleet, "selected_ship_id": selected_id, "ship": ship_info, "ship_stats": stats,
        "ship_catalogue": ship_catalogue(),
        "slots": slots, "pins": pins, "catalogue": _blueprint_catalogue(),
        "experimentals": _experimental_catalogue(), "materials": material_rows,
        "wishlist": {"plans": len(pins), "required": sum(row["need"] for row in required.values()), "missing": missing_total, "ready": sum(bool(row["craftable"]) for row in pins)},
        "engineers": _engineers(state), "tech_brokers": _tech_brokers(inventory),
        "tech_broker_guidance": reference_catalogues()["tech_brokers"],
        "material_traders": nearest_material_traders(current_coords, current_system),
        "tool": dict(tool_state or {}), "last_updated": state.get("last_updated"),
    }


def export_loadout(companion: dict, selected_ship_id: str) -> str:
    _fleet, loadout = fleet_rows(companion or {}, selected_ship_id)
    if not loadout:
        return ""
    payload = {
        "format": "VOIDCOMPASS_ENGINEERING_LOADOUT_V1", "status": "COMPLETE",
        "Ship": loadout.get("Ship"),
        "Modules": loadout.get("Modules") or [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
