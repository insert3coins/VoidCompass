"""5.6.4: completing, failing or deleting an expedition takes its waypoints
off the route, so the Galaxy Minimap and the HUD stop showing the trip."""

import unittest

from tests.test_expeditions_561 import Deck


class Waypoints:
    def __init__(self, rows):
        self.waypoints = rows
        self.saved = 0

    def save(self):
        self.saved += 1


class EndedTripTests(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()
        self.manager = self.deck.expedition_manager
        self.trip = self.manager.create("Colonia run", start_system="Sol", destination="Colonia")
        self.manager.set_status(self.trip["id"], "active")
        self.deck.minimap_redrawn = 0
        self.deck._update_galaxy_minimap_safely = lambda: setattr(self.deck, "minimap_redrawn", self.deck.minimap_redrawn + 1)
        self.deck.waypoint_manager = Waypoints([
            {"name": "Eol Prou RS-T d3-94", "note": "Expedition: Colonia run"},
            {"name": "Colonia", "note": "Expedition: Colonia run"},
            {"name": "Shinrarta Dezhra", "note": "Expedition: to sell"},
            {"name": "Maia", "note": "My own stop"},
        ])

    def names(self):
        return [row["name"] for row in self.deck.waypoint_manager.waypoints]

    def test_completing_the_trip_clears_its_route(self):
        self.assertTrue(self.deck._handle_expedition_command("status", {"expedition_id": self.trip["id"], "status": "completed"}))
        self.assertEqual(self.manager.get(self.trip["id"])["status"], "completed")
        self.assertEqual(self.names(), ["Maia"], "your own waypoints stay")
        self.assertEqual(self.deck.minimap_redrawn, 1)

    def test_deleting_it_does_too_but_only_when_confirmed(self):
        self.assertIsNone(self.deck._handle_expedition_command("delete", {"expedition_id": self.trip["id"]}))
        self.assertEqual(len(self.names()), 4)
        self.assertTrue(self.deck._handle_expedition_command("delete", {"expedition_id": self.trip["id"], "confirmed": True}))
        self.assertIsNone(self.manager.get(self.trip["id"]))
        self.assertEqual(self.names(), ["Maia"])

    def test_a_paused_trip_only_takes_its_own_legs(self):
        self.manager.set_status(self.trip["id"], "paused")
        self.deck._handle_expedition_command("status", {"expedition_id": self.trip["id"], "status": "failed"})
        self.assertEqual(self.names(), ["Shinrarta Dezhra", "Maia"])

    def test_pausing_leaves_the_route_alone(self):
        self.assertIsNone(self.deck._handle_expedition_command("status", {"expedition_id": self.trip["id"], "status": "paused"}))
        self.assertEqual(len(self.names()), 4)


if __name__ == "__main__":
    unittest.main()
