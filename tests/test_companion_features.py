import base64
import gzip
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import companion_features as features  # noqa: E402
from bgs_window import BGSWindow  # noqa: E402
from dashboard import MainDashboard  # noqa: E402


def test_ship_export_round_trip():
    loadout = {
        "event": "Loadout", "Ship": "krait_mkii", "ShipName": "BESSIE",
        "Modules": [{"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_size5_class5"}],
    }
    url = features.edsy_url(loadout)
    blob = url.split("#/I=", 1)[1].replace("%3D", "=")
    decoded = json.loads(gzip.decompress(base64.urlsafe_b64decode(blob)))
    assert decoded == loadout
    wrapped = json.loads(features.slef(loadout))
    assert wrapped[0]["header"]["appName"] == "VoidCompass"
    assert wrapped[0]["data"] == loadout


def test_synthesis_and_sampling_math():
    synth = features.fsd_injections({
        "carbon": 5, "vanadium": 4, "germanium": 3, "cadmium": 2,
        "niobium": 2, "arsenic": 1, "polonium": 1, "yttrium": 1,
    })
    assert synth == {"basic": 3, "standard": 2, "premium": 1}
    moon_radius = 600_000
    lat_500m = 500 / moon_radius * 180 / 3.141592653589793
    result = features.sample_clearance(
        [{"lat": 0, "lon": 0, "body": 7}],
        {"lat": lat_500m, "lon": 0, "body": 7, "radius_m": moon_radius},
        500,
    )
    assert result["min_distance_m"] == 500 and result["clear"]


def test_massacre_stack_math():
    state = features.fresh_state()
    for mid, giver, kills, reward in ((1, "A", 10, 5_000_000), (2, "A", 8, 4_000_000), (3, "B", 12, 6_000_000)):
        event = {"MissionID": mid, "Name": "Mission_Massacre", "Faction": giver,
                 "TargetFaction": "Pirates", "KillCount": kills, "Reward": reward}
        state["missions"][str(mid)] = features.mission_from_event(event)
    stack = features.massacre_stacks(state)[0]
    assert stack["kills_needed"] == 18 and stack["reward"] == 15_000_000
    state["faction_kills"]["Pirates"] = 18
    assert features.massacre_stacks(state)[0]["complete"]


def test_faction_watch_changes_and_history_delta():
    state = features.fresh_state()
    assert features.toggle_faction_watch(state, "Test Controllers")
    baseline = [{"name": "Test Controllers", "influence": 0.50,
                 "active_states": ["Boom"]}]
    assert features.update_faction_watch_snapshots(
        state, "Test", baseline, "Test Controllers", notify=False) == []
    changed = [{"name": "Test Controllers", "influence": 0.52,
                "active_states": ["Expansion"]}]
    notices = features.update_faction_watch_snapshots(
        state, "Test", changed, None, notify=True)
    assert len(notices) == 1
    assert "influence +2.0%" in notices[0][1]
    assert "state Expansion" in notices[0][1]
    assert "lost system control" in notices[0][1]

    window = BGSWindow.__new__(BGSWindow)
    window._load_factions = lambda _system: [
        {"faction_name": "Test Controllers", "influence": 0.52, "recorded_at": 2},
        {"faction_name": "Test Controllers", "influence": 0.50, "recorded_at": 1},
    ]
    deltas = window._faction_history_deltas("Test", changed)
    assert round(deltas["Test Controllers"], 4) == 0.02


def test_dashboard_companion_journal_integration():
    class Root:
        @staticmethod
        def after(_delay, callback):
            callback()

    class Toast:
        def __init__(self):
            self.rows = []

        def push(self, *args, **kwargs):
            self.rows.append((args, kwargs))

    app = MainDashboard.__new__(MainDashboard)
    app.root = Root()
    app.config = {}
    app.toast_hud = Toast()
    app.commander_profile_window = None
    app.bgs_window = None
    app.survey_status_hud = None
    app.companion_state = features.fresh_state()
    app._save_companion_state = lambda: None
    app.cmdr_ship = {}
    app.cmdr_balance = 100_000_000
    app.current_sys = "Test"
    app.current_latitude = 0.0
    app.current_longitude = 0.0
    app.current_planet_radius = 600_000
    app.bio_sampling = None
    app.bio_sample_points = []
    app._sample_clear_announced = False
    app._rebuy_warning_level = 0
    app._data_risk_level = 0
    app.scan_items_by_id = {7: {"first_footfall": False}}

    for mid, giver, kills in ((1, "A", 10), (2, "A", 8), (3, "B", 12)):
        app._process_companion_event("MissionAccepted", {
            "MissionID": mid, "Name": "Mission_Massacre", "Faction": giver,
            "TargetFaction": "Pirates", "KillCount": kills, "Reward": 1_000_000,
        }, {}, False)
    for _ in range(18):
        app._process_companion_event("Bounty", {"VictimFaction": "Pirates"}, {}, False)
    assert features.massacre_stacks(app.companion_state)[0]["complete"]
    assert any(row[0][0] == "STACK COMPLETE" for row in app.toast_hud.rows)

    app._process_companion_event("StoredShips", {
        "StationName": "Jameson Memorial", "StarSystem": "Shinrarta Dezhra",
        "ShipsHere": [{"ShipType_Localised": "Krait Mk II", "Name": "Bessie", "Value": 1}],
        "ShipsRemote": [],
    }, {}, False)
    assert app.companion_state["stored_ships"]["here"][0]["name"] == "Bessie"

    app._process_companion_event("Powerplay", {"Power": "Edmund Mahon", "Rank": 2, "Merits": 50}, {}, False)
    app._process_companion_event("PowerplayMerits", {"Power": "Edmund Mahon", "MeritsGained": 20, "TotalMerits": 70}, {}, False)
    assert app.companion_state["powerplay"]["session_merits"] == 20
    app._process_companion_event("FSDJump", {
        "StarSystem": "Test", "SystemFaction": {"Name": "Test Controllers"},
        "ControllingPower": "Edmund Mahon", "Powers": ["Edmund Mahon", "Aisling Duval"],
        "PowerplayState": "Exploited", "PowerplayStateControlProgress": 0.5,
        "Factions": [{
            "Name": "Test Controllers", "Influence": 0.6, "Government": "Democracy",
            "Allegiance": "Independent", "MyReputation": 91,
            "ActiveStates": [{"State": "Boom"}],
            "PendingStates": [{"State": "Expansion"}],
            "RecoveringStates": [{"State": "War"}],
        }],
        "Conflicts": [{
            "WarType": "war", "Status": "active",
            "Faction1": {"Name": "A", "Stake": "Port", "WonDays": 2},
            "Faction2": {"Name": "B", "WonDays": 1},
        }],
    }, {}, False)
    assert app.companion_state["controlling_faction"] == "Test Controllers"
    assert app.companion_state["factions"][0]["recovering_states"] == ["War"]
    assert app.companion_state["conflicts"][0]["faction1"]["stake"] == "Port"
    assert app.companion_state["galaxy_source"] == "FSDJump"
    assert app.companion_state["galaxy_system_updated"]

    app._toggle_galaxy_faction_watch("Test Controllers")
    app._process_companion_event("FSDJump", {
        "timestamp": "2026-07-13T12:00:00Z", "StarSystem": "Test",
        "SystemFaction": {"Name": "Other Controllers"},
        "Factions": [{
            "Name": "Test Controllers", "Influence": 0.62,
            "ActiveStates": [{"State": "Expansion"}],
        }],
    }, {}, False)
    assert any(row[0][0] == "FACTION WATCH" for row in app.toast_hud.rows)

    app.cmdr_balance = 15_000_000
    app._process_companion_event("Loadout", {"event": "Loadout", "Ship": "krait_mkii", "Rebuy": 10_000_000}, {}, False)
    assert any(row[0][0] == "LOW REBUY COVER" for row in app.toast_hud.rows)
    app.companion_state["unsold_bio_cr"] = 300_000_000
    app._check_data_risk()
    assert any(row[0][0] == "DATA AT RISK" for row in app.toast_hud.rows)

    app._process_companion_event("ScanOrganic", {
        "ScanType": "Log", "Species_Localised": "Bacterium Aurasus",
        "Genus_Localised": "Bacterium", "Body": 7,
    }, {"species": "Bacterium Aurasus", "genus": "Bacterium", "body_id": 7}, False)
    app.current_latitude = 0.05
    app._update_sampling_clearance()
    assert any(row[0][0] == "CLEAR TO SAMPLE" for row in app.toast_hud.rows)


if __name__ == "__main__":
    test_ship_export_round_trip()
    test_synthesis_and_sampling_math()
    test_massacre_stack_math()
    test_faction_watch_changes_and_history_delta()
    test_dashboard_companion_journal_integration()
    print("ALL COMPANION FEATURE TESTS PASSED")
