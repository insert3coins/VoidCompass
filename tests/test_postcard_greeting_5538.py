"""The postcards' lettering (5.5.3.8): "Greetings from", "Wish you were
here", your own words, or none, over the place's name."""
from __future__ import annotations

from pathlib import Path
import unittest

from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays.postcard_picture import render_postcard
from voidcompass.overlays.postcards import caption_text, greeting_text, postcard_card, postcard_options

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
EVENT = {"timestamp": "2026-10-12T20:14:00Z", "System": "Hatchooe", "Body": "Hatchooe AB 3"}


class GreetingTests(unittest.TestCase):
    def test_the_choices(self):
        self.assertEqual(greeting_text({}), "Greetings from", "as before, by default")
        self.assertEqual(greeting_text({"postcard_greeting": "wish"}), "Wish you were here")
        self.assertEqual(greeting_text({"postcard_greeting": "custom", "postcard_greeting_text": "  Fly   safe from "}), "Fly safe from")
        self.assertEqual(greeting_text({"postcard_greeting": "custom", "postcard_greeting_text": ""}), "Greetings from")
        self.assertEqual(greeting_text({"postcard_greeting": "custom", "postcard_greeting_text": "x" * 99}), "x" * 40)
        self.assertEqual(greeting_text({"postcard_greeting": "none"}), "")
        self.assertEqual(greeting_text({"postcard_greeting": "shouting"}), "Greetings from")
        self.assertEqual(postcard_options({"postcard_greeting": "wish"})["greeting"], "Wish you were here")

    def test_the_caption_file_reads_naturally(self):
        card = postcard_card(EVENT, state="LANDED")
        for words, first in (("Greetings from", "Greetings from Hatchooe AB 3"), ("Wish you were here", "Wish you were here · Hatchooe AB 3"),
                             ("Love from", "Love from Hatchooe AB 3"), ("", "Hatchooe AB 3")):
            card["greeting"] = words
            self.assertEqual(caption_text(card).splitlines()[0], first)

    def test_the_picture_with_and_without(self):
        card = postcard_card(EVENT, state="LANDED")
        lettered = render_postcard(dict(card), None, {}, width=420)
        bare = render_postcard(dict(card, greeting=""), None, {}, width=420)
        self.assertLess(bare.height, lettered.height, "no lettering: no line for it")

    def test_set_on_the_postcards_page(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = {}
        deck._persist_config = lambda: None
        self.assertTrue(deck._postcard_setting("postcard_greeting", "Custom"))
        self.assertTrue(deck._postcard_setting("postcard_greeting_text", "  From the black  "))
        self.assertEqual((deck.config["postcard_greeting"], deck.config["postcard_greeting_text"]), ("custom", "From the black"))
        self.assertFalse(deck._postcard_setting("postcard_greeting", "shouting"))
        key = deck._postcard_preview_key()
        deck._postcard_setting("postcard_greeting", "none")
        self.assertNotEqual(deck._postcard_preview_key(), key, "the preview follows")
        for name in ("postcard_greeting", "postcard_greeting_text"):
            self.assertIn(name, config_module.PROFILE_SETTINGS)
        page = (WEB / "dashboard" / "postcards.js").read_text(encoding="utf-8")
        self.assertIn('data-postcard-setting="postcard_greeting"', page)
        overlay = (WEB / "postcards" / "app.js").read_text(encoding="utf-8")
        self.assertIn('String(card.greeting ?? "Greetings from")', overlay)


if __name__ == "__main__":
    unittest.main()
