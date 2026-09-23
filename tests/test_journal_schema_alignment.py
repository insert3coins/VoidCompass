import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from voidcompass.services.carrier_tracker import CarrierTracker
from voidcompass.exploration.captains_log import CaptainsLog
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.core.journal_watcher import JournalWatcher
from voidcompass.core import companion_features
from voidcompass.core import operational_state
from voidcompass.mining import mining_data


class JournalSchemaAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.watcher = JournalWatcher("")

    def test_colonisation_depot_uses_current_schema_fields(self):
        event = self.watcher._normalize_event({
            "event": "ColonisationConstructionDepot",
            "MarketID": 42,
            "ConstructionProgress": 0.141462,
            "ConstructionComplete": False,
            "ConstructionFailed": False,
            "ResourcesRequired": [{
                "Name": "Steel", "Name_Localised": "Steel",
                "RequiredAmount": 1000, "ProvidedAmount": 250, "Payment": 3239,
            }],
        })
        self.assertAlmostEqual(event["data"]["progress"], 0.141462)
        self.assertEqual(event["data"]["resources"][0]["provided"], 250)
        self.assertEqual(event["data"]["resources"][0]["payment"], 3239)

    def test_colonisation_contribution_uses_amount(self):
        event = self.watcher._normalize_event({
            "event": "ColonisationContribution", "MarketID": 42,
            "Contributions": [{"Name": "Steel", "Amount": 724}],
        })
        self.assertEqual(event["data"]["contributions"][0]["count"], 724)
        self.assertNotIn("progress", event["data"])

    def test_claim_and_footfall_fields_match_schema(self):
        claim = self.watcher._normalize_event({
            "event": "ColonisationSystemClaim", "StarSystem": "Test",
            "SystemAddress": 123,
        })
        self.assertEqual(claim["type"], "ColonisationSystemClaim")
        self.assertEqual(claim["data"]["star_system"], "Test")

        scan = self.watcher._normalize_event({
            "event": "Scan", "BodyName": "Test A 1", "PlanetClass": "Rocky body",
            "Landable": True, "WasFootfalled": False,
        })
        self.assertIs(scan["data"]["was_footfalled"], False)
        self.assertTrue(scan["data"]["first_footfall"])

    def test_carrier_name_change_accepts_schema_and_live_fallback(self):
        tracker = CarrierTracker()
        tracker.carrier_data["carrier_id"] = 42
        tracker.save_state = lambda: None
        tracker._ensure_status_ticker = lambda: None
        tracker.process_event({
            "event": "CarrierNameChange", "CarrierID": 42,
            "Name": "Schema Name", "Callsign": "ABC-12Z",
        })
        self.assertEqual(tracker.carrier_data["name"], "Schema Name")
        self.assertEqual(tracker.carrier_data["callsign"], "ABC-12Z")
        tracker.process_event({
            "event": "CarrierNameChange", "CarrierID": 42, "": "Live Journal Name",
        })
        self.assertEqual(tracker.carrier_data["name"], "Live Journal Name")

    def test_clear_carrier_expedition_retains_carrier_evidence(self):
        tracker = CarrierTracker()
        tracker.save_state = lambda: None
        tracker.carrier_data.update({
            "carrier_id": 42,
            "space_cargo": 9000,
            "jump_history": [{"system": "Colonia"}],
            "expedition_name": "Colonia Run",
            "expedition_route": [{"system": "Colonia", "fuel_used_t": 90}],
            "expedition_requested_destinations": ["Colonia"],
            "expedition_reserve_fuel": 350,
            "expedition_route_source": "spansh",
            "expedition_spansh_job": "job-id",
            "expedition_spansh_url": "https://spansh.co.uk/fleet-carrier/results/job-id",
            "expedition_fuel_required_t": 4000,
            "expedition_used_capacity_t": 11000,
        })

        tracker.clear_expedition()

        self.assertEqual(tracker.carrier_data["expedition_name"], "")
        self.assertEqual(tracker.carrier_data["expedition_route"], [])
        self.assertEqual(tracker.carrier_data["expedition_requested_destinations"], [])
        self.assertEqual(tracker.carrier_data["expedition_route_source"], "manual")
        self.assertIsNone(tracker.carrier_data["expedition_spansh_job"])
        self.assertIsNone(tracker.carrier_data["expedition_spansh_url"])
        self.assertIsNone(tracker.carrier_data["expedition_fuel_required_t"])
        self.assertIsNone(tracker.carrier_data["expedition_used_capacity_t"])
        self.assertEqual(tracker.carrier_data["expedition_reserve_fuel"], 350)
        self.assertEqual(tracker.carrier_data["carrier_id"], 42)
        self.assertEqual(tracker.carrier_data["space_cargo"], 9000)
        self.assertEqual(tracker.carrier_data["jump_history"], [{"system": "Colonia"}])

    def test_carrier_arrival_projects_live_depot_fuel_once(self):
        tracker = CarrierTracker()
        tracker.save_state = lambda *args, **kwargs: None
        tracker._ensure_status_ticker = lambda: None
        tracker.carrier_data.update({
            "carrier_id": 3708973824,
            "system": "Col 359 Sector JT-N c21-18",
            "system_address": 5031319376802,
            "fuel_level": 895,
            "fuel_capacity": 1000,
            "fuel_level_updated_at": "2026-07-29T09:23:31Z",
            "stats_updated_at": "2026-07-29T09:23:31Z",
            "space_total": 25000,
            "space_free": 11035,
            "expedition_route": [{
                "system": "Pru Euq GO-T b58-3",
                "id64": 7262387251193,
                "distance_ly": 499.959089146615,
                "fuel_used_t": 114,
                "visited": False,
                "visited_at": None,
            }],
        })

        tracker.process_event({
            "event": "CarrierLocation",
            "timestamp": "2026-07-29T09:39:11Z",
            "CarrierID": 3708973824,
            "StarSystem": "Pru Euq GO-T b58-3",
            "SystemAddress": 7262387251193,
        })
        row = tracker.carrier_data["expedition_route"][0]
        self.assertEqual(tracker.carrier_data["fuel_level"], 790)
        self.assertTrue(tracker.carrier_data["fuel_level_estimated"])
        self.assertEqual(row["fuel_actual_used_t"], 105)

        tracker.process_event({
            "event": "CarrierJump",
            "timestamp": "2026-07-29T09:40:01Z",
            "MarketID": 3708973824,
            "StarSystem": "Pru Euq GO-T b58-3",
            "SystemAddress": 7262387251193,
        })
        self.assertEqual(tracker.carrier_data["fuel_level"], 790)

    def test_carrier_fuel_recovery_and_authoritative_reconciliation(self):
        tracker = CarrierTracker()
        tracker.save_state = lambda *args, **kwargs: None
        tracker._ensure_status_ticker = lambda: None
        tracker.carrier_data.update({
            "carrier_id": 3708973824,
            "system": "Pru Euq GO-T b58-3",
            "system_address": 7262387251193,
            "fuel_level": 895,
            "fuel_capacity": 1000,
            "stats_updated_at": "2026-07-29T09:23:31Z",
            "space_total": 25000,
            "space_free": 11035,
            "expedition_route": [{
                "system": "Pru Euq GO-T b58-3",
                "id64": 7262387251193,
                "distance_ly": 499.959089146615,
                "visited": True,
                "visited_at": "2026-07-29T09:39:11Z",
            }],
        })

        tracker.process_event({
            "event": "CarrierJump",
            "timestamp": "2026-07-29T09:40:01Z",
            "MarketID": 3708973824,
            "StarSystem": "Pru Euq GO-T b58-3",
            "SystemAddress": 7262387251193,
        })
        self.assertEqual(tracker.carrier_data["fuel_level"], 790)

        tracker.process_event({
            "event": "CarrierStats",
            "timestamp": "2026-07-29T09:23:31Z",
            "CarrierID": 3708973824,
            "FuelLevel": 895,
        })
        self.assertEqual(tracker.carrier_data["fuel_level"], 790)
        self.assertTrue(tracker.carrier_data["fuel_level_estimated"])

        tracker.process_event({
            "event": "CarrierStats",
            "timestamp": "2026-07-29T09:45:00Z",
            "CarrierID": 3708973824,
            "FuelLevel": 790,
        })
        self.assertEqual(tracker.carrier_data["fuel_level"], 790)
        self.assertFalse(tracker.carrier_data["fuel_level_estimated"])
        self.assertEqual(tracker.carrier_data["fuel_level_source"], "CarrierStats")

    def test_ship_redeemed_waits_for_confirmed_swap(self):
        ship, changed = companion_features.update_active_ship(
            {"ship": "sidewinder", "ship_id": 1, "ship_name": "Old"},
            "ShipRedeemed",
            {"ShipType": "mediumtransport01", "ShipType_Localised": "Lynx Highliner",
             "NewShipID": 128},
        )
        self.assertFalse(changed)
        self.assertEqual(ship["ship_id"], 1)

        ship, changed = companion_features.update_active_ship(ship, "ShipyardSwap", {
            "ShipType": "mediumtransport01", "ShipType_Localised": "Lynx Highliner",
            "ShipID": 128,
        })
        self.assertTrue(changed)
        self.assertEqual(ship["ship_id"], 128)
        self.assertEqual(ship["ship_localised"], "Lynx Highliner")

    def test_legacy_biology_estimate_migrates_to_range(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "companion.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"unsold_bio_cr": 5_000_000}, handle)
            state = companion_features.load_state(path)
        self.assertEqual(state["unsold_bio_cr"], 1_000_000)
        self.assertEqual(state["unsold_bio_bonus_potential_cr"], 4_000_000)

    def test_biology_estimate_separates_base_and_possible_bonus(self):
        app = MainDashboard.__new__(MainDashboard)
        app.scan_items_by_id = {1: {"first_footfall": True}}
        app.companion_state = {"unsold_bio_cr": 0, "unsold_bio_bonus_potential_cr": 0}
        app.current_latitude = app.current_longitude = None
        app.bio_sampling = None
        app.bio_sample_points = []
        app._update_sampling_clearance = lambda: None
        self.assertTrue(app._process_sampling_event(
            {"ScanType": "Analyse", "Body": 1},
            {"scan_type": "Analyse", "body_id": 1, "species": "Bacterium Aurasus"},
        ))
        self.assertEqual(app.companion_state["unsold_bio_cr"], 1_000_000)
        self.assertEqual(app.companion_state["unsold_bio_bonus_potential_cr"], 4_000_000)

    def test_sample_clearance_updates_survey_without_duplicate_toast(self):
        app = MainDashboard.__new__(MainDashboard)
        sample = {
            "species": "Bacterium Aurasus", "progress": 2,
            "min_distance_m": 530, "colony_m": 500, "clear": True,
        }
        app._sampling_snapshot = lambda: sample
        app.survey_status_hud = Mock()
        app._toast_on_main = Mock()
        app._ui_post = lambda callback, key=None: callback()
        app.current_sys = "Testia"
        app.scanned = app.total = 2
        app.scan_items = []
        app.body_signals = {}
        app.current_body_id = 1
        app.current_body_name = "Testia A 1"
        app.scan_total_confirmed = True
        app.belt_clusters = []
        app._dss_efficiency_snapshot = lambda: {}
        app.exploration_window = None

        app._update_sampling_clearance()

        self.assertFalse(app._toast_on_main.called)
        self.assertEqual(app.survey_status_hud.update.call_args.kwargs["sampling"], sample)

    def test_captains_log_derives_carrier_distance_and_bio_body(self):
        log = CaptainsLog("")
        log.process_event({"event": "LoadGame", "timestamp": "2026-01-01T00:00:00Z"}, save=False)
        log.process_event({"event": "Location", "StarPos": [0, 0, 0]}, save=False)
        log.process_event({
            "event": "CarrierJump", "timestamp": "2026-01-01T00:01:00Z",
            "StarSystem": "Beta", "StarPos": [3, 4, 0],
        }, save=False)
        log.process_event({
            "event": "Scan", "SystemAddress": 99, "BodyID": 7, "BodyName": "Beta A 1",
        }, save=False)
        log.process_event({
            "event": "ScanOrganic", "timestamp": "2026-01-01T00:02:00Z",
            "ScanType": "Analyse", "SystemAddress": 99, "Body": 7,
            "Species_Localised": "Bacterium Aurasus",
        }, save=False)
        session = log.data["sessions"][-1]
        self.assertEqual(session["distance_ly"], 5.0)
        self.assertEqual(session["highlights"][-2]["detail"], "5.0 ly")
        self.assertEqual(session["highlights"][-1]["detail"], "Beta A 1")

    def test_vehicle_switch_updates_navigation_state_immediately(self):
        app = MainDashboard.__new__(MainDashboard)
        app.current_on_foot = False
        app.current_in_fighter = False
        app.current_in_srv = False
        app.current_docked = False
        app.current_landed = False
        app.current_vehicle_id = None
        app.current_vehicle_name = ""
        app._last_surface_vehicle_name = "NOMAD"
        app.hud_flight_state = "FLIGHT"
        app.update_hud = lambda: None

        self.assertEqual(app._apply_vehicle_switch("SRV"), "NOMAD")
        self.assertTrue(app.current_in_srv)
        self.assertEqual(app._apply_vehicle_switch("Mothership"), "FLIGHT")
        self.assertFalse(app.current_in_srv)

    def test_operational_state_tracks_vehicle_and_crew_context(self):
        state = operational_state.fresh_runtime_state()
        operational_state.observe_event(state, "VehicleSwitch", {"To": "Fighter"})
        operational_state.observe_event(state, "JoinACrew", {"Captain": "Test Captain"})

        self.assertEqual(state["ground"]["vehicle_control"], "Fighter")
        self.assertTrue(state["ground"]["in_multicrew"])

    def test_spansh_ring_search_uses_reference_range_and_ring_signals(self):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"results": [{
                    "system_name": "Nearby System", "name": "Nearby System 2",
                    "id64": 22, "system_id64": 11, "distance": 42.5,
                    "distance_to_arrival": 1234, "reserve_level": "Pristine",
                    "rings": [{
                        "name": "Nearby System 2 A Ring", "type": "Icy",
                        "signals": {"signals": [
                            {"name": "Tritium", "count": 3},
                            {"name": "Bromellite", "count": 1},
                        ]},
                    }],
                }]}

        with patch.object(mining_data.requests, "post", return_value=Response()) as post:
            rows = mining_data.search_spansh_rings(
                "Origin", material="Tritium", max_results=10, max_distance=125,
            )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["reference_system"], "Origin")
        self.assertEqual(payload["filters"]["distance"], {"min": 0, "max": 125.0})
        self.assertEqual(payload["filters"]["ring_signals"][0]["name"], "Tritium")
        self.assertEqual(payload["sort"][0]["distance"]["direction"], "asc")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hotspot_count"], 3)
        self.assertEqual(rows[0]["body_id64"], 22)


if __name__ == "__main__":
    unittest.main()
