"""The commander's trading, worked out from their own trades (TradeStore):
totals, profit per day for the charts, best commodities, routes and stations,
sessions with profit per hour, recent trades, and a report to copy.

Trading profit only counts sales with a cost (AvgPricePaid); sales of cargo
that cost nothing (mined, salvaged, rewards) are shown beside it as "other
sales", never mixed into trading profit."""

from __future__ import annotations

from datetime import datetime, timezone
import time

DAY = 86400
RANGES = (1, 7, 30, 90, 365, 3650)


def _day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _credits(value):
    value = float(value or 0)
    for size, unit in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= size:
            return f"{value / size:.1f}{unit}"
    return f"{value:.0f}"


def _totals(store, since):
    row = store.query(
        "SELECT COALESCE(SUM(CASE WHEN kind='sell' AND profit IS NOT NULL THEN profit END),0) trade_profit,"
        " COALESCE(SUM(CASE WHEN kind='sell' AND profit IS NOT NULL THEN count END),0) traded_t,"
        " COALESCE(SUM(CASE WHEN kind='sell' AND profit IS NULL THEN total END),0) other_sales,"
        " COALESCE(SUM(CASE WHEN kind='sell' AND profit IS NULL THEN count END),0) other_t,"
        " COALESCE(SUM(CASE WHEN kind='sell' THEN total END),0) income,"
        " COALESCE(SUM(CASE WHEN kind='buy' THEN total END),0) spent,"
        " COALESCE(SUM(CASE WHEN kind='sell' AND profit IS NOT NULL THEN 1 END),0) trades,"
        " COUNT(*) events FROM trades WHERE ts >= ?", (since,))[0]
    return {key: int(value or 0) for key, value in row.items()}


def per_day(store, days, now=None):
    """One bucket per UTC day (or per hour for 24 hours): trading profit and
    other sales. Empty days are kept, so the chart's time axis is honest."""
    now = now or time.time()
    if days == 1:
        start = (int(now) // 3600 - 23) * 3600
        buckets = [start + index * 3600 for index in range(24)]
        size = 3600
    else:
        first = store.query("SELECT MIN(ts) ts FROM trades")[0]["ts"]
        span = min(days, max(1, int((now - (first or now)) // DAY) + 1)) if days >= 3650 else days
        start = (int(now) // DAY - span + 1) * DAY
        buckets = [start + index * DAY for index in range(span)]
        size = DAY
    rows = store.query(
        "SELECT CAST((ts - ?) / ? AS INTEGER) bucket,"
        " SUM(CASE WHEN profit IS NOT NULL THEN profit ELSE 0 END) trade,"
        " SUM(CASE WHEN profit IS NULL THEN total ELSE 0 END) other,"
        " SUM(count) tonnes FROM trades WHERE kind = 'sell' AND ts >= ? GROUP BY bucket", (start, size, start))
    by_bucket = {row["bucket"]: row for row in rows}
    out = []
    for index, ts in enumerate(buckets):
        row = by_bucket.get(index) or {}
        out.append({"ts": ts, "trade": int(row.get("trade") or 0), "other": int(row.get("other") or 0),
                    "tonnes": int(row.get("tonnes") or 0)})
    return out


def by_commodity(store, names, since, limit=12):
    rows = store.query(
        "SELECT commodity, SUM(profit) profit, SUM(count) tonnes, COUNT(*) sales, MAX(price) best_price"
        " FROM trades WHERE kind = 'sell' AND profit IS NOT NULL AND ts >= ? GROUP BY commodity"
        " ORDER BY profit DESC LIMIT ?", (since, limit))
    other = store.query(
        "SELECT commodity, SUM(total) income, SUM(count) tonnes, COUNT(*) sales FROM trades"
        " WHERE kind = 'sell' AND profit IS NULL AND ts >= ? GROUP BY commodity ORDER BY income DESC LIMIT ?",
        (since, limit))
    trade = [{"name": names.name(row["commodity"]), "profit": int(row["profit"] or 0), "tonnes": int(row["tonnes"] or 0),
              "sales": row["sales"], "per_t": int((row["profit"] or 0) / row["tonnes"]) if row["tonnes"] else 0}
             for row in rows]
    sold = [{"name": names.name(row["commodity"]), "income": int(row["income"] or 0), "tonnes": int(row["tonnes"] or 0),
             "sales": row["sales"]} for row in other]
    return trade, sold


def routes(store, names, since, limit=10):
    """Where trading cargo was bought and where it was sold (a sale's cargo
    came from the last purchase of that commodity before it)."""
    rows = store.query(
        "SELECT from_station, from_system, station, system, commodity, SUM(profit) profit, SUM(count) tonnes,"
        " COUNT(*) runs, MAX(ts) last FROM trades WHERE kind = 'sell' AND profit IS NOT NULL AND from_market_id IS NOT NULL"
        " AND ts >= ? GROUP BY from_market_id, market_id, commodity ORDER BY profit DESC LIMIT ?", (since, limit))
    return [{"from": row["from_station"] or "Unknown station", "from_system": row["from_system"] or "",
             "to": row["station"] or "Unknown station", "to_system": row["system"] or "",
             "commodity": names.name(row["commodity"]), "profit": int(row["profit"] or 0),
             "tonnes": int(row["tonnes"] or 0), "runs": row["runs"],
             "per_t": int((row["profit"] or 0) / row["tonnes"]) if row["tonnes"] else 0, "last": row["last"]}
            for row in rows]


def stations(store, since, limit=8):
    rows = store.query(
        "SELECT station, system, SUM(total) income, SUM(CASE WHEN profit IS NOT NULL THEN profit ELSE 0 END) profit,"
        " SUM(count) tonnes, COUNT(*) sales, MAX(ts) last FROM trades WHERE kind = 'sell' AND ts >= ?"
        " GROUP BY market_id ORDER BY income DESC LIMIT ?", (since, limit))
    return [{"station": row["station"] or "Unknown station", "system": row["system"] or "",
             "income": int(row["income"] or 0), "profit": int(row["profit"] or 0), "tonnes": int(row["tonnes"] or 0),
             "sales": row["sales"], "last": row["last"]} for row in rows]


def sessions(store, since, limit=20):
    """Game sessions with any selling in them, newest first, with profit per
    hour over the session's length (LoadGame to Shutdown)."""
    out = []
    for start, end in store.sessions(since=since - 12 * 3600):
        row = store.query(
            "SELECT COALESCE(SUM(CASE WHEN profit IS NOT NULL THEN profit END),0) trade,"
            " COALESCE(SUM(CASE WHEN profit IS NULL THEN total END),0) other, COALESCE(SUM(count),0) tonnes,"
            " COUNT(*) sales FROM trades WHERE kind = 'sell' AND ts >= ? AND ts <= ?", (start, end))[0]
        if not row["sales"] or end < since:
            continue
        hours = max((end - start) / 3600, 0.25)
        out.append({"start": start, "end": end, "hours": round(hours, 2), "trade": int(row["trade"]),
                    "other": int(row["other"]), "tonnes": int(row["tonnes"]), "sales": row["sales"],
                    "per_hour": int(row["trade"] / hours)})
    out.sort(key=lambda row: -row["start"])
    return out[:limit]


def recent(store, names, limit=60):
    rows = store.query("SELECT * FROM trades ORDER BY ts DESC LIMIT ?", (limit,))
    return [{"ts": row["ts"], "kind": row["kind"], "name": names.name(row["commodity"]), "count": row["count"],
             "price": row["price"], "total": row["total"], "profit": row["profit"], "avg_paid": row["avg_paid"],
             "station": row["station"] or "", "system": row["system"] or "",
             "flags": [flag for flag in ("stolen", "black_market", "illegal") if row.get(flag)]} for row in rows]


def summary(store, names, days=30, now=None):
    now = now or time.time()
    days = days if days in RANGES else 30
    since = now - days * DAY if days < 3650 else 0
    today = (int(now) // DAY) * DAY
    trade, other = by_commodity(store, names, since)
    session_rows = sessions(store, since)
    hours = sum(row["hours"] for row in session_rows)
    traded = sum(row["trade"] for row in session_rows)
    best = store.query("SELECT * FROM trades WHERE kind = 'sell' AND profit IS NOT NULL AND ts >= ? "
                       "ORDER BY profit DESC LIMIT 1", (since,))
    return {
        "days": days,
        "totals": {"range": _totals(store, since), "today": _totals(store, today), "all": _totals(store, 0)},
        "series": per_day(store, days, now),
        "commodities": trade, "other_sales": other,
        "routes": routes(store, names, since), "stations": stations(store, since),
        "sessions": session_rows,
        "per_hour": int(traded / hours) if hours else None,
        "best": ({"name": names.name(best[0]["commodity"]), "profit": int(best[0]["profit"]), "count": best[0]["count"],
                  "station": best[0]["station"], "system": best[0]["system"], "ts": best[0]["ts"]} if best else None),
        "recent": recent(store, names),
    }


def report(data):
    """A plain-text report of the range shown, ready to paste into Discord."""
    totals = data["totals"]["range"]
    label = {1: "the last 24 hours", 3650: "all time"}.get(data["days"], f"the last {data['days']} days")
    lines = [f"**Trading report: {label}**",
             f"Trading profit: {_credits(totals['trade_profit'])} CR from {totals['trades']} sales "
             f"({totals['traded_t']:,} t)"]
    if totals["other_sales"]:
        lines.append(f"Other sales (mined, salvaged): {_credits(totals['other_sales'])} CR ({totals['other_t']:,} t)")
    if data.get("per_hour"):
        lines.append(f"Profit per hour: {_credits(data['per_hour'])} CR")
    if data["commodities"]:
        lines.append("Best commodities: " + ", ".join(f"{row['name']} {_credits(row['profit'])}" for row in data["commodities"][:5]))
    if data["routes"]:
        top = data["routes"][0]
        lines.append(f"Best route: {top['commodity']}, {top['from']} ({top['from_system']}) → {top['to']} ({top['to_system']}), "
                     f"{_credits(top['profit'])} over {top['runs']} run{'s' if top['runs'] != 1 else ''}")
    return "\n".join(lines)
