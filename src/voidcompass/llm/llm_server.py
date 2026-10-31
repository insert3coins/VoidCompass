"""The Watcher's mind running: llama.cpp's server, in its own process.

Started below normal priority (the game always wins the CPU), on the graphics
card or the CPU alone, and tied to Void Compass by a Windows job object, so it
goes when the app does, even after a crash. It keeps the model loaded: idle
it costs only memory. With "free memory when idle" the server itself unloads
the model after a quiet spell and loads it again on the next request.
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
IDLE_SLEEP_S = 600
CONTEXT = 4096
# Its prompt cache (5.7.1): a slot each for its thoughts, your talks and its
# notes, so one kind of request doesn't push out another's cached prompt.
# Qwen3.5 can only go back to a saved checkpoint, so they're kept every
# CHECKPOINT tokens (llama.cpp's default, 8192, is longer than any prompt it
# gets). Measured on the CPU (Light): a mix of thoughts and talk in 20 s, not 47.
SLOTS = 3
CHECKPOINT_GPU = 128
CHECKPOINT_CPU = 64
# The old prompts it keeps in RAM besides (llama.cpp's own default is 8 GB).
CACHE_RAM_MB = 256
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _job_object():
    """A job object that kills its processes when Void Compass closes."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
                        ("SchedulingClass", ctypes.c_uint32)]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_uint64 * 6),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(ctypes.c_void_p(job), 9, ctypes.byref(info), ctypes.sizeof(info)):
            kernel32.CloseHandle(ctypes.c_void_p(job))
            return None
        return job
    except Exception:
        return None


class LlmServer:
    """One llama-server process for one model and device."""

    def __init__(self, exe, model, gpu=True, free_idle=False, log_path=None):
        self.exe = Path(exe).resolve()
        self.model = Path(model).resolve()
        self.gpu = bool(gpu)
        self.free_idle = bool(free_idle)
        self.log_path = Path(log_path) if log_path else self.exe.parent.parent / "server.log"
        self.port = 0
        # A key of its own each start: a web page in the browser can't use it.
        self.key = ""
        self.process = None
        self.error = ""
        self._lock = threading.Lock()
        self._job = None

    def matches(self, exe, model, gpu, free_idle):
        return ((Path(exe).resolve(), Path(model).resolve(), bool(gpu), bool(free_idle))
                == (self.exe, self.model, self.gpu, self.free_idle))

    def arguments(self):
        args = [str(self.exe), "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.port),
                "--api-key", self.key,
                "-c", str(CONTEXT * SLOTS), "-np", str(SLOTS), "--jinja", "--reasoning-budget", "0",
                "--chat-template-kwargs", '{"enable_thinking":false}', "--no-webui"]
        args += ["-ngl", "99"] if self.gpu else ["--device", "none", "-ngl", "0",
                                                 "-t", str(max(1, min(8, (os.cpu_count() or 4) // 2)))]
        step = str(CHECKPOINT_GPU if self.gpu else CHECKPOINT_CPU)
        args += ["--checkpoint-min-step", step, "-ub", step, "-b", step, "--cache-ram", str(CACHE_RAM_MB)]
        if self.free_idle:
            args += ["--sleep-idle-seconds", str(IDLE_SLEEP_S)]
        return args

    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self):
        with self._lock:
            if self.running():
                return True
            if not self.exe.is_file() or not self.model.is_file():
                self.error = "not downloaded"
                return False
            self.port = _free_port()
            self.key = secrets.token_hex(16)
            self.error = ""
            try:
                log = open(self.log_path, "w", encoding="utf-8", errors="replace")
            except OSError:
                log = subprocess.DEVNULL
            try:
                self.process = subprocess.Popen(
                    self.arguments(), cwd=str(self.exe.parent), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=(CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0)
            except OSError as exc:
                self.error = str(exc)
                self.process = None
                return False
            finally:
                if log is not subprocess.DEVNULL:
                    log.close()
            if self._job is None:
                self._job = _job_object()
            if self._job:
                try:
                    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    handle = int(self.process._handle)
                    kernel32.AssignProcessToJobObject(ctypes.c_void_p(self._job), ctypes.c_void_p(handle))
                except Exception:
                    pass
            return True

    def ready(self, timeout=0.5):
        """The model loaded and the server answering."""
        if not self.running():
            return False
        try:
            with _OPENER.open(f"http://127.0.0.1:{self.port}/health", timeout=timeout) as response:
                return json.loads(response.read() or b"{}").get("status") == "ok"
        except (OSError, ValueError, urllib.error.URLError):
            return False

    def wait_ready(self, timeout=90.0, cancelled=lambda: False):
        end = time.monotonic() + timeout
        while time.monotonic() < end and not cancelled():
            if not self.running():
                self.error = self.error or self._log_tail() or "the server stopped"
                return False
            if self.ready():
                return True
            time.sleep(0.25)
        return False

    def chat(self, messages, max_tokens=96, temperature=0.8, timeout=60.0, slot=None):
        """One reply from the model (its text), or None. ``slot`` keeps a kind
        of request on its own cached prompt (see SLOTS)."""
        body = json.dumps({
            "messages": messages, "max_tokens": int(max_tokens), "temperature": float(temperature),
            "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": True,
            **({"id_slot": int(slot)} if slot is not None else {}),
        }).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {self.key}"}, method="POST")
        try:
            with _OPENER.open(request, timeout=timeout) as response:
                data = json.loads(response.read() or b"{}")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            logging.debug("Watcher mind request failed: %s", exc)
            return None
        try:
            return str(data["choices"][0]["message"].get("content") or "")
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    def _log_tail(self):
        try:
            lines = [line.strip() for line in self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                     if line.strip()]
        except OSError:
            return ""
        return lines[-1][:200] if lines else ""

    def stop(self, wait=True):
        """Stop it. ``wait`` for it to be gone (and its graphics memory free),
        as before loading another model; at app shutdown there's no need: the
        job object ends it with the app (its wait was most of a slow close)."""
        with self._lock:
            process, self.process = self.process, None
        if process is None:
            return
        try:
            process.terminate()
            if wait:
                process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
