"""Lifecycle bridge between the Python application and HTML command deck."""

from __future__ import annotations

import atexit
import importlib.util
import logging
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

from html_dashboard_server import HtmlDashboardServer
from diagnostic_logs import (
    LOG_ARCHIVE_LIMIT, application_base_dir, prepare_log, resolve_log_path,
)
import themes


_GEOMETRY_RE = re.compile(
    r"^(?P<width>\d+)x(?P<height>\d+)(?P<x>[+-]-?\d+)?(?P<y>[+-]-?\d+)?$"
)


def _resource_path(relative_path):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def _geometry_payload(value):
    match = _GEOMETRY_RE.fullmatch(str(value or ""))
    if not match:
        return {"width": 1440, "height": 900, "x": None, "y": None}
    payload = {
        "width": max(980, int(match.group("width"))),
        "height": max(680, int(match.group("height"))),
        "x": None,
        "y": None,
    }
    for key in ("x", "y"):
        raw = match.group(key)
        if raw:
            try:
                payload[key] = int(raw)
            except ValueError:
                pass
    return payload


class HtmlDashboardSplash:
    """Small Tk-splash-compatible facade backed by the browser boot scene."""

    def __init__(self, runtime):
        self.runtime = runtime
        self._voidcompass_boot = runtime

    def update_idletasks(self):
        return None

    def deiconify(self):
        return None

    def attributes(self, *_args):
        return None

    def lift(self):
        return None

    def destroy(self):
        return None


class HtmlDashboardRuntime:
    """Own the private server, native WebView2 window and command queue."""

    _ready_emitted = True

    def __init__(self, root, config, app_version):
        self.root = root
        self.config = config
        self.app_version = str(app_version)
        self.app = None
        self.process = None
        self._closing_process = None
        self._disposed = False
        self._commands = queue.SimpleQueue()
        self._command_job = None
        self._host_watchdog_job = None
        self._host_exit_seen_at = 0.0
        self._host_log = None
        self._host_log_lock = threading.Lock()
        theme_name, palette = themes.resolve_theme(
            config.get("ui_theme_name"), config.get("ui_custom_themes") or {},
        )
        theme_names = list(themes.BUILTIN_THEMES)
        theme_names.extend(
            name for name in (config.get("ui_custom_themes") or {})
            if name not in theme_names
        )
        self._latest_app_model = {
            "theme": {
                "name": theme_name,
                "palette": palette,
                "available": theme_names,
            },
        }
        self._commissioning_callback = None
        self._commissioning_session = 0
        self._onboarding = {"active": False, "session": 0}
        self._boot = {
            "active": True,
            "status": "INITIALISING FLIGHT COMPUTER",
            "detail": "Starting the private command deck",
            "progress": 0.06,
        }
        geometry = _geometry_payload(
            config.get("dashboard_window_geometry") or config.get("main_geometry")
        )
        host_state = {
            **geometry,
            "title": f"VOID COMPASS // v{self.app_version}",
            "storage_path": str(application_base_dir() / "webview" / "dashboard"),
            "background": "#070b10",
        }
        self.window_geometry = geometry
        self.server = HtmlDashboardServer(
            _resource_path(Path("web") / "dashboard"),
            command_callback=self._receive_command,
            host_state=host_state,
        )
        self._open_host_log()
        self.splash = HtmlDashboardSplash(self)
        self._publish()
        self._launch()
        self._schedule_host_watchdog()
        atexit.register(self._force_process_exit)

    @staticmethod
    def supported():
        return bool(os.name == "nt" and importlib.util.find_spec("webview") is not None)

    def _open_host_log(self):
        try:
            path = prepare_log(
                resolve_log_path("html_dashboard_host.log"),
                keep=LOG_ARCHIVE_LIMIT,
            )
            self._host_log = open(path, "ab", buffering=0)
            self._write_host_log(
                f"\n=== Void Compass HTML dashboard host // {time.strftime('%Y-%m-%d %H:%M:%S')} ==="
            )
        except Exception:
            self._host_log = None

    def _write_host_log(self, message):
        handle = self._host_log
        if handle is None:
            return
        try:
            payload = (str(message or "") + "\n").encode("utf-8", "replace")
            with self._host_log_lock:
                handle.write(payload)
        except Exception:
            pass

    def _launch(self):
        if not self.supported():
            raise RuntimeError("The HTML dashboard requires Windows WebView2/pywebview")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--html-dashboard-host", self.server.url]
            cwd = str(Path(sys.executable).resolve().parent)
        else:
            entry = Path(__file__).resolve().with_name("VoidCompass.py")
            command = [sys.executable, str(entry), "--html-dashboard-host", self.server.url]
            cwd = str(entry.parent)
        kwargs = {
            "cwd": cwd,
            "stdin": subprocess.DEVNULL,
            "stdout": self._host_log or subprocess.DEVNULL,
            "stderr": subprocess.STDOUT if self._host_log else subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self.process = subprocess.Popen(command, **kwargs)

    def attach_app(self, app):
        self.app = app
        self._schedule_command_pump()
        self.publish_app(app.html_dashboard_snapshot())

    def begin_commissioning(self, config, callback):
        """Present first-run/setup commissioning entirely inside WebView2."""
        self._commissioning_session += 1
        self._commissioning_callback = callback
        self._onboarding = {
            "active": True,
            "session": self._commissioning_session,
            "journal_path": str((config or {}).get("journal_path") or "")[:2048],
            "adaptive_command_enabled": bool(
                (config or {}).get("adaptive_command_enabled", True)
            ),
            "overlay_enabled": bool((config or {}).get("overlay_enabled", True)),
            "overlay_mouse_passthrough": bool(
                (config or {}).get("overlay_mouse_passthrough", True)
            ),
            "error": "",
            "submitting": False,
        }
        self._boot.update({
            "active": True,
            "status": "FIRST COMMISSIONING",
            "detail": "Connect the local Frontier journal and initialise the flight deck",
            "progress": 0.10,
        })
        self._publish()
        self._schedule_command_pump()
        return True

    def set_runtime_status(self, status, detail="", progress=None):
        self._boot.update({
            "active": True,
            "status": str(status or "PREPARING COMMAND DECK"),
            "detail": str(detail or ""),
        })
        if progress is not None:
            try:
                self._boot["progress"] = max(0.0, min(1.0, float(progress)))
            except (TypeError, ValueError):
                pass
        self._publish()

    def stop(self):
        self._onboarding["active"] = False
        self._boot.update({
            "active": False,
            "status": "VOID COMPASS LIVE",
            "detail": "Journal and exploration state synchronized",
            "progress": 1.0,
        })
        self._publish()

    def publish_app(self, model):
        self._latest_app_model = dict(model or {})
        self._publish()

    @property
    def origin(self):
        return self.server.origin

    def allow_frame_source(self, origin):
        return self.server.allow_frame_source(origin)

    def _publish(self):
        payload = dict(self._latest_app_model)
        payload.setdefault("app", {})
        payload["app"] = {
            "name": "Void Compass",
            "version": self.app_version,
            **dict(payload.get("app") or {}),
        }
        payload["boot"] = dict(self._boot)
        payload["onboarding"] = dict(self._onboarding)
        payload["transport"] = {"renderer": "webview2", "private": True}
        # Mirror the presentation gate into the native host channel. The host
        # can release a stale browser curtain even if its long-poll client was
        # delayed during the final journal/overlay handoff.
        self.server.update_host_state({
            "boot_active": bool(self._boot.get("active")),
            "onboarding_active": bool(self._onboarding.get("active")),
        })
        self.server.publish(payload)

    def _receive_command(self, payload):
        action = str((payload or {}).get("action") or "").strip().casefold()
        if action == "client_error":
            message = str(payload.get("message") or "unknown renderer error")[:2000]
            source = str(payload.get("source") or "dashboard-js")[:160]
            self._write_host_log(f"[renderer:{source}] {message}")
            return True
        if action == "window_geometry":
            try:
                width = max(980, int(payload.get("width") or 0))
                height = max(680, int(payload.get("height") or 0))
                x = int(payload.get("x") or 0)
                y = int(payload.get("y") or 0)
            except (TypeError, ValueError):
                return False
            self.window_geometry = {"width": width, "height": height, "x": x, "y": y}
            return True
        if action == "window_closed":
            try:
                self.root.after(0, self._close_from_window)
            except Exception:
                pass
            return True
        if action not in {
            "open", "copy_next", "set_theme", "rebuild_cache",
            "open_screenshots", "open_logs", "quit",
            "page_changed", "overlay_studio", "workspace",
            "set_adaptive_mode", "open_adaptive_mode",
            "set_flight_log_mode",
            "onboarding_submit", "onboarding_cancel",
        }:
            return False
        self._commands.put(dict(payload))
        return True

    def _close_from_window(self):
        if self._disposed:
            return
        app = self.app
        if app is not None:
            app.on_close()
        else:
            try:
                self.root.destroy()
            except Exception:
                pass

    def _schedule_command_pump(self):
        if self._disposed or self._command_job is not None:
            return
        try:
            self._command_job = self.root.after(40, self._drain_commands)
        except Exception:
            self._command_job = None

    def _schedule_host_watchdog(self):
        if self._disposed or self._host_watchdog_job is not None:
            return
        try:
            self._host_watchdog_job = self.root.after(500, self._check_host_process)
        except Exception:
            self._host_watchdog_job = None

    def _check_host_process(self):
        self._host_watchdog_job = None
        if self._disposed:
            return
        process = self.process
        if process is None or process.poll() is not None:
            # A normal window close posts its command immediately before the
            # host exits. Give Tk one turn to consume that command before
            # treating an unannounced exit as a renderer failure.
            now = time.monotonic()
            if not self._host_exit_seen_at:
                self._host_exit_seen_at = now
                self._schedule_host_watchdog()
                return
            if now - self._host_exit_seen_at < 0.45:
                self._schedule_host_watchdog()
                return
            exit_code = process.poll() if process is not None else None
            self._write_host_log(
                f"HTML command-deck host exited unexpectedly (code {exit_code})"
            )
            logging.error(
                "HTML command-deck host exited unexpectedly (code %s)", exit_code,
            )
            try:
                from tkinter import messagebox

                messagebox.showerror(
                    "Void Compass",
                    "The HTML command deck closed unexpectedly. Void Compass "
                    "will now close so its profile state remains consistent.",
                    parent=self.root,
                )
            except Exception:
                pass
            self._close_from_window()
            return
        self._host_exit_seen_at = 0.0
        self._schedule_host_watchdog()

    def _drain_commands(self):
        self._command_job = None
        app = self.app
        for _index in range(24):
            try:
                payload = self._commands.get_nowait()
            except queue.Empty:
                break
            action = str(payload.get("action") or "").strip().casefold()
            if action in {"onboarding_submit", "onboarding_cancel"}:
                self._handle_commissioning_command(payload)
            elif app is not None:
                try:
                    app.handle_html_dashboard_command(payload)
                except Exception:
                    pass
        self._schedule_command_pump()

    def _handle_commissioning_command(self, payload):
        if not self._onboarding.get("active"):
            return False
        action = str(payload.get("action") or "").strip().casefold()
        if action == "onboarding_cancel":
            self._close_from_window()
            return True
        if action != "onboarding_submit" or self._onboarding.get("submitting"):
            return False

        journal_path = str(payload.get("journal_path") or "").strip()[:2048]
        if journal_path and not os.path.isabs(journal_path):
            self._onboarding["error"] = (
                "Use the full journal-folder path, such as C:\\Users\\…\\Elite Dangerous."
            )
            self._publish()
            return False
        values = {
            "journal_path": journal_path,
            "adaptive_command_enabled": bool(
                payload.get("adaptive_command_enabled", True)
            ),
            "overlay_enabled": bool(payload.get("overlay_enabled", True)),
            "overlay_mouse_passthrough": bool(
                payload.get("overlay_mouse_passthrough", True)
            ),
            "onboarding_complete": True,
        }
        self._onboarding.update({
            "submitting": True,
            "error": "",
        })
        self._boot.update({
            "status": "COMMISSIONING FLIGHT DECK",
            "detail": "Saving the local profile and preparing journal recovery",
            "progress": 0.15,
        })
        self._publish()

        def complete():
            if self._disposed:
                return
            self._onboarding["active"] = False
            callback = self._commissioning_callback
            self._commissioning_callback = None
            self._publish()
            if callable(callback):
                callback(values)

        try:
            self.root.after(280, complete)
        except Exception:
            complete()
        return True

    def geometry_string(self):
        geometry = self.window_geometry or {}
        try:
            return (
                f"{int(geometry['width'])}x{int(geometry['height'])}"
                f"{int(geometry['x']):+d}{int(geometry['y']):+d}"
            )
        except (KeyError, TypeError, ValueError):
            return ""

    def apply_profile_geometry(self, value):
        geometry = _geometry_payload(value)
        self.window_geometry = geometry
        self.server.update_host_state(geometry)
        return True

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        if self._command_job is not None:
            try:
                self.root.after_cancel(self._command_job)
            except Exception:
                pass
            self._command_job = None
        if self._host_watchdog_job is not None:
            try:
                self.root.after_cancel(self._host_watchdog_job)
            except Exception:
                pass
            self._host_watchdog_job = None
        self.server.request_shutdown()
        process = self.process
        self.process = None
        self._closing_process = process
        threading.Thread(
            target=self._finish_dispose,
            args=(process,),
            name="html-dashboard-dispose",
            daemon=True,
        ).start()

    def _finish_dispose(self, process):
        try:
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=1.2)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=0.3)
                    except subprocess.TimeoutExpired:
                        process.kill()
        except Exception:
            try:
                if process is not None and process.poll() is None:
                    process.kill()
            except Exception:
                pass
        finally:
            self._closing_process = None
            self.server.stop()
            handle = self._host_log
            self._host_log = None
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass

    def _force_process_exit(self):
        process = self.process or self._closing_process
        try:
            if process is not None and process.poll() is None:
                process.kill()
        except Exception:
            pass
