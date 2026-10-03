"""Colonisation reference data: build types, their cargo, commodity names.

Generated from SrvSurvey by tools/vendor_colonisation_data.py. Commodity ids
are Raven Colonial's: lower case and language agnostic (``liquidoxygen``).
"""

from __future__ import annotations

from functools import lru_cache
import json
import math

from voidcompass.core.paths import resource_path

SYSTEM_COLONISATION_SHIP = "System Colonisation Ship"
EXT_PANEL_COLONISATION_SHIP = "$EXT_PANEL_ColonisationShip"
PLANETARY_CONSTRUCTION_SITE = "Planetary Construction Site:"
ORBITAL_CONSTRUCTION_SITE = "Orbital Construction Site:"
FC_LOADING = "fc_loading"


@lru_cache(maxsize=1)
def build_types():
    """Every build type: ``{buildType, category, tier, location,
    displayName, layouts, cargo}`` in tier order."""
    try:
        data = json.loads(resource_path("data", "colonisation", "build_costs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    rows = [row for row in data.get("build_types") or () if isinstance(row, dict)]
    return tuple(sorted(rows, key=lambda row: (int(row.get("tier") or 0), str(row.get("displayName") or ""))))


@lru_cache(maxsize=1)
def commodities():
    """``{id: {"name", "category"}}`` for every construction commodity."""
    try:
        data = json.loads(resource_path("data", "colonisation", "commodities.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dict(data.get("commodities") or {})


def commodity_id(value):
    """``$LiquidOxygen_Name;`` / ``LiquidOxygen`` / ``liquidoxygen`` ->
    ``liquidoxygen``, as Raven Colonial names commodities."""
    text = str(value or "").strip()
    if text.startswith("$"):
        text = text[1:]
    if text.casefold().endswith("_name;"):
        text = text[:-len("_name;")]
    return text.casefold()


def commodity_name(value):
    key = commodity_id(value)
    row = commodities().get(key)
    return row["name"] if row else key.title()


def commodity_category(value):
    row = commodities().get(commodity_id(value))
    return row["category"] if row else "Other"


def build_type_for(layout):
    """The build type a layout (``dual_truss``) or build type belongs to."""
    wanted = str(layout or "").strip().casefold()
    if not wanted:
        return None
    for row in build_types():
        if wanted == str(row.get("buildType") or "").casefold():
            return row
        if any(wanted == str(item).casefold() for item in row.get("layouts") or ()):
            return row
    return None


def build_type_label(layout):
    if str(layout or "").casefold() == FC_LOADING:
        return "Fleet carrier loading"
    row = build_type_for(layout)
    if row is None:
        return str(layout or "Unknown").replace("_", " ").title()
    return f"{row.get('displayName')} (Tier {row.get('tier')})"


def match_by_cargo(cargo):
    """The build type whose cargo is nearest the given needs (SrvSurvey's
    least-squares match), for a site whose type is not known."""
    cargo = {commodity_id(key): int(value or 0) for key, value in (cargo or {}).items()}
    best = None
    for row in build_types():
        names = set(cargo) | set(row.get("cargo") or {})
        distance = math.sqrt(sum((int((row.get("cargo") or {}).get(name, 0)) - cargo.get(name, 0)) ** 2 for name in names))
        if distance > 0 and (best is None or distance < best[0]):
            best = (distance, row)
    return best[1] if best else None


def is_construction_site(station_name, station_services=None):
    """A docked station that takes colonisation deliveries."""
    name = str(station_name or "")
    named = (name.casefold().startswith(PLANETARY_CONSTRUCTION_SITE.casefold())
             or name.casefold().startswith(ORBITAL_CONSTRUCTION_SITE.casefold())
             or name.casefold().startswith(EXT_PANEL_COLONISATION_SHIP.casefold())
             or name == SYSTEM_COLONISATION_SHIP)
    if not named:
        return False
    if station_services is None:
        return True
    return any(str(service).casefold() == "colonisationcontribution" for service in station_services)


def is_primary_port_site(station_name):
    name = str(station_name or "")
    return name.casefold().startswith(EXT_PANEL_COLONISATION_SHIP.casefold()) or name == SYSTEM_COLONISATION_SHIP


def default_project_name(station_name):
    """A construction site's name without the game's prefix."""
    name = str(station_name or "")
    if is_primary_port_site(name):
        return "Primary port"
    for prefix in (EXT_PANEL_COLONISATION_SHIP + "; ", PLANETARY_CONSTRUCTION_SITE, ORBITAL_CONSTRUCTION_SITE):
        if name.casefold().startswith(prefix.casefold()):
            name = name[len(prefix):]
    return name.strip() or "Construction site"


def depot_needs(resources):
    """``{id: still needed}`` from ColonisationConstructionDepot's
    ResourcesRequired (raw journal rows or the watcher's normalised ones)."""
    needs = {}
    for row in resources or ():
        if not isinstance(row, dict):
            continue
        name = commodity_id(row.get("Name") or row.get("name"))
        required = int(row.get("RequiredAmount", row.get("required", 0)) or 0)
        provided = int(row.get("ProvidedAmount", row.get("provided", 0)) or 0)
        if name:
            needs[name] = max(0, required - provided)
    return needs


def depot_total(resources):
    return sum(int((row or {}).get("RequiredAmount", (row or {}).get("required", 0)) or 0) for row in resources or ())
