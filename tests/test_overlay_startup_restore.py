import unittest

from dashboard import MainDashboard
from global_hotkeys import OVERLAY_HOTKEY_SPECS


class _Window:
    def __init__(self):
        self.deiconified = False
        self.topmost = False
        self.lifted = False

    def winfo_exists(self):
        return True

    def state(self):
        return "withdrawn"

    def deiconify(self):
        self.deiconified = True

    def withdraw(self):
        self.deiconified = False

    def attributes(self, key, value):
        if key == "-topmost":
            self.topmost = bool(value)

    def lift(self):
        self.lifted = True


class _SurveyOverlay:
    """Mimics SurveyStatusHUD's startup presentation protocol."""

    def __init__(self, window, pending=False, has_content=True):
        self.window = window
        self._startup_pending_visible = pending
        self._suppressed = False
        self.has_content = has_content
        self.released = 0

    def release_startup_visibility(self):
        self.released += 1
        if not self._startup_pending_visible or self._suppressed or not self.has_content:
            return False
        self.window.deiconify()
        self._startup_pending_visible = False
        return True

    def show(self):
        if self._suppressed or not self.has_content:
            return False
        self.window.deiconify()
        return True


class _PlainOverlay:
    pass


class _Harness:
    _restore_overlay_hotkey_windows = (
        MainDashboard._restore_overlay_hotkey_windows
    )

    def __init__(self, items):
        self._items = list(items)
        self._adaptive_hidden_overlays = set()
        self._overlay_hotkey_hidden = set()

    def _overlay_hotkey_window_items(self):
        return self._items


class OverlayStartupRestoreTests(unittest.TestCase):
    def test_every_managed_overlay_has_a_settings_hotkey(self):
        managed = {attr for attr, _x_key, _y_key in MainDashboard._OVERLAY_POSITION_SPECS}
        hotkey_managed = {attr for _action, _key, _label, attr in OVERLAY_HOTKEY_SPECS if attr}
        self.assertEqual(hotkey_managed, managed)

    def _harness(self, survey_pending=False, has_content=True):
        survey_window = _Window()
        plain_window = _Window()
        harness = _Harness([
            ("survey_status_hud", survey_window),
            ("cargo_hud", plain_window),
        ])
        harness.survey_status_hud = _SurveyOverlay(
            survey_window, pending=survey_pending, has_content=has_content,
        )
        harness.cargo_hud = _PlainOverlay()
        return harness, survey_window, plain_window

    def test_startup_handoff_skips_survey_that_hid_itself(self):
        harness, survey_window, plain_window = self._harness(survey_pending=False)
        harness._restore_overlay_hotkey_windows(
            {"survey_status_hud", "cargo_hud"}, force_show=False,
        )
        self.assertFalse(survey_window.deiconified)
        self.assertTrue(plain_window.deiconified)

    def test_startup_handoff_restores_pending_survey_via_protocol(self):
        harness, survey_window, _plain_window = self._harness(survey_pending=True)
        harness._restore_overlay_hotkey_windows(
            {"survey_status_hud"}, force_show=False,
        )
        self.assertEqual(harness.survey_status_hud.released, 1)
        self.assertTrue(survey_window.deiconified)

    def test_explicit_force_show_maps_survey_with_content(self):
        harness, survey_window, _plain_window = self._harness(survey_pending=False, has_content=True)
        harness._restore_overlay_hotkey_windows({"survey_status_hud"})
        self.assertTrue(survey_window.deiconified)

    def test_explicit_force_show_skips_survey_without_content(self):
        harness, survey_window, _plain_window = self._harness(survey_pending=False, has_content=False)
        harness._restore_overlay_hotkey_windows({"survey_status_hud"})
        self.assertFalse(survey_window.deiconified)

    def _ground_harness(self, *, active=True, on_planet=True, held=False):
        dashboard = MainDashboard.__new__(MainDashboard)
        window = _Window()
        dashboard.root = type(
            "Root", (), {"_voidcompass_startup_presentation_held": held},
        )()
        dashboard._startup_presentation_held = held
        dashboard._overlay_hotkey_hidden = set()
        dashboard.target_latlon_active = active
        dashboard.target_lat = 32.328 if active else None
        dashboard.target_lon = 108.838 if active else None
        dashboard.on_planet = on_planet
        dashboard.ground_popup_enabled = True
        dashboard.ground_popup = window
        dashboard._ground_popup_visible = False
        dashboard.current_latitude = 32.0
        dashboard.current_longitude = 108.0
        dashboard.current_planet_radius = 1_000_000
        dashboard.current_heading = 90.0
        dashboard._overlay_hotkey_window_items = lambda: [("ground_popup", window)]
        return dashboard, window

    def test_startup_handoff_never_maps_planet_waypoint_through_curtain(self):
        dashboard, window = self._ground_harness(held=True)
        dashboard._restore_overlay_hotkey_windows({"ground_popup"})
        self.assertFalse(window.deiconified)
        self.assertFalse(dashboard._ground_popup_visible)

    def test_planet_waypoint_requires_target_and_live_planet_position(self):
        for active, on_planet in ((False, True), (True, False)):
            with self.subTest(active=active, on_planet=on_planet):
                dashboard, window = self._ground_harness(
                    active=active, on_planet=on_planet,
                )
                dashboard._restore_overlay_hotkey_windows({"ground_popup"})
                self.assertFalse(window.deiconified)
        dashboard, window = self._ground_harness()
        dashboard._restore_overlay_hotkey_windows({"ground_popup"})
        self.assertTrue(window.deiconified)
        self.assertTrue(dashboard._ground_popup_visible)


class RuntimeOverlayVisibilityTests(unittest.TestCase):
    def test_cached_survey_and_contacts_restore_after_startup_curtain(self):
        from application_runtime import ApplicationRuntime
        from survey_status_hud import SurveyStatusHUD
        from contact_scope_hud import ContactScopeHUD
        from types import SimpleNamespace
        loop = ApplicationRuntime()
        loop._voidcompass_startup_presentation_held = False
        app = MainDashboard.__new__(MainDashboard)
        app.root = loop
        app._startup_overlay_restore = set()
        app._overlay_hotkey_hidden = set()
        app.survey_status_hud = SurveyStatusHUD(loop, {'survey_status_show_all_bodies':True})
        app.contact_scope_hud = ContactScopeHUD(loop, {})
        app._overlay_hotkey_window_items = lambda: [
            (name, getattr(app,name).win) for name in ('survey_status_hud','contact_scope_hud')]
        try:
            app.survey_status_hud.update('Sol',1,2,[{'name':'Sol 1','body_id':1,'bio_count':1}],{})
            app.contact_scope_hud.update('Sol',1,[{'name':'Test signal'}])
            for _, window in app._overlay_hotkey_window_items():
                self.assertEqual(window.state(),'normal')
            loop._voidcompass_startup_splash = SimpleNamespace()
            app._hold_startup_presentation()
            for _, window in app._overlay_hotkey_window_items():
                self.assertEqual(window.state(),'withdrawn')
            loop._voidcompass_startup_presentation_held = False
            app._restore_overlay_hotkey_windows(app._startup_overlay_restore, force_show=False)
            for _, window in app._overlay_hotkey_window_items():
                self.assertEqual(window.state(),'normal')
            # An explicit hide during startup must still cancel restoration.
            app._hold_startup_presentation()
            app.survey_status_hud.hide()
            app.contact_scope_hud.hide()
            loop._voidcompass_startup_presentation_held = False
            app._restore_overlay_hotkey_windows(app._startup_overlay_restore, force_show=False)
            for _, window in app._overlay_hotkey_window_items():
                self.assertEqual(window.state(),'withdrawn')
        finally:
            for _, window in app._overlay_hotkey_window_items(): window.destroy()
            loop.close()

    def test_navigation_handoff_updates_browser_visibility_without_journal_event(self):
        from application_runtime import ApplicationRuntime
        from hud import TacticalHUD
        from unittest.mock import Mock
        loop = ApplicationRuntime()
        nav = TacticalHUD(loop, {})
        try:
            nav.update('Sol','',0,0,0,None,{},nav_context={})
            self.assertFalse(nav._html_last_model['window']['visible'])
            bridge = nav._html_bridge = Mock()
            loop._voidcompass_startup_presentation_held = False
            nav.sync_html_window()
            self.assertTrue(bridge.publish.call_args.args[0]['window']['visible'])
            self.assertTrue(nav._html_last_model['window']['visible'])
            nav.win.withdraw()
            nav.sync_html_window()
            self.assertFalse(bridge.publish.call_args.args[0]['window']['visible'])
        finally:
            nav.win.destroy()
            loop.close()


if __name__ == "__main__":
    unittest.main()
