"""5.5.2.7: a hidden overlay is revealed only once its page has drawn the
latest model, and the host wakes a hidden page directly to fetch it.

A hidden WebView2 throttles the page's polling timer (down to about once a
minute), and the host used to reveal a window as soon as its page had drawn
anything. Survey Operations then appeared showing what it drew while hidden:
a system's first scanned planet was missing until the next scan."""

import unittest
from unittest import mock

from voidcompass.overlays import html_overlay_host as host


class _Window:
    def __init__(self):
        self.calls = []

    def run_js(self, script):
        self.calls.append(script)


class RevealTests(unittest.TestCase):
    def setUp(self):
        self.shown = []
        self.native_visible = False

        def set_visibility(_window, visible):
            self.native_visible = bool(visible)
            self.shown.append(bool(visible))
            return True
        patches = {
            "_native_handle": lambda _w: 1, "_apply_windows_geometry": lambda *_a: True,
            "_windows_visibility": lambda _w: self.native_visible, "_set_windows_visibility": set_visibility,
            "_apply_windows_style": lambda *_a: None, "_apply_webview_transparency": lambda *_a: None,
            "_apply_window_alpha": lambda *_a: True, "monitor_scale": lambda *_a: 1.0,
            "_foreground_window": lambda: 0,
        }
        for name, value in patches.items():
            patcher = mock.patch.object(host, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.window = _Window()
        self.controller = host._WindowController("survey", self.window)
        self.payload = {"x": 10, "y": 10, "width": 420, "height": 200, "visible": True}

    def test_waits_for_the_page_to_draw_the_latest_model(self):
        self.controller.apply(self.payload, render_current=False)
        self.assertFalse(self.native_visible, "not revealed showing stale content")
        self.assertTrue(self.window.calls, "the hidden page was woken to fetch its data")
        self.controller.apply(self.payload, render_current=True)
        self.assertTrue(self.native_visible, "revealed once the page is current")

    def test_reveals_anyway_after_two_seconds(self):
        with mock.patch.object(host.time, "monotonic", return_value=100.0):
            self.controller.apply(self.payload, render_current=False)
        self.assertFalse(self.native_visible)
        with mock.patch.object(host.time, "monotonic", return_value=102.5):
            self.controller.apply(self.payload, render_current=False)
        self.assertTrue(self.native_visible, "a page that never confirms still appears")

    def test_a_visible_overlay_is_never_hidden_for_new_data(self):
        self.controller.apply(self.payload, render_current=True)
        self.assertTrue(self.native_visible)
        self.controller.apply(self.payload, render_current=False)
        self.assertTrue(self.native_visible, "no flicker while it catches up")
        self.assertEqual(self.shown, [True])

    def test_wake_calls_are_rate_limited(self):
        hidden = {**self.payload, "visible": False}
        with mock.patch.object(host.time, "monotonic", return_value=50.0):
            for _ in range(5):
                self.controller.apply(hidden, render_current=False)
        self.assertEqual(len(self.window.calls), 1)


class ManifestTests(unittest.TestCase):
    def test_manifest_says_whether_the_page_is_current(self):
        from pathlib import Path
        from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

        server = HtmlOverlayServer(Path(__file__).resolve().parents[1] / "web")
        server.register("survey", template="survey", title="Survey")
        state = server._overlays["survey"]
        state.ready.set()
        state.revision, state.rendered_revision = 4, 3
        self.assertFalse(server.window_manifest()["survey"]["render_current"])
        state.rendered_revision = 4
        self.assertTrue(server.window_manifest()["survey"]["render_current"])
        self.assertIn("__voidcompassPoll", (Path(__file__).resolve().parents[1] / "web" / "assets" / "overlay-client.js").read_text(encoding="utf-8"))
        self.assertIn("__voidcompassPoll", (Path(__file__).resolve().parents[1] / "web" / "navigation_hud" / "app.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
