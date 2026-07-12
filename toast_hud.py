"""ToastHUD — generic transient notification popup stack, modeled on
SrvSurvey's PlotFloatie.

Not exploration-specific: any part of the app can call push(title, message,
severity, icon) to show a short-lived popup. Toasts stack vertically from a
corner anchor and auto-dismiss individually after their own timeout.
"""

import time
import tkinter as tk
from config import COLOR_ACCENT, COLOR_TEXT, COLOR_ORANGE, save_config

_CHROMA = "#ff00ff"
_RED = "#ff5a5a"
_GREEN = "#54e39a"

_SEVERITY_COLOR = {
    "info": COLOR_ACCENT,
    "warn": COLOR_ORANGE,
    "fail": _RED,
    "success": _GREEN,
}

WIDTH = 320
_TOAST_H = 46
_GAP = 6
_MAX_STACK = 4
_TEXT_X = 14
_ICON_X = WIDTH - 25
_TITLE_CHARS = 34
_MESSAGE_CHARS = 39


class ToastHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._toasts = []  # list of {id, title, message, severity, expire_at}
        self._next_id = 1
        self._tick_job = None

        self.win = tk.Toplevel(root)
        self.win.attributes("-topmost", True, "-transparentcolor", _CHROMA, "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg=_CHROMA)

        self.canvas = tk.Canvas(self.win, width=WIDTH, height=10, bg=_CHROMA, highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        x = self._safe_int(config.get("toast_hud_x"), None)
        y = self._safe_int(config.get("toast_hud_y"), None)
        if x is None or y is None:
            screen_w = root.winfo_screenwidth()
            x = screen_w - WIDTH - 40
            y = 60
        self.win.geometry(f"+{x}+{y}")

        self._force_topmost()
        self.win.withdraw()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return default

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _force_topmost(self):
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        refresh_ms = max(2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000))
        self.win.after(refresh_ms, self._force_topmost)

    # ── Data interface ───────────────────────────────────────────────────

    def push(self, title, message="", severity="info", duration_s=6.0, icon=None):
        """Queue a new toast. Oldest is dropped if the stack is already full."""
        toast = {
            "id": self._next_id,
            "title": str(title or ""),
            "message": str(message or ""),
            "icon": str(icon or ""),
            "severity": severity if severity in _SEVERITY_COLOR else "info",
            "expire_at": time.time() + max(2.0, float(duration_s or 6.0)),
        }
        self._next_id += 1
        self._toasts.append(toast)
        if len(self._toasts) > _MAX_STACK:
            self._toasts = self._toasts[-_MAX_STACK:]
        self._redraw()
        self._ensure_tick()
        try:
            x = self._safe_int(self.config.get("toast_hud_x"), self.win.winfo_x())
            y = self._safe_int(self.config.get("toast_hud_y"), self.win.winfo_y())
            self.win.geometry(f"+{x}+{y}")
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
        except Exception:
            pass

    def _ensure_tick(self):
        if self._tick_job is not None:
            return
        self._tick()

    def _tick(self):
        self._tick_job = None
        now = time.time()
        before = len(self._toasts)
        self._toasts = [t for t in self._toasts if t["expire_at"] > now]
        if len(self._toasts) != before:
            self._redraw()
        if self._toasts:
            self._tick_job = self.win.after(300, self._tick)
        else:
            try:
                self.win.withdraw()
            except Exception:
                pass

    # ── Drag-to-move ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        self.config["toast_hud_x"] = self.win.winfo_x()
        self.config["toast_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    @staticmethod
    def _truncate(text, max_chars):
        text = str(text or "")
        return text if len(text) <= max_chars else text[:max_chars - 1] + "…"

    def _redraw(self):
        w = WIDTH
        n = len(self._toasts)
        h = max(1, n * _TOAST_H + max(0, n - 1) * _GAP)
        self.canvas.config(width=w, height=h)
        self.win.geometry(f"{w}x{h}")
        self.canvas.delete("all")

        y = 0
        for toast in self._toasts:
            color = _SEVERITY_COLOR[toast["severity"]]
            self.canvas.create_rectangle(0, y, w, y + _TOAST_H, fill="#010101", outline="")
            self.canvas.create_rectangle(0, y, 4, y + _TOAST_H, fill=color, outline="")
            self.canvas.create_rectangle(4, y, w, y + _TOAST_H, outline=color, width=1)
            if toast.get("icon"):
                self._text(
                    _ICON_X,
                    y + (_TOAST_H // 2),
                    toast["icon"],
                    COLOR_TEXT,
                    ("Segoe UI Emoji", 18),
                    anchor="center",
                )
            self._text(
                _TEXT_X,
                y + 15,
                self._truncate(toast["title"], _TITLE_CHARS),
                color,
                ("Courier", 9, "bold"),
            )
            if toast["message"]:
                self._text(
                    _TEXT_X,
                    y + 32,
                    self._truncate(toast["message"], _MESSAGE_CHARS),
                    COLOR_TEXT,
                    ("Courier", 8),
                )
            y += _TOAST_H + _GAP
