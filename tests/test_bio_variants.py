"""Colour variants for Survey Operations' Codex flags (SrvSurvey's bio
criteria, read the way its BioPredictor reads them)."""

import unittest
from unittest import mock

from voidcompass.exploration import bio_variants
from voidcompass.exploration.bio_variants import Node, body_properties, flatten_star_type, predict

# A trimmed tree in the bio-criteria format: colour by star, by material,
# and one branch per body type.
ALEOIDA = {
    "genus": "Aleoida",
    "commonChildren": [
        {"variant": "Green", "query": ["    star [A]", "body [Rocky]"]},
        {"variant": "Turquoise", "query": ["star [K]"]},
    ],
    "query": ["   body [HMC,Rocky]", " gravity [ ~ 0.276]"],
    "children": [{
        "species": "Arcus",
        "query": ["# hit count: 1", "atmosType [CarbonDioxide]", "     temp [175.0 ~ 180.0]",
                  "atmosComp [CarbonDioxide >= 100 | SulphurDioxide >= 0.99]"],
        "children": [{"useCommonChildren": True, "query": ["body [Rocky]"]}],
    }],
}
FUNGOIDA = {
    "genus": "Fungoida",
    "children": [{
        "species": "Stabitis",
        "query": ["regions ![Orion-CygnusArm]"],
        "children": [
            {"variant": "Peach", "query": ["mats [Antimony]"]},
            {"variant": "Lime", "query": ["mats [Polonium]"]},
        ],
    }],
}


def system(star_type="K", materials=None, temp=178.0, region=None):
    star = {"body_id": 0, "is_star": True, "star_type": star_type, "radius": 4.0e8,
            "surface_temp": 4500, "distance_to_arrival": 0.0}
    planet = {"body_id": 3, "planet_class": "Rocky body", "surface_gravity": 2.0,
              "surface_temp": temp, "surface_pressure": 2000.0, "atmosphere_type": "CarbonDioxide",
              "atmosphere_composition": [{"Name": "CarbonDioxide", "Percent": 99.0}],
              "materials": materials or [], "volcanism": "", "parents": [{"Star": 0}],
              "semi_major_axis": 1.0e11}
    return planet, [star, planet]


class BioVariantTests(unittest.TestCase):
    def setUp(self):
        trees = (Node(ALEOIDA), Node(FUNGOIDA))
        patcher = mock.patch.object(bio_variants, "_criteria", return_value=trees)
        patcher.start()
        self.addCleanup(patcher.stop)
        bio_variants._CACHE.clear()

    def test_star_types_flatten_as_srvsurvey_does(self):
        self.assertEqual([flatten_star_type(kind) for kind in ("DA", "WC", "CN", "M_RedGiant", "TTS", "K")],
                         ["D", "W", "C", "M", "TTS", "K"])

    def test_the_parent_star_decides_the_colour(self):
        planet, items = system("K")
        props = body_properties(planet, items, 18)
        self.assertEqual(props["Star"], ["K"])
        self.assertAlmostEqual(props["SurfaceGravity"], 0.2, msg="m/s² / 10, as the criteria were measured")
        self.assertEqual(props["AtmosphereComposition"], {"CarbonDioxide": 100.0}, "a single gas is 100%")
        self.assertIn("Aleoida Arcus - Turquoise", predict(props))
        self.assertNotIn("Aleoida Arcus - Green", predict(props))

    def test_materials_and_regions_decide_too(self):
        planet, items = system(materials=[{"symbol": "antimony", "percent": 0.4},
                                          {"symbol": "polonium", "percent": 0.1}])
        self.assertIn("Fungoida Stabitis - Peach", predict(body_properties(planet, items, 20)))
        self.assertNotIn("Fungoida Stabitis - Lime", predict(body_properties(planet, items, 20)),
                         "a trace under 0.25% does not count")
        self.assertEqual({name for name in predict(body_properties(planet, items, 7)) if "Stabitis" in name},
                         set(), "Orion-Cygnus Arm is excluded")

    def test_body_variants_name_codex_entries(self):
        planet, items = system("K")
        variants = bio_variants.body_variants(planet, items, 18)
        self.assertEqual(variants["aleoida arcus"],
                         [{"colour": "Turquoise", "key": "$Codex_Ent_Aleoids_01_K_Name;", "predicted": True}])

    def test_colours_follow_the_star_when_species_rules_disagree(self):
        """BioScan predicted the species; SrvSurvey's species rules may not
        agree, but its colour still follows the star."""
        planet, items = system("K", temp=230.0)
        self.assertEqual(predict(body_properties(planet, items, 18)), set())
        variants = bio_variants.body_variants(planet, items, 18)
        self.assertEqual([row["colour"] for row in variants["aleoida arcus"]], ["Turquoise"])

    def test_another_parent_star_when_the_brightest_gives_no_colour(self):
        """A neutron star outshines the planet's own L star on paper, but
        Aleoida has no neutron colour: the other parent star still answers."""
        planet, items = system("N", temp=230.0)
        own = {"body_id": 4, "is_star": True, "star_type": "K", "radius": 4.0e8, "surface_temp": 1,
               "parents": [{"Null": 0}], "semi_major_axis": 1.0e12}
        planet["parents"] = [{"Star": 4}, {"Null": 0}]
        items[0]["parents"] = [{"Null": 0}]
        variants = bio_variants.body_variants(planet, items + [own], 18)
        self.assertEqual([row["colour"] for row in variants["aleoida arcus"]], ["Turquoise"])
        self.assertFalse(variants["aleoida arcus"][0]["predicted"])

    def test_no_parent_star_scan_means_no_colours(self):
        planet, items = system()
        self.assertIsNone(body_properties(planet, [planet]))
        self.assertEqual(bio_variants.body_variants(planet, [planet]), {})

    def test_the_brightest_of_two_parent_stars(self):
        planet, items = system()
        near = {"body_id": 1, "is_star": True, "star_type": "M", "radius": 2.0e8, "surface_temp": 3000,
                "parents": [{"Null": 2}], "semi_major_axis": 1.0e9}
        far = {"body_id": 4, "is_star": True, "star_type": "F", "radius": 8.0e8, "surface_temp": 7000,
               "parents": [{"Null": 2}], "semi_major_axis": 1.0e9}
        planet["parents"] = [{"Null": 2}]
        self.assertEqual(body_properties(planet, [near, far, planet])["Star"], ["F"])


class PackagedCriteriaTests(unittest.TestCase):
    def test_every_packaged_criteria_file_parses(self):
        bio_variants._criteria.cache_clear()
        self.addCleanup(bio_variants._criteria.cache_clear)
        folder = bio_variants.criteria_dir()
        if not folder.is_dir():
            self.skipTest("data/bio_criteria is not present")
        trees = bio_variants._criteria()
        self.assertEqual(len(trees), len(list(folder.glob("*.json"))))


if __name__ == "__main__":
    unittest.main()
