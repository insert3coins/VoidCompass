"""5.5.3.2: the Watcher's idle thoughts come from what's really around."""

import random
import unittest
from datetime import datetime

from voidcompass.overlays import watcher_lines
from voidcompass.overlays.watcher_idle import IDLE_TOPICS, Surroundings, star_words
from voidcompass.overlays.watcher_mind import WatcherMind

NOON = datetime(2026, 10, 9, 12, 0).timestamp()


class Clock:
    def __init__(self, now=NOON):
        self.now = now

    def __call__(self):
        return self.now


class IdleTests(unittest.TestCase):
    def test_star_words(self):
        self.assertEqual(star_words("M"), ("red dwarf", False))
        self.assertEqual(star_words("DA"), ("white dwarf", True))
        self.assertEqual(star_words("N"), ("neutron star", True))
        self.assertEqual(star_words(""), ("", False))

    def test_it_follows_the_surroundings(self):
        around = Surroundings()
        around.observe("StartJump", {"JumpType": "Hyperspace", "StarClass": "N"})
        around.observe("FSDJump", {"StarSystem": "Far Away", "StarPos": [3000, 0, 4000], "JumpDist": 40})
        around.observe("FSSDiscoveryScan", {"BodyCount": 24})
        around.observe("Scan", {"BodyName": "Far Away 3", "PlanetClass": "Water giant"}, rarity=(2, "WATER GIANT"))
        topics = dict(around.choices(NOON, random.Random(1)))
        self.assertEqual(topics["idle_star_odd"]["star"], "neutron star")
        self.assertEqual(topics["idle_big_system"]["count"], 24)
        self.assertEqual(topics["idle_far"]["dist"], "5,000")
        self.assertEqual(topics["idle_recall"]["thing"], "Far Away 3, the water giant")
        around.observe("Docked", {"StationName": "Jameson Memorial"})
        topics = dict(around.choices(NOON, random.Random(1)))
        self.assertEqual(topics["idle_docked"]["station"], "Jameson Memorial")
        self.assertNotIn("idle_star_odd", topics, "docked: no remarks about the star")

    def test_a_new_session_forgets_the_old_memories(self):
        around = Surroundings()
        around.observe("ScanOrganic", {"ScanType": "Analyse", "Species_Localised": "Bacterium Aurasus"})
        self.assertTrue(around.memories)
        around.reset_session()
        self.assertFalse(around.memories)

    def test_the_quiet_brings_a_thought_about_here(self):
        clock = Clock()
        watcher = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, clock, random.Random(4))
        watcher.observe("LoadGame", {})
        watcher.observe("StartJump", {"JumpType": "Hyperspace", "StarClass": "K"})
        watcher.observe("FSDJump", {"StarSystem": "Prai", "StarPos": [10, 0, 10], "JumpDist": 12})
        topics = set()
        for _ in range(40):
            clock.now += 400
            thought = watcher.tick()
            if thought:
                topics.add(thought["topic"])
        self.assertTrue(topics & {"idle_star", "idle_home"}, topics)
        self.assertTrue(all(topic in IDLE_TOPICS or topic in {"quiet", "long_session"} for topic in topics), topics)

    def test_lines_for_every_idle_topic(self):
        for topic in IDLE_TOPICS:
            self.assertGreaterEqual(len(watcher_lines.NORMAL[topic]), 4, topic)
            self.assertGreaterEqual(len(watcher_lines.WEARY[topic]), 4, topic)


if __name__ == "__main__":
    unittest.main()
