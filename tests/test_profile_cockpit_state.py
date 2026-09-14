import json
import os
import tempfile
import unittest

from voidcompass.dashboard.dashboard import MainDashboard


class ProfileCockpitStateTests(unittest.TestCase):
    @staticmethod
    def _dashboard(path, profile="cmdr_alpha"):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.config = {
            "active_commander_profile": profile,
            "active_commander_name": "Alpha",
            "active_commander_fid": "F123",
        }
        dashboard.cmdr_name = "Alpha"
        dashboard.cmdr_fid = "F123"
        dashboard._startup_restore_active = False
        dashboard._profile_path = lambda _filename: path
        dashboard.current_sys = "Test System"
        dashboard.current_coords = [1.0, 2.0, 3.0]
        dashboard.previous_coords = [0.0, 0.0, 0.0]
        dashboard.dest_coords = [4.0, 5.0, 6.0]
        dashboard.body_signals = {7: {"bio_count": 2}}
        dashboard.current_docked = True
        dashboard.current_station_name = "Test Port"
        dashboard.route_list = ["Test System", "Next System"]
        dashboard.current_cargo_inventory = [{"Name": "gold", "Count": 4}]
        return dashboard

    def test_shutdown_snapshot_round_trip_is_profile_aware(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "last_cockpit_state.json")
            source = self._dashboard(path)
            self.assertTrue(source._save_profile_cockpit_state())
            with open(path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)["state"]
            self.assertNotIn("route_list", saved)
            self.assertEqual(saved["nav_route_entries"][-1]["StarSystem"], "Next System")

            restored = self._dashboard(path)
            restored.current_sys = "---"
            restored.current_station_name = None
            restored.route_list = []
            restored.body_signals = {}
            self.assertTrue(restored._load_profile_cockpit_state())
            self.assertEqual(restored.current_sys, "Test System")
            self.assertEqual(restored.current_station_name, "Test Port")
            self.assertEqual(restored.route_list[-1], "Next System")
            self.assertIn(7, restored.body_signals)

            wrong_profile = self._dashboard(path, profile="cmdr_beta")
            wrong_profile.current_sys = "---"
            self.assertFalse(wrong_profile._load_profile_cockpit_state())
            self.assertEqual(wrong_profile.current_sys, "---")

    def test_shutdown_during_catchup_keeps_known_good_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "last_cockpit_state.json")
            dashboard = self._dashboard(path)
            self.assertTrue(dashboard._save_profile_cockpit_state())
            with open(path, "r", encoding="utf-8") as handle:
                original = json.load(handle)

            dashboard.current_sys = "Partially Replayed System"
            dashboard._startup_restore_active = True
            self.assertFalse(dashboard._save_profile_cockpit_state())
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), original)

    def test_schema_one_route_names_migrate_to_canonical_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "last_cockpit_state.json")
            dashboard = self._dashboard(path)
            payload = {
                "schema": dashboard._COCKPIT_STATE_SCHEMA,
                "profile_key": "cmdr_alpha",
                "fid": "F123",
                "state": {
                    "current_sys": "Sol", "route_list": ["Sol", "Achenar"],
                    "scan_total_confirmed": False,
                },
            }
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            dashboard.nav_route_entries = []
            self.assertTrue(dashboard._load_profile_cockpit_state())
            self.assertEqual(dashboard.route_list, ["Sol", "Achenar"])
            self.assertEqual(
                dashboard.nav_route_entries,
                [{"StarSystem": "Sol"}, {"StarSystem": "Achenar"}],
            )


if __name__ == "__main__":
    unittest.main()
