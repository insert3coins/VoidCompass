"""Host push, atomic snapshots and versioned layout acknowledgements (5.6.8)."""
import json
import os
from pathlib import Path
import threading
import time
import unittest
from urllib.request import urlopen

from voidcompass.overlays.html_overlay_host import _OverlayHost, HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'


class DeliveryServerTests(unittest.TestCase):
    def setUp(self):
        self.server = HtmlOverlayServer(WEB)
        self.addCleanup(self.server.stop)
        self.server.register('test', 'cargo')

    def publish(self, value, **extra):
        return self.server.publish('test', {'value': value, 'window': {'visible': False, 'width': 410, 'height': 190}, **extra})

    def receipt(self, packet=None, **extra):
        packet = packet or self.server.delivery('test')
        return {'generation': packet['generation'], 'layout_revision': packet['layout_revision'],
                'revision': packet['revision'], 'measurement': 1, 'measured': True, 'content_height': 200, **extra}

    def test_plain_state_coalesces_but_event_changes_keep_their_order(self):
        for value in range(1, 5):
            self.publish(value)
        self.assertEqual([r['snapshot']['value'] for r in self.server.delivery('test')['deliveries']], [4])
        self.server.register('notices', 'toast')
        for value in range(1, 5):
            self.server.publish('notices', {'notifications': [{'id': value}], 'value': value})
        packet = self.server.delivery('notices')
        self.assertEqual([r['snapshot']['value'] for r in packet['deliveries']], [1, 2, 3, 4])
        self.assertTrue(all(r['ordered'] for r in packet['deliveries']))
        self.server.acknowledge_rendered('notices', self.receipt(packet))
        self.assertFalse(self.server._overlays['notices'].ordered)

    def test_companion_events_are_retained_without_queueing_every_vital_reading(self):
        self.server.register('eye', 'heartbeat')
        for value in range(5):
            self.server.publish('eye', {'heartbeat': {'events': [{'id': 1}], 'vitals': {'heat': value}}})
        packet = self.server.delivery('eye')
        self.assertEqual([r['revision'] for r in packet['deliveries']], [1, 5])
        self.server.publish('eye', {'heartbeat': {'events': [{'id': 1}, {'id': 2}]}})
        self.assertEqual([r['revision'] for r in self.server.delivery('eye')['deliveries']], [1, 6])

    def test_only_a_current_measurement_can_make_a_versioned_page_current(self):
        self.publish(1)
        old = self.server.delivery('test')
        self.server.acknowledge_rendered('test', self.receipt(old))
        self.assertTrue(self.server.window_manifest()['test']['render_current'])
        self.server.update_window('test', {'visible': False, 'width': 820, 'height': 380})
        latest = self.server.delivery('test')
        self.server.acknowledge_rendered('test', self.receipt(old, measurement=2, content_height=999))
        self.assertFalse(self.server.window_manifest()['test']['render_current'])
        self.assertEqual(self.server.rendered_content_height('test'), 200)
        self.server.acknowledge_rendered('test', self.receipt(latest, measurement=3, content_height=400))
        self.assertTrue(self.server.window_manifest()['test']['render_current'])
        self.server.acknowledge_rendered('test', self.receipt(latest, measurement=2, content_height=999))
        self.assertEqual(self.server.rendered_content_height('test'), 400)
        self.publish(2)
        self.assertFalse(self.server.window_manifest()['test']['render_current'])
        self.server.acknowledge_rendered('test', self.receipt(latest, measurement=4, content_height=999))
        self.assertEqual(self.server.rendered_content_height('test'), 400)

    def test_old_page_replies_and_malformed_measurements_cannot_change_new_state(self):
        self.publish(1)
        old = self.server.delivery('test')
        self.server.request_reload('test')
        self.assertFalse(self.server.acknowledge_rendered('test', self.receipt(old)))
        self.assertEqual(self.server.rendered_revision('test'), -1)
        latest = self.server.delivery('test')
        self.server.acknowledge_rendered('test', self.receipt(latest, content_height=230))
        with self.assertRaises(ValueError):
            self.server.acknowledge_rendered('test', self.receipt(latest, content_height='bad'))
        self.assertEqual(self.server.rendered_content_height('test'), 230)
        # A later shape report must not erase the height.
        payload = self.receipt(latest, measurement=2, shapes=[])
        del payload['content_height']
        self.server.acknowledge_rendered('test', payload)
        self.assertEqual(self.server.rendered_content_height('test'), 230)

    def test_hidden_model_changes_wake_the_shared_host_and_snapshot_revision_is_atomic(self):
        self.publish(1)
        host = _OverlayHost(self.server.url, None)
        host.manifest()
        result = []
        worker = threading.Thread(target=lambda: result.append(host.manifest()), daemon=True)
        worker.start()
        self.publish(2)
        worker.join(2)
        self.assertFalse(worker.is_alive())
        packet = result[0]['test']['delivery']
        self.assertEqual(packet['deliveries'][-1]['snapshot']['value'], 2)
        self.assertEqual(packet['revision'], self.server._overlays['test'].revision)
        self.assertFalse(result[0]['test']['window']['visible'])
        url = f'http://127.0.0.1:{self.server.port}/api/snapshot?token={self.server.token}&overlay=test'
        with urlopen(url + '&envelope=1') as response:
            envelope = json.load(response)
        with urlopen(url) as response:
            raw = json.load(response)
        self.assertEqual(envelope['deliveries'][-1]['snapshot'], raw)
        self.assertNotIn('revision', raw, 'the existing raw snapshot API remains compatible')
        seen = [packet[key] for key in ('generation', 'layout_revision', 'revision')]
        self.assertEqual(self.server.delivery('test', seen)['deliveries'], [])


HARNESS = '''<!doctype html><meta charset="utf-8"><main id="view" style="width:100%;min-height:30px"></main>
<script src="/assets/overlay-client.js"></script><script>
window.seen=[]; window.block=false;
window.client=VoidCompassOverlay.startPolling({token:TOKEN,overlay:'test',interval:100,
  contentHeight:()=>document.getElementById('view').getBoundingClientRect().height,
  async render(model) {
    seen.push(model.value); document.getElementById('view').textContent=String(model.value);
    if (block && model.value===2) await new Promise(resolve=>window.resume=resolve);
  }});
</script>'''


class DeliveryBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.server = HtmlOverlayServer(WEB)
        self.addCleanup(self.server.stop)
        self.server.register('test', 'cargo')
        self.page = self.browser.new_page(viewport={'width': 410, 'height': 190})
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(self.errors, []))
        self.page.route('**/delivery-test.html', lambda route: route.fulfill(
            content_type='text/html', body=HARNESS.replace('TOKEN', json.dumps(self.server.token))))
        self.page.add_init_script('''window.__listeners=[];
          window.chrome={webview:{addEventListener:(_,f)=>__listeners.push(f),removeEventListener:()=>{}}};
          window.nativeDeliver=packet=>__listeners.forEach(f=>f({data:packet}));
          Object.defineProperty(document,'hidden',{get:()=>true});
          window.requestAnimationFrame=()=>0;''')

    def start(self, template='cargo'):
        self.server._overlays['test'].template = template
        self.publish(1)
        self.page.goto(f'http://127.0.0.1:{self.server.port}/delivery-test.html')
        self.wait_revision(self.server._overlays['test'].revision)

    def publish(self, value):
        return self.server.publish('test', {'value': value, 'notifications': [{'id': value}],
                                           'window': {'visible': False, 'width': 410, 'height': 190}})

    def deliver(self):
        self.page.evaluate('packet=>nativeDeliver(packet)', self.server.delivery('test'))

    def wait_revision(self, revision):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.page.wait_for_timeout(20)
            if self.server.rendered_revision('test') >= revision and self.server.is_ready('test'):
                return
        self.fail(f'page did not acknowledge {revision}')

    def test_hidden_page_applies_push_without_animation_frames_and_coalesces_busy_state(self):
        self.start()
        self.page.evaluate('block=true')
        self.publish(2); self.deliver()
        self.page.wait_for_function('Boolean(window.resume)')
        self.publish(3); self.deliver()
        revision = self.publish(4); self.deliver()
        self.page.evaluate('resume()')
        self.wait_revision(revision)
        self.assertEqual(self.page.evaluate('seen'), [1, 2, 4])
        self.assertTrue(self.server.window_manifest()['test']['render_current'])
        self.assertFalse(self.page.evaluate('!document.hidden'))

    def test_notifications_are_rendered_in_order_while_hidden(self):
        self.start('toast')
        self.publish(2); self.publish(3); revision = self.publish(4)
        self.deliver()
        self.wait_revision(revision)
        self.assertEqual(self.page.evaluate('seen'), [1, 2, 3, 4])
        self.assertFalse(self.server._overlays['test'].ordered)

    def test_a_delayed_bootstrap_response_cannot_revert_a_pushed_model(self):
        revision = self.publish(1)
        old = self.server.delivery('test')
        requests = []
        self.page.route('**/api/snapshot?**', lambda route: requests.append(route))
        self.page.goto(f'http://127.0.0.1:{self.server.port}/delivery-test.html')
        self.page.wait_for_timeout(100)
        self.assertTrue(requests)
        latest = self.publish(2); self.deliver()
        self.wait_revision(latest)
        requests[0].fulfill(content_type='application/json', body=json.dumps(old))
        self.page.wait_for_timeout(200)
        self.assertEqual(self.page.evaluate('seen'), [2])
        self.assertEqual(self.page.locator('#view').inner_text(), '2')
        self.assertGreater(self.server.rendered_revision('test'), revision)

    def test_active_push_suppresses_fast_snapshot_checks_and_stop_unsubscribes(self):
        self.start()
        requests = []
        self.page.on('request', lambda request: requests.append(request.url) if '/api/snapshot?' in request.url else None)
        revision = self.publish(2); self.deliver()
        self.wait_revision(revision)
        self.page.wait_for_timeout(350)
        self.assertEqual(requests, [])
        self.page.evaluate('client.stop()')
        self.publish(3); self.deliver()
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.evaluate('seen'), [1, 2])

    def test_readiness_retries_a_refused_handshake_without_redrawing_the_model(self):
        attempts = []
        def ready(route):
            attempts.append(1)
            if len(attempts) == 1:
                route.fulfill(status=503, content_type='application/json', body='{"error":"retry"}')
            else:
                route.continue_()
        self.page.route('**/api/ready?**', ready)
        self.start()
        self.assertGreaterEqual(len(attempts), 2)
        self.assertEqual(self.page.evaluate('seen'), [1])

    def test_navigation_uses_the_same_push_client_and_remeasures_a_new_layout(self):
        from tests.test_navigation_state_visuals import hud_snapshot, hud_state
        self.server.register('navigation', 'navigation')
        model = hud_snapshot(hud_state('FLIGHT'), window={'visible': False, 'width': 500, 'height': 350})
        self.server.publish('navigation', model)
        self.page.set_viewport_size({'width': 500, 'height': 350})
        host = _OverlayHost(self.server.url, None)
        self.page.goto(host.page_url('navigation', 'navigation'))
        self.page.wait_for_function("document.getElementById('link-state').textContent==='HTML NAV // LIVE'")
        changed = hud_snapshot(hud_state('RHINO'), scale=1.5,
            window={'visible': False, 'width': 750, 'height': 525})
        revision = self.server.publish('navigation', changed)
        self.page.set_viewport_size({'width': 750, 'height': 525})
        self.page.evaluate('packet=>nativeDeliver(packet)', self.server.delivery('navigation'))
        self.page.wait_for_function("document.getElementById('state-label').textContent.includes('RHINO')")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not self.server.window_manifest()['navigation']['render_current']:
            self.page.wait_for_timeout(20)
        self.assertTrue(self.server.window_manifest()['navigation']['render_current'])
        self.assertEqual(self.server.rendered_revision('navigation'), revision)
        self.assertGreaterEqual(self.server.rendered_content_height('navigation'), 350)


@unittest.skipUnless(os.name == 'nt', 'Windows native composition hosting')
class NativeDeliveryTests(unittest.TestCase):
    def test_real_hidden_window_receives_models_with_snapshot_polling_blocked(self):
        import webview.platforms.edgechromium
        from voidcompass.overlays.composition_host import CompositionRuntime
        from voidcompass.overlays.cargo_hud import build_cargo_model
        from tests.test_overlay_text_fit_5539 import THEME
        runtime = CompositionRuntime()
        self.assertTrue(runtime.start(), runtime.error)
        server = HtmlOverlayServer(WEB)
        server.register('cargo', 'cargo')
        host = _OverlayHost(server.url, None, runtime=runtime)
        worker = None
        def publish(count, visible=False):
            return server.publish('cargo', {'cargo': build_cargo_model([{'Name': 'gold', 'Count': count}], capacity=64),
                'theme': THEME, 'effects': {'text_scale': 1},
                'window': {'x': HIDDEN_WINDOW_X, 'y': HIDDEN_WINDOW_Y, 'width': 410, 'height': 190, 'visible': visible}})
        def until(condition):
            deadline = time.monotonic() + 20
            while not condition() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(condition())
        try:
            publish(1)
            worker = threading.Thread(target=host.control_loop, daemon=True)
            worker.start()
            until(lambda: server.is_ready('cargo'))
            window = host.controllers['cargo'].window
            operation = runtime.call(lambda: window.controller.CoreWebView2.ExecuteScriptAsync('''
              const oldFetch=window.fetch;
              window.fetch=(url,...args)=>String(url).includes('/api/snapshot')
                ? new Promise(()=>{}) : oldFetch(url,...args);
              window.requestAnimationFrame=()=>0; true;
            '''))
            until(lambda: operation.IsCompleted)
            revision = publish(7)
            until(lambda: server.rendered_revision('cargo') >= revision)
            self.assertTrue(server.window_manifest()['cargo']['render_current'])
            self.assertFalse(host.controllers['cargo'].last_visible)
            revision = publish(8, visible=True)
            until(lambda: server.rendered_revision('cargo') >= revision and host.controllers['cargo'].last_visible)
        finally:
            host.closing = True
            server.request_host_shutdown()
            if worker is not None:
                worker.join(3)
            host.close()
            runtime.stop()
            server.stop()


if __name__ == '__main__':
    unittest.main()
