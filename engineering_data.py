"""Canonical engineering reference data and blueprint planning helpers.

Material symbols are the internal names written by Elite Dangerous journals.
The catalogue covers standard ship-engineering materials plus Guardian and
Thargoid materials that can appear in the same Materials event.
"""

from __future__ import annotations

import math


GRADE_CAP = {1: 300, 2: 250, 3: 200, 4: 150, 5: 100}
# Frontier's deterministic post-rebalance maximum-access costs.  A plan from
# stock to G5 therefore budgets 1, 2, 3, 4 and 5 applications respectively.
ROLLS_PER_GRADE = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


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


# Module-slot categories used to group each engineer's offered blueprints in the
# ENGINEERS-tab cards. Order here is the display order.
SLOT_CATEGORIES = [
    "Hardpoint - Kinetic", "Hardpoint - Energy", "Hardpoint - Missiles & Mines",
    "Core Internal - Power Plant", "Core Internal - Thrusters", "Core Internal - FSD",
    "Core Internal - Power Distributor", "Core Internal - Life Support",
    "Core Internal - Sensors", "Core Internal - Armour",
    "Optional Internal - Shield Generator", "Optional Internal - Shield Booster",
    "Optional Internal - Hull / Module Reinforcement",
    "Optional Internal - Fuel Scoop",
    "Optional Internal - Detailed Surface Scanner",
    "Utility Mount - Shield Booster", "Utility Mount",
]

BLUEPRINT_INFO = {
    "FSD Increased Range": {
        "what": "Raises jump range; the best first upgrade for most ships.",
        "slot": "Core Internal - FSD",
        "engineers": ["Felicity Farseer", "Elvira Martuuk", "Etienne Dorn", "Colonel Bris Dekker"],
    },
    "Thrusters Dirty Tuning": {
        "what": "Raises speed and agility at the cost of additional heat.",
        "slot": "Core Internal - Thrusters",
        "engineers": ["Professor Palin", "Chloe Sedesi", "Zacariah Nemo"],
    },
    "Power Plant Armoured": {
        "what": "Improves plant integrity and heat efficiency.",
        "slot": "Core Internal - Power Plant",
        "engineers": ["Hera Tani", "Marco Qwent"],
    },
    "Power Plant Overcharged": {
        "what": "Raises power output at the cost of heat and integrity.",
        "slot": "Core Internal - Power Plant",
        "engineers": ["Hera Tani", "Marco Qwent"],
    },
    "Power Plant Low Emissions": {
        "what": "Reduces heat generation at the cost of mass and output.",
        "slot": "Core Internal - Power Plant",
        "engineers": ["Hera Tani", "Marco Qwent"],
    },
    "Power Distributor Charge Enhanced": {
        "what": "Raises recharge rates across all three capacitors.",
        "slot": "Core Internal - Power Distributor",
        "engineers": ["The Dweller", "Marco Qwent"],
    },
    "Power Distributor Engine Focused": {
        "what": "Prioritises the engine capacitor and its recharge rate.",
        "slot": "Core Internal - Power Distributor",
        "engineers": ["The Dweller", "Marco Qwent"],
    },
    "Power Distributor High Capacity": {
        "what": "Raises capacitor capacity at the cost of recharge rate.",
        "slot": "Core Internal - Power Distributor",
        "engineers": ["The Dweller", "Marco Qwent"],
    },
    "Shield Generator Enhanced Low Power": {
        "what": "Reduces shield mass and power draw.",
        "slot": "Optional Internal - Shield Generator",
        "engineers": ["Elvira Martuuk", "Lei Cheung"],
    },
    "Shield Generator Reinforced": {
        "what": "Raises absolute shield strength.",
        "slot": "Optional Internal - Shield Generator",
        "engineers": ["Elvira Martuuk", "Lei Cheung"],
    },
    "Shield Generator Thermal Resistant": {
        "what": "Improves thermal resistance while balancing defences.",
        "slot": "Optional Internal - Shield Generator",
        "engineers": ["Elvira Martuuk", "Lei Cheung"],
    },
    "Shield Booster Heavy Duty": {
        "what": "Raises total shield boost at the cost of mass and power.",
        "slot": "Utility Mount - Shield Booster",
        "engineers": ["Didi Vatermann"],
    },
    "Shield Booster Resistance Augmented": {
        "what": "Improves all shield resistances.",
        "slot": "Utility Mount - Shield Booster",
        "engineers": ["Didi Vatermann"],
    },
    "Armour Heavy Duty": {
        "what": "Raises hull integrity and resistance.",
        "slot": "Core Internal - Armour",
        "engineers": ["Selene Jean", "Petra Olmanova"],
    },
    "Life Support Lightweight": {
        "what": "Reduces life-support mass.",
        "slot": "Core Internal - Life Support",
        "engineers": ["Lori Jameson"],
    },
    "Surface Scanner Expanded Probe Radius": {
        "what": "Makes efficient surface mapping easier.",
        "slot": "Optional Internal - Detailed Surface Scanner",
        "engineers": ["Hera Tani", "Juri Ishmaak"],
    },

    # ---- Weapon hardpoint mods, one row per (category, effect) rather than per
    # weapon model — every model offering a given effect shares an identical
    # per-grade recipe. "what" text lists exactly which models it applies to. ----
    "Kinetic Weapon Overcharged": {
        "what": "Raises damage output at the cost of higher thermal load and distributor draw. Applies to Multi-cannons, Cannons and Fragment Cannons (not Rail Guns).",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Kinetic Weapon Efficient": {
        "what": "Cuts thermal load, power and distributor draw for sustained fire, with a smaller damage bonus. Applies to Multi-cannons, Cannons and Fragment Cannons (not Rail Guns).",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Kinetic Weapon Long Range": {
        "what": "Extends maximum range and removes damage falloff at the cost of mass and power draw. Applies to Multi-cannons, Cannons and Rail Guns (not Fragment Cannons).",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Etienne Dorn", "Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Kinetic Weapon Rapid Fire": {
        "what": "Raises rate of fire and cuts reload time at the cost of accuracy jitter and a small damage penalty. Applies to Multi-cannons, Cannons and Fragment Cannons (not Rail Guns).",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Kinetic Weapon Lightweight": {
        "what": "Sharply reduces mass and power/distributor draw at the cost of weapon integrity. Applies to Multi-cannons, Cannons, Fragment Cannons and Rail Guns.",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Etienne Dorn", "Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Kinetic Weapon Sturdy": {
        "what": "Raises weapon integrity and armour piercing at the cost of mass. Applies to Multi-cannons, Cannons, Fragment Cannons and Rail Guns.",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Etienne Dorn", "Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Kinetic Weapon Short Range Blaster": {
        "what": "Raises damage sharply at the cost of range and higher thermal load. Applies to Multi-cannons, Cannons and Rail Guns (not Fragment Cannons).",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Etienne Dorn", "Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Kinetic Weapon High Capacity Magazine": {
        "what": "Raises clip and ammo capacity at the cost of mass and power draw. Applies to Multi-cannons, Cannons, Fragment Cannons and Rail Guns.",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Etienne Dorn", "Marsha Hicks", "The Sarge", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Fragment Cannon Double Shot": {
        "what": "Fires two shots per trigger pull for more burst damage. Fragment Cannon only.",
        "slot": "Hardpoint - Kinetic",
        "engineers": ["Marsha Hicks", "Tod 'The Blaster' McQuinn", "Zacariah Nemo"],
    },
    "Energy Weapon Overcharged": {
        "what": "Raises damage output at the cost of higher thermal load and distributor draw. Applies to Beam, Burst and Pulse Lasers and Plasma Accelerators.",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Energy Weapon Efficient": {
        "what": "Cuts thermal load, power and distributor draw for sustained fire, with a smaller damage bonus. Applies to Beam, Burst and Pulse Lasers and Plasma Accelerators.",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Energy Weapon Long Range": {
        "what": "Extends maximum range, removes damage falloff and raises shot speed at the cost of mass and power draw. Applies to Beam, Burst and Pulse Lasers and Plasma Accelerators.",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Energy Weapon Focused": {
        "what": "Extends range and raises armour piercing at the cost of rate of fire and thermal load. Applies to Burst and Pulse Lasers and Plasma Accelerators (not Beam Lasers).",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Energy Weapon Rapid Fire": {
        "what": "Raises rate of fire and cuts reload time at the cost of accuracy jitter and a small damage penalty. Applies to Burst and Pulse Lasers and Plasma Accelerators (not Beam Lasers).",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Energy Weapon Lightweight": {
        "what": "Sharply reduces mass and power/distributor draw at the cost of weapon integrity. Applies to Beam, Burst and Pulse Lasers and Plasma Accelerators.",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Energy Weapon Sturdy": {
        "what": "Raises weapon integrity and armour piercing at the cost of mass. Applies to Beam, Burst and Pulse Lasers and Plasma Accelerators.",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Energy Weapon Short Range Blaster": {
        "what": "Raises damage sharply at the cost of range and higher thermal load. Applies to Beam, Burst and Pulse Lasers and Plasma Accelerators.",
        "slot": "Hardpoint - Energy",
        "engineers": ["Bill Turner", "Broo Tarquin", "Etienne Dorn", "Mel Brandon", "The Dweller", "Zacariah Nemo"],
    },
    "Missile & Mine Lightweight": {
        "what": "Sharply reduces mass and power/distributor draw at the cost of weapon integrity. Applies to Missile Racks, Mine Launchers and Torpedo Pylons.",
        "slot": "Hardpoint - Missiles & Mines",
        "engineers": ["Juri Ishmaak", "Liz Ryder", "Petra Olmanova"],
    },
    "Missile & Mine Sturdy": {
        "what": "Raises weapon integrity and armour piercing at the cost of mass. Applies to Missile Racks, Mine Launchers and Torpedo Pylons.",
        "slot": "Hardpoint - Missiles & Mines",
        "engineers": ["Juri Ishmaak", "Liz Ryder", "Petra Olmanova"],
    },
    "Missile & Mine Rapid Fire": {
        "what": "Raises rate of fire and cuts reload time at the cost of accuracy jitter and a small damage penalty. Applies to Missile Racks and Mine Launchers (not Torpedo Pylons).",
        "slot": "Hardpoint - Missiles & Mines",
        "engineers": ["Juri Ishmaak", "Liz Ryder", "Petra Olmanova"],
    },
    "Missile & Mine High Capacity Magazine": {
        "what": "Raises clip and ammo capacity at the cost of mass and power draw. Applies to Missile Racks and Mine Launchers (not Torpedo Pylons, which have no magazine).",
        "slot": "Hardpoint - Missiles & Mines",
        "engineers": ["Juri Ishmaak", "Liz Ryder", "Petra Olmanova"],
    },
    "Sensors Lightweight": {
        "what": "Reduces sensor mass and narrows scan angle at the cost of module integrity.",
        "slot": "Core Internal - Sensors",
        "engineers": ["Bill Turner", "Etienne Dorn", "Felicity Farseer", "Hera Tani", "Juri Ishmaak", "Lei Cheung", "Lori Jameson", "Tiana Fortune"],
    },
    "Sensors Long Range": {
        "what": "Extends detection range at the cost of a narrower scan angle and more mass.",
        "slot": "Core Internal - Sensors",
        "engineers": ["Bill Turner", "Etienne Dorn", "Felicity Farseer", "Hera Tani", "Juri Ishmaak", "Lei Cheung", "Lori Jameson", "Tiana Fortune"],
    },
    "Sensors Wide Angle": {
        "what": "Widens the scan angle at the cost of detection range and power draw.",
        "slot": "Core Internal - Sensors",
        "engineers": ["Bill Turner", "Etienne Dorn", "Felicity Farseer", "Hera Tani", "Juri Ishmaak", "Lei Cheung", "Lori Jameson", "Tiana Fortune"],
    },
    "Armour Lightweight": {
        "what": "Cuts hull mass sharply and raises overall resistances slightly, at the cost of some hull boost.",
        "slot": "Core Internal - Armour",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Armour Blast Resistant": {
        "what": "Raises explosive resistance at the cost of thermal and kinetic resistance.",
        "slot": "Core Internal - Armour",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Armour Kinetic Resistant": {
        "what": "Raises kinetic resistance at the cost of thermal and explosive resistance.",
        "slot": "Core Internal - Armour",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Armour Thermal Resistant": {
        "what": "Raises thermal resistance at the cost of kinetic and explosive resistance.",
        "slot": "Core Internal - Armour",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Hull Reinforcement Heavy Duty": {
        "what": "Raises hull reinforcement and all resistances at the cost of mass.",
        "slot": "Optional Internal - Hull / Module Reinforcement",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Hull Reinforcement Lightweight": {
        "what": "Cuts mass and raises hull boost at the cost of hull reinforcement.",
        "slot": "Optional Internal - Hull / Module Reinforcement",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Hull Reinforcement Blast Resistant": {
        "what": "Raises explosive resistance and hull reinforcement at the cost of thermal and kinetic resistance.",
        "slot": "Optional Internal - Hull / Module Reinforcement",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Hull Reinforcement Kinetic Resistant": {
        "what": "Raises kinetic resistance and hull reinforcement at the cost of thermal and explosive resistance.",
        "slot": "Optional Internal - Hull / Module Reinforcement",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Hull Reinforcement Thermal Resistant": {
        "what": "Raises thermal resistance and hull reinforcement at the cost of kinetic and explosive resistance.",
        "slot": "Optional Internal - Hull / Module Reinforcement",
        "engineers": ["Liz Ryder", "Petra Olmanova", "Selene Jean"],
    },
    "Fuel Scoop Shielded": {
        "what": "Raises module integrity so the scoop better survives sustained close-star scooping, at the cost of power draw.",
        "slot": "Optional Internal - Fuel Scoop",
        "engineers": ["Bill Turner", "Lori Jameson", "Marsha Hicks"],
    },
}

# Highest grade each engineer can apply for the compact blueprint families
# above.  This is a static, runtime-independent snapshot of the per-grade
# engineer lists in ed-odyssey-materials-helper.  A flat list is not enough:
# many engineers offer a blueprint only through G1-G4 while another reaches
# G5.  Keeping the cap lets the UI answer the useful question: "who can finish
# this upgrade?"
BLUEPRINT_ENGINEER_GRADES = {
    'FSD Increased Range': {'Chloe Sedesi': 3, 'Colonel Bris Dekker': 3, 'Elvira Martuuk': 5, 'Felicity Farseer': 5, 'Mel Brandon': 5, 'Professor Palin': 3},
    'Thrusters Dirty Tuning': {'Chloe Sedesi': 5, 'Elvira Martuuk': 2, 'Felicity Farseer': 3, 'Mel Brandon': 5, 'Professor Palin': 5},
    'Power Plant Armoured': {'Etienne Dorn': 5, 'Felicity Farseer': 1, 'Hera Tani': 5, 'Marco Qwent': 4},
    'Power Plant Overcharged': {'Etienne Dorn': 5, 'Felicity Farseer': 1, 'Hera Tani': 5, 'Marco Qwent': 4},
    'Power Plant Low Emissions': {'Etienne Dorn': 5, 'Felicity Farseer': 1, 'Hera Tani': 5, 'Marco Qwent': 4},
    'Power Distributor Charge Enhanced': {'Etienne Dorn': 5, 'Hera Tani': 3, 'Marco Qwent': 3, 'The Dweller': 5},
    'Power Distributor Engine Focused': {'Etienne Dorn': 5, 'Hera Tani': 3, 'Marco Qwent': 3, 'The Dweller': 5},
    'Power Distributor High Capacity': {'Etienne Dorn': 5, 'Hera Tani': 3, 'Marco Qwent': 3, 'The Dweller': 5},
    'Shield Generator Enhanced Low Power': {'Didi Vatermann': 3, 'Elvira Martuuk': 3, 'Lei Cheung': 5, 'Mel Brandon': 5},
    'Shield Generator Reinforced': {'Didi Vatermann': 3, 'Elvira Martuuk': 3, 'Lei Cheung': 5, 'Mel Brandon': 5},
    'Shield Generator Thermal Resistant': {'Didi Vatermann': 3, 'Elvira Martuuk': 3, 'Lei Cheung': 5, 'Mel Brandon': 5},
    'Shield Booster Heavy Duty': {'Didi Vatermann': 5, 'Felicity Farseer': 1, 'Lei Cheung': 3, 'Mel Brandon': 5},
    'Shield Booster Resistance Augmented': {'Didi Vatermann': 5, 'Felicity Farseer': 1, 'Lei Cheung': 3, 'Mel Brandon': 5},
    'Armour Heavy Duty': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Life Support Lightweight': {'Bill Turner': 3, 'Etienne Dorn': 5, 'Lori Jameson': 4},
    'Surface Scanner Expanded Probe Radius': {'Bill Turner': 5, 'Etienne Dorn': 5, 'Felicity Farseer': 3, 'Hera Tani': 5, 'Juri Ishmaak': 5, 'Lei Cheung': 5, 'Lori Jameson': 5, 'Tiana Fortune': 3},
    'Kinetic Weapon Overcharged': {'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 5},
    'Kinetic Weapon Efficient': {'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 5},
    'Kinetic Weapon Long Range': {'Etienne Dorn': 5, 'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 3},
    'Kinetic Weapon Rapid Fire': {'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 5},
    'Kinetic Weapon Lightweight': {'Etienne Dorn': 5, 'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 5},
    'Kinetic Weapon Sturdy': {'Etienne Dorn': 5, 'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 5},
    'Kinetic Weapon Short Range Blaster': {'Etienne Dorn': 5, 'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 3},
    'Kinetic Weapon High Capacity Magazine': {'Etienne Dorn': 5, 'Marsha Hicks': 5, 'The Sarge': 5, "Tod 'The Blaster' McQuinn": 5, 'Zacariah Nemo': 5},
    'Fragment Cannon Double Shot': {'Marsha Hicks': 5, "Tod 'The Blaster' McQuinn": 3, 'Zacariah Nemo': 5},
    'Energy Weapon Overcharged': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 4, 'Zacariah Nemo': 2},
    'Energy Weapon Efficient': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 4, 'Zacariah Nemo': 2},
    'Energy Weapon Long Range': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 4, 'Zacariah Nemo': 2},
    'Energy Weapon Focused': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 4, 'Zacariah Nemo': 2},
    'Energy Weapon Rapid Fire': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 4, 'Zacariah Nemo': 2},
    'Energy Weapon Lightweight': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 4, 'Zacariah Nemo': 2},
    'Energy Weapon Sturdy': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 4, 'Zacariah Nemo': 2},
    'Energy Weapon Short Range Blaster': {'Bill Turner': 5, 'Broo Tarquin': 5, 'Etienne Dorn': 5, 'Mel Brandon': 5, 'The Dweller': 3, 'Zacariah Nemo': 2},
    'Missile & Mine Lightweight': {'Juri Ishmaak': 5, 'Liz Ryder': 5, 'Petra Olmanova': 5},
    'Missile & Mine Sturdy': {'Juri Ishmaak': 5, 'Liz Ryder': 5, 'Petra Olmanova': 5},
    'Missile & Mine Rapid Fire': {'Juri Ishmaak': 5, 'Liz Ryder': 5, 'Petra Olmanova': 5},
    'Missile & Mine High Capacity Magazine': {'Juri Ishmaak': 5, 'Liz Ryder': 5, 'Petra Olmanova': 5},
    'Sensors Lightweight': {'Bill Turner': 5, 'Etienne Dorn': 5, 'Felicity Farseer': 3, 'Hera Tani': 3, 'Juri Ishmaak': 5, 'Lei Cheung': 5, 'Lori Jameson': 5, 'Tiana Fortune': 5},
    'Sensors Long Range': {'Bill Turner': 5, 'Etienne Dorn': 5, 'Felicity Farseer': 3, 'Hera Tani': 3, 'Juri Ishmaak': 5, 'Lei Cheung': 5, 'Lori Jameson': 5, 'Tiana Fortune': 5},
    'Sensors Wide Angle': {'Bill Turner': 5, 'Etienne Dorn': 5, 'Felicity Farseer': 3, 'Hera Tani': 3, 'Juri Ishmaak': 5, 'Lei Cheung': 5, 'Lori Jameson': 5, 'Tiana Fortune': 5},
    'Armour Lightweight': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Armour Blast Resistant': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Armour Kinetic Resistant': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Armour Thermal Resistant': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Hull Reinforcement Heavy Duty': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Hull Reinforcement Lightweight': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Hull Reinforcement Blast Resistant': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Hull Reinforcement Kinetic Resistant': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Hull Reinforcement Thermal Resistant': {'Liz Ryder': 1, 'Petra Olmanova': 5, 'Selene Jean': 5},
    'Fuel Scoop Shielded': {'Bill Turner': 3, 'Lori Jameson': 4, 'Marsha Hicks': 5},
}

# Keep the original public metadata shape compatible while replacing the old
# hand-written, non-grade-aware engineer lists with the verified snapshot.
for _blueprint_name, _engineer_grades in BLUEPRINT_ENGINEER_GRADES.items():
    BLUEPRINT_INFO[_blueprint_name]["engineers"] = list(_engineer_grades)


def blueprint_info(name: str) -> dict:
    return BLUEPRINT_INFO.get(name, {"what": "", "slot": "Unclassified", "engineers": []})


def engineer_blueprints(name: str) -> dict[str, list[str]]:
    """Blueprint names offered by an engineer, grouped by slot (SLOT_CATEGORIES order)."""
    groups: dict[str, list[str]] = {}
    for bp_name, info in BLUEPRINT_INFO.items():
        if name in info.get("engineers", ()):
            groups.setdefault(info.get("slot", "Unclassified"), []).append(bp_name)
    for names in groups.values():
        names.sort()
    ordered = {slot: groups[slot] for slot in SLOT_CATEGORIES if slot in groups}
    ordered.update({slot: names for slot, names in groups.items() if slot not in ordered})
    return ordered


def engineer_blueprint_grade(engineer: str, blueprint: str) -> int:
    """Highest grade *engineer* can apply for *blueprint*, or zero."""
    return int((BLUEPRINT_ENGINEER_GRADES.get(blueprint) or {}).get(engineer) or 0)

# Verified high-use ship recipes.  Costs are expressed per application; the
# planner applies ROLLS_PER_GRADE and can start from an existing grade.
BLUEPRINTS = {
    "FSD Increased Range": {
        1: {"disruptedwakeechoes": 1},
        2: {"disruptedwakeechoes": 1, "chemicalprocessors": 1},
        3: {"phosphorus": 1, "chemicalprocessors": 1, "wakesolutions": 1},
        4: {"manganese": 1, "chemicaldistillery": 1, "hyperspacetrajectories": 1},
        5: {"arsenic": 1, "chemicalmanipulators": 1, "dataminedwake": 1},
    },
    "Thrusters Dirty Tuning": {
        1: {"legacyfirmware": 1},
        2: {"legacyfirmware": 1, "mechanicalequipment": 1},
        3: {"legacyfirmware": 1, "chromium": 1, "mechanicalcomponents": 1},
        4: {"consumerfirmware": 1, "selenium": 1, "configurablecomponents": 1},
        5: {"industrialfirmware": 1, "cadmium": 1, "pharmaceuticalisolators": 1},
    },
    "Power Plant Armoured": {
        1: {"wornshieldemitters": 1}, 2: {"carbon": 1, "shieldemitters": 1},
        3: {"carbon": 1, "highdensitycomposites": 1, "shieldemitters": 1},
        4: {"fedproprietarycomposites": 1, "shieldingsensors": 1, "vanadium": 1},
        5: {"compoundshielding": 1, "fedcorecomposites": 1, "tungsten": 1},
    },
    "Power Plant Overcharged": {
        1: {"sulphur": 1}, 2: {"conductivecomponents": 1, "heatconductionwiring": 1},
        3: {"conductivecomponents": 1, "heatconductionwiring": 1, "selenium": 1},
        4: {"cadmium": 1, "conductiveceramics": 1, "heatdispersionplate": 1},
        5: {"chemicalmanipulators": 1, "conductiveceramics": 1, "tellurium": 1},
    },
    "Power Plant Low Emissions": {
        1: {"iron": 1}, 2: {"iron": 1, "archivedemissiondata": 1},
        3: {"heatexchangers": 1, "iron": 1, "archivedemissiondata": 1},
        4: {"germanium": 1, "emissiondata": 1, "heatvanes": 1},
        5: {"niobium": 1, "decodedemissiondata": 1, "protoheatradiators": 1},
    },
    "Power Distributor Charge Enhanced": {
        1: {"legacyfirmware": 1}, 2: {"chemicalprocessors": 1, "legacyfirmware": 1},
        3: {"chemicaldistillery": 1, "gridresistors": 1, "consumerfirmware": 1},
        4: {"chemicalmanipulators": 1, "industrialfirmware": 1, "hybridcapacitors": 1},
        5: {"chemicalmanipulators": 1, "industrialfirmware": 1, "exquisitefocuscrystals": 1},
    },
    "Power Distributor Engine Focused": {
        1: {"sulphur": 1}, 2: {"conductivecomponents": 1, "sulphur": 1},
        3: {"bulkscandata": 1, "chromium": 1, "electrochemicalarrays": 1},
        4: {"scanarchives": 1, "selenium": 1, "polymercapacitors": 1},
        5: {"scandatabanks": 1, "cadmium": 1, "militarysupercapacitors": 1},
    },
    "Power Distributor High Capacity": {
        1: {"sulphur": 1}, 2: {"chromium": 1, "legacyfirmware": 1},
        3: {"chromium": 1, "highdensitycomposites": 1, "legacyfirmware": 1},
        4: {"consumerfirmware": 1, "fedproprietarycomposites": 1, "selenium": 1},
        5: {"industrialfirmware": 1, "militarysupercapacitors": 1, "fedproprietarycomposites": 1},
    },
    "Shield Generator Enhanced Low Power": {
        1: {"shieldcyclerecordings": 1}, 2: {"shieldcyclerecordings": 1, "germanium": 1},
        3: {"shieldcyclerecordings": 1, "germanium": 1, "precipitatedalloys": 1},
        4: {"shieldsoakanalysis": 1, "niobium": 1, "thermicalloys": 1},
        5: {"militarygradealloys": 1, "tin": 1, "shielddensityreports": 1},
    },
    "Shield Generator Reinforced": {
        1: {"phosphorus": 1}, 2: {"conductivecomponents": 1, "phosphorus": 1},
        3: {"conductivecomponents": 1, "mechanicalcomponents": 1, "phosphorus": 1},
        4: {"conductiveceramics": 1, "configurablecomponents": 1, "manganese": 1},
        5: {"arsenic": 1, "conductivepolymers": 1, "improvisedcomponents": 1},
    },
    "Shield Generator Thermal Resistant": {
        1: {"shieldcyclerecordings": 1}, 2: {"shieldcyclerecordings": 1, "germanium": 1},
        3: {"shieldcyclerecordings": 1, "germanium": 1, "selenium": 1},
        4: {"focuscrystals": 1, "shieldsoakanalysis": 1, "mercury": 1},
        5: {"refinedfocuscrystals": 1, "ruthenium": 1, "shielddensityreports": 1},
    },
    "Shield Booster Heavy Duty": {
        1: {"gridresistors": 1}, 2: {"shieldcyclerecordings": 1, "hybridcapacitors": 1},
        3: {"shieldcyclerecordings": 1, "hybridcapacitors": 1, "niobium": 1},
        4: {"electrochemicalarrays": 1, "shieldsoakanalysis": 1, "tin": 1},
        5: {"antimony": 1, "polymercapacitors": 1, "shielddensityreports": 1},
    },
    "Shield Booster Resistance Augmented": {
        1: {"phosphorus": 1}, 2: {"conductivecomponents": 1, "phosphorus": 1},
        3: {"conductivecomponents": 1, "focuscrystals": 1, "phosphorus": 1},
        4: {"conductiveceramics": 1, "manganese": 1, "refinedfocuscrystals": 1},
        5: {"conductiveceramics": 1, "imperialshielding": 1, "refinedfocuscrystals": 1},
    },
    "Armour Heavy Duty": {
        1: {"carbon": 1}, 2: {"carbon": 1, "shieldemitters": 1},
        3: {"carbon": 1, "highdensitycomposites": 1, "shieldemitters": 1},
        4: {"fedproprietarycomposites": 1, "shieldingsensors": 1, "vanadium": 1},
        5: {"compoundshielding": 1, "fedcorecomposites": 1, "tungsten": 1},
    },
    "Life Support Lightweight": {
        1: {"phosphorus": 1}, 2: {"manganese": 1, "salvagedalloys": 1},
        3: {"conductiveceramics": 1, "manganese": 1, "salvagedalloys": 1},
        4: {"conductivecomponents": 1, "phasealloys": 1, "protolightalloys": 1},
        5: {"conductiveceramics": 1, "protoradiolicalloys": 1, "protolightalloys": 1},
    },
    "Surface Scanner Expanded Probe Radius": {
        1: {"mechanicalscrap": 1}, 2: {"mechanicalscrap": 1, "germanium": 1},
        3: {"mechanicalscrap": 1, "germanium": 1, "phasealloys": 1},
        4: {"mechanicalequipment": 1, "niobium": 1, "protolightalloys": 1},
        5: {"mechanicalcomponents": 1, "tin": 1, "protoradiolicalloys": 1},
    },

    # ---- Kinetic weapon hardpoints (Multi-cannon, Cannon, Fragment Cannon, Rail Gun) ----
    "Kinetic Weapon Overcharged": {
        1: {"nickel": 1},
        2: {"nickel": 1, "conductivecomponents": 1},
        3: {"nickel": 1, "conductivecomponents": 1, "electrochemicalarrays": 1},
        4: {"zinc": 1, "conductiveceramics": 1, "polymercapacitors": 1},
        5: {"zirconium": 1, "conductivepolymers": 1, "embeddedfirmware": 1},
    },
    "Kinetic Weapon Efficient": {
        1: {"sulphur": 1},
        2: {"sulphur": 1, "heatdispersionplate": 1},
        3: {"chromium": 1, "heatexchangers": 1, "scrambledemissiondata": 1},
        4: {"selenium": 1, "heatvanes": 1, "archivedemissiondata": 1},
        5: {"cadmium": 1, "protoheatradiators": 1, "emissiondata": 1},
    },
    "Kinetic Weapon Long Range": {
        1: {"sulphur": 1},
        2: {"sulphur": 1, "consumerfirmware": 1},
        3: {"sulphur": 1, "consumerfirmware": 1, "focuscrystals": 1},
        4: {"consumerfirmware": 1, "focuscrystals": 1, "conductivepolymers": 1},
        5: {"industrialfirmware": 1, "thermicalloys": 1, "biotechconductors": 1},
    },
    "Kinetic Weapon Rapid Fire": {
        1: {"mechanicalscrap": 1},
        2: {"mechanicalscrap": 1, "heatdispersionplate": 1},
        3: {"legacyfirmware": 1, "mechanicalequipment": 1, "precipitatedalloys": 1},
        4: {"consumerfirmware": 1, "mechanicalcomponents": 1, "thermicalloys": 1},
        5: {"configurablecomponents": 1, "precipitatedalloys": 1, "technetium": 1},
    },
    "Kinetic Weapon Lightweight": {
        1: {"phosphorus": 1},
        2: {"manganese": 1, "salvagedalloys": 1},
        3: {"manganese": 1, "salvagedalloys": 1, "conductiveceramics": 1},
        4: {"conductivecomponents": 1, "phasealloys": 1, "protolightalloys": 1},
        5: {"conductiveceramics": 1, "protolightalloys": 1, "protoradiolicalloys": 1},
    },
    "Kinetic Weapon Sturdy": {
        1: {"nickel": 1},
        2: {"nickel": 1, "shieldemitters": 1},
        3: {"nickel": 1, "shieldemitters": 1, "tungsten": 1},
        4: {"molybdenum": 1, "tungsten": 1, "zinc": 1},
        5: {"highdensitycomposites": 1, "molybdenum": 1, "technetium": 1},
    },
    "Kinetic Weapon Short Range Blaster": {
        1: {"nickel": 1},
        2: {"nickel": 1, "consumerfirmware": 1},
        3: {"nickel": 1, "consumerfirmware": 1, "electrochemicalarrays": 1},
        4: {"consumerfirmware": 1, "electrochemicalarrays": 1, "conductivepolymers": 1},
        5: {"industrialfirmware": 1, "biotechconductors": 1, "configurablecomponents": 1},
    },
    "Kinetic Weapon High Capacity Magazine": {
        1: {"mechanicalscrap": 1},
        2: {"mechanicalscrap": 1, "vanadium": 1},
        3: {"mechanicalscrap": 1, "vanadium": 1, "niobium": 1},
        4: {"tin": 1, "mechanicalequipment": 1, "highdensitycomposites": 1},
        5: {"mechanicalcomponents": 1, "militarysupercapacitors": 1, "fedproprietarycomposites": 1},
    },
    "Fragment Cannon Double Shot": {
        1: {"carbon": 1},
        2: {"carbon": 1, "mechanicalequipment": 1},
        3: {"carbon": 1, "mechanicalequipment": 1, "industrialfirmware": 1},
        4: {"vanadium": 1, "mechanicalcomponents": 1, "securityfirmware": 1},
        5: {"highdensitycomposites": 1, "configurablecomponents": 1, "embeddedfirmware": 1},
    },

    # ---- Energy weapon hardpoints (Beam/Burst/Pulse Laser, Plasma Accelerator) ----
    "Energy Weapon Overcharged": {
        1: {"nickel": 1},
        2: {"nickel": 1, "conductivecomponents": 1},
        3: {"nickel": 1, "conductivecomponents": 1, "electrochemicalarrays": 1},
        4: {"zinc": 1, "conductiveceramics": 1, "polymercapacitors": 1},
        5: {"zirconium": 1, "conductivepolymers": 1, "embeddedfirmware": 1},
    },
    "Energy Weapon Efficient": {
        1: {"sulphur": 1},
        2: {"sulphur": 1, "heatdispersionplate": 1},
        3: {"chromium": 1, "heatexchangers": 1, "scrambledemissiondata": 1},
        4: {"selenium": 1, "heatvanes": 1, "archivedemissiondata": 1},
        5: {"cadmium": 1, "protoheatradiators": 1, "emissiondata": 1},
    },
    "Energy Weapon Long Range": {
        1: {"sulphur": 1},
        2: {"sulphur": 1, "consumerfirmware": 1},
        3: {"sulphur": 1, "consumerfirmware": 1, "focuscrystals": 1},
        4: {"consumerfirmware": 1, "focuscrystals": 1, "conductivepolymers": 1},
        5: {"industrialfirmware": 1, "thermicalloys": 1, "biotechconductors": 1},
    },
    "Energy Weapon Focused": {
        1: {"iron": 1},
        2: {"iron": 1, "conductivecomponents": 1},
        3: {"iron": 1, "chromium": 1, "conductiveceramics": 1},
        4: {"germanium": 1, "focuscrystals": 1, "polymercapacitors": 1},
        5: {"niobium": 1, "refinedfocuscrystals": 1, "militarysupercapacitors": 1},
    },
    "Energy Weapon Rapid Fire": {
        1: {"mechanicalscrap": 1},
        2: {"mechanicalscrap": 1, "heatdispersionplate": 1},
        3: {"legacyfirmware": 1, "mechanicalequipment": 1, "precipitatedalloys": 1},
        4: {"consumerfirmware": 1, "mechanicalcomponents": 1, "thermicalloys": 1},
        5: {"configurablecomponents": 1, "precipitatedalloys": 1, "technetium": 1},
    },
    "Energy Weapon Lightweight": {
        1: {"phosphorus": 1},
        2: {"manganese": 1, "salvagedalloys": 1},
        3: {"manganese": 1, "salvagedalloys": 1, "conductiveceramics": 1},
        4: {"conductivecomponents": 1, "phasealloys": 1, "protolightalloys": 1},
        5: {"conductiveceramics": 1, "protolightalloys": 1, "protoradiolicalloys": 1},
    },
    "Energy Weapon Sturdy": {
        1: {"nickel": 1},
        2: {"nickel": 1, "shieldemitters": 1},
        3: {"nickel": 1, "shieldemitters": 1, "tungsten": 1},
        4: {"molybdenum": 1, "tungsten": 1, "zinc": 1},
        5: {"highdensitycomposites": 1, "molybdenum": 1, "technetium": 1},
    },
    "Energy Weapon Short Range Blaster": {
        1: {"nickel": 1},
        2: {"nickel": 1, "consumerfirmware": 1},
        3: {"nickel": 1, "consumerfirmware": 1, "electrochemicalarrays": 1},
        4: {"consumerfirmware": 1, "electrochemicalarrays": 1, "conductivepolymers": 1},
        5: {"industrialfirmware": 1, "biotechconductors": 1, "configurablecomponents": 1},
    },

    # ---- Missile / mine ordnance hardpoints (Missile Rack, Mine Launcher, Torpedo Pylon) ----
    "Missile & Mine Lightweight": {
        1: {"phosphorus": 1},
        2: {"manganese": 1, "salvagedalloys": 1},
        3: {"manganese": 1, "salvagedalloys": 1, "conductiveceramics": 1},
        4: {"conductivecomponents": 1, "phasealloys": 1, "protolightalloys": 1},
        5: {"conductiveceramics": 1, "protolightalloys": 1, "protoradiolicalloys": 1},
    },
    "Missile & Mine Sturdy": {
        1: {"nickel": 1},
        2: {"nickel": 1, "shieldemitters": 1},
        3: {"nickel": 1, "shieldemitters": 1, "tungsten": 1},
        4: {"molybdenum": 1, "tungsten": 1, "zinc": 1},
        5: {"highdensitycomposites": 1, "molybdenum": 1, "technetium": 1},
    },
    "Missile & Mine Rapid Fire": {
        1: {"mechanicalscrap": 1},
        2: {"mechanicalscrap": 1, "heatdispersionplate": 1},
        3: {"legacyfirmware": 1, "mechanicalequipment": 1, "precipitatedalloys": 1},
        4: {"consumerfirmware": 1, "mechanicalcomponents": 1, "thermicalloys": 1},
        5: {"configurablecomponents": 1, "precipitatedalloys": 1, "technetium": 1},
    },
    "Missile & Mine High Capacity Magazine": {
        1: {"mechanicalscrap": 1},
        2: {"mechanicalscrap": 1, "vanadium": 1},
        3: {"mechanicalscrap": 1, "vanadium": 1, "niobium": 1},
        4: {"tin": 1, "mechanicalequipment": 1, "highdensitycomposites": 1},
        5: {"mechanicalcomponents": 1, "militarysupercapacitors": 1, "fedproprietarycomposites": 1},
    },

    # ---- Sensors (core internal) ----
    "Sensors Lightweight": {
        1: {"phosphorus": 1},
        2: {"salvagedalloys": 1, "manganese": 1},
        3: {"salvagedalloys": 1, "manganese": 1, "conductiveceramics": 1},
        4: {"conductivecomponents": 1, "phasealloys": 1, "protolightalloys": 1},
        5: {"conductiveceramics": 1, "protolightalloys": 1, "protoradiolicalloys": 1},
    },
    "Sensors Long Range": {
        1: {"iron": 1},
        2: {"iron": 1, "hybridcapacitors": 1},
        3: {"iron": 1, "hybridcapacitors": 1, "emissiondata": 1},
        4: {"germanium": 1, "electrochemicalarrays": 1, "decodedemissiondata": 1},
        5: {"niobium": 1, "polymercapacitors": 1, "compactemissionsdata": 1},
    },
    "Sensors Wide Angle": {
        1: {"mechanicalscrap": 1},
        2: {"mechanicalscrap": 1, "germanium": 1},
        3: {"mechanicalscrap": 1, "germanium": 1, "scandatabanks": 1},
        4: {"mechanicalequipment": 1, "niobium": 1, "encodedscandata": 1},
        5: {"mechanicalcomponents": 1, "tin": 1, "classifiedscandata": 1},
    },

    # ---- Armour (core internal); "Armour Heavy Duty" already exists above ----
    "Armour Lightweight": {
        1: {"iron": 1},
        2: {"iron": 1, "conductivecomponents": 1},
        3: {"iron": 1, "conductivecomponents": 1, "highdensitycomposites": 1},
        4: {"germanium": 1, "conductiveceramics": 1, "fedproprietarycomposites": 1},
        5: {"conductiveceramics": 1, "tin": 1, "militarygradealloys": 1},
    },
    "Armour Blast Resistant": {
        1: {"nickel": 1},
        2: {"carbon": 1, "zinc": 1},
        3: {"salvagedalloys": 1, "vanadium": 1, "zirconium": 1},
        4: {"galvanisingalloys": 1, "tungsten": 1, "mercury": 1},
        5: {"phasealloys": 1, "molybdenum": 1, "ruthenium": 1},
    },
    "Armour Kinetic Resistant": {
        1: {"nickel": 1},
        2: {"nickel": 1, "vanadium": 1},
        3: {"highdensitycomposites": 1, "salvagedalloys": 1, "vanadium": 1},
        4: {"galvanisingalloys": 1, "tungsten": 1, "fedproprietarycomposites": 1},
        5: {"phasealloys": 1, "molybdenum": 1, "fedcorecomposites": 1},
    },
    "Armour Thermal Resistant": {
        1: {"heatconductionwiring": 1},
        2: {"heatdispersionplate": 1, "nickel": 1},
        3: {"heatexchangers": 1, "salvagedalloys": 1, "vanadium": 1},
        4: {"galvanisingalloys": 1, "tungsten": 1, "heatvanes": 1},
        5: {"phasealloys": 1, "molybdenum": 1, "protoheatradiators": 1},
    },

    # ---- Hull Reinforcement Package (optional internal) ----
    "Hull Reinforcement Heavy Duty": {
        1: {"carbon": 1},
        2: {"carbon": 1, "shieldemitters": 1},
        3: {"carbon": 1, "highdensitycomposites": 1, "shieldemitters": 1},
        4: {"fedproprietarycomposites": 1, "shieldingsensors": 1, "vanadium": 1},
        5: {"compoundshielding": 1, "fedcorecomposites": 1, "tungsten": 1},
    },
    "Hull Reinforcement Lightweight": {
        1: {"iron": 1},
        2: {"iron": 1, "conductivecomponents": 1},
        3: {"iron": 1, "conductivecomponents": 1, "highdensitycomposites": 1},
        4: {"conductiveceramics": 1, "germanium": 1, "fedproprietarycomposites": 1},
        5: {"conductiveceramics": 1, "militarygradealloys": 1, "tin": 1},
    },
    "Hull Reinforcement Blast Resistant": {
        1: {"nickel": 1},
        2: {"carbon": 1, "zinc": 1},
        3: {"salvagedalloys": 1, "vanadium": 1, "zirconium": 1},
        4: {"galvanisingalloys": 1, "tungsten": 1, "mercury": 1},
        5: {"phasealloys": 1, "molybdenum": 1, "ruthenium": 1},
    },
    "Hull Reinforcement Kinetic Resistant": {
        1: {"nickel": 1},
        2: {"nickel": 1, "vanadium": 1},
        3: {"highdensitycomposites": 1, "salvagedalloys": 1, "vanadium": 1},
        4: {"galvanisingalloys": 1, "tungsten": 1, "fedproprietarycomposites": 1},
        5: {"phasealloys": 1, "molybdenum": 1, "fedcorecomposites": 1},
    },
    "Hull Reinforcement Thermal Resistant": {
        1: {"heatconductionwiring": 1},
        2: {"heatdispersionplate": 1, "nickel": 1},
        3: {"heatexchangers": 1, "salvagedalloys": 1, "vanadium": 1},
        4: {"galvanisingalloys": 1, "tungsten": 1, "heatvanes": 1},
        5: {"phasealloys": 1, "molybdenum": 1, "protoheatradiators": 1},
    },

    # ---- Fuel Scoop (optional internal) ----
    "Fuel Scoop Shielded": {
        1: {"wornshieldemitters": 1},
        2: {"carbon": 1, "shieldemitters": 1},
        3: {"carbon": 1, "highdensitycomposites": 1, "shieldemitters": 1},
        4: {"fedproprietarycomposites": 1, "shieldingsensors": 1, "vanadium": 1},
        5: {"compoundshielding": 1, "fedcorecomposites": 1, "tungsten": 1},
    },
}


# Unlock text is deliberately broad, stable guidance on the *type* of activity or
# standing each engineer requires (combat rank, exploration, trade reputation,
# on-foot missions, etc.) rather than exact numeric thresholds — Frontier has
# adjusted specific requirements over time, but the general unlock pathway for
# each engineer has stayed stable. Verify exact current requirements in-game via
# the engineer's holo-terminal or a wiki before relying on this for a hard block.
ENGINEERS = {
    "Felicity Farseer": {"system": "Deciat", "offers": "FSD range, thrusters, sensors", "odyssey": False,
        "unlock": "Available from the start of the game — simply travel to Deciat and speak to her."},
    "Elvira Martuuk": {"system": "Khun", "offers": "FSD range, shields", "odyssey": False,
        "unlock": "Build reputation with a minor faction (Cordial or higher), then travel to Khun."},
    "The Dweller": {"system": "Wyrd", "offers": "power distributor, lasers", "odyssey": False,
        "unlock": "Redeem a bounty voucher for a wanted commander at an Interstellar Factors contact, then travel to Wyrd."},
    "Liz Ryder": {"system": "Eurybia", "offers": "missiles, torpedoes", "odyssey": False,
        "unlock": "Reach a combat rank of Novice or higher, then travel to Eurybia."},
    "Tod 'The Blaster' McQuinn": {"system": "Wolf 397", "offers": "multi-cannons, fragment cannons", "odyssey": False,
        "unlock": "Reach a combat rank of Competent or higher, then travel to Wolf 397."},
    "Zacariah Nemo": {"system": "Yoru", "offers": "fragment cannons, plasma", "odyssey": False,
        "unlock": "Complete missions for minor factions, then travel to Yoru."},
    "Lei Cheung": {"system": "Laksak", "offers": "shield generators, sensors", "odyssey": False,
        "unlock": "Build trade reputation with a minor faction, then travel to Laksak."},
    "Hera Tani": {"system": "Kuwemaki", "offers": "power plant, surface scanner", "odyssey": False,
        "unlock": "Sell exploration data at a high-tech system, then travel to Kuwemaki."},
    "Juri Ishmaak": {"system": "Giryak", "offers": "mines, sensors, scanners", "odyssey": False,
        "unlock": "Scan wake signatures or hand in bounty vouchers, then travel to Giryak."},
    "Selene Jean": {"system": "Kuk", "offers": "hull reinforcement, armour", "odyssey": False,
        "unlock": "Undertake mining activity, then travel to Kuk."},
    "Marco Qwent": {"system": "Sirius", "offers": "power plant, distributor", "odyssey": False,
        "unlock": "Build reputation with Sirius Corporation-aligned factions, then travel to Sirius."},
    "Ram Tah": {"system": "Meene", "offers": "utilities, limpets", "odyssey": False,
        "unlock": "Hand in unlocked Guardian data logs from ancient ruins, then travel to Meene."},
    "Broo Tarquin": {"system": "Muang", "offers": "pulse and burst lasers", "odyssey": False,
        "unlock": "Hand in combat bounty vouchers, then travel to Muang."},
    "The Sarge": {"system": "Beta-3 Tucani", "offers": "cannons, limpets", "odyssey": False,
        "unlock": "Complete combat bounty activity against Thargoids or pirates, then travel to Beta-3 Tucani."},
    "Colonel Bris Dekker": {"system": "Sol", "offers": "FSD interdictors", "odyssey": False,
        "unlock": "Reach a Federation Navy rank, then travel to Sol (Federation-aligned CMDRs only)."},
    "Didi Vatermann": {"system": "Leesti", "offers": "shield boosters", "odyssey": False,
        "unlock": "Reach an exploration rank of Scout or higher, then travel to Leesti."},
    "Bill Turner": {"system": "Alioth", "offers": "plasma accelerators, utilities", "odyssey": False,
        "unlock": "Reach a Federation Navy rank, then travel to Alioth."},
    "Lori Jameson": {"system": "Shinrarta Dezhra", "offers": "sensors, scanners, life support", "odyssey": False,
        "unlock": "Sell exploration data and hold Pilots Federation membership, then travel to Shinrarta Dezhra."},
    "Professor Palin": {"system": "Arque", "offers": "thrusters, FSD", "odyssey": False,
        "unlock": "Reach an exploration rank of Surveyor or higher, then travel to Arque."},
    "Tiana Fortune": {"system": "Achenar", "offers": "interdictors, limpets, sensors", "odyssey": False,
        "unlock": "Reach an Empire Navy rank, then travel to Achenar (Empire-aligned CMDRs only)."},
    "Chloe Sedesi": {"system": "Shenve", "offers": "thrusters, FSD", "odyssey": False,
        "unlock": "Undertake deep-space exploration, then travel to Shenve."},
    "Mel Brandon": {"system": "Luchtaine", "offers": "lasers, shields, FSD, thrusters", "odyssey": False,
        "unlock": "Build reputation with the Silver Bridge Talon minor faction, then travel to Luchtaine."},
    "Petra Olmanova": {"system": "Asura", "offers": "armour, countermeasures, explosives", "odyssey": False,
        "unlock": "Complete combat mission activity, then travel to Asura."},
    "Marsha Hicks": {"system": "Tir", "offers": "multi-cannons, fragments, limpets", "odyssey": False,
        "unlock": "Complete combat bounty activity, then travel to Tir."},
    "Etienne Dorn": {"system": "Los", "offers": "rail guns, power, sensors", "odyssey": False,
        "unlock": "Reach an exploration rank of Pathfinder or higher, then travel to Los."},
    "Domino Green": {"system": "Orishis", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot combat or settlement missions, then visit her in person at Orishis."},
    "Hero Ferrari": {"system": "Siris", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot covert-theft missions, then visit her in person at Siris."},
    "Kit Fowler": {"system": "Capoya", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit her in person at Capoya."},
    "Jude Navarro": {"system": "Aurai", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit him in person at Aurai."},
    "Terra Velasquez": {"system": "Shou Xing", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit her in person at Shou Xing."},
    "Oden Geiger": {"system": "Candiaei", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit him in person at Candiaei."},
    "Uma Laszlo": {"system": "Xuane", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit her in person at Xuane."},
    "Wellington Beck": {"system": "Jolapa", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit him in person at Jolapa."},
    "Yarden Bond": {"system": "Bayan", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit him in person at Bayan."},
    "Baltanos": {"system": "Deriso", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit him in person at Deriso."},
    "Eleanor Bresa": {"system": "Desy", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit her in person at Desy."},
    "Rosa Dayette": {"system": "Kojeara", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit her in person at Kojeara."},
    "Yi Shen": {"system": "Einheriar", "offers": "suit and weapon mods", "odyssey": True,
        "unlock": "Complete on-foot mission activity, then visit him in person at Einheriar."},
}

# Exact access chains from the helper reference.  The journal supplies the
# current Known/Invited/Unlocked state; these steps explain what advances it.
ENGINEER_ACCESS_STEPS = {
    "Elvira Martuuk": (
        "Revealed by default.",
        "Travel at least 300 ly from your starting system.",
        "Provide 3 t of Soontill Relics from Cheranovsky City in Ngurii.",
    ),
    "Mel Brandon": (
        "Reach grade 3 plus 33% reputation with Elvira Martuuk.",
        "Become Friendly with the Colonia Council and complete its invitation mission.",
        "Provide 100,000 credits of bounty vouchers.",
    ),
    "Zacariah Nemo": (
        "Reach grade 3 plus 33% reputation with Elvira Martuuk.",
        "Become Friendly with the Party of Yoru and complete its invitation mission.",
        "Provide 25 t of Xihe Biomorphic Companions from Zhen Dock in Xihe.",
    ),
    "Marco Qwent": (
        "Reach grade 3 plus 33% reputation with Elvira Martuuk.",
        "Become Friendly with Sirius Corporation and complete its invitation mission.",
        "Provide 25 t of Modular Terminals from mission rewards.",
    ),
    "Professor Palin": (
        "Reach grade 3 plus 33% reputation with Marco Qwent.",
        "Visit a system at least 5,000 ly from your starting system.",
        "Provide 25 Sensor Fragments from Thargoid Sensor salvage.",
    ),
    "Lori Jameson": (
        "Reach grade 3 plus 33% reputation with Marco Qwent.",
        "Reach Dangerous combat rank.",
        "Provide 25 t of Kongga Ale.",
    ),
    "Chloe Sedesi": (
        "Reach grade 3 plus 33% reputation with Marco Qwent.",
        "Visit a system at least 5,000 ly from your starting system.",
        "Provide 25 Sensor Fragments from Thargoid Sensor salvage.",
    ),
    "The Dweller": (
        "Revealed by default.",
        "Trade at five different black markets.",
        "Donate 500,000 credits.",
    ),
    "Marsha Hicks": (
        "Reach grade 3 plus 33% reputation with The Dweller.",
        "Reach Surveyor exploration rank.",
        "Mine and provide 10 t of Osmium.",
    ),
    "Lei Cheung": (
        "Reach grade 3 plus 33% reputation with The Dweller.",
        "Buy or sell goods at 50 different stations.",
        "Provide 200 t of Gold.",
    ),
    "Ram Tah": (
        "Reach grade 3 plus 33% reputation with Lei Cheung.",
        "Reach Surveyor exploration rank.",
        "Provide 50 Classified Scan Databanks.",
    ),
    "Felicity Farseer": (
        "Revealed by default.",
        "Reach Scout exploration rank.",
        "Provide 1 t of Meta-Alloys.",
    ),
    "Juri Ishmaak": (
        "Reach grade 3 plus 33% reputation with Felicity Farseer.",
        "Earn more than 50 combat bonds.",
        "Provide 1,000,000 credits of combat bonds.",
    ),
    "Colonel Bris Dekker": (
        "Reach grade 3 plus 33% reputation with Juri Ishmaak.",
        "Become Friendly with the Federation.",
        "Provide 1,000,000 credits of combat bonds.",
    ),
    "The Sarge": (
        "Reach grade 3 plus 33% reputation with Juri Ishmaak.",
        "Reach Midshipman or higher in the Federal Navy.",
        "Provide 50 Aberrant Shield Pattern Analysis.",
    ),
    "Tod 'The Blaster' McQuinn": (
        "Revealed by default.",
        "Hand in at least 15 bounty vouchers.",
        "Provide 100,000 credits of bounty vouchers.",
    ),
    "Petra Olmanova": (
        "Reach grade 3 plus 33% reputation with Tod McQuinn.",
        "Reach Expert combat rank.",
        "Provide 200 t of Progenitor Cells.",
    ),
    "Selene Jean": (
        "Reach grade 3 plus 33% reputation with Tod McQuinn.",
        "Mine at least 500 t of ore.",
        "Provide 10 t of Painite.",
    ),
    "Didi Vatermann": (
        "Reach grade 3 plus 33% reputation with Selene Jean.",
        "Reach Merchant trade rank.",
        "Provide 50 t of Lavian Brandy from Lave Station in Lave.",
    ),
    "Bill Turner": (
        "Reach grade 3 plus 33% reputation with Selene Jean.",
        "Become Friendly with the Alliance and Allied with Alioth Independents for the Alioth permit.",
        "Provide 50 t of Bromellite.",
    ),
    "Liz Ryder": (
        "Revealed by default.",
        "Become Cordial with the Eurybia Blue Mafia.",
        "Provide 200 t of Landmines from planetary markets.",
    ),
    "Etienne Dorn": (
        "Reach grade 3 plus 33% reputation with Liz Ryder.",
        "Reach Dealer trade rank.",
        "Provide 25 Occupied Escape Pods.",
    ),
    "Hera Tani": (
        "Reach grade 3 plus 33% reputation with Liz Ryder.",
        "Reach Outsider or higher in the Imperial Navy.",
        "Provide 50 t of Kamitra Cigars from Hammel Terminal in Kamitra.",
    ),
    "Broo Tarquin": (
        "Reach grade 3 plus 33% reputation with Hera Tani.",
        "Reach Competent combat rank.",
        "Provide 50 t of Fujin Tea from Futen Spaceport in Fujin.",
    ),
    "Tiana Fortune": (
        "Reach grade 3 plus 33% reputation with Hera Tani.",
        "Become Friendly with the Empire.",
        "Provide 50 Decoded Emission Data.",
    ),
    "Domino Green": ("Travel 100 ly in Apex Interstellar Transport shuttles.",),
    "Kit Fowler": (
        "Provide Domino Green with 5 Push to learn about Kit Fowler.",
        "Sell 5 Opinion Polls to bartenders.",
    ),
    "Yarden Bond": (
        "Provide Kit Fowler with 5 Surveillance Equipment to learn about Yarden Bond.",
        "Sell 5 Smear Campaign Plans to bartenders.",
    ),
    "Hero Ferrari": ("Complete 10 low-threat Conflict Zones.",),
    "Wellington Beck": (
        "Provide Hero Ferrari with 5 Settlement Defence Plans.",
        "Sell 15 Classic Entertainment, Multimedia Entertainment or Cat Media to bartenders.",
    ),
    "Uma Laszlo": (
        "Provide Wellington Beck with 5 InSight Entertainment Suites.",
        "Reach Unfriendly reputation or lower with Sirius Corporation.",
    ),
    "Jude Navarro": ("Complete 10 Restore or Reactivation on-foot missions.",),
    "Terra Velasquez": (
        "Provide Jude Navarro with 5 Genetic Repair Meds.",
        "Complete 6 Covert Heist or Covert Theft on-foot missions.",
    ),
    "Oden Geiger": (
        "Provide Terra Velasquez with 15 Financial Projections.",
        "Sell 20 Biological Samples, Employee Genetic Data or Genetic Research to bartenders.",
    ),
    "Baltanos": ("Become Friendly with the Colonia Council.",),
    "Rosa Dayette": ("Sell 10 Culinary Recipes or Cocktail Recipes to stations in Colonia.",),
    "Eleanor Bresa": ("Dock and disembark at 5 settlements in the Colonia system.",),
    "Yi Shen": (
        "Provide one referral: 10 Faction Associates to Baltanos, 10 Manufacturing Instructions to Rosa Dayette, or 10 Digital Designs to Eleanor Bresa.",
        "Complete all three referral deliveries to unlock Yi Shen.",
    ),
}

for _engineer_name, _access_steps in ENGINEER_ACCESS_STEPS.items():
    ENGINEERS[_engineer_name]["unlock_steps"] = _access_steps
    ENGINEERS[_engineer_name]["unlock"] = _access_steps[-1]


def engineer_info(name: str) -> dict:
    return ENGINEERS.get(name, {"system": "", "offers": "", "odyssey": False,
                                "unlock": "", "unlock_steps": ()})


# Compact gathering guidance inspired by the workflow used by dedicated
# material-helper applications.  These are deliberately broad, stable hints:
# the journal tells us what the commander owns, while the workshop explains
# the most useful activity or trader lane without pretending to know a live
# spawn location.
_SOURCE_BY_CATEGORY = {
    "raw": "Surface prospecting, crystalline sites or brain trees; exchange at a Raw trader.",
    "manufactured": "Ship salvage, signal sources and mission rewards; exchange at a Manufactured trader.",
    "encoded": "Scan ships, wakes and data points; exchange at an Encoded trader.",
}

_SOURCE_BY_FAMILY = {
    "capacitors": "Combat-ship salvage, signal sources and mission rewards.",
    "crystals": "Ship salvage and mission rewards; high grades are often fastest through missions.",
    "thermic": "Signal sources and heat-related ship salvage.",
    "conductive": "Transport and authority ship salvage, signal sources or missions.",
    "mechanical": "Ship salvage, encoded emissions and mission rewards.",
    "heat": "Transport-ship salvage and signal sources.",
    "shielding": "Shielded ship salvage and signal sources.",
    "composite": "Combat-ship salvage and high-grade emissions.",
    "alloys": "Ship salvage and high-grade emissions.",
    "chemical": "Transport-ship salvage, emissions and mission rewards.",
    "firmware": "Scan data points and mission terminals.",
    "encryption": "Scan data points, installations and mission targets.",
    "archives": "Scan ships and data points.",
    "wake scans": "Scan low and high wakes with a wake scanner.",
    "emissions": "Scan ships and emissions signal sources.",
    "shield data": "Scan shielded ships during normal traffic or combat.",
    "guardian": "Guardian surface sites; these materials cannot use normal material traders.",
    "thargoid": "Thargoid salvage or surface sites; these materials cannot use normal material traders.",
    "special": "Special activity reward; normal material traders cannot supply it.",
}


def material_source_hint(symbol: str) -> str:
    """Return concise, non-live gathering guidance for a material."""
    info = material_info(symbol)
    return _SOURCE_BY_FAMILY.get(
        info.get("family"),
        _SOURCE_BY_CATEGORY.get(info.get("category"), "Check the material description and current activity rewards."),
    )


def material_relevance(state: dict) -> dict[str, dict]:
    """Describe how every known material relates to the shared wishlist.

    The result gives the UI one authoritative place to decide whether an item
    is missing, required, spare, near capacity, or simply untracked.
    """
    inventory = inventory_counts(state)
    shopping = wishlist_plan(state)
    needed = {row["symbol"]: row for row in shopping["materials"]}
    result = {}
    symbols = set(MATERIALS) | set(inventory) | set(needed)
    for symbol in symbols:
        info = material_info(symbol)
        have = int(inventory.get(symbol, 0))
        need = int((needed.get(symbol) or {}).get("need", 0))
        deficit = max(0, need - have)
        grade = info.get("grade")
        cap = GRADE_CAP.get(grade)
        fill = (have / cap) if cap else 0.0
        if deficit:
            status = "MISSING"
        elif need:
            status = "READY"
        elif cap and fill >= 0.85:
            status = "NEAR CAP"
        elif have:
            status = "SPARE"
        else:
            status = "UNHELD"
        result[symbol] = {
            **info,
            "have": have,
            "need": need,
            "deficit": deficit,
            "cap": cap,
            "fill": fill,
            "status": status,
            "source": material_source_hint(symbol),
        }
    return result


def collection_priorities(state: dict, limit: int | None = None) -> list[dict]:
    """Return wishlist shortages in a useful collection order."""
    rows = [row for row in material_relevance(state).values() if row["deficit"]]
    rows.sort(key=lambda row: (-(row.get("grade") or 0), -row["deficit"], row["name"]))
    return rows if limit is None else rows[:max(0, int(limit))]


_ODYSSEY_KEY_USES = {
    "power regulator": "Suit upgrades and settlement restoration; high-value engineering stock.",
    "suit schematic": "Required for suit grade upgrades.",
    "weapon schematic": "Required for weapon grade upgrades.",
    "manufacturing instructions": "Common weapon and suit modification ingredient.",
    "opinion polls": "Engineer invitation requirement; keep until access is complete.",
    "settlement defence plans": "Engineer unlock requirement; rare data worth keeping.",
    "smear campaign plans": "Engineer unlock requirement; rare data worth keeping.",
    "financial projections": "Engineer unlock and modification ingredient.",
    "push": "Engineer invitation item and bartender-trade good.",
    "surveillance equipment": "Engineer invitation item.",
    "genetic repair meds": "Engineer invitation item.",
    "insight entertainment suite": "Engineer invitation item.",
}


# Common suit and weapon modifications.  Names match the localized English
# values stored by ShipLocker.json so goals remain useful without a separate
# database or network lookup.
ODYSSEY_BLUEPRINTS = {
    "Added Melee Damage": {
        "Combat Training Material": 5, "Combatant Performance": 5,
        "Epinephrine": 5, "Micro Thrusters": 8,
    },
    "Combat Movement Speed": {
        "Evacuation Protocols": 5, "Genetic Research": 3,
        "Epinephrine": 5, "pH Neutraliser": 8,
    },
    "Damage Resistance": {
        "Weapon Inventory": 5, "Ballistics Data": 5, "Titanium Plating": 3,
        "Epoxy Adhesive": 8, "Carbon Fibre Plating": 3,
    },
    "Enhanced Tracking": {
        "Topographical Surveys": 5, "Stellar Activity Logs": 5,
        "Spectral Analysis Data": 5, "Transmitter": 3, "Circuit Board": 3,
    },
    "Extra Ammo Capacity": {
        "Recycling Logs": 8, "Weapon Test Data": 5,
        "Production Reports": 5, "Weapon Component": 3,
    },
    "Extra Backpack Capacity": {
        "Weapon Inventory": 5, "Chemical Inventory": 5, "Digital Designs": 5,
        "Epoxy Adhesive": 5, "Memory Chip": 3,
    },
    "Faster Shield Regeneration": {
        "Reactor Output Review": 5, "Ion Battery": 3,
        "Micro Transformer": 8, "Electrical Wiring": 8,
    },
    "Improved Battery Capacity": {
        "Reactor Output Review": 5, "Maintenance Logs": 8, "Ion Battery": 3,
        "Micro Supercapacitor": 5, "Electrical Wiring": 5,
    },
    "Improved Jump Assist": {
        "G-Meds": 5, "Topographical Surveys": 5, "Micro Thrusters": 3, "Motor": 5,
    },
    "Increased Air Reserves": {
        "Pharmaceutical Patents": 3, "Air Quality Reports": 8,
        "Oxygenic Bacteria": 5, "pH Neutraliser": 8,
    },
    "Increased Sprint Duration": {
        "Troop Deployment Records": 3, "Gene Sequencing Data": 3,
        "Medical Trial Records": 3, "Oxygenic Bacteria": 5, "Chemical Catalyst": 8,
    },
    "Night Vision": {
        "Surveillance Equipment": 5, "Surveillance Logs": 3,
        "NOC Data": 3, "Radioactivity Data": 3, "Circuit Switch": 5,
    },
    "Quieter Footsteps": {
        "Settlement Assault Plans": 3, "Tactical Plans": 5, "Patrol Routes": 5,
        "Micro Hydraulics": 3, "Viscoelastic Polymer": 8,
    },
    "Reduced Tool Battery Consumption": {
        "Reactor Output Review": 5, "Electrical Wiring": 8,
        "Electrical Fuse": 3, "Micro Transformer": 5,
    },
    "Audio Masking": {
        "Audio Logs": 3, "Patrol Routes": 5, "Scrambler": 5,
        "Transmitter": 8, "Circuit Board": 3,
    },
    "Faster Handling": {
        "Operational Manual": 5, "Combatant Performance": 5,
        "Combat Training Material": 5, "Viscoelastic Polymer": 3,
    },
    "Magazine Size": {
        "Weapon Test Data": 5, "Security Expenses": 3, "Weapon Component": 3,
        "Tungsten Carbide": 3, "Metal Coil": 5,
    },
    "Noise Suppressor": {
        "Atmospheric Data": 5, "Mining Analytics": 5,
        "Viscoelastic Polymer": 8, "Weapon Component": 3,
    },
    "Reload Speed": {
        "Operational Manual": 5, "Production Reports": 5,
        "Combat Training Material": 5, "Micro Hydraulics": 5, "Electromagnet": 5,
    },
    "Scope": {
        "Spectral Analysis Data": 5, "Biometric Data": 3,
        "Optical Lens": 5, "Optical Fibre": 3,
    },
    "Stability": {
        "Mining Analytics": 5, "Risk Assessments": 8,
        "Viscoelastic Polymer": 5, "Micro Hydraulics": 5,
    },
    "Stowed Reloading": {
        "Digital Designs": 5, "Operational Manual": 5, "Production Schedule": 5,
        "Circuit Board": 3, "Encrypted Memory Chip": 8,
    },
}


def _locker_key(value: str) -> str:
    return "".join(character for character in (value or "").casefold() if character.isalnum())


def odyssey_inventory_counts(state: dict) -> dict[str, dict]:
    """Return normalized Odyssey locker counts while preserving display names."""
    result = {}
    for group in ("items", "components", "data", "consumables"):
        for item in ((state.get("ship_locker") or {}).get(group) or []):
            name = item.get("name") or ""
            key = _locker_key(name)
            if not key:
                continue
            row = result.setdefault(key, {"name": name, "count": 0, "group": group})
            row["count"] += int(item.get("count") or 0)
    return result


def odyssey_wishlist_plan(state: dict) -> dict:
    """Combine every Odyssey modification goal into one locker shopping list."""
    inventory = odyssey_inventory_counts(state)
    needed = {}
    goals = []
    for goal in state.get("odyssey_goals") or []:
        name = goal.get("name")
        recipe = ODYSSEY_BLUEPRINTS.get(name)
        if not recipe:
            continue
        quantity = max(1, min(99, int(goal.get("quantity") or 1)))
        goals.append({"name": name, "quantity": quantity})
        for material, amount in recipe.items():
            key = _locker_key(material)
            row = needed.setdefault(key, {"symbol": key, "name": material, "need": 0})
            row["need"] += int(amount) * quantity
    materials = []
    for key, row in needed.items():
        held = inventory.get(key) or {}
        have = int(held.get("count") or 0)
        materials.append({
            **row,
            "have": have,
            "deficit": max(0, row["need"] - have),
            "group": held.get("group", "unknown"),
        })
    materials.sort(key=lambda row: (row["deficit"] == 0, -row["deficit"], row["name"]))
    return {
        "goals": goals,
        "materials": materials,
        "required_units": sum(row["need"] for row in materials),
        "missing_units": sum(row["deficit"] for row in materials),
        "complete": bool(goals) and all(row["deficit"] == 0 for row in materials),
    }


def odyssey_item_use(name: str, group: str = "") -> tuple[str, bool]:
    """Return a useful locker description and whether the item is notable."""
    text = (name or "").replace("_", " ").casefold()
    for token, description in _ODYSSEY_KEY_USES.items():
        if token in text:
            return description, True
    group_key = (group or "").casefold()
    if group_key == "consumables":
        return "Mission and on-foot consumable; not an engineering ingredient.", False
    if group_key == "data":
        return "Odyssey data; keep when a suit, weapon or engineer goal requires it.", False
    if group_key == "components":
        return "Odyssey asset used by suit and weapon modifications or bartender trades.", False
    return "Odyssey good used by engineers, upgrades, missions or bartender trades.", False


def inventory_counts(state: dict) -> dict[str, int]:
    out = {}
    for category in ("raw", "manufactured", "encoded"):
        for symbol, item in (state.get(category) or {}).items():
            out[symbol.lower()] = int(item.get("count", 0) if isinstance(item, dict) else item)
    return out


def requirements(blueprint: str, target_grade: int, rolls=None,
                 current_grade: int = 0, quantity: int = 1) -> dict[str, int]:
    recipe = BLUEPRINTS.get(blueprint)
    if not recipe:
        raise KeyError(blueprint)
    rolls = rolls or ROLLS_PER_GRADE
    need = {}
    current_grade = max(0, min(4, int(current_grade or 0)))
    target_grade = min(5, max(1, int(target_grade)))
    quantity = max(1, min(99, int(quantity or 1)))
    for grade in range(current_grade + 1, target_grade + 1):
        for symbol, qty in recipe.get(grade, {}).items():
            need[symbol] = need.get(symbol, 0) + qty * rolls.get(grade, grade) * quantity
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


def plan(blueprint: str, target_grade: int, inventory: dict,
         current_grade: int = 0, quantity: int = 1) -> dict:
    need = requirements(blueprint, target_grade, current_grade=current_grade, quantity=quantity)
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
    return {"blueprint": blueprint, "grade": int(target_grade),
            "current_grade": int(current_grade or 0), "quantity": int(quantity or 1), "materials": rows,
            "craftable": all(row["deficit"] == 0 for row in rows)}


def pinned_plans(state: dict) -> list[dict]:
    inventory = inventory_counts(state)
    plans = []
    for pin in state.get("pinned_blueprints") or []:
        try:
            plans.append(plan(
                pin["name"], pin.get("target_grade", pin.get("grade", 5)), inventory,
                current_grade=pin.get("current_grade", 0), quantity=pin.get("quantity", 1),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return plans


def ready_blueprints(state: dict) -> set[str]:
    return {row["blueprint"] for row in pinned_plans(state) if row["craftable"]}


def wishlist_plan(state: dict) -> dict:
    """Return one combined, non-double-counted shopping list for every pin."""
    inventory = inventory_counts(state)
    needed = {}
    valid_pins = 0
    for pin in state.get("pinned_blueprints") or []:
        try:
            req = requirements(
                pin["name"], pin.get("target_grade", pin.get("grade", 5)),
                current_grade=pin.get("current_grade", 0), quantity=pin.get("quantity", 1),
            )
        except (KeyError, TypeError, ValueError):
            continue
        valid_pins += 1
        for symbol, count in req.items():
            needed[symbol] = needed.get(symbol, 0) + count
    rows = []
    for symbol, count in needed.items():
        info = material_info(symbol)
        have = int(inventory.get(symbol, 0))
        deficit = max(0, count - have)
        rows.append({**info, "need": count, "have": have, "deficit": deficit})
    rows.sort(key=lambda row: (row["deficit"] == 0, -(row.get("grade") or 0), row["name"]))
    return {
        "pins": valid_pins,
        "materials": rows,
        "required_units": sum(row["need"] for row in rows),
        "missing_units": sum(row["deficit"] for row in rows),
        "complete": bool(valid_pins) and all(row["deficit"] == 0 for row in rows),
    }
