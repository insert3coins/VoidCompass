"""Small, dependency-free helpers for per-run diagnostic log rotation."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from voidcompass.core.platform_support import application_dir


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


def log_clock():
    """Wall-clock time to the millisecond, as the runtime trace records it."""
    now = datetime.now()
    return now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


class TimestampedStream:
    """Prefix each line a host process prints with ``log_clock()``.

    The WebView host processes write their stdout and stderr into the
    per-run host logs; without times, a slow or failed page start cannot be
    lined up against the runtime trace.
    """

    def __init__(self, stream):
        self._stream = stream
        self._line_start = True

    def write(self, text):
        text = str(text)
        pieces = []
        for part in text.splitlines(keepends=True):
            if self._line_start and part.strip():
                pieces.append(f"{log_clock()} ")
            pieces.append(part)
            self._line_start = part.endswith(("\n", "\r"))
        return self._stream.write("".join(pieces))

    def flush(self):
        return self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class ShutdownClock:
    """How long closing takes, step by step (5.6.4), in the current run's log."""

    def __init__(self, clock=None):
        import time
        self._clock = clock or time.perf_counter
        self.started = self.last = self._clock()
        self.steps = []
        self._prepared_path = None

    def mark(self, name):
        now = self._clock()
        self.steps.append((str(name), now - self.last))
        self.last = now

    def report(self, when=None):
        total = self.last - self.started
        stamp = (when or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"=== close {stamp} · {total:.2f} s ==="]
        lines += [f"  {seconds * 1000:7.0f} ms  {name}" for name, seconds in self.steps if seconds >= .01]
        return "\n".join(lines) + "\n"

    def write(self, base_dir=None):
        path = Path(resolve_log_path("shutdown.log", base_dir=base_dir)).resolve()
        try:
            if path != self._prepared_path:
                path = Path(prepare_log(path))
                self._prepared_path = path
            path.parent.mkdir(parents=True, exist_ok=True)
            # on_close writes once before closing the window and once after;
            # both writes update this run's report in place.
            path.write_text(self.report(), encoding="utf-8")
            return str(path)
        except OSError:
            return None
