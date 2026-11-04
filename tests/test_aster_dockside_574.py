"""Aster keeps varied company in port without bypassing pace, repeats or voice preferences."""
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from voidcompass.overlays import aster_dockside, aster_lines, watcher_mind
from voidcompass.overlays.aster_mind import AsterMind, _fingerprint
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD
from voidcompass.overlays.watcher_idle import Surroundings


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.

    def __call__(self):
        return self.now


class AsterDocksideTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def mind(self, frequency="occasional", humour="dry", location="station", path=None):
        mind = AsterMind(path, {"companion_identity": "aster", "aster_thoughts": frequency, "aster_humour": humour},
                         clock=self.clock, rng=random.Random(7))
        mind.observe("LoadGame", {"Ship_Localised": "Mandalay", "ShipName": "Quiet Hours"})
        mind.observe("Location", {"StarSystem": "Sol", "Docked": True, "StationName": "Galileo",
                                  "StationType": "FleetCarrier" if location == "carrier" else "Orbis"})
        if location == "concourse":
            mind.observe("Disembark", {"OnStation": True})
        return mind

    def test_docked_location_restores_station_and_carrier_without_another_docking(self):
        for kind, expected in (("Orbis", "idle_docked"), ("FleetCarrier", "idle_carrier")):
            with self.subTest(kind=kind):
                around = Surroundings()
                around.supercruise = around.taxi = True
                around.observe("Location", {"Docked": True, "StationName": "Galileo", "StationType": kind})
                self.assertTrue(aster_dockside.active(around))
                self.assertFalse(around.supercruise)
                self.assertFalse(around.taxi)
                self.assertEqual(dict(around.choices(self.clock(), random.Random(1)))[expected]["station"], "Galileo")
                around.observe("Location", {"Docked": False, "StarSystem": "Achenar"})
                self.assertEqual(around.station, "")
                self.assertFalse(around.carrier)
                self.assertFalse(aster_dockside.active(around))

    def live_deck(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        deck = SimpleNamespace(
            config={"companion_identity": "aster", "galnet_enabled": False,
                    "aster_thoughts": "occasional",
                    "active_commander_name": "insert3coins", "active_commander_fid": "F1"},
            heartbeat_hud=SimpleNamespace(_status_serial=1, _last_pulse_ts=self.clock()),
            current_docked=True, current_station_name="Galileo", current_station_type="FleetCarrier")
        def context():
            with patch("voidcompass.dashboard.dashboard.time.time", self.clock):
                return MainDashboard._watcher_context(deck)
        return deck, context

    def test_live_port_context_wakes_a_fresh_or_switched_mind_without_replaying_history(self):
        deck, context = self.live_deck()
        mind = AsterMind(None, deck.config, clock=self.clock, rng=random.Random(7))
        first = mind.tick(context())
        self.assertEqual(first["topic"], "greet_new")
        self.assertEqual(mind.memory["sessions"], 1)
        self.assertEqual(mind.memory["name"]["known"], "insert3coins")
        self.assertEqual(mind.memory["name"]["fid"], "F1")
        self.assertEqual(mind.memory["name"]["seen"], 1)
        self.assertNotIn("call", mind.memory["name"], "reading the name does not grant permission")
        self.assertEqual(mind.memory["aster_marks"], {}, "snapshot learning is not a fabricated docking event")
        self.assertEqual(mind.surroundings.station, "Galileo")
        self.assertTrue(mind.surroundings.carrier)
        self.clock.now += 301
        deck.heartbeat_hud._last_pulse_ts = self.clock()
        with patch.object(mind, "remember", return_value=None):
            thought = mind.tick(context())
        self.assertIn(thought["topic"], (*aster_dockside.TOPICS, "idle_carrier", "quiet"))
        self.assertEqual(mind.memory["sessions"], 1, "subsequent telemetry does not restart the watch")

    def test_stale_or_unconfirmed_saved_port_state_does_not_wake_a_mind(self):
        deck, context = self.live_deck()
        mind = AsterMind(None, deck.config, clock=self.clock)
        deck.heartbeat_hud._last_pulse_ts = self.clock() - 60
        self.assertIsNone(mind.tick(context()))
        self.assertIsNone(mind._session_start)
        self.assertFalse(mind.surroundings.station)
        self.assertNotIn("known", mind.memory.get("name", {}))
        deck.heartbeat_hud._status_serial = 0
        self.assertNotIn("port", context())
        self.assertIsNone(mind.tick(context()))

    def test_live_undocked_snapshot_clears_the_port_watch_after_a_restart(self):
        deck, context = self.live_deck()
        mind = AsterMind(None, deck.config, clock=self.clock)
        mind.tick(context())
        deck.current_docked = False
        deck.current_station_name = None
        mind.learn(context())
        self.assertFalse(aster_dockside.active(mind.surroundings))
        self.assertFalse(any(topic in aster_dockside.TOPICS for topic, _ in mind._idle_choices(self.clock(), {})))

    def test_eight_hours_in_port_remain_varied_on_default_and_rare_in_both_modes(self):
        for frequency in ("occasional", "rare"):
            for humour in ("dry", "off"):
                for location in ("station", "carrier", "concourse"):
                    with self.subTest(frequency=frequency, humour=humour, location=location):
                        self.clock = Clock()
                        mind = self.mind(frequency, humour, location)
                        start = self.clock()
                        heard, times, topics = [], [], set()
                        with patch.object(mind, "remember", return_value=None):
                            for step in range(1, 8 * 120 + 1):
                                self.clock.now = start + step * 30
                                thought = mind.tick()
                                if thought:
                                    heard.append(thought["text"])
                                    times.append(self.clock())
                                    topics.add(thought["topic"])
                        self.assertGreaterEqual(len(heard), 35 if frequency == "occasional" else 18)
                        self.assertEqual(len(heard), len(set(heard)))
                        self.assertTrue(all(right - left >= watcher_mind.FREQUENCIES[frequency]["mutter"]
                                            for left, right in zip(times, times[1:])))
                        self.assertGreater(times[-1], start + 7 * 3600, "company continues late into the port watch")
                        self.assertTrue(set(aster_dockside.TOPICS) <= topics)
                        contextual = {"station": "idle_docked", "carrier": "idle_carrier", "concourse": "idle_station_foot"}[location]
                        self.assertIn(contextual, topics)

    def test_four_hours_on_chatty_have_fresh_dockside_lines_in_both_modes(self):
        for humour in ("dry", "off"):
            with self.subTest(humour=humour):
                self.clock = Clock()
                mind = self.mind("chatty", humour)
                start = self.clock()
                heard = []
                with patch.object(mind, "remember", return_value=None):
                    for minute in range(1, 241):
                        self.clock.now = start + minute * 60
                        thought = mind.tick()
                        if thought:
                            heard.append(thought["text"])
                self.assertGreaterEqual(len(heard), 35)
                self.assertEqual(len(heard), len(set(heard)))

    def test_older_exhausted_remarks_do_not_leave_the_new_port_watch_muted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path=path)
            for topic in ("quiet", "idle_docked"):
                for line in aster_lines.EVENTS[topic]:
                    mind._utter(topic, f"aster:{topic}:{_fingerprint(line)}", line.format(station="Galileo"), self.clock())
            mind.save()
            self.clock.now += 1801
            resumed = self.mind(path=path)
            self.clock.now += 301
            with patch.object(resumed, "remember", return_value=None):
                thought = resumed.tick()
            self.assertIsNotNone(thought)
            self.assertIn(thought["topic"], aster_dockside.TOPICS)
            self.assertNotIn(thought["text"], [row[2] for row in mind.memory["log"]])

    def test_rare_eligibility_keeps_minor_wording_exhaustion_and_topic_rest(self):
        mind = self.mind("rare")
        self.clock.now += 901
        topic = aster_dockside.TOPICS[0]
        with patch.object(mind.random, "random", return_value=0.):
            self.assertIsNotNone(mind.consider(topic, {"station": "Galileo"}))
            self.clock.now += 1201
            self.assertIsNone(mind.consider(topic, {"station": "Galileo"}), "half-hour topic rest remains")
            self.clock.now += 600
            self.assertIsNotNone(mind.consider(topic, {"station": "Galileo"}))
        remaining = len(aster_lines.EVENTS[topic]) - 2
        for _ in range(remaining):
            self.assertIsNotNone(mind.consider(topic, {"station": "Galileo"}, force=True))
        self.assertIsNone(mind.consider(topic, {"station": "Galileo"}, force=True), "eligibility is not permission to repeat")

    def test_no_dockside_conversation_after_undocking_or_with_thoughts_off_or_danger(self):
        mind = self.mind()
        mind.observe("Undocked", {})
        self.assertFalse(any(topic in aster_dockside.TOPICS for topic, _ in mind._idle_choices(self.clock(), {})))
        for topic in aster_dockside.TOPICS:
            self.assertIsNone(mind.consider(topic, {"station": "Galileo"}, force=True))
        off = self.mind("off")
        self.clock.now += 3600
        self.assertIsNone(off.tick())
        for topic in aster_dockside.TOPICS:
            self.assertIsNone(off.consider(topic, {"station": "Galileo"}, force=True))
        dangerous = self.mind()
        dangerous._in_danger = True
        self.assertIsNone(dangerous.consider(aster_dockside.TOPICS[0], {"station": "Galileo"}, force=True))
        self.assertIsNotNone(dangerous.consider("hull_critical", {"hull": 8}, force=True))

    def test_dockside_chatter_respects_voice_selection_instead_of_becoming_a_warning(self):
        mind = self.mind("rare")
        thought = mind.consider(aster_dockside.TOPICS[0], {"station": "Galileo"}, force=True)
        self.assertEqual(thought["importance"], 1)
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud.config, hud.mind = mind.config.source, mind
        mind.voice_active = True
        hud.voice_listener = lambda *args, **kwargs: True
        for level, expected in (("important", False), ("sometimes", True), ("every", True)):
            hud.config["aster_voice_level"] = level
            self.assertEqual(hud._speaks(thought), expected)
