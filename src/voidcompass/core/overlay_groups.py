"""Overlay groups (5.8.1): sets of overlays for whatever you're doing.

A group has a name, its overlays and a type:

- "only": while it's on, every other overlay hides. One at a time.
- "add": its overlays show while it's on and hide while it's off; the rest
  are left as they are. Any number can be on.

A group can be tied to an activity: it comes on by itself when that's what
you're doing, and goes when it stops. Switched by hand (its hotkey, the deck
header, Overlay Studio, the Local API), it stays as you left it until the
activity changes.

Plain functions over a list of groups and a small state dict:
{"only": id or "", "on": [ids], "auto": [ids switched on by the activity]}."""
from __future__ import annotations

import re

MODES = ("only", "add")
MAX_GROUPS = 8
ACTIVITIES = (
    ("", "By hand only"),
    ("exploring", "Exploring (in flight)"),
    ("ring_mining", "Ring mining"),
    ("rhino", "In the Rhino"),
    ("planet", "On a planet (landed, in an SRV or on foot)"),
    ("on_foot", "On foot"),
    ("docked", "Docked"),
    ("combat", "In combat (a ship targeted)"),
    ("witch_space", "Jumping (charging and in witch space)"),
)
ACTIVITY_KEYS = tuple(key for key, _label in ACTIVITIES)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").casefold()).strip("-")[:32] or "group"


def normalize_groups(raw, known=None):
    """The groups as kept: valid ids, names, types, activities and members
    (only overlays that exist, when ``known`` is given). At most MAX_GROUPS."""
    out, ids = [], set()
    for row in raw if isinstance(raw, list) else ():
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()[:40]
        if not name:
            continue
        group_id = _slug(row.get("id") or name)
        while group_id in ids:
            group_id = f"{group_id}-2"
        ids.add(group_id)
        members = [str(attr) for attr in row.get("members") or () if isinstance(attr, str)]
        if known is not None:
            members = [attr for attr in members if attr in known]
        activity = str(row.get("activity") or "")
        out.append({"id": group_id, "name": name, "mode": row.get("mode") if row.get("mode") in MODES else "add",
                    "members": list(dict.fromkeys(members)), "activity": activity if activity in ACTIVITY_KEYS else ""})
        if len(out) >= MAX_GROUPS:
            break
    return out


def normalize_state(raw, groups):
    ids = {group["id"]: group for group in groups}
    raw = raw if isinstance(raw, dict) else {}
    only = str(raw.get("only") or "")
    only = only if only in ids and ids[only]["mode"] == "only" else ""
    on = [group_id for group_id in raw.get("on") or () if group_id in ids and ids[group_id]["mode"] == "add"]
    auto = [group_id for group_id in raw.get("auto") or () if group_id == only or group_id in on]
    return {"only": only, "on": list(dict.fromkeys(on)), "auto": list(dict.fromkeys(auto)), "activity": str(raw.get("activity") or "")}


def is_on(group, state):
    return state["only"] == group["id"] if group["mode"] == "only" else group["id"] in state["on"]


def hidden(groups, state, every):
    """The overlays (attrs, from ``every``) the groups hide right now."""
    by_id = {group["id"]: group for group in groups}
    showing = set()
    if state["only"] in by_id:
        showing |= set(by_id[state["only"]]["members"])
    for group_id in state["on"]:
        if group_id in by_id:
            showing |= set(by_id[group_id]["members"])
    out = set()
    if state["only"] in by_id:
        out |= {attr for attr in every if attr not in showing}
    for group in groups:
        if group["mode"] == "add" and group["id"] not in state["on"]:
            out |= {attr for attr in group["members"] if attr not in showing}
    return out


def toggle(groups, state, group_id, on=None):
    """Switch a group by hand (``on`` None flips it). Returns the new state."""
    group = next((row for row in groups if row["id"] == group_id), None)
    if group is None:
        return state
    state = {**state, "on": list(state["on"]), "auto": [item for item in state["auto"] if item != group_id]}
    want = (not is_on(group, state)) if on is None else bool(on)
    if group["mode"] == "only":
        state["only"] = group_id if want else ("" if state["only"] == group_id else state["only"])
    elif want and group_id not in state["on"]:
        state["on"].append(group_id)
    elif not want:
        state["on"] = [item for item in state["on"] if item != group_id]
    return state


def follow_activity(groups, state, activity):
    """What you're doing changed: groups tied to the old activity that it
    switched on go off, and the ones tied to the new one come on. A group you
    switched by hand is left alone."""
    if activity == state.get("activity"):
        return state
    state = {**state, "on": list(state["on"]), "auto": list(state["auto"]), "activity": activity}
    for group_id in list(state["auto"]):
        group = next((row for row in groups if row["id"] == group_id), None)
        if group is None or group["activity"] == activity:
            continue
        state["auto"].remove(group_id)
        if state["only"] == group_id:
            state["only"] = ""
        state["on"] = [item for item in state["on"] if item != group_id]
    for group in groups:
        if not activity or group["activity"] != activity or is_on(group, state):
            continue
        if group["mode"] == "only":
            state["only"] = group["id"]
        else:
            state["on"].append(group["id"])
        state["auto"].append(group["id"])
    return state


_ON_WORDS = r"show|open|bring up|use|switch on|turn on|activate|start|switch to|change to|go to|load"
_OFF_WORDS = r"hide|close|switch off|turn off|deactivate|stop|drop|put away|clear"
_FLIP_WORDS = r"toggle|flip|switch"


def _words(text):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).split())


def request(text, groups):
    """A group asked for by name, "show the Rhino group", "hide exploring
    group", "switch to the combat group": {"id", "on": True/False/None (flip)},
    {"id": None} for a group that isn't one of yours, or None when no group
    was asked about. The word "group" must be said."""
    said = _words(text)
    if not re.search(r"\bgroups?\b", said):
        return None
    said = re.sub(r"^(?:(?:please|could you|can you|would you|will you|ok|okay|hey|now)\s+)+", "", said)
    match = re.match(rf"^(?:(?P<on>{_ON_WORDS})|(?P<off>{_OFF_WORDS})|(?P<flip>{_FLIP_WORDS}))\s+(?:the\s+|my\s+)?(?P<name>.+?)\s+"
                     rf"(?:overlay\s+)?groups?(?:\s+(?P<tail>on|off))?(?:\s+(?:please|now|for me))*$", said)
    if not match:
        match = re.match(r"^(?:the\s+)?(?P<name>.+?)\s+(?:overlay\s+)?groups?\s+(?P<tail>on|off)$", said)
        if not match:
            return None
    name = match.group("name")
    by_name = {_words(group["name"]): group for group in groups}
    by_name.update({_words(group["id"]): group for group in groups if _words(group["id"]) not in by_name})
    group = by_name.get(name) or next((row for key, row in by_name.items() if key.startswith(name) or name.startswith(key)), None)
    tail = match.groupdict().get("tail")
    on = True if (match.groupdict().get("on") or tail == "on") else False if (match.groupdict().get("off") or tail == "off") else None
    return {"id": group["id"] if group else None, "name": group["name"] if group else name, "on": on}


def activity_of(facts):
    """What you're doing, from the Navigation HUD's page facts: the most
    particular first."""
    facts = facts or {}
    if facts.get("has_jump"):
        return "witch_space"
    if facts.get("in_rhino"):
        return "rhino"
    if facts.get("on_foot"):
        return "on_foot"
    if facts.get("docked"):
        return "docked"
    if facts.get("on_planet"):
        return "planet"
    if facts.get("target"):
        return "combat"
    if facts.get("prospecting"):
        return "ring_mining"
    return "exploring" if facts.get("system") else ""
