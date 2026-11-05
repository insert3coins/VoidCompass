"""Every example on the companion page's TALK panel gets a real answer (5.7.4):
"Where are we?" fell through to the general rundown."""
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from voidcompass.core import voice_commands
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import watcher_copilot, watcher_ship

ROOT = Path(__file__).resolve().parents[1]


def prompts():
    script = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
    block = re.search(r"const TALK_PROMPTS = (\[[^\]]*\]);", script).group(1)
    return json.loads(block)


class TalkPromptTests(unittest.TestCase):
    def test_every_example_is_a_command_or_a_question_with_readings(self):
        found = prompts()
        self.assertIn("Where are we?", found)
        for prompt in found:
            with self.subTest(prompt=prompt):
                ship = [item for item in voice_commands.catalogue(None) if not hasattr(item, "native")]
                answered = (voice_commands.native_request(prompt, None) or watcher_ship.request(prompt, ship)
                            or watcher_ship.power_request(prompt) or watcher_copilot.topics_for(prompt))
                self.assertTrue(answered, "neither a command nor a lookup")

    def test_where_are_we_is_the_position_and_where_are_we_going_the_route(self):
        self.assertEqual(watcher_copilot.topics_for("Where are we?"), ["where"])
        self.assertEqual(watcher_copilot.topics_for("what system is this"), ["where"])
        self.assertEqual(watcher_copilot.topics_for("Where are we going?"), ["route"])
        self.assertEqual(watcher_copilot.topics_for("where am I headed"), ["route"])

    def test_the_answer_names_the_system_and_the_station_or_body(self):
        deck = SimpleNamespace(current_sys="Hypio Pruae LH-V d2-11", current_docked=False,
                               current_station_name="Old Dock", current_body_name="Hypio Pruae LH-V d2-11 3")
        self.assertEqual(DashboardWatcherVoiceMixin._watcher_lookup_where(deck),
                         ["Current system: Hypio Pruae LH-V d2-11", "Nearest body: Hypio Pruae LH-V d2-11 3"])
        deck.current_docked = True
        self.assertEqual(DashboardWatcherVoiceMixin._watcher_lookup_where(deck)[1], "Docked at Old Dock")
        self.assertEqual(watcher_copilot.where_lines("---"), ["The ship's position isn't known yet."])


if __name__ == "__main__":
    unittest.main()
