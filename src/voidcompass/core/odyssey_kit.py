"""Odyssey on foot (5.5.2.8): the commander's suit, loadout and weapons, what
they carry, and their on-foot and exobiology record, for Commander Record.

Everything comes from the journal: SuitLoadout (logged at login and on every
change), Backpack, ShipLocker.json, and the Statistics event. The game names
suits and modifications by internal symbols (and its localised suit names
carry the wrong grade), so they are turned into the names shown in game here.
"""

from __future__ import annotations

import re

SUITS = {
    "explorationsuit": "Artemis Suit",
    "tacticalsuit": "Dominator Suit",
    "utilitysuit": "Maverick Suit",
    "flightsuit": "Flight Suit",
}

SUIT_MODS = {
    "suit_increasedmeleedamage": "Added Melee Damage",
    "suit_increasedcombatmovementspeed": "Combat Movement Speed",
    "suit_improvedarmourrating": "Damage Resistance",
    "suit_improvedradar": "Enhanced Tracking",
    "suit_increasedammoreserves": "Extra Ammo Capacity",
    "suit_backpackcapacity": "Extra Backpack Capacity",
    "suit_increasedshieldregen": "Faster Shield Regen",
    "suit_increasedbatterycapacity": "Improved Battery Capacity",
    "suit_improvedjumpassist": "Improved Jump Assist",
    "suit_increasedo2capacity": "Increased Air Reserves",
    "suit_increasedsprintduration": "Increased Sprint Duration",
    "suit_nightvision": "Night Vision",
    "suit_quieterfootsteps": "Quieter Footsteps",
    "suit_reducedtoolbatteryconsumption": "Reduced Tool Battery Consumption",
}

WEAPON_MODS = {
    "weapon_suppression_unpressurised": "Audio Masking",
    "weapon_handling": "Faster Handling",
    "weapon_range": "Greater Range",
    "weapon_headshotdamage": "Headshot Damage",
    "weapon_accuracy": "Improved Hip Fire Accuracy",
    "weapon_clipsize": "Magazine Size",
    "weapon_suppression_pressurised": "Noise Suppressor",
    "weapon_reloadspeed": "Reload Speed",
    "weapon_scope": "Scope",
    "weapon_stability": "Stability",
    "weapon_backpackreloading": "Stowed Reloading",
}

SLOTS = {"PrimaryWeapon1": "Primary", "PrimaryWeapon2": "Primary", "SecondaryWeapon": "Secondary"}


def _readable(symbol, table, prefix):
    key = str(symbol or "").strip().casefold()
    if key in table:
        return table[key]
    text = re.sub(rf"^{prefix}_", "", key).replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else ""


def suit_name(symbol):
    """'explorationsuit_class5' -> ('Artemis Suit', 5); grade None if unknown."""
    key = str(symbol or "").strip().casefold()
    match = re.match(r"([a-z]+?)(?:_class(\d))?$", key)
    kind = match.group(1) if match else key
    grade = int(match.group(2)) if match and match.group(2) else None
    return SUITS.get(kind, kind.replace("_", " ").title() or "Suit"), grade


def loadout_summary(raw, timestamp=None):
    """A SuitLoadout event -> what Commander Record shows."""
    if not isinstance(raw, dict):
        return None
    name, grade = suit_name(raw.get("SuitName"))
    weapons = []
    for row in raw.get("Modules") or ():
        if not isinstance(row, dict):
            continue
        weapons.append({
            "slot": SLOTS.get(row.get("SlotName"), str(row.get("SlotName") or "")),
            "name": str(row.get("ModuleName_Localised") or "").strip()
            or _readable(row.get("ModuleName"), {}, "wpn"),
            "grade": row.get("Class"),
            "mods": [label for label in (_readable(mod, WEAPON_MODS, "weapon") for mod in row.get("WeaponMods") or ()) if label],
        })
    return {
        "suit": name, "grade": grade, "loadout": str(raw.get("LoadoutName") or "").strip(),
        "suit_mods": [label for label in (_readable(mod, SUIT_MODS, "suit") for mod in raw.get("SuitMods") or ()) if label],
        "weapons": weapons, "ts": timestamp or raw.get("timestamp"),
    }


def inventory_summary(raw, timestamp=None):
    """A Backpack event -> its contents by kind, largest first."""
    if not isinstance(raw, dict):
        return None
    out = {"ts": timestamp or raw.get("timestamp")}
    for key, source in (("items", "Items"), ("components", "Components"), ("consumables", "Consumables"), ("data", "Data")):
        counts = {}
        for row in raw.get(source) or ():
            if not isinstance(row, dict):
                continue
            label = str(row.get("Name_Localised") or "").strip() or _readable(row.get("Name"), {}, "")
            if label:
                counts[label] = counts.get(label, 0) + int(row.get("Count") or 0)
        out[key] = [{"name": name, "count": count}
                    for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]
    return out


def _section(statistics, name):
    for key, value in (statistics or {}).items():
        if str(key).casefold() == name.casefold() and isinstance(value, dict):
            return value
    return {}


def _value(section, key):
    try:
        return int(float(section.get(key)))
    except (TypeError, ValueError):
        return None


def on_foot_record(statistics):
    """The Statistics event's on-foot figures (shown only when the game sends them)."""
    exploration, combat, crime = (_section(statistics, name) for name in ("Exploration", "Combat", "Crime"))
    rows = [
        ("Distance walked", exploration, "OnFoot_Distance_Travelled", "m"),
        ("Settlements visited", exploration, "Settlements_Visited", ""),
        ("On-foot combat bonds", combat, "OnFoot_Combat_Bonds", ""),
        ("On-foot combat bond profits", combat, "OnFoot_Combat_Bonds_Profits", "cr"),
        ("Settlements defended", combat, "Settlement_Defended", ""),
        ("Settlements conquered", combat, "Settlement_Conquered", ""),
        ("Skimmers destroyed", combat, "OnFoot_Skimmers_Killed", ""),
        ("Scavengers killed", combat, "OnFoot_Scavs_Killed", ""),
        ("Vehicles destroyed on foot", combat, "OnFoot_Vehicles_Destroyed", ""),
        ("Ships destroyed on foot", combat, "OnFoot_Ships_Destroyed", ""),
        ("Settlements shut down", crime, "Settlements_State_Shutdown", ""),
    ]
    return [{"label": label, "value": _value(section, key), "unit": unit}
            for label, section, key, unit in rows if _value(section, key) is not None]


def exobiology_record(statistics):
    """The Statistics event's exobiology career."""
    exo = _section(statistics, "Exobiology")
    rows = [
        ("Organic data sold", "Organic_Data", ""),
        ("Organic data profits", "Organic_Data_Profits", "cr"),
        ("First logged", "First_Logged", ""),
        ("First logged profits", "First_Logged_Profits", "cr"),
        ("Genera encountered", "Organic_Genus_Encountered", ""),
        ("Species encountered", "Organic_Species_Encountered", ""),
        ("Variants encountered", "Organic_Variant_Encountered", ""),
        ("Systems with life", "Organic_Systems", ""),
        ("Planets with life", "Organic_Planets", ""),
        ("Genera analysed", "Organic_Genus", ""),
        ("Species analysed", "Organic_Species", ""),
    ]
    return [{"label": label, "value": _value(exo, key), "unit": unit}
            for label, key, unit in rows if _value(exo, key) is not None]
