"""5.5.3: the Cargo overlay lists the hold alphabetically, so a commodity is
always in the same place (stolen and mission cargo keep their tags)."""

import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.overlays.cargo_hud import build_cargo_model

WEB = Path(__file__).resolve().parents[1] / "web"


class CargoOrderTests(unittest.TestCase):
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

    def test_the_hold_is_alphabetical(self):
        page = self.browser.new_page(viewport={"width": 420, "height": 700})
        self.addCleanup(page.close)

        def serve(route, _request=None):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8")
                              + "\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: o => {"
                              " window.__render = o.render; }};")
            elif path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")

        page.route("http://cargo.test/**", serve)
        page.goto("http://cargo.test/cargo/index.html")
        page.wait_for_function("Boolean(window.__render)")
        model = build_cargo_model([
            {"Name": "tritium", "Name_Localised": "Tritium", "Count": 300},
            {"Name": "gold", "Name_Localised": "Gold", "Count": 4, "Stolen": 4},
            {"Name": "agronomictreatment", "Name_Localised": "Agronomic Treatment", "Count": 12, "MissionID": 9},
            {"Name": "bauxite", "Name_Localised": "Bauxite", "Count": 50},
        ], capacity=400)
        page.evaluate("m => __render({cargo: m, theme: {}, effects: {reduced_motion: true}})", model)
        names = page.evaluate("""() => [...document.querySelectorAll('article[data-key]')]
            .map(row => row.dataset.key)""")
        self.assertEqual([name.split(":")[-1] for name in names][:4],
                         ["agronomic treatment", "bauxite", "gold", "tritium"])


if __name__ == "__main__":
    unittest.main()
