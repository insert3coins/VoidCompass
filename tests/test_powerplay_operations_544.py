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


if __name__ == "__main__":
    unittest.main()
