"""Browser checks for the Explore & Survey page (web/dashboard/explore.js).

The page shows one live system model in three views -- System survey, Route &
waypoints and Prospects -- that each fit the window and scroll their own
lists. Workspace data is built with the real stellar-cartography builders so
the Python payload and the renderer are exercised together.
"""

import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from tests.test_dashboard_overview_visuals import overview_state
from voidcompass.exploration.exploration_intelligence import system_completion
from voidcompass.exploration.exploration_scout import SCOUT_MODES, system_audit
from voidcompass.exploration.stellar_cartography import (
    build_orrery, build_planetary_resources, build_survey_queue,
)


WEB = Path(__file__).resolve().parents[1] / "web"
SYSTEM = "SYNUEFE XR-H D11-102"
LS = 299_792_458


def _body(body_id, suffix, planet_class, distance, **extra):
    return {
        "body_id": body_id, "name": f"{SYSTEM} {suffix}", "planet_class": planet_class,
        "distance_to_arrival": distance, "parents": [{"Star": 0}],
        "semi_major_axis": distance * LS, "orbital_period": 86400 * (5 + body_id * 9),
        "eccentricity": .02, "orbital_inclination": 1, "periapsis": 40,
        "ascending_node": body_id * 25, "mean_anomaly": body_id * 40,
        "scan_timestamp": "2026-09-26T09:00:00Z", **extra,
    }


SCAN_ITEMS = [
    {"body_id": 0, "name": f"{SYSTEM} A", "is_star": True, "star_type": "K", "planet_class": ""},
    _body(1, "A 1", "High metal content body", 12, landable=True, geo_count=3, reward=41000,
          materials=[{"name": "Polonium", "percent": 1.1}, {"name": "Iron", "percent": 21}]),
    _body(2, "A 2", "Icy body", 45, reward=1400),
    _body(3, "A 3", "High metal content body", 88, landable=True, bio_count=3, reward=38000,
          dss_complete=True, gravity_g=.21, atmosphere_type="Thin sulphur dioxide"),
    _body(4, "B 1", "Water world", 1200, terraformable=True, reward=1210000),
    _body(5, "B 2", "Icy body", 1210, landable=True, bio_count=4, reward=2800),
    _body(6, "B 3", "Rocky ice body", 1300, landable=True, bio_count=2, dss_complete=True,
          reward=4000, organic_scans={"a": {"is_complete": True}, "b": {"is_complete": True}}),
]


def workspace_data(queue_state=None, target=None, waypoints=12, entries=3):
    queue = build_survey_queue(SCAN_ITEMS, queue_state or {"pinned": ["body:5"]}, target)
    completion = system_completion(SCAN_ITEMS, 7, 9, current_system=SYSTEM)
    return {
        "current": SYSTEM, "destination": "COL 285 SECTOR OX-U C17-4",
        "nav_route": [{"index": index, "system": f"ROUTE STOP {index}", "star_class": "K",
                       "distance": 40.0 + index, "current": index == 0, "passed": False}
                      for index in range(6)],
        "waypoints": [{"index": index, "name": f"WAYPOINT {index}", "visited": index == 0,
                       "note": "", "coords_known": True, "distance": 20.0}
                      for index in range(waypoints)],
        "next_waypoint": "WAYPOINT 1", "auto_copy": False,
        "return_later": {"entries": [{"id": f"r:{index}", "system": f"RETURN SYSTEM {index}",
                                      "body": "", "reasons": ["4 FSS bodies unresolved"],
                                      "last_visited": "2026-09-25T10:20:00Z", "source": "journal"}
                                     for index in range(entries)]},
        "cartography": {"system": SYSTEM, "target": target,
                        "orrery": build_orrery(SCAN_ITEMS, target, []), "queue": queue,
                        "resources": build_planetary_resources(SCAN_ITEMS)},
        "scout": {"reference": SYSTEM, "mode": "biology", "modes": SCOUT_MODES, "radius": 500,
                  "min_signals": 1, "min_value": 500000, "max_results": 20, "jump_range": 40,
                  "status": "ready", "detail": "Ready.", "results": [],
                  "audit": system_audit(completion, queue),
                  "codex": {"region": "Inner Orion Spur", "candidates": [{"name": "Bacterium Tela"}]}},
        "plotter": {"from": SYSTEM, "to": "BEAGLE POINT", "range": 40, "efficiency": 60,
                    "multiplier": 4, "status": "ready", "detail": "Ready.", "result": None},
    }


def snapshot_state(extra_bodies=()):
    state = overview_state()
    state["profile"]["key"] = "explore-visual-test"
    state["flight"]["system"] = SYSTEM
    bodies = [{"body_id": row["body_id"], "name": row["name"], "planet_class": row["planet_class"],
               "bio_count": row.get("bio_count", 0), "geo_count": row.get("geo_count", 0),
               "mapped": bool(row.get("dss_complete")), "priority": bool(row.get("bio_count")),
               "detail": "SURVEY RECORD", "latest_scan": row["body_id"] == 3}
              for row in SCAN_ITEMS[1:]]
    bodies.extend(extra_bodies)
    state["survey"].update({"total_known": True, "scanned": 7, "total": 9, "percent": 77.8,
                            "star_class": "K", "bio_signals": 9, "bio_complete": 2,
                            "geo_signals": 3, "bodies": bodies})
    return state


class ExploreSurveyVisualTests(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={"width": 1380, "height": 850})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("dialog", lambda dialog: dialog.accept())

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                route.fulfill(content_type="application/json", body='{"closing":true}')
                return
            if path == "/api/command":
                route.fulfill(content_type="application/json", body='{"accepted":true}')
                return
            if path == "/api/snapshot":
                route.fulfill(content_type="application/json", body=json.dumps(overview_state()))
                return
            file = WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                source = file.read_text(encoding="utf-8") + """
                  window.__exploreHarness = {
                    render(data) {
                      model = data;
                      applyTheme(data.theme || {});
                      document.body.classList.add('ready');
                      document.getElementById('boot').hidden = true;
                      document.getElementById('app').setAttribute('aria-hidden', 'false');
                      renderDashboard(data);
                    },
                    show(name) { showPage(name); },
                    workspace(data) { renderExploreWorkspace(data, EXPLORE_WORKSPACE_UI); },
                    fail(error) {
                      model.workspace = {page: 'explore', ready: false, error};
                      renderWorkspace(model);
                    },
                    orreryPick(id) { orreryView.select(id); },
                  };
                """
                route.fulfill(content_type="application/javascript", body=source)
            elif file.is_file():
                route.fulfill(path=str(file))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://explore.test/**", serve)
        self.load()

    def tearDown(self):
        self.context.close()

    def load(self):
        self.page.goto("http://explore.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__exploreHarness)")

    def open_explore(self, state=None, data=None):
        self.page.evaluate("state => window.__exploreHarness.render(state)", state or snapshot_state())
        self.page.evaluate("() => window.__exploreHarness.show('explore')")
        self.page.evaluate("data => window.__exploreHarness.workspace(data)", data or workspace_data())

    def board_ids(self, visible_only=False):
        selector = "#body-workboard .body-row" + (":visible" if visible_only else "")
        return self.page.locator(selector).evaluate_all("rows => rows.map(row => row.dataset.bodyId)")

    def test_every_view_fits_the_window_with_its_controls_on_screen(self):
        controls = {
            "system": ["#body-workboard", '#body-workboard .body-row.next [data-ws-op="survey_pin"]',
                       '[data-explore-filter="todo"]', "#system-orrery-canvas", "#orrery-detail",
                       "#explore-survey-reset"],
            "route": ["#waypoint-name", '[data-ws-op="add_waypoint"]', '[data-ws-op="copy_next"]',
                      "#neutron-to", '[data-ws-op="neutron_plot"]', '[data-ws-op="clear_waypoints"]'],
            "prospects": ['.return-later-entry [data-ws-op="return_later_waypoint"]',
                          "#scout-reference", '[data-ws-op="scout_search"]', ".scout-codex-row"],
        }
        for width, height in ((1380, 850), (1920, 1080)):
            self.page.set_viewport_size({"width": width, "height": height})
            self.open_explore()
            for view, selectors in controls.items():
                with self.subTest(size=f"{width}x{height}", view=view):
                    self.page.locator(f"#explore-tab-{view}").click()
                    report = self.page.evaluate("""selectors => {
                      const pages = document.querySelector('.pages');
                      const box = pages.getBoundingClientRect();
                      return {overflow: pages.scrollHeight - pages.clientHeight,
                        outside: selectors.filter(selector => {
                          const node = document.querySelector(selector);
                          if (!node) return true;
                          const r = node.getBoundingClientRect();
                          return !r.height || r.top < box.top - 1 || r.bottom > box.bottom + 1;
                        })};
                    }""", selectors)
                    # Nothing on this page needs a page scroll; long lists scroll inside.
                    self.assertLessEqual(report["overflow"], 0, report)
                    self.assertEqual(report["outside"], [], report)
        self.page.locator("#explore-tab-route").click()
        waypoints = self.page.locator('[data-scroll-key="waypoints"]')
        self.assertTrue(waypoints.evaluate("node => node.scrollHeight > node.clientHeight"))
        self.assertFalse(self.errors, self.errors)

    def test_views_switch_by_click_and_keyboard_and_are_remembered(self):
        self.open_explore()
        tabs = {view: self.page.locator(f"#explore-tab-{view}") for view in ("system", "route", "prospects")}
        panels = {view: self.page.locator(f"#explore-view-{view}") for view in tabs}
        self.assertEqual(tabs["system"].get_attribute("aria-selected"), "true")
        self.assertTrue(panels["system"].is_visible())
        tabs["route"].click()
        self.assertEqual([panels[view].is_visible() for view in tabs], [False, True, False])
        self.assertEqual(tabs["route"].get_attribute("aria-selected"), "true")
        self.assertEqual(tabs["route"].get_attribute("tabindex"), "0")
        self.assertIn("6 STOPS", tabs["route"].inner_text())
        tabs["route"].press("ArrowRight")
        self.assertTrue(panels["prospects"].is_visible())
        self.assertTrue(tabs["prospects"].evaluate("node => node === document.activeElement"))
        tabs["prospects"].press("Home")
        self.assertTrue(panels["system"].is_visible())
        tabs["system"].press("ArrowLeft")
        self.assertTrue(panels["prospects"].is_visible())
        # A live refresh keeps the pilot's view; so does reopening the page.
        self.page.evaluate("data => window.__exploreHarness.workspace(data)", workspace_data())
        self.assertTrue(panels["prospects"].is_visible())
        self.load()
        self.open_explore()
        self.assertTrue(self.page.locator("#explore-view-prospects").is_visible())
        # The Dashboard's survey link always opens the System view.
        self.page.locator('.nav-item[data-page="overview"]').click()
        self.page.locator("#survey-open-workboard").click()
        self.assertTrue(self.page.locator("#explore-view-system").is_visible())
        self.assertFalse(self.errors, self.errors)

    def test_board_ranks_open_work_first_and_filters_without_dropping_bodies(self):
        signal_only = {"body_id": 7, "name": f"{SYSTEM} C 1", "planet_class": "", "bio_count": 2,
                       "signal_only": True, "detail": "BIOLOGICAL SIGNALS"}
        archive = {"body_id": 8, "name": f"{SYSTEM} C 2", "planet_class": "Icy body",
                   "archived": True, "detail": "KNOWN ARCHIVE"}
        self.open_explore(snapshot_state([signal_only, archive]),
                          workspace_data({"pinned": ["body:5"], "skipped": ["body:2"]}))
        board = self.page.locator("#body-workboard")
        order = self.board_ids()
        self.assertEqual(sorted(order, key=int), [str(index) for index in range(1, 9)])
        # Pinned first, then open queue work, awaiting scans, skipped, complete, archive.
        self.assertEqual(order[0], "5")
        self.assertEqual(order[-3:], ["2", "6", "8"])
        status = lambda body_id: board.locator(f'.body-row[data-body-id="{body_id}"]').get_attribute("class")
        self.assertIn("status-pinned", status(5))
        self.assertIn("status-awaiting", status(7))
        self.assertIn("status-skipped", status(2))
        self.assertIn("status-complete", status(6))
        self.assertIn("status-known", status(8))
        self.assertEqual(board.locator(".body-row.next").get_attribute("data-body-id"), "5")
        self.assertEqual(board.locator('.body-row[data-body-id="3"] .tag.latest').count(), 1)
        self.assertEqual(board.locator('.body-row[data-body-id="1"] .chip.rare').inner_text(), "RARE 1")
        # Only journal-scanned queue bodies carry commander actions.
        self.assertEqual(board.locator('.body-row[data-body-id="7"] .body-actions').count(), 0)
        self.assertEqual(board.locator('.body-row[data-body-id="8"] .body-actions').count(), 0)
        self.assertEqual(board.locator('.body-row[data-body-id="2"] [data-ws-op="survey_skip"]').inner_text(),
                         "RESTORE")
        counts = self.page.locator("[data-filter-count]").evaluate_all(
            "nodes => Object.fromEntries(nodes.map(node => [node.dataset.filterCount, node.textContent]))")
        self.assertEqual(counts, {"all": "8", "todo": "5", "bio": "4", "done": "2"})
        self.page.locator('[data-explore-filter="done"]').click()
        self.assertEqual(sorted(self.board_ids(visible_only=True)), ["2", "6"])
        self.page.locator('[data-explore-filter="bio"]').click()
        self.assertEqual(sorted(self.board_ids(visible_only=True)), ["3", "5", "6", "7"])
        self.page.locator('[data-explore-filter="all"]').click()
        self.assertEqual(len(self.board_ids(visible_only=True)), 8)
        # Every body stays in the DOM whatever the filter.
        self.assertEqual(len(self.board_ids()), 8)
        self.assertFalse(self.errors, self.errors)

    def test_board_and_orrery_share_one_selection(self):
        signal_only = {"body_id": 7, "name": f"{SYSTEM} C 1", "planet_class": "", "bio_count": 2,
                       "signal_only": True}
        self.open_explore(snapshot_state([signal_only]))
        detail = self.page.locator("#orrery-detail")
        # With nothing picked, the orrery opens on the recommended next body.
        self.assertIn(f"{SYSTEM} B 2", detail.inner_text())
        self.page.locator('#body-workboard .body-row[data-body-id="4"] .body-select').click()
        selected = self.page.locator("#body-workboard .body-row.selected")
        self.assertEqual(selected.get_attribute("data-body-id"), "4")
        self.assertEqual(selected.get_attribute("aria-current"), "true")
        self.assertIn(f"{SYSTEM} B 1", detail.inner_text())
        self.assertIn("TERRAFORMABLE", detail.inner_text())
        self.page.evaluate("() => window.__exploreHarness.orreryPick('1')")
        self.assertEqual(selected.get_attribute("data-body-id"), "1")
        self.assertIn("Polonium", detail.inner_text())
        self.page.locator('#body-workboard .body-row[data-body-id="7"] .body-select').click()
        self.assertIn("NOT YET IN THE ORRERY", detail.inner_text())
        # A live refresh keeps the pick on both sides.
        self.page.evaluate("data => window.__exploreHarness.workspace(data)",
                           workspace_data({"pinned": ["body:5"], "skipped": ["body:2"]}))
        self.assertEqual(selected.get_attribute("data-body-id"), "7")
        self.assertIn("NOT YET IN THE ORRERY", detail.inner_text())
        self.assertFalse(self.errors, self.errors)

    def test_elite_target_lock_takes_the_selection(self):
        target = {"name": f"{SYSTEM} A 2", "body": 2, "system": SYSTEM}
        self.open_explore(data=workspace_data(target=target))
        self.assertIn(f"{SYSTEM} A 2", self.page.locator("#explore-orrery .cartography-target-lock").inner_text())
        row = self.page.locator('#body-workboard .body-row[data-body-id="2"]')
        self.assertIn("status-targeted", row.get_attribute("class"))
        self.assertEqual(self.board_ids()[0], "2")
        self.assertEqual(self.page.locator("#body-workboard .body-row.selected").get_attribute("data-body-id"), "2")
        self.assertIn(f"{SYSTEM} A 2", self.page.locator("#orrery-detail").inner_text())
        self.assertFalse(self.errors, self.errors)

    def test_refresh_keeps_list_scroll_and_an_error_panel_recovers(self):
        self.open_explore(data=workspace_data(waypoints=30))
        self.page.locator("#explore-tab-route").click()
        waypoints = self.page.locator('[data-scroll-key="waypoints"]')
        waypoints.evaluate("node => { node.scrollTop = 180; }")
        refreshed = workspace_data(waypoints=31)
        self.page.evaluate("data => window.__exploreHarness.workspace(data)", refreshed)
        self.assertEqual(waypoints.evaluate("node => node.scrollTop"), 180)
        self.assertEqual(self.page.locator(".waypoint-row").count(), 31)
        self.page.evaluate("() => window.__exploreHarness.fail('journal link interrupted')")
        self.assertIn("COMMANDER RECORD LINK INTERRUPTED",
                      self.page.locator("#explore-workspace").inner_text())
        self.assertEqual(self.page.locator("#explore-workspace .explore-views").count(), 0)
        # The next good payload rebuilds the views and the live board with it.
        self.page.evaluate("data => window.__exploreHarness.workspace(data)", refreshed)
        self.assertEqual(self.page.locator("#explore-workspace .explore-views").count(), 1)
        self.assertTrue(self.page.locator("#explore-view-route").is_visible())
        self.assertEqual(len(self.board_ids()), 6)
        self.assertIn("SYNUEFE XR-H", self.page.locator("#workboard-system").inner_text().upper())
        self.assertFalse(self.errors, self.errors)


if __name__ == "__main__":
    unittest.main()
