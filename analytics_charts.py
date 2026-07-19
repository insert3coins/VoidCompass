"""Small dependency-free Tk charts used by the native Analytics workspace."""

from __future__ import annotations

import datetime as _dt
import math
import tkinter as tk

from ui_theme import THEME


def compact_credits(value):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if value < 0 else ""
    value = abs(value)
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= divisor:
            number = value / divisor
            precision = 0 if number >= 100 else 1
            return f"{sign}{number:.{precision}f}{suffix} cr"
    return f"{sign}{value:,.0f} cr"


class _AnalyticsChart(tk.Canvas):
    """Theme-aware Canvas chart with resize redraw and an in-canvas tooltip."""

    def __init__(self, parent, *, height=220, empty_text="No analytics recorded yet."):
        super().__init__(
            parent, height=height, bg=THEME.inset, highlightthickness=1,
            highlightbackground=THEME.border_soft, bd=0,
        )
        self.empty_text = empty_text
        self.points = []
        self._screen = []
        self._hover = None
        self._redraw_job = None
        self.bind("<Configure>", self._schedule_redraw, add="+")
        self.bind("<Motion>", self._on_motion, add="+")
        self.bind("<Leave>", self._on_leave, add="+")

    def set_data(self, points):
        self.points = [dict(row) for row in (points or []) if isinstance(row, dict)]
        self._hover = None
        self._schedule_redraw()

    def _schedule_redraw(self, _event=None):
        if self._redraw_job is not None:
            return
        try:
            self._redraw_job = self.after_idle(self._redraw)
        except tk.TclError:
            self._redraw_job = None

    def _redraw(self):
        self._redraw_job = None
        try:
            self.delete("all")
            self._screen = []
            width = max(240, self.winfo_width())
            height = max(120, self.winfo_height())
            if not self.points:
                self.create_text(
                    width / 2, height / 2, text=self.empty_text,
                    fill=THEME.muted, font=("Segoe UI", 9), justify=tk.CENTER,
                )
                return
            self._draw_chart(width, height)
        except tk.TclError:
            return

    def _draw_chart(self, width, height):
        raise NotImplementedError

    def _on_motion(self, event):
        if not self._screen:
            return
        nearest = min(range(len(self._screen)), key=lambda index: abs(self._screen[index][0] - event.x))
        if nearest != self._hover:
            self._hover = nearest
            self._schedule_redraw()

    def _on_leave(self, _event):
        if self._hover is not None:
            self._hover = None
            self._schedule_redraw()

    def _grid_line(self, x1, y1, x2, y2):
        self.create_line(x1, y1, x2, y2, fill=THEME.border_soft, width=1)

    def _tooltip(self, width, text, x, y):
        font = ("Consolas", 8, "bold")
        box_width = min(width - 18, max(190, len(text) * 6.4 + 18))
        left = max(9, min(width - box_width - 9, x + 12))
        top = max(7, y - 34)
        self.create_rectangle(
            left, top, left + box_width, top + 25,
            fill=THEME.panel_raised, outline=THEME.border, width=1,
        )
        self.create_text(left + 9, top + 12, text=text, fill=THEME.text, font=font, anchor="w")


class BalanceLineChart(_AnalyticsChart):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("empty_text", "No balance history yet — journal balance snapshots will fill this graph.")
        super().__init__(parent, **kwargs)

    @staticmethod
    def _date(timestamp):
        try:
            return _dt.datetime.fromtimestamp(float(timestamp)).strftime("%d %b")
        except (TypeError, ValueError, OSError):
            return "—"

    def _draw_chart(self, width, height):
        if len(self.points) < 2:
            self.create_text(
                width / 2, height / 2, text=self.empty_text,
                fill=THEME.muted, font=("Segoe UI", 9), justify=tk.CENTER,
            )
            return
        left, right, top, bottom = 62, width - 76, 18, height - 28
        timestamps = [float(row.get("ts") or 0) for row in self.points]
        balances = [float(row.get("balance") or 0) for row in self.points]
        t0, t1 = min(timestamps), max(timestamps)
        low, high = min(balances), max(balances)
        padding = (high - low) * 0.1 or abs(high) * 0.03 or 1
        low, high = low - padding, high + padding

        def px(value):
            return left + ((value - t0) / max(1, t1 - t0)) * max(1, right - left)

        def py(value):
            return bottom - ((value - low) / max(1, high - low)) * max(1, bottom - top)

        for index in range(3):
            value = low + (high - low) * index / 2
            y = py(value)
            self._grid_line(left, y, right, y)
            self.create_text(left - 8, y, text=compact_credits(value).replace(" cr", ""), fill=THEME.dim, font=("Consolas", 7), anchor="e")
        coords = []
        for timestamp, balance in zip(timestamps, balances):
            x, y = px(timestamp), py(balance)
            coords.extend((x, y))
            self._screen.append((x, y))
        self.create_polygon(
            left, bottom, *coords, right, bottom,
            fill=THEME.selection, outline="",
        )
        self.create_line(*coords, fill=THEME.accent, width=2, joinstyle=tk.ROUND)
        last_x, last_y = self._screen[-1]
        self.create_oval(last_x - 3, last_y - 3, last_x + 3, last_y + 3, fill=THEME.accent, outline="")
        self.create_text(min(width - 4, last_x + 7), last_y - 8, text=compact_credits(balances[-1]), fill=THEME.text, font=("Consolas", 8, "bold"), anchor="se" if last_x > width - 130 else "sw")
        self.create_text(left, height - 8, text=self._date(t0), fill=THEME.dim, font=("Segoe UI", 7), anchor="w")
        self.create_text(right, height - 8, text=self._date(t1), fill=THEME.dim, font=("Segoe UI", 7), anchor="e")
        if self._hover is not None and self._hover < len(self._screen):
            index = self._hover
            x, y = self._screen[index]
            self.create_line(x, top, x, bottom, fill=THEME.muted, dash=(3, 3))
            self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=THEME.orange, outline=THEME.text)
            self._tooltip(width, f"{self._date(timestamps[index])}  ·  {compact_credits(balances[index])}", x, y)


class DailyProfitChart(_AnalyticsChart):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("empty_text", "No trading days recorded yet — completed sales will fill this graph.")
        super().__init__(parent, **kwargs)

    def _draw_chart(self, width, height):
        left, right, top, bottom = 62, width - 16, 18, height - 28
        values = [float(row.get("profit") or 0) for row in self.points]
        high, low = max(0, max(values)), min(0, min(values))
        span = high - low or 1

        def py(value):
            return top + ((high - value) / span) * max(1, bottom - top)

        zero = py(0)
        self._grid_line(left, zero, right, zero)
        self.create_text(left - 8, py(high), text=compact_credits(high).replace(" cr", ""), fill=THEME.dim, font=("Consolas", 7), anchor="e")
        if low < 0:
            self.create_text(left - 8, py(low), text=compact_credits(low).replace(" cr", ""), fill=THEME.dim, font=("Consolas", 7), anchor="e")
        step = max(1, (right - left) / max(1, len(values)))
        bar_width = max(1, step - min(3, step * 0.2))
        for index, (row, value) in enumerate(zip(self.points, values)):
            x = left + index * step + (step - bar_width) / 2
            value_y = py(value)
            y1, y2 = min(zero, value_y), max(zero, value_y)
            if math.isclose(y1, y2):
                y1 -= 1
            colour = THEME.green if value >= 0 else THEME.red
            self.create_rectangle(x, y1, x + bar_width, y2, fill=colour, outline="")
            self._screen.append((x + bar_width / 2, value_y))
        first = str(self.points[0].get("date") or "")
        last = str(self.points[-1].get("date") or "")
        self.create_text(left, height - 8, text=first[5:] if len(first) >= 10 else first, fill=THEME.dim, font=("Segoe UI", 7), anchor="w")
        self.create_text(right, height - 8, text=last[5:] if len(last) >= 10 else last, fill=THEME.dim, font=("Segoe UI", 7), anchor="e")
        if self._hover is not None and self._hover < len(self._screen):
            index = self._hover
            x, y = self._screen[index]
            row = self.points[index]
            self.create_line(x, top, x, bottom, fill=THEME.muted, dash=(3, 3))
            self._tooltip(width, f"{row.get('date') or '—'}  ·  {compact_credits(row.get('profit'))}  ·  {int(row.get('tons') or 0):,} t", x, y)
