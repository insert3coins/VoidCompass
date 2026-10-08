"""Colour variants a predicted species will show on a body (SrvSurvey's
bio criteria).

The species predictions come from EDMC-BioScan's requirements
(``bio_requirements``). The colour of an Odyssey species depends mostly on the
brightest parent star, sometimes on a surface material. SrvSurvey describes
both in its ``bio-criteria`` files, packaged in ``data/bio_criteria`` (GPL-3,
see the README there); this module reads them the way SrvSurvey's
``BioPredictor`` does, so Survey Operations can flag each colour the
commander's Codex still lacks.

Only Odyssey genera are coloured: a legacy species is its own Codex entry.
Without the folder, or without the parent star's scan, there are simply no
variants and the overlay keeps its species-level flags.
"""

from functools import lru_cache
import json
import os
import re
import threading

from voidcompass.core.paths import resource_path

MATS_THRESHOLD = 0.25

# SrvSurvey's Map.properties and Map.values.
_PROPERTIES = {
    "body": "PlanetClass", "gravity": "SurfaceGravity", "temp": "SurfaceTemperature",
    "pressure": "SurfacePressure", "atmosphere": "Atmosphere", "atmosType": "AtmosphereType",
    "atmosComp": "AtmosphereComposition", "matsComp": "Materials", "dist": "DistanceFromArrivalLS",
    "volcanism": "Volcanism", "mats": "Materials", "regions": "Region", "star": "Star",
    "parentStar": "ParentStar", "primaryStar": "PrimaryStar", "nebulae": "Nebulae",
    "guardian": "Guardian",
}
_VALUES = {
    "Icy": "Icy body", "Rocky": "Rocky body", "RockyIce": "Rocky ice ",
    "HMC": "High metal content ", "MRB": "Metal rich body",
}
# SrvSurvey's GalacticRegions.mapArmRegions: named groups of Codex region ids.
_REGION_GROUPS = {
    "Orion-CygnusArm": (7, 8, 16, 17, 18, 35),
    "OuterArm": (5, 6, 13, 14, 27, 29, 31, 41, 37),
    "Scutum-CentaurusArm": (9, 10, 11, 12, 24, 25, 26, 42, 28),
    "PerseusArm": (15, 30, 32, 33, 34, 36, 38, 39),
    "Sagittarius-CarinaArm": (9, 18, 19, 20, 21, 22, 23, 40),
    "CentreLeft": (1, 4),
    "CentreTop": (1, 3, 7),
    "CentreRight": (1, 2),
    "AmphoraBatch": (10, 19, 20, 21, 22),
    "AnemoneBatch": (7, 8, 9, 13, 14, 15, 16, 17, 18, 27, 31),
    "BarkMoundBatch": (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 25, 32, 33, 34),
    "BrainTreeBatch": (2, 9, 10, 17, 18, 35),
    "TubersBatch": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 18, 19),
    "ShardBatch": (14, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 34, 36, 37, 38, 39, 40, 41, 42),
}
# Only these decide a colour; the lenient pass tests nothing else.
_COLOUR_PROPERTIES = {"star", "mats", "primaryStar"}

_CLAUSE = re.compile(r"\s*(\w+)\s*([&!$]?)\[(.+)\]")
_COMPOSITION = re.compile(r"([\w\s]+)>=\s*([.\d]+)")


class Clause:
    __slots__ = ("raw", "prop", "op", "values", "low", "high", "compositions")

    def __init__(self, raw):
        match = _CLAUSE.match(raw)
        if not match:
            raise ValueError(f"Bad criteria: {raw}")
        self.raw = raw
        self.prop, marker, text = match.group(1), match.group(2), match.group(3)
        self.values = self.low = self.high = self.compositions = None
        if "~" in text:
            self.op = "range"
            low, high = (part.strip() for part in text.split("~", 1))
            self.low = float(low) if low else None
            self.high = float(high) if high else None
        elif ">=" in text:
            self.op = "composition"
            self.compositions = {}
            for part in text.split("|"):
                found = _COMPOSITION.search(part)
                if not found:
                    raise ValueError(f"Bad composition clause: {part}")
                self.compositions[found.group(1).strip()] = float(found.group(2))
        else:
            self.op = {"!": "not", "&": "all", "$": "all"}.get(marker, "is")
            values = [value.strip() for value in text.split(",") if value.strip()]
            self.values = [_VALUES.get(value, value) for value in values]
            if self.prop == "regions":
                regions = set()
                for value in values:
                    if value.isdigit():
                        regions.add(int(value))
                    else:
                        regions.update(_REGION_GROUPS.get(value, ()))
                self.values = regions


class Node:
    __slots__ = ("genus", "species", "variant", "query", "children", "use_common", "common")

    def __init__(self, raw):
        self.genus = raw.get("genus")
        self.species = raw.get("species")
        self.variant = raw.get("variant")
        self.query = [Clause(text.strip()) for text in raw.get("query") or ()
                      if str(text).strip() and not str(text).strip().startswith("#")]
        self.children = [Node(child) for child in raw.get("children") or ()]
        self.use_common = bool(raw.get("useCommonChildren"))
        common = raw.get("commonChildren")
        self.common = [Node(child) for child in common] if common is not None else None


def criteria_dir():
    return resource_path("data", "bio_criteria")


@lru_cache(maxsize=1)
def _criteria():
    folder = criteria_dir()
    try:
        names = sorted(name for name in os.listdir(folder) if name.endswith(".json"))
    except OSError:
        return ()
    trees = []
    for name in names:
        try:
            with open(os.path.join(folder, name), "r", encoding="utf-8") as handle:
                trees.append(Node(json.load(handle)))
        except (OSError, ValueError):
            continue
    return tuple(trees)


@lru_cache(maxsize=1)
def _variant_entries():
    """English Odyssey variant name, casefolded -> (species name, colour,
    Codex entry)."""
    path = resource_path("data", "codexRef.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            reference = json.load(handle)
    except (OSError, ValueError):
        return {}
    entries = {}
    for row in reference.values():
        if row.get("hud_category") != "Biology" or str(row.get("platform")).lower() != "odyssey":
            continue
        english = str(row.get("english_name") or "")
        species, separator, colour = english.partition(" - ")
        if separator and row.get("name"):
            entries[english.casefold()] = (species.strip(), colour.strip(), row["name"])
    return entries


def flatten_star_type(star_type):
    """SrvSurvey's Util.flattenStarType: every white dwarf is D, every
    Wolf-Rayet W, every carbon star C, and giants lose their suffix."""
    star_type = str(star_type or "")
    if not star_type:
        return ""
    if star_type[0] in "DWC":
        return star_type[0]
    if len(star_type) > 1 and star_type[1] == "_":
        return star_type[0]
    return star_type


# -- the body, as SrvSurvey's predictor sees it --------------------------------
def _parents(item):
    out = []
    for parent in item.get("parents") or ():
        if isinstance(parent, dict):
            for kind, body_id in parent.items():
                out.append((str(kind), body_id))
    return out


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parent_stars(item, by_id):
    """Stars this body orbits, directly or through barycentres."""
    stars = []
    for kind, body_id in _parents(item):
        if kind == "Star":
            star = by_id.get(body_id)
            if star and star.get("is_star") and star not in stars:
                stars.append(star)
        elif kind == "Null":
            for star in by_id.values():
                if not star.get("is_star") or star in stars:
                    continue
                if star.get("body_id") == body_id or _has_parent(star, body_id):
                    stars.append(star)
    return stars


def _has_parent(body, target):
    """The target is a direct parent, or only barycentres lie between."""
    for kind, body_id in _parents(body):
        if body_id == target:
            return True
        if kind != "Null":
            return False
    return False


def _parent_bodies(body, by_id):
    return [by_id[body_id] for _kind, body_id in _parents(body) if body_id in by_id]


def _distance_sq(body, target, by_id):
    """SrvSurvey's euclidianDistance: orbit radii summed, squared, up to the
    common parent."""
    if body is target:
        return 0.0
    total = (_number(body.get("semi_major_axis")) or 0.0) ** 2
    for parent in _parent_bodies(body, by_id):
        if target is not None and parent.get("body_id") == target.get("body_id"):
            return total
        total += (_number(parent.get("semi_major_axis")) or 0.0) ** 2
    return total


def _brightness(body, star, by_id):
    radius = _number(star.get("radius"))
    temperature = _number(star.get("surface_temp"))
    if not radius or not temperature:
        return 0.0
    star_parents = _parent_bodies(star, by_id)
    common = next((parent for parent in _parent_bodies(body, by_id)
                   if parent is star or parent in star_parents), None)
    distance = (_distance_sq(body, common, by_id) + _distance_sq(star, common, by_id)) ** 0.5
    if not distance:
        return 0.0
    return (radius * temperature ** 2 / distance) ** 2


def _stars_by_brightness(item, by_id):
    """Parent stars, brightest first (SrvSurvey's relative brightness); one
    whose brightness cannot be judged goes last."""
    stars = _parent_stars(item, by_id)
    if len(stars) < 2:
        return stars
    return [star for _value, star in sorted(((_brightness(item, star, by_id), star) for star in stars),
                                            key=lambda pair: pair[0], reverse=True)]


def _primary_star(by_id):
    stars = [row for row in by_id.values() if row.get("is_star")]
    for star in stars:
        if not _parents(star) or _number(star.get("distance_to_arrival")) == 0:
            return star
    return None


def body_properties(item, system_items, region_id=None):
    """SrvSurvey's bodyProps for one scanned body, or None when its parent
    star has not been scanned (no colour can be judged)."""
    if not item or item.get("is_star") or not item.get("planet_class"):
        return None
    by_id = {row.get("body_id"): row for row in system_items or () if row.get("body_id") is not None}
    by_id.setdefault(item.get("body_id"), item)
    stars = [star for star in _stars_by_brightness(item, by_id) if star.get("star_type")]
    if not stars:
        return None
    star = stars[0]
    primary = _primary_star(by_id)
    composition = {}
    for row in item.get("atmosphere_composition") or ():
        if isinstance(row, dict) and row.get("Name"):
            composition[str(row["Name"])] = _number(row.get("Percent")) or 0.0
    if len(composition) == 1:
        composition = {key: 100.0 for key in composition}
    materials = {}
    for row in item.get("materials") or ():
        if isinstance(row, dict):
            name = str(row.get("symbol") or row.get("name") or "").casefold()
            if name:
                materials[name] = _number(row.get("percent")) or 0.0
    gravity = _number(item.get("surface_gravity"))
    pressure = _number(item.get("surface_pressure"))
    atmosphere = str(item.get("atmosphere") or "").replace(" atmosphere", "")
    return {
        "PlanetClass": str(item.get("planet_class") or ""),
        # SrvSurvey's criteria were measured against m/s² / 10, not g.
        "SurfaceGravity": gravity / 10.0 if gravity is not None else None,
        "SurfaceTemperature": _number(item.get("surface_temp")),
        "SurfacePressure": pressure / 100000.0 if pressure is not None else None,
        "Atmosphere": atmosphere,
        "AtmosphereType": str(item.get("atmosphere_type") or "None"),
        "AtmosphereComposition": composition,
        "DistanceFromArrivalLS": _number(item.get("distance_to_arrival")),
        "Volcanism": str(item.get("volcanism") or "") or "None",
        "Materials": materials,
        "Region": region_id,
        "Star": [flatten_star_type(star.get("star_type"))],
        # Every parent star, for colours the brightest one cannot give.
        "AllStars": list(dict.fromkeys(flatten_star_type(row.get("star_type")) for row in stars)),
        "PrimaryStar": flatten_star_type(primary.get("star_type")) if primary else None,
        # Not known here; clauses on them are not held against a body.
        "Nebulae": None,
        "Guardian": None,
    }


# -- SrvSurvey's BioPredictor.testQuery ----------------------------------------
def _passes(clause, props):
    value = props.get(_PROPERTIES.get(clause.prop, clause.prop))
    if value is None:
        return True  # unknown: do not rule a colour out on it
    if clause.op == "range":
        number = _number(value)
        if number is None:
            return True
        if clause.low is not None and number < clause.low:
            return False
        return not (clause.high is not None and number > clause.high)
    if clause.op == "composition":
        if not isinstance(value, dict):
            return True
        return any(value.get(name, -1) >= amount for name, amount in clause.compositions.items())
    if clause.prop == "regions":
        try:
            region = int(value)
        except (TypeError, ValueError):
            return True
        inside = region in clause.values
        return not inside if clause.op == "not" else inside
    wanted = [str(text).casefold() for text in clause.values]
    if clause.op == "is":
        if clause.prop == "mats" and isinstance(value, dict):
            return any(value.get(name, 0) > MATS_THRESHOLD for name in wanted)
        if isinstance(value, dict):
            value = list(value)
        if isinstance(value, (list, tuple)):
            return any(str(item).casefold() in wanted for item in value)
        text = str(value).casefold()
        if clause.prop == "body":
            return any(text.startswith(option) for option in wanted)
        if clause.prop == "volcanism":
            if wanted and wanted[0] == "any":
                return text != "none"
            return any(option in text for option in wanted)
        return text in wanted
    values = list(value) if isinstance(value, (dict, list, tuple)) else [value]
    values = {str(item).casefold() for item in values}
    if clause.op == "all":
        return all(option in values for option in wanted)
    return not any(option in values for option in wanted)  # not


def _walk(node, props, found, lenient, genus=None, species=None, variant=None, common=None):
    common = node.common if node.common is not None else common
    genus = node.genus if node.genus is not None else genus
    species = node.species if node.species is not None else species
    variant = node.variant if node.variant is not None else variant
    clauses = [clause for clause in node.query if not lenient or clause.prop in _COLOUR_PROPERTIES]
    if not all(_passes(clause, props) for clause in clauses):
        return
    if genus and species and variant:
        found.add(f"{genus} {species} - {variant}")
    for child in (common if node.use_common else node.children) or ():
        _walk(child, props, found, lenient, genus, species, variant, common)


def predict(props, lenient=False):
    """Every "Genus Species - Colour" the criteria allow on this body."""
    found = set()
    if props:
        for tree in _criteria():
            _walk(tree, props, found, lenient)
    return found


def _group(names):
    entries = _variant_entries()
    grouped = {}
    for name in names:
        entry = entries.get(name.casefold())
        if entry:
            species, colour, key = entry
            rows = grouped.setdefault(species.casefold(), [])
            if all(row["key"] != key for row in rows):
                rows.append({"colour": colour, "key": key})
    for rows in grouped.values():
        rows.sort(key=lambda row: row["colour"])
    return grouped


_CACHE = {}
_CACHE_LOCK = threading.Lock()


def body_variants(item, system_items, region_id=None):
    """``{species name casefolded: [{'colour', 'key', 'predicted'}]}`` for one
    body.

    ``predicted`` marks species the criteria themselves expect on this body
    (SrvSurvey's own prediction). For the others, which BioScan's rules may
    still predict, the colours follow from the star and materials alone: the
    brightest parent star first, then any parent star.
    """
    props = body_properties(item, system_items, region_id)
    if not props or not _criteria():
        return {}
    signature = json.dumps(props, sort_keys=True, default=str)
    with _CACHE_LOCK:
        cached = _CACHE.get(signature)
    if cached is not None:
        return cached
    strict = _group(predict(props))
    lenient = _group(predict(props, lenient=True))
    any_star = _group(predict({**props, "Star": props.get("AllStars") or props["Star"]}, lenient=True))
    result = {}
    for species in set(any_star) | set(lenient) | set(strict):
        rows = strict.get(species) or lenient.get(species) or any_star.get(species)
        result[species] = [{**row, "predicted": species in strict} for row in rows]
    with _CACHE_LOCK:
        if len(_CACHE) > 256:
            _CACHE.clear()
        _CACHE[signature] = result
    return result
