from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from voidcompass.engineering import build_planner
from voidcompass.engineering import engineering_companion
from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.core.version import APP_VERSION


class _PlannerDashboard(HtmlDashboardMixin):
    def __init__(self):
        self.engineer_materials = {}
        self.companion_state = {}
        self._tools = {}

    def _html_profile_transient(self, name, default):
        return self._tools.setdefault(name, dict(default))

    def _save_engineer_materials(self, state):
        self.engineer_materials = state
        return True

    def _schedule_html_dashboard_publish(self, **_kwargs):
        return None


class BuildPlanner546Tests(unittest.TestCase):
    def test_new_build_is_a_prominent_action_with_planner_button_styling(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (root / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        styles = (root / "web" / "dashboard" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('class="primary" data-bp-focus="new"', html)
        self.assertIn('<section class="bp-new-build" id="bp-new-build">', script)
        self.assertNotIn("<summary>NEW STOCK BUILD</summary>", script)
        self.assertIn(".bp-manager-actions button", styles)
        self.assertIn('".bp-slot", ".bp-module"', script)

    def test_catalogue_contains_current_ship_and_module_sets(self):
        self.assertEqual(len(build_planner.ship_catalogue()), 48)
        self.assertEqual(len(build_planner.catalogue()["modules"]), 958)
        self.assertTrue(any(row["name"] == "Caspian Explorer" for row in build_planner.ship_catalogue()))
        self.assertTrue(all(row["asset"] for row in build_planner.ship_catalogue()))

    def test_every_stock_hull_is_valid_and_produces_finite_analysis(self):
        for ship in build_planner.ship_catalogue():
            with self.subTest(ship=ship["name"]):
                analysis = build_planner.calculate(build_planner.stock_build(ship["id"]))
                self.assertTrue(analysis["valid"], analysis["invalid"])
                self.assertGreater(analysis["totals"]["mass"], 0)
                self.assertGreater(analysis["navigation"]["currentJump"], 0)
                for section in ("totals", "navigation", "power", "thermal", "defenses", "weapons", "handling"):
                    for value in analysis[section].values():
                        if isinstance(value, (int, float)) and value is not None:
                            self.assertTrue(math.isfinite(value))

    def test_outfitting_and_engineering_change_calculated_performance(self):
        build = build_planner.stock_build(1)
        baseline = build_planner.calculate(build)["navigation"]["maxJump"]
        fsd_modules = [
            row for row in build_planner._compact_modules(1)
            if row["type"] == "cfsd" and row["class"] <= 2
        ]
        best = max(fsd_modules, key=lambda row: row["attrs"].get("fsdoptmass", 0))
        build = build_planner.set_module(build, "component:3", best["id"])
        blueprint = best["blueprints"][0]
        build = build_planner.configure_slot(build, "component:3", {
            "blueprint": blueprint, "grade": 5, "roll": 1,
            "experimental": "", "priority": 2, "enabled": True,
        })
        self.assertGreater(build_planner.calculate(build)["navigation"]["maxJump"], baseline)
        exported = json.loads(build_planner.export_slef(build))[0]["data"]
        fsd = next(row for row in exported["Modules"] if row["Slot"] == "FrameShiftDrive")
        self.assertEqual(fsd["Priority"], 1)
        self.assertTrue(fsd["Engineering"]["Modifiers"])
        imported = build_planner.parse_import(json.dumps([{"header": {"appName": "VoidCompass"}, "data": exported}]))["builds"][0]
        self.assertEqual(imported["slots"]["component:3"]["priority"], 2)
        self.assertTrue(imported["slots"]["component:3"]["modifiers"])
        self.assertAlmostEqual(
            build_planner.calculate(imported)["navigation"]["maxJump"],
            build_planner.calculate(build)["navigation"]["maxJump"], places=4,
        )

    def test_incompatible_module_is_rejected(self):
        build = build_planner.stock_build(1)
        oversized = next(row for row in build_planner._compact_modules(1) if row["type"] == "cpp" and row["class"] > 2)
        with self.assertRaises(build_planner.BuildPlannerError):
            build_planner.set_module(build, "component:1", oversized["id"])
        with self.assertRaises(build_planner.BuildPlannerError):
            build_planner.set_module(build, "component:1", 0)

    def test_edsy_long_url_import(self):
        url = ("https://edsy.org/#/L=Ff00000H4C0S00,Hf500FBR00FBR00,CzY00,"
               "9p300A5y00ALa00AbC00AnO00B2Q00BJm00BZY00,,"
               "05U007Q40003w0003w0002M000nG000nF00")
        preview = build_planner.parse_import(url)
        self.assertEqual(preview["count"], 1)
        self.assertEqual(preview["summary"][0]["ship"], "Adder")
        self.assertTrue(build_planner.calculate(preview["builds"][0])["valid"])

    def test_slef_round_trip_preserves_ship_and_modules(self):
        source = build_planner.stock_build(1, "Round trip")
        exported = build_planner.export_slef(source)
        document = json.loads(exported)
        self.assertEqual(document[0]["header"]["appVersion"], APP_VERSION)
        imported = build_planner.parse_import(exported)["builds"][0]
        self.assertEqual(imported["ship_id"], source["ship_id"])
        self.assertGreaterEqual(sum(bool(row.get("module")) for row in imported["slots"].values()), 10)

    def test_workspace_reuses_engineering_ship_art_and_supports_comparison(self):
        first = build_planner.stock_build(1, "Scout")
        second = build_planner.clone_build(first, "Scout copy")
        state = {
            "build_planner_builds": [first, second],
            "build_planner_selected": first["id"],
            "build_planner_compare": second["id"],
        }
        model = build_planner.workspace(state, {})
        self.assertTrue(model["selected"]["asset"].startswith("assets/engineering/ships/"))
        self.assertTrue(model["selected"]["editable"])
        self.assertEqual(model["comparison"]["build"]["id"], second["id"])

    def test_dashboard_commands_create_and_edit_profile_build(self):
        dashboard = _PlannerDashboard()
        self.assertTrue(dashboard._handle_html_workspace_command({
            "page": "build-planner", "operation": "create", "ship_id": 1,
            "name": "Command test",
        }))
        created = dashboard.engineer_materials["build_planner_builds"][0]
        self.assertEqual(created["name"], "Command test")
        self.assertTrue(dashboard._handle_html_workspace_command({
            "page": "build-planner", "operation": "configure_slot", "slot": "component:3",
            "priority": 3, "enabled": True, "blueprint": "", "grade": 0,
        }))
        updated = dashboard.engineer_materials["build_planner_builds"][0]
        self.assertEqual(updated["slots"]["component:3"]["priority"], 3)
        workspace = dashboard._html_workspace("build-planner")
        self.assertTrue(workspace["ready"])
        self.assertEqual(workspace["data"]["selected"]["id"], created["id"])

    def test_engineering_handoff_creates_material_backed_goal(self):
        build = build_planner.stock_build(1, "FSD plan")
        fsd = next(row for row in build_planner._compact_modules(1) if row["type"] == "cfsd" and row["class"] == 2 and row["rating"] == "A")
        build = build_planner.set_module(build, "component:3", fsd["id"])
        build = build_planner.configure_slot(build, "component:3", {
            "blueprint": "cfsd_ir", "grade": 5, "priority": 1, "enabled": True,
        })
        planned, pins = build_planner.engineering_plan(build)
        workspace = engineering_companion.build_workspace({
            "engineering_builds": [planned], "pinned_blueprints": pins,
        }, {})
        self.assertEqual(pins[0]["name"], "Increased FSD Range")
        self.assertEqual(pins[0]["source_build_id"], build["id"])
        self.assertGreater(len(workspace["pins"][0]["materials"]), 0)

    def test_engineering_handoff_refreshes_without_duplicate_build_or_goals(self):
        build = build_planner.stock_build(1, "FSD plan")
        fsd = next(
            row for row in build_planner._compact_modules(1)
            if row["type"] == "cfsd" and row["class"] == 2 and row["rating"] == "A"
        )
        build = build_planner.set_module(build, "component:3", fsd["id"])
        build = build_planner.configure_slot(build, "component:3", {
            "blueprint": "cfsd_ir", "grade": 5, "priority": 1, "enabled": True,
        })
        dashboard = _PlannerDashboard()
        dashboard.engineer_materials = {
            "build_planner_builds": [build],
            "build_planner_selected": build["id"],
        }

        command = {"page": "build-planner", "operation": "send_engineering"}
        self.assertTrue(dashboard._handle_html_workspace_command(command))
        self.assertTrue(dashboard._handle_html_workspace_command(command))

        state = dashboard.engineer_materials
        self.assertEqual(state.get("engineering_builds"), [])
        self.assertEqual(len(state["pinned_blueprints"]), 1)
        self.assertEqual(state["pinned_blueprints"][0]["source_build_id"], build["id"])


if __name__ == "__main__":
    unittest.main()
