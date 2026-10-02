"""5.5.1.5: cockpit notifications for body signals can be turned off (they
pile up while scanning a system); the signals are still recorded."""

from pathlib import Path
import unittest
from unittest.mock import Mock

from voidcompass.core import config as config_module

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("toast_fss_signals_enabled", "toast_dss_signals_enabled")


class SignalNotificationTests(unittest.TestCase):
    def test_both_switches_are_per_profile_and_on_by_default(self):
        source = (ROOT / "src/voidcompass/core/config.py").read_text(encoding="utf-8")
        for key in KEYS:
            with self.subTest(key=key):
                self.assertIn(key, config_module.PROFILE_BOOL_SETTINGS)
                self.assertIn(f'"{key}": True', source)

    def test_studio_offers_and_saves_them(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio.config = {}
        studio._persist_config = Mock()
        studio._schedule_html_dashboard_publish = Mock()
        for key in KEYS:
            self.assertTrue(studio._html_overlay_option_toggle(key, False))
            self.assertFalse(studio.config[key])
        index = (ROOT / "web/dashboard/index.html").read_text(encoding="utf-8")
        toast = index.split('data-studio-settings="toast_hud"', 1)[1].split("</section>", 1)[0]
        for key in KEYS:
            self.assertIn(f'data-overlay-option="{key}"', toast)

    def test_each_notification_checks_its_own_switch(self):
        dashboard = (ROOT / "src/voidcompass/dashboard/dashboard.py").read_text(encoding="utf-8")
        for key, title in zip(KEYS, ("SURFACE SIGNALS", "DSS SIGNALS")):
            with self.subTest(title=title):
                gate = dashboard.index(f'self.config.get("{key}", True)')
                push = dashboard.index(f'self._push_live_toast("{title}"')
                self.assertLess(push - gate, 600, "the switch guards that notification")


if __name__ == "__main__":
    unittest.main()
