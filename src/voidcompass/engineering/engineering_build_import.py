"""Adapted from ED Engineering Companion (GPL-3.0).

Strict, preview-first Coriolis, EDSY/SLEF engineering build import.
"""

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import url2pathname


class BuildImportError(ValueError):
    """A safe, actionable build import error for the UI."""


def empty_build_import_preview(warning=""):
    """Return one stable UI payload shape for idle and failed previews."""
    return {
        "compatible": False,
        "source": "",
        "shipType": "",
        "status": "PARTIAL",
        "rows": [],
        "warnings": [str(warning)] if warning else [],
        "recognized": 0,
        "partial": 0,
        "actionMessage": "",
        "actionError": False,
    }


# Frontier Journal machine names and established import variants resolve here
# to the exact canonical blueprint catalog name. Localized text is separate
# evidence, never a competing parallel mapping path.
JOURNAL_BLUEPRINT_NAMES = {
    "armouradvanced": "Heavy Duty",
    "armourexplosive": "Blast Resistant",
    "armourheavyduty": "Heavy Duty",
    "armourkinetic": "Kinetic Resistant",
    "armourlightweight": "Lightweight",
    "armourthermic": "Thermal Resistant",
    "chargeenhancedpowerdistributor": "Charge Enhanced",
    "dirty": "Dirty Drive Tuning",
    "dirtydrives": "Dirty Drive Tuning",
    "engineclean": "Clean Drive Tuning",
    "enginetuned": "Clean Drive Tuning",
    "enginedirty": "Dirty Drive Tuning",
    "enginereinforced": "Drive Strengthening",
    "fsdfastboot": "Faster FSD Boot Sequence",
    "fsdinterdictorexpanded": "Expanded FSD Interdictor Capture Arc",
    "fsdinterdictorlongrange": "Long Range FSD Interdictor",
    "fsdlongrange": "Increased FSD Range",
    "fsdshielded": "Shielded FSD",
    "heavydutyarmour": "Heavy Duty",
    "hullreinforcementheavyduty": "Heavy Duty Hull Reinforcement",
    "hullreinforcementexplosive": "Blast Resistant Hull Reinforcement",
    "hullreinforcementkinetic": "Kinetic Resistant Hull Reinforcement",
    "hullreinforcementlightweight": "Lightweight Hull Reinforcement",
    "hullreinforcementthermic": "Thermal Resistant Hull Reinforcement",
    "hullreinforcementadvanced": "Lightweight Hull Reinforcement",
    "increasedrange": "Increased FSD Range",
    "mischeatsinkcapacity": "Ammo Capacity",
    "miscchaffcapacity": "Ammo Capacity",
    "miscpointdefensecapacity": "Ammo Capacity",
    "misclightweight": "Lightweight",
    "miscreinforced": "Reinforced",
    "miscshielded": "Shielded",
    "overchargedpowerplant": "Overcharged",
    "powerdistributorenginefocused": "Engine Focused",
    "powerdistributorhighcapacity": "High Charge Capacity",
    "powerdistributorhighfrequency": "Charge Enhanced",
    "powerdistributorpriorityengines": "Engine Focused",
    "powerdistributorprioritysystems": "System Focused",
    "powerdistributorpriorityweapons": "Weapon Focused",
    "powerdistributorshielded": "Shielded",
    "powerdistributorsystemfocused": "System Focused",
    "powerdistributorweaponfocused": "Weapon Focused",
    "powerplantarmoured": "Armoured",
    "powerplantboosted": "Overcharged",
    "powerplantlowemissions": "Low Emissions",
    "powerplantstealth": "Low Emissions",
    "powerplantovercharged": "Overcharged",
    "mrpheavyduty": "Heavy Duty",
    "sensorexpanded": "Expanded Probe Scanning Radius",
    "sensorfastscan": "Fast Scanner",
    "sensorlightweight": "Light Weight Scanner",
    "sensorlongrange": "Long Range Scanner",
    "sensorwideangle": "Wide Angle Scanner",
    "sensorsensorlightweight": "Light Weight Scanner",
    "sensorsensorwideangle": "Wide Angle Scanner",
    "shieldboosterheavyduty": "Heavy Duty",
    "shieldboosterexplosive": "Blast Resistant",
    "shieldboosterkinetic": "Kinetic Resistant",
    "shieldboosterresistive": "Resistance Augmented",
    "shieldboosterthermic": "Thermal Resistant",
    "generatorlowpower": "Enhanced, Low Power Shields",
    "shieldgeneratorlowpower": "Enhanced, Low Power Shields",
    "shieldgeneratoroptimised": "Enhanced, Low Power Shields",
    "shieldgeneratorkinetic": "Kinetic Resistant Shields",
    "shieldgeneratorreinforced": "Reinforced Shields",
    "shieldgeneratorthermic": "Thermal Resistant Shields",
    "shieldcellbankrapid": "Rapid Charge",
    "shieldcellbankspecialised": "Specialised",
    "weaponefficient": "Efficient Weapon",
    "weaponfocused": "Focused Weapon",
    "weapondoubleshot": "Double Shot",
    "weaponhighcapacity": "High Capacity Magazine",
    "weaponlightweight": "Lightweight Mount",
    "weaponlongrange": "Long Range Weapon",
    "weaponovercharged": "Overcharged Weapon",
    "weaponrapidfire": "Rapid Fire Modification",
    "weaponreinforced": "Sturdy Mount",
    "weaponsturdy": "Sturdy Mount",
    "weaponshortrange": "Short Range Blaster",
    "weaponfocuseddistributor": "Weapon Focused",
}


# Frontier's Journal special_* identifiers are stable machine evidence but
# many suffixes do not resemble the displayed effect. Keep their canonical
# catalog names in one place; localized text remains independent evidence.
JOURNAL_EXPERIMENTAL_NAMES = {
    "specialblindingshell": "Dazzle Shell",
    "specialchokecanister": "Ion Disruptor",
    "specialdeepcutpayload": "Penetrator Payload",
    "specialdispersalfield": "Dispersal Field",
    "specialdistortionfield": "Inertial Impact",
    "specialdragmunitions": "Drag Munition",
    "specialemissivemunitions": "Emissive Munitions",
    "specialfeedbackcascade": "Feedback Cascade",
    "specialfeedbackcascadecooled": "Feedback Cascade",
    "specialforceshell": "Force Shell",
    "specialfsdinterrupt": "FSD Interrupt (Dumbfire only)",
    "specialhighyieldshell": "High Yield Shell",
    "speciallockbreaker": "Target Lock Breaker",
    "specialmasslock": "Mass Lock Munition",
    "specialoverloadmunitions": "Overload Munitions",
    "specialpenetratormunitions": "Penetrator Munitions (Dumbfire only)",
    "specialphasingsequence": "Phasing Sequence",
    "specialplasmaslug": "Plasma Slug",
    "specialradiantcanister": "Radiant Canister",
    "specialregenerationsequence": "Regeneration Sequence",
    "specialreverberatingcascade": "Reverberating Cascade",
    "specialscramblespectrum": "Scramble Spectrum",
    "specialscreeningshell": "Screening Shell",
    "specialshiftlockcanister": "Shift-Lock Canister",
    "specialsmartrounds": "Smart Rounds",
    "specialsuperpenetratorcooled": "Super Penetrator",
    "specialthermalcascade": "Thermal Cascade",
    "specialthermalconduit": "Thermal Conduit",
    "specialthermalshock": "Thermal Shock",
    "specialthermalvent": "Thermal Vent",
    "specialweaponefficient": "Flow Control",
    "specialautoloader": "Auto Loader",
    "specialarmourchunky": "Deep Plating",
    "specialarmourexplosive": "Layered Plating",
    "specialarmourkinetic": "Angled Plating",
    "specialarmourthermic": "Reflective Plating",
    "specialenginecooled": "Thermal Spread",
    "specialenginelightweight": "Stripped Down",
    "specialengineoverloaded": "Drag Drives",
    "specialenginehaulage": "Drive Distributors",
    "specialenginetoughened": "Double Braced",
    "specialcorrosiveshell": "Corrosive Shell",
    "specialfsdcooled": "Thermal Spread",
    "specialfsdfuelcapacity": "Deep Charge",
    "specialfsdheavy": "Mass Manager",
    "specialfsdlightweight": "Stripped Down",
    "specialfsdtoughened": "Double Braced",
    "specialhullreinforcementchunky": "Deep Plating",
    "specialhullreinforcementexplosive": "Layered Plating",
    "specialhullreinforcementkinetic": "Angled Plating",
    "specialhullreinforcementthermic": "Reflective Plating",
    "specialplasmaslugcooled": "Plasma Slug",
    "specialpowerdistributorcapacity": "Cluster Capacitor",
    "specialpowerdistributorfast": "Super Conduits",
    "specialpowerdistributorlightweight": "Stripped Down",
    "specialpowerdistributorefficient": "Flow Control",
    "specialpowerdistributortoughened": "Double Braced",
    "specialpowerplantcooled": "Thermal Spread",
    "specialpowerplanthighcharge": "Monstered",
    "specialpowerplantlightweight": "Stripped Down",
    "specialpowerplanttoughened": "Double Braced",
    "specialshieldboosterchunky": "Super Capacitor",
    "specialshieldboosterdoublebraced": "Double Braced",
    "specialshieldboosterexplosive": "Blast Block",
    "specialshieldboosterflowcontrol": "Flow Control",
    "specialshieldboosterkinetic": "Force Block",
    "specialshieldboosterthermic": "Thermo Block",
    "specialshieldboosterefficient": "Flow Control",
    "specialshieldboostertoughened": "Double Braced",
    "specialshieldcellefficient": "Flow Control",
    "specialshieldcellgradual": "Recycling Cells",
    "specialshieldcelllightweight": "Stripped Down",
    "specialshieldcelloversized": "Boss Cells",
    "specialshieldcelltoughened": "Double Braced",
    "specialshieldhighcapacity": "Hi-cap",
    "specialshieldkinetic": "Force Block",
    "specialshieldlightweight": "Stripped Down",
    "specialshieldlowdraw": "Lo-draw",
    "specialshieldmultiweave": "Multi-weave",
    "specialshieldregenerative": "Fast Charge",
    "specialshieldthermic": "Thermo Block",
    "specialshieldefficient": "Lo-draw",
    "specialshieldhealth": "Hi-cap",
    "specialshieldresistive": "Multi-weave",
    "specialshieldtoughened": "Double Braced",
    "specialweapondamage": "Oversized",
    "specialweaponlightweight": "Stripped Down",
    "specialweaponrateoffire": "Multi-Servos",
    "specialincendiaryrounds": "Incendiary Rounds",
    "specialweaponstabilised": "Flow Control",
    "specialweapontoughened": "Double Braced",
}

EXPERIMENTAL_FAMILY_WORDS = (
    "armour", "engine", "fsd", "powerdistributor", "powerplant",
    "shieldbooster", "shieldgenerator", "weapon",
)

# Stable Coriolis/Journal ship symbols whose internal IDs do not normalize to
# the player-facing fleet type. Values are normalized display-name keys.
SHIP_ALIASES = {
    "asp": "aspexplorer",
    "diamondback": "diamondbackscout",
    "diamondbackxl": "diamondbackexplorer",
    "empirecourier": "imperialcourier",
    "empireeagle": "imperialeagle",
    "empiretrader": "imperialclipper",
    "federationcorvette": "federalcorvette",
    "federationdropship": "federaldropship",
    "federationdropshipmkii": "federalassaultship",
    "federationgunship": "federalgunship",
    "independanttrader": "keelback",
    "kraitlight": "kraitphantom",
    "type6": "type6transporter",
    "type7": "type7transporter",
    "type8": "type8transporter",
    "type9": "type9heavy",
    "type9military": "type10defender",
    "typex": "alliancechieftain",
    "typex2": "alliancecrusader",
    "typex3": "alliancechallenger",
}

BLUEPRINT_NOISE_WORDS = frozenset({
    "blaster", "drive", "hull", "magazine", "modification", "mount",
    "reinforcement", "scanner", "shield", "shields", "tuning", "weapon",
})


def _key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _blueprint_keys(value):
    raw = _key(value)
    canonical = JOURNAL_BLUEPRINT_NAMES.get(raw, "")
    alias = _key(canonical) if canonical else raw
    words = re.findall(r"[a-z0-9]+", str(value or "").casefold())
    reduced = "".join(word for word in words if word not in BLUEPRINT_NOISE_WORDS)
    return {key for key in (raw, alias, reduced) if key}


def _read_input(value):
    text = str(value or "").strip()
    if not text:
        raise BuildImportError("Paste JSON/SLEF or enter a local JSON file path.")
    if text.casefold().startswith("file:"):
        parsed = urlparse(text)
        if parsed.scheme.casefold() != "file":
            raise BuildImportError("Only local file URLs are accepted.")
        local_path = url2pathname(unquote(parsed.path))
        if parsed.netloc:
            local_path = f"//{parsed.netloc}{local_path}"
        if re.match(r"^/[a-zA-Z]:/", local_path):
            local_path = local_path[1:]
        text = local_path
    looks_like_path = (
        len(text) < 2048 and "\n" not in text
        and not text.lstrip().startswith(("{", "[", "http://", "https://"))
    )
    if looks_like_path:
        candidate = Path(text.strip('"'))
        try:
            if candidate.is_file():
                if candidate.suffix.casefold() != ".json":
                    raise BuildImportError("Only local .json build files are accepted.")
                text = candidate.read_text(encoding="utf-8-sig")
            elif candidate.suffix.casefold() == ".json":
                raise BuildImportError(f"Build file does not exist: {candidate}")
        except OSError as exc:
            raise BuildImportError(f"Build file cannot be read: {exc}") from None
    if text.startswith(("http://", "https://")):
        parsed = urlparse(text)
        embedded = []
        for values in parse_qs(parsed.query).values():
            embedded.extend(values)
        fragment = unquote(parsed.fragment or "").strip()
        if fragment.startswith(("{", "[")):
            embedded.append(fragment)
        text = next(
            (unquote(item).strip() for item in embedded
             if unquote(item).lstrip().startswith(("{", "["))),
            "",
        )
        if not text:
            raise BuildImportError(
                "This share link has no deterministic JSON/SLEF payload. "
                "Export JSON from Coriolis or SLEF from EDSY and paste it here."
            )
    try:
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise BuildImportError(f"Invalid build JSON: {exc}") from None


def _flatten_components(value, path=""):
    rows = []
    if isinstance(value, list):
        for index, child in enumerate(value, 1):
            rows.extend(_flatten_components(child, f"{path}{index}"))
    elif isinstance(value, dict):
        module_keys = {
            "item", "module", "name", "id", "blueprint", "engineering",
            "experimental", "experimentaleffect", "blueprintname", "special",
            "specialname", "edname", "group",
        }
        if module_keys.intersection({str(key).casefold() for key in value}):
            row = dict(value)
            row.setdefault("Slot", path or str(value.get("slot") or "module"))
            row.setdefault("_SourcePath", path)
            rows.append(row)
        else:
            for key, child in value.items():
                rows.extend(_flatten_components(child, f"{path}/{key}".strip("/")))
    return rows


def _builds(document):
    values = document if isinstance(document, list) else [document]
    builds = []
    for value in values:
        if not isinstance(value, dict):
            continue
        data = value.get("data") if isinstance(value.get("data"), dict) else value
        ship = data.get("Ship") or data.get("ship")
        if isinstance(ship, dict):
            ship = ship.get("name") or ship.get("Name") or ship.get("id")
        modules = data.get("Modules") or data.get("modules")
        source = "SLEF" if isinstance(value.get("header"), dict) else "JSON"
        if isinstance(modules, list) and ship:
            builds.append({"source": source, "ship": ship, "modules": modules})
            continue
        components = data.get("components") or data.get("Components")
        if ship and isinstance(components, (dict, list)):
            builds.append({
                "source": "Coriolis JSON", "ship": ship,
                "modules": _flatten_components(components),
            })
    if not builds:
        raise BuildImportError(
            "No supported Coriolis JSON, Journal Loadout, or EDSY/SLEF build found."
        )
    return builds


def _engineering(module):
    nested = module.get("Engineering") or module.get("engineering")
    nested = nested if isinstance(nested, dict) else {}
    blueprint = module.get("Blueprint") or module.get("blueprint")
    blueprint = blueprint if isinstance(blueprint, dict) else {}
    experimental = module.get("Experimental") or module.get("experimental")
    blueprint_name = (
        nested.get("BlueprintName") or nested.get("blueprintName")
        or module.get("BlueprintName") or module.get("blueprintName")
        or blueprint.get("fdname") or blueprint.get("FdName")
        or blueprint.get("edname") or blueprint.get("EdName")
        or blueprint.get("name") or blueprint.get("Name")
        or blueprint.get("label") or blueprint.get("type")
        or blueprint.get("Type") or blueprint.get("id")
        or (blueprint if isinstance(blueprint, str) else "")
    )
    sources = (nested, module, blueprint)
    localized_blueprint = next((
        source.get(key)
        for source in sources
        for key in (
            "BlueprintName_Localised", "blueprintName_Localised",
            "blueprint_name_localised",
        )
        if source.get(key) not in (None, "")
    ), "")
    blueprint_evidence = []
    for value in (blueprint_name, localized_blueprint):
        text = str(value or "").strip()
        if text and text not in blueprint_evidence:
            blueprint_evidence.append(text)
    grade = (
        nested.get("Level") or nested.get("level") or nested.get("Grade")
        or nested.get("grade") or module.get("Level") or module.get("Grade")
        or blueprint.get("grade") or blueprint.get("level") or 0
    )
    # Coriolis ship-loadout v4 nests the experimental under blueprint.special.
    experimental_name = next((
        source.get(key)
        for source in sources
        for key in (
            "ExperimentalEffect", "experimentalEffect", "experimental_effect",
            "SpecialName", "specialName", "special_name", "Special", "special",
            "SpecialEdName", "specialEdName", "special_edname",
        )
        if source.get(key) not in (None, "")
    ), experimental)
    if isinstance(experimental_name, dict):
        experimental_name = next((
            experimental_name.get(key) for key in (
                "name", "Name", "specialName", "SpecialName", "label", "Label",
                "fdname", "fdName", "FdName", "edname", "edName", "EdName",
                "id", "Id", "uuid", "UUID",
            ) if experimental_name.get(key) not in (None, "")
        ), "")
    try:
        grade = int(grade or 0)
    except (TypeError, ValueError):
        grade = 0
    localized = next((
        source.get(key)
        for source in sources
        for key in (
            "ExperimentalEffect_Localised", "experimentalEffect_Localised",
            "experimental_effect_localised",
        )
        if source.get(key) not in (None, "")
    ), "")
    evidence = []
    for value in (experimental_name, localized):
        text = str(value or "").strip()
        if text and text not in evidence:
            evidence.append(text)
    return blueprint_evidence, grade, evidence


def _effect_keys(effect):
    keys = set()
    for field in ("Name", "ExperimentalId", "CoriolisGuid", "EdName", "edname"):
        value = _key(effect.get(field))
        if value:
            keys.add(value)
            if field == "ExperimentalId" and "::" in str(effect.get(field)):
                keys.add(_key(str(effect.get(field)).rsplit("::", 1)[-1]))
    return keys


def _experimental_keys(value):
    raw = _key(value)
    if not raw:
        return set()
    canonical = JOURNAL_EXPERIMENTAL_NAMES.get(raw, "")
    keys = {raw, _key(canonical) if canonical else raw}
    if raw.startswith("special"):
        suffix = raw[len("special"):]
        keys.add(suffix)
        for family in EXPERIMENTAL_FAMILY_WORDS:
            family_key = _key(family)
            if suffix.startswith(family_key):
                keys.add(suffix[len(family_key):])
    return {key for key in keys if key}


def resolve_experimental_name(value, experimentals, localized=""):
    """Return one readable canonical effect name from machine/localized evidence."""
    for evidence in (value, localized):
        keys = _experimental_keys(evidence)
        names = {
            str(effect.get("Name") or "").strip()
            for effect in (experimentals or [])
            if isinstance(effect, dict) and keys.intersection(_effect_keys(effect))
            and str(effect.get("Name") or "").strip()
        }
        if len(names) == 1:
            return next(iter(names))
    localized_text = str(localized or "").strip()
    if localized_text and not (
        localized_text.startswith("$") or _key(localized_text).startswith("special")
    ):
        return localized_text
    raw_text = str(value or "").strip()
    if raw_text and not (
        raw_text.startswith("$") or _key(raw_text).startswith("special")
    ):
        return raw_text
    return ""


def _module_identity(module):
    return str(
        module.get("Item") or module.get("item") or module.get("module")
        or module.get("name") or module.get("Name")
        or module.get("group") or module.get("Group")
        or module.get("id") or module.get("_SourcePath") or ""
    )


def _ship_key(value):
    key = _key(value)
    return SHIP_ALIASES.get(key, key)


def _module_types(module_id, blueprint_types, module_matcher):
    matches = {
        module_type for module_type in blueprint_types
        if module_matcher(module_id, module_type)
    }
    if matches:
        return matches
    module_key = _key(module_id)
    textual = {
        module_type for module_type in blueprint_types
        if _key(module_type) and _key(module_type) in module_key
    }
    longest = max((len(_key(value)) for value in textual), default=0)
    return {value for value in textual if len(_key(value)) == longest}


def _canonical_import_slot(value, physical_slots, source=""):
    """Resolve an external slot only when the hull schema makes it deterministic."""
    slots = [row for row in (physical_slots or []) if isinstance(row, dict)]
    if not slots:
        # Backwards-compatible for callers without a hull schema. The desktop
        # controller always supplies one before an import can be applied.
        return str(value or "").strip(), ""
    raw = str(value or "").strip()
    exact = {
        _key(row.get("slot")): str(row.get("slot") or "")
        for row in slots if row.get("slot")
    }
    if _key(raw) in exact:
        return exact[_key(raw)], ""
    legacy_optional = re.fullmatch(
        r"Slot(\d+)_Size(\d+)", raw, re.IGNORECASE
    )
    if legacy_optional:
        optional = [
            row for row in slots
            if row.get("group") == "OPTIONAL INTERNALS"
        ]
        position = int(legacy_optional.group(1))
        declared_size = int(legacy_optional.group(2))
        if 1 <= position <= len(optional):
            candidate = optional[position - 1]
            if int(candidate.get("slotSize") or 0) == declared_size:
                return str(candidate.get("slot") or ""), ""
    legacy_hardpoint = re.fullmatch(
        r"(Small|Medium|Large|Huge)Hardpoint(\d+)", raw, re.IGNORECASE
    )
    if legacy_hardpoint:
        sizes = {"small": 1, "medium": 2, "large": 3, "huge": 4}
        wanted_size = sizes[legacy_hardpoint.group(1).casefold()]
        position = int(legacy_hardpoint.group(2))
        candidates = [
            row for row in slots
            if row.get("group") == "HARDPOINTS"
            and int(row.get("slotSize") or 0) == wanted_size
        ]
        if 1 <= position <= len(candidates):
            return str(candidates[position - 1].get("slot") or ""), ""
    if str(source or "").casefold() != "coriolis json":
        return "", f"Slot '{raw or '?'}' is not present on the selected hull."

    tokens = [token for token in re.split(r"[/\\.\[\]]+", raw) if token]
    keys = [_key(token) for token in tokens]
    joined = "".join(keys)
    core_aliases = {
        "armour": "Armour", "armor": "Armour",
        "powerplant": "PowerPlant", "thrusters": "MainEngines",
        "mainengines": "MainEngines", "frameshiftdrive": "FrameShiftDrive",
        "fsd": "FrameShiftDrive", "lifesupport": "LifeSupport",
        "powerdistributor": "PowerDistributor", "sensors": "Radar",
        "radar": "Radar", "fueltank": "FuelTank",
    }
    for alias, slot in core_aliases.items():
        if alias in joined and _key(slot) in exact:
            return exact[_key(slot)], ""

    groups = {
        "optional": [row for row in slots if row.get("group") == "OPTIONAL INTERNALS"],
        "internal": [row for row in slots if row.get("group") == "OPTIONAL INTERNALS"],
        "hardpoint": [row for row in slots if row.get("group") == "HARDPOINTS"],
        "hardpoints": [row for row in slots if row.get("group") == "HARDPOINTS"],
        "utility": [row for row in slots if row.get("group") == "UTILITY MOUNTS"],
        "utilities": [row for row in slots if row.get("group") == "UTILITY MOUNTS"],
    }
    for marker, candidates in groups.items():
        marker_index = next((i for i, key in enumerate(keys) if marker in key), -1)
        if marker_index < 0:
            continue
        number = next((
            int(match.group(1)) for token in tokens[marker_index:]
            for match in [re.search(r"(\d+)", token)] if match
        ), 0)
        if 1 <= number <= len(candidates):
            return str(candidates[number - 1].get("slot") or ""), ""
        return "", (
            f"Coriolis path '{raw}' has no deterministic {marker} slot "
            "on the selected hull."
        )
    return "", f"Coriolis path '{raw or '?'}' cannot be mapped to a physical hull slot."


def _resolve_blueprint_group(evidence, groups, module_types):
    """Resolve Journal machine evidence first, then localized fallback text."""
    for value in evidence:
        wanted = _blueprint_keys(value)
        candidates = [
            group for group in groups
            if wanted.intersection(_blueprint_keys(group[1]))
            and (not module_types or group[0] in module_types)
        ]
        if len(candidates) == 1:
            return candidates[0]
    return None


def preview_build(value, target_ship_type, blueprints, experimentals,
                  module_matcher, physical_slots=None):
    builds = _builds(_read_input(value))
    target_key = _ship_key(target_ship_type)
    compatible = [build for build in builds if _ship_key(build["ship"]) == target_key]
    selected = compatible[0] if len(compatible) == 1 else None
    if selected is None:
        found = ", ".join(str(build["ship"]) for build in builds)
        warning = (
            f"The import contains {len(compatible)} builds matching "
            f"'{target_ship_type}'. Export exactly one ship build."
            if len(compatible) > 1 else
            f"Build ship '{found}' is incompatible with target ship "
            f"'{target_ship_type}'."
        )
        return {
            "compatible": False, "source": builds[0]["source"],
            "shipType": str(builds[0]["ship"]), "rows": [], "recognized": 0,
            "partial": 0, "status": "PARTIAL",
            "warnings": [warning],
        }
    groups = {}
    for record in blueprints if isinstance(blueprints, list) else []:
        if not isinstance(record, dict) or record.get("Grade") is None:
            continue
        group = (str(record.get("Type") or ""), str(record.get("Name") or ""))
        groups.setdefault(group, []).append(record)
    blueprint_types = {group[0] for group in groups if group[0]}
    rows, warnings = [], []
    installed_by_slot = {
        str(row.get("slot") or ""): row
        for row in (physical_slots or []) if isinstance(row, dict)
    }
    for position, module in enumerate(selected["modules"], 1):
        if not isinstance(module, dict):
            continue
        source_slot = str(
            module.get("Slot") or module.get("slot")
            or module.get("_SourcePath") or ""
        )
        slot, slot_issue = _canonical_import_slot(
            source_slot, physical_slots, selected["source"]
        )
        module_id = _module_identity(module)
        installed = installed_by_slot.get(slot, {})
        installed_module = str(installed.get("moduleId") or "")
        module_change = bool(
            slot and module_id
            and _key(installed_module) != _key(module_id)
        )
        blueprint_evidence, grade, experimental_evidence = _engineering(module)
        blueprint_name = next(iter(blueprint_evidence), "")
        experimental_name = next(iter(experimental_evidence), "")
        types = _module_types(module_id, blueprint_types, module_matcher)
        # SLEF exposes intrinsic modifications on Guardian, Human Tech Broker,
        # pre-engineered, and other special modules through the same fields as
        # ordinary engineering. If the module has no engineerable family, its
        # installed properties are not a craftable wishlist recipe. Preserve
        # the module replacement without inventing an engineering plan.
        if (blueprint_evidence or experimental_evidence) and not types:
            rows.append({
                "status": "ready" if module_change else "ignored", "slot": slot,
                "sourceSlot": source_slot, "slotBound": bool(slot),
                "module": module_id or "Unknown module", "blueprint": "",
                "grade": 0, "experimental": "", "planMode": (
                    "module_only" if module_change else ""
                ),
                "moduleChange": module_change,
                "installedModule": installed_module,
                "desiredModule": module_id,
                "intrinsicEngineering": True,
                "detail": (
                    "Module replacement tracked; built-in or non-craftable "
                    "modification is not added as an engineering recipe."
                    if module_change else
                    "Built-in or non-craftable modification; installed module "
                    "already matches."
                ),
            })
            continue
        if not blueprint_evidence and not experimental_evidence:
            rows.append({
                "status": "ready" if module_change else "ignored", "slot": slot,
                "sourceSlot": source_slot, "slotBound": bool(slot),
                "module": module_id or "Unknown module", "blueprint": "",
                "grade": 0, "experimental": "",
                "planMode": "module_only" if module_change else "",
                "moduleChange": module_change,
                "installedModule": installed_module,
                "desiredModule": module_id,
                "detail": (
                    "Installed module differs; module replacement will be tracked."
                    if module_change else
                    "No engineering data and installed module already matches."
                ),
            })
            continue
        blueprint_group = _resolve_blueprint_group(
            blueprint_evidence, groups, types
        )
        effect_candidates = []
        effect_keys = set()
        for value in experimental_evidence:
            effect_keys.update(_experimental_keys(value))
        if effect_keys:
            for effect in experimentals if isinstance(experimentals, list) else []:
                if not isinstance(effect, dict) or not (
                    effect_keys.intersection(_effect_keys(effect))
                ):
                    continue
                supported = {str(item) for item in effect.get("ModuleTypes", []) or []}
                if not types or not supported or supported.intersection(types):
                    effect_candidates.append(effect)
        effect = effect_candidates[0] if len(effect_candidates) == 1 else None
        installed_blueprint = str(installed.get("engineeringBlueprint") or "")
        installed_grade = int(installed.get("engineeringGrade") or 0)
        installed_quality = max(0.0, min(1.0, float(
            installed.get("engineeringQuality") or 0
        )))
        installed_quality_known = bool(
            installed.get("engineeringQualityKnown")
        )
        blueprint_matches_installed = bool(
            blueprint_group and not module_change and installed_grade > 0
            and _blueprint_keys(installed_blueprint).intersection(
                _blueprint_keys(blueprint_group[1])
            )
        )
        # Loadout reports the installed grade, but not its within-grade
        # Quality. Treat only the preceding grade as certainly complete; the
        # next EngineerCraft supplies authoritative progress for this grade.
        if not blueprint_matches_installed:
            current_grade = 0
        elif installed_grade > grade:
            current_grade = grade
        elif installed_quality_known:
            current_grade = min(installed_grade, grade)
        else:
            current_grade = max(0, min(installed_grade, grade) - 1)
        grade_progress = {}
        crafts_completed = {}
        if (
            blueprint_matches_installed and installed_quality_known
            and 0 < installed_grade <= grade
        ):
            planned_rolls = installed_grade
            grade_progress[str(installed_grade)] = installed_quality
            crafts_completed[str(installed_grade)] = max(
                0, min(
                    planned_rolls,
                    round(installed_quality * planned_rolls),
                ),
            )
        installed_experimental = str(installed.get("experimentalEffect") or "")
        experimental_complete = bool(
            effect and not module_change and installed_experimental
            and _experimental_keys(installed_experimental).intersection(
                _effect_keys(effect)
            )
        )
        issues = []
        if slot_issue:
            issues.append(slot_issue)
        elif not slot:
            issues.append("Module slot is missing; binding will require Journal evidence.")
        if blueprint_name and not blueprint_group:
            issues.append(
                f"Blueprint '{blueprint_name}' is unknown or ambiguous for '{module_id}'."
            )
        if blueprint_group:
            maximum = max(int(item.get("Grade", 0) or 0)
                          for item in groups[blueprint_group])
            if not 1 <= grade <= maximum:
                issues.append(
                    f"Grade G{grade or '?'} is invalid for {blueprint_group[1]} "
                    f"(maximum G{maximum})."
                )
                blueprint_group = None
        if experimental_name and not effect:
            issues.append(
                f"Experimental '{experimental_name}' is unknown or ambiguous for '{module_id}'."
            )
        if not types:
            issues.append(f"Module '{module_id}' cannot be mapped to an engineering family.")
            blueprint_group = None
            effect = None
        if issues:
            warnings.extend(f"{slot or source_slot or '?'}: {issue}" for issue in issues)
        plan_mode = (
            "combined" if blueprint_group and effect else
            "grade_only" if blueprint_group else
            "experimental_only" if effect else ""
        )
        slot_bound = bool(slot)
        row_status = "blocked" if not slot_bound else ("partial" if issues else "ready")
        rows.append({
            "status": row_status,
            "slot": slot, "sourceSlot": source_slot, "slotBound": slot_bound,
            "module": module_id or "Unknown module",
            "moduleType": blueprint_group[0] if blueprint_group else (
                next(iter(types)) if len(types) == 1 else ""
            ),
            "blueprint": blueprint_group[1] if blueprint_group else blueprint_name,
            "blueprintGroup": (
                f"{blueprint_group[0]}\u241f{blueprint_group[1]}"
                if blueprint_group else ""
            ),
            "grade": grade if blueprint_group else 0,
            "experimental": str(effect.get("Name") or "") if effect else experimental_name,
            "experimentalId": str(
                effect.get("ExperimentalId") or effect.get("Name") or ""
            ) if effect else "",
            "planMode": plan_mode,
            "currentGrade": current_grade,
            "gradeProgress": grade_progress,
            "craftsCompleted": crafts_completed,
            "installedBlueprint": installed_blueprint,
            "installedExperimental": installed_experimental,
            "experimentalComplete": experimental_complete,
            "moduleChange": module_change,
            "installedModule": installed_module,
            "desiredModule": module_id,
            "detail": (
                "; ".join(issues) if issues else
                "Complete engineering data; ready for wishlist import."
            ),
        })
    recognized = sum(
        bool(row.get("planMode")) and bool(row.get("slotBound")) for row in rows
    )
    module_changes = sum(bool(row.get("moduleChange")) for row in rows)
    partial = sum(row.get("status") in {"partial", "blocked"} for row in rows)
    return {
        "compatible": True, "source": selected["source"],
        "shipType": str(selected["ship"]), "rows": rows,
        "recognized": recognized,
        "partial": partial,
        "status": "PARTIAL" if partial or warnings else "COMPLETE",
        "warnings": list(dict.fromkeys(warnings)),
        "moduleChanges": module_changes,
    }
