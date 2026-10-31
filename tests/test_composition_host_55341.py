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
        server = HtmlOverlayServer(WEB)
        server.register("cargo", "cargo")
        page_url = html_overlay_host._OverlayHost(server.url, None).page_url("cargo", "cargo")
        try:
            window = runtime.create_window("VC Test", page_url,
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
            server.stop()
        self.assertEqual(runtime.windows, {}, "every window destroyed")
        self.assertFalse(os.path.isdir(folder), "the private WebView2 data removed")

    def test_concurrent_controller_initialisation_keeps_every_window_usable(self):
        try:
            import webview.platforms.edgechromium
        except Exception as exc:
            self.skipTest(f"WebView2 unavailable: {exc}")
        runtime = composition_host.CompositionRuntime()
        if not runtime.start():
            self.skipTest(f"visual hosting unavailable: {runtime.error}")
        server = HtmlOverlayServer(WEB)
        from voidcompass.overlays.cargo_hud import build_cargo_model
        from tests.test_overlay_text_fit_5539 import THEME
        host = html_overlay_host._OverlayHost(server.url, None)
        for index in range(8):
            overlay_id = f"batch-{index}"
            server.register(overlay_id, "cargo")
            server.publish(overlay_id, {"cargo": build_cargo_model([], capacity=64), "theme": THEME})
        try:
            windows = runtime.call(lambda: [runtime.create_window(
                f"VC batch {index}", host.page_url(f"batch-{index}", "cargo"),
                180 + index * 20, 100 + index * 10,
                html_overlay_host.HIDDEN_WINDOW_X, html_overlay_host.HIDDEN_WINDOW_Y,
            ) for index in range(8)])
            deadline = time.monotonic() + 25
            while not all(window._voidcompass_navigation_completed_at for window in windows) and time.monotonic() < deadline:
                time.sleep(.05)
            ready_deadline = time.monotonic() + 10
            while not all(server._overlays[f"batch-{i}"].ready.is_set() for i in range(8)) and time.monotonic() < ready_deadline:
                time.sleep(.05)
            for i in range(8):
                self.assertTrue(server._overlays[f"batch-{i}"].ready.is_set(), "the actual overlay script reported ready")
            for window in windows:
                self.assertIsNotNone(window.controller)
                self.assertTrue(window._voidcompass_navigation_completed_at)
                self.assertFalse(window._voidcompass_navigation_failed)
            controllers = [html_overlay_host._WindowController(str(i), window) for i, window in enumerate(windows)]
            host.controllers = {controller.overlay_id: controller for controller in controllers}
            def apply(visible):
                return runtime.call(lambda: [controller.apply({
                    "x": html_overlay_host.HIDDEN_WINDOW_X, "y": html_overlay_host.HIDDEN_WINDOW_Y,
                    "width": 180+i*20, "height": 100+i*10, "visible": visible,
                    "click_through": True, "opacity": .8,
                }) for i, controller in enumerate(controllers)])
            for visible in (True, False, True, False):
                results = apply(visible)
                self.assertTrue(all(item["ok"] for item in results))
                # 5.7.1: shown under their cloaks; the host's group step puts
                # them on the screen together once they have drawn.
                settle_deadline = time.monotonic() + 3
                while time.monotonic() < settle_deadline:
                    runtime.call(host._settle)
                    if all(controller.last_visible is visible for controller in controllers):
                        break
                    time.sleep(.02)
                self.assertTrue(all(controller.last_visible is visible for controller in controllers))
                for window in windows:
                    self.assertEqual(html_overlay_host._windows_visibility(window), visible)
        finally:
            runtime.stop()
            server.stop()


if __name__ == "__main__":
    unittest.main()
