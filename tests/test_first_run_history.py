"""First run reads the commander's history (5.5.1.3): journals in their real
order across Frontier's two name formats, the commander found in the newest
journals that have one, the newest session's header replayed ahead of the
clipped startup tail, and the full journal scan once setup is done."""

import json
import os
import tempfile
import unittest
from unittest.mock import Mock

from voidcompass.core import journal_files
from voidcompass.core.journal_watcher import JournalWatcher
from voidcompass.dashboard.dashboard import MainDashboard


def write(folder, name, rows):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def session(commander="Jameson", ship="Krait Phantom", system="Sol", padding=0):
    return [
        {"event": "Fileheader"},
        {"event": "Commander", "Name": commander, "FID": "F1"},
        {"event": "Materials", "Raw": []},
        {"event": "LoadGame", "Commander": commander, "FID": "F1", "Ship_Localised": ship, "ShipName": "Lantern", "Credits": 1000},
        {"event": "Rank", "Combat": 3},
        {"event": "Location", "StarSystem": system},
        *({"event": "Music", "MusicTrack": "Exploration", "pad": "x" * 200} for _ in range(padding)),
    ]


class JournalOrderTests(unittest.TestCase):
    def test_both_name_formats_sort_by_date(self):
        names = ["Journal.2026-01-02T100000.01.log", "Journal.211231093407.01.log", "Journal.190101101010.01.log",
                 "Journal.2022-01-01T000000.02.log", "Journal.2022-01-01T000000.01.log"]
        self.assertEqual(sorted(names, key=journal_files.journal_sort_key), [
            "Journal.190101101010.01.log", "Journal.211231093407.01.log",
            "Journal.2022-01-01T000000.01.log", "Journal.2022-01-01T000000.02.log", "Journal.2026-01-02T100000.01.log",
        ])
        self.assertEqual(journal_files.journal_date("Journal.211231093407.01.log").year, 2021)

    def test_the_watcher_follows_the_newest_journal_not_the_last_name(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.211231093407.01.log", session("Old"))
            write(folder, "Journal.2026-01-02T100000.01.log", session("New"))
            watcher = JournalWatcher(folder, config={})
            watcher._check_journal()
            self.assertTrue(watcher.last_journal.endswith("Journal.2026-01-02T100000.01.log"))


class CommanderDetectionTests(unittest.TestCase):
    def test_a_main_menu_launch_does_not_hide_the_commander(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.2026-09-30T081500.01.log", session())
            write(folder, "Journal.2026-10-01T081500.01.log", [{"event": "Fileheader"}, {"event": "Music"}])
            found = JournalWatcher.detect_latest_commander(folder)
            self.assertEqual((found["commander"], found["fid"]), ("Jameson", "F1"))
            latest = journal_files.latest_session(folder)
            self.assertEqual((latest["ship"], latest["system"]), ("Krait Phantom", "Sol"))

    def test_the_commander_at_the_top_of_a_long_journal_is_found(self):
        with tempfile.TemporaryDirectory() as folder:
            # Over 2 MB after the commander: the old tail read missed it.
            write(folder, "Journal.2026-09-30T081500.01.log", session(padding=12000))
            self.assertEqual(JournalWatcher.detect_latest_commander(folder)["commander"], "Jameson")

    def test_no_journals_means_no_commander(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(JournalWatcher.detect_latest_commander(folder))


class SessionHeaderTests(unittest.TestCase):
    def test_a_first_run_replays_the_header_ahead_of_the_clipped_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.2026-09-30T081500.01.log", session(padding=1500))
            batches = []
            watcher = JournalWatcher(folder, config={"watcher_startup_tail_bytes": 32768})
            watcher.seed_session_header = True
            watcher.register_callback(batch_cb=lambda events: batches.append(events))
            watcher._check_journal()
            first = batches[0]
            seeded = [event["type"] for event in first if event.get("startup_header_seed")]
            self.assertEqual(seeded, ["Commander", "Materials", "LoadGame", "Rank"])
            self.assertTrue(first[0].get("startup_header_seed"), "the header comes before the tail")
            self.assertTrue(all(event.get("startup_catchup") for event in first))

    def test_without_the_flag_or_with_a_short_journal_nothing_is_added(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.2026-09-30T081500.01.log", session(padding=1500))
            batches = []
            watcher = JournalWatcher(folder, config={"watcher_startup_tail_bytes": 32768})
            watcher.register_callback(batch_cb=lambda events: batches.append(events))
            watcher._check_journal()
            self.assertFalse(any(event.get("startup_header_seed") for event in batches[0]))
        with tempfile.TemporaryDirectory() as folder:
            # The whole journal fits in the tail, which replays it anyway.
            write(folder, "Journal.2026-09-30T081500.01.log", session())
            path = os.path.join(folder, "Journal.2026-09-30T081500.01.log")
            self.assertEqual(journal_files.session_header(folder, path, 32768), [])

    def test_a_main_menu_launch_takes_the_header_from_the_session_before(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, "Journal.2026-09-30T081500.01.log", session(commander="Jameson") + [{"event": "Rank", "Combat": 4}])
            write(folder, "Journal.2026-10-01T081500.01.log", [{"event": "Fileheader"}])
            live = os.path.join(folder, "Journal.2026-10-01T081500.01.log")
            header = journal_files.session_header(folder, live, 32768)
            self.assertEqual([row["event"] for row in header], ["Commander", "Materials", "LoadGame", "Rank"])
            self.assertEqual(header[-1]["Combat"], 4, "the last of each kind")


class FirstRunScanTests(unittest.TestCase):
    def dashboard(self, first_run):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard._first_run_scan_pending = first_run
        dashboard._startup_history_pending = {"exploration"}
        dashboard._startup_boot_history_timeout_job = None
        dashboard._trace_bump = Mock()
        dashboard._startup_boot_update = Mock()
        dashboard._maybe_complete_startup_presentation = Mock()
        dashboard.add_event_feed_entry = Mock()
        dashboard.scan_all_logs_threaded = Mock(return_value=True)
        return dashboard

    def test_the_full_scan_runs_once_after_setup_without_an_edsm_upload(self):
        dashboard = self.dashboard(first_run=True)
        dashboard._startup_history_phase_complete("exploration")
        dashboard.scan_all_logs_threaded.assert_called_once_with(upload_history_to_edsm=False)
        self.assertFalse(dashboard._first_run_scan_pending)
        dashboard._startup_history_pending = {"carrier"}
        dashboard._startup_history_phase_complete("carrier")
        dashboard.scan_all_logs_threaded.assert_called_once()

    def test_an_ordinary_start_does_not_scan(self):
        dashboard = self.dashboard(first_run=False)
        dashboard._startup_history_phase_complete("exploration")
        dashboard.scan_all_logs_threaded.assert_not_called()


if __name__ == "__main__":
    unittest.main()
