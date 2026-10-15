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

import base64
from datetime import datetime, timezone
import json
import os
import re
import threading
import time
import uuid
import zlib

NOTE_MAX = 280
# "Not before…" (5.5.3.7): how long a capsule must wait, whatever happens.
# "date" waits for a day you choose (5.5.4).
WAITS = {"none": 0, "week": 7 * 86400, "month": 30 * 86400, "six_months": 182 * 86400, "year": 365 * 86400,
         "two_years": 730 * 86400, "date": 0}
SYSTEM_MAX = 100
CAPSULES_MAX = 500
# What kind of note it is (5.5.4): how it looks, and how it's handed back.
KINDS = ("note", "reminder", "warning", "memory", "greeting")

# Sharing (5.5.4). No server: a capsule (or a pack of them) travels as a
# code commanders pass around by hand, or as a .vccapsule file. A code is
# "VCCAP1-" + the capsules as compressed JSON in base64url + "-" + a CRC32,
# so a code mangled on the way is refused rather than misread.
CODE_PREFIX = "VCCAP1"
CODE_MAX = 64 * 1024
PACK_MAX = 50
FILE_FORMAT = "voidcompass-capsules"


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

    def leave(self, system, note, here="", wait="none", coords=None, kind="note", target="", opens_on=None):
        """Seal a note for ``system``, not to open for ``wait`` (a WAITS
        key, or "date" with ``opens_on`` a unix time), with the system's
        [x, y, z] when known (for the minimap). ``target`` names a station
        or body in it: then it opens only when you dock or land there. The
        capsule, or None when it can't be."""
        system, note = _clean(system, SYSTEM_MAX), _clean(note, NOTE_MAX)
        if not system or not note:
            return None
        not_before = None
        if wait == "date":
            try:
                not_before = float(opens_on) if opens_on and float(opens_on) > self.clock() else None
            except (TypeError, ValueError):
                not_before = None
        try:
            coords = [round(float(value), 3) for value in coords][:3] if coords else None
        except (TypeError, ValueError):
            coords = None
        with self._lock:
            rows = self._load()
            if sum(1 for row in rows if not row.get("opened_at")) >= CAPSULES_MAX:
                return None
            now = round(self.clock(), 1)
            if not_before is None and WAITS.get(str(wait), 0):
                not_before = now + WAITS[str(wait)]
            capsule = {"id": uuid.uuid4().hex[:12], "system": system, "note": note, "left_at": now,
                       "left_from": _clean(here, SYSTEM_MAX), "opened_at": None, "not_before": not_before,
                       "coords": coords if coords and len(coords) == 3 else None,
                       "kind": kind if kind in KINDS else "note", "target": _clean(target, SYSTEM_MAX)}
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

    def deliver(self, system, arrived_at=None, place=None):
        """Arrived at ``system``: the sealed capsules left for it before you
        got here are opened (oldest first) and returned. A capsule for a
        station or body there opens only when ``place`` (where you docked or
        landed) is it; one for the whole system, only without a place."""
        key = _clean(system, SYSTEM_MAX).casefold()
        place_key = _clean(place, SYSTEM_MAX).casefold()
        arrived_at = float(arrived_at if arrived_at is not None else self.clock())
        if not key:
            return []
        with self._lock:
            rows = self._load()
            opened = []
            for row in sorted(rows, key=lambda item: float(item.get("left_at") or 0)):
                if row.get("opened_at") or str(row.get("system")).casefold() != key:
                    continue
                target = _clean(row.get("target"), SYSTEM_MAX).casefold()
                if target != place_key and not (target and place_key and place_key.endswith(target)):
                    continue  # it waits for its own station or body, or for the system itself
                if float(row.get("left_at") or 0) >= arrived_at:
                    continue  # left after this arrival (an old journal read late)
                if row.get("not_before") and float(row["not_before"]) > arrived_at:
                    continue  # not yet: "Not before…"
                row["opened_at"] = round(self.clock(), 1)
                opened.append(dict(row))
            if opened:
                self._save()
        return opened


    def waiting_here(self, system):
        """Sealed capsules in this system that wait for a station or body."""
        key = _clean(system, SYSTEM_MAX).casefold()
        with self._lock:
            return [dict(row) for row in self._load() if not row.get("opened_at")
                    and str(row.get("system")).casefold() == key and row.get("target")]

    def reseal(self, capsule_id, wait="none", opens_on=None):
        """An opened capsule, sealed again for another visit."""
        with self._lock:
            row = next((dict(row) for row in self._load() if row.get("id") == capsule_id), None)
        if row is None:
            return None
        return self.leave(row["system"], row["note"], here=row.get("left_from") or "", wait=wait, opens_on=opens_on,
                          coords=row.get("coords"), kind=row.get("kind") or "note", target=row.get("target") or "")

    def find(self, ids):
        wanted = set(ids or ())
        with self._lock:
            return [dict(row) for row in self._load() if row.get("id") in wanted]

    def receive(self, capsules, now=None):
        """Capsules shared by another commander (decode() rows): sealed for
        their system like your own, with who sent them. Ones already here
        are skipped. How many were added."""
        now = round(float(now if now is not None else self.clock()), 1)
        added = 0
        with self._lock:
            rows = self._load()
            known = {row.get("share_id") for row in rows if row.get("share_id")}
            for capsule in capsules or ():
                if capsule["share_id"] in known:
                    continue
                if sum(1 for row in rows if not row.get("opened_at")) >= CAPSULES_MAX:
                    break
                rows.append({"id": uuid.uuid4().hex[:12], "system": capsule["system"], "note": capsule["note"],
                             "left_at": capsule["left_at"], "left_from": "", "opened_at": None,
                             "not_before": capsule["not_before"], "coords": capsule["coords"],
                             "kind": capsule["kind"], "target": capsule["target"], "sender": capsule["sender"],
                             "share_id": capsule["share_id"], "received_at": now})
                known.add(capsule["share_id"])
                added += 1
            if added and not self._save():
                return 0
        return added

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


# -- sharing (5.5.4) ---------------------------------------------------------
def _share_row(row, sender=""):
    """A capsule as it travels: short keys, and nothing about where you were."""
    return {"s": row["system"], "n": row["note"], "t": row.get("target") or "", "k": row.get("kind") or "note",
            "l": round(float(row.get("left_at") or 0)),
            "w": round(float(row["not_before"])) if row.get("not_before") else None,
            "c": row.get("coords"), "i": row.get("share_id") or str(row.get("id")),
            "f": _clean(sender or row.get("sender"), 60)}


def _from_share(item):
    """One shared capsule, checked, as receive() takes it; None if it isn't one."""
    if not isinstance(item, dict):
        return None
    system, note = _clean(item.get("s"), SYSTEM_MAX), _clean(item.get("n"), NOTE_MAX)
    share_id = re.sub(r"[^0-9A-Za-z_-]", "", str(item.get("i") or ""))[:40]
    if not system or not note or not share_id:
        return None
    coords = item.get("c")
    try:
        coords = [round(float(value), 3) for value in coords][:3] if isinstance(coords, list) and len(coords) >= 3 else None
        left_at = float(item.get("l") or 0)
        not_before = float(item["w"]) if item.get("w") else None
    except (TypeError, ValueError):
        return None
    kind = str(item.get("k") or "note")
    return {"system": system, "note": note, "target": _clean(item.get("t"), SYSTEM_MAX),
            "kind": kind if kind in KINDS else "note", "left_at": left_at, "not_before": not_before,
            "coords": coords, "share_id": share_id, "sender": _clean(item.get("f"), 60)}


def encode(rows, sender=""):
    """A share code for these capsules (one, or a pack of up to PACK_MAX)."""
    payload = [_share_row(row, sender) for row in list(rows)[:PACK_MAX]]
    packed = zlib.compress(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)
    body = base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")
    return f"{CODE_PREFIX}-{body}-{zlib.crc32(body.encode('ascii')):08x}"


def decode(text):
    """The capsules in a share code, or a .vccapsule file's text: (capsules,
    problem). The code may sit inside a longer message (a Discord post)."""
    text = str(text or "")[:CODE_MAX * 2].strip()
    if not text:
        return [], "Paste a capsule code, or choose a .vccapsule file."
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            return [], "That file isn't a capsule file."
        if not isinstance(data, dict) or data.get("format") != FILE_FORMAT:
            return [], "That file isn't a capsule file."
        items = data.get("capsules") if isinstance(data.get("capsules"), list) else []
    else:
        match = re.search(CODE_PREFIX + r"-([A-Za-z0-9_-]+)-([0-9a-f]{8})", text)
        if not match:
            return [], "No capsule code there. A code starts with VCCAP1-."
        body, check = match.groups()
        if len(body) > CODE_MAX:
            return [], "That code is too long to be a capsule."
        if f"{zlib.crc32(body.encode('ascii')):08x}" != check:
            return [], "That code was damaged on the way: part of it is missing or changed."
        try:
            unpack = zlib.decompressobj()
            raw = unpack.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)), CODE_MAX * 4)
            items = json.loads(raw.decode("utf-8"))
        except (ValueError, zlib.error, UnicodeDecodeError):
            return [], "That code couldn't be read."
    items = items if isinstance(items, list) else []
    capsules = [capsule for capsule in (_from_share(item) for item in items[:PACK_MAX]) if capsule]
    return capsules, "" if capsules else "There are no capsules in that."


def export_file(rows, sender=""):
    """A .vccapsule file's text: readable JSON, the same capsules as a code."""
    return json.dumps({"format": FILE_FORMAT, "version": 1, "from": _clean(sender, 60),
                       "exported": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "capsules": [_share_row(row, sender) for row in list(rows)[:PACK_MAX]]},
                      indent=1, ensure_ascii=False)


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
