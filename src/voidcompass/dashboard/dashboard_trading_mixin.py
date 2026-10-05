"""Trading (5.5.2.6): the record and the Spansh work behind the Trading tab.

The commander's own trades go through one reader for live play and the
history import (trading.journal), kept per profile in trading.db. Prices,
routes and stations come from Spansh, only when the commander asks (and
"Trading searches" is on in Settings > Integrations); replies are kept for a
few minutes so moving between views doesn't ask again. The docked station's
own market comes from the game's Market.json, which is always the freshest.

A followed route ticks along from live MarketBuy/MarketSell events (never
from the startup replay, which would count trades twice), and when you dock
at one of its stations its prices there are checked again on Spansh.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

from voidcompass.core.config import get_active_profile, get_profile_file
from voidcompass.services import spansh
from voidcompass.trading import market as trade_market
from voidcompass.trading import route as trade_route
from voidcompass.trading.commodities import CommodityNames, symbol
from voidcompass.trading.importer import import_journals
from voidcompass.trading.journal import TradeJournal, journal_ts
from voidcompass.trading.store import TradeStore

_CACHE_S = 10 * 60


class DashboardTradingMixin:
    def _trading_init(self, profile_key=None):
        key = profile_key or get_active_profile(self.config)
        self.trading_store = TradeStore(get_profile_file(key, "trading.db"))
        self.trading_journal = TradeJournal()
        self.trading_names = CommodityNames(self.trading_store.names())
        self.trading_route = self.trading_store.value("route")
        self._trading_import_state = {"running": False, "done": False}
        self._trading_cache = {}
        self._trading_busy = {}
        self._trading_generation = getattr(self, "_trading_generation", 0) + 1

    def _trading_switch_profile(self, profile_key):
        old = getattr(self, "trading_store", None)
        self._trading_init(profile_key)
        if old is not None:
            old.close()
        self._trading_start_import()

    def _trading_close(self):
        self._trading_generation = getattr(self, "_trading_generation", 0) + 1
        store = getattr(self, "trading_store", None)
        if store is not None:
            store.close()

    def _trading_online(self):
        return bool(self.config.get("trading_online_enabled", True))

    def _trading_publish(self):
        if getattr(self, "_html_dashboard_active_page", "") == "trading":
            self._schedule_html_dashboard_publish()

    # -- the journal -------------------------------------------------------
    def _trading_observe(self, raw, startup_replay=False):
        reader, store = getattr(self, "trading_journal", None), getattr(self, "trading_store", None)
        if reader is None or store is None or not isinstance(raw, dict):
            return False
        try:
            records = reader.observe(raw)
            for kind, value in records:
                if kind == "name":
                    self.trading_names.learn(*value)
            changed = store.apply(records)
        except Exception as exc:
            logging.debug("Trading event skipped [%s]: %s", raw.get("event"), exc)
            return False
        if not startup_replay:
            changed = self._trading_follow_route(raw) or changed
        if changed and not startup_replay:
            self._trading_publish()
        return changed

    def _trading_follow_route(self, raw):
        state = getattr(self, "trading_route", None)
        if not state or not trade_route.observe(state, raw, self.trading_names):
            return False
        self.trading_store.set_value("route", state)
        step = trade_route.next_step(state)
        if raw.get("event") == "Docked" and step and step.get("here") and self._trading_online():
            self._trading_recheck_route(step["market_id"])
        self._trading_update_overlay()
        return True

    def _trading_recheck_route(self, market_id):
        """Docked at a route station: are its prices still what was planned?"""
        def done(station, error):
            state = getattr(self, "trading_route", None)
            if station and state:
                trade_route.check_prices(state, station)
                self.trading_store.set_value("route", state)
                self._trading_update_overlay()
        self._trading_task("recheck", lambda: trade_market.parse_station(spansh.station_market(market_id)), done,
                           cache_key=None)

    def _trading_update_overlay(self):
        hud = getattr(self, "trade_route_hud", None)
        if hud is not None:
            try:
                hud.update_route(trade_route.next_step(getattr(self, "trading_route", None)))
            except Exception:
                logging.exception("Trade overlay update failed")

    # -- history -----------------------------------------------------------
    def _trading_start_import(self):
        store, state = getattr(self, "trading_store", None), getattr(self, "_trading_import_state", None)
        if store is None or state is None or state.get("running"):
            return False
        journal_path = self.config.get("journal_path") or getattr(getattr(self, "watcher", None), "journal_path", None)
        commander, fid = getattr(self, "cmdr_name", None), getattr(self, "cmdr_fid", None)
        generation = self._trading_generation
        state["running"] = True

        def run():
            try:
                import_journals(store, journal_path, commander, fid,
                                should_stop=lambda: generation != self._trading_generation)
            except Exception:
                logging.exception("Trading history import failed")
            if generation != self._trading_generation:
                return
            for key, name in store.names().items():
                self.trading_names.learn(key, name)

            def finish():
                state.update(running=False, done=True)
                self._trading_publish()
            self._ui_post(finish, key=None)
        threading.Thread(target=run, name="trading-import", daemon=True).start()
        return True

    # -- Spansh ------------------------------------------------------------
    def _trading_task(self, name, work, on_done, cache_key=None):
        """Run one Spansh request in the background. ``on_done(result,
        error)`` runs on the UI thread; a cached reply answers at once."""
        if not self._trading_online():
            on_done(None, "Trading searches are off. Turn them on in Settings > Integrations.")
            return True
        if cache_key is not None:
            cached = self._trading_cache.get(cache_key)
            if cached and time.time() - cached[0] < _CACHE_S:
                on_done(cached[1], "")
                return True
        generation = self._trading_generation
        self._trading_busy[name] = True

        def run():
            result, error = None, ""
            try:
                result = work()
                if cache_key is not None:
                    self._trading_cache[cache_key] = (time.time(), result)
            except spansh.SpanshError as exc:
                error = str(exc)
            except Exception as exc:
                logging.exception("Trading %s failed", name)
                error = f"Spansh request failed: {exc}"
            if generation != self._trading_generation:
                return

            def finish():
                self._trading_busy.pop(name, None)
                on_done(result, error)
                self._schedule_html_dashboard_publish(immediate=True)
            self._ui_post(finish, key=None)
        threading.Thread(target=run, name=f"trading-{name}", daemon=True).start()
        return True

    def _trading_spansh_names(self):
        """Spansh's own commodity names (and best prices anywhere), once a
        session, so journal symbols become names Spansh can search by."""
        cached = getattr(self, "_trading_price_ranges", None)
        if cached is None:
            cached = trade_market.price_ranges(spansh.market_field_values())
            self._trading_price_ranges = cached
            self.trading_names.add_spansh_names(cached)
        return cached

    # -- the game's own files ----------------------------------------------
    def _trading_local_market(self):
        """The docked station's market from Market.json (written by the game
        when the commodity market is opened), if it is this station's."""
        market_id = getattr(self, "current_station_market_id", None)
        journal_path = self.config.get("journal_path") or getattr(getattr(self, "watcher", None), "journal_path", None)
        if not market_id or not journal_path:
            return None
        try:
            with open(os.path.join(journal_path, "Market.json"), "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return None
        if data.get("MarketID") != market_id:
            return None
        rows = []
        for item in data.get("Items") or ():
            self.trading_names.learn(item.get("Name"), item.get("Name_Localised"))
            rows.append({"name": self.trading_names.name(item.get("Name")),
                         "category": item.get("Category_Localised") or "",
                         "buy": int(item.get("BuyPrice") or 0), "sell": int(item.get("SellPrice") or 0),
                         "supply": int(item.get("Stock") or 0), "demand": int(item.get("Demand") or 0),
                         "mean": int(item.get("MeanPrice") or 0)})
        return {"station": data.get("StationName") or "", "system": data.get("StarSystem") or "",
                "market_id": market_id, "updated": journal_ts(data.get("timestamp")), "source": "game",
                "market": sorted(rows, key=lambda row: (row["category"], row["name"]))}

    def _trading_cargo(self):
        """The ship's hold now (Cargo.json), by commodity."""
        rows = {}
        for item in getattr(self, "current_cargo_inventory", None) or ():
            key = symbol(item.get("Name"))
            if not key:
                continue
            self.trading_names.learn(item.get("Name"), item.get("Name_Localised"))
            row = rows.setdefault(key, {"symbol": key, "name": self.trading_names.name(item.get("Name")),
                                        "count": 0, "stolen": 0})
            row["count"] += int(item.get("Count") or 0)
            row["stolen"] += int(item.get("Stolen") or 0)
        return sorted(rows.values(), key=lambda row: -row["count"])
