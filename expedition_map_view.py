"""Flat expedition route map used by Explore's Expedition page."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from stellar_types import star_type_label
from ui_theme import THEME, button, configure_ttk


class ExpeditionMapView:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self._map_points = []
        configure_ttk(parent, "ExpeditionMap")
        self._build()

    def _build(self):
        toolbar = tk.Frame(self.parent, bg=THEME.panel)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            toolbar, text="EXPEDITION ROUTE MAP", fg=THEME.orange,
            bg=THEME.panel, font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=8)
        tk.Label(
            toolbar, text="profile-local journal coordinates", fg=THEME.muted,
            bg=THEME.panel, font=("Cascadia Mono", 8),
        ).pack(side=tk.LEFT)
        button(toolbar, "Refresh", self.refresh).pack(side=tk.RIGHT, padx=8, pady=5)
        self.projection = tk.StringVar(value="X / Z")
        combo = ttk.Combobox(
            toolbar, textvariable=self.projection, state="readonly", width=8,
            values=("X / Z", "X / Y", "Y / Z"), style="ExpeditionMap.TCombobox",
        )
        combo.pack(side=tk.RIGHT, padx=(0, 6), pady=5)
        combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        self.summary = tk.Label(
            self.parent, text="", fg=THEME.accent, bg=THEME.bg,
            font=("Cascadia Mono", 9, "bold"), anchor="w",
        )
        self.summary.pack(fill=tk.X, padx=4, pady=(0, 7))
        self.canvas = tk.Canvas(
            self.parent, bg=THEME.inset, highlightthickness=1,
            highlightbackground=THEME.border, bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        self.canvas.bind("<Button-1>", self._click)
        self.detail = tk.Label(
            self.parent, text="Click a plotted system for its journal summary.",
            fg=THEME.muted, bg=THEME.panel, font=("Cascadia Mono", 8),
            anchor="w",
        )
        self.detail.pack(fill=tk.X, pady=(7, 0), ipady=6)

    def refresh(self):
        tracker = getattr(self.app, "deep_survey", None)
        snapshot = tracker.snapshot() if tracker else {}
        all_rows = [
            row for row in snapshot.get("route_points") or []
            if len(row.get("pos") or []) == 3
        ]
        rows = all_rows
        if len(rows) > 1500:
            last = len(rows) - 1
            rows = [rows[round(index * last / 1499)] for index in range(1500)]
        canvas = self.canvas
        canvas.delete("all")
        width = max(200, canvas.winfo_width())
        height = max(160, canvas.winfo_height())
        margin = 36
        axes = {"X / Z": (0, 2), "X / Y": (0, 1), "Y / Z": (1, 2)}[self.projection.get()]
        if not rows:
            canvas.create_text(
                width / 2, height / 2, text="No journal route coordinates recorded yet",
                fill=THEME.muted, font=("Segoe UI", 11),
            )
            self.summary.config(text="0 plotted systems")
            self._map_points = []
            return
        xs = [row["pos"][axes[0]] for row in rows]
        ys = [row["pos"][axes[1]] for row in rows]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        span_x, span_y = max(1.0, max_x - min_x), max(1.0, max_y - min_y)
        scale = min((width - margin * 2) / span_x, (height - margin * 2) / span_y)
        points = []
        for row, x, y in zip(rows, xs, ys):
            px = margin + (x - min_x) * scale
            py = height - margin - (y - min_y) * scale
            points.append((px, py, row))
        if len(points) > 1:
            canvas.create_line(
                *[coordinate for point in points for coordinate in point[:2]],
                fill=THEME.border, width=1,
            )
        for index, (px, py, row) in enumerate(points):
            notable = int(row.get("codex") or 0) + int(row.get("discoveries") or 0)
            colour = THEME.orange if notable else THEME.accent
            radius = 4 if index in (0, len(points) - 1) else 3
            canvas.create_oval(
                px - radius, py - radius, px + radius, py + radius,
                fill=colour, outline="",
            )
        canvas.create_text(
            margin, 14, text=self.projection.get(), fill=THEME.muted,
            anchor="w", font=("Cascadia Mono", 8),
        )
        total_ly = sum(float(row.get("jump_dist") or 0) for row in all_rows)
        unique = len({row.get("system") for row in all_rows})
        representative = (
            f" · {len(rows):,} representative points shown"
            if len(rows) != len(all_rows) else ""
        )
        self.summary.config(
            text=f"{unique:,} systems · {total_ly:,.1f} ly journalled · "
                 f"{len(all_rows):,} arrivals{representative}"
        )
        self._map_points = points

    def _click(self, event):
        if not self._map_points:
            return
        px, py, row = min(
            self._map_points,
            key=lambda point: (point[0] - event.x) ** 2 + (point[1] - event.y) ** 2,
        )
        if (px - event.x) ** 2 + (py - event.y) ** 2 > 400:
            return
        pos = row.get("pos") or [0, 0, 0]
        star = star_type_label(row.get("star_class"), "Unknown")
        self.detail.config(text=(
            f"{row.get('system') or 'Unknown'} · "
            f"{pos[0]:,.2f}, {pos[1]:,.2f}, {pos[2]:,.2f} · "
            f"{float(row.get('jump_dist') or 0):.1f} ly · {star} · "
            f"{int(row.get('codex') or 0)} Codex / "
            f"{int(row.get('screenshots') or 0)} photos"
        ))
