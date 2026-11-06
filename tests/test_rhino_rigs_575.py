"""The companions know the Rhino and its rigs (5.7.5): refining in the Rhino is
the rigs' yield, and the rig hotkeys tell the companion what the journal
can't (placed, ready, collected, too far, lost, left behind)."""
import random
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from voidcompass.core import companions
from voidcompass.overlays import companion_personas, rhino_lines, rig_tracker, watcher_mind
from tests.test_aster_companion import Clock
from tests.test_rhino_map_5517 import Deck as RigDeck, degrees

CREW = ("watcher", "aster", "axiom", "meridian", "lyra")


def mind(identity, frequency="chatty"):
    config = {"companion_identity": identity, f"{identity}_thoughts": frequency, "heartbeat_thoughts": frequency}
    companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(5))
    companion.memory["hours"] = 20
    companion.session_start()
    companion.random.random = lambda: 0.0
    return companion


class RefiningTests(unittest.TestCase):
    def test_refining_in_the_rhino_is_the_rigs_yield_for_every_companion(self):
        for identity in CREW:
            companion = mind(identity)
            companion.observe("LaunchSRV", {"event": "LaunchSRV", "SRVType": "rhino", "SRVType_Localised": "Rhino"})
            companion.clock.now += 120
            thought = companion.observe("MiningRefined", {"event": "MiningRefined", "Type": "platinum", "Type_Localised": "Platinum"})
            self.assertEqual((thought or {}).get("topic"), "mined_surface", identity)
            self.assertIn("Platinum", thought["text"])

    def test_the_officers_no_longer_talk_as_if_they_picked_it_up(self):
        for identity in ("aster", "axiom", "meridian", "lyra"):
            lines = companion_personas.get(identity).lines
            plain, full = rhino_lines.officer_refining(identity)
            self.assertEqual(lines.event_lines("mined_surface"), full)
            self.assertEqual(lines.event_lines("mined_surface", True), plain)
            for line in full:
                self.assertNotRegex(line.casefold(), r"gathered|materials store|picked|suit|pocket", line)


class RigNoteTests(unittest.TestCase):
    def test_every_companion_speaks_to_each_rig_moment(self):
        fields = {"slot": "2", "left": "3", "km": "3.6", "body": "Synuefe 4 a", "percent": "50", "pulses": "6"}
        for identity in CREW:
            for kind in rhino_lines.IMPORTANCE:
                with self.subTest(identity=identity, kind=kind):
                    companion = mind(identity)
                    companion.clock.now += 400
                    thought = companion.note(kind, fields)
                    self.assertEqual((thought or {}).get("topic"), kind)
                    self.assertNotIn("{", thought["text"])

    def test_warnings_matter_more_than_routine(self):
        for kind in ("rig_far", "rig_lost", "rigs_left_behind", "rig_all_collected"):
            self.assertEqual(watcher_mind.IMPORTANCE[kind], 2, kind)
        for kind in ("rig_placed", "rig_ready", "rig_collected"):
            self.assertEqual(watcher_mind.IMPORTANCE[kind], 1, kind)

    def test_every_companion_has_depth_for_rigs(self):
        for topic in rhino_lines.IMPORTANCE:
            self.assertGreaterEqual(len(watcher_mind.TOPICS[topic][1]), 10)
            self.assertGreaterEqual(len(watcher_mind.WEARY[topic]), 10)
            for identity in ("aster", "axiom", "meridian", "lyra"):
                lines = companion_personas.get(identity).lines
                self.assertGreaterEqual(len(lines.event_lines(topic)), 9, (identity, topic))
                self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4, (identity, topic))


class Deck(RigDeck):
    def __init__(self, folder):
        super().__init__(folder)
        self.notes = []
        self.heartbeat_hud = SimpleNamespace(note=lambda kind, fields: self.notes.append((kind, fields)))


class RigTrackerTests(unittest.TestCase):
    def deck(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Deck(folder.name)

    def test_placing_and_collecting_tell_the_companion(self):
        deck = self.deck()
        deck._rig_mark(1)
        deck.current_latitude = degrees(100)
        deck._rig_mark(2)
        deck._rig_mark(2)
        deck.current_latitude = 0.0
        deck._rig_mark(1)
        self.assertEqual(deck.notes, [("rig_placed", {"slot": "1"}), ("rig_placed", {"slot": "2"}),
                                      ("rig_collected", {"slot": "2", "left": "1"}), ("rig_all_collected", {})])

    def test_a_rig_is_ready_once_after_its_two_minutes(self):
        deck = self.deck()
        deck._rig_mark(3)
        deck._rig_range_watch()
        self.assertNotIn("rig_ready", [kind for kind, _fields in deck.notes], "not yet two minutes")
        with mock.patch.object(rig_tracker, "READY_S", 0):
            deck._rig_range_watch()
            deck._rig_range_watch()
        self.assertEqual([fields for kind, fields in deck.notes if kind == "rig_ready"], [{"slot": "3"}], "once")

    def test_too_far_lost_and_left_behind_tell_the_companion(self):
        deck = self.deck()
        deck._rig_mark(1)
        deck.current_latitude = degrees(3800)
        deck._rig_range_watch()
        far = [fields for kind, fields in deck.notes if kind == "rig_far"]
        self.assertEqual(far, [{"slot": "1", "km": "3.8"}])
        deck.current_latitude = degrees(5100)
        deck._rig_range_watch()
        self.assertIn(("rig_lost", {"slot": "1"}), deck.notes)
        deck.current_latitude = 0.0
        deck._rig_mark(4)
        deck._rig_left_body(deck.current_body_name)
        self.assertEqual(deck.notes[-1], ("rigs_left_behind", {"body": deck.current_body_name}))


if __name__ == "__main__":
    unittest.main()
