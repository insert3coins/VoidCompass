"""5.6.2: one set of visualizer looks for the Music page and the music
overlay (with the six Pulse looks), and the Neon skin rebuilt with its
palettes as variants."""

import json
import re
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.overlays.music_player_hud import (
    MUSIC_PALETTES, MUSIC_SKINS, MUSIC_VISUALIZERS, music_overlay_options, music_overlay_size,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SHARED = (WEB / "assets" / "music-visualizers.js").read_text(encoding="utf-8")
STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderMusic = options.render; return {rerender() {}}; }};")
THEME = {"bg": "#070b10", "panel": "#0d141c", "accent": "#00d1ff", "orange": "#ff7a18", "text": "#dce8ef",
         "green": "#4ee59b", "yellow": "#ffd166", "red": "#ff6075", "muted": "#85939d", "dim": "#52616c"}


def shared_looks():
    block = SHARED[SHARED.index("const LOOKS = ["):SHARED.index("];", SHARED.index("const LOOKS = ["))]
    return tuple(re.findall(r'\{id: "(\w+)"', block))


def shared_palettes():
    block = SHARED[SHARED.index("const PALETTES = {"):SHARED.index("};", SHARED.index("const PALETTES = {"))]
    return re.findall(r"^    (\w+): \{label", block, re.M)


class ChoiceTests(unittest.TestCase):
    def test_python_knows_every_shared_look(self):
        self.assertEqual(MUSIC_VISUALIZERS, shared_looks())
        for look in ("vu", "radial", "particles", "tunnel", "spiral", "sonar", "scanner", "witchspace"):
            self.assertIn(look, MUSIC_VISUALIZERS)

    def test_the_neon_palettes_and_a_safe_default(self):
        self.assertEqual(set(MUSIC_PALETTES) - {"theme"}, set(shared_palettes()))
        self.assertEqual(music_overlay_options({})["palette"], "neon")
        self.assertEqual(music_overlay_options({"music_player_palette": "VAPORWAVE"})["palette"], "vaporwave")
        self.assertEqual(music_overlay_options({"music_player_palette": "plaid"})["palette"], "neon")
        self.assertIn("music_player_palette", config_module.PROFILE_SETTINGS)

    def test_neon_has_its_own_size(self):
        self.assertIn("neon", MUSIC_SKINS)
        self.assertEqual(music_overlay_size({"music_player_skin": "neon", "music_player_show_next": False}), (440, 232))

    def test_studio_offers_the_palettes(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        select = re.search(r'data-studio-setting="music_player_palette">(.*?)</select>', html, re.S).group(1)
        self.assertEqual(set(re.findall(r'value="([^"]+)"', select)), set(MUSIC_PALETTES))
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
        source = Path(__import__("inspect").getsourcefile(HtmlOverlayStudioMixin)).read_text(encoding="utf-8")
        self.assertIn('("music_player_palette", MUSIC_PALETTES, "neon")', source)

    def test_the_deck_uses_the_shared_looks(self):
        music = (WEB / "dashboard" / "music.js").read_text(encoding="utf-8")
        self.assertNotIn("function drawWitchspace", music, "one copy of the looks, in /assets")
        self.assertIn("shared().painter()", music)
        self.assertIn("data-viz-palette", music)
        self.assertIn('src="/assets/music-visualizers.js"', (WEB / "dashboard" / "index.html").read_text(encoding="utf-8"))
        self.assertIn('src="/assets/music-visualizers.js"', (WEB / "music_player" / "index.html").read_text(encoding="utf-8"))

    def test_the_waveform_reaches_the_overlay(self):
        from voidcompass.dashboard.html_music import MUSIC_WAVE_POINTS, HtmlMusicMixin

        class Deck(HtmlMusicMixin):
            pass

        deck = Deck()
        self.assertTrue(deck.receive_music_levels({"bands": [10] * 32, "wave": [300, -5, 128] + [128] * 100, "playing": True}))
        levels = deck.music_levels()
        self.assertEqual(len(levels["wave"]), MUSIC_WAVE_POINTS)
        self.assertEqual(levels["wave"][:3], [255, 0, 128], "kept within 0-255")


class CoverTests(unittest.TestCase):
    """yt-dlp's covers are video thumbnails (16:9 or 4:3, the art inside bars);
    spotdl's are square. Every box shows the art, filling it."""

    def test_covers_come_out_square(self):
        from PIL import Image, ImageDraw
        from voidcompass.services.music_library import square_cover
        thumb = Image.new("RGB", (1280, 720), (0, 0, 0))
        ImageDraw.Draw(thumb).rectangle((280, 0, 999, 719), fill=(200, 40, 40))
        self.assertEqual((square_cover(thumb).size, square_cover(thumb).getpixel((4, 4))), ((720, 720), (200, 40, 40)),
                         "the bars trimmed: all art")
        old = Image.new("RGB", (480, 360), (0, 0, 0))
        ImageDraw.Draw(old).rectangle((105, 45, 374, 314), fill=(40, 200, 40))
        self.assertEqual(square_cover(old).getpixel((2, 2)), (40, 200, 40), "bars on every side")
        framed = Image.new("RGB", (600, 600), (0, 0, 0))
        ImageDraw.Draw(framed).rectangle((250, 250, 350, 350), fill=(255, 255, 255))
        self.assertEqual(square_cover(framed).getpixel((10, 10)), (0, 0, 0), "a square cover keeps its own frame")
        self.assertEqual(square_cover(Image.effect_noise((1280, 720), 60)).size, (720, 720), "a photo: its middle square")

    def test_stored_covers_are_square(self):
        import io
        import tempfile
        from PIL import Image
        from voidcompass.services.music_library import ART_SIZE, MusicLibrary
        with tempfile.TemporaryDirectory() as folder:
            library = MusicLibrary(folder)
            thumb = io.BytesIO()
            Image.new("RGB", (1280, 720), (90, 10, 160)).save(thumb, "JPEG")
            self.assertTrue(library._store_cover("abc123", thumb.getvalue(), Path(folder) / "song.mp3"))
            with Image.open(library.art_root / "abc123.jpg") as stored:
                self.assertEqual(stored.size, (ART_SIZE, ART_SIZE))


class LookPageTests(unittest.TestCase):
    """Every look draws in the overlay, on a skin of its own and on Neon."""

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

    @staticmethod
    def serve(route):
        path = urlsplit(route.request.url).path
        if path == "/api/live":
            bands = [200 - band * 4 for band in range(32)]
            wave = [128 + (60 if point % 8 < 4 else -60) for point in range(64)]
            return route.fulfill(content_type="application/json", body=json.dumps({"bands": bands, "wave": wave, "playing": True}))
        file = WEB / path.lstrip("/")
        if not file.is_file():
            return route.fulfill(status=404, body="")
        if file.name == "overlay-client.js":
            return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
        return route.fulfill(path=str(file))

    def test_every_look_draws(self):
        page = self.browser.new_page(viewport={"width": 440, "height": 254})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("http://looks.test/**", self.serve)
        page.goto("http://looks.test/music_player/index.html?token=t&overlay=music-player")
        page.wait_for_function("Boolean(window.renderMusic)")
        for skin in ("deck", "neon"):
            for look in [look for look in MUSIC_VISUALIZERS if look != "off"]:
                with self.subTest(skin=skin, look=look):
                    config = {"music_player_skin": skin, "music_player_visualizer": look, "music_player_palette": "miami"}
                    music = {"state": "playing", "position": 40, "reported_at": int(time.time() * 1000),
                             "track": {"id": "t", "title": "Departure", "artist": "Lumen", "duration": 300, "format": "FLAC"},
                             "options": music_overlay_options(config)}
                    page.evaluate("([m, t]) => renderMusic({theme: t, effects: {text_scale: 1}, music: m})", [music, THEME])
                    page.wait_for_timeout(260)
                    lit = page.evaluate("""() => { const c = document.getElementById('visualizer');
                        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
                        let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 8) n += 1; return n; }""")
                    self.assertGreater(lit, 30, "something drawn")
                    state = page.evaluate("window.musicPlayerOverlay.state()")
                    self.assertEqual((state["skin"], state["visualizer"]), (skin, look))
        self.assertEqual(page.evaluate("window.musicPlayerOverlay.state().wave"), 64, "the real waveform arrived")
        self.assertEqual(page.evaluate("document.getElementById('neon-look').textContent"), "SONAR")
        self.assertEqual(page.evaluate("getComputedStyle(document.getElementById('player')).getPropertyValue('--neon-low').trim()"), "#2de6c8",
                         "Miami's colours")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
