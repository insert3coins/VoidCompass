"""Optional local neural voice callouts powered by Piper.

Voice models and the Piper runtime are downloaded on demand into ``data/tts``.
Downloads are restricted to the curated, SHA-256-pinned catalogue below.
Synthesis and playback always happen on worker threads so journal processing and
the Tk event loop are never blocked.
"""

import atexit
import hashlib
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import wave
from array import array
from pathlib import Path

import requests

from trade.marketdb import DATA_DIR


TTS_DIR = DATA_DIR / "tts"
CACHE_DIR = TTS_DIR / "cache"
DEFAULT_VOICE = "en_GB-alba-medium"
MAX_TEXT = 400
CACHE_KEEP = 300

_PIPER_RELEASE = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2"
_VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en"

VOICES = {
    "en_GB-cori-high": {
        "label": "Cori - British female", "hf": "en_GB/cori/high", "mb": 109,
        "onnx_sha": "470b4dd634c98f8a4850d7626ffc3dfc90774628eeef6605a6dd8f88f30a5903",
        "config_sha": "9e7fb5b5671612c22f3c81cbe46c1ae87b031a4632bcb509e499dad6f1e2adec",
    },
    "en_GB-alba-medium": {
        "label": "Alba - Scottish female", "hf": "en_GB/alba/medium", "mb": 60,
        "onnx_sha": "401369c4a81d09fdd86c32c5c864440811dbdcc66466cde2d64f7133a66ad03b",
        "config_sha": "aa965a2f02ecced632c2694e1fc72bbff6d65f265fab567ca945918c73dd89f4",
    },
    "en_GB-northern_english_male-medium": {
        "label": "Northern English male", "hf": "en_GB/northern_english_male/medium", "mb": 60,
        "onnx_sha": "57a219ae8e638873db7d18893304be5069c42868f392bb95c3ff17f0690d0689",
        "config_sha": "69557ed3d974463453e9b0c09dd99a7ed0e52b8b87b64b357dbeeb2540a97d47",
    },
    "en_US-lessac-medium": {
        "label": "Lessac - American female", "hf": "en_US/lessac/medium", "mb": 60,
        "onnx_sha": "5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f",
        "config_sha": "efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0",
    },
    "en_US-ryan-high": {
        "label": "Ryan - American male", "hf": "en_US/ryan/high", "mb": 115,
        "onnx_sha": "b3990d7606e183ec8dbfba70a4607074f162de1a0c412e0180d1ff60bb154eca",
        "config_sha": "c6d3b98f08315cb4bebf0d49d50fc4ff491b503c64b940cd3d5ca28543b48011",
    },
    "en_US-amy-medium": {
        "label": "Amy - American female", "hf": "en_US/amy/medium", "mb": 60,
        "onnx_sha": "b3a6e47b57b8c7fbe6a0ce2518161a50f59a9cdd8a50835c02cb02bdd6206c18",
        "config_sha": "95a23eb4d42909d38df73bb9ac7f45f597dbfcde2d1bf9526fdeaf5466977d77",
    },
}


class VoiceError(Exception):
    pass


def canonical_voice(name):
    return next((known for known in VOICES if name == known), None)


def selected_voice(config):
    return canonical_voice(config.get("voice_name")) or DEFAULT_VOICE


def model_path(voice):
    return TTS_DIR / f"{voice}.onnx"


def model_config_path(voice):
    return TTS_DIR / f"{voice}.onnx.json"


def binary_path():
    return TTS_DIR / "piper" / ("piper.exe" if sys.platform == "win32" else "piper")


def _binary_artifact():
    if sys.platform == "win32":
        return (
            f"{_PIPER_RELEASE}/piper_windows_amd64.zip", TTS_DIR / "piper.zip",
            "f3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea",
        )
    return (
        f"{_PIPER_RELEASE}/piper_linux_x86_64.tar.gz", TTS_DIR / "piper.tar.gz",
        "a50cb45f355b7af1f6d758c1b360717877ba0a398cc8cbe6d2a7a3a26e225992",
    )


def _voice_artifacts(voice):
    item = VOICES[voice]
    return [
        (f"{_VOICE_BASE}/{item['hf']}/{voice}.onnx", model_path(voice), item["onnx_sha"]),
        (f"{_VOICE_BASE}/{item['hf']}/{voice}.onnx.json", model_config_path(voice), item["config_sha"]),
    ]


def voice_installed(voice):
    voice = canonical_voice(voice)
    return bool(voice and model_path(voice).is_file() and model_config_path(voice).is_file())


def ready(voice):
    return binary_path().is_file() and voice_installed(voice)


_download_lock = threading.Lock()
_download = {"running": False, "voice": None, "progress": 0.0, "error": None}


def status(voice=None):
    voice = canonical_voice(voice) or DEFAULT_VOICE
    with _download_lock:
        return {
            "ready": ready(voice),
            "voice": voice,
            "voices": [
                {"name": name, "label": item["label"], "mb": item["mb"], "installed": voice_installed(name)}
                for name, item in VOICES.items()
            ],
            "downloading": _download["running"],
            "download_voice": _download["voice"],
            "progress": round(_download["progress"], 3),
            "error": _download["error"],
            "supported": sys.platform in ("win32", "linux"),
        }


def start_download(voice):
    voice = canonical_voice(voice)
    if voice is None:
        raise VoiceError("Unknown voice pack.")
    if ready(voice):
        return False
    if sys.platform not in ("win32", "linux"):
        raise VoiceError("Neural voice packs are only available on Windows and Linux.")
    with _download_lock:
        if _download["running"]:
            raise VoiceError("Another voice pack is already downloading.")
        _download.update(running=True, voice=voice, progress=0.0, error=None)
    threading.Thread(target=_download_worker, args=(voice,), name="voice-download", daemon=True).start()
    return True


def _fetch(url, destination, expected_sha, base, fraction):
    digest = hashlib.sha256()
    temporary = destination.with_suffix(destination.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(temporary, "wb") as output:
            for chunk in response.iter_content(1 << 20):
                if not chunk:
                    continue
                output.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if total:
                    with _download_lock:
                        _download["progress"] = base + fraction * (done / total)
    if digest.hexdigest() != expected_sha:
        temporary.unlink(missing_ok=True)
        raise VoiceError("Downloaded voice files failed verification. Please try again.")
    temporary.replace(destination)


def _download_worker(voice):
    try:
        TTS_DIR.mkdir(parents=True, exist_ok=True)
        artifacts = []
        if not binary_path().is_file():
            artifacts.append(_binary_artifact())
        artifacts.extend(item for item in _voice_artifacts(voice) if not item[1].is_file())
        weights = [0.84 if dest.suffix == ".onnx" else (0.15 if "piper" in dest.name else 0.01)
                   for _, dest, _ in artifacts]
        total_weight = sum(weights) or 1.0
        base = 0.0
        for (url, destination, checksum), weight in zip(artifacts, weights):
            fraction = weight / total_weight
            _fetch(url, destination, checksum, base, fraction)
            base += fraction
        archive = _binary_artifact()[1]
        if archive.exists():
            shutil.unpack_archive(str(archive), str(TTS_DIR))
            archive.unlink()
        if not ready(voice):
            raise VoiceError("Voice installation is incomplete. Delete data/tts and try again.")
        with _download_lock:
            _download.update(running=False, progress=1.0, error=None)
    except VoiceError as exc:
        with _download_lock:
            _download.update(running=False, error=str(exc))
    except Exception as exc:
        with _download_lock:
            _download.update(running=False, error=f"Download failed ({type(exc).__name__}). Please try again.")


_process = None
_process_voice = None
_process_lock = threading.RLock()


def _ensure_process(voice):
    global _process, _process_voice
    if _process is not None and _process.poll() is None and _process_voice == voice:
        return _process
    if _process is not None and _process.poll() is None:
        _process.kill()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    options = {}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    _process = subprocess.Popen(
        [str(binary_path()), "--model", str(model_path(voice)), "--json-input"],
        cwd=str(binary_path().parent), stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options,
    )
    _process_voice = voice
    return _process


def stop_engine():
    global _process, _process_voice
    with _process_lock:
        if _process is not None and _process.poll() is None:
            _process.kill()
        _process = None
        _process_voice = None


def _evict_cache():
    files = sorted(CACHE_DIR.glob("*.wav"), key=lambda path: path.stat().st_mtime)
    for path in files[:-CACHE_KEEP]:
        try:
            path.unlink()
        except OSError:
            pass


def cache_status():
    files = list(CACHE_DIR.glob("*.wav")) if CACHE_DIR.is_dir() else []
    total_bytes = 0
    for path in files:
        try:
            total_bytes += path.stat().st_size
        except OSError:
            pass
    return {"files": len(files), "bytes": total_bytes, "limit": CACHE_KEEP}


def clear_cache():
    removed = 0
    freed = 0
    if CACHE_DIR.is_dir():
        for path in CACHE_DIR.glob("*.wav"):
            try:
                size = path.stat().st_size
                path.unlink()
                removed += 1
                freed += size
            except OSError:
                pass
    return {"files": removed, "bytes": freed}


def synthesize(text, voice, cancel_event=None, use_cache=True):
    voice = canonical_voice(voice)
    if voice is None:
        raise VoiceError("Unknown voice pack.")
    if not ready(voice):
        raise VoiceError("Install the selected voice pack in Settings first.")
    text = re.sub(r"\s+", " ", str(text or "")).strip()[:MAX_TEXT]
    if not text:
        raise VoiceError("Nothing to say.")
    key = hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output = CACHE_DIR / (f"{key}.wav" if use_cache else f"temporary-{uuid.uuid4().hex}.wav")
    if use_cache and output.is_file() and output.stat().st_size > 44:
        return output
    with _process_lock:
        if use_cache and output.is_file() and output.stat().st_size > 44:
            return output
        process = _ensure_process(voice)
        try:
            line = json.dumps({"text": text, "output_file": str(output)}) + "\n"
            process.stdin.write(line.encode("utf-8"))
            process.stdin.flush()
        except OSError as exc:
            stop_engine()
            raise VoiceError("The voice engine stopped. Trying again usually fixes it.") from exc
        deadline = time.monotonic() + 30
        previous_size = -1
        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                stop_engine()
                output.unlink(missing_ok=True)
                raise VoiceError("Voice playback stopped.")
            if output.is_file():
                size = output.stat().st_size
                if size > 44 and size == previous_size:
                    if use_cache:
                        _evict_cache()
                    return output
                previous_size = size
            time.sleep(0.05)
        stop_engine()
        output.unlink(missing_ok=True)
        raise VoiceError("The voice engine timed out. Trying again usually fixes it.")


def _scaled_wav(source, volume):
    volume = max(0.0, min(1.0, float(volume)))
    if volume >= 0.995:
        return source
    target = source.with_name(f"{source.stem}-v{int(round(volume * 100)):03d}.wav")
    if target.is_file() and target.stat().st_size > 44:
        return target
    with wave.open(str(source), "rb") as reader:
        params = reader.getparams()
        frames = reader.readframes(reader.getnframes())
    if params.sampwidth != 2:
        return source
    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()
    for index, sample in enumerate(samples):
        samples[index] = max(-32768, min(32767, int(sample * volume)))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(target), "wb") as writer:
        writer.setparams(params)
        writer.writeframes(samples.tobytes())
    return target


def _play_wav(path):
    if sys.platform != "win32":
        raise VoiceError("Voice playback is currently available on Windows only.")
    import winsound
    winsound.PlaySound(str(path), winsound.SND_FILENAME)


class VoiceCalloutManager:
    """Serialises callouts and applies commander preferences at speak time."""

    def __init__(self, config):
        self.config = config
        self._queue = queue.Queue(maxsize=8)
        self._stop = threading.Event()
        self._last_spoken = {}
        self.last_error = None
        self._thread = threading.Thread(target=self._run, name="voice-callouts", daemon=True)
        self._thread.start()

    def say(self, text, category="safety", cooldown_s=20, key=None):
        if not self.config.get("voice_callouts_enabled", False):
            return False
        if not self.config.get(f"voice_{category}_enabled", True):
            return False
        voice = selected_voice(self.config)
        if not ready(voice):
            return False
        dedup_key = key or f"{category}:{text}"
        now = time.monotonic()
        if now - self._last_spoken.get(dedup_key, 0.0) < cooldown_s:
            return False
        self._last_spoken[dedup_key] = now
        return self._enqueue(text, voice, self.config.get("voice_volume", 0.8))

    def test(self, voice=None, volume=None, use_cache=None):
        voice = canonical_voice(voice) or selected_voice(self.config)
        return self._enqueue(
            "Voice systems online, Commander.", voice,
            self.config.get("voice_volume", 0.8) if volume is None else volume,
            self.config.get("voice_cache_enabled", True) if use_cache is None else use_cache,
        )

    def _enqueue(self, text, voice, volume, use_cache=None):
        if not ready(voice):
            raise VoiceError("Install the selected voice pack first.")
        if use_cache is None:
            use_cache = self.config.get("voice_cache_enabled", True)
        item = (str(text), voice, max(0.0, min(1.0, float(volume))), bool(use_cache))
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            self._queue.put_nowait(item)
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                text, voice, volume, use_cache = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            source = None
            playback = None
            try:
                source = synthesize(text, voice, self._stop, use_cache=use_cache)
                playback = _scaled_wav(source, volume)
                _play_wav(playback)
                if use_cache:
                    _evict_cache()
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
            finally:
                if not use_cache:
                    for path in {source, playback}:
                        if path is not None:
                            try:
                                path.unlink(missing_ok=True)
                            except OSError:
                                pass
                self._queue.task_done()

    def stop(self):
        self._stop.set()
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass
        stop_engine()


atexit.register(stop_engine)
