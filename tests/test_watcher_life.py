"""5.5.3: The Watcher's life (todo-watcher-life.md) — its aperture, breathing and
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
                         {"fsd_charging": False, "glide": False, "fuel_percent": None,
                          "scooping": True, "low_fuel": False, "overheating": False, "danger": True})
        self.assertEqual(vitals(0x00020000, 0x00001000, 18.25)["fsd_charging"], True)
        self.assertEqual(vitals(0, 0x00001000, 18.25)["glide"], True)
        self.assertEqual(vitals(0, 0, 18.25)["fuel_percent"], 18.2)
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

    def test_it_thinks_and_glances_between_events_but_never_blinks(self):
        """5.5.3.1: no blinking (the user disliked it). The aperture tightens
        as it thinks, light sweeps the glass, and it glances about."""
        page = self.open()
        run = self.simulate(page, until=25000)
        self.assertLess(max(pose["lid"] for pose in run["poses"]), .05, "the lids stay open")
        self.assertGreater(max(pose["aperture"] for pose in run["poses"]), .9, "the aperture works")
        self.assertGreaterEqual(run["state"]["pulses"], 1)
        self.assertTrue(any(pose["glint"] is not None for pose in run["poses"]), "light crosses the glass")
        moved = [pose for pose in run["poses"] if abs(pose["dx"]) + abs(pose["dy"]) > .005]
        self.assertTrue(moved, "a saccade")
        still = [pose for pose in run["poses"] if pose["dx"] == 0 and pose["dy"] == 0]
        self.assertTrue(still, "and returns to centre")

    def test_idle_motion_off_holds_still(self):
        page = self.open()
        run = self.simulate(page, until=20000, configure={"idle": False})
        self.assertEqual(max(pose["aperture"] for pose in run["poses"]), 0)
        self.assertEqual(run["state"]["pulses"], 0)

    def test_a_depressed_eye(self):
        """The default nature: heavy lids, a low gaze, a dim slow eye, and a
        startle that barely lifts it."""
        page = self.open()
        moods = page.evaluate("""() => {
          const at = (personality) => {
            const life = new HeartbeatLife(6, 0);
            life.configure({personality, idle: false});
            life.notice({event: 'x', weight: .1}, 0);
            life.notice({event: 'UnderAttack', effect: 'alarm', tone: 'red', weight: .8}, 1000);
            return {pose: life.pose(5000), startle: life.expression?.strength || 0};
          };
          return {depressed: at('weary'), curious: at('curious')};
        }""")
        sad, keen = moods["depressed"], moods["curious"]
        self.assertGreater(sad["pose"]["lid"], .25, "heavy lids")
        self.assertGreater(sad["pose"]["dy"], keen["pose"]["dy"], "its gaze rests low")
        self.assertLess(sad["pose"]["dim"], keen["pose"]["dim"])
        self.assertLess(sad["pose"]["spin"], keen["pose"]["spin"])
        self.assertLess(sad["startle"], keen["startle"])

    def test_the_eye_follows_each_event_in(self):
        """Every journal line gets a look: the eye tracks the mote it drops."""
        from tests.test_heartbeat_orb import THEME

        page = self.open()
        base = {"theme": THEME, "effects": {"crt": True, "reduced_motion": False}}
        orb = {"size": 96, "eye": "theme", "liveliness": "standard", "idle": True}
        page.evaluate("s => renderHeartbeat(s)", {**base, "heartbeat": {"events": [], "status_seq": 0, "orb": orb}})
        page.evaluate("s => renderHeartbeat(s)", {**base, "heartbeat": {"status_seq": 0, "orb": orb, "events": [
            {"seq": 1, "event": "Music", "family": "system", "tone": "muted", "effect": "tick", "weight": .05,
             "gaze": "centre", "rare": False}]}})
        page.wait_for_timeout(250)
        gaze = page.evaluate("() => Math.hypot(heartbeatOrb.gaze.x, heartbeatOrb.gaze.y)")
        self.assertGreater(gaze, .005, "even a tick draws a glance")

    def test_what_the_commander_is_doing_sets_how_it_watches(self):
        page = self.open()
        stances = page.evaluate("""() => {
          const at = (state) => {
            const life = new HeartbeatLife(2, 0);
            life.configure({state, idle: false});
            return {activity: life.state(0).activity, pose: life.pose(100)};
          };
          return Object.fromEntries(['DOCKED', 'SUPERCRUISE', 'FSS', 'GLIDE', 'INTERDICTION EVADED', 'FLIGHT']
            .map((state) => [state, at(state)]));
        }""")
        self.assertEqual({state: row["activity"] for state, row in stances.items()},
                         {"DOCKED": "relaxed", "SUPERCRUISE": "ahead", "FSS": "scanning", "GLIDE": "down",
                          "INTERDICTION EVADED": "wary", "FLIGHT": "idle"})
        self.assertGreater(stances["DOCKED"]["pose"]["lidLower"], .05, "relaxed, lids at ease")
        self.assertLess(stances["SUPERCRUISE"]["pose"]["dy"], 0, "looking ahead")
        self.assertGreater(stances["GLIDE"]["pose"]["dy"], 0, "looking down at the surface")
        self.assertGreater(stances["INTERDICTION EVADED"]["pose"]["lid"], .1, "narrowed in danger")

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

    def test_expressions_feel_each_event(self):
        """5.5.3.1: startled then wary at danger, a smile at a payout, a
        steady stare for a jump, reading a message line by line."""
        page = self.open()
        feel = page.evaluate("""() => {
          const pose = (event, at) => { const life = new HeartbeatLife(9, 0); life.configure({});
            life.notice({event: 'Old', weight: .1}, 0); life.notice(event, 100); return life; };
          const alarm = pose({event: 'Interdicted', effect: 'alarm', tone: 'red', weight: 1}, 100);
          const startled = alarm.pose(300), wary = alarm.pose(3000);
          const paid = pose({event: 'SellExplorationData', effect: 'payout', tone: 'green', weight: .8}).pose(1200);
          const jump = pose({event: 'StartJump', effect: 'charge', weight: .9});
          const reading = pose({event: 'ReceiveText', effect: 'speak', weight: .6});
          const xs = [400, 700, 900].map((t) => reading.pose(t).dx);
          return {startled: [startled.expression, startled.pupil, startled.lid],
                  wary: [wary.expression, wary.lid], paid: [paid.expression, paid.lid, paid.lidLower, paid.tone],
                  jump: jump.pose(1000).expression, reading: [reading.pose(500).expression, xs]};
        }""")
        self.assertEqual(feel["startled"][0], "startled")
        self.assertLess(feel["startled"][1], .75, "a tiny pupil")
        self.assertEqual(feel["wary"][0], "wary", "then it stays wary")
        self.assertGreater(feel["wary"][1], .15, "narrowed eyes")
        self.assertEqual(feel["paid"][0], "pleased")
        self.assertGreater(feel["paid"][2], feel["paid"][1], "a smile: the lower lid rises more")
        self.assertEqual(feel["paid"][3], "green")
        self.assertEqual(feel["jump"], "focused")
        self.assertEqual(feel["reading"][0], "reading")
        xs = feel["reading"][1]
        self.assertLess(xs[0], xs[1], "reads left to right")

    def test_repeats_wear_off_and_quiet_makes_it_jumpy(self):
        page = self.open()
        habit = page.evaluate("""() => {
          const life = new HeartbeatLife(4, 0);
          const strengths = [];
          for (let index = 0; index < 8; index += 1) {
            life.notice({event: 'FSSSignalDiscovered', effect: 'signal', family: 'scan', weight: .4}, 1000 + index * 1000);
            strengths.push(life.expression.strength);
          }
          const calm = new HeartbeatLife(4, 0);
          calm.notice({event: 'x', weight: .1}, 1000);
          calm.notice({event: 'UnderAttack', effect: 'alarm', tone: 'red', weight: .8}, 2000);
          const quiet = new HeartbeatLife(4, 0);
          quiet.notice({event: 'x', weight: .1}, 1000);
          quiet.notice({event: 'UnderAttack', effect: 'alarm', tone: 'red', weight: .8}, 200000);
          return {strengths, calm: calm.expression.strength, quiet: quiet.expression.strength};
        }""")
        strengths = habit["strengths"]
        self.assertLess(strengths[-1], strengths[0] * .5, "the eighth signal in a row barely registers")
        self.assertGreater(habit["quiet"], habit["calm"], "after a long quiet it startles harder")

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
