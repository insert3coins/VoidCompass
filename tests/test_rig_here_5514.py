"""5.5.14: how close counts as HERE on the Rig Tracker is a Studio setting
(10 to 200 m, 40 by default), and the Mining page follows it."""

import tempfile
import unittest
from pathlib import Path

from tests.test_rig_tracker_5510 import BODY, RADIUS, Deck
from voidcompass.overlays.rig_tracker import HERE_M, build_rig_model, rig_here_m

ROOT = Path(__file__).resolve().parents[1]


def rig_at(metres):
    # One rig due north, this many metres away on the test planet.
    import math
    lat = math.degrees(metres / RADIUS)
    return {1: {"lat": lat, "lon": 0.0, "at": 0.0}}


class ModelTests(unittest.TestCase):
    def test_forty_metres_by_default(self):
        self.assertEqual(HERE_M, 40)
        self.assertTrue(build_rig_model(rig_at(35), 0, 0, 0, RADIUS, BODY)["slots"][0]["here"])
        self.assertFalse(build_rig_model(rig_at(60), 0, 0, 0, RADIUS, BODY)["slots"][0]["here"])

    def test_a_wider_here(self):
        self.assertTrue(build_rig_model(rig_at(60), 0, 0, 0, RADIUS, BODY, here_m=80)["slots"][0]["here"])
        self.assertFalse(build_rig_model(rig_at(35), 0, 0, 0, RADIUS, BODY, here_m=20)["slots"][0]["here"])

    def test_the_setting_is_kept_in_range(self):
        self.assertEqual(rig_here_m({}), 40)
        self.assertEqual(rig_here_m({"rig_tracker_here_m": 3}), 10)
        self.assertEqual(rig_here_m({"rig_tracker_here_m": "900"}), 200)
        self.assertEqual(rig_here_m({"rig_tracker_here_m": "lots"}), 40)


class DeckTests(unittest.TestCase):
    def test_the_overlay_follows_the_setting(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck = Deck(folder.name)
        deck._rig_mark(1)
        deck.current_latitude = rig_at(60)[1]["lat"]
        deck._rig_update_overlay()
        self.assertFalse(deck.rig_tracker_hud.update.call_args.args[0]["slots"][0]["here"])
        deck.config["rig_tracker_here_m"] = 100
        deck._rig_update_overlay()
        self.assertTrue(deck.rig_tracker_hud.update.call_args.args[0]["slots"][0]["here"])


class StudioTests(unittest.TestCase):
    def test_saved_per_commander(self):
        from voidcompass.core.config import PROFILE_SETTINGS
        self.assertIn("rig_tracker_here_m", PROFILE_SETTINGS)

    def test_the_studio_field(self):
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = page.split('data-studio-settings="rig_tracker_hud"', 1)[1].split("</section>", 1)[0]
        self.assertIn('data-studio-setting="rig_tracker_here_m"', section)
        self.assertIn('min="10" max="200"', section)

    def test_saving_it_clamps_and_redraws(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
        deck = SimpleNamespace(config={}, _persist_config=lambda: None, update_hud=lambda: None,
                               _schedule_html_dashboard_publish=lambda **kw: None, _rig_update_overlay=Mock(),
                               heartbeat_hud=None, galnet_ticker_hud=None, music_player_hud=None,
                               galaxy_minimap_hud=None, postcard_hud=None, station_info_hud=None,
                               contact_scope_hud=None, current_docked=False)
        HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"rig_tracker_here_m": "500"})
        self.assertEqual(deck.config["rig_tracker_here_m"], 200)
        deck._rig_update_overlay.assert_called_once()
        HtmlOverlayStudioMixin._html_overlay_settings_save(deck, {"overlay_opacity_percent": "90"})
        self.assertEqual(deck._rig_update_overlay.call_count, 1, "only when it's the setting that changed")


if __name__ == "__main__":
    unittest.main()
