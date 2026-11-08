"""Whether a Scan is a first discovery that's really the commander's.

The game's WasDiscovered only says nobody has sold that body's data yet. A
nav beacon's read carries the flag too, on bodies the commander didn't find,
and other commanders can be on record at EDSM for a body nobody has sold.
"""

from __future__ import annotations

NAV_BEACON_SCANS = {"navbeacondetail", "navbeacon"}

# The deck sets this: (raw Scan) -> True when EDSM names another commander.
SOMEONE_ELSE = None


def unclaimed(raw):
    """The commander's own scan of a body with no discoverer's tag."""
    return raw.get("WasDiscovered") is False and str(raw.get("ScanType") or "").casefold() not in NAV_BEACON_SCANS


def our_first(raw):
    """Whether the crew may call this scan your first discovery."""
    if not unclaimed(raw):
        return False
    check = SOMEONE_ELSE
    if check is None:
        return True
    try:
        return not check(raw)
    except Exception:
        return True
