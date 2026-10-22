"""5.5.17: what a planet's ground tends to hold, for the Rhino. EDIntel's
ground mining table (vendored by tools/vendor_ground_mining.py) says, per
kind of ground, how often each material turns up at mining locations and its
price; the Survey page, the HUD's Survey and Planet pages and the Mining page
use it. Also the six scenes redone after the place scenes."""

import importlib.util
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tests.test_navigation_state_visuals import SHIP_ART, hud_snapshot, hud_state
from voidcompass.mining.rhino_intelligence import WORTH_CR, mining_sheet, rhino_forecast, rhino_hint
from voidcompass.overlays import hud_pages as hp

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class SheetTests(unittest.TestCase):
    def test_the_vendored_table(self):
        sheet = mining_sheet()
        self.assertEqual(sheet["generated"], "2026-10-11 14:28 UTC")
        self.assertEqual(len(sheet["grounds"]), 8)
        platinum = next(row for row in sheet["grounds"]["metal-rich"] if row["material"] == "Platinum")
        self.assertEqual((platinum["pct"], platinum["median"]), (46.5, 58000))

    def test_the_vendor_tool_reads_the_page(self):
        spec = importlib.util.spec_from_file_location("vendor", ROOT / "tools" / "vendor_ground_mining.py")
        vendor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vendor)
        page = ("<tbody><tr><td>Diamond</td><td>29.8%</td><td>4.0%</td><td>2.1%</td><td>15.2%</td><td>11.1%</td>"
                "<td></td><td>2.1%</td><td></td><td>108k</td><td>581k</td></tr></tbody> Generated from EDIntel, 2026-10-11 14:28")
        sheet = vendor.parse(page)
        self.assertEqual(sheet["grounds"]["metal-rich"], [{"material": "Diamond", "pct": 29.8, "median": 108000, "best": 581000}])
        self.assertEqual(sheet["grounds"]["rock 80%+ [silicate vapour geysers]"], [], "an empty cell is no signal")
        self.assertEqual(sheet["generated"], "2026-10-11 14:28 UTC")


class ForecastTests(unittest.TestCase):
    def test_best_ground_first_by_what_it_is_worth(self):
        metal = {"class": "Metal rich body", "landable": True}
        forecast = rhino_forecast(metal)
        self.assertEqual(len(forecast), 3)
        self.assertGreaterEqual(forecast[0]["expected"], forecast[1]["expected"])
        self.assertEqual(rhino_hint(metal), forecast[0]["material"])
        self.assertEqual(rhino_hint({"class": "Rocky body", "volcanism": "major rocky magma volcanism", "landable": True}), "Monazite")
        self.assertEqual(rhino_hint({"class": "Icy body", "landable": True}), "", f"under {WORTH_CR} cr a tonne: no hint")
        self.assertEqual(rhino_forecast({"class": "Metal rich body", "landable": False}), [])
        self.assertEqual(rhino_forecast({"class": "Sudarsky class I gas giant"}), [])

    def test_the_hud_pages_say_it(self):
        model = {"system": "Col 285", "scanned": 3, "total": 5, "total_known": True,
                 "rows": [{"name": "Col 285 A 1", "rhino": "Iridium", "mining_count": 3, "max_value": 1000}]}
        rows = next(block for block in hp.survey_page(model)["blocks"] if block["type"] == "list")["items"]
        self.assertIn("3 MINE · RHINO IRIDIUM", str(rows[0]))
        planet = hp.planet_page("A 1", {"short_body": "A 1", "details": {"gravity": .3, "mining_locations": 4},
                                        "best_materials": [{"material": "Iridium", "pct": 29.8, "median": 181000}]})
        listing = next(block for block in planet["blocks"] if block["type"] == "list")
        self.assertEqual(listing["title"], "RHINO GROUND · 4 MINING SITES")
        self.assertIn("Iridium", str(listing["items"][0]))

    def test_the_pages_show_it(self):
        explore = (WEB / "dashboard" / "explore.js").read_text(encoding="utf-8")
        self.assertIn("chip rhino", explore)
        mining = (WEB / "dashboard" / "mining.js").read_text(encoding="utf-8")
        self.assertIn("RHINO PROSPECTS IN THIS SYSTEM", mining)
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_mining.py").read_text(encoding="utf-8")
        self.assertIn('"system_grounds": self._mining_system_grounds()', source)


class MiningSystemTests(unittest.TestCase):
    def test_prospects_across_the_system(self):
        from voidcompass.dashboard.html_mining import HtmlMiningMixin
        deck = HtmlMiningMixin.__new__(HtmlMiningMixin)
        deck.scan_items = [
            {"name": "A 1", "full_name": "Sol A 1", "planet_class": "Icy body", "landable": True},
            {"name": "A 2", "full_name": "Sol A 2", "planet_class": "Metal rich body", "landable": True},
            {"name": "A 3", "full_name": "Sol A 3", "planet_class": "Rocky ice body", "landable": True},
            {"name": "B", "full_name": "Sol B", "planet_class": "Metal rich body", "landable": False},
            {"name": "Sol", "is_star": True},
        ]
        deck.body_signals = {7: {"body_name": "Sol A 3", "mining": 2}}
        rows = deck._mining_system_grounds()
        self.assertEqual([row["short"] for row in rows], ["A 3", "A 2", "A 1"], "mining sites found first, then worth")
        self.assertEqual(rows[0]["mining_count"], 2)


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

    def test_the_redone_scenes_draw(self):
        page = self.browser.new_page(viewport={"width": 500, "height": 326})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = SHIP_ART / path[len("/ship-art/"):] if path.startswith("/ship-art/") else WEB / path.lstrip("/")
            route.fulfill(path=str(target)) if target.is_file() else route.fulfill(status=404, body="")

        page.route("http://r.test/**", serve)
        page.goto("http://r.test/navigation_hud/index.html")
        pictures = []
        for label in ("STATION", "MAP", "CODEX", "AFMU REPAIR", "SYSTEM REBOOT", "SURFACE STATION"):
            page.evaluate("s => render(s)", hud_snapshot(hud_state(label), reduced=True))
            page.wait_for_timeout(250)
            pictures.append(page.evaluate("document.getElementById('deck-canvas').toDataURL()"))
        self.assertEqual(errors, [])
        self.assertEqual(len(set(pictures)), 6)


if __name__ == "__main__":
    unittest.main()
