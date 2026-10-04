"""The journal's SurfaceGravity is m/s²; everything we show and judge is g.

A commander's 0.23 g icy world showed as "2.3 G": the old conversion only
divided above 5 m/s², so every world under 0.51 g came out ~9.8x too heavy,
which also skewed bio predictions and set off false gravity warnings."""

import unittest

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.dashboard_scan_mixin import DashboardScanMixin


class _Deck(DashboardScanMixin):
    _gravity_to_g = staticmethod(MainDashboard._gravity_to_g)

    @staticmethod
    def _bio_location_context():
        return None, None


class GravityUnitTests(unittest.TestCase):
    def test_journal_gravity_is_always_divided(self):
        to_g = MainDashboard._gravity_to_g
        self.assertEqual(to_g(2.255), 0.23, "Hypi Eurk RH-A b28-0 2, 0.23 G in game")
        self.assertEqual(to_g(4.9), 0.5)
        self.assertEqual(to_g(9.80665), 1.0)
        self.assertEqual(to_g(29.4), 3.0)
        self.assertIsNone(to_g(None))
        self.assertIsNone(to_g("n/a"))

    def test_saved_scans_are_repaired_on_load(self):
        deck = _Deck()
        stale = {"planet_class": "Icy body", "atmosphere_type": "Argon", "surface_temp": 80.0,
                 "surface_gravity": 2.255, "gravity_g": 2.26, "volcanism": "", "surface_pressure": 2000.0,
                 "predicted_genuses": []}
        self.assertTrue(deck._repair_scan_item_gravity(stale))
        self.assertEqual(stale["gravity_g"], 0.23)
        self.assertFalse(deck._repair_scan_item_gravity(stale), "a correct scan is left alone")
        self.assertFalse(deck._repair_scan_item_gravity({"gravity_g": 0.4}), "nothing to work from")


if __name__ == "__main__":
    unittest.main()
