"""The overview survey must surface unfinished journal work before passive finds."""

import unittest

from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin


class SurveyHarness(HtmlDashboardMixin):
    def __init__(self, rows):
        self.current_sys = "Test Sector AB-C d1"
        self.scan_items = rows
        self.scanned = len(rows)
        self.total = len(rows)
        self.scan_total_confirmed = True
        self.valuable_bodies = []
        self.star_class = "K"
        self.system_bio_signals = 2
        self.organic_count = 0
        self.system_undiscovered = False
        self.body_signals = {}
        self._edsm_orrery_bodies = {}
        self._edsm_orrery_pending = set()


class DashboardSurveyPriorityTests(unittest.TestCase):
    def test_unfinished_biology_leads_and_overflow_count_is_preserved(self):
        rows = [
            {"body_id": body_id, "name": f"Mapped world {body_id}",
             "planet_class": "Earthlike body", "dss_complete": True}
            for body_id in range(1, 10)
        ]
        rows.append({
            "body_id": 10, "name": "Biological target", "planet_class": "Rocky body",
            "bio_count": 2, "organic_complete_count": 1, "dss_complete": False,
        })
        survey = SurveyHarness(rows)._html_dashboard_survey({})
        self.assertEqual(survey["notable_total"], 10)
        self.assertEqual(len(survey["notables"]), 8)
        self.assertTrue(survey["notables"][0].startswith("Biological target · BIO 1/2"))
        self.assertEqual(survey["bodies"][0]["body_id"], 1)

    def test_unmapped_valuable_world_precedes_completed_find(self):
        rows = [
            {"body_id": 1, "name": "Already mapped", "planet_class": "Water world",
             "dss_complete": True},
            {"body_id": 2, "name": "Map this world", "planet_class": "Water world",
             "dss_complete": False},
        ]
        survey = SurveyHarness(rows)._html_dashboard_survey({})
        self.assertEqual(survey["notables"][0], "Map this world · DSS PENDING")
        self.assertEqual(survey["notable_total"], 2)

    def test_every_scanned_planet_is_available_and_latest_scan_is_marked(self):
        rows = [
            {"body_id": body_id, "name": f"World {body_id}",
             "planet_class": "Rocky body", "rings": []}
            for body_id in range(35, 0, -1)
        ]
        rows[0]["rings"] = [{"Name": "World 35 A Ring"}]
        rows[0]["scan_timestamp"] = "2026-09-25T01:30:00Z"
        rows[1]["scan_timestamp"] = "2026-09-25T01:20:00Z"
        rows.insert(0, {"body_id": 0, "name": "Main star", "is_star": True,
                        "star_type": "K", "scan_timestamp": "2026-09-25T01:40:00Z"})
        survey = SurveyHarness(rows)._html_dashboard_survey({})
        self.assertEqual(len(survey["bodies"]), 35)
        self.assertEqual(survey["bodies"][0]["body_id"], 1)
        self.assertEqual(survey["bodies"][-1]["body_id"], 35)
        latest = [row for row in survey["bodies"] if row["latest_scan"]]
        self.assertEqual([row["body_id"] for row in latest], [35])
        self.assertEqual(latest[0]["ring_count"], 1)
        self.assertEqual(survey["bodies"][0]["ring_count"], 0)

    def test_surface_signal_before_scan_stays_unclassified(self):
        harness = SurveyHarness([{
            "body_id": 2, "name": "Scanned world", "planet_class": "Water world",
            "bio_count": 0, "rings": [],
        }])
        harness.body_signals = {
            2: {"bio": 3, "geo": 0, "body_name": "Scanned world"},
            "7": {"bio": 2, "geo": 1, "body_name": "Unscanned world"},
        }
        survey = harness._html_dashboard_survey({})
        scanned, unscanned = survey["bodies"]
        self.assertEqual(scanned["bio_count"], 3)
        self.assertEqual(scanned["planet_class"], "Water world")
        self.assertTrue(scanned["latest_scan"])
        self.assertEqual(unscanned["name"], "Unscanned world")
        self.assertEqual(unscanned["planet_class"], "")
        self.assertEqual(unscanned["type"], "")
        self.assertIsNone(unscanned["ring_count"])
        self.assertFalse(unscanned["latest_scan"])
        self.assertTrue(unscanned["signal_only"])
        self.assertTrue(unscanned["priority"])
        self.assertEqual(unscanned["badge"], "SIGNAL")
        self.assertEqual(unscanned["detail"], "SIGNAL DETECTED · BIO 2 · GEO 1")

    def test_mining_signal_does_not_claim_a_scan(self):
        harness = SurveyHarness([])
        harness.body_signals = {
            5: {"bio": 0, "geo": 0, "mining": 3, "body_name": "Mining contact"},
        }
        survey = harness._html_dashboard_survey({})
        self.assertEqual(len(survey["bodies"]), 1)
        self.assertEqual(survey["bodies"][0]["badge"], "SIGNAL")
        self.assertEqual(survey["bodies"][0]["detail"], "SIGNAL DETECTED · MINING 3")
        self.assertFalse(survey["bodies"][0]["latest_scan"])

    def test_latest_journal_timestamp_wins_over_cache_order(self):
        survey = SurveyHarness([
            {"body_id": 4, "name": "Earlier world", "planet_class": "Icy body",
             "scan_timestamp": "2026-09-25T01:00:00Z"},
            {"body_id": 6, "name": "Later world", "planet_class": "Rocky body",
             "scan_timestamp": "2026-09-25T02:00:00Z"},
        ])._html_dashboard_survey({})
        self.assertEqual(
            [row["body_id"] for row in survey["bodies"] if row["latest_scan"]], [6]
        )

    def test_synthetic_biology_record_is_not_a_scan(self):
        survey = SurveyHarness([{
            "body_id": 9, "name": "Organic contact", "planet_class": "Unknown",
            "bio_count": 1,
        }])._html_dashboard_survey({})
        self.assertFalse(survey["bodies"][0]["latest_scan"])


if __name__ == "__main__":
    unittest.main()
