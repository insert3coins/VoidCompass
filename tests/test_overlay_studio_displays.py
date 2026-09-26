"""Overlay Studio works one display at a time.

The old Studio drew the whole virtual desktop, so two side-by-side 2560 px
monitors became one thin strip. Now the Python side lists each display, tags
every surface with the display holding most of it, snaps to that display's
own edges (the seam between monitors is an edge), and saves one setting at a
time without resetting the others.
"""

import unittest
from types import SimpleNamespace

from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays.html_survey_overlay import HtmlSurveyOverlayBridge


DISPLAYS = [
    {"id": "display-1", "number": 1, "label": "DISPLAY 1", "primary": True,
     "left": 0, "top": 0, "width": 2560, "height": 1440},
    {"id": "display-2", "number": 2, "label": "DISPLAY 2", "primary": False,
     "left": 2560, "top": 0, "width": 2560, "height": 1440},
]


class _Studio(HtmlOverlayStudioMixin):
    _OVERLAY_POSITION_SPECS = [("survey_status_hud", "survey_status_hud_x", "survey_status_hud_y")]

    def __init__(self, records):
        self.config = {"prospector_hud_timeout_s": 90, "gravity_warning_threshold_g": 2.5,
                       "hud_crt_intensity": "Strong", "survey_spotlight_threshold": 15}
        self.records = records
        self.moves = []

    def _persist_config(self):
        pass

    def update_hud(self):
        pass

    def _schedule_html_dashboard_publish(self, **kwargs):
        pass

    def _html_overlay_monitors(self):
        return [dict(display) for display in DISPLAYS]

    def _html_overlay_desktop(self):
        return {"left": 0, "top": 0, "width": 5120, "height": 1440,
                "primary": {"left": 0, "top": 0, "width": 2560, "height": 1440}}

    def _html_overlay_records(self, **kwargs):
        return [dict(record) for record in self.records]

    def _set_overlay_position(self, attr, x, y, **kwargs):
        self.moves.append((attr, x, y))

    def _ground_target_solution(self):
        return {}

    def _ground_target_configured(self):
        return False

    def _ground_target_should_show(self, solution):
        return False


class _LiveSizeStudio(_Studio):
    def _html_overlay_records(self, **kwargs):
        return HtmlOverlayStudioMixin._html_overlay_records(self, **kwargs)


def surface(x, y=200, width=520, height=340):
    return {"id": "survey_status_hud", "label": "Survey Operations", "short_label": "SURVEY",
            "x": x, "y": y, "width": width, "height": height,
            "enabled": True, "shown": True, "html_ready": True, "state": "HTML"}


class OverlayStudioDisplayTests(unittest.TestCase):
    def test_surfaces_belong_to_the_display_holding_most_of_them(self):
        monitor_for = HtmlOverlayStudioMixin._html_overlay_monitor_for
        self.assertEqual(monitor_for(surface(40), DISPLAYS)["id"], "display-1")
        self.assertEqual(monitor_for(surface(3000), DISPLAYS)["id"], "display-2")
        # Straddling the seam: most of it is on the second screen.
        self.assertEqual(monitor_for(surface(2400), DISPLAYS)["id"], "display-2")
        # Off every screen (a monitor unplugged): the nearest one.
        self.assertEqual(monitor_for(surface(6000), DISPLAYS)["id"], "display-2")

    def test_studio_snapshot_lists_displays_and_tags_each_surface(self):
        studio = _Studio([surface(3000)])
        snapshot = studio._html_overlay_studio()
        self.assertEqual([monitor["id"] for monitor in snapshot["monitors"]], ["display-1", "display-2"])
        self.assertEqual(snapshot["overlays"][0]["monitor"], "display-2")

    def test_smart_snap_treats_the_seam_between_displays_as_an_edge(self):
        # 12 px short of the second display's left edge (the seam at 2560).
        studio = _Studio([surface(2572)])
        self.assertTrue(studio._html_overlay_snap("survey_status_hud"))
        self.assertEqual(studio.moves[-1], ("survey_status_hud", 2560, 200))

    def test_survey_html_size_reaches_the_right_display_edge(self):
        overlay = SimpleNamespace(_html_ready=True, _html_render_model={"mode": "system", "rows": [1]})
        window = SimpleNamespace(
            master=SimpleNamespace(), state=lambda: "normal",
            winfo_x=lambda: 3000, winfo_y=lambda: 200,
            winfo_viewable=lambda: True,
        )
        overlay.win = window
        bridge = HtmlSurveyOverlayBridge.__new__(HtmlSurveyOverlayBridge)
        bridge.overlay = overlay
        bridge.win = window
        bridge.config = {"survey_status_hud_x": 3000, "survey_status_hud_y": 200,
                         "survey_status_overlay_enabled": True}
        bridge.x_key = "survey_status_hud_x"
        bridge.y_key = "survey_status_hud_y"
        bridge.enabled_key = "survey_status_overlay_enabled"
        bridge._browser_content_height = 180
        self.assertEqual(bridge._window_payload()["width"], 420)

        studio = _LiveSizeStudio([])
        studio.config.update(bridge.config)
        studio.survey_status_hud = overlay
        overlay._html_ready = False
        self.assertEqual(studio._html_overlay_records()[0]["width"], 420)
        overlay._html_ready = True
        record = studio._html_overlay_records()[0]
        self.assertEqual((record["width"], record["height"]), (420, 180))
        self.assertTrue(studio._html_overlay_position("survey_status_hud", 9999, 200))
        self.assertEqual(studio.moves[-1], ("survey_status_hud", 5120 - 420, 200))

    def test_empty_notifications_keep_a_useful_placement_card(self):
        studio = _LiveSizeStudio([])
        studio._OVERLAY_POSITION_SPECS = [("toast_hud", "toast_hud_x", "toast_hud_y")]
        studio.toast_hud = SimpleNamespace(
            _html_ready=True, _html_window_size=(400, 24), _toasts=[],
            win=SimpleNamespace(winfo_viewable=lambda: False, state=lambda: "withdrawn"),
        )
        record = studio._html_overlay_records()[0]
        self.assertEqual((record["width"], record["height"]), (400, 94))

    def test_a_single_setting_saves_without_resetting_the_rest(self):
        studio = _Studio([])
        self.assertTrue(studio._html_overlay_settings_save({"survey_spotlight_threshold": "20"}))
        self.assertEqual(studio.config["survey_spotlight_threshold"], 20)
        self.assertEqual((studio.config["prospector_hud_timeout_s"], studio.config["gravity_warning_threshold_g"],
                          studio.config["hud_crt_intensity"]), (90, 2.5, "Strong"))
        studio._html_overlay_settings_save({"gravity_warning_threshold_g": "4.25"})
        self.assertEqual(studio.config["gravity_warning_threshold_g"], 4.25)
        self.assertEqual(studio.config["survey_spotlight_threshold"], 20)

    def test_windows_display_enumeration_returns_real_rectangles(self):
        displays = HtmlOverlayStudioMixin()._html_overlay_monitors()
        self.assertTrue(displays)
        for display in displays:
            self.assertGreater(display["width"], 0)
            self.assertGreater(display["height"], 0)
            self.assertTrue(display["label"].startswith("DISPLAY "))
        self.assertEqual(len({display["id"] for display in displays}), len(displays))


if __name__ == "__main__":
    unittest.main()
