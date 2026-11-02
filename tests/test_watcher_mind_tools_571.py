"""The Watcher's plain life lookups use Survey's existing predictions."""

import unittest

from voidcompass.overlays import watcher_copilot, watcher_mind


class LifeTests(unittest.TestCase):
    GENERA = [{"name": "Bacterium", "min_value": 1000000, "max_value": 1000000,
               "species": [{"name": "Bacterium Aurasus", "value": 1000000}]},
              {"name": "Stratum", "min_value": 2637500, "max_value": 19010800,
               "species": [{"name": "Stratum Tectonicas", "value": 19010800}, {"name": "Stratum Paleas", "value": 1362000}]}]

    def test_what_could_live_there(self):
        self.assertEqual(watcher_copilot.topics_for("What could live on 3 a?"), ["life"])
        self.assertIn("life", watcher_copilot.topics_for("any bacteria here?"))
        lines = watcher_copilot.life_lines([{"name": "Hypio 3 a", "signals": 3, "known": ["Bacterium"],
                                             "genera": self.GENERA, "colours": {"stratum tectonicas": "Emerald"}}])
        self.assertEqual(lines[0], "Hypio 3 a: 3 biological signals, found so far: Bacterium")
        self.assertEqual(lines[1], "Could grow on Hypio 3 a: Stratum (2,637,500 to 19,010,800 credits), "
                                   "Bacterium (1,000,000 credits)")
        self.assertEqual(lines[2], "On Hypio 3 a, Stratum Tectonicas would fetch 19,010,800 credits, in Emerald")
        self.assertEqual(watcher_copilot.life_lines([]), ["No world scanned here has any sign of life yet."])
        self.assertIn("Nothing in the species data fits", watcher_copilot.life_lines([{"name": "X", "genera": []}])[1])

    def test_the_world_you_name_or_where_you_are(self):
        from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin

        deck = DashboardWatcherVoiceMixin.__new__(type("Deck", (DashboardWatcherVoiceMixin,), {}))
        deck.scan_items = [
            {"body_id": 1, "name": "3 a", "full_name": "Hypio 3 a", "bio_count": 3, "genuses": ["Bacterium"],
             "predicted_genuses": self.GENERA},
            {"body_id": 2, "name": "5", "full_name": "Hypio 5", "bio_count": 0, "predicted_genuses": self.GENERA[:1]},
            {"body_id": 3, "name": "A", "full_name": "Hypio A", "is_star": True}]
        deck._survey_codex_variants = lambda body_id: {"stratum tectonicas": [{"colour": "Emerald"}]} if body_id == 1 else {}
        self.assertTrue(deck._watcher_lookup_life("what could live on 5?")[0].startswith("Hypio 5:"))
        deck.current_body_name = "Hypio 5"
        self.assertTrue(deck._watcher_lookup_life("what lives here?")[0].startswith("Hypio 5:"), "where you are")
        deck.current_body_name = ""
        lines = deck._watcher_lookup_life("any life in this system?")
        self.assertTrue(lines[0].startswith("Hypio 3 a: 3 biological signals"), "the worlds with signals")
        self.assertIn("in Emerald", " ".join(lines))


    def test_life_question_is_answered_from_the_lookup_without_a_model(self):
        lines = watcher_copilot.life_lines([{"name": "Hypio 3 a", "signals": 3, "genera": self.GENERA}])
        asked = []
        mind = watcher_mind.WatcherMind(None, {})
        mind.lookup_provider = lambda question: asked.append(question) or lines
        self.assertTrue(mind.talk("What could live on 3 a?"))
        self.assertEqual(asked, ["What could live on 3 a?"])
        self.assertEqual(mind.memory["talk"][-1]["it"], watcher_copilot.plain_answer(lines))
        self.assertIn("Hypio 3 a", mind.thought["text"])
        self.assertFalse(mind.talk_waiting())


if __name__ == "__main__":
    unittest.main()
