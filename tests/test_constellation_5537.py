"""Your constellation (5.5.3.7): a star per session, nine to a constellation."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from voidcompass.dashboard.dashboard_capsules_mixin import DashboardCapsulesMixin
from voidcompass.exploration.constellation import (
    LEGENDS, LINGER_S, STARS_PER_CONSTELLATION, constellations, session_stars,
)
from voidcompass.services.postcard_album import PostcardAlbum

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
START = 1_700_000_000


def stamp(seconds):
    return datetime.fromtimestamp(START + seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def history(stays, gap=86400):
    """One session per (system, minutes stayed): two quick hops, the stay,
    one more hop; sessions a day apart."""
    rows, t = [], 0
    for index, (system, minutes, star) in enumerate(stays):
        t = index * gap
        for name, wait in ((f"Hop {index}a", 120), (system, minutes * 60), (f"Hop {index}b", 120), (f"Hop {index}c", 0)):
            rows.append([stamp(t), name, 100.0 * index, 0.0, 250.0 * index + len(name), star, 30.0, ""])
            t += wait
    return rows


class StarTests(unittest.TestCase):
    def test_one_star_a_session_where_you_lingered(self):
        stars = session_stars(history([("Sol", 45, "G"), ("Colonia", 90, "F")]))
        self.assertEqual([(star["system"], star["dwell"], star["star"]) for star in stars], [("Sol", 2700, "G"), ("Colonia", 5400, "F")])

    def test_a_session_that_never_stopped_gives_none(self):
        self.assertEqual(session_stars(history([("Brief", LINGER_S / 60 - 1, "K")])), [])

    def test_a_long_gap_is_a_new_session_and_caps_the_stay(self):
        rows = [[stamp(0), "Home", 0, 0, 0, "K", 0, "L"], [stamp(30 * 3600), "Next day", 1, 0, 1, "K", 5, ""]]
        self.assertEqual(session_stars(rows), [], "logged off: the night away isn't a stay")


class SkyTests(unittest.TestCase):
    def stays(self, count, offset=0):
        return [(f"Star {offset + index}", 20 + index * 5, "GKMFA"[index % 5]) for index in range(count)]

    def test_nine_stars_to_a_constellation(self):
        sky = constellations(history(self.stays(20)))
        self.assertEqual([len(item["stars"]) for item in sky], [9, 9, 2])
        self.assertEqual([item["complete"] for item in sky], [True, True, False])
        self.assertEqual([item["index"] for item in sky], [1, 2, 3])
        for item in sky:
            keys = set(item["keys"])
            self.assertTrue(all(a in keys and b in keys for a, b in item["lines"]))
            self.assertEqual(len(item["lines"]), len(item["stars"]) - 1, "each star joined once")
            for star in item["stars"]:
                self.assertTrue(-1 <= star["x"] <= 1 and -1 <= star["y"] <= 1)

    def test_a_place_you_return_to_shines_brighter(self):
        stays = [("Home", 60, "K"), ("Away", 30, "G"), ("Home", 60, "K")]
        item = constellations(history(stays))[0]
        home = next(star for star in item["stars"] if star["system"] == "Home")
        self.assertEqual((home["visits"], home["dwell"], len(item["stars"])), (2, 7200, 2))

    def test_the_same_history_draws_the_same_sky(self):
        rows = history(self.stays(12))
        self.assertEqual(constellations(rows), constellations(list(rows)))
        self.assertNotEqual(constellations(rows)[0]["stars"], constellations(history(self.stays(12, offset=50)))[0]["stars"])

    def test_named_with_a_legend_in_its_voice(self):
        rows = history(self.stays(9))
        weary, normal = constellations(rows, "weary")[0], constellations(rows, "stoic")[0]
        self.assertTrue(weary["name"].startswith("The "))
        self.assertEqual(weary["name"], normal["name"], "the name is the sky's, whatever its nature")
        self.assertNotIn("{", weary["legend"])
        self.assertTrue(any(weary["legend"].startswith(line.split("{")[0]) for line in LEGENDS["weary"]))
        self.assertTrue(weary["from"].endswith(str(datetime.fromtimestamp(START).year + 1286)))

    def test_no_stars_no_sky(self):
        self.assertEqual(constellations([]), [])


class DeckTests(unittest.TestCase):
    def deck(self, rows):
        class Deck(DashboardCapsulesMixin):
            pass
        deck = Deck()
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        deck.config = {"postcards_path": folder}
        # Saved pictures (5.5.4) go in their own folder: a temporary one here.
        saved_folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, saved_folder, True)
        deck.constellations_folder = lambda: saved_folder
        deck.saved_folder = saved_folder
        deck.travel_history = type("History", (), {"lock": threading.Lock(), "rows": rows, "revision": 1})()
        deck.feed = []
        deck.add_event_feed_entry = lambda *args, **kwargs: deck.feed.append(args)
        return deck, folder

    def test_the_page(self):
        deck, _folder = self.deck(history([(f"S{index}", 30, "K") for index in range(4)]))
        data = deck._html_constellation_workspace()
        self.assertEqual((len(data["sky"]), data["per"], data["to_go"]), (1, STARS_PER_CONSTELLATION, 5))
        deck.travel_history.rows = []
        self.assertEqual(len(deck._html_constellation_workspace()["sky"]), 1, "drawn again only on a new revision")
        deck.travel_history.revision = 2
        self.assertEqual(deck._html_constellation_workspace()["sky"], [])

    def test_saved_as_a_picture_on_the_constellation_page(self):
        from PIL import Image
        deck, folder = self.deck([])
        out = io.BytesIO()
        Image.new("RGB", (160, 100), (10, 20, 40)).save(out, "JPEG", quality=90)
        picture = "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
        self.assertTrue(deck._handle_constellation_command("save", {"name": 'The Restless/Crown?', "picture": picture}))
        self.assertEqual(os.listdir(folder), [], "not with the postcards (5.5.4)")
        saved = os.listdir(deck.saved_folder)
        self.assertEqual(len(saved), 1)
        self.assertTrue(saved[0].startswith("Constellation - The RestlessCrown - "), saved[0])
        with Image.open(os.path.join(deck.saved_folder, saved[0])) as image:
            self.assertEqual((image.format, image.size), ("PNG", (160, 100)), "kept as a PNG")
        rows = deck._html_constellation_workspace()["saved"]
        self.assertEqual([row["title"] for row in rows], ["The RestlessCrown"], "on the Constellation page")

    def test_saved_pictures_go_to_your_chosen_folder(self):
        from PIL import Image
        deck, _folder = self.deck([])
        del deck.constellations_folder  # the real one, following the setting
        chosen = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, chosen, True)
        self.assertTrue(deck._handle_constellation_command("folder", {"value": f"  {chosen}  "}))
        self.assertEqual(deck.config["constellations_path"], chosen, "kept as typed, trimmed")
        self.assertEqual(deck.constellations_folder(), chosen)
        out = io.BytesIO()
        Image.new("RGB", (16, 10)).save(out, "PNG")
        picture = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
        self.assertTrue(deck._handle_constellation_command("save", {"name": "The Bright Key", "picture": picture}))
        self.assertEqual(len(os.listdir(chosen)), 1)
        self.assertEqual(deck._html_constellation_workspace()["folder"]["now"], chosen)
        deck._handle_constellation_command("folder", {"value": ""})
        self.assertTrue(deck.constellations_folder().endswith("constellations"), "empty: beside Void Compass")
        from voidcompass.core import config as config_module
        self.assertIn("constellations_path", config_module.PROFILE_SETTINGS)
        page = (WEB / "dashboard" / "constellation.js").read_text(encoding="utf-8")
        self.assertIn('data-sky-folder="browse"', page)

    def test_pictures_saved_before_move_to_their_own_folder(self):
        from PIL import Image
        deck, folder = self.deck([])
        Image.new("RGB", (16, 10)).save(os.path.join(folder, "Constellation - The Old Kite - 2026-10-01 20-00-00.png"))
        Image.new("RGB", (16, 10)).save(os.path.join(folder, "Postcard - Sol - 2026-10-01 20-00-00.png"))
        self.assertEqual([row["title"] for row in PostcardAlbum(lambda: folder).rows()], ["Sol"], "the album shows postcards only")
        self.assertEqual([row["title"] for row in deck.constellation_album().rows()], ["The Old Kite"])
        self.assertEqual(sorted(os.listdir(folder)), ["Postcard - Sol - 2026-10-01 20-00-00.png"], "moved, postcards left alone")

    def test_only_a_picture_is_saved(self):
        deck, folder = self.deck([])
        for picture in ("", "not base64!", base64.b64encode(b"GIF89a....").decode("ascii")):
            self.assertFalse(deck._handle_constellation_command("save", {"name": "X", "picture": picture}))
        self.assertFalse(deck._handle_constellation_command("delete", {}))
        self.assertEqual(os.listdir(folder), [])


class WiringTests(unittest.TestCase):
    def test_it_is_a_deck_page(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="constellation"', html)
        self.assertIn('data-page-name="constellation"', html)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("constellation: (data) => renderConstellation(data, WORKSHOP_UI)", app)
        page = (WEB / "dashboard" / "constellation.js").read_text(encoding="utf-8")
        self.assertIn('canvas.toDataURL("image/jpeg"', page, "small enough for the command channel")


if __name__ == "__main__":
    unittest.main()
