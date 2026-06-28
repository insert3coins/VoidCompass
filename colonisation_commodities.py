# Local colonisation commodity helpers, adapted from the EDCOLONY EDMC plugin.

COLONISATION_COMMODITIES = [
    "agriculturalmedicines", "advancedcatalysers", "aluminium", "animalmeat",
    "autofabricators", "basicmedicines", "battleweapons", "beer",
    "bioreducinglichen", "biowaste", "buildingfabricators",
    "ceramiccomposites", "cmmcomposite", "coffee", "combatstabilisers",
    "computercomponents", "copper", "cropharvesters", "emergencypowercells",
    "evacuationshelter", "fish", "foodcartridges", "fruitandvegetables",
    "geologicalequipment", "grain", "hazardousenvironmentsuits",
    "insulatingmembrane", "terrainenrichmentsystems", "liquidoxygen", "liquor",
    "medicaldiagnosticequipment", "microcontrollers", "heliostaticfurnaces",
    "militarygradefabrics", "mineralextractors", "mutomimager",
    "nonlethalweapons", "pesticides", "polymers", "powergenerators",
    "reactivearmour", "resonatingseparators", "robotics", "semiconductors",
    "steel", "structuralregulators", "superconductors", "surfacestabilisers",
    "survivalequipment", "tea", "thermalcoolingunits", "titanium", "water",
    "waterpurifiers", "wine",
]

COMMODITY_NAME_MAPPING = {
    "agriculturalmedicines": "Agri-Medicines",
    "advancedcatalysers": "Advanced Catalysers",
    "aluminium": "Aluminium",
    "animalmeat": "Animal Meat",
    "autofabricators": "Auto-Fabricators",
    "basicmedicines": "Basic Medicines",
    "battleweapons": "Battle Weapons",
    "beer": "Beer",
    "bioreducinglichen": "Bioreducing Lichen",
    "biowaste": "Biowaste",
    "buildingfabricators": "Building Fabricators",
    "ceramiccomposites": "Ceramic Composites",
    "cmmcomposite": "CMM Composite",
    "coffee": "Coffee",
    "combatstabilisers": "Combat Stabilisers",
    "computercomponents": "Computer Components",
    "copper": "Copper",
    "cropharvesters": "Crop Harvesters",
    "emergencypowercells": "Emergency Power Cells",
    "evacuationshelter": "Evacuation Shelter",
    "fish": "Fish",
    "foodcartridges": "Food Cartridges",
    "fruitandvegetables": "Fruit and Vegetables",
    "geologicalequipment": "Geological Equipment",
    "grain": "Grain",
    "hazardousenvironmentsuits": "H.E. Suits",
    "insulatingmembrane": "Insulating Membrane",
    "terrainenrichmentsystems": "Land Enrichment Systems",
    "liquidoxygen": "Liquid Oxygen",
    "liquor": "Liquor",
    "medicaldiagnosticequipment": "Medical Diagnostic Equipment",
    "microcontrollers": "Micro Controllers",
    "heliostaticfurnaces": "Microbial Furnaces",
    "militarygradefabrics": "Military Grade Fabrics",
    "mineralextractors": "Mineral Extractors",
    "mutomimager": "Muon Imager",
    "nonlethalweapons": "Non-Lethal Weapons",
    "pesticides": "Pesticides",
    "polymers": "Polymers",
    "powergenerators": "Power Generators",
    "reactivearmour": "Reactive Armour",
    "resonatingseparators": "Resonating Separators",
    "robotics": "Robotics",
    "semiconductors": "Semiconductors",
    "steel": "Steel",
    "structuralregulators": "Structural Regulators",
    "superconductors": "Superconductors",
    "surfacestabilisers": "Surface Stabilisers",
    "survivalequipment": "Survival Equipment",
    "tea": "Tea",
    "thermalcoolingunits": "Thermal Cooling Units",
    "titanium": "Titanium",
    "water": "Water",
    "waterpurifiers": "Water Purifiers",
    "wine": "Wine",
}

CATEGORY = {
    "agriculturalmedicines": "Medicines", "advancedcatalysers": "Technology",
    "aluminium": "Metals", "animalmeat": "Foods",
    "autofabricators": "Technology", "basicmedicines": "Medicines",
    "battleweapons": "Weapons", "beer": "Legal Drugs",
    "bioreducinglichen": "Technology", "biowaste": "Waste",
    "buildingfabricators": "Machinery", "ceramiccomposites": "Industrial Materials",
    "cmmcomposite": "Industrial Materials", "coffee": "Foods",
    "combatstabilisers": "Medicines", "computercomponents": "Technology",
    "copper": "Metals", "cropharvesters": "Machinery",
    "emergencypowercells": "Machinery", "evacuationshelter": "Consumer Items",
    "fish": "Foods", "foodcartridges": "Foods",
    "fruitandvegetables": "Foods", "geologicalequipment": "Machinery",
    "grain": "Foods", "hazardousenvironmentsuits": "Technology",
    "insulatingmembrane": "Industrial Materials",
    "terrainenrichmentsystems": "Technology", "liquidoxygen": "Chemicals",
    "liquor": "Legal Drugs", "medicaldiagnosticequipment": "Technology",
    "microcontrollers": "Technology", "heliostaticfurnaces": "Machinery",
    "militarygradefabrics": "Textiles", "mineralextractors": "Machinery",
    "mutomimager": "Technology", "nonlethalweapons": "Weapons",
    "pesticides": "Chemicals", "polymers": "Industrial Materials",
    "powergenerators": "Machinery", "reactivearmour": "Weapons",
    "resonatingseparators": "Technology", "robotics": "Technology",
    "semiconductors": "Industrial Materials", "steel": "Metals",
    "structuralregulators": "Technology", "superconductors": "Industrial Materials",
    "surfacestabilisers": "Chemicals", "survivalequipment": "Consumer Items",
    "tea": "Foods", "thermalcoolingunits": "Machinery", "titanium": "Metals",
    "water": "Chemicals", "waterpurifiers": "Machinery", "wine": "Legal Drugs",
}

CATEGORY_ORDER = [
    "Chemicals", "Consumer Items", "Foods", "Industrial Materials",
    "Legal Drugs", "Machinery", "Medicines", "Metals", "Technology",
    "Textiles", "Waste", "Weapons", "Uncategorized",
]

SOURCE = {
    "liquidoxygen": ["Refinery"], "pesticides": ["High Tech"],
    "surfacestabilisers": ["Refinery"], "water": ["Agriculture"],
    "evacuationshelter": ["High Tech"], "survivalequipment": ["Industrial"],
    "animalmeat": ["Agriculture"], "coffee": ["Agriculture"],
    "fish": ["Agriculture"], "foodcartridges": ["Industrial"],
    "fruitandvegetables": ["Agriculture"], "grain": ["Agriculture"],
    "tea": ["Agriculture"], "ceramiccomposites": ["Refinery"],
    "cmmcomposite": ["Refinery"], "insulatingmembrane": ["Refinery"],
    "polymers": ["Refinery"], "semiconductors": ["Refinery"],
    "superconductors": ["Refinery"], "buildingfabricators": ["Industrial"],
    "cropharvesters": ["Industrial"], "emergencypowercells": ["High Tech", "Industrial"],
    "geologicalequipment": ["Industrial"], "heliostaticfurnaces": ["High Tech"],
    "mineralextractors": ["Industrial"], "powergenerators": ["Industrial"],
    "thermalcoolingunits": ["Industrial"], "waterpurifiers": ["Industrial"],
    "agriculturalmedicines": ["High Tech"], "basicmedicines": ["High Tech", "Industrial"],
    "aluminium": ["Refinery"], "copper": ["Refinery"], "steel": ["Refinery"],
    "titanium": ["Refinery"], "advancedcatalysers": ["High Tech"],
    "bioreducinglichen": ["High Tech"], "autofabricators": ["High Tech"],
    "computercomponents": ["Industrial"], "hazardousenvironmentsuits": ["High Tech"],
    "terrainenrichmentsystems": ["High Tech"],
    "medicaldiagnosticequipment": ["High Tech"], "microcontrollers": ["High Tech"],
    "mutomimager": ["High Tech", "Industrial"], "resonatingseparators": ["High Tech"],
    "robotics": ["High Tech"], "structuralregulators": ["High Tech"],
    "militarygradefabrics": ["Industrial"], "biowaste": ["All except Agriculture"],
    "nonlethalweapons": ["High Tech", "Military"],
    "reactivearmour": ["High Tech", "Military"],
    "battleweapons": ["High Tech", "Industrial", "Military"],
    "combatstabilisers": ["High Tech"], "beer": ["Agriculture"],
    "liquor": ["Agriculture", "Industrial"], "wine": ["Agriculture"],
}

SOURCE_ORDER = [
    "Agriculture", "Industrial", "High Tech", "Refinery", "Military",
    "All except Agriculture", "Unknown Source",
]

ALIASES = {
    "combatstabilizers": "combatstabilisers",
}


def normalize_commodity_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    n = name.strip().lower()
    if n.startswith("$") and "_name;" in n:
        n = n.split("_name;", 1)[0][1:]
    return ALIASES.get(n, n)


def get_commodity_display_name(commodity_name):
    canonical = normalize_commodity_name(commodity_name)
    return COMMODITY_NAME_MAPPING.get(canonical, str(commodity_name or ""))


def get_commodity_category(commodity_name: str) -> str:
    canonical = normalize_commodity_name(commodity_name)
    return CATEGORY.get(canonical, "Uncategorized")


def get_primary_source(commodity_name: str) -> str:
    canonical = normalize_commodity_name(commodity_name)
    values = SOURCE.get(canonical)
    if values:
        return values[0]
    return "Unknown Source"
