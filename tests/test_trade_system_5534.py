"""5.5.3.4 Trading: routes from a whole system. One request (Spansh's system
dump, a real one for Sol, trimmed, in fixtures/spansh_trade) brings every
station's market; the form's rules leave some out; the best few are tried on
the trade router side by side and compared. Also what a system's own
stations pay beside a nearby search, and any station in a system opened from
the Market view."""

import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from voidcompass.services import spansh
from voidcompass.trading import market

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "spansh_trade"
NOW = 1_791_594_000.0  # 2026-10-10T01:00:00Z, an hour after the dump


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sol_dump():
    """The dump as spansh.system_dump hands it over (trimmed)."""
    with patch.object(spansh, "_call", return_value=fixture("system_dump_sol.json")), \
            patch.object(spansh, "_cache_dir", None):
        return spansh.system_dump(10477373803)


def form(**changes):
    out = {"max_cargo": 720, "max_price_age_days": 3, "max_system_distance": 5000, "requires_large_pad": 1,
           "allow_planetary": 1, "allow_player_owned": 0}
    out.update(changes)
    return out


class DumpTests(unittest.TestCase):
    def test_the_dump_is_trimmed_to_stations_with_a_market(self):
        dump = sol_dump()
        self.assertEqual((dump["name"], dump["id64"]), ("Sol", 10477373803))
        names = [row["name"] for row in dump["stations"]]
        self.assertEqual(names[:4], ["Abraham Lincoln", "Daedalus", "Mars High", "Li Qing Jao"])
        self.assertIn("Walz Depot", names, "surface ports are under their bodies in the dump")
        self.assertIn("Majoro Entertainment Complex", names)
        row = dump["stations"][0]
        self.assertNotIn("outfitting", row)
        self.assertNotIn("services", row)
        self.assertEqual(set(row["commodities"][0]), {"name", "category", "buyPrice", "sellPrice", "supply", "demand"})

    def test_parsed_like_any_station(self):
        found = market.parse_dump(sol_dump())
        by_name = {row["station"]: row for row in found["stations"]}
        daedalus = by_name["Daedalus"]
        self.assertEqual((daedalus["system"], daedalus["market_id"], daedalus["pad"], daedalus["planetary"]),
                         ("Sol", 128016384, "L", False))
        self.assertEqual(set(daedalus["market"][0]), {"name", "category", "buy", "sell", "supply", "demand"})
        self.assertTrue(by_name["Walz Depot"]["planetary"])
        self.assertEqual(by_name["Walz Depot"]["body"], "Mercury")
        self.assertTrue(by_name["Majoro Entertainment Complex"]["planetary"])
        self.assertAlmostEqual(daedalus["updated"], 1_791_576_501.0)
        distances = [row["arrival_ls"] for row in found["stations"]]
        self.assertEqual(distances, sorted(distances), "nearest the star first")


class StartTests(unittest.TestCase):
    def setUp(self):
        self.stations = market.parse_dump(sol_dump())["stations"]

    def test_the_most_promising_stations_lead(self):
        picks, fitting, left_out = market.start_candidates(self.stations, form(), NOW)
        self.assertEqual([row["station"] for row in picks], ["Daedalus", "Walz Depot", "Abraham Lincoln"],
                         "most goods for a full hold, then the freshest prices")
        self.assertEqual(fitting, 5)
        self.assertEqual(left_out, {"old": 1}, "the settlement's prices are three weeks old")
        self.assertEqual((picks[0]["full_hold"], picks[0]["in_stock"]), (8, 8))
        self.assertNotIn("market", picks[0])

    def test_the_form_rules_leave_stations_out(self):
        picks, fitting, left_out = market.start_candidates(self.stations, form(allow_planetary=0), NOW, limit=6)
        self.assertEqual([row["station"] for row in picks], ["Daedalus", "Abraham Lincoln", "Li Qing Jao", "Mars High"])
        self.assertEqual(left_out, {"planetary": 2})
        _picks, fitting, left_out = market.start_candidates(self.stations, form(max_system_distance=300), NOW)
        self.assertEqual((fitting, left_out), (2, {"far": 3, "old": 1}))
        carrier = {**self.stations[1], "station": "Q8X-1TZ", "carrier": True, "type": "Drake-Class Carrier"}
        empty = {**self.stations[1], "station": "Bare", "market": [{"name": "Gold", "category": "Metals", "buy": 0,
                                                                     "sell": 9000, "supply": 0, "demand": 50}]}
        small = {**self.stations[1], "station": "Little", "pad": "M"}
        _picks, _fitting, left_out = market.start_candidates([carrier, empty, small], form(), NOW)
        self.assertEqual(left_out, {"carrier": 1, "empty": 1, "pad": 1})
        picks, _fitting, _left = market.start_candidates([carrier], form(allow_player_owned=1), NOW)
        self.assertEqual(picks[0]["station"], "Q8X-1TZ")

    def test_a_system_own_stations(self):
        rows = market.parse_commodity(fixture("commodity_sell_gold.json"), "Gold", "sell")
        here = market.in_system(rows, "ugps 0722-05", "sell")
        self.assertEqual({row["station"] for row in here}, {"Cloutier's Forge", "Arai Town"})
        self.assertEqual([row["price"] for row in here], sorted((row["price"] for row in here), reverse=True))
        self.assertEqual(market.in_system(rows, "Sol", "sell"), [])


class DeckTests(unittest.TestCase):
    def deck(self):
        from voidcompass.dashboard.dashboard_trading_mixin import DashboardTradingMixin
        from voidcompass.dashboard.html_trading import HtmlTradingMixin

        class Deck(DashboardTradingMixin, HtmlTradingMixin):
            pass
        deck = Deck()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck.config = {"trading_online_enabled": True, "journal_path": folder.name}
        with patch("voidcompass.dashboard.dashboard_trading_mixin.get_profile_file",
                   lambda key, name: os.path.join(folder.name, name)), \
                patch("voidcompass.dashboard.dashboard_trading_mixin.get_active_profile", lambda config: "p"):
            deck._trading_init()
        self.addCleanup(deck.trading_store.close)
        transient = {}
        deck._html_profile_transient = lambda key, default: transient.setdefault(key, default)
        deck._schedule_html_dashboard_publish = Mock()
        deck._ui_post = lambda callback, *args, key=None: callback(*args)
        deck.current_sys, deck.current_docked, deck.current_station_name = "Sol", False, ""
        deck.cmdr_balance = 50_000_000
        deck.cmdr_ship = {"ship": "Type9", "cargo_capacity": 720, "max_jump_range": 18.6}
        return deck

    def wait(self, deck, name="route"):
        deadline = time.monotonic() + 10
        while name in deck._trading_busy and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertNotIn(name, deck._trading_busy, "the search finished")

    def test_routes_from_the_best_stations_side_by_side(self):
        deck = self.deck()
        route = fixture("trade_route_result.json")["result"]
        sent, states = [], []

        def router(request, on_state=None, should_stop=None):
            sent.append((request["system"], request["station"]))
            on_state("started")
            states.append([dict(row) for row in deck._trading_ui()["route"]["starts"]])
            if request["station"] == "Walz Depot":
                raise spansh.SpanshError("Spansh error (503): busy")
            return ([] if request["station"] == "Abraham Lincoln" else route), "job-" + request["station"]
        with patch.object(spansh, "system_id64", return_value=("Sol", 10477373803)) as lookup, \
                patch.object(spansh, "system_dump", return_value=sol_dump()), \
                patch.object(spansh, "trade_route", side_effect=router):
            deck._handle_trading_command("plan", {"system": "sol", "station": "", "whole_system": 1,
                                                  "max_price_age_days": 365, "requires_large_pad": 1})
            self.wait(deck)
        lookup.assert_called_once_with("sol")
        self.assertEqual(sorted(sent), [("Sol", "Abraham Lincoln"), ("Sol", "Daedalus"), ("Sol", "Walz Depot")],
                         "the three most promising, by Spansh's own names")
        self.assertTrue(all(any(row["state"] == "started" for row in seen) for seen in states))
        ui = deck._trading_ui()
        result = ui["route"]
        self.assertEqual([row["station"] for row in result["starts"]], ["Daedalus", "Abraham Lincoln", "Walz Depot"],
                         "the best route first, then no route, then the one that failed")
        self.assertEqual((result["pick"], result["station"]), (0, "Daedalus"))
        self.assertEqual(len(result["result"]["hops"]), 3)
        self.assertIn("busy", result["starts"][2]["error"])
        self.assertEqual((result["system"], result["markets"], result["fitting"]), ("Sol", 6, 6))
        self.assertEqual(ui["form"]["system"], "Sol")
        self.assertFalse(deck._handle_trading_command("pick_start", {"index": 2}), "nothing to show from a failed start")
        self.assertTrue(deck._handle_trading_command("pick_start", {"index": 0}))
        deck._handle_trading_command("view", {"view": "route"})
        json.dumps(deck._html_trading_workspace())
        deck.trade_route_hud = Mock()
        self.assertTrue(deck._handle_trading_command("follow", {}))
        self.assertEqual(deck.trading_route["plan"]["hops"][0]["from"]["station"], result["result"]["hops"][0]["from"]["station"])

    def test_nothing_fits_says_why(self):
        deck = self.deck()
        with patch.object(spansh, "system_id64", return_value=("Sol", 10477373803)), \
                patch.object(spansh, "system_dump", return_value=sol_dump()), \
                patch.object(spansh, "trade_route") as router:
            deck._handle_trading_command("plan", {"system": "Sol", "whole_system": 1, "max_system_distance": 10})
            self.wait(deck)
        router.assert_not_called()
        error = deck._trading_ui()["route"]["error"]
        self.assertIn("None of the 6 stations with a market in Sol fit these settings", error)
        self.assertIn("too far from the star", error)

    def test_stop_stops_every_search(self):
        deck = self.deck()

        def router(request, on_state=None, should_stop=None):
            deck._handle_trading_command("stop_plan", {})
            if should_stop():
                raise spansh.SpanshError("Stopped.")
            return fixture("trade_route_result.json")["result"], "job"
        with patch.object(spansh, "system_id64", return_value=("Sol", 10477373803)), \
                patch.object(spansh, "system_dump", return_value=sol_dump()), \
                patch.object(spansh, "trade_route", side_effect=router):
            deck._handle_trading_command("plan", {"system": "Sol", "whole_system": 1, "max_price_age_days": 365,
                                                  "try_stations": 2})
            deadline = time.monotonic() + 10
            while deck._trading_ui()["route"] and time.monotonic() < deadline:
                time.sleep(.02)
        self.assertEqual(deck._trading_ui()["route"], {}, "stopped: no result, no error")
        self.assertEqual(deck._trading_ui()["notice"], "Stopped the route search.")

    def test_a_station_is_still_needed_without_the_switch(self):
        deck = self.deck()
        with patch.object(spansh, "trade_route") as router:
            deck._handle_trading_command("plan", {"system": "Sol", "station": ""})
        router.assert_not_called()
        self.assertIn("give its system and station", deck._trading_ui()["error"])
        deck._handle_trading_command("plan", {"system": "", "whole_system": 1})
        self.assertEqual(deck._trading_ui()["error"], "Give the system to start from.")
        deck._handle_trading_command("plan", {"system": "", "whole_system": 1, "try_stations": 40})
        self.assertEqual(deck._trading_ui()["form"]["try_stations"], 6, "never more than six at once")

    def test_any_station_in_a_system_for_the_market_view(self):
        deck = self.deck()
        with patch.object(spansh, "system_id64", return_value=("Sol", 10477373803)), \
                patch.object(spansh, "system_dump", return_value=sol_dump()):
            deck._handle_trading_command("system_markets", {"system": "sol"})
            self.wait(deck, "markets")
        listed = deck._trading_ui()["markets"]
        self.assertEqual(listed["system"], "Sol")
        self.assertEqual(len(listed["stations"]), 6)
        self.assertNotIn("market", listed["stations"][0])
        daedalus = next(row for row in listed["stations"] if row["station"] == "Daedalus")
        self.assertEqual(daedalus["in_stock"], 8)
        deck._handle_trading_command("view", {"view": "station"})
        self.assertEqual(deck._html_trading_workspace()["station"]["list"]["system"], "Sol")

    def test_find_says_what_the_system_itself_pays(self):
        deck = self.deck()
        with patch.object(spansh, "market_field_values", return_value=fixture("field_values_market.json")), \
                patch.object(spansh, "commodity_stations", return_value=fixture("commodity_sell_gold.json")):
            deck._handle_trading_command("find", {"kind": "sell", "commodity": "gold", "system": "UGPS 0722-05", "amount": "1"})
            self.wait(deck, "find")
        here = deck._trading_ui()["find"]["here"]
        self.assertEqual({row["station"] for row in here}, {"Cloutier's Forge", "Arai Town"})


class PageTests(unittest.TestCase):
    def test_the_route_planner_offers_it(self):
        source = (ROOT / "web" / "dashboard" / "trading.js").read_text(encoding="utf-8")
        for text in ('check("whole_system", "From any station in this system"', 'name="try_stations"',
                     'data-trade-op="pick_start"', "function systemProgress", "BEST START IN",
                     'data-trade-form="system_markets"', "ANY STATION IN A SYSTEM", 'class="tr-here"'):
            self.assertIn(text, source)


if __name__ == "__main__":
    unittest.main()
