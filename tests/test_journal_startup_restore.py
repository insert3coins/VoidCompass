import json
import os
import tempfile
import unittest

from voidcompass.core.journal_watcher import JournalWatcher


class JournalStartupRestoreTests(unittest.TestCase):
    def test_startup_catchup_marks_only_final_batch_and_applies_location_first(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "Journal.2026-07-16T120000.01.log")
            rows = [
                {"timestamp": "2026-07-16T12:00:00Z", "event": "Fileheader"},
                {"timestamp": "2026-07-16T12:00:01Z", "event": "Location", "StarSystem": "Sol"},
            ]
            rows.extend(
                {"timestamp": f"2026-07-16T12:00:0{index}Z", "event": "Music", "MusicTrack": "Exploration"}
                for index in range(2, 8)
            )
            with open(path, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")

            batches = []
            watcher = JournalWatcher(folder, config={
                "watcher_startup_max_lines_per_cycle": 5,
            })
            watcher.register_callback(batch_cb=lambda events: batches.append(events))

            watcher._check_journal()
            self.assertEqual(len(batches), 1)
            self.assertFalse(any(row.get("startup_catchup_final") for row in batches[0]))
            self.assertTrue(batches[0][0]["startup_location_seed"])
            self.assertEqual(batches[0][0]["type"], "Location")
            self.assertEqual(batches[0][0]["data"]["star_system"], "Sol")

            watcher._check_journal()
            self.assertEqual(len(batches), 2)
            self.assertTrue(batches[-1][-1]["startup_catchup_final"])
            self.assertEqual(batches[-1][-1]["type"], "Music")
            self.assertTrue(watcher._startup_catchup_done)

    def test_empty_journal_still_completes_startup_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "Journal.2026-07-16T130000.01.log")
            open(path, "w", encoding="utf-8").close()
            batches = []
            watcher = JournalWatcher(folder, config={})
            watcher.register_callback(batch_cb=lambda events: batches.append(events))

            watcher._check_journal()

            self.assertEqual(len(batches), 1)
            self.assertEqual(batches[0][0]["type"], "StartupCatchupComplete")
            self.assertTrue(batches[0][0]["startup_catchup_final"])
            self.assertTrue(watcher._startup_catchup_done)


if __name__ == "__main__":
    unittest.main()
