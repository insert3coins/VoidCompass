"""Panels and bound-key sequences, with a pretend game and no real key presses."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from voidcompass.core import elite_macros
from voidcompass.dashboard import dashboard_ship_control_mixin as ship_mixin
from voidcompass.overlays import watcher_ship as ws
from tests.test_ship_commands_573 import Deck, keys


class SequenceParsingTests(unittest.TestCase):
    def test_repeats_waits_holds_and_conditional_panels(self):
        steps = elite_macros.parse_macro(["focus FocusLeftPanel 2", "UI_Down x3", "wait 0.5",
                                          "hold UI_Select 1.2", "ensure FocusLeftPanel 2", "leave UI_Back 2"])
        self.assertEqual([step.kind for step in steps],
                         ["focus", "press", "press", "press", "wait", "hold", "focus", "leave"])
        self.assertEqual(steps[5].seconds, 1.2)
        self.assertEqual(elite_macros.actions_in(steps), ("FocusLeftPanel", "UI_Down", "UI_Select", "UI_Back"))

    def test_rejects_invalid_or_unbounded_sequences_before_execution(self):
        for lines in ([], "UI_Select", [None], [""], ["wait"], ["wait nan"], ["wait inf"], ["wait -1"],
                      ["wait 6"], ["wait 1"], ["hold UI_Select 0"], ["hold UI_Select nan"],
                      ["UI_Down x0"], ["UI_Down x13"], ["UI_Down x12"] * 6,
                      ["UI_Down x12"] * 5 + ["wait 1"], ["leave UI_Back 0"],
                      ["focus FocusLeftPanel 99"], ["press some desktop keys"], ["EjectAllCargo"], ["SelfDestruct"]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                elite_macros.parse_macro(lines)


class CommandCoverageTests(unittest.TestCase):
    def test_every_catalogue_example_is_recognised(self):
        for command in ws.COMMANDS:
            with self.subTest(command=command.id):
                asked = ws.request(command.example)
                self.assertIsNotNone(asked)
                self.assertEqual(asked["command"], command.id)

    def test_natural_map_panel_and_sequence_phrases(self):
        for phrase, ident, op in (
                ("show me the galaxy map", "galaxy_map", "on"),
                ("open galaxey map", "galaxy_map", "on"),
                ("let me see the star map", "galaxy_map", "on"),
                ("bring up the solar system map please", "system_map", "on"),
                ("back out of the local map", "system_map", "off"),
                ("open the left hand panel", "left_panel", "on"),
                ("show navigation", "left_panel", "on"),
                ("open the contacts panel", "left_panel", "on"),
                ("show modules", "right_panel", "on"),
                ("check messages", "comms_panel", "on"),
                ("open the helm panel", "role_panel", "on"),
                ("request docking permission", "request_docking", "press"),
                ("request permission to land", "request_docking", "press"),
                ("launch the Nomad", "deploy_nomad", "press"),
                ("assist wingman two", "assist_wingman_2", "press"),
                ("target wingman three's target", "assist_wingman_3", "press"),
                ("equip the energy link", "energy_link", "press"),
                ("use a medical pack", "medkit", "press"),
                ("next tab", "ui_next_tab", "press"),
                ("go back", "ui_back", "press")):
            with self.subTest(phrase=phrase):
                self.assertEqual(ws.request(phrase), {"command": ident, "op": op})

    def test_questions_and_partial_requests_never_press(self):
        for phrase in ("how do I request docking", "is the contacts panel open", "I can see the galaxy map",
                       "open galaxy map and tell me a story", "close the medkit", "do I need an energy cell"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(ws.request(phrase))

    def test_orrery_is_an_open_system_map(self):
        command = ws.BY_ID["system_map"]
        self.assertEqual(ws.already(command, "on", focus=8), "already")
        self.assertEqual(ws.already(command, "off", focus=8), "")


class SequenceExecutionTests(unittest.TestCase):
    def setUp(self):
        self.deck = Deck()
        self.deck.binds.actions["ship"].update(keys(FocusLeftPanel=("Key_1",), FocusRightPanel=("Key_4",),
                                                     FocusRadarPanel=("Key_3",), TargetWingman0=("Key_F1",),
                                                     SelectTargetsTarget=("Key_T",)))
        self.deck.binds.actions["general"].update(keys(UI_Up=("Key_W",), UI_Down=("Key_S",), UI_Left=("Key_A",),
                                                        UI_Right=("Key_D",), UI_Select=("Key_Space",), UI_Back=("Key_Escape",),
                                                        CycleNextPanel=("Key_E",), CyclePreviousPanel=("Key_Q",)))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.status_path = Path(folder.name) / "Status.json"
        self.deck.config["journal_path"] = folder.name
        self.write_status()
        self.deck._ship_key_presser.on_press = self.answer
        pause = self.deck._ship_pause
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(self.deck, "_ship_pause", side_effect=lambda seconds, where: pause(0, where)).start()

    def write_status(self, focus=0, flags=0, flags2=0):
        self.status_path.write_text(json.dumps({"Flags": flags, "Flags2": flags2, "GuiFocus": focus}), encoding="utf-8")

    def answer(self, key):
        focus = {"Key_1": 2, "Key_4": 1, "Key_3": 4, "Key_Escape": 0, "Key_G": 6}.get(key)
        if focus is not None:
            self.write_status(focus)

    def test_docking_waits_for_panel_and_uses_all_the_bound_keys_in_order(self):
        self.assertEqual(self.deck._watcher_ship("request docking"), "Requesting docking.")
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed,
                         ["1", "E", "E", "D", "Space", "A", "Q", "Q", "Escape"])

    def test_a_second_docking_request_starts_with_the_tab_and_column_reset(self):
        tab, right, requests = 0, False, []
        answer = self.answer
        def station_menu(key):
            nonlocal tab, right
            answer(key)
            if key == "Key_E" and not right:
                tab += 1
            elif key == "Key_Q" and not right:
                tab -= 1
            elif key == "Key_D":
                right = True
            elif key == "Key_A":
                right = False
            elif key == "Key_Space" and tab == 2 and right:
                requests.append("docking")
        self.deck._ship_key_presser.on_press = station_menu
        for _ in range(2):
            self.deck._watcher_ship("request docking")
            self.assertEqual(self.deck.run(), [None])
            self.assertEqual((tab, right), (0, False))
        self.assertEqual(requests, ["docking", "docking"])

    def test_maps_and_panels_expose_open_and_close_editors_for_each_vehicle(self):
        rows = {row["id"]: row for group in self.deck._html_ship_controls()["groups"]
                for row in group["rows"] if "id" in row}
        for ident, action in (("galaxy_map", "GalaxyMapOpen"), ("system_map", "SystemMapOpen")):
            editors = {editor["id"]: editor for editor in rows[ident]["editors"]}
            self.assertEqual(len(editors), 6)
            self.assertEqual(editors[ident]["default_sequence"], [action])
            self.assertEqual(editors[ident + ":srv"]["default_sequence"], [action + "_Buggy"])
            self.assertEqual(editors[ident + ":foot"]["default_sequence"], [action + "_Humanoid"])
            self.assertIn("close", editors[ident + ":off"]["say"])
        self.assertEqual({editor["id"] for editor in rows["left_panel"]["editors"]},
                         {"left_panel", "left_panel:off", "left_panel:srv", "left_panel:off:srv"})

    def test_map_sequence_can_use_bound_menu_actions_when_the_direct_map_key_is_missing(self):
        self.deck.config["watcher_ship_macros"] = {"system_map": ["focus FocusLeftPanel 2", "UI_Select"],
                                                    "system_map:off": ["UI_Back"]}
        answer = self.deck._ship_key_presser.on_press

        def game(key):
            answer(key)
            if key == "Key_Space":
                self.write_status(focus=7)

        self.deck._ship_key_presser.on_press = game
        self.assertEqual(self.deck._watcher_ship("open the system map"), "The system map.")
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["1", "Space"])
        self.assertEqual(self.deck._watcher_ship("close the system map"), "Closing the system map.")
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["1", "Space", "Escape"])
        self.assertEqual(self.deck._watcher_ship("close the system map"), "The system map isn't open.")

    def test_ship_map_override_does_not_replace_the_srv_binding(self):
        self.deck.config["watcher_ship_macros"] = {"galaxy_map": ["UI_Select"]}
        self.write_status(flags=ws.IN_SRV)
        self.assertIn("no keyboard key", self.deck._watcher_ship("open the galaxy map"))
        self.assertEqual(self.deck.jobs, [])
        self.deck.config["watcher_ship_macros"]["galaxy_map:srv"] = ["UI_Select"]
        self.assertEqual(self.deck._watcher_ship("open the galaxy map"), "The galaxy map.")
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["Space"])

    def test_an_already_open_panel_is_not_toggled_shut(self):
        self.write_status(focus=2)
        self.deck._watcher_ship("request docking")
        self.assertEqual(self.deck.run(), [None])
        self.assertNotIn("1", self.deck._ship_key_presser.pressed)

    def test_missing_later_key_prevents_the_entire_sequence(self):
        del self.deck.binds.actions["general"]["UI_Right"]
        said = self.deck._watcher_ship("request docking")
        self.assertIn("UI right", said)
        self.assertEqual(self.deck.jobs, [])

    def test_panel_must_open_before_menu_keys_are_sent(self):
        self.deck._ship_key_presser.on_press = None
        self.deck._watcher_ship("deploy the Nomad")
        with mock.patch.object(ship_mixin, "PANEL_WAIT_S", 0.001):
            self.assertEqual(self.deck.run(), ["screen_stuck"])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["3"])

    def test_other_screen_and_vehicle_changes_stop_the_sequence(self):
        self.write_status(focus=6)
        self.deck._watcher_ship("request docking")
        self.assertEqual(self.deck.run(), ["screen_changed"])
        self.assertEqual(self.deck._ship_key_presser.pressed, [])
        self.write_status()
        self.deck._watcher_ship("request docking")
        self.write_status(flags2=ws.ON_FOOT)
        self.assertEqual(self.deck.run(), ["place_changed"])

    def test_focus_loss_or_changed_panel_stops_remaining_keys(self):
        def lose_focus(key):
            self.answer(key)
            self.deck._ship_game_window.forward = False
        self.deck._ship_key_presser.on_press = lose_focus
        self.deck._watcher_ship("request docking")
        self.assertEqual(self.deck.run(), ["lost_front"])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["1"])

    def test_custom_steps_repeat_and_hold_without_literal_keys(self):
        self.deck.config["watcher_ship_macros"] = {"deploy_nomad": ["focus FocusRadarPanel 4", "UI_Down x2", "hold UI_Select 1.2"]}
        self.deck._watcher_ship("deploy Nomad")
        with mock.patch.object(self.deck._ship_key_presser, "press", wraps=self.deck._ship_key_presser.press) as press:
            self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["3", "S", "S", "Space"])
        self.assertEqual(press.call_args.kwargs["hold"], 1.2)

    def test_invalid_custom_sequence_is_explained_and_not_queued(self):
        self.deck.config["watcher_ship_macros"] = {"deploy_nomad": ["wait nan"]}
        self.assertIn("sequence in Settings needs fixing", self.deck._watcher_ship("deploy Nomad"))
        self.assertEqual(self.deck.jobs, [])

    def test_assisting_wingman_is_two_distinct_bound_actions(self):
        self.deck._watcher_ship("assist wingman one")
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["F1", "T"])

    def test_menu_keys_require_an_open_screen_at_request_and_execution(self):
        self.assertIn("Open a panel", self.deck._watcher_ship("next tab"))
        self.assertEqual(self.deck.jobs, [])
        self.deck.current_gui_focus = 2
        self.write_status(focus=2)
        self.deck._watcher_ship("next tab")
        self.write_status()
        self.assertEqual(self.deck.run(), ["menu_closed"])
        self.assertEqual(self.deck._ship_key_presser.pressed, [])

    def test_panel_close_uses_back_and_checks_state_when_executed(self):
        self.deck.current_gui_focus = 2
        self.write_status(focus=2)
        self.deck._watcher_ship("close the left panel")
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["Escape"])
        self.assertEqual(self.deck._watcher_ship("close the left panel"), "The left panel isn't open.")
        self.assertEqual(self.deck.run(), [], "already closed in the game's newer status")
        self.assertEqual(self.deck._ship_key_presser.pressed, ["Escape"])

    def test_toggle_map_closes_when_open_and_late_open_does_not_toggle_again(self):
        self.deck.current_gui_focus = 6
        self.write_status(focus=6)
        self.assertEqual(self.deck._watcher_ship("toggle galaxy map"), "Closing the galaxy map.")
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["Left Shift+G"])
        self.deck.current_gui_focus = 0
        self.write_status()
        self.deck._watcher_ship("open the galaxy map")
        self.write_status(focus=6)
        self.assertEqual(self.deck.run(), [None])
        self.assertEqual(self.deck._ship_key_presser.pressed, ["Left Shift+G"])

    def test_launch_requires_docked_cockpit_even_after_queueing(self):
        self.assertIn("docked", self.deck._watcher_ship("launch the ship"))
        self.deck.current_status_flags = 1
        self.write_status(flags=1)
        self.deck._watcher_ship("launch the ship")
        self.write_status()
        self.assertEqual(self.deck.run(), ["not_docked"])

    def test_settings_requires_every_sequence_key_and_exposes_steps(self):
        del self.deck.binds.actions["general"]["UI_Right"]
        page = self.deck._html_ship_controls()
        row = next(row for group in page["groups"] for row in group["rows"] if row.get("id") == "request_docking")
        self.assertEqual(row["state"], "none")
        self.assertTrue(row["sequence"])
        self.assertTrue(any(item["action"] == "UI right" for item in page["missing"]))
        self.assertTrue(any(cell["action"] == "UI right" and cell["problem"] for cell in row["cells"]))


if __name__ == "__main__":
    unittest.main()
