"""5.5.1.3 tester reports: readable text, overlays on scaled displays, the
survey overlay, the overlay frame-rate cap and the support bundle notice."""

import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.overlays.html_overlay_host import _WindowController
from voidcompass.overlays.survey_status_hud import build_survey_model

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class SettingsRegistrationTests(unittest.TestCase):
    def test_text_and_frame_settings_are_per_profile(self):
        for key in ("ui_text_scale_percent", "ui_text_min_px", "overlay_text_scale_percent", "overlay_frame_rate"):
            self.assertIn(key, config_module.PROFILE_VALUE_SETTINGS, key)

    def test_overlay_text_size_lives_in_settings_appearance_only(self):
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        index = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('key: "overlay_text_scale_percent", label: "Overlay text size"', app)
        self.assertNotIn('data-studio-setting="overlay_text_scale_percent"', index)
        self.assertIn('data-settings-section="appearance"', index, "Studio links to it")
        self.assertIn('data-studio-setting="overlay_frame_rate"', index)


class DisplayScalingTests(unittest.TestCase):
    def test_overlay_windows_grow_by_their_monitors_scaling(self):
        # 420 x 150 design pixels on a 150% display: WebView2 draws at 1.5x,
        # so the window must be 630 x 225 or the bottom third is cut off.
        controller = _WindowController("survey", object())
        with patch("voidcompass.overlays.html_overlay_host.monitor_scale", return_value=1.5), \
             patch("voidcompass.overlays.html_overlay_host._native_handle", return_value=99), \
             patch("voidcompass.overlays.html_overlay_host._apply_windows_geometry", return_value=True) as geometry, \
             patch("voidcompass.overlays.html_overlay_host._apply_windows_style", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._apply_webview_transparency"), \
             patch("voidcompass.overlays.html_overlay_host._windows_visibility", return_value=True), \
             patch("voidcompass.overlays.html_overlay_host._set_windows_visibility", return_value=True):
            controller.apply({"x": 2400, "y": 1200, "width": 420, "height": 150, "visible": True, "click_through": True})
        geometry.assert_called_with(controller.window, 2400, 1200, 630, 225)

    def test_the_scaling_helpers_leave_overlay_studios_display_list_alone(self):
        # They once set argument types on the shared ctypes.windll functions,
        # and Overlay Studio's own GetMonitorInfoW then failed: every display
        # merged into one. Run them first, as the survey overlay does.
        import os
        if os.name != "nt":
            self.skipTest("Windows display APIs")
        from voidcompass.core import display_scale
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        display_scale.room_below(100, 100)
        display_scale.monitor_scale(100, 100)
        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        import ctypes

        # SM_CMONITORS: how many displays Windows has. A failed listing falls
        # back to one desktop-wide display, which this catches on any setup
        # with two or more.
        expected = ctypes.WinDLL("user32").GetSystemMetrics(80)
        self.assertEqual(len(studio._html_overlay_monitors()), expected)

    def test_every_process_becomes_per_monitor_dpi_aware_first(self):
        entry = (ROOT / "VoidCompass.py").read_text(encoding="utf-8")
        dispatch = entry[entry.index("def _dispatch"):]
        self.assertLess(dispatch.index("enable_per_monitor_dpi()"), dispatch.index("--html-overlay-host"))

    def test_the_deck_zoom_reaches_webview2(self):
        from voidcompass.dashboard.html_dashboard_host import DashboardHost

        host = DashboardHost.__new__(DashboardHost)
        control = SimpleNamespace(ZoomFactor=1.0, BeginInvoke=lambda action: action())
        host._webview_control = control
        with patch.dict("sys.modules", {"System": SimpleNamespace(Action=lambda fn: fn)}):
            self.assertTrue(host.apply_zoom(125))
            self.assertFalse(host.apply_zoom(125), "only a change is applied")
        self.assertEqual(control.ZoomFactor, 1.25)


class SurveyOverlayTests(unittest.TestCase):
    def test_an_unmatched_focus_shows_the_system_instead_of_hiding(self):
        scan_items = [
            {"body_id": 3, "name": "Blaa A 1", "planet_class": "Icy body", "landable": True},
            {"body_id": 4, "name": "Blaa A 2", "planet_class": "Rocky body", "landable": True},
        ]
        signals = {"3": {"bio": 2}, "4": {"bio": 1}}
        model = build_survey_model("Blaa A", scan_items, focused_body_id=99, focused_body_name="Blaa A 9",
                                   scanned=2, total=5, body_signals=signals)
        self.assertIsNotNone(model)
        self.assertEqual(model["mode"], "system")
        focused = build_survey_model("Blaa A", scan_items, focused_body_id=3, body_signals=signals)
        self.assertEqual(focused["mode"], "body")


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        from tests.test_dashboard_overview_visuals import overview_state
        cls.overview_state = staticmethod(overview_state)
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

    def test_text_size_and_smallest_text_resize_the_deck(self):
        page = self.browser.new_page(viewport={"width": 1600, "height": 900})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        state = self.overview_state()

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/events":
                return route.fulfill(content_type="application/json", body='{"closing":true}')
            if path in {"/api/command", "/api/snapshot"}:
                return route.fulfill(content_type="application/json", body=json.dumps(state if path.endswith("snapshot") else {"accepted": True}))
            file = WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8")
                                     + "\nwindow.__text = (s, m) => applyTextSize(s, m);")
            return route.fulfill(path=str(file)) if file.is_file() else route.fulfill(status=404, body="")

        page.route("http://deck.test/**", serve)
        page.goto("http://deck.test/dashboard/index.html")
        page.wait_for_function("Boolean(window.__text)")
        sizes = """() => ({label: getComputedStyle(document.querySelector('.nav-item b')).fontSize,
                          nav: getComputedStyle(document.querySelector('.nav-item span')).fontSize,
                          brand: getComputedStyle(document.querySelector('.brand strong')).fontSize})"""
        standard = page.evaluate(sizes)
        page.evaluate("() => window.__text(100, 12)")
        lifted = page.evaluate(sizes)
        self.assertEqual(lifted["label"], "12px", "small labels rise to the floor")
        self.assertEqual(lifted["nav"], standard["nav"], "bigger text is left alone")
        page.evaluate("() => window.__text(150, 0)")
        scaled = page.evaluate(sizes)
        self.assertAlmostEqual(float(scaled["nav"][:-2]), float(standard["nav"][:-2]) * 1.5, places=1)
        self.assertEqual(scaled["brand"], standard["brand"], "the logo keeps its size")
        self.assertEqual(errors, [])

    def test_the_frame_cap_paces_every_animation_loop(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_content("<body></body>")
        page.add_script_tag(path=str(WEB / "assets" / "frame-cap.js"))
        counts = page.evaluate("""() => new Promise((resolve) => {
            window.VoidCompassFrameCap.set(15);
            let a = 0, b = 0;
            const loopA = () => { a += 1; requestAnimationFrame(loopA); };
            const loopB = () => { b += 1; requestAnimationFrame(loopB); };
            requestAnimationFrame(loopA); requestAnimationFrame(loopB);
            setTimeout(() => resolve([a, b]), 1000);
        })""")
        for count in counts:
            self.assertGreaterEqual(count, 10)
            self.assertLessEqual(count, 17)
        cancelled = page.evaluate("""() => new Promise((resolve) => {
            let ran = false; const id = requestAnimationFrame(() => { ran = true; });
            cancelAnimationFrame(id); setTimeout(() => resolve(ran), 300);
        })""")
        self.assertFalse(cancelled)


class SupportBundleTests(unittest.TestCase):
    def test_the_bundle_is_reported_in_the_deck_not_a_blocking_box(self):
        from voidcompass.dashboard.dashboard import MainDashboard

        dashboard = MainDashboard.__new__(MainDashboard)
        dashboard.config = {}
        dashboard._tools = {}
        dashboard._html_profile_transient = lambda name, default: dashboard._tools.setdefault(name, dict(default))
        dashboard._adaptive_health_snapshot = lambda: {}
        dashboard._ui_post = lambda fn, **_: fn()
        dashboard.add_event_feed_entry = Mock()
        dashboard._schedule_html_dashboard_publish = Mock()
        started = []
        with patch("voidcompass.dashboard.dashboard.create_support_bundle", return_value="C:/bundles/b.zip"), \
             patch("voidcompass.dashboard.dashboard.threading.Thread",
                   side_effect=lambda target, **_: SimpleNamespace(start=lambda: started.append(target()))), \
             patch("subprocess.Popen") as explorer, \
             patch("voidcompass.core.native_services.messagebox.showinfo") as box:
            dashboard._create_support_bundle()
        box.assert_not_called()
        explorer.assert_called_once()
        self.assertIn("b.zip", dashboard.add_event_feed_entry.call_args.args[1])
        self.assertEqual(dashboard._tools["_html_settings_tool_state"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()


class DeckWindowGeometryTests(unittest.TestCase):
    """5.5.1.4: the deck window is saved and restored in real screen pixels.

    pywebview divides by the scaling of the monitor the window is on when it
    reports a position, and multiplies by the scaling of the monitor it is
    created on when it restores one, so on mixed-scaling setups the deck
    reopened in the wrong place."""

    def host(self):
        from voidcompass.dashboard.html_dashboard_host import DashboardHost

        host = DashboardHost("http://127.0.0.1:1/?token=t")
        host._schedule_geometry_post = Mock()
        return host

    def test_moves_and_resizes_record_the_windows_real_rectangle(self):
        host = self.host()
        host._hwnd = 42
        real = {"x": 3840, "y": 100, "width": 2250, "height": 1470}
        with patch("voidcompass.dashboard.html_dashboard_host._native_rect", return_value=real):
            host.moved(2560, 66)          # pywebview's scaled numbers are ignored
            host.resized(1500, 980)
        self.assertEqual(host._geometry, {**real, "physical": True})
        with patch("voidcompass.dashboard.html_dashboard_host._native_rect",
                   return_value={"x": -32000, "y": -32000, "width": 160, "height": 28}):
            host.moved(-32000, -32000)    # minimizing keeps the last real place
        self.assertEqual(host._geometry["x"], 3840)

    def test_the_saved_rectangle_is_applied_before_the_window_shows(self):
        host = self.host()
        host._physical_rect = {"x": 3840, "y": 100, "width": 2250, "height": 1470}
        window = SimpleNamespace(native=SimpleNamespace(Handle=SimpleNamespace(ToInt64=lambda: 77)))
        with patch("voidcompass.dashboard.html_dashboard_host._set_native_rect") as place:
            host.before_show(window)
        place.assert_called_once_with(77, 3840, 100, 2250, 1470)

    def test_the_runtime_keeps_the_real_pixel_flag(self):
        from voidcompass.dashboard.html_dashboard_runtime import HtmlDashboardRuntime, _geometry_payload

        self.assertTrue(_geometry_payload("2250x1470+3840+100", physical=True)["physical"])
        self.assertFalse(_geometry_payload("1720x1120")["physical"], "older saves stay pywebview's")
        runtime = HtmlDashboardRuntime.__new__(HtmlDashboardRuntime)
        runtime.window_geometry = {}
        runtime._receive_command({"action": "window_geometry", "x": 3840, "y": 100,
                                  "width": 2250, "height": 1470, "physical": True})
        self.assertTrue(runtime.geometry_is_physical())
        self.assertEqual(runtime.geometry_string(), "2250x1470+3840+100")
        self.assertIn("dashboard_window_physical", config_module.PROFILE_VALUE_SETTINGS)
