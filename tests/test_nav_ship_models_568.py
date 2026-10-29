"""5.6.8: the Navigation HUD's state scenes fly the commander's own ship.

Every ship in the catalogue has its own hologram model in the shared
web/assets/ship-models.js, built from the feel of its portrait. The scene's
hero is the ship the journal says you are in; other traffic, pirates and the
fighter keep their own hulls, and a ship without a model falls back cleanly.
"""

import unittest
from itertools import combinations
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tests.test_navigation_state_visuals import SHIP_ART, hud_snapshot, hud_state

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class ShipModelTests(unittest.TestCase):
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

    def open(self):
        page = self.browser.new_page(viewport={"width": 500, "height": 350})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = SHIP_ART / path[len("/ship-art/"):] if path.startswith("/ship-art/") else WEB / path.lstrip("/")
            route.fulfill(path=str(target)) if target.is_file() else route.fulfill(status=404, body="")

        page.route("http://ships.test/**", serve)
        page.goto("http://ships.test/navigation_hud/index.html")
        page.wait_for_function("Boolean(window.navigationScene)")
        return page

    def render(self, page, label, symbol):
        state = hud_state(label)
        state["vehicle"].update(ship_symbol=symbol, ship_type=symbol)
        page.evaluate("snapshot => render(snapshot)", hud_snapshot(state, reduced=True))

    def hero(self, page):
        return page.evaluate("""() => {
          const surface = navigationScene.surfaces.find(s => s.role === 'deck');
          return surface.get(navigationScene.state, navigationScene.palette).hero?.userData.type || null;
        }""")

    def test_every_catalogue_ship_has_a_well_formed_model(self):
        page = self.open()
        report = page.evaluate("""() => window.VoidCompassShipCatalog.ships.map(ship => {
          const key = ship.name.toLowerCase().replace(/[^a-z0-9]/g, '');
          const model = window.ShipModels.get(key), faults = [];
          if (!model) return [ship.name, key, null];
          model.f.forEach((face, index) => {
            if (face.i.length < 3) faults.push(`face ${index} has ${face.i.length} corners`);
            if (face.i.some(vertex => !Array.isArray(model.v[vertex]))) faults.push(`face ${index} misses a vertex`);
            if (typeof face.k !== 'string') faults.push(`face ${index} has no kind`);
          });
          if (!model.v.every(v => v.length === 3 && v.every(Number.isFinite))) faults.push('bad vertex');
          const kinds = new Set(model.f.map(face => face.k));
          const xs = model.v.map(v => v[0]);
          return [ship.name, key, {faces: model.f.length, faults, engine: kinds.has('engine'),
            canopy: kinds.has('glass') || kinds.has('window'),
            // Nose to +x: the drive glow sits behind the hull's middle.
            drivesAft: model.f.filter(face => face.k === 'engine')
              .every(face => face.i.reduce((sum, i) => sum + model.v[i][0], 0) / face.i.length < (Math.min(...xs) + Math.max(...xs)) / 2)}];
        })""")
        self.assertGreaterEqual(len(report), 49)
        for name, key, result in report:
            with self.subTest(ship=name):
                self.assertIsNotNone(result, f"no model for {key}")
                self.assertGreater(result["faces"], 10)
                self.assertEqual(result["faults"], [])
                self.assertTrue(result["engine"], "no drive glow")
                self.assertTrue(result["canopy"], "no canopy or windows")
                self.assertTrue(result["drivesAft"], "drives not at the stern")

    def test_ships_have_their_own_shapes(self):
        page = self.open()
        shapes = page.evaluate("""() => Object.fromEntries(window.ShipModels.keys.map(key => {
          const model = window.ShipModels.get(key);
          return [key, JSON.stringify(model.v.map(v => v.map(n => Math.round(n * 100))))];
        }))""")
        for left, right in combinations(shapes, 2):
            with self.subTest(left=left, right=right):
                self.assertNotEqual(shapes[left], shapes[right])
        self.assertTrue(page.evaluate("window.ShipModels.has('fighter') && window.ShipModels.has('Type-9 Heavy')"))

    def test_the_hero_is_the_commanders_own_ship(self):
        page = self.open()
        frames = {}
        for symbol, key in (("Anaconda", "anaconda"), ("SideWinder", "sidewinder"), ("Krait_MkII", "kraitmkii")):
            with self.subTest(ship=symbol):
                self.render(page, "SUPERCRUISE", symbol)
                self.assertEqual(page.evaluate("navigationScene.state.shipKey"), key)
                self.assertEqual(self.hero(page), key)
                frames[key] = page.evaluate("document.getElementById('deck-canvas').toDataURL()")
        self.assertEqual(len(set(frames.values())), 3, "each ship draws its own scene")
        # The scene follows a ship swap without a state change.
        self.render(page, "SUPERCRUISE", "Anaconda")
        self.assertEqual(self.hero(page), "anaconda")

    def test_named_craft_and_unknown_ships_keep_their_hulls(self):
        page = self.open()
        self.render(page, "FIGHTER", "Anaconda")
        self.assertEqual(self.hero(page), "fighter")
        self.render(page, "TAXI", "Anaconda")
        self.assertEqual(self.hero(page), "taxi")
        # A ship the catalogue does not know yet still gets a scene.
        self.render(page, "SUPERCRUISE", "SomeFutureShip")
        self.assertEqual(page.evaluate("navigationScene.state.shipKey"), "")
        self.assertEqual(page.evaluate("navigationScene.renderer"), "three")
        self.assertEqual(self.hero(page), "ship")


if __name__ == "__main__":
    unittest.main()
