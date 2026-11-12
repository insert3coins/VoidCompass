"""Pressing Elite's own keys (5.7.3), for the Watcher's ship commands.

Elite reads the keyboard by scancode, so a press goes through SendInput as a
scancode (a virtual key alone is ignored by the game), using the key your
bindings give the action (elite_binds). Keys only ever go to Elite: before
each one goes down, the window in front must be the game's, and a press
stops the moment it isn't. A pad or stick button can't be pressed this way:
an action bound only to one needs a keyboard key in Elite's controls too.
"""
from __future__ import annotations

import ctypes
import logging
import sys
import time

GAME_EXE = "elitedangerous64.exe"
HOLD_S = 0.08         # Elite reads input once a frame: a key held this long is seen at 15 fps
MODIFIER_LEAD_S = 0.03
FOCUS_WAIT_S = 0.6
SETTLE_S = 0.25       # the game, just brought forward, before it reads the keyboard

# Elite's key names (after "Key_", any case) -> (scancode, extended).
SCANCODES = {}


def _add(names, code, extended=False):
    for name in names.split():
        SCANCODES[name.casefold()] = (code, extended)


for _offset, _letter in enumerate("qwertyuiop"):
    _add(_letter, 0x10 + _offset)
for _offset, _letter in enumerate("asdfghjkl"):
    _add(_letter, 0x1E + _offset)
for _offset, _letter in enumerate("zxcvbnm"):
    _add(_letter, 0x2C + _offset)
for _offset, _digit in enumerate("1234567890"):
    _add(_digit, 0x02 + _offset)
for _number in range(1, 11):
    _add(f"F{_number}", 0x3A + _number)
_add("F11", 0x57)
_add("F12", 0x58)
for _offset, _number in enumerate(range(13, 24)):
    _add(f"F{_number}", 0x64 + _offset)
_add("F24", 0x76)
_add("Escape", 0x01)
_add("Minus", 0x0C)
_add("Equals", 0x0D)
_add("Backspace", 0x0E)
_add("Tab", 0x0F)
_add("LeftBracket", 0x1A)
_add("RightBracket", 0x1B)
_add("Enter", 0x1C)
_add("LeftControl", 0x1D)
_add("SemiColon", 0x27)
_add("Apostrophe", 0x28)
_add("Grave", 0x29)
_add("LeftShift", 0x2A)
_add("BackSlash", 0x2B)
_add("Comma", 0x33)
_add("Period", 0x34)
_add("Slash", 0x35)
_add("RightShift", 0x36)
_add("LeftAlt", 0x38)
_add("Space", 0x39)
_add("CapsLock", 0x3A)
_add("NumLock", 0x45, True)
_add("ScrollLock", 0x46)
for _number, _code in enumerate((0x52, 0x4F, 0x50, 0x51, 0x4B, 0x4C, 0x4D, 0x47, 0x48, 0x49)):
    _add(f"Numpad_{_number}", _code)
_add("Numpad_Multiply", 0x37)
_add("Numpad_Subtract", 0x4A)
_add("Numpad_Add", 0x4E)
_add("Numpad_Decimal", 0x53)
_add("Numpad_Enter", 0x1C, True)
_add("Numpad_Divide", 0x35, True)
_add("RightControl", 0x1D, True)
_add("RightAlt", 0x38, True)
_add("Home", 0x47, True)
_add("UpArrow", 0x48, True)
_add("PageUp", 0x49, True)
_add("LeftArrow", 0x4B, True)
_add("RightArrow", 0x4D, True)
_add("End", 0x4F, True)
_add("DownArrow", 0x50, True)
_add("PageDown", 0x51, True)
_add("Insert", 0x52, True)
_add("Delete", 0x53, True)
_add("LeftWin", 0x5B, True)
_add("RightWin", 0x5C, True)
_add("Apps", 0x5D, True)

# How a key is shown on the page.
_LABELS = {"leftcontrol": "Left Ctrl", "rightcontrol": "Right Ctrl", "leftshift": "Left Shift",
           "rightshift": "Right Shift", "leftalt": "Left Alt", "rightalt": "Right Alt", "uparrow": "Up",
           "downarrow": "Down", "leftarrow": "Left", "rightarrow": "Right", "pageup": "Page Up",
           "pagedown": "Page Down", "semicolon": ";", "apostrophe": "'", "grave": "`", "backslash": "\\",
           "slash": "/", "comma": ",", "period": ".", "minus": "-", "equals": "=", "leftbracket": "[",
           "rightbracket": "]", "capslock": "Caps Lock", "numlock": "Num Lock", "scrolllock": "Scroll Lock"}


def key_name(key):
    """"Key_LeftShift" -> "leftshift"; "Key_Numpad_0" -> "numpad_0"."""
    name = str(key or "")
    return (name[4:] if name[:4].casefold() == "key_" else name).casefold()


def scancode(key):
    """(scancode, extended) for one of Elite's key names, or None."""
    return SCANCODES.get(key_name(key))


def label(key, modifiers=()):
    """"Key_Home" with Key_LeftShift held -> "Left Shift+Home"."""
    def one(name):
        bare = key_name(name)
        if bare in _LABELS:
            return _LABELS[bare]
        if bare.startswith("numpad_"):
            return "Numpad " + bare[7:].replace("_", " ").title()
        return bare.upper() if len(bare) <= 3 else bare.title()
    return "+".join([one(name) for name in modifiers] + [one(key)])


def keyboard_slot(slots):
    """The first of an action's bindings on the keyboard alone, as
    (key, (modifier, ...)), or None (a pad, a stick, nothing)."""
    for slot in slots or ():
        if str(slot.device).casefold() != "keyboard":
            continue
        if all(str(device).casefold() == "keyboard" for device, _key in slot.modifiers):
            return slot.key, tuple(key for _device, key in slot.modifiers)
    return None


def pressable(key, modifiers=()):
    """The keys of a binding this can't press (an unknown name), or ()."""
    return tuple(name for name in (*modifiers, key) if scancode(name) is None)


def keyboard_shortcut(value):
    """A recorded game key, including bare keys, as (key, modifiers)."""
    text = str(value or "").strip()
    if not text:
        return None
    parts = [part.strip() for part in text.split("+")]
    modifier_names = {"ctrl": "LeftControl", "control": "LeftControl", "alt": "LeftAlt",
                      "shift": "LeftShift", "win": "LeftWin"}
    aliases = {"up": "UpArrow", "down": "DownArrow", "left": "LeftArrow", "right": "RightArrow"}
    modifiers, key = [], None
    for part in parts:
        token = part.replace(" ", "").casefold()
        if token in modifier_names:
            modifier = "Key_" + modifier_names[token]
            if modifier in modifiers:
                raise ValueError("Use each modifier only once.")
            modifiers.append(modifier)
        elif key is None and token:
            bare = aliases.get(token, token)
            key = "Key_" + key_name(bare)
        else:
            raise ValueError("Record one keyboard key, with optional modifiers.")
    if key is None or pressable(key, modifiers):
        raise ValueError("Record a letter, number, F-key or another supported keyboard key.")
    if key_name(key) in {"leftcontrol", "rightcontrol", "leftalt", "rightalt", "leftshift", "rightshift", "leftwin", "rightwin"}:
        raise ValueError("Add a final key after the modifier.")
    return key, tuple(modifiers)


# -- Windows ----------------------------------------------------------------------------
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_SCANCODE = 0x0008
_INPUT_KEYBOARD = 1


def _input_types():
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _EVENT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("event", _EVENT)]

    return KEYBDINPUT, INPUT


class GameWindow:
    """Elite's window: found by its process, brought to the front when a
    command is typed on the deck, and asked whether it's in front."""

    def __init__(self):
        self.handle = 0
        self._user32 = self._kernel32 = None
        if sys.platform == "win32":
            from ctypes import wintypes
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._user32.GetForegroundWindow.restype = wintypes.HWND
            self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            self._user32.IsWindow.argtypes = [wintypes.HWND]
            self._user32.IsWindowVisible.argtypes = [wintypes.HWND]
            self._user32.IsIconic.argtypes = [wintypes.HWND]
            self._user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            self._user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            self._user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
            self._kernel32.OpenProcess.restype = wintypes.HANDLE
            self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self._kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                                  wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    def _exe(self, handle):
        from ctypes import wintypes
        pid = wintypes.DWORD(0)
        self._user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if not pid.value:
            return ""
        process = self._kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not process:
            return ""
        try:
            size = wintypes.DWORD(520)
            buffer = ctypes.create_unicode_buffer(size.value)
            if self._kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                return buffer.value.rsplit("\\", 1)[-1].casefold()
            return ""
        finally:
            self._kernel32.CloseHandle(process)

    def find(self):
        """Elite's top window, or 0 when the game isn't running."""
        if self._user32 is None:
            return 0
        if self.handle and self._user32.IsWindow(self.handle) and self._exe(self.handle) == GAME_EXE:
            return self.handle
        from ctypes import wintypes
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(handle, _param):
            if self._user32.IsWindowVisible(handle) and self._exe(handle) == GAME_EXE:
                found.append(handle)
                return False
            return True

        self._user32.EnumWindows(visit, 0)
        self.handle = found[0] if found else 0
        return self.handle

    def in_front(self):
        return bool(self.handle) and self._user32 is not None and self._user32.GetForegroundWindow() == self.handle

    def bring_forward(self):
        """Elite to the front (a command typed on the deck). True once it is."""
        if not self.find():
            return False
        if self.in_front():
            return True
        user32, kernel32 = self._user32, self._kernel32
        try:
            if user32.IsIconic(self.handle):
                user32.ShowWindow(self.handle, 9)  # SW_RESTORE
            front = user32.GetForegroundWindow()
            theirs = user32.GetWindowThreadProcessId(front, None) if front else 0
            ours = kernel32.GetCurrentThreadId()
            # Windows lets a window come forward from the thread whose input it shares.
            attached = bool(theirs and theirs != ours and user32.AttachThreadInput(ours, theirs, True))
            try:
                user32.SetForegroundWindow(self.handle)
            finally:
                if attached:
                    user32.AttachThreadInput(ours, theirs, False)
        except OSError:
            logging.exception("Couldn't bring Elite to the front")
            return False
        end = time.monotonic() + FOCUS_WAIT_S
        while time.monotonic() < end:
            if self.in_front():
                time.sleep(SETTLE_S)
                return True
            time.sleep(0.03)
        return False


class KeyPresser:
    """Presses one binding at a time, and only while ``allowed()`` says the
    game is in front. ``send(scancode, extended, up)`` is SendInput's."""

    def __init__(self, allowed, send=None, sleep=time.sleep):
        self.allowed = allowed
        self.sleep = sleep
        self.send = send or self._send_input
        self._types = None

    def _send_input(self, code, extended, up):
        if sys.platform != "win32":
            return False
        if self._types is None:
            self._types = _input_types()
        KEYBDINPUT, INPUT = self._types
        flags = _KEYEVENTF_SCANCODE | (_KEYEVENTF_EXTENDEDKEY if extended else 0) | (_KEYEVENTF_KEYUP if up else 0)
        event = INPUT(type=_INPUT_KEYBOARD)
        event.event.ki = KEYBDINPUT(wVk=0, wScan=code, dwFlags=flags, time=0, dwExtraInfo=0)
        return ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) == 1

    def press(self, key, modifiers=(), hold=HOLD_S):
        """Down and up, its modifiers held around it. False (nothing left
        held) when a key can't be pressed or the game isn't in front."""
        names = [*modifiers, key]
        codes = [scancode(name) for name in names]
        if any(code is None for code in codes):
            return False
        down = []
        try:
            for index, (code, extended) in enumerate(codes):
                if not self.allowed():
                    return False
                if not self.send(code, extended, False):
                    return False
                down.append((code, extended))
                duration = hold if index == len(codes) - 1 else MODIFIER_LEAD_S
                if duration <= 0.2:
                    self.sleep(duration)
                else:
                    remaining = duration
                    while remaining > 0:
                        if not self.allowed():
                            return False
                        step = min(0.05, remaining)
                        self.sleep(step)
                        remaining -= step
            return True
        finally:
            for code, extended in reversed(down):
                self.send(code, extended, True)
