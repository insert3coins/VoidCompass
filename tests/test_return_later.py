"""Journal-grounded, profile-local Return Later board regression tests."""

from pathlib import Path
import tempfile
import unittest

from voidcompass.dashboard.html_explore_workspace import HtmlExploreWorkspaceMixin
from voidcompass.exploration.return_later import (
    dismiss_entry, empty_state, read_state, reconcile_state,
    unfinished_entries, write_state,
)


class _Waypoints:
    def __init__(self):
        self.waypoints = []
        self.should_fail = False

    def add_waypoint(self, name, coords, note):
        self.waypoints.append({"name": name, "coords": coords, "note": note})

    def save(self):
        return not self.should_fail


class _Dashboard(HtmlExploreWorkspaceMixin):
    def __init__(self, directory):
        self.directory = Path(directory)
        self.config = {"active_commander_profile": "one", "stellar_survey_queue_state": {}}
        self.current_sys = "Alpha"
        self.current_coords = [1, 2, 3]
        self.scan_items = [{
            "name": "Alpha 1", "body_id": 1, "planet_class": "Water world",
            "dss_complete": False,
        }]
        self.scanned = 1
        self.total = 1
        self.scan_total_confirmed = True
        self.fss_all_bodies = True
        self.waypoint_manager = _Waypoints()
        self.copied = ""
        self.publishes = 0

    def _profile_path(self, filename):
        return self.directory / self.config["active_commander_profile"] / filename

    def _schedule_html_dashboard_publish(self, **_kwargs):
        self.publishes += 1

    def _html_copy_text(self, value):
        self.copied = value
        return True

    def update_hud(self):
        pass


class ReturnLaterTests(unittest.TestCase):
    def test_only_recorded_unfinished_targets_are_added(self):
        rows = unfinished_entries(
            "Alpha", [
                {"name": "Alpha A", "body_id": 1, "is_star": True, "star_type": "G"},
                {"name": "Alpha 1", "body_id": 2, "planet_class": "Water world", "dss_complete": False},
                {"name": "Alpha 2", "body_id": 3, "planet_class": "Rocky body", "bio_count": 3,
                 "organic_scans": {"A": {"scan_type": "Analyse"}}},
                {"name": "Alpha 3", "body_id": 4, "planet_class": "Rocky body"},
            ], {"pinned": ["body:4"]}, scanned=4, total=7,
            total_confirmed=True, visited_at="2026-09-25T01:00:00Z",
            coords=[1, 2, 3],
        )
        self.assertEqual({row["id"] for row in rows}, {
            "alpha|fss", "alpha|body:2", "alpha|body:3", "alpha|body:4",
        })
        self.assertEqual(rows[0]["reasons"], ["3 FSS bodies unresolved"])
        self.assertEqual(rows[2]["reasons"], ["Biology 1/3 analysed"])
        self.assertEqual(rows[3]["source"], "journal + pin")
        self.assertEqual(rows[1]["coords"], [1.0, 2.0, 3.0])

    def test_unconfirmed_total_is_not_labelled_missing_fss(self):
        self.assertEqual(unfinished_entries(
            "Alpha", [], scanned=2, total=9, total_confirmed=False,
        ), [])

    def test_unknown_origin_coordinate_is_not_added_to_route(self):
        body = {"name": "Alpha 1", "body_id": 1, "planet_class": "Water world"}
        row = unfinished_entries("Alpha", [body], coords=[0, 0, 0])[0]
        self.assertIsNone(row["coords"])
        sol = unfinished_entries("Sol", [{**body, "name": "Sol 1"}], coords=[0, 0, 0])[0]
        self.assertEqual(sol["coords"], [0.0, 0.0, 0.0])

    def test_pinned_but_journal_complete_body_is_not_return_later_work(self):
        rows = unfinished_entries(
            "Alpha", [{"name": "Alpha 1", "body_id": 1, "planet_class": "Rocky body",
                       "dss_complete": True, "bio_count": 0, "geo_count": 0}],
            {"pinned": ["body:1"]},
        )
        self.assertEqual(rows, [])

    def test_named_signal_only_biology_is_retained_without_inventing_a_scan(self):
        rows = unfinished_entries(
            "Alpha", [], scanned=0, total=3, total_confirmed=True,
            body_signals={7: {"body_name": "Alpha 7", "bio": 2}},
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["reasons"], ["3 FSS bodies unresolved"])
        self.assertEqual(rows[1]["body"], "Alpha 7")
        self.assertEqual(rows[1]["source"], "journal signals")

    def test_board_is_not_populated_until_departure(self):
        body = {"name": "Alpha 1", "body_id": 1, "planet_class": "Water world"}
        self.assertEqual(reconcile_state(empty_state(), "Alpha", [body])["entries"], [])
        self.assertEqual(len(reconcile_state(empty_state(), "Alpha", [body], departure=True)["entries"]), 1)

    def test_revisit_clears_completed_body_but_keeps_unobserved_rows(self):
        before = reconcile_state(empty_state(), "Alpha", [
            {"name": "Alpha 1", "body_id": 1, "planet_class": "Water world"},
            {"name": "Alpha 2", "body_id": 2, "planet_class": "Ammonia world"},
        ], visited_at="2026-09-25T01:00:00Z", departure=True)
        sparse = reconcile_state(before, "Alpha", [], visited_at="2026-09-25T03:00:00Z")
        self.assertEqual(len(sparse["entries"]), 2)
        later = reconcile_state(sparse, "Alpha", [
            {"name": "Alpha 1", "body_id": 1, "planet_class": "Water world", "dss_complete": True},
        ], visited_at="2026-09-25T04:00:00Z")
        self.assertEqual([row["body"] for row in later["entries"]], ["Alpha 2"])
        self.assertEqual(later["entries"][0]["last_visited"], "2026-09-25T01:00:00Z")
        left_again = reconcile_state(
            later, "Alpha", [], visited_at="2026-09-25T05:00:00Z", departure=True,
        )
        self.assertEqual(left_again["entries"][0]["last_visited"], "2026-09-25T05:00:00Z")

    def test_sparse_revisit_scan_does_not_erase_known_biology_or_dss_work(self):
        before = reconcile_state(
            empty_state(), "Alpha", [
                {"name": "Alpha 1", "body_id": 1, "planet_class": "Water world",
                 "bio_count": 2, "dss_complete": False},
            ], departure=True,
        )
        sparse = reconcile_state(before, "Alpha", [
            {"name": "Alpha 1", "body_id": 1, "planet_class": "Rocky body",
             "bio_count": 0, "organic_complete_count": 1},
        ])
        self.assertEqual(sparse["entries"][0]["reasons"], [
            "Biology 1/2 analysed", "Valuable world not DSS mapped",
        ])
        mapped = reconcile_state(sparse, "Alpha", [
            {"name": "Alpha 1", "body_id": 1, "dss_complete": True,
             "organic_complete_count": 1},
        ])
        self.assertEqual(mapped["entries"][0]["reasons"], ["Biology 1/2 analysed"])
        complete = reconcile_state(mapped, "Alpha", [
            {"name": "Alpha 1", "body_id": 1, "dss_complete": True,
             "organic_complete_count": 2},
        ])
        self.assertEqual(complete["entries"], [])

    def test_signal_only_biology_survives_minimal_scanorganic_row(self):
        before = reconcile_state(
            empty_state(), "Alpha", [], departure=True,
            body_signals={7: {"body_name": "Alpha 7", "bio": 2}},
        )
        partial = reconcile_state(before, "Alpha", [
            {"name": "Alpha 7", "body_id": 7, "bio_count": 0,
             "organic_complete_count": 1},
        ])
        self.assertEqual(partial["entries"][0]["reasons"], ["Biology 1/2 analysed"])

    def test_dismissed_target_stays_dismissed_after_departure(self):
        item = {"name": "Alpha 1", "body_id": 1, "planet_class": "Water world"}
        state = reconcile_state(empty_state(), "Alpha", [item], departure=True)
        dismissed = dismiss_entry(state, "alpha|body:1")
        refreshed = reconcile_state(dismissed, "Alpha", [item], departure=True)
        self.assertEqual(refreshed["entries"], [])
        self.assertEqual(refreshed["dismissed"], ["alpha|body:1"])

    def test_profile_files_and_commands_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            dashboard = _Dashboard(directory)
            dashboard._reconcile_return_later(
                visited_at="2026-09-25T01:00:00Z", departure=True,
            )
            one_path = Path(directory) / "one" / "return_later.json"
            self.assertTrue(one_path.exists())
            self.assertEqual(len(read_state(one_path)["entries"]), 1)
            self.assertTrue(dashboard._handle_html_explore_command({
                "operation": "return_later_copy", "id": "alpha|body:1",
            }))
            self.assertEqual(dashboard.copied, "Alpha")
            self.assertTrue(dashboard._handle_html_explore_command({
                "operation": "return_later_waypoint", "id": "alpha|body:1",
            }))
            self.assertEqual(dashboard.waypoint_manager.waypoints[0]["coords"], [1.0, 2.0, 3.0])
            dashboard.waypoint_manager.waypoints.clear()
            dashboard.waypoint_manager.should_fail = True
            self.assertFalse(dashboard._handle_html_explore_command({
                "operation": "return_later_waypoint", "id": "alpha|body:1",
            }))
            self.assertEqual(dashboard.waypoint_manager.waypoints, [])
            self.assertTrue(dashboard._handle_html_explore_command({
                "operation": "return_later_dismiss", "id": "alpha|body:1",
            }))
            self.assertEqual(read_state(one_path)["entries"], [])
            dashboard.config["active_commander_profile"] = "two"
            dashboard._reconcile_return_later(departure=True)
            two_path = Path(directory) / "two" / "return_later.json"
            self.assertTrue(two_path.exists())
            self.assertEqual(len(read_state(two_path)["entries"]), 1)
            self.assertEqual(read_state(one_path)["dismissed"], ["alpha|body:1"])

    def test_state_round_trip_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "board.json"
            self.assertEqual(read_state(path), empty_state())
            self.assertTrue(write_state(path, {"version": 1, "entries": [], "dismissed": ["x"]}))
            self.assertEqual(read_state(path)["dismissed"], ["x"])

    def test_cap_retains_newest_reminders(self):
        rows = [
            {"id": f"old|body:{index}", "system": "Old", "body_key": f"body:{index}",
             "last_visited": f"2026-09-25T00:{index // 60:02d}:{index % 60:02d}Z"}
            for index in range(510)
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "board.json"
            self.assertTrue(write_state(path, {"version": 1, "entries": rows, "dismissed": []}))
            loaded = read_state(path)
        self.assertEqual(len(loaded["entries"]), 500)
        self.assertEqual(loaded["entries"][0]["id"], "old|body:509")
        self.assertEqual(loaded["entries"][-1]["id"], "old|body:10")
        reconciled = reconcile_state({"version": 1, "entries": rows, "dismissed": []}, "Other", [])
        self.assertEqual(reconciled["entries"][0]["id"], "old|body:509")

    def test_live_jump_captures_before_system_state_is_replaced(self):
        source = (Path(__file__).resolve().parents[1] /
                  "src/voidcompass/dashboard/dashboard.py").read_text(encoding="utf-8")
        hook = source.index("if is_jump and not startup_replay and incoming_sys != previous_current_sys:")
        capture = source.index("self._reconcile_return_later(", hook)
        reset = source.index("self.current_sys = incoming_sys", hook)
        scans = source.index("self.scan_items = self.load_scan_items_from_db", hook)
        self.assertLess(hook, capture)
        self.assertLess(capture, reset)
        self.assertLess(capture, scans)
        profile_migration = source.index('if old_key == "unknown_commander":')
        self.assertIn('"return_later.json"', source[profile_migration:source.index("self.config[\"active_commander_profile\"]", profile_migration)])


if __name__ == "__main__":
    unittest.main()
