"""5.6.1: the Watcher, deeper. It asks and you answer; Book Four's road comes
from your answer; it asks to be taken places; it keeps moments, trust and a
slow mood; it dreams; it meets other Watchers; its story marks the orb; and
its voice carries feeling. All hand-written: no model."""

import math
import os
import random
import tempfile
import unittest
from array import array

from voidcompass.overlays import watcher_deeper, watcher_lines, watcher_lore, watcher_places, watcher_questions
from voidcompass.overlays.watcher_lore_four import CHAPTERS_FOUR, MUSINGS_OPEN, MUSINGS_SHUT
from voidcompass.overlays.watcher_mind import IMPORTANCE, WatcherMind, plain_text
from voidcompass.voice.watcher_voice import slip, stretch

BANNED = ("raxxla", "thargoid", "guardian", "dark wheel", "azimuth", "marvin", "hal 9000", "2001", "the club")


def mind(nature="weary", clock=None):
    now = [1_700_000_000.0] if clock is None else clock
    watcher = WatcherMind(os.path.join(tempfile.mkdtemp(), "watcher.json"),
                          config={"heartbeat_thoughts": "chatty", "heartbeat_personality": nature},
                          clock=lambda: now[0], rng=random.Random(7))
    return watcher, now


def through(book_end, road=None):
    return [[row[0], 0.0] for row in watcher_lore.FRAGMENTS if row[5] < book_end or (row[5] == book_end and row[8] is None)]


class QuestionTests(unittest.TestCase):
    def test_it_asks_and_remembers_the_answer(self):
        watcher, now = mind()
        watcher.observe("LoadGame", {})
        now[0] += 60
        thought = watcher.ask("stay_here", {"system": "Sol"})
        self.assertEqual([row["key"] for row in thought["question"]["answers"]], ["stay", "go"])
        reply = watcher.answer(1)
        self.assertTrue(reply["text"])
        self.assertEqual(watcher.memory["questions"]["stay_here"]["answer"], "stay")
        self.assertGreater(watcher.memory["trust"], watcher_deeper.TRUST_START)
        self.assertIsNone(watcher.ask("stay_here", {"system": "Sol"}), "an everyday question rests a fortnight")

    def test_unanswered_is_noticed(self):
        watcher, now = mind()
        watcher.observe("LoadGame", {})
        watcher.ask("talk_less")
        now[0] += watcher_questions.UNANSWERED_S + 1
        watcher._question_tick(now[0])
        self.assertIsNone(watcher.pending_question())
        self.assertEqual(watcher.memory["questions"]["talk_less"]["unanswered"], 1)
        self.assertLess(watcher.memory["trust"], watcher_deeper.TRUST_START)

    def test_talk_less_turns_it_down(self):
        watcher, _now = mind()
        watcher.config["heartbeat_thoughts"] = "occasional"
        watcher.observe("LoadGame", {})
        watcher.ask("talk_less")
        watcher.answer("less")
        self.assertEqual(watcher.config["heartbeat_thoughts"], "rare")


class BookFourTests(unittest.TestCase):
    def test_two_roads_and_the_answer_chooses(self):
        memory = {"lore": through(watcher_lore.BOOK_THREE_END), "afterword": 1}
        self.assertTrue(watcher_lore.road_question_due(memory))
        self.assertIsNone(watcher_lore.due(memory, 999, 2000, now=10 ** 10), "the road waits for the answer")
        for road in watcher_lore.ROADS:
            row = watcher_lore.due({**memory, "road": road}, 999, 2000, now=10 ** 10)
            self.assertEqual(row[8], road)
            page = watcher_lore.page({**memory, "road": road}, 999, 2000, now=10 ** 10)
            roads = {chapter["road"] for chapter in page["chapters"] if chapter["book"] == 4}
            self.assertEqual(roads, {None, road}, "only your road's chapters show")

    def test_the_shutter_question_sets_the_road(self):
        watcher, now = mind()
        watcher.observe("LoadGame", {})
        watcher.memory.update(lore=through(watcher_lore.BOOK_THREE_END), afterword=1)
        now[0] += 600
        watcher._last_spoke = 0
        self.assertEqual(watcher._maybe_ask(now[0], {})["question"]["id"], "shutter")
        watcher.answer("shut")
        self.assertEqual(watcher.memory["road"], "shut")
        self.assertEqual(watcher.story_marks()["shutter"], .6)

    def test_left_unanswered_it_chooses_itself(self):
        watcher, now = mind()
        watcher.observe("LoadGame", {})
        watcher.memory.update(lore=through(watcher_lore.BOOK_THREE_END), afterword=1)
        watcher.ask("shutter", force=True)
        now[0] += watcher_questions.ROAD_SELF_CHOSEN_S + 1
        watcher._question_tick(now[0])
        self.assertEqual(watcher.memory["road"], "shut")

    def test_passages_short_and_never_name_the_mysteries(self):
        for chapter in CHAPTERS_FOUR:
            for passage_id, words in chapter[5]:
                self.assertLessEqual(len(words), 240, passage_id)
                self.assertFalse([word for word in BANNED if word in words.casefold()], passage_id)
            self.assertFalse([word for word in BANNED if word in chapter[4].casefold()], chapter[1])
        for line in MUSINGS_OPEN + MUSINGS_SHUT:
            self.assertFalse([word for word in BANNED if word in line.casefold()], line)

    def test_places_it_asks_for(self):
        self.assertEqual(watcher_places.place_of("FSDJump", {"StarPos": [25, -20, 25800]}), "core")
        self.assertEqual(watcher_places.place_of("FSDJump", {"StarPos": [-1111.6, -134.2, 65269.75]}), "edge", "Beagle Point")
        self.assertEqual(watcher_places.place_of("Scan", {"StarType": "H"}), "black_hole")
        self.assertEqual(watcher_places.place_of("Scan", {"StarType": "K", "DistanceFromArrivalLS": 0, "WasDiscovered": False}),
                         "undiscovered")
        self.assertIsNone(watcher_places.place_of("FSDJump", {"StarPos": [0, 0, 0]}))
        memory = {"lore": through(watcher_lore.BOOK_THREE_END) + [["iv_o_breath", 0], ["iv_o_current", 0], ["iv_o_mountain", 0],
                                                                    ["iv_o_noticed", 0], ["iv_o_not_glass", 0]],
                  "afterword": 1, "road": "open"}
        self.assertEqual(watcher_lore.waiting_place(memory, 999, 2000, now=10 ** 10), "black_hole")


class MemoryTests(unittest.TestCase):
    def test_moments_trust_dreams_and_meeting(self):
        watcher, now = mind()
        watcher.observe("LoadGame", {})
        watcher.observe("FSDJump", {"StarSystem": "Sol", "StarPos": [0, 0, 0]})
        watcher.observe("Loadout", {"ShipName": "Void Dancer"})
        watcher.observe("Died", {})
        self.assertEqual(watcher.memory["moments"][-1]["text"], "the Void Dancer we lost near Sol")
        self.assertLess(watcher.memory["trust"], watcher_deeper.TRUST_START)
        dream = watcher._dream()
        self.assertTrue("Void Dancer" in dream or "Sol" in dream, dream)
        card = watcher.share_card("Kai")
        self.assertEqual(watcher_deeper.read_code("paste: " + watcher_deeper.share_code(card) + " thanks"), card)
        self.assertIsNone(watcher_deeper.read_code("VCWATCH1-abc-00000000"))
        met = watcher.meet({"name": "Zed", "nature": "curious", "road": "open", "hours": 4})
        self.assertTrue(met["text"])
        self.assertEqual(watcher._say_next[0][0], "lore_meeting", "the first meeting has its own passage")

    def test_faded_memories_after_the_shutter(self):
        faded = watcher_deeper.fade("the water world you were first to find, Col 285 Sector 3 a", 12345)
        self.assertIn("…", faded)
        self.assertTrue(faded.startswith("the"))


class OrbAndVoiceTests(unittest.TestCase):
    def test_story_marks(self):
        watcher, _now = mind()
        self.assertEqual(watcher.story_marks(), {"crack": False, "second_pupil": False, "shutter": 0.0})
        watcher.memory.update(lore=through(watcher_lore.BOOK_THREE_END), afterword=1, road="open")
        self.assertEqual(watcher.story_marks(), {"crack": True, "second_pupil": True, "shutter": 0.0})

    def test_feel_and_effects(self):
        watcher, _now = mind()
        watcher.memory.update(afterword=None)
        thought = watcher._utter("lore_fragment", "lore:the_fold", "There's a fold beside the seat.", 1.0)
        self.assertEqual(thought["effect"], "story_shutter")
        self.assertLess(thought["voice"]["gain"], 1.0, "a whisper for its story")
        self.assertTrue(watcher._utter("lore_fragment", "lore:let_me", "Watch.", 2.0)["voice"]["slip"])

    def test_the_voice_is_stretched_without_changing_pitch(self):
        samples = array("h", (int(8000 * math.sin(index / 10)) for index in range(22050)))
        slower = stretch(samples, 1.1, 22050)
        self.assertAlmostEqual(len(slower) / len(samples), 1.1, delta=.05)
        self.assertGreater(len(slip(samples, 22050)), len(samples), "a gap")


class BankTests(unittest.TestCase):
    def test_new_topics_have_deep_banks_and_no_shared_lines(self):
        for topic in ("poked_wary", "poked_warm", "mood_low", "mood_high", "idle_moment", "anniversary_us", "dream_told",
                      "watchers_meet", "idle_four_shut", "idle_four_open"):
            self.assertIn(topic, IMPORTANCE)
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 10, topic)
                self.assertFalse([line for line in bank[topic] if any(word in line.casefold() for word in BANNED)], topic)
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            lines = [plain_text(line) for lines in bank.values() for line in lines]
            self.assertEqual(len(lines), len(set(lines)))

    def test_every_question_answers_in_both_voices(self):
        for question_id, spec in watcher_questions.QUESTIONS.items():
            for key, _label in spec["answers"]:
                for voice in ("normal", "weary"):
                    self.assertTrue(spec["replies"][key][voice], (question_id, key, voice))
                self.assertIn(key, spec["callbacks"])


class PageTests(unittest.TestCase):
    def test_the_page_is_laid_out_as_tabs(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parents[1] / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        for tab in ("now", "story", "you", "said", "settings", "voice"):
            self.assertIn(f'data-watcher-tab="{tab}"', script)
            self.assertIn(f'data-watcher-panel="{tab}"', script)
        # A tab remembered from before 5.6.1 still opens something.
        self.assertIn('const OLD_TABS = {overview: "now", together: "you"};', script)
        for marker in ("BOOK FOUR", "THE ROAD TAKEN", 'class="watcher-answer"', "<kbd>", 'data-page="mission"', "all four books"):
            self.assertIn(marker, script)


if __name__ == "__main__":
    unittest.main()
