"""Browser regressions for the journal-backed Focused Log surface."""

from pathlib import Path
import copy
import json
import unittest
from urllib.parse import urlsplit

from tests.test_dashboard_overview_visuals import overview_state


WEB = Path(__file__).resolve().parents[1] / "web"


def focused_state():
    state = copy.deepcopy(overview_state())
    state["sources"] = {"overall": "LIVE", "detail": "JOURNAL / STATUS LINKED"}
    state["ui"] = {"flight_log_mode": True, "reduced_motion": False}
    state["survey"]["completion"] = {
        "unknown_bodies": 4, "dss_targets": 3, "dss_complete": 1,
        "bio_total": 3, "bio_complete": 1,
    }
    state["data"].update({"unsold_exploration": 2300000, "unsold_bio": 2200000})
    state["route"].update({"source": "ELITE NAV ROUTE", "distance_text": "52 LY"})
    return state


class FocusedLogVisualTests(unittest.TestCase):
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

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1500, "height": 900})
        self.errors = []
        self.commands = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                route.fulfill(content_type="application/json", body='{"closing":true}')
                return
            if path == "/api/command":
                self.commands.append(route.request.post_data_json)
                route.fulfill(content_type="application/json", body='{"accepted":true}')
                return
            if path == "/api/snapshot":
                route.fulfill(content_type="application/json", body=json.dumps(focused_state()))
                return
            file = WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                source = file.read_text(encoding="utf-8")
                source += """
                  window.__focusedHarness = {
                    render(data) {
                      model = data;
                      applyTheme(data.theme || {});
                      document.body.classList.add('ready');
                      document.body.classList.toggle('reduced-motion', Boolean(data.ui?.reduced_motion));
                      document.getElementById('boot').hidden = true;
                      document.getElementById('app').setAttribute('aria-hidden', 'false');
                      renderDashboard(data);
                    }
                  };
                """
                route.fulfill(content_type="application/javascript", body=source)
            elif file.is_file():
                route.fulfill(path=str(file))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://focused.test/**", serve)
        self.page.goto("http://focused.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__focusedHarness)")

    def tearDown(self):
        self.page.close()

    def render(self, state):
        self.page.evaluate("data => window.__focusedHarness.render(data)", state)

    def test_live_field_brief_and_restore_dashboard(self):
        state = focused_state()
        self.render(state)
        shell = self.page.locator("#flight-log-shell")
        self.assertTrue(shell.is_visible())
        self.assertEqual(shell.get_attribute("aria-hidden"), "false")
        self.assertEqual(self.page.locator("#flightlog-source").inner_text(), "LOCAL LINK LIVE")
        self.assertEqual(self.page.locator("#flightlog-source").get_attribute("data-source"), "live")
        self.assertIn("SYNUEFE AA-A H1", self.page.locator("#flightlog-system").inner_text())
        self.assertEqual(self.page.locator("#flightlog-survey").inner_text(), "8 / 12")
        self.assertEqual(self.page.locator("#flightlog-survey-percent").inner_text(), "67%")
        self.assertEqual(self.page.locator("#flightlog-work-value-1").inner_text(), "2")
        self.assertEqual(self.page.locator("#flightlog-work-value-2").inner_text(), "2")
        self.assertEqual(self.page.locator("#flightlog-route").inner_text(), "COL 285 SECTOR")
        self.assertIn("4,500,000 CR", self.page.locator("#flightlog-value").inner_text())
        self.assertIn("MAP THE BIOLOGICAL WORLD", self.page.locator("#flightlog-directive").inner_text())
        self.assertIn("Map biological world", self.page.locator("#flightlog-priorities").inner_text())
        self.assertIn("World surveyed", self.page.locator("#flightlog-event-list").inner_text())
        self.assertIn("not a permanent flight archive", self.page.locator("#flightlog-event-limit").inner_text())

        self.page.locator(".flightlog-restore").click()
        self.assertEqual(self.commands[-1], {"action": "set_flight_log_mode", "enabled": False})
        state["ui"]["flight_log_mode"] = False
        self.render(state)
        self.assertFalse(shell.is_visible())
        self.assertEqual(shell.get_attribute("aria-hidden"), "true")
        self.assertTrue(self.page.locator(".overview-page").is_visible())
        self.page.locator('.overview-actions [data-command="set_flight_log_mode"]').click()
        self.assertEqual(self.commands[-1], {"action": "set_flight_log_mode", "enabled": True})
        self.assertFalse(self.errors, self.errors)

    def test_unknown_survey_and_cached_source_are_honest(self):
        state = focused_state()
        state["sources"]["overall"] = "CACHED"
        state["survey"].update({"scanned": 2, "total": 0, "total_known": False,
                                "percent": 0, "complete": False})
        state["route"].update({"next": "", "final": "", "distance_text": ""})
        self.render(state)
        gauge = self.page.locator("#flightlog-survey-gauge")
        self.assertEqual(self.page.locator("#flightlog-source").get_attribute("data-source"), "cached")
        self.assertEqual(gauge.get_attribute("data-known"), "false")
        self.assertEqual(gauge.get_attribute("role"), "img")
        self.assertIsNone(gauge.get_attribute("aria-valuenow"))
        self.assertEqual(self.page.locator("#flightlog-survey-percent").inner_text(), "—")
        self.assertEqual(self.page.locator("#flightlog-survey").inner_text(), "2 / ?")
        self.assertEqual(self.page.locator("#flightlog-work-value-0").inner_text(), "?")
        self.assertEqual(self.page.locator("#flightlog-survey-badge").inner_text(), "TOTAL UNKNOWN")
        self.assertEqual(self.page.locator("#flightlog-route").inner_text(), "NO ACTIVE ROUTE")
        state["sources"]["overall"] = "RECENT"
        self.render(state)
        self.assertEqual(self.page.locator("#flightlog-source").get_attribute("data-source"), "recent")
        self.assertFalse(self.errors, self.errors)

    def test_filter_search_recent_limit_and_live_scroll(self):
        state = focused_state()
        state["events"] = [
            {"ts": index, "time": f"12:00:{index:02d}",
             "tag": "SCAN" if index % 2 == 0 else "JUMP",
             "severity": "INFO", "message": f"Field entry {index}"
             + (" <img src=x>" if index == 2 else "")}
            for index in range(80)
        ]
        self.render(state)
        rows = self.page.locator("#flightlog-event-list .flightlog-event")
        self.assertEqual(rows.count(), 40)
        self.assertIn("latest 40 of 80", self.page.locator("#flightlog-event-limit").inner_text())
        self.assertEqual(self.page.locator("#flightlog-event-list img").count(), 0)
        self.assertIn("<img src=x>", self.page.locator("#flightlog-event-list").inner_text())
        geometry = self.page.locator("#flightlog-event-list").evaluate(
            "node => ({height: node.clientHeight, full: node.scrollHeight})")
        self.assertGreater(geometry["full"], geometry["height"])
        self.page.locator("#flightlog-event-list").evaluate("node => { node.scrollTop = 100; }")
        state["events"][0]["message"] = "Fresh field entry"
        self.render(state)
        self.assertGreaterEqual(self.page.locator("#flightlog-event-list").evaluate("node => node.scrollTop"), 95)
        self.page.locator('[data-flightlog-filter="DISCOVERY"]').click()
        self.assertEqual(rows.count(), 20)
        self.assertEqual(self.page.locator('[data-flightlog-filter="DISCOVERY"]').get_attribute("aria-pressed"), "true")
        self.page.locator("#flightlog-search").fill("Field entry 2")
        self.assertEqual(rows.count(), 6)  # 2, 20, 22, 24, 26, 28
        self.assertEqual(self.page.locator("#flightlog-event-count").inner_text(), "6 SHOWN / 40 RECENT")
        self.render(state)
        self.assertEqual(self.page.locator("#flightlog-search").input_value(), "Field entry 2")
        self.assertEqual(rows.count(), 6)
        self.assertFalse(self.errors, self.errors)

    def test_responsive_theme_and_reduced_motion(self):
        state = focused_state()
        state["theme"] = {"name": "Custom", "palette": {"accent": "#ff44aa"}}
        state["ui"]["reduced_motion"] = True
        self.render(state)
        self.assertEqual(self.page.locator("#flightlog-route").evaluate(
            "node => getComputedStyle(node).color"), "rgb(255, 68, 170)")
        self.assertEqual(self.page.locator(".flightlog-mark i:last-child").evaluate(
            "node => getComputedStyle(node).animationName"), "none")
        for width, height in ((1500, 900), (700, 760), (430, 760)):
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({"width": width, "height": height})
                self.assertTrue(self.page.locator("#flight-log-shell").is_visible())
                self.assertTrue(self.page.locator(".flightlog-restore").is_visible())
                self.assertTrue(self.page.locator("#flightlog-event-list").is_visible())
                self.assertTrue(self.page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth + 1"))
        self.assertFalse(self.errors, self.errors)


if __name__ == "__main__":
    unittest.main()
