"""Offline ship outfitting, analysis, and EDSY/SLEF interchange.

The planner owns profile-local build documents while the bundled catalogue
contains Elite Dangerous game data.  Calculations are implemented locally so
the dashboard remains useful without an account or network connection.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import lru_cache
import json
import math
import re
import time
from typing import Any
from urllib.parse import unquote, urlparse

from voidcompass.core.paths import resource_path
from voidcompass.core.version import APP_VERSION


CORE_NAMES = (
    "Bulkheads", "Power Plant", "Thrusters", "Frame Shift Drive",
    "Life Support", "Power Distributor", "Sensors", "Fuel Tank",
)
GROUP_LABELS = {
    "ship": "Ship Systems", "hardpoint": "Hardpoints",
    "utility": "Utility Mounts", "component": "Core Internals",
    "military": "Military Internals", "internal": "Optional Internals",
}
GROUP_ORDER = ("ship", "hardpoint", "utility", "component", "military", "internal")
HASH_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-"
HASH_VALUES = {character: index for index, character in enumerate(HASH_ALPHABET)}
HASH_TEXT_PUNCTUATION = " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
MAX_BUILDS = 100
MAX_POWER_PRIORITY = 5
SUPPORTED_HASH_MIN_VERSION = 15
SUPPORTED_HASH_MAX_VERSION = 19


class BuildPlannerError(ValueError):
    """Actionable input or outfitting failure for the dashboard."""


def stored_builds(state: dict) -> list[dict]:
    """Return only valid profile builds, normalized for editing."""
    rows = []
    for source in (state or {}).get("build_planner_builds") or []:
        try:
            rows.append(normalize_build(source))
        except BuildPlannerError:
            continue
    return rows


def find_build(state: dict, build_id: Any) -> dict | None:
    wanted = str(build_id or "")
    return next((row for row in stored_builds(state) if row["id"] == wanted), None)


def clone_build(build: dict, name: str = "") -> dict:
    result = normalize_build(build)
    result["id"] = f"build:{time.time_ns()}"
    result["name"] = str(name or f"{result['name']} copy")[:80]
    result["created"] = result["updated"] = time.time()
    result["source"] = "VoidCompass build clone"
    return result


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


@lru_cache(maxsize=1)
def catalogue() -> dict:
    path = resource_path("data", "build_planner", "catalogue.json")
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    raw["ships"] = {int(key): value for key, value in raw.get("ships", {}).items()}
    raw["modules"] = {int(key): value for key, value in raw.get("modules", {}).items()}
    raw["attributeMap"] = {
        str(row.get("attr")): row for row in raw.get("attributes", []) if row.get("attr")
    }
    raw["shipByName"] = {}
    for ship_id, ship in raw["ships"].items():
        for value in (ship.get("name"), ship.get("fdname"), ship_id):
            raw["shipByName"][_key(value)] = ship_id
    raw["moduleByName"] = {}
    for module_id, module in raw["modules"].items():
        for value in (module.get("fdname"), module.get("fdid")):
            if value not in (None, ""):
                raw["moduleByName"][_key(value)] = module_id
    for ship in raw["ships"].values():
        for module_id, module in (ship.get("module") or {}).items():
            for value in (module.get("fdname"), module.get("fdid")):
                if value not in (None, ""):
                    raw["moduleByName"][_key(value)] = int(module_id)
    return raw


def _ship(ship_id: Any) -> dict:
    return catalogue()["ships"].get(_integer(ship_id), {})


def _module(ship_id: Any, module_id: Any) -> dict:
    module_id = abs(_integer(module_id))
    ship_modules = _ship(ship_id).get("module") or {}
    common = catalogue()["modules"].get(module_id, {})
    override = ship_modules.get(str(module_id)) or ship_modules.get(module_id) or {}
    # Ship-specific modules (notably bulkheads) only contain their hull-dependent
    # cost/mass/Frontier identifiers.  EDSY stores the shared module definition in
    # the main module table, so combine both halves before using it.
    return {**common, **override} if override else common


def _module_label(module: dict) -> str:
    if not module:
        return "Empty"
    suffix = module.get("mount") or module.get("missile") or module.get("cabincls") or ""
    rating = f"{_integer(module.get('class'))}{module.get('rating') or '?'}"
    if suffix:
        rating += f"/{suffix}"
    return f"{rating} {module.get('name') or 'Unknown module'}"


def _slot_key(group: str, index: Any) -> str:
    return f"{group}:{index}"


def _slot_label(ship: dict, group: str, index: int, size: int) -> str:
    if group == "ship":
        return "Cargo Hatch"
    if group == "component" and 0 <= index < len(CORE_NAMES):
        return CORE_NAMES[index]
    named = ((ship.get("slotnames") or {}).get(group) or [])
    if index < len(named) and named[index]:
        text = re.sub(r"(?<=[a-z])(?=[A-Z])|[_-]+", " ", str(named[index]))
        text = re.sub(r"\b(?:Size|Slot)\s*\d+\b", "", text, flags=re.I).strip()
        if text and not re.fullmatch(r"(?:Large|Medium|Small|Tiny)?\s*(?:Hardpoint)?\s*\d*", text, re.I):
            return text
    singular = GROUP_LABELS.get(group, group).rstrip("s")
    return f"Class {size} {singular} {index + 1}"


def _ship_asset(name: str) -> str:
    from voidcompass.engineering.engineering_companion import ship_catalogue

    target = _key(name)
    row = next((item for item in ship_catalogue() if target in {_key(item.get("name")), _key(item.get("symbol"))}), None)
    return str((row or {}).get("asset") or "")


def ship_catalogue() -> list[dict]:
    rows = []
    for ship_id, ship in catalogue()["ships"].items():
        rows.append({
            "id": ship_id, "name": ship.get("name") or f"Ship {ship_id}",
            "symbol": ship.get("fdname") or "", "manufacturer": ship.get("manufacturer") or "",
            "class": _integer(ship.get("class")), "cost": _integer(ship.get("retail") or ship.get("cost")),
            "mass": _number(ship.get("mass")), "asset": _ship_asset(ship.get("name") or ""),
        })
    return sorted(rows, key=lambda row: row["name"].casefold())


def _stock_slots(ship_id: int) -> dict[str, dict]:
    ship = _ship(ship_id)
    slots: dict[str, dict] = {
        "ship:hatch": {"module": 49180, "enabled": True, "priority": 1},
    }
    for group, sizes in (ship.get("slots") or {}).items():
        stock = (ship.get("stock") or {}).get(group) or []
        for index, size in enumerate(sizes or []):
            module_id = abs(_integer(stock[index] if index < len(stock) else 0))
            slots[_slot_key(group, index)] = {
                "module": module_id, "enabled": True, "priority": 1,
            }
    return slots


def stock_build(ship_id: Any, name: str = "") -> dict:
    ship_id = _integer(ship_id)
    ship = _ship(ship_id)
    if not ship:
        raise BuildPlannerError("Select a supported ship hull.")
    return {
        "id": f"build:{time.time_ns()}", "ship_id": ship_id,
        "name": str(name or f"{ship.get('name')} build")[:80], "tag": "",
        "created": time.time(), "updated": time.time(),
        "fuel": None, "cargo": 0.0, "pips": {"sys": 4, "eng": 4, "wep": 4},
        "slots": _stock_slots(ship_id), "source": "Stock hull",
    }


def normalize_build(build: dict) -> dict:
    result = deepcopy(build if isinstance(build, dict) else {})
    ship_id = _integer(result.get("ship_id"))
    if not _ship(ship_id):
        raise BuildPlannerError("Build references an unsupported ship hull.")
    result["ship_id"] = ship_id
    result["id"] = str(result.get("id") or f"build:{time.time_ns()}")[:100]
    result["name"] = str(result.get("name") or _ship(ship_id).get("name") or "Ship build")[:80]
    result["tag"] = str(result.get("tag") or "")[:16]
    result["slots"] = dict(result.get("slots") or {})
    for key, slot in list(result["slots"].items()):
        if not isinstance(slot, dict):
            slot = {"module": slot}
        result["slots"][str(key)] = {
            "module": abs(_integer(slot.get("module"))),
            "enabled": slot.get("enabled", True) is not False,
            "priority": max(1, min(MAX_POWER_PRIORITY, _integer(slot.get("priority"), 1))),
            "blueprint": str(slot.get("blueprint") or "")[:80],
            "grade": max(0, min(5, _integer(slot.get("grade")))),
            "roll": max(0.0, min(1.0, _number(slot.get("roll"), 1.0))),
            "experimental": str(slot.get("experimental") or "")[:80],
            "modifiers": {
                str(attr): _number(value) for attr, value in (slot.get("modifiers") or {}).items()
                if isinstance(attr, str)
            },
        }
    result["pips"] = {
        axis: max(0, min(8, _integer((result.get("pips") or {}).get(axis), 4)))
        for axis in ("sys", "eng", "wep")
    }
    if sum(result["pips"].values()) != 12:
        result["pips"] = {"sys": 4, "eng": 4, "wep": 4}
    result["cargo"] = max(0.0, _number(result.get("cargo")))
    result["fuel"] = None if result.get("fuel") is None else max(0.0, _number(result.get("fuel")))
    return result


def _slot_definitions(build: dict) -> list[dict]:
    ship = _ship(build.get("ship_id"))
    rows = [{
        "key": "ship:hatch", "group": "ship", "groupLabel": GROUP_LABELS["ship"],
        "index": 0, "size": 1, "label": "Cargo Hatch",
    }]
    for group in GROUP_ORDER[1:]:
        for index, size in enumerate(((ship.get("slots") or {}).get(group) or [])):
            rows.append({
                "key": _slot_key(group, index), "group": group,
                "groupLabel": GROUP_LABELS.get(group, group.title()), "index": index,
                "size": _integer(size), "label": _slot_label(ship, group, index, _integer(size)),
                "allowedTypes": list(((((ship.get("reserved") or {}).get(group) or [])[index]) or {}).keys())
                if index < len(((ship.get("reserved") or {}).get(group) or [])) else [],
            })
    return rows


def _group_mtypes(group: str, index: int | None = None) -> set[str]:
    groups = catalogue().get("groups") or {}
    definition = groups.get(group) or {}
    if group == "component":
        entries = definition if isinstance(definition, list) else []
        definition = entries[index] if index is not None and index < len(entries) else {}
    return set((definition.get("mtypes") or {}).keys())


def module_allowed(build: dict, slot_key: str, module_id: Any) -> tuple[bool, str]:
    build = normalize_build(build)
    definition = next((row for row in _slot_definitions(build) if row["key"] == slot_key), None)
    if definition is None:
        return False, "Unknown ship slot."
    module_id = abs(_integer(module_id))
    if not module_id:
        return (True, "") if definition["group"] != "component" else (False, "Core internals cannot be empty.")
    module = _module(build["ship_id"], module_id)
    if not module:
        return False, "Unknown module."
    if definition["group"] == "ship":
        return (module_id == 49180, "Only the cargo hatch belongs in this slot.")
    allowed_types = _group_mtypes(definition["group"], definition["index"])
    if module.get("mtype") not in allowed_types:
        return False, "That module type does not fit this slot group."
    size = _integer(module.get("class"))
    if size > definition["size"]:
        return False, "The module is larger than the slot."
    if definition["group"] == "component" and definition["index"] in {4, 6} and size != definition["size"]:
        return False, "Life Support and Sensors must match their core slot size."
    if module.get("noundersize") and size < definition["size"]:
        return False, "This module cannot be undersized."
    reserved = module.get("reserved")
    if isinstance(reserved, dict) and str(build["ship_id"]) not in reserved and build["ship_id"] not in reserved:
        return False, "This module is restricted to another ship hull."
    ship = _ship(build["ship_id"])
    ship_reserved = (((ship.get("reserved") or {}).get(definition["group"]) or []))
    restriction = ship_reserved[definition["index"]] if definition["index"] < len(ship_reserved) else None
    if restriction and module.get("mtype") not in restriction:
        return False, "This specialised slot does not accept that module type."
    limit = module.get("limit")
    if limit:
        count = sum(
            1 for key, row in build["slots"].items()
            if key != slot_key and _module(build["ship_id"], row.get("module")).get("limit") == limit
        )
        maximum = _integer((catalogue().get("limits") or {}).get(limit), 1)
        if count >= maximum:
            return False, f"Only {maximum} module(s) of this restricted type may be fitted."
    return True, ""


def set_module(build: dict, slot_key: str, module_id: Any) -> dict:
    result = normalize_build(build)
    allowed, reason = module_allowed(result, slot_key, module_id)
    if not allowed:
        raise BuildPlannerError(reason)
    previous = result["slots"].get(slot_key) or {}
    result["slots"][slot_key] = {
        "module": abs(_integer(module_id)), "enabled": True,
        "priority": max(1, min(MAX_POWER_PRIORITY, _integer(previous.get("priority"), 1))),
        "blueprint": "", "grade": 0, "roll": 1.0,
        "experimental": "", "modifiers": {},
    }
    result["updated"] = time.time()
    return result


def configure_slot(build: dict, slot_key: str, payload: dict) -> dict:
    result = normalize_build(build)
    slot = result["slots"].get(slot_key)
    if not isinstance(slot, dict) or not slot.get("module"):
        raise BuildPlannerError("Select a fitted module first.")
    module = _module(result["ship_id"], slot["module"])
    module_type = (catalogue().get("moduleTypes") or {}).get(module.get("mtype"), {})
    blueprint = str(payload.get("blueprint") or "")[:80]
    experimental = str(payload.get("experimental") or "")[:80]
    if blueprint and blueprint not in (module_type.get("blueprints") or []):
        raise BuildPlannerError("That engineering blueprint is not available for this module.")
    if experimental and experimental not in (module_type.get("expeffects") or []):
        raise BuildPlannerError("That experimental effect is not available for this module.")
    grade = max(0, min(_integer((catalogue().get("blueprints") or {}).get(blueprint, {}).get("maxgrade"), 5), _integer(payload.get("grade"))))
    if not blueprint:
        grade = 0
    slot.update({
        "enabled": payload.get("enabled", True) is not False,
        "priority": max(1, min(MAX_POWER_PRIORITY, _integer(payload.get("priority"), 1))),
        "blueprint": blueprint, "grade": grade,
        "roll": max(0.0, min(1.0, _number(payload.get("roll"), 1.0))),
        "experimental": experimental, "modifiers": {},
    })
    result["updated"] = time.time()
    return result


def _combine_modifier(attribute: dict, first: Any, second: Any) -> float:
    first = _number(first)
    second = _number(second)
    if attribute.get("modset"):
        return second
    if attribute.get("modadd"):
        return first + second
    return (1.0 + first) * (1.0 + second) - 1.0


def _raw_modifier(attribute: dict, value: Any) -> float:
    value = _number(value)
    if attribute.get("modset") or attribute.get("modadd"):
        return value
    return value / _number(attribute.get("modmod"), 100.0)


def _modifier_from_values(attribute: dict, original: Any, current: Any) -> float:
    original = _number(original)
    current = _number(current)
    if attribute.get("modset"):
        return current
    if attribute.get("modadd"):
        return current - original
    if attribute.get("modmod"):
        scale = _number(attribute.get("modmod"), 100.0)
        return (1.0 + current / scale) / max(0.0000001, 1.0 + original / scale) - 1.0
    return current / original - 1.0 if original else 0.0


def _slot_modifiers(module: dict, slot: dict) -> dict[str, float]:
    db = catalogue()
    attributes = db["attributeMap"]
    result: dict[str, float] = {}
    blueprint = (db.get("blueprints") or {}).get(slot.get("blueprint"), {})
    grade = max(0, min(_integer(blueprint.get("maxgrade"), 5), _integer(slot.get("grade"))))
    if blueprint and grade:
        roll = max(0.0, min(1.0, _number(slot.get("roll"), 1.0)))
        for attr, values in blueprint.items():
            if attr not in attributes or not isinstance(values, list) or not values:
                continue
            current = _number(values[min(grade, len(values)) - 1])
            previous = _number(values[min(grade - 1, len(values)) - 1]) if grade > 1 else 0.0
            value = previous + (current - previous) * roll
            result[attr] = _raw_modifier(attributes[attr], value)
    experimental = (db.get("experimentalEffects") or {}).get(slot.get("experimental"), {})
    for attr, value in experimental.items():
        if attr not in attributes or not isinstance(value, (int, float)):
            continue
        result[attr] = _combine_modifier(attributes[attr], result.get(attr), _raw_modifier(attributes[attr], value))
    for attr, value in (slot.get("modifiers") or {}).items():
        if attr in attributes:
            result[attr] = _number(value)
    return result


def _attribute_value(module: dict, attr: str, modifiers: dict, memo: dict) -> float:
    if attr in memo:
        return memo[attr]
    metadata = catalogue()["attributeMap"].get(attr, {})
    value = module.get(attr)
    if value is None:
        default = metadata.get("default", 0)
        value = _attribute_value(module, default, modifiers, memo) if isinstance(default, str) else default
    value = _number(value)
    modifier = modifiers.get(attr)
    if modifier is not None and (value or metadata.get("modset") or metadata.get("modadd") or metadata.get("modmod")):
        if metadata.get("modset"):
            value = modifier
        elif metadata.get("modadd"):
            value += modifier
        elif metadata.get("modmod"):
            scale = _number(metadata.get("modmod"))
            value = ((1.0 + value / scale) * (1.0 + modifier) - 1.0) * scale
        else:
            value *= 1.0 + modifier
        step = _number(metadata.get("step"))
        if step:
            value = round(value / step) * step
        if metadata.get("min") is not None:
            value = max(value, _number(metadata["min"]))
        if metadata.get("max") is not None:
            value = min(value, _number(metadata["max"]))
    memo[attr] = value
    return value


def _effective_module(ship_id: int, slot: dict) -> tuple[dict, dict[str, float]]:
    module = _module(ship_id, slot.get("module"))
    if not module:
        return {}, {}
    modifiers = _slot_modifiers(module, slot)
    memo: dict[str, float] = {}
    attrs = set(module) | set(modifiers)
    attrs.update((catalogue().get("moduleTypes") or {}).get(module.get("mtype"), {}).get("keyattrs") or [])
    values = {
        attr: (_attribute_value(module, attr, modifiers, memo)
               if attr in catalogue()["attributeMap"] else _number(module.get(attr)))
        for attr in attrs if isinstance(module.get(attr), (int, float)) or attr in catalogue()["attributeMap"]
    }

    def get(attr: str, default: float = 0.0) -> float:
        return values.get(attr, _attribute_value(module, attr, modifiers, memo) if attr in catalogue()["attributeMap"] else default)

    burst_size = max(1.0, get("bstsize", 1.0))
    burst_rate = max(0.000001, get("bstrof", get("rof", 1.0)))
    burst_interval = max(0.0, get("bstint", 0.0))
    duration = max(0.0, get("duration")) * (1.0 + 0.0 * (get("dmgmul", 1.0) - 1.0))
    shots = max(1.0, get("ammoclip", burst_size))
    cycle = duration + (burst_size - 1.0) / burst_rate + burst_interval
    firing = cycle * math.ceil(shots / burst_size)
    sustained_cycle = firing + max(0.0, get("rldtime") - duration - burst_interval)
    rate = shots / firing if firing > 0 else get("rof", 1.0)
    sustained_rate = shots / sustained_cycle if sustained_cycle > 0 else rate
    damage = get("damage") * max(1.0, get("rounds", 1.0))
    values.update({
        "rof": rate, "srof": sustained_rate,
        "dps": damage * rate, "sdps": damage * sustained_rate,
        "eps": get("distdraw") * rate, "seps": get("distdraw") * sustained_rate,
        "hps": get("thmload") * rate, "shps": get("thmload") * sustained_rate,
    })
    return module, values


def _mass_curve(mass: float, minimum: float, optimum: float, maximum: float,
                minimum_multiplier: float, optimum_multiplier: float,
                maximum_multiplier: float) -> float:
    if maximum <= minimum or not maximum:
        return 0.0
    ratio = min(1.0, max(0.0, (maximum - mass) / (maximum - minimum)))
    if optimum == minimum or maximum_multiplier == minimum_multiplier:
        exponent = 1.0
    else:
        numerator = (optimum_multiplier - minimum_multiplier) / (maximum_multiplier - minimum_multiplier)
        denominator = (maximum - optimum) / (maximum - minimum)
        if numerator <= 0 or denominator <= 0 or denominator == 1:
            exponent = 1.0
        else:
            exponent = math.log(numerator) / math.log(denominator)
    return minimum_multiplier + math.pow(ratio, exponent) * (maximum_multiplier - minimum_multiplier)


def _jump_distance(mass: float, fuel: float, fsd: dict, boost: float = 0.0) -> float:
    fuel_use = min(max(0.0, fuel), fsd.get("maxfuel", 0.0))
    if not fuel_use or not fsd.get("fuelmul") or not fsd.get("fuelpower") or not fsd.get("fsdoptmass"):
        return 0.0
    return math.pow(fuel_use / fsd["fuelmul"], 1.0 / fsd["fuelpower"]) * fsd["fsdoptmass"] / max(0.0001, mass + fuel) + boost


def _total_jump_range(mass: float, fuel: float, fsd: dict, boost: float = 0.0) -> float:
    total = 0.0
    remaining = max(0.0, fuel)
    for _ in range(1000):
        if remaining < 0.000001:
            break
        total += _jump_distance(mass, remaining, fsd, boost)
        remaining -= min(remaining, fsd.get("maxfuel", 0.0))
    return total


def _damage_resistance(base: float, extra: float, exempt: float = 0.0, best: float = 0.0) -> float:
    low = max(30.0, base, best)
    expected = (1.0 - ((1.0 - base / 100.0) * (1.0 - extra / 100.0))) * 100.0
    penalized = low + (expected - low) / max(0.0001, 100.0 - low) * (65.0 - low)
    actual = penalized if penalized >= 30.0 else expected
    return (1.0 - ((1.0 - exempt / 100.0) * (1.0 - actual / 100.0))) * 100.0


def calculate(build: dict) -> dict:
    build = normalize_build(build)
    ship = _ship(build["ship_id"])
    definitions = {row["key"]: row for row in _slot_definitions(build)}
    fitted = []
    warnings = []
    invalid = []
    totals = {
        "mass": _number(ship.get("mass")), "cost": _number(ship.get("cost")),
        "fuel": 0.0, "cargo": 0.0, "passengers": 0.0,
        "powerCapacity": 0.0, "powerRetracted": 0.0, "powerDeployed": 0.0,
        "scoopRate": 0.0, "jumpBoost": 0.0, "hullBoost": 0.0, "hullReinforcement": 0.0,
        "shieldBoost": 0.0, "shieldReinforcement": 0.0,
    }
    priority_retracted = [0.0] * 6
    priority_deployed = [0.0] * 6
    hardpoints = []
    shield_generator = None
    bulkheads = None
    thrusters = None
    fsd = None
    distributor = None
    plant = None
    booster_resistance = {key: 1.0 for key in ("kinres", "thmres", "expres", "caures")}
    hull_resistance = {key: 1.0 for key in ("kinres", "thmres", "expres", "caures")}
    hull_best = {key: 1.0 for key in hull_resistance}
    thermal = {"thrusters": 0.0, "fsd": 0.0, "weapons": 0.0, "scb": 0.0}

    for slot_key, definition in definitions.items():
        slot = build["slots"].get(slot_key) or {"module": 0, "enabled": True, "priority": 1}
        module, attrs = _effective_module(build["ship_id"], slot)
        if not module:
            if definition["group"] == "component":
                invalid.append(f"{definition['label']} is empty")
            continue
        allowed, reason = module_allowed(build, slot_key, slot.get("module"))
        if not allowed:
            invalid.append(f"{definition['label']}: {reason}")
        priority = max(1, min(5, _integer(slot.get("priority"), 1)))
        enabled = slot.get("enabled", True) is not False or bool(module.get("powerlock"))
        power = attrs.get("pwrdraw", 0.0) if enabled else 0.0
        deployed = power
        retracted = power if definition["group"] != "hardpoint" and (definition["group"] != "utility" or module.get("passive")) else 0.0
        priority_deployed[priority] += deployed
        priority_retracted[priority] += retracted
        totals["mass"] += attrs.get("mass", 0.0)
        totals["cost"] += attrs.get("cost", _number(module.get("cost")))
        totals["fuel"] += attrs.get("fuelcap", 0.0)
        totals["cargo"] += attrs.get("cargocap", 0.0)
        totals["passengers"] += attrs.get("cabincap", 0.0)
        totals["powerCapacity"] += attrs.get("pwrcap", 0.0)
        totals["scoopRate"] += attrs.get("scooprate", 0.0) if enabled else 0.0
        totals["jumpBoost"] += attrs.get("jumpbst", 0.0) if enabled else 0.0
        totals["hullBoost"] += attrs.get("hullbst", 0.0)
        totals["hullReinforcement"] += attrs.get("hullrnf", 0.0)
        totals["shieldBoost"] += attrs.get("shieldbst", 0.0) if enabled else 0.0
        totals["shieldReinforcement"] += attrs.get("shieldrnf", 0.0) if enabled else 0.0
        mtype = module.get("mtype")
        if mtype == "cpp": plant = attrs
        elif mtype == "ct": thrusters, thermal["thrusters"] = attrs, attrs.get("engheat", 0.0)
        elif mtype in {"cfsd", "cfsdo"}: fsd, thermal["fsd"] = attrs, attrs.get("fsdheat", 0.0)
        elif mtype == "cpd": distributor = attrs
        elif mtype == "cbh": bulkheads = attrs
        elif mtype == "isg" and shield_generator is None and enabled: shield_generator = attrs
        elif mtype == "usb" and enabled:
            for key in booster_resistance:
                booster_resistance[key] *= 1.0 - attrs.get(key, 0.0) / 100.0
        elif mtype in {"ihrp", "imahrp"}:
            for key in hull_resistance:
                multiplier = 1.0 - attrs.get(key, 0.0) / 100.0
                hull_resistance[key] *= multiplier
                hull_best[key] = min(hull_best[key], multiplier)
        if definition["group"] == "hardpoint" and enabled:
            hardpoints.append(attrs)
            thermal["weapons"] += attrs.get("shps", attrs.get("hps", 0.0))
        if mtype == "iscb" and enabled:
            spinup = max(0.0001, attrs.get("spinup", 1.0))
            thermal["scb"] += attrs.get("scbheat", 0.0) / spinup
        fitted.append({
            **definition, "module": _integer(slot.get("module")), "moduleName": module.get("name") or "Unknown",
            "moduleLabel": _module_label(module), "type": mtype, "typeName": (catalogue().get("moduleTypes") or {}).get(mtype, {}).get("name") or mtype,
            "rating": f"{_integer(module.get('class'))}{module.get('rating') or '?'}", "enabled": enabled,
            "priority": priority, "blueprint": slot.get("blueprint") or "", "grade": _integer(slot.get("grade")),
            "roll": _number(slot.get("roll"), 1.0),
            "experimental": slot.get("experimental") or "", "mass": attrs.get("mass", 0.0),
            "power": attrs.get("pwrdraw", 0.0), "cost": attrs.get("cost", _number(module.get("cost"))),
            "attrs": {key: round(value, 6) for key, value in attrs.items() if value and math.isfinite(value)},
        })

    for priority in range(1, 6):
        priority_deployed[priority] += priority_deployed[priority - 1]
        priority_retracted[priority] += priority_retracted[priority - 1]
    totals["powerDeployed"] = priority_deployed[5]
    totals["powerRetracted"] = priority_retracted[5]
    totals["unladenMass"] = totals["mass"] + totals["fuel"]
    totals["ladenMass"] = totals["unladenMass"] + totals["cargo"]
    current_fuel = min(totals["fuel"], totals["fuel"] if build.get("fuel") is None else _number(build.get("fuel")))
    current_cargo = min(totals["cargo"], _number(build.get("cargo")))
    totals["currentMass"] = totals["mass"] + current_fuel + current_cargo
    totals["rebuy"] = totals["cost"] * 0.05
    if totals["powerDeployed"] > totals["powerCapacity"]:
        warnings.append("Deployed power draw exceeds plant output")
    if totals["powerRetracted"] > totals["powerCapacity"]:
        warnings.append("Retracted power draw exceeds plant output")

    navigation = {"currentJump": 0.0, "ladenJump": 0.0, "unladenJump": 0.0, "maxJump": 0.0, "ladenRange": 0.0, "unladenRange": 0.0, "speed": 0.0, "boost": 0.0, "boostInterval": 0.0}
    if fsd:
        navigation.update({
            "currentJump": _jump_distance(totals["mass"] + current_cargo, current_fuel, fsd, totals["jumpBoost"]),
            "ladenJump": _jump_distance(totals["mass"] + totals["cargo"], totals["fuel"], fsd, totals["jumpBoost"]),
            "unladenJump": _jump_distance(totals["mass"], totals["fuel"], fsd, totals["jumpBoost"]),
            "maxJump": _jump_distance(totals["mass"], min(totals["fuel"], fsd.get("maxfuel", 0.0)), fsd, totals["jumpBoost"]),
            "ladenRange": _total_jump_range(totals["mass"] + totals["cargo"], totals["fuel"], fsd, totals["jumpBoost"]),
            "unladenRange": _total_jump_range(totals["mass"], totals["fuel"], fsd, totals["jumpBoost"]),
        })
    if thrusters:
        multiplier = _mass_curve(
            totals["currentMass"], thrusters.get("engminmass", 0.0), thrusters.get("engoptmass", 0.0), thrusters.get("engmaxmass", 0.0),
            thrusters.get("engminmul", 0.0), thrusters.get("engoptmul", 100.0), thrusters.get("engmaxmul", 0.0),
        ) / 100.0
        navigation["speed"] = _number(ship.get("topspd")) * multiplier
        navigation["boost"] = _number(ship.get("bstspd")) * multiplier if distributor and distributor.get("engcap", 0.0) >= _number(ship.get("boostcost")) + 0.5 else 0.0
        navigation["boostInterval"] = max(_number(ship.get("boostint")), _number(ship.get("boostcost")) / max(0.0001, (distributor or {}).get("engchg", 0.0)))
        if totals["mass"] > thrusters.get("engmaxmass", float("inf")):
            invalid.append("Ship mass exceeds the fitted thrusters' maximum mass")

    defenses = {"shield": 0.0, "armour": 0.0, "hardness": _number(ship.get("hardness")), "shieldResistances": {}, "armourResistances": {}}
    if shield_generator:
        hull_mass = _number(ship.get("mass"))
        if hull_mass <= shield_generator.get("genmaxmass", 0.0):
            multiplier = _mass_curve(
                hull_mass, shield_generator.get("genminmass", 0.0), shield_generator.get("genoptmass", 0.0), shield_generator.get("genmaxmass", 0.0),
                shield_generator.get("genminmul", 0.0), shield_generator.get("genoptmul", 0.0), shield_generator.get("genmaxmul", 0.0),
            ) / 100.0
            defenses["shield"] = _number(ship.get("shields")) * (1.0 + totals["shieldBoost"] / 100.0) * multiplier + totals["shieldReinforcement"]
            for key in booster_resistance:
                extra = (1.0 - booster_resistance[key]) * 100.0
                defenses["shieldResistances"][key] = _damage_resistance(0.0, extra, shield_generator.get(key, 0.0))
        else:
            invalid.append("The fitted shield generator cannot support this hull mass")
    base_armour = _number(ship.get("armour"))
    defenses["armour"] = base_armour * (1.0 + totals["hullBoost"] / 100.0) + totals["hullReinforcement"]
    for key in hull_resistance:
        extra = (1.0 - hull_resistance[key]) * 100.0
        defenses["armourResistances"][key] = _damage_resistance((bulkheads or {}).get(key, 0.0), extra, 0.0, (1.0 - hull_best[key]) * 100.0)

    weapons = {key: 0.0 for key in ("dps", "sustainedDps", "absolute", "thermal", "kinetic", "explosive", "antiXeno", "caustic", "distributorDraw", "heat")}
    ammo_time = float("inf")
    for attrs in hardpoints:
        dps = attrs.get("dps", 0.0)
        sustained = attrs.get("sdps", dps)
        weapons["dps"] += dps
        weapons["sustainedDps"] += sustained
        weapons["distributorDraw"] += attrs.get("seps", attrs.get("eps", 0.0))
        weapons["heat"] += attrs.get("shps", attrs.get("hps", 0.0))
        for output, attr in (("absolute", "abswgt"), ("thermal", "thmwgt"), ("kinetic", "kinwgt"), ("explosive", "expwgt"), ("antiXeno", "axewgt"), ("caustic", "cauwgt")):
            weapons[output] += sustained * attrs.get(attr, 0.0) / 100.0
        ammo = attrs.get("ammoclip", 0.0) + attrs.get("ammomax", 0.0)
        if ammo and attrs.get("srof", 0.0):
            ammo_time = min(ammo_time, ammo / attrs["srof"])
    weapons["ammoTime"] = None if math.isinf(ammo_time) else ammo_time
    wep_cap = (distributor or {}).get("wepcap", 0.0)
    wep_recharge = (distributor or {}).get("wepchg", 0.0) * math.pow(build["pips"]["wep"] / 8.0, 1.1)
    weapons["capacitorDuration"] = None if weapons["distributorDraw"] <= wep_recharge else wep_cap / max(0.0001, weapons["distributorDraw"] - wep_recharge)
    weapons["sustain"] = min(1.0, wep_recharge / weapons["distributorDraw"]) if weapons["distributorDraw"] else 1.0

    heat_capacity = _number(ship.get("heatcap"))
    heat_dissipation = _number(ship.get("heatdismax"))
    efficiency = (plant or {}).get("heateff", 1.0)
    idle_load = totals["powerRetracted"] * efficiency
    thermal.update({
        "capacity": heat_capacity, "dissipation": heat_dissipation,
        "idle": math.sqrt(idle_load / heat_dissipation) * 100.0 if heat_dissipation and idle_load >= 0 else 0.0,
        "thrust": math.sqrt((idle_load + thermal["thrusters"]) / heat_dissipation) * 100.0 if heat_dissipation else 0.0,
        "fsdCharge": math.sqrt((idle_load + thermal["thrusters"] + thermal["fsd"]) / heat_dissipation) * 100.0 if heat_dissipation else 0.0,
        "weaponsFiring": math.sqrt((idle_load + thermal["thrusters"] + thermal["weapons"]) / heat_dissipation) * 100.0 if heat_dissipation else 0.0,
        "shieldCell": math.sqrt((idle_load + thermal["thrusters"] + thermal["scb"]) / heat_dissipation) * 100.0 if heat_dissipation else 0.0,
    })
    handling_multiplier = navigation["speed"] / max(0.0001, _number(ship.get("topspd"))) if navigation["speed"] else 0.0
    handling = {
        "pitch": _number(ship.get("pitch")) * handling_multiplier,
        "roll": _number(ship.get("roll")) * handling_multiplier,
        "yaw": _number(ship.get("yaw")) * handling_multiplier,
        "pitch180": 180.0 / max(0.0001, _number(ship.get("pitch")) * handling_multiplier) if handling_multiplier else 0.0,
    }
    power = {
        "capacity": totals["powerCapacity"], "retracted": totals["powerRetracted"], "deployed": totals["powerDeployed"],
        "retractedPercent": totals["powerRetracted"] * 100.0 / max(0.0001, totals["powerCapacity"]),
        "deployedPercent": totals["powerDeployed"] * 100.0 / max(0.0001, totals["powerCapacity"]),
        "prioritiesRetracted": priority_retracted[1:], "prioritiesDeployed": priority_deployed[1:],
    }
    return {
        "totals": totals, "navigation": navigation, "power": power, "thermal": thermal,
        "defenses": defenses, "weapons": weapons, "handling": handling,
        "warnings": warnings, "invalid": invalid, "valid": not invalid,
        "fitted": fitted,
    }


def _compact_modules(ship_id: int) -> list[dict]:
    db = catalogue()
    modules = dict(db["modules"])
    for key, value in (_ship(ship_id).get("module") or {}).items():
        module_id = int(key)
        modules[module_id] = {**modules.get(module_id, {}), **value}
    rows = []
    for module_id, module in modules.items():
        module_type = (db.get("moduleTypes") or {}).get(module.get("mtype"), {})
        groups = []
        for group in ("hardpoint", "utility", "military", "internal"):
            if module.get("mtype") in _group_mtypes(group):
                groups.append(group)
        component_indexes = [index for index in range(8) if module.get("mtype") in _group_mtypes("component", index)]
        rows.append({
            "id": module_id, "name": module.get("name") or "Unknown module", "label": _module_label(module),
            "type": module.get("mtype") or "", "typeName": module_type.get("name") or module.get("mtype") or "Unknown",
            "class": _integer(module.get("class")), "rating": str(module.get("rating") or "?"),
            "mount": str(module.get("mount") or module.get("missile") or module.get("cabincls") or ""),
            "cost": _number(module.get("cost")), "mass": _number(module.get("mass")),
            "power": _number(module.get("pwrdraw")), "groups": groups, "components": component_indexes,
            "hidden": bool(module.get("hidden")), "reservedShips": list((module.get("reserved") or {}).keys()) if isinstance(module.get("reserved"), dict) else [],
            "blueprints": list(module_type.get("blueprints") or []), "effects": list(module_type.get("expeffects") or []),
            "attrs": {key: value for key, value in module.items() if key in db["attributeMap"] and isinstance(value, (int, float))},
        })
    return sorted(rows, key=lambda row: (row["typeName"].casefold(), -row["class"], row["rating"], row["name"].casefold()))


def _engineering_catalogue() -> tuple[list[dict], list[dict]]:
    blueprints = [{"id": key, "name": row.get("name") or key, "maxGrade": _integer(row.get("maxgrade"), 5)} for key, row in (catalogue().get("blueprints") or {}).items()]
    effects = [{"id": key, "name": row.get("name") or key, "description": row.get("special") or ""} for key, row in (catalogue().get("experimentalEffects") or {}).items()]
    return blueprints, effects


def _hash_number(text: str) -> int:
    result = 0
    for character in text:
        result = (result << 6) | HASH_VALUES.get(character, 0)
    return result


def _hash_text(text: str) -> str:
    output = []
    index = 0
    while index < len(text):
        first = HASH_VALUES.get(text[index], 0)
        index += 1
        if first < 62:
            output.append(HASH_ALPHABET[first])
        elif first == 62 and index < len(text):
            output.append(HASH_TEXT_PUNCTUATION[HASH_VALUES.get(text[index], 0)])
            index += 1
        elif first == 63 and index + 1 < len(text):
            value = (HASH_VALUES.get(text[index], 0) << 6) | HASH_VALUES.get(text[index + 1], 0)
            output.append(chr(value + 0x7F))
            index += 2
    return "".join(output)


def _float20(value: int) -> float:
    sign = (value >> 19) & 1
    exponent = (value >> 14) & 31
    mantissa = value & 0x3FFF
    if exponent >= 31:
        return math.nan if mantissa else (-math.inf if sign else math.inf)
    return (-1 if sign else 1) * math.pow(2.0, exponent - 29 + (1 if exponent == 0 else 0)) * ((0x4000 if exponent else 0) | mantissa)


def _version_module_id(version: int, module_id: int) -> int:
    """Apply EDSY's forward maps for supported historic hash versions."""
    if version <= 16:
        return {86220: 86250, 86222: 86262, 86310: 86330, 86312: 86352}.get(module_id, module_id)
    return module_id


def _version_slot_index(version: int, ship_id: int, group: str, index: int) -> int:
    if version <= 18 and ship_id == 46 and group == "hardpoint":
        mapping = (4, 5, 0, 1, 2, 3)
        return mapping[index] if index < len(mapping) else index
    return index


def _decode_edsy_slot(text: str, version: int, ship_id: int) -> tuple[dict, int]:
    if version < SUPPORTED_HASH_MIN_VERSION or version > SUPPORTED_HASH_MAX_VERSION:
        raise BuildPlannerError(f"EDSY URL hash version {version} is not supported; export SLEF from EDSY instead.")
    index = 0
    module_id = _version_module_id(version, _hash_number(text[index:index + 3])); index += 3
    slot_bits = _hash_number(text[index:index + 1]); index += 1
    costed = bool(slot_bits & 0x20)
    engineered = bool(slot_bits & 0x10)
    if costed:
        cost_bits = _hash_number(text[index:index + 1]); index += 1
        index += ((cost_bits >> 4) & 0x3) + 2
    else:
        index += 1
    module = _module(ship_id, module_id)
    slot = {
        "module": module_id, "enabled": not bool(slot_bits & 0x8),
        "priority": (slot_bits & 0x7) + 1, "blueprint": "", "grade": 0,
        "roll": 1.0, "experimental": "", "modifiers": {},
    }
    if engineered:
        engineering_bits = _hash_number(text[index:index + 2]); index += 2
        blueprint_index = (engineering_bits >> 7) & 0xF
        grade = (engineering_bits >> 4) & 0x7
        effect_index = engineering_bits & 0xF
        roll = _hash_number(text[index:index + 2]) / 4000.0; index += 2
        count = _hash_number(text[index:index + 1]); index += 1
        module_type = (catalogue().get("moduleTypes") or {}).get(module.get("mtype"), {})
        blueprints = module_type.get("blueprints") or []
        effects = module_type.get("expeffects") or []
        slot.update({
            "blueprint": blueprints[blueprint_index - 1] if 0 < blueprint_index <= len(blueprints) else "",
            "grade": grade, "roll": roll,
            "experimental": effects[effect_index - 1] if 0 < effect_index <= len(effects) else "",
        })
        modifiable = module_type.get("modifiable") or []
        for _ in range(count):
            encoded = _hash_number(text[index:index + 4]); index += 4
            attr_index = (encoded >> 20) & 0xF
            if attr_index < len(modifiable):
                slot["modifiers"][modifiable[attr_index]] = _float20(encoded & 0xFFFFF)
    return slot, index


def decode_edsy_hash(build_hash: str) -> dict:
    build_hash = unquote(str(build_hash or "").strip())
    if "#/" in build_hash:
        fragment = urlparse(build_hash).fragment
        match = re.search(r"(?:^|/)L=([^/]+)", fragment)
        if not match:
            raise BuildPlannerError("The EDSY URL does not contain a long build hash.")
        build_hash = match.group(1)
    if not build_hash:
        raise BuildPlannerError("The EDSY build hash is empty.")
    version = _hash_number(build_hash[0])
    if version < SUPPORTED_HASH_MIN_VERSION or version > SUPPORTED_HASH_MAX_VERSION:
        raise BuildPlannerError(f"EDSY URL hash version {version} is not supported; export SLEF from EDSY instead.")
    chunks = build_hash[1:].split(",")
    if len(chunks) < 6:
        raise BuildPlannerError("The EDSY build hash is incomplete.")
    ship_chunk = chunks[0]
    ship_id = _hash_number(ship_chunk[:1])
    ship = _ship(ship_id)
    if not ship:
        raise BuildPlannerError(f"The EDSY build uses unknown ship ID {ship_id}.")
    index = 1
    index += 1  # hull discount
    cost_bits = _hash_number(ship_chunk[index:index + 1]); index += 1
    index += ((cost_bits >> 4) & 0x3) + 2
    index += 3  # crew distribution and pip distribution
    hatch, _used = _decode_edsy_slot(ship_chunk[index:], version, ship_id)
    build = stock_build(ship_id, ship.get("name") or "EDSY import")
    build.update({"source": "EDSY URL", "slots": {}, "name": _hash_text(chunks[6]) if len(chunks) > 6 and chunks[6] else f"{ship.get('name')} EDSY import", "tag": _hash_text(chunks[7]) if len(chunks) > 7 else ""})
    build["slots"]["ship:hatch"] = hatch
    for group, chunk_index in (("hardpoint", 1), ("utility", 2), ("component", 3), ("military", 4), ("internal", 5)):
        text = chunks[chunk_index] if chunk_index < len(chunks) else ""
        cursor = slot_index = 0
        while cursor < len(text):
            module_id = _hash_number(text[cursor:cursor + 3])
            if module_id >= 199900:
                slot_index += module_id - 199900
                cursor += 3
                continue
            slot, used = _decode_edsy_slot(text[cursor:], version, ship_id)
            mapped_index = _version_slot_index(version, ship_id, group, slot_index)
            build["slots"][_slot_key(group, mapped_index)] = slot
            cursor += used
            slot_index += 1
    for definition in _slot_definitions(build):
        build["slots"].setdefault(definition["key"], {"module": 0, "enabled": True, "priority": 1})
    return normalize_build(build)


def _journal_slot_key(build: dict, journal_slot: str, module_id: int, used: set[str]) -> str | None:
    core = {
        "armour": 0, "powerplant": 1, "mainengines": 2, "frameshiftdrive": 3,
        "lifesupport": 4, "powerdistributor": 5, "radar": 6, "fueltank": 7,
    }
    normalized = _key(journal_slot)
    if normalized in core:
        return _slot_key("component", core[normalized])
    module = _module(build["ship_id"], module_id)
    possible = []
    for definition in _slot_definitions(build):
        if definition["key"] in used or definition["group"] in {"ship", "component"}:
            continue
        if module.get("mtype") in _group_mtypes(definition["group"], definition["index"]):
            possible.append(definition)
    number = re.search(r"(\d+)(?:_size\d+)?$", str(journal_slot or ""), re.I)
    if number:
        ordinal = int(number.group(1)) - 1
        same_group = [row for row in possible if row["index"] == ordinal]
        if same_group:
            return same_group[0]["key"]
    return possible[0]["key"] if possible else None


def journal_build(loadout: dict, name: str = "") -> tuple[dict, list[str]]:
    ship_value = loadout.get("Ship") or loadout.get("ShipType") or ""
    if isinstance(ship_value, dict):
        ship_value = ship_value.get("name") or ship_value.get("id") or ""
    ship_id = catalogue()["shipByName"].get(_key(ship_value))
    if not ship_id:
        raise BuildPlannerError(f"Unsupported ship in loadout: {ship_value or 'unknown'}")
    build = stock_build(ship_id, name or loadout.get("ShipName") or f"{_ship(ship_id).get('name')} import")
    build["source"] = "EDCD SLEF / Journal Loadout"
    build["tag"] = str(loadout.get("ShipIdent") or "")[:16]
    warnings = []
    used = set()
    for row in loadout.get("Modules") or loadout.get("modules") or []:
        if not isinstance(row, dict):
            continue
        item = row.get("Item") or row.get("item") or row.get("module") or row.get("name") or row.get("id")
        if isinstance(item, dict):
            item = item.get("fdname") or item.get("edname") or item.get("id") or item.get("name")
        module_id = catalogue()["moduleByName"].get(_key(item))
        if not module_id:
            warnings.append(f"Unknown module skipped: {item}")
            continue
        key = _journal_slot_key(build, str(row.get("Slot") or row.get("slot") or ""), module_id, used)
        if not key:
            warnings.append(f"No compatible slot found for {_module_label(_module(ship_id, module_id))}")
            continue
        engineering = row.get("Engineering") or row.get("engineering") or {}
        engineering = engineering if isinstance(engineering, dict) else {}
        module_data = _module(ship_id, module_id)
        module_type = (catalogue().get("moduleTypes") or {}).get(module_data.get("mtype"), {})
        blueprint_name = _key(engineering.get("BlueprintName") or engineering.get("blueprintName"))
        blueprint = next((item for item in module_type.get("blueprints") or [] if blueprint_name in {_key(item), _key((catalogue().get("blueprints") or {}).get(item, {}).get("name")), _key((catalogue().get("blueprints") or {}).get(item, {}).get("fdname"))}), "")
        effect_name = _key(engineering.get("ExperimentalEffect") or engineering.get("ExperimentalEffect_Localised") or engineering.get("experimentalEffect"))
        effect = next((item for item in module_type.get("expeffects") or [] if effect_name in {_key(item), _key((catalogue().get("experimentalEffects") or {}).get(item, {}).get("name")), _key((catalogue().get("experimentalEffects") or {}).get(item, {}).get("fdname"))}), "")
        exact_modifiers = {}
        attribute_by_frontier = {
            _key(metadata.get("fdattr")): (attr, metadata)
            for attr, metadata in catalogue()["attributeMap"].items() if metadata.get("fdattr")
        }
        for modifier in engineering.get("Modifiers") or engineering.get("modifiers") or []:
            if not isinstance(modifier, dict):
                continue
            match = attribute_by_frontier.get(_key(modifier.get("Label") or modifier.get("label")))
            if not match:
                continue
            attr, metadata = match
            original = modifier.get("OriginalValue", modifier.get("originalValue", module_data.get(attr)))
            current = modifier.get("Value", modifier.get("value"))
            if current is not None:
                exact_modifiers[attr] = _modifier_from_values(metadata, original, current)
        build["slots"][key] = {
            "module": module_id, "enabled": row.get("On", row.get("on", True)) is not False,
            "priority": max(1, min(5, _integer(row.get("Priority", row.get("priority", 0)), 0) + 1)),
            "blueprint": blueprint, "grade": max(0, min(5, _integer(engineering.get("Level") or engineering.get("grade")))),
            "roll": _number(engineering.get("Quality"), 1.0), "experimental": effect, "modifiers": exact_modifiers,
        }
        used.add(key)
    if loadout.get("FuelCapacity"):
        capacity = loadout.get("FuelCapacity")
        build["fuel"] = _number(capacity.get("Main")) if isinstance(capacity, dict) else _number(capacity)
    build["cargo"] = _number(loadout.get("CargoCapacity"), 0.0)
    return normalize_build(build), warnings


def parse_import(text: str) -> dict:
    value = str(text or "").strip()
    if not value:
        raise BuildPlannerError("Paste an EDSY URL, EDSY backup, SLEF, or Journal Loadout JSON.")
    builds = []
    warnings = []
    if re.search(r"https?://[^\s]*(?:edsy|edshipyard)[^\s]*#/", value, re.I) or re.fullmatch(r"[0-9A-Za-z_\-,]+", value):
        builds.append(decode_edsy_hash(value))
    else:
        try:
            document = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise BuildPlannerError(f"Invalid build input: {exc}") from None
        if isinstance(document, dict) and document.get("format") == "edsy":
            hashes = []
            hashes.extend((row.get("hash"), row.get("label")) for row in document.get("buildlist") or [] if isinstance(row, dict) and row.get("hash"))
            hashes.extend((build_hash, label) for label, build_hash in (document.get("builds") or {}).items())
            for build_hash, label_hash in hashes[:MAX_BUILDS]:
                imported = decode_edsy_hash(str(build_hash))
                if label_hash and imported["name"].endswith(" EDSY import"):
                    decoded_label = _hash_text(str(label_hash))
                    if decoded_label:
                        imported["name"] = decoded_label[:80]
                builds.append(imported)
        else:
            values = document if isinstance(document, list) else [document]
            for value_row in values[:MAX_BUILDS]:
                if not isinstance(value_row, dict):
                    continue
                data = value_row.get("data") if isinstance(value_row.get("data"), dict) else value_row
                if data.get("event") == "Loadout" or data.get("Ship") and (data.get("Modules") or data.get("modules")):
                    build, row_warnings = journal_build(data)
                    builds.append(build)
                    warnings.extend(row_warnings)
        if not builds:
            raise BuildPlannerError("No supported EDSY/SLEF or Journal build was found.")
    return {
        "ready": bool(builds), "count": len(builds), "warnings": warnings[:100],
        "builds": builds, "summary": [
            {"name": build["name"], "ship": _ship(build["ship_id"]).get("name"), "modules": sum(1 for slot in build["slots"].values() if slot.get("module"))}
            for build in builds
        ],
    }


def export_slef(build: dict) -> str:
    build = normalize_build(build)
    ship = _ship(build["ship_id"])
    definitions = {row["key"]: row for row in _slot_definitions(build)}
    modules = []
    for key, slot in build["slots"].items():
        if key == "ship:hatch" or not slot.get("module") or key not in definitions:
            continue
        module = _module(build["ship_id"], slot["module"])
        definition = definitions[key]
        if not module:
            continue
        engineering = {}
        blueprint = (catalogue().get("blueprints") or {}).get(slot.get("blueprint"), {})
        effect = (catalogue().get("experimentalEffects") or {}).get(slot.get("experimental"), {})
        if blueprint:
            engineering.update({"BlueprintName": blueprint.get("fdname") or slot.get("blueprint"), "Level": slot.get("grade"), "Quality": slot.get("roll", 1.0)})
        if effect:
            engineering["ExperimentalEffect"] = effect.get("fdname") or slot.get("experimental")
            engineering["ExperimentalEffect_Localised"] = effect.get("name") or slot.get("experimental")
        applied = _slot_modifiers(module, slot)
        _effective, effective_attrs = _effective_module(build["ship_id"], slot)
        modifier_rows = []
        for attr in sorted(applied):
            metadata = catalogue()["attributeMap"].get(attr, {})
            if not metadata.get("fdattr") or attr not in effective_attrs:
                continue
            original = _attribute_value(module, attr, {}, {})
            modifier_rows.append({
                "Label": metadata["fdattr"], "Value": round(effective_attrs[attr], 6),
                "OriginalValue": round(original, 6),
            })
        if modifier_rows:
            engineering["Modifiers"] = modifier_rows
        core_slots = ("Armour", "PowerPlant", "MainEngines", "FrameShiftDrive", "LifeSupport", "PowerDistributor", "Radar", "FuelTank")
        journal_slot = core_slots[definition["index"]] if definition["group"] == "component" else (((ship.get("slotnames") or {}).get(definition["group"]) or [])[definition["index"]] if definition["index"] < len(((ship.get("slotnames") or {}).get(definition["group"]) or [])) else f"{definition['group'].title()}{definition['index'] + 1}")
        modules.append({
            "Slot": journal_slot, "Item": module.get("fdname") or str(slot["module"]),
            "On": slot.get("enabled", True), "Priority": max(0, _integer(slot.get("priority"), 1) - 1),
            **({"Engineering": engineering} if engineering else {}),
        })
    payload = [{
        "header": {"appName": "VoidCompass", "appVersion": APP_VERSION, "exportTime": datetime.now(timezone.utc).isoformat()},
        "data": {"timestamp": datetime.now(timezone.utc).isoformat(), "event": "Loadout", "Ship": ship.get("fdname"), "ShipID": 0, "ShipName": build.get("name"), "ShipIdent": build.get("tag"), "HullValue": _integer(ship.get("cost")), "Modules": modules},
    }]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def engineering_plan(build: dict) -> tuple[dict, list[dict]]:
    """Translate a planner loadout into the existing material-wishlist model."""
    build = normalize_build(build)
    ship = _ship(build["ship_id"])
    definitions = {row["key"]: row for row in _slot_definitions(build)}
    core_slots = ("Armour", "PowerPlant", "MainEngines", "FrameShiftDrive", "LifeSupport", "PowerDistributor", "Radar", "FuelTank")
    assignments = {}
    pins = []
    plan_id = f"plan:{time.time_ns()}"
    from voidcompass.engineering import engineering_companion

    engineering_groups = engineering_companion.blueprint_groups()

    def engineering_identity(module: dict, blueprint: dict) -> tuple[str, str]:
        source_type = str((catalogue().get("moduleTypes") or {}).get(module.get("mtype"), {}).get("name") or module.get("name") or "")
        source_name = str(blueprint.get("name") or "")
        possible = [
            (target_type, target_name) for target_type, target_name in engineering_groups
            if engineering_companion.module_matches_type(module.get("fdname") or module.get("name"), target_type)
        ]
        if not possible:
            return source_type, source_name
        source_type_key = _key(source_type.rstrip("s"))
        source_name_key = _key(source_name)
        return max(possible, key=lambda row: (
            SequenceMatcher(None, source_name_key, _key(row[1])).ratio() * 2.0
            + SequenceMatcher(None, source_type_key, _key(row[0])).ratio()
        ))
    for slot_key, slot in build["slots"].items():
        definition = definitions.get(slot_key)
        module = _module(build["ship_id"], slot.get("module"))
        if not definition or not module or definition["group"] == "ship":
            continue
        if definition["group"] == "component":
            journal_slot = core_slots[definition["index"]]
        else:
            named = ((ship.get("slotnames") or {}).get(definition["group"]) or [])
            journal_slot = str(named[definition["index"]]) if definition["index"] < len(named) else f"{definition['group'].title()}{definition['index'] + 1}"
        blueprint = (catalogue().get("blueprints") or {}).get(slot.get("blueprint"), {})
        module_type = str((catalogue().get("moduleTypes") or {}).get(module.get("mtype"), {}).get("name") or module.get("name") or "")
        blueprint_name = str(blueprint.get("name") or slot.get("blueprint") or "")
        if blueprint:
            module_type, blueprint_name = engineering_identity(module, blueprint)
        assignments[journal_slot] = {"module_type": module_type}
        if not blueprint or not slot.get("grade"):
            continue
        effect = (catalogue().get("experimentalEffects") or {}).get(slot.get("experimental"), {})
        pins.append({
            "id": f"{plan_id}:{journal_slot}", "name": blueprint_name,
            "type": module_type, "grade": _integer(slot.get("grade")),
            "target_grade": _integer(slot.get("grade")), "current_grade": 0,
            "quantity": 1, "slot": journal_slot, "ship_id": plan_id,
            "experimental": str(effect.get("name") or slot.get("experimental") or ""),
        })
    planned = {
        "id": plan_id, "ship_symbol": str(ship.get("fdname") or ""),
        "name": f"{build['name']} engineering", "slots": assignments,
        "created": time.time(), "source_build_id": build["id"],
    }
    return planned, pins


def clone_live(companion: dict, name: str = "") -> tuple[dict, list[str]]:
    loadout = companion.get("loadout") if isinstance(companion, dict) else None
    if not isinstance(loadout, dict) or not loadout.get("Ship"):
        raise BuildPlannerError("A live Journal Loadout event is required before cloning the current ship.")
    build, warnings = journal_build(loadout, name=name or f"{loadout.get('ShipName') or loadout.get('Ship')} live clone")
    build["id"] = f"build:{time.time_ns()}"
    build["source"] = "Live Journal clone"
    return build, warnings


def workspace(state: dict, companion: dict, transient: dict | None = None) -> dict:
    state = state if isinstance(state, dict) else {}
    transient = transient if isinstance(transient, dict) else {}
    stored = stored_builds(state)
    live = None
    live_warning = ""
    try:
        live, warnings = clone_live(companion or {})
        live["id"] = "live"
        live["name"] = f"LIVE · {live['name']}"
        live_warning = "; ".join(warnings[:3])
    except BuildPlannerError as exc:
        live_warning = str(exc)
    build_id = str(state.get("build_planner_selected") or "")
    selected = next((row for row in stored if row["id"] == build_id), None)
    if selected is None and build_id == "live":
        selected = live
    selected = selected or live or (stored[0] if stored else stock_build(1, "Unsaved Sidewinder"))
    editable = selected.get("id") != "live" and any(row["id"] == selected.get("id") for row in stored)
    analysis = calculate(selected)
    comparison_id = str(state.get("build_planner_compare") or "")
    comparison = next((row for row in stored if row["id"] == comparison_id and row["id"] != selected.get("id")), None)
    comparison_analysis = calculate(comparison) if comparison else None
    blueprints, effects = _engineering_catalogue()
    slots = analysis.pop("fitted")
    slot_map = {row["key"]: row for row in slots}
    for definition in _slot_definitions(selected):
        if definition["key"] not in slot_map:
            slots.append({**definition, "module": 0, "moduleName": "Empty", "moduleLabel": "Empty", "type": "", "typeName": "", "rating": "—", "enabled": True, "priority": 1, "blueprint": "", "grade": 0, "experimental": "", "mass": 0, "power": 0, "cost": 0, "attrs": {}})
    slots.sort(key=lambda row: (GROUP_ORDER.index(row["group"]), row["index"]))
    source = catalogue().get("source") or {}
    return {
        "version": APP_VERSION, "catalogueVersion": source.get("databaseVersion"), "catalogueDate": source.get("lastModified"),
        "ships": ship_catalogue(), "builds": [{"id": row["id"], "name": row["name"], "ship": _ship(row["ship_id"]).get("name"), "updated": row.get("updated"), "source": row.get("source")} for row in stored],
        "live": {"available": live is not None, "warning": live_warning},
        "selected": {"id": selected.get("id"), "name": selected.get("name"), "tag": selected.get("tag"), "shipId": selected["ship_id"], "ship": _ship(selected["ship_id"]).get("name"), "symbol": _ship(selected["ship_id"]).get("fdname"), "asset": _ship_asset(_ship(selected["ship_id"]).get("name") or ""), "source": selected.get("source"), "fuel": selected.get("fuel"), "cargo": selected.get("cargo"), "pips": selected.get("pips"), "editable": editable},
        "slots": slots, "modules": _compact_modules(selected["ship_id"]),
        "blueprints": blueprints, "effects": effects,
        "attributes": [{
            "id": row.get("attr"), "name": row.get("name") or row.get("abbr") or row.get("attr"),
            "unit": row.get("unit") or "", "description": row.get("desc") or "",
            "hidden": bool(row.get("hidden")),
        } for row in catalogue().get("attributes") or [] if row.get("attr")],
        "analysis": analysis,
        "comparison": ({"build": {"id": comparison["id"], "name": comparison["name"], "ship": _ship(comparison["ship_id"]).get("name")}, "analysis": comparison_analysis} if comparison else None),
        "importPreview": transient.get("import_preview") or {},
        "notice": str(transient.get("notice") or ""), "error": str(transient.get("error") or ""),
    }
