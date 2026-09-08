import unittest

from html_overlay_host import (
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TRANSPARENT,
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


if __name__ == "__main__":
    unittest.main()
