"""5.5.12: Planetary operations as one page. ON THE GROUND (compass, field
map, the planet), EXOBIOLOGY (the planet's biology as Survey Operations
reads it, the sample you're on, the system's biology, unsold value) and
SITES (saved surface sites, heat map, by material)."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlsplit

from voidcompass.dashboard.html_planetary import HtmlPlanetaryMixin
from voidcompass.exploration import bio_values

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = "Synuefe AA-A h1"


def planet(body_id, name, temp, gravity, bio, scans=None, first=False):
    return {"body_id": body_id, "name": name, "planet_class": "Rocky body", "atmosphere_type": "Thin Carbon dioxide",
            "surface_temp": temp, "gravity_g": gravity, "volcanism": "", "landable": True, "bio_count": bio,
            "first_footfall": first, "organic_scans": scans or {},
            "organic_complete_count": sum(1 for row in (scans or {}).values() if row.get("is_complete")),
            "predicted_genuses": bio_values.predict_genera("Rocky body", "Thin Carbon dioxide", temp, gravity, "", 0.01)}


ITEMS = [
    planet(5, f"{SYSTEM} 3 a", 190, 0.12, 3, {
        "a": {"species": "Bacterium Aurasus", "genus": "Bacterium", "sample_idx": 3, "is_complete": True},
        "b": {"species": "Stratum Tectonicas", "genus": "Stratum", "sample_idx": 1, "is_complete": False}}, first=True),
    planet(6, f"{SYSTEM} 3 b", 175, 0.08, 2),
]


class Deck(HtmlPlanetaryMixin):
    def __init__(self, codex=None, sampling=True):
        self.config = {"survey_codex_flags": codex is not None}
        self.current_sys = SYSTEM
        self.current_body_name = f"{SYSTEM} 3 a"
        self.scan_items = ITEMS
        self.body_signals = {}
        self.bio_sampling = {"species": "Stratum Tectonicas", "genus": "Stratum", "body": 5, "progress": 1, "colony_m": 500} if sampling else None
        self.companion_state = {"unsold_bio_cr": 21_500_000, "unsold_bio_bonus_potential_cr": 86_000_000}
        if codex is not None:
            self._survey_codex_lookup = codex
            self._survey_codex_variants = lambda body_id: {}

    def _sampling_snapshot(self):
        return {**self.bio_sampling, "min_distance_m": 320, "clear": False}

    def _html_ground_workspace(self):
        return {"field_map": {"body": f"{SYSTEM} 3 a"}}


class MapDeck(HtmlPlanetaryMixin):
    """Ship at 10 N 20 E on a 1,000 km world: 0.01 degrees is about 175 m."""
    def __init__(self, target_body=""):
        self.current_planet_radius = 1_000_000
        self.current_body_name = "Moon A"
        self.on_planet = True
        self.current_latitude, self.current_longitude, self.current_heading = 10.01, 20.0, 90
        self.surface_ship_position = {"lat": 10.0, "lon": 20.0}
        self.surface_trail = [{"lat": 10.0, "lon": 20.0}, {"lat": 10.005, "lon": 20.0}]
        self.target_latlon_active, self.target_lat, self.target_lon = True, 10.0, 20.01
        self.ground_target_body, self.ground_target_label = target_body, "Spot"
        self.specialist_engine = Mock(exobiology_snapshot=lambda: {
            "sampling": {"sample_group": "g", "colony_m": 100},
            "current_map": {"body": "Moon A", "pins": [
                {"id": "s", "kind": "organic_sample", "label": "Stratum", "lat": 10.0, "lon": 19.99, "source": "ScanOrganic",
                 "metadata": {"sample_group": "g", "progress": 2}},
                {"id": "m", "kind": "waypoint", "label": "Rim", "lat": 9.99, "lon": 20.0, "source": "manual", "metadata": {}}]}})

    def _planet_materials_store(self):
        return Mock(rows=lambda: [{"id": 1, "name": "Here", "body": "Moon A", "latitude": 10.0, "longitude": 20.0},
                                  {"id": 2, "name": "Elsewhere", "body": "Moon B", "latitude": 1.0, "longitude": 1.0}])


class MapTests(unittest.TestCase):
    def test_everything_in_one_frame_from_the_ship(self):
        surface = MapDeck()._planetary_map()
        self.assertEqual(surface["ship"]["at"], [0.0, 0.0])
        east, north = surface["you"]["at"]
        self.assertAlmostEqual(north, 174.5, delta=0.5, msg="0.01 degrees north")
        self.assertAlmostEqual(east, 0.0, delta=0.1)
        self.assertEqual(surface["you"]["heading"], 90)
        self.assertEqual(surface["trail"][-1], surface["you"]["at"], "the trail runs to where you are now")
        target_east, _ = surface["target"]["at"]
        self.assertAlmostEqual(target_east, 174.5 * __import__("math").cos(__import__("math").radians(10)), delta=0.5)
        pins = {pin["id"]: pin for pin in surface["pins"]}
        self.assertLess(pins["s"]["at"][0], 0, "west of the ship")
        self.assertEqual((pins["s"]["group"], pins["s"]["progress"], pins["s"]["lat"]), ("g", 2, 10.0))
        self.assertTrue(pins["m"]["manual"])
        self.assertEqual([site["label"] for site in surface["sites"]], ["Here"], "only this planet's sites")
        self.assertEqual(surface["sampling"]["colony_m"], 100)

    def test_a_target_on_another_planet_isnt_drawn(self):
        self.assertIsNone(MapDeck(target_body="Moon B")._planetary_map()["target"])

    def test_nothing_to_draw_without_a_planet(self):
        deck = MapDeck()
        deck.current_planet_radius = None
        deck.specialist_engine = Mock(exobiology_snapshot=lambda: {})
        self.assertIsNone(deck._planetary_map())


class ExobiologyTests(unittest.TestCase):
    def test_the_planet_you_are_on(self):
        exo = Deck()._planetary_exobiology({"field_map": {"body": f"{SYSTEM} 3 a"}})
        here = exo["here"]
        kinds = [row["kind"] for row in here["rows"]]
        self.assertEqual(kinds[:2], ["complete", "sample"], "what you've done first")
        self.assertTrue(set(kinds[2:]) <= {"detected", "predicted", "possible"})
        self.assertEqual((here["bio_count"], here["complete"], here["first_footfall"]), (3, 1, True))
        aurasus = next(row for row in here["rows"] if row["name"] == "Bacterium Aurasus")
        self.assertEqual(aurasus["value"], bio_values.species_value("Bacterium Aurasus") * bio_values.FIRST_LOGGED_MULTIPLIER,
                         "first footfall pays five times")
        self.assertGreater(here["max_value"], here["min_value"])

    def test_the_sample_you_are_on_and_whats_aboard(self):
        exo = Deck()._planetary_exobiology({})
        self.assertEqual((exo["sampling"]["species"], exo["sampling"]["min_distance_m"]), ("Stratum Tectonicas", 320))
        self.assertEqual(exo["unsold"], 107_500_000)
        self.assertEqual(exo["unsold_base"], 21_500_000)
        self.assertIsNone(Deck(sampling=False)._planetary_exobiology({})["sampling"])

    def test_the_systems_biology(self):
        rows = Deck()._planetary_exobiology({})["system_bodies"]
        self.assertEqual([row["full_name"] for row in rows if row["here"]], [f"{SYSTEM} 3 a"])
        self.assertEqual({row["bio_count"] for row in rows}, {3, 2})

    def test_codex_flags_as_on_survey_operations(self):
        flagged = lambda kind, key, body_id: "new"
        exo = Deck(codex=flagged)._planetary_exobiology({})
        self.assertTrue(exo["codex_flags"])
        self.assertIn("new", {row["codex"] for row in exo["here"]["rows"]})
        self.assertFalse(Deck()._planetary_exobiology({})["codex_flags"], "off when Survey's codex flags are off")

    def test_nothing_breaks_the_page(self):
        deck = Deck()
        deck._html_ground_workspace = lambda: 1 / 0
        extras = deck._planetary_extras()
        self.assertEqual(extras["ground"], {})
        self.assertIn("system_bodies", extras["exobiology"])

    def test_only_the_page_pays_for_it(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('"planet-materials": lambda: {**self._html_planet_materials_workspace(), **self._planetary_extras()}', source)
        overlay = source.split("def _refresh_planet_materials_overlay", 1)[1].split("\n    def ", 1)[0]
        self.assertNotIn("_planetary_extras", overlay, "the overlay refreshes often and needs none of it")


def page_data():
    ground = {
        "system": SYSTEM, "body": f"{SYSTEM} 3 a", "on_planet": True,
        "position": {"lat": 12.4, "lon": -45.1, "heading": 212},
        "target": {"active": True, "lat": 12.43, "lon": -45.08, "popup": True, "bearing": 38, "distance": 1240, "heading_delta": 64, "label": "Patch"},
        "elite_target": {"name": f"{SYSTEM} 3 a", "is_current_body": True},
        "trail": {"travelled": 3820, "return_distance": 610, "return_bearing": 191, "points": []},
        "field_map": {"body": f"{SYSTEM} 3 a", "heading": 212, "sampling": {"colony_m": 500},
                      "pins": [{"id": "m1", "kind": "waypoint", "label": "Crater rim", "east": -320, "north": 420, "distance": 540, "bearing": 322, "manual": True, "metadata": {}},
                               {"id": "s1", "kind": "organic_sample", "label": "Stratum 1/3", "east": 260, "north": 180, "distance": 320, "bearing": 140, "manual": False, "metadata": {}}]},
    }
    return {
        "profile_key": "p", "on_planet": True, "system": SYSTEM,
        "current_position": {"latitude": 12.4, "longitude": -45.1, "body": f"{SYSTEM} 3 a", "system": SYSTEM, "planet_radius": 1100000,
                             "body_details": {"class": "Rocky body", "gravity": 0.12, "materials": [{"name": "Iron", "percent": 21.4}]}},
        "bodies": [{"body": f"{SYSTEM} 3 a", "system": SYSTEM, "class": "Rocky body"}],
        "sites": [{"id": 1, "system": "Ba Po", "body": "Ba Po C 3", "name": "Site 3", "latitude": 12.5, "longitude": -45.0, "materials": "Platinum", "body_details": {"class": "Metal rich body"}}],
        "mining_catalogue": ["Platinum"], "new_mining_materials": [],
        "navigation_target": {"active": False},
        "ground": ground, "exobiology": Deck()._planetary_exobiology(ground),
        "map": MapDeck()._planetary_map(),
    }


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        from tests.test_dashboard_overview_visuals import overview_state
        cls.overview = overview_state()
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

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1400, "height": 1000})
        self.errors, self.sent = [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        web = ROOT / "web"
        harness = """
          window.__planet = (data) => { model.workspace = {page: 'planet-materials', ready: true, data}; workspaceFingerprints['planet-materials'] = ''; renderWorkspace(model); };
          window.__render = (data) => { model = data; applyTheme(data.theme || {}); document.body.classList.add('ready'); document.getElementById('boot').hidden = true; renderDashboard(data); };
          window.__show = (name) => showPage(name);"""

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                return route.fulfill(content_type="application/json", body='{"closing":true}')
            if path == "/api/command":
                self.sent.append(json.loads(route.request.post_data or "{}"))
                return route.fulfill(content_type="application/json", body='{"accepted":true}')
            if path == "/api/snapshot":
                return route.fulfill(content_type="application/json", body=json.dumps(self.overview))
            file = web / path.lstrip("/")
            if path == "/dashboard/app.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + harness)
            if file.is_file():
                return route.fulfill(path=str(file))
            route.fulfill(status=404, body="")

        self.page.route("http://planet.test/**", serve)
        self.page.goto("http://planet.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__planet)")
        self.page.evaluate("data => window.__render(data)", self.overview)
        self.page.evaluate("() => window.__show('ground')")
        self.page.evaluate("data => window.__planet(data)", page_data())

    def tearDown(self):
        self.page.close()

    def workspace_ops(self):
        return [(row.get("page"), row.get("operation")) for row in self.sent if row.get("action") == "workspace"]

    def test_the_old_ground_page_opens_on_the_ground(self):
        self.assertTrue(self.page.evaluate("() => document.querySelector('.page[data-page-name=\"planet-materials\"]').classList.contains('active')"))
        self.assertEqual(self.page.inner_text(".po-tabs button.active").strip(), "ON THE GROUND")

    def test_every_tab_draws_and_fits(self):
        for width in (1400, 980):
            self.page.set_viewport_size({"width": width, "height": 1000})
            for tab in ("ground", "exobio", "sites"):
                with self.subTest(width=width, tab=tab):
                    self.page.click(f'[data-po-op="view"][data-view="{tab}"]')
                    fits = self.page.evaluate("() => { const p = document.querySelector('.page[data-page-name=\"planet-materials\"]'); return p.scrollWidth <= p.clientWidth + 1; }")
                    self.assertTrue(fits)
        self.page.click('[data-po-op="view"][data-view="exobio"]')
        text = self.page.inner_text("#planet-materials-workspace")
        self.assertIn("Move 180 m further", text)
        self.assertIn("Bacterium Aurasus", text)
        self.assertIn("107.5M CR", text)
        self.assertFalse(self.errors, self.errors)

    def test_the_compass_uses_the_decks_ground_commands(self):
        self.page.fill("#ground-lat", "10.5")
        self.page.fill("#ground-lon", "-20.25")
        self.page.click('[data-ws-page="ground"][data-ws-op="set"]')
        self.page.wait_for_timeout(200)
        sent = next(row for row in self.sent if row.get("operation") == "set")
        self.assertEqual((sent["page"], sent["lat"], sent["lon"]), ("ground", "10.5", "-20.25"))
        self.page.fill("#field-marker-label", "Lone tree")
        self.page.click('[data-ws-op="add_pin"]')
        self.page.wait_for_timeout(200)
        self.assertEqual(next(row for row in self.sent if row.get("operation") == "add_pin")["label"], "Lone tree")

    def test_save_this_spot_and_add_the_site(self):
        self.page.click('[data-po-op="save_spot"]')
        form = "form[data-new-site]"
        self.assertEqual(self.page.input_value(f"{form} [name=latitude]"), "12.4")
        self.assertEqual(self.page.input_value(f"{form} [name=body]"), f"{SYSTEM} 3 a")
        self.page.fill(f"{form} [name=name]", "Bacteria field")
        self.page.fill(f"{form} [name=materials]", "Iron")
        self.page.click(f"{form} button[type=submit]")
        self.page.wait_for_timeout(200)
        save = next(row for row in self.sent if row.get("operation") == "save")
        self.assertEqual((save["page"], save["name"], save["latitude"]), ("planet-materials", "Bacteria field", "12.4"))

    def test_an_unsaved_site_edit_survives_a_redraw(self):
        self.page.click('[data-po-op="view"][data-view="sites"]')
        self.page.select_option("[data-po-planet]", index=0)
        self.page.click("details[data-site-id='1'] summary span b")
        self.page.fill("details[data-site-id='1'] [name=notes]", "half typed")
        self.page.evaluate("() => document.activeElement.blur()")
        moved = page_data()
        moved["ground"]["position"]["lat"] = 12.41
        self.page.evaluate("data => window.__planet(data)", moved)
        self.assertEqual(self.page.input_value("details[data-site-id='1'] [name=notes]"), "half typed")
        self.page.click("[data-site-navigate='1']")
        self.page.wait_for_timeout(200)
        self.assertIn(("planet-materials", "navigate_site"), self.workspace_ops())

    def test_the_map_steers_the_compass(self):
        self.page.click('[data-po-op="view"][data-view="ground"]')
        self.assertTrue(self.page.locator(".po-surface svg .you").count())
        self.page.locator(".po-surface .feat.marker").click(force=True)
        self.page.wait_for_timeout(200)
        sent = next(row for row in self.sent if row.get("operation") == "set")
        self.assertEqual((sent["page"], sent["lat"], sent["lon"]), ("ground", "9.99", "20"))
        self.assertFalse(self.errors, self.errors)

    def test_the_ship_on_the_map_takes_you_back(self):
        self.page.click('[data-po-op="view"][data-view="ground"]')
        self.page.locator(".po-surface .feat.ship path").click(force=True)
        self.page.wait_for_timeout(200)
        self.assertIn(("ground", "return_ship"), self.workspace_ops())

    def test_fit_all_around_me_and_zoom(self):
        self.page.click('[data-po-op="view"][data-view="ground"]')
        self.page.click('[data-po-op="map_mode"][data-mode="me"]')
        self.page.click('[data-po-op="map_zoom"][data-step="1.6"]')
        self.assertIn("active", self.page.get_attribute('[data-po-op="map_mode"][data-mode="me"]', "class"))
        self.assertTrue(self.page.locator(".po-surface .scale").count())
        self.assertFalse(self.errors, self.errors)

    def test_arrows_are_arrowheads(self):
        for name in ("planetary.js", "mining.js"):
            source = (ROOT / "web" / "dashboard" / name).read_text(encoding="utf-8")
            self.assertNotIn(">▲<", source, f"{name}: a triangle turned 60 degrees reads as pointing back")
        self.assertTrue(self.page.locator(".po-needle svg").count())


if __name__ == "__main__":
    unittest.main()
