"""Navigation HUD: who discovered the system and when, and when EDSM last
updated it (as SrvSurvey's jump panel shows), on the line under the system
name, taking turns with the region."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.parse import unquote, urlsplit

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.overlays.hud import TacticalHUD
from voidcompass.services.edsm_handler import EDSMHandler


def reply(payload):
    return SimpleNamespace(json=lambda: payload)


class EdsmTrafficTests(unittest.TestCase):
    def fetch(self, traffic_reply, bodies_reply):
        handler = EDSMHandler.__new__(EDSMHandler)
        calls = []

        def get(url, params=None, **_):
            calls.append(url)
            return reply(traffic_reply if url.endswith("/traffic") else bodies_reply)

        handler._limited_get = get
        results = []
        import threading
        original = threading.Thread
        threading.Thread = lambda target, daemon=True: SimpleNamespace(start=target)
        try:
            handler.fetch_traffic("Aucoks LW-M d7-0", results.append)
        finally:
            threading.Thread = original
        return results[0], calls

    def test_discovery_and_the_newest_body_update_come_with_traffic(self):
        result, calls = self.fetch(
            {"traffic": {"day": 0, "week": 0, "total": 1},
             "discovery": {"commander": "Jededdiah Stahl", "date": "2022-04-04 10:11:12"}},
            {"bodies": [{"updateTime": "2022-04-04 10:20:00"}, {"updateTime": "2023-09-01 08:00:00"}, {}]},
        )
        self.assertEqual(result["discovered_by"], "Jededdiah Stahl")
        self.assertEqual(result["discovered_at"], "2022-04-04 10:11:12")
        self.assertEqual(result["updated_at"], "2023-09-01 08:00:00")
        self.assertEqual(result["total"], 1)

    def test_an_unknown_system_costs_no_body_request(self):
        result, calls = self.fetch({"traffic": {"day": 0, "week": 0, "total": 0}}, {"bodies": []})
        self.assertEqual(result["discovered_by"], "")
        self.assertEqual(len(calls), 1)

    def test_the_dashboard_keeps_the_history_with_traffic(self):
        normalized = MainDashboard._normalize_system_traffic(
            {"day": 1, "week": 2, "total": 3, "discovered_by": "Jededdiah Stahl", "discovered_at": "2022-04-04 10:11:12",
             "updated_at": "2023-09-01 08:00:00"})
        self.assertEqual(normalized["discovered_by"], "Jededdiah Stahl")
        self.assertEqual(normalized["updated_at"], "2023-09-01 08:00:00")


class TrafficRecheckTests(unittest.TestCase):
    """EDSM's CDN keeps each reply a day: a system asked about before EDSM
    heard of it (a fresh discovery, before our upload lands) stayed unknown
    all day, so "discovered by" never showed for the commander's own finds."""

    def test_a_recheck_reaches_edsm_itself(self):
        handler = EDSMHandler.__new__(EDSMHandler)
        seen = []

        def get(url, params=None, **_):
            seen.append(dict(params))
            return reply({"id": 1, "name": "Prai Preia OD-F c0", "traffic": {"total": 1},
                          "discovery": {"commander": "insert3coins", "date": "2026-10-02 19:09:34"}}
                         if url.endswith("/traffic") else {"bodies": []})

        handler._limited_get = get
        import threading
        original = threading.Thread
        threading.Thread = lambda target, daemon=True: SimpleNamespace(start=target)
        results = []
        try:
            handler.fetch_traffic("Prai Preia OD-F c0", results.append)
            handler.fetch_traffic("Prai Preia OD-F c0", results.append, recheck=True)
        finally:
            threading.Thread = original
        self.assertNotIn("recheck", seen[0])
        self.assertIn("recheck", seen[2])
        self.assertIn("recheck", seen[3], "the body update time too")
        self.assertTrue(results[1]["known"])

    def app(self):
        app = MainDashboard.__new__(MainDashboard)
        app.current_sys = "Prai Preia OD-F c0"
        app.is_running = True
        app._ui_post = lambda callback, key=None: callback()
        app._apply_system_traffic_context = Mock()
        app.update_dashboard_ui = Mock()
        app.update_hud = Mock()
        app.root = SimpleNamespace(call_later=Mock())
        return app

    def test_an_unknown_system_is_asked_again_twice(self):
        app = self.app()
        answers = [{"known": False, "total": 0}, {"known": False}, {"known": True, "total": 1, "discovered_by": "insert3coins"}]
        calls = []
        app.edsm = SimpleNamespace(fetch_traffic=lambda name, callback, recheck=False: (calls.append(recheck), callback(answers[len(calls) - 1])))
        app.fetch_system_traffic("Prai Preia OD-F c0")
        self.assertEqual(app.root.call_later.call_args.args[0], 60000)
        app.root.call_later.call_args.args[1]()
        # Still unknown on the first recheck: what is shown stays, one more try.
        self.assertEqual(app._apply_system_traffic_context.call_count, 1)
        self.assertEqual(app.root.call_later.call_args.args[0], 300000)
        app.root.call_later.call_args.args[1]()
        self.assertEqual(calls, [False, True, True])
        self.assertEqual(app._apply_system_traffic_context.call_args.args[1]["discovered_by"], "insert3coins")
        self.assertEqual(app.root.call_later.call_count, 2, "known now: no more checks")

    def test_a_known_system_and_a_new_system_stop_the_checks(self):
        app = self.app()
        app.edsm = SimpleNamespace(fetch_traffic=lambda name, callback, recheck=False: callback({"known": True, "total": 4}))
        app.fetch_system_traffic("Prai Preia OD-F c0")
        app.root.call_later.assert_not_called()
        app.edsm = SimpleNamespace(fetch_traffic=Mock(side_effect=lambda name, callback, recheck=False: callback({"known": False})))
        app.fetch_system_traffic("Prai Preia OD-F c0")
        app.current_sys = "Somewhere Else"
        app.root.call_later.call_args.args[1]()
        self.assertEqual(app.edsm.fetch_traffic.call_count, 1)


class HudHistoryTests(unittest.TestCase):
    def test_dates_read_as_elite_writes_them(self):
        lines = TacticalHUD._system_history(
            {"discovered_by": "Jededdiah Stahl", "discovered_at": "2022-04-04 10:11:12", "updated_at": "2025-01-09 08:00:00"})
        self.assertEqual(lines, ["DISCOVERED BY JEDEDDIAH STAHL · 4 APR 3308", "UPDATED 9 JAN 3311"])

    def test_an_update_no_later_than_the_discovery_is_left_out(self):
        lines = TacticalHUD._system_history(
            {"discovered_by": "A", "discovered_at": "2022-04-04 10:11:12", "updated_at": "2022-04-04 10:11:12"})
        self.assertEqual(lines, ["DISCOVERED BY A · 4 APR 3308"])
        self.assertEqual(TacticalHUD._system_history({}), [])
        self.assertEqual(TacticalHUD._system_history({"updated_at": "2024-02-29T01:00:00"}), ["UPDATED 29 FEB 3310"])


class HudPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        from tests.test_navigation_state_visuals import SHIP_ART, WEB, hud_snapshot, hud_state
        cls.snapshot = staticmethod(lambda: hud_snapshot(hud_state("EXPLORATION")))
        cls.web, cls.ship_art = WEB, SHIP_ART
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

    def test_the_region_line_takes_turns_with_the_history(self):
        page = self.browser.new_page(viewport={"width": 500, "height": 326})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            path = unquote(urlsplit(route.request.url).path)
            target = (self.ship_art / path[len("/ship-art/"):] if path.startswith("/ship-art/")
                      else self.web / path.lstrip("/"))
            return route.fulfill(path=str(target)) if target.is_file() else route.fulfill(status=404, body="")

        page.clock.install()
        page.route("http://state.test/**", serve)
        page.goto("http://state.test/navigation_hud/index.html")
        snapshot = self.snapshot()
        snapshot["system"]["history"] = ["DISCOVERED BY JEDEDDIAH STAHL · 4 APR 3308"]
        page.evaluate("s => render(s)", snapshot)
        label = page.locator("#region-label")
        self.assertEqual(label.inner_text(), "REGION 18 // INNER ORION SPUR")
        page.clock.run_for(6100)
        self.assertEqual(label.inner_text(), "DISCOVERED BY JEDEDDIAH STAHL · 4 APR 3308")
        self.assertIn("system-history", label.get_attribute("class"))
        page.clock.run_for(6100)
        self.assertEqual(label.inner_text(), "REGION 18 // INNER ORION SPUR")
        # Without history the region holds still.
        snapshot["system"]["history"] = []
        snapshot["system"]["name"] = "OTHER SYSTEM"
        page.evaluate("s => render(s)", snapshot)
        page.clock.run_for(13000)
        self.assertEqual(label.inner_text(), "REGION 18 // INNER ORION SPUR")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
