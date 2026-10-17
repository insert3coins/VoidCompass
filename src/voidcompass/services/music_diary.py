"""The music diary (5.5.10): what played, and when, for each commander.

The Music page reports each track as it starts; the diary keeps one row per
track started: ``[unix time, track id, title, artist, album]``. The Flight
Recorder plays a past session's music again from it, and Void Wrapped finds
your soundtrack of the year. Nothing is kept from before 5.5.10.
"""
from __future__ import annotations

import bisect
import json
import os
import threading

from voidcompass.core.persistence_queue import persistence_queue

MAX_ROWS = 40_000
# The same track reported again this soon is the same play (a pause, a seek).
SAME_PLAY_S = 90.0


class MusicDiary:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.rows = []
        self.revision = 0
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        rows = [row for row in (data or {}).get("rows") or [] if isinstance(row, list) and len(row) >= 5]
        with self.lock:
            self.rows = sorted(rows, key=lambda row: float(row[0] or 0))[-MAX_ROWS:]
            self.revision += 1

    def _payload(self):
        with self.lock:
            return {"schema": 1, "rows": list(self.rows)}

    def save(self):
        if self.path:
            persistence_queue().submit_json(self.path, source=self._payload, indent=None, delay_s=2.0)

    def note(self, when, track_id, title="", artist="", album=""):
        """A track started playing. True when it's a new play."""
        track_id = str(track_id or "")[:16]
        if not track_id:
            return False
        with self.lock:
            last = self.rows[-1] if self.rows else None
            if last and last[1] == track_id and float(when) - float(last[0]) < SAME_PLAY_S:
                return False
            self.rows.append([round(float(when), 1), track_id, str(title or "")[:200], str(artist or "")[:200],
                              str(album or "")[:200]])
            if len(self.rows) > MAX_ROWS:
                del self.rows[:len(self.rows) - MAX_ROWS]
            self.revision += 1
        self.save()
        return True

    def between(self, start, end):
        """The plays started from ``start`` to ``end`` (unix times), oldest first."""
        with self.lock:
            times = [float(row[0]) for row in self.rows]
            low, high = bisect.bisect_left(times, float(start)), bisect.bisect_right(times, float(end))
            return [list(row) for row in self.rows[low:high]]

    def playing_at(self, moment):
        """The play that was going at ``moment`` (the last one started before it)."""
        with self.lock:
            times = [float(row[0]) for row in self.rows]
            index = bisect.bisect_right(times, float(moment)) - 1
            return list(self.rows[index]) if index >= 0 else None
