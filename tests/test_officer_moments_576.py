"""The officers' displays (5.7.6): Aster, Axiom and Meridian wear the mood of
what they say, and show a moment of their own work: Meridian's heading
needle on a route, Axiom's crystal lit facet by facet as a system is
scanned, Aster's halo with the pad when docking is granted. Each has its own
bezel and instruments (the same size as every other): Aster's watch bells
and watch bill, Axiom's scale, tally and map of the system, Meridian's
compass, sounding gauge and wake."""
from io import BytesIO
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageChops
from tests import test_watcher_three_568 as three
from tests.test_heartbeat_orb import snapshot
from voidcompass.overlays import companion_moments

ARTIFACTS = Path(tempfile.gettempdir()) / "voidcompass-officer-moments"
ARTIFACTS.mkdir(exist_ok=True)


class MomentTests(unittest.TestCase):
    def test_the_heading_is_to_the_next_star_on_the_route(self):
        route = [{"StarSystem": "Here", "StarPos": [0, 0, 0]}, {"StarSystem": "North", "StarPos": [0, 5, 20]},
                 {"StarSystem": "East", "StarPos": [30, 0, 20]}]
        self.assertEqual(companion_moments.bearing([0, 0, 0], route, "Here"), 0.0, "coreward is up the dial")
        self.assertEqual(companion_moments.bearing([0, 0, 20], route, "North"), 90.0)
        self.assertEqual(companion_moments.bearing([0, 0, 0], route, ""), 0.0, "before the first jump: the first leg")
        self.assertIsNone(companion_moments.bearing([30, 0, 20], route, "East"), "the end of the route")
        self.assertIsNone(companion_moments.bearing(None, route, "Here"))
        self.assertEqual(companion_moments.bearing([0, 0, 0], [{"StarSystem": "W", "StarPos": [-10, 0, 0]}], ""), 270.0)

    def test_scan_and_dock_last_only_while_they_apply(self):
        now = [1000.0]
        moments = companion_moments.Moments(clock=lambda: now[0])
        mind = SimpleNamespace(_route_left=None, _survey=SimpleNamespace(bodies={}))
        self.assertEqual(moments.payload(mind), {"jumps": 0})
        moments.observe("FSSDiscoveryScan", {"BodyCount": 8})
        mind._survey.bodies = {"A": 1, "B": 2, "C": 3}
        self.assertEqual(moments.payload(mind)["scan"], {"found": 3, "total": 8, "complete": False})
        moments.observe("FSSAllBodiesFound", {"Count": 8})
        self.assertTrue(moments.payload(mind)["scan"]["complete"])
        moments.observe("FSDJump", {})
        self.assertNotIn("scan", moments.payload(mind), "a new system starts again")
        moments.observe("DockingGranted", {"LandingPad": 7})
        self.assertEqual(moments.payload(mind)["dock"], {"pad": 7})
        moments.observe("Docked", {})
        self.assertNotIn("dock", moments.payload(mind))
        moments.observe("DockingGranted", {"LandingPad": 12})
        now[0] += companion_moments.DOCK_HOLD_S + 1
        self.assertNotIn("dock", moments.payload(mind), "a grant you never used fades")
        mind._route_left, mind._route_total = 4, 9
        self.assertEqual(moments.payload(mind, {"next": 45.0})["route"], {"left": 4, "total": 9, "bearing": 45.0})

    def test_headings_jumps_bodies_and_the_watch(self):
        here, home = [0, 0, 0], [0, 0, -500]
        heading = companion_moments.headings(here, (), "", home)
        self.assertEqual((heading["home"], heading["home_ly"], heading["next"]), (180.0, 500.0, None))
        self.assertLess(abs(heading["core"]), 1, "the core is (nearly) straight up the dial")
        moments = companion_moments.Moments()
        from voidcompass.overlays.survey_report import SurveyTally
        mind = SimpleNamespace(_route_left=None, _survey=SurveyTally())
        mind._survey.observe("Scan", {"BodyName": "A", "StarType": "K", "DistanceFromArrivalLS": 0})
        mind._survey.observe("Scan", {"BodyName": "A 1", "PlanetClass": "Earthlike body", "DistanceFromArrivalLS": 450.5})
        moments.observe("FSDJump", {})
        payload = moments.payload(mind, {**heading, "rota": True, "duty": "flight"})
        self.assertEqual(payload["jumps"], 1)
        self.assertEqual(payload["scan"]["bodies"], [[0.0, "star"], [450.5, "earthlike"]])
        self.assertEqual(payload["heading"], {"home": 180.0, "home_ly": 500.0, "core": heading["core"]})
        self.assertEqual(payload["watch"], {"rota": True, "duty": "flight"})


class OfficerDisplayTests(unittest.TestCase):
    setUpClass = classmethod(three.WatcherThreeBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(three.WatcherThreeBrowserTests.tearDownClass.__func__)
    open_page = three.WatcherThreeBrowserTests.open_page

    def ready(self, identity, focus="tracking"):
        page = self.open_page("heartbeat/index.html")
        page.set_viewport_size({"width": 256, "height": 256})
        live = {"identity": identity, "speech": None, "hearing": None}
        page.route("http://watcher3d.test/api/live*", lambda route: route.fulfill(content_type="application/json", body=json.dumps(live)))
        page.wait_for_function("Boolean(window.CrewCompanion && window.AsterCompanion && window.renderHeartbeat)")
        data = snapshot(crt=False)
        data["heartbeat"]["orb"].update(identity=identity, size=256, motion=False, focus_movement=focus, accent="signature")
        page.evaluate("d=>renderHeartbeat(d)", data)
        adapter = "AsterCompanion" if identity == "aster" else "CrewCompanion"
        inspect = f'{adapter}.inspect(document.getElementById("orb"))'
        page.wait_for_function(f"{inspect}?.frames > 0")
        return page, data, inspect

    def render(self, page, data, **heartbeat):
        data["heartbeat"].update(heartbeat)
        page.evaluate("d=>renderHeartbeat(d)", data)

    def pixels(self, page, name):
        return Image.open(BytesIO(page.screenshot(path=str(ARTIFACTS / name), omit_background=True))).convert("RGB")

    def differ(self, a, b):
        return sum(max(p) > 20 for p in ImageChops.difference(a, b).get_flattened_data())

    def settled(self, page, inspect):
        page.wait_for_function(f"!{inspect}.expressing && !{inspect}.moving")

    def test_every_officer_wears_each_mood_and_rests_after(self):
        for identity in ("aster", "axiom", "meridian"):
            with self.subTest(identity=identity):
                page, data, inspect = self.ready(identity)
                rest = self.pixels(page, f"{identity}-rest.png")
                for n, (mood, channel) in enumerate((("pleased", "joy"), ("wary", "worry"), ("downcast", "sad"), ("curious", "curious")), 2):
                    self.render(page, data, thought={"id": n, "text": "A thought.", "mood": mood, "voice": False})
                    page.wait_for_function(f"{inspect}.expression.{channel} === 1")
                    self.settled(page, inspect)
                    self.assertGreater(self.differ(rest, self.pixels(page, f"{identity}-{mood}.png")), 40, (identity, mood))
                self.render(page, data, thought=None)
                page.wait_for_function(f"Object.values({inspect}.expression).every(v => v === 0)")
                self.settled(page, inspect)
                page.wait_for_timeout(100); frames = page.evaluate(inspect)["frames"]
                page.wait_for_timeout(200)
                self.assertEqual(page.evaluate(inspect)["frames"], frames, f"{identity} parks once its face has settled")
                page.close()

    def test_meridian_smiles_frowns_and_holds_level_with_fixed_focus(self):
        page, data, inspect = self.ready("meridian", focus="off")
        self.render(page, data, thought={"id": 2, "text": "Fair winds.", "mood": "pleased", "voice": False})
        page.wait_for_function(f"{inspect}.smileCurve === 1")
        self.render(page, data, thought={"id": 3, "text": "Ah.", "mood": "downcast", "voice": False})
        page.wait_for_function(f"{inspect}.smileCurve < -1.3")

    def test_meridians_needle_points_to_the_next_star_while_the_drive_charges(self):
        page, data, inspect = self.ready("meridian")
        self.render(page, data, moment={"route": {"left": 6, "total": 9, "bearing": 90.0}})
        page.wait_for_timeout(150)
        self.assertFalse(page.evaluate(inspect)["needle"]["visible"], "only while the drive charges")
        before = self.pixels(page, "meridian-no-needle.png")
        self.render(page, data, vitals={"fsd_charging": True})
        page.wait_for_function(f"{inspect}.needle.show === 1 && Math.abs({inspect}.needle.angle + Math.PI/2) < .01")
        self.assertGreater(self.differ(before, self.pixels(page, "meridian-needle-east.png")), 30)
        self.render(page, data, moment={"route": {"left": 5, "total": 9, "bearing": 270.0}})
        page.wait_for_function(f"Math.abs({inspect}.needle.angle - Math.PI/2) < .01 || Math.abs({inspect}.needle.angle + 3*Math.PI/2) < .01")
        self.render(page, data, vitals={})
        page.wait_for_function(f"!{inspect}.needle.visible")

    def test_axiom_lights_a_facet_for_each_body_scanned(self):
        page, data, inspect = self.ready("axiom")
        none = self.pixels(page, "axiom-scan-none.png")
        self.render(page, data, moment={"scan": {"found": 4, "total": 8, "complete": False}})
        page.wait_for_function(f"{inspect}.reactor.litFacets === 10")
        half = self.pixels(page, "axiom-scan-half.png")
        self.assertGreater(self.differ(none, half), 30)
        self.render(page, data, moment={"scan": {"found": 8, "total": 8, "complete": True}})
        page.wait_for_function(f"{inspect}.reactor.litFacets === 20")
        self.assertGreater(self.differ(half, self.pixels(page, "axiom-scan-all.png")), 30)
        self.render(page, data, moment={})
        page.wait_for_function(f"{inspect}.reactor.litFacets === 0")

    def test_aster_shows_the_pad_and_sweeps_the_halo_once(self):
        page, data, inspect = self.ready("aster")
        before = self.pixels(page, "aster-no-pad.png")
        self.render(page, data, moment={"dock": {"pad": 7}})
        page.wait_for_function(f"{inspect}.pad === 7 && {inspect}.sweep > 0")
        self.pixels(page, "aster-pad-sweep.png")
        page.wait_for_function(f"{inspect}.sweep === -1 && {inspect}.padShow === 1 && !{inspect}.moving")
        self.assertGreater(self.differ(before, self.pixels(page, "aster-pad-07.png")), 60)
        page.wait_for_timeout(100); frames = page.evaluate(inspect)["frames"]
        page.wait_for_timeout(200)
        self.assertEqual(page.evaluate(inspect)["frames"], frames, "parks with the pad on show")
        self.render(page, data, moment={})
        page.wait_for_function(f"{inspect}.pad === null && {inspect}.padShow === 0")

    def test_every_officer_is_the_same_size_with_its_own_bezel(self):
        shots = {}
        for identity in ("aster", "axiom", "meridian", "lyra"):
            page, data, inspect = self.ready(identity)
            page.wait_for_timeout(150)
            shot = Image.open(BytesIO(page.screenshot(omit_background=True))).convert("RGBA")
            shots[identity] = shot
            page.close()
        boxes = {identity: shot.getchannel("A").getbbox() for identity, shot in shots.items()}
        widths = {identity: box[2] - box[0] for identity, box in boxes.items()}
        self.assertLessEqual(max(widths.values()) - min(widths.values()), 2, widths)
        # The bezel band itself differs: scale, compass and command marks.
        band = (118, 0, 138, 12)
        crops = {identity: shots[identity].convert("RGB").crop(band) for identity in ("aster", "axiom", "meridian")}
        self.assertGreater(self.differ(crops["axiom"], crops["meridian"]), 10)
        self.assertGreater(self.differ(crops["aster"], crops["axiom"]), 10)

    def test_meridian_compass_points_home_sounds_the_distance_and_leaves_a_wake(self):
        page, data, inspect = self.ready("meridian")
        self.render(page, data, moment={"jumps": 3, "heading": {"home": 90.0, "home_ly": 1000.0, "core": 0.0}})
        page.wait_for_function(f"{inspect}.needle.show > .44 && Math.abs({inspect}.needle.angle + Math.PI/2) < .01")
        self.assertEqual(page.evaluate(inspect)["needle"]["target"], .45, "at rest, dimmer")
        page.wait_for_function(f"{inspect}.gauge.visible && Math.abs({inspect}.gauge.depth - (-.38 + .6*.76)) < .002")
        self.pixels(page, "meridian-compass-home.png")
        self.render(page, data, moment={"jumps": 4, "heading": {"home": 90.0, "home_ly": 5.0, "core": 0.0}})
        page.wait_for_function(f"{inspect}.wake > 0")
        self.pixels(page, "meridian-wake.png")
        page.wait_for_function(f"Math.abs({inspect}.needle.angle) < .01", timeout=10000)
        page.wait_for_function(f"{inspect}.wake === -1 && !{inspect}.moving")

    def test_axiom_maps_the_system_and_tallies_what_it_counts(self):
        page, data, inspect = self.ready("axiom")
        empty = self.pixels(page, "axiom-map-empty.png")
        bodies = [[0, "star"], [12, "rocky"], [180, "metal"], [450, "earthlike"], [1300, "gas"], [5200, "icy"], [9000, "water"]]
        self.render(page, data, moment={"jumps": 1, "scan": {"found": 7, "total": 9, "complete": False, "bodies": bodies}})
        page.wait_for_function(f"{inspect}.map.bodies === 7 && {inspect}.map.show === 1 && {inspect}.tally.count === 7")
        page.wait_for_function(f"!{inspect}.moving")
        mapped = self.pixels(page, "axiom-map.png")
        self.assertGreater(self.differ(empty, mapped), 30)
        self.render(page, data, moment={"jumps": 2})
        page.wait_for_function(f"{inspect}.map.show === 0 && {inspect}.tally.count === 0")

    def test_aster_rings_the_watch_bells_and_keeps_the_watch_bill(self):
        page, data, inspect = self.ready("aster")
        page.evaluate("() => { window.__testTime = new Date(2026, 10, 7, 1, 29, 50).getTime(); window.__voidcompassNow = () => window.__testTime; }")
        self.render(page, data, moment={"jumps": 0})
        page.evaluate("() => { window.__testTime += 20000; }")
        self.render(page, data, moment={"jumps": 0, "watch": {"rota": False, "duty": None}})
        page.wait_for_function(f"{inspect}.bells === 3", timeout=5000)
        page.wait_for_function(f"{inspect}.bells === 0 && !{inspect}.moving")
        off = self.pixels(page, "aster-bill-off.png")
        self.render(page, data, moment={"jumps": 0, "watch": {"rota": True, "duty": "route"}})
        page.wait_for_function(f"{inspect}.watch.handover >= 0")
        page.wait_for_function(f"{inspect}.watch.show === 1 && {inspect}.watch.handover === -1 && !{inspect}.moving")
        self.assertGreater(self.differ(off, self.pixels(page, "aster-bill-route.png")), 20)

    def test_aster_acknowledges_with_a_double_pulse_but_not_under_reduced_motion(self):
        page, data, inspect = self.ready("aster")
        self.render(page, data, thought={"id": 2, "text": "Noted.", "mood": "pleased", "voice": False})
        page.wait_for_function(f"{inspect}.acknowledging")
        page.wait_for_function(f"!{inspect}.acknowledging")
        page.emulate_media(reduced_motion="reduce"); self.render(page, data, thought=None)
        page.wait_for_function(f"{inspect}.reduced && {inspect}.expression.joy === 0")
        self.render(page, data, thought={"id": 3, "text": "Noted again.", "mood": "pleased", "voice": False})
        page.wait_for_function(f"{inspect}.expression.joy === 1")
        self.assertFalse(page.evaluate(inspect)["acknowledging"])


if __name__ == "__main__":
    unittest.main()
