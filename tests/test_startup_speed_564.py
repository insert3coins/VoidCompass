"""5.6.4: starting with the game running. The journal catch-up keeps its
small batches but no longer waits a second between them, so a long
session's journal is caught up in a moment, not 11 seconds; and each close
is timed, step by step, into logs/shutdown.log."""

import json
import os
import tempfile
import time
import unittest

from voidcompass.core.diagnostic_logs import ShutdownClock
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
    def test_each_close_is_timed_and_the_last_twenty_kept(self):
        folder = tempfile.mkdtemp()
        moment = [0.0]
        for close in range(22):
            clock = ShutdownClock(clock=lambda: moment[0])
            moment[0] += .4
            clock.mark("overlay host")
            moment[0] += .002
            clock.mark("a quick one")
            clock.write(base_dir=folder)
            moment[0] += .1
            clock.mark("app window closed")
            clock.write(base_dir=folder)
        with open(os.path.join(folder, "logs", "shutdown.log"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count("=== close "), 20)
        self.assertIn("400 ms  overlay host", text)
        self.assertIn("100 ms  app window closed", text)
        self.assertNotIn("a quick one", text, "steps under 10 ms are left out")
        self.assertIn("· 0.50 s ===", text)

    def test_the_close_is_timed(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        body = source[source.index("    def on_close(self):"):source.index("    def _save_watcher_memory(self):")]
        for step in ("overlay host", "command deck host", "database closed", "files written", "app window closed"):
            self.assertIn(f'clock.mark("{step}")', body)
        self.assertEqual(body.count("clock.write()"), 2, "written before the window goes, and after")


if __name__ == "__main__":
    unittest.main()
