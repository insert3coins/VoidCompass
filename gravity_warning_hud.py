"""GravityWarningHUD — transient warning overlay for high-gravity landable bodies.

Shown when the body the commander is currently approaching (ApproachBody)
has a known surface gravity (from an earlier Scan this session) at or
above a configurable threshold. Auto-hides after a timeout, same pattern
as ProspectorHUD.
"""

import tkinter as tk
from config import COLOR_TEXT, COLOR_ORANGE, save_config
import overlay_chrome

_CHROMA = "#ff00ff"
_RED = "#ff5a5a"


class GravityWarningHUD:
    WIDTH = 300
    HEIGHT = 90

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._hide_job = None
        self._last_body = None
        self._last_gravity = None

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)

        self.canvas = tk.Canvas(self.win, width=self.WIDTH, height=self.HEIGHT, bg=overlay_bg, highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        # Right side, clear of the left-edge overlay stack (system info /
        # carrier / station info / survey status).
        screen_w = root.winfo_screenwidth()
        default_x = max(30, screen_w - self.WIDTH - 30)
        x = self._safe_int(config.get("gravity_warning_hud_x"), default_x)
        y = self._safe_int(config.get("gravity_warning_hud_y"), 530)
        self.win.geometry(overlay_chrome.position_geometry(x, y))

        self._force_topmost()
        self.win.withdraw()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self._force_topmost)

    def show(self):
        try:
            x = self._safe_int(self.config.get("gravity_warning_hud_x"), 30)
            y = self._safe_int(self.config.get("gravity_warning_hud_y"), 30)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

    def hide(self):
        if self._hide_job:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        try:
            self.win.withdraw()
        except Exception:
            pass

    def _schedule_hide(self):
        if self._hide_job:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
        timeout_s = max(5, int(self.config.get("gravity_warning_hud_timeout_s") or 20))
        self._hide_job = self.win.after(timeout_s * 1000, self._auto_hide)

    def _auto_hide(self):
        self._hide_job = None
        self.hide()

    def _threshold(self):
        try:
            return max(0.5, float(self.config.get("gravity_warning_threshold_g", 3.0) or 3.0))
        except Exception:
            return 3.0

    # ── Data interface ───────────────────────────────────────────────────

    def check_body(self, body_name, gravity_g):
        """Show/refresh/hide the warning for the currently-approached body.

        Silently does nothing if gravity_g is unknown (body not yet scanned
        this session) — this overlay can only warn about bodies we already
        have data for, same limitation as the local-data-only game state.
        """
        if not body_name or gravity_g is None:
            return
        if gravity_g < self._threshold():
            if self._last_body == body_name:
                self.clear()
            return
        if body_name == self._last_body and gravity_g == self._last_gravity:
            self.show()
            self._schedule_hide()
            return
        self._last_body = body_name
        self._last_gravity = gravity_g
        self._redraw(body_name, gravity_g)
        self.show()
        self._schedule_hide()

    def clear(self):
        """Called on LeaveBody — drop tracked state and hide immediately."""
        self._last_body = None
        self._last_gravity = None
        self.hide()

    # ── Drag-to-move ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    def _drag_end(self, event):
        self.config["gravity_warning_hud_x"] = self.win.winfo_x()
        self.config["gravity_warning_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def _redraw(self, body_name, gravity_g):
        w, h = self.WIDTH, self.HEIGHT
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(self.canvas, w, h, accent=_RED, bracket_len=10)
        self.canvas.create_line(16, 30, w - 16, 30, fill=_RED, width=1)
        self._text(w / 2, 18, "⚠  HIGH GRAVITY WORLD  ⚠", _RED, ("Courier", 10, "bold"), anchor="center")
        self._text(w / 2, 48, body_name.upper() if len(body_name) <= 30 else body_name[:29].upper() + "…",
                    COLOR_TEXT, ("Courier", 11, "bold"), anchor="center")
        self._text(w / 2, 70, f"{gravity_g:.2f} g   (threshold {self._threshold():.1f} g)",
                    COLOR_ORANGE, ("Courier", 9, "bold"), anchor="center")
