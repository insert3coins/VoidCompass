"""Pure modules ported from ED-Outrider (github.com/weslocke/ED-Outrider), GPL-3.0-or-later.

The credits are in THIRD_PARTY_NOTICES.md. Nothing here reads
Outrider's database: the deck hands in its own journal-derived rows.
"""


def ts_seconds(ts):
    """Journal timestamp ('2026-09-28T02:06:56Z') -> seconds since the epoch (UTC)."""
    import calendar
    import time
    return calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
