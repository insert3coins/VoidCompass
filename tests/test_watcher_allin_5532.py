"""5.5.3.2, all in: the Watcher remembers places, your records and the day
you started; answers a poke; notices being hidden or moved; grows fond of
you; speaks in each nature's own voice; moves with the music; and has a page
of its own on the deck."""

import json
import random
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import DEFAULT_OVERLAY_HOTKEYS, OVERLAY_HOTKEY_SPECS
from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.exploration.travel_history import TravelHistory
from voidcompass.overlays import watcher_natures
from voidcompass.overlays.watcher_mind import WatcherMind, plain_text, times_text, when_text

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
NOON = datetime(2026, 10, 10, 12, 0).timestamp()


class Clock:
    def __init__(self, now=NOON):
        self.now = now

    def __call__(self):
        return self.now


def mind(config=None, seed=3):
    clock = Clock()
    watcher = WatcherMind(None, {"heartbeat_thoughts": "chatty", **(config or {})}, clock, random.Random(seed))
    return watcher, clock


def history(rows):
    path = Path(tempfile.mkdtemp()) / "travel.json"
    path.write_text(json.dumps({"schema": 1, "rows": rows, "files": {}}), encoding="utf-8")
    return TravelHistory(str(path))


class TravelMemoryTests(unittest.TestCase):
    def test_recall_and_records(self):
        travel = history([
            ["2025-03-02T10:00:00Z", "Sol", 0, 0, 0, "G", 0.0],
            ["2025-03-02T11:00:00Z", "Prai", 300, 0, 400, "K", 42.5],
            ["2025-04-01T11:00:00Z", "Far Out", 3000, 0, 4000, "M", 61.0],
            ["2025-04-02T11:00:00Z", "Carrier Spot", 3300, 0, 4400, "", 480.0, "C"],
            ["2025-05-02T11:00:00Z", "Prai", 300, 0, 400, "K", 55.0],
        ])
        self.assertEqual(travel.recall("prai"), {"count": 2, "first": "2025-03-02T11:00:00Z", "last": "2025-05-02T11:00:00Z"})
        self.assertIsNone(travel.recall("Nowhere"))
        records = travel.records()
        self.assertEqual(records["jump"], 61.0, "a carrier jump is not the ship's record")
        self.assertAlmostEqual(records["far"], 5500.0)
        self.assertEqual(records["first"], "2025-03-02T10:00:00Z")
        travel.observe({"event": "FSDJump", "timestamp": "2026-10-10T12:00:00Z", "StarSystem": "Prai",
                        "StarPos": [300, 0, 400], "JumpDist": 70.1})
        self.assertEqual(travel.recall("Prai")["count"], 3)
        self.assertEqual(travel.records()["jump"], 70.1)

    def test_when_and_times(self):
        self.assertEqual(when_text("2026-03-02T10:00:00Z", NOON), "in March")
        self.assertEqual(when_text("2025-03-02T10:00:00Z", NOON), "in March 2025")
        self.assertEqual(times_text(1), "once")
        self.assertEqual(times_text(7), "7 times")

    def test_dashboard_notes_revisits_records_and_the_anniversary(self):
        notes = []
        today = datetime.now()
        travel = history([
            [f"{today.year - 2}-{today.month:02d}-{today.day:02d}T10:00:00Z", "Sol", 0, 0, 0, "G", 0.0],
            ["2025-03-02T11:00:00Z", "Prai", 300, 0, 400, "K", 42.5],
        ])
        deck = SimpleNamespace(heartbeat_hud=SimpleNamespace(note=lambda kind, fields=None: notes.append((kind, fields))),
                               travel_history=travel)
        from voidcompass.dashboard.dashboard import MainDashboard
        MainDashboard._watcher_travel(deck, {"event": "FSDJump", "StarSystem": "Prai", "timestamp": "2026-10-10T12:00:00Z",
                                            "StarPos": [3000, 0, 4000], "JumpDist": 60.2})
        kinds = dict(notes)
        self.assertEqual(kinds["revisit"]["system"], "Prai")
        self.assertEqual(kinds["revisit"]["times"], "once")
        self.assertEqual(kinds["record_far"]["dist"], "5,000")
        self.assertEqual(kinds["record_jump"]["dist"], "60.20")
        self.assertEqual(kinds["anniversary"]["years"], "2 years")


class MindTests(unittest.TestCase):
    def test_records_once_a_session_and_the_anniversary_once_a_day(self):
        watcher, clock = mind()
        watcher.session_start()
        clock.now += 60  # past the greeting
        self.assertIsNotNone(watcher.note("record_far", {"dist": "5,000"}))
        clock.now += 60
        self.assertIsNone(watcher.note("record_far", {"dist": "5,010"}), "once a session")
        self.assertIsNotNone(watcher.note("anniversary", {"years": "2 years"}))
        self.assertIsNone(watcher.note("anniversary", {"years": "2 years"}), "once a day")

    def test_a_session_record_for_first_discoveries(self):
        watcher, clock = mind()
        watcher.memory["records"] = {"firsts": 5}
        watcher.session_start()
        heard = []
        for index in range(7):
            clock.now += 400
            thought = watcher.observe("Scan", {"BodyName": f"A {index}", "PlanetClass": "Icy body", "WasDiscovered": False})
            if thought:
                heard.append(thought["topic"])
        self.assertIn("record_firsts", heard)
        self.assertEqual(watcher.memory["records"]["firsts"], 7)

    def test_a_poke_answers_and_too_many_annoy_it(self):
        watcher, clock = mind()
        first = watcher.poke()
        self.assertIsNotNone(first)
        clock.now += 2
        watcher.poke()
        clock.now += 2
        self.assertEqual(watcher.poke()["topic"], "poked_again")
        clock.now += 60
        self.assertNotEqual(watcher.poke()["topic"], "poked_again", "after a pause it calms down")

    def test_hidden_then_shown_and_moved(self):
        watcher, clock = mind()
        self.assertIsNone(watcher.note("moved"), "nothing before the session")
        watcher.session_start()
        watcher.note("hidden")
        clock.now += 30
        self.assertEqual(watcher.note("shown")["topic"], "unhidden")
        watcher.note("hidden")
        clock.now += 2
        self.assertIsNone(watcher.note("shown"), "a blink of hiding isn't worth a word")

    def test_the_bond_grows_with_sessions_and_hours(self):
        watcher, clock = mind()
        self.assertEqual(watcher.bond(), 0)
        watcher.memory.update(sessions=12, hours=26.0)
        self.assertEqual(watcher.bond(), 2)
        watcher.memory.update(sessions=40, hours=150.0)
        self.assertEqual(watcher.bond(), 3)
        watcher.memory.update(sessions=3, hours=0.0)
        watcher.session_start()
        clock.now += 3600
        watcher.tick()
        self.assertAlmostEqual(watcher.memory["hours"], 1.0, places=2)

    def test_it_keeps_a_log_of_what_it_said(self):
        watcher, _clock = mind()
        thought = watcher.consider("quiet", force=True)
        self.assertEqual(watcher.memory["log"][-1][1:], ["quiet", thought["text"]])

    def test_each_nature_speaks_in_its_own_voice(self):
        for nature, bank in watcher_natures.BANKS.items():
            with self.subTest(nature=nature):
                watcher, clock = mind({"heartbeat_personality": nature}, seed=9)
                own = 0
                for index in range(6):
                    clock.now += 4000
                    thought = watcher.consider("arrival", {"system": f"Prai {index}"}, force=True)
                    if thought["text"] in [line.format(system=f"Prai {index}") for line in bank["arrival"]]:
                        own += 1
                self.assertGreaterEqual(own, 3, f"{nature} mostly uses its own words")
        for bank in watcher_natures.BANKS.values():
            for lines in bank.values():
                for line in lines:
                    self.assertEqual(line, plain_text(line))


class HotkeyAndPageTests(unittest.TestCase):
    def test_the_poke_hotkey_is_registered(self):
        actions = {row[0] for row in OVERLAY_HOTKEY_SPECS}
        self.assertIn("watcher_poke", actions)
        self.assertEqual(DEFAULT_OVERLAY_HOTKEYS["overlay_hotkey_watcher_poke"], "Ctrl+Alt+Shift+F9")
        self.assertIn("overlay_hotkey_watcher_poke", config_module.PROFILE_TEXT_SETTINGS)

    def test_the_watcher_page_data(self):
        watcher, _clock = mind()
        watcher.consider("green_giant", {"system": "Hatchooe"}, force=True)
        travel = history([["2025-03-02T10:00:00Z", "Sol", 0, 0, 0, "G", 0.0],
                          ["2025-03-03T10:00:00Z", "Prai", 300, 0, 400, "K", 42.5]])
        deck = SimpleNamespace(config={"heartbeat_personality": "weary", "overlay_hotkey_watcher_poke": "Ctrl+Alt+Shift+F9"},
                               heartbeat_hud=SimpleNamespace(mind=watcher), travel_history=travel,
                               _WATCHER_BONDS=HtmlDashboardMixin._WATCHER_BONDS,
                               _WATCHER_BOND_NEXT=HtmlDashboardMixin._WATCHER_BOND_NEXT)
        data = HtmlDashboardMixin._html_watcher_workspace(deck)
        self.assertEqual(data["log"][0]["topic"], "green_giant")
        self.assertEqual(data["log"][0]["mood"], "pleased")
        self.assertEqual(data["records"]["systems"], 2)
        self.assertEqual(data["bond"]["name"], "A stranger")
        self.assertEqual(data["hotkey"], "Ctrl+Alt+Shift+F9")
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="watcher"', html)
        self.assertIn('id="watcher-workspace"', html)


STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderHeartbeat = options.render; return {rerender() {}}; }};")


class MusicBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_the_eye_moves_with_the_music(self):
        page = self.browser.new_page(viewport={"width": 96, "height": 96})
        self.addCleanup(page.close)

        def serve(route):
            url = urlsplit(route.request.url)
            if url.path == "/api/live":
                return route.fulfill(content_type="application/json",
                                     body=json.dumps({"playing": True, "bands": [230, 210, 190, 160, 90, 60, 40, 30]}))
            path = WEB / url.path.lstrip("/")
            if not path.is_file():
                return route.fulfill(status=404, body="")
            if path.name == "overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + STUB)
            return route.fulfill(path=str(path))

        page.route("http://orb.test/**", serve)
        page.goto("http://orb.test/heartbeat/index.html?token=t&overlay=heartbeat_hud")
        page.evaluate("d => renderHeartbeat(d)", {"theme": {}, "effects": {}, "heartbeat": {"events": [], "orb": {"size": 96}}})
        page.wait_for_timeout(900)
        music = page.evaluate("heartbeatOrb.state().music")
        self.assertGreater(music["bass"], .3, "the bass reaches the eye")


if __name__ == "__main__":
    unittest.main()
