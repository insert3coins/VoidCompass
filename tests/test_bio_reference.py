import unittest

import bio_reference
import bio_values


class BioReferenceTests(unittest.TestCase):
    def test_packaged_srvsurvey_catalogue_contains_species_variants_and_rewards(self):
        data = bio_reference.catalogue()
        self.assertGreaterEqual(data["entry_count"], 800)
        arcus = bio_reference.species_info("Aleoida Arcus")
        self.assertEqual(arcus["value"], 7_252_500)
        self.assertIn("Yellow", arcus["variants"])
        self.assertIn("Emerald", arcus["variants"])

    def test_catalogue_exposes_genus_reward_range(self):
        bacterium = bio_reference.genus_info("Bacterium")
        self.assertEqual(bacterium["min_value"], 1_000_000)
        self.assertEqual(bacterium["max_value"], 8_418_000)
        self.assertGreaterEqual(len(bacterium["species"]), 10)

    def test_catalogue_reward_takes_priority_over_legacy_fallback_table(self):
        self.assertEqual(bio_values.species_value("Bacterium Nebulus"), 5_289_900)


if __name__ == "__main__":
    unittest.main()
