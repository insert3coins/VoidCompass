"""Older postcards made editable (5.5.4).

Postcards saved before 5.5.4 have no card beside them, only the finished
picture. Its file name still says where and when it was saved, so the
journal's Screenshot event from that moment gives the card back (the place,
the coordinates, the date), and the screenshot itself is usually still in
the screenshot folder: the game's BMP, or the converter's PNG named after the
system and the time. With neither, the card is made from the file name alone
and can be given a picture by hand.
"""
from __future__ import annotations

import datetime as _datetime
import json
import os
import re
import time

from voidcompass.core.journal_files import journal_date, list_journals

# The postcard is saved a few seconds after the screenshot (the picture is
# waited for); the converter names its PNG by the BMP's own time.
MATCH_WINDOW_S = 240
PICTURE_WINDOW_S = 90
_STAMP = re.compile(r"(\d{4}-\d\d-\d\d) (\d\d)-(\d\d)-(\d\d)")
_PNG_STAMP = re.compile(r"_(\d{4}-\d\d-\d\d)_(\d\d)-(\d\d)-(\d\d)(?:_\d+)?\.png$", re.I)


def saved_at(filename):
    """When a postcard was saved, from ``Postcard - <title> - <stamp>.png``
    (local time), as epoch seconds; None if the name doesn't say."""
    match = _STAMP.search(str(filename or ""))
    if not match:
        return None
    day, hour, minute, second = match.groups()
    try:
        return time.mktime(time.strptime(f"{day} {hour}:{minute}:{second}", "%Y-%m-%d %H:%M:%S"))
    except (ValueError, OverflowError):
        return None


def _epoch(stamp):
    try:
        moment = _datetime.datetime.strptime(str(stamp)[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return moment.replace(tzinfo=_datetime.timezone.utc).timestamp()


class ScreenshotIndex:
    """Every Screenshot event in the journals, read once: (epoch, event,
    the position of the system it was taken in, or None)."""

    def __init__(self, journal_folder, moments=()):
        self.folder = str(journal_folder or "")
        # Only journals begun up to a few days before the earliest postcard
        # (a long session) and before the latest need reading.
        moments = [moment for moment in moments if moment]
        # Note: a journal's name is your local time, read as UTC; a day's
        # slack either way keeps time zones far from UTC in (NZ is +12/+13).
        self._bounds = (min(moments) - 4 * 86400, max(moments) + 86400) if moments else None
        self._events = None

    def _wanted(self, path):
        if self._bounds is None:
            return True
        started = journal_date(path)
        return started is None or self._bounds[0] <= started.timestamp() <= self._bounds[1]

    def events(self):
        if self._events is None:
            found = []
            for path in filter(self._wanted, list_journals(self.folder)):
                position = None
                try:
                    with open(path, encoding="utf-8", errors="ignore") as source:
                        for line in source:
                            if '"StarPos"' in line or '"Screenshot"' in line:
                                try:
                                    row = json.loads(line)
                                except ValueError:
                                    continue
                                if row.get("event") == "Screenshot":
                                    at = _epoch(row.get("timestamp"))
                                    if at is not None:
                                        found.append((at, row, position))
                                elif isinstance(row.get("StarPos"), list) and len(row["StarPos"]) == 3:
                                    position = tuple(float(value) for value in row["StarPos"])
                except OSError:
                    continue
            self._events = found
        return self._events

    def near(self, moment, title=""):
        """The screenshot taken just before ``moment`` (the postcard follows
        it), preferring one whose body or system is the postcard's title."""
        wanted = str(title or "").casefold()
        best = None
        for at, row, position in self.events():
            gap = moment - at
            if not -30 <= gap <= MATCH_WINDOW_S:
                continue
            named = wanted and wanted in {str(row.get("Body") or "").casefold(), str(row.get("System") or "").casefold()}
            score = (0 if named else 1, abs(gap))
            if best is None or score < best[0]:
                best = (score, at, row, position)
        return best[1:] if best else None


def find_picture(folder, event, taken_at):
    """The screenshot itself: the game's BMP by name, or the converter's PNG
    (``<System>_<date>_<time>.png``) from about then."""
    if not folder or not os.path.isdir(folder):
        return None
    name = os.path.basename(str((event or {}).get("Filename") or "").replace("\\", "/"))
    if name and os.path.isfile(os.path.join(folder, name)):
        return os.path.join(folder, name)
    system = "".join(char for char in str((event or {}).get("System") or "") if char.isalnum() or char in " -_()").strip()
    best = None
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    for candidate in names:
        match = _PNG_STAMP.search(candidate)
        if match is None:
            continue
        day, hour, minute, second = match.groups()
        try:
            at = time.mktime(time.strptime(f"{day} {hour}:{minute}:{second}", "%Y-%m-%d %H:%M:%S"))
        except (ValueError, OverflowError):
            continue
        gap = abs(at - taken_at)
        if gap > PICTURE_WINDOW_S:
            continue
        score = (0 if system and candidate.casefold().startswith(system.casefold()) else 1, gap)
        if best is None or score < best[0]:
            best = (score, os.path.join(folder, candidate))
    return best[1] if best else None
