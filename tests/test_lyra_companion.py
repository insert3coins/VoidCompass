"""Lyra (5.7.6): the fifth companion, a ship's computer with her own voice,
story and crew, and a robot face that wears the mood of what she says."""
from io import BytesIO
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageChops
from tests import test_watcher_three_568 as three, test_crew_ui_574 as crew
from tests.test_aster_companion import Clock
from tests.test_heartbeat_orb import snapshot
from tests.test_crew_motion_studio_574 import live_studio
from tests.test_companion_stories_574 import _Deck
from voidcompass.core import companions, config, crew_rota
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.overlays import crew_lore, watcher_chat, watcher_deeper
from voidcompass.overlays.crew_mind import CrewMind
from voidcompass.overlays.heartbeat_hud import _memory_path
from voidcompass.voice import voice_assets

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(tempfile.gettempdir())/"voidcompass-lyra"
ARTIFACTS.mkdir(exist_ok=True)


class LyraBackendTests(unittest.TestCase):
    def setUp(self):
        self.config = {**companions.new_defaults(), "companion_identity": "lyra", "lyra_thoughts": "chatty",
                       "heartbeat_thoughts": "chatty"}

    def test_she_is_an_officer_with_her_own_mind_and_answers_by_name(self):
        mind = companions.create_mind(None, self.config, clock=Clock(), rng=random.Random(1))
        self.assertIsInstance(mind, CrewMind)
        self.assertEqual(mind.persona.identity, "lyra")
        mind.session_start()
        self.assertTrue(mind.current()["heading"].startswith("LYRA"))
        self.assertTrue(mind.talk("Hello Lyra"))
        self.assertEqual(watcher_chat.intent("hello lyra"), "greeting")
        self.assertEqual(watcher_chat.intent("lyra what can you do"), "capabilities")
        card = watcher_deeper.read_code(watcher_deeper.share_code(mind.share_card("Jeff")))
        self.assertEqual(card["companion"], "lyra")
        self.assertEqual(watcher_deeper.NATURE_WORDS["lyra"], "a ship's computer called Lyra")

    def test_profile_settings_and_memory_are_independent(self):
        for key, value in companions.new_defaults().items():
            if key.startswith("lyra_"):
                group = (config.PROFILE_BOOL_SETTINGS if type(value) is bool else config.PROFILE_VALUE_SETTINGS
                         if type(value) is int else config.PROFILE_TEXT_SETTINGS)
                self.assertIn(key, group)
        with patch.object(config, "get_profile_file", side_effect=lambda profile, name: name):
            self.assertEqual(_memory_path(self.config), "lyra_memory.json")
        self.assertEqual(companions.settings(self.config)["heartbeat_thoughts"], "chatty")
        self.assertFalse(companions.settings({**self.config, "lyra_voice_enabled": False})["watcher_voice_enabled"])

    def test_her_voice_is_the_one_in_models_lyra(self):
        folder, files, url = voice_assets.manifest("lyra")
        self.assertEqual(folder, "lyra")
        self.assertEqual([row["name"] for row in files], ["glados.onnx", "glados.onnx.json"])
        self.assertTrue(url.endswith("/models/lyra/"))
        self.assertEqual(voice_assets.model_name("lyra"), "Lyra voice")
        self.assertIn("models/lyra", voice_assets.notice("lyra"))
        for row in files:
            local = ROOT/"models"/"lyra"/row["name"]
            if local.exists():
                self.assertEqual(local.stat().st_size, row["size"], row["name"])
        with tempfile.TemporaryDirectory() as base:
            self.assertFalse(voice_assets.installed(base, "lyra"))
        receipts = {voice_assets._receipt("base", identity) for identity in companions.IDENTITIES}
        self.assertEqual(len(receipts), len(companions.IDENTITIES), "each voice has its own receipt")

    def test_api_offers_everything_the_other_officers_have(self):
        deck = _Deck("aster")
        with patch("voidcompass.overlays.heartbeat_hud._memory_path", return_value=None):
            profile = deck.api_companion_profile("lyra")
            axiom = deck.api_companion_profile("axiom")
        self.assertEqual(profile["capabilities"], axiom["capabilities"])
        self.assertEqual(profile["voice"]["model"], "Lyra voice")
        self.assertEqual(profile["story"]["title"], "The Empty Chip")
        self.assertGreater(profile["story"]["total"], 40)

    def test_keepsakes_and_switching(self):
        deck = DashboardKeepsakesMixin(); deck.config = self.config
        self.assertTrue(deck._postcard_companion_note({"title": "Sol"}, 0, "DOCKED"))
        switch = DashboardWatcherVoiceMixin()
        switch.config = {**self.config, "companion_identity": "aster", "aster_hud_size": 192, "aster_hud_focus": "off",
                         "aster_hud_accent": "brass", "aster_hud_liveliness": "calm", "aster_hud_motion": False}
        switch._persist_config = Mock(); switch._schedule_html_dashboard_publish = Mock()
        speaker = switch._watcher_voice = Mock(); listener = switch._watcher_listen = Mock()
        self.assertTrue(switch._companion_switch("lyra"))
        speaker.close.assert_called_once(); listener.close.assert_called_once()
        self.assertEqual(switch.config["lyra_thoughts"], "chatty", "switching to her no longer silences her")
        # The shared Studio settings come along; colour stays each companion's own.
        for identity in companions.IDENTITIES:
            look = companions.display_options({**switch.config, "companion_identity": identity})
            self.assertEqual((look["companion_size"], look["companion_focus"], look["companion_liveliness"], look["companion_motion"]),
                             (192, "off", "calm", False), identity)
        self.assertEqual(companions.display_accent(switch.config), "signature", "Lyra keeps her own colour")

    def test_the_rest_of_the_crew_know_her(self):
        self.assertIn("lyra", crew_lore.CREW)
        for identity in crew_lore.CREW:
            if identity != "lyra":
                # Her passage comes last, so saved progress keeps its places.
                self.assertEqual(crew_lore.PASSAGES[identity][-1][2], "lyra", identity)
        self.assertEqual(crew_rota.wanted({"home_ly": 200}), "lyra", "ordinary flight is her watch")
        self.assertIsNone(crew_rota.duty_of({"home_ly": None}), "no fix on where we are, no flight duty")
        rows = {row["id"]: row for row in json.loads((ROOT/"data"/"achievements.json").read_text(encoding="utf-8"))}
        self.assertEqual({key for key in rows if key.startswith("lyra_")},
                         {"lyra_story_begins", "lyra_story_complete", "lyra_every_echo", "lyra_request"})
        self.assertEqual(rows["crew_full"]["trigger"]["value"], len(companions.IDENTITIES))


class LyraOverlayTests(unittest.TestCase):
    setUpClass = classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three.WatcherThreeBrowserTests.open_page

    def ready(self, size=256, identity="lyra"):
        page = self.open_page("heartbeat/index.html")
        page.set_viewport_size({"width": size, "height": size})
        live = {"identity": identity, "speech": None, "hearing": None}
        page.route("http://watcher3d.test/api/live*", lambda route: route.fulfill(content_type="application/json", body=json.dumps(live)))
        page.wait_for_function("Boolean(window.CrewCompanion && window.renderHeartbeat)")
        data = snapshot(crt=False)
        data["heartbeat"]["orb"].update(identity=identity, size=size, motion=False, focus_movement="off", accent="signature")
        page.evaluate("d=>renderHeartbeat(d)", data)
        inspect = 'CrewCompanion.inspect(document.getElementById("orb"))'
        page.wait_for_function(f"{inspect}?.frames > 0")
        return page, data, live, inspect

    def pixels(self, page, name):
        return Image.open(BytesIO(page.screenshot(path=str(ARTIFACTS/name), omit_background=True))).convert("RGBA")

    def changed(self, before, after, box):
        diff = ImageChops.difference(before.convert("RGB").crop(box), after.convert("RGB").crop(box))
        return sum(max(p) > 25 for p in diff.get_flattened_data())

    def say(self, page, data, mood, thought_id):
        data["heartbeat"]["thought"] = {"id": thought_id, "text": "Tank full.", "mood": mood, "voice": False} if mood else None
        page.evaluate("d=>renderHeartbeat(d)", data)

    def test_jaw_uses_playback_only_and_the_shell_is_visible_and_transparent(self):
        page, data, live, inspect = self.ready()
        quiet = self.pixels(page, "lyra-robot-final.png")
        self.assertEqual(quiet.getpixel((0, 0))[3], 0)
        self.assertGreater(sum(max(p[:3]) > 100 and p[3] > 200 for p in quiet.crop((60, 30, 196, 180)).get_flattened_data()), 4000)
        info = page.evaluate(inspect)
        self.assertEqual(info["modelType"], "articulated-robot")
        self.assertEqual(info["eyeRigs"], 2)
        live["speech"] = {"level": .8}
        page.wait_for_function(f"{inspect}.mouthMorph > .8")
        self.assertGreater(self.changed(quiet, self.pixels(page, "lyra-robot-speaking.png"), (105, 150, 151, 177)), 15)
        live["speech"]["level"] = 0
        page.wait_for_function(f"{inspect}.mouthMorph < .02")
        live["speech"] = None; live["hearing"] = {"stage": "listening", "level": .9}
        page.wait_for_function(f"{inspect}.state === 'listening'")
        self.assertEqual(page.evaluate(inspect)["mouthMorph"], 0)
        live["hearing"] = None
        data["heartbeat"]["thought"] = {"id": 1, "text": "Queued test", "voice": True, "voice_state": "queued"}
        page.evaluate("d=>renderHeartbeat(d)", data)
        page.wait_for_function(f"{inspect}.state === 'idle'")
        self.assertEqual(page.evaluate(inspect)["mouthMorph"], 0)

    def test_her_face_wears_the_mood_of_what_she_says_then_rests(self):
        page, data, live, inspect = self.ready()
        rest = self.pixels(page, "lyra-face-rest.png")
        self.assertEqual(page.evaluate(inspect)["expression"], {"joy": 0, "worry": 0, "sad": 0, "curious": 0})
        self.say(page, data, "pleased", 2)
        page.wait_for_function(f"{inspect}.expression.joy === 1 && {inspect}.smile === 1")
        pleased = self.pixels(page, "lyra-face-pleased.png")
        self.assertGreater(self.changed(rest, pleased, (95, 140, 161, 180)), 15, "the smile widens")
        self.assertGreater(self.changed(rest, pleased, (65, 85, 192, 137)), 100, "the eyes squint")
        self.say(page, data, "wary", 3)
        page.wait_for_function(f"{inspect}.expression.worry === 1 && {inspect}.expression.joy === 0")
        self.assertLess(page.evaluate(inspect)["smile"], 0)
        self.say(page, data, "downcast", 4)
        page.wait_for_function(f"{inspect}.expression.sad === 1")
        self.assertLess(page.evaluate(inspect)["smile"], -1.2, "a frown, not a flat line")
        self.pixels(page, "lyra-face-downcast.png")
        # Danger outranks whatever she was saying.
        data["heartbeat"]["vitals"] = {"low_fuel": True}
        self.say(page, data, "pleased", 5)
        page.wait_for_function(f"{inspect}.state === 'alert' && {inspect}.expression.worry === 1 && {inspect}.expression.joy === 0")
        data["heartbeat"]["vitals"] = {}
        self.say(page, data, "", 6)
        page.wait_for_function(f"Object.values({inspect}.expression).every(v => v === 0)")
        page.wait_for_timeout(120); frames = page.evaluate(inspect)["frames"]
        page.wait_for_timeout(180); self.assertEqual(page.evaluate(inspect)["frames"], frames, "parked once the face is at rest")

    def test_reduced_motion_changes_the_face_at_once(self):
        page, data, live, inspect = self.ready()
        page.emulate_media(reduced_motion="reduce"); page.evaluate("d=>renderHeartbeat(d)", data)
        page.wait_for_function(f"{inspect}.reduced")
        self.say(page, data, "curious", 2)
        page.wait_for_function(f"{inspect}.expression.curious === 1")
        page.wait_for_timeout(100); frames = page.evaluate(inspect)["frames"]
        page.wait_for_timeout(180); self.assertEqual(page.evaluate(inspect)["frames"], frames)

    def test_blink_changes_the_actual_optics_and_reduced_motion_parks(self):
        page, data, live, inspect = self.ready()
        open_eyes = self.pixels(page, "lyra-eyes-open.png")
        data["heartbeat"]["orb"]["motion"] = True
        page.evaluate("d=>renderHeartbeat(d)", data)
        page.evaluate('''async data=>{
          await new Promise(resolve=>{function check(){
            if(CrewCompanion.inspect(document.getElementById('orb')).blink>.9){
              CrewCompanion.update(document.getElementById('orb'),data.heartbeat,{}, {visible:false});resolve();
            }else requestAnimationFrame(check);
          }check();});
        }''', data)
        self.assertGreater(self.changed(open_eyes, self.pixels(page, "lyra-blinking.png"), (65, 85, 192, 137)), 300)
        page.emulate_media(reduced_motion="reduce"); page.evaluate("d=>renderHeartbeat(d)", data)
        page.wait_for_function(f"{inspect}.reduced && {inspect}.blink === 0")
        page.wait_for_timeout(100); frames = page.evaluate(inspect)["frames"]
        page.wait_for_timeout(180); self.assertEqual(page.evaluate(inspect)["frames"], frames)

    def test_studio_updates_parked_robot_and_switches_all_five_at_same_size(self):
        page, data, live, inspect = self.ready()
        studio, hud, bridge = live_studio("lyra")
        studio._handle_html_overlay_studio_command({"operation": "toggle_option", "key": "companion_motion", "value": False})

        def send(**values):
            self.assertTrue(studio._handle_html_overlay_studio_command({"operation": "save_settings", **values}))
            page.evaluate("d=>renderHeartbeat(d)", bridge.surface.publish.call_args.args[0])
            page.wait_for_timeout(120)
        send(companion_accent="cyan", companion_size="96", companion_focus="off")
        cyan = self.pixels(page, "lyra-cyan-96.png")
        send(companion_accent="brass", companion_liveliness="alive", heartbeat_frame_rate="15")
        brass = self.pixels(page, "lyra-brass-96.png")
        self.assertGreater(self.changed(cyan, brass, (0, 0, 96, 96)), 80)
        info = page.evaluate(inspect)
        self.assertEqual((info["width"], info["height"], info["focus"], info["intensity"], info["frameRate"]), (96, 96, "off", 1.6, 15))
        # Parked once her face has settled on the mood of the thought on show.
        page.wait_for_function(f"!{inspect}.expressing"); page.wait_for_timeout(100)
        frames = page.evaluate(inspect)["frames"]; page.wait_for_timeout(180); self.assertEqual(page.evaluate(inspect)["frames"], frames)
        for identity in companions.IDENTITIES:
            data["heartbeat"]["orb"].update(identity=identity, size=96)
            page.evaluate("d=>renderHeartbeat(d)", data); page.wait_for_timeout(100)
            visible = page.locator(".crew-instrument:visible,.aster-instrument:visible").count()
            self.assertEqual(visible, 0 if identity == "watcher" else 1)
            if identity != "watcher":
                box = page.locator(".crew-instrument:visible,.aster-instrument:visible").bounding_box()
                self.assertEqual(round(box["width"]), 96)

    def test_real_server_module_loads_inside_opaque_sandbox(self):
        from voidcompass.dashboard.html_dashboard_server import HtmlDashboardServer
        server = HtmlDashboardServer(ROOT/"web/dashboard"); self.addCleanup(server.stop)
        page = self.browser.new_page(); self.addCleanup(page.close)
        origin = server.origin
        response = page.request.get(origin+"/assets/lyra-robot.js", headers={"Origin": "null"})
        self.assertTrue(response.ok); self.assertEqual(response.headers.get("access-control-allow-origin"), "*")
        page.set_content("<script>window.addEventListener('message',e=>window.result=e.data)</script><iframe sandbox='allow-scripts'></iframe>")
        page.locator("iframe").evaluate('''(frame,url)=>frame.srcdoc=`<canvas style="width:192px;height:192px"></canvas><script type="module">
          try {const {createCrewDisplay}=await import('${url}/assets/crew-3d.js');
          const display=createCrewDisplay(document.querySelector('canvas'),'lyra');
          setTimeout(()=>{parent.postMessage(display.inspect(),'*');display.destroy();},250);
          }catch(error){parent.postMessage({error:String(error)},'*');}</script>`''', origin)
        page.wait_for_function("window.result")
        result = page.evaluate("window.result")
        self.assertNotIn("error", result, result); self.assertTrue(result["modelReady"])
        self.assertGreater(result["frames"], 0)


class LyraDeckTests(unittest.TestCase):
    setUpClass = crew.CrewPageTests.__dict__["setUpClass"]
    tearDownClass = crew.CrewPageTests.__dict__["tearDownClass"]
    setUp = crew.CrewPageTests.setUp
    load_module = crew.CrewPageTests.load_module
    render = crew.CrewPageTests.render
    commands = crew.CrewPageTests.commands

    def test_deck_robot_speaks_in_time_and_fits_a_phone(self):
        self.data.update(identity="lyra", companion_name="Lyra", talk={"orb_on": True, "talk": []},
                         heartbeat={"orb": {"identity": "lyra", "motion": False, "focus_movement": "off"},
                                    "thought": {"id": 7, "text": "Tank full.", "mood": "pleased"}},
                         voice={"identity": "lyra", "available": True, "model_name": "Lyra voice", "orb_on": True})
        self.render()
        inspect = 'CrewCompanion.inspect(document.getElementById("watcher-orb"))'
        self.page.wait_for_function(f"{inspect}?.modelReady")
        self.assertEqual(self.page.inner_text(".watcher-stage-head > span"), "LYRA")
        self.assertFalse(self.page.is_disabled("#watcher-talk-text"))
        self.page.wait_for_function(f"{inspect}.expression.joy === 1", timeout=5000)
        self.page.locator(".watcher-eye-panel").screenshot(path=str(ARTIFACTS/"lyra-robot-deck.png"))
        self.page.emulate_media(reduced_motion="no-preference")
        live = {"identity": "lyra", "speech": {"level": .8}, "hearing": None}
        self.page.route("http://watcher.test/api/data/companion-live", lambda route: route.fulfill(content_type="application/json", body=json.dumps(live)))
        self.page.wait_for_function(f"{inspect}.mouthMorph > .6")
        live["speech"] = None; self.page.wait_for_function(f"{inspect}.mouthMorph === 0")
        self.page.set_viewport_size({"width": 390, "height": 900})
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 391)


if __name__ == "__main__":
    unittest.main()
