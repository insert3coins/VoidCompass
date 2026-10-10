"""5.5.3.3.1: the Dark box fix. Where WebView2 draws without the GPU (a
commander's GTX 1660 Super), its transparent pixels come out black, a dark box
round anything not rectangular, and no colour key can reach them. With the
fix on, every overlay window is cut to the shapes its page reports."""

import json
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.overlays import html_overlay_host
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer, _clean_shapes

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(HtmlOverlayServer.set_shape_windows, False)

    def test_shapes_are_cleaned(self):
        self.assertEqual(_clean_shapes([[[0, 0], [10, 0], [10, 10]], [[1, 2]], "x", [[0, 0], ["a", 1], [5, 5], [9, 9]]]),
                         [[[0, 0], [10, 0], [10, 10]], [[0, 0], [5, 5], [9, 9]]])
        self.assertEqual(len(_clean_shapes([[[0, 0], [1, 0], [1, 1]]] * 50)), 32)

    def test_the_region_goes_to_the_host_only_with_the_fix_on(self):
        server = HtmlOverlayServer(WEB, presentation_held=False)
        self.addCleanup(server.stop)
        server.register("music", "music_player", "Music")
        server._overlays["music"].shapes = [[[0, 0], [100, 0], [100, 50], [0, 50]]]
        self.assertNotIn("region", server.window_manifest()["music"]["window"])
        self.assertTrue(HtmlOverlayServer.set_shape_windows(True))
        self.assertEqual(server.window_manifest()["music"]["window"]["region"], [[[0, 0], [100, 0], [100, 50], [0, 50]]])

    def test_wired_through(self):
        self.assertTrue(callable(html_overlay_host._apply_window_polygons))
        self.assertIn("overlay_transparency_fix", config_module.PROFILE_BOOL_SETTINGS)
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-overlay-option="overlay_transparency_fix"', html)
        studio = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn('"overlay_transparency_fix"', studio)
        self.assertIn("HtmlOverlayServer.set_shape_windows", studio)


class ClientShapeTests(unittest.TestCase):
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

    def report(self, template, snapshot, width, height):
        """Load a real overlay page with its real client; what it reports."""
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        sent = {"rendered": [], "ready": []}

        def serve(route):
            url = urlsplit(route.request.url)
            if url.path == "/api/health":
                return route.fulfill(content_type="application/json", body=json.dumps({"revision": 1}))
            if url.path == "/api/snapshot":
                return route.fulfill(content_type="application/json", body=json.dumps(snapshot))
            if url.path in ("/api/rendered", "/api/ready"):
                sent["rendered" if url.path.endswith("rendered") else "ready"].append(json.loads(route.request.post_data or "{}"))
                return route.fulfill(content_type="application/json", body="{}")
            if url.path.startswith("/api/"):
                return route.fulfill(content_type="application/json", body="{}")
            path = WEB / url.path.lstrip("/")
            return route.fulfill(path=str(path)) if path.is_file() else route.fulfill(status=404, body="")

        page.route("http://o.test/**", serve)
        page.goto(f"http://o.test/{template}/index.html?token=t&overlay=x")
        page.wait_for_timeout(1500)
        return sent

    def test_the_orb_skin_reports_its_rounded_shape(self):
        sent = self.report("music_player", {"theme": {}, "effects": {"text_scale": 1, "reduced_motion": True}, "music": {
            "state": "playing", "track": {"id": "1", "title": "Solar Echoes", "artist": "nyxevera", "duration": 277},
            "position": 96, "reported_at": time.time() * 1000,
            "options": {"layout": "card", "skin": "orb", "show_art": True}}}, 440, 174)
        shapes = sent["rendered"][-1]["shapes"]
        self.assertEqual(len(shapes), 1)
        polygon = shapes[0]
        self.assertGreater(len(polygon), 20, "rounded corners, not a plain box")
        xs = [x for x, _y in polygon]
        self.assertLessEqual(min(xs), 2)
        self.assertGreaterEqual(max(xs), 436)
        self.assertTrue(sent["ready"] and sent["ready"][0].get("renderer"), "the renderer is reported for the logs")

    def test_each_notification_is_its_own_shape(self):
        now = time.time()
        sent = self.report("toast", {"theme": {}, "effects": {"text_scale": 1, "reduced_motion": True}, "notifications": [
            {"id": 1, "title": "Codex", "message": "New colour", "kind": "notice", "severity": "info", "created_at": now, "expire_at": now + 60},
            {"id": 2, "title": "Fuel", "message": "Scooping", "kind": "notice", "severity": "warn", "created_at": now, "expire_at": now + 60},
        ]}, 400, 180)
        shapes = sent["rendered"][-1]["shapes"]
        self.assertEqual(len(shapes), 2, "the gap between the cards stays see-through")
        self.assertGreater(min(y for _x, y in shapes[1]), max(y for _x, y in shapes[0]))
        self.assertGreaterEqual(len(shapes[0]), 6, "the cards' cut corners")


if __name__ == "__main__":
    unittest.main()
