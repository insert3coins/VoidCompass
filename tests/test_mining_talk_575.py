"""Mining in a ring, followed by every companion (5.7.5)."""
import random
import unittest

from voidcompass.core import companions
from voidcompass.overlays import companion_personas, mining_talk, watcher_mind
from tests.test_aster_companion import Clock

CREW = ("watcher", "aster", "axiom", "meridian")
RING = "Sim 3 A Ring"


def refined(trip, material, times=1, srv=False):
    result = None
    for _ in range(times):
        result = trip.observe("MiningRefined", {"Type_Localised": material}, srv=srv) or result
    return result


class TripTests(unittest.TestCase):
    def test_hotspots_are_named_and_remembered_for_the_arrival(self):
        trip = mining_talk.MiningTrip()
        topic, fields = trip.observe("SAASignalsFound", {"BodyName": RING, "Signals": [
            {"Type": "Platinum", "Type_Localised": "Platinum", "Count": 2}, {"Type": "LowTemperatureDiamond", "Count": 1},
            {"Type": "$SAA_SignalType_Geological;", "Count": 3}]})
        self.assertEqual((topic, fields["hotspots"]), ("ring_hotspots", "2 Platinum and 1 LowTemperatureDiamond"))
        self.assertIsNone(trip.observe("SAASignalsFound", {"BodyName": "Sim 3 a", "Signals": [{"Type": "Gold", "Count": 1}]}),
                          "a planet's signals aren't ring hotspots")
        topic, fields = trip.observe("SupercruiseExit", {"Body": RING, "BodyType": "PlanetaryRing"})
        self.assertEqual((topic, fields["ring"], fields["hotspots"]), ("ring_arrival", RING, "2 Platinum and 1 LowTemperatureDiamond"))
        self.assertTrue(trip.active)

    def test_rocks_tallies_the_hold_and_limpets(self):
        trip = mining_talk.MiningTrip()
        self.assertIsNone(refined(trip, "Platinum"), "nothing counts outside a ring")
        trip.observe("SupercruiseExit", {"Body": RING, "BodyType": "PlanetaryRing"})
        self.assertEqual(trip.observe("ProspectedAsteroid", {"Materials": [{"Proportion": 4.0}], "Remaining": 100})[0],
                         "prospected_poor")
        self.assertEqual(trip.observe("ProspectedAsteroid", {"Materials": [{"Proportion": 40.0}], "Remaining": 0})[0],
                         "prospected_depleted")
        self.assertIsNone(trip.observe("ProspectedAsteroid", {"Materials": [{"Proportion": 40.0}], "Remaining": 100}),
                          "a good rock is the rich-rock remark's business")
        self.assertIsNone(trip.observe("ProspectedAsteroid", {"MotherlodeMaterial": "Painite", "Materials": [], "Remaining": 100}))
        self.assertIsNone(trip.observe("Cargo", {"Vessel": "Ship", "Count": 40}, capacity=64), "nothing refined yet")
        self.assertEqual(refined(trip, "Platinum", 10), ("mining_tally", {"tonnes": "10", "material": "Platinum"}))
        self.assertIsNone(refined(trip, "Platinum", 5, srv=True), "the Rhino's refining is the rigs' business")
        self.assertEqual(trip.observe("Cargo", {"Vessel": "Ship", "Count": 32}, capacity=64)[0], "hold_half_mining")
        self.assertIsNone(trip.observe("Cargo", {"Vessel": "Ship", "Count": 33}, capacity=64), "once a trip")
        self.assertIsNone(trip.observe("LaunchDrone", {"Type": "Prospector"}, limpets=6))
        self.assertEqual(trip.observe("LaunchDrone", {"Type": "Collection"}, limpets=2), ("limpets_low", {"count": "2"}))
        self.assertIsNone(trip.observe("LaunchDrone", {"Type": "Collection"}, limpets=1), "once a trip")
        refined(trip, "Painite", 3)
        topic, fields = trip.observe("SupercruiseEntry", {})
        self.assertEqual((topic, fields["summary"]), ("mining_summary", "13 tonnes refined: 10 Platinum and 3 Painite."))
        self.assertFalse(trip.active)

    def test_a_single_material_and_an_empty_trip(self):
        trip = mining_talk.MiningTrip()
        trip.observe("SupercruiseExit", {"Body": RING, "BodyType": "PlanetaryRing"})
        refined(trip, "Bromellite")
        self.assertEqual(trip.summary(), "One tonne of Bromellite.")
        trip.observe("SupercruiseExit", {"Body": RING, "BodyType": "PlanetaryRing"})
        self.assertIsNone(trip.observe("Docked", {}), "nothing mined, nothing to sum up")


class CompanionTests(unittest.TestCase):
    def mind(self, identity):
        config = {"companion_identity": identity, f"{identity}_thoughts": "chatty", "heartbeat_thoughts": "chatty"}
        companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(4))
        companion.memory["hours"] = 20
        companion.session_start()
        companion.random.random = lambda: 0.0
        companion.learn({"cargo_capacity": 64, "limpets": 3})
        return companion

    def test_every_companion_follows_a_ring_visit(self):
        for identity in CREW:
            companion = self.mind(identity)
            heard = []
            for event, raw in (("SAASignalsFound", {"BodyName": RING, "Signals": [{"Type": "Platinum", "Count": 2}]}),
                               ("SupercruiseExit", {"Body": RING, "BodyType": "PlanetaryRing"}),
                               ("LaunchDrone", {"Type": "Prospector"}),
                               ("ProspectedAsteroid", {"Materials": [{"Proportion": 3.0}], "Remaining": 100})):
                companion.clock.now += 400
                thought = companion.observe(event, {"event": event, **raw})
                heard.append((thought or {}).get("topic"))
            self.assertEqual(heard, ["ring_hotspots", "ring_arrival", "limpets_low", "prospected_poor"], identity)
            self.assertEqual(companion._limpets, 2, "each launch counted until the deck says otherwise")

    def test_the_haul_waits_its_turn_when_something_was_just_said(self):
        for identity in CREW:
            companion = self.mind(identity)
            companion.observe("SupercruiseExit", {"event": "SupercruiseExit", "Body": RING, "BodyType": "PlanetaryRing"})
            for _ in range(4):
                companion.observe("MiningRefined", {"event": "MiningRefined", "Type_Localised": "Painite"})
            companion.consider("green_giant", {"system": "Sim"}, force=True)
            companion.observe("SupercruiseEntry", {"event": "SupercruiseEntry"})
            heard = None
            for _ in range(30):
                companion.clock.now += 5
                thought = companion.tick()
                if thought and thought["topic"] == "mining_summary":
                    heard = thought
                    break
            self.assertIsNotNone(heard, identity)
            self.assertIn("4 tonnes of Painite.", heard["text"])

    def test_every_companion_has_depth_for_mining(self):
        for topic, level in mining_talk.IMPORTANCE.items():
            self.assertEqual(watcher_mind.IMPORTANCE[topic], level)
            self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 10)
            self.assertGreaterEqual(len(watcher_mind.WEARY[topic]), 10)
            for identity in ("aster", "axiom", "meridian"):
                lines = companion_personas.get(identity).lines
                self.assertGreaterEqual(len(lines.event_lines(topic)), 9, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))
                for line in lines.event_lines(topic):
                    self.assertNotIn(": {summary}", line, "the summary already has a colon")


if __name__ == "__main__":
    unittest.main()
