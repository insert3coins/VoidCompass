"""Main-process owner for the shared HTML overlay renderer."""

from __future__ import annotations

import atexit
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from html_overlay_server import HtmlOverlayServer


def _resource_path(relative_path):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


class HtmlOverlayRuntime:
    """Own one HTTP transport and one WebView2 process per application."""

    def __init__(self, root):
        self.root = root
        self.server = HtmlOverlayServer(
            _resource_path("web"),
            presentation_held=bool(getattr(
                root, "_voidcompass_startup_presentation_held", False,
            )),
        )
        self.process = None
        self._closing_process = None
        self.surfaces = {}
        self._disposed = False
        atexit.register(self._force_process_exit)
        self._launch()
        try:
            root.bind("<Destroy>", self._on_root_destroy, add="+")
        except Exception:
            pass

    @staticmethod
    def supported():
        return bool(os.name == "nt" and importlib.util.find_spec("webview") is not None)

    def _launch(self):
        if not self.supported():
            raise RuntimeError("pywebview/WebView2 is unavailable")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--html-overlay-host", self.server.url]
            cwd = str(Path(sys.executable).resolve().parent)
        else:
            entry = Path(__file__).resolve().with_name("VoidCompass.py")
            command = [sys.executable, str(entry), "--html-overlay-host", self.server.url]
            cwd = str(entry.parent)
        kwargs = {
            "cwd": cwd,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        # Launch is deferred until the first surface has registered; the host
        # needs a master window in its initial manifest.
        self._command = command
        self._popen_kwargs = kwargs

    def _ensure_process(self):
        if self._disposed:
            raise RuntimeError("HTML overlay runtime is closed")
        if self.process is not None and self.process.poll() is None:
            return
        self.process = subprocess.Popen(self._command, **self._popen_kwargs)

    def register(self, surface):
        self.surfaces[surface.overlay_id] = surface
        self.server.register(surface.overlay_id, surface.template, surface.title)
        # Pre-warm WebView2 and let each hidden page render while the bootloader
        # owns the presentation. HtmlOverlayServer supplies an independent,
        # host-enforced curtain so no model can accidentally map its window.
        self._ensure_process()

    def release_startup_hold(self):
        """Start the shared browser host only after the live UI handoff."""
        if self._disposed or not self.surfaces:
            return False
        if bool(getattr(
            self.root, "_voidcompass_startup_presentation_held", False,
        )):
            return False
        # Reveal the already-warmed native surfaces atomically. Any surface
        # that did not finish warming receives a fresh fallback timeout now.
        self.server.set_presentation_held(False)
        started_at = time.monotonic()
        for surface in self.surfaces.values():
            if not surface.ready:
                surface._started_at = started_at
                surface._renderer_lost_at = None
        self._ensure_process()
        return True

    def unregister(self, surface):
        if self.surfaces.get(surface.overlay_id) is surface:
            self.surfaces.pop(surface.overlay_id, None)
            self.server.unregister(surface.overlay_id)

    def is_alive(self):
        return bool(self.process is not None and self.process.poll() is None)

    def _on_root_destroy(self, event):
        if event.widget is self.root:
            self.dispose()

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        for surface in list(self.surfaces.values()):
            surface._disposed = True
        self.surfaces.clear()
        process = self.process
        self.process = None
        self._closing_process = process
        # Let WebView2 destroy its windows cleanly, but never hold Tk's close
        # callback while its message loop winds down. The Dashboard starts this
        # before its durability flush so both shutdown paths overlap.
        self.server.request_host_shutdown()
        threading.Thread(
            target=self._finish_dispose,
            args=(process,),
            name="html-overlay-dispose",
            daemon=True,
        ).start()

    def _finish_dispose(self, process):
        try:
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=0.75)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=0.2)
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

    def _force_process_exit(self):
        """Last-resort guard against an orphaned frozen WebView host."""
        process = self.process or self._closing_process
        try:
            if process is not None and process.poll() is None:
                process.kill()
        except Exception:
            pass


class HtmlOverlaySurface:
    """Independent model stream backed by the application's shared host."""

    def __init__(self, root, overlay_id, template="canvas", title=None):
        self.root = root
        self.overlay_id = str(overlay_id)
        self.template = str(template)
        self.title = str(title or overlay_id)
        self._disposed = False
        self._latest_model = {}
        self._started_at = time.monotonic()
        self._renderer_seen = False
        self._renderer_lost_at = None
        runtime = getattr(root, "_voidcompass_html_overlay_runtime", None)
        if runtime is None or getattr(runtime, "_disposed", False):
            runtime = HtmlOverlayRuntime(root)
            root._voidcompass_html_overlay_runtime = runtime
        self.runtime = runtime
        runtime.register(self)

    @staticmethod
    def supported():
        return HtmlOverlayRuntime.supported()

    @property
    def server(self):
        """Compatibility for existing diagnostics/fallback logging."""
        return self.runtime.server

    @property
    def host_status(self):
        return self.runtime.server.host_status(self.overlay_id)

    @property
    def ready(self):
        if self._disposed or not self.runtime.is_alive():
            return False
        server = self.runtime.server
        last_seen = server.last_client_seen(self.overlay_id)
        recently_seen = bool(last_seen and time.monotonic() - last_seen < 4.0)
        browser_rendered = server.rendered_revision(self.overlay_id) >= 0
        # The page's revision checks are also its browser-side heartbeat.
        # Host control requests intentionally do not update this timestamp.
        if server.is_ready(self.overlay_id) and browser_rendered and recently_seen:
            self._renderer_seen = True
            self._renderer_lost_at = None
            return True
        if self._renderer_seen:
            if self._renderer_lost_at is None:
                self._renderer_lost_at = time.monotonic()
            return time.monotonic() - self._renderer_lost_at < 2.5
        return False

    @property
    def startup_failed(self):
        if self._disposed:
            return True
        # The browser process is deliberately dormant behind the startup
        # curtain.  Do not interpret that intentional delay as renderer
        # failure and fall back to Tk before the boot handoff occurs.
        if bool(getattr(
            self.root, "_voidcompass_startup_presentation_held", False,
        )):
            return False
        elapsed = time.monotonic() - self._started_at
        if self.ready:
            return False
        if self._renderer_seen and self._renderer_lost_at is not None:
            return time.monotonic() - self._renderer_lost_at >= 2.5
        if self.runtime.is_alive():
            return elapsed > 12.0
        return elapsed > 0.35

    def is_alive(self):
        return self.runtime.is_alive()

    def publish(self, model):
        if self._disposed:
            return 0
        self._latest_model = dict(model or {})
        return self.runtime.server.publish(self.overlay_id, self._latest_model)

    def update_window(self, window):
        if self._disposed:
            return 0
        return self.runtime.server.update_window(self.overlay_id, window)

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        self.runtime.unregister(self)
