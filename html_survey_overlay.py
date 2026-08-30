"""Purpose-built HTML renderer bridge for Survey Operations."""

from __future__ import annotations

import json
import logging
import os

from html_overlay_runtime import HtmlOverlaySurface, suppress_native_proxy, overlay_opacity_ratio


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _json_safe(value):
    """Detach journal-owned containers and tolerate uncommon restored values."""
    return json.loads(json.dumps(value or {}, ensure_ascii=False, default=str))


class HtmlSurveyOverlayBridge:
    """Publish SurveyStatusHUD's semantic model to its dedicated web page."""

    def __init__(self, overlay, overlay_id, title, enabled_key, x_key, y_key):
        self.overlay = overlay
        self.win = overlay.win
        self.canvas = overlay.canvas
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
        self._browser_content_height = 0
        try:
            self.win.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass
        self.set_enabled(True)
        self._schedule()

    @property
    def ready(self):
        return self._ready

    def _has_actionable_model(self):
        """Only map the browser surface when Survey has real work to show."""
        model = getattr(self.overlay, "_html_render_model", None)
        if not isinstance(model, dict) or model.get("mode") not in {"system", "body"}:
            return False
        if model.get("sampling"):
            return True
        if model.get("mode") == "body":
            body = model.get("body") or {}
            return bool(
                model.get("rows")
                or model.get("notable")
                or body.get("bio_count")
                or body.get("geo_count")
                or body.get("mining_count")
            )
        return bool(model.get("rows") or model.get("notable_rows"))

    def _dimensions(self):
        try:
            width = max(_safe_int(self.canvas.cget("width"), 420), self.canvas.winfo_width())
            height = max(_safe_int(self.canvas.cget("height"), 90), self.canvas.winfo_height())
        except Exception:
            width, height = 420, 90
        return width, max(height, _safe_int(self._browser_content_height))

    def _window_payload(self):
        width, height = self._dimensions()
        try:
            state = str(self.win.state())
            shown = state not in {"withdrawn", "iconic"}
            fallback_x, fallback_y = self.win.winfo_x(), self.win.winfo_y()
        except Exception:
            shown = False
            fallback_x = fallback_y = 0
        startup_held = bool(getattr(
            self.win.master, "_voidcompass_startup_presentation_held", False,
        ))
        config_x = _safe_int(self.config.get(self.x_key), fallback_x)
        config_y = _safe_int(self.config.get(self.y_key), fallback_y)
        use_live = (fallback_x, fallback_y) != (0, 0) or (config_x, config_y) == (0, 0)
        return {
            "x": fallback_x if use_live else config_x,
            "y": fallback_y if use_live else config_y,
            "width": width,
            "height": height,
            "visible": bool(
                shown
                and self._has_actionable_model()
                and not startup_held
                and self.config.get(self.enabled_key, False)
            ),
            "click_through": True,
        }

    def _snapshot(self):
        try:
            text_scale = max(75, min(200, _safe_int(
                self.config.get("overlay_text_scale_percent"), 100,
            ))) / 100.0
        except Exception:
            text_scale = 1.0
        return {
            "schema": 1,
            "kind": "survey",
            "name": self.overlay_id,
            "survey": _json_safe(getattr(self.overlay, "_html_render_model", None)),
            "theme": dict(getattr(self.overlay, "_palette", {}) or {}),
            "effects": {
                "crt": bool(self.config.get("hud_crt_enabled", True)),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
                "text_scale": text_scale,
                "opacity": overlay_opacity_ratio(self.config),
            },
            "window": self._window_payload(),
        }

    def _quick_fingerprint(self):
        window = self._window_payload()
        palette = tuple(sorted((getattr(self.overlay, "_palette", {}) or {}).items()))
        return (
            getattr(self.overlay, "_last_render_key", None),
            self._has_actionable_model(),
            palette,
            tuple(sorted(window.items())),
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
            self._browser_content_height = 0
            return False
        if self.surface is not None:
            return True
        try:
            self.surface = HtmlOverlaySurface(
                self.win.master, self.overlay_id, template="survey", title=self.title,
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
            logging.warning("HTML Survey Operations unavailable; overlay suppressed: %s", exc)
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
                    "HTML Survey Operations unavailable; overlay remains suppressed (%s)",
                    surface.host_status or "renderer did not connect",
                )
                self.set_enabled(False)
            else:
                was_ready = self._ready
                self._ready = surface.ready
                self.overlay._html_ready = self._ready
                suppress_native_proxy(self.win)
                measured_height = surface.server.rendered_content_height(
                    self.overlay_id,
                )
                if measured_height != self._browser_content_height:
                    self._browser_content_height = measured_height
                    # Window geometry is part of the quick fingerprint. Force
                    # one immediate publication so the shared host resizes
                    # before the next journal model arrives.
                    self._last_quick_fingerprint = None
                if self._ready:
                    if not was_ready:
                        logging.info("HTML Survey Operations renderer is live")
                quick = self._quick_fingerprint()
                if quick != getattr(self, "_last_quick_fingerprint", None):
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


def attach_html_survey_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    """Attach the dedicated Survey Operations browser renderer once."""
    if overlay is None or getattr(overlay, "_html_survey_bridge", None) is not None:
        return overlay
    bridge = HtmlSurveyOverlayBridge(
        overlay, overlay_id, title, enabled_key, x_key, y_key,
    )
    overlay._html_survey_bridge = bridge
    overlay._html_ready = False

    def set_html_renderer(enabled):
        result = bridge.set_enabled(enabled)
        overlay._html_ready = bridge.ready
        return result

    overlay.set_html_renderer = set_html_renderer
    overlay.sync_html_window = bridge.sync_window
    return overlay
