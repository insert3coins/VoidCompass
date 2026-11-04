"""Reactive centre geometry and speech-driven lips on the actual display paths."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops
from tests import test_watcher_three_568 as three
from tests import test_crew_ui_574 as crew
from tests.test_heartbeat_orb import snapshot

ARTIFACTS = Path(tempfile.gettempdir()) / "voidcompass-companion-centres"
ARTIFACTS.mkdir(exist_ok=True)


class CentreOverlayTests(unittest.TestCase):
    setUpClass = classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three.WatcherThreeBrowserTests.open_page

    def ready(self, identity, size=192, reduced=False):
        page = self.open_page("heartbeat/index.html", reduced=reduced)
        page.set_viewport_size({"width":size,"height":size})
        live = {"identity":identity,"speech":None,"hearing":None}
        page.route("http://watcher3d.test/api/live*", lambda route: route.fulfill(content_type="application/json",body=json.dumps(live)))
        page.wait_for_function("Boolean(window.CrewCompanion && window.AsterCompanion && window.renderHeartbeat)")
        data = snapshot(crt=False,reduced=reduced)
        data["heartbeat"]["orb"].update(identity=identity,size=size,accent="signature",motion=False,focus_movement="off")
        page.evaluate("data => renderHeartbeat(data)",data)
        adapter = "AsterCompanion" if identity=="aster" else "CrewCompanion"
        inspect = f'{adapter}.inspect(document.getElementById("orb"))'
        page.wait_for_function(f"{inspect}?.frames > 0")
        return page,data,live,inspect

    def capture(self,page,name):
        return Image.open(BytesIO(page.screenshot(path=str(ARTIFACTS/name),omit_background=True))).convert("RGBA")

    def test_both_lattices_fill_the_centre_and_visibly_animate_at_small_sizes(self):
        for identity,design in (("aster","command-prism"),("axiom","lattice-crystal")):
            for size in (54,96):
                page,data,live,inspect = self.ready(identity,size)
                data["heartbeat"]["orb"]["motion"]=True
                page.evaluate("data => renderHeartbeat(data)",data)
                page.wait_for_function(f"{inspect}.frames > 2")
                first=self.capture(page,f"{identity}-{size}-idle.png")
                info=page.evaluate(inspect)
                self.assertEqual(info["reactor"]["design"],design)
                self.assertLessEqual(info["drawCalls"],40 if identity=="aster" else 20)
                radius=round(size*(.11 if identity=="aster" else .16))
                centre=size//2;box=(centre-radius,centre-radius,centre+radius,centre+radius)
                self.assertGreater(sum(max(rgb[:3])>60 and rgb[3]>32 for rgb in first.crop(box).get_flattened_data()),5)
                page.wait_for_timeout(650)
                second=self.capture(page,f"{identity}-{size}-idle-later.png")
                diff=ImageChops.difference(first.convert("RGB").crop(box),second.convert("RGB").crop(box))
                self.assertGreater(sum(max(rgb)>20 for rgb in diff.get_flattened_data()),5)
                page.emulate_media(reduced_motion="reduce")
                # This fixture stubs the poller's rerender callback; deliver
                # the changed preference explicitly, as the real poller does.
                page.evaluate("data => renderHeartbeat(data)",data)
                page.wait_for_function(f"{inspect}.reduced")
                page.wait_for_timeout(120)
                frames=page.evaluate(inspect)["frames"]
                still=self.capture(page,f"{identity}-{size}-reduced.png")
                page.wait_for_timeout(180)
                self.assertEqual(page.evaluate(inspect)["frames"],frames)
                self.assertIsNone(ImageChops.difference(still,self.capture(page,f"{identity}-{size}-reduced-later.png")).getbbox())
                page.close()

    def test_core_activity_follows_live_listening_work_and_speech_levels(self):
        for identity in ("aster","axiom"):
            page,data,live,inspect=self.ready(identity,reduced=True)
            baseline=page.evaluate(inspect)["reactor"]["scale"]
            adapter="AsterCompanion" if identity=="aster" else "CrewCompanion"
            for state,payload in (("listening",{"hearing":{"stage":"listening","level":.4}}),
                                  ("working",{"hearing":{"stage":"working","level":0}}),
                                  ("speaking",{"speech":{"level":.9}})):
                live.update(speech=None,hearing=None);live.update(payload)
                page.evaluate(f'args => {adapter}.update(document.getElementById("orb"),args.model,args.live,{{reducedMotion:true}})',{"model":data["heartbeat"],"live":live})
                page.wait_for_function(f"{inspect}.reactor.state === '{state}'")
                reactor=page.evaluate(inspect)["reactor"]
                if state=="speaking":
                    self.assertGreater(reactor["scale"],baseline+.1)
                    self.assertAlmostEqual(reactor["energy"],.9)
                else:
                    self.assertEqual(reactor["links"],1)
            self.capture(page,f"{identity}-speaking.png")

    def test_meridian_lips_follow_actual_audio_and_close_for_silence_and_queued_text(self):
        page,data,live,inspect=self.ready("meridian")
        self.assertEqual(page.evaluate(inspect)["mouthOpen"],0)
        quiet=self.capture(page,"meridian-quiet.png")
        live["speech"]={"level":.8}
        page.wait_for_function(f"{inspect}.mouthOpen > .6")
        speaking=self.capture(page,"meridian-speaking.png")
        mouth=(81,109,111,127)
        diff=ImageChops.difference(quiet.convert("RGB").crop(mouth),speaking.convert("RGB").crop(mouth))
        self.assertGreater(sum(max(rgb)>25 for rgb in diff.get_flattened_data()),15,"the lips must visibly open, rather than just changing renderer state")
        live["speech"]["level"]=0
        page.wait_for_function(f"{inspect}.mouthOpen < .02")
        self.assertEqual(page.evaluate(inspect)["state"],"speaking","pauses in the same audio line close the mouth")
        live["speech"]=None
        data["heartbeat"]["thought"]={"id":7,"text":"A queued report.","voice":True,"voice_state":"queued"}
        page.evaluate("data => renderHeartbeat(data)",data)
        page.wait_for_function(f"{inspect}.mouthOpen === 0 && {inspect}.state === 'idle'")
        live["hearing"]={"stage":"listening","level":.9}
        page.wait_for_function(f"{inspect}.state === 'listening'")
        self.assertEqual(page.evaluate(inspect)["mouthOpen"],0)
        live["hearing"]=None
        live["speech"]={"level":.8}
        data["heartbeat"]["vitals"]={"danger":True}
        page.evaluate("data => renderHeartbeat(data)",data)
        page.wait_for_function(f"{inspect}.state === 'alert' && {inspect}.mouthOpen > .6")
        page.emulate_media(reduced_motion="reduce")
        page.wait_for_function(f"{inspect}.reduced && {inspect}.mouthOpen === 0")
        page.wait_for_timeout(100)
        frames=page.evaluate(inspect)["frames"]
        page.wait_for_timeout(180)
        self.assertEqual(page.evaluate(inspect)["frames"],frames)


class CentreDeckTests(unittest.TestCase):
    setUpClass = crew.CrewPageTests.__dict__["setUpClass"]
    tearDownClass = crew.CrewPageTests.__dict__["tearDownClass"]
    setUp = crew.CrewPageTests.setUp
    load_module = crew.CrewPageTests.load_module
    render = crew.CrewPageTests.render
    commands = crew.CrewPageTests.commands

    def test_deck_uses_both_core_variants_and_meridian_audio_lips(self):
        self.page.emulate_media(reduced_motion="no-preference")
        live={"identity":"aster","speech":None,"hearing":None}
        self.page.route("http://watcher.test/api/data/companion-live",lambda route:route.fulfill(content_type="application/json",body=json.dumps(live)))
        for identity,design in (("aster","command-prism"),("axiom","lattice-crystal")):
            live["identity"]=identity
            self.data.update(identity=identity,heartbeat={"orb":{"identity":identity,"accent":"signature","motion":False,"focus_movement":"off"}})
            self.render();self.page.click('[data-watcher-tab="now"]')
            adapter="AsterCompanion" if identity=="aster" else "CrewCompanion"
            inspect=f'{adapter}.inspect(document.getElementById("watcher-orb"))'
            self.page.wait_for_function(f"{inspect}?.frames > 0")
            self.assertEqual(self.page.evaluate(inspect)["reactor"]["design"],design)
            self.page.locator(".watcher-eye-panel").screenshot(path=str(ARTIFACTS/f"{identity}-panel.png"))
        live.update(identity="meridian",speech={"level":.85})
        self.data.update(identity="meridian",heartbeat={"orb":{"identity":"meridian","accent":"signature","motion":False,"focus_movement":"off"}})
        self.render()
        inspect='CrewCompanion.inspect(document.getElementById("watcher-orb"))'
        self.page.wait_for_function(f"{inspect}?.mouthOpen > .6")
        self.page.locator(".watcher-eye-panel").screenshot(path=str(ARTIFACTS/"meridian-speaking-panel.png"))
        live["speech"]=None
        self.page.wait_for_function(f"{inspect}.mouthOpen === 0")
