"""Small, dependency-free helpers for per-run diagnostic log rotation."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from platform_support import application_dir


LOG_ARCHIVE_LIMIT = 10
LOG_DIR_NAME = "logs"


def application_base_dir():
    """Return the writable folder beside the EXE, or the current source run."""
    return application_dir()


def resolve_log_path(filename, configured=None, base_dir=None):
    """Resolve bare legacy names into the shared logs directory."""
    base = Path(base_dir).resolve() if base_dir is not None else application_base_dir()
    value = str(configured or "").strip()
    if not value:
        return str(base / LOG_DIR_NAME / filename)
    path = Path(value)
    if path.is_absolute():
        return str(path)
    if path.parent == Path("."):
        return str(base / LOG_DIR_NAME / path.name)
    return str(base / path)


def _archive_target(path, source=None):
    timestamp_source = source or path
    try:
        modified = timestamp_source.stat().st_mtime
    except OSError:
        modified = None
    stamp = (
        datetime.fromtimestamp(modified).strftime("%Y%m%d-%H%M%S")
        if modified else datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    target = path.with_name(f"{path.stem}.{stamp}{path.suffix}")
    counter = 2
    while target.exists():
        target = path.with_name(f"{path.stem}.{stamp}-{counter}{path.suffix}")
        counter += 1
    return target


def _prune_archives(path, keep):
    pattern = f"{path.stem}.*{path.suffix}"
    archives = []
    for candidate in path.parent.glob(pattern):
        if candidate == path or not candidate.is_file():
            continue
        try:
            stat = candidate.stat()
            archives.append((stat.st_mtime_ns, candidate.name, candidate))
        except OSError:
            pass
    archives.sort(reverse=True)
    for _mtime, _name, candidate in archives[max(0, int(keep)):]:
        try:
            candidate.unlink()
        except OSError:
            pass


def prepare_log(path, legacy_paths=(), keep=LOG_ARCHIVE_LIMIT):
    """Archive previous current logs and return a clean current-log path."""
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    sources = [target]
    sources.extend(Path(item).resolve() for item in legacy_paths or () if item)
    seen = set()
    for source in sources:
        source_key = os.path.normcase(str(source))
        if source_key in seen or not source.is_file():
            continue
        seen.add(source_key)
        try:
            os.replace(source, _archive_target(target, source=source))
        except OSError:
            pass
    _prune_archives(target, keep)
    return str(target)
