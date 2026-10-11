"""The Galaxy Minimap's Spansh trip (5.5.3.7): the whole trip beyond the leg
plotted in game, from the waypoint route or the latest neutron plot."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays.galaxy_minimap_hud import (
    GalaxyMinimapHUD, TRIP_POINTS, build_minimap_model, minimap_options, spansh_trip,
)
from voidcompass.services import spansh

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def plot(count=5, start=0):
    """A neutron plot: Start, then neutron stars every 500 ly up the z axis."""
    return {"total_jumps": count * 2, "waypoints": [
        {"system": "Start" if i == 0 else f"Neutron {i}", "coords": [0.0, 0.0, 500.0 * i],
         "neutron": i > 0, "jumps": 0 if i == 0 else 2} for i in range(start, count + 1)]}


class TripTests(unittest.TestCase):
    def test_the_neutron_plot_ahead_of_you(self):
        trip = spansh_trip([], plot(), [0, 0, 0], "Start")
        self.assertEqual(trip["points"], [[0.0, 500.0], [0.0, 1000.0], [0.0, 1500.0], [0.0, 2000.0], [0.0, 2500.0]])
        self.assertEqual((trip["neutron"], trip["name"], trip["distance"], trip["jumps"], trip["source"]),
                         ([0, 1, 2, 3, 4], "Neutron 5", 2500.0, 10, "neutron"))

    def test_further_along_it_counts_only_whats_left(self):
        trip = spansh_trip([], plot(), [0, 0, 1500], "Neutron 3")
        self.assertEqual((len(trip["points"]), trip["distance"], trip["jumps"]), (2, 1000.0, 4))
        self.assertIsNone(spansh_trip([], plot(), [0, 0, 2500], "Neutron 5"), "arrived: no trip ahead")

    def test_the_waypoint_route_comes_first(self):
        waypoints = [{"name": "Start", "coords": [0, 0, 0]}, {"name": "Colonia", "coords": [-9530.5, -910.3, 19808.1]},
                     {"name": "Beagle Point", "coords": {"x": -1111.6, "y": -134.2, "z": 65269.8}}]
        trip = spansh_trip(waypoints, plot(), [0, 0, 0], "Somewhere else")
        self.assertEqual((trip["source"], trip["name"], trip["stops"], trip["jumps"]), ("waypoints", "Beagle Point", 3, 3))
        self.assertEqual(trip["points"][0], [0.0, 0.0], "not on the route: from its first stop")

    def test_the_visited_ones_are_behind_you(self):
        waypoints = [{"name": f"W{i}", "coords": [0, 0, 100 * i], "visited": i < 2} for i in range(4)]
        trip = spansh_trip(waypoints, None, [0, 0, 150], "Between")
        self.assertEqual(trip["points"], [[0.0, 200.0], [0.0, 300.0]])

    def test_imported_waypoints_without_coordinates_borrow_the_plots(self):
        # Imported before 5.5.3.7 (no coordinates): the plot still knows them.
        waypoints = [{"name": row["system"], "coords": None, "note": "Spansh neutron route"} for row in plot()["waypoints"]]
        trip = spansh_trip(waypoints, plot(), [0, 0, 0], "Start")
        self.assertEqual((trip["source"], len(trip["points"]), trip["neutron"]), ("waypoints", 5, [0, 1, 2, 3, 4]))
        self.assertIsNone(spansh_trip(waypoints, None, [0, 0, 0], "Start"), "nowhere known: nothing drawn")

    def test_nothing_without_a_route(self):
        self.assertIsNone(spansh_trip([], None))
        self.assertIsNone(spansh_trip([{"name": "Only", "coords": [0, 0, 0]}], None))

    def test_a_very_long_trip_is_thinned_but_keeps_its_neutron_stars(self):
        rows = [{"system": f"S{i}", "coords": [0, 0, 10.0 * i], "neutron": i % 1000 == 7, "jumps": 1}
                for i in range(TRIP_POINTS * 3)]
        trip = spansh_trip([], {"waypoints": rows}, [0, 0, 0], "S0")
        self.assertLessEqual(len(trip["points"]), TRIP_POINTS + 10)
        self.assertEqual(len(trip["neutron"]), 5)
        self.assertEqual(trip["points"][-1], [0.0, 10.0 * (TRIP_POINTS * 3 - 1)], "its end always")
        self.assertEqual(trip["jumps"], TRIP_POINTS * 3 - 1)

    def test_it_can_be_turned_off(self):
        trip = spansh_trip([], plot(), [0, 0, 0], "Start")
        self.assertTrue(minimap_options({})["spansh"])
        self.assertIs(build_minimap_model([], [0, 0, 0], "Start", trip=trip)["trip"], trip)
        options = minimap_options({"galaxy_minimap_spansh": False})
        self.assertIsNone(build_minimap_model([], [0, 0, 0], "Start", options=options, trip=trip)["trip"])

    def test_the_hud_redraws_when_the_trip_changes(self):
        hud = GalaxyMinimapHUD.__new__(GalaxyMinimapHUD)
        hud.config, hud._signature, hud._region_cache = {}, None, {}
        self.assertTrue(hud.update([], [], 1, [0, 0, 0], "Start", [], spansh_trip([], plot(), [0, 0, 0], "Start")))
        self.assertFalse(hud.update([], [], 1, [0, 0, 0], "Start", [], spansh_trip([], plot(), [0, 0, 0], "Start")))
        self.assertTrue(hud.update([], [], 1, [0, 0, 0], "Start", [], None))
        self.assertIsNone(hud._html_render_model["trip"])


class SourceTests(unittest.TestCase):
    def test_spansh_coordinates_are_kept(self):
        reply = {"total_jumps": 3, "system_jumps": [
            {"system": "Sol", "x": 0, "y": 0, "z": 0, "jumps": 0, "neutron_star": False},
            {"system": "Jackson's Lighthouse", "x": 157.0, "y": -27.0, "z": -70.0, "jumps": 3, "neutron_star": True},
            {"system": "Odd", "jumps": 1, "neutron_star": False}]}
        with patch.object(spansh, "submit_and_poll", return_value=reply):
            route = spansh.neutron_route("Sol", "Jackson's Lighthouse", 60)
        self.assertEqual([row["coords"] for row in route["waypoints"]], [[0.0, 0.0, 0.0], [157.0, -27.0, -70.0], None])

    def test_the_deck_gives_the_minimap_this_commanders_trip(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = {}
        deck.waypoint_manager = type("Manager", (), {"waypoints": []})()
        profile = config_module.get_active_profile(deck.config)
        deck._html_explore_tool_state = {"profile": profile, "route": plot()}
        self.assertEqual(deck._galaxy_minimap_trip([0, 0, 0], "Start")["source"], "neutron")
        deck._html_explore_tool_state = {"profile": "someone else", "route": plot()}
        self.assertIsNone(deck._galaxy_minimap_trip([0, 0, 0], "Start"), "another commander's plot isn't yours")
        deck.waypoint_manager.waypoints = [{"name": "A", "coords": [0, 0, 0]}, {"name": "B", "coords": [0, 0, 900]}]
        self.assertEqual(deck._galaxy_minimap_trip([0, 0, 0], "A")["source"], "waypoints")

    def test_import_keeps_the_coordinates(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_explore_workspace.py").read_text(encoding="utf-8")
        self.assertIn('"coords": row.get("coords"), "note": "Spansh neutron route"', source)
        self.assertIn('"neutron": bool(row.get("neutron"))', source)

    def test_a_studio_switch_that_follows_the_commander(self):
        self.assertIn("galaxy_minimap_spansh", config_module.PROFILE_SETTINGS)
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-overlay-option="galaxy_minimap_spansh"', html)
        studio = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn('"galaxy_minimap_spansh": galaxy_minimap_hud.minimap_options(self.config)["spansh"]', studio)


if __name__ == "__main__":
    unittest.main()
