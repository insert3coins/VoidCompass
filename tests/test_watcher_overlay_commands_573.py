"""5.7.3: one overlay by name. "Hide the survey overlay" / "show the minimap"
hide or show it as its hotkey does; "turn off the music player" / "switch on
the Rhino Map" switch it as Overlay Studio does. "Hide the overlays" is still
the whole lot."""

import unittest

from voidcompass.core.overlay_registry import OVERLAY_SPECS
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import watcher_copilot as copilot


class RequestTests(unittest.TestCase):
    def test_one_overlay_by_name(self):
        for said, wanted in (
                ("Hide the survey overlay", {"op": "hide", "overlay": "survey"}),
                ("show the minimap", {"op": "show", "overlay": "galaxy-minimap"}),
                ("bring back the nav HUD", {"op": "show", "overlay": "navigation"}),
                ("turn off the music player", {"op": "off", "overlay": "music-player"}),
                ("turn the Rhino Map off", {"op": "off", "overlay": "rhino-map"}),
                ("switch on the galnet ticker", {"op": "on", "overlay": "galnet-ticker"}),
                ("please hide yourself", {"op": "hide", "overlay": "heartbeat"}),
                ("close the trade route", {"op": "hide", "overlay": "trade-route"})):
            self.assertEqual(copilot.overlay_request(said), wanted, said)

    def test_the_whole_lot_and_questions_stay_as_they_were(self):
        for said in ("hide the overlays", "hide everything", "show the overlays", "hide the hud",
                     "show me the cargo", "what cargo do we have", "pause the music"):
            self.assertIsNone(copilot.overlay_request(said), said)

    def test_every_overlay_has_a_name(self):
        self.assertEqual(set(copilot.OVERLAY_NAMES), {spec.overlay_id for spec in OVERLAY_SPECS})


class FakeWindow:
    def __init__(self, shown=True):
        self.shown = shown


class Deck(DashboardWatcherVoiceMixin):
    def __init__(self, enabled=True, shown=True, hidden=(), curtain=False):
        spec = next(row for row in OVERLAY_SPECS if row.overlay_id == "survey")
        self.config = {spec.enabled_key: enabled}
        self.survey_status_hud = object()
        self.window = FakeWindow(shown)
        self._overlay_hotkey_hidden = set(hidden)
        self._overlay_hotkey_global_hidden = curtain
        self.done = []

    def _overlay_window(self, overlay):
        return self.window if overlay is not None else None

    @staticmethod
    def _overlay_window_is_shown(window):
        return window.shown

    def _ui_post(self, callback, *args, key=None, **kwargs):
        callback(*args, **kwargs)

    def _handle_overlay_hotkey(self, action):
        self.done.append(("hotkey", action))

    def _html_overlay_toggle(self, attr):
        self.done.append(("studio", attr))
        return True


class DeckTests(unittest.TestCase):
    def test_hide_and_show_as_its_hotkey_does(self):
        deck = Deck()
        self.assertEqual(deck._watcher_mind_action("hide the survey overlay"), "Survey Operations hidden.")
        self.assertEqual(deck.done, [("hotkey", "survey")])
        deck = Deck(hidden={"survey_status_hud"}, shown=False)
        self.assertEqual(deck._watcher_mind_action("show the survey"), "Survey Operations is back.")
        self.assertEqual(deck.done, [("hotkey", "survey")])

    def test_nothing_to_do(self):
        self.assertEqual(Deck(hidden={"survey_status_hud"}, shown=False)._watcher_mind_action("hide the survey"),
                         "Survey Operations is already hidden.")
        self.assertEqual(Deck()._watcher_mind_action("show the survey"), "Survey Operations is already showing.")
        self.assertIn("shows itself when there's something to show",
                      Deck(shown=False)._watcher_mind_action("show the survey"), "on, with nothing to show")

    def test_switched_off_and_on_as_overlay_studio_does(self):
        deck = Deck()
        self.assertEqual(deck._watcher_mind_action("turn off the survey"), "Survey Operations switched off.")
        self.assertEqual(deck.done, [("studio", "survey_status_hud")])
        deck = Deck(enabled=False)
        self.assertEqual(deck._watcher_mind_action("show the survey overlay"), "Survey Operations switched on.",
                         "shown, a switched-off one is switched on")
        self.assertEqual(Deck(enabled=False)._watcher_mind_action("turn off the survey"), "Survey Operations is already off.")
        self.assertEqual(Deck(enabled=False)._watcher_mind_action("hide the survey"), "Survey Operations is already off.")

    def test_behind_the_curtain(self):
        deck = Deck(curtain=True)
        self.assertIn("show the overlays first", deck._watcher_mind_action("show the survey"))
        self.assertEqual(deck.done, [])


if __name__ == "__main__":
    unittest.main()
