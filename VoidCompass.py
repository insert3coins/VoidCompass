import os
import sys

# HTML cockpit overlays share a separate WinForms/WebView2 message loop.
# Dispatch it before importing Tk/dashboard modules or acquiring the primary
# Void Compass instance lock. PyInstaller retains this direct import for the
# one-file helper invocation used by the frozen executable.
if __name__ == "__main__" and "--html-overlay-host" in sys.argv:
    from html_overlay_host import main as _run_html_overlay_host

    _flag_index = sys.argv.index("--html-overlay-host")
    raise SystemExit(_run_html_overlay_host(sys.argv[_flag_index + 1:]))

# The main HTML command deck owns a normal taskbar window and therefore runs
# in its own WebView2 message loop during the staged Tk-backend migration.
if __name__ == "__main__" and "--html-dashboard-host" in sys.argv:
    from html_dashboard_host import main as _run_html_dashboard_host

    _flag_index = sys.argv.index("--html-dashboard-host")
    raise SystemExit(_run_html_dashboard_host(sys.argv[_flag_index + 1:]))

import tkinter as tk
import logging
import atexit
import tempfile
import crash_reporter
from config import commander_profile_key, load_config, save_config
from dashboard import MainDashboard
from journal_watcher import JournalWatcher
from onboarding import should_show as should_show_onboarding
from html_dashboard_runtime import HtmlDashboardRuntime
from version import APP_VERSION

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

    dashboard_runtime = None
    try:
        root = tk.Tk()
        # Do not let Windows map Tk's small default root while the dashboard is
        # still being constructed.  Apart from looking like a stray startup
        # window, mapping it early can make child HUDs report transient window
        # manager coordinates before their saved positions are reapplied.
        root.withdraw()
        # Shared overlay chrome reads this before any HUD Toplevel can map.
        # The Dashboard clears it only at the authoritative live handoff.
        root._voidcompass_startup_presentation_held = True
        if not HtmlDashboardRuntime.supported():
            from tkinter import messagebox

            messagebox.showerror(
                "Void Compass",
                "Void Compass 5.3.9 requires Windows WebView2 and pywebview.\n\n"
                "Install the Microsoft Edge WebView2 Runtime and reinstall Void Compass.",
                parent=root,
            )
            root.destroy()
            return
        root._voidcompass_html_dashboard_enabled = True
        root._voidcompass_first_commissioning = False
        dashboard_runtime = HtmlDashboardRuntime(
            root, startup_config, APP_VERSION,
        )
        root._voidcompass_html_dashboard_runtime = dashboard_runtime
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

        def launch_dashboard(splash):
            try:
                root._voidcompass_startup_splash = splash
                boot = getattr(splash, "_voidcompass_boot", None)
                if boot is not None:
                    boot.set_runtime_status(
                        "BUILDING DASHBOARD CORE",
                        "Loading profile, databases and flight systems",
                        0.18,
                    )
                splash.update_idletasks()
                app = MainDashboard(root)
                # Retain an explicit reference for the callback-driven startup
                # path; Tk callbacks alone should not own the application.
                root._voidcompass_app = app
                if dashboard_runtime is not None:
                    app.start_html_dashboard_bridge()
                # Withdraw and remember intended overlay visibility before
                # update_idletasks is allowed to process any pending maps.
                app._hold_startup_presentation()
                app._startup_boot_update(
                    "RESTORING JOURNAL HISTORY",
                    "Catching cached exploration records up to the live tail",
                    0.46,
                )
                # Flush final geometry while the root is still hidden. This
                # prevents the default Tk size from flashing before the
                # dashboard receives its saved dimensions.
                root.update_idletasks()
                return True
            except BaseException:
                try:
                    splash.destroy()
                except tk.TclError:
                    pass
                if crash_reporting_enabled:
                    crash_reporter.log_exception(*sys.exc_info(), source="startup")
                try:
                    root.destroy()
                except tk.TclError:
                    pass
                raise

        startup_splash = dashboard_runtime.splash

        def commissioning_complete(values):
            startup_config.update(values)
            detected = JournalWatcher.detect_latest_commander(
                startup_config.get("journal_path")
            )
            if detected:
                name = detected.get("commander") or "Unknown Commander"
                fid = detected.get("fid") or ""
                key = commander_profile_key(name, fid)
                profile = startup_config.setdefault("commander_profiles", {}).setdefault(
                    key, {},
                )
                profile.update({"commander_name": name, "fid": fid})
                startup_config.update({
                    "active_commander_profile": key,
                    "active_commander_name": name,
                    "active_commander_fid": fid,
                })
            save_config(startup_config)
            root._voidcompass_first_commissioning = True
            dashboard_runtime.set_runtime_status(
                "PROFILE VAULT COMMISSIONED",
                "Local settings saved; bringing the exploration core online",
                0.17,
            )
            root.after(120, lambda: launch_dashboard(startup_splash))

        def begin_startup():
            # The event loop is already live before either presented startup
            # path begins, keeping WebView2 motion and form input responsive
            # while the Python state engine performs synchronous construction.
            if should_show_onboarding(startup_config):
                dashboard_runtime.begin_commissioning(
                    startup_config, commissioning_complete,
                )
            else:
                launch_dashboard(startup_splash)

        root.after(0, begin_startup)
        root.mainloop()
    except BaseException:
        if crash_reporting_enabled:
            crash_reporter.log_exception(*sys.exc_info(), source="main")
        raise
    finally:
        if dashboard_runtime is not None:
            try:
                dashboard_runtime.dispose()
            except Exception:
                pass


if __name__ == "__main__":
    main()
