"""The galaxy tick: when the BGS moves on, about once a day.

The EDCD tick service (https://tick.edcd.io) says when the last tick was;
each one we hear of is kept. Work is grouped by the tick it came after. Ticks
from before we started asking are estimated: the tick keeps roughly the same
time of day, so the nearest known one is carried back a day at a time (shown
as estimated).
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging

import requests

from voidcompass.core.version import APP_VERSION

TICK_URLS = ("https://tick.edcd.io/api/tick", "http://tick.infomancer.uk/galtick.json")
DAY = 86400
_MAX_GAP = DAY + 2 * 3600


def _parse(text):
    text = str(text or "").strip().strip('"')
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(text.replace("Z", "+00:00"), fmt).timestamp()
        except ValueError:
            continue
    return None


def fetch_latest_tick(session=None, timeout=10):
    """The last galaxy tick (epoch seconds), or None if no service answered."""
    session = session or requests
    headers = {"User-Agent": f"VoidCompass/{APP_VERSION}"}
    for url in TICK_URLS:
        try:
            reply = session.get(url, headers=headers, timeout=timeout)
            reply.raise_for_status()
            try:
                data = reply.json()
            except ValueError:
                data = reply.text
            if isinstance(data, dict):
                data = data.get("lastGalaxyTick") or data.get("time") or data.get("tick")
            ts = _parse(data)
            if ts:
                return ts
        except Exception as exc:
            logging.info("BGS tick service %s unavailable: %s", url, exc)
    return None


def tick_for(ts, known):
    """``(tick_start, estimated)`` for a moment, from the ticks known."""
    known = sorted(known or ())
    if ts is None:
        return None, True
    before = [tick for tick in known if tick <= ts]
    if before and ts - before[-1] <= _MAX_GAP:
        return before[-1], False
    if known:
        base = min(known, key=lambda tick: abs(tick - ts))
    else:
        base = 0.0  # midnight UTC, with nothing better known
    return base + ((ts - base) // DAY) * DAY, True


def label(ts):
    if not ts:
        return "Unknown"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
