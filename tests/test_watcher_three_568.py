"""The Three.js Watcher is shared, reactive, and has a usable fallback."""

import unittest
from pathlib import Path
from urllib.parse import urlsplit

from tests.test_heartbeat_orb import STUB, THEME, event, snapshot


WEB = Path(__file__).resolve().parents[1] / "web"


class WatcherThreeBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def open_page(self, path, *, disable_webgl=False, reduced=False, delayed_module=False, missing_module=False, missing_dependency=False, hidden=False):
        viewport = {"width": 96, "height": 96} if path.startswith("heartbeat/") else {"width": 1000, "height": 700}
        page = self.browser.new_page(viewport=viewport, reduced_motion="reduce" if reduced else "no-preference")
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))
        if hidden:
            page.add_init_script("window.mockHidden = true; Object.defineProperty(document, 'hidden', {configurable: true, get: () => window.mockHidden});")
        if disable_webgl:
            page.add_init_script("""(() => {
              const get = HTMLCanvasElement.prototype.getContext;
              window.blockedWebGL = 0;
              HTMLCanvasElement.prototype.getContext = function(kind, ...args) {
                if (/^webgl/i.test(kind) || kind === 'experimental-webgl') { window.blockedWebGL++; return null; }
                return get.call(this, kind, ...args);
              };
            })();""")

        def serve(route):
            file = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not file.is_file():
                return route.fulfill(status=404, body="")
            if file == WEB / "dashboard" / "app.js":
                return route.fulfill(content_type="application/javascript", body="")
            if file.name == "overlay-client.js":
                return route.fulfill(content_type="application/javascript", body=file.read_text(encoding="utf-8") + STUB)
            if missing_module and file.name == "heartbeat-3d.js":
                return route.fulfill(status=404, body="")
            if missing_dependency and file.name == "three.core.min.js":
                return route.fulfill(status=404, body="")
            if delayed_module and file.name == "heartbeat-3d.js":
                delay = delayed_module if type(delayed_module) is int else 1200
                return route.fulfill(content_type="application/javascript", body=f"await new Promise(resolve => setTimeout(resolve, {delay}));\n" + file.read_text(encoding="utf-8"))
            return route.fulfill(path=str(file))

        page.route("http://watcher3d.test/**", serve)
        page.goto("http://watcher3d.test/" + path, wait_until="commit" if delayed_module else "load")
        return page

    def test_overlay_uses_three_and_keeps_colour_and_journal_reactions(self):
        page = self.open_page("heartbeat/index.html")
        page.wait_for_function("typeof renderHeartbeat === 'function' && window.HeartbeatThree")
        page.evaluate("data => renderHeartbeat(data)", snapshot())
        page.wait_for_function("heartbeatOrb.state().renderer === 'three'")
        first = page.evaluate("heartbeatOrb.state()")
        self.assertEqual(first["base"], THEME["accent"])
        page.evaluate("data => renderHeartbeat(data)", snapshot(eye="hal"))
        self.assertEqual(page.evaluate("heartbeatOrb.state().base"), THEME["red"])
        page.evaluate("data => renderHeartbeat(data)", snapshot([event(1, "UnderAttack", "red", "alarm", 1)]))
        state = page.evaluate("heartbeatOrb.state()")
        self.assertEqual(state["lastEvent"], "UnderAttack")
        self.assertIn("alarm", state["effects"])
        self.assertEqual(state["renderer"], "three")
        pixels = page.evaluate("""() => {
          const c=document.getElementById('orb'), p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
          let visible=0; for(let i=3;i<p.length;i+=4) if(p[i]>0) visible++;
          return {visible,corner:p[3]};
        }""")
        self.assertGreater(pixels["visible"], 100)
        self.assertEqual(pixels["corner"], 0)

    def test_webgl_failure_still_renders_and_reacts(self):
        page = self.open_page("heartbeat/index.html", disable_webgl=True)
        page.wait_for_function("typeof renderHeartbeat === 'function' && window.HeartbeatThree")
        page.evaluate("data => renderHeartbeat(data)", snapshot())
        page.wait_for_function("window.blockedWebGL > 0 && heartbeatOrb.state().renderer === 'canvas'")
        page.evaluate("data => renderHeartbeat(data)", snapshot([event(1, "Scan", "accent", "signal", .8)]))
        state = page.evaluate("heartbeatOrb.state()")
        self.assertEqual(state["lastEvent"], "Scan")
        self.assertIn("signal", state["effects"])
        page.evaluate("heartbeatOrb.advance(performance.now() + 4000); heartbeatOrb.draw(performance.now() + 4000)")
        lit = page.evaluate("""() => {
          const c=document.getElementById('orb');
          return c.getContext('2d').getImageData(c.width/2,c.height/2,1,1).data[3];
        }""")
        self.assertGreater(lit, 0)

    def test_optional_overlay_diagnostic_reports_the_actual_renderer_once(self):
        for disabled, expected in ((False, 'three'), (True, 'canvas')):
            with self.subTest(disabled=disabled):
                page = self.open_page('heartbeat/index.html', disable_webgl=disabled, delayed_module=not disabled)
                reports = []
                page.route('http://watcher3d.test/api/watcher-renderer**',
                           lambda route: (reports.append(route.request.post_data_json),
                                          route.fulfill(status=202, content_type='application/json', body='{"accepted":true}')))
                page.wait_for_function("typeof renderHeartbeat === 'function'")
                data = snapshot()
                data['heartbeat']['orb']['renderer_logging'] = True
                page.evaluate('data => renderHeartbeat(data)', data)
                page.wait_for_function('heartbeatOrb.rendererReported', timeout=10000)
                page.wait_for_timeout(200)
                page.evaluate('data => renderHeartbeat(data)', data)
                page.wait_for_timeout(200)
                self.assertEqual(reports, [{'renderer': expected, **({'reason': 'renderer-error'} if disabled else {})}])

    def test_missing_renderer_module_reports_canvas_instead_of_waiting_forever(self):
        for option in ('missing_module', 'missing_dependency'):
            with self.subTest(option=option):
                page = self.open_page('heartbeat/index.html', **{option: True})
                reports = []
                page.route('http://watcher3d.test/api/watcher-renderer**',
                           lambda route: (reports.append(route.request.post_data_json),
                                          route.fulfill(status=202, content_type='application/json', body='{"accepted":true}')))
                page.wait_for_function("typeof renderHeartbeat === 'function'")
                data = snapshot()
                data['heartbeat']['orb']['renderer_logging'] = True
                page.evaluate('data => renderHeartbeat(data)', data)
                page.wait_for_function('heartbeatOrb.rendererReported', timeout=7000)
                page.wait_for_timeout(200)
                self.assertEqual(reports, [{'renderer': 'canvas', 'reason': 'module-error'}])

    def test_hidden_overlay_waits_for_a_real_late_three_render(self):
        page = self.open_page('heartbeat/index.html', hidden=True, delayed_module=6500)
        reports = []
        page.route('http://watcher3d.test/api/watcher-renderer**',
                   lambda route: (reports.append(route.request.post_data_json),
                                  route.fulfill(status=202, content_type='application/json', body='{"accepted":true}')))
        page.wait_for_function("typeof renderHeartbeat === 'function'")
        data = snapshot()
        data['heartbeat']['orb']['renderer_logging'] = True
        page.evaluate('data => renderHeartbeat(data)', data)
        page.wait_for_timeout(4500)
        self.assertFalse(page.evaluate('heartbeatOrb.rendererReported'))
        self.assertEqual(reports, [], 'a pending module is not a canvas failure')
        page.wait_for_function('Boolean(window.HeartbeatThree)', timeout=8000)
        self.assertEqual(reports, [], 'a hidden eye must wait for its actual draw')
        page.evaluate("window.mockHidden = false; document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_function("heartbeatOrb.rendererReported && heartbeatOrb.state().renderer === 'three'", timeout=8000)
        page.wait_for_timeout(200)
        self.assertEqual(reports, [{'renderer': 'three'}])

    def test_new_journal_reactions_animate_the_live_three_dimensional_eye(self):
        from voidcompass.overlays.heartbeat_events import classify

        page = self.open_page("heartbeat/index.html")
        page.wait_for_function("typeof renderHeartbeat === 'function' && window.HeartbeatThree")
        page.evaluate("data => renderHeartbeat(data)", snapshot())
        page.wait_for_function("heartbeatOrb.state().renderer === 'three'")
        for sequence, (name, expected) in enumerate((("ScanOrganic", "bioscan"), ("Touchdown", "touchdown"), ("LaunchDrone", "limpet")), 1):
            with self.subTest(event=name):
                item = {**classify(name), "seq": sequence}
                self.assertEqual(item["effect"], expected)
                result = page.evaluate("""data => {
                  renderHeartbeat(data);
                  const orb=heartbeatOrb, effect=orb.effects.findLast(e => e.name === data.heartbeat.events[0].effect);
                  if (!effect) return null;
                  const ctx=orb.canvas.getContext('2d'), pixels=() => Array.from(ctx.getImageData(0,0,orb.canvas.width,orb.canvas.height).data);
                  orb.draw(effect.start); const first=pixels();
                  orb.draw(effect.start + effect.ms * .55); const second=pixels();
                  let changed=0; for(let i=0;i<first.length;i+=4) if(Math.abs(first[i]-second[i])>8 || Math.abs(first[i+1]-second[i+1])>8) changed++;
                  return {changed, renderer:orb.state().renderer};
                }""", snapshot([item]))
                self.assertIsNotNone(result)
                self.assertEqual(result['renderer'], 'three')
                self.assertGreater(result['changed'], 30)

    def test_3d_frame_reflects_the_living_eye_and_event_effects(self):
        page = self.open_page("heartbeat/index.html")
        page.wait_for_function("typeof renderHeartbeat === 'function' && window.HeartbeatThree")
        page.evaluate("data => renderHeartbeat(data)", snapshot())
        page.wait_for_function("heartbeatOrb.state().renderer === 'three'")
        result = page.evaluate("""() => {
          const orb=heartbeatOrb, c=document.getElementById('orb'), ctx=c.getContext('2d');
          cancelAnimationFrame(orb.raf); orb.running=true;
          const t=performance.now()+5000;
          orb.effects=[];
          orb.advance(t); orb.draw(t);
          const first=ctx.getImageData(0,0,c.width,c.height).data;
          const before=orb.state().shown.lid;
          orb.life.vitals({scooping:true});
          orb.play({effect:'alarm',tone:'red',weight:1},t);
          for(let i=1;i<=60;i++){ orb.advance(t+i*16.7); orb.draw(t+i*16.7); }
          const after=ctx.getImageData(0,0,c.width,c.height).data;
          let changed=0;
          for(let i=0;i<first.length;i+=4)
            if(Math.abs(first[i]-after[i])>12 || Math.abs(first[i+1]-after[i+1])>12 || Math.abs(first[i+3]-after[i+3])>12) changed++;
          return {changed, before, after:orb.state().shown.lid, renderer:orb.state().renderer};
        }""")
        self.assertEqual(result["renderer"], "three")
        self.assertGreater(result["after"], result["before"] + .05)
        self.assertGreater(result["changed"], 100)

    def test_reduced_motion_gets_three_even_when_module_loads_after_first_frame(self):
        page = self.open_page("heartbeat/index.html", reduced=True, delayed_module=True)
        page.wait_for_function("typeof renderHeartbeat === 'function'")
        page.evaluate("data => renderHeartbeat(data)", snapshot(reduced=True))
        self.assertFalse(page.evaluate("Boolean(window.HeartbeatThree)"), "the first still frame precedes the module")
        page.wait_for_function("window.HeartbeatThree && heartbeatOrb.state().renderer === 'three'")
        state = page.evaluate("heartbeatOrb.state()")
        self.assertFalse(state["running"])
        self.assertEqual(state["shown"]["lid"], state["pose"]["lid"])

    def test_boot_and_watcher_page_use_the_same_renderer(self):
        page = self.open_page("dashboard/index.html")
        page.wait_for_function("window.bootScene && window.HeartbeatThree && bootScene.state().orb?.renderer === 'three'")
        self.assertEqual(page.evaluate("() => new Promise(resolve => bootScene.watchRenderer(resolve))"), 'three')
        page.evaluate("""async () => {
          document.getElementById('boot').hidden=true;
          document.body.classList.add('ready');
          document.querySelector('[data-page-name="watcher"]').classList.add('active');
          window.watcherReports = [];
          const ui = {byId: id => document.getElementById(id),
            escapeHtml: value => String(value ?? ''), numeric: value => String(value ?? 0),
            command: async (...args) => { watcherReports.push(args); return true; }, showToast() {}};
          const module = await import('/dashboard/watcher.js');
          window.testRenderWatcher = data => module.renderWatcher(data, ui);
          testRenderWatcher({eye:'theme', enabled:true, nature:'curious', renderer_logging:true});
        }""")
        page.wait_for_function("window.watcherPageOrb && watcherPageOrb.state().renderer === 'three'")
        page.wait_for_function("watcherReports.length === 1")
        self.assertEqual(page.evaluate("watcherReports[0]"), ['watcher_renderer', {'surface': 'dashboard', 'renderer': 'three'}])
        before = page.evaluate("watcherPageOrb.state().base")
        page.evaluate("testRenderWatcher({eye:'hal', enabled:true, nature:'curious', renderer_logging:true})")
        self.assertEqual(page.evaluate("watcherReports.length"), 1)
        red = page.evaluate("watcherPageOrb.state().base")
        self.assertNotEqual(before, red)
        self.assertGreater(int(red[1:3], 16), int(red[3:5], 16) * 1.5)
        page.wait_for_function("!bootScene.state().orb.running")
        data = {'eye':'hal', 'enabled':True, 'nature':'curious', 'heartbeat':{
            'state':'SUPERCRUISE', 'status':'TELEMETRY LIVE', 'status_seq':1, 'events':[],
            'orb':{'story':{'crack':True}}, 'vitals':{}}}
        page.evaluate('data=>testRenderWatcher(data)', data)
        data['heartbeat']['events'] = [event(1, 'UnderAttack', 'red', 'alarm', 1)]
        page.evaluate('data=>testRenderWatcher(data)', data)
        self.assertEqual(page.evaluate('watcherPageOrb.state().lastEvent'), 'UnderAttack')
        self.assertIn('alarm', page.evaluate('watcherPageOrb.state().effects'))
        self.assertTrue(page.evaluate('watcherPageOrb.story.crack'))
        self.assertEqual(page.locator('#watcher-flight-state').inner_text(), 'SUPERCRUISE')
        self.assertEqual(page.locator('#watcher-feed').inner_text(), 'JOURNAL LIVE')
        self.assertEqual(page.locator('#watcher-last-event').inner_text(), 'UNDER ATTACK')
        page.evaluate('data=>testRenderWatcher(data)', data)
        self.assertEqual(page.evaluate('watcherPageOrb.state().lastSeq'), 1)


if __name__ == "__main__":
    unittest.main()
