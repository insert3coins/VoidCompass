"""Small Windows OS services; independent of application state and GUI toolkits."""
import ctypes
import logging
import os


def screen_size():
    if os.name == 'nt':
        return (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
    return 1920, 1080


def copy_text(text, attempts=20, wait_s=0.025):
    """Put ``text`` on the Windows clipboard.

    Another program often holds the clipboard for a moment (clipboard
    history and managers, Discord, OBS, remote desktop), so opening it is
    retried for about half a second. It's opened by a hidden window of our
    own: opened with no owner, Windows may refuse the write (5.5.12)."""
    if os.name != 'nt':
        raise RuntimeError('System clipboard requires Windows')
    import time
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    data = (str(text) + '\0').encode('utf-16-le')
    memory = kernel32.GlobalAlloc(0x0002, len(data))
    if not memory:
        raise OSError('Could not allocate clipboard memory')
    # A message-only window (HWND_MESSAGE) to own the clipboard.
    owner = user32.CreateWindowExW(0, "STATIC", None, 0, 0, 0, 0, 0, wintypes.HWND(-3), None, None, None)
    try:
        pointer = kernel32.GlobalLock(memory)
        if not pointer:
            raise OSError('Could not lock clipboard memory')
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(memory)
        for attempt in range(max(1, attempts)):
            if user32.OpenClipboard(owner):
                break
            time.sleep(wait_s)
        else:
            raise OSError('the clipboard is busy: another program has it open')
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(13, memory):
                raise OSError('Windows refused the clipboard write')
            memory = None  # Windows now owns the allocation.
        finally:
            user32.CloseClipboard()
    finally:
        if memory:
            kernel32.GlobalFree(memory)
        if owner:
            user32.DestroyWindow(owner)

class messagebox:
    @staticmethod
    def showerror(title, message, **_kwargs):
        logging.error('%s: %s', title, message)
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(None, str(message), str(title), 0x10)

    @staticmethod
    def showinfo(title, message, **_kwargs):
        logging.info('%s: %s', title, message)
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(None, str(message), str(title), 0x40)
