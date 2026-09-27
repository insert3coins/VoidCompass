"""The rebuilt Settings page (5.4.9.7).

Settings are grouped into sections on a rail, one shown at a time, with a
find box that searches every setting. Each control saves the moment it
changes; the command channel answers before Python applies a save, so each
save carries an id and the next snapshot says whether it was kept. A refused
save (a clashing hotkey) changes nothing and the page puts the old value
back. Python applies only what a change affects: a toggle must not refetch
Galnet or re-register hotkeys. A new journal folder is watched from the end
of its newest journal, so nothing replays as live.
"""

import json
import os
import re
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

from voidcompass.core import themes
from voidcompass.core.journal_watcher import JournalWatcher
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS, OVERLAY_SPECS
from voidcompass.dashboard.dashboard import MainDashboard
from tests.test_dashboard_overview_visuals import overview_state

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
IMAGES = ROOT / "assets" / "images"


def dashboard(config=None):
    app = MainDashboard.__new__(MainDashboard)
    app.config = {key: "" for _action, key, _label, _attr in OVERLAY_HOTKEY_SPECS}
    app.config.update({"overlay_hotkey_toggle_all": "Ctrl+Alt+Shift+F11", "low_fuel_threshold_pct": 0.25,
                       "galnet_enabled": True})
    app.config.update(config or {})
    app._persist_config = Mock()
    app._schedule_html_dashboard_publish = Mock()
    return app


class SettingsSaveTests(unittest.TestCase):
    def save(self, app, **payload):
        return app._handle_html_workspace_command({"page": "settings", "operation": "save", **payload})

    def test_one_setting_saves_without_touching_the_rest(self):
        app = dashboard()
        app._apply_settings_changes = Mock()
        self.assertTrue(self.save(app, save_id=4, values={"auto_copy_waypoint": True}))
        self.assertTrue(app.config["auto_copy_waypoint"])
        self.assertEqual(app.config["overlay_hotkey_toggle_all"], "Ctrl+Alt+Shift+F11", "hotkeys left alone")
        app._apply_settings_changes.assert_called_once_with({"auto_copy_waypoint"})
        self.assertEqual(app._html_settings_last_save, {"id": 4, "ok": True, "detail": ""})

    def test_values_are_held_to_their_limits(self):
        app = dashboard()
        app._apply_settings_changes = Mock()
        self.save(app, values={"low_fuel_threshold_pct": 5, "ui_scale_percent": 999,
                               "galnet_rotation_seconds": 1, "galnet_refresh_minutes": 9999})
        self.assertEqual((app.config["low_fuel_threshold_pct"], app.config["ui_scale_percent"],
                          app.config["galnet_rotation_seconds"], app.config["galnet_refresh_minutes"]),
                         (0.6, 200, 4, 240))

    def test_a_clashing_hotkey_changes_nothing_and_says_so(self):
        app = dashboard()
        app._apply_settings_changes = Mock()
        hotkeys = {action: "" for action, *_ in OVERLAY_HOTKEY_SPECS}
        hotkeys.update(toggle_all="Ctrl+Alt+Shift+F2", navigation="Ctrl+Alt+Shift+F2")
        self.assertFalse(self.save(app, save_id=9, values={"auto_copy_waypoint": True}, hotkeys=hotkeys))
        self.assertNotIn("auto_copy_waypoint", app.config)
        self.assertEqual(app.config["overlay_hotkey_toggle_all"], "Ctrl+Alt+Shift+F11")
        self.assertFalse(app._html_settings_last_save["ok"])
        self.assertEqual(app._html_settings_last_save["id"], 9)
        self.assertIn("duplicates", app._html_settings_last_save["detail"])
        app._schedule_html_dashboard_publish.assert_called()
        app._apply_settings_changes.assert_not_called()

    def test_only_affected_systems_are_reapplied(self):
        app = dashboard()
        for name in ("_restart_galnet_feed_schedule", "_configure_overlay_hotkeys", "_apply_active_profile_theme",
                     "_apply_runtime_feature_toggles", "_apply_overlay_mouse_passthrough", "update_hud",
                     "_update_galnet_ticker"):
            setattr(app, name, Mock())
        app.watcher = SimpleNamespace(switch_folder=Mock())
        app.root = SimpleNamespace()
        with patch("voidcompass.dashboard.html_dashboard.apply_ui_scale") as scale:
            app._apply_settings_changes({"auto_copy_waypoint"})
            app._restart_galnet_feed_schedule.assert_not_called()
            app._configure_overlay_hotkeys.assert_not_called()
            scale.assert_not_called()
            app._apply_settings_changes({"galnet_rotation_seconds"})
            app._restart_galnet_feed_schedule.assert_not_called()
            app._apply_settings_changes({"galnet_enabled"})
            app._restart_galnet_feed_schedule.assert_called_once()
            app._update_galnet_ticker.assert_called_once()
            app._apply_settings_changes({"hotkeys"})
            app._configure_overlay_hotkeys.assert_called_once()
            app._apply_settings_changes({"ui_scale_percent"})
            scale.assert_called_once()
            folder = tempfile.mkdtemp()
            self.addCleanup(os.rmdir, folder)
            app.config["journal_path"] = folder
            app._apply_settings_changes({"journal_path"})
            app.watcher.switch_folder.assert_called_once_with(folder)

    def test_snapshot_carries_what_the_page_draws(self):
        app = dashboard({"active_commander_name": "Jeff", "active_commander_fid": "F1"})
        app._adaptive_health_snapshot = lambda: {"level": "NOMINAL"}
        app._html_dashboard_galnet = lambda: {"articles": []}
        app._html_profile_transient = lambda _key, default: dict(default)
        data = app._html_settings_workspace()
        self.assertEqual(data["profile"]["name"], "Jeff")
        self.assertEqual([theme["name"] for theme in data["themes"]][:len(themes.BUILTIN_THEMES)], list(themes.BUILTIN_THEMES))
        self.assertNotIn("overlays", data, "overlays are Overlay Studio's")
        self.assertIn("journal", data["paths"])
        self.assertEqual(data["last_save"], {"id": 0, "ok": True, "detail": ""})
        for key in ("low_fuel_threshold_pct", "auto_copy_waypoint", "achievements_enabled",
                    "achievement_notifications_enabled", "adaptive_command_enabled"):
            self.assertIn(key, data["values"])
        for key in ("overlay_mouse_passthrough", "hud_animation_intensity"):
            self.assertNotIn(key, data["values"])

    def test_no_setting_lives_in_both_settings_and_overlay_studio(self):
        # Overlay Studio holds everything about overlays; Settings holds the rest.
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        studio = set(re.findall(r'data-(?:studio-setting|overlay-option)="([a-z_]+)"', html))
        source = (WEB / "dashboard" / "app.js").read_text(encoding="utf-8")
        settings_code = source[source.index("function settingsSectionBody"):source.index("function settingsHealthDetail")]
        settings = set(re.findall(r'key: "([a-z_]+)"', settings_code))
        self.assertTrue(studio and settings)
        self.assertEqual(studio & settings, set())
        app = dashboard()
        app._apply_settings_changes = Mock()
        self.save(app, values={"overlay_mouse_passthrough": False, "hud_animation_intensity": "Calm"})
        self.assertNotIn("overlay_mouse_passthrough", app.config, "Settings will not save an overlay setting")
        self.assertNotIn("hud_animation_intensity", app.config)


class JournalFolderSwitchTests(unittest.TestCase):
    def test_a_new_folder_is_watched_from_the_end_of_its_newest_journal(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        folder = Path(holder.name)
        old = folder / "Journal.2026-09-26T100000.01.log"
        newest = folder / "Journal.2026-09-27T100000.01.log"
        old.write_text(json.dumps({"event": "Fileheader"}) + "\n", encoding="utf-8")
        newest.write_text(json.dumps({"event": "FSDJump", "StarSystem": "Sol"}) + "\n", encoding="utf-8")
        watcher = JournalWatcher("")
        watcher._startup_catchup_done = True
        events = []
        # A burst goes to the batch callback, a single live event to the other.
        watcher.batch_event_callback = events.extend
        watcher.event_callback = events.append
        watcher.switch_folder(str(folder))
        # Nothing moves until the watcher's own thread picks it up.
        self.assertEqual(watcher.journal_path, "")
        watcher._check_journal()
        self.assertEqual(watcher.journal_path, str(folder))
        self.assertEqual(watcher.last_journal, str(newest))
        self.assertEqual(events, [], "what already happened does not replay as live")
        with newest.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "Scan", "BodyName": "Sol A"}) + "\n")
        watcher._check_journal()
        self.assertEqual([event.get("type") for event in events], ["Scan"])


SETTINGS = {
    "values": {"journal_path": "C:/Journals", "screenshots_path": "C:/Shots", "screenshots_enabled": True,
               "ui_scale_percent": 100, "reduced_motion_enabled": False,
               "overlay_hotkeys_enabled": True, "edsm_cmdr_name": "Jeff",
               "edsm_api_key": "key", "edsm_upload_enabled": True, "eddn_market_upload_enabled": True,
               "carrier_discord_webhook_url": "", "runtime_trace_enabled": True, "crash_reporting_enabled": True,
               "recovery_safe_mode_enabled": True, "edsm_backfill_on_cache_rebuild": False,
               "automatic_profile_backups_enabled": True, "galnet_enabled": True, "galnet_auto_rotate_enabled": True,
               "galnet_rotation_seconds": 7, "galnet_refresh_minutes": 30, "low_fuel_threshold_pct": 0.25,
               "auto_copy_waypoint": False, "achievements_enabled": True, "achievement_notifications_enabled": True,
               "adaptive_command_enabled": True},
    "hotkeys": [
        {"action": "toggle_all", "key": "overlay_hotkey_toggle_all", "label": "Show / hide all overlays", "value": "Ctrl+Alt+Shift+F11", "default": "Ctrl+Alt+Shift+F11"},
        {"action": "navigation", "key": "overlay_hotkey_navigation", "label": "Navigation HUD", "value": "Ctrl+Alt+Shift+F2", "default": ""},
    ],
    "health": {"level": "NOMINAL"}, "eddn": {"uploads": 3},
    "galnet": {"status": "live", "detail": "Refreshed", "articles": [{}, {}]},
    "profile": {"key": "jeff", "name": "Jeff", "fid": "F1"},
    "paths": {"journal": {"exists": True, "logs": 12, "latest": "Journal.x.log"}, "screenshots": {"exists": True}},
    "themes": [{"name": "Void Cyan", "custom": False, "swatch": {"accent": "#00d1ff"}},
               {"name": "Elite Orange", "custom": False, "swatch": {"accent": "#ff8c1a"}}],
    "theme_editor": {"name": "Void Cyan", "palette": {}, "custom": [], "keys": ["accent"]},
    "tools": {"status": "ready", "detail": ""}, "cache_rebuild": {},
    "last_save": {"id": 0, "ok": True, "detail": ""},
}

HARNESS = """
  window.__settings = {
    render(data, settings) {
      model = data;
      applyTheme(data.theme || {});
      document.body.classList.add('ready');
      document.getElementById('boot').hidden = true;
      renderDashboard(data);
      document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.dataset.pageName === 'settings'));
      currentPage = 'settings';
      this.publish(settings);
    },
    publish(settings) {
      model.workspace = {page: 'settings', ready: true, data: settings};
      renderWorkspace(model);
    },
  };
"""


class SettingsPageBrowserTests(unittest.TestCase):
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

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1600, "height": 1000})
        self.page.emulate_media(reduced_motion="reduce")
        self.errors, self.commands = [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

        def serve(route):
            path = urlsplit(route.request.url).path
            if path == "/api/command":
                self.commands.append(json.loads(route.request.post_data or "{}"))
                route.fulfill(content_type="application/json", body='{"accepted":true}')
                return
            if path in ("/api/events", "/api/snapshot"):
                route.fulfill(content_type="application/json", body=json.dumps(overview_state()) if path == "/api/snapshot" else '{"closing":true}')
                return
            file = IMAGES / path.removeprefix("/dashboard/images/") if path.startswith("/dashboard/images/") else WEB / path.lstrip("/")
            if path == "/dashboard/app.js":
                route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + HARNESS)
            elif file.is_file():
                route.fulfill(path=str(file))
            else:
                route.fulfill(status=404, body="")

        self.page.route("http://settings.test/**", serve)
        self.page.goto("http://settings.test/dashboard/index.html")
        self.page.wait_for_function("Boolean(window.__settings)")
        self.page.evaluate("([d, s]) => window.__settings.render(d, s)", [overview_state(), SETTINGS])
        self.addCleanup(self.page.close)
        self.addCleanup(lambda: self.assertEqual(self.errors, []))

    def saves(self):
        return [command for command in self.commands if command.get("operation") == "save"]

    def wait_for(self, condition, message=""):
        """Commands reach the stub server asynchronously; poll briefly for them."""
        for _ in range(80):
            if condition():
                return
            self.page.wait_for_timeout(25)
        self.fail(message or "condition not met")

    def visible_panels(self):
        return self.page.evaluate("[...document.querySelectorAll('[data-settings-panel]')].filter(n => !n.hidden).map(n => n.dataset.settingsPanel)")

    def test_one_section_at_a_time_from_the_rail(self):
        self.assertEqual(self.visible_panels(), ["journal"])
        self.page.click('[data-settings-section="galnet"]')
        self.assertEqual(self.visible_panels(), ["galnet"])
        self.assertIn("LIVE · 2 DISPATCHES", self.page.inner_text('[data-settings-section="galnet"]'))

    def test_find_searches_every_section(self):
        self.page.fill("#settings-search", "fuel")
        self.assertEqual(self.visible_panels(), ["flight"])
        rows = self.page.evaluate("[...document.querySelectorAll('[data-settings-panel=flight] .setting-row')].filter(n => !n.hidden).length")
        self.assertEqual(rows, 1)
        self.assertEqual(self.page.inner_text('[data-settings-section="flight"] .settings-tab-count'), "1")
        self.page.fill("#settings-search", "zzzz")
        self.assertTrue(self.page.is_visible(".settings-no-match"))
        self.page.click('[data-settings-section="hotkeys"]')
        self.assertEqual((self.page.input_value("#settings-search"), self.visible_panels()), ("", ["hotkeys"]))

    def test_a_change_saves_at_once_and_its_row_reports_the_result(self):
        self.page.click('[data-settings-section="flight"]')
        row = '.setting-row:has([data-setting="auto_copy_waypoint"])'
        self.page.click(row)
        self.page.wait_for_function("document.querySelector('%s .setting-flag').textContent === 'SAVING'" % row)
        save = self.saves()[-1]
        self.assertEqual(save["values"], {"auto_copy_waypoint": True})
        self.assertEqual(self.page.inner_text("#settings-save-state"), "SAVING…")
        confirmed = dict(SETTINGS, last_save={"id": save["save_id"], "ok": True, "detail": ""})
        self.page.evaluate("data => window.__settings.publish(data)", confirmed)
        self.assertEqual(self.page.inner_text(f"{row} .setting-flag"), "SAVED")
        self.assertEqual(self.page.inner_text("#settings-save-state"), "ALL CHANGES SAVED")

    def test_a_refused_save_puts_the_old_value_back(self):
        self.page.click('[data-settings-section="flight"]')
        self.page.select_option('[data-setting="low_fuel_threshold_pct"]', "0.4")
        self.wait_for(lambda: self.saves(), "the change was not saved")
        save = self.saves()[-1]
        self.assertEqual(save["values"], {"low_fuel_threshold_pct": 0.4})
        refused = dict(SETTINGS, last_save={"id": save["save_id"], "ok": False, "detail": "refused"})
        self.page.evaluate("data => window.__settings.publish(data)", refused)
        self.assertEqual(self.page.input_value('[data-setting="low_fuel_threshold_pct"]'), "0.25")
        self.assertIn("NOT SAVED", self.page.inner_text("#settings-save-state"))

    def test_a_shortcut_already_in_use_is_refused_here(self):
        self.page.click('[data-settings-section="hotkeys"]')
        self.page.click('[data-hotkey-record="navigation"]')
        self.page.keyboard.press("Control+Alt+Shift+F11")
        self.page.wait_for_function("document.getElementById('hotkey-status').textContent.includes('already used')")
        self.assertEqual(self.page.input_value('[data-hotkey-action="navigation"]'), "Ctrl+Alt+Shift+F2")
        self.assertEqual(self.saves(), [], "a clash never reaches Python")
        self.page.click('[data-hotkey-record="navigation"]')
        self.page.keyboard.press("Control+Alt+Shift+F5")
        self.wait_for(lambda: self.saves(), "the new shortcut was not saved")
        self.assertEqual(self.saves()[-1]["hotkeys"]["navigation"], "Ctrl+Alt+Shift+F5")

    def test_a_theme_applies_straight_away_and_overlays_stay_in_studio(self):
        self.page.click('[data-settings-section="appearance"]')
        self.page.click('[data-theme-name="Elite Orange"]')
        self.page.wait_for_function("document.querySelector('[data-theme-name=\"Elite Orange\"]').classList.contains('active')")
        self.assertIn({"action": "set_theme", "name": "Elite Orange"}, self.commands)
        self.assertEqual(self.page.locator('[data-settings-section="overlays"], [data-overlay-toggle]').count(), 0)
        self.assertEqual(self.page.locator('[data-setting="hud_animation_intensity"], [data-setting="overlay_mouse_passthrough"]').count(), 0)

    def test_a_publish_redraws_only_when_nothing_is_in_hand(self):
        self.page.click('[data-settings-section="galnet"]')
        self.page.focus('[data-setting="galnet_refresh_minutes"]')
        changed = dict(SETTINGS, galnet=dict(SETTINGS["galnet"], articles=[{}] * 9))
        self.page.evaluate("data => window.__settings.publish(data)", changed)
        self.assertIn("2 DISPATCHES", self.page.inner_text('[data-settings-section="galnet"]'), "no redraw while focused")
        self.page.evaluate("document.activeElement.blur()")
        self.page.evaluate("data => window.__settings.publish(data)", changed)
        self.assertIn("9 DISPATCHES", self.page.inner_text('[data-settings-section="galnet"]'))
        self.assertEqual(self.visible_panels(), ["galnet"], "the section survives a redraw")


if __name__ == "__main__":
    unittest.main()
