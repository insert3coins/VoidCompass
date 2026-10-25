"""5.6.4: starting with the game running. The journal catch-up keeps its
small batches but no longer waits a second between them, so a long
session's journal is caught up in a moment, not 11 seconds; and each close
is timed, step by step, into logs/shutdown.log."""

import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from voidcompass.core.diagnostic_logs import LOG_ARCHIVE_LIMIT, ShutdownClock
from voidcompass.core.journal_watcher import JournalWatcher


class CatchUpTests(unittest.TestCase):
    def test_a_long_journal_is_caught_up_quickly(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "Journal.2026-10-25T104105.01.log")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": "2026-10-25T10:41:05Z", "event": "Fileheader", "part": 1}) + "\n")
            for line in range(600):
                handle.write(json.dumps({"timestamp": "2026-10-25T10:42:00Z", "event": "FSSSignalDiscovered",
                                         "SystemAddress": line, "SignalName": f"Signal {line} " + "x" * 160}) + "\n")
        batches = []
        watcher = JournalWatcher(folder)
        watcher.register_callback(event_cb=lambda event: None, batch_cb=batches.append)
        began = time.monotonic()
        watcher.start()
        try:
            while not watcher._startup_catchup_done and time.monotonic() - began < 20:
                time.sleep(.02)
        finally:
            watcher.stop()
        took = time.monotonic() - began
        self.assertTrue(watcher._startup_catchup_done)
        self.assertGreater(len(batches), 10, "still in small batches, for the UI")
        self.assertLess(took, 4.0, f"caught up in {took:.1f} s")

    def test_once_live_it_checks_once_a_second(self):
        watcher = JournalWatcher(tempfile.mkdtemp())
        self.assertEqual(watcher._cycle_pause(), .05)
        watcher._startup_catchup_done = True
        self.assertEqual(watcher._cycle_pause(), 1.0)


class ShutdownClockTests(unittest.TestCase):
    def test_each_session_archives_the_previous_close_and_keeps_ten_archives(self):
        folder = tempfile.mkdtemp()
        moment = [0.0]
        for close in range(22):
            clock = ShutdownClock(clock=lambda: moment[0])
            moment[0] += .4
            clock.mark(f"overlay host {close}")
            moment[0] += .002
            clock.mark("a quick one")
            clock.write(base_dir=folder)
            moment[0] += .1
            clock.mark("app window closed")
            clock.write(base_dir=folder)
        log_dir = os.path.join(folder, "logs")
        with open(os.path.join(log_dir, "shutdown.log"), encoding="utf-8") as handle:
            current = handle.read()
        archives = [path for path in os.listdir(log_dir)
                    if path != "shutdown.log" and path.startswith("shutdown.") and path.endswith(".log")]
        self.assertEqual(current.count("=== close "), 1, "the current file contains this session only")
        self.assertIn("overlay host 21", current)
        self.assertIn("400 ms  overlay host 21", current)
        self.assertIn("100 ms  app window closed", current)
        self.assertNotIn("a quick one", current, "steps under 10 ms are left out")
        self.assertIn("· 0.50 s ===", current)
        self.assertEqual(len(archives), LOG_ARCHIVE_LIMIT)
        archive_texts = [(Path(log_dir) / name).read_text(encoding="utf-8") for name in archives]
        self.assertTrue(all("app window closed" in text for text in archive_texts), "the two writes stay in one session file")
        self.assertTrue(any("overlay host 20" in text for text in archive_texts))
        self.assertFalse(any("overlay host 10" in text for text in archive_texts), "old sessions are pruned")

    def test_the_close_is_timed(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        body = source[source.index("    def on_close(self):"):source.index("    def _save_watcher_memory(self):")]
        for step in ("overlay host", "command deck host", "database closed", "files written", "app window closed"):
            self.assertIn(f'clock.mark("{step}")', body)
        self.assertEqual(body.count("clock.write()"), 2, "written before the window goes, and after")


if __name__ == "__main__":
    unittest.main()
