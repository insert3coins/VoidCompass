"""Aster's short, original name introduction shares the existing preference and answer paths."""
from pathlib import Path
import random
import tempfile
import unittest

from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.overlays import aster_name, watcher_name, watcher_questions
from voidcompass.overlays.aster_mind import AsterMind
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.

    def __call__(self):
        return self.now


class AsterNameTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.config = {"companion_identity": "aster", "aster_thoughts": "chatty"}

    def mind(self, path=None, known=True):
        mind = AsterMind(path, self.config, clock=self.clock, rng=random.Random(3))
        if known:
            mind.observe("LoadGame", {"Commander": "insert3coins", "FID": "F1"})
        else:
            mind.session_start()
        return mind

    def introduce(self, mind):
        self.clock.now += 901
        notice = mind.tick()
        self.assertEqual(notice["topic"], "aster_name_notice")
        self.clock.now += aster_name.GAP_S + 1
        question = mind.tick()
        self.assertEqual(question["topic"], "aster_name_ask")
        return notice, question

    def test_three_short_parts_then_approved_name_once_a_session(self):
        mind = self.mind()
        self.assertIsNone(mind.tick())
        self.clock.now += 899
        self.assertFalse((mind.tick() or {}).get("topic", "").startswith("aster_name_"))
        # The ordinary story/idle tick may have spoken; leave a real quiet gap.
        self.clock.now += 121
        notice = mind.tick()
        self.assertEqual(notice["heading"], "THE CREW REGISTER · 1 OF 3")
        self.assertIn("insert3coins", notice["text"])
        self.clock.now += 120
        self.assertIsNone(mind.tick(), "the short introduction has room before its question")
        self.clock.now += 61
        question = mind.tick()
        self.assertEqual(question["heading"], "THE CREW REGISTER · 2 OF 3")
        self.assertEqual([row["key"] for row in question["question"]["answers"]], ["yes", "commander", "other"])
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud.mind = mind
        hud._redraw = lambda: None
        first = hud.answer(1)
        self.assertEqual(first["heading"], "THE CREW REGISTER · 3 OF 3")
        self.assertIn("insert3coins", first["text"])
        self.assertEqual(watcher_name.call_name(mind.memory), "insert3coins")
        self.assertIsNone(watcher_name.may_name(mind.memory, mind._session_start))
        self.clock.now += 3600
        mind._session_start = self.clock()
        first = mind._utter("greet_away", "greet-one", "Welcome back, Commander.", self.clock())
        second = mind._utter("greet_away", "greet-two", "Welcome back, Commander.", self.clock())
        self.assertEqual(first["text"], "Welcome back, insert3coins.")
        self.assertEqual(second["text"], "Welcome back, Commander.")
        self.assertIsNone(mind._name_step(self.clock() + 301))

    def test_commander_choice_is_respected_and_does_not_nag(self):
        mind = self.mind()
        self.introduce(mind)
        thought = mind.answer("commander")
        self.assertIn("Commander", thought["text"])
        self.assertNotIn("insert3coins", thought["text"])
        self.assertIsNone(watcher_name.call_name(mind.memory))
        self.clock.now += 30 * 86400
        self.assertIsNone(mind._name_step(self.clock()))
        self.assertIsNone(mind.ask("your_name", force=True))

    def test_spoken_refusal_and_polite_nickname_requests_are_understood(self):
        for phrase, expected in (("No thanks", None), ("Aster, please call me Jeff", "Jeff"),
                                 ("You can call me Jeff, please", "Jeff")):
            with self.subTest(phrase=phrase):
                mind = self.mind()
                self.introduce(mind)
                self.assertTrue(mind.talk(phrase, voice=True))
                self.assertEqual(watcher_name.call_name(mind.memory), expected)
                self.assertIsNone(mind.pending_question())

    def test_nickname_can_be_given_by_typed_or_recognised_speech(self):
        for voice in (False, True):
            with self.subTest(voice=voice):
                mind = self.mind()
                self.introduce(mind)
                self.assertTrue(mind.talk("Aster, call me Jeff", voice=voice))
                self.assertEqual(watcher_name.call_name(mind.memory), "Jeff")
                self.assertIn("Jeff", mind.thought["text"])
                self.assertEqual(mind.memory["talk"][-1]["it"], mind.thought["text"])
                self.assertEqual(bool(mind.memory["talk"][-1].get("voice")), voice)
                watcher_name.set_spoken(mind.memory, "Jef")
                self.assertEqual(mind.spoken_words({"text": "Jeff, ready to proceed."}), "Jef, ready to proceed.")

    def test_other_answer_can_wait_for_a_nickname_across_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path)
            self.introduce(mind)
            mind.answer("other")
            self.assertIn("YOUR NAME", mind.thought["text"])
            self.assertIsNone(mind.pending_question())
            resumed = self.mind(path)
            self.assertTrue(resumed.talk("Call me Jeff"))
            self.assertEqual(watcher_name.call_name(resumed.memory), "Jeff")
            self.assertTrue(resumed.name_page()["story"]["complete"])
            self.assertEqual(len(resumed.name_page()["story"]["told"]), 3)

    def test_question_and_completed_introduction_survive_restart_without_repeating(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            untouched = Path(folder) / "watcher_memory.json"
            untouched.write_text('{"story":"unchanged"}')
            mind = self.mind(path)
            self.introduce(mind)
            self.clock.now += 30
            resumed = self.mind(path)
            self.assertEqual(resumed.pending_question()["id"], "your_name")
            resumed.answer("yes")
            completed = self.mind(path)
            self.assertIsNone(completed.pending_question())
            self.clock.now += 600
            self.assertIsNone(completed._name_step(self.clock()))
            self.assertEqual(completed.name_page()["told"], ["notice", "ask", "first"])
            self.assertEqual(untouched.read_text(), '{"story":"unchanged"}')

    def test_unanswered_question_expires_and_cannot_be_forced_into_repetition(self):
        mind = self.mind()
        self.introduce(mind)
        self.clock.now += watcher_questions.UNANSWERED_S + 1
        self.assertIsNone(mind.pending_question())
        self.assertIsNone(mind.answer("yes"))
        self.assertIsNone(mind.ask("your_name", force=True))
        self.assertIsNone(watcher_name.record(mind.memory).get("call"))
        self.clock.now += watcher_questions.ASK_REST_S
        self.assertIsNotNone(mind.ask("your_name"))
        self.assertEqual(mind.memory["questions"]["your_name"]["times"], 2)
        self.assertEqual(len(mind.name_page()["story"]["told"]), 2, "the introduction was not retold")

    def test_manual_preferences_are_honoured_before_and_during_the_introduction(self):
        mind = self.mind()
        watcher_name.set_call(mind.memory, "nickname", "Jeff")
        self.clock.now += 901
        mind._account_time()
        self.assertIsNone(mind._name_step(self.clock()))
        self.assertIsNone(mind.pending_question())
        another = self.mind()
        self.introduce(another)
        watcher_name.set_call(another.memory, "commander")
        self.assertIsNone(another.pending_question())
        self.assertIsNone(another.answer("yes"), "an old question cannot override a manual preference")
        self.clock.now += 121
        self.assertIn("Commander", another._name_step(self.clock())["text"])

    def test_no_invented_name_or_intro_during_danger_activity_or_thoughts_off(self):
        unknown = self.mind(known=False)
        self.clock.now += 1000
        unknown._account_time()
        self.assertIsNone(unknown._name_step(self.clock()))
        mind = self.mind()
        self.clock.now += 1000
        mind._account_time()
        mind._in_danger = True
        self.assertIsNone(mind._name_step(self.clock()))
        mind._in_danger = False
        mind._last_interesting = self.clock()
        self.assertIsNone(mind._name_step(self.clock()))
        self.clock.now += 121
        self.config["aster_thoughts"] = "off"
        self.assertIsNone(mind._name_step(self.clock()))

    def test_naming_answers_do_not_take_over_unrelated_commands_or_other_watcher_questions(self):
        mind = self.mind()
        self.introduce(mind)
        mind.action_provider = lambda text: "Opening the system map."
        mind.talk("Aster, open the system map")
        self.assertEqual(mind.thought["text"], "Opening the system map.")
        self.assertIsNotNone(mind.pending_question())
        self.assertIsNone(mind.ask("shutter", force=True))
        self.assertTrue(mind.talk("yes please"))
        self.assertEqual(watcher_name.call_name(mind.memory), "insert3coins")

    def test_journal_rename_uses_officer_wording_without_restarting_the_arc(self):
        mind = self.mind()
        self.introduce(mind)
        mind.answer("yes")
        mind.observe("LoadGame", {"Commander": "NightOwl", "FID": "F1"})
        self.clock.now += 121
        thought = mind.tick()
        self.assertEqual(thought["topic"], "aster_name_renamed")
        self.assertIn("NightOwl", thought["text"])
        self.assertIn("insert3coins", thought["text"])
        self.assertEqual(watcher_name.call_name(mind.memory), "NightOwl")
        self.assertTrue(mind.name_page()["story"]["complete"])

    def test_deck_question_hotkeys_heard_passages_and_book_export_use_new_arc(self):
        mind = self.mind()
        notice, question = self.introduce(mind)
        class Deck(HtmlDashboardMixin):
            config = {"companion_identity": "aster", "overlay_hotkey_watcher_answer_1": "Alt+1"}
            def _watcher_mind(self):
                return mind
        deck = Deck()
        deeper = deck._html_watcher_deeper(mind)
        self.assertEqual(deeper["question"]["text"], question["text"])
        self.assertEqual(deeper["hotkeys"][0], "Alt+1")
        mind.answer("yes")
        with tempfile.TemporaryDirectory() as folder:
            deck.wrapped_folder = lambda: folder
            self.assertTrue(deck._watcher_save_book())
            book = next(Path(folder).glob('*.html')).read_text(encoding='utf-8')
            self.assertIn(notice["text"], book)
            self.assertIn(mind.thought["text"], book)
        self.assertEqual(len(mind.name_page()["story"]["told"]), 3)

    def test_reset_backs_up_and_reopens_only_this_companions_name_introduction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path)
            self.introduce(mind)
            mind.answer("yes")
            backup = mind.reset()
            self.assertTrue(Path(backup).is_file())
            self.assertFalse(mind.name_page()["story"]["told"])
            self.assertFalse(mind.name_page()["known"])
