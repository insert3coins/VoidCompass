import os
import sqlite3
import tempfile
import unittest

from voidcompass.exploration.explorer_fieldcraft import data_vault_snapshot, revisit_candidate, route_safety_forecast
from voidcompass.core.profile_backups import snapshot_profile, validate_backup


class ExplorerFieldcraft529Tests(unittest.TestCase):
    def test_route_safety_reports_dry_stretch_and_white_dwarf(self):
        route = [
            {"StarSystem": "Sol", "StarClass": "G"},
            {"StarSystem": "A", "StarClass": "T"},
            {"StarSystem": "B", "StarClass": "DA"},
            {"StarSystem": "C", "StarClass": "M"},
        ]
        result = route_safety_forecast(route, "Sol", "G", 4.0, 8.0, [1.0])
        self.assertEqual(result["next_scoop_jumps"], 3)
        self.assertEqual(result["white_dwarf_count"], 1)
        self.assertEqual(result["status"], "CAUTION")

    def test_revisit_keeps_unmapped_value_and_unfinished_biology(self):
        candidate = revisit_candidate("Test", [{
            "planet_class": "Earthlike body", "dss_complete": False,
            "bio_count": 2, "organic_complete_count": 1, "name": "Test 2",
        }], scanned=4, total=6)
        self.assertEqual(candidate["valuable_unmapped"], 1)
        self.assertEqual(candidate["biology_remaining"], 1)
        self.assertIn("FSS 4/6", candidate["detail"])

    def test_data_vault_separates_minimum_and_possible_bonus(self):
        vault = data_vault_snapshot({
            "unsold_exploration_cr": 100, "unsold_bio_cr": 200,
            "unsold_bio_bonus_potential_cr": 300, "unsold_scan_keys": ["a", "b"],
        })
        self.assertEqual(vault["minimum_total_cr"], 300)
        self.assertEqual(vault["maximum_total_cr"], 600)
        self.assertEqual(vault["systems_represented"], 2)

    def test_profile_snapshot_uses_readable_sqlite_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            source = os.path.join(temp, "profile")
            target = os.path.join(temp, "backup")
            os.makedirs(source)
            db = sqlite3.connect(os.path.join(source, "exploration_data.db"))
            db.execute("CREATE TABLE facts (value TEXT)")
            db.execute("INSERT INTO facts VALUES ('safe')")
            db.commit()
            snapshot_profile(source, target)
            db.close()
            valid, _detail = validate_backup(target)
            self.assertTrue(valid)
            restored = sqlite3.connect(os.path.join(target, "exploration_data.db"))
            try:
                self.assertEqual(restored.execute("SELECT value FROM facts").fetchone()[0], "safe")
            finally:
                restored.close()


if __name__ == "__main__":
    unittest.main()
