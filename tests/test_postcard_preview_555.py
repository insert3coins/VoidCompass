"""5.5.5: the postcard studio's preview no longer locks the system up. The
screenshot is read once and kept small, filtered at postcard size, and the
previews render one at a time with only the newest asked for."""
from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

from voidcompass.dashboard import dashboard_keepsakes_mixin as keepsakes
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays import postcard_picture
from voidcompass.overlays.postcards import postcard_card

ROOT = Path(__file__).resolve().parents[1]


class PictureTests(unittest.TestCase):
    def test_read_once_and_kept_small(self):
        path = Path(tempfile.mkdtemp()) / "big.png"
        Image.new("RGB", (3840, 2160), (40, 80, 120)).save(path)
        with patch.object(postcard_picture, "open_picture", wraps=postcard_picture.open_picture) as opened:
            first = postcard_picture.open_picture_small(str(path), 1280)
            second = postcard_picture.open_picture_small(str(path), 1280)
        self.assertEqual(opened.call_count, 1, "decoded once")
        self.assertEqual(first.size, (1280, 720))
        self.assertIsNot(first, second, "a copy each time: a render can't spoil the kept one")
        self.assertIsNone(postcard_picture.open_picture_small(str(path) + ".missing"))

    def test_the_filter_works_at_postcard_size(self):
        sizes = []
        real = postcard_picture._filtered

        def recorded(picture, photo_filter, style):
            sizes.append(picture.size)
            return real(picture, photo_filter, style)
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe"}, state="LANDED")
        with patch.object(postcard_picture, "_filtered", recorded):
            postcard_picture.render_postcard(card, Image.new("RGB", (7680, 4320)), {}, width=400, theme={"filter": "sepia"})
        self.assertEqual(sizes, [(400, 225)], "never the 8K screenshot itself")


class PreviewTests(unittest.TestCase):
    def deck(self):
        deck = DashboardKeepsakesMixin()
        deck.config = {"screenshots_path": tempfile.mkdtemp()}
        return deck

    def test_one_render_at_a_time(self):
        deck = self.deck()
        busy, most = [0], [0]

        def render():
            busy[0] += 1
            most[0] = max(most[0], busy[0])
            time.sleep(.05)
            busy[0] -= 1
            return b"png"
        deck._postcard_preview_render = render
        threads = [threading.Thread(target=deck._postcard_preview_png) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertEqual(most[0], 1)
        self.assertIsInstance(keepsakes._PREVIEW_LOCK, type(threading.Lock()))

    def test_the_same_edit_is_drawn_once(self):
        deck = self.deck()
        deck._postcard_edit_draft = {"id": "abc", "values": {"title": "Home"}}
        calls = []

        def edited(card_id, values):
            calls.append(card_id)
            card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Home"}, state="LANDED")
            return "x.png", card, None, "polaroid", {}, False, {}
        deck._postcard_edited = edited
        first, second = deck._postcard_edit_preview(), deck._postcard_edit_preview()
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)
        deck._postcard_edit_draft = {"id": "abc", "values": {"title": "Away"}}
        deck._postcard_edit_preview()
        self.assertEqual(len(calls), 2, "a change draws it again")

    def test_the_newest_screenshot_is_looked_for_only_now_and_then(self):
        deck = self.deck()
        folder = Path(deck.config["screenshots_path"])
        Image.new("RGB", (2560, 1440)).save(folder / "one.png")
        with patch.object(keepsakes.os, "listdir", wraps=keepsakes.os.listdir) as listed:
            for _ in range(5):
                picture = deck._postcard_preview_picture()
        self.assertEqual(listed.call_count, 1)
        self.assertLessEqual(max(picture.size), 1280)


class PageTests(unittest.TestCase):
    def test_one_preview_on_its_way(self):
        page = (ROOT / "web" / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn("function loadPreview(img, src)", page)
        self.assertIn('loadPreview(ui.byId("pc-preview-img"), previewSrc())', page)
        self.assertIn("loadPreview(ui.byId(\"pc-full\")", page)


if __name__ == "__main__":
    unittest.main()
