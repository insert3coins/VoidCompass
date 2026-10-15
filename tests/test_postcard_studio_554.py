"""5.5.4: the Postcards page rebuilt (album, studio, keeping), the postmark,
the studio's live preview, a saved postcard edited with its own preview and
a new picture, and older postcards made editable from the journal."""
from __future__ import annotations

import datetime
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from PIL import Image

from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays import postcard_picture
from voidcompass.overlays.postcard_restore import ScreenshotIndex, find_picture, saved_at
from voidcompass.overlays.postcards import postcard_card, postcard_options

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def photo(colour=(10, 40, 90)):
    return Image.new("RGB", (320, 180), colour)


def utc(local_seconds):
    return datetime.datetime.fromtimestamp(local_seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Album:
    def __init__(self, folder):
        self._folder = folder

    def folder(self):
        return self._folder

    def rows(self):
        from voidcompass.services.postcard_album import PostcardAlbum
        return PostcardAlbum(lambda: self._folder).rows()

    def path(self, card_id):
        for row in self.rows():
            if row["id"] == card_id:
                return os.path.join(self._folder, row["file"])
        return None


def deck_for(folder, **config):
    deck = DashboardKeepsakesMixin()
    deck.config = {"postcards_path": folder, **config}
    deck.postcard_hud = None
    deck._ui_post = lambda callback, *args, key=None: callback(*args)
    album = Album(folder)
    deck.postcard_album = lambda: album
    return deck, album


class PostmarkTests(unittest.TestCase):
    def test_stamped_on_the_paper_and_a_setting(self):
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe", "Body": "Hatchooe AB 3"}, state="LANDED")
        card["note"] = "Still here."
        plain = postcard_picture.render_postcard(card, photo(), {}, width=400)
        stamped = postcard_picture.render_postcard(card, photo(), {}, width=400, postmark=True)
        self.assertNotEqual(plain.tobytes(), stamped.tobytes())
        self.assertGreaterEqual(stamped.height, plain.height, "room is made beside the note")
        self.assertTrue(postcard_options({})["postmark"], "on by default")
        self.assertFalse(postcard_options({"postcard_postmark": False})["postmark"])
        self.assertIn("postcard_postmark", config_module.PROFILE_SETTINGS)
        overlay = (WEB / "postcards" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function postmark(card)", overlay)
        self.assertIn('classList.toggle("postmarked", options.postmark !== false)', overlay)
        self.assertIn(".card.postmarked .postmark", (WEB / "postcards" / "styles.css").read_text(encoding="utf-8"))

    def test_saved_postcards_keep_their_postmark(self):
        folder = tempfile.mkdtemp()
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe"}, state="LANDED")
        path = postcard_picture.save_postcard_picture(card, photo(), folder, {}, postmark=True)
        postcard_picture.keep_card(path, card, photo(), {"style": "polaroid", "theme": {}, "postmark": True})
        deck, album = deck_for(folder)
        card_id = album.rows()[0]["id"]
        self.assertTrue(deck._postcard_edit_open(card_id))
        self.assertTrue(deck._postcard_editing["postmark"])
        self.assertTrue(deck._postcard_edit_save(card_id, {"title": "Home", "postmark": False}))
        self.assertFalse(postcard_picture.kept_card(path)[1]["postmark"])


class TextSizeTests(unittest.TestCase):
    def test_the_lettering_the_note_and_the_details(self):
        self.assertEqual(postcard_options({})["sizes"], {"lettering": 1.0, "note": 1.0, "details": 1.0})
        options = postcard_options({"postcard_size_note": 150, "postcard_size_details": "115", "postcard_size_lettering": 999})
        self.assertEqual(options["sizes"], {"lettering": 1.0, "note": 1.5, "details": 1.15}, "only the list's sizes")
        for part in ("lettering", "note", "details"):
            self.assertIn(f"postcard_size_{part}", config_module.PROFILE_SETTINGS)
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe"}, state="LANDED")
        card["note"] = "A long note, long enough to wrap onto a second line or a third at the larger size."
        plain = postcard_picture.render_postcard(card, photo(), {}, width=400)
        larger = postcard_picture.render_postcard(card, photo(), {}, width=400, sizes={"note": 1.5, "details": 1.3})
        self.assertGreater(larger.height, plain.height, "the card grows with its words")

    def test_set_in_the_studio_and_per_postcard(self):
        folder = tempfile.mkdtemp()
        deck, album = deck_for(folder)
        deck._persist_config = lambda: None
        self.assertTrue(deck._postcard_setting("postcard_size_note", "130"))
        self.assertEqual(deck.config["postcard_size_note"], 130)
        self.assertFalse(deck._postcard_setting("postcard_size_note", "120"), "only the list's sizes")
        self.assertEqual(deck._html_postcards_workspace()["settings"]["postcard_size_note"], 130)
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe"}, state="LANDED")
        path = postcard_picture.save_postcard_picture(card, photo(), folder, {}, sizes={"note": 1.3})
        postcard_picture.keep_card(path, card, photo(), {"style": "polaroid", "theme": {}, "sizes": {"note": 1.3}})
        card_id = album.rows()[0]["id"]
        self.assertTrue(deck._postcard_edit_open(card_id))
        self.assertEqual(deck._postcard_editing["sizes"], {"lettering": 100, "note": 130, "details": 100})
        self.assertTrue(deck._postcard_edit_save(card_id, {"title": "Hatchooe", "size_lettering": "150"}))
        self.assertEqual(postcard_picture.kept_card(path)[1]["sizes"], {"note": 1.3, "lettering": 1.5})

    def test_the_overlay_and_the_page(self):
        overlay = (WEB / "postcards" / "app.js").read_text(encoding="utf-8")
        self.assertIn("`--pc-${part}`", overlay)
        css = (WEB / "postcards" / "styles.css").read_text(encoding="utf-8")
        for part in ("lettering", "note", "details"):
            self.assertIn(f"var(--pc-{part}, 1)", css)
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn('data-postcard-setting="postcard_size_${part}"', page)
        self.assertIn('name="size_${part}"', page)


class StudioPreviewTests(unittest.TestCase):
    def test_a_theme_tried_out_before_it_is_saved(self):
        deck, _album = deck_for(tempfile.mkdtemp(), postcard_style="polaroid")
        saved = deck._postcard_preview_key()
        self.assertTrue(deck._postcard_set_draft({"theme": {"base": "airmail", "greet": "#33ff66", "angle": 4}}))
        self.assertNotEqual(deck._postcard_preview_key(), saved, "the preview follows the draft")
        options = postcard_options(deck._postcard_preview_config())
        self.assertEqual((options["style"], options["theme"]["greet"]), ("airmail", "#33ff66"))
        self.assertEqual(deck.config["postcard_style"], "polaroid", "nothing saved")
        self.assertNotIn("postcard_themes", deck.config)
        self.assertTrue(deck._handle_postcards_command("draft_clear", {}))
        self.assertEqual(deck._postcard_preview_key(), saved)

    def test_a_saved_postcard_previewed_while_edited_and_given_a_new_picture(self):
        folder = tempfile.mkdtemp()
        card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe"}, state="LANDED")
        path = postcard_picture.save_postcard_picture(card, photo(), folder, {})
        postcard_picture.keep_card(path, card, photo(), {"style": "polaroid", "theme": {}})
        deck, album = deck_for(folder)
        card_id = album.rows()[0]["id"]
        self.assertTrue(deck._handle_postcards_command("edit_draft", {"id": card_id, "title": "Home", "note": "Back.",
                                                                       "postmark": True}))
        preview = deck._postcard_preview_png()
        self.assertTrue(preview.startswith(b"\x89PNG"))
        self.assertEqual(postcard_picture.kept_card(path)[0]["title"], "Hatchooe", "only a preview")
        deck._handle_postcards_command("edit_close", {})
        self.assertIsNone(deck._postcard_edit_preview())
        chosen = os.path.join(folder, "new.png")
        photo((200, 20, 20)).save(chosen)
        self.assertTrue(deck._handle_postcards_command("edit_picture", {"id": card_id, "path": chosen}))
        self.assertGreater(postcard_picture.kept_card(path)[2].getpixel((5, 5))[0], 150)
        self.assertFalse(deck._postcard_swap_picture(card_id, os.path.join(folder, "missing.png")))


class RestoreTests(unittest.TestCase):
    def test_older_postcards_given_their_card_back(self):
        folder, journals, shots = tempfile.mkdtemp(), tempfile.mkdtemp(), tempfile.mkdtemp()
        card = postcard_card({"timestamp": "2026-09-21T20:40:00Z", "System": "Colonia"}, state="")
        found = postcard_picture.save_postcard_picture(card, photo(), folder, {}, stamp="2026-09-21 22-40-05")
        lonely = postcard_picture.save_postcard_picture(dict(card, title="Beagle Point"), photo(), folder, {},
                                                        stamp="2026-08-02 12-00-00")
        self.assertFalse(postcard_picture.is_editable(found))
        taken = saved_at(os.path.basename(found)) - 4
        self.assertIsNotNone(taken)
        # The converter's PNG of the screenshot, and the journal's entries.
        Image.new("RGB", (64, 36), (0, 200, 0)).save(os.path.join(shots, time.strftime("Colonia_%Y-%m-%d_%H-%M-%S.png", time.localtime(taken))))
        opened = datetime.datetime.fromtimestamp(taken - 3600, datetime.timezone.utc)
        with open(os.path.join(journals, opened.strftime("Journal.%Y-%m-%dT%H%M%S.01.log")), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": utc(taken), "event": "FSDJump", "StarSystem": "Colonia",
                                     "StarPos": [-9530.5, -910.28, 19808.125]}) + "\n")
            handle.write(json.dumps({"timestamp": utc(taken), "event": "Screenshot", "Filename": "\\ED_Pictures\\Screenshot_0007.bmp",
                                     "System": "Colonia", "Body": "Colonia"}) + "\n")
        index = ScreenshotIndex(journals, [taken + 4])
        self.assertIsNotNone(index.near(taken + 4, "Colonia"))
        self.assertIsNone(index.near(taken + 4000, "Colonia"), "too long after")
        self.assertTrue(find_picture(shots, {"System": "Colonia"}, taken).endswith(".png"))

        deck, album = deck_for(folder, journal_path=journals, screenshots_path=shots)
        rows = album.rows()
        deck._postcard_restore_state = {"running": True, "done": 0, "total": 2, "pictures": 0, "found": 0}
        deck._postcard_restore_run(folder, rows)
        state = deck._postcard_restore_state
        self.assertEqual((state["running"], state["done"], state["found"], state["pictures"]), (False, 2, 1, 1))
        self.assertTrue(postcard_picture.is_editable(found) and postcard_picture.is_editable(lonely))
        card_back, settings, picture = postcard_picture.kept_card(found)
        self.assertEqual(card_back["title"], "Colonia")
        self.assertIn("Scutum", card_back["region"], "the region from the journal's star position")
        self.assertEqual((card_back["doing"], card_back["note"]), ("", ""))
        self.assertGreater(picture.getpixel((5, 5))[1], 150, "its own screenshot")
        self.assertTrue(settings["restored"])
        alone, _settings, no_picture = postcard_picture.kept_card(lonely)
        self.assertEqual(alone["title"], "Beagle Point", "from the file name")
        self.assertIsNone(no_picture)
        self.assertFalse(deck._postcard_restore_start(), "nothing left to restore")


class PageTests(unittest.TestCase):
    def test_album_studio_and_keeping(self):
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        for marker in ('[["album", "ALBUM"], ["studio", "STUDIO"], ["keeping", "KEEPING"]]', "data-pc-restore-all",
                       '"edit_draft"', 'send("draft", {theme: themeParams()})', "choose_picture_file", "data-pc-step",
                       "function monthOf", '"postcard_postmark"'):
            self.assertIn(marker, page)
        host = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard_host.py").read_text(encoding="utf-8")
        self.assertIn("def choose_picture_file(self):", host)
        css = (WEB / "dashboard" / "postcards.css").read_text(encoding="utf-8")
        for rule in (".pc-studio", ".pc-viewer", ".pc-restore", ".album-grid"):
            self.assertIn(rule, css, "the Screenshots page still shares the album rules")


if __name__ == "__main__":
    unittest.main()
