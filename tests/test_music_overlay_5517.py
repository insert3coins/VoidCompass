"""5.5.17: the music overlay made over. Five new skins, every part in its own
lane (text never on the visualizer), shuffle and repeat as icons, up next for
one track or three, the scene Follow the game is playing for, and where a long
mix carries on from."""

import json
import re
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.dashboard.html_music import HtmlMusicMixin
from voidcompass.overlays.music_player_hud import MUSIC_SKINS, MusicPlayerHUD, music_overlay_size

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderMusic = options.render; return {rerender() {}}; }};")


class Library:
    TRACKS = {"a": ("Into the Black", "Nyx", 200), "b": ("Hutton Run", "The Long Haul", 180),
              "c": ("Witch Space", "Orbital", 210), "d": ("Sagittarius A*", "Nyx", 190),
              "m": ("Colonia Nights (full mix)", "DJ Jameson", 3600)}

    def track(self, identifier):
        found = self.TRACKS.get(identifier)
        return {"title": found[0], "artist": found[1], "duration": found[2]} if found else None

    def playlist(self, _identifier):
        return {"name": "Deep Space Radio"}

    def overlay_art(self, _identifier):
        return ""

    def resume_at(self, identifier):
        return 2520.0 if identifier == "m" else 0.0


def hud(config=None, **status):
    overlay = MusicPlayerHUD.__new__(MusicPlayerHUD)
    overlay.config = config or {}
    overlay._status = status
    overlay._library = Library()
    overlay._rebuild()
    return overlay._html_render_model


class ModelTests(unittest.TestCase):
    def test_up_next_the_scene_and_a_long_mix(self):
        model = hud({"music_player_next_count": 3}, track_id="a", playing=True, scene="deep",
                    upcoming=[{"id": "b", "queued": True}, {"id": "c"}, {"id": "d"}])
        self.assertEqual([(item["title"], item["queued"]) for item in model["upcoming"]],
                         [("Hutton Run", True), ("Witch Space", False), ("Sagittarius A*", False)])
        self.assertEqual(model["next"]["title"], "Hutton Run")
        self.assertEqual(model["scene"], "deep")
        self.assertFalse(model["long_mix"])
        mix = hud(track_id="m", playing=False, scene="nowhere", next_id="a")
        self.assertEqual((mix["long_mix"], mix["resume_at"], mix["scene"]), (True, 2520.0, ""))
        self.assertEqual([item["title"] for item in mix["upcoming"]], ["Into the Black"], "next_id still works")
        self.assertEqual(hud({"music_player_show_next": False}, track_id="a", upcoming=[{"id": "b"}])["upcoming"], [])

    def test_the_status_report_keeps_only_what_it_should(self):
        deck = HtmlMusicMixin.__new__(HtmlMusicMixin)
        deck._music_remember = lambda status: None
        deck._music_update_overlay = lambda: None
        deck._music_status = {"track_id": "a", "playing": True}
        deck._music_status_report({"track_id": "a", "playing": True, "scene": "combat",
                                   "upcoming": [{"id": "b", "queued": 1}, "junk", {"id": "c"}, {"id": "d"}, {"id": "e"}]})
        self.assertEqual(deck._music_status["upcoming"], [{"id": "b", "queued": True}, {"id": "c", "queued": False},
                                                          {"id": "d", "queued": False}])
        self.assertEqual(deck._music_status["scene"], "combat")
        deck._music_status_report({"track_id": "a", "playing": True, "upcoming": {"id": "b"}})
        self.assertEqual(deck._music_status["upcoming"], [])

    def test_studio_and_the_profile_know_the_up_next_count(self):
        self.assertIn("music_player_next_count", config_module.PROFILE_SETTINGS)
        page = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        select = re.search(r'data-studio-setting="music_player_next_count">(.*?)</select>', page, re.S).group(1)
        self.assertEqual(re.findall(r'value="([^"]+)"', select), ["1", "3"])
        deck = (WEB / "dashboard" / "music.js").read_text(encoding="utf-8")
        self.assertIn("upcoming: upcoming(3)", deck, "the Music page sends the next three")


class PageTests(unittest.TestCase):
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

    def open(self, skin, layout="card", count=3):
        width, height = music_overlay_size({"music_player_skin": skin, "music_player_layout": layout,
                                            "music_player_next_count": count})
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            url = urlsplit(route.request.url)
            if url.path == "/api/live":
                return route.fulfill(content_type="application/json", body=json.dumps({"playing": True, "bands": [150] * 32}))
            path = WEB / url.path.lstrip("/")
            if not path.is_file():
                return route.fulfill(status=404, body="")
            if path.name == "overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + STUB)
            return route.fulfill(path=str(path))

        page.route("http://m.test/**", serve)
        page.goto("http://m.test/music_player/index.html")
        return page

    @staticmethod
    def snapshot(skin, state="playing", layout="card", count=3, **music):
        return {"theme": {}, "effects": {"text_scale": 1}, "music": {
            "state": state, "playlist": "Deep Space Radio", "scene": "deep", "shuffle": True, "repeat": "one",
            "track": {"id": "1", "title": "Into the Black", "artist": "Nyx", "album": "Colonia Nights", "duration": 200},
            "upcoming": [{"title": "Hutton Run", "artist": "The Long Haul", "queued": True},
                         {"title": "Witch Space", "artist": "Orbital"}, {"title": "Sagittarius A*", "artist": "Nyx"}],
            "position": 50, "reported_at": time.time() * 1000,
            "options": {"layout": layout, "skin": skin, "visualizer": "bars", "show_art": True, "show_next": True,
                        "show_details": True, "next_count": count}, **music}}

    def test_every_skin_keeps_its_text_off_the_visualizer(self):
        for skin in MUSIC_SKINS:
            with self.subTest(skin=skin):
                page = self.open(skin)
                page.evaluate("s => renderMusic(s)", self.snapshot(skin))
                page.wait_for_timeout(300)
                result = page.evaluate("""() => {
                  const box = (el) => el.getBoundingClientRect();
                  const viz = box(document.getElementById('visualizer'));
                  const view = {w: innerWidth, h: innerHeight};
                  const parts = ['.info', '.progress', '#next'].map((sel) => box(document.querySelector(sel)));
                  const overlaps = parts.filter((r) => r.height && r.top < viz.bottom - 1 && r.bottom > viz.top + 1 && r.left < viz.right - 1 && r.right > viz.left + 1);
                  const inside = [...document.querySelectorAll('#next li, .progress, #title')].every((el) => {
                    const r = box(el); return r.bottom <= view.h + 1 && r.right <= view.w + 1; });
                  return {lane: viz.height, overlaps: overlaps.length, inside, rows: document.querySelectorAll('#next li').length};
                }""")
                self.assertGreater(result["lane"], 8, "the visualizer has a lane of its own")
                self.assertEqual(result["overlaps"], 0)
                self.assertTrue(result["inside"], "the last up-next row fits the window")
                self.assertEqual(result["rows"], 3)

    def test_icons_scene_and_up_next_tags(self):
        page = self.open("deck")
        page.evaluate("s => renderMusic(s)", self.snapshot("deck"))
        self.assertTrue(page.is_visible("#shuffle"))
        self.assertTrue(page.is_visible("#repeat"))
        self.assertTrue(page.is_visible("#repeat-one"), "repeat one shows a 1")
        self.assertEqual(page.inner_text("#scene"), "DEEP SPACE")
        self.assertEqual(page.eval_on_selector_all("#next li span", "nodes => nodes.map((n) => n.textContent)"),
                         ["QUEUED", "THEN", "THEN"])
        page.evaluate("s => renderMusic(s)", self.snapshot("deck", shuffle=False, repeat="off", scene="", count=1))
        self.assertFalse(page.is_visible("#shuffle"))
        self.assertFalse(page.is_visible("#repeat"))
        self.assertFalse(page.is_visible("#scene"))
        self.assertEqual(len(page.evaluate("musicPlayerOverlay.state().next")), 1)

    def test_a_paused_long_mix_says_where_it_carries_on(self):
        page = self.open("vinyl")
        mix = self.snapshot("vinyl", state="paused", long_mix=True, resume_at=2520)
        mix["music"]["track"]["duration"] = 3600
        page.evaluate("s => renderMusic(s)", mix)
        self.assertIn("CARRIES ON FROM 42:00", page.inner_text("#details"))
        self.assertTrue(page.is_visible("#resume"))
        mix["music"]["state"] = "playing"
        page.evaluate("s => renderMusic(s)", mix)
        self.assertIn("LONG MIX", page.inner_text("#details"))
        self.assertFalse(page.is_visible("#resume"))

    def test_every_skin_keeps_the_strip_one_line(self):
        # Vinyl and Minimal set their own card grid, which once took over the strip.
        for skin in MUSIC_SKINS:
            with self.subTest(skin=skin):
                page = self.open(skin, layout="strip")
                page.evaluate("s => renderMusic(s)", self.snapshot(skin, layout="strip"))
                self.assertFalse(page.is_visible("#next"))
                box = page.evaluate("""() => {
                  const r = (sel) => document.querySelector(sel).getBoundingClientRect();
                  return {player: r('#player').height, cover: r('.cover').height, title: r('.title-window').width, viz: r('#visualizer').width};
                }""")
                self.assertLessEqual(box["player"], 44)
                self.assertLessEqual(box["cover"], 31, "a small cover, not the card's")
                self.assertGreater(box["title"], 200, "the title has the room")
                self.assertGreater(box["viz"], 80)


if __name__ == "__main__":
    unittest.main()
