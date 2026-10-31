"""5.7.1: overlays come and go together, and can hide in the game's menus.

Under visual hosting a window reaches the screen through DWM cloaking: shown
under its cloak, it draws, and the host uncloaks it with everything else
arriving at the same moment. ShowWindow one window after another put them up
several frames apart (back from the Galaxy Map, they popped in one at a time).
One hidden for a map or a menu stays drawing under its cloak for a while, so
it comes back at once. A page that has never been on the screen doesn't draw
under a cloak, so each is drawn once while veiled (fully transparent) as soon
as it's ready: behind the boot screen, which the ones due to show then wait
out drawn, coming up together when it lifts.

The menus: GuiFocus gives the ship panels, station services and the Codex;
the journal's Music event the main menu, carrier management, Powerplay and
Squadrons. The game says nothing about the pause (Esc) menu."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from voidcompass.core import config as config_module
from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR, OVERLAY_SPECS
from voidcompass.overlays import html_overlay_host
from voidcompass.overlays.html_overlay_host import _OverlayHost, _WindowController
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
HOST = "voidcompass.overlays.html_overlay_host"


class Desk:
    """Fake Win32 and DWM for the host: which windows are shown and cloaked,
    and every call in order."""

    def __init__(self, test):
        self.now = 100.0
        self.shown = set()
        self.cloaked = set()
        self.alpha = {}
        self.log = []
        hooks = {
            "_native_handle": lambda window: window.hwnd,
            "_windows_visibility": lambda window: window.hwnd in self.shown,
            "_set_windows_visibility": self.show,
            "_cloak_window": self.cloak,
            "_apply_windows_geometry": lambda *args: True,
            "_apply_windows_style": lambda *args: True,
            "_apply_window_shape": lambda *args: True,
            "_window_has_region": lambda *args: True,
            "_apply_window_alpha": self.fade,
            "_apply_webview_transparency": lambda *args: False,
            "_foreground_window": lambda: 0,
            "monitor_scale": lambda *args: 1.0,
            "time": SimpleNamespace(monotonic=lambda: self.now, sleep=lambda _s: None),
        }
        for name, value in hooks.items():
            patcher = patch(f"{HOST}.{name}", value)
            patcher.start()
            test.addCleanup(patcher.stop)

    def show(self, window, visible):
        self.log.append(("show" if visible else "hide", window.hwnd))
        (self.shown.add if visible else self.shown.discard)(window.hwnd)
        return True

    def cloak(self, window, cloaked):
        self.log.append(("cloak" if cloaked else "uncloak", window.hwnd))
        (self.cloaked.add if cloaked else self.cloaked.discard)(window.hwnd)
        return True

    def fade(self, window, alpha):
        self.log.append(("alpha", window.hwnd, alpha))
        self.alpha[window.hwnd] = alpha
        return True

    def on_screen(self):
        return {hwnd for hwnd in self.shown - self.cloaked if self.alpha.get(hwnd, 255)}


class CloakTests(unittest.TestCase):
    IDS = ("survey", "navigation", "cargo")

    def setUp(self):
        self.desk = Desk(self)
        self.host = _OverlayHost("http://127.0.0.1:1/?token=t", None)
        self.host.runtime = SimpleNamespace(call=lambda fn: fn())
        self.host.presentation_held = False
        self.windows = {}
        for number, overlay_id in enumerate(self.IDS, start=1):
            window = SimpleNamespace(hwnd=number, _voidcompass_composition=True, _voidcompass_painted_at=0.0)
            self.windows[overlay_id] = window
            self.host.controllers[overlay_id] = _WindowController(overlay_id, window)
        self.status = {}

    def manifest(self, visible=True, held=False, render_current=True, stale=()):
        return {overlay_id: {
            "window": {"x": 10, "y": 10, "width": 300, "height": 200, "visible": visible,
                       **({"held": True} if held else {})},
            "content_ready": True, "render_current": render_current and overlay_id not in stale,
            "strict_ready": True,
        } for overlay_id in self.IDS}

    def apply(self, manifest):
        changes = self.host._apply_manifest(manifest, self.status)
        self.status.update(changes)
        return changes

    def paint(self, *overlay_ids):
        for overlay_id in overlay_ids or self.IDS:
            self.windows[overlay_id]._voidcompass_painted_at = self.desk.now

    def show_everything(self):
        self.apply(self.manifest())
        self.desk.now += .05
        self.paint()
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3})

    def test_overlays_arriving_together_are_uncloaked_together(self):
        self.show_everything()
        self.apply(self.manifest(visible=False))
        self.desk.now += 1
        self.apply(self.manifest())
        self.assertEqual(self.desk.shown, {1, 2, 3}, "shown, so their pages draw")
        self.assertEqual(self.desk.cloaked, {1, 2, 3}, "but under their cloaks until they have")
        self.assertTrue(self.host.settling, "the host looks again soon")
        self.desk.now += .05
        self.paint("survey", "navigation")
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), set(), "the group waits for its last page")
        self.desk.now += .02
        self.paint("cargo")
        self.desk.log.clear()
        changes = self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3})
        self.assertEqual(self.desk.log, [("uncloak", 1), ("uncloak", 2), ("uncloak", 3)], "one go, one frame")
        self.assertTrue(all(changes[overlay_id]["visible"] for overlay_id in self.IDS))
        self.assertFalse(self.host.settling)

    def test_a_first_show_is_veiled_not_cloaked(self):
        self.apply(self.manifest())
        self.assertEqual(self.desk.shown, {1, 2, 3})
        self.assertEqual(self.desk.cloaked, set(), "a page never on the screen doesn't draw under a cloak")
        self.assertEqual(self.desk.on_screen(), set(), "fully transparent instead")
        self.desk.now += .05
        self.paint()
        self.desk.log.clear()
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3})
        self.assertEqual(self.desk.log, [("alpha", 1, 255), ("alpha", 2, 255), ("alpha", 3, 255)], "one go")

    def test_every_page_is_drawn_once_out_of_sight_when_it_is_ready(self):
        self.apply(self.manifest(visible=False))
        self.assertEqual(self.desk.shown, {1, 2, 3}, "drawn once, veiled, as soon as it's ready")
        self.assertEqual(self.desk.on_screen(), set())
        self.desk.now += .05
        self.paint()
        self.apply(self.manifest(visible=False))
        self.assertEqual(self.desk.shown, set(), "then really hidden")
        self.assertEqual(self.desk.cloaked, {1, 2, 3}, "and from now on shown under the cloak")
        self.assertTrue(all(self.desk.alpha[hwnd] == 255 for hwnd in (1, 2, 3)), "unveiled")
        self.desk.log.clear()
        self.desk.now += 5
        self.apply(self.manifest(visible=False))
        self.assertEqual(self.desk.log, [], "once only")

    def test_behind_the_boot_screen_they_wait_drawn_and_come_up_together(self):
        self.host.presentation_held = True
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), set(), "nothing over the boot screen")
        self.desk.now += .05
        self.paint()
        self.apply(self.manifest())
        self.desk.now += 30
        self.apply(self.manifest())
        self.assertEqual(self.desk.shown, {1, 2, 3}, "still drawing, however long the boot screen")
        self.assertEqual(self.desk.on_screen(), set())
        self.host.presentation_held = False
        self.desk.log.clear()
        changes = self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3}, "up the moment it lifts")
        self.assertEqual(self.desk.log, [("uncloak", 1), ("uncloak", 2), ("uncloak", 3)])
        self.assertTrue(all(changes[overlay_id]["visible"] for overlay_id in self.IDS))

    def test_a_page_that_never_says_goes_up_with_its_group_when_the_wait_ends(self):
        self.show_everything()
        self.apply(self.manifest(visible=False))
        self.apply(self.manifest())
        self.desk.now += .05
        self.paint("survey", "navigation")
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), set())
        self.desk.now += html_overlay_host.REVEAL_WAIT_S
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3})

    def test_a_slow_page_holds_its_group_only_so_long(self):
        self.show_everything()
        self.apply(self.manifest(visible=False))
        self.apply(self.manifest(stale={"cargo"}))
        self.desk.now += .05
        self.paint()
        self.apply(self.manifest(stale={"cargo"}))
        self.assertEqual(self.desk.on_screen(), set(), "waiting for Cargo to draw its latest model")
        self.desk.now += html_overlay_host.REVEAL_WAIT_S
        self.apply(self.manifest(stale={"cargo"}))
        self.assertEqual(self.desk.on_screen(), {1, 2}, "the two that are ready go up together")
        self.desk.now += .1
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3}, "the slow one joins when it's ready")

    def test_a_page_never_shown_gets_longer_to_draw_its_first_frame(self):
        self.apply(self.manifest())
        self.desk.now += .05
        self.paint("survey", "navigation")
        self.desk.now += html_overlay_host.REVEAL_WAIT_S
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), set(), "cold pages at startup are waited for")
        self.desk.now += html_overlay_host.FIRST_REVEAL_WAIT_S
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3}, "a page that never says is taken as drawn")

    def test_hiding_cloaks_every_window_before_any_is_really_hidden(self):
        self.show_everything()
        self.desk.log.clear()
        changes = self.apply(self.manifest(visible=False))
        self.assertEqual(self.desk.log, [("cloak", 1), ("cloak", 2), ("cloak", 3),
                                         ("hide", 1), ("hide", 2), ("hide", 3)])
        self.assertEqual(self.desk.shown, set(), "really hidden: their pages stop drawing")
        self.assertFalse(any(changes[overlay_id]["visible"] for overlay_id in self.IDS))

    def test_a_map_keeps_them_drawing_and_they_come_back_at_once(self):
        self.show_everything()
        self.desk.log.clear()
        self.apply(self.manifest(visible=False, held=True))
        self.assertEqual(self.desk.on_screen(), set())
        self.assertEqual(self.desk.shown, {1, 2, 3}, "still drawing under their cloaks")
        self.assertNotIn("hide", {call for call, _hwnd in self.desk.log})
        self.desk.now += 3
        self.apply(self.manifest(visible=False, held=True))
        self.desk.log.clear()
        # The map closes; the Navigation HUD has a model it hasn't confirmed yet.
        changes = self.apply(self.manifest(render_current=False))
        self.assertEqual(self.desk.on_screen(), {1, 2, 3}, "back in the same pass")
        self.assertEqual(self.desk.log, [("uncloak", 1), ("uncloak", 2), ("uncloak", 3)])
        self.assertTrue(all(changes[overlay_id]["visible"] for overlay_id in self.IDS))

    def test_a_long_map_visit_really_hides_them(self):
        self.show_everything()
        self.apply(self.manifest(visible=False, held=True))
        self.desk.now += html_overlay_host.HOLD_DRAWN_S + 1
        self.apply(self.manifest(visible=False, held=True))
        self.assertEqual(self.desk.shown, set(), "drawing stops after a while")
        self.desk.now += 30
        self.apply(self.manifest(visible=False, held=True))
        self.assertEqual(self.desk.shown, set(), "and isn't started again")
        # Back from the map: shown under the cloak, drawn, up together.
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), set())
        self.desk.now += .05
        self.paint()
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3})

    def test_one_with_news_on_the_map_is_drawn_ready_for_its_close(self):
        self.show_everything()
        self.apply(self.manifest(visible=False))
        self.assertEqual(self.desk.shown, set())
        self.apply(self.manifest(visible=False, held=True))
        self.assertEqual(self.desk.shown, {1, 2, 3}, "shown under the cloak while the map is open")
        self.assertEqual(self.desk.on_screen(), set())

    def test_a_really_hidden_page_shows_only_its_latest_model(self):
        self.show_everything()
        self.apply(self.manifest(visible=False))
        self.apply(self.manifest(render_current=False))
        self.desk.now += 5
        self.paint()
        self.apply(self.manifest(render_current=False))
        self.assertEqual(self.desk.on_screen(), set(), "drawn, but not the model it's about to show")
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3})

    def test_only_the_visual_hosting_windows_are_cloaked(self):
        for window in self.windows.values():
            window._voidcompass_composition = False
        self.apply(self.manifest())
        self.assertEqual(self.desk.on_screen(), {1, 2, 3}, "classic windows show as before")
        self.assertFalse(any(call in {"cloak", "uncloak"} for call, _hwnd in self.desk.log))

    def test_the_host_looks_again_soon_while_a_group_waits(self):
        urls = []
        with patch(f"{HOST}._request_json", side_effect=lambda url, *args, **kwargs: urls.append(url) or {}):
            self.host.manifest()
            self.host.settling = True
            self.host.manifest()
        self.assertIn("&wait=1&", urls[0])
        self.assertIn("&wait=0.03&", urls[1])


class PaintedTests(unittest.TestCase):
    def test_visual_hosting_pages_say_when_they_have_drawn(self):
        host = _OverlayHost("http://127.0.0.1:1/?token=t", None)
        self.assertNotIn("painted", host.page_url("cargo", "cargo"), "classic windows don't")
        host.runtime = object()
        self.assertTrue(host.page_url("cargo", "cargo").endswith("&painted=1"))
        composition = (ROOT / "src" / "voidcompass" / "overlays" / "composition_host.py").read_text(encoding="utf-8")
        self.assertIn("core.WebMessageReceived += self._on_web_message", composition)
        self.assertIn('if message == "voidcompass.painted":', composition)

    def test_the_host_asks_as_it_shows_a_window(self):
        desk = Desk(self)
        asked = []
        window = SimpleNamespace(hwnd=7, _voidcompass_composition=True, run_js=asked.append)
        controller = _WindowController("cargo", window)
        controller.apply({"width": 100, "height": 50, "visible": True})
        self.assertEqual(desk.shown, {7})
        self.assertEqual(asked, ["window.__voidcompassPainted && window.__voidcompassPainted()"])

    def test_the_page_answers_two_frames_after_it_is_asked(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")
        server = HtmlOverlayServer(WEB, presentation_held=False)
        self.addCleanup(server.stop)
        server.register("cargo", "cargo")
        url = _OverlayHost(server.url, None).page_url("cargo", "cargo")
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f"Playwright Chromium is unavailable: {exc}")
            try:
                page = browser.new_page()
                page.add_init_script("""
                    window.__sent = [];
                    window.chrome = {webview: {postMessage: (message) => window.__sent.push(message),
                                               addEventListener() {}, removeEventListener() {}}};
                """)
                for suffix, expected in (("", []), ("&painted=1", ["voidcompass.painted"])):
                    page.goto(url + suffix)
                    page.evaluate("window.__voidcompassPainted && window.__voidcompassPainted()")
                    page.wait_for_timeout(300)
                    self.assertEqual(page.evaluate("window.__sent"), expected)
            finally:
                browser.close()


class HeldTests(unittest.TestCase):
    def setUp(self):
        self.server = HtmlOverlayServer(WEB, presentation_held=False)
        self.addCleanup(self.server.stop)
        self.addCleanup(HtmlOverlayServer.set_overrides, hidden=(), layout=False)
        self.server.register("survey", "survey")
        self.server.publish("survey", {"window": {"visible": False}})
        self.server.register("nav", "navigation")
        self.server.publish("nav", {"window": {"visible": True}})

    def test_a_map_holds_only_the_overlays_that_would_be_showing(self):
        HtmlOverlayServer.set_overrides(hidden={"survey", "nav"})
        windows = {key: row["window"] for key, row in self.server.window_manifest().items()}
        self.assertEqual((windows["nav"]["visible"], windows["nav"]["held"]), (False, True))
        self.assertEqual((windows["survey"]["visible"], windows["survey"]["held"]), (False, False))
        HtmlOverlayServer.set_overrides(hidden=())
        windows = {key: row["window"] for key, row in self.server.window_manifest().items()}
        self.assertNotIn("held", windows["nav"])
        self.assertTrue(windows["nav"]["visible"])


class MenuTests(unittest.TestCase):
    EVERY = frozenset(spec.overlay_id for spec in OVERLAY_SPECS)
    COLONY = OVERLAY_SPEC_BY_ATTR["colony_needs_hud"].overlay_id

    def tearDown(self):
        HtmlOverlayServer.set_overrides(hidden=(), layout=False)

    def studio(self, focus=0, menus=True, maps=True, keep=None):
        from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin

        studio = HtmlOverlayStudioMixin.__new__(type("Studio", (HtmlOverlayStudioMixin,), {}))
        studio.config = {"overlay_hide_on_maps": maps, "overlay_hide_in_menus": menus}
        if keep is not None:
            studio.config["overlay_menu_keep_visible"] = keep
        studio.current_gui_focus = focus
        studio._persist_config = Mock()
        studio._schedule_html_dashboard_publish = Mock()
        return studio

    def hidden(self):
        return set(HtmlOverlayServer.overlays_hidden)

    def test_ship_panels_station_services_and_the_codex_hide_the_overlays(self):
        for focus, hidden in ((1, self.EVERY - {self.COLONY}), (2, self.EVERY - {self.COLONY}),
                              (3, self.EVERY - {self.COLONY}), (4, self.EVERY - {self.COLONY}),
                              (5, self.EVERY - {self.COLONY}), (11, self.EVERY - {self.COLONY}),
                              (0, set()), (9, set()), (10, set()), (-1, set())):
            with self.subTest(focus=focus):
                self.studio(focus)._apply_map_overlay_hiding()
                self.assertEqual(self.hidden(), hidden)

    def test_off_by_default_and_the_maps_keep_their_own_switch(self):
        self.studio(2, menus=False)._apply_map_overlay_hiding()
        self.assertEqual(self.hidden(), set())
        self.studio(6, menus=False)._apply_map_overlay_hiding()
        self.assertEqual(self.hidden(), set(self.EVERY))
        self.studio(6, menus=True, maps=False)._apply_map_overlay_hiding()
        self.assertEqual(self.hidden(), set(), "a map isn't a menu")

    def test_the_journal_music_tells_the_screens_status_json_does_not(self):
        studio = self.studio()
        for track, in_menu in (("MainMenu", True), ("Exploration", False), ("FleetCarrier_Managment", True),
                               ("Supercruise", False), ("GalacticPowers", True), ("NoTrack", False),
                               ("Squadrons", True), ("", False), ("CQCMenu", True)):
            with self.subTest(track=track):
                studio._observe_menu_music(track)
                self.assertEqual(self.hidden(), self.EVERY - {self.COLONY} if in_menu else set())

    def test_the_menu_is_remembered_while_the_setting_is_off(self):
        studio = self.studio(menus=False)
        studio._observe_menu_music("GalacticPowers")
        self.assertEqual(self.hidden(), set())
        self.assertTrue(studio._html_overlay_option_toggle("overlay_hide_in_menus", True))
        self.assertTrue(studio.config["overlay_hide_in_menus"])
        self.assertIn("navigation", self.hidden(), "switched on in Powerplay: hidden at once")

    def test_each_overlay_can_stay_in_the_menus(self):
        studio = self.studio(5)
        self.assertTrue(studio._handle_html_overlay_studio_command(
            {"operation": "menu_hiding", "overlay_id": "survey_status_hud", "hide": False}))
        self.assertEqual(studio.config["overlay_menu_keep_visible"], ["colony_needs_hud", "survey_status_hud"])
        studio._persist_config.assert_called()
        self.assertNotIn("survey", self.hidden())
        self.assertNotIn(self.COLONY, self.hidden())
        studio._handle_html_overlay_studio_command(
            {"operation": "menu_hiding", "overlay_id": "colony_needs_hud", "hide": True})
        self.assertIn(self.COLONY, self.hidden())
        self.assertFalse(studio._handle_html_overlay_studio_command(
            {"operation": "menu_hiding", "overlay_id": "not-an-overlay", "hide": False}))
        records_source = (ROOT / "src" / "voidcompass" / "dashboard" / "html_overlay_studio.py").read_text(encoding="utf-8")
        self.assertIn('"hide_in_menus": attr not in self._menu_keep_visible()', records_source)

    def test_the_settings_are_per_profile_off_and_keep_construction_needs(self):
        self.assertIn("overlay_hide_in_menus", config_module.PROFILE_BOOL_SETTINGS)
        self.assertIn("overlay_menu_keep_visible", config_module.PROFILE_VALUE_SETTINGS)
        source = (ROOT / "src" / "voidcompass" / "core" / "config.py").read_text(encoding="utf-8")
        self.assertIn('"overlay_hide_in_menus": False', source)
        self.assertIn("'overlay_hide_in_menus': False", source)
        self.assertIn('"overlay_menu_keep_visible": ["colony_needs_hud"]', source)
        self.assertIn("'overlay_menu_keep_visible': ['colony_needs_hud']", source)

    def test_the_dashboard_feeds_it_the_music_and_the_session(self):
        source = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("self._observe_menu_music(track)", source)
        self.assertIn('if ev in {"LoadGame", "Shutdown"}:\n            # Out of the main menu, or the game closed: no menu is open.\n'
                      '            self._observe_menu_music("")', source)

    def test_studio_tools_and_the_local_api_offer_it(self):
        index = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-overlay-option="overlay_hide_in_menus"', index)
        self.assertIn('id="studio-selected-menuhide"', index)
        app = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('operation: "menu_hiding"', app)
        from voidcompass.dashboard.dashboard_tools_mixin import STUDIO_OPTIONS, TOOL_SWITCHES

        self.assertIn("overlay_hide_in_menus", {row[0] for row in TOOL_SWITCHES})
        self.assertIn("overlay_hide_in_menus", STUDIO_OPTIONS)
        from voidcompass.dashboard.dashboard_api_mixin import DashboardApiMixin

        row = DashboardApiMixin._api_overlay_row(SimpleNamespace(config={}), SimpleNamespace(overlay_id="survey", attr="survey_status_hud", label="Survey"),
                                                 {"hide_in_menus": True})
        self.assertTrue(row["hide_in_menus"])


if __name__ == "__main__":
    unittest.main()
