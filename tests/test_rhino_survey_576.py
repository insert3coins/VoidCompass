"""Rhino survey tools (5.7.6, after EDSMT): the survey's coverage and sweep
stops, the best patch from refining pulses, the rig planner, and where they
show (Rhino map, Rig Tracker, Mining page) and are said."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from voidcompass.core import config as config_module, overlay_registry
from voidcompass.overlays import rhino_lines, rhino_survey
from voidcompass.overlays.surface_map import cluster_deposits
from tests.test_rhino_map_5517 import Deck as RigDeck, Plane, degrees

ROOT = Path(__file__).resolve().parents[1]


class Deck(RigDeck):
    def __init__(self, folder):
        super().__init__(folder)
        self.notes = []
        self.heartbeat_hud = SimpleNamespace(note=lambda kind, fields: self.notes.append((kind, fields)))

    def at(self, east, north):
        self.current_latitude, self.current_longitude = degrees(north), degrees(east)


class CoverageTests(unittest.TestCase):
    def test_the_scanner_covers_what_it_reaches(self):
        covered = set()
        added = rhino_survey.cover(covered, 3000.0, (0.0, 0.0))
        percent, swept = rhino_survey.progress(covered, 3000.0)
        self.assertAlmostEqual(percent, 100 * (2000 / 3000) ** 2, delta=3)
        self.assertEqual(added, len(covered))
        self.assertEqual(rhino_survey.cover(covered, 3000.0, (0.0, 0.0)), 0, "nothing new the second time")
        self.assertEqual(rhino_survey.cover(covered, 3000.0, (9000.0, 0.0)), 0, "out of reach of the area")
        self.assertTrue(swept[0], "the centre stop is swept")
        self.assertFalse(any(swept[1:]))

    def test_sweep_stops_cover_the_whole_area(self):
        for radius in (600.0, 1500.0, 3000.0, 6000.0, 12000.0):
            with self.subTest(radius=radius):
                stops = rhino_survey.sweep_points(radius)
                for _index, x, y in rhino_survey.cells(radius):
                    self.assertTrue(any(math.hypot(x - sx, y - sy) <= rhino_survey.SCANNER_M for sx, sy in stops), (x, y))
                for sx, sy in stops:
                    self.assertLessEqual(math.hypot(sx, sy), radius + .5, "every stop is inside the area")
                covered = set()
                for stop in stops:
                    rhino_survey.cover(covered, radius, stop)
                percent, swept = rhino_survey.progress(covered, radius)
                self.assertEqual(percent, 100.0)
                self.assertTrue(all(swept))
        self.assertEqual(len(rhino_survey.sweep_points(3000.0)), 7)
        self.assertEqual(rhino_survey.sweep_points(1000.0), ((0.0, 0.0),), "a small survey is one stop")


class PatchAndPlanTests(unittest.TestCase):
    def test_the_best_patch_is_where_pulses_gathered(self):
        self.assertIsNone(rhino_survey.best_patch([{"at": [0, 0], "pulses": 2, "materials": []}]), "too few to call")
        deposits = [{"at": [0, 0], "pulses": 3, "materials": ["Platinum"]}, {"at": [100, 0], "pulses": 2, "materials": ["Osmium"]},
                    {"at": [900, 900], "pulses": 4, "materials": ["Gold"]}]
        patch = rhino_survey.best_patch(deposits, (0, 0))
        self.assertEqual((patch["pulses"], patch["deposits"]), (5, 2), "close deposits make one patch")
        self.assertEqual(patch["materials"], ["Platinum", "Osmium"])
        self.assertAlmostEqual(patch["at"][0], 40, delta=1)
        self.assertEqual(patch["bearing"], 90)

    def test_the_plan_keeps_the_spacing(self):
        spacing = 78.0
        rigs = [(0.0, 0.0), (80.0, 0.0)]
        plan = rhino_survey.rig_plan(rigs[0], rigs, spacing, you=(0.0, -200.0), warn_m=3500)
        self.assertEqual(len(plan), rhino_survey.SLOTS - len(rigs))
        points = rigs + [tuple(spot["at"]) for spot in plan]
        for index, a in enumerate(points):
            for b in points[index + 1:]:
                self.assertGreaterEqual(math.hypot(a[0] - b[0], a[1] - b[1]), spacing - .5, (a, b))
        nearest = min(plan, key=lambda spot: spot["distance"])
        self.assertTrue(nearest.get("next"))
        self.assertEqual(sum(1 for spot in plan if spot.get("next")), 1)
        self.assertFalse(any(spot["far"] for spot in plan))
        self.assertEqual(rhino_survey.rig_plan((0, 0), [(0, 0)] * 6, spacing), [], "every rig is down")
        self.assertEqual(rhino_survey.rig_plan(None, [], spacing), [])
        far = rhino_survey.rig_plan((5000.0, 0.0), [(0.0, 0.0)], spacing, warn_m=3500)
        self.assertTrue(all(spot["far"] for spot in far), "a pattern far from your rigs is flagged")


class StoreTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = str(Path(folder.name) / "rhino_survey.json")

    def test_centre_edge_drive_and_keep(self):
        store = rhino_survey.SurveyStore(self.path)
        radius = 1_000_000.0
        self.assertIsNone(store.mark_edge("Sys", "Body 1", 0.0, 0.0, radius), "the centre comes first")
        store.mark_centre("Sys", "Body 1", 0.0, 0.0)
        self.assertEqual(store.survey("sys", "body 1")["radius_m"], rhino_survey.DEFAULT_RADIUS_M)
        size = store.mark_edge("Sys", "Body 1", math.degrees(4000 / radius), 0.0, radius)
        self.assertAlmostEqual(size, 4000, delta=1)
        tiny = rhino_survey.SurveyStore(None)
        tiny.mark_centre("S", "B", 0, 0)
        self.assertEqual(tiny.mark_edge("S", "B", 0, 0, radius), rhino_survey.RADIUS_RANGE_M[0], "never smaller than the least")
        added, percent = store.drive("Sys", "Body 1", 0.0, 0.0, radius)
        self.assertGreater(added, 0)
        self.assertAlmostEqual(percent, 25, delta=3)
        self.assertTrue(store.said("Sys", "Body 1", 50))
        self.assertFalse(store.said("Sys", "Body 1", 50), "once")
        store.note_pulse("Sys", "Body 1", 0.0, 0.0, "Platinum")
        Path(self.path).write_text(json.dumps(store._payload()), encoding="utf-8")
        again = rhino_survey.SurveyStore(self.path)
        survey = again.survey("Sys", "Body 1")
        self.assertEqual((survey["radius_m"], survey["edge"], len(survey["covered"])), (4000, True, added))
        self.assertEqual(again.pulses("Sys", "Body 1"), [(0.0, 0.0, "Platinum")])
        self.assertTrue(again.clear("Sys", "Body 1"))
        self.assertIsNone(again.survey("Sys", "Body 1"))
        self.assertEqual(len(again.pulses("Sys", "Body 1")), 1, "the pulses stay for the best patch")
        self.assertIsNone(again.drive("Sys", "Body 1", 0, 0, radius))

    def test_a_new_edge_starts_coverage_again(self):
        store = rhino_survey.SurveyStore(None)
        radius = 1_000_000.0
        store.mark_centre("S", "B", 0.0, 0.0)
        store.drive("S", "B", 0.0, 0.0, radius)
        store.mark_edge("S", "B", math.degrees(5000 / radius), 0.0, radius)
        self.assertEqual(store.survey("S", "B")["covered"], set())


class DeckTests(unittest.TestCase):
    def deck(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Deck(folder.name)

    def test_keys_mark_the_survey_and_coverage_is_said_once(self):
        deck = self.deck()
        self.assertTrue(deck.survey_store().path.endswith("rhino_survey.json"))
        self.assertEqual(Path(deck.survey_store().path).parent, Path(deck.rig_store().path).parent, "kept beside the rigs")
        self.assertIsNone(deck._survey_mark("edge"))
        self.assertEqual(deck._survey_mark("centre"), "centre")
        deck.at(0, 3000)
        self.assertEqual(deck._survey_mark("edge"), "edge")
        self.assertIn(("survey_marked", {"km": "3.0", "body": deck.current_body_name}), deck.notes)
        for stop in rhino_survey.sweep_points(3000.0):
            deck.at(*stop)
            deck._survey_tick()
        kinds = [kind for kind, _fields in deck.notes]
        self.assertEqual(kinds.count("survey_half"), 1)
        self.assertEqual(kinds.count("survey_done"), 1)
        self.assertLess(kinds.index("survey_half"), kinds.index("survey_done"))
        deck._survey_tick()
        self.assertEqual([kind for kind, _fields in deck.notes].count("survey_done"), 1)
        deck.current_in_srv = False
        self.assertIsNone(deck._survey_tick(), "only the SRV's scanner counts")
        self.assertEqual(deck._survey_mark("clear"), "cleared")

    def test_facts_for_the_rig_tracker_and_mining_page(self):
        deck = self.deck()
        self.assertIsNone(deck._survey_facts())
        deck._survey_mark("centre")
        facts = deck._survey_facts()
        self.assertEqual(facts["survey"]["edge"], False)
        self.assertEqual(facts["survey"]["next"]["compass"] in ("N", "NE", "E", "SE", "S", "SW", "W", "NW"), True)
        for _ in range(4):
            deck._surface_note_pulse({"Type_Localised": "Platinum"})
        facts = deck._survey_facts()
        self.assertEqual(facts["patch"]["pulses"], 4)
        self.assertNotIn("at", facts["patch"])
        deck._rig_mark(1)
        deck.at(0, -300)
        spot = deck._survey_facts()["rig_spot"]
        self.assertLess(spot["distance"], 300, "the next rig spot is in the pattern round rig 1")

    def test_the_best_patch_is_said_when_it_shows_and_when_another_leads(self):
        deck = self.deck()
        for _ in range(3):
            deck._surface_note_pulse({"Type_Localised": "Platinum"})
        deck._surface_note_pulse({"Type_Localised": "Platinum"})
        self.assertEqual([fields for kind, fields in deck.notes if kind == "best_patch"], [{"pulses": "3"}], "once as it grows")
        deck.at(600, 0)
        for _ in range(6):
            deck._surface_note_pulse({"Type_Localised": "Osmium"})
        self.assertEqual([fields for kind, fields in deck.notes if kind == "best_patch"], [{"pulses": "3"}, {"pulses": "5"}])
        fresh = Deck.__new__(Deck)
        fresh.__dict__.update({**deck.__dict__, "notes": [], "_survey_patch_said": None,
                               "heartbeat_hud": SimpleNamespace(note=lambda kind, fields: fresh.notes.append((kind, fields)))})
        fresh._surface_note_pulse({"Type_Localised": "Osmium"})
        self.assertEqual(fresh.notes, [], "a patch from before a restart isn't news")

    def test_the_map_shows_the_survey_patch_and_plan(self):
        deck = self.deck()
        deck._survey_mark("centre")
        for _ in range(3):
            deck._surface_note_pulse({"Type_Localised": "Platinum"})
        deck._update_rhino_map()
        surface = deck.rhino_map_hud._html_render_model
        self.assertEqual(surface["survey"]["radius_m"], rhino_survey.DEFAULT_RADIUS_M)
        self.assertGreater(surface["survey"]["percent"], 0)
        self.assertEqual(len(surface["survey"]["covered"]), rhino_survey.GRID ** 2 // 4)
        self.assertEqual(surface["best_patch"]["pulses"], 3)
        self.assertEqual(len(surface["plan"]), rhino_survey.SLOTS, "the pattern round the patch before any rig")
        deck._rig_mark(1)
        deck.at(0, 30)
        deck._update_rhino_map()
        surface = deck.rhino_map_hud._html_render_model
        self.assertTrue(surface["next_spot"].get("planned"))
        self.assertEqual(len(surface["plan"]), rhino_survey.SLOTS - 1)

    def test_covered_cells_survive_the_hex_string(self):
        covered = {0, 5, 2303, 1000}
        model = rhino_survey.survey_model({"centre": [0.0, 0.0], "radius_m": 3000.0, "edge": True, "covered": covered},
                                          Plane(), (0.0, 0.0))
        text = model["covered"]
        decoded = {index * 4 + bit for index, char in enumerate(text) for bit in range(4) if int(char, 16) & (1 << bit)}
        self.assertEqual(decoded, covered)


class WiringTests(unittest.TestCase):
    def test_keys_and_their_settings(self):
        actions = {row[0]: row[1] for row in overlay_registry.OVERLAY_HOTKEY_SPECS if isinstance(row, tuple)}
        source = (ROOT / "src/voidcompass/core/overlay_registry.py").read_text(encoding="utf-8")
        dashboard = (ROOT / "src/voidcompass/dashboard/dashboard.py").read_text(encoding="utf-8")
        config_source = (ROOT / "src/voidcompass/core/config.py").read_text(encoding="utf-8")
        defaults = {"rhino_survey_centre": "Ctrl+Alt+7", "rhino_survey_edge": "Ctrl+Alt+8", "rhino_survey_clear": ""}
        for name, default in defaults.items():
            key = f"overlay_hotkey_{name}"
            self.assertIn(f'("{name}", "{key}"', source)
            self.assertIn(key, config_module.PROFILE_SETTINGS)
            self.assertIn(f'"{key}": "{default}"', config_source, "after the rig keys; clearing has no key by default")
            self.assertIn(f"'{key}': '{default}'", config_source)
            self.assertIn(f'"{name}"', dashboard)
            if actions is not None:
                self.assertEqual(actions.get(name), key)

    def test_every_page_shows_it(self):
        rhino = (ROOT / "web/rhino_map/app.js").read_text(encoding="utf-8")
        for needle in ("survey.covered", "SWEEP", "best_patch", "surface.plan"):
            self.assertIn(needle, rhino)
        self.assertIn('id="rigs-survey"', (ROOT / "web/rig_tracker/index.html").read_text(encoding="utf-8"))
        self.assertIn("NEXT STOP", (ROOT / "web/rig_tracker/app.js").read_text(encoding="utf-8"))
        mining = (ROOT / "web/dashboard/mining.js").read_text(encoding="utf-8")
        for op in ("survey_centre", "survey_edge", "survey_clear"):
            self.assertIn(f'"{op}"', mining)
        self.assertIn("surveyPanel(data, esc)", mining)

    def test_the_lines_are_whole(self):
        for topic in rhino_survey_lines_topics():
            self.assertIn(topic, rhino_lines.IMPORTANCE)
        self.assertEqual(rhino_lines.IMPORTANCE["survey_done"], 2)


def rhino_survey_lines_topics():
    from voidcompass.overlays import rhino_survey_lines
    return tuple(rhino_survey_lines.IMPORTANCE)


if __name__ == "__main__":
    unittest.main()
