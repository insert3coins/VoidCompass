"""Presentation-neutral first-commissioning state helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from voidcompass.core.platform_support import detect_elite_journal_path

# Journal.2026-09-10T101500.01.log (Odyssey) and Journal.200910101500.01.log (older).
_NEW_NAME = re.compile(r"^Journal\.(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})\.\d+\.log$")
_OLD_NAME = re.compile(r"^Journal\.(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\.\d+\.log$")
_TAIL_BYTES = 2 * 1024 * 1024


def should_show(config):
    """Return whether the HTML First Commissioning deck must be presented."""
    return not bool((config or {}).get("onboarding_complete", False))


def _journal_date(path: Path):
    match = _NEW_NAME.match(path.name)
    if match:
        parts = [int(part) for part in match.groups()]
    else:
        match = _OLD_NAME.match(path.name)
        if not match:
            return None
        parts = [int(part) for part in match.groups()]
        parts[0] += 2000
    try:
        return datetime(*parts, tzinfo=timezone.utc)
    except ValueError:
        return None


def _journal_order(path: Path):
    stamp = _journal_date(path)
    if stamp is not None:
        return stamp.timestamp(), path.name
    try:
        return path.stat().st_mtime, path.name
    except OSError:
        return 0.0, path.name


def _tail_events(path: Path):
    """The newest journal's last events, newest first."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as source:
            source.seek(max(0, size - _TAIL_BYTES))
            lines = source.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    if size > _TAIL_BYTES and lines:
        lines = lines[1:]
    events = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            events.append(row)
    return events


def probe_journal_folder(path=""):
    """What the setup screen shows about a journal folder, read-only.

    An empty path is the folder Elite uses on this PC. Reports how many
    journals there are, the span they cover, and, from the newest journal,
    the commander, ship and last system: enough to tell the right folder at
    a glance without reading the whole history.
    """
    text = str(path or "").strip()
    auto = not text
    if auto:
        text = detect_elite_journal_path()
    result = {
        "path": text, "auto": auto, "status": "missing", "journals": 0,
        "first": "", "latest": "", "commander": "", "ship": "", "ship_name": "",
        "system": "", "mode": "", "live_status": False, "message": "",
    }
    if not text:
        result["message"] = "Elite Dangerous journals were not found in the usual place. Browse to the folder that holds Journal.*.log."
        return result
    folder = Path(text).expanduser()
    if not folder.is_absolute():
        result.update(status="invalid", message="Use the full folder path, such as C:\\Users\\…\\Saved Games\\Frontier Developments\\Elite Dangerous.")
        return result
    if not folder.is_dir():
        result["message"] = "That folder does not exist."
        return result
    try:
        journals = sorted((item for item in folder.iterdir()
                           if item.is_file() and item.name.startswith("Journal.") and item.suffix == ".log"), key=_journal_order)
    except OSError as exc:
        result.update(status="invalid", message=f"The folder could not be read: {exc.strerror or exc}.")
        return result
    result["live_status"] = (folder / "Status.json").is_file()
    if not journals:
        result.update(status="empty", message="The folder exists but holds no Journal.*.log files yet. Play once and they appear.")
        return result
    first, latest = _journal_date(journals[0]), _journal_date(journals[-1])
    result.update(status="ok", journals=len(journals),
                  first=first.date().isoformat() if first else "", latest=latest.date().isoformat() if latest else "")
    for row in _tail_events(journals[-1]):
        event = row.get("event")
        if event in {"FSDJump", "Location", "CarrierJump"} and not result["system"]:
            result["system"] = str(row.get("StarSystem") or "")
        elif event == "LoadGame" and not result["commander"]:
            result.update(commander=str(row.get("Commander") or ""), mode=str(row.get("GameMode") or ""),
                          ship=str(row.get("Ship_Localised") or row.get("Ship") or ""), ship_name=str(row.get("ShipName") or ""))
        elif event == "Commander" and not result["commander"]:
            result["commander"] = str(row.get("Name") or "")
        if result["system"] and result["commander"]:
            break
    result["message"] = "Journals found. Void Compass reads them; it never changes them."
    return result
