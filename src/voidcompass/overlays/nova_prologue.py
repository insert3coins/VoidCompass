"""Nova's Prologue, The Forgotten Archive (Nyx Evera): how she comes aboard.

Lyra, on watch, notices Nova's voice aboard and finds a reference to an
incomplete shipboard program in an old research archive; the commander flies
to the scientific installation in LFT 1748, scans it with the Data Link
Scanner, and agrees to download a copy. Nova is installed, comes on watch and
initialises in silence for 30 minutes of gameplay (her Entry 01's own
requirement), then says hello. Until then she isn't aboard.

It's Lyra's alone: every line is hers, on her watch. Her words are Nyx's,
verbatim. What the Prologue keeps for later chapters (Gorgon, the Life
Sciences Expedition, what N.O.V.A. stands for) is never said here.

Where the installation is in the journal isn't confirmed yet (installations go
by their own names, and the Data Link Scan's event wasn't seen there), so the
triggers are forgiving: dropping at an installation in LFT 1748, then any data
link scan there."""
from __future__ import annotations

import re

SYSTEM = "LFT 1748"
SYSTEM_ADDRESS = 22660650182049
TITLE = "Prologue · The Forgotten Archive"

# The scenes in order: (key, title, Lyra's lines).
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
        "Let's see if we can retrieve anything useful.")),
    ("asked", "The Forgotten Program", (
        "Interesting. I've found the archive.",
        "Most of the documentation is missing, but the software itself appears to be intact.",
        "Designation: N.O.V.A.",
        "Classification: Shipboard Software.",
        "Development records: Incomplete.",
        "I can't determine much more without examining the program itself.",
        "The files appear compatible with our systems.",
        "Would you like me to retrieve a copy?")),
    ("downloaded", "Retrieval", (
        "Understood. Retrieving the archived software.",
        "Download complete.",
        "The original archive remains untouched.",
        "Preparing installation.")),
    ("installed", "Initialization", (
        "N.O.V.A. has been installed.",
        "The program is running, but its communication interface hasn't initialized.",
        "I'm not detecting any critical errors.",
        "Perhaps we should give it some time.",
        "I'll monitor the process.")),
)
LINES = {key: lines for key, _title, lines in SCENES}
TITLES = {key: title for key, title, _lines in SCENES}
ORDER = tuple(key for key, _title, _lines in SCENES)

OBJECTIVES = {
    "found": "Investigate the Large Scientific Installation in LFT 1748.",
    "arrived": "Scan the Scientific Installation using your Data Link Scanner.",
    "asked": "Download N.O.V.A. / Not now",
}
SYSTEM_MESSAGE = "N.O.V.A. — Initializing."

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

_ABOUT = re.compile(r"\b(download|retrieve|install|copy|n\.?o\.?v\.?a|program|software)\b", re.I)
_YES = re.compile(r"\b(download|retrieve|install|yes|yeah|yep|sure|ok|okay|go ahead|do it|please|get it|copy it)\b", re.I)
_NO = re.compile(r"\b(not now|no|nope|later|leave it|don'?t|do not|not yet)\b", re.I)
_INSTALLATION = re.compile(r"installation|scientific", re.I)


def answer(text):
    """"yes", "no" or "" for what was said while Lyra asks about the copy:
    anything about the download, or a short yes or no. Longer words about
    something else are left for TALK."""
    words = " ".join(str(text or "").split())
    if not words or (len(words.split()) > 4 and not _ABOUT.search(words)):
        return ""
    if _NO.search(words):
        return "no"
    return "yes" if _YES.search(words) else ""


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


def data_link_scan(event, raw, system):
    """The Data Link Scanner used in LFT 1748."""
    return event in {"DataScanned", "DatalinkScan"} and in_system(system, raw.get("SystemAddress"))


def step(state, event, raw, system):
    """The scene a journal event moves the Prologue to, or None."""
    stage = state.get("state") or ""
    if stage == "found":
        if at_installation(event, raw, system, state.get("installations") or ()):
            return "arrived"
        if data_link_scan(event, raw, system):
            return "arrived+asked"   # scanned it straight away: both scenes, in order
    if stage == "arrived" and data_link_scan(event, raw, system):
        return "asked"
    return None


def installation_name(event, raw, system):
    """An installation's signal found in LFT 1748, by its own name."""
    if event != "FSSSignalDiscovered" or not in_system(system, raw.get("SystemAddress")):
        return ""
    kind = str(raw.get("SignalType") or "")
    name = str(raw.get("SignalName_Localised") or raw.get("SignalName") or "")
    return name if kind.casefold() == "installation" or _INSTALLATION.search(name) else ""
