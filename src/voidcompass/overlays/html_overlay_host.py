"""One isolated pywebview/WebView2 process for all cockpit overlays."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import sys
import time
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import build_opener, ProxyHandler, Request

from voidcompass.core.display_scale import monitor_scale


GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002
# The overlay form's own background, keyed out by Windows (5.5.1.9). Once a
# window has layered attributes (the OPACITY fade), Windows composites the
# form's background wherever the page is transparent: cut corners and the
# gaps between notifications showed as grey blocks (WinForms' 240 grey, faded).
# A colour no overlay draws, made see-through with LWA_COLORKEY.
OVERLAY_KEY_RGB = (1, 2, 3)
OVERLAY_KEY_COLORREF = OVERLAY_KEY_RGB[0] | (OVERLAY_KEY_RGB[1] << 8) | (OVERLAY_KEY_RGB[2] << 16)
HWND_TOPMOST = -1
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_DONOTROUND = 1
DWMWA_COLOR_NONE = 0xFFFFFFFE
HIDDEN_WINDOW_X = -32000
HIDDEN_WINDOW_Y = -32000
WINDOW_CREATE_INTERVAL_S = 0.25
DWMWA_CLOAK = 13
# Visual hosting (5.7.1). An overlay hidden for a map or a menu keeps drawing
# under its cloak this long, so it comes back at once; then it really hides.
HOLD_DRAWN_S = 10.0
# Overlays arriving together wait this long at most for their slowest page,
# and a page that never says it has drawn is taken as drawn after as long.
REVEAL_WAIT_S = 0.3
# A page's first draw, from cold at startup, takes longer.
FIRST_REVEAL_WAIT_S = 1.0
_LOOPBACK_OPENER = build_opener(ProxyHandler({}))
# One hidden, never-shown form owns every overlay (see _own_overlay_form).
_OVERLAY_OWNER = None


def _own_overlay_form(form, winforms_module):
    """Keep an overlay off the taskbar and out of Alt-Tab by giving it a
    hidden owner, rather than with the tool-window style.

    Windows gives owned windows no taskbar button and leaves them out of
    Alt-Tab, exactly like tool windows. The difference is OBS: its Window
    Capture lists ordinary windows but skips every tool window, so an owned
    overlay can be captured on its own ("Void Compass Navigation HUD").
    WinForms' Owner property sets the owner in place (no HWND recreation, so
    WebView2 stays attached) and WinForms keeps it. Returns False when the
    owner can't be made, and the overlay then stays a tool window.
    """
    global _OVERLAY_OWNER
    try:
        forms = winforms_module.WinForms
        if _OVERLAY_OWNER is None:
            owner = forms.Form()
            owner.ShowInTaskbar = False
            owner.Text = "Void Compass overlays"
            # Creating the handle makes the owner without ever showing it.
            if not owner.Handle:
                return False
            _OVERLAY_OWNER = owner
        form.Owner = _OVERLAY_OWNER
        return True
    except Exception:
        return False


def _patch_pywebview_overlay_focus(winforms_module=None):
    """Prepare pywebview overlays before their first native ``Show`` call.

    WinForms creates even ``hidden=True`` pywebview windows by showing and
    immediately hiding the form. Applying ``WS_EX_TOOLWINDOW`` only from the
    later host control pass is therefore too late: Explorer can register that
    first frame as an application window and flash Void Compass' grouped
    taskbar icon when an overlay appears. Patch the constructor so non-focused
    forms receive native tool-window styles before pywebview performs its
    internal first show. Do not set WinForms' ``ShowInTaskbar`` property here:
    changing it after WebView2 is attached recreates the HWND and strands the
    browser controller on the discarded handle.

    pywebview also unconditionally calls ``WebView.Focus`` from Form.Shown.
    Keep its lifecycle signal but omit that focus call for overlay windows.
    """
    try:
        if winforms_module is None:
            from webview.platforms import winforms as winforms_module

        browser_form = winforms_module.BrowserView.BrowserForm
        original_init = browser_form.__init__
        if not getattr(original_init, "_voidcompass_no_taskbar", False):
            def __init__(form, *args, **kwargs):
                original_init(form, *args, **kwargs)
                window = getattr(form, "pywebview_window", None)
                if getattr(window, "focus", True):
                    return
                # Owned before pywebview's first show, so Explorer never gives
                # the transient form a taskbar button. When an owner can't be
                # made, TOOLWINDOW does the same job (but hides it from OBS).
                window._voidcompass_owned = _own_overlay_form(form, winforms_module)
                # Change the existing HWND in place. SetWindowLongPtr preserves
                # WebView2's parent handle.
                _apply_windows_style(window, click_through=True)

            __init__._voidcompass_no_taskbar = True
            browser_form.__init__ = __init__

        original_shown = browser_form.on_shown
        if not getattr(original_shown, "_voidcompass_no_activate", False):
            def on_shown(form, *args):
                if getattr(form.pywebview_window, "focus", True):
                    return original_shown(form, *args)
                # BrowserForm.on_shown normally signals this before focusing
                # the child WebView. Keep the signal and omit only Focus().
                form.shown.set()
                return None

            on_shown._voidcompass_no_activate = True
            browser_form.on_shown = on_shown
        return True
    except Exception:
        return False


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


def _foreground_window():
    """Return the HWND that was active before an overlay was mapped."""
    if os.name != "nt":
        return 0
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        getter = user32.GetForegroundWindow
        getter.restype = ctypes.c_void_p
        return int(getter() or 0)
    except Exception:
        return 0


def _restore_foreground_window(hwnd):
    """Give focus back to the previously active application window.

    WebView2 can activate a newly mapped WinForms window even when pywebview
    was asked for ``focus=False`` and the HWND carries ``WS_EX_NOACTIVATE``.
    Reattach the host thread briefly when Windows rejects a direct foreground
    request, then detach immediately after the restoration.
    """
    try:
        hwnd = int(hwnd or 0)
    except (TypeError, ValueError):
        return False
    if not hwnd or os.name != "nt":
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        target = ctypes.c_void_p(hwnd)
        foreground = user32.SetForegroundWindow
        foreground.argtypes = (ctypes.c_void_p,)
        foreground.restype = ctypes.c_bool
        if bool(foreground(target)):
            return True

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        current_thread = kernel32.GetCurrentThreadId()
        process_id = ctypes.c_uint32()
        get_thread = user32.GetWindowThreadProcessId
        get_thread.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
        get_thread.restype = ctypes.c_uint32
        target_thread = get_thread(target, ctypes.byref(process_id))
        if not target_thread or target_thread == current_thread:
            return False
        attach = user32.AttachThreadInput
        attach.argtypes = (ctypes.c_uint32, ctypes.c_uint32, ctypes.c_bool)
        attach.restype = ctypes.c_bool
        if not bool(attach(current_thread, target_thread, True)):
            return False
        try:
            return bool(foreground(target))
        finally:
            attach(current_thread, target_thread, False)
    except Exception:
        return False


def _overlay_window_style(style, click_through=True, owned=False):
    """Return taskbar-free extended styles for an on-screen overlay.

    An owned overlay is already off the taskbar, and drops TOOLWINDOW so
    OBS's Window Capture can list it; an unowned one keeps TOOLWINDOW.
    """
    style = int(style) & ~WS_EX_APPWINDOW
    style |= WS_EX_LAYERED | WS_EX_NOACTIVATE
    if owned:
        style &= ~WS_EX_TOOLWINDOW
    else:
        style |= WS_EX_TOOLWINDOW
    if click_through:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    return style


def _opacity_alpha(value):
    """Overlay opacity (0.4-1) as a layered-window alpha byte."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 1.0
    return int(round(max(0.4, min(1.0, value)) * 255))


def _apply_overlay_key_background(window, rgb=OVERLAY_KEY_RGB):
    """Paint the overlay form's background in the key colour (UI thread)."""
    native = getattr(window, "native", None)
    if native is None:
        return False
    try:
        from System import Func, Type
        from System.Drawing import Color

        def paint():
            if bool(getattr(native, "IsDisposed", False)):
                return None
            native.BackColor = Color.FromArgb(255, *rgb)
            native.Invalidate(True)
            return None

        if bool(getattr(native, "InvokeRequired", False)):
            native.Invoke(Func[Type](paint))
        else:
            paint()
        return True
    except Exception:
        return False


def _apply_window_shape(window, shape):
    """Clip the window to a circle (the heartbeat orb) or give it back its
    full rectangle. A window region is never drawn outside, on any GPU, so a
    round overlay's corners can't show even where transparent pixels don't
    composite (5.5.3.3). A private user32/gdi32 handle, as everywhere here."""
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        set_region = user32.SetWindowRgn
        set_region.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
        set_region.restype = ctypes.c_int
        if shape != "circle":
            return bool(set_region(ctypes.c_void_p(hwnd), None, 1))
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.wintypes.RECT))
        if not user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect)):
            return False
        width, height = rect.right - rect.left, rect.bottom - rect.top
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        make = gdi32.CreateEllipticRgn
        make.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
        make.restype = ctypes.c_void_p
        region = make(0, 0, width + 1, height + 1)
        if not region:
            return False
        # The window owns the region from here (Windows frees it).
        return bool(set_region(ctypes.c_void_p(hwnd), ctypes.c_void_p(region), 1))
    except Exception:
        return False


def _apply_window_polygons(window, polygons):
    """Cut the window to the shapes its page draws (device px polygons from
    overlay-client), for the Dark box fix (5.5.3.3.1). Where WebView2 draws
    without the GPU, its transparent pixels come out black and no colour key
    reaches them (DirectComposition); a window region is the one thing that
    cuts them, on any PC."""
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        make = gdi32.CreatePolygonRgn
        make.argtypes = (ctypes.POINTER(ctypes.wintypes.POINT), ctypes.c_int, ctypes.c_int)
        make.restype = ctypes.c_void_p
        combine = gdi32.CombineRgn
        combine.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
        delete = gdi32.DeleteObject
        delete.argtypes = (ctypes.c_void_p,)
        whole = None
        for polygon in polygons:
            points = (ctypes.wintypes.POINT * len(polygon))(*(ctypes.wintypes.POINT(int(x), int(y)) for x, y in polygon))
            part = make(points, len(polygon), 2)  # WINDING
            if not part:
                continue
            if whole is None:
                whole = part
            else:
                combine(ctypes.c_void_p(whole), ctypes.c_void_p(whole), ctypes.c_void_p(part), 2)  # RGN_OR
                delete(ctypes.c_void_p(part))
        set_region = user32.SetWindowRgn
        set_region.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
        set_region.restype = ctypes.c_int
        if whole is None:
            return bool(set_region(ctypes.c_void_p(hwnd), None, 1))
        return bool(set_region(ctypes.c_void_p(hwnd), ctypes.c_void_p(whole), 1))
    except Exception:
        return False


def _window_has_region(window):
    """True when Windows reports a region on the window (the round cut)."""
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        make = gdi32.CreateRectRgn
        make.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
        make.restype = ctypes.c_void_p
        probe = make(0, 0, 0, 0)
        get = user32.GetWindowRgn
        get.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        get.restype = ctypes.c_int
        kind = get(ctypes.c_void_p(hwnd), ctypes.c_void_p(probe))
        gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
        gdi32.DeleteObject(ctypes.c_void_p(probe))
        return kind > 1  # SIMPLEREGION (2) or COMPLEXREGION (3); 0/1 none or error
    except Exception:
        return False


def _apply_window_alpha(window, alpha):
    """Fade the whole overlay window with Windows' layered-window alpha.

    The desktop compositor applies it to everything the window shows, and
    WebView2's per-pixel transparency is kept, so the overlay fades without
    depending on the browser's own GPU compositing. A private user32 handle:
    never set argtypes on the shared ctypes.windll functions.
    """
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        setter = user32.SetLayeredWindowAttributes
        setter.argtypes = (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_ubyte, ctypes.c_uint32)
        setter.restype = ctypes.c_int
        if getattr(window, "_voidcompass_composition", False):
            # Visual hosting (5.5.3.4.1): no form background under the page,
            # so the fade alone.
            return bool(setter(ctypes.c_void_p(hwnd), 0, int(alpha), LWA_ALPHA))
        # The fade, and the form background keyed out so transparent page
        # pixels stay see-through under it.
        _apply_overlay_key_background(window)
        return bool(setter(ctypes.c_void_p(hwnd), OVERLAY_KEY_COLORREF, int(alpha), LWA_ALPHA | LWA_COLORKEY))
    except Exception:
        return False


def _apply_windows_overlay_chrome(window):
    """Keep Windows 11 from decorating a frameless overlay HWND.

    DWM can independently add rounded corners and a one-pixel system border
    after pywebview creates or remaps a window.  Those pixels sit outside the
    transparent WebView surface, which makes clipped HUD panels look as if
    they have white or malformed corners.  Both attributes are best-effort so
    the same host continues to work on Windows versions that predate them.
    """
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        setter = dwmapi.DwmSetWindowAttribute
        setter.argtypes = (
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
        )
        setter.restype = ctypes.c_long
        corner = ctypes.c_int(DWMWCP_DONOTROUND)
        border = ctypes.c_uint32(DWMWA_COLOR_NONE)
        corner_result = setter(
            ctypes.c_void_p(hwnd),
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner),
            ctypes.sizeof(corner),
        )
        border_result = setter(
            ctypes.c_void_p(hwnd),
            DWMWA_BORDER_COLOR,
            ctypes.byref(border),
            ctypes.sizeof(border),
        )
        return corner_result == 0 or border_result == 0
    except Exception:
        return False


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
        style = _overlay_window_style(old_style, click_through, bool(getattr(window, "_voidcompass_owned", False)))
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
        _apply_windows_overlay_chrome(window)
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
    # ``native.webview`` is pywebview's public native-control hook.  Keep the
    # older BrowserForm.browser.webview route as a fallback for releases that
    # did not expose it directly.
    control = getattr(native, "webview", None)
    browser = getattr(native, "browser", None)
    if control is None and browser is not None:
        control = getattr(browser, "webview", None)
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
            transparent = Color.FromArgb(0, 0, 0, 0)
            restored = False
            try:
                control.DefaultBackgroundColor = transparent
                restored = True
            except Exception:
                pass
            # Newer WebView2 runtimes also expose the colour on the initialized
            # controller.  Reasserting both sides survives hide/show and
            # navigation races that otherwise leave an opaque white fallback.
            try:
                controller = getattr(control, "CoreWebView2Controller", None)
                if controller is not None:
                    controller.DefaultBackgroundColor = transparent
                    restored = True
            except Exception:
                pass
            try:
                control.Invalidate()
            except Exception:
                pass
            try:
                native.Invalidate(True)
            except Exception:
                pass
            if not restored:
                raise RuntimeError("WebView2 transparency property unavailable")
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
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        previous = _foreground_window() if visible else 0
        user32.ShowWindow(
            ctypes.c_void_p(hwnd), SW_SHOWNOACTIVATE if visible else SW_HIDE,
        )
        if visible and previous and previous != hwnd and _foreground_window() != previous:
            _restore_foreground_window(previous)
        return True
    except Exception:
        return False


def _cloak_window(window, cloaked):
    """DWM cloaking: a cloaked window stays shown (and its page keeps
    drawing) but isn't put on the screen. Many windows cloaked or uncloaked in
    one go change in the same frame, where ShowWindow takes milliseconds each."""
    hwnd = _native_handle(window)
    if not hwnd:
        return False
    try:
        value = ctypes.c_int(1 if cloaked else 0)
        return ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), DWMWA_CLOAK, ctypes.byref(value), ctypes.sizeof(value),
        ) == 0
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
    def __init__(self, overlay_id, window, restore_foreground=0):
        self.overlay_id = str(overlay_id)
        self.window = window
        self.restore_foreground = int(restore_foreground or 0)
        self.last_geometry = None
        self.last_click_through = None
        self.last_alpha = None
        self.last_shape = None
        self.last_visible = None
        self.reveal_waiting_since = None
        self.last_nudge = 0.0
        self.last_topmost_refresh = 0.0
        self.reload_revision = 0
        self.navigation_retries = 0
        self.last_navigation_retry_at = 0.0
        # Visual hosting only (5.7.1): see _apply_composed.
        self.cloaked = False
        self.mapped_at = 0.0
        self.pending_since = None
        self.pending_live = False
        self.render_ready = False
        self.held_since = None
        self.hide_due = False
        self.ever_shown = False
        self.veiled = False
        self.keep_mapped = False
        self.target_alpha = None

    def _nudge(self):
        """Ask the page to fetch its new data now. A hidden WebView2 throttles
        the page's own polling timer (to about once a minute after a few
        minutes hidden); a direct call is not throttled."""
        now = time.monotonic()
        if now - self.last_nudge < 0.25:
            return
        self.last_nudge = now
        try:
            self.window.run_js("window.__voidcompassPoll && window.__voidcompassPoll()")
        except Exception:
            pass

    def apply(self, payload, presentation_held=False, content_ready=True, render_current=True,
              strict_ready=False, push_updates=False):
        payload = payload if isinstance(payload, dict) else {}
        try:
            width = max(24, int(payload.get("width") or 360))
            height = max(24, int(payload.get("height") or 180))
            x = int(payload.get("x") or 0)
            y = int(payload.get("y") or 0)
            # Sizes are design pixels (100% scaling); WebView2 draws at the
            # monitor's scale, so the window must be that much bigger or the
            # overlay's lower and right parts are cut off.
            scale = monitor_scale(x + width // 2, y + height // 2)
            width, height = round(width * scale), round(height * scale)
            requested_geometry = (x, y, width, height)
            visible = bool(
                payload.get("visible", False)
                and not payload.get("shutdown")
                and not presentation_held
                and content_ready
            )
            wanted = visible
            # A hidden overlay is revealed only once its page has drawn the
            # latest model; otherwise it appeared showing whatever it drew
            # while hidden (the first planet of a system missing from Survey
            # until the next scan). Versioned clients also confirm the layout;
            # older clients keep their existing two-second reveal fallback.
            if not render_current and not push_updates:
                self._nudge()
            if visible and self.last_visible is not True and not render_current:
                now = time.monotonic()
                if self.reveal_waiting_since is None:
                    self.reveal_waiting_since = now
                if strict_ready or now - self.reveal_waiting_since < 2.0:
                    visible = False
            if visible or not payload.get("visible", False):
                self.reveal_waiting_since = None
            # WebView2/WinForms can map a dynamically created window despite
            # pywebview's hidden=True request. Keep every non-presentable
            # surface outside the desktop even after the boot curtain drops.
            # Only rendered content moves to its saved position before reveal.
            geometry = (
                (HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y, width, height)
                if not visible else requested_geometry
            )
            handle = _native_handle(self.window)
            if not handle:
                return {"ok": False, "reason": "native handle pending"}
            if getattr(self.window, "_voidcompass_composition", False):
                # Would be showing but for a map, a menu or the boot screen.
                held = bool((payload.get("held") or (presentation_held and payload.get("visible")))
                            and not payload.get("shutdown") and content_ready)
                return self._apply_composed(payload, requested_geometry, wanted, visible, held,
                                            handle, presentation_held, content_ready)
            resized = geometry != self.last_geometry
            if resized:
                if not _apply_windows_geometry(self.window, *geometry):
                    return {"ok": False, "reason": "native geometry unavailable", "handle": handle}
                self.last_geometry = geometry
            click_through = self._apply_surface(payload, resized)
            # WebView2 occasionally maps an asynchronously-created window
            # after our first SW_HIDE. Compare with the actual HWND instead of
            # trusting only last_visible, otherwise inactive transient HUDs
            # can remain on screen indefinitely with a false manifest state.
            native_visible = _windows_visibility(self.window)
            visibility_drifted = (
                native_visible is not None and native_visible != visible
            )
            visibility_changed = visible != self.last_visible or visibility_drifted
            if visibility_changed:
                if visible:
                    _apply_windows_style(self.window, click_through)
                    _apply_windows_geometry(self.window, *geometry)
                    _apply_webview_transparency(self.window)
                if _set_windows_visibility(self.window, visible):
                    self.last_visible = visible
                    if visible and self.last_shape == "circle":
                        # Showing the form can bring back its full rectangle
                        # on some PCs, as it can WebView2's opaque brush.
                        _apply_window_shape(self.window, "circle")
                    if visible:
                        # Showing the native form is the operation that can
                        # make WebView2 restore its opaque fallback brush.
                        _apply_webview_transparency(self.window)
                        if self.restore_foreground and _foreground_window() != self.restore_foreground:
                            _restore_foreground_window(self.restore_foreground)
                        self.restore_foreground = 0
                else:
                    self.last_visible = None
            self._keep_on_top(visible, click_through)
            return {
                "ok": True,
                "handle": handle,
                "visible": visible,
                "curtained": bool(presentation_held),
                # Mapping or unmapping one WebView2 form can disturb the
                # transparent composition brush on sibling forms in the
                # shared overlay process.  The host consumes this private
                # flag and repairs every surface in one pass.
                "_restore_all_transparency": bool(visibility_changed),
            }
        except Exception as exc:
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

    def _apply_surface(self, payload, resized):
        """Shape, opacity and click-through, the same for both kinds of
        window. Returns whether clicks pass through."""
        # The Dark box fix: the window cut to the shapes its page draws.
        polygons = payload.get("region") if isinstance(payload.get("region"), list) else None
        if polygons:
            key = repr(polygons)
            if key != getattr(self, "last_region", None) or resized:
                shaped = _apply_window_polygons(self.window, polygons)
                if shaped:
                    self.last_region = key
                    self.last_shape = "region"
                if ("region", shaped) != getattr(self, "last_shape_reported", None):
                    self.last_shape_reported = ("region", shaped)
                    print(f"Overlay window shape: {self.overlay_id} page shapes ({len(polygons)}) {'applied' if shaped else 'FAILED'}", flush=True)
        elif getattr(self, "last_region", None) is not None:
            self.last_region = None
            self.last_shape = None  # back to circle or rectangle below
        # A round overlay (the heartbeat orb) is clipped to a circle; a
        # resized circle is clipped again to its new size.
        shape = "circle" if payload.get("shape") == "circle" else "rect"
        if not polygons and (shape != self.last_shape or (resized and shape == "circle")):
            shaped = _apply_window_shape(self.window, shape)
            if shaped and shape == "circle":
                shaped = _window_has_region(self.window)
            if (shape, shaped) != getattr(self, "last_shape_reported", None):
                # In the logs (and a support bundle), once per change: did
                # the round cut take on this PC? (5.5.3.3)
                self.last_shape_reported = (shape, shaped)
                print(f"Overlay window shape: {self.overlay_id} {shape} {'applied' if shaped else 'FAILED'}", flush=True)
            if shaped:
                self.last_shape = shape
        # Overlay Studio's OPACITY. A window never faded keeps Windows'
        # default (no call at all), exactly as before.
        alpha = _opacity_alpha(payload.get("opacity", 1.0))
        self.target_alpha = alpha
        if not self.veiled and alpha != self.last_alpha and not (alpha == 255 and self.last_alpha is None):
            if _apply_window_alpha(self.window, alpha):
                self.last_alpha = alpha
        click_through = bool(payload.get("click_through", True))
        if click_through != self.last_click_through:
            _apply_windows_style(self.window, click_through)
            _apply_webview_transparency(self.window)
            self.last_click_through = click_through
        return click_through

    def _keep_on_top(self, visible, click_through):
        now = time.monotonic()
        if visible and now - self.last_topmost_refresh >= 12.0:
            _apply_windows_style(self.window, click_through)
            _apply_webview_transparency(self.window)
            # Keep the round cut: if something took it away, put it back
            # and say so in the logs.
            if self.last_shape == "circle" and not _window_has_region(self.window):
                restored = _apply_window_shape(self.window, "circle")
                print(f"Overlay window shape: {self.overlay_id} circle lost; {'restored' if restored else 'restore FAILED'}", flush=True)
            self.last_topmost_refresh = now

    def _cloak(self, cloaked):
        if _cloak_window(self.window, cloaked):
            self.cloaked = cloaked
            return True
        return False

    def _veil(self, veiled):
        """Fully transparent, but on the screen as far as the page knows."""
        alpha = 0 if veiled else (self.target_alpha if self.target_alpha is not None else 255)
        if not _apply_window_alpha(self.window, alpha):
            return False
        self.veiled = veiled
        if not veiled:
            self.last_alpha = alpha
        return True

    def _map_hidden(self, now, must_hide=False):
        """Show the window out of sight so its page draws, and ask the page to
        say when it has (a page loaded hidden gets no visibility event).
        Out of sight is under the cloak; the first time, it's veiled instead,
        as a page that has never been on the screen doesn't draw under one."""
        if self.ever_shown or not self._veil(True):
            hidden = self._cloak(True)
            if hidden and self.veiled:
                self._veil(False)
        else:
            hidden = True
            if self.cloaked:
                self._cloak(False)
        if must_hide and not hidden:
            return False
        if not _set_windows_visibility(self.window, True):
            return False
        self.mapped_at = now
        try:
            self.window.run_js("window.__voidcompassPainted && window.__voidcompassPainted()")
        except Exception:
            pass
        return True

    def _apply_composed(self, payload, geometry, wanted, ready, held, handle, presentation_held, content_ready):
        """Visual hosting (5.7.1): overlays reach the screen through DWM
        cloaking, so ones coming or going together do it in the same frame.
        ShowWindow one window after another put them up several frames apart.

        A window is shown under its cloak, draws, and the host uncloaks it
        with the rest of its group (_OverlayHost._settle). One hidden for a
        map or a menu (``held``) stays shown and drawing under its cloak for
        HOLD_DRAWN_S, so it comes back at once; after that it really hides
        and stops drawing, like any other hidden overlay."""
        now = time.monotonic()
        mapped = bool(_windows_visibility(self.window))
        if held and not wanted:
            if self.held_since is None:
                self.held_since = now
        else:
            self.held_since = None
        # Behind the boot screen, held for as long as it's up.
        keep_mapped = wanted or (held and (presentation_held or now - self.held_since < HOLD_DRAWN_S))
        self.keep_mapped = keep_mapped
        # Every page is drawn once out of sight as soon as it's ready (at
        # startup, behind the boot screen), so its first real show is quick.
        warming = not self.ever_shown and content_ready and not payload.get("shutdown")
        placed = keep_mapped or warming
        resized = False
        if placed or not mapped:
            target = geometry if placed else (HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y, geometry[2], geometry[3])
            resized = target != self.last_geometry
            if resized:
                if not _apply_windows_geometry(self.window, *target):
                    return {"ok": False, "reason": "native geometry unavailable", "handle": handle}
                self.last_geometry = target
        click_through = self._apply_surface(payload, resized)
        if not wanted:
            self.pending_since = None
            if mapped and not (self.cloaked or self.veiled):
                self._cloak(True)
            elif placed and not mapped:
                # Drawn ready for the map closing, the boot screen lifting, or
                # (warming) its first show.
                mapped = self._map_hidden(now, must_hide=True)
            # Really hidden after the loop, every one at once (and at once if
            # this PC won't cloak it).
            if mapped and not (warming and self.veiled) and (not keep_mapped or not (self.cloaked or self.veiled)):
                self.hide_due = True
            self.last_visible = False
        else:
            if not mapped:
                _apply_windows_style(self.window, click_through)
                if self._map_hidden(now) and self.last_shape == "circle":
                    _apply_window_shape(self.window, "circle")
            if self.cloaked or self.veiled:
                if self.pending_since is None:
                    self.pending_since = now
                    # Shown already: it has been drawing all along (a map or
                    # menu visit), so it needn't wait for its latest model.
                    self.pending_live = mapped
                self.render_ready = ready
            elif _windows_visibility(self.window):
                self.last_visible = True
        self._keep_on_top(self.last_visible is True, click_through)
        return {
            "ok": True,
            "handle": handle,
            "visible": self.last_visible is True,
            "curtained": bool(presentation_held),
        }

    def reveal_wait(self):
        return REVEAL_WAIT_S if self.ever_shown else FIRST_REVEAL_WAIT_S

    def framed(self, now):
        """Whether the page has drawn since its window was shown."""
        painted = float(getattr(self.window, "_voidcompass_painted_at", 0.0) or 0.0)
        return painted > self.mapped_at or now - self.mapped_at >= self.reveal_wait()

    def drawn(self, now):
        """Whether a window waiting out of sight is ready to be seen."""
        return self.framed(now) and (self.pending_live or self.render_ready)

    def hide(self):
        _set_windows_visibility(self.window, False)
        # Navigation can remap a WinForms window. Move it away before reloading,
        # not on the next manifest pass after navigation has already started.
        if self.last_geometry:
            _, _, width, height = self.last_geometry
            hidden_geometry = (HIDDEN_WINDOW_X, HIDDEN_WINDOW_Y, width, height)
            if _apply_windows_geometry(self.window, *hidden_geometry):
                self.last_geometry = hidden_geometry
        self.last_visible = False
        self.hide_due = False
        self.pending_since = None


class _OverlayHost:
    def __init__(self, base_url, webview_module, runtime=None):
        parsed = urlparse(str(base_url))
        # Visual hosting (5.5.3.4.1): composition_host's runtime makes the
        # windows; without one, pywebview does as before.
        self.runtime = runtime
        self.hosting = "composition"
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self.token = (parse_qs(parsed.query).get("token") or [""])[0]
        self.webview = webview_module
        self.controllers = {}
        self.closing = False
        self.last_contact = time.monotonic()
        self.last_window_created_at = 0.0
        self.failed_windows = set()
        self.window_revision = -1
        self.presentation_held = True
        self.last_delivery = {}
        # Overlays waiting under their cloaks: the host looks again soon.
        self.settling = False

    def _url(self, path, overlay_id=None):
        suffix = f"token={quote(self.token)}"
        if overlay_id is not None:
            suffix += f"&overlay={quote(str(overlay_id))}"
        return f"{self.origin}{path}?{suffix}"

    def manifest(self):
        now = time.monotonic()
        seen = {key: list(value[0][:3]) for key, value in self.last_delivery.items()
                if now - value[1] < 2.0}
        response = _request_json(
            self._url("/api/windows")
            + f"&since={int(self.window_revision)}&wait={'0.03' if getattr(self, 'settling', False) else '1'}"
            + f"&deliver=1&seen={quote(json.dumps(seen, separators=(',', ':')))}",
            timeout=2.25,
        )
        if not isinstance(response, dict):
            return {}
        try:
            self.window_revision = int(response.get("revision", self.window_revision))
        except (TypeError, ValueError):
            pass
        self.presentation_held = bool(response.get("presentation_held", False))
        self.hosting = str(response.get("hosting") or "composition")
        if response.get("closing"):
            self.close()
            return {}
        overlays = response.get("overlays")
        return overlays if isinstance(overlays, dict) else {}

    def page_url(self, overlay_id, template):
        if template == "navigation":
            path = "/navigation_hud/index.html"
        elif template == "cargo":
            path = "/cargo/index.html"
        elif template == "carrier":
            path = "/carrier/index.html"
        elif template == "prospector":
            path = "/prospector/index.html"
        elif template == "heartbeat":
            path = "/heartbeat/index.html"
        elif template == "galnet_ticker":
            path = "/galnet_ticker/index.html"
        elif template == "music_player":
            path = "/music_player/index.html"
        elif template == "survey":
            path = "/survey/index.html"
        elif template == "toast":
            path = "/toast/index.html"
        elif template == "gravity":
            path = "/gravity/index.html"
        elif template == "ground":
            path = "/ground/index.html"
        elif template == "station":
            path = "/station/index.html"
        elif template == "contact_scope":
            path = "/contact_scope/index.html"
        elif template == "jump_info":
            path = "/jump_info/index.html"
        elif template == "colony_needs":
            path = "/colony_needs/index.html"
        elif template == "trade_route":
            path = "/trade_route/index.html"
        elif template == "expedition":
            path = "/expedition/index.html"
        elif template == "hatchling":
            path = "/hatchling/index.html"
        elif template == "rig_tracker":
            path = "/rig_tracker/index.html"
        elif template == "galaxy_minimap":
            path = "/galaxy_minimap/index.html"
        elif template == "rhino_map":
            path = "/rhino_map/index.html"
        elif template == "postcards":
            path = "/postcards/index.html"
        elif template == "planet-materials-overlay":
            path = "/planet-materials-overlay/index.html"
        elif template == "powerplay-overlay":
            path = "/powerplay-overlay/index.html"
        else:
            raise ValueError(f"Unsupported semantic overlay template: {template}")
        url = self._url(path, overlay_id)
        # Visual hosting: the page says when it has drawn after being shown.
        return url + "&painted=1" if getattr(self, "runtime", None) is not None else url

    def create_window(self, overlay_id, spec, hidden=True):
        window_state = spec.get("window") if isinstance(spec, dict) else {}
        width = max(24, int((window_state or {}).get("width") or 360))
        height = max(24, int((window_state or {}).get("height") or 180))
        # Always create hidden surfaces in quarantine. The controller moves a
        # released window to its authoritative profile coordinates before it
        # calls ShowWindow, eliminating WebView2's dynamic-window startup flash.
        start_x = HIDDEN_WINDOW_X if hidden else int((window_state or {}).get("x") or 0)
        start_y = HIDDEN_WINDOW_Y if hidden else int((window_state or {}).get("y") or 0)
        restore_foreground = _foreground_window()
        if self.runtime is not None:
            window = self.runtime.create_window(
                str(spec.get("title") or f"Void Compass {overlay_id}"),
                self.page_url(overlay_id, spec.get("template")),
                width, height, start_x, start_y,
            )
            # These windows never take focus when made, so nothing to give
            # back on the first reveal. Restoring what had focus at creation
            # (usually the command deck, at startup) pulled the deck in front
            # of the game, or flashed its taskbar button (5.5.3.4.1).
            controller = _WindowController(overlay_id, window, restore_foreground=0)
            try:
                controller.reload_revision = int(spec.get("reload_revision") or 0)
            except (TypeError, ValueError):
                controller.reload_revision = 0
            self.controllers[str(overlay_id)] = controller
            self.last_window_created_at = time.monotonic()
            return window
        window = self.webview.create_window(
            str(spec.get("title") or f"Void Compass {overlay_id}"),
            url=self.page_url(overlay_id, spec.get("template")),
            width=width, height=height, x=start_x, y=start_y,
            min_size=(24, 24), resizable=False, hidden=hidden,
            frameless=True, easy_drag=False, shadow=False, focus=False,
            on_top=True, transparent=True, background_color="#000000",
            text_select=False, zoomable=False,
        )
        controller = _WindowController(
            overlay_id, window, restore_foreground=restore_foreground,
        )
        try:
            controller.reload_revision = int(spec.get("reload_revision") or 0)
        except (TypeError, ValueError):
            controller.reload_revision = 0
        self.controllers[str(overlay_id)] = controller
        self.last_window_created_at = time.monotonic()
        return window

    def _apply_manifest(self, manifest, last_status):
        changes = {}
        statuses = {}
        restore_shared_transparency = False
        # Classic WinForms still needs staggered navigation; composition controllers initialise asynchronously.
        created_window = False
        for overlay_id, spec in manifest.items():
            if overlay_id not in self.controllers:
                if (getattr(self, "runtime", None) is None and (created_window or time.monotonic()
                        - self.last_window_created_at
                        < WINDOW_CREATE_INTERVAL_S)):
                    continue
                try:
                    self.create_window(overlay_id, spec, hidden=True)
                except Exception as exc:
                    # One window that can't be made must not hold
                    # back every overlay after it (5.5.18).
                    self.last_window_created_at = time.monotonic()
                    if overlay_id not in self.failed_windows:
                        self.failed_windows.add(overlay_id)
                        print(f"Overlay window failed: {overlay_id} ({exc})", flush=True)
                    continue
                created_window = True
            controller = self.controllers[overlay_id]
            if spec.get("shutdown"):
                controller.hide()
                continue
            if (not spec.get("content_ready") and
                    bool(getattr(controller.window, "_voidcompass_navigation_failed", False))):
                now = time.monotonic()
                if (controller.navigation_retries < 2 and
                        now - controller.last_navigation_retry_at >= 1.5):
                    controller.window._voidcompass_navigation_failed = False
                    controller.hide()
                    controller.navigation_retries += 1
                    controller.last_navigation_retry_at = now
                    print(f"Overlay navigation retry: {overlay_id} ({controller.navigation_retries})", flush=True)
                    controller.window.load_url(self.page_url(
                        overlay_id, spec.get("template"),
                    ) + f"&host_retry={controller.navigation_retries}")
            elif spec.get("content_ready"):
                controller.navigation_retries = 0
            try:
                reload_revision = int(spec.get("reload_revision") or 0)
            except (TypeError, ValueError):
                reload_revision = 0
            if reload_revision > controller.reload_revision:
                controller.hide()
                print(f"Overlay page retry: {overlay_id} ({reload_revision})", flush=True)
                controller.window.load_url(self.page_url(
                    overlay_id, spec.get("template"),
                ) + f"&reload={reload_revision}")
                controller.reload_revision = reload_revision
            result = controller.apply(
                spec.get("window"),
                presentation_held=self.presentation_held,
                content_ready=bool(spec.get("content_ready", False)),
                render_current=bool(spec.get("render_current", True)),
                strict_ready=bool(spec.get("strict_ready", False)),
                push_updates=isinstance(spec.get("delivery"), dict),
            )
            self._deliver(overlay_id, controller.window, spec.get("delivery"))
            restore_shared_transparency = bool(
                result.pop("_restore_all_transparency", False)
            ) or restore_shared_transparency
            statuses[overlay_id] = result
        for overlay_id, controller in self.controllers.items():
            if overlay_id not in manifest:
                controller.hide()
        if restore_shared_transparency:
            for controller in self.controllers.values():
                if controller.last_visible:
                    _apply_webview_transparency(controller.window)
        for overlay_id in self._settle():
            if statuses.get(overlay_id, {}).get("ok"):
                statuses[overlay_id] = {**statuses[overlay_id], "visible": True}
        for overlay_id, result in statuses.items():
            if result != last_status.get(overlay_id):
                changes[overlay_id] = result
        return changes

    def _settle(self):
        """The second half of a pass under visual hosting: really hide the
        overlays that went (already cloaked, so they left the screen together),
        then uncloak the ones arriving, as one group. A group waits for its
        slowest page up to REVEAL_WAIT_S (FIRST_REVEAL_WAIT_S for a page never
        shown yet); a page slower than that joins on its own when it's ready.
        Returns the ids put on the screen."""
        now = time.monotonic()
        controllers = [controller for controller in self.controllers.values() if isinstance(controller, _WindowController)]
        for controller in controllers:
            if controller.hide_due:
                controller.hide()
        # Warmed: a page drawn once out of sight goes under its cloak, or away.
        for controller in controllers:
            if controller.veiled and controller.pending_since is None and controller.framed(now):
                controller.ever_shown = True
                if controller._cloak(True):
                    controller._veil(False)
                if not controller.keep_mapped:
                    controller.hide()
        pending = [controller for controller in controllers if controller.pending_since is not None]
        drawn = {controller.overlay_id: controller.drawn(now) for controller in pending}
        waiting = any(not drawn[controller.overlay_id] and now - controller.pending_since < controller.reveal_wait()
                      for controller in pending)
        arriving = [controller for controller in pending if drawn[controller.overlay_id]
                    and (not waiting or now - controller.pending_since >= controller.reveal_wait())]
        shown = [controller for controller in arriving
                 if (controller._veil(False) if controller.veiled else controller._cloak(False))]
        for controller in shown:
            controller.pending_since = None
            controller.last_visible = True
            controller.ever_shown = True
        # A page that never says it has drawn isn't watched closely forever;
        # its render confirmation still wakes the host.
        self.settling = any((controller.pending_since is not None and now - controller.pending_since < 2.0)
                            or (controller.veiled and now - controller.mapped_at < 2.0)
                            for controller in controllers)
        return [controller.overlay_id for controller in shown]

    def _deliver(self, overlay_id, window, packet):
        if not isinstance(packet, dict):
            return
        health = packet.get("health") or {}
        key = (packet["generation"], packet["layout_revision"], packet["revision"],
               health.get("frame_rate"), health.get("layout"))
        now = time.monotonic()
        previous = self.last_delivery.get(overlay_id)
        if previous and previous[0] == key and now - previous[1] < 2.0:
            return
        try:
            sender = getattr(window, "post_message", None)
            if callable(sender):
                sent = sender(packet)
            else:
                # Classic pywebview shares the same receiver. A direct host
                # call also bypasses hidden-page timer throttling.
                encoded = json.dumps(packet, ensure_ascii=True, separators=(",", ":"))
                window.run_js(f"window.__voidcompassDeliver && window.__voidcompassDeliver({encoded})")
                sent = True
            if sent:
                self.last_delivery[overlay_id] = (key, now)
        except Exception:
            # Unattached or navigating pages are retried by the shared feed.
            pass

    def control_loop(self):
        last_status = {}
        while not self.closing:
            try:
                manifest = self.manifest()
                self.last_contact = time.monotonic()
                runtime = getattr(self, "runtime", None)
                if runtime is not None:
                    changes = runtime.call(lambda: self._apply_manifest(manifest, last_status))
                else:
                    changes = self._apply_manifest(manifest, last_status)
                if changes:
                    try:
                        _request_json(self._url("/api/host-status-batch"), {"overlays": changes})
                        last_status.update(changes)
                    except Exception:
                        pass
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


def _run_composition(url):
    """Visual hosting (5.5.3.4.1): the overlays without WebView2's dark-mode
    base. None when it can't start here, and the pywebview host runs instead."""
    from voidcompass.overlays import composition_host

    if not composition_host.available():
        print("Overlay windows: visual hosting unavailable on this Windows; classic windows", flush=True)
        return None
    try:
        import webview.platforms.edgechromium  # noqa: F401  (the WebView2 assemblies and loader)
    except Exception as exc:
        print(f"Overlay windows: WebView2 unavailable for visual hosting ({type(exc).__name__}); classic windows", flush=True)
        return None
    host = _OverlayHost(url, None)
    manifest = host.manifest()
    if not manifest:
        return 5
    if host.hosting == "classic":
        print("Overlay windows: classic windows (Overlay Studio setting)", flush=True)
        return None
    runtime = composition_host.CompositionRuntime()
    if not runtime.start():
        print(f"Overlay windows: visual hosting failed ({runtime.error}); classic windows", flush=True)
        runtime.stop()
        return None
    host.runtime = runtime
    try:
        runtime.call(lambda: host._apply_manifest(manifest, {}))
        host.control_loop()
    finally:
        host.close()
        runtime.stop()
    return 0


def run(url):
    if os.name != "nt":
        return 2
    os.environ.setdefault("WEBVIEW2_DEFAULT_BACKGROUND_COLOR", "00000000")
    # The Hatchling's chirps (5.6.4): an overlay never gets a click to unlock sound.
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--autoplay-policy=no-user-gesture-required")
    try:
        result = _run_composition(url)
    except Exception as exc:
        print(f"Overlay windows: visual hosting stopped ({type(exc).__name__}: {exc}); classic windows", flush=True)
        result = None
    if result is not None:
        return result
    try:
        import webview
    except Exception:
        return 3
    if not _patch_pywebview_overlay_focus():
        return 3
    from voidcompass.core.webview_bootstrap import configure_embedded_navigation
    configure_embedded_navigation()
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
    from voidcompass.core.diagnostic_logs import TimestampedStream
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and not isinstance(stream, TimestampedStream):
            setattr(sys, name, TimestampedStream(stream))
    if not argv:
        return 1
    return run(argv[0])


if __name__ == "__main__":
    raise SystemExit(main())
