"""Studio commands must change the live model and rendered pixels, even when idle."""
from collections import deque
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock

from PIL import Image, ImageChops
from tests import test_watcher_three_568 as three
from tests.test_heartbeat_orb import snapshot
from tests.test_overlay_studio_displays import _Studio, surface
from voidcompass.core import companions
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD
from voidcompass.overlays.html_heartbeat_overlay import HtmlHeartbeatBridge


def live_studio(identity):
    studio = _Studio([])
    studio.config.update(companion_identity=identity, heartbeat_overlay_enabled=True,
                         reduced_motion_enabled=False, **companions.new_defaults())
    hud = HeartbeatHUD.__new__(HeartbeatHUD)
    hud.config = studio.config
    hud.mind = companions.create_mind(None, studio.config)
    hud._check_profile = Mock()
    hud._last_pulse_ts = time.time()
    hud._pulse_serial = hud._status_serial = 0
    hud._events = deque()
    hud._activity_kind, hud._activity_label, hud._activity_state = "startup", "LINK READY", "DOCKED"
    hud._state_changed = False
    hud._vitals = {}
    hud._thought_payload = lambda: None
    hud._palette = {}
    hud._redraw()
    bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
    bridge.overlay, bridge.config = hud, studio.config
    bridge.model_attr, bridge.snapshot_key, bridge.template = "_html_render_model", "heartbeat", "heartbeat"
    bridge.overlay_id, bridge.enabled_key = "heartbeat", "heartbeat_overlay_enabled"
    bridge.x_key, bridge.y_key = "heartbeat_hud_x", "heartbeat_hud_y"
    bridge._last_fingerprint = bridge._last_quick_fingerprint = None
    bridge.win = SimpleNamespace(state=lambda: "normal", winfo_x=lambda: 20, winfo_y=lambda: 20,
                                 master=SimpleNamespace())
    bridge.surface = SimpleNamespace(publish=Mock(), update_window=Mock())
    hud._html_heartbeat_bridge, hud.sync_html_window = bridge, bridge.sync_window
    studio.heartbeat_hud = hud
    def records(**kwargs):
        size = companions.display_size(studio.config)
        return [dict(surface(20, width=size, height=size), id="heartbeat_hud", label=companions.name(studio.config),
                     short_label=companions.name(studio.config).upper(), group="Companion", html_ready=True)]
    studio._html_overlay_records = records
    return studio, hud, bridge


class LiveStudioTests(unittest.TestCase):
    def test_every_control_publishes_the_active_model_without_a_journal_tick(self):
        for identity in companions.NEW_IDENTITIES:
            studio, hud, bridge = live_studio(identity)
            for key, value, field, expected in (
                ("companion_size", "192", "size", 192),
                ("companion_accent", "brass", "accent", "brass"),
                ("companion_focus", "off", "focus_movement", "off"),
                ("companion_liveliness", "alive", "liveliness", "alive"),
                ("heartbeat_frame_rate", "15", "frame_rate", 15),
            ):
                before = bridge.surface.publish.call_count
                self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "save_settings", key: value}))
                self.assertEqual(bridge.surface.publish.call_count, before + 1)
                published = bridge.surface.publish.call_args.args[0]
                self.assertEqual(published["heartbeat"]["orb"][field], expected)
                self.assertEqual(published["heartbeat"]["orb"]["identity"], identity)
                self.assertEqual(published["window"]["width"], 192)
            self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "toggle_option", "key": "companion_motion", "value": False}))
            self.assertFalse(bridge.surface.publish.call_args.args[0]["heartbeat"]["orb"]["motion"])
            count = bridge.surface.publish.call_count
            hud.apply_settings()
            self.assertEqual(bridge.surface.publish.call_count, count, "unchanged settings need no duplicate delivery")


class CrewMotionBrowserTests(unittest.TestCase):
    setUpClass = classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three.WatcherThreeBrowserTests.open_page

    def ready(self):
        page = self.open_page("heartbeat/index.html")
        page.set_viewport_size({"width": 256, "height": 256})
        page.route("http://watcher3d.test/api/live*", lambda route: route.fulfill(content_type="application/json", body="{}"))
        page.wait_for_function("Boolean(window.CrewCompanion && window.renderHeartbeat)")
        return page

    def pixels(self, page):
        return Image.open(BytesIO(page.screenshot())).convert("RGB")

    def test_idle_animation_changes_visible_pixels_with_focus_fixed(self):
        page = self.ready()
        for identity in companions.NEW_IDENTITIES:
            for size, minimum in ((54, 40), (96, 150)):
                data = snapshot(crt=False)
                data["heartbeat"]["orb"].update(identity=identity, size=size, motion=True, focus_movement="off")
                page.evaluate("data => renderHeartbeat(data)", data)
                page.wait_for_function('CrewCompanion.inspect(document.getElementById("orb"))?.frames > 2')
                first = self.pixels(page)
                page.wait_for_timeout(650)
                diff = ImageChops.difference(first, self.pixels(page))
                self.assertGreater(sum(max(rgb) > 30 for rgb in diff.get_flattened_data()), minimum,
                                   "idle movement must be visible at a small size without gaze or speech")

    def test_studio_models_change_size_colour_motion_focus_intensity_and_rate(self):
        page = self.ready()
        for identity in companions.NEW_IDENTITIES:
            studio, hud, bridge = live_studio(identity)
            def send(**fields):
                self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "save_settings", **fields}))
                page.evaluate("data => renderHeartbeat(data)", bridge.surface.publish.call_args.args[0])
                page.wait_for_timeout(80)
            send(companion_size="96", companion_accent="cyan", companion_focus="off", companion_liveliness="calm", heartbeat_frame_rate="15")
            studio._handle_html_overlay_studio_command({"operation": "toggle_option", "key": "companion_motion", "value": False})
            page.evaluate("data => renderHeartbeat(data)", bridge.surface.publish.call_args.args[0])
            page.wait_for_timeout(150)
            cyan = self.pixels(page)
            send(companion_accent="brass")
            self.assertGreater(sum(max(rgb) > 20 for rgb in ImageChops.difference(cyan, self.pixels(page)).get_flattened_data()), 50,
                               "accent changes must repaint the parked display without resizing or animation")
            send(companion_size="192", companion_liveliness="alive", heartbeat_frame_rate="60")
            info = page.evaluate('CrewCompanion.inspect(document.getElementById("orb"))')
            self.assertEqual((info["width"], info["height"]), (192, 192))
            self.assertEqual((info["accent"], info["focus"], info["intensity"], info["frameRate"]), ("#e8c48c", "off", 1.6, 60))
            self.assertIsNotNone(ImageChops.difference(cyan, self.pixels(page)).getbbox())
            self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "toggle_option", "key": "companion_motion", "value": False}))
            page.evaluate("data => renderHeartbeat(data)", bridge.surface.publish.call_args.args[0])
            page.wait_for_timeout(150)
            frames = page.evaluate('CrewCompanion.inspect(document.getElementById("orb")).frames')
            still = self.pixels(page)
            page.wait_for_timeout(250)
            self.assertEqual(page.evaluate('CrewCompanion.inspect(document.getElementById("orb")).frames'), frames)
            self.assertIsNone(ImageChops.difference(still, self.pixels(page)).getbbox())
            # A new event must wake a display with idle motion turned off.
            data = bridge.surface.publish.call_args.args[0]
            data["heartbeat"]["events"] = [{"seq": 1, "event": "Scan", "weight": .8, "gaze": "left"}]
            page.evaluate("data => renderHeartbeat(data)", data)
            page.wait_for_timeout(180)
            self.assertGreater(page.evaluate('CrewCompanion.inspect(document.getElementById("orb")).frames'), frames + 1)

    def test_real_studio_controls_save_and_republish_the_new_companion(self):
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
        from tests.test_dashboard_overview_visuals import overview_state
        root = Path(__file__).resolve().parents[1]
        studio, hud, bridge = live_studio("axiom")
        state = overview_state()
        server = HtmlDashboardServer(root / "web/dashboard")
        self.addCleanup(server.stop)
        def publish():
            state["overlay_studio"] = studio._html_overlay_studio()
            state["companion"] = {"identity": companions.identity(studio.config)}
            server.publish(state)
        def command(payload):
            if payload.get("action") == "overlay_studio":
                result = studio._handle_html_overlay_studio_command(payload)
                publish()
                return result
            return True
        server.set_command_callback(command)
        publish()
        context = self.browser.new_context(viewport={"width": 1600, "height": 1100}, reduced_motion="no-preference")
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server.url)
        page.wait_for_selector("body.ready", timeout=15000)
        page.click('.nav-item[data-page="overlay-studio"]')
        for identity in companions.NEW_IDENTITIES:
            studio.config["companion_identity"] = identity
            hud.mind = companions.create_mind(None, studio.config)
            hud.apply_settings(); publish()
            page.wait_for_function('id => document.querySelector("[data-studio-settings=heartbeat_hud]").dataset.identity === id', arg=identity)
            # Select the single companion surface in the roster.
            page.locator('#studio-overlay-index button').first.click()
            for key, value, field, expected in (
                ("companion_size", "192", "size", 192),
                ("companion_accent", "signature", "accent", "signature"),
                ("companion_accent", "brass", "accent", "brass"),
                ("companion_focus", "expressive", "focus_movement", "expressive"),
                ("companion_liveliness", "alive", "liveliness", "alive"),
                ("heartbeat_frame_rate", "15", "frame_rate", 15),
            ):
                control = page.locator(f'[data-studio-setting="{key}"]')
                control.click()
                control.press("Escape")
                with page.expect_response(lambda response: "/api/command" in response.url and response.request.post_data_json.get(key) == value) as changed:
                    control.select_option(value)
                self.assertTrue(changed.value.ok)
                page.wait_for_function('([key,value]) => document.querySelector(`[data-studio-setting="${key}"]`).closest(".studio-field").classList.contains("saved")', arg=[key, value])
                self.assertEqual(bridge.surface.publish.call_args.args[0]["heartbeat"]["orb"][field], expected)
            # Motion is shared by the whole crew: one click sets it for every companion.
            wanted = not page.is_checked('[data-overlay-option="companion_motion"]')
            with page.expect_response(lambda response: "/api/command" in response.url and response.request.post_data_json.get("key") == "companion_motion") as changed:
                page.locator('[data-overlay-option="companion_motion"]').locator("..").click()
            self.assertTrue(changed.value.ok)
            self.assertEqual(page.is_checked('[data-overlay-option="companion_motion"]'), wanted)
            self.assertEqual({studio.config[key] for key in companions.shared_display("companion_motion", True)}, {wanted})
            self.assertEqual(bridge.surface.publish.call_args.args[0]["heartbeat"]["orb"]["motion"], wanted)
        self.assertEqual(errors, [])

    def test_theme_accent_uses_the_app_theme_instead_of_the_panel_decoration(self):
        page = self.ready()
        for identity in companions.NEW_IDENTITIES:
            data = snapshot(crt=False)
            data["heartbeat"]["orb"].update(identity=identity, size=96, motion=False, accent="theme")
            page.evaluate("data => renderHeartbeat(data)", data)
            page.evaluate('''data => {
                document.documentElement.style.setProperty("--accent", "#72bb88");
                document.getElementById("orb").parentElement.style.setProperty("--accent", "#112233");
                CrewCompanion.update(document.getElementById("orb"), data.heartbeat);
            }''', data)
            self.assertEqual(page.evaluate('CrewCompanion.inspect(document.getElementById("orb")).accent'), "#72bb88")
