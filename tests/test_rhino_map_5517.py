"""5.5.17: the Rhino map. While you drive the Rhino on a planet, the Galaxy
Minimap shows the ground round you: you and your trail, the ship, your
rigs (the next to collect, their HERE rings) and where your drill refined."""

import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from tests.test_rig_tracker_5510 import BODY, RADIUS
from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard_rigs_mixin import DashboardRigsMixin
from voidcompass.dashboard.html_planetary import HtmlPlanetaryMixin
from voidcompass.overlays.galaxy_minimap_hud import GalaxyMinimapHUD
from voidcompass.overlays.rig_tracker import RigStore
from voidcompass.overlays.surface_map import (
    MAX_HALF_M, MIN_HALF_M, build_surface_map, cluster_deposits, map_half, surface_options, wants_surface,
)

ROOT = Path(__file__).resolve().parents[1]


def degrees(metres):
    return math.degrees(metres / RADIUS)


class Plane:
    """East/north metres from 0, 0 (as html_planetary's frame, near the equator)."""

    def __call__(self, point):
        return [round(math.radians(point[1]) * RADIUS, 1), round(math.radians(point[0]) * RADIUS, 1)]


class OptionTests(unittest.TestCase):
    def test_in_the_rhino_by_default(self):
        self.assertEqual(surface_options({}), {"mode": "rhino", "up": "heading"})
        self.assertTrue(wants_surface("rhino", on_planet=True, in_srv=True, vehicle="RHINO"))
        self.assertFalse(wants_surface("rhino", on_planet=True, in_srv=True, vehicle="SCARAB"))
        self.assertTrue(wants_surface("srv", on_planet=True, in_srv=False, on_foot=True))
        self.assertFalse(wants_surface("off", on_planet=True, in_srv=True, vehicle="RHINO"))
        self.assertFalse(wants_surface("rhino", on_planet=False, in_srv=True, vehicle="RHINO"))

    def test_saved_per_commander_and_set_in_studio(self):
        for key in ("galaxy_minimap_surface", "galaxy_minimap_surface_up"):
            self.assertIn(key, config_module.PROFILE_SETTINGS)
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = page.split('data-studio-settings="galaxy_minimap_hud"', 1)[1].split("</section>", 1)[0]
        self.assertIn('data-studio-setting="galaxy_minimap_surface"', section)
        self.assertIn('data-studio-setting="galaxy_minimap_surface_up"', section)


class ModelTests(unittest.TestCase):
    def test_refining_pulses_gather_into_deposits(self):
        spots = [(degrees(100 + n), degrees(200), "Platinum") for n in range(5)] + [(degrees(-300), degrees(0), "Osmium")] * 2
        deposits = cluster_deposits(spots, Plane())
        self.assertEqual([deposit["pulses"] for deposit in deposits], [5, 2])
        self.assertEqual(deposits[0]["materials"], ["Platinum"])
        self.assertAlmostEqual(deposits[0]["at"][1], 102, delta=1)

    def test_the_map_zooms_to_what_matters(self):
        self.assertEqual(map_half([0, 0], []), MIN_HALF_M)
        self.assertAlmostEqual(map_half([0, 0], [[400, 0]]), 460)
        self.assertEqual(map_half([0, 0], [[90000, 0]]), MAX_HALF_M)

    def test_rigs_ship_and_next_to_collect(self):
        plane_map = {"body": BODY, "you": {"at": [0.0, 0.0], "heading": 90.0}, "ship": {"at": [0.0, -300.0]},
                     "trail": [[0, -300], [0, -150], [0, 0]], "sites": [], "target": None}
        rig_model = {"slots": [{"slot": 1, "tracked": True, "distance_m": 120.0, "here": False, "nearest": True},
                               {"slot": 2, "tracked": True, "distance_m": 20.0, "here": True}], "order": [1]}
        model = build_surface_map(plane_map, Plane(), rig_model=rig_model,
                                  rig_points={1: (degrees(120), 0.0), 2: (0.0, degrees(20))},
                                  spots=[(0.0, 0.0, "Gold")], signals=3, vehicle="Rhino")
        self.assertEqual(model["vehicle"], "RHINO")
        self.assertEqual((model["ship"]["distance"], model["ship"]["bearing"]), (300, 180.0))
        self.assertEqual([rig["slot"] for rig in model["rigs"]], [1, 2])
        self.assertEqual(model["next_rig"], 1)
        self.assertTrue(model["rigs"][1]["here"])
        self.assertEqual((model["signals"], len(model["deposits"]), model["half_m"]), (3, 1, 345.0))


class Deck(DashboardRigsMixin, HtmlPlanetaryMixin):
    def __init__(self, folder):
        self.config = {"active_commander_name": "Tester"}
        self.on_planet, self.current_latitude, self.current_longitude = True, 0.0, 0.0
        self.current_planet_radius, self.current_heading = RADIUS, 0.0
        self.current_body_name, self.current_sys = BODY, "Synuefe XX-A d1-58"
        self.current_in_srv, self.current_vehicle_name, self.current_on_foot = True, "RHINO", False
        self.surface_ship_position = {"lat": degrees(-200), "lon": 0.0}
        self.surface_trail = []
        self.target_latlon_active = False
        self.body_signals = {7: {"body_name": BODY, "mining": 4}}
        self.toast_hud = Mock()
        self.rig_tracker_hud = None
        self.galaxy_minimap_hud = GalaxyMinimapHUD(Mock(), self.config)
        self._rig_store_instance = RigStore(str(Path(folder) / "rigs.json"))

    def rig_store(self):
        return self._rig_store_instance


class DeckTests(unittest.TestCase):
    def deck(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Deck(folder.name)

    def test_the_minimap_turns_to_the_ground_in_the_rhino(self):
        deck = self.deck()
        deck._rig_mark(1)
        deck.current_latitude = degrees(80)
        deck._surface_note_pulse({"Type_Localised": "Platinum"})
        deck._update_surface_minimap()
        surface = deck.galaxy_minimap_hud._html_render_model["surface"]
        self.assertEqual((surface["vehicle"], surface["signals"], len(surface["rigs"]), len(surface["deposits"])), ("RHINO", 4, 1, 1))
        self.assertEqual(surface["ship"]["distance"], 280)

    def test_back_to_the_galaxy_out_of_the_rhino(self):
        deck = self.deck()
        deck._update_surface_minimap()
        deck.current_in_srv = False
        deck._update_surface_minimap()
        self.assertIsNone(deck.galaxy_minimap_hud._html_render_model["surface"])
        deck.config["galaxy_minimap_surface"] = "off"
        deck.current_in_srv = True
        deck._update_surface_minimap()
        self.assertIsNone(deck.galaxy_minimap_hud._html_render_model["surface"])

    def test_pulses_belong_to_their_planet(self):
        deck = self.deck()
        deck._surface_note_pulse({"Type": "gold"})
        deck.current_body_name = "Another body"
        deck._surface_note_pulse({"Type": "gold"})
        self.assertEqual(len(deck._surface_pulses["spots"]), 1, "a new body starts afresh")


class PageTests(unittest.TestCase):
    """The minimap page draws the ground instead of the galaxy."""

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

    def test_the_ground_view(self):
        import json
        from urllib.parse import unquote, urlsplit
        from voidcompass.core import themes
        plane_map = {"body": BODY, "you": {"at": [0.0, 0.0], "heading": 45.0}, "ship": {"at": [0.0, -300.0]},
                     "trail": [[0, -300], [0, 0]], "sites": [{"label": "Vein", "at": [50.0, 50.0]}], "target": None}
        surface = build_surface_map(plane_map, Plane(), rig_model={"slots": [{"slot": 1, "tracked": True, "distance_m": 120.0}], "order": [1]},
                                    rig_points={1: (degrees(120), 0.0)}, vehicle="RHINO")
        snapshot = {"theme": dict(themes.ACTIVE_PALETTE), "effects": {}, "minimap": {"here": None, "trail": [], "options": {}, "surface": surface}}
        page = self.browser.new_page(viewport={"width": 240, "height": 280})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = ROOT / "web" / path.lstrip("/")
            if target.is_file():
                route.fulfill(path=str(target))
            elif path.startswith("/api/snapshot"):
                route.fulfill(status=200, body=json.dumps(snapshot), content_type="application/json")
            elif path.startswith("/api/health"):
                route.fulfill(status=200, body='{"revision": 1}', content_type="application/json")
            else:
                route.fulfill(status=200, body="{}", content_type="application/json")

        page.route("http://map.test/**", serve)
        page.goto("http://map.test/galaxy_minimap/index.html?token=t&overlay=galaxy-minimap")
        page.wait_for_function("document.getElementById('minimap').classList.contains('surface')", timeout=5000)
        self.assertEqual(page.inner_text("#region"), "RHINO MAP")
        self.assertIn("SHIP 300 M", page.inner_text("#facts"))
        self.assertFalse(page.is_visible("#galaxy"))
        frame = page.evaluate("window.__minimap.surface()")
        self.assertAlmostEqual(frame["turn"], math.radians(45), places=3)
        self.assertEqual(errors, [])



class RigsOutTests(unittest.TestCase):
    """Rigs out on a planet keep the map, out of the Rhino too; and the next
    to collect is the next in the order they went down."""

    def test_next_is_the_order_they_went_down(self):
        from voidcompass.overlays.rig_tracker import build_rig_model, placed_order
        rigs = {1: {"lat": degrees(10), "lon": 0.0, "at": 300.0}, 2: {"lat": degrees(500), "lon": 0.0, "at": 100.0},
                3: {"lat": degrees(5), "lon": 0.0, "at": 200.0}}
        self.assertEqual(placed_order(rigs), [2, 3, 1])
        model = build_rig_model(rigs, 0.0, 0.0, 0.0, RADIUS, BODY)
        self.assertEqual(model["order"], [2, 3, 1])
        self.assertEqual([row["slot"] for row in model["slots"] if row.get("next")], [2], "not the nearest (3)")
        self.assertTrue(next(row for row in model["slots"] if row["slot"] == 3)["nearest"])

    def test_the_map_stays_while_rigs_are_out(self):
        self.assertTrue(wants_surface("rhino", on_planet=True, in_srv=False, rigs_here=True))
        self.assertFalse(wants_surface("rhino", on_planet=False, in_srv=False, rigs_here=True), "not once you've left")
        self.assertFalse(wants_surface("off", on_planet=True, in_srv=False, rigs_here=True))

    def test_in_the_ship_no_second_ship_marker(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck = Deck(folder.name)
        deck._rig_mark(1)
        deck.current_in_srv, deck.current_vehicle_name = False, ""
        deck._update_surface_minimap()
        surface = deck.galaxy_minimap_hud._html_render_model["surface"]
        self.assertEqual((surface["vehicle"], surface["ship"]), ("SHIP", None))
        self.assertEqual(len(surface["rigs"]), 1)


class EdsmtIdeasTests(unittest.TestCase):
    """After EDSMT: rig spacing, where the next rig can go, rigs about to be
    lost (the game destroys one 5 km behind you), and rigs ready to collect."""

    def test_the_advice(self):
        from voidcompass.overlays.rig_tracker import rig_advice
        rows = [{"slot": 1, "tracked": True, "distance_m": 30.0, "here": True, "age_s": 130},
                {"slot": 2, "tracked": True, "distance_m": 3600.0, "age_s": 50},
                {"slot": 3, "tracked": True, "distance_m": 4850.0}, {"slot": 4, "tracked": False}]
        advice = rig_advice(rows, spacing_m=78, warn_m=3500)
        self.assertEqual(advice["too_close"], 1)
        self.assertEqual(advice["too_far"], [{"slot": 3, "distance": 4850, "last": True}, {"slot": 2, "distance": 3600, "last": False}])
        self.assertEqual(advice["ready"], [1])
        self.assertEqual(rig_advice(rows, warn_m=0)["too_far"], [], "0 turns the warning off")

    def test_where_the_next_rig_can_go(self):
        from voidcompass.overlays.surface_map import legal_spot
        self.assertEqual(legal_spot([0, 0], [[200, 0]], 78), {"at": [0, 0], "distance": 0, "here": True})
        spot = legal_spot([10, 0], [[0, 0]], 78)
        self.assertFalse(spot["here"])
        self.assertAlmostEqual(spot["distance"], 69, delta=2, msg="straight out past the ring")
        self.assertGreaterEqual(math.hypot(*spot["at"]), 78)

    def test_settings(self):
        from voidcompass.overlays.rig_tracker import rig_spacing_m, rig_warn_m
        self.assertEqual((rig_spacing_m({}), rig_warn_m({})), (78, 3500))
        self.assertEqual((rig_spacing_m({"rig_tracker_spacing_m": 5}), rig_warn_m({"rig_tracker_warn_m": 9000})), (20, 4900))
        for key in ("rig_tracker_spacing_m", "rig_tracker_warn_m"):
            self.assertIn(key, config_module.PROFILE_SETTINGS)
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = page.split('data-studio-settings="rig_tracker_hud"', 1)[1].split("</section>", 1)[0]
        self.assertIn('data-studio-setting="rig_tracker_spacing_m"', section)
        self.assertIn('data-studio-setting="rig_tracker_warn_m"', section)

    def test_a_rig_too_far_is_said_once_a_trip(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck = Deck(folder.name)
        deck._rig_mark(1)
        deck.toast_hud.push.reset_mock()
        deck.current_latitude = degrees(3700)
        self.assertTrue(deck._rig_range_watch())
        deck._rig_range_watch()
        titles = [call.args[0] for call in deck.toast_hud.push.call_args_list]
        self.assertEqual(titles, ["RIG 1 TOO FAR"], "once, not every tick")
        deck.current_latitude = degrees(100)
        deck._rig_range_watch()
        deck.current_latitude = degrees(3700)
        deck._rig_range_watch()
        self.assertEqual(len(deck.toast_hud.push.call_args_list), 2, "again after you went back")

    def test_the_hud_page_says_it(self):
        from voidcompass.overlays import hud_pages as hp
        model = {"slots": [{"slot": 1, "tracked": True, "distance_m": 3900.0, "relative": 0},
                           {"slot": 2, "tracked": True, "distance_m": 10.0, "here": True, "age_s": 200}], "order": [1, 2]}
        notes = [block["text"] for block in hp.rhino_page(model)["blocks"] if block["type"] == "note"]
        self.assertEqual(notes[:2], ["RIG 1 3.9 KM AWAY · LOST AT 5 KM", "COLLECT RIG 2: IT'S HAD TWO MINUTES"])


if __name__ == "__main__":
    unittest.main()
