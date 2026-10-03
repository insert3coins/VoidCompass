"""5.5.1.6: Overlay Studio's OPACITY fades each overlay window with Windows'
layered-window alpha, applied by the overlay host. The pages used to fade
themselves, and that page-level fade did not reach the screen for a Radeon
RX 9070 XT user although full transparency did; the desktop compositor's
window alpha does not depend on the browser's GPU compositing."""

from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from voidcompass.overlays import html_overlay_host
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class ServerTests(unittest.TestCase):
    def setUp(self):
        # Class-wide state: other tests' settings saves may have set it.
        HtmlOverlayServer.set_opacity(1.0)
        self.server = HtmlOverlayServer(WEB, presentation_held=False)
        self.server.register("survey", "survey", "Void Compass Survey Operations")
        self.server.publish("survey", {"window": {"x": 1, "y": 2, "width": 420, "height": 150, "visible": True}})

    def tearDown(self):
        HtmlOverlayServer.set_opacity(1.0)
        self.server.stop()

    def test_every_window_carries_the_opacity_and_the_host_is_told(self):
        self.assertEqual(self.server.window_manifest()["survey"]["window"]["opacity"], 1.0)
        revision = self.server._window_revision
        self.assertTrue(HtmlOverlayServer.set_opacity(0.4))
        self.assertGreater(self.server._window_revision, revision)
        self.assertEqual(self.server.window_manifest()["survey"]["window"]["opacity"], 0.4)
        self.assertFalse(HtmlOverlayServer.set_opacity(0.4), "no change, no churn")
        HtmlOverlayServer.set_opacity(0.1)
        self.assertEqual(HtmlOverlayServer.opacity, 0.4, "never below the studio minimum")


class HostTests(unittest.TestCase):
    def controller(self):
        controller = html_overlay_host._WindowController.__new__(html_overlay_host._WindowController)
        controller.last_alpha = None
        return controller

    def test_alpha_bytes(self):
        self.assertEqual(html_overlay_host._opacity_alpha(1.0), 255)
        self.assertEqual(html_overlay_host._opacity_alpha(0.4), 102)
        self.assertEqual(html_overlay_host._opacity_alpha("bad"), 255)

    def test_the_host_applies_it_only_when_it_changes(self):
        source = (ROOT / "src/voidcompass/overlays/html_overlay_host.py").read_text(encoding="utf-8")
        # A window never faded keeps Windows' default: no call at all at 100%.
        self.assertIn("if alpha != self.last_alpha and not (alpha == 255 and self.last_alpha is None):", source)
        self.assertIn("SetLayeredWindowAttributes", source)
        self.assertNotIn("windll.user32.SetLayeredWindowAttributes", source, "private user32 handle only")


class KeyedBackgroundTests(unittest.TestCase):
    """5.5.1.9: with a fade applied, Windows composites the overlay form's own
    background wherever the page is transparent (cut corners, gaps between
    notifications): grey blocks once the window had been resized. The form's
    background is a key colour Windows makes see-through, with the fade."""

    def test_the_fade_keys_out_the_form_background(self):
        host = html_overlay_host
        self.assertEqual(host.OVERLAY_KEY_COLORREF,
                         host.OVERLAY_KEY_RGB[0] | host.OVERLAY_KEY_RGB[1] << 8 | host.OVERLAY_KEY_RGB[2] << 16)
        calls = []
        fake_user32 = Mock()
        fake_user32.SetLayeredWindowAttributes = Mock(side_effect=lambda *args: calls.append(args) or 1)
        with patch.object(host, "_native_handle", return_value=1234),                 patch.object(host.ctypes, "WinDLL", return_value=fake_user32),                 patch.object(host, "_apply_overlay_key_background", return_value=True) as paint:
            self.assertTrue(host._apply_window_alpha(object(), 166))
        paint.assert_called_once()
        _hwnd, key, alpha, flags = calls[0]
        self.assertEqual((key, alpha, flags), (host.OVERLAY_KEY_COLORREF, 166, host.LWA_ALPHA | host.LWA_COLORKEY))


class PageTests(unittest.TestCase):
    def test_pages_no_longer_fade_themselves(self):
        client = (WEB / "assets" / "overlay-client.js").read_text(encoding="utf-8")
        hud = (WEB / "navigation_hud" / "app.js").read_text(encoding="utf-8")
        for name, source in (("overlay-client", client), ("navigation hud", hud)):
            with self.subTest(page=name):
                self.assertNotIn("body.style.opacity =", source)


class StudioTests(unittest.TestCase):
    def test_the_slider_reaches_the_windows_while_dragging(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio.config = {"overlay_opacity_percent": 100}
        for name in ("_persist_config", "update_hud", "_schedule_html_dashboard_publish"):
            setattr(studio, name, Mock())
        try:
            self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "set_opacity", "value": 55}))
            self.assertEqual(HtmlOverlayServer.opacity, 0.55)
        finally:
            HtmlOverlayServer.set_opacity(1.0)


if __name__ == "__main__":
    unittest.main()
