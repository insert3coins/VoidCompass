"""One isolated pywebview/WebView2 process for all cockpit overlays."""

from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import build_opener, ProxyHandler, Request


GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
HIDDEN_WINDOW_X = -32000
HIDDEN_WINDOW_Y = -32000
_LOOPBACK_OPENER = build_opener(ProxyHandler({}))


def _native_handle(window):
    native = getattr(window, "native", None)
    handle = getattr(native, "Handle", None)
    if handle is None:
        return 0
    for name in ("ToInt64", "ToInt32"):
        converter = getattr(handle, name, None)
        if callable(converter):
            return int(converter())
    try:
        return int(handle)
    except (TypeError, ValueError):
        return 0


def _overlay_window_style(style, click_through=True):
    """Return taskbar-free extended styles for an on-screen overlay."""
    style = int(style) & ~WS_EX_APPWINDOW
    style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if click_through:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    return style


def _apply_windows_style(window, click_through=True):
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_style.argtypes = (ctypes.c_void_p, ctypes.c_int)
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
        set_style.restype = ctypes.c_ssize_t
        old_style = int(get_style(hwnd, GWL_EXSTYLE))
        style = _overlay_window_style(old_style, click_through)
        style_changed = style != old_style
        # APPWINDOW explicitly asks Explorer to create a taskbar button and
        # takes precedence over the tool-window intent on some WebView2/
        # WinForms combinations. If it was present on an already visible
        # surface, briefly hide it while changing styles so the shell drops
        # its cached taskbar entry. New overlay windows begin hidden anyway.
        was_appwindow = bool(old_style & WS_EX_APPWINDOW)
        was_visible = bool(user32.IsWindowVisible(ctypes.c_void_p(hwnd)))
        if style_changed and was_appwindow and was_visible:
            user32.ShowWindow(ctypes.c_void_p(hwnd), SW_HIDE)
        if style_changed:
            ctypes.set_last_error(0)
            previous = set_style(hwnd, GWL_EXSTYLE, style)
            if previous == 0 and ctypes.get_last_error():
                if was_appwindow and was_visible:
                    user32.ShowWindow(ctypes.c_void_p(hwnd), SW_SHOWNOACTIVATE)
                return False
        position_flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if style_changed:
            position_flags |= SWP_FRAMECHANGED
        user32.SetWindowPos(
            ctypes.c_void_p(hwnd), ctypes.c_void_p(HWND_TOPMOST), 0, 0, 0, 0,
            position_flags,
        )
        if style_changed and was_appwindow and was_visible:
            user32.ShowWindow(ctypes.c_void_p(hwnd), SW_SHOWNOACTIVATE)
        return True
    except Exception:
        return False


def _apply_webview_transparency(window):
    """Restore WebView2's per-pixel transparent composition surface.

    A hidden WinForms/WebView2 window can occasionally return from ShowWindow
    with its controller's default background in the opaque fallback state.
    CSS transparency cannot repair that native surface, so reassert the same
    transparent-black controller colour pywebview applies at construction.
    The work is marshalled to the WinForms UI thread because the overlay host
    control loop runs on pywebview's background thread.
    """
    native = getattr(window, "native", None)
    if native is None:
        return False
    browser = getattr(native, "browser", None)
    control = getattr(browser, "webview", None) if browser is not None else None
    if control is None:
        control = getattr(native, "webview", None)
    if control is None:
        return False
    try:
        from System import Func, Type
        from System.Drawing import Color

        def restore():
            if bool(getattr(native, "IsDisposed", False)):
                return None
            if bool(getattr(control, "IsDisposed", False)):
                return None
            control.DefaultBackgroundColor = Color.FromArgb(0, 0, 0, 0)
            control.Invalidate()
            return None

        if bool(getattr(native, "InvokeRequired", False)):
            native.Invoke(Func[Type](restore))
        else:
            restore()
        return True
    except Exception:
        # Transparency recovery is defensive. A controller that is still
        # initializing will be retried on the next visible host pass.
        return False


def _apply_windows_geometry(window, x, y, width, height):
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        return bool(user32.SetWindowPos(
            ctypes.c_void_p(hwnd), ctypes.c_void_p(HWND_TOPMOST),
            int(x), int(y), int(width), int(height),
            # This is only a bounds update. Forcing a non-client frame rebuild
            # on every Studio drag, content resize or restored position can
            # also make WebView2 recreate its opaque fallback surface.
            SWP_NOACTIVATE,
        ))
    except Exception:
        return False


def _set_windows_visibility(window, visible):
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        ctypes.WinDLL("user32", use_last_error=True).ShowWindow(
            ctypes.c_void_p(hwnd), SW_SHOWNOACTIVATE if visible else SW_HIDE,
        )
        return True
    except Exception:
        return False


def _windows_visibility(window):
    """Read the real native visibility, independent of host bookkeeping.

    WebView2 can map a window after its initial ``hidden=True`` creation and
    after an early SW_HIDE has already succeeded. The requested state is not
    therefore enough to decide whether a later hide can be skipped.
    """
    hwnd = _native_handle(window)
    if not hwnd:
        return None
    try:
        return bool(ctypes.WinDLL("user32", use_last_error=True).IsWindowVisible(
            ctypes.c_void_p(hwnd),
        ))
    except Exception:
        return None


def _request_json(url, payload=None, timeout=1.5):
    body = None
    headers = {}
    method = "GET"
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = Request(url, data=body, headers=headers, method=method)
    with _LOOPBACK_OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


class _WindowController:
    def __init__(self, overlay_id, window):
        self.overlay_id = str(overlay_id)
        self.window = window
        self.last_geometry = None
        self.last_click_through = None
        self.last_visible = None
        self.last_topmost_refresh = 0.0
        self.ready_sent = False

    def apply(self, payload, presentation_held=False):
        payload = payload if isinstance(payload, dict) else {}
        try:
            width = max(24, int(payload.get("width") or 360))
            height = max(24, int(payload.get("height") or 180))
            x = int(payload.get("x") or 0)
            y = int(payload.get("y") or 0)
            requested_geometry = (x, y, width, height)
            # WebView2/WinForms can map a dynamically created window despite
            # pywebview's hidden=True request. While startup owns the screen,
            # quarantine every native surface outside the virtual desktop as
            # well as issuing SW_HIDE. Release moves it to the saved position
            # before the first visible frame.
            geometry = (
                (HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y, width, height)
                if presentation_held else requested_geometry
            )
            handle = _native_handle(self.window)
            if not handle:
                return {"ok": False, "reason": "native handle pending"}
            if geometry != self.last_geometry:
                if not _apply_windows_geometry(self.window, *geometry):
                    return {"ok": False, "reason": "native geometry unavailable", "handle": handle}
                self.last_geometry = geometry
            click_through = bool(payload.get("click_through", True))
            if click_through != self.last_click_through:
                _apply_windows_style(self.window, click_through)
                _apply_webview_transparency(self.window)
                self.last_click_through = click_through
            visible = bool(
                payload.get("visible", False)
                and not payload.get("shutdown")
                and not presentation_held
            )
            # WebView2 occasionally maps an asynchronously-created window
            # after our first SW_HIDE. Compare with the actual HWND instead of
            # trusting only last_visible, otherwise inactive transient HUDs
            # can remain on screen indefinitely with a false manifest state.
            native_visible = _windows_visibility(self.window)
            visibility_drifted = (
                native_visible is not None and native_visible != visible
            )
            if visible != self.last_visible or visibility_drifted:
                if visible:
                    _apply_windows_style(self.window, click_through)
                    _apply_windows_geometry(self.window, *geometry)
                    _apply_webview_transparency(self.window)
                if _set_windows_visibility(self.window, visible):
                    self.last_visible = visible
                    if visible:
                        # Showing the native form is the operation that can
                        # make WebView2 restore its opaque fallback brush.
                        _apply_webview_transparency(self.window)
                else:
                    self.last_visible = None
            now = time.monotonic()
            if visible and now - self.last_topmost_refresh >= 12.0:
                _apply_windows_style(self.window, click_through)
                self.last_topmost_refresh = now
            return {
                "ok": True,
                "handle": handle,
                "visible": visible,
                "curtained": bool(presentation_held),
            }
        except Exception as exc:
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

    def hide(self):
        _set_windows_visibility(self.window, False)
        self.last_visible = False


class _OverlayHost:
    def __init__(self, base_url, webview_module):
        parsed = urlparse(str(base_url))
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self.token = (parse_qs(parsed.query).get("token") or [""])[0]
        self.webview = webview_module
        self.controllers = {}
        self.closing = False
        self.last_contact = time.monotonic()
        self.window_revision = -1
        self.presentation_held = True

    def _url(self, path, overlay_id=None):
        suffix = f"token={quote(self.token)}"
        if overlay_id is not None:
            suffix += f"&overlay={quote(str(overlay_id))}"
        return f"{self.origin}{path}?{suffix}"

    def manifest(self):
        response = _request_json(
            self._url("/api/windows")
            + f"&since={int(self.window_revision)}&wait=0.75",
            timeout=1.25,
        )
        if not isinstance(response, dict):
            return {}
        try:
            self.window_revision = int(response.get("revision", self.window_revision))
        except (TypeError, ValueError):
            pass
        self.presentation_held = bool(response.get("presentation_held", False))
        if response.get("closing"):
            self.close()
            return {}
        overlays = response.get("overlays")
        return overlays if isinstance(overlays, dict) else {}

    def page_url(self, overlay_id, template):
        if template == "navigation":
            path = "/navigation_hud/index.html"
        elif template == "survey":
            path = "/survey/index.html"
        elif template == "toast":
            path = "/toast/index.html"
        elif template == "gravity":
            path = "/gravity/index.html"
        elif template == "ground":
            path = "/ground/index.html"
        else:
            path = "/overlays/index.html"
        return self._url(path, overlay_id)

    def create_window(self, overlay_id, spec, hidden=True):
        window_state = spec.get("window") if isinstance(spec, dict) else {}
        width = max(24, int((window_state or {}).get("width") or 360))
        height = max(24, int((window_state or {}).get("height") or 180))
        # Always create hidden surfaces in quarantine. The controller moves a
        # released window to its authoritative profile coordinates before it
        # calls ShowWindow, eliminating WebView2's dynamic-window startup flash.
        start_x = HIDDEN_WINDOW_X if hidden else int((window_state or {}).get("x") or 0)
        start_y = HIDDEN_WINDOW_Y if hidden else int((window_state or {}).get("y") or 0)
        window = self.webview.create_window(
            str(spec.get("title") or f"Void Compass {overlay_id}"),
            url=self.page_url(overlay_id, spec.get("template")),
            width=width, height=height, x=start_x, y=start_y,
            min_size=(24, 24), resizable=False, hidden=hidden,
            frameless=True, easy_drag=False, shadow=False, focus=False,
            on_top=True, transparent=True, background_color="#000000",
            text_select=False, zoomable=False,
        )
        self.controllers[str(overlay_id)] = _WindowController(overlay_id, window)
        return window

    def control_loop(self):
        last_status = {}
        while not self.closing:
            try:
                manifest = self.manifest()
                self.last_contact = time.monotonic()
                for overlay_id, spec in manifest.items():
                    if overlay_id not in self.controllers:
                        self.create_window(overlay_id, spec, hidden=True)
                    controller = self.controllers[overlay_id]
                    if spec.get("shutdown"):
                        controller.hide()
                        continue
                    result = controller.apply(
                        spec.get("window"),
                        presentation_held=self.presentation_held,
                    )
                    if result != last_status.get(overlay_id):
                        last_status[overlay_id] = result
                        try:
                            _request_json(self._url("/api/host-status", overlay_id), result)
                        except Exception:
                            pass
                    if result.get("ok") and not controller.ready_sent:
                        try:
                            _request_json(self._url("/api/ready", overlay_id), {})
                            controller.ready_sent = True
                        except Exception:
                            pass
                for overlay_id, controller in self.controllers.items():
                    if overlay_id not in manifest:
                        controller.hide()
            except Exception:
                if time.monotonic() - self.last_contact > 15.0:
                    self.close()
                    break
                time.sleep(0.1)

    def close(self):
        if self.closing:
            return
        self.closing = True
        for controller in list(self.controllers.values()):
            try:
                controller.window.destroy()
            except Exception:
                pass


def run(url):
    if os.name != "nt":
        return 2
    os.environ.setdefault("WEBVIEW2_DEFAULT_BACKGROUND_COLOR", "00000000")
    try:
        import webview
    except Exception:
        return 3
    host = _OverlayHost(url, webview)
    try:
        manifest = host.manifest()
        if not manifest:
            return 5
        first_id, first_spec = next(iter(manifest.items()))
        host.create_window(first_id, first_spec, hidden=True)
        webview.start(
            host.control_loop, gui="edgechromium", debug=False, private_mode=True,
        )
    except Exception:
        return 4
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return 1
    return run(argv[0])


if __name__ == "__main__":
    raise SystemExit(main())
