import datetime
import faulthandler
import os
import platform
import sys
import threading
import time
import traceback


_CRASH_FILE = None
_CRASH_PATH = None
_HEARTBEAT_TS = time.monotonic()
_WATCHDOG_STARTED = False
_WATCHDOG_STOP = threading.Event()
_WATCHDOG_LAST_DUMP = 0.0


def crash_log_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.getcwd()
    return os.path.join(base, "crash_report.log")


def _write_header(fh):
    fh.write("\n" + "=" * 80 + "\n")
    fh.write(f"Void Compass crash reporter started: {datetime.datetime.now().isoformat()}\n")
    fh.write(f"Executable: {sys.executable}\n")
    fh.write(f"CWD: {os.getcwd()}\n")
    fh.write(f"Frozen: {bool(getattr(sys, 'frozen', False))}\n")
    fh.write(f"Python: {sys.version.replace(os.linesep, ' ')}\n")
    fh.write(f"Platform: {platform.platform()}\n")
    fh.write("=" * 80 + "\n")
    fh.flush()


def log_exception(exc_type, exc_value, exc_tb, source="uncaught"):
    global _CRASH_FILE
    try:
        fh = _CRASH_FILE or open(crash_log_path(), "a", encoding="utf-8")
        fh.write("\n" + "-" * 80 + "\n")
        fh.write(f"{datetime.datetime.now().isoformat()} [{source}]\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
        fh.flush()
    except Exception:
        pass


def log_message(message):
    global _CRASH_FILE
    try:
        fh = _CRASH_FILE or open(crash_log_path(), "a", encoding="utf-8")
        fh.write("\n" + "-" * 80 + "\n")
        fh.write(f"{datetime.datetime.now().isoformat()} [diagnostic]\n")
        fh.write(str(message) + "\n")
        fh.flush()
    except Exception:
        pass


def dump_stacks(reason="manual dump"):
    try:
        fh = _CRASH_FILE or open(crash_log_path(), "a", encoding="utf-8")
        fh.write("\n" + "-" * 80 + "\n")
        fh.write(f"{datetime.datetime.now().isoformat()} [stack dump] {reason}\n")
        fh.flush()
        faulthandler.dump_traceback(file=fh, all_threads=True)
        fh.flush()
    except Exception:
        pass


def heartbeat():
    global _HEARTBEAT_TS
    _HEARTBEAT_TS = time.monotonic()


def install_ui_freeze_watchdog(root, interval_ms=500, timeout_s=5.0, dump_cooldown_s=15.0):
    global _WATCHDOG_STARTED
    heartbeat()

    def _tick():
        heartbeat()
        try:
            root.after(interval_ms, _tick)
        except Exception:
            pass

    try:
        root.after(interval_ms, _tick)
    except Exception:
        pass

    if _WATCHDOG_STARTED:
        return
    _WATCHDOG_STARTED = True

    def _watch():
        global _WATCHDOG_LAST_DUMP
        while not _WATCHDOG_STOP.wait(1.0):
            idle_s = time.monotonic() - _HEARTBEAT_TS
            now = time.monotonic()
            if idle_s >= timeout_s and (now - _WATCHDOG_LAST_DUMP) >= dump_cooldown_s:
                _WATCHDOG_LAST_DUMP = now
                dump_stacks(f"UI heartbeat stalled for {idle_s:.1f}s")

    t = threading.Thread(target=_watch, name="crash-ui-freeze-watchdog", daemon=True)
    t.start()


def install(root=None):
    global _CRASH_FILE, _CRASH_PATH
    if _CRASH_FILE is not None:
        if root is not None:
            install_tk(root)
        return _CRASH_PATH

    _CRASH_PATH = crash_log_path()
    try:
        os.makedirs(os.path.dirname(_CRASH_PATH), exist_ok=True)
        # Each launch starts a fresh diagnostic session. Keep all exceptions
        # and stack dumps from the current run together without allowing the
        # log to grow indefinitely across restarts.
        _CRASH_FILE = open(_CRASH_PATH, "w", encoding="utf-8")
        _write_header(_CRASH_FILE)
        faulthandler.enable(file=_CRASH_FILE, all_threads=True)
    except Exception:
        _CRASH_FILE = None

    def _sys_hook(exc_type, exc_value, exc_tb):
        log_exception(exc_type, exc_value, exc_tb, "sys.excepthook")
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _sys_hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            log_exception(args.exc_type, args.exc_value, args.exc_traceback, f"thread:{getattr(args.thread, 'name', '?')}")
            try:
                threading.__excepthook__(args)
            except Exception:
                pass
        threading.excepthook = _thread_hook

    if root is not None:
        install_tk(root)
    return _CRASH_PATH


def install_tk(root):
    def _tk_exception(exc_type, exc_value, exc_tb):
        log_exception(exc_type, exc_value, exc_tb, "tkinter callback")
    try:
        root.report_callback_exception = _tk_exception
    except Exception:
        pass
    install_ui_freeze_watchdog(root)


def close():
    global _CRASH_FILE
    try:
        _WATCHDOG_STOP.set()
    except Exception:
        pass
    try:
        faulthandler.disable()
    except Exception:
        pass
    try:
        if _CRASH_FILE:
            _CRASH_FILE.flush()
            _CRASH_FILE.close()
    except Exception:
        pass
    _CRASH_FILE = None
