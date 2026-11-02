"""What the Watcher hears you with (5.7.1): whisper.cpp's server and its
English speech models, downloaded on first use into models/stt/ like
its voice, and run on this PC only.

Both are pinned (a fixed release and a fixed commit) and checked by SHA-256
when they arrive; a receipt records what was checked.
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
    "name": "whisper.cpp b5454", "size": 8928640,
    "url": "https://github.com/ggml-org/whisper.cpp/releases/download/b5454/whisper-bin-x64.zip",
    "sha256": "6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb",
}
MODEL = {
    "name": "Whisper small (English)", "file": "ggml-small.en.bin", "size": 487614201,
    "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/"
           "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-small.en.bin",
    "sha256": "c6138d6d58ecc8322097e0f987c32f1be8bb0a18532a3f88f734d1bbf9c41e5d",
}
MODELS = {
    "fast": {"name": "Fast · Whisper Base English", "file": "ggml-base.en.bin", "size": 147964211,
             "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/"
                    "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base.en.bin",
             "sha256": "a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002"},
    "accurate": MODEL,
}


def model_spec(key="accurate"):
    return MODELS["fast"] if key == "fast" else MODEL


NOTICE = ("It hears you with OpenAI's Whisper (English; MIT licence) on whisper.cpp (MIT licence), on this PC "
          "only. The microphone is open only while you hold or tap your talk key, and nothing it hears is kept.")
_CHUNK = 1024 * 1024
_USER_AGENT = "VoidCompass hearing download"


def stt_dir(base=None) -> Path:
    return Path(base or application_dir()) / "models" / "stt"


def engine_exe(base=None) -> Path:
    return stt_dir(base) / "engine" / "whisper-server.exe"


def model_path(base=None, model="accurate") -> Path:
    return stt_dir(base) / model_spec(model)["file"]


def _receipt(base=None) -> Path:
    return stt_dir(base) / "installed.json"


def _read_receipt(base=None):
    try:
        data = json.loads(_receipt(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def installed(base=None, model="accurate") -> bool:
    """The server and the model both in place, and installed by us."""
    receipt = _read_receipt(base)
    return (receipt.get("engine") == ENGINE["sha256"] and _model_recorded(receipt, model_spec(model))
            and engine_exe(base).is_file() and model_path(base, model).is_file())


def _model_recorded(receipt, spec):
    models = receipt.get("models", [])
    return receipt.get("model") == spec["sha256"] or (isinstance(models, list) and spec["sha256"] in models)


def download_bytes(base=None, model="accurate"):
    receipt = _read_receipt(base)
    total = 0 if receipt.get("engine") == ENGINE["sha256"] and engine_exe(base).is_file() else ENGINE["size"]
    spec = model_spec(model)
    return total + (0 if _model_recorded(receipt, spec) and model_path(base, model).is_file() else spec["size"])


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


class Cancelled(Exception):
    pass


class ListenDownload:
    """One download of what's missing, on its own thread. ``state()`` is safe
    to read from anywhere: {"stage", "done", "total", "error"}."""

    def __init__(self, base=None, opener=None, model="accurate"):
        self.base = base
        self.model = model if model in MODELS else "accurate"
        self._open = opener or (lambda url: urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}), timeout=60))
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._state = {"stage": "idle", "done": 0, "total": 0, "error": ""}
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
        self._set(stage="starting", done=0, total=download_bytes(self.base, self.model), error="")
        self._thread = threading.Thread(target=self._run, args=(on_done,), name="hearing-download", daemon=True)
        self._thread.start()
        return True

    def cancel(self):
        self._cancel.set()

    def _fetch(self, url, target, expected_sha, size, counted):
        partial = Path(f"{target}.part")
        partial.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        done = counted
        with self._open(url) as response, open(partial, "wb") as handle:
            while True:
                if self._cancel.is_set():
                    raise Cancelled()
                block = response.read(_CHUNK)
                if not block:
                    break
                handle.write(block)
                digest.update(block)
                done += len(block)
                self._set(done=done)
        if digest.hexdigest() != expected_sha:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"{Path(target).name} didn't match its checksum")
        os.replace(partial, target)
        return counted + size

    def _run(self, on_done):
        folder = stt_dir(self.base)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            receipt = _read_receipt(self.base)
            counted = 0
            if not (receipt.get("engine") == ENGINE["sha256"] and engine_exe(self.base).is_file()):
                receipt.pop("engine", None)
                self._set(stage="engine")
                archive = folder / "whisper.zip"
                counted = self._fetch(ENGINE["url"], archive, ENGINE["sha256"], ENGINE["size"], counted)
                self._set(stage="unpacking")
                unpack = folder / ".engine-unpack"
                shutil.rmtree(unpack, ignore_errors=True)
                unpack.mkdir(parents=True)
                with zipfile.ZipFile(archive) as bundle:
                    for member in bundle.namelist():
                        name = member.replace("\\", "/").rsplit("/", 1)[-1]
                        # Only the server and its libraries, never outside the folder.
                        if not name or not (name == "whisper-server.exe" or name.lower().endswith(".dll")):
                            continue
                        with bundle.open(member) as source, open(unpack / name, "wb") as target:
                            shutil.copyfileobj(source, target)
                if not (unpack / "whisper-server.exe").is_file():
                    raise RuntimeError("whisper-server.exe wasn't in the archive")
                archive.unlink(missing_ok=True)
                engine = engine_exe(self.base).parent
                shutil.rmtree(engine, ignore_errors=True)
                os.replace(unpack, engine)
                receipt["engine"] = ENGINE["sha256"]
                _receipt(self.base).write_text(json.dumps(receipt), encoding="utf-8")
            spec = model_spec(self.model)
            if not (_model_recorded(receipt, spec) and model_path(self.base, self.model).is_file()):
                self._set(stage="model")
                self._fetch(spec["url"], model_path(self.base, self.model), spec["sha256"], spec["size"], counted)
                models = set(receipt.get("models", []))
                if receipt.get("model"):
                    models.add(receipt["model"])
                models.add(spec["sha256"])
                receipt["models"] = sorted(models)
                receipt["model"] = spec["sha256"]
                _receipt(self.base).write_text(json.dumps(receipt), encoding="utf-8")
            self._set(stage="done", done=self.state()["total"])
        except Cancelled:
            self._set(stage="cancelled", error="")
        except Exception as exc:
            logging.warning("The Watcher's hearing download failed: %s", exc)
            self._set(stage="failed", error=str(exc) or exc.__class__.__name__)
        finally:
            for leftover in folder.glob("*.part") if folder.exists() else ():
                leftover.unlink(missing_ok=True)
            shutil.rmtree(folder / ".engine-unpack", ignore_errors=True)
        if callable(on_done):
            try:
                on_done(self.state())
            except Exception:
                logging.debug("Hearing download callback failed", exc_info=True)


def remove(base=None) -> bool:
    """Delete the server and the model."""
    ok = True
    for target in (engine_exe(base).parent, _receipt(base), *(model_path(base, key) for key in MODELS), stt_dir(base) / "server.log",
                   stt_dir(base) / "public"):
        try:
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        except OSError as exc:
            logging.warning("Couldn't remove %s: %s", target, exc)
            ok = False
    return ok
