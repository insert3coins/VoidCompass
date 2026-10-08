"""The journal heartbeat is a HAL 9000-style orb that watches every event.

Python classifies each journal event (family, tone, effect, weight) and keeps
the recent ones with a sequence number; the page draws them. These tests hold
both halves to the design: no event is ignored, every effect the classifier
can name has a painter, a burst shows as a stream of motes with only the
strongest events playing full effects, danger turns the iris red and fades,
a quiet feed keeps the eye lit, and reduced motion paints still frames.
"""

from pathlib import Path
from types import SimpleNamespace
import re
import unittest
from urllib.parse import urlsplit

from voidcompass.core import config as config_module
from voidcompass.core.application_runtime import ApplicationRuntime
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays import heartbeat_events
from voidcompass.overlays.heartbeat_events import EFFECTS, TONES, classify
from voidcompass.overlays.heartbeat_hud import EYE_COLORS, ORB_SIZES, HeartbeatHUD
from voidcompass.overlays.html_heartbeat_overlay import HtmlHeartbeatBridge


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

THEME = {"bg": "#070b10", "panel": "#0d141c", "border": "#243746", "text": "#d8e6ee",
         "muted": "#7d93a3", "accent": "#00d1ff", "orange": "#ff7a18", "green": "#4ee59b",
         "yellow": "#ffd54a", "red": "#ff6075"}


class JournalClassificationTests(unittest.TestCase):
    def test_every_listed_event_names_a_real_tone_and_effect(self):
        specs = list(heartbeat_events._EVENTS.items()) + [
            (prefix, spec) for prefix, spec in heartbeat_events._PREFIXES
        ] + [("default", heartbeat_events._DEFAULT)]
        for name, (family, tone, effect, weight) in specs:
            with self.subTest(name):
                self.assertIn(tone, TONES)
                self.assertIn(effect, EFFECTS)
                self.assertTrue(family)
                self.assertTrue(0 < weight <= 1)

    def test_no_journal_event_is_ignored(self):
        # A future Frontier event still reaches the orb as a quiet pulse.
        self.assertEqual(classify("SomeFutureEvent"), {
            "event": "SomeFutureEvent", "family": "log", "tone": "muted",
            "effect": "pulse", "weight": .15, "gaze": "centre", "rare": False})
        # Whole event groups are covered by their prefix.
        self.assertEqual(classify("CarrierNewService")["family"], "carrier")
        self.assertEqual(classify("ColonisationConstructionDepot")["effect"], "gather")
        self.assertEqual(classify("SquadronPromotion")["family"], "comms")
        self.assertEqual(classify("")["event"], "Journal")

    def test_event_fields_refine_what_the_orb_does(self):
        self.assertEqual(classify("ShieldState", {"ShieldsUp": False})["effect"], "breach")
        self.assertEqual(classify("ShieldState", {"ShieldsUp": True})["tone"], "green")
        self.assertEqual(classify("StartJump", {"JumpType": "Hyperspace"})["effect"], "charge")
        self.assertEqual(classify("StartJump", {"JumpType": "Supercruise"})["effect"], "cruise")
        self.assertEqual(classify("Music", {"MusicTrack": "Combat_Dogfight"})["tone"], "red")
        self.assertEqual(classify("Music", {"MusicTrack": "MainMenu"})["effect"], "sleep")
        self.assertEqual(classify("Music", {"MusicTrack": "Exploration"})["effect"], "tick")
        self.assertGreater(classify("ReceiveText", {"Channel": "player"})["weight"],
                           classify("ReceiveText", {"Channel": "npc"})["weight"])
        self.assertEqual(classify("ShipTargeted", {"TargetLocked": False})["effect"], "tick")
        self.assertGreater(classify("CodexEntry", {"IsNewEntry": True})["weight"],
                           classify("CodexEntry", {})["weight"])

    def test_the_session_wakes_and_sleeps_the_orb(self):
        self.assertEqual(classify("LoadGame")["effect"], "wake")
        self.assertEqual(classify("Shutdown")["effect"], "sleep")
        self.assertEqual(classify("Died")["effect"], "die")
        self.assertEqual(classify("Resurrect")["effect"], "wake")


class HeartbeatModelTests(unittest.TestCase):
    def setUp(self):
        self.root = ApplicationRuntime()
        self.addCleanup(self.root.close)

    def hud(self, **config):
        hud = HeartbeatHUD(self.root, {"heartbeat_hud_x": 20, "heartbeat_hud_y": 20, **config})
        self.addCleanup(hud.destroy)
        return hud

    def test_journal_events_are_kept_with_sequence_and_status_writes_counted(self):
        hud = self.hud()
        for index in range(30):
            hud.pulse("journal", "FSSSignalDiscovered" if index % 2 else "Scan", "SUPERCRUISE")
        hud.pulse("journal", "ShieldState", "SUPERCRUISE", {"ShieldsUp": True})
        hud.pulse("status", "STATUS", "SUPERCRUISE")
        hud.pulse("status", "STATUS", "SUPERCRUISE")
        model = hud._html_render_model
        events = model["events"]
        # Enough history to catch up a burst between two polls, no more.
        self.assertEqual(len(events), 24)
        self.assertEqual([event["seq"] for event in events], list(range(8, 32)))
        self.assertEqual(events[-1], {"seq": 31, "event": "ShieldState", "family": "danger",
                                      "tone": "green", "effect": "clear", "weight": .6,
                                      "gaze": "side", "rare": False})
        self.assertEqual(model["status_seq"], 2)
        # The dashboard's own heartbeat lamp still reads these.
        self.assertEqual((model["pulse_id"], model["activity"], model["state"]), (33, "STATUS", "SUPERCRUISE"))
        self.assertFalse(model["stalled"])
        self.assertEqual(model["orb"], {"size": 54, "eye": "theme", "liveliness": "standard", "idle": True})

    def test_orb_settings_are_sanitised(self):
        self.assertEqual(self.hud(heartbeat_orb_size=96, heartbeat_eye_color="HAL")._html_render_model["orb"],
                         {"size": 96, "eye": "hal", "liveliness": "standard", "idle": True})
        self.assertEqual(self.hud(heartbeat_orb_size="60", heartbeat_eye_color="blue",
                                  heartbeat_liveliness="frantic", heartbeat_idle_motion=False)._html_render_model["orb"],
                         {"size": 54, "eye": "theme", "liveliness": "standard", "idle": False})

    def test_window_is_the_orb_square(self):
        bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
        for size in ORB_SIZES:
            bridge.config = {"heartbeat_orb_size": size}
            self.assertEqual(bridge._dimensions(), (size, size))


class _Studio(HtmlOverlayStudioMixin):
    def __init__(self):
        self.config = {"heartbeat_orb_size": 54, "heartbeat_eye_color": "theme", "survey_spotlight_threshold": 12}
        self.applied = 0
        self.heartbeat_hud = SimpleNamespace(apply_settings=self._applied)

    def _applied(self):
        self.applied += 1

    def _persist_config(self):
        pass

    def update_hud(self):
        pass

    def _schedule_html_dashboard_publish(self, **kwargs):
        pass


class HeartbeatSettingsTests(unittest.TestCase):
    def test_studio_saves_size_and_eye_one_at_a_time(self):
        studio = _Studio()
        self.assertTrue(studio._html_overlay_settings_save({"heartbeat_orb_size": "72"}))
        self.assertEqual(studio.config["heartbeat_orb_size"], 72)
        self.assertEqual(studio.config["heartbeat_eye_color"], "theme")
        studio._html_overlay_settings_save({"heartbeat_orb_size": "60"})
        self.assertEqual(studio.config["heartbeat_orb_size"], 72, "an unknown size keeps the current one")
        studio._html_overlay_settings_save({"heartbeat_eye_color": "HAL"})
        self.assertEqual(studio.config["heartbeat_eye_color"], "hal")
        studio._html_overlay_settings_save({"heartbeat_eye_color": "blue"})
        self.assertEqual(studio.config["heartbeat_eye_color"], "theme")
        self.assertEqual(studio.config["survey_spotlight_threshold"], 12)
        self.assertEqual(studio.applied, 4, "the orb picks each change up live")

    def test_orb_settings_follow_the_commander_profile(self):
        self.assertIn("heartbeat_orb_size", config_module.PROFILE_VALUE_SETTINGS)
        self.assertIn("heartbeat_eye_color", config_module.PROFILE_TEXT_SETTINGS)

    def test_studio_inspector_offers_exactly_the_supported_choices(self):
        html = (WEB / "dashboard" / "index.html").read_text(encoding="utf-8")
        section = re.search(r'<section data-studio-settings="heartbeat_hud">(.*?)</section>', html, re.S)
        self.assertIsNotNone(section)
        size = re.search(r'data-studio-setting="heartbeat_orb_size">(.*?)</select>', section.group(1), re.S)
        eye = re.search(r'data-studio-setting="heartbeat_eye_color">(.*?)</select>', section.group(1), re.S)
        self.assertEqual(tuple(int(value) for value in re.findall(r'value="(\d+)"', size.group(1))), ORB_SIZES)
        self.assertEqual(tuple(re.findall(r'value="([a-z]+)"', eye.group(1))), EYE_COLORS)


STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderHeartbeat = options.render; return {rerender() {}}; }};")


def event(seq, name, tone="accent", effect="pulse", weight=.5):
    return {"seq": seq, "event": name, "family": "x", "tone": tone, "effect": effect, "weight": weight}


def snapshot(events=(), status=0, stalled=False, eye="theme", reduced=False, crt=True):
    return {"theme": THEME, "effects": {"crt": crt, "reduced_motion": reduced},
            "heartbeat": {"events": list(events), "status_seq": status, "stalled": stalled,
                          "orb": {"size": 72, "eye": eye}}}


class HeartbeatOrbBrowserTests(unittest.TestCase):
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

    def open(self, size=72):
        page = self.browser.new_page(viewport={"width": size, "height": size})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        self.addCleanup(lambda: self.assertEqual(errors, []))

        def serve(route):
            path = WEB / urlsplit(route.request.url).path.lstrip("/")
            if not path.is_file():
                route.fulfill(status=404, body="")
            elif path.name == "overlay-client.js":
                route.fulfill(content_type="application/javascript",
                              body=path.read_text(encoding="utf-8") + STUB)
            else:
                route.fulfill(path=str(path))

        page.route("http://orb.test/**", serve)
        page.goto("http://orb.test/heartbeat/index.html")
        return page

    def render(self, page, data):
        page.evaluate("data => renderHeartbeat(data)", data)
        return page.evaluate("heartbeatOrb.state()")

    def lit(self, page, x, y):
        """Brightest channel of the canvas pixel at CSS (x, y)."""
        return page.evaluate("""([x, y]) => {
          const canvas = document.getElementById('orb');
          const ratio = canvas.width / canvas.clientWidth;
          const pixel = canvas.getContext('2d').getImageData(Math.round(x * ratio), Math.round(y * ratio), 1, 1).data;
          return {max: Math.max(pixel[0], pixel[1], pixel[2]), r: pixel[0], g: pixel[1], b: pixel[2], a: pixel[3]};
        }""", [x, y])

    def test_every_effect_the_classifier_names_has_a_painter(self):
        page = self.open()
        painters = set(page.evaluate("HeartbeatOrb.EFFECTS"))
        self.assertEqual(painters, set(EFFECTS) - {"tick"}, "tick is a mote only")
        self.render(page, snapshot())
        # Every painter draws through its whole run without an error.
        page.evaluate("""effects => {
          const orb = heartbeatOrb;
          for (const effect of effects) {
            orb.effects = [];
            orb.play({effect, tone: 'red', weight: 1}, 0);
            for (const p of [0, .1, .3, .5, .7, .9, 1]) orb.draw(orb.effects[0].ms * p);
          }
          orb.effects = [];
        }""", sorted(painters))

    def test_first_look_is_history_and_the_eye_opens(self):
        page = self.open()
        state = self.render(page, snapshot([event(1, "LoadGame", effect="wake", weight=1),
                                            event(2, "FSDJump", effect="warp", weight=.95)]))
        self.assertEqual(state["lastSeq"], 2)
        self.assertEqual(state["effects"], ["wake"])
        self.assertEqual(state["motes"], 0, "old events are not replayed as news")
        self.assertTrue(state["running"])
        self.assertEqual(state["size"], 72)

    def test_a_burst_streams_motes_and_plays_only_the_strongest(self):
        page = self.open()
        self.render(page, snapshot())
        burst = [event(1, "Music", "muted", "tick", .05), event(2, "FSDJump", "accent", "warp", .95)]
        burst += [event(3 + index, "FSSSignalDiscovered", "accent", "signal", .25) for index in range(14)]
        burst += [event(17, "ReceiveText", "accent", "speak", .25)]
        state = self.render(page, snapshot(burst))
        self.assertEqual(state["lastSeq"], 17)
        self.assertEqual(state["motes"], 14, "every event falls in, up to the per-update cap")
        self.assertIn("warp", state["effects"])
        self.assertLessEqual(len(state["effects"]), 3)
        self.assertEqual(state["lastEvent"], "ReceiveText")
        self.assertEqual(page.get_attribute("#heartbeat", "aria-label"), "Journal watcher: ReceiveText")
        # The same snapshot again is not news.
        self.assertEqual(self.render(page, snapshot(burst))["motes"], 14)

    def test_danger_turns_the_iris_red_then_it_settles(self):
        page = self.open()
        rest = self.render(page, snapshot())
        self.assertEqual((rest["tint"], rest["base"]), (THEME["accent"], THEME["accent"]))
        danger = self.render(page, snapshot([event(1, "Interdicted", "red", "alarm", 1.0),
                                             event(2, "UnderAttack", "red", "alarm", .85)]))
        self.assertEqual(danger["tint"], THEME["red"])
        self.assertIn("alarm", danger["effects"])
        page.evaluate("heartbeatOrb.decay(performance.now() + 120000)")
        self.assertEqual(page.evaluate("heartbeatOrb.state().tint"), THEME["accent"])

    def test_hal_eye_rests_red(self):
        page = self.open()
        state = self.render(page, snapshot(eye="hal"))
        self.assertEqual((state["base"], state["tint"]), (THEME["red"], THEME["red"]))

    def test_status_writes_blip_the_bezel_without_motes(self):
        page = self.open()
        self.render(page, snapshot(status=1))
        state = self.render(page, snapshot(status=2))
        self.assertEqual((state["blips"], state["motes"]), (1, 0))

    def test_shutdown_sleeps_the_eye_and_the_next_session_wakes_it(self):
        page = self.open()
        self.render(page, snapshot())
        state = self.render(page, snapshot([event(1, "Shutdown", "muted", "sleep", 1.0)]))
        self.assertIn("sleep", state["effects"])
        page.evaluate("heartbeatOrb.advance(performance.now() + 5000)")
        self.assertTrue(page.evaluate("heartbeatOrb.state().asleep"))
        state = self.render(page, snapshot([event(1, "Shutdown", "muted", "sleep", 1.0),
                                            event(2, "LoadGame", "accent", "wake", 1.0)]))
        self.assertFalse(state["asleep"])
        self.assertIn("wake", state["effects"])

    def test_quiet_feed_holds_still_but_keeps_the_eye_lit(self):
        page = self.open()
        self.render(page, snapshot([event(1, "Scan")]))
        self.render(page, snapshot([event(1, "Scan"), event(2, "FSDJump", effect="warp", weight=.95)]))
        state = self.render(page, snapshot([event(1, "Scan"), event(2, "FSDJump")], stalled=True))
        self.assertEqual((state["effects"], state["motes"], state["stalled"]), ([], 0, True))
        page.wait_for_timeout(250)
        spin = page.evaluate("heartbeatOrb.spin")
        page.wait_for_timeout(300)
        self.assertEqual(page.evaluate("heartbeatOrb.spin"), spin, "the galaxy stops turning")
        self.assertGreater(self.lit(page, 36, 36)["max"], 150, "the pupil stays lit")
        # One small red lamp on the bezel, lower right.
        lamp = self.lit(page, 36 + .885 * 36 * .7071, 36 + .885 * 36 * .7071)
        self.assertGreater(lamp["r"], lamp["b"])
        self.assertGreater(lamp["r"], 120)

    def test_reduced_motion_paints_still_frames_with_the_current_mood(self):
        page = self.open()
        self.render(page, snapshot(reduced=True))
        state = self.render(page, snapshot([event(1, "HullDamage", "red", "alarm", .9)], reduced=True))
        self.assertFalse(state["running"])
        self.assertEqual((state["effects"], state["motes"]), ([], 0))
        self.assertNotEqual(state["tint"], THEME["accent"], "the mood still changes")
        self.assertGreater(self.lit(page, 36, 36)["max"], 150)
        self.assertEqual(page.evaluate("document.getAnimations().length"), 0)

    def test_orb_fills_each_supported_size(self):
        for size in ORB_SIZES:
            with self.subTest(size=size):
                page = self.open(size)
                state = self.render(page, snapshot())
                self.assertEqual(state["size"], size)
                # Past the eye opening on first load.
                page.evaluate("""() => { const later = performance.now() + 4000;
                  heartbeatOrb.advance(later); heartbeatOrb.draw(later); }""")
                self.assertGreater(self.lit(page, size / 2, size / 2)["max"], 150)
                self.assertEqual(self.lit(page, 1, 1)["a"], 0, "corners stay transparent")


if __name__ == "__main__":
    unittest.main()
