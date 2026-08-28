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
    ("layout_studio", "overlay_hotkey_layout_studio", "Toggle Overlay Layout Studio", None),
    ("toggle_all", "overlay_hotkey_toggle_all", "Show / hide all overlays", None),
    ("navigation", "overlay_hotkey_navigation", "Navigation HUD", "hud"),
    ("navigation_layout", "overlay_hotkey_navigation_layout", "Navigation HUD layout", None),
    ("survey", "overlay_hotkey_survey", "Survey Operations", "survey_status_hud"),
    ("contact_scope", "overlay_hotkey_contact_scope", "Deep Space Contacts", "contact_scope_hud"),
    ("station_info", "overlay_hotkey_station_info", "Station Info", "station_info_hud"),
    ("cargo", "overlay_hotkey_cargo", "Cargo Manifest", "cargo_hud"),
    ("carrier", "overlay_hotkey_carrier", "Fleet Carrier", "carrier_hud"),
    ("prospector", "overlay_hotkey_prospector", "Prospector Results", "prospector_hud"),
    ("field_bookmark", "overlay_hotkey_field_bookmark", "Save field bookmark", None),
)

DEFAULT_OVERLAY_HOTKEYS = {
    "overlay_hotkey_layout_studio": "Ctrl+Alt+Shift+F10",
    "overlay_hotkey_toggle_all": "Ctrl+Alt+Shift+F11",
    "overlay_hotkey_field_bookmark": "Ctrl+Alt+Shift+F12",
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

_TK_MODIFIER_KEYSYMS = {
    "ALT", "ALTL", "ALTR",
    "CONTROL", "CONTROLL", "CONTROLR",
    "CTRL", "CTRLL", "CTRLR",
    "META", "METAL", "METAR",
    "SHIFT", "SHIFTL", "SHIFTR",
    "SUPER", "SUPERL", "SUPERR",
    "WIN", "WINL", "WINR",
}
_TK_NAMED_KEYSYMS = {
    "BACKSPACE": "Backspace",
    "TAB": "Tab",
    "ISOLEFTTAB": "Tab",
    "RETURN": "Enter",
    "KPENTER": "Enter",
    "ESC": "Escape",
    "ESCAPE": "Escape",
    "SPACE": "Space",
    "PRIOR": "PageUp",
    "PAGEUP": "PageUp",
    "NEXT": "PageDown",
    "PAGEDOWN": "PageDown",
    "END": "End",
    "HOME": "Home",
    "LEFT": "Left",
    "UP": "Up",
    "RIGHT": "Right",
    "DOWN": "Down",
    "INSERT": "Insert",
    "DELETE": "Delete",
}
_TK_SHIFTED_DIGIT_KEYSYMS = {
    # Tk reports the produced symbol rather than the number-row key whenever
    # Shift is held. Global RegisterHotKey needs the underlying 0-9 key.
    "EXCLAM": "1",
    "AT": "2",
    "QUOTEDBL": "2",
    "NUMBERSIGN": "3",
    "STERLING": "3",
    "DOLLAR": "4",
    "PERCENT": "5",
    "ASCIICIRCUM": "6",
    "CARET": "6",
    "AMPERSAND": "7",
    "ASTERISK": "8",
    "PARENLEFT": "9",
    "PARENRIGHT": "0",
}


def _tk_keysym_token(keysym):
    return re.sub(r"[\s_-]+", "", str(keysym or "")).upper()


def tk_modifier_labels(keysym="", state=0):
    """Return canonical modifiers held during a Tk key event.

    Tk's portable modifier masks cover Shift/Control/Mod1/Mod4.  Windows can
    additionally report Alt through its extended state bit, so accept both.
    Including the modifier currently being pressed keeps the recorder preview
    responsive before Tk adds that key to the event state.
    """
    try:
        state = int(state or 0)
    except (TypeError, ValueError):
        state = 0
    held = set()
    if state & 0x0004:
        held.add("Ctrl")
    if state & (0x0008 | 0x20000):
        held.add("Alt")
    if state & 0x0001:
        held.add("Shift")
    if state & 0x0040:
        held.add("Win")

    token = _tk_keysym_token(keysym)
    if token.startswith(("CONTROL", "CTRL")):
        held.add("Ctrl")
    elif token.startswith("ALT"):
        held.add("Alt")
    elif token.startswith("SHIFT"):
        held.add("Shift")
    elif token.startswith(("SUPER", "META", "WIN")):
        held.add("Win")
    return tuple(label for _bit, label in _MODIFIER_ORDER if label in held)


def hotkey_from_tk_event(keysym, state=0, keycode=None):
    """Convert a Tk key press into the canonical global-hotkey syntax.

    Modifier-only events return an empty string so a recorder can show the
    partial chord. Unsupported keys and unmodified final keys raise the same
    friendly validation errors as manually entered bindings.
    """
    token = _tk_keysym_token(keysym)
    if token in _TK_MODIFIER_KEYSYMS:
        return ""
    try:
        virtual_key = int(keycode) if keycode is not None else None
    except (TypeError, ValueError):
        virtual_key = None
    if os.name == "nt" and virtual_key is not None and 0x30 <= virtual_key <= 0x39:
        # On Windows Tk's keycode is the same virtual-key value consumed by
        # RegisterHotKey, so it remains layout-safe even when Shift turns 9
        # into the ``parenleft`` keysym (and similarly for the other digits).
        key_label = chr(virtual_key)
    elif len(token) == 1 and token in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        key_label = token
    elif token in _TK_SHIFTED_DIGIT_KEYSYMS:
        key_label = _TK_SHIFTED_DIGIT_KEYSYMS[token]
    elif token in _TK_NAMED_KEYSYMS:
        key_label = _TK_NAMED_KEYSYMS[token]
    elif re.fullmatch(r"F(?:[1-9]|1[0-9]|2[0-4])", token):
        key_label = token
    else:
        raise ValueError(f"unsupported key '{keysym}'")
    modifiers = tk_modifier_labels("", state)
    if not modifiers:
        raise ValueError("hold Ctrl, Alt, Shift or Win before pressing the final key")
    return normalize_hotkey("+".join((*modifiers, key_label)))


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
