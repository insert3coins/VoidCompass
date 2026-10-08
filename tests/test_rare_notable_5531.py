"""5.5.3.1: green gas giants and other rare worlds lead Survey's NOTABLE."""

import unittest
from pathlib import Path

from voidcompass.dashboard.dashboard_scan_mixin import DashboardScanMixin
from voidcompass.exploration.notable_bodies import build_notable_body_rows, is_green_giant_codex, rarity

ROOT = Path(__file__).resolve().parents[1]
GREEN = {"event": "CodexEntry", "EntryID": 1200602, "Name": "$Codex_Ent_Green_Sudarsky_Class_II_Name;",
         "timestamp": "2026-02-02T03:48:19Z", "SystemAddress": 561608973115, "BodyID": 0}
SCAN = {"event": "Scan", "BodyName": "Hatchooe YF-O d6-16 4", "BodyID": 10, "PlanetClass": "Sudarsky class II gas giant",
        "timestamp": "2026-02-02T03:48:19Z", "SystemAddress": 561608973115}


class _Deck(DashboardScanMixin):
    current_sys = "Hatchooe YF-O d6-16"
    batch_mode = True

    def __init__(self):
        self.scan_items = []
        self.saved = []

    def save_scan_item_to_db(self, system, item):
        self.saved.append(item)


class RareNotableTests(unittest.TestCase):
    def test_green_codex_entries_are_recognised(self):
        self.assertTrue(is_green_giant_codex(GREEN))
        self.assertTrue(is_green_giant_codex({"EntryID": 1200402, "Name": "$Codex_Ent_Green_Giant_With_Ammonia_Life_Name;"}))
        self.assertFalse(is_green_giant_codex({"EntryID": 1200601, "Name": "$Codex_Ent_Standard_Sudarsky_Class_II_Name;"}))

    def test_codex_then_scan_marks_the_gas_giant(self):
        deck = _Deck()
        deck._note_green_giant_codex(GREEN)
        self.assertTrue(deck._claim_green_giant(SCAN, SCAN["PlanetClass"]))
        # Used once: the next gas giant is not green.
        self.assertFalse(deck._claim_green_giant(dict(SCAN, BodyID=17), SCAN["PlanetClass"]))

    def test_a_rocky_body_or_a_late_scan_is_not_claimed(self):
        deck = _Deck()
        deck._note_green_giant_codex(GREEN)
        self.assertFalse(deck._claim_green_giant(dict(SCAN, PlanetClass="Rocky body"), "Rocky body"))
        self.assertFalse(deck._claim_green_giant(dict(SCAN, timestamp="2026-02-02T03:49:02Z"), SCAN["PlanetClass"]))

    def test_scan_then_codex_marks_it_too(self):
        deck = _Deck()
        item = {"body_id": 10, "planet_class": SCAN["PlanetClass"], "scan_timestamp": SCAN["timestamp"],
                "system_address": SCAN["SystemAddress"]}
        deck.scan_items = [item]
        deck._note_green_giant_codex(GREEN)
        self.assertTrue(item["green_giant"])
        self.assertEqual(deck.saved, [item])

    def test_rare_worlds_are_notable_and_say_why(self):
        rows = build_notable_body_rows([
            {"body_id": 1, "name": "A 1", "planet_class": "Sudarsky class II gas giant", "reward": 3000, "green_giant": True},
            {"body_id": 2, "name": "A 2", "planet_class": "Helium rich gas giant", "reward": 3000},
            {"body_id": 3, "name": "A 3", "planet_class": "Water giant", "reward": 3000},
            {"body_id": 4, "name": "A 4", "planet_class": "Sudarsky class I gas giant", "reward": 3000},
        ], 50_000)
        by_id = {row["body_id"]: row for row in rows}
        self.assertEqual(set(by_id), {1, 2, 3})
        self.assertTrue(by_id[1]["value_line"].startswith("GREEN GAS GIANT"))
        self.assertGreater(by_id[1]["rarity"], by_id[2]["rarity"])
        self.assertEqual(rarity({"planet_class": "Earthlike body"}), (0, ""), "Earth-likes keep their order by value")

    def test_survey_lists_rare_worlds_first(self):
        app = (ROOT / "web" / "survey" / "app.js").read_text(encoding="utf-8")
        self.assertIn("rarity(right) - rarity(left) || worth(right) - worth(left)", app)


if __name__ == "__main__":
    unittest.main()
