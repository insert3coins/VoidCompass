"""The ship's everyday life, which the companions used to let pass (5.7.5)."""
import random
import re
import unittest

from voidcompass.core import companions
from voidcompass.overlays import companion_personas, ship_life, watcher_mind
from tests.test_aster_companion import Clock

CREW = ("watcher", "aster", "axiom", "meridian", "lyra")
EVENTS = (("DockingGranted", {"LandingPad": 5}, "docking_granted"),
          ("DockingDenied", {"Reason": "NoSpace"}, "docking_denied"),
          ("RefuelAll", {"Amount": 12.5}, "refuelled"),
          ("ShipyardSwap", {"ShipType": "diamondbackxl", "ShipType_Localised": "Diamondback Explorer"}, "ship_swap"),
          ("RepairDrone", {"HullRepaired": 112.4}, "repaired"),
          ("AfmuRepairs", {"Module_Localised": "Thrusters"}, "repaired"),
          ("Scanned", {"ScanType": "Cargo"}, "scanned"),
          ("USSDrop", {"USSType_Localised": "Degraded emissions"}, "uss_drop"),
          ("HeatDamage", {}, "heat_damage"),
          ("JetConeDamage", {"Module_Localised": "Supercruise Assist"}, "jet_damage"),
          ("CarrierJumpRequest", {"SystemName": "Col 359 Sector PE-X b16-6"}, "carrier_jump_set"),
          ("CarrierJumpCancelled", {}, "carrier_jump_cancelled"),
          ("PowerplayRank", {"Power": "Yuri Grom", "Rank": 12}, "powerplay_rank"),
          ("Synthesis", {"Name": "FSD Premium"}, "synthesis"),
          ("Screenshot", {"System": "Pria Ain JK-M b22-0"}, "screenshot"))


class MomentTests(unittest.TestCase):
    def test_each_event_and_what_it_carries(self):
        for event, raw, topic in EVENTS:
            self.assertEqual(ship_life.moment(event, raw)[0], topic, event)
        self.assertEqual(ship_life.moment("DockingDenied", {"Reason": "Distance"})[1],
                         {"reason": "we're too far out", "Reason": "We're too far out"})
        self.assertEqual(ship_life.moment("DockingDenied", {"Reason": "Something new"})[1]["reason"], "no reason given")
        self.assertEqual(ship_life.moment("USSDrop", {"USSType_Localised": "High grade emissions"})[1]["Signal"],
                         "High grade emissions")
        self.assertEqual(ship_life.moment("ShipyardSwap", {"ShipType": "type9_military"})[1]["ship"], "Type9 Military")

    def test_what_stays_quiet(self):
        self.assertIsNone(ship_life.moment("RefuelAll", {"Amount": 0.03}), "the scrap after scooping")
        self.assertIsNone(ship_life.moment("PowerplayRank", {"Power": "Yuri Grom", "Rank": 0}), "pledging isn't a promotion")
        self.assertIsNone(ship_life.moment("USSDrop", {"USSType": "$USS_Type_Unknown;"}))
        self.assertIsNone(ship_life.moment("Music", {}))

    def test_recipes_read_after_synthesised(self):
        for name, words in (("FSD Basic", "a basic FSD injection"), ("FSD Premium", "a premium FSD injection"),
                            ("Limpet Basic", "limpets"), ("Mining Rig Basic", "mining rigs"), ("Fuel Standard", "standard fuel"),
                            ("Repair Standard", "a repair"), ("AFM Refill", "AFMU refills"), ("Plasma Ammo Standard", "ammunition")):
            self.assertEqual(ship_life.recipe(name), words, name)


class CompanionTests(unittest.TestCase):
    def test_every_companion_speaks_to_every_moment(self):
        for identity in CREW:
            config = {"companion_identity": identity, f"{identity}_thoughts": "chatty", "heartbeat_thoughts": "chatty"}
            companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(2))
            companion.session_start()
            companion.random.random = lambda: 0.0
            for event, raw, topic in EVENTS:
                with self.subTest(identity=identity, event=event):
                    companion.clock.now += 400
                    thought = companion.observe(event, {"event": event, **raw})
                    self.assertEqual((thought or {}).get("topic"), topic)
                    self.assertNotIn("{", thought["text"])
                    for sentence in re.split(r"(?<=[.!?]) ", thought["text"]):
                        self.assertFalse(sentence[:1].islower(), thought["text"])

    def test_docking_is_acknowledged_even_on_quieter_settings(self):
        """It was importance 0: never said on Occasional or Rare."""
        self.assertEqual(watcher_mind.IMPORTANCE["docked_home"], 2)
        self.assertEqual(watcher_mind.IMPORTANCE["docking_granted"], 1)
        self.assertEqual(watcher_mind.IMPORTANCE["undocked"], 1)
        for identity, frequency in (("meridian", "occasional"), ("watcher", "rare")):
            config = {"companion_identity": identity, f"{identity}_thoughts": frequency, "heartbeat_thoughts": frequency}
            companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(2))
            companion.session_start()
            companion.clock.now += 1200
            thought = companion.observe("Docked", {"event": "Docked", "StationName": "Jameson Memorial", "StationType": "Orbis"})
            self.assertEqual((thought or {}).get("topic"), "docked_home", (identity, frequency))

    def test_depth_for_every_companion(self):
        for topic, level in ship_life.IMPORTANCE.items():
            self.assertEqual(watcher_mind.IMPORTANCE[topic], level)
            self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 10)
            self.assertGreaterEqual(len(watcher_mind.WEARY[topic]), 10)
            for identity in ("aster", "axiom", "meridian", "lyra"):
                lines = companion_personas.get(identity).lines
                self.assertGreaterEqual(len(lines.event_lines(topic)), 9, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))


if __name__ == "__main__":
    unittest.main()
