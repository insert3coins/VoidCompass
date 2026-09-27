"""The Galnet Ticker overlay: headlines and their stories, scrolling.

A slim bar for the cockpit: a GALNET badge, then each dispatch's headline,
its date and its story, scrolling right to left as one seamless loop. Its
length, speed, how much of each story it reads and how many stories are
Overlay Studio options, saved per commander. These tests hold the model
Python builds, the options' limits, its registration as an overlay, and the
page's scrolling, speed changes, idle states and reduced motion.
"""

from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.core.application_runtime import ApplicationRuntime
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS, OVERLAY_SPEC_BY_ATTR
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays.galnet_ticker_hud import (
    FULL_CHARS, SUMMARY_CHARS, TICKER_CONTENT, TICKER_SPEEDS, TICKER_STORIES,
    GalnetTickerHUD, ticker_options, ticker_text,
)
from voidcompass.overlays.html_galnet_ticker_overlay import HtmlGalnetTickerBridge
from voidcompass.overlays.html_overlay_host import _OverlayHost

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LONG_STORY = " ".join(f"Sentence number {index} reports on the frontier in some detail." for index in range(60))


def feed(*titles, busy=False, status="ready"):
    return {
        "status": status, "busy": busy, "detail": "",
        "articles": [
            {"id": title.lower(), "title": title, "body": f"{title} happened. Then more happened.", "stamp": "27 SEP 3312"}
            for title in titles
        ],
    }


class TickerOptionTests(unittest.TestCase):
    def test_options_stay_within_their_choices(self):
        self.assertEqual(ticker_options({}), {"width": 860, "speed": "standard", "content": "summary",
                                              "stories": 5, "show_date": True})
        wild = ticker_options({"galnet_ticker_width": 99999, "galnet_ticker_speed": "warp",
                               "galnet_ticker_content": "poem", "galnet_ticker_stories": 7,
                               "galnet_ticker_show_date": False})
        self.assertEqual(wild, {"width": 2560, "speed": "standard", "content": "summary",
                                "stories": 5, "show_date": False})
        self.assertEqual(ticker_options({"galnet_ticker_width": 10})["width"], 360)

    def test_story_text_follows_the_content_choice(self):
        self.assertEqual(ticker_text("A short story.", "headlines"), "")
        self.assertEqual(ticker_text("A  short\n story.", "summary"), "A short story.")
        summary = ticker_text(LONG_STORY, "summary")
        self.assertLessEqual(len(summary), SUMMARY_CHARS)
        self.assertTrue(summary.endswith("."), "a summary ends on a whole sentence")
        self.assertLessEqual(len(ticker_text(LONG_STORY, "full")), FULL_CHARS)
        self.assertGreater(len(ticker_text(LONG_STORY, "full")), len(summary))
        unbroken = ticker_text("word " * 200, "summary")
        self.assertTrue(unbroken.endswith("…"))
        self.assertLessEqual(len(unbroken), SUMMARY_CHARS + 1)


class TickerModelTests(unittest.TestCase):
    def setUp(self):
        self.root = ApplicationRuntime()
        self.addCleanup(self.root.close)

    def ticker(self, **config):
        hud = GalnetTickerHUD(self.root, {"galnet_ticker_hud_x": 20, "galnet_ticker_hud_y": 20, **config})
        self.addCleanup(hud.destroy)
        return hud

    def test_live_stories_are_limited_and_read_as_chosen(self):
        hud = self.ticker(galnet_ticker_stories=3, galnet_ticker_content="headlines")
        hud.update_feed(feed("One", "Two", "Three", "Four", "Five"))
        model = hud._html_render_model
        self.assertEqual(model["status"], "live")
        self.assertEqual([story["title"] for story in model["stories"]], ["One", "Two", "Three"])
        self.assertEqual({story["text"] for story in model["stories"]}, {""})
        self.assertEqual(model["options"]["px_per_second"], TICKER_SPEEDS["standard"])

    def test_dispatches_arriving_later_are_marked_new(self):
        hud = self.ticker()
        hud.update_feed(feed("Old news"))
        self.assertFalse(hud._html_render_model["stories"][0]["new"], "what was there at start is not news")
        hud.update_feed(feed("Breaking", "Old news"))
        stories = {story["title"]: story["new"] for story in hud._html_render_model["stories"]}
        self.assertEqual(stories, {"Breaking": True, "Old news": False})

    def test_status_covers_off_waiting_receiving_and_error(self):
        hud = self.ticker()
        self.assertEqual(hud._html_render_model["status"], "waiting")
        hud.update_feed(feed(busy=True))
        self.assertEqual(hud._html_render_model["status"], "receiving")
        hud.update_feed(feed(status="error"))
        self.assertEqual(hud._html_render_model["status"], "error")
        hud.update_feed(feed("Anything"), enabled=False)
        self.assertEqual(hud._html_render_model["status"], "off")

    def test_settings_change_rebuilds_the_model(self):
        hud = self.ticker()
        hud.update_feed(feed("One"))
        hud.config["galnet_ticker_speed"] = "fast"
        hud.apply_settings()
        self.assertEqual(hud._html_render_model["options"]["px_per_second"], TICKER_SPEEDS["fast"])

    def test_window_is_the_bar_length_and_grows_with_text_size(self):
        bridge = HtmlGalnetTickerBridge.__new__(HtmlGalnetTickerBridge)
        bridge.config = {"galnet_ticker_width": 1200, "overlay_text_scale_percent": 150}
        self.assertEqual(bridge._dimensions(), (1200, 51))
        bridge.config = {}
        self.assertEqual(bridge._dimensions(), (860, 34))

    def test_dashboard_hands_the_ticker_the_relay_and_its_switch(self):
        app = MainDashboard.__new__(MainDashboard)
        app.config = {"galnet_enabled": False}
        app.galnet_ticker_hud = SimpleNamespace(update_feed=Mock())
        app._html_dashboard_galnet = lambda: {"articles": [], "status": "ready"}
        app._update_galnet_ticker()
        app.galnet_ticker_hud.update_feed.assert_called_once_with({"articles": [], "status": "ready"}, enabled=False)


class TickerRegistrationTests(unittest.TestCase):
    def test_it_is_a_managed_overlay_with_a_hotkey(self):
        spec = OVERLAY_SPEC_BY_ATTR["galnet_ticker_hud"]
        self.assertEqual((spec.enabled_key, spec.default_enabled), ("galnet_ticker_overlay_enabled", False))
        self.assertIn(("galnet_ticker", "overlay_hotkey_galnet_ticker", "Galnet Ticker", "galnet_ticker_hud"),
                      OVERLAY_HOTKEY_SPECS)
        host = _OverlayHost.__new__(_OverlayHost)
        host.token = "t"
        host.origin = "http://127.0.0.1:1"
        self.assertIn("/galnet_ticker/index.html", host.page_url("galnet-ticker", "galnet_ticker"))

    def test_settings_follow_the_commander_profile(self):
        for key in ("galnet_ticker_overlay_enabled", "galnet_ticker_show_date"):
            self.assertIn(key, config_module.PROFILE_BOOL_SETTINGS)
        for key in ("galnet_ticker_speed", "galnet_ticker_content", "overlay_hotkey_galnet_ticker"):
            self.assertIn(key, config_module.PROFILE_TEXT_SETTINGS)
        for key in ("galnet_ticker_width", "galnet_ticker_stories", "galnet_ticker_hud_x", "galnet_ticker_hud_y"):
            self.assertIn(key, config_module.PROFILE_VALUE_SETTINGS)

    def test_studio_saves_and_validates_each_option(self):
        class Studio(HtmlOverlayStudioMixin):
            def __init__(self):
                self.config = {}
                self.galnet_ticker_hud = SimpleNamespace(apply_settings=Mock())

            def _persist_config(self):
                pass

            def update_hud(self):
                pass

            def _schedule_html_dashboard_publish(self, **kwargs):
                pass

        studio = Studio()
        studio._html_overlay_settings_save({"galnet_ticker_width": "5000", "galnet_ticker_speed": "FAST",
                                            "galnet_ticker_content": "full", "galnet_ticker_stories": "8"})
        self.assertEqual({key: studio.config[key] for key in studio.config},
                         {"galnet_ticker_width": 2560, "galnet_ticker_speed": "fast",
                          "galnet_ticker_content": "full", "galnet_ticker_stories": 8})
        studio._html_overlay_settings_save({"galnet_ticker_speed": "warp", "galnet_ticker_stories": "7"})
        self.assertEqual((studio.config["galnet_ticker_speed"], studio.config["galnet_ticker_stories"]), ("standard", 5))
        self.assertTrue(studio._html_overlay_option_toggle("galnet_ticker_show_date", False))
        self.assertFalse(studio.config["galnet_ticker_show_date"])
        self.assertGreaterEqual(studio.galnet_ticker_hud.apply_settings.call_count, 3)

    def test_studio_offers_exactly_the_supported_choices(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="galnet_ticker_hud">(.*?)</section>', html, re.S).group(1)
        choices = lambda key: re.search(rf'data-studio-setting="{key}">(.*?)</select>', section, re.S).group(1)  # noqa: E731
        self.assertEqual(tuple(re.findall(r'value="([a-z]+)"', choices("galnet_ticker_speed"))), tuple(TICKER_SPEEDS))
        self.assertEqual(tuple(re.findall(r'value="([a-z]+)"', choices("galnet_ticker_content"))), TICKER_CONTENT)
        self.assertEqual(tuple(int(v) for v in re.findall(r'value="(\d+)"', choices("galnet_ticker_stories"))), TICKER_STORIES)
        self.assertIn('data-studio-setting="galnet_ticker_width"', section)
        self.assertIn('data-overlay-option="galnet_ticker_show_date"', section)


STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderTicker = options.render; return {rerender() {}}; }};")
STORIES = [
    {"id": "a", "title": "Thargoid Titan Signals Fade", "stamp": "27 SEP 3312", "text": "Researchers report the signal has weakened.", "new": True},
    {"id": "b", "title": "Colonisation Contracts Peak", "stamp": "26 SEP 3312", "text": "Claims exceed projections.", "new": False},
]


def snapshot(status="live", stories=STORIES, speed="standard", reduced=False, scale=1.0):
    return {"theme": {}, "effects": {"crt": True, "reduced_motion": reduced, "text_scale": scale},
            "ticker": {"status": status, "busy": False, "stories": stories if status == "live" else [],
                       "options": {"width": 860, "speed": speed, "content": "summary", "stories": 5,
                                   "show_date": True, "px_per_second": TICKER_SPEEDS[speed]}}}


class TickerBrowserTests(unittest.TestCase):
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

    def open(self, width=860, height=34):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not path.is_file():
                route.fulfill(status=404, body="")
            elif path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(path))

        page.route("http://ticker.test/**", serve)
        page.goto("http://ticker.test/galnet_ticker/index.html")
        return page

    def test_stories_scroll_as_a_seamless_loop(self):
        page = self.open()
        page.evaluate("data => renderTicker(data)", snapshot())
        state = page.evaluate("galnetTicker.state()")
        self.assertTrue(state["scrolling"])
        self.assertGreaterEqual(state["copies"], 2, "enough copies to keep the bar full")
        text = page.inner_text("#ticker-track")
        for story in STORIES:
            self.assertIn(story["title"].upper(), text.upper())
            self.assertIn(story["text"], text)
        self.assertFalse(page.is_hidden("#ticker-new"), "a new dispatch lights the badge")

    def test_a_speed_change_carries_on_without_restarting(self):
        page = self.open()
        page.evaluate("data => renderTicker(data)", snapshot())
        page.wait_for_timeout(400)
        before = page.evaluate("document.getAnimations()[0]?.currentTime || 0")
        page.evaluate("data => renderTicker(data)", snapshot(speed="fast"))
        state = page.evaluate("galnetTicker.state()")
        self.assertAlmostEqual(state["rate"], TICKER_SPEEDS["fast"] / 75, places=3)
        self.assertGreaterEqual(page.evaluate("document.getAnimations()[0]?.currentTime || 0"), before)
        # Larger text scrolls proportionally faster, so it reads at the same pace.
        page.evaluate("data => renderTicker(data)", snapshot(scale=1.5))
        self.assertAlmostEqual(page.evaluate("galnetTicker.state().rate"), 1.5, places=3)

    def test_idle_states_say_why_there_is_no_news(self):
        page = self.open()
        for status, words in (("off", "SWITCH IT ON IN SETTINGS"), ("waiting", "AWAITING"),
                              ("error", "UNAVAILABLE"), ("receiving", "RECEIVING")):
            page.evaluate("data => renderTicker(data)", snapshot(status))
            state = page.evaluate("galnetTicker.state()")
            self.assertIn(words, state["idle"], status)
            self.assertFalse(state["scrolling"])

    def test_reduced_motion_holds_one_story_and_steps(self):
        page = self.open()
        page.clock.install()
        page.evaluate("data => renderTicker(data)", snapshot(reduced=True))
        state = page.evaluate("galnetTicker.state()")
        self.assertEqual((state["still"], state["scrolling"]), (True, False))
        first = page.inner_text("#ticker-track")
        self.assertIn(STORIES[0]["title"].upper(), first.upper())
        page.clock.run_for(8100)
        self.assertIn(STORIES[1]["title"].upper(), page.inner_text("#ticker-track").upper())
        self.assertEqual(page.evaluate("document.getAnimations().length"), 0)


if __name__ == "__main__":
    unittest.main()
