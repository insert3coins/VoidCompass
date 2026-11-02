"""Elite Dangerous's own key bindings (5.7.3), for any commander, so Void
Compass can say when a hotkey or controller button you pick already does
something in the game.

Which bindings are in use: Odyssey writes the four presets it uses, one per
line, to Options\\Bindings\\StartPreset.4.start: General, Ship, SRV and On
foot (Horizons writes StartPreset.start, one line for everything). A preset
you've changed is a file in that folder ("Custom.4.2.binds"); a built-in one
("ConsoleX360", "KeyboardMouseOnly", "SaitekX52"...) is never copied there:
it lives in the game's install, Products\\<product>\\ControlSchemes, found
through Steam's library list, Epic's manifests, the Frontier launcher's
folder or the running game. Elite names some devices by their USB id
("068E00F4") and others by a name ("SaitekX52", "GamePad");
ControlSchemes\\DeviceMappings.xml says which hardware each name is.

Nothing here writes to the game's files.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

GROUPS = ("general", "ship", "srv", "onfoot")
GROUP_LABELS = {"general": "General", "ship": "Ship", "srv": "SRV", "onfoot": "On foot"}
PRODUCTS = ("elite-dangerous-odyssey-64", "FORC-FDEV-D-1010")
NO_DEVICE = "{nodevice}"
REFRESH_S = 10.0
# Elite's own names for an Xbox-style pad (XInput); both spellings are in use.
PAD_DEVICES = {"gamepad", "xb360 pad"}
PAD_KEYS = {
    "A": ("GamePad_FaceDown", "Pad_A"), "B": ("GamePad_FaceRight", "Pad_B"),
    "X": ("GamePad_FaceLeft", "Pad_X"), "Y": ("GamePad_FaceUp", "Pad_Y"),
    "LB": ("GamePad_LBumper", "Pad_LBumper"), "RB": ("GamePad_RBumper", "Pad_RBumper"),
    "Back": ("GamePad_Back", "Pad_Back"), "Start": ("GamePad_Start", "Pad_Start"),
    "LS": ("GamePad_LThumb", "Pad_LThumb"), "RS": ("GamePad_RThumb", "Pad_RThumb"),
    "Up": ("GamePad_DPadUp", "Pad_DPadUp"), "Down": ("GamePad_DPadDown", "Pad_DPadDown"),
    "Left": ("GamePad_DPadLeft", "Pad_DPadLeft"), "Right": ("GamePad_DPadRight", "Pad_DPadRight"),
    "LT": ("Pos_GamePad_LTrigger", "GamePad_LTrigger", "Pad_LTrigger"),
    "RT": ("Pos_GamePad_RTrigger", "GamePad_RTrigger", "Pad_RTrigger"),
}
_PAD_BY_KEY = {key.casefold(): name for name, keys in PAD_KEYS.items() for key in keys}
# Void Compass's key names (global_hotkeys) as Elite writes them.
_KEY_NAMES = {"Left": "Key_LeftArrow", "Right": "Key_RightArrow", "Up": "Key_UpArrow", "Down": "Key_DownArrow",
              "PageUp": "Key_PageUp", "PageDown": "Key_PageDown", "Escape": "Key_Escape"}
_MODIFIER_KIND = {"key_leftcontrol": "ctrl", "key_rightcontrol": "ctrl", "key_leftalt": "alt", "key_rightalt": "alt",
                  "key_leftshift": "shift", "key_rightshift": "shift", "key_leftwin": "win", "key_rightwin": "win"}
# The General preset's actions: the panels and menus, the cameras, the maps.
_GENERAL = re.compile(r"^(UI_|Cycle(Next|Previous)(Panel|Page)|Cam(Pitch|Yaw|Translate|Zoom)|FreeCam|MoveFreeCam|"
                      r"ToggleFreeCam|FStop|Vanity|FixCamera|ToggleRotationLock|ToggleAdvanceMode|"
                      r"GalaxyMap(?!Open)|SystemMap(?!Open)|HeadLook|Pause$|FriendsMenu|OpenCodex|PhotoCamera|"
                      r"HMDReset|MouseGUI|Store|CommanderCreator|QuickCommsPanel)")


def group_of(action):
    """Which of Elite's four control groups an action belongs to."""
    name = str(action or "")
    if "Humanoid" in name:
        return "onfoot"
    if "Buggy" in name:
        return "srv"
    if _GENERAL.match(name):
        return "general"
    return "ship"


def action_label(action):
    """"LandingGearToggle" -> "Landing gear toggle"; "ToggleCargoScoop_Buggy" -> "Toggle cargo scoop"."""
    name = str(action or "")
    for suffix in ("_Buggy", "_Humanoid", "_Fighter", "_MultiCrew", "_Landing"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    for prefix in ("Humanoid", "Buggy"):
        if name.startswith(prefix) and len(name) > len(prefix):
            name = name[len(prefix):]
    name = re.sub(r"_?Button$", "", name).replace("_", " ")
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name).split()
    if not words:
        return str(action or "")
    text = " ".join(word if word.isupper() and len(word) <= 3 else word.lower() for word in words)
    return text[:1].upper() + text[1:]


class Slot:
    __slots__ = ("device", "key", "modifiers")

    def __init__(self, device, key, modifiers=()):
        self.device = str(device or "")
        self.key = str(key or "")
        self.modifiers = tuple((str(d or ""), str(k or "")) for d, k in modifiers)

    def empty(self):
        return self.device.casefold() in ("", NO_DEVICE) or not self.key


def parse_binds(text):
    """A .binds file -> {action: [Slot, ...]}: its Primary and Secondary
    buttons, and an axis Binding as a slot too. Bad XML raises ValueError."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"not a valid bindings file ({error})") from None
    actions = {}
    for element in root:
        slots = []
        for tag in ("Primary", "Secondary", "Binding"):
            node = element.find(tag)
            if node is None:
                continue
            slot = Slot(node.get("Device"), node.get("Key"),
                        [(m.get("Device"), m.get("Key")) for m in node.findall("Modifier")])
            if not slot.empty():
                slots.append(slot)
        if slots:
            actions.setdefault(element.tag, []).extend(slots)
    return actions


def bindings_folder(environ=None):
    base = (os.environ if environ is None else environ).get("LOCALAPPDATA")
    return Path(base) / "Frontier Developments" / "Elite Dangerous" / "Options" / "Bindings" if base else None


def start_presets(folder):
    """{group: preset name} from StartPreset.4.start (Odyssey: General, Ship,
    SRV, On foot) or StartPreset.start (one line, or four), and whether it was Odyssey's."""
    if folder is None:
        return {}, False
    for name, odyssey in (("StartPreset.4.start", True), ("StartPreset.start", False)):
        try:
            lines = [line.strip() for line in (Path(folder) / name).read_text(encoding="utf-8-sig", errors="ignore")
                     .splitlines() if line.strip()]
        except OSError:
            continue
        if not lines:
            continue
        if len(lines) < len(GROUPS):
            lines += [lines[-1]] * (len(GROUPS) - len(lines))
        return dict(zip(GROUPS, lines)), odyssey
    return {}, False


def _version(path):
    match = re.search(r"\.(\d+)\.(\d+)\.binds$", path.name)
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def resolve_preset(name, folder, schemes):
    """A preset's file: yours in the Bindings folder (the newest version of
    it), else the built-in one in the game's ControlSchemes. (path, built_in)
    or (None, False)."""
    if folder is not None and Path(folder).is_dir():
        yours = [path for path in Path(folder).glob(f"{name}*.binds")
                 if path.name == f"{name}.binds" or re.fullmatch(rf"{re.escape(name)}\.\d+\.\d+\.binds", path.name)]
        if yours:
            return max(yours, key=lambda path: (_version(path), path.stat().st_mtime)), False
    for directory in schemes or ():
        path = Path(directory) / f"{name}.binds"
        if path.is_file():
            return path, True
    return None, False


def device_mappings(schemes):
    """ControlSchemes\\DeviceMappings.xml: Elite's device name -> {"VVVV:PPPP", ...}."""
    for directory in schemes or ():
        try:
            root = ET.parse(Path(directory) / "DeviceMappings.xml").getroot()
        except (OSError, ET.ParseError):
            continue
        found = {}
        for device in root:
            ids = set()
            for node in [device, *device.findall("Alternative")]:
                vid, pid = (node.findtext("VID") or "").strip(), (node.findtext("PID") or "").strip()
                if vid and pid:
                    ids.add(f"{vid.upper().zfill(4)}:{pid.upper().zfill(4)}")
            if ids:
                found[device.tag.casefold()] = ids
        return found
    return {}


# -- where the game is -------------------------------------------------------------
def _steam_libraries(environ):
    roots = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            roots.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
    except (ImportError, OSError):
        pass
    program_files = environ.get("ProgramFiles(x86)") or environ.get("ProgramFiles")
    if program_files:
        roots.append(Path(program_files) / "Steam")
    libraries = []
    for root in roots:
        libraries.append(root)
        try:
            text = (root / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        libraries += [Path(path.replace("\\\\", "\\")) for path in re.findall(r'"path"\s+"([^"]+)"', text)]
    return libraries


def _epic_installs(environ):
    folder = Path(environ.get("ProgramData") or r"C:\ProgramData") / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    found = []
    try:
        manifests = list(folder.glob("*.item"))
    except OSError:
        return found
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, ValueError):
            continue
        if "elite" in str(data.get("DisplayName") or "").casefold() and data.get("InstallLocation"):
            found.append(Path(data["InstallLocation"]))
    return found


def running_game_folder():
    """The folder of a running EliteDangerous64.exe, or None (Windows only)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Entry(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_wchar * 260)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                      ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)
        if not snapshot or snapshot == wintypes.HANDLE(-1).value:
            return None
        try:
            entry = Entry()
            entry.dwSize = ctypes.sizeof(Entry)
            ok = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.casefold() == "elitedangerous64.exe":
                    process = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)
                    if process:
                        try:
                            size = wintypes.DWORD(1024)
                            buffer = ctypes.create_unicode_buffer(size.value)
                            if kernel.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                                return Path(buffer.value).parent
                        finally:
                            kernel.CloseHandle(process)
                ok = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
    except Exception:
        logging.debug("Couldn't look for the running game", exc_info=True)
    return None


def control_scheme_folders(odyssey=True, environ=None, chosen="", game_folder=None):
    """Every ControlSchemes folder found, the game's product first (Odyssey's,
    or Horizons 3.8's), from a folder you chose, the running game, Steam,
    Epic and the Frontier launcher."""
    environ = os.environ if environ is None else environ
    products = PRODUCTS if odyssey else PRODUCTS[::-1]
    roots = []
    if chosen:
        roots.append(Path(chosen))
    if game_folder is not None:
        roots.append(Path(game_folder))
    roots += [library / "steamapps" / "common" / "Elite Dangerous" for library in _steam_libraries(environ)]
    roots += _epic_installs(environ)
    program_files = environ.get("ProgramFiles(x86)") or environ.get("ProgramFiles")
    if program_files:
        roots.append(Path(program_files) / "Frontier")
    found = []
    for root in roots:
        # A chosen or running-game folder can be the install, Products, or the product itself.
        for product in products:
            for candidate in (root / "Products" / product / "ControlSchemes", root / product / "ControlSchemes",
                              root / "ControlSchemes"):
                if candidate.is_dir() and candidate not in found and (product in str(candidate) or candidate.parent == root):
                    found.append(candidate)
    return found


# -- the bindings ------------------------------------------------------------------
class EliteBinds:
    """The bindings in use, re-read when their files change (looked at no
    more often than every ``REFRESH_S``)."""

    def __init__(self, folder=None, chosen=lambda: "", environ=None, clock=time.monotonic,
                 game_folder=running_game_folder):
        self.folder = Path(folder) if folder else bindings_folder(environ)
        self.chosen = chosen
        self.environ = environ
        self.clock = clock
        self.game_folder = game_folder
        self.groups = {}
        self.actions = {}            # group -> {action: [Slot]}
        self.mappings = {}
        self.schemes = []
        self.odyssey = False
        self.error = ""
        self._stamp = None
        self._checked = -REFRESH_S

    def refresh(self, force=False):
        now = self.clock()
        if not force and now - self._checked < REFRESH_S and self._stamp is not None:
            return bool(self.actions)
        self._checked = now
        presets, self.odyssey = start_presets(self.folder)
        if not presets:
            self.groups, self.actions, self._stamp = {}, {}, ()
            self.error = "Elite's controls folder or its start presets weren't found"
            return False
        chosen = ""
        try:
            chosen = str(self.chosen() or "")
        except Exception:
            pass
        game = None
        schemes = control_scheme_folders(self.odyssey, self.environ, chosen)
        needs_game = any(resolve_preset(name, self.folder, schemes)[0] is None for name in set(presets.values()))
        if needs_game and callable(self.game_folder):
            game = self.game_folder()
            if game is not None:
                schemes = control_scheme_folders(self.odyssey, self.environ, chosen, game)
        files = {group: resolve_preset(name, self.folder, schemes) for group, name in presets.items()}
        stamp = tuple(sorted((group, str(path), path.stat().st_mtime_ns if path else 0)
                             for group, (path, _built_in) in files.items()))
        if stamp == self._stamp:
            return bool(self.actions)
        parsed, actions, missing = {}, {}, []
        for group, (path, _built_in) in files.items():
            if path is None:
                missing.append(presets[group])
                continue
            if path not in parsed:
                try:
                    parsed[path] = parse_binds(path.read_text(encoding="utf-8-sig", errors="ignore"))
                except (OSError, ValueError) as exc:
                    logging.warning("Couldn't read Elite's bindings %s: %s", path, exc)
                    parsed[path] = {}
            actions[group] = {name: slots for name, slots in parsed[path].items() if group_of(name) == group}
        self.schemes = schemes
        self.mappings = device_mappings(schemes)
        self.groups = {group: {"preset": presets[group], "path": str(path) if path else "", "built_in": built_in,
                               "found": path is not None} for group, (path, built_in) in files.items()}
        self.actions = actions
        self._stamp = stamp
        self.error = ("Built-in presets not found (the game's install folder): " + ", ".join(sorted(set(missing)))
                      if missing else "")
        return bool(actions)

    def summary(self):
        """[{group, label, preset, built_in, found, path}] for Settings."""
        self.refresh()
        return [{"group": group, "label": GROUP_LABELS[group], **self.groups[group]} for group in GROUPS
                if group in self.groups]

    # -- what a control does in Elite ---------------------------------------------------
    def _device_ids(self, device):
        """The USB ids an Elite device name means ("068E00F4", or a DeviceMappings name)."""
        name = device.strip()
        if re.fullmatch(r"[0-9A-Fa-f]{8}", name):
            return {f"{name[:4].upper()}:{name[4:].upper()}"}
        return self.mappings.get(name.casefold(), set())

    def _pad_name(self, device, key):
        if device.casefold() in PAD_DEVICES or self._device_ids(device) & self.mappings.get("gamepad", set()):
            return _PAD_BY_KEY.get(key.casefold())
        return None

    def _joy_name(self, device, key, ident):
        if ident not in self._device_ids(device):
            return None
        match = re.fullmatch(r"Joy_(\d+)|Joy_POV1(Up|Down|Left|Right)", key, re.I)
        if not match:
            return None
        return match.group(1) if match.group(1) else f"hat {match.group(2).title()}"

    def clashes(self, control):
        """What a control already does in Elite: ["Landing gear toggle (Ship)", ...].

        ``control`` is ("keyboard", "Key_F8", {"ctrl", "alt"}), ("pad", "A",
        {"LB"}) (an Xbox-style pad's buttons: A B X Y LB RB Back Start LS RS
        Up Down Left Right LT RT) or ("joy", "06A3:075C", "7" | "hat Up", set())."""
        if not self.refresh():
            return []
        kind, key = control[0], control[1]
        found = []
        for group in GROUPS:
            for action, slots in (self.actions.get(group) or {}).items():
                if any(self._slot_matches(slot, control) for slot in slots):
                    found.append(f"{action_label(action)} ({GROUP_LABELS[group]})")
        return sorted(set(found), key=found.index)

    def _slot_matches(self, slot, control):
        kind = control[0]
        if kind == "keyboard":
            _kind, key, mods = control
            if slot.device.casefold() != "keyboard" or slot.key.casefold() != key.casefold():
                return False
            if any(d.casefold() != "keyboard" for d, _k in slot.modifiers):
                return False
            return {_MODIFIER_KIND.get(k.casefold(), k.casefold()) for _d, k in slot.modifiers} == set(mods)
        if kind == "pad":
            _kind, button, mods = control
            if self._pad_name(slot.device, slot.key) != button:
                return False
            return {self._pad_name(d, k) for d, k in slot.modifiers} == set(mods)
        if kind == "joy":
            _kind, ident, button, mods = control
            if self._joy_name(slot.device, slot.key, ident) != button:
                return False
            return {self._joy_name(d, k, ident) for d, k in slot.modifiers} == set(mods)
        return False


def hotkey_control(canonical):
    """A Void Compass hotkey ("Ctrl+Alt+Shift+F8") as a keyboard control for clashes, or None."""
    parts = [part for part in str(canonical or "").split("+") if part]
    if not parts:
        return None
    key = parts[-1]
    if key.startswith("Media"):
        return None
    name = _KEY_NAMES.get(key, f"Key_{key}")
    return "keyboard", name, {part.casefold() for part in parts[:-1]}
