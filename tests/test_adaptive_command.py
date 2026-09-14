import os
import tempfile
import unittest

from voidcompass.core.adaptive_command import AdaptiveCommandDeck, normalize_mode


class AdaptiveCommandDeckTests(unittest.TestCase):
    def test_normalizes_existing_activity_names(self):
        self.assertEqual(normalize_mode("colonisation"), "general")
        self.assertEqual(normalize_mode("explore"), "exploration")

    def test_manual_lock_overrides_detected_activity(self):
        with tempfile.TemporaryDirectory() as folder:
            config = {"adaptive_command_enabled": True, "adaptive_mode_lock": "carrier"}
            deck = AdaptiveCommandDeck(os.path.join(folder, "adaptive.json"), config)
            result = deck.observe("MiningRefined", "mining", {"event": "MiningRefined"})
            self.assertEqual(result["mode"], "carrier")
            self.assertFalse(deck.automatic)

    def test_operational_queue_prioritises_active_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            config = {"adaptive_command_enabled": True, "adaptive_mode_lock": "exploration"}
            deck = AdaptiveCommandDeck(os.path.join(folder, "adaptive.json"), config)
            rows = deck.build_queue(
                {"objectives": {"unsold_data_total_cr": 1000}, "missions": {"active": 2}},
                {"survey_remaining": 3, "current_system": "Test", "next_destination": "Next"},
            )
            self.assertEqual(rows[0]["id"], "survey")
            self.assertTrue(any(row["id"] == "route" for row in rows))

    def test_retired_mode_lock_migrates_to_general(self):
        with tempfile.TemporaryDirectory() as folder:
            deck = AdaptiveCommandDeck(
                os.path.join(folder, "deck.json"),
                {"adaptive_mode_lock": "powerplay"},
            )
            self.assertEqual(deck.current_mode, "general")
            self.assertTrue(deck.automatic)

if __name__ == "__main__":
    unittest.main()
