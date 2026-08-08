"""Profile-aware exploration analytics built from the Captain's Log."""

from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime, timezone
from tkinter import ttk

from analytics_charts import SessionDistanceChart, SurveyActivityChart
from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from ui_theme import (
    THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar,
    window_surface,
)


class AnalyticsWindow(ThemedWindowMixin):
    def __init__(self, root, app, embedded=False):
        self.root = root
        self.app = app
        self.config = app.config
        self.embedded = embedded
        self._tick_job = None
        self._refresh_job = None
        self.win = window_surface(root, embedded=embedded)
        self.win.title("VOID COMPASS // EXPLORATION ANALYTICS")
        self.win.geometry(self.config.get("analytics_geometry", "1100x760"))
        apply_window(self.win)
        configure_ttk(self.win, prefix="Analytics")
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.refresh()

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def _on_close(self):
        for job in (self._tick_job, self._refresh_job):
            if job is not None:
                try:
                    self.win.after_cancel(job)
                except Exception:
                    pass
        self._tick_job = None
        self._refresh_job = None
        try:
            if not self.embedded:
                self.config["analytics_geometry"] = self.win.geometry()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    def on_shown(self):
        self.refresh()
        self._schedule_tick()

    def _schedule_tick(self):
        if self._tick_job is None and self.is_open():
            self._tick_job = self.win.after(1000, self._tick)

    def _tick(self):
        self._tick_job = None
        if not self.is_open():
            return
        if getattr(self.app, "_active_page", None) == "ANALYTICS":
            self._render_session()
            self._schedule_tick()

    def _build(self):
        header = tk.Frame(self.win, bg=THEME.header)
        header.pack(fill=tk.X)
        title = tk.Frame(header, bg=THEME.header)
        title.pack(side=tk.LEFT, padx=14, pady=9)
        tk.Label(
            title, text="EXPLORATION ANALYTICS", fg=COLOR_ACCENT,
            bg=THEME.header, font=("Bahnschrift SemiCondensed", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title, text="PROFILE-AWARE JOURNAL HISTORY · LOCAL ONLY",
            fg=THEME.muted, bg=THEME.header, font=("Consolas", 8, "bold"),
        ).pack(anchor="w")
        shell = tk.Frame(self.win, bg=THEME.bg)
        shell.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        session = self._card(shell, "THIS APP SESSION", "live exploration pace")
        self.session_rate = tk.Label(
            session, text="— LY / HR", fg=THEME.green, bg=THEME.panel,
            font=("Bahnschrift SemiCondensed", 16, "bold"), anchor="e",
        )
        self.session_rate.pack(side=tk.RIGHT, padx=(14, 0))
        self.session_metrics = self._metric_row(
            session, ("DURATION", "JUMPS", "DISTANCE", "SYSTEMS", "FSS SCANS", "BIO ANALYSES"),
        )

        history = self._card(shell, "EXPEDITION HISTORY", "Captain's Log flight sessions")
        controls = tk.Frame(history, bg=THEME.panel)
        controls.pack(fill=tk.X, pady=(0, 7))
        tk.Label(controls, text="PERIOD", fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)
        self.days = ttk.Combobox(
            controls, values=("7", "30", "90", "365"), state="readonly",
            width=7, style="Analytics.TCombobox",
        )
        self.days.set("30")
        self.days.pack(side=tk.LEFT, padx=(7, 5))
        tk.Label(controls, text="DAYS", fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)
        self.days.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        button(controls, "REFRESH", self.refresh, accent=True).pack(side=tk.RIGHT)
        self.status = tk.Label(controls, text="", fg=THEME.muted, bg=THEME.panel, font=("Consolas", 8), anchor="e")
        self.status.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=12)
        self.period_metrics = self._metric_row(
            history, ("FLIGHT SESSIONS", "JUMPS", "DISTANCE", "FSS SURVEYS", "DSS MAPS", "BIO ANALYSES"),
        )

        charts = tk.Frame(shell, bg=THEME.bg)
        charts.pack(fill=tk.BOTH, expand=True)
        charts.grid_columnconfigure(0, weight=1, uniform="analytics")
        charts.grid_columnconfigure(1, weight=1, uniform="analytics")
        distance_body = self._card(charts, "DISTANCE BY SESSION", "light years travelled", grid=(0, 0))
        survey_body = self._card(charts, "SURVEY ACTIVITY", "FSS · DSS · biological analyses", grid=(0, 1))
        self.distance_chart = SessionDistanceChart(distance_body, height=225)
        self.distance_chart.pack(fill=tk.BOTH, expand=True)
        self.survey_chart = SurveyActivityChart(survey_body, height=225)
        self.survey_chart.pack(fill=tk.BOTH, expand=True)

        recent = self._card(shell, "RECENT FLIGHT SESSIONS", "newest first")
        wrap = tk.Frame(recent, bg=THEME.panel)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.session_tree = ttk.Treeview(
            wrap, columns=("date", "route", "jumps", "distance", "fss", "dss", "bio"),
            show="headings", height=7, style="Analytics.Treeview",
        )
        for key, label, width, anchor in (
            ("date", "Started", 115, "w"), ("route", "Route", 270, "w"),
            ("jumps", "Jumps", 65, "e"), ("distance", "Distance", 90, "e"),
            ("fss", "FSS", 55, "e"), ("dss", "DSS", 55, "e"),
            ("bio", "Bio", 55, "e"),
        ):
            self.session_tree.heading(key, text=label)
            self.session_tree.column(key, width=width, anchor=anchor)
        bar = scrollbar(wrap, orient=tk.VERTICAL, command=self.session_tree.yview, prefix="Analytics")
        self.session_tree.configure(yscrollcommand=bar.set)
        self.session_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(
            shell,
            text="Analytics are derived from this commander's bounded Captain's Log; no market database or network lookup is used.",
            fg=THEME.dim, bg=THEME.bg, font=("Segoe UI", 8), anchor="w",
        ).pack(fill=tk.X, pady=(0, 5))

    def _card(self, parent, title, subtitle="", grid=None):
        card = tk.Frame(parent, bg=THEME.panel, highlightbackground=THEME.border, highlightthickness=1)
        if grid is None:
            card.pack(fill=tk.X, pady=(0, 9))
        else:
            row, column = grid
            card.grid(row=row, column=column, sticky="nsew", padx=(0, 5) if column == 0 else (5, 0), pady=(0, 9))
        tk.Frame(card, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        heading = tk.Frame(card, bg=THEME.panel)
        heading.pack(fill=tk.X, padx=11, pady=(8, 4))
        tk.Label(heading, text=title, fg=COLOR_ORANGE, bg=THEME.panel, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        if subtitle:
            tk.Label(heading, text=f"  {subtitle}", fg=THEME.muted, bg=THEME.panel, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        body = tk.Frame(card, bg=THEME.panel)
        body.pack(fill=tk.BOTH, expand=True, padx=11, pady=(0, 10))
        return body

    def _metric_row(self, parent, names):
        row = tk.Frame(parent, bg=THEME.panel)
        row.pack(side=tk.LEFT, fill=tk.X, expand=True)
        values = {}
        for name in names:
            tile = tk.Frame(row, bg=THEME.panel_alt, highlightbackground=THEME.border_soft, highlightthickness=1)
            tile.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            tk.Label(tile, text=name, fg=THEME.muted, bg=THEME.panel_alt, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(6, 1))
            values[name] = tk.Label(tile, text="—", fg=COLOR_TEXT, bg=THEME.panel_alt, font=("Consolas", 10, "bold"), anchor="w")
            values[name].pack(fill=tk.X, padx=8, pady=(0, 6))
        return values

    @staticmethod
    def _duration(seconds):
        seconds = max(0, int(seconds or 0))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:d}:{secs:02d}"

    @staticmethod
    def _number(value, suffix=""):
        try:
            return f"{float(value or 0):,.1f}".rstrip("0").rstrip(".") + suffix
        except (TypeError, ValueError):
            return "—"

    @staticmethod
    def _session_epoch(session):
        text = str((session or {}).get("started") or "").strip()
        if not text:
            return 0.0
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OSError):
            return 0.0

    @classmethod
    def _session_label(cls, session):
        timestamp = cls._session_epoch(session)
        if not timestamp:
            return "Unknown"
        return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%d %b")

    def _set_metric(self, mapping, key, text, colour=None):
        mapping[key].config(text=text, fg=colour or COLOR_TEXT)

    def _render_session(self):
        elapsed = max(0, time.time() - float(getattr(self.app, "session_start_ts", time.time()) or time.time()))
        distance = float(getattr(self.app, "session_ly", 0) or 0)
        hours = elapsed / 3600
        self.session_rate.config(text=f"{distance / hours if hours > 0 else 0:,.1f} LY / HR")
        log_sessions = self.app.captains_log.sessions() if getattr(self.app, "captains_log", None) else []
        current = log_sessions[0] if log_sessions and not log_sessions[0].get("ended") else {}
        values = {
            "DURATION": self._duration(elapsed),
            "JUMPS": f"{int(getattr(self.app, 'session_jump_count', 0) or 0):,}",
            "DISTANCE": self._number(distance, " ly"),
            "SYSTEMS": f"{len(getattr(self.app, 'session_systems', None) or ()):,.0f}",
            "FSS SCANS": f"{int(current.get('fss_surveys') or 0):,}",
            "BIO ANALYSES": f"{int(current.get('bio_analyses') or 0):,}",
        }
        for key, value in values.items():
            self._set_metric(self.session_metrics, key, value)

    def refresh(self):
        if not self.is_open():
            return
        self._render_session()
        try:
            days = max(1, min(365, int(float(self.days.get() or 30))))
        except (TypeError, ValueError):
            days = 30
        cutoff = time.time() - days * 86400
        sessions = self.app.captains_log.sessions() if getattr(self.app, "captains_log", None) else []
        selected = [row for row in sessions if self._session_epoch(row) >= cutoff]
        chronological = list(reversed(selected))
        totals = {
            "FLIGHT SESSIONS": len(selected),
            "JUMPS": sum(int(row.get("jumps") or 0) for row in selected),
            "DISTANCE": sum(float(row.get("distance_ly") or 0) for row in selected),
            "FSS SURVEYS": sum(int(row.get("fss_surveys") or 0) for row in selected),
            "DSS MAPS": sum(int(row.get("dss_maps") or 0) for row in selected),
            "BIO ANALYSES": sum(int(row.get("bio_analyses") or 0) for row in selected),
        }
        for key, value in totals.items():
            text = self._number(value, " ly") if key == "DISTANCE" else f"{int(value):,}"
            self._set_metric(self.period_metrics, key, text)
        points = [
            {
                "label": self._session_label(row),
                "distance": float(row.get("distance_ly") or 0),
                "jumps": int(row.get("jumps") or 0),
                "fss": int(row.get("fss_surveys") or 0),
                "dss": int(row.get("dss_maps") or 0),
                "bio": int(row.get("bio_analyses") or 0),
            }
            for row in chronological[-60:]
        ]
        self.distance_chart.set_data(points)
        self.survey_chart.set_data(points)
        children = self.session_tree.get_children()
        if children:
            self.session_tree.delete(*children)
        for row in selected[:80]:
            start = str(row.get("started") or "").replace("T", " ")[:16] or "—"
            origin = row.get("start_system") or "—"
            destination = row.get("end_system") or origin
            route = origin if origin == destination else f"{origin} → {destination}"
            self.session_tree.insert("", tk.END, values=(
                start, route, f"{int(row.get('jumps') or 0):,}",
                f"{float(row.get('distance_ly') or 0):,.1f} ly",
                f"{int(row.get('fss_surveys') or 0):,}",
                f"{int(row.get('dss_maps') or 0):,}",
                f"{int(row.get('bio_analyses') or 0):,}",
            ))
        self.status.config(
            text=f"{days} DAYS · {len(selected):,} FLIGHT SESSION{'S' if len(selected) != 1 else ''}",
            fg=THEME.muted,
        )

    def request_refresh(self, delay_ms=250):
        if not self.is_open():
            return
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except Exception:
                pass
        self._refresh_job = self.win.after(max(0, int(delay_ms)), self._run_requested_refresh)

    def _run_requested_refresh(self):
        self._refresh_job = None
        self.refresh()
