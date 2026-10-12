from pathlib import Path
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
    def test_rhino_learns_the_mothership_hold_from_the_journal(self):
        """Started out in the Rhino: Cargo.json never describes the ship, but
        the journal's Cargo event does, so the mothership card still shows."""
        dashboard = _dashboard()
        dashboard._cargo_inventory_by_hold = {}
        dashboard.current_cargo_vessel = "SRV"
        dashboard.current_cargo_inventory = []
        dashboard.current_in_srv = True
        dashboard.current_vehicle_name = "RHINO"
        self.assertEqual(dashboard._rhino_related_cargo_holds(), [])

        learned = dashboard._remember_ship_hold_from_journal({
            "event": "Cargo", "Vessel": "Ship", "Count": 40,
            "Inventory": [{"Name": "platinum", "Count": 40}],
        })
        self.assertTrue(learned)
        dashboard._apply_rhino_cargo_transfer({"event": "CargoTransfer", "Transfers": [
            {"Type": "platinum", "Count": 51, "Direction": "toship"}]})
        related = dashboard._rhino_related_cargo_holds()
        self.assertEqual(related[0]["inventory"], [{"Name": "platinum", "Count": 91}])
        self.assertEqual(related[0]["capacity"], 322)

    def test_journal_never_replaces_the_active_ship_hold(self):
        dashboard = _dashboard()
        self.assertFalse(dashboard._remember_ship_hold_from_journal({
            "event": "Cargo", "Vessel": "Ship", "Inventory": [{"Name": "gold", "Count": 1}]}))
        self.assertFalse(dashboard._remember_ship_hold_from_journal({"event": "Cargo", "Vessel": "Ship", "Count": 3}))
        self.assertEqual(dashboard.current_cargo_inventory, [{"Name": "gold", "Count": 12}])

    def test_mothership_card_shows_space_left(self):
        script = (Path(__file__).resolve().parents[1] / "web" / "cargo" / "app.js").read_text(encoding="utf-8")
        self.assertIn("T FREE", script)
        self.assertIn("related-meter", script)
    def test_unloaded_tonnes_are_not_passed_off_as_the_whole_hold(self):
        dashboard = _dashboard()
        dashboard._cargo_inventory_by_hold = {}
        dashboard.current_cargo_vessel = "SRV"
        dashboard.current_cargo_inventory = []
        dashboard.current_in_srv = True
        dashboard.current_vehicle_name = "RHINO"
        dashboard._apply_rhino_cargo_transfer({"event": "CargoTransfer", "Transfers": [
            {"Type": "platinum", "Count": 51, "Direction": "toship"}]})
        self.assertIn("BOARD SHIP", dashboard._rhino_related_cargo_holds()[0]["status"])
        self.assertTrue(dashboard._rhino_related_cargo_holds()[0]["partial"], "no free space guessed")
        dashboard._remember_ship_hold_from_journal({
            "event": "Cargo", "Vessel": "Ship", "Inventory": [{"Name": "platinum", "Count": 765}]})
        self.assertEqual(dashboard._rhino_related_cargo_holds()[0]["status"], "REMOTE / RETAINED")

    def test_capacity_found_in_an_earlier_journal(self):
        import json
        import tempfile
        from voidcompass.core.journal_watcher import JournalWatcher
        with tempfile.TemporaryDirectory() as folder:
            older = Path(folder) / "Journal.2026-10-09T200900.01.log"
            newer = Path(folder) / "Journal.2026-10-10T090500.01.log"
            older.write_text(json.dumps({"event": "Loadout", "Ship": "panthermkii", "CargoCapacity": 832}) + "\n", encoding="utf-8")
            newer.write_text(json.dumps({"event": "LoadGame", "Ship": "mev_rhino"}) + "\n", encoding="utf-8")
            watcher = JournalWatcher.__new__(JournalWatcher)
            watcher.journal_path = folder
            self.assertEqual(watcher.get_latest_cargo_capacity(), 832)

    def test_rhino_launch_keeps_the_ship_hold_on_disk(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        launch = source.split("def _apply_surface_vehicle_launch", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("_save_profile_cockpit_state()", launch)
        self.assertIn('"_ship_hold_partial"', source)
        self.assertIn("get_latest_cargo_capacity() or self.cargo_capacity", source)

if __name__ == "__main__":
    unittest.main()
