"""5.5.2.6 Trading: commodity names, the commander's trades from the journal
(profit from AvgPricePaid, sales without a cost kept apart), the views and
report, Spansh's replies (real ones, trimmed, in fixtures/spansh_trade),
loop routes, following a route, and the Trading tab and its overlay."""

import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS, OVERLAY_SPEC_BY_ATTR
from voidcompass.services import spansh
from voidcompass.trading import market, route, views
from voidcompass.trading.commodities import CommodityNames, symbol
from voidcompass.trading.importer import import_journals
from voidcompass.trading.journal import TradeJournal, journal_ts
from voidcompass.trading.store import TradeStore

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "spansh_trade"


SOL_STATIONS = ("Sol", [
    {"name": "Abraham Lincoln", "type": "Orbis Starport", "market_id": 128016896, "arrival_ls": 503, "carrier": False},
    {"name": "Daedalus", "type": "Orbis Starport", "market_id": 128016384, "arrival_ls": 7, "carrier": False},
])


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def docked(market_id, station, system, at="2026-10-01T10:00:00Z"):
    return {"timestamp": at, "event": "Docked", "MarketID": market_id, "StationName": station, "StarSystem": system}


def buy(market_id, kind, count, price, at="2026-10-01T10:05:00Z", localised=None):
    raw = {"timestamp": at, "event": "MarketBuy", "MarketID": market_id, "Type": kind, "Count": count,
           "BuyPrice": price, "TotalCost": count * price}
    if localised:
        raw["Type_Localised"] = localised
    return raw


def sell(market_id, kind, count, price, paid, at="2026-10-01T10:40:00Z"):
    return {"timestamp": at, "event": "MarketSell", "MarketID": market_id, "Type": kind, "Count": count,
            "SellPrice": price, "TotalSale": count * price, "AvgPricePaid": paid}


def store_with(*events):
    folder = tempfile.mkdtemp()
    store = TradeStore(os.path.join(folder, "trading.db"))
    reader = TradeJournal()
    for raw in events:
        store.apply(reader.observe(raw))
    return store


class NamesTests(unittest.TestCase):
    def test_journal_symbols_become_spansh_names(self):
        names = CommodityNames(spansh_names=market.price_ranges(fixture("field_values_market.json")))
        self.assertEqual(symbol("$Gold_Name;"), "gold")
        self.assertEqual(names.name("gold"), "Gold")
        self.assertEqual(names.name("$opal_name;"), "Void Opal", "Frontier's symbol is just 'opal'")
        self.assertEqual(names.name("lowtemperaturediamond"), "Low Temperature Diamonds", "a plural on Spansh")
        self.assertEqual(names.name("agriculturalmedicines"), "Agri-Medicines")
        self.assertEqual(names.name("marinesupplies"), "Marine Equipment")
        self.assertEqual(names.spansh_name("void opal"), "Void Opal", "typed names match Spansh's exact spelling")
        names.learn("consumertechnology", "Consumer Technology")
        self.assertEqual(names.name("consumertechnology"), "Consumer Technology", "learned from the journal")


class RecordTests(unittest.TestCase):
    def test_trades_profit_and_origin(self):
        store = store_with(
            docked(10, "Abraham Lincoln", "Sol"), buy(10, "gold", 100, 9000, localised="Gold"),
            {"timestamp": "2026-10-01T10:10:00Z", "event": "Undocked"},
            docked(20, "Arai Town", "UGPS 0722-05", at="2026-10-01T10:35:00Z"), sell(20, "gold", 100, 9800, 9000),
            sell(20, "platinum", 50, 200000, 0, at="2026-10-01T10:41:00Z"))
        sale = store.query("SELECT * FROM trades WHERE commodity = 'gold' AND kind = 'sell'")[0]
        self.assertEqual((sale["profit"], sale["station"], sale["from_station"]), (80000, "Arai Town", "Abraham Lincoln"))
        mined = store.query("SELECT profit, total FROM trades WHERE commodity = 'platinum'")[0]
        self.assertEqual((mined["profit"], mined["total"]), (None, 10000000), "a sale with no cost is not trading profit")
        self.assertEqual(store.names()["gold"], "Gold")

    def test_each_event_counts_once(self):
        event = sell(20, "gold", 1, 10, 5)
        store = store_with(event, event)
        reader = TradeJournal()
        self.assertFalse(store.apply(reader.observe(event)), "the history import meeting a live trade again")
        self.assertEqual(store.query("SELECT COUNT(*) n FROM trades")[0]["n"], 1)

    def test_summary_and_report(self):
        store = store_with(
            {"timestamp": "2026-10-01T09:00:00Z", "event": "LoadGame", "Commander": "Jameson"},
            docked(10, "Abraham Lincoln", "Sol"), buy(10, "gold", 100, 9000),
            docked(20, "Arai Town", "UGPS 0722-05", at="2026-10-01T10:35:00Z"), sell(20, "gold", 100, 9800, 9000),
            sell(20, "platinum", 50, 200000, 0, at="2026-10-01T10:41:00Z"),
            {"timestamp": "2026-10-01T11:00:00Z", "event": "Shutdown"})
        names = CommodityNames()
        now = journal_ts("2026-10-02T12:00:00Z")  # the trades are "yesterday" for the ranges
        data = views.summary(store, names, days=3650, now=now)
        self.assertEqual(data["totals"]["range"]["trade_profit"], 80000)
        self.assertEqual(data["totals"]["range"]["other_sales"], 10000000)
        self.assertEqual(data["sessions"][0]["per_hour"], 40000, "80k over the two-hour session")
        self.assertEqual(data["routes"][0]["from"], "Abraham Lincoln")
        self.assertEqual(sum(row["trade"] for row in data["series"]), 80000)
        report = views.report(data)
        self.assertIn("Trading profit: 80.0k CR", report)
        self.assertIn("Abraham Lincoln (Sol) → Arai Town (UGPS 0722-05)", report)
        json.dumps(data)

    def test_history_import_reads_only_this_commander(self):
        with tempfile.TemporaryDirectory() as folder:
            journals = Path(folder) / "journals"
            journals.mkdir()
            rows = [{"timestamp": "2026-10-01T09:00:00Z", "event": "LoadGame", "Commander": "Me", "FID": "F1"},
                    docked(10, "Abraham Lincoln", "Sol"), sell(10, "gold", 10, 100, 50),
                    {"timestamp": "2026-10-01T12:00:00Z", "event": "LoadGame", "Commander": "Alt", "FID": "F2"},
                    sell(10, "gold", 99, 100, 50, at="2026-10-01T12:30:00Z")]
            (journals / "Journal.2026-10-01T090000.01.log").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            store = TradeStore(os.path.join(folder, "trading.db"))
            self.assertEqual(import_journals(store, str(journals), "Me", "F1"), 1)
            self.assertEqual([row["count"] for row in store.query("SELECT count FROM trades")], [10])
            store.close()


class SpanshReplyTests(unittest.TestCase):
    def test_trade_route(self):
        plan = market.parse_route(fixture("trade_route_result.json")["result"])
        self.assertEqual(len(plan["hops"]), 3)
        first = plan["hops"][0]
        self.assertEqual((first["from"]["station"], first["to"]["station"]), ("Abraham Lincoln", "Arai Town"))
        self.assertEqual((first["goods"][0]["name"], first["goods"][0]["buy"], first["goods"][0]["sell"]), ("Biowaste", 109, 138))
        self.assertEqual(plan["profit"], plan["hops"][-1]["cumulative"])
        self.assertEqual(len(plan["hops"][2]["goods"]), 2, "a hop can carry two commodities")

    def test_commodity_searches(self):
        sell = market.parse_commodity(fixture("commodity_sell_gold.json"), "Gold", "sell")
        self.assertTrue(sell and all(row["price"] > 0 and row["stock"] > 0 for row in sell))
        self.assertEqual(sell[0]["station"], "Magnus Gateway")
        self.assertEqual(sell[0]["pad"], "L")
        self.assertIsNotNone(sell[0]["updated"])
        buy_rows = market.parse_commodity(fixture("commodity_buy_gold.json"), "Gold", "buy")
        self.assertTrue(all(row["stock"] > 0 for row in buy_rows), "only stations with it in stock")

    def test_station_and_ranges(self):
        station = market.parse_station(fixture("station.json"))
        self.assertEqual((station["station"], station["system"]), ("Abraham Lincoln", "Sol"))
        self.assertTrue(station["market"])
        ranges = market.price_ranges(fixture("field_values_market.json"))
        self.assertGreater(ranges["Gold"]["sell_max"], 0)

    def test_loop_between_two_markets(self):
        a = {"station": "A", "system": "S1", "market_id": 1, "market": [
            {"name": "Gold", "buy": 9000, "sell": 8800, "supply": 500, "demand": 0},
            {"name": "Tea", "buy": 0, "sell": 1900, "supply": 0, "demand": 900}]}
        b = {"station": "B", "system": "S2", "market_id": 2, "market": [
            {"name": "Gold", "buy": 0, "sell": 9900, "supply": 0, "demand": 300},
            {"name": "Tea", "buy": 1200, "sell": 1100, "supply": 9000, "demand": 0}]}
        loop = market.loop_route(a, b, cargo=400, capital=10 ** 9)
        self.assertEqual((loop["out"]["name"], loop["out"]["amount"]), ("Gold", 300), "limited by demand")
        self.assertEqual((loop["back"]["name"], loop["back"]["amount"], loop["back"]["profit"]), ("Tea", 400, 700))
        self.assertEqual(loop["profit"], 300 * 900 + 400 * 700)
        poor = market.loop_route(a, b, cargo=400, capital=100)
        self.assertEqual(poor["profit"], 0, "credits limit what can be bought")

    def test_trade_route_request_needs_a_station(self):
        with self.assertRaises(spansh.SpanshError):
            spansh.trade_route({"system": "Sol"})


class FollowRouteTests(unittest.TestCase):
    def test_hops_tick_along_from_the_journal(self):
        plan = market.parse_route(fixture("trade_route_result.json")["result"])
        state = route.start(plan)
        names = CommodityNames()
        first = plan["hops"][0]
        step = route.next_step(state)
        self.assertEqual((step["phase"], step["station"]), ("buy", "Abraham Lincoln"))
        self.assertFalse(route.observe(state, buy(first["from"]["market_id"], "gold", 5, 1), names), "not this hop's cargo")
        self.assertFalse(route.observe(state, buy(999, "biowaste", 200, 109), names), "not this hop's station")
        self.assertTrue(route.observe(state, buy(first["from"]["market_id"], "biowaste", 200, 109), names))
        self.assertEqual(route.next_step(state)["phase"], "sell")
        self.assertTrue(route.observe(state, docked(first["to"]["market_id"], "Arai Town", "UGPS 0722-05"), names))
        self.assertTrue(route.next_step(state)["here"])
        self.assertTrue(route.observe(state, sell(first["to"]["market_id"], "biowaste", 200, 138, 109), names))
        self.assertEqual((state["hop"], state["profit"]), (1, 200 * 29))
        route.skip(state)
        route.skip(state)
        self.assertTrue(route.next_step(state)["done"])

    def test_prices_checked_on_arrival(self):
        plan = market.parse_route(fixture("trade_route_result.json")["result"])
        state = route.start(plan)
        station = {"market": [{"name": "Biowaste", "buy": 140, "sell": 100, "supply": 50000, "demand": 0}]}
        warnings = route.check_prices(state, station)
        self.assertEqual(len(warnings), 1)
        self.assertIn("planned 109", warnings[0])
        station["market"][0]["buy"] = 110
        self.assertEqual(route.check_prices(state, station), [], "a small move is not a warning")


class TabTests(unittest.TestCase):
    def deck(self, online=True):
        from voidcompass.dashboard.dashboard_trading_mixin import DashboardTradingMixin
        from voidcompass.dashboard.html_trading import HtmlTradingMixin

        class Deck(DashboardTradingMixin, HtmlTradingMixin):
            pass
        deck = Deck()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck.config = {"trading_online_enabled": online, "journal_path": folder.name}
        with patch("voidcompass.dashboard.dashboard_trading_mixin.get_profile_file",
                   lambda key, name: os.path.join(folder.name, name)), \
                patch("voidcompass.dashboard.dashboard_trading_mixin.get_active_profile", lambda config: "p"):
            deck._trading_init()
        self.addCleanup(deck.trading_store.close)
        transient = {}
        deck._html_profile_transient = lambda key, default: transient.setdefault(key, default)
        deck._schedule_html_dashboard_publish = Mock()
        deck._html_copy_text = Mock(return_value=True)
        deck._ui_post = lambda callback, *args, key=None: callback(*args)
        deck.current_sys, deck.current_docked, deck.current_station_name = "Sol", True, "Abraham Lincoln"
        deck.current_station_market_id = 128016896
        deck.cmdr_balance = 20_000_000
        deck.cmdr_ship = {"ship": "Type9", "cargo_capacity": 720, "max_jump_range": 18.6}
        deck.current_cargo_inventory = [{"Name": "gold", "Count": 100, "Stolen": 0}]
        return deck

    def run_inline(self):
        original = threading.Thread
        threading.Thread = lambda target, **kw: Mock(start=target)
        self.addCleanup(setattr, threading, "Thread", original)

    def test_form_from_the_journal_and_every_view(self):
        deck = self.deck()
        form = deck._trading_form_defaults()
        self.assertEqual((form["system"], form["station"], form["max_cargo"], form["requires_large_pad"], form["max_hop_distance"]),
                         ("Sol", "Abraham Lincoln", 720, 1, 18))
        for view in ("overview", "route", "cargo", "find", "station", "history"):
            deck._handle_trading_command("view", {"view": view})
            json.dumps(deck._html_trading_workspace())
        deck._handle_trading_command("days", {"days": 1})
        self.assertEqual(deck._trading_ui()["days"], 1)

    def test_no_spansh_traffic_when_off(self):
        deck = self.deck(online=False)
        with patch.object(spansh, "trade_route") as planner:
            deck._handle_trading_command("plan", {})
            planner.assert_not_called()
        self.assertIn("Trading searches are off", deck._trading_ui()["route"]["error"])

    def test_plan_follow_and_tick_live(self):
        self.run_inline()
        deck = self.deck()
        result = fixture("trade_route_result.json")["result"]
        with patch.object(spansh, "trade_route", return_value=(result, "job")) as planner,                 patch.object(spansh, "system_stations", return_value=SOL_STATIONS):
            deck._handle_trading_command("plan", {"max_hops": "3", "requires_large_pad": "0"})
            sent = planner.call_args.args[0]
        self.assertEqual((sent["system"], sent["station"], sent["max_hops"], sent["requires_large_pad"]), ("Sol", "Abraham Lincoln", 3, 0))
        self.assertEqual(sent["max_price_age"], 3 * 86400)
        self.assertEqual(len(deck._trading_ui()["route"]["result"]["hops"]), 3)
        deck.trade_route_hud = Mock()
        deck._handle_trading_command("follow", {})
        deck.trade_route_hud.update_route.assert_called()
        source = deck.trading_route["plan"]["hops"][0]["from"]["market_id"]
        deck._trading_observe(buy(source, "biowaste", 200, 109), startup_replay=True)
        self.assertEqual(deck.trading_route["phase"], "buy", "the startup replay never ticks a route")
        deck._trading_observe(buy(source, "biowaste", 200, 109))
        self.assertEqual(deck.trading_route["phase"], "sell")
        self.assertEqual(deck.trading_store.value("route")["phase"], "sell", "kept across restarts")

    def test_station_names_are_matched_before_planning(self):
        self.run_inline()
        deck = self.deck()
        result = fixture("trade_route_result.json")["result"]
        with patch.object(spansh, "trade_route", return_value=(result, "job")) as planner,                 patch.object(spansh, "system_stations", return_value=SOL_STATIONS) as lookup:
            deck._handle_trading_command("plan", {"system": "sol", "station": "orbis starport"})
            planner.assert_not_called()
            choices = deck._trading_ui()["route"]["choices"]
            self.assertEqual((choices["typed"], choices["stations"][0]["name"]), ("orbis starport", "Abraham Lincoln"),
                             "a station type is not a station: offer the system's stations")
            deck._handle_trading_command("pick_station", {"system": "Sol", "station": "abraham lincoln"})
            self.assertEqual(planner.call_args.args[0]["station"], "Abraham Lincoln", "sent as Spansh spells it")
            self.assertEqual(deck._trading_ui()["form"]["station"], "Abraham Lincoln")
            self.assertEqual(lookup.call_count, 1, "a system's stations are asked for once")

    def test_route_progress_stop_and_docked_shortcut(self):
        self.run_inline()
        deck = self.deck()
        seen = []

        def slow_router(form, on_state=None, should_stop=None):
            on_state("queued")
            seen.append(dict(deck._trading_ui()["route"]))
            on_state("started")
            seen.append(dict(deck._trading_ui()["route"]))
            deck._handle_trading_command("stop_plan", {})
            if should_stop():
                raise spansh.SpanshError("Stopped.")
            return fixture("trade_route_result.json")["result"], "job"
        with patch.object(spansh, "trade_route", side_effect=slow_router) as planner,                 patch.object(spansh, "system_stations") as lookup:
            deck._handle_trading_command("plan", {"system": "sol", "station": "ABRAHAM LINCOLN"})
            lookup.assert_not_called()
            self.assertEqual(planner.call_args.args[0]["station"], "Abraham Lincoln", "docked here: the game's own spelling")
        self.assertEqual([row["stage"] for row in seen], ["queued", "started"])
        self.assertTrue(seen[0]["pending"] and seen[0]["started"])
        self.assertEqual(deck._trading_ui()["route"], {}, "stopped: no result, no error")
        self.assertEqual(deck._trading_ui()["notice"], "Stopped the route search.")
        self.assertNotIn("route", deck._trading_busy)

    def test_sell_my_cargo_and_find(self):
        self.run_inline()
        deck = self.deck()
        with patch.object(spansh, "market_field_values", return_value=fixture("field_values_market.json")), \
                patch.object(spansh, "commodity_stations", return_value=fixture("commodity_sell_gold.json")) as search:
            deck._handle_trading_command("cargo", {})
            self.assertEqual(search.call_args.args, ("sell", "Sol", "Gold", 100))
            rows = deck._trading_ui()["cargo"]["rows"]
            self.assertEqual(rows[0]["name"], "Gold")
            prices = [row["price"] for row in rows[0]["stations"]]
            self.assertEqual(prices, sorted(prices, reverse=True), "best price first")
            deck._handle_trading_command("find", {"kind": "sell", "commodity": "gold", "system": "Sol", "amount": "5"})
            self.assertEqual(search.call_args.args, ("sell", "Sol", "Gold", 5), "typed lower case, sent as Spansh spells it")
        self.assertTrue(deck._trading_ui()["find"]["results"])

    def test_docked_market_comes_from_the_game(self):
        deck = self.deck()
        market_file = {"timestamp": "2026-10-01T10:00:00Z", "event": "Market", "MarketID": 128016896, "StationName": "Abraham Lincoln",
                       "StarSystem": "Sol", "Items": [{"Name": "$gold_name;", "Name_Localised": "Gold", "Category_Localised": "Metals",
                                                       "BuyPrice": 9000, "SellPrice": 8800, "Stock": 50, "Demand": 0, "MeanPrice": 9400}]}
        Path(deck.config["journal_path"], "Market.json").write_text(json.dumps(market_file), encoding="utf-8")
        local = deck._trading_local_market()
        self.assertEqual((local["station"], local["market"][0]["name"], local["market"][0]["buy"]), ("Abraham Lincoln", "Gold", 9000))
        deck.current_station_market_id = 1
        self.assertIsNone(deck._trading_local_market(), "another station's Market.json is not this one's")

    def test_registered(self):
        for key in ("trading_online_enabled", "trade_route_overlay_enabled"):
            self.assertIn(key, config_module.PROFILE_BOOL_SETTINGS)
        spec = OVERLAY_SPEC_BY_ATTR["trade_route_hud"]
        self.assertEqual((spec.overlay_id, spec.hotkey_action), ("trade-route", "trade_route"))
        self.assertIn("trade_route", [row[0] for row in OVERLAY_HOTKEY_SPECS])
        deck = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="trading"', deck)
        self.assertIn('href="trading.css"', deck)
        self.assertIn('settingGroup("Trading"', (WEB / "dashboard" / "app.js").read_text(encoding="utf-8"))
        self.assertNotIn("<style", (WEB / "trade_route" / "index.html").read_text(encoding="utf-8"))
        css = (WEB / "dashboard" / "trading.css").read_text(encoding="utf-8")
        hexes = [line for line in css.splitlines() if "--tr-s" not in line and __import__("re").search(r"#[0-9a-fA-F]{3,6}\b", line)
                 and not line.strip().startswith("#trading-workspace")]
        self.assertEqual(hexes, [], "only the chart series palette is fixed colour")


if __name__ == "__main__":
    unittest.main()
