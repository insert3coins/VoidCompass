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

    def test_voice_sequences_save_reset_and_reject_invalid_steps_atomically(self):
        app = dashboard()
        app._apply_settings_changes = Mock()
        custom = {"deploy_nomad": ["focus FocusRadarPanel 4", "UI_Down x2", "hold UI_Select 1.2"]}
        self.assertTrue(self.save(app, save_id=1, values={"watcher_ship_macros": custom}))
        self.assertEqual(app.config["watcher_ship_macros"], custom)
        for invalid in ({"deploy_nomad": ["wait nan"]}, {"unknown": ["UI_Select"]}, [],
                        {"deploy_nomad": []}, {"deploy_nomad": ["SelfDestruct"]}):
            with self.subTest(invalid=invalid):
                self.assertFalse(self.save(app, save_id=2, values={"watcher_ship_macros": invalid, "home_system": "Sol"}))
                self.assertEqual(app.config["watcher_ship_macros"], custom)
                self.assertNotIn("home_system", app.config)
                self.assertFalse(app._html_settings_last_save["ok"])
        self.assertTrue(self.save(app, save_id=3, values={"watcher_ship_macros": {}}))
        self.assertEqual(app.config["watcher_ship_macros"], {})

    def test_values_are_held_to_their_limits(self):
        app = dashboard()
        app._apply_settings_changes = Mock()
        self.save(app, values={"low_fuel_threshold_pct": 5, "ui_scale_percent": 999,
                               "galnet_rotation_seconds": 1, "galnet_refresh_minutes": 9999})
        self.assertEqual((app.config["low_fuel_threshold_pct"], app.config["ui_scale_percent"],
                          app.config["galnet_rotation_seconds"], app.config["galnet_refresh_minutes"]),
                         (0.6, 200, 4, 240))

    def test_map_open_close_and_vehicle_sequences_save_independently(self):
        app = dashboard()
        app._apply_settings_changes = Mock()
        custom = {"galaxy_map": ["GalaxyMapOpen"], "galaxy_map:off": ["UI_Back"],
                  "system_map:srv": ["focus FocusLeftPanel_Buggy 2", "UI_Select"]}
        self.assertTrue(self.save(app, values={"watcher_ship_macros": custom}))
        self.assertEqual(app.config["watcher_ship_macros"], custom)
        self.assertFalse(self.save(app, values={"watcher_ship_macros": {"gear:off": ["UI_Select"]}}))
        self.assertEqual(app.config["watcher_ship_macros"], custom)

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

    def test_voice_settings_save_and_switch_its_hearing(self):
        """Settings › Voice (5.7.3): its hearing switched on or off as the
        MIND page did it, and a talk-key mode held to the two there are."""
        app = dashboard()
        app._watcher_listen_switched = Mock()
        self.assertTrue(self.save(app, save_id=5, values={"watcher_listen_enabled": True, "watcher_listen_mode": "shout",
                                                          "watcher_ship_enabled": False}))
        self.assertEqual(app.config["watcher_listen_mode"], "hold")
        self.assertFalse(app.config["watcher_ship_enabled"])
        app._watcher_listen_switched.assert_called_once()
        app._handle_watcher_listen_command = Mock(return_value=True)
        self.assertTrue(app._handle_html_workspace_command({"page": "settings", "operation": "listen_test"}))
        app._handle_watcher_listen_command.assert_called_once_with("listen_test", {"page": "settings", "operation": "listen_test"})

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
        labels = [row["label"] for row in data["hotkeys"]]
        self.assertEqual(labels, sorted(labels, key=lambda label: label.casefold().removeprefix("the ")), "hotkeys A to Z")
        self.assertEqual(labels[0], "Achievements")

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
        {"action": "toggle_all", "key": "overlay_hotkey_toggle_all", "label": "Show / hide all overlays", "value": "Ctrl+Alt+Shift+F11", "default": "Ctrl+Alt+Shift+F11", "group": "controls"},
        {"action": "navigation", "key": "overlay_hotkey_navigation", "label": "Navigation HUD", "value": "Ctrl+Alt+Shift+F2", "default": "", "group": "overlays"},
        {"action": "music_next", "key": "overlay_hotkey_music_next", "label": "Next track", "value": "", "default": "", "group": "music"},
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

    def test_controller_buttons_beside_the_shortcuts(self):
        """5.7.3: a controller button beside each shortcut, what Elite does with
        the key and the button, and SET learning it in the app."""
        controllers = {
            "enabled": True,
            "buttons": {"toggle_all": {"spec": "pad:LB+pad:A", "label": "Pad: hold LB, press A",
                                       "clashes": ["Landing gear toggle (Ship)"], "more": 0}},
            "keys": {"navigation": {"clashes": ["Select target (Ship)"], "more": 2}},
            "learning": {},
            "elite": {"groups": [{"group": "ship", "label": "Ship", "preset": "ConsoleX360", "built_in": True,
                                  "found": True, "path": ""}], "error": ""},
        }
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, controllers=controllers))
        self.page.click('[data-settings-section="hotkeys"]')
        everything = '.hotkey-row:has([data-hotkey-action="toggle_all"])'
        navigation = '.hotkey-row:has([data-hotkey-action="navigation"])'
        self.assertEqual(self.page.inner_text(f"{everything} [data-controller-label]"), "Pad: hold LB, press A")
        self.assertIn("Button in Elite: Landing gear toggle (Ship)", self.page.inner_text(everything))
        self.assertIn("Key in Elite: Select target (Ship) and 2 more", self.page.inner_text(navigation))
        self.assertTrue(self.page.is_disabled(f"{navigation} [data-controller-clear]"), "nothing to clear")
        elite = self.page.inner_text(".controller-elite .elite-groups")
        self.assertTrue(all(word in elite.lower() for word in ("ship", "consolex360", "built-in")), elite)
        self.page.click('[data-controller-learn="navigation"]')
        self.wait_for(lambda: any(c.get("operation") == "controller_learn" and c.get("hotkey") == "navigation"
                                  for c in self.commands), "SET didn't ask the app to learn")
        learning = dict(controllers, learning={"action": "navigation", "status": "listening", "at": 1})
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, controllers=learning))
        self.assertEqual(self.page.inner_text(f"{navigation} [data-controller-label]"), "PRESS A BUTTON…")
        self.page.click('[data-controller-learn="navigation"]')
        self.wait_for(lambda: any(c.get("operation") == "controller_cancel" for c in self.commands), "CANCEL")
        self.page.click('[data-controller-clear="toggle_all"]')
        self.wait_for(lambda: any(c.get("operation") == "controller_clear" and c.get("hotkey") == "toggle_all"
                                  for c in self.commands), "CLEAR")

    def test_shortcuts_in_groups_with_a_filter(self):
        """5.7.3: shortcuts sit in their groups; the filter shows all, bound,
        clashing or free ones, remembers the choice, and a search ignores it."""
        controllers = {"enabled": True, "buttons": {}, "learning": {}, "elite": {"groups": [], "error": ""},
                       "keys": {"navigation": {"clashes": ["Select target (Ship)"], "more": 0}}}
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, controllers=controllers))
        self.page.click('[data-settings-section="hotkeys"]')
        groups = self.page.evaluate("[...document.querySelectorAll('[data-settings-panel=hotkeys] .settings-group h4')].map(n => n.textContent)")
        self.assertEqual(groups, ["INPUT", "SHORTCUTS", "OVERLAYS", "OVERLAY CONTROLS", "MUSIC"])
        shown = "[...document.querySelectorAll('.hotkey-row')].filter(n => n.offsetParent).map(n => n.querySelector('[data-hotkey-action]').dataset.hotkeyAction)"
        self.assertEqual(self.page.evaluate(shown), ["navigation", "toggle_all", "music_next"])
        self.assertIn("CLASHES 1", self.page.inner_text('[data-hotkey-filter="clashes"]'))
        self.page.click('[data-hotkey-filter="clashes"]')
        self.assertEqual(self.page.evaluate(shown), ["navigation"])
        self.page.click('[data-hotkey-filter="free"]')
        self.assertEqual(self.page.evaluate(shown), ["music_next"])
        self.assertFalse(self.page.is_visible('[data-settings-group="overlays"]'), "an empty group hides")
        self.assertEqual(self.page.evaluate("localStorage.getItem('voidcompass.settings.hotkeyFilter')"), "free")
        self.page.fill("#settings-search", "navigation")
        self.assertEqual(self.page.evaluate(shown), ["navigation"])
        self.page.fill("#settings-search", "")
        self.page.click('[data-hotkey-filter="bound"]')
        self.assertEqual(self.page.evaluate(shown), ["navigation", "toggle_all"])

    def test_voice_has_its_hearing_and_the_ship_commands(self):
        """5.7.3: talking by voice (moved from the MIND page) and the ship
        commands: what's ready, what to bind in Elite, what you can say."""
        voice = {"listen": {"enabled": True, "installed": True, "download_mb": 497, "notice": "It hears you with Whisper.",
                            "mics": ["Microphone (USB FS AUDIO)"], "mic": "", "mode": "hold", "hotkey": "Ctrl+Alt+Shift+F8",
                            "hotkeys_on": True, "has_test": True, "downloading": False},
                 "ship": {"enabled": True, "running": True, "error": "", "ready": 1, "total": 2,
                          "groups": [{"title": "Maps and panels", "rows": [
                              {"say": "open the galaxy map", "state": "ready",
                               "cells": [{"where": "Ship", "action": "Galaxy map open", "key": "Left Shift+G", "problem": ""}]},
                              {"say": "open the system map", "state": "none",
                               "cells": [{"where": "Ship", "action": "System map open", "key": "", "problem": "no_key"}]}]}],
                          "missing": [{"action": "System map open", "say": "open the system map", "where": "Ship",
                                       "group": "ship", "preset": "Ship · ConsoleX360"}]}}
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice=voice))
        self.page.click('.settings-tab[data-settings-section="voice"]')
        self.assertEqual(self.visible_panels(), ["voice"])
        self.assertIn("1 OF 2 COMMANDS READY", self.page.inner_text('.settings-tab[data-settings-section="voice"]'))
        groups = self.page.evaluate("[...document.querySelectorAll('[data-settings-panel=voice] .settings-group h4')].map(n => n.textContent)")
        self.assertEqual(groups, ["TALK BY VOICE", "COMMAND CONTROLS", "SEQUENCE RECORDER", "WHAT YOU CAN SAY", "Maps and panels"])
        self.assertIn("Ship · ConsoleX360", self.page.inner_text('[data-settings-panel="voice"]'))
        self.assertEqual(self.page.locator('[data-voice-choice="watcher_listen_mic"]').count(), 2)
        # The recorder's new-command vehicle choice stays hidden until requested.
        choices = self.page.locator('[data-settings-panel="voice"] select')
        self.assertEqual(choices.count(), 1)
        self.assertEqual(choices.first.get_attribute("id"), "sequence-new-place")
        self.assertFalse(choices.first.is_visible())
        self.assertEqual(self.page.locator(".voice-commands summary").count(), 0)
        self.assertEqual(self.page.inner_text(".voice-key kbd"), "Ctrl+Alt+Shift+F8")
        commands = self.page.locator(".voice-command")
        self.assertEqual(commands.count(), 2)
        self.assertIn("Left Shift+G", commands.first.inner_text())
        self.assertIn("ADD A KEY IN ELITE", commands.last.inner_text())
        self.page.click('[data-voice-filter="missing"]')
        self.assertFalse(commands.first.is_visible())
        self.assertTrue(commands.last.is_visible())
        self.page.click('[data-voice-filter="all"]')
        self.page.fill("#voice-command-search", "galaxy")
        self.assertTrue(commands.first.is_visible())
        self.assertFalse(commands.last.is_visible())
        self.page.fill("#voice-command-search", "nothing matches")
        self.assertTrue(self.page.is_visible("#voice-filter-empty"))
        self.page.fill("#voice-command-search", "")
        self.page.click('.setting-row:has([data-setting="watcher_ship_enabled"])')
        self.wait_for(lambda: self.saves(), "the switch didn't save")
        self.assertEqual(self.saves()[-1]["values"], {"watcher_ship_enabled": False})
        self.page.click("#voice-test")
        self.wait_for(lambda: any(c.get("operation") == "listen_test" for c in self.commands), "TEST MIC")
        self.page.click('[data-settings-goto="hotkeys"]')
        self.assertEqual(self.visible_panels(), ["hotkeys"])

    def test_voice_sequence_editor_saves_and_restores_default_steps(self):
        defaults = ["focus FocusRadarPanel 4", "UI_Down", "UI_Select"]
        voice = {"listen": {}, "ship": {"enabled": True, "running": True, "ready": 1, "total": 1,
            "macros": {}, "missing": [], "groups": [{"title": "Sequences", "rows": [
                {"id": "deploy_nomad", "say": "deploy the Nomad", "state": "ready", "sequence": defaults,
                 "default_sequence": defaults, "cells": [{"where": "Ship", "action": "Focus radar panel", "key": "3", "problem": ""}]}]}]}}
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice=voice))
        self.page.click('[data-settings-section="voice"]')
        self.page.click("[data-voice-edit]")
        editor = self.page.locator('[data-ship-macro="deploy_nomad"]')
        custom = ["focus FocusRadarPanel 4", "UI_Down x2", "hold UI_Select 1.2"]
        editor.fill("\n".join(custom))
        editor.blur()
        self.wait_for(lambda: self.saves(), "the sequence didn't save")
        self.assertEqual(self.saves()[-1]["values"], {"watcher_ship_macros": {"deploy_nomad": custom}})
        self.page.click('[data-ship-macro-reset="deploy_nomad"]')
        self.wait_for(lambda: len(self.saves()) == 2, "default sequence wasn't restored")
        self.assertEqual(self.saves()[-1]["values"], {"watcher_ship_macros": {}})
        self.assertEqual(editor.input_value(), "\n".join(defaults))
        self.page.set_viewport_size({"width": 850, "height": 800})
        self.assertLessEqual(editor.bounding_box()["width"], 850)

    def test_voice_choices_save_and_a_rejected_model_choice_rolls_back(self):
        voice = {"listen": {"model": "accurate", "mode": "hold", "mic": "", "mics": ["USB mic"]}, "ship": {}}
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice=voice))
        self.page.click('[data-settings-section="voice"]')
        fast = '[data-voice-choice="watcher_listen_model"][data-value="fast"]'
        accurate = '[data-voice-choice="watcher_listen_model"][data-value="accurate"]'
        self.page.click(fast)
        self.wait_for(lambda: self.saves(), "model choice wasn't saved")
        save = self.saves()[-1]
        self.assertEqual(save["values"], {"watcher_listen_model": "fast"})
        self.assertEqual(self.page.get_attribute(fast, "aria-pressed"), "true")
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice=voice,
            last_save={"id": save["save_id"], "ok": False, "detail": "download running"}))
        self.assertEqual(self.page.get_attribute(accurate, "aria-pressed"), "true")
        self.assertEqual(self.page.get_attribute(fast, "aria-pressed"), "false")
        self.page.click('[data-voice-choice="watcher_listen_mode"][data-value="tap"]')
        self.wait_for(lambda: len(self.saves()) == 2, "talk mode wasn't saved")
        self.assertEqual(self.saves()[-1]["values"], {"watcher_listen_mode": "tap"})
        self.page.click('[data-voice-choice="watcher_listen_mic"][data-value="USB mic"]')
        self.wait_for(lambda: len(self.saves()) == 3, "mic choice wasn't saved")
        self.assertEqual(self.saves()[-1]["values"], {"watcher_listen_mic": "USB mic"})

    def test_all_ship_and_app_names_are_editable_and_settings_rail_is_alphabetical(self):
        from tests.test_ship_commands_573 import Deck
        ship = Deck()._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": ship}))
        self.page.click('[data-settings-section="voice"]')
        names = self.page.locator('.settings-tab b').all_text_contents()
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.assertEqual(self.page.locator('[data-voice-edit]').count(), ship["total"])
        self.page.fill("#voice-command-search", "music")
        row = self.page.locator('[data-voice-row="app_music_pause"]')
        row.locator('[data-voice-edit]').click()
        row.locator('[data-command-field="name"]').fill("Quiet cockpit")
        row.locator('[data-command-field="phrase"]').fill("pause soundtrack")
        row.locator('[data-command-field="aliases"]').fill("quiet record\nhalt soundtrack")
        row.locator('[data-command-field="keep_defaults"]').uncheck()
        row.locator('[data-command-save]').click()
        self.wait_for(lambda: self.saves(), "the command name did not save")
        save = self.saves()[-1]
        definitions = save["values"]["watcher_ship_commands"]
        self.assertEqual(definitions["app_music_pause"]["name"], "Quiet cockpit")
        self.assertEqual(definitions["app_music_pause"]["aliases"], ["quiet record", "halt soundtrack"])
        updated = Deck(watcher_ship_commands=definitions)._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": updated},
            last_save={"id": save["save_id"], "ok": True}))
        self.assertEqual(row.locator('.voice-command-say b').inner_text(), "Quiet cockpit")
        self.assertTrue(row.locator('.voice-editor').is_visible())
        row.locator('[data-command-restore]').click()
        self.wait_for(lambda: len(self.saves()) == 2, "restore did not save")
        self.assertEqual(self.saves()[-1]["values"]["watcher_ship_commands"], {})

    def test_custom_commands_can_be_created_grouped_and_deleted(self):
        from tests.test_ship_commands_573 import Deck
        ship = Deck()._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": ship}))
        self.page.click('[data-settings-section="voice"]')
        self.page.click('#voice-command-add')
        form = self.page.locator('#voice-command-new .voice-definition')
        form.locator('[data-command-field="name"]').fill("My chart")
        form.locator('[data-command-field="phrase"]').fill("chart time")
        form.locator('[data-command-field="aliases"]').fill("chart please")
        form.locator('[data-command-field="group"]').fill("My cockpit")
        form.locator('[data-command-field="sequence"]').fill("GalaxyMapOpen\nwait 0.2")
        form.locator('[data-command-save]').click()
        self.wait_for(lambda: self.saves(), "custom command did not save")
        save = self.saves()[-1]
        definitions = save["values"]["watcher_ship_commands"]
        ident = next(iter(definitions))
        self.assertTrue(ident.startswith("custom_"))
        self.assertEqual(definitions[ident]["sequence"], ["GalaxyMapOpen", "wait 0.2"])
        self.assertEqual(definitions[ident]["places"], ["ship"])
        updated = Deck(watcher_ship_commands=definitions)._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": updated},
            last_save={"id": save["save_id"], "ok": True}))
        self.page.click('[data-voice-filter="custom"]')
        row = self.page.locator(f'[data-voice-row="{ident}"]')
        self.assertTrue(row.is_visible())
        row.locator('[data-voice-edit]').click()
        row.locator('[data-command-delete]').click()
        self.wait_for(lambda: len(self.saves()) == 2, "delete did not save")
        self.assertEqual(self.saves()[-1]["values"]["watcher_ship_commands"], {})

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

    def test_map_sequences_are_editable_for_open_close_and_vehicle(self):
        from tests.test_ship_commands_573 import Deck
        ship = Deck()._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": ship}))
        self.page.click('[data-settings-section="voice"]')
        for ident in ("galaxy_map", "galaxy_map:off", "galaxy_map:srv", "system_map", "system_map:off", "system_map:foot"):
            self.assertEqual(self.page.locator(f'[data-ship-macro="{ident}"]').count(), 1)
        self.page.click('[data-voice-filter="ready"]')
        self.assertTrue(self.page.locator('.voice-command:has([data-ship-macro="galaxy_map"])').is_visible())
        editor = self.page.locator('[data-ship-macro="galaxy_map"]')
        self.page.locator('.voice-command:has([data-ship-macro="galaxy_map"]) [data-voice-edit]').click()
        self.assertEqual(editor.input_value(), "GalaxyMapOpen")
        custom = ["GalaxyMapOpen", "wait 0.2"]
        editor.fill("\n".join(custom))
        editor.blur()
        self.wait_for(lambda: self.saves(), "map sequence wasn't saved")
        self.assertEqual(self.saves()[-1]["values"], {"watcher_ship_macros": {"galaxy_map": custom}})
        close = self.page.locator('[data-ship-macro="galaxy_map:off"]')
        self.page.click('[data-voice-tab="galaxy_map:off"]')
        close.fill("UI_Back")
        close.blur()
        self.wait_for(lambda: len(self.saves()) == 2, "close sequence wasn't saved")
        self.assertEqual(self.saves()[-1]["values"], {"watcher_ship_macros": {"galaxy_map": custom, "galaxy_map:off": ["UI_Back"]}})
        self.page.set_viewport_size({"width": 850, "height": 800})
        self.assertLessEqual(close.bounding_box()["width"], 850)

    def test_record_sequence_requires_review_then_saves_only_the_selected_editor(self):
        from tests.test_ship_commands_573 import Deck
        ship = Deck()._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": ship}))
        state = {"status": "idle", "events": [], "steps": [], "errors": [], "can_use": False}
        self.page.route("**/api/data/sequence-recording*", lambda route: route.fulfill(content_type="application/json", body=json.dumps(state)))
        def recorder_command(route):
            payload = json.loads(route.request.post_data or "{}")
            self.commands.append(payload)
            if payload.get("operation") == "sequence_choose":
                state["events"][0]["choice"] = payload["action"]
                state.update(can_use=True, errors=[], steps=[f"hold {payload['action']} 0.15"])
            route.fulfill(content_type="application/json", body='{"accepted":true}')
        self.page.route("**/api/command*", recorder_command)
        self.page.click('[data-settings-section="voice"]')
        self.page.locator('[data-voice-row="galaxy_map"] [data-voice-edit]').click()
        self.page.click('[data-sequence-record="galaxy_map"]')
        self.wait_for(lambda: any(row.get("operation") == "sequence_record" for row in self.commands))
        self.assertEqual(next(row["target"] for row in self.commands if row.get("operation") == "sequence_record"), "galaxy_map")
        state.update(id="record-1", profile="jeff", target="galaxy_map", place="ship", status="review",
                     note="Recording stopped.", errors=[], can_use=True, steps=["hold GalaxyMapOpen 0.15"],
                     events=[{"index": 0, "input": "key:m", "seconds": .15, "focus": 0, "choice": "GalaxyMapOpen",
                              "match_note": "Matched an action in this sequence",
                              "actions": [{"action": "GalaxyMapOpen", "label": "Galaxy map", "playable": True},
                                          {"action": "UI_Select", "label": "Select", "playable": True}]}])
        self.page.wait_for_selector('[data-sequence-choice="0"]')
        self.assertFalse(self.page.locator('[data-sequence-use]').is_disabled())
        self.assertEqual(self.page.input_value('[data-sequence-choice="0"]'), "GalaxyMapOpen")
        self.assertEqual(self.page.locator('[data-sequence-choice="0"] option[value=""]').count(), 0)
        self.assertIn("Matched an action", self.page.inner_text('.sequence-match-note'))
        self.assertEqual(self.saves(), [])
        self.page.select_option('[data-sequence-choice="0"]', "UI_Select")
        self.page.wait_for_function("document.getElementById('sequence-recording-preview').value === 'hold UI_Select 0.15'")
        self.page.select_option('[data-sequence-choice="0"]', "GalaxyMapOpen")
        self.page.wait_for_function("document.getElementById('sequence-recording-preview').value === 'hold GalaxyMapOpen 0.15'")
        self.page.fill('#sequence-recording-preview', "hold GalaxyMapOpen 0.15\nwait 0.9")
        self.page.locator('#sequence-recording-preview').blur()
        changed = dict(SETTINGS, values=dict(SETTINGS["values"], home_system="Sol"), voice={"listen": {}, "ship": ship})
        self.page.evaluate("data => window.__settings.publish(data)", changed)
        self.assertEqual(self.page.input_value('#sequence-recording-preview'), "hold GalaxyMapOpen 0.15\nwait 0.9")
        self.page.click('[data-sequence-use]')
        self.wait_for(lambda: self.saves())
        self.assertEqual(self.saves()[-1]["values"], {"watcher_ship_macros": {"galaxy_map": ["hold GalaxyMapOpen 0.15", "wait 0.9"]}})
        self.assertEqual(self.saves()[-1]["recorded_profile"], "jeff")
        save = self.saves()[-1]
        self.assertEqual(save["recording_id"], "record-1")
        self.assertTrue(self.page.locator('#sequence-recording-preview').is_visible(), "review stays until saving succeeds")
        updated = Deck(watcher_ship_macros=save["values"]["watcher_ship_macros"])._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(changed, voice={"listen": {}, "ship": updated},
            last_save={"id": save["save_id"], "ok": True}))
        state.update(status="saved", events=[], steps=[], can_use=False, note="Recorded sequence saved.")
        self.page.wait_for_function("!document.getElementById('sequence-recording-preview') && document.activeElement.dataset.shipMacro === 'galaxy_map'")
        self.assertEqual(self.page.locator('[data-sequence-use]').count(), 0)
        self.assertTrue(self.page.locator('[data-voice-row="galaxy_map"] .voice-editor').is_visible())

    def test_rejected_recorded_sequence_save_keeps_review_and_draft_open(self):
        from tests.test_ship_commands_573 import Deck
        ship = Deck()._html_ship_controls()
        settings = dict(SETTINGS, voice={"listen": {}, "ship": ship})
        self.page.evaluate("data => window.__settings.publish(data)", settings)
        state = {"id": "rejected-recording", "profile": "jeff", "target": "galaxy_map", "place": "ship", "status": "review",
                 "events": [], "steps": ["hold GalaxyMapOpen 0.15"], "errors": [], "can_use": True}
        self.page.route("**/api/data/sequence-recording*", lambda route: route.fulfill(content_type="application/json", body=json.dumps(state)))
        self.page.click('[data-settings-section="voice"]')
        self.page.wait_for_selector('#sequence-recording-preview')
        draft = "hold GalaxyMapOpen 99"
        self.page.fill('#sequence-recording-preview', draft)
        self.page.click('[data-sequence-use]')
        self.wait_for(lambda: self.saves())
        save = self.saves()[-1]
        self.page.evaluate("data => window.__settings.publish(data)", dict(settings,
            last_save={"id": save["save_id"], "ok": False, "detail": "Invalid hold duration."}))
        self.assertTrue(self.page.locator('#sequence-recording-preview').is_visible())
        self.assertEqual(self.page.input_value('#sequence-recording-preview'), draft)
        self.assertTrue(self.page.locator('[data-sequence-use]').is_visible())

    def test_recording_keeps_the_editor_in_view_with_inline_status_and_stop(self):
        from tests.test_ship_commands_573 import Deck
        ship = Deck()._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": ship}))
        state = {"status": "idle", "events": [], "steps": [], "errors": [], "can_use": False}
        self.page.route("**/api/data/sequence-recording*", lambda route: route.fulfill(content_type="application/json", body=json.dumps(state)))
        def recorder_command(route):
            payload = json.loads(route.request.post_data or "{}")
            self.commands.append(payload)
            if payload.get("operation") == "sequence_record":
                state.update(id="stay-here", profile="jeff", target=payload["target"], place="ship", status="armed",
                             note="Switch to Elite and perform the sequence.")
            elif payload.get("operation") == "sequence_stop":
                state.update(status="review", note="Recording stopped.")
            route.fulfill(content_type="application/json", body='{"accepted":true}')
        self.page.route("**/api/command*", recorder_command)
        self.page.click('[data-settings-section="voice"]')
        self.page.locator('[data-voice-row="request_docking"] [data-voice-edit]').click()
        record = self.page.locator('[data-sequence-record="request_docking"]')
        record.scroll_into_view_if_needed()
        before = record.bounding_box()["y"]
        record.click()
        inline = self.page.locator('[data-sequence-inline="request_docking"]')
        inline.wait_for(state="visible")
        self.assertIn("ARMED", inline.inner_text())
        self.assertAlmostEqual(record.bounding_box()["y"], before, delta=3)
        self.assertGreater(self.page.locator('.pages').evaluate('node => node.scrollTop'), 100)
        self.assertTrue(inline.locator('[data-sequence-stop]').is_visible())
        inline.locator('[data-sequence-stop]').click()
        self.page.wait_for_function("document.querySelector('[data-sequence-inline=request_docking] [role=status]').textContent.includes('REVIEW')")
        self.assertTrue(inline.locator('[data-sequence-review]').is_visible())
        self.assertFalse(inline.locator('[data-sequence-stop]').is_visible())
        self.assertEqual(self.saves(), [])
        inline.locator('[data-sequence-review]').click()
        self.page.wait_for_function("document.getElementById('sequence-recorder').getBoundingClientRect().top > 0")
        self.assertTrue(self.page.locator('#sequence-recorder').is_visible())

    def test_recording_can_fill_a_new_custom_command_without_saving_it_early(self):
        from tests.test_ship_commands_573 import Deck
        ship = Deck()._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(SETTINGS, voice={"listen": {}, "ship": ship}))
        state = {"status": "idle", "events": [], "steps": [], "errors": [], "can_use": False}
        self.page.route("**/api/data/sequence-recording*", lambda route: route.fulfill(content_type="application/json", body=json.dumps(state)))
        self.page.click('[data-settings-section="voice"]')
        self.page.click('#voice-command-add')
        form = self.page.locator('#voice-command-new .voice-definition')
        form.locator('[data-command-field="name"]').fill("Rover panel")
        form.locator('[data-command-field="phrase"]').fill("check rover panel")
        self.page.select_option('#sequence-new-place', "srv")
        self.page.click('[data-sequence-record="new"]')
        self.wait_for(lambda: any(row.get("operation") == "sequence_record" for row in self.commands))
        self.assertEqual(next(row["place"] for row in self.commands if row.get("operation") == "sequence_record"), "srv")
        steps = ["focus FocusLeftPanel_Buggy 2", "hold UI_Select 0.15"]
        state.update(id="record-new", profile="jeff", target="new", place="srv", status="review", note="Review ready.",
                     can_use=True, steps=steps, events=[{"index": 0, "input": "key:2", "seconds": .15, "focus": 0,
                         "choice": "FocusLeftPanel_Buggy", "actions": [{"action": "FocusLeftPanel_Buggy", "label": "Left panel", "playable": True}]}])
        self.page.wait_for_selector('[data-sequence-use]')
        changed = dict(SETTINGS, values=dict(SETTINGS["values"], home_system="Sol"), voice={"listen": {}, "ship": ship})
        self.page.evaluate("data => window.__settings.publish(data)", changed)
        self.assertTrue(form.is_visible())
        self.assertEqual(form.locator('[data-command-field="name"]').input_value(), "Rover panel")
        self.page.click('[data-sequence-use]')
        self.page.wait_for_function("wanted => document.querySelector('#voice-command-new [data-command-field=sequence]').value === wanted", arg="\n".join(steps))
        self.assertEqual(form.locator('[data-command-field="sequence"]').input_value(), "\n".join(steps))
        self.assertFalse(form.locator('[data-command-place="ship"]').is_checked())
        self.assertTrue(form.locator('[data-command-place="srv"]').is_checked())
        self.assertEqual(self.saves(), [])
        form.locator('[data-command-save]').click()
        self.wait_for(lambda: self.saves())
        value = next(iter(self.saves()[-1]["values"]["watcher_ship_commands"].values()))
        self.assertEqual((value["name"], value["sequence"], value["places"]), ("Rover panel", steps, ["srv"]))
        save = self.saves()[-1]
        ident = next(iter(save["values"]["watcher_ship_commands"]))
        self.assertEqual(save["recording_id"], "record-new")
        self.assertEqual(save["recorded_command_id"], ident)
        updated = Deck(watcher_ship_commands=save["values"]["watcher_ship_commands"])._html_ship_controls()
        self.page.evaluate("data => window.__settings.publish(data)", dict(changed, voice={"listen": {}, "ship": updated},
            last_save={"id": save["save_id"], "ok": True}))
        state.update(status="saved", target=ident + ":srv", events=[], steps=[], can_use=False, note="Recorded sequence saved.")
        self.page.wait_for_function("wanted => !document.getElementById('sequence-recording-preview') && document.activeElement.dataset.shipMacro === wanted", arg=ident + ":srv")
        self.assertTrue(self.page.locator('#voice-command-new').is_hidden())
        self.page.set_viewport_size({"width": 650, "height": 900})
        self.assertLessEqual(self.page.locator('#sequence-recorder').bounding_box()["width"], 650)
        self.page.screenshot(path=str(Path(tempfile.gettempdir()) / "voidcompass-sequence-recorder-650.png"))

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

    def test_every_section_and_the_workshop_fit_larger_text_and_smaller_windows(self):
        settings = json.loads(json.dumps(SETTINGS))
        settings["theme_editor"]["keys"] = list(themes.THEME_KEYS)
        settings["themes"] = [{"name": name, "swatch": themes.resolve_theme(name, {})[1]}
                              for name in themes.BUILTIN_THEMES]
        settings["paths"]["journal"]["latest"] = "Journal.2026-10-29T123456.01.log"
        self.page.evaluate("data => window.__settings.publish(data)", settings)
        sections = ["journal", "appearance", "flight", "hotkeys", "voice", "galnet", "integrations", "diagnostics", "updates"]
        for width, height, scale, minimum in ((1600, 1000, 100, 0), (1280, 680, 120, 12),
                                              (980, 800, 140, 14), (700, 800, 135, 16)):
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.evaluate("""async ([scale, minimum]) => {
              const sizing = await import('/dashboard/text-size.js');
              sizing.applyTextSize(scale, minimum);
            }""", [scale, minimum])
            for section in sections:
                with self.subTest(section=section, width=width, scale=scale):
                    self.page.locator(f'.settings-tab[data-settings-section="{section}"]').click()
                    if section == "appearance":
                        self.page.locator('.theme-workshop').evaluate('node => node.open = true')
                    geometry = self.page.evaluate("""() => {
                      const page = document.querySelector('.settings-page');
                      const panel = page.querySelector('[data-settings-panel]:not([hidden])');
                      const outer = page.getBoundingClientRect();
                      const clipped = [...panel.querySelectorAll('h3, h4, .setting-copy, .setting-control, .setting-status, .theme-colour-grid label, button')]
                        .filter(node => node.getClientRects().length).filter(node => {
                          const b = node.getBoundingClientRect();
                          return b.left < outer.left - 1 || b.right > outer.right + 1
                            || node.scrollWidth > node.clientWidth + 2;
                        }).map(node => node.className || node.tagName);
                      return {fits: page.scrollWidth <= page.clientWidth + 1, clipped};
                    }""")
                    self.assertTrue(geometry['fits'], geometry)
                    self.assertEqual(geometry['clipped'], [], geometry)
        header = self.page.locator('[data-settings-panel="updates"] .settings-section-head')
        before = header.evaluate('node => getComputedStyle(node).backgroundImage')
        snapshot = overview_state()
        snapshot['theme'] = {'palette': {'accent': '#bf73ff', 'orange': '#ffcb55'}}
        self.page.evaluate('([d,s]) => window.__settings.render(d,s)', [snapshot, settings])
        self.assertNotEqual(before, header.evaluate('node => getComputedStyle(node).backgroundImage'))

    def test_search_can_be_cleared_and_group_jumps_use_the_deck_scroller(self):
        self.page.fill('#settings-search', 'fuel')
        self.assertEqual(self.page.locator('#settings-search-summary').inner_text(), '1 match across 1 section')
        self.page.locator('.settings-toolbar [data-settings-clear]').click()
        self.assertEqual(self.visible_panels(), ['journal'])
        self.assertTrue(self.page.locator('#settings-search').evaluate('node => node === document.activeElement'))
        self.page.fill('#settings-search', 'zzzz')
        self.page.keyboard.press('Escape')
        self.assertEqual(self.page.input_value('#settings-search'), '')
        self.assertFalse(self.page.locator('.settings-no-match').is_visible())
        self.page.locator('.settings-tab[data-settings-section="integrations"]').click()
        self.page.locator('[data-settings-jump="settings-integrations-local-api"]').click()
        position = self.page.evaluate("""() => {
          const group = document.getElementById('settings-integrations-local-api');
          const scroll = document.querySelector('.pages');
          return {scroll: scroll.scrollTop, top: group.getBoundingClientRect().top,
            viewportTop: scroll.getBoundingClientRect().top, viewportBottom: scroll.getBoundingClientRect().bottom,
            focused: document.activeElement.id};
        }""")
        self.assertGreater(position['scroll'], 0)
        self.assertGreaterEqual(position['top'], position['viewportTop'] - 1)
        self.assertLess(position['top'], position['viewportBottom'])
        self.assertEqual(position['focused'], 'settings-integrations-local-api-heading')
        self.page.get_by_text('Port', exact=True).click()
        self.assertTrue(self.page.locator('#setting-api-port').evaluate('node => node === document.activeElement'))
        self.page.locator('.settings-tab[data-settings-section="journal"]').click()
        self.assertEqual(self.page.locator('.pages').evaluate('node => node.scrollTop'), 0)


if __name__ == "__main__":
    unittest.main()
