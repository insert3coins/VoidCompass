"""Purpose-built HTML renderer bridge for the transient gravity warning."""

from __future__ import annotations

import logging
import os

from html_overlay_runtime import HtmlOverlaySurface, suppress_native_proxy, overlay_opacity_ratio


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


class HtmlGravityOverlayBridge:
    """Publish GravityWarningHUD state without replaying Tk Canvas commands."""

    def __init__(self, overlay, overlay_id, title, enabled_key, x_key, y_key):
        self.overlay = overlay
        self.win = overlay.win
        self.config = overlay.config
        self.overlay_id = str(overlay_id)
        self.title = str(title)
        self.enabled_key = str(enabled_key)
        self.x_key = str(x_key)
        self.y_key = str(y_key)
        self.surface = None
        self._ready = False
        self._disposed = False
        self._sync_job = None
        self._last_fingerprint = None
        try:
            self.win.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass
        self.set_enabled(True)
        self._schedule()

    @property
    def ready(self):
        return self._ready

    def _window_payload(self):
        try:
            shown = str(self.win.state()) not in {"withdrawn", "iconic"}
            fallback_x, fallback_y = self.win.winfo_x(), self.win.winfo_y()
        except Exception:
            shown = False
            fallback_x = fallback_y = 0
        held = bool(getattr(
            self.win.master, "_voidcompass_startup_presentation_held", False,
        ))
        x = _integer(self.config.get(self.x_key), fallback_x)
        y = _integer(self.config.get(self.y_key), fallback_y)
        return {
            "x": x,
            "y": y,
            "width": 320,
            "height": 106,
            "visible": bool(
                shown and self.overlay._last_body is not None
                and self.overlay._last_gravity is not None
                and not held and self.config.get(self.enabled_key, False)
            ),
            "click_through": True,
        }

    def _snapshot(self):
        gravity = self.overlay._last_gravity
        threshold = self.overlay._threshold()
        ratio = max(0.0, float(gravity or 0.0)) / max(0.1, float(threshold))
        return {
            "schema": 1,
            "kind": "gravity",
            "name": self.overlay_id,
            "gravity": {
                "body": str(self.overlay._last_body or ""),
                "g": None if gravity is None else round(float(gravity), 2),
                "threshold": round(float(threshold), 1),
                "severity": "critical" if ratio >= 1.75 else "high" if ratio >= 1.25 else "warning",
                "ratio": min(2.0, ratio),
            },
            "theme": dict(getattr(self.overlay, "_palette", {}) or {}),
            "effects": {
                "crt": bool(self.config.get("hud_crt_enabled", True)),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
                "text_scale": max(75, min(200, _integer(
                    self.config.get("overlay_text_scale_percent"), 100,
                ))) / 100.0,
                "opacity": overlay_opacity_ratio(self.config),
            },
            "window": self._window_payload(),
        }

    def sync_window(self, x=None, y=None):
        if self.surface is None:
            return False
        window = self._window_payload()
        if x is not None:
            window["x"] = int(round(float(x)))
        if y is not None:
            window["y"] = int(round(float(y)))
        self.surface.update_window(window)
        return True

    def set_enabled(self, enabled):
        enabled = bool(enabled and os.name == "nt")
        if not enabled:
            surface, self.surface = self.surface, None
            self._ready = False
            self.overlay._html_ready = False
            if surface is not None:
                surface.dispose()
            try:
                self.win.attributes("-alpha", 0.0)
            except Exception:
                pass
            self._last_fingerprint = None
            return False
        if self.surface is not None:
            return True
        try:
            self.surface = HtmlOverlaySurface(
                self.win.master, self.overlay_id,
                template="gravity", title=self.title,
            )
            snapshot = self._snapshot()
            self._last_fingerprint = repr(snapshot)
            self.surface.publish(snapshot)
            return True
        except Exception as exc:
            self.surface = None
            try:
                self.win.attributes("-alpha", 0.0)
            except Exception:
                pass
            logging.warning("HTML Gravity Warning unavailable; overlay suppressed: %s", exc)
            return False

    def _schedule(self):
        try:
            self._sync_job = self.win.after(100, self._sync)
        except Exception:
            self._sync_job = None

    def _sync(self):
        self._sync_job = None
        if self.surface is not None:
            if self.surface.startup_failed:
                logging.warning(
                    "HTML Gravity Warning unavailable; overlay remains suppressed (%s)",
                    self.surface.host_status or "renderer did not connect",
                )
                self.set_enabled(False)
            else:
                was_ready = self._ready
                self._ready = self.surface.ready
                self.overlay._html_ready = self._ready
                suppress_native_proxy(self.win)
                if self._ready:
                    if not was_ready:
                        logging.info("HTML Gravity Warning renderer is live")
                snapshot = self._snapshot()
                fingerprint = repr(snapshot)
                if fingerprint != self._last_fingerprint:
                    self._last_fingerprint = fingerprint
                    self.surface.publish(snapshot)
        self._schedule()

    def _on_destroy(self, event):
        if event.widget is self.win:
            self.dispose()

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        if self._sync_job is not None:
            try:
                self.win.after_cancel(self._sync_job)
            except Exception:
                pass
            self._sync_job = None
        surface, self.surface = self.surface, None
        if surface is not None:
            surface.dispose()


def attach_html_gravity_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    if overlay is None or getattr(overlay, "_html_gravity_bridge", None) is not None:
        return overlay
    bridge = HtmlGravityOverlayBridge(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
    )
    overlay._html_gravity_bridge = bridge
    overlay._html_ready = False
    overlay._html_window_size = (320, 106)

    def set_html_renderer(enabled):
        result = bridge.set_enabled(enabled)
        overlay._html_ready = bridge.ready
        return result

    overlay.set_html_renderer = set_html_renderer
    overlay.sync_html_window = bridge.sync_window
    return overlay
