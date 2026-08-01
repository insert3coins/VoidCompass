"""Compact live route telemetry overlay for Trade Assist."""

from __future__ import annotations

import tkinter as tk

from config import save_config
import overlay_chrome
import themes


class TradeHUD:
    WIDTH = 380
    HEIGHT = 250

    def __init__(self, root, config, state_provider):
        self.config = config
        self.state_provider = state_provider
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._state = {}
        self._last_signature = None
        self._tick_job = None
        self._topmost_job = None
        self._save_job = None

        self.win = tk.Toplevel(root)
        overlay_bg = overlay_chrome.configure_overlay_window(self.win, "#ff00ff")
        self.canvas = tk.Canvas(
            self.win, width=self.WIDTH, height=self.HEIGHT,
            bg=overlay_bg, highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.save_final_pos)

        x = self._safe_int(config.get("trade_hud_x"), 820)
        y = self._safe_int(config.get("trade_hud_y"), 560)
        self._desired_pos = (x, y)
        self.win.geometry(overlay_chrome.position_geometry(x, y, self.WIDTH, self.HEIGHT))
        self.win.after(0, self._apply_initial_position)
        self.win.after(250, self._apply_initial_position)
        self.win.after(700, self._apply_initial_position)
        self._force_topmost()
        self.update(force=True)
        self._schedule_tick()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return int(default)

    def _apply_initial_position(self):
        try:
            x, y = self._desired_pos
            self.win.geometry(
                overlay_chrome.position_geometry(x, y, self.WIDTH, self.HEIGHT)
            )
        except (AttributeError, tk.TclError):
            pass

    def _force_topmost(self):
        self._topmost_job = None
        try:
            if not self.win.winfo_exists():
                return
            self.win.attributes("-topmost", True)
            refresh_ms = max(
                2000, int(self.config.get("overlay_topmost_refresh_ms", 12000) or 12000),
            )
            self._topmost_job = self.win.after(refresh_ms, self._force_topmost)
        except (AttributeError, tk.TclError, TypeError, ValueError):
            pass

    def _schedule_tick(self):
        try:
            if self.win.winfo_exists():
                self._tick_job = self.win.after(750, self._tick)
        except (AttributeError, tk.TclError):
            self._tick_job = None

    def _tick(self):
        self._tick_job = None
        self.update()
        self._schedule_tick()

    def start_move(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def do_move(self, event):
        x = self.win.winfo_x() + event.x - self._drag_x
        y = self.win.winfo_y() + event.y - self._drag_y
        self._desired_pos = (x, y)
        self.config["trade_hud_x"], self.config["trade_hud_y"] = x, y
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self._schedule_save()

    def save_final_pos(self, _event=None):
        try:
            x, y = self.win.winfo_x(), self.win.winfo_y()
            self._desired_pos = (x, y)
            self.config["trade_hud_x"], self.config["trade_hud_y"] = x, y
            self._flush_save()
        except (AttributeError, tk.TclError):
            pass

    def _schedule_save(self):
        if self._save_job is not None:
            try:
                self.win.after_cancel(self._save_job)
            except tk.TclError:
                pass
        self._save_job = self.win.after(250, self._flush_save)

    def _flush_save(self):
        self._save_job = None
        try:
            save_config(self.config)
        except Exception:
            pass

    @staticmethod
    def _truncate(value, limit):
        text = str(value or "---")
        return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"

    @staticmethod
    def _credits(value):
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return "---"
        sign = "-" if number < 0 else ""
        number = abs(number)
        for suffix, divisor in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
            if number >= divisor:
                return f"{sign}{number / divisor:.1f}{suffix} CR"
        return f"{sign}{number:,} CR"

    def _text(self, x, y, text, fill, font=("Courier", 9), anchor="w"):
        font = overlay_chrome.scaled_font(font, self.config)
        self.canvas.create_text(
            x + 1, y + 1, text=text, fill="black", font=font, anchor=anchor,
        )
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)

    def update(self, force=False):
        try:
            state = dict(self.state_provider() or {})
        except Exception:
            state = {}
        signature = repr(state)
        if not force and signature == self._last_signature:
            return
        self._last_signature = signature
        self._state = state
        self._draw()

    def _draw(self):
        state = self._state
        plan = dict(state.get("plan") or {})
        palette = self._palette
        self.canvas.delete("all")
        overlay_chrome.draw_chrome(
            self.canvas, self.WIDTH, self.HEIGHT, accent=palette["accent"],
            scanlines=False,
        )
        self.canvas.create_line(
            16, 45, self.WIDTH - 16, 45,
            fill=palette["border_soft"], width=1,
        )
        self._text(16, 21, "TRADE ROUTE", palette["accent"], ("Courier", 10, "bold"))
        route_type = "ROUND TRIP" if plan.get("kind") == "round-trip" else "ONE WAY"
        self._text(
            self.WIDTH - 16, 21, route_type if plan else "STANDBY",
            palette["orange"] if plan else palette["dim"],
            ("Courier", 9, "bold"), "e",
        )

        if not plan:
            self._text(
                self.WIDTH // 2, 102, "[ NO ACTIVE TRADE PLAN ]",
                palette["dim"], ("Courier", 10, "bold"), "center",
            )
            self._text(
                self.WIDTH // 2, 126,
                "Choose a Trade Assist result to begin tracking",
                palette["muted"], ("Courier", 8), "center",
            )
            self._draw_footer(state, palette)
            return

        stage = str(state.get("stage") or "ROUTE READY").upper()
        self._text(16, 63, stage, palette["green"], ("Courier", 10, "bold"))
        confidence = str(plan.get("confidence") or "?").upper()
        eta = self._duration(plan.get("estimated_seconds"))
        self._text(
            self.WIDTH - 16, 63, f"{confidence} · {eta}", palette["muted"],
            ("Courier", 8), "e",
        )

        source = plan.get("from_station") or plan.get("from_system") or "---"
        destination = plan.get("to_station") or plan.get("to_system") or "---"
        self._text(16, 87, "FROM", palette["dim"], ("Courier", 7, "bold"))
        self._text(58, 87, self._truncate(source, 36), palette["text"], ("Courier", 9, "bold"))
        self._text(16, 107, "TO", palette["dim"], ("Courier", 7, "bold"))
        self._text(58, 107, self._truncate(destination, 36), palette["text"], ("Courier", 9, "bold"))

        units = int(plan.get("units") or 0)
        outbound = self._truncate(plan.get("commodity") or "Commodity", 25)
        self._text(16, 134, "OUT", palette["orange"], ("Courier", 7, "bold"))
        self._text(58, 134, f"{units:,} t  {outbound}", palette["text"], ("Courier", 9))
        if plan.get("return_commodity"):
            return_units = int(plan.get("return_units") or 0)
            return_name = self._truncate(plan.get("return_commodity"), 24)
            self._text(16, 154, "BACK", palette["orange"], ("Courier", 7, "bold"))
            self._text(
                58, 154, f"{return_units:,} t  {return_name}",
                palette["text"], ("Courier", 9),
            )

        stage_index = max(0, min(4, int(state.get("stage_index") or 0)))
        markers = " ".join("◆" if index < stage_index else "◇" for index in range(4))
        self._text(16, 181, markers, palette["accent"], ("Segoe UI Symbol", 10, "bold"))
        self._text(
            self.WIDTH - 16, 181,
            f"{int(state.get('transactions') or 0)} JOURNAL TRADE(S)",
            palette["dim"], ("Courier", 7, "bold"), "e",
        )
        self._text(16, 205, "EXPECTED", palette["dim"], ("Courier", 7, "bold"))
        self._text(
            79, 205, self._credits(plan.get("profit_cr")),
            palette["orange"], ("Courier", 9, "bold"),
        )
        self._text(206, 205, "REALIZED", palette["dim"], ("Courier", 7, "bold"))
        realized = int(state.get("realized_profit") or 0)
        self._text(
            self.WIDTH - 16, 205, self._credits(realized),
            palette["green"] if realized >= 0 else palette["red"],
            ("Courier", 9, "bold"), "e",
        )
        self._draw_footer(state, palette)

    @staticmethod
    def _duration(seconds):
        try:
            seconds = max(0, int(seconds or 0))
        except (TypeError, ValueError):
            return "?"
        if not seconds:
            return "?"
        minutes = max(1, round(seconds / 60))
        return f"{minutes} MIN" if minutes < 60 else f"{minutes / 60:.1f} HR"

    def _draw_footer(self, state, palette):
        location = self._truncate(state.get("current_station") or state.get("current_system"), 24)
        cargo = int(state.get("cargo_tons") or 0)
        capacity = int(state.get("cargo_capacity") or 0)
        cargo_text = f"HOLD {cargo:,}/{capacity:,} T" if capacity else f"HOLD {cargo:,}/? T"
        self._text(16, 232, location, palette["muted"], ("Courier", 8))
        self._text(
            self.WIDTH - 16, 232, cargo_text,
            palette["muted"], ("Courier", 8), "e",
        )

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)
        self._last_signature = None
        self.update(force=True)

    def destroy(self):
        for job in (self._tick_job, self._topmost_job, self._save_job):
            if job is not None:
                try:
                    self.win.after_cancel(job)
                except (AttributeError, tk.TclError):
                    pass
        self._tick_job = self._topmost_job = self._save_job = None
        try:
            self.win.destroy()
        except (AttributeError, tk.TclError):
            pass
