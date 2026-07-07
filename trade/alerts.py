"""In-memory route watches checked against live EDDN market updates."""

import itertools
import threading
from collections import deque

from . import marketdb

SELL_DROP = 0.90
BUY_RISE = 1.10
MAX_ALERTS = 50

_lock = threading.Lock()
_watch_ids = itertools.count(1)
WATCHES = {}
ALERTS = deque(maxlen=MAX_ALERTS)


def add_loop_watch(loop):
    a, b = loop.get("a") or {}, loop.get("b") or {}
    if not a.get("market_id") or not b.get("market_id"):
        raise ValueError("Loop has no market ids.")
    conditions = []

    def leg(src, dst, commodities):
        for c in commodities or []:
            sym = c.get("symbol")
            units = c.get("amount") or 0
            if not sym:
                continue
            conditions.append((src["market_id"], sym, "buy", units, c.get("buy_price") or 0, src.get("station")))
            conditions.append((dst["market_id"], sym, "sell", units, c.get("sell_price") or 0, dst.get("station")))

    leg(a, b, (loop.get("outbound") or {}).get("commodities"))
    leg(b, a, (loop.get("inbound") or {}).get("commodities"))
    if not conditions:
        raise ValueError("Loop has no commodities to watch.")
    with _lock:
        wid = next(_watch_ids)
        WATCHES[wid] = {
            "id": wid,
            "label": f"{a.get('station')} <-> {b.get('station')}",
            "market_ids": {a["market_id"], b["market_id"]},
            "conditions": conditions,
            "created": marketdb.utc_now_iso(),
            "profit": loop.get("profit"),
        }
        return dict(WATCHES[wid])


def remove_watch(wid):
    with _lock:
        return WATCHES.pop(int(wid), None) is not None


def snapshot():
    with _lock:
        return {
            "watches": [
                {"id": w["id"], "label": w["label"], "created": w["created"], "profit": w["profit"]}
                for w in WATCHES.values()
            ],
            "alerts": list(ALERTS),
        }


def clear_alerts():
    with _lock:
        ALERTS.clear()


def on_market_update(market_id, station_name, rows):
    with _lock:
        interested = [w for w in WATCHES.values() if market_id in w["market_ids"]]
    if not interested:
        return
    by_symbol = {r[0]: r for r in rows}
    for watch in interested:
        for mid, sym, side, units, base_price, station in watch["conditions"]:
            if mid != market_id:
                continue
            row = by_symbol.get(sym)
            name = sym.replace("_", " ").title()
            if row is None:
                _alert(watch, f"{name} vanished from {station}'s market ({watch['label']})")
                continue
            _symbol, buy, sell, supply, demand = row
            if side == "sell":
                if base_price and sell < base_price * SELL_DROP:
                    _alert(watch, f"{name} sell price at {station} dropped {base_price:,} -> {sell:,} cr ({watch['label']})")
                if units and demand < units:
                    _alert(watch, f"{name} demand at {station} is {demand:,}, below your {units:,} t load ({watch['label']})")
            else:
                if base_price and buy > base_price * BUY_RISE:
                    _alert(watch, f"{name} buy price at {station} rose {base_price:,} -> {buy:,} cr ({watch['label']})")
                if units and supply < units:
                    _alert(watch, f"{name} stock at {station} is {supply:,}, below your {units:,} t load ({watch['label']})")


def _alert(watch, text):
    with _lock:
        if any(existing["text"] == text for existing in ALERTS):
            return
        ALERTS.appendleft({"ts": marketdb.utc_now_iso(), "watch_id": watch["id"], "text": text})
