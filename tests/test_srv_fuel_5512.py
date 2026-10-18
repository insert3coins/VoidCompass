"""5.5.12: out in an SRV the game says the ship's tank is empty and puts the
SRV's own fuel in FuelReservoir. Void Compass learns each vehicle's tank and
tracks its fuel as a percentage; the Watcher never calls the Rhino empty."""

import unittest
from pathlib import Path
from unittest.mock import Mock

from voidcompass.dashboard.dashboard_scan_mixin import DashboardScanMixin
from voidcompass.overlays import watcher_lines
from voidcompass.overlays.watcher_mind import WatcherMind

ROOT = Path(__file__).resolve().parents[1]


class Deck(DashboardScanMixin):
    def __init__(self, vehicle="RHINO"):
        self.current_vehicle_name = vehicle
        self.current_in_srv = True
        self.current_in_fighter = False
        self.current_fuel_main = 0.0
        self.fuel_capacity_main = 32.0
        self.current_surface_fuel_reservoir = None
        self.companion_state = {"surface_tanks": {}}
        self._save_companion_state = Mock()


class TankTests(unittest.TestCase):
    def test_learnt_from_the_fullest_reading(self):
        deck = Deck()
        self.assertIsNone(deck._watcher_fuel_percent(), "unknown tank: no figure, never the ship's 0%")
        for reading in (0.80, 0.78):
            deck.current_surface_fuel_reservoir = reading
            deck._learn_surface_tank(reading)
        self.assertEqual(deck.companion_state["surface_tanks"], {"RHINO": 0.8})
        self.assertEqual(deck._save_companion_state.call_count, 1, "saved when it grows, not every reading")
        deck.current_surface_fuel_reservoir = 0.2
        self.assertEqual(deck._watcher_fuel_percent(), 25.0)
        self.assertEqual(deck._surface_fuel_percent(), 25.0)

    def test_each_vehicle_its_own_tank(self):
        deck = Deck("SCARAB")
        deck._learn_surface_tank(0.45)
        deck.current_vehicle_name = "RHINO"
        deck._learn_surface_tank(0.8)
        self.assertEqual(deck.companion_state["surface_tanks"], {"SCARAB": 0.45, "RHINO": 0.8})

    def test_back_in_the_ship_its_the_ship(self):
        deck = Deck()
        deck.current_in_srv = False
        deck.current_fuel_main = 8.0
        self.assertEqual(deck._watcher_fuel_percent(), 25.0)

    def test_the_status_reading_feeds_it(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard_scan_mixin.py").read_text(encoding="utf-8")
        self.assertIn("self._learn_surface_tank(reservoir)", source)
        self.assertIn('"fuel_vehicle":', source)
        hud = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("fuel_percent = self._surface_fuel_percent() if surface_vehicle_fuel else self._current_fuel_percent()", hud)


class DeckTests(unittest.TestCase):
    def test_logging_in_out_in_the_rhino_keeps_the_ships_fuel(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('if d.get("fuel_level") is not None and float(fuel_capacity or 0) > 0:', source)

    def test_the_departure_checks_show_the_vehicles_tank_too(self):
        from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
        deck = HtmlDashboardMixin.__new__(HtmlDashboardMixin)
        deck.config = {}
        from types import SimpleNamespace
        deck.root = SimpleNamespace()
        flight = {"fuel_percent": 71.0, "vehicle_fuel": {"name": "RHINO", "percent": 20.0, "tonnes": 0.16}}
        checks = {row["id"]: row for row in deck._html_exploration_preflight({}, flight, {})["checks"]}
        self.assertEqual((checks["fuel"]["value"], checks["fuel"]["status"]), ("71%", "ready"), "the ship's own tank")
        self.assertEqual((checks["vehicle_fuel"]["label"], checks["vehicle_fuel"]["value"], checks["vehicle_fuel"]["status"]),
                         ("Rhino fuel", "20%", "warn"))
        flight["vehicle_fuel"]["percent"] = None
        checks = {row["id"]: row for row in deck._html_exploration_preflight({}, flight, {})["checks"]}
        self.assertEqual(checks["vehicle_fuel"]["value"], "0.16 T")
        flight.pop("vehicle_fuel")
        checks = {row["id"]: row for row in deck._html_exploration_preflight({}, flight, {})["checks"]}
        self.assertNotIn("vehicle_fuel", checks, "in the ship, just the ship")


class WatcherTests(unittest.TestCase):
    def mind(self):
        mind = WatcherMind(memory_path=None, config={})
        mind.session_start()
        said = []
        mind.consider = lambda topic, fields=None, force=False: said.append((topic, dict(fields or {})))
        return mind, said

    def test_rhino_fuel_has_its_own_words_once(self):
        mind, said = self.mind()
        mind.vitals(20.0, vehicle="rhino")
        mind.vitals(18.0, vehicle="rhino")
        self.assertEqual(said, [("srv_fuel_low", {"fuel": 20, "srv": "Rhino"})])
        mind.vitals(None, vehicle="rhino")
        self.assertEqual(len(said), 1, "no figure, no worry")
        mind.vitals(90.0, vehicle="rhino")
        mind.vitals(22.0, vehicle="rhino")
        self.assertEqual(len(said), 2, "a refill re-arms it")

    def test_the_ships_worry_is_separate(self):
        mind, said = self.mind()
        mind.vitals(20.0, vehicle="rhino")
        mind.vitals(20.0)
        self.assertEqual([topic for topic, _ in said], ["srv_fuel_low", "fuel_low"])

    def test_no_stars_to_scoop_from_a_rover(self):
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            lines = bank["srv_fuel_low"]
            self.assertGreaterEqual(len(lines), 10)
            for line in lines:
                self.assertNotIn("scoop", line.casefold())
                self.assertIn("{fuel}", line)


if __name__ == "__main__":
    unittest.main()
