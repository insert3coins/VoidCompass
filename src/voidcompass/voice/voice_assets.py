"""Downloading the Watcher's voice: the Piper engine and the HAL model.

Neither ships with Void Compass. The engine comes from Piper's own release
and the model from our GitHub repo (models/hal9000), both on the commander's
first switch-on, into models/ beside the app: the same layout as the repo,
so a source checkout already has the model and only fetches the engine.
Every file is checked against its pinned SHA-256 before it is used.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import threading
import urllib.request
import zipfile

from voidcompass.core.platform_support import application_dir
from voidcompass.core import companions

ENGINE = {
    "name": "Piper engine",
    "url": "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip",
    "sha256": "f3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea",
    "size": 22477236,
}
MODEL_URL = "https://raw.githubusercontent.com/insert3coins/VoidCompass/master/models/hal9000/"
MODEL_FILES = (
    {"name": "hal.onnx", "sha256": "0e08c82dc027bc72b8b839324801709e205e8c201ccae171b92e37a664d94361", "size": 63516050},
    {"name": "hal.onnx.json", "sha256": "cb6f82c03fc9e6db1f3b6978b9601bab9854f92c40d3a0681501944b8c26745e", "size": 7087},
)
DOWNLOAD_BYTES = ENGINE["size"] + sum(row["size"] for row in MODEL_FILES)
ASTER_MODEL_FILES = (
    {"name": "en_GB-jarvis-medium.onnx", "sha256": "0b222b43cb882aac25c4eb1b648c80fd855de423351dc778c01102e578c3a64d", "size": 63511037},
    {"name": "en_GB-jarvis-medium.onnx.json", "sha256": "8e189c86e055b672a3380cc68e1c74fe88206b1b0b5c5b1ac791b5511921be90", "size": 5068},
)
ASTER_MODEL_URL = "https://raw.githubusercontent.com/insert3coins/VoidCompass/master/models/jarvis/onnx/"
ASTER_NOTICE = "Aster uses praharshbhatt's British-English JARVIS Piper voice. Its model card limits use to personal, non-commercial purposes. The source voice is separate from Aster's original character and story."
AXIOM_MODEL_FILES = (
    {"name": "en_US-data_7024-medium.onnx", "sha256": "b3b4b9578a0bc0bbd21385a21f9c89d57be90bdf31087e73378a3a232002a76f", "size": 63516050},
    {"name": "en_US-data_7024-medium.onnx.json", "sha256": "2270937a50fb2b1cb3c79b5227abe56b060ee680cb2c3ba3b52ef366be937304", "size": 4846},
)
MERIDIAN_MODEL_FILES = (
    {"name": "en_US-picard_7399-medium.onnx", "sha256": "24edef8d75b26f498ffc995b933446229f527c66967514ab96b978f1e54c750c", "size": 63516050},
    {"name": "en_US-picard_7399-medium.onnx.json", "sha256": "4d4ad126bb0089b7f48f49a8c7349a82ec92afc49fccc934b395976a6629bbce", "size": 4848},
)

# 5.7.6: Lyra's robot voice, kept in models/lyra/ like the others.
LYRA_MODEL_FILES = (
    {"name": "glados.onnx", "sha256": "17ea16dd18e1bac343090b8589042b4052f1e5456d42cad8842a4f110de25095", "size": 63511038},
    {"name": "glados.onnx.json", "sha256": "01f5e602e1ec04daec6d54960e4d641b5de305f39186e40bf9b4a47bd757a489", "size": 7097},
)
LYRA_NOTICE = ("Lyra uses a GLaDOS-style robot Piper voice (rokeya71/VITS-Piper-GlaDOS-en-onnx, from the dnhkng/GLaDOS project). "
               "The mirror labels the model MIT; that says nothing about rights in the game recordings or the character voice "
               "it was trained on. Source filenames and attribution are kept in models/lyra. Lyra herself is this app's own character.")
_RAW = "https://raw.githubusercontent.com/insert3coins/VoidCompass/master/models/"
# Each companion's voice: (folder under models/, files, download URL, name, receipt folder).
# Files and URLs are named, not copied, so they are read when used.
VOICES = {
    "watcher": ("hal9000", "MODEL_FILES", "MODEL_URL", "HAL 9000 voice", ""),
    "aster": ("jarvis/onnx", "ASTER_MODEL_FILES", "ASTER_MODEL_URL", "Aster officer voice", "jarvis"),
    "axiom": ("data", "AXIOM_MODEL_FILES", _RAW + "data/", "Axiom voice", "data"),
    "meridian": ("picard", "MERIDIAN_MODEL_FILES", _RAW + "picard/", "Meridian voice", "picard"),
    "lyra": ("lyra", "LYRA_MODEL_FILES", _RAW + "lyra/", "Lyra voice", "lyra"),
}


def model_name(model):
    if companions.overlay_only(model):
        return "Voice pending"
    return VOICES.get(model, VOICES["watcher"])[3]


def notice(model):
    if model in ("axiom", "meridian"):
        source = "Data" if model == "axiom" else "Picard"
        return (f"{companions.NAMES[model]} uses the {source} Piper model from dividebysandwich/piper-voice-models, "
                "trained on Star Trek Generations game dialogue. The downloaded source includes no licence or usage terms. "
                "Source filenames and attribution are retained in models/. The voice source is separate from the companion identity.")
    return {"aster": ASTER_NOTICE, "lyra": LYRA_NOTICE}.get(model, RIGHTS_NOTICE)


def manifest(model="watcher"):
    if companions.overlay_only(model):
        raise ValueError("This companion has no voice model yet")
    folder, files, url, _name, _receipt = VOICES.get(model, VOICES["watcher"])
    return folder, globals()[files], globals().get(url, url)


def download_bytes(model="watcher"):
    return ENGINE["size"] + sum(row["size"] for row in manifest(model)[1])

# Shown before the download, as the model's own README asks.
RIGHTS_NOTICE = (
    "The HAL 9000 voice model (campwill/HAL-9000-Piper-TTS) was trained on the voice of HAL 9000 "
    "from 2001: A Space Odyssey (1968), performed by Douglas Rain. Separate copyright, personality "
    "and publicity rights may apply to that voice and character. It is offered for personal use; "
    "think twice before broadcasting it."
)

_CHUNK = 256 * 1024
_USER_AGENT = "VoidCompass voice download"
_INSTALL_LOCK = threading.Lock()


def voice_dir(base=None) -> Path:
    return Path(base or application_dir()) / "models"


def engine_exe(base=None) -> Path:
    return voice_dir(base) / "piper" / "piper.exe"


def model_path(base=None, model="watcher") -> Path:
    folder, files, _url = manifest(model)
    return voice_dir(base) / folder / files[0]["name"]


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _receipt(base=None, model="watcher") -> Path:
    folder = VOICES.get(model, VOICES["watcher"])[4]
    return voice_dir(base) / folder / "installed.json"


def installed(base=None, model="watcher") -> bool:
    """Engine and model both in place, and installed by us (the receipt
    records the hashes checked when they arrived)."""
    if companions.overlay_only(model):
        return False
    try:
        receipt = json.loads(_receipt(base, model).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(receipt, dict):
        return False
    if receipt.get("engine") != ENGINE["sha256"]:
        return False
    files = manifest(model)[1]
    if receipt.get("model") != [row["sha256"] for row in files]:
        return False
    folder = model_path(base, model).parent
    return engine_exe(base).is_file() and all((folder / row["name"]).is_file() for row in files)


def _engine_installed(base=None):
    if not engine_exe(base).is_file():
        return False
    for selected in companions.IDENTITIES:
        try:
            if json.loads(_receipt(base, selected).read_text(encoding="utf-8")).get("engine") == ENGINE["sha256"]:
                return True
        except (OSError, ValueError, AttributeError):
            pass
    return False


class Cancelled(Exception):
    pass


class VoiceDownload:
    """One download of the engine and model, on its own thread. ``state()``
    is safe to read from anywhere: {"stage", "done", "total", "error"}."""

    def __init__(self, base=None, opener=None, model="watcher"):
        self.base = base
        self.model = model if model in companions.IDENTITIES else "watcher"
        self._open = opener or (lambda url: urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}), timeout=30))
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._state = {"stage": "idle", "done": 0, "total": download_bytes(self.model), "error": "", "model": self.model}
        self._thread = None

    def state(self):
        with self._lock:
            return dict(self._state)

    def _set(self, **changes):
        with self._lock:
            self._state.update(changes)

    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self, on_done=None):
        if self.running():
            return False
        self._cancel.clear()
        self._set(stage="starting", done=0, error="")
        self._thread = threading.Thread(target=self._run, args=(on_done,), name="voice-download", daemon=True)
        self._thread.start()
        return True

    def cancel(self):
        self._cancel.set()

    def _fetch(self, url, target, expected_sha, size, counted):
        """Download to target.part, check its hash, then move it into place.
        A file already there with the right hash is kept as it is."""
        if self._cancel.is_set():
            raise Cancelled()
        if Path(target).is_file() and sha256_of(target) == expected_sha:
            self._set(done=counted + size)
            return counted + size
        partial = Path(f"{target}.part")
        partial.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        got = 0
        with self._open(url) as response, open(partial, "wb") as out:
            while True:
                if self._cancel.is_set():
                    raise Cancelled()
                block = response.read(_CHUNK)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                got += len(block)
                self._set(done=counted + min(got, size))
        if digest.hexdigest() != expected_sha:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"{Path(target).name} didn't match its checksum")
        os.replace(partial, target)
        return counted + size

    def _run(self, on_done):
        # A cancelled profile's request can still be returning from HTTP.
        # Serialise writes to the shared engine before a new install starts.
        with _INSTALL_LOCK:
            self._run_serial(on_done)

    def _run_serial(self, on_done):
        folder = voice_dir(self.base)
        try:
            if self._cancel.is_set():
                raise Cancelled()
            folder.mkdir(parents=True, exist_ok=True)
            engine_ready = _engine_installed(self.base)
            _receipt(self.base, self.model).unlink(missing_ok=True)
            counted = 0
            if engine_ready:
                counted = ENGINE["size"]
            else:
                self._set(stage="engine")
                archive = folder / "piper_windows_amd64.zip"
                counted = self._fetch(ENGINE["url"], archive, ENGINE["sha256"], ENGINE["size"], counted)
                self._set(stage="unpacking")
                # Unpacked beside the model, then its piper/ folder moved into place.
                unpack = folder / ".engine-unpack"
                shutil.rmtree(unpack, ignore_errors=True)
                with zipfile.ZipFile(archive) as bundle:
                    for member in bundle.namelist():
                        # Never outside the unpack folder, whatever the archive says.
                        destination = (unpack / member).resolve()
                        if unpack.resolve() not in destination.parents and destination != unpack.resolve():
                            raise RuntimeError("The engine archive has an unsafe path")
                    bundle.extractall(unpack)
                archive.unlink(missing_ok=True)
                engine = engine_exe(self.base).parent
                shutil.rmtree(engine, ignore_errors=True)
                if not (unpack / "piper").is_dir():
                    raise RuntimeError("piper.exe wasn't in the engine archive")
                os.replace(unpack / "piper", engine)
                shutil.rmtree(unpack, ignore_errors=True)
            self._set(stage="model")
            model_folder = model_path(self.base, self.model).parent
            _folder, files, url = manifest(self.model)
            for row in files:
                counted = self._fetch(url + row["name"], model_folder / row["name"], row["sha256"], row["size"], counted)
            if self._cancel.is_set():
                raise Cancelled()
            if not engine_exe(self.base).is_file():
                raise RuntimeError("piper.exe wasn't in the engine archive")
            _receipt(self.base, self.model).write_text(json.dumps({
                "engine": ENGINE["sha256"], "model": [row["sha256"] for row in files],
            }), encoding="utf-8")
            self._set(stage="done", done=download_bytes(self.model))
        except Cancelled:
            self._set(stage="cancelled", error="")
        except Exception as exc:
            logging.warning("Watcher voice download failed: %s", exc)
            self._set(stage="failed", error=str(exc) or exc.__class__.__name__)
        finally:
            leftovers = [folder / "piper_windows_amd64.zip.part"]
            leftovers.extend(model_path(self.base, self.model).parent / (row["name"] + ".part")
                             for row in manifest(self.model)[1])
            for leftover in leftovers:
                leftover.unlink(missing_ok=True)
        if callable(on_done):
            try:
                on_done(self.state())
            except Exception:
                logging.debug("Voice download callback failed", exc_info=True)


def remove(base=None, model="watcher") -> bool:
    """Delete the engine and model (the speech cache with them). Only the
    files the download brought: the model's README stays."""
    if companions.overlay_only(model):
        return False
    folder = voice_dir(base)
    selected = model
    model = model_path(base, selected).parent
    files = manifest(selected)[1]
    ok = True
    shared = () if any(installed(base, other) for other in companions.IDENTITIES if other != selected) else (engine_exe(base).parent, folder / "cache")
    for target in (*shared, _receipt(base, selected), *(model / row["name"] for row in files)):
        try:
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        except OSError as exc:
            logging.warning("Couldn't remove %s: %s", target, exc)
            ok = False
    return ok
