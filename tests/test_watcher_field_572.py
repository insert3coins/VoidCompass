"""5.7.2: in the field, the Watcher says when you're the first (the first
world nobody found in a charted system, the first map, the first footsteps)
and how far to go between biology samples, and when you're far enough."""
from __future__ import annotations

import unittest

from voidcompass.overlays import watcher_field, watcher_lines, watcher_mind
from voidcompass.overlays.watcher_mind import WatcherMind

from tests.test_watcher_worlds_5539 import Clock

TOPICS = ("planet_first", "mapped_first", "footfall_first", "sample_first", "sample_second", "sample_clear")


def arrival(discovered=True):
    return {"event": "Scan", "BodyName": "Hypio A", "StarType": "K", "DistanceFromArrivalLS": 0.0,
            "WasDiscovered": discovered}


def world(name="Hypio A 3", discovered=False, mapped=False, walked=False, planet="Rocky body"):
    return {"event": "Scan", "BodyName": name, "PlanetClass": planet, "DistanceFromArrivalLS": 420.0,
            "WasDiscovered": discovered, "WasMapped": mapped, "WasFootfalled": walked}


def organic(kind, species="Bacterium Aurasus", genus="Bacterium"):
    return {"event": "ScanOrganic", "ScanType": kind, "Species_Localised": species, "Genus_Localised": genus}


class BankTests(unittest.TestCase):
    def test_every_topic_has_its_words_in_each_voice(self):
        fields = {"body": "Hypio A 3", "species": "Bacterium Aurasus", "distance": "500"}
        for topic in TOPICS:
            self.assertIn(topic, watcher_mind.TOPICS)
            self.assertIn(topic, watcher_mind.MOODS)
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10, topic)
                for line in bank[topic]:
                    text = line.format(**fields)
                    self.assertTrue(text[:1].isupper() or text[:1].isdigit(), text)
                    self.assertNotIn("Marvin", text)
                    if topic.startswith("sample_"):
                        self.assertIn("{species}", line, line)
        for topic in ("sample_first", "sample_second"):
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertTrue(all("{distance}" in line for line in bank[topic]), "every line says how far")


class FieldTests(unittest.TestCase):
    def mind(self, nature="stoic"):
        clock = Clock()
        mind = WatcherMind(None, {"heartbeat_thoughts": "chatty", "heartbeat_personality": nature}, clock)
        mind.session_start()
        clock.now += 3600
        # These cases check event routing, so choose to speak minor remarks.
        mind.random.random = lambda: 0.0
        return mind, clock

    def test_the_first_world_nobody_found_in_a_charted_system(self):
        mind, clock = self.mind()
        mind.observe("Scan", arrival(discovered=True))
        clock.now += 30
        thought = mind.observe("Scan", world())
        self.assertEqual(thought["topic"], "planet_first")
        self.assertIn("Hypio A 3", thought["text"])
        clock.now += 30
        self.assertNotEqual((mind.observe("Scan", world("Hypio A 4")) or {}).get("topic"), "planet_first",
                            "once a system: the overlays list the rest")
        mind.observe("FSDJump", {"event": "FSDJump", "StarSystem": "Elsewhere", "JumpDist": 10})
        clock.now += 30
        mind.observe("Scan", dict(arrival(True), BodyName="Elsewhere A"))
        clock.now += 30
        self.assertEqual(mind.observe("Scan", world("Elsewhere 1"))["topic"], "planet_first", "a new system, again")

    def test_an_uncharted_system_has_its_own_words(self):
        mind, clock = self.mind()
        mind.observe("Scan", arrival(discovered=False))   # its own remark (a minor one: it may keep it to itself)
        clock.now += 30
        self.assertNotEqual((mind.observe("Scan", world()) or {}).get("topic"), "planet_first")

    def test_a_special_world_keeps_its_own_words(self):
        mind, clock = self.mind()
        mind.observe("Scan", arrival(True))
        clock.now += 30
        self.assertEqual(mind.observe("Scan", world(planet="Earthlike body"))["topic"], "world_first")

    def test_the_first_map_and_the_first_footsteps(self):
        mind, clock = self.mind("weary")
        mind.observe("Scan", arrival(True))
        mind.observe("Scan", world(discovered=True, mapped=False, walked=False))
        clock.now += 60
        thought = mind.observe("SAAScanComplete", {"event": "SAAScanComplete", "BodyName": "Hypio A 3",
                                                   "ProbesUsed": 4, "EfficiencyTarget": 6})
        self.assertEqual(thought["topic"], "mapped_first")
        clock.now += 60
        thought = mind.observe("Disembark", {"event": "Disembark", "Body": "Hypio A 3", "OnPlanet": True,
                                             "OnStation": False, "SRV": True})
        self.assertEqual(thought["topic"], "footfall_first")
        self.assertIn("Hypio A 3", thought["text"])

    def test_a_world_others_mapped_is_just_mapped(self):
        mind, clock = self.mind()
        mind.observe("Scan", world(discovered=True, mapped=True))
        clock.now += 60
        thought = mind.observe("SAAScanComplete", {"event": "SAAScanComplete", "BodyName": "Hypio A 3",
                                                   "ProbesUsed": 4, "EfficiencyTarget": 6})
        self.assertEqual(thought["topic"], "mapped_efficient")

    def test_how_far_to_the_next_sample(self):
        mind, clock = self.mind()
        thought = mind.observe("ScanOrganic", organic("Log"))
        self.assertEqual(thought["topic"], "sample_first")
        self.assertIn("500", thought["text"])
        self.assertIn("Bacterium Aurasus", thought["text"])
        clock.now += 5
        thought = mind.observe("ScanOrganic", organic("Sample"))
        self.assertEqual(thought["topic"], "sample_second", "said even straight after the first")
        self.assertIn("500", thought["text"])
        clock.now += 5
        thought = mind.observe("ScanOrganic", organic("Log", "Osseus Spiralis", "Osseus"))
        self.assertIn("800", thought["text"], "each genus its own distance")

    def test_far_enough_from_the_last_sample(self):
        mind, _clock = self.mind()
        thought = mind.note("sample_clear", {"species": "Bacterium Aurasus", "distance": "500"})
        self.assertEqual(thought["topic"], "sample_clear")
        self.assertIn("Bacterium Aurasus", thought["text"])

    def test_off_means_off(self):
        clock = Clock()
        mind = WatcherMind(None, {"heartbeat_thoughts": "off"}, clock)
        mind.session_start()
        self.assertIsNone(mind.observe("ScanOrganic", organic("Log")))


class DashboardTests(unittest.TestCase):
    def test_clear_is_said_once_a_sample(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        noted = []
        app = MainDashboard.__new__(MainDashboard)
        app.heartbeat_hud = type("Hud", (), {"note": lambda self, kind, fields: noted.append((kind, fields))})()
        app._ui_post = lambda callback, *args, key=None, **kwargs: callback(*args, **kwargs)
        sample = {"clear": True, "progress": 1, "colony_m": 500, "species": "Bacterium Aurasus", "body": 3}
        app._watcher_sample_clear(sample)
        app._watcher_sample_clear(sample)
        self.assertEqual(noted, [("sample_clear", {"species": "Bacterium Aurasus", "distance": "500"})])
        app._watcher_sample_clear({**sample, "progress": 2})
        self.assertEqual(len(noted), 2, "and again after the second sample")
        app._watcher_sample_clear({**sample, "progress": 3})
        app._watcher_sample_clear({**sample, "progress": 2, "clear": False, "species": "Osseus Spiralis"})
        self.assertEqual(len(noted), 2, "not after the third, and not while too close")


class NotesTests(unittest.TestCase):
    def test_jumping_forgets_the_systems_scans(self):
        notes = watcher_field.FieldNotes()
        notes.observe("Scan", arrival(True))
        notes.observe("Scan", world())
        self.assertTrue(notes.charted)
        self.assertIn("Hypio A 3", notes.unmapped)
        notes.observe("FSDJump", {})
        self.assertIsNone(notes.charted)
        self.assertEqual((notes.unmapped, notes.unwalked), (set(), set()))


if __name__ == "__main__":
    unittest.main()
