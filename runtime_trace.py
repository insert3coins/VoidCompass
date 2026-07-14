import json
import threading
import time

from diagnostic_logs import LOG_ARCHIVE_LIMIT, prepare_log


class RuntimeTrace:
    def __init__(self, path, enabled=True, legacy_paths=(), archive_limit=LOG_ARCHIVE_LIMIT):
        self.path = path
        self.enabled = bool(enabled)
        self.legacy_paths = tuple(legacy_paths or ())
        self.archive_limit = max(0, int(archive_limit))
        self._lock = threading.Lock()
        self._bucket = {}
        self._started = False

    def start(self):
        if not self.enabled or self._started:
            return
        self._started = True
        try:
            self.path = prepare_log(
                self.path,
                legacy_paths=self.legacy_paths,
                keep=self.archive_limit,
            )
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "type": "trace_start",
                            "version": 1,
                        }
                    )
                    + "\n"
                )
        except Exception:
            self.enabled = False

    def record_ms(self, label, elapsed_ms):
        if not self.enabled:
            return
        try:
            val = float(elapsed_ms)
        except Exception:
            return
        with self._lock:
            agg = self._bucket.get(label)
            if agg is None:
                agg = {"count": 0, "sum_ms": 0.0, "max_ms": 0.0}
                self._bucket[label] = agg
            agg["count"] += 1
            agg["sum_ms"] += val
            if val > agg["max_ms"]:
                agg["max_ms"] = val

    def bump(self, label, amount=1):
        if not self.enabled:
            return
        try:
            inc = int(amount)
        except Exception:
            return
        with self._lock:
            agg = self._bucket.get(label)
            if agg is None:
                agg = {"count": 0, "sum_ms": 0.0, "max_ms": 0.0, "bump": 0}
                self._bucket[label] = agg
            agg["bump"] = int(agg.get("bump", 0)) + inc

    def flush(self, extra=None):
        if not self.enabled:
            return
        with self._lock:
            snap = self._bucket
            self._bucket = {}
        if not snap and not extra:
            return
        payload = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "trace_tick",
            "metrics": {},
        }
        for label, agg in snap.items():
            cnt = int(agg.get("count", 0))
            total = float(agg.get("sum_ms", 0.0))
            mx = float(agg.get("max_ms", 0.0))
            out = {}
            if cnt > 0:
                out["count"] = cnt
                out["avg_ms"] = round(total / cnt, 3)
                out["max_ms"] = round(mx, 3)
            if "bump" in agg:
                out["bump"] = int(agg.get("bump", 0))
            if out:
                payload["metrics"][label] = out
        if extra:
            payload["extra"] = extra
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            self.enabled = False
