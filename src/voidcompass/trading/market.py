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


def _dump_pad(pads):
    pads = pads if isinstance(pads, dict) else {}
    return pad_size({"large_pads": pads.get("large"), "medium_pads": pads.get("medium"), "small_pads": pads.get("small")})


def parse_dump(reply):
    """A system's stations and markets (``spansh.system_dump``, 5.5.3.4) ->
    ``{"system", "id64", "stations": [...]}``, each station shaped like
    ``parse_station``, nearest the star first."""
    reply = reply or {}
    system = str(reply.get("name") or "")
    stations = []
    for row in reply.get("stations") or ():
        kind = str(row.get("type") or "")
        folded = kind.casefold()
        market = [{
            "name": item.get("name") or "", "category": item.get("category") or "",
            "buy": int(_num(item.get("buyPrice"))), "sell": int(_num(item.get("sellPrice"))),
            "supply": int(_num(item.get("supply"))), "demand": int(_num(item.get("demand"))),
        } for item in row.get("commodities") or () if item.get("name")]
        stations.append({
            "station": row.get("name") or "", "system": system, "market_id": row.get("id"),
            "distance": 0.0, "arrival_ls": _num(row.get("distanceToArrival"), None),
            "pad": _dump_pad(row.get("landingPads")),
            # Surface stations sit under a body in the dump.
            "planetary": bool(row.get("body")) or "planetary" in folded or "settlement" in folded,
            "carrier": "carrier" in folded, "type": kind, "body": row.get("body") or "",
            "updated": _ts(row.get("updateTime")),
            "market": sorted(market, key=lambda item: (item["category"], item["name"])),
        })
    stations.sort(key=lambda row: (row["arrival_ls"] is None, row["arrival_ls"] or 0.0, row["station"]))
    return {"system": system, "id64": reply.get("id64"), "stations": stations}


# Why a station in the system was not tried as a start, in the words shown.
LEFT_OUT = {
    "pad": "no large pad", "carrier": "fleet carriers", "planetary": "planetary",
    "old": "prices too old", "far": "too far from the star", "empty": "nothing in stock",
}


def start_candidates(stations, form, now, limit=3):
    """The stations in a system most worth starting a trade route from
    (5.5.3.4), within the route form's own rules (pad, carriers, planetary,
    price age, distance from the star), and how many each rule left out.

    A guess, not a promise: the one with the most goods in stock for a full
    hold leads, then the most goods in stock, then the freshest prices, then
    the nearest the star. Spansh's router then says what each is worth."""
    cargo = max(1, int(_num(form.get("max_cargo"), 1)))
    max_age = max(1, int(_num(form.get("max_price_age_days"), 3))) * 86400
    max_ls = _num(form.get("max_system_distance"), 0)
    left_out = {key: 0 for key in LEFT_OUT}
    picks = []
    for row in stations or ():
        if form.get("requires_large_pad") and row.get("pad") != "L":
            left_out["pad"] += 1
            continue
        if row.get("carrier") and not form.get("allow_player_owned"):
            left_out["carrier"] += 1
            continue
        if row.get("planetary") and not form.get("allow_planetary"):
            left_out["planetary"] += 1
            continue
        updated = row.get("updated")
        if updated is None or now - updated > max_age:
            left_out["old"] += 1
            continue
        if max_ls and row.get("arrival_ls") is not None and row["arrival_ls"] > max_ls:
            left_out["far"] += 1
            continue
        stocked = [item for item in row.get("market") or () if item["buy"] > 0 and item["supply"] > 0]
        if not stocked:
            left_out["empty"] += 1
            continue
        pick = {key: value for key, value in row.items() if key != "market"}
        pick.update(in_stock=len(stocked), full_hold=sum(1 for item in stocked if item["supply"] >= cargo))
        picks.append(pick)
    picks.sort(key=lambda row: (-row["full_hold"], -row["in_stock"], now - row["updated"],
                                row["arrival_ls"] if row["arrival_ls"] is not None else 1e12))
    return picks[:max(1, int(limit))], len(picks), {key: count for key, count in left_out.items() if count}


def in_system(rows, system, kind, limit=3):
    """What a system's own stations pay (``kind`` "sell") or charge ("buy")
    for a commodity, from rows of ``parse_commodity``: best price first."""
    wanted = str(system or "").casefold()
    here = [row for row in rows or () if str(row.get("system") or "").casefold() == wanted]
    here.sort(key=lambda row: row["price"], reverse=(kind == "sell"))
    return [{key: row.get(key) for key in ("station", "market_id", "price", "stock", "pad", "planetary", "updated")}
            for row in here[:limit]]


def price_ranges(reply):
    """``/api/stations/field_values/market`` -> {name: {"buy_max", "sell_max"}}:
    every commodity Spansh knows, and the best prices anywhere right now."""
    out = {}
    for name, ranges in ((reply or {}).get("min_max") or {}).items():
        ranges = ranges or {}
        out[name] = {"buy_min": _num((ranges.get("buy_price") or {}).get("min"), None),
                     "sell_max": _num((ranges.get("sell_price") or {}).get("max"), None)}
    return out
