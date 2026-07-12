import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import flight_callouts  # noqa: E402
from dashboard_scan_mixin import DashboardScanMixin  # noqa: E402


class FlightCalloutTests(unittest.TestCase):
    def test_scoopable_star_classes(self):
        for star_class in ("O", "B", "A", "F", "G", "K", "M", "TTS", "AeBe"):
            self.assertTrue(flight_callouts.is_scoopable(star_class), star_class)
        for star_class in ("L", "T", "Y", "N", "H", "D", "DA", "MS"):
            self.assertFalse(flight_callouts.is_scoopable(star_class), star_class)

    def test_route_ahead_handles_full_and_upcoming_only_routes(self):
        entries = [
            {"StarSystem": "Sol", "StarClass": "G"},
            {"StarSystem": "Dry One", "StarClass": "L"},
            {"StarSystem": "Fuel", "StarClass": "K"},
        ]
        full = flight_callouts.route_ahead(entries, "Sol", "G")
        self.assertEqual([row["system"] for row in full], ["Sol", "Dry One", "Fuel"])
        upcoming = flight_callouts.route_ahead(entries[1:], "Sol", "G")
        self.assertEqual([row["system"] for row in upcoming], ["Sol", "Dry One", "Fuel"])

    def test_dry_stretch_warns_at_scoopable_star(self):
        ahead = [
            {"system": "Fuel", "scoopable": True},
            {"system": "Dry One", "scoopable": False},
            {"system": "Dry Two", "scoopable": False},
            {"system": "Fuel Two", "scoopable": True},
        ]
        advisory = flight_callouts.fuel_advisory(ahead, 20, 32, None)
        self.assertEqual(advisory["code"], "dry_stretch")

    def test_scoop_now_beats_generic_low_fuel(self):
        ahead = [
            {"system": "Fuel", "scoopable": True},
            {"system": "Dry One", "scoopable": False},
            {"system": "Dry Two", "scoopable": False},
            {"system": "Fuel Two", "scoopable": True},
        ]
        advisory = flight_callouts.fuel_advisory(ahead, 2, 32, 1.1)
        self.assertEqual(advisory["code"], "scoop_now")

    def test_strand_warning_mentions_available_jumponium(self):
        ahead = [
            {"system": "Dry", "scoopable": False},
            {"system": "Dry Two", "scoopable": False},
            {"system": "Fuel", "scoopable": True},
        ]
        advisory = flight_callouts.fuel_advisory(
            ahead, 1, 32, 1.1, {"basic": 0, "standard": 0, "premium": 2}
        )
        self.assertEqual(advisory["code"], "strand_risk")
        self.assertIn("100 percent range boost", advisory["say"])

    def test_dashboard_route_advisory_is_one_shot_until_situation_changes(self):
        class Dashboard(DashboardScanMixin):
            def __init__(self):
                self.config = {"voice_callouts_enabled": True, "voice_safety_enabled": True}
                self.is_first_load = False
                self.current_sys = "Fuel"
                self.star_class = "K"
                self.current_fuel_main = 20
                self.fuel_capacity_main = 32
                self._fuel_used_samples = []
                self._fuel_advisory_signature = None
                self.engineer_materials = {"raw": {}}
                self.nav_route_entries = [
                    {"StarSystem": "Fuel", "StarClass": "K"},
                    {"StarSystem": "Dry One", "StarClass": "L"},
                    {"StarSystem": "Dry Two", "StarClass": "T"},
                    {"StarSystem": "Fuel Two", "StarClass": "G"},
                ]
                self.spoken = []

            def _speak(self, text, **kwargs):
                self.spoken.append((text, kwargs))
                return True

        dashboard = Dashboard()
        dashboard._check_route_fuel_callout()
        dashboard._check_route_fuel_callout()
        self.assertEqual(len(dashboard.spoken), 1)
        self.assertIn("next 2 jumps", dashboard.spoken[0][0])


if __name__ == "__main__":
    unittest.main()
