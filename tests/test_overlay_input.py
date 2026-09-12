import unittest
from unittest.mock import patch

from html_overlay_host import (
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TRANSPARENT,
    _WindowController,
    _overlay_window_style as overlay_ex_style,
)


class OverlayInputStyleTests(unittest.TestCase):
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

    def test_first_visible_frame_restores_previous_foreground_window(self):
        controller = _WindowController("ground", object(), restore_foreground=4242)
        with patch("html_overlay_host._native_handle", return_value=99), \
             patch("html_overlay_host._apply_windows_geometry", return_value=True), \
             patch("html_overlay_host._apply_windows_style", return_value=True), \
             patch("html_overlay_host._apply_webview_transparency"), \
             patch("html_overlay_host._set_windows_visibility", return_value=True), \
             patch("html_overlay_host._foreground_window", return_value=777), \
             patch("html_overlay_host._restore_foreground_window") as restore:
            result = controller.apply({
                "x": 100, "y": 100, "width": 370, "height": 154,
                "visible": True, "click_through": True,
            })

        self.assertTrue(result["visible"])
        restore.assert_called_once_with(4242)
        self.assertEqual(controller.restore_foreground, 0)


if __name__ == "__main__":
    unittest.main()
