"""Whether a Scan or a step outside is a first that's really the commander's.

The game's WasDiscovered only says nobody has sold that body's data yet. A
nav beacon's read carries it on bodies the commander didn't find, and other
commanders can be on record at EDSM for a body nobody has sold.

WasFootfalled has the same trouble, and stays false after you've walked
there yourself, so a step outside needs its own check.
"""

from __future__ import annotations

NAV_BEACON_SCANS = {"navbeacondetail", "navbeacon"}

# The deck sets these.
# (raw Scan) -> True when EDSM names another commander.
SOMEONE_ELSE = None
# (raw Disembark) -> True when you've walked that body before, or people live in the system.
WALKED_BEFORE = None


def beacon_read(raw):
    """A Scan read off a nav beacon: its Was* flags aren't the commander's."""
    return str(raw.get("ScanType") or "").casefold() in NAV_BEACON_SCANS


def unclaimed(raw):
    """The commander's own scan of a body with no discoverer's tag."""
    return raw.get("WasDiscovered") is False and not beacon_read(raw)


def _no(check, raw):
    if check is None:
        return True
    try:
        return not check(raw)
    except Exception:
        return True


def our_first(raw):
    """Whether the crew may call this scan your first discovery."""
    return unclaimed(raw) and _no(SOMEONE_ELSE, raw)


def footfall_open(raw):
    """The commander's own scan of a body nobody is recorded as walking on."""
    return raw.get("WasFootfalled") is False and not beacon_read(raw)


def new_ground(raw):
    """Whether this Disembark can be a first footfall at all."""
    if raw.get("Taxi") or raw.get("Multicrew") or raw.get("OnStation") or raw.get("StationName"):
        return False
    return _no(WALKED_BEFORE, raw)
