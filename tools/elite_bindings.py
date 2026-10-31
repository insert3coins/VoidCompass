"""Elite's own bindings: the keys that open the pause menu. For
tools/pause_probe.py only; not part of the app (parked, 2026-10-30).

The game writes nothing when its pause menu opens, so the only way to tell is
the keys pressed. Esc on the keyboard and Start on a controller open it
whatever the bindings say (no preset binds either); the Pause action is a
second key a commander can bind (P in every one of Frontier's presets).

StartPreset.4.start names the preset in use for each part of the controls
(general, ship, SRV, on foot), and they can differ. A commander's own presets
are in Options/Bindings (Custom.4.2.binds: the newest version wins);
Frontier's (KeyboardMouseOnly, ConsoleX360...) are only in the game's
ControlSchemes folder, wherever the game is installed: Steam, Epic or
Frontier's own standalone client, at any path. If it can't be found, P is
assumed, as 23 of Frontier's 29 presets have it (the rest: nothing, or a
joystick button).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ElementTree

BINDINGS = (Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            / "Frontier Developments" / "Elite Dangerous" / "Options" / "Bindings")
# Odyssey's folder first, then Horizons'.
PRODUCTS = ("elite-dangerous-odyssey-64", "FORC-FDEV-D-1010")
ALWAYS = (
    {"device": "Keyboard", "key": "Key_Escape", "modifiers": []},
    {"device": "GamePad", "key": "GamePad_Start", "modifiers": []},
)
FRONTIER_PAUSE = {"device": "Keyboard", "key": "Key_P", "modifiers": []}
GAME_EXE = "elitedangerous64.exe"

# Elite's keyboard names to Windows virtual-key codes.
_NAMED = {
    "Escape": 0x1B, "Minus": 0xBD, "Equals": 0xBB, "Backspace": 0x08, "Tab": 0x09,
    "LeftBracket": 0xDB, "RightBracket": 0xDD, "Enter": 0x0D, "Numpad_Enter": 0x0D,
    "LeftControl": 0xA2, "RightControl": 0xA3, "LeftShift": 0xA0, "RightShift": 0xA1,
    "LeftAlt": 0xA4, "RightAlt": 0xA5, "LeftWin": 0x5B, "RightWin": 0x5C, "Apps": 0x5D,
    "SemiColon": 0xBA, "Apostrophe": 0xDE, "Grave": 0xC0, "BackSlash": 0xDC, "Comma": 0xBC,
    "Period": 0xBE, "Slash": 0xBF, "OEM_102": 0xE2, "Space": 0x20, "CapsLock": 0x14,
    "NumLock": 0x90, "ScrollLock": 0x91, "SYSRQ": 0x2C, "Pause": 0x13,
    "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22, "Insert": 0x2D, "Delete": 0x2E,
    "UpArrow": 0x26, "DownArrow": 0x28, "LeftArrow": 0x25, "RightArrow": 0x27,
    "Numpad_Multiply": 0x6A, "Numpad_Add": 0x6B, "Numpad_Subtract": 0x6D, "Numpad_Decimal": 0x6E,
    "Numpad_Divide": 0x6F, "Numpad_Equals": 0x92,
    "Mute": 0xAD, "VolumeDown": 0xAE, "VolumeUp": 0xAF, "NextTrack": 0xB0, "PrevTrack": 0xB1,
    "MediaStop": 0xB2, "PlayPause": 0xB3,
}


def virtual_key(name):
    """The Windows virtual-key code for one of Elite's keyboard names, or None."""
    name = str(name or "")
    if not name.startswith("Key_"):
        return None
    name = name[4:]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name.startswith("Numpad_") and name[7:].isdigit():
        return 0x60 + int(name[7:])
    if name[:1] == "F" and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x6F + int(name[1:])
    return _NAMED.get(name)


def active_presets(folder=BINDINGS):
    """The presets in use, in StartPreset's order, each once."""
    folder = Path(folder)
    starts = sorted(folder.glob("StartPreset*.start"), key=lambda path: _version(path.name, "StartPreset", ".start"))
    if not starts:
        return []
    try:
        lines = starts[-1].read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    names = []
    for line in lines:
        name = line.strip()
        if name and name not in names:
            names.append(name)
    return names


def _version(filename, name, suffix):
    match = re.fullmatch(re.escape(name) + r"(?:\.(\d+)\.(\d+)|\.(\d+))?" + re.escape(suffix), filename)
    if not match:
        return (-1, -1)
    if match.group(1):
        return (int(match.group(1)), int(match.group(2)))
    return (int(match.group(3)), 0) if match.group(3) else (0, 0)


def preset_file(name, folder=BINDINGS, schemes=()):
    """A preset's .binds file: the commander's own (newest version), else
    Frontier's in the game folder. None when it can't be found."""
    own = [path for path in Path(folder).glob(f"{name}*.binds") if _version(path.name, name, ".binds") >= (0, 0)]
    if own:
        return max(own, key=lambda path: _version(path.name, name, ".binds"))
    for scheme in schemes:
        path = Path(scheme) / f"{name}.binds"
        if path.is_file():
            return path
    return None


def game_schemes():
    """The game's ControlSchemes folders, wherever it's installed: beside the
    running game first, then installs Windows knows of (Frontier's standalone
    installer registers one), Steam's libraries, Epic's manifests and
    Frontier's default folders."""
    places = list(running_games()) + list(installed_games())
    program_files = Path(os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)")
    places += [library / "steamapps" / "common" / "Elite Dangerous" for library in steam_libraries(program_files / "Steam")]
    manifests = Path(os.environ.get("ProgramData") or r"C:\ProgramData") / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    for item in manifests.glob("*.item") if manifests.is_dir() else ():
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "elite dangerous" in str(data.get("DisplayName", "")).casefold() and data.get("InstallLocation"):
            places.append(Path(data["InstallLocation"]))
    places += [program_files / "Frontier", program_files / "Frontier" / "EDLaunch"]
    found = []
    for place in places:
        for scheme in schemes_near(place):
            if scheme not in found:
                found.append(scheme)
    return found


def schemes_near(place):
    """ControlSchemes folders at an install, given its top folder, its
    Products folder, a product's own folder or a file inside one."""
    place = Path(place)
    found = []
    for base in (place, *list(place.parents)[:3]):
        for scheme in (base / "ControlSchemes", *(base / "Products" / product / "ControlSchemes" for product in PRODUCTS),
                       *(base / product / "ControlSchemes" for product in PRODUCTS)):
            if scheme.is_dir() and scheme not in found:
                found.append(scheme)
        if found:
            break
    return found


def running_games():
    """The folder of each running EliteDangerous64.exe."""
    if os.name != "nt":
        return []
    import ctypes
    import ctypes.wintypes as wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.OpenProcess.restype = ctypes.c_void_p
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    folders = []
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return folders
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        more = kernel32.Process32FirstW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() == GAME_EXE:
                handle = kernel32.OpenProcess(0x1000, False, entry.th32ProcessID)
                if handle:
                    buffer = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(len(buffer))
                    if kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buffer, ctypes.byref(size)):
                        folders.append(Path(buffer.value).parent)
                    kernel32.CloseHandle(ctypes.c_void_p(handle))
            more = kernel32.Process32NextW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snapshot))
    return folders


def installed_games():
    """Install folders from Windows' list of installed programs."""
    if os.name != "nt":
        return []
    import winreg

    folders = []
    for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                      (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:
            root = winreg.OpenKey(hive, key)
        except OSError:
            continue
        with root:
            for index in range(winreg.QueryInfoKey(root)[0]):
                try:
                    with winreg.OpenKey(root, winreg.EnumKey(root, index)) as program:
                        name = str(winreg.QueryValueEx(program, "DisplayName")[0])
                        location = str(winreg.QueryValueEx(program, "InstallLocation")[0])
                except OSError:
                    continue
                if "elite dangerous" in name.casefold() and location:
                    folders.append(Path(location))
    return folders


def steam_libraries(steam):
    """Every Steam library folder (libraryfolders.vdf), the main one first."""
    libraries = [Path(steam)]
    try:
        text = (Path(steam) / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return libraries
    for path in re.findall(r'"path"\s+"([^"]+)"', text):
        library = Path(path.replace("\\\\", "\\"))
        if library not in libraries:
            libraries.append(library)
    return libraries


def read_bindings(path, action):
    """One action's bindings in a .binds file: device, key and modifiers each."""
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return []
    element = root.find(action)
    found = []
    for slot in (element.findall("Primary") + element.findall("Secondary")) if element is not None else ():
        device, key = slot.get("Device") or "", slot.get("Key") or ""
        if device and device != "{NoDevice}" and key:
            found.append({"device": device, "key": key,
                          "modifiers": [modifier.get("Key") for modifier in slot.findall("Modifier") if modifier.get("Key")]})
    return found


def action_bindings(action, folder=BINDINGS, schemes=None, missing=()):
    """An action's bindings across every preset in use (``missing`` for a
    preset that can't be found), and which presets were read."""
    schemes = game_schemes() if schemes is None else schemes
    found, presets = [], []
    for name in active_presets(folder):
        path = preset_file(name, folder, schemes)
        presets.append({"name": name, "file": str(path) if path else None})
        for binding in read_bindings(path, action) if path else [dict(binding) for binding in missing]:
            if binding not in found:
                found.append(binding)
    return found, presets


def pause_keys(folder=BINDINGS, schemes=None):
    """What opens the pause menu for this commander: Esc and Start always,
    and whatever each preset in use binds to Pause. Also which presets were
    read and which couldn't be found."""
    found, presets = action_bindings("Pause", folder, schemes, missing=[FRONTIER_PAUSE])
    keys = [dict(binding) for binding in ALWAYS]
    keys += [binding for binding in found if binding not in keys]
    return {"keys": keys, "presets": presets}
