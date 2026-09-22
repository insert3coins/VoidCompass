import tempfile
import unittest
from pathlib import Path

from voidcompass.mining.rhino_minimap import (
    CoverageMap,
    RhinoMinimapTracker,
    drive_radii,
    location_index,
)
from voidcompass.mining.planet_materials import PlanetMaterialsStore
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.core.global_hotkeys import (
    DEFAULT_OVERLAY_HOTKEYS,
    OVERLAY_HOTKEY_SPECS,
)
from voidcompass.overlays.overlay_layout_model import OVERLAY_ENABLE_KEYS


class RhinoMinimapCoverageTests(unittest.TestCase):
    def test_location_parser_and_drive_rings_match_elite_semantics(self):
        self.assertEqual(location_index({"Name": "$SAA_Unknown_Signal:#index=22;"}), 22)
        self.assertIsNone(location_index({"Name": "Sol A 1"}))
        self.assertEqual(drive_radii(), [3750, 5500])
        self.assertEqual(drive_radii(10_000), [3750, 5500, 7250, 9000])

    def test_coverage_stamps_recenter_and_border_clip(self):
        cover = CoverageMap("Test 1 a", 0, 0, 1_000_000)
        self.assertTrue(cover.add(0, 0))
        self.assertGreater(cover.painted_km2, 11)
        count = len(cover.stamps)
        self.assertTrue(cover.add(0, 0.001))
        self.assertEqual(len(cover.stamps), count)
        cover.recenter(0, 0)
        self.assertTrue(cover.set_border(0, 0.03))
        self.assertGreater(cover.border_m, 500)
        before = cover.painted_km2
        self.assertTrue(cover.add(0, 0.08))
        self.assertEqual(cover.painted_km2, before)

    def test_profile_persistence_resume_and_bookmarks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rhino_minimap.json.gz"
            tracker = RhinoMinimapTracker(path)
            self.assertFalse(tracker.update(
                body="Sol Moon", system="Sol", latitude=0, longitude=0,
                radius_m=1_000_000, heading=90, in_srv=True, vehicle="Scarab",
            ))
            self.assertTrue(tracker.update(
                body="Sol Moon", system="Sol", latitude=0, longitude=0,
                radius_m=1_000_000, heading=90, in_srv=True, vehicle="Rhino",
                destination={"Name": "$SAA_Unknown_Signal:#index=4;"},
            ))
            self.assertTrue(tracker.center_here())
            self.assertTrue(tracker.update(
                body="Sol Moon", system="Sol", latitude=0, longitude=0.03,
                radius_m=1_000_000, heading=90, in_srv=True, vehicle="Rhino",
            ))
            self.assertTrue(tracker.border_here())
            snapshot = tracker.snapshot([{
                "system": "Sol", "body": "Sol Moon", "name": "Ruby ridge",
                "latitude": 0, "longitude": 0.01, "materials": "Ruby",
                "depleted": 1,
            }, {
                "system": "Sol", "body": "Sol Moon", "name": "Drill 7",
                "latitude": 0, "longitude": 0.02, "materials": "",
                "site_type": "drill", "map_name": "map 1",
            }, {
                "system": "Sol", "body": "Sol Moon", "name": "Other map drill",
                "latitude": 0, "longitude": 0.025, "materials": "",
                "site_type": "drill", "map_name": "map 2",
            }], center_hotkey="Ctrl+Alt+Z", border_hotkey="Ctrl+Alt+B",
                drill_hotkey="Ctrl+Alt+D", reset_hotkey="Ctrl+Alt+Shift+R")
            self.assertEqual(snapshot["header"], "loc 4  Moon")
            self.assertTrue(snapshot["centered"])
            self.assertTrue(snapshot["bookmarks"][0]["depleted"])
            self.assertEqual(snapshot["bookmarks"][0]["code"], "RU")
            self.assertEqual(snapshot["bookmarks"][1]["code"], "D7")
            self.assertEqual(snapshot["bookmarks"][1]["kind"], "drill")
            self.assertEqual(len(snapshot["bookmarks"]), 2)
            self.assertEqual(snapshot["drill_count"], 1)
            self.assertEqual(snapshot["hotkeys"]["drill"], "Ctrl+Alt+D")
            self.assertEqual(snapshot["hotkeys"]["reset"], "Ctrl+Alt+Shift+R")
            self.assertTrue(path.exists())
            picture = tracker.export_picture([{
                "system": "Sol", "body": "Sol Moon", "name": "Ruby ridge",
                "latitude": 0, "longitude": 0.01, "materials": "Ruby",
                "depleted": 1,
            }])
            self.assertTrue(picture.is_file())
            self.assertEqual(tracker.usage()[0], 1)
            catalogue = tracker.map_catalogue([{
                "system": "Sol", "body": "Sol Moon", "name": "Ruby ridge",
                "latitude": 0, "longitude": 0.01, "materials": "Ruby",
                "location_index": 4,
            }], {"Sol Moon": 20}, "Sol")
            self.assertEqual(catalogue[0]["mapped_count"], 1)
            self.assertEqual(catalogue[0]["location_total"], 20)
            self.assertEqual(catalogue[0]["maps"][0]["bookmarks"], 1)

            restored = RhinoMinimapTracker(path)
            self.assertTrue(restored.update(
                body="Sol Moon", system="Sol", latitude=0, longitude=0.03,
                radius_m=1_000_000, heading=45, in_srv=True, vehicle="RHINO",
            ))
            self.assertEqual(restored.active.name, tracker.active.name)
            self.assertTrue(restored.active.centered)
            self.assertIsNotNone(restored.active.border_m)

    def test_reset_replaces_only_the_active_map_at_the_rhino_position(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rhino_minimap.json.gz"
            tracker = RhinoMinimapTracker(path)
            self.assertTrue(tracker.update(
                body="Sol Moon", system="Sol", latitude=0, longitude=0,
                radius_m=1_000_000, heading=90, in_srv=True, vehicle="Rhino",
                destination={"Name": "$SAA_Unknown_Signal:#index=4;"},
            ))
            original = tracker.active
            original_name = original.name
            tracker.center_here()
            tracker.update(
                body="Sol Moon", system="Sol", latitude=0, longitude=0.03,
                radius_m=1_000_000, heading=90, in_srv=True, vehicle="Rhino",
            )
            tracker.border_here()
            picture = tracker.export_picture()
            self.assertTrue(picture.is_file())

            self.assertTrue(tracker.reset_active())
            self.assertIsNot(tracker.active, original)
            self.assertEqual(tracker.active.name, original_name)
            self.assertEqual(tracker.active.location, 4)
            self.assertEqual(tracker.active.origin, (0.0, 0.03))
            self.assertFalse(tracker.active.centered)
            self.assertIsNone(tracker.active.border_m)
            self.assertEqual(len(tracker.active.stamps), 1)
            self.assertFalse(picture.exists())
            self.assertEqual(tracker.usage()[0], 1)

            tracker.update(in_srv=False)
            self.assertFalse(tracker.reset_active())

    def test_disabled_rhino_map_hotkeys_are_not_exposed_to_settings(self):
        actions = {action: key for action, key, _label, _attr in OVERLAY_HOTKEY_SPECS}
        self.assertFalse(any(action.startswith("rhino_minimap") for action in actions))
        self.assertFalse(any("rhino_minimap" in key for key in DEFAULT_OVERLAY_HOTKEYS))

    def test_mark_drill_persists_numbered_current_position(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = RhinoMinimapTracker(Path(folder) / "rhino_minimap.json.gz")
            self.assertTrue(tracker.update(
                body="Sol Moon", system="Sol", latitude=1.25, longitude=-4.5,
                radius_m=1_000_000, heading=90, in_srv=True, vehicle="Rhino",
            ))
            store = PlanetMaterialsStore(Path(folder) / "planet_materials.db")
            dashboard = MainDashboard.__new__(MainDashboard)
            dashboard.config = {}
            dashboard.rhino_minimap = tracker
            dashboard._planet_materials_store = lambda: store
            dashboard._refresh_planet_materials_overlay = lambda: True
            dashboard._refresh_rhino_minimap_overlay = lambda: True
            dashboard._schedule_html_dashboard_publish = lambda **_kwargs: None
            dashboard.add_event_feed_entry = lambda *_args, **_kwargs: None

            self.assertTrue(dashboard._mark_rhino_drill())
            tracker.here = (1.5, -4.0)
            self.assertTrue(dashboard._mark_rhino_drill())
            rows = store.rows()
            self.assertEqual([row["name"] for row in rows], ["Drill 1", "Drill 2"])
            self.assertTrue(all(row["site_type"] == "drill" for row in rows))
            self.assertTrue(all(row["map_name"] == "map 1" for row in rows))
            self.assertEqual((rows[1]["latitude"], rows[1]["longitude"]), (1.5, -4.0))
            snapshot = tracker.snapshot(rows)
            self.assertEqual(snapshot["drill_count"], 2)
            self.assertIn("Drill 2 marked", snapshot["notice"])

            store.save(dict(
                system="Sol", body="Sol Moon", name="Other map drill",
                site_type="drill", map_name="map 2", materials="",
                latitude=2, longitude=-3,
            ))
            self.assertTrue(dashboard._reset_rhino_minimap())
            remaining = store.rows()
            self.assertEqual([row["name"] for row in remaining], ["Other map drill"])
            self.assertEqual(tracker.snapshot(remaining)["drill_count"], 0)

    def test_overlay_is_first_class_managed_surface(self):
        self.assertEqual(
            OVERLAY_ENABLE_KEYS["rhino_minimap_hud"],
            "rhino_minimap_overlay_enabled",
        )


if __name__ == "__main__":
    unittest.main()
