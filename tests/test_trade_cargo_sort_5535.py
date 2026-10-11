"""5.5.3.5: Sell cargo sorts by price or by distance.

It listed each commodity's best five payers among Spansh's 30 nearest
buyers. Now the five nearest are kept from the same search too, and BY PRICE
/ BY DISTANCE switches between them without asking Spansh again (Find
commodity already had the same switch)."""

from pathlib import Path
import unittest
from unittest.mock import patch

from tests.test_trading import TabTests, fixture
from voidcompass.services import spansh

WEB = Path(__file__).resolve().parents[1] / "web"


class CargoSortTests(unittest.TestCase):
    deck = TabTests.deck
    run_inline = TabTests.run_inline

    def test_by_price_and_by_distance_from_one_search(self):
        self.run_inline()
        deck = self.deck()
        with patch.object(spansh, "market_field_values", return_value=fixture("field_values_market.json")), \
                patch.object(spansh, "commodity_stations", return_value=fixture("commodity_sell_gold.json")) as search:
            deck._handle_trading_command("cargo", {})
            self.assertEqual(search.call_count, 1)
            row = deck._trading_ui()["cargo"]["rows"][0]
            prices = [station["price"] for station in row["stations"]]
            self.assertEqual(prices, sorted(prices, reverse=True), "by price: the best payers")
            distances = [station["distance"] for station in row["nearest"]]
            self.assertEqual(distances, sorted(distances), "by distance: the nearest first")
            self.assertLessEqual(len(row["nearest"]), 5)
            deck._handle_trading_command("view", {"view": "cargo"})
            self.assertEqual(deck._html_trading_workspace()["cargo_sort"], "price", "by price until asked")
            deck._handle_trading_command("cargo_sort", {"sort": "distance"})
            self.assertEqual(deck._html_trading_workspace()["cargo_sort"], "distance")
            self.assertEqual(search.call_count, 1, "switching never asks Spansh again")
        deck._handle_trading_command("cargo_sort", {"sort": "nonsense"})
        self.assertEqual(deck._trading_ui()["cargo_sort"], "price")

    def test_the_page_has_the_switch(self):
        page = (WEB / "dashboard" / "trading.js").read_text(encoding="utf-8")
        self.assertIn('data-trade-op="cargo_sort" data-sort="distance"', page)
        self.assertIn("row.nearest", page)


if __name__ == "__main__":
    unittest.main()
