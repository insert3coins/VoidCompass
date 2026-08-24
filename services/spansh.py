"""Client for the Spansh carrier, neutron, ring and station services."""

import time
import re

import requests

from version import APP_VERSION

BASE = "https://spansh.co.uk/api"
HEADERS = {
    "User-Agent": f"VoidCompass/{APP_VERSION} (Elite Dangerous companion; insert3coins/VoidCompass)"
}
SUBMIT_TIMEOUT = 20
POLL_TIMEOUT = 20
MAX_WAIT_SECONDS = 90
MODULE_RE = None
FLEET_CARRIER_JOB_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class SpanshError(Exception):
    pass


def submit_and_poll(path, payload, include_job=False):
    """Spansh's async job pattern: POST form payload, then poll results."""
    try:
        resp = requests.post(f"{BASE}/{path}", data=payload, headers=HEADERS, timeout=SUBMIT_TIMEOUT)
    except requests.RequestException as exc:
        raise SpanshError(f"Could not reach Spansh: {exc}") from exc
    if resp.status_code >= 400:
        raise SpanshError(_error_text(resp))
    job = resp.json().get("job")
    if not job:
        raise SpanshError(f"Spansh did not return a job id: {resp.text[:200]}")

    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            poll = requests.get(f"{BASE}/results/{job}", headers=HEADERS, timeout=POLL_TIMEOUT)
        except requests.RequestException as exc:
            raise SpanshError(f"Lost connection to Spansh: {exc}") from exc
        if poll.status_code >= 400:
            raise SpanshError(_error_text(poll))
        data = poll.json()
        status = data.get("status")
        if status == "ok":
            result = data.get("result")
            return (result, str(job)) if include_job else result
        if status in ("queued", "processing"):
            time.sleep(1.5)
            continue
        raise SpanshError(f"Spansh job failed: {data.get('error') or status}")
    raise SpanshError("Spansh took too long to compute a route; try again.")


def resolve_system(system, id64=None):
    """Resolve one exact Elite system through Spansh's public system search."""
    if isinstance(system, dict):
        id64 = system.get("id64") or system.get("system_address") or id64
        name = str(system.get("name") or system.get("system") or "").strip()
    else:
        name = str(system or "").strip()
    if id64 is not None:
        try:
            return {"id64": int(id64), "name": name or str(id64)}
        except (TypeError, ValueError):
            pass
    if not name:
        raise SpanshError("A carrier route system is blank.")
    try:
        response = requests.get(
            f"{BASE}/search/systems", params={"q": name},
            headers=HEADERS, timeout=SUBMIT_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SpanshError(f"Could not resolve {name} through Spansh: {exc}") from exc
    if response.status_code >= 400:
        raise SpanshError(_error_text(response))
    try:
        results = response.json().get("results") or []
    except (ValueError, AttributeError) as exc:
        raise SpanshError(f"Spansh returned invalid system-search data for {name}.") from exc
    exact = next(
        (row for row in results if str(row.get("name") or "").casefold() == name.casefold()),
        None,
    )
    selected = exact or (results[0] if results else None)
    if not selected or selected.get("id64") is None:
        raise SpanshError(f"Spansh could not find the system {name}.")
    return {"id64": int(selected["id64"]), "name": selected.get("name") or name}


def _normalize_fleet_carrier_result(
    result, job, *, source=None, destinations=None, carrier_type=None,
    used_capacity=None, calculate_starting_fuel=None,
):
    if not isinstance(result, dict) or not isinstance(result.get("jumps"), list):
        raise SpanshError("Spansh returned no Fleet Carrier route.")
    jumps = []
    for index, row in enumerate(result["jumps"]):
        if not isinstance(row, dict) or not row.get("name"):
            continue
        jumps.append({
            "index": index,
            "system": row.get("name"),
            "id64": row.get("id64"),
            "distance_ly": row.get("distance"),
            "distance_to_destination_ly": row.get("distance_to_destination"),
            "fuel_remaining_t": row.get("fuel_in_tank"),
            "fuel_used_t": row.get("fuel_used"),
            "tritium_market_t": row.get("tritium_in_market"),
            "restock_t": row.get("restock_amount"),
            "must_restock": bool(row.get("must_restock")),
            "icy_ring": bool(row.get("has_icy_ring")),
            "pristine": bool(row.get("is_system_pristine")),
            "desired_destination": bool(row.get("is_desired_destination")),
        })
    if len(jumps) < 2:
        raise SpanshError("Spansh returned an empty Fleet Carrier route.")

    source_record = source or {"name": jumps[0]["system"], "id64": jumps[0].get("id64")}
    requested = list(destinations or [])
    if not requested:
        requested = [
            {"name": row["system"], "id64": row.get("id64")}
            for row in jumps[1:] if row.get("desired_destination")
        ]
    if not requested:
        requested = [{"name": jumps[-1]["system"], "id64": jumps[-1].get("id64")}]

    carrier_key = str(carrier_type or result.get("carrier_type") or "fleet").casefold()
    squadron = carrier_key in {"squadron", "squadroncarrier"}
    source_jump = jumps[0]
    normalized_used_capacity = (
        used_capacity if used_capacity is not None else result.get("capacity_used")
    )
    normalized_calculate_fuel = (
        calculate_starting_fuel
        if calculate_starting_fuel is not None
        else result.get("calculate_starting_fuel")
    )
    return {
        "job": str(job),
        "url": f"https://spansh.co.uk/fleet-carrier/results/{job}",
        "source": source_record,
        "destinations": requested,
        "carrier_type": "squadron" if squadron else "fleet",
        "used_capacity_t": normalized_used_capacity,
        "calculate_starting_fuel": normalized_calculate_fuel,
        "total_distance_ly": sum(float(row.get("distance_ly") or 0) for row in jumps[1:]),
        "fuel_required_t": sum(int(float(row.get("fuel_used_t") or 0)) for row in jumps[1:]),
        "starting_tank_t": source_jump.get("fuel_remaining_t"),
        "starting_market_tritium_t": source_jump.get("tritium_market_t"),
        "starting_load_t": source_jump.get("restock_t"),
        "jumps": jumps,
    }


def fleet_carrier_job_id(reference):
    """Return a real Spansh result UUID, never a plausible system name."""
    value = str(reference or "").strip()
    candidate = value.split("#", 1)[0].split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return candidate if FLEET_CARRIER_JOB_RE.fullmatch(candidate) else None


def import_fleet_carrier_route(reference):
    """Import a completed Spansh Fleet Carrier result URL or job id."""
    job = fleet_carrier_job_id(reference)
    if not job:
        raise SpanshError(
            "Paste a Spansh Fleet Carrier result URL or UUID; system names are destinations."
        )

    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            response = requests.get(
                f"{BASE}/results/{job}", headers=HEADERS, timeout=POLL_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise SpanshError(f"Could not import the Spansh route: {exc}") from exc
        if response.status_code >= 400:
            raise SpanshError(_error_text(response))
        try:
            data = response.json()
        except ValueError as exc:
            raise SpanshError("Spansh returned invalid route data.") from exc
        status = data.get("status")
        if status == "ok":
            return _normalize_fleet_carrier_result(data.get("result"), job)
        if status in ("queued", "processing"):
            time.sleep(1.5)
            continue
        raise SpanshError(f"Spansh route import failed: {data.get('error') or status}")
    raise SpanshError("The Spansh route is still processing; try the import again.")


def fleet_carrier_route(
    source,
    destinations,
    *,
    source_id64=None,
    used_capacity=0,
    carrier_type="fleet",
    calculate_starting_fuel=True,
    tritium_fuel=0,
    tritium_stored=0,
    refuel_destinations=None,
):
    """Plot a Fleet/Squadron Carrier route using Spansh's live route service.

    The current Spansh web client submits system id64 values to
    ``/api/fleetcarrier/route`` and polls the normal results endpoint. Keep the
    response normalisation here so UI code never depends on its raw shape.
    """
    source_record = resolve_system(source, source_id64)
    requested = []
    seen = {source_record["id64"]}
    for value in destinations or []:
        record = resolve_system(value)
        if record["id64"] in seen:
            continue
        seen.add(record["id64"])
        requested.append(record)
    if not requested:
        raise SpanshError("Add at least one unvisited carrier destination.")

    carrier_key = str(carrier_type or "fleet").casefold()
    squadron = carrier_key in {"squadron", "squadroncarrier"}
    capacity = 60_000 if squadron else 25_000
    mass = 15_000 if squadron else 25_000
    try:
        used = max(0, min(capacity, int(used_capacity or 0)))
    except (TypeError, ValueError):
        used = 0

    payload = {
        "source": source_record["id64"],
        "destinations": [row["id64"] for row in requested],
        "capacity": capacity,
        "mass": mass,
        "capacity_used": used,
        "calculate_starting_fuel": 1 if calculate_starting_fuel else 0,
    }
    if calculate_starting_fuel:
        refuel_ids = []
        for value in refuel_destinations or []:
            refuel_ids.append(resolve_system(value)["id64"])
        if refuel_ids:
            payload["refuel_destinations"] = refuel_ids
    else:
        payload["fuel_loaded"] = max(0, min(1000, int(tritium_fuel or 0)))
        payload["tritium_stored"] = max(0, int(tritium_stored or 0))

    result, job = submit_and_poll("fleetcarrier/route", payload, include_job=True)
    return _normalize_fleet_carrier_result(
        result, job, source=source_record, destinations=requested,
        carrier_type="squadron" if squadron else "fleet", used_capacity=used,
        calculate_starting_fuel=bool(calculate_starting_fuel),
    )


def riches_route(
    from_system,
    to_system=None,
    jump_range=30.0,
    radius=50,
    max_results=30,
    max_distance=1000,
    min_value=300000,
    use_mapping_value=True,
    loop=True,
):
    if not from_system:
        raise SpanshError("No starting system known yet.")
    payload = {
        "from": from_system,
        "to": to_system or from_system,
        "range": float(jump_range),
        "radius": int(radius),
        "max_results": int(max_results),
        "max_distance": int(max_distance),
        "min_value": int(min_value),
        "use_mapping_value": 1 if use_mapping_value else 0,
        "loop": 1 if loop else 0,
    }
    result = submit_and_poll("riches/route", payload)
    systems = []
    for hop in result if isinstance(result, list) else []:
        bodies = []
        for body in hop.get("bodies") or []:
            bodies.append({
                "name": body.get("name"),
                "type": body.get("subtype") or body.get("type"),
                "terraformable": bool(body.get("is_terraformable")),
                "dist_ls": body.get("distance_to_arrival"),
                "map_value": body.get("estimated_mapping_value"),
                "scan_value": body.get("estimated_scan_value"),
            })
        systems.append({
            "system": hop.get("name") or hop.get("system_name"),
            "jumps": hop.get("jumps"),
            "bodies": bodies,
            "total_value": sum((b["map_value"] or b["scan_value"] or 0) for b in bodies),
        })
    return systems


def neutron_route(from_system, to_system, jump_range, efficiency=60, supercharge_multiplier=4):
    if not from_system:
        raise SpanshError("No starting system known yet.")
    if not to_system:
        raise SpanshError("No destination system given.")
    payload = {
        "from": from_system,
        "to": to_system,
        "range": float(jump_range),
        "efficiency": int(efficiency),
        "supercharge_multiplier": 6 if int(supercharge_multiplier) == 6 else 4,
    }
    result = submit_and_poll("route", payload)
    jumps = result.get("system_jumps") if isinstance(result, dict) else None
    if not jumps:
        raise SpanshError("Spansh returned no route.")
    return {
        "total_jumps": result.get("total_jumps"),
        "waypoints": [
            {
                "system": j.get("system"),
                "distance_jumped": j.get("distance_jumped"),
                "distance_left": j.get("distance_left"),
                "neutron": bool(j.get("neutron_star")),
                "jumps": j.get("jumps"),
                "supercharge_multiplier": 6 if int(supercharge_multiplier) == 6 else 4,
            }
            for j in jumps
        ],
    }


def station_search(reference_system, module=None, ship=None, size=20):
    global MODULE_RE
    if not reference_system:
        raise SpanshError("No reference system known yet.")
    if MODULE_RE is None:
        # (\S.*) instead of (.+): the latter can backtrack polynomially against
        # the preceding \s+ on pathological all-whitespace input (ReDoS).
        MODULE_RE = re.compile(r"^(\d)\s*([A-EI])\s+(\S.*)$", re.IGNORECASE)
    filters = {}
    if module:
        match = MODULE_RE.match(module.strip())
        if match:
            filters["modules"] = [{
                "class": [match.group(1)],
                "rating": [match.group(2).upper()],
                "name": [match.group(3).strip().title()],
            }]
        else:
            filters["modules"] = [{"name": [module.strip().title()]}]
    elif ship:
        filters["ships"] = {"value": [ship.strip()]}
    else:
        raise SpanshError("Give a module or ship to search for.")
    body = {
        "filters": filters,
        "sort": [{"distance": {"direction": "asc"}}],
        "size": int(size),
        "page": 0,
        "reference_system": reference_system,
    }
    try:
        resp = requests.post(f"{BASE}/stations/search", json=body, headers=HEADERS, timeout=SUBMIT_TIMEOUT)
    except requests.RequestException as exc:
        raise SpanshError(f"Could not reach Spansh: {exc}") from exc
    if resp.status_code >= 400:
        raise SpanshError(_error_text(resp))
    return [
        {
            "station": s.get("name"),
            "system": s.get("system_name"),
            "distance": round(s.get("distance") or 0, 1),
            "dist_ls": s.get("distance_to_arrival"),
            "type": s.get("type"),
            "large_pad": bool(s.get("has_large_pad")),
            "updated_at": s.get("outfitting_updated_at") or s.get("shipyard_updated_at") or s.get("updated_at"),
        }
        for s in resp.json().get("results") or []
    ]


def material_traders(reference_system, kind, size=8, coords=None):
    """Return nearby Raw, Manufactured, or Encoded material traders."""
    if not reference_system and not (coords and len(coords) == 3):
        raise SpanshError("No reference system known yet.")
    body = {
        "filters": {"material_trader": {"value": [str(kind).title()]}},
        "sort": [{"distance": {"direction": "asc"}}],
        "size": int(size),
        "page": 0,
    }
    if reference_system:
        body["reference_system"] = reference_system
    else:
        body["reference_coords"] = {"x": coords[0], "y": coords[1], "z": coords[2]}
    try:
        resp = requests.post(f"{BASE}/stations/search", json=body, headers=HEADERS, timeout=SUBMIT_TIMEOUT)
        if resp.status_code >= 400 and coords and len(coords) == 3 and reference_system:
            body.pop("reference_system", None)
            body["reference_coords"] = {"x": coords[0], "y": coords[1], "z": coords[2]}
            resp = requests.post(f"{BASE}/stations/search", json=body, headers=HEADERS, timeout=SUBMIT_TIMEOUT)
    except requests.RequestException as exc:
        raise SpanshError(f"Could not reach Spansh: {exc}") from exc
    if resp.status_code >= 400:
        raise SpanshError(_error_text(resp))
    return [
        {
            "station": row.get("name"),
            "system": row.get("system_name"),
            "distance": round(row.get("distance") or 0, 1),
            "dist_ls": row.get("distance_to_arrival"),
            "large_pad": bool(row.get("has_large_pad")),
        }
        for row in resp.json().get("results") or []
    ]


def service_stations(reference_system, service, size=8, coords=None):
    """Return nearby stations offering a named service."""
    if not reference_system and not (coords and len(coords) == 3):
        raise SpanshError("No reference system known yet.")
    if not service:
        raise SpanshError("Enter a station service to search for.")
    body = {
        "filters": {"services": [{"name": [service]}]},
        "sort": [{"distance": {"direction": "asc"}}],
        "size": int(size), "page": 0,
    }
    if reference_system:
        body["reference_system"] = reference_system
    else:
        body["reference_coords"] = {"x": coords[0], "y": coords[1], "z": coords[2]}
    try:
        resp = requests.post(f"{BASE}/stations/search", json=body, headers=HEADERS, timeout=SUBMIT_TIMEOUT)
        if resp.status_code >= 400 and coords and len(coords) == 3 and reference_system:
            body.pop("reference_system", None)
            body["reference_coords"] = {"x": coords[0], "y": coords[1], "z": coords[2]}
            resp = requests.post(f"{BASE}/stations/search", json=body, headers=HEADERS, timeout=SUBMIT_TIMEOUT)
    except requests.RequestException as exc:
        raise SpanshError(f"Could not reach Spansh: {exc}") from exc
    if resp.status_code >= 400:
        raise SpanshError(_error_text(resp))
    return [{
        "station": row.get("name"), "system": row.get("system_name"),
        "distance": round(row.get("distance") or 0, 1),
        "dist_ls": row.get("distance_to_arrival"), "type": row.get("type"),
        "large_pad": bool(row.get("has_large_pad")), "updated_at": row.get("updated_at"),
        "carrier": (row.get("type") or "") == "Drake-Class Carrier",
    } for row in resp.json().get("results") or []]


def _error_text(resp):
    try:
        detail = resp.json().get("error")
    except ValueError:
        detail = None
    return f"Spansh error ({resp.status_code}): {detail or resp.text[:200]}"
