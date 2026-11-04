"""The hatchling's separate timer cannot bypass Aster's restraint or replay moments."""
import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from voidcompass.dashboard.dashboard_games_mixin import DashboardGamesMixin
from voidcompass.overlays.aster_mind import AsterMind


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.

    def __call__(self):
        return self.now


class HatchlingDeck(DashboardGamesMixin):
    def __init__(self, mind):
        self.config = mind.config.source
        self.heartbeat_hud = SimpleNamespace(mind=mind, note=mind.note)
        self.state = {"pet": {"name": "Pip", "born": mind.clock() - 3600, "stage": "hatchling",
                              "dormant_since": None, "asleep": False, "moment": None}}
        self._hatchling_chat = Mock()
        self._hatchling_sync_trip = Mock()
        self._hatchling_overlay_refresh = Mock()

    def _hatchling_state(self):
        return self.state

    def _hatchling_watcher_seen(self, side=None):
        return None


class AsterHatchlingTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def mind(self, path=None, humour="dry", frequency="chatty"):
        return AsterMind(path, {"companion_identity": "aster", "aster_thoughts": frequency, "aster_humour": humour},
                         clock=self.clock, rng=random.Random(3))

    def moment(self, ident, **fields):
        return {"name": "Pip", "_moment_id": ident, "_moment_at": self.clock(), **fields}

    def test_four_hour_watch_includes_actual_hatchling_timer_and_normal_idle_tick(self):
        for humour in ("dry", "off"):
            with self.subTest(humour=humour):
                self.clock = Clock()
                mind = self.mind(humour=humour)
                deck = HatchlingDeck(mind)
                mind.session_start()
                heard, pet_times = [], []
                start = self.clock()
                with patch("voidcompass.dashboard.dashboard_games_mixin.time.time", self.clock), \
                        patch("voidcompass.dashboard.dashboard_games_mixin.time.monotonic", self.clock), \
                        patch.object(mind.random, "random", return_value=0.):
                    for minute in range(241):
                        self.clock.now = start + minute * 60
                        before = mind._serial
                        deck._hatchling_tick()
                        if mind._serial != before:
                            heard.append(mind.thought["text"])
                            pet_times.append(self.clock())
                        thought = mind.tick()
                        if thought:
                            heard.append(thought["text"])
                self.assertGreaterEqual(len(pet_times), 2, "the real timer reaches the mind")
                self.assertLessEqual(len(pet_times), 8, "pet remarks cannot arrive every few minutes")
                self.assertTrue(all(right - left >= 1800 for left, right in zip(pet_times, pet_times[1:])))
                self.assertEqual(len(heard), len(set(heard)), "the pet-enabled watch has no repeated lines")

    def test_replayed_growth_moment_is_silent_across_restart_and_log_rollover(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path)
            deck = HatchlingDeck(mind)
            deck.state["pet"]["moment"] = {"kind": "grown", "at": self.clock(), "form": "hatchling"}
            with patch("voidcompass.dashboard.dashboard_games_mixin.time.time", self.clock):
                deck._hatchling_watcher()
                self.assertIn("hatchling", mind.thought["text"])
                self.assertEqual(mind._serial, 1)
                for index in range(1600):
                    mind._reply(f"Requested report {index}.")
                mind.save()
                resumed = self.mind(path)
                restarted = HatchlingDeck(resumed)
                restarted.state = deck.state
                self.clock.now += 30
                restarted._hatchling_watcher()
                self.assertIsNone(resumed.thought, "the growth force flag cannot re-announce the same moment")
                restarted.state["pet"]["moment"] = {"kind": "grown", "at": self.clock(), "form": "juvenile"}
                restarted._hatchling_watcher()
                self.assertIn("juvenile", resumed.thought["text"], "a genuinely new growth stage still gets its notice")
            self.assertEqual(len(json.loads(path.read_text())["aster_hatchling_seen"]), 1)

    def test_old_moment_is_not_announced_as_new_on_startup(self):
        mind = self.mind()
        deck = HatchlingDeck(mind)
        deck.state["pet"]["moment"] = {"kind": "trick", "at": self.clock() - 3600, "trick": "spin"}
        deck._hatchling_watcher()
        self.assertIsNone(mind.thought)

    def test_forced_tricks_still_obey_subject_rest_but_new_growth_can_speak(self):
        mind = self.mind()
        first = self.moment("first", trick="spin")
        self.assertIsNotNone(mind.note("hatchling_trick", first))
        self.clock.now += 60
        another = self.moment("another", trick="wave")
        self.assertIsNone(mind.note("hatchling_trick", another))
        self.assertEqual(len(mind.memory["aster_hatchling_seen"]), 2, "a deferred event is consumed too")
        self.clock.now += 601
        third = self.moment("third", trick="roll")
        self.assertIn("roll", mind.note("hatchling_trick", third)["text"])
        grown = self.moment("grown", form="juvenile")
        self.assertIn("juvenile", mind.note("hatchling_grown", grown)["text"])
        self.assertIsNone(mind.note("hatchling_grown", grown))

    def test_hatchling_subject_rest_and_global_idle_rest_work_in_both_directions(self):
        mind = self.mind()
        mind.session_start()
        with patch.object(mind.random, "random", return_value=0.):
            self.clock.now += 121
            self.assertIsNotNone(mind.note("hatchling_idle", {"name": "Pip"}))
            self.clock.now += 600
            self.assertIsNone(mind.consider("hatchling_said", {"name": "Pip", "said": "Lovely stars"}, force=True))
            self.clock.now += 1201
            self.assertIsNotNone(mind.consider("hatchling_said", {"name": "Pip", "said": "Lovely stars"}, force=True))
            self.assertIsNone(mind.tick(), "a pet remark is an idle remark for overall pacing")
            self.clock.now += 1801
            mind._utter("quiet", "a fresh quiet remark", "A quiet interval.", self.clock())
            self.assertIsNone(mind.consider("hatchling_idle", {"name": "Pip"}, force=True))
            self.clock.now += 301
            self.assertIsNotNone(mind.consider("hatchling_idle", {"name": "Pip"}, force=True))

    def test_no_passive_pet_chatter_during_reports_activity_or_danger(self):
        mind = self.mind()
        self.clock.now += 1801
        mind._reply("Requested cargo report.")
        self.assertIsNone(mind.consider("hatchling_idle", {"name": "Pip"}, force=True))
        self.clock.now += 301
        mind._last_interesting = self.clock()
        self.assertIsNone(mind.consider("hatchling_idle", {"name": "Pip"}, force=True))
        mind._in_danger = True
        growth = self.moment("growing in danger", form="juvenile")
        self.assertIsNone(mind.note("hatchling_grown", growth))
        self.assertIsNotNone(mind.consider("hull_critical", {"hull": 8}, force=True))
        mind.talk("Hello Aster")
        self.assertEqual(mind.thought["topic"], "talk", "direct requests still answer")

    def test_specific_event_reports_include_the_actual_toy_trick_and_form(self):
        for humour in ("dry", "off"):
            for kind, label, value in (("toy", "toy", "a chunk of Painite"), ("trick", "trick", "spin"),
                                       ("grown", "form", "juvenile")):
                with self.subTest(humour=humour, kind=kind):
                    mind = self.mind(humour=humour)
                    with patch.object(mind.random, "random", return_value=0.):
                        thought = mind.note("hatchling_" + kind, self.moment(kind, **{label: value}))
                    self.assertIsNotNone(thought)
                    self.assertIn(value, thought["text"])
                    self.assertIn("Pip", thought["text"])

    def test_moment_cache_is_bounded_and_older_topic_history_seeds_subject_rest(self):
        mind = self.mind()
        for index in range(150):
            mind.note("hatchling_grown", self.moment(f"moment-{index}", form="juvenile"))
        self.assertEqual(len(mind.memory["aster_hatchling_seen"]), 128)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            path.write_text(json.dumps({"said": [["aster:hatchling_trick:old", self.clock()], ["hatchling_trick", self.clock()]],
                                        "log": [[self.clock(), "hatchling_trick", "An earlier pet report."]]}))
            resumed = self.mind(path)
            self.clock.now += 301
            self.assertIsNone(resumed.consider("hatchling_idle", {"name": "Pip"}, force=True))
