"""RESET THE WATCHER (5.5.3.9): it forgets everything, story and all, and
wakes again as it did the first time; asked twice, with a backup kept."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from voidcompass.overlays.watcher_mind import WatcherMind

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


def lived_in(test):
    """A Watcher with a past: sessions, hours, its story begun, an echo."""
    folder = Path(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, folder, True)
    path = folder / "watcher_memory.json"
    path.write_text(json.dumps({"sessions": 42, "hours": 310.5, "lore": [["salvage", 1.0], ["waking", 2.0]],
                                "echoes": {"lore_core": [1, 3.0]}, "afterword": None, "thoughts": 900,
                                "said": [["greet_new", 1.0]], "log": [[1.0, "greet_new", "Hello."]]}), encoding="utf-8")
    return path


class ResetTests(unittest.TestCase):
    def test_it_forgets_everything_and_keeps_a_copy(self):
        path = lived_in(self)
        clock = Clock()
        mind = WatcherMind(path, {"heartbeat_thoughts": "chatty"}, clock)
        self.assertEqual(mind.bond(), 3)
        backup = mind.reset()
        self.assertTrue(backup and Path(backup).exists(), "the old memory, kept beside it")
        self.assertEqual(json.loads(Path(backup).read_text(encoding="utf-8"))["sessions"], 42)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((saved["sessions"], saved["hours"], saved["lore"], saved["echoes"], saved["log"]), (0, 0.0, [], {}, []))
        self.assertEqual(mind.bond(), 0)
        again = WatcherMind(path, {"heartbeat_thoughts": "chatty"}, clock)
        self.assertEqual(again.memory["sessions"], 0, "and stays forgotten")

    def test_it_wakes_as_the_first_time(self):
        path = lived_in(self)
        clock = Clock()
        mind = WatcherMind(path, {"heartbeat_thoughts": "chatty"}, clock)
        mind.session_start()
        mind.reset()
        clock.now += 60
        self.assertEqual(mind.session_start()["topic"], "greet_new", "it meets you as a stranger")

    def test_no_backup_no_reset(self):
        path = lived_in(self)
        mind = WatcherMind(path, {}, Clock())
        with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
            self.assertIsNone(mind.reset())
        self.assertEqual(mind.memory["sessions"], 42, "nothing forgotten without a copy kept")


class DeckTests(unittest.TestCase):
    def test_only_with_the_confirmation_word(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('if payload.get("confirm") != "FORGET":', source)

    def test_reset_with_the_overlay_off(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        path = lived_in(self)

        class Deck:
            config = {}
            heartbeat_hud = None
            feed = []

            def add_event_feed_entry(self, *args, **kwargs):
                self.feed.append(args)
        deck = Deck()
        with patch("voidcompass.overlays.heartbeat_hud._memory_path", return_value=path):
            self.assertTrue(MainDashboard._watcher_reset(deck))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["sessions"], 0)
        self.assertIn("forgotten everything", deck.feed[0][1])

    def test_the_page_asks_twice(self):
        page = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        for marker in ("RESET THE WATCHER", "ARE YOU SURE?", "YES, FORGET EVERYTHING", "KEEP IT", 'confirm: "FORGET"',
                       'id="watcher-reset-yes" disabled'):
            self.assertIn(marker, page)


if __name__ == "__main__":
    unittest.main()
