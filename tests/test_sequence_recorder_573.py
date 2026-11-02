"""Recording resolves bound inputs, keeps timing, and needs review before saving."""
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock, patch

from voidcompass.core import elite_binds, elite_macros, elite_recorder
from voidcompass.core.config import get_active_profile
from tests.test_ship_commands_573 import Deck
from tests.test_settings_page import dashboard


def fixture_binds():
    binds = elite_binds.EliteBinds.__new__(elite_binds.EliteBinds)
    binds.mappings = {"gamepad": {"045E:028E"}, "saitekx52": {"06A3:075C"}}
    slot = elite_binds.Slot
    binds.actions = {
        "general": {"UI_Select": [slot("Keyboard", "Key_Space"), slot("GamePad", "GamePad_FaceDown")],
                    "UI_Right": [slot("Keyboard", "Key_D"), slot("SaitekX52", "Joy_POV1Right")],
                    "CycleNextPanel": [slot("Keyboard", "Key_E"), slot("GamePad", "GamePad_FaceDown", [("GamePad", "GamePad_LBumper")])]},
        "ship": {"FocusLeftPanel": [slot("Keyboard", "Key_1"), slot("Keyboard", "Key_F1")],
                 "OtherSpaceAction": [slot("Keyboard", "Key_Space")],
                 "MissingKeyboard": [slot("SaitekX52", "Joy_7")],
                 "EjectAllCargo": [slot("Keyboard", "Key_X")]},
        "srv": {"FocusLeftPanel_Buggy": [slot("Keyboard", "Key_2")]},
        "onfoot": {"HumanoidJumpButton": [slot("Keyboard", "Key_Space")]},
    }
    binds.refresh = lambda: True
    return binds


class RecordingTests(unittest.TestCase):
    def make(self, bindings=None):
        self.now = 0.0
        self.recorder = elite_recorder.SequenceRecorder(
            bindings or elite_recorder.bindings_for(fixture_binds(), "ship"), "request_docking", "ship", "jeff",
            clock=lambda: self.now)
        return self.recorder

    def sample(self, at, down=(), front=True, focus=0, place="ship"):
        self.now = at
        self.recorder.sample(set(down), front, (place, focus))

    def test_bound_keys_buttons_secondary_keys_and_vehicle_scope(self):
        binds = fixture_binds()
        ship = elite_recorder.bindings_for(binds, "ship")
        pairs = {(binding.action, binding.trigger) for binding in ship}
        self.assertIn(("FocusLeftPanel", "key:f1"), pairs)
        self.assertIn(("UI_Right", "hat:06A3:075C:Right"), pairs)
        self.assertIn(("UI_Select", "pad:A"), pairs)
        self.assertNotIn(("FocusLeftPanel_Buggy", "key:2"), pairs)
        self.assertFalse(any("Eject" in action for action, _ in pairs))
        self.assertFalse(next(binding.playable for binding in ship if binding.action == "MissingKeyboard"))
        self.assertIn("HumanoidJumpButton", {binding.action for binding in elite_recorder.bindings_for(binds, "foot")})

    def test_docking_panel_guard_holds_waits_and_return_path(self):
        rec = self.make()
        self.sample(0, front=False)
        self.assertEqual(rec.state()["status"], "armed")
        self.sample(1)
        self.sample(8, ["key:1"])
        self.sample(8.15, focus=2)
        self.sample(8.9, ["key:e"], focus=2)
        self.sample(9.05, focus=2)
        self.sample(10, ["key:d"], focus=2)
        self.sample(10.15, focus=2)
        self.sample(11, ["pad:A"], focus=2)
        self.sample(11.15, focus=2)
        self.sample(12, ["key:1"], focus=2)
        self.sample(12.15)
        self.sample(13, front=False)
        state = rec.state()
        self.assertTrue(state["can_use"], state)
        self.assertEqual(state["steps"][0], "focus FocusLeftPanel 2")
        self.assertEqual(state["steps"][-1], "leave FocusLeftPanel 2")
        self.assertIn("hold UI_Right 0.15", state["steps"])
        steps = elite_macros.parse_macro(state["steps"])
        self.assertAlmostEqual(steps[1].seconds + rec.gap * 2, .75)
        self.assertEqual(len(state["events"]), 5)

    def test_shared_keys_require_a_choice_and_skip_is_explicit(self):
        rec = self.make()
        self.sample(0)
        self.sample(1, ["key:space"])
        self.sample(1.2)
        rec.finish()
        self.assertFalse(rec.state()["can_use"])
        self.assertFalse(rec.choose(0, "SelfDestruct"))
        self.assertFalse(rec.choose(-1, "UI_Select"))
        self.assertTrue(rec.choose(0, "UI_Select"))
        self.assertEqual(rec.state()["steps"], ["hold UI_Select 0.2"])
        self.assertTrue(rec.state()["can_use"])
        self.assertTrue(rec.choose(0, "skip"))
        self.assertFalse(rec.state()["can_use"])

    def test_controller_combo_prefers_modifiers_and_does_not_duplicate_them(self):
        modifier = elite_recorder.Binding("SomeBumperAction", "pad:LB", frozenset(), "Bumper", True)
        rec = self.make((*elite_recorder.bindings_for(fixture_binds(), "ship"), modifier))
        self.sample(0)
        self.sample(1, ["pad:LB"])
        self.sample(1.1, ["pad:LB", "pad:A"])
        self.sample(1.3, ["pad:LB"])
        self.sample(1.4)
        rec.finish()
        self.assertTrue(rec.state()["can_use"], rec.state())
        self.assertEqual(rec.state()["steps"], ["hold CycleNextPanel 0.2"])

    def test_keyboard_modifier_combination_takes_priority_over_a_plain_binding(self):
        combo = elite_recorder.Binding("UI_Back", "key:space", frozenset({"key:leftshift"}), "Back", True)
        rec = self.make((*elite_recorder.bindings_for(fixture_binds(), "ship"), combo))
        self.sample(0)
        self.sample(1, ["key:leftshift"])
        self.sample(1.1, ["key:leftshift", "key:space"])
        self.sample(1.3, ["key:leftshift"])
        self.sample(1.4)
        rec.finish()
        self.assertEqual(rec.state()["steps"], ["hold UI_Back 0.2"])
        self.assertTrue(rec.state()["can_use"])

    def test_overlap_hold_limits_and_controller_without_playback_binding_are_review_errors(self):
        for events, error in (
            ([(1, ["key:e"]), (1.1, ["key:e", "key:d"]), (1.3, [])], "Overlapping"),
            ([(1, ["key:e"]), (7, [])], "five seconds"),
            ([(1, ["joy:06A3:075C:7"]), (1.2, [])], "keyboard key"),
        ):
            with self.subTest(error=error):
                rec = self.make()
                self.sample(0)
                for at, down in events:
                    self.sample(at, down)
                rec.finish()
                self.assertFalse(rec.state()["can_use"])
                self.assertTrue(any(error in text for text in rec.state()["errors"]), rec.state())

    def test_long_waits_are_split_and_capture_is_bounded(self):
        rec = self.make()
        self.sample(0)
        self.sample(1, ["key:e"])
        self.sample(1.1)
        self.sample(14, ["key:d"])
        self.sample(14.1)
        self.sample(121)
        state = rec.state()
        self.assertEqual(state["status"], "review")
        self.assertTrue(state["can_use"], state)
        waits = [step for step in elite_macros.parse_macro(state["steps"]) if step.kind == "wait"]
        self.assertEqual(len(waits), 3)
        self.assertAlmostEqual(sum(step.seconds for step in waits) + rec.gap * 4, 12.9)
        rec = self.make()
        self.sample(0)
        for n in range(31):
            self.sample(n + 1, ["key:e"])
            self.sample(n + 1.1)
        self.assertEqual(len(rec.state()["events"]), 30)
        self.assertEqual(rec.state()["status"], "review")

    def test_held_keys_on_entry_are_ignored_and_vehicle_change_stops_capture(self):
        rec = self.make()
        self.sample(0, ["key:e"])
        self.sample(1)
        self.sample(2, ["key:e"])
        self.sample(2.1)
        self.sample(3, place="srv")
        self.assertEqual(len(rec.state()["events"]), 1)
        self.assertEqual(rec.state()["status"], "review")
        rec.discard()
        self.assertFalse(rec.state()["steps"])
        self.assertEqual(rec.state()["status"], "discarded")

    def test_input_is_not_sampled_outside_elite_and_close_wakes_worker(self):
        rec = self.make()
        sampled = Mock(return_value=set())
        checked = threading.Event()
        def front():
            checked.set()
            return False
        rec.start(sampled, front, lambda: ("ship", 0))
        self.assertTrue(checked.wait(2))
        rec.discard()
        rec._thread.join(2)
        sampled.assert_not_called()
        self.assertFalse(rec._thread.is_alive())


class RecorderDeckTests(unittest.TestCase):
    def test_start_stop_id_validation_profile_and_automation_guards(self):
        deck = Deck()
        deck.binds = fixture_binds()
        hub = SimpleNamespace(watch=Mock(), snapshot=lambda: set())
        deck._controller_hub = lambda: hub
        with patch.object(elite_recorder, "BoundKeyboard"), patch.object(elite_recorder.SequenceRecorder, "start") as start:
            self.assertTrue(deck._handle_sequence_command("sequence_record", {"target": "request_docking"}))
            start.assert_called_once()
            self.assertTrue(deck._ship_recording())
            self.assertFalse(deck._handle_sequence_command("sequence_record", {"target": "galaxy_map"}))
            self.assertIn("Finish recording", deck._watcher_ship("gear down"))
            self.assertFalse(deck.jobs)
            self.assertEqual(deck._ship_pause(0, "ship"), "cancelled")
            self.assertEqual(deck._ship_power_job(None, ["sys"], {"sys": "IncreaseSystemsPower"})(), "cancelled")
            record_id = deck._ship_recorder_state()["id"]
            self.assertFalse(deck._handle_sequence_command("sequence_stop", {"record_id": "stale"}))
            self.assertTrue(deck._handle_sequence_command("sequence_stop", {"record_id": record_id}))
            self.assertFalse(deck._ship_recording())
            self.assertEqual(deck._ship_recorder_state()["status"], "review")
            deck.config["active_commander_profile"] = "other"
            self.assertEqual(deck._ship_recorder_state()["status"], "idle")

    def test_new_vehicle_target_validation_and_saved_steps_survive_discard(self):
        deck = Deck(watcher_ship_macros={"request_docking": ["UI_Select"]})
        deck.binds = fixture_binds()
        deck._controller_hub = lambda: SimpleNamespace(watch=Mock())
        with patch.object(elite_recorder, "BoundKeyboard"), patch.object(elite_recorder.SequenceRecorder, "start"):
            for payload in ({"target": "not_a_command"}, {"target": "new", "place": "fighter"}, {"target": "app_greeting"}, {"target": "new", "place": []}):
                self.assertFalse(deck._handle_sequence_command("sequence_record", payload))
            self.assertTrue(deck._handle_sequence_command("sequence_record", {"target": "new", "place": "srv"}))
            state = deck._ship_recorder_state()
            self.assertEqual((state["target"], state["place"]), ("new", "srv"))
            self.assertTrue(deck._handle_sequence_command("sequence_discard", {"record_id": state["id"]}))
            self.assertEqual(deck.config["watcher_ship_macros"], {"request_docking": ["UI_Select"]})

    def test_app_hotkeys_and_controller_shortcuts_do_not_fire_during_recording(self):
        app = dashboard()
        app.is_running = True
        app._ship_recording = Mock(return_value=True)
        app._ui_post = Mock()
        app._watcher_talk_key = Mock()
        app._handle_overlay_hotkey("watcher_talk")
        app._controller_pressed("watcher_talk", "pad:A")
        app._watcher_talk_key.assert_not_called()
        app._ui_post.assert_not_called()

    def test_recorded_sequence_save_rejects_a_changed_commander(self):
        app = dashboard()
        app._apply_settings_changes = Mock()
        original = get_active_profile(app.config)
        app.config["active_commander_profile"] = "other"
        payload = {"page": "settings", "operation": "save", "save_id": 7, "recorded_profile": original,
                   "values": {"watcher_ship_macros": {"request_docking": ["UI_Select"]}}}
        self.assertFalse(app._handle_html_workspace_command(payload))
        self.assertFalse(app._html_settings_last_save["ok"])
        app._persist_config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
