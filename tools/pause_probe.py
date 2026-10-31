"""Find out what marks Elite's pause menu. A developer tool, run on its own;
it's no part of Void Compass and never ships (parked, 2026-10-30).

The game writes nothing when its pause menu opens. While you play, this
records what might tell:
  - the keys that open it, read from your bindings: Esc, Start on a
    controller, and whatever your presets bind to Pause. Only those keys are
    recorded (and Scroll Lock, below), nothing else you type.
  - the mouse pointer: showing or not, which one, and whether it's held
    inside Elite's window
  - Status.json (GuiFocus, Flags) and the journal's Music track
  - whether Elite is the window in front

    python tools/pause_probe.py keys       # the keys your bindings use to open it
    python tools/pause_probe.py selftest   # it opens and closes the menu itself
    python tools/pause_probe.py watch      # record while you play (Ctrl+C to stop)
    python tools/pause_probe.py report     # what lined up with the pause menu

selftest: with Elite running and you docked somewhere safe, click into the
game and keep your hands off for a minute. It presses Esc itself (as voice
macro tools do), and the galaxy map and left panel keys if you have keyboard
bindings for them; after each it records the signals and a screenshot of the
game, so you can see the menu really opened. Results in
tools/pause_probe/selftest-<time>/.

watch: tap Scroll Lock each time you open the pause menu and again when it
closes: the report checks every signal against your taps. Open and close a
panel, a map and station services too, so it can see what they look like.
Recordings go to tools/pause_probe/ (git-ignored).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elite_bindings  # noqa: E402  (beside this tool; not part of the app)

HERE = Path(__file__).resolve().parent / "pause_probe"
JOURNALS = Path.home() / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
VK_SCROLL = 0x91
MODIFIER_KEYS = {0xA0: "Key_LeftShift", 0xA1: "Key_RightShift", 0xA2: "Key_LeftControl",
                 0xA3: "Key_RightControl", 0xA4: "Key_LeftAlt", 0xA5: "Key_RightAlt"}
XINPUT_BUTTONS = {0x0010: "GamePad_Start", 0x0020: "GamePad_Back"}

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
kernel32.GetModuleHandleW.restype = wt.HMODULE


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hCursor", ctypes.c_void_p), ("ptScreenPos", wt.POINT)]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wt.DWORD), ("wButtons", wt.WORD), ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]


# -- the keys -------------------------------------------------------------------------------------
def watched_keys():
    """Virtual-key code -> Elite key name, for every keyboard key that opens the menu."""
    found = elite_bindings.pause_keys()
    keys = {}
    for binding in found["keys"]:
        code = elite_bindings.virtual_key(binding["key"]) if binding["device"] == "Keyboard" else None
        if code is not None:
            keys[code] = binding["key"]
    return found, keys


class KeyWatch:
    """A low-level keyboard hook that only notes the keys it's given (and the
    modifiers held with them). Keys still reach the game as normal."""

    def __init__(self, keys):
        self.keys = dict(keys)
        self.keys[VK_SCROLL] = "MARK"
        self.events = []
        self.down = set()
        self.thread_id = 0
        self._proc = HOOKPROC(self._hook)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)  # WM_QUIT

    def _run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        hook = user32.SetWindowsHookExW(13, self._proc, kernel32.GetModuleHandleW(None), 0)  # WH_KEYBOARD_LL
        message = wt.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        user32.UnhookWindowsHookEx(hook)

    def _hook(self, code, wparam, lparam):
        if code >= 0:
            info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk, pressed = int(info.vkCode), wparam in (0x0100, 0x0104)
            if vk in self.keys or vk in MODIFIER_KEYS:
                if pressed and vk not in self.down and vk in self.keys:
                    held = sorted(MODIFIER_KEYS[key] for key in self.down if key in MODIFIER_KEYS)
                    self.events.append({"t": time.time(), "kind": "key", "key": self.keys[vk], "modifiers": held})
                (self.down.add if pressed else self.down.discard)(vk)
        return user32.CallNextHookEx(None, code, wparam, lparam)


class PadWatch:
    """Start and Back on any XInput controller (polled; works with Elite in front)."""

    def __init__(self):
        self.get = None
        for name in ("xinput1_4", "xinput9_1_0", "xinput1_3"):
            try:
                self.get = getattr(ctypes.WinDLL(name), "XInputGetState")
                break
            except (OSError, AttributeError):
                continue
        self.held = [0, 0, 0, 0]

    def poll(self):
        events = []
        if self.get is None:
            return events
        for pad in range(4):
            state = XINPUT_STATE()
            if self.get(pad, ctypes.byref(state)) != 0:
                continue
            buttons = int(state.wButtons)
            for mask, name in XINPUT_BUTTONS.items():
                if buttons & mask and not self.held[pad] & mask:
                    events.append({"t": time.time(), "kind": "key", "key": name, "modifiers": [], "pad": pad})
            self.held[pad] = buttons
        return events


# -- the rest of the picture ----------------------------------------------------------------------
def front_window():
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    name = ""
    if handle:
        buffer = ctypes.create_unicode_buffer(520)
        size = wt.DWORD(len(buffer))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            name = Path(buffer.value).name
        kernel32.CloseHandle(handle)
    return hwnd, name


def pointer(hwnd):
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    user32.GetCursorInfo(ctypes.byref(info))
    clip, window = wt.RECT(), wt.RECT()
    user32.GetClipCursor(ctypes.byref(clip))
    user32.GetWindowRect(hwnd, ctypes.byref(window))
    screen = (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
              user32.GetSystemMetrics(76) + user32.GetSystemMetrics(78),
              user32.GetSystemMetrics(77) + user32.GetSystemMetrics(79))
    clipped = (clip.left, clip.top, clip.right, clip.bottom) != screen
    return {"showing": bool(info.flags & 1), "suppressed": bool(info.flags & 2),
            "cursor": int(info.hCursor or 0), "clipped": clipped,
            "clip_is_window": clipped and (clip.left, clip.top, clip.right, clip.bottom)
            == (window.left, window.top, window.right, window.bottom)}


class GameFiles:
    """Status.json and the journal's Music track, read as they change."""

    def __init__(self, folder=JOURNALS):
        self.folder = Path(folder)
        self.status_mtime = 0.0
        self.status = {}
        self.journal = None
        self.offset = 0
        self.music = ""

    def read(self):
        path = self.folder / "Status.json"
        try:
            mtime = path.stat().st_mtime
            if mtime != self.status_mtime:
                self.status_mtime = mtime
                self.status = json.loads(path.read_text(encoding="utf-8") or "{}")
        except (OSError, ValueError):
            pass
        journals = sorted(self.folder.glob("Journal.*.log"), key=lambda item: item.stat().st_mtime)
        if journals and journals[-1] != self.journal:
            self.journal, self.offset = journals[-1], 0
        if self.journal is not None:
            try:
                with open(self.journal, "rb") as handle:
                    handle.seek(self.offset)
                    data = handle.read()
                    self.offset += len(data)
            except OSError:
                data = b""
            for line in data.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("event") == "Music":
                    self.music = str(event.get("MusicTrack") or "")
        return {"gui_focus": self.status.get("GuiFocus", None), "flags": self.status.get("Flags", None),
                "flags2": self.status.get("Flags2", None), "music": self.music}


# -- commands --------------------------------------------------------------------------------------
def keys_command():
    found, codes = watched_keys()
    print("Presets in use:")
    for preset in found["presets"]:
        print(f"  {preset['name']:<22} {preset['file'] or 'NOT FOUND'}")
    print("Opens the pause menu:")
    for binding in found["keys"]:
        mods = " + ".join(binding["modifiers"] + [binding["key"]])
        watched = binding["device"] == "GamePad" or elite_bindings.virtual_key(binding["key"]) in codes
        print(f"  {binding['device']:<10} {mods:<34} {'watched' if watched else 'can not be watched (device)'}")


def watch_command():
    HERE.mkdir(exist_ok=True)
    found, codes = watched_keys()
    out = HERE / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    keys, pads, files = KeyWatch(codes), PadWatch(), GameFiles()
    keys.start()
    print(f"Recording to {out}\nTap Scroll Lock as the pause menu opens and again as it closes. Ctrl+C to stop.")
    last_state, next_sample = None, 0.0
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": "start", "t": time.time(), "bindings": found}) + "\n")
        try:
            while True:
                now = time.time()
                events = pads.poll()
                while keys.events:
                    events.append(keys.events.pop(0))
                if now >= next_sample or events:
                    next_sample = now + 0.1
                    hwnd, process = front_window()
                    state = {"elite": process.casefold().startswith("elitedangerous"), "process": process,
                             **pointer(hwnd), **files.read()}
                    if state != last_state:
                        handle.write(json.dumps({"kind": "state", "t": now, **state}) + "\n")
                        print(time.strftime("%H:%M:%S"), "state", {key: value for key, value in state.items()
                                                                   if last_state is None or value != last_state.get(key)})
                        last_state = state
                for event in events:
                    handle.write(json.dumps(event) + "\n")
                    print(time.strftime("%H:%M:%S"), "MARK" if event["key"] == "MARK" else f"key {event['key']}",
                          event.get("modifiers") or "")
                handle.flush()
                time.sleep(0.02)
        except KeyboardInterrupt:
            pass
        finally:
            keys.stop()
    print(f"Saved {out}. Next: python tools/pause_probe.py report")


def _load(path):
    records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    states = [record for record in records if record["kind"] == "state"]
    keys = [record for record in records if record["kind"] == "key"]
    return records, states, keys


def report_command(path=None):
    recordings = sorted(HERE.glob("*.jsonl"))
    path = Path(path) if path else (recordings[-1] if recordings else None)
    if path is None:
        print("Nothing recorded yet: python tools/pause_probe.py watch")
        return
    _records, states, keys = _load(path)
    marks = [key["t"] for key in keys if key["key"] == "MARK"]
    if not states:
        print("No samples in", path)
        return
    end = states[-1]["t"] + 0.1
    opened = [(marks[i], marks[i + 1] if i + 1 < len(marks) else end) for i in range(0, len(marks), 2)]

    def marked(t):
        return any(start <= t < stop for start, stop in opened)

    # The key model: an opening key with no panel or map open opens the menu;
    # pressed again (or a panel or map opening) closes it.
    opening = {binding["key"] for binding in _records[0].get("bindings", {}).get("keys", [])} if _records else set()
    events = sorted([("key", key["t"], key) for key in keys if key["key"] in opening]
                    + [("state", state["t"], state) for state in states], key=lambda item: item[1])
    key_open, focus, model = False, 0, []
    for kind, t, item in events:
        if kind == "state":
            focus = item.get("gui_focus") or 0
            if focus:
                key_open = False
        elif item.get("modifiers") == [] and not focus:
            key_open = not key_open
        model.append((t, key_open))

    def key_says(t):
        said = False
        for when, value in model:
            if when > t:
                break
            said = value
        return said

    signals = {
        "pointer showing (GuiFocus 0)": lambda s: s["showing"] and not s.get("gui_focus"),
        "pointer not held in the window": lambda s: not s["clip_is_window"],
        "pointer free (no clip at all)": lambda s: not s["clipped"],
        "keys (open/close toggle)": lambda s: key_says(s["t"]),
    }
    print(f"{path.name}: {len(opened)} marked pause menu visit(s), {len(states)} samples")
    print(f"{'signal':<34}{'in the menu':>14}{'elsewhere':>14}")
    for name, says in signals.items():
        inside = outside = inside_yes = outside_yes = 0.0
        for index, state in enumerate(states):
            if not state.get("elite"):
                continue
            span = (states[index + 1]["t"] if index + 1 < len(states) else end) - state["t"]
            yes = bool(says(state))
            if marked(state["t"]):
                inside, inside_yes = inside + span, inside_yes + span * yes
            else:
                outside, outside_yes = outside + span, outside_yes + span * yes
        right = f"{100 * inside_yes / inside:.0f}% said yes" if inside else "-"
        wrong = f"{100 * outside_yes / outside:.0f}% said yes" if outside else "-"
        print(f"{name:<34}{right:>14}{wrong:>14}")
    cursors = {}
    for state in states:
        if state.get("elite") and state["showing"]:
            cursors.setdefault(state["cursor"], set()).add("menu" if marked(state["t"]) else
                                                           f"GuiFocus {state.get('gui_focus')}")
    print("Pointers seen (handle: where):", {hex(key): sorted(value) for key, value in cursors.items()})
    print("Keys pressed:", [(time.strftime("%H:%M:%S", time.localtime(key["t"])), key["key"]) for key in keys])
    print("A good signal says yes near 100% in the menu and near 0% elsewhere.")


# -- selftest: it presses the keys itself -----------------------------------------------------------
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _Union(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _Union)]


EXTENDED_KEYS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F, 0xA3, 0xA5, 0x5B, 0x5C, 0x5D}


def press(binding):
    """Press and release a keyboard binding (its modifiers held round it), by
    scan code, which is what the game reads."""
    codes = [elite_bindings.virtual_key(name) for name in binding["modifiers"]] + [elite_bindings.virtual_key(binding["key"])]
    if None in codes:
        return False

    def send(vk, up):
        flags = 0x0008 | (0x0002 if up else 0) | (0x0001 if vk in EXTENDED_KEYS else 0)  # SCANCODE, KEYUP, EXTENDED
        item = INPUT(type=1)
        item.ki = KEYBDINPUT(0, user32.MapVirtualKeyW(vk, 0), flags, 0, 0)
        user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))
    for vk in codes:
        send(vk, False)
        time.sleep(0.03)
    time.sleep(0.08)
    for vk in reversed(codes):
        send(vk, True)
        time.sleep(0.03)
    return True


def keyboard_binding(action):
    found, _presets = elite_bindings.action_bindings(action)
    for binding in found:
        if binding["device"] == "Keyboard" and elite_bindings.virtual_key(binding["key"]) is not None \
                and all(elite_bindings.virtual_key(name) is not None for name in binding["modifiers"]):
            return binding
    return None


def selftest_command():
    if not elite_bindings.running_games():
        print("Elite isn't running. Start it, dock somewhere safe, and run this again.")
        return
    from PIL import ImageGrab

    escape = {"device": "Keyboard", "key": "Key_Escape", "modifiers": []}
    steps = [("in the game", None), ("pause menu", escape), ("closed", escape),
             ("pause menu again", escape), ("closed again", escape)]
    for action, label in (("GalaxyMapOpen", "galaxy map"), ("FocusLeftPanel", "left panel")):
        binding = keyboard_binding(action)
        if binding:
            steps += [(label, binding), (f"{label} closed", binding)]
        else:
            print(f"No keyboard key for {action} in your bindings: the {label} is left out.")
    folder = HERE / f"selftest-{time.strftime('%Y%m%d-%H%M%S')}"
    folder.mkdir(parents=True, exist_ok=True)
    print("Click into Elite now (docked somewhere safe), then keep your hands off the keyboard and mouse.")
    deadline = time.time() + 60
    while time.time() < deadline and not front_window()[1].casefold().startswith("elitedangerous"):
        time.sleep(0.2)
    if not front_window()[1].casefold().startswith("elitedangerous"):
        print("Elite never came to the front; nothing was pressed.")
        return
    for count in (3, 2, 1):
        print(f"  starting in {count}…")
        time.sleep(1)
    files, results = GameFiles(), []
    files.read()
    try:
        for number, (name, binding) in enumerate(steps, start=1):
            hwnd, process = front_window()
            if not process.casefold().startswith("elitedangerous"):
                print("Elite isn't in front any more; stopped.")
                break
            if binding:
                press(binding)
            time.sleep(2.5 if "map" in name else 1.5)
            samples = []
            for _ in range(5):
                samples.append({**pointer(hwnd), **files.read()})
                time.sleep(0.1)
            window = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(window))
            shot = folder / f"{number:02d}-{name.replace(' ', '-')}.png"
            try:
                picture = ImageGrab.grab(bbox=(window.left, window.top, window.right, window.bottom), all_screens=True)
                picture.thumbnail((1280, 1280))
                picture.save(shot)
            except Exception as exc:
                shot = f"screenshot failed: {exc}"
            result = {"step": name, "pressed": binding["key"] if binding else None, "samples": samples, "screenshot": str(shot)}
            results.append(result)
            last = samples[-1]
            print(f"  {name:<20} pointer {'showing' if last['showing'] else 'hidden ':<8} "
                  f"{'held in window' if last['clip_is_window'] else 'free' if not last['clipped'] else 'clipped':<15}"
                  f"cursor {hex(last['cursor']):<10} GuiFocus {last['gui_focus']}  music {last['music']}")
    finally:
        (folder / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"Saved {folder}. Look at the screenshots to see the menu opened when it says so.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("keys", "selftest", "watch", "report"))
    parser.add_argument("recording", nargs="?", help="report: a recording other than the newest")
    args = parser.parse_args(argv)
    if args.command == "keys":
        keys_command()
    elif args.command == "selftest":
        selftest_command()
    elif args.command == "watch":
        watch_command()
    else:
        report_command(args.recording)


if __name__ == "__main__":
    main()
