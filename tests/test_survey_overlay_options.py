"""Survey Operations presentation options: profile settings to overlay page."""

import types
import unittest

from voidcompass.core.config import PROFILE_TEXT_SETTINGS, PROFILE_VALUE_SETTINGS
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays.survey_options import survey_overlay_options, survey_text_scale
from tests.test_survey_overlay_visibility import _bridge


class _Studio(HtmlOverlayStudioMixin):
    """Just enough of the dashboard for the Studio save handler."""

    def __init__(self, config):
        self.config = config
        self.persisted = 0

    def _persist_config(self):
        self.persisted += 1

    def update_hud(self):
        pass

    def _schedule_html_dashboard_publish(self, immediate=False):
        pass


class SurveyOverlayOptionTests(unittest.TestCase):
    def test_options_are_profile_settings(self):
        self.assertIn("survey_spotlight_rotation", PROFILE_TEXT_SETTINGS)
        self.assertIn("survey_spotlight_threshold", PROFILE_VALUE_SETTINGS)
        self.assertIn("survey_text_scale_percent", PROFILE_VALUE_SETTINGS)

    def test_rotation_defaults_to_auto_above_eight_and_is_bounded(self):
        self.assertEqual(survey_overlay_options({}),
                         {"spotlight_rotation": "auto", "spotlight_threshold": 8})
        self.assertEqual(survey_overlay_options({"survey_spotlight_rotation": " OFF "}),
                         {"spotlight_rotation": "off", "spotlight_threshold": 8})
        self.assertEqual(survey_overlay_options({"survey_spotlight_rotation": "sometimes",
                                                 "survey_spotlight_threshold": "99"}),
                         {"spotlight_rotation": "auto", "spotlight_threshold": 40})
        self.assertEqual(survey_overlay_options({"survey_spotlight_threshold": 1})["spotlight_threshold"], 2)

    def test_survey_text_size_overrides_only_when_set(self):
        self.assertEqual(survey_text_scale({"overlay_text_scale_percent": 150}), 1.5)
        self.assertEqual(survey_text_scale({"overlay_text_scale_percent": 150,
                                            "survey_text_scale_percent": 0}), 1.5)
        self.assertEqual(survey_text_scale({"overlay_text_scale_percent": 150,
                                            "survey_text_scale_percent": 110}), 1.1)
        self.assertEqual(survey_text_scale({"survey_text_scale_percent": 500}), 2.0)

    def test_bridge_publishes_options_and_survey_text_size(self):
        bridge = _bridge("normal", {"mode": "system", "rows": [{"name": "Body A", "bio_count": 1}]})
        bridge.config.update({"survey_spotlight_rotation": "always", "survey_spotlight_threshold": 5,
                              "overlay_text_scale_percent": 100, "survey_text_scale_percent": 130})
        snapshot = bridge._snapshot()
        self.assertEqual(snapshot["options"], {"spotlight_rotation": "always", "spotlight_threshold": 5})
        self.assertEqual(snapshot["effects"]["text_scale"], 1.3)
        # Changing a choice must change the quick fingerprint, so it applies live.
        bridge.overlay._palette = {}
        bridge.overlay._last_render_key = "key"
        before = bridge._quick_fingerprint()
        bridge.config["survey_spotlight_rotation"] = "off"
        self.assertNotEqual(bridge._quick_fingerprint(), before)

    def test_studio_saves_bounded_choices_and_keeps_omitted_ones(self):
        studio = _Studio({"survey_spotlight_rotation": "off", "survey_spotlight_threshold": 12,
                          "survey_text_scale_percent": 120})
        base = {"overlay_text_scale_percent": 100, "overlay_opacity_percent": 100}
        # An older form that does not send the Survey fields keeps them.
        self.assertTrue(studio._html_overlay_settings_save(dict(base)))
        self.assertEqual((studio.config["survey_spotlight_rotation"],
                          studio.config["survey_spotlight_threshold"],
                          studio.config["survey_text_scale_percent"]), ("off", 12, 120))
        studio._html_overlay_settings_save({**base, "survey_spotlight_rotation": "ALWAYS",
                                            "survey_spotlight_threshold": "0",
                                            "survey_text_scale_percent": "0"})
        self.assertEqual((studio.config["survey_spotlight_rotation"],
                          studio.config["survey_spotlight_threshold"],
                          studio.config["survey_text_scale_percent"]), ("always", 2, 0))
        studio._html_overlay_settings_save({**base, "survey_spotlight_rotation": "wobble",
                                            "survey_spotlight_threshold": "8",
                                            "survey_text_scale_percent": "40"})
        self.assertEqual((studio.config["survey_spotlight_rotation"],
                          studio.config["survey_spotlight_threshold"],
                          studio.config["survey_text_scale_percent"]), ("auto", 8, 75))


if __name__ == "__main__":
    unittest.main()
