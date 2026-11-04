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

    def test_download_progress_uses_the_active_voice_name(self):
        self.data["voice"] = {"identity": "aster", "model_name": "Aster officer voice", "enabled": True, "installed": False,
                              "download": {"stage": "model", "done": 1, "total": 2}}
        self.render()
        self.page.click('[data-watcher-tab="voice"]')
        self.assertIn("Aster officer voice", self.page.inner_text('#watcher-voice-progress'))
        self.assertNotIn("HAL", self.page.inner_text('#watcher-voice-progress'))

    def test_name_question_is_visible_and_uses_shared_answer_buttons(self):
        self.data["deeper"] = {"question": {"id": "your_name", "text": "May I call you Jeff?",
            "answers": [{"key": "yes", "label": "Use my name"}, {"key": "commander", "label": "Keep it Commander"},
                        {"key": "other", "label": "Call me something else"}]}, "hotkeys": ["Alt+1", "Alt+2", "Alt+3"]}
        self.render()
        self.assertTrue(self.page.is_visible('#watcher-question'))
        self.assertIn("ASTER ASKS", self.page.inner_text('#watcher-question'))
        self.assertIn("Alt+1", self.page.inner_text('#watcher-question'))
        self.page.set_viewport_size({"width": 390, "height": 1000})
        self.page.locator('#watcher-question').scroll_into_view_if_needed()
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)
        self.page.locator('#watcher-question').screenshot(path=str(ARTIFACTS / 'aster-name-question-390.png'))
        self.page.click('[data-watcher-answer="yes"]')
        self.assertIn({"page": "watcher", "operation": "answer", "answer": "yes"}, self.commands())
        self.data["deeper"]["question"] = None
        self.render()
        self.assertFalse(self.page.is_visible('#watcher-question'))

    def test_heard_name_story_can_be_read_without_showing_unheard_passages(self):
        self.data["name"] = {"known": "insert3coins", "call": "nickname", "nickname": "Jeff", "spoken": "Jef",
            "told": ["notice"], "steps": 3, "story": {"title": "THE CREW REGISTER", "complete": False,
                "told": [{"id": "notice", "text": "The register gives your name as insert3coins.", "at": 1800000000}]}}
        self.render()
        self.page.click('[data-watcher-tab="you"]')
        self.assertIn("Jeff", self.page.inner_text('#watcher-name-note'))
        self.assertIn("regular form of address", self.page.inner_text('#watcher-name-note'))
        self.assertIn("replies and reports", self.page.inner_text('#watcher-name-policy'))
        self.assertNotIn("once a session", self.page.inner_text('#watcher-name-policy'))
        self.page.click('#watcher-name-story summary')
        self.assertIn("THE CREW REGISTER", self.page.inner_text('#watcher-name-story'))
        self.assertEqual(self.page.locator('#watcher-name-passages li').count(), 1)
        self.assertEqual(self.page.input_value('#watcher-name-spoken'), "Jef")
        self.page.locator('.watcher-name').screenshot(path=str(ARTIFACTS / 'aster-name-reader.png'))
        self.data["identity"] = "watcher"
        self.data["name"]["call"] = "name"
        self.render()
        self.assertIn("once a session", self.page.inner_text('#watcher-name-policy'))
        self.assertIn("once a session", self.page.inner_text('#watcher-name-note'))

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
        self.assertEqual(page.text_content('.nav-item[data-page="watcher"] span'), "Aster")
        self.assertEqual(page.text_content('[data-page-name="watcher"] .page-title h2'), "Aster")
        self.assertTrue(page.is_visible('.aster-officer-mark'))
        self.assertEqual(page.text_content('#watcher-poke'), 'CALL ASTER')
        live["speech"] = {"level": .8}
        page.locator('.aster-instrument[data-state="speaking"]').wait_for(state="visible")
        page.wait_for_function('document.getElementById("aster-signal").textContent === "REPLYING"')
        page.click('[data-watcher-tab="voice"]')
        self.assertEqual(page.inner_text('#watcher-voice-model-name'), "Aster officer voice")
        page.click('[data-watcher-tab="now"]')
        page.set_viewport_size({'width': 390, 'height': 844})
        page.locator('#watcher-poke').scroll_into_view_if_needed()
        box = page.locator('#watcher-poke').bounding_box()
        self.assertGreaterEqual(box['y'], 0)
        self.assertLessEqual(box['y'] + box['height'], 844)
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 391)
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
        for size in (54, 72, 96, 144, 192, 256):
            page.set_viewport_size({'width': size, 'height': size})
            data['heartbeat']['orb']['size'] = size
            page.evaluate('data => renderHeartbeat(data)', data)
            page.wait_for_timeout(100)
            self.assertEqual(page.locator('.aster-instrument').bounding_box()['width'], size)
        shot = page.screenshot(path=str(ARTIFACTS / 'overlay-256.png'), omit_background=True)
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

    def test_halo_has_a_translucent_command_core_instead_of_two_lights(self):
        from PIL import Image
        from io import BytesIO
        page = self.open_page('heartbeat/index.html', reduced=True)
        page.set_viewport_size({'width': 192, 'height': 192})
        page.wait_for_function('typeof renderHeartbeat === "function" && window.AsterCompanion')
        data = snapshot(reduced=True)
        data['heartbeat']['orb'].update(identity='aster', size=192, motion=False, focus_movement='off')
        page.evaluate('data => renderHeartbeat(data)', data)
        page.wait_for_function('AsterCompanion.inspect(document.getElementById("orb"))?.frames > 0')
        canvas = page.locator('.aster-instrument')
        pixels = Image.open(BytesIO(canvas.screenshot(omit_background=True, path=str(ARTIFACTS / 'command-core-transparent-192.png')))).convert('RGBA')
        alpha = pixels.getchannel('A')
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertLess(alpha.getpixel((96, 96)), 96, 'the lattice facets let the game show through')
        self.assertEqual(page.evaluate('AsterCompanion.inspect(document.getElementById("orb")).reactor.design'), 'command-prism')
        import math
        gap = [(round(96+math.cos(i/48*math.tau)*.27/2.32*192),
                round(96+math.sin(i/48*math.tau)*.27/2.32*192)) for i in range(48)]
        self.assertGreater(sum(alpha.getpixel(point)<16 for point in gap),24,
                           'most of the gap between prism and interface stays transparent')
        lit = sum(alpha.getpixel((x,y)) > 64 for x in range(48,144) for y in range(48,144))
        self.assertGreater(lit, 150, 'the centre contains luminous interface tracks')

    def test_command_core_animates_and_reacts_to_speech_level(self):
        from PIL import Image, ImageChops
        from io import BytesIO
        page = self.open_page('heartbeat/index.html')
        live = {"speech": None, "hearing": None}
        page.route('http://watcher3d.test/api/live*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(live)))
        page.set_viewport_size({'width':192,'height':192})
        page.wait_for_function('typeof renderHeartbeat === "function" && window.AsterCompanion')
        data = snapshot(crt=False)
        data['heartbeat']['orb'].update(identity='aster',size=192,motion=True,focus_movement='off')
        page.evaluate('data=>renderHeartbeat(data)',data)
        canvas=page.locator('.aster-instrument')
        def core():
            return Image.open(BytesIO(canvas.screenshot())).convert('RGB').crop((64,64,128,128))
        first=core()
        page.wait_for_timeout(350)
        self.assertIsNotNone(ImageChops.difference(first,core()).getbbox(), 'the inner interface animates independently of the outer halo')
        page.emulate_media(reduced_motion='reduce')
        page.evaluate('data=>renderHeartbeat(data)',data)
        page.wait_for_timeout(80)
        quiet=core()
        live["speech"] = {"level": .8}
        page.wait_for_function('AsterCompanion.inspect(document.getElementById("orb"))?.state === "speaking"')
        page.wait_for_timeout(80)
        self.assertIsNotNone(ImageChops.difference(quiet,core()).getbbox(), 'the command core reads the actual speech level')

    def test_visible_diameter_and_selected_size_match_even_in_a_tall_caption_window(self):
        from PIL import Image
        from io import BytesIO
        page = self.open_page('heartbeat/index.html', reduced=True)
        page.wait_for_function('typeof renderHeartbeat === "function" && window.AsterCompanion')
        data = snapshot(reduced=True)
        for size in (54, 72, 96, 144, 192, 256):
            page.set_viewport_size({'width': size + 330, 'height': max(size, 220)})
            data['heartbeat']['orb'].update(size=size, motion=False)
            widths = []
            for identity in ('watcher', 'aster'):
                data['heartbeat']['orb']['identity'] = identity
                for thought in (None, {'id': size, 'text': 'A report beside the display.', 'side': 'right', 'orb_top': 0}):
                    data['heartbeat']['thought'] = thought
                    page.evaluate('data => renderHeartbeat(data)', data)
                    page.wait_for_timeout(80)
                    self.assertEqual(page.locator('#orb').bounding_box()['width'], size)
                canvas = page.locator('.aster-instrument' if identity == 'aster' else '#orb')
                self.assertEqual(canvas.bounding_box()['width'], size)
                pixels = Image.open(BytesIO(canvas.screenshot(omit_background=True))).convert('RGBA')
                box = pixels.getchannel('A').point(lambda alpha: 255 if alpha > 24 else 0).getbbox()
                self.assertIsNotNone(box)
                widths.append(box[2] - box[0])
            self.assertLessEqual(abs(widths[0] - widths[1]), max(3, size * .04), (size, widths))

    def test_spoken_caption_waits_for_its_queued_audio_then_tracks_real_progress(self):
        page = self.open_page('heartbeat/index.html')
        live = {'speech': None}
        page.route('http://watcher3d.test/api/live**', lambda route: route.fulfill(content_type='application/json', body=json.dumps(live)))
        page.wait_for_function('typeof renderHeartbeat === "function" && window.AsterCompanion')
        text = 'A report which must wait for the voice rather than run ahead of its playback.'
        data = snapshot()
        data['heartbeat']['orb'].update(identity='aster', size=96, motion=False)
        data['heartbeat']['thought'] = {'id': 901, 'text': text, 'voice': True, 'voice_full': True, 'voice_state': 'queued'}
        page.evaluate('data => renderHeartbeat(data)', data)
        page.wait_for_timeout(3900)
        self.assertEqual(page.inner_text('.thought-words'), '', 'model loading must not hit the old 3.5-second fallback')
        data['heartbeat']['thought']['voice_state'] = 'playing'
        live['speech'] = {'key': 901, 'duration': 8, 'elapsed': 2, 'level': .5}
        page.evaluate('data => renderHeartbeat(data)', data)
        page.wait_for_function('document.querySelector(".thought-words").textContent.length > 0')
        shown = page.text_content('.thought-words')
        self.assertTrue(text.startswith(shown))
        self.assertTrue(len(text) * .1 < len(shown) < len(text) * .5)
        live['speech']['elapsed'] = 6
        page.wait_for_function('document.querySelector(".thought-words").textContent.length > 40')
        self.assertFalse(page.locator('#thought').evaluate('node => node.classList.contains("done")'))
        live['speech'] = None
        data['heartbeat']['thought']['voice_state'] = 'finished'
        page.evaluate('data => renderHeartbeat(data)', data)
        page.wait_for_function('document.querySelector("#thought").classList.contains("done")')
        self.assertEqual(page.inner_text('.thought-words'), text)


    def test_idle_instrument_moves_and_reduced_motion_stops_it(self):
        from PIL import Image, ImageChops
        from io import BytesIO
        page = self.open_page('heartbeat/index.html')
        page.emulate_media(reduced_motion="no-preference")
        page.set_viewport_size({"width": 192, "height": 192})
        page.wait_for_function('typeof renderHeartbeat === "function" && window.AsterCompanion')
        data = snapshot(crt=False)
        data['heartbeat']['orb'].update(identity="aster", size=192, motion=True, liveliness="alive")
        page.evaluate('data => renderHeartbeat(data)', data)
        canvas = page.locator('.aster-instrument')
        for intensity in ("calm", "standard", "alive"):
            data['heartbeat']['orb']['liveliness'] = intensity
            page.evaluate('data => renderHeartbeat(data)', data)
            page.wait_for_timeout(120)
            first = Image.open(BytesIO(canvas.screenshot())).convert("RGB")
            page.wait_for_timeout(350)
            second = Image.open(BytesIO(canvas.screenshot())).convert("RGB")
            self.assertIsNotNone(ImageChops.difference(first, second).getbbox(), f"idle halo must move at {intensity} intensity")
        page.emulate_media(reduced_motion="reduce")
        page.evaluate('data => renderHeartbeat(data)', data)
        page.wait_for_timeout(120)
        first = Image.open(BytesIO(canvas.screenshot())).convert("RGB")
        page.wait_for_timeout(350)
        second = Image.open(BytesIO(canvas.screenshot())).convert("RGB")
        self.assertIsNone(ImageChops.difference(first, second).getbbox(), "reduced motion must retain a still instrument")

    def test_gaze_follows_new_events_and_focus_modes_without_replaying_history(self):
        page = self.open_page('heartbeat/index.html')
        result = page.evaluate("""async () => {
          const {createAsterMotion} = await import('/assets/aster-3d.js');
          const baseline = {state:'DOCKED',events:[{seq:40,weight:1,rare:true,gaze:'left'}]};
          const motion = createAsterMotion(); motion.context(baseline);
          const before = motion.step(.1,{idle:false});
          motion.context({...baseline,events:[...baseline.events,{seq:41,weight:1,rare:true,overlay:'cargo_hud'}],overlays:{cargo_hud:[.8,.6]}});
          let followed; for(let i=0;i<10;i++) followed=motion.step(.1,{idle:false});
          motion.context({...baseline,events:[{seq:41,weight:1,rare:true,gaze:'left'}]});
          const duplicate=motion.step(.1,{idle:false});
          const fixed=motion.step(.1,{focus:'off'});
          const still=motion.step(.1,{reduced:true,state:'listening'});
          const run = focus => {const life=createAsterMotion();let pose;for(let i=0;i<10;i++)pose=life.step(.1,{focus});return pose;};
          const scan=createAsterMotion();scan.context({state:'FSS SCANNING'});
          const scanning=scan.step(.1,{});
          motion.context({events:[{seq:1,weight:1,rare:true,gaze:'right'}]});
          const reset=motion.step(.1,{idle:false});
          return {before,followed,duplicate,fixed,still,tracking:run('tracking'),expressive:run('expressive'),scanning,reset};
        }""")
        self.assertEqual(result['before']['attention'], 0)
        self.assertGreater(result['followed']['x'], .5)
        self.assertLess(result['followed']['y'], -.4, "screen Y must be inverted for the 3D eye")
        self.assertGreater(result['followed']['pulse'], 0)
        self.assertLess(result['duplicate']['attention'], result['followed']['attention'])
        self.assertEqual((result['fixed']['x'], result['fixed']['y']), (0, 0))
        self.assertFalse(result['still']['active'])
        self.assertEqual(result['still']['aperture'], .88)
        self.assertAlmostEqual(result['expressive']['x'], result['tracking']['x'] * 1.45)
        self.assertEqual(result['scanning']['activity'], 'scanning')
        self.assertEqual(result['reset']['attention'], 0)

    def test_idle_off_still_reacts_and_hidden_renderer_parks(self):
        page = self.open_page('heartbeat/index.html', hidden=True)
        page.set_viewport_size({'width': 192, 'height': 192})
        page.evaluate("""async () => {
          const {createAsterDisplay}=await import('/assets/aster-3d.js');
          const canvas=document.createElement('canvas');canvas.style='width:192px;height:192px';document.body.append(canvas);
          window.instrument=createAsterDisplay(canvas);instrument.setMotion(false);
        }""")
        page.wait_for_timeout(120)
        self.assertEqual(page.evaluate('instrument.inspect().frames'), 0)
        page.evaluate("window.mockHidden=false;document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_function('instrument.inspect().frames > 0')
        page.wait_for_timeout(100)
        count = page.evaluate('instrument.inspect().frames')
        page.wait_for_timeout(150)
        self.assertEqual(page.evaluate('instrument.inspect().frames'), count)
        page.evaluate("instrument.setState('listening',.5)")
        page.wait_for_function('instrument.inspect().frames > ' + str(count + 2))
        listening = page.evaluate('instrument.inspect()')
        self.assertGreater(listening['aperture'], .61)
        self.assertLessEqual(listening['drawCalls'], 40)
        page.evaluate('instrument.setVisible(false)')
        count = page.evaluate('instrument.inspect().frames')
        page.wait_for_timeout(150)
        self.assertEqual(page.evaluate('instrument.inspect().frames'), count)
        page.evaluate('instrument.setVisible(true);instrument.setReducedMotion(true)')
        page.wait_for_function('instrument.inspect().frames > ' + str(count))
        count = page.evaluate('instrument.inspect().frames')
        page.wait_for_timeout(150)
        self.assertEqual(page.evaluate('instrument.inspect().frames'), count)
        page.evaluate('instrument.destroy()')

    def test_shared_watcher_focus_modes_and_eye_colours(self):
        page = self.open_page('heartbeat/index.html', reduced=True)
        page.wait_for_function('typeof renderHeartbeat === "function"')
        data = snapshot(reduced=True)
        page.evaluate('data => renderHeartbeat(data)', data)
        result = page.evaluate("""() => {
          const result={};heartbeatOrb.shown=null;
          heartbeatOrb.gaze.x=.1;heartbeatOrb.gaze.y=-.05;
          for(const focus of ['tracking','expressive','off']) {
            heartbeatOrb.focusMovement=focus;heartbeatOrb.draw(performance.now());
            result[focus]=heartbeatOrb.state().focusGaze;
          }
          return result;
        }""")
        self.assertEqual(result['off'], {'x': 0, 'y': 0})
        self.assertAlmostEqual(result['expressive']['x'], result['tracking']['x'] * 1.45)
        self.assertNotEqual(result['tracking']['x'], 0)
        for accent, expected in (('cyan', '#65e4ef'), ('brass', '#e8c48c')):
            data['heartbeat']['orb']['eye'] = accent
            data['heartbeat']['thought'] = {'id': 10, 'text': 'On watch.', 'style': {'colour': 'eye'}}
            page.evaluate('data => renderHeartbeat(data)', data)
            self.assertEqual(page.evaluate('heartbeatOrb.state().base'), expected)
            self.assertEqual(page.get_attribute('body', 'data-thought-colour'), accent)
