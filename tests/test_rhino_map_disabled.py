"""The Rhino coverage map is switched off app-wide until it is removed.

One switch, RHINO_MAP_AVAILABLE, turns off the minimap overlay, its
coverage maps in Planet Materials, map export, its Overlay Studio controls,
its hotkey actions and the Status tracking that painted the map. Saved maps
stay on disk; nothing reads, paints or exports them. Rhino SRV mining (its
hold and cargo) is a different feature and is unaffected.
"""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from voidcompass.core import overlay_registry
from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR, RHINO_MAP_AVAILABLE
from voidcompass.dashboard.dashboard import MainDashboard

ROOT = Path(__file__).resolve().parents[1]


def dashboard():
    app = MainDashboard.__new__(MainDashboard)
    app.config = {"rhino_minimap_overlay_enabled": True}
    app.is_running = True
    app.rhino_minimap = SimpleNamespace(
        update=Mock(), in_rhino=True, export_picture_for=Mock(), usage=Mock(return_value=(3, 1024)),
        map_catalogue=Mock(return_value=[{"body": "A 1"}]),
    )
    for name in ("_set_rhino_minimap_center", "_set_rhino_minimap_border", "_mark_rhino_drill",
                 "_reset_rhino_minimap", "_open_rhino_minimap_folder"):
        setattr(app, name, Mock(return_value=True))
    return app


class RhinoMapDisabledTests(unittest.TestCase):
    def test_one_switch_turns_the_map_off(self):
        self.assertFalse(RHINO_MAP_AVAILABLE)
        self.assertFalse(OVERLAY_SPEC_BY_ATTR["rhino_minimap_hud"].available)
        self.assertNotIn("rhino_minimap_hud", overlay_registry.HTML_OVERLAY_SPECS)
        app = dashboard()
        self.assertFalse(app._overlay_enabled("rhino_minimap_hud"), "an old profile cannot switch it back on")

    def test_status_updates_no_longer_paint_the_map(self):
        app = dashboard()
        self.assertFalse(app._observe_rhino_minimap_status({"Latitude": 1.0, "Longitude": 2.0}))
        app.rhino_minimap.update.assert_not_called()

    def test_studio_and_hotkeys_cannot_drive_it(self):
        app = dashboard()
        for operation in ("rhino_center", "rhino_border", "rhino_drill", "rhino_reset", "rhino_open_maps"):
            self.assertFalse(app._handle_html_overlay_studio_command({"operation": operation, "confirmed": True}), operation)
        for action in ("rhino_minimap_center", "rhino_minimap_border", "rhino_minimap_drill", "rhino_minimap_reset"):
            app._handle_overlay_hotkey(action)
        for name in ("_set_rhino_minimap_center", "_set_rhino_minimap_border", "_mark_rhino_drill",
                     "_reset_rhino_minimap", "_open_rhino_minimap_folder"):
            getattr(app, name).assert_not_called()

    def test_planet_materials_offers_no_coverage_maps(self):
        source = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('...(coverageEnabled ? [["maps","COVERAGE MAPS"]] : [])', source)
        python = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('"coverage_maps_enabled": RHINO_MAP_AVAILABLE', python)
        self.assertIn("if tracker is not None and include_coverage_maps and RHINO_MAP_AVAILABLE else []", python)
        self.assertIn("if tracker is None or not RHINO_MAP_AVAILABLE:", python.split('elif operation == "export_map":')[1][:200])


if __name__ == "__main__":
    unittest.main()
