"""Presentation-neutral first-commissioning state helpers."""

from __future__ import annotations

from pathlib import Path

from voidcompass.core.journal_files import journal_date, latest_session, list_journals
from voidcompass.core.platform_support import detect_elite_journal_path


def should_show(config):
    """Return whether the HTML First Commissioning deck must be presented."""
    return not bool((config or {}).get("onboarding_complete", False))


def probe_journal_folder(path=""):
    """What the setup screen shows about a journal folder, read-only.

    An empty path is the folder Elite uses on this PC. Reports how many
    journals there are, the span they cover, and the commander, ship and
    last system from the newest journals that have them: enough to tell the
    right folder at a glance.
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
        next(folder.iterdir(), None)
    except OSError as exc:
        result.update(status="invalid", message=f"The folder could not be read: {exc.strerror or exc}.")
        return result
    journals = list_journals(folder)
    result["live_status"] = (folder / "Status.json").is_file()
    if not journals:
        result.update(status="empty", message="The folder exists but holds no Journal.*.log files yet. Play once and they appear.")
        return result
    first, latest = journal_date(journals[0]), journal_date(journals[-1])
    result.update(status="ok", journals=len(journals),
                  first=first.date().isoformat() if first else "", latest=latest.date().isoformat() if latest else "")
    # The newest journal may be a launch that never left the main menu; the
    # commander and their last system come from the newest journals that
    # have them, as the app itself finds them.
    session = latest_session(str(folder))
    result.update({key: session.get(key) or "" for key in ("commander", "ship", "ship_name", "mode", "system")})
    result["message"] = "Journals found. Void Compass reads them; it never changes them."
    return result
