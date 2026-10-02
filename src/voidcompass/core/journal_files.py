"""Frontier journal files: their real order, and what the newest session says.

Elite has named journals two ways: ``Journal.YYMMDDHHMMSS.NN.log`` until early
2022 and ``Journal.YYYY-MM-DDTHHMMSS.NN.log`` since. Sorted by name the two
interleave wrongly (a 2021 journal sorts after every 2026 one), so anything
that wants "the newest journal" or history in order sorts with
:func:`journal_sort_key`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re

_NEW_NAME = re.compile(r"^Journal\.(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})\.(\d+)\.log$")
_OLD_NAME = re.compile(r"^Journal\.(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\.(\d+)\.log$")
# Events that name the commander, and those that say where they last were.
# Matched as quoted names first (a cheap filter on any spacing), then by the
# parsed event.
_COMMANDER_EVENTS = ('"LoadGame"', '"Commander"')
_LOCATION_EVENTS = ('"FSDJump"', '"Location"', '"CarrierJump"')


def is_journal_name(name) -> bool:
    name = os.path.basename(str(name or ""))
    return name.startswith("Journal.") and name.endswith(".log")


def _stamp(name):
    match = _NEW_NAME.match(name)
    if match:
        year, month, day, hour, minute, second, part = match.groups()
        return f"{year}-{month}-{day}T{hour}{minute}{second}", int(part)
    match = _OLD_NAME.match(name)
    if match:
        year, month, day, hour, minute, second, part = match.groups()
        return f"20{year}-{month}-{day}T{hour}{minute}{second}", int(part)
    return None


def journal_sort_key(path):
    """Chronological sort key for a journal path or file name. Names in
    neither format sort first, by name."""
    name = os.path.basename(str(path or ""))
    stamp = _stamp(name)
    return (stamp[0], stamp[1], name) if stamp else ("", 0, name)


def journal_date(path):
    """The UTC time a journal was started, from its name, or None."""
    stamp = _stamp(os.path.basename(str(path or "")))
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp[0], "%Y-%m-%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def list_journals(folder) -> list[str]:
    """Every journal in a folder, oldest first, as full paths."""
    try:
        names = [name for name in os.listdir(folder) if is_journal_name(name)]
    except (OSError, TypeError):
        return []
    return [os.path.join(folder, name) for name in sorted(names, key=journal_sort_key)]


def _events(path, markers):
    """The file's events whose line carries one of ``markers``, in order."""
    found = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as source:
            for line in source:
                if any(marker in line for marker in markers):
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        found.append(row)
    except OSError:
        return []
    return found


def latest_session(folder, max_files=40) -> dict:
    """Who last played and where they were, from the newest journals.

    The newest journal is often no help on its own: a launch that never left
    the main menu has no commander in it, and the commander is written at
    the top of a journal that can run to megabytes. This walks back from the
    newest journal (at most ``max_files``) and reads each whole, taking the
    last commander event and the last arrival it finds.
    """
    result = {"commander": "", "fid": "", "ship": "", "ship_name": "", "mode": "", "journal_file": "", "system": ""}
    for path in reversed(list_journals(folder)[-max(1, int(max_files)):]):
        rows = _events(path, _COMMANDER_EVENTS + (() if result["system"] else _LOCATION_EVENTS))
        if not result["system"]:
            arrival = next((row for row in reversed(rows) if row.get("event") in {"FSDJump", "Location", "CarrierJump"}
                            and row.get("StarSystem")), None)
            if arrival:
                result["system"] = str(arrival["StarSystem"])
        if not result["commander"]:
            event = next((row for row in reversed(rows) if row.get("event") in {"LoadGame", "Commander"}
                          and (row.get("Commander") or row.get("Name"))), None)
            if event:
                result.update(commander=str(event.get("Commander") or event.get("Name") or ""),
                              fid=str(event.get("FID") or ""), journal_file=path)
                if event.get("event") == "LoadGame":
                    result.update(ship=str(event.get("Ship_Localised") or event.get("Ship") or ""),
                                  ship_name=str(event.get("ShipName") or ""), mode=str(event.get("GameMode") or ""))
        if result["commander"] and result["system"]:
            break
    return result


# The commander's standing, written at the top of every session: replayed on
# a first run so a new profile starts with its ranks, credits and ship.
SESSION_HEADER_EVENTS = (
    "Commander", "Materials", "Rank", "Progress", "Reputation", "EngineerProgress",
    "SquadronStartup", "LoadGame", "Statistics", "Powerplay", "Missions", "Loadout", "Cargo", "ShipLocker",
)


def session_header(folder, live_journal="", skip_tail_bytes=0, max_files=40) -> list[dict]:
    """The newest session's header events (the last of each kind), in file order.

    A session starts at its Commander event, just before LoadGame. When the
    newest session is in the live journal, only what comes before its last
    ``skip_tail_bytes`` is returned: the watcher replays that tail itself, and
    if the session started inside the tail there is nothing to add.
    """
    markers = tuple(f'"{name}"' for name in SESSION_HEADER_EVENTS)
    live = os.path.normcase(os.path.abspath(live_journal)) if live_journal else ""
    for path in reversed(list_journals(folder)[-max(1, int(max_files)):]):
        rows = []
        try:
            with open(path, "rb") as source:
                offset = 0
                for raw in source:
                    offset += len(raw)
                    line = raw.decode("utf-8", errors="ignore")
                    if any(marker in line for marker in markers):
                        try:
                            row = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(row, dict) and row.get("event") in SESSION_HEADER_EVENTS:
                            rows.append((offset, row))
            size = offset
        except OSError:
            continue
        loads = [index for index, (_, row) in enumerate(rows) if row.get("event") == "LoadGame"]
        if not loads:
            continue  # a launch that never left the main menu
        first = loads[-1]
        commanders = [index for index in range(first) if rows[index][1].get("event") == "Commander"]
        if commanders:
            first = commanders[-1]
        if live and os.path.normcase(os.path.abspath(path)) == live:
            limit = max(0, size - int(skip_tail_bytes))
            if rows[first][0] > limit:
                return []
            rows = [entry for entry in rows if entry[0] <= limit]
        session = [row for _, row in rows[first:]]
        latest = {row["event"]: index for index, row in enumerate(session)}
        return [session[index] for index in sorted(latest.values())]
    return []
