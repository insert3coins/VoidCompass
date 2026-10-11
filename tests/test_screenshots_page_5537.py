"""The Screenshots page (5.5.3.7): the screenshot folder as an album, like
the Postcards page."""
from __future__ import annotations

import http.client
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
from voidcompass.services import postcard_album
from voidcompass.services.screenshot_album import ScreenshotAlbum

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def shots_folder(test):
    """A screenshot folder: converted PNGs, one with a caption, a BMP Elite
    has just written, a high-res shot and something that isn't a picture."""
    from PIL import Image
    folder = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, folder, True)
    files = [("Colonia_2026-10-12_20-14-00.png", 500), ("Colonia_2026-10-12_20-14-00_2.png", 400),
             ("Unknown_2026-10-11_10-00-00.png", 300), ("HighResScreenShot_2026-10-10_09-00-00.png", 200),
             ("Screenshot_0004.bmp", 600)]
    for name, at in files:
        path = os.path.join(folder, name)
        Image.new("RGB", (64, 36), (20, 60, 120)).save(path, "BMP" if name.endswith(".bmp") else "PNG")
        os.utime(path, (1000 + at, 1000 + at))
    with open(os.path.join(folder, "Colonia_2026-10-12_20-14-00.txt"), "w", encoding="utf-8") as handle:
        handle.write("Greetings from Jaques Station\nDocked\n")
    with open(os.path.join(folder, "notes.txt"), "w", encoding="utf-8") as handle:
        handle.write("not a picture")
    return folder


class AlbumTests(unittest.TestCase):
    def test_every_picture_newest_first_by_system(self):
        album = ScreenshotAlbum(lambda: shots_folder(self))
        rows = album.rows()
        self.assertEqual([row["title"] for row in rows],
                         ["Not converted yet", "Colonia", "Colonia", "Unknown system", "High-res screenshot"])
        self.assertEqual(album.total, 5)
        self.assertEqual([row["kind"] for row in rows], ["BMP", "PNG", "PNG", "PNG", "PNG"])
        self.assertEqual(rows[1]["caption"], "Greetings from Jaques Station\nDocked", "its postcard in words")
        self.assertEqual(rows[2]["caption"], "")
        self.assertEqual(rows[3]["system"], "", "the converter's Unknown is no system")
        self.assertEqual((rows[4]["high_res"], rows[4]["system"]), (True, ""))
        self.assertNotIn("notes.txt", [row["file"] for row in rows])

    def test_the_pictures_as_they_are(self):
        album = ScreenshotAlbum(lambda: shots_folder(self))
        rows = album.rows()
        data, kind = album.picture(rows[0]["id"])
        self.assertEqual((kind, data[:2]), ("image/bmp", b"BM"))
        data, kind = album.picture(rows[1]["id"])
        self.assertEqual((kind, data[:4]), ("image/png", b"\x89PNG"))
        self.assertEqual(album.picture("1" * 16), (None, ""))
        self.assertTrue(album.thumb(rows[0]["id"]).startswith(b"\xff\xd8"), "a BMP has a thumbnail too")

    def test_only_the_newest_are_listed(self):
        album = ScreenshotAlbum(lambda: shots_folder(self))
        with patch.object(postcard_album, "MAX_SHOWN", 2):
            self.assertEqual(len(album.rows()), 2)
        self.assertEqual(album.total, 5, "but the count is all of them")

    def test_postcards_stay_pngs_only(self):
        self.assertEqual(postcard_album.PostcardAlbum.EXTENSIONS, (".png",))


class PageTests(unittest.TestCase):
    def deck(self, folder):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = {"screenshots_path": folder, "screenshots_enabled": True}
        deck.opened = 0

        def opener():
            deck.opened += 1
        deck.open_screenshots_folder = opener
        return deck

    def test_the_screenshots_page(self):
        folder = shots_folder(self)
        deck = self.deck(folder)
        data = deck._html_screenshots_workspace()
        self.assertEqual((len(data["rows"]), data["total"], data["folder"], data["found"], data["converting"]),
                         (5, 5, folder, True, True))
        self.assertTrue(deck._handle_screenshots_command("open_folder", {}))
        self.assertEqual(deck.opened, 1)
        with patch("voidcompass.services.postcard_album.copy_dib", return_value=True):
            self.assertTrue(deck._handle_screenshots_command("copy", {"id": data["rows"][1]["id"]}))
        self.assertFalse(deck._handle_screenshots_command("delete", {"id": data["rows"][1]["id"]}), "nothing is deleted here")
        self.assertEqual(len(os.listdir(folder)), 7)

    def test_a_missing_folder(self):
        data = self.deck(os.path.join(tempfile.gettempdir(), "no-such-elite-folder-5537"))._html_screenshots_workspace()
        self.assertEqual((data["rows"], data["found"]), ([], False))

    def test_the_deck_serves_them_with_its_token(self):
        server = HtmlDashboardServer(WEB)
        self.addCleanup(server.stop)
        server.screenshots = ScreenshotAlbum(lambda: shots_folder(self))
        rows = server.screenshots.rows()
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        self.addCleanup(connection.close)
        for path, kind in ((f"/media/shot/{rows[1]['id']}", "image/png"), (f"/media/shot/{rows[0]['id']}", "image/bmp"),
                           (f"/media/shot-thumb/{rows[1]['id']}.jpg", "image/jpeg")):
            connection.request("GET", f"{path}?token={server.token}")
            reply = connection.getresponse()
            body = reply.read()
            self.assertEqual((reply.status, reply.getheader("Content-Type")), (200, kind), path)
            self.assertTrue(body)
        connection.request("GET", f"/media/shot/{rows[1]['id']}")
        reply = connection.getresponse()
        reply.read()
        self.assertEqual(reply.status, 403, "only with the token")
        connection.request("GET", f"/media/shot/{'1' * 16}?token={server.token}")
        reply = connection.getresponse()
        reply.read()
        self.assertEqual(reply.status, 404)

    def test_it_is_a_deck_page(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="screenshots"', html)
        self.assertIn('data-page-name="screenshots"', html)
        self.assertIn('href="screenshots.css"', html)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("screenshots: (data) => renderScreenshots(data, WORKSHOP_UI)", app)
        self.assertIn('<button type="button" data-page="screenshots">SCREENSHOTS</button>', app, "linked from Settings")
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('"screenshots": getattr(self, "_html_screenshots_workspace", None)', dashboard)
        page = (WEB / "dashboard" / "screenshots.js").read_text(encoding="utf-8")
        self.assertIn("/media/shot/", page)
        self.assertNotIn("delete", page.lower(), "the page never deletes a screenshot")


if __name__ == "__main__":
    unittest.main()
