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

# Shown before the download, as the model's own README asks.
RIGHTS_NOTICE = (
    "The HAL 9000 voice model (campwill/HAL-9000-Piper-TTS) was trained on the voice of HAL 9000 "
    "from 2001: A Space Odyssey (1968), performed by Douglas Rain. Separate copyright, personality "
    "and publicity rights may apply to that voice and character. It is offered for personal use; "
    "think twice before broadcasting it."
)

_CHUNK = 256 * 1024
_USER_AGENT = "VoidCompass voice download"


def voice_dir(base=None) -> Path:
    return Path(base or application_dir()) / "models"


def engine_exe(base=None) -> Path:
    return voice_dir(base) / "piper" / "piper.exe"


def model_path(base=None) -> Path:
    return voice_dir(base) / "hal9000" / "hal.onnx"


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _receipt(base=None) -> Path:
    return voice_dir(base) / "installed.json"


def installed(base=None) -> bool:
    """Engine and model both in place, and installed by us (the receipt
    records the hashes checked when they arrived)."""
    try:
        receipt = json.loads(_receipt(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if receipt.get("engine") != ENGINE["sha256"]:
        return False
    if receipt.get("model") != [row["sha256"] for row in MODEL_FILES]:
        return False
    folder = model_path(base).parent
    return engine_exe(base).is_file() and all((folder / row["name"]).is_file() for row in MODEL_FILES)


class Cancelled(Exception):
    pass


class VoiceDownload:
    """One download of the engine and model, on its own thread. ``state()``
    is safe to read from anywhere: {"stage", "done", "total", "error"}."""

    def __init__(self, base=None, opener=None):
        self.base = base
        self._open = opener or (lambda url: urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}), timeout=30))
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._state = {"stage": "idle", "done": 0, "total": DOWNLOAD_BYTES, "error": ""}
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
        folder = voice_dir(self.base)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            _receipt(self.base).unlink(missing_ok=True)
            counted = 0
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
            model_folder = model_path(self.base).parent
            for row in MODEL_FILES:
                counted = self._fetch(MODEL_URL + row["name"], model_folder / row["name"], row["sha256"], row["size"], counted)
            if not engine_exe(self.base).is_file():
                raise RuntimeError("piper.exe wasn't in the engine archive")
            _receipt(self.base).write_text(json.dumps({
                "engine": ENGINE["sha256"], "model": [row["sha256"] for row in MODEL_FILES],
            }), encoding="utf-8")
            self._set(stage="done", done=DOWNLOAD_BYTES)
        except Cancelled:
            self._set(stage="cancelled", error="")
        except Exception as exc:
            logging.warning("Watcher voice download failed: %s", exc)
            self._set(stage="failed", error=str(exc) or exc.__class__.__name__)
        finally:
            for leftover in folder.glob("**/*.part") if folder.exists() else ():
                leftover.unlink(missing_ok=True)
        if callable(on_done):
            try:
                on_done(self.state())
            except Exception:
                logging.debug("Voice download callback failed", exc_info=True)


def remove(base=None) -> bool:
    """Delete the engine and model (the speech cache with them). Only the
    files the download brought: the model's README stays."""
    folder = voice_dir(base)
    model = model_path(base).parent
    ok = True
    for target in (engine_exe(base).parent, folder / "cache", folder / "installed.json",
                   *(model / row["name"] for row in MODEL_FILES)):
        try:
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        except OSError as exc:
            logging.warning("Couldn't remove %s: %s", target, exc)
            ok = False
    return ok
