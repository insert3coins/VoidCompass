"""5.5.13: the exobiology snapshot reads a long career's surveys in place
and copies only what it hands out, and a page refresh asking several times
gets one answer, made again as soon as anything changes."""

import tempfile
import time
import unittest
from pathlib import Path

from voidcompass.mining.specialist_engine import SpecialistEngine


def engine(test, surveys=3000):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    e = SpecialistEngine(str(Path(folder.name) / "specialists.json"))
    e.state["exobiology"]["surveys"] = {
        f"k{i}": {"key": f"k{i}", "system": f"Sys {i}", "body": f"Body {i}", "updated_ts": i,
                  "pins": [{"id": f"p{i}", "kind": "organic_sample", "lat": 1.0, "lon": 2.0, "metadata": {"progress": 1}}],
                  "completed": {}}
        for i in range(surveys)}
    return e


class SnapshotTests(unittest.TestCase):
    def test_the_same_answers(self):
        e = engine(self)
        e.update_position({"lat": 1.001, "lon": 2.0, "radius_m": 1_000_000, "body": "Body 7"})
        snap = e.exobiology_snapshot()
        self.assertEqual(snap["current_map"]["key"], "k7", "the planet you're on")
        self.assertEqual(snap["current_map"]["pins_total"], 1)
        self.assertIsNotNone(snap["current_map"]["pins"][0]["distance_m"])
        self.assertEqual([row["key"] for row in snap["surveys"]], [f"k{i}" for i in range(2999, 2949, -1)], "newest 50")

    def test_hands_out_copies_never_the_state(self):
        e = engine(self)
        snap = e.exobiology_snapshot()
        snap["current_map"]["pins"].clear()
        snap["surveys"].clear()
        again = e.exobiology_snapshot()
        self.assertTrue(again["current_map"]["pins"])
        self.assertEqual(len(again["surveys"]), 50)
        self.assertTrue(e.state["exobiology"]["surveys"]["k2999"]["pins"])

    def test_made_again_when_anything_changes(self):
        e = engine(self)
        first = e.exobiology_snapshot()["current_map"]["key"]
        e.update_position({"lat": 1.0, "lon": 2.0, "radius_m": 1_000_000, "body": "Body 3"})
        self.assertEqual(e.exobiology_snapshot()["current_map"]["key"], "k3", "moving changes it")
        e.state["exobiology"]["surveys"]["k3"]["pins"].append({"id": "new", "kind": "waypoint", "lat": 1.0, "lon": 2.0})
        e._save()
        self.assertEqual(e.exobiology_snapshot()["current_map"]["pins_total"], 2, "a saved change shows at once")
        self.assertNotEqual(first, "k3")

    def test_a_long_career_is_quick(self):
        e = engine(self, surveys=15000)
        started = time.perf_counter()
        e.exobiology_snapshot()
        self.assertLess(time.perf_counter() - started, 0.15, "it took ~0.19 s when it copied everything")
        started = time.perf_counter()
        for _ in range(10):
            e.exobiology_snapshot()
        self.assertLess(time.perf_counter() - started, 0.05, "asked again without a change: reused")


if __name__ == "__main__":
    unittest.main()
