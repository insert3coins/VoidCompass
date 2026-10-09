"""5.5.3.3: each overlay can have its own opacity (Overlay Studio inspector),
and the heartbeat orb's window is round, so its corners never show, even on
a PC whose graphics lose WebView2's transparency (a commander saw a black
square round the orb)."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from voidcompass.core import config as config_module
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays import html_overlay_host
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]


class OwnOpacityTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(HtmlOverlayServer.set_overlay_opacities, {})
        self.addCleanup(HtmlOverlayServer.set_opacity, 1.0)

    def test_manifest_gives_an_overlay_its_own_opacity(self):
        server = HtmlOverlayServer(ROOT / "web", presentation_held=False)
        self.addCleanup(server.stop)
        server.register("heartbeat", "heartbeat", "Heartbeat")
        server.register("cargo", "cargo", "Cargo")
        HtmlOverlayServer.set_opacity(0.8)
        self.assertTrue(HtmlOverlayServer.set_overlay_opacities({"heartbeat": 0.5}))
        manifest = server.window_manifest()
        self.assertEqual(manifest["heartbeat"]["window"]["opacity"], 0.5)
        self.assertEqual(manifest["cargo"]["window"]["opacity"], 0.8, "the rest follow OPACITY")
        self.assertFalse(HtmlOverlayServer.set_overlay_opacities({"heartbeat": 0.5}), "no change, no churn")

    def test_studio_sets_and_clears_it(self):
        saved = []
        studio = SimpleNamespace(config={}, _persist_config=lambda: saved.append(True),
                                 _schedule_html_dashboard_publish=lambda **_: None)
        for name in ("_own_opacities", "_apply_own_opacities", "_set_overlay_own_opacity"):
            setattr(studio, name, getattr(HtmlOverlayStudioMixin, name).__get__(studio))
        studio._OWN_OPACITY_CHOICES = HtmlOverlayStudioMixin._OWN_OPACITY_CHOICES
        self.assertTrue(studio._set_overlay_own_opacity("heartbeat_hud", 60))
        self.assertEqual(studio.config["overlay_opacity_by_overlay"], {"heartbeat_hud": 60})
        self.assertEqual(HtmlOverlayServer.opacity_by_overlay, {"heartbeat": 0.6})
        self.assertFalse(studio._set_overlay_own_opacity("heartbeat_hud", 35), "only the offered choices")
        self.assertFalse(studio._set_overlay_own_opacity("no_such_overlay", 60))
        self.assertTrue(studio._set_overlay_own_opacity("heartbeat_hud", 0))
        self.assertEqual(studio.config["overlay_opacity_by_overlay"], {})
        self.assertEqual(HtmlOverlayServer.opacity_by_overlay, {})
        self.assertIn("overlay_opacity_by_overlay", config_module.PROFILE_VALUE_SETTINGS)

    def test_the_inspector_offers_it(self):
        html = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="studio-selected-opacity"', html)
        app = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('operation: "own_opacity"', app)


class RoundOrbTests(unittest.TestCase):
    def test_the_orb_asks_for_a_round_window_unless_a_thought_shows(self):
        from voidcompass.overlays.html_heartbeat_overlay import HtmlHeartbeatBridge
        bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
        with patch("voidcompass.overlays.html_model_overlay.HtmlModelOverlayBridge._window_payload",
                   return_value={"x": 10, "y": 10, "width": 54, "height": 54}), \
                patch.object(HtmlHeartbeatBridge, "_thought", return_value=None):
            self.assertEqual(bridge._window_payload()["shape"], "circle")
        with patch("voidcompass.overlays.html_model_overlay.HtmlModelOverlayBridge._window_payload",
                   return_value={"x": 10, "y": 10, "width": 384, "height": 54}), \
                patch.object(HtmlHeartbeatBridge, "_thought", return_value={"side": "right"}):
            self.assertEqual(bridge._window_payload()["shape"], "rect")

    def test_the_host_clips_a_round_window(self):
        self.assertTrue(callable(html_overlay_host._apply_window_shape))
        source = Path(html_overlay_host.__file__).read_text(encoding="utf-8")
        self.assertIn("CreateEllipticRgn", source)
        self.assertIn('payload.get("shape") == "circle"', source)
        self.assertFalse(html_overlay_host._apply_window_shape(SimpleNamespace(native=None), "circle"),
                         "no window yet: nothing to clip")


if __name__ == "__main__":
    unittest.main()
