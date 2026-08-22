"""Native pywebview host for the Void Compass command deck."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import time
import traceback
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import build_opener, ProxyHandler, Request


_OPENER = build_opener(ProxyHandler({}))


def _request_json(url, payload=None, timeout=2.0):
    body = None
    headers = {}
    method = "GET"
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = Request(url, data=body, headers=headers, method=method)
    with _OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


class DashboardHost:
    def __init__(self, dashboard_url):
        parsed = urlparse(str(dashboard_url))
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self.token = (parse_qs(parsed.query).get("token") or [""])[0]
        self.dashboard_url = dashboard_url
        self.window = None
        self.closing_from_backend = False
        self._geometry = {}
        self._geometry_lock = threading.Lock()
        self._geometry_timer = None
        self.host_revision = -1
        self.monitor_failures = 0
        self.boot_released = False
        self.boot_release_started_at = 0.0

    def url(self, path):
        return f"{self.origin}{path}?token={quote(self.token)}"

    def host_state(self):
        return _request_json(self.url("/api/host"), timeout=3.0)

    def post(self, action, **payload):
        try:
            return _request_json(
                self.url("/api/command"),
                {"action": action, **payload},
                timeout=1.0,
            )
        except Exception:
            return {}

    def moved(self, x, y):
        with self._geometry_lock:
            self._geometry.update({"x": int(x), "y": int(y)})
        self._schedule_geometry_post()

    def resized(self, width, height):
        with self._geometry_lock:
            self._geometry.update({"width": int(width), "height": int(height)})
        self._schedule_geometry_post()

    def _schedule_geometry_post(self):
        """Coalesce the high-rate WebView move/resize event stream."""
        with self._geometry_lock:
            timer = self._geometry_timer
            if timer is not None:
                timer.cancel()
            timer = threading.Timer(0.16, self._post_geometry)
            timer.daemon = True
            self._geometry_timer = timer
            timer.start()

    def _post_geometry(self):
        required = {"x", "y", "width", "height"}
        with self._geometry_lock:
            self._geometry_timer = None
            geometry = dict(self._geometry)
        if required.issubset(geometry):
            self.post("window_geometry", **geometry)

    def closed(self):
        with self._geometry_lock:
            timer = self._geometry_timer
            self._geometry_timer = None
            geometry = dict(self._geometry)
        if timer is not None:
            timer.cancel()
        if {"x", "y", "width", "height"}.issubset(geometry):
            self.post("window_geometry", **geometry)
        if not self.closing_from_backend:
            self.post("window_closed")

    def monitor(self):
        while self.window is not None:
            try:
                state = _request_json(self.url("/api/host"), timeout=2.0)
                if state.get("closing"):
                    self.closing_from_backend = True
                    self.window.destroy()
                    return
                self.monitor_failures = 0
                boot_active = bool(state.get("boot_active", True))
                onboarding_active = bool(state.get("onboarding_active", False))
                if boot_active or onboarding_active:
                    # A later commissioning run owns the curtain again.
                    self.boot_released = False
                    self.boot_release_started_at = 0.0
                elif not self.boot_released:
                    # Belt-and-braces handoff: a snapshot GET that began just
                    # before runtime.stop() can arrive after the first native
                    # release and make the curtain visible again. Reassert the
                    # live presentation for a short settling window instead of
                    # treating release as a one-shot edge.
                    now = time.monotonic()
                    if not self.boot_release_started_at:
                        self.boot_release_started_at = now
                        print("HTML dashboard boot release guard engaged", flush=True)
                    elapsed = now - self.boot_release_started_at
                    force_hide = elapsed >= 0.85
                    self.window.evaluate_js(
                        "document.body.classList.add('ready');"
                        "document.getElementById('app')?.setAttribute('aria-hidden','false');"
                        + (
                            "(()=>{const b=document.getElementById('boot');if(b)b.hidden=true;})()"
                            if force_hide else
                            "setTimeout(()=>{const b=document.getElementById('boot');if(b)b.hidden=true;},720)"
                        )
                    )
                    if elapsed >= 4.0:
                        self.boot_released = True
                        print("HTML dashboard boot release guard settled", flush=True)
                host_revision = int(state.get("host_revision") or 0)
                if host_revision != self.host_revision:
                    self.host_revision = host_revision
                    width = max(980, int(state.get("width") or self._geometry.get("width") or 1440))
                    height = max(680, int(state.get("height") or self._geometry.get("height") or 900))
                    x, y = state.get("x"), state.get("y")
                    self.window.resize(width, height)
                    if x is not None and y is not None:
                        self.window.move(int(x), int(y))
            except Exception as exc:
                # Cache rebuilds and security software can briefly delay a
                # loopback response. Require a sustained outage before
                # treating the Python backend as gone.
                self.monitor_failures += 1
                if self.monitor_failures < 8:
                    time.sleep(0.35)
                    continue
                print(
                    f"Dashboard backend monitor failed {self.monitor_failures} times: {exc}",
                    file=sys.stderr,
                )
                self.closing_from_backend = True
                try:
                    self.window.destroy()
                except Exception:
                    pass
                return
            time.sleep(0.35)


class DashboardApi:
    """Small native capability surface exposed only to bundled dashboard JS."""

    __slots__ = ("_host",)

    def __init__(self, host):
        # pywebview recursively walks every public attribute on a JS API object.
        # Keeping the native host private prevents it from descending through
        # window.native.AccessibilityObject and exhausting Python's recursion
        # limit before the dashboard can finish its startup handoff.
        self._host = host

    def choose_journal_folder(self):
        return self.choose_folder()

    def choose_folder(self):
        """Choose a local directory for profile backup/restore and paths."""
        window = self._host.window
        if window is None:
            return ""
        try:
            import webview

            selected = window.create_file_dialog(webview.FileDialog.FOLDER)
        except Exception:
            return ""
        if not selected:
            return ""
        return str(selected[0] or "")


def main(argv=None):
    argv = list(argv or [])
    if not argv:
        return 2
    dashboard_url = str(argv[0])
    host = DashboardHost(dashboard_url)
    try:
        state = host.host_state()
    except Exception as exc:
        print(f"Dashboard host could not read its startup state: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 3

    import webview

    width = max(980, int(state.get("width") or 1440))
    height = max(680, int(state.get("height") or 900))
    x = state.get("x")
    y = state.get("y")
    host._geometry = {"width": width, "height": height}
    if x is not None and y is not None:
        host._geometry.update({"x": int(x), "y": int(y)})
    api = DashboardApi(host)
    window = webview.create_window(
        str(state.get("title") or "Void Compass"),
        dashboard_url,
        js_api=api,
        width=width,
        height=height,
        x=int(x) if x is not None else None,
        y=int(y) if y is not None else None,
        min_size=(980, 680),
        background_color=str(state.get("background") or "#070b10"),
        text_select=True,
    )
    host.window = window
    host.host_revision = int(state.get("host_revision") or 0)
    window.events.moved += host.moved
    window.events.resized += host.resized
    window.events.closed += host.closed
    threading.Thread(target=host.monitor, name="dashboard-host-monitor", daemon=True).start()
    storage = Path(str(state.get("storage_path") or "")).resolve()
    storage.mkdir(parents=True, exist_ok=True)
    try:
        webview.start(private_mode=False, storage_path=str(storage))
    except Exception:
        print("Dashboard WebView2 message loop failed", file=sys.stderr)
        traceback.print_exc()
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
