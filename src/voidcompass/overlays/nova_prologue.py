"""Nova's Prologue, The Forgotten Archive (Nyx Evera): how she comes aboard.

Lyra, on watch, notices Nova's voice aboard and finds a reference to an
incomplete shipboard program in an old research archive. When the commander
arrives at the scientific installation in LFT 1748 (Lyra still on watch), she
connects to its systems, recovers the archived software and installs it, a
few seconds apart, as if she's working. Nova then comes on watch and
initialises in silence for 30 minutes of gameplay (her Entry 01's own
requirement) before she says hello. Until then she isn't aboard.

It's Lyra's alone: every line is hers, on her watch. Her words are Nyx's,
verbatim (the revised sequence of 28 November: no Data Link Scan, no
question). What the Prologue keeps for later chapters (Gorgon, the Life
Sciences Expedition, what N.O.V.A. stands for) is never said here.

The arrival is forgiving, since installations go by their own names: a drop
at an installation in LFT 1748, or beside one whose signal was found there."""
from __future__ import annotations

import re

SYSTEM = "LFT 1748"
SYSTEM_ADDRESS = 22660650182049
TITLE = "Prologue · The Forgotten Archive"
REVISION = 2

# The scenes in order: (key, title, Lyra's lines). Scene 4 is told in two
# parts, a pause apart; the book shows it as one.
SCENES = (
    ("found", "An Unusual Discovery", (
        "Commander, I've come across something unusual in an old research archive.",
        "It's listed as a shipboard software program, but the documentation is rather incomplete.",
        "There's a designation attached to it. N.O.V.A.",
        "I found a reference to a scientific installation in LFT 1748.",
        "If you're interested, perhaps we should investigate.")),
    ("arrived", "The Scientific Installation", (
        "That appears to be the installation, Commander.",
        "The identification matches our archive reference.",
        "I'll attempt to establish a connection to its systems.")),
    ("connected", "Establishing Connection", (
        "Connection established.",
        "I've located the archived software package. Beginning data transfer now.")),
    ("recovered", "Recovery and Installation", (
        "Download complete. The data appears to be intact.",
        "I'll prepare the software for installation aboard our ship.")),
    ("installing", "Recovery and Installation", (
        "Installation complete.",
        "N.O.V.A. is currently initialising. According to the system diagnostics, the process should take approximately thirty minutes.",
        "I'll monitor her progress in the meantime.")),
)
LINES = {key: lines for key, _title, lines in SCENES}
TITLES = {key: title for key, title, _lines in SCENES}
ORDER = tuple(key for key, _title, _lines in SCENES)

# After the installation, each scene follows the last once Lyra has finished
# speaking and this many seconds have passed (Nyx's delays).
NEXT = {"arrived": ("connected", 10.0), "connected": ("recovered", 20.0), "recovered": ("installing", 15.0)}

STAY = "Stay at the installation while Lyra recovers the archive."
OBJECTIVES = {
    "found": "Investigate the Large Scientific Installation in LFT 1748.",
    "arrived": STAY,
    "connected": STAY,
    "recovered": STAY,
}
SYSTEM_MESSAGE = "N.O.V.A. — Initialising"

# Shown in her book once she's aboard (Nyx's suggested UI text).
GETTING_TO_KNOW = {
    "title": "Getting to Know NOVA",
    "text": ("NOVA is an unfamiliar shipboard program with an incomplete history. "
             "As you travel together, she may discover more about herself and share what she learns with you. "
             "Exploration, scientific discoveries, and the experiences you accumulate together will gradually "
             "unlock her story."),
    "activities": ("Hyperspace jumps", "Lightyears travelled", "Exploration and cartographic discoveries",
                   "Exobiology research", "Codex discoveries and notable stellar phenomena",
                   "Visits to significant systems, nebulae, and galactic regions", "Special exploration objectives"),
    "note": "Combat and mining do not contribute to NOVA's story progression.",
}

_INSTALLATION = re.compile(r"installation|scientific", re.I)


def in_system(system, address=None):
    try:
        if address is not None and int(address) == SYSTEM_ADDRESS:
            return True
    except (TypeError, ValueError):
        pass
    return str(system or "").strip().casefold() == SYSTEM.casefold()


def at_installation(event, raw, system, seen=()):
    """Dropped at an installation in LFT 1748: a destination drop naming one,
    or leaving supercruise beside one whose signal was found there."""
    if not in_system(system, raw.get("SystemAddress")):
        return False
    if event == "SupercruiseDestinationDrop":
        kind = f"{raw.get('Type') or ''} {raw.get('Type_Localised') or ''}"
        return bool(_INSTALLATION.search(kind)) or any(str(name).casefold() in kind.casefold() for name in seen if name)
    if event == "SupercruiseExit":
        body = str(raw.get("Body") or "")
        return bool(_INSTALLATION.search(body)) or any(str(name).casefold() == body.casefold() for name in seen if name)
    return False


def step(state, event, raw, system):
    """The scene a journal event moves the Prologue to, or None: only the
    arrival; everything after it follows on its own (NEXT)."""
    if (state.get("state") or "") == "found" and at_installation(event, raw, system, state.get("installations") or ()):
        return "arrived"
    return None


def installation_name(event, raw, system):
    """An installation's signal found in LFT 1748, by its own name."""
    if event != "FSSSignalDiscovered" or not in_system(system, raw.get("SystemAddress")):
        return ""
    kind = str(raw.get("SignalType") or "")
    name = str(raw.get("SignalName_Localised") or raw.get("SignalName") or "")
    return name if kind.casefold() == "installation" or _INSTALLATION.search(name) else ""


def revised(state):
    """A Prologue begun under the first sequence, carried onto this one.
    Stuck waiting for a Data Link Scan (the event never came), it goes back to
    the arrival, which now does everything; a download already said yes to
    finishes as before."""
    state = dict(state or {})
    if state.get("revision") == REVISION:
        return state, False
    stage = state.get("state") or ""
    if stage in {"arrived", "asked"}:
        state["state"] = "found"
        state["scenes"] = {key: at for key, at in (state.get("scenes") or {}).items() if key == "found"}
        state.pop("declined", None)
    state["revision"] = REVISION
    return state, True
