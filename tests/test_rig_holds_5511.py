"""5.5.11: the Rig Tracker shows how full the Rhino's hold is while you
drive it, and the mothership's, like SrvSurvey's cargo bar (never what's in
them: that's the Cargo overlay)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tests.test_rig_tracker_5510 import BODY, RADIUS, Deck
from voidcompass.overlays.rig_tracker import build_rig_model, hold_row

ROOT = Path(__file__).resolve().parents[1]


class HoldRowTests(unittest.TestCase):
    def test_how_full_never_what(self):
        self.assertEqual(hold_row("RHINO", 23, 72), {"name": "RHINO", "used": 23, "capacity": 72, "free": 49, "partial": False})
        self.assertEqual(hold_row("SHIP", 80, 64)["free"], 0)
        self.assertIsNone(hold_row("SHIP", 12, 256, partial=True)["free"], "only what was unloaded this trip is known")

    def test_holds_without_a_size_are_left_out(self):
        model = build_rig_model({}, 0, 0, 0, RADIUS, BODY, in_rhino=True,
                                holds=[hold_row("RHINO", 3, 72), hold_row("SHIP", 0, 0)])
        self.assertEqual([row["name"] for row in model["holds"]], ["RHINO"])


class DeckTests(unittest.TestCase):
    def deck(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        deck = Deck(folder.name)
        deck.cargo_capacity = 256
        return deck

    def test_out_in_the_rhino_both_holds(self):
        deck = self.deck()
        deck.current_in_srv, deck.current_vehicle_name = True, "RHINO"
        deck.current_cargo_vessel = "SRV"
        deck.current_cargo_inventory = [{"Name": "platinum", "Count": 20}, {"Name": "painite", "Count": 3}]
        deck._cargo_inventory_by_hold = {"Ship": [{"Name": "platinum", "Count": 160}]}
        deck._rig_update_overlay()
        holds = deck.rig_tracker_hud.update.call_args.args[0]["holds"]
        self.assertEqual(holds, [hold_row("RHINO", 23, 72), hold_row("SHIP", 160, 256)])
        self.assertEqual(deck.api_rigs()["holds"], holds)

    def test_ship_hold_not_yet_read(self):
        deck = self.deck()
        deck.current_in_srv, deck.current_vehicle_name = True, "RHINO"
        deck.current_cargo_vessel, deck.current_cargo_inventory = "SRV", []
        self.assertEqual([row["name"] for row in deck._rig_holds()], ["RHINO"])
        deck._cargo_inventory_by_hold, deck._ship_hold_partial = {"Ship": [{"Count": 9}]}, True
        self.assertTrue(deck._rig_holds()[1]["partial"])

    def test_back_in_the_ship_just_its_hold(self):
        deck = self.deck()
        deck._rig_mark(1)
        deck.current_cargo_vessel, deck.current_cargo_inventory = "Ship", [{"Count": 200}]
        deck._rig_update_overlay()
        self.assertEqual(deck.rig_tracker_hud.update.call_args.args[0]["holds"], [hold_row("SHIP", 200, 256)])

    def test_studio_can_turn_them_off(self):
        deck = self.deck()
        deck.current_in_srv, deck.current_vehicle_name = True, "RHINO"
        deck.current_cargo_vessel, deck.current_cargo_inventory = "SRV", [{"Count": 5}]
        deck.config["rig_tracker_show_holds"] = False
        deck._rig_update_overlay()
        self.assertEqual(deck.rig_tracker_hud.update.call_args.args[0]["holds"], [])
        self.assertEqual(len(deck.api_rigs()["holds"]), 1, "the Local API still has them")

    def test_the_studio_switch(self):
        from voidcompass.core.config import PROFILE_SETTINGS
        self.assertIn("rig_tracker_show_holds", PROFILE_SETTINGS)
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = page.split('data-studio-settings="rig_tracker_hud"', 1)[1].split("</section>", 1)[0]
        self.assertIn('data-overlay-option="rig_tracker_show_holds"', section)
        studio = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn('key == "rig_tracker_show_holds"', studio)
        self.assertIn('"rig_tracker_show_holds": bool(self.config.get("rig_tracker_show_holds", True))', studio)

    def test_a_cargo_change_redraws_the_tracker(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        body = source.split("def _refresh_cargo_consumers", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("self._rig_update_overlay()", body)

    def test_the_page_draws_them(self):
        page = (ROOT / "web" / "rig_tracker" / "app.js").read_text(encoding="utf-8")
        self.assertIn('byId("rigs-holds")', page)
        self.assertIn("FREE", page)


if __name__ == "__main__":
    unittest.main()
