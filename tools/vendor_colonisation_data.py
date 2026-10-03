"""Vendor SrvSurvey's colonisation reference data into data/colonisation/.

SrvSurvey (https://github.com/njthomson/SrvSurvey, GPL-3.0, like Void
Compass) ships the build-type cost table Raven Colonial uses and English
names for every commodity. This copies the parts Colonisation needs:

* build_costs.json  - every build type: tier, orbital/surface, display name,
                      layouts and the cargo it takes.
* commodities.json  - construction commodity id -> English name and market
                      category (SrvSurvey's mapCargoType, including the names
                      Frontier corrected).

From RavenColonialWeb (https://github.com/njthomson/RavenColonialWeb,
GPL-3.0), the website's system planner data:

* site_types.json   - every site type: class, tier, pads, economy influence,
                      tier points it needs and gives, system effects, score,
                      prerequisites and unlocks; pad counts per layout; the
                      system unlocks and what enables them.
* haul_costs.json   - approximate cargo per build type, for planning.

Run again to refresh from newer checkouts:

    python tools/vendor_colonisation_data.py D:/Programming/Elite/SrvSurvey D:/Programming/Elite/RavenColonialWeb
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


def _ts_literal(text: str):
    """A TypeScript object/array literal (as site-data.ts writes them) as
    Python: drops comments, quotes bare keys, swaps single quotes, drops
    trailing commas and leading plus signs."""
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"'([^'\\]*)'", lambda m: json.dumps(m.group(1)), text)
    text = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', text)
    text = re.sub(r":\s*\+(\d)", r": \1", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def _block(source: str, start: str) -> str:
    """The bracketed literal that follows ``start``."""
    index = source.index(start) + len(start)
    opener = source[index:].lstrip()[0]
    index = source.index(opener, index)
    closer = {"[": "]", "{": "}"}[opener]
    depth = 0
    for position in range(index, len(source)):
        char = source[position]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return source[index:position + 1]
    raise ValueError(start)


def vendor_raven(raven: Path) -> None:
    src = raven / "src"
    site_data = (src / "site-data.ts").read_text(encoding="utf-8")
    system_model = (src / "system-model2.ts").read_text(encoding="utf-8")
    site_types = _ts_literal(_block(site_data, "export const siteTypes: SiteType[] ="))
    pads = _ts_literal(_block(site_data, "export const mapSitePads: Record<string, [s: number, m: number, l: number,]> ="))
    primary = {f"t{tier}": json.loads(re.search(rf"primaryPortsT{tier} = (\[[^\]]*\])", site_data).group(1).replace("'", '"'))
               for tier in (1, 2, 3)}
    unlocks = _ts_literal(_block(system_model, "export const mapSysUnlocks: Record<SysUnlocks, { icon: string, title: string, needTypes: string[], needs: string }> ="))
    pre_reqs = {name: json.loads(found) for name, found in
                re.findall(r"case '(\w+)': return (\[[^\]]*\]);", _block(system_model, "export const getPreReqNeeded = (type: SiteType): string[] =>"))}
    if not pre_reqs or len(site_types) < 40:
        raise SystemExit("site-data.ts changed shape: check the vendoring")
    header = {"source": "RavenColonialWeb (https://github.com/njthomson/RavenColonialWeb), GPL-3.0",
              "generated_by": "tools/vendor_colonisation_data.py"}
    (OUT / "site_types.json").write_text(json.dumps({
        **header, "site_types": site_types, "site_pads": pads, "primary_ports": primary,
        "system_unlocks": {key: {"title": row["title"], "need_types": row["needTypes"], "needs": row["needs"]}
                           for key, row in unlocks.items()},
        "pre_reqs": pre_reqs,
    }, indent=1), encoding="utf-8")
    haul = json.loads((src / "assets" / "haul-costs.json").read_text(encoding="utf-8"))
    (OUT / "haul_costs.json").write_text(json.dumps({**header, **haul}, indent=1), encoding="utf-8")
    print(f"{len(site_types)} site types, {len(pads)} pad layouts, {len(unlocks)} unlocks -> {OUT}")


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
    vendor_raven(Path(sys.argv[2] if len(sys.argv) > 2 else r"D:\Programming\Elite\RavenColonialWeb"))
