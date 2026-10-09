"""5.5.3.3: ten skins for the music player overlay, chosen in Overlay Studio,
each with its own size; on the slim strip a skin sets its colours."""

import json
import re
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.overlays.music_player_hud import MUSIC_SKINS, music_overlay_options, music_overlay_size

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderMusic = options.render; return {rerender() {}}; }};")


class SkinSettingTests(unittest.TestCase):
    def test_ten_skins_and_a_safe_default(self):
        self.assertEqual(len(MUSIC_SKINS), 10)
        self.assertEqual(music_overlay_options({})["skin"], "deck")
        self.assertEqual(music_overlay_options({"music_player_skin": "VINYL"})["skin"], "vinyl")
        self.assertEqual(music_overlay_options({"music_player_skin": "hologram"})["skin"], "deck")
        self.assertIn("music_player_skin", config_module.PROFILE_TEXT_SETTINGS)

    def test_each_skin_has_its_own_size(self):
        self.assertEqual(music_overlay_size({"music_player_skin": "cassette", "music_player_show_next": False}), (400, 196))
        self.assertEqual(music_overlay_size({"music_player_skin": "minimal"}), (440, 84 + 18))
        self.assertEqual(music_overlay_size({"music_player_skin": "orb", "overlay_text_scale_percent": 150,
                                             "music_player_show_next": False}), (660, 234))
        self.assertEqual(music_overlay_size({"music_player_skin": "vinyl", "music_player_layout": "strip"}), (580, 44),
                         "the strip keeps its own size")

    def test_studio_offers_exactly_the_skins(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        select = re.search(r'data-studio-setting="music_player_skin">(.*?)</select>', html, re.S).group(1)
        self.assertEqual(tuple(re.findall(r'value="([^"]+)"', select)), tuple(MUSIC_SKINS))

    def test_studio_saves_only_a_real_skin(self):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
        source = Path(__import__("inspect").getsourcefile(HtmlOverlayStudioMixin)).read_text(encoding="utf-8")
        self.assertIn('("music_player_skin", tuple(MUSIC_SKINS), "deck")', source)


class SkinPageTests(unittest.TestCase):
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

    def test_every_skin_renders_and_draws(self):
        for skin in MUSIC_SKINS:
            with self.subTest(skin=skin):
                width, height = music_overlay_size({"music_player_skin": skin})
                page = self.browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def serve(route):
                    url = urlsplit(route.request.url)
                    if url.path == "/api/live":
                        return route.fulfill(content_type="application/json",
                                             body=json.dumps({"playing": True, "bands": [180] * 32}))
                    path = WEB / url.path.lstrip("/")
                    if not path.is_file():
                        return route.fulfill(status=404, body="")
                    if path.name == "overlay-client.js":
                        return route.fulfill(content_type="application/javascript",
                                             body=path.read_text(encoding="utf-8") + STUB)
                    return route.fulfill(path=str(path))

                page.route("http://m.test/**", serve)
                page.goto("http://m.test/music_player/index.html")
                page.evaluate("s => renderMusic(s)", {
                    "theme": {}, "effects": {"text_scale": 1},
                    "music": {"state": "playing", "track": {"id": "1", "title": "Into the Black", "artist": "Nyx", "duration": 200},
                              "position": 50, "reported_at": time.time() * 1000,
                              "options": {"layout": "card", "skin": skin, "visualizer": "bars", "show_art": True,
                                          "show_next": True}}})
                page.wait_for_timeout(500)
                state = page.evaluate("musicPlayerOverlay.state()")
                self.assertEqual(state["skin"], skin)
                progress = float(page.evaluate("getComputedStyle(document.getElementById('player')).getPropertyValue('--progress')"))
                self.assertAlmostEqual(progress, .25, delta=.03)
                drawn = page.evaluate("""() => { const c = document.getElementById('visualizer');
                  if (!c.width || !c.height) return false;
                  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
                  for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; }""")
                if skin != "cassette":  # the cassette's reels are its visualizer
                    self.assertTrue(drawn, f"{skin} draws its visualizer")
                self.assertEqual(errors, [])
                page.close()


if __name__ == "__main__":
    unittest.main()
