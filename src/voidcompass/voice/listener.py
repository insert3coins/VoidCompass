"""Talking to the Watcher by voice (5.7.1): hold (or tap) your talk key,
speak, and what you said runs the same commands as the TALK box.

Hearing is whisper.cpp's server with a choice of English models, on the
CPU and on this PC only, warmed before you talk and kept while
voice is on. It listens on 127.0.0.1 behind a random path each start (it has
no key of its own, and answers any web page that finds it), so a page in
your browser can't use it. The microphone is open only while you talk or test
it, and nothing it hears is kept.
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request

from voidcompass.voice.local_server import LocalServer
from voidcompass.voice import listen_assets, microphone

# Shorter than this is a slipped key, not a question.
MIN_SECONDS = 0.4
TRANSCRIBE_TIMEOUT_S = 60
# Unused this long, its hearing is stopped (the model holds ~500 MB of RAM);
# the next press loads it again while you speak.
IDLE_S = 600
# Words Whisper wouldn't know, said in Elite: each request also carries where
# you are and what you fly (prompt_provider).
VOCABULARY = ("Elite Dangerous. Commander. Watcher. Sol, Colonia, Shinrarta Dezhra, Jameson Memorial, fleet carrier, "
              "neutron star, frame shift drive, supercruise, exobiology, Powerplay, Galnet.")
# What Whisper writes for sounds that aren't words.
_NOISE = re.compile(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*")
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def clean(text):
    """What was said, without Whisper's [BLANK_AUDIO] and (wind) notes."""
    text = " ".join(_NOISE.sub(" ", str(text or "")).split())
    return text.strip(" -")


def trim_silence(pcm):
    """Drop only quiet ends, with a quarter second of padding around speech."""
    frame = microphone.RATE // 50 * 2
    levels = [microphone.rms(pcm[i:i + frame]) for i in range(0, len(pcm), frame)]
    threshold = min(microphone.SILENCE_RMS, max(levels, default=0) * 0.04)
    voiced = [i for i, level in enumerate(levels) if level > threshold]
    if not voiced:
        return pcm
    pad = 13
    return pcm[max(0, voiced[0] - pad) * frame:min(len(pcm), (voiced[-1] + pad + 1) * frame)]


class ListenServer(LocalServer):
    """whisper-server for the speech model: CPU only, behind a random path."""

    def arguments(self):
        threads = max(1, min(8, (os.cpu_count() or 4) // 2))
        return [str(self.exe), "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.port),
                "--request-path", f"/{self.key}", "--public", str(self.exe.parent.parent / "public"),
                # -mc 0: nothing carried over from what you said before.
                "-t", str(threads), "-l", "en", "-nt", "-mc", "0", "-sns", "-ng"]

    def start(self):
        # An empty folder for its web page: it serves nothing.
        try:
            (self.exe.parent.parent / "public").mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return super().start()

    def _log_tail(self):
        """Why it stopped: its "error:" line, not the help text printed after it."""
        try:
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        errors = [line.strip() for line in lines if line.strip().casefold().startswith("error")]
        return errors[-1][:200] if errors else super()._log_tail()

    def ready(self, timeout=0.5):
        if not self.running():
            return False
        try:
            with _OPENER.open(f"http://127.0.0.1:{self.port}/{self.key}/health", timeout=timeout) as response:
                return json.loads(response.read() or b"{}").get("status") == "ok"
        except (OSError, ValueError, urllib.error.URLError):
            return False

    def transcribe(self, wav, prompt="", timeout=TRANSCRIBE_TIMEOUT_S):
        """What was said in this WAV, or None."""
        boundary = secrets.token_hex(12)
        fields = {"response_format": "json", "temperature": "0.0", "prompt": prompt}
        if getattr(self, "fast", False):
            fields.update(best_of="1", beam_size="1", temperature_inc="0.0")
        body = b"".join(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
            for name, value in fields.items() if value)
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"said.wav\"\r\n"
                 "Content-Type: audio/wav\r\n\r\n").encode("utf-8") + wav + f"\r\n--{boundary}--\r\n".encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/{self.key}/inference", data=body, method="POST",
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with _OPENER.open(request, timeout=timeout) as response:
                return str(json.loads(response.read() or b"{}").get("text") or "")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            logging.debug("Watcher hearing request failed: %s", exc)
            return None


class WatcherListener:
    """Push-to-talk for the Watcher: start() opens the microphone, stop()
    closes it and sends what it heard to ``on_heard`` (on its own thread).
    ``state()`` is safe to read from anywhere."""

    def __init__(self, settings, on_heard=None, on_change=None, prompt_provider=None, base=None,
                 server_factory=ListenServer, recorder_factory=microphone.Recorder):
        self.settings = settings
        self.on_heard = on_heard
        self.on_change = on_change
        self.prompt_provider = prompt_provider
        self.base = base
        self._factory = server_factory
        self._recorder = recorder_factory()
        self._recorder.on_full = lambda: self.stop()
        self.server = None
        self._server_model = None
        self._lock = threading.Lock()
        self._idle_timer = None
        self._used = 0.0
        self._closed = False
        self.failure = ""
        self._stage = "idle"     # idle, opening, listening, test, hearing
        self._wanted = False
        self.heard = ""
        self.note = ""
        self._testing = False
        self._last_test = None
        self.latency_ms = None
        self._warming = False

    def config(self):
        try:
            return self.settings() or {}
        except Exception:
            return {}

    def model(self):
        return "fast" if self.config().get("watcher_listen_model") == "fast" else "accurate"

    def enabled(self):
        return bool(self.config().get("watcher_listen_enabled")) and listen_assets.installed(self.base, self.model())

    def state(self):
        return {"stage": self._stage if self.enabled() else "off", "testing": self._testing, "level": round(self._recorder.level, 3),
                "seconds": round(self._recorder.seconds(), 1) if self._stage in ("listening", "test") else 0,
                "heard": self.heard, "note": self.note, "latency_ms": self.latency_ms,
                "engine": "ready" if self.server is not None and self.server.running() and not self._warming else "warming" if self._warming else "sleeping", "mic": self.config().get("watcher_listen_mic") or ""}

    def _set(self, stage, note=None):
        with self._lock:
            self._stage = stage
            if note is not None:
                self.note = note
            if stage == "idle":
                self._used = time.monotonic()
                self._arm_idle_locked()
        if callable(self.on_change):
            try:
                self.on_change()
            except Exception:
                logging.debug("Hearing change listener failed", exc_info=True)

    def listening(self):
        return self._stage in ("listening", "test")

    def active(self):
        """The microphone open, or opening."""
        return self._stage in ("opening", "listening", "test")

    def live(self):
        """For the orb: listening (and how loud) or working out what was said."""
        if self._testing or self._stage not in ("listening", "hearing"):
            return None
        return {"stage": self._stage, "level": round(self._recorder.level, 3)}

    # -- the server ---------------------------------------------------------------
    def _server(self):
        """The server, started if it isn't, once it answers; or None."""
        with self._lock:
            if self._closed:
                return None
            server = self.server
            if server is not None and self._server_model != self.model():
                server.stop(wait=False)
                server = self.server = None
            if server is None or not server.running():
                server = self._factory(listen_assets.engine_exe(self.base), listen_assets.model_path(self.base, self.model()),
                                       log_path=listen_assets.stt_dir(self.base) / "server.log")
                server.fast = self.model() == "fast"
                self.server = server
                self._server_model = self.model()
                started = server.start()
            else:
                started = True
        if started and server.wait_ready(90):
            with self._lock:
                if self._closed or self.server is not server:
                    return None
                self._used = time.monotonic()
                self.failure = ""
                self._arm_idle_locked()
                return server
        self.failure = server.error or "no answer"
        logging.warning("The Watcher's hearing wouldn't start: %s", self.failure)
        server.stop(wait=False)
        with self._lock:
            if self.server is server:
                self.server = None
                self._cancel_idle_locked()
        return None

    def warm(self):
        """Load the speech model now (in the background), so it's ready when you stop speaking."""
        if not self.enabled():
            return
        with self._lock:
            if self._closed or self._warming:
                return
            self._warming = True
        def run():
            try:
                self._server()
            finally:
                self._warming = False
        threading.Thread(target=run, name="watcher-hearing-warm", daemon=True).start()

    def _cancel_idle_locked(self):
        timer, self._idle_timer = self._idle_timer, None
        if timer is not None:
            timer.cancel()

    def _arm_idle_locked(self, delay=IDLE_S):
        self._cancel_idle_locked()
        if self._closed or self.server is None:
            return
        timer = threading.Timer(max(0.01, delay), lambda: self._idle_check(timer))
        timer.daemon = True
        self._idle_timer = timer
        timer.start()

    def _idle_check(self, timer=None):
        with self._lock:
            if timer is not None and timer is not self._idle_timer:
                return
            self._cancel_idle_locked()
            if self._closed or self.server is None:
                return
            remaining = IDLE_S - (time.monotonic() - self._used)
            if self._stage != "idle" or remaining > 0:
                self._arm_idle_locked(IDLE_S if self._stage != "idle" else remaining)
                return
            server, self.server = self.server, None
        if server is not None:
            server.stop(wait=False)

    # -- talking ------------------------------------------------------------------
    def start(self, test=False):
        """Open the microphone. False, with a note, if it couldn't."""
        if not self.enabled():
            return False
        with self._lock:
            if self._closed or self._stage in ("opening", "listening", "test", "hearing"):
                return False
            self._wanted = True
            self._stage = "opening"
            self._cancel_idle_locked()
        device = microphone.device_index(self.config().get("watcher_listen_mic"))
        if not self._recorder.start(device):
            self._set("idle", self._recorder.error or "The microphone wouldn't open.")
            return False
        self._testing = test
        self.heard = ""
        self._set("test" if test else "listening", "")
        self.warm()
        if not self._wanted:
            # Let go while it was opening.
            self.stop()
        return True

    def stop(self):
        """Close the microphone and work out what was said, in the background."""
        released = time.monotonic()
        self._wanted = False
        if not self.listening():
            return False
        test = self._testing
        pcm = self._recorder.stop()
        loudest = self._recorder.loudest
        if len(pcm) / (microphone.RATE * 2) < MIN_SECONDS:
            self._set("idle", "Too short: hold the key while you speak.")
            return False
        if loudest < microphone.SILENCE_RMS:
            self._set("idle", "It heard nothing: is the right microphone chosen, and unmuted?")
            return False
        self._set("hearing", "")
        threading.Thread(target=self._hear, args=(pcm, test, released), name="watcher-hearing", daemon=True).start()
        return True

    def _hear(self, pcm, test, started=None):
        started = started if started is not None else time.monotonic()
        if not self.enabled():
            # Switched off while you spoke.
            self._set("idle", "")
            return
        model = self.model()
        wav = microphone.to_wav(pcm if test else trim_silence(pcm))
        server = self._server()
        if server is None:
            why = f" ({self.failure})" if self.failure else ""
            self._set("idle", f"Its hearing wouldn't start{why}. Try again, or download it again in Settings, under Voice.")
            return
        prompt = VOCABULARY
        if callable(self.prompt_provider):
            try:
                prompt += " " + " ".join(str(word) for word in self.prompt_provider() or () if word)
            except Exception:
                pass
        text = server.transcribe(wav, prompt[:600])
        if self._closed or not self.enabled() or self.model() != model:
            return
        said = clean(text) if text is not None else ""
        self.heard = said
        self.latency_ms = round((time.monotonic() - started) * 1000)
        if test:
            self._last_test = wav
            self._set("idle", f"It heard: “{said}”" if said else "It heard sound, but no words it knew.")
            return
        if not said:
            self._set("idle", "It didn't catch that. Try again, a little closer to the microphone.")
            return
        self._set("idle", "")
        if callable(self.on_heard):
            try:
                self.on_heard(said)
            except Exception:
                logging.exception("What you said to the Watcher couldn't be passed on")

    def last_test(self):
        """The last mic test's sound (WAV bytes), to hear back, or None."""
        return self._last_test

    def close(self):
        """App shutdown: the microphone closed, the server told to stop."""
        with self._lock:
            self._closed = True
            self._wanted = False
            self._cancel_idle_locked()
            server, self.server = self.server, None
        if self.listening():
            self._recorder.stop()
        if server is not None:
            server.stop(wait=False)

    def stop_server(self):
        with self._lock:
            self._cancel_idle_locked()
            server, self.server = self.server, None
        if server is not None:
            server.stop()
