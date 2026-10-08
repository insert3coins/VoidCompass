"""5.5.3: a journal Loadout imports into the Build Planner as the ship is.

Slots the journal leaves out are empty in game (they showed the stock Pulse
Lasers), and each module goes to the slot its journal name says
(MediumHardpoint2 is the second class 2 hardpoint, not the first hardpoint
that takes a weapon).
"""

import unittest

from voidcompass.engineering import build_planner as bp


def module(slot, item, **extra):
    return {"Slot": slot, "Item": item, "On": True, "Priority": 0, **extra}


class JournalLoadoutImportTests(unittest.TestCase):
    def loadout(self, *modules):
        return {"event": "Loadout", "Ship": "anaconda", "ShipName": "Test", "Modules": [
            module("PowerPlant", "int_powerplant_size8_class5"),
            *modules,
        ]}

    def slot(self, build, key):
        return bp._module(build["ship_id"], build["slots"][key]["module"]).get("name") if build["slots"][key]["module"] else None

    def test_empty_hardpoints_stay_empty(self):
        build, _warnings = bp.journal_build(self.loadout(module("HugeHardpoint1", "hpt_beamlaser_gimbal_huge")))
        # Anaconda: hardpoints are classes 4, 3, 3, 3, 2, 2, 1, 1; stock has
        # Pulse Lasers in the two class 1 slots.
        self.assertEqual(self.slot(build, "hardpoint:0"), "Beam Laser")
        for index in range(1, 8):
            self.assertIsNone(self.slot(build, f"hardpoint:{index}"), f"hardpoint {index} is empty in game")
        self.assertEqual(build["slots"]["internal:0"]["module"], 0, "no stock internals either")

    def test_modules_go_to_the_slot_their_journal_name_gives(self):
        build, _warnings = bp.journal_build(self.loadout(
            module("MediumHardpoint2", "hpt_pulselaser_fixed_medium"),
            module("SmallHardpoint1", "hpt_pulselaser_fixed_small"),
            module("TinyHardpoint3", "hpt_shieldbooster_size0_class5"),
            module("Slot05_Size5", "int_shieldgenerator_size5_class5"),
        ))
        self.assertEqual(self.slot(build, "hardpoint:5"), "Pulse Laser", "second class 2 hardpoint")
        self.assertIsNone(self.slot(build, "hardpoint:0"))
        self.assertEqual(self.slot(build, "hardpoint:6"), "Pulse Laser", "first class 1 hardpoint")
        self.assertEqual(self.slot(build, "utility:2"), "Shield Booster")
        self.assertEqual(self.slot(build, "internal:4"), "Shield Generator", "Slot05_Size5, by the ship's own slot names")

    def test_modules_given_with_a_ship_are_recognised(self):
        loadout = {"event": "Loadout", "Ship": "panthermkii", "Modules": [
            module("Slot08_Size4", "int_mkiilargebuggybay_size2_class3_free"),
        ]}
        build, warnings = bp.journal_build(loadout)
        self.assertFalse([w for w in warnings if "buggybay" in w])
        self.assertTrue(any(slot["module"] for key, slot in build["slots"].items() if key.startswith("internal:")))

    def test_engineering_comes_across(self):
        build, _warnings = bp.journal_build(self.loadout(module(
            "LargeHardpoint1", "hpt_multicannon_gimbal_large",
            Engineering={"BlueprintName": "Weapon_Overcharged", "Level": 5, "Quality": 0.5,
                         "ExperimentalEffect": "special_auto_loader", "Modifiers": []},
        )))
        slot = build["slots"]["hardpoint:1"]
        self.assertTrue(slot["blueprint"])
        self.assertEqual((slot["grade"], slot["roll"]), (5, 0.5))
        self.assertTrue(slot["experimental"])


if __name__ == "__main__":
    unittest.main()
