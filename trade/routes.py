"""Local trade-route planner over the market database: the same feature the
Spansh/Inara planners provide, computed offline against EDDN-fresh prices.

Beam search: each hop is buy-at-source -> sell-at-destination; destinations
must lie within max_hop_distance ly of the source system. Cargo is filled
greedily with the most profitable commodities (respecting supply, demand and
capital), and the best few partial routes are extended each round."""

import math
import threading
import time
from collections import OrderedDict

from . import marketdb

BEAM_WIDTH = 6
DESTS_PER_HOP = 5
MAX_COMMODITIES_PER_HOP = 3
MAX_SOURCE_CANDIDATES = 8
MAX_SOURCE_POOL = 60
MAX_DEST_CANDIDATES = 250
PAIR_QUERY_LIMIT = 600

# Dense inhabited regions can have many hundreds of stations inside the
# default radius.  The commodity flow join grows roughly with the square of
# this pool, so 900 candidates made otherwise valid searches (for example,
# Deciat at 100 ly) appear hung for tens of seconds.  The nearest 400 keeps a
# broad search area while bounding the expensive pair ranking.
LOOP_STATION_CAP = 400       # nearest stations considered in loop mode
LOOP_FLOW_LIMIT = 30000      # top commodity flows pulled from SQL
LOOP_FLOWS_PER_PAIR = 12
LOOP_RESULTS = 8
LOOP_CANDIDATES = 250        # loops kept for time-weighted ranking
NEAR_CACHE_TTL_S = 90.0
NEAR_CACHE_MAX = 24

# Travel-time model for profit/hour (rough but consistent across candidates).
JUMP_TIME_S = 50.0           # one hyperspace jump incl. align/scoop average
DOCK_OVERHEAD_S = 180.0      # request dock, land, trade, launch
SC_BASE_S = 60.0             # drop from jump + initial acceleration
UNKNOWN_DIST_LS = 500.0      # assumed when a station's star distance is unknown

_near_cache = OrderedDict()
_near_cache_lock = threading.Lock()


def _supercruise_time_s(dist_ls):
    ls = dist_ls if dist_ls and dist_ls > 0 else UNKNOWN_DIST_LS
    return SC_BASE_S + 170.0 * (ls / 1000.0) ** 0.35


def _leg_time_s(distance_ly, dest_dist_ls, jump_range):
    jumps = math.ceil(distance_ly / max(1.0, jump_range)) if distance_ly > 0.01 else 0
    return jumps * JUMP_TIME_S + _supercruise_time_s(dest_dist_ls) + DOCK_OVERHEAD_S


FRESHNESS_HALF_LIFE_DAYS = 7.0


def _freshness_factor(updated_at):
    """Ranking weight for price age: 1.0 now, 0.5 at one week, ~0.06 at a
    month. Displayed prices/profits stay raw — this only orders candidates so
    an hour-old quote outranks a marginally better month-old one."""
    if not updated_at:
        return 0.5
    age_days = max(0.0, (marketdb.now_epoch() - int(updated_at)) / 86400.0)
    return 0.5 ** (age_days / FRESHNESS_HALF_LIFE_DAYS)


def _load_temp_ids(conn, ids):
    """Stage station ids in a per-connection temp table so queries can say
    `market_id IN (SELECT market_id FROM temp.near_ids)` instead of building
    unbounded ?-placeholder lists — SQLite builds compiled with the old
    999-variable limit crash on wide-radius searches otherwise."""
    conn.execute("DROP TABLE IF EXISTS temp.near_ids")
    conn.execute("CREATE TEMP TABLE near_ids(market_id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT OR IGNORE INTO temp.near_ids VALUES(?)", ((i,) for i in ids))


class RouteError(Exception):
    pass


def _near_cache_key(start, radius, max_price_age_days, requires_large_pad, include_carriers, max_system_distance):
    # Bucket the time-based freshness cutoff so repeated searches reuse work,
    # while still refreshing often enough for EDDN/live journal updates.
    return (
        int(start.get("id64") or 0),
        round(float(start["x"]), 3),
        round(float(start["y"]), 3),
        round(float(start["z"]), 3),
        round(float(radius), 2),
        int(max_price_age_days),
        bool(requires_large_pad),
        bool(include_carriers),
        round(float(max_system_distance), 2) if max_system_distance else None,
        int(time.time() // 300),
    )


def _nearby_station_pool(
    conn,
    start,
    radius,
    max_price_age_days,
    requires_large_pad=False,
    include_carriers=True,
    max_system_distance=None,
    cap=None,
):
    key = _near_cache_key(start, radius, max_price_age_days, requires_large_pad, include_carriers, max_system_distance)
    now = time.monotonic()
    with _near_cache_lock:
        cached = _near_cache.get(key)
        if cached and now - cached[0] < NEAR_CACHE_TTL_S:
            _near_cache.move_to_end(key)
            stations = cached[1]
            return list(stations[:cap]) if cap else list(stations)

    stations = marketdb.stations_near(
        conn,
        start["x"],
        start["y"],
        start["z"],
        float(radius),
        min_updated=marketdb.now_epoch() - int(max_price_age_days) * 86400,
        require_large_pad=bool(requires_large_pad),
        max_dist_ls=float(max_system_distance) if max_system_distance else None,
    )
    stations = _filter_carriers(stations, include_carriers)
    stations.sort(key=lambda s: _dist(start, s))

    with _near_cache_lock:
        _near_cache[key] = (now, tuple(stations))
        while len(_near_cache) > NEAR_CACHE_MAX:
            _near_cache.popitem(last=False)
    return stations[:cap] if cap else stations


def plan_route_local(
    system,
    station=None,
    star_pos=None,
    capital=100000,
    max_cargo=8,
    max_hop_distance=25.0,
    max_hops=4,
    max_system_distance=1000,
    max_price_age_days=30,
    requires_large_pad=False,
    include_carriers=True,
    min_supply=1,
    jump_range=20.0,
):
    conn = marketdb.connect()
    try:
        if not marketdb.is_ready(conn):
            raise RouteError("Local market database is empty - build it from the Market Database panel first.")

        start = _resolve_start(conn, system, star_pos)
        min_updated = marketdb.now_epoch() - int(max_price_age_days) * 86400
        filters = {
            "min_updated": min_updated,
            "require_large_pad": bool(requires_large_pad),
            "max_dist_ls": float(max_system_distance),
        }

        sources = _source_candidates(conn, start, station, float(max_hop_distance), filters)
        sources = _filter_carriers(sources, include_carriers)
        sources = sources[:MAX_SOURCE_CANDIDATES]
        if not sources:
            raise RouteError(
                "No market stations found near the start with fresh enough prices - "
                "try a larger max hop distance or price age."
            )

        beam = [
            {"hops": [], "profit": 0, "score": 0.0, "time_s": 0.0,
             "capital": int(capital), "at": src, "seen": {src["market_id"]}}
            for src in sources
        ]
        # Rank by freshness-weighted profit PER HOUR, same economics as loops:
        # a long detour hop has to out-earn its extra jumps and supercruise.
        def _rate(route):
            return route["score"] * 3600.0 / max(1.0, route["time_s"])

        best = None
        for _ in range(max(1, int(max_hops))):
            candidates = []
            for route in beam:
                candidates.extend(
                    _extend(conn, route, float(max_hop_distance), int(max_cargo), filters,
                            max(1, int(min_supply)), include_carriers, float(jump_range))
                )
            if not candidates:
                break
            candidates.sort(key=_rate, reverse=True)
            beam = candidates[:BEAM_WIDTH]
            if best is None or _rate(beam[0]) > _rate(best):
                best = beam[0]

        if not best or not best["hops"]:
            raise RouteError("No profitable route found with those settings.")
        return _format(conn, best)
    finally:
        conn.close()


# ---------- internals ----------


def _resolve_start(conn, system, star_pos):
    if system:
        row = marketdb.find_system(conn, system)
        if row:
            return {"id64": row[0], "system": row[1], "x": row[2], "y": row[3], "z": row[4]}
    if star_pos and len(star_pos) == 3:
        return {"system": system or "current position", "x": star_pos[0], "y": star_pos[1], "z": star_pos[2]}
    raise RouteError(f"Start system '{system}' not found in the local database.")


def _source_candidates(conn, start, station_name, max_hop, filters):
    near = marketdb.stations_near(conn, start["x"], start["y"], start["z"], max_hop, **filters)
    if station_name:
        exact = [
            s for s in near
            if s["station"].lower() == station_name.lower()
            and s["system"].lower() == start["system"].lower()
        ]
        if exact:
            return exact
    # Prefer close-by stations as the first buy point.
    near.sort(key=lambda s: (s["x"] - start["x"]) ** 2 + (s["y"] - start["y"]) ** 2 + (s["z"] - start["z"]) ** 2)
    return near[:MAX_SOURCE_POOL]


def _extend(conn, route, max_hop, max_cargo, filters, min_supply=1, include_carriers=True, jump_range=20.0):
    src = route["at"]
    dests = marketdb.stations_near(conn, src["x"], src["y"], src["z"], max_hop, **filters)
    dests = _filter_carriers(dests, include_carriers)
    if len(dests) > MAX_DEST_CANDIDATES:
        dests.sort(key=lambda station: _dist(src, station))
        dests = dests[:MAX_DEST_CANDIDATES]
    dest_by_id = {
        d["market_id"]: d for d in dests
        if d["market_id"] != src["market_id"] and d["market_id"] not in route["seen"]
    }
    if not dest_by_id:
        return []

    marks = ",".join("?" for _ in dest_by_id)
    dest_index = " INDEXED BY sqlite_autoindex_commodities_1" if len(dest_by_id) <= 1000 else ""
    pairs = conn.execute(
        f"""SELECT cd.market_id, cs.symbol, cs.buy_price, cd.sell_price, cs.supply, cd.demand
            FROM commodities cs
            JOIN commodities cd{dest_index} ON cd.symbol = cs.symbol
            WHERE cs.market_id = ?
              AND cd.market_id IN ({marks})
              AND cs.supply > 0 AND cs.buy_price > 0
              AND cd.demand > 0 AND cd.sell_price > cs.buy_price
            ORDER BY (cd.sell_price - cs.buy_price) DESC
            LIMIT {PAIR_QUERY_LIMIT}""",
        [src["market_id"], *dest_by_id.keys()],
    ).fetchall()

    flows_by_dest = {}
    for market_id, symbol, buy, sell, supply, demand in pairs:
        flows_by_dest.setdefault(market_id, []).append((symbol, buy, sell, supply, demand))

    extensions = []
    for market_id, flows in flows_by_dest.items():
        load = _fill_cargo(flows, max_cargo, route["capital"], min_supply)
        if not load:
            continue
        dest = dest_by_id[market_id]
        hop_profit = sum(c["profit"] for c in load)
        hop_dist = _dist(src, dest)
        hop_time = _leg_time_s(hop_dist, dest.get("dist_ls"), jump_range)
        extensions.append(
            {
                "hops": route["hops"]
                + [{"from": src, "to": dest, "commodities": load, "profit": hop_profit,
                    "distance": hop_dist}],
                "profit": route["profit"] + hop_profit,
                "score": route["score"] + hop_profit * _freshness_factor(dest.get("updated_at")),
                "time_s": route["time_s"] + hop_time,
                "capital": route["capital"] + hop_profit,
                "at": dest,
                "seen": route["seen"] | {market_id},
            }
        )
    extensions.sort(key=lambda r: r["score"] * 3600.0 / max(1.0, r["time_s"]), reverse=True)
    return extensions[:DESTS_PER_HOP]


def _fill_cargo(flows, max_cargo, capital, min_supply=1):
    """Greedy fill by unit profit; flows are pre-sorted by the SQL query.
    min_supply is a floor on BOTH source stock and destination demand, so
    routes never hinge on a handful of units."""
    space, funds = max_cargo, capital
    load = []
    for symbol, buy, sell, supply, demand in flows:
        if space <= 0 or funds < buy:
            break
        if supply < min_supply or demand < min_supply:
            continue
        if any(c["symbol"] == symbol for c in load):
            continue
        units = min(space, supply, demand, funds // buy)
        if units <= 0:
            continue
        load.append(
            {"symbol": symbol, "amount": units, "buy_price": buy, "sell_price": sell,
             "profit": units * (sell - buy), "supply": supply, "demand": demand}
        )
        space -= units
        funds -= units * buy
        if len(load) >= MAX_COMMODITIES_PER_HOP:
            break
    return load


def plan_loops(
    system,
    station=None,
    star_pos=None,
    capital=100000,
    max_cargo=8,
    radius=100.0,
    max_price_age_days=30,
    max_system_distance=1000,
    requires_large_pad=False,
    include_carriers=True,
    min_supply=1,
    jump_range=20.0,
    max_leg=None,
    top_n=LOOP_RESULTS,
):
    """Inara-style 2-station round trips near the player: fill the hold A->B,
    refill B->A, rank by estimated profit PER HOUR (travel-time model: jumps +
    supercruise + docking), not raw profit per trip. Legs may span several jumps.

    `radius` = how far from the player loop stations may be (getting to a distant
    loop is a one-time cost, so it is not penalised in the ranking); `max_leg` =
    the max distance between the two loop stations (defaults to radius)."""
    conn = marketdb.connect()
    try:
        if not marketdb.is_ready(conn):
            raise RouteError("Local market database is empty - build it from the Market Database panel first.")
        start = _resolve_start(conn, system, star_pos)

        stations = _nearby_station_pool(
            conn,
            start,
            radius,
            max_price_age_days,
            requires_large_pad,
            include_carriers,
            max_system_distance,
        )
        if len(stations) < 2:
            raise RouteError("Fewer than two market stations in range - increase the radius or price age.")
        stations = stations[:LOOP_STATION_CAP]
        by_id = {s["market_id"]: s for s in stations}

        conn.execute("DROP TABLE IF EXISTS temp.near_buy")
        conn.execute("DROP TABLE IF EXISTS temp.near_sell")
        conn.execute("CREATE TEMP TABLE near_buy(market_id INTEGER, symbol TEXT, buy INTEGER, supply INTEGER)")
        conn.execute("CREATE TEMP TABLE near_sell(market_id INTEGER, symbol TEXT, sell INTEGER, demand INTEGER)")
        _load_temp_ids(conn, by_id.keys())
        min_units = max(1, int(min_supply))
        conn.execute(
            "INSERT INTO temp.near_buy SELECT market_id, symbol, buy_price, supply"
            " FROM commodities WHERE market_id IN (SELECT market_id FROM temp.near_ids)"
            " AND supply >= ? AND buy_price > 0",
            (min_units,),
        )
        conn.execute(
            "INSERT INTO temp.near_sell SELECT market_id, symbol, sell_price, demand"
            " FROM commodities WHERE market_id IN (SELECT market_id FROM temp.near_ids)"
            " AND demand >= ? AND sell_price > 0",
            (min_units,),
        )
        conn.execute("CREATE INDEX temp.idx_nearsell_sym ON near_sell(symbol)")

        flows = conn.execute(
            f"""SELECT a.market_id, b.market_id, a.symbol, a.buy, b.sell, a.supply, b.demand
                FROM near_buy a JOIN near_sell b ON b.symbol = a.symbol
                WHERE a.market_id != b.market_id AND b.sell > a.buy
                ORDER BY (b.sell - a.buy) DESC LIMIT {LOOP_FLOW_LIMIT}"""
        ).fetchall()

        # Flows per directed pair, best-first (SQL already sorted them).
        directed = {}
        for a, b, sym, buy, sell, supply, demand in flows:
            lst = directed.setdefault((a, b), [])
            if len(lst) < LOOP_FLOWS_PER_PAIR:
                lst.append((sym, buy, sell, supply, demand))

        capital = int(capital)
        max_cargo = int(max_cargo)
        min_supply = max(1, int(min_supply))
        # Without a cap, two stations each within radius of the player could
        # still be up to 2x radius apart from each other.
        leg_cap = float(max_leg) if max_leg else float(radius)
        seen_pairs = set()
        loops = []
        for (a, b) in directed:
            key = frozenset((a, b))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            pair_dist = _dist(by_id[a], by_id[b])
            if pair_dist > leg_cap:
                continue
            out = _fill_cargo(directed.get((a, b), []), max_cargo, capital, min_supply)
            back = _fill_cargo(directed.get((b, a), []), max_cargo, capital, min_supply)
            out_p = sum(c["profit"] for c in out)
            back_p = sum(c["profit"] for c in back)
            if out_p + back_p <= 0:
                continue
            # Present the more profitable leg as the outbound one.
            if back_p > out_p:
                a, b, out, back, out_p, back_p = b, a, back, out, back_p, out_p
            trip_s = (
                _leg_time_s(pair_dist, by_id[b]["dist_ls"], float(jump_range))
                + _leg_time_s(pair_dist, by_id[a]["dist_ls"], float(jump_range))
            )
            loops.append(
                {"a": by_id[a], "b": by_id[b], "out": out, "back": back,
                 "profit": out_p + back_p, "out_profit": out_p, "back_profit": back_p,
                 "trip_s": trip_s, "profit_per_hour": (out_p + back_p) * 3600.0 / trip_s}
            )
        # Rank by earnings rate: a 4M loop that takes an hour loses to a 2M
        # loop that takes 20 minutes. Weighted by price freshness so a
        # month-old quote can't outrank a live one on nominal margin alone.
        loops.sort(
            key=lambda l: l["profit_per_hour"] * min(
                _freshness_factor(l["a"].get("updated_at")),
                _freshness_factor(l["b"].get("updated_at")),
            ),
            reverse=True,
        )
        loops = loops[:top_n]
        if not loops:
            raise RouteError("No profitable loop found with those settings.")
        return _format_loops(conn, loops, start)
    finally:
        conn.close()


def _format_loops(conn, loops, start):
    symbols = {c["symbol"] for l in loops for c in l["out"] + l["back"]}
    names = marketdb.commodity_display_names(conn, symbols)

    def leg(commodities):
        return [
            {
                "name": names.get(c["symbol"], c["symbol"].title()),
                "symbol": c["symbol"],
                "amount": c["amount"],
                "buy_price": c["buy_price"],
                "sell_price": c["sell_price"],
                "profit": c["profit"],
                "supply": c.get("supply"),
                "demand": c.get("demand"),
            }
            for c in commodities
        ]

    def endpoint(st):
        return {
            "station": st["station"],
            "market_id": st["market_id"],
            "system": st["system"],
            "dist_ls": st["dist_ls"],
            "large_pad": st["large_pad"],
            "updated_at": st["updated_at"],
            "from_player": round(_dist(st, start), 1),
        }

    return [
        {
            "a": endpoint(l["a"]),
            "b": endpoint(l["b"]),
            "distance": round(_dist(l["a"], l["b"]), 1),
            "profit": l["profit"],
            "minutes_per_trip": round(l["trip_s"] / 60.0),
            "profit_per_hour": int(l["profit_per_hour"]),
            "outbound": {"profit": l["out_profit"], "commodities": leg(l["out"])},
            "inbound": {"profit": l["back_profit"], "commodities": leg(l["back"])},
        }
        for l in loops
    ]


def _dist(a, b):
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def _filter_carriers(stations, include_carriers=True):
    if include_carriers:
        return list(stations)
    return [s for s in stations if not marketdb.is_carrier(s.get("type"), s.get("station"))]


def list_commodities():
    """All known commodities, for the search autocomplete."""
    conn = marketdb.connect()
    try:
        rows = conn.execute(
            "SELECT symbol, name, category FROM commodity_names ORDER BY name"
        ).fetchall()
        return [{"symbol": r[0], "name": r[1], "category": r[2]} for r in rows]
    finally:
        conn.close()


def search_commodity(
    query,
    mode,  # "buy" (I want to purchase) or "sell" (I want to offload cargo)
    system=None,
    star_pos=None,
    radius=50.0,
    min_units=1,
    max_price_age_days=30,
    requires_large_pad=False,
    include_carriers=True,
    max_system_distance=None,
    limit=40,
):
    if mode not in ("buy", "sell"):
        raise RouteError("mode must be 'buy' or 'sell'.")
    conn = marketdb.connect()
    try:
        if not marketdb.is_ready(conn):
            raise RouteError("Local market database is empty - build it from the Market Database panel first.")
        symbol, display = _resolve_commodity(conn, query)
        start = _resolve_start(conn, system, star_pos)

        stations = _nearby_station_pool(
            conn,
            start,
            radius,
            max_price_age_days,
            requires_large_pad,
            include_carriers,
            max_system_distance,
            cap=900,
        )
        by_id = {s["market_id"]: s for s in stations}
        if not by_id:
            return {"commodity": display, "results": []}

        _load_temp_ids(conn, by_id.keys())
        condition = "supply >= ? AND buy_price > 0" if mode == "buy" else "demand >= ? AND sell_price > 0"
        rows = conn.execute(
            f"""SELECT market_id, buy_price, sell_price, supply, demand
                FROM commodities
                WHERE symbol = ? AND market_id IN (SELECT market_id FROM temp.near_ids)
                  AND {condition}""",
            [symbol, max(1, int(min_units))],
        ).fetchall()

        results = []
        for market_id, buy, sell, supply, demand in rows:
            st = by_id[market_id]
            results.append(
                {
                    "station": st["station"],
                    "system": st["system"],
                    "type": st["type"],
                    "distance": round(_dist(start, st), 1),
                    "dist_ls": st["dist_ls"],
                    "large_pad": st["large_pad"],
                    "buy_price": buy,
                    "sell_price": sell,
                    "supply": supply,
                    "demand": demand,
                    "updated_at": st["updated_at"],
                }
            )
        results.sort(key=lambda r: r["buy_price"] if mode == "buy" else -r["sell_price"])
        return {"commodity": display, "symbol": symbol, "results": results[:limit]}
    finally:
        conn.close()


def find_opportunities(
    system=None,
    star_pos=None,
    radius=80.0,
    min_profit=1000,
    min_units=1,
    max_price_age_days=30,
    requires_large_pad=False,
    include_carriers=True,
    max_system_distance=None,
    source_market_id=None,
    limit=60,
):
    conn = marketdb.connect()
    try:
        if not marketdb.is_ready(conn):
            raise RouteError("Local market database is empty - build it from the Database tab first.")
        start = _resolve_start(conn, system, star_pos)
        stations = _nearby_station_pool(
            conn,
            start,
            radius,
            max_price_age_days,
            requires_large_pad,
            include_carriers,
            max_system_distance,
            cap=450,
        )
        by_id = {s["market_id"]: s for s in stations}
        if len(by_id) < 2:
            return []
        _load_temp_ids(conn, by_id.keys())
        source_filter = ""
        query_values = [
            max(1, int(min_units)), max(1, int(min_units)), int(min_profit),
        ]
        if source_market_id is not None:
            source_filter = " AND buy.market_id = ?"
            query_values.append(int(source_market_id))
        query_values.append(int(limit) * 4)
        rows = conn.execute(
            f"""SELECT buy.market_id, sell.market_id, buy.symbol, buy.buy_price, sell.sell_price,
                       buy.supply, sell.demand
                FROM commodities buy
                JOIN commodities sell ON sell.symbol = buy.symbol
                WHERE buy.market_id IN (SELECT market_id FROM temp.near_ids)
                  AND sell.market_id IN (SELECT market_id FROM temp.near_ids)
                  AND buy.market_id != sell.market_id
                  AND buy.supply >= ? AND sell.demand >= ?
                  AND buy.buy_price > 0 AND sell.sell_price > buy.buy_price
                  AND (sell.sell_price - buy.buy_price) >= ?
                  {source_filter}
                ORDER BY (sell.sell_price - buy.buy_price) DESC
                LIMIT ?""",
            query_values,
        ).fetchall()
        names = marketdb.commodity_display_names(conn, {r[2] for r in rows})
        out = []
        seen = set()
        for src_id, dst_id, symbol, buy, sell, supply, demand in rows:
            src = by_id.get(src_id)
            dst = by_id.get(dst_id)
            if not src or not dst:
                continue
            key = (src_id, dst_id, symbol)
            if key in seen:
                continue
            seen.add(key)
            units = min(int(supply or 0), int(demand or 0))
            profit_each = int(sell) - int(buy)
            updated_at = min(src.get("updated_at") or 0, dst.get("updated_at") or 0)
            out.append({
                "commodity": names.get(symbol, symbol.replace("_", " ").title()),
                "symbol": symbol,
                "from_station": src["station"],
                "from_system": src["system"],
                "to_station": dst["station"],
                "to_system": dst["system"],
                "buy_price": int(buy),
                "sell_price": int(sell),
                "profit_each": profit_each,
                "units": units,
                "supply": supply,
                "demand": demand,
                "distance": round(_dist(src, dst), 1),
                "from_player": round(_dist(start, src), 1),
                "from_dist_ls": src.get("dist_ls"),
                "to_dist_ls": dst.get("dist_ls"),
                "large_pad": bool(src.get("large_pad") and dst.get("large_pad")),
                "updated_at": updated_at,
                "_rank": profit_each * _freshness_factor(updated_at),
            })
        # Freshness-weighted ordering: nominal margin alone no longer wins.
        out.sort(key=lambda r: r["_rank"], reverse=True)
        out = out[:int(limit)]
        for r in out:
            r.pop("_rank", None)
        return out
    finally:
        conn.close()


def sell_cargo(
    cargo_items,
    system=None,
    star_pos=None,
    radius=80.0,
    max_price_age_days=30,
    requires_large_pad=False,
    include_carriers=True,
    max_system_distance=None,
    limit=10,
):
    items = []
    for item in cargo_items or []:
        raw_name = item.get("Name_Localised") or item.get("name") or item.get("Name")
        count = int(item.get("Count", item.get("count", 0)) or 0)
        if not raw_name or count <= 0:
            continue
        items.append({"raw_name": raw_name, "count": count})
    if not items:
        raise RouteError("Cargo hold is empty.")
    conn = marketdb.connect()
    try:
        if not marketdb.is_ready(conn):
            raise RouteError("Local market database is empty - build it from the Database tab first.")
        start = _resolve_start(conn, system, star_pos)
        stations = _nearby_station_pool(
            conn,
            start,
            radius,
            max_price_age_days,
            requires_large_pad,
            include_carriers,
            max_system_distance,
            cap=900,
        )
        by_id = {s["market_id"]: s for s in stations}
        if not by_id:
            return []
        counts = {}
        names = {}
        for item in items:
            try:
                symbol, display = _resolve_commodity(conn, item["raw_name"])
            except RouteError:
                symbol = marketdb.clean_commodity_symbol(item["raw_name"])
                if not symbol:
                    continue
                display_names = marketdb.commodity_display_names(conn, [symbol])
                display = display_names.get(symbol, str(item["raw_name"]).replace("_", " ").title())
            counts[symbol] = counts.get(symbol, 0) + item["count"]
            names[symbol] = display
        if not counts:
            raise RouteError("Cargo hold commodities are not known in the local market database.")
        _load_temp_ids(conn, by_id.keys())
        marks_s = ",".join("?" for _ in counts)
        rows = conn.execute(
            f"""SELECT market_id, symbol, sell_price, demand FROM commodities
                WHERE market_id IN (SELECT market_id FROM temp.near_ids)
                  AND symbol IN ({marks_s})
                  AND sell_price > 0 AND demand > 0""",
            [*counts.keys()],
        ).fetchall()
        per_station = {}
        for market_id, symbol, sell, demand in rows:
            units = min(int(counts[symbol]), int(demand or 0))
            if units <= 0:
                continue
            entry = per_station.setdefault(market_id, {"total": 0, "items": []})
            payout = units * int(sell)
            entry["total"] += payout
            entry["items"].append({
                "name": names.get(symbol, symbol.replace("_", " ").title()),
                "symbol": symbol,
                "units": units,
                "hold": counts[symbol],
                "sell_price": int(sell),
                "demand": int(demand or 0),
                "payout": payout,
                "partial": units < counts[symbol],
            })
        results = []
        for market_id, entry in per_station.items():
            st = by_id[market_id]
            entry["items"].sort(key=lambda i: -i["payout"])
            results.append({
                "station": st["station"],
                "system": st["system"],
                "distance": round(_dist(start, st), 1),
                "dist_ls": st.get("dist_ls"),
                "large_pad": st.get("large_pad"),
                "updated_at": st.get("updated_at"),
                "total": entry["total"],
                "items": entry["items"],
            })
        results.sort(key=lambda r: -r["total"])
        return results[:int(limit)]
    finally:
        conn.close()


def analyze_station_market(
    market_items,
    system=None,
    star_pos=None,
    radius=80.0,
    max_price_age_days=30,
    requires_large_pad=False,
    include_carriers=True,
    max_system_distance=None,
    limit=80,
):
    conn = marketdb.connect()
    try:
        if not marketdb.is_ready(conn):
            raise RouteError("Local market database is empty - build it from the Database tab first.")
        start = _resolve_start(conn, system, star_pos)
        stations = _nearby_station_pool(
            conn,
            start,
            radius,
            max_price_age_days,
            requires_large_pad,
            include_carriers,
            max_system_distance,
            cap=900,
        )
        by_id = {s["market_id"]: s for s in stations}
        if not by_id:
            return {}
        _load_temp_ids(conn, by_id.keys())
        analysis = {}
        for item in market_items or []:
            symbol = marketdb.clean_commodity_symbol(item.get("Name") or item.get("Name_Localised"))
            if not symbol:
                continue
            display = item.get("Name_Localised") or symbol.replace("_", " ").title()
            buy_price = int(item.get("BuyPrice") or 0)
            sell_price = int(item.get("SellPrice") or 0)
            stock = int(item.get("Stock") or 0)
            demand = int(item.get("Demand") or 0)
            best = None
            if stock > 0 and buy_price > 0:
                row = conn.execute(
                    """SELECT market_id, sell_price, demand
                        FROM commodities
                        WHERE symbol = ? AND market_id IN (SELECT market_id FROM temp.near_ids)
                          AND demand > 0 AND sell_price > ?
                        ORDER BY sell_price DESC LIMIT 1""",
                    [symbol, buy_price],
                ).fetchone()
                if row:
                    st = by_id[row[0]]
                    best = {
                        "signal": "Export",
                        "note": f"+{int(row[1]) - buy_price:,}/t to {st['station']} ({st['system']})",
                        "profit_each": int(row[1]) - buy_price,
                    }
            if best is None and demand > 0 and sell_price > 0:
                row = conn.execute(
                    """SELECT market_id, buy_price, supply
                        FROM commodities
                        WHERE symbol = ? AND market_id IN (SELECT market_id FROM temp.near_ids)
                          AND supply > 0 AND buy_price > 0 AND buy_price < ?
                        ORDER BY buy_price ASC LIMIT 1""",
                    [symbol, sell_price],
                ).fetchone()
                if row:
                    st = by_id[row[0]]
                    best = {
                        "signal": "Import",
                        "note": f"+{sell_price - int(row[1]):,}/t from {st['station']} ({st['system']})",
                        "profit_each": sell_price - int(row[1]),
                    }
            if best:
                analysis[display.lower()] = best
                if len(analysis) >= int(limit):
                    break
        return analysis
    finally:
        conn.close()


def _resolve_commodity(conn, query):
    q = (query or "").strip()
    if not q:
        raise RouteError("No commodity given.")
    row = conn.execute(
        "SELECT symbol, name FROM commodity_names WHERE symbol = ? COLLATE NOCASE OR name = ? COLLATE NOCASE",
        (q, q),
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT symbol, name FROM commodity_names WHERE name LIKE ? COLLATE NOCASE ORDER BY LENGTH(name) LIMIT 1",
            (f"%{q}%",),
        ).fetchone()
    if not row:
        raise RouteError(f"Unknown commodity '{query}'.")
    return row[0], row[1]


def _format(conn, route):
    symbols = {c["symbol"] for hop in route["hops"] for c in hop["commodities"]}
    names = marketdb.commodity_display_names(conn, symbols)
    hops = []
    cumulative = 0
    for hop in route["hops"]:
        cumulative += hop["profit"]
        hops.append(
            {
                "from_system": hop["from"]["system"],
                "from_station": hop["from"]["station"],
                "to_system": hop["to"]["system"],
                "to_station": hop["to"]["station"],
                "to_dist_ls": hop["to"]["dist_ls"],
                "distance": hop["distance"],
                "profit": hop["profit"],
                "cumulative_profit": cumulative,
                "commodities": [
                    {
                        "name": names.get(c["symbol"], c["symbol"].title()),
                        "amount": c["amount"],
                        "buy_price": c["buy_price"],
                        "sell_price": c["sell_price"],
                        "profit": c["profit"],
                        "supply": c.get("supply"),
                        "demand": c.get("demand"),
                    }
                    for c in hop["commodities"]
                ],
            }
        )
    return hops
