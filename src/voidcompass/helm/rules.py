"""What's wrong with a binds file: two controls on one input, a key the system
or the game menu takes, and what the crew needs that has no key.

Elite fires a binding on its exact chord (the main input and exactly its
modifiers): bare 6 and Ctrl+Alt+6 are two controls. Two slots clash when they
hold the same chord, with the same tap or hold, in controls that are live
together. The one exception is a modifier shadow: a chord whose modifier is
also bound on its own, which fires first as the modifier goes down.

Which controls are live together: only one of ship, SRV and on foot is ever
flown, the interface keys belong to the focused panel, and the cameras, the
scanners, the wheels and the like are screens of their own. Except where the
game itself is known to fire both (the map camera and the panel keys, Select
and quick comms, the panel and map keys and the panel keys), or where its own
rebind check complains."""
from __future__ import annotations

from voidcompass.helm import catalog
from voidcompass.helm.binds import KEYBOARD, MODIFIER_KEYS, POSITIONS, layout_names, is_azerty

GAME_MENU = "Pause"
# Ejecting the cargo can't be undone: only ever bound by hand.
LEFT_TO_THE_COMMANDER = {"EjectAllCargo", "EjectAllCargo_Buggy"}

_QUICK_COMMS = {"QuickCommsPanel", "QuickCommsPanel_Buggy", "QuickCommsPanel_Humanoid"}
_INTERFACE_SWITCH = {"FocusLeftPanel", "FocusLeftPanel_Buggy", "FocusCommsPanel", "FocusCommsPanel_Buggy",
                     "FocusCommsPanel_Humanoid", "FocusRadarPanel", "FocusRadarPanel_Buggy", "FocusRightPanel",
                     "FocusRightPanel_Buggy", "GalaxyMapOpen", "GalaxyMapOpen_Buggy", "GalaxyMapOpen_Humanoid",
                     "SystemMapOpen", "SystemMapOpen_Buggy", "SystemMapOpen_Humanoid"}
_INTERFACE_MODE = {"UI_Up", "UI_Down", "UI_Left", "UI_Right", "UI_Select", "UI_Back", "UI_Toggle",
                   "CycleNextPanel", "CyclePreviousPanel", "CycleNextPage", "CyclePreviousPage"}
_MODAL_GROUPS = {"Full Spectrum System Scanner", "Detailed Surface Scanner", "System Colonisation Facility Placement"}
_CURATED = {}


def _pair(a, b):
    return (a, b) if a <= b else (b, a)


def _curate(a, b, text):
    _CURATED[_pair(a, b)] = text


_curate("DeployHardpointToggle", "LandingGearToggle", "Deploying hardpoints will also toggle the landing gear")
_curate("DeployHardpointToggle", "ToggleCargoScoop", "Deploying hardpoints will also toggle the cargo scoop")
_curate("LandingGearToggle", "ToggleCargoScoop", "Toggling the landing gear will also toggle the cargo scoop")
_curate("Supercruise", "Hyperspace", "Supercruise and hyperspace share a key: which jump you get depends on the target")
for _comms in _QUICK_COMMS:
    _curate("UI_Select", _comms, "Select and the quick comms panel share a key: every selection also opens the chat "
                                 "box, which then takes the keys that follow and can send them")

# Frontier's own rebind check: which groups it warns about sharing a key, tested
# pair by pair in game (2026-07-30). It only ever adds a conflict.
_GAME_WARNS = set()


def _warn(section, group, *others):
    for other in others:
        _GAME_WARNS.add((section,) + _pair(group, other))


_warn("general", "Interface Mode", "Holo-Me", "Playlist", "Store Camera")
_warn("general", "Galaxy Map", "Playlist")
_warn("general", "Camera Suite", "Holo-Me", "Playlist", "Store Camera")
_warn("general", "Free Camera", "Holo-Me", "Playlist", "Store Camera")
_warn("general", "Holo-Me", "Playlist")
_warn("ship", "Mouse Controls", "Flight Rotation", "Flight Thrust", "Alternate Flight Controls", "Flight Throttle",
      "Flight Landing Overrides", "Flight Miscellaneous", "Targeting", "Weapons", "Cooling", "Miscellaneous",
      "Mode Switches", "Multi-Crew", "Fighter Orders")
_warn("ship", "Flight Rotation", "Flight Thrust", "Flight Throttle", "Flight Miscellaneous", "Targeting", "Weapons",
      "Cooling", "Miscellaneous", "Mode Switches", "Multi-Crew")
_warn("ship", "Flight Thrust", "Flight Throttle", "Flight Miscellaneous", "Targeting", "Weapons", "Cooling",
      "Mode Switches", "Multi-Crew")
_warn("ship", "Alternate Flight Controls", "Flight Miscellaneous", "Targeting", "Weapons", "Cooling", "Miscellaneous",
      "Mode Switches", "Multi-Crew")
_warn("ship", "Flight Throttle", "Flight Miscellaneous", "Targeting", "Weapons", "Cooling", "Miscellaneous",
      "Mode Switches", "Multi-Crew")
_warn("ship", "Flight Landing Overrides", "Mode Switches", "Multi-Crew")
_warn("ship", "Flight Miscellaneous", "Targeting", "Weapons", "Cooling", "Miscellaneous", "Mode Switches", "Multi-Crew")
_warn("ship", "Targeting", "Weapons", "Cooling", "Miscellaneous", "Mode Switches", "Multi-Crew")
_warn("ship", "Weapons", "Cooling", "Miscellaneous", "Mode Switches", "Multi-Crew", "Detailed Surface Scanner")
_warn("ship", "Cooling", "Miscellaneous", "Mode Switches", "Multi-Crew")
_warn("ship", "Miscellaneous", "Mode Switches", "Multi-Crew")
_warn("ship", "Mode Switches", "Headlook Mode", "Multi-Crew", "Detailed Surface Scanner")
_warn("ship", "Headlook Mode", "Multi-Crew")
_warn("srv", "Driving", "Driving Targeting", "Drive Throttle", "Driving Miscellaneous", "Driving Mode Switches")
_warn("srv", "Driving Targeting", "Drive Throttle", "Driving Miscellaneous", "Driving Mode Switches")
_warn("srv", "Driving Turret Controls", "Driving Mode Switches")
_warn("srv", "Drive Throttle", "Driving Miscellaneous", "Driving Mode Switches")
_warn("srv", "Driving Miscellaneous", "Driving Mode Switches")
_warn("onfoot", "On Foot", "On Foot Mode Switches", "On Foot Emotes")
_warn("onfoot", "On Foot Mode Switches", "On Foot Emotes")


def game_warns(a, b):
    """Would the game's own rebind check complain about these two sharing a key?"""
    ca, cb = catalog.lookup(a), catalog.lookup(b)
    return ca.section == cb.section and bool(ca.group) and bool(cb.group) and \
        (ca.section,) + _pair(ca.group, cb.group) in _GAME_WARNS


# -- contexts ----------------------------------------------------------------------
def _map_camera(action):
    return action.startswith(("CamTranslate", "CamPitch", "CamYaw", "CamZoom")) or action == "GalaxyMapHome"


def _ui_navigation(action):
    return action.startswith("UI_")


def _map_vs_ui(a, b):
    return (_map_camera(a) and _ui_navigation(b)) or (_map_camera(b) and _ui_navigation(a))


def _select_vs_comms(a, b):
    return (a == "UI_Select" and b in _QUICK_COMMS) or (b == "UI_Select" and a in _QUICK_COMMS)


def _switch_vs_ui(a, b):
    return (a in _INTERFACE_SWITCH and _ui_navigation(b)) or (b in _INTERFACE_SWITCH and _ui_navigation(a))


def context_of(action):
    """ui, buggy, humanoid or ship: only one is ever live."""
    if action in _INTERFACE_MODE or _ui_navigation(action):
        return "ui"
    section = catalog.lookup(action).section
    if section == "srv":
        return "buggy"
    if section == "onfoot":
        return "humanoid"
    if section == "ship":
        return "ship"
    if "Buggy" in action:
        return "buggy"
    if "Humanoid" in action:
        return "humanoid"
    return "ship"


def _sub_state(action):
    """Live only inside a screen of its own: cameras, the scanners, the wheels, the store, Galnet audio..."""
    group = catalog.lookup(action).group
    return ("Cam" in action or action == "GalaxyMapHome" or "Wheel" in action or action.startswith("HumanoidEmote")
            or action.startswith(("Vanity", "GalnetAudio", "MultiCrew", "Store")) or (group in _MODAL_GROUPS))


def blocking(a, b):
    """A clash that stops keyboard menu navigation (the crew's map and panel walks) outright."""
    return _map_vs_ui(a, b) or _select_vs_comms(a, b) or _switch_vs_ui(a, b)


def safe_shadow(a, b):
    if blocking(a, b):
        return False
    if _sub_state(a) or _sub_state(b):
        return True
    return context_of(a) != context_of(b)


def safe_overlap(a, b):
    return not game_warns(a, b) and safe_shadow(a, b)


def ship_twin(action):
    """"ToggleCargoScoop_Buggy" -> "ToggleCargoScoop": the same control in the ship."""
    return action[:-len("_Buggy")] if action and action.endswith("_Buggy") else None


def describe(a, b):
    curated = _CURATED.get(_pair(a, b))
    if curated:
        return curated
    la, lb = catalog.lookup(a).name, catalog.lookup(b).name
    if _map_vs_ui(a, b):
        return f"{la} and {lb} share a key: in the galaxy and system maps both are live, so map movement and panel " \
               "moves fight each other"
    if _switch_vs_ui(a, b):
        return f"{la} and {lb} share a key: the panel and map keys stay live while a panel is open, so moving " \
               "through a panel also switches it"
    return f"{la} and {lb} share a key and may interfere"


def describe_shadow(chord_action, bare_action, modifier):
    bare = catalog.lookup(bare_action).name
    return f"{catalog.lookup(chord_action).name} holds {token_label(modifier)} as a modifier, and that input on its " \
           f"own is {bare}: pressing the combination fires {bare} too"


# -- chords ------------------------------------------------------------------------
def token(device, key):
    """One input as the scan names it: a key bare, anything else DEVICE/TOKEN in capitals."""
    return key if device == KEYBOARD else f"{device}/{key}".upper()


def chord_of(slot):
    """The set of inputs a slot holds down, or an empty set."""
    if slot is None or not slot.assigned():
        return frozenset()
    keys = {token(d, k) for d, k in slot.modifiers if k}
    keys.add(token(slot.device, slot.key))
    return frozenset(keys)


def _is_modifier_key(key):
    return key in MODIFIER_KEYS


def _shadowed(chord_a, mods_a, chord_b, mods_b):
    def held(bare, chord, chord_mods):
        key = next(iter(bare))
        if key not in chord:
            return None
        if _is_modifier_key(key):
            return key
        return key if "/" in key and key in chord_mods else None
    if len(chord_a) == 1 and len(chord_b) > 1:
        return held(chord_a, chord_b, mods_b)
    if len(chord_b) == 1 and len(chord_a) > 1:
        return held(chord_b, chord_a, mods_a)
    return None


def _entries(binds):
    rows = []
    for action in sorted(binds.buttons):
        for slot in binds.slots(action):
            chord = chord_of(slot)
            if chord:
                rows.append((action, slot.position, slot.hold, frozenset(token(d, k) for d, k in slot.modifiers if k),
                             slot.device != KEYBOARD, chord))
    return rows


def scan(binds):
    """Every clash in a binds file: [{a, b, chord_a, chord_b, text, blocking, shadow}]."""
    rows = _entries(binds)
    found, seen = [], set()
    for i, (a, pos_a, hold_a, mods_a, pad_a, chord_a) in enumerate(rows):
        for b, pos_b, hold_b, mods_b, _pad_b, chord_b in rows[i + 1:]:
            if a == b:
                continue
            same = chord_a == chord_b
            if same and hold_a != hold_b:
                continue
            shadow = None if same else _shadowed(chord_a, mods_a, chord_b, mods_b)
            if not same and shadow is None:
                continue
            if (safe_overlap(a, b) if same else safe_shadow(a, b)):
                continue
            wide = chord_a if len(chord_a) >= len(chord_b) else chord_b
            if (a, b, wide) in seen:
                continue
            seen.add((a, b, wide))
            if same:
                text = describe(a, b)
            elif wide is chord_a:
                text = describe_shadow(a, b, shadow)
            else:
                text = describe_shadow(b, a, shadow)
            found.append({"a": a, "b": b, "chord_a": sorted(chord_a), "chord_b": sorted(chord_b), "text": text,
                          "blocking": same and not pad_a and blocking(a, b), "shadow": not same,
                          "position_a": pos_a, "position_b": pos_b})
    return found


def holder_of(binds, action, device, key, modifiers=(), hold=False):
    """The control that already takes this input, judged as the scan judges, or None."""
    if not device or not key:
        return None
    candidate_mods = frozenset(token(d, k) for d, k in modifiers)
    candidate = candidate_mods | {token(device, key)}
    for other, _pos, other_hold, other_mods, _pad, chord in _entries(binds):
        if other == action:
            continue
        same = candidate == chord
        if not same and _shadowed(candidate, candidate_mods, chord, other_mods) is None:
            continue
        if same and bool(hold) != other_hold:
            continue
        if safe_overlap(action, other) if same else safe_shadow(action, other):
            continue
        return other
    return None


def twins(binds):
    """Ship and SRV twins on different keys ({ship, srv}): not a clash, a nudge."""
    chords = {}
    for action in binds.buttons:
        for slot in binds.slots(action):
            chord = chord_of(slot)
            if chord:
                chords.setdefault(action, set()).add(chord)
    found = []
    for action in sorted(chords):
        ship = ship_twin(action)
        if ship and ship in chords and chords[ship].isdisjoint(chords[action]):
            found.append({"ship": ship, "srv": action})
    return found


# -- reserved keys -----------------------------------------------------------------
def game_menu_keys(binds):
    """The keyboard keys on the game menu (Pause): the menu opens on that key however it's modified."""
    keys = set()
    for slot in binds.slots(GAME_MENU):
        if slot.keyboard():
            keys.add(slot.key)
    return keys


def reserved_reason(key, modifiers, menu_keys=()):
    """Why a keyboard chord mustn't be used, or "": Alt+F4 closes the game; the game-menu key opens the menu."""
    keys = {key, *modifiers}
    if keys & {"Key_LeftAlt", "Key_RightAlt"} and "Key_F4" in keys:
        return "closes the game window (Alt+F4)"
    if key in set(menu_keys):
        return "is the game menu's key, so it pauses the game and opens the menu"
    return ""


def reserved(binds):
    """Controls already on a reserved chord: [{action, position, chord, reason, fix}]."""
    menu = game_menu_keys(binds)
    found = []
    for action in sorted(binds.buttons):
        if action == GAME_MENU:
            continue
        for slot in binds.slots(action):
            if not slot.keyboard():
                continue
            mods = [k for d, k in slot.modifiers]
            reason = reserved_reason(slot.key, mods, menu)
            if reason:
                fix = ("clear the Game Menu binding: Escape opens that menu anyway" if slot.key in menu
                       else "move this control to another key")
                found.append({"action": action, "position": slot.position, "chord": sorted({slot.key, *mods}),
                              "reason": reason, "fix": fix})
    return found


def layout_invalid(binds):
    """Keyboard slots on a key the file's layout can't name (Key_9 in an AZERTY file)."""
    if not is_azerty(binds.layout):
        return []
    return [{"action": action, "position": slot.position, "key": slot.key}
            for action in sorted(binds.buttons) for slot in binds.slots(action)
            if slot.keyboard() and not layout_names(binds.layout, slot.key)]


def keyboard_bound(binds, action):
    return any(slot.keyboard_usable(binds.layout) for slot in binds.slots(action))


def missing(binds, wanted):
    """Of the controls wanted (the crew's), those with no key we can press: [{action, why}]."""
    rows = []
    for action in sorted(set(wanted), key=str.casefold):
        if action not in binds.buttons:
            rows.append({"action": action, "why": "absent"})
        elif not keyboard_bound(binds, action):
            slots = binds.slots(action)
            on_device = any(slot.assigned() for slot in slots)
            rows.append({"action": action, "why": "device_only" if on_device else "unbound"})
    return rows


# -- names -------------------------------------------------------------------------
_KEY_WORDS = {"LeftControl": "Left Ctrl", "RightControl": "Right Ctrl", "LeftShift": "Left Shift",
              "RightShift": "Right Shift", "LeftAlt": "Left Alt", "RightAlt": "Right Alt", "LeftArrow": "←",
              "RightArrow": "→", "UpArrow": "↑", "DownArrow": "↓", "SemiColon": ";", "Apostrophe": "'",
              "Comma": ",", "Period": ".", "Slash": "/", "BackSlash": "\\", "Minus": "-", "Equals": "=",
              "LeftBracket": "[", "RightBracket": "]", "Grave": "`", "Hash": "#", "PageUp": "Page Up",
              "PageDown": "Page Down", "CapsLock": "Caps Lock", "NumLock": "Num Lock", "ScrollLock": "Scroll Lock",
              "Backspace": "Backspace", "Enter": "Enter", "Space": "Space", "Escape": "Esc", "Tab": "Tab",
              "Insert": "Insert", "Delete": "Delete", "Home": "Home", "End": "End", "Pause": "Pause", "Apps": "Menu",
              "LeftWin": "Left Win", "RightWin": "Right Win"}


def key_name(key):
    """"Key_LeftControl" -> "Left Ctrl"; "Key_Numpad_4" -> "Num 4"; others as written."""
    key = str(key or "")
    if key.startswith("Key_"):
        rest = key[4:]
        if rest.startswith("Numpad_"):
            tail = rest[7:]
            return "Num " + {"Add": "+", "Subtract": "-", "Multiply": "*", "Divide": "/", "Decimal": ".",
                             "Enter": "Enter"}.get(tail, tail)
        return _KEY_WORDS.get(rest, rest)
    return key


_PAD_WORDS = {"facedown": "A", "faceright": "B", "faceleft": "X", "faceup": "Y", "lbumper": "LB", "rbumper": "RB",
              "lthumb": "LS", "rthumb": "RS", "back": "Back", "start": "Start", "dpadup": "D-pad ↑",
              "dpaddown": "D-pad ↓", "dpadleft": "D-pad ←", "dpadright": "D-pad →", "ltrigger": "LT", "rtrigger": "RT",
              "lstickx": "Left stick X", "lsticky": "Left stick Y", "rstickx": "Right stick X", "rsticky": "Right stick Y",
              "a": "A", "b": "B", "x": "X", "y": "Y"}
_HAT = {"up": "↑", "down": "↓", "left": "←", "right": "→"}


def input_label(device, key, device_label=None, button_labels=None):
    """One input as people say it: "Left Ctrl", "Mouse 2", "Pad A", "X52 7", "X52 hat ↑", "X52 Y axis+".
    ``button_labels`` {(device, key) casefolded: label}: a .buttonMap's own name for it wins."""
    import re
    device, key = str(device or ""), str(key or "")
    own = (button_labels or {}).get((device.casefold(), key.casefold()))
    if own:
        return f"{device_label or device} {own}"
    if device == KEYBOARD:
        return key_name(key)
    if device == "Mouse":
        match = re.fullmatch(r"Mouse_(\d+)", key)
        if match:
            return {"1": "Left click", "2": "Right click", "3": "Middle click"}.get(match.group(1), f"Mouse {match.group(1)}")
        return {"Pos_Mouse_ZAxis": "Wheel up", "Neg_Mouse_ZAxis": "Wheel down", "Mouse_XAxis": "Mouse X",
                "Mouse_YAxis": "Mouse Y", "Mouse_ZAxis": "Wheel"}.get(key, key)
    pad = re.fullmatch(r"(?:Pos_|Neg_)?(?:GamePad|Pad)_(\w+)", key)
    if pad:
        word = _PAD_WORDS.get(pad.group(1).casefold(), pad.group(1))
        sign = "+" if key.startswith("Pos_") and "Stick" in key else "−" if key.startswith("Neg_") else ""
        return f"Pad {word}{sign}"
    name = device_label or device
    joy = re.fullmatch(r"(Pos_|Neg_)?Joy_(\w+)", key, re.I)
    if not joy:
        return f"{name} {key}".strip()
    sign, rest = (joy.group(1) or "").casefold(), joy.group(2)
    if rest.isdigit():
        return f"{name} {rest}"
    hat = re.fullmatch(r"POV(\d)(Up|Down|Left|Right)", rest, re.I)
    if hat:
        return f"{name} hat{'' if hat.group(1) == '1' else hat.group(1)} {_HAT[hat.group(2).lower()]}"
    axis = rest[:-4].upper() if rest.casefold().endswith("axis") else rest
    return f"{name} {axis} axis{'+' if sign == 'pos_' else '−' if sign == 'neg_' else ''}"


def token_label(scan_token):
    """A scan token ("Key_LeftShift", "GAMEPAD/GAMEPAD_FACEDOWN") as people say it."""
    if "/" not in scan_token:
        return key_name(scan_token)
    device, _, key = scan_token.partition("/")
    if device.casefold() in ("gamepad", "xb360 pad"):
        return input_label("GamePad", key.title().replace("Gamepad_", "GamePad_"))
    return input_label(device, key.title())


def slot_label(slot, device_label=None, button_labels=None):
    """"Left Shift + F9", "Pad LB + A"."""
    if slot is None or not slot.assigned():
        return ""
    name = device_label if callable(device_label) else (lambda _device: None)
    parts = [input_label(d, k, name(d), button_labels) for d, k in slot.modifiers]
    parts.append(input_label(slot.device, slot.key, name(slot.device), button_labels))
    text = " + ".join(parts)
    return text
