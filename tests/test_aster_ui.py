"""5.7.4: Real browser checks of companion selection, independent story and Three.js states."""
import json
import tempfile
from pathlib import Path
import unittest
from tests import test_watcher_talk_573 as talk
from voidcompass.overlays import aster_lore

ARTIFACTS = Path(tempfile.gettempdir()) / "voidcompass-aster-checks"
ARTIFACTS.mkdir(exist_ok=True)


class AsterPageTests(unittest.TestCase):
    setUpClass = classmethod(talk.TalkPageTests.setUpClass.__func__)
    tearDownClass = classmethod(talk.TalkPageTests.tearDownClass.__func__)
    load_module = talk.TalkPageTests.load_module
    render = talk.TalkPageTests.render
    commands = talk.TalkPageTests.commands

    def setUp(self):
        talk.TalkPageTests.setUp(self)
        self.page.route("http://watcher.test/api/data/companion-live", lambda route: route.fulfill(content_type="application/json", body=json.dumps({"speech": None, "hearing": None})))
        self.page.evaluate("async () => {await import('/assets/aster-companion.js'); window.__draws=0; const p=WebGL2RenderingContext.prototype; const draw=p.drawElements; p.drawElements=function(...args){window.__draws++;return draw.apply(this,args)};}")
        self.data.update(identity="aster", companion_name="Aster", nature="officer", frequency="occasional", lore=aster_lore.page({}, 0), heartbeat={"orb": {"identity": "aster", "accent": "brass", "motion": False}})
        self.render()
        self.page.click('[data-watcher-tab="now"]')

    def test_identity_picker_and_own_story_with_no_watcher_control_leaks(self):
        self.assertEqual(self.page.get_attribute('button[data-companion="aster"]', 'aria-pressed'), 'true')
        self.assertEqual(self.page.inner_text('.watcher-stage-head > span'), 'ASTER')
        self.page.click('[data-watcher-tab="settings"]')
        self.assertFalse(self.page.is_visible('[data-watcher-setting="heartbeat_personality"]'))
        self.page.click('[data-watcher-tab="story"]')
        self.assertIn('Unopened report', self.page.inner_text('#watcher-lore'))
        self.assertNotIn('Iven', self.page.inner_text('#watcher-reader'))
        self.assertFalse(self.page.is_visible('#watcher-echoes'))
        self.page.click('[data-watcher-tab="voice"]')
        self.assertFalse(self.page.is_visible('.watcher-finding'))
        self.page.click('button[data-companion="watcher"]')
        self.assertIn({'page': 'watcher', 'operation': 'companion_identity', 'value': 'watcher'}, self.commands())
        self.data['identity'] = 'watcher'; self.data['companion_name'] = 'The Watcher'; self.data['lore'] = {}
        self.render()
        self.page.click('[data-watcher-tab="settings"]')
        self.assertTrue(self.page.is_visible('[data-watcher-setting="heartbeat_personality"]'))
        self.assertFalse(self.page.is_visible('.aster-instrument'))

    def test_webgl_draws_and_real_live_signals_drive_states(self):
        self.page.wait_for_function('() => window.__draws > 0')
        self.assertTrue(self.page.is_visible('.aster-instrument'))
        for live, expected in (({'speech': {'level': .8}}, 'speaking'), ({'hearing': {'stage': 'listening', 'level': .1}}, 'listening'), ({'hearing': {'stage': 'hearing'}}, 'working'), ({'working': True}, 'working')):
            self.page.evaluate('live => window.AsterCompanion.update(document.getElementById("watcher-orb"), {orb: {identity: "aster", motion: false}}, live)', live)
            self.assertEqual(self.page.get_attribute('.aster-instrument', 'data-state'), expected)
        self.page.evaluate('() => window.AsterCompanion.update(document.getElementById("watcher-orb"), {orb: {identity: "aster"}, vitals: {low_fuel: true}}, {})')
        self.assertEqual(self.page.get_attribute('.aster-instrument', 'data-state'), 'alert')
        self.page.screenshot(path=str(ARTIFACTS / 'dashboard-1440.png'))

    def test_narrow_layout_and_story_reader(self):
        self.data['lore'] = aster_lore.page({'lore': [[aster_lore.PASSAGES[0][0], 1800000000]]}, 1)
        self.render()
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.click('[data-watcher-tab="story"]')
        self.page.click('[data-chapter="0"]')
        self.assertIn(aster_lore.PASSAGES[0][5], self.page.inner_text('#watcher-reader'))
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 391)
        self.page.screenshot(path=str(ARTIFACTS / 'dashboard-390.png'), full_page=True)
    def test_aster_runs_through_the_real_dashboard_server_and_security_policy(self):
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
        from tests.test_dashboard_overview_visuals import overview_state
        self.page.close()
        server = HtmlDashboardServer(talk.ROOT / "web/dashboard", image_root=talk.ROOT / "assets/images", command_callback=lambda payload: True)
        self.addCleanup(server.stop)
        from voidcompass.dashboard.dashboard_journey_mixin import DashboardJourneyMixin
        provider = DashboardJourneyMixin()
        live = {"speech": None, "hearing": None, "working": False, "identity": "aster"}
        provider._watcher_live_levels = lambda: live
        server.data_provider = provider._html_data
        state = overview_state()
        server.publish(state)
        context = self.browser.new_context(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        self.addCleanup(context.close)
        page = context.new_page()
        errors, missing = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("response", lambda response: missing.append(response.url) if response.status >= 400 else None)
        page.goto(server.url)
        page.wait_for_selector("body.ready", timeout=15000)
        page.click('.nav-item[data-page="watcher"]')
        self.data["voice"] = {"identity": "aster", "model_name": "Aster officer voice", "installed": False, "enabled": False, "size_mb": 86}
        state["workspace"] = {"page": "watcher", "ready": True, "data": self.data}
        server.publish(state)
        page.wait_for_selector('[data-companion="aster"] .aster-instrument', state="visible")
        self.assertEqual(page.inner_text('.watcher-stage-head > span'), "ASTER")
        live["speech"] = {"level": .8}
        page.locator('.aster-instrument[data-state="speaking"]').wait_for(state="visible")
        page.click('[data-watcher-tab="voice"]')
        self.assertEqual(page.inner_text('#watcher-voice-model-name'), "Aster officer voice")
        self.assertEqual(errors, [])
        self.assertEqual(missing, [])


from tests import test_watcher_three_568 as three
from tests.test_heartbeat_orb import snapshot


class AsterOverlayTests(unittest.TestCase):
    setUpClass = classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three.WatcherThreeBrowserTests.open_page

    def test_actual_overlay_transparent_sizes_and_switching(self):
        page = self.open_page('heartbeat/index.html')
        page.wait_for_function('typeof renderHeartbeat === "function" && window.AsterCompanion')
        data = snapshot(reduced=True)
        data['heartbeat']['orb'].update(identity='aster', size=144, accent='cyan', motion=False)
        page.set_viewport_size({'width': 144, 'height': 144})
        page.evaluate('data => renderHeartbeat(data)', data)
        page.wait_for_function('document.querySelector(".aster-instrument")?.getContext("webgl2")')
        self.assertTrue(page.is_visible('.aster-instrument'))
        self.assertTrue(page.evaluate('heartbeatOrb.suspended'))
        for size in (96, 144, 192):
            page.set_viewport_size({'width': size, 'height': size})
            data['heartbeat']['orb']['size'] = size
            page.evaluate('data => renderHeartbeat(data)', data)
            page.wait_for_timeout(100)
            self.assertEqual(page.locator('.aster-instrument').bounding_box()['width'], size)
        shot = page.screenshot(path=str(ARTIFACTS / 'overlay-192.png'), omit_background=True)
        from PIL import Image
        from io import BytesIO
        pixels = Image.open(BytesIO(shot)).convert("RGBA")
        self.assertEqual(pixels.getpixel((0, 0))[3], 0)
        self.assertIsNotNone(pixels.getchannel("A").getbbox())
        data['heartbeat']['orb']['identity'] = 'watcher'
        page.evaluate('data => renderHeartbeat(data)', data)
        self.assertFalse(page.is_visible('.aster-instrument'))
        self.assertFalse(page.evaluate('heartbeatOrb.suspended'))

    def test_webgl_error_is_clear_and_does_not_retry_each_poll(self):
        page = self.open_page('heartbeat/index.html', disable_webgl=True)
        page.wait_for_function('typeof renderHeartbeat === "function" && window.AsterCompanion')
        data = snapshot(); data['heartbeat']['orb']['identity'] = 'aster'
        page.evaluate('data => renderHeartbeat(data)', data)
        self.assertIn('WebGL', page.inner_text('.aster-renderer-error'))
        attempts = page.evaluate('window.blockedWebGL')
        for _ in range(3): page.evaluate('data => renderHeartbeat(data)', data)
        self.assertEqual(page.evaluate('window.blockedWebGL'), attempts)
