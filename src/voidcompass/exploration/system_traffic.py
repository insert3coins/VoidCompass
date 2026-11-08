"""Is a system worth asking you to scan? (5.7.7)

Your rule: no traffic through it, ask; more than five visits a year, don't.
EDSM counts visits per day, per week and all-time, not per year, so the
year is estimated: all-time visits spread over how long EDSM has known the
system (never less than a year), and at least the last week's.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

QUIET_PER_YEAR = 5


def _when(stamp):
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(stamp or "").strip(), pattern).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def _count(traffic, key):
    try:
        return max(0, int(float((traffic or {}).get(key) or 0)))
    except (AttributeError, TypeError, ValueError):
        return 0


def yearly_visits(traffic, discovered_at="", now=None):
    """About how many visits a year the system gets, from EDSM's counts."""
    now = time.time() if now is None else now
    total, week = _count(traffic, "total"), _count(traffic, "week")
    if not total:
        return 0.0
    since = _when(discovered_at)
    years = max(1.0, (now - since) / (365.25 * 86400)) if since else 1.0
    return max(total / years, float(week))


def quiet(traffic, discovered_at="", now=None):
    """True: worth asking you to scan it (five visits a year or fewer)."""
    return yearly_visits(traffic, discovered_at, now) <= QUIET_PER_YEAR
