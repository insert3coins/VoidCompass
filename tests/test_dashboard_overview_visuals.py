"""Browser regressions for the live exploration dashboard overview."""

from pathlib import Path
import json
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web"


def overview_state():
    """A small journal-shaped state with deliberately distinct work counts."""
    return {
        "app": {"version": "5.4.9.2"},
        "profile": {"key": "overview-visual-test", "commander": "TEST CMDR",
                    "profile_label": "TEST CMDR · live field briefing"},
        "theme": {},
        "ui": {"flight_log_mode": False},
        "flight": {"system": "SYNUEFE AA-A H1", "context": "EXPLORING SYSTEM",
                   "ship": "MANDALAY", "state": "FLIGHT", "fuel_percent": 73,
                   "fuel_detail": "FUEL RESERVE NOMINAL"},
        "survey": {
            "total_known": True, "scanned": 8, "total": 12, "percent": 66.7,
            "bio_signals": 3, "geo_signals": 1, "valuable_count": 2,
            "star_class": "K", "complete": False, "notable_total": 7,
            "completion": {"unknown_bodies": 4, "dss_targets": 3,
                           "dss_complete": 1, "bio_total": 3, "bio_complete": 1},
            "notables": [f"Priority world {index}" for index in range(1, 8)],
            "bodies": [{"body_id": 2, "name": "SYNUEFE AA-A H1 2",
                        "detail": "BIOLOGICAL SIGNALS", "badge": "BIO",
                        "priority": True, "bio_count": 3}],
        },
        "route": {"mode": "game", "source": "GAME ROUTE", "next": "COL 285 SECTOR",
                  "final": "BEAGLE POINT", "summary": "12 JUMPS REMAINING",
                  "remaining": 12, "percent": 25, "distance_text": "52 LY",
                  "horizon": {"jumps": []}},
        "session": {"elapsed": "01:24:30", "distance_ly": 52, "jumps": 3},
        "data": {"unsold_total": 4500000, "unsold_bio": 2200000},
        "intelligence": {"region": "OUTER ORION SPUR"},
        "decision": {"doctrine_label": "BALANCED", "confidence": "JOURNAL-BACKED",
                     "title": "MAP THE BIOLOGICAL WORLD",
                     "detail": "Complete the remaining surface survey.",
                     "tags": ["BIOLOGY", "DSS"],
                     "primary": {"label": "OPEN SYSTEM SURVEY", "command": "open"}},
        "preflight": {
            "status": "CHECK", "summary": "Departure checks need attention.",
            "checks": [
                {"id": "journal", "status": "ready", "label": "JOURNAL LINK",
                 "value": "CONNECTED", "detail": "Telemetry is live"},
                {"id": "route", "status": "warn", "label": "DEPARTURE ROUTE",
                 "value": "UNPLOTTED", "detail": "Plot a destination"},
                {"id": "fuel", "status": "fail", "label": "FUEL RESERVE",
                 "value": "CRITICAL", "detail": "Refuel before departure"},
                {"id": "landing", "status": "optional", "label": "LANDING PLAN",
                 "value": "STANDBY", "detail": "Optional"},
            ],
        },
        "codex_hunt": {"region": "OUTER ORION SPUR", "candidates": []},
        "dashboard_layout": {
            "module_order": ["route", "session", "priorities", "codex", "feed"],
            "hidden_modules": [], "available_modules": [],
            "doctrine": "balanced", "doctrines": [{"id": "balanced", "label": "Balanced"}],
        },
        "page_layouts": {},
        "priorities": [{"title": "Map biological world", "detail": "Two samples remain.",
                        "severity": "WARN"}],
        "events": [{"time": "12:34:56", "tag": "SCAN", "message": "World surveyed",
                    "severity": "INFO", "ts": "2026-09-24T12:34:56Z"}],
        "sources": {"overall": "LIVE", "detail": "JOURNAL LINK ACTIVE"},
        "workspace": {"page": "overview", "ready": False},
    }


class DashboardOverviewVisualTests(unittest.TestCase):
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
        self.page = self.browser.new_page(viewport={"width": 1600, "height": 900})
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
                route.fulfill(content_type="application/json", body=json.dumps(overview_state()))
                return
            file = WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                source = file.read_text(encoding="utf-8")
                source += """
                  window.__overviewHarness = {
                    render(data) {
                      model = data;
                      applyTheme(data.theme || {});
                      document.body.classList.add('ready');
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

        self.page.route("http://overview.test/**", serve)
        self.page.goto("http://overview.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__overviewHarness)")

    def tearDown(self):
        self.page.close()

    def render(self, state):
        self.page.evaluate("data => window.__overviewHarness.render(data)", state)

    def test_populated_survey_work_and_ranked_notable_overflow(self):
        self.render(overview_state())
        self.assertEqual(self.page.locator("#header-system").inner_text(), "SYNUEFE AA-A H1")
        self.assertIn("8 OPEN TASKS", self.page.locator("#metric-work").inner_text())
        work_detail = self.page.locator("#metric-work-detail").inner_text()
        for part in ("FSS 4", "DSS 2", "BIO 2"):
            self.assertIn(part, work_detail)

        notables = self.page.locator("#survey-notables")
        for index in range(1, 5):
            self.assertIn(f"Priority world {index}", notables.inner_text())
        self.assertNotIn("Priority world 5", notables.inner_text())
        self.assertIn("+3 MORE", self.page.locator("#survey-overflow").inner_text())
        workboard = self.page.locator("#survey-open-workboard")
        self.assertEqual(workboard.get_attribute("data-page"), "explore")
        self.assertTrue(workboard.is_visible())
        workboard.click()
        self.assertIn("active", self.page.locator('[data-page-name="explore"]').get_attribute("class"))
        self.assertEqual(self.page.locator('.nav-item[data-page="explore"]').get_attribute("aria-current"), "page")
        self.assertFalse(self.errors, self.errors)

    def test_preflight_is_exception_first_and_can_expand(self):
        state = overview_state()
        state["preflight"] = {
            "status": "READY", "summary": "Departure systems ready.",
            "checks": [state["preflight"]["checks"][0]],
        }
        self.render(state)
        toggle = self.page.locator("#preflight-toggle")
        self.assertEqual(toggle.get_attribute("aria-controls"), "preflight-checks")
        self.assertEqual(toggle.get_attribute("aria-expanded"), "false")
        checks = self.page.locator("#preflight-checks .preflight-check")
        self.assertEqual(checks.count(), 0)

        state["preflight"] = overview_state()["preflight"]
        self.render(state)
        self.assertEqual(checks.count(), 2)
        self.assertIn("DEPARTURE ROUTE", self.page.locator("#preflight-checks").inner_text())
        self.assertIn("FUEL RESERVE", self.page.locator("#preflight-checks").inner_text())
        self.assertNotIn("JOURNAL LINK", self.page.locator("#preflight-checks").inner_text())
        toggle.click()
        self.assertEqual(toggle.get_attribute("aria-expanded"), "true")
        self.assertEqual(checks.count(), 4)
        toggle.click()
        self.assertEqual(toggle.get_attribute("aria-expanded"), "false")
        self.assertEqual(checks.count(), 2)
        self.assertFalse(self.errors, self.errors)

    def test_empty_survey_and_clear_work_states(self):
        state = overview_state()
        state["flight"]["system"] = ""
        state["survey"].update({"total_known": False, "scanned": 0, "total": 0,
                                "percent": 0, "notable_total": 0, "notables": [],
                                "bodies": [], "bio_signals": 0, "valuable_count": 0,
                                "completion": {"unknown_bodies": 0, "dss_targets": 0,
                                               "dss_complete": 0, "bio_total": 0,
                                               "bio_complete": 0}})
        self.render(state)
        self.assertIn("AWAITING SURVEY", self.page.locator("#metric-work").inner_text())
        self.assertIn("Awaiting scan telemetry", self.page.locator("#survey-notables").inner_text())
        self.assertTrue(self.page.locator("#survey-overflow").is_hidden())

        state["flight"]["system"] = "SOL"
        state["survey"].update({"total_known": True, "scanned": 1, "total": 1,
                                "percent": 100, "complete": True})
        self.render(state)
        self.assertIn("CLEAR", self.page.locator("#metric-work").inner_text())
        self.assertFalse(self.errors, self.errors)

    def test_responsive_cards_statusbar_and_icon_rail_accessibility(self):
        self.render(overview_state())
        nav = self.page.get_by_role("navigation", name="Command deck")
        for width, height in ((1600, 900), (1250, 800), (980, 680)):
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({"width": width, "height": height})
                self.assertTrue(nav.get_by_role("button", name="Dashboard").is_visible())
                geometry = self.page.evaluate("""() => {
                  const box = selector => document.querySelector(selector).getBoundingClientRect();
                  const page = box('.page[data-page-name="overview"]');
                  const survey = box('.overview-modules > .survey-card');
                  const route = box('.overview-modules > .route-card');
                  const status = box('.statusbar');
                  const cards = [...document.querySelectorAll('.overview-modules > :not([hidden])')]
                    .map(node => node.getBoundingClientRect());
                  return {
                    viewport: window.innerWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    cardsFit: cards.every(rect => rect.left >= page.left - 1 && rect.right <= page.right + 1),
                    pair: Math.abs(survey.top - route.top) <= 2 && survey.right <= route.left + 2,
                    statusVisible: status.height >= 25 && Math.abs(status.bottom - innerHeight) <= 1
                      && status.left >= 0 && status.right <= innerWidth + 1,
                  };
                }""")
                self.assertLessEqual(geometry["scrollWidth"], geometry["viewport"] + 1, geometry)
                self.assertTrue(geometry["cardsFit"], geometry)
                self.assertTrue(geometry["pair"], geometry)
                self.assertTrue(geometry["statusVisible"], geometry)
        hidden_route = overview_state()
        hidden_route["dashboard_layout"]["hidden_modules"] = ["route"]
        self.render(hidden_route)
        self.assertTrue(self.page.locator(".overview-modules > .route-card").is_hidden())
        self.assertTrue(self.page.locator(".overview-modules > .survey-card").evaluate(
            "node => Math.abs(node.getBoundingClientRect().width - node.parentElement.clientWidth) <= 2"))
        self.assertFalse(self.errors, self.errors)


if __name__ == "__main__":
    unittest.main()
