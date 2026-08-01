"""Small, bounded client for Ardent Insight's public Elite market API.

Trade searches are deliberately request-driven: no galaxy dump is downloaded
and no remote quote catalogue is persisted.  A short in-memory cache prevents
repeat clicks and shared colony searches from needlessly repeating requests.
"""

from __future__ import annotations

from collections import OrderedDict
import os
import threading
import time
from urllib.parse import quote

import requests

from version import APP_VERSION


BASE_URL = os.environ.get("VC_ARDENT_API_URL", "https://api.ardent-insight.com/v2").rstrip("/")
USER_AGENT = f"VoidCompass/{APP_VERSION}"
CONNECT_TIMEOUT_S = 4
READ_TIMEOUT_S = 22
CACHE_TTL_S = 10 * 60
STATUS_TTL_S = 5 * 60
REPORT_TTL_S = 60 * 60
MAX_CACHE_ENTRIES = 96
MAX_NEARBY_ROWS = 250


class ArdentError(RuntimeError):
    """A concise, user-safe online market error."""


_lock = threading.Lock()
_cache = OrderedDict()
_cache_hits = 0
_cache_misses = 0
_last_success_at = None
_last_error = None


def _cache_key(path, params):
    pairs = tuple(sorted((str(key), str(value)) for key, value in (params or {}).items()))
    return path, pairs


def _cached(key):
    global _cache_hits
    now = time.monotonic()
    with _lock:
        item = _cache.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= now:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        _cache_hits += 1
        return value


def _remember(key, value, ttl_s):
    with _lock:
        _cache[key] = (time.monotonic() + max(1, int(ttl_s)), value)
        _cache.move_to_end(key)
        while len(_cache) > MAX_CACHE_ENTRIES:
            _cache.popitem(last=False)


def _request(path, params=None, *, ttl_s=CACHE_TTL_S, force=False, row_limit=None):
    global _cache_misses, _last_success_at, _last_error
    key = _cache_key(path, params)
    if not force:
        value = _cached(key)
        if value is not None:
            return value
    with _lock:
        _cache_misses += 1
    try:
        response = requests.get(
            f"{BASE_URL}{path}",
            params=params or None,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
        )
        response.raise_for_status()
        value = response.json()
        if row_limit is not None and isinstance(value, list):
            value = value[: max(1, int(row_limit))]
    except requests.Timeout as exc:
        message = "Online market service timed out; try the search again shortly."
        with _lock:
            _last_error = message
        raise ArdentError(message) from exc
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        message = (
            f"Online market service returned HTTP {status}."
            if status else "Online market service is unavailable; check the internet connection."
        )
        with _lock:
            _last_error = message
        raise ArdentError(message) from exc
    except (TypeError, ValueError) as exc:
        message = "Online market service returned data VoidCompass could not read."
        with _lock:
            _last_error = message
        raise ArdentError(message) from exc

    with _lock:
        _last_success_at = int(time.time())
        _last_error = None
    _remember(key, value, ttl_s)
    return value


def service_status(*, force=False):
    """Return provider health plus lightweight cache diagnostics."""
    try:
        payload = _request("/version", ttl_s=STATUS_TTL_S, force=force)
        version = str((payload or {}).get("version") or "online") if isinstance(payload, dict) else "online"
        online = True
        error = None
    except ArdentError as exc:
        version = None
        online = False
        error = str(exc)
    with _lock:
        return {
            "online": online,
            "version": version,
            "cache_entries": len(_cache),
            "cache_hits": _cache_hits,
            "cache_misses": _cache_misses,
            "last_success_at": _last_success_at,
            "last_error": error or _last_error,
        }


def commodities_report():
    payload = _request("/commodities", ttl_s=REPORT_TTL_S)
    if not isinstance(payload, list):
        raise ArdentError("Online market service returned an invalid commodity catalogue.")
    return payload


def _nearby(system, commodity, direction, *, min_volume=1, min_price=None,
            max_price=None, max_distance=80, max_days_ago=30,
            include_carriers=False):
    system_name = str(system or "").strip()
    commodity_name = str(commodity or "").strip()
    if not system_name:
        raise ArdentError("Current system is not known yet.")
    if not commodity_name:
        raise ArdentError("Commodity name is missing.")
    if direction not in ("imports", "exports"):
        raise ValueError("direction must be imports or exports")
    params = {
        "minVolume": max(1, int(min_volume or 1)),
        "maxDistance": max(1, min(500, int(float(max_distance or 80)))),
        "maxDaysAgo": max(1, int(float(max_days_ago or 30))),
        "fleetCarriers": "true" if include_carriers else "false",
    }
    if min_price is not None:
        params["minPrice"] = max(1, int(min_price))
    if max_price is not None:
        params["maxPrice"] = max(1, int(max_price))
    path = (
        f"/system/name/{quote(system_name, safe='')}/commodity/name/"
        f"{quote(commodity_name, safe='')}/nearby/{direction}"
    )
    payload = _request(path, params=params, row_limit=MAX_NEARBY_ROWS)
    if not isinstance(payload, list):
        raise ArdentError("Online market service returned an invalid nearby-market result.")
    return payload


def nearby_importers(system, commodity, **filters):
    return _nearby(system, commodity, "imports", **filters)


def nearby_exporters(system, commodity, **filters):
    return _nearby(system, commodity, "exports", **filters)


def clear_cache():
    with _lock:
        _cache.clear()
