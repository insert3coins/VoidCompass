"""Docking, start to finish (5.7.6): the station's answer to your request is
always said, even straight after your own "request docking" command, on Rare,
and on the third docking in twenty minutes; the request, cancelling and timing
out have their own words."""
import random
import unittest

from voidcompass.core import companions
from voidcompass.overlays import docking_talk, ship_life, watcher_mind
from tests.test_aster_companion import Clock

CREW = ("watcher", "aster", "axiom", "meridian")


def mind(identity, frequency="chatty"):
    config = {"companion_identity": identity, f"{identity}_thoughts": frequency, "heartbeat_thoughts": frequency}
    companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(2))
    companion.memory["hours"] = 40
    companion.session_start()
    companion.clock.now += 600
    companion.action_provider = lambda words: "Aye. The docking request."
    return companion


def event(companion, name, after=1, **raw):
    companion.clock.now += after
    return companion.observe(name, {"event": name, **raw})


class MomentTests(unittest.TestCase):
    def test_every_docking_event(self):
        self.assertEqual(ship_life.moment("DockingRequested", {"StationName": "XNG-40Z", "StationType": "FleetCarrier"}),
                         ("docking_requested", {"station": "XNG-40Z"}))
        self.assertEqual(ship_life.moment("DockingCancelled", {}), ("docking_cancelled", {}), "its fields are all optional")
        self.assertEqual(ship_life.moment("DockingTimeout", {}), ("docking_timeout", {}))
        self.assertEqual(ship_life.moment("DockingGranted", {"LandingPad": 4}), ("docking_granted", {"pad": "4"}))
        self.assertEqual(ship_life.moment("DockingDenied", {"Reason": "TooLarge"})[1]["reason"], "the ship is too large for their pads")
        for topic in docking_talk.IMPORTANCE:
            self.assertEqual(watcher_mind.IMPORTANCE[topic], docking_talk.IMPORTANCE[topic])


class AnswerTests(unittest.TestCase):
    def test_the_grant_follows_your_own_command(self):
        for identity in CREW:
            companion = mind(identity)
            companion.talk("Request docking.")
            self.assertIsNone(event(companion, "DockingRequested", 4, StationName="XNG-40Z"),
                              "the command's reply already said the request")
            granted = event(companion, "DockingGranted", 1, StationName="XNG-40Z", LandingPad=4)
            self.assertEqual((granted or {}).get("topic"), "docking_granted", identity)
            self.assertGreaterEqual(granted["importance"], 2, "said aloud on 'important only' too")

    def test_every_answer_even_on_rare_and_often(self):
        for identity in CREW:
            companion = mind(identity, "rare")
            said = []
            for _ in range(4):
                event(companion, "DockingRequested", 300, StationName="Jameson Memorial")
                said.append((event(companion, "DockingGranted", 1, LandingPad=7) or {}).get("text"))
            self.assertTrue(all(said), (identity, said))
            self.assertEqual(len(set(said[:2])), 2, "a different line the next time")
            event(companion, "DockingRequested", 60, StationName="Jameson Memorial")
            self.assertEqual((event(companion, "DockingTimeout", 30) or {}).get("topic"), "docking_timeout")
            event(companion, "DockingRequested", 60, StationName="Jameson Memorial")
            self.assertEqual((event(companion, "DockingCancelled", 5) or {}).get("topic"), "docking_cancelled")
            event(companion, "DockingRequested", 60, StationName="Jameson Memorial")
            self.assertEqual((event(companion, "DockingDenied", 1, Reason="NoSpace") or {}).get("topic"), "docking_denied")

    def test_an_answer_long_after_any_request_is_ordinary(self):
        companion = mind("meridian", "rare")
        self.assertIsNone(event(companion, "DockingGranted", 1, LandingPad=2), "no request this session: Rare stays quiet")

    def test_a_request_from_the_panel_is_announced(self):
        companion = mind("aster")
        companion.random.random = lambda: 0.0
        thought = event(companion, "DockingRequested", 5, StationName="Jameson Memorial")
        self.assertEqual((thought or {}).get("topic"), "docking_requested")
        self.assertIn("Jameson Memorial", thought["text"])


class LineTests(unittest.TestCase):
    def test_depth_and_whole_lines(self):
        for topic in docking_talk.IMPORTANCE:
            self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 10)
            self.assertGreaterEqual(len(watcher_mind.WEARY[topic]), 10)
            for identity in ("aster", "axiom", "meridian"):
                from voidcompass.overlays import companion_personas
                lines = companion_personas.get(identity).lines
                self.assertGreaterEqual(len(lines.event_lines(topic)), 9, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))
                for line in lines.event_lines(topic):
                    self.assertNotIn("{", line.format(station="XNG-40Z"))


if __name__ == "__main__":
    unittest.main()
