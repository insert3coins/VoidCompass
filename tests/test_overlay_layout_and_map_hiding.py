"""5.5.1.5 (CMDR Nyx Evera's ideas): hide the overlays on the Galaxy Map,
System Map and Orrery (each overlay can opt out in Overlay Studio), and an
Overlay Studio layout mode that shows every enabled overlay with its outline
so empty ones can be placed."""

import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from urllib.request import ProxyHandler, build_opener

from voidcompass.core import config as config_module
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class OverrideTests(unittest.TestCase):
    def setUp(self):
        self.server = HtmlOverlayServer(WEB, presentation_held=False)
        self.server.register("survey", "survey", "Void Compass Survey Operations")
        self.server.publish("survey", {"window": {"x": 10, "y": 10, "width": 420, "height": 150, "visible": False}})
        self.server.register("nav", "navigation", "Void Compass Navigation HUD")
        self.server.publish("nav", {"window": {"x": 10, "y": 300, "width": 500, "height": 326, "visible": True}})

    def tearDown(self):
        HtmlOverlayServer.set_overrides(hidden=(), layout=False)
        self.server.stop()

    def visible(self):
        return {key: row["window"]["visible"] for key, row in self.server.window_manifest().items()}

    def test_layout_mode_shows_every_overlay_and_maps_hide_the_chosen_ones(self):
        self.assertEqual(self.visible(), {"survey": False, "nav": True})
        revision = self.server._window_revision
        self.assertTrue(HtmlOverlayServer.set_overrides(layout=True))
        self.assertGreater(self.server._window_revision, revision, "the host is told at once")
        self.assertEqual(self.visible(), {"survey": True, "nav": True})
        HtmlOverlayServer.set_overrides(layout=False, hidden={"survey", "nav"})
        self.assertEqual(self.visible(), {"survey": False, "nav": False})
        # An overlay left out of the set stays as it was.
        HtmlOverlayServer.set_overrides(hidden={"survey"})
        self.assertEqual(self.visible(), {"survey": False, "nav": True})
        HtmlOverlayServer.set_overrides(hidden={"survey", "nav"})
        # Layout mode wins over a map left open.
        HtmlOverlayServer.set_overrides(layout=True)
        self.assertEqual(self.visible(), {"survey": True, "nav": True})
        HtmlOverlayServer.set_overrides(layout=False, hidden=())
        self.assertEqual(self.visible(), {"survey": False, "nav": True})
        self.assertFalse(HtmlOverlayServer.set_overrides(hidden=[]), "no change, no churn")

    def test_health_carries_layout_mode_and_the_overlay_title(self):
        HtmlOverlayServer.set_overrides(layout=True)
        opener = build_opener(ProxyHandler({}))
        health = json.loads(opener.open(
            f"http://127.0.0.1:{self.server.port}/api/health?token={self.server.token}&overlay=survey", timeout=5).read())
        self.assertTrue(health["layout"])
        self.assertEqual(health["title"], "Void Compass Survey Operations")


class MapHidingTests(unittest.TestCase):
    def tearDown(self):
        HtmlOverlayServer.set_overrides(hidden=(), layout=False)

    def studio(self, focus, enabled=True, keep=None):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio.config = {"overlay_hide_on_maps": enabled}
        if keep is not None:
            studio.config["overlay_map_keep_visible"] = keep
        studio.current_gui_focus = focus
        studio._persist_config = Mock()
        studio._schedule_html_dashboard_publish = Mock()
        return studio

    def test_galaxy_map_system_map_and_orrery_hide_the_overlays(self):
        from voidcompass.core.overlay_registry import OVERLAY_SPECS

        every = {spec.overlay_id for spec in OVERLAY_SPECS}
        for focus, hidden in ((6, every), (7, every), (8, every), (0, set()), (9, set()), (-1, set())):
            with self.subTest(focus=focus):
                self.studio(focus)._apply_map_overlay_hiding()
                self.assertEqual(HtmlOverlayServer.overlays_hidden, hidden)

    def test_the_setting_turns_it_off(self):
        self.studio(6, enabled=False)._apply_map_overlay_hiding()
        self.assertEqual(HtmlOverlayServer.overlays_hidden, frozenset())

    def test_an_overlay_can_stay_on_the_maps(self):
        studio = self.studio(6)
        self.assertTrue(studio._handle_html_overlay_studio_command(
            {"operation": "map_hiding", "overlay_id": "survey_status_hud", "hide": False}))
        self.assertEqual(studio.config["overlay_map_keep_visible"], ["survey_status_hud"])
        studio._persist_config.assert_called()
        # Studio ids map to the server's overlay ids.
        self.assertNotIn("survey", HtmlOverlayServer.overlays_hidden)
        self.assertIn("navigation", HtmlOverlayServer.overlays_hidden)
        studio._handle_html_overlay_studio_command(
            {"operation": "map_hiding", "overlay_id": "survey_status_hud", "hide": True})
        self.assertEqual(studio.config["overlay_map_keep_visible"], [])
        self.assertIn("survey", HtmlOverlayServer.overlays_hidden)
        self.assertFalse(studio._handle_html_overlay_studio_command(
            {"operation": "map_hiding", "overlay_id": "not-an-overlay", "hide": False}))

    def test_a_bad_saved_choice_hides_everything(self):
        self.studio(7, keep="survey_status_hud")._apply_map_overlay_hiding()
        self.assertIn("survey", HtmlOverlayServer.overlays_hidden)

    def test_the_choice_is_per_profile_and_none_kept_by_default(self):
        self.assertIn("overlay_map_keep_visible", config_module.PROFILE_VALUE_SETTINGS)
        source = (ROOT / "src" / "voidcompass" / "core" / "config.py").read_text(encoding="utf-8")
        self.assertIn('"overlay_map_keep_visible": []', source)
        self.assertIn("'overlay_map_keep_visible': []", source)

    def test_the_setting_is_per_profile_and_on_by_default(self):
        self.assertIn("overlay_hide_on_maps", config_module.PROFILE_BOOL_SETTINGS)
        source = (ROOT / "src" / "voidcompass" / "core" / "config.py").read_text(encoding="utf-8")
        self.assertIn('"overlay_hide_on_maps": True', source)

    def test_layout_mode_ends_when_leaving_overlay_studio(self):
        studio = self.studio(0)
        studio._schedule_html_dashboard_publish = Mock()
        studio._set_overlay_layout_mode(True)
        self.assertTrue(HtmlOverlayServer.layout_mode)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('if page != "overlay-studio":\n                self._set_overlay_layout_mode(False)', dashboard)


class HeaderSwitchboardTests(unittest.TestCase):
    """5.5.1.6: the command deck header's ALL switch is the all-overlays
    hotkey's curtain, and its state is published for the header to show."""

    def test_hide_all_runs_the_curtain_and_is_published(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio._handle_overlay_hotkey = Mock(side_effect=lambda action: setattr(studio, "_overlay_hotkey_global_hidden", True))
        self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "hide_all"}))
        studio._handle_overlay_hotkey.assert_called_once_with("toggle_all")
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn('"all_hidden": bool(getattr(self, "_overlay_hotkey_global_hidden", False))', source)


class PageWiringTests(unittest.TestCase):
    def test_every_overlay_page_loads_the_layout_outline_without_inline_styles(self):
        script = (WEB / "assets" / "overlay-layout.js").read_text(encoding="utf-8")
        # Overlay pages allow stylesheets from their own server only.
        self.assertNotIn('createElement("style")', script)
        self.assertIn("/assets/overlay-layout.css", script)
        self.assertTrue((WEB / "assets" / "overlay-layout.css").is_file())
        for index in WEB.glob("*/index.html"):
            if index.parent.name in {"dashboard", "galactic_map"}:
                continue
            with self.subTest(page=index.parent.name):
                self.assertIn("/assets/overlay-layout.js", index.read_text(encoding="utf-8"))

    def test_studio_offers_both_switches(self):
        index = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="studio-layout-mode"', index)
        self.assertIn('data-overlay-option="overlay_hide_on_maps"', index)
        self.assertIn('id="studio-selected-maphide"', index)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('operation: "map_hiding"', app)


if __name__ == "__main__":
    unittest.main()
