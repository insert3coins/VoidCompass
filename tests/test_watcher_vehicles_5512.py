"""5.5.12: the Watcher knows what you took out of the ship (the Scarab, the
Scorpion, the Rhino, the Nomad, a fighter) and has words for each, and for
mining's moments: a rich rock, a motherlode, a cracked one, a full hold."""

import re
import unittest
from pathlib import Path

from voidcompass.overlays import watcher_lines
from voidcompass.overlays.watcher_idle import Surroundings, vehicle_kind
from voidcompass.overlays.watcher_mind import WatcherMind

VEHICLES = ("scarab", "scorpion", "rhino", "nomad", "fighter")
NAMES = {"scarab": "Scarab", "scorpion": "Scorpion", "rhino": "Rhino", "nomad": "Nomad"}


class KindTests(unittest.TestCase):
    def test_each_vehicle_by_its_journal_name(self):
        self.assertEqual(vehicle_kind({"event": "LaunchSRV", "SRVType": "mev_rhino"}), "rhino")
        # The Rhino launches with the Nomad's loadout name (from a real journal).
        self.assertEqual(vehicle_kind({"event": "LaunchSRV", "SRVType": "mev_rhino", "SRVType_Localised": "SRV Rhino",
                                       "Loadout": "galactic", "ID": 133, "PlayerControlled": True}), "rhino")
        self.assertEqual(vehicle_kind({"event": "LaunchSRV", "SRVType": "testbuggy"}), "scarab")
        self.assertEqual(vehicle_kind({"event": "LaunchSRV", "SRVType": "combat_multicrew_srv_01"}), "scorpion")
        self.assertEqual(vehicle_kind({"event": "LaunchFighter", "Loadout": "galactic", "PlayerControlled": True}), "nomad")
        self.assertEqual(vehicle_kind({"event": "LaunchFighter", "Loadout": "starter", "PlayerControlled": True}), "fighter")
        self.assertEqual(vehicle_kind({"event": "LoadGame", "Ship": "TestBuggy"}), "scarab")
        self.assertEqual(vehicle_kind({"event": "LoadGame", "Ship": "Type9"}), "")


def topics(surroundings):
    return [topic for topic, _fields in surroundings.choices(0, __import__("random").Random(1))]


class SurroundingsTests(unittest.TestCase):
    def test_idle_in_the_vehicle_you_are_in(self):
        here = Surroundings()
        here.observe("Touchdown", {"Body": "Ba Po C 3", "PlayerControlled": True})
        here.observe("LaunchSRV", {"SRVType": "mev_rhino"})
        self.assertIn("idle_rhino", topics(here))
        self.assertNotIn("idle_srv", topics(here))
        rhino = dict(here.choices(0, __import__("random").Random(1)))["idle_rhino"]
        self.assertEqual(rhino, {"body": "Ba Po C 3"})
        here.observe("DockSRV", {})
        self.assertNotIn("idle_rhino", topics(here))

    def test_the_nomad_and_fighters(self):
        here = Surroundings()
        here.observe("Location", {"StarSystem": "Sol"})
        here.observe("LaunchFighter", {"event": "LaunchFighter", "Loadout": "galactic", "PlayerControlled": True})
        self.assertIn("idle_nomad", topics(here))
        here.observe("DockFighter", {})
        here.observe("LaunchFighter", {"event": "LaunchFighter", "Loadout": "one", "PlayerControlled": True})
        self.assertIn("idle_fighter", topics(here))
        here.observe("VehicleSwitch", {"To": "Mothership"})
        self.assertNotIn("idle_fighter", topics(here))

    def test_loaded_in_while_out_in_an_srv(self):
        here = Surroundings()
        here.observe("LoadGame", {"Ship": "TestBuggy", "Ship_Localised": "SRV Scarab"})
        self.assertEqual((here.srv, here.vehicle, here.ship), (True, "scarab", ""), "the SRV isn't your ship")
        here.observe("LoadGame", {"Ship": "Type9", "Ship_Localised": "Type-9 Heavy"})
        self.assertEqual((here.srv, here.vehicle, here.ship), (False, "", "Type-9 Heavy"))

    def test_drifting_in_a_ring(self):
        here = Surroundings()
        here.observe("SupercruiseExit", {"Body": "Ba Po 1 A Ring", "BodyType": "PlanetaryRing"})
        self.assertEqual(dict(here.choices(0, __import__("random").Random(1))).get("idle_ring"), {"ring": "Ba Po 1 A Ring"})
        here.observe("SupercruiseEntry", {})
        self.assertNotIn("idle_ring", topics(here))


class MindTests(unittest.TestCase):
    def mind(self):
        mind = WatcherMind(memory_path=None, config={})
        mind.session_start()
        said = []
        mind.consider = lambda topic, fields=None, force=False: said.append((topic, dict(fields or {})))
        return mind, said

    def test_launches_by_name(self):
        mind, said = self.mind()
        for raw, topic in (({"SRVType": "mev_rhino"}, "launch_rhino"), ({"SRVType": "testbuggy"}, "launch_scarab"),
                           ({"SRVType": "combat_multicrew_srv_01"}, "launch_scorpion"), ({"SRVType": "something new"}, "srv_launch")):
            mind.observe("LaunchSRV", raw)
            self.assertEqual(said[-1][0], topic)
        mind.observe("LaunchFighter", {"event": "LaunchFighter", "Loadout": "galactic", "PlayerControlled": True})
        self.assertEqual(said[-1][0], "launch_nomad")
        mind.observe("LaunchFighter", {"event": "LaunchFighter", "Loadout": "two", "PlayerControlled": True})
        self.assertEqual(said[-1][0], "launch_fighter")
        count = len(said)
        mind.observe("LaunchFighter", {"event": "LaunchFighter", "PlayerControlled": False})
        self.assertEqual(len(said), count, "a crew member's fighter isn't yours")

    def test_rocks(self):
        mind, said = self.mind()
        mind.observe("ProspectedAsteroid", {"Materials": [{"Name": "palladium", "Proportion": 34.6}], "Content": "x"})
        self.assertEqual(said[-1], ("prospected_rich", {"material": "Palladium", "percent": "35%"}))
        count = len(said)
        mind.observe("ProspectedAsteroid", {"Materials": [{"Name": "Bauxite", "Proportion": 12.0}]})
        self.assertEqual(len(said), count, "a dull rock goes unremarked")
        mind.observe("ProspectedAsteroid", {"Materials": [], "MotherlodeMaterial": "Painite"})
        self.assertEqual(said[-1], ("motherlode", {"material": "Painite"}))
        mind.observe("AsteroidCracked", {"Body": "Ring"})
        self.assertEqual(said[-1][0], "cracked")

    def test_full_holds_said_once(self):
        mind, said = self.mind()
        mind.observe("LaunchSRV", {"SRVType": "mev_rhino"})
        for count in (70, 72, 72):
            mind.observe("Cargo", {"Vessel": "SRV", "Count": count})
        self.assertEqual([topic for topic, _ in said].count("rhino_full"), 1)
        mind.observe("Cargo", {"Vessel": "SRV", "Count": 0})
        mind.observe("Cargo", {"Vessel": "SRV", "Count": 72})
        self.assertEqual([topic for topic, _ in said].count("rhino_full"), 2, "the next load fills it again")
        mind.observe("DockSRV", {})
        mind.observe("Loadout", {"CargoCapacity": 256})
        mind.observe("Cargo", {"Vessel": "Ship", "Count": 256})
        self.assertNotIn("hold_full_mining", [topic for topic, _ in said], "full, but not from mining")
        mind.observe("MiningRefined", {"Type_Localised": "Platinum"})
        mind.observe("Cargo", {"Vessel": "Ship", "Count": 255})
        mind.observe("Cargo", {"Vessel": "Ship", "Count": 256})
        self.assertEqual([topic for topic, _ in said].count("hold_full_mining"), 1)

    def test_a_full_hold_after_loading_anything(self):
        mind, said = self.mind()
        mind.observe("Loadout", {"CargoCapacity": 64})
        mind.observe("Cargo", {"Vessel": "Ship", "Count": 64})
        self.assertNotIn("hold_full", [topic for topic, _ in said], "sitting full isn't news")
        mind.observe("Cargo", {"Vessel": "Ship", "Count": 0})
        mind.observe("MarketBuy", {"Type": "gold", "Count": 64})
        mind.observe("Cargo", {"Vessel": "Ship", "Count": 64})
        self.assertEqual(said[-1][0], "hold_full")

    def test_the_small_srvs(self):
        mind, said = self.mind()
        mind.observe("LaunchSRV", {"SRVType": "testbuggy"})
        mind.observe("Cargo", {"Vessel": "SRV", "Count": 4})
        self.assertEqual(said[-1], ("srv_full", {"srv": "Scarab"}))
        mind.observe("DockSRV", {})
        mind.observe("LaunchSRV", {"SRVType": "combat_multicrew_srv_01"})
        mind.observe("Cargo", {"Vessel": "SRV", "Count": 2})
        self.assertEqual(said[-1], ("srv_full", {"srv": "Scorpion"}))

    def test_after_a_restart_the_deck_fills_the_gaps(self):
        mind, said = self.mind()
        mind.observe("Cargo", {"Vessel": "SRV", "Count": 40})       # restarted out in the Rhino
        self.assertEqual(mind.surroundings.vehicle, "")
        mind.learn({"vehicle": "rhino", "cargo_capacity": 256})
        self.assertEqual((mind.surroundings.vehicle, mind.surroundings.srv), ("rhino", True))
        mind.observe("Cargo", {"Vessel": "SRV", "Count": 72})
        self.assertEqual(said[-1][0], "rhino_full")
        mind.observe("DockSRV", {})
        mind.observe("MiningRefined", {"Type_Localised": "Platinum"})
        mind.observe("Cargo", {"Vessel": "Ship", "Count": 256})
        self.assertEqual(said[-1][0], "hold_full_mining", "the ship's hold size came from the deck")
        mind.observe("LaunchSRV", {"SRVType": "mev_rhino"})
        mind.learn({"vehicle": "scarab"})
        self.assertEqual(mind.surroundings.vehicle, "rhino", "the journal knows best once it has spoken")

    def test_the_deck_says_what_vehicle_and_hold(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        context = source.split("def _watcher_context", 1)[1].split("\n    def ", 1)[0]
        self.assertIn('context["vehicle"]', context)
        self.assertIn('context["cargo_capacity"]', context)


class LineTests(unittest.TestCase):
    def test_each_vehicle_keeps_to_its_own_name(self):
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            for kind in VEHICLES:
                others = [name for key, name in NAMES.items() if key != kind]
                for topic in (f"launch_{kind}", f"idle_{kind}"):
                    self.assertGreaterEqual(len(bank[topic]), 10, topic)
                    for line in bank[topic]:
                        self.assertFalse(any(name in line for name in others), (topic, line))

    def test_an_srv_it_cant_name_isnt_named(self):
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            for topic in ("srv_launch", "idle_srv"):
                for line in bank[topic]:
                    self.assertIsNone(re.search("Scarab|Scorpion|Rhino|Nomad", line), line)

    def test_mining_moments_have_their_fields(self):
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            self.assertTrue(all("{material}" in line and "{percent}" in line for line in bank["prospected_rich"]))
            self.assertTrue(all("{material}" in line for line in bank["motherlode"]))
            self.assertTrue(all("{ring}" in line for line in bank["idle_ring"]))
            self.assertTrue(all("{srv}" in line for line in bank["srv_full"]))
            self.assertGreaterEqual(len(bank["mined"]), 30)
            self.assertGreaterEqual(len(bank["mined_surface"]), 26)


if __name__ == "__main__":
    unittest.main()
