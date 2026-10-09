"""5.5.3.2: the Watcher's chatter has life (moods, corrections, second
beats, the rest of the app), and its eye acts it out."""

import random
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from voidcompass.overlays import watcher_lines
from voidcompass.overlays.watcher_idle import Surroundings
from voidcompass.overlays.watcher_mind import MOODS, TOPICS, WatcherMind, plain_text

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
NOON = datetime(2026, 10, 9, 12, 0).timestamp()


class Clock:
    def __init__(self, now=NOON):
        self.now = now

    def __call__(self):
        return self.now


class AliveTests(unittest.TestCase):
    def test_corrections_keep_the_final_word(self):
        self.assertEqual(plain_text("I [[love|tolerate]] this one."), "I tolerate this one.")
        self.assertEqual(plain_text("No markup."), "No markup.")
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            for lines in bank.values():
                for line in lines:
                    self.assertNotIn("[[", plain_text(line))

    def test_moods_name_real_topics(self):
        self.assertTrue(set(MOODS) <= set(TOPICS))
        self.assertTrue(set(MOODS.values()) <= {"pleased", "wary", "curious", "downcast"})

    def test_a_thought_carries_its_mood_and_script(self):
        watcher = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, Clock(), random.Random(2))
        thought = watcher.consider("green_giant", {"system": "Hatchooe"}, force=True)
        self.assertEqual(thought["mood"], "pleased")
        self.assertEqual(thought["text"], plain_text(thought["script"]))

    def test_a_second_beat_follows_now_and_then(self):
        clock = Clock()
        watcher = WatcherMind(None, {"heartbeat_thoughts": "chatty"}, clock, random.Random(1))
        beats = 0
        for _ in range(30):
            clock.now += 4000
            first = watcher.consider("quiet", force=True)
            if not first:
                continue
            clock.now += 7  # past the reading time, before it dissolves
            beat = watcher.follow_up()
            if beat:
                beats += 1
                self.assertEqual(beat["topic"], "afterthought")
                self.assertNotEqual(beat["id"], first["id"])
        self.assertGreater(beats, 0, "an afterthought now and then")
        self.assertLess(beats, 20, "but not every time")

    def test_it_notices_the_music_galnet_and_its_own_history(self):
        around = Surroundings()
        context = {"music": {"title": "Cosmic Dust", "artist": "Nyx"}, "galnet": "Thargoids sighted near Sol.",
                   "thoughts": 42, "sessions": 7, "deaths": 2}
        topics = dict(around.choices(NOON, random.Random(3), context))
        self.assertEqual(topics["idle_music"]["title"], "Cosmic Dust")
        self.assertEqual(topics["idle_galnet"]["headline"], "Thargoids sighted near Sol")
        self.assertEqual(topics["idle_self"]["count"], "42")
        self.assertEqual(topics["idle_deaths"]["times"], "twice")
        quiet = dict(around.choices(NOON, random.Random(3), {"thoughts": 3}))
        self.assertNotIn("idle_self", quiet, "not until it has said a fair amount")

    def test_older_memories_count_their_thoughts(self):
        import json, tempfile
        folder = Path(tempfile.mkdtemp())
        path = folder / "watcher_memory.json"
        path.write_text(json.dumps({"said": [["quiet:1a2b", 1], ["quiet", 1], ["idle", 1], ["arrival", 2]]}), encoding="utf-8")
        self.assertEqual(WatcherMind(path, {}).memory["thoughts"], 2)


STUB = ("\nwindow.VoidCompassOverlay = {...VoidCompassOverlay, startPolling: options => {"
        " window.renderHeartbeat = options.render; return {rerender() {}}; }};")
THEME = {"bg": "#070b10", "panel": "#0d141c", "border": "#243746", "text": "#d8e6ee",
         "muted": "#7d93a3", "accent": "#00d1ff", "orange": "#ff7a18", "green": "#4ee59b",
         "yellow": "#ffd54a", "red": "#ff6075"}


class AliveBrowserTests(unittest.TestCase):
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
        page = self.browser.new_page(viewport={"width": 96 + 330, "height": 96})
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

        page.route("http://orb.test/**", serve)
        page.goto("http://orb.test/heartbeat/index.html")
        return page

    def test_it_thinks_feels_then_types_and_corrects_itself(self):
        page = self.open()
        page.evaluate("""() => {
          window.__typed = [];
          new MutationObserver(() => window.__typed.push(document.querySelector('#thought span').textContent))
            .observe(document.querySelector('#thought span'), {childList: true, characterData: true, subtree: true});
        }""")
        page.evaluate("data => renderHeartbeat(data)", {
            "theme": THEME, "effects": {"crt": True, "reduced_motion": False},
            "heartbeat": {"events": [], "status_seq": 0, "orb": {"size": 96, "eye": "theme"}, "personality": "curious",
                          "thought": {"id": 1, "text": "I tolerate it.", "script": "I [[love|tolerate]] it.",
                                      "mood": "downcast", "side": "right", "style": {}}}})
        page.wait_for_timeout(300)
        life = page.evaluate("heartbeatOrb.life.state()")
        self.assertEqual(life["expression"], "downcast", "the eye shows how it feels")
        self.assertGreater(page.evaluate("heartbeatOrb.life.pose().aperture"), .3, "it thinks before it speaks")
        page.wait_for_timeout(3200)
        typed = page.evaluate("window.__typed")
        self.assertIn("I love", typed, "it typed the word it then thought better of")
        self.assertEqual(typed[-1], "I tolerate it.")
        self.assertIn("done", page.get_attribute("#thought", "class"))


if __name__ == "__main__":
    unittest.main()
