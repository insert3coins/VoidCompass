"""Pure journal-backed helpers for the Explorer Decision Deck.

These helpers deliberately avoid predicting undiscovered game state.  They
rank only facts already present in Elite's journals and describe personal
Codex coverage rather than claiming that a discovery exists in a region.
"""

from __future__ import annotations

import math

from galactic_regions import find_region
from route_stars import is_scoopable


DOCTRINES = {
    "balanced": "Balanced",
    "completionist": "Completionist",
    "exobiology": "Exobiology",
    "codex": "Codex Hunter",
    "value": "Value Hunter",
    "transit": "Fast Transit",
}

WHITE_DWARF_CLASSES = {
    "D", "DA", "DAB", "DAO", "DAZ", "DAV", "DB", "DBZ", "DBV",
    "DO", "DOV", "DQ", "DC", "DCV", "DX",
}


def _integer(value, default=0):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return default


def _position(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return tuple(float(value[index]) for index in range(3))
    except (TypeError, ValueError, OverflowError):
        return None


def _distance(left, right):
    if left is None or right is None:
        return None
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def normalise_doctrine(value):
    key = str(value or "balanced").strip().casefold()
    return key if key in DOCTRINES else "balanced"


def route_horizon(entries, current_system="", current_position=None, limit=5):
    """Build a compact next-jump outlook from exact NavRoute entries."""
    rows = []
    for raw in entries or ():
        if not isinstance(raw, dict) or not raw.get("StarSystem"):
            continue
        star_class = str(raw.get("StarClass") or "").strip().upper()
        position = _position(raw.get("StarPos"))
        if star_class in {"N", "NS"}:
            hazard = "NEUTRON"
        elif star_class in WHITE_DWARF_CLASSES:
            hazard = "WHITE DWARF"
        elif star_class in {"H", "BH", "SUPERMASSIVEBLACKHOLE"}:
            hazard = "BLACK HOLE"
        else:
            hazard = ""
        rows.append({
            "system": str(raw.get("StarSystem")),
            "star_class": star_class or "?",
            "scoopable": is_scoopable(star_class),
            "hazard": hazard,
            "position": position,
        })

    current_key = str(current_system or "").casefold()
    current_index = next((
        index for index, row in enumerate(rows)
        if row["system"].casefold() == current_key
    ), None)
    pending = rows[current_index + 1:] if current_index is not None else rows
    pending = pending[:max(1, min(8, _integer(limit, 5)))]
    previous_position = _position(current_position)
    previous_region = find_region(*previous_position) if previous_position else None
    output = []
    for index, row in enumerate(pending, 1):
        region = find_region(*row["position"]) if row["position"] else None
        distance = _distance(previous_position, row["position"])
        crossing = bool(
            previous_region and region
            and previous_region[0] != region[0]
        )
        output.append({
            "index": index,
            "system": row["system"],
            "star_class": row["star_class"],
            "scoopable": row["scoopable"],
            "hazard": row["hazard"],
            "distance_ly": round(distance, 1) if distance is not None else None,
            "region": region[1] if region else "",
            "region_crossing": crossing,
        })
        if row["position"] is not None:
            previous_position = row["position"]
        if region:
            previous_region = region

    scoopable_count = sum(row["scoopable"] is True for row in output)
    unknown_count = sum(row["scoopable"] is None for row in output)
    hazards = [row["hazard"] for row in output if row["hazard"]]
    crossings = [row["region"] for row in output if row["region_crossing"] and row["region"]]
    parts = []
    if output:
        parts.append(f"{scoopable_count}/{len(output)} scoopable")
    if unknown_count:
        parts.append(f"{unknown_count} star class unknown")
    if hazards:
        parts.append("hazard " + ", ".join(dict.fromkeys(hazards)))
    if crossings:
        parts.append("entering " + crossings[0])
    return {
        "active": bool(output),
        "jumps": output,
        "summary": " · ".join(parts) if parts else "No plotted jump horizon",
        "scoopable_count": scoopable_count,
        "hazard_count": len(hazards),
        "region_crossings": crossings,
    }


def personal_codex_hunt(codex_rows, current_region="", active_expedition=None, limit=5):
    """Compare personal Codex history across regions without inventing spawns."""
    unique = {}
    current_keys = set()
    region_key = str(current_region or "").strip().casefold()
    region_known = bool(region_key and region_key not in {"unknown", "unknown region"})
    for raw in codex_rows or ():
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "Codex entry").strip()
        entry_id = raw.get("entry_id")
        key = str(entry_id) if entry_id not in (None, "") else name.casefold()
        row = unique.setdefault(key, {
            "entry_id": entry_id,
            "name": name,
            "category": str(raw.get("category") or "Unclassified").strip(),
            "subcategory": str(raw.get("subcategory") or "").strip(),
            "regions": set(),
        })
        source_region = str(raw.get("region") or "").strip()
        if source_region:
            row["regions"].add(source_region)
        if region_known and source_region.casefold() == region_key:
            current_keys.add(key)

    candidates = []
    for key, row in unique.items():
        if not region_known or key in current_keys:
            continue
        candidates.append({
            "entry_id": row["entry_id"],
            "name": row["name"],
            "category": row["category"],
            "subcategory": row["subcategory"],
            "seen_in": sorted(row["regions"])[:3],
        })
    candidates.sort(key=lambda row: (row["category"].casefold(), row["name"].casefold()))
    category_counts = {}
    for row in candidates:
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1
    categories = [
        {"name": name, "personal_gaps": count}
        for name, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    total = len(unique)
    current = len(current_keys)
    coverage = round(current * 100.0 / total, 1) if total else 0.0
    target = categories[0]["name"] if categories else ""
    active_expedition = active_expedition if isinstance(active_expedition, dict) else {}
    return {
        "region": current_region or "Unknown region",
        "personal_entries_here": current,
        "personal_entries_total": total,
        "personal_coverage_percent": coverage,
        "personal_gap_count": len(candidates),
        "candidates": candidates[:max(1, min(12, _integer(limit, 5)))],
        "categories": categories[:6],
        "target_category": target,
        "active_expedition_id": active_expedition.get("id"),
        "active_expedition_name": active_expedition.get("name") or "",
        "availability_note": (
            "Personal coverage comparison; local availability is not inferred."
            if region_known else "Current Codex region is not yet known."
        ),
    }


def explorer_decision(doctrine, survey, route, actions, flight, data, codex_hunt, adaptive=None):
    """Choose one explainable next action from already-known facts."""
    doctrine = normalise_doctrine(doctrine)
    doctrine_label = DOCTRINES[doctrine]
    survey = survey or {}
    route = route or {}
    flight = flight or {}
    data = data or {}
    codex_hunt = codex_hunt or {}
    adaptive = adaptive or {}
    candidates = []

    for source in actions or ():
        if not isinstance(source, dict):
            continue
        row = dict(source)
        row["score"] = _integer(source.get("priority"), 50)
        row["id"] = str(source.get("id") or source.get("kind") or "objective")
        row["kind"] = str(source.get("kind") or "survey").casefold()
        candidates.append(row)

    if codex_hunt.get("target_category"):
        candidates.append({
            "id": "regional-codex", "kind": "codex", "score": 46,
            "title": f"Review {codex_hunt['target_category']} coverage",
            "detail": (
                f"Your personal Codex has {codex_hunt.get('personal_gap_count', 0)} entries "
                f"recorded elsewhere but not yet in {codex_hunt.get('region') or 'this region'}. "
                "Local availability remains unconfirmed."
            ),
        })
    if route.get("next") and not any(row["kind"] == "route" for row in candidates):
        candidates.append({
            "id": "continue-route", "kind": "route", "score": 48,
            "title": f"Continue to {route['next']}",
            "detail": route.get("horizon", {}).get("summary") or route.get("text") or "The plotted route is ready.",
        })

    activity_mode = str(adaptive.get("mode") or "").casefold()
    activity_cards = {
        "mining": ("mining", "Review active mining operation", "Prospector, refinery and cargo evidence are active in the mining workspace."),
        "carrier": ("carrier", "Review carrier expedition", "Carrier navigation and Tritium context are the current live activity."),
        "ground": ("ground", "Review surface operation", "Ground navigation and exobiology context are currently active."),
    }
    if activity_mode in activity_cards:
        kind, title, detail = activity_cards[activity_mode]
        candidates.append({
            "id": f"activity-{kind}", "kind": kind, "score": 84,
            "title": title, "detail": detail,
        })

    modifiers = {
        "balanced": {},
        "completionist": {"survey": 36, "body": 28, "biology": 24, "route": -12},
        "exobiology": {"biology": 55, "body": 12, "survey": 10, "route": -14},
        "codex": {"codex": 60, "survey": 12, "route": -10},
        "value": {"data": 38, "body": 20, "biology": 12},
        "transit": {"route": 65, "survey": -28, "body": -34, "codex": -20},
    }[doctrine]
    for row in candidates:
        row["score"] += modifiers.get(row["kind"], 0)
        haystack = f"{row.get('title', '')} {row.get('detail', '')}".casefold()
        if doctrine == "value" and any(token in haystack for token in ("valuable", "earthlike", "water world", "ammonia", "terraform")):
            row["score"] += 35
        if doctrine == "exobiology" and "bio" in haystack:
            row["score"] += 28
        if row["id"] == "active-sample":
            row["score"] += 100  # Never abandon a live three-sample chain.

    if flight.get("docked") and _integer(data.get("unsold_total")) > 0:
        candidates.append({
            "id": "review-data", "kind": "data", "score": 155,
            "title": "Review data before departure",
            "detail": f"{_integer(data.get('unsold_total')):,} cr remains in the profile ledger while docked.",
        })

    if candidates:
        chosen = max(candidates, key=lambda row: (row["score"], row.get("title") or ""))
    else:
        chosen = {
            "id": "monitor-system", "kind": "survey", "score": 1,
            "title": "Hold for exploration telemetry",
            "detail": "No unresolved journal-backed survey or route objective is currently known.",
        }

    chosen_id = chosen["id"]
    kind = chosen["kind"]
    if chosen_id == "continue-route":
        primary = {"label": "COPY NEXT SYSTEM", "command": "copy_next", "target": ""}
    elif chosen_id == "regional-codex" or kind == "codex":
        primary = {"label": "OPEN CODEX ATLAS", "command": "open_codex_atlas", "target": ""}
    elif chosen_id in {"active-sample", "bio-field-target"} or kind == "biology":
        primary = {"label": "OPEN GROUND & EXOBIO", "command": "open", "target": "ground"}
    elif chosen_id == "review-data" or kind == "data":
        primary = {"label": "OPEN VALUE LEDGER", "command": "open", "target": "ledger"}
    elif chosen_id == "depart-system" or kind == "departure":
        primary = {"label": "OPEN GALACTIC ATLAS", "command": "open", "target": "map"}
    elif kind == "mining":
        primary = {"label": "OPEN MINING COMMAND", "command": "open", "target": "mining"}
    elif kind == "carrier":
        primary = {"label": "OPEN CARRIER COMMAND", "command": "open", "target": "carrier"}
    elif kind == "ground":
        primary = {"label": "OPEN GROUND & EXOBIO", "command": "open", "target": "ground"}
    else:
        primary = {"label": "OPEN SYSTEM SURVEY", "command": "open", "target": "explore"}

    tags = [doctrine_label.upper(), kind.upper()]
    activity = str(adaptive.get("label") or "").strip()
    if activity:
        tags.append(activity.upper())
    return {
        "id": chosen_id,
        "title": str(chosen.get("title") or "Exploration objective").upper(),
        "detail": str(chosen.get("detail") or "Journal-backed exploration objective."),
        "kind": kind,
        "score": chosen["score"],
        "doctrine": doctrine,
        "doctrine_label": doctrine_label,
        "confidence": "SMART JOURNAL CUE" if chosen_id != "regional-codex" else "PERSONAL COVERAGE",
        "tags": tags[:4],
        "primary": primary,
    }
