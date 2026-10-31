"""What the live debugger sees (5.7.1): the app's recent log lines, its
threads and its own process, read off the app's main thread so a frozen UI
can still be looked at.

The log is kept in memory only (the last few thousand lines) with secrets
scrubbed as each line arrives. Debug-level lines are noted only while the
debugger asks for them (``set_verbose``), and never more than 15 minutes at
a time; the console keeps INFO either way. tools/debug reads all of it
through the Local API's /debug routes.
"""
from __future__ import annotations

from collections import deque
import ctypes
import logging
import os
import re
import sys
import threading
import time
import traceback

RING_SIZE = 4000
VERBOSE_MAX_S = 15 * 60
LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
# Libraries that talk a lot at debug level, kept at INFO even when verbose.
QUIET_LOGGERS = ("urllib3", "PIL", "asyncio", "comtypes", "websockets", "charset_normalizer", "matplotlib")

# Secrets in log text: query keys, webhooks, bearer tokens, and the
# commander's own secret settings (secret_values, set by the app).
_SECRET_QUERY = re.compile(r"(?i)\b(api_?key|apikey|key|token|secret|password)=([^&\s\"']+)")
_WEBHOOK = re.compile(r"(?i)https?://(?:[a-z]+\.)?discord(?:app)?\.com/api/webhooks/\S+")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")

_ring = deque(maxlen=RING_SIZE)
_lock = threading.Lock()
_seq = 0
_verbose_until = 0.0
_handler = None
# The root logger's level before any verbose spell (INFO in the app).
_quiet_level = logging.INFO
_started = time.time()
# A callable giving the commander's secret setting values (the app sets it).
secret_values = None
_secrets = ((), 0.0)


def _known_secrets():
    global _secrets
    values, at = _secrets
    if time.monotonic() - at > 30:
        try:
            found = secret_values() if callable(secret_values) else ()
            values = tuple(sorted({str(value) for value in found or () if value and len(str(value)) >= 6}, key=len,
                                  reverse=True))
        except Exception:
            values = ()
        _secrets = (values, time.monotonic())
    return values


def scrub(text):
    text = _WEBHOOK.sub("<hidden webhook>", str(text))
    text = _BEARER.sub("Bearer <hidden>", text)
    text = _SECRET_QUERY.sub(lambda match: f"{match.group(1)}=<hidden>", text)
    for value in _known_secrets():
        text = text.replace(value, "<hidden>")
    return text


class _Ring(logging.Handler):
    def emit(self, record):
        global _seq
        try:
            text = record.getMessage()
            if record.exc_info:
                text += "\n" + "".join(traceback.format_exception(*record.exc_info))[-6000:]
            row = {"at": round(record.created, 3), "level": record.levelname, "name": record.name,
                   "thread": record.threadName, "text": scrub(text)[:8000]}
            with _lock:
                _seq += 1
                row["seq"] = _seq
                _ring.append(row)
        except Exception:
            pass


def install():
    """Start keeping the log (once). The console's handlers keep INFO, so
    a verbose debugger doesn't flood them."""
    global _handler, _quiet_level
    if _handler is not None:
        return _handler
    root = logging.getLogger()
    _quiet_level = root.level or logging.INFO
    _console_at_info(root)
    for name in QUIET_LOGGERS:
        logger = logging.getLogger(name)
        if logger.level == logging.NOTSET:
            logger.setLevel(logging.INFO)
    _handler = _Ring(level=logging.DEBUG)
    root.addHandler(_handler)
    return _handler


def _console_at_info(root):
    """Every other handler (the console, a file) keeps INFO."""
    for handler in root.handlers:
        if handler is not _handler and handler.level == logging.NOTSET:
            handler.setLevel(logging.INFO)


def set_verbose(on, seconds=VERBOSE_MAX_S):
    """Note debug-level lines for a while (at most 15 minutes), or stop."""
    global _verbose_until
    _verbose_until = time.time() + max(10.0, min(float(seconds), VERBOSE_MAX_S)) if on else 0.0
    root = logging.getLogger()
    if on:
        _console_at_info(root)
    root.setLevel(logging.DEBUG if on else _quiet_level)
    return verbose()


def verbose():
    """Seconds of verbose logging left (0 when off); it ends by itself."""
    global _verbose_until
    left = _verbose_until - time.time()
    if _verbose_until and left <= 0:
        _verbose_until = 0.0
        logging.getLogger().setLevel(_quiet_level)
    return max(0, round(left)) if _verbose_until else 0


def records(since=0, level="DEBUG", limit=500, text=""):
    """Log lines after ``since``, at ``level`` or above, oldest first."""
    verbose()
    floor = LEVELS.get(str(level).upper(), logging.DEBUG)
    wanted = str(text or "").casefold()
    with _lock:
        rows = [row for row in _ring if row["seq"] > since]
        newest = _seq
    rows = [row for row in rows if LEVELS.get(row["level"], logging.ERROR) >= floor
            and (not wanted or wanted in row["text"].casefold() or wanted in row["name"].casefold())]
    return {"seq": newest, "verbose_s": verbose(), "records": rows[-max(1, min(int(limit), RING_SIZE)):]}


def threads(stacks=False):
    """Every thread: name, daemon, and what it's doing right now (its top
    frame, or with ``stacks`` its whole stack)."""
    frames = sys._current_frames()
    out = []
    for thread in threading.enumerate():
        frame = frames.get(thread.ident)
        row = {"name": thread.name, "daemon": thread.daemon, "id": thread.ident, "where": ""}
        if frame is not None:
            summary = traceback.extract_stack(frame)
            if summary:
                top = summary[-1]
                row["where"] = f"{os.path.basename(top.filename)}:{top.lineno} {top.name}"
            if stacks:
                row["stack"] = [f"{os.path.basename(item.filename)}:{item.lineno} {item.name}"
                                + (f"  ·  {item.line.strip()}" if item.line else "") for item in summary[-30:]]
        out.append(row)
    return sorted(out, key=lambda row: (row["name"] != "MainThread", row["name"].casefold()))


# -- the process itself (Windows) --------------------------------------------------
class _Memory(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
                # PROCESS_MEMORY_COUNTERS_EX2 (Windows 10 1809 on): what Task Manager's Memory shows.
                ("PrivateWorkingSetSize", ctypes.c_size_t), ("SharedCommitUsage", ctypes.c_ulonglong)]


def process():
    """This process: id, how long it's been up, memory and CPU time."""
    row = {"pid": os.getpid(), "uptime_s": round(time.time() - _started), "threads": threading.active_count(),
           "python": sys.version.split()[0], "frozen": bool(getattr(sys, "frozen", False))}
    if os.name != "nt":
        return row
    try:
        # Their own instances, so the prototypes set here touch no one else's.
        kernel = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        handle = ctypes.c_void_p(-1)  # this process
        kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
        kernel.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        memory = _Memory()
        memory.cb = ctypes.sizeof(_Memory)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            # Its own memory, as Task Manager counts it; the working set also
            # holds shared pages and mapped files.
            row["memory_mb"] = round(memory.PrivateWorkingSetSize / 1048576, 1)
            row["working_set_mb"] = round(memory.WorkingSetSize / 1048576, 1)
            row["commit_mb"] = round(memory.PrivateUsage / 1048576, 1)
        times = [ctypes.c_ulonglong() for _ in range(4)]
        if kernel.GetProcessTimes(handle, *[ctypes.byref(item) for item in times]):
            row["cpu_s"] = round((times[2].value + times[3].value) / 10_000_000, 2)
        count = ctypes.c_ulong()
        if kernel.GetProcessHandleCount(handle, ctypes.byref(count)):
            row["handles"] = count.value
    except Exception:
        pass
    return row
