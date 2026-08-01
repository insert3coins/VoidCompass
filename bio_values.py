"""Exobiology reference values and lightweight genus prediction helpers."""

import bio_reference
import bio_requirements

GENUS_COLONY_M = {
    "Aleoida": 150, "Bacterium": 500, "Cactoida": 300, "Clypeus": 150,
    "Concha": 150, "Electricae": 1000, "Fonticulua": 500, "Frutexa": 150,
    "Fumerola": 100, "Fungoida": 300, "Osseus": 800, "Recepta": 150,
    "Stratum": 500, "Tubus": 800, "Tussock": 200,
    "Anemone": 100, "Amphora Plant": 100, "Bark Mounds": 100,
    "Brain Tree": 100, "Sinuous Tubers": 100, "Crystalline Shards": 100,
}

# Values are generated from the same pinned EDMC-BioScan catalogue as the
# prediction rules.  Keeping a second hand-maintained list here allowed older
# SrvSurvey/Codex values to silently override the 5.3.3 data.
SPECIES_VALUES = {}
SPECIES_FAMILIES = {}
_CODEX_SPECIES_VALUES = {}
for genus_key, species_rows in bio_requirements.CATALOG.items():
    family = bio_requirements.GENUS_FAMILIES.get(genus_key)
    for species_key, row in species_rows.items():
        name = str(row.get("name") or "").strip()
        value = int(row.get("value") or 0)
        if not name or not value:
            continue
        SPECIES_VALUES[name] = value
        SPECIES_FAMILIES[name] = family or name.split(" ", 1)[0]
        _CODEX_SPECIES_VALUES[str(species_key).casefold()] = value

# EDMC-BioScan's species.py adds three legacy/special entries outside its
# rulesets package.  Retain the plural Bark Mounds alias used by Elite's Codex
# reference and older VoidCompass scan caches.
_SUPPLEMENTAL_SPECIES = {
    "Bark Mound": (1471900, "Bark Mounds"),
    "Bark Mounds": (1471900, "Bark Mounds"),
    "Amphora Plant": (1628800, "Amphora Plant"),
    "Radicoida Unicus": (119037, "Radicoida"),
}
for name, (value, family) in _SUPPLEMENTAL_SPECIES.items():
    SPECIES_VALUES[name] = value
    SPECIES_FAMILIES[name] = family

_SPECIES_VALUE_INDEX = {
    str(name).casefold(): value for name, value in SPECIES_VALUES.items()
}

GENUS_VALUE_RANGE = {}
for species, value in SPECIES_VALUES.items():
    genus = SPECIES_FAMILIES.get(species) or species.split(" ", 1)[0]
    lo, hi = GENUS_VALUE_RANGE.get(genus, (value, value))
    GENUS_VALUE_RANGE[genus] = (min(lo, value), max(hi, value))

ROCKY = {"Rocky body", "High metal content body"}
ICY = {"Icy body", "Rocky ice body"}
PREDICTION_RULES = {
    "Bacterium": (None, (20, 400), 0.61, None, False),
    "Tussock": ({"carbon dioxide", "ammonia", "argon", "methane", "sulphur dioxide", "water", "nitrogen"}, (145, 197), 0.28, ROCKY, False),
    "Stratum": ({"carbon dioxide", "ammonia", "sulphur dioxide", "water", "oxygen"}, (165, 400), 0.58, ROCKY, False),
    "Cactoida": ({"carbon dioxide", "ammonia", "water"}, (160, 197), 0.28, ROCKY, False),
    "Clypeus": ({"carbon dioxide", "water"}, (190, 455), 0.28, ROCKY, False),
    "Concha": ({"carbon dioxide", "ammonia", "water", "nitrogen"}, (160, 200), 0.28, ROCKY, False),
    "Frutexa": ({"carbon dioxide", "ammonia", "sulphur dioxide", "water", "nitrogen"}, (146, 200), 0.28, ROCKY, False),
    "Fonticulua": ({"argon", "neon", "methane", "nitrogen", "oxygen", "carbon dioxide"}, (50, 150), 0.28, ICY, False),
    "Fungoida": ({"carbon dioxide", "ammonia", "argon", "methane"}, (160, 210), 0.28, ROCKY | ICY, False),
    "Osseus": ({"carbon dioxide", "ammonia", "argon", "methane", "nitrogen"}, (160, 200), 0.28, ROCKY | ICY, False),
    "Aleoida": ({"carbon dioxide", "ammonia"}, (152, 197), 0.28, ROCKY, False),
    "Electricae": ({"argon", "neon", "helium"}, (50, 150), 0.28, {"Icy body"}, False),
    "Recepta": ({"sulphur dioxide", "carbon dioxide"}, (130, 300), 0.28, ROCKY | ICY, False),
    "Tubus": ({"carbon dioxide", "ammonia", "argon", "methane", "nitrogen"}, (160, 197), 0.16, {"Rocky body"}, False),
    "Fumerola": ({"carbon dioxide", "ammonia", "argon", "methane", "sulphur dioxide", "water"}, (50, 450), 0.28, None, True),
}


def species_value(species_localised):
    if not species_localised:
        return None
    key = str(species_localised).strip().casefold()
    # The pinned EDMC-BioScan values are authoritative for every species it
    # knows.  codexRef remains a compatibility fallback for entries outside
    # that catalogue, rather than overriding the newer values.
    value = _SPECIES_VALUE_INDEX.get(key)
    if value is None:
        value = _CODEX_SPECIES_VALUES.get(key)
    if value is not None:
        return value
    reference = bio_reference.species_info(species_localised)
    if reference and reference.get("value") is not None:
        return reference["value"]
    return None


def genus_info(genus_localised):
    lo, hi = GENUS_VALUE_RANGE.get(genus_localised, (None, None))
    reference = bio_reference.genus_info(genus_localised)
    if reference and genus_localised not in GENUS_VALUE_RANGE:
        lo = reference.get("min_value") if reference.get("min_value") is not None else lo
        hi = reference.get("max_value") if reference.get("max_value") is not None else hi
    return {
        "name": genus_localised,
        "min_value": lo,
        "max_value": hi,
        "colony_m": GENUS_COLONY_M.get(genus_localised),
    }


def predict_genera(planet_class, atmosphere, temp_k, gravity_g, volcanism,
                   pressure_atm=None, region_id=None, coords=None):
    """Predict genera present on a body, newest data first.

    The published species requirements cover families that live on airless
    bodies, so this no longer refuses to answer unless the atmosphere is thin.
    Each genus reports the species behind it and whether every published
    requirement could actually be tested. ``PREDICTION_RULES`` remains as a
    fallback for bodies the species data does not describe.
    """
    # Fall back only when the scan is too incomplete to judge against the
    # published requirements. A body that was tested and matched nothing is a
    # real answer, and the coarser legacy rules must not overrule it.
    if not planet_class or (temp_k is None and gravity_g is None):
        return _predict_genera_legacy(planet_class, atmosphere, temp_k, gravity_g, volcanism)
    species = bio_requirements.candidate_species(
        planet_class, atmosphere, temp_k, gravity_g, volcanism, pressure_atm,
        region_id, coords,
    )
    if species:
        grouped = {}
        for row in species:
            # The catalogue's own genus identifier is authoritative: species
            # names alone cannot be split reliably, because the non-flora
            # families are named colour-first.
            genus = bio_requirements.GENUS_FAMILIES.get(row.get("genus_key")) or \
                bio_requirements.family_for_species(row.get("name"))
            if not genus:
                continue
            entry = grouped.get(genus)
            if entry is None:
                entry = genus_info(genus)
                entry["species"] = []
                entry["confirmed"] = False
                grouped[genus] = entry
            entry["species"].append({
                "name": row.get("name"), "value": row.get("value"),
                "unchecked": row.get("unchecked"), "confirmed": row.get("confirmed"),
            })
            entry["confirmed"] = entry["confirmed"] or bool(row.get("confirmed"))
        for entry in grouped.values():
            # genus_info() spans every species the genus can contain. Now that
            # the fitting species are known, narrow the range to those, so the
            # figure cannot contradict the species listed beneath it.
            values = [row["value"] for row in entry["species"] if row.get("value")]
            if values:
                entry["min_value"] = min(values)
                entry["max_value"] = max(values)
        if grouped:
            return sorted(
                grouped.values(),
                key=lambda row: (not row.get("confirmed"), row.get("name") or ""),
            )
    return []


def _predict_genera_legacy(planet_class, atmosphere, temp_k, gravity_g, volcanism):
    atmo = (atmosphere or "").lower()
    if "thin" not in atmo or temp_k is None or gravity_g is None:
        return []
    has_volcanism = bool(volcanism)
    out = []
    for genus, (keywords, (t_lo, t_hi), g_max, classes, needs_volcanism) in PREDICTION_RULES.items():
        if keywords is not None and not any(k in atmo for k in keywords):
            continue
        if not (t_lo <= float(temp_k) <= t_hi) or float(gravity_g) > g_max:
            continue
        if classes is not None and planet_class not in classes:
            continue
        if needs_volcanism and not has_volcanism:
            continue
        out.append(genus_info(genus))
    return out
