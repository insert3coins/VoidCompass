import unittest
from dashboard import MainDashboard
import route_strip


class _WaypointPlan:
    def __init__(self):
        self.waypoints = [
            {"name": "OLD EXPEDITION STOP", "coords": [100, 0, 0]},
        ]

    @staticmethod
    def get_distance(first, second):
        return route_strip._distance(first, second)

    def get_next_waypoint(self, _current):
        return self.waypoints[0]["name"]


class ExploreRouteWorkspaceTests(unittest.TestCase):
    def test_route_entrypoint_opens_html_explore_workspace(self):
        app = MainDashboard.__new__(MainDashboard)
        opened = []
        app._route_to_html_workspace = opened.append
        app.open_exploration_window('route')
        self.assertEqual(opened, ['explore'])

    def test_specialist_actions_route_to_html_workspaces(self):
        app = MainDashboard.__new__(MainDashboard)
        opened = []
        app._route_to_html_workspace = opened.append
        for section in ('mission','recon','ledger','survey'):
            app.open_exploration_window(section)
        self.assertEqual(opened, ['mission','recon','ledger','explore'])

    def test_live_elite_route_overrides_pending_profile_waypoints(self):
        route = ["CURRENT", "NEW NEXT", "NEW DESTINATION"]
        entries = [
            {"StarSystem": "CURRENT", "StarPos": [0, 0, 0], "StarClass": "K"},
            {"StarSystem": "NEW NEXT", "StarPos": [10, 0, 0], "StarClass": "G"},
            {"StarSystem": "NEW DESTINATION", "StarPos": [20, 0, 0], "StarClass": "M"},
        ]
        plan = _WaypointPlan()

        hops, truncated = route_strip.build_route_hops(
            [0, 0, 0], route, entries, "CURRENT", waypoint_manager=plan,
        )
        track = route_strip.build_route_track(
            [0, 0, 0], route, entries, "CURRENT", waypoint_manager=plan,
        )

        self.assertEqual([hop["name"] for hop in hops], ["NEW NEXT", "NEW DESTINATION"])
        self.assertEqual(truncated, 0)
        self.assertEqual(track["source"], "game")
        self.assertEqual([hop["name"] for hop in track["hops"]], ["NEW NEXT", "NEW DESTINATION"])

    def test_profile_waypoints_remain_fallback_without_elite_route(self):
        plan = _WaypointPlan()

        hops, truncated = route_strip.build_route_hops(
            [0, 0, 0], [], [], "CURRENT", waypoint_manager=plan,
        )
        track = route_strip.build_route_track(
            [0, 0, 0], [], [], "CURRENT", waypoint_manager=plan,
        )

        self.assertEqual([hop["name"] for hop in hops], ["OLD EXPEDITION STOP"])
        self.assertEqual(truncated, 0)
        self.assertEqual(track["source"], "waypoints")

    def test_navigation_context_uses_recalculated_elite_next_jump(self):
        app = MainDashboard.__new__(MainDashboard)
        app.current_sys = "CURRENT"
        app.previous_sys = "PREVIOUS"
        app.previous_coords = [-10, 0, 0]
        app.current_coords = [0, 0, 0]
        app.route_list = ["CURRENT", "NEW NEXT", "NEW DESTINATION"]
        app.nav_route_entries = [
            {"StarSystem": "CURRENT", "StarPos": [0, 0, 0], "StarClass": "K"},
            {"StarSystem": "NEW NEXT", "StarPos": [10, 0, 0], "StarClass": "G"},
            {"StarSystem": "NEW DESTINATION", "StarPos": [20, 0, 0], "StarClass": "M"},
        ]
        app.waypoint_manager = _WaypointPlan()
        app.dest_name = "NEW DESTINATION"
        app.target_waypoint = None
        app.system_bio_signals = 0
        app.organic_count = 0
        app.system_undiscovered = False
        app.current_station_name = ""
        app.current_docked = False
        app._active_cargo_capacity = lambda: 0
        app._route_safety_snapshot = lambda: {}
        app._navigation_next_star_intelligence = lambda *_args: {}
        app._current_fuel_percent = lambda: None
        app._navigation_fsd_readiness_context = lambda: {}
        app._navigation_local_target_context = lambda _next: {}
        app._latest_hud_balance = lambda: 0
        app._navigation_on_carrier_deck = lambda: False
        app._navigation_region_context = lambda: {}
        app._navigation_hud_event_context = lambda: {}

        context = app._build_navigation_hud_context()

        self.assertEqual(context["route_mode"], "GAME ROUTE")
        self.assertEqual(context["next"], "NEW NEXT")
        self.assertEqual(context["route_remaining"], 2)
        self.assertEqual(context["route_track"]["source"], "game")
