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


if __name__ == "__main__":
    unittest.main()
