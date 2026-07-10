import os
import sys

import tkinter as tk
import logging
import atexit
import tempfile
import msvcrt
import crash_reporter
from config import load_config
from dashboard import MainDashboard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_INSTANCE_LOCK_FILE = None

def acquire_single_instance_lock():
    global _INSTANCE_LOCK_FILE
    lock_path = os.path.join(tempfile.gettempdir(), "void_compass.instance.lock")
    lock_file = open(lock_path, "a+")
    try:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        _INSTANCE_LOCK_FILE = lock_file
        return True
    except OSError:
        lock_file.close()
        return False

def release_single_instance_lock():
    global _INSTANCE_LOCK_FILE
    if _INSTANCE_LOCK_FILE is None:
        return
    try:
        _INSTANCE_LOCK_FILE.seek(0)
        msvcrt.locking(_INSTANCE_LOCK_FILE.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    try:
        _INSTANCE_LOCK_FILE.close()
    except OSError:
        pass
    _INSTANCE_LOCK_FILE = None

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    startup_config = load_config()
    crash_reporting_enabled = bool(startup_config.get("crash_reporting_enabled", True))
    if crash_reporting_enabled:
        crash_reporter.install()
    if not acquire_single_instance_lock():
        logging.warning("Void Compass is already running. Exiting duplicate instance.")
        sys.exit(0)
    atexit.register(release_single_instance_lock)
    if crash_reporting_enabled:
        atexit.register(crash_reporter.close)

    try:
        root = tk.Tk()
        if crash_reporting_enabled:
            crash_reporter.install_tk(root)
            root.bind_all("<Control-Alt-d>", lambda _event: crash_reporter.dump_stacks("manual Ctrl+Alt+D"))

        # Attempt to set the window icon
        try:
            root.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass # Icon file likely missing or invalid

        app = MainDashboard(root)
        root.mainloop()
    except BaseException:
        if crash_reporting_enabled:
            crash_reporter.log_exception(*sys.exc_info(), source="main")
        raise
