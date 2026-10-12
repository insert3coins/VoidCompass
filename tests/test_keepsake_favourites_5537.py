"""Favourites on the Postcards and Screenshots pages (5.5.3.7): a star on a
picture, kept in keepsakes.json, and a FAVOURITES filter."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tests.test_keepsakes_polish_5537 import album_folder
from tests.test_screenshots_page_5537 import shots_folder
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.services.postcard_album import Favourites

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def favourites_file(test):
    folder = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, folder, True)
    return os.path.join(folder, "keepsakes.json")


class FavouritesTests(unittest.TestCase):
    def test_starred_and_kept(self):
        path = favourites_file(self)
        favourites = Favourites(path)
        self.assertEqual(favourites.names("screenshots"), set())
        self.assertTrue(favourites.set("screenshots", "Colonia_2026-10-12_20-14-00.png", True))
        self.assertTrue(favourites.set("postcards", "Postcard - Earth - 2026-10-12 20-14-00.png", True))
        again = Favourites(path)
        self.assertEqual(again.names("screenshots"), {"colonia_2026-10-12_20-14-00.png"}, "kept on disk")
        self.assertEqual(len(again.names("postcards")), 1, "each page its own list")
        self.assertTrue(again.set("screenshots", "COLONIA_2026-10-12_20-14-00.png", False))
        self.assertEqual(Favourites(path).names("screenshots"), set())
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(set(json.load(handle)), {"screenshots", "postcards"})

    def test_a_broken_file_is_no_favourites(self):
        path = favourites_file(self)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(Favourites(path).names("postcards"), set())


class PageTests(unittest.TestCase):
    def deck(self, **config):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = dict(config)
        deck._keepsake_favourites = Favourites(favourites_file(self))
        return deck

    def test_a_screenshot_starred(self):
        deck = self.deck(screenshots_path=shots_folder(self))
        rows = deck._html_screenshots_workspace()["rows"]
        self.assertFalse(any(row["favourite"] for row in rows))
        self.assertTrue(deck._handle_screenshots_command("favourite", {"id": rows[1]["id"], "value": True}))
        rows = deck._html_screenshots_workspace()["rows"]
        self.assertEqual([row["favourite"] for row in rows], [False, True, False, False, False])
        self.assertTrue(deck._handle_screenshots_command("favourite", {"id": rows[1]["id"], "value": False}))
        self.assertFalse(any(row["favourite"] for row in deck._html_screenshots_workspace()["rows"]))
        self.assertFalse(deck._handle_screenshots_command("favourite", {"id": "1" * 16, "value": True}), "no such picture")

    def test_a_postcard_starred(self):
        deck = self.deck(postcards_path=album_folder(self, 2))
        rows = deck._html_postcards_workspace()["rows"]
        self.assertTrue(deck._handle_postcards_command("favourite", {"id": rows[0]["id"], "value": True}))
        rows = deck._html_postcards_workspace()["rows"]
        self.assertEqual([row["favourite"] for row in rows], [True, False])
        self.assertEqual(deck.keepsake_favourites().names("screenshots"), set(), "a postcard's star is the postcards'")

    def test_kept_in_void_compass_folder(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        with patch("voidcompass.dashboard.dashboard_keepsakes_mixin.application_dir", return_value=Path("C:/VC")):
            self.assertEqual(Path(Deck().keepsake_favourites().path), Path("C:/VC") / "keepsakes.json")
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("keepsakes.json", ignored)

    def test_both_pages_have_the_star_and_the_filter(self):
        for page in ("postcards.js", "screenshots.js"):
            with self.subTest(page=page):
                source = (WEB / "dashboard" / page).read_text(encoding="utf-8")
                self.assertIn('from "./favourites.js"', source)
                self.assertIn("starButton(row, ui)", source)
                self.assertIn("favouritesFilter(", source)
                self.assertIn('="favourite">☆ FAVOURITE</button>', source)
        for page in ("postcards.js", "screenshots.js"):
            source = (WEB / "dashboard" / page).read_text(encoding="utf-8")
            self.assertIn("document.body.append(viewer)", source, "the viewer opens where you are, not at the page's top")
        shared = (WEB / "dashboard" / "favourites.js").read_text(encoding="utf-8")
        self.assertIn('operation: "favourite"', shared)


if __name__ == "__main__":
    unittest.main()
