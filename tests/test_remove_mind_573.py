"""5.7.3: written Watcher replies, retired engine cleanup and old saves."""
import ast
import copy
import json
import os
from pathlib import Path
import random
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

from voidcompass.core import config as config_module, watcher_retirement
from voidcompass.dashboard.dashboard_flight_log_mixin import DashboardFlightLogMixin
from voidcompass.dashboard.dashboard_journey_mixin import DashboardJourneyMixin
from voidcompass.dashboard.dashboard_keepsakes_mixin import DashboardKeepsakesMixin
from voidcompass.exploration.flight_log import flight_logs
from voidcompass.overlays import watcher_copilot, watcher_mind, watcher_postcards
from tests.test_flight_log_5538 import NIGHT, ROWS
from tests.test_watcher_mind import Always, Clock

ROOT = Path(__file__).resolve().parents[1]


class WrittenTalkTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.watcher = watcher_mind.WatcherMind(clock=self.clock, rng=Always())

    def test_typed_and_spoken_commands_answer_without_a_model(self):
        self.watcher.action_provider = lambda words: "The galaxy map." if words == "open the galaxy map" else None
        self.watcher.lookup_provider = mock.Mock(side_effect=AssertionError("a command must not run a lookup"))
        self.assertFalse(hasattr(self.watcher, "llm"))
        self.assertTrue(self.watcher.talk("open the galaxy map", voice=True))
        self.assertEqual(self.watcher.current()["text"], "The galaxy map.")
        self.assertEqual(self.watcher.current()["importance"], 3)
        self.assertTrue(self.watcher.memory["talk"][-1]["voice"])
        self.assertEqual(self.watcher.memory["talk"][-1]["it"], "The galaxy map.")
        self.assertFalse(self.watcher.talk_waiting())
        self.assertNotIn("own_words", self.watcher.current())

    def test_questions_answer_only_from_plain_ship_readings(self):
        readings = ["The hold contains 12 tonnes of painite", "Capacity is 64 tonnes"]
        self.watcher.lookup_provider = mock.Mock(return_value=readings)
        self.assertTrue(self.watcher.talk("What's in the hold?"))
        self.assertEqual(self.watcher.memory["talk"][-1]["it"], watcher_copilot.plain_answer(readings))
        self.watcher.lookup_provider.assert_called_once_with("What's in the hold?")

    def test_unknown_text_and_failed_lookups_use_written_help(self):
        self.watcher.lookup_provider = mock.Mock(side_effect=RuntimeError("no readings"))
        self.watcher.talk("Tell me a story about yesterday")
        self.assertIn(self.watcher.current()["text"], watcher_copilot.REPLIES["plain"])
        self.assertNotIn("mind", self.watcher.current()["text"].casefold())
        self.assertFalse(self.watcher.talk("   "))
        self.assertEqual(len(self.watcher.memory["talk"]), 1)

    def test_plain_uplink_finishes_the_pending_question_and_keeps_all_readings(self):
        self.watcher.action_provider = lambda words: {"waiting": True, "say": "Opening the uplink."}
        self.watcher.talk("Where can I sell painite?")
        self.assertTrue(self.watcher.talk_waiting())
        readings = ["Best price: 700,000 credits a tonne", "Next best: 650,000 credits a tonne", "Nearest: Sol"]
        self.assertTrue(self.watcher.uplink_answer("Where can I sell painite?", readings))
        self.assertEqual(self.watcher.current()["text"], watcher_copilot.plain_answer(readings))
        self.assertEqual(self.watcher.memory["talk"][-1]["it"], self.watcher.current()["text"])
        self.assertFalse(self.watcher.talk_waiting())
        self.assertFalse(self.watcher.uplink_answer("Where can I sell painite?", readings))

    def test_a_new_command_cancels_the_old_uplink_reply(self):
        self.watcher.action_provider = lambda words: ({"waiting": True, "say": "Opening the uplink."}
                                                       if "painite" in words else "Lights on.")
        self.watcher.talk("Where can I sell painite?")
        self.watcher.talk("lights on")
        self.assertFalse(self.watcher.uplink_answer("Where can I sell painite?", ["Late market data"]))
        self.assertEqual(self.watcher.current()["text"], "Lights on.")

    def test_history_remains_bounded_and_follow_up_is_still_written(self):
        self.watcher.action_provider = lambda words: "Done."
        for number in range(55):
            self.watcher.talk(f"Command {number}")
        self.assertEqual(len(self.watcher.memory["talk"]), 50)
        self.assertEqual(self.watcher.memory["talk"][0]["you"], "Command 5")
        after = self.watcher.say_after("Elite stopped being in front.")
        self.assertEqual((after["topic"], after["importance"]), ("talk", 3))
        self.assertEqual(self.watcher.current()["text"], "Elite stopped being in front.")
        self.watcher.consider("quiet", force=True)
        self.assertIsNotNone(self.watcher._afterthought)
        self.clock.now = self.watcher._afterthought["at"] + .01
        self.assertEqual(self.watcher.follow_up()["topic"], "afterthought")

    def test_old_model_memory_is_loaded_and_saved_without_being_used_or_changed(self):
        legacy = {"diary": [{"text": "Old diary"}], "told_me": [{"text": "Old question", "source": "question"}],
                  "taught": [{"text": "Old fact"}], "about_you": {"text": "Old summary"},
                  "liked": [{"text": "A liked line"}], "disliked": [{"text": "A disliked line"}],
                  "own_said": [{"topic": "talk", "text": "Generated line"}],
                  "mind_words": {"log:1": {"text": "Generated paragraph", "from": "abc"}},
                  "happened": [{"e": "FSDJump", "text": "Old event"}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watcher_memory.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            watcher = watcher_mind.WatcherMind(path, clock=self.clock, rng=Always())
            self.assertEqual({key: watcher.memory[key] for key in legacy}, legacy)
            watcher.talk("hello")
            watcher.consider("danger", force=True)
            watcher.save()
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual({key: saved[key] for key in legacy}, legacy)
            self.assertNotIn("Generated", watcher.current()["text"])

    def test_removed_modules_have_no_source_imports_or_references(self):
        for path in (ROOT / "src").rglob("*.py"):
            source = path.read_text(encoding="utf-8-sig")
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("watcher_llm", source)
                self.assertNotIn("voidcompass.llm", source)
                ast.parse(source)
        for module in ("watcher_llm", "watcher_world", "watcher_knowing", "watcher_learning"):
            self.assertFalse((ROOT / "src/voidcompass/overlays" / f"{module}.py").exists())
        self.assertFalse((ROOT / "src/voidcompass/llm").exists())

    def test_legacy_generated_lines_are_hidden_without_changing_the_saved_history(self):
        from voidcompass.dashboard.html_dashboard import HtmlDashboardMixin
        from voidcompass.dashboard.dashboard_watcher_voice_mixin import DashboardWatcherVoiceMixin

        class Deck(HtmlDashboardMixin):
            _html_watcher_talk = DashboardWatcherVoiceMixin._html_watcher_talk

            def _html_watcher_deeper(self, mind):
                return {}

            def _html_watcher_extras(self, mind):
                return {"talk": self._html_watcher_talk(mind)}

        memory = self.watcher.memory
        memory.update(log=[[1, "mind_own", "Generated thought"], [2, "quiet", "Generated reword"],
                           [3, "quiet", "Written line"], [4, "quiet", "Liked generated line"]],
                      said=[["mind_own", 1], ["quiet", 2]],
                      own_said=[{"topic": "quiet", "text": "Generated reword"}, {"topic": "talk", "text": "Generated answer"}],
                      liked=[{"topic": "quiet", "text": "Liked generated line"}],
                      talk=[{"you": "Old question", "it": "Generated answer"}, {"you": "lights on", "it": "Lights on."}])
        before = copy.deepcopy(memory)
        deck = Deck()
        deck.config = {}
        deck.heartbeat_hud = SimpleNamespace(mind=self.watcher)
        data = deck._html_watcher_workspace()
        self.assertEqual([row["text"] for row in data["log"]], ["Written line"])
        self.assertNotIn("mind_own", [row["topic"] for row in data["favourites"]])
        self.assertEqual(data["talk"]["talk"][0]["you"], "Old question")
        self.assertEqual(data["talk"]["talk"][0]["it"], "")
        self.assertEqual(data["talk"]["talk"][1]["it"], "Lights on.")
        self.assertEqual(memory, before)


class RetiredModelCleanupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name) / "install"
        self.base.mkdir()

    def write(self, name, data=b"keep"):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def link_directory(self, target, source):
        try:
            target.symlink_to(source, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            import _winapi
            _winapi.CreateJunction(str(source), str(target))

    def test_only_retired_models_are_removed_and_reported_once(self):
        self.write("models/llm/engine/llama-server.exe", b"engine")
        self.write("models/llm/old.gguf", b"weights")
        kept = [self.write("models/stt/whisper-server.exe"), self.write("models/hal9000/hal.onnx"),
                self.write("profiles/commander/watcher_memory.json")]
        self.assertEqual(watcher_retirement.remove_retired_models(self.base), len(b"engineweights"))
        self.assertFalse((self.base / "models/llm").exists())
        self.assertTrue(all(path.read_bytes() == b"keep" for path in kept))
        self.assertIsNone(watcher_retirement.remove_retired_models(self.base))
        self.assertEqual(watcher_retirement.cleanup_notice(None), "")
        self.assertIn("1.0 GB", watcher_retirement.cleanup_notice(1024 ** 3))

    def test_linked_target_and_linked_models_parent_are_not_followed(self):
        shared = Path(self.folder.name) / "shared"
        shared.mkdir()
        outside = shared / "llm" / "keep.gguf"
        outside.parent.mkdir()
        outside.write_bytes(b"outside")
        models = self.base / "models"
        models.mkdir()
        self.link_directory(models / "llm", shared / "llm")
        self.assertIsNone(watcher_retirement.remove_retired_models(self.base))
        self.assertEqual(outside.read_bytes(), b"outside")
        alternate = Path(self.folder.name) / "alternate"
        alternate.mkdir()
        self.link_directory(alternate / "models", shared)
        self.assertIsNone(watcher_retirement.remove_retired_models(alternate))
        self.assertEqual(outside.read_bytes(), b"outside")

    def test_links_inside_the_retired_folder_do_not_delete_or_count_external_files(self):
        weights = self.write("models/llm/old.gguf", b"retired")
        shared = Path(self.folder.name) / "shared"
        shared.mkdir()
        outside = shared / "keep.gguf"
        outside.write_bytes(b"outside")
        self.link_directory(weights.parent / "linked-engine", shared)
        self.assertEqual(watcher_retirement.remove_retired_models(self.base), len(b"retired"))
        self.assertEqual(outside.read_bytes(), b"outside")

    def test_cleanup_failure_keeps_the_install_usable(self):
        weights = self.write("models/llm/old.gguf")
        with mock.patch.object(watcher_retirement.shutil, "rmtree", side_effect=PermissionError("busy")), \
                self.assertLogs(level="WARNING"):
            self.assertIsNone(watcher_retirement.remove_retired_models(self.base))
        self.assertTrue(weights.exists())

    def test_default_cleanup_is_bound_to_the_application_install_directory(self):
        self.write("models/llm/old.gguf", b"retired")
        self.write("models/stt/whisper-server.exe")
        with mock.patch.object(watcher_retirement, "application_dir", return_value=self.base) as app_dir, \
                mock.patch.object(watcher_retirement.shutil, "rmtree", wraps=watcher_retirement.shutil.rmtree) as delete:
            self.assertEqual(watcher_retirement.remove_retired_models(), len(b"retired"))
        app_dir.assert_called_once_with()
        delete.assert_called_once_with(self.base.resolve() / "models" / "llm")
        self.assertTrue((self.base / "models/stt/whisper-server.exe").exists())


class LegacyConfigTests(unittest.TestCase):
    def test_copied_real_profile_migrates_without_touching_the_original(self):
        candidates = sorted((ROOT / "profiles").glob("*/config.json"))
        original = candidates[0] if candidates else None
        original_bytes = original.read_bytes() if original else None
        profile = json.loads(original_bytes) if original_bytes else {"home_system": "Sol"}
        old_prefix = "watcher_" + "llm_"
        retired = {old_prefix + "enabled": True, old_prefix + "model": "standard", old_prefix + "device": "gpu",
                   old_prefix + "diary": True, old_prefix + "future_option": "old value"}
        profile.update(retired, watcher_ship_enabled=True, watcher_listen_enabled=True, watcher_voice_enabled=True)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profiles = root / "profiles"
            copied = profiles / "legacy_f123" / "config.json"
            copied.parent.mkdir(parents=True)
            copied.write_text(json.dumps(profile), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({"active_commander_profile": "legacy_f123",
                "active_commander_name": "Legacy", "active_commander_fid": "F123", **retired,
                "commander_profiles": {"legacy_f123": {"commander_name": "Legacy", "fid": "F123", **retired}}}), encoding="utf-8")
            with mock.patch.object(config_module, "CONFIG_FILE", str(config_path)), \
                    mock.patch.object(config_module, "PROFILE_DIR", str(profiles)):
                config = config_module.load_config()
                self.assertFalse(any(key.startswith(old_prefix) for key in config))
                self.assertFalse(any(key.startswith(old_prefix) for key in config["commander_profiles"]["legacy_f123"]))
                self.assertTrue(config["watcher_ship_enabled"] and config["watcher_listen_enabled"] and config["watcher_voice_enabled"])
                config_module.save_config(config)
            for path in (config_path, copied):
                self.assertNotIn(old_prefix, path.read_text(encoding="utf-8"))
            persisted = json.loads(copied.read_text(encoding="utf-8"))
            self.assertTrue(persisted["watcher_ship_enabled"] and persisted["watcher_listen_enabled"])
        if original:
            self.assertEqual(original.read_bytes(), original_bytes)


class WrittenKeepsakeTests(unittest.TestCase):
    def test_flight_log_keeps_its_written_paragraph(self):
        class Deck(DashboardFlightLogMixin):
            pass
        deck = Deck()
        deck.config = {"heartbeat_personality": "weary"}
        deck.travel_history = SimpleNamespace(lock=threading.Lock(), rows=copy.deepcopy(ROWS), revision=1)
        deck.heartbeat_hud = SimpleNamespace(mind=SimpleNamespace(own_paragraph=mock.Mock(side_effect=AssertionError("model used"))))
        actual = deck._flight_logs([copy.deepcopy(NIGHT)])
        self.assertEqual(actual[0]["words"], flight_logs([NIGHT], ROWS, (), "weary")[0]["words"])
        self.assertNotIn("own_words", actual[0])
        deck.heartbeat_hud.mind.own_paragraph.assert_not_called()

    def test_wrapped_verdict_is_written_without_any_model_hook(self):
        class Deck(DashboardJourneyMixin):
            pass
        deck = Deck()
        deck.config = {"active_commander_name": "Legacy", "heartbeat_personality": "weary"}
        deck._journey_rows = lambda: copy.deepcopy(ROWS)
        deck._journey_sessions = lambda: [copy.deepcopy(NIGHT)]
        deck._journey_bodies = lambda start, end: []
        deck._journey_postcards = lambda: []
        deck.music_diary = lambda: SimpleNamespace(between=lambda start, end: [])
        deck._year_record = SimpleNamespace(events=lambda *args: [])
        deck._wrapped_own_words = mock.Mock(side_effect=AssertionError("model used"))
        story = deck._tell_year(2026)
        verdict = next(card for card in story["cards"] if card["kind"] == "verdict")
        self.assertTrue(verdict["words"])
        self.assertNotIn("own_words", verdict)
        deck._wrapped_own_words.assert_not_called()

    def test_postcard_uses_the_written_note_and_respects_its_off_switch(self):
        class Deck(DashboardKeepsakesMixin):
            pass
        deck = Deck()
        deck.config = {"heartbeat_overlay_enabled": True, "heartbeat_thoughts": "chatty"}
        deck._watcher_own_words = mock.Mock(side_effect=AssertionError("model used"))
        card = {"id": "plain", "title": "Sol", "place": "Sol"}
        with mock.patch.object(watcher_postcards.random, "Random", return_value=random.Random(12)):
            note = deck._postcard_watcher_note(card, 0, "DOCKED")
        self.assertTrue(note)
        self.assertIn(note, deck._postcard_recent_notes)
        deck.config["heartbeat_thoughts"] = "off"
        self.assertEqual(deck._postcard_watcher_note(card, 0, "DOCKED"), "")
        deck._watcher_own_words.assert_not_called()


if __name__ == "__main__":
    unittest.main()
