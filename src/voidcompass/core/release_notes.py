"""This release's notes, read from the update log for the boot screen.

mini-readme.md is the update log: its first section is the current release
("## v5.4.9.6 // Title", a release date, then one bullet per change). The
build bundles it, so source and packaged runs read the same file. Notes are
only returned when that section is this version's, so a stale log never
presents an older release as new.
"""

from __future__ import annotations

import re
from pathlib import Path

from voidcompass.core.paths import resource_path

_HEADING = re.compile(r"^##\s+v(?P<version>[0-9][\w.]*)\s*//\s*(?P<title>.+?)\s*$")
_DATE = re.compile(r"^\*\*Release Date:\*\*\s*(?P<date>.+?)\s*$")
_BULLET = re.compile(r"^\s*[*-]\s+(?P<text>.+?)\s*$")
_MARKUP = re.compile(r"\*\*|__|`")
MAX_NOTES = 8
MAX_NOTE_LENGTH = 600


def current_release(version, path=None):
    """Return {version, title, date, notes} for this version, or None."""
    source = Path(path) if path is not None else resource_path("mini-readme.md")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    release = None
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            if release is not None:
                break
            release = {
                "version": heading["version"],
                "title": _MARKUP.sub("", heading["title"]),
                "date": "",
                "notes": [],
            }
            continue
        if release is None:
            continue
        if line.startswith("## "):
            break
        date = _DATE.match(line)
        if date:
            release["date"] = date["date"]
            continue
        bullet = _BULLET.match(line)
        if bullet and len(release["notes"]) < MAX_NOTES:
            release["notes"].append(_MARKUP.sub("", bullet["text"])[:MAX_NOTE_LENGTH])
    if release is None or release["version"] != str(version or "").strip():
        return None
    return release
