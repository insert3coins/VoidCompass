"""Vendor SrvSurvey's colonisation reference data into data/colonisation/.

SrvSurvey (https://github.com/njthomson/SrvSurvey, GPL-3.0, like Void
Compass) ships the build-type cost table Raven Colonial uses and English
names for every commodity. This copies the parts Colonisation needs:

* build_costs.json  - every build type: tier, orbital/surface, display name,
                      layouts and the cargo it takes.
* commodities.json  - construction commodity id -> English name and market
                      category (SrvSurvey's mapCargoType, including the names
                      Frontier corrected).

Run again to refresh from a newer SrvSurvey checkout:

    python tools/vendor_colonisation_data.py D:/Programming/Elite/SrvSurvey
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "colonisation"

# SrvSurvey's ColonyData.mapCargoType: market category -> commodity ids. The
# old names (microbialfurnaces, landenrichmentsystems, muonimager,
# combatstabilizers) are kept so older projects still resolve.
CARGO_TYPES = {
    "Chemicals": ["liquidoxygen", "pesticides", "surfacestabilisers", "water"],
    "Consumer Items": ["evacuationshelter", "survivalequipment"],
    "Foods": ["animalmeat", "coffee", "fish", "foodcartridges", "fruitandvegetables", "grain", "tea"],
    "Industrial Materials": ["ceramiccomposites", "cmmcomposite", "insulatingmembrane", "polymers", "semiconductors", "superconductors"],
    "Legal Drugs": ["beer", "liquor", "wine"],
    "Machinery": ["buildingfabricators", "cropharvesters", "emergencypowercells", "geologicalequipment", "microbialfurnaces", "heliostaticfurnaces", "mineralextractors", "powergenerators", "thermalcoolingunits", "waterpurifiers"],
    "Medicines": ["agriculturalmedicines", "basicmedicines", "combatstabilisers", "combatstabilizers"],
    "Metals": ["aluminium", "copper", "steel", "titanium"],
    "Technology": ["advancedcatalysers", "autofabricators", "bioreducinglichen", "computercomponents", "hazardousenvironmentsuits", "landenrichmentsystems", "terrainenrichmentsystems", "medicaldiagnosticequipment", "microcontrollers", "muonimager", "mutomimager", "resonatingseparators", "robotics", "structuralregulators"],
    "Textiles": ["militarygradefabrics"],
    "Waste": ["biowaste"],
    "Weapons": ["battleweapons", "nonlethalweapons", "reactivearmour"],
}
# Names the .resx lacks or spells for a different id.
NAME_FALLBACKS = {
    "cmmcomposite": "CMM Composite",
    "microbialfurnaces": "Microbial Furnaces",
    "landenrichmentsystems": "Land Enrichment Systems",
    "muonimager": "Muon Imager",
    "combatstabilizers": "Combat Stabilisers",
}


def _resx_names(path: Path) -> dict[str, str]:
    tree = ElementTree.parse(path)
    names = {}
    for data in tree.getroot().iter("data"):
        value = data.find("value")
        if value is not None and value.text:
            names[data.get("name", "").casefold()] = value.text.strip()
    return names


def main(srvsurvey: Path) -> None:
    project = srvsurvey / "SrvSurvey"
    costs = json.loads((project / "colonization-costs2.json").read_text(encoding="utf-8"))
    names = _resx_names(project / "Properties" / "Commodities.resx")
    categories = _resx_names(project / "Properties" / "CommodityCategories.resx")
    commodities = {}
    for category, ids in CARGO_TYPES.items():
        for commodity in ids:
            name = names.get(commodity) or NAME_FALLBACKS.get(commodity) or commodity.title()
            commodities[commodity] = {"name": name, "category": categories.get(category.casefold(), category)}
    # Any id the cost table uses must resolve.
    missing = sorted({key for row in costs for key in row["cargo"]} - set(commodities))
    if missing:
        raise SystemExit(f"cost table commodities without a category: {missing}")
    OUT.mkdir(parents=True, exist_ok=True)
    header = {"source": "SrvSurvey (https://github.com/njthomson/SrvSurvey), GPL-3.0",
              "generated_by": "tools/vendor_colonisation_data.py"}
    (OUT / "build_costs.json").write_text(json.dumps({**header, "build_types": costs}, indent=1), encoding="utf-8")
    (OUT / "commodities.json").write_text(json.dumps({**header, "commodities": commodities}, indent=1), encoding="utf-8")
    print(f"{len(costs)} build types, {len(commodities)} commodities -> {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\Programming\Elite\SrvSurvey"))
