import time
import unittest

from heartbeat_hud import HeartbeatHUD, _AI_MAX_GROWTH, _MAX_GROWTH


class HeartbeatHUDTests(unittest.TestCase):
    def _hud(self):
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud._pulse_level = 0
        hud._pulse_kind = "journal"
        hud._special_until = 0.0
        hud._last_pulse_ts = time.time()
        hud._last_render_key = None
        hud._redraw = lambda: None
        return hud

    def test_ai_pulse_is_larger_and_survives_immediate_journal_activity(self):
        hud = self._hud()

        hud.pulse("ai")
        self.assertEqual(hud._pulse_kind, "ai")
        self.assertEqual(hud._pulse_level, _AI_MAX_GROWTH)

        hud.pulse()
        self.assertEqual(hud._pulse_kind, "ai")
        self.assertEqual(hud._pulse_level, _AI_MAX_GROWTH)

    def test_normal_pulse_returns_after_ai_hold_expires(self):
        hud = self._hud()
        hud.pulse("ai")
        hud._special_until = time.monotonic() - 1

        hud.pulse()

        self.assertEqual(hud._pulse_kind, "journal")
        self.assertEqual(hud._pulse_level, _MAX_GROWTH)


if __name__ == "__main__":
    unittest.main()
