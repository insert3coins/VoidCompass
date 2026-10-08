"""Each navigation state projects its own animated scene.

The status plate's deck plays a scene per state and the ship's hologram bay an
aura round the ship (web/navigation_hud/scene.js). These checks keep the
promises that are easy to lose in a canvas: every state reaches a scene of its
own, the clock stops when nobody can see it, a state change re-projects
rather than cutting, journal pulses play once, and the canvases stay sharp at
any text size. They read canvas pixels and scene state, not screenshots.
"""

from itertools import combinations
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

    def controlled_frame(self, page, phase, age=8):
        """Capture a settled scene at a known phase, independent of wall time."""
        return page.evaluate("""({phase, age}) => {
          const scene = navigationScene;
          scene.transition = null;
          scene.previous = null;
          scene.state.p = phase;
          scene.state.terrain = phase;
          scene.state.age = age;
          scene.draw(performance.now());
          const canvas = document.getElementById('deck-canvas');
          const data = canvas.getContext('2d').getImageData(
            0, 0, canvas.width, canvas.height).data;
          let lit = 0;
          for (let index = 3; index < data.length; index += 4) if (data[index] > 12) lit += 1;
          const lane = document.createElement('canvas');
          lane.width = Math.floor(canvas.width * .3);
          lane.height = canvas.height;
          lane.getContext('2d').drawImage(canvas, 0, 0, lane.width, lane.height,
            0, 0, lane.width, lane.height);
          return {key: scene.key, deck: canvas.toDataURL(), lane: lane.toDataURL(),
            coverage: lit / (canvas.width * canvas.height)};
        }""", {"phase": phase, "age": age})

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

    def test_every_model_is_a_well_formed_solid(self):
        # Scenes stage solid models (models.js): rocks, the station, the
        # carrier, ships, vehicles, the commander. A face pointing at a missing
        # vertex, or a light without a direction, would fail silently.
        page = self.open()
        report = page.evaluate("""() => {
          const M = window.NavigationModels;
          const models = {
            coriolis: M.coriolis(), city: M.stationCity(), carrier: M.carrier(), capital: M.capital(),
            wedge: M.ship(), fighter: M.ship('fighter'), taxi: M.ship('taxi'), interdictor: M.ship('interdictor'),
            thargoid: M.thargoid(), scarab: M.vehicle('scarab'), scorpion: M.vehicle('scorpion'),
            rhino: M.vehicle('rhino'), nomad: M.vehicle('nomad'), skimmer: M.skimmer(), pad: M.hexPad(),
            port: M.surfacePort(), dome: M.building('dome'), tower: M.building('tower', 1),
            hangar: M.building('hangar'), block: M.building('block'), beacon: M.beacon(),
            canister: M.canister(), crystal: M.crystal(), cone: M.cone(12, 1.4), segment: M.driveSegment(),
            walking: M.commander(1.2), standing: M.commander(0, {walking: false}), limpet: M.limpet(),
            ...Object.fromEntries(Array.from({length: 12}, (_, seed) => [`rock${seed}`, M.rock(seed)])),
          };
          return Object.fromEntries(Object.entries(models).map(([name, model]) => {
            const faults = [];
            model.f.forEach((face, index) => {
              if (face.i.length < 3) faults.push(`face ${index} has ${face.i.length} corners`);
              if (face.i.some((vertex) => !Array.isArray(model.v[vertex]))) faults.push(`face ${index} misses a vertex`);
              if (typeof face.k !== 'string') faults.push(`face ${index} has no kind`);
            });
            (model.lights || []).forEach((light, index) => {
              if (![light.at, light.n].every((v) => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite))) {
                faults.push(`light ${index} is malformed`);
              }
            });
            if (!model.v.every((v) => v.length === 3 && v.every(Number.isFinite))) faults.push('bad vertex');
            return [name, {faces: model.f.length, faults}];
          }));
        }""")
        for name, result in report.items():
            with self.subTest(model=name):
                self.assertGreater(result["faces"], 0)
                self.assertEqual(result["faults"], [])
        # The carrier's pads are separate lamps so a scene can light them in turn.
        kinds = page.evaluate("[...new Set(NavigationModels.carrier().f.map((face) => face.k))]")
        self.assertTrue({f"pad{index}" for index in range(8)} <= set(kinds))

    def test_each_kind_of_star_has_its_own_form(self):
        # The star takes its colour from its class and its form from what it
        # is: a sun, a white dwarf, a neutron star's jets, a black hole's
        # disc, a Wolf-Rayet's shells, a T Tauri's dust, a brown dwarf.
        page = self.open()
        frames = {}
        for star in ("G", "DA", "N", "H", "W", "TTS", "T"):
            with self.subTest(star=star):
                snapshot = hud_snapshot(hud_state("SYSTEM MAP"), reduced=False)
                snapshot["system"]["star_class"] = star
                page.evaluate("snapshot => render(snapshot)", snapshot)
                frames[star] = self.controlled_frame(page, 1.37)["deck"]
        for left, right in combinations(frames, 2):
            with self.subTest(left=left, right=right):
                self.assertNotEqual(frames[left], frames[right])
        # A targeted system shows the route's next star, not the local one.
        targets = {}
        for star in ("H", "N"):
            snapshot = hud_snapshot(hud_state("SYSTEM TARGET"), reduced=False)
            snapshot["system"]["star_class"] = "G"
            snapshot["route"]["next_star"]["star_class"] = star
            page.evaluate("snapshot => render(snapshot)", snapshot)
            self.assertEqual(page.evaluate("[navigationScene.state.starFamily, navigationScene.state.targetFamily]"),
                             ["g", "blackhole" if star == "H" else "neutron"])
            targets[star] = self.controlled_frame(page, 1.37)["deck"]
        self.assertNotEqual(targets["H"], targets["N"])

    def test_every_state_projects_into_the_deck_and_round_the_ship(self):
        page = self.open()
        for label in LABELS:
            with self.subTest(label=label):
                self.render(page, hud_state(label, altitude_m=18400, vertical_mps=310, scan_percent=.44))
                page.evaluate("navigationScene.transition = null; navigationScene.previous = null;"
                              "navigationScene.draw(performance.now())")
                self.assertGreater(page.evaluate(LIT_PIXELS, "deck-canvas"), .01, "an empty deck")
                self.assertGreater(page.evaluate(LIT_PIXELS, "bay-canvas"), .01, "no aura round the ship")

    def test_fsd_charge_scenes_remain_distinct_and_alive(self):
        page = self.open()
        opening_frames = {}
        reduced_stills = {}
        for label, key in (("FSD CHARGE", "fsd_charge"), ("HYPER CHARGE", "hyper_charge")):
            with self.subTest(label=label):
                self.render(page, hud_state(label))
                frames = page.evaluate("""() => {
                  const scene = navigationScene;
                  const canvas = document.getElementById('deck-canvas');
                  scene.transition = null;
                  scene.previous = null;
                  const capture = (age, phase) => {
                    scene.state.age = age;
                    scene.state.p = phase;
                    scene.draw(performance.now());
                    const data = canvas.getContext('2d').getImageData(
                      0, 0, canvas.width, canvas.height).data;
                    let lit = 0;
                    for (let i = 3; i < data.length; i += 4) if (data[i] > 12) lit += 1;
                    return {image: canvas.toDataURL(), coverage: lit / (canvas.width * canvas.height)};
                  };
                  return {
                    key: scene.key,
                    opening: capture(.5, 1.37),
                    moving: capture(1.2, 1.73),
                    mature: capture(60, 1.37),
                    matureMoving: capture(120, 1.73),
                    running: scene.running,
                  };
                }""")
                self.assertEqual(frames["key"], key)
                self.assertTrue(frames["running"], "charge animation stopped")
                for frame in ("opening", "moving", "mature", "matureMoving"):
                    self.assertGreater(frames[frame]["coverage"], .01, frame)
                self.assertNotEqual(frames["opening"]["image"], frames["moving"]["image"])
                # Charge is a continuing state, not a timer that empties at an
                # invented deadline while waiting for the next journal event.
                self.assertNotEqual(frames["mature"]["image"], frames["matureMoving"]["image"])
                opening_frames[key] = frames["opening"]["image"]

                self.render(page, hud_state(label), reduced=True)
                self.assertFalse(page.evaluate("navigationScene.running"))
                self.assertGreater(page.evaluate(LIT_PIXELS, "deck-canvas"), .01)
                still = page.evaluate("document.getElementById('deck-canvas').toDataURL()")
                page.wait_for_timeout(120)
                self.assertEqual(page.evaluate("document.getElementById('deck-canvas').toDataURL()"), still)
                reduced_stills[key] = still

        self.assertNotEqual(opening_frames["fsd_charge"], opening_frames["hyper_charge"])
        self.assertNotEqual(reduced_stills["fsd_charge"], reduced_stills["hyper_charge"])

    def test_surface_vehicles_have_distinct_living_scenes(self):
        page = self.open()
        frames = {}
        for label in ("SRV", "SCARAB", "SCORPION", "RHINO", "NOMAD"):
            with self.subTest(label=label):
                state = hud_state(label)
                state["color"] = "#ef8938"
                self.render(page, state)
                first = self.controlled_frame(page, 1.37)
                second = self.controlled_frame(page, 2.17)
                self.assertGreater(first["coverage"], .01, "an empty vehicle deck")
                self.assertNotEqual(first["deck"], second["deck"], "vehicle scene stopped")
                frames[label] = first["deck"]
        # SRV is the generic Scarab presentation; named vehicle types each
        # need their own recognizable deck motion and silhouette.
        for left, right in combinations(("SCARAB", "SCORPION", "RHINO", "NOMAD"), 2):
            with self.subTest(left=left, right=right):
                self.assertNotEqual(frames[left], frames[right])

    def test_station_and_carrier_phases_have_distinct_scenes(self):
        page = self.open()
        labels = ("STATION", "STATION VICINITY", "CARRIER VICINITY",
                  "CARRIER PREPARING", "CARRIER LOCKDOWN", "CARRIER TRANSIT",
                  "CARRIER ARRIVAL", "CARRIER DECK")
        frames, later = {}, {}
        for label in labels:
            with self.subTest(label=label):
                state = hud_state(label)
                state["color"] = "#ef8938"
                self.render(page, state)
                first = self.controlled_frame(page, 1.37, age=.8 if label == "CARRIER ARRIVAL" else 8)
                second = self.controlled_frame(page, 2.17, age=.8 if label == "CARRIER ARRIVAL" else 8)
                frames[label] = first
                later[label] = second
                self.assertGreater(first["coverage"], .01, "an empty station/carrier deck")
                if label == "STATION":
                    # A settled port no longer sends approach traffic past the pilot.
                    self.assertTrue(first["lane"] == second["lane"],
                                    "station approach lane kept moving after settling")
                else:
                    self.assertNotEqual(first["deck"], second["deck"], "scene stopped")
        for left, right in combinations(labels, 2):
            with self.subTest(left=left, right=right):
                self.assertNotEqual(frames[left]["deck"], frames[right]["deck"])
        self.assertNotEqual(frames["STATION VICINITY"]["lane"],
                            later["STATION VICINITY"]["lane"],
                            "station vicinity lost its approach motion")

    def test_new_vehicle_and_port_scenes_hold_reduced_motion_stills(self):
        page = self.open()
        for label in ("SRV", "SCARAB", "SCORPION", "RHINO", "NOMAD", "STATION",
                      "STATION VICINITY", "CARRIER VICINITY", "CARRIER PREPARING",
                      "CARRIER LOCKDOWN", "CARRIER TRANSIT", "CARRIER ARRIVAL", "CARRIER DECK"):
            with self.subTest(label=label):
                self.render(page, hud_state(label), reduced=True)
                self.assertFalse(page.evaluate("navigationScene.running"))
                self.assertGreater(page.evaluate(LIT_PIXELS, "deck-canvas"), .01)
                still = page.evaluate("document.getElementById('deck-canvas').toDataURL()")
                page.wait_for_timeout(90)
                self.assertEqual(page.evaluate("document.getElementById('deck-canvas').toDataURL()"), still)

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
        # Back to 100%: the app shrinks the window with the text (the HUD
        # fits whatever window it has, 5.5.2.7).
        page.set_viewport_size({"width": 500, "height": 326})
        self.render(page, hud_state("SUPERCRUISE"), scale=1)
        backing, css, ratio = page.evaluate("""() => {
          const canvas = document.getElementById('deck-canvas');
          return [canvas.width, canvas.clientWidth, devicePixelRatio];
        }""")
        self.assertAlmostEqual(backing, css * ratio, delta=1)

    LIT = """() => {
      const canvas = document.getElementById('deck-canvas');
      const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let lit = 0;
      for (let index = 3; index < data.length; index += 4) if (data[index] > 12) lit += 1;
      return lit / (canvas.width * canvas.height);
    }"""

    def scene_render(self, page, label, mode):
        snapshot = hud_snapshot(hud_state(label), reduced=False)
        snapshot["effects"]["scene"] = mode
        page.evaluate("snapshot => render(snapshot)", snapshot)

    def test_still_hologram_moves_only_when_the_state_changes(self):
        """5.5.3 Hologram: Still (Overlay Studio, for low-end PCs) holds each
        state's settled scene and draws only while a change re-projects it."""
        page = self.open()
        self.scene_render(page, "SUPERCRUISE", "still")
        self.assertFalse(page.evaluate("navigationScene.running"), "no frames at rest")
        self.assertTrue(page.evaluate("document.querySelector('.hud').classList.contains('scene-still')"))
        self.assertGreater(page.evaluate(self.LIT), .002, "the settled scene is on screen")
        before = self.frames(page)
        page.wait_for_timeout(500)
        self.assertEqual(self.frames(page), before)
        # A state change re-projects the hologram, then it settles again.
        self.scene_render(page, "HYPERSPACE", "still")
        self.assertTrue(page.evaluate("navigationScene.running"))
        page.wait_for_timeout(900)
        self.assertFalse(page.evaluate("navigationScene.running"))
        self.assertGreater(self.frames(page), before, "the change animated")
        self.assertEqual(page.evaluate("navigationScene.state.key"), "hyperspace")
        self.assertGreater(page.evaluate(self.LIT), .002)
        settled = self.frames(page)
        page.wait_for_timeout(500)
        self.assertEqual(self.frames(page), settled, "and then draws nothing")

    def test_hologram_off_draws_nothing_and_full_comes_back(self):
        page = self.open()
        self.scene_render(page, "SUPERCRUISE", "off")
        self.assertFalse(page.evaluate("navigationScene.running"))
        self.assertTrue(page.evaluate("document.querySelector('.hud').classList.contains('scene-off')"))
        self.assertEqual(page.evaluate(self.LIT), 0)
        self.scene_render(page, "HYPERSPACE", "off")
        self.assertFalse(page.evaluate("navigationScene.running"))
        self.scene_render(page, "HYPERSPACE", "full")
        self.assertTrue(page.evaluate("navigationScene.running"))
        page.wait_for_timeout(200)
        self.assertGreater(page.evaluate(self.LIT), .002)

    def test_scenes_are_cheap_to_draw(self):
        page = self.open()
        worst = []
        for label in ("ASTEROID FIELD", "HYPERSPACE", "SCO OVERCHARGE", "FSD CHARGE",
                      "HYPER CHARGE", "SETTLEMENT", "FSS", "SCARAB", "SCORPION",
                      "RHINO", "NOMAD", "STATION", "STATION VICINITY",
                      "CARRIER VICINITY", "CARRIER PREPARING", "CARRIER LOCKDOWN",
                      "CARRIER TRANSIT", "CARRIER ARRIVAL", "CARRIER DECK"):
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
