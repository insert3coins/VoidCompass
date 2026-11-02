"""A local speech engine process, bound to a random loopback port and key.

Started below normal priority and attached to a Windows job so it stops
when the app exits, including after a crash. Whisper supplies its protected
HTTP endpoints; this module only manages the process.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time

CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


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


class LocalServer:
    """One protected local engine process for its speech model."""

    def __init__(self, exe, model, log_path=None):
        self.exe = Path(exe).resolve()
        self.model = Path(model).resolve()
        self.log_path = Path(log_path) if log_path else self.exe.parent.parent / "server.log"
        self.port = 0
        self.key = ""
        self.process = None
        self.error = ""
        self._lock = threading.Lock()
        self._job = None

    def arguments(self):
        raise NotImplementedError("The local engine must define its server arguments.")

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
        raise NotImplementedError("The local engine must check its protected health endpoint.")

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

    def _log_tail(self):
        try:
            lines = [line.strip() for line in self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                     if line.strip()]
        except OSError:
            return ""
        return lines[-1][:200] if lines else ""

    def stop(self, wait=True):
        """Stop the engine; app shutdown can let the job object finish it."""
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
