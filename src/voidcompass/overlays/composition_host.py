"""Overlay windows with WebView2 in visual hosting (5.5.3.4).

Windowed hosting (pywebview's, and ours until 5.5.3.3.1) paints an opaque
base behind every transparent page whenever Windows is in dark mode: the dark
boxes round the overlays (WebView2Feedback #5752; seen on runtimes 153-155,
with no flag, theme or page setting that avoids it). In visual hosting
WebView2 draws into a DirectComposition visual that we own and put on our own
window, and that base is never painted.

Each overlay is a plain Win32 popup without a redirection surface
(WS_EX_NOREDIRECTIONBITMAP), so only the composition content shows; it stays
layered for click-through and the OPACITY fade, exactly as before. Everything
runs on one STA thread that pumps a hidden WinForms form's message loop: the
form owns every overlay (no taskbar button, and OBS can still list them) and
is the Invoke target for work from the host's control loop.

The window objects mimic what html_overlay_host uses of a pywebview window:
``native.Handle``, ``run_js``, ``load_url``, ``destroy`` and the navigation
flags, so the host's positioning, shapes, opacity and visibility code is the
same for both kinds.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import tempfile
import threading
import time
import uuid
from ctypes import wintypes

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOREDIRECTIONBITMAP = 0x00200000
LWA_ALPHA = 0x00000002
WM_SIZE = 0x0005
WM_SHOWWINDOW = 0x0018
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_ERASEBKGND = 0x0014
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
WM_MOUSEHWHEEL = 0x020E
WM_MOUSELEAVE = 0x02A3
WM_LBUTTONDOWN = 0x0201
WM_XBUTTONDBLCLK = 0x020D
MA_NOACTIVATE = 3
TME_LEAVE = 0x00000002
# DirectComposition (dcomp.h): IDCompositionDevice and its vtable slots.
IID_IDCOMPOSITION_DEVICE = "C37EA93A-E7AA-450D-B16F-9746CB0407F3"
DEVICE_COMMIT, DEVICE_CREATE_TARGET, DEVICE_CREATE_VISUAL = 3, 6, 7
TARGET_SET_ROOT = 3
COM_RELEASE = 2

_WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", _WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


class _TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("hwndTrack", wintypes.HWND),
                ("dwHoverTime", wintypes.DWORD)]


def _guid(text):
    value = uuid.UUID(text)
    return _GUID(value.time_low, value.time_mid, value.time_hi_version, (ctypes.c_ubyte * 8)(*value.bytes[8:]))


def _com(pointer, index, restype, *argtypes):
    """A COM method by vtable slot, for the few DirectComposition calls."""
    vtable = ctypes.cast(ctypes.c_void_p.from_address(pointer).value, ctypes.POINTER(ctypes.c_void_p))
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])


def _release(pointer):
    if pointer:
        try:
            _com(pointer, COM_RELEASE, ctypes.c_ulong)(pointer)
        except Exception:
            pass


def _user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.DefWindowProcW.argtypes = (wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                       wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = (wintypes.HWND,)
    user32.SetLayeredWindowAttributes.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD)
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.ScreenToClient.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    user32.SetCapture.argtypes = (wintypes.HWND,)
    user32.SetCursor.argtypes = (wintypes.HANDLE,)
    user32.TrackMouseEvent.argtypes = (ctypes.POINTER(_TRACKMOUSEEVENT),)
    return user32


class _Native:
    """What the host reads of ``window.native``: the HWND."""

    def __init__(self, handle):
        self.Handle = int(handle or 0)


class CompositionWindow:
    """One overlay: our popup window, its composition target and visual, and
    a WebView2 composition controller drawing into that visual."""

    _voidcompass_composition = True

    def __init__(self, runtime, title, url, width, height, x, y):
        self.runtime = runtime
        self.title = str(title)
        self.url = str(url)
        self.native = _Native(0)
        # Owned by the runtime's hidden form: off the taskbar, listed by OBS.
        self._voidcompass_owned = True
        self._voidcompass_navigation_failed = False
        self._voidcompass_renderer_failed = False
        self._voidcompass_navigation_completed_at = 0.0
        self.controller = None
        self._target = None
        self._visual = None
        self._tracking = False
        self._closed = False
        self._create(width, height, x, y)

    # -- creation (runtime thread) ---------------------------------------------
    def _create(self, width, height, x, y):
        runtime = self.runtime
        user32 = runtime.user32
        ex_style = WS_EX_NOREDIRECTIONBITMAP | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TRANSPARENT
        hwnd = user32.CreateWindowExW(ex_style, runtime.class_name, self.title, WS_POPUP,
                                      int(x), int(y), max(1, int(width)), max(1, int(height)),
                                      runtime.owner_hwnd, None, None, None)
        if not hwnd:
            raise OSError(f"CreateWindowEx failed ({ctypes.get_last_error()})")
        self.native = _Native(hwnd)
        runtime.windows[int(hwnd)] = self
        # A layered window shows nothing until it has layered attributes.
        user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
        target, visual = ctypes.c_void_p(), ctypes.c_void_p()
        device = runtime.device
        if _com(device, DEVICE_CREATE_TARGET, ctypes.c_long, wintypes.HWND, wintypes.BOOL,
                ctypes.POINTER(ctypes.c_void_p))(device, hwnd, True, ctypes.byref(target)) != 0:
            raise OSError("DirectComposition target unavailable")
        if _com(device, DEVICE_CREATE_VISUAL, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(device, ctypes.byref(visual)) != 0:
            raise OSError("DirectComposition visual unavailable")
        _com(target.value, TARGET_SET_ROOT, ctypes.c_long, ctypes.c_void_p)(target.value, visual.value)
        self._target, self._visual = target.value, visual.value
        runtime.commit()
        from System import IntPtr

        operation = runtime.environment.CreateCoreWebView2CompositionControllerAsync(IntPtr(int(hwnd)))
        operation.GetAwaiter().OnCompleted(runtime.action(lambda: self._attach(operation)))

    def _attach(self, operation):
        if self._closed:
            return
        try:
            if operation.IsFaulted:
                raise RuntimeError(str(operation.Exception))
            controller = operation.Result
        except Exception as exc:
            self._voidcompass_renderer_failed = True
            print(f"WebView2 failed to initialise: {type(exc).__name__}", flush=True)
            return
        from System import IntPtr
        from System.Drawing import Color, Rectangle
        from System.Runtime.InteropServices import Marshal

        self.controller = controller
        controller.DefaultBackgroundColor = Color.FromArgb(0, 0, 0, 0)
        rect = wintypes.RECT()
        self.runtime.user32.GetClientRect(self.native.Handle, ctypes.byref(rect))
        controller.Bounds = Rectangle(0, 0, max(1, rect.right), max(1, rect.bottom))
        controller.RootVisualTarget = Marshal.GetObjectForIUnknown(IntPtr(self._visual))
        controller.IsVisible = bool(self.runtime.user32.IsWindowVisible(self.native.Handle))
        self.runtime.commit()
        core = controller.CoreWebView2
        settings = core.Settings
        for name, value in (("AreDefaultContextMenusEnabled", False), ("AreDevToolsEnabled", False),
                            ("AreBrowserAcceleratorKeysEnabled", False), ("IsZoomControlEnabled", False),
                            ("IsPinchZoomEnabled", False), ("IsStatusBarEnabled", False),
                            ("IsSwipeNavigationEnabled", False), ("IsBuiltInErrorPageEnabled", False)):
            try:
                setattr(settings, name, value)
            except Exception:
                pass
        core.NewWindowRequested += self._on_new_window
        core.NavigationCompleted += self._on_navigation_completed
        controller.CursorChanged += self._on_cursor_changed
        core.Navigate(self.url)

    # -- WebView2 events (runtime thread) -------------------------------------
    def _on_new_window(self, _sender, args):
        args.Handled = True  # overlays never open windows

    def _on_navigation_completed(self, _sender, args):
        success = bool(getattr(args, "IsSuccess", True))
        self._voidcompass_navigation_failed = not success
        self._voidcompass_navigation_completed_at = time.monotonic()
        if not success:
            from urllib.parse import urlparse

            # Never the loopback token in diagnostics.
            print(f"WebView navigation failed: {urlparse(self.url).path} ({getattr(args, 'WebErrorStatus', 'unknown')})",
                  flush=True)

    def _on_cursor_changed(self, _sender, _args):
        self._apply_cursor()

    def _apply_cursor(self):
        try:
            cursor = self.controller.Cursor if self.controller is not None else None
            if cursor is not None:
                self.runtime.user32.SetCursor(int(cursor.ToInt64()))
                return True
        except Exception:
            pass
        return False

    # -- messages (runtime thread) ---------------------------------------------
    def handle(self, message, wparam, lparam):
        """A message for this window; None for the default handling."""
        if message == WM_ERASEBKGND:
            return 1
        if message == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        controller = self.controller
        if message == WM_SIZE and controller is not None:
            from System.Drawing import Rectangle

            controller.Bounds = Rectangle(0, 0, max(1, lparam & 0xFFFF), max(1, (lparam >> 16) & 0xFFFF))
            return 0
        if message == WM_SHOWWINDOW and controller is not None:
            # A hidden overlay stops drawing, as a hidden windowed WebView2 did.
            controller.IsVisible = bool(wparam)
            return None
        if message == WM_SETCURSOR and controller is not None and (lparam & 0xFFFF) == 1:  # HTCLIENT
            if self._apply_cursor():
                return 1
            return None
        if controller is not None and (WM_MOUSEMOVE <= message <= WM_MOUSEHWHEEL or message == WM_MOUSELEAVE):
            self._forward_mouse(controller, message, wparam, lparam)
            return 0
        return None

    def _forward_mouse(self, controller, message, wparam, lparam):
        """An overlay with mouse passthrough off takes the mouse: hand each
        message to WebView2, which has no window of its own to receive it."""
        from Microsoft.Web.WebView2.Core import CoreWebView2MouseEventKind, CoreWebView2MouseEventVirtualKeys
        from System.Drawing import Point

        user32 = self.runtime.user32
        hwnd = self.native.Handle
        mouse_data = 0
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        if message in (WM_MOUSEWHEEL, WM_MOUSEHWHEEL):
            mouse_data = ctypes.c_short((wparam >> 16) & 0xFFFF).value & 0xFFFFFFFF
            point = wintypes.POINT(x, y)  # wheel messages carry screen coordinates
            user32.ScreenToClient(hwnd, ctypes.byref(point))
            x, y = point.x, point.y
        elif message == WM_MOUSELEAVE:
            self._tracking = False
            x = y = 0
        else:
            if WM_LBUTTONDOWN <= message <= WM_XBUTTONDBLCLK:
                if message in (0x0201, 0x0204, 0x0207, 0x020B):  # a button down
                    user32.SetCapture(hwnd)
                elif message in (0x0202, 0x0205, 0x0208, 0x020C):  # a button up
                    user32.ReleaseCapture()
                if message >= 0x020B:  # X buttons: which one
                    mouse_data = (wparam >> 16) & 0xFFFF
            if not self._tracking:
                track = _TRACKMOUSEEVENT(ctypes.sizeof(_TRACKMOUSEEVENT), TME_LEAVE, hwnd, 0)
                self._tracking = bool(user32.TrackMouseEvent(ctypes.byref(track)))
        kind = _enum(CoreWebView2MouseEventKind, int(message))
        keys = _enum(CoreWebView2MouseEventVirtualKeys, 0 if message == WM_MOUSELEAVE else int(wparam & 0xFFFF))
        try:
            controller.SendMouseInput(kind, keys, mouse_data, Point(x, y))
        except Exception:
            pass

    # -- what the host calls (any thread) -------------------------------------
    def run_js(self, script):
        def run():
            if self.controller is not None and not self._closed:
                self.controller.CoreWebView2.ExecuteScriptAsync(str(script))
        self.runtime.post(run)

    def load_url(self, url):
        self.url = str(url)

        def navigate():
            if self.controller is not None and not self._closed:
                self._voidcompass_navigation_failed = False
                self.controller.CoreWebView2.Navigate(self.url)
        self.runtime.post(navigate)

    def destroy(self):
        self.runtime.call(self._destroy)

    def _destroy(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self.controller is not None:
                self.controller.Close()
        except Exception:
            pass
        self.controller = None
        hwnd = self.native.Handle
        self.runtime.windows.pop(int(hwnd), None)
        if hwnd:
            self.runtime.user32.DestroyWindow(hwnd)
        _release(self._visual)
        _release(self._target)
        self._visual = self._target = None


def _enum(enum_type, value):
    """A .NET enum member from its number (pythonnet takes either form)."""
    try:
        return enum_type(value)
    except Exception:
        import clr
        import System

        return System.Enum.ToObject(clr.GetClrType(enum_type), value)


class CompositionRuntime:
    """The STA thread, its message loop, the WebView2 environment and the
    DirectComposition device every overlay window shares."""

    class_name = "VoidCompassOverlay"

    def __init__(self, user_data_folder=None):
        self.user_data_folder = user_data_folder or tempfile.mkdtemp(prefix="voidcompass-overlays-")
        self._own_folder = user_data_folder is None
        self.windows = {}
        self.environment = None
        self.device = None
        self.owner = None
        self.owner_hwnd = None
        self.user32 = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self.error = None
        self._wndproc = _WNDPROC(self._window_proc)
        self._thread = None

    # -- lifetime -----------------------------------------------------------------
    def start(self, timeout=30.0):
        """Start the runtime thread; True once WebView2 and DirectComposition
        are ready. False (with ``error``) when either is unavailable."""
        from System.Threading import ApartmentState, Thread, ThreadStart

        self._thread = Thread(ThreadStart(self._run))
        self._thread.SetApartmentState(ApartmentState.STA)
        self._thread.IsBackground = True
        self._thread.Start()
        if not self._ready.wait(timeout):
            self.error = self.error or "timed out"
        return self.error is None

    def _run(self):
        try:
            import System.Windows.Forms as WinForms
            from Microsoft.Web.WebView2.Core import CoreWebView2Environment

            self.user32 = _user32()
            window_class = _WNDCLASSEXW(ctypes.sizeof(_WNDCLASSEXW), 0, self._wndproc, 0, 0, None, None, None, None,
                                        None, self.class_name, None)
            if not self.user32.RegisterClassExW(ctypes.byref(window_class)) and ctypes.get_last_error() != 1410:
                raise OSError(f"RegisterClassEx failed ({ctypes.get_last_error()})")
            owner = WinForms.Form()
            owner.ShowInTaskbar = False
            owner.Text = "Void Compass overlays"
            self.owner = owner
            self.owner_hwnd = int(owner.Handle.ToInt64())
            device = ctypes.c_void_p()
            result = ctypes.WinDLL("dcomp").DCompositionCreateDevice2(
                None, ctypes.byref(_guid(IID_IDCOMPOSITION_DEVICE)), ctypes.byref(device))
            if result != 0 or not device.value:
                raise OSError(f"DirectComposition unavailable ({result & 0xFFFFFFFF:#x})")
            self.device = device.value
            operation = CoreWebView2Environment.CreateAsync(None, self.user_data_folder, None)

            def environment_ready():
                try:
                    if operation.IsFaulted:
                        raise RuntimeError(str(operation.Exception))
                    self.environment = operation.Result
                    print(f"Overlay windows: visual hosting, WebView2 {self.environment.BrowserVersionString}", flush=True)
                except Exception as exc:
                    self.error = f"WebView2 unavailable: {type(exc).__name__}"
                self._ready.set()

            operation.GetAwaiter().OnCompleted(self.action(environment_ready))
            WinForms.Application.Run()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self._ready.set()
        finally:
            self._stopped.set()

    def stop(self):
        if self.owner is None:
            return

        def shutdown():
            for window in list(self.windows.values()):
                window._destroy()
            _release(self.device)
            self.device = None
            import System.Windows.Forms as WinForms

            WinForms.Application.ExitThread()
        try:
            self.call(shutdown)
        except Exception:
            pass
        self._stopped.wait(5.0)
        if self._own_folder:
            # WebView2's browser process lets go of its data a moment after
            # the last controller closes; keep trying for a few seconds.
            deadline = time.monotonic() + 8.0
            while os.path.isdir(self.user_data_folder) and time.monotonic() < deadline:
                shutil.rmtree(self.user_data_folder, ignore_errors=True)
                if os.path.isdir(self.user_data_folder):
                    time.sleep(.25)

    # -- the runtime thread -----------------------------------------------------
    @staticmethod
    def action(function):
        from System import Action

        return Action(function)

    def call(self, function):
        """Run on the runtime thread and wait for it (exceptions come back)."""
        if self.owner is None:
            return function()
        if not self.owner.InvokeRequired:
            return function()
        box = {}

        def run():
            try:
                box["value"] = function()
            except Exception as exc:
                box["error"] = exc
        self.owner.Invoke(self.action(run))
        if "error" in box:
            raise box["error"]
        return box.get("value")

    def post(self, function):
        """Run on the runtime thread later, without waiting."""
        if self.owner is None or self._stopped.is_set():
            return

        def run():
            try:
                function()
            except Exception as exc:
                print(f"Overlay window call failed: {type(exc).__name__}: {exc}", flush=True)
        try:
            self.owner.BeginInvoke(self.action(run))
        except Exception:
            pass

    def commit(self):
        if self.device:
            _com(self.device, DEVICE_COMMIT, ctypes.c_long)(self.device)

    def create_window(self, title, url, width, height, x, y):
        return self.call(lambda: CompositionWindow(self, title, url, width, height, x, y))

    def _window_proc(self, hwnd, message, wparam, lparam):
        window = self.windows.get(int(hwnd or 0))
        if window is not None:
            try:
                result = window.handle(message, wparam, lparam)
            except Exception:
                result = None
            if result is not None:
                return result
        return self.user32.DefWindowProcW(hwnd, message, wparam, lparam)


def available():
    """Visual hosting needs Windows 8.1 or later (DCompositionCreateDevice2)."""
    if os.name != "nt":
        return False
    try:
        return bool(getattr(ctypes.WinDLL("dcomp"), "DCompositionCreateDevice2", None))
    except OSError:
        return False
