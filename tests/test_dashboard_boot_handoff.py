import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.dashboard.html_dashboard_host import DashboardHost
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime


class _Window:
    def __init__(self):
        self.scripts = []
        self.results = iter(("pending", "ready"))

    def evaluate_js(self, script):
        self.scripts.append(script)
        return next(self.results)


class DashboardBootHandoffTests(unittest.TestCase):
    def test_browser_milestones_gate_backend_startup_and_overlay_release(self):
        app = SimpleNamespace(
            _maybe_complete_startup_presentation=Mock(),
            _complete_startup_overlay_handoff=Mock(),
        )
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime.root = SimpleNamespace(call_later=lambda _delay, _callback: 1)
        runtime.app = app
        runtime._commands = queue.SimpleQueue()
        runtime._command_job = None
        runtime._disposed = False
        runtime._boot = {"active": True}
        runtime._ready_emitted = False
        runtime._host_log = None

        self.assertTrue(runtime._receive_command({"action": "boot_presented"}))
        runtime._drain_commands()
        self.assertTrue(runtime._ready_emitted)
        app._maybe_complete_startup_presentation.assert_called_once_with()

        self.assertTrue(runtime._receive_command({"action": "boot_handoff_complete"}))
        runtime._drain_commands()
        app._complete_startup_overlay_handoff.assert_not_called()
        runtime._boot["active"] = False
        self.assertTrue(runtime._receive_command({"action": "boot_handoff_complete"}))
        runtime._drain_commands()
        app._complete_startup_overlay_handoff.assert_called_once_with()

    def test_overlay_curtain_stays_held_until_browser_handoff(self):
        boot = SimpleNamespace(stop=Mock())
        overlay_runtime = SimpleNamespace(release_startup_hold=Mock())
        root = SimpleNamespace(
            _voidcompass_startup_splash=SimpleNamespace(_voidcompass_boot=boot),
            _voidcompass_html_overlay_runtime=overlay_runtime,
            call_later=lambda _delay, _callback: 1,
        )
        app = MainDashboard.__new__(MainDashboard)
        app.root = root
        app._startup_overlay_restore = {"survey_status_hud"}
        app._startup_overlay_handoff_pending = None
        app._startup_boot_handoff_job = None
        app._startup_boot_journal_timeout_job = None
        app._startup_boot_history_timeout_job = None
        app._trace_bump = Mock()
        app._hold_startup_presentation = Mock()
        app._persistent_startup_overlay_names = Mock(return_value={"hud"})
        app._release_startup_overlay_curtain = Mock()
        app._restore_overlay_hotkey_windows = Mock()
        app._enforce_overlay_hotkey_visibility = Mock()
        app._sync_html_overlay_windows = Mock()
        app._resync_startup_html_overlays = Mock()
        app._reapply_overlay_positions = Mock()

        app._finish_startup_presentation()
        boot.stop.assert_called_once_with()
        app._release_startup_overlay_curtain.assert_not_called()
        overlay_runtime.release_startup_hold.assert_not_called()
        self.assertEqual(app._startup_overlay_handoff_pending,
                         {"survey_status_hud", "hud"})

        app._complete_startup_overlay_handoff()
        app._release_startup_overlay_curtain.assert_called_once_with()
        app._restore_overlay_hotkey_windows.assert_called_once_with(
            {"survey_status_hud", "hud"}, force_show=False,
        )
        overlay_runtime.release_startup_hold.assert_called_once_with()
        self.assertIsNone(root._voidcompass_startup_splash)

    def test_native_host_waits_for_browser_hold_and_only_requests_recovery(self):
        host = DashboardHost("http://127.0.0.1:8765/?token=test")
        host.window = _Window()

        host._service_boot_release(True, False, 100.0)
        host._service_boot_release(False, False, 101.0)
        host._service_boot_release(False, False, 107.9)
        self.assertEqual(host.window.scripts, [])

        host._service_boot_release(False, False, 108.1)
        self.assertEqual(len(host.window.scripts), 1)
        self.assertIn("voidcompass:boot-recover", host.window.scripts[0])
        self.assertNotIn("classList.add('ready')", host.window.scripts[0])
        self.assertNotIn("hidden=true", host.window.scripts[0])

        host._service_boot_release(False, False, 108.5)
        self.assertEqual(len(host.window.scripts), 1)
        host._service_boot_release(False, False, 109.2)
        self.assertTrue(host.boot_released)
        self.assertEqual(len(host.window.scripts), 2)

        host._service_boot_release(True, False, 110.0)
        self.assertFalse(host.boot_released)
        self.assertEqual(host.boot_release_started_at, 0.0)


if __name__ == "__main__":
    unittest.main()
