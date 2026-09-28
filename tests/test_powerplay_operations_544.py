import unittest

from voidcompass.powerplay import powerplay_operations as powerplay
from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.overlays.overlay_layout_model import OVERLAY_ENABLE_KEYS
from voidcompass.overlays.powerplay_hud import build_powerplay_overlay_model


class _PowerplayDashboard(HtmlDashboardMixin):
    def __init__(self):
        self.companion_state = {"powerplay": powerplay.fresh_powerplay_state()}
        self.powerplay_hud = None
        self.session_start_ts = 0
        self.saved = 0
        self.published = 0

    def _save_companion_state(self):
        self.saved += 1

    def _schedule_html_dashboard_publish(self, immediate=False):
        self.published += int(bool(immediate))


class PowerplayOperations544Tests(unittest.TestCase):
    def test_complete_power_dossier_catalogue_uses_bundled_portraits(self):
        self.assertEqual(len(powerplay.POWER_DOSSIERS), 12)
        self.assertEqual(len({row["slug"] for row in powerplay.POWER_DOSSIERS}), 12)
        self.assertTrue(all(row["portrait"] for row in powerplay.POWER_DOSSIERS))
        self.assertEqual(powerplay.dossier_for("A. Lavigny-Duval")["headquarters"], "Kamadhenu")

    def test_cycle_window_rolls_at_thursday_0700_utc(self):
        before = powerplay.cycle_window("2026-09-17T06:59:59Z")
        after = powerplay.cycle_window("2026-09-17T07:00:00Z")
        self.assertEqual(before["id"], "2026-09-10")
        self.assertEqual(after["id"], "2026-09-17")

    def test_merit_events_keep_total_delta_system_and_cycle_summary(self):
        state = powerplay.fresh_powerplay_state()
        state = powerplay.reduce_event(state, "Powerplay", {
            "timestamp": "2026-09-17T08:00:00Z", "Power": "Nakato Kaine",
            "Rank": 4, "Merits": 1000, "TimePledged": 86400,
        })
        state = powerplay.reduce_event(state, "PowerplayMerits", {
            "timestamp": "2026-09-17T09:00:00Z", "Power": "Nakato Kaine",
            "TotalMerits": 1125, "MeritsGained": 125,
            "StarSystem": "Tionisla",
        })
        self.assertEqual(state["merits"], 1125)
        self.assertEqual(state["merit_history"][-1]["delta"], 125)
        self.assertEqual(state["current_cycle"]["merits_gained"], 125)
        self.assertEqual(state["current_cycle"]["systems"], {"Tionisla": 125})
        workspace = powerplay.build_workspace(
            state, now="2026-09-17T10:00:00Z",
            session_started="2026-09-17T08:30:00Z",
        )
        self.assertEqual(workspace["session_merits"], 125)
        duplicate = powerplay.reduce_event(state, "PowerplayMerits", {
            "timestamp": "2026-09-17T09:00:00Z", "Power": "Nakato Kaine",
            "TotalMerits": 1125, "MeritsGained": 125,
            "StarSystem": "Tionisla",
        })
        self.assertEqual(len(duplicate["merit_history"]), 2)
        self.assertEqual(duplicate["current_cycle"]["merits_gained"], 125)

    def test_cargo_event_advances_matching_assignment(self):
        state, added = powerplay.add_objective(
            powerplay.fresh_powerplay_state(),
            {"title": "Supply the front", "kind": "deliver", "system": "Rhea",
             "commodity": "Power Supplies", "target": 20},
            now="2026-09-17T08:00:00Z",
        )
        self.assertTrue(added)
        state = powerplay.reduce_event(state, "PowerplayDeliver", {
            "timestamp": "2026-09-17T09:00:00Z", "Power": "Felicia Winters",
            "StarSystem": "Rhea", "Type_Localised": "Power Supplies", "Count": 20,
        })
        objective = state["objectives"][0]
        self.assertEqual(objective["current"], 20)
        self.assertTrue(objective["complete"])
        self.assertEqual(state["current_cycle"]["cargo_delivered"], 20)
        duplicate = powerplay.reduce_event(state, "PowerplayDeliver", {
            "timestamp": "2026-09-17T09:00:00Z", "Power": "Felicia Winters",
            "StarSystem": "Rhea", "Type_Localised": "Power Supplies", "Count": 20,
        })
        self.assertEqual(len(duplicate["cargo_history"]), 1)
        self.assertEqual(duplicate["current_cycle"]["cargo_delivered"], 20)

    def test_new_week_archives_previous_cycle(self):
        state = powerplay.reduce_event(powerplay.fresh_powerplay_state(), "PowerplayMerits", {
            "timestamp": "2026-09-17T08:00:00Z", "Power": "Edmund Mahon",
            "TotalMerits": 50, "MeritsGained": 50,
        })
        state = powerplay.reduce_event(state, "PowerplayMerits", {
            "timestamp": "2026-09-24T08:00:00Z", "Power": "Edmund Mahon",
            "TotalMerits": 75, "MeritsGained": 25,
        })
        self.assertEqual(state["cycles"][-1]["id"], "2026-09-17")
        self.assertEqual(state["cycles"][-1]["merits_gained"], 50)
        self.assertEqual(state["current_cycle"]["id"], "2026-09-24")
        self.assertEqual(state["current_cycle"]["merits_gained"], 25)

    def test_defection_archives_old_power_without_losing_same_week_history(self):
        state = powerplay.reduce_event(powerplay.fresh_powerplay_state(), "PowerplayMerits", {
            "timestamp": "2026-09-17T08:00:00Z", "Power": "Edmund Mahon",
            "TotalMerits": 50, "MeritsGained": 50,
        })
        state = powerplay.reduce_event(state, "PowerplayDefect", {
            "timestamp": "2026-09-18T08:00:00Z", "FromPower": "Edmund Mahon",
            "ToPower": "Nakato Kaine",
        })
        self.assertEqual(state["cycles"][-1]["power"], "Edmund Mahon")
        self.assertEqual(state["cycles"][-1]["merits_gained"], 50)
        self.assertEqual(state["current_cycle"]["power"], "Nakato Kaine")

    def test_overlay_model_carries_active_assignment_and_cycle_totals(self):
        workspace = powerplay.build_workspace({
            **powerplay.fresh_powerplay_state(),
            "pledged": True, "power": "Edmund Mahon", "rank": 8,
            "merits": 4200,
            "current_cycle": {
                **powerplay.cycle_window("2026-09-17T08:00:00Z"),
                "power": "Edmund Mahon", "merits_gained": 250,
                "cargo_collected": 12, "cargo_delivered": 8,
            },
            "objectives": [{
                "id": "pp-one", "title": "Hold Gateway", "kind": "system",
                "system": "Gateway", "target": 1, "current": 0,
                "complete": False,
            }],
            "selected_objective_id": "pp-one",
        }, now="2026-09-17T08:00:00Z")
        model = build_powerplay_overlay_model(workspace)
        self.assertTrue(model["active"])
        self.assertEqual(model["cycle_merits"], 250)
        self.assertEqual(model["objective"]["title"], "Hold Gateway")

    def test_dashboard_and_overlay_assets_use_dedicated_powerplay_modules(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        app = (root / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")
        host = (
            root / "src" / "voidcompass" / "overlays" / "html_overlay_host.py"
        ).read_text(encoding="utf-8")
        self.assertIn('from "./powerplay.js"', app)
        self.assertIn('template == "powerplay-overlay"', host)
        self.assertTrue((root / "web" / "powerplay-overlay" / "index.html").is_file())
        self.assertEqual(OVERLAY_ENABLE_KEYS["powerplay_hud"], "powerplay_overlay_enabled")

    def test_dashboard_commands_persist_assignments_and_dossier_selection(self):
        dashboard = _PowerplayDashboard()
        self.assertTrue(dashboard._handle_html_workspace_command({
            "page": "powerplay", "operation": "add_objective",
            "title": "Fortify Gateway", "kind": "system", "system": "Gateway",
            "target": 1,
        }))
        self.assertEqual(dashboard.saved, 1)
        self.assertEqual(dashboard.companion_state["powerplay"]["objectives"][0]["title"], "Fortify Gateway")
        self.assertTrue(dashboard._handle_html_workspace_command({
            "page": "powerplay", "operation": "select_dossier",
            "dossier": "nakato_kaine",
        }))
        self.assertEqual(dashboard.companion_state["powerplay"]["selected_dossier"], "nakato_kaine")


def _jump(ts, system, **fields):
    raw = {"timestamp": ts, "StarSystem": system}
    names = {"controller": "ControllingPower", "powers": "Powers", "state": "PowerplayState",
             "progress": "PowerplayStateControlProgress", "reinforcement": "PowerplayStateReinforcement",
             "undermining": "PowerplayStateUndermining", "conflict": "PowerplayConflictProgress"}
    raw.update({names[key]: value for key, value in fields.items()})
    return raw


class PowerplayRework5498Tests(unittest.TestCase):
    """The rebuilt page: rank curve, system intel, relations and the cycle's days."""

    def test_rank_curve_matches_powerplay_2(self):
        self.assertEqual([powerplay.rank_threshold(rank) for rank in range(1, 9)],
                         [0, 2000, 5000, 9000, 15000, 23000, 31000, 39000])
        progress = powerplay.rank_progress(8, 43000)
        self.assertEqual((progress["floor"], progress["next"], progress["to_go"]), (39000, 47000, 4000))
        self.assertAlmostEqual(progress["fraction"], 0.5)
        self.assertTrue(progress["consistent"])
        # A total outside the rank's band is shown without a bar, never "fixed".
        self.assertFalse(powerplay.rank_progress(8, 60000)["consistent"])
        self.assertEqual(powerplay.rank_progress(None, 100), {})

    def test_jumps_log_powerplay_systems_with_the_change_since_last_reading(self):
        state = powerplay.fresh_powerplay_state()
        state = powerplay.reduce_event(state, "FSDJump", _jump("2026-09-24T09:00:00Z", "Sol"))
        self.assertEqual(state["system_intel"], [])  # no power reported: not logged
        first = _jump("2026-09-24T10:00:00Z", "LHS 3447", controller="Nakato Kaine",
                      powers=["Nakato Kaine"], state="Fortified", progress=0.41,
                      reinforcement=12050, undermining=8870)
        state = powerplay.reduce_event(state, "FSDJump", first)
        same = dict(first, timestamp="2026-09-24T11:00:00Z")
        state = powerplay.reduce_event(state, "FSDJump", same)
        self.assertEqual(state["system_intel"][0]["visits"], 2)
        self.assertEqual(state["system_intel"][0]["previous"], {})  # nothing changed yet
        moved = dict(first, timestamp="2026-09-25T10:00:00Z", PowerplayStateControlProgress=0.47)
        state = powerplay.reduce_event(state, "FSDJump", moved)
        # A journal replayed at start-up never rolls a newer reading back.
        state = powerplay.reduce_event(state, "Location", dict(first))
        row = state["system_intel"][0]
        self.assertEqual((row["visits"], row["control_progress"]), (3, 0.47))
        self.assertEqual(row["previous"]["control_progress"], 0.41)
        workspace = powerplay.build_workspace({**state, "pledged": True, "power": "Nakato Kaine"},
                                              now="2026-09-25T12:00:00Z")
        intel = workspace["intel"][0]
        self.assertAlmostEqual(intel["progress_delta"], 0.06)
        self.assertEqual((intel["relation"], intel["action"], intel["tier"]), ("ours", "REINFORCE", 2))
        self.assertEqual(intel["ethos"], "Covert")
        # After the Thursday tick the reading is marked as pre-tick.
        later = powerplay.build_workspace({**state, "pledged": True, "power": "Nakato Kaine"},
                                          now="2026-10-02T12:00:00Z")
        self.assertTrue(later["intel"][0]["stale"])
        self.assertEqual(later["intel_counts"]["stale"], 1)

    def test_the_current_system_card_uses_its_intel_row(self):
        state = {**powerplay.fresh_powerplay_state(), "pledged": True, "power": "Nakato Kaine"}
        for stamp, progress in (("2026-09-24T10:00:00Z", 0.41), ("2026-09-25T10:00:00Z", 0.47)):
            state = powerplay.reduce_event(state, "FSDJump", _jump(
                stamp, "LHS 3447", controller="Nakato Kaine", state="Fortified", progress=progress))
        here = powerplay.build_workspace(state, now="2026-09-25T12:00:00Z")["location"]
        self.assertAlmostEqual(here["progress_delta"], 0.06)
        self.assertEqual(here["visits"], 2)
        self.assertFalse(here["stale"])
        # Still sitting in it after the Thursday tick: the reading is old news.
        self.assertTrue(powerplay.build_workspace(state, now="2026-10-01T08:00:00Z")["location"]["stale"])

    def test_relation_decides_the_orders(self):
        rival = {"controlling_power": "Edmund Mahon", "powers": ["Edmund Mahon"], "state": "Exploited"}
        open_fight = {"powers": ["Nakato Kaine", "Zemina Torval"], "state": "Unoccupied",
                      "conflict": [{"power": "Nakato Kaine", "progress": 0.3}]}
        elsewhere = {"powers": ["Archon Delaine"], "state": "Unoccupied"}
        self.assertEqual(powerplay.system_relation(rival, "Nakato Kaine"), "hostile")
        self.assertEqual(powerplay.system_relation(open_fight, "Nakato Kaine"), "acquisition")
        self.assertEqual(powerplay.system_relation(elsewhere, "Nakato Kaine"), "out_of_reach")
        self.assertEqual(powerplay.system_relation(rival, ""), "unaligned")
        self.assertEqual(powerplay.system_relation({"state": ""}, "Nakato Kaine"), "none")
        self.assertEqual(powerplay.control_tier("Stronghold"), 3)
        self.assertEqual(powerplay.control_tier("Unoccupied"), 0)

    def test_conflict_progress_keeps_only_well_formed_rows(self):
        state = powerplay.reduce_event(powerplay.fresh_powerplay_state(), "FSDJump", _jump(
            "2026-09-24T10:00:00Z", "Wolf 359", powers=["Nakato Kaine"], state="Unoccupied",
            conflict=[{"Power": "Zemina Torval", "ConflictProgress": 0.2},
                      {"Power": "Nakato Kaine", "ConflictProgress": 0.35},
                      {"Power": "", "ConflictProgress": 1}, {"ConflictProgress": "x"}, "junk"]))
        self.assertEqual(state["location"]["conflict"], [
            {"power": "Nakato Kaine", "progress": 0.35}, {"power": "Zemina Torval", "progress": 0.2}])

    def test_cycle_days_start_at_0700_utc(self):
        state = powerplay.fresh_powerplay_state()
        total = 0
        for stamp, gain in (("2026-09-24T07:30:00Z", 100), ("2026-09-25T06:59:00Z", 50),
                            ("2026-09-25T07:00:00Z", 25), ("2026-09-30T20:00:00Z", 10)):
            total += gain
            state = powerplay.reduce_event(state, "PowerplayMerits", {
                "timestamp": stamp, "Power": "Edmund Mahon", "MeritsGained": gain, "TotalMerits": total})
        days = powerplay.build_workspace(state, now="2026-09-30T21:00:00Z")["cycle_days"]
        self.assertEqual([day["label"] for day in days], ["THU", "FRI", "SAT", "SUN", "MON", "TUE", "WED"])
        self.assertEqual([day["merits"] for day in days], [150, 25, 0, 0, 0, 0, 10])

    def test_hand_counted_assignments_step_from_the_dashboard(self):
        dashboard = _PowerplayDashboard()
        dashboard._handle_html_workspace_command({
            "page": "powerplay", "operation": "add_objective",
            "title": "Take Wolf 359", "kind": "system", "target": 3,
        })
        objective_id = dashboard.companion_state["powerplay"]["objectives"][0]["id"]
        for offset in (1, 1, 5):
            self.assertTrue(dashboard._handle_html_workspace_command({
                "page": "powerplay", "operation": "step_objective",
                "objective_id": objective_id, "offset": offset,
            }))
        objective = dashboard.companion_state["powerplay"]["objectives"][0]
        self.assertEqual((objective["current"], objective["complete"]), (3, True))
        self.assertFalse(dashboard._handle_html_workspace_command({
            "page": "powerplay", "operation": "step_objective",
            "objective_id": objective_id, "offset": 0,
        }))

    def test_page_assets_are_wired(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "web" / "dashboard"
        index = (root / "index.html").read_text(encoding="utf-8")
        app = (root / "app.js").read_text(encoding="utf-8")
        page = (root / "powerplay.js").read_text(encoding="utf-8")
        self.assertIn('href="powerplay.css"', index)
        self.assertIn('".pp-tabs button"', app)
        for operation in ("add_objective", "select_objective", "toggle_objective",
                          "delete_objective", "step_objective", "select_dossier", "copy_system"):
            self.assertIn(f'data-ws-op="{operation}"', page)
        # The assignment form keeps the ids app.js reads when ADD is pressed.
        for field in ("title", "kind", "system", "commodity", "target", "notes"):
            self.assertIn(f'id="powerplay-objective-{field}"', page)


if __name__ == "__main__":
    unittest.main()
