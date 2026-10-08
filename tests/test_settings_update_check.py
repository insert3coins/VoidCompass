"""Settings › Diagnostics has a CHECK FOR UPDATES button with live status."""

import unittest
from pathlib import Path
from unittest import mock

from voidcompass.dashboard.dashboard_core_mixin import DashboardCoreMixin

ROOT = Path(__file__).resolve().parents[1]


class _Deck(DashboardCoreMixin):
    def __init__(self):
        self.published = 0
        self.feed = []

    def _schedule_html_dashboard_publish(self, immediate=False, **_kw):
        self.published += 1

    def add_event_feed_entry(self, *args, **kwargs):
        self.feed.append(args)

    def _ui_post(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


class SettingsUpdateCheckTests(unittest.TestCase):
    def test_settings_page_has_the_button(self):
        app = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('settingGroup("UPDATES"', app)
        self.assertIn('data-command="check_updates" data-update-check', app)
        self.assertIn("function renderSettingsUpdate", app)

    def test_manual_check_shows_checking_then_failure(self):
        deck = _Deck()
        with mock.patch("threading.Thread") as thread:
            self.assertTrue(deck.check_updates(manual=True))
        self.assertTrue(deck.release_update["checking"])
        self.assertEqual(deck.published, 1)
        # A second press while it is still asking does nothing.
        with mock.patch("threading.Thread") as again:
            self.assertFalse(deck.check_updates(manual=True))
            again.assert_not_called()
        deck._release_check_failed("timed out", manual=True)
        self.assertFalse(deck.release_update["checking"])
        self.assertEqual(deck.release_update["error"], "timed out")
        self.assertTrue(deck.feed)

    def test_result_clears_checking(self):
        deck = _Deck()
        deck.release_update = {"checking": True}
        deck._apply_release_update({"checked": True, "available": False, "checked_at": 1.0}, manual=True)
        self.assertFalse(deck.release_update.get("checking"))


if __name__ == "__main__":
    unittest.main()
