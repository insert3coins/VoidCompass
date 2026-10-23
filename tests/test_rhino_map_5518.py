"""5.5.18: the Rhino map has its own zoom. A ship parked a long way off (or
old refining spots) zoomed it out until the rigs and their spacing rings were
specks and a new rig seemed not to appear; now it fits your rigs and nearby
deposits, with the ship and a target pointing from the edge, or a fixed range
chosen in Overlay Studio. Also: the HUD's survey list ranked like the survey
overlay."""

import math
import re
import tempfile
import unittest
from pathlib import Path

from unittest.mock import Mock

from tests.test_rhino_map_5517 import Deck as RhinoDeck, degrees
from voidcompass.overlays.galaxy_minimap_hud import GalaxyMinimapHUD


class Deck(RhinoDeck):
    """The Rhino tests' deck, with the Galaxy Minimap up beside the Rhino Map."""

    def __init__(self, folder):
        super().__init__(folder)
        self.galaxy_minimap_hud = GalaxyMinimapHUD(Mock(), self.config)
from voidcompass.core import config as config_module
from voidcompass.overlays import hud_pages as hp
from voidcompass.overlays.surface_map import FOCUS_M, RANGES, map_half, surface_options

ROOT = Path(__file__).resolve().parents[1]


class ZoomTests(unittest.TestCase):
    def deck(self, **config):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck = Deck(folder.name)
        deck.config.update(config)
        return deck

    def test_a_far_ship_no_longer_zooms_it_out(self):
        deck = self.deck()
        deck.surface_ship_position = {"lat": degrees(-2500), "lon": 0.0}
        deck._rig_mark(1)
        deck.current_latitude = degrees(80)
        deck._rig_mark(2)
        surface = deck.rhino_map_hud._html_render_model
        self.assertEqual([rig["slot"] for rig in surface["rigs"]], [1, 2], "a new rig shows at once")
        self.assertLess(surface["half_m"], 200, "fitted to the rigs, not the ship 2.5 km away")
        self.assertIsNotNone(surface["ship"], "the ship still shows, from the map's edge")
        self.assertGreater(surface["spacing_m"] / surface["half_m"], .3, "the spacing rings are big enough to see")

    def test_its_own_range_set_in_studio(self):
        self.assertEqual(surface_options({"rhino_map_range": "600"})["range"], "600")
        self.assertEqual(surface_options({"rhino_map_range": "9"})["range"], "auto")
        self.assertEqual(map_half([0, 0], [[50, 0]], "2500"), 2500.0)
        self.assertEqual(map_half([0, 0], [[FOCUS_M + 1, 0]]), 150.0)
        deck = self.deck(rhino_map_range="1200")
        deck._update_rhino_map()
        self.assertEqual(deck.rhino_map_hud._html_render_model["half_m"], 1200.0)
        self.assertIn("rhino_map_range", config_module.PROFILE_SETTINGS)
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        select = re.search(r'data-studio-setting="rhino_map_range">(.*?)</select>', page, re.S).group(1)
        self.assertEqual(tuple(re.findall(r'value="([^"]+)"', select)), RANGES)


class RangeHotkeyTests(unittest.TestCase):
    def test_the_hotkey_goes_round_the_ranges(self):
        from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS
        spec = next(row for row in OVERLAY_HOTKEY_SPECS if row[0] == "rhino_map_range")
        self.assertEqual(spec[1:3], ("overlay_hotkey_rhino_map_range", "Rhino Map: range"))
        self.assertIn("overlay_hotkey_rhino_map_range", config_module.PROFILE_SETTINGS)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck = Deck(folder.name)
        said = []
        deck.add_event_feed_entry = lambda tag, text, severity="INFO": said.append(text)
        seen = [deck._rhino_map_next_range() for _ in RANGES]
        self.assertEqual(seen, list(RANGES[1:]) + ["auto"], "round the ranges and back to Your rigs")
        self.assertEqual(said[0], "Rhino map range: 300 m")
        deck._rhino_map_next_range()
        surface = deck.rhino_map_hud._html_render_model
        self.assertEqual((surface["range"], surface["half_m"]), ("300 M", 300.0), "the map shows its new range")


class OwnOverlayTests(unittest.TestCase):
    """The Rhino Map is its own overlay: the Galaxy Minimap stays the galaxy,
    and changing the range never sends the map back to it."""

    def test_it_shows_in_the_rhino_and_hides_after(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck = Deck(folder.name)
        deck._update_rhino_map()
        self.assertTrue(deck.rhino_map_hud.visible)
        deck._rhino_map_next_range()
        self.assertTrue(deck.rhino_map_hud.visible, "a new range keeps the map up")
        self.assertNotIn("surface", deck.galaxy_minimap_hud._html_render_model, "the minimap stays the galaxy")
        deck.current_in_srv = False
        deck._update_rhino_map()
        self.assertFalse(deck.rhino_map_hud.visible)

    def test_it_is_an_overlay_of_its_own(self):
        from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR, TEXT_SIZE_KEYS
        spec = OVERLAY_SPEC_BY_ATTR["rhino_map_hud"]
        self.assertEqual((spec.overlay_id, spec.enabled_key, spec.hotkey_key),
                         ("rhino-map", "rhino_map_overlay_enabled", "overlay_hotkey_rhino_map"))
        self.assertEqual(TEXT_SIZE_KEYS["rhino_map_hud"], "rhino_map_text_scale_percent")
        for key in ("rhino_map_overlay_enabled", "rhino_map_hud_x", "rhino_map_hud_y", "rhino_map_size",
                    "rhino_map_show", "rhino_map_up", "rhino_map_range"):
            self.assertIn(key, config_module.PROFILE_SETTINGS)
        for name in ("index.html", "app.js", "styles.css"):
            self.assertTrue((ROOT / "web" / "rhino_map" / name).is_file())
        minimap = (ROOT / "web" / "galaxy_minimap" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("drawSurface", minimap, "the ground drawing moved out of the minimap")
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = page.split('data-studio-settings="galaxy_minimap_hud"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn("rhino_map", section, "no Rhino settings left in the minimap's section")


class SurveyOrderTests(unittest.TestCase):
    def test_biology_first_then_geology_then_value(self):
        model = {"system": "S", "scanned": 4, "total": 4, "total_known": True, "rows": [
            {"name": "S A 1", "max_value": 5_000_000}, {"name": "S A 2", "bio_count": 2, "max_value": 100_000},
            {"name": "S A 3", "geo_count": 1, "max_value": 400_000},
            {"name": "S A 4", "bio_count": 1, "bio_complete": True, "max_value": 9_000_000}]}
        listing = next(block for block in hp.survey_page(model)["blocks"] if block["type"] == "list")
        self.assertEqual([item["name"] for item in listing["items"]], ["A 2", "A 3", "A 4", "A 1"])


if __name__ == "__main__":
    unittest.main()
