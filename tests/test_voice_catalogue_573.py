"""Editable ship/app commands, repeatable docking and written conversation."""
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock
import zipfile

from tests.test_settings_page import dashboard
from tests.test_ship_commands_573 import Deck, keys
from tests.test_watcher_overlay_commands_573 import Deck as AppDeck
from voidcompass.core import config, voice_commands as vc
from voidcompass.overlays import watcher_chat, watcher_mind, watcher_ship
from tools import release_packager


CUSTOM = {"name": "My chart", "phrase": "chart time", "aliases": ["please chart"],
          "group": "My cockpit", "sequence": ["GalaxyMapOpen", "wait 0.1"],
          "places": ["ship"], "reply": "Your chart, Commander."}


class CatalogueTests(unittest.TestCase):
    def test_every_builtin_and_app_action_can_be_renamed(self):
        originals = vc.catalogue()
        definitions = {item.id: {"name": "Renamed " + item.id, "phrase": "phrase " + str(index),
                                "aliases": [], "keep_defaults": False}
                       for index, item in enumerate(originals) if getattr(item, "native", {}).get("kind") != "uplink"}
        for item in originals:
            if getattr(item, "native", {}).get("kind") == "uplink":
                definitions[item.id] = {"name": "Renamed " + item.id,
                                        "phrase": "market " + item.id + " {commodity}", "aliases": [], "keep_defaults": False}
        definitions = vc.validate(definitions)
        configured = vc.catalogue(definitions)
        self.assertEqual(len(configured), len(originals))
        for command in configured:
            self.assertTrue(command.say.startswith("Renamed "))
            if hasattr(command, "native"):
                found = vc.native_request(command.example.replace("{commodity}", "gold"), definitions)
                self.assertEqual(found[0].id, command.id)
            else:
                self.assertEqual(watcher_ship.request(command.example, configured)["command"], command.id)
        self.assertIsNone(vc.native_request("stop music", definitions))
        self.assertIsNone(watcher_ship.request("open the galaxy map", configured))

    def test_default_catalogue_keeps_every_existing_phrase_operation(self):
        configured = vc.catalogue()
        for command in watcher_ship.COMMANDS:
            with self.subTest(command=command.id):
                self.assertEqual(watcher_ship.request(command.example, configured), watcher_ship.request(command.example))
        renamed = vc.validate({"gear": {"phrase": "boots down", "aliases": ["boots up"], "keep_defaults": False}})
        self.assertEqual(watcher_ship.request("Watcher, boots down, please.", vc.catalogue(renamed)), {"command": "gear", "op": "on"})
        self.assertEqual(watcher_ship.request("boots up!", vc.catalogue(renamed)), {"command": "gear", "op": "off"})

    def test_custom_sequence_runs_from_alias_and_checks_all_keys_before_pressing(self):
        definitions = vc.validate({"custom_chart": CUSTOM})
        deck = Deck(watcher_ship_commands=definitions)
        with mock.patch.object(deck, "_ship_pause", return_value=None):
            self.assertEqual(deck._watcher_ship("Watcher, please chart"), CUSTOM["reply"])
            self.assertEqual(deck.run(), [None])
        self.assertEqual(deck._ship_key_presser.pressed, ["Left Shift+G"])
        deck.config["watcher_ship_macros"] = {"custom_chart": ["GalaxyMapOpen", "UI_Select"]}
        self.assertIn("keyboard", deck._watcher_ship("chart time"))
        self.assertEqual(deck.jobs, [])

    def test_phrases_are_literal_and_conflicts_or_invalid_steps_are_rejected(self):
        for value in (
                {"custom_test": {**CUSTOM, "phrase": "open the galaxy map"}},
                {"custom_test": {**CUSTOM, "phrase": "stop music"}},
                {"custom_test": {**CUSTOM, "aliases": ["hello watcher"]}},
                {"custom_test": {**CUSTOM, "sequence": ["SelfDestruct"]}},
                {"custom_test": {**CUSTOM, "places": []}},
                {"app_uplink_buy": {"phrase": "market search"}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                vc.validate(value)
        definitions = vc.validate({"custom_test": {**CUSTOM, "phrase": "chart.* now"}})
        commands = vc.catalogue(definitions)
        self.assertIsNone(watcher_ship.request("chart anything now", commands))
        self.assertEqual(watcher_ship.request("chart.* now", commands)["command"], "custom_test")

    def test_app_music_overlay_and_market_aliases_keep_their_actions(self):
        definitions = vc.validate({
            "app_music_play": {"name": "Soundtrack", "phrase": "spin a record", "keep_defaults": False},
            "app_overlay_survey_hide": {"name": "Clear survey", "phrase": "clear my survey", "keep_defaults": False},
            "app_uplink_buy": {"phrase": "find sellers for {commodity}", "keep_defaults": False}})
        deck = AppDeck()
        deck.config["watcher_ship_commands"] = definitions
        deck.music_remote = mock.Mock(return_value=True)
        self.assertEqual(deck._watcher_mind_action("spin a record"), "Music, then.")
        deck.music_remote.assert_called_once_with("play")
        self.assertIsNone(deck._watcher_mind_action("play music"))
        deck._watcher_mind_action("clear my survey")
        self.assertEqual(deck.done, [("hotkey", "survey")])
        self.assertIsNone(deck._watcher_mind_action("hide the survey overlay"))
        deck._watcher_uplink_commodities = mock.Mock(return_value=[("gold", "Gold")])
        deck._watcher_uplink = mock.Mock(return_value="Looking.")
        self.assertEqual(deck._watcher_mind_action("find sellers for gold"), "Looking.")
        self.assertEqual(deck._watcher_uplink.call_args.args[1], {"kind": "buy", "commodity": "Gold"})

    def test_disabling_app_or_ship_commands_stops_their_old_phrases(self):
        definitions = vc.validate({"app_music_play": {"enabled": False}, "galaxy_map": {"enabled": False}})
        self.assertIsNone(vc.native_request("play music", definitions))
        self.assertIsNone(watcher_ship.request("open galaxy map", vc.catalogue(definitions)))
        rows = [row for group in Deck(watcher_ship_commands=definitions)._html_ship_controls()["groups"] for row in group["rows"]]
        self.assertFalse(next(row for row in rows if row["id"] == "galaxy_map")["enabled"])
        self.assertTrue(all(row.get("id") for row in rows))
        self.assertTrue(any(row["id"] == "power_reset" for row in rows))
        reassigned = vc.validate({"app_greeting": {"enabled": False},
                                  "custom_hello": {**CUSTOM, "phrase": "hello watcher", "aliases": []}})
        self.assertIsNone(vc.native_request("hello watcher", reassigned))
        self.assertEqual(watcher_ship.request("hello watcher", vc.catalogue(reassigned))["command"], "custom_hello")

    def test_settings_save_definitions_and_sequences_atomically_and_delete_stale_sequences(self):
        app = dashboard()
        app._apply_settings_changes = mock.Mock()
        def save(values):
            return app._handle_html_workspace_command({"page": "settings", "operation": "save", "save_id": 3, "values": values})
        self.assertTrue(save({"watcher_ship_commands": {"custom_chart": CUSTOM},
                              "watcher_ship_macros": {"custom_chart": ["GalaxyMapOpen", "wait 0.2"]}}))
        self.assertEqual(app.config["watcher_ship_macros"]["custom_chart"][-1], "wait 0.2")
        before = json.dumps(app.config, sort_keys=True)
        self.assertFalse(save({"watcher_ship_commands": {"custom_chart": {**CUSTOM, "sequence": ["wait 90"]}},
                               "home_system": "Changed"}))
        self.assertEqual(json.dumps(app.config, sort_keys=True), before)
        self.assertTrue(save({"watcher_ship_commands": {}}))
        self.assertEqual(app.config["watcher_ship_macros"], {})
        self.assertIn("watcher_ship_commands", config.PROFILE_VALUE_SETTINGS)


class ConversationTests(unittest.TestCase):
    def test_fifty_greetings_and_ten_rundowns_cycle_and_are_spoken_in_full(self):
        mind = watcher_mind.WatcherMind(None, {}, rng=random.Random(5))
        self.assertEqual(len(set(watcher_chat.GREETINGS)), 50)
        self.assertEqual(len(set(watcher_chat.CAPABILITIES)), 10)
        for phrase, count, pool in (("hello watcher", 50, watcher_chat.GREETINGS),
                                    ("Watcher, what can you do?", 10, watcher_chat.CAPABILITIES)):
            said = []
            for _ in range(count):
                self.assertTrue(mind.talk(phrase, voice=True))
                thought = mind.current()
                said.append(thought["text"])
                self.assertEqual(mind.spoken_words(thought), thought["text"])
                self.assertEqual(mind.memory["talk"][-1]["it"], thought["text"])
            self.assertEqual(set(said), set(pool))
            mind.talk(phrase)
            self.assertNotEqual(mind.current()["text"], said[-1])

    def test_conversation_aliases_and_original_phrase_switch(self):
        definitions = vc.validate({"app_greeting": {"name": "Old friend", "phrase": "salutations", "keep_defaults": False},
                                   "app_capabilities": {"phrase": "give me the tour", "aliases": ["your duties"], "keep_defaults": False}})
        mind = watcher_mind.WatcherMind(None, {"watcher_ship_commands": definitions})
        mind.talk("salutations")
        self.assertIn(mind.current()["text"], watcher_chat.GREETINGS)
        mind.talk("your duties")
        self.assertIn(mind.current()["text"], watcher_chat.CAPABILITIES)
        self.assertIsNone(vc.native_request("hello watcher", definitions, kind="chat"))


class DocumentationReleaseTests(unittest.TestCase):
    def test_docs_are_shipped_in_archive_and_manifest_and_unrelated_files_stay_out(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("dist/VoidCompass.exe", "README.md", "mini-readme.md", "api.md", "THIRD_PARTY_NOTICES.md",
                         "data/codexRef.json", "data/mining_data.db", "docs/VOICE_COMMANDS.md", "docs/examples/actions.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("example", encoding="utf-8")
            (root / "config.json").write_text('private')
            def database(_source, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"sanitised")
            with mock.patch.object(release_packager, "_sanitize_mining_database", side_effect=database), \
                 mock.patch.object(release_packager, "_copy_readme_images", return_value=set()), \
                 mock.patch.object(release_packager, "_copy_runtime_images", return_value=set()):
                result = release_packager.create_release(root, "5.7.3", platform_name="Windows-x64")
            archives = list((root / "release").glob("*.zip"))
            self.assertEqual(len(archives), 1)
            with zipfile.ZipFile(archives[0]) as archive:
                names = archive.namelist()
                self.assertTrue(any(name.endswith("/docs/VOICE_COMMANDS.md") for name in names))
                self.assertTrue(any(name.endswith("/docs/examples/actions.json") for name in names))
                self.assertFalse(any(name.endswith("/config.json") for name in names))
                manifest = json.loads(archive.read(next(name for name in names if name.endswith("/RELEASE_MANIFEST.json"))))
                self.assertIn("docs/VOICE_COMMANDS.md", manifest["files"])
