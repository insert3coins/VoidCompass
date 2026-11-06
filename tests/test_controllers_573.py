"""5.7.3: controller buttons as shortcuts, and Elite's own bindings.

Elite's bindings are read for any commander: the four presets in
StartPreset.4.start (General, Ship, SRV, On foot) or Horizons' one, each a
file of yours or a built-in one from the game's install (found through
Steam, Epic, the Frontier launcher, a folder you give, or the running game).
Controllers are read through XInput (Xbox-style pads) and winmm (the rest),
here faked; a controller plugged in later is found because winmm is told to
look again."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from voidcompass.core import controller_input as ci
from voidcompass.core import elite_binds as eb
from voidcompass.core.overlay_registry import OVERLAY_HOTKEY_SPECS
from voidcompass.dashboard.dashboard_controller_mixin import DashboardControllerMixin

SHIP_PAD = """<?xml version="1.0" encoding="UTF-8" ?>
<Root PresetName="ConsoleX360" MajorVersion="4" MinorVersion="0">
  <LandingGearToggle>
    <Primary Device="GamePad" Key="GamePad_FaceDown"><Modifier Device="GamePad" Key="GamePad_LBumper" /></Primary>
    <Secondary Device="Keyboard" Key="Key_L" />
  </LandingGearToggle>
  <SelectTarget>
    <Primary Device="GamePad" Key="GamePad_FaceDown" />
    <Secondary Device="{NoDevice}" Key="" />
  </SelectTarget>
  <UI_Select>
    <Primary Device="GamePad" Key="Pad_A" />
    <Secondary Device="Keyboard" Key="Key_Space" />
  </UI_Select>
  <ThrottleAxis>
    <Binding Device="GamePad" Key="GamePad_LTrigger" />
  </ThrottleAxis>
  <HyperSuperCombination>
    <Primary Device="Keyboard" Key="Key_J"><Modifier Device="Keyboard" Key="Key_LeftControl" /></Primary>
    <Secondary Device="SaitekX52" Key="Joy_7" />
  </HyperSuperCombination>
  <FocusLeftPanel>
    <Primary Device="06A3075C" Key="Joy_POV1Left" />
    <Secondary Device="{NoDevice}" Key="" />
  </FocusLeftPanel>
  <ToggleCargoScoop_Buggy>
    <Primary Device="GamePad" Key="GamePad_FaceDown" />
    <Secondary Device="{NoDevice}" Key="" />
  </ToggleCargoScoop_Buggy>
  <HumanoidJumpButton>
    <Primary Device="Keyboard" Key="Key_Space" />
    <Secondary Device="{NoDevice}" Key="" />
  </HumanoidJumpButton>
</Root>"""

YOURS = """<?xml version="1.0" encoding="UTF-8" ?>
<Root PresetName="Custom" MajorVersion="4" MinorVersion="2">
  <ToggleCargoScoop_Buggy>
    <Primary Device="Keyboard" Key="Key_Home" />
    <Secondary Device="{NoDevice}" Key="" />
  </ToggleCargoScoop_Buggy>
  <LandingGearToggle>
    <Primary Device="Keyboard" Key="Key_G" />
    <Secondary Device="{NoDevice}" Key="" />
  </LandingGearToggle>
</Root>"""

MAPPINGS = """<?xml version="1.0" encoding="UTF-8" ?>
<Root>
  <GamePad><PID>028E</PID><VID>045E</VID><Alternative><PID>0B13</PID><VID>045E</VID></Alternative></GamePad>
  <SaitekX52><PID>075C</PID><VID>06A3</VID><Alternative><PID>075c</PID><VID>0738</VID></Alternative></SaitekX52>
</Root>"""


class GameFolders(unittest.TestCase):
    """A Bindings folder and a Steam install, made up in a temp folder."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.bindings = self.root / "Bindings"
        self.bindings.mkdir()
        self.steam = self.root / "Steam"
        self.schemes = self.steam / "steamapps" / "common" / "Elite Dangerous" / "Products" / eb.PRODUCTS[0] / "ControlSchemes"
        self.schemes.mkdir(parents=True)
        (self.schemes / "ConsoleX360.binds").write_text(SHIP_PAD, encoding="utf-8")
        (self.schemes / "DeviceMappings.xml").write_text(MAPPINGS, encoding="utf-8")
        self.environ = {"LOCALAPPDATA": str(self.root), "ProgramFiles(x86)": str(self.root), "ProgramData": str(self.root)}

    def start(self, *lines, name="StartPreset.4.start"):
        (self.bindings / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def binds(self):
        with mock.patch.object(eb, "_steam_libraries", return_value=[self.steam]):
            book = eb.EliteBinds(folder=self.bindings, environ=self.environ, game_folder=None)
            book.refresh(force=True)
        return book


class PresetTests(GameFolders):
    def test_four_groups_built_in_or_yours(self):
        self.start("ConsoleX360", "ConsoleX360", "Custom", "KeyboardMouseOnly")
        (self.bindings / "Custom.4.2.binds").write_text(YOURS, encoding="utf-8")
        (self.bindings / "Custom.3.0.binds").write_text(YOURS, encoding="utf-8")
        book = self.binds()
        groups = {row["group"]: row for row in book.summary()}
        self.assertEqual(groups["ship"]["preset"], "ConsoleX360")
        self.assertTrue(groups["ship"]["built_in"], "a built-in preset, from the game's install")
        self.assertEqual(Path(groups["srv"]["path"]).name, "Custom.4.2.binds", "yours, its newest version")
        self.assertFalse(groups["srv"]["built_in"])
        self.assertFalse(groups["onfoot"]["found"], "KeyboardMouseOnly isn't in this made-up install")
        self.assertIn("KeyboardMouseOnly", book.error)
        self.assertTrue(book.odyssey)

    def test_horizons_one_preset_for_everything(self):
        self.start("ConsoleX360", name="StartPreset.start")
        book = self.binds()
        self.assertEqual({row["preset"] for row in book.summary()}, {"ConsoleX360"})
        self.assertFalse(book.odyssey)

    def test_no_controls_folder(self):
        book = eb.EliteBinds(folder=self.root / "missing", environ=self.environ, game_folder=None)
        self.assertFalse(book.refresh(force=True))
        self.assertIn("weren't found", book.error)
        self.assertEqual(book.clashes(("keyboard", "Key_L", set())), [])

    def test_found_through_the_running_game_or_a_folder_you_give(self):
        product = self.root / "Elsewhere" / "Products" / eb.PRODUCTS[0]
        (product / "ControlSchemes").mkdir(parents=True)
        (product / "ControlSchemes" / "SaitekX52.binds").write_text(SHIP_PAD, encoding="utf-8")
        self.start("SaitekX52")
        with mock.patch.object(eb, "_steam_libraries", return_value=[]):
            book = eb.EliteBinds(folder=self.bindings, environ=self.environ, game_folder=lambda: product)
            self.assertTrue(book.refresh(force=True), "the running game's folder")
            book = eb.EliteBinds(folder=self.bindings, environ=self.environ, game_folder=None,
                                 chosen=lambda: str(self.root / "Elsewhere"))
            self.assertTrue(book.refresh(force=True), "a folder you give")

    def test_steam_libraries_and_epic(self):
        library = self.root / "Library2"
        (self.steam / "steamapps").mkdir(parents=True, exist_ok=True)
        (self.steam / "steamapps" / "libraryfolders.vdf").write_text(
            '"libraryfolders"\n{\n "0"\n {\n  "path"  "%s"\n }\n}\n' % str(library).replace("\\", "\\\\"), encoding="utf-8")
        with mock.patch("winreg.OpenKey", side_effect=OSError):
            libraries = eb._steam_libraries({"ProgramFiles(x86)": str(self.root)})
        self.assertIn(library, libraries)
        manifests = self.root / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
        manifests.mkdir(parents=True)
        (manifests / "x.item").write_text(json.dumps({"DisplayName": "Elite Dangerous", "InstallLocation": "E:/Elite"}),
                                          encoding="utf-8")
        self.assertEqual(eb._epic_installs({"ProgramData": str(self.root)}), [Path("E:/Elite")])

    def test_read_again_only_when_a_file_changes(self):
        self.start("Custom", "Custom", "Custom", "Custom")
        yours = self.bindings / "Custom.4.2.binds"
        yours.write_text(YOURS, encoding="utf-8")
        book = self.binds()
        self.assertEqual(book.clashes(("keyboard", "Key_G", set())), ["Landing gear toggle (Ship)"])
        yours.write_text(YOURS.replace("Key_G", "Key_K"), encoding="utf-8")
        import os
        os.utime(yours, ns=(yours.stat().st_atime_ns, yours.stat().st_mtime_ns + 10_000_000))
        with mock.patch.object(eb, "_steam_libraries", return_value=[self.steam]):
            book.refresh(force=True)
        self.assertEqual(book.clashes(("keyboard", "Key_K", set())), ["Landing gear toggle (Ship)"])


class ClashTests(GameFolders):
    def setUp(self):
        super().setUp()
        self.start("ConsoleX360", "ConsoleX360", "ConsoleX360", "ConsoleX360")
        self.book = self.binds()

    def test_pad_buttons_in_both_spellings_and_combinations(self):
        self.assertEqual(self.book.clashes(("pad", "A", set())), ["UI select (General)", "Select target (Ship)",
                                                                  "Toggle cargo scoop (SRV)"])
        self.assertEqual(self.book.clashes(("pad", "A", {"LB"})), ["Landing gear toggle (Ship)"])
        self.assertEqual(self.book.clashes(("pad", "B", {"LB"})), [], "a free combination")
        self.assertEqual(self.book.clashes(("pad", "LT", set())), ["Throttle axis (Ship)"], "a trigger used as an axis")

    def test_keyboard_keys_with_their_modifiers(self):
        self.assertEqual(self.book.clashes(eb.hotkey_control("Ctrl+J")), ["Hyper super combination (Ship)"])
        self.assertEqual(self.book.clashes(eb.hotkey_control("Ctrl+Alt+J")), [], "other modifiers: not the same")
        self.assertEqual(self.book.clashes(("keyboard", "Key_Space", set())), ["UI select (General)", "Jump (On foot)"])

    def test_a_stick_by_its_name_or_its_usb_id(self):
        self.assertEqual(self.book.clashes(("joy", "06A3:075C", "7", set())), ["Hyper super combination (Ship)"],
                         "DeviceMappings: SaitekX52 is 06A3:075C")
        self.assertEqual(self.book.clashes(("joy", "0738:075C", "7", set())), ["Hyper super combination (Ship)"],
                         "and its alternatives")
        self.assertEqual(self.book.clashes(("joy", "06A3:075C", "hat Left", set())), ["Focus left panel (Ship)"],
                         "a hat, by USB id")
        self.assertEqual(self.book.clashes(("joy", "044F:B10A", "7", set())), [], "another stick")


class NameTests(unittest.TestCase):
    def test_groups_and_labels(self):
        self.assertEqual(eb.group_of("UI_Select"), "general")
        self.assertEqual(eb.group_of("GalaxyMapOpen"), "ship")
        self.assertEqual(eb.group_of("CamZoomIn"), "general")
        self.assertEqual(eb.group_of("AutoBreakBuggyButton"), "srv")
        self.assertEqual(eb.group_of("HumanoidJumpButton"), "onfoot")
        self.assertEqual(eb.action_label("ToggleCargoScoop_Buggy"), "Toggle cargo scoop")
        self.assertEqual(eb.action_label("HumanoidJumpButton"), "Jump")
        self.assertEqual(eb.action_label("UI_Select"), "UI select")

    def test_hotkeys_as_elite_writes_them(self):
        self.assertEqual(eb.hotkey_control("Ctrl+Alt+Shift+F8"), ("keyboard", "Key_F8", {"ctrl", "alt", "shift"}))
        self.assertEqual(eb.hotkey_control("Alt+Left")[1], "Key_LeftArrow")
        self.assertIsNone(eb.hotkey_control("MediaPlayPause"))
        self.assertIsNone(eb.hotkey_control(""))

    def test_bad_bindings_file(self):
        with self.assertRaises(ValueError):
            eb.parse_binds("<Root><Broken></Root>")


class SpecTests(unittest.TestCase):
    def test_specs(self):
        self.assertEqual(ci.split("pad:A"), ("", "pad:A"))
        self.assertEqual(ci.split("pad:LB+pad:A"), ("pad:LB", "pad:A"))
        for bad in ("pad:Q", "joy:06A3:075C:40", "pad:A+pad:A", "pad:A+pad:B+pad:X", "", None):
            self.assertFalse(ci.valid(bad), bad)
        names = {"06A3:075C": "Saitek X52"}
        self.assertEqual(ci.describe("pad:LB+pad:A"), "Pad: hold LB, press A")
        self.assertEqual(ci.describe("joy:06A3:075C:7", names), "Saitek X52: button 7")
        self.assertEqual(ci.describe("hat:06A3:075C:Up", names), "Saitek X52: hat up")
        self.assertEqual(ci.describe("joy:06A3:075C:7"), "Controller 06A3:075C: button 7", "not plugged in")
        self.assertEqual(ci.elite_control("pad:LB+pad:A"), ("pad", "A", {"LB"}))
        self.assertEqual(ci.elite_control("hat:06A3:075C:Left"), ("joy", "06A3:075C", "hat Left", set()))
        self.assertIsNone(ci.elite_control("pad:LB+joy:06A3:075C:7"), "two devices: Elite can't bind that")

    def test_hat_directions(self):
        self.assertEqual(ci.hat_directions(0), {"Up"})
        self.assertEqual(ci.hat_directions(4500), {"Up", "Right"})
        self.assertEqual(ci.hat_directions(65535), set())


class FakePads:
    def __init__(self):
        self.down = {}

    def pressed(self):
        return {slot: set(buttons) for slot, buttons in self.down.items()}


class FakeSticks:
    def __init__(self, devices=()):
        self.list = list(devices)
        self.states = {}
        self.listed = 0

    def devices(self):
        self.listed += 1
        return list(self.list)

    def state(self, index):
        return self.states.get(index, (0, 65535))


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def hub(bindings=None, devices=()):
    pads, sticks, clock, pressed = FakePads(), FakeSticks(devices), Clock(), []
    found = ci.ControllerHub(bindings=lambda: dict(bindings or {}), on_press=lambda action, spec: pressed.append(action),
                             pads=pads, joysticks=sticks, clock=clock)
    return found, pads, sticks, clock, pressed


class HubTests(unittest.TestCase):
    def test_a_press_is_its_shortcut_once(self):
        found, pads, _sticks, _clock, pressed = hub({"survey": "pad:Y"})
        pads.down = {0: {"Y"}}
        found.poll_once()
        found.poll_once()
        self.assertEqual(pressed, ["survey"], "once a press, not while held")
        pads.down = {0: set()}
        found.poll_once()
        pads.down = {0: {"Y"}}
        found.poll_once()
        self.assertEqual(pressed, ["survey", "survey"])

    def test_a_combination_before_its_second_button_alone(self):
        found, pads, _sticks, _clock, pressed = hub({"survey": "pad:A", "watcher_poke": "pad:LB+pad:A"})
        pads.down = {0: {"LB"}}
        found.poll_once()
        pads.down = {0: {"LB", "A"}}
        found.poll_once()
        self.assertEqual(pressed, ["watcher_poke"], "holding LB, A is the combination's")
        pads.down = {0: set()}
        found.poll_once()
        pads.down = {0: {"A"}}
        found.poll_once()
        self.assertEqual(pressed, ["watcher_poke", "survey"])
        self.assertTrue(found.is_down("pad:A"))
        self.assertFalse(found.is_down("pad:LB+pad:A"))

    def test_stick_buttons_and_hats(self):
        found, _pads, sticks, _clock, pressed = hub({"survey": "joy:06A3:075C:7", "navigation": "hat:06A3:075C:Up"},
                                                    devices=[(2, "06A3:075C", "Saitek X52", 32)])
        found.refresh(force=True)
        sticks.states[2] = (1 << 6, 0)
        found.poll_once()
        self.assertEqual(sorted(pressed), ["navigation", "survey"])
        self.assertIn("Saitek X52: button 7", [ci.describe(spec, found.names()) for spec in found.snapshot()])

    def test_controllers_plugged_in_later_are_found(self):
        found, pads, sticks, clock, _pressed = hub()
        found.refresh(force=True)
        self.assertEqual(found.devices, [])
        pads.down = {0: set()}
        sticks.list = [(1, "06A3:075C", "Saitek X52", 32), (0, "045E:02FF", "Controller (Xbox One For Windows)", 16)]
        clock.now += ci.IDLE_REFRESH_S + 1
        found.refresh()
        self.assertEqual([row["name"] for row in found.devices], ["Xbox-style pad 1", "Saitek X52"],
                         "the Xbox pad through XInput, not twice")

    def test_winmm_is_told_to_look_again(self):
        sticks = ci.WinmmJoysticks.__new__(ci.WinmmJoysticks)
        calls = []
        sticks.winmm = type("Winmm", (), {"joyConfigChanged": lambda self, flags: calls.append(flags),
                                          "joyGetNumDevs": lambda self: 0})()
        self.assertEqual(sticks.devices(), [])
        self.assertEqual(calls, [0], "without it winmm keeps the list from when the app started")

    def test_learning_a_button_or_a_combination(self):
        found, pads, _sticks, clock, pressed = hub({"survey": "pad:X"})
        steps = iter([{"X"}, set()])

        def step():
            pads.down = {0: next(steps, set())}
            found.poll_once()
        found._learning = {"until": clock.now + 8, "before": set(), "first": "", "done": mock.Mock(), "result": ""}
        step()
        step()
        self.assertEqual(found._learning["result"], "pad:X", "let go: that button alone")
        self.assertEqual(pressed, [], "no shortcut fires while learning")
        steps = iter([{"LB"}, {"LB", "A"}])
        found._learning = {"until": clock.now + 8, "before": set(), "first": "", "done": mock.Mock(), "result": ""}
        found._held = set()
        step()
        step()
        self.assertEqual(found._learning["result"], "pad:LB+pad:A")
        found._learning = {"until": clock.now + 8, "before": set(), "first": "", "done": mock.Mock(), "result": ""}
        clock.now += 9
        pads.down = {0: set()}
        found.poll_once()
        found._learning["done"].set.assert_called()
        self.assertEqual(found._learning["result"], "", "nothing pressed in time")


class FakeHub:
    def __init__(self):
        self.devices = [{"ident": "pad1", "name": "Xbox-style pad 1", "kind": "pad", "buttons": 16}]
        self.error = ""
        self.started = 0
        self.down = {"pad:LB", "pad:A"}
        self.learned = "pad:LB+pad:A"
        self.watched = 0

    def names(self):
        return {}

    def start(self):
        self.started += 1

    def is_down(self, spec):
        return spec == "pad:Y"

    def snapshot(self):
        return set(self.down)

    def watch(self, seconds):
        self.watched += 1

    def learn(self):
        return self.learned

    def cancel_learning(self):
        pass


class FakeBinds:
    _stamp = ("x",)
    error = ""

    def refresh(self):
        return True

    def summary(self):
        return [{"group": "ship", "label": "Ship", "preset": "ConsoleX360", "built_in": True, "found": True, "path": ""}]

    def clashes(self, control):
        return {"pad": ["Select target (Ship)"], "keyboard": ["Landing gear toggle (Ship)"]}.get(control[0], [])


class Deck(DashboardControllerMixin):
    def __init__(self, config=None):
        self.config = {"controller_hotkeys_enabled": True, "overlay_controller_bindings": {}, **(config or {})}
        self._controller_input = FakeHub()
        self._elite_bindings = FakeBinds()
        self.posted, self.saved, self.handled, self.talked = [], 0, [], []

    def _ui_post(self, callback, *args, key=None, **kwargs):
        callback(*args, **kwargs)

    def _persist_config(self):
        self.saved += 1

    def _schedule_html_dashboard_publish(self, immediate=False):
        pass

    def _handle_overlay_hotkey(self, action):
        self.handled.append(action)

    def _watcher_talk_key(self, held=None):
        self.talked.append(held)


class DeckTests(unittest.TestCase):
    def test_only_valid_bindings_for_real_shortcuts_and_only_when_on(self):
        deck = Deck({"overlay_controller_bindings": {"survey": "pad:Y", "nothing": "pad:A", "navigation": "pad:Q"}})
        self.assertEqual(deck._controller_bindings(), {"survey": "pad:Y"})
        deck.config["controller_hotkeys_enabled"] = False
        self.assertEqual(deck._controller_bindings(), {})

    def test_a_press_does_what_its_hotkey_does(self):
        deck = Deck()
        deck._controller_pressed("survey", "pad:Y")
        self.assertEqual(deck.handled, ["survey"])
        deck._controller_pressed("watcher_talk", "pad:Y")
        self.assertEqual(len(deck.talked), 1)
        self.assertTrue(deck.talked[0](), "held: it listens until the button, not a key, is let go")

    def test_learning_keeps_the_button_unless_another_has_it(self):
        deck = Deck()
        self.assertTrue(deck._handle_controller_command("controller_learn", {"hotkey": "survey"}))
        for thread in __import__("threading").enumerate():
            if thread.name == "controller-learn":
                thread.join(2)
        self.assertEqual(deck.config["overlay_controller_bindings"], {"survey": "pad:LB+pad:A"})
        self.assertEqual(deck._controller_learning["status"], "done")
        self.assertEqual(deck._controller_input.started, 1, "reading starts once a button is bound")
        deck._controller_learned("navigation", "pad:LB+pad:A")
        self.assertEqual(deck._controller_learning["status"], "taken")
        self.assertIn("is already set for Survey Operations", deck._controller_learning["note"])
        deck._controller_learned("navigation", "")
        self.assertEqual(deck._controller_learning["status"], "none")
        self.assertFalse(deck._handle_controller_command("controller_learn", {"hotkey": "nonsense"}))

    def test_clear_and_switch(self):
        deck = Deck({"overlay_controller_bindings": {"survey": "pad:Y"}})
        self.assertTrue(deck._handle_controller_command("controller_clear", {"hotkey": "survey"}))
        self.assertEqual(deck.config["overlay_controller_bindings"], {})
        self.assertFalse(deck._handle_controller_command("controller_clear", {"hotkey": "survey"}))
        self.assertTrue(deck._handle_controller_command("controller_toggle", {"value": False}))
        self.assertFalse(deck.config["controller_hotkeys_enabled"])
        self.assertIsNone(deck._handle_controller_command("save", {}), "not one of its own")

    def test_the_settings_page_and_its_live_readout(self):
        deck = Deck({"overlay_controller_bindings": {"survey": "pad:A"}, "overlay_hotkey_navigation": "Ctrl+Alt+L"})
        page = deck._html_controller_settings()
        self.assertEqual(page["buttons"]["survey"]["label"], "Pad: A")
        self.assertEqual(page["buttons"]["survey"]["clashes"], ["Select target (Ship)"])
        self.assertEqual(page["keys"]["navigation"]["clashes"], ["Landing gear toggle (Ship)"])
        self.assertEqual(page["elite"]["groups"][0]["preset"], "ConsoleX360")
        live = deck._controller_live()
        self.assertEqual(live["devices"][0]["name"], "Xbox-style pad 1")
        self.assertEqual(live["down"], ["Pad: A", "Pad: LB"])
        self.assertEqual(deck._controller_input.watched, 1, "it polls quickly while you look")

    def test_every_shortcut_can_have_a_button(self):
        self.assertTrue(all(row[0] for row in OVERLAY_HOTKEY_SPECS))

    def test_every_shortcut_in_a_group_on_the_hotkeys_page(self):
        from voidcompass.dashboard.html_dashboard import _hotkey_group
        from voidcompass.dashboard.html_dashboard import HOTKEY_GROUP_OF
        groups = {action: _hotkey_group(action, attr) for action, _key, _label, attr in OVERLAY_HOTKEY_SPECS}
        self.assertEqual(set(groups.values()), {"overlays", "controls", "navigation", "rhino", "field", "watcher", "music"})
        self.assertEqual((groups["watcher_talk"], groups["toggle_all"], groups["navigation"]),
                         ("watcher", "controls", "overlays"))
        # 5.7.6: no strays. Every shortcut that isn't an overlay's, the companion's
        # or the music's is placed by name; OVERLAY CONTROLS is only the overlay-wide ones.
        for action, _key, _label, attr in OVERLAY_HOTKEY_SPECS:
            if attr is None and not action.startswith(("watcher_", "music_")):
                self.assertIn(action, HOTKEY_GROUP_OF, f"{action} has no hotkey group")
        self.assertEqual(sorted(action for action, group in groups.items() if group == "controls"), ["layout_studio", "toggle_all"])
        self.assertEqual({groups[name] for name in ("rig_1", "rig_clear", "rhino_map_range", "rhino_survey_centre")}, {"rhino"})
        script = (Path(__file__).resolve().parents[1] / "web/dashboard/app.js").read_text(encoding="utf-8")
        for group in set(groups.values()):
            self.assertIn(f'["{group}", "', script, f"app.js has no HOTKEY_GROUPS entry for {group}")


class TalkTests(unittest.TestCase):
    def test_held_on_a_controller_button(self):
        from voidcompass.dashboard.dashboard_watcher_listen_mixin import DashboardWatcherListenMixin

        class Listen(DashboardWatcherListenMixin):
            def __init__(self):
                self.config = {"watcher_listen_mode": "hold"}
                self.begun = []

            def _watcher_listener(self):
                return mock.Mock(active=lambda: False)

            def _watcher_listen_blocked(self, test=False):
                return ""

            def _watcher_listen_begin(self, key=None, test=False, held=None):
                self.begun.append((key, held))

        listen = Listen()
        down = lambda: True  # noqa: E731
        listen._watcher_talk_key(held=down)
        self.assertEqual(listen.begun, [(None, down)])


if __name__ == "__main__":
    unittest.main()
