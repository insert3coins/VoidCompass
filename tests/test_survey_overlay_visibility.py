import types
import unittest

from voidcompass.overlays.html_survey_overlay import HtmlSurveyOverlayBridge


class _Master:
    pass


class _Win:
    def __init__(self, state):
        self._state = state
        self.master = _Master()

    def state(self):
        return self._state

    def winfo_x(self):
        return 30

    def winfo_y(self):
        return 520


class _Canvas:
    def __init__(self, height=90):
        self.height = height

    def cget(self, key):
        return 420 if key == "width" else self.height

    def winfo_width(self):
        return 420

    def winfo_height(self):
        return self.height


def _bridge(window_state, model):
    bridge = HtmlSurveyOverlayBridge.__new__(HtmlSurveyOverlayBridge)
    bridge.win = _Win(window_state)
    bridge.canvas = _Canvas()
    bridge.config = {
        "survey_status_overlay_enabled": True,
        "survey_status_hud_x": 30,
        "survey_status_hud_y": 520,
    }
    bridge.overlay_id = "survey"
    bridge.enabled_key = "survey_status_overlay_enabled"
    bridge.x_key = "survey_status_hud_x"
    bridge.y_key = "survey_status_hud_y"
    bridge._browser_content_height = 0
    bridge.overlay = types.SimpleNamespace(_html_render_model=model)
    return bridge


class SurveyOverlayVisibilityTests(unittest.TestCase):
    def test_browser_measurement_replaces_taller_native_proxy(self):
        bridge = _bridge("normal", {
            "mode": "system",
            "rows": [{"name": "Body A", "bio_count": 1}],
        })
        bridge.canvas = _Canvas(height=180)
        bridge._browser_content_height = 126
        self.assertEqual(bridge._dimensions(), (420, 126))

    def test_mapped_window_without_model_publishes_hidden(self):
        bridge = _bridge("normal", None)
        self.assertFalse(bridge._window_payload()["visible"])

    def test_mapped_window_with_empty_model_publishes_hidden(self):
        bridge = _bridge("normal", {"mode": "system", "rows": []})
        self.assertFalse(bridge._window_payload()["visible"])

    def test_mapped_window_with_actionable_model_publishes_visible(self):
        bridge = _bridge("normal", {
            "mode": "system",
            "rows": [{"name": "Body A", "bio_count": 1}],
        })
        self.assertTrue(bridge._window_payload()["visible"])

    def test_focused_routine_scan_publishes_visible(self):
        bridge = _bridge("normal", {
            "mode": "body", "body": {"body_id": 5, "name": "Testia A 5"},
            "rows": [],
        })
        self.assertTrue(bridge._window_payload()["visible"])

    def test_withdrawn_window_with_actionable_model_stays_hidden(self):
        bridge = _bridge("withdrawn", {
            "mode": "system",
            "rows": [{"name": "Body A", "bio_count": 1}],
        })
        self.assertFalse(bridge._window_payload()["visible"])

    def test_disabled_overlay_never_publishes_visible(self):
        bridge = _bridge("normal", {
            "mode": "system",
            "rows": [{"name": "Body A", "bio_count": 1}],
        })
        bridge.config["survey_status_overlay_enabled"] = False
        self.assertFalse(bridge._window_payload()["visible"])


if __name__ == "__main__":
    unittest.main()
