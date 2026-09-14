import unittest

from voidcompass.core.config import PROFILE_TEXT_SETTINGS
from voidcompass.exploration.deep_survey import expedition_report_markdown


class DeepSurveyReportTests(unittest.TestCase):
    def test_report_scopes_journal_discoveries_to_selected_session(self):
        report = expedition_report_markdown(
            snapshot={
                "route_points": [
                    {"timestamp": "2026-07-26T10:05:00Z", "system": "Alpha", "jump_dist": 12.5},
                    {"timestamp": "2026-07-26T10:20:00Z", "system": "Beta", "jump_dist": 17.5},
                ],
                "codex": [
                    {"timestamp": "2026-07-25T09:00:00Z", "system": "Old", "name": "Old entry"},
                    {"timestamp": "2026-07-26T10:10:00Z", "system": "Alpha", "name": "New entry"},
                ],
                "dss": [
                    {"timestamp": "2026-07-26T10:12:00Z", "system": "Alpha", "efficient": True},
                ],
                "signals": [], "screenshots": [], "candidates": [],
            },
            session={
                "started": "2026-07-26T10:00:00Z", "ended": "2026-07-26T11:00:00Z",
                "start_system": "Alpha", "end_system": "Beta", "jumps": 2,
                "distance_ly": 30.0, "bio_analyses": 1,
            },
            current_system="Beta",
        )

        self.assertIn("Alpha → Beta", report)
        self.assertIn("2 jumps · 30.0 ly", report)
        self.assertIn("New entry", report)
        self.assertNotIn("Old entry", report)
        self.assertIn("DSS mappings: 1 (1 efficiency targets met)", report)

    def test_explore_view_preferences_are_profile_settings(self):
        for key in (
            "explore_active_page", "explore_survey_filter",
            "explore_discovery_filter", "explore_expedition_section",
        ):
            self.assertIn(key, PROFILE_TEXT_SETTINGS)


if __name__ == "__main__":
    unittest.main()
