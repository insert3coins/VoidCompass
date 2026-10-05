"""The commander's trades, from the journal: one reader for live play and the
history import, so each trade counts once whichever way it arrives (a trade's
id is a hash of its journal line).

MarketSell carries AvgPricePaid, the game's own average cost of what was sold,
so profit is exact. AvgPricePaid 0 means the cargo cost nothing (mined,
salvaged, a mission reward): those are kept as sales without a cost, and are
told apart from trading in every figure."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json

from voidcompass.trading.commodities import symbol


def journal_ts(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def event_uid(raw):
    return hashlib.sha1(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class TradeJournal:
    """``observe(raw)`` -> records for TradeStore.apply: ("market", …),
    ("name", (symbol, name)), ("trade", …), ("session", ts), ("session_end", ts)."""

    def __init__(self):
        self.docked = None   # {"market_id", "station", "system"}

    def observe(self, raw):
        if not isinstance(raw, dict):
            return []
        event, ts = raw.get("event"), journal_ts(raw.get("timestamp"))
        if ts is None:
            return []
        if event in ("Docked", "Location", "Market") and raw.get("MarketID"):
            if event == "Location" and not raw.get("Docked"):
                self.docked = None
                return []
            self.docked = {"market_id": _int(raw["MarketID"]), "station": raw.get("StationName") or "",
                           "system": raw.get("StarSystem") or ""}
            return [("market", {**self.docked, "ts": ts})]
        if event == "Undocked":
            self.docked = None
            return []
        if event == "LoadGame":
            return [("session", ts)]
        if event == "Shutdown":
            return [("session_end", ts)]
        if event not in ("MarketBuy", "MarketSell"):
            return []
        key = symbol(raw.get("Type"))
        count = _int(raw.get("Count"))
        if not key or count <= 0:
            return []
        records = []
        if raw.get("Type_Localised"):
            records.append(("name", (key, raw["Type_Localised"])))
        market_id = _int(raw.get("MarketID"))
        here = self.docked if self.docked and self.docked["market_id"] == market_id else {}
        trade = {
            "uid": event_uid(raw), "ts": ts, "market_id": market_id,
            "station": here.get("station", ""), "system": here.get("system", ""),
            "commodity": key, "count": count, "stolen": 0, "black_market": 0, "illegal": 0,
        }
        if event == "MarketBuy":
            trade.update(kind="buy", price=_int(raw.get("BuyPrice")), total=_int(raw.get("TotalCost")),
                         avg_paid=None, profit=None)
        else:
            total, paid = _int(raw.get("TotalSale")), _int(raw.get("AvgPricePaid"))
            trade.update(kind="sell", price=_int(raw.get("SellPrice")), total=total, avg_paid=paid,
                         # No cost (mined, salvaged, rewarded): a sale, not a trade.
                         profit=(total - paid * count) if paid > 0 else None,
                         stolen=int(bool(raw.get("StolenGoods"))), black_market=int(bool(raw.get("BlackMarket"))),
                         illegal=int(bool(raw.get("IllegalGoods"))))
        records.append(("trade", trade))
        return records
