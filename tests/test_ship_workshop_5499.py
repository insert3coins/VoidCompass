"""Ship Workshop rewrite (5.4.9.9): workshop.js pages over the planner and companion models."""

from __future__ import annotations

import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from voidcompass.engineering import build_planner, engineering_companion

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
IMAGES = ROOT / "assets" / "images"


def _adder():
    ship = next(row for row in build_planner.ship_catalogue() if row["name"] == "Adder")
    return build_planner.stock_build(ship["id"], "Test Adder")


class WorkshopModelTests(unittest.TestCase):
    def test_range_curve_runs_from_unladen_to_laden_in_eighths(self):
        analysis = build_planner.calculate(_adder())
        curve = analysis["navigation"]["curve"]
        self.assertEqual(len(curve), 9)
        self.assertEqual(curve[0]["cargo"], 0)
        self.assertAlmostEqual(curve[-1]["cargo"], analysis["totals"]["cargo"])
        self.assertAlmostEqual(curve[0]["jump"], analysis["navigation"]["unladenJump"])
        self.assertAlmostEqual(curve[-1]["jump"], analysis["navigation"]["ladenJump"])
        jumps = [point["jump"] for point in curve]
        self.assertEqual(jumps, sorted(jumps, reverse=True))

    def test_a_hull_without_a_hold_has_no_curve(self):
        holdless = [analysis for analysis in (build_planner.calculate(build_planner.stock_build(ship["id"]))
                                              for ship in build_planner.ship_catalogue()) if analysis["totals"]["cargo"] == 0]
        self.assertTrue(holdless)
        for analysis in holdless:
            self.assertNotIn("curve", analysis["navigation"])

    def test_builds_and_the_live_loadout_carry_their_hull_art(self):
        state = {"build_planner_builds": [_adder()]}
        companion = {"loadout": {"event": "Loadout", "Ship": "adder", "ShipName": "Little Wing", "ShipID": 3, "Modules": []}}
        workspace = build_planner.workspace(state, companion, {})
        self.assertTrue(workspace["builds"][0]["asset"].endswith(".svg"))
        live = workspace["live"]
        self.assertTrue(live["available"])
        self.assertEqual(live["name"], "Little Wing")
        self.assertEqual(live["ship"], "Adder")
        self.assertTrue(live["asset"].endswith(".svg"))

    def test_journal_blueprint_symbols_read_as_the_game_names_them(self):
        names = build_planner.journal_engineering_names()
        self.assertEqual(names[build_planner._key("FSD_LongRange")], "Increased Range")
        self.assertEqual(names[build_planner._key("special_auto_loader")], "Auto Loader")
        companion = {"loadout": {"event": "Loadout", "Ship": "adder", "ShipName": "Little Wing", "ShipID": 3, "Modules": [
            {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_size3_class5", "On": True, "Priority": 0,
             "Engineering": {"BlueprintName": "FSD_LongRange", "Level": 5, "Quality": 0.8}},
            {"Slot": "PowerPlant", "Item": "int_powerplant_size3_class5", "On": True, "Priority": 0},
        ]}}
        model = engineering_companion.build_workspace({}, companion)
        rows = {row["slot"]: row for row in model["slots"]}
        self.assertEqual(rows["FrameShiftDrive"]["blueprintName"], "Increased Range")
        self.assertEqual(rows["PowerPlant"]["blueprintName"], "")

    def test_the_pages_are_one_module_with_its_own_styles(self):
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        index = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        workshop = (WEB / "dashboard" / "workshop.js").read_text(encoding="utf-8")
        self.assertIn('from "./workshop.js"', app)
        self.assertIn('href="workshop.css"', index)
        self.assertIn("renderEngineering(data, WORKSHOP_UI)", app)
        self.assertIn("renderBuildPlanner(data, WORKSHOP_UI)", app)
        # The old renderers and their view state are gone from app.js.
        for retired in ("bp-stat-grid", "buildPlannerSelectedSlot", "engineeringMaterialFilter", "engineering-suite-nav"):
            self.assertNotIn(retired, app)
        # Every op the pages send is one the backend knows.
        for op in ("select", "compare", "set_module", "set_load", "configure_slot", "create", "clone", "rename", "delete",
                   "export_copy", "send_engineering", "import_preview", "import_apply", "select_ship", "follow_current",
                   "unpin", "copy_system", "odyssey_pin", "odyssey_unpin"):
            self.assertTrue(f'"{op}"' in workshop or f'data-ws-op="{op}"' in workshop, op)


class WorkshopBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        from tests.test_dashboard_overview_visuals import overview_state
        cls.overview_state = staticmethod(overview_state)
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
        self.page = self.browser.new_page(viewport={"width": 1600, "height": 1000})
        self.errors, self.commands = [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        state = self.overview_state()

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                return route.fulfill(content_type="application/json", body='{"closing":true}')
            if path == "/api/command":
                self.commands.append(json.loads(route.request.post_data or "{}"))
                return route.fulfill(content_type="application/json", body='{"accepted":true}')
            if path == "/api/snapshot":
                return route.fulfill(content_type="application/json", body=json.dumps(state))
            file = IMAGES / path.removeprefix("/dashboard/images/") if path.startswith("/dashboard/images/") else WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + """
                  window.__ws = {
                    render(data) { model = data; applyTheme(data.theme || {}); document.body.classList.add('ready');
                      document.getElementById('boot').hidden = true; renderDashboard(data); },
                    workspace(name, data) { document.querySelectorAll('.page').forEach(n => n.classList.toggle('active', n.dataset.pageName === name));
                      currentPage = name; model.workspace = {page: name, ready: true, data}; workspaceFingerprints[name] = ''; renderWorkspace(model); },
                  };""")
            if file.is_file():
                return route.fulfill(path=str(file))
            return route.fulfill(status=404, body="")

        self.page.route("http://deck.test/**", serve)
        self.page.goto("http://deck.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__ws)")
        self.page.evaluate("d => window.__ws.render(d)", state)

    def tearDown(self):
        self.page.close()

    def workspace_commands(self):
        return [row for row in self.commands if row.get("action") == "workspace"]

    def test_planner_fits_engineers_and_balances_the_distributor(self):
        build = _adder()
        data = build_planner.workspace({"build_planner_builds": [build], "build_planner_selected": build["id"]}, {}, {})
        self.page.evaluate("d => window.__ws.workspace('build-planner', d)", data)
        self.page.wait_for_selector(".wk-bay")
        self.assertEqual(self.page.locator(".wk-slot").count(), len(data["slots"]))
        # The hull loads inline and lights the chosen hardpoint.
        self.page.wait_for_selector(".wk-hull svg [data-journal-slot]")
        self.page.locator('.wk-slot[data-bp-slot^="hardpoint:"]').first.click()
        self.page.wait_for_selector(".wk-hull svg [data-journal-slot].lit")
        # Fitting a module sends the chosen slot.
        slot = self.page.locator(".wk-slot.active").get_attribute("data-bp-slot")
        self.page.locator(".wk-module:not(.active):not(.clear)").first.click()
        self.page.wait_for_function("() => true")
        fitted = [row for row in self.workspace_commands() if row.get("operation") == "set_module"]
        self.assertEqual(fitted[-1]["slot"], slot)
        # A pip takes its difference from the other two axes: 12 half-pips always.
        self.page.locator('[data-wk-pip="sys"][data-level="8"]').click()
        self.page.wait_for_timeout(100)
        loads = [row for row in self.workspace_commands() if row.get("operation") == "set_load"]
        pips = loads[-1]["pips"]
        self.assertEqual(pips["sys"], 8)
        self.assertEqual(sum(pips.values()), 12)
        self.assertEqual(self.page.locator('[data-wk-pip="sys"].on').count(), 8)
        # The engineer tab sends the dock's form for the chosen slot.
        self.page.locator('.wk-slot[data-bp-slot="component:3"]').click()
        self.page.locator('[data-wk-dock="engineer"]').click()
        self.page.locator('[data-wk-seg="bp-grade"] .wk-segbtn[data-value="3"]').click()
        self.page.locator('[data-ws-op="configure_slot"]').click()
        self.page.wait_for_timeout(100)
        configured = [row for row in self.workspace_commands() if row.get("operation") == "configure_slot"]
        self.assertEqual(configured[-1]["slot"], "component:3")
        self.assertEqual(str(configured[-1]["grade"]), "3")
        self.assertEqual(self.errors, [])

    def test_hangar_tiles_select_builds_and_the_new_drawer_picks_a_hull(self):
        first, second = _adder(), build_planner.stock_build(1, "Second")
        data = build_planner.workspace({"build_planner_builds": [first, second], "build_planner_selected": first["id"]}, {}, {})
        self.page.evaluate("d => window.__ws.workspace('build-planner', d)", data)
        self.page.locator(f'[data-wk-build="{second["id"]}"]').click()
        self.page.wait_for_timeout(100)
        selected = [row for row in self.workspace_commands() if row.get("operation") == "select"]
        self.assertEqual(selected[-1]["build_id"], second["id"])
        self.page.locator('[data-bp-focus="new"]').click()
        self.assertTrue(self.page.locator("#bp-new-build").is_visible())
        pick = self.page.locator(".wk-hullpick").nth(3)
        pick.click()
        self.assertEqual(self.page.locator("#bp-new-ship").input_value(), pick.get_attribute("data-wk-hullpick"))
        self.assertEqual(self.errors, [])

    def test_engineering_tabs_render_from_the_companion_model(self):
        companion = {"loadout": {"event": "Loadout", "Ship": "adder", "ShipName": "Little Wing", "ShipID": 3, "Modules": [
            {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_size3_class5", "On": True, "Priority": 0,
             "Engineering": {"BlueprintName": "FSD_LongRange", "Level": 5, "Quality": 0.8}},
        ]}}
        data = engineering_companion.build_workspace({"raw": {"arsenic": 12}}, companion)
        data["follow_current"] = True
        data["odyssey"] = {"goals": [], "materials": [], "required": 0, "missing": 0, "complete": False, "catalogue": []}
        self.page.evaluate("d => window.__ws.workspace('engineering', d)", data)
        self.page.wait_for_selector(".wk-ebay")
        self.assertIn("Increased Range", self.page.locator(".wk-pane").inner_text())
        for tab in ("plans", "materials", "engineers", "blueprints", "sources", "brokers", "odyssey", "ship"):
            self.page.locator(f'[data-engineering-view="{tab}"]').click()
            self.page.wait_for_selector(f".wk-pane-{tab}")
        self.page.locator('[data-engineering-view="materials"]').click()
        self.page.locator('[data-engineering-material-filter="empty"]').click()
        self.assertGreater(self.page.locator(".wk-mat.dim").count(), 0)
        self.assertEqual(self.page.locator(".wk-mat").count(), len(data["materials"]))
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
