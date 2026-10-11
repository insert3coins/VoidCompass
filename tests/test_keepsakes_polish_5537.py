"""5.5.3.7 polish, the user's picks: the minimap's stars along the route, a
scale bar and smooth moves; the Watcher keeping the postcards you take and
bringing them up later; and a postcard album on the deck."""

import http.client
import os
from pathlib import Path
import random
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from tests.test_galaxy_minimap_5537 import STUB, THEME, FakeRoot, row
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.overlays import watcher_idle, watcher_postcards
from voidcompass.overlays.galaxy_minimap_hud import build_minimap_model, plotted_route, star_kind
from voidcompass.overlays.html_galaxy_minimap_overlay import minimap_file
from voidcompass.overlays.postcard_picture import open_picture, save_postcard_picture
from voidcompass.overlays.postcards import postcard_card
from voidcompass.overlays.watcher_mind import WatcherMind
from voidcompass.services.postcard_album import PostcardAlbum, postcard_id

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def stop(name, x, star):
    return {"StarSystem": name, "StarPos": [x, 0.0, x], "StarClass": star}


class RouteStarTests(unittest.TestCase):
    def test_what_each_star_is_good_for(self):
        for star, kind in (("K", "scoop"), ("M", "scoop"), ("O", "scoop"), ("N", "neutron"), ("DA", "dwarf"),
                           ("DC", "dwarf"), ("L", ""), ("T", ""), ("TTS", ""), ("H", ""), ("", "")):
            self.assertEqual(star_kind(star), kind, star)

    def test_the_stars_along_the_route(self):
        route = [stop("Here", 0, "M"), stop("A", 10, "L"), stop("B", 20, "N"), stop("C", 30, "K"), stop("D", 40, "Y")]
        ahead = plotted_route(route, [0, 0, 0], "Here")
        self.assertEqual(ahead["stars"], ["scoop", "", "neutron", "scoop", ""])
        self.assertNotIn("scoop_in", ahead, "no scoop count: the Nav HUD has it")


class WatcherKeepsTests(unittest.TestCase):
    def test_it_keeps_every_postcard_and_brings_old_ones_up(self):
        memory = {}
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe", "Body": "Hatchooe AB 3"},
                             kind="Water world")
        for index in range(watcher_postcards.KEPT_MAX + 5):
            watcher_postcards.keep(memory, card, 1000.0 + index)
        self.assertEqual(len(memory["postcards"]), watcher_postcards.KEPT_MAX)
        self.assertEqual(memory["postcards"][-1][1:], ["Hatchooe AB 3", "Water world"])
        now = time.time()
        fresh = {"postcards": [[now - 60, "Hatchooe AB 3", ""]]}
        self.assertIsNone(watcher_postcards.recall_choice(fresh, random.Random(1), now), "not the one just taken")
        old = {"postcards": [[now - 3 * 86400, "Hatchooe AB 3", ""]]}
        recalled = watcher_postcards.recall_choice(old, random.Random(1), now)
        self.assertEqual(recalled["place"], "Hatchooe AB 3")
        self.assertTrue(recalled["when"])

    def test_a_quiet_moment_can_bring_one_up(self):
        self.assertIn("idle_postcard", watcher_idle.IDLE_TOPICS)
        mind = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, lambda: 50000.0, random.Random(2))
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe", "Body": "Hatchooe AB 3"})
        self.assertEqual(mind.keep_postcard(card), 1)
        thought = mind.consider("idle_postcard", {"place": "Hatchooe AB 3", "when": "3 days ago", "When": "3 days ago"}, force=True)
        self.assertIn("Hatchooe AB 3", thought["text"])
        self.assertNotIn("{", thought["text"])
        page = (WEB / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        self.assertIn('"POSTCARDS KEPT"', page)

    def test_the_app_hands_it_each_postcard(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        kept = []
        deck.config = {}
        deck.postcard_hud = None
        deck.heartbeat_hud = SimpleNamespace(mind=SimpleNamespace(keep_postcard=kept.append))
        deck.config["screenshot_captions"] = True
        with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.threading.Thread"):
            deck._postcard_observe("Screenshot", {"timestamp": "2026-10-11T20:14:00Z", "System": "Sol", "Body": "Earth"})
        self.assertEqual([card["title"] for card in kept], ["Earth"])


def album_folder(test, count=3):
    folder = tempfile.mkdtemp()
    test.addCleanup(lambda: [os.remove(os.path.join(folder, name)) for name in os.listdir(folder)] and None)
    from PIL import Image
    shot = os.path.join(folder, "shot.bmp")
    Image.new("RGB", (64, 36), (20, 60, 120)).save(shot, "BMP")
    picture = open_picture(shot)
    os.remove(shot)
    for index in range(count):
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Sol", "Body": f"Place {index}"})
        path = save_postcard_picture(card, picture, folder, stamp=f"2026-10-1{index} 20-14-00")
        os.utime(path, (1000 + index * 100, 1000 + index * 100))
    return folder


class AlbumTests(unittest.TestCase):
    def test_newest_first_by_id_never_by_path(self):
        folder = album_folder(self)
        album = PostcardAlbum(lambda: folder)
        rows = album.rows()
        self.assertEqual([row["title"] for row in rows], ["Place 2", "Place 1", "Place 0"])
        self.assertEqual(rows[0]["id"], postcard_id(rows[0]["file"]))
        self.assertTrue(album.full(rows[0]["id"]).startswith(b"\x89PNG"))
        self.assertTrue(album.thumb(rows[0]["id"]).startswith(b"\xff\xd8"), "a small JPEG")
        self.assertIsNone(album.full("0" * 16))
        with patch("voidcompass.services.postcard_album.copy_dib", return_value=True) as copied:
            self.assertTrue(album.copy(rows[0]["id"]))
            self.assertGreater(len(copied.call_args.args[0]), 1000)

    def test_the_deck_serves_them_with_its_token(self):
        folder = album_folder(self, 1)
        server = HtmlDashboardServer(WEB)
        self.addCleanup(server.stop)
        server.postcards = PostcardAlbum(lambda: folder)
        card_id = server.postcards.rows()[0]["id"]
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        self.addCleanup(connection.close)
        for path, kind in ((f"/media/postcard/{card_id}.png", "image/png"), (f"/media/postcard-thumb/{card_id}.jpg", "image/jpeg")):
            connection.request("GET", f"{path}?token={server.token}")
            reply = connection.getresponse()
            body = reply.read()
            self.assertEqual((reply.status, reply.getheader("Content-Type")), (200, kind), path)
            self.assertTrue(body)
        connection.request("GET", f"/media/postcard/{card_id}.png")
        reply = connection.getresponse()
        reply.read()
        self.assertEqual(reply.status, 403, "only with the token")
        connection.request("GET", f"/media/postcard/{'1' * 16}.png?token={server.token}")
        reply = connection.getresponse()
        reply.read()
        self.assertEqual(reply.status, 404)

    def test_the_postcards_page(self):
        folder = album_folder(self, 2)

        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = {"postcards_path": folder, "screenshot_postcards": False}
        deck._persist_config = lambda: None
        data = deck._html_postcards_workspace()
        self.assertEqual((len(data["rows"]), data["saving"], data["folder"]), (2, False, folder))
        self.assertTrue(deck._handle_postcards_command("set", {"key": "screenshot_postcards", "value": True}))
        self.assertTrue(deck.config["screenshot_postcards"])
        with patch("voidcompass.services.postcard_album.copy_dib", return_value=True):
            self.assertTrue(deck._handle_postcards_command("copy", {"id": data["rows"][0]["id"]}))
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="postcards"', html)
        self.assertIn('data-page-name="postcards"', html)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("postcards: (data) => renderPostcards(data, WORKSHOP_UI)", app)
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('"postcards": getattr(self, "_html_postcards_workspace", None)', dashboard)


class PostcardSettingsTests(unittest.TestCase):
    """Everything about postcards on the Postcards page; Overlay Studio keeps
    only the overlay's own options."""

    def deck(self, folder):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = {"postcards_path": folder}
        deck.saved = 0

        def persist():
            deck.saved += 1
        deck._persist_config = persist
        return deck

    def test_the_page_carries_the_settings(self):
        deck = self.deck(album_folder(self, 1))
        deck.config.update({"postcard_style": "holo", "postcard_note": False, "screenshot_captions": True})
        data = deck._html_postcards_workspace()
        settings = data["settings"]
        self.assertEqual((settings["postcard_style"], settings["postcard_note"], settings["screenshot_captions"]), ("holo", False, True))
        self.assertTrue(settings["default_folder"].endswith("postcards"))
        self.assertEqual(data["styles"], ["polaroid", "airmail", "holo", "vintage"])
        self.assertTrue(data["preview"].startswith("holo-"))

    def test_settings_are_checked_and_saved(self):
        deck = self.deck(album_folder(self, 1))
        command = deck._handle_postcards_command
        self.assertTrue(command("set", {"key": "postcard_style", "value": "Vintage"}))
        self.assertEqual(deck.config["postcard_style"], "vintage")
        self.assertFalse(command("set", {"key": "postcard_style", "value": "neon"}))
        self.assertTrue(command("set", {"key": "postcard_facts", "value": False}))
        self.assertIs(deck.config["postcard_facts"], False)
        self.assertTrue(command("set", {"key": "screenshot_captions", "value": "true"}))
        self.assertIs(deck.config["screenshot_captions"], True)
        self.assertTrue(command("set", {"key": "postcards_path", "value": "  D:/Cards  "}))
        self.assertEqual(deck.config["postcards_path"], "D:/Cards")
        self.assertFalse(command("set", {"key": "theme", "value": "red"}), "only postcard settings")
        self.assertNotIn("theme", deck.config)
        self.assertEqual(deck.saved, 4)

    def test_the_preview_follows_the_design(self):
        deck = self.deck(album_folder(self, 1))
        first = deck._postcard_preview_png()
        self.assertTrue(first.startswith(b"\x89PNG"))
        key = deck._postcard_preview_key()
        deck._postcard_setting("postcard_style", "airmail")
        self.assertNotEqual(deck._postcard_preview_key(), key)
        self.assertNotEqual(deck._postcard_preview_png(), first)

    def test_the_deck_serves_the_preview(self):
        server = HtmlDashboardServer(WEB)
        self.addCleanup(server.stop)
        server.postcards = PostcardAlbum(lambda: "")
        server.postcards.preview_source = lambda: b"\x89PNG preview"
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("GET", f"/media/postcard-preview/holo-1-1-1.png?token={server.token}")
        reply = connection.getresponse()
        self.assertEqual((reply.status, reply.getheader("Content-Type"), reply.read()), (200, "image/png", b"\x89PNG preview"))

    def test_studio_keeps_only_the_overlay_options(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        studio = html[html.index('data-studio-settings="postcard_hud"'):]
        studio = studio[:studio.index("</section>")]
        for kept in ("postcard_hold_s", "postcard_size", "postcard_photo"):
            self.assertIn(kept, studio)
        for moved in ("postcard_style", "postcard_facts", "postcard_note", "postcard_doing"):
            self.assertNotIn(moved, html, "on the Postcards page now")
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        for moved in ("screenshot_captions", "screenshot_postcards", "postcards_path"):
            self.assertNotIn(f'key: "{moved}"', app, "not in Settings twice")
        self.assertIn('data-page="postcards">POSTCARDS</button>', app)


class MinimapPageTests(unittest.TestCase):
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

    def open(self, model, reduced=False):
        page = self.browser.new_page(viewport={"width": 240, "height": 280})
        self.addCleanup(page.close)

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/file":
                body, kind = minimap_file("regions")
                route.fulfill(body=body, content_type=kind)
                return
            file = WEB / path.lstrip("/")
            if not file.is_file():
                route.fulfill(status=404, body="")
            elif file.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(file))
        page.route("http://map.test/**", serve)
        page.goto("http://map.test/galaxy_minimap/index.html?token=t&overlay=galaxy-minimap")
        page.wait_for_function("Boolean(window.renderMinimap) && window.__minimap.ready()", timeout=20000)
        self.show(page, model, reduced)
        return page

    @staticmethod
    def show(page, model, reduced=False):
        page.evaluate("([m, r]) => renderMinimap({theme: arguments[0], effects: {text_scale: 1, reduced_motion: r}, minimap: m})"
                      .replace("arguments[0]", str(THEME).replace("'", '"')), [model, reduced])

    def model(self, x, route=None):
        return build_minimap_model([row(0, 0.0, 0.0, "Sol"), row(1, x, x, "Here")], position=[x, 0.0, x],
                                   system="Here", route_entries=route)

    def test_no_scoop_badge(self):
        route = [stop("Here", 1000, "L"), stop("A", 1100, "T"), stop("B", 1200, "K")]
        page = self.open(self.model(1000.0, route))
        self.assertEqual(page.locator("#scoop").count(), 0, "the Nav HUD shows fuel stops; the minimap doesn't")
        self.assertNotIn("SCOOP", page.inner_text("body"))

    def test_the_spansh_trip(self):
        from voidcompass.overlays.galaxy_minimap_hud import spansh_trip
        plot = {"waypoints": [{"system": "Here" if i == 0 else f"N{i}", "coords": [1000.0, 0.0, 1000.0 + 800 * i],
                               "neutron": True, "jumps": 0 if i == 0 else 3} for i in range(6)]}
        model = build_minimap_model([row(0, 0.0, 0.0, "Sol"), row(1, 1000.0, 1000.0, "Here")], position=[1000.0, 0.0, 1000.0],
                                    system="Here", trip=spansh_trip([], plot, [1000.0, 0.0, 1000.0], "Here"))
        page = self.open(model)
        self.assertEqual(page.inner_text("#facts .trip"), "▸ 4,000 LY · 15 JUMPS")
        # Framed in "Your route": the trip's end is on the map.
        end = page.evaluate("window.__minimap.project(window.__minimap.bounds(), 240, 240, 1000, 5000)")
        self.assertTrue(0 <= end[0] <= 240 and 0 <= end[1] <= 240, end)

    def test_a_jump_glides_and_settles(self):
        page = self.open(self.model(1000.0))
        self.show(page, self.model(3000.0))
        page.wait_for_timeout(200)
        moving = page.evaluate("() => document.getElementById('galaxy').style.transform")
        self.assertIn("scale", moving, "the galaxy moves as it stands while gliding")
        page.wait_for_timeout(900)
        self.assertEqual(page.evaluate("() => document.getElementById('galaxy').style.transform"), "", "then it's drawn afresh")
        still = self.open(self.model(1000.0), reduced=True)
        self.show(still, self.model(3000.0), reduced=True)
        page.wait_for_timeout(50)
        self.assertEqual(still.evaluate("() => document.getElementById('galaxy').style.transform"), "", "reduced motion: no glide")


if __name__ == "__main__":
    unittest.main()
