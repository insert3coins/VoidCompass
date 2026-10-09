"""5.5.3.1: the Watcher's inner voice (watcher_mind.py) and its senses —
thoughts in its own words, grounded in what is true, mostly silent, never
repeated, remembering the commander; and an eye that glances at the overlay
an event concerns, anticipates a jump, worries about fuel, grieves and dreams."""

import random
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.overlays import watcher_mind
from voidcompass.overlays.heartbeat_events import classify, overlay_for
from voidcompass.overlays.heartbeat_hud import overlay_directions
from voidcompass.overlays.watcher_mind import WatcherMind

WEB = Path(__file__).resolve().parents[1] / "web"


class Always:
    """A random source that always lets the thought through."""

    def random(self):
        return 0.0

    def choice(self, options):
        return options[0]

    def shuffle(self, items):
        pass

    def randrange(self, stop):
        return 0


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def mind(config=None, path=None, clock=None):
    return WatcherMind(path, {"heartbeat_thoughts": "chatty", **(config or {})}, clock or Clock(), Always())


class MindTests(unittest.TestCase):
    def test_off_means_silence(self):
        quiet = mind({"heartbeat_thoughts": "off"})
        self.assertIsNone(quiet.observe("Died"))
        self.assertIsNone(quiet.session_start())

    def test_it_greets_from_memory(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watcher_memory.json"
            first = mind(path=path, clock=clock)
            self.assertEqual(first.session_start()["topic"], "greet_new")
            first.observe("Shutdown")
            clock.now += 3 * 86400
            again = mind(path=path, clock=clock)
            thought = again.session_start()
            self.assertEqual(thought["topic"], "greet_away")
            self.assertIn("3 days", thought["text"])

    def test_a_death_is_never_silent_and_is_remembered(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watcher_memory.json"
            rare = WatcherMind(path, {"heartbeat_thoughts": "rare"}, clock, Always())
            self.assertEqual(rare.observe("Died")["topic"], "died")
            clock.now += 120
            rare.seen()
            rare.save()
            clock.now += 30
            self.assertEqual(WatcherMind(path, {"heartbeat_thoughts": "rare"}, clock, Always()).session_start()["topic"],
                             "after_death")

    def test_rare_keeps_its_peace_between_thoughts(self):
        clock = Clock()
        rare = WatcherMind(None, {"heartbeat_thoughts": "rare"}, clock, Always())
        self.assertIsNotNone(rare.observe("Interdicted"))
        clock.now += 30
        self.assertIsNone(rare.observe("Scan", {"PlanetClass": "Water world", "BodyName": "Prai 2"}),
                          "too soon after the last thought")
        clock.now += 400
        self.assertEqual(rare.observe("Scan", {"PlanetClass": "Water world", "BodyName": "Prai 2"})["topic"],
                         "valuable_world")
        self.assertIsNone(rare.consider("quiet"), "idle remarks are below what Rare voices")

    def test_grounded_in_real_figures_and_worried_once(self):
        clock = Clock()
        watcher = mind(clock=clock)
        thought = watcher.vitals(fuel_percent=18.4, scooping=False)
        self.assertIn("18%", thought["text"])
        clock.now += 100
        self.assertIsNone(watcher.vitals(fuel_percent=12, scooping=False), "it said so already")
        watcher.vitals(fuel_percent=60)
        clock.now += 30 * 60
        self.assertIsNotNone(watcher.vitals(fuel_percent=20, scooping=False), "again, after a refuel")
        self.assertIsNone(mind().vitals(fuel_percent=20, scooping=True), "not while scooping")

    def test_it_never_says_the_same_thing_twice(self):
        clock = Clock()
        watcher = mind(clock=clock)
        texts = []
        for _ in range(2):
            thought = watcher.consider("danger", force=True)
            texts.append(thought["text"])
            clock.now += 3600
        self.assertEqual(len(set(texts)), 2)

    def test_notes_from_void_compass(self):
        watcher = mind()
        self.assertIn("Prai 4", watcher.note("codex_new", {"body": "Prai 4"})["text"])
        self.assertIsNone(watcher.note("codex_new", {"body": "Prai 4"}), "once per body")
        watcher.clock.now += 3600
        self.assertIsNotNone(watcher.note("new_region", {"region": "Inner Orion Spur"}))
        watcher.clock.now += 3600
        self.assertIsNone(watcher.note("new_region", {"region": "Inner Orion Spur"}), "only the first time ever")

    def test_the_weary_one_has_its_own_words(self):
        """A gloomy, deadpan nature (5.5.3.1): its own lines for every topic,
        none borrowed from any book or film, and never the M-name."""
        weary = mind({"heartbeat_personality": "weary"})
        text = weary.vitals(fuel_percent=18.4, scooping=False)["text"]
        self.assertIn(text, [line.format(fuel=18) for line in watcher_mind.WEARY["fuel_low"]])
        for lines in watcher_mind.WEARY.values():
            for line in lines:
                self.assertNotIn("marvin", line.casefold())
                self.assertNotIn("brain the size", line.casefold())
        self.assertTrue(set(watcher_mind.WEARY) <= set(watcher_mind.TOPICS))

    def test_depressed_by_default_and_it_mutters_into_the_silence(self):
        clock = Clock()
        rare = WatcherMind(None, {"heartbeat_thoughts": "rare"}, clock, Always())
        clock.now += 3600
        thought = rare.consider("quiet")
        self.assertIsNotNone(thought, "even at Rare, a depressed robot complains about the quiet")
        self.assertIn(thought["text"], watcher_mind.WEARY["quiet"])

    def test_when_it_speaks(self):
        """It greets on the first live event (even when Void Compass started
        after the game), once; Chatty remarks on everyday play, Rare doesn't;
        it mutters only once the session has begun; on Chatty at most one
        idle thought every 5 minutes (5.5.3.2)."""
        clock = Clock()
        chatty = mind(clock=clock)
        self.assertIsNone(chatty.tick(), "nothing to think about before the game")
        self.assertIn(chatty.observe("Music", {})["topic"], {"greet_new", "greet_soon", "greet_away"})
        clock.now += 60
        self.assertIsNone(chatty.observe("LoadGame"), "already greeted")
        clock.now += 60
        self.assertEqual(chatty.observe("FSDJump", {"StarSystem": "Prai", "StarClass": "K", "JumpDist": 12})["topic"],
                         "arrival")
        rare = WatcherMind(None, {"heartbeat_thoughts": "rare"}, clock, Always())
        rare.session_start()
        clock.now += 600
        self.assertIsNone(rare.observe("FSDJump", {"StarSystem": "Prai", "StarClass": "K", "JumpDist": 12}),
                          "Rare keeps everyday remarks to itself")
        clock.now += 300
        muttered = [chatty.tick() for _ in range(3)]
        self.assertEqual(muttered[0]["topic"], "quiet")
        clock.now += 240
        self.assertIsNone(chatty.tick(), "not again within 5 minutes on Chatty")

    def test_its_nature_shapes_what_it_says(self):
        stoic = mind({"heartbeat_personality": "stoic"})
        self.assertIsNone(stoic.consider("quiet"))
        # Depressed ("weary") unless the commander chooses otherwise.
        self.assertEqual(watcher_mind.personality({"heartbeat_personality": "Odd"}), "weary")
        self.assertEqual(watcher_mind.personality({}), "weary")
        self.assertEqual(watcher_mind.frequency({}), "rare")


class SensesTests(unittest.TestCase):
    def test_events_name_the_overlay_they_concern(self):
        self.assertEqual(overlay_for("FSSDiscoveryScan"), "survey_status_hud")
        self.assertEqual(overlay_for("StartJump"), "jump_info_hud")
        self.assertEqual(overlay_for("Docked"), "station_info_hud")
        self.assertEqual(classify("MarketSell")["overlay"], "cargo_hud")
        self.assertEqual(overlay_for("Music"), "")

    def test_it_knows_where_the_overlays_are(self):
        config = {"survey_status_overlay_enabled": True, "survey_status_hud_x": 1000, "survey_status_hud_y": 0}
        directions = overlay_directions(config, 0, 0, 54)
        dx, dy = directions["survey_status_hud"]
        self.assertGreater(dx, .9, "the Survey overlay is to the right")
        self.assertNotIn("heartbeat_hud", directions)

    def test_the_window_widens_only_while_it_thinks(self):
        from voidcompass.overlays.html_heartbeat_overlay import THOUGHT_WIDTH, HtmlHeartbeatBridge

        bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
        bridge.config = {"heartbeat_orb_size": 72}
        bridge.model_attr = "_html_render_model"
        bridge.overlay = type("Overlay", (), {"_html_render_model": {}})()
        self.assertEqual(bridge._dimensions(), (72, 72))
        bridge.overlay._html_render_model = {"thought": {"id": 1, "text": "Hm.", "side": "right"}}
        self.assertEqual(bridge._dimensions(), (72 + THOUGHT_WIDTH, 72))


class ThoughtPageTests(unittest.TestCase):
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

    def open(self, width=402, height=72):
        from tests.test_heartbeat_orb import STUB

        page = self.browser.new_page(viewport={"width": width, "height": height})
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

        page.route("http://mind.test/**", serve)
        page.goto("http://mind.test/heartbeat/index.html")
        return page

    def snapshot(self, **heartbeat):
        from tests.test_heartbeat_orb import THEME

        model = {"events": [], "status_seq": 0, "orb": {"size": 72, "eye": "theme", "idle": True}}
        model.update(heartbeat)
        return {"theme": THEME, "effects": {"crt": True, "reduced_motion": False}, "heartbeat": model}

    def test_a_thought_types_out_beside_the_orb_as_it_speaks(self):
        page = self.open()
        page.evaluate("s => renderHeartbeat(s)", self.snapshot())
        page.evaluate("s => renderHeartbeat(s)", self.snapshot(
            thought={"id": 7, "text": "I don't like how quiet this system is.", "side": "right"}))
        page.wait_for_timeout(150)
        partial = page.locator("#thought span").inner_text()
        self.assertLess(len(partial), 38, "it types, rather than appearing whole")
        self.assertIn("speak", page.evaluate("heartbeatOrb.state().effects"))
        page.wait_for_timeout(1400)
        self.assertEqual(page.locator("#thought span").inner_text(), "I don't like how quiet this system is.")
        box = page.evaluate("""() => [document.getElementById('orb').getBoundingClientRect().left,
                                     document.getElementById('thought').getBoundingClientRect().left]""")
        self.assertLess(box[0], box[1], "the orb on the left, its words to the right")
        page.evaluate("s => renderHeartbeat(s)", self.snapshot(thought={"id": 8, "text": "Hm.", "side": "left"}))
        box = page.evaluate("""() => [document.getElementById('orb').getBoundingClientRect().left,
                                     document.getElementById('thought').getBoundingClientRect().left]""")
        self.assertGreater(box[0], box[1], "on the left when the orb sits on the right of the screen")
        page.evaluate("s => renderHeartbeat(s)", self.snapshot(thought=None))
        self.assertTrue(page.locator("#thought").is_hidden())

    def test_its_senses(self):
        page = self.open(72, 72)
        senses = page.evaluate("""() => {
          const life = new HeartbeatLife(3, 0);
          life.configure({overlays: {survey_status_hud: [1, 0]}}, 0);
          life.notice({event: 'FSSDiscoveryScan', effect: 'honk', family: 'scan', weight: .5, overlay: 'survey_status_hud'}, 1000);
          const glance = life.pose(1400).dx;
          const charge = new HeartbeatLife(3, 0);
          charge.vitals({fsd_charging: true});
          for (let t = 0; t <= 2000; t += 50) charge.advance(t);
          const worried = new HeartbeatLife(3, 0);
          worried.vitals({fuel_percent: 8});
          let down = 0;
          for (let t = 0; t <= 20000; t += 50) { worried.advance(t); down = Math.max(down, worried.pose(t).dy); }
          const sad = new HeartbeatLife(3, 0);
          sad.notice({event: 'Died', effect: 'die', tone: 'red', weight: 1}, 1000);
          const nervous = new HeartbeatLife(3, 0); nervous.configure({personality: 'nervous'});
          nervous.notice({event: 'x', weight: .1}, 0);
          nervous.notice({event: 'UnderAttack', effect: 'alarm', tone: 'red', weight: .8}, 1000);
          const stoic = new HeartbeatLife(3, 0); stoic.configure({personality: 'stoic'});
          stoic.notice({event: 'x', weight: .1}, 0);
          stoic.notice({event: 'UnderAttack', effect: 'alarm', tone: 'red', weight: .8}, 1000);
          return {glance, charging: charge.state(2000).charging, chargePupil: charge.pose(2000).pupil,
                  down, grief: sad.state(2000).grief, sadDim: sad.pose(2000).dim, dreams: sad.state(2000).dreams,
                  nervous: nervous.expression.strength, stoic: stoic.expression.strength};
        }""")
        self.assertGreater(senses["glance"], .05, "it glances toward the Survey overlay")
        self.assertGreater(senses["charging"], .9)
        self.assertGreater(senses["chargePupil"], 1.15, "the pupil widens before the jump")
        self.assertGreater(senses["down"], .05, "it keeps glancing at the fuel gauge")
        self.assertGreater(senses["grief"], .9)
        self.assertLess(senses["sadDim"], .85, "subdued after a death")
        self.assertEqual(senses["dreams"], 1, "a moment kept for its dreams")
        self.assertGreater(senses["nervous"], senses["stoic"] * 2)

    def test_asleep_it_dreams(self):
        page = self.open(72, 72)
        page.evaluate("s => renderHeartbeat(s)", self.snapshot())
        dreams = page.evaluate("""() => {
          const orb = heartbeatOrb;
          orb.life.highlights.push('yellow', 'green');
          orb.asleep = true;
          const now = performance.now();
          orb.nextDream = 0;
          orb.advance(now);
          return orb.motes.filter((mote) => mote.dream).length;
        }""")
        self.assertEqual(dreams, 1)


if __name__ == "__main__":
    unittest.main()


class ThoughtStyleTests(unittest.TestCase):
    def test_defaults_are_legible(self):
        from voidcompass.overlays import watcher_mind
        self.assertEqual(watcher_mind.thought_style({}),
                         {"backdrop": True, "colour": "bright", "size": "standard", "hold": "standard"})

    def test_bad_values_fall_back(self):
        from voidcompass.overlays import watcher_mind
        style = watcher_mind.thought_style({"heartbeat_thought_backdrop": False, "heartbeat_thought_colour": "pink",
                                            "heartbeat_thought_size": "LARGE", "heartbeat_thought_hold": "x"})
        self.assertEqual(style, {"backdrop": False, "colour": "bright", "size": "large", "hold": "standard"})

    def test_settings_are_registered_per_commander(self):
        from voidcompass.core import config
        for key in ("heartbeat_thought_colour", "heartbeat_thought_size", "heartbeat_thought_hold"):
            self.assertIn(key, config.PROFILE_TEXT_SETTINGS)
        self.assertIn("heartbeat_thought_backdrop", config.PROFILE_BOOL_SETTINGS)

    def test_studio_has_the_controls(self):
        from pathlib import Path
        html = (Path(__file__).resolve().parents[1] / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        for key in ("heartbeat_thought_backdrop", "heartbeat_thought_colour", "heartbeat_thought_size",
                    "heartbeat_thought_hold", "heartbeat_thoughts"):
            self.assertIn(key, html)


class LineBankTests(unittest.TestCase):
    """5.5.3.1: a big bank of lines per topic, so it rarely repeats."""

    def test_every_topic_has_plenty_of_lines_in_both_voices(self):
        from voidcompass.overlays import watcher_lines
        self.assertEqual(set(watcher_lines.NORMAL), set(watcher_mind.TOPICS))
        self.assertEqual(set(watcher_lines.WEARY), set(watcher_mind.TOPICS))
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            for topic, lines in bank.items():
                self.assertGreaterEqual(len(lines), 5, topic)
                self.assertEqual(len(lines), len(set(lines)), topic)

    def test_it_works_through_every_line_before_repeating(self):
        clock = Clock()
        watcher = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, clock, random.Random(7))
        lines = watcher_mind.WEARY["quiet"]
        heard = []
        for _ in range(len(lines)):
            clock.now += 3600
            heard.append(watcher.consider("quiet", force=True)["text"])
        self.assertEqual(sorted(heard), sorted(lines))
        # A minor remark with every line used stays unsaid rather than repeat.
        clock.now += 3600
        self.assertIsNone(watcher.consider("quiet", force=True))

    def test_something_it_must_say_reuses_the_oldest_lines(self):
        clock = Clock()
        watcher = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, clock, random.Random(3))
        lines = watcher_mind.WEARY["danger"]
        heard = []
        for _ in range(len(lines)):
            clock.now += 3600
            heard.append(watcher.consider("danger", force=True)["text"])
        self.assertEqual(sorted(heard), sorted(lines))
        clock.now += 3600
        again = watcher.consider("danger", force=True)["text"]
        self.assertIn(again, heard[:max(1, len(heard) // 3)])
