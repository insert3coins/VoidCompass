"""Chosen journal events from every journal file, for the tables that keep
the books (5.7.8: My Samples, Sessions, Earnings, History, Hotspots).

Each file is read once per size: its matching lines are kept parsed in a small
in-memory cache, so asking again after a jump reads only the newest file.
Only one commander's events come back when a commander or FID is given.
"""

from __future__ import annotations

import json
import os
import re
import threading
from functools import lru_cache

from voidcompass.core.journal_files import journal_sort_key
from voidcompass.exploration.travel_history import commander_matches

_LOCK = threading.Lock()
_CACHE = {}          # path -> (signature, events key, [events])
_CACHE_MAX = 4000
IDENTITY = frozenset({"Commander", "LoadGame"})
# Every event any table reads: one pass of each file serves them all.
_REGISTERED = set(IDENTITY)


def register(events):
    """Name the events a table will ask for, so each file is read once for all of them."""
    with _LOCK:
        new = set(events) - _REGISTERED
        if new:
            _REGISTERED.update(new)
            _CACHE.clear()


@lru_cache(maxsize=8)
def _markers(events):
    return re.compile(r'"event"\s*:\s*"(?:' + "|".join(re.escape(event) for event in sorted(events)) + r')"')


def journal_files(journal_dir):
    try:
        names = [name for name in os.listdir(journal_dir) if name.startswith("Journal.") and name.endswith(".log")]
    except OSError:
        return []
    return [os.path.join(journal_dir, name) for name in sorted(names, key=journal_sort_key)]


def signature(journal_dir):
    """Changes to any journal invalidate a reduced history, including older imports."""
    out = []
    for path in journal_files(journal_dir):
        try:
            stat = os.stat(path)
            out.append((path, stat.st_size, stat.st_mtime_ns))
        except OSError:
            continue
    return tuple(out)


def _file_events(path, wanted, markers):
    try:
        stat = os.stat(path)
        signature = (stat.st_size, stat.st_mtime_ns)
    except OSError:
        return []
    key = path
    with _LOCK:
        cached = _CACHE.get(key)
    if cached and cached[0] == signature and cached[1] == wanted:
        return cached[2]
    rows = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not markers.search(line):
                    continue
                try:
                    raw = json.loads(line)
                except ValueError:
                    continue
                if isinstance(raw, dict) and raw.get("event") in wanted:
                    rows.append(raw)
    except OSError:
        return []
    with _LOCK:
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = (signature, wanted, rows)
    return rows


def read(journal_dir, events, commander=None, fid=None, since=None):
    """Every wanted event, oldest first. ``since``: an ISO timestamp; files
    that ended before it are still read (their names don't always say)."""
    register(events)
    with _LOCK:
        everything = frozenset(_REGISTERED)
    markers = _markers(everything)
    wanted = frozenset(events) | IDENTITY
    out = []
    active = not bool(commander or fid)
    for path in journal_files(journal_dir):
        for raw in _file_events(path, everything, markers):
            event = raw.get("event")
            if event not in wanted:
                continue
            if event in IDENTITY:
                active = commander_matches(raw, commander, fid)
                if event in events and active:
                    out.append(raw)
                continue
            if not active:
                continue
            if since and str(raw.get("timestamp") or "") < since:
                continue
            out.append(raw)
    return out
