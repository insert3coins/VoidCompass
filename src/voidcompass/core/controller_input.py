"""Controller buttons for Void Compass's shortcuts (5.7.3): an Xbox-style pad,
a flight stick, a HOTAS, a PlayStation pad.

Two of Windows' own services, nothing to install:
- XInput for Xbox-style pads (Xbox 360, One and Series, and pads that act
  like them). It reads a pad directly, in the background, with no device
  list to go stale.
- winmm for everything else (sticks, throttles, button boxes, PlayStation
  pads), the way Starling reads an X52. winmm makes its device list once per
  program, so a controller plugged in after Void Compass started stayed
  invisible: the cause of the 5.5.17 attempts seeing nothing in the app while
  a fresh script saw the pad. Each refresh calls joyConfigChanged first, so
  winmm looks again. A pad XInput reads is left out of the winmm list.

A button is written as a short "spec":
    pad:A              a button on any Xbox-style pad (A B X Y LB RB Back
                       Start LS RS Up Down Left Right LT RT)
    joy:06A3:075C:7    button 7 on the device with USB id 06A3:075C
    hat:06A3:075C:Up   that device's hat, pushed up
    pad:LB+pad:A       hold the first, press the second (a combination:
                       a pad has few buttons Elite leaves free)

A ControllerHub polls on its own thread and calls ``on_press(action, spec)``
for the shortcut a press means; ``snapshot()`` is what's held right now (for
the Settings page's live readout) and ``learn()`` waits for the next press.
"""
from __future__ import annotations

import logging
import sys
import threading
import time

PAD_BUTTONS = (
    ("Up", 0x0001), ("Down", 0x0002), ("Left", 0x0004), ("Right", 0x0008), ("Start", 0x0010), ("Back", 0x0020),
    ("LS", 0x0040), ("RS", 0x0080), ("LB", 0x0100), ("RB", 0x0200), ("A", 0x1000), ("B", 0x2000), ("X", 0x4000),
    ("Y", 0x8000),
)
PAD_NAMES = {"Up": "D-pad up", "Down": "D-pad down", "Left": "D-pad left", "Right": "D-pad right",
             "Start": "Menu (Start)", "Back": "View (Back)", "LS": "left stick press", "RS": "right stick press",
             "LB": "LB", "RB": "RB", "A": "A", "B": "B", "X": "X", "Y": "Y", "LT": "LT", "RT": "RT"}
TRIGGER_DOWN = 128
POLL_S = 0.02
IDLE_POLL_S = 0.25
# How often to look for controllers plugged in since: quickly while the
# Settings page is watching or learning a button, now and then otherwise.
REFRESH_S = 3.0
IDLE_REFRESH_S = 15.0
LEARN_S = 8.0
# Names winmm gives an Xbox-style pad, which XInput reads instead.
_XINPUT_WORDS = ("xbox", "xinput", "x-box")


def _ident(vendor, product):
    return f"{int(vendor) & 0xFFFF:04X}:{int(product) & 0xFFFF:04X}"


def hat_directions(value):
    """The hat in hundredths of a degree (65535: centred) -> {"Up", "Right", ...}."""
    if value is None or value < 0 or value >= 36000:
        return set()
    found = set()
    if value <= 4500 or value >= 31500:
        found.add("Up")
    if 4500 <= value <= 13500:
        found.add("Right")
    if 13500 <= value <= 22500:
        found.add("Down")
    if 22500 <= value <= 31500:
        found.add("Left")
    return found


# -- specs ------------------------------------------------------------------------
def parse(spec):
    """One button: ("pad", "A") | ("joy", "06A3:075C", 7) | ("hat", "06A3:075C", "Up") | None."""
    kind, _, rest = str(spec or "").strip().partition(":")
    if kind == "pad" and rest in PAD_NAMES:
        return "pad", rest
    parts = rest.split(":")
    if kind in ("joy", "hat") and len(parts) == 3:
        ident = f"{parts[0].upper()}:{parts[1].upper()}"
        if kind == "joy" and parts[2].isdigit() and 1 <= int(parts[2]) <= 32:
            return "joy", ident, int(parts[2])
        if kind == "hat" and parts[2].title() in ("Up", "Down", "Left", "Right"):
            return "hat", ident, parts[2].title()
    return None


def split(spec):
    """A spec as (held first, pressed): ("", spec) for one button; None if not understood."""
    parts = [part.strip() for part in str(spec or "").split("+") if part.strip()]
    if len(parts) == 1 and parse(parts[0]):
        return "", parts[0]
    if len(parts) == 2 and parse(parts[0]) and parse(parts[1]) and parts[0] != parts[1]:
        return parts[0], parts[1]
    return None


def valid(spec):
    return split(spec) is not None


def describe(spec, names=None):
    """"pad:LB+pad:A" -> "Pad: hold LB, press A"; a stick's button by its name when known."""
    pair = split(spec)
    if pair is None:
        return ""
    names = names or {}

    def one(part, with_device=True):
        parsed = parse(part)
        if parsed[0] == "pad":
            return ("Pad: " if with_device else "") + PAD_NAMES[parsed[1]]
        device = names.get(parsed[1]) or f"Controller {parsed[1]}"
        what = f"button {parsed[2]}" if parsed[0] == "joy" else f"hat {parsed[2].lower()}"
        return f"{device}: {what}" if with_device else what

    held, pressed = pair
    if not held:
        return one(pressed)
    first, second = parse(held), parse(pressed)
    if first[0] == second[0] == "pad":
        return f"Pad: hold {one(held, False)}, press {one(pressed, False)}"
    if first[0] != "pad" and second[0] != "pad" and first[1] == second[1]:
        device = names.get(second[1]) or f"Controller {second[1]}"
        return f"{device}: hold {one(held, False)}, press {one(pressed, False)}"
    return f"hold {one(held)}, then press {one(pressed)}"


def elite_control(spec):
    """A spec as elite_binds' control, for clashes: ("pad", "A", {"LB"}) or
    ("joy", "06A3:075C", "7", set()); None when the two buttons are on different devices."""
    pair = split(spec)
    if pair is None:
        return None
    held, pressed = (parse(part) if part else None for part in pair)
    if pressed[0] == "pad":
        if held and held[0] != "pad":
            return None
        return "pad", pressed[1], {held[1]} if held else set()

    def name(parsed):
        return str(parsed[2]) if parsed[0] == "joy" else f"hat {parsed[2]}"

    if held and (held[0] == "pad" or held[1] != pressed[1]):
        return None
    return "joy", pressed[1], name(pressed), {name(held)} if held else set()


# -- reading Windows ---------------------------------------------------------------
class XInputPads:
    """Windows' XInput: up to four Xbox-style pads, read directly."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class Gamepad(ctypes.Structure):
            _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
                        ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                        ("sThumbRY", ctypes.c_short)]

        class State(ctypes.Structure):
            _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", Gamepad)]

        self.ctypes, self.State = ctypes, State
        self.dll = None
        for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                self.dll = ctypes.WinDLL(name)
                break
            except OSError:
                continue
        if self.dll is not None:
            self.dll.XInputGetState.argtypes = [wintypes.DWORD, ctypes.POINTER(State)]
            self.dll.XInputGetState.restype = wintypes.DWORD

    def pressed(self):
        """{slot: set of button names} for each pad connected."""
        found = {}
        if self.dll is None:
            return found
        for slot in range(4):
            state = self.State()
            if self.dll.XInputGetState(slot, self.ctypes.byref(state)) != 0:
                continue
            pad = state.Gamepad
            down = {name for name, bit in PAD_BUTTONS if pad.wButtons & bit}
            if pad.bLeftTrigger >= TRIGGER_DOWN:
                down.add("LT")
            if pad.bRightTrigger >= TRIGGER_DOWN:
                down.add("RT")
            found[slot] = down
        return found


class WinmmJoysticks:
    """Windows' winmm joystick service: sticks, throttles, button boxes,
    PlayStation pads. ``devices()`` asks Windows to look again first."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class Caps(ctypes.Structure):
            _fields_ = ([("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("szPname", ctypes.c_wchar * 32)]
                        + [(n, wintypes.UINT) for n in ("wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax",
                                                         "wNumButtons", "wPeriodMin", "wPeriodMax", "wRmin", "wRmax",
                                                         "wUmin", "wUmax", "wVmin", "wVmax", "wCaps", "wMaxAxes",
                                                         "wNumAxes", "wMaxButtons")]
                        + [("szRegKey", ctypes.c_wchar * 32), ("szOEMVxD", ctypes.c_wchar * 260)])

        class Info(ctypes.Structure):
            _fields_ = [(n, wintypes.DWORD) for n in ("dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos",
                                                        "dwUpos", "dwVpos", "dwButtons", "dwButtonNumber", "dwPOV",
                                                        "dwReserved1", "dwReserved2")]

        self.ctypes, self.Caps, self.Info = ctypes, Caps, Info
        self.winmm = ctypes.WinDLL("winmm")
        self.winmm.joyGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(Caps), wintypes.UINT]
        self.winmm.joyGetPosEx.argtypes = [wintypes.UINT, ctypes.POINTER(Info)]
        try:
            self.winmm.joyConfigChanged.argtypes = [wintypes.DWORD]
        except AttributeError:
            pass

    def devices(self):
        """[(index, ident, name, buttons)] for each one plugged in."""
        try:
            # Without this, winmm keeps the list it made when the program first asked.
            self.winmm.joyConfigChanged(0)
        except (AttributeError, OSError):
            pass
        found = []
        for index in range(int(self.winmm.joyGetNumDevs())):
            caps = self.Caps()
            if self.winmm.joyGetDevCapsW(index, self.ctypes.byref(caps), self.ctypes.sizeof(caps)) != 0:
                continue
            if self.state(index) is None:
                continue
            name = _registry_name(caps.szRegKey, index) or caps.szPname or f"Controller {index + 1}"
            found.append((index, _ident(caps.wMid, caps.wPid), name, min(int(caps.wNumButtons), 32)))
        return found

    def state(self, index):
        """(button mask, hat) for one device, or None when it can't be read."""
        info = self.Info()
        info.dwSize = self.ctypes.sizeof(info)
        info.dwFlags = 0x80 | 0x40   # JOY_RETURNBUTTONS | JOY_RETURNPOV
        if self.winmm.joyGetPosEx(index, self.ctypes.byref(info)) != 0:
            return None
        return int(info.dwButtons), int(info.dwPOV)


def _registry_name(reg_key, index):
    """The name Windows shows in its game controller settings (best effort)."""
    if sys.platform != "win32" or not reg_key:
        return ""
    import winreg
    config = rf"System\CurrentControlSet\Control\MediaResources\Joystick\{reg_key}\CurrentJoystickSettings"
    oem = r"System\CurrentControlSet\Control\MediaProperties\PrivateProperties\Joystick\OEM\%s"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, config) as key:
                oem_key = winreg.QueryValueEx(key, f"Joystick{index + 1}OEMName")[0]
            with winreg.OpenKey(hive, oem % oem_key) as key:
                return str(winreg.QueryValueEx(key, "OEMName")[0])
        except OSError:
            continue
    return ""


# -- the hub -----------------------------------------------------------------------
class ControllerHub:
    """Reads every controller on its own thread and turns presses into shortcuts.

    ``bindings()`` -> {action: spec}; ``on_press(action, spec)`` is called on
    this thread when a binding's button goes down (for a combination: the
    second button, while the first is held)."""

    def __init__(self, bindings=lambda: {}, on_press=None, pads=None, joysticks=None, clock=time.monotonic,
                 sleep=time.sleep):
        self.bindings = bindings
        self.on_press = on_press
        self._pads = pads
        self._joysticks = joysticks
        self.clock = clock
        self.sleep = sleep
        self.devices = []            # [{"ident", "name", "kind", "buttons"}]
        self.error = ""
        self._winmm = []             # [(index, ident, name, buttons)]
        self._refreshed = -REFRESH_S
        self._held = set()
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._learning = None        # {"until", "before", "first", "done", "result"}
        self._watching_until = 0.0

    # -- reading ------------------------------------------------------------------
    def _backends(self):
        if self._pads is None:
            try:
                self._pads = XInputPads()
            except Exception as exc:
                logging.debug("XInput unavailable: %s", exc)
                self._pads = False
        if self._joysticks is None:
            try:
                self._joysticks = WinmmJoysticks()
            except Exception as exc:
                logging.debug("winmm joysticks unavailable: %s", exc)
                self._joysticks = False
        return self._pads or None, self._joysticks or None

    def refresh(self, force=False):
        """Look again for controllers (every few seconds; plugged in later, they're found)."""
        now = self.clock()
        interval = REFRESH_S if self._learning is not None or now < self._watching_until else IDLE_REFRESH_S
        if not force and now - self._refreshed < interval:
            return
        self._refreshed = now
        pads, joysticks = self._backends()
        found = []
        try:
            for slot in sorted((pads.pressed() if pads else {})):
                found.append({"ident": f"pad{slot + 1}", "name": f"Xbox-style pad {slot + 1}", "kind": "pad",
                              "buttons": len(PAD_NAMES)})
        except Exception as exc:
            self.error = f"XInput: {exc}"
        winmm = []
        try:
            for row in (joysticks.devices() if joysticks else []):
                if any(word in row[2].casefold() for word in _XINPUT_WORDS):
                    continue   # XInput reads it
                winmm.append(row)
                found.append({"ident": row[1], "name": row[2], "kind": "joystick", "buttons": row[3]})
        except Exception as exc:
            self.error = f"winmm: {exc}"
        with self._lock:
            self._winmm = winmm
            self.devices = found

    def names(self):
        """{"06A3:075C": "Saitek X52"} for describing specs."""
        return {row["ident"]: row["name"] for row in self.devices if row["kind"] == "joystick"}

    def snapshot(self):
        """Every button held right now, as specs."""
        pads, joysticks = self._backends()
        down = set()
        try:
            for buttons in (pads.pressed() if pads else {}).values():
                down |= {f"pad:{name}" for name in buttons}
        except Exception as exc:
            self.error = f"XInput: {exc}"
        with self._lock:
            winmm = list(self._winmm)
        for index, ident, _name, buttons in winmm:
            try:
                state = joysticks.state(index) if joysticks else None
            except Exception:
                state = None
            if state is None:
                continue
            mask, hat = state
            down |= {f"joy:{ident}:{button}" for button in range(1, min(buttons or 32, 32) + 1)
                     if mask & (1 << (button - 1))}
            down |= {f"hat:{ident}:{direction}" for direction in hat_directions(hat)}
        return down

    def is_down(self, spec):
        """A binding held now (both buttons, for a combination)."""
        pair = split(spec)
        if pair is None:
            return False
        down = self._held
        return pair[1] in down and (not pair[0] or pair[0] in down)

    # -- learning a button ------------------------------------------------------------
    def learn(self, seconds=LEARN_S):
        """Wait for the next press (from now): a button, or a combination when
        a second goes down while the first is held. The spec, or "" if none."""
        done = threading.Event()
        with self._lock:
            self._learning = {"until": self.clock() + seconds, "before": set(self._held), "first": "",
                              "done": done, "result": ""}
        self.start()
        done.wait(seconds + 1)
        with self._lock:
            result, self._learning = (self._learning or {}).get("result", ""), None
        return result

    def cancel_learning(self):
        with self._lock:
            learning = self._learning
        if learning:
            learning["done"].set()

    def watch(self, seconds=30.0):
        """Poll quickly for a while (the Settings page's live readout)."""
        self._watching_until = self.clock() + seconds
        self.start()

    def _learn_step(self, down, now):
        learning = self._learning
        if not learning:
            return
        fresh = sorted(down - learning["before"])
        first = learning["first"]
        if first and first not in down:
            # Let go without a second button: that button alone.
            learning["result"] = first
        elif first and fresh:
            second = next((spec for spec in fresh if spec != first), "")
            if second:
                learning["result"] = f"{first}+{second}"
        elif not first and fresh:
            learning["first"] = fresh[0]
            learning["before"] = set(down) - {fresh[0]}
        if learning["result"] or now >= learning["until"]:
            learning["done"].set()

    # -- the loop ---------------------------------------------------------------------
    def poll_once(self):
        self.refresh()
        down = self.snapshot()
        now = self.clock()
        pressed = down - self._held
        self._held = down
        with self._lock:
            learning = self._learning
        if learning:
            self._learn_step(down, now)
            return
        if not pressed or not callable(self.on_press):
            return
        try:
            bindings = dict(self.bindings() or {})
        except Exception:
            bindings = {}
        # A combination before its second button alone: holding LB, A means LB+A.
        for action, spec in sorted(bindings.items(), key=lambda item: "+" not in str(item[1])):
            pair = split(spec)
            if pair is None or pair[1] not in pressed:
                continue
            if pair[0] and pair[0] not in down:
                continue
            if not pair[0] and any(split(other) and split(other)[0] in down and split(other)[1] == pair[1]
                                   for other in bindings.values() if other != spec):
                continue   # that button, held with another, is a combination's
            try:
                self.on_press(action, spec)
            except Exception:
                logging.exception("A controller shortcut failed")

    def busy(self):
        return bool(self.bindings()) or self._learning is not None or self.clock() < self._watching_until

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._loop, name="controller-input", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self.cancel_learning()

    def _loop(self):
        while self._running:
            try:
                self.poll_once()
            except Exception:
                logging.exception("Controller poll failed")
            try:
                busy = self.busy()
            except Exception:
                busy = False
            self.sleep(POLL_S if busy else IDLE_POLL_S)
