"""5.5.3: Survey Operations lists high-value bodies (Earth-likes, water
worlds...) straight after biology, the most valuable first, so they are not
lost on a later page."""

import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.overlays.survey_status_hud import build_survey_model

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def body(body_id, name, planet_class, **extra):
    return {"body_id": body_id, "name": name, "planet_class": planet_class, "landable": False,
            "reward": 1000, "dss_reward": 2000, **extra}


class NotableOrderTests(unittest.TestCase):
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

    def test_notable_bodies_follow_biology_most_valuable_first(self):
        from tests.test_survey_planet_visuals import CLIENT_STUB

        page = self.browser.new_page(viewport={"width": 420, "height": 1400})
        self.addCleanup(page.close)

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/assets/overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=CLIENT_STUB)
            file = WEB / path.lstrip("/")
            return route.fulfill(path=str(file)) if file.is_file() else route.fulfill(status=404, body="")

        page.route("http://survey.test/**", serve)
        page.goto("http://survey.test/survey/index.html")
        scans = [
            body(1, "Prai 1", "Rocky body", landable=True, bio_count=2),
            body(2, "Prai 2", "Water world", reward=900_000, dss_reward=2_400_000),
            body(3, "Prai 3", "Earthlike body", reward=1_200_000, dss_reward=3_100_000),
            body(4, "Prai 4", "Icy body", landable=True, geo_count=3),
            # Notable with geology: listed as notable, not as surface.
            body(5, "Prai 5", "Ammonia world", reward=500_000, dss_reward=1_500_000, geo_count=1),
        ]
        model = build_survey_model("Prai", scans, scanned=5, total=5)
        page.evaluate("s => window.__surveyRender(s)", {"survey": model, "theme": {}, "effects": {"reduced_motion": True}})
        groups = page.eval_on_selector_all(".catalogue-group", "els => els.map(e => e.dataset.group)")
        self.assertEqual(groups[:2], ["notable", "surface"])
        names = page.locator(".group-notable .row-name strong").all_inner_texts()
        self.assertEqual(names, ["3", "2", "5"], "Earth-like, water world, ammonia world: by value")


if __name__ == "__main__":
    unittest.main()
