"""5.5.1.6: a finished system read "one body to go" (33/34).

Mapping a planetary ring with probes logs DiscoveryScan "Bodies":1 after
FSSAllBodiesFound. DiscoveryScan used to add its count to the bodies already
scanned, so a complete 16/16 became 16/17 and could never finish. The
sequence below is the commander's own (Phrausky CW-U c16-0, 2026-08-21).
"""

import json
from pathlib import Path
import tempfile
import unittest

from voidcompass.core.journal_watcher import JournalWatcher
from voidcompass.dashboard.dashboard import MainDashboard

SYSTEM = "Phrausky CW-U c16-0"
ADDRESS = 1000


def app(scanned, total, *, honk=0, all_found=False, confirmed=True):
    dashboard = MainDashboard.__new__(MainDashboard)
    dashboard.scanned, dashboard.total = scanned, total
    dashboard._fss_honk_total = honk
    dashboard.fss_all_bodies = all_found
    dashboard.scan_total_confirmed = confirmed
    return dashboard


class DiscoveryScanTests(unittest.TestCase):
    def test_a_ring_mapped_after_all_bodies_found_changes_nothing(self):
        dashboard = app(16, 16, honk=16, all_found=True)
        self.assertFalse(dashboard._apply_discovery_scan(1))
        self.assertEqual((dashboard.scanned, dashboard.total), (16, 16))

    def test_after_a_honk_the_game_count_stands(self):
        dashboard = app(16, 16, honk=16)
        self.assertFalse(dashboard._apply_discovery_scan(1))
        self.assertEqual(dashboard.total, 16)
        # A return visit before any honk: the stored complete count stands too.
        dashboard = app(16, 16)
        self.assertFalse(dashboard._apply_discovery_scan(1))
        self.assertEqual(dashboard.total, 16)

    def test_without_a_game_count_it_still_reveals_bodies(self):
        dashboard = app(3, 3, confirmed=False)
        self.assertTrue(dashboard._apply_discovery_scan(2))
        self.assertEqual((dashboard.total, dashboard.scan_total_confirmed), (5, True))
        self.assertFalse(app(3, 3, confirmed=False)._apply_discovery_scan(0))


class HistoryRebuildTests(unittest.TestCase):
    def test_the_rebuilt_cache_keeps_the_game_count(self):
        events = [
            {"event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": ADDRESS},
            {"event": "FSSDiscoveryScan", "Progress": 0.16, "BodyCount": 16,
             "SystemName": SYSTEM, "SystemAddress": ADDRESS},
            *({"event": "Scan", "ScanType": "Detailed", "StarSystem": SYSTEM, "SystemAddress": ADDRESS,
               "BodyID": body, "BodyName": f"{SYSTEM} {body}", "PlanetClass": "Icy body"} for body in range(1, 17)),
            {"event": "FSSAllBodiesFound", "SystemName": SYSTEM, "SystemAddress": ADDRESS, "Count": 16},
            {"event": "DiscoveryScan", "SystemAddress": ADDRESS, "Bodies": 1},
        ]
        with tempfile.TemporaryDirectory() as folder:
            lines = "\n".join(json.dumps({"timestamp": "2026-08-21T08:00:00Z", **event}) for event in events)
            (Path(folder) / "Journal.2026-08-21T202708.01.log").write_text(lines + "\n", encoding="utf-8")
            watcher = JournalWatcher.__new__(JournalWatcher)
            watcher.journal_path = folder
            watcher.config = {}
            row = watcher.scan_history()[SYSTEM]
        self.assertEqual((row["scanned_count"], row["total"]), (16, 16))


if __name__ == "__main__":
    unittest.main()
