import unittest

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.overlays.hud import TacticalHUD


class NavigationIndicatorStateTests(unittest.TestCase):
    @staticmethod
    def _state(context):
        return TacticalHUD._state_text(TacticalHUD.__new__(TacticalHUD), context)

    def test_status_file_decodes_navigation_and_surface_control_flags(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.config = {
            "ground_target_lat": 0,
            "ground_target_lon": 0,
            "ground_target_active": False,
            "ground_popup_enabled": False,
        }
        dashboard._reset_profile_runtime_state("Commander", "F1")
        dashboard.batch_mode = True
        dashboard.heartbeat_hud = None
        dashboard.mining_window = None
        dashboard._perf_spike = lambda *_args, **_kwargs: None

        flags = (
            dashboard._STATUS_SHIELDS_UP
            | dashboard._STATUS_FLIGHT_ASSIST_OFF
            | dashboard._STATUS_HARDPOINTS_DEPLOYED
            | dashboard._STATUS_SILENT_RUNNING
            | dashboard._STATUS_SRV_HANDBRAKE
            | dashboard._STATUS_SRV_TURRET
            | dashboard._STATUS_SRV_DRIVE_ASSIST
            | dashboard._STATUS_LOW_FUEL
            | dashboard._STATUS_OVERHEATING
            | dashboard._STATUS_NIGHT_VISION
            | dashboard._STATUS_IN_MAIN_SHIP
        )
        flags2 = (
            dashboard._STATUS2_SUPERCRUISE_ASSIST
            | dashboard._STATUS2_LOW_OXYGEN
            | dashboard._STATUS2_LOW_HEALTH
            | dashboard._STATUS2_VERY_COLD
        )
        dashboard._apply_status_update({"Flags": flags, "Flags2": flags2})

        self.assertTrue(dashboard.current_shields_up)
        self.assertTrue(dashboard.current_flight_assist_off)
        self.assertTrue(dashboard.current_hardpoints_deployed)
        self.assertTrue(dashboard.current_silent_running)
        self.assertTrue(dashboard.current_srv_handbrake)
        self.assertTrue(dashboard.current_srv_turret)
        self.assertTrue(dashboard.current_srv_drive_assist)
        self.assertTrue(dashboard.current_low_fuel)
        self.assertTrue(dashboard.current_overheating)
        self.assertTrue(dashboard.current_night_vision)
        self.assertTrue(dashboard.current_in_main_ship)
        self.assertTrue(dashboard.current_supercruise_assist)
        self.assertTrue(dashboard.current_suit_low_oxygen)
        self.assertTrue(dashboard.current_suit_low_health)
        self.assertTrue(dashboard.current_suit_very_cold)

    def test_authoritative_states_have_useful_precedence(self):
        self.assertEqual(self._state({
            "flight_state": "SUPERCRUISE",
            "ship_config": {"supercruise_assist": True},
        }), "SC ASSIST")
        self.assertEqual(self._state({
            "flight_state": "FLIGHT",
            "ship_config": {"overheating": True, "flight_assist_off": True},
        }), "HEAT CRITICAL")
        self.assertEqual(self._state({
            "flight_state": "ONFOOT", "on_foot": True,
            "suit_status": {"low_oxygen": True, "very_hot": True},
        }), "SUIT OXYGEN LOW")
        self.assertEqual(self._state({
            "flight_state": "NOMAD", "in_srv": True,
            "vehicle_name": "NOMAD",
            "ship_config": {"srv_handbrake": True},
        }), "HANDBRAKE")
        self.assertEqual(self._state({
            "flight_state": "FLIGHT",
            "music_mode": "EXPLORATION",
            "fsd_readiness": {
                "state": "station_vicinity", "mass_locked": True,
                "local_space_type": "Station", "local_space_name": "Jaques Station",
            },
        }), "STATION VICINITY")

    def test_station_drop_owns_mass_lock_navigation_context(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard._capture_navigation_local_space({
            "Body": "Jaques Station", "BodyType": "Station",
        })
        dashboard.current_fsd_mass_locked = True

        context = dashboard._navigation_fsd_readiness_context()
        self.assertEqual(context["state"], "station_vicinity")
        self.assertEqual(context["label"], "STATION VICINITY")
        self.assertTrue(context["station_vicinity"])
        self.assertEqual(context["local_space_name"], "Jaques Station")

        dashboard._clear_navigation_local_space()
        context = dashboard._navigation_fsd_readiness_context()
        self.assertEqual(context["state"], "mass_lock")

    def test_docking_clearance_latches_pad_until_resolved(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard._navigation_docking_state = None
        dashboard._observe_navigation_docking_state(
            "DockingGranted", {"StationName": "Explorer's Anchorage", "LandingPad": 7}, {},
        )
        self.assertEqual(dashboard._navigation_docking_state["label"], "PAD 07 CLEARED")
        self.assertEqual(self._state({
            "flight_state": "FLIGHT",
            "docking_state": dashboard._navigation_docking_state,
        }), "PAD 07 CLEARED")

        dashboard._observe_navigation_docking_state("Docked", {}, {})
        self.assertIsNone(dashboard._navigation_docking_state)

    def test_new_states_use_distinct_motion_families(self):
        expected = {
            "SC ASSIST": "supercruise_assist",
            "FLIGHT ASSIST OFF": "flight_assist_off",
            "SILENT RUNNING": "silent_running",
            "HEAT CRITICAL": "heat_critical",
            "SUIT OXYGEN LOW": "suit_hazard",
            "HANDBRAKE": "srv_handbrake",
            "TURRET VIEW": "srv_turret",
            "DRIVE ASSIST": "srv_drive_assist",
            "PAD 07 CLEARED": "docking_clearance",
            "AFMU REPAIR": "maintenance",
            "SYSTEM REBOOT": "system_reboot",
            "JET CONE DAMAGE": "jet_cone_damage",
            "STATION VICINITY": "station",
        }
        for label, motion in expected.items():
            self.assertEqual(TacticalHUD._navigation_motion_profile(label), motion)


if __name__ == "__main__":
    unittest.main()
