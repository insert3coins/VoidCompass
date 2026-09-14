import unittest

from voidcompass.exploration import bio_requirements
from voidcompass.exploration import bio_values


class BioRequirementsTests(unittest.TestCase):
    def test_vendored_catalogue_is_intact(self):
        catalog = bio_requirements.CATALOG
        self.assertEqual(len(catalog), 20)
        species = sum(len(entry) for entry in catalog.values())
        self.assertEqual(species, 116)
        rulesets = sum(
            len(row.get("rulesets") or ())
            for entry in catalog.values() for row in entry.values()
        )
        self.assertEqual(rulesets, 254)
        # Keys must stay in the raw journal form so they join to ScanOrganic.
        for genus_key in catalog:
            self.assertTrue(genus_key.startswith("$Codex_Ent_"))
            self.assertTrue(genus_key.endswith(";"))

    def test_every_genus_resolves_to_a_real_family(self):
        """Species names are colour-first for non-flora, so keys are the source."""
        families = set(bio_requirements.GENUS_FAMILIES.values())
        self.assertIn("Anemone", families)
        self.assertIn("Brain Tree", families)
        self.assertIn("Sinuous Tubers", families)
        self.assertIn("Crystalline Shards", families)
        # Colour words must never be mistaken for a family.
        for colour in ("Roseum", "Luteolum", "Prasinum", "Ostrinum", "Crystalline"):
            self.assertNotIn(colour, families)
        # Both Stratum keys collapse onto one family.
        self.assertEqual(
            [key for key, value in bio_requirements.GENUS_FAMILIES.items() if value == "Stratum"],
            ["$Codex_Ent_Stratum_04_Name;", "$Codex_Ent_Stratum_Genus_Name;"],
        )

    def test_known_body_matches_expected_species(self):
        found = bio_requirements.candidate_species(
            "Rocky body", "CarbonDioxide", 200.0, 0.3, None, 0.05,
        )
        names = [row["name"] for row in found]
        self.assertIn("Bacterium Aurasus", names)
        aurasus = next(row for row in found if row["name"] == "Bacterium Aurasus")
        self.assertTrue(aurasus["confirmed"])
        self.assertEqual(aurasus["unchecked"], [])

    def test_prose_and_raw_atmosphere_agree(self):
        raw = bio_requirements.candidate_species(
            "Rocky body", "CarbonDioxide", 200.0, 0.3, None, 0.05,
        )
        prose = bio_requirements.candidate_species(
            "Rocky body", "thin carbon dioxide atmosphere", 200.0, 0.3, None, 0.05,
        )
        self.assertEqual([row["name"] for row in raw], [row["name"] for row in prose])

    def test_airless_bodies_are_no_longer_refused(self):
        """The old rules returned nothing unless the atmosphere was thin."""
        self.assertEqual(
            bio_values._predict_genera_legacy("Icy body", "None", 60.0, 0.04, None), [],
        )
        predicted = bio_values.predict_genera("Icy body", "None", 60.0, 0.04, None, None)
        self.assertTrue(predicted)
        self.assertIn("Crystalline Shards", [row["name"] for row in predicted])

    def test_unverifiable_constraints_are_reported_not_assumed(self):
        found = bio_requirements.candidate_species(
            "Icy body", "None", 60.0, 0.04, None, None,
        )
        shards = next(row for row in found if row["name"] == "Crystalline Shards")
        self.assertFalse(shards["confirmed"])
        # Region, star and parent-body context cannot be judged from a body scan.
        self.assertTrue(set(shards["unchecked"]) & {"regions", "star", "bodies", "distance"})

    def test_minimum_gravity_is_enforced(self):
        """The legacy rules modelled no lower gravity bound at all."""
        low = bio_requirements.candidate_species(
            "Rocky body", "CarbonDioxide", 200.0, 0.001, None, 0.05,
        )
        self.assertNotIn("Bacterium Aurasus", [row["name"] for row in low])

    def test_prediction_keeps_the_shape_consumers_expect(self):
        for row in bio_values.predict_genera(
            "Rocky body", "CarbonDioxide", 200.0, 0.3, None, 0.05,
        ):
            self.assertIn("name", row)
            self.assertIn("min_value", row)
            self.assertIn("max_value", row)
            self.assertIn("colony_m", row)

    def test_incomplete_scan_falls_back_but_a_negative_result_does_not(self):
        # Too little to judge -> legacy rules still get a chance.
        self.assertEqual(
            bio_values.predict_genera(None, "thin carbon dioxide atmosphere", None, None, None),
            bio_values._predict_genera_legacy(
                None, "thin carbon dioxide atmosphere", None, None, None,
            ),
        )
        # Judged and rejected -> the coarser rules must not overrule the data.
        self.assertEqual(
            bio_values.predict_genera("Icy body", "Ammonia", 25.0, 0.5, None, None), [],
        )
        self.assertTrue(
            bio_values._predict_genera_legacy("Icy body", "thin ammonia", 25.0, 0.5, None),
        )


class SurveyOverlayPredictionTests(unittest.TestCase):
    """The overlay must show species detail without overstating confidence."""

    def _body(self):
        return {
            "name": "Test 1 a", "bio_count": 2, "organic_scans": {}, "genuses": [],
            "planet_class": "Rocky body", "body_id": 1,
            "predicted_genuses": bio_values.predict_genera(
                "Rocky body", "CarbonDioxide", 200.0, 0.3, None, 0.05,
            ),
        }

    def test_value_estimate_uses_fitting_species_not_whole_genus(self):
        from voidcompass.overlays import survey_status_hud as hud
        item = self._body()
        low, high = hud._body_value_range(item)
        # Every candidate here is a low-value species; the genus range for
        # Bacterium alone reaches far higher, and must not be used.
        genus_high = max(
            bio_values.genus_info(row["name"])["max_value"]
            for row in item["predicted_genuses"]
            if bio_values.genus_info(row["name"]).get("max_value")
        )
        self.assertLess(high, item["bio_count"] * genus_high)
        self.assertGreater(high, low - 1)

    def test_rows_separate_checked_predictions_from_possible_ones(self):
        from voidcompass.overlays import survey_status_hud as hud
        rows = hud._body_detail_rows(self._body())
        kinds = {row["kind"] for row in rows}
        self.assertIn("predicted", kinds)
        self.assertIn("possible", kinds)
        for row in rows:
            if row["kind"] == "predicted":
                self.assertEqual(row["status"], "PREDICTED")
            elif row["kind"] == "possible":
                self.assertEqual(row["status"], "POSSIBLE")

    def test_species_epithet_reaches_the_row_label(self):
        from voidcompass.overlays import survey_status_hud as hud
        rows = hud._body_detail_rows(self._body())
        labels = [row["display_name"] for row in rows]
        self.assertIn("Bacterium Aurasus", labels)

    def test_system_mode_still_hides_every_prediction(self):
        """Predictions must never be mistaken for DSS results."""
        from voidcompass.overlays import survey_status_hud as hud
        model = hud.build_survey_model("Testia", [self._body()])
        self.assertEqual(model["mode"], "system")
        for row in model["rows"]:
            for detail in row.get("bio_details") or []:
                self.assertNotIn(detail.get("kind"), hud.PREDICTED_KINDS)

    def test_focused_body_view_does_show_predictions(self):
        from voidcompass.overlays import survey_status_hud as hud
        model = hud.build_survey_model("Testia", [self._body()], focused_body_id=1)
        kinds = {row.get("kind") for row in model["rows"]}
        self.assertTrue(kinds & hud.PREDICTED_KINDS)


class RegionConstraintTests(unittest.TestCase):
    """Position decides the region, Guardian and Tuber requirements."""

    def test_region_map_uses_our_codex_identifiers(self):
        from voidcompass.exploration.galactic_regions import region_names
        names = region_names()
        referenced = {rid for ids in bio_requirements.REGION_MAP.values() for rid in ids}
        self.assertEqual(min(referenced), 1)
        self.assertLessEqual(max(referenced), len(names))
        # Spot-check that an id means what our own region lookup says.
        self.assertEqual(bio_requirements.REGION_MAP["empyrean-straits"], [2])
        self.assertEqual(names[1], "Empyrean Straits")

    def test_negated_group_excludes_and_plain_group_requires(self):
        allow = bio_requirements._regions_allow
        inside = bio_requirements.REGION_MAP["perseus"][0]
        self.assertFalse(allow(["!perseus"], inside))
        self.assertTrue(allow(["perseus"], inside))
        outside = next(
            rid for rid in range(1, 43)
            if rid not in bio_requirements.REGION_MAP["perseus"]
        )
        self.assertTrue(allow(["!perseus"], outside))
        self.assertFalse(allow(["perseus"], outside))

    def test_only_negations_means_anywhere_else_is_allowed(self):
        allow = bio_requirements._regions_allow
        outside = next(
            rid for rid in range(1, 43)
            if rid not in bio_requirements.REGION_MAP["perseus"]
        )
        self.assertTrue(allow(["!perseus"], outside))

    def test_unknown_position_is_undecided_not_assumed(self):
        self.assertIsNone(bio_requirements._regions_allow(["perseus"], None))
        self.assertIsNone(bio_requirements._guardian_allows(True, None))
        self.assertIsNone(bio_requirements._tuber_allows("Any", None))

    def test_guardian_and_tuber_zones_resolve_from_coordinates(self):
        # Sitting on a Guardian nebula must satisfy the requirement.
        _radius, position = next(iter(bio_requirements.GUARDIAN_NEBULAE.values()))
        self.assertTrue(bio_requirements._guardian_allows(True, position))
        self.assertFalse(bio_requirements._guardian_allows(True, (0.0, 0.0, 0.0)))
        # A tuber zone needs a distance band, so its own centre is too close.
        zone, (bounds, centre) = next(iter(bio_requirements.TUBER_ZONES.items()))
        self.assertFalse(bio_requirements._tuber_allows([zone], centre))
        edge = (centre[0] + (bounds[0] + bounds[1]) / 2.0, centre[1], centre[2])
        self.assertTrue(bio_requirements._tuber_allows([zone], edge))

    def test_position_rules_out_candidates_and_removes_uncertainty(self):
        body = ("Rocky body", "CarbonDioxide", 200.0, 0.3, None, 0.05)
        blind = bio_requirements.candidate_species(*body)
        located = bio_requirements.candidate_species(*body, region_id=18, coords=(0.0, 0.0, 0.0))
        self.assertLessEqual(len(located), len(blind))
        for row in located:
            self.assertNotIn("regions", row["unchecked"])
            self.assertNotIn("guardian", row["unchecked"])
            self.assertNotIn("tuber", row["unchecked"])

    def test_singular_region_key_is_honoured_unlike_upstream(self):
        """Brain Trees use 'region'; upstream has no branch for it and ignores it.

        The value names a real group and has the same shape as 'regions', so it
        is enforced here. Without this, Brain Trees are offered galaxy-wide.
        """
        named = {
            species.get("name")
            for genus in bio_requirements.CATALOG.values()
            for species in genus.values()
            for rule in (species.get("rulesets") or ())
            if "region" in rule
        }
        self.assertTrue(any("Brain Tree" in name for name in named))
        self.assertIn("region", bio_requirements._LOCATION_CONSTRAINTS)

        # Inside the brain-tree regions and a Guardian zone they are offered.
        from voidcompass.exploration.galactic_regions import find_region
        _radius, guardian = next(iter(bio_requirements.GUARDIAN_NEBULAE.values()))
        region = find_region(*guardian)
        self.assertIsNotNone(region)
        self.assertIn(region[0], bio_requirements.REGION_MAP["brain-tree"])
        body = ("Rocky body", "CarbonDioxide", 350.0, 0.3, "water geysers volcanism", 0.05)

        def trees(region_id, coords):
            return [
                row for row in bio_requirements.candidate_species(
                    *body, region_id=region_id, coords=coords,
                )
                if "Brain Tree" in (row["name"] or "")
            ]

        self.assertTrue(trees(region[0], guardian))
        # Outside those regions they must not be offered at all.
        elsewhere = next(
            rid for rid in range(1, 43)
            if rid not in bio_requirements.REGION_MAP["brain-tree"]
        )
        self.assertEqual(trees(elsewhere, guardian), [])
        # Unknown position keeps them possible but never confirmed.
        self.assertTrue(all(not row["confirmed"] for row in trees(None, None)))


class GenusRangeConsistencyTests(unittest.TestCase):
    def test_genus_range_matches_the_species_listed_under_it(self):
        """A genus must not advertise a range wider than its fitting species."""
        predicted = bio_values.predict_genera(
            "Rocky body", "CarbonDioxide", 350.0, 0.3,
            "minor water geysers volcanism", 0.05, 10, (-840.65625, -561.15625, 13361.8125),
        )
        self.assertTrue(predicted)
        for row in predicted:
            values = [entry["value"] for entry in row["species"] if entry.get("value")]
            if not values:
                continue
            self.assertEqual(row["min_value"], min(values), row["name"])
            self.assertEqual(row["max_value"], max(values), row["name"])

    def test_narrowing_actually_beats_the_whole_genus_range(self):
        predicted = bio_values.predict_genera(
            "Rocky body", "CarbonDioxide", 350.0, 0.3,
            "minor water geysers volcanism", 0.05, 10, (-840.65625, -561.15625, 13361.8125),
        )
        stratum = next((row for row in predicted if row["name"] == "Stratum"), None)
        self.assertIsNotNone(stratum)
        whole_genus = bio_values.GENUS_VALUE_RANGE["Stratum"]
        self.assertLess(stratum["max_value"], whole_genus[1])


if __name__ == "__main__":
    unittest.main()
