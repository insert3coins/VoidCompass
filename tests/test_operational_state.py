from datetime import datetime, timedelta, timezone
import unittest

from voidcompass.core import operational_state


class OperationalStateTests(unittest.TestCase):
    def test_activity_tracks_current_focused_modes_only(self):
        state = operational_state.fresh_runtime_state()
        operational_state.observe_event(state, "ProspectedAsteroid", {})
        self.assertEqual(state["activity"]["mode"], "mining")
        operational_state.observe_event(state, "MarketSell", {})
        self.assertEqual(state["activity"]["mode"], "mining")
        operational_state.observe_event(state, "FSDJump", {"StarSystem": "Beta"})
        self.assertEqual(state["activity"]["mode"], "exploration")
        operational_state.observe_event(state, "Docked", {})
        self.assertEqual(state["activity"]["mode"], "station")

    def test_ground_context_uses_journal_and_status(self):
        state = operational_state.fresh_runtime_state()
        operational_state.observe_event(state, "Disembark", {"Taxi": False})
        operational_state.observe_event(state, "SuitLoadout", {
            "SuitName_Localised": "Artemis Suit",
            "LoadoutName": "Survey",
            "Modules": [{"ModuleName_Localised": "Karma P-15", "Class": 2}],
        })
        operational_state.observe_event(state, "Backpack", {
            "Consumables": [
                {"Name_Localised": "Medkit", "Count": 2},
                {"Name_Localised": "Energy Cell", "Count": 1},
            ],
        })
        operational_state.observe_status(state, {
            "Flags2": 1, "Oxygen": 0.8, "Health": 0.65,
            "SelectedWeapon": {"Name_Localised": "Karma P-15"},
        })
        snapshot = operational_state.build_snapshot(state)
        ground = snapshot["ground_operations"]
        self.assertTrue(ground["on_foot"])
        self.assertEqual(ground["suit"], "Artemis Suit")
        self.assertEqual(ground["medkits"], 2)
        self.assertEqual(ground["energy_cells"], 1)
        self.assertEqual(ground["health_percent"], 65)

    def test_mission_context_tracks_deadlines_grouping_and_risk(self):
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=35)).isoformat()
        result = operational_state.mission_snapshot({
            "1": {"id": 1, "name": "Delivery", "destination_system": "Sol", "expiry": expiry},
            "2": {"id": 2, "name": "Covert delivery", "internal_name": "Mission_Covert",
                  "destination_system": "Sol", "destination_settlement": "Abraham Lincoln", "expiry": expiry},
        })
        self.assertEqual(result["active"], 2)
        self.assertEqual(result["grouped_destinations"][0], {"system": "Sol", "missions": 2})
        self.assertEqual(len(result["urgent"]), 2)
        self.assertEqual(result["illegal"], 1)
        self.assertEqual(result["ground"], 1)

    def test_expired_missions_are_removed_from_active_context(self):
        expired = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        result = operational_state.mission_snapshot({
            "1": {"id": 1, "name": "Expired", "destination_system": "Sol", "expiry": expired},
        })
        self.assertEqual(result["active"], 0)
        self.assertEqual(result["expired_count"], 1)
        self.assertEqual(result["by_system"], {})

    def test_mission_session_counts_are_retained(self):
        state = operational_state.fresh_runtime_state()
        operational_state.observe_event(state, "MissionCompleted", {"Reward": 250000})
        snapshot = operational_state.build_snapshot(
            state,
            companion_state={"missions": {}},
            current_system="Sol",
        )
        self.assertEqual(snapshot["missions"]["session"]["completed"], 1)
        self.assertEqual(snapshot["missions"]["session"]["rewards_cr"], 250000)
        self.assertEqual(snapshot["strategy"]["current_system"], "Sol")

    def test_carrier_strategy_uses_live_expedition_and_current_load(self):
        snapshot = operational_state.build_snapshot(
            operational_state.fresh_runtime_state(),
            carrier_data={
                "carrier_id": 3708973824,
                "name": "The Silent Flutter",
                "system": "Pru Euq GO-T b58-3",
                "fuel_level": 790,
                "fuel_capacity": 1000,
                "space_total": 25000,
                "space_free": 11035,
                "expedition_name": "Carrier Route",
                "expedition_route": [
                    {"system": "First", "visited": True, "distance_ly": 499.9},
                    {"system": "Second", "visited": True, "distance_ly": 499.9},
                    {"system": "Bleae Thua QQ-N b20-6", "visited": False,
                     "distance_ly": 499.966211748979, "fuel_used_t": 114},
                ],
            },
        )
        carrier = snapshot["strategy"]["carrier"]
        self.assertEqual(carrier["route_completed"], 2)
        self.assertEqual(carrier["route_total"], 3)
        self.assertEqual(carrier["route_remaining"], 1)
        self.assertEqual(carrier["space_used"], 13965)
        self.assertEqual(carrier["route_next"]["system"], "Bleae Thua QQ-N b20-6")
        self.assertEqual(carrier["route_next"]["calculated_fuel_t"], 104)
        self.assertEqual(carrier["route_next"]["projected_fuel_t"], 686)


if __name__ == "__main__":
    unittest.main()
