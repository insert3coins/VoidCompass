import unittest
import ctypes
from http.client import HTTPConnection
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import Mock, patch

from voidcompass.overlays.html_overlay_host import (
    DWMWA_BORDER_COLOR,
    DWMWA_WINDOW_CORNER_PREFERENCE,
    DWMWA_COLOR_NONE,
    DWMWCP_DONOTROUND,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TRANSPARENT,
    HIDDEN_WINDOW_X,
    HIDDEN_WINDOW_Y,
    _WindowController,
    _apply_webview_transparency,
    _apply_windows_overlay_chrome,
    _overlay_window_style as overlay_ex_style,
    _patch_pywebview_overlay_focus,
    _OverlayHost,
)
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer


class OverlayInputStyleTests(unittest.TestCase):
    def test_ready_handshake_does_not_corrupt_next_keepalive_request(self):
        server = HtmlOverlayServer(Path(__file__).resolve().parents[1] / "web")
        server.register("heartbeat", "heartbeat", "Heartbeat")
        connection = HTTPConnection("127.0.0.1", server.port, timeout=2)
        suffix = f"?token={server.token}&overlay=heartbeat"
        try:
            connection.request("POST", "/api/ready" + suffix, body="{}")
            response = connection.getresponse()
            self.assertEqual(response.status, 202)
            response.read()
            connection.request("GET", "/api/health" + suffix)
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
        finally:
            connection.close()
            server.stop()

    def test_failed_page_reload_does_not_reset_healthy_overlays(self):
        static_root = Path(__file__).resolve().parents[1] / "web"
        server = HtmlOverlayServer(static_root)
        try:
            failed = server.register("prospector", "prospector", "Prospector")
            healthy = server.register("station", "station", "Station")
            for state in (failed, healthy):
                state.ready.set()
                state.rendered_revision = 3

            self.assertEqual(server.request_reload("prospector"), 1)

            manifest = server.window_manifest()
            self.assertFalse(manifest["prospector"]["content_ready"])
            self.assertEqual(manifest["prospector"]["reload_revision"], 1)
            self.assertTrue(manifest["station"]["content_ready"])
            self.assertEqual(manifest["station"]["reload_revision"], 0)
        finally:
            server.stop()

    def test_host_reloads_only_the_requested_browser_window(self):
        window = SimpleNamespace(load_url=Mock())
        controller = SimpleNamespace(
            reload_revision=0,
            hide=Mock(),
            window=window,
            apply=Mock(return_value={
                "ok": True, "visible": False, "curtained": False,
                "_restore_all_transparency": False,
            }),
            last_visible=False,
        )
        host = _OverlayHost.__new__(_OverlayHost)
        host.origin = "http://127.0.0.1:1234"
        host.token = "test-token"
        host.controllers = {"prospector": controller}
        host.closing = False
        host.last_contact = 0.0
        host.presentation_held = False

        def one_manifest():
            host.closing = True
            return {"prospector": {
                "template": "prospector",
                "reload_revision": 1,
                "content_ready": False,
                "window": {"visible": True},
            }}

        host.manifest = one_manifest
        with patch("voidcompass.overlays.html_overlay_host._request_json"):
            host.control_loop()

        controller.hide.assert_called_once_with()
        window.load_url.assert_called_once_with(
            "http://127.0.0.1:1234/prospector/index.html"
            "?token=test-token&overlay=prospector&reload=1",
        )
        self.assertEqual(controller.reload_revision, 1)
        controller.apply.assert_called_once_with(
            {"visible": True},
            presentation_held=False,
            content_ready=False,
        )

    def test_planet_materials_template_resolves_to_bundled_page(self):
        host = _OverlayHost.__new__(_OverlayHost)
        host.origin = "http://127.0.0.1:1234"
        host.token = "test-token"

        url = host.page_url("planet-materials", "planet-materials-overlay")

        self.assertEqual(
            url,
            "http://127.0.0.1:1234/planet-materials-overlay/index.html"
            "?token=test-token&overlay=planet-materials",
        )

    def test_rhino_minimap_template_resolves_to_bundled_page(self):
        host = _OverlayHost.__new__(_OverlayHost)
        host.origin = "http://127.0.0.1:1234"
        host.token = "test-token"

        url = host.page_url("rhino-minimap", "rhino-minimap-overlay")

        self.assertEqual(
            url,
            "http://127.0.0.1:1234/rhino-minimap/index.html"
            "?token=test-token&overlay=rhino-minimap",
        )

    def test_passthrough_adds_required_windows_styles(self):
        original = 0
        updated = overlay_ex_style(original, True)

        self.assertTrue(updated & WS_EX_TOOLWINDOW)
        self.assertTrue(updated & WS_EX_LAYERED)
        self.assertTrue(updated & WS_EX_TRANSPARENT)
        self.assertTrue(updated & WS_EX_NOACTIVATE)

    def test_interaction_mode_removes_only_input_blocking_styles(self):
        retained = 0x00000080 | WS_EX_LAYERED
        original = retained | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        updated = overlay_ex_style(original, False)

        self.assertEqual(updated, retained | WS_EX_NOACTIVATE)

    def test_windows_chrome_disables_system_border_and_rounded_corners(self):
        calls = []

        class FakeSetter:
            argtypes = None
            restype = None

            def __call__(self, hwnd, attribute, value, size):
                value_type = (
                    ctypes.c_int
                    if attribute == DWMWA_WINDOW_CORNER_PREFERENCE
                    else ctypes.c_uint32
                )
                calls.append((
                    attribute,
                    ctypes.cast(value, ctypes.POINTER(value_type)).contents.value,
                    size,
                ))
                return 0

        window = SimpleNamespace(
            native=SimpleNamespace(
                Handle=SimpleNamespace(ToInt64=lambda: 4242),
            ),
        )
        fake_dwm = SimpleNamespace(DwmSetWindowAttribute=FakeSetter())
        with patch(
            "voidcompass.overlays.html_overlay_host.ctypes.WinDLL",
            return_value=fake_dwm,
        ):
            self.assertTrue(_apply_windows_overlay_chrome(window))

        self.assertEqual(calls, [
            (DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_DONOTROUND, 4),
            (DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE, 4),
        ])

    def test_transparency_repairs_webview_control_and_controller(self):
        transparent = object()

        class FakeColor:
            @staticmethod
            def FromArgb(*_):
                return transparent

        system = ModuleType("System")
        system.Func = object
        system.Type = object
        drawing = ModuleType("System.Drawing")
        drawing.Color = FakeColor
        controller = SimpleNamespace(DefaultBackgroundColor=None)
        control = SimpleNamespace(
            IsDisposed=False,
            DefaultBackgroundColor=None,
            CoreWebView2Controller=controller,
            Invalidate=Mock(),
        )
        native = SimpleNamespace(
            IsDisposed=False,
            InvokeRequired=False,
            webview=control,
            browser=SimpleNamespace(webview=object()),
            Invalidate=Mock(),
        )
        with patch.dict(sys.modules, {
            "System": system,
            "System.Drawing": drawing,
        }):
            self.assertTrue(_apply_webview_transparency(SimpleNamespace(native=native)))

        self.assertIs(control.DefaultBackgroundColor, transparent)
        self.assertIs(controller.DefaultBackgroundColor, transparent)
        control.Invalidate.assert_called_once_with()
        native.Invalidate.assert_called_once_with(True)

    def test_first_visible_frame_restores_previous_foreground_window(self):
        controller = _WindowController("ground", object(), restore_foreground=4242)
        with patch("voidcompass.overlays.html_overlay_host._native_handle", return_value=99), \
             patch("voidcompass.overlays.html_overlay_host._apply_windows_geometry", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._apply_windows_style", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._apply_webview_transparency"), \
             patch("voidcompass.overlays.html_overlay_host._set_windows_visibility", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._foreground_window", return_value=777), \
             patch("voidcompass.overlays.html_overlay_host._restore_foreground_window") as restore:
            result = controller.apply({
                "x": 100, "y": 100, "width": 370, "height": 154,
                "visible": True, "click_through": True,
            })

        self.assertTrue(result["visible"])
        restore.assert_called_once_with(4242)
        self.assertEqual(controller.restore_foreground, 0)

    def test_surface_stays_hidden_until_browser_content_is_ready(self):
        controller = _WindowController("station", object())
        with patch("voidcompass.overlays.html_overlay_host._native_handle", return_value=99), \
             patch("voidcompass.overlays.html_overlay_host._apply_windows_geometry", return_value=True) as geometry, \
             patch("voidcompass.overlays.html_overlay_host._apply_windows_style", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._apply_webview_transparency"), \
             patch("voidcompass.overlays.html_overlay_host._windows_visibility", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._set_windows_visibility", return_value=True) as set_visible:
            result = controller.apply({
                "x": 100, "y": 100, "width": 520, "height": 442,
                "visible": True, "click_through": True,
            }, content_ready=False)

            geometry.assert_called_with(controller.window, HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y, 520, 442)
            self.assertFalse(result["visible"])
            set_visible.assert_called_once_with(controller.window, False)
            ready = controller.apply({
                "x": 100, "y": 100, "width": 520, "height": 442,
                "visible": True, "click_through": True,
            }, content_ready=True)
            geometry.assert_called_with(controller.window, 100, 100, 520, 442)
            self.assertTrue(ready["visible"])

    def test_reload_quarantines_window_before_navigation_can_remap_it(self):
        controller = _WindowController("station", object())
        controller.last_geometry = (100, 200, 520, 442)
        with patch("voidcompass.overlays.html_overlay_host._set_windows_visibility", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._apply_windows_geometry", return_value=True) as geometry:
            controller.hide()
        geometry.assert_called_once_with(controller.window, HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y, 520, 442)
        self.assertEqual(controller.last_geometry, (HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y, 520, 442))
        self.assertFalse(controller.last_visible)

    def test_non_activating_webview_is_not_focused_when_shown(self):
        class FakeBrowserForm:
            def __init__(self, window):
                self.pywebview_window = window
                self.ShowInTaskbar = True

            def on_shown(self, *_):
                self.original_handler_called = True

        winforms = SimpleNamespace(
            BrowserView=SimpleNamespace(BrowserForm=FakeBrowserForm),
        )
        with patch(
            "voidcompass.overlays.html_overlay_host._apply_windows_style",
            return_value=True,
        ) as apply_style:
            self.assertTrue(_patch_pywebview_overlay_focus(winforms))
            form = FakeBrowserForm(SimpleNamespace(focus=False))

        # Changing this managed property after WebView2 is attached recreates
        # the HWND, so the pre-show patch must use native styles exclusively.
        self.assertTrue(form.ShowInTaskbar)
        apply_style.assert_called_once_with(
            form.pywebview_window, click_through=True,
        )

        shown = Mock()
        overlay = SimpleNamespace(
            pywebview_window=SimpleNamespace(focus=False),
            shown=SimpleNamespace(set=shown),
        )
        FakeBrowserForm.on_shown(overlay)

        shown.assert_called_once_with()
        self.assertFalse(hasattr(overlay, "original_handler_called"))

        focused = SimpleNamespace(
            pywebview_window=SimpleNamespace(focus=True),
            shown=SimpleNamespace(set=Mock()),
        )
        FakeBrowserForm.on_shown(focused)
        self.assertTrue(focused.original_handler_called)


if __name__ == "__main__":
    unittest.main()
