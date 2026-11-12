"""The Watcher speaking: a warm Piper process and Windows audio playback.

Piper runs as its own low-priority process (--json-input) so the model loads
once and each line takes a fraction of a second. Lines are spoken in order,
with a short pause between them. Hush clears the queue and stops playback.
"""
from __future__ import annotations

from array import array
from collections import deque
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import wave

from voidcompass.voice import voice_assets
from voidcompass.core import companions

SPEEDS = {"slow": 1.15, "standard": 1.0, "fast": 0.88}
LEVELS = ("important", "sometimes", "every")
ENVELOPE_HZ = 20
# Note: an idle engine gets paged out under the game's memory pressure, so a
# silent line every so often keeps the first real one quick.
KEEP_WARM_S = 600.0
SPEECH_PAUSE_S = 0.6
PLAYBACK_TAIL_S = 0.3
_CREATE_NO_WINDOW = 0x08000000
_BELOW_NORMAL_PRIORITY = 0x00004000

_ROMAN = {"I": "one", "II": "two", "III": "three", "IV": "four", "V": "five",
          "VI": "six", "VII": "seven", "VIII": "eight", "IX": "nine", "X": "ten"}
# Capitals it says as letters or as written; any other shouted word (IT, THE
# MOST) is said as a word, or espeak spells it out ("IT" was "I T").
_KEEP_CAPS = frozenset({"DSS", "FSS", "SRV", "HIP", "NPC", "AI", "UV", "CQC", "LY", "OK", "TV"}) | frozenset(_ROMAN)


_ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _two(number):
    if number < 20:
        return _ONES[number]
    tens, ones = divmod(number, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


def year_words(number):
    """A year as it's said (5.7.5): 1998 "nineteen ninety-eight", 2005 "two
    thousand five", 3312 "thirty-three twelve", 3301 "thirty-three oh one".
    Piper read them as counts ("one thousand nine hundred ninety-eight")."""
    if 2000 <= number <= 2009:
        return "two thousand" + (f" {_ONES[number - 2000]}" if number > 2000 else "")
    high, low = divmod(number, 100)
    if not low:
        return f"{_two(high)} hundred"
    return f"{_two(high)} oh {_ONES[low]}" if low < 10 else f"{_two(high)} {_two(low)}"


# A four-digit number that reads as a year: 1100-2099 or Elite's 3000s, on
# its own (no comma, decimal, sign or digits around it) and not a count of
# something ("1500 tonnes", "1200 light years", "2048 credits").
_YEAR = re.compile(
    r"(?<![\d.,#$£€+-])\b(1[1-9]\d\d|20\d\d|3\d\d\d)\b(?!\d|%|[.,]\d)"
    r"(?!\s*(?:tonnes?|tons?|t\b|credits?|cr\b|km\b|kilomet|met(?:re|er)s?\b|m\b|light|ly\b|ls\b|lightyears?|jumps?|"
    r"bod(?:y|ies)|systems?|hours?|minutes?|seconds?|days?|percent|kg|probes?|limpets?|times|ships?|stars?|worlds?|"
    r"planets?|signals?|samples?|units?|thousand|million|billion|metres|feet|rigs?|fragments?|°))", re.I)


_CATALOGUE = re.compile(r"\b[A-Z]{2,}\s+$")


def _year_or_name(match):
    """A star's catalogue number (LHS 3447, HIP 1998) is part of its name: kept."""
    if _CATALOGUE.search(match.string[max(0, match.start() - 12):match.start()]):
        return match.group(0)
    return year_words(int(match.group(1)))


def _like(word, sound):
    """``sound`` in the case ``word`` was written in."""
    return sound[:1].upper() + sound[1:] if word[:1].isupper() else sound


def _said_quietly(match):
    word = match.group(0)
    if word in _KEEP_CAPS or not re.search(r"[AEIOUY]", word):
        return word
    return word.lower()


# Words written for the eye that Piper would read badly. 5.7.1: the sounds
# and abbreviations espeak spelled out letter by letter ("Hm" was "aitch
# em"), each respelling checked against the phonemes it makes.
_SAY_AS = (
    (re.compile(r"⟦|⟧"), ""),
    (re.compile(r"\[\[[^|\]]*\|([^\]]*)\]\]"), r"\1"),
    (re.compile(r"(\d)\s*ly\b", re.I), r"\1 light years"),
    (re.compile(r"(\d)\s*Ls\b"), r"\1 light seconds"),
    (re.compile(r"(\d)\s*T\b"), r"\1 tonnes"),
    (re.compile(r"(\d)\s*°C"), r"\1 degrees"),
    (re.compile(r"(\d)\s*g\b"), r"\1 gravities"),
    (re.compile(r"(\d)\s*Cr\b"), r"\1 credits"),
    (re.compile(r"(\d)\s*km\b"), r"\1 kilometres"),
    (re.compile(r"(\d)\s*AU\b"), r"\1 astronomical units"),
    # 5.7.7: names the crew's orders say aloud, checked with piper --debug:
    # "A*" was "A asterisk", and Concha was "con-CHAH".
    (re.compile(r"\b(Sagittarius|Sag) A\*"), r"\1 A-Star"),
    (re.compile(r"\bConcha\b"), "Conka"),
    (re.compile(r"\bCMDR\b"), "Commander"),
    (re.compile(r"\bFSD\b"), "frame shift drive"),
    (re.compile(r"\bSRV\b"), "S R V"),
    (re.compile(r"\b(?:Mk|Mark)\.?\s+(VIII|VII|VI|IV|IX|III|II|I|V|X)\b"), lambda match: f"Mark {_ROMAN[match.group(1)]}"),
    (re.compile(r"\bElite\s+(V|IV|III|II|I)\b"), lambda match: f"Elite {_ROMAN[match.group(1)]}"),
    (re.compile(r"\b(SCO|EDSM|SAA)\b"), lambda match: " ".join(match.group(1))),
    # Its sounds: agreement, a thoughtful hum, a grumble, a scoff, a hush.
    (re.compile(r"\b[Mm]+-?[Hh]+[Mm]+\b"), lambda match: _like(match.group(0), "uh-huh")),
    (re.compile(r"\b[Hh]mph\b"), lambda match: _like(match.group(0), "humph")),
    (re.compile(r"\b[Hh][Rr]+[Mm]+\b"), lambda match: _like(match.group(0), "hmm")),
    (re.compile(r"\b[Hh]+[Mm]+\b"), lambda match: _like(match.group(0), "hmmm")),
    (re.compile(r"\b[Mm]{2,}\b"), lambda match: _like(match.group(0), "hmm")),
    (re.compile(r"\b[Ss][Hh]+\b"), lambda match: _like(match.group(0), "shush")),
    (re.compile(r"\b[Pp][Ff]+[Tt]*\b"), lambda match: _like(match.group(0), "puh")),
    # Years said as years (5.7.5), after the units above have become words.
    (_YEAR, lambda match: _year_or_name(match)),
    # A shouted word, not a catalogue's letters (HIP 10322, JB-W d2-16).
    (re.compile(r"\b[A-Z]{2,}\b(?![-\d])(?!\s+\d)"), _said_quietly),
    (re.compile(r"\s*[·—–]\s*"), ", "),
    (re.compile(r"\s+"), " "),
)


# 5.7.8: the species' Latin, said right. ED-Outrider's respellings
# (data/pronounce.json, "fon-TIK-yoo-loo-uh"), lower-cased: our Piper reads
# capitals letter by letter and has no phoneme input, so "fon-tik-yoo-loo-uh".
_RESPELL = None


def _respellings():
    global _RESPELL
    if _RESPELL is None:
        words = {}
        try:
            from voidcompass.core.paths import resource_path
            with open(resource_path("data", "pronounce.json"), encoding="utf-8") as handle:
                for word, say in (json.load(handle).get("words") or {}).items():
                    if isinstance(word, str) and isinstance(say, str) and re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*", say.strip()):
                        words[word.casefold()] = say.strip().lower()
        except (OSError, ValueError):
            words = {}
        pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b", re.I) if words else None
        _RESPELL = (pattern, words)
    return _RESPELL


def respelled(text):
    pattern, words = _respellings()
    return pattern.sub(lambda match: words[match.group(1).casefold()], text) if pattern else text


def speakable(text):
    """The words as they should be heard."""
    said = respelled(str(text or ""))
    for pattern, replacement in _SAY_AS:
        said = pattern.sub(replacement, said)
    return said.strip()


def volume_gain(percent):
    try:
        value = float(percent)
    except (TypeError, ValueError):
        value = 80.0
    return max(0.0, min(100.0, value)) / 100.0


def envelope(samples, rate, hz=ENVELOPE_HZ):
    """Loudness 0..1, ``hz`` times a second, for the eye to follow."""
    step = max(1, int(rate // hz))
    levels = []
    for start in range(0, len(samples), step):
        chunk = samples[start:start + step]
        if not chunk:
            break
        levels.append(math.sqrt(sum(value * value for value in chunk) / len(chunk)))
    peak = max(levels, default=0.0) or 1.0
    return [round(level / peak, 2) for level in levels]


def stretch(samples, factor, rate):
    """Slower (``factor`` over 1) or quicker, at the same pitch: windowed
    overlap-add (5.6.1, the voice follows its mood). Small changes only."""
    if abs(factor - 1.0) < .01 or len(samples) < 4096:
        return samples
    frame = max(256, int(rate * .04)) // 2 * 2
    hop_out = frame // 2
    hop_in = hop_out / factor
    window = [.5 - .5 * math.cos(2 * math.pi * index / frame) for index in range(frame)]
    length = int(len(samples) * factor) + frame
    out, weight = [0.0] * length, [0.0] * length
    read, write = 0.0, 0
    while int(read) + frame < len(samples) and write + frame < length:
        start = int(read)
        for index in range(frame):
            value = window[index]
            out[write + index] += samples[start + index] * value
            weight[write + index] += value
        read += hop_in
        write += hop_out
    return array("h", (max(-32768, min(32767, int(out[index] / weight[index]))) if weight[index] > 1e-3 else 0
                       for index in range(write)))


def slip(samples, rate):
    """A rare moment its voice slips (5.6.1): a short gap partway through, and
    a second, lower voice faintly under it."""
    if len(samples) < rate // 2:
        return samples
    under = [samples[int(index * .82)] for index in range(len(samples))]
    mixed = array("h", (max(-32768, min(32767, int(value + under[index] * .16))) for index, value in enumerate(samples)))
    at = int(len(mixed) * .45)
    return mixed[:at] + array("h", [0] * int(rate * .3)) + mixed[at:]


class WatcherSpeaker:
    """Speaks one line at a time. ``settings()`` returns the config (volume,
    speed); ``on_change()`` is told when speech starts or stops."""

    def __init__(self, base=None, settings=None, on_change=None, player=None):
        self.base = base
        self._settings = settings or (lambda: {})
        self._on_change = on_change
        self._play = player or _windows_player()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = deque()
        self._states = {}
        self._serial = 0
        self._live = None
        self._proc = None
        self._proc_speed = None
        self._proc_model = None
        self._closed = False
        self._worker = None
        self._last_used = time.time()

    # -- engine --------------------------------------------------------------
    def _voice_settings(self, voice=None):
        """The settings for this line's voice: the active companion's, or a
        crewmate's when it speaks off watch (5.7.4)."""
        settings = self._settings()
        if not voice or voice not in companions.IDENTITIES or voice == companions.identity(settings):
            return settings
        return companions.settings(getattr(settings, "source", settings), voice)

    def _speed(self, voice=None):
        return SPEEDS.get(str(self._voice_settings(voice).get("watcher_voice_speed") or "standard"), 1.0)

    def _ensure_engine(self, voice=None):
        model = companions.identity(self._voice_settings(voice))
        ready = voice_assets.installed(self.base, model=model) if model != "watcher" else voice_assets.installed(self.base)
        if self._closed or not ready:
            return None
        speed = self._speed(voice)
        model_file = voice_assets.model_path(self.base, model)
        model_signature = (model, str(model_file), tuple(row["sha256"] for row in voice_assets.manifest(model)[1]))
        proc = self._proc
        if proc is not None and proc.poll() is None and self._proc_speed == speed and self._proc_model == model_signature:
            return proc
        self._stop_engine()
        flags = _CREATE_NO_WINDOW | _BELOW_NORMAL_PRIORITY if os.name == "nt" else 0
        try:
            self._proc = subprocess.Popen(
                [str(voice_assets.engine_exe(self.base)), "-m", str(model_file),
                 "--json-input", "-q", "--length_scale", f"{speed:.2f}"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1, creationflags=flags,
                cwd=str(voice_assets.engine_exe(self.base).parent))
            self._proc_speed = speed
            self._proc_model = model_signature
        except OSError as exc:
            logging.warning("Couldn't start the Watcher's voice: %s", exc)
            self._proc = None
        return self._proc

    def _stop_engine(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.kill()
        except OSError:
            pass

    def warm(self):
        """Load the model now, so the first thought isn't late."""
        self._start_worker()
        with self._lock:
            if not self._pending and self._live is None and not self._closed:
                self._pending.append({"warm": True})
        self._wake.set()

    # -- speaking ------------------------------------------------------------
    def say(self, text, key=None, feel=None):
        """Queue this after earlier lines. ``feel`` is
        how (5.6.1): {pace, gain, slip}."""
        words = speakable(text)
        if not words or self._closed:
            return False
        self._start_worker()
        with self._lock:
            if self._closed:
                return False
            self._pending.append({"text": words, "key": key, "serial": self._serial, "feel": dict(feel or {})})
            self._remember_state(key, "queued")
        self._wake.set()
        return True

    def stop(self):
        """Hush: whatever is playing stops, and nothing waiting is said."""
        with self._lock:
            self._pending.clear()
            for key, state in self._states.items():
                if state in {"queued", "preparing", "playing"}:
                    self._states[key] = "cancelled"
            self._serial += 1
            was = self._live
            self._live = None
            self._play(None)
        self._wake.set()
        if was:
            self._changed()

    def close(self):
        """App shutdown: silence at once, and the engine killed."""
        self._closed = True
        self.stop()
        self._stop_engine()
        self._wake.set()

    def busy(self):
        """5.7.7: something queued, being prepared or playing. The crew wait
        for this in conversation, so nobody talks over anyone."""
        with self._lock:
            if self._pending or self._live:
                return True
            return any(state == "preparing" for state in self._states.values())

    def live(self):
        """What it's saying now, for the orb and the typing: the key, how
        far in (s), how long, and the loudness right now."""
        with self._lock:
            live = dict(self._live) if self._live else None
        if not live:
            return None
        elapsed = time.time() - live["start"]
        if elapsed > live["duration"] + PLAYBACK_TAIL_S:
            with self._lock:
                if self._live and self._live["start"] == live["start"]:
                    self._remember_state(self._live.get("key"), "finished")
                    self._live = None
            self._changed()
            return None
        envelope_ = live.get("envelope") or []
        index = int(elapsed * ENVELOPE_HZ)
        level = envelope_[index] if 0 <= index < len(envelope_) else 0.0
        return {"key": live.get("key"), "elapsed": round(max(0.0, elapsed), 3),
                "duration": round(live["duration"], 3), "level": level}

    def _remember_state(self, key, state):
        self._states[key] = state
        if len(self._states) > 64:
            old = next((key for key, value in self._states.items() if value in {"finished", "failed", "cancelled"}), None)
            if old in self._states and self._states[old] in {"finished", "failed", "cancelled"}:
                self._states.pop(old)

    def status(self, key):
        """Caption timing includes queued synthesis, playback and failure."""
        with self._lock:
            return self._states.get(key, "cancelled" if self._closed else "unknown")

    def _job_state(self, job, state):
        with self._lock:
            if job.get("serial") == self._serial:
                self._remember_state(job.get("key"), state)

    def _changed(self):
        if callable(self._on_change):
            try:
                self._on_change()
            except Exception:
                logging.debug("Voice change listener failed", exc_info=True)

    def _start_worker(self):
        with self._lock:
            if not self._closed and (self._worker is None or not self._worker.is_alive()):
                self._worker = threading.Thread(target=self._run, name="watcher-voice", daemon=True)
                self._worker.start()

    def _wait_playback(self, seconds, serial):
        deadline = time.monotonic() + seconds
        while not self._closed:
            with self._lock:
                if serial != self._serial:
                    return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._wake.wait(remaining)
            self._wake.clear()

    def _run(self):
        turn = 0
        while not self._closed:
            with self._lock:
                job = self._pending.popleft() if self._pending else None
            if not job:
                self._wake.wait(1.0)
                self._wake.clear()
                with self._lock:
                    job = self._pending.popleft() if self._pending else None
            if not job and self._proc is not None and time.time() - self._last_used > KEEP_WARM_S:
                job = {"warm": True}
            if not job or self._closed:
                continue
            if not job.get("warm"):
                self._job_state(job, "preparing")
            voice = (job.get("feel") or {}).get("voice")
            proc = self._ensure_engine(voice) if voice else self._ensure_engine()
            if proc is None:
                if not job.get("warm"):
                    self._job_state(job, "failed")
                continue
            self._last_used = time.time()
            if job.get("warm"):
                job = {"text": ".", "key": None, "serial": None, "silent": True}
            turn += 1
            raw = voice_assets.voice_dir(self.base) / "cache" / companions.identity(self._voice_settings(voice)) / f"speech-{turn % 3}.wav"
            try:
                raw.parent.mkdir(parents=True, exist_ok=True)
                proc.stdin.write(json.dumps({"text": job["text"], "output_file": str(raw)}) + "\n")
                proc.stdin.flush()
                if not proc.stdout.readline():
                    raise OSError("the voice engine stopped")
            except (OSError, ValueError) as exc:
                logging.warning("The Watcher's voice failed: %s", exc)
                self._job_state(job, "failed")
                self._stop_engine()
                continue
            if job.get("silent") or self._closed:
                continue
            with self._lock:
                stale = job["serial"] != self._serial
            if stale:
                continue  # hushed while this was made
            try:
                played, duration, levels = self._prepare(raw, turn, job.get("feel"))
            except (OSError, EOFError, wave.Error) as exc:
                logging.warning("The Watcher's voice couldn't play: %s", exc)
                self._job_state(job, "failed")
                continue
            with self._lock:
                if job["serial"] != self._serial:
                    continue
                start = time.time()
                self._live = {"key": job.get("key"), "start": start, "duration": duration, "envelope": levels}
                self._remember_state(job.get("key"), "playing")
                self._play(str(played))
            self._changed()
            self._wait_playback(duration + PLAYBACK_TAIL_S, job["serial"])
            self._ended(start)
            self._wait_playback(SPEECH_PAUSE_S, job["serial"])

    def _ended(self, start):
        with self._lock:
            if not self._live or self._live["start"] != start:
                return
            self._remember_state(self._live.get("key"), "finished")
            self._live = None
        self._changed()

    def _prepare(self, raw, turn, feel=None):
        """The WAV at the chosen volume (and the thought's feel: its pace, a
        whisper, a slip), its length and its loudness."""
        with wave.open(str(raw), "rb") as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
        samples = array("h")
        samples.frombytes(frames)
        rate = params.framerate or 22050
        feel = feel or {}
        if params.nchannels == 1 and params.sampwidth == 2:
            try:
                pace = float(feel.get("pace") or 1.0)
            except (TypeError, ValueError):
                pace = 1.0
            samples = stretch(samples, max(.85, min(1.2, pace)), rate)
            if feel.get("slip"):
                samples = slip(samples, rate)
        gain = volume_gain(self._voice_settings(feel.get("voice")).get("watcher_voice_volume", 80))
        try:
            gain *= max(.3, min(1.0, float(feel.get("gain") or 1.0)))
        except (TypeError, ValueError):
            pass
        if gain < .999:
            samples = array("h", (int(value * gain) for value in samples))
        played = Path(raw).with_name(f"play-{turn % 2}.wav")
        with wave.open(str(played), "wb") as out:
            out.setparams(params)
            out.writeframes(samples.tobytes())
        duration = len(samples) / float(rate)
        return played, duration, envelope(samples, params.framerate or 22050)


def _windows_player():
    """Play a WAV without waiting (None stops it). Silent off Windows."""
    try:
        import winsound
    except ImportError:
        return lambda path: None

    def play(path):
        try:
            if path is None:
                winsound.PlaySound(None, 0)
            else:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except RuntimeError as exc:
            logging.debug("Watcher voice playback failed: %s", exc)
    return play
