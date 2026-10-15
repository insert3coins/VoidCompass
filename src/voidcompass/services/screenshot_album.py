"""The screenshot album (5.5.3.7): the deck's Screenshots page. Every picture
in the screenshot folder, newest first, the way the postcard album lists
postcards: by id (the page never sees a path), a small JPEG of each for the
gallery, the picture itself full size, a copy to the clipboard and the file
shown in its folder.

The converter names its PNGs ``<System>_<YYYY-MM-DD_HH-MM-SS>.png`` (with a
``_2`` and so on for several in a second), so the system comes from the name.
A BMP Elite has just written, not converted yet, is listed too. A caption
file beside a picture (Caption files on the Postcards page) is its postcard
in words, shown with it.
"""
from __future__ import annotations

import os
import re

from voidcompass.services.postcard_album import PostcardAlbum, postcard_id

_CONVERTED = re.compile(r"^(?P<system>.+)_(?P<stamp>\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d)(?:_\d+)?\.(?:png|jpe?g)$", re.I)
_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".bmp": "image/bmp"}
CAPTION_MAX = 2000
# Names that aren't a system: the converter's when it didn't know, and
# Elite's own.
_NOT_A_SYSTEM = {"unknown", "highresscreenshot", "screenshot"}


class ScreenshotAlbum(PostcardAlbum):
    EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")

    def _wanted(self, name):
        return True

    def rows(self):
        """Newest first: {id, title, system, at, file, kind, caption, favourite}."""
        out = []
        starred = self.starred()
        for modified, name, path in self._files():
            match = _CONVERTED.match(name)
            raw = name.lower().endswith(".bmp")
            high_res = name.casefold().startswith("highres")
            system = match.group("system") if match and match.group("system").casefold() not in _NOT_A_SYSTEM else ""
            title = system or ("Not converted yet" if raw else "High-res screenshot" if high_res
                               else "Unknown system" if match else os.path.splitext(name)[0])
            out.append({
                "id": postcard_id(name),
                "title": title,
                "system": system,
                "at": round(modified, 1),
                "file": name,
                "kind": "BMP" if raw else os.path.splitext(name)[1][1:].upper(),
                "high_res": high_res,
                "caption": caption_of(path),
                "favourite": name.casefold() in starred,
            })
        return out

    def picture(self, card_id):
        """The picture's bytes and type, as it is on disk."""
        path = self.path(card_id)
        if path is None:
            return None, ""
        try:
            with open(path, "rb") as handle:
                return handle.read(), _TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        except OSError:
            return None, ""


def caption_of(path):
    """The caption file beside a picture, if it has one."""
    try:
        with open(os.path.splitext(path)[0] + ".txt", encoding="utf-8") as handle:
            return handle.read(CAPTION_MAX).strip()
    except (OSError, UnicodeDecodeError):
        return ""
