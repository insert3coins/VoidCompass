"""Online, request-driven trade searches backed by Ardent Insight.

Only the current station's Market.json is treated as local price evidence.
Galaxy-wide buyers and sellers are queried on demand and cached briefly in
memory by :mod:`trade.ardent`; no local galaxy market database is required.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import re

from colonisation_commodities import COMMODITY_NAME_MAPPING
from . import ardent, marketdb


class RouteError(RuntimeError):
    pass


_DISPLAY_TO_SYMBOL = {
    str(display).casefold(): symbol
    for symbol, display in COMMODITY_NAME_MAPPING.items()
}

_SURFACE_STATION_MARKERS = (
    "crater", "onfoot", "settlement", "surface", "planetary",
)


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


def _item_value(item, *names):
    for name in names:
        if name in item and item.get(name) is not None:
            return item.get(name)
    return None


def _row_updated_at(row):
    return marketdb.parse_update_time(_item_value(row, "updatedAt", "timestamp")) or 0


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


def is_surface_station(station_type):
    value = str(station_type or "").casefold().replace(" ", "")
    return any(marker in value for marker in _SURFACE_STATION_MARKERS)


def _station_allowed(row, *, requires_large_pad=False, include_carriers=False,
                     max_system_distance=None, orbital_only=False,
                     min_pad_size=0, surface_mode=None):
    if not include_carriers and _is_carrier(row):
        return False
    pad = _int(row.get("maxLandingPadSize"), 0)
    required_pad = max(3 if requires_large_pad else 0, _int(min_pad_size, 0))
    if required_pad and pad < required_pad:
        return False
    mode = str(surface_mode or ("exclude" if orbital_only else "include")).casefold()
    surface = is_surface_station(row.get("stationType"))
    if mode == "exclude" and surface:
        return False
    if mode == "only" and not surface:
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


def resolve_market_origin(system, station=None, *, max_price_age_days=30,
                          requires_large_pad=False, include_carriers=False,
                          orbital_only=False, min_pad_size=0,
                          surface_mode=None):
    """Resolve a typed station, or choose a supplied market when station is blank."""
    system_query = str(system or "").strip()
    station_query = str(station or "").strip()
    if not system_query:
        raise RouteError("Enter a start system or choose USE CURRENT.")
    try:
        if station_query:
            matches = ardent.search_stations(station_query)
            in_system = [
                row for row in matches
                if str(row.get("systemName") or "").casefold() == system_query.casefold()
            ]
            exact = [
                row for row in in_system
                if str(row.get("stationName") or "").casefold() == station_query.casefold()
            ]
            choices = exact or in_system
            if not choices:
                raise RouteError(
                    f"No station matching '{station_query}' was found in {system_query}."
                )
            if len(choices) > 1:
                names = ", ".join(str(row.get("stationName")) for row in choices[:4])
                raise RouteError(f"Station name is ambiguous in {system_query}: {names}.")
            selected = choices[0]
            canonical_system = str(selected.get("systemName") or system_query)
            market_id = _int(selected.get("marketId"))
            market_rows = ardent.market_commodities(canonical_system, market_id)
        else:
            canonical_system = system_query
            all_rows = ardent.market_commodities(canonical_system)
            grouped = {}
            for row in all_rows:
                market_id = _int(row.get("marketId"))
                if market_id:
                    grouped.setdefault(market_id, []).append(row)
            ranked = []
            cutoff = marketdb.now_epoch() - max(1, int(max_price_age_days)) * 86400
            for market_id, rows in grouped.items():
                first = rows[0]
                if not _station_allowed(
                    first, requires_large_pad=requires_large_pad,
                    include_carriers=include_carriers,
                    orbital_only=orbital_only, min_pad_size=min_pad_size,
                    surface_mode=surface_mode,
                ):
                    continue
                supplied = [
                    row for row in rows
                    if _int(row.get("buyPrice")) > 0
                    and _int(row.get("stock")) > 0
                    and _row_updated_at(row) >= cutoff
                ]
                if supplied:
                    ranked.append((
                        len(supplied),
                        sum(min(_int(r.get("stock")), 10000) for r in supplied),
                        first, rows,
                    ))
            if not ranked:
                raise RouteError(
                    f"No market with fresh commodity supply was found in {canonical_system}."
                )
            _count, _stock, selected, market_rows = max(
                ranked, key=lambda item: (item[0], item[1]),
            )
            market_id = _int(selected.get("marketId"))

        if not market_id:
            raise RouteError("The selected station has no usable market ID.")
        if not _station_allowed(
            selected, requires_large_pad=requires_large_pad,
            include_carriers=include_carriers,
            orbital_only=orbital_only, min_pad_size=min_pad_size,
            surface_mode=surface_mode,
        ):
            if requires_large_pad or _int(min_pad_size, 0):
                restriction = "the selected landing-pad size"
            elif str(surface_mode or "").casefold() in {"exclude", "only"} or orbital_only:
                restriction = "the selected surface-station policy"
            else:
                restriction = "the selected carrier filter"
            raise RouteError(f"{selected.get('stationName') or station_query} does not satisfy {restriction}.")

        cutoff = marketdb.now_epoch() - max(1, int(max_price_age_days)) * 86400
        fresh_rows = [
            row for row in market_rows
            if _row_updated_at(row) >= cutoff
            and _item_value(row, "commodityName", "Name", "Name_Localised")
        ]
        supplied_rows = [
            row for row in fresh_rows
            if _int(_item_value(row, "buyPrice", "BuyPrice")) > 0
            and _int(_item_value(row, "stock", "Stock")) > 0
        ]
        if not supplied_rows:
            raise RouteError(
                "That station has no buyable commodities within the selected quote age."
            )
        updated_values = [
            _row_updated_at(row)
            for row in fresh_rows
            if _row_updated_at(row)
        ]
        return {
            "market_id": market_id,
            "station": selected.get("stationName") or station_query,
            "system": selected.get("systemName") or canonical_system,
            "station_type": selected.get("stationType") or "",
            "dist_ls": _float(selected.get("distanceToArrival")),
            "large_pad": _int(selected.get("maxLandingPadSize")) >= 3,
            "timestamp": min(updated_values) if updated_values else None,
            "items": fresh_rows,
            "online": True,
            "auto_selected": not bool(station_query),
        }
    except ardent.ArdentError as exc:
        raise RouteError(str(exc)) from exc


def search_commodity(query, mode, system=None, star_pos=None, radius=50.0,
                     min_units=1, max_price_age_days=30,
                     requires_large_pad=False, include_carriers=True,
                     max_system_distance=None, orbital_only=False,
                     min_pad_size=0, surface_mode=None, limit=40):
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
            orbital_only=orbital_only, min_pad_size=min_pad_size,
            surface_mode=surface_mode,
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
               orbital_only=False, min_pad_size=0,
               surface_mode=None, limit=10):
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
                orbital_only=orbital_only, min_pad_size=min_pad_size,
                surface_mode=surface_mode,
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
                       orbital_only=False, min_pad_size=0,
                       surface_mode=None, source_updated_at=None,
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
        buy_price = _int(_item_value(item, "BuyPrice", "buyPrice"))
        stock = _int(_item_value(item, "Stock", "stock"))
        if buy_price <= 0 or stock < max(1, int(min_units)):
            continue
        source_updated = marketdb.parse_update_time(
            _item_value(item, "updatedAt", "timestamp")
        )
        if source_updated and (
            source_updated < marketdb.now_epoch() - max(1, int(max_price_age_days)) * 86400
        ):
            continue
        symbol = _resolve_symbol(
            _item_value(item, "Name", "Name_Localised", "commodityName"),
            report_index,
        )
        if not symbol:
            continue
        summary = report_index.get(_key(symbol), {})
        possible_margin = _int(summary.get("maxSellPrice")) - buy_price
        if summary and possible_margin < int(min_profit):
            continue
        sources.append({
            "symbol": symbol,
            "commodity": (
                item.get("Name_Localised")
                or COMMODITY_NAME_MAPPING.get(symbol)
                or symbol.replace("_", " ").title()
            ),
            "buy_price": buy_price,
            "supply": stock,
            "possible_margin": max(possible_margin, int(min_profit)),
            "updated_at": (
                source_updated
                or marketdb.parse_update_time(source_updated_at)
                or None
            ),
        })
    if not sources:
        return []

    # The daily catalogue cheaply identifies the most plausible departures;
    # cap fan-out so one click remains courteous to the community API.
    sources.sort(
        key=lambda row: row["possible_margin"] * min(row["supply"], 256),
        reverse=True,
    )
    sources = sources[:12]

    def find(source):
        return ardent.nearby_importers(
            system, source["symbol"], min_volume=max(1, int(min_units)),
            min_price=source["buy_price"] + max(1, int(min_profit)),
            max_distance=radius, max_days_ago=max_price_age_days,
            include_carriers=include_carriers,
        )

    query_results, errors = _parallel(sources, find, workers=6)
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
                orbital_only=orbital_only, min_pad_size=min_pad_size,
                surface_mode=surface_mode,
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
                "source_updated_at": source.get("updated_at"),
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


def find_system_market_routes(system, *, max_route_distance=80.0,
                              min_profit=1000, cargo_units=64,
                              min_supply=1, min_demand=1,
                              max_price_age_days=7, min_pad_size=0,
                              include_carriers=False, max_system_distance=None,
                              surface_mode="include", full_load=False,
                              round_trip=False, limit=75):
    """Search every eligible departure market in one exact star system."""
    system_name = str(system or "").strip()
    if not system_name:
        raise RouteError("Enter a departure system or leave it blank for galaxy-wide search.")
    max_route_distance = max(1.0, min(500.0, float(max_route_distance or 80.0)))
    min_profit = max(1, int(min_profit or 1))
    min_supply = max(1, int(min_supply or 1))
    min_demand = max(1, int(min_demand or 1))
    cargo_units = max(1, int(cargo_units or 1))
    cutoff = marketdb.now_epoch() - max(1, int(max_price_age_days)) * 86400
    try:
        report = ardent.commodities_report()
        all_market_rows = ardent.market_commodities(system_name)
    except ardent.ArdentError as exc:
        raise RouteError(str(exc)) from exc
    report_index = _report_index(report)

    markets = {}
    for item in all_market_rows:
        if not isinstance(item, dict):
            continue
        market_id = _int(item.get("marketId"))
        if market_id:
            markets.setdefault(market_id, []).append(item)

    sources = []
    eligible_markets = {}
    for market_id, items in markets.items():
        first = items[0]
        if not _station_allowed(
            first, include_carriers=include_carriers,
            max_system_distance=max_system_distance,
            min_pad_size=min_pad_size, surface_mode=surface_mode,
        ):
            continue
        eligible_markets[market_id] = items
        for item in items:
            buy_price = _int(item.get("buyPrice"))
            stock = _int(item.get("stock"))
            updated = _row_updated_at(item)
            if buy_price <= 0 or stock < min_supply or (updated and updated < cutoff):
                continue
            symbol = _resolve_symbol(item.get("commodityName"), report_index)
            if not symbol:
                continue
            summary = report_index.get(_key(symbol), {})
            possible_margin = _int(summary.get("maxSellPrice")) - buy_price
            if summary and possible_margin < min_profit:
                continue
            sources.append({
                "market_id": market_id,
                "station": first.get("stationName") or "Unknown station",
                "station_type": first.get("stationType") or "",
                "system": first.get("systemName") or system_name,
                "dist_ls": _float(first.get("distanceToArrival")),
                "symbol": symbol,
                "commodity": (
                    item.get("commodityName_Localised")
                    or COMMODITY_NAME_MAPPING.get(symbol)
                    or symbol.replace("_", " ").title()
                ),
                "buy_price": buy_price,
                "supply": stock,
                "updated_at": updated or None,
                "score": max(min_profit, possible_margin) * min(stock, cargo_units),
            })
    if not eligible_markets:
        raise RouteError(
            f"No market in {system_name} matches the selected pad, surface, carrier and station-distance filters."
        )
    if not sources:
        raise RouteError(
            f"Markets were found in {system_name}, but none has fresh commodity supply matching the filters."
        )

    # Query each promising commodity once for the system, then apply those
    # buyers to every departure station that actually sells it.
    symbol_scores = {}
    for source in sources:
        key = _key(source["symbol"])
        symbol_scores[key] = max(symbol_scores.get(key, 0), int(source["score"]))
    selected_keys = {
        key for key, _score in sorted(
            symbol_scores.items(), key=lambda item: item[1], reverse=True,
        )[:12]
    }
    sources = [source for source in sources if _key(source["symbol"]) in selected_keys]
    symbols = {}
    for source in sources:
        symbols.setdefault(_key(source["symbol"]), source["symbol"])

    def find_buyers(symbol):
        return ardent.nearby_importers(
            system_name, symbol,
            min_volume=min_demand,
            max_distance=max_route_distance,
            max_days_ago=max_price_age_days,
            include_carriers=include_carriers,
        )

    query_results, errors = _parallel(list(symbols.values()), find_buyers, workers=6)
    buyers_by_symbol = {
        _key(symbol): list(rows or []) for symbol, rows in query_results
    }
    opportunities = []
    seen = set()
    for source in sources:
        for destination in buyers_by_symbol.get(_key(source["symbol"]), []):
            if not isinstance(destination, dict):
                continue
            destination_market = _int(destination.get("marketId"))
            if destination_market == source["market_id"]:
                continue
            if not _station_allowed(
                destination, include_carriers=include_carriers,
                max_system_distance=max_system_distance,
                min_pad_size=min_pad_size, surface_mode=surface_mode,
            ):
                continue
            sell_price = _int(destination.get("sellPrice"))
            demand = _int(destination.get("demand"))
            profit_each = sell_price - source["buy_price"]
            units = min(cargo_units, source["supply"], demand)
            if profit_each < min_profit or demand < min_demand or units <= 0:
                continue
            if full_load and units < cargo_units:
                continue
            identity = (
                source["market_id"], destination_market,
                _key(source["symbol"]),
            )
            if identity in seen:
                continue
            seen.add(identity)
            station = _normalise_station(destination)
            opportunities.append({
                "from_market": source["market_id"],
                "from_station": source["station"],
                "from_system": source["system"],
                "from_dist_ls": source["dist_ls"],
                "from_type": source["station_type"],
                "to_market": destination_market,
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
                "source_updated_at": source["updated_at"],
                "updated_at": station["updated_at"],
            })
    if not opportunities and errors:
        raise RouteError(str(errors[0]))

    opportunities.sort(
        key=lambda row: -int(row.get("profit_each") or 0) * int(row.get("units") or 0)
    )
    if round_trip and opportunities:
        candidate_limit = min(len(opportunities), max(12, min(40, int(limit))))
        candidates = opportunities[:candidate_limit]
        grouped = {}
        for row in candidates:
            grouped.setdefault(_int(row.get("from_market")), []).append(row)
        loops = []
        for market_id, rows in grouped.items():
            loops.extend(attach_return_trades(
                rows, eligible_markets.get(market_id) or [],
                cargo_units=cargo_units, capital=None,
                max_price_age_days=max_price_age_days,
            ))
        opportunities = [
            row for row in loops
            if int(row.get("return_supply") or 0) >= min_supply
            and int(row.get("return_demand") or 0) >= min_demand
            and (not full_load or int(row.get("return_units") or 0) >= cargo_units)
        ]
        opportunities.sort(
            key=lambda row: -(
                int(row.get("profit_each") or 0) * int(row.get("units") or 0)
                + int(row.get("return_profit") or 0)
            )
        )
    return opportunities[: max(1, int(limit))]


def _station_coordinates(row):
    values = (row.get("systemX"), row.get("systemY"), row.get("systemZ"))
    try:
        return tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return None


def _market_distance(source, destination):
    left = _station_coordinates(source)
    right = _station_coordinates(destination)
    if left is None or right is None:
        return None
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def _route_commodity_candidates(report, min_profit, min_supply, min_demand, limit=10):
    candidates = []
    for item in report or []:
        if not isinstance(item, dict) or item.get("rare"):
            continue
        symbol = str(item.get("commodityName") or "").strip()
        buy = _int(item.get("minBuyPrice"))
        sell = _int(item.get("maxSellPrice"))
        stock = _int(item.get("totalStock"))
        demand = _int(item.get("totalDemand"))
        margin = sell - buy
        if (
            not symbol or buy <= 0 or margin < max(1, int(min_profit))
            or stock < max(1, int(min_supply))
            or demand < max(1, int(min_demand))
        ):
            continue
        # Potential margin finds good routes; a restrained volume term keeps
        # a one-off exotic quote from displacing consistently traded goods.
        volume_weight = math.log10(max(10, min(stock, demand)))
        candidates.append((margin * volume_weight, symbol))
    candidates.sort(reverse=True)
    return [symbol for _score, symbol in candidates[: max(1, int(limit))]]


def find_market_routes(reference_system=None, *, max_route_distance=80.0,
                       min_profit=1000, cargo_units=64,
                       min_supply=1, min_demand=1,
                       max_price_age_days=7, min_pad_size=0,
                       include_carriers=False, max_system_distance=1000.0,
                       surface_mode="include", full_load=False,
                       round_trip=False, limit=75):
    """Find real station pairs near a system, or galaxy-wide when blank.

    Unlike :func:`find_opportunities`, this does not require the commander to
    be docked at a source market. It pairs bounded, current Ardent exporter and
    importer results and therefore remains request-driven with no local galaxy
    market database.
    """
    reference_system = str(reference_system or "").strip()
    max_route_distance = max(1.0, min(500.0, float(max_route_distance or 80.0)))
    min_supply = max(1, int(min_supply or 1))
    min_demand = max(1, int(min_demand or 1))
    cargo_units = max(1, int(cargo_units or 1))
    min_profit = max(1, int(min_profit or 1))
    try:
        report = ardent.commodities_report()
    except ardent.ArdentError as exc:
        raise RouteError(str(exc)) from exc
    symbols = _route_commodity_candidates(
        report, min_profit, min_supply, min_demand, limit=10,
    )
    if not symbols:
        return []

    def load_markets(symbol):
        common = {
            "max_days_ago": max_price_age_days,
            "include_carriers": include_carriers,
        }
        if reference_system:
            exports = ardent.nearby_exporters(
                reference_system, symbol,
                min_volume=min_supply, max_distance=max_route_distance, **common,
            )
            imports = ardent.nearby_importers(
                reference_system, symbol,
                min_volume=min_demand, max_distance=max_route_distance, **common,
            )
        else:
            exports = ardent.global_exporters(
                symbol, min_volume=min_supply, **common,
            )
            imports = ardent.global_importers(
                symbol, min_volume=min_demand, **common,
            )
        return list(exports or []), list(imports or [])

    query_results, errors = _parallel(symbols, load_markets, workers=5)
    if not query_results and errors:
        raise RouteError(str(errors[0]))

    report_index = _report_index(report)
    market_exports = {}
    market_imports = {}
    opportunities = []
    seen = set()
    for symbol, pair in query_results:
        exports, imports = pair
        allowed_exports = [
            row for row in exports
            if isinstance(row, dict)
            and _int(row.get("buyPrice")) > 0
            and _int(row.get("stock")) >= min_supply
            and _station_allowed(
                row, include_carriers=include_carriers,
                max_system_distance=max_system_distance,
                min_pad_size=min_pad_size, surface_mode=surface_mode,
            )
        ]
        allowed_imports = [
            row for row in imports
            if isinstance(row, dict)
            and _int(row.get("sellPrice")) > 0
            and _int(row.get("demand")) >= min_demand
            and _station_allowed(
                row, include_carriers=include_carriers,
                max_system_distance=max_system_distance,
                min_pad_size=min_pad_size, surface_mode=surface_mode,
            )
        ]
        allowed_exports.sort(key=lambda row: _int(row.get("buyPrice")))
        allowed_imports.sort(key=lambda row: _int(row.get("sellPrice")), reverse=True)
        allowed_exports = allowed_exports[:60]
        allowed_imports = allowed_imports[:60]
        for row in allowed_exports:
            market_exports[(_int(row.get("marketId")), _key(symbol))] = row
        for row in allowed_imports:
            market_imports[(_int(row.get("marketId")), _key(symbol))] = row

        summary = report_index.get(_key(symbol), {})
        commodity = (
            COMMODITY_NAME_MAPPING.get(symbol)
            or str(summary.get("commodityName") or symbol).replace("_", " ").title()
        )
        for source in allowed_exports:
            source_market = _int(source.get("marketId"))
            buy_price = _int(source.get("buyPrice"))
            supply = _int(source.get("stock"))
            for destination in allowed_imports:
                destination_market = _int(destination.get("marketId"))
                if source_market and source_market == destination_market:
                    continue
                distance = _market_distance(source, destination)
                if distance is None or distance > max_route_distance:
                    continue
                sell_price = _int(destination.get("sellPrice"))
                demand = _int(destination.get("demand"))
                profit_each = sell_price - buy_price
                units = min(cargo_units, supply, demand)
                if profit_each < min_profit or units <= 0:
                    continue
                if full_load and units < cargo_units:
                    continue
                identity = (source_market, destination_market, _key(symbol))
                if identity in seen:
                    continue
                seen.add(identity)
                opportunities.append({
                    "from_market": source_market,
                    "from_station": source.get("stationName") or "Unknown station",
                    "from_system": source.get("systemName") or "Unknown system",
                    "from_dist_ls": _float(source.get("distanceToArrival")),
                    "from_type": source.get("stationType") or "",
                    "to_market": destination_market,
                    "to_station": destination.get("stationName") or "Unknown station",
                    "to_system": destination.get("systemName") or "Unknown system",
                    "to_dist_ls": _float(destination.get("distanceToArrival")),
                    "to_type": destination.get("stationType") or "",
                    "commodity": commodity,
                    "symbol": symbol,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "profit_each": profit_each,
                    "supply": supply,
                    "demand": demand,
                    "units": units,
                    "distance": distance,
                    "reference_distance": _float(source.get("distance")),
                    "source_updated_at": _row_updated_at(source) or None,
                    "updated_at": _row_updated_at(destination) or None,
                })

    if round_trip:
        outbound_candidates = list(opportunities)
        loops = []
        for row in opportunities:
            best = None
            source_market = _int(row.get("from_market"))
            destination_market = _int(row.get("to_market"))
            outbound_symbol = _key(row.get("symbol"))
            for symbol in symbols:
                symbol_key = _key(symbol)
                if symbol_key == outbound_symbol:
                    continue
                return_source = market_exports.get((destination_market, symbol_key))
                return_destination = market_imports.get((source_market, symbol_key))
                if not return_source or not return_destination:
                    continue
                buy_price = _int(return_source.get("buyPrice"))
                sell_price = _int(return_destination.get("sellPrice"))
                supply = _int(return_source.get("stock"))
                demand = _int(return_destination.get("demand"))
                margin = sell_price - buy_price
                units = min(cargo_units, supply, demand)
                if margin <= 0 or units <= 0 or (full_load and units < cargo_units):
                    continue
                profit = units * margin
                candidate = {
                    "return_symbol": symbol,
                    "return_commodity": symbol.replace("_", " ").title(),
                    "return_buy_price": buy_price,
                    "return_sell_price": sell_price,
                    "return_profit_each": margin,
                    "return_units": units,
                    "return_profit": profit,
                    "return_supply": supply,
                    "return_demand": demand,
                    "return_updated_at": min(
                        value for value in (
                            _row_updated_at(return_source),
                            _row_updated_at(return_destination),
                        ) if value
                    ) if (_row_updated_at(return_source) or _row_updated_at(return_destination)) else None,
                }
                if best is None or profit > int(best.get("return_profit") or 0):
                    best = candidate
            if best:
                row.update(best)
                loops.append(row)

        # Galaxy-wide top-price lists may not contain the reverse commodity at
        # both exact markets. Fill a bounded number of missing loops from the
        # two real station market snapshots rather than inventing a return leg.
        target_loops = min(12, max(3, int(limit)))
        if len(loops) < target_loops:
            existing = {
                (_int(row.get("from_market")), _int(row.get("to_market")), _key(row.get("symbol")))
                for row in loops
            }
            remaining = [
                row for row in outbound_candidates
                if (
                    _int(row.get("from_market")),
                    _int(row.get("to_market")),
                    _key(row.get("symbol")),
                ) not in existing
            ]
            remaining.sort(
                key=lambda row: -int(row.get("profit_each") or 0) * int(row.get("units") or 0)
            )

            def load_direct_return(row):
                source_items = ardent.market_commodities(
                    row.get("from_system"), row.get("from_market"),
                )
                enriched = attach_return_trades(
                    [row], source_items,
                    cargo_units=cargo_units, capital=None,
                    source_updated_at=row.get("source_updated_at"),
                    max_price_age_days=max_price_age_days,
                )
                return enriched[0] if enriched else None

            needed = target_loops - len(loops)
            direct_results, _direct_errors = _parallel(
                remaining[: max(needed * 2, 6)], load_direct_return, workers=4,
            )
            for _candidate, enriched in direct_results:
                if not enriched:
                    continue
                if (
                    int(enriched.get("return_supply") or 0) < min_supply
                    or int(enriched.get("return_demand") or 0) < min_demand
                    or (full_load and int(enriched.get("return_units") or 0) < cargo_units)
                ):
                    continue
                loops.append(enriched)
                if len(loops) >= target_loops:
                    break
        opportunities = loops

    opportunities.sort(
        key=lambda row: -(
            int(row.get("profit_each") or 0) * int(row.get("units") or 0)
            + int(row.get("return_profit") or 0)
        )
    )
    return opportunities[: max(1, int(limit))]


def attach_return_trades(opportunities, source_market_items, *, cargo_units=64,
                         capital=None, source_updated_at=None,
                         max_price_age_days=30):
    """Attach the best real commodity return leg to each outbound route.

    The outbound destination is queried for its current exports, while the
    selected departure market supplies the return demand.  This deliberately
    avoids inventing a symmetrical profit or using galaxy-wide extrema.
    """
    rows = [dict(row) for row in opportunities or [] if isinstance(row, dict)]
    if not rows:
        return []

    cutoff = marketdb.now_epoch() - max(1, int(max_price_age_days)) * 86400
    source_demands = {}
    for item in source_market_items or []:
        if not isinstance(item, dict):
            continue
        sell_price = _int(_item_value(item, "SellPrice", "sellPrice"))
        demand = _int(_item_value(item, "Demand", "demand"))
        updated = marketdb.parse_update_time(
            _item_value(item, "updatedAt", "timestamp")
        ) or marketdb.parse_update_time(source_updated_at) or None
        if sell_price <= 0 or demand <= 0 or (updated and updated < cutoff):
            continue
        symbol = _resolve_symbol(
            _item_value(item, "Name", "Name_Localised", "commodityName")
        )
        if not symbol:
            continue
        source_demands[_key(symbol)] = {
            "symbol": symbol,
            "commodity": (
                item.get("Name_Localised")
                or COMMODITY_NAME_MAPPING.get(symbol)
                or symbol.replace("_", " ").title()
            ),
            "sell_price": sell_price,
            "demand": demand,
            "updated_at": updated,
        }
    if not source_demands:
        return []

    destinations = {}
    for row in rows:
        market_id = _int(row.get("to_market"))
        system_name = str(row.get("to_system") or "").strip()
        if market_id and system_name:
            destinations.setdefault((system_name, market_id), None)

    def load_market(destination):
        system_name, market_id = destination
        return ardent.market_commodities(system_name, market_id)

    market_results, errors = _parallel(list(destinations), load_market, workers=4)
    for destination, market_rows in market_results:
        destinations[destination] = list(market_rows or [])
    if destinations and not any(value is not None for value in destinations.values()):
        if errors:
            raise RouteError(str(errors[0]))
        return []

    hold = max(1, int(cargo_units or 1))
    enriched = []
    for row in rows:
        market_rows = destinations.get((
            str(row.get("to_system") or "").strip(),
            _int(row.get("to_market")),
        ))
        if market_rows is None:
            continue
        available_capital = None
        if capital is not None:
            available_capital = max(
                0, int(capital) + int(row.get("projected_profit") or 0),
            )
        best = None
        outbound_key = _key(row.get("symbol"))
        for item in market_rows:
            if not isinstance(item, dict):
                continue
            buy_price = _int(_item_value(item, "BuyPrice", "buyPrice"))
            stock = _int(_item_value(item, "Stock", "stock"))
            updated = marketdb.parse_update_time(
                _item_value(item, "updatedAt", "timestamp")
            )
            if (
                buy_price <= 0 or stock <= 0
                or (updated and updated < cutoff)
            ):
                continue
            symbol = _resolve_symbol(
                _item_value(item, "Name", "Name_Localised", "commodityName")
            )
            demand = source_demands.get(_key(symbol))
            if not demand or _key(symbol) == outbound_key:
                continue
            margin = int(demand["sell_price"]) - buy_price
            if margin <= 0:
                continue
            affordable = hold
            if available_capital is not None:
                affordable = available_capital // buy_price
            units = min(hold, stock, int(demand["demand"]), affordable)
            if units <= 0:
                continue
            profit = units * margin
            candidate = {
                "return_symbol": symbol,
                "return_commodity": (
                    item.get("Name_Localised")
                    or demand.get("commodity")
                    or symbol.replace("_", " ").title()
                ),
                "return_buy_price": buy_price,
                "return_sell_price": int(demand["sell_price"]),
                "return_profit_each": margin,
                "return_units": units,
                "return_profit": profit,
                "return_supply": stock,
                "return_demand": int(demand["demand"]),
                "return_updated_at": min(
                    value for value in (updated, demand.get("updated_at")) if value
                ) if (updated or demand.get("updated_at")) else None,
            }
            if best is None or profit > int(best.get("return_profit") or 0):
                best = candidate
        if best:
            row.update(best)
            enriched.append(row)
    return enriched
