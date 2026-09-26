"""Each navigation state projects its own animated scene.

The status plate's deck plays a scene per state and the ship's hologram bay an
aura round the ship (web/navigation_hud/scene.js). These checks keep the
promises that are easy to lose in a canvas: every state reaches a scene of its
own, the clock stops when nobody can see it, a state change re-projects
rather than cutting, journal pulses play once, and the canvases stay sharp at
any text size. They read canvas pixels and scene state, not screenshots.
"""

from pathlib import Path
import time
import unittest
from urllib.parse import unquote, urlsplit

from tests.test_navigation_state_visuals import LABELS, hud_snapshot, hud_state


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SHIP_ART = ROOT / "assets" / "images" / "ships"

LIT_PIXELS = """(id) => {
  const canvas = document.getElementById(id);
  const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
  let lit = 0;
  for (let index = 3; index < data.length; index += 4) if (data[index] > 12) lit += 1;
  return lit / (canvas.width * canvas.height);
}"""


class NavigationSceneBrowserTests(unittest.TestCase):
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

    def open(self, width=500, height=326):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            if path.startswith("/ship-art/"):
                target = SHIP_ART / path[len("/ship-art/"):]
            else:
                target = WEB / path.lstrip("/")
            if target.is_file():
                route.fulfill(path=str(target))
            else:
                route.fulfill(status=404, body="")

        page.route("http://scene.test/**", serve)
        page.goto("http://scene.test/navigation_hud/index.html")
        return page

    def render(self, page, state, **options):
        options.setdefault("reduced", False)
        page.evaluate("snapshot => render(snapshot)", hud_snapshot(state, **options))

    def frames(self, page):
        return page.evaluate("navigationScene.frames")

    def test_every_state_reaches_a_scene_of_its_own(self):
        page = self.open()
        keys = page.evaluate("""labels => labels.map((label) => {
          const motion = label.motion, key = NavigationScene.sceneKey(motion, label.label, '');
          return [label.label, key, NavigationScene.hasScene(key)];
        })""", [{"label": label, "motion": hud_state(label)["motion"]} for label in LABELS])
        for label, key, has_scene in keys:
            with self.subTest(label=label):
                self.assertTrue(has_scene, f"{label} fell through to no scene ({key})")
        # Only normal space itself uses the normal-space scene.
        self.assertEqual([label for label, key, _ in keys if key == "flight"], ["FLIGHT"])
        by_label = {label: key for label, key, _ in keys}
        expected = {
            "SUPERCRUISE": "supercruise", "SCO OVERCHARGE": "supercruise_overcharge",
            "HYPERSPACE": "hyperspace", "JUMPING": "jumping", "FSD CHARGE": "fsd_charge",
            "HYPER CHARGE": "hyper_charge", "ASTEROID FIELD": "asteroid_field",
            "GALAXY MAP": "galaxy_map", "ORRERY": "orrery", "DSS EFFICIENT 4/6": "dss",
            "SIGNAL TARGET": "target_signal", "SIGNAL THREAT 4": "signal_threat",
            "ORBITAL APPROACH": "orbital_approach", "LANDED": "landed",
            "RHINO": "rhino", "HANDBRAKE": "srv_handbrake", "ONFOOT": "on_foot",
            "SCARAB DEPLOY": "vehicle_deploy_srv", "BOARDING SCORPION": "vehicle_board_scorpion",
            "PAD 07 CLEARED": "docking_clearance", "DOCK TIMEOUT": "docking_timeout",
            "CARRIER VICINITY": "carrier_vicinity", "STATION VICINITY": "station_vicinity",
            "COMMS": "comms_panel", "SYSTEM REBOOT": "system_reboot",
        }
        for label, key in expected.items():
            with self.subTest(label=label):
                self.assertEqual(by_label[label], key)

    def test_every_state_projects_into_the_deck_and_round_the_ship(self):
        page = self.open()
        for label in LABELS:
            with self.subTest(label=label):
                self.render(page, hud_state(label, altitude_m=18400, vertical_mps=310, scan_percent=.44))
                page.evaluate("navigationScene.transition = null; navigationScene.previous = null;"
                              "navigationScene.draw(performance.now())")
                self.assertGreater(page.evaluate(LIT_PIXELS, "deck-canvas"), .01, "an empty deck")
                self.assertGreater(page.evaluate(LIT_PIXELS, "bay-canvas"), .01, "no aura round the ship")

    def test_the_clock_runs_only_while_someone_can_see_it(self):
        page = self.open()
        self.render(page, hud_state("SUPERCRUISE"))
        before = self.frames(page)
        page.wait_for_timeout(400)
        self.assertGreater(self.frames(page) - before, 5, "a visible scene animates")
        self.assertTrue(page.evaluate("navigationScene.running"))
        # Hidden overlays keep their state but spend no frames on it.
        self.render(page, hud_state("SUPERCRUISE"), window={"visible": False})
        self.assertFalse(page.evaluate("navigationScene.running"))
        before = self.frames(page)
        page.wait_for_timeout(300)
        self.assertEqual(self.frames(page), before)
        self.render(page, hud_state("SUPERCRUISE"))
        self.assertTrue(page.evaluate("navigationScene.running"))

    def test_reduced_motion_paints_one_settled_still_per_change(self):
        page = self.open()
        self.render(page, hud_state("HYPERSPACE"), reduced=True)
        self.assertFalse(page.evaluate("navigationScene.running"))
        self.assertIsNone(page.evaluate("navigationScene.transition"))
        still = page.evaluate("document.getElementById('deck-canvas').toDataURL()")
        self.assertGreater(page.evaluate(LIT_PIXELS, "deck-canvas"), .01)
        page.wait_for_timeout(250)
        self.assertEqual(page.evaluate("document.getElementById('deck-canvas').toDataURL()"), still)
        # A change is a new still, without a re-projection or an event accent.
        state = hud_state("ARRIVAL")
        state.update(event_sequence=9, event_kind="arrival", event_tone="accent")
        self.render(page, state, reduced=True)
        self.assertEqual(page.evaluate("[navigationScene.key, navigationScene.transition, navigationScene.event]"),
                         ["arrival", None, None])
        self.assertNotEqual(page.evaluate("document.getElementById('deck-canvas').toDataURL()"), still)

    def test_state_changes_reproject_and_related_states_cross_fade(self):
        page = self.open()
        self.render(page, hud_state("SUPERCRUISE"))
        page.wait_for_timeout(100)
        self.render(page, hud_state("HYPERSPACE"))
        self.assertEqual(page.evaluate("navigationScene.transition.crossfade"), False)
        # Interrupted part-way, the next change continues from what is shown.
        page.wait_for_timeout(120)
        self.render(page, hud_state("ARRIVAL"))
        transition = page.evaluate("[navigationScene.previous.key, navigationScene.transition.fromScale]")
        self.assertEqual(transition[0], "supercruise", "still folding the scene on screen")
        self.assertLess(transition[1], 1)
        page.wait_for_function("navigationScene.transition === null", timeout=2000)
        self.assertEqual(page.evaluate("navigationScene.key"), "arrival")
        # Supercruise and its assist share one hologram: they cross-fade.
        self.render(page, hud_state("SUPERCRUISE"))
        page.wait_for_function("navigationScene.transition === null", timeout=2000)
        self.render(page, hud_state("SC ASSIST"))
        self.assertTrue(page.evaluate("navigationScene.transition.crossfade"))
        # Live telemetry within one state never restarts the scene.
        page.wait_for_function("navigationScene.transition === null", timeout=2000)
        self.render(page, hud_state("SC ASSIST", fuel_scooping=True))
        self.assertIsNone(page.evaluate("navigationScene.transition"))

    def test_journal_pulses_play_once_and_gear_pulses_on_change(self):
        page = self.open()
        state = hud_state("SUPERCRUISE")
        state.update(event_sequence=5, event_kind="honk", event_tone="accent")
        self.render(page, state)
        started = page.evaluate("navigationScene.event.start")
        self.assertEqual(page.evaluate("navigationScene.event.kind"), "honk")
        # Snapshots repeat a live pulse until it expires; it must not restart.
        self.render(page, state)
        self.assertEqual(page.evaluate("navigationScene.event.start"), started)
        page.wait_for_function("navigationScene.event === null", timeout=3000)
        self.render(page, hud_state("SUPERCRUISE", landing_gear=False))
        self.render(page, hud_state("SUPERCRUISE", landing_gear=True))
        self.assertEqual(page.evaluate("navigationScene.gear.down"), True)

    def test_quiet_states_project_in_the_hud_colour(self):
        page = self.open()
        self.render(page, hud_state("FLIGHT"))
        colours = page.evaluate("""() => [navigationScene.state.c, navigationScene.state.level,
          getComputedStyle(document.documentElement).getPropertyValue('--orange').trim(),
          dom.hud.style.getPropertyValue('--state')]""")
        self.assertEqual(colours[0], colours[2], "the hologram is the HUD's orange")
        self.assertLess(colours[1], 1, "and a little softer")
        self.assertNotEqual(colours[3], colours[2], "while the notice stays quiet grey")

    def test_canvases_stay_sharp_at_larger_text(self):
        page = self.open(750, 489)
        self.render(page, hud_state("SUPERCRUISE"), scale=1.5)
        sizes = page.evaluate("""() => ['deck-canvas', 'bay-canvas'].map((id) => {
          const canvas = document.getElementById(id);
          return [canvas.width, canvas.clientWidth, devicePixelRatio];
        })""")
        for backing, css, ratio in sizes:
            self.assertAlmostEqual(backing, css * 1.5 * ratio, delta=1)
        self.render(page, hud_state("SUPERCRUISE"), scale=1)
        backing, css, ratio = page.evaluate("""() => {
          const canvas = document.getElementById('deck-canvas');
          return [canvas.width, canvas.clientWidth, devicePixelRatio];
        }""")
        self.assertAlmostEqual(backing, css * ratio, delta=1)

    def test_scenes_are_cheap_to_draw(self):
        page = self.open()
        worst = []
        for label in ("ASTEROID FIELD", "HYPERSPACE", "SCO OVERCHARGE", "FSD CHARGE", "SETTLEMENT", "FSS"):
            self.render(page, hud_state(label, shields_known=True, shields_up=False, fuel_scooping=True))
            page.wait_for_timeout(600)
            worst.append(page.evaluate("""() => {
              const scene = navigationScene, start = performance.now();
              let now = start;
              for (let index = 0; index < 30; index += 1) { now += 33.3; scene.advance(now); scene.draw(now); }
              return (performance.now() - start) / 30;
            }"""))
        # A 30 fps overlay beside the game: the whole frame stays well inside
        # a couple of milliseconds even in software-rendered Chromium.
        self.assertLess(max(worst), 4.0, worst)


if __name__ == "__main__":
    unittest.main()
