"""Coalesced background persistence for small application state files.

Void Compass receives some journal events in dense bursts.  Writing several
JSON snapshots and the runtime trace from different threads for every event
can make Windows storage or antivirus contention visible as a Tk UI freeze.
This module serialises those writes through one worker and keeps only the
newest pending snapshot for each file.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
import threading
import time


class PersistenceQueue:
    def __init__(self):
        self._condition = threading.Condition()
        self._jobs = {}
        self._active_path = None
        self._stopping = False
        self._writes = 0
        self._coalesced = 0
        self._retries = 0
        self._failures = 0
        self._last_write_ms = 0.0
        self._max_write_ms = 0.0
        self._thread = threading.Thread(
            target=self._run, name="void-persistence", daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _key(path):
        return os.path.normcase(os.path.abspath(os.fspath(path)))

    def submit_json(self, path, value, *, indent=2, delay_s=1.5, immediate=False):
        """Queue the newest JSON snapshot, replacing an older pending one."""
        key = self._key(path)
        # Copy on the caller while its reducer has a consistent view. JSON
        # encoding and all filesystem work happen on the persistence worker.
        snapshot = copy.deepcopy(value)
        now = time.monotonic()
        due = now if immediate else now + max(0.0, float(delay_s))
        with self._condition:
            previous = self._jobs.get(key)
            if previous is not None:
                self._coalesced += 1
                # Do not postpone a busy stream forever; retain the first due
                # time while replacing its payload with the newest snapshot.
                due = min(float(previous["due"]), due)
            self._jobs[key] = {
                "kind": "json", "path": key, "value": snapshot,
                "indent": indent, "due": due,
            }
            self._condition.notify_all()

    def append_text(self, path, text, *, delay_s=0.05):
        """Queue append-only text and merge adjacent pending chunks."""
        if not text:
            return
        key = self._key(path)
        now = time.monotonic()
        due = now + max(0.0, float(delay_s))
        with self._condition:
            previous = self._jobs.get(key)
            if previous is not None and previous.get("kind") == "append":
                previous["text"] += str(text)
                previous["due"] = min(float(previous["due"]), due)
                self._coalesced += 1
            else:
                self._jobs[key] = {
                    "kind": "append", "path": key, "text": str(text), "due": due,
                }
            self._condition.notify_all()

    def _next_ready(self):
        if not self._jobs:
            return None, None
        key, job = min(self._jobs.items(), key=lambda pair: pair[1]["due"])
        wait_s = float(job["due"]) - time.monotonic()
        if wait_s > 0:
            return None, wait_s
        self._jobs.pop(key, None)
        self._active_path = key
        return job, 0.0

    def _run(self):
        while True:
            with self._condition:
                while not self._jobs and not self._stopping:
                    self._condition.wait()
                if self._stopping and not self._jobs:
                    return
                job, wait_s = self._next_ready()
                if job is None:
                    self._condition.wait(timeout=max(0.001, wait_s or 0.05))
                    continue
            started = time.perf_counter()
            try:
                self._write(job)
                self._writes += 1
            except Exception as exc:
                attempt = int(job.get("attempt") or 0) + 1
                if attempt <= 3:
                    job["attempt"] = attempt
                    job["due"] = time.monotonic() + (0.15 * attempt)
                    with self._condition:
                        existing = self._jobs.get(job["path"])
                        if existing is None:
                            self._jobs[job["path"]] = job
                        elif job.get("kind") == existing.get("kind") == "append":
                            existing["text"] = job.get("text", "") + existing.get("text", "")
                            existing["due"] = min(existing["due"], job["due"])
                        # A newer JSON snapshot already pending supersedes a
                        # failed older one for the same path.
                        self._retries += 1
                        self._condition.notify_all()
                    logging.warning(
                        "Persistence write retry %s/3 for %s: %s",
                        attempt, Path(job["path"]).name, exc,
                    )
                else:
                    self._failures += 1
                    logging.error(
                        "Persistence write failed for %s after retries: %s",
                        Path(job["path"]).name, exc,
                    )
            finally:
                elapsed = (time.perf_counter() - started) * 1000.0
                self._last_write_ms = elapsed
                self._max_write_ms = max(self._max_write_ms, elapsed)
                with self._condition:
                    self._active_path = None
                    self._condition.notify_all()

    @staticmethod
    def _write(job):
        path = Path(job["path"])
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        if job["kind"] == "append":
            with path.open("a", encoding="utf-8") as handle:
                handle.write(job["text"])
            return
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(job["value"], handle, indent=job.get("indent", 2), ensure_ascii=False)
        os.replace(temporary, path)

    def flush(self, path=None, timeout=5.0):
        """Make matching jobs ready now and wait briefly for durable writes."""
        key = self._key(path) if path is not None else None
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._condition:
            for job_key, job in self._jobs.items():
                if key is None or job_key == key:
                    job["due"] = 0.0
            self._condition.notify_all()
            while True:
                pending = any(key is None or job_key == key for job_key in self._jobs)
                active = self._active_path is not None and (key is None or self._active_path == key)
                if not pending and not active:
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=min(0.1, remaining))

    def stats(self):
        with self._condition:
            oldest_due = min((job["due"] for job in self._jobs.values()), default=None)
            return {
                "pending": len(self._jobs),
                "active": bool(self._active_path),
                "writes": self._writes,
                "coalesced": self._coalesced,
                "retries": self._retries,
                "failures": self._failures,
                "last_write_ms": round(self._last_write_ms, 1),
                "max_write_ms": round(self._max_write_ms, 1),
                "oldest_due_ms": round(max(0.0, (oldest_due or 0) - time.monotonic()) * 1000.0, 1)
                if oldest_due is not None else 0.0,
            }


_QUEUE = PersistenceQueue()


def persistence_queue():
    return _QUEUE


def flush_persistence(path=None, timeout=5.0):
    return _QUEUE.flush(path=path, timeout=timeout)
