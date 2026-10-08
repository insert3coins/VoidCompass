"""5.5.3: The Watcher's life (todo-watcher-life.md) — blinks, breathing and
glances between events, a look the way each event points, a double take at
rare finds, side-eye and squint, and a mood that remembers the session."""

import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.core.application_runtime import ApplicationRuntime
from voidcompass.overlays.heartbeat_events import GAZES, _EVENTS, classify
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD, LIVELINESS, vitals

WEB = Path(__file__).resolve().parents[1] / "web"


class WatcherEventTests(unittest.TestCase):
    def test_every_event_looks_somewhere(self):
        for name in _EVENTS:
            with self.subTest(event=name):
                self.assertIn(classify(name)["gaze"], GAZES)
        self.assertEqual(classify("FSDJump")["gaze"], "up")
        self.assertEqual(classify("Docked")["gaze"], "down")
        self.assertEqual(classify("Interdicted")["gaze"], "side")
        self.assertEqual(classify("FSSDiscoveryScan")["gaze"], "sweep")

    def test_rare_finds_earn_a_double_take(self):
        self.assertTrue(classify("Scan", {"PlanetClass": "Icy body", "WasDiscovered": False})["rare"])
        self.assertTrue(classify("Scan", {"PlanetClass": "Earthlike body", "WasDiscovered": True})["rare"])
        self.assertFalse(classify("Scan", {"PlanetClass": "Icy body", "WasDiscovered": True})["rare"])
        self.assertTrue(classify("CodexEntry", {"IsNewEntry": True})["rare"])
        self.assertFalse(classify("CodexEntry", {})["rare"])

    def test_status_flags_become_vitals(self):
        self.assertEqual(vitals(0x00000800 | 0x00400000),
                         {"scooping": True, "low_fuel": False, "overheating": False, "danger": True})
        root = ApplicationRuntime()
        self.addCleanup(root.close)
        hud = HeartbeatHUD(root, {"heartbeat_hud_x": 20, "heartbeat_hud_y": 20})
        self.addCleanup(hud.destroy)
        hud.pulse("status", "STATUS", "FLIGHT", {"Flags": 0x00100000})
        self.assertTrue(hud._html_render_model["vitals"]["overheating"])

    def test_settings_are_per_profile_and_in_overlay_studio(self):
        self.assertIn("heartbeat_liveliness", config_module.PROFILE_TEXT_SETTINGS)
        self.assertIn("heartbeat_idle_motion", config_module.PROFILE_BOOL_SETTINGS)
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="heartbeat_hud">(.*?)</section>', html, re.S).group(1)
        lively = re.search(r'data-studio-setting="heartbeat_liveliness">(.*?)</select>', section, re.S).group(1)
        self.assertEqual(tuple(re.findall(r'value="([a-z]+)"', lively)), LIVELINESS)
        self.assertIn('data-overlay-option="heartbeat_idle_motion"', section)
        for page in ("dashboard/index.html", "heartbeat/index.html"):
            source = (WEB / page).read_text(encoding="utf-8")
            self.assertLess(source.index("heartbeat-life.js"), source.index("heartbeat-orb.js"))


class WatcherLifeBrowserTests(unittest.TestCase):
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

    def open(self):
        from tests.test_heartbeat_orb import STUB

        page = self.browser.new_page(viewport={"width": 96, "height": 96})
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

        page.route("http://life.test/**", serve)
        page.goto("http://life.test/heartbeat/index.html")
        return page

    # A life on its own seeded clock, stepped by hand.
    SIM = """({steps, until, configure, before}) => {
      const life = new HeartbeatLife(7, 0);
      life.configure(configure || {});
      (before || []).forEach(([at, kind, value]) => { life.advance(at); life[kind](value, at); });
      const poses = [];
      for (let t = 0; t <= until; t += steps) { life.advance(t); poses.push({t, ...life.pose(t)}); }
      return {poses, state: life.state(until)};
    }"""

    def simulate(self, page, until=13000, steps=20, configure=None, before=None):
        return page.evaluate(self.SIM, {"steps": steps, "until": until, "configure": configure, "before": before})

    def test_it_blinks_and_glances_between_events(self):
        page = self.open()
        run = self.simulate(page)
        self.assertGreater(max(pose["lid"] for pose in run["poses"]), .9, "a full blink within 12 s")
        self.assertGreaterEqual(run["state"]["blinks"], 1)
        moved = [pose for pose in run["poses"] if abs(pose["dx"]) + abs(pose["dy"]) > .005]
        self.assertTrue(moved, "a saccade")
        self.assertLess(abs(run["poses"][-1]["dx"]) + abs(run["poses"][-1]["dy"]), .1)
        still = [pose for pose in run["poses"] if pose["dx"] == 0 and pose["dy"] == 0]
        self.assertTrue(still, "and returns to centre")

    def test_idle_motion_off_holds_still(self):
        page = self.open()
        run = self.simulate(page, until=20000, configure={"idle": False})
        self.assertLess(max(pose["lid"] for pose in run["poses"]), .01, "no blinks (only the slow droop of fatigue)")
        self.assertEqual(run["state"]["blinks"], 0)

    def test_it_looks_where_events_point_and_double_takes_rare_finds(self):
        page = self.open()
        result = page.evaluate("""() => {
          const life = new HeartbeatLife(3, 0);
          const up = life.notice({gaze: 'up', weight: .9}, 0);
          const lookUp = life.pose(400).dy;
          const side = (life.notice({gaze: 'side', weight: .9}, 2000), life.pose(2600));
          const pulseAt = life.notice({rare: true, weight: .9, gaze: 'sweep'}, 6000);
          return {up, lookUp, sideLid: side.lid, sideTilt: side.tilt, pulseAt,
                  excitement: life.state(6000).excitement};
        }""")
        self.assertIsNone(result["up"])
        self.assertLess(result["lookUp"], -.03, "looks up for a jump")
        self.assertGreater(result["sideLid"], .2)
        self.assertGreater(result["sideTilt"], 0, "a narrowed, tilted side-eye")
        self.assertEqual(result["pulseAt"], 7250, "the double take ends in a pulse")
        self.assertGreater(result["excitement"], .3)

    def test_mood_squints_tenses_and_tires(self):
        page = self.open()
        mood = page.evaluate("""() => {
          const life = new HeartbeatLife(5, 0);
          life.vitals({scooping: true});
          const squint = life.pose(100).lid;
          life.vitals({danger: true});
          for (let t = 0; t <= 6000; t += 100) life.advance(t);
          const tense = life.pose(6000);
          life.vitals({});
          for (let t = 6000; t <= 90000; t += 500) life.advance(t);
          const relieved = life.pose(90000);
          life.notice({weight: .3}, 3 * 3600 * 1000 - 1000);
          const tired = life.pose(3 * 3600 * 1000);
          return {squint, tenseRed: tense.red, tensePupil: tense.pupil, relievedRed: relieved.red,
                  tiredLid: tired.lid, tiredDim: tired.dim};
        }""")
        self.assertGreaterEqual(mood["squint"], .42)
        self.assertGreater(mood["tenseRed"], .5)
        self.assertLess(mood["tensePupil"], .85)
        self.assertLess(mood["relievedRed"], .1, "relief lets go of it")
        self.assertGreater(mood["tiredLid"], .2, "heavy lids after a long session")
        self.assertLess(mood["tiredDim"], 1)

    def test_the_orb_draws_lids_and_plays_the_double_take(self):
        from tests.test_heartbeat_orb import THEME

        page = self.open()
        base = {"theme": THEME, "effects": {"crt": True, "reduced_motion": False}}
        page.evaluate("s => renderHeartbeat(s)", {**base, "heartbeat": {
            "events": [], "status_seq": 0, "orb": {"size": 96, "eye": "theme", "liveliness": "alive", "idle": True},
            "vitals": {"scooping": True}}})
        page.evaluate("""s => renderHeartbeat(s)""", {**base, "heartbeat": {
            "events": [{"seq": 1, "event": "Scan", "family": "scan", "tone": "accent", "effect": "sweep",
                        "weight": .9, "gaze": "sweep", "rare": True}],
            "status_seq": 0, "orb": {"size": 96, "eye": "theme", "liveliness": "alive", "idle": True},
            "vitals": {"scooping": True}}})
        page.wait_for_timeout(1500)
        state = page.evaluate("heartbeatOrb.state()")
        self.assertGreaterEqual(state["pose"]["lid"], .42, "squinting into the star")
        self.assertIn("pulse", state["effects"])
        # Lids close the top of the lens: it reads darker than the open eye.
        self.assertGreater(state["life"]["excitement"], .3)
        cost = page.evaluate("""() => {
          const orb = heartbeatOrb, start = performance.now();
          for (let index = 0; index < 60; index += 1) { const now = start + index * 33; orb.advance(now); orb.draw(now); }
          return (performance.now() - start) / 60;
        }""")
        self.assertLess(cost, 4.0)


if __name__ == "__main__":
    unittest.main()
