"""Small Windows OS services; independent of application state and GUI toolkits."""
import ctypes
import logging
import os


def screen_size():
    if os.name == 'nt':
        return (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
    return 1920, 1080


def copy_text(text):
    if os.name != 'nt':
        raise RuntimeError('System clipboard requires Windows')
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
    data = (str(text) + '\0').encode('utf-16-le')
    memory = kernel32.GlobalAlloc(0x0002, len(data))
    if not memory:
        raise OSError('Could not allocate clipboard memory')
    try:
        pointer = kernel32.GlobalLock(memory)
        if not pointer:
            raise OSError('Could not lock clipboard memory')
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(memory)
        if not user32.OpenClipboard(None):
            raise OSError('Clipboard is busy')
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(13, memory):
                raise OSError('Could not write clipboard')
            memory = None  # Windows now owns the allocation.
        finally:
            user32.CloseClipboard()
    finally:
        if memory:
            kernel32.GlobalFree(memory)


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
