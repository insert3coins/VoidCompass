"""A .binds file: reading every slot, axis and setting it holds, and changing
one of them without touching any other byte.

The writer edits the text, never a re-serialised tree, so the rest of the file
stays exactly as the game wrote it (a UTF-8 BOM and line endings included).
It refuses, and changes nothing, when a slot holds structure it doesn't know.
Nothing here reads or writes a file: it takes bytes and gives bytes back."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

KEYBOARD, MOUSE, NO_DEVICE = "Keyboard", "Mouse", "{NoDevice}"
PRIMARY, SECONDARY = "Primary", "Secondary"
POSITIONS = (PRIMARY, SECONDARY)

# What a write came to. Anything but SAVED leaves the bytes as they were.
SAVED, NO_CHANGE, UNKNOWN_KEY, NOT_FOUND, UNSUPPORTED = "saved", "no_change", "unknown_key", "not_found", "unsupported"

MODIFIER_KEYS = ("Key_LeftControl", "Key_RightControl", "Key_LeftShift", "Key_RightShift", "Key_LeftAlt", "Key_RightAlt")
_RESERVED_DEVICES = {"keyboard", "mouse", "{nodevice}"}
_DEVICE_NAME = re.compile(r"[\w.:-]+")
_KEYBOARD_TOKEN = re.compile(r"Key_[^\s\"'<>&]+")
_MOUSE_TOKEN = re.compile(r"Mouse_[1-9][0-9]*|(?:Pos|Neg)_Mouse_ZAxis")
_AXIS = r"(?:X|Y|Z|RX|RY|RZ|U|V)Axis"
_PAD = (r"Pos_GamePad_(?:LTrigger|RTrigger)"
        r"|GamePad_(?:Face(?:Down|Right|Left|Up)|Back|Start|LBumper|RBumper|LThumb|RThumb|DPad(?:Up|Right|Down|Left))")
_CONTROLLER_BUTTON = re.compile(rf"Joy_[1-9][0-9]*|Joy_POV[1-4](?:Up|Down|Left|Right)|(?:Pos|Neg)_Joy_{_AXIS}|{_PAD}")
_CONTROLLER_AXIS = re.compile(rf"Joy_{_AXIS}")
_SETTING_VALUE = re.compile(r"[^\"'<>&]*")
_SLOT_CHILD = re.compile(r"<(?![/!?])([A-Za-z_][A-Za-z0-9_.:-]*)(?=[\s>/])")
_LAYOUT = re.compile(r"<KeyboardLayout>\s*([^<]*?)\s*</KeyboardLayout>")
_VALUE_ATTR = re.compile(r"(?<![A-Za-z0-9_.:-])Value\s*=\s*([\"'])(.*?)\1")
_BOM = b"\xef\xbb\xbf"

# Elite names a key by the character it types unshifted: an AZERTY file has no
# Key_1..Key_0 or Key_Period (those need Shift there), so a chord on one of these
# names is a key the game can't tell from its neighbours.
_AZERTY_TAGS = {"fr-fr", "fr-be"}
_NOT_ON_AZERTY = {"Key_0", "Key_1", "Key_2", "Key_3", "Key_4", "Key_5", "Key_6", "Key_7", "Key_8", "Key_9",
                  "Key_Period", "Key_Slash", "Key_LeftBracket", "Key_RightBracket", "Key_BackSlash", "Key_Grave"}


def is_azerty(layout):
    return str(layout or "").strip().casefold() in _AZERTY_TAGS


def layout_names(layout, key):
    """False when a file of this layout can't name ``key`` as a key of its own."""
    return not is_azerty(layout) or key not in _NOT_ON_AZERTY


def is_reserved_device(device):
    return str(device or "").casefold() in _RESERVED_DEVICES


def is_device_name(device):
    """A controller's DeviceMappings name or hardware id: XML-name characters, not Keyboard/Mouse/{NoDevice}."""
    return bool(device) and bool(_DEVICE_NAME.fullmatch(device)) and not is_reserved_device(device)


def is_button_input(device, key):
    """What a button slot (or a modifier) can hold: a key, a mouse button or
    wheel direction, a controller's button, hat or axis direction. Never a whole axis."""
    if device == KEYBOARD:
        return bool(_KEYBOARD_TOKEN.fullmatch(key or ""))
    if device == MOUSE:
        return bool(_MOUSE_TOKEN.fullmatch(key or ""))
    return is_device_name(device) and bool(_CONTROLLER_BUTTON.fullmatch(key or ""))


def is_axis_input(device, key):
    return is_device_name(device) and bool(_CONTROLLER_AXIS.fullmatch(key or ""))


# -- reading ---------------------------------------------------------------------
class Slot:
    """One Primary or Secondary slot."""
    __slots__ = ("device", "key", "modifiers", "hold", "position")

    def __init__(self, device, key, modifiers=(), hold=False, position=PRIMARY):
        self.device = str(device or "")
        self.key = str(key or "")
        self.modifiers = tuple((str(d or ""), str(k or "")) for d, k in modifiers)
        self.hold = bool(hold)
        self.position = position

    def assigned(self):
        return self.device not in ("", NO_DEVICE) and self.device.casefold() != NO_DEVICE.casefold() \
            and bool(self.key) and self.key != "Key_"

    def empty(self):
        return not self.assigned()

    def writable_empty(self):
        """The game's own empty slot, the one thing an automatic write may fill."""
        return self.device == NO_DEVICE and not self.key and not self.modifiers

    def keyboard(self):
        return self.device == KEYBOARD and bool(self.key) and self.key != "Key_"

    def keyboard_usable(self, layout=""):
        """A key we can press: on the keyboard, every modifier too, and a name the file's layout has."""
        return self.keyboard() and all(d == KEYBOARD for d, _k in self.modifiers) and layout_names(layout, self.key)

    def as_dict(self):
        return {"device": self.device, "key": self.key, "modifiers": [list(m) for m in self.modifiers],
                "hold": self.hold, "position": self.position}

    def __eq__(self, other):
        return isinstance(other, Slot) and (self.device, self.key, frozenset(self.modifiers), self.hold) == \
            (other.device, other.key, frozenset(other.modifiers), other.hold)

    def __hash__(self):
        return hash((self.device, self.key, frozenset(self.modifiers), self.hold))

    def __repr__(self):
        return f"Slot({self.device!r}, {self.key!r}, {self.modifiers!r}, hold={self.hold})"


class Axis:
    __slots__ = ("tag", "device", "key", "inverted", "deadzone", "editable")

    def __init__(self, tag, device, key, inverted, deadzone, editable):
        self.tag, self.device, self.key = tag, str(device or ""), str(key or "")
        self.inverted, self.deadzone, self.editable = bool(inverted), float(deadzone), bool(editable)

    def bound(self):
        return self.device not in ("", NO_DEVICE) and bool(self.key)

    def as_dict(self):
        return {"device": self.device, "key": self.key, "inverted": self.inverted,
                "deadzone": round(self.deadzone, 4), "editable": self.editable, "bound": self.bound()}


class BindsFile:
    """What a .binds file holds."""

    def __init__(self):
        self.preset_name = ""
        self.major = self.minor = ""
        self.layout = ""
        self.buttons = {}       # tag -> {"Primary": Slot|None, "Secondary": Slot|None}
        self.toggle_on = {}     # tag -> its <ToggleOn Value>, where one is
        self.axes = {}          # tag -> Axis
        self.settings = {}      # tag -> {"value", "editable"}
        self.order = []         # every top-level tag, in file order, once
        self.repeated = set()

    def slots(self, tag):
        pair = self.buttons.get(tag) or {}
        return [slot for slot in (pair.get(PRIMARY), pair.get(SECONDARY)) if slot is not None]


def _text(data):
    """The file as text, and whether it had a BOM. Bad UTF-8 raises ValueError."""
    if isinstance(data, str):
        return data, False
    bom = data.startswith(_BOM)
    return (data[3:] if bom else data).decode("utf-8"), bom


def _bytes(text, bom):
    body = text.encode("utf-8")
    return _BOM + body if bom else body


def parse(data):
    """A .binds file (bytes or text) -> BindsFile. Not a binds file: ValueError."""
    try:
        text, _bom = _text(data)
    except UnicodeDecodeError as exc:
        raise ValueError(f"not UTF-8 ({exc.reason})") from None
    # A binds file never declares a DTD; one that does isn't parsed at all.
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
        raise ValueError("holds a DTD")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"not a valid bindings file ({exc})") from None
    binds = BindsFile()
    binds.preset_name = root.get("PresetName") or ""
    binds.major, binds.minor = root.get("MajorVersion") or "", root.get("MinorVersion") or ""
    children = list(root)
    seen = set()
    for element in children:
        if element.tag in seen:
            binds.repeated.add(element.tag)
        else:
            seen.add(element.tag)
            binds.order.append(element.tag)
    for element in children:
        tag = element.tag
        if tag == "KeyboardLayout":
            binds.layout = binds.layout or (element.text or "").strip()
            continue
        kids = list(element)
        names = [kid.tag for kid in kids]
        if PRIMARY in names or SECONDARY in names:
            if tag in binds.buttons:
                continue
            pair = {}
            for position in POSITIONS:
                node = element.find(position)
                pair[position] = None if node is None else _slot(node, position)
            binds.buttons[tag] = pair
            toggle = element.find("ToggleOn")
            if toggle is not None:
                binds.toggle_on[tag] = toggle.get("Value") or ""
        elif "Binding" in names:
            if tag not in binds.axes:
                binds.axes[tag] = _axis(tag, kids, tag not in binds.repeated)
        elif not kids and element.get("Value") is not None:
            if tag not in binds.settings:
                copies = [node for node in children if node.tag == tag]
                plain = all(not list(node) and list(node.attrib) == ["Value"] for node in copies)
                binds.settings[tag] = {"value": element.get("Value") or "", "editable": plain}
    return binds


def _slot(node, position):
    hold = node.get("Hold") == "1" or any(kid.tag == "Hold" and kid.get("Value") == "1" for kid in node)
    modifiers = [(kid.get("Device"), kid.get("Key")) for kid in node if kid.tag == "Modifier"]
    return Slot(node.get("Device"), node.get("Key"), modifiers, hold, position)


def _axis(tag, kids, once):
    binding = next(kid for kid in kids if kid.tag == "Binding")
    inverted = [kid for kid in kids if kid.tag == "Inverted"]
    deadzone = [kid for kid in kids if kid.tag == "Deadzone"]
    zone = None
    if len(deadzone) == 1:
        try:
            zone = float(deadzone[0].get("Value"))
        except (TypeError, ValueError):
            zone = None
    editable = (once and len(kids) == 3 and sum(kid.tag == "Binding" for kid in kids) == 1 and len(inverted) == 1
                and not list(binding) and zone is not None and 0.0 <= zone <= 1.0)
    return Axis(tag, binding.get("Device"), binding.get("Key"),
                bool(inverted) and inverted[0].get("Value") == "1", zone or 0.0, editable)


def values_equal(a, b):
    """Two binds files hold the same values (dates, bytes, order and line endings aside)."""
    return canonical(a) == canonical(b)


def canonical(data, ignore_preset_name=False):
    """A comparable form of a binds file: each top-level element as (tag, attributes, children)."""
    try:
        text, _bom = _text(data)
        root = ET.fromstring(text)
    except (ValueError, ET.ParseError):
        return ("unreadable", bytes(data) if isinstance(data, (bytes, bytearray)) else data)

    def form(node):
        return (node.tag, tuple(sorted(node.attrib.items())), tuple(sorted(form(kid) for kid in node)),
                (node.text or "").strip() if not list(node) else "")
    attrib = dict(root.attrib)
    if ignore_preset_name:
        attrib.pop("PresetName", None)
    return (tuple(sorted(attrib.items())), tuple(sorted(form(kid) for kid in root)))


# -- the text, as the writer sees it ---------------------------------------------
def _tag_end(text, start):
    quote = ""
    for index in range(start, len(text)):
        char = text[index]
        if char in "\"'" and not quote:
            quote = char
        elif char == quote:
            quote = ""
        elif char == ">" and not quote:
            return index
    return -1


def _self_closing(text, start, end):
    index = end - 1
    while index > start and text[index].isspace():
        index -= 1
    return index > start and text[index] == "/"


def _starts(text, tag, start, end):
    pattern = re.compile("<" + re.escape(tag) + r"(?=[\s>/])")
    found, at = [], max(0, start)
    while True:
        match = pattern.search(text, at)
        if not match or match.start() >= end:
            return found
        found.append(match.start())
        at = match.end()


def _closing(tag):
    return re.compile("</" + re.escape(tag) + r"\s*>")


def _attr(start_tag, name):
    match = re.search(r"\b" + re.escape(name) + r"\s*=\s*([\"'])(.*?)\1", start_tag)
    return match.group(2) if match else ""


def _attr_names(start_tag):
    return set(re.findall(r"\s+([A-Za-z_:][A-Za-z0-9_.:-]*)\s*=", start_tag))


def _newline(text):
    return "\r\n" if "\r\n" in text else "\n"


def _indent(text, at):
    line = text.rfind("\n", 0, at) + 1
    prefix = text[line:at]
    return prefix if not prefix.strip() else ""


def _locate_action(text, tag):
    """(None, (body_start, body_end)) or (result, None)."""
    starts = _starts(text, tag, 0, len(text))
    if not starts:
        return NOT_FOUND, None
    if len(starts) > 1:
        return UNSUPPORTED, None
    start = starts[0]
    end = _tag_end(text, start)
    if end < 0 or _self_closing(text, start, end):
        return UNSUPPORTED, None
    close = _closing(tag).search(text, end + 1)
    if not close or _starts(text, tag, end + 1, close.start()):
        return UNSUPPORTED, None
    return None, (end + 1, close.start())


def _locate_slot(text, body, position):
    starts = _starts(text, position, body[0], body[1])
    if len(starts) != 1:
        return UNSUPPORTED, None
    start = starts[0]
    end = _tag_end(text, start)
    if end < 0 or end >= body[1]:
        return UNSUPPORTED, None
    if _self_closing(text, start, end):
        return None, (start, end + 1)
    close = _closing(position).search(text, end + 1)
    if not close or close.start() > body[1] or _starts(text, position, end + 1, close.start()):
        return UNSUPPORTED, None
    return None, (start, close.end())


def _slot_shape(text, span, position):
    """(start tag, self-closing, body start, body end) when the slot is one the
    writer may read: Device, Key and Hold attributes, Modifier and Hold children."""
    start_tag_end = _tag_end(text, span[0])
    if start_tag_end < 0:
        return None
    start_tag = text[span[0]:start_tag_end + 1]
    if not _attr_names(start_tag) <= {"Device", "Key", "Hold"}:
        return None
    if _self_closing(text, span[0], start_tag_end):
        return start_tag, True, start_tag_end + 1, start_tag_end + 1
    close = _closing(position).search(text, start_tag_end + 1)
    if not close or close.end() != span[1]:
        return None
    for match in _SLOT_CHILD.finditer(text, start_tag_end + 1, close.start()):
        if match.group(1) not in ("Modifier", "Hold"):
            return None
    return start_tag, False, start_tag_end + 1, close.start()


def _existing_slot(text, span, position):
    """The slot as it stands -> (device, key, modifiers, hold, hold_as_attribute), or None."""
    shape = _slot_shape(text, span, position)
    if shape is None:
        return None
    start_tag, closed, body_start, body_end = shape
    device, key = _attr(start_tag, "Device"), _attr(start_tag, "Key")
    hold_attribute = "Hold" in _attr_names(start_tag)
    hold = _attr(start_tag, "Hold") == "1"
    modifiers = []
    if not closed:
        for at in _starts(text, "Modifier", body_start, body_end):
            end = _tag_end(text, at)
            if end < 0 or end >= body_end or not _self_closing(text, at, end):
                return None
            tag = text[at:end + 1]
            if not _attr_names(tag) <= {"Device", "Key"}:
                return None
            modifiers.append((_attr(tag, "Device"), _attr(tag, "Key")))
        holds = _starts(text, "Hold", body_start, body_end)
        if holds:
            end = _tag_end(text, holds[0])
            if end < 0 or end >= body_end or not _self_closing(text, holds[0], end):
                return None
            hold = hold or _attr(text[holds[0]:end + 1], "Value") == "1"
    return device, key, modifiers, hold, hold_attribute


def _layout_of(text):
    match = _LAYOUT.search(text)
    return match.group(1) if match else ""


# -- writing ---------------------------------------------------------------------
def assign_slot(data, tag, position, device="", key="", modifiers=(), hold=False):
    """One button slot as the commander chose it, or cleared (no device).
    -> (result, bytes). A deliberate edit: it may replace whatever is there,
    on any device; it never makes up structure it doesn't know."""
    clear = not device
    modifiers = [(str(d), str(k)) for d, k in modifiers or ()]
    if position not in POSITIONS:
        return UNSUPPORTED, data
    if (not clear and not is_button_input(device, key)) or not all(is_button_input(d, k) for d, k in modifiers) \
            or len(modifiers) > 3:
        return UNKNOWN_KEY, data
    try:
        text, bom = _text(data)
    except UnicodeDecodeError:
        return UNSUPPORTED, data
    if not clear and device == KEYBOARD and not layout_names(_layout_of(text), key):
        return UNKNOWN_KEY, data
    result, body = _locate_action(text, tag)
    if result:
        return result, data
    result, span = _locate_slot(text, body, position)
    if result:
        return result, data
    existing = _existing_slot(text, span, position)
    if existing is None:
        return UNSUPPORTED, data
    old_device, old_key, old_modifiers, old_hold, hold_attribute = existing
    if clear:
        if old_device == NO_DEVICE and not old_key and not old_modifiers and not old_hold:
            return NO_CHANGE, data
        replacement = f'<{position} Device="{NO_DEVICE}" Key="" />'
    else:
        if (old_device, old_key, bool(old_hold)) == (device, key, bool(hold)) \
                and len(old_modifiers) == len(modifiers) and set(old_modifiers) == set(modifiers):
            return NO_CHANGE, data
        indent, newline = _indent(text, span[0]), _newline(text)
        replacement = _slot_xml(position, device, key, modifiers, hold, hold_attribute, indent, newline)
    return SAVED, _bytes(text[:span[0]] + replacement + text[span[1]:], bom)


def clear_slot(data, tag, position):
    return assign_slot(data, tag, position)


def _slot_xml(position, device, key, modifiers, hold, hold_attribute, indent, newline):
    open_tag = f'<{position} Device="{device}" Key="{key}"' + (' Hold="1"' if hold and hold_attribute else "")
    hold_child = hold and not hold_attribute
    if not modifiers and not hold_child:
        return open_tag + " />"
    child = indent + ("\t" if not indent or "\t" in indent else "    ")
    lines = [open_tag + ">"]
    if hold_child:
        lines.append(child + '<Hold Value="1" />')
    lines += [f'{child}<Modifier Device="{d}" Key="{k}" />' for d, k in modifiers]
    lines.append(f"{indent}</{position}>")
    return newline.join(lines)


def assign_axis(data, tag, device="", key="", inverted=False, deadzone=0.0):
    """An axis's Binding, Inverted and Deadzone as chosen, or its binding cleared
    (no device; Inverted and Deadzone kept as given). -> (result, bytes)."""
    clear = not device
    try:
        text, bom = _text(data)
    except UnicodeDecodeError:
        return UNSUPPORTED, data
    result, body = _locate_action(text, tag)
    if result:
        return result if clear or is_axis_input(device, key) else UNKNOWN_KEY, data
    parts = _axis_parts(text, body)
    holds = parts is not None and (parts["device"], parts["key"]) == (device, key)
    if not clear and not is_axis_input(device, key) and not holds:
        return UNKNOWN_KEY, data
    if parts is None:
        return UNSUPPORTED, data
    try:
        zone = float(deadzone)
    except (TypeError, ValueError):
        return UNKNOWN_KEY, data
    if not 0.0 <= zone <= 1.0:
        return UNKNOWN_KEY, data
    binding = f'<Binding Device="{NO_DEVICE}" Key="" />' if clear else f'<Binding Device="{device}" Key="{key}" />'
    inverted_text = "1" if inverted else "0"
    zone_text = parts["deadzone_text"] if abs(parts["deadzone"] - zone) < 1e-7 else f"{zone:.8f}"
    same = (parts["device"] == NO_DEVICE and not parts["key"]) if clear else (parts["device"], parts["key"]) == (device, key)
    if same and inverted_text == parts["inverted_text"] and zone_text == parts["deadzone_text"]:
        return NO_CHANGE, data
    edits = sorted([(parts["binding"], binding), (parts["inverted"], inverted_text), (parts["deadzone_span"], zone_text)],
                   key=lambda item: item[0][0], reverse=True)
    for span, replacement in edits:
        text = text[:span[0]] + replacement + text[span[1]:]
    return SAVED, _bytes(text, bom)


def _single_closed(text, name, body, attributes):
    starts = _starts(text, name, body[0], body[1])
    if len(starts) != 1:
        return None
    end = _tag_end(text, starts[0])
    if end < 0 or end >= body[1] or not _self_closing(text, starts[0], end) \
            or _attr_names(text[starts[0]:end + 1]) != attributes:
        return None
    return starts[0], end + 1


def _value_span(text, span):
    match = _VALUE_ATTR.search(text, span[0], span[1])
    return (match.start(2), match.end(2)) if match else None


def _axis_parts(text, body):
    binding = _single_closed(text, "Binding", body, {"Device", "Key"})
    inverted = _single_closed(text, "Inverted", body, {"Value"})
    deadzone = _single_closed(text, "Deadzone", body, {"Value"})
    if not (binding and inverted and deadzone):
        return None
    inverted_value, zone_value = _value_span(text, inverted), _value_span(text, deadzone)
    if not inverted_value or not zone_value:
        return None
    zone_text = text[zone_value[0]:zone_value[1]]
    try:
        zone = float(zone_text)
    except ValueError:
        return None
    tag = text[binding[0]:binding[1]]
    return {"binding": binding, "device": _attr(tag, "Device"), "key": _attr(tag, "Key"),
            "inverted": inverted_value, "inverted_text": text[inverted_value[0]:inverted_value[1]],
            "deadzone_span": zone_value, "deadzone_text": zone_text, "deadzone": zone}


def _top_level_starts(text, tag):
    """Where each direct child of the root named ``tag`` starts (comments and
    the like skipped), or None when the text isn't well enough formed to tell."""
    found, depth = [], 0
    at = text.find("<")
    while at >= 0:
        if text.startswith("<!--", at):
            end = text.find("-->", at + 4)
            nxt = -1 if end < 0 else end + 3
        elif text.startswith("<![CDATA[", at):
            end = text.find("]]>", at + 9)
            nxt = -1 if end < 0 else end + 3
        elif text.startswith("<?", at):
            end = text.find("?>", at + 2)
            nxt = -1 if end < 0 else end + 2
        elif text.startswith("<!", at):
            end = text.find(">", at + 2)
            nxt = -1 if end < 0 else end + 1
        elif text.startswith("</", at):
            depth -= 1
            if depth < 0:
                return None
            end = text.find(">", at + 2)
            nxt = -1 if end < 0 else end + 1
        else:
            end = _tag_end(text, at)
            if end < 0:
                return None
            after = at + 1 + len(tag)
            if depth == 1 and text.startswith(tag, at + 1) and after < len(text) \
                    and (text[after].isspace() or text[after] in ">/"):
                found.append(at)
            if not _self_closing(text, at, end):
                depth += 1
            nxt = end + 1
        if nxt < 0:
            return None
        at = text.find("<", nxt)
    return found


def assign_setting(data, setting, value):
    """A bare setting (<MouseSensitivity Value="1.0" />), every copy of it. -> (result, bytes)."""
    value = str(value)
    if not _SETTING_VALUE.fullmatch(value):
        return UNKNOWN_KEY, data
    try:
        text, bom = _text(data)
    except UnicodeDecodeError:
        return UNSUPPORTED, data
    starts = _top_level_starts(text, setting)
    if starts is None:
        return UNSUPPORTED, data
    if not starts:
        return NOT_FOUND, data
    spans = []
    for start in starts:
        end = _tag_end(text, start)
        if end < 0 or not _self_closing(text, start, end) or _attr_names(text[start:end + 1]) != {"Value"}:
            return UNSUPPORTED, data
        span = _value_span(text, (start, end + 1))
        if span is None:
            return UNSUPPORTED, data
        spans.append(span)
    if all(text[a:b] == value for a, b in spans):
        return NO_CHANGE, data
    for a, b in reversed(spans):
        text = text[:a] + value + text[b:]
    return SAVED, _bytes(text, bom)


def with_preset_name(data, name):
    """The file with its root's PresetName set to ``name`` (added when there's
    none), every other byte kept. No <Root>: ValueError."""
    text, bom = _text(data)
    match = re.search(r"<Root(?=[\s/>])", text)
    end = _tag_end(text, match.start()) if match else -1
    if not match or end < 0:
        raise ValueError("no <Root> element")
    tag = text[match.start():end + 1]
    value = (str(name).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))
    found = re.search(r"\bPresetName\s*=\s*([\"'])(.*?)\1", tag)
    if found:
        new = tag[:found.start(2)] + value + tag[found.end(2):]
    else:
        new = f'<Root PresetName="{value}"' + tag[len("<Root"):]
    return _bytes(text[:match.start()] + new + text[end + 1:], bom)


def root_version(data):
    """(major, minor) from the root, when both are digits; else None."""
    try:
        text, _bom = _text(data)
    except UnicodeDecodeError:
        return None
    match = re.search(r"<Root(?=[\s/>])", text)
    end = _tag_end(text, match.start()) if match else -1
    if end < 0:
        return None
    tag = text[match.start():end + 1]
    major, minor = _attr(tag, "MajorVersion"), _attr(tag, "MinorVersion")
    return (major, minor) if re.fullmatch(r"\d{1,6}", major or "") and re.fullmatch(r"\d{1,6}", minor or "") else None


# -- merging, one control at a time ------------------------------------------------
def _spans(text, tag):
    out = []
    for start in _top_level_starts(text, tag) or ():
        end = _tag_end(text, start)
        if end < 0:
            continue
        if _self_closing(text, start, end):
            out.append((start, end + 1))
            continue
        close = _closing(tag).search(text, end + 1)
        if close:
            out.append((start, close.end()))
    return out


def copy_element(dest, source, tag):
    """``dest`` with its control ``tag`` (every copy) as ``source`` has it: put
    in where dest has none, taken out where source has none. -> bytes."""
    text, bom = _text(dest)
    other, _ = _text(source)
    theirs = [other[a:b] for a, b in _spans(other, tag)]
    mine = _spans(text, tag)
    newline = _newline(text)
    if mine:
        first = mine[0]
        indent = _indent(text, first[0])
        piece = (newline + indent).join(theirs)
        for start, end in reversed(mine[1:]):
            line = text.rfind("\n", 0, start)
            cut = line if line >= 0 and not text[line + 1:start].strip() else start
            if cut == line and line > 0 and text[line - 1] == "\r":
                cut -= 1
            text = text[:cut] + text[end:]
        if not piece:
            start, end = first
            line = text.rfind("\n", 0, start)
            cut = line if line >= 0 and not text[line + 1:start].strip() else start
            if cut == line and line > 0 and text[line - 1] == "\r":
                cut -= 1
            text = text[:cut] + text[end:]
        else:
            text = text[:first[0]] + piece + text[first[1]:]
    elif theirs:
        close = text.rfind("</Root>")
        if close < 0:
            raise ValueError("no </Root>")
        line = text.rfind("\n", 0, close)
        indent = "\t"
        match = re.search(r"\n([ \t]+)<[A-Za-z]", text)
        if match:
            indent = match.group(1)
        insert_at = line + 1 if line >= 0 and not text[line + 1:close].strip() else close
        text = text[:insert_at] + "".join(f"{indent}{piece}{newline}" for piece in theirs) + text[insert_at:]
    return _bytes(text, bom)


def element_summary(binds_file, tag):
    """A control's value in words, for comparing two files."""
    if tag in binds_file.buttons:
        pair = binds_file.buttons[tag]
        parts = []
        for position in POSITIONS:
            slot = pair.get(position)
            if slot is None or not slot.assigned():
                parts.append("—")
                continue
            words = " + ".join([*(k for _d, k in slot.modifiers), slot.key])
            device = "" if slot.device == KEYBOARD else f"{slot.device} "
            parts.append(f"{device}{words}{' (hold)' if slot.hold else ''}")
        return " · ".join(parts)
    if tag in binds_file.axes:
        axis = binds_file.axes[tag]
        bound = f"{axis.device} {axis.key}" if axis.bound() else "unbound"
        return f"{bound}{' inverted' if axis.inverted else ''}, dead zone {axis.deadzone:.2f}"
    if tag in binds_file.settings:
        return binds_file.settings[tag]["value"] or "(default)"
    return "not in the file"
