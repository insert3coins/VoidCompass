"""Every jump from every journal, for the Galactic Atlas's "where you have been".

Deep Survey keeps only the newest 5,000 jumps, so a commander's older trips
(Beagle Point, in the case that found this) vanished from the map. The travel
history keeps them all, per commander, and the atlas draws from it.
"""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from voidcompass.core.persistence_queue import flush_persistence
from voidcompass.exploration.expedition_map_view import ExpeditionMapView
from voidcompass.exploration.travel_history import TravelHistory


def event(timestamp, name, **fields):
    return json.dumps({"timestamp": timestamp, "event": name, **fields})


def jump(timestamp, system, pos, dist=20.0, star=None):
    lines = []
    if star:
        lines.append(event(timestamp.replace(":00Z", ":-5Z").replace("-5Z", "00Z"), "StartJump",
                           JumpType="Hyperspace", StarSystem=system, StarClass=star))
    lines.append(event(timestamp, "FSDJump", StarSystem=system, StarPos=pos, JumpDist=dist))
    return lines


class TravelHistoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.journals = self.root / "journals"
        self.journals.mkdir()
        # Saves go through the background writer: let it finish before the
        # folder is removed (cleanups run last-registered first).
        self.addCleanup(lambda: flush_persistence(str(self.root / "travel_history.json"), timeout=5))

    def write(self, name, lines):
        (self.journals / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def history(self):
        return TravelHistory(str(self.root / "travel_history.json"))

    def test_every_jump_of_the_commander_is_kept_with_its_star_class(self):
        self.write("Journal.2026-02-01T100000.01.log", [
            event("2026-02-01T10:00:00Z", "Commander", FID="F1", Name="Me"),
            event("2026-02-01T10:00:05Z", "Location", StarSystem="Sol", StarPos=[0, 0, 0]),
            *jump("2026-02-01T10:05:00Z", "Beagle Point", [-1111.56, -134.22, 65269.75], 64000, star="K"),
            event("2026-02-01T11:00:00Z", "Commander", FID="F2", Name="Alt"),
            *jump("2026-02-01T11:05:00Z", "Colonia", [-9530.5, -910.3, 19808.1]),
        ])
        history = self.history()
        self.assertEqual(history.import_journals(str(self.journals), commander="Me", fid="F1"), 2)
        rows = history.route_rows()
        self.assertEqual([row["system"] for row in rows], ["Sol", "Beagle Point"], "the other commander's jump is not ours")
        self.assertEqual((rows[1]["star_class"], rows[1]["jump_dist"]), ("K", 64000.0))
        # Reading the folder again adds nothing: each file is remembered.
        self.assertEqual(history.import_journals(str(self.journals), commander="Me", fid="F1"), 0)

    def test_older_journals_read_later_keep_the_journey_in_order_and_it_survives_a_restart(self):
        self.write("Journal.2026-03-01T100000.01.log", [
            event("2026-03-01T10:00:00Z", "Commander", FID="F1", Name="Me"),
            *jump("2026-03-01T10:05:00Z", "Later", [10, 0, 10])])
        history = self.history()
        history.import_journals(str(self.journals), fid="F1")
        self.write("Journal.2026-02-01T100000.01.log", [
            event("2026-02-01T10:00:00Z", "Commander", FID="F1", Name="Me"),
            *jump("2026-02-01T10:05:00Z", "Earlier", [5, 0, 5])])
        history.import_journals(str(self.journals), fid="F1")
        # A live jump, then a login at the same place (not a new arrival).
        history.observe({"timestamp": "2026-03-02T10:00:00Z", "event": "FSDJump", "StarSystem": "Newest", "StarPos": [20, 0, 20]})
        history.observe({"timestamp": "2026-03-03T10:00:00Z", "event": "Location", "StarSystem": "Newest", "StarPos": [20, 0, 20]})
        self.assertEqual([row["system"] for row in history.route_rows()], ["Earlier", "Later", "Newest"])
        history.flush()
        flush_persistence(history.path, timeout=5)
        self.assertEqual([row["system"] for row in self.history().route_rows()], ["Earlier", "Later", "Newest"])


class AtlasJourneyTests(unittest.TestCase):
    def view(self, history_rows, survey_rows):
        history = SimpleNamespace(revision=1, route_rows=lambda: history_rows)
        view = ExpeditionMapView.__new__(ExpeditionMapView)
        view.app = SimpleNamespace(travel_history=history)
        view._journey_cache = (None, [], {})
        view._region_by_system = {}
        return view

    def test_the_atlas_draws_the_whole_journey_not_just_the_last_5000(self):
        old = [{"system": "Beagle Point", "pos": [-1111.56, -134.22, 65269.75], "timestamp": "2026-02-10T10:00:00Z",
                "star_class": "", "jump_dist": 60000.0}]
        middle = [{"system": f"S{index}", "pos": [0, 0, index * 10.0], "timestamp": f"2026-03-01T{index // 60:02d}:{index % 60:02d}:00Z",
                   "star_class": "M", "jump_dist": 10.0} for index in range(20)]
        survey = [{"system": "S19", "pos": [0, 0, 190.0], "timestamp": middle[-1]["timestamp"], "fss_complete": True, "star_class": "M"},
                  {"system": "Not Yet Imported", "pos": [0, 0, 400.0], "timestamp": "2026-03-02T00:00:00Z", "jump_dist": 5.0}]
        route, journey = self.view(old + middle, survey)._journey(survey)
        self.assertEqual(route[0]["system"], "Beagle Point")
        self.assertEqual(route[-1]["system"], "Not Yet Imported", "Deep Survey covers jumps the history hasn't read yet")
        self.assertTrue(next(row for row in route if row["system"] == "S19")["fss_complete"])
        self.assertEqual((journey["jumps"], journey["systems"]), (22, 22))
        self.assertIn("40", journey["regions"], "Beagle Point's region, The Abyss, counts as visited")
        self.assertEqual(journey["regions"]["40"]["systems"], 1)

    def test_a_very_long_journey_keeps_every_recent_jump_and_a_spread_of_older_ones(self):
        rows = [{"system": f"S{index}", "pos": [index, 0, index], "timestamp": f"2026-01-01T00:00:{index:06d}Z",
                 "star_class": "", "jump_dist": 1.0} for index in range(12000)]
        route, journey = self.view(rows, [])._journey([])
        self.assertEqual(len(route), 8000)
        self.assertEqual(route[0]["system"], "S0")
        self.assertEqual([row["system"] for row in route[-3000:]], [f"S{index}" for index in range(9000, 12000)])
        self.assertEqual((journey["jumps"], journey["systems"], journey["distance_ly"]), (12000, 12000, 12000.0))


if __name__ == "__main__":
    unittest.main()
