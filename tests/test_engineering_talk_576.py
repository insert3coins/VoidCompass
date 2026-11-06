"""Engineering in the companions' words (5.7.6): a grade completed, a grade 5
finished, an experimental effect, materials filling up, and TALK's answers
about your engineers. Events as the journal writes them."""
import random
import unittest

from voidcompass.core import companions
from voidcompass.overlays import life_engineering, watcher_copilot
from tests.test_aster_companion import Clock


def craft(level, quality, **extra):
    return {"event": "EngineerCraft", "Engineer": "Felicity Farseer", "BlueprintName": "FSD_LongRange", "Level": level,
            "Quality": quality, "Slot": "FrameShiftDrive", "Module": "int_hyperdrive_size5_class5",
            "Ingredients": [{"Name": "arsenic", "Count": 1}], **extra}


class CraftTests(unittest.TestCase):
    def test_a_roll_is_quiet_until_the_grade_is_done(self):
        self.assertIsNone(life_engineering.moment("EngineerCraft", craft(3, .42)), "one roll of many")
        topic, fields = life_engineering.moment("EngineerCraft", craft(3, 1.0))
        self.assertEqual(topic, "engineer_grade_done")
        self.assertEqual((fields["blueprint"], fields["module"], fields["grade"], fields["Blueprint"]),
                         ("Increased Range", "frame shift drive", "3", "Increased Range"))
        self.assertEqual(life_engineering.moment("EngineerCraft", craft(5, 1.0))[0], "engineer_grade5")

    def test_an_experimental_is_its_own_moment(self):
        topic, fields = life_engineering.moment("EngineerCraft", craft(5, .2, ApplyExperimentalEffect="special_fsd_heavy",
                                                                       ExperimentalEffect_Localised="Mass Manager"))
        self.assertEqual((topic, fields["effect"]), ("engineer_experimental", "Mass Manager"))

    def test_readable_names(self):
        self.assertEqual(life_engineering.blueprint("Engine_Dirty"), "Dirty Drive Tuning")
        self.assertEqual(life_engineering.blueprint("Sensor_SomethingNew"), "Something New", "new ones still read")
        self.assertEqual(life_engineering.module("Sensor_Expanded", "int_detailedsurfacescanner_tiny"), "surface scanner")
        self.assertEqual(life_engineering.module("Weapon_Overcharged", "hpt_multicannon_gimbal_medium"), "multi-cannon")
        self.assertEqual(life_engineering.module("Armour_Advanced", "explorer_nx_armour_grade1"), "armour")


class MaterialStoreTests(unittest.TestCase):
    def store(self):
        store = life_engineering.MaterialStore(grade_of=lambda symbol: {"iron": 1, "arsenic": 2, "polonium": 4,
                                                                        "antimony": 4, "tellurium": 4,
                                                                        "rutheniumx": 5, "technetium": 5}.get(symbol))
        store.observe("Materials", {"Raw": [{"Name": "iron", "Count": 297}, {"Name": "arsenic", "Count": 250},
                                            {"Name": "technetium", "Count": 3}], "Manufactured": [], "Encoded": []})
        return store

    def test_full_is_said_once_until_it_drops(self):
        store = self.store()
        self.assertIsNone(store.observe("MaterialCollected", {"Category": "Raw", "Name": "iron", "Count": 2}))
        topic, fields = store.observe("MaterialCollected", {"Category": "Raw", "Name": "iron", "Count": 3})
        self.assertEqual((topic, fields["cap"]), ("material_full", "300"))
        self.assertIsNone(store.observe("MaterialCollected", {"Category": "Raw", "Name": "iron", "Count": 3}), "already full")
        self.assertIsNone(store.observe("MaterialCollected", {"Category": "Raw", "Name": "arsenic", "Count": 1}),
                          "full at login isn't news")
        store.observe("EngineerCraft", craft(1, 1.0, Ingredients=[{"Name": "iron", "Count": 10}]))
        self.assertEqual(store.counts["iron"], 290)
        store.observe("MaterialCollected", {"Category": "Raw", "Name": "iron", "Count": 9})
        self.assertEqual(store.observe("MaterialCollected", {"Category": "Raw", "Name": "iron", "Count": 1})[0], "material_full",
                         "full again after using some")

    def test_a_grade_5_pickup_once_a_session(self):
        store = self.store()
        topic, fields = store.observe("MaterialCollected", {"Category": "Raw", "Name": "technetium", "Count": 1,
                                                            "Name_Localised": "Technetium"})
        self.assertEqual((topic, fields["material"]), ("material_grade5", "Technetium"))
        self.assertIsNone(store.observe("MaterialCollected", {"Category": "Raw", "Name": "technetium", "Count": 1}))

    def test_trades_synthesis_and_discards_count(self):
        store = self.store()
        store.observe("MaterialTrade", {"Paid": {"Material": "arsenic", "Quantity": 6},
                                        "Received": {"Material": "polonium", "Quantity": 1}})
        store.observe("Synthesis", {"Name": "FSD Basic", "Materials": [{"Name": "arsenic", "Count": 1}]})
        store.observe("MaterialDiscarded", {"Category": "Raw", "Name": "iron", "Count": 7})
        self.assertEqual((store.counts["arsenic"], store.counts["polonium"], store.counts["iron"]), (243, 1, 290))


class CompanionTests(unittest.TestCase):
    def test_every_companion_speaks_of_a_finished_grade_and_a_full_store(self):
        for identity in ("watcher", "aster", "axiom", "meridian", "lyra"):
            with self.subTest(identity=identity):
                config = {"companion_identity": identity, f"{identity}_thoughts": "chatty", "heartbeat_thoughts": "chatty"}
                companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(3))
                companion.memory["hours"] = 30
                companion.session_start()
                companion.random.random = lambda: 0.0
                companion.clock.now += 1300
                thought = companion.observe("EngineerCraft", craft(4, 1.0))
                self.assertEqual(thought["topic"], "engineer_grade_done")
                self.assertNotIn("{", thought["text"])
                companion.observe("Materials", {"Raw": [{"Name": "iron", "Count": 299}], "Manufactured": [], "Encoded": []})
                companion.clock.now += 1300
                thought = companion.observe("MaterialCollected", {"Category": "Raw", "Name": "iron", "Count": 3})
                self.assertEqual(thought["topic"], "material_full")
                self.assertNotIn("{", thought["text"])


class TalkTests(unittest.TestCase):
    ENGINEERS = {"Felicity Farseer": {"progress": "Unlocked", "rank": 5, "rank_progress": 0},
                 "Hera Tani": {"progress": "Unlocked", "rank": 4, "rank_progress": 52},
                 "Tod McQuinn": {"progress": "Invited"}, "Lei Cheung": {"progress": "Known"}}

    def test_engineers_summed_up_and_by_name(self):
        self.assertEqual(watcher_copilot.topics_for("which engineers have I unlocked?"), ["engineers"])
        lines = watcher_copilot.engineer_lines(self.ENGINEERS, "which engineers have I unlocked?")
        self.assertEqual(lines[:3], ["Engineers: 2 unlocked of 4 you know", "Rank 5: Felicity Farseer", "Rank 4: Hera Tani"])
        self.assertIn("Invited: Tod McQuinn", lines)
        self.assertEqual(watcher_copilot.engineer_lines(self.ENGINEERS, "what rank am I with Tani?"),
                         ["Hera Tani: unlocked, rank 4 (52% of the way to rank 5)"])
        self.assertEqual(watcher_copilot.engineer_lines({}, "engineers"), ["No engineers on record yet (the game lists them when it starts)"])

    def test_which_materials_are_full(self):
        inventory = {"raw": {"iron": {"name": "Iron", "count": 300}, "arsenic": {"name": "Arsenic", "count": 12}},
                     "encoded": {"scandata": {"name": "Classified Scan Fragment", "count": 100}}}
        grades = {"iron": 1, "arsenic": 2, "scandata": 5}
        lines = watcher_copilot.materials_lines(inventory, "which materials are full?", grade_of=grades.get)
        self.assertEqual(lines, ["Full (2): Iron 300, Classified Scan Fragment 100"])
        self.assertEqual(watcher_copilot.materials_lines(inventory, "any raw materials maxed out?", grade_of=grades.get),
                         ["Full (1): Iron 300"])


if __name__ == "__main__":
    unittest.main()
