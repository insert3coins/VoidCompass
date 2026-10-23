"""5.6.1: Explore & Survey in the newer pages' style. A hero for the system,
plain tabs (the route is on the Expeditions page now), one survey order
everywhere (biology still to do, then geology and mining, then value) with a
sort switch, first footfalls and codex targets counted, and big systems
cheaper to redraw."""

import unittest
from pathlib import Path

from voidcompass.exploration import stellar_cartography
from voidcompass.overlays import hud_pages

ROOT = Path(__file__).resolve().parents[1]
EXPLORE = (ROOT / "web" / "dashboard" / "explore.js").read_text(encoding="utf-8")


class OrderTests(unittest.TestCase):
    def test_one_survey_order(self):
        rows = [{"name": "value", "max_value": 9_000_000}, {"name": "geo", "geo_count": 2, "max_value": 10},
                {"name": "bio done", "bio_count": 2, "bio_complete": True, "max_value": 5},
                {"name": "bio", "bio_count": 1, "max_value": 1}]
        self.assertEqual([row["name"] for row in sorted(rows, key=hud_pages.survey_rank)], ["bio", "geo", "value", "bio done"])

    def test_the_board_sorts_the_same_way_and_can_be_switched(self):
        self.assertIn('const SORTS = [["bio", "BIO FIRST"], ["value", "VALUE"], ["distance", "DISTANCE"]];', EXPLORE)
        self.assertIn("ui.number(body.bio_count) > ui.number(body.bio_done)", EXPLORE)


class PageTests(unittest.TestCase):
    def test_the_route_moved_to_expeditions(self):
        self.assertNotIn('data-explore-panel="route"', EXPLORE)
        self.assertIn('data-page="mission"', EXPLORE, "a slim next-waypoint line links to it")
        self.assertIn("export function routeMarkup", EXPLORE)
        expeditions = (ROOT / "web" / "dashboard" / "expeditions.js").read_text(encoding="utf-8")
        self.assertIn('import {routeMarkup} from "./explore.js";', expeditions)

    def test_the_hero_counts_codex_targets_and_footfalls(self):
        for marker in ('id="explore-codex"', 'id="explore-footfall"', 'class="explore-hero"', 'class="chip footfall"'):
            self.assertIn(marker, EXPLORE)
        self.assertNotIn("workboard-orbits", EXPLORE, "the 18-body strip gave way to the orrery")

    def test_title_buttons(self):
        page = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = page.split('data-page-name="explore"', 1)[1].split("</header>", 1)[0]
        self.assertIn('data-page="planet-materials">PLANETARY', section)
        self.assertNotIn("GROUND NAV", section)


class SpeedTests(unittest.TestCase):
    def test_body_facts_are_kept_until_the_body_changes(self):
        item = {"name": "X 1", "body_id": 1, "radius": 1e6, "organic_scans": {"a": {"species": "Bac", "sample_idx": 1}}}
        first = stellar_cartography._cached_body_facts(item, False)
        first["codex"] = ["added by the deck"]
        again = stellar_cartography._cached_body_facts(item, False)
        self.assertNotIn("codex", again, "handed out as copies")
        item["organic_scans"]["a"]["sample_idx"] = 2
        self.assertEqual(stellar_cartography._cached_body_facts(item, False)["organics"][0]["state"], "2/3",
                         "a new sample makes them anew")
        item["volcanism"] = "Major silicate vapour geysers volcanism"
        self.assertIn("volcanism", stellar_cartography._cached_body_facts(item, False))


class ApiTests(unittest.TestCase):
    def test_the_survey_route_is_listed(self):
        api = (ROOT / "api.md").read_text(encoding="utf-8")
        self.assertIn("`/api/v1/exploration/survey`", api)
        source = (ROOT / "src" / "voidcompass" / "services" / "local_api.py").read_text(encoding="utf-8")
        self.assertIn('r"/exploration/survey"', source)


if __name__ == "__main__":
    unittest.main()
