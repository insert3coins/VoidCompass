"""5.7.1: the Watcher learns your name, and speaks a little better.

The ship writes your name first thing every time you wake it (LoadGame). The
Watcher notices it once you've been together a while, tries it, asks whether
it may use it, and then keeps it for the moments that matter, once a session.
How the name is said, and what it calls you, are set on its page. It reads
what the journal says of you too: promotions by their names, your record,
your power, your squadron, your carrier. And its little sounds are said, not
spelled out (espeak read "Hm" as "aitch em"; each respelling here was checked
against the phonemes Piper makes).
"""

import os
import random
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from voidcompass.core import ranks
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import watcher_lines, watcher_name, watcher_questions
from voidcompass.overlays.watcher_mind import IMPORTANCE, WatcherMind, plain_text
from voidcompass.voice.watcher_voice import speakable

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("raxxla", "thargoid", "guardian", "dark wheel", "azimuth", "marvin", "hal 9000", "2001", "the club")


def mind(nature="weary", sessions=40, hours=120.0):
    now = [1_800_000_000.0]
    watcher = WatcherMind(os.path.join(tempfile.mkdtemp(), "watcher.json"),
                          config={"heartbeat_thoughts": "chatty", "heartbeat_personality": nature},
                          clock=lambda: now[0], rng=random.Random(4))
    watcher.memory.update(sessions=sessions, hours=hours, last_seen=now[0] - 5 * 3600,
                          voice={"minutes": 500.0, "told": [], "found": 1})
    return watcher, now


def session(watcher, now, name="insert3coins", answer=None, ticks=40):
    """A new session: LoadGame, then a few quiet minutes. The thoughts of its arc."""
    now[0] += 10 * 3600
    watcher.observe("LoadGame", {"Commander": name, "FID": "F1"})
    said = []
    for _ in range(ticks):
        now[0] += 30
        thought = watcher.tick({})
        if thought and thought.get("topic") in {"name_lore", "question", "name_renamed"}:
            said.append(thought)
            if thought.get("question") and answer:
                watcher.answer(answer)
                said.append(watcher.thought)
    return said


class SpeechTests(unittest.TestCase):
    def test_its_sounds_are_said_not_spelled(self):
        for written, heard in (("Hm. I see.", "Hmmm. I see."), ("Hmm, well.", "Hmmm, well."), ("Mm.", "Hmm."),
                               ("Mmm. Nice.", "Hmm. Nice."), ("Mm-hm.", "Uh-huh."), ("Hmph.", "Humph."),
                               ("Shh.", "Shush."), ("Pfft. Fine.", "Puh. Fine."), ("Ugh. Huh. Tsk.", "Ugh. Huh. Tsk.")):
            self.assertEqual(speakable(written), heard, written)

    def test_marks_units_letters_and_shouting(self):
        self.assertEqual(speakable("Cobra Mk III, Krait Mk II"), "Cobra Mark three, Krait Mark two")
        self.assertEqual(speakable("Elite III, in exploration."), "Elite three, in exploration.")
        self.assertEqual(speakable("42 km away, 3 AU out"), "42 kilometres away, 3 astronomical units out")
        self.assertEqual(speakable("SCO and EDSM"), "S C O and E D S M")
        self.assertEqual(speakable("IT IS THE MOST beautiful thing."), "it is the most beautiful thing.")
        # A catalogue's letters and the scanners stay as they are.
        for kept in ("HIP 10322", "Pyriveae JB-W d2-16", "LHS 3447 and IC 2391", "DSS done, FSS 32%"):
            self.assertEqual(speakable(kept), kept)


class RankTests(unittest.TestCase):
    def test_promotions_by_name(self):
        self.assertEqual(ranks.said("Explore", 8), "Elite, in exploration")
        self.assertEqual(ranks.said("Federation", 14), "Admiral, in the Federal Navy")
        self.assertEqual(ranks.name("Exobiologist", 12), "Elite IV")
        self.assertEqual(ranks.said("Nonsense", 3), "")
        watcher, now = mind()
        watcher._session_start = now[0]
        thoughts = [watcher.consider("promotion", {"rank": ranks.said("Explore", 8)}, force=True) for _ in range(3)]
        self.assertTrue(any("Elite, in exploration" in (thought or {}).get("text", "") for thought in thoughts))


class NameTests(unittest.TestCase):
    def test_a_tag_as_it_can_be_said(self):
        self.assertEqual(watcher_name.auto_spoken("insert3coins"), "insert 3 coins")
        self.assertEqual(watcher_name.auto_spoken("DarkStar_77"), "Dark Star 77")
        self.assertEqual(watcher_name.auto_spoken("xX_Nova_Xx"), "Nova")
        self.assertEqual(speakable(watcher_name.auto_spoken("insert3coins")), "insert 3 coins")

    def test_the_arc_one_step_a_session_then_the_name_once_a_session(self):
        watcher, now = mind()
        self.assertEqual(session(watcher, now), [], "it needs to have read the name in two sessions first")
        notice = session(watcher, now)
        self.assertEqual(notice[0]["heading"], "THE NAME · 1 OF 3")
        self.assertIn("insert3coins", notice[0]["text"])
        self.assertIn("42", notice[0]["text"], "it read the name every session it was there (40, and two more)")
        self.assertEqual(session(watcher, now)[0]["heading"], "THE NAME · 2 OF 3")
        asked = session(watcher, now, answer="yes")
        self.assertEqual(asked[0]["question"]["id"], "your_name")
        self.assertEqual([row["key"] for row in asked[0]["question"]["answers"]], ["yes", "commander", "other"])
        self.assertEqual(watcher_name.record(watcher.memory)["call"], "name")
        first = session(watcher, now)
        self.assertEqual(first[0]["heading"], "THE NAME · 3 OF 3")
        self.assertIn("insert3coins", first[0]["text"])
        self.assertEqual(session(watcher, now), [], "the arc is done")
        # Named lines: at most once a session, and only in the moments that matter.
        now[0] += 10 * 3600
        watcher.observe("LoadGame", {"Commander": "insert3coins", "FID": "F1"})
        named = 0
        for _ in range(40):
            thought = watcher.consider("greet_bond", {"sessions": 41}, force=True)
            named += "insert3coins" in (thought or {}).get("text", "")
        self.assertEqual(named, 1)
        self.assertIsNone(watcher_name.may_name(watcher.memory, watcher._session_start))
        # Spoken as you'd have it said.
        watcher_name.set_spoken(watcher.memory, "Insert Three Coins")
        self.assertEqual(watcher.spoken_words({"topic": "x", "text": "Goodnight, insert3coins."}), "Goodnight, Insert Three Coins.")

    def test_commander_keeps_it_unsaid_and_a_chosen_name_is_used_instead(self):
        watcher, now = mind(nature="curious")
        watcher_name.observe(watcher.memory, "LoadGame", {"Commander": "insert3coins"})
        watcher_name.set_call(watcher.memory, "commander")
        watcher._session_start = now[0]
        texts = [(watcher.consider("greet_bond", {"sessions": 9}, force=True) or {}).get("text", "") for _ in range(30)]
        self.assertFalse([text for text in texts if "insert3coins" in text])
        watcher_name.set_call(watcher.memory, "nickname", "Coins")
        self.assertEqual(watcher_name.call_name(watcher.memory), "Coins")
        self.assertEqual(watcher_name.spoken(watcher.memory)["Coins"], "Coins")

    def test_a_new_name_is_noticed(self):
        watcher, now = mind()
        session(watcher, now)
        renamed = session(watcher, now, name="NightOwl", ticks=10)
        self.assertEqual(renamed[0]["topic"], "name_renamed")
        self.assertEqual(renamed[0]["heading"], "A NEW NAME")
        self.assertIn("NightOwl", renamed[0]["text"])
        self.assertIn("insert3coins", renamed[0]["text"])
        self.assertEqual(watcher_name.record(watcher.memory)["old"], ["insert3coins"])

    def test_what_the_journal_says_of_you(self):
        self.assertEqual(watcher_name.fact_fields("Statistics", {"Exploration": {
            "Systems_Visited": 29993, "Total_Hyperspace_Jumps": 41280, "Time_Played": 3600 * 2345}}),
            ("cmdr_record", {"systems": "29,993", "jumps": "41,280", "played": "2,345 hours"}))
        self.assertEqual(watcher_name.fact_fields("Powerplay", {"Power": "Pranav Antal", "Rank": 36})[0], "cmdr_power")
        self.assertEqual(watcher_name.fact_fields("SquadronStartup", {"SquadronName": "Void Runners"})[1], {"squadron": "Void Runners"})
        self.assertEqual(watcher_name.fact_fields("CarrierStats", {"Name": "Insert Coin", "CarrierType": "FleetCarrier"})[0], "cmdr_carrier")
        self.assertIsNone(watcher_name.fact_fields("CarrierStats", {"Name": "Squad", "CarrierType": "SquadronCarrier"}))
        watcher, now = mind()
        session(watcher, now, ticks=1)
        watcher.observe("Powerplay", {"Power": "Pranav Antal", "Rank": 36})
        said = [watcher.tick({}) for _ in range(6) if not now.__setitem__(0, now[0] + 30)]
        power = [thought for thought in said if thought and thought.get("topic") == "cmdr_power"]
        self.assertTrue(power and "Pranav Antal" in power[0]["text"])
        self.assertEqual(power[0]["heading"], "WHAT IT HAS READ OF YOU")
        # Not again for three weeks.
        watcher.observe("Powerplay", {"Power": "Pranav Antal", "Rank": 36})
        self.assertNotIn("cmdr_power", [topic for topic, _fields in watcher._say_next])

    def test_banks_rules(self):
        for topic in watcher_name.FACTS:
            self.assertIn(topic, IMPORTANCE)
        lines = [line for bank in (watcher_name.ARC, watcher_name.NAMED) for row in bank.values() for voice in row.values() for line in voice]
        lines += [line for voice in watcher_name.RENAMED.values() for line in voice]
        lines += [line for _level, normal, weary in watcher_name.FACTS.values() for line in normal + weary]
        spec = watcher_questions.QUESTIONS["your_name"]
        lines += [line for voice in spec["ask"].values() for line in voice]
        lines += [line for replies in spec["replies"].values() for voice in replies.values() for line in voice]
        for line in lines:
            self.assertLessEqual(len(line), 240, line)
            self.assertFalse([word for word in BANNED if word in line.casefold()], line)
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            every = [plain_text(line) for rows in bank.values() for line in rows]
            self.assertEqual(len(every), len(set(every)))


class Deck(DashboardWatcherVoiceMixin):
    def __init__(self, watcher):
        self.config = {}
        self.watcher = watcher
        self.published = 0
        self.spoken = []
        deck = self

        class Speaker:
            def say(self, words, key=None, feel=None):
                deck.spoken.append(words)
                return True
        self._speaker = Speaker()

    def _watcher_mind(self):
        return self.watcher

    def _watcher_speaker(self):
        return self._speaker

    def _schedule_html_dashboard_publish(self, immediate=False):
        self.published += 1


class PageCommandTests(unittest.TestCase):
    def test_the_page_sets_what_it_calls_you_and_how_it_says_it(self):
        watcher, _now = mind()
        watcher_name.observe(watcher.memory, "LoadGame", {"Commander": "insert3coins"})
        deck = Deck(watcher)
        self.assertTrue(deck._handle_watcher_settings_command("name_call", {"value": "nickname"}))
        self.assertTrue(deck._handle_watcher_settings_command("name_nickname", {"value": "  Coins   "}))
        self.assertTrue(deck._handle_watcher_settings_command("name_spoken", {"value": "Insert Three Coins"}))
        self.assertFalse(deck._handle_watcher_settings_command("name_call", {"value": "lord"}))
        page = watcher_name.page(watcher.memory)
        self.assertEqual((page["known"], page["call"], page["nickname"], page["spoken"], page["spoken_auto"]),
                         ("insert3coins", "nickname", "Coins", "Insert Three Coins", "insert 3 coins"))
        self.assertGreaterEqual(deck.published, 3)
        self.assertTrue(Path(watcher.memory_path).is_file(), "kept in its memory of this commander")


class PageTests(unittest.TestCase):
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

    def test_the_your_name_card(self):
        page = self.browser.new_page(viewport={"width": 1400, "height": 900})
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route, _request=None):
            path = unquote(urlsplit(route.request.url).path)
            target = ROOT / "web" / path.lstrip("/")
            if path == "/test.html":
                route.fulfill(body="<!doctype html><body><div id='watcher-workspace'></div></body>", content_type="text/html")
            elif target.is_file():
                route.fulfill(path=str(target))
            else:
                route.fulfill(status=404, body="")

        page.route("http://watcher.test/**", serve)
        page.goto("http://watcher.test/test.html")
        page.evaluate("""async () => {
          const module = await import('/dashboard/watcher.js');
          window.__sent = [];
          window.__ui = {byId: (id) => document.getElementById(id), escapeHtml: (text) => String(text ?? ''),
            numeric: (value) => String(value ?? 0), showToast: () => {},
            command: async (kind, payload) => { window.__sent.push(payload); return true; }};
          window.__render = (data) => module.renderWatcher(data, window.__ui);
        }""")
        page.evaluate("__render({name: {known: 'insert3coins', call: 'name', nickname: '', spoken: '', spoken_auto: 'insert 3 coins', told: ['notice', 'try'], steps: 3}})")
        page.locator('[data-watcher-tab="you"]').click()
        card = page.locator(".watcher-name")
        self.assertTrue(card.is_visible())
        self.assertIn("insert3coins", page.locator("#watcher-name-note").text_content())
        self.assertEqual(page.locator("#watcher-name-call").input_value(), "name")
        self.assertEqual(page.locator("#watcher-name-spoken").get_attribute("placeholder"), "insert 3 coins")
        page.locator("#watcher-name-call").select_option("nickname")
        page.locator("#watcher-name-nickname").fill("Coins")
        page.locator("#watcher-name-nickname").press("Tab")
        page.locator("#watcher-name-hear").click()
        page.wait_for_function("window.__sent.length >= 3")
        sent = page.evaluate("window.__sent.map((row) => [row.operation, row.value])")
        self.assertEqual(sent[:3], [["name_call", "nickname"], ["name_nickname", "Coins"], ["name_hear", "insert 3 coins"]])
        # Before the game has been loaded, there's nothing to call you yet.
        page.evaluate("__render({name: {known: ''}})")
        self.assertTrue(page.locator("#watcher-name-call").is_disabled())
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
