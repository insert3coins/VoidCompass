"""The music library: playlists of audio files wherever they live, with tags.

Void Compass plays music straight from where it already is on disk; nothing
is ever copied or moved. The library remembers each file once (its tags,
length, format and a cover thumbnail) and playlists list those files in
order. Playlists also import from and export to M3U/M3U8, the format every
player reads.

The dashboard page does the playing (it streams each track from the local
dashboard server by id), so this module keeps the lists and reads the tags.
Tags are read in the background: a thousand files appear at once under their
file names and fill in with their real titles, artists and covers.

On disk it is one folder: ``library.json`` and ``art/`` for cover thumbnails.
"""

from __future__ import annotations

import base64
from hashlib import sha1
import io
import json
import logging
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

# Formats the WebView2 player plays, and the type each is served as.
AUDIO_TYPES = {
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac",
    ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav",
    ".webm": "audio/webm",
}
PLAYLIST_TYPES = (".m3u", ".m3u8")
# Picture files rips keep beside their tracks, tried in this order when a
# track has no cover of its own.
FOLDER_COVERS = ("cover", "folder", "front", "album", "albumart")
MAX_TRACKS = 25000
MAX_NAME = 60
ART_SIZE = 360
OVERLAY_ART_SIZE = 128
_ID = re.compile(r"[0-9a-f]{16}")


def track_id(path) -> str:
    """A stable id for a file: the same file always gets the same id."""
    normal = os.path.normcase(os.path.abspath(str(path)))
    return sha1(normal.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def is_audio(path) -> bool:
    return Path(str(path)).suffix.casefold() in AUDIO_TYPES


def audio_type(path) -> str:
    return AUDIO_TYPES.get(Path(str(path)).suffix.casefold(), "application/octet-stream")


def _clean(value, limit=200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _natural(text):
    """Sort key that counts numbers as numbers: 2 comes before 10."""
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", str(text))]


def tags_from_name(path) -> dict:
    """Title, artist and number from a name like "03 - Artist - Title.flac"."""
    stem = Path(str(path)).stem.replace("_", " ")
    number = ""
    match = re.match(r"^\s*(\d{1,3})\s*[-._)\]]\s*(.+)$", stem)
    if match:
        number, stem = match.group(1).lstrip("0") or "0", match.group(2)
    artist, _, title = stem.partition(" - ")
    if not title:
        artist, title = "", stem
    return {"title": _clean(title) or _clean(stem), "artist": _clean(artist), "number": number}


def _first(value) -> str:
    """The first text of a tag, whichever shape the format stores it in."""
    if value is None:
        return ""
    text = getattr(value, "text", None)
    if text is not None:
        value = text
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if isinstance(value, tuple):
        value = value[0]
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return _clean(value)


def _year(value) -> str:
    match = re.search(r"\b(1[89]\d\d|2[01]\d\d)\b", _first(value))
    return match.group(1) if match else ""


def _number(value) -> str:
    """A track number from "3", "03/12" or MP4's (3, 12)."""
    if isinstance(value, list) and value and isinstance(value[0], tuple):
        return str(value[0][0] or "") if value[0][0] else ""
    match = re.match(r"\s*(\d+)", _first(value))
    return match.group(1).lstrip("0") if match else ""


def _format(audio, path) -> str:
    """A short description of the audio itself: "FLAC · 44.1 kHz · 24-bit"."""
    info = getattr(audio, "info", None)
    kind = Path(str(path)).suffix.lstrip(".").upper()
    parts = [{"OGA": "OGG", "M4A": "AAC" if "mp4a" in str(getattr(info, "codec", "mp4a")) else "ALAC"}.get(kind, kind)]
    rate = getattr(info, "sample_rate", 0) or 0
    bits = getattr(info, "bits_per_sample", 0) or 0
    bitrate = getattr(info, "bitrate", 0) or 0
    if kind in {"MP3", "OGG", "OPUS", "AAC", "M4A", "WEBM"} and bitrate:
        parts.append(f"{round(bitrate / 1000)} kbps")
    if rate:
        parts.append(f"{rate / 1000:g} kHz")
    if bits and kind in {"FLAC", "WAV", "M4A"}:
        parts.append(f"{bits}-bit")
    return " · ".join(parts)


def read_tags(path) -> dict:
    """Everything the player shows about one file, and its embedded cover."""
    named = tags_from_name(path)
    result = {"title": named["title"], "artist": named["artist"], "album": "", "album_artist": "",
              "year": "", "genre": "", "number": named["number"], "duration": 0.0,
              "format": Path(str(path)).suffix.lstrip(".").upper(), "cover": None}
    try:
        import mutagen
    except ImportError:
        return result
    try:
        audio = mutagen.File(str(path))
    except Exception as exc:
        logging.debug("Music tags unreadable for %s: %s", path, exc)
        return result
    if audio is None:
        return result
    length = getattr(getattr(audio, "info", None), "length", 0) or 0
    result["duration"] = round(float(length), 2) if length > 0 else 0.0
    result["format"] = _format(audio, path)
    tags = getattr(audio, "tags", None)
    if not tags:
        return result
    keys = {str(key) for key in tags.keys()}
    found, cover = {}, None
    if any(key.startswith(("TIT2", "TPE1", "TALB", "APIC")) for key in keys):
        # ID3v2: MP3, and WAV/AIFF files that carry an ID3 chunk.
        get = lambda name: tags.get(name)  # noqa: E731
        found = {"title": _first(get("TIT2")), "artist": _first(get("TPE1")), "album": _first(get("TALB")),
                 "album_artist": _first(get("TPE2")), "year": _year(get("TDRC") or get("TYER")),
                 "genre": _first(get("TCON")), "number": _number(get("TRCK"))}
        pictures = [frame for key, frame in tags.items() if str(key).startswith("APIC")]
        pictures.sort(key=lambda frame: 0 if getattr(frame, "type", 0) == 3 else 1)  # front cover first
        cover = pictures[0].data if pictures else None
    elif keys & {"\xa9nam", "\xa9ART", "\xa9alb", "covr"}:
        # MP4 atoms: M4A/AAC/ALAC.
        found = {"title": _first(tags.get("\xa9nam")), "artist": _first(tags.get("\xa9ART")),
                 "album": _first(tags.get("\xa9alb")), "album_artist": _first(tags.get("aART")),
                 "year": _year(tags.get("\xa9day")), "genre": _first(tags.get("\xa9gen")),
                 "number": _number(tags.get("trkn"))}
        covers = tags.get("covr") or []
        cover = bytes(covers[0]) if covers else None
    else:
        # Vorbis comments: FLAC, Ogg Vorbis, Opus.
        lower = {str(key).casefold(): value for key, value in tags.items()}
        found = {"title": _first(lower.get("title")), "artist": _first(lower.get("artist")),
                 "album": _first(lower.get("album")), "album_artist": _first(lower.get("albumartist")),
                 "year": _year(lower.get("date") or lower.get("year")), "genre": _first(lower.get("genre")),
                 "number": _number(lower.get("tracknumber"))}
        pictures = list(getattr(audio, "pictures", []) or [])
        if pictures:
            pictures.sort(key=lambda picture: 0 if getattr(picture, "type", 0) == 3 else 1)
            cover = pictures[0].data
        elif lower.get("metadata_block_picture"):
            try:
                from mutagen.flac import Picture
                cover = Picture(base64.b64decode(_first(lower.get("metadata_block_picture")))).data
            except Exception:
                cover = None
    for key, value in found.items():
        if value:
            result[key] = value
    if not result["artist"] and result["album_artist"]:
        result["artist"] = result["album_artist"]
    result["cover"] = cover
    return result


def folder_cover(path):
    """A cover image kept beside a track (cover.jpg, folder.png...), if any."""
    folder = Path(str(path)).parent
    try:
        pictures = {entry.stem.casefold(): entry for entry in folder.iterdir()
                    if entry.suffix.casefold() in {".jpg", ".jpeg", ".png", ".webp"} and entry.is_file()}
    except OSError:
        return None
    for name in FOLDER_COVERS:
        if name in pictures:
            return pictures[name]
    return None


def parse_m3u(path) -> tuple[list[dict], dict]:
    """The usable entries of an M3U/M3U8 playlist, and what was skipped.

    Relative paths resolve from the playlist's own folder and file:// URLs
    become paths. Web streams, missing files and formats the player cannot
    play are skipped and counted, so an import can say what it left out.
    """
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or str(path).casefold().endswith(".m3u8"):
        text = raw.decode("utf-8-sig", "replace")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            # Older players wrote .m3u in the Windows code page.
            text = raw.decode("cp1252", "replace")
    base = Path(path).resolve().parent
    entries = []
    skipped = {"streams": 0, "missing": 0, "unsupported": 0}
    hint = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            match = re.match(r"#EXTINF:\s*(-?[\d.]+)[^,]*,(.*)$", line, re.I)
            if match:
                shown = _clean(match.group(2))
                artist, _, title = shown.partition(" - ")
                hint = {"duration": max(0.0, float(match.group(1) or 0)),
                        "title": title or artist, "artist": artist if title else ""}
            continue
        if re.match(r"^[a-z][a-z0-9+.-]*://", line, re.I):
            parsed = urlparse(line)
            if parsed.scheme.casefold() != "file":
                skipped["streams"] += 1
                hint = {}
                continue
            remote = f"//{parsed.netloc}{parsed.path}" if parsed.netloc else parsed.path
            location = url2pathname(unquote(remote))
        else:
            location = line
        candidate = Path(location)
        if not candidate.is_absolute():
            candidate = base / candidate
        candidate = Path(os.path.normpath(str(candidate)))
        if not is_audio(candidate):
            skipped["unsupported"] += 1
        elif not candidate.is_file():
            skipped["missing"] += 1
        else:
            entries.append({"path": str(candidate), **hint})
        hint = {}
    return entries, skipped


def write_m3u(path, tracks) -> None:
    """Write tracks ({path, title, artist, duration}) as an extended M3U8."""
    lines = ["#EXTM3U"]
    for track in tracks:
        shown = " - ".join(part for part in (track.get("artist"), track.get("title")) if part)
        seconds = int(round(float(track.get("duration") or 0))) or -1
        lines.append(f"#EXTINF:{seconds},{shown}")
        lines.append(str(track.get("path") or ""))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class MusicLibrary:
    """Playlists and the tracks they list, kept in one folder."""

    def __init__(self, root, *, on_change=None):
        self.root = Path(root)
        self.art_root = self.root / "art"
        self.on_change = on_change
        self.revision = 0
        self._lock = threading.RLock()
        self._tracks: dict[str, dict] = {}
        self._playlists: list[dict] = []
        self._missing: dict[str, bool] = {}
        self._overlay_art: dict[str, str] = {}
        self._pending: list[str] = []
        self._worker = None
        self._load()

    # -- storage ---------------------------------------------------------------
    @property
    def file(self) -> Path:
        return self.root / "library.json"

    def _load(self):
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        tracks = data.get("tracks")
        if isinstance(tracks, dict):
            self._tracks = {str(key): dict(value) for key, value in tracks.items()
                            if _ID.fullmatch(str(key)) and isinstance(value, dict) and value.get("path")}
        for item in data.get("playlists") or []:
            if isinstance(item, dict) and item.get("id"):
                self._playlists.append({
                    "id": str(item["id"])[:40], "name": _clean(item.get("name"), MAX_NAME) or "Playlist",
                    "tracks": [str(key) for key in item.get("tracks") or [] if str(key) in self._tracks],
                    "created": float(item.get("created") or 0),
                })
        self.revision = int(data.get("revision") or 0)
        untagged = [key for key, track in self._tracks.items() if not track.get("tagged")]
        if untagged:
            self._queue_tags(untagged)

    def _save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "revision": self.revision, "tracks": self._tracks, "playlists": self._playlists}
        temporary = self.file.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, self.file)

    def _changed(self):
        self.revision += 1
        self._save()
        callback = self.on_change
        if callable(callback):
            try:
                callback()
            except Exception:
                logging.exception("Music library change callback failed")

    # -- reading ---------------------------------------------------------------
    def playlist(self, playlist_id):
        with self._lock:
            return next((item for item in self._playlists if item["id"] == str(playlist_id)), None)

    def track(self, identifier):
        with self._lock:
            track = self._tracks.get(str(identifier))
            return dict(track) if track else None

    def track_file(self, identifier):
        """The file a track plays from, if it is in the library and still there."""
        track = self.track(identifier)
        path = Path(track.get("path") or "") if track else None
        return path if path is not None and path.is_file() else None

    def art_file(self, identifier):
        identifier = str(identifier)
        if not _ID.fullmatch(identifier):
            return None
        path = self.art_root / f"{identifier}.jpg"
        return path if path.is_file() else None

    def overlay_art(self, identifier) -> str:
        """A small cover as a data URI, carried in the overlay's snapshot."""
        identifier = str(identifier)
        if identifier in self._overlay_art:
            return self._overlay_art[identifier]
        uri = ""
        source = self.art_file(identifier)
        if source is not None:
            try:
                from PIL import Image
                with Image.open(source) as image:
                    image = image.convert("RGB")
                    image.thumbnail((OVERLAY_ART_SIZE, OVERLAY_ART_SIZE))
                    buffer = io.BytesIO()
                    image.save(buffer, "JPEG", quality=84)
                uri = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
            except Exception as exc:
                logging.debug("Overlay cover unavailable for %s: %s", identifier, exc)
        if len(self._overlay_art) > 48:
            self._overlay_art.clear()
        self._overlay_art[identifier] = uri
        return uri

    def missing(self, identifier) -> bool:
        identifier = str(identifier)
        if identifier not in self._missing:
            track = self._tracks.get(identifier) or {}
            self._missing[identifier] = not Path(track.get("path") or "").is_file()
        return self._missing[identifier]

    def recheck_files(self):
        """Look at the files again: a drive may be back, or a file moved."""
        with self._lock:
            self._missing.clear()

    def pending(self) -> int:
        with self._lock:
            return len(self._pending)

    def payload(self) -> dict:
        """Everything the Music page lists, compactly."""
        with self._lock:
            return {
                "revision": self.revision,
                "tagging": len(self._pending),
                "playlists": [{"id": item["id"], "name": item["name"], "tracks": list(item["tracks"])}
                              for item in self._playlists],
                "tracks": {
                    key: {
                        "title": track.get("title") or "", "artist": track.get("artist") or "",
                        "album": track.get("album") or "", "album_artist": track.get("album_artist") or "",
                        "year": track.get("year") or "", "genre": track.get("genre") or "",
                        "number": track.get("number") or "", "format": track.get("format") or "",
                        "duration": float(track.get("duration") or 0), "art": bool(track.get("art")),
                        "missing": self.missing(key),
                    }
                    for key, track in self._tracks.items()
                },
            }

    # -- playlists ---------------------------------------------------------------
    def create_playlist(self, name) -> str:
        with self._lock:
            base = _clean(name, MAX_NAME) or "New playlist"
            taken = {item["name"].casefold() for item in self._playlists}
            label, counter = base, 2
            while label.casefold() in taken:
                label = f"{base[:MAX_NAME - 4]} {counter}"
                counter += 1
            identifier = secrets.token_hex(6)
            self._playlists.append({"id": identifier, "name": label, "tracks": [], "created": time.time()})
            self._changed()
            return identifier

    def rename_playlist(self, playlist_id, name) -> bool:
        with self._lock:
            playlist, label = self.playlist(playlist_id), _clean(name, MAX_NAME)
            if playlist is None or not label:
                return False
            playlist["name"] = label
            self._changed()
            return True

    def delete_playlist(self, playlist_id) -> bool:
        with self._lock:
            playlist = self.playlist(playlist_id)
            if playlist is None:
                return False
            self._playlists.remove(playlist)
            self._forget_unlisted()
            self._changed()
            return True

    def remove_tracks(self, playlist_id, positions) -> int:
        with self._lock:
            playlist = self.playlist(playlist_id)
            if playlist is None:
                return 0
            drop = set()
            for position in positions:
                try:
                    position = int(position)
                except (TypeError, ValueError):
                    continue
                if 0 <= position < len(playlist["tracks"]):
                    drop.add(position)
            if not drop:
                return 0
            playlist["tracks"] = [key for position, key in enumerate(playlist["tracks"]) if position not in drop]
            self._forget_unlisted()
            self._changed()
            return len(drop)

    def move_track(self, playlist_id, source, target) -> bool:
        with self._lock:
            playlist = self.playlist(playlist_id)
            if playlist is None:
                return False
            tracks = playlist["tracks"]
            if not (0 <= source < len(tracks) and 0 <= target < len(tracks)) or source == target:
                return False
            tracks.insert(target, tracks.pop(source))
            self._changed()
            return True

    def _forget_unlisted(self):
        """A track no playlist lists any more is forgotten, cover and all."""
        listed = {key for playlist in self._playlists for key in playlist["tracks"]}
        for key in [key for key in self._tracks if key not in listed]:
            self._tracks.pop(key, None)
            self._missing.pop(key, None)
            self._overlay_art.pop(key, None)
            try:
                (self.art_root / f"{key}.jpg").unlink(missing_ok=True)
            except OSError:
                pass

    # -- adding music --------------------------------------------------------------
    def expand(self, paths) -> list[str]:
        """The audio files in files and folders (folders walked in name order)."""
        found = []
        for entry in paths:
            path = Path(str(entry))
            if path.is_dir():
                for folder, subfolders, files in os.walk(path):
                    subfolders.sort(key=_natural)
                    for name in sorted(files, key=_natural):
                        if is_audio(name):
                            found.append(str(Path(folder) / name))
                            if len(found) >= MAX_TRACKS:
                                return found
            elif path.is_file() and is_audio(path):
                found.append(str(path))
                if len(found) >= MAX_TRACKS:
                    break
        return found

    def add_files(self, playlist_id, files, hints=None) -> int:
        """Add audio files to a playlist, in place; tags follow in the background."""
        hints = hints or {}
        with self._lock:
            playlist = self.playlist(playlist_id)
            if playlist is None:
                return 0
            added = []
            for file in files:
                path = os.path.abspath(str(file))
                if not is_audio(path):
                    continue
                key = track_id(path)
                if key not in self._tracks:
                    if len(self._tracks) >= MAX_TRACKS:
                        break
                    hint, named = hints.get(path) or {}, tags_from_name(path)
                    self._tracks[key] = {
                        "path": path, "title": hint.get("title") or named["title"],
                        "artist": hint.get("artist") or named["artist"], "album": "", "album_artist": "",
                        "year": "", "genre": "", "number": named["number"],
                        "format": Path(path).suffix.lstrip(".").upper(),
                        "duration": float(hint.get("duration") or 0), "art": False,
                        "added": time.time(), "tagged": False,
                    }
                    self._missing.pop(key, None)
                playlist["tracks"].append(key)
                added.append(key)
            if added:
                self._changed()
                self._queue_tags([key for key in dict.fromkeys(added) if not self._tracks[key].get("tagged")])
            return len(added)

    def import_m3u(self, path, playlist_id=None) -> dict:
        """Add an M3U/M3U8 to a playlist, or to a new one named after the file."""
        entries, skipped = parse_m3u(path)
        if not playlist_id or self.playlist(playlist_id) is None:
            playlist_id = self.create_playlist(Path(path).stem)
        hints = {os.path.abspath(entry["path"]): entry for entry in entries}
        added = self.add_files(playlist_id, [entry["path"] for entry in entries], hints)
        return {"playlist_id": playlist_id, "added": added, **skipped}

    def export_m3u(self, playlist_id, path) -> int:
        with self._lock:
            playlist = self.playlist(playlist_id)
            if playlist is None:
                return 0
            tracks = [dict(self._tracks[key]) for key in playlist["tracks"] if key in self._tracks]
        write_m3u(path, tracks)
        return len(tracks)

    def set_duration(self, identifier, seconds) -> bool:
        """The player measured a track's real length while playing it."""
        try:
            seconds = round(float(seconds), 2)
        except (TypeError, ValueError):
            return False
        with self._lock:
            track = self._tracks.get(str(identifier))
            if not track or not 0 < seconds < 86400 or abs(float(track.get("duration") or 0) - seconds) < .5:
                return False
            track["duration"] = seconds
            self._changed()
            return True

    # -- tags, read in the background -------------------------------------------------
    def _queue_tags(self, identifiers):
        with self._lock:
            waiting = set(self._pending)
            self._pending.extend(key for key in identifiers if key not in waiting)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._read_tags_worker, name="music-tags", daemon=True)
                self._worker.start()

    def _read_tags_worker(self):
        shown_at = time.monotonic()
        while True:
            with self._lock:
                if not self._pending:
                    self._worker = None
                    self._changed()
                    return
                key = self._pending.pop(0)
                track = dict(self._tracks.get(key) or {})
            if not track:
                continue
            tags = read_tags(track["path"])
            art = self._store_cover(key, tags.pop("cover", None), track["path"])
            with self._lock:
                current = self._tracks.get(key)
                if current is not None:
                    for field in ("title", "artist", "album", "album_artist", "year", "genre", "number", "format"):
                        if tags.get(field):
                            current[field] = tags[field]
                    if tags.get("duration"):
                        current["duration"] = tags["duration"]
                    current["art"] = art
                    current["tagged"] = True
                    self._overlay_art.pop(key, None)
                # A big import shows its progress without saving after every file.
                if time.monotonic() - shown_at > 1.5:
                    shown_at = time.monotonic()
                    self._changed()

    def _store_cover(self, key, data, path) -> bool:
        """Keep a thumbnail of the embedded cover, or of the folder's picture."""
        source = io.BytesIO(data) if data else folder_cover(path)
        if source is None:
            return False
        try:
            from PIL import Image
            self.art_root.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as image:
                image = image.convert("RGB")
                image.thumbnail((ART_SIZE, ART_SIZE))
                image.save(self.art_root / f"{key}.jpg", "JPEG", quality=86)
            return True
        except Exception as exc:
            logging.debug("Music cover unreadable for %s: %s", key, exc)
            return False

    def wait_idle(self, timeout=10.0) -> bool:
        """Block until the background tag reading is done (tests, shutdown)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if not self._pending and (self._worker is None or not self._worker.is_alive()):
                    return True
            time.sleep(.02)
        return False
