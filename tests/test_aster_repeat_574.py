"""Aster keeps the Watcher's restraint with its own officer wording and memory."""
import json
from pathlib import Path
import random
import re
import string
import tempfile
import unittest
from unittest.mock import patch

from voidcompass.overlays import aster_lines, route_lines, watcher_copilot, watcher_mind, watcher_ship
from voidcompass.overlays.aster_mind import AsterMind, _fingerprint
from tests import test_watcher_long_session_5532 as exploration_fixture


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.

    def __call__(self):
        return self.now


def fields_for(lines):
    return {name: name.replace('_', ' ') for line in lines
            for _, name, _, _ in string.Formatter().parse(line) if name}


class AsterRepeatTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.config = {"companion_identity": "aster", "aster_thoughts": "chatty"}

    def mind(self, path=None, humour="dry", seed=2):
        return AsterMind(path, dict(self.config, aster_humour=humour), clock=self.clock, rng=random.Random(seed))

    def test_every_command_outcome_finishes_each_cycle_without_repeats(self):
        mind = self.mind()
        self.assertTrue(set(watcher_ship.REPLIES) | set(watcher_copilot.REPLIES) <= set(aster_lines.COMMANDS))
        for outcome, templates in aster_lines.COMMANDS.items():
            with self.subTest(outcome=outcome):
                fields = fields_for(templates)
                expected = {line.format(**fields) for line in templates}
                self.assertGreaterEqual(len(expected), 4)
                previous = None
                for _ in range(4):
                    cycle = [watcher_ship.reply(outcome, mind.random, **fields)
                             if outcome in watcher_ship.REPLIES else watcher_copilot.reply(outcome, mind.random, **fields)
                             for _ in templates]
                    self.assertEqual(set(cycle), expected)
                    self.assertEqual(len(cycle), len(set(cycle)))
                    self.assertNotEqual(cycle[0], previous)
                    previous = cycle[-1]

    def test_every_event_has_variety_in_both_commentary_modes(self):
        self.assertEqual(set(aster_lines.EVENTS), set(aster_lines.RESTRAINED_EVENTS))
        for humour in ("dry", "off"):
            for topic in aster_lines.EVENTS:
                with self.subTest(humour=humour, topic=topic):
                    mind = self.mind(humour=humour)
                    templates = aster_lines.event_lines(topic, humour == "off")
                    fields = fields_for(templates)
                    self.assertGreaterEqual(len(templates), 3)
                    keys = []
                    for _ in templates:
                        chosen = mind._variant(topic, fields)
                        self.assertIsNotNone(chosen)
                        key, words = chosen
                        keys.append(key)
                        mind._utter(topic, key, words, self.clock())
                    self.assertEqual(len(keys), len(set(keys)))
                    following = mind._variant(topic, fields)
                    if topic in route_lines.TRAVEL and watcher_mind.frequency(mind.config) == "chatty":
                        # 5.7.5: Chatty's jump-by-jump talk starts a new round, never the last line again.
                        self.assertIsNotNone(following, "Chatty keeps talking through a long trip")
                        self.assertNotEqual(following[0], keys[-1])
                    elif watcher_mind.IMPORTANCE.get(topic, 1) < 2:
                        self.assertIsNone(following, "minor commentary leaves room for silence")
                    else:
                        self.assertIsNotNone(following, "important reports still answer")
                        self.assertNotEqual(following[0], keys[-1], "tied timestamps cannot repeat the last wording")

    def test_chat_cycles_and_commands_resume_after_restart_and_style_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            for phrase, pool in (("Hello Aster", aster_lines.GREETINGS),
                                 ("Aster, what can you do?", aster_lines.CAPABILITIES)):
                mind = self.mind(path)
                heard = []
                for _ in range(len(pool) // 2):
                    mind.talk(phrase)
                    heard.append(mind.thought["text"])
                mind.save()
                mind = self.mind(path)
                for _ in range(len(pool) - len(heard)):
                    mind.talk(phrase)
                    heard.append(mind.thought["text"])
                self.assertEqual(set(heard), set(pool))
                self.assertEqual(len(heard), len(set(heard)))
                for _ in range(2):
                    previous = heard[-1]
                    heard = []
                    for _ in pool:
                        mind.talk(phrase)
                        heard.append(mind.thought["text"])
                    self.assertEqual(set(heard), set(pool))
                    self.assertNotEqual(heard[0], previous)
                mind.save()

            # A smaller plain greeting bank still cycles correctly after
            # switching style, and does not repeat at its own cycle boundary.
            mind = self.mind(path, humour="off")
            for _ in range(3):
                heard = []
                for _ in aster_lines.RESTRAINED_GREETINGS:
                    previous = (mind.thought or {}).get("text")
                    mind.talk("Hello Aster")
                    self.assertNotEqual(mind.thought["text"], previous)
                    heard.append(mind.thought["text"])
                self.assertEqual(set(heard), set(aster_lines.RESTRAINED_GREETINGS))

    def test_all_command_histories_survive_an_interrupted_cycle(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path)
            heard = {}
            for outcome, templates in aster_lines.COMMANDS.items():
                heard[outcome] = [aster_lines.command_reply(outcome, mind.random, fields_for(templates))
                                  for _ in range(len(templates) // 2)]
            mind.save()
            resumed = self.mind(path)
            for outcome, templates in aster_lines.COMMANDS.items():
                with self.subTest(outcome=outcome):
                    cycle = heard[outcome] + [aster_lines.command_reply(outcome, resumed.random, fields_for(templates))
                                             for _ in range(len(templates) - len(heard[outcome]))]
                    self.assertEqual(len(cycle), len(set(cycle)))
                    self.assertNotEqual(aster_lines.command_reply(outcome, resumed.random, fields_for(templates)), cycle[-1])

    def test_old_memory_migrates_greetings_and_event_wording(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            template = aster_lines.EVENTS["quiet"][0]
            key = "aster:quiet:" + _fingerprint(template)
            greeting = aster_lines.GREETINGS[0]
            path.write_text(json.dumps({"said": [[key, self.clock()], ["quiet", self.clock()]],
                                        "log": [[self.clock(), "quiet", template]],
                                        "talk": [{"you": "Hello Aster", "it": greeting}]}), encoding="utf-8")
            mind = self.mind(path)
            self.assertNotEqual(mind.consider("quiet", force=True)["text"], template)
            for _ in range(len(aster_lines.GREETINGS) - 1):
                mind.talk("Hello Aster")
                self.assertNotEqual(mind.thought["text"], greeting)

    def test_command_log_pressure_cannot_erase_event_or_headline_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "aster_memory.json"
            mind = self.mind(path)
            first = mind.consider("quiet", force=True)["text"]
            self.assertIsNotNone(mind.consider("idle_galnet", {"headline": "An existing bulletin"}, force=True))
            for index in range(1600):
                mind._reply(f"Requested report {index}.")
            mind.save()
            self.assertNotIn("quiet", {row[0] for row in json.loads(path.read_text())["said"]})
            resumed = self.mind(path)
            self.assertIsNone(resumed.consider("quiet"), "topic rest survives the rolling log")
            self.assertIsNone(resumed.consider("idle_galnet", {"headline": "An existing bulletin"}, force=True))
            remainder = [resumed.consider("quiet", force=True)["text"]
                         for _ in range(len(aster_lines.EVENTS["quiet"]) - 1)]
            self.assertNotIn(first, remainder)
            self.assertIsNone(resumed.consider("quiet", force=True))

    def test_minor_rest_is_per_template_and_critical_reports_still_speak(self):
        mind = self.mind(humour="off")
        # This idle topic has both a fixed line and templates with a system.
        for _ in aster_lines.RESTRAINED_EVENTS["idle_supercruise"]:
            self.assertIsNotNone(mind.consider("idle_supercruise", {"system": "Sol"}, force=True))
        self.assertIsNone(mind.consider("idle_supercruise", {"system": "Achenar"}, force=True))
        self.clock.now += 86401
        self.assertIn("Achenar", mind.consider("idle_supercruise", {"system": "Achenar"}, force=True)["text"])
        for topic, fields in (("hull_critical", {"hull": 8}), ("danger", {}), ("fuel_low", {"fuel": 4})):
            previous = None
            for _ in range(len(aster_lines.RESTRAINED_EVENTS[topic]) * 3):
                thought = mind.consider(topic, fields, force=True)
                self.assertIsNotNone(thought)
                self.assertNotEqual(thought["text"], previous)
                previous = thought["text"]

    def test_cross_topic_duplicates_are_avoided_and_recent_text_cache_is_bounded(self):
        mind = self.mind()
        shared = aster_lines.EVENTS["hatchling_toy"][0]
        first = mind._utter("hatchling_toy", "aster:hatchling_toy:" + _fingerprint(shared),
                            shared.format(name="Pip", toy="a chunk of Painite"), self.clock())
        # Deliberately introduce a shared template to exercise exact wording
        # protection independently of the hatchling subject cooldown.
        with patch.object(aster_lines, "event_lines", return_value=(shared, *aster_lines.EVENTS["hatchling_trick"])):
            for _ in range(4):
                key, script = mind._variant("hatchling_trick", {"name": "Pip", "toy": "a chunk of Painite", "trick": "spin"})
                thought = mind._utter("hatchling_trick", key, script, self.clock())
                self.assertNotEqual(thought["text"], first["text"])
        for index in range(600):
            mind._utter("arrival", "aster:arrival:" + _fingerprint(aster_lines.EVENTS["arrival"][0]),
                        f"Arrival in sector {index}.", self.clock())
        self.assertEqual(len(mind.memory["aster_texts"]), 512)

    def test_idle_pacing_matches_watcher_across_different_topics_and_restart(self):
        for frequency in ("chatty", "occasional", "rare"):
            with self.subTest(frequency=frequency), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "aster_memory.json"
                mind = self.mind(path)
                mind.config.source["aster_thoughts"] = frequency
                mind.session_start()
                setting = watcher_mind.FREQUENCIES[frequency]
                # Use important contextual observations so Rare has an eligible
                # topic, and remove story timing from this idle-pacing check.
                with patch.object(mind, "remember", return_value=None), \
                        patch.object(mind.surroundings, "choices", return_value=[("revisit", {"system": "Sol", "when": "yesterday"})]), \
                        patch.object(mind.random, "random", return_value=.5):
                    self.clock.now += setting["quiet"] + 1
                    self.assertIsNotNone(mind.tick())
                mind.save()
                resumed = self.mind(path)
                resumed.config.source["aster_thoughts"] = frequency
                resumed._session_start = resumed._counted_until = self.clock()
                resumed._last_interesting = self.clock() - setting["quiet"] - 1
                self.clock.now += setting["quiet"] + 1
                with patch.object(resumed, "remember", return_value=None), \
                        patch.object(resumed.surroundings, "choices", return_value=[("achievement", {"title": "A new record"})]), \
                        patch.object(resumed.random, "random", return_value=.5):
                    self.assertIsNone(resumed.tick(), "another topic cannot bypass the overall idle interval")
                    self.clock.now += setting["mutter"] - setting["quiet"]
                    self.assertIsNotNone(resumed.tick())

    def test_factual_questions_and_relay_keep_the_requested_information(self):
        mind = self.mind()
        mind.lookup_provider = lambda _: ["Our destination is Sol, 12 jumps away."]
        for _ in range(4):
            mind.talk("Aster, where are we headed?")
            self.assertEqual(mind.thought["text"], "Our destination is Sol, 12 jumps away.")
        mind.lookup_provider = lambda _: ["Our destination is Achenar, 8 jumps away."]
        mind.talk("Aster, where are we headed?")
        self.assertEqual(mind.thought["text"], "Our destination is Achenar, 8 jumps away.")
        for _ in range(2):
            self.assertEqual(mind.relay("Requested external report.")["text"], "Requested external report.")
        unavailable = set(aster_lines.COMMANDS["unavailable"])
        self.assertIn(aster_lines.command_reply("screen_open", mind.random, {}), unavailable)

    def test_empty_uplink_and_unrecognised_requests_use_officer_rotations(self):
        mind = self.mind()
        heard = []
        for _ in aster_lines.COMMANDS["plain"]:
            mind.talk("Something outside the command catalogue")
            heard.append(mind.thought["text"])
        self.assertEqual(set(heard), set(aster_lines.COMMANDS["plain"]))
        heard = []
        for _ in aster_lines.COMMANDS["uplink_empty"]:
            mind._uplink = {"said": "Where can I sell platinum?"}
            self.assertTrue(mind.uplink_answer("Where can I sell platinum?", []))
            heard.append(mind.thought["text"])
        self.assertEqual(set(heard), set(aster_lines.COMMANDS["uplink_empty"]))
        watcher = watcher_mind.WatcherMind(None, clock=self.clock)
        watcher._uplink = {"said": "Where can I sell platinum?"}
        watcher.uplink_answer("Where can I sell platinum?", [])
        self.assertEqual(watcher.thought["text"], "The uplink came back empty.")

    def test_same_four_hour_exploration_workload_as_watcher_has_no_repeated_lines(self):
        for humour in ("dry", "off"):
            for seed in (3, 11, 31):
                with self.subTest(humour=humour, seed=seed):
                    def officer(path, config, clock, rng):
                        return AsterMind(path, {"aster_thoughts": config["heartbeat_thoughts"], "aster_humour": humour}, clock=clock, rng=rng)
                    with patch.object(exploration_fixture, "WatcherMind", side_effect=officer):
                        heard = exploration_fixture.session("stoic", seed=seed)
                    # 5.7.5: Chatty's jump-by-jump talk starts new rounds on a long
                    # trip (test_route_talk_575); everything else never repeats.
                    travel = [re.compile(re.sub(r"\\\{\w+\\\}", ".+", re.escape(line)) + "$")
                              for topic in route_lines.TRAVEL for line in aster_lines.event_lines(topic, humour == "off")]
                    others = [line for line in heard if not any(pattern.match(line) for pattern in travel)]
                    self.assertEqual(len(others), len(set(others)), [line for line in set(others) if others.count(line) > 1])
                    self.assertGreater(len(heard), 60, "the officer remains useful through the whole watch")

    def test_shutdown_cycles_complete_across_restarts_and_gaps_longer_than_freshness_window(self):
        for humour in ("dry", "off"):
            for topic in ("sign_off", "sign_off_quiet"):
                with self.subTest(humour=humour, topic=topic), tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "aster_memory.json"
                    previous = None
                    size = len(aster_lines.event_lines(topic, humour == "off"))
                    expected = {f"aster:{topic}:{_fingerprint(line)}" for line in aster_lines.event_lines(topic, humour == "off")}
                    for cycle in range(2):
                        used = set()
                        for index in range(size):
                            mind = self.mind(path, humour=humour, seed=cycle * size + index)
                            mind.observe("LoadGame")
                            self.clock.now += 600
                            mind.observe("Shutdown")
                            thought = mind.note("sign_off", {"summary": "19 jumps" if topic == "sign_off" else ""})
                            self.assertEqual(thought["topic"], topic)
                            self.assertNotEqual(thought["text"], previous)
                            previous = thought["text"]
                            key = mind.memory["aster_event_last"][topic]
                            self.assertNotIn(key, used)
                            used.add(key)
                            self.clock.now += 45 * 86400
                        self.assertEqual(used, expected)

    def test_shutdown_rotation_migrates_recent_wording_and_survives_style_changes(self):
        for topic in ("sign_off", "sign_off_quiet"):
            with self.subTest(topic=topic), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "aster_memory.json"
                fields = {"summary": "19 jumps"} if topic == "sign_off" else {}
                old = self.mind(path, humour="off")
                line = aster_lines.event_lines(topic, True)[0]
                key = f"aster:{topic}:{_fingerprint(line)}"
                old._utter(topic, key, line.format(**fields), self.clock())
                old.save()
                previous = old.thought["text"]
                for humour in ("dry", "off") * 20:
                    mind = self.mind(path, humour=humour)
                    thought = mind.note("sign_off", fields)
                    self.assertNotEqual(thought["text"], previous)
                    previous = thought["text"]
                    self.clock.now += 86400
