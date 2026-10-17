"""5.5.11: refining in the Rhino is planet mining with rigs, so the Watcher
talks about the ground and the rigs, never asteroids or limpets."""

import re
import unittest

from voidcompass.overlays import watcher_lines
from voidcompass.overlays.watcher_mind import IMPORTANCE, WatcherMind

ASTEROIDS = re.compile(r"asteroid|limpet|rock", re.IGNORECASE)


class SurfaceMiningLines(unittest.TestCase):
    def test_no_asteroids_on_a_planet(self):
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            lines = bank["mined_surface"]
            self.assertGreaterEqual(len(lines), 12)
            for line in lines:
                self.assertIsNone(ASTEROIDS.search(line), line)
                self.assertIn("{material}", line)
        self.assertIn("mined_surface", IMPORTANCE)


class WhichMining(unittest.TestCase):
    def mind(self):
        mind = WatcherMind(memory_path=None, config={})
        mind.session_start()
        topics = []
        mind.consider = lambda topic, fields=None, force=False: topics.append(topic)
        return mind, topics

    def test_in_the_rhino(self):
        mind, topics = self.mind()
        mind.observe("LaunchSRV", {"SRVType": "mev_rhino"})
        mind.observe("MiningRefined", {"Type_Localised": "Uraninite"})
        self.assertEqual(topics[-1], "mined_surface")
        mind.observe("DockSRV", {})
        mind.observe("MiningRefined", {"Type_Localised": "Platinum"})
        self.assertEqual(topics[-1], "mined")

    def test_started_while_already_out_in_the_rhino(self):
        mind, topics = self.mind()
        mind.observe("Cargo", {"Vessel": "SRV", "Count": 4})
        mind.observe("MiningRefined", {"Type_Localised": "Uraninite"})
        self.assertEqual(topics[-1], "mined_surface")

    def test_a_lost_srv_is_back_to_the_ship(self):
        mind, topics = self.mind()
        mind.observe("LaunchSRV", {"SRVType": "mev_rhino"})
        mind.observe("SRVDestroyed", {})
        mind.observe("MiningRefined", {"Type_Localised": "Painite"})
        self.assertEqual(topics[-1], "mined")


if __name__ == "__main__":
    unittest.main()
