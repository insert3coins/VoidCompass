"""Windows display scaling, the same in every Void Compass process.

Overlay positions are stored in screen pixels and the overlay host places its
windows in screen pixels. Every process therefore runs per-monitor DPI aware:
otherwise a process Windows treats as unaware sees a shrunken desktop on a
display scaled above 100% (a 4K screen at 150% reads as 2560 x 1440), and
Overlay Studio stopped overlays well short of the right and bottom edges.
Overlay sizes are design sizes (CSS pixels at 100%); a window is made
``size x scale`` real pixels on its monitor so WebView2, which draws at that
monitor's scale, shows all of its content.
"""

from __future__ import annotations

import ctypes
import os

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
_PER_MONITOR_V2 = -4
_MONITOR_DEFAULTTONEAREST = 2
_MDT_EFFECTIVE_DPI = 0


def _library(name):
    """A private handle on a Windows DLL. Argument types set on the shared
    ctypes.windll objects apply to every caller in the process: setting them
    here once broke Overlay Studio's own GetMonitorInfoW, which then could not
    list the displays and showed the whole desktop as one."""
    cache = _library.__dict__.setdefault("cache", {})
    if name not in cache:
        cache[name] = ctypes.WinDLL(name, use_last_error=True)
    return cache[name]


def enable_per_monitor_dpi() -> bool:
    """Make this process per-monitor DPI aware. Call before any window or
    screen metric. Later calls (pywebview's SetProcessDPIAware) then fail
    harmlessly, because awareness can only be set once."""
    if os.name != "nt":
        return False
    try:
        user32 = _library("user32")
        setter = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if setter is not None:
            setter.argtypes = (ctypes.c_void_p,)
            setter.restype = ctypes.c_bool
            if setter(ctypes.c_void_p(_PER_MONITOR_V2)):
                return True
        # Windows 8.1: PROCESS_PER_MONITOR_DPI_AWARE.
        return _library("shcore").SetProcessDpiAwareness(2) == 0
    except (AttributeError, OSError):
        return False


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def monitor_scale(x, y) -> float:
    """The scale of the monitor nearest to screen point (x, y): 1.0 at 100%."""
    if os.name != "nt":
        return 1.0
    try:
        user32 = _library("user32")
        user32.MonitorFromPoint.argtypes = (_Point, ctypes.c_uint32)
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        monitor = user32.MonitorFromPoint(_Point(int(x), int(y)), _MONITOR_DEFAULTTONEAREST)
        dpi_x, dpi_y = ctypes.c_uint(), ctypes.c_uint()
        shcore = _library("shcore")
        shcore.GetDpiForMonitor.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint))
        if shcore.GetDpiForMonitor(monitor, _MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) != 0:
            return 1.0
        return max(1.0, min(4.0, dpi_x.value / 96.0))
    except (AttributeError, OSError):
        return 1.0


def monitor_handle_scale(handle) -> float:
    """The scale of an HMONITOR, as monitor_scale."""
    if os.name != "nt" or not handle:
        return 1.0
    try:
        dpi_x, dpi_y = ctypes.c_uint(), ctypes.c_uint()
        shcore = _library("shcore")
        shcore.GetDpiForMonitor.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint))
        if shcore.GetDpiForMonitor(ctypes.c_void_p(handle), _MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) != 0:
            return 1.0
        return max(1.0, min(4.0, dpi_x.value / 96.0))
    except (AttributeError, OSError):
        return 1.0


class _Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("rcMonitor", _Rect), ("rcWork", _Rect), ("dwFlags", ctypes.c_uint32)]


def room_below(x, y) -> int | None:
    """Design pixels from screen point (x, y) down to the bottom of its
    monitor's work area (above the taskbar), or None when unknown. An overlay
    that grows with its content keeps within this rather than running off
    the bottom of a smaller or scaled display."""
    if os.name != "nt":
        return None
    try:
        user32 = _library("user32")
        user32.MonitorFromPoint.argtypes = (_Point, ctypes.c_uint32)
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        monitor = user32.MonitorFromPoint(_Point(int(x), int(y)), _MONITOR_DEFAULTTONEAREST)
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.POINTER(_MonitorInfo))
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return max(0, int((info.rcWork.bottom - int(y)) / monitor_handle_scale(monitor)))
    except (AttributeError, OSError):
        return None
