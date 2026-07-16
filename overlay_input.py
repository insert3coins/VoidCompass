"""Windows input-mode helpers for native Tk overlay windows."""

import ctypes
import os


GWL_EXSTYLE = -20
GA_ROOT = 2
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x00000002

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def overlay_ex_style(style, enabled):
    """Return the extended-window style for the requested input mode."""
    style = int(style or 0)
    if enabled:
        # Tk's chroma-key windows are layered already, but retaining the flag
        # here makes mouse pass-through reliable if a HUD changes its setup.
        return style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    return style & ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)


def set_mouse_passthrough(window, enabled=True):
    """Make a Tk top-level ignore mouse input, or restore interaction.

    Windows explicitly passes mouse events through a layered window carrying
    WS_EX_TRANSPARENT. Other platforms are left unchanged.
    """
    if os.name != "nt" or window is None:
        return False
    try:
        window.update_idletasks()
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        hwnd = int(window.winfo_id())
        root_hwnd = int(user32.GetAncestor(hwnd, GA_ROOT) or 0)
        if root_hwnd:
            hwnd = root_hwnd

        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_style.argtypes = (ctypes.c_void_p, ctypes.c_int)
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
        set_style.restype = ctypes.c_ssize_t
        user32.SetWindowPos.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_uint,
        )
        user32.SetWindowPos.restype = ctypes.c_int
        user32.SetLayeredWindowAttributes.argtypes = (
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_ubyte, ctypes.c_uint,
        )
        user32.SetLayeredWindowAttributes.restype = ctypes.c_int

        current = int(get_style(hwnd, GWL_EXSTYLE))
        wanted = overlay_ex_style(current, bool(enabled))
        if wanted != current:
            ctypes.set_last_error(0)
            previous = set_style(hwnd, GWL_EXSTYLE, wanted)
            if previous == 0 and ctypes.get_last_error():
                return False
            if enabled and not (current & WS_EX_LAYERED):
                # Non-chroma overlays (currently the ground-guidance popup)
                # need an explicit opaque alpha after becoming layered.
                user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
                | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
        window._mouse_passthrough = bool(enabled)
        return True
    except Exception:
        # Overlay input mode is a convenience/safety layer; a platform or
        # destroyed-window edge case must never stop the dashboard startup.
        return False
