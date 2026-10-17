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
            # 5.5.10: the best payers within your radius, and the nearest.
            self.assertEqual(search.call_count, 2)
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
            self.assertEqual(search.call_count, 2, "switching never asks Spansh again")
        deck._handle_trading_command("cargo_sort", {"sort": "nonsense"})
        self.assertEqual(deck._trading_ui()["cargo_sort"], "price")

    def test_near_me_is_a_radius_you_choose(self):
        # 5.5.10: "near me" was Spansh's 30 nearest buyers (in the bubble,
        # all within about 20 ly). Now it's a radius, kept for the commander,
        # with the best payers inside it, and Find's market filters.
        self.run_inline()
        deck = self.deck()
        with patch.object(spansh, "market_field_values", return_value=fixture("field_values_market.json")),                 patch.object(spansh, "commodity_stations", return_value=fixture("commodity_sell_gold.json")) as search:
            deck._handle_trading_command("cargo", {"radius": "250", "large": 1, "carriers": 0, "planetary": 0})
            calls = [call.kwargs for call in search.call_args_list]
            self.assertEqual({call.get("sort", "distance") for call in calls}, {"price", "distance"})
            for call in calls:
                self.assertEqual((call["radius"], call["large_pad"], call["carriers"], call["planetary"]), (250, 1, 0, 0))
            self.assertEqual(deck._trading_ui()["cargo"]["radius"], 250)
        deck._handle_trading_command("view", {"view": "cargo"})
        self.assertEqual(deck._html_trading_workspace()["cargo_options"], {"radius": 250, "large": True, "carriers": False, "planetary": False})
        self.assertEqual(deck._trading_cargo_options({"radius": 99999})["radius"], 1000)

    def test_spansh_is_asked_within_the_radius_by_price(self):
        with patch.object(spansh, "_call", return_value={}) as call:
            spansh.commodity_stations("sell", "Sol", "Gold", 50, size=10, radius=120, sort="price")
        body = call.call_args.kwargs["body"]
        self.assertEqual(body["filters"]["distance"], {"min": 0, "max": 120})
        self.assertEqual(body["sort"], [{"market_sell_price": [{"name": "Gold", "direction": "desc"}]}])

    def test_the_page_has_the_radius(self):
        page = (WEB / "dashboard" / "trading.js").read_text(encoding="utf-8")
        for needle in ('data-trade-form="cargo"', 'name="radius_slider"', 'name="radius"', "NEAR ME MEANS WITHIN"):
            self.assertIn(needle, page)

    def test_the_page_has_the_switch(self):
        page = (WEB / "dashboard" / "trading.js").read_text(encoding="utf-8")
        self.assertIn('data-trade-op="cargo_sort" data-sort="distance"', page)
        self.assertIn("row.nearest", page)


if __name__ == "__main__":
    unittest.main()
