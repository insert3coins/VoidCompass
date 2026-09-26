"""Purpose-built HTML planet-waypoint navigator bridge."""

from __future__ import annotations

import logging
import os
import time

from voidcompass.core import themes
from voidcompass.overlays.html_overlay_runtime import (
    HtmlOverlayBridgeLifecycle,
    HtmlOverlaySurface,
    overlay_opacity_ratio,
)


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


class HtmlGroundOverlayBridge(HtmlOverlayBridgeLifecycle):
    """Turn the legacy ground popup proxy into a semantic HTML surface."""

    # Closing speed is measured, never modelled: it comes from the change in
    # real distance between Status.json positions. Elite repeats a position
    # while nothing moves, so a sample this old means the commander stopped.
    _CLOSING_STALE_S = 3.0
    # Faster than any glide or boost: a relog, a respawn or a new fix, so the
    # old samples no longer describe one continuous approach.
    _CLOSING_MAX_MPS = 3000.0

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
        self._browser_content_height = 0
        self._closing_key = None
        self._closing_sample = None
        self._closing_mps = None
        try:
            self.win.on_destroy(self._on_destroy)
        except Exception:
            pass
        self.set_enabled(True)
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
        width, height = self._dimensions()
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
            "width": width,
            "height": height,
            "visible": bool(
                shown and self._active(solution) and not held
                and self.config.get(self.enabled_key, True)
            ),
            "click_through": bool(self.config.get("overlay_mouse_passthrough", True)),
        }

    def _text_scale(self):
        return max(75, min(200, _integer(
            self.config.get("overlay_text_scale_percent"), 100,
        ))) / 100.0

    def _dimensions(self):
        # The compass is a fixed instrument that the page zooms by the overlay
        # text size, so the window grows by the same factor instead of
        # squeezing its heading tape. Height still follows the page content.
        scale = self._text_scale()
        width = int(round(420 * scale))
        floor, ceiling = int(round(208 * scale)), int(round(400 * scale))
        measured = _integer(self._browser_content_height, 0)
        return width, max(floor, min(ceiling, measured)) if measured else floor

    def _theme(self):
        _, palette = themes.resolve_theme(
            self.config.get("ui_theme_name"),
            self.config.get("ui_custom_themes") or {},
        )
        return dict(palette or {})

    def _mode(self):
        app = self.app
        if getattr(app, "current_on_foot", False):
            return "foot"
        if getattr(app, "current_in_srv", False):
            return "srv"
        if getattr(app, "current_in_fighter", False):
            return "fighter"
        if getattr(app, "current_in_taxi", False) or getattr(app, "current_in_multicrew", False):
            return "passenger"
        return "ship"

    def _body_short(self):
        body = str(getattr(self.app, "current_body_name", "") or "").strip()
        system = str(getattr(self.app, "current_sys", "") or "").strip()
        if system and body.casefold().startswith(system.casefold() + " "):
            return body[len(system) + 1:].strip()
        return body

    def _closing(self, solution, now=None):
        """Return (closing m/s, ETA seconds) from successive real distances."""
        now = time.monotonic() if now is None else now
        distance = solution.get("distance_m") if solution.get("state") == "OK" else None
        key = (
            getattr(self.app, "target_lat", None), getattr(self.app, "target_lon", None),
            str(getattr(self.app, "current_body_name", "") or ""),
        )
        if distance is None or key != self._closing_key:
            self._closing_key = key
            self._closing_sample = None if distance is None else (float(distance), now)
            self._closing_mps = None
            return None, None
        distance = float(distance)
        if self._closing_sample is None:
            self._closing_sample = (distance, now)
            return None, None
        last_distance, last_at = self._closing_sample
        if distance != last_distance:
            elapsed = now - last_at
            if elapsed >= 0.05:
                rate = (last_distance - distance) / elapsed
                if abs(rate) > self._CLOSING_MAX_MPS:
                    self._closing_mps = None
                elif self._closing_mps is None:
                    self._closing_mps = rate
                else:
                    self._closing_mps = self._closing_mps * 0.6 + rate * 0.4
                self._closing_sample = (distance, now)
        elif self._closing_mps is not None and now - last_at > self._CLOSING_STALE_S:
            self._closing_mps = 0.0
        closing = self._closing_mps
        if closing is None:
            return None, None
        eta = distance / closing if closing > 0.5 else None
        return round(closing, 1), (int(round(eta)) if eta is not None else None)

    def _snapshot(self):
        solution = self._solution()
        distance = solution.get("distance_m")
        bearing = solution.get("bearing")
        delta = solution.get("heading_delta")
        try:
            distance_label = self.app._format_ground_distance(distance)
        except Exception:
            distance_label = "—"
        mode = self._mode()
        landed = bool(getattr(self.app, "current_landed", False))
        altitude = getattr(self.app, "current_altitude_m", None)
        closing, eta = self._closing(solution)
        return {
            "schema": 1,
            "kind": "ground-target",
            "name": self.overlay_id,
            "navigation": {
                "active": self._active(solution),
                "state": str(solution.get("state") or "OFF"),
                "body": str(getattr(self.app, "current_body_name", "") or "SURFACE FIX"),
                "target_label": str(getattr(self.app, "ground_target_label", "") or ""),
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
                "body_short": self._body_short(),
                "mode": mode,
                "landed": landed,
                # Altitude matters only to a pilot in flight; SRVs and suits
                # report the surface they stand on.
                "altitude_m": altitude if mode == "ship" and not landed else None,
                "closing_mps": closing,
                "eta_s": eta,
            },
            "theme": self._theme(),
            "effects": {
                "crt": bool(self.config.get("hud_crt_enabled", True)),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
                "text_scale": self._text_scale(),
                "opacity": overlay_opacity_ratio(self.config),
            },
            "window": self._window_payload(solution),
        }

    def set_enabled(self, enabled):
        enabled = bool(enabled and os.name == "nt")
        if not enabled:
            surface, self.surface = self.surface, None
            self._ready = False
            self.win._html_ready = False
            if surface is not None:
                surface.dispose()
            pass
            self._last_fingerprint = None
            self._browser_content_height = 0
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
            pass
            logging.warning("HTML Planet Waypoint Navigation unavailable; overlay suppressed: %s", exc)
            return False

    def _schedule(self):
        try:
            self._sync_job = self.win.call_later(100, self._sync)
        except Exception:
            self._sync_job = None

    def _sync(self):
        self._sync_job = None
        if self.surface is not None:
            if self.surface.startup_failed:
                logging.warning(
                    "HTML Planet Waypoint Navigation unavailable; overlay remains suppressed (%s)",
                    self.surface.host_status or "renderer did not connect",
                )
                self.set_enabled(False)
            else:
                was_ready = self._ready
                self._ready = self.surface.ready
                self.win._html_ready = self._ready
                pass
                measured_height = self.surface.server.rendered_content_height(
                    self.overlay_id,
                )
                if measured_height != self._browser_content_height:
                    self._browser_content_height = measured_height
                    self.win._html_window_size = self._dimensions()
                if self._ready:
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

def attach_html_ground_overlay(app, window, overlay_id, title, enabled_key, x_key, y_key):
    if window is None or getattr(window, "_html_ground_bridge", None) is not None:
        return window
    bridge = HtmlGroundOverlayBridge(
        app, window, overlay_id, title, enabled_key, x_key, y_key,
    )
    window._html_ground_bridge = bridge
    window._html_ready = False
    window._html_window_size = bridge._dimensions()

    def set_html_renderer(enabled):
        result = bridge.set_enabled(enabled)
        window._html_ready = bridge.ready
        return result

    window.set_html_renderer = set_html_renderer
    window.sync_html_window = bridge.sync_window
    return window
