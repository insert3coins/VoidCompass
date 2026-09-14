import unittest

from voidcompass.engineering.engineering_data import (
    BLUEPRINTS,
    BLUEPRINT_ENGINEER_GRADES,
    BLUEPRINT_INFO,
    ENGINEERS,
    engineer_blueprint_grade,
    engineer_blueprints,
)


class EngineeringReferenceDataTests(unittest.TestCase):
    def test_every_planner_blueprint_has_valid_grade_aware_engineers(self):
        self.assertEqual(set(BLUEPRINTS), set(BLUEPRINT_ENGINEER_GRADES))
        for blueprint, engineers in BLUEPRINT_ENGINEER_GRADES.items():
            self.assertTrue(engineers, blueprint)
            for engineer, grade in engineers.items():
                self.assertIn(engineer, ENGINEERS, (blueprint, engineer))
                self.assertIn(grade, range(1, 6), (blueprint, engineer, grade))

    def test_reference_grade_caps_replace_flat_manual_guesses(self):
        self.assertEqual(engineer_blueprint_grade("Felicity Farseer", "FSD Increased Range"), 5)
        self.assertEqual(engineer_blueprint_grade("Colonel Bris Dekker", "FSD Increased Range"), 3)
        self.assertEqual(engineer_blueprint_grade("Felicity Farseer", "Thrusters Dirty Tuning"), 3)
        self.assertEqual(engineer_blueprint_grade("Mel Brandon", "Thrusters Dirty Tuning"), 5)
        self.assertEqual(engineer_blueprint_grade("Zacariah Nemo", "Thrusters Dirty Tuning"), 0)
        self.assertEqual(
            engineer_blueprint_grade("Tiana Fortune", "Surface Scanner Expanded Probe Radius"),
            3,
        )

    def test_public_blueprint_engineer_lists_follow_grade_snapshot(self):
        for blueprint, engineers in BLUEPRINT_ENGINEER_GRADES.items():
            self.assertEqual(set(BLUEPRINT_INFO[blueprint]["engineers"]), set(engineers))

    def test_every_engineer_has_a_structured_access_path(self):
        self.assertTrue(all(info.get("unlock_steps") for info in ENGINEERS.values()))
        self.assertIn("Meta-Alloys", ENGINEERS["Felicity Farseer"]["unlock"])
        self.assertIn("five different black markets", " ".join(ENGINEERS["The Dweller"]["unlock_steps"]))
        self.assertIn("Opinion Polls", " ".join(ENGINEERS["Kit Fowler"]["unlock_steps"]))

    def test_engineer_grouping_only_returns_supported_blueprints(self):
        for engineer in ENGINEERS:
            for blueprints in engineer_blueprints(engineer).values():
                for blueprint in blueprints:
                    self.assertGreater(engineer_blueprint_grade(engineer, blueprint), 0)


if __name__ == "__main__":
    unittest.main()
