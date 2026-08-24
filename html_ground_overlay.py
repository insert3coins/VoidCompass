"""Purpose-built HTML planet-waypoint navigator bridge."""

from __future__ import annotations

import logging
import os

import themes
from html_overlay_runtime import HtmlOverlaySurface, overlay_opacity_ratio


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


class HtmlGroundOverlayBridge:
    """Turn the legacy ground popup proxy into a semantic HTML surface."""

    def __init__(self, app, window, overlay_id, title, enabled_key, x_key, y_key):
        self.app = app
        self.win = window
        self.config = app.config
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
        self.set_enabled(bool(self.config.get("hud_html_renderer", False)))
        self._schedule()

    @property
    def ready(self):
        return self._ready

    def _solution(self):
        try:
            solution = self.app._ground_target_solution()
        except Exception:
            solution = None
        return solution if isinstance(solution, dict) else {}

    def _active(self, solution=None):
        solution = solution if solution is not None else self._solution()
        predicate = getattr(self.app, "_ground_target_should_show", None)
        if callable(predicate):
            try:
                return bool(predicate(solution))
            except Exception:
                return False
        return False

    def _window_payload(self, solution=None):
        held = bool(getattr(
            self.win.master, "_voidcompass_startup_presentation_held", False,
        ))
        try:
            shown = str(self.win.state()) not in {"withdrawn", "iconic"}
        except Exception:
            shown = False
        return {
            "x": _integer(self.config.get(self.x_key), 1320),
            "y": _integer(self.config.get(self.y_key), 160),
            "width": 370,
            "height": 154,
            "visible": bool(
                shown and self._active(solution) and not held
                and self.config.get(self.enabled_key, True)
            ),
            "click_through": True,
        }

    def _theme(self):
        _, palette = themes.resolve_theme(
            self.config.get("ui_theme_name"),
            self.config.get("ui_custom_themes") or {},
        )
        return dict(palette or {})

    def _snapshot(self):
        solution = self._solution()
        distance = solution.get("distance_m")
        bearing = solution.get("bearing")
        delta = solution.get("heading_delta")
        try:
            distance_label = self.app._format_ground_distance(distance)
        except Exception:
            distance_label = "—"
        return {
            "schema": 1,
            "kind": "ground-target",
            "name": self.overlay_id,
            "navigation": {
                "active": self._active(solution),
                "state": str(solution.get("state") or "OFF"),
                "body": str(getattr(self.app, "current_body_name", "") or "SURFACE FIX"),
                "target_lat": getattr(self.app, "target_lat", None),
                "target_lon": getattr(self.app, "target_lon", None),
                "current_lat": getattr(self.app, "current_latitude", None),
                "current_lon": getattr(self.app, "current_longitude", None),
                "heading": getattr(self.app, "current_heading", None),
                "bearing": bearing,
                "heading_delta": delta,
                "distance_m": distance,
                "distance_label": distance_label,
                "direction": str(solution.get("direction") or "HEADING N/A"),
            },
            "theme": self._theme(),
            "effects": {
                "crt": bool(self.config.get("hud_crt_enabled", True)),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
                "text_scale": max(75, min(200, _integer(
                    self.config.get("overlay_text_scale_percent"), 100,
                ))) / 100.0,
                "opacity": overlay_opacity_ratio(self.config),
            },
            "window": self._window_payload(solution),
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
            self.win._html_ready = False
            if surface is not None:
                surface.dispose()
            try:
                held = bool(getattr(
                    self.win.master, "_voidcompass_startup_presentation_held", False,
                ))
                self.win.attributes("-alpha", 0.0 if held else 1.0)
            except Exception:
                pass
            self._last_fingerprint = None
            return False
        if self.surface is not None:
            return True
        try:
            self.surface = HtmlOverlaySurface(
                self.win.master, self.overlay_id,
                template="ground", title=self.title,
            )
            snapshot = self._snapshot()
            self._last_fingerprint = repr(snapshot)
            self.surface.publish(snapshot)
            return True
        except Exception as exc:
            self.surface = None
            logging.warning("HTML Planet Waypoint Navigation unavailable; using Tk renderer: %s", exc)
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
                    "HTML Planet Waypoint Navigation unavailable; returning to Tk renderer (%s)",
                    self.surface.host_status or "renderer did not connect",
                )
                self.set_enabled(False)
            else:
                was_ready = self._ready
                self._ready = self.surface.ready
                self.win._html_ready = self._ready
                if self._ready:
                    try:
                        self.win.attributes("-alpha", 0.0)
                    except Exception:
                        pass
                    if not was_ready:
                        logging.info("HTML Planet Waypoint Navigation renderer is live")
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


def attach_html_ground_overlay(app, window, overlay_id, title, enabled_key, x_key, y_key):
    if window is None or getattr(window, "_html_ground_bridge", None) is not None:
        return window
    bridge = HtmlGroundOverlayBridge(
        app, window, overlay_id, title, enabled_key, x_key, y_key,
    )
    window._html_ground_bridge = bridge
    window._html_ready = False
    window._html_window_size = (370, 154)

    def set_html_renderer(enabled):
        result = bridge.set_enabled(enabled)
        window._html_ready = bridge.ready
        return result

    window.set_html_renderer = set_html_renderer
    window.sync_html_window = bridge.sync_window
    return window
