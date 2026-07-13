import unittest

from survey_status_hud import build_survey_model


def _body(**updates):
    row = {
        "body_id": 7,
        "name": "Test AB 1 c",
        "bio_count": 3,
        "organic_complete_count": 1,
        "dss_complete": True,
        "genuses": [{"Genus_Localised": "Bacterium"}, {"Genus_Localised": "Stratum"}],
        "organic_scans": {
            "7|Bacterium Acies": {
                "species": "Bacterium Acies",
                "genus": "Bacterium",
                "species_value": 1_000_000,
                "is_complete": True,
            }
        },
    }
    row.update(updates)
    return row


class SurveyStatusModelTests(unittest.TestCase):
    def test_focused_bio_body_uses_detailed_species_view(self):
        model = build_survey_model("Test AB", [_body()], focused_body_id=7)
        self.assertEqual(model["mode"], "body")
        self.assertEqual(model["body"]["name"], "Test AB 1 c")
        self.assertEqual(model["rows"][0]["name"], "Bacterium Acies")
        self.assertEqual(model["rows"][0]["kind"], "complete")
        self.assertTrue(any(row["name"] == "Stratum" and row["kind"] == "detected"
                            for row in model["rows"]))
        self.assertGreater(model["max_value"], model["min_value"])

    def test_system_view_prioritises_unfinished_bio_bodies_and_dss_work(self):
        dss_only = _body(body_id=8, name="Test AB 2", bio_count=0,
                         organic_complete_count=0, dss_complete=False,
                         genuses=[], organic_scans={})
        model = build_survey_model("Test AB", [_body(), dss_only])
        self.assertEqual(model["mode"], "system")
        self.assertEqual([row["name"] for row in model["rows"]], ["Test AB 1 c", "Test AB 2"])
        self.assertEqual(model["rows"][0]["bio_count"], 3)
        self.assertTrue(model["rows"][1]["needs_dss"])

    def test_completed_system_hides_strip(self):
        self.assertIsNone(build_survey_model("Test AB", [_body(organic_complete_count=3)]))


if __name__ == "__main__":
    unittest.main()
