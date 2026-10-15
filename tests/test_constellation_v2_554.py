"""Constellation v2 (5.5.4): designations, the night behind each star, its
marks, a constellation's character and lore, the sky chart and the almanac."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import unittest

from voidcompass.core import config as config_module
from voidcompass.exploration.constellation import CHARACTERS, GREEK, LORE, almanac, constellations

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "dashboard"
START = datetime(2026, 3, 1, 19, 0, tzinfo=timezone.utc)


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def night(index, system, minutes, x=0.0, z=0.0, star="K"):
    """One session: arrive at ``system``, stay ``minutes``, then a short hop."""
    begin = START + timedelta(days=index)
    return [(stamp(begin), system, x, 0.0, z, star),
            (stamp(begin + timedelta(minutes=minutes)), f"{system} B", x + 5, 0.0, z + 5, "M")]


def session(index, **figures):
    begin = START + timedelta(days=index)
    return {"started": stamp(begin), "ended": stamp(begin + timedelta(hours=4)), "ship": "Mandalay", **figures}


class StarTests(unittest.TestCase):
    def test_designations_by_brightness(self):
        rows = night(0, "Dim", 20) + night(1, "Bright", 90) + night(2, "Middling", 45)
        item = constellations(rows)[0]
        named = {star["system"]: star["designation"] for star in item["stars"]}
        self.assertEqual(named, {"Bright": GREEK[0], "Middling": GREEK[1], "Dim": GREEK[2]}, "α is where you stayed longest")

    def test_the_night_behind_a_star(self):
        rows = night(0, "Colonia", 60, -9530, 19808)
        sessions = [session(0, jumps=40, distance_ly=1800, first_discoveries=12, rare_worlds=1, bio_analyses=2,
                            highlights=[{"kind": "RARE", "title": "Earth-like world"}, {"kind": "SALE", "title": "Sold"}])]
        postcards = [{"id": "abc", "title": "Colonia", "at": (START + timedelta(minutes=30)).timestamp()}]
        star = constellations(rows, "weary", None, sessions, postcards, [{"system": "colonia"}])[0]["stars"][0]
        evening = star["nights"][0]
        self.assertEqual((evening["figures"]["jumps"], evening["figures"]["firsts"], evening["flown"]), (40, 12, "4 hours"))
        self.assertEqual(evening["highlights"], ["Earth-like world"], "only the finds")
        self.assertEqual(evening["postcards"], [{"id": "abc", "title": "Colonia"}])
        self.assertTrue(evening["date"].endswith("3312"))
        self.assertEqual(star["capsules"], 1)
        self.assertEqual(star["marks"], ["first", "rare", "photo", "capsule"])

    def test_without_the_captains_log_a_star_still_has_its_night(self):
        star = constellations(night(0, "Sol", 40))[0]["stars"][0]
        self.assertEqual(len(star["nights"]), 1)
        self.assertEqual(star["marks"], [])


class ConstellationTests(unittest.TestCase):
    def test_character_and_lore(self):
        rows = [row for index in range(3) for row in night(index, f"S{index}", 40)]
        explorer = constellations(rows, "weary", None, [session(index, first_discoveries=30, dss_maps=4) for index in range(3)])[0]
        self.assertEqual((explorer["character"], explorer["epithet"]), ("pathfinder", CHARACTERS["pathfinder"]))
        self.assertIn("90 first discoveries", explorer["lore"])
        self.assertNotIn("{", explorer["lore"])
        gardener = constellations(rows, "stoic", None, [session(index, bio_analyses=9) for index in range(3)])[0]
        self.assertEqual(gardener["character"], "gardener")
        self.assertTrue(gardener["lore"].startswith(LORE["normal"]["gardener"].split("{")[0]) or "27" in gardener["lore"])
        quiet = constellations(rows)[0]
        self.assertEqual(quiet["character"], "wanderer", "nothing recorded: a wanderer's")

    def test_names_are_never_repeated(self):
        rows = [row for index in range(120) for row in night(index, f"System {index}", 30, index * 10.0, index * 10.0)]
        sky = constellations(rows)
        names = [item["name"] for item in sky]
        self.assertGreater(len(names), 10)
        self.assertEqual(len(names), len(set(names)))

    def test_on_the_sky_chart_where_it_lies(self):
        rows = [row for index in range(9) for row in night(index, f"Near {index}", 30, 10.0 * index, 10.0 * index)]
        rows += [row for index in range(9, 18) for row in night(index, f"Core {index}", 30, 25.0, 25899.0)]
        near, core = constellations(rows)[:2]
        for item in (near, core):
            self.assertLessEqual(math.hypot(*item["place"]), .95)
        self.assertGreater(core["place"][1], near["place"][1], "the core is straight up")
        self.assertGreater(core["from_sol"], 25000)
        self.assertTrue(core["region"])


class AlmanacTests(unittest.TestCase):
    def test_pole_star_brightest_and_farthest(self):
        rows = night(0, "Home", 30) + night(1, "Away", 90, 0, 5000) + night(2, "Home", 30) + night(3, "Home", 20)
        book = almanac(constellations(rows))
        self.assertEqual(book["pole_star"]["system"], "Home")
        self.assertEqual(book["brightest"]["system"], "Away")
        self.assertEqual(book["stars"], 2)
        self.assertEqual(almanac([]), {})


class PageTests(unittest.TestCase):
    def test_the_page_has_the_chart_the_night_and_the_almanac(self):
        page = (WEB / "constellation.js").read_text(encoding="utf-8")
        for marker in ('data-sky-view="chart"', "function paintChart", "THE NIGHT BEHIND", "data-sky-star", 'data-sky="trace"',
                       "sky-almanac", "constellation_designations", "next star"):
            self.assertIn(marker, page)
        self.assertIn("constellation_designations", config_module.PROFILE_SETTINGS)
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard_capsules_mixin.py").read_text(encoding="utf-8")
        self.assertIn('"almanac": almanac(sky)', source)


if __name__ == "__main__":
    unittest.main()
