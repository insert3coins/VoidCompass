import unittest

from dashboard import MainDashboard


class DashboardRouteProgressTests(unittest.TestCase):
    @staticmethod
    def _app(route=None, current="Sol", waypoints=None):
        app = MainDashboard.__new__(MainDashboard)
        app.route_list = list(route or [])
        app.current_sys = current

        class WaypointManager:
            pass

        app.waypoint_manager = WaypointManager()
        app.waypoint_manager.waypoints = list(waypoints or [])
        return app

    def test_live_nav_route_reports_remaining_jumps_from_current_system(self):
        app = self._app(["Sol", "Achenar", "Alioth", "Colonia"], current="Achenar")

        progress = app._current_route_progress()

        self.assertEqual(progress["mode"], "game")
        self.assertEqual(progress["remaining"], 2)
        self.assertEqual(progress["text"], "NAV ROUTE · 2 JUMPS LEFT")
        self.assertEqual(progress["summary"], "2 LEFT")

    def test_upcoming_only_nav_route_counts_every_entry_as_a_remaining_jump(self):
        app = self._app(["Achenar", "Alioth", "Colonia"], current="Sol")

        progress = app._current_route_progress()

        self.assertEqual(progress["remaining"], 3)
        self.assertEqual(progress["text"], "NAV ROUTE · 3 JUMPS LEFT")

    def test_live_nav_route_takes_priority_over_saved_waypoints(self):
        app = self._app(
            ["Sol", "Achenar"], current="Sol",
            waypoints=[{"name": "Old route", "visited": False}],
        )

        progress = app._current_route_progress()

        self.assertEqual(progress["mode"], "game")
        self.assertEqual(progress["text"], "NAV ROUTE · 1 JUMP LEFT")

    def test_saved_waypoints_are_labelled_and_show_visited_progress(self):
        app = self._app(waypoints=[
            {"name": "One", "visited": True},
            {"name": "Two", "visited": True},
            {"name": "Three", "visited": False},
            {"name": "Four", "visited": False},
        ])

        progress = app._current_route_progress()

        self.assertEqual(progress["mode"], "waypoints")
        self.assertEqual(progress["text"], "WAYPOINTS · 2/4 · 2 LEFT")
        self.assertEqual(progress["summary"], "2/4")

    def test_no_route_has_an_explicit_inactive_state(self):
        progress = self._app()._current_route_progress()

        self.assertEqual(progress["text"], "NO ACTIVE ROUTE")
        self.assertEqual(progress["summary"], "INACTIVE")


if __name__ == "__main__":
    unittest.main()
