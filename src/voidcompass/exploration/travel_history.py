"""Every jump the commander has made, from the journals, for the Galactic Atlas.

Deep Survey keeps rich facts about the most recent 5,000 jumps and lets the
rest go; the atlas's "where you have been" needs the whole journey, and only
where and when. This keeps one compact row per arrival (FSDJump, CarrierJump,
or a Location that finds the ship somewhere new), imported once from every
journal file and extended live.

A row is ``[timestamp, system, x, y, z, star class, jump ly]``; the star class
comes from the StartJump that announced the jump.
"""

from __future__ import annotations

import json
import math
import os
import threading

from voidcompass.core.journal_files import journal_sort_key
from voidcompass.core.persistence_queue import persistence_queue

SCHEMA = 1
MAX_ROWS = 250_000
ARRIVALS = frozenset({"FSDJump", "CarrierJump", "Location"})
MARKERS = tuple(
    marker
    for event in ("FSDJump", "CarrierJump", "Location", "StartJump", "Commander", "LoadGame")
    for marker in (f'"event":"{event}"', f'"event": "{event}"')
)


def _position(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        position = tuple(float(value[index]) for index in range(3))
    except (TypeError, ValueError):
        return None
    return position if all(math.isfinite(axis) for axis in position) else None


def commander_matches(raw, commander=None, fid=None):
    """Whether a Commander/LoadGame event is the wanted commander (FID first)."""
    if raw.get("event") == "Commander":
        name, event_fid = raw.get("Name"), raw.get("FID")
    else:
        name, event_fid = raw.get("Commander"), raw.get("FID")
    if fid and event_fid:
        return str(fid).casefold() == str(event_fid).casefold()
    if commander and name:
        return str(commander).casefold() == str(name).casefold()
    return not bool(commander or fid)


class TravelHistory:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.rows = []
        self.files = {}
        self.revision = 0
        self._keys = set()
        self._pending_star = ("", "")
        self.load()

    # -- storage -------------------------------------------------------------
    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        rows = [row for row in data.get("rows") or [] if isinstance(row, list) and len(row) >= 7]
        with self.lock:
            self.rows = rows[-MAX_ROWS:]
            self.files = {str(key): str(value) for key, value in (data.get("files") or {}).items()}
            self._keys = {(str(row[0]), str(row[1]).casefold()) for row in self.rows}
            self.revision += 1

    def _payload(self):
        with self.lock:
            return {"schema": SCHEMA, "rows": list(self.rows), "files": dict(self.files)}

    def save(self, immediate=False):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None,
                                            delay_s=0.25 if immediate else 3.0, immediate=immediate)

    def flush(self, wait=False):
        self.save(immediate=True)
        if wait and self.path:
            persistence_queue().flush(self.path, timeout=1.0)

    # -- recording -------------------------------------------------------------
    def _record(self, raw):
        """Add one arrival; True when it was new."""
        event = raw.get("event")
        if event == "StartJump":
            self._pending_star = (str(raw.get("StarSystem") or "").casefold(), str(raw.get("StarClass") or ""))
            return False
        if event not in ARRIVALS:
            return False
        position = _position(raw.get("StarPos"))
        system = str(raw.get("StarSystem") or "").strip()
        timestamp = str(raw.get("timestamp") or "")
        if position is None or not system or not timestamp:
            return False
        key = (timestamp, system.casefold())
        if key in self._keys:
            return False
        previous = self.rows[-1] if self.rows else None
        if event == "Location" and previous and str(previous[1]).casefold() == system.casefold():
            return False  # Logged in where the last jump left the ship.
        jump = raw.get("JumpDist")
        if jump is None and previous is not None:
            jump = math.dist(position, previous[2:5]) if event != "Location" else 0.0
        star = self._pending_star[1] if self._pending_star[0] == system.casefold() else ""
        self._pending_star = ("", "")
        row = [timestamp, system, round(position[0], 5), round(position[1], 5), round(position[2], 5),
               star, round(float(jump or 0.0), 2)]
        if previous is not None and timestamp < str(previous[0]):
            # An older journal read after newer ones: keep the list in time order.
            index = len(self.rows)
            while index and str(self.rows[index - 1][0]) > timestamp:
                index -= 1
            self.rows.insert(index, row)
        else:
            self.rows.append(row)
        self._keys.add(key)
        return True

    def observe(self, raw):
        """A live journal event."""
        if not isinstance(raw, dict):
            return False
        with self.lock:
            added = self._record(raw)
            if added:
                if len(self.rows) > MAX_ROWS:
                    del self.rows[:len(self.rows) - MAX_ROWS]
                self.revision += 1
        if added:
            self.save()
        return added

    def import_journals(self, journal_path, commander=None, fid=None):
        """Read every journal file not read before (or changed since)."""
        if not journal_path or not os.path.isdir(journal_path):
            return 0
        names = sorted((name for name in os.listdir(journal_path)
                        if name.startswith("Journal.") and name.endswith(".log")), key=journal_sort_key)
        added = 0
        for name in names:
            path = os.path.join(journal_path, name)
            try:
                signature = f"{os.path.getsize(path)}:{int(os.path.getmtime(path))}"
            except OSError:
                continue
            if self.files.get(name) == signature:
                continue
            active = not bool(commander or fid)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    lines = [line for line in handle if any(marker in line for marker in MARKERS)]
            except OSError:
                continue
            with self.lock:
                self._pending_star = ("", "")
                for line in lines:
                    try:
                        raw = json.loads(line)
                    except ValueError:
                        continue
                    if raw.get("event") in ("Commander", "LoadGame"):
                        active = commander_matches(raw, commander, fid)
                        continue
                    if active and self._record(raw):
                        added += 1
                self.files[name] = signature
        with self.lock:
            if len(self.rows) > MAX_ROWS:
                del self.rows[:len(self.rows) - MAX_ROWS]
            if added:
                self.revision += 1
        self.save(immediate=bool(added))
        return added

    # -- reading ---------------------------------------------------------------------
    def route_rows(self):
        """The journey as the atlas takes it, oldest first."""
        with self.lock:
            return [{"system": row[1], "pos": [row[2], row[3], row[4]], "timestamp": row[0],
                     "star_class": row[5], "jump_dist": row[6]} for row in self.rows]
