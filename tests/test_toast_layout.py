"""Scaled notification geometry stays aligned with the HTML card heights."""

from types import SimpleNamespace
import unittest

from voidcompass.overlays.toast_hud import ToastHUD


class ToastLayoutTests(unittest.TestCase):
    def test_notice_and_achievement_heights_follow_text_scale(self):
        hud = ToastHUD.__new__(ToastHUD)
        hud.config = {"overlay_text_scale_percent": 100}
        for scale, notice, achievement in (
            (75, 70, 98), (100, 80, 112),
            (150, 100, 140), (200, 120, 168),
        ):
            with self.subTest(scale=scale):
                hud.config["overlay_text_scale_percent"] = scale
                self.assertEqual(hud.toast_height({"kind": "notice"}), notice)
                self.assertEqual(hud.toast_height({"kind": "achievement"}), achievement)

    def test_stack_height_uses_scaled_rows_and_gap(self):
        hud = ToastHUD.__new__(ToastHUD)
        hud.config = {"overlay_text_scale_percent": 150}
        hud._toasts = [{"kind": "notice"}, {"kind": "achievement"}]
        hud.win = SimpleNamespace(height=0)
        hud._redraw()
        self.assertEqual(hud.win.height, 100 + hud.GAP + 140)


if __name__ == "__main__":
    unittest.main()
