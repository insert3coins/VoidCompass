"""5.5.3: the exobiology first-logged bonus (4x again, 5x in all) is counted
where it is certain: on first-footfall bodies (the developer's journals: 228
of 228 such samples paid it)."""

import unittest

from voidcompass.core.companion_features import unsold_bio_value
from voidcompass.exploration import bio_values
from voidcompass.overlays.survey_status_hud import build_survey_model


def body(first_footfall):
    return {"body_id": 5, "name": "Prai 5", "planet_class": "Rocky body", "landable": True, "bio_count": 1,
            "first_footfall": first_footfall,
            "organic_scans": {"5|Bacterium Aurasus": {"species": "Bacterium Aurasus", "genus": "Bacterium",
                                                       "sample_idx": 3, "is_complete": True}}}


class BioBonusTests(unittest.TestCase):
    def test_unsold_value_counts_the_first_footfall_bonus(self):
        self.assertEqual(unsold_bio_value({"unsold_bio_cr": 1_000_000, "unsold_bio_bonus_potential_cr": 4_000_000}),
                         5_000_000)
        self.assertEqual(unsold_bio_value({}), 0)

    def test_survey_values_are_five_times_on_a_first_footfall_body(self):
        base = bio_values.species_value("Bacterium Aurasus")
        self.assertTrue(base)
        plain = build_survey_model("Prai", [body(False)], focused_body_id=5, scanned=1, total=1)
        bonus = build_survey_model("Prai", [body(True)], focused_body_id=5, scanned=1, total=1)
        self.assertEqual(plain["rows"][0]["value"], base)
        self.assertEqual(bonus["rows"][0]["value"], base * 5)
        self.assertTrue(bonus["rows"][0]["first_logged_bonus"])
        self.assertEqual((bonus["min_value"], bonus["max_value"]), (base * 5, base * 5))


if __name__ == "__main__":
    unittest.main()
