"""Nomad launch evidence in the newer LaunchVessel journal event."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from voidcompass.core.journal_watcher import JournalWatcher
from voidcompass.dashboard.dashboard import MainDashboard


NOMAD_LAUNCH = {
    "event": "LaunchVessel",
    "VesselType": "lander01",
    "VesselType_Localised": "Nomad",
    "Loadout": "galactic",
    "PlayerControlled": True,
}


class NomadVesselIdentityTests(unittest.TestCase):
    def test_launch_vessel_identity_is_available_during_startup_recovery(self):
        self.assertEqual(
            JournalWatcher._surface_vehicle_identity(NOMAD_LAUNCH),
            {"name": "NOMAD", "id": None},
        )
        self.assertIsNone(JournalWatcher._surface_vehicle_identity({
            **NOMAD_LAUNCH, "PlayerControlled": False,
        }))

        with TemporaryDirectory() as folder:
            journal = Path(folder) / "Journal.test.log"
            journal.write_text(json.dumps(NOMAD_LAUNCH) + "\n", encoding="utf-8")
            watcher = JournalWatcher(folder)
            watcher.last_journal = str(journal)
            watcher._seed_startup_location()
            self.assertEqual(
                watcher.get_startup_surface_vehicle_identity(),
                {"name": "NOMAD", "id": None},
            )

    def test_live_launch_vessel_assigns_nomad_to_navigation_hud(self):
        app = MainDashboard.__new__(MainDashboard)
        app.current_in_fighter = False
        app.current_in_srv = False
        app.current_on_foot = False
        app.current_in_taxi = False
        app.current_in_multicrew = False
        app.current_vehicle_id = None
        app.current_vehicle_name = ""
        app.current_surface_fuel_reservoir = 0.5
        app._vehicle_name_by_id = {}
        app._last_surface_vehicle_name = ""
        app.hud_flight_state = "FLIGHT"
        app._clear_navigation_vehicle_handoff = lambda: None
        published = []
        app.update_hud = lambda: published.append(app.hud_flight_state)
        app._refresh_cargo_consumers = lambda: None

        self.assertEqual(app._srv_toast_vehicle_name(NOMAD_LAUNCH, NOMAD_LAUNCH), "NOMAD")
        self.assertEqual(
            app._navigation_vehicle_transition_label("LaunchVessel", NOMAD_LAUNCH, NOMAD_LAUNCH),
            "NOMAD DEPLOY",
        )
        app._apply_surface_vehicle_launch(NOMAD_LAUNCH, NOMAD_LAUNCH)

        self.assertTrue(app.current_in_srv)
        self.assertFalse(app.current_in_fighter)
        self.assertEqual(app.current_vehicle_name, "NOMAD")
        self.assertEqual(app.hud_flight_state, "NOMAD")
        self.assertIsNone(app.current_vehicle_id)
        self.assertIsNone(app.current_surface_fuel_reservoir)
        self.assertEqual(published, ["NOMAD"])


if __name__ == "__main__":
    unittest.main()
