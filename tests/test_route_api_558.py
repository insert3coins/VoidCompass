"""5.5.8: Explore & Survey's ROUTE tab through the Local API. Waypoints are
added, changed, moved, removed and cleared, return-later places become
waypoints or are put aside, and a plotted neutron route is imported, all
through the tab's own handler (run here for real, on files in a temp folder)."""

import json
from pathlib import Path
import tempfile
import threading
import unittest

from voidcompass.dashboard.dashboard_api_records_mixin import ApiRecordsMixin
from voidcompass.dashboard.html_explore_workspace import HtmlExploreWorkspaceMixin
from voidcompass.exploration.return_later import write_state as write_return_later
from voidcompass.exploration.waypoint_manager import WaypointManager
from voidcompass.services.local_api import ApiError, LocalApi

from tests.test_local_api_557 import ServerCase


class Deck(HtmlExploreWorkspaceMixin, ApiRecordsMixin):
    """Just enough of the app for the ROUTE tab."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.config = {}
        self.current_sys = "Colonia"
        self.current_coords = [-9530.5, -910.28, 19808.13]
        self.waypoint_manager = WaypointManager(str(self.folder / "waypoints.json"))
        self._return_later_lock = threading.RLock()
        self._transient = {}
        self.published = 0

    def _profile_path(self, name):
        return str(self.folder / name)

    def _html_profile_transient(self, name, default):
        return self._transient.setdefault(name, default)

    def _schedule_html_dashboard_publish(self, immediate=False):
        self.published += 1

    def update_hud(self):
        pass

    def _html_copy_text(self, text):
        self.copied = text
        return True


class RouteProviderTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.deck = Deck(folder.name)

    def names(self):
        return [row["name"] for row in self.deck.api_route()["waypoints"]]

    def test_add_change_move_and_remove(self):
        self.deck.api_add_waypoint("Sol", "home")
        self.deck.api_add_waypoint("Colonia", "")
        self.deck.api_add_waypoint("Sagittarius A*", "the middle")
        self.assertEqual(self.names(), ["Sol", "Colonia", "Sagittarius A*"])
        self.assertEqual(self.deck.api_route()["waypoints"][1]["coords"], [-9530.5, -910.28, 19808.13],
                         "the system you're in takes its position from the game")
        rows = self.deck.api_change_waypoint(0, {"visited": True})["waypoints"]
        self.assertEqual((rows[0]["visited"], rows[0]["note"]), (True, "home"), "marking keeps the note")
        rows = self.deck.api_change_waypoint(2, {"name": "Sgr A*"})["waypoints"]
        self.assertEqual((rows[2]["name"], rows[2]["note"]), ("Sgr A*", "the middle"), "renaming keeps the note")
        self.deck.api_change_waypoint(2, {"move": "up"})
        self.assertEqual(self.names(), ["Sol", "Sgr A*", "Colonia"])
        self.assertEqual(self.deck.api_delete_waypoint(0)["removed"], "Sol")
        self.assertEqual(self.names(), ["Sgr A*", "Colonia"])
        saved = json.loads((self.deck.folder / "waypoints.json").read_text(encoding="utf-8"))
        self.assertEqual([row["name"] for row in saved], ["Sgr A*", "Colonia"], "saved like the tab saves them")
        self.assertGreater(self.deck.published, 0, "the deck follows at once")
        with self.assertRaises(ApiError) as caught:
            self.deck.api_change_waypoint(9, {"visited": True})
        self.assertEqual(caught.exception.status, 404)
        self.deck.api_clear_waypoints()
        self.assertEqual(self.names(), [])

    def test_return_later_places(self):
        write_return_later(str(self.deck.folder / "return_later.json"), {"version": 1, "dismissed": [], "entries": [
            {"id": "colonia|body:7", "system": "Colonia", "body": "Colonia 4 a", "reasons": ["2 organics left"],
             "coords": [-9530.5, -910.28, 19808.13]},
            {"id": "sol|fss", "system": "Sol", "body": "", "reasons": ["Not fully scanned"], "coords": [0, 0, 0]}]})
        places = self.deck.api_return_later()["places"]
        self.assertEqual({row["id"] for row in places}, {"colonia|body:7", "sol|fss"})  # in the board's own order
        added = self.deck.api_return_later_action("waypoint", "colonia|body:7")["waypoints"]
        self.assertEqual(added[0]["name"], "Colonia")
        self.assertIn("2 organics left", added[0]["note"])
        self.deck.api_return_later_action("dismiss", "sol|fss")
        self.assertEqual([row["id"] for row in self.deck.api_return_later()["places"]], ["colonia|body:7"])
        with self.assertRaises(ApiError) as caught:
            self.deck.api_return_later_action("waypoint", "nowhere")
        self.assertEqual(caught.exception.status, 404)

    def test_the_neutron_route(self):
        with self.assertRaises(ApiError) as caught:
            self.deck.api_import_neutron_route()
        self.assertEqual(caught.exception.status, 409, "nothing plotted yet")
        self.deck.api_add_waypoint("Colonia", "")
        self.deck._transient["_html_explore_tool_state"] = {"status": "ready", "route": {"waypoints": [
            {"system": "Colonia", "coords": [1, 2, 3], "neutron": False, "jumps": 0},
            {"system": "Hypoe Flyi HW-W e1-7966", "coords": [4, 5, 6], "neutron": True, "jumps": 1},
            {"system": "Sagittarius A*", "coords": [7, 8, 9], "neutron": False, "jumps": 2}]}}
        self.assertEqual(len(self.deck.api_neutron_route()["route"]["waypoints"]), 3)
        result = self.deck.api_import_neutron_route()
        self.assertEqual(result["imported"], 2, "Colonia was there already")
        self.assertEqual([(row["name"], row.get("neutron")) for row in result["waypoints"]][1:],
                         [("Hypoe Flyi HW-W e1-7966", True), ("Sagittarius A*", False)])


class RouteServerTests(ServerCase):
    def setUp(self):
        super().setUp()
        self.asked = []
        for name in ("api_add_waypoint", "api_change_waypoint", "api_delete_waypoint", "api_clear_waypoints",
                     "api_return_later_action"):
            setattr(self.provider, name, lambda *args, _name=name: self.asked.append((_name, *args)) or {})

    def test_what_each_takes(self):
        self.assertEqual(self.call("/route/waypoints", "POST", {"note": "no name"})[0], 400)
        self.assertEqual(self.call("/route/waypoints", "POST", {"name": " Colonia ", "note": "Jaques"})[0], 200)
        self.assertEqual(self.call("/route/waypoints/3", "POST", {})[0], 400)
        self.assertEqual(self.call("/route/waypoints/3", "POST", {"move": "sideways"})[0], 400)
        self.assertEqual(self.call("/route/waypoints/3", "POST", {"visited": True, "move": "down"})[0], 200)
        self.assertEqual(self.call("/route/waypoints/3/delete", "POST")[0], 200)
        self.assertEqual(self.call("/route/waypoints/clear", "POST", {})[0], 400, "clearing needs confirming")
        self.assertEqual(self.call("/route/waypoints/clear", "POST", {"confirmed": True})[0], 200)
        self.assertEqual(self.call("/route/return-later/waypoint", "POST", {})[0], 400)
        self.assertEqual(self.call("/route/return-later/dismiss", "POST", {"id": "sol|fss"})[0], 200)
        self.assertEqual(self.asked, [
            ("api_add_waypoint", "Colonia", "Jaques"), ("api_change_waypoint", 3, {"visited": True, "move": "down"}),
            ("api_delete_waypoint", 3), ("api_clear_waypoints",), ("api_return_later_action", "dismiss", "sol|fss")])

    def test_read_only_keeps_the_route_as_it_is(self):
        self.api.configure(enabled=True, port=self.port, allow_control=False)
        for path, body in (("/route/waypoints", {"name": "x"}), ("/route/waypoints/0", {"visited": True}),
                           ("/route/waypoints/0/delete", None), ("/route/waypoints/clear", {"confirmed": True}),
                           ("/route/neutron/import", None)):
            self.assertEqual(self.call(path, "POST", body)[0], 403, path)
        self.assertEqual(self.asked, [])

    def test_on_the_index(self):
        paths = {(row["method"], row["path"]) for row in LocalApi(object()).endpoints()}
        for method, path in (("POST", "route/waypoints"), ("POST", "route/waypoints/{n}"),
                             ("POST", "route/waypoints/{n}/delete"), ("POST", "route/waypoints/clear"),
                             ("GET", "route/return-later"), ("GET", "route/neutron"), ("POST", "route/neutron/import")):
            self.assertIn((method, f"/api/v1/{path}"), paths)


if __name__ == "__main__":
    unittest.main()
