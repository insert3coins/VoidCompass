"""Remove the retired Watcher engine and models from the portable install."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil

from voidcompass.core.platform_support import application_dir


def retired_speech(memory):
    """Identify old generated lines without changing the saved conversation."""
    return {(str(row.get("topic") or ""), " ".join(str(row.get("text") or "").split()))
            for key in ("own_said", "liked", "disliked") for row in memory.get(key) or ()
            if isinstance(row, dict) and row.get("text")}


def written_log(memory):
    retired = retired_speech(memory)
    return [row for row in memory.get("log") or () if isinstance(row, list) and len(row) >= 3
            and row[1] != "mind_own" and (str(row[1]), " ".join(str(row[2]).split())) not in retired]


def _linked(path):
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def remove_retired_models(base=None):
    """Return bytes freed, or None when absent, linked or not removable.

    Only the install's models/llm directory is retired. Commander saves,
    speech recognition and the speaking voice are outside this target.
    """
    root = Path(base or application_dir()).resolve()
    models = root / "models"
    target = models / "llm"
    if not target.exists():
        return None
    if _linked(models) or _linked(target) or not target.is_dir():
        logging.warning("Retired Watcher model cleanup skipped a linked or non-directory path")
        return None
    expected = root / "models" / "llm"
    if target.resolve() != expected or target.resolve().parent != models.resolve():
        logging.warning("Retired Watcher model cleanup skipped a path outside the install")
        return None
    try:
        size = 0
        for folder, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [name for name in dirs if not _linked(Path(folder) / name)]
            for name in files:
                path = Path(folder) / name
                if not _linked(path):
                    size += path.stat().st_size
        shutil.rmtree(target)
        return size
    except OSError:
        logging.warning("Could not remove the retired Watcher model files", exc_info=True)
        return None


def cleanup_notice(size):
    if size is None:
        return ""
    amount = f"{size / (1024 ** 3):.1f} GB" if size >= 1024 ** 3 else f"{size / (1024 ** 2):.1f} MB"
    return f"Removed the retired Watcher model files and freed {amount}."
