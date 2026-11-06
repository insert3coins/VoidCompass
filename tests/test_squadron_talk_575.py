"""Your squadron, beyond its name (5.7.5): your rank in it, its moments, and
TALK answering what squadron you're in."""
import random
import re
import unittest
from types import SimpleNamespace

from voidcompass.core import companions
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import companion_personas, squadron_talk, watcher_copilot, watcher_mind, watcher_name
from tests.test_aster_companion import Clock

CREW = ("watcher", "aster", "axiom", "meridian")
EVENTS = (("AppliedToSquadron", {"SquadronName": "NEON HORIZON"}, "squadron_applied"),
          ("InvitedToSquadron", {"SquadronName": "NEON HORIZON"}, "squadron_invited"),
          ("JoinedSquadron", {"SquadronName": "NEON HORIZON"}, "squadron_joined"),
          ("LeftSquadron", {"SquadronName": "GLOW RUNNERS"}, "squadron_left"),
          ("KickedFromSquadron", {"SquadronName": "GLOW RUNNERS"}, "squadron_kicked"),
          ("SquadronPromotion", {"SquadronName": "EAST ORION COMPANY", "OldRankName": "Cadet", "NewRankName": "agincourt helmsman"},
           "squadron_promoted"),
          ("SquadronDemotion", {"SquadronName": "EAST ORION COMPANY", "NewRankName": "Cadet"}, "squadron_demoted"),
          ("SquadronCreated", {"SquadronName": "VOID WALKERS"}, "squadron_created"),
          ("DisbandedSquadron", {"SquadronName": "VOID WALKERS"}, "squadron_disbanded"),
          ("WonATrophyForSquadron", {"SquadronName": "EAST ORION COMPANY"}, "squadron_trophy"),
          ("SharedBookmarkToSquadron", {"SquadronName": "EAST ORION COMPANY"}, "squadron_bookmark"))


class FieldTests(unittest.TestCase):
    def test_names_read_normally_and_the_rank_comes_along(self):
        self.assertEqual(squadron_talk.readable("EAST ORION COMPANY"), "East Orion Company")
        self.assertEqual(squadron_talk.readable("agincourt helmsman"), "Agincourt Helmsman")
        self.assertEqual(squadron_talk.readable("The Dark Wheel"), "The Dark Wheel", "mixed case is left as written")
        self.assertEqual(watcher_name.fact_fields("SquadronStartup", {"SquadronName": "EAST ORION COMPANY",
                                                                      "CurrentRankName": "agincourt helmsman"}),
                         ("cmdr_squadron", {"squadron": "East Orion Company", "rank": "Agincourt Helmsman"}))
        for event, raw, topic in EVENTS:
            self.assertEqual(squadron_talk.moment(event, raw)[0], topic, event)
        self.assertIsNone(squadron_talk.moment("SquadronStartup", {"SquadronName": "X"}), "the fact handles startup")


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
                    self.assertFalse(re.search(r"[A-Z]{4,} [A-Z]{4,}", thought["text"]), "no squadron names in capitals")

    def test_depth_and_rank_lines(self):
        for topic in squadron_talk.IMPORTANCE:
            self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 10)
            self.assertGreaterEqual(len(watcher_mind.WEARY[topic]), 10)
            for identity in ("aster", "axiom", "meridian"):
                lines = companion_personas.get(identity).lines
                self.assertGreaterEqual(len(lines.event_lines(topic)), 9, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))
        self.assertTrue(any("{rank}" in line for line in watcher_mind.TOPICS["cmdr_squadron"][1]))
        for identity in ("aster", "axiom", "meridian"):
            self.assertTrue(any("{rank}" in line for line in companion_personas.get(identity).lines.event_lines("cmdr_squadron")))


class TalkTests(unittest.TestCase):
    def test_talk_answers_what_squadron_you_are_in(self):
        self.assertEqual(watcher_copilot.topics_for("what squadron am I in?"), ["squadron"])
        self.assertEqual(watcher_copilot.topics_for("what's my squadron rank"), ["squadron"], "not the pilot ranks")
        self.assertIn("ranks", watcher_copilot.topics_for("my squadron and combat rank"))
        deck = SimpleNamespace(carrier_tracker=SimpleNamespace(_squadron_context={
            "squadron_name": "EAST ORION COMPANY", "squadron_rank_name": "agincourt helmsman"}))
        self.assertEqual(DashboardWatcherVoiceMixin._watcher_lookup_squadron(deck),
                         ["Squadron: East Orion Company, rank Agincourt Helmsman"])
        self.assertEqual(watcher_copilot.squadron_lines(None), ["The commander isn't in a squadron, as far as the journal says"])


if __name__ == "__main__":
    unittest.main()
