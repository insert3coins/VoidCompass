"""Real logins receive a welcome; fallback wakes and duplicate delivery stay singular."""
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock

from voidcompass.overlays import aster_lines, watcher_name
from voidcompass.overlays.aster_mind import AsterMind, _fingerprint
from voidcompass.overlays.heartbeat_hud import HeartbeatHUD


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.

    def __call__(self):
        return self.now


class AsterLoginTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def mind(self, path=None, frequency="rare", humour="dry"):
        return AsterMind(path, {"companion_identity": "aster", "aster_thoughts": frequency,
                               "aster_humour": humour, "aster_voice_level": "important"},
                         clock=self.clock, rng=random.Random(8))

    def login(self):
        return {"event": "LoadGame", "timestamp": datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                "Commander": "NightOwl", "FID": "F1"}

    def test_each_real_load_game_welcomes_even_during_a_quick_relog(self):
        for frequency in ("rare", "occasional", "chatty"):
            for humour in ("dry", "off"):
                with self.subTest(frequency=frequency, humour=humour):
                    mind = self.mind(frequency=frequency, humour=humour)
                    first = mind.observe("LoadGame", self.login())
                    self.assertEqual(first["topic"], "greet_new")
                    for index in range(5):
                        self.clock.now += 15
                        if index % 2:
                            mind.observe("Shutdown")
                            self.clock.now += 1
                        thought = mind.observe("LoadGame", self.login())
                        self.assertEqual(thought["topic"], "greet_away")
                        self.assertNotEqual(first["text"], thought["text"])
                        first = thought
                    self.assertEqual(mind.memory["sessions"], 6)
                    self.assertEqual(mind.memory["name"]["seen"], 6)

    def test_an_earlier_journal_wake_does_not_swallow_a_later_login(self):
        mind = self.mind()
        greeting = mind.observe("Location", {"StarSystem": "Sol"})
        self.assertEqual(greeting["topic"], "greet_new")
        self.clock.now += 60
        login = mind.observe("LoadGame", self.login())
        self.assertEqual(login["topic"], "greet_away")
        self.assertEqual(mind.memory["sessions"], 2)

    def test_immediate_early_wake_is_one_welcome_and_one_counted_watch(self):
        for source in ("journal", "port"):
            with self.subTest(source=source):
                mind = self.mind()
                if source == "journal":
                    greeting = mind.observe("Rank", {})
                else:
                    greeting = mind.tick({"port": {"live": True, "docked": True, "station": "Galileo"}})
                self.assertEqual(greeting["topic"], "greet_new")
                self.clock.now += 2
                self.assertIsNone(mind.observe("LoadGame", self.login()))
                self.assertEqual(mind.memory["sessions"], 1)
                self.assertEqual(mind.memory["name"]["seen"], 1)
                self.assertEqual(mind.thought["id"], greeting["id"])
                self.clock.now += 2
                # A second distinct LoadGame is a real relog, even inside
                # the early-wake grace period after a confirmed login.
                self.assertEqual(mind.observe("LoadGame", self.login())["topic"], "greet_away")
                self.assertEqual(mind.memory["sessions"], 2)

    def test_duplicate_timestamped_login_is_ignored_and_remembered_across_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path)
            event = self.login()
            welcome = mind.observe("LoadGame", event)
            for _ in range(3):
                self.clock.now += 60
                self.assertIsNone(mind.observe("LoadGame", dict(event)))
                self.assertEqual(mind.thought["id"], welcome["id"])
            self.assertEqual(mind.memory["sessions"], 1)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["log"][-1][1:], [welcome["topic"], welcome["text"]])
            resumed = self.mind(path)
            self.assertIsNone(resumed.observe("LoadGame", event))
            self.assertEqual(resumed.memory["sessions"], 1)
            self.clock.now += 1
            self.assertEqual(resumed.observe("LoadGame", self.login())["topic"], "greet_away")

    def test_missing_timestamp_does_not_misidentify_real_loads_as_duplicates(self):
        mind = self.mind()
        self.assertIsNotNone(mind.observe("LoadGame", {}))
        for _ in range(3):
            self.clock.now += 10
            self.assertIsNotNone(mind.observe("LoadGame", {}))
        self.assertEqual(mind.memory["sessions"], 4)

    def test_welcome_rotation_survives_restarts_long_gaps_and_bank_exhaustion(self):
        for humour in ("dry", "off"):
            with self.subTest(humour=humour), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "aster_memory.json"
                mind = self.mind(path, humour=humour)
                mind.observe("LoadGame", self.login())
                variants = aster_lines.event_lines("greet_away", humour == "off")
                expected = {f"aster:greet_away:{_fingerprint(line)}" for line in variants}
                previous = None
                for _ in range(2):
                    used = set()
                    for _ in variants:
                        self.clock.now += 45 * 86400
                        mind = self.mind(path, humour=humour)
                        welcome = mind.observe("LoadGame", self.login())
                        self.assertEqual(welcome["topic"], "greet_away")
                        self.assertNotEqual(welcome["text"], previous)
                        previous = welcome["text"]
                        key = mind.memory["aster_event_last"]["greet_away"]
                        self.assertNotIn(key, used)
                        used.add(key)
                    self.assertEqual(used, expected)

    def test_quick_login_uses_the_approved_address_and_off_remains_silent(self):
        mind = self.mind()
        watcher_name.observe(mind.memory, "Commander", {"Name": "NightOwl", "FID": "F1"})
        watcher_name.set_call(mind.memory, "nickname", "Jeff")
        heard = [mind.observe("LoadGame", self.login())["text"]]
        for _ in aster_lines.EVENTS["greet_away"]:
            self.clock.now += 10
            heard.append(mind.observe("LoadGame", self.login())["text"])
        self.assertTrue(any("Jeff" in words for words in heard))
        self.assertTrue(all("Commander" not in words for words in heard))
        off = self.mind(frequency="off")
        self.assertIsNone(off.observe("LoadGame", self.login()))
        self.clock.now += 10
        self.assertIsNone(off.observe("LoadGame", self.login()))
        self.assertFalse(off.memory["aster_welcomes"], "muted logins do not consume welcome wording")

    def test_live_hud_load_game_queues_each_welcome_once_at_the_selected_voice_level(self):
        mind = self.mind()
        mind.voice_active = True
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        hud.config, hud.mind = mind.config.source, mind
        hud._pulse_serial = hud._event_serial = 0
        hud._activity_state = "FLIGHT"
        hud._events = deque(maxlen=32)
        hud._check_profile = lambda: None
        hud._spoken_id = hud._voice_caption = None
        hud._voice_thoughts = {}
        hud.voice_listener = Mock(return_value=True)
        hud.voice_status_listener = lambda _: "queued"
        hud.thought_side = lambda: "right"
        payloads = []
        hud._redraw = lambda: payloads.append(hud._thought_payload())
        first = self.login()
        hud.pulse("journal", "LoadGame", "FLIGHT", first)
        self.clock.now += 10
        second = self.login()
        hud.pulse("journal", "LoadGame", "FLIGHT", second)
        hud.pulse("journal", "LoadGame", "FLIGHT", dict(second))
        self.assertEqual(hud.voice_listener.call_count, 2)
        calls = hud.voice_listener.call_args_list
        self.assertNotEqual(calls[0].args[0], calls[1].args[0])
        self.assertNotEqual(calls[0].args[1], calls[1].args[1])
        self.assertEqual(len(hud._voice_thoughts), 2, "the second welcome joins the speech queue")
        self.assertTrue(all(payload["voice_state"] == "queued" for payload in payloads))


if __name__ == "__main__":
    unittest.main()
