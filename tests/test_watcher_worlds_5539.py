"""The Watcher on the worlds worth stopping for (5.5.3.9): earth-likes, water
and ammonia worlds, terraformables, and one nobody has charted before."""
from __future__ import annotations

import unittest

from voidcompass.overlays import watcher_lines, watcher_mind, watcher_worlds
from voidcompass.overlays.watcher_mind import WatcherMind


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


def scan(planet, discovered=True, terraform="", temp=290.0, name="Hatchooe AB 3"):
    return {"event": "Scan", "BodyName": name, "PlanetClass": planet, "SurfaceTemperature": temp,
            "WasDiscovered": discovered, "TerraformState": terraform}


class WorldTests(unittest.TestCase):
    def mind(self, nature="stoic"):
        clock = Clock()
        mind = WatcherMind(None, {"heartbeat_thoughts": "chatty", "heartbeat_personality": nature}, clock)
        mind.session_start()
        clock.now += 3600
        return mind, clock

    def test_each_kind_in_its_own_words(self):
        for planet, topic in (("Earthlike body", "world_earthlike"), ("Water world", "world_water"),
                              ("Ammonia world", "world_ammonia")):
            for nature in ("stoic", "weary"):
                with self.subTest(planet=planet, nature=nature):
                    mind, clock = self.mind(nature)
                    topics = []
                    for _attempt in range(60):  # a minor remark may stay unsaid; try a few
                        clock.now += 500
                        thought = mind.observe("Scan", scan(planet))
                        topics.append((thought or {}).get("topic"))
                        if topics[-1] == topic:
                            break
                    self.assertIn(topic, topics)

    def test_an_earthlike_is_always_remarked_on(self):
        mind, _clock = self.mind("weary")
        self.assertEqual(mind.observe("Scan", scan("Earthlike body"))["topic"], "world_earthlike")

    def test_one_nobody_has_seen_before(self):
        mind, _clock = self.mind()
        thought = mind.observe("Scan", scan("Water world", discovered=False))
        self.assertEqual(thought["topic"], "world_first")
        self.assertIn("water world", thought["text"].lower())
        self.assertNotRegex(thought["text"], r"[a-z] A (water|earth)", "mid-sentence in lower case")

    def test_terraformable_worlds(self):
        mind, clock = self.mind()
        topics = []
        for _attempt in range(80):
            clock.now += 500
            thought = mind.observe("Scan", scan("High metal content body", terraform="Terraformable"))
            topics.append((thought or {}).get("topic"))
            if topics[-1] == "world_terraformable":
                break
        self.assertIn("world_terraformable", topics)

    def test_banks_deep_original_and_filled(self):
        fields = {"body": "B", "kind": "An earth-like", "kind_l": "an earth-like", "temp": "17°C"}
        for topic in ("world_earthlike", "world_water", "world_ammonia", "world_terraformable", "world_first"):
            self.assertIn(topic, watcher_mind.TOPICS)
            self.assertIn(topic, watcher_mind.MOODS)
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10, topic)
                for line in bank[topic]:
                    text = line.format(**fields)
                    self.assertNotIn("Marvin", text)
                    self.assertTrue(text[:1].isupper() or text[:1].isdigit(), text)

    def test_temperature_from_the_scan(self):
        self.assertTrue(any("{temp}" in line for line in watcher_worlds.EARTHLIKE_NORMAL))


if __name__ == "__main__":
    unittest.main()
