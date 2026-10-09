"""5.5.3.2: notifications and achievements show everything at any text
size: cards grow with their text and the window fits what the page measures,
as the other overlays do."""

import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlsplit

from voidcompass.overlays.html_toast_overlay import HtmlToastOverlayBridge

WEB = Path(__file__).resolve().parents[1] / "web"
STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.__toast = options; return {rerender() {}}; }};")
LONG = ("Codex entry logged in Inner Orion Spur: Bacterium Aurasus, a colour you had not seen in this region, "
        "with a first-footfall bonus pending on Synuefe XR-H d11-102 4 a.")


def toast_bridge(measured, scale=150):
    item = HtmlToastOverlayBridge.__new__(HtmlToastOverlayBridge)
    item.config = {"overlay_text_scale_percent": scale}
    item._browser_content_height = measured
    item.overlay = Mock(WIDTH=400, GAP=7, toast_height=lambda _item: 100)
    return item


class ToastWindowTests(unittest.TestCase):
    def test_window_fits_the_measured_cards(self):
        self.assertEqual(toast_bridge(0)._dimensions([{}]), (600, 100))
        self.assertEqual(toast_bridge(260)._dimensions([{}]), (600, 260), "a long message wraps: the window grows")
        self.assertEqual(toast_bridge(80)._dimensions([{}]), (600, 100), "never smaller than the estimate")
        self.assertEqual(toast_bridge(260)._dimensions([])[1], 24, "nothing showing: no stale height")


class ToastPageTests(unittest.TestCase):
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

    def test_long_text_at_a_large_size_is_shown_whole(self):
        page = self.browser.new_page(viewport={"width": 640, "height": 900})
        self.addCleanup(page.close)

        def serve(route):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not path.is_file():
                route.fulfill(status=404, body="")
            elif path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(path))

        page.route("http://toast.test/**", serve)
        page.goto("http://toast.test/toast/index.html")
        now = time.time()
        page.evaluate("s => window.__toast.render(s)", {
            "theme": {}, "effects": {"text_scale": 1.6, "reduced_motion": True},
            "notifications": [
                {"id": 1, "kind": "notice", "severity": "info", "title": "New Codex colour on Synuefe XR-H d11-102 4 a",
                 "message": LONG, "created_at": now, "expire_at": now + 30},
                {"id": 2, "kind": "achievement", "title": "Seeker of the Unseen Colours of the Galaxy",
                 "message": LONG, "created_at": now, "expire_at": now + 30,
                 "meta": {"category": "Exobiology", "tier": 3, "points": 250}},
            ]})
        clipped = page.evaluate("""() => [...document.querySelectorAll(
            '.notice-title, .notice-message, .achievement-title, .achievement-message, .notification')]
            .filter((el) => el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)
            .map((el) => el.className)""")
        self.assertEqual(clipped, [], "every line is shown")
        height = page.evaluate("window.__toast.contentHeight()")
        cards = page.evaluate("[...document.querySelectorAll('.notification')].reduce((sum, el) => sum + el.offsetHeight, 0)")
        self.assertGreaterEqual(height, cards, "the window is asked for the cards' full height")
        self.assertGreater(height, 2 * 80 * 1.6, "taller than the old fixed cards")
