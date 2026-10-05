"""Spansh's trade replies -> the compact rows the Trading tab shows.

Shapes (captured 2026-10-05; fixtures in tests/fixtures/spansh_trade/):

* trade router result: a list of hops, each ``source``/``destination``
  (station, system, market_id, distance_to_arrival, market_updated_at as
  epoch seconds), ``distance`` (ly), ``commodities`` (name, amount, profit
  per tonne, total_profit, ``source_commodity``/``destination_commodity``
  with buy/sell price, supply, demand) and ``cumulative_profit``.
* commodity buy/sell search, and one station: station records (name,
  system_name, distance, distance_to_arrival, pad counts, is_planetary, type,
  market_updated_at as ISO text) each with their whole ``market``.
"""

from __future__ import annotations

from datetime import datetime

from voidcompass.trading.commodities import fold


def _ts(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pad_size(record):
    if record.get("has_large_pad") or _num(record.get("large_pads")) > 0:
        return "L"
    if _num(record.get("medium_pads")) > 0:
        return "M"
    if _num(record.get("small_pads")) > 0:
        return "S"
    return ""


def _station(record):
    kind = str(record.get("type") or "")
    return {
        "station": record.get("name") or record.get("station") or "",
        "system": record.get("system_name") or record.get("system") or "",
        "market_id": record.get("market_id"),
        "distance": _num(record.get("distance"), None),
        "arrival_ls": _num(record.get("distance_to_arrival"), None),
        "pad": pad_size(record),
        "planetary": bool(record.get("is_planetary")),
        "carrier": "carrier" in kind.casefold(),
        "type": kind,
        "updated": _ts(record.get("market_updated_at")),
    }


def parse_route(result):
    """The trade router's result -> ``{"hops": [...], "profit", "distance"}``."""
    hops = []
    for row in result or ():
        if not isinstance(row, dict):
            continue
        goods = []
        for item in row.get("commodities") or ():
            source, target = item.get("source_commodity") or {}, item.get("destination_commodity") or {}
            goods.append({
                "name": item.get("name") or "", "amount": int(_num(item.get("amount"))),
                "buy": int(_num(source.get("buy_price"))), "sell": int(_num(target.get("sell_price"))),
                "profit": int(_num(item.get("profit"))), "total": int(_num(item.get("total_profit"))),
                "supply": int(_num(source.get("supply"))), "demand": int(_num(target.get("demand"))),
            })
        source, target = row.get("source") or {}, row.get("destination") or {}
        hops.append({
            "from": {"station": source.get("station") or "", "system": source.get("system") or "",
                     "market_id": source.get("market_id"), "arrival_ls": _num(source.get("distance_to_arrival"), None),
                     "updated": _ts(source.get("market_updated_at"))},
            "to": {"station": target.get("station") or "", "system": target.get("system") or "",
                   "market_id": target.get("market_id"), "arrival_ls": _num(target.get("distance_to_arrival"), None),
                   "updated": _ts(target.get("market_updated_at"))},
            "distance": _num(row.get("distance")), "goods": goods,
            "profit": int(_num(row.get("total_profit"))), "cumulative": int(_num(row.get("cumulative_profit"))),
        })
    return {"hops": hops, "profit": hops[-1]["cumulative"] if hops else 0,
            "distance": round(sum(hop["distance"] for hop in hops), 2)}


def _market_row(record, commodity):
    wanted = fold(commodity)
    return next((row for row in record.get("market") or () if fold(row.get("commodity")) == wanted), None)


def parse_commodity(reply, commodity, kind):
    """A commodity buy/sell search -> stations where it can really be bought
    (in stock) or sold (wanted), nearest first as Spansh sends them."""
    out = []
    for record in (reply or {}).get("results") or ():
        row = _market_row(record, commodity)
        if not row:
            continue
        if kind == "buy" and not (_num(row.get("buy_price")) > 0 and _num(row.get("supply")) > 0):
            continue
        if kind == "sell" and not (_num(row.get("sell_price")) > 0 and _num(row.get("demand")) > 0):
            continue
        out.append({**_station(record), "commodity": row.get("commodity") or commodity,
                    "price": int(_num(row.get("buy_price" if kind == "buy" else "sell_price"))),
                    "stock": int(_num(row.get("supply" if kind == "buy" else "demand")))})
    return out


def parse_station(reply):
    """One station (``/api/station/<market id>``) -> its details and market."""
    record = (reply or {}).get("record") or {}
    if not record:
        return None
    market = [{
        "name": row.get("commodity") or "", "category": row.get("category") or "",
        "buy": int(_num(row.get("buy_price"))), "sell": int(_num(row.get("sell_price"))),
        "supply": int(_num(row.get("supply"))), "demand": int(_num(row.get("demand"))),
    } for row in record.get("market") or () if row.get("commodity")]
    return {**_station(record), "market": sorted(market, key=lambda row: (row["category"], row["name"]))}


def best_leg(market_from, market_to, cargo, capital):
    """The most profitable commodity to carry from one station's market to
    another's, within cargo space, credits, stock and demand."""
    sells = {fold(row["name"]): row for row in market_to or () if row["sell"] > 0 and row["demand"] > 0}
    best = None
    for row in market_from or ():
        target = sells.get(fold(row["name"]))
        if not target or row["buy"] <= 0 or row["supply"] <= 0:
            continue
        per_t = target["sell"] - row["buy"]
        amount = min(int(cargo or 0), row["supply"], target["demand"], int((capital or 0) // row["buy"]))
        if per_t <= 0 or amount <= 0:
            continue
        leg = {"name": row["name"], "amount": amount, "buy": row["buy"], "sell": target["sell"],
               "profit": per_t, "total": per_t * amount, "supply": row["supply"], "demand": target["demand"]}
        if best is None or leg["total"] > best["total"]:
            best = leg
    return best


def loop_route(station_a, station_b, cargo, capital):
    """A → B → A between two stations (parse_station results): the best cargo
    each way, from both markets as Spansh has them."""
    out = {"a": {key: station_a.get(key) for key in ("station", "system", "market_id", "updated")},
           "b": {key: station_b.get(key) for key in ("station", "system", "market_id", "updated")},
           "out": best_leg(station_a.get("market"), station_b.get("market"), cargo, capital),
           "back": best_leg(station_b.get("market"), station_a.get("market"), cargo, capital)}
    out["profit"] = sum(leg["total"] for leg in (out["out"], out["back"]) if leg)
    return out


def price_ranges(reply):
    """``/api/stations/field_values/market`` -> {name: {"buy_max", "sell_max"}}:
    every commodity Spansh knows, and the best prices anywhere right now."""
    out = {}
    for name, ranges in ((reply or {}).get("min_max") or {}).items():
        ranges = ranges or {}
        out[name] = {"buy_min": _num((ranges.get("buy_price") or {}).get("min"), None),
                     "sell_max": _num((ranges.get("sell_price") or {}).get("max"), None)}
    return out
