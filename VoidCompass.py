import os
import sys


def run_market_seed_worker():
    """Run the in-app market builder mode without loading the dashboard."""
    from trade import seed

    return seed.run_worker(sys.argv[1:])


if __name__ == "__main__" and "--trade-seed-worker" in sys.argv:
    raise SystemExit(run_market_seed_worker())


import tkinter as tk
import logging
import atexit
import tempfile
import crash_reporter
from config import load_config
from dashboard import MainDashboard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_INSTANCE_LOCK_FILE = None


def _lock_file(lock_file, unlock=False):
    """Acquire or release the platform-native non-blocking process lock."""
    if os.name == "nt":
        import msvcrt
        lock_file.seek(0)
        mode = msvcrt.LK_UNLCK if unlock else msvcrt.LK_NBLCK
        msvcrt.locking(lock_file.fileno(), mode, 1)
        return
    import fcntl
    operation = fcntl.LOCK_UN if unlock else (fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(lock_file.fileno(), operation)

def acquire_single_instance_lock():
    global _INSTANCE_LOCK_FILE
    lock_path = os.path.join(tempfile.gettempdir(), "void_compass.instance.lock")
    lock_file = open(lock_path, "a+")
    try:
        _lock_file(lock_file)
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
        _lock_file(_INSTANCE_LOCK_FILE, unlock=True)
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

def main():
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
        # Do not let Windows map Tk's small default root while the dashboard is
        # still being constructed.  Apart from looking like a stray startup
        # window, mapping it early can make child HUDs report transient window
        # manager coordinates before their saved positions are reapplied.
        root.withdraw()
        if crash_reporting_enabled:
            crash_reporter.install_tk(root)
            root.bind_all("<Control-Alt-d>", lambda _event: crash_reporter.dump_stacks("manual Ctrl+Alt+D"))

        # Attempt to set the native window icon.
        try:
            if sys.platform == "win32":
                root.iconbitmap(resource_path("icon.ico"))
            else:
                root._voidcompass_icon = tk.PhotoImage(
                    file=resource_path("icon-source.png")
                )
                root.iconphoto(True, root._voidcompass_icon)
        except Exception:
            pass # Icon file likely missing or invalid

        app = MainDashboard(root)
        root.update_idletasks()
        root.deiconify()
        root.lift()
        root.mainloop()
    except BaseException:
        if crash_reporting_enabled:
            crash_reporter.log_exception(*sys.exc_info(), source="main")
        raise


if __name__ == "__main__":
    main()
