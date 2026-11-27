"""Free, safe keyboard keys for the controls the crew presses and you have
only on a pad or stick (or nowhere).

- Add, never replace: only the game's own empty slot is filled. Anything you
  bound, on any device, stays exactly as it is; a control with both slots
  taken is left for you.
- Never collide: a chord is used once, not if anything already has it.
- Never a modifier on its own, never the numpad (not every keyboard has one),
  never a modifier you bound on its own to something live alongside.
- Never the game menu's key, never Alt+F4, never the cargo eject.
- Only keys that sit in the same place on QWERTY, AZERTY and QWERTZ; on an
  AZERTY file, fewer still."""
from __future__ import annotations

from voidcompass.helm import rules
from voidcompass.helm.binds import KEYBOARD, MODIFIER_KEYS, PRIMARY, SECONDARY, is_azerty

_STABLE_LETTERS = ["Key_E", "Key_R", "Key_T", "Key_U", "Key_I", "Key_O", "Key_P", "Key_S", "Key_D", "Key_F", "Key_G",
                   "Key_H", "Key_J", "Key_K", "Key_L", "Key_B", "Key_N"]
_DIGITS = [f"Key_{n}" for n in range(10)]
_FUNCTION = [f"Key_F{n}" for n in range(1, 13)]
_VARIABLE = ["Key_Q", "Key_W", "Key_A", "Key_Z", "Key_M", "Key_Y", "Key_Minus", "Key_Equals", "Key_LeftBracket",
             "Key_RightBracket", "Key_BackSlash", "Key_SemiColon", "Key_Apostrophe", "Key_Comma", "Key_Period",
             "Key_Slash", "Key_Grave"]
# Right Alt is AltGr on AZERTY and QWERTZ: never a modifier here.
SAFE_MODIFIERS = ["Key_LeftControl", "Key_LeftShift", "Key_LeftAlt", "Key_RightShift"]

# Every key a commander can pick by hand (the numpad included).
ASSIGNABLE_KEYS = ([f"Key_{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + _DIGITS + _FUNCTION + [
    "Key_Escape", "Key_Tab", "Key_CapsLock", "Key_LeftShift", "Key_RightShift", "Key_LeftControl", "Key_RightControl",
    "Key_LeftAlt", "Key_RightAlt", "Key_Space", "Key_Enter", "Key_Backspace", "Key_Insert", "Key_Delete", "Key_Home",
    "Key_End", "Key_PageUp", "Key_PageDown", "Key_UpArrow", "Key_DownArrow", "Key_LeftArrow", "Key_RightArrow",
    "Key_Grave", "Key_Minus", "Key_Equals", "Key_LeftBracket", "Key_RightBracket", "Key_BackSlash", "Key_SemiColon",
    "Key_Apostrophe", "Key_Comma", "Key_Period", "Key_Slash", "Key_Hash"] + [f"Key_Numpad_{n}" for n in range(10)] + [
    "Key_Numpad_Add", "Key_Numpad_Subtract", "Key_Numpad_Multiply", "Key_Numpad_Divide", "Key_Numpad_Decimal",
    "Key_NumLock", "Key_ScrollLock", "Key_Pause", "Key_Apps"])


def base_keys(layout):
    return _STABLE_LETTERS + _FUNCTION if is_azerty(layout) else _STABLE_LETTERS + _DIGITS + _FUNCTION + _VARIABLE


def pool(layout):
    """Every chord auto-assign may use, in order: modifier combos first (so bare
    keys stay free for what you reach for most), then bare keys. Alt+F4 never."""
    keys = base_keys(layout)
    chords = [(key, modifier) for key in keys for modifier in SAFE_MODIFIERS]
    chords += [(key, None) for key in keys]
    return [(key, mod) for key, mod in chords if not rules.reserved_reason(key, [mod] if mod else [])]


def _taken(binds):
    taken = set()
    for action in binds.buttons:
        for slot in binds.slots(action):
            if slot.keyboard():
                mods = [k for d, k in slot.modifiers]
                taken.add((slot.key, mods[0] if len(mods) == 1 and mods[0] in MODIFIER_KEYS else None))
    return taken


def _bare_modifier_owners(binds):
    owners = {}
    for action in binds.buttons:
        for slot in binds.slots(action):
            if slot.device == KEYBOARD and slot.key in MODIFIER_KEYS and not slot.modifiers:
                owners.setdefault(slot.key, set()).add(action)
    return owners


def _writable_position(binds, action):
    pair = binds.buttons.get(action) or {}
    for position in (PRIMARY, SECONDARY):
        slot = pair.get(position)
        if slot is not None and slot.writable_empty():
            return position
    return None


def can_assign(binds, action):
    return action != rules.GAME_MENU and action not in rules.LEFT_TO_THE_COMMANDER \
        and _writable_position(binds, action) is not None


def plan(binds, wanted, also_taken=(), usable=None):
    """Keys for the wanted controls that have none we can press.
    -> {"edits": [{action, position, key, modifier}], "skipped": [{action, reason}]}.
    ``also_taken``: chords used in the other files the game has active;
    ``usable(key, modifier)``: whether whoever presses them can (the crew's presser)."""
    chords = [chord for chord in pool(binds.layout) if usable is None or usable(*chord)]
    taken = _taken(binds) | set(also_taken)
    menu = rules.game_menu_keys(binds)
    owners = _bare_modifier_owners(binds)
    edits, skipped = [], []
    for action in sorted(set(wanted), key=str.casefold):
        if action not in binds.buttons:
            skipped.append({"action": action, "reason": "absent"})
            continue
        if rules.keyboard_bound(binds, action):
            continue
        if action == rules.GAME_MENU:
            skipped.append({"action": action, "reason": "game_menu"})
            continue
        if action in rules.LEFT_TO_THE_COMMANDER:
            skipped.append({"action": action, "reason": "on_purpose"})
            continue
        position = _writable_position(binds, action)
        if position is None:
            slots = binds.slots(action)
            both = len(slots) == 2 and all(not slot.writable_empty() for slot in slots)
            skipped.append({"action": action, "reason": "both_slots" if both else "no_slot"})
            continue
        shadowed = {key for key, actions in owners.items()
                    if any(other != action and not rules.safe_shadow(action, other) for other in actions)}
        chosen = None
        for key, modifier in chords:
            if (key, modifier) in taken or key in menu or key in MODIFIER_KEYS or key.startswith("Key_Numpad"):
                continue
            if modifier and modifier in shadowed:
                continue
            chosen = (key, modifier)
            break
        if chosen is None:
            skipped.append({"action": action, "reason": "no_free_key"})
            continue
        taken.add(chosen)
        edits.append({"action": action, "position": position, "key": chosen[0], "modifier": chosen[1]})
    return {"edits": edits, "skipped": skipped}


def taken_chords(binds):
    """The keyboard chords a file uses, for planning against another file."""
    return _taken(binds)


SKIP_REASONS = {
    "absent": "isn't in this binds file",
    "game_menu": "left unbound on purpose: Escape opens the game menu anyway",
    "on_purpose": "left for you to bind by hand (it can't be undone)",
    "both_slots": "both of its slots are taken: free one in Helm and try again",
    "no_slot": "has no empty slot that can be filled",
    "no_free_key": "no free, safe key was left",
}
