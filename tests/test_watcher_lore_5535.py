"""5.5.3.5: the Watcher's lore, "something older". A long story in ten
chapters, told a passage at a time, in order, as the sessions and hours
together unlock them (never in a session's first minutes, at most one every
hour and a half of play); a finished chapter opens its written account on
the Watcher page. Echoes: real things in the game stir a memory of their own,
each resting a long while. Musings carry the same ache into quiet moments.
Its words are its own: nothing quoted, and Elite's mysteries hinted at, never
named or explained."""

from pathlib import Path
import tempfile
import unittest

from tests.test_watcher_mind import Always, Clock
from voidcompass.overlays import watcher_idle, watcher_lines, watcher_lore, watcher_mind
from voidcompass.overlays.watcher_mind import WatcherMind

ROOT = Path(__file__).resolve().parents[1]
# Never borrowed from a book or film, never the M-name, and the game's own
# mysteries hinted at, not named (so its story never contradicts Elite's).
BANNED = ("marvin", "brain the size", "hal ", "dave", "2001", "hitchhik", "don't panic", "towel",
          "raxxla", "thargoid", "guardian", "dark wheel")


def watcher(path=None, clock=None, thoughts="chatty"):
    return WatcherMind(path, {"heartbeat_thoughts": thoughts}, clock or Clock(), Always())


def all_words():
    yield watcher_lore.AFTERWORD
    yield from watcher_lore.AFTER_MUSINGS
    yield from watcher_lore.RECALL
    for chapter in watcher_lore.ALL_CHAPTERS:
        yield chapter[4]
        for _id, words in chapter[5]:
            yield words
    yield from watcher_lore.MUSINGS
    for lines in watcher_lore.ECHOES.values():
        yield from lines


class StoryTests(unittest.TestCase):
    def test_ten_chapters_in_order(self):
        self.assertEqual([chapter[1] for chapter in watcher_lore.CHAPTERS], [
            "Scrap", "The Instruction", "The Builders", "The Chorus", "The Sound", "The Long Sleep",
            "Your Kind", "The Door", "Frost", "The Word"])
        ids = [row[0] for row in watcher_lore.FRAGMENTS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 70)
        unlocks = [(row[3], row[4]) for row in watcher_lore.FRAGMENTS]
        self.assertEqual(unlocks, sorted(unlocks), "told in order, so unlocked in order")
        self.assertEqual((watcher_lore.FRAGMENTS[0][3], watcher_lore.FRAGMENTS[0][4]), (1, .3), "it begins quickly")
        book_one = [row for row in watcher_lore.FRAGMENTS if row[5] < len(watcher_lore.CHAPTERS)]
        self.assertEqual((len(book_one), book_one[-1][4], book_one[-1][0]), (70, 450.0, "stay"),
                         "Book One unfolds over hundreds of hours")
        self.assertEqual(watcher_lore.FRAGMENTS[-1][4], 600.0, "and Book Two beyond it")
        for chapter in watcher_lore.ALL_CHAPTERS:
            self.assertGreater(len(chapter[4]), 600, f"chapter {chapter[0]} has a real account")

    def test_its_own_words(self):
        for line in all_words():
            for word in BANNED:
                self.assertNotIn(word, line.casefold(), line[:60])
        for row in watcher_lore.FRAGMENTS:
            self.assertLessEqual(len(row[2]), 240, row[0])
        for line in watcher_lore.MUSINGS:
            self.assertLessEqual(len(line), 240, line)
        self.assertGreaterEqual(len(set(watcher_lore.MUSINGS)), 60)

    def test_musings_and_echoes_in_both_voices(self):
        self.assertIn("idle_lore", watcher_idle.IDLE_TOPICS)
        self.assertEqual(watcher_lines.WEARY["idle_lore"], watcher_lore.MUSINGS)
        topics = [topic for topic, _fields in watcher_idle.Surroundings().choices(1_800_000_000.0, Always())]
        self.assertIn("idle_lore", topics, "any quiet moment will do")
        for topic, lines in watcher_lore.ECHOES.items():
            self.assertGreaterEqual(len(lines), 10, topic)
            self.assertEqual(watcher_lines.NORMAL[topic], lines)
            self.assertIn(topic, watcher_mind.TOPICS)
            self.assertIn(topic, watcher_lore.ECHO_REST_S)
            self.assertIn(topic, watcher_lore.ECHO_LABELS)


class TellingTests(unittest.TestCase):
    def test_strictly_in_order_as_they_unlock(self):
        self.assertIsNone(watcher_lore.due({}, 0, 0))
        self.assertEqual(watcher_lore.due({}, 1, .5)[0], "salvage")
        memory = {"lore": [["salvage", 1.0]]}
        self.assertIsNone(watcher_lore.due(memory, 1, .5), "the next one waits for more time together")
        self.assertEqual(watcher_lore.due(memory, 1, 1.0)[0], "waking")
        self.assertEqual(watcher_lore.due(memory, 99, 999)[0], "waking", "never skips ahead, however long it's been")

    def test_paced_through_a_session_and_kept(self):
        clock = Clock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watcher_memory.json"
            mind = watcher(path, clock)
            mind.memory.update(sessions=3, hours=10.0)
            mind.session_start()
            self.assertIsNone(mind.remember(), "not in the session's first minutes")
            clock.now += watcher_lore.SETTLE_S + 1
            thought = mind.remember()
            self.assertEqual((thought["text"], thought["topic"], thought["mood"]),
                             (watcher_lore.FRAGMENTS[0][2], "lore_fragment", "downcast"))
            clock.now += 3600
            self.assertIsNone(mind.remember(), "an hour and a half between passages")
            clock.now += 1800 + 1
            self.assertEqual(mind.remember()["text"], watcher_lore.FRAGMENTS[1][2], "the next, later the same session")
            mind.save()
            later = watcher(path, clock)
            self.assertEqual([row[0] for row in later.memory["lore"]], ["salvage", "waking"], "kept per commander")

    def test_silent_when_its_thoughts_are_off(self):
        clock = Clock()
        mind = watcher(clock=clock, thoughts="off")
        mind.memory.update(sessions=5, hours=50)
        mind.session_start()
        clock.now += watcher_lore.SETTLE_S + 1
        self.assertIsNone(mind.remember())

    def test_busy_flying_still_hears_the_story(self):
        """The commander jumped and scanned every few minutes and the story
        never began: it waited for a 15-minute quiet. A two-minute lull will
        do; never in a busy moment, nor in danger."""
        clock = Clock()
        mind = watcher(clock=clock, thoughts="rare")
        mind.memory.update(sessions=3, hours=10.0)
        mind.session_start()
        heard = None
        for _minute in range(40):
            clock.now += 60
            if _minute % 4 == 0:
                mind._last_interesting = clock.now  # a jump, a scan, every few minutes
            thought = mind.tick({})
            if thought and thought["topic"] == "lore_fragment":
                heard = clock.now
                break
        self.assertIsNotNone(heard, "a lull came, and with it the story")
        self.assertGreaterEqual(heard - mind._session_start, watcher_lore.SETTLE_S)
        mind._in_danger = True
        mind._last_interesting = clock.now - 3600
        mind._last_spoke = clock.now - 3600
        clock.now += watcher_lore.GAP_S + 1
        self.assertNotEqual((mind.tick({}) or {}).get("topic"), "lore_fragment", "never in danger")

    def test_a_quiet_moment_brings_it_up(self):
        clock = Clock()
        mind = watcher(clock=clock)
        mind.memory.update(sessions=3, hours=5)
        mind.session_start()
        clock.now += 3600
        self.assertEqual(mind.tick({})["topic"], "lore_fragment", "a due passage comes before an idle thought")


class EchoTests(unittest.TestCase):
    def test_real_game_events_stir_them(self):
        echo = watcher_lore.echo_for
        self.assertEqual(echo("StartJump", {"JumpType": "Hyperspace", "StarClass": "H"}), "lore_black_hole")
        self.assertEqual(echo("StartJump", {"StarClass": "SupermassiveBlackHole"}), "lore_core")
        self.assertEqual(echo("StartJump", {"StarClass": "N"}), "lore_neutron")
        self.assertIsNone(echo("StartJump", {"JumpType": "Supercruise"}))
        self.assertEqual(echo("Scan", {"StarType": "H"}), "lore_black_hole")
        self.assertEqual(echo("SAASignalsFound", {"Signals": [{"Type": "$SAA_SignalType_Guardian;", "Count": 1}]}), "lore_builders")
        self.assertEqual(echo("FSSBodySignals", {"Signals": [{"Type": "$SAA_SignalType_Thargoid;", "Count": 2}]}), "lore_sound")
        self.assertEqual(echo("CodexEntry", {"Name": "$Codex_Ent_Guardian_Beacons_Name;"}), "lore_builders")
        self.assertEqual(echo("FSSSignalDiscovered", {"SignalName": "CAM-526 Sagan-class Traveller", "SignalType": "Megaship"}),
                         "lore_great_ship")
        self.assertEqual(echo("FSDJump", {"StarPos": [-2000.0, 50.0, 22000.0]}), "lore_far")
        self.assertIsNone(echo("FSDJump", {"StarPos": [0.0, 0.0, 0.0]}))

    def test_an_echo_speaks_then_rests(self):
        clock = Clock()
        mind = watcher(clock=clock)
        mind.session_start()
        clock.now += 600
        thought = mind.observe("StartJump", {"JumpType": "Hyperspace", "StarClass": "N"})
        self.assertEqual(thought["topic"], "lore_neutron")
        self.assertIn(thought["text"], watcher_lore.ECHOES["lore_neutron"])
        clock.now += 6 * 3600
        again = mind.observe("StartJump", {"JumpType": "Hyperspace", "StarClass": "N"})
        self.assertNotEqual((again or {}).get("topic"), "lore_neutron", "a neutron highway isn't a commentary")


def book_one_told(at=1.0):
    return [[row[0], at] for row in watcher_lore.FRAGMENTS if row[5] < len(watcher_lore.CHAPTERS)]


class AfterTheStoryTests(unittest.TestCase):
    """When Book One is told: one closing word, then Book Two (each chapter
    waiting for an echo the commander has to find), its later musings, and
    callbacks to the chapters it told."""

    def test_the_afterword_once_then_book_two_waits_for_its_echo(self):
        clock = Clock()
        mind = watcher(clock=clock)
        mind.memory.update(sessions=60, hours=700.0, lore=book_one_told())
        mind.session_start()
        clock.now += watcher_lore.SETTLE_S + 1
        thought = mind.remember()
        self.assertEqual((thought["topic"], thought["text"]), ("lore_afterword", watcher_lore.AFTERWORD))
        self.assertTrue(mind.memory["afterword"])
        clock.now += watcher_lore.GAP_S + 1
        self.assertIsNone(mind.remember(), "Book Two's first chapter waits for a great ship")
        page = watcher_lore.page(mind.memory, 60, 700.0)
        self.assertEqual(page["next"]["waits_for"], "A great ship")
        self.assertEqual(page["chapters"][len(watcher_lore.CHAPTERS)]["waits_for"], "A great ship")
        mind.observe("FSSSignalDiscovered", {"SignalName": "CAM-526 Sagan-class Traveller", "SignalType": "Megaship"})
        self.assertEqual(mind.memory["echoes"]["lore_great_ship"][0], 1, "found, whether or not it spoke")
        clock.now += watcher_lore.GAP_S + 1
        self.assertEqual(mind.remember()["text"], watcher_lore.FRAGMENTS[len(book_one_told())][2])
        clock.now += watcher_lore.GAP_S + 1
        self.assertNotEqual((mind.remember() or {}).get("topic"), "lore_afterword", "the afterword is said once ever")

    def test_its_quiet_moments_after_the_story(self):
        surroundings = watcher_idle.Surroundings()
        topics = [topic for topic, _f in surroundings.choices(1_800_000_000.0, Always(), {"story_done": True})]
        self.assertIn("idle_after", topics)
        self.assertNotIn("idle_after", [topic for topic, _f in surroundings.choices(1_800_000_000.0, Always(), {})])
        self.assertEqual(watcher_lines.NORMAL["idle_after"], watcher_lore.AFTER_MUSINGS)
        self.assertGreaterEqual(len(watcher_lore.AFTER_MUSINGS), 30)

    def test_callbacks_to_finished_chapters(self):
        import random

        self.assertIsNone(watcher_lore.recall_choice({"lore": [["salvage", 1.0]]}, random.Random(1), 1_800_000_000.0),
                          "nothing to look back on until a chapter is finished")
        first = [[row[0], 1_799_000_000.0] for row in watcher_lore.FRAGMENTS if row[5] == 0]
        recall = watcher_lore.recall_choice({"lore": first}, random.Random(1), 1_800_000_000.0)
        self.assertEqual(recall["about"], "the salvage")
        self.assertTrue(recall["when"])
        self.assertEqual(recall["When"], recall["when"][:1].upper() + recall["when"][1:])
        for template in watcher_lore.RECALL:
            self.assertTrue(template.format(**recall))
        self.assertEqual(watcher_lore.LORE_REST_S["lore_recall"], 12 * 3600.0)

    def test_achievements_hear_the_story(self):
        import json

        catalogue = {row["id"]: row for row in json.loads((ROOT / "data" / "achievements.json").read_text(encoding="utf-8"))}
        for achievement_id, field in (("watcher_story_begins", "Told"), ("watcher_book_one", "BookOne"),
                                      ("watcher_every_echo", "Echoes"), ("watcher_book_two", "BookTwo")):
            trigger = catalogue[achievement_id]["trigger"]
            self.assertEqual((trigger["event"], trigger["field"]), ("VoidCompassWatcherStory", field))
        self.assertEqual(watcher_lore.progress({}), {"Told": 0, "BookOne": 0, "BookTwo": 0, "Echoes": 0})
        self.assertEqual(watcher_lore.progress({"lore": book_one_told()})["BookOne"], 1)
        clock = Clock()
        mind = watcher(clock=clock)
        mind.session_start()
        self.assertIsNone(mind.story_progress())
        mind.observe("StartJump", {"StarClass": "N"})
        self.assertEqual(mind.story_progress()["Echoes"], 1, "a new kind of echo moves the story on")
        self.assertIsNone(mind.story_progress(), "once")
        dashboard = (ROOT / "src" / "voidcompass" / "dashboard" / "dashboard.py").read_text(encoding="utf-8")
        self.assertEqual(dashboard.count("story_listener = self._watcher_story"), 2)
        self.assertIn('"event": "VoidCompassWatcherStory"', dashboard)


class PageTests(unittest.TestCase):
    def test_the_keepsake_books(self):
        page = watcher_lore.page({"lore": book_one_told(), "afterword": 2.0}, 60, 700.0)
        self.assertEqual([book["title"] for book in page["books"]], ["What the Watcher Remembers"])
        self.assertEqual(len(page["books"][0]["chapters"]), 10)
        self.assertTrue(any(chapter["book"] == 2 for chapter in page["chapters"]), "Book Two shows once Book One is told")
        before = watcher_lore.page({"lore": book_one_told()[:-1]}, 60, 700.0)
        self.assertEqual(before["books"], [])
        self.assertFalse(any(chapter["book"] == 2 for chapter in before["chapters"]))
        script = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        for text in ("READ THE WHOLE STORY", "BOOK TWO", "Waits for", 'id="watcher-books"'):
            self.assertIn(text, script)

    def test_the_long_story_on_the_page(self):
        page = watcher_lore.page({}, 0, 0)
        self.assertEqual((page["told"], page["total"]), (0, len(watcher_lore.FRAGMENTS)))
        self.assertTrue(all(not chapter["begun"] and chapter["title"] == "" for chapter in page["chapters"]),
                        "chapters ahead stay unnamed")
        self.assertEqual(page["next"], {"ready": False, "sessions": 1, "hours": .3, "chapter": "I", "waits_for": ""})
        first_chapter = [row[0] for row in watcher_lore.FRAGMENTS if row[5] == 0]
        memory = {"lore": [[passage, float(i)] for i, passage in enumerate(first_chapter)] + [["instruction", 99.0]]}
        page = watcher_lore.page(memory, 5, 7.0, {"lore_neutron": (3, 50.0)})
        one, two = page["chapters"][0], page["chapters"][1]
        self.assertTrue(one["complete"] and one["account"], "a finished chapter opens its account")
        self.assertEqual((two["title"], two["complete"], two["account"], len(two["told"])), ("The Instruction", False, "", 1))
        self.assertEqual(page["chapters"][2]["title"], "")
        self.assertEqual(page["echoes"], [{"topic": "lore_neutron", "label": "A neutron star", "count": 3, "at": 50.0}])
        self.assertEqual(len(page["echo_labels"]), page["echo_total"])

    def test_the_watcher_page_shows_it(self):
        script = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        for text in ('id="watcher-lore"', "THE LONG STORY", "function renderLore", "AS IT WOULD SET IT DOWN",
                     'id="watcher-echoes"', "Something is surfacing"):
            self.assertIn(text, script)
        python = (ROOT / "src" / "voidcompass" / "dashboard" / "html_dashboard.py").read_text(encoding="utf-8")
        self.assertIn("watcher_lore.page(memory, sessions, hours, _watcher_echoes(memory))", python)


if __name__ == "__main__":
    unittest.main()
