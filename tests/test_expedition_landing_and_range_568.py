"""5.6.8 expedition arrival and ship range regressions."""

import unittest
from unittest.mock import patch

from tests.test_expeditions_561 import Deck
from tests.test_hatchling_563 import HOUR, hatched
from voidcompass.core import hatchling
from voidcompass.exploration.waypoint_manager import WaypointManager


class ExpeditionLandingAndRangeTests(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()
        self.trip = self.deck.expedition_manager.create("Surface trip", start_system="Sol")
        self.eid = self.trip["id"]
        self.deck.expedition_manager.add_leg(self.eid, "Colonia", body="Colonia 4 a", lat=10, lon=20, radius=1_000_000)
        self.deck.expedition_manager.add_leg(self.eid, "Beagle Point")
        self.deck.waypoint_manager = WaypointManager(path=self.deck.expedition_manager.path + ".waypoints")

    def test_surface_route_stays_until_grounded_at_site(self):
        deck = self.deck
        leg = deck.expedition_manager.get(self.eid)["legs"][0]
        deck._expedition_use_route(self.eid, leg["id"])
        deck.current_sys, deck.current_body_name, deck.on_planet = "Colonia", "Colonia 4 a", True
        deck.current_latitude, deck.current_longitude, deck.current_planet_radius = 10, 20, 1_000_000
        deck.current_landed = deck.current_in_srv = deck.current_on_foot = False
        deck._expedition_on_position()
        self.assertEqual(deck.waypoint_manager.get_next_waypoint("Colonia"), "Colonia")
        self.assertFalse(deck.expedition_manager.get(self.eid)["legs"][0]["reached"])
        deck._expedition_position_at = 0
        deck.current_landed = True
        deck._expedition_on_position()
        self.assertTrue(deck.expedition_manager.get(self.eid)["legs"][0]["reached"])
        self.assertEqual(deck.waypoint_manager.get_next_waypoint("Colonia"), "Beagle Point")

    def test_both_plot_paths_use_restored_current_ship_range(self):
        deck = self.deck
        deck.companion_state["loadout"] = {}
        deck.cmdr_ship = {"max_jump_range": 47.35}
        deck._expedition_worker = lambda _name, work, done: done(work(), None)
        leg = deck.expedition_manager.get(self.eid)["legs"][0]
        with patch("voidcompass.services.spansh.neutron_route", return_value={"total_jumps": 1, "waypoints": [{"system": "Colonia"}]}) as route:
            self.assertTrue(deck._expedition_plot(self.eid, leg["id"], {}))
            self.assertEqual(route.call_args.args[2], 47.35)
            self.assertTrue(deck._expedition_route_to("Colonia", "Expedition: home"))
            self.assertEqual(route.call_args.args[2], 47.35)
        deck.companion_state["loadout"] = {"Provisional": True}
        self.assertEqual(deck._expedition_jump_range(), 0, "do not use the old ship while swapping")

    def test_existing_expedition_route_is_upgraded(self):
        deck = self.deck
        deck.waypoint_manager.waypoints = [
            {"name": "Colonia", "note": "Expedition: Surface trip"},
            {"name": "Beagle Point", "note": "Expedition: Surface trip"},
        ]
        deck._expedition_sync_route()
        self.assertEqual(deck.waypoint_manager.get_next_waypoint("Colonia"), "Colonia")
        self.assertEqual(deck.waypoint_manager.waypoints[0]["body"], "Colonia 4 a")

    def test_an_uncontrolled_touchdown_does_not_complete_a_leg(self):
        manager = self.deck.expedition_manager
        manager.observe_event({"event": "Touchdown", "StarSystem": "Colonia", "Body": "Colonia 4 a", "Latitude": 10, "Longitude": 20, "PlayerControlled": False}, event_uid="npc")
        self.assertFalse(manager.get(self.eid)["legs"][0]["reached"])

    def test_touchdown_away_from_the_site_does_not_complete_it(self):
        manager = self.deck.expedition_manager
        manager.observe_event({"event": "Touchdown", "StarSystem": "Colonia", "Body": "Colonia 4 a", "Latitude": 11, "Longitude": 20, "PlayerControlled": True}, event_uid="far")
        self.assertFalse(manager.get(self.eid)["legs"][0]["reached"])

    def test_already_landed_body_stop_is_recognised_from_status(self):
        manager = self.deck.expedition_manager
        leg = manager.get(self.eid)["legs"][0]
        manager.update_leg(self.eid, leg["id"], lat=None, lon=None)
        result = manager.visit_near("Colonia", "Colonia 4 a", 0, 0, 1_000_000, grounded=True)
        self.assertTrue(result["legs"])


class HatchlingJournalTests(unittest.TestCase):
    def test_honk_and_completed_biology_are_separate_cues(self):
        state = hatched("larva")
        now = 2 * HOUR
        hatchling.observe(state, {"event": "FSSDiscoveryScan"}, now)
        self.assertEqual(state["pet"]["cue"]["kind"], "honk")
        hatchling.observe(state, {"event": "ScanOrganic", "ScanType": "Sample"}, now + 30)
        self.assertEqual(state["pet"]["cue"]["kind"], "honk")
        hatchling.observe(state, {"event": "ScanOrganic", "ScanType": "Analyse"}, now + 60)
        self.assertEqual(state["pet"]["cue"]["kind"], "biology")


if __name__ == "__main__":
    unittest.main()
