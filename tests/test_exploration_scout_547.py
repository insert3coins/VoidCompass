from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.exploration.exploration_scout import (
    normalise_body_prospects,
    normalise_scout_form,
    normalise_value_route,
    system_audit,
)
from voidcompass.exploration.exploration_intelligence import system_completion
from voidcompass.services.spansh import SpanshError, exploration_body_search


ROOT = Path(__file__).resolve().parents[1]


class _ImmediateThread:
    def __init__(self, target, **_kwargs):
        self.target = target

    def start(self):
        self.target()


class _ScoutDashboard(HtmlDashboardMixin):
    def __init__(self):
        self.config = {"active_commander_profile": "test-cmdr"}
        self.current_sys = "Sol"
        self._tools = {}
        self.events = []
        self.publish_count = 0

    def _html_profile_transient(self, name, defaults):
        return self._tools.setdefault(name, {"profile": "test-cmdr", **defaults})

    def _persist_config(self):
        return None

    def add_event_feed_entry(self, kind, detail, severity="INFO"):
        self.events.append((kind, detail, severity))

    def _schedule_html_dashboard_publish(self, **_kwargs):
        self.publish_count += 1

    def _ui_post(self, callback, **_kwargs):
        callback()


class ExplorationScout547Tests(unittest.TestCase):
    def test_body_prospects_rank_matching_known_signals_and_keep_provenance(self):
        payload = {
            "count": 2,
            "reference": {"name": "Sol"},
            "results": [
                {
                    "system_name": "Far Bio",
                    "name": "Far Bio A 1",
                    "distance": 80,
                    "signals": [{"name": "Biological", "count": 2}],
                    "estimated_mapping_value": 100_000,
                    "signals_updated_at": "2026-09-10T12:00:00Z",
                },
                {
                    "system_name": "Near Bio",
                    "name": "Near Bio 2",
                    "system_id64": 42,
                    "system_x": 1,
                    "system_y": 2,
                    "system_z": 3,
                    "distance": 5,
                    "distance_to_arrival": 740,
                    "signals": [{"name": "Biological", "count": 4}],
                    "landmarks": [{"type": "Biological", "subtype": "Aleoida"}],
                },
                {
                    "system_name": "Wrong Signal",
                    "name": "Wrong Signal 1",
                    "signals": [{"name": "Guardian", "count": 8}],
                },
            ],
        }

        result = normalise_body_prospects(payload, "biology", searched_at="2026-09-15T00:00:00Z")

        self.assertEqual(result["reference"], "Sol")
        self.assertEqual(result["catalogue_count"], 2)
        self.assertEqual([row["system"] for row in result["results"]], ["Near Bio", "Far Bio"])
        self.assertEqual(result["results"][0]["coords"], [1.0, 2.0, 3.0])
        self.assertIn("known community records", result["evidence_note"].casefold())
        self.assertEqual(result["searched_at"], "2026-09-15T00:00:00Z")

    def test_value_route_explains_estimates_without_claiming_discovery(self):
        result = normalise_value_route([{
            "system": "Worthwhile",
            "jumps": 2,
            "total_value": 1_600_000,
            "bodies": [{
                "name": "Worthwhile 3", "type": "Water world",
                "terraformable": True, "dist_ls": 410, "map_value": 1_600_000,
            }],
        }], reference="Sol")

        row = result["results"][0]
        self.assertEqual(row["system"], "Worthwhile")
        self.assertEqual(row["body"], "Worthwhile 3")
        self.assertEqual(row["route_index"], 1)
        self.assertTrue(any("terraformable" in reason for reason in row["reasons"]))
        self.assertIn("not guaranteed", result["evidence_note"])

    def test_scout_form_normalisation_is_shared_and_bounded(self):
        form = normalise_scout_form({
            "mode": "unknown", "radius": 99999, "min_signals": 0,
            "min_value": 999_999_999, "max_results": 0, "jump_range": -4,
        }, current_system="Sol")

        self.assertEqual(form, {
            "reference": "Sol", "mode": "biology", "radius": 10_000,
            "min_signals": 1, "min_value": 100_000_000,
            "max_results": 1, "jump_range": 1.0,
        })

    def test_system_audit_uses_shared_completion_and_survey_queue_status(self):
        scan_items = [
            {"name": "A 1", "dss_complete": True, "bio_count": 2, "dss_reward": 900_000},
            {"name": "A 2", "geo_count": 1},
        ]
        queue = {
            "rows": [
                {"body": "A 1", "status": "complete"},
                {"body": "A 2", "status": "pending"},
            ],
            "next": {"body": "A 2", "status": "pending"},
        }

        completion = system_completion(
            scan_items, scanned=2, total=2, fss_complete=True,
            current_system="Test",
        )
        audit = system_audit(completion, queue)

        self.assertEqual(audit["pending"], 1)
        self.assertEqual(audit["next"], "A 2")
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["known_bodies"], completion["known_bodies"])
        self.assertEqual(audit["bio_targets"], completion["bio_targets"])
        self.assertEqual(audit["source"], "Elite journal")

    @patch("voidcompass.services.spansh.requests.post")
    def test_spansh_signal_search_is_bounded_and_normalised(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {
            "count": 1,
            "reference": {"name": "Sol"},
            "results": [{
                "system_name": "Known Site", "name": "Known Site 1",
                "signals": [{"name": "Guardian", "count": 1}],
            }],
        }
        post.return_value = response

        result = exploration_body_search("Sol", "guardian", 250, 1, 12)

        self.assertEqual(result["results"][0]["system"], "Known Site")
        request = post.call_args.kwargs["json"]
        self.assertEqual(request["reference_system"], "Sol")
        self.assertEqual(request["filters"]["signals"][0]["name"], "Guardian")
        self.assertEqual(request["filters"]["distance"]["max"], 250)
        self.assertEqual(request["size"], 12)

    def test_value_mode_cannot_use_signal_endpoint(self):
        with self.assertRaises(SpanshError):
            exploration_body_search("Sol", "value")

    @patch("voidcompass.dashboard.html_explore_workspace.threading.Thread", _ImmediateThread)
    @patch("voidcompass.dashboard.html_explore_workspace.riches_route")
    def test_workspace_search_runs_off_ui_boundary_and_retains_results(self, riches):
        riches.return_value = [{
            "system": "Valuable Stop", "jumps": 1, "total_value": 800_000,
            "bodies": [{"name": "Valuable Stop 2", "map_value": 800_000}],
        }]
        dashboard = _ScoutDashboard()

        accepted = dashboard._handle_html_workspace_command({
            "page": "explore", "operation": "scout_search", "reference": "Sol",
            "mode": "value", "radius": 60, "min_value": 500_000,
            "max_results": 10, "jump_range": 35,
        })

        state = dashboard._tools["_html_exploration_scout_state"]
        self.assertTrue(accepted)
        self.assertEqual(state["status"], "ready")
        self.assertEqual(state["results"][0]["system"], "Valuable Stop")
        self.assertEqual(dashboard.config["exploration_scout_form"]["mode"], "value")
        self.assertGreaterEqual(dashboard.publish_count, 2)

    def test_explore_workspace_contains_scout_controls_and_source_language(self):
        script = "\n".join(
            (ROOT / "web" / "dashboard" / name).read_text(encoding="utf-8")
            for name in ("app.js", "explore.js")
        )
        styles = "\n".join(
            (ROOT / "web" / "dashboard" / name).read_text(encoding="utf-8")
            for name in ("styles.css", "explore.css")
        )

        self.assertIn("EXPLORATION SCOUT", script)
        self.assertIn('data-ws-op="scout_search"', script)
        self.assertIn('data-ws-op="scout_add_waypoint"', script)
        self.assertIn('data-ws-op="scout_add_objective"', script)
        self.assertIn("scout.evidence_note", script)
        self.assertIn(".exploration-scout", styles)

    def test_dashboard_domains_remain_split_into_dedicated_modules(self):
        html_dashboard = (
            ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py"
        ).read_text(encoding="utf-8")
        dashboard = (
            ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py"
        ).read_text(encoding="utf-8")
        app_script = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("def _html_explore_workspace", html_dashboard)
        self.assertNotIn("def _html_overlay_desktop", html_dashboard)
        self.assertNotIn("def _exploration_intelligence_snapshot", dashboard)
        self.assertNotIn("function renderExploreWorkspace(data)", app_script)
        for relative in (
            "src/voidcompass/dashboard/html_explore_workspace.py",
            "src/voidcompass/dashboard/html_overlay_studio.py",
            "src/voidcompass/dashboard/dashboard_exploration_mixin.py",
            "web/dashboard/explore.js",
            "web/dashboard/explore.css",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_explore_workspace_serialises_audit_codex_and_search_defaults(self):
        dashboard = _ScoutDashboard()
        dashboard.current_coords = [0, 0, 0]
        dashboard.scanned = 1
        dashboard.total = 1
        dashboard.scan_total_confirmed = True
        dashboard.scan_items = [{
            "name": "Sol A", "body_id": 0, "is_star": True, "star_type": "G",
        }]

        workspace = dashboard._html_explore_workspace()

        self.assertEqual(workspace["scout"]["reference"], "Sol")
        self.assertEqual(workspace["scout"]["audit"]["source"], "Elite journal")
        self.assertIn("region", workspace["scout"]["codex"])
        self.assertEqual(workspace["scout"]["modes"]["biology"], "Biological signals")


if __name__ == "__main__":
    unittest.main()
