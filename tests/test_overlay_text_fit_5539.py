"""Prospector, Cargo and Planet Materials at large text (5.5.3.9): the page's columns grow with
the text size as the window does, so nothing is cut off at 150% or 200%."""
from __future__ import annotations

from pathlib import Path
import unittest
from urllib.parse import urlsplit

from voidcompass.overlays.cargo_hud import build_cargo_model
from voidcompass.overlays.planet_materials_hud import build_planet_materials_model
from voidcompass.overlays.prospector_hud import build_prospector_model

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderIt = options.render; window.measure = options.contentHeight; return {rerender() {}}; }};")
THEME = {"bg": "#070b10", "panel": "#0d141c", "accent": "#00d1ff", "orange": "#ff7a18", "text": "#dce8ef",
         "green": "#4ee59b", "yellow": "#ffd166", "red": "#ff6075", "muted": "#85939d", "dim": "#52616c"}

PROSPECTED = {"event": "ProspectedAsteroid", "Content": "$AsteroidMaterialContent_High;", "MotherlodeMaterial": "Painite",
              "Remaining": 100.0, "Materials": [
                  {"Name": "platinum", "Name_Localised": "Platinum", "Proportion": 31.2},
                  {"Name": "praseodymium", "Name_Localised": "Praseodymium", "Proportion": 9.9},
                  {"Name": "lowtemperaturediamond", "Name_Localised": "Low Temperature Diamonds", "Proportion": 6.1}]}
HOLD = [{"Name": "lowtemperaturediamond", "Name_Localised": "Low Temperature Diamonds", "Count": 212},
        {"Name": "hydrogenfuel", "Name_Localised": "Hydrogen Fuel", "Count": 12, "Stolen": 2}]

BODY = "Synuefe XX-A d1-58 AB 3 a"
WORKSPACE = {"system": "Synuefe XX-A d1-58", "body": BODY, "on_planet": True,
             "bodies": [{"body": BODY, "short_name": "AB 3 a", "class": "High metal content world",
                         "volcanism": "Minor metallic magma volcanism", "gravity": 0.31, "temperature": 182, "landable": True,
                         "mining_locations": 4, "ground_label": "Metallic rocky ground", "ground_sample": 3,
                         "materials": [{"name": "Ruthenium", "percent": 1.9, "rare": True}, {"name": "Iron", "percent": 21.4}],
                         "best_materials": [{"material": "Low Temperature Diamonds", "pct": 42.0, "median": 12}]}],
             "sites": [{"id": 1, "system": "Synuefe XX-A d1-58", "body": BODY, "name": "Ridge seam", "density": "Medium",
                        "amount": "Medium", "materials": "Painite", "latitude": 10.1, "longitude": -44.0}],
             "navigation_target": {}}

# (page, model key, model, design width, min height, max height)
OVERLAYS = (
    ("prospector", "prospector", build_prospector_model(PROSPECTED, {"Platinum": 12}), 400, 180, 560),
    ("cargo", "cargo", build_cargo_model(HOLD, 320, "Ship", "Mandalay"), 410, 190, 760),
    ("planet-materials-overlay", "planet_materials",
     build_planet_materials_model(WORKSPACE, latitude=11.9, longitude=-45.1, heading=212, radius_m=2400000, vehicle_name="Rhino"),
     440, 190, 680),
)


class LargeTextFitTests(unittest.TestCase):
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

    def test_nothing_cut_off_at_large_text(self):
        for name, key, model, width, low, high in OVERLAYS:
            for scale in (1.0, 1.5, 2.0):
                with self.subTest(overlay=name, scale=scale):
                    page = self.browser.new_page(viewport={"width": round(width * scale), "height": 1600})
                    self.addCleanup(page.close)

                    def serve(route):
                        file = WEB / urlsplit(route.request.url).path.lstrip("/")
                        if not file.is_file():
                            route.fulfill(status=404, body="")
                        elif file.name == "overlay-client.js":
                            route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
                        else:
                            route.fulfill(path=str(file))
                    page.route("http://fit.test/**", serve)
                    page.goto(f"http://fit.test/{name}/index.html?token=t&overlay={name}")
                    page.wait_for_function("Boolean(window.renderIt)")
                    page.evaluate(f"([m, t, s]) => renderIt({{theme: t, effects: {{text_scale: s}}, {key}: m}})", [model, THEME, scale])
                    measured = page.evaluate("measure()")
                    # The window the app gives it: design size times the text size.
                    page.set_viewport_size({"width": round(width * scale),
                                            "height": max(round(low * scale), min(round(high * scale), measured))})
                    cut = page.evaluate("""() => [...document.querySelectorAll('body strong, body span, body b, body small')]
                      .filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1)
                      .map(el => el.textContent.trim()).filter(Boolean)""")
                    self.assertEqual(cut, [], "no text cut short")
                    wide = page.evaluate("document.documentElement.scrollWidth")
                    self.assertLessEqual(wide, round(width * scale) + 1, "nothing past the window's edge")

    def test_fits_a_window_drawn_at_another_scale(self):
        """Windows draws the page at another scale than the window was sized
        for: the page fits itself to the window, and every row still shows."""
        for name, key, model, width, low, high in OVERLAYS:
            for drawn in (1.25, 1.5):
                with self.subTest(overlay=name, drawn=drawn):
                    page = self.browser.new_page(viewport={"width": round(width / drawn), "height": 1600})
                    self.addCleanup(page.close)

                    def serve(route):
                        file = WEB / urlsplit(route.request.url).path.lstrip("/")
                        if not file.is_file():
                            route.fulfill(status=404, body="")
                        elif file.name == "overlay-client.js":
                            route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
                        else:
                            route.fulfill(path=str(file))
                    page.route("http://fit.test/**", serve)
                    page.goto(f"http://fit.test/{name}/index.html?token=t&overlay={name}")
                    page.wait_for_function("Boolean(window.renderIt)")
                    page.evaluate(f"([m, t]) => renderIt({{theme: t, effects: {{text_scale: 1}}, {key}: m}})", [model, THEME])
                    measured = page.evaluate("measure()")
                    # The app's window, in the page's own (larger) pixels.
                    page.set_viewport_size({"width": round(width / drawn), "height": round(max(low, min(high, measured)) / drawn)})
                    page.wait_for_timeout(50)
                    cut = page.evaluate("""() => [...document.querySelectorAll('body strong, body span, body b, body small')]
                      .filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1)
                      .map(el => el.textContent.trim()).filter(Boolean)""")
                    self.assertEqual(cut, [], "no text cut short")
                    below = page.evaluate("""() => [...document.querySelectorAll('body *')]
                      .filter(el => el.getClientRects().length && el.getBoundingClientRect().bottom > innerHeight + 2)
                      .map(el => el.tagName + '.' + el.className)""")
                    self.assertEqual(below, [], "every row inside the window")


if __name__ == "__main__":
    unittest.main()
