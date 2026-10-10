"""5.5.3.4.1: overlays in WebView2's visual hosting. Windowed hosting paints an
opaque base behind every transparent page whenever Windows is in dark mode
(the dark boxes round CMDR Nyx Evera's overlays; WebView2Feedback #5752, on
runtimes 153 to 155). Visual hosting draws into our own composition visual
and never paints it. The classic windows stay as a fallback: chosen in
Overlay Studio, or used when visual hosting can't start."""

import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from voidcompass.core import config as config_module
from voidcompass.overlays import composition_host, html_overlay_host
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class HostChoiceTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(HtmlOverlayServer.set_classic_windows, False)

    def test_the_server_tells_the_host_which_windows(self):
        server = HtmlOverlayServer(WEB, presentation_held=False)
        self.addCleanup(server.stop)
        server.register("toast", "toast", "Notifications")
        host = html_overlay_host._OverlayHost(server.url, None)
        host.manifest()
        self.assertEqual(host.hosting, "composition", "visual hosting by default")
        self.assertTrue(HtmlOverlayServer.set_classic_windows(True))
        host.manifest()
        self.assertEqual(host.hosting, "classic")

    def test_classic_or_unavailable_falls_back_to_pywebview(self):
        manifest = {"toast": {"template": "toast", "window": {}}}

        def fake_manifest(host):
            host.hosting = "classic"
            return manifest
        with patch.object(html_overlay_host._OverlayHost, "manifest", fake_manifest), \
                patch.object(composition_host, "available", return_value=True), \
                patch.object(composition_host, "CompositionRuntime") as runtime:
            self.assertIsNone(html_overlay_host._run_composition("http://127.0.0.1:1/?token=t"))
            runtime.assert_not_called()
        with patch.object(composition_host, "available", return_value=False):
            self.assertIsNone(html_overlay_host._run_composition("http://127.0.0.1:1/?token=t"))

    def test_a_new_overlay_never_hands_focus_back_on_its_first_reveal(self):
        """5.5.3.4.1: each overlay restored whatever had focus when it was made
        (the command deck, at startup) on its first reveal: mid-game, the deck
        jumped in front of Elite or its taskbar button flashed. These windows
        never take focus, so there is nothing to give back."""
        host = html_overlay_host._OverlayHost("http://127.0.0.1:1/?token=t", None)
        host.runtime = type("Runtime", (), {"create_window": lambda self, *args: object()})()
        with patch.object(html_overlay_host, "_foreground_window", return_value=4242):
            host.create_window("toast", {"template": "toast", "window": {"width": 100, "height": 50}})
        self.assertEqual(host.controllers["toast"].restore_foreground, 0)

    def test_the_classic_switch_is_registered(self):
        self.assertIn("overlay_classic_windows", config_module.PROFILE_BOOL_SETTINGS)
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-overlay-option="overlay_classic_windows"', html)
        studio = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn("HtmlOverlayServer.set_classic_windows", studio)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("HtmlOverlayServer.set_classic_windows", dashboard)


@unittest.skipUnless(os.name == "nt" and composition_host.available(), "Windows with DirectComposition")
class RealWindowTests(unittest.TestCase):
    def test_a_window_hosts_a_page_and_closes_cleanly(self):
        try:
            import webview.platforms.edgechromium  # noqa: F401
        except Exception as exc:
            self.skipTest(f"WebView2 unavailable: {exc}")
        runtime = composition_host.CompositionRuntime()
        if not runtime.start():
            self.skipTest(f"visual hosting unavailable: {runtime.error}")
        folder = runtime.user_data_folder
        try:
            window = runtime.create_window("VC Test", "data:text/html,<body style='background:transparent'>ok</body>",
                                           120, 60, html_overlay_host.HIDDEN_WINDOW_X, html_overlay_host.HIDDEN_WINDOW_Y)
            self.assertTrue(window._voidcompass_composition and window._voidcompass_owned)
            self.assertTrue(window.native.Handle, "a real window handle for the host's positioning code")
            deadline = time.monotonic() + 20
            while (window.controller is None or not window._voidcompass_navigation_completed_at) \
                    and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertIsNotNone(window.controller, "WebView2 attached to our composition visual")
            self.assertFalse(window._voidcompass_navigation_failed)
            self.assertTrue(html_overlay_host._apply_window_alpha(window, 200), "the OPACITY fade, alpha only")
            window.run_js("1 + 1")
        finally:
            runtime.stop()
        self.assertEqual(runtime.windows, {}, "every window destroyed")
        self.assertFalse(os.path.isdir(folder), "the private WebView2 data removed")


if __name__ == "__main__":
    unittest.main()
