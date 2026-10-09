"""5.5.3.2: a long session on Chatty (four hours of jumping, scanning,
scooping, landing and walking about) never repeats a line, in either voice,
and the Watcher keeps talking throughout."""

import random
import unittest
from datetime import datetime

from voidcompass.overlays import watcher_lines
from voidcompass.overlays.watcher_mind import IMPORTANCE, WatcherMind

START = datetime(2026, 10, 9, 19, 0).timestamp()


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def session(nature, frequency="chatty", hours=4, seed=11):
    """A synthetic evening of exploration, returning every thought said."""
    clock = Clock(START)
    rng = random.Random(seed)
    mind = WatcherMind(None, {"heartbeat_thoughts": frequency, "heartbeat_personality": nature}, clock, random.Random(seed))
    said = []

    def hear(thought):
        if thought:
            said.append(thought["text"])

    hear(mind.observe("LoadGame", {"Ship_Localised": "Mandalay", "ShipName": "Quiet Hours"}))
    hear(mind.observe("SuitLoadout", {"SuitName_Localised": "Artemis Suit"}))
    context = {"music": {"title": "Long Way Out", "artist": "The Drift"}, "galnet": "Thargoid activity reported"}
    end = START + hours * 3600
    next_jump = START + 60
    jump = 0
    while clock.now < end:
        clock.now += 15
        if clock.now >= next_jump:
            jump += 1
            system = f"Synuefe AB-{jump} c{jump % 9}"
            star = rng.choice(["K", "M", "G", "F", "DA", "N", "A", "B"])
            hear(mind.observe("StartJump", {"JumpType": "Hyperspace", "StarClass": star}))
            hear(mind.observe("FSDJump", {"StarSystem": system, "StarPos": [800 + jump * 30, 0, 9000 + jump * 25],
                                          "JumpDist": rng.choice([38.2, 45.6, 61.3, 52.0])}))
            hear(mind.observe("FSSDiscoveryScan", {"BodyCount": rng.choice([1, 2, 6, 14, 23, 31])}))
            if rng.random() < .6:
                hear(mind.observe("FuelScoop", {}))
            for body in range(rng.randint(1, 3)):
                hear(mind.observe("Scan", {"BodyName": f"{system} {body + 1}", "PlanetClass": rng.choice(
                    ["Rocky body", "Icy body", "High metal content body", "Water world", "Helium gas giant"]),
                    "WasDiscovered": rng.random() < .5}))
            if rng.random() < .3:
                hear(mind.observe("FSSAllBodiesFound", {"SystemName": system}))
            if rng.random() < .25:
                hear(mind.observe("SAAScanComplete", {"BodyName": f"{system} 1", "ProbesUsed": 5, "EfficiencyTarget": 6}))
            if rng.random() < .15:
                hear(mind.observe("SupercruiseExit", {"Body": f"{system} 2", "BodyType": "Planet"}))
                hear(mind.observe("Touchdown", {"Body": f"{system} 2", "PlayerControlled": True}))
                hear(mind.observe("Disembark", {"OnPlanet": True}))
                hear(mind.observe("ScanOrganic", {"ScanType": "Analyse", "Species_Localised": f"Bacterium {jump}"}))
                hear(mind.observe("Embark", {}))
                hear(mind.observe("Liftoff", {}))
            # Sometimes a long quiet stretch between jumps.
            next_jump = clock.now + rng.choice([120, 180, 240, 600, 900])
        if int(clock.now) % 30 == 0:
            hear(mind.tick(context))
        hear(mind.follow_up())
    return said


class LongSessionTests(unittest.TestCase):
    def test_four_hours_on_chatty_never_repeats_a_line(self):
        for nature in ("weary", "curious"):
            with self.subTest(nature=nature):
                said = session(nature)
                repeats = sorted({line for line in said if said.count(line) > 1})
                self.assertEqual(repeats, [], f"{nature}: a line came back in one session")
                self.assertGreater(len(said), 60, f"{nature}: it keeps talking through the evening")

    def test_every_topic_has_a_deep_bank(self):
        for topic in IMPORTANCE:
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10, topic)

    def test_no_line_is_said_by_two_topics(self):
        from voidcompass.overlays.watcher_mind import plain_text
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            lines = [plain_text(line) for lines in bank.values() for line in lines]
            self.assertEqual(len(lines), len(set(lines)))


if __name__ == "__main__":
    unittest.main()


class FlyingAndWalkingTests(unittest.TestCase):
    """It knows what you're doing in Elite: supercruise, the SRV, a
    settlement, a taxi, a carrier, the concourse, your ship and suit."""

    def topics(self, around):
        return dict(around.choices(START, random.Random(1), {}))

    def test_where_you_are(self):
        from voidcompass.overlays.watcher_idle import Surroundings
        around = Surroundings()
        around.observe("LoadGame", {"Ship_Localised": "Krait Phantom", "ShipName": "Nightjar"})
        around.observe("FSDJump", {"StarSystem": "Prai", "StarPos": [0, 0, 20]})
        self.assertEqual(self.topics(around)["idle_supercruise"]["system"], "Prai")
        self.assertEqual(self.topics(around)["idle_ship"], {"ship": "Krait Phantom", "ship_name": "Nightjar"})
        around.observe("SupercruiseExit", {"Body": "Prai 3", "BodyType": "Planet"})
        self.assertEqual(self.topics(around)["idle_near_body"]["body"], "Prai 3")
        around.observe("ApproachSettlement", {"Name": "$Ancient:#index=1;", "Name_Localised": "Hughes Biotech Hub"})
        self.assertEqual(self.topics(around)["idle_settlement"]["settlement"], "Hughes Biotech Hub")
        around.observe("Touchdown", {"Body": "Prai 3", "PlayerControlled": True})
        around.observe("LaunchSRV", {})
        self.assertEqual(self.topics(around)["idle_srv"]["body"], "Prai 3")
        around.observe("DockSRV", {})
        around.observe("SuitLoadout", {"SuitName_Localised": "Dominator Suit"})
        around.observe("Disembark", {"OnPlanet": True})
        self.assertEqual(self.topics(around)["idle_on_foot"], {"body": "Prai 3", "suit": "Dominator Suit"})
        self.assertNotIn("idle_ship", self.topics(around), "on foot, it talks about you, not the ship")

    def test_stations_carriers_and_taxis(self):
        from voidcompass.overlays.watcher_idle import Surroundings
        around = Surroundings()
        around.observe("Docked", {"StationName": "K7Q-1HT", "StationType": "FleetCarrier"})
        self.assertIn("idle_carrier", self.topics(around))
        around.observe("Undocked", {})
        around.observe("Docked", {"StationName": "Jameson Memorial", "StationType": "Orbis"})
        around.observe("Disembark", {"OnStation": True})
        self.assertEqual(self.topics(around)["idle_station_foot"]["station"], "Jameson Memorial")
        around.observe("BookTaxi", {})
        around.observe("Embark", {"Taxi": True})
        self.assertIn("idle_taxi", self.topics(around))

    def test_flying_events_get_remarks(self):
        clock = Clock(START)
        mind = WatcherMind(None, {"heartbeat_thoughts": "chatty", "heartbeat_personality": "curious"}, clock,
                           random.Random(5))
        mind.observe("LoadGame", {})
        heard = set()
        for event, raw in (("JetConeBoost", {"BoostValue": 4}), ("HeatWarning", {}), ("EscapeInterdiction", {}),
                           ("LaunchSRV", {}), ("ApproachSettlement", {"Name_Localised": "Ross Base"}),
                           ("BookTaxi", {}), ("CarrierJump", {"StarSystem": "Colonia"})):
            for _ in range(6):
                clock.now += 400
                thought = mind.observe(event, raw)
                if thought:
                    heard.add(thought["topic"])
                    break
        self.assertTrue({"jet_boost", "heat_warning", "interdiction_escaped", "srv_launch", "settlement_seen",
                         "taxi_ride", "carrier_jump"} <= heard, heard)

    def test_it_saves_what_it_said_every_few_minutes(self):
        import json
        import tempfile
        from pathlib import Path
        path = Path(tempfile.mkdtemp()) / "watcher_memory.json"
        mind = WatcherMind(path, {"heartbeat_thoughts": "chatty"}, Clock(START), random.Random(1))
        mind.consider("quiet", force=True)
        mind.save_if_due(every=0)
        self.assertTrue(json.loads(path.read_text(encoding="utf-8"))["said"])
