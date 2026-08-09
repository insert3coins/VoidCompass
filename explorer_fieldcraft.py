"""Pure exploration fieldcraft helpers shared by UI, HUD, and tests."""

from __future__ import annotations

from datetime import datetime, timezone
import math

from flight_callouts import is_scoopable, route_ahead


WHITE_DWARF_CLASSES = {
    "D", "DA", "DAB", "DAO", "DAZ", "DAV", "DB", "DBZ", "DBV",
    "DO", "DOV", "DQ", "DC", "DCV", "DX",
}
HIGH_VALUE_WORLDS = {"Earthlike body", "Water world", "Ammonia world"}

# Practical search guidance, not spawn guarantees. The published species
# rules remain authoritative for atmosphere/gravity/temperature suitability;
# these short terrain cues merely help a commander decide where to look after
# a body and genus have already been identified or predicted.
BIO_TERRAIN_HINTS = {
    "Aleoida": "open flats and low rolling terrain",
    "Bacterium": "flat ground; use the ship or SRV composition scanner",
    "Cactoida": "rocky plains and broken lowlands",
    "Clypeus": "rough high ground and mountain shelves",
    "Concha": "rocky slopes, gullies and foothills",
    "Electricae": "open icy plains away from steep relief",
    "Fonticulua": "low icy flats and shallow depressions",
    "Frutexa": "rocky slopes and broken highlands",
    "Fumerola": "volcanic sites, vents and fumarole fields",
    "Fungoida": "mountainous ground, ravines and steep slopes",
    "Osseus": "rock-strewn plains and rough lowlands",
    "Recepta": "uneven rocky terrain and sheltered depressions",
    "Stratum": "broad flat plains; avoid strongly broken terrain",
    "Tubus": "rough highlands, ridges and mountainous terrain",
    "Tussock": "open plains and gently rolling ground",
    "Anemone": "geological or notable-stellar surface sites",
    "Amphora Plant": "notable-stellar surface sites",
    "Bark Mounds": "wooded-looking mound fields on suitable bodies",
    "Brain Tree": "Guardian-influenced surface regions",
    "Crystalline Shards": "distant cold volcanic surface sites",
    "Sinuous Tubers": "notable-stellar surface sites",
}


def _number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _body_name(item):
    return str((item or {}).get("full_name") or (item or {}).get("name") or "Unknown body")


def _genus_names(item):
    names = []
    for row in (item or {}).get("genuses") or ():
        if isinstance(row, dict):
            name = (
                row.get("Genus_Localised") or row.get("Name_Localised")
                or row.get("Genus") or row.get("Name")
            )
        else:
            name = row
        name = str(name or "").strip().strip("$;")
        if name and name not in names:
            names.append(name)
    for scan in ((item or {}).get("organic_scans") or {}).values():
        if not isinstance(scan, dict):
            continue
        name = str(scan.get("genus") or "").strip().strip("$;")
        if not name:
            species = str(scan.get("species") or "").strip()
            name = species.split(" ", 1)[0] if species else ""
        if name and name not in names:
            names.append(name)
    if names:
        return names
    for row in (item or {}).get("predicted_genuses") or ():
        name = row.get("name") if isinstance(row, dict) else row
        name = str(name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _organic_complete(item):
    item = item if isinstance(item, dict) else {}
    verified = sum(
        1 for row in (item.get("organic_scans") or {}).values()
        if isinstance(row, dict) and row.get("is_complete")
    )
    return max(_integer(item.get("organic_complete_count")), verified)


def _bio_value_range(item, genera):
    import bio_values

    completed = [
        _integer(row.get("species_value"))
        for row in ((item or {}).get("organic_scans") or {}).values()
        if isinstance(row, dict) and row.get("is_complete") and row.get("species_value")
    ]
    if completed:
        value = sum(completed)
        return value, value
    ranges = []
    for name in genera:
        info = bio_values.genus_info(name)
        if info.get("min_value") and info.get("max_value"):
            ranges.append((int(info["min_value"]), int(info["max_value"])))
    if not ranges:
        return None, None
    return min(row[0] for row in ranges), max(row[1] for row in ranges)


def bio_field_assistant(bodies, sampling=None, focused_body=""):
    """Choose one useful, evidence-backed surface biology action."""
    import bio_values

    sampling = sampling if isinstance(sampling, dict) else {}
    if sampling.get("species") or sampling.get("genus"):
        species = str(sampling.get("species") or sampling.get("genus") or "Biological sample")
        genus = str(sampling.get("genus") or species.split(" ", 1)[0])
        progress = max(1, min(3, _integer(sampling.get("progress") or sampling.get("sample_idx"), 1)))
        spacing = _integer(sampling.get("colony_m")) or bio_values.GENUS_COLONY_M.get(genus)
        minimum = _number(sampling.get("min_distance_m"))
        clear = bool(sampling.get("clear"))
        value = bio_values.species_value(species)
        if clear:
            action = "Clear to take the next sample"
        elif spacing and minimum is not None:
            action = f"Move {max(0, round(spacing - minimum)):,} m farther from the last sample"
        elif spacing:
            action = f"Move at least {int(spacing):,} m from the last sample"
        else:
            action = "Move to a genetically distinct colony"
        return {
            "state": "ACTIVE", "body": sampling.get("body") or focused_body,
            "species": species, "genus": genus, "progress": progress,
            "spacing_m": spacing, "distance_m": minimum, "clear": clear,
            "terrain": BIO_TERRAIN_HINTS.get(genus, "use the composition scanner and local terrain contrast"),
            "atmosphere": "", "min_value_cr": value, "max_value_cr": value,
            "headline": f"ACTIVE SAMPLE · {species} · {progress}/3",
            "detail": action,
        }

    candidates = []
    for item in bodies or ():
        if not isinstance(item, dict):
            continue
        total = max(0, _integer(item.get("bio_count")))
        complete = _organic_complete(item)
        if total <= complete:
            continue
        genera = _genus_names(item)
        low, high = _bio_value_range(item, genera)
        score = (high or 0) / 1_000_000 + (total - complete) * 8
        score += 14 if item.get("first_footfall") else 0
        score += 5 if item.get("dss_complete") else 0
        if focused_body and _body_name(item).casefold() == str(focused_body).casefold():
            score += 10
        candidates.append((score, item, genera, total, complete, low, high))
    if not candidates:
        return {
            "state": "CLEAR", "headline": "BIO FIELD ASSISTANT · NO PENDING TARGET",
            "detail": "No unfinished biological analysis is currently supported by journal evidence.",
        }
    _score, item, genera, total, complete, low, high = max(candidates, key=lambda row: row[0])
    genus = genera[0] if genera else "Unresolved genus"
    spacing = bio_values.GENUS_COLONY_M.get(genus)
    atmosphere = str(item.get("atmosphere_type") or item.get("atmosphere") or "").replace("Thin ", "")
    remaining = max(1, total - complete)
    return {
        "state": "TARGET", "body": _body_name(item), "body_id": item.get("body_id"),
        "species": None, "genus": genus, "genera": genera,
        "progress": 0, "remaining": remaining, "spacing_m": spacing,
        "terrain": BIO_TERRAIN_HINTS.get(genus, "use the composition scanner and local terrain contrast"),
        "atmosphere": atmosphere, "min_value_cr": low, "max_value_cr": high,
        "first_footfall": bool(item.get("first_footfall")),
        "headline": f"NEXT BIO TARGET · {_body_name(item)} · {remaining} remaining",
        "detail": " · ".join(filter(None, (
            ", ".join(genera[:3]) if genera else "Genus unresolved until DSS",
            f"spacing {int(spacing):,} m" if spacing else None,
            BIO_TERRAIN_HINTS.get(genus),
            atmosphere or None,
            "first footfall available" if item.get("first_footfall") else None,
        ))),
    }


def discovery_significance(item):
    """Rank a measured body without presenting the score as a game reward."""
    item = item if isinstance(item, dict) else {}
    body_class = str(item.get("planet_class") or item.get("class") or "")
    star_class = str(item.get("star_type") or "").upper()
    value = _integer(item.get("dss_reward") or item.get("reward"))
    bio = max(_integer(item.get("bio_count")), _organic_complete(item))
    score = 0
    reasons = []
    if body_class in HIGH_VALUE_WORLDS:
        points = {"Earthlike body": 38, "Ammonia world": 32, "Water world": 26}[body_class]
        score += points
        reasons.append(body_class)
    if item.get("terraformable"):
        score += 18
        reasons.append("terraformable")
    if value >= 1_000_000:
        score += 14
        reasons.append("high survey value")
    elif value >= 250_000:
        score += 8
        reasons.append("valuable survey target")
    if item.get("was_discovered") is False:
        score += 16
        reasons.append("first discovery available")
    if item.get("first_footfall"):
        score += 12
        reasons.append("first footfall available")
    if bio:
        score += min(25, 5 + bio * 4)
        reasons.append(f"{bio} biological signal{'s' if bio != 1 else ''}")
    geo = _integer(item.get("geo_count"))
    if geo:
        score += min(8, 2 + geo)
        reasons.append(f"{geo} geological signal{'s' if geo != 1 else ''}")
    if item.get("rings"):
        score += 4
        reasons.append("ring system")
    if star_class.startswith(("N", "D", "H", "BLACK", "SUPERMASSIVE")):
        score += 25
        reasons.append("compact or unusual stellar object")
    score = min(100, score)
    if score >= 75:
        tier = "EXCEPTIONAL"
    elif score >= 50:
        tier = "RARE"
    elif score >= 25:
        tier = "NOTABLE"
    else:
        tier = "ROUTINE"
    return {"score": score, "tier": tier, "reasons": reasons or ["ordinary measured characteristics"]}


def system_significance(bodies, codex_rows=()):
    rows = []
    for item in bodies or ():
        if not isinstance(item, dict):
            continue
        result = discovery_significance(item)
        rows.append({"body": _body_name(item), "body_id": item.get("body_id"), **result})
    rows.sort(key=lambda row: (-row["score"], row["body"]))
    score = rows[0]["score"] if rows else 0
    diversity = len({name for item in bodies or () for name in _genus_names(item)})
    if diversity >= 5:
        score = min(100, score + min(12, diversity))
    new_codex = sum(1 for row in codex_rows or () if isinstance(row, dict) and row.get("new"))
    if new_codex:
        score = min(100, score + min(12, new_codex * 4))
    tier = "EXCEPTIONAL" if score >= 75 else "RARE" if score >= 50 else "NOTABLE" if score >= 25 else "ROUTINE"
    return {
        "score": score, "tier": tier, "bodies": rows,
        "top": rows[0] if rows else None, "bio_diversity": diversity,
        "new_codex": new_codex,
    }


def return_to_base_plan(*, current_system="", target_system="", distance_ly=None,
                        exact_jumps=None, jump_range_ly=None, fuel_percent=None,
                        hull_percent=None, unsold_min_cr=0, unsold_max_cr=0,
                        route_forecast=None, known_services=()):
    """Build a conservative return estimate from explicit route/ship facts."""
    distance = _number(distance_ly)
    jump_range = _number(jump_range_ly)
    jumps = -1 if exact_jumps is None or exact_jumps == "" else _integer(exact_jumps, -1)
    source = "game route"
    if jumps < 0:
        jumps = math.ceil(distance / jump_range) if distance is not None and jump_range and jump_range > 0 else None
        source = "straight-line estimate" if jumps is not None else "unavailable"
    eta = max(1, math.ceil(jumps * 55 / 60)) if jumps is not None and jumps > 0 else 0
    issues = []
    if not target_system:
        issues.append("Set an expedition return system or plot a game route")
    if fuel_percent is not None and fuel_percent < 25:
        issues.append(f"Fuel is {round(fuel_percent)}%")
    if hull_percent is not None and hull_percent < 70:
        issues.append(f"Hull is {round(hull_percent)}%")
    forecast = route_forecast if isinstance(route_forecast, dict) else {}
    if forecast.get("level") in {"warn", "alert"}:
        issues.append(str(forecast.get("status") or "Route caution"))
    service_names = {str(value).casefold() for value in known_services or ()}
    has_cartographics = any("cartographic" in value for value in service_names)
    has_vista = any("vista" in value for value in service_names)
    if has_cartographics and has_vista:
        service_text = "Cartographics and Vista Genomics verified at the current destination"
    elif has_cartographics:
        service_text = "Cartographics verified; Vista Genomics not confirmed"
    elif has_vista:
        service_text = "Vista Genomics verified; Cartographics not confirmed"
    else:
        service_text = "Data-sale services are not verified from retained journal evidence"
    if not target_system:
        state = "SET RETURN"
    elif issues:
        state = "CAUTION"
    else:
        state = "READY"
    return {
        "state": state, "current_system": current_system, "target_system": target_system,
        "distance_ly": distance, "jumps": jumps, "jump_source": source,
        "eta_minutes": eta, "fuel_percent": fuel_percent, "hull_percent": hull_percent,
        "unsold_min_cr": _integer(unsold_min_cr), "unsold_max_cr": _integer(unsold_max_cr),
        "issues": issues, "service_text": service_text,
        "headline": (
            f"{state} · {jumps} jump{'s' if jumps != 1 else ''} · ~{eta} min"
            if target_system and jumps is not None else
            f"{state} · {target_system or 'no return destination'}"
        ),
    }


def route_endurance_monitor(route_forecast=None, loadout=None, raw_materials=None,
                            hull_percent=None, srv_available=None):
    """Summarise verified expedition consumables and explicitly unknown facts."""
    import companion_features

    loadout_known = isinstance(loadout, dict) and bool(loadout)
    loadout = loadout if isinstance(loadout, dict) else {}
    modules = [row for row in loadout.get("Modules") or () if isinstance(row, dict)]
    module_text = [
        " ".join(str(row.get(key) or "") for key in ("Item", "Item_Localised", "Slot")).casefold()
        for row in modules
    ]

    def matching(*needles):
        return [row for row, text in zip(modules, module_text) if any(needle in text for needle in needles)]

    def health(row):
        value = _number((row or {}).get("Health"))
        if value is None:
            return None
        return round(value * 100 if value <= 1.0 else value, 1)

    fsd_rows = matching("frameshiftdrive", "frame shift drive")
    fsd_health = min((value for value in (health(row) for row in fsd_rows) if value is not None), default=None)
    afmu_rows = matching("modulerepairer", "field maintenance")
    sink_rows = matching("heatsinklauncher", "heat sink")
    sinks = sum(
        _integer(row.get("AmmoInClip")) + _integer(row.get("AmmoInHopper"))
        for row in sink_rows
    ) if any("AmmoInClip" in row or "AmmoInHopper" in row for row in sink_rows) else None
    afmu_ammo = sum(
        _integer(row.get("AmmoInClip")) + _integer(row.get("AmmoInHopper"))
        for row in afmu_rows
    ) if any("AmmoInClip" in row or "AmmoInHopper" in row for row in afmu_rows) else None
    materials_known = isinstance(raw_materials, dict) and bool(raw_materials)
    raw_counts = {
        str(key).casefold(): _integer(value.get("count") if isinstance(value, dict) else value)
        for key, value in (raw_materials or {}).items()
    }
    injections = companion_features.fsd_injections(raw_counts) if materials_known else None
    forecast = route_forecast if isinstance(route_forecast, dict) else {}
    neutron = _integer(forecast.get("neutron_count"))
    projected_fsd = max(0.0, fsd_health - neutron) if fsd_health is not None else None
    issues = []
    if fsd_health is not None and projected_fsd < 80:
        issues.append(f"Projected FSD integrity {projected_fsd:.0f}% after {neutron} neutron boost(s)")
    if hull_percent is not None and hull_percent < 70:
        issues.append(f"Hull integrity {hull_percent:.0f}%")
    if forecast.get("level") in {"warn", "alert"}:
        issues.append(str(forecast.get("status") or "Route fuel risk"))
    return {
        "state": "CAUTION" if issues else "READY",
        "hull_percent": hull_percent, "fsd_health_percent": fsd_health,
        "projected_fsd_percent": projected_fsd,
        "afmu_installed": bool(afmu_rows) if loadout_known else None,
        "afmu_ammo": afmu_ammo,
        "heat_sink_installed": bool(sink_rows) if loadout_known else None,
        "heat_sinks": sinks,
        "srv_available": srv_available,
        "injections": injections, "neutron_boosts": neutron,
        "route": forecast, "issues": issues,
        "headline": "CAUTION · " + issues[0] if issues else "READY · exploration reserves monitored",
    }


def sector_grid(route_points, center, radius_ly=500.0, cell_size_ly=100.0):
    """Classify a bounded X/Z expedition grid from retained visit evidence."""
    if not isinstance(center, (list, tuple)) or len(center) < 3:
        return {"active": False, "cells": [], "summary": "Set a sector centre first"}
    try:
        cx, cy, cz = (float(center[index]) for index in range(3))
        radius = max(25.0, min(5000.0, float(radius_ly)))
        cell = max(10.0, min(radius, float(cell_size_ly)))
    except (TypeError, ValueError):
        return {"active": False, "cells": [], "summary": "Sector dimensions are invalid"}
    dimension = max(1, min(21, int(math.ceil(radius * 2 / cell))))
    cell = radius * 2 / dimension
    buckets = {}
    for row in route_points or ():
        if not isinstance(row, dict):
            continue
        pos = row.get("pos")
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            continue
        try:
            x, _y, z = (float(pos[index]) for index in range(3))
        except (TypeError, ValueError):
            continue
        if not (cx - radius <= x < cx + radius and cz - radius <= z < cz + radius):
            continue
        ix = min(dimension - 1, max(0, int((x - (cx - radius)) / cell)))
        iz = min(dimension - 1, max(0, int((z - (cz - radius)) / cell)))
        bucket = buckets.setdefault((ix, iz), {})
        system = str(row.get("system") or f"{x:.2f},{z:.2f}")
        existing = bucket.get(system)
        complete = bool(row.get("fss_complete"))
        bucket[system] = complete or bool(existing)
    cells = []
    counts = {"surveyed": 0, "incomplete": 0, "untouched": 0}
    for iz in range(dimension):
        for ix in range(dimension):
            systems = buckets.get((ix, iz), {})
            if not systems:
                status = "untouched"
            elif all(systems.values()):
                status = "surveyed"
            else:
                status = "incomplete"
            counts[status] += 1
            x = cx - radius + (ix + 0.5) * cell
            z = cz - radius + (iz + 0.5) * cell
            cells.append({
                "id": f"{ix + 1:02d}-{iz + 1:02d}", "x_index": ix, "z_index": iz,
                "position": [round(x, 3), cy, round(z, 3)], "status": status,
                "visited_systems": len(systems),
                "surveyed_systems": sum(1 for value in systems.values() if value),
            })
    total = len(cells)
    completed = counts["surveyed"]
    return {
        "active": True, "center": [cx, cy, cz], "radius_ly": radius,
        "cell_size_ly": round(cell, 2), "dimension": dimension, "cells": cells,
        "counts": counts, "completion_percent": round(completed * 100 / total) if total else 0,
        "summary": (
            f"{dimension}×{dimension} cells · {counts['surveyed']} surveyed · "
            f"{counts['incomplete']} incomplete · {counts['untouched']} unvisited"
        ),
    }


def surface_trail_snapshot(points, current=None, ship=None, radius_m=None, sample_pins=()):
    """Return bounded trail distance, return vector and local plot points."""
    points = [row for row in (points or ()) if isinstance(row, dict)][-600:]
    radius = _number(radius_m)

    def distance(left, right):
        if not left or not right or not radius:
            return None
        from companion_features import surface_distance_m
        return surface_distance_m(left.get("lat"), left.get("lon"), right.get("lat"), right.get("lon"), radius)

    travelled = 0.0
    for left, right in zip(points, points[1:]):
        segment = distance(left, right)
        if segment is not None:
            travelled += segment
    return_distance = distance(current, ship)
    bearing = None
    if current and ship:
        try:
            lat1, lat2 = math.radians(float(current["lat"])), math.radians(float(ship["lat"]))
            delta_lon = math.radians(float(ship["lon"]) - float(current["lon"]))
            y = math.sin(delta_lon) * math.cos(lat2)
            x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
            bearing = math.degrees(math.atan2(y, x)) % 360
        except (KeyError, TypeError, ValueError):
            bearing = None
    origin = ship or (points[0] if points else current)
    plot = []
    if origin and radius:
        lat0 = math.radians(float(origin.get("lat") or 0))
        for row in points:
            north = math.radians(float(row.get("lat") or 0) - float(origin.get("lat") or 0)) * radius
            east = math.radians(float(row.get("lon") or 0) - float(origin.get("lon") or 0)) * radius * math.cos(lat0)
            plot.append({"east_m": east, "north_m": north, **row})
    return {
        "points": points, "plot": plot, "sample_pins": list(sample_pins or ())[-60:],
        "ship": ship, "current": current, "travelled_m": round(travelled, 1),
        "return_distance_m": round(return_distance, 1) if return_distance is not None else None,
        "return_bearing_deg": round(bearing, 1) if bearing is not None else None,
    }


def route_safety_forecast(entries, current_system="", current_star_class="",
                          fuel_main=None, fuel_capacity=None, fuel_samples=()):
    """Summarise the verified hazards and refuelling horizon of NavRoute."""
    ahead = route_ahead(entries, current_system, current_star_class)
    pending = ahead[1:] if ahead else []
    if not pending:
        return {
            "status": "IDLE", "level": "muted", "headline": "NO ACTIVE GAME ROUTE",
            "detail": "Plot a route in Elite to calculate scoop and stellar-hazard intelligence.",
            "jumps": 0, "eta_minutes": 0, "badge": None,
        }

    known = [row for row in pending if row.get("scoopable") is not None]
    scoopable = [row for row in pending if row.get("scoopable") is True]
    unknown = len(pending) - len(known)
    neutron = []
    white_dwarfs = []
    for row in pending:
        star_class = str(row.get("star_class") or "").strip().upper()
        if star_class in {"N", "NS"}:
            neutron.append(row)
        elif star_class in WHITE_DWARF_CLASSES:
            white_dwarfs.append(row)

    next_scoop = next(
        (index + 1 for index, row in enumerate(pending) if row.get("scoopable") is True),
        None,
    )
    longest_dry = 0
    dry_now = 0
    dry_start = None
    dry_span = None
    for index, row in enumerate(pending):
        if row.get("scoopable") is False:
            if dry_now == 0:
                dry_start = index
            dry_now += 1
            if dry_now > longest_dry:
                longest_dry = dry_now
                dry_span = (dry_start, index)
        else:
            dry_now = 0
            dry_start = None

    conservative_sample = max(
        (_number(value, 0.0) or 0.0 for value in (fuel_samples or ())),
        default=0.0,
    )
    current_fuel = _number(fuel_main)
    capacity = _number(fuel_capacity)
    endurance = (
        max(0, int(current_fuel / conservative_sample))
        if current_fuel is not None and conservative_sample > 0 else None
    )
    fuel_percent = (
        max(0, min(100, round(current_fuel * 100 / capacity)))
        if current_fuel is not None and capacity and capacity > 0 else None
    )
    current_scoopable = is_scoopable(current_star_class)

    level, status = "ok", "READY"
    if next_scoop is not None and endurance is not None and endurance < next_scoop:
        level, status = (
            ("warn", "TOP OFF NOW") if current_scoopable is True
            else ("alert", "FUEL RISK")
        )
    elif next_scoop is None and not unknown and endurance is not None and endurance < len(pending):
        level, status = "alert", "NO FUEL STAR"
    elif white_dwarfs or longest_dry >= 4:
        level, status = "warn", "CAUTION"
    elif unknown:
        level, status = "info", "PARTIAL DATA"

    scoop_text = (
        f"next scoopable in {next_scoop} jump{'s' if next_scoop != 1 else ''}"
        if next_scoop is not None else
        ("no scoopable primary recorded" if not unknown else "next scoop point uncertain")
    )
    dry_text = f"longest confirmed dry stretch {longest_dry}"
    if dry_span:
        start_name = pending[dry_span[0]].get("system") or "?"
        end_name = pending[dry_span[1]].get("system") or "?"
        dry_text += f" ({start_name} → {end_name})"
    fuel_text = (
        f"tank {fuel_percent}% · about {endurance} conservative jumps"
        if endurance is not None and fuel_percent is not None else
        f"tank {fuel_percent}% · jump burn still learning"
        if fuel_percent is not None else "fuel endurance unavailable"
    )
    hazard_bits = []
    if neutron:
        hazard_bits.append(f"{len(neutron)} neutron")
    if white_dwarfs:
        hazard_bits.append(f"{len(white_dwarfs)} white dwarf")
    if unknown:
        hazard_bits.append(f"{unknown} unknown class")
    hazards = ", ".join(hazard_bits) or "no compact-star hazards recorded"
    badge = None
    if level == "alert":
        badge = "ROUTE FUEL"
    elif white_dwarfs:
        badge = f"WD {len(white_dwarfs)}"
    elif longest_dry >= 4:
        badge = f"DRY {longest_dry}"

    return {
        "status": status,
        "level": level,
        "headline": f"{status} · {len(pending)} jumps · ~{max(1, math.ceil(len(pending) * 55 / 60))} min nominal",
        "detail": f"{scoop_text} · {dry_text} · {fuel_text} · {hazards}",
        "jumps": len(pending),
        "eta_minutes": max(1, math.ceil(len(pending) * 55 / 60)),
        "known_classes": len(known),
        "unknown_classes": unknown,
        "scoopable_count": len(scoopable),
        "next_scoop_jumps": next_scoop,
        "longest_dry": longest_dry,
        "neutron_count": len(neutron),
        "white_dwarf_count": len(white_dwarfs),
        "fuel_percent": fuel_percent,
        "fuel_endurance_jumps": endurance,
        "badge": badge,
        "badge_state": "alert" if level == "alert" else "info",
    }


def revisit_candidate(system, bodies, scanned=0, total=0, position=None, timestamp=None):
    """Return a worthwhile unfinished-system record, or ``None`` for noise."""
    system = str(system or "").strip()
    if not system or system in {"---", "Unknown"}:
        return None
    reasons = []
    body_names = []
    score = 0
    valuable_unmapped = 0
    biology_remaining = 0
    for item in bodies or []:
        if not isinstance(item, dict) or item.get("is_star"):
            continue
        body_class = str(item.get("planet_class") or item.get("class") or "")
        reward = _integer(item.get("dss_reward") or item.get("reward"))
        mapped = bool(item.get("dss_complete") or item.get("mapped"))
        terraformable = bool(item.get("terraformable"))
        valuable = body_class in HIGH_VALUE_WORLDS or terraformable or reward >= 250_000
        if valuable and not mapped:
            valuable_unmapped += 1
            score += 45 if body_class in HIGH_VALUE_WORLDS else 30
            body_names.append(str(item.get("full_name") or item.get("name") or body_class))
        bio_total = _integer(item.get("bio_count"))
        bio_done = max(
            _integer(item.get("organic_complete_count")),
            sum(1 for row in (item.get("organic_scans") or {}).values()
                if isinstance(row, dict) and row.get("is_complete")),
        )
        if bio_total > bio_done:
            remaining = bio_total - bio_done
            biology_remaining += remaining
            score += 35 + min(25, remaining * 5)
            body_names.append(str(item.get("full_name") or item.get("name") or "Biology body"))

    remaining_fss = max(0, _integer(total) - _integer(scanned))
    if valuable_unmapped:
        reasons.append(f"{valuable_unmapped} valuable mapping target(s)")
    if biology_remaining:
        reasons.append(f"{biology_remaining} biological analysis/analyses")
    # Retain an incomplete FSS record when some worthwhile evidence is already
    # known, or when a substantial portion of a larger system remains unknown.
    if remaining_fss and (reasons or remaining_fss >= 5):
        reasons.append(f"FSS {_integer(scanned)}/{_integer(total)}")
        score += min(25, remaining_fss * 3)
    if not reasons:
        return None
    return {
        "system": system,
        "timestamp": str(timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")),
        "position": list(position[:3]) if isinstance(position, (list, tuple)) and len(position) >= 3 else None,
        "score": min(100, score),
        "reasons": reasons,
        "detail": " · ".join(reasons),
        "bodies": list(dict.fromkeys(body_names))[:8],
        "scanned": _integer(scanned),
        "total": _integer(total),
        "valuable_unmapped": valuable_unmapped,
        "biology_remaining": biology_remaining,
    }


def data_vault_snapshot(companion_state, sessions=()):
    """Build a truthful unsold/sold explorer-data summary."""
    state = companion_state if isinstance(companion_state, dict) else {}
    sessions = [row for row in (sessions or ()) if isinstance(row, dict)]
    exploration = _integer(state.get("unsold_exploration_cr"))
    biology = _integer(state.get("unsold_bio_cr"))
    bonus = _integer(state.get("unsold_bio_bonus_potential_cr"))
    keys = len(state.get("unsold_scan_keys") or [])
    last_cartographic = state.get("last_exploration_sale") or {}
    last_biology = state.get("last_bio_sale") or {}
    if not last_cartographic:
        session = next((row for row in sessions if _integer(row.get("exploration_sales"))), None)
        if session:
            last_cartographic = {
                "timestamp": session.get("ended") or session.get("started"),
                "value": _integer(session.get("exploration_sales")),
            }
    if not last_biology:
        session = next((row for row in sessions if _integer(row.get("biology_sales"))), None)
        if session:
            last_biology = {
                "timestamp": session.get("ended") or session.get("started"),
                "value": _integer(session.get("biology_sales")),
            }
    return {
        "exploration_cr": exploration,
        "biology_cr": biology,
        "biology_bonus_cr": bonus,
        "minimum_total_cr": exploration + biology,
        "maximum_total_cr": exploration + biology + bonus,
        "systems_represented": keys,
        "last_exploration_sale": dict(last_cartographic),
        "last_bio_sale": dict(last_biology),
        "lost_at": state.get("exploration_data_lost_at"),
    }


def save_expedition_share_card(path, title, session, snapshot, palette):
    """Write a themed 1200×675 PNG from retained expedition facts."""
    from PIL import Image, ImageDraw, ImageFont

    palette = dict(palette or {})
    bg = palette.get("bg", "#070b10")
    panel = palette.get("panel", "#0d141c")
    accent = palette.get("accent", "#00d1ff")
    orange = palette.get("orange", "#ff8a3d")
    text = palette.get("text", "#dcebf3")
    muted = palette.get("muted", "#91a8b7")
    image = Image.new("RGB", (1200, 675), bg)
    draw = ImageDraw.Draw(image)

    def font(size, bold=False):
        candidates = (
            "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    session = session if isinstance(session, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    route = [row for row in snapshot.get("route_points") or [] if isinstance(row, dict)]
    draw.rectangle((28, 28, 1172, 647), fill=panel, outline=accent, width=2)
    draw.line((28, 102, 1172, 102), fill=accent, width=2)
    draw.text((58, 48), str(title or "EXPEDITION").upper()[:60], fill=accent, font=font(31, True))
    draw.text((58, 82), "VOIDCOMPASS // EXPEDITION CHRONICLE", fill=orange, font=font(13, True))

    stats = (
        ("JUMPS", _integer(session.get("jumps"))),
        ("DISTANCE", f"{_number(session.get('distance_ly'), 0.0):,.1f} LY"),
        ("FSS", _integer(session.get("fss_surveys"))),
        ("DSS", _integer(session.get("dss_maps"))),
        ("BIO", _integer(session.get("bio_analyses"))),
        ("CODEX", _integer(session.get("codex"))),
    )
    for index, (label, value) in enumerate(stats):
        x = 58 + (index % 3) * 190
        y = 132 + (index // 3) * 92
        draw.text((x, y), label, fill=muted, font=font(12, True))
        draw.text((x, y + 23), str(value), fill=text, font=font(23, True))

    map_box = (650, 130, 1135, 520)
    draw.rectangle(map_box, fill=bg, outline=palette.get("border", "#243746"), width=2)
    points = []
    for row in route:
        pos = row.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) >= 3:
            try:
                points.append((float(pos[0]), float(pos[2])))
            except (TypeError, ValueError):
                pass
    if points:
        min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
        min_y, max_y = min(y for _, y in points), max(y for _, y in points)
        span_x, span_y = max(1.0, max_x - min_x), max(1.0, max_y - min_y)
        projected = [(
            map_box[0] + 24 + (x - min_x) / span_x * (map_box[2] - map_box[0] - 48),
            map_box[3] - 24 - (y - min_y) / span_y * (map_box[3] - map_box[1] - 48),
        ) for x, y in points]
        if len(projected) > 1:
            draw.line(projected, fill=orange, width=3)
        for index, point in enumerate(projected):
            radius = 7 if index in (0, len(projected) - 1) else 3
            draw.ellipse((point[0] - radius, point[1] - radius,
                          point[0] + radius, point[1] + radius),
                         fill=accent if index == len(projected) - 1 else orange)
    else:
        draw.text((795, 310), "NO ROUTE COORDINATES", fill=muted, font=font(14, True))

    start = session.get("start_system") or (route[0].get("system") if route else "Unknown")
    end = session.get("end_system") or (route[-1].get("system") if route else "Unknown")
    draw.text((58, 350), "ROUTE", fill=orange, font=font(13, True))
    draw.text((58, 378), f"{start}  →  {end}", fill=text, font=font(21, True))
    sales = _integer(session.get("exploration_sales")) + _integer(session.get("biology_sales"))
    draw.text((58, 438), "DATA SOLD", fill=muted, font=font(12, True))
    draw.text((58, 462), f"{sales:,} CR", fill=accent, font=font(24, True))
    date = str(session.get("started") or datetime.now(timezone.utc).isoformat())[:10]
    draw.text((58, 590), f"{date}  //  Generated locally from Elite journal evidence",
              fill=muted, font=font(12))
    image.save(path, format="PNG", optimize=True)
    return path
