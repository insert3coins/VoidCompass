"""Browser regressions for the live exploration dashboard overview."""

from pathlib import Path
import json
import unittest
from urllib.parse import urlsplit


WEB = Path(__file__).resolve().parents[1] / "web"


def overview_state():
    """A small journal-shaped state with deliberately distinct work counts."""
    return {
        "app": {"version": "5.4.9.4"},
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
                        "planet_class": "Water world", "ring_count": 1,
                        "detail": "BIOLOGICAL SIGNALS", "badge": "BIO",
                        "priority": True, "bio_count": 3, "latest_scan": True}],
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
                    },
                    workspace(data) { renderExploreWorkspace(data, EXPLORE_WORKSPACE_UI); }
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
        self.assertIn("EXPEDITION BRIDGE", self.page.locator(".overview-masthead h2").inner_text().upper())
        self.assertEqual(self.page.locator("#overview-link-state").inner_text(), "JOURNAL LIVE")
        self.assertEqual(self.page.locator("#overview-link-state").get_attribute("data-source"), "live")
        for selector in ("#customise-deck", ".overview-actions [data-command='set_flight_log_mode']",
                         ".overview-actions [data-target='explore']",
                         ".overview-actions [data-page='map']"):
            self.assertTrue(self.page.locator(selector).is_visible(), selector)
        self.assertTrue(self.page.locator(".decision-lens").is_visible())
        self.assertEqual(self.page.locator("#decision-context").inner_text(), "SYNUEFE AA-A H1")
        self.assertEqual(self.page.locator("#decision-tags span").count(), 2)
        self.assertTrue(self.page.locator("#decision-primary").is_enabled())
        for selector, key in ((".decision-card", "smart-next-action"),
                              (".preflight-card", "exploration-preflight"),
                              (".survey-card", "current-system-survey")):
            self.assertEqual(self.page.locator(f".overview-modules > {selector}").get_attribute(
                "data-layout-panel"), key)
        self.assertIn("8 OPEN TASKS", self.page.locator("#metric-work").inner_text())
        work_detail = self.page.locator("#metric-work-detail").inner_text()
        for part in ("FSS 4", "DSS 2", "BIO 2"):
            self.assertIn(part, work_detail)

        survey = self.page.locator(".overview-modules > .survey-card")
        self.assertEqual(survey.get_attribute("data-survey-state"), "active")
        self.assertEqual(survey.get_attribute("data-star-class"), "K")
        self.assertAlmostEqual(float(self.page.locator("#survey-orbital").evaluate(
            "node => parseFloat(node.style.getPropertyValue('--survey-angle'))")), 240.12, places=2)
        self.assertEqual(self.page.locator("#survey-percent").inner_text(), "67%")
        self.assertEqual(self.page.locator("#survey-body-total").inner_text(), "1 BODY RECORD")
        self.assertEqual(self.page.locator("#survey-body-list .survey-body-row").count(), 1)
        self.assertIn("2", self.page.locator("#survey-body-list .survey-body-copy b").inner_text())
        self.assertIn("Water world", self.page.locator("#survey-body-list .survey-body-copy small").inner_text())
        planet_orb = self.page.locator("#survey-body-list .bridge-planet-orb")
        self.assertIn("bridge-planet-water", planet_orb.get_attribute("class"))
        self.assertIn("has-rings", planet_orb.get_attribute("class"))
        for layer in ("ring", "sphere", "glint"):
            self.assertEqual(planet_orb.locator(f":scope > .bridge-planet-{layer}").count(), 1)
        sphere = planet_orb.locator(":scope > .bridge-planet-sphere")
        self.assertTrue(sphere.evaluate("""node => {
          const style = getComputedStyle(node), box = node.getBoundingClientRect();
          return box.width > 15 && box.height > 15 && style.backgroundImage !== 'none';
        }"""))
        self.assertTrue(self.page.locator(".route-radar").is_visible())
        self.assertIn("has-route", self.page.locator(".overview-modules > .route-card").get_attribute("class"))
        self.assertEqual(self.page.locator("#route-badge").inner_text(), "GAME ROUTE")

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
        signal = self.page.locator("#preflight-signal")
        self.assertEqual(signal.get_attribute("aria-label"), "1 departure checks; 0 need attention")
        self.assertEqual(signal.locator("i.ready").count(), 1)

        state["preflight"] = overview_state()["preflight"]
        self.render(state)
        self.assertEqual(self.page.locator("#preflight-status").inner_text(), "CHECK")
        self.assertTrue(self.page.locator("#preflight-status").evaluate(
            "node => node.scrollWidth <= node.clientWidth + 1"))
        self.assertEqual(signal.get_attribute("aria-label"), "4 departure checks; 2 need attention")
        for status in ("ready", "warn", "fail", "optional"):
            self.assertEqual(signal.locator(f"i.{status}").count(), 1)
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
        self.assertEqual(self.page.locator("#survey-body-total").inner_text(), "0 BODY RECORDS")
        self.assertIn("Planets and moons appear", self.page.locator("#survey-body-list").inner_text())
        self.assertTrue(self.page.locator("#survey-overflow").is_hidden())
        self.assertEqual(self.page.locator(".overview-modules > .survey-card").get_attribute("data-survey-state"), "awaiting")
        self.assertEqual(self.page.locator("#decision-context").inner_text(), "UNKNOWN SYSTEM")

        state["flight"]["system"] = "SOL"
        state["survey"].update({"total_known": True, "scanned": 1, "total": 1,
                                "percent": 100, "complete": True})
        self.render(state)
        self.assertIn("CLEAR", self.page.locator("#metric-work").inner_text())
        self.assertEqual(self.page.locator(".overview-modules > .survey-card").get_attribute("data-survey-state"), "complete")
        self.assertEqual(self.page.locator("#survey-orbital").evaluate(
            "node => node.style.getPropertyValue('--survey-angle')"), "360deg")
        self.assertEqual(self.page.locator("#decision-context").inner_text(), "SOL")

        state["route"].update({"mode": "none", "next": "", "summary": "", "horizon": {"jumps": []}})
        self.render(state)
        self.assertNotIn("has-route", self.page.locator(".overview-modules > .route-card").get_attribute("class"))
        self.assertEqual(self.page.locator("#route-badge").inner_text(), "NO ROUTE")
        self.assertFalse(self.errors, self.errors)

    def test_current_system_body_deck_tracks_new_scans_and_large_systems(self):
        state = overview_state()
        state["survey"]["bodies"] = [
            {"body_id": index, "name": f"SYNUEFE AA-A H1 {index}",
             "planet_class": "Rocky body" if index % 3 else "Icy body",
             "ring_count": 2 if index == 35 else 0,
             "latest_scan": index == 35, "priority": index % 4 == 0,
             "bio_count": 2 if index == 35 else 0}
            for index in range(1, 36)
        ]
        state["survey"].update({"scanned": 35, "total": 60, "percent": 58.3})
        self.render(state)
        rows = self.page.locator("#survey-body-list .survey-body-row")
        self.assertEqual(rows.count(), 35)
        self.assertEqual(rows.first.get_attribute("data-body-id"), "35")
        self.assertIn("has-rings", rows.first.locator(".bridge-planet-orb").get_attribute("class"))
        self.assertIn("LATEST", rows.first.inner_text())
        self.assertIn("35 BODY RECORDS", self.page.locator("#survey-body-total").inner_text())
        for width, height in ((1600, 900), (980, 680)):
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({"width": width, "height": height})
                geometry = self.page.locator("#survey-body-list").evaluate("""node => ({
                  viewport: node.clientHeight, content: node.scrollHeight,
                  fits: node.scrollWidth <= node.clientWidth + 1,
                })""")
                self.assertLessEqual(geometry["viewport"], 170, geometry)
                self.assertGreater(geometry["content"], geometry["viewport"], geometry)
                self.assertTrue(geometry["fits"], geometry)

        body_list = self.page.locator("#survey-body-list")
        body_list.scroll_into_view_if_needed()
        self.page.wait_for_function("document.querySelectorAll('#survey-body-list .survey-body-row.in-view').length > 0")
        self.assertLess(self.page.locator("#survey-body-list .survey-body-row.in-view").count(), 35)
        body_list.evaluate("node => { node.scrollTop = node.scrollHeight; }")
        self.page.wait_for_function("document.querySelector('#survey-body-list .survey-body-row:last-child').classList.contains('in-view')")
        self.assertNotIn("in-view", rows.first.get_attribute("class"))

        state["survey"]["bodies"].append({"body_id": 36, "name": "SYNUEFE AA-A H1 36",
                                           "bio_count": 1, "latest_scan": True})
        state["survey"]["bodies"][-2]["latest_scan"] = False
        self.render(state)
        self.assertEqual(rows.count(), 36)
        self.assertEqual(rows.first.get_attribute("data-body-id"), "36")
        self.assertIn("bridge-planet-unknown", rows.first.locator(".bridge-planet-orb").get_attribute("class"))
        self.assertIn("CLASS UNCONFIRMED", rows.first.inner_text())

        state["flight"]["system"] = "SOL"
        state["survey"].update({"bodies": [], "scanned": 0, "total": 0,
                                "total_known": False, "notables": [], "notable_total": 0})
        self.render(state)
        self.assertEqual(rows.count(), 0)
        self.assertIn("Planets and moons appear", self.page.locator("#survey-body-list").inner_text())
        self.assertNotIn("SYNUEFE", self.page.locator("#survey-body-list").inner_text())
        self.assertFalse(self.errors, self.errors)

    def test_workboard_keeps_every_body_and_preserves_live_scroll(self):
        state = overview_state()
        state["survey"]["bodies"] = [
            {"body_id": index, "name": f"SYNUEFE AA-A H1 {index}",
             "planet_class": "Rocky body", "detail": "SURVEY RECORD"}
            for index in range(1, 36)
        ]
        self.render(state)
        self.assertEqual(self.page.locator("#body-workboard .body-row:not(.empty)").count(), 35)
        self.assertEqual(self.page.locator("#workboard-orbits .workboard-body-marker").count(), 18)
        self.assertEqual(self.page.locator("#workboard-orbits .workboard-more").inner_text(), "+17 MORE")
        self.assertIn("18 of 35", self.page.locator("#workboard-orbits").get_attribute("aria-label"))
        self.page.locator('.nav-item[data-page="explore"]').click()
        workboard = self.page.locator("#body-workboard")
        initial = workboard.evaluate("""node => {
          node.scrollTop = Math.floor(node.scrollHeight * .45);
          node.children[20].dataset.domProof = 'retained';
          return {top: node.scrollTop, bounded: node.clientHeight < node.scrollHeight};
        }""")
        self.assertTrue(initial["bounded"], initial)
        self.assertGreater(initial["top"], 0)
        self.render(state)
        self.assertEqual(workboard.locator('[data-dom-proof="retained"]').count(), 1)
        self.assertEqual(workboard.evaluate("node => node.scrollTop"), initial["top"])

        state["survey"]["bodies"].append({"body_id": 36, "name": "SYNUEFE AA-A H1 36"})
        self.render(state)
        self.assertEqual(workboard.locator(".body-row:not(.empty)").count(), 36)
        self.assertEqual(self.page.locator("#workboard-orbits .workboard-more").inner_text(), "+18 MORE")
        self.assertEqual(workboard.evaluate("node => node.scrollTop"), initial["top"])
        self.assertFalse(self.errors, self.errors)

    def test_current_system_body_click_and_keyboard_focus_matching_workboard(self):
        state = overview_state()
        state["survey"]["bodies"] = [
            {"body_id": index, "name": f"SYNUEFE AA-A H1 {index}",
             "planet_class": "Rocky body"}
            for index in range(1, 36)
        ]
        self.render(state)
        source = self.page.locator('#survey-body-list .survey-body-row[data-body-id="32"]')
        self.assertEqual(source.get_attribute("aria-label"),
                         "Open SYNUEFE AA-A H1 32 in the Survey Board")
        source.click()
        self.assertIn("active", self.page.locator('[data-page-name="explore"]').get_attribute("class"))
        selected = self.page.locator("#body-workboard .body-row.selected")
        self.assertEqual(selected.count(), 1)
        self.assertEqual(selected.get_attribute("data-body-id"), "32")
        self.assertEqual(selected.get_attribute("aria-current"), "true")
        self.assertTrue(selected.evaluate("node => document.activeElement === node"))
        self.assertGreater(self.page.locator("#body-workboard").evaluate("node => node.scrollTop"), 0)

        self.page.locator('.nav-item[data-page="overview"]').click()
        source = self.page.locator('#survey-body-list .survey-body-row[data-body-id="3"]')
        source.focus()
        source.press("Enter")
        self.assertEqual(self.page.locator("#body-workboard .body-row.selected").get_attribute("data-body-id"), "3")
        self.page.locator('.nav-item[data-page="overview"]').click()
        source = self.page.locator('#survey-body-list .survey-body-row[data-body-id="4"]')
        source.focus()
        source.press("Space")
        self.assertEqual(self.page.locator("#body-workboard .body-row.selected").get_attribute("data-body-id"), "4")

        state["profile"]["key"] = "another-commander"
        self.render(state)
        self.assertEqual(self.page.locator("#body-workboard .body-row.selected").count(), 0)
        self.page.locator('#survey-body-list .survey-body-row[data-body-id="3"]').click()
        self.assertEqual(self.page.locator("#body-workboard .body-row.selected").count(), 1)
        state["flight"]["system"] = "SOL"
        state["survey"]["bodies"] = [{"body_id": 1, "name": "SOL 1"}]
        self.render(state)
        self.assertEqual(self.page.locator("#body-workboard .body-row.selected").count(), 0)
        self.assertEqual(self.page.locator("#body-workboard .body-row").count(), 1)
        self.assertFalse(self.errors, self.errors)

    def test_survey_board_distinguishes_journal_and_manual_completion(self):
        state = overview_state()
        names = {1: "JOURNAL WORLD", 2: "MANUAL WORLD", 3: "PENDING WORLD"}
        state["survey"]["bodies"] = [
            {"body_id": body_id, "name": f"SYNUEFE AA-A H1 {body_id}", "planet_class": "Rocky body"}
            for body_id in names
        ]
        self.render(state)
        rows = [
            {"key": "body:1", "body": "SYNUEFE AA-A H1 1", "status": "complete",
             "manual_complete": False, "action": "Observe", "reason": names[1]},
            {"key": "body:2", "body": "SYNUEFE AA-A H1 2", "status": "complete",
             "manual_complete": True, "action": "Observe", "reason": names[2]},
            {"key": "body:3", "body": "SYNUEFE AA-A H1 3", "status": "pending", "score": 100,
             "action": "DSS map", "reason": names[3]},
        ]
        self.page.evaluate("data => window.__overviewHarness.workspace(data)", {
            "current": "SYNUEFE AA-A H1",
            "cartography": {"system": "SYNUEFE AA-A H1", "queue": {"rows": rows, "next": rows[2]}},
        })
        board = self.page.locator("#body-workboard")
        # Open work ranks first and carries the recommendation.
        self.assertEqual(board.locator(".body-row").first.get_attribute("data-body-id"), "3")
        self.assertEqual(board.locator(".body-row.next").get_attribute("data-body-id"), "3")
        complete = lambda body_id: board.locator(
            f'.body-row[data-body-id="{body_id}"] [data-ws-op="survey_complete"]')
        self.assertEqual(complete(1).inner_text(), "JOURNAL ✓")
        self.assertFalse(complete(1).is_enabled())
        self.assertEqual(complete(2).inner_text(), "REOPEN")
        self.assertTrue(complete(2).is_enabled())
        self.assertEqual(complete(3).inner_text(), "DONE")
        self.assertTrue(complete(3).is_enabled())
        self.assertEqual(complete(3).get_attribute("data-body-key"), "body:3")
        self.assertEqual(complete(3).get_attribute("data-system"), "SYNUEFE AA-A H1")
        self.assertFalse(self.errors, self.errors)

    def test_return_later_action_id_is_forwarded(self):
        self.render(overview_state())
        self.page.locator('.nav-item[data-page="explore"]').click()
        self.page.evaluate("""() => {
          document.getElementById('explore-workspace').innerHTML =
            '<button data-ws-page="explore" data-ws-op="return_later_waypoint" data-return-later-id="system:body">ADD WAYPOINT</button>';
        }""")
        with self.page.expect_request(lambda request: urlsplit(request.url).path == "/api/command"
                                      and request.post_data_json.get("action") == "workspace") as captured:
            self.page.locator('[data-ws-op="return_later_waypoint"]').click()
        payload = captured.value.post_data_json
        self.assertEqual(payload["operation"], "return_later_waypoint")
        self.assertEqual(payload["id"], "system:body")
        self.assertFalse(self.errors, self.errors)

    def test_saved_overview_layout_keeps_legacy_core_panel_keys(self):
        state = overview_state()
        saved_order = ["current-system-survey", "route", "smart-next-action",
                       "exploration-preflight"]
        state["page_layouts"] = {"overview": {"overview-modules": saved_order}}
        self.render(state)
        actual = self.page.locator("#overview-modules > [data-layout-panel]").evaluate_all(
            "nodes => nodes.map(node => node.dataset.layoutPanel)")
        self.assertEqual(actual[:len(saved_order)], saved_order)
        self.assertFalse(self.errors, self.errors)

    def test_arrange_panels_still_uses_the_redesigned_cards(self):
        self.render(overview_state())
        self.page.locator('[data-page-layout-open="overview"]').click()
        self.assertIn("layout-editing", self.page.locator('[data-page-name="overview"]').get_attribute("class"))
        self.assertEqual(self.page.locator("#overview-modules > .layout-panel").count(), 9)
        self.assertEqual(self.page.locator(".decision-lens").evaluate(
            "node => getComputedStyle(node).visibility"), "hidden")
        self.page.locator('[data-page-layout-cancel]').click()
        self.assertNotIn("layout-editing", self.page.locator('[data-page-name="overview"]').get_attribute("class"))
        self.assertEqual(self.page.locator(".decision-lens").evaluate(
            "node => getComputedStyle(node).visibility"), "visible")
        self.assertFalse(self.errors, self.errors)

    def test_bridge_instruments_follow_profile_theme(self):
        state = overview_state()
        self.render(state)
        def palette_readout():
            return self.page.evaluate("""() => {
              const root = getComputedStyle(document.documentElement);
              const css = selector => getComputedStyle(document.querySelector(selector));
              return {
                accent: root.getPropertyValue('--accent').trim(),
                orange: root.getPropertyValue('--orange').trim(),
                green: root.getPropertyValue('--green').trim(),
                lens: css('.decision-lens').borderTopColor,
                orbital: css('#survey-orbital').backgroundImage,
                radar: css('.route-radar').borderTopColor,
                link: css('#overview-link-state').color,
              };
            }""")
        baseline = palette_readout()
        state["theme"] = {"name": "Bridge Test", "palette": {
            "accent": "#bf73ff", "orange": "#ffcb55", "green": "#46dd87",
        }}
        self.render(state)
        themed = palette_readout()
        self.assertEqual(themed["accent"].lower(), "#bf73ff")
        self.assertEqual(themed["orange"].lower(), "#ffcb55")
        self.assertEqual(themed["green"].lower(), "#46dd87")
        for instrument in ("lens", "orbital", "radar", "link"):
            self.assertNotEqual(themed[instrument], baseline[instrument], (instrument, baseline, themed))
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
                  const masthead = box('.overview-masthead');
                  const decision = box('.overview-modules > .decision-card');
                  const preflight = box('.overview-modules > .preflight-card');
                  const survey = box('.overview-modules > .survey-card');
                  const route = box('.overview-modules > .route-card');
                  const status = box('.statusbar');
                  const cards = [...document.querySelectorAll('.overview-modules > :not([hidden])')]
                    .map(node => node.getBoundingClientRect());
                  const inside = (child, parent) => child.left >= parent.left - 1
                    && child.right <= parent.right + 1
                    && child.top >= parent.top - 1 && child.bottom <= parent.bottom + 1;
                  const controls = [...document.querySelectorAll('.overview-actions button')]
                    .map(node => node.getBoundingClientRect());
                  return {
                    viewport: window.innerWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    mastheadAboveCards: masthead.bottom <= decision.top + 1,
                    primaryHierarchy: decision.top <= survey.top + 1 && preflight.top <= survey.top + 1,
                    actionsFit: controls.every(rect => inside(rect, masthead)),
                    instrumentsFit: inside(box('.decision-lens'), decision)
                      && inside(box('#decision-primary'), decision)
                      && inside(box('#preflight-signal'), preflight)
                      && inside(box('#survey-orbital'), survey)
                      && inside(box('.route-radar'), route),
                    cardsFit: cards.every(rect => rect.left >= page.left - 1 && rect.right <= page.right + 1),
                    pair: Math.abs(survey.top - route.top) <= 2 && survey.right <= route.left + 2,
                    statusVisible: status.height >= 25 && Math.abs(status.bottom - innerHeight) <= 1
                      && status.left >= 0 && status.right <= innerWidth + 1,
                  };
                }""")
                self.assertLessEqual(geometry["scrollWidth"], geometry["viewport"] + 1, geometry)
                self.assertTrue(geometry["mastheadAboveCards"], geometry)
                self.assertTrue(geometry["primaryHierarchy"], geometry)
                self.assertTrue(geometry["actionsFit"], geometry)
                self.assertTrue(geometry["instrumentsFit"], geometry)
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
