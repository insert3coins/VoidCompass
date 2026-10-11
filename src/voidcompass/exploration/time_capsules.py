"""Time capsules and On this day (5.5.3.7).

A time capsule is a note you leave for a system ("Bring the SRV next time",
"The carrier's tritium is here"). It stays sealed until you next arrive
there, a week or years later, and then it is handed back to you: by the
Watcher when its thoughts are on, otherwise as a notice. Each commander has
their own, in capsules.json in their profile folder.

On this day looks back through the travel history: where you were on this
date one, two, three years ago, how far you flew that day.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import threading
import time
import uuid

NOTE_MAX = 280
# "Not before…" (5.5.3.7): how long a capsule must wait, whatever happens.
WAITS = {"none": 0, "week": 7 * 86400, "month": 30 * 86400, "year": 365 * 86400}
SYSTEM_MAX = 100
CAPSULES_MAX = 500


def _clean(text, limit):
    return " ".join(str(text or "").split())[:limit]


def span_text(seconds):
    """How long, in words: '3 days', '2 months', '1 year, 3 months'."""
    seconds = max(0.0, float(seconds or 0))
    days = int(seconds // 86400)
    if days < 1:
        hours = int(seconds // 3600)
        if hours < 1:
            return "a few minutes"
        return "an hour" if hours == 1 else f"{hours} hours"
    if days < 14:
        return "a day" if days == 1 else f"{days} days"
    if days < 60:
        weeks = days // 7
        return f"{weeks} weeks"
    months = int(days // 30.44)
    if months < 12:
        return f"{months} months"
    years, months = divmod(months, 12)
    head = "a year" if years == 1 else f"{years} years"
    return f"{head}, {months} month{'' if months == 1 else 's'}" if months else head


def _epoch(stamp):
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


class CapsuleStore:
    """One commander's time capsules: [{id, system, note, left_at,
    left_from, opened_at}] in capsules.json (``folder`` is a callable giving
    the commander's profile folder, which changes with the commander)."""

    def __init__(self, folder, clock=time.time):
        self._folder = folder
        self.clock = clock
        self._lock = threading.Lock()
        self._path = None
        self._rows = []

    def _load(self):
        path = os.path.join(str(self._folder()), "capsules.json")
        if path != self._path:
            self._path = path
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                data = []
            self._rows = [row for row in (data if isinstance(data, list) else ())
                          if isinstance(row, dict) and row.get("id") and row.get("system") and row.get("note")]
        return self._rows

    def _save(self):
        temporary = self._path + ".part"
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self._rows, handle, indent=1)
            os.replace(temporary, self._path)
            return True
        except OSError:
            return False

    def rows(self):
        """Newest first."""
        with self._lock:
            return sorted((dict(row) for row in self._load()), key=lambda row: -float(row.get("left_at") or 0))

    def leave(self, system, note, here="", wait="none", coords=None):
        """Seal a note for ``system``, not to open for ``wait`` (a WAITS
        key), with the system's [x, y, z] when known (for the minimap). The
        capsule, or None when it can't be."""
        system, note = _clean(system, SYSTEM_MAX), _clean(note, NOTE_MAX)
        if not system or not note:
            return None
        try:
            coords = [round(float(value), 3) for value in coords][:3] if coords else None
        except (TypeError, ValueError):
            coords = None
        with self._lock:
            rows = self._load()
            if sum(1 for row in rows if not row.get("opened_at")) >= CAPSULES_MAX:
                return None
            now = round(self.clock(), 1)
            capsule = {"id": uuid.uuid4().hex[:12], "system": system, "note": note, "left_at": now,
                       "left_from": _clean(here, SYSTEM_MAX), "opened_at": None,
                       "not_before": now + WAITS.get(str(wait), 0) if WAITS.get(str(wait), 0) else None,
                       "coords": coords if coords and len(coords) == 3 else None}
            rows.append(capsule)
            if not self._save():
                rows.remove(capsule)
                return None
        return dict(capsule)

    def remove(self, capsule_id):
        with self._lock:
            rows = self._load()
            kept = [row for row in rows if row.get("id") != capsule_id]
            if len(kept) == len(rows):
                return False
            rows[:] = kept
            return self._save()

    def deliver(self, system, arrived_at=None):
        """Arrived at ``system``: the sealed capsules left for it before you
        got here are opened (oldest first) and returned."""
        key = _clean(system, SYSTEM_MAX).casefold()
        arrived_at = float(arrived_at if arrived_at is not None else self.clock())
        if not key:
            return []
        with self._lock:
            rows = self._load()
            opened = []
            for row in sorted(rows, key=lambda item: float(item.get("left_at") or 0)):
                if row.get("opened_at") or str(row.get("system")).casefold() != key:
                    continue
                if float(row.get("left_at") or 0) >= arrived_at:
                    continue  # left after this arrival (an old journal read late)
                if row.get("not_before") and float(row["not_before"]) > arrived_at:
                    continue  # not yet: "Not before…"
                row["opened_at"] = round(self.clock(), 1)
                opened.append(dict(row))
            if opened:
                self._save()
        return opened


    def early(self, system, arrived_at=None):
        """The sealed capsules here that aren't ready yet ("Not before…")."""
        key = _clean(system, SYSTEM_MAX).casefold()
        arrived_at = float(arrived_at if arrived_at is not None else self.clock())
        with self._lock:
            return [dict(row) for row in self._load() if not row.get("opened_at")
                    and str(row.get("system")).casefold() == key and row.get("not_before")
                    and float(row["not_before"]) > arrived_at >= float(row.get("left_at") or 0)]

    def set_coords(self, system, coords):
        """Where a sealed capsule's system is, once known (for the minimap)."""
        key = _clean(system, SYSTEM_MAX).casefold()
        changed = False
        with self._lock:
            for row in self._load():
                if not row.get("coords") and str(row.get("system")).casefold() == key:
                    row["coords"] = [round(float(value), 3) for value in coords][:3]
                    changed = True
            if changed:
                self._save()
        return changed


def on_this_day(rows, today=None):
    """Where you were on this date in years gone by, from the travel history
    rows ([timestamp, system, x, y, z, star, jump, kind], oldest first):
    newest year first, {years, date, first, last, systems, jumps, distance}.
    Dates are your own (local) days."""
    today = today or datetime.now().astimezone()
    days = {}
    for row in rows or ():
        try:
            moment = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
        except (TypeError, ValueError, IndexError):
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        local = moment.astimezone(today.tzinfo)
        if (local.month, local.day) != (today.month, today.day) or local.year >= today.year:
            continue
        day = days.setdefault(local.year, {"systems": [], "jumps": 0, "distance": 0.0})
        name = str(row[1])
        if not day["systems"] or day["systems"][-1] != name:
            day["systems"].append(name)
        if len(row) > 7 and row[7] in ("", None):
            day["jumps"] += 1
            try:
                day["distance"] += float(row[6] or 0)
            except (TypeError, ValueError):
                pass
    out = []
    for year in sorted(days, reverse=True):
        day = days[year]
        out.append({"years": today.year - year, "date": f"{year:04d}-{today.month:02d}-{today.day:02d}",
                    "first": day["systems"][0], "last": day["systems"][-1], "systems": len(set(day["systems"])),
                    "jumps": day["jumps"], "distance": round(day["distance"], 1)})
    return out


def years_text(years):
    return "a year ago" if years == 1 else f"{years} years ago"
