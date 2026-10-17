"""5.5.11: the Watcher mentions Galnet at most once a day, and each headline
only once (it kept repeating the top story)."""

import random
import unittest

from voidcompass.overlays.watcher_mind import GALNET_REST_S, WatcherMind


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


class GalnetOnce(unittest.TestCase):
    def mind(self):
        clock = Clock()
        rng = random.Random(1)
        rng.random = lambda: 0.0      # never keeps it to itself
        mind = WatcherMind(memory_path=None, config={"heartbeat_thoughts": "chatty"}, clock=clock, rng=rng)
        mind.session_start()
        return mind, clock

    def say(self, mind, clock, headline, later):
        clock.now += later
        mind._last_spoke = 0.0
        return mind.consider("idle_galnet", {"headline": headline})

    def test_once_a_day(self):
        mind, clock = self.mind()
        self.assertIsNotNone(self.say(mind, clock, "Thargoids sighted near Sol", 0))
        self.assertIsNone(self.say(mind, clock, "A new Galnet story", 3 * 3600), "not again the same day")
        self.assertIsNotNone(self.say(mind, clock, "A new Galnet story", GALNET_REST_S))

    def test_each_headline_once(self):
        mind, clock = self.mind()
        self.assertIsNotNone(self.say(mind, clock, "Thargoids sighted near Sol", 0))
        self.assertIsNone(self.say(mind, clock, "Thargoids sighted near Sol", 2 * GALNET_REST_S), "old news")
        self.assertIsNone(mind.consider("idle_galnet", {"headline": "thargoids sighted near sol"}, force=True))


if __name__ == "__main__":
    unittest.main()
