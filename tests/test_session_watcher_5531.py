"""5.5.3.1: the Watcher notices rare worlds and signs off with the
session's real figures; the Session Pulse shows the same figures."""

import random
import unittest
from pathlib import Path

from voidcompass.exploration.captains_log import CaptainsLog
from voidcompass.overlays import watcher_mind
from voidcompass.overlays.watcher_mind import WatcherMind

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    now = 1_000_000.0

    def __call__(self):
        return self.now


def mind():
    clock = Clock()
    watcher = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, clock, random.Random(1))
    watcher.session_start()
    clock.now += 600
    return watcher, clock


class SessionWatcherTests(unittest.TestCase):
    def test_summary_says_only_what_happened(self):
        self.assertEqual(watcher_mind.session_summary({}), "")
        self.assertEqual(
            watcher_mind.session_summary({"jumps": 41, "first_discoveries": 1, "exploration_sales": 12_400_000}),
            "41 jumps, 1 first discovery and 12.4M credits")
        self.assertEqual(watcher_mind.session_flown({"started": "2026-10-09T10:00:00Z", "ended": "2026-10-09T12:14:00Z"}), "2h 14m")

    def test_it_signs_off_with_the_figures(self):
        watcher, _clock = mind()
        thought = watcher.note("sign_off", {"summary": "41 jumps and 12.4M credits", "hours": "2h 14m"})
        self.assertIn("41 jumps and 12.4M credits", thought["text"])

    def test_a_quiet_session_without_a_time_never_says_in_nothing(self):
        for seed in range(12):
            watcher, _clock = mind()
            watcher.random = random.Random(seed)
            thought = watcher.note("sign_off", {"summary": "", "hours": ""})
            self.assertNotIn("{", thought["text"])
            self.assertFalse(thought["text"].startswith(" of"))

    def test_rare_worlds_and_green_giants(self):
        watcher, _clock = mind()
        thought = watcher.observe("Scan", {"BodyName": "Prai 3", "PlanetClass": "Helium gas giant", "WasDiscovered": True})
        self.assertIsNotNone(thought)
        self.assertIn("helium gas giant", thought["text"].casefold())
        watcher, _clock = mind()
        green = watcher.observe("CodexEntry", {"EntryID": 1200602, "Name": "$Codex_Ent_Green_Sudarsky_Class_II_Name;",
                                               "System": "Hatchooe"})
        self.assertIn("green", green["text"].casefold())

    def test_captains_log_counts_rare_worlds(self):
        log = CaptainsLog.__new__(CaptainsLog)
        import threading
        log.lock = threading.RLock()
        log.data = {"sessions": [], "seen": []}
        log._seen_set = set()
        log._body_names = {}
        log._last_star_pos = None
        log.save = lambda *a, **k: None
        log.process_event({"event": "LoadGame", "timestamp": "2026-10-09T10:00:00Z", "Commander": "J"}, save=False)
        log.process_event({"event": "Scan", "timestamp": "2026-10-09T10:05:00Z", "BodyName": "A 1", "PlanetClass": "Water giant"}, save=False)
        log.process_event({"event": "CodexEntry", "timestamp": "2026-10-09T10:06:00Z", "EntryID": 1200402,
                           "Name": "$Codex_Ent_Green_Giant_With_Ammonia_Life_Name;", "System": "A"}, save=False)
        session = log.sessions()[0]
        self.assertEqual(session["rare_worlds"], 2)

    def test_session_pulse_shows_the_new_figures(self):
        html = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        for node in ("pulse-flown", "pulse-earned", "pulse-firsts", "pulse-rare"):
            self.assertIn(f'id="{node}"', html)


if __name__ == "__main__":
    unittest.main()
