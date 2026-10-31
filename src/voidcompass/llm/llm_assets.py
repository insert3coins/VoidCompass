"""Downloading the Watcher's mind: llama.cpp's server and a Qwen model.

Neither ships with Void Compass. The engine is llama.cpp's own Windows build
(Vulkan, which runs on AMD, NVIDIA and Intel graphics and carries its CPU
backends too); the model is Qwen3.5 (Apache 2.0) as LM Studio's community
GGUF. Both come on the commander's first switch-on, into models/llm beside
the app, pinned to one release and checked against its SHA-256.
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
    "name": "llama.cpp b11669 (Vulkan)",
    "url": "https://github.com/ggml-org/llama.cpp/releases/download/b11669/llama-b11669-bin-win-vulkan-x64.zip",
    "sha256": "2c07574e7bde71321cb785282b20cc821e951132149eeceeea32ddebdbf0598e",
    "size": 32182350,
}
MODELS = {
    "light": {
        "name": "Qwen3.5 2B", "file": "Qwen3.5-2B-Q4_K_M.gguf", "size": 1270808032,
        "url": "https://huggingface.co/lmstudio-community/Qwen3.5-2B-GGUF/resolve/"
               "bb84e11355a036e28f080c7793fa6d22b7c4e344/Qwen3.5-2B-Q4_K_M.gguf",
        "sha256": "0bfe35afc9f05b7fac3fa04925e051ac7939a42a8a17ea11afc99701bea826cc",
    },
    "standard": {
        "name": "Qwen3.5 4B", "file": "Qwen3.5-4B-Q4_K_M.gguf", "size": 2707513696,
        "url": "https://huggingface.co/lmstudio-community/Qwen3.5-4B-GGUF/resolve/"
               "f9f88ac3e234be915e23811a6d28ea287bdb927e/Qwen3.5-4B-Q4_K_M.gguf",
        "sha256": "25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c",
    },
}
DEFAULT_MODEL = "standard"
# Its library search (5.7.1): a small model that reads a card's meaning, not
# just its words, so "Who builds carriers?" finds the Brewer Corporation.
EMBEDDER = {
    "name": "bge-small-en-v1.5", "file": "bge-small-en-v1.5-q8_0.gguf", "size": 36806944,
    "url": "https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/"
           "d32f8c040ea3b516330eeb75b72bcc2d3a780ab7/bge-small-en-v1.5-q8_0.gguf",
    "sha256": "ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514",
}
NOTICE = ("Qwen3.5 is made by Alibaba's Qwen team and released under the Apache 2.0 licence; its library search "
          "uses BAAI's bge-small (MIT licence); llama.cpp is MIT licensed. All of it runs on this PC only: "
          "nothing you say to it leaves your computer.")

_CHUNK = 1024 * 1024
_USER_AGENT = "VoidCompass mind download"


def model_choice(value):
    return value if value in MODELS else DEFAULT_MODEL


def llm_dir(base=None) -> Path:
    return Path(base or application_dir()) / "models" / "llm"


def engine_exe(base=None) -> Path:
    return llm_dir(base) / "engine" / "llama-server.exe"


def model_path(choice=DEFAULT_MODEL, base=None) -> Path:
    return llm_dir(base) / MODELS[model_choice(choice)]["file"]


def embedder_path(base=None) -> Path:
    return llm_dir(base) / EMBEDDER["file"]


def download_bytes(choice=DEFAULT_MODEL, base=None):
    """What a download of this model still has to fetch (and its search model)."""
    total = 0 if installed(choice, base) else MODELS[model_choice(choice)]["size"]
    if not engine_installed(base):
        total += ENGINE["size"]
    if not embedder_installed(base):
        total += EMBEDDER["size"]
    return total


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _receipt(base=None) -> Path:
    return llm_dir(base) / "installed.json"


def _read_receipt(base=None):
    try:
        data = json.loads(_receipt(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def engine_installed(base=None) -> bool:
    return _read_receipt(base).get("engine") == ENGINE["sha256"] and engine_exe(base).is_file()


def installed(choice=DEFAULT_MODEL, base=None) -> bool:
    """The engine and this model both in place, and installed by us (the
    receipt records the hashes checked when they arrived)."""
    row = MODELS[model_choice(choice)]
    return (engine_installed(base) and row["sha256"] in (_read_receipt(base).get("models") or [])
            and model_path(choice, base).is_file())


def embedder_installed(base=None) -> bool:
    """Its library search model in place (and the engine to run it)."""
    return (engine_installed(base) and _read_receipt(base).get("embedder") == EMBEDDER["sha256"]
            and embedder_path(base).is_file())


class Cancelled(Exception):
    pass


class MindDownload:
    """One download of the engine (if missing) and a model, on its own thread.
    ``state()`` is safe to read from anywhere: {"stage", "done", "total", "error", "model"}."""

    def __init__(self, base=None, opener=None):
        self.base = base
        self._open = opener or (lambda url: urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}), timeout=60))
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._state = {"stage": "idle", "done": 0, "total": 0, "error": "", "model": ""}
        self._thread = None

    def state(self):
        with self._lock:
            return dict(self._state)

    def _set(self, **changes):
        with self._lock:
            self._state.update(changes)

    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self, choice=DEFAULT_MODEL, on_done=None):
        if self.running():
            return False
        choice = model_choice(choice)
        self._cancel.clear()
        self._set(stage="starting", done=0, total=download_bytes(choice, self.base), error="", model=choice)
        self._thread = threading.Thread(target=self._run, args=(choice, on_done), name="mind-download", daemon=True)
        self._thread.start()
        return True

    def cancel(self):
        self._cancel.set()

    def _fetch(self, url, target, expected_sha, size, counted):
        """Download to target.part, check its hash, then move it into place.
        A file already there with the right hash is kept as it is."""
        if Path(target).is_file() and Path(target).stat().st_size == size and sha256_of(target) == expected_sha:
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

    def _run(self, choice, on_done):
        folder = llm_dir(self.base)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            receipt = _read_receipt(self.base)
            counted = 0
            if not engine_installed(self.base):
                receipt.pop("engine", None)
                self._set(stage="engine")
                archive = folder / "llama-vulkan.zip"
                counted = self._fetch(ENGINE["url"], archive, ENGINE["sha256"], ENGINE["size"], counted)
                self._set(stage="unpacking")
                unpack = folder / ".engine-unpack"
                shutil.rmtree(unpack, ignore_errors=True)
                with zipfile.ZipFile(archive) as bundle:
                    for member in bundle.namelist():
                        # Never outside the unpack folder, whatever the archive says.
                        destination = (unpack / member).resolve()
                        if unpack.resolve() not in destination.parents and destination != unpack.resolve():
                            raise RuntimeError("The engine archive has an unsafe path")
                    bundle.extractall(unpack)
                if not (unpack / "llama-server.exe").is_file():
                    raise RuntimeError("llama-server.exe wasn't in the engine archive")
                archive.unlink(missing_ok=True)
                engine = engine_exe(self.base).parent
                shutil.rmtree(engine, ignore_errors=True)
                os.replace(unpack, engine)
                receipt["engine"] = ENGINE["sha256"]
                _receipt(self.base).write_text(json.dumps(receipt), encoding="utf-8")
            row = MODELS[choice]
            if not installed(choice, self.base):
                self._set(stage="model")
                counted = self._fetch(row["url"], model_path(choice, self.base), row["sha256"], row["size"], counted)
                receipt["models"] = sorted(set(receipt.get("models") or []) | {row["sha256"]})
                _receipt(self.base).write_text(json.dumps(receipt), encoding="utf-8")
            if not embedder_installed(self.base):
                self._set(stage="search")
                self._fetch(EMBEDDER["url"], embedder_path(self.base), EMBEDDER["sha256"], EMBEDDER["size"], counted)
                receipt["embedder"] = EMBEDDER["sha256"]
                _receipt(self.base).write_text(json.dumps(receipt), encoding="utf-8")
            self._set(stage="done", done=self.state()["total"])
        except Cancelled:
            self._set(stage="cancelled", error="")
        except Exception as exc:
            logging.warning("Watcher mind download failed: %s", exc)
            self._set(stage="failed", error=str(exc) or exc.__class__.__name__)
        finally:
            for leftover in folder.glob("*.part") if folder.exists() else ():
                leftover.unlink(missing_ok=True)
            shutil.rmtree(folder / ".engine-unpack", ignore_errors=True)
        if callable(on_done):
            try:
                on_done(self.state())
            except Exception:
                logging.debug("Mind download callback failed", exc_info=True)


def remove(base=None) -> bool:
    """Delete the engine and every model."""
    folder = llm_dir(base)
    ok = True
    for target in (engine_exe(base).parent, _receipt(base), folder / "server.log", folder / "search.log",
                   embedder_path(base), *(folder / row["file"] for row in MODELS.values())):
        try:
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        except OSError as exc:
            logging.warning("Couldn't remove %s: %s", target, exc)
            ok = False
    return ok
