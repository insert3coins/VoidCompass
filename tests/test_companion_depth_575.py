"""Every officer's topic has real depth (5.7.5): combat, travel, docking,
trade, expeditions and the quiet hours, after the ground and exploration."""
import re
import unittest

from voidcompass.overlays import aster_more, axiom_more, companion_personas, meridian_more, watcher_mind
from tests.test_companion_field_575 import SEALED

# The Watcher's own mechanics (being poked, its moods, its story's lens), the
# officers' own systems (greetings, names, keepsakes, story) and the habit
# summaries, whose templates take many fields at once.
NOT_OFFICER = ("lore", "echo", "idle_crew", "handover", "watchers_meet", "name_", "hatchling", "capsule", "constellation",
               "on_this_day", "anniversary", "dream", "companion_wish", "voice", "greet", "sign_off", "aster_", "talk",
               "relay", "callback", "habit", "poked", "mood_", "idle_four", "afterthought", "idle_lore", "idle_after",
               "idle_lens", "idle_moment", "idle_recall")


class DepthTests(unittest.TestCase):
    def test_every_officer_topic_has_depth_in_both_styles(self):
        topics = [topic for topic in watcher_mind.TOPICS if not topic.startswith(NOT_OFFICER)]
        self.assertGreater(len(topics), 130)
        for identity in ("aster", "axiom", "meridian"):
            lines = companion_personas.get(identity).lines
            for topic in topics:
                with self.subTest(identity=identity, topic=topic):
                    self.assertGreaterEqual(len(lines.event_lines(topic)), 9)
                    self.assertGreaterEqual(len(lines.event_lines(topic, True)), 4)

    def test_new_lines_use_only_fields_the_topic_provides(self):
        for module in (aster_more, axiom_more, meridian_more):
            for bank in (module.PLAIN, module.VOICED):
                for topic, lines in bank.items():
                    known = set(re.findall(r"\{(\w+)", " ".join(watcher_mind.TOPICS[topic][1]))) | {"cmdr"}
                    for line in lines:
                        with self.subTest(module=module.__name__, topic=topic, line=line):
                            self.assertLessEqual(set(re.findall(r"\{(\w+)", line)), known)
                            self.assertFalse(any(name in line for name in SEALED))

    def test_distances_say_their_units_and_home_is_home(self):
        """{dist} is a bare number ("22,000"), so every line says light years;
        idle_far measures from your home system, which isn't always Sol."""
        for identity in ("aster", "axiom", "meridian"):
            lines = companion_personas.get(identity).lines
            for topic in ("jump_long", "record_far", "record_jump", "idle_far", "idle_home", "idle_home_away"):
                for line in lines.event_lines(topic):
                    with self.subTest(identity=identity, topic=topic, line=line):
                        if "{dist}" in line:
                            self.assertRegex(line, r"\{dist\}( light years|-light-year)")
                        if topic == "idle_far":
                            self.assertNotIn("Sol", line)


if __name__ == "__main__":
    unittest.main()
