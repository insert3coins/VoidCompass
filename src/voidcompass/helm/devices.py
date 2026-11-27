"""The game's device files: ControlSchemes\\DeviceMappings.xml (each device's
name and its USB ids) and DeviceButtonMaps\\<name>.buttonMap (its buttons'
labels), and the binds files' references to them.

A .binds file names a device by its DeviceMappings entry, or by its raw ids
("334483F3", VID then PID) when it has none. Once a controller has a name,
a firmware update that changes its ids costs one edit (the entry's ids), not
every binding. When two entries claim the same ids the game uses the first in
the file, so the commander's own entries go at the top.

Like the binds writer, every change edits the text in place: Frontier's
entries, comments and tags nobody has documented (<SupportsIcons>) are kept.
Bytes in, bytes out."""
from __future__ import annotations

from functools import lru_cache
import re
import unicodedata
import xml.etree.ElementTree as ET

from voidcompass.core.paths import resource_path
from voidcompass.helm.binds import _bytes, _closing, _self_closing, _tag_end, _text, _top_level_starts

MAPPINGS = "DeviceMappings.xml"
MAPS_DIR = "DeviceButtonMaps"
AXES = ("X", "Y", "Z", "RX", "RY", "RZ", "U", "V")
HAT_DIRECTIONS = ("Up", "Right", "Down", "Left")
_TYPED_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,49}")
_HEX_ID = re.compile(r"[0-9A-Fa-f]{8}")
_DEVICE_TAG = re.compile(r"<(?:Primary|Secondary|Binding|Modifier)(?=[\s/>])")
_DEVICE_ATTR = re.compile(r"(?<![A-Za-z0-9_.:-])Device\s*=\s*([\"'])(.*?)\1")


# -- reading -------------------------------------------------------------------------
def parse_mappings(data):
    """[{name, ids: ["VVVV:PPPP", ...]}] in file order (the first pair is the entry's own)."""
    if not data:
        return []
    try:
        text, _bom = _text(data)
        root = ET.fromstring(text)
    except (ValueError, ET.ParseError):
        return []
    out = []
    for element in root:
        ids = []
        for node in [element, *element.findall("Alternative")]:
            vid, pid = (node.findtext("VID") or "").strip().upper(), (node.findtext("PID") or "").strip().upper()
            if vid and pid:
                ids.append(f"{vid.zfill(4)}:{pid.zfill(4)}")
        out.append({"name": element.tag, "ids": ids})
    return out


@lru_cache(maxsize=1)
def stock_mappings():
    """Frontier's own DeviceMappings.xml, as shipped."""
    try:
        return resource_path("data", "helm", "FrontierStock-DeviceMappings.xml").read_bytes()
    except OSError:
        return b""


@lru_cache(maxsize=1)
def frontier_names():
    return frozenset(row["name"] for row in parse_mappings(stock_mappings()))


def hex_id(ident):
    """"3344:83F4" -> "334483F4", as a binds file names an unnamed device."""
    return str(ident).replace(":", "").upper()


def ident_of_hex(device):
    """"334483F4" -> "3344:83F4", or "" when it isn't a raw id."""
    device = str(device or "")
    return f"{device[:4].upper()}:{device[4:].upper()}" if _HEX_ID.fullmatch(device) else ""


def parse_button_map(data):
    """{token: label} in file order."""
    if not data:
        return {}
    try:
        text, _bom = _text(data)
        root = ET.fromstring(text)
    except (ValueError, ET.ParseError):
        return {}
    return {node.tag: (node.text or "").strip() for node in root}


def build_button_map(labels):
    """A .buttonMap as Frontier writes one (tabs, CRLF)."""
    def esc(value):
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = ['<?xml version="1.0" encoding="UTF-8" ?>', "<Root>"]
    lines += [f"\t<{token}>{esc(label)}</{token}>" for token, label in labels.items() if label and re.fullmatch(r"[A-Za-z_][\w]*", token)]
    lines.append("</Root>")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def default_labels(buttons, axes=0, hats=0):
    """Button 1..N, the axes and the hats' four directions, as the device reports them."""
    labels = {f"Joy_{n}": f"Button {n}" for n in range(1, max(0, int(buttons or 0)) + 1)}
    if int(axes or 0) > 0:
        labels.update({f"Joy_{axis}Axis": f"{axis} Axis" for axis in AXES})
    for hat in range(1, max(0, int(hats or 0)) + 1):
        labels.update({f"Joy_POV{hat}{direction}": f"Hat {hat} {direction}" for direction in HAT_DIRECTIONS})
    return labels


# -- names ---------------------------------------------------------------------------
def fold(name):
    return str(name).casefold().replace("-", "").replace("_", "")


def default_name(reported, taken):
    """The name a controller is offered: ASCII letters and digits of what it
    reports, starting with a letter, 3 to 50 long, unique (case, - and _ aside)."""
    ascii_text = unicodedata.normalize("NFKD", str(reported or "")).encode("ascii", "ignore").decode()
    name = re.sub(r"[^A-Za-z0-9]", "", ascii_text)
    if not name:
        name = "Controller"
    elif not name[0].isalpha() or len(name) < 3:
        name = "Device" + name
    name = name[:50]
    used = {fold(other) for other in taken}
    if fold(name) not in used:
        return name
    number = 2
    while True:
        tail = str(number)
        candidate = name[:50 - len(tail)] + tail
        if fold(candidate) not in used:
            return candidate
        number += 1


def name_problem(name, taken):
    """Why a typed name won't do, or ""."""
    if not _TYPED_NAME.fullmatch(str(name or "")):
        return "Use 3 to 50 letters, digits, - or _, starting with a letter (no spaces or accents)."
    if fold(name) in {fold(other) for other in taken}:
        return f"{name} is taken (another device, or one of the game's own names)."
    return ""


# -- DeviceMappings.xml, edited in place ------------------------------------------------
def _root_span(text):
    match = re.search(r"<Root(?=[\s/>])", text)
    end = _tag_end(text, match.start()) if match else -1
    if not match or end < 0:
        raise ValueError("no <Root> element")
    return match.start(), end + 1


def _element_spans(text, tag, ignore_case=False):
    """(start, end) of each top-level element named ``tag``."""
    spans = []
    names = [tag]
    if ignore_case:
        names = sorted({m.group(1) for m in re.finditer(r"<([A-Za-z_][\w.-]*)", text) if m.group(1).casefold() == tag.casefold()})
    for name in names:
        for start in _top_level_starts(text, name) or ():
            end = _tag_end(text, start)
            if end < 0:
                continue
            if _self_closing(text, start, end):
                spans.append((start, end + 1))
                continue
            close = _closing(name).search(text, end + 1)
            if close:
                spans.append((start, close.end()))
    return sorted(spans)


def _indent_and_newline(text):
    newline = "\r\n" if "\r\n" in text else "\n"
    match = re.search(r"\n([ \t]+)<[A-Za-z]", text)
    return (match.group(1) if match else "\t"), newline


def insert_entry(data, name, vid, pid):
    """A new entry at the top of <Root> (the first claim on its ids wins). -> bytes."""
    if not data:
        data = stock_mappings() or b'<?xml version="1.0" encoding="UTF-8" ?>\r\n<Root>\r\n</Root>\r\n'
    text, bom = _text(data)
    if _element_spans(text, name):
        return data
    _start, open_end = _root_span(text)
    indent, newline = _indent_and_newline(text)
    entry = f"{newline}{indent}<{name}>{newline}{indent}{indent}<PID>{pid.upper()}</PID>{newline}{indent}{indent}<VID>{vid.upper()}</VID>{newline}{indent}</{name}>"
    return _bytes(text[:open_end] + entry + text[open_end:], bom)


def rename_entry(data, old, new):
    """The entry renamed where it stands, every child kept. -> bytes."""
    text, bom = _text(data)
    spans = _element_spans(text, old, ignore_case=True)
    if not spans:
        return data
    start, end = spans[0]
    actual = re.match(r"<([A-Za-z_][\w.-]*)", text[start:]).group(1)
    piece = "<" + new + text[start + 1 + len(actual):end]
    if not piece.rstrip().endswith("/>"):
        piece = re.sub(r"</" + re.escape(actual) + r"(\s*)>$", lambda m: "</" + new + m.group(1) + ">", piece)
    text = text[:start] + piece + text[end:]
    # A second copy under the old name further down would be dead: it goes.
    for s, e in reversed(_element_spans(text, old, ignore_case=True)):
        if s != start:
            text = text[:s] + text[e:]
    return _bytes(text, bom)


def retarget_entry(data, name, vid, pid):
    """The entry's own VID and PID changed (firmware moved them); nothing else. -> bytes."""
    text, bom = _text(data)
    spans = _element_spans(text, name)
    if not spans:
        return data
    start, end = spans[0]
    piece = text[start:end]
    body_end = piece.find("<Alternative")
    head, tail = (piece, "") if body_end < 0 else (piece[:body_end], piece[body_end:])
    head = re.sub(r"<VID>\s*[0-9A-Fa-f]*\s*</VID>", f"<VID>{vid.upper()}</VID>", head, count=1)
    head = re.sub(r"<PID>\s*[0-9A-Fa-f]*\s*</PID>", f"<PID>{pid.upper()}</PID>", head, count=1)
    return _bytes(text[:start] + head + tail + text[end:], bom)


def remove_entry(data, name):
    text, bom = _text(data)
    for start, end in reversed(_element_spans(text, name)):
        line = text.rfind("\n", 0, start)
        cut = line if line >= 0 and not text[line + 1:start].strip() else start
        if cut == line and line > 0 and text[line - 1] == "\r":
            cut -= 1
        text = text[:cut] + text[end:]
    return _bytes(text, bom)


def user_entries(data):
    """The entries that aren't Frontier's (by name), in file order."""
    stock = {fold(name) for name in frontier_names()}
    return [row for row in parse_mappings(data) if fold(row["name"]) not in stock]


def resolve(mappings, ident):
    """The name the game gives a device with these ids: the first entry claiming them, or ""."""
    for row in mappings:
        if ident in row["ids"]:
            return row["name"]
    return ""


# -- the binds files' references ---------------------------------------------------------
def rewrite_references(data, matches, new):
    """Every Device="..." on a slot, axis or modifier that ``matches(value)`` becomes ``new``.
    -> (bytes, how many)."""
    text, bom = _text(data)
    out, copied, count, at = [], 0, 0, 0
    while True:
        tag = _DEVICE_TAG.search(text, at)
        if not tag:
            break
        end = _tag_end(text, tag.start())
        if end < 0:
            break
        attr = _DEVICE_ATTR.search(text, tag.end(), end)
        if attr and matches(attr.group(2)):
            out.append(text[copied:attr.start(2)])
            out.append(new)
            copied = attr.end(2)
            count += 1
        at = end + 1
    if not count:
        return data, 0
    out.append(text[copied:])
    return _bytes("".join(out), bom), count


def count_references(data, matches):
    return rewrite_references(data, matches, "x")[1]


def by_name(name):
    folded = str(name).casefold()
    return lambda value: str(value).casefold() == folded


def by_ident(ident):
    raw = hex_id(ident)
    return lambda value: str(value).upper() == raw
