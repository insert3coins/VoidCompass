"""5.5.5: a postcard edited into your theme keeps it (its angle, its name
when reopened, its preview following the theme), and postcards can be
deleted, to the Recycle Bin."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays import postcard_picture, postcard_themes
from voidcompass.overlays.postcards import postcard_card
from voidcompass.services import postcard_album
from voidcompass.services.postcard_album import Favourites, PostcardAlbum

ROOT = Path(__file__).resolve().parents[1]


def saved_postcard():
    folder = tempfile.mkdtemp()
    card = postcard_card({"timestamp": "2026-10-11T20:14:00Z", "System": "Hatchooe"}, state="LANDED")
    photo = Image.new("RGB", (320, 180), (10, 40, 90))
    path = postcard_picture.save_postcard_picture(card, photo, folder, {})
    postcard_picture.keep_card(path, card, photo, {"style": "polaroid", "theme": {}})
    deck = DashboardKeepsakesMixin()
    theme = postcard_themes.normalize({"base": "vintage", "paper": "#00ff00", "angle": 6})
    deck.config = {"postcards_path": folder, "postcard_themes": {"Neon": theme}}
    album = PostcardAlbum(lambda: folder)
    deck.postcard_album = lambda: album
    return deck, album, path, album.rows()[0]["id"]


class ThemeEditTests(unittest.TestCase):
    def test_the_theme_keeps_its_angle_and_its_name(self):
        deck, _album, path, card_id = saved_postcard()
        deck._postcard_edit_open(card_id)
        # The page sends the angle only once the slider is moved.
        self.assertTrue(deck._postcard_edit_save(card_id, {"title": "Hatchooe", "style": "theme:Neon"}))
        settings = postcard_picture.kept_card(path)[1]
        self.assertEqual((settings["style"], settings["theme"]["angle"], settings["theme"]["name"]), ("vintage", 6.0, "Neon"))
        self.assertTrue(deck._postcard_edit_open(card_id))
        self.assertEqual(deck._postcard_editing["style"], "theme:Neon", "reopened in its theme, not its base")
        self.assertTrue(deck._postcard_edit_save(card_id, {"title": "Hatchooe", "style": "theme:Neon", "angle": "-3"}))
        self.assertEqual(postcard_picture.kept_card(path)[1]["theme"]["angle"], -3.0, "moved: your angle")

    def test_a_theme_in_use_knows_its_name(self):
        theme = postcard_themes.normalize({"base": "holo"})
        self.assertEqual(postcard_themes.chosen({"postcard_themes": {"Night run": theme}, "postcard_style": "theme:Night run"})[1]["name"],
                         "Night run")

    def test_the_preview_follows_a_theme_changed_in_the_studio(self):
        deck, _album, _path, card_id = saved_postcard()
        deck._postcard_set_edit_draft(card_id, {"title": "Hatchooe", "style": "theme:Neon"})
        first = deck._postcard_edit_preview()
        deck.config["postcard_themes"]["Neon"] = postcard_themes.normalize({"base": "vintage", "paper": "#ff0000"})
        self.assertNotEqual(deck._postcard_edit_preview(), first)

    def test_the_page_sends_the_angle_only_when_moved(self):
        page = (ROOT / "web" / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn('if (form.dataset.angleMoved !== "1") delete values.angle;', page)
        self.assertIn("(as saved)", page, "a theme deleted since keeps the postcard's look")


class DeleteTests(unittest.TestCase):
    def test_to_the_recycle_bin_with_its_card_and_star(self):
        deck, album, path, card_id = saved_postcard()
        album.favourites = Favourites(os.path.join(tempfile.mkdtemp(), "keepsakes.json"))
        album.set_favourite(card_id, True)
        stem = os.path.splitext(os.path.basename(path))[0]
        sidecar = os.path.join(os.path.dirname(path), ".cards", stem + ".json")
        self.assertTrue(os.path.isfile(sidecar))

        def removed(paths):
            for item in paths:
                os.remove(item)
            return True
        with patch.object(postcard_album, "recycle", removed):
            self.assertTrue(deck._handle_postcards_command("delete", {"id": card_id}))
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(sidecar), "what lets it be edited goes with it")
        self.assertEqual(album.starred(), set())
        self.assertFalse(deck._handle_postcards_command("delete", {"id": card_id}), "gone already")

    def test_on_the_page_asked_twice(self):
        page = (ROOT / "web" / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn("data-pc-delete", page)
        self.assertIn("SURE? TO THE RECYCLE BIN", page)
        self.assertIn('send("delete", {id: gone.id})', page)


if __name__ == "__main__":
    unittest.main()
