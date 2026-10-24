"""5.6.3: an expedition that already exists can be renamed (and what it's for
changed) from its page."""

import unittest
from pathlib import Path

from tests.test_expeditions_561 import Deck

ROOT = Path(__file__).resolve().parents[1]


class RenameTests(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()
        self.manager = self.deck.expedition_manager
        self.trip = self.manager.create("Colonia run", description="Out and back", start_system="Sol", destination="Colonia")

    def rename(self, **payload):
        return self.deck._handle_expedition_command("rename", {"expedition_id": self.trip["id"], **payload})

    def test_a_new_name_and_purpose_are_kept(self):
        self.assertTrue(self.rename(name="  The Long Way Round  ", description="Via the Bubble's back roads"))
        again = self.manager.get(self.trip["id"])
        self.assertEqual((again["name"], again["description"]), ("The Long Way Round", "Via the Bubble's back roads"))
        self.assertEqual(again["destination"], "Colonia", "only the words change")

    def test_a_blank_name_is_refused_and_the_purpose_left_alone_when_unsent(self):
        self.assertFalse(self.rename(name="   "))
        self.assertTrue(self.rename(name="Colonia Express"))
        trip = self.manager.get(self.trip["id"])
        self.assertEqual((trip["name"], trip["description"]), ("Colonia Express", "Out and back"))
        self.assertFalse(self.deck._handle_expedition_command("rename", {"expedition_id": "nope", "name": "X"}))

    def test_the_page_has_the_edit(self):
        page = (ROOT / "web" / "dashboard" / "expeditions.js").read_text(encoding="utf-8")
        self.assertIn('button("EDIT NAME", "rename_form"', page)
        self.assertIn('data-ex-form="rename"', page)


if __name__ == "__main__":
    unittest.main()
