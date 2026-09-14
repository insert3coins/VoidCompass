import unittest

from voidcompass.dashboard.dashboard import MainDashboard


class _EDSMStub:
    def __init__(self):
        self.snapshots = []

    def queue_cargo_snapshot(self, inventory, vessel="Ship"):
        self.snapshots.append((list(inventory or []), vessel))


def _dashboard():
    dashboard = MainDashboard.__new__(MainDashboard)
    dashboard.current_cargo_vessel = "Ship"
    dashboard.current_cargo_inventory = [{"Name": "gold", "Count": 12}]
    dashboard.current_cargo_tons = 12
    dashboard.cargo_capacity = 322
    dashboard.current_in_srv = False
    dashboard.current_in_fighter = False
    dashboard.current_vehicle_name = ""
    dashboard._last_surface_vehicle_name = "RHINO"
    dashboard._cargo_inventory_by_hold = {}
    dashboard.cargo_hud = None
    dashboard.specialist_engine = None
    dashboard.edsm = _EDSMStub()
    dashboard._refresh_html_workspace = lambda: None
    return dashboard


class CargoVesselHandoffTests(unittest.TestCase):
    def test_stale_srv_file_cannot_replace_active_ship_hold(self):
        dashboard = _dashboard()

        accepted = dashboard.update_cargo(
            [{"Name": "tantalum", "Count": 3}], vessel="SRV",
        )

        self.assertFalse(accepted)
        self.assertEqual(dashboard.current_cargo_vessel, "Ship")
        self.assertEqual(dashboard.current_cargo_inventory, [{"Name": "gold", "Count": 12}])
        self.assertEqual(dashboard.edsm.snapshots, [])

    def test_docking_restores_ship_manifest_after_rhino_snapshot(self):
        dashboard = _dashboard()
        dashboard.current_in_srv = True
        dashboard.current_vehicle_name = "RHINO"
        dashboard._refresh_cargo_consumers()

        self.assertEqual(dashboard.current_cargo_vessel, "SRV")
        dashboard.update_cargo(
            [{"Name": "tantalum", "Count": 7}], vessel="SRV",
        )
        self.assertEqual(dashboard.current_cargo_tons, 7)

        dashboard.current_in_srv = False
        dashboard.current_vehicle_name = ""
        dashboard._refresh_cargo_consumers()

        self.assertEqual(dashboard.current_cargo_vessel, "Ship")
        self.assertEqual(dashboard.current_cargo_inventory, [{"Name": "gold", "Count": 12}])
        self.assertEqual(dashboard.current_cargo_tons, 12)

if __name__ == "__main__":
    unittest.main()
