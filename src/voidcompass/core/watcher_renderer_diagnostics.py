"""Optional, once-per-surface Watcher renderer report for this app session."""

from pathlib import Path
import threading

from voidcompass.core.diagnostic_logs import log_clock, prepare_log, resolve_log_path

_lock = threading.Lock()
_reported = set()
_log_path = None
_SURFACES = {"boot", "dashboard", "overlay"}
_RENDERERS = {"three", "canvas"}
_REASONS = {"module-error": "Three.js module failed to load", "renderer-error": "Three.js renderer could not start"}


def record(surface, renderer, reason=""):
    """Append the first observed renderer for a surface; retry on write failure."""
    global _log_path
    if surface not in _SURFACES or renderer not in _RENDERERS:
        return False
    with _lock:
        if surface in _reported:
            return True
        try:
            if _log_path is None:
                _log_path = Path(prepare_log(resolve_log_path("watcher_renderer.log")))
            description = "Three.js active" if renderer == "three" else "Canvas fallback"
            detail = _REASONS.get(reason, "") if renderer == "canvas" else ""
            with _log_path.open("a", encoding="utf-8") as stream:
                stream.write(f"{log_clock()} Watcher {surface}: {description} ({renderer}){': ' + detail if detail else ''}\n")
        except OSError:
            return False
        _reported.add(surface)
        return True
