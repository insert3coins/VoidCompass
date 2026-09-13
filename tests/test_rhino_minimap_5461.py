import tempfile
import unittest
from pathlib import Path

from voidcompass.mining.rhino_minimap import (
    CoverageMap,
    RhinoMinimapTracker,
    drive_radii,
    location_index,
)
from voidcompass.overlays.overlay_layout_model import OVERLAY_ENABLE_KEYS


class RhinoMinimapCoverageTests(unittest.TestCase):
    def test_location_parser_and_drive_rings_match_elite_semantics(self):
        self.assertEqual(location_index({"Name": "$SAA_Unknown_Signal:#index=22;"}), 22)
        self.assertIsNone(location_index({"Name": "Sol A 1"}))
        self.assertEqual(drive_radii(10_000), [8000, 4250, 500])

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
            }], center_hotkey="Ctrl+Alt+Z", border_hotkey="Ctrl+Alt+B")
            self.assertEqual(snapshot["header"], "loc 4  Moon")
            self.assertTrue(snapshot["centered"])
            self.assertTrue(snapshot["bookmarks"][0]["depleted"])
            self.assertEqual(snapshot["bookmarks"][0]["code"], "RU")
            self.assertTrue(path.exists())
            picture = tracker.export_picture([{
                "system": "Sol", "body": "Sol Moon", "name": "Ruby ridge",
                "latitude": 0, "longitude": 0.01, "materials": "Ruby",
                "depleted": 1,
            }])
            self.assertTrue(picture.is_file())
            self.assertEqual(tracker.usage()[0], 1)

            restored = RhinoMinimapTracker(path)
            self.assertTrue(restored.update(
                body="Sol Moon", system="Sol", latitude=0, longitude=0.03,
                radius_m=1_000_000, heading=45, in_srv=True, vehicle="RHINO",
            ))
            self.assertEqual(restored.active.name, tracker.active.name)
            self.assertTrue(restored.active.centered)
            self.assertIsNotNone(restored.active.border_m)

    def test_overlay_is_first_class_managed_surface(self):
        self.assertEqual(
            OVERLAY_ENABLE_KEYS["rhino_minimap_hud"],
            "rhino_minimap_overlay_enabled",
        )


if __name__ == "__main__":
    unittest.main()
