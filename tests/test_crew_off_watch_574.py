"""The crew off watch (5.7.4): ask a crewmate by name in TALK, a crewmate's
line at a big moment, and a new companion starting at the Watcher's pace."""
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from voidcompass.core import companions
from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin
from voidcompass.overlays import crew_voices, meridian_lines, watcher_copilot
from voidcompass.voice.watcher_voice import WatcherSpeaker
from tests.test_aster_companion import Clock

ROOT = Path(__file__).resolve().parents[1]
CREW = ["watcher", "aster", "axiom", "meridian"]


def mind(identity, frequency="chatty", flown=CREW, seed=2):
    config = {"companion_identity": identity, f"{identity}_thoughts": frequency, "heartbeat_thoughts": frequency}
    companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(seed))
    companion.lookup_provider = lambda question: ["Colonia is 22,000 ly away."]
    companion.session_start()
    companion.learn({"crew": {"flown": list(flown)}})
    return companion


class AddressTests(unittest.TestCase):
    def test_a_crewmate_by_name_but_never_the_one_on_watch(self):
        cases = {"Meridian, how far to Colonia?": ("meridian", "how far to Colonia?"),
                 "ask Axiom what is in this system": ("axiom", "what is in this system"),
                 "hey Meridian": ("meridian", "hello"),
                 "The Watcher: are you there?": ("watcher", "are you there?"),
                 "Axiom how many bodies are here": ("axiom", "how many bodies are here")}
        for text, expected in cases.items():
            self.assertEqual(crew_voices.addressed(text, "aster"), expected, text)
        for text in ("Aster, what is my fuel?", "watcher overlay off", "meridian", "Meridian, ", "open the galaxy map"):
            self.assertIsNone(crew_voices.addressed(text, "aster"), text)


class AskACrewmateTests(unittest.TestCase):
    def test_the_crewmate_answers_off_watch_in_its_own_voice(self):
        for active in ("aster", "watcher", "axiom"):
            companion = mind(active)
            self.assertTrue(companion.talk("Meridian, how far to Colonia?"))
            thought = companion.thought
            self.assertEqual(thought["text"], "Colonia is 22,000 ly away.")
            self.assertEqual(thought["heading"], "MERIDIAN · OFF WATCH")
            self.assertEqual((thought["speaker"], thought["voice"]["voice"], thought["kind"]), ("meridian", "meridian", "reply"))
            self.assertEqual(companion.memory["talk"][-1]["who"], "meridian")
            self.assertEqual(companion.spoken_words(thought), thought["text"], "said whole")
            self.assertEqual(companion.identity, active, "the watch never changes hands")

    def test_greetings_and_fallbacks_come_from_the_crewmates_own_lines(self):
        companion = mind("aster")
        companion.talk("hey Meridian")
        self.assertIn(companion.thought["text"], meridian_lines.GREETINGS)
        before = dict(companion.memory.get("aster_commands") or {})
        reply = watcher_copilot.reply("plain", crew_voices.CrewRandom(companion.random, "meridian"))
        self.assertIn(reply, meridian_lines.COMMANDS["plain"])
        self.assertEqual(companion.memory.get("aster_commands") or {}, before, "the officer's own rotations untouched")
        companion.lookup_provider = lambda question: []
        companion.talk("Meridian, do a little dance")
        self.assertIn(companion.thought["text"], meridian_lines.COMMANDS["plain"])

    def test_a_command_is_worded_by_the_crewmate(self):
        seen = []
        companion = mind("aster")
        companion.action_provider = lambda words: seen.append((words, companion.talking_as)) or "Done."
        companion.talk("Axiom, open the galaxy map")
        self.assertEqual(seen, [("open the galaxy map", "axiom")])
        self.assertIsNone(companion.talking_as)
        self.assertEqual(companion.thought["heading"], "AXIOM · OFF WATCH")

    def test_an_uplink_answer_keeps_the_crewmate(self):
        companion = mind("watcher")
        companion.action_provider = lambda words: {"waiting": True, "say": "Searching."}
        companion.talk("Meridian, where can I sell gold")
        self.assertEqual(companion.thought["heading"], "MERIDIAN · OFF WATCH")
        self.assertTrue(companion.uplink_answer("where can I sell gold", ["Sell at Jameson Memorial."]))
        self.assertEqual(companion.thought["speaker"], "meridian")


class ChimeTests(unittest.TestCase):
    def run_moment(self, companion, topic="world_earthlike", ticks=30):
        companion.consider(topic, {"body": "Test 3", "dist": "80 ly"}, force=True)
        for _ in range(ticks):
            companion.clock.now += 2
            thought = companion.tick()
            if thought and thought["topic"] == "crew_chime":
                return thought
        return None

    def test_a_big_moment_brings_one_crewmate_up_once_a_session(self):
        companion = mind("axiom")
        with mock.patch.object(crew_voices, "CHIME_CHANCE", 1.0):
            started = companion.clock.now
            chime = self.run_moment(companion)
            self.assertIsNotNone(chime)
            self.assertGreaterEqual(companion.clock.now - started, crew_voices.CHIME_DELAY_S, "after the one on watch")
            self.assertTrue(chime["heading"].endswith("· OFF WATCH"))
            self.assertNotEqual(chime["speaker"], "axiom")
            self.assertEqual(chime["voice"]["voice"], chime["speaker"])
            self.assertIn(chime["text"], crew_voices.CHIMES[chime["speaker"]]["earthlike"])
            companion.clock.now += 2 * 3600
            self.assertIsNone(self.run_moment(companion, "footfall_first"), "once a session")

    def test_only_crewmates_you_have_flown_with_and_never_with_thoughts_off(self):
        with mock.patch.object(crew_voices, "CHIME_CHANCE", 1.0):
            self.assertIsNone(self.run_moment(mind("aster", flown=["aster"])))
            only = self.run_moment(mind("aster", flown=["aster", "meridian"]))
            self.assertEqual(only["speaker"], "meridian")
            quiet = mind("aster", frequency="off")
            quiet.memory["hours"] = 5
            self.assertIsNone(self.run_moment(quiet))

    def test_a_close_call_counts_once_survived_but_not_a_death(self):
        with mock.patch.object(crew_voices, "CHIME_CHANCE", 1.0):
            survived = mind("meridian")
            survived.consider("hull_critical", {"hull": 9}, force=True)
            survived.clock.now += crew_voices.CLOSE_CALL_AFTER_S + 1
            chime = survived.tick()
            self.assertEqual((chime or {}).get("topic"), "crew_chime")
            self.assertIn(chime["text"], crew_voices.CHIMES[chime["speaker"]]["close_call"])
            lost = mind("meridian")
            lost.consider("hull_critical", {"hull": 9}, force=True)
            lost.consider("died", {}, force=True)
            lost.clock.now += crew_voices.CLOSE_CALL_AFTER_S + 1
            self.assertNotEqual((lost.tick() or {}).get("topic"), "crew_chime")

    def test_every_crewmate_has_every_moment_in_a_full_rotation(self):
        moments = set(crew_voices.MOMENTS.values()) | {"close_call"}
        for speaker, lines in crew_voices.CHIMES.items():
            self.assertEqual(set(lines), moments, speaker)
            for moment, options in lines.items():
                self.assertGreaterEqual(len(set(options)), 5)
                memory, rng = {}, random.Random(1)
                heard = [crew_voices.pick(memory, speaker, moment, rng) for _ in range(len(options))]
                self.assertEqual(len(set(heard)), len(options), f"{speaker} {moment}")


class DeckTests(unittest.TestCase):
    def test_a_crewmate_without_its_voice_stays_written(self):
        said = []
        deck = SimpleNamespace(config={"companion_identity": "aster", "aster_voice_enabled": True, "meridian_voice_enabled": False},
                               _watcher_voice_boot_held=lambda: False, _watcher_voice_on=lambda: True,
                               _watcher_voice_hushed=lambda: False,
                               _watcher_speaker=lambda: SimpleNamespace(say=lambda *args, **kwargs: said.append(args) or True))
        deck._crewmate_voice_on = lambda selected: DashboardWatcherVoiceMixin._crewmate_voice_on(deck, selected)
        with mock.patch("voidcompass.dashboard.dashboard_watcher_voice_mixin.voice_assets.installed", return_value=True):
            self.assertFalse(DashboardWatcherVoiceMixin._watcher_voice_say(deck, "Hello.", "k", feel={"voice": "meridian"}))
            deck.config["meridian_voice_enabled"] = True
            self.assertTrue(DashboardWatcherVoiceMixin._watcher_voice_say(deck, "Hello.", "k", feel={"voice": "meridian"}))
        self.assertEqual(len(said), 1)

    def test_the_speaker_uses_the_crewmates_own_voice_settings(self):
        config = {"companion_identity": "aster", "aster_voice_volume": 80, "meridian_voice_volume": 35,
                  "aster_voice_speed": "standard", "meridian_voice_speed": "slow"}
        speaker = WatcherSpeaker(settings=lambda: companions.settings(config))
        self.assertEqual(companions.identity(speaker._voice_settings("meridian")), "meridian")
        self.assertEqual(speaker._voice_settings("meridian").get("watcher_voice_volume"), 35)
        self.assertEqual(companions.identity(speaker._voice_settings()), "aster")
        self.assertNotEqual(speaker._speed("meridian"), speaker._speed())

    def test_the_chat_names_the_crewmate(self):
        companion = mind("aster")
        companion.talk("Meridian, how far to Colonia?")
        page = DashboardWatcherVoiceMixin._html_watcher_talk(SimpleNamespace(), companion)
        self.assertEqual(page["talk"][-1]["who"], "meridian")
        script = (ROOT / "web" / "dashboard" / "watcher.js").read_text(encoding="utf-8")
        self.assertIn("· OFF WATCH`", script)

    def test_a_new_companion_starts_at_the_watchers_pace(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = {name: Path(folder) / f"{name}_memory.json" for name in CREW}
            paths["axiom"].write_text("{}", encoding="utf-8")
            deck = SimpleNamespace(config={"heartbeat_thoughts": "chatty", "axiom_thoughts": "rare", "meridian_thoughts": "occasional"})
            with mock.patch("voidcompass.overlays.heartbeat_hud._memory_path", lambda config: paths[companions.identity(config)]):
                DashboardWatcherVoiceMixin._companion_first_pace(deck, "meridian")
                DashboardWatcherVoiceMixin._companion_first_pace(deck, "axiom")
        self.assertEqual(deck.config["meridian_thoughts"], "chatty", "never stood a watch: the Watcher's pace")
        self.assertEqual(deck.config["axiom_thoughts"], "rare", "a companion you've had keeps its own")


if __name__ == "__main__":
    unittest.main()
