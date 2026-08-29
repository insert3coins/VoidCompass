"""Shared, journal-grounded exploration decision support.

The functions in this module deliberately derive display and Compass facts from
state VoidCompass already owns.  They do not claim that optional surface work
was completed when Elite provides no corresponding journal evidence.
"""

from __future__ import annotations

from datetime import datetime
import math

from deep_survey import HIGH_VALUE_WORLDS, item_value, survey_plan, wonder_rows
from explorer_fieldcraft import (
    bio_field_assistant, return_to_base_plan, route_endurance_monitor,
    route_safety_forecast, sector_grid, system_significance,
)
from galactic_regions import find_region, region_names
from stellar_types import star_type_label


def _integer(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _position(value):
    if isinstance(value, dict):
        value = (
            value.get("x", value.get("X")),
            value.get("y", value.get("Y")),
            value.get("z", value.get("Z")),
        )
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return tuple(float(value[index]) for index in range(3))
    except (TypeError, ValueError):
        return None


def _distance(left, right):
    left, right = _position(left), _position(right)
    if left is None or right is None:
        return None
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _body_name(item):
    return str(item.get("full_name") or item.get("name") or "Unknown body")


def _body_id(item):
    value = item.get("body_id")
    return str(value) if value is not None else None


def _is_valuable(item):
    planet_class = str(item.get("planet_class") or item.get("class") or "")
    return bool(
        item.get("terraformable")
        or planet_class in HIGH_VALUE_WORLDS
        or item_value(item) >= 250_000
    )


def _organic_complete(item):
    reported = _integer(item.get("organic_complete_count"))
    scans = item.get("organic_scans") or {}
    verified = sum(
        1 for row in scans.values()
        if isinstance(row, dict) and row.get("is_complete")
    )
    return max(reported, verified)


def body_completion(item, codex_rows=()):
    """Return the factual completion matrix for one known body."""
    item = item if isinstance(item, dict) else {}
    name = _body_name(item)
    body_id = _body_id(item)
    is_star = bool(item.get("is_star") or item.get("star_type"))
    # WasMapped describes prior Universal Cartographics state; only this
    # commander's SAAScanComplete-backed flag proves current DSS completion.
    mapped = bool(item.get("dss_complete"))
    bio_total = max(0, _integer(item.get("bio_count")))
    bio_complete = min(bio_total, _organic_complete(item)) if bio_total else _organic_complete(item)
    geo_total = max(0, _integer(item.get("geo_count")))
    dss_recommended = bool(
        not is_star and (
            _is_valuable(item) or bio_total or geo_total
            or item.get("was_discovered") is False
        )
    )
    codex_count = 0
    for row in codex_rows or ():
        if not isinstance(row, dict):
            continue
        row_body_id = row.get("body_id")
        row_body = str(row.get("body") or "")
        if (
            body_id is not None and row_body_id is not None
            and str(row_body_id) == body_id
        ) or (row_body and row_body.casefold() == name.casefold()):
            codex_count += 1

    dss_state = "not applicable" if is_star else (
        "complete" if mapped else "recommended" if dss_recommended else "optional"
    )
    biology_state = "none detected"
    if bio_total:
        biology_state = "complete" if bio_complete >= bio_total else "incomplete"
    elif bio_complete:
        biology_state = "complete"
    geology_state = f"{geo_total} detected" if geo_total else "none detected"
    firsts = []
    if item.get("was_discovered") is False:
        firsts.append("first discovery available")
    if item.get("first_footfall"):
        firsts.append("first footfall available")
    matrix = ["FSS ✓"]
    if not is_star:
        matrix.append("DSS ✓" if mapped else "DSS !" if dss_recommended else "DSS —")
    if bio_total or bio_complete:
        matrix.append(f"BIO {bio_complete}/{bio_total or bio_complete}")
    if geo_total:
        matrix.append(f"GEO {geo_total}")
    if codex_count:
        matrix.append(f"CODEX {codex_count}")
    return {
        "body": name,
        "body_id": item.get("body_id"),
        "fss": "complete",
        "dss": dss_state,
        "dss_recommended": dss_recommended,
        "mapped": mapped,
        "biology": biology_state,
        "bio_total": bio_total,
        "bio_complete": bio_complete,
        "geology": geology_state,
        "geo_detected": geo_total,
        "codex": codex_count,
        "firsts": firsts,
        "complete": bool(
            (not dss_recommended or mapped)
            and (not bio_total or bio_complete >= bio_total)
        ),
        "matrix": " · ".join(matrix),
    }


def system_completion(
    bodies, scanned=0, total=0, *, fss_complete=False,
    codex_rows=(), current_system="",
):
    """Build an explainable current-system completion summary."""
    bodies = [row for row in (bodies or ()) if isinstance(row, dict)]
    scanned = max(_integer(scanned), len({
        str(row.get("body_id")) if row.get("body_id") is not None else _body_name(row)
        for row in bodies
    }))
    total = max(0, _integer(total))
    fss_known = bool(fss_complete or (total and scanned >= total))
    unknown_bodies = 0 if fss_complete else max(0, total - scanned)
    rows = [body_completion(item, codex_rows) for item in bodies]
    dss_targets = [row for row in rows if row["dss_recommended"]]
    dss_complete = sum(1 for row in dss_targets if row["mapped"])
    bio_total = sum(row["bio_total"] for row in rows)
    bio_complete = sum(min(row["bio_total"], row["bio_complete"]) for row in rows)
    geo_detected = sum(row["geo_detected"] for row in rows)
    codex_count = sum(row["codex"] for row in rows)
    first_discoveries = sum(
        1 for row in bodies if row.get("was_discovered") is False
    )
    first_footfalls = sum(1 for row in bodies if row.get("first_footfall"))
    task_total = (1 if total or scanned else 0) + len(dss_targets) + bio_total
    task_complete = (1 if fss_known and (total or scanned) else 0) + dss_complete + bio_complete
    percent = round(task_complete * 100 / task_total) if task_total else (100 if fss_known else 0)
    reasons = []
    if unknown_bodies:
        reasons.append(f"{unknown_bodies} FSS bod{'ies' if unknown_bodies != 1 else 'y'} unresolved")
    elif total and not fss_known:
        reasons.append("FSS completion event not yet recorded")
    if len(dss_targets) > dss_complete:
        reasons.append(f"{len(dss_targets) - dss_complete} recommended DSS target(s) remain")
    if bio_total > bio_complete:
        reasons.append(f"{bio_total - bio_complete} biological analysis/analyses remain")
    complete = bool(fss_known and not reasons)
    state = "COMPLETE" if complete else "PARTIAL" if scanned or bodies else "AWAITING"
    fss_label = "COMPLETE" if fss_known else f"{scanned}/{total or '?'}"
    summary_bits = [
        f"FSS {fss_label}",
        f"DSS {dss_complete}/{len(dss_targets)}",
        f"BIO {bio_complete}/{bio_total}",
    ]
    if geo_detected:
        summary_bits.append(f"GEO {geo_detected} DETECTED")
    if codex_count:
        summary_bits.append(f"CODEX {codex_count}")
    return {
        "system": str(current_system or ""),
        "state": state,
        "complete": complete,
        "percent": percent,
        "fss_complete": fss_known,
        "scanned": scanned,
        "total": total,
        "unknown_bodies": unknown_bodies,
        "dss_complete": dss_complete,
        "dss_targets": len(dss_targets),
        "bio_complete": bio_complete,
        "bio_total": bio_total,
        "geo_detected": geo_detected,
        "codex": codex_count,
        "first_discoveries": first_discoveries,
        "first_footfalls": first_footfalls,
        "reasons": reasons,
        "summary": " · ".join(summary_bits),
        "body_rows": rows,
    }


def route_context(app):
    """Compare the live position with game-route and waypoint coordinates."""
    current_system = str(getattr(app, "current_sys", "") or "")
    current_position = _position(getattr(app, "current_coords", None))
    planned = []
    for row in getattr(app, "nav_route_entries", None) or ():
        if not isinstance(row, dict):
            continue
        name = row.get("StarSystem") or row.get("system")
        pos = _position(row.get("StarPos") or row.get("pos"))
        if name:
            planned.append({"system": str(name), "pos": pos, "source": "game", "visited": False})
    game_count = len(planned)
    manager = getattr(app, "waypoint_manager", None)
    waypoints = list(getattr(manager, "waypoints", None) or ())
    for row in waypoints:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        pos = _position(row.get("coords"))
        if not any(str(item["system"]).casefold() == str(row["name"]).casefold() for item in planned):
            planned.append({
                "system": str(row["name"]), "pos": pos, "source": "waypoint",
                "visited": bool(row.get("visited")),
            })
    active_planned = planned[:game_count] if game_count else planned
    current_index = next((
        index for index, row in enumerate(active_planned)
        if current_system and row["system"].casefold() == current_system.casefold()
    ), -1)
    next_row = None
    if current_index >= 0:
        next_row = next((row for row in active_planned[current_index + 1:] if not row.get("visited")), None)
    elif current_index < 0 and active_planned:
        next_row = next((row for row in active_planned if not row.get("visited")), None)
    distance_rows = active_planned
    distances = [
        (distance, row) for row in distance_rows
        if row.get("pos") is not None
        for distance in [_distance(current_position, row["pos"])]
        if distance is not None
    ]
    nearest_distance, nearest = min(distances, default=(None, None), key=lambda item: item[0])
    on_route = current_index >= 0 or (nearest_distance is not None and nearest_distance < 0.1)
    # A game NavRoute contains exact intermediate stars and supports a factual
    # deviation test. User waypoint plans can be very widely spaced, so being
    # between them is not labelled off-route.
    off_route = bool(game_count and not on_route)
    remaining_rows = active_planned[current_index + 1:] if current_index >= 0 else active_planned
    return {
        "planned": planned,
        "on_route": on_route,
        "off_route": off_route,
        "nearest_system": nearest.get("system") if nearest else None,
        "nearest_distance_ly": round(nearest_distance, 1) if nearest_distance is not None else None,
        "next_system": next_row.get("system") if next_row else None,
        "remaining": sum(1 for row in remaining_rows if not row.get("visited")),
    }


def action_queue(app, completion=None, route=None, snapshot=None):
    """Return a small ranked queue of actions backed by known facts."""
    bodies = list(getattr(app, "scan_items", None) or ())
    current_system = str(getattr(app, "current_sys", "") or "")
    completion = completion or system_completion(
        bodies, getattr(app, "scanned", 0), getattr(app, "total", 0),
        fss_complete=bool(getattr(app, "fss_all_bodies", False)),
        current_system=current_system,
    )
    route = route or route_context(app)
    rows = []
    sampling = None
    try:
        sampling = app._sampling_snapshot()
    except Exception:
        sampling = getattr(app, "bio_sampling", None)
    if isinstance(sampling, dict) and sampling.get("species"):
        progress = _integer(sampling.get("progress") or sampling.get("sample_idx"), 1)
        rows.append({
            "id": "active-sample", "priority": 120, "kind": "biology",
            "title": f"Complete {sampling.get('species')}",
            "detail": f"Sample {progress}/3 on {sampling.get('body') or 'the current body'}",
            "system": current_system, "body": sampling.get("body"),
        })
    elif snapshot and isinstance(snapshot.get("bio_assistant"), dict):
        assistant = snapshot["bio_assistant"]
        if assistant.get("state") == "TARGET":
            rows.append({
                "id": "bio-field-target", "priority": 92, "kind": "biology",
                "title": str(assistant.get("headline") or "Review biological target"),
                "detail": str(assistant.get("detail") or "Biological survey work remains"),
                "system": current_system, "body": assistant.get("body"),
                "body_id": assistant.get("body_id"),
            })
    companion = getattr(app, "companion_state", None) or {}
    unsold = _integer(companion.get("unsold_exploration_cr")) + _integer(
        companion.get("unsold_bio_cr")
    )
    if unsold >= 20_000_000:
        rows.append({
            "id": "secure-survey-data", "priority": 106, "kind": "data",
            "title": "Secure valuable survey data",
            "detail": f"Approximately {unsold:,} cr of exploration and biology data remains unsold",
            "system": current_system,
        })
    if (current_system and current_system not in {"---", "Unknown"}
            and not bool(getattr(app, "scan_total_confirmed", False))
            and not bool(getattr(app, "current_docked", False))):
        rows.append({
            "id": "run-discovery-scan", "priority": 116, "kind": "survey",
            "title": "Run a discovery scan",
            "detail": f"The live body count for {current_system} has not been confirmed",
            "system": current_system,
        })
    if completion["unknown_bodies"]:
        count = completion["unknown_bodies"]
        rows.append({
            "id": "complete-fss", "priority": 110, "kind": "survey",
            "title": "Complete the FSS survey",
            "detail": f"{count} bod{'ies remain' if count != 1 else 'y remains'} unresolved in {current_system}",
            "system": current_system,
        })
    plan_items = {_body_name(item): item for item in bodies}
    for plan in survey_plan(bodies):
        if plan.get("action") in ("Observe", "Review biology"):
            continue
        body = str(plan.get("body") or "Unknown body")
        item = plan_items.get(body) or {}
        matrix = body_completion(item, ())
        rows.append({
            "id": f"body:{item.get('body_id', body)}", "priority": _integer(plan.get("score")),
            "kind": "body", "title": f"{plan.get('action')} · {body}",
            "detail": f"{plan.get('reason')} · {matrix['matrix']}",
            "system": current_system, "body": body, "body_id": item.get("body_id"),
        })
    expedition = {}
    manager = getattr(app, "expedition_manager", None)
    if manager:
        try:
            expedition = manager.status_snapshot(
                next_waypoint=route.get("next_system"),
            )
        except Exception:
            expedition = {}
    next_objective = expedition.get("next_objective")
    if expedition.get("active") and next_objective:
        rows.append({
            "id": "expedition-objective", "priority": 72, "kind": "expedition",
            "title": str(next_objective),
            "detail": f"Next objective for {expedition.get('name') or 'the active expedition'}",
            "system": current_system,
        })
    if route.get("off_route"):
        distance = route.get("nearest_distance_ly")
        rows.append({
            "id": "return-route", "priority": 68, "kind": "route",
            "title": f"Return toward {route.get('nearest_system') or 'the planned route'}",
            "detail": f"Current position is {distance:,.1f} ly from the nearest plotted point" if distance is not None else "Current system is outside the plotted route",
            "system": route.get("nearest_system"),
        })
    elif route.get("next_system"):
        rows.append({
            "id": "continue-route", "priority": 48, "kind": "route",
            "title": f"Continue to {route['next_system']}",
            "detail": f"{route.get('remaining', 0)} plotted point(s) remain",
            "system": route["next_system"],
        })
    elif completion.get("complete") and current_system:
        rows.append({
            "id": "depart-system", "priority": 44, "kind": "departure",
            "title": "Survey complete — ready to depart",
            "detail": "No unresolved FSS, mapping or biological work remains in this system",
            "system": current_system,
        })
    deduped = {}
    for row in rows:
        key = (row.get("kind"), row.get("body") or row.get("system") or row.get("title"))
        if key not in deduped or row["priority"] > deduped[key]["priority"]:
            deduped[key] = row
    return sorted(deduped.values(), key=lambda row: (-row["priority"], row["title"]))[:8]


def arrival_brief(app, completion=None, route=None, snapshot=None):
    bodies = list(getattr(app, "scan_items", None) or ())
    current_system = str(getattr(app, "current_sys", "") or "")
    current_position = _position(getattr(app, "current_coords", None))
    region = find_region(*current_position) if current_position else None
    completion = completion or system_completion(
        bodies, getattr(app, "scanned", 0), getattr(app, "total", 0),
        fss_complete=bool(getattr(app, "fss_all_bodies", False)),
        current_system=current_system,
    )
    route = route or route_context(app)
    notable = wonder_rows(bodies)[:3]
    traffic = getattr(app, "system_traffic", None) or {}
    parts = [
        star_type_label(getattr(app, "star_class", ""), "star unknown"),
        region[1] if region else "region unresolved",
        completion["summary"],
    ]
    if notable:
        parts.append("notable " + ", ".join(row["body"] for row in notable[:2]))
    if route.get("off_route"):
        distance = route.get("nearest_distance_ly")
        parts.append(f"off route {distance:,.1f} ly" if distance is not None else "off route")
    traffic_total = _integer(traffic.get("total"))
    if traffic_total:
        parts.append(f"traffic {traffic_total:,}")
    elif getattr(app, "_system_traffic_resolved", False):
        parts.append("no prior traffic recorded")
    return {
        "system": current_system,
        "region": {"id": region[0], "name": region[1]} if region else None,
        "star": star_type_label(getattr(app, "star_class", ""), "Unknown"),
        "scoopable": str(getattr(app, "star_class", "") or "").upper()[:1] in set("OBAFGKM"),
        "traffic": {
            "day": _integer(traffic.get("day")), "week": _integer(traffic.get("week")),
            "total": traffic_total,
        },
        "notable": notable,
        "summary": " · ".join(parts),
    }


def build_intelligence(app):
    """Build the one shared fact packet used by UI, map and Compass."""
    tracker = getattr(app, "deep_survey", None)
    current_system = str(getattr(app, "current_sys", "") or "")
    if tracker and hasattr(tracker, "intelligence_state"):
        snapshot = tracker.intelligence_state(current_system)
    else:
        snapshot = tracker.snapshot() if tracker else {}
    codex_rows = [
        row for row in snapshot.get("codex") or []
        if str(row.get("system") or "").casefold() == current_system.casefold()
    ]
    bodies = list(getattr(app, "scan_items", None) or ())
    completion = system_completion(
        bodies,
        getattr(app, "scanned", 0), getattr(app, "total", 0),
        fss_complete=bool(getattr(app, "fss_all_bodies", False)),
        codex_rows=codex_rows, current_system=current_system,
    )
    route = route_context(app)
    field = build_field_intelligence(
        app, tracker_snapshot=snapshot, route=route, codex_rows=codex_rows,
    )
    action_source = dict(snapshot or {})
    action_source.update(field)
    actions = action_queue(app, completion, route, action_source)
    arrival = arrival_brief(app, completion, route, snapshot)
    regions = snapshot.get("region_stats") or {}
    visited_regions = len([row for row in regions.values() if _integer(row.get("visits"))])
    return {
        "completion": completion,
        "actions": actions,
        "arrival": arrival,
        "route": route,
        "regions": {
            "visited": visited_regions,
            "total": len(region_names()),
            "current": arrival.get("region"),
        },
        "checkpoint": dict(snapshot.get("checkpoint") or {}),
        "last_departure": dict(snapshot.get("last_departure") or {}),
        "milestones": list(snapshot.get("milestones") or [])[-8:],
        **field,
    }


def _system_position_from_state(app, system, tracker_snapshot=None):
    wanted = str(system or "").strip().casefold()
    if not wanted:
        return None
    if wanted == str(getattr(app, "current_sys", "") or "").casefold():
        return _position(getattr(app, "current_coords", None))
    for row in getattr(app, "nav_route_entries", None) or ():
        if not isinstance(row, dict):
            continue
        name = row.get("StarSystem") or row.get("system")
        if str(name or "").casefold() == wanted:
            pos = _position(row.get("StarPos") or row.get("pos"))
            if pos:
                return pos
    waypoint_manager = getattr(app, "waypoint_manager", None)
    for row in getattr(waypoint_manager, "waypoints", None) or ():
        if isinstance(row, dict) and str(row.get("name") or "").casefold() == wanted:
            pos = _position(row.get("coords"))
            if pos:
                return pos
    for row in reversed((tracker_snapshot or {}).get("route_points") or []):
        if isinstance(row, dict) and str(row.get("system") or "").casefold() == wanted:
            pos = _position(row.get("pos"))
            if pos:
                return pos
    return None


def build_field_intelligence(app, tracker_snapshot=None, route=None, codex_rows=()):
    """Build the exploration field-computer packet from cached local facts."""
    tracker_snapshot = tracker_snapshot if isinstance(tracker_snapshot, dict) else {}
    route = route if isinstance(route, dict) else route_context(app)
    bodies = list(getattr(app, "scan_items", None) or ())
    sampling = None
    try:
        sampling = app._sampling_snapshot()
    except Exception:
        sampling = getattr(app, "bio_sampling", None)
    bio = bio_field_assistant(
        bodies, sampling=sampling,
        focused_body=getattr(app, "current_body_name", ""),
    )
    significance = system_significance(bodies, codex_rows)

    entries = list(getattr(app, "nav_route_entries", None) or ())
    try:
        forecast = app._route_safety_snapshot()
    except Exception:
        forecast = route_safety_forecast(
            entries,
            str(getattr(app, "current_sys", "") or ""),
            str(getattr(app, "star_class", "") or ""),
            getattr(app, "current_fuel_main", None),
            getattr(app, "fuel_capacity_main", None),
            getattr(app, "_fuel_used_samples", None) or (),
        )

    manager = getattr(app, "expedition_manager", None)
    active = manager.active() if manager else None
    target = str((active or {}).get("return_system") or "").strip()
    route_names = [
        str(row.get("StarSystem") or row.get("system") or "").strip()
        for row in entries if isinstance(row, dict)
    ]
    if not target and route_names:
        target = route_names[-1]
    current_system = str(getattr(app, "current_sys", "") or "")
    current_pos = _position(getattr(app, "current_coords", None))
    target_pos = _system_position_from_state(app, target, tracker_snapshot)
    distance = _distance(current_pos, target_pos)
    exact_jumps = None
    if target and route_names and route_names[-1].casefold() == target.casefold():
        exact_jumps = route.get("remaining")

    state = getattr(app, "companion_state", None) or {}
    loadout = state.get("loadout") or {}
    jump_range = loadout.get("MaxJumpRange") or (getattr(app, "cmdr_ship", None) or {}).get("max_jump_range")
    fuel_percent = None
    try:
        fuel = float(getattr(app, "current_fuel_main", None))
        capacity = float(getattr(app, "fuel_capacity_main", None))
        if capacity > 0:
            fuel_percent = max(0, min(100, round(fuel * 100 / capacity)))
    except (TypeError, ValueError):
        pass
    hull = _number(getattr(app, "current_hull_percent", None), None)
    minimum_data = _integer(state.get("unsold_exploration_cr")) + _integer(state.get("unsold_bio_cr"))
    maximum_data = minimum_data + _integer(state.get("unsold_bio_bonus_potential_cr"))
    known_services = (
        list(getattr(app, "current_station_services", None) or [])
        if target and target.casefold() == current_system.casefold()
        and bool(getattr(app, "current_docked", False)) else []
    )
    return_plan = return_to_base_plan(
        current_system=current_system, target_system=target,
        distance_ly=distance, exact_jumps=exact_jumps,
        jump_range_ly=jump_range, fuel_percent=fuel_percent,
        hull_percent=hull, unsold_min_cr=minimum_data,
        unsold_max_cr=maximum_data, route_forecast=forecast,
        known_services=known_services,
    )
    raw_materials = (getattr(app, "engineer_materials", None) or {}).get("raw") or {}
    module_text = " ".join(
        str(row.get("Item") or row.get("Item_Localised") or "").casefold()
        for row in loadout.get("Modules") or () if isinstance(row, dict)
    )
    srv_available = None if not loadout else any(
        marker in module_text for marker in ("vehiclebay", "planetary vehicle")
    )
    endurance = route_endurance_monitor(
        forecast, loadout, raw_materials, hull_percent=hull,
        srv_available=srv_available,
    )
    sector = {"active": False, "cells": [], "summary": "No active expedition sector"}
    sector_plan = (active or {}).get("sector_plan")
    if isinstance(sector_plan, dict) and sector_plan.get("center"):
        sector = sector_grid(
            tracker_snapshot.get("route_points") or (), sector_plan.get("center"),
            sector_plan.get("radius_ly", 500), sector_plan.get("cell_size_ly", 100),
        )
        sector["name"] = sector_plan.get("name") or "Expedition sector"
        sector["plan"] = dict(sector_plan)
    return {
        "bio_assistant": bio, "significance": significance,
        "return_plan": return_plan, "endurance": endurance,
        "sector": sector,
    }


def checkpoint_payload(app, reason="app-close", intelligence=None):
    """Build a resume checkpoint.

    ``intelligence`` lets a caller that has just built the shared fact packet
    hand it in, rather than paying for a second identical build.
    """
    if not intelligence:
        intelligence = build_intelligence(app)
    state = getattr(app, "companion_state", None) or {}
    manager = getattr(app, "expedition_manager", None)
    expedition = manager.status_snapshot(
        next_waypoint=intelligence["route"].get("next_system"),
    ) if manager else {}
    sample = None
    try:
        sample = app._sampling_snapshot()
    except Exception:
        sample = getattr(app, "bio_sampling", None)
    deck = getattr(app, "adaptive_command", None)
    dashboard_mode = None
    try:
        dashboard_mode = deck.status().get("mode") if deck else None
    except Exception:
        pass
    return {
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reason": str(reason or "checkpoint"),
        "system": getattr(app, "current_sys", None),
        "coords": list(_position(getattr(app, "current_coords", None)) or ()),
        "completion": intelligence["completion"],
        "active_sample": dict(sample) if isinstance(sample, dict) else None,
        "unsold": {
            "exploration_cr": _integer(state.get("unsold_exploration_cr")),
            "biology_cr": _integer(state.get("unsold_bio_cr")),
            "biology_bonus_potential_cr": _integer(state.get("unsold_bio_bonus_potential_cr")),
        },
        "expedition": expedition,
        "next_waypoint": intelligence["route"].get("next_system"),
        "route": intelligence["route"],
        "dashboard_mode": dashboard_mode,
    }
