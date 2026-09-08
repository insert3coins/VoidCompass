import json
import os
import sqlite3
import tempfile
import threading
import unittest
from collections import deque

from captains_log import CaptainsLog
from carrier_tracker import CarrierTracker
from dashboard import MainDashboard
from edsm_handler import EDSMHandler
from journal_watcher import JournalWatcher


def _write_journal(path, rows):
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


class ProfileIsolationTests(unittest.TestCase):
    def test_runtime_reset_drops_outgoing_commander_state(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        cancelled = []
        dashboard.root = type("Root", (), {"cancel": lambda _self, job: cancelled.append(job)})()
        dashboard._hud_refresh_job = "old-hud-refresh"
        dashboard._hud_refresh_requested = True
        dashboard.config = {
            "ground_target_lat": 12.5,
            "ground_target_lon": -44.0,
            "ground_target_active": True,
            "ground_popup_enabled": False,
        }
        dashboard.current_sys = "Old System"
        dashboard.route_list = [{"StarSystem": "Old Route"}]
        dashboard.current_cargo_inventory = [{"Name": "gold", "Count": 20}]
        dashboard.colonisation_projects = {1: {"name": "Old Project"}}
        dashboard.engineer_materials = {"raw": {"iron": 99}}
        dashboard.companion_state = {"unsold_exploration_cr": 123456}
        dashboard.log_entries = ["old"]
        dashboard.event_feed_entries = [{"message": "old"}]
        dashboard.event_feed_view = list(dashboard.event_feed_entries)
        dashboard.journal_history_entries = [{"event": "Old"}]
        dashboard._event_feed_pending = deque([{"message": "pending"}])
        dashboard._journal_history_pending = deque([{"event": "Pending"}])
        dashboard._event_feed_pending_lock = threading.Lock()

        dashboard._reset_profile_runtime_state("New Commander", "F999")

        self.assertEqual(dashboard.cmdr_name, "New Commander")
        self.assertEqual(dashboard.cmdr_fid, "F999")
        self.assertEqual(dashboard.current_sys, "---")
        self.assertEqual(dashboard.route_list, [])
        self.assertEqual(dashboard.current_cargo_inventory, [])
        self.assertEqual(dashboard.colonisation_projects, {})
        self.assertEqual(dashboard.engineer_materials, {})
        self.assertEqual(dashboard.companion_state["unsold_exploration_cr"], 0)
        self.assertEqual(dashboard.event_feed_entries, [])
        self.assertEqual(dashboard.journal_history_entries, [])
        self.assertEqual(list(dashboard._event_feed_pending), [])
        self.assertEqual(list(dashboard._journal_history_pending), [])
        self.assertTrue(dashboard.target_latlon_active)
        self.assertFalse(dashboard.ground_popup_enabled)
        self.assertFalse(dashboard.current_docked)
        self.assertEqual(dashboard.hud_flight_state, "FLIGHT")
        self.assertEqual(cancelled, ["old-hud-refresh"])
        self.assertIsNone(dashboard._hud_refresh_job)
        self.assertFalse(dashboard._hud_refresh_requested)

    def test_location_login_replaces_outgoing_navigation_hud_state(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.hud_flight_state = "SUPERCRUISE"
        dashboard.current_docked = False
        dashboard.current_on_foot = False
        dashboard.current_in_fighter = True
        dashboard.current_in_srv = True
        dashboard.current_vehicle_id = 99
        dashboard.current_vehicle_name = "FIGHTER"
        dashboard.current_station_name = "Old Station"

        raw = {
            "event": "Location", "StarSystem": "Sol", "Docked": True,
            "StationName": "Galileo", "StationType": "Coriolis",
            "MarketID": 128666762, "StationServices": ["Dock", "Market"],
        }
        normalised = JournalWatcher(None)._normalize_event(raw)["data"]
        dashboard._apply_location_navigation_state(raw, normalised)

        self.assertTrue(dashboard.current_docked)
        self.assertFalse(dashboard.current_in_fighter)
        self.assertFalse(dashboard.current_in_srv)
        self.assertEqual(dashboard.hud_flight_state, "DOCKED")
        self.assertEqual(dashboard.current_station_name, "Galileo")
        self.assertEqual(dashboard.current_station_market_id, 128666762)

    def test_status_refresh_updates_hud_state_even_during_profile_catchup(self):
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.config = {
            "ground_target_lat": 0, "ground_target_lon": 0,
            "ground_target_active": False, "ground_popup_enabled": False,
        }
        dashboard._reset_profile_runtime_state("Docked Commander", "F2")
        dashboard.batch_mode = True
        dashboard.heartbeat_hud = None
        dashboard.mining_window = None
        dashboard._perf_spike = lambda *_args, **_kwargs: None

        dashboard._apply_status_update({"Flags": 0x00000001, "Flags2": 0})
        self.assertTrue(dashboard.current_docked)
        self.assertEqual(dashboard.hud_flight_state, "DOCKED")

        dashboard._apply_status_update({"Flags": 0x00000010, "Flags2": 0})
        self.assertFalse(dashboard.current_docked)
        self.assertEqual(dashboard.hud_flight_state, "SUPERCRUISE")

    def test_carrier_state_is_empty_when_new_profile_has_no_file(self):
        with tempfile.TemporaryDirectory() as folder:
            alpha_path = os.path.join(folder, "alpha_carrier.json")
            bravo_path = os.path.join(folder, "bravo_carrier.json")
            with open(alpha_path, "w", encoding="utf-8") as handle:
                json.dump({"carrier_id": 123, "name": "Alpha Carrier", "system": "Sol"}, handle)

            tracker = CarrierTracker()
            tracker.set_config({"carrier_state_file": alpha_path})
            self.assertEqual(tracker.carrier_data["name"], "Alpha Carrier")

            tracker.set_config({"carrier_state_file": bravo_path})
            self.assertIsNone(tracker.carrier_data["carrier_id"])
            self.assertIsNone(tracker.carrier_data["name"])
            self.assertIsNone(tracker.carrier_data["system"])
            self.assertEqual(tracker.carrier_data["status"], "idle")

    def test_carrier_history_only_imports_selected_commander(self):
        with tempfile.TemporaryDirectory() as folder:
            _write_journal(os.path.join(folder, "Journal.01.log"), [
                {"timestamp": "2026-01-01T00:00:00Z", "event": "LoadGame", "Commander": "Alpha", "FID": "F1"},
                {"timestamp": "2026-01-01T00:00:01Z", "event": "CarrierStats", "CarrierID": 111, "Name": "Alpha Carrier", "Callsign": "A1"},
            ])
            _write_journal(os.path.join(folder, "Journal.02.log"), [
                {"timestamp": "2026-01-02T00:00:00Z", "event": "LoadGame", "Commander": "Bravo", "FID": "F2"},
                {"timestamp": "2026-01-02T00:00:01Z", "event": "CarrierStats", "CarrierID": 222, "Name": "Bravo Carrier", "Callsign": "B2"},
            ])
            tracker = CarrierTracker()
            tracker.set_config({"carrier_state_file": os.path.join(folder, "active.json")})

            tracker.scan_journal_history(folder, commander="Alpha", fid="F1")

            self.assertEqual(tracker.carrier_data["carrier_id"], 111)
            self.assertEqual(tracker.carrier_data["name"], "Alpha Carrier")

    def test_captains_log_history_only_imports_selected_commander(self):
        with tempfile.TemporaryDirectory() as folder:
            _write_journal(os.path.join(folder, "Journal.01.log"), [
                {"timestamp": "2026-01-01T00:00:00Z", "event": "LoadGame", "Commander": "Alpha", "FID": "F1", "StarSystem": "Sol"},
                {"timestamp": "2026-01-01T00:01:00Z", "event": "FSDJump", "StarSystem": "Achenar", "JumpDist": 10},
                {"timestamp": "2026-01-01T00:02:00Z", "event": "Shutdown"},
            ])
            _write_journal(os.path.join(folder, "Journal.02.log"), [
                {"timestamp": "2026-01-02T00:00:00Z", "event": "LoadGame", "Commander": "Bravo", "FID": "F2", "StarSystem": "Lave"},
                {"timestamp": "2026-01-02T00:01:00Z", "event": "FSDJump", "StarSystem": "Leesti", "JumpDist": 5},
                {"timestamp": "2026-01-02T00:02:00Z", "event": "Shutdown"},
            ])
            logbook = CaptainsLog(os.path.join(folder, "alpha_log.json"))

            logbook.import_journals(folder, commander="Alpha", fid="F1")

            sessions = logbook.sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["commander"], "Alpha")
            self.assertEqual(sessions[0]["end_system"], "Achenar")
            self.assertEqual(sessions[0]["jumps"], 1)

    def test_edsm_profile_switch_invalidates_old_background_generation(self):
        handler = EDSMHandler({"edsm_game_version": "old", "edsm_game_build": "old-build"})
        outgoing_generation = handler._profile_generation
        handler.prepare_profile_switch()
        handler._arm_flush(immediate=True, expected_generation=outgoing_generation)
        self.assertIsNone(handler._flush_timer)

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute("CREATE TABLE edsm_queue (id INTEGER PRIMARY KEY, queued_ts REAL, event_json TEXT)")
        lock = threading.RLock()
        handler.switch_profile({}, conn, lock)
        self.assertEqual(handler._game_version, "")
        self.assertEqual(handler._game_build, "")
        self.assertIs(handler._db_conn, conn)

    def test_edsm_cargo_snapshot_is_complete_debounced_and_can_clear_inventory(self):
        handler = EDSMHandler({
            "edsm_upload_enabled": True,
            "edsm_cmdr_name": "Test Commander",
            "edsm_api_key": "test-key",
            "edsm_game_version": "4.0",
            "edsm_game_build": "test-build",
        })
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute("CREATE TABLE edsm_queue (id INTEGER PRIMARY KEY, queued_ts REAL, event_json TEXT)")
        lock = threading.RLock()
        handler.set_db(conn, lock)
        handler._arm_flush = lambda *args, **kwargs: None

        inventory = [
            {"Name": "gold", "Count": 2, "Stolen": 0},
            {"Name": "silver", "Count": 3, "Stolen": 0},
        ]
        self.assertTrue(handler.queue_cargo_snapshot(inventory, vessel="Ship"))
        with handler._queue_lock:
            handler._cargo_timer.cancel()
            handler._cargo_timer = None
        handler._flush_pending_cargo(handler._profile_generation)

        row = conn.execute("SELECT event_json FROM edsm_queue").fetchone()
        event = json.loads(row[0])
        self.assertEqual(event["event"], "Cargo")
        self.assertEqual(event["Vessel"], "Ship")
        self.assertEqual(event["Count"], 5)
        self.assertEqual(event["Inventory"], inventory)

        # An identical snapshot is suppressed, while an empty one is retained
        # so EDSM can clear stale cargo rather than keeping the old total.
        self.assertFalse(handler.queue_cargo_snapshot(list(reversed(inventory)), vessel="Ship"))
        self.assertTrue(handler.queue_cargo_snapshot([], vessel="Ship"))
        with handler._queue_lock:
            handler._cargo_timer.cancel()
            handler._cargo_timer = None
        handler._flush_pending_cargo(handler._profile_generation)
        rows = conn.execute("SELECT event_json FROM edsm_queue ORDER BY id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[1][0])["Inventory"], [])


if __name__ == "__main__":
    unittest.main()
