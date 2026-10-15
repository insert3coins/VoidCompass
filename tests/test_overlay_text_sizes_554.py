"""Every overlay's own text size (5.5.4): one list in Overlay Studio, like the
Watcher's, for whichever overlay is selected; 0 follows all overlays."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import Mock

from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import (
    OVERLAY_SPECS, TEXT_SIZE_KEYS, TEXT_SIZES, overlay_text_percent, overlay_text_scale, text_size_choice,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "dashboard"


class RuleTests(unittest.TestCase):
    def test_every_overlay_has_its_own_size_per_commander(self):
        self.assertEqual(set(TEXT_SIZE_KEYS), {spec.attr for spec in OVERLAY_SPECS})
        for key in TEXT_SIZE_KEYS.values():
            with self.subTest(key=key):
                self.assertIn(key, config_module.PROFILE_SETTINGS)
        self.assertEqual(len(set(TEXT_SIZE_KEYS.values())), len(TEXT_SIZE_KEYS))

    def test_its_own_or_all_overlays(self):
        every = {"overlay_text_scale_percent": 125}
        self.assertEqual(overlay_text_percent(every, "cargo_hud"), 125, "0: all overlays")
        self.assertEqual(overlay_text_percent({**every, "cargo_text_scale_percent": 175}, "cargo_hud"), 175)
        self.assertEqual(overlay_text_scale({**every, "station_text_scale_percent": 85}, "station_info_hud"), .85)
        self.assertEqual(overlay_text_percent({}, "toast_hud"), 100)
        self.assertEqual(overlay_text_percent({"overlay_text_scale_percent": 999}, "toast_hud"), 200)

    def test_only_the_sizes_on_the_list(self):
        self.assertEqual(TEXT_SIZES, (0, 75, 85, 100, 110, 125, 150, 175, 200))
        self.assertEqual([text_size_choice(value) for value in (0, -5, 10, 95, 140, 999, "x")], [0, 0, 75, 100, 150, 200, 0])


class HostTests(unittest.TestCase):
    def test_shared_overlays_find_their_own(self):
        from voidcompass.overlays.html_model_overlay import HtmlModelOverlayBridge
        bridge = HtmlModelOverlayBridge.__new__(HtmlModelOverlayBridge)
        bridge.config = {"overlay_text_scale_percent": 100, "powerplay_text_scale_percent": 150}
        bridge.enabled_key = "powerplay_overlay_enabled"
        self.assertEqual(bridge._text_scale(), 1.5)
        bridge.enabled_key = "carrier_overlay_enabled"
        self.assertEqual(bridge._text_scale(), 1.0)

    def test_notifications_and_achievements_apart(self):
        from voidcompass.overlays.toast_hud import AchievementHUD, ToastHUD
        self.assertEqual((ToastHUD.STUDIO_ID, AchievementHUD.STUDIO_ID), ("toast_hud", "achievement_hud"))
        config = {"toast_text_scale_percent": 75, "achievement_text_scale_percent": 200}
        self.assertEqual(overlay_text_percent(config, ToastHUD.STUDIO_ID), 75)
        self.assertEqual(overlay_text_percent(config, AchievementHUD.STUDIO_ID), 200)

    def test_the_older_six_keep_their_settings(self):
        from voidcompass.overlays.galnet_ticker_hud import ticker_text_scale
        from voidcompass.overlays.heartbeat_hud import heartbeat_text_scale
        from voidcompass.overlays.hud import hud_text_scale_percent
        from voidcompass.overlays.survey_options import survey_text_scale
        self.assertEqual(hud_text_scale_percent({"hud_text_scale_percent": 110}), 110)
        self.assertEqual(survey_text_scale({"survey_text_scale_percent": 175}), 1.75)
        self.assertEqual(ticker_text_scale({"galnet_ticker_text_scale_percent": 85}), .85)
        self.assertEqual(heartbeat_text_scale({"heartbeat_text_scale_percent": 0, "overlay_text_scale_percent": 150}), 1.5)


class StudioTests(unittest.TestCase):
    def studio(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
        studio = HtmlOverlayStudioMixin()
        studio.config = {}
        studio._html_overlay_settings_save = Mock()
        return studio

    def test_one_list_for_the_selected_overlay(self):
        studio = self.studio()
        self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "own_text", "overlay_id": "cargo_hud", "value": 150}))
        self.assertEqual(studio.config["cargo_text_scale_percent"], 150)
        studio._html_overlay_settings_save.assert_called_once()
        self.assertTrue(studio._set_overlay_own_text("cargo_hud", 0))
        self.assertEqual(studio.config["cargo_text_scale_percent"], 0, "back to all overlays")
        self.assertFalse(studio._set_overlay_own_text("cargo_hud", 140), "only the list's sizes")
        self.assertFalse(studio._set_overlay_own_text("nonsense", 100))
        self.assertFalse(studio._set_overlay_own_text("heartbeat_hud", 100), "the Watcher's is on its page")

    def test_the_inspector(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="studio-selected-text"', html)
        for gone in ("studio-hud-text-scale", "studio-survey-text-scale", "studio-minimap-text-scale",
                     "studio-music-text-scale", "studio-ticker-text-scale"):
            self.assertNotIn(gone, html, "one list, not a number box per overlay")
        app = (WEB / "app.js").read_bytes().decode("utf-8")
        self.assertIn('operation: "own_text"', app)
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn('"own_text": text_size_choice(', source)


if __name__ == "__main__":
    unittest.main()
