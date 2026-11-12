"""Short alert sounds (5.7.8), synthesised from data/alert_sounds.json, so
there are no audio files to ship: ED-Outrider's recipes (a fanfare for a
system nobody has reported, an upbeat pair for one known but unscanned, a
thud for one you've done), rendered to WAV here and played through Windows.

Each tone in a recipe: freq (Hz), start and dur (s), type (sine, triangle,
square, sawtooth), vol, attack (s to the peak, then an exponential fade),
glideTo (Hz). lowpass (Hz) filters the tones not marked dry.
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import struct
import tempfile
import threading
import wave

from voidcompass.core.paths import resource_path

logger = logging.getLogger(__name__)
RATE = 22050
TARGET_SOUNDS = {"unreported": "fanfare", "known": "upbeat", "done": "thud"}

_lock = threading.Lock()
_recipes = None
_files = {}


def recipes():
    global _recipes
    if _recipes is None:
        try:
            with open(resource_path("data", "alert_sounds.json"), encoding="utf-8") as handle:
                _recipes = json.load(handle)
        except (OSError, ValueError):
            _recipes = {}
    return _recipes


def _wave(kind, phase):
    x = phase % 1.0
    if kind == "sine":
        return math.sin(2 * math.pi * x)
    if kind == "square":
        return 1.0 if x < 0.5 else -1.0
    if kind == "sawtooth":
        return 2 * ((x + 0.5) % 1.0) - 1
    return 1 - 4 * abs((x + 0.25) % 1.0 - 0.5)


def _tone_into(buffer, tone, rate):
    freq, start, dur = float(tone["freq"]), float(tone.get("start", 0)), float(tone["dur"])
    vol, attack = max(float(tone.get("vol", 0.3)), 0.0001), min(float(tone.get("attack", 0.01)), dur)
    kind, glide = tone.get("type", "triangle"), tone.get("glideTo")
    first, count = int(start * rate), int(dur * rate)
    phase, floor = 0.0, 0.0001
    for i in range(count):
        t = i / rate
        if t < attack:
            gain = floor * (vol / floor) ** (t / attack)
        else:
            gain = vol * (floor / vol) ** ((t - attack) / max(dur - attack, 1e-6))
        f = freq * (float(glide) / freq) ** (t / dur) if glide else freq
        buffer[first + i] += gain * _wave(kind, phase)
        phase += f / rate


def render(spec, gain=0.8, rate=RATE):
    """One recipe as 16-bit mono WAV bytes."""
    tones = spec.get("tones") or []
    length = max((float(t.get("start", 0)) + float(t["dur"]) for t in tones), default=0) + 0.05
    size = int(length * rate) + 1
    wet, dry = [0.0] * size, [0.0] * size
    cut = spec.get("lowpass")
    for tone in tones:
        _tone_into(dry if (tone.get("dry") or not cut) else wet, tone, rate)
    if cut:
        a, y = 1 - math.exp(-2 * math.pi * float(cut) / rate), 0.0
        for i, x in enumerate(wet):
            y += a * (x - y)
            dry[i] += y
    frames = struct.pack(f"<{size}h", *(int(max(-1.0, min(1.0, v * gain)) * 32767) for v in dry))
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return out.getvalue()


def sound_file(name, volume=1.0):
    """A sound rendered once (per volume step) into a temporary WAV, or None."""
    doc = recipes()
    spec = (doc.get("sounds") or {}).get(name)
    if not spec:
        return None
    step = round(max(0.0, min(1.0, float(volume))) * 10) / 10
    key = (name, step)
    with _lock:
        path = _files.get(key)
        if path and os.path.exists(path):
            return path
        data = render(spec, gain=float(doc.get("gain", 0.8)) * step)
        handle, path = tempfile.mkstemp(prefix=f"voidcompass-{name}-", suffix=".wav")
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        _files[key] = path
        return path


def play(name, volume=1.0):
    """Play a sound without waiting for it; False when it can't be played."""
    if os.name != "nt":
        return False
    try:
        path = sound_file(name, volume)
        if not path:
            return False
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return True
    except Exception:
        logger.debug("Alert sound %s not played", name, exc_info=True)
        return False
