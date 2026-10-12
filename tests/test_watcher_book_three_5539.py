"""The Watcher's Book Three, What Was Put There (5.5.3.9): the seat in the
ship's core, and what looks through the Watcher. Told over about a year."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from voidcompass.overlays import watcher_idle, watcher_lines, watcher_lore, watcher_mind
from voidcompass.overlays.watcher_lore_three import CHAPTERS_THREE, MUSINGS_THREE

ROOT = Path(__file__).resolve().parents[1]
DAY = 86400.0
T0 = 1_800_000_000.0

BOOK_THREE = [row for row in watcher_lore.FRAGMENTS if row[5] >= watcher_lore.BOOK_TWO_END]
BEFORE = [row for row in watcher_lore.FRAGMENTS if row[5] < watcher_lore.BOOK_TWO_END]


def memory_with(told, echoes=(), at=T0):
    """Book One and Two told by ``at`` (plus ``told`` Book Three ids at given times)."""
    lore = [[row[0], at] for row in BEFORE] + [[passage, when] for passage, when in told]
    return {"lore": lore, "afterword": at - 1000, "echoes": {topic: [1, at] for topic in echoes}}


class StoryTests(unittest.TestCase):
    def test_seven_chapters_after_book_two(self):
        self.assertEqual([chapter[0] for chapter in CHAPTERS_THREE], ["XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV"])
        self.assertEqual(watcher_lore.BOOKS[2][:2], ("Three", "What Was Put There"))
        self.assertEqual(len(BOOK_THREE), sum(len(chapter[5]) for chapter in CHAPTERS_THREE))
        ids = [row[0] for row in watcher_lore.FRAGMENTS]
        self.assertEqual(len(ids), len(set(ids)), "every passage its own id, across all three books")

    def test_its_own_words_and_the_games_mysteries_unnamed(self):
        banned = re.compile(r"thargoid|guardian|raxxla|dark wheel|marvin|azimuth|club\b", re.I)
        for chapter in CHAPTERS_THREE:
            texts = [chapter[4]] + [words for _id, words in chapter[5]]
            for text in texts:
                self.assertNotRegex(text, banned)
            for _id, words in chapter[5]:
                self.assertLessEqual(len(words), 240, words)
            self.assertIn(chapter[0], watcher_lore.CHAPTER_ABOUT)
        for line in MUSINGS_THREE:
            self.assertNotRegex(line, banned)

    def test_the_echoes_it_waits_for_exist(self):
        for chapter in CHAPTERS_THREE:
            needs = watcher_lore.chapter_needs(chapter)
            if needs:
                self.assertIn(needs, watcher_lore.ECHO_LABELS)


class PacingTests(unittest.TestCase):
    """About a year: chapters weeks apart, passages days apart."""

    def test_two_weeks_after_book_two_then_its_hours(self):
        memory = memory_with([])
        first = BOOK_THREE[0]
        self.assertIsNone(watcher_lore.due(memory, 999, 2000, now=T0 + 13 * DAY), "not before two weeks")
        self.assertIsNone(watcher_lore.due(memory, 999, 600, now=T0 + 30 * DAY), "nor before its hours")
        self.assertEqual(watcher_lore.due(memory, first[3], first[4], now=T0 + 15 * DAY)[0], first[0])

    def test_passages_days_apart_and_chapters_weeks_apart(self):
        chapter_one = [row for row in BOOK_THREE if row[5] == watcher_lore.BOOK_TWO_END]
        told = [(chapter_one[0][0], T0 + 15 * DAY)]
        memory = memory_with(told)
        self.assertIsNone(watcher_lore.due(memory, 999, 2000, now=T0 + 16 * DAY), "a day later: not yet")
        self.assertEqual(watcher_lore.due(memory, 999, 2000, now=T0 + 17.5 * DAY)[0], chapter_one[1][0])
        # The whole first chapter told: the next waits six weeks.
        finished = T0 + 40 * DAY
        memory = memory_with([(row[0], finished) for row in chapter_one])
        self.assertIsNone(watcher_lore.due(memory, 999, 2000, now=finished + 30 * DAY))
        self.assertEqual(watcher_lore.due(memory, 999, 2000, now=finished + 43 * DAY)[5], watcher_lore.BOOK_TWO_END + 1)

    def test_a_chapter_that_waits_for_an_echo(self):
        index = next(i for i, chapter in enumerate(watcher_lore.ALL_CHAPTERS) if chapter[0] == "XXI")
        before = [row for row in watcher_lore.FRAGMENTS if watcher_lore.BOOK_TWO_END <= row[5] < index]
        done = T0 + 300 * DAY
        memory = memory_with([(row[0], done) for row in before])
        self.assertIsNone(watcher_lore.due(memory, 999, 5000, now=done + 60 * DAY), "a great ship first")
        memory = memory_with([(row[0], done) for row in before], echoes=["lore_great_ship"])
        self.assertEqual(watcher_lore.due(memory, 999, 5000, now=done + 60 * DAY)[5], index)

    def test_about_a_year_at_the_least(self):
        days = sum(row[7] for row in BOOK_THREE)
        self.assertGreaterEqual(days, 300, "the calendar alone keeps it to most of a year")


class PageTests(unittest.TestCase):
    def test_book_three_appears_once_book_two_is_told(self):
        partial = {"lore": [[row[0], T0] for row in BEFORE[:-1]], "afterword": T0}
        page = watcher_lore.page(partial, 999, 2000, now=T0)
        self.assertFalse(page["book_three"])
        self.assertNotIn(3, {chapter["book"] for chapter in page["chapters"]})
        page = watcher_lore.page(memory_with([]), 999, 2000, now=T0 + DAY)
        self.assertTrue(page["book_three"])
        self.assertIn(3, {chapter["book"] for chapter in page["chapters"]})
        self.assertEqual((page["next"]["book"], page["next"]["days"], page["next"]["ready"]), (3, 13.0, False))
        script = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        self.assertIn("WHAT WAS PUT THERE", script)
        self.assertIn("days(next)", script)

    def test_progress_and_achievements(self):
        progress = watcher_lore.progress(memory_with([(BOOK_THREE[0][0], T0 + 15 * DAY)]))
        self.assertEqual((progress["BookTwo"], progress["BookThreeBegun"], progress["BookThree"]), (1, 1, 0))
        everything = watcher_lore.progress(memory_with([(row[0], T0 + 400 * DAY) for row in BOOK_THREE]))
        self.assertEqual(everything["BookThree"], 1)
        self.assertTrue(watcher_lore.book_three_begun(memory_with([(BOOK_THREE[0][0], T0)])))
        achievements = json.loads((ROOT / "data" / "achievements.json").read_text(encoding="utf-8"))
        fields = {row["trigger"].get("field") for row in achievements if row.get("trigger", {}).get("event") == "VoidCompassWatcherStory"}
        self.assertTrue({"BookThreeBegun", "BookThree"} <= fields)


class MusingTests(unittest.TestCase):
    def test_darker_musings_once_it_has_begun(self):
        self.assertIn("idle_lens", watcher_idle.IDLE_TOPICS)
        self.assertIn("idle_lens", watcher_mind.TOPICS)
        for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
            self.assertGreaterEqual(len(bank["idle_lens"]), 10)
        self.assertEqual(watcher_mind.thought_heading("idle_lens"), ("musing", "THE SEAT"))
        self.assertEqual(watcher_mind.thought_heading("lore_fragment", BOOK_THREE[0][2])[1], "MEMORY · XVIII. THE SEAT · 1 OF 6")


if __name__ == "__main__":
    unittest.main()
