"""The microphone (5.7.1), through Windows' own waveIn API: no extra
library in the build. Records 16 kHz mono 16-bit sound, what Whisper wants,
in tenth-of-a-second buffers, with the loudness of the latest for a meter.

The microphone is open only between start() and stop().
"""
from __future__ import annotations

from array import array
import ctypes
from ctypes import wintypes
import io
import logging
import math
import os
import threading
import time
import wave

RATE = 16000
BUFFER_MS = 100
BUFFERS = 4
MAX_SECONDS = 30
# Quieter than this all the way through is silence: nothing to send.
SILENCE_RMS = 0.006

_WAVE_MAPPER = 0xFFFFFFFF
_CALLBACK_EVENT = 0x00050000
_WHDR_DONE = 0x00000001


class _Format(ctypes.Structure):
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                ("cbSize", wintypes.WORD)]


class _Header(ctypes.Structure):
    pass


_Header._fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD), ("dwBytesRecorded", wintypes.DWORD),
                    ("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                    ("lpNext", ctypes.POINTER(_Header)), ("reserved", ctypes.c_size_t)]


class _Caps(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.UINT),
                ("szPname", wintypes.WCHAR * 32), ("dwFormats", wintypes.DWORD), ("wChannels", wintypes.WORD),
                ("wReserved1", wintypes.WORD)]


def _winmm():
    winmm = ctypes.WinDLL("winmm")
    winmm.waveInGetNumDevs.restype = wintypes.UINT
    winmm.waveInGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(_Caps), wintypes.UINT]
    winmm.waveInOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), wintypes.UINT, ctypes.POINTER(_Format),
                                 ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
    for name in ("waveInPrepareHeader", "waveInAddBuffer", "waveInUnprepareHeader"):
        getattr(winmm, name).argtypes = [ctypes.c_void_p, ctypes.POINTER(_Header), wintypes.UINT]
    for name in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
        getattr(winmm, name).argtypes = [ctypes.c_void_p]
    return winmm


def devices():
    """The microphones Windows offers, by name, in its own order."""
    if os.name != "nt":
        return []
    try:
        winmm = _winmm()
        names = []
        for index in range(int(winmm.waveInGetNumDevs())):
            caps = _Caps()
            if winmm.waveInGetDevCapsW(index, ctypes.byref(caps), ctypes.sizeof(_Caps)) == 0:
                names.append(caps.szPname)
        return names
    except OSError:
        return []


def device_index(name):
    """A microphone's index by name, or Windows' own default (None)."""
    if not name:
        return None
    names = devices()
    return names.index(name) if name in names else None


def rms(chunk):
    """How loud 16-bit samples are, 0 (silence) to 1."""
    samples = array("h")
    samples.frombytes(chunk[:len(chunk) - len(chunk) % 2])
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768.0


def to_wav(pcm, rate=RATE):
    """16-bit mono samples as the bytes of a WAV file."""
    out = io.BytesIO()
    with wave.open(out, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(pcm)
    return out.getvalue()


class Recorder:
    """One recording at a time: start(), then stop() gives the sound back.
    ``level`` is the loudness of the latest tenth of a second (0 to 1)."""

    def __init__(self, max_seconds=MAX_SECONDS):
        self.max_seconds = max_seconds
        self.level = 0.0
        self.loudest = 0.0
        self.error = ""
        self._chunks = []
        self._thread = None
        self._stop = threading.Event()
        self._started = 0.0
        self.on_full = None  # told when it stopped itself at max_seconds

    def recording(self):
        return self._thread is not None and self._thread.is_alive()

    def seconds(self):
        return len(b"".join(self._chunks)) / (RATE * 2)

    def start(self, device=None):
        """Open the microphone (an index from devices(), or None for Windows'
        default). False, with ``error`` set, if it couldn't."""
        if self.recording():
            return True
        self._chunks, self.level, self.loudest, self.error = [], 0.0, 0.0, ""
        self._stop.clear()
        opened = threading.Event()
        self._thread = threading.Thread(target=self._record, args=(device, opened), name="watcher-microphone",
                                        daemon=True)
        self._thread.start()
        opened.wait(2)
        return not self.error and self.recording()

    def stop(self):
        """Close the microphone: the 16-bit sound recorded."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(3)
        self.level = 0.0
        return b"".join(self._chunks)

    def _record(self, device, opened):
        if os.name != "nt":
            self.error = "the microphone works on Windows only"
            opened.set()
            return
        winmm = _winmm()
        kernel = ctypes.WinDLL("kernel32")
        kernel.CreateEventW.restype = ctypes.c_void_p
        kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        event = kernel.CreateEventW(None, False, False, None)
        handle = ctypes.c_void_p()
        fmt = _Format(1, 1, RATE, RATE * 2, 2, 16, 0)
        size = RATE * 2 * BUFFER_MS // 1000
        result = winmm.waveInOpen(ctypes.byref(handle), _WAVE_MAPPER if device is None else int(device),
                                  ctypes.byref(fmt), event, 0, _CALLBACK_EVENT)
        if result != 0:
            self.error = f"the microphone wouldn't open (Windows error {result})"
            kernel.CloseHandle(event)
            opened.set()
            return
        memory = [ctypes.create_string_buffer(size) for _ in range(BUFFERS)]
        headers = [_Header() for _ in range(BUFFERS)]
        try:
            for header, buffer in zip(headers, memory):
                header.lpData, header.dwBufferLength = ctypes.cast(buffer, ctypes.c_void_p), size
                winmm.waveInPrepareHeader(handle, ctypes.byref(header), ctypes.sizeof(_Header))
                winmm.waveInAddBuffer(handle, ctypes.byref(header), ctypes.sizeof(_Header))
            winmm.waveInStart(handle)
            self._started = time.monotonic()
            opened.set()
            while not self._stop.is_set():
                kernel.WaitForSingleObject(event, 200)
                for header, buffer in zip(headers, memory):
                    if header.dwFlags & _WHDR_DONE:
                        self._take(buffer.raw[:header.dwBytesRecorded])
                        header.dwFlags &= ~_WHDR_DONE
                        winmm.waveInAddBuffer(handle, ctypes.byref(header), ctypes.sizeof(_Header))
                if time.monotonic() - self._started >= self.max_seconds:
                    self._stop.set()
                    if callable(self.on_full):
                        threading.Thread(target=self.on_full, daemon=True).start()
            winmm.waveInStop(handle)
            winmm.waveInReset(handle)
            for header, buffer in zip(headers, memory):
                if header.dwFlags & _WHDR_DONE and header.dwBytesRecorded:
                    self._take(buffer.raw[:header.dwBytesRecorded])
        except Exception as exc:
            logging.warning("The microphone stopped: %s", exc)
            self.error = f"the microphone stopped ({exc})"
            opened.set()
        finally:
            for header in headers:
                winmm.waveInUnprepareHeader(handle, ctypes.byref(header), ctypes.sizeof(_Header))
            winmm.waveInClose(handle)
            kernel.CloseHandle(event)

    def _take(self, chunk):
        if not chunk:
            return
        self._chunks.append(chunk)
        self.level = rms(chunk)
        self.loudest = max(self.loudest, self.level)
