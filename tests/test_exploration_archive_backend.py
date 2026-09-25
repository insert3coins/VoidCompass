"""The Exploration Archive must distinguish missing data from a busy database."""

import json
import sqlite3
import threading
import unittest
from types import SimpleNamespace

from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin


class _ArchiveDashboard(HtmlDashboardMixin):
    def __init__(self):
        self.config = {"active_commander_profile": "archive-test"}
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE scan_hud_items (system_name TEXT, data_json TEXT)"
        )
        self.conn.execute(
            "INSERT INTO scan_hud_items VALUES (?, ?)",
            ("Test System", json.dumps({
                "body_id": 1, "name": "Test System A 1",
                "planet_class": "Water world", "landable": False,
            })),
        )
        self.db_lock = threading.Lock()
        self.deep_survey = SimpleNamespace(region_passport_state=lambda: {
            "1": {"visits": 1, "systems": ["Test System"]},
        })


class ExplorationArchiveBackendTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = _ArchiveDashboard()
        self.addCleanup(self.dashboard.conn.close)

    def test_busy_lock_without_cache_reports_loading_then_recovers(self):
        self.dashboard.db_lock.acquire()
        try:
            loading = self.dashboard._html_analytics_workspace()
        finally:
            self.dashboard.db_lock.release()

        self.assertEqual(loading["science_status"], {
            "state": "loading", "age_seconds": None,
        })
        self.assertNotIn("_html_science_lab_cache", self.dashboard.__dict__)
        self.assertEqual(loading["science"]["bodies"], 0)

        ready = self.dashboard._html_analytics_workspace()
        self.assertEqual(ready["science_status"], {
            "state": "ready", "age_seconds": 0.0,
        })
        self.assertEqual(ready["science"]["bodies"], 1)
        self.assertEqual(ready["passport"]["visited"], 1)

    def test_stale_same_profile_data_survives_busy_lock_and_read_error(self):
        ready = self.dashboard._html_analytics_workspace()
        self.dashboard._html_science_lab_cache["time"] -= 7.0
        self.dashboard.db_lock.acquire()
        try:
            stale = self.dashboard._html_analytics_workspace()
        finally:
            self.dashboard.db_lock.release()

        self.assertEqual(stale["science_status"]["state"], "stale")
        self.assertGreaterEqual(stale["science_status"]["age_seconds"], 7)
        self.assertEqual(stale["science"], ready["science"])
        self.assertEqual(stale["passport"], ready["passport"])

        self.dashboard.conn.execute("DROP TABLE scan_hud_items")
        after_error = self.dashboard._html_analytics_workspace()
        self.assertEqual(after_error["science_status"]["state"], "stale")
        self.assertEqual(after_error["science"], ready["science"])

    def test_read_failure_does_not_cache_empty_or_leak_other_profile(self):
        original = self.dashboard._html_analytics_workspace()
        self.dashboard.config["active_commander_profile"] = "another-cmdr"
        self.dashboard.db_lock.acquire()
        try:
            other_profile = self.dashboard._html_analytics_workspace()
        finally:
            self.dashboard.db_lock.release()
        self.assertEqual(other_profile["science_status"]["state"], "loading")
        self.assertEqual(other_profile["science"]["bodies"], 0)
        self.assertEqual(self.dashboard._html_science_lab_cache["profile"], "archive-test")
        self.assertEqual(original["science"]["bodies"], 1)

        self.dashboard.conn.execute("DROP TABLE scan_hud_items")
        unavailable = self.dashboard._html_analytics_workspace()
        self.assertEqual(unavailable["science_status"]["state"], "unavailable")
        self.assertEqual(unavailable["science"]["bodies"], 0)
        self.assertEqual(self.dashboard._html_science_lab_cache["profile"], "archive-test")


if __name__ == "__main__":
    unittest.main()
