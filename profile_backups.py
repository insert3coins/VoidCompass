"""SQLite-safe commander profile snapshots and restart-time restore handling."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sqlite3
import time

from platform_support import application_dir


BACKUP_ROOT = Path(application_dir()) / "backups"
RESTORE_MARKER = Path(application_dir()) / ".profile_restore.json"
SKIP_NAMES = {"session.active"}


def _copy_file(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.casefold() in {".db", ".sqlite", ".sqlite3"}:
        src = sqlite3.connect(str(source), timeout=10.0)
        dst = sqlite3.connect(str(target), timeout=10.0)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    else:
        shutil.copy2(source, target)


def snapshot_profile(source, destination):
    """Create a consistent profile directory snapshot, including live WAL databases."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Profile folder not found: {source}")
    if source == destination or source in destination.parents:
        raise ValueError("The backup destination must be outside the profile folder.")
    if destination.exists():
        raise FileExistsError(f"Backup already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            if path.name in SKIP_NAMES or path.name.endswith(("-wal", "-shm")):
                continue
            target = destination / relative
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                _copy_file(path, target)
        manifest = {
            "schema": 1, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source": str(source),
        }
        (destination / "backup_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return str(destination)


def validate_backup(path):
    path = Path(path)
    if not path.is_dir():
        return False, "The selected backup folder does not exist."
    files = [row for row in path.iterdir() if row.is_file()]
    if not files:
        return False, "The selected folder contains no profile files."
    if not any(row.name in {"config.json", "companion_state.json", "exploration_data.db",
                            "captains_log.json", "deep_survey.json"} for row in files):
        return False, "This does not look like a VoidCompass profile backup."
    return True, "Backup is valid."


def automatic_backup(profile_key, profile_dir, reason="automatic", keep=5):
    """Create a bounded internal snapshot; repeated same-reason runs are rate limited."""
    source = Path(profile_dir)
    if not source.is_dir() or not any(source.iterdir()):
        return None
    safe_reason = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in reason)[:30]
    folder = BACKUP_ROOT / str(profile_key)
    folder.mkdir(parents=True, exist_ok=True)
    existing = sorted(
        (row for row in folder.iterdir() if row.is_dir() and row.name.endswith(f"_{safe_reason}")),
        key=lambda row: row.stat().st_mtime,
    )
    if existing and time.time() - existing[-1].stat().st_mtime < 6 * 3600:
        return str(existing[-1])
    target = folder / f"{time.strftime('%Y%m%d_%H%M%S')}_{safe_reason}"
    snapshot_profile(source, target)
    all_backups = sorted((row for row in folder.iterdir() if row.is_dir()),
                         key=lambda row: row.stat().st_mtime, reverse=True)
    for stale in all_backups[max(1, int(keep)):]:
        shutil.rmtree(stale, ignore_errors=True)
    return str(target)


def schedule_restore(backup_path, profile_key):
    valid, message = validate_backup(backup_path)
    if not valid:
        raise ValueError(message)
    payload = {
        "schema": 1, "backup_path": str(Path(backup_path).resolve()),
        "profile_key": str(profile_key), "requested_at": time.time(),
    }
    temp = RESTORE_MARKER.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp, RESTORE_MARKER)
    return str(RESTORE_MARKER)


def apply_pending_restore(profile_root):
    """Apply a scheduled restore before profile files or databases are opened."""
    if not RESTORE_MARKER.exists():
        return None
    try:
        payload = json.loads(RESTORE_MARKER.read_text(encoding="utf-8"))
        source = Path(payload.get("backup_path") or "")
        key = str(payload.get("profile_key") or "").strip()
        valid, message = validate_backup(source)
        if not key or not valid:
            raise ValueError(message if not valid else "Restore profile key is missing.")
        root = Path(profile_root).resolve()
        target = (root / key).resolve()
        if root not in target.parents:
            raise ValueError("Restore target is outside the profile folder.")
        root.mkdir(parents=True, exist_ok=True)
        rollback = BACKUP_ROOT / key / f"{time.strftime('%Y%m%d_%H%M%S')}_pre_restore"
        old = target.with_name(target.name + ".restore-old")
        if old.exists():
            shutil.rmtree(old, ignore_errors=True)
        if target.exists():
            snapshot_profile(target, rollback)
            target.rename(old)
        try:
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("backup_manifest.json"))
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            if old.exists():
                old.rename(target)
            raise
        shutil.rmtree(old, ignore_errors=True)
        RESTORE_MARKER.unlink(missing_ok=True)
        return {"profile_key": key, "backup": str(source), "rollback": str(rollback)}
    except Exception as exc:
        failed = RESTORE_MARKER.with_name(f".profile_restore_failed_{int(time.time())}.json")
        try:
            os.replace(RESTORE_MARKER, failed)
        except OSError:
            pass
        return {"error": str(exc)}
