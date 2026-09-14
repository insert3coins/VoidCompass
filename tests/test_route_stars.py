import unittest

from voidcompass.exploration import route_stars


class RouteStarTests(unittest.TestCase):
    def test_missing_star_class_is_unknown_not_non_scoopable(self):
        ahead = route_stars.route_ahead(
            [
                {"StarSystem": "Here", "StarClass": "G"},
                {"StarSystem": "Unknown Next"},
            ],
            "Here",
            "G",
        )
        self.assertTrue(ahead[0]["scoopable"])
        self.assertIsNone(ahead[1]["scoopable"])

        self.assertTrue(ahead[0]["scoopable"])
        self.assertIsNone(ahead[1]["scoopable"])

    def test_current_system_is_prefixed_when_route_has_already_advanced(self):
        ahead = route_stars.route_ahead(
            [{"StarSystem": "Next", "StarClass": "K"}],
            "Here",
            None,
        )
        self.assertEqual([row["system"] for row in ahead], ["Here", "Next"])
        self.assertIsNone(ahead[0]["scoopable"])
        self.assertTrue(ahead[1]["scoopable"])


if __name__ == "__main__":
    unittest.main()
