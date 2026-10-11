"""5.5.3.5: a thought never clips. The lore's long passages ran past the
three lines the thought box allowed and past the orb-high window; now the
window is as tall as the thought's words wrapped (the font is monospaced, so
the bridge works it out before the page draws it), growing up and down alike
so the orb stays put, and the orb keeps its own size inside it."""

from pathlib import Path
import unittest
from unittest.mock import patch

from tests.test_heartbeat_orb import STUB, THEME, WEB
from voidcompass.overlays import watcher_lore
from voidcompass.overlays.heartbeat_hud import ORB_SIZES
from voidcompass.overlays.html_heartbeat_overlay import HtmlHeartbeatBridge

LONGEST = max((row[2] for row in watcher_lore.FRAGMENTS), key=len)


def window_for(orb, size_name, text_percent, text):
    """The window the bridge asks for, with this thought showing."""
    bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
    bridge.config = {"heartbeat_orb_size": orb, "overlay_text_scale_percent": text_percent}
    thought = {"text": text, "style": {"size": size_name}, "side": "right"}
    with patch.object(HtmlHeartbeatBridge, "_thought", return_value=thought):
        return bridge._dimensions(), thought


class ThoughtFitTests(unittest.TestCase):
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

    def show(self, width, height, orb, text_percent, thought):
        from urllib.parse import urlsplit

        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)

        def serve(route):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not path.is_file():
                route.fulfill(status=404, body="")
            elif path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(path))
        page.route("http://orb.test/**", serve)
        page.goto("http://orb.test/heartbeat/index.html")
        page.evaluate("data => renderHeartbeat(data)", {
            "theme": THEME, "effects": {"reduced_motion": True, "text_scale": text_percent / 100},
            "heartbeat": {"events": [], "orb": {"size": orb, "eye": "theme"},
                          "thought": {"id": 1, "text": thought["text"], "script": thought["text"], "mood": "downcast",
                                      "side": "right", "style": {**thought["style"], "backdrop": True}}}})
        page.wait_for_timeout(150)
        return page.evaluate("""() => {
            const span = document.querySelector('#thought .thought-words').getBoundingClientRect();
            const words = document.querySelector('#thought .thought-words');
            const orb = document.querySelector('.heartbeat').getBoundingClientRect();
            return {top: span.top, bottom: span.bottom, right: span.right, cut: words.scrollHeight - words.clientHeight,
                    orb: [orb.width, orb.height], text: words.textContent};
        }""")

    def test_the_longest_passage_fits_every_size(self):
        for orb in (min(ORB_SIZES), max(ORB_SIZES)):
            for size_name in ("small", "standard", "large"):
                for text_percent in (100, 150):
                    with self.subTest(orb=orb, size=size_name, text=text_percent):
                        (width, height), thought = window_for(orb, size_name, text_percent, LONGEST)
                        box = self.show(width, height, orb, text_percent, thought)
                        self.assertEqual(box["text"], LONGEST)
                        self.assertLessEqual(box["cut"], 1, "no lines clipped")
                        self.assertGreaterEqual(box["top"], 0)
                        self.assertLessEqual(box["bottom"], height, "inside the window")
                        self.assertLessEqual(box["right"], width)
                        self.assertEqual(box["orb"], [orb, orb], "the orb keeps its size")

    def test_the_window_grows_around_the_orb(self):
        (width, height), thought = window_for(54, "standard", 100, LONGEST)
        self.assertGreater(height, 54, "taller than the orb for a long thought")
        bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
        bridge.config = {"heartbeat_orb_size": 54, "overlay_text_scale_percent": 100}
        with patch("voidcompass.overlays.html_model_overlay.HtmlModelOverlayBridge._window_payload",
                   return_value={"x": 500, "y": 400, "width": width, "height": height}), \
                patch.object(HtmlHeartbeatBridge, "_thought", return_value=thought), \
                patch("voidcompass.overlays.html_heartbeat_overlay.monitor_scale", return_value=1.0):
            payload = HtmlHeartbeatBridge._window_payload(bridge)
        self.assertEqual(payload["y"], 400 - round((height - 54) / 2), "up and down alike: the orb stays put")
        self.assertEqual(payload["x"], 500)
        (short_width, short_height), _short = window_for(96, "standard", 100, "Hm.")
        self.assertEqual(short_height, 96, "a short thought keeps the orb-high window")

    def test_no_three_line_limit(self):
        css = (Path(WEB) / "heartbeat" / "styles.css").read_text(encoding="utf-8")
        self.assertNotIn("-webkit-line-clamp: 3", css)
        self.assertIn("var(--orb-size, 100vh)", css)


if __name__ == "__main__":
    unittest.main()
