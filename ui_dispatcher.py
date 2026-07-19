"""Bounded, coalescing dispatcher for all cross-thread Tk work."""

from __future__ import annotations

from collections import deque
import logging
import threading
import time


class TkDispatcher:
    def __init__(self, root, *, interval_ms=15, budget_ms=8.0, max_tasks=48):
        self.root = root
        self.interval_ms = max(5, int(interval_ms))
        self.budget_ms = max(1.0, float(budget_ms))
        self.max_tasks = max(1, int(max_tasks))
        self._lock = threading.Lock()
        self._queue = deque()
        self._coalesced = {}
        self._running = True
        self._processed = 0
        self._failures = 0
        self._max_lag_ms = 0.0
        self._main_thread = threading.get_ident()
        self.root.after(self.interval_ms, self._drain)

    def post(self, callback, *args, key=None, **kwargs):
        if not self._running or not callable(callback):
            return False
        item = (time.monotonic(), callback, args, kwargs, key)
        with self._lock:
            if key is not None:
                old = self._coalesced.get(key)
                if old is not None:
                    old[1] = item
                else:
                    holder = [key, item]
                    self._coalesced[key] = holder
                    self._queue.append(holder)
            else:
                self._queue.append([None, item])
        return True

    def _pop(self):
        with self._lock:
            if not self._queue:
                return None
            holder = self._queue.popleft()
            key, item = holder
            if key is not None:
                self._coalesced.pop(key, None)
            return item

    def _drain(self):
        if not self._running:
            return
        started = time.perf_counter()
        handled = 0
        while handled < self.max_tasks:
            item = self._pop()
            if item is None:
                break
            queued_at, callback, args, kwargs, _key = item
            lag_ms = (time.monotonic() - queued_at) * 1000.0
            self._max_lag_ms = max(self._max_lag_ms, lag_ms)
            try:
                callback(*args, **kwargs)
            except Exception:
                self._failures += 1
                logging.exception(
                    "Tk dispatcher callback failed: %s",
                    getattr(callback, "__name__", type(callback).__name__),
                )
            self._processed += 1
            handled += 1
            if (time.perf_counter() - started) * 1000.0 >= self.budget_ms:
                break
        self.root.after(1 if self.pending else self.interval_ms, self._drain)

    @property
    def pending(self):
        with self._lock:
            return len(self._queue)

    def clear(self):
        with self._lock:
            self._queue.clear()
            self._coalesced.clear()

    def stop(self):
        self._running = False
        self.clear()

    def stats(self):
        return {
            "pending": self.pending,
            "processed": self._processed,
            "failures": self._failures,
            "max_lag_ms": round(self._max_lag_ms, 1),
            "main_thread": self._main_thread,
        }
