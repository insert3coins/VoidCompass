"""Session flight logs (5.5.3.8): one page for each night you flew."""
from __future__ import annotations

from pathlib import Path
import threading
import unittest

from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard_flight_log_mixin import DashboardFlightLogMixin
from voidcompass.exploration.flight_log import credits_text, flight_log, flight_logs, flown_text, watcher_words

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

NIGHT = {
    "started": "2026-10-12T18:00:00Z", "ended": "2026-10-12T21:41:00Z", "start_system": "Sol", "end_system": "Colonia",
    "ship": "Mandalay", "jumps": 63, "distance_ly": 2814.2, "first_discoveries": 4, "rare_worlds": 1, "codex": 3,
    "exploration_sales": 12_000_000, "biology_sales": 400_000, "trade_profit": 0,
    "highlights": [{"kind": "JUMP", "title": "Arrived in Sol"}, {"kind": "PHOTO", "title": "Screenshot"},
                   {"kind": "RARE", "title": "Green gas giant", "detail": "Hatchooe"}, {"kind": "CODEX", "title": "Stratum"}],
}


def row(stamp, system, x=0.0, z=0.0):
    return [stamp, system, x, 0.0, z, "K", 40.0, ""]


ROWS = [row("2026-10-11T23:00:00Z", "Yesterday"), row("2026-10-12T18:05:00Z", "Sol"),
        row("2026-10-12T18:10:00Z", "Hatchooe", 10, 30), row("2026-10-12T20:10:00Z", "Colonia", -9530, 19808),
        row("2026-10-13T09:00:00Z", "Tomorrow")]


class LogTests(unittest.TestCase):
    def test_one_page_for_the_night(self):
        log = flight_log(NIGHT, ROWS, [{"id": "a", "title": "Hatchooe", "at": 1760300000}], "weary")
        self.assertEqual((log["flown"], log["start_system"], log["end_system"], log["ship"]),
                         ("3 hours and 41 minutes", "Sol", "Colonia", "Mandalay"))
        self.assertEqual(log["figures"]["credits"], 12_400_000)
        self.assertEqual(log["trail"], [[0.0, 0.0], [10.0, 30.0], [-9530.0, 19808.0]], "only tonight's arrivals")
        self.assertEqual(log["star"], {"system": "Hatchooe", "minutes": 120}, "where it stayed longest")
        self.assertEqual([item["kind"] for item in log["highlights"]], ["RARE", "CODEX", "PHOTO"], "the best first; no plain jumps")
        self.assertTrue(log["elite_date"].endswith("3312"))
        self.assertFalse(log["open"])

    def test_the_watchers_words_are_the_nights_own(self):
        weary = flight_log(NIGHT, ROWS, (), "weary")["words"]
        self.assertEqual(weary, flight_log(NIGHT, ROWS, (), "weary")["words"], "the same every time it's read")
        self.assertIn("green gas giant", weary)
        self.assertIn("4 first discoveries", weary)
        self.assertNotEqual(weary, flight_log(NIGHT, ROWS, (), "stoic")["words"], "its nature's voice")
        quiet = watcher_words({"id": "x", "flown": "A minute", "start": "Sol", "end": "Sol"}, "normal")
        self.assertIn("A quiet night", quiet)
        died = watcher_words({"id": "x", "flown": "2 hours", "start": "A", "end": "B", "deaths": 1}, "weary")
        self.assertIn("We died tonight", died)

    def test_a_night_still_in_flight(self):
        open_night = dict(NIGHT, ended=None)
        log = flight_log(open_night, ROWS, (), now=1760300000 + 3600)
        self.assertTrue(log["open"])

    def test_the_newest_nights_from_one_pass(self):
        older = dict(NIGHT, started="2026-10-10T19:00:00Z", ended="2026-10-10T20:00:00Z", jumps=9)
        logs = flight_logs([NIGHT, older, {"started": None}], ROWS, ())
        self.assertEqual([log["figures"]["jumps"] for log in logs], [63, 9])
        self.assertEqual(logs[1]["trail"], [], "nothing flown in the history that night")
        self.assertEqual(len(flight_logs([NIGHT] * 80, ROWS, ())), 80, "every night the log keeps")
        self.assertEqual(len(flight_logs([NIGHT] * 300, ROWS, ())), 250)

    def test_words_and_numbers(self):
        self.assertEqual([flown_text(seconds) for seconds in (60, 1500, 3600, 13260)],
                         ["A minute", "25 minutes", "An hour", "3 hours and 41 minutes"])
        self.assertEqual([credits_text(value) for value in (950, 12_400, 12_400_000, 2_100_000_000)], ["950", "12K", "12.4M", "2.1B"])


class Toasts:
    def __init__(self):
        self.pushed = []

    def push(self, title, message="", **options):
        self.pushed.append((title, message))


class DeckTests(unittest.TestCase):
    def deck(self, **config):
        class Deck(DashboardFlightLogMixin):
            pass
        deck = Deck()
        deck.config = dict(config)
        deck.toast_hud = Toasts()
        deck.captains_log = type("Log", (), {"sessions": lambda self: [NIGHT]})()
        deck.travel_history = type("H", (), {"lock": threading.Lock(), "rows": ROWS, "revision": 1})()
        return deck

    def test_a_notice_when_you_log_off(self):
        deck = self.deck()
        self.assertTrue(deck._flight_log_written())
        title, message = deck.toast_hud.pushed[0]
        self.assertEqual(title, "FLIGHT LOG WRITTEN")
        self.assertIn("63 jumps", message)
        self.assertFalse(self.deck(flight_log_notice=False)._flight_log_written())

    def test_switched_from_the_page_and_kept(self):
        deck = self.deck()
        saved = []
        deck._persist_config = lambda: saved.append(True)
        self.assertTrue(deck._handle_flight_log_command("notice", {"value": False}))
        self.assertIs(deck.config["flight_log_notice"], False)
        self.assertFalse(deck._handle_flight_log_command("delete", {}))
        self.assertIn("flight_log_notice", config_module.PROFILE_SETTINGS)

    def test_worked_out_once_until_something_changes(self):
        deck = self.deck()
        first = deck._flight_logs([NIGHT])
        self.assertIs(deck._flight_logs([NIGHT]), first)
        deck.travel_history.revision = 2
        self.assertIsNot(deck._flight_logs([NIGHT]), first)

    def test_on_the_captains_log_page(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index('id="flightlog-workspace"'), html.index('id="chronicle-workspace"'), "at the top")
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("renderFlightLogs(data.flight_logs || {}, WORKSHOP_UI, data.sessions || [])", app)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("self._flight_log_written()", dashboard)


class PageTests(unittest.TestCase):
    def test_one_list_of_logs_instead_of_a_heap(self):
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        self.assertNotIn('<section class="chronicle-list">${cards.join', app, "no heap of session cards")
        self.assertIn('chronicleFold("photos"', app)
        self.assertIn('chronicleFold("discoveries"', app)
        self.assertIn("renderFlightLogs(data.flight_logs || {}, WORKSHOP_UI, data.sessions || [])", app)
        page = (WEB / "dashboard" / "flightlog.js").read_text(encoding="utf-8")
        for marker in ('id="flightlog-find"', 'class="flightlog-month"', 'data-fold="full"', "FULL LOG"):
            self.assertIn(marker, page)

    def test_grouped_by_month_with_each_day(self):
        log = flight_log(NIGHT, ROWS, ())
        self.assertTrue(log["month"].endswith("3312"))
        self.assertRegex(log["day"], r"^[A-Z][a-z]{2} \d{1,2}$")


if __name__ == "__main__":
    unittest.main()
