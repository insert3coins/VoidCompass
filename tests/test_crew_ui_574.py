"""Real browser verification of the two preview companions and shared controls."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests import test_watcher_three_568 as three, test_watcher_talk_573 as talk
from tests.test_heartbeat_orb import snapshot
from voidcompass.core import companions
from voidcompass.overlays import companion_personas

ARTIFACTS=Path(tempfile.gettempdir())/"voidcompass-crew-checks"
ARTIFACTS.mkdir(exist_ok=True)


class CrewOverlayTests(unittest.TestCase):
    setUpClass=classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page=three.WatcherThreeBrowserTests.open_page

    def test_both_transparent_displays_animate_and_park_with_controls(self):
        from PIL import Image
        page=self.open_page("heartbeat/index.html")
        page.set_viewport_size({"width":256,"height":256})
        page.wait_for_function('typeof renderHeartbeat === "function" && window.CrewCompanion')
        for identity in companions.NEW_IDENTITIES:
            data=snapshot()
            data["heartbeat"]["orb"].update(identity=identity,size=256,accent="cyan" if identity=="axiom" else "brass",motion=True,focus_movement="expressive")
            page.evaluate("data => renderHeartbeat(data)",data)
            page.wait_for_function('CrewCompanion.inspect(document.getElementById("orb"))?.frames > 3')
            before=page.evaluate('CrewCompanion.inspect(document.getElementById("orb"))')
            page.wait_for_function('n => CrewCompanion.inspect(document.getElementById("orb")).frames > n+3',arg=before["frames"])
            self.assertEqual(before["identity"],identity)
            self.assertLessEqual(before["drawCalls"],20)
            shot=page.screenshot(path=str(ARTIFACTS/f"{identity}-overlay.png"),omit_background=True)
            pixels=Image.open(io.BytesIO(shot)).convert("RGBA")
            self.assertEqual(pixels.getpixel((0,0))[3],0)
            bbox=pixels.getchannel("A").getbbox();self.assertIsNotNone(bbox)
            self.assertGreater(bbox[2]-bbox[0],190)
            page.evaluate('data => CrewCompanion.update(document.getElementById("orb"),data.heartbeat,{speech:{level:.85}})',data)
            self.assertEqual(page.get_attribute(".crew-instrument","data-state"),"speaking")
            data["heartbeat"]["orb"]["motion"]=False
            page.evaluate("data => renderHeartbeat(data)",data)
            page.emulate_media(reduced_motion="reduce")
            page.wait_for_timeout(150)
            frames=page.evaluate('CrewCompanion.inspect(document.getElementById("orb")).frames')
            page.wait_for_timeout(180)
            self.assertEqual(page.evaluate('CrewCompanion.inspect(document.getElementById("orb")).frames'),frames)
            page.emulate_media(reduced_motion="no-preference")
        data["heartbeat"]["orb"]["identity"]="aster"
        page.evaluate("data => renderHeartbeat(data)",data)
        self.assertTrue(page.is_visible(".aster-instrument"))
        self.assertFalse(page.is_visible(".crew-instrument"))
        self.assertEqual(page.evaluate('document.getElementById("orb").style.opacity'),"0")
        data["heartbeat"]["orb"]["identity"]="watcher"
        page.evaluate("data => renderHeartbeat(data)",data)
        self.assertEqual(page.evaluate('document.getElementById("orb").style.opacity'),"")

    def test_reduced_motion_and_speech_clock_follow_shared_caption_presenter(self):
        page=self.open_page("heartbeat/index.html",reduced=True)
        page.wait_for_function('typeof renderHeartbeat === "function" && window.CrewCompanion')
        for identity in companions.NEW_IDENTITIES:
            data=snapshot()
            data["heartbeat"]["orb"].update(identity=identity,size=96,motion=True)
            data["heartbeat"]["thought"]={"id":1,"scope":f"cmdr:{identity}","text":"Welcome aboard, Commander.","voice":True,"voice_full":True,"voice_state":"queued"}
            page.evaluate("data => renderHeartbeat(data)",data)
            page.wait_for_timeout(100)
            self.assertEqual(page.inner_text(".thought-words"),"")
            self.assertTrue(page.evaluate('CrewCompanion.inspect(document.getElementById("orb")).reduced'))


class CrewPageTests(unittest.TestCase):
    setUpClass=classmethod(talk.TalkPageTests.setUpClass.__func__)
    tearDownClass=classmethod(talk.TalkPageTests.tearDownClass.__func__)
    load_module=talk.TalkPageTests.load_module
    render=talk.TalkPageTests.render
    commands=talk.TalkPageTests.commands

    def setUp(self):
        talk.TalkPageTests.setUp(self)
        self.page.route("http://watcher.test/api/data/companion-live",lambda route:route.fulfill(content_type="application/json",body=json.dumps({"speech":None,"hearing":None})))
        self.page.evaluate('async () => { await import("/assets/aster-companion.js"); await import("/assets/crew-companion.js"); }')

    def test_picker_pending_story_voice_and_mobile_layout(self):
        for identity in companions.NEW_IDENTITIES:
            name=companions.NAMES[identity]
            story=companion_personas.get(identity).story
            self.data.update(identity=identity,companion_name=name,nature="officer",lore=story.page({},0),
                settings={**self.data.get("settings",{}),"companion_humour":{"value":"dry","label":companion_personas.get(identity).humour_label,"choices":[list(row) for row in companion_personas.get(identity).humour_choices]}},
                heartbeat={"orb":{"identity":identity,"accent":"cyan" if identity=="axiom" else "brass","motion":False}},
                voice={"identity":identity,"model_name":f"{name} voice","orb_on":True},name={"known":"NightOwl"})
            self.render();self.page.click('[data-watcher-tab="now"]')
            self.assertEqual(self.page.locator("button[data-companion]").count(),4)
            self.assertEqual(self.page.get_attribute(f'button[data-companion="{identity}"]',"aria-pressed"),"true")
            self.assertEqual(self.page.inner_text(".watcher-stage-head > span"),name.upper())
            self.assertTrue(self.page.is_visible(".crew-instrument"))
            self.page.wait_for_function('CrewCompanion.inspect(document.getElementById("watcher-orb"))?.frames > 0')
            self.page.locator(".watcher-eye-panel").screenshot(path=str(ARTIFACTS/f"{identity}-panel.png"))
            self.page.click('[data-watcher-tab="story"]')
            self.assertIn(story.empty_note,self.page.inner_text("#watcher-reader"))
            self.assertEqual(self.page.inner_text(".watcher-lore-panel > header > span"),story.title.upper())
            self.assertIn("Opens with",self.page.get_attribute("#watcher-lore .watcher-chapter.locked >> nth=1","title"))
            self.assertIn("about 15 minutes",self.page.inner_text("#watcher-lore-next"))
            self.page.click('[data-watcher-tab="settings"]')
            self.assertEqual(self.page.inner_text("#watcher-voice-model-name"),f"{name} voice")
            self.assertFalse(self.page.is_visible(".watcher-finding"))
            self.assertIn("Settings",self.page.inner_text("#watcher-voice-orb"))
            self.page.click('[data-watcher-tab="you"]')
            self.assertIn("NightOwl",self.page.inner_text("#watcher-name-note"))
            self.assertIn("wait for it to ask",self.page.inner_text("#watcher-name-note"))
            self.page.set_viewport_size({"width":390,"height":1000})
            self.page.click('[data-watcher-tab="now"]')
            self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"),391)
            self.page.set_viewport_size({"width":1600,"height":1050})
            self.page.click('button[data-companion="watcher"]')
            self.assertIn({"page":"watcher","operation":"companion_identity","value":"watcher"},self.commands())

    def test_real_dashboard_server_serves_both_modules_and_switches_identity(self):
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
        from voidcompass.dashboard.dashboard_journey_mixin import DashboardJourneyMixin
        from tests.test_dashboard_overview_visuals import overview_state
        server=HtmlDashboardServer(talk.ROOT/"web/dashboard",image_root=talk.ROOT/"assets/images",command_callback=lambda payload:True)
        self.addCleanup(server.stop)
        provider=DashboardJourneyMixin()
        live={"speech":None,"hearing":None,"working":False,"identity":"axiom"}
        provider._watcher_live_levels=lambda:live
        server.data_provider=provider._html_data
        state=overview_state();server.publish(state)
        context=self.browser.new_context(viewport={"width":1440,"height":1050},reduced_motion="reduce")
        self.addCleanup(context.close)
        page=context.new_page();errors=[];missing=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.on("response",lambda response:missing.append(response.url) if response.status>=400 else None)
        page.goto(server.url);page.wait_for_selector("body.ready",timeout=15000)
        page.click('.nav-item[data-page="watcher"]')
        for identity in companions.NEW_IDENTITIES:
            name=companions.NAMES[identity];live["identity"]=identity
            self.data.update(identity=identity,companion_name=name,nature="officer",lore={"pending":True,"identity":identity,"title":f"{name} story pending"},
                heartbeat={"orb":{"identity":identity,"motion":False}},voice={"identity":identity,"model_name":f"{name} voice","orb_on":True})
            state["workspace"]={"page":"watcher","ready":True,"data":self.data};server.publish(state)
            page.wait_for_selector(f'.crew-instrument[data-identity="{identity}"]',state="visible")
            page.wait_for_function('CrewCompanion.inspect(document.getElementById("watcher-orb"))?.frames > 0')
            self.assertEqual(page.text_content('.nav-item[data-page="watcher"] span'),name)
            self.assertEqual(page.text_content('[data-page-name="watcher"] .page-title h2'),name)
            live["speech"]={"level":.8}
            page.wait_for_selector('.crew-instrument[data-state="speaking"]',state="visible")
            live["speech"]=None
        self.assertEqual(errors,[])
        self.assertEqual(missing,[])
