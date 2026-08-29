"""Purpose-built HTML renderer bridge for cockpit notifications."""

from __future__ import annotations

import logging
import os

from html_overlay_runtime import HtmlOverlaySurface, suppress_native_proxy, overlay_opacity_ratio


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


class HtmlToastOverlayBridge:
    """Publish ToastHUD's semantic queue to a dedicated HTML surface."""

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
        self._last_quick_fingerprint = None
        try:
            self.win.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass
        self.set_enabled(True)
        self._schedule()

    @property
    def ready(self):
        return self._ready

    def _notifications(self):
        result = []
        for item in list(getattr(self.overlay, "_toasts", ())):
            result.append({
                "id": _safe_int(item.get("id")),
                "title": str(item.get("title") or ""),
                "message": str(item.get("message") or ""),
                "icon": str(item.get("icon") or ""),
                "severity": str(item.get("severity") or "info"),
                "kind": str(item.get("kind") or "notice"),
                "created_at": float(item.get("created_at") or 0.0),
                "expire_at": float(item.get("expire_at") or 0.0),
                "meta": dict(item.get("meta") or {}),
            })
        return result

    def _dimensions(self, notifications=None):
        notifications = notifications if notifications is not None else self._notifications()
        width = _safe_int(getattr(self.overlay, "WIDTH", 400), 400)
        height_for = getattr(self.overlay, "toast_height", None)
        heights = [
            _safe_int(height_for(item) if callable(height_for) else 68, 68)
            for item in notifications
        ]
        gap = _safe_int(getattr(self.overlay, "GAP", 7), 7)
        return width, max(24, sum(heights) + max(0, len(heights) - 1) * gap)

    def _window_payload(self, notifications=None):
        notifications = notifications if notifications is not None else self._notifications()
        width, height = self._dimensions(notifications)
        try:
            shown = str(self.win.state()) not in {"withdrawn", "iconic"}
            fallback_x, fallback_y = self.win.winfo_x(), self.win.winfo_y()
        except Exception:
            shown = False
            fallback_x = fallback_y = 0
        config_x = _safe_int(self.config.get(self.x_key), fallback_x)
        config_y = _safe_int(self.config.get(self.y_key), fallback_y)
        use_live = (fallback_x, fallback_y) != (0, 0) or (config_x, config_y) == (0, 0)
        startup_held = bool(getattr(
            self.win.master, "_voidcompass_startup_presentation_held", False,
        ))
        return {
            "x": fallback_x if use_live else config_x,
            "y": fallback_y if use_live else config_y,
            "width": width,
            "height": height,
            "visible": bool(
                notifications
                and shown
                and not startup_held
                and self.config.get(self.enabled_key, False)
            ),
            "click_through": True,
        }

    def _snapshot(self):
        notifications = self._notifications()
        try:
            text_scale = max(75, min(200, _safe_int(
                self.config.get("overlay_text_scale_percent"), 100,
            ))) / 100.0
        except Exception:
            text_scale = 1.0
        return {
            "schema": 1,
            "kind": "notifications",
            "name": self.overlay_id,
            "notifications": notifications,
            "theme": dict(getattr(self.overlay, "_palette", {}) or {}),
            "effects": {
                "crt": bool(self.config.get("hud_crt_enabled", True)),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
                "text_scale": text_scale,
                "opacity": overlay_opacity_ratio(self.config),
            },
            "window": self._window_payload(notifications),
        }

    def _quick_fingerprint(self):
        try:
            state = str(self.win.state())
            live_position = (int(self.win.winfo_x()), int(self.win.winfo_y()))
        except Exception:
            state, live_position = "gone", ()
        return (
            _safe_int(getattr(self.overlay, "_html_revision", 0)),
            state, live_position,
            self.config.get(self.x_key), self.config.get(self.y_key),
            bool(self.config.get(self.enabled_key, False)),
            bool(getattr(self.win.master, "_voidcompass_startup_presentation_held", False)),
            tuple(sorted((getattr(self.overlay, "_palette", {}) or {}).items())),
            self.config.get("overlay_text_scale_percent"),
            self.config.get("overlay_opacity_percent", 100),
            bool(self.config.get("hud_crt_enabled", True)),
            bool(self.config.get("reduced_motion_enabled", False)),
        )

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
            self._last_quick_fingerprint = None
            return False
        if self.surface is not None:
            return True
        try:
            self.surface = HtmlOverlaySurface(
                self.win.master, self.overlay_id, template="toast", title=self.title,
            )
            snapshot = self._snapshot()
            self._last_fingerprint = repr(snapshot)
            self._last_quick_fingerprint = self._quick_fingerprint()
            self.surface.publish(snapshot)
            return True
        except Exception as exc:
            self.surface = None
            try:
                self.win.attributes("-alpha", 0.0)
            except Exception:
                pass
            logging.warning("HTML notifications unavailable; overlay suppressed: %s", exc)
            return False

    def _schedule(self):
        try:
            self._sync_job = self.win.after(100, self._sync)
        except Exception:
            self._sync_job = None

    def _sync(self):
        self._sync_job = None
        surface = self.surface
        if surface is not None:
            if surface.startup_failed:
                logging.warning(
                    "HTML notifications unavailable; overlay remains suppressed (%s)",
                    surface.host_status or "renderer did not connect",
                )
                self.set_enabled(False)
            else:
                was_ready = self._ready
                self._ready = surface.ready
                self.overlay._html_ready = self._ready
                suppress_native_proxy(self.win)
                if self._ready:
                    if not was_ready:
                        logging.info("HTML cockpit notification renderer is live")
                quick = self._quick_fingerprint()
                if quick != self._last_quick_fingerprint:
                    self._last_quick_fingerprint = quick
                    snapshot = self._snapshot()
                    fingerprint = repr(snapshot)
                    if fingerprint != self._last_fingerprint:
                        self._last_fingerprint = fingerprint
                        surface.publish(snapshot)
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


def attach_html_toast_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    """Attach the semantic notification renderer once."""
    if overlay is None or getattr(overlay, "_html_toast_bridge", None) is not None:
        return overlay
    bridge = HtmlToastOverlayBridge(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
    )
    overlay._html_toast_bridge = bridge
    overlay._html_ready = False

    def set_html_renderer(enabled):
        result = bridge.set_enabled(enabled)
        overlay._html_ready = bridge.ready
        return result

    overlay.set_html_renderer = set_html_renderer
    overlay.sync_html_window = bridge.sync_window
    return overlay
