"""Each companion's role (5.7.4): Axiom cares about the survey, Meridian about
the voyage, Aster keeps the log. They rate those topics higher and have enough
lines for them that a long exploring trip doesn't go quiet or wear thin."""
import random
import unittest

from voidcompass.core import companions
from voidcompass.overlays import companion_personas, watcher_mind
from tests.test_aster_companion import Clock


def mind(identity, frequency="occasional"):
    config = {"companion_identity": identity, f"{identity}_thoughts": frequency, "heartbeat_thoughts": frequency}
    companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(4))
    companion.memory["hours"] = 20
    companion.session_start()
    return companion


class InterestTests(unittest.TestCase):
    def test_each_role_rates_its_own_topics_higher(self):
        axiom, meridian, aster = (companion_personas.get(name).interests for name in ("axiom", "meridian", "aster"))
        for topic in ("fss_complete", "mapped", "undiscovered_system", "codex_logged"):
            self.assertGreaterEqual(axiom[topic], 2, topic)
        for topic in ("arrival", "jump_long", "jump_far", "idle_far"):
            self.assertGreaterEqual(meridian[topic], 2, topic)
        self.assertGreaterEqual(aster["jump_long"], 2)
        for persona in (axiom, meridian, aster):
            for topic, level in persona.items():
                self.assertGreater(level, watcher_mind.IMPORTANCE.get(topic, 1) if level > 1 else -1, topic)
        self.assertEqual(mind("meridian")._importance("arrival"), 2)
        self.assertEqual(mind("axiom")._importance("arrival"), 1)
        self.assertEqual(mind("axiom")._importance("fuel_low"), watcher_mind.IMPORTANCE["fuel_low"], "never lowered")

    def test_interest_topics_have_plenty_of_lines_in_both_styles(self):
        for identity in ("aster", "axiom", "meridian", "lyra"):
            persona = companion_personas.get(identity)
            for topic in persona.interests:
                with self.subTest(identity=identity, topic=topic):
                    self.assertGreaterEqual(len(persona.lines.event_lines(topic)), 12)
                    self.assertGreaterEqual(len(persona.lines.event_lines(topic, True)), 4)

    def test_merged_banks_add_lines_rather_than_replace_them(self):
        from voidcompass.overlays import axiom_events, axiom_survey, meridian_events, meridian_soundings
        for lines, events, extra in ((companion_personas.get("axiom").lines, axiom_events, axiom_survey),
                                     (companion_personas.get("meridian").lines, meridian_events, meridian_soundings)):
            for topic in extra.PLAIN:
                bank = lines.event_lines(topic)
                for line in events.PLAIN.get(topic, ()) + events.VOICED.get(topic, ()) + extra.PLAIN[topic] + extra.VOICED.get(topic, ()):
                    self.assertIn(line, bank, topic)

    def test_occasional_still_marks_arrivals_for_the_navigator(self):
        heard = []
        for identity in ("meridian", "watcher"):
            companion = mind(identity)
            said = 0
            for jump in range(30):
                companion.clock.now += 700
                thought = companion.observe("FSDJump", {"event": "FSDJump", "StarSystem": f"Sim {jump}", "SystemAddress": jump,
                                                         "JumpDist": 20.0, "StarPos": [0, 0, 0]})
                said += bool(thought and thought["topic"] == "arrival")
            heard.append(said)
        self.assertGreaterEqual(heard[0], 10, "Meridian notes many arrivals ten minutes apart")
        self.assertEqual(heard[1], 0, "the Watcher's own pacing is unchanged")


if __name__ == "__main__":
    unittest.main()
