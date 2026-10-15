"""The postcard album (5.5.3.7): the postcards saved as pictures, for the
deck's Postcards page. Listed newest first from the postcard folder, each by
an id made from its file name (the page never sees a path); a small JPEG of
each for the gallery, the PNG itself full size, and on Windows a copy to the
clipboard (to paste into Discord and the like) or the file shown in its
folder.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import threading

MAX_SHOWN = 300
THUMB_WIDTH = 420
# A postcard, or a constellation saved from its page (5.5.3.7).
_NAME = re.compile(r"^(?:Postcard|Constellation) - (?P<title>.+) - (?P<stamp>\d{4}-\d\d-\d\d \d\d-\d\d-\d\d)(?: \(\d+\))?\.png$", re.I)


def postcard_id(name):
    return hashlib.sha1(str(name).encode("utf-8")).hexdigest()[:16]


FAVOURITES_MAX = 5000


class Favourites:
    """The pictures starred on the Postcards and Screenshots pages (5.5.3.7),
    by file name, one list a page, in one small JSON file (keepsakes.json in
    Void Compass's own folder): {"postcards": [...], "screenshots": [...]}.
    """

    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.Lock()
        self._data = None

    def _load(self):
        if self._data is None:
            try:
                with open(self.path, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                data = {}
            self._data = {kind: [str(name) for name in names][:FAVOURITES_MAX]
                          for kind, names in (data.items() if isinstance(data, dict) else ())
                          if isinstance(names, list)}
        return self._data

    def names(self, kind):
        with self._lock:
            return {name.casefold() for name in self._load().get(kind, ())}

    def set(self, kind, name, on):
        """Star or unstar one picture; kept at once."""
        with self._lock:
            data = self._load()
            names = [item for item in data.get(kind, ()) if item.casefold() != str(name).casefold()]
            if on:
                names.insert(0, str(name))
            data[kind] = names[:FAVOURITES_MAX]
            temporary = self.path + ".part"
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
                with open(temporary, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, indent=1)
                os.replace(temporary, self.path)
            except OSError:
                return False
        return True


class PostcardAlbum:
    # The pictures it lists (the Screenshots page's album adds more).
    EXTENSIONS = (".png",)

    def __init__(self, folder):
        """``folder`` is a callable giving the postcard folder now (it can
        change in Settings)."""
        self._folder = folder
        self._lock = threading.Lock()
        self._thumbs = {}
        # How many pictures the folder holds (only the newest are listed).
        self.total = 0
        # The Postcards page's preview: a callable giving PNG bytes.
        self.preview_source = None
        # Its stars (a Favourites, set by the deck) and its list in them.
        self.favourites = None
        self.favourites_kind = "postcards"

    def folder(self):
        return str(self._folder() or "")

    def _wanted(self, name):
        # Constellations have their own page and folder since 5.5.4.
        return not name.casefold().startswith("constellation - ")

    def _files(self):
        folder = self.folder()
        try:
            names = [name for name in os.listdir(folder) if name.lower().endswith(self.EXTENSIONS) and self._wanted(name)]
        except OSError:
            self.total = 0
            return []
        found = []
        for name in names:
            path = os.path.join(folder, name)
            try:
                found.append((os.path.getmtime(path), name, path))
            except OSError:
                continue
        found.sort(reverse=True)
        self.total = len(found)
        return found[:MAX_SHOWN]

    def starred(self):
        return self.favourites.names(self.favourites_kind) if self.favourites is not None else set()

    def rows(self):
        """Newest first: {id, title, at, file, favourite}."""
        out = []
        starred = self.starred()
        for modified, name, _path in self._files():
            match = _NAME.match(name)
            out.append({"id": postcard_id(name), "title": match.group("title") if match else name[:-4],
                        "at": round(modified, 1), "file": name, "favourite": name.casefold() in starred})
        return out

    def set_favourite(self, card_id, on):
        path = self.path(card_id)
        if path is None or self.favourites is None:
            return False
        return self.favourites.set(self.favourites_kind, os.path.basename(path), bool(on))

    def path(self, card_id):
        for _modified, name, path in self._files():
            if postcard_id(name) == card_id:
                return path
        return None

    def full(self, card_id):
        path = self.path(card_id)
        if path is None:
            return None
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except OSError:
            return None

    def thumb(self, card_id):
        """A small JPEG of the postcard, made once per file version."""
        path = self.path(card_id)
        if path is None:
            return None
        try:
            key = (card_id, os.path.getmtime(path))
        except OSError:
            return None
        with self._lock:
            if key in self._thumbs:
                return self._thumbs[key]
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.load()
                ground = Image.new("RGB", image.size, (14, 20, 28))
                ground.paste(image, (0, 0), image if image.mode == "RGBA" else None)
            ground.thumbnail((THUMB_WIDTH, THUMB_WIDTH))
            out = io.BytesIO()
            ground.save(out, "JPEG", quality=82, optimize=True)
            data = out.getvalue()
        except (ImportError, OSError, ValueError):
            return None
        with self._lock:
            self._thumbs = {k: v for k, v in self._thumbs.items() if k[0] != card_id}
            self._thumbs[key] = data
        return data

    def preview(self):
        source = self.preview_source
        try:
            return source() if callable(source) else None
        except Exception:
            return None

    def delete(self, card_id):
        """The picture to the Recycle Bin (5.5.5), with the card kept beside
        it for editing, and its star. True when it's gone."""
        path = self.path(card_id)
        if path is None:
            return False
        stem = os.path.splitext(os.path.basename(path))[0]
        sidecars = [os.path.join(os.path.dirname(path), ".cards", stem + suffix) for suffix in (".json", ".jpg")]
        if not recycle([path] + [item for item in sidecars if os.path.isfile(item)]):
            return False
        if self.favourites is not None:
            self.favourites.set(self.favourites_kind, os.path.basename(path), False)
        with self._lock:
            self._thumbs = {key: value for key, value in self._thumbs.items() if key[0] != card_id}
        return True

    def show_in_folder(self, card_id):
        path = self.path(card_id)
        if path is None or os.name != "nt":
            return False
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return True
        except OSError:
            return False

    def copy(self, card_id):
        """The postcard on the Windows clipboard, as a picture."""
        path = self.path(card_id)
        if path is None:
            return False
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.load()
                ground = Image.new("RGB", image.size, (255, 255, 255))
                ground.paste(image, (0, 0), image if image.mode == "RGBA" else None)
            out = io.BytesIO()
            ground.save(out, "BMP")
        except (ImportError, OSError, ValueError):
            return False
        return copy_dib(out.getvalue()[14:])  # a BMP without its file header is a DIB


class ConstellationAlbum(PostcardAlbum):
    """Constellations saved as pictures (5.5.4), in their own folder, for
    the Constellation page: ``Constellation - <name> - <stamp>.png``."""

    def _wanted(self, name):
        return name.casefold().startswith("constellation - ")


def recycle(paths):
    """Files to the Recycle Bin on Windows (they can be put back); deleted
    elsewhere. True when none are left."""
    paths = [os.path.abspath(path) for path in paths if os.path.exists(path)]
    if not paths:
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
        # FO_DELETE with undo, no prompt, no progress, no error box.
        operation = SHFILEOPSTRUCTW(None, 3, "\0".join(paths) + "\0\0", None, 0x40 | 0x10 | 0x04 | 0x400, False, None, None)
        try:
            ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
        except (OSError, AttributeError):
            pass
    else:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass
    return not any(os.path.exists(path) for path in paths)


def copy_dib(dib):
    """Put a device-independent bitmap on the Windows clipboard."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
    user32.OpenClipboard.argtypes = (wintypes.HWND,)
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.SetClipboardData.restype = wintypes.HANDLE
    gmem_moveable, cf_dib = 0x0002, 8
    handle = kernel32.GlobalAlloc(gmem_moveable, len(dib))
    if not handle:
        return False
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        return False
    ctypes.memmove(pointer, dib, len(dib))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        return False
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(cf_dib, handle):
            kernel32.GlobalFree(handle)
            return False
        return True  # the clipboard owns the memory now
    finally:
        user32.CloseClipboard()
