"""5.5.3.5: how the Watcher shows its words.

A heading over each thought says what kind it is (a memory and where it sits
in the story, an echo and what stirred it, or simply THE WATCHER); its story reads as
passages. Its words go on the side chosen in Overlay Studio (Auto, Left,
Right), swapping sides when they won't fit on the screen, and a tall thought
grows away from a screen edge instead of off it. The Watcher has its own text
size. Studio's card is the orb with an outline where its words go, not the
stretched window (which ran off the display). Its page lists the newest 100.
"""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_heartbeat_orb import STUB, THEME, WEB
from tests.test_overlay_studio_displays import _LiveSizeStudio
from tests.test_watcher_allin_5532 import mind
from voidcompass.core import config as config_module
from voidcompass.dashboard.html_dashboard import WATCHER_LOG_SHOWN, HtmlDashboardMixin
from voidcompass.dashboard.html_overlay_studio import HtmlOverlayStudioMixin
from voidcompass.overlays import watcher_lore
from voidcompass.overlays.heartbeat_hud import heartbeat_text_scale, place_thought
from voidcompass.overlays.html_heartbeat_overlay import HtmlHeartbeatBridge, thought_zone
from voidcompass.overlays.watcher_mind import thought_heading

SCREEN = (0, 0, 2560, 1400)  # a work area, taskbar off the bottom
HERE = "voidcompass.overlays.html_heartbeat_overlay"


class PlacementTests(unittest.TestCase):
    """place_thought(side, orb_x, orb_y, orb, words_width, window_height, bounds)."""

    def test_the_side_asked_for_when_it_fits(self):
        self.assertEqual(place_thought("right", 1000, 600, 54, 330, 80, SCREEN), ("right", 1000, 587))
        self.assertEqual(place_thought("left", 1000, 600, 54, 330, 80, SCREEN), ("left", 670, 587))

    def test_swaps_sides_at_a_screen_edge(self):
        side, x, _y = place_thought("right", 2400, 600, 54, 330, 80, SCREEN)
        self.assertEqual((side, x), ("left", 2070), "no room on the right: the words go left")
        side, x, _y = place_thought("left", 40, 600, 54, 330, 80, SCREEN)
        self.assertEqual((side, x), ("right", 40))

    def test_grows_away_from_the_top_and_bottom(self):
        _side, _x, y = place_thought("right", 1000, 0, 54, 330, 160, SCREEN)
        self.assertEqual(y, 0, "at the top it grows downward, onto the screen")
        _side, _x, y = place_thought("right", 1000, 1346, 54, 330, 160, SCREEN)
        self.assertEqual(y, 1400 - 160, "at the bottom it grows upward")
        _side, _x, y = place_thought("right", 1000, 600, 54, 330, 160, SCREEN)
        self.assertEqual(y, 600 - 53, "in the open, up and down alike")

    def test_the_window_always_holds_the_orb(self):
        # Taller than the whole screen: never shifted past the orb itself.
        _side, _x, y = place_thought("right", 1000, 30, 54, 330, 2000, SCREEN)
        self.assertLessEqual(y, 30)
        self.assertGreaterEqual(y + 2000, 30 + 54)

    def test_no_monitor_known_keeps_the_side(self):
        self.assertEqual(place_thought("left", 10, 10, 54, 330, 54, None), ("left", -320, 10))


class BridgeTests(unittest.TestCase):
    def bridge(self, config):
        bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
        bridge.config = {"heartbeat_orb_size": 54, "overlay_text_scale_percent": 100, **config}
        return bridge

    def payload(self, bridge, thought, x, y):
        with patch.object(HtmlHeartbeatBridge, "_thought", return_value=thought):
            width, height = bridge._dimensions()
            with patch("voidcompass.overlays.html_model_overlay.HtmlModelOverlayBridge._window_payload",
                       return_value={"x": x, "y": y, "width": width, "height": height}), \
                    patch(f"{HERE}.monitor_scale", return_value=1.0), \
                    patch(f"{HERE}.monitor_bounds", return_value=SCREEN):
                return HtmlHeartbeatBridge._window_payload(bridge), height

    def test_a_long_memory_at_the_top_right_stays_on_screen(self):
        words = max((row[2] for row in watcher_lore.FRAGMENTS), key=len)
        kind, heading = thought_heading("lore_fragment", words)
        thought = {"text": words, "kind": kind, "heading": heading, "side": "right", "style": {"size": "large"}}
        bridge = self.bridge({})
        payload, height = self.payload(bridge, thought, 2500, 0)
        self.assertGreater(height, 54)
        self.assertEqual(payload["y"], 0, "grew down, not off the top")
        self.assertLess(payload["x"], 2500, "the words went left")
        self.assertGreaterEqual(payload["x"], 0)
        self.assertEqual(bridge._thought_layout, {"side": "left", "orb_top": 0})

    def test_the_page_learns_where_the_orb_sits(self):
        thought = {"text": "x " * 200, "side": "right", "style": {}}
        bridge = self.bridge({})
        payload, height = self.payload(bridge, thought, 1000, 1346)
        self.assertEqual(payload["y"], 1400 - height)
        self.assertEqual(bridge._thought_layout["orb_top"], 1346 - payload["y"])

    def test_the_heading_and_the_rule_are_counted(self):
        words = "word " * 40
        plain = self.bridge({})._thought_height({"text": words, "style": {"heading": False}})
        headed = self.bridge({})._thought_height({"text": words, "style": {}})
        self.assertGreater(headed, plain, "a heading line on top")
        ruled = self.bridge({})._thought_height({"text": words * 2, "kind": "memory", "style": {}})
        self.assertGreaterEqual(ruled, self.bridge({})._thought_height({"text": words * 2, "style": {}}))

    def test_its_own_text_size(self):
        self.assertEqual(heartbeat_text_scale({"overlay_text_scale_percent": 120}), 1.2, "0 follows all overlays")
        self.assertEqual(heartbeat_text_scale({"overlay_text_scale_percent": 120,
                                               "heartbeat_text_scale_percent": 150}), 1.5)
        self.assertEqual(heartbeat_text_scale({"heartbeat_text_scale_percent": 999}), 2.0)
        bridge = self.bridge({"heartbeat_text_scale_percent": 150})
        self.assertEqual(bridge._text_scale(), 1.5, "the snapshot's effects carry it to the page")


class HeadingTests(unittest.TestCase):
    def test_a_passage_says_where_it_sits(self):
        row = next(row for row in watcher_lore.FRAGMENTS if row[5] == 2)
        kind, heading = thought_heading("lore_fragment", row[2])
        chapter = watcher_lore.ALL_CHAPTERS[2]
        self.assertEqual(kind, "memory")
        self.assertTrue(heading.startswith(f"MEMORY · {chapter[0]}. {chapter[1].upper()} · 1 OF "), heading)

    def test_echoes_and_the_rest(self):
        self.assertEqual(thought_heading("lore_black_hole"), ("echo", "ECHO · A BLACK HOLE"))
        self.assertEqual(thought_heading("lore_afterword")[0], "afterword")
        self.assertEqual(thought_heading("lore_recall"), ("recall", "LOOKING BACK"))
        self.assertEqual(thought_heading("arrival"), ("", ""), "an everyday remark: the page says THE WATCHER")

    def test_the_journal_words_are_marked_in_the_script_only(self):
        from voidcompass.overlays.watcher_mind import plain_text
        watcher, _clock = mind()
        thought = watcher.consider("arrival", {"system": "Hatchooe", "star": "K"}, force=True)
        self.assertIn("⟦Hatchooe⟧", thought["script"])
        self.assertNotIn("⟦", thought["text"], "what it says, and what its page keeps, is plain")
        self.assertIn("Hatchooe", watcher.memory["log"][-1][2])
        self.assertNotIn("⟦", watcher.memory["log"][-1][2])
        self.assertEqual(plain_text("I [[love|like]] ⟦Sol⟧."), "I like Sol.")
        watcher, _clock = mind()
        thought = watcher.consider("long_session", {"hours": "3"}, force=True)
        self.assertNotIn("⟦", thought["script"], "its own sense of time isn't something it noticed")

    def test_every_thought_carries_its_heading(self):
        watcher, _clock = mind()
        thought = watcher.consider("lore_black_hole", force=True)
        self.assertEqual((thought["kind"], thought["heading"]), ("echo", "ECHO · A BLACK HOLE"))


class StudioTests(unittest.TestCase):
    def studio(self, x):
        class Studio(_LiveSizeStudio):
            _OVERLAY_POSITION_SPECS = [("heartbeat_hud", "heartbeat_hud_x", "heartbeat_hud_y")]
        studio = Studio([])
        studio.config.update({"heartbeat_hud_x": x, "heartbeat_hud_y": 600, "heartbeat_orb_size": 54,
                              "heartbeat_hud_enabled": True})
        # Mid-thought: the window is the orb and its words, 384 wide.
        studio.heartbeat_hud = SimpleNamespace(_html_ready=True, _html_window_size=(384, 140), win=None)
        with patch(f"{HERE}.monitor_scale", return_value=1.0), patch(f"{HERE}.monitor_bounds", return_value=SCREEN):
            return next(row for row in HtmlOverlayStudioMixin._html_overlay_records(studio, live=False)
                        if row["id"] == "heartbeat_hud")

    def test_the_card_is_the_orb_with_its_words_beside_it(self):
        row = self.studio(2490)
        self.assertEqual((row["width"], row["height"]), (54, 54), "not the stretched window")
        zone = row["thought"]
        self.assertEqual(zone["side"], "left")
        self.assertEqual(zone["x"] + zone["width"], 2490, "the words end at the orb")
        self.assertGreaterEqual(zone["x"], 0)
        self.assertEqual(self.studio(100)["thought"]["side"], "right")

    def test_the_side_setting_and_its_controls(self):
        with patch(f"{HERE}.monitor_scale", return_value=1.0), patch(f"{HERE}.monitor_bounds", return_value=SCREEN):
            self.assertEqual(thought_zone({"heartbeat_thought_side": "left"}, 1200, 600)["side"], "left")
            self.assertEqual(thought_zone({"heartbeat_thought_side": "right"}, 1200, 600)["side"], "right")
            self.assertEqual(thought_zone({"heartbeat_thought_side": "left"}, 20, 600)["side"], "right",
                             "no room on the left of an orb at the edge")
        html = (Path(WEB) / "dashboard" / "index.html").read_text(encoding="utf-8")
        for setting in ('data-studio-setting="heartbeat_thought_side"', 'data-overlay-option="heartbeat_thought_heading"',
                        'data-studio-setting="heartbeat_text_scale_percent"'):
            self.assertIn(setting, html)

    def test_the_text_size_sticks(self):
        """It kept falling back to 75%: the number field saved on every arrow
        step (0 up one step is 5, kept as 75). Now a list of real sizes."""
        import re
        from voidcompass.overlays.heartbeat_hud import HEARTBEAT_TEXT_SIZES
        studio = self.studio_for_settings()
        for size in HEARTBEAT_TEXT_SIZES:
            with self.subTest(size=size):
                HtmlOverlayStudioMixin._html_overlay_settings_save(studio, {"heartbeat_text_scale_percent": str(size)})
                self.assertEqual(studio.config["heartbeat_text_scale_percent"], size)
                self.assertEqual(heartbeat_text_scale(studio.config), (size or 100) / 100)
        HtmlOverlayStudioMixin._html_overlay_settings_save(studio, {"heartbeat_text_scale_percent": "120"})
        self.assertEqual(studio.config["heartbeat_text_scale_percent"], 125, "the nearest size on the list")
        html = (Path(WEB) / "dashboard" / "index.html").read_text(encoding="utf-8")
        field = re.search(r'<select id="studio-heartbeat-text-scale"[^>]*>(.*?)</select>', html).group(1)
        self.assertEqual(tuple(int(value) for value in re.findall(r'value="(\d+)"', field)), HEARTBEAT_TEXT_SIZES)

    def studio_for_settings(self):
        studio = _LiveSizeStudio([])
        studio.config.update({"overlay_text_scale_percent": 100})
        return studio

    def test_settings_are_per_commander(self):
        self.assertIn("heartbeat_thought_side", config_module.PROFILE_TEXT_SETTINGS)
        self.assertIn("heartbeat_thought_heading", config_module.PROFILE_BOOL_SETTINGS)
        self.assertIn("heartbeat_text_scale_percent", config_module.PROFILE_VALUE_SETTINGS)


class WatcherPageTests(unittest.TestCase):
    def test_the_newest_hundred(self):
        watcher, _clock = mind()
        watcher.memory["log"] = [[1000.0 + index, "arrival", f"thought {index}"] for index in range(250)]
        deck = SimpleNamespace(config={}, heartbeat_hud=SimpleNamespace(mind=watcher), travel_history=None,
                               _WATCHER_BONDS=HtmlDashboardMixin._WATCHER_BONDS,
                               _WATCHER_BOND_NEXT=HtmlDashboardMixin._WATCHER_BOND_NEXT)
        data = HtmlDashboardMixin._html_watcher_workspace(deck)
        self.assertEqual(WATCHER_LOG_SHOWN, 100)
        self.assertEqual(len(data["log"]), 100)
        self.assertEqual(data["log"][0]["text"], "thought 249", "newest first")
        self.assertEqual(data["log"][-1]["text"], "thought 150")


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

    def show(self, width, height, thought):
        from urllib.parse import urlsplit

        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)

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
        page.evaluate("data => renderHeartbeat(data)", {
            "theme": THEME, "effects": {"reduced_motion": True, "text_scale": 1},
            "heartbeat": {"events": [], "orb": {"size": 54, "eye": "theme"},
                          "thought": {"id": 1, "script": thought["text"], "mood": "downcast", **thought}}})
        page.wait_for_timeout(150)
        return page

    def test_every_memory_fits_with_its_heading(self):
        for size_name in ("small", "standard", "large"):
            for words in sorted((row[2] for row in watcher_lore.FRAGMENTS), key=len)[-3:]:
                with self.subTest(size=size_name, words=words[:30]):
                    kind, heading = thought_heading("lore_fragment", words)
                    thought = {"text": words, "kind": kind, "heading": heading, "side": "right",
                               "style": {"size": size_name, "backdrop": True}}
                    bridge = HtmlHeartbeatBridge.__new__(HtmlHeartbeatBridge)
                    bridge.config = {"heartbeat_orb_size": 54}
                    with patch.object(HtmlHeartbeatBridge, "_thought", return_value=thought):
                        width, height = bridge._dimensions()
                    page = self.show(width, height, thought)
                    box = page.evaluate("""() => {
                        const words = document.querySelector('#thought .thought-words');
                        const box = document.querySelector('.thought-box').getBoundingClientRect();
                        return {cut: words.scrollHeight - words.clientHeight, top: box.top, bottom: box.bottom,
                                head: document.querySelector('.thought-head').textContent,
                                italic: getComputedStyle(words).fontStyle};
                    }""")
                    self.assertLessEqual(box["cut"], 1, "no line clipped")
                    self.assertGreaterEqual(box["top"], 0)
                    self.assertLessEqual(box["bottom"], height)
                    self.assertEqual(box["head"], heading)
                    self.assertEqual(box["italic"], "italic", "a passage, not a remark")

    def test_an_everyday_remark_is_simply_the_watcher_and_the_orb_where_told(self):
        page = self.show(384, 120, {"text": "Fuel's full.", "side": "right", "orb_top": 66, "style": {}})
        head = page.evaluate("() => document.querySelector('.thought-head').textContent")
        self.assertEqual(head, "THE WATCHER", "no time: it doesn't need one")
        top = page.evaluate("() => document.querySelector('.heartbeat').getBoundingClientRect().top")
        self.assertEqual(top, 66, "the orb sits where the bridge says, near the bottom edge")

    def test_the_words_it_noticed_stand_out(self):
        page = self.show(384, 80, {"text": "Hatchooe. Another K star.", "script": "⟦Hatchooe⟧. Another ⟦K⟧ star.",
                                   "side": "right", "style": {}})
        marks = page.evaluate("() => [...document.querySelectorAll('.thought-words em.noticed')].map(n => n.textContent)")
        self.assertEqual(marks, ["Hatchooe", "K"])
        self.assertEqual(page.evaluate("() => document.querySelector('.thought-words').textContent"),
                         "Hatchooe. Another K star.")

    def test_each_nature_types_its_own_way(self):
        page = self.show(384, 60, {"text": "Hm.", "side": "right", "style": {}})
        words = ("I keep thinking about the long dark between the stars, and the quiet way it waits for us, "
                 "patient as anything, while we pretend we are only passing through it on our way somewhere.")
        plan = page.evaluate("""([script]) => Object.fromEntries(['weary', 'stoic', 'nervous', 'curious', ''].map(nature => {
            const {frames, total} = window.heartbeatTyping.typingPlan(script, nature);
            const lengths = frames.map(frame => frame.parts.length);
            return [nature || 'standard', {total, deletes: lengths.filter((n, i) => i && n < lengths[i - 1]).length}];
        }))""", [words])
        self.assertGreater(plan["weary"]["total"], plan["standard"]["total"], "Depressed types slowly")
        self.assertLess(plan["nervous"]["total"], plan["weary"]["total"])
        self.assertGreater(plan["nervous"]["deletes"], 0, "Nervous slips and fixes it")
        self.assertEqual(plan["stoic"]["deletes"], 0)
        corrected = page.evaluate("""() => ['stoic', 'curious'].map(nature =>
            window.heartbeatTyping.typingPlan('I [[love|tolerate]] it.', nature).frames.some(
                frame => frame.parts.map(part => part.ch).join('') === 'I love'))""")
        self.assertEqual(corrected, [False, True], "Stoic has no second thoughts")
        eager = page.evaluate("""() => ['⟦Hatchooe Prime⟧ again.', 'Hatchooe Prime again.'].map(
            script => window.heartbeatTyping.typingPlan(script, 'curious').total)""")
        self.assertLess(eager[0], eager[1], "Curious hurries through what caught its eye")

    def test_the_heading_can_be_turned_off(self):
        page = self.show(384, 60, {"text": "Hm.", "side": "right", "style": {"heading": False}})
        self.assertTrue(page.locator(".thought-head").is_hidden())


if __name__ == "__main__":
    unittest.main()
