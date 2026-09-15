"""Normalisation and ranking for the Exploration Scout workspace.

The scout deliberately deals in *known* community catalogue evidence.  It
does not imply that an absent body or signal is absent from the galaxy, and
keeps source/freshness metadata beside every recommendation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math


SCOUT_MODES = {
    "value": "High-value worlds",
    "biology": "Biological signals",
    "guardian": "Guardian sites",
    "thargoid": "Thargoid sites",
}

SIGNAL_MODES = {
    "biology": "Biological",
    "guardian": "Guardian",
    "thargoid": "Thargoid",
}


def _number(value, default=None):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return default


def _text(value, limit=180):
    return str(value or "").strip()[:limit]


def utc_timestamp(value=None):
    """Return a stable UTC timestamp for the result provenance line."""
    if value:
        return _text(value, 40)
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def scout_mode(value):
    key = _text(value, 30).casefold()
    return key if key in SCOUT_MODES else "biology"


def normalise_scout_form(values=None, *, current_system=""):
    """Return the one bounded form model used by Scout display and commands."""
    values = values if isinstance(values, dict) else {}
    jump_range = _number(values.get("jump_range"), 30.0)
    return {
        "reference": _text(values.get("reference") or current_system, 140),
        "mode": scout_mode(values.get("mode")),
        "radius": max(1, min(10_000, _integer(values.get("radius"), 500))),
        "min_signals": max(1, min(100, _integer(values.get("min_signals"), 1))),
        "min_value": max(1, min(100_000_000, _integer(values.get("min_value"), 500_000))),
        "max_results": max(1, min(100, _integer(values.get("max_results"), 20))),
        "jump_range": max(1.0, min(500.0, jump_range if jump_range is not None else 30.0)),
    }


def _signals(row):
    output = []
    for item in row.get("signals") or []:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name") or item.get("type"), 80)
        count = max(0, _integer(item.get("count")))
        if name:
            output.append({"name": name, "count": count})
    return output


def normalise_body_prospects(payload, mode, *, searched_at=None):
    """Turn a Spansh body-search response into bounded display records."""
    mode = scout_mode(mode)
    wanted_signal = SIGNAL_MODES.get(mode)
    rows = []
    for raw in (payload or {}).get("results") or []:
        if not isinstance(raw, dict):
            continue
        signals = _signals(raw)
        wanted_count = sum(
            item["count"] for item in signals
            if wanted_signal and item["name"].casefold() == wanted_signal.casefold()
        )
        if wanted_signal and wanted_count <= 0:
            continue
        distance = _number(raw.get("distance"))
        mapping_value = max(0, _integer(raw.get("estimated_mapping_value")))
        scan_value = max(0, _integer(raw.get("estimated_scan_value")))
        landmarks = []
        for item in raw.get("landmarks") or []:
            if not isinstance(item, dict):
                continue
            kind = _text(item.get("type"), 80)
            subtype = _text(item.get("subtype"), 120)
            if wanted_signal and wanted_signal.casefold() not in f"{kind} {subtype}".casefold():
                continue
            landmarks.append({"type": kind, "subtype": subtype})
        reasons = []
        if wanted_count:
            reasons.append(f"{wanted_count} known {wanted_signal.lower()} signal{'s' if wanted_count != 1 else ''}")
        if mapping_value:
            reasons.append(f"{mapping_value:,} CR estimated mapping value")
        if raw.get("terraforming_state") and "not terraformable" not in str(raw.get("terraforming_state")).casefold():
            reasons.append("terraformable")
        if landmarks:
            named = sorted({item["subtype"] or item["type"] for item in landmarks if item["subtype"] or item["type"]})
            if named:
                reasons.append("known sites: " + ", ".join(named[:3]))
        score = wanted_count * 100.0 + min(80.0, mapping_value / 20_000.0)
        if distance is not None:
            score -= min(60.0, distance / 20.0)
        rows.append({
            "system": _text(raw.get("system_name") or raw.get("systemName"), 140),
            "body": _text(raw.get("name") or raw.get("body_name"), 180),
            "system_id64": raw.get("system_id64"),
            "body_id64": raw.get("id64"),
            "coords": [
                _number(raw.get("system_x")),
                _number(raw.get("system_y")),
                _number(raw.get("system_z")),
            ],
            "distance": distance,
            "arrival_ls": _number(raw.get("distance_to_arrival")),
            "body_type": _text(raw.get("subtype") or raw.get("type"), 100),
            "atmosphere": _text(raw.get("atmosphere"), 100),
            "gravity": _number(raw.get("gravity")),
            "temperature": _number(raw.get("surface_temperature")),
            "mapping_value": mapping_value,
            "scan_value": scan_value,
            "signal_count": wanted_count,
            "signals": signals[:12],
            "landmarks": landmarks[:12],
            "reasons": reasons[:4],
            "confidence": "NAMED SITE MATCH" if landmarks else "CATALOGUE SIGNAL MATCH",
            "score": round(score, 2),
            "updated_at": _text(raw.get("signals_updated_at") or raw.get("updated_at"), 40),
            "source": "Spansh community catalogue",
        })
    rows.sort(key=lambda row: (
        -row["score"],
        row["distance"] is None,
        row["distance"] if row["distance"] is not None else float("inf"),
        row["system"].casefold(),
        row["body"].casefold(),
    ))
    reference = (payload or {}).get("reference") or {}
    return {
        "mode": mode,
        "mode_label": SCOUT_MODES[mode],
        "reference": _text(reference.get("name"), 140),
        "catalogue_count": max(0, _integer((payload or {}).get("count"))),
        "searched_at": utc_timestamp(searched_at),
        "source": "Spansh",
        "evidence_note": "Known community records only; unreported and unexplored systems cannot appear.",
        "results": rows,
    }


def normalise_value_route(systems, *, reference="", searched_at=None):
    """Normalise the Spansh riches route as ranked system prospects."""
    rows = []
    for index, raw in enumerate(systems or []):
        if not isinstance(raw, dict):
            continue
        bodies = []
        for body in raw.get("bodies") or []:
            if not isinstance(body, dict):
                continue
            value = max(0, _integer(body.get("map_value") or body.get("scan_value")))
            bodies.append({
                "name": _text(body.get("name"), 180),
                "type": _text(body.get("type"), 100),
                "terraformable": bool(body.get("terraformable")),
                "arrival_ls": _number(body.get("dist_ls")),
                "value": value,
            })
        bodies.sort(key=lambda row: (-row["value"], row["arrival_ls"] or 0))
        total = max(0, _integer(raw.get("total_value")))
        reasons = []
        if total:
            reasons.append(f"{total:,} CR estimated system value")
        if bodies:
            reasons.append(f"{len(bodies)} mapped-value target{'s' if len(bodies) != 1 else ''}")
        terraformable = sum(1 for body in bodies if body["terraformable"])
        if terraformable:
            reasons.append(f"{terraformable} terraformable")
        rows.append({
            "system": _text(raw.get("system"), 140),
            "body": bodies[0]["name"] if bodies else "",
            "system_id64": raw.get("system_id64"),
            "body_id64": None,
            "coords": None,
            "distance": None,
            "arrival_ls": bodies[0]["arrival_ls"] if bodies else None,
            "body_type": bodies[0]["type"] if bodies else "",
            "mapping_value": total,
            "scan_value": 0,
            "signal_count": 0,
            "signals": [],
            "landmarks": [],
            "bodies": bodies[:12],
            "reasons": reasons,
            "confidence": "ROUTE VALUE ESTIMATE",
            "score": float(total),
            "route_index": index + 1,
            "jumps": max(0, _integer(raw.get("jumps"))),
            "updated_at": "",
            "source": "Spansh riches route",
        })
    return {
        "mode": "value",
        "mode_label": SCOUT_MODES["value"],
        "reference": _text(reference, 140),
        "catalogue_count": len(rows),
        "searched_at": utc_timestamp(searched_at),
        "source": "Spansh",
        "evidence_note": "Known community records only; values are estimates and first-discovery status is not guaranteed.",
        "results": rows,
    }


def system_audit(completion, survey_queue=None):
    """Add commander queue state to the shared exploration completion model."""
    completion = completion if isinstance(completion, dict) else {}
    queue = survey_queue or {}
    rows = list(queue.get("rows") or [])
    pending = [row for row in rows if row.get("status") in {"pinned", "pending"}]
    scanned_count = max(0, _integer(completion.get("scanned")))
    total_count = max(0, _integer(completion.get("total")))
    scan_known = bool(completion.get("fss_complete"))
    return {
        "known_bodies": max(0, _integer(completion.get("known_bodies"))),
        "mapped_bodies": max(0, _integer(completion.get("mapped_bodies"))),
        "bio_targets": max(0, _integer(completion.get("bio_targets"))),
        "geo_targets": max(0, _integer(completion.get("geo_targets"))),
        "valuable_targets": max(0, _integer(completion.get("valuable_targets"))),
        "pending": len(pending),
        "scan_known": scan_known,
        "scanned": scanned_count,
        "total": total_count,
        "complete": bool(completion.get("complete") and not pending),
        "next": _text((queue.get("next") or (pending[0] if pending else {})).get("body"), 180),
        "source": "Elite journal",
    }
