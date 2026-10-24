"""5.6.3: the postcard editor. The card is drawn in the page and saved as
exactly what it shows (over the postcard or as a new one), with its design
kept so it opens again as you left it; any screenshot can be made into a
postcard; the album has groups, a timeline, today's card and a slideshow."""

import base64
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.overlays import postcard_picture
from voidcompass.overlays.postcards import postcard_card
from voidcompass.services.postcard_album import PostcardAlbum
from voidcompass.services.screenshot_album import ScreenshotAlbum

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def png_bytes(colour=(200, 40, 40)):
    out = io.BytesIO()
    Image.new("RGBA", (64, 48), colour + (255,)).save(out, "PNG")
    return out.getvalue()


def make_deck(postcards=1):
    root = Path(tempfile.mkdtemp())
    folder, shots = root / "postcards", root / "shots"
    shots.mkdir(parents=True)
    for index in range(postcards):
        card = postcard_card({"timestamp": f"2026-10-1{index}T20:14:00Z", "System": f"Hatchooe {index}"}, state="LANDED", region="Inner Orion Spur")
        card["note"] = "Wish you were here."
        picture = Image.new("RGB", (640, 360), (10, 40 + index * 30, 90))
        path = postcard_picture.save_postcard_picture(card, picture, str(folder), {}, stamp=f"2026-10-1{index} 20-14-00", postmark=True)
        postcard_picture.keep_card(path, card, picture, {"style": "polaroid", "theme": {}, "postmark": True})
    Image.new("RGB", (640, 360), (20, 160, 60)).save(shots / "Colonia_2026-10-20_18-33-18.png")

    class Deck(DashboardKeepsakesMixin):
        pass

    deck = Deck()
    deck.config = {"postcards_path": str(folder), "screenshots_path": str(shots), "postcard_themes": {}}
    album = PostcardAlbum(lambda: str(folder))
    shot_album = ScreenshotAlbum(lambda: str(shots))
    deck.postcard_album = lambda: album
    deck.screenshot_album = lambda: shot_album
    deck._ui_post = lambda callback, *args, key=None, **kwargs: callback(*args, **kwargs)
    deck._schedule_html_dashboard_publish = lambda immediate=False: None
    return deck, album, shot_album, folder


def sidecar(folder, card_id, album):
    path = album.path(card_id)
    stem = os.path.splitext(os.path.basename(path))[0]
    with open(Path(folder) / ".cards" / f"{stem}.json", encoding="utf-8") as handle:
        return json.load(handle)


class AlbumTests(unittest.TestCase):
    def test_a_design_saved_over_the_postcard_and_as_a_new_one(self):
        deck, album, _shots, folder = make_deck()
        self.addCleanup(shutil.rmtree, folder.parent, True)
        card_id = album.rows()[0]["id"]
        design = {"v": 2, "base": "holo", "layers": [{"id": "s1", "kind": "sticker", "sticker": "o7"}]}
        self.assertEqual(album.save_design(card_id, png_bytes(), design), card_id)
        self.assertEqual(album.full(card_id), png_bytes(), "the editor's drawing is the picture")
        self.assertEqual(sidecar(folder, card_id, album)["settings"]["design"], design)
        new_id = album.save_design(card_id, png_bytes((10, 200, 10)), {**design, "base": "vintage"}, as_new=True)
        self.assertNotEqual(new_id, card_id)
        self.assertEqual(len(album.rows()), 2)
        self.assertEqual(sidecar(folder, new_id, album)["settings"]["design"]["base"], "vintage")
        self.assertTrue(album.photo(new_id).startswith(b"\xff\xd8"), "the new one has its own copy of the photo")
        self.assertIsNone(album.save_design(card_id, b"GIF89a", design), "only a PNG")
        self.assertIsNone(album.save_design("0" * 16, png_bytes(), design))

    def test_the_editor_is_handed_the_card(self):
        deck, album, shots, folder = make_deck()
        self.addCleanup(shutil.rmtree, folder.parent, True)
        card_id = album.rows()[0]["id"]
        self.assertTrue(deck._handle_postcards_command("edit", {"id": card_id}))
        editing = deck._html_postcards_workspace()["editing"]
        self.assertEqual(editing["info"]["title"], "Hatchooe 0")
        self.assertEqual(editing["info"]["region"], "Inner Orion Spur")
        self.assertTrue(editing["info"]["postmark"])
        self.assertEqual(set(editing["looks"]), {"polaroid", "airmail", "holo", "vintage"})
        self.assertRegex(editing["looks"]["airmail"]["paper"], r"^#[0-9a-f]{6}$")
        self.assertEqual(editing["shots"][0]["id"], shots.rows()[0]["id"])
        self.assertIsNone(editing["design"], "never edited: the editor lays it out")
        row = deck._html_postcards_workspace()["rows"][0]
        self.assertEqual((row["system"], row["region"], row["note"], row["designed"]), ("Hatchooe 0", "Inner Orion Spur", "Wish you were here.", False))

    def test_saved_through_the_deck_and_reopened_as_left(self):
        deck, album, _shots, folder = make_deck()
        self.addCleanup(shutil.rmtree, folder.parent, True)
        card_id = album.rows()[0]["id"]
        design = {"v": 2, "base": "airmail", "layers": []}
        answer = deck._postcard_design_save({"id": card_id, "mode": "replace", "design": design, "png": base64.b64encode(png_bytes()).decode()})
        self.assertEqual(answer, {"ok": True, "id": card_id})
        self.assertFalse(deck._postcard_design_save({"id": card_id, "design": design, "png": "not base64!"})["ok"])
        self.assertFalse(deck._postcard_design_save({"id": card_id, "design": "nope", "png": ""})["ok"])
        deck._handle_postcards_command("edit", {"id": card_id})
        self.assertEqual(deck._html_postcards_workspace()["editing"]["design"], design)
        self.assertTrue(deck._html_postcards_workspace()["rows"][0]["designed"])

    def test_a_new_picture_from_the_screenshots(self):
        deck, album, shots, folder = make_deck()
        self.addCleanup(shutil.rmtree, folder.parent, True)
        card_id = album.rows()[0]["id"]
        before = album.photo(card_id)
        self.assertTrue(deck._handle_postcards_command("edit_photo", {"id": card_id, "shot": shots.rows()[0]["id"]}))
        after = album.photo(card_id)
        self.assertNotEqual(before, after)
        self.assertGreater(Image.open(io.BytesIO(after)).getpixel((10, 10))[1], 120, "the green screenshot")
        self.assertFalse(deck._handle_postcards_command("edit_photo", {"id": card_id, "shot": "f" * 16}))

    def test_any_screenshot_made_into_a_postcard_opens_in_the_editor(self):
        deck, album, shots, folder = make_deck(postcards=0)
        self.addCleanup(shutil.rmtree, folder.parent, True)
        self.assertTrue(deck._handle_screenshots_command("postcard", {"id": shots.rows()[0]["id"]}))
        rows = album.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Colonia", "the place from the screenshot's name")
        data = deck._html_postcards_workspace()
        self.assertEqual(data["open_next"], rows[0]["id"])
        self.assertTrue(data["rows"][0]["editable"])
        self.assertTrue(deck._handle_postcards_command("opened", {}))
        self.assertEqual(deck._html_postcards_workspace()["open_next"], "")
        self.assertFalse(deck._handle_screenshots_command("postcard", {"id": "0" * 16}))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.deck, self.album, _shots, folder = make_deck()
        self.addCleanup(shutil.rmtree, folder.parent, True)
        self.server = HtmlDashboardServer(WEB / "dashboard", image_root=ROOT / "assets" / "images")
        self.addCleanup(self.server.stop)
        self.server.postcards = self.album
        self.server.postcard_saver = self.deck._postcard_design_save
        self.card_id = self.album.rows()[0]["id"]

    def post(self, body, token=True, origin=None):
        url = f"{self.server.origin}/api/postcard-save" + (f"?token={self.server.token}" if token else "")
        request = Request(url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
        if origin:
            request.add_header("Origin", origin)
        try:
            with urlopen(request, timeout=5) as reply:
                return reply.status, json.loads(reply.read())
        except HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_the_editor_saves_through_its_own_route(self):
        body = {"id": self.card_id, "mode": "new", "design": {"v": 2, "layers": []}, "png": base64.b64encode(png_bytes()).decode()}
        status, answer = self.post(body)
        self.assertEqual((status, answer["ok"]), (200, True))
        self.assertEqual(len(self.album.rows()), 2)
        self.assertEqual(self.post(body, token=False)[0], 403)
        self.assertEqual(self.post(body, origin="http://evil.example")[0], 403)

    def test_the_photo_is_served_for_the_editor(self):
        with urlopen(f"{self.server.origin}/media/postcard-photo/{self.card_id}.jpg?token={self.server.token}", timeout=5) as reply:
            self.assertEqual(reply.headers["Content-Type"], "image/jpeg")
            self.assertTrue(reply.read().startswith(b"\xff\xd8"))
        with self.assertRaises(HTTPError):
            urlopen(f"{self.server.origin}/media/postcard-photo/{self.card_id}.jpg", timeout=5)


class EditorPageTests(unittest.TestCase):
    """The Postcards page in a real browser: the album, the editor, saving, the slideshow."""

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

    def open_page(self, postcards=3):
        from tests.test_dashboard_overview_visuals import overview_state
        self.deck, self.album, self.shots, folder = make_deck(postcards)
        self.addCleanup(shutil.rmtree, folder.parent, True)
        state = overview_state()
        current = {"page": "postcards", "turn": 0}

        def publish(page=None):
            page = page or current["page"]
            data = self.deck._html_postcards_workspace() if page == "postcards" else self.deck._html_screenshots_workspace()
            current["turn"] += 1
            server.publish({**state, "turn": current["turn"], "workspace": {"page": page, "ready": True, "data": data}})

        def command(payload):
            if payload.get("action") == "page_changed":
                current["page"] = payload.get("page")
                publish()
                return True
            if payload.get("action") != "workspace":
                return True
            handler = self.deck._handle_postcards_command if payload.get("page") == "postcards" else self.deck._handle_screenshots_command
            done = handler(payload.get("operation"), payload)
            publish()
            return bool(done)

        server = HtmlDashboardServer(WEB / "dashboard", image_root=ROOT / "assets" / "images", command_callback=command)
        self.addCleanup(server.stop)
        server.postcards, server.screenshots, server.postcard_saver = self.album, self.shots, self.deck._postcard_design_save
        self.publish, self.current = publish, current
        context = self.browser.new_context(viewport={"width": 1600, "height": 950}, bypass_csp=True)
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        # The studio's own preview isn't served here: only page errors count.
        self.addCleanup(lambda: self.assertEqual(errors, []))
        page.goto(server.url)
        page.wait_for_selector("body.ready", timeout=15000)
        page.locator('.nav-item[data-page="postcards"]').click()
        page.wait_for_timeout(200)
        publish("postcards")
        page.wait_for_selector(".pc-grid .pc-tile")
        return page

    def editor(self, page):
        return page.evaluate("window.voidcompassPostcardEditor.state()")

    def test_the_album_has_today_a_timeline_and_groups(self):
        page = self.open_page(3)
        self.assertTrue(page.locator("#pc-hero").is_visible(), "today's card")
        self.assertEqual(page.locator(".pc-month h4").count(), 1, "one month")
        page.select_option("#pc-group", "day")
        page.wait_for_function("document.querySelectorAll('.pc-month h4').length === 3")
        page.select_option("#pc-group", "region")
        page.wait_for_function("document.querySelectorAll('.pc-month h4').length === 1")
        self.assertIn("INNER ORION SPUR", page.locator(".pc-month h4").first.inner_text())
        page.fill("#pc-find", "orion spur")
        page.wait_for_function("document.querySelectorAll('.pc-tile').length === 3", timeout=3000)

    def test_edit_drag_undo_add_and_save(self):
        page = self.open_page(1)
        page.locator(".pc-grid .pc-tile button[data-postcard]").first.click()
        page.click("#pc-edit")
        page.wait_for_function("window.voidcompassPostcardEditor.state() && window.voidcompassPostcardEditor.state().photo", timeout=8000)
        design = self.editor(page)["design"]
        roles = {layer.get("role") for layer in design["layers"]}
        self.assertTrue({"greeting", "title", "note", "signed", "postmark", "date"} <= roles)
        title = next(layer for layer in design["layers"] if layer.get("role") == "title")
        x, y = page.evaluate(f"window.voidcompassPostcardEditor.at('{title['id']}')")
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 50, y - 80, steps=6)
        page.mouse.up()
        moved = next(layer for layer in self.editor(page)["design"]["layers"] if layer["id"] == title["id"])
        self.assertLess(moved["y"], title["y"] - 40, "dragged up")
        self.assertEqual(self.editor(page)["selected"], title["id"])
        page.keyboard.press("Control+z")
        back = next(layer for layer in self.editor(page)["design"]["layers"] if layer["id"] == title["id"])
        self.assertEqual((back["x"], back["y"]), (title["x"], title["y"]), "undone")
        page.keyboard.press("Control+y")
        page.click('[data-pe-tab="add"]')
        page.click('[data-pe-sticker="thargoid"]')
        page.click('[data-pe-journal="0"]')
        page.click('[data-pe-tab="look"]')
        page.click('[data-pe-base="vintage"]')
        state = self.editor(page)
        self.assertEqual(state["base"], "vintage")
        self.assertEqual(state["layers"], len(design["layers"]) + 2)
        self.assertTrue(state["dirty"])
        page.keyboard.press("Control+s")
        page.wait_for_function("!window.voidcompassPostcardEditor.state().dirty", timeout=10000)
        card_id = self.album.rows()[0]["id"]
        kept = sidecar(self.album.folder(), card_id, self.album)["settings"]["design"]
        self.assertEqual(kept["base"], "vintage")
        self.assertIn("thargoid", [layer.get("sticker") for layer in kept["layers"]])
        with Image.open(io.BytesIO(self.album.full(card_id))) as saved:
            self.assertGreater(saved.width, 1500, "drawn at full size")
            self.assertEqual(saved.mode, "RGBA")
        # Closed and opened again: just as it was left.
        page.click('[data-pe="close"]')
        page.wait_for_function("window.voidcompassPostcardEditor.state() === null")
        page.click("#pc-edit")
        page.wait_for_function("window.voidcompassPostcardEditor.state() && window.voidcompassPostcardEditor.state().base === 'vintage'", timeout=8000)
        self.assertEqual(self.editor(page)["layers"], state["layers"])

    def test_a_screenshot_becomes_a_postcard_in_the_editor(self):
        page = self.open_page(1)
        page.locator('.nav-item[data-page="screenshots"]').click()
        page.wait_for_timeout(200)
        self.publish("screenshots")
        page.wait_for_selector(".album-tile button[data-shot]")
        page.locator(".album-tile button[data-shot]").first.click()
        page.click('[data-shots="postcard"]')
        page.wait_for_timeout(300)
        self.publish("postcards")
        page.wait_for_function("window.voidcompassPostcardEditor.state() !== null", timeout=8000)
        self.assertEqual(len(self.album.rows()), 2)
        self.assertEqual(self.editor(page)["id"], self.deck._html_postcards_workspace()["rows"][0]["id"])

    def test_the_slideshow(self):
        page = self.open_page(3)
        page.click(".pc-toolbar [data-pc-show]")
        page.wait_for_selector(".pc-show .pc-show-card")
        self.assertEqual(page.evaluate("window.voidcompassPostcardShow.state().count"), 3)
        page.keyboard.press("ArrowRight")
        self.assertEqual(page.evaluate("window.voidcompassPostcardShow.state().at"), 1)
        page.keyboard.press(" ")
        self.assertFalse(page.evaluate("window.voidcompassPostcardShow.state().playing"))
        page.keyboard.press("Escape")
        page.wait_for_function("window.voidcompassPostcardShow.state() === null")


if __name__ == "__main__":
    unittest.main()
