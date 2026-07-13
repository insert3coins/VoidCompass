"""HeartbeatHUD — tiny always-on corner pulse confirming the status/journal
watcher is alive, modeled on SrvSurvey's PlotPulse (bottom-left corner icon
that flashes on every journal write).

Rather than pulsing strictly on journal-file writes (which can go quiet for
long stretches during uneventful supercruise), this ties into the highest
-frequency reliable signal already flowing through the app: every processed
Status.json update (dashboard_scan_mixin.py's _apply_status_update). If no
pulse arrives for a while, the dot itself turns red as a stall indicator —
a small visual complement to the app's existing freeze-diagnostics work.

Deliberately skips the shared tri-line/bracket chrome (overlay_chrome.py) —
at ~34px across there's no room for it to read as anything but noise, same
reasoning that kept toast_hud.py's compact notification cards plain.
"""

import time
import tkinter as tk
from config import COLOR_ACCENT, save_config

_CHROMA = "#ff00ff"
_SIZE = 34
_STALL_COLOR = "#ff5a5a"
_AI_COLOR = "#c084fc"
_STALL_AFTER_S = 15
_MAX_GROWTH = 6
_AI_MAX_GROWTH = 8
_AI_HOLD_S = 2.0


class HeartbeatHUD:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._pulse_level = 0
        self._pulse_kind = "journal"
        self._special_until = 0.0
        self._last_pulse_ts = time.time()
        self._tick_job = None
        self._last_render_key = None

        self.win = tk.Toplevel(root)
        self.win.attributes("-topmost", True, "-transparentcolor", _CHROMA, "-toolwindow", True)
        self.win.overrideredirect(True)
        self.win.config(bg=_CHROMA)

        self.canvas = tk.Canvas(self.win, width=_SIZE, height=_SIZE, bg=_CHROMA, highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        screen_h = root.winfo_screenheight()
        x = self._safe_int(config.get("heartbeat_hud_x"), 12)
        y = self._safe_int(config.get("heartbeat_hud_y"), max(12, screen_h - _SIZE - 12))
        self.win.geometry(f"+{x}+{y}")

        self._force_topmost()
        self._redraw()
        self._schedule_tick()

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

    def destroy(self):
        if self._tick_job:
            try:
                self.win.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None
        try:
            self.win.destroy()
        except Exception:
            pass

    def _schedule_tick(self, delay_ms=None):
        delay_ms = 150 if self._pulse_level > 0 else 750 if delay_ms is None else delay_ms
        self._tick_job = self.win.after(delay_ms, self._tick)

    def _tick(self):
        if self._pulse_level > 0:
            self._pulse_level -= 1
        if self._pulse_kind == "ai" and time.monotonic() >= self._special_until:
            self._pulse_kind = "journal"
        render_key = (
            self._pulse_level,
            (time.time() - self._last_pulse_ts) > _STALL_AFTER_S,
            self._pulse_kind,
        )
        if render_key != self._last_render_key:
            self._redraw()
        self._schedule_tick()

    # ── Data interface ───────────────────────────────────────────────────

    def pulse(self, kind="journal"):
        """Flash for stream activity; AI work gets a brief distinct violet pulse."""
        now = time.monotonic()
        if str(kind).casefold() == "ai":
            self._pulse_kind = "ai"
            self._special_until = now + _AI_HOLD_S
            self._pulse_level = _AI_MAX_GROWTH
        elif self._pulse_kind == "ai" and now < self._special_until:
            # Frequent Status.json writes must not immediately hide AI activity.
            self._pulse_level = max(self._pulse_level, _AI_MAX_GROWTH)
        else:
            self._pulse_kind = "journal"
            self._pulse_level = _MAX_GROWTH
        self._last_pulse_ts = time.time()
        if self._last_render_key != (self._pulse_level, False, self._pulse_kind):
            self._redraw()

    # ── Drag-to-move ─────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.win.winfo_x() + (event.x - self._dx)
        y = self.win.winfo_y() + (event.y - self._dy)
        self.win.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        self.config["heartbeat_hud_x"] = self.win.winfo_x()
        self.config["heartbeat_hud_y"] = self.win.winfo_y()
        try:
            save_config(self.config)
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────

    def _redraw(self):
        self.canvas.delete("all")
        cx = cy = _SIZE // 2
        stalled = (time.time() - self._last_pulse_ts) > _STALL_AFTER_S
        pulse_kind = getattr(self, "_pulse_kind", "journal")
        self._last_render_key = (self._pulse_level, stalled, pulse_kind)
        color = _STALL_COLOR if stalled else _AI_COLOR if pulse_kind == "ai" else COLOR_ACCENT
        base_r = 5
        r = base_r if stalled else base_r + self._pulse_level
        self.canvas.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2, outline=color, width=1)
        self.canvas.create_oval(cx - base_r, cy - base_r, cx + base_r, cy + base_r, outline=color, width=2, fill="#010101")
        if not stalled and self._pulse_level > 0:
            self.canvas.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=color, outline="")
            if pulse_kind == "ai":
                self.canvas.create_rectangle(cx - 4, cy - 4, cx + 4, cy + 4, outline=color, width=1)
