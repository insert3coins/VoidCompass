"""Regression checks for the shared Overlay Studio opacity control."""

import unittest

from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays.html_overlay_runtime import overlay_opacity_ratio


class _Studio(HtmlOverlayStudioMixin):
    def __init__(self, opacity=100):
        self.config = {
            "overlay_opacity_percent": opacity,
            "overlay_text_scale_percent": 125,
        }
        self.persist_count = 0
        self.hud_update_count = 0
        self.publish_count = 0

    def _persist_config(self):
        self.persist_count += 1

    def update_hud(self):
        self.hud_update_count += 1

    def _schedule_html_dashboard_publish(self, **kwargs):
        self.publish_count += 1

    def _html_overlay_desktop(self):
        return {
            "left": 0, "top": 0, "width": 1920, "height": 1080,
            "primary": {"left": 0, "top": 0, "width": 1920, "height": 1080},
        }

    def _html_overlay_records(self, **kwargs):
        return []

    def _ground_target_solution(self):
        return {}

    def _ground_target_configured(self):
        return False

    def _ground_target_should_show(self, solution):
        return False


class OverlayStudioOpacityTests(unittest.TestCase):
    def test_live_opacity_change_persists_and_refreshes_overlay_and_studio(self):
        studio = _Studio()

        self.assertTrue(studio._handle_html_overlay_studio_command({
            "operation": "set_opacity", "value": 65, "sequence": 1,
        }))

        self.assertEqual(studio.config["overlay_opacity_percent"], 65)
        self.assertEqual(studio.config["overlay_text_scale_percent"], 125)
        self.assertEqual(studio.persist_count, 1)
        self.assertEqual(studio.hud_update_count, 1)
        self.assertEqual(studio.publish_count, 1)
        self.assertEqual(studio._html_overlay_studio()["options"]["overlay_opacity_percent"], 65)
        self.assertEqual(overlay_opacity_ratio(studio.config), 0.65)

    def test_opacity_clamps_before_persisting(self):
        studio = _Studio()

        studio._handle_html_overlay_studio_command({
            "operation": "set_opacity", "value": 10, "sequence": 1,
        })
        self.assertEqual(studio.config["overlay_opacity_percent"], 40)
        studio._handle_html_overlay_studio_command({
            "operation": "set_opacity", "value": 150, "sequence": 2,
        })
        self.assertEqual(studio.config["overlay_opacity_percent"], 100)
        self.assertEqual(studio.persist_count, 2)

    def test_stale_live_slider_command_does_not_undo_newer_setting(self):
        studio = _Studio()

        studio._handle_html_overlay_studio_command({
            "operation": "set_opacity", "value": 65, "sequence": 2,
        })
        studio._handle_html_overlay_studio_command({
            "operation": "set_opacity", "value": 80, "sequence": 1,
        })

        self.assertEqual(studio.config["overlay_opacity_percent"], 65)
        self.assertEqual(studio.persist_count, 1)
        self.assertEqual(studio.hud_update_count, 1)

    def test_overlay_ratio_bounds_existing_and_corrupt_profile_values(self):
        self.assertEqual(overlay_opacity_ratio({}), 1.0)
        self.assertEqual(overlay_opacity_ratio({"overlay_opacity_percent": 5}), 0.4)
        self.assertEqual(overlay_opacity_ratio({"overlay_opacity_percent": 110}), 1.0)
        self.assertEqual(overlay_opacity_ratio({"overlay_opacity_percent": "bad"}), 1.0)


if __name__ == "__main__":
    unittest.main()
