"""5.5.2.8: Odyssey on foot in Commander Record. The suit (with its real
grade, which the game's localised name gets wrong), loadout, weapons and their
modifications in readable names; the backpack apart from the ship locker; and
the on-foot and exobiology figures from Statistics."""

import json
from pathlib import Path
import unittest

from voidcompass.core import odyssey_kit, operational_state

ROOT = Path(__file__).resolve().parents[1]

SUIT_LOADOUT = {
    "timestamp": "2026-10-05T06:52:17Z", "event": "SuitLoadout", "SuitID": 1849961453672360,
    "SuitName": "explorationsuit_class5", "SuitName_Localised": "$ExplorationSuit_Class1_Name;",
    "SuitMods": ["suit_increasedbatterycapacity", "suit_nightvision", "suit_increasedsprintduration", "suit_improvedjumpassist"],
    "LoadoutID": 4293000002, "LoadoutName": "arty",
    "Modules": [
        {"SlotName": "PrimaryWeapon1", "SuitModuleID": 1, "ModuleName": "wpn_m_assaultrifle_laser_fauto",
         "ModuleName_Localised": "TK Aphelion", "Class": 1, "WeaponMods": []},
        {"SlotName": "SecondaryWeapon", "SuitModuleID": 2, "ModuleName": "wpn_s_pistol_laser_sauto",
         "ModuleName_Localised": "TK Zenith", "Class": 3, "WeaponMods": ["weapon_stability", "weapon_somethingnew"]},
    ],
}
STATISTICS = {
    "event": "Statistics",
    "Exobiology": {"Organic_Species_Encountered": 57, "Organic_Data_Profits": 4143632872, "First_Logged": 244},
    "Exploration": {"OnFoot_Distance_Travelled": 231085, "Settlements_Visited": 2},
    "Combat": {"OnFoot_Combat_Bonds": 0, "Settlement_Defended": 0},
}


class OdysseyKitTests(unittest.TestCase):
    def test_suit_names_and_grades(self):
        self.assertEqual(odyssey_kit.suit_name("explorationsuit_class5"), ("Artemis Suit", 5))
        self.assertEqual(odyssey_kit.suit_name("tacticalsuit_class3"), ("Dominator Suit", 3))
        self.assertEqual(odyssey_kit.suit_name("utilitysuit_class1"), ("Maverick Suit", 1))
        self.assertEqual(odyssey_kit.suit_name("flightsuit"), ("Flight Suit", None))

    def test_loadout_in_readable_names(self):
        kit = odyssey_kit.loadout_summary(SUIT_LOADOUT)
        self.assertEqual((kit["suit"], kit["grade"], kit["loadout"]), ("Artemis Suit", 5, "arty"),
                         "grade from the symbol, not the game's wrong localised name")
        self.assertEqual(kit["suit_mods"], ["Improved Battery Capacity", "Night Vision", "Increased Sprint Duration", "Improved Jump Assist"])
        self.assertEqual([(w["slot"], w["name"], w["grade"]) for w in kit["weapons"]],
                         [("Primary", "TK Aphelion", 1), ("Secondary", "TK Zenith", 3)])
        self.assertEqual(kit["weapons"][1]["mods"], ["Stability", "Somethingnew"], "unknown symbols still readable")
        json.dumps(kit)

    def test_backpack_and_records(self):
        pack = odyssey_kit.inventory_summary({"event": "Backpack", "Items": [], "Consumables": [
            {"Name": "healthpack", "Name_Localised": "Medkit", "Count": 2}, {"Name": "energycell", "Count": 5}]})
        self.assertEqual(pack["consumables"], [{"name": "Energycell", "count": 5}, {"name": "Medkit", "count": 2}])
        walked = odyssey_kit.on_foot_record(STATISTICS)
        self.assertEqual(walked[0], {"label": "Distance walked", "value": 231085, "unit": "m"})
        self.assertNotIn("Scavengers killed", [row["label"] for row in walked], "only figures the game sent")
        exo = {row["label"]: row["value"] for row in odyssey_kit.exobiology_record(STATISTICS)}
        self.assertEqual((exo["Species encountered"], exo["First logged"]), (57, 244))

    def test_ship_locker_no_longer_overwrites_the_backpack(self):
        state = operational_state.fresh_runtime_state()
        operational_state.observe_event(state, "Backpack", {"event": "Backpack", "Consumables": [{"Name": "healthpack", "Count": 2}]})
        operational_state.observe_event(state, "ShipLocker", {"event": "ShipLocker", "Consumables": [{"Name": "healthpack", "Count": 87}]})
        ground = state["ground"]
        self.assertEqual(sum(ground["backpack"]["consumables"].values()), 2)
        self.assertEqual(sum(ground["locker"]["consumables"].values()), 87)

    def test_kept_with_the_profile(self):
        from voidcompass.dashboard.dashboard import MainDashboard

        deck = MainDashboard.__new__(MainDashboard)
        deck.companion_state = {}
        saves = []
        deck._save_companion_state = lambda: saves.append(1)
        self.assertTrue(deck._record_odyssey_kit("SuitLoadout", SUIT_LOADOUT))
        self.assertFalse(deck._record_odyssey_kit("SuitLoadout", SUIT_LOADOUT), "unchanged: not saved again")
        self.assertEqual(deck.companion_state["odyssey_loadout"]["loadout"], "arty")
        self.assertEqual(len(saves), 1)
        self.assertIn("ON FOOT · SUIT & LOADOUT", (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
