"""5.6.5: the Expedition overlay reworked around the next stop. It walks you
through it step by step (jump to the system, fly to the body, land at the
spot, arrive) and makes the planet to land on plain: its short name, what it
is from your scans, where it sits among the system's bodies, and a compass
on the way down."""

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from tests.test_expeditions_561 import Deck
from tests.test_overlay_text_fit_5539 import EXPEDITION_SAMPLE
from voidcompass.dashboard.dashboard_expedition_mixin import _body_facts, _short_body
from voidcompass.overlays.expedition_hud import build_expedition_model

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = "Eol Prou LW-L c8-306"
BODY = f"{SYSTEM} 4 a"


def scan(name, ls, **extra):
    return {"name": name.removeprefix(SYSTEM).strip(), "full_name": name, "distance_to_arrival": ls, **extra}


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()
        self.deck.current_sys = "Sol"
        self.deck.current_body_name = ""
        self.deck.current_landed = self.deck.current_in_srv = self.deck.current_on_foot = False
        self.deck.on_planet = False
        self.deck.scan_items_by_id = {}
        self.deck.nav_route_entries = []
        self.legs = [{"id": "a", "system": SYSTEM, "body": BODY, "note": "The Crystal Arches", "lat": -23.45, "lon": 114.08, "kind": "stop"}]

    def guide(self):
        return self.deck._expedition_guide(self.legs)

    def test_jump_then_fly_then_land_then_arrive(self):
        self.deck.nav_route_entries = [{"StarSystem": "Sol"}, {"StarSystem": "Achenar"}, {"StarSystem": SYSTEM}]
        guide = self.guide()
        self.assertEqual((guide["stage"], guide["jumps"], guide["short"]), ("jump", 2, "4 A"))
        self.deck.current_sys = SYSTEM
        self.deck.scan_items_by_id = {
            1: scan(f"{SYSTEM} A", 0, star_type="K"), 2: scan(f"{SYSTEM} 4", 1800, planet_class="Class I gas giant"),
            3: scan(BODY, 1834.2, planet_class="High metal content body", gravity_g=.38, surface_temp=412, landable=True,
                    atmosphere_type="None", radius=2_400_000)}
        guide = self.guide()
        self.assertEqual(guide["stage"], "fly")
        self.assertEqual(guide["info"]["class"], "High metal content body")
        self.assertEqual((guide["info"]["ls"], guide["info"]["gravity"], guide["info"]["atmosphere"]), (1834.2, .38, ""))
        self.assertEqual([row["short"] for row in guide["bodies"]], ["A", "4", "4 A"], "by distance from the arrival star")
        self.assertEqual([row["target"] for row in guide["bodies"]], [False, False, True])
        self.deck.current_body_name = BODY
        self.deck.on_planet = True
        self.deck.current_latitude, self.deck.current_longitude, self.deck.current_heading = -20.0, 110.0, 90.0
        self.deck.current_planet_radius = 2_400_000
        self.assertEqual(self.guide()["stage"], "land")
        self.deck.current_landed = True
        self.assertEqual(self.guide()["stage"], "ground")
        self.deck.current_latitude, self.deck.current_longitude = -23.45, 114.08
        self.assertEqual(self.guide()["stage"], "arrived")

    def test_edsm_body_facts_arrive_before_the_ship_and_footfall_is_qualified(self):
        class EDSM:
            callback = None

            def fetch_system_bodies(self, system, callback):
                self.system = system
                self.callback = callback

        edsm = EDSM()
        self.deck.edsm = edsm
        guide = self.guide()
        self.assertEqual(guide["stage"], "jump")
        self.assertIsNone(guide["info"], "the lookup is asynchronous")
        self.assertEqual(edsm.system, SYSTEM)

        edsm.callback({"name": SYSTEM, "bodies": [{
            "bodyId": 4, "name": BODY, "type": "Planet", "subType": "High metal content body",
            "distanceToArrival": 1834.2, "gravity": .38, "surfaceTemperature": 412,
            "atmosphereType": "None", "isLandable": True, "wasFootfalled": False,
        }]})
        guide = self.guide()
        self.assertEqual(guide["stage"], "jump")
        self.assertEqual((guide["info"]["class"], guide["info"]["ls"], guide["info"]["gravity"],
                          guide["info"]["temp"], guide["info"]["source"], guide["info"]["footfall"]),
                         ("High metal content body", 1834.2, .38, 412, "EDSM", "LIKELY OPEN"))

    def test_route_intel_cache_uses_the_planned_route_not_live_position(self):
        from unittest.mock import patch

        self.deck._expedition_worker = lambda _name, work, done: done(work(), None)
        expedition = {
            "id": "route-cache-test", "start_system": "Sol", "stats": {"start_pos": [0, 0, 0]},
            "legs": [{"system": "Destination", "coords": [100, 0, 0], "plot": {}}],
        }
        response = {"results": [{
            "system": "Near Route", "body": "Near Route 1", "coords": [50, 10, 0], "distance": 30,
            "landable": True, "first_footfall": False, "biological_count": 2,
            "atmosphere": "Thin Ammonia", "mapping_value": 800_000,
        }]}
        with patch("voidcompass.services.spansh.exploration_body_search", return_value=response) as search:
            self.deck._expedition_route_intel(expedition)
            self.deck.current_coords = [10, 0, 0]
            cached = self.deck._expedition_route_intel(expedition)

        search.assert_called_once_with("Destination", "route", 150, 1, 80)
        self.assertFalse(cached["waiting"])
        self.assertEqual(cached["rows"][0]["system"], "Near Route")

    def test_a_system_stop_is_jump_then_arrive(self):
        self.legs = [{"id": "b", "system": "Colonia", "kind": "destination"}]
        self.assertEqual(self.guide()["stage"], "jump")
        self.assertIsNone(self.guide()["jumps"], "no route plotted there")
        self.deck.current_sys = "Colonia"
        self.assertEqual(self.guide()["stage"], "arrived")

    def test_every_leg_reached_is_no_guide(self):
        self.legs[0]["reached"] = True
        self.assertIsNone(self.guide())

    def test_short_names_and_facts(self):
        self.assertEqual(_short_body(BODY, SYSTEM), "4 A")
        self.assertEqual(_short_body("Pleione A 1", "Sol"), "PLEIONE A 1", "another system's body keeps its name")
        facts = _body_facts({"planet_class": "Icy body", "atmosphere_type": "Thin Neon", "gravity_g": "0.12", "rings": [{"Name": "x"}]})
        self.assertEqual((facts["atmosphere"], facts["gravity"], facts["rings"], facts["ls"]), ("Thin Neon", .12, True, None))

    def test_the_overlay_model_carries_it(self):
        exp, live = json.loads(json.dumps(EXPEDITION_SAMPLE))
        live["guide"] = {"stage": "fly", "short": "4 A"}
        self.assertEqual(build_expedition_model(exp, live)["guide"]["stage"], "fly")


class OverlayPageTests(unittest.TestCase):
    """Every step draws, and fits at large text."""

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

    def test_each_step_draws(self):
        web = ROOT / "web"
        stub = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
                " window.renderIt = options.render; return {rerender() {}}; }};")
        info = {"class": "High metal content body", "ls": 1834, "gravity": 2.6, "temp": 412, "landable": True, "atmosphere": "", "rings": True}
        bodies = [{"short": "A", "ls": 0, "star": True, "class": "K", "target": False},
                  {"short": "4 A", "ls": 1834, "star": False, "class": "High metal content body", "target": True}]
        base = {"system": SYSTEM, "body": BODY, "short": "4 A", "title": "The Crystal Arches", "kind": "stop", "lat": -23.45, "lon": 114.08,
                "jumps": 3, "info": info, "bodies": bodies}
        expected = {"jump": "JUMP TO", "fly": "FLY TO", "land": "LAND ON", "ground": "ON THE GROUND", "arrived": "YOU'RE HERE"}
        for stage, words in expected.items():
            with self.subTest(stage=stage):
                exp, live = json.loads(json.dumps(EXPEDITION_SAMPLE))
                live["guide"] = {**base, "stage": stage}
                model = build_expedition_model(exp, live)
                page = self.browser.new_page(viewport={"width": 570, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def serve(route):
                    file = web / urlsplit(route.request.url).path.lstrip("/")
                    if not file.is_file():
                        return route.fulfill(status=404, body="")
                    if file.name == "overlay-client.js":
                        return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + stub)
                    return route.fulfill(path=str(file))

                page.route("http://e.test/**", serve)
                page.goto("http://e.test/expedition/index.html")
                page.wait_for_function("typeof window.renderIt === 'function'")
                page.evaluate("m => renderIt({theme: {}, effects: {text_scale: 1.5}, expedition: m})", model)
                self.assertTrue(page.inner_text("#target-step").startswith(words))
                self.assertEqual(page.locator("#steps li.now").count(), 1)
                self.assertEqual(page.is_visible("#compass"), stage in {"land", "ground"})
                self.assertEqual(page.is_visible("#strip"), stage == "fly")
                if stage == "fly":
                    self.assertIn("2.60 G", page.inner_text("#facts"))
                    self.assertIn("TARGET 4 A IN THE NAV PANEL", page.inner_text("#hint"))
                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                self.assertFalse(overflow, "fits the window at 150% text")
                self.assertEqual(errors, [])
                page.close()


if __name__ == "__main__":
    unittest.main()
