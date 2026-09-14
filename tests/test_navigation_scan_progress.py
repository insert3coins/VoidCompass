import unittest

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.overlays.hud import TacticalHUD


class NavigationScanProgressTests(unittest.TestCase):
    @staticmethod
    def _dashboard(scanned=3, total=42):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.scanned = scanned
        dashboard.total = total
        dashboard.navigation_scan_progress = None
        dashboard.navigation_scan_progress_source = "bodies"
        return dashboard

    def test_return_visit_uses_partial_frontier_fss_progress(self):
        dashboard = self._dashboard()
        dashboard._seed_navigation_scan_progress()
        dashboard._record_navigation_fss_progress(0.106271)

        self.assertAlmostEqual(dashboard.navigation_scan_progress, 0.106271)
        self.assertEqual(dashboard.navigation_scan_progress_source, "fss")

        pct, label = TacticalHUD._scan_progress_state(
            dashboard.scanned,
            dashboard.total,
            {
                "scan_progress": dashboard.navigation_scan_progress,
                "scan_progress_source": dashboard.navigation_scan_progress_source,
            },
        )
        self.assertAlmostEqual(pct, 0.106271)
        self.assertEqual(label, "3/42  ·  FSS 10%")

    def test_live_progress_never_moves_behind_known_body_ratio(self):
        dashboard = self._dashboard(scanned=10, total=20)
        dashboard._seed_navigation_scan_progress()
        dashboard._record_navigation_fss_progress(0.2)

        self.assertEqual(dashboard.navigation_scan_progress, 0.5)

    def test_body_count_fallback_remains_unchanged(self):
        pct, label = TacticalHUD._scan_progress_state(
            5, 10, {"scan_progress_source": "bodies"},
        )

        self.assertEqual(pct, 0.5)
        self.assertEqual(label, "5/10  ·  50%")

    def test_waypoint_route_presentation_keeps_target_progress_and_distance_together(self):
        route = TacticalHUD._route_presentation(
            {
                "route_mode": "WAYPOINT ROUTE",
                "next": "Next jump",
                "next_distance": "42.1 LY",
                "route_remaining": 3,
                "hops": [{"name": "Next jump"}],
            },
            "Beagle Point",
            (7, 18),
            (1, 4),
            (8, 18, "14,282 LY"),
        )

        self.assertTrue(route["active"])
        self.assertEqual(route["source"], "WAYPOINT ROUTE")
        self.assertEqual(route["target"], "BEAGLE POINT")
        self.assertEqual(route["meta"], "3 JUMPS · 14,282 LY · 7/18 STOPS")
        self.assertAlmostEqual(route["progress"], 7 / 18)

    def test_no_route_is_explicit_without_fake_progress(self):
        route = TacticalHUD._route_presentation(
            {"route_mode": "NO ROUTE", "next": "---", "next_distance": "--"},
            None, None, None, None,
        )

        self.assertFalse(route["active"])
        self.assertEqual(route["source"], "NO ACTIVE ROUTE")
        self.assertEqual(route["target"], "NO DESTINATION PLOTTED")
        self.assertEqual(route["meta"], "")

    def test_survey_and_traffic_summaries_are_readable(self):
        self.assertEqual(
            TacticalHUD._survey_summary({
                "dss_complete": 4,
                "bio_complete": 2,
                "bio_signals": 3,
                "geo_signals": 7,
                "valuable_count": 1,
                "undiscovered": True,
            }),
            "DSS 4 · BIO 2/3 · GEO 7",
        )
        self.assertEqual(
            TacticalHUD._traffic_summary({"day": 1, "week": 6, "total": 42}),
            "TRAFFIC 1 TODAY · 6 THIS WEEK · 42 TOTAL",
        )

    def test_survey_rail_exposes_distinct_evidence_states(self):
        unknown = TacticalHUD._survey_rail_presentation(
            0, 0, 0, {"scan_progress_source": "unknown"},
        )
        live = TacticalHUD._survey_rail_presentation(
            4, 11, 4 / 11, {"scan_progress_source": "fss", "in_fss": True},
        )
        retained = TacticalHUD._survey_rail_presentation(
            4, 11, 4 / 11, {"scan_progress_source": "bodies"},
        )
        complete = TacticalHUD._survey_rail_presentation(
            11, 11, 1, {"scan_progress_source": "bodies", "dss_complete": 2},
        )

        self.assertEqual(unknown["state"], "unknown")
        self.assertEqual(live["state"], "live")
        self.assertIn("7 REMAINS", live["label"])
        self.assertEqual(retained["state"], "retained")
        self.assertIn("RECORDED SURVEY", retained["label"])
        self.assertEqual(complete["state"], "complete")
        self.assertEqual(complete["label"], "COMPLETE")


if __name__ == "__main__":
    unittest.main()
