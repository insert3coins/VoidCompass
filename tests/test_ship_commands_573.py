"""The Watcher works the ship (5.7.3): "open the galaxy map", "gear down",
"four pips to systems". What a request means, in the ship, the SRV or on
foot; whether Status.json says it's done already; the presses that set the
power distributor (read back and planned again when the game disagrees);
the keyboard key your bindings give each action, and what it says when
there's only a pad button. Keys go only to Elite, while it's in front.
"""
import ctypes
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest import mock

from voidcompass.core import elite_keys
from voidcompass.core.elite_binds import Slot
from voidcompass.dashboard import dashboard_ship_control_mixin as ship_mixin
from voidcompass.dashboard.dashboard_ship_control_mixin import DashboardShipControlMixin
from voidcompass.overlays import watcher_ship as ws

ROOT = Path(__file__).resolve().parents[1]


class RequestTests(unittest.TestCase):
    def asks(self, text):
        found = ws.request(text)
        return (found["command"], found["op"]) if found else None

    def test_what_it_understands(self):
        for text, wanted in (
                ("open the galaxy map", ("galaxy_map", "on")), ("Close the galaxy map.", ("galaxy_map", "off")),
                ("galaxy map", ("galaxy_map", "on")), ("can you open the system map?", ("system_map", "on")),
                ("gear down", ("gear", "on")), ("lower the landing gear please", ("gear", "on")),
                ("landing gear up", ("gear", "off")), ("deploy hardpoints", ("hardpoints", "on")),
                ("hardpoints in", ("hardpoints", "off")), ("lights on", ("lights", "on")),
                ("turn the lights off", ("lights", "off")), ("toggle the lights", ("lights", "toggle")),
                ("silent running", ("silent_running", "on")), ("flight assist off", ("flight_assist", "off")),
                ("analysis mode", ("analysis_mode", "on")), ("combat mode", ("combat_mode", "on")),
                ("heat sink", ("heat_sink", "press")), ("pop a heat sink", ("heat_sink", "press")),
                ("jump", ("jump", "press")), ("jump to the next system", ("jump", "press")),
                ("target the next system", ("next_route_system", "press")), ("engage supercruise", ("supercruise", "press")),
                ("full throttle", ("throttle_100", "press")), ("full speed", ("throttle_100", "press")),
                ("all stop", ("throttle_0", "press")), ("next target", ("next_target", "press")),
                ("recall the ship", ("recall_ship", "press")), ("holster", ("holster", "press")),
                ("open the FSS", ("fss", "on")), ("close the fss", ("fss", "off")), ("open comms", ("comms_panel", "on")),
                ("fighter attack my target", ("fighter_attack", "press")), ("open the cargo scoop", ("scoop", "on"))):
            with self.subTest(text=text):
                self.assertEqual(self.asks(text), wanted)

    def test_talk_that_only_mentions_it_does_nothing(self):
        for text in ("I like the galaxy map a lot", "what is the galaxy map", "is the gear down?", "heat sink off",
                     "where are the lights", "balance", "tell me about supercruise", "", "the lights were lovely"):
            with self.subTest(text=text):
                self.assertIsNone(ws.request(text))
                self.assertIsNone(ws.power_request(text))

    def test_nothing_that_throws_cargo_away_or_destroys_the_ship(self):
        actions = {action for command in ws.COMMANDS for table in (command.actions, command.close)
                   for action in table.values()}
        self.assertFalse({action for action in actions if "Eject" in action or "Destruct" in action or "Jettison" in action})

    def test_where_you_are(self):
        self.assertEqual(ws.place(0, 0), "ship")
        self.assertEqual(ws.place(ws.IN_SRV, 0), "srv")
        self.assertEqual(ws.place(ws.IN_FIGHTER, 0), "fighter")
        self.assertEqual(ws.place(ws.IN_SRV, ws.ON_FOOT), "foot")
        lights = ws.BY_ID["lights"]
        self.assertEqual((lights.action("ship"), lights.action("srv"), lights.action("foot")),
                         ("ShipSpotLightToggle", "HeadlightsBuggyButton", "HumanoidToggleFlashlightButton"))
        self.assertEqual(ws.BY_ID["gear"].action("fighter"), "LandingGearToggle", "a fighter flies like the ship")
        self.assertIsNone(ws.BY_ID["hardpoints"].action("foot"))
        self.assertEqual(ws.BY_ID["fss"].action("ship", "off"), "ExplorationFSSQuit")

    def test_done_already(self):
        gear, fa, galaxy = ws.BY_ID["gear"], ws.BY_ID["flight_assist"], ws.BY_ID["galaxy_map"]
        self.assertEqual(ws.already(gear, "on", ws.GEAR), "already")
        self.assertEqual(ws.already(gear, "off", ws.GEAR), "")
        self.assertEqual(ws.already(gear, "toggle", ws.GEAR), "", "a toggle always presses")
        self.assertEqual(ws.already(fa, "off", ws.FA_OFF), "already", "the flag says assist is OFF")
        self.assertEqual(ws.already(fa, "on", 0), "already")
        self.assertEqual(ws.already(galaxy, "on", focus=6), "already")
        self.assertEqual(ws.already(galaxy, "off", focus=0), "not_open")
        self.assertEqual(ws.already(ws.BY_ID["lights"], "on", ws.LIGHTS, where="foot"), "", "nothing known on foot")


class PowerTests(unittest.TestCase):
    def test_what_it_understands(self):
        for text, wanted in (
                ("four pips to systems", {"target": (8, 2, 2)}), ("4 pips to sys", {"target": (8, 2, 2)}),
                ("max engines", {"target": (2, 8, 2)}), ("full power to weapons", {"target": (2, 2, 8)}),
                ("4 sys 2 wep", {"target": (8, 0, 4)}), ("systems 4 weapons 2", {"target": (8, 0, 4)}),
                ("pips 4 0 2", {"target": (8, 0, 4)}), ("three pips to weapons", {"target": (3, 3, 6)}),
                ("balance power", {"reset": True}), ("reset the pips", {"reset": True}),
                ("power to weapons", {"press": "wep"}), ("more power to engines", {"press": "eng"}),
                ("4 sys 4 eng", {"invalid": True}), ("pips 4 4 4", {"invalid": True})):
            with self.subTest(text=text):
                self.assertEqual(ws.power_request(text), wanted)

    def test_a_press_moves_one_pip_and_keeps_six_in_all(self):
        self.assertEqual(ws.press_power((4, 4, 4), "sys"), (6, 3, 3))
        self.assertEqual(ws.press_power((6, 3, 3), "sys"), (8, 2, 2))
        self.assertEqual(ws.press_power((8, 2, 2), "sys"), (8, 2, 2), "four is the most")
        self.assertEqual(ws.press_power((6, 0, 6), "wep"), (4, 0, 8), "all from one when the other is empty")
        self.assertEqual(ws.press_power((7, 1, 4), "sys"), (8, 1, 3), "half a pip near the top")
        for _ in range(500):
            state = ws.BALANCED
            for system in random.choices(list(ws.SYSTEMS), k=6):
                state = ws.press_power(state, system)
                self.assertEqual(sum(state), 12)
                self.assertTrue(all(0 <= value <= 8 for value in state))

    def test_the_fewest_presses(self):
        self.assertEqual(ws.plan_power((4, 4, 4), (8, 2, 2)), ["sys", "sys"])
        self.assertEqual(ws.plan_power((8, 2, 2), (2, 8, 2)), ["reset", "eng", "eng"])
        self.assertEqual(ws.plan_power(None, (8, 2, 2)), ["reset", "sys", "sys"], "unknown: from a reset")
        self.assertEqual(ws.plan_power((2, 4, 6), ws.BALANCED), ["reset"])
        self.assertEqual(ws.plan_power((8, 2, 2), (8, 2, 2)), [])
        self.assertEqual(ws.pips_words((8, 0, 4)), "systems 4, engines 0, weapons 2")
        self.assertEqual(ws.pips_words((3, 3, 6)), "systems 1.5, engines 1.5, weapons 3")


class KeyTests(unittest.TestCase):
    def test_elite_key_names_to_scancodes(self):
        self.assertEqual(elite_keys.scancode("Key_A"), (0x1E, False))
        self.assertEqual(elite_keys.scancode("Key_L"), (0x26, False))
        self.assertEqual(elite_keys.scancode("Key_1"), (0x02, False))
        self.assertEqual(elite_keys.scancode("Key_F12"), (0x58, False))
        self.assertEqual(elite_keys.scancode("Key_Numpad_0"), (0x52, False))
        self.assertEqual(elite_keys.scancode("Key_Home"), (0x47, True), "the grey keys are extended")
        self.assertEqual(elite_keys.scancode("Key_RightControl"), (0x1D, True))
        self.assertEqual(elite_keys.scancode("Key_backslash"), (0x2B, False), "any case")
        self.assertIsNone(elite_keys.scancode("Key_Nonsense"))
        # Every key Elite's own presets use (read from its ControlSchemes, 5.7.3).
        for name in ("0 1 2 3 4 5 6 7 8 9 A Apostrophe B BackSlash Backspace C Comma D Delete DownArrow E End Enter "
                     "Equals F F1 F12 G H Home I Insert J L LeftAlt LeftArrow LeftBracket LeftControl LeftShift M Minus "
                     "N Numpad_0 Numpad_1 Numpad_2 Numpad_3 Numpad_4 Numpad_5 Numpad_6 Numpad_7 Numpad_8 Numpad_9 O P "
                     "PageDown PageUp Period Q R RightArrow RightBracket RightControl RightShift S Slash Space T Tab U "
                     "UpArrow V W X Y Z").split():
            self.assertIsNotNone(elite_keys.scancode(f"Key_{name}"), name)

    def test_labels_and_keyboard_bindings(self):
        self.assertEqual(elite_keys.label("Key_Home", ("Key_LeftShift",)), "Left Shift+Home")
        self.assertEqual(elite_keys.label("Key_Numpad_Add"), "Numpad Add")
        self.assertEqual(elite_keys.label("Key_L"), "L")
        slots = [Slot("GamePad", "GamePad_DPadLeft", [("GamePad", "GamePad_FaceUp")]),
                 Slot("Keyboard", "Key_G", [("Keyboard", "Key_LeftShift")])]
        self.assertEqual(elite_keys.keyboard_slot(slots), ("Key_G", ("Key_LeftShift",)))
        self.assertIsNone(elite_keys.keyboard_slot(slots[:1]), "a pad button can't be pressed")
        self.assertIsNone(elite_keys.keyboard_slot([Slot("Keyboard", "Key_G", [("GamePad", "GamePad_LBumper")])]),
                          "nor a key held with a pad button")
        self.assertEqual(elite_keys.pressable("Key_Nonsense", ("Key_LeftShift",)), ("Key_Nonsense",))

    def test_a_press_holds_its_modifiers_around_it_and_lets_go(self):
        sent = []
        presser = elite_keys.KeyPresser(lambda: True, send=lambda code, ext, up: sent.append((code, ext, up)) or True,
                                        sleep=lambda _s: None)
        self.assertTrue(presser.press("Key_Home", ("Key_LeftShift",)))
        self.assertEqual(sent, [(0x2A, False, False), (0x47, True, False), (0x47, True, True), (0x2A, False, True)])

    def test_only_while_elite_is_in_front(self):
        sent, front = [], iter([True, False])
        presser = elite_keys.KeyPresser(lambda: next(front), send=lambda code, ext, up: sent.append((code, up)) or True,
                                        sleep=lambda _s: None)
        self.assertFalse(presser.press("Key_G", ("Key_LeftShift",)))
        self.assertEqual(sent, [(0x2A, False), (0x2A, True)], "the held modifier is let go; G never goes down")
        sent.clear()
        presser = elite_keys.KeyPresser(lambda: True, send=lambda code, ext, up: sent.append(code) or True)
        self.assertFalse(presser.press("Key_Nonsense"))
        self.assertEqual(sent, [], "an unknown key: nothing pressed")

    @unittest.skipUnless(sys.platform == "win32" and ctypes.sizeof(ctypes.c_void_p) == 8, "64-bit Windows")
    def test_sendinput_structure(self):
        _keyboard, input_type = elite_keys._input_types()
        self.assertEqual(ctypes.sizeof(input_type), 40)


# -- the deck ------------------------------------------------------------------------------
def keys(**actions):
    return {action: [Slot("Keyboard", key, [("Keyboard", mod) for mod in mods])] for action, (key, *mods) in actions.items()}


class FakeBinds:
    def __init__(self):
        self.error = ""
        self.actions = {
            "ship": {**keys(GalaxyMapOpen=("Key_G", "Key_LeftShift"), LandingGearToggle=("Key_L",),
                            ShipSpotLightToggle=("Key_Insert",), DeployHeatSink=("Key_V",),
                            IncreaseSystemsPower=("Key_LeftArrow",), IncreaseEnginesPower=("Key_UpArrow",),
                            IncreaseWeaponsPower=("Key_RightArrow",), ResetPowerDistribution=("Key_DownArrow",)),
                     "SystemMapOpen": [Slot("GamePad", "GamePad_DPadRight", [("GamePad", "GamePad_FaceUp")])]},
            "srv": keys(HeadlightsBuggyButton=("Key_Delete",)),
            "general": {}, "onfoot": {}}

    def refresh(self, force=False):
        return True

    def summary(self):
        return [{"group": "general", "label": "General", "preset": "ConsoleX360"},
                {"group": "ship", "label": "Ship", "preset": "ConsoleX360"},
                {"group": "srv", "label": "SRV", "preset": "Custom"},
                {"group": "onfoot", "label": "On foot", "preset": "KeyboardMouseOnly"}]


class FakeGame:
    def __init__(self, running=True, forward=True):
        self.running, self.forward, self.brought = running, forward, 0

    def find(self):
        return 7 if self.running else 0

    def bring_forward(self):
        self.brought += 1
        return self.forward

    def in_front(self):
        return self.forward


class FakePresser:
    """Presses go to a pretend game: ``on_press`` is what the game does."""

    def __init__(self, on_press=None):
        self.pressed = []
        self.on_press = on_press

    def press(self, key, modifiers=(), hold=0):
        self.pressed.append(elite_keys.label(key, modifiers))
        if self.on_press:
            self.on_press(key)
        return True


class FakeMind:
    random = None

    def __init__(self):
        self.after = []

    def say_after(self, words):
        self.after.append(words)


class Deck(DashboardShipControlMixin):
    def __init__(self, **config):
        self.config = {"watcher_ship_enabled": True, **config}
        self.binds = FakeBinds()
        self.current_status_flags = self.current_status_flags2 = 0
        self.current_gui_focus = 0
        self.current_pips = [4, 4, 4]
        self._ship_game_window = FakeGame()
        self._ship_key_presser = FakePresser()
        self.jobs = []
        self.heartbeat_hud = type("Hud", (), {"mind": FakeMind()})()

    def _elite_binds(self):
        return self.binds

    def _ship_queue(self, job):
        self.jobs.append(job)

    def _ui_post(self, callback, *args, key=None):
        callback(*args)

    def _watcher_mind_watch(self):
        pass

    def run(self):
        """The queued presses, as the ship-keys thread runs them."""
        outcomes = [job() for job in self.jobs]
        self.jobs.clear()
        return outcomes


class DeckTests(unittest.TestCase):
    def test_asked_pressed_and_said(self):
        deck = Deck()
        self.assertEqual(deck._watcher_ship("open the galaxy map"), "The galaxy map.")
        self.assertEqual(deck.run(), [None])
        self.assertEqual(deck._ship_key_presser.pressed, ["Left Shift+G"])
        self.assertEqual(deck._ship_game_window.brought, 1, "Elite brought forward first")
        self.assertEqual(deck._watcher_ship("gear down"), "The landing gear: down.")
        self.assertEqual(deck._watcher_ship("heat sink"), "Heat sink away.")
        self.assertIsNone(deck._watcher_ship("what's for dinner"), "nothing of the ship")

    def test_done_already_presses_nothing(self):
        deck = Deck()
        deck.current_gui_focus = 6
        self.assertEqual(deck._watcher_ship("open the galaxy map"), "The galaxy map is already open.")
        deck.current_gui_focus = 0
        self.assertEqual(deck._watcher_ship("close the galaxy map"), "The galaxy map isn't open.")
        deck.current_status_flags = ws.GEAR
        self.assertEqual(deck._watcher_ship("gear down"), "The landing gear is already down.")
        self.assertEqual(deck.jobs, [])

    def test_a_pad_button_only_says_so(self):
        deck = Deck()
        said = deck._watcher_ship("open the system map")
        self.assertIn("no keyboard key in Elite's controls", said)
        self.assertEqual(deck.jobs, [])

    def test_off_not_running_and_not_here(self):
        deck = Deck(watcher_ship_enabled=False)
        self.assertIn("Settings, under Voice", deck._watcher_ship("gear down"))
        deck = Deck()
        deck._ship_game_window.running = False
        self.assertEqual(deck._watcher_ship("gear down"), "Elite isn't running. Nothing to press.")
        deck = Deck()
        deck.current_status_flags2 = ws.ON_FOOT
        self.assertEqual(deck._watcher_ship("deploy hardpoints"), "That's not one for on foot.")
        self.assertEqual(deck.jobs, [])

    def test_the_srv_has_its_own_keys(self):
        deck = Deck()
        deck.current_status_flags = ws.IN_SRV
        deck._watcher_ship("lights on")
        deck.run()
        self.assertEqual(deck._ship_key_presser.pressed, ["Delete"])

    def test_elite_wont_come_forward(self):
        deck = Deck()
        deck._ship_game_window.forward = False
        deck._watcher_ship("gear down")
        problem = deck.run()[0]
        self.assertEqual(problem, "focus_failed")
        deck._watcher_ship_follow_up(problem)
        self.assertEqual(deck.heartbeat_hud.mind.after, ["Elite wouldn't come to the front, so I pressed nothing."])
        self.assertEqual(deck._ship_key_presser.pressed, [])

    def game(self, deck, start, rule=ws.press_power):
        """A pretend distributor behind Status.json, answering each press."""
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [path.unlink() for path in folder.iterdir()] and None or folder.rmdir())
        status = folder / "Status.json"
        status.write_text(json.dumps({"Pips": list(start)}), encoding="utf-8")
        deck.config["journal_path"] = str(folder)
        systems = {"Key_LeftArrow": "sys", "Key_UpArrow": "eng", "Key_RightArrow": "wep"}

        def answer(key):
            state = tuple(json.loads(status.read_text(encoding="utf-8"))["Pips"])
            state = ws.BALANCED if key == "Key_DownArrow" else rule(state, systems[key])
            status.write_text(json.dumps({"Pips": list(state)}), encoding="utf-8")

        deck._ship_key_presser.on_press = answer
        return lambda: tuple(json.loads(status.read_text(encoding="utf-8"))["Pips"])

    def test_pips_set_and_read_back(self):
        deck = Deck()
        pips = self.game(deck, (4, 4, 4))
        with mock.patch.object(ship_mixin, "POWER_WAIT_S", 0.2):
            self.assertEqual(deck._watcher_ship("four pips to systems"), "Power: systems 4, engines 1, weapons 1.")
            self.assertEqual(deck.run(), [None])
        self.assertEqual(pips(), (8, 2, 2))
        self.assertEqual(deck._ship_key_presser.pressed, ["Left", "Left"])

    def test_pips_planned_again_from_the_game(self):
        """The deck's copy is a second behind: the game's own is used."""
        deck = Deck()
        deck.current_pips = [4, 4, 4]
        pips = self.game(deck, (2, 4, 6))
        with mock.patch.object(ship_mixin, "POWER_WAIT_S", 0.2):
            deck._watcher_ship("max systems")
            self.assertEqual(deck.run(), [None])
        self.assertEqual(pips(), (8, 2, 2))

    def test_a_distributor_that_doesnt_answer(self):
        deck = Deck()
        self.game(deck, (4, 4, 4), rule=lambda state, _system: state)
        with mock.patch.object(ship_mixin, "POWER_WAIT_S", 0.1):
            deck._watcher_ship("4 sys 2 wep")
            self.assertEqual(deck.run(), ["power_stuck"])
        self.assertEqual(len(deck._ship_key_presser.pressed), 1, "it stopped after the first press")

    def test_one_press_and_balance(self):
        deck = Deck()
        self.assertEqual(deck._watcher_ship("power to weapons"), "More to weapons.")
        self.assertEqual(deck._watcher_ship("balance power"), "The power's already there: systems 2, engines 2, weapons 2.")
        deck.current_pips = [8, 2, 2]
        self.assertEqual(deck._watcher_ship("balance power"), "Power balanced.")
        deck.run()
        self.assertEqual(deck._ship_key_presser.pressed, ["Right", "Down"])
        self.assertIn("Six pips in all", deck._watcher_ship("4 sys 4 eng"))

    def test_settings_shows_what_needs_a_key(self):
        deck = Deck()
        page = deck._html_ship_controls()
        self.assertTrue(page["enabled"])
        self.assertTrue(page["running"])
        from voidcompass.core import voice_commands
        self.assertEqual(page["total"], len(voice_commands.builtins()))
        rows = {row["say"]: row for group in page["groups"] for row in group["rows"]}
        self.assertEqual(rows["open the galaxy map"]["state"], "some", "the ship's key, not the SRV's or on foot")
        self.assertEqual(rows["open the galaxy map"]["cells"][0], {"where": "Ship", "action": "Galaxy map open",
                                                                    "key": "Left Shift+G", "problem": ""})
        self.assertEqual(rows["gear down"]["state"], "ready")
        missing = {(row["action"], row["where"]): row for row in page["missing"]}
        self.assertEqual(missing["System map open", "Ship"]["preset"], "Ship · ConsoleX360")
        self.assertEqual(missing["System map open", "On foot"]["preset"], "On foot · KeyboardMouseOnly")
        self.assertEqual(missing["System map open", "Ship"]["say"], "open the system map")
        self.assertNotIn(("Landing gear toggle", "Ship"), missing)
        self.assertIn("Power", [group["title"] for group in page["groups"]])


class WiringTests(unittest.TestCase):
    def test_the_watcher_asks_the_ship_and_settings_shows_it(self):
        voice = (ROOT / "src/voidcompass/dashboard/dashboard_watcher_voice_mixin.py").read_text(encoding="utf-8")
        self.assertIn('getattr(self, "_watcher_ship", None)', voice)
        board = (ROOT / "src/voidcompass/dashboard/dashboard.py").read_text(encoding="utf-8")
        self.assertIn("DashboardShipControlMixin,", board)
        self.assertIn("self._ship_close()", board)
        from voidcompass.core import config
        self.assertIn("watcher_ship_enabled", config.PROFILE_BOOL_SETTINGS)


if __name__ == "__main__":
    unittest.main()
