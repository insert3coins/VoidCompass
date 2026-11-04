"""Both companions use Watcher's timed text in the deck and floating overlay."""
import json
from types import SimpleNamespace
import unittest

from tests import test_aster_ui as aster_ui
from tests import test_watcher_three_568 as three_ui
from tests.test_heartbeat_orb import snapshot
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD


class CaptionMetadataTests(unittest.TestCase):
    def test_whole_speech_is_classified_the_same_way_for_both_identities(self):
        for identity, stage, topic, whole in (
            ('watcher', 0, 'talk', True), ('watcher', 2, 'quiet', False),
            ('watcher', 4, 'quiet', True), ('aster', 4, 'quiet', True)):
            with self.subTest(identity=identity, stage=stage, topic=topic):
                hud = HeartbeatHUD.__new__(HeartbeatHUD)
                hud.config = {'companion_identity': identity}
                hud.mind = SimpleNamespace(voice_active=True, spoken_words=lambda thought: 'Welcome, Jef.', voice_stage=lambda: stage)
                hud.voice_listener = lambda *args, **kwargs: True
                hud._voice_thought({'id': 1, 'text': 'Welcome, Jeff.', 'topic': topic, 'importance': 3})
                self.assertEqual(hud._voiced, (1, whole))

    def test_fast_deck_feed_carries_the_actual_caption_not_just_audio_level(self):
        deck = DashboardWatcherVoiceMixin()
        deck.config = {'companion_identity': 'aster'}
        deck.music_levels = lambda: {}
        deck._watcher_listen_live = lambda: None
        thought = {'id': 7, 'text': 'The first report.', 'voice_state': 'playing', 'scope': 'cmdr:aster'}
        deck.heartbeat_hud = SimpleNamespace(_html_render_model={'thought': thought})
        live = deck._watcher_live_levels()
        self.assertEqual(live['thought'], thought)
        self.assertEqual(live['identity'], 'aster')
        thought['text'] = 'A changed model.'
        self.assertEqual(live['thought']['text'], 'The first report.')


class SharedCaptionBrowserTests(unittest.TestCase):
    setUpClass = classmethod(three_ui.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three_ui.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three_ui.WatcherThreeBrowserTests.open_page

    def ready(self):
        page = self.open_page('heartbeat/index.html', reduced=True)
        page.wait_for_function('Boolean(window.CompanionCaption)')
        return page

    def test_all_four_presentations_have_the_same_speech_clock_and_punctuation(self):
        page = self.ready()
        page.evaluate("""() => {
          window.captionTime=0;window.captures=Array(4).fill('');window.finished=Array(4).fill(false);
          window.line='Ready, Commander. Hold position.';
          window.controllers=Array.from({length:4},(_,i)=>CompanionCaption.createPresenter({
            now:()=>captionTime,paint:parts=>captures[i]=parts.map(p=>p.ch).join(''),onDone:value=>finished[i]=value
          }));
          window.pushCaption=(elapsed,status='playing')=>controllers.forEach((c,i)=>{
            c.show({id:1,scope:i<2?'cmdr:watcher':'cmdr:aster',text:line,voice:true,voice_full:true,voice_state:status},
              {scope:String(i),nature:i<2?'stoic':'officer'});
            c.live(elapsed==null?null:{key:1,elapsed,duration:8});
          });
          pushCaption(null,'queued');
        }""")
        page.wait_for_timeout(340)
        self.assertEqual(page.evaluate('captures'), ['', '', '', ''])
        previous = 0
        for elapsed in (.2, 1, 2.5, 5, 7.5):
            page.evaluate('elapsed=>{captionTime=elapsed*1000;pushCaption(elapsed)}', elapsed)
            page.wait_for_timeout(60)
            values = page.evaluate('captures')
            self.assertEqual(len(set(values)), 1, values)
            self.assertTrue('Ready, Commander. Hold position.'.startswith(values[0]))
            self.assertGreaterEqual(len(values[0]), previous)
            self.assertLess(len(values[0]), len('Ready, Commander. Hold position.'))
            previous = len(values[0])
        pauses = page.evaluate("CompanionCaption.typingPlan(line,'stoic',true).frames.map(f=>f.ms)")
        self.assertGreater(max(pauses), min(pauses) * 8, 'retain Watcher punctuation pauses')
        page.evaluate("captionTime=9000;pushCaption(null,'finished')")
        page.wait_for_function('finished.every(Boolean)')
        self.assertEqual(page.evaluate('captures'), ['Ready, Commander. Hold position.'] * 4)
        page.evaluate('controllers.forEach(c=>c.destroy())')

    def test_late_samples_and_brief_missing_live_feed_do_not_rewind_or_finish_early(self):
        page = self.ready()
        page.evaluate("""() => {
          window.captionTime=1000;window.text='';window.done=false;
          window.caption=CompanionCaption.createPresenter({now:()=>captionTime,paint:p=>text=p.map(x=>x.ch).join(''),onDone:v=>done=v});
          caption.show({id:5,text:'A measured report, followed by another sentence. Still speaking.',voice:true,voice_full:true,voice_state:'playing'});
          caption.live({key:5,elapsed:7,duration:10});
        }""")
        page.wait_for_function('text.length > 0')
        first = page.evaluate('text')
        page.evaluate('captionTime=1800;caption.live({key:5,elapsed:6.5,duration:10})')
        page.wait_for_timeout(70)
        self.assertEqual(page.evaluate('text'), first)
        page.evaluate('captionTime=2000;caption.live(null)')
        page.wait_for_timeout(70)
        self.assertFalse(page.evaluate('done'))
        self.assertEqual(page.evaluate('text'), first)
        page.evaluate('captionTime=6000')
        page.wait_for_function('done')
        self.assertTrue(page.evaluate('text.endsWith("Still speaking.")'))
        page.evaluate('caption.destroy()')

    def test_scope_changes_cancel_old_text_and_hidden_views_park(self):
        page = self.ready()
        page.evaluate("""() => {
          window.captionTime=1000;window.text='';window.paints=0;
          window.caption=CompanionCaption.createPresenter({now:()=>captionTime,paint:p=>{text=p.map(x=>x.ch).join('');paints++}});
          window.makeLine=scope=>({id:1,scope,text:'On watch, Commander. Ready when you are.',voice:true,voice_full:true,voice_state:'queued'});
          caption.show(makeLine('first:watcher'));caption.live({key:1,elapsed:3,duration:8});
        }""")
        page.wait_for_function('text.length > 0')
        page.evaluate("caption.show(makeLine('second:aster'))")
        page.wait_for_timeout(100)
        self.assertEqual(page.evaluate('text'), '')
        page.evaluate('caption.setVisible(false)')
        count = page.evaluate('paints')
        page.wait_for_timeout(120)
        self.assertEqual(page.evaluate('paints'), count)
        page.evaluate('captionTime=6000;caption.setVisible(true);caption.live({key:1,elapsed:6,duration:8})')
        page.wait_for_function('text.length > 0')
        page.evaluate('caption.clear()')
        page.wait_for_timeout(70)
        self.assertEqual(page.evaluate('text'), '')
        self.assertFalse(page.evaluate('caption.busy()'))

    def test_reduced_motion_still_waits_for_the_voice_to_begin(self):
        page = self.ready()
        page.evaluate("""() => {
          window.captionTime=0;window.text='';
          window.caption=CompanionCaption.createPresenter({now:()=>captionTime,paint:p=>text=p.map(x=>x.ch).join('')});
          caption.show({id:9,text:'Ready, Commander.',voice:true,voice_full:true,voice_state:'queued'},{reduced:true});
          captionTime=5000;
        }""")
        page.wait_for_timeout(340)
        self.assertEqual(page.evaluate('text'), '')
        page.evaluate('caption.live({key:9,elapsed:.1,duration:2})')
        page.wait_for_function('text === "Ready, Commander."')
        page.evaluate('caption.destroy()')


class CaptionSurfaceTests(unittest.TestCase):
    setUpClass = classmethod(aster_ui.AsterPageTests.setUpClass.__func__)
    tearDownClass = classmethod(aster_ui.AsterPageTests.tearDownClass.__func__)
    setUp = aster_ui.AsterPageTests.setUp
    load_module = aster_ui.AsterPageTests.load_module
    render = aster_ui.AsterPageTests.render
    open_page = three_ui.WatcherThreeBrowserTests.open_page

    def test_native_overlay_and_deck_wait_and_type_for_both_companions(self):
        deck = self.page
        deck.emulate_media(reduced_motion='no-preference')
        overlay = self.open_page('heartbeat/index.html')
        overlay.wait_for_function('typeof renderHeartbeat === "function"')
        live = {'speech': None}
        for page, origin in ((deck, 'watcher.test'), (overlay, 'watcher3d.test')):
            page.route(f'http://{origin}/api/' + ('data/companion-live**' if page == deck else 'live**'),
                       lambda route: route.fulfill(content_type='application/json', body=json.dumps(live)))
        text = 'Ready, Commander. A measured report, followed by the next instruction.'
        for identity in ('watcher', 'aster'):
            with self.subTest(identity=identity):
                thought = {'id': 101, 'scope': 'cmdr:' + identity, 'text': text, 'voice': True, 'voice_full': True, 'voice_state': 'queued'}
                live.update(identity=identity, generation=0, speech=None, thought=thought)
                self.data.update(identity=identity, companion_name='Aster' if identity == 'aster' else 'The Watcher',
                                 log=[{'at': 1800000000, 'text': text}],
                                 heartbeat={'personality': 'stoic', 'thought': thought, 'orb': {'identity': identity, 'motion': False}})
                self.render()
                data = snapshot(crt=False)
                data['heartbeat'].update(thought=thought, personality='stoic')
                data['heartbeat']['orb'].update(identity=identity, motion=False)
                overlay.evaluate('data=>renderHeartbeat(data)', data)
                deck.wait_for_timeout(3800)
                self.assertEqual(deck.text_content('.companion-caption-text'), '')
                self.assertEqual(overlay.text_content('.thought-words'), '')
                before = deck.locator('#watcher-poke').bounding_box()['y']
                thought['voice_state'] = 'playing'
                live['speech'] = {'key': 101, 'elapsed': 2, 'duration': 8, 'level': .5}
                overlay.evaluate('data=>renderHeartbeat(data)', data)
                for page, selector in ((deck, '.companion-caption-text'), (overlay, '.thought-words')):
                    page.wait_for_function('selector=>document.querySelector(selector).textContent.length > 0', arg=selector)
                lengths = [len(deck.text_content('.companion-caption-text')), len(overlay.text_content('.thought-words'))]
                self.assertLessEqual(abs(lengths[0] - lengths[1]), 3)
                self.assertTrue(all(0 < length < len(text) for length in lengths))
                self.assertAlmostEqual(deck.locator('#watcher-poke').bounding_box()['y'], before, delta=1)
                self.data['log'][0]['text'] = 'A newer queued reply must not replace the spoken line.'
                self.render()
                self.assertTrue(text.startswith(deck.text_content('.companion-caption-text')))
                thought['voice_state'] = 'finished'; live['speech'] = None
                overlay.evaluate('data=>renderHeartbeat(data)', data)
                for page, selector in ((deck, '.companion-caption-text'), (overlay, '.thought-words')):
                    page.wait_for_function('args=>document.querySelector(args[0]).textContent === args[1]', arg=[selector, text])

