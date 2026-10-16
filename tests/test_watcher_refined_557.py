"""5.5.7 The Watcher, refined: the orb glides between poses (springs), hands
one effect to the next with a fade, and has a Frame rate of its own in
Overlay Studio for older PCs, which its overlay window and the deck's Watcher
page both keep to."""

import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from voidcompass.core import config as config_module
from voidcompass.dashboard.dashboard import MainDashboard
from voidcompass.overlays.heartbeat_hud import FRAME_RATES, frame_rate, frame_rate_setting
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer
from tests.test_heartbeat_orb import STUB, THEME, _Studio

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class WatcherFrameRateSettingTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(HtmlOverlayServer.set_overlay_frame_rates, {})
        saved = HtmlOverlayServer.frame_rate
        self.addCleanup(setattr, HtmlOverlayServer, "frame_rate", saved)

    def test_it_follows_the_commander_and_defaults_to_all_overlays(self):
        self.assertIn("heartbeat_frame_rate", config_module.PROFILE_VALUE_SETTINGS)
        self.assertEqual(frame_rate_setting({}), 0)
        for junk in ("45", "fast", None, -1):
            self.assertEqual(frame_rate_setting({"heartbeat_frame_rate": junk}), 0, junk)
        HtmlOverlayServer.frame_rate = 15
        self.assertEqual(frame_rate({}), 15, "same as all overlays")
        self.assertEqual(frame_rate({"heartbeat_frame_rate": "24"}), 24)

    def test_studio_offers_exactly_the_supported_rates(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="heartbeat_hud">(.*?)</section>', html, re.S).group(1)
        choice = re.search(r'data-studio-setting="heartbeat_frame_rate">(.*?)</select>', section, re.S)
        self.assertIsNotNone(choice, "the Watcher's own section has it")
        self.assertEqual(tuple(int(value) for value in re.findall(r'value="(\d+)"', choice.group(1))), FRAME_RATES)
        self.assertEqual(html.count('data-studio-setting="heartbeat_frame_rate"'), 1)

    def test_studio_saves_it_and_the_overlay_server_follows(self):
        studio = _Studio()
        self.assertTrue(studio._html_overlay_settings_save({"heartbeat_frame_rate": "15"}))
        self.assertEqual(studio.config["heartbeat_frame_rate"], 15)
        self.assertEqual(HtmlOverlayServer.frame_rate_by_overlay, {"heartbeat": 15})
        studio._html_overlay_settings_save({"heartbeat_frame_rate": "45"})
        self.assertEqual(studio.config["heartbeat_frame_rate"], 0, "an unknown rate follows all overlays")
        self.assertEqual(HtmlOverlayServer.frame_rate_by_overlay, {})

    def test_startup_applies_it_before_a_save(self):
        MainDashboard._apply_overlay_server_settings(SimpleNamespace(config={"heartbeat_frame_rate": 24}))
        self.assertEqual(HtmlOverlayServer.frame_rate_by_overlay, {"heartbeat": 24})

    def test_each_overlay_page_hears_its_own_rate(self):
        server = HtmlOverlayServer(WEB)
        self.addCleanup(server.stop)
        server.register("heartbeat", "heartbeat", "Heartbeat")
        server.register("survey", "survey", "Survey")
        HtmlOverlayServer.frame_rate = 30
        HtmlOverlayServer.set_overlay_frame_rates({"heartbeat": 60})
        opener = build_opener(ProxyHandler({}))

        def health(overlay):
            url = f"http://127.0.0.1:{server.port}/api/health?token={server.token}&overlay={overlay}"
            return json.loads(opener.open(url, timeout=5).read())["frame_rate"]

        self.assertEqual(health("heartbeat"), 60, "the Watcher above all overlays")
        self.assertEqual(health("survey"), 30)
        HtmlOverlayServer.set_overlay_frame_rates({"heartbeat": 0})
        self.assertEqual(health("heartbeat"), 30)

    def test_the_deck_page_orb_keeps_to_it(self):
        script = (WEB / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        self.assertIn("frameRate: data.frame_rate", script)


def snapshot(events=(), reduced=False, frame_rate=None, thought=None, vitals=None):
    orb = {"size": 96, "eye": "theme", "liveliness": "standard", "idle": True}
    if frame_rate is not None:
        orb["frame_rate"] = frame_rate
    heartbeat = {"events": list(events), "status_seq": 0, "orb": orb, "personality": "curious"}
    if thought:
        heartbeat["thought"] = thought
    if vitals:
        heartbeat["vitals"] = vitals
    return {"theme": THEME, "effects": {"crt": True, "reduced_motion": reduced}, "heartbeat": heartbeat}


class _BrowserTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Playwright Chromium is unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()


class WatcherMotionBrowserTests(_BrowserTestCase):
    def open(self, data=None, width=96):
        page = self.browser.new_page(viewport={"width": width, "height": 96})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not path.is_file():
                route.fulfill(status=404, body="")
            elif path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(path))

        page.route("http://refined.test/**", serve)
        page.goto("http://refined.test/heartbeat/index.html")
        page.evaluate("data => renderHeartbeat(data)", data or snapshot())
        return page

    # The orb on a hand-stepped 60 fps clock: its own loop stopped, frames
    # drawn one at a time.
    STEP = """({frames, setup}) => {
      const orb = heartbeatOrb;
      cancelAnimationFrame(orb.raf);
      orb.running = true;
      const life = orb.life;
      life.saccade = {x: 0, y: 0, at: 1e15, until: 0};
      life.look = null;
      const t0 = performance.now() + 5000;
      for (let i = 0; i < 3; i += 1) { orb.advance(t0 + i * 16.7); orb.draw(t0 + i * 16.7); }
      const begin = t0 + 50;
      new Function('orb', 'life', 'now', setup)(orb, life, begin);
      const rows = [];
      for (let i = 1; i <= frames; i += 1) {
        const t = begin + i * 16.7;
        orb.advance(t);
        orb.draw(t);
        rows.push({pose: {...orb.pose}, shown: {...orb.shown}, effects: orb.effects.map((e) => [e.name, e.cut != null, orb.fadeOf(e, t)]),
          live: orb.state().effects});
      }
      return rows;
    }"""

    def step(self, page, frames, setup=""):
        return page.evaluate(self.STEP, {"frames": frames, "setup": setup})

    def test_a_glance_settles_instead_of_jumping(self):
        page = self.open()
        # A saccade: the life module moves the eye there in one step; what's
        # drawn follows it.
        rows = self.step(page, 30, "life.saccade = {x: .05, y: 0, at: 1e15, until: now + 1e6};")
        target = rows[-1]["pose"]["dx"]
        self.assertAlmostEqual(target, rows[0]["pose"]["dx"], places=6, msg="a step, held")
        shown = [row["shown"]["dx"] for row in rows]
        self.assertLess(shown[0], target * .6, "the first frame is on its way, not there")
        self.assertLess(abs(shown[-1] - target), .002, "and half a second later it has arrived")
        self.assertLess(max(shown), target * 1.15, "a hint of overshoot at most")

    def test_lids_glide_into_a_squint(self):
        page = self.open()
        rows = self.step(page, 90, "life.vitals({scooping: true});")
        self.assertGreaterEqual(rows[0]["pose"]["lid"], .42, "the life module asks for the squint at once")
        self.assertLess(rows[0]["shown"]["lid"], rows[0]["pose"]["lid"] - .05, "the lids don't snap")
        self.assertGreater(rows[-1]["shown"]["lid"], .41, "and close to it within a second and a half")
        lids = [row["shown"]["lid"] for row in rows]
        self.assertEqual(lids, sorted(lids), "steadily, without bouncing")

    def test_still_frames_land_exactly_on_the_pose(self):
        page = self.open(snapshot(reduced=True, vitals={"scooping": True}))
        state = page.evaluate("heartbeatOrb.state()")
        self.assertFalse(state["running"])
        self.assertEqual(state["shown"]["lid"], state["pose"]["lid"])

    def test_a_newer_effect_fades_the_last_one_out(self):
        page = self.open()
        rows = self.step(page, 24, """
          orb.play({effect: 'signal', tone: 'accent', weight: .8}, now - 400);
          orb.play({effect: 'signal', tone: 'green', weight: .8}, now);""")
        first = rows[3]["effects"]
        self.assertEqual([cut for _name, cut, _fade in first], [True, False])
        self.assertTrue(0 < first[0][2] < 1, "the older one is fading, still drawn")
        self.assertEqual(rows[3]["live"], ["signal"], "only what plays is reported")
        self.assertEqual(len(rows[-1]["effects"]), 1, "gone once faded")

    def test_its_frame_rate_reaches_the_orb(self):
        page = self.open(snapshot(frame_rate=15))
        self.assertEqual(page.evaluate("heartbeatOrb.state().frameRate"), 15)
        page.evaluate("data => renderHeartbeat(data)", snapshot(frame_rate=0))
        self.assertEqual(page.evaluate("heartbeatOrb.state().frameRate"), 60, "0 leaves it at its best")

    def test_a_thought_fades_in_except_under_reduced_motion(self):
        thought = {"id": 1, "text": "Another star.", "side": "right",
                   "style": {"backdrop": True, "colour": "bright", "size": "standard", "hold": "standard"}}
        names = "() => document.getAnimations().map((animation) => animation.animationName)"
        page = self.open(snapshot(thought=thought), width=96 + 330)
        page.wait_for_timeout(60)
        self.assertIn("thought-in", page.evaluate(names))
        self.assertIn("thought-reach", page.evaluate(names))
        still = self.open(snapshot(thought=thought, reduced=True), width=96 + 330)
        self.assertTrue(still.evaluate("document.body.classList.contains('still')"))
        self.assertEqual(still.evaluate(names), [])
        self.assertEqual(still.text_content(".thought-words"), "Another star.")

    def test_the_pupil_is_a_soft_star_not_a_disc(self):
        page = self.open(snapshot(reduced=True))
        # Its whiteness (the dimmest channel; the glow round it is the eye's
        # own colour) falls away from the centre without a hard edge. The old
        # disc fell by about 150 in one pixel; the star by about 75 at most.
        samples = page.evaluate("""() => {
          const canvas = document.getElementById('orb');
          const ratio = canvas.width / canvas.clientWidth;
          const ctx = canvas.getContext('2d');
          const row = [];
          for (let x = 48; x <= 60; x += 1) {
            const pixel = ctx.getImageData(Math.round(x * ratio), Math.round(48 * ratio), 1, 1).data;
            row.push(Math.min(pixel[0], pixel[1], pixel[2]));
          }
          return row;
        }""")
        self.assertGreater(samples[0], 200, "white-hot at its heart")
        steps = [samples[index] - samples[index + 1] for index in range(len(samples) - 1)]
        self.assertLess(max(steps), 110, samples)


class WatcherFinishBrowserTests(_BrowserTestCase):
    """The second 5.5.7 pass: what still looked only "ok" in the stills.

    Each measure here was checked against 5.5.6, which fails it, so the
    thresholds sit between the two.
    """

    # One still frame (reduced motion) of a curious eye looking straight
    # ahead, with whatever the test changes in its pose or heat.
    STILL = """({pose, heat}) => {
      const orb = heartbeatOrb, life = orb.life;
      Object.assign(orb.heat, heat || {});
      const base = life.pose.bind(life);
      life.pose = (now) => ({...base(now), dx: 0, dy: 0, lid: 0, lidLower: 0, ...(pose || {})});
      orb.draw(performance.now());
      life.pose = base;
    }"""

    PIXEL = """([x, y]) => {
      const canvas = document.getElementById('orb');
      const ratio = canvas.width / canvas.clientWidth;
      return Array.from(canvas.getContext('2d').getImageData(Math.round(x * ratio), Math.round(y * ratio), 1, 1).data);
    }"""

    # The average whiteness (dimmest channel) on a ring round the pupil.
    RING = """(radius) => {
      const canvas = document.getElementById('orb');
      const ratio = canvas.width / canvas.clientWidth;
      const ctx = canvas.getContext('2d');
      let sum = 0;
      for (let index = 0; index < 16; index += 1) {
        const angle = index / 16 * Math.PI * 2;
        const pixel = ctx.getImageData(Math.round((48 + Math.cos(angle) * radius) * ratio),
          Math.round((48 + Math.sin(angle) * radius) * ratio), 1, 1).data;
        sum += Math.min(pixel[0], pixel[1], pixel[2]);
      }
      return sum / 16;
    }"""

    def still_page(self):
        data = snapshot(reduced=True)
        page = self.browser.new_page(viewport={"width": 96, "height": 96}, device_scale_factor=2)
        self.addCleanup(page.close)

        def serve(route, *_rest):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not path.is_file():
                route.fulfill(status=404, body="")
            elif path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript", body=path.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(path))

        page.route("http://finish.test/**", serve)
        page.goto("http://finish.test/heartbeat/index.html")
        page.evaluate("data => renderHeartbeat(data)", data)
        return page

    def draw(self, page, pose=None, heat=None):
        page.evaluate(self.STILL, {"pose": pose or {}, "heat": heat or {}})

    @staticmethod
    def hue(pixel):
        red, green, blue = (channel / 255 for channel in pixel[:3])
        high, low = max(red, green, blue), min(red, green, blue)
        if high == low:
            return 0.0
        span = high - low
        if high == red:
            return 60 * (((green - blue) / span) % 6)
        if high == green:
            return 60 * ((blue - red) / span + 2)
        return 60 * ((red - green) / span + 4)

    def test_the_scanlines_thin_where_the_star_burns_through(self):
        page = self.still_page()
        alpha = page.evaluate("""() => {
          const orb = heartbeatOrb;
          const glass = [...orb.layers.entries()].find(([key]) => key.startsWith('glass|'))[1];
          const ctx = glass.getContext('2d');
          const ratio = orb.ratio, step = Math.max(2, 2 * 48 / 27) * ratio, top = (48 - .8 * 48) * ratio;
          const row = Math.round(top + step * Math.round((48 * ratio - top) / step) + 1);
          const at = (x) => ctx.getImageData(Math.round(x * ratio), row, 1, 1).data[3];
          return [at(48), at(48 + .45 * 48)];
        }""")
        self.assertGreater(alpha[1], 15, "scanlines still cross the glass")
        self.assertLess(alpha[0], alpha[1] * .5, "but thin over the centre (5.5.6: the same everywhere)")

    def test_a_flare_spreads_instead_of_blowing_the_iris_out(self):
        page = self.still_page()
        self.draw(page, {"flare": 0})
        calm = page.evaluate(self.RING, .2 * 48)
        self.draw(page, {"flare": 1.2})
        flared = page.evaluate(self.RING, .2 * 48)
        self.assertGreater(flared, calm, "a flare still brightens it")
        self.assertLess(flared - calm, 37, "by much less than the 45 that washed 5.5.6 out")

    # Brightness and saturation, averaged on a ring well out in the iris.
    OUTER = """() => {
      const canvas = document.getElementById('orb');
      const ratio = canvas.width / canvas.clientWidth;
      const ctx = canvas.getContext('2d');
      let bright = 0, saturation = 0;
      for (let index = 0; index < 24; index += 1) {
        const angle = index / 24 * Math.PI * 2;
        const p = ctx.getImageData(Math.round((48 + Math.cos(angle) * 18) * ratio),
          Math.round((48 + Math.sin(angle) * 18) * ratio), 1, 1).data;
        const high = Math.max(p[0], p[1], p[2]) / 255, low = Math.min(p[0], p[1], p[2]) / 255;
        bright += high / 24;
        saturation += (high === low ? 0 : (high - low) / (1 - Math.abs(high + low - 1))) / 24;
      }
      return {bright, saturation};
    }"""

    def test_the_iris_deepens_toward_its_edge(self):
        page = self.still_page()
        self.draw(page)
        self.assertGreater(page.evaluate(self.OUTER)["bright"], .34,
                           "a band of its own colour, not a fade to black (5.5.6: .30)")
        data = snapshot(reduced=True)
        data["heartbeat"]["orb"]["eye"] = "hal"
        page.evaluate("data => renderHeartbeat(data)", data)
        self.draw(page)
        self.assertGreater(page.evaluate(self.OUTER)["saturation"], .48,
                           "HAL's red stays a deep red out there (5.5.6: .34, washed toward grey)")

    def test_a_squint_shades_the_lit_iris(self):
        page = self.still_page()
        above_pupil = [48, 48 - .3 * 48]
        self.draw(page)
        open_eye = max(page.evaluate(self.PIXEL, above_pupil)[:3])
        self.draw(page, {"lid": .42, "lidLower": .42})
        squint = max(page.evaluate(self.PIXEL, above_pupil)[:3])
        self.assertLess(squint, open_eye * .75, "5.5.6's lids never reached it")

    def test_danger_recedes_to_the_rim_instead_of_turning_the_eye_pink(self):
        page = self.still_page()
        # Danger half gone: 5.5.6 tinted the whole eye magenta here.
        self.draw(page, heat={"red": .42})
        centre = page.evaluate(self.PIXEL, [52, 48])
        rim = page.evaluate(self.PIXEL, [48 + .5 * 48, 50])
        self.assertTrue(150 <= self.hue(centre) <= 220, centre)
        self.assertGreater(rim[0], rim[2], f"the rim holds the red {rim}")
        self.draw(page, heat={"red": 0})
        self.assertLess(page.evaluate(self.PIXEL, [48 + .5 * 48, 50])[0], rim[0], "and lets it go")

    def test_a_dark_edge_parts_it_from_a_bright_scene(self):
        page = self.still_page()
        self.draw(page)
        edge = page.evaluate(self.PIXEL, [48 - .7071 * 48 * .985, 48 + .7071 * 48 * .985])
        self.assertGreater(edge[3], 70, "5.5.6: 35, the bevel's own edge")
        self.assertEqual(page.evaluate(self.PIXEL, [1, 1])[3], 0, "corners stay transparent")


if __name__ == "__main__":
    unittest.main()
