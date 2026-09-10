import unittest
from pathlib import Path

import engineering_companion as companion
from companion_features import fresh_state, update_ship_companion_state
from html_dashboard import HtmlDashboardMixin


class EngineeringCompanion543Tests(unittest.TestCase):
    def setUp(self):
        companion._load.cache_clear()
        companion._material_index.cache_clear()
        companion.blueprint_groups.cache_clear()
        companion.experimental_groups.cache_clear()

    def test_complete_reference_catalogues_are_available(self):
        model = companion.build_workspace({}, {})
        self.assertGreaterEqual(len(model["catalogue"]), 240)
        self.assertEqual(len(model["experimentals"]), 154)
        self.assertEqual(len(model["materials"]), 137)
        self.assertGreaterEqual(len(model["engineers"]), 34)
        self.assertTrue(model["tech_brokers"])

    def test_unused_engineering_language_packs_are_not_bundled(self):
        root = Path(__file__).resolve().parents[1]
        language_files = sorted(
            path.name for path in (root / "data" / "engineering_companion" / "i18n").glob("*.json")
        )
        self.assertEqual(language_files, [])

    def test_observed_ship_exposes_physical_slots_and_artwork(self):
        loadout = {
            "event": "Loadout", "ShipID": 7, "Ship": "Anaconda",
            "ShipName": "Wanderer", "MaxJumpRange": 62.5,
            "Modules": [{
                "Slot": "FrameShiftDrive", "Item": "Int_Hyperdrive_Size6_Class5",
                "Engineering": {"BlueprintName": "FSD_LongRange", "Level": 3},
            }],
        }
        model = companion.build_workspace({}, {"loadout": loadout})
        self.assertEqual(model["selected_ship_id"], "7")
        self.assertTrue(model["ship"]["observed"])
        self.assertTrue(model["ship"]["asset"].endswith("Anaconda.svg"))
        self.assertEqual(model["slots"][0]["slot"], "FrameShiftDrive")
        self.assertEqual(model["slots"][0]["engineeringGrade"], 3)

    def test_ship_bound_plan_uses_live_stock_and_exact_recipe(self):
        state = {
            "raw": {"arsenic": {"count": 12}}, "manufactured": {}, "encoded": {},
            "pinned_blueprints": [{
                "id": "plan", "name": "Increased FSD Range",
                "type": "Frame Shift Drive", "grade": 5, "current_grade": 0,
                "quantity": 1, "slot": "FrameShiftDrive", "ship_id": "7",
                "experimental": "Mass Manager",
            }],
        }
        model = companion.build_workspace(state, {})
        plan = model["pins"][0]
        self.assertGreater(len(plan["materials"]), 5)
        self.assertGreater(model["wishlist"]["required"], 0)
        arsenic = next(row for row in plan["materials"] if row["key"] == "arsenic")
        self.assertEqual(arsenic["have"], 12)

    def test_planned_build_uses_catalogue_slots_and_compatible_module_families(self):
        state = {"engineering_builds": [{
            "id": "plan:anaconda", "ship_symbol": "Anaconda",
            "name": "Long Range Survey", "slots": {},
        }]}
        model = companion.build_workspace(state, {}, selected_ship_id="plan:anaconda")
        self.assertEqual(len(model["ship_catalogue"]), 48)
        self.assertTrue(model["ship"]["planned"])
        self.assertGreater(len(model["slots"]), 30)
        fsd = next(row for row in model["slots"] if row["slot"] == "FrameShiftDrive")
        self.assertEqual(fsd["name"], "Frame Shift Drive")
        self.assertEqual(fsd["allowedTypes"], ["Frame Shift Drive"])
        hardpoint = next(row for row in model["slots"] if row["category"] == "Hardpoints")
        self.assertTrue(hardpoint["empty"])
        self.assertIn("Beam Laser", hardpoint["allowedTypes"])
        self.assertNotIn("Frame Shift Drive", hardpoint["allowedTypes"])

    def test_planned_slot_assignment_is_reflected_in_build_model(self):
        state = {"engineering_builds": [{
            "id": "plan:python", "ship_symbol": "Python", "name": "Miner",
            "slots": {"LargeHardpoint1": {"module_type": "Multi-cannon"}},
        }]}
        model = companion.build_workspace(state, {}, selected_ship_id="plan:python")
        slot = next(row for row in model["slots"] if row["slot"] == "LargeHardpoint1")
        self.assertEqual(slot["name"], "Multi-cannon")
        self.assertTrue(slot["assigned"])
        self.assertFalse(slot["empty"])

    def test_shipyard_swap_exposes_new_current_ship_before_loadout(self):
        state = fresh_state()
        state["loadout"] = {"ShipID": 7, "Ship": "SideWinder", "Modules": []}
        changed = update_ship_companion_state(state, "ShipyardSwap", {
            "ShipID": 42, "ShipType": "Anaconda", "ShipType_Localised": "Anaconda",
        })
        self.assertTrue(changed)
        self.assertTrue(state["loadout"]["Provisional"])
        model = companion.build_workspace({}, state)
        self.assertEqual(model["selected_ship_id"], "42")
        self.assertTrue(model["ship"]["current"])
        self.assertFalse(model["ship"]["observed"])

    def test_immediate_dashboard_publish_preempts_delayed_snapshot(self):
        class Root:
            def __init__(self):
                self.cancelled = []
                self.calls = []

            def cancel(self, job):
                self.cancelled.append(job)

            def call_later(self, delay, callback):
                self.calls.append((delay, callback))
                return 99

        class Host(HtmlDashboardMixin):
            is_running = True

        host = Host()
        host.root = Root()
        host._html_dashboard_publish_job = 17
        host._schedule_html_dashboard_publish(immediate=True)
        self.assertEqual(host.root.cancelled, [17])
        self.assertEqual(host.root.calls[0][0], 0)
        self.assertEqual(host._html_dashboard_publish_job, 99)

    def test_engineering_follow_current_overrides_previous_planned_selection(self):
        class Host(HtmlDashboardMixin):
            engineer_materials = {
                "engineering_follow_current": True,
                "engineering_selected_ship": "plan:old",
                "engineering_builds": [{
                    "id": "plan:old", "ship_symbol": "Python", "name": "Old plan",
                    "slots": {},
                }],
            }
            companion_state = {"loadout": {
                "ShipID": 77, "Ship": "Anaconda", "ShipName": "Live ship", "Modules": [],
            }}
            current_sys = "Sol"
            current_coords = (0, 0, 0)

            def _html_profile_transient(self, _name, default):
                return default

        model = Host()._html_engineering_workspace()
        self.assertTrue(model["follow_current"])
        self.assertEqual(model["selected_ship_id"], "77")
        self.assertEqual(model["ship"]["label"], "Live ship")

    def test_profile_companion_state_has_fleet_and_powerplay_storage(self):
        state = fresh_state()
        self.assertEqual(state["fleet_loadouts"], {})
        self.assertFalse(state["powerplay"]["pledged"])

    def test_powerplay_is_a_root_field_tools_workspace(self):
        root = Path(__file__).resolve().parents[1]
        index = (root / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        app = (root / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('data-page="powerplay"', index)
        self.assertIn('data-page-name="powerplay"', index)
        self.assertIn("function renderPowerplayWorkspace", app)
        self.assertNotIn("powerplay", companion.build_workspace({}, {}))

    def test_engineering_rail_omits_commander_logbook_and_settings(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        index = (root / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        engineering = app[app.index("function renderEngineeringWorkspace"):]
        engineering = engineering[:engineering.index("function renderPowerplayWorkspace")]
        self.assertNotIn('data-page="commander"', engineering)
        self.assertNotIn('data-page="chronicle"', engineering)
        self.assertNotIn('data-page="settings"', engineering)
        self.assertNotIn('data-page="mining"', engineering)
        engineering_page = index[index.index('data-page-name="engineering"'):]
        engineering_page = engineering_page[:engineering_page.index('data-page-name="powerplay"')]
        self.assertNotIn('>FIELD TOOLS</button>', engineering_page)

    def test_ship_engineering_uses_compact_module_groups_and_split_blueprint_browser(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        engineering = app[app.index("function renderEngineeringWorkspace"):]
        engineering = engineering[:engineering.index("function renderPowerplayWorkspace")]
        self.assertIn('class="engineering-module-tabs"', engineering)
        self.assertIn('data-engineering-category=', engineering)
        self.assertIn('class="engineering-slot-grid"', engineering)
        self.assertIn('class="engineering-blueprint-browser"', engineering)


if __name__ == "__main__":
    unittest.main()
