"""Rhino deposit estimates and ground-based surface-mining intelligence.

The ground classifier and reserve model follow Fumlop/EDRhinoSpotter's
GPL-3.0 mining sheet and deposit evidence at commit
30177fcd60ed3604b45a01b1d388d3dc4354ea1b.  The figures are field estimates,
not values published by Frontier or guaranteed contents of a location.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache

from voidcompass.core.paths import resource_path


DENSITIES = ("Low", "Medium", "High")
AMOUNTS = ("High", "Medium", "Low", "Depleted")
TONS_PER_RIG = (275, 300)
SHARE_LEFT = {
    "High": (0.566, 1.0),
    "Medium": (0.267, 0.665),
    "Low": (0.0, 0.342),
    "Depleted": (0.0, 0.0),
}

GROUND_LABELS = {
    "metal-rich": "Metal-Rich World",
    "high-metal-content": "High Metal Content World",
    "rock 80%+ [metallic magma]": "Rocky World [metallic magma]",
    "rock 80%+ [rocky magma]": "Rocky World [rocky magma]",
    "rock 80%+ [silicate vapour geysers]": "Rocky World [silicate]",
    "rock 80%+ [silicate magma]": "Rocky World [silicate magma]",
    "rock 80%+ [other volcanism]": "Rocky World [volcanic]",
    "rock 80%+ [none]": "Rocky World",
    "rocky-ice": "Rocky Ice World",
    "icy": "Icy World",
}


def _round10(value):
    return int(round(float(value) / 10.0)) * 10


def tons_left(rigs, amount):
    """Return an estimated ``(low, high)`` tonnes remaining range."""
    share = SHARE_LEFT.get(str(amount or ""))
    if share is None or isinstance(rigs, bool):
        return None
    try:
        rigs = int(rigs)
    except (TypeError, ValueError):
        return None
    if rigs <= 0:
        return None
    return (
        _round10(rigs * TONS_PER_RIG[0] * share[0]),
        _round10(rigs * TONS_PER_RIG[1] * share[1]),
    )


def describe_tons(rigs, amount):
    if amount == "Depleted":
        return "Depleted"
    estimate = tons_left(rigs, amount)
    if estimate is None:
        return ""
    low, high = estimate
    if low == 0:
        return f"Estimated up to {high:,} t left"
    return f"Estimated {low:,}–{high:,} t left"


def classify_ground(body):
    """Classify a VoidCompass body snapshot into a mining-sheet ground."""
    body = body if isinstance(body, dict) else {}
    if body.get("landable") is False or body.get("Landable") is False:
        return None
    planet = str(
        body.get("class") or body.get("planet_class") or body.get("PlanetClass") or ""
    ).strip().casefold()
    if not planet or planet == "unknown":
        return None
    if planet.startswith(("metal rich", "metal-rich")):
        return "metal-rich"
    if planet.startswith("high metal"):
        return "high-metal-content"
    if planet.startswith("rocky ice"):
        return "rocky-ice"
    if planet.startswith("icy"):
        return "icy"
    if not planet.startswith("rocky"):
        return None

    volcanism = " ".join(str(
        body.get("volcanism") or body.get("Volcanism") or ""
    ).casefold().split())
    if "silicate magma" in volcanism:
        return "rock 80%+ [silicate magma]"
    if "silicate" in volcanism:
        return "rock 80%+ [silicate vapour geysers]"
    if "metallic" in volcanism:
        return "rock 80%+ [metallic magma]"
    if "rocky" in volcanism:
        return "rock 80%+ [rocky magma]"
    if volcanism and not any(value in volcanism for value in ("none", "no volcanism")):
        return "rock 80%+ [other volcanism]"
    return "rock 80%+ [none]"


@lru_cache(maxsize=1)
def mining_sheet():
    path = resource_path("data", "rhino_mining_sheet.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {"generated": None, "locations": {}, "grounds": {}}
    return value if isinstance(value, dict) else {"generated": None, "locations": {}, "grounds": {}}


def ground_intelligence(body):
    ground = classify_ground(body)
    sheet = mining_sheet()
    rows = list((sheet.get("grounds") or {}).get(ground) or ())
    ranked = sorted(
        (dict(row, score=float(row.get("pct") or 0) * float(row.get("median") or 0))
         for row in rows if isinstance(row, dict)),
        key=lambda row: (-row["score"], str(row.get("material") or "")),
    )
    return {
        "ground": ground,
        "ground_label": GROUND_LABELS.get(ground, ground or "Ground unclassified"),
        "ground_sample": int((sheet.get("locations") or {}).get(ground) or 0),
        "sheet_generated": sheet.get("generated"),
        "expected_materials": rows,
        "best_materials": ranked[:3],
    }


def surface_distance_m(lat1, lon1, lat2, lon2, radius_m):
    """Great-circle distance between two surface coordinates."""
    try:
        values = tuple(float(value) for value in (lat1, lon1, lat2, lon2, radius_m))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values) or values[-1] <= 0:
        return None
    lat1, lon1, lat2, lon2, radius_m = values
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lon = math.radians((lon2 - lon1 + 180.0) % 360.0 - 180.0)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lon / 2) ** 2
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
