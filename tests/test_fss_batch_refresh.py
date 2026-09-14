import threading
import unittest

from voidcompass.dashboard.dashboard import MainDashboard


class _Root:
    def call_later(self, _delay, callback):
        callback()


class _Connection:
    def commit(self):
        pass

    def rollback(self):
        pass


class _Waypoints:
    waypoints = []

    @staticmethod
    def get_next_waypoint(_system):
        return None


class FssBatchRefreshTests(unittest.TestCase):
    @staticmethod
    def _dashboard():
        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.batch_mode = False
        dashboard.db_lock = threading.Lock()
        dashboard.conn = _Connection()
        dashboard.root = _Root()
        dashboard.scanned = 10
        dashboard.total = 11
        dashboard.current_sys = "---"
        dashboard.config = {}
        dashboard.waypoint_manager = _Waypoints()
        dashboard.dashboard_refresh_full_pending = False
        dashboard._startup_restore_active = False
        dashboard._startup_restore_ui_pending = False
        dashboard._refresh_cockpit_brain = lambda **_kwargs: None
        dashboard.update_waypoint_display = lambda: None
        dashboard._refresh_commander_profile_window = lambda: None
        dashboard._refresh_value_ledger_window = lambda: None
        dashboard._refresh_colonisation_planner_window = lambda: None
        dashboard._refresh_exploration_window = lambda: None
        dashboard._refresh_bgs_window = lambda: None
        # Startup-presentation choreography and overlay consumers added since
        # this fake was written; the tests only assert refresh scheduling.
        dashboard.station_info_hud = None
        dashboard.specialists_window = None
        dashboard._trace_bump = lambda *_args, **_kwargs: None
        dashboard._startup_boot_update = lambda *_args, **_kwargs: None
        dashboard._finalize_startup_sampling_replay = lambda: None
        dashboard._restore_current_system_bio_completions = lambda: False
        dashboard._request_db_commit = lambda *_args, **_kwargs: None
        dashboard._freeze_startup_heap = lambda: None
        dashboard._apply_adaptive_overlay_scene = lambda: None
        dashboard._adaptive_startup_mode = lambda: None
        dashboard._hold_startup_presentation = lambda: None
        dashboard._publish_expedition_resume_briefing = lambda: None
        dashboard._update_main_window_title = lambda: None
        dashboard.fetch_system_traffic = lambda _system: None
        dashboard.load_system_from_db = lambda *_args, **_kwargs: None

        def _ui_post(fn, *_args, **_kwargs):
            return fn(*_args)

        dashboard._ui_post = _ui_post
        return dashboard

    def test_completed_fss_batch_refreshes_survey_status_once(self):
        dashboard = self._dashboard()
        dashboard.is_first_load = False
        dashboard.refresh_count = 0

        def process_event(_event):
            dashboard.scanned = dashboard.total

        def refresh_progress():
            dashboard.refresh_count += 1

        dashboard.process_event = process_event
        dashboard.update_dashboard_ui = lambda: None
        dashboard.update_hud = lambda: None
        dashboard._refresh_survey_status_progress = refresh_progress
        dashboard.process_batch([{"type": "FSSAllBodiesFound"}])

        self.assertEqual((dashboard.scanned, dashboard.total), (11, 11))
        self.assertEqual(dashboard.refresh_count, 1)

    def test_startup_batches_draw_only_after_final_marker(self):
        dashboard = self._dashboard()
        dashboard.is_first_load = True
        dashboard.refresh_count = 0
        dashboard.dashboard_count = 0
        dashboard.hud_count = 0
        dashboard.process_event = lambda _event: None
        dashboard._refresh_survey_status_progress = lambda: setattr(
            dashboard, "refresh_count", dashboard.refresh_count + 1,
        )
        dashboard.update_dashboard_ui = lambda: setattr(
            dashboard, "dashboard_count", dashboard.dashboard_count + 1,
        )
        dashboard.update_hud = lambda: setattr(
            dashboard, "hud_count", dashboard.hud_count + 1,
        )

        dashboard.process_batch([{"type": "Scan", "startup_catchup": True}])
        self.assertTrue(dashboard._startup_restore_active)
        self.assertEqual((dashboard.refresh_count, dashboard.dashboard_count, dashboard.hud_count), (0, 0, 0))

        dashboard.process_batch([{
            "type": "Location", "startup_catchup": True,
            "startup_catchup_final": True,
        }])
        self.assertFalse(dashboard._startup_restore_active)
        self.assertEqual(dashboard.refresh_count, 1)
        self.assertEqual(dashboard.dashboard_count, 1)
        self.assertEqual(dashboard.hud_count, 1)


if __name__ == "__main__":
    unittest.main()
