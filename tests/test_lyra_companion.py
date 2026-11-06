"""Lyra stays silent while her articulated robot works on the shared surfaces."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageChops
from tests import test_watcher_three_568 as three, test_crew_ui_574 as crew
from tests.test_heartbeat_orb import snapshot
from tests.test_crew_motion_studio_574 import live_studio
from tests.test_companion_stories_574 import _Deck
from voidcompass.core import companions, config
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.dashboard.dashboard_watcher_listen_mixin import DashboardWatcherListenMixin
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.services.local_api import ApiError
from voidcompass.overlays.heartbeat_hud import _memory_path
from voidcompass.overlays.overlay_preview_mind import OverlayPreviewMind
from voidcompass.exploration.flight_log import companion_words
from voidcompass.voice import voice_assets

ARTIFACTS=Path(tempfile.gettempdir())/"voidcompass-lyra-preview"
ARTIFACTS.mkdir(exist_ok=True)


class LyraBackendTests(unittest.TestCase):
    def setUp(self):
        self.config={**companions.new_defaults(),"companion_identity":"lyra","watcher_voice_enabled":True,
                     "watcher_listen_enabled":True,"heartbeat_thoughts":"chatty"}

    def test_events_dialogue_and_queued_callbacks_cannot_borrow_the_watcher(self):
        mind=companions.create_mind(None,self.config)
        self.assertIsInstance(mind,OverlayPreviewMind)
        for event in ("LoadGame","Docked","FSDJump","Shutdown"):
            self.assertIsNone(mind.observe(event,{"Commander":"Jeff","StarSystem":"Sol"}))
        for result in (mind.session_start(),mind.consider("idle_docked",force=True),mind.remember(),
                       mind.note("crew_handover",{"previous":"aster"}),mind.tick(),mind.poke(),
                       mind.find_voice(),mind.say_after("A late callback"),mind.relay("External text")):
            self.assertIsNone(result)
        self.assertFalse(mind.talk("Hello Lyra"))
        self.assertIsNone(mind.current())
        self.assertEqual(mind.memory["log"],[])
        self.assertEqual(mind.story_progress()["total"],0)
        self.assertTrue(mind.name_page()["pending"])
        self.assertEqual(HtmlDashboardMixin()._companion_deeper(mind)["memories"],[])

    def test_profile_settings_and_memory_are_independent(self):
        for key,value in companions.new_defaults().items():
            if key.startswith("lyra_"):
                group=config.PROFILE_BOOL_SETTINGS if type(value) is bool else config.PROFILE_VALUE_SETTINGS if type(value) is int else config.PROFILE_TEXT_SETTINGS
                self.assertIn(key,group)
        with patch.object(config,"get_profile_file",side_effect=lambda profile,name:name):
            self.assertEqual(_memory_path(self.config),"lyra_memory.json")
        self.assertEqual(companions.settings(self.config).get("heartbeat_thoughts"),"off")
        self.assertIsNone(companions.settings(self.config).get("watcher_voice_enabled"))

    def test_no_voice_download_or_recognition_fallback(self):
        deck=DashboardWatcherVoiceMixin();deck.config=self.config
        with patch.object(voice_assets,"installed",side_effect=AssertionError("No installed voice lookup")):
            self.assertFalse(deck._watcher_voice_on())
            self.assertFalse(deck._companion_voice_installed())
            self.assertFalse(deck._crewmate_voice_on("lyra"))
            self.assertFalse(deck._html_watcher_voice({})["available"])
        for operation in ("voice_download","voice_test","talk","name_nickname"):
            self.assertFalse(deck._handle_watcher_settings_command(operation,{}))
        with self.assertRaises(ValueError):deck._watcher_voice_downloader()
        with self.assertRaises(ValueError):voice_assets.manifest("lyra")
        with tempfile.TemporaryDirectory() as base:
            self.assertFalse(voice_assets.installed(base,"lyra"))
            self.assertFalse(voice_assets.remove(base,"lyra"))
            self.assertEqual(list(Path(base).iterdir()),[])
        listener=DashboardWatcherListenMixin();listener.config=self.config
        self.assertIn("preview",listener._watcher_listen_blocked())

    def test_api_lists_and_selects_preview_but_rejects_story_actions(self):
        deck=_Deck("aster")
        with patch("voidcompass.overlays.heartbeat_hud._memory_path",return_value=None):
            profile=deck.api_companion_profile("lyra")
        self.assertFalse(profile["active"])
        self.assertEqual(profile["capabilities"],["overlay"])
        self.assertEqual(profile["voice"],{"model":None,"installed":False})
        self.assertEqual(profile["story"]["total"],0)
        self.assertEqual(deck.config["companion_identity"],"aster")
        deck.api_companion_select("lyra")
        for action in (lambda:deck.api_watcher_thought("Hello"),deck.api_watcher_poke,
                       lambda:deck.api_watcher_answer("yes"),deck.api_watcher_book,
                       deck.api_watcher_code,lambda:deck.api_watcher_meet("example")):
            with self.assertRaises(ApiError) as caught:action()
            self.assertEqual(caught.exception.status,409)

    def test_no_postcard_or_log_writing_is_borrowed(self):
        deck=DashboardKeepsakesMixin();deck.config=self.config
        card={"title":"Sol"}
        self.assertEqual(deck._postcard_companion_note(card,0,"DOCKED"),"")
        self.assertEqual(companion_words({},"lyra"),"")
        self.assertNotIn("signed",card)

    def test_switching_preserves_size_closes_old_voice_and_keeps_preview_quiet(self):
        deck=DashboardWatcherVoiceMixin();deck.config={**self.config,"companion_identity":"aster","aster_hud_size":192}
        deck._persist_config=Mock();deck._schedule_html_dashboard_publish=Mock()
        speaker=deck._watcher_voice=Mock();listener=deck._watcher_listen=Mock()
        self.assertTrue(deck._companion_switch("lyra"))
        speaker.close.assert_called_once();listener.close.assert_called_once()
        self.assertFalse(deck._watcher_voice_on())
        self.assertEqual(deck.config["lyra_thoughts"],"off")
        for identity in companions.IDENTITIES:
            self.assertEqual(companions.display_size({**deck.config,"companion_identity":identity}),192)


class LyraOverlayTests(unittest.TestCase):
    setUpClass=classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page=three.WatcherThreeBrowserTests.open_page

    def ready(self,size=256):
        page=self.open_page("heartbeat/index.html")
        page.set_viewport_size({"width":size,"height":size})
        live={"identity":"lyra","speech":None,"hearing":None}
        page.route("http://watcher3d.test/api/live*",lambda route:route.fulfill(content_type="application/json",body=json.dumps(live)))
        page.wait_for_function("Boolean(window.CrewCompanion && window.renderHeartbeat)")
        data=snapshot(crt=False)
        data["heartbeat"]["orb"].update(identity="lyra",size=size,motion=False,focus_movement="off",accent="signature")
        page.evaluate("d=>renderHeartbeat(d)",data)
        inspect='CrewCompanion.inspect(document.getElementById("orb"))'
        page.wait_for_function(f"{inspect}?.frames > 0")
        return page,data,live,inspect

    def pixels(self,page,name):
        return Image.open(BytesIO(page.screenshot(path=str(ARTIFACTS/name),omit_background=True))).convert("RGBA")

    def test_jaw_uses_playback_only_and_the_shell_is_visible_and_transparent(self):
        page,data,live,inspect=self.ready()
        quiet=self.pixels(page,"lyra-robot-final.png")
        self.assertEqual(quiet.getpixel((0,0))[3],0)
        self.assertGreater(sum(max(p[:3])>100 and p[3]>200 for p in quiet.crop((60,30,196,180)).get_flattened_data()),4000)
        info=page.evaluate(inspect)
        self.assertEqual(info["modelType"],"articulated-robot")
        self.assertEqual(info["eyeRigs"],2)
        live["speech"]={"level":.8}
        page.wait_for_function(f"{inspect}.mouthMorph > .8")
        speaking=self.pixels(page,"lyra-robot-speaking.png")
        diff=ImageChops.difference(quiet.convert("RGB").crop((105,150,151,177)),speaking.convert("RGB").crop((105,150,151,177)))
        self.assertGreater(sum(max(p)>25 for p in diff.get_flattened_data()),15)
        live["speech"]["level"]=0
        page.wait_for_function(f"{inspect}.mouthMorph < .02")
        live["speech"]=None;live["hearing"]={"stage":"listening","level":.9}
        page.wait_for_function(f"{inspect}.state === 'listening'")
        self.assertEqual(page.evaluate(inspect)["mouthMorph"],0)
        live["hearing"]=None
        data["heartbeat"]["thought"]={"id":1,"text":"Queued test","voice":True,"voice_state":"queued"}
        page.evaluate("d=>renderHeartbeat(d)",data)
        page.wait_for_function(f"{inspect}.state === 'idle'")
        self.assertEqual(page.evaluate(inspect)["mouthMorph"],0)

    def test_blink_changes_the_actual_optics_and_reduced_motion_parks(self):
        page,data,live,inspect=self.ready()
        open_eyes=self.pixels(page,"lyra-eyes-open.png")
        data["heartbeat"]["orb"]["motion"]=True
        page.evaluate("d=>renderHeartbeat(d)",data)
        page.evaluate('''async data=>{
          await new Promise(resolve=>{function check(){
            if(CrewCompanion.inspect(document.getElementById('orb')).blink>.9){
              CrewCompanion.update(document.getElementById('orb'),data.heartbeat,{}, {visible:false});resolve();
            }else requestAnimationFrame(check);
          }check();});
        }''',data)
        blink=self.pixels(page,"lyra-blinking.png")
        diff=ImageChops.difference(open_eyes.convert("RGB").crop((65,85,192,137)),blink.convert("RGB").crop((65,85,192,137)))
        self.assertGreater(sum(max(p)>30 for p in diff.get_flattened_data()),300)
        page.emulate_media(reduced_motion="reduce");page.evaluate("d=>renderHeartbeat(d)",data)
        page.wait_for_function(f"{inspect}.reduced && {inspect}.blink === 0")
        page.wait_for_timeout(100);frames=page.evaluate(inspect)["frames"]
        page.wait_for_timeout(180);self.assertEqual(page.evaluate(inspect)["frames"],frames)

    def test_studio_updates_parked_robot_and_switches_all_five_at_same_size(self):
        page,data,live,inspect=self.ready()
        studio,hud,bridge=live_studio("lyra")
        studio._handle_html_overlay_studio_command({"operation":"toggle_option","key":"companion_motion","value":False})
        def send(**values):
            self.assertTrue(studio._handle_html_overlay_studio_command({"operation":"save_settings",**values}))
            page.evaluate("d=>renderHeartbeat(d)",bridge.surface.publish.call_args.args[0])
            page.wait_for_timeout(120)
        send(companion_accent="cyan",companion_size="96",companion_focus="off")
        cyan=self.pixels(page,"lyra-cyan-96.png")
        send(companion_accent="brass",companion_liveliness="alive",heartbeat_frame_rate="15")
        brass=self.pixels(page,"lyra-brass-96.png")
        self.assertGreater(sum(max(p)>20 for p in ImageChops.difference(cyan.convert("RGB"),brass.convert("RGB")).get_flattened_data()),80)
        info=page.evaluate(inspect)
        self.assertEqual((info["width"],info["height"],info["focus"],info["intensity"],info["frameRate"]),(96,96,"off",1.6,15))
        frames=info["frames"];page.wait_for_timeout(180);self.assertEqual(page.evaluate(inspect)["frames"],frames)
        for identity in ("watcher","aster","axiom","meridian","lyra"):
            data["heartbeat"]["orb"].update(identity=identity,size=96)
            page.evaluate("d=>renderHeartbeat(d)",data);page.wait_for_timeout(100)
            visible=page.locator(".crew-instrument:visible,.aster-instrument:visible").count()
            self.assertEqual(visible,0 if identity=="watcher" else 1)
            if identity!="watcher":
                box=page.locator(".crew-instrument:visible,.aster-instrument:visible").bounding_box()
                self.assertEqual(round(box["width"]),96)

    def test_real_server_module_loads_inside_opaque_sandbox(self):
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
        server=HtmlDashboardServer(Path(__file__).resolve().parents[1]/"web/dashboard");self.addCleanup(server.stop)
        page=self.browser.new_page();self.addCleanup(page.close)
        origin=server.origin
        response=page.request.get(origin+"/assets/lyra-robot.js",headers={"Origin":"null"})
        self.assertTrue(response.ok);self.assertEqual(response.headers.get("access-control-allow-origin"),"*")
        page.set_content("<script>window.addEventListener('message',e=>window.result=e.data)</script><iframe sandbox='allow-scripts'></iframe>")
        page.locator("iframe").evaluate('''(frame,url)=>frame.srcdoc=`<canvas style="width:192px;height:192px"></canvas><script type="module">
          try {const {createCrewDisplay}=await import('${url}/assets/crew-3d.js');
          const display=createCrewDisplay(document.querySelector('canvas'),'lyra');
          setTimeout(()=>{parent.postMessage(display.inspect(),'*');display.destroy();},250);
          }catch(error){parent.postMessage({error:String(error)},'*');}</script>`''',origin)
        page.wait_for_function("window.result")
        result=page.evaluate("window.result")
        self.assertNotIn("error",result,result);self.assertTrue(result["modelReady"])
        self.assertGreater(result["frames"],0)


class LyraDeckTests(unittest.TestCase):
    setUpClass=crew.CrewPageTests.__dict__["setUpClass"]
    tearDownClass=crew.CrewPageTests.__dict__["tearDownClass"]
    setUp=crew.CrewPageTests.setUp
    load_module=crew.CrewPageTests.load_module
    render=crew.CrewPageTests.render
    commands=crew.CrewPageTests.commands

    def test_preview_controls_and_deck_robot_are_consistent(self):
        self.data.update(identity="lyra",companion_name="Lyra",overlay_only=True,
            talk={"orb_on":True,"talk":[]},lore={"pending":True,"title":"Story pending"},
            heartbeat={"orb":{"identity":"lyra","motion":False,"focus_movement":"off"}},
            voice={"identity":"lyra","available":False,"orb_on":True})
        self.render()
        inspect='CrewCompanion.inspect(document.getElementById("watcher-orb"))'
        self.page.wait_for_function(f"{inspect}?.modelReady")
        self.assertEqual(self.page.inner_text(".watcher-stage-head > span"),"LYRA")
        self.assertTrue(self.page.is_disabled("#watcher-talk-send"))
        self.assertTrue(self.page.is_disabled("#watcher-talk-text"))
        self.assertIn("pending",self.page.inner_text("#watcher-talk-note"))
        self.assertFalse(self.page.is_visible('[data-watcher-tab="you"]'))
        self.page.locator(".watcher-eye-panel").screenshot(path=str(ARTIFACTS/"lyra-robot-deck.png"))
        self.page.click('[data-watcher-tab="settings"]')
        self.assertIn("pending",self.page.inner_text("#watcher-voice-state"))
        self.assertFalse(self.page.is_visible("#watcher-voice-download"))
        self.page.click('[data-watcher-tab="now"]');self.page.emulate_media(reduced_motion="no-preference")
        live={"identity":"lyra","speech":{"level":.8},"hearing":None}
        self.page.route("http://watcher.test/api/data/companion-live",lambda route:route.fulfill(content_type="application/json",body=json.dumps(live)))
        self.page.wait_for_function(f"{inspect}.mouthMorph > .6")
        live["speech"]=None;self.page.wait_for_function(f"{inspect}.mouthMorph === 0")
        self.page.set_viewport_size({"width":390,"height":900})
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"),391)


if __name__=="__main__":unittest.main()
