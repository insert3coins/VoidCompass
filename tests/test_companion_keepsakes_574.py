"""Keepsakes and deeper company for Aster, Axiom and Meridian (5.7.4)."""
import json
from pathlib import Path
import random
import string
from types import SimpleNamespace
import threading
import unittest

from voidcompass.core import companions
from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
from voidcompass.exploration.flight_log import flight_log
from voidcompass.overlays import companion_personas, watcher_deeper, watcher_mind
from tests.test_aster_companion import Clock

ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ("aster", "axiom", "meridian", "lyra")
KEEPSAKES = {"capsule": {"note": "Remember the rings", "span": "3 weeks", "system": "Sol"},
             "capsule_early": {"system": "Sol", "wait": "2 days"},
             "capsule_shared": {"note": "Fly safe", "span": "a month", "system": "Sol", "sender": "CMDR Ana"},
             "constellation_named": {"name": "The Kettle", "count": 9},
             "on_this_day": {"ago": "A year ago", "system": "Colonia"}}


def mind(identity, **config):
    return companions.create_mind(None, {"companion_identity": identity, f"{identity}_thoughts": "chatty", **config},
                                  clock=Clock(), rng=random.Random(4))


class KeepsakeWordingTests(unittest.TestCase):
    def test_every_watcher_moment_has_each_personas_own_words(self):
        formatter = string.Formatter()
        for identity in PERSONAS:
            lines = companion_personas.get(identity).lines
            for topic in (*KEEPSAKES, "anniversary_us", "dream_told", "watchers_meet", "companion_wish", "companion_wish_reached"):
                with self.subTest(identity=identity, topic=topic):
                    self.assertTrue(lines.event_lines(topic, True), "plain wording")
                    self.assertGreater(len(lines.event_lines(topic)), len(lines.event_lines(topic, True)) - 1)
                    allowed = {name for line in watcher_mind.TOPICS.get(topic, (0, ()))[1]
                               for _, name, _, _ in formatter.parse(line) if name}
                    if allowed and topic != "watchers_meet":  # personas say who they met in one field
                        for line in lines.EVENTS[topic]:
                            self.assertLessEqual({n for _, n, _, _ in formatter.parse(line) if n}, allowed, line)

    def test_note_speaks_keepsakes_in_the_active_companions_voice_and_heading(self):
        for identity in PERSONAS:
            companion = mind(identity)
            companion.session_start()
            for topic, fields in KEEPSAKES.items():
                with self.subTest(identity=identity, topic=topic):
                    companion.clock.now += 60
                    thought = companion.note(topic, fields)
                    self.assertIsNotNone(thought)
                    self.assertEqual(thought["heading"], watcher_mind.HEADED_TOPICS[topic][1])
                    self.assertNotIn("{", thought["text"])
                    self.assertIn(thought["text"].replace(", Commander", ", Commander"),
                                  [line.format(**fields) for line in companion.persona.lines.EVENTS[topic]])

    def test_an_anniversary_of_meeting_is_said_after_the_welcome(self):
        companion = mind("meridian")
        companion.memory["first_seen"] = companion.clock.now - 365 * 86400 - 3600 * 0
        companion.memory["sessions"] = 4
        companion.session_start()
        self.assertIn("anniversary_us", [topic for topic, _ in companion._say_next])
        companion.clock.now += 120
        companion._last_spoke = companion._last_interesting = companion.clock.now - 60
        thought = companion.tick({})
        self.assertEqual(thought["topic"], "anniversary_us")
        self.assertIn("year", thought["text"])


class DeeperCompanyTests(unittest.TestCase):
    def test_after_watch_notes_are_written_kept_and_told(self):
        for identity in PERSONAS:
            companion = mind(identity)
            companion.session_start()
            companion.observe("FSDJump", {"StarSystem": "Achenar"})
            companion.observe("Docked", {"StationName": "Dawes Hub", "StarSystem": "Achenar"})
            companion.observe("Shutdown", {})
            note = companion.memory["dreams"][-1]["text"]
            self.assertNotIn("{", note)
            self.assertTrue(note[:1].isupper())
            companion.random.random = lambda: 0.0
            companion.clock.now += 86400
            companion.session_start()
            told = dict(companion._say_next)["dream_told"]["dream"]
            self.assertEqual(told, note)
            deeper = HtmlDashboardMixin._companion_deeper(SimpleNamespace(config={}), companion)
            self.assertEqual(deeper["notes_title"], companion.persona.keepsakes.NOTES_TITLE)
            self.assertEqual(deeper["dreams"][0]["text"], note)

    def test_readings_move_with_real_events_and_use_their_own_labels(self):
        for identity in PERSONAS:
            companion = mind(identity)
            companion.session_start()
            companion.observe("SellExplorationData", {"StarSystem": "Sol"})
            companion.observe("RepairAll", {})
            self.assertGreater(companion.memory["trust"], watcher_deeper.TRUST_START)
            companion.observe("Died", {})
            deeper = HtmlDashboardMixin._companion_deeper(SimpleNamespace(config={}), companion)
            labels = [label for label, _words in companion.persona.keepsakes.FEELING.values()]
            self.assertEqual(deeper["feeling"]["labels"], labels)
            self.assertIn(deeper["feeling"]["trust"], companion.persona.keepsakes.FEELING["trust"][1])
            self.assertEqual(deeper["feeling"]["story"]["title"], "Not begun")

    def test_the_request_comes_once_after_its_chapter_and_is_noticed_on_arrival(self):
        arrivals = {"aster": ("FSDJump", {"StarSystem": "Home", "StarPos": [0, 0, 0]}),
                    "axiom": ("Scan", {"BodyName": "BH", "StarType": "H"}),
                    "meridian": ("FSDJump", {"StarSystem": "Rim", "StarPos": [0, 0, 26000 + 39000]}),
                    "lyra": ("Scan", {"BodyName": "Fresh A", "StarType": "K", "DistanceFromArrivalLS": 0,
                                      "WasDiscovered": False})}
        for identity in PERSONAS:
            with self.subTest(identity=identity):
                companion = mind(identity)
                companion.memory["sessions"] = 2
                companion.session_start()
                companion.observe("FSDJump", {"StarSystem": "Home", "StarPos": [0, 0, 0]})
                story, spec = companion.persona.story, companion.persona.keepsakes.WISH
                index = next(i for i, chapter in enumerate(story.chapters) if chapter["numeral"] == spec["after"])
                companion.memory["lore"] = [[row[0], companion.clock.now] for row in story.passages if row[4] < index]
                self.assertIsNone(companion._wish(companion.clock.now), "not before its chapter is complete")
                companion.memory["lore"] = [[row[0], companion.clock.now - 7200] for row in story.passages if row[4] <= index]
                asked = companion._wish(companion.clock.now)
                self.assertEqual(asked["heading"], "A REQUEST")
                self.assertIsNone(companion._wish(companion.clock.now), "asked once")
                deeper = HtmlDashboardMixin._companion_deeper(SimpleNamespace(config={}), companion)
                self.assertTrue(deeper["pilgrimage"]["asked"])
                self.assertFalse(deeper["pilgrimage"]["reached"])
                companion.observe(*arrivals[identity])
                self.assertTrue(companion.memory["pilgrimage"]["reached"])
                self.assertIn("companion_wish_reached", [topic for topic, _ in companion._say_next])
                self.assertEqual(companion.story_progress()[f"{identity.capitalize()}Request"], 1)

    def test_share_codes_meet_across_every_kind_of_companion(self):
        aster, axiom = mind("aster"), mind("axiom")
        card = watcher_deeper.read_code(watcher_deeper.share_code(aster.share_card("Jeff")))
        self.assertEqual(card["companion"], "aster")
        met = axiom.meet(card)
        self.assertIn("Another commander's Aster", met["text"])
        self.assertIsNone(axiom.meet(card), "the same companion is met once")
        watcher = companions.create_mind(None, {"companion_identity": "watcher", "heartbeat_thoughts": "chatty"},
                                         clock=Clock(), rng=random.Random(1))
        said = watcher.meet(card)
        self.assertEqual(said["topic"], "watchers_meet_other")
        self.assertIn("an officer called aster", said["text"].casefold())
        self.assertNotIn("another of me", said["text"])
        old = watcher_deeper.read_code(watcher_deeper.share_code({"name": "Old", "nature": "weary", "hours": 3}))
        self.assertEqual(old["companion"], "watcher", "codes made before 5.7.4 are Watchers")


class AchievementAndLogTests(unittest.TestCase):
    def test_story_achievements_listen_for_each_personas_progress(self):
        rows = [row for row in json.loads((ROOT / "data" / "achievements.json").read_text(encoding="utf-8"))
                if row["id"].split("_")[0] in PERSONAS]
        self.assertEqual(len(rows), 16)
        for identity in PERSONAS:
            companion = mind(identity)
            companion._story_changed = True
            progress = companion.story_progress()
            fields = {row["trigger"]["field"] for row in rows if row["id"].startswith(identity)}
            self.assertLessEqual(fields, set(progress))
            self.assertTrue(all(row["trigger"]["event"] == "VoidCompassWatcherStory" for row in rows))

    def test_the_captains_log_paragraph_is_written_by_the_companion_on_watch(self):
        session = {"started": "2026-11-05T10:00:00Z", "ended": "2026-11-05T12:00:00Z", "start_system": "Sol",
                   "end_system": "Colonia", "first_discoveries": 2}
        self.assertEqual(flight_log(session)["companion_name"], "the Watcher")
        for identity in PERSONAS:
            log = flight_log({**session, "companion": identity})
            self.assertEqual(log["companion"], identity)
            self.assertEqual(log["companion_name"], companions.NAMES[identity])
            self.assertEqual(log["words"], flight_log({**session, "companion": identity})["words"], "the same words each reading")
            self.assertIn(log["words"].split(". ")[-1].rstrip("."), " ".join(companion_personas.get(identity).keepsakes.LOG["closings"]))

    def test_live_sessions_are_stamped_and_a_switch_hands_them_over(self):
        from voidcompass.dashboard.dashboard import MainDashboard
        log = SimpleNamespace(lock=threading.Lock(), data={"sessions": [{"started": "a", "ended": None}]}, save=lambda: None)
        deck = SimpleNamespace(captains_log=log, config={"companion_identity": "axiom"})
        MainDashboard._stamp_session_companion(deck)
        self.assertEqual(log.data["sessions"][-1]["companion"], "axiom")
        deck.config["companion_identity"] = "meridian"
        MainDashboard._stamp_session_companion(deck)
        self.assertEqual(log.data["sessions"][-1]["companion"], "axiom", "an ordinary event keeps the first stamp")
        MainDashboard._stamp_session_companion(deck, switched=True)
        self.assertEqual(log.data["sessions"][-1]["companion"], "meridian")
        log.data["sessions"][-1]["ended"] = "b"
        deck.config["companion_identity"] = "aster"
        MainDashboard._stamp_session_companion(deck, switched=True)
        self.assertEqual(log.data["sessions"][-1]["companion"], "meridian", "a finished session keeps its companion")


class CopyTests(unittest.TestCase):
    def test_shared_settings_no_longer_assume_the_watchers_orb(self):
        script = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        self.assertNotIn("beside the orb", script)
        self.assertNotIn("The Watcher's orb overlay", script)
        from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS
        labels = [row[2] for row in OVERLAY_HOTKEY_SPECS if isinstance(row, tuple) and str(row[0]).startswith("watcher_")]
        self.assertTrue(labels and all(label.startswith("Companion:") for label in labels))


if __name__ == "__main__":
    unittest.main()
