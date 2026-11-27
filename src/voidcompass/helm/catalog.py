"""Every control as the game's Options › Controls screen shows it: the section
(General, Ship, SRV, On foot), the group inside it and the row's name.

The .binds file names a control by an internal tag ("ExplorationSAANextGenus")
the game never shows. data/helm/control_names.txt maps each tag to where
the commander reads it, in the game's own order. A tag it doesn't know falls
back to its tag, made readable, under "other"."""
from __future__ import annotations

from functools import lru_cache
import logging
import re

from voidcompass.core.paths import resource_path

SECTIONS = ("general", "ship", "srv", "onfoot")
SECTION_LABELS = {"general": "General", "ship": "Ship", "srv": "SRV", "onfoot": "On foot", "other": "Other"}
_FILE_SECTIONS = {"GENERAL": "general", "SHIP": "ship", "SRV": "srv", "ON_FOOT": "onfoot"}
UNKNOWN_ORDER = 1_000_000


class Control:
    __slots__ = ("tag", "section", "group", "name", "order")

    def __init__(self, tag, section, group, name, order):
        self.tag, self.section, self.group, self.name, self.order = tag, section, group, name, order

    @property
    def label(self):
        """"Flight Rotation / Yaw Left": names repeat across groups (four rows are called "Move Forward")."""
        return f"{self.group} / {self.name}" if self.group else self.name

    def as_dict(self):
        return {"tag": self.tag, "section": self.section, "group": self.group or "", "name": self.name,
                "order": self.order}


def humanize(tag):
    """"ToggleCargoScoop_Buggy" -> "Toggle Cargo Scoop Buggy"."""
    text = str(tag or "").replace("_", " ")
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text).split()
    return " ".join(words) or str(tag or "")


@lru_cache(maxsize=1)
def _table():
    names = {}
    try:
        text = resource_path("data", "helm", "control_names.txt").read_text(encoding="utf-8-sig")
    except OSError as exc:
        logging.error("Helm's control names are missing (%s): controls show their tags", exc)
        return names
    order = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        tag, _, rest = line.partition("=")
        parts = [part.strip() for part in rest.split("|")]
        if len(parts) != 3 or parts[0] not in _FILE_SECTIONS:
            continue
        names[tag.strip()] = Control(tag.strip(), _FILE_SECTIONS[parts[0]], parts[1], parts[2], order)
        order += 1
    return names


def lookup(tag):
    """The control for a tag; never None (an unknown one is "other", humanized)."""
    known = _table().get(str(tag or ""))
    if known is not None:
        return known
    return Control(str(tag or ""), "other", "", humanize(tag), UNKNOWN_ORDER)


def known():
    """{tag: Control} in the game's order."""
    return dict(_table())


def label(tag):
    return lookup(tag).label


def section_of(tag):
    """The control's section; for one the table hasn't met, a guess from its tag."""
    control = lookup(tag)
    if control.section != "other":
        return control.section
    name = str(tag or "")
    if "Humanoid" in name:
        return "onfoot"
    if "Buggy" in name:
        return "srv"
    return "other"
