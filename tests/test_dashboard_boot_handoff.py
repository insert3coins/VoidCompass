from pathlib import Path
import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from voidcompass.dashboard.dashboard import MainDashboard, STARTUP_BROWSER_ACK_TIMEOUT_MS
from voidcompass.dashboard.html_dashboard_host import DashboardHost, HOST_RELAUNCH_EXIT_CODE
from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime

APP_JS = Path(__file__).resolve().parents[1] / "web" / "dashboard" / "app.js"


class _Window:
    def __init__(self):
        self.scripts = []
        self.results = iter(("pending", "ready"))

    def evaluate_js(self, script):
        self.scripts.append(script)
        return next(self.results)


class _PageWindow:
    """The attributes webview_bootstrap records on a pywebview window."""

    def __init__(self):
        self.loads = []
        self._voidcompass_navigation_failed = False
        self._voidcompass_navigation_completed_at = 0.0

    def load_url(self, url):
        self.loads.append(url)

    def completed(self, at, failed=False):
        self._voidcompass_navigation_completed_at = at
        self._voidcompass_navigation_failed = failed


class _Root:
    """Records scheduled callbacks so a test can fire them by hand."""

    def __init__(self, **attrs):
        self.__dict__.update(attrs)
        self.jobs = {}
        self.cancelled = []

    def call_later(self, delay, callback):
        job = len(self.jobs) + 1
        self.jobs[job] = (delay, callback)
        return job

    def cancel(self, job):
        self.cancelled.append(job)

    def scheduled(self, callback_name):
        return [job for job, (_delay, callback) in self.jobs.items()
                if getattr(callback, "__name__", "") == callback_name]


def _ready_backend(boot):
    """A dashboard whose journal/history startup is done, awaiting the browser."""
    app = MainDashboard.__new__(MainDashboard)
    app.root = _Root(_voidcompass_startup_splash=SimpleNamespace(_voidcompass_boot=boot))
    app._startup_boot_handoff_job = None
    app._startup_overlay_handoff_pending = None
    app._startup_live_tail_ready = True
    app._startup_presentation_ready = True
    app._startup_history_pending = set()
    app._startup_boot_update = Mock()
    app._trace_bump = Mock()
    return app


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
        root = _Root(
            _voidcompass_startup_splash=SimpleNamespace(_voidcompass_boot=boot),
            _voidcompass_html_overlay_runtime=overlay_runtime,
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

        fallback = root.scheduled("_startup_handoff_ack_timeout")
        self.assertEqual(len(fallback), 1)
        app._complete_startup_overlay_handoff()
        # The browser answered in time, so its fallback must not fire later.
        self.assertIn(fallback[0], root.cancelled)
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


    def test_startup_completes_when_browser_never_confirms_boot_frame(self):
        boot = SimpleNamespace(_ready_emitted=False)
        app = _ready_backend(boot)

        app._maybe_complete_startup_presentation()
        app._maybe_complete_startup_presentation()
        waits = app.root.scheduled("_startup_boot_ack_timeout")
        self.assertEqual(len(waits), 1, "one bounded wait, not one per call")
        self.assertEqual(app.root.jobs[waits[0]][0], STARTUP_BROWSER_ACK_TIMEOUT_MS)
        self.assertEqual(app.root.scheduled("_finish_startup_presentation"), [])

        app.root.jobs[waits[0]][1]()
        app._trace_bump.assert_any_call("startup_browser_ack_timeout")
        self.assertEqual(len(app.root.scheduled("_finish_startup_presentation")), 1)
        app._startup_boot_update.assert_called_with(
            "VOID COMPASS LIVE",
            "Journal, survey history and overlays are synchronized",
            1.0,
        )

    def test_browser_confirmation_skips_the_fallback_and_late_timer_is_inert(self):
        boot = SimpleNamespace(_ready_emitted=False)
        app = _ready_backend(boot)
        app._maybe_complete_startup_presentation()
        wait = app.root.scheduled("_startup_boot_ack_timeout")[0]

        boot._ready_emitted = True
        app._maybe_complete_startup_presentation()
        self.assertEqual(len(app.root.scheduled("_finish_startup_presentation")), 1)
        app.root.jobs[wait][1]()
        self.assertFalse(getattr(app, "_startup_boot_ack_bypassed", False))
        self.assertEqual(len(app.root.scheduled("_finish_startup_presentation")), 1)

    def test_overlays_release_when_browser_never_confirms_reveal(self):
        app = MainDashboard.__new__(MainDashboard)
        app.root = _Root()
        app._startup_overlay_handoff_pending = {"hud"}
        app._trace_bump = Mock()

        def release():
            app._startup_overlay_handoff_pending = None

        app._complete_startup_overlay_handoff = Mock(side_effect=release)
        app._startup_handoff_ack_timeout()
        app._trace_bump.assert_called_once_with("startup_browser_handoff_timeout")
        app._complete_startup_overlay_handoff.assert_called_once_with()
        app._startup_handoff_ack_timeout()
        app._complete_startup_overlay_handoff.assert_called_once_with()

    def test_host_reloads_failed_or_silent_page_until_its_client_starts(self):
        host = DashboardHost("http://127.0.0.1:8765/?token=test")
        host.window = page = _PageWindow()
        with patch("builtins.print"):
            self.assertFalse(host._service_page_recovery(0, 5.0))
            page.completed(10.0, failed=True)
            host._service_page_recovery(0, 10.3)
            self.assertEqual(page.loads, [])
            host._service_page_recovery(0, 10.6)
            self.assertEqual(page.loads, ["http://127.0.0.1:8765/?token=test&host_retry=1"])
            self.assertFalse(page._voidcompass_navigation_failed)
            # The reload is still in flight: the old completion is not reused.
            host._service_page_recovery(0, 30.0)
            self.assertEqual(len(page.loads), 1)
            # Loaded, but its client never reached the API.
            page.completed(31.0)
            host._service_page_recovery(0, 36.9)
            self.assertEqual(len(page.loads), 1)
            host._service_page_recovery(0, 37.1)
            self.assertEqual(page.loads[-1], "http://127.0.0.1:8765/?token=test&host_retry=2")
            page.completed(42.0)
            host._service_page_recovery(3, 42.2)
        self.assertTrue(host.page_started)
        page.completed(50.0, failed=True)
        host._service_page_recovery(3, 90.0)
        self.assertEqual(len(page.loads), 2, "a running page is never reloaded")

    def test_host_reload_budget_is_bounded(self):
        host = DashboardHost("http://127.0.0.1:8765/?token=test")
        host.window = page = _PageWindow()
        now = 0.0
        with patch("builtins.print"):
            for _attempt in range(8):
                now += 1.0
                page.completed(now, failed=True)
                now += 7.0
                host._service_page_recovery(0, now)
        self.assertEqual(len(page.loads), 4)
        self.assertTrue(host.page_gave_up)

    def test_renderer_failure_requests_a_new_host_without_closing_the_app(self):
        host = DashboardHost("http://127.0.0.1:8765/?token=test")
        host.window = page = _PageWindow()
        page._voidcompass_renderer_failed = True
        with patch("builtins.print"):
            self.assertTrue(host._service_page_recovery(0, 1.0))
        self.assertTrue(host.relaunch_requested)
        self.assertEqual(page.loads, [])
        host.post = Mock()
        host.closed()
        self.assertNotIn("window_closed", [call.args[0] for call in host.post.call_args_list])

    def test_runtime_relaunches_a_failed_host_a_bounded_number_of_times(self):
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime.root = _Root()
        runtime._disposed = False
        runtime._host_watchdog_job = None
        runtime._host_exit_seen_at = 0.0
        runtime._host_relaunches = 0
        runtime._host_log = None
        runtime._command_pump_last_tick = 0.0
        runtime._close_from_window = Mock()
        failed = SimpleNamespace(poll=lambda: HOST_RELAUNCH_EXIT_CODE)
        runtime.process = failed
        launches = []

        def launch():
            launches.append(1)
            runtime.process = failed

        runtime._launch = launch
        with patch("voidcompass.core.native_services.messagebox.showerror") as error, \
                patch("voidcompass.dashboard.html_dashboard_runtime.logging.error"):
            runtime._check_host_process()
            runtime._check_host_process()
            self.assertEqual(len(launches), 2)
            error.assert_not_called()
            # Out of relaunches: the ordinary unexpected-exit path takes over.
            runtime._check_host_process()
            runtime._host_exit_seen_at -= 1.0
            runtime._check_host_process()
        self.assertEqual(len(launches), 2)
        error.assert_called_once()
        runtime._close_from_window.assert_called_once_with()


class BootMilestoneBrowserTests(unittest.TestCase):
    """The real milestone code in a browser whose frames never arrive."""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_milestones_post_when_a_minimized_window_stops_frames(self):
        source = APP_JS.read_text(encoding="utf-8")
        milestones = source[source.index("function postBootMilestone(action)"):
                            source.index("function reportClientError(")]
        page = self.browser.new_page()
        try:
            page.set_content("<div id='boot'></div>")
            page.add_script_tag(content="""
              window.posted = [];
              window.requestAnimationFrame = () => 0;  // a minimized WebView2
              window.fetch = (_url, options) => {
                window.posted.push(JSON.parse(options.body).action);
                return Promise.resolve({ok: true});
              };
              let bootPresentedRequested = false, bootHandoffRequested = false;
              const byId = id => document.getElementById(id);
              const apiUrl = path => path;
            """ + milestones + """
              acknowledgeBootPresented();
              window.handoff = () => {
                byId('boot').hidden = true;
                document.body.classList.add('ready');
                acknowledgeBootHandoff();
              };
            """)
            # Poll on a timer: the default polling rides the stubbed-out frames.
            page.wait_for_function("window.posted.includes('boot_presented')",
                                   polling=100, timeout=3000)
            page.evaluate("window.handoff()")
            page.wait_for_function("window.posted.includes('boot_handoff_complete')",
                                   polling=100, timeout=3000)
            self.assertEqual(page.evaluate("window.posted"), ["boot_presented", "boot_handoff_complete"])
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
