"""Online, request-driven trade searches backed by Ardent Insight.

Only the current station's Market.json is treated as local price evidence.
Galaxy-wide buyers and sellers are queried on demand and cached briefly in
memory by :mod:`trade.ardent`; no local galaxy market database is required.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re

from colonisation_commodities import COMMODITY_NAME_MAPPING
from . import ardent, marketdb


class RouteError(RuntimeError):
    pass


_DISPLAY_TO_SYMBOL = {
    str(display).casefold(): symbol
    for symbol, display in COMMODITY_NAME_MAPPING.items()
}


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _raw_symbol(value):
    text = str(value or "").strip()
    if text.startswith("$") and text.endswith(";"):
        text = text[1:-1]
    lowered = text.casefold()
    for suffix in ("_name_localised", "_name"):
        if lowered.endswith(suffix):
            lowered = lowered[: -len(suffix)]
            break
    return lowered


def _report_index(report):
    result = {}
    for item in report or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("commodityName") or "").strip()
        if name:
            result[_key(name)] = item
    return result


def _resolve_symbol(value, report_index=None):
    raw = _raw_symbol(value)
    raw_key = _key(raw)
    if report_index and raw_key in report_index:
        return str(report_index[raw_key].get("commodityName") or raw)
    special = _DISPLAY_TO_SYMBOL.get(str(value or "").strip().casefold())
    if special:
        return special
    return raw_key


def _is_carrier(row):
    station_type = str(row.get("stationType") or "").casefold()
    return "carrier" in station_type or marketdb.is_carrier(
        row.get("stationType"), row.get("stationName")
    )


def _station_allowed(row, *, requires_large_pad=False, include_carriers=False,
                     max_system_distance=None):
    if not include_carriers and _is_carrier(row):
        return False
    pad = _int(row.get("maxLandingPadSize"), 0)
    if requires_large_pad and pad < 3:
        return False
    dist_ls = _float(row.get("distanceToArrival"))
    if dist_ls is None and _is_carrier(row):
        dist_ls = 0.0
    if max_system_distance is not None:
        limit = max(0.0, float(max_system_distance))
        if dist_ls is None or dist_ls > limit:
            return False
    return True


def _normalise_station(row):
    dist_ls = _float(row.get("distanceToArrival"))
    if dist_ls is None and _is_carrier(row):
        dist_ls = 0.0
    return {
        "market_id": _int(row.get("marketId")),
        "station": row.get("stationName") or "Unknown station",
        "system": row.get("systemName") or "Unknown system",
        "type": row.get("stationType") or "",
        "distance": max(0.0, _float(row.get("distance"), 0.0) or 0.0),
        "dist_ls": dist_ls,
        "large_pad": _int(row.get("maxLandingPadSize"), 0) >= 3,
        "updated_at": marketdb.parse_update_time(row.get("updatedAt")),
    }


def _parallel(items, function, workers=4):
    if not items:
        return [], []
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        futures = {pool.submit(function, item): item for item in items}
        for future in as_completed(futures):
            try:
                results.append((futures[future], future.result()))
            except Exception as exc:
                errors.append(exc)
    return results, errors


def list_commodities():
    rows = []
    for item in ardent.commodities_report():
        symbol = str(item.get("commodityName") or "").strip()
        if symbol:
            rows.append({"symbol": symbol, "name": symbol.replace("_", " ").title(), "category": ""})
    return sorted(rows, key=lambda row: row["name"].casefold())


def search_commodity(query, mode, system=None, star_pos=None, radius=50.0,
                     min_units=1, max_price_age_days=30,
                     requires_large_pad=False, include_carriers=True,
                     max_system_distance=None, limit=40):
    del star_pos
    if mode not in ("buy", "sell"):
        raise RouteError("mode must be 'buy' or 'sell'.")
    try:
        report = ardent.commodities_report()
        symbol = _resolve_symbol(query, _report_index(report))
        finder = ardent.nearby_exporters if mode == "buy" else ardent.nearby_importers
        rows = finder(
            system, symbol,
            min_volume=max(1, int(min_units)),
            max_distance=radius,
            max_days_ago=max_price_age_days,
            include_carriers=include_carriers,
        )
    except ardent.ArdentError as exc:
        raise RouteError(str(exc)) from exc

    results = []
    for row in rows:
        if not _station_allowed(
            row, requires_large_pad=requires_large_pad,
            include_carriers=include_carriers,
            max_system_distance=max_system_distance,
        ):
            continue
        station = _normalise_station(row)
        station.update({
            "buy_price": _int(row.get("buyPrice")),
            "sell_price": _int(row.get("sellPrice")),
            "supply": _int(row.get("stock")),
            "demand": _int(row.get("demand")),
        })
        if mode == "buy" and (station["buy_price"] <= 0 or station["supply"] < min_units):
            continue
        if mode == "sell" and (station["sell_price"] <= 0 or station["demand"] < min_units):
            continue
        results.append(station)
    results.sort(key=lambda row: row["buy_price"] if mode == "buy" else -row["sell_price"])
    return {
        "commodity": str(query or symbol),
        "symbol": symbol,
        "results": results[: max(1, int(limit))],
    }


def sell_cargo(cargo_items, system=None, star_pos=None, radius=80.0,
               max_price_age_days=30, requires_large_pad=False,
               include_carriers=False, max_system_distance=1000.0,
               limit=10):
    del star_pos
    try:
        report_index = _report_index(ardent.commodities_report())
    except ardent.ArdentError:
        report_index = {}

    cargo_by_symbol = {}
    for item in cargo_items or []:
        if not isinstance(item, dict):
            continue
        units = _int(item.get("Count") or item.get("count"))
        symbol = _resolve_symbol(
            item.get("Name") or item.get("name") or item.get("Name_Localised"),
            report_index,
        )
        if units > 0 and symbol:
            cargo_row = cargo_by_symbol.setdefault(symbol, {
                "symbol": symbol,
                "name": item.get("Name_Localised") or item.get("name") or symbol.replace("_", " ").title(),
                "units": 0,
            })
            cargo_row["units"] += units
    cargo = list(cargo_by_symbol.values())
    if not cargo:
        return []

    def find(item):
        return ardent.nearby_importers(
            system, item["symbol"], min_volume=1,
            max_distance=radius, max_days_ago=max_price_age_days,
            include_carriers=include_carriers,
        )

    query_results, errors = _parallel(cargo, find)
    destinations = {}
    for item, rows in query_results:
        for row in rows:
            if not _station_allowed(
                row, requires_large_pad=requires_large_pad,
                include_carriers=include_carriers,
                max_system_distance=max_system_distance,
            ):
                continue
            price = _int(row.get("sellPrice"))
            demand = _int(row.get("demand"))
            if price <= 0 or demand <= 0:
                continue
            station = _normalise_station(row)
            key = station["market_id"] or (station["system"], station["station"])
            result = destinations.setdefault(key, dict(station, total=0, items=[]))
            units = min(item["units"], demand)
            payout = units * price
            result["items"].append({
                "symbol": item["symbol"], "name": item["name"],
                "units": units, "sell_price": price, "demand": demand,
                "payout": payout,
            })
            result["total"] += payout
            updated = station.get("updated_at")
            if updated and (not result.get("updated_at") or updated < result["updated_at"]):
                result["updated_at"] = updated
    if not destinations and errors:
        raise RouteError(str(errors[0]))
    ranked = sorted(
        destinations.values(),
        key=lambda row: (-int(row.get("total") or 0), float(row.get("distance") or 0)),
    )
    return ranked[: max(1, int(limit))]


def find_opportunities(system=None, star_pos=None, radius=80.0,
                       min_profit=1000, min_units=1,
                       max_price_age_days=30, requires_large_pad=False,
                       include_carriers=False, max_system_distance=1000.0,
                       source_market_id=None, source_station=None,
                       market_items=None, limit=18):
    del star_pos
    try:
        report = ardent.commodities_report()
    except ardent.ArdentError as exc:
        raise RouteError(str(exc)) from exc
    report_index = _report_index(report)

    sources = []
    for item in market_items or []:
        if not isinstance(item, dict):
            continue
        buy_price = _int(item.get("BuyPrice"))
        stock = _int(item.get("Stock"))
        if buy_price <= 0 or stock < max(1, int(min_units)):
            continue
        symbol = _resolve_symbol(item.get("Name") or item.get("Name_Localised"), report_index)
        if not symbol:
            continue
        summary = report_index.get(_key(symbol), {})
        possible_margin = _int(summary.get("maxSellPrice")) - buy_price
        if summary and possible_margin < int(min_profit):
            continue
        sources.append({
            "symbol": symbol,
            "commodity": item.get("Name_Localised") or symbol.replace("_", " ").title(),
            "buy_price": buy_price,
            "supply": stock,
            "possible_margin": max(possible_margin, int(min_profit)),
        })
    if not sources:
        return []

    # The daily catalogue cheaply identifies the most plausible departures;
    # cap fan-out so one click remains courteous to the community API.
    sources.sort(
        key=lambda row: row["possible_margin"] * min(row["supply"], 256),
        reverse=True,
    )
    sources = sources[:16]

    def find(source):
        return ardent.nearby_importers(
            system, source["symbol"], min_volume=max(1, int(min_units)),
            min_price=source["buy_price"] + max(1, int(min_profit)),
            max_distance=radius, max_days_ago=max_price_age_days,
            include_carriers=include_carriers,
        )

    query_results, errors = _parallel(sources, find)
    opportunities = []
    seen = set()
    for source, rows in query_results:
        for row in rows:
            market_id = _int(row.get("marketId"))
            if source_market_id and market_id == _int(source_market_id):
                continue
            if not _station_allowed(
                row, requires_large_pad=requires_large_pad,
                include_carriers=include_carriers,
                max_system_distance=max_system_distance,
            ):
                continue
            sell_price = _int(row.get("sellPrice"))
            demand = _int(row.get("demand"))
            profit_each = sell_price - source["buy_price"]
            units = min(source["supply"], demand)
            if profit_each < int(min_profit) or units < max(1, int(min_units)):
                continue
            key = (source["symbol"], market_id or row.get("stationName"), row.get("systemName"))
            if key in seen:
                continue
            seen.add(key)
            station = _normalise_station(row)
            opportunities.append({
                "from_market": _int(source_market_id),
                "from_station": source_station or "Current market",
                "from_system": system,
                "to_market": market_id,
                "to_station": station["station"],
                "to_system": station["system"],
                "to_dist_ls": station["dist_ls"],
                "to_type": station["type"],
                "commodity": source["commodity"],
                "symbol": source["symbol"],
                "buy_price": source["buy_price"],
                "sell_price": sell_price,
                "profit_each": profit_each,
                "supply": source["supply"],
                "demand": demand,
                "units": units,
                "distance": station["distance"],
                "updated_at": station["updated_at"],
            })
    if not opportunities and errors:
        raise RouteError(str(errors[0]))
    opportunities.sort(
        key=lambda row: (
            -(int(row["profit_each"]) * int(row["units"])),
            float(row.get("distance") or 0),
        )
    )
    return opportunities[: max(1, int(limit))]
