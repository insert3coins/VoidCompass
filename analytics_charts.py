"""Small dependency-free Tk charts for exploration analytics."""

from __future__ import annotations

import math
import tkinter as tk

from ui_theme import THEME


class _AnalyticsChart(tk.Canvas):
    """Theme-aware Canvas chart with resize redraw and an in-canvas tooltip."""

    def __init__(self, parent, *, height=220, empty_text="No exploration history yet."):
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
        nearest = min(
            range(len(self._screen)),
            key=lambda index: abs(self._screen[index][0] - event.x),
        )
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
        box_width = min(width - 18, max(190, len(text) * 6.4 + 18))
        left = max(9, min(width - box_width - 9, x + 12))
        top = max(7, y - 34)
        self.create_rectangle(
            left, top, left + box_width, top + 25,
            fill=THEME.panel_raised, outline=THEME.border, width=1,
        )
        self.create_text(
            left + 9, top + 12, text=text, fill=THEME.text,
            font=("Consolas", 8, "bold"), anchor="w",
        )


class SessionDistanceChart(_AnalyticsChart):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault(
            "empty_text",
            "No completed flight sessions yet — jumps will fill this distance graph.",
        )
        super().__init__(parent, **kwargs)

    def _draw_chart(self, width, height):
        left, right, top, bottom = 56, width - 18, 18, height - 28
        values = [max(0.0, float(row.get("distance") or 0)) for row in self.points]
        high = max(values) or 1.0

        def px(index):
            return left + index / max(1, len(values) - 1) * max(1, right - left)

        def py(value):
            return bottom - value / high * max(1, bottom - top)

        for index in range(3):
            value = high * index / 2
            y = py(value)
            self._grid_line(left, y, right, y)
            self.create_text(
                left - 7, y, text=f"{value:,.0f}", fill=THEME.dim,
                font=("Consolas", 7), anchor="e",
            )
        coords = []
        for index, value in enumerate(values):
            x, y = px(index), py(value)
            coords.extend((x, y))
            self._screen.append((x, y))
        if len(coords) >= 4:
            self.create_polygon(left, bottom, *coords, right, bottom, fill=THEME.selection, outline="")
            self.create_line(*coords, fill=THEME.accent, width=2, joinstyle=tk.ROUND)
        else:
            x, y = self._screen[0]
            self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=THEME.accent, outline="")
        self.create_text(left, height - 8, text=self.points[0].get("label") or "", fill=THEME.dim, font=("Segoe UI", 7), anchor="w")
        self.create_text(right, height - 8, text=self.points[-1].get("label") or "", fill=THEME.dim, font=("Segoe UI", 7), anchor="e")
        if self._hover is not None and self._hover < len(self._screen):
            index = self._hover
            x, y = self._screen[index]
            row = self.points[index]
            self.create_line(x, top, x, bottom, fill=THEME.muted, dash=(3, 3))
            self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=THEME.orange, outline=THEME.text)
            self._tooltip(
                width,
                f"{row.get('label') or 'Session'} · {values[index]:,.1f} ly · {int(row.get('jumps') or 0):,} jumps",
                x, y,
            )


class SurveyActivityChart(_AnalyticsChart):
    SERIES = (
        ("fss", "FSS", "accent"),
        ("dss", "DSS", "orange"),
        ("bio", "BIO", "green"),
    )

    def __init__(self, parent, **kwargs):
        kwargs.setdefault(
            "empty_text",
            "No survey activity recorded yet — FSS, DSS and biology will appear here.",
        )
        super().__init__(parent, **kwargs)

    def _draw_chart(self, width, height):
        left, right, top, bottom = 46, width - 16, 18, height - 28
        totals = [
            sum(max(0, int(row.get(key) or 0)) for key, _label, _colour in self.SERIES)
            for row in self.points
        ]
        high = max(totals) or 1
        step = max(1.0, (right - left) / max(1, len(self.points)))
        bar_width = max(2.0, step - min(5.0, step * 0.25))
        for grid_index in range(3):
            value = high * grid_index / 2
            y = bottom - value / high * (bottom - top)
            self._grid_line(left, y, right, y)
            self.create_text(left - 7, y, text=f"{value:,.0f}", fill=THEME.dim, font=("Consolas", 7), anchor="e")
        for index, row in enumerate(self.points):
            x1 = left + index * step + (step - bar_width) / 2
            x2 = x1 + bar_width
            y = bottom
            for key, _label, colour_name in self.SERIES:
                value = max(0, int(row.get(key) or 0))
                if not value:
                    continue
                segment = value / high * (bottom - top)
                next_y = y - segment
                self.create_rectangle(x1, next_y, x2, y, fill=getattr(THEME, colour_name), outline="")
                y = next_y
            if math.isclose(y, bottom):
                y -= 1
            self._screen.append((x1 + bar_width / 2, y))
        self.create_text(left, height - 8, text=self.points[0].get("label") or "", fill=THEME.dim, font=("Segoe UI", 7), anchor="w")
        self.create_text(right, height - 8, text=self.points[-1].get("label") or "", fill=THEME.dim, font=("Segoe UI", 7), anchor="e")
        legend = "  ".join(label for _key, label, _colour in self.SERIES)
        self.create_text(right, top, text=legend, fill=THEME.muted, font=("Consolas", 7, "bold"), anchor="ne")
        if self._hover is not None and self._hover < len(self._screen):
            index = self._hover
            x, y = self._screen[index]
            row = self.points[index]
            self.create_line(x, top, x, bottom, fill=THEME.muted, dash=(3, 3))
            self._tooltip(
                width,
                f"{row.get('label') or 'Session'} · FSS {int(row.get('fss') or 0)} · DSS {int(row.get('dss') or 0)} · BIO {int(row.get('bio') or 0)}",
                x, y,
            )
