"""Small Windows global-hotkey service used by the native overlays.

The service deliberately uses the Win32 API directly so packaged releases do
not gain another Python dependency.  Callbacks are raised on the hotkey thread;
the dashboard forwards them through its bounded Tk dispatcher.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import threading


OVERLAY_HOTKEY_SPECS = (
    ("toggle_all", "overlay_hotkey_toggle_all", "Show / hide all overlays", None),
    ("navigation", "overlay_hotkey_navigation", "Navigation HUD", "hud"),
    ("survey", "overlay_hotkey_survey", "Survey Status", "survey_status_hud"),
    ("system_info", "overlay_hotkey_system_info", "System Info", "system_info_hud"),
    ("station_info", "overlay_hotkey_station_info", "Station Info", "station_info_hud"),
    ("cargo", "overlay_hotkey_cargo", "Cargo Manifest", "cargo_hud"),
    ("carrier", "overlay_hotkey_carrier", "Fleet Carrier", "carrier_hud"),
    ("prospector", "overlay_hotkey_prospector", "Prospector Results", "prospector_hud"),
    ("colony", "overlay_hotkey_colony", "Colony Shopping", "colony_overlay"),
)

DEFAULT_OVERLAY_HOTKEYS = {
    "overlay_hotkey_toggle_all": "Ctrl+Shift+O",
}

_MODIFIERS = {
    "CTRL": (0x0002, "Ctrl"),
    "CONTROL": (0x0002, "Ctrl"),
    "ALT": (0x0001, "Alt"),
    "SHIFT": (0x0004, "Shift"),
    "WIN": (0x0008, "Win"),
    "WINDOWS": (0x0008, "Win"),
    "META": (0x0008, "Win"),
}
_MODIFIER_ORDER = ((0x0002, "Ctrl"), (0x0001, "Alt"), (0x0004, "Shift"), (0x0008, "Win"))
_NAMED_KEYS = {
    "BACKSPACE": (0x08, "Backspace"),
    "TAB": (0x09, "Tab"),
    "ENTER": (0x0D, "Enter"),
    "RETURN": (0x0D, "Enter"),
    "ESC": (0x1B, "Escape"),
    "ESCAPE": (0x1B, "Escape"),
    "SPACE": (0x20, "Space"),
    "SPACEBAR": (0x20, "Space"),
    "PAGEUP": (0x21, "PageUp"),
    "PGUP": (0x21, "PageUp"),
    "PAGEDOWN": (0x22, "PageDown"),
    "PGDN": (0x22, "PageDown"),
    "END": (0x23, "End"),
    "HOME": (0x24, "Home"),
    "LEFT": (0x25, "Left"),
    "UP": (0x26, "Up"),
    "RIGHT": (0x27, "Right"),
    "DOWN": (0x28, "Down"),
    "INSERT": (0x2D, "Insert"),
    "INS": (0x2D, "Insert"),
    "DELETE": (0x2E, "Delete"),
    "DEL": (0x2E, "Delete"),
}


def parse_hotkey(value):
    """Return ``(modifiers, virtual_key, canonical)`` or ``None`` when blank."""
    text = str(value or "").strip()
    if not text:
        return None
    parts = [part.strip() for part in text.split("+") if part.strip()]
    if not parts:
        return None
    modifier_mask = 0
    key_value = None
    key_label = None
    for part in parts:
        token = re.sub(r"[\s_-]+", "", part).upper()
        modifier = _MODIFIERS.get(token)
        if modifier:
            if modifier_mask & modifier[0]:
                raise ValueError(f"duplicate {modifier[1]} modifier")
            modifier_mask |= modifier[0]
            continue
        if key_value is not None:
            raise ValueError("use exactly one non-modifier key")
        if len(token) == 1 and token in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            key_value, key_label = ord(token), token
        elif token in _NAMED_KEYS:
            key_value, key_label = _NAMED_KEYS[token]
        elif re.fullmatch(r"F(?:[1-9]|1[0-9]|2[0-4])", token):
            number = int(token[1:])
            key_value, key_label = 0x6F + number, f"F{number}"
        else:
            raise ValueError(f"unsupported key '{part}'")
    if not modifier_mask:
        raise ValueError("include Ctrl, Alt, Shift or Win")
    if key_value is None:
        raise ValueError("include a letter, number, function or navigation key")
    labels = [label for bit, label in _MODIFIER_ORDER if modifier_mask & bit]
    labels.append(key_label)
    return modifier_mask, key_value, "+".join(labels)


def normalize_hotkey(value):
    parsed = parse_hotkey(value)
    return parsed[2] if parsed else ""


def validate_hotkey_bindings(bindings):
    """Normalize action bindings and reject ambiguous duplicate shortcuts."""
    normalized = {}
    owners = {}
    errors = {}
    for action, value in dict(bindings or {}).items():
        try:
            canonical = normalize_hotkey(value)
        except ValueError as exc:
            errors[action] = str(exc)
            continue
        normalized[action] = canonical
        if not canonical:
            continue
        previous = owners.get(canonical.casefold())
        if previous is not None:
            errors[action] = f"duplicates {canonical} assigned to {previous}"
            errors.setdefault(previous, f"duplicates {canonical} assigned to {action}")
        else:
            owners[canonical.casefold()] = action
    return normalized, errors


class GlobalHotkeyManager:
    """Register a replaceable set of application-global Windows hotkeys."""

    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012
    PM_NOREMOVE = 0x0000
    MOD_NOREPEAT = 0x4000

    def __init__(self, callback):
        self.callback = callback
        self._thread = None
        self._thread_id = 0
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def supported(self):
        return os.name == "nt"

    def configure(self, bindings):
        """Replace registrations and return registered shortcuts plus errors."""
        self.stop()
        normalized, errors = validate_hotkey_bindings(bindings)
        parsed = []
        for action, canonical in normalized.items():
            if not canonical or action in errors:
                continue
            modifiers, virtual_key, _label = parse_hotkey(canonical)
            parsed.append((action, canonical, modifiers, virtual_key))
        report = {"registered": {}, "errors": dict(errors), "supported": self.supported}
        if not self.supported:
            return report
        if not parsed:
            return report

        ready = threading.Event()
        self._stop_event = threading.Event()
        thread = threading.Thread(
            target=self._message_loop,
            args=(parsed, report, ready, self._stop_event),
            name="overlay-hotkeys",
            daemon=True,
        )
        with self._lock:
            self._thread = thread
        thread.start()
        if not ready.wait(0.75):
            report["errors"]["service"] = "hotkey service did not start in time"
        return report

    def _message_loop(self, parsed, report, ready, stop_event):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
        user32.GetMessageW.restype = wintypes.BOOL
        user32.PeekMessageW.argtypes = (
            ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT,
        )
        user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.PostThreadMessageW.restype = wintypes.BOOL
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, self.PM_NOREMOVE)
        thread_id = int(kernel32.GetCurrentThreadId())
        with self._lock:
            self._thread_id = thread_id
        actions = {}
        registered_ids = []
        try:
            for index, (action, canonical, modifiers, virtual_key) in enumerate(parsed):
                hotkey_id = 0x5600 + index
                if user32.RegisterHotKey(
                    None, hotkey_id, modifiers | self.MOD_NOREPEAT, virtual_key,
                ):
                    actions[hotkey_id] = action
                    registered_ids.append(hotkey_id)
                    report["registered"][action] = canonical
                else:
                    code = ctypes.get_last_error()
                    detail = "already used by Windows or another application" if code == 1409 else f"Windows error {code}"
                    report["errors"][action] = detail
            ready.set()
            while not stop_event.is_set():
                result = int(user32.GetMessageW(ctypes.byref(msg), None, 0, 0))
                if result <= 0:
                    break
                if msg.message == self.WM_HOTKEY:
                    action = actions.get(int(msg.wParam))
                    if action and callable(self.callback):
                        try:
                            self.callback(action)
                        except Exception:
                            pass
        finally:
            for hotkey_id in registered_ids:
                user32.UnregisterHotKey(None, hotkey_id)
            ready.set()
            with self._lock:
                if self._thread_id == thread_id:
                    self._thread_id = 0

    def stop(self):
        with self._lock:
            thread = self._thread
            thread_id = self._thread_id
            stop_event = self._stop_event
            self._thread = None
        if not thread:
            return
        stop_event.set()
        if thread_id and os.name == "nt":
            try:
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostThreadMessageW(thread_id, self.WM_QUIT, 0, 0)
            except Exception:
                pass
        if thread is not threading.current_thread():
            thread.join(timeout=0.35)
