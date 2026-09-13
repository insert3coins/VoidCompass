import unittest
import ctypes
import sys
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
    WS_EX_TRANSPARENT,
    _WindowController,
    _apply_webview_transparency,
    _apply_windows_overlay_chrome,
    _overlay_window_style as overlay_ex_style,
    _patch_pywebview_overlay_focus,
    _OverlayHost,
)


class OverlayInputStyleTests(unittest.TestCase):
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
        original = 0x00000080  # WS_EX_TOOLWINDOW, retained by the helper.
        updated = overlay_ex_style(original, True)

        self.assertEqual(updated & original, original)
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

    def test_non_activating_webview_is_not_focused_when_shown(self):
        class FakeBrowserForm:
            def on_shown(self, *_):
                self.original_handler_called = True

        winforms = SimpleNamespace(
            BrowserView=SimpleNamespace(BrowserForm=FakeBrowserForm),
        )
        self.assertTrue(_patch_pywebview_overlay_focus(winforms))

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
