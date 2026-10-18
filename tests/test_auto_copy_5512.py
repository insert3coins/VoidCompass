"""5.5.12: auto-copy the next waypoint, out where commanders can find it: a
switch under COPY NEXT DESTINATION on the Command Deck."""

import unittest
from pathlib import Path

from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin

ROOT = Path(__file__).resolve().parents[1]


class Deck(HtmlDashboardMixin):
    def __init__(self):
        self.config = {"auto_copy_waypoint": False}
        self.feed, self.saved, self.published = [], 0, 0

    def _persist_config(self):
        self.saved += 1

    def _schedule_html_dashboard_publish(self, immediate=False):
        self.published += 1

    def add_event_feed_entry(self, tag, message, severity="INFO", copy_text=None, url=None):
        self.feed.append((tag, message))


class AutoCopyTests(unittest.TestCase):
    def test_the_command_deck_switch(self):
        deck = Deck()
        self.assertTrue(deck.handle_html_dashboard_command({"action": "set_auto_copy", "enabled": True}))
        self.assertTrue(deck.config["auto_copy_waypoint"])
        self.assertEqual(deck.saved, 1)
        self.assertIn("Auto-copy on", deck.feed[-1][1])
        deck.handle_html_dashboard_command({"action": "set_auto_copy", "enabled": False})
        self.assertFalse(deck.config["auto_copy_waypoint"])

    def test_the_deck_is_allowed_to_send_it(self):
        runtime = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"set_auto_copy"', runtime)

    def test_the_route_panel_shows_it(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        route = source.split("def _html_dashboard_route", 1)[1].split("\n    def ", 1)[0]
        self.assertIn('"auto_copy": bool(self.config.get("auto_copy_waypoint", False))', route)
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="auto-copy"', page)
        self.assertLess(page.index('id="copy-next"'), page.index('id="auto-copy"'), "right under COPY NEXT DESTINATION")
        app = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn("AUTO-COPY NEXT WAYPOINT ON ARRIVAL", app)
        self.assertIn('label: "Auto-copy the next waypoint"', app, "Settings calls it the same thing")


if __name__ == "__main__":
    unittest.main()
