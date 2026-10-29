"""5.5.17: the Navigation HUD knows where you are. Docked scenes differ by
place (a station's interior, an outpost, a carrier, a planetary port), and so
does on foot (concourse, hangar, carrier deck, planet); FSD cooldown and the
Rhino have scenes of their own. Also: the combat page's target follows the
scanner's stages, and rigs the game has taken back are forgotten."""

import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tests.test_navigation_state_visuals import SHIP_ART, hud_snapshot, hud_state
from tests.test_rhino_map_5517 import Deck as RigDeck, degrees
from voidcompass.overlays import hud_pages as hp
from voidcompass.overlays.hud import dock_place, foot_place

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class PlaceTests(unittest.TestCase):
    def test_where_you_are_docked(self):
        for station_type, place in (("Coriolis", "orbital"), ("Orbis", "orbital"), ("AsteroidBase", "orbital"),
                                    ("Outpost", "outpost"), ("MegaShip", "outpost"), ("FleetCarrier", "carrier"),
                                    ("CraterOutpost", "surface"), ("OnFootSettlement", "surface"), ("", "orbital")):
            self.assertEqual(dock_place(station_type), place, station_type)

    def test_where_you_are_on_foot(self):
        self.assertEqual(foot_place(0x1 | 0x8 | 0x4000, "Coriolis"), "concourse")
        self.assertEqual(foot_place(0x1 | 0x8 | 0x2000, "Orbis"), "hangar")
        self.assertEqual(foot_place(0x1 | 0x8 | 0x4000, "FleetCarrier"), "carrier")
        self.assertEqual(foot_place(0x1, "", on_carrier_deck=True), "carrier")
        self.assertEqual(foot_place(0x1 | 0x10 | 0x8000), "planet")


class TargetTests(unittest.TestCase):
    def test_the_target_follows_the_scan_stages(self):
        target = hp.read_target({"TargetLocked": True, "Ship": "mandalay", "ScanStage": 0})
        self.assertEqual((target["ship"], target["stage"]), ("Mandalay", 0), "no Ship_Localised: its symbol made readable")
        target = hp.read_target({"TargetLocked": True, "Ship": "mandalay", "ScanStage": 3, "PilotName_Localised": "Kai",
                                 "PilotRank": "Elite", "ShieldHealth": 50, "HullHealth": 80, "LegalStatus": "WantedEnemy",
                                 "Subsystem_Localised": "Power Plant", "SubsystemHealth": 70}, target)
        self.assertEqual((target["pilot"], target["shields"], target["subsystem"]), ("Kai", 50.0, "Power Plant"))
        self.assertEqual(hp.combat_page(target)["blocks"][0]["tone"], "red", "WantedEnemy is wanted")
        target = hp.read_target({"TargetLocked": True, "Ship": "mandalay", "ScanStage": 3, "PilotName_Localised": "Kai",
                                 "ShieldHealth": 20, "HullHealth": 80, "LegalStatus": "WantedEnemy"}, target)
        self.assertNotIn("subsystem", target, "the subsystem let go")
        other = hp.read_target({"TargetLocked": True, "Ship": "mandalay", "ScanStage": 1, "PilotName_Localised": "Ava"}, target)
        self.assertNotIn("shields", other, "another pilot in the same type starts afresh")
        self.assertIsNone(hp.read_target({"TargetLocked": False}, other))
        self.assertEqual(hp.ship_name("type9_military"), "Type9 Military")


class RigTests(unittest.TestCase):
    def deck(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return RigDeck(folder.name)

    def test_a_rig_past_5_km_is_forgotten(self):
        deck = self.deck()
        deck._rig_mark(1)
        deck._rig_mark(2)
        deck.current_latitude = degrees(5100)
        deck._rig_range_watch()
        self.assertEqual(deck.rig_store().rigs(deck.current_sys, deck.current_body_name), {},
                         "both rigs are over 5 km behind: the game has them")
        titles = [call.args[0] for call in deck.toast_hud.push.call_args_list]
        self.assertIn("RIG 1 LOST", titles)

    def test_leaving_the_planet_forgets_its_rigs(self):
        deck = self.deck()
        deck._rig_mark(3)
        self.assertTrue(deck._rig_left_body(deck.current_body_name))
        self.assertEqual(deck.rig_store().rigs(deck.current_sys, deck.current_body_name), {})
        self.assertFalse(deck._rig_left_body(deck.current_body_name), "nothing to forget the second time")
        # Back in the ship on that planet later: no ground map from old rigs.
        deck.current_in_srv, deck.current_vehicle_name = False, ""
        self.assertIsNone(deck._surface_map_model())


class SceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_each_place_draws_its_own_scene(self):
        page = self.browser.new_page(viewport={"width": 500, "height": 350})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = SHIP_ART / path[len("/ship-art/"):] if path.startswith("/ship-art/") else WEB / path.lstrip("/")
            route.fulfill(path=str(target)) if target.is_file() else route.fulfill(status=404, body="")

        page.route("http://p.test/**", serve)
        page.goto("http://p.test/navigation_hud/index.html")
        page.wait_for_function('Boolean(window.navigationScene)')
        pictures = {}
        for label, key, value in (("DOCKED", "dock_place", "orbital"), ("DOCKED", "dock_place", "outpost"),
                                  ("DOCKED", "dock_place", "carrier"), ("DOCKED", "dock_place", "surface"),
                                  ("ONFOOT", "foot_place", "planet"), ("ONFOOT", "foot_place", "concourse"),
                                  ("ONFOOT", "foot_place", "hangar"), ("FSD COOLDOWN", "foot_place", "planet"),
                                  ("RHINO", "foot_place", "planet")):
            state = hud_state(label)
            state["dynamics"][key] = value
            page.evaluate("s => render(s)", hud_snapshot(state, reduced=True))
            page.wait_for_timeout(250)
            pictures[(label, value)] = page.evaluate("document.getElementById('deck-canvas').toDataURL()")
        self.assertEqual(errors, [])
        docked = [pictures[("DOCKED", place)] for place in ("orbital", "outpost", "carrier", "surface")]
        self.assertEqual(len(set(docked)), 4, "four places, four scenes")
        foot = [pictures[("ONFOOT", place)] for place in ("planet", "concourse", "hangar")]
        self.assertEqual(len(set(foot)), 3)
        state = hud_state("ONFOOT")
        state["dynamics"]["foot_place"] = "concourse"
        page.evaluate("s => render(s)", hud_snapshot(state, reduced=True))
        self.assertEqual(page.inner_text("#state-label"), "CONCOURSE")


if __name__ == "__main__":
    unittest.main()
