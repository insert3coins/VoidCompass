"""The current-system scan cache must not hide bodies from Survey Operations."""

import json
import sqlite3
import threading
import unittest

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.dashboard_db_mixin import DashboardDBMixin
from voidcompass.dashboard.dashboard_scan_mixin import DashboardScanMixin
from voidcompass.overlays.survey_status_hud import build_survey_model


class _ScanCache(DashboardScanMixin):
    def __init__(self):
        self.current_sys = "Large System"
        self.current_system_address = None
        self.scan_items = []
        self.scan_items_by_id = {}
        self.body_signals = {}
        self.body_dss_complete = set()
        self.saved = {}

    @staticmethod
    def _gravity_to_g(value):
        return None

    @staticmethod
    def _bio_location_context():
        return None, None

    @staticmethod
    def _get_body_value(*args):
        return 0

    def save_scan_item_to_db(self, system_name, item):
        self.saved[item["body_id"]] = dict(item)


class _StoredScanCache(DashboardDBMixin):
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.db_lock = threading.RLock()
        self.conn.execute(
            "CREATE TABLE scan_hud_items (system_name TEXT, body_id INTEGER, "
            "data_json TEXT, ts INTEGER, PRIMARY KEY (system_name, body_id))"
        )


class SurveyLargeSystemCacheTests(unittest.TestCase):
    def test_live_scan_cache_and_survey_keep_more_than_100_bodies(self):
        cache = _ScanCache()
        for body_id in range(1, 122):
            cache.add_scan_item({
                "BodyID": body_id,
                "BodyName": f"Large System A {body_id}",
                "PlanetClass": "Rocky body",
            })

        self.assertEqual(len(cache.scan_items), 121)
        self.assertEqual(len(cache.scan_items_by_id), 121)
        self.assertEqual(len(cache.saved), 121)
        model = build_survey_model(
            cache.current_sys, cache.scan_items, show_all_bodies=True,
        )
        self.assertEqual(len(model["rows"]), 121)

    def test_db_hydration_restores_all_current_system_bodies(self):
        cache = _StoredScanCache()
        self.addCleanup(cache.conn.close)
        for body_id in range(1, 122):
            cache.conn.execute(
                "INSERT INTO scan_hud_items VALUES (?, ?, ?, ?)",
                ("Large System", body_id, json.dumps({
                    "body_id": body_id,
                    "name": f"Large System A {body_id}",
                    "planet_class": "Rocky body",
                }), body_id),
            )
        cache.conn.execute(
            "INSERT INTO scan_hud_items VALUES (?, ?, ?, ?)",
            ("Another System", 999, json.dumps({"body_id": 999}), 999),
        )

        restored = cache.load_scan_items_from_db("Large System")
        self.assertEqual(len(restored), 121)
        self.assertEqual(restored[0]["body_id"], 121)
        self.assertEqual({row["body_id"] for row in restored}, set(range(1, 122)))

    def test_organic_fallback_does_not_evict_older_body(self):
        class FallbackCache:
            scan_items = [{"body_id": body_id} for body_id in range(1, 102)]
            scan_items_by_id = {row["body_id"]: row for row in scan_items}
            body_signals = {}
            body_scan_data = {}

            @staticmethod
            def _normalize_body_id(value):
                return int(value)

            @staticmethod
            def _normalize_scan_item(item):
                pass

        cache = FallbackCache()
        MainDashboard._scan_item_for_bio_body(cache, 102, "Large System A 102")
        self.assertEqual(len(cache.scan_items), 102)
        self.assertEqual(cache.scan_items[-1]["body_id"], 101)


if __name__ == "__main__":
    unittest.main()
