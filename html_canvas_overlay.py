"""Mirror existing Tk Canvas overlays into the shared HTML renderer."""

from __future__ import annotations

import logging
import os
import tkinter.font as tkfont

from html_overlay_runtime import HtmlOverlaySurface


_ITEM_OPTIONS = {
    "line": ("fill", "width", "dash", "capstyle", "joinstyle", "smooth", "arrow"),
    "rectangle": ("fill", "outline", "width", "dash"),
    "oval": ("fill", "outline", "width", "dash"),
    "polygon": ("fill", "outline", "width", "dash", "smooth"),
    "arc": ("fill", "outline", "width", "dash", "start", "extent", "style"),
    "text": ("text", "fill", "anchor", "justify", "angle", "width"),
}


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _bool(value):
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _font_model(canvas, item_id):
    try:
        font = tkfont.Font(root=canvas, font=canvas.itemcget(item_id, "font"))
        actual = font.actual()
        raw_size = int(actual.get("size", 9) or 9)
        size = (max(1, abs(raw_size)) if raw_size < 0 else
                max(1, round(raw_size * float(canvas.winfo_fpixels("1p")))))
        return {
            "family": str(actual.get("family") or "Courier New"),
            "size": size,
            "weight": str(actual.get("weight") or "normal"),
            "slant": str(actual.get("slant") or "roman"),
            "underline": bool(actual.get("underline")),
            "overstrike": bool(actual.get("overstrike")),
        }
    except Exception:
        return {"family": "Courier New", "size": 9, "weight": "normal", "slant": "roman"}


def _widget_font_model(widget):
    try:
        font = tkfont.Font(root=widget, font=widget.cget("font"))
        actual = font.actual()
        raw_size = int(actual.get("size", 9) or 9)
        size = (max(1, abs(raw_size)) if raw_size < 0 else
                max(1, round(raw_size * float(widget.winfo_fpixels("1p")))))
        return {
            "family": str(actual.get("family") or "Courier New"), "size": size,
            "weight": str(actual.get("weight") or "normal"),
            "slant": str(actual.get("slant") or "roman"),
        }
    except Exception:
        return {"family": "Courier New", "size": 9, "weight": "normal", "slant": "roman"}


def _widget_scene(widget, canvas):
    """Flatten the Colony overlay's embedded Tk controls for visual parity."""
    result = []
    try:
        canvas_x, canvas_y = canvas.winfo_rootx(), canvas.winfo_rooty()
    except Exception:
        return result

    def visit(node):
        try:
            if not node.winfo_ismapped() and str(node.winfo_manager()) != "pack":
                return
            x = node.winfo_rootx() - canvas_x
            y = node.winfo_rooty() - canvas_y
            width, height = node.winfo_width(), node.winfo_height()
            if width <= 1 or height <= 1:
                return
            bg = str(node.cget("background"))
        except Exception:
            bg = ""
            x = y = width = height = 0
        if bg and bg.casefold() not in {"#ff00ff", "magenta"}:
            result.append({
                "type": "rectangle", "coords": [x, y, x + width, y + height],
                "fill": bg, "outline": "",
            })
        try:
            text = str(node.cget("text"))
        except Exception:
            text = ""
        if text:
            try:
                fg = str(node.cget("foreground"))
            except Exception:
                fg = "#ffffff"
            prefix = ""
            try:
                variable = str(node.cget("variable"))
                if variable:
                    prefix = "[x] " if bool(node.getvar(variable)) else "[ ] "
            except Exception:
                pass
            result.append({
                "type": "text", "coords": [x + width / 2, y + height / 2],
                "text": prefix + text, "fill": fg, "anchor": "center",
                "font": _widget_font_model(node),
            })
        try:
            for child in node.winfo_children():
                visit(child)
        except Exception:
            pass

    visit(widget)
    return result


def canvas_scene(canvas):
    """Serialise the primitive subset used by Void Compass overlays."""
    items = []
    for item_id in canvas.find_all():
        kind = str(canvas.type(item_id) or "")
        if kind == "window":
            try:
                widget_name = canvas.itemcget(item_id, "window")
                widget = canvas.nametowidget(widget_name)
                items.extend(_widget_scene(widget, canvas))
            except Exception:
                pass
            continue
        if kind not in _ITEM_OPTIONS:
            continue
        try:
            if str(canvas.itemcget(item_id, "state")) == "hidden":
                continue
        except Exception:
            pass
        item = {
            "type": kind,
            "coords": [_number(value) for value in canvas.coords(item_id)],
        }
        for option in _ITEM_OPTIONS[kind]:
            try:
                value = canvas.itemcget(item_id, option)
            except Exception:
                continue
            if value in (None, ""):
                continue
            if option in {"width", "start", "extent", "angle"}:
                item[option] = _number(value)
            elif option == "smooth":
                item[option] = _bool(value)
            else:
                item[option] = str(value)
        if kind == "text":
            item["font"] = _font_model(canvas, item_id)
        items.append(item)
    width = max(1, int(_number(canvas.cget("width"))), int(canvas.winfo_width()))
    height = max(1, int(_number(canvas.cget("height"))), int(canvas.winfo_height()))
    return {"width": width, "height": height, "items": items}


class HtmlCanvasOverlayBridge:
    """Keep one non-navigation overlay's browser surface in sync with Tk."""

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
        self._last_quick_fingerprint = None
        self._last_window_fingerprint = None
        self._canvas_revision = 0
        self._install_canvas_mutation_hooks()
        try:
            self.win.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass
        self.set_enabled(bool(self.config.get("hud_html_renderer", False)))
        self._schedule()

    def _install_canvas_mutation_hooks(self):
        """Mark visual Canvas changes without serialising every HUD each tick.

        Several overlays keep stable item IDs and update their text/coordinates
        in place. Watching only ``find_all()`` therefore misses real journal
        changes. Instance-level wrappers retain Tk's normal API while giving
        the HTML mirror a cheap, renderer-neutral dirty revision.
        """
        always_mutating = {
            "delete", "move", "scale", "tag_raise", "tag_lower", "lift", "lower",
            "insert", "dchars",
        }
        conditional_mutating = {
            "coords", "itemconfigure", "itemconfig", "configure", "config",
        }
        create_methods = {
            name for name in dir(self.canvas) if name.startswith("create_")
        }
        for name in sorted(always_mutating | conditional_mutating | create_methods):
            original = getattr(self.canvas, name, None)
            if not callable(original):
                continue

            def wrapped(*args, _name=name, _original=original, **kwargs):
                result = _original(*args, **kwargs)
                changed = _name not in conditional_mutating
                if _name == "coords":
                    changed = len(args) > 1 or bool(kwargs)
                elif _name in {"itemconfigure", "itemconfig"}:
                    changed = len(args) > 1 or bool(kwargs)
                elif _name in {"configure", "config"}:
                    changed = bool(args or kwargs)
                if changed:
                    self._canvas_revision += 1
                return result

            setattr(self.canvas, name, wrapped)

    @property
    def ready(self):
        return self._ready

    def _safe_int(self, value, default):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return int(default)

    def _window_payload(self, scene):
        try:
            state = str(self.win.state())
            shown = state not in {"withdrawn", "iconic"}
        except Exception:
            shown = False
        startup_held = bool(getattr(
            self.win.master, "_voidcompass_startup_presentation_held", False,
        ))
        try:
            fallback_x, fallback_y = self.win.winfo_x(), self.win.winfo_y()
        except Exception:
            fallback_x = fallback_y = 0
        config_x = self._safe_int(self.config.get(self.x_key), fallback_x)
        config_y = self._safe_int(self.config.get(self.y_key), fallback_y)
        # Follow the proxy while it is being dragged. The saved profile value
        # remains the authority across restarts, but waiting for ButtonRelease
        # here would make overlays appear frozen during a native drag.
        use_live_position = (fallback_x, fallback_y) != (0, 0) or (config_x, config_y) == (0, 0)
        return {
            "x": fallback_x if use_live_position else config_x,
            "y": fallback_y if use_live_position else config_y,
            "width": int(scene["width"]),
            "height": int(scene["height"]),
            "visible": bool(shown and not startup_held and self.config.get(self.enabled_key, False)),
            "click_through": True,
        }

    def _snapshot(self):
        scene = canvas_scene(self.canvas)
        return {
            "schema": 1,
            "kind": "canvas",
            "name": self.overlay_id,
            "scene": scene,
            "window": self._window_payload(scene),
            "effects": {
                "crt": bool(self.config.get("hud_crt_enabled", True)),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
            },
        }

    def sync_window(self, x=None, y=None):
        """Send a Studio drag directly to the host without scene work."""
        surface = self.surface
        if surface is None:
            return False
        scene = {
            "width": max(1, int(_number(self.canvas.cget("width"))), int(self.canvas.winfo_width())),
            "height": max(1, int(_number(self.canvas.cget("height"))), int(self.canvas.winfo_height())),
        }
        window = self._window_payload(scene)
        if x is not None:
            window["x"] = int(round(float(x)))
        if y is not None:
            window["y"] = int(round(float(y)))
        surface.update_window(window)
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
                held = bool(getattr(
                    self.win.master, "_voidcompass_startup_presentation_held", False,
                ))
                self.win.attributes("-alpha", 0.0 if held else 1.0)
            except Exception:
                pass
            self._last_fingerprint = None
            self._last_quick_fingerprint = None
            self._last_window_fingerprint = None
            return False
        if self.surface is not None:
            return True
        try:
            self.surface = HtmlOverlaySurface(
                self.win.master, self.overlay_id, template="canvas", title=self.title,
            )
            snapshot = self._snapshot()
            self._last_fingerprint = repr(snapshot)
            self._last_quick_fingerprint = self._quick_fingerprint()
            self._last_window_fingerprint = self._window_fingerprint()
            self.surface.publish(snapshot)
            return True
        except Exception as exc:
            self.surface = None
            logging.warning("HTML %s overlay unavailable; using Tk renderer: %s", self.overlay_id, exc)
            return False

    def _schedule(self):
        try:
            self._sync_job = self.win.after(100, self._sync)
        except Exception:
            self._sync_job = None

    def _quick_fingerprint(self):
        try:
            items = tuple(self.canvas.find_all())
            width = (str(self.canvas.cget("width")), int(self.canvas.winfo_width()))
            height = (str(self.canvas.cget("height")), int(self.canvas.winfo_height()))
        except Exception:
            items, width, height = (), (), ()
        return (
            self._canvas_revision, items, width, height,
            bool(self.config.get("hud_crt_enabled", True)),
            bool(self.config.get("reduced_motion_enabled", False)),
        )

    def _window_fingerprint(self):
        try:
            state = str(self.win.state())
            live_position = (int(self.win.winfo_x()), int(self.win.winfo_y()))
        except Exception:
            state, live_position = "gone", ()
        return (
            state, live_position,
            self.config.get(self.x_key), self.config.get(self.y_key),
            bool(self.config.get(self.enabled_key, False)),
            bool(getattr(
                self.win.master, "_voidcompass_startup_presentation_held", False,
            )),
        )

    def _sync(self):
        self._sync_job = None
        surface = self.surface
        if surface is not None:
            if surface.startup_failed:
                logging.warning(
                    "HTML %s overlay unavailable; returning to Tk renderer (%s)",
                    self.overlay_id, surface.host_status or "renderer did not connect",
                )
                self.set_enabled(False)
            else:
                was_ready = self._ready
                self._ready = surface.ready
                self.overlay._html_ready = self._ready
                if self._ready:
                    try:
                        self.win.attributes("-alpha", 0.0)
                    except Exception:
                        pass
                    if not was_ready:
                        logging.info("HTML %s overlay renderer is live", self.overlay_id)
                quick = self._quick_fingerprint()
                window_quick = self._window_fingerprint()
                # All standard overlays replace their primitive scene when
                # content changes. Colony embeds Tk widgets, so its labels can
                # change without changing Canvas item IDs and needs the full
                # comparison.
                if self.overlay_id == "colony" or quick != self._last_quick_fingerprint:
                    self._last_quick_fingerprint = quick
                    self._last_window_fingerprint = window_quick
                    snapshot = self._snapshot()
                    fingerprint = repr(snapshot)
                    if fingerprint != self._last_fingerprint:
                        self._last_fingerprint = fingerprint
                        surface.publish(snapshot)
                elif window_quick != self._last_window_fingerprint:
                    # Geometry-only Studio movement must never pay the cost of
                    # serialising an unchanged Canvas scene. The shared host
                    # has a dedicated lightweight window channel for this.
                    self._last_window_fingerprint = window_quick
                    self.sync_window()
        self._schedule()

    def _on_destroy(self, event):
        if event.widget is not self.win:
            return
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


def attach_html_canvas_overlay(overlay, overlay_id, title, enabled_key, x_key, y_key):
    """Attach once and expose a common ``set_html_renderer`` hook."""
    if overlay is None or getattr(overlay, "_html_canvas_bridge", None) is not None:
        return overlay
    bridge = HtmlCanvasOverlayBridge(overlay, overlay_id, title, enabled_key, x_key, y_key)
    overlay._html_canvas_bridge = bridge
    overlay._html_ready = False

    def set_html_renderer(enabled):
        result = bridge.set_enabled(enabled)
        overlay._html_ready = bridge.ready
        return result

    overlay.set_html_renderer = set_html_renderer
    overlay.sync_html_window = bridge.sync_window
    return overlay
