"""Pet-only needs are real, readable warnings, not a permanent test label."""

import unittest
from urllib.parse import urlsplit

from tests.test_hatchling_563 import HOUR, ROOT, hatched
from voidcompass.core.hatchling import view
from voidcompass.overlays.hatchling_hud import build_hatchling_model, hatchling_overlay_options


class PetOnlyNeedWarnings(unittest.TestCase):
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

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 294, "height": 258})
        self.addCleanup(self.page.close)
        self.page.add_init_script("""(() => {
          window.drawnText = [];
          const original = CanvasRenderingContext2D.prototype.fillText;
          CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
            if (this.canvas.id === 'roam') window.drawnText.push(String(text));
            return original.call(this, text, ...args);
          };
        })();""")
        stub = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
                " window.renderPet = options.render; return {rerender() {}}; }};")

        def serve(route):
            file = ROOT / "web" / urlsplit(route.request.url).path.lstrip("/")
            if not file.is_file():
                return route.fulfill(status=404, body="")
            if file.name == "overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + stub)
            return route.fulfill(path=str(file))

        self.page.route("http://needs.test/**", serve)
        self.page.goto("http://needs.test/hatchling/index.html")
        self.page.wait_for_function("typeof window.renderPet === 'function'")

    def draw(self, model):
        self.page.evaluate("m => { window.drawnText = []; renderPet({hatchling: m}); }", model)
        self.page.wait_for_timeout(150)
        return self.page.evaluate("window.drawnText")

    def model(self, species="bot", needs="low"):
        options = hatchling_overlay_options({"hatchling_look": "pet", "hatchling_needs": needs,
                                             "hatchling_speech": False})
        model = build_hatchling_model(view(hatched(species), 3 * HOUR), 3 * HOUR, options=options)
        model["needs"] = {"hunger": 18, "clean": 90, "mood": 90, "health": 90, "energy": 90}
        model["wants"] = "POWER" if species == "bot" else "FOOD"
        return model

    def test_low_bot_power_is_live_and_clears_after_feeding_even_if_wants_is_stale(self):
        model = self.model()
        text = self.draw(model)
        self.assertIn("LOW POWER · 18%", text)
        self.assertNotIn("POWER", text)
        model["needs"]["hunger"] = 88
        self.assertFalse(any("POWER" in line for line in self.draw(model)))
        model["wants"] = ""
        self.assertFalse(any("POWER" in line for line in self.draw(model)))
        self.assertFalse(any("POWER" in line for line in self.draw(None)), "no hatchling means no sample warning")

    def test_food_and_urgent_warnings_respect_studio_needs_options(self):
        model = self.model("larva")
        self.assertIn("LOW FOOD · 18%", self.draw(model))
        model["options"]["needs"] = "always"
        self.assertIn("LOW FOOD · 18%", self.draw(model))
        model["options"]["needs"] = "never"
        self.assertNotIn("LOW FOOD · 18%", self.draw(model))
        model["options"]["needs"] = "low"
        model["wants"] = "MEDICINE"
        self.assertIn("MEDICINE", self.draw(model))
        model["wants"] = "REVIVE IT"
        self.assertIn("REVIVE IT", self.draw(model))

    def test_each_species_shows_its_own_food_or_power(self):
        for species, label in (("bot", "LOW POWER"), ("larva", "LOW FOOD"),
                               ("sample", "LOW NUTRIENTS"), ("thargoid", "LOW NOURISHMENT")):
            with self.subTest(species=species):
                model = self.model(species)
                self.assertIn(f"{label} · 18%", self.draw(model))

    def test_other_low_needs_clear_when_their_own_level_recovers(self):
        model = self.model()
        for want, need, warning, threshold in (("PLAY", "mood", "NEEDS PLAY", 35),
                                                ("A CLEAN HOLD", "clean", "NEEDS CLEANING", 35),
                                                ("SLEEP", "energy", "NEEDS SLEEP", 20)):
            with self.subTest(need=need):
                model["wants"] = want
                model["needs"][need] = threshold - 0.1
                self.assertIn(f"{warning} · {threshold - 1}%", self.draw(model))
                model["needs"][need] = threshold
                self.assertFalse(any(warning in line for line in self.draw(model)))


if __name__ == "__main__":
    unittest.main()
