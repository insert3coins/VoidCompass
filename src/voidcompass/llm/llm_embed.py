"""The Watcher's library search by meaning (5.7.1): a small model (BAAI's
bge-small) that turns a card, or your question, into a list of numbers that
sit close together when they mean the same thing. "Who builds carriers?"
then finds the card about the Brewer Corporation, which shares no word with
it but "carriers".

It runs as a second, tiny llama-server on the CPU only (it never takes the
graphics card from the game or from the mind), started the first time it's
needed and asleep again when idle. Vectors are kept as 384 small whole
numbers each, so thousands of cards cost a few megabytes and are compared in
plain Python.
"""
from __future__ import annotations

from array import array
import base64
import json
import logging
import math
import operator
import threading
import urllib.error
import urllib.request

from voidcompass.llm import llm_assets
from voidcompass.llm.llm_server import IDLE_SLEEP_S, LlmServer

BATCH = 16
# A question is asked the way bge-small was taught to look for passages.
QUERY = "Represent this sentence for searching relevant passages: "
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class EmbedServer(LlmServer):
    """llama-server for the search model: embeddings only, CPU only."""

    def arguments(self):
        return [str(self.exe), "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.port),
                "--api-key", self.key, "--embedding", "--pooling", "cls", "-c", "512", "-b", "512", "-ub", "512",
                "--device", "none", "-ngl", "0", "-t", "2", "--no-webui", "--sleep-idle-seconds", str(IDLE_SLEEP_S)]

    def matches(self, exe, model, gpu, free_idle):
        return True

    def embed(self, texts, timeout=120.0):
        """Their vectors, in order, or None."""
        body = json.dumps({"input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/embeddings", data=body, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {self.key}"})
        try:
            with _OPENER.open(request, timeout=timeout) as response:
                data = json.loads(response.read() or b"{}")
            rows = sorted(data["data"], key=lambda row: row.get("index", 0))
            return [row["embedding"] for row in rows]
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as exc:
            logging.debug("Watcher library search request failed: %s", exc)
            return None


def pack(vector):
    """A vector, made unit length, as 384 small whole numbers in base64."""
    size = math.sqrt(sum(value * value for value in vector)) or 1.0
    return base64.b64encode(array("b", [max(-127, min(127, round(value / size * 127))) for value in vector])
                            .tobytes()).decode("ascii")


def unpack(text):
    numbers = array("b")
    numbers.frombytes(base64.b64decode(text))
    return numbers


def similarity(first, second):
    """How alike two packed vectors are: 1 the same, about 0 unrelated."""
    return sum(map(operator.mul, first, second)) / 16129.0


class Embedder:
    """Cards and questions to vectors, through the search model; None from
    any of it when the model isn't downloaded or won't answer."""

    def __init__(self, base=None, server_factory=EmbedServer):
        self.base = base
        self._factory = server_factory
        self._server = None
        self._lock = threading.Lock()
        self._failed = False

    def available(self):
        return llm_assets.embedder_installed(self.base) and not self._failed

    def _running(self):
        with self._lock:
            server = self._server
            if server is not None and server.running():
                return server
            if not self.available():
                return None
            server = self._factory(llm_assets.engine_exe(self.base), llm_assets.embedder_path(self.base), gpu=False,
                                   log_path=llm_assets.llm_dir(self.base) / "search.log")
            if not server.start() or not server.wait_ready(60):
                logging.warning("The Watcher's library search model wouldn't start: %s", server.error or "no answer")
                server.stop(wait=False)
                self._failed = True
                return None
            self._server = server
            return server

    def vectors(self, texts):
        """Packed vectors for these texts (cards), in order, or None."""
        server = self._running()
        if server is None:
            return None
        out = []
        texts = list(texts)
        for start in range(0, len(texts), BATCH):
            rows = server.embed([text[:1800] for text in texts[start:start + BATCH]])
            if rows is None or len(rows) != len(texts[start:start + BATCH]):
                return None
            out.extend(pack(row) for row in rows)
        return out

    def question(self, text):
        """A packed vector for a question, or None."""
        rows = self.vectors([QUERY + str(text or "")[:600]])
        return rows[0] if rows else None

    def close(self):
        with self._lock:
            server, self._server = self._server, None
        if server is not None:
            server.stop(wait=False)
