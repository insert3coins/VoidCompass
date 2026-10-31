"""The real overlay host with its passes timed, for tools/overlay_bench.py (dev only).

    python tools/overlay_bench_host.py <stats.json> <server url>

Writes how long each manifest pass, window apply and Win32 step took to
<stats.json> when the host exits.
"""
import atexit
import json
import sys
import time

from voidcompass.overlays import html_overlay_host as host

OUT = sys.argv.pop(1)
stats = {"passes": [], "applies": {}, "visibility_ms": [], "fetch_ms": [], "primitives": {}}
original_apply_manifest = host._OverlayHost._apply_manifest
original_apply = host._WindowController.apply
original_manifest = host._OverlayHost.manifest


def timed_apply_manifest(self, manifest, last_status):
    start = time.perf_counter()
    try:
        return original_apply_manifest(self, manifest, last_status)
    finally:
        stats["passes"].append((time.time(), 1000 * (time.perf_counter() - start), len(manifest)))


def timed_apply(self, payload, *args, **kwargs):
    start = time.perf_counter()
    before = self.last_visible
    try:
        return original_apply(self, payload, *args, **kwargs)
    finally:
        elapsed = 1000 * (time.perf_counter() - start)
        stats["applies"].setdefault(self.overlay_id, []).append(elapsed)
        if before != self.last_visible:
            stats["visibility_ms"].append((self.overlay_id, bool(self.last_visible), elapsed))


def timed_manifest(self):
    start = time.perf_counter()
    try:
        return original_manifest(self)
    finally:
        stats["fetch_ms"].append(1000 * (time.perf_counter() - start))


def primitive(name):
    original = getattr(host, name, None)
    if original is None:
        return

    def timed(*args, **kwargs):
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            stats["primitives"].setdefault(name, []).append(1000 * (time.perf_counter() - start))
    setattr(host, name, timed)


for name in ("_set_windows_visibility", "_apply_windows_style", "_apply_windows_geometry", "_windows_visibility",
             "_apply_webview_transparency", "monitor_scale", "_native_handle", "_apply_window_shape"):
    primitive(name)

original_settle = getattr(host._OverlayHost, "_settle", None)


def traced_settle(self):
    """What each window waiting under its cloak is waiting for."""
    now = time.monotonic()
    waiting = {overlay_id: {"age_ms": round(1000 * (now - c.pending_since)),
                            "painted": c.window._voidcompass_painted_at > c.mapped_at,
                            "render_ready": c.render_ready, "live": c.pending_live}
               for overlay_id, c in self.controllers.items() if getattr(c, "pending_since", None) is not None}
    shown = original_settle(self)
    if waiting:
        stats.setdefault("settles", []).append({"at": time.time(), "waiting": waiting, "shown": shown})
    return shown


if original_settle is not None:
    host._OverlayHost._settle = traced_settle
host._OverlayHost._apply_manifest = timed_apply_manifest
host._WindowController.apply = timed_apply
host._OverlayHost.manifest = timed_manifest


@atexit.register
def dump():
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(stats, handle)


sys.exit(host.main(sys.argv[1:]))
