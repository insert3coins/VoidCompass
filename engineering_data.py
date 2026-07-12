"""Canonical engineering reference data and blueprint planning helpers.

Material symbols are the internal names written by Elite Dangerous journals.
The catalogue covers standard ship-engineering materials plus Guardian and
Thargoid materials that can appear in the same Materials event.
"""

from __future__ import annotations

import math


GRADE_CAP = {1: 300, 2: 250, 3: 200, 4: 150, 5: 100}
ROLLS_PER_GRADE = {1: 2, 2: 2, 3: 3, 4: 4, 5: 5}


# symbol, display name, category, family, grade
_MATERIAL_ROWS = [
    # Raw trader columns
    ("carbon", "Carbon", "raw", "raw 1", 1), ("vanadium", "Vanadium", "raw", "raw 1", 2),
    ("niobium", "Niobium", "raw", "raw 1", 3), ("yttrium", "Yttrium", "raw", "raw 1", 4),
    ("phosphorus", "Phosphorus", "raw", "raw 2", 1), ("chromium", "Chromium", "raw", "raw 2", 2),
    ("molybdenum", "Molybdenum", "raw", "raw 2", 3), ("technetium", "Technetium", "raw", "raw 2", 4),
    ("sulphur", "Sulphur", "raw", "raw 3", 1), ("manganese", "Manganese", "raw", "raw 3", 2),
    ("cadmium", "Cadmium", "raw", "raw 3", 3), ("ruthenium", "Ruthenium", "raw", "raw 3", 4),
    ("iron", "Iron", "raw", "raw 4", 1), ("zinc", "Zinc", "raw", "raw 4", 2),
    ("tin", "Tin", "raw", "raw 4", 3), ("selenium", "Selenium", "raw", "raw 4", 4),
    ("nickel", "Nickel", "raw", "raw 5", 1), ("germanium", "Germanium", "raw", "raw 5", 2),
    ("tungsten", "Tungsten", "raw", "raw 5", 3), ("tellurium", "Tellurium", "raw", "raw 5", 4),
    ("rhenium", "Rhenium", "raw", "raw 6", 1), ("arsenic", "Arsenic", "raw", "raw 6", 2),
    ("mercury", "Mercury", "raw", "raw 6", 3), ("polonium", "Polonium", "raw", "raw 6", 4),
    ("lead", "Lead", "raw", "raw 7", 1), ("zirconium", "Zirconium", "raw", "raw 7", 2),
    ("boron", "Boron", "raw", "raw 7", 3), ("antimony", "Antimony", "raw", "raw 7", 4),
    # Manufactured trader columns
    ("gridresistors", "Grid Resistors", "manufactured", "capacitors", 1),
    ("hybridcapacitors", "Hybrid Capacitors", "manufactured", "capacitors", 2),
    ("electrochemicalarrays", "Electrochemical Arrays", "manufactured", "capacitors", 3),
    ("polymercapacitors", "Polymer Capacitors", "manufactured", "capacitors", 4),
    ("militarysupercapacitors", "Military Supercapacitors", "manufactured", "capacitors", 5),
    ("crystalshards", "Crystal Shards", "manufactured", "crystals", 1),
    ("uncutfocuscrystals", "Flawed Focus Crystals", "manufactured", "crystals", 2),
    ("focuscrystals", "Focus Crystals", "manufactured", "crystals", 3),
    ("refinedfocuscrystals", "Refined Focus Crystals", "manufactured", "crystals", 4),
    ("exquisitefocuscrystals", "Exquisite Focus Crystals", "manufactured", "crystals", 5),
    ("temperedalloys", "Tempered Alloys", "manufactured", "thermic", 1),
    ("heatresistantceramics", "Heat Resistant Ceramics", "manufactured", "thermic", 2),
    ("precipitatedalloys", "Precipitated Alloys", "manufactured", "thermic", 3),
    ("thermicalloys", "Thermic Alloys", "manufactured", "thermic", 4),
    ("militarygradealloys", "Military Grade Alloys", "manufactured", "thermic", 5),
    ("basicconductors", "Basic Conductors", "manufactured", "conductive", 1),
    ("conductivecomponents", "Conductive Components", "manufactured", "conductive", 2),
    ("conductiveceramics", "Conductive Ceramics", "manufactured", "conductive", 3),
    ("conductivepolymers", "Conductive Polymers", "manufactured", "conductive", 4),
    ("biotechconductors", "Biotech Conductors", "manufactured", "conductive", 5),
    ("mechanicalscrap", "Mechanical Scrap", "manufactured", "mechanical", 1),
    ("mechanicalequipment", "Mechanical Equipment", "manufactured", "mechanical", 2),
    ("mechanicalcomponents", "Mechanical Components", "manufactured", "mechanical", 3),
    ("configurablecomponents", "Configurable Components", "manufactured", "mechanical", 4),
    ("improvisedcomponents", "Improvised Components", "manufactured", "mechanical", 5),
    ("heatconductionwiring", "Heat Conduction Wiring", "manufactured", "heat", 1),
    ("heatdispersionplate", "Heat Dispersion Plate", "manufactured", "heat", 2),
    ("heatexchangers", "Heat Exchangers", "manufactured", "heat", 3),
    ("heatvanes", "Heat Vanes", "manufactured", "heat", 4),
    ("protoheatradiators", "Proto Heat Radiators", "manufactured", "heat", 5),
    ("wornshieldemitters", "Worn Shield Emitters", "manufactured", "shielding", 1),
    ("shieldemitters", "Shield Emitters", "manufactured", "shielding", 2),
    ("shieldingsensors", "Shielding Sensors", "manufactured", "shielding", 3),
    ("compoundshielding", "Compound Shielding", "manufactured", "shielding", 4),
    ("imperialshielding", "Imperial Shielding", "manufactured", "shielding", 5),
    ("compactcomposites", "Compact Composites", "manufactured", "composite", 1),
    ("filamentcomposites", "Filament Composites", "manufactured", "composite", 2),
    ("highdensitycomposites", "High Density Composites", "manufactured", "composite", 3),
    ("fedproprietarycomposites", "Proprietary Composites", "manufactured", "composite", 4),
    ("fedcorecomposites", "Core Dynamics Composites", "manufactured", "composite", 5),
    ("salvagedalloys", "Salvaged Alloys", "manufactured", "alloys", 1),
    ("galvanisingalloys", "Galvanising Alloys", "manufactured", "alloys", 2),
    ("phasealloys", "Phase Alloys", "manufactured", "alloys", 3),
    ("protolightalloys", "Proto Light Alloys", "manufactured", "alloys", 4),
    ("protoradiolicalloys", "Proto Radiolic Alloys", "manufactured", "alloys", 5),
    ("chemicalstorageunits", "Chemical Storage Units", "manufactured", "chemical", 1),
    ("chemicalprocessors", "Chemical Processors", "manufactured", "chemical", 2),
    ("chemicaldistillery", "Chemical Distillery", "manufactured", "chemical", 3),
    ("chemicalmanipulators", "Chemical Manipulators", "manufactured", "chemical", 4),
    ("pharmaceuticalisolators", "Pharmaceutical Isolators", "manufactured", "chemical", 5),
    # Encoded trader columns
    ("legacyfirmware", "Specialised Legacy Firmware", "encoded", "firmware", 1),
    ("consumerfirmware", "Modified Consumer Firmware", "encoded", "firmware", 2),
    ("industrialfirmware", "Cracked Industrial Firmware", "encoded", "firmware", 3),
    ("securityfirmware", "Security Firmware Patch", "encoded", "firmware", 4),
    ("embeddedfirmware", "Modified Embedded Firmware", "encoded", "firmware", 5),
    ("encryptedfiles", "Unusual Encrypted Files", "encoded", "encryption", 1),
    ("encryptioncodes", "Tagged Encryption Codes", "encoded", "encryption", 2),
    ("symmetrickeys", "Open Symmetric Keys", "encoded", "encryption", 3),
    ("encryptionarchives", "Atypical Encryption Archives", "encoded", "encryption", 4),
    ("adaptiveencryptors", "Adaptive Encryptors Capture", "encoded", "encryption", 5),
    ("bulkscandata", "Anomalous Bulk Scan Data", "encoded", "archives", 1),
    ("scanarchives", "Unidentified Scan Archives", "encoded", "archives", 2),
    ("scandatabanks", "Classified Scan Databanks", "encoded", "archives", 3),
    ("encodedscandata", "Divergent Scan Data", "encoded", "archives", 4),
    ("classifiedscandata", "Classified Scan Fragment", "encoded", "archives", 5),
    ("disruptedwakeechoes", "Atypical Disrupted Wake Echoes", "encoded", "wake scans", 1),
    ("fsdtelemetry", "Anomalous FSD Telemetry", "encoded", "wake scans", 2),
    ("wakesolutions", "Strange Wake Solutions", "encoded", "wake scans", 3),
    ("hyperspacetrajectories", "Eccentric Hyperspace Trajectories", "encoded", "wake scans", 4),
    ("dataminedwake", "Datamined Wake Exceptions", "encoded", "wake scans", 5),
    ("scrambledemissiondata", "Exceptional Scrambled Emission Data", "encoded", "emissions", 1),
    ("archivedemissiondata", "Irregular Emission Data", "encoded", "emissions", 2),
    ("emissiondata", "Unexpected Emission Data", "encoded", "emissions", 3),
    ("decodedemissiondata", "Decoded Emission Data", "encoded", "emissions", 4),
    ("compactemissionsdata", "Abnormal Compact Emissions Data", "encoded", "emissions", 5),
    ("shieldcyclerecordings", "Distorted Shield Cycle Recordings", "encoded", "shield data", 1),
    ("shieldsoakanalysis", "Inconsistent Shield Soak Analysis", "encoded", "shield data", 2),
    ("shielddensityreports", "Untypical Shield Scans", "encoded", "shield data", 3),
    ("shieldpatternanalysis", "Aberrant Shield Pattern Analysis", "encoded", "shield data", 4),
    ("shieldfrequencydata", "Peculiar Shield Frequency Data", "encoded", "shield data", 5),
]

# Non-trader materials still need their correct category and grade in inventory.
_MATERIAL_ROWS += [
    ("unknownenergysource", "Sensor Fragment", "manufactured", "special", 5),
    ("guardian_powercell", "Guardian Power Cell", "manufactured", "guardian", 1),
    ("guardian_powerconduit", "Guardian Power Conduit", "manufactured", "guardian", 2),
    ("guardian_techcomponent", "Guardian Technology Component", "manufactured", "guardian", 3),
    ("guardian_sentinel_weaponparts", "Guardian Sentinel Weapon Parts", "manufactured", "guardian", 3),
    ("guardian_sentinel_wreckagecomponents", "Guardian Sentinel Wreckage Components", "manufactured", "guardian", 1),
    ("unknowncarapace", "Thargoid Carapace", "manufactured", "thargoid", 2),
    ("unknownenergycell", "Thargoid Energy Cell", "manufactured", "thargoid", 3),
    ("unknownorganiccircuitry", "Thargoid Organic Circuitry", "manufactured", "thargoid", 5),
    ("unknowntechnologycomponents", "Thargoid Technological Components", "manufactured", "thargoid", 4),
    ("tg_biomechanicalconduits", "Bio-Mechanical Conduits", "manufactured", "thargoid", 3),
    ("tg_propulsionelement", "Propulsion Elements", "manufactured", "thargoid", 5),
    ("tg_weaponparts", "Weapon Parts", "manufactured", "thargoid", 4),
    ("tg_wreckagecomponents", "Wreckage Components", "manufactured", "thargoid", 3),
    ("unknownshipsignature", "Thargoid Ship Signature", "encoded", "special", 3),
    ("unknownwakedata", "Thargoid Wake Data", "encoded", "special", 4),
    ("ancientlanguagedata", "Pattern Delta Obelisk Data", "encoded", "guardian", 4),
    ("ancientbiologicaldata", "Pattern Alpha Obelisk Data", "encoded", "guardian", 4),
    ("ancientculturaldata", "Pattern Beta Obelisk Data", "encoded", "guardian", 4),
    ("ancienthistoricaldata", "Pattern Gamma Obelisk Data", "encoded", "guardian", 4),
    ("ancienttechnologicaldata", "Pattern Epsilon Obelisk Data", "encoded", "guardian", 4),
    ("guardian_weaponblueprint", "Guardian Weapon Blueprint Segment", "encoded", "guardian", 4),
    ("guardian_moduleblueprint", "Guardian Module Blueprint Segment", "encoded", "guardian", 4),
    ("guardian_vesselblueprint", "Guardian Vessel Blueprint Segment", "encoded", "guardian", 5),
    ("tg_compositiondata", "Thargoid Material Composition Data", "encoded", "thargoid", 3),
    ("tg_residuedata", "Thargoid Residue Data", "encoded", "thargoid", 4),
    ("tg_structuraldata", "Thargoid Structural Data", "encoded", "thargoid", 2),
    ("tg_shipflightdata", "Ship Flight Data", "encoded", "thargoid", 3),
    ("tg_shipsystemsdata", "Ship Systems Data", "encoded", "thargoid", 4),
]

MATERIALS = {
    symbol: {"symbol": symbol, "name": name, "category": category, "family": family, "grade": grade}
    for symbol, name, category, family, grade in _MATERIAL_ROWS
}


def material_info(symbol: str) -> dict:
    key = (symbol or "").lower()
    return MATERIALS.get(key, {"symbol": key, "name": key.replace("_", " ").title(),
                               "category": "manufactured", "family": "unknown", "grade": None})


BLUEPRINT_INFO = {
    "FSD Increased Range": {
        "what": "Raises jump range; the best first upgrade for most ships.",
        "engineer": "Felicity Farseer, Elvira Martuuk and others.",
    },
    "Thrusters Dirty Tuning": {
        "what": "Raises speed and agility at the cost of additional heat.",
        "engineer": "Professor Palin and other thruster engineers.",
    },
}

# Verified starter recipes: material display names are resolved to symbols below.
BLUEPRINTS = {
    "FSD Increased Range": {
        1: {"disruptedwakeechoes": 1},
        2: {"disruptedwakeechoes": 1, "chemicalprocessors": 1},
        3: {"phasealloys": 1, "chemicalprocessors": 1, "wakesolutions": 1},
        4: {"manganese": 1, "chemicaldistillery": 1, "hyperspacetrajectories": 1},
        5: {"arsenic": 1, "chemicalmanipulators": 1, "dataminedwake": 1},
    },
    "Thrusters Dirty Tuning": {
        1: {"legacyfirmware": 1},
        2: {"legacyfirmware": 1, "mechanicalequipment": 1},
        3: {"legacyfirmware": 1, "chromium": 1, "mechanicalcomponents": 1},
        4: {"consumerfirmware": 1, "selenium": 1, "mechanicalcomponents": 1},
        5: {"industrialfirmware": 1, "cadmium": 1, "pharmaceuticalisolators": 1},
    },
}


ENGINEERS = {
    "Felicity Farseer": ("Deciat", "FSD range, thrusters, sensors", False),
    "Elvira Martuuk": ("Khun", "FSD range, shields", False),
    "The Dweller": ("Wyrd", "power distributor, lasers", False),
    "Liz Ryder": ("Eurybia", "missiles, torpedoes", False),
    "Tod 'The Blaster' McQuinn": ("Wolf 397", "multi-cannons, fragment cannons", False),
    "Zacariah Nemo": ("Yoru", "fragment cannons, plasma", False),
    "Lei Cheung": ("Laksak", "shield generators, sensors", False),
    "Hera Tani": ("Kuwemaki", "power plant, surface scanner", False),
    "Juri Ishmaak": ("Giryak", "mines, sensors, scanners", False),
    "Selene Jean": ("Kuk", "hull reinforcement, armour", False),
    "Marco Qwent": ("Sirius", "power plant, distributor", False),
    "Ram Tah": ("Meene", "utilities, limpets", False),
    "Broo Tarquin": ("Muang", "pulse and burst lasers", False),
    "The Sarge": ("Beta-3 Tucani", "cannons, limpets", False),
    "Colonel Bris Dekker": ("Sol", "FSD interdictors", False),
    "Didi Vatermann": ("Leesti", "shield boosters", False),
    "Bill Turner": ("Alioth", "plasma accelerators, utilities", False),
    "Lori Jameson": ("Shinrarta Dezhra", "sensors, scanners, life support", False),
    "Professor Palin": ("Arque", "thrusters, FSD", False),
    "Tiana Fortune": ("Achenar", "interdictors, limpets, sensors", False),
    "Chloe Sedesi": ("Shenve", "thrusters, FSD", False),
    "Mel Brandon": ("Luchtaine", "lasers, shields, FSD, thrusters", False),
    "Petra Olmanova": ("Asura", "armour, countermeasures, explosives", False),
    "Marsha Hicks": ("Tir", "multi-cannons, fragments, limpets", False),
    "Etienne Dorn": ("Los", "rail guns, power, sensors", False),
    "Domino Green": ("Orishis", "suit and weapon mods", True),
    "Hero Ferrari": ("Siris", "suit and weapon mods", True),
    "Kit Fowler": ("Capoya", "suit and weapon mods", True),
    "Jude Navarro": ("Aurai", "suit and weapon mods", True),
    "Terra Velasquez": ("Shou Xing", "suit and weapon mods", True),
    "Oden Geiger": ("Candiaei", "suit and weapon mods", True),
    "Uma Laszlo": ("Xuane", "suit and weapon mods", True),
    "Wellington Beck": ("Jolapa", "suit and weapon mods", True),
    "Yarden Bond": ("Bayan", "suit and weapon mods", True),
    "Baltanos": ("Deriso", "suit and weapon mods", True),
    "Eleanor Bresa": ("Desy", "suit and weapon mods", True),
    "Rosa Dayette": ("Kojeara", "suit and weapon mods", True),
    "Yi Shen": ("Einheriar", "suit and weapon mods", True),
}


def inventory_counts(state: dict) -> dict[str, int]:
    out = {}
    for category in ("raw", "manufactured", "encoded"):
        for symbol, item in (state.get(category) or {}).items():
            out[symbol.lower()] = int(item.get("count", 0) if isinstance(item, dict) else item)
    return out


def requirements(blueprint: str, target_grade: int, rolls=None) -> dict[str, int]:
    recipe = BLUEPRINTS.get(blueprint)
    if not recipe:
        raise KeyError(blueprint)
    rolls = rolls or ROLLS_PER_GRADE
    need = {}
    for grade in range(1, min(5, max(1, int(target_grade))) + 1):
        for symbol, qty in recipe.get(grade, {}).items():
            need[symbol] = need.get(symbol, 0) + qty * rolls.get(grade, 3)
    return need


def convertible(surplus: int, from_grade: int, to_grade: int) -> int:
    if surplus <= 0:
        return 0
    if from_grade > to_grade:
        return surplus * (3 ** (from_grade - to_grade))
    if from_grade < to_grade:
        return surplus // (6 ** (to_grade - from_grade))
    return surplus


def _cost_for(wanted: int, from_grade: int, to_grade: int) -> int:
    if from_grade > to_grade:
        return math.ceil(wanted / (3 ** (from_grade - to_grade)))
    return wanted * (6 ** (to_grade - from_grade))


def _best_trade(target: dict, deficit: int, inventory: dict, reserved: dict):
    best = None
    if target["family"] in ("unknown", "special", "guardian", "thargoid"):
        return None
    for symbol, candidate in MATERIALS.items():
        if candidate["family"] != target["family"] or symbol == target["symbol"]:
            continue
        surplus = inventory.get(symbol, 0) - reserved.get(symbol, 0)
        gain = convertible(surplus, candidate["grade"], target["grade"])
        if gain <= 0:
            continue
        covered = min(gain, deficit)
        spend = _cost_for(covered, candidate["grade"], target["grade"])
        if best is None or covered > best["covers"]:
            best = {"from": candidate["name"], "spend": spend, "covers": covered}
    return best


def plan(blueprint: str, target_grade: int, inventory: dict) -> dict:
    need = requirements(blueprint, target_grade)
    reserved = dict(need)
    rows = []
    for symbol, qty in sorted(need.items(), key=lambda item: -material_info(item[0])["grade"]):
        info = material_info(symbol)
        have = int(inventory.get(symbol, 0))
        deficit = max(0, qty - have)
        row = {**info, "need": qty, "have": have, "deficit": deficit, "trade": None}
        if deficit:
            row["trade"] = _best_trade(info, deficit, inventory, reserved)
        rows.append(row)
    return {"blueprint": blueprint, "grade": int(target_grade), "materials": rows,
            "craftable": all(row["deficit"] == 0 for row in rows)}


def pinned_plans(state: dict) -> list[dict]:
    inventory = inventory_counts(state)
    plans = []
    for pin in state.get("pinned_blueprints") or []:
        try:
            plans.append(plan(pin["name"], pin.get("grade", 5), inventory))
        except (KeyError, TypeError, ValueError):
            continue
    return plans


def ready_blueprints(state: dict) -> set[str]:
    return {row["blueprint"] for row in pinned_plans(state) if row["craftable"]}
