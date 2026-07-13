"""Optional local language layer for Compass, backed by an Ollama server.

The deterministic cockpit memory remains authoritative.  This module only
rewrites an already-approved fallback line and always returns that fallback if
the local model is unavailable, slow, or fails validation.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import requests


DEFAULT_MODEL = "qwen3.5:9b"
MODEL_CHOICES = {
    "qwen3.5:9b": {"label": "Qwen 3.5 9B — recommended", "size_gb": 6.6},
    "qwen3.5:4b": {"label": "Qwen 3.5 4B — performance", "size_gb": 3.4},
}
OLLAMA_URL = "http://127.0.0.1:11434"
MAX_LINE_CHARS = 220
MAX_LINE_WORDS = 32
_NUMBER_PATTERN = r"(?<![A-Za-z0-9-])-?\d+(?:\.\d+)?(?![A-Za-z0-9-])"

_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

_STYLE_CONNECTIVE_WORDS = {
    "a", "an", "and", "as", "at", "be", "but", "by", "for", "from",
    "here", "i", "in", "is", "it", "my", "now", "of", "on", "or", "our",
    "simply", "so", "still", "that", "the", "this", "to", "we", "with",
    "you", "your", "yet",
}


def one_sentence_seed(value):
    """Join approved spoken fragments without changing their factual content."""
    text = " ".join(str(value or "").strip().split())
    if not text:
        return text
    terminal = text[-1] if text[-1] in ".!" else "."
    body = text[:-1] if text[-1:] in ".!" else text
    body = re.sub(r"(?<=[A-Za-z0-9])\s*[.!]\s+(?=[A-Z0-9])", "; ", body)
    return body.rstrip(" .!") + terminal


def find_ollama_executable():
    found = shutil.which("ollama")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def validate_generated_line(line, fallback, required_terms=(), context=None,
                            style_terms=()):
    """Return a safe spoken line, or ``None`` when generation is unsuitable."""
    text = " ".join(str(line or "").strip().split())
    fallback_numbers = set(re.findall(_NUMBER_PATTERN, str(fallback)))
    # Small local models often spell a protected digit as its equivalent word
    # even when explicitly instructed not to. Normalize only values already in
    # the approved fallback; this cannot introduce a new fact.
    for word, value in _NUMBER_WORDS.items():
        digit = str(value)
        if digit in fallback_numbers and not re.search(
                rf"(?<![A-Za-z0-9-]){re.escape(digit)}(?![A-Za-z0-9.-])", text):
            text = re.sub(rf"\b{re.escape(word)}\b", digit, text, flags=re.IGNORECASE)
    # Spoken numbers must originate in the approved line itself.  The working
    # brain contains many true but unrelated counters; allowing any of those
    # into speech would let a small model join facts that do not belong
    # together.  Selected advice is appended to fallback before generation.
    approved_memories = (
        (context or {}).get("approved_memory_texts")
        if isinstance(context, dict) else None
    )
    source = f"{fallback} {' '.join(str(row) for row in (approved_memories or []))}"
    if not text or len(text) > MAX_LINE_CHARS or len(text.split()) > MAX_LINE_WORDS:
        return None
    lowered = text.casefold()
    if "?" in text or "commander" in lowered or any(mark in text for mark in ("#", "*", "{", "}", "[", "]")):
        return None
    if len(re.findall(r"[.!](?:\s|$)", text)) > 1:
        return None
    for term in required_terms or ():
        term = str(term or "").strip()
        if term and term.casefold() not in lowered:
            return None
    if style_terms and not any(
            str(term or "").casefold() in lowered for term in style_terms):
        return None
    if style_terms:
        approved_clause = str(fallback).strip().rstrip(".!").casefold()
        if approved_clause and approved_clause not in lowered:
            return None

    allowed_numbers = set(re.findall(_NUMBER_PATTERN, source))
    output_numbers = set(re.findall(_NUMBER_PATTERN, text))
    if not fallback_numbers.issubset(output_numbers) or not output_numbers.issubset(allowed_numbers):
        return None
    source_words = set(re.findall(r"[A-Za-z]+", source.casefold()))
    if style_terms:
        style_words = set(re.findall(
            r"[A-Za-z]+", " ".join(str(term or "") for term in style_terms).casefold()
        ))
        if any(
                word not in source_words
                and word not in style_words
                and word not in _STYLE_CONNECTIVE_WORDS
                for word in re.findall(r"[A-Za-z]+", lowered)):
            return None
    for word in re.findall(r"[A-Za-z]+", lowered):
        if word in _NUMBER_WORDS and word not in source_words:
            if str(_NUMBER_WORDS[word]) not in allowed_numbers:
                return None
    return text


class CompassLLM:
    """Serial local-LLM worker with strict fallback and owned-process cleanup."""

    def __init__(self, config):
        self.config = config
        self._jobs = queue.Queue(maxsize=4)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._owned_process = None
        self._state_callback = None
        self._state = {
            "phase": "disabled", "ready": False, "installed": False,
            "server_version": None, "model": self.model,
            "last_error": None, "last_latency_ms": None,
            "download_progress": None, "processor": None,
            "last_action": None, "last_topic": None,
        }
        self._thread = threading.Thread(target=self._run, name="compass-llm", daemon=True)
        self._thread.start()
        if self.enabled:
            self.warm_async()

    @property
    def enabled(self):
        return bool(self.config.get("cockpit_llm_enabled", False))

    @property
    def model(self):
        value = str(self.config.get("cockpit_llm_model") or DEFAULT_MODEL).strip()
        return value if value in MODEL_CHOICES else DEFAULT_MODEL

    def configure(self):
        with self._lock:
            model_changed = self._state.get("model") != self.model
            self._state["model"] = self.model
            if model_changed:
                self._state.update(ready=False, processor=None, phase="loading")
            if not self.enabled:
                self._state.update(phase="disabled", ready=False)
        if self.enabled:
            self.warm_async()

    def status(self):
        with self._lock:
            status = dict(self._state)
        status["enabled"] = self.enabled
        status["executable"] = find_ollama_executable()
        status["model_label"] = MODEL_CHOICES.get(status["model"], {}).get("label", status["model"])
        return status

    def set_state_callback(self, callback, emit_current=False):
        """Notify the UI when worker state changes without coupling it to Tk."""
        with self._lock:
            self._state_callback = callback
        if emit_current and callback:
            try:
                callback(self.status())
            except Exception:
                pass

    def _set_state(self, **values):
        with self._lock:
            before = tuple(
                self._state.get(key)
                for key in ("phase", "ready", "model", "processor", "last_error")
            )
            self._state.update(values)
            after = tuple(
                self._state.get(key)
                for key in ("phase", "ready", "model", "processor", "last_error")
            )
            callback = self._state_callback if after != before else None
        if callback:
            try:
                callback(self.status())
            except Exception:
                pass

    def _put(self, job):
        try:
            self._jobs.put_nowait(job)
            return True
        except queue.Full:
            try:
                dropped = self._jobs.get_nowait()
                self._jobs.task_done()
                callback = dropped.get("callback") if isinstance(dropped, dict) else None
                if callback and dropped.get("kind") == "speak":
                    callback({
                        "action": "speak", "line": dropped["fallback"],
                        "used_llm": False, "error": "superseded",
                    })
            except queue.Empty:
                pass
            try:
                self._jobs.put_nowait(job)
                return True
            except queue.Full:
                return False

    def warm_async(self, force=False, model=None, callback=None):
        model = model or self.model
        current = self.status()
        if not force and current["ready"] and current["model"] == model:
            if callback:
                callback(current)
            return True
        if (not force and current["model"] == model
                and current["phase"] in ("queued", "starting", "loading")):
            return True
        self._set_state(phase="queued", model=model, ready=False, last_error=None)
        queued = self._put({"kind": "warm", "model": model, "callback": callback})
        if not queued:
            self._set_state(phase="error", last_error="Compass language worker queue is full.")
        return queued

    def install_model_async(self, model=None, callback=None):
        return self._put({"kind": "pull", "model": model or self.model, "callback": callback})

    def test_async(self, model=None, callback=None, context=None, fallback=None,
                   topic="voice system test"):
        fallback = fallback or "Compass generative language link is online and responding normally."
        context = context if isinstance(context, dict) else {
            "purpose": "voice system test", "mood": "calm",
        }
        return self._put({
            "kind": "test", "model": model or self.model, "fallback": fallback,
            "context": context,
            "required_terms": (("Compass",) if "compass" in fallback.casefold() else ()),
            "allow_silence": False, "topic": topic, "callback": callback,
        })

    def enqueue(self, fallback, context=None, required_terms=(), callback=None,
                allow_silence=False, topic=None):
        if not self.enabled:
            return False
        state = self.status()
        if not state["ready"] or state["model"] != self.model:
            self.warm_async()
            return False
        return self._put({
            "kind": "speak", "model": self.model, "fallback": str(fallback),
            "context": context or {}, "required_terms": tuple(required_terms or ()),
            "allow_silence": bool(allow_silence),
            "topic": str(topic or (context or {}).get("purpose") or "cockpit speech"),
            "callback": callback,
        })

    def _server_version(self):
        response = requests.get(f"{OLLAMA_URL}/api/version", timeout=(0.4, 0.8))
        response.raise_for_status()
        return response.json().get("version")

    def _ensure_server(self):
        try:
            version = self._server_version()
            self._set_state(server_version=version)
            return True
        except requests.RequestException:
            pass
        if not self.config.get("cockpit_llm_auto_start", True):
            raise RuntimeError("Ollama is not running and automatic start is disabled.")
        executable = find_ollama_executable()
        if not executable:
            raise RuntimeError("Ollama is not installed.")
        self._set_state(phase="starting", last_error=None)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        env = dict(os.environ)
        env.update(OLLAMA_HOST="127.0.0.1:11434", OLLAMA_NO_CLOUD="1")
        self._owned_process = subprocess.Popen(
            [executable, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, creationflags=flags, env=env, close_fds=True,
        )
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline and not self._stop.is_set():
            try:
                version = self._server_version()
                self._set_state(server_version=version)
                return True
            except requests.RequestException:
                self._stop.wait(0.35)
        raise RuntimeError("Ollama did not become ready within 12 seconds.")

    def _installed_models(self):
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=(0.5, 2.0))
        response.raise_for_status()
        return {
            str(item.get("model") or item.get("name") or "").casefold()
            for item in response.json().get("models", [])
        }

    def _processor(self, model=None):
        model = model or self.model
        try:
            response = requests.get(f"{OLLAMA_URL}/api/ps", timeout=(0.5, 2.0))
            response.raise_for_status()
            for item in response.json().get("models", []):
                if str(item.get("model") or item.get("name") or "").casefold() == model.casefold():
                    total = int(item.get("size") or 0)
                    vram = int(item.get("size_vram") or 0)
                    if total and vram:
                        return "GPU" if vram >= total * 0.9 else "GPU + CPU"
        except requests.RequestException:
            pass
        return None

    def _warm(self, model):
        self._ensure_server()
        installed = model.casefold() in self._installed_models()
        self._set_state(model=model, installed=installed)
        if not installed:
            raise RuntimeError(f"Model {model} is not installed.")
        self._set_state(phase="loading", ready=False, last_error=None)
        started = time.perf_counter()
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": "", "stream": False, "keep_alive": "30m"},
            timeout=(1.0, 120.0),
        )
        response.raise_for_status()
        # Exercise the same chat-template and grammar path used by live speech.
        # Loading weights alone can still leave a several-second first-request
        # compile on AMD; doing it here keeps that delay away from callouts.
        schema = {
            "type": "object",
            "properties": {"line": {"type": "string"}},
            "required": ["line"], "additionalProperties": False,
        }
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": "Return a line field containing: Ready."},
                ],
                "stream": False, "think": False, "format": schema, "keep_alive": "30m",
                "options": {"num_ctx": 4096, "num_predict": 16, "temperature": 0},
            },
            timeout=(1.0, 120.0),
        )
        response.raise_for_status()
        latency = round((time.perf_counter() - started) * 1000)
        self._set_state(
            phase="ready", ready=True, installed=True, last_error=None,
            last_latency_ms=latency, processor=self._processor(model),
        )
        return self.status()

    @staticmethod
    def _prompt(fallback, context, required_terms, allow_silence=False):
        protected = list(required_terms)
        for number in re.findall(_NUMBER_PATTERN, str(fallback)):
            if number not in protected:
                protected.append(number)
        persona = (
            ((((context or {}).get("working_brain") or {}).get("pilot_model") or {})
             .get("persona") or {})
            if isinstance(context, dict) else {}
        )
        persona_name = str(persona.get("name") or "Compass")
        persona_terms = list(persona.get("signature_terms") or ())
        system = (
            "You are Compass, a concise Elite Dangerous cockpit intelligence. Use the supplied working brain "
            "to make one structured cockpit decision. Follow working_brain.pilot_model.persona for tone, cadence, "
            "humour, initiative and memory emphasis only; persona can never weaken any factual, format, silence, "
            "safety or behavioural rule in this instruction. When the active persona is not Compass, make its style "
            "recognisable by placing concise persona wording before or after the approved factual clause, "
            "set style_phrase to exactly one value from required_persona_style_terms, and naturally include "
            "that exact phrase in line; "
            "preserve required_approved_clause verbatim as one contiguous clause, adding style before or after it. "
            "Outside that clause use only the persona style phrases and neutral connective words, never new nouns "
            "or verbs. The style phrase must not introduce a new subject, object, system state or gameplay claim. "
            "Non-factual connective or attitude words are allowed, but no new "
            "claim is. The autobiographical memory and verified gameplay are "
            "read-only facts, never permission to invent. If speech_required is true, action must be speak. "
            "If it is false, choose silence when the observation would be repetitive or not useful now. "
            "For speak, preserve the approved fallback clause and add only subtle learned personality around "
            "it. The preferred pattern is '<style_phrase>, <required_approved_clause>.' Avoid closely repeating "
            "recent_decisions. When selected_advice is present, preserve "
            "that actionable observation; otherwise do not narrate unrelated routine state. For silence, return "
            "an empty line. The spoken line may claim only what appears in approved_fallback, selected_advice, "
            "or a relevant_memories text field. Every other working-brain field controls tone and the silence "
            "decision only: never speak its counters, route state, session activity, or inferred meaning. Merge "
            "any approved fragments into exactly one grammatical sentence rather than retaining multiple full stops. "
            "Use only supplied facts. Never ask a question. Never say commander. Preserve every required term exactly, "
            "including spelling. Every required numeric term must remain Arabic digits: write 2, never two. "
            "Keep all numbers exactly as supplied. Do not add destinations, "
            "scenery, actions, threats, discoveries, or game facts. Return JSON only with action and line."
        )
        payload = {
            "approved_fallback": fallback,
            "required_exact_terms": protected,
            "active_persona": persona_name,
            "required_persona_style_terms": persona_terms,
            "required_approved_clause": fallback.rstrip(".!"),
            "speech_required": not bool(allow_silence),
            "cockpit_context": context,
            "rules": {"maximum_words": 32, "one_sentence": True},
        }
        return system, json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))

    def _generate(self, job, allow_cold=False):
        model = job["model"]
        state = self.status()
        if allow_cold and (not state["ready"] or state["model"] != model):
            self._warm(model)
        allow_silence = bool(job.get("allow_silence"))
        approved_seed = one_sentence_seed(job["fallback"])
        persona = (
            (((job.get("context") or {}).get("working_brain") or {}).get("pilot_model") or {})
            .get("persona") or {}
        )
        style_terms = (
            tuple(persona.get("signature_terms") or ())
            if str(persona.get("name") or "Compass") != "Compass" else ()
        )
        system, user = self._prompt(
            approved_seed, job["context"], job["required_terms"], allow_silence,
        )
        schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["speak", "silence"]},
                "line": {"type": "string", "description": "One spoken sentence, or empty for silence"},
            },
            "required": ["action", "line"], "additionalProperties": False,
        }
        if style_terms:
            schema["properties"]["style_phrase"] = {
                "type": "string", "enum": list(style_terms),
                "description": "The exact persona opener used in line",
            }
            schema["required"].append("style_phrase")
        timeout = max(1.0, min(8.0, float(self.config.get("cockpit_llm_timeout_s", 2.5) or 2.5)))
        started = time.perf_counter()
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False, "think": False, "format": schema, "keep_alive": "30m",
                "options": {
                    "num_ctx": 4096, "num_predict": 48, "temperature": 0.65,
                    "top_p": 0.8, "top_k": 20,
                },
            },
            timeout=(0.5, timeout),
        )
        response.raise_for_status()
        latency = round((time.perf_counter() - started) * 1000)
        content = (response.json().get("message") or {}).get("content") or ""
        try:
            decision = json.loads(content)
            action = str(decision.get("action") or "").casefold()
            line = decision.get("line")
            style_phrase = str(decision.get("style_phrase") or "").strip()
        except (TypeError, ValueError, AttributeError):
            action = ""
            line = None
            style_phrase = ""
        if action == "silence" and allow_silence:
            self._set_state(
                phase="ready", ready=True, last_error=None, last_latency_ms=latency,
                processor=self._processor(model), last_action="silence",
                last_topic=job.get("topic"),
            )
            return {
                "action": "silence", "line": None, "used_llm": True,
                "error": None, "latency_ms": latency,
            }
        if action != "speak":
            line = None
        line = validate_generated_line(
            line, approved_seed, job["required_terms"], job["context"], style_terms,
        )
        # A persona response may understand the character but still add a
        # second sentence or unsupported flourish.  The grammar-constrained
        # style choice is safe to retain: combine it with the approved clause
        # instead of dropping all audible personality or weakening validation.
        if not line and style_terms and style_phrase in style_terms:
            safe_persona_line = f"{style_phrase}, {approved_seed}"
            line = validate_generated_line(
                safe_persona_line, approved_seed, job["required_terms"],
                job["context"], (style_phrase,),
            )
        if not line:
            raise RuntimeError("Generated line failed factual or speech validation.")
        self._set_state(
            phase="ready", ready=True, last_error=None, last_latency_ms=latency,
            processor=self._processor(model), last_action="speak",
            last_topic=job.get("topic"),
        )
        return {
            "action": "speak", "line": line, "used_llm": True,
            "error": None, "latency_ms": latency,
        }

    def _pull(self, model, callback):
        self._ensure_server()
        self._set_state(
            phase="downloading", model=model, ready=False, last_error=None,
            download_progress=0.0,
        )
        last_callback_at = 0.0
        with requests.post(
            f"{OLLAMA_URL}/api/pull", json={"model": model, "stream": True},
            stream=True, timeout=(2.0, 1800.0),
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines():
                if self._stop.is_set():
                    break
                if not raw_line:
                    continue
                data = json.loads(raw_line)
                total = int(data.get("total") or 0)
                completed = int(data.get("completed") or 0)
                progress = completed / total if total else self.status().get("download_progress")
                self._set_state(download_progress=progress)
                now = time.monotonic()
                if callback and now - last_callback_at >= 0.2:
                    callback(self.status())
                    last_callback_at = now
        self._set_state(installed=True, download_progress=1.0)
        result = self._warm(model)
        if callback:
            callback(result)
        return result

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self._jobs.get(timeout=0.25)
            except queue.Empty:
                continue
            callback = job.get("callback")
            result = None
            try:
                if job["kind"] == "warm":
                    result = self._warm(job["model"])
                elif job["kind"] == "pull":
                    result = self._pull(job["model"], callback)
                    callback = None
                else:
                    result = self._generate(job, allow_cold=job["kind"] == "test")
            except Exception as exc:
                message = str(exc)
                ready = self.status().get("ready", False) and job["kind"] not in ("warm", "pull")
                self._set_state(
                    phase="degraded" if ready else "error", ready=ready,
                    last_error=message,
                )
                if job["kind"] in ("speak", "test"):
                    result = {
                        "action": "speak", "line": job["fallback"],
                        "used_llm": False, "error": message,
                    }
                else:
                    result = self.status()
            finally:
                if callback:
                    try:
                        callback(result)
                    except Exception:
                        pass
                self._jobs.task_done()

    def stop(self):
        self._stop.set()
        if self.config.get("cockpit_llm_unload_on_shutdown", True):
            try:
                requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": self.model, "keep_alive": 0}, timeout=(0.25, 1.0),
                )
            except requests.RequestException:
                pass
        process = self._owned_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except Exception:
                    pass
        self._thread.join(timeout=1.0)
