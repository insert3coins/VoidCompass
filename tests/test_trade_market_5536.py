"""5.5.3.6: Trading's Market view, searching one system after another.

It got quirky: open a station, search another system, and the first
station's market could land late under the new system's list; two searches
in a row could list the first one's stations under the second one's name; a
market from the system before stayed on screen. Only the latest request is
shown now, a new system clears a market from another, and the view keeps the
search and its stations beside the market (one hid the other)."""

from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from tests.test_trading import TabTests
from voidcompass.services import spansh

WEB = Path(__file__).resolve().parents[1] / "web"
SYSTEMS = {"sol": ("Sol", 1), "colonia": ("Colonia", 2)}
DUMPS = {
    1: {"name": "Sol", "stations": [{"name": "Abraham Lincoln", "id": 101, "type": "Orbis Starport", "commodities": []}]},
    2: {"name": "Colonia", "stations": [{"name": "Jaques Station", "id": 201, "type": "Orbis Starport", "commodities": []}]},
}


def market(market_id, name, system):
    return {"record": {"name": name, "system_name": system, "market_id": market_id, "market": [
        {"commodity": "Gold", "category": "Metals", "buy_price": 9000, "sell_price": 8800, "supply": 10, "demand": 0}]}}


MARKETS = {101: market(101, "Abraham Lincoln", "Sol"), 102: market(102, "Daedalus", "Sol"),
           201: market(201, "Jaques Station", "Colonia")}


class MarketSearchTests(unittest.TestCase):
    deck = TabTests.deck

    def held(self):
        """Spansh's replies held back, to be let through in any order."""
        queue = []
        original = threading.Thread
        threading.Thread = lambda target, **kw: type("Held", (), {"start": lambda self: queue.append(target)})()
        self.addCleanup(setattr, threading, "Thread", original)
        for name, fake in (("system_id64", lambda system: SYSTEMS[system.casefold()]),
                           ("system_dump", lambda id64: DUMPS[id64]),
                           ("station_market", lambda market_id: MARKETS[market_id]),
                           ("market_field_values", lambda: {})):
            patcher = patch.object(spansh, name, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        return queue

    def shown(self, deck):
        deck._handle_trading_command("view", {"view": "station"})
        return deck._html_trading_workspace()["station"]

    def test_a_late_list_never_covers_the_newer_search(self):
        deck = self.deck()
        queue = self.held()
        deck._handle_trading_command("system_markets", {"system": "Sol"})
        deck._handle_trading_command("system_markets", {"system": "Colonia"})
        queue.pop()()  # Colonia answers first
        queue.pop()()  # then Sol, late
        self.assertEqual(self.shown(deck)["list"]["system"], "Colonia")

    def test_a_late_market_never_covers_the_newer_station(self):
        deck = self.deck()
        queue = self.held()
        deck._handle_trading_command("station", {"market_id": 101})
        deck._handle_trading_command("station", {"market_id": 102})
        self.assertTrue(self.shown(deck)["pending"], "opening: the page says so")
        queue.pop()()  # Daedalus answers first
        queue.pop()()  # then Abraham Lincoln, late
        station = self.shown(deck)
        self.assertEqual(station["remote"]["station"], "Daedalus")
        self.assertFalse(station["pending"])

    def test_a_new_system_clears_a_market_from_another(self):
        deck = self.deck()
        queue = self.held()
        deck._handle_trading_command("system_markets", {"system": "Sol"})
        queue.pop(0)()
        deck._handle_trading_command("station", {"market_id": 101})
        queue.pop(0)()
        self.assertEqual(self.shown(deck)["remote"]["system"], "Sol")
        deck._handle_trading_command("system_markets", {"system": "sol"})
        self.assertEqual(self.shown(deck)["remote"]["station"], "Abraham Lincoln", "the same system keeps it")
        deck._handle_trading_command("station", {"market_id": 102})
        deck._handle_trading_command("system_markets", {"system": "Colonia"})
        while queue:
            queue.pop(0)()
        station = self.shown(deck)
        self.assertIsNone(station["remote"], "Sol's market (even one still opening) goes for Colonia")
        self.assertEqual(station["list"]["system"], "Colonia")

    def test_the_search_sits_beside_the_market(self):
        page = (WEB / "dashboard" / "trading.js").read_text(encoding="utf-8")
        self.assertIn('<div class="tr-market-split">${search}<div class="tr-market-shown">${shown}</div></div>', page)
        self.assertIn("list.pending", page, "the search's own state, not a shared busy flag")
        self.assertIn('class="tr-station-row${String(row.market_id) === openId ? " open" : ""}"', page)


if __name__ == "__main__":
    unittest.main()
