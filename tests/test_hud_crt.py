import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import overlay_chrome  # noqa: E402
from hud import TacticalHUD  # noqa: E402


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def _record(self, kind, *args, **kwargs):
        self.calls.append((kind, args, kwargs))
        return len(self.calls)

    def create_line(self, *args, **kwargs):
        return self._record("line", *args, **kwargs)

    def create_rectangle(self, *args, **kwargs):
        return self._record("rectangle", *args, **kwargs)

    def create_text(self, *args, **kwargs):
        return self._record("text", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._record("delete", *args, **kwargs)


class HudCrtTests(unittest.TestCase):
    def test_chrome_scanlines_can_be_disabled(self):
        canvas = FakeCanvas()
        overlay_chrome.draw_chrome(
            canvas, 120, 60, scanlines=False, scanline_color="#123456"
        )
        self.assertFalse(any(
            kind == "line" and kwargs.get("fill") == "#123456"
            for kind, _args, kwargs in canvas.calls
        ))

        canvas = FakeCanvas()
        overlay_chrome.draw_chrome(
            canvas, 120, 60, scanlines=True, scanline_step=4,
            scanline_color="#123456",
        )
        scanlines = [call for call in canvas.calls if call[0] == "line" and call[2].get("fill") == "#123456"]
        self.assertEqual(len(scanlines), 15)

    def test_text_glow_tracks_crt_toggle_and_intensity(self):
        hud = TacticalHUD.__new__(TacticalHUD)
        hud.canvas = FakeCanvas()
        hud.config = {"hud_crt_enabled": True, "hud_crt_intensity": "Subtle"}
        hud.draw_text(10, 10, "TEST", "#00ffff", ("Courier", 8))
        self.assertEqual(sum(1 for call in hud.canvas.calls if call[0] == "text"), 4)

        hud.canvas = FakeCanvas()
        hud.config["hud_crt_enabled"] = False
        hud.draw_text(10, 10, "TEST", "#00ffff", ("Courier", 8))
        self.assertEqual(sum(1 for call in hud.canvas.calls if call[0] == "text"), 2)

    def test_motion_updates_only_tagged_crt_elements(self):
        hud = TacticalHUD.__new__(TacticalHUD)
        hud.canvas = FakeCanvas()
        hud.config = {
            "hud_crt_enabled": True,
            "hud_crt_motion_enabled": True,
            "hud_crt_intensity": "Standard",
        }
        hud.width = 560
        hud.base_height = 246
        hud._crt_phase = 0
        hud.anim_step = 0
        hud._draw_crt_animation()
        lines = [call for call in hud.canvas.calls if call[0] == "line"]
        self.assertTrue(lines)
        self.assertTrue(all(call[2].get("tags") == "crt_motion" for call in lines))
        self.assertEqual(hud._crt_phase, 5)

        hud.canvas = FakeCanvas()
        hud.config["hud_crt_motion_enabled"] = False
        hud._draw_crt_animation()
        self.assertFalse(any(call[0] == "line" for call in hud.canvas.calls))


if __name__ == "__main__":
    unittest.main()
