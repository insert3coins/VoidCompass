"""5.5.3: Shock and Awe no longer counts limpets (a collector limpet raised
it), Drone Operator counts mining limpets only, and progress kept under the
old Shock and Awe trigger is cleared once."""

import json
import tempfile
import unittest
from pathlib import Path

from voidcompass.exploration.achievement_engine import AchievementEngine


def event(name, **fields):
    return {"event": name, "timestamp": "2026-10-08T12:00:00Z", **fields}


class AchievementTriggerTests(unittest.TestCase):
    def engine(self, folder, state=None):
        path = Path(folder) / "achievements_state.json"
        if state is not None:
            path.write_text(json.dumps(state), encoding="utf-8")
        return AchievementEngine(path)

    def test_limpets_do_not_count_as_seismic_charges(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = self.engine(folder)
            engine.process_event(event("LaunchDrone", Type="Collection"), notify=False)
            self.assertNotIn("seismic_charge", engine.state["counters"])
            for _ in range(3):
                engine.process_event(event("AsteroidCracked", Body="Ring A"), notify=False)
            self.assertIn("seismic_charge", engine.state["unlocked"])

    def test_drone_operator_counts_mining_limpets(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = self.engine(folder)
            engine.process_event(event("LaunchDrone", Type="Repair"), notify=False)
            self.assertNotIn("first_limpet", engine.state["unlocked"])
            engine.process_event(event("LaunchDrone", Type="Prospector"), notify=False)
            self.assertIn("first_limpet", engine.state["unlocked"])

    def test_old_shock_and_awe_progress_is_cleared_once(self):
        with tempfile.TemporaryDirectory() as folder:
            old = {"schemaVersion": 1, "unlocked": {"seismic_charge": "2026-10-01T00:00:00Z", "first_limpet": "x"},
                   "counters": {"seismic_charge": 7}}
            engine = self.engine(folder, old)
            self.assertNotIn("seismic_charge", engine.state["unlocked"])
            self.assertNotIn("seismic_charge", engine.state["counters"])
            self.assertIn("first_limpet", engine.state["unlocked"], "other achievements are untouched")
            engine.process_event(event("AsteroidCracked", Body="Ring A"), notify=False)
            engine.save(force=True)
            engine.flush(wait=True)
            again = self.engine(folder)
            self.assertEqual(again.state["counters"].get("seismic_charge"), 1, "cleared once, not on every start")


if __name__ == "__main__":
    unittest.main()
