"""Renderer-neutral transient cockpit notification queue.

Not exploration-specific: any part of the app can call push(title, message,
severity, icon) to show a short-lived popup. The dedicated HTML renderer gives
ordinary alerts and commander achievements distinct visual treatments while
this class retains the hidden native state proxy and authoritative expiry queue.
"""

import time
import tkinter as tk
from config import save_config
import overlay_chrome
import themes

_CHROMA = "#ff00ff"
_SEVERITIES = frozenset(("info", "warn", "fail", "success"))

WIDTH = 400
_TOAST_H = 66
_ACHIEVEMENT_H = 94
_GAP = 7
_MAX_STACK = 4
_TEXT_X = 17
_ICON_X = WIDTH - 31
_TITLE_CHARS = 43
_MESSAGE_CHARS = 50


class ToastHUD:
    WIDTH = WIDTH
    GAP = _GAP

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._toasts = []  # list of {id, title, message, severity, expire_at}
        self._next_id = 1
        self._tick_job = None
        self._html_revision = 0
        self._startup_pending_visible = False
        self._visible = False
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, _CHROMA)

        self.canvas = tk.Canvas(self.win, width=WIDTH, height=10, bg=overlay_bg, highlightthickness=0)
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
        self.win.geometry(overlay_chrome.position_geometry(x, y))

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

    @staticmethod
    def toast_height(toast):
        return _ACHIEVEMENT_H if str((toast or {}).get("kind")) == "achievement" else _TOAST_H

    def _show(self):
        if not self._toasts:
            return self.hide()
        if bool(getattr(
            self.root, "_voidcompass_startup_presentation_held", False,
        )):
            self._startup_pending_visible = True
            try:
                self.win.withdraw()
                self.win.attributes("-alpha", 0.0)
            except Exception:
                pass
            return False
        try:
            x = self._safe_int(self.config.get("toast_hud_x"), self.win.winfo_x())
            y = self._safe_int(self.config.get("toast_hud_y"), self.win.winfo_y())
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
            self._startup_pending_visible = False
            self._visible = True
            return True
        except Exception:
            return False

    def hide(self):
        pending = self._startup_pending_visible
        self._startup_pending_visible = False
        try:
            self.win.withdraw()
        except Exception:
            return False
        changed = self._visible or pending
        self._visible = False
        return bool(changed)

    def release_startup_visibility(self):
        if not self._startup_pending_visible or not self._toasts:
            self._startup_pending_visible = False
            return False
        return self._show()

    def push(self, title, message="", severity="info", duration_s=6.0, icon=None,
             kind="notice", meta=None):
        """Queue a new toast. Oldest is dropped if the stack is already full."""
        now = time.time()
        toast = {
            "id": self._next_id,
            "title": str(title or ""),
            "message": str(message or ""),
            "icon": str(icon or ""),
            "severity": severity if severity in _SEVERITIES else "info",
            "kind": "achievement" if str(kind) == "achievement" else "notice",
            "meta": dict(meta or {}),
            "created_at": now,
            "expire_at": now + max(2.0, float(duration_s or 6.0)),
        }
        self._next_id += 1
        self._toasts.append(toast)
        if len(self._toasts) > _MAX_STACK:
            self._toasts = self._toasts[-_MAX_STACK:]
        self._html_revision += 1
        self._redraw()
        self._ensure_tick()
        self._show()

    def dismiss(self, title=None, title_prefix=None):
        """Dismiss matching stale notifications without clearing the stack."""
        exact = str(title or "").casefold()
        prefix = str(title_prefix or "").casefold()
        if not exact and not prefix:
            return 0
        before = len(self._toasts)
        self._toasts = [
            toast for toast in self._toasts
            if not (
                (exact and str(toast.get("title") or "").casefold() == exact)
                or (prefix and str(toast.get("title") or "").casefold().startswith(prefix))
            )
        ]
        removed = before - len(self._toasts)
        if not removed:
            return 0
        self._html_revision += 1
        self._redraw()
        if not self._toasts:
            if self._tick_job is not None:
                try:
                    self.win.after_cancel(self._tick_job)
                except Exception:
                    pass
                self._tick_job = None
            try:
                self.hide()
            except Exception:
                pass
        return removed

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
            self._html_revision += 1
            self._redraw()
        if self._toasts:
            self._tick_job = self.win.after(300, self._tick)
        else:
            try:
                self.hide()
            except Exception:
                pass

    # ── Drag-to-move ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    def _drag_end(self, event):
        self.config["toast_hud_x"] = self.win.winfo_x()
        self.config["toast_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────

    def _text(self, x, y, text, fill, font, anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    @staticmethod
    def _truncate(text, max_chars):
        text = str(text or "")
        return text if len(text) <= max_chars else text[:max_chars - 1] + "…"

    def _redraw(self):
        w = WIDTH
        palette = self._palette
        severity_colors = {
            "info": palette["accent"],
            "warn": palette["orange"],
            "fail": palette["red"],
            "success": palette["green"],
        }
        heights = [self.toast_height(toast) for toast in self._toasts]
        h = max(1, sum(heights) + max(0, len(heights) - 1) * _GAP)
        self.canvas.config(width=w, height=h)
        self.win.geometry(f"{w}x{h}")
        self.canvas.delete("all")

        y = 0
        for toast in self._toasts:
            toast_h = self.toast_height(toast)
            achievement = toast.get("kind") == "achievement"
            color = palette["yellow"] if achievement else severity_colors[toast["severity"]]
            fill = palette["panel"] if achievement else "#010101"
            self.canvas.create_rectangle(0, y, w, y + toast_h, fill=fill, outline="")
            self.canvas.create_rectangle(0, y, 5, y + toast_h, fill=color, outline="")
            self.canvas.create_rectangle(5, y, w, y + toast_h, outline=color, width=1)
            if toast.get("icon"):
                self._text(
                    36 if achievement else _ICON_X,
                    y + (toast_h // 2),
                    toast["icon"],
                    color if achievement else palette["text"],
                    ("Segoe UI Emoji", 24 if achievement else 20),
                    anchor="center",
                )
            text_x = 70 if achievement else _TEXT_X
            self._text(
                text_x,
                y + (22 if achievement else 20),
                self._truncate(toast["title"], _TITLE_CHARS),
                color,
                ("Courier", 10, "bold"),
            )
            if toast["message"]:
                self._text(
                    text_x,
                    y + (49 if achievement else 43),
                    self._truncate(toast["message"], _MESSAGE_CHARS),
                    palette["text"],
                    ("Courier", 9),
                )
            if achievement:
                points = self._safe_int((toast.get("meta") or {}).get("points"), 0) or 0
                self._text(
                    WIDTH - 16, y + 22, f"+{points:,} PTS",
                    color, ("Courier", 9, "bold"), anchor="e",
                )
                category = str((toast.get("meta") or {}).get("category") or "COMMANDER MILESTONE")
                self._text(
                    text_x, y + 73, self._truncate(category.upper(), 38),
                    palette["muted"], ("Courier", 8, "bold"),
                )
            y += toast_h + _GAP

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._html_revision += 1
        if self._toasts:
            self._redraw()
