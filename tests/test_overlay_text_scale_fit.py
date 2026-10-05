"""5.5.2.7: overlays fit larger text.

Every overlay page zooms its content by the overlay text size, so its window
must grow by the same factor, in width and in its height limits. Before this,
most overlays kept their design width and height caps, so larger text was
squeezed and the bottom rows were cut off. The Navigation HUD also fits
itself to the window it actually gets, so a PC that draws pages larger than
expected can't clip it."""

from pathlib import Path
import unittest
from unittest.mock import Mock
from urllib.parse import unquote, urlsplit

from voidcompass.overlays.html_cargo_overlay import HtmlCargoOverlayBridge
from voidcompass.overlays.html_jump_info_overlay import HtmlJumpInfoBridge
from voidcompass.overlays.html_model_overlay import HtmlModelOverlayBridge
from voidcompass.overlays.html_station_overlay import HtmlStationOverlayBridge
from voidcompass.overlays.html_survey_overlay import HtmlSurveyOverlayBridge
from voidcompass.overlays.html_toast_overlay import HtmlToastOverlayBridge

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def bridge(cls, config, measured=0, **fields):
    """A bridge with only what its sizing reads (no windows, no server)."""
    item = cls.__new__(cls)
    item.config = config
    item._browser_content_height = measured
    for key, value in fields.items():
        setattr(item, key, value)
    return item


class WindowSizeTests(unittest.TestCase):
    def model(self, scale, measured=0):
        return bridge(HtmlModelOverlayBridge, {"overlay_text_scale_percent": scale}, measured,
                      width=430, min_height=180, default_height=310, max_height=520)

    def test_shared_overlays_grow_with_the_text(self):
        self.assertEqual(self.model(100)._dimensions(), (430, 310))
        self.assertEqual(self.model(150)._dimensions(), (645, 465), "width and default height grow")
        self.assertEqual(self.model(150, measured=760)._dimensions(), (645, 760),
                         "content taller than the design cap still fits: the cap grows too")
        self.assertEqual(self.model(150, measured=900)._dimensions()[1], 780, "within the scaled cap")
        self.assertEqual(self.model(400)._dimensions()[0], 860, "text size is capped at 200%")

    def test_jump_info_is_not_scaled_twice(self):
        info = bridge(HtmlJumpInfoBridge, {"overlay_text_scale_percent": 150}, 0,
                      width=560, min_height=96, default_height=180, max_height=640)
        self.assertEqual(info._dimensions(), (840, 270))

    def test_cargo_station_survey_and_notifications(self):
        self.assertEqual(bridge(HtmlCargoOverlayBridge, {"overlay_text_scale_percent": 150})._dimensions(), (615, 390))
        self.assertEqual(bridge(HtmlStationOverlayBridge, {"overlay_text_scale_percent": 150}, 1000)._dimensions(), (780, 1000))
        survey = bridge(HtmlSurveyOverlayBridge, {"overlay_text_scale_percent": 100, "survey_text_scale_percent": 150}, 300)
        self.assertEqual(survey._dimensions(), (630, 300), "Survey follows its own text size")
        toast = bridge(HtmlToastOverlayBridge, {"overlay_text_scale_percent": 150},
                       overlay=Mock(WIDTH=400, GAP=7, toast_height=lambda item: 100))
        self.assertEqual(toast._dimensions([{}])[0], 600)


class NavigationHudFitTests(unittest.TestCase):
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

    def test_the_hud_fits_the_window_it_actually_gets(self):
        from tests.test_navigation_state_visuals import SHIP_ART, hud_snapshot, hud_state

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = SHIP_ART / path[len("/ship-art/"):] if path.startswith("/ship-art/") else WEB / path.lstrip("/")
            route.fulfill(path=str(target)) if target.is_file() else route.fulfill(status=404, body="")

        # The commander's PC drew the page about 1.3x larger than the window
        # was sized for: a 150% text size in a window made for 115%.
        for layout, (width, height) in (("standard", (500, 326)), ("expanded", (620, 342))):
            with self.subTest(layout=layout):
                page = self.browser.new_page(viewport={"width": round(width * 1.15), "height": round(height * 1.15)})
                self.addCleanup(page.close)
                page.route("http://fit.test/**", serve)
                page.goto("http://fit.test/navigation_hud/index.html")
                snapshot = hud_snapshot(hud_state("DOCKED"), layout=layout, scale=1.5)
                snapshot["theme"]["type"] = {"face": "cockpit", "labels": "larger", "bright": False}
                page.evaluate("s => render(s)", snapshot)
                result = page.evaluate("""() => {
                  const box = dom.hud.getBoundingClientRect();
                  const rail = document.querySelector('.context-rail').getBoundingClientRect();
                  return {hud: [box.width, box.height], rail: rail.bottom, view: [innerWidth, innerHeight],
                          scale: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--text-scale'))};
                }""")
                self.assertAlmostEqual(result["scale"], 1.15, places=2)
                self.assertLessEqual(result["hud"][0], result["view"][0] + 1)
                self.assertLessEqual(result["hud"][1], result["view"][1] + 1)
                self.assertLessEqual(result["rail"], result["view"][1] + 1, "the bottom row is inside the window")


if __name__ == "__main__":
    unittest.main()
