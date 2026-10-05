"""Following a planned trade route, live from the journal.

A route (market.parse_route) is followed hop by hop: buy the hop's goods at
its source station, fly, sell them at its destination, which is the next
hop's source. MarketBuy and MarketSell at the right stations tick it along;
nothing is assumed. The state is a plain dict kept in trading.db (kv
"route"), so it survives a restart."""

from __future__ import annotations

from voidcompass.trading.commodities import fold


def start(plan, form=None, planned_at=None):
    return {"plan": plan, "form": dict(form or {}), "planned_at": planned_at, "hop": 0, "phase": "buy",
            "bought": {}, "sold": {}, "profit": 0, "done": not plan.get("hops"), "docked_at": None, "warnings": []}


def _hop(state):
    hops = state["plan"].get("hops") or []
    return hops[state["hop"]] if 0 <= state["hop"] < len(hops) else None


def _goods(hop):
    return {fold(item["name"]): item for item in hop.get("goods") or ()}


def observe(state, raw, names):
    """Advance ``state`` from one journal event; True when it changed.
    ``names`` (CommodityNames) turns journal symbols into route names."""
    if not state or state.get("done") or not isinstance(raw, dict):
        return False
    hop = _hop(state)
    if hop is None:
        return False
    event = raw.get("event")
    market_id = raw.get("MarketID")
    if event == "Docked":
        state["docked_at"] = market_id
        return True
    if event == "Undocked":
        state["docked_at"] = None
        return True
    if event not in ("MarketBuy", "MarketSell"):
        return False
    goods = _goods(hop)
    key = fold(names.name(raw.get("Type")))
    if key not in goods:
        return False
    count = int(raw.get("Count") or 0)
    if event == "MarketBuy" and market_id == hop["from"]["market_id"]:
        state["bought"][key] = state["bought"].get(key, 0) + count
        state["phase"] = "sell"
        return True
    if event == "MarketSell" and market_id == hop["to"]["market_id"]:
        state["sold"][key] = state["sold"].get(key, 0) + count
        paid = int(raw.get("AvgPricePaid") or 0)
        if paid > 0:
            state["profit"] += int(raw.get("TotalSale") or 0) - paid * count
        if all(state["sold"].get(name, 0) >= state["bought"].get(name, 0) for name in state["bought"]):
            _advance(state)
        return True
    return False


def _advance(state):
    state["hop"] += 1
    state["phase"] = "buy"
    state["bought"], state["sold"], state["warnings"] = {}, {}, []
    if _hop(state) is None:
        state["done"] = True


def skip(state):
    """The commander moved on without trading this hop."""
    if state and not state.get("done"):
        _advance(state)


def next_step(state):
    """What to do now, for the tab and the overlay."""
    if not state:
        return None
    hops = state["plan"].get("hops") or []
    if state.get("done"):
        return {"done": True, "text": "Route complete", "profit": state["profit"], "hops": len(hops)}
    hop = _hop(state)
    goods = hop.get("goods") or []
    if state["phase"] == "buy":
        station, system = hop["from"]["station"], hop["from"]["system"]
        action = "Buy " + ", ".join(f"{item['amount']:,} t {item['name']}" for item in goods)
        here = state.get("docked_at") == hop["from"]["market_id"]
    else:
        station, system = hop["to"]["station"], hop["to"]["system"]
        action = "Sell " + ", ".join(item["name"] for item in goods)
        here = state.get("docked_at") == hop["to"]["market_id"]
    return {"done": False, "hop": state["hop"] + 1, "hops": len(hops), "phase": state["phase"], "action": action,
            "station": station, "system": system, "here": here, "distance": hop["distance"],
            "expected": hop["profit"], "profit": state["profit"],
            "market_id": hop["from"]["market_id"] if state["phase"] == "buy" else hop["to"]["market_id"],
            "warnings": list(state.get("warnings") or ())}


def check_prices(state, station):
    """Compare the hop's planned prices with the station's market now (a
    parse_station result); returns the warnings it set."""
    hop = _hop(state) if state else None
    if not hop or not station:
        return []
    market = {fold(row["name"]): row for row in station.get("market") or ()}
    warnings = []
    for item in hop.get("goods") or ():
        row = market.get(fold(item["name"]))
        planned, field = (item["buy"], "buy") if state["phase"] == "buy" else (item["sell"], "sell")
        if row is None or not planned:
            continue
        now = row[field]
        if field == "buy" and (row["supply"] <= 0 or now <= 0):
            warnings.append(f"{item['name']} is no longer sold here.")
            continue
        if field == "sell" and (row["demand"] <= 0 or now <= 0):
            warnings.append(f"{item['name']} is no longer wanted here.")
            continue
        change = (now - planned) / planned
        worse = change > 0.05 if field == "buy" else change < -0.05
        if worse:
            warnings.append(f"{item['name']} now {'costs' if field == 'buy' else 'sells for'} {now:,} CR "
                            f"(planned {planned:,}, {change:+.0%}).")
    state["warnings"] = warnings
    return warnings
