"""Root Commander Analytics workspace with native interactive charts."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import ttk

from analytics_charts import BalanceLineChart, DailyProfitChart, compact_credits
from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from trade import marketdb
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, configure_ttk, scrollbar, window_surface


class AnalyticsWindow(ThemedWindowMixin):
    def __init__(self, root, app, embedded=False):
        self.root = root
        self.app = app
        self.config = app.config
        self.embedded = embedded
        self._request_id = 0
        self._tick_job = None
        self._refresh_job = None
        self.win = window_surface(root, embedded=embedded)
        self.win.title("VOID COMPASS // ANALYTICS")
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

    def _post_ui(self, callback, key=None):
        poster = getattr(self.app, "_ui_post", None)
        if callable(poster):
            return poster(callback, key=key)
        return self.root.after(0, callback)

    def _on_close(self):
        self._request_id += 1
        if self._tick_job is not None:
            try:
                self.win.after_cancel(self._tick_job)
            except Exception:
                pass
        self._tick_job = None
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except Exception:
                pass
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
        tk.Label(title, text="COMMANDER ANALYTICS", fg=COLOR_ACCENT, bg=THEME.header, font=("Bahnschrift SemiCondensed", 16, "bold")).pack(anchor="w")
        tk.Label(title, text="JOURNAL-BACKED PERFORMANCE · LOCAL HISTORY", fg=THEME.muted, bg=THEME.header, font=("Consolas", 8, "bold")).pack(anchor="w")
        shell = tk.Frame(self.win, bg=THEME.bg)
        shell.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        session = self._card(shell, "THIS SESSION", "live flight and trading pace")
        self.session_rate = tk.Label(
            session, text="— / HR", fg=THEME.green, bg=THEME.panel,
            font=("Bahnschrift SemiCondensed", 16, "bold"), anchor="e",
        )
        self.session_rate.pack(side=tk.RIGHT, padx=(14, 0))
        self.session_metrics = self._metric_row(
            session, ("DURATION", "JUMPS", "DISTANCE", "TRADE PROFIT", "TONS SOLD", "TRANSACTIONS"),
        )

        performance = self._card(shell, "TRADING PERFORMANCE", "realised profit from journal market sales")
        controls = tk.Frame(performance, bg=THEME.panel)
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
            performance, ("PROFIT TODAY", "PROFIT 7 DAYS", "PROFIT PERIOD", "TONS SOLD", "BALANCE CHANGE"),
        )

        charts = tk.Frame(shell, bg=THEME.bg)
        charts.pack(fill=tk.BOTH, expand=True)
        charts.grid_columnconfigure(0, weight=1, uniform="analytics")
        charts.grid_columnconfigure(1, weight=1, uniform="analytics")
        balance_body = self._card(charts, "CREDIT BALANCE OVER TIME", grid=(0, 0))
        daily_body = self._card(charts, "DAILY TRADING PROFIT", "green profit · red loss", grid=(0, 1))
        self.balance_chart = BalanceLineChart(balance_body, height=225)
        self.balance_chart.pack(fill=tk.BOTH, expand=True)
        self.daily_chart = DailyProfitChart(daily_body, height=225)
        self.daily_chart.pack(fill=tk.BOTH, expand=True)

        top = self._card(shell, "TOP COMMODITIES BY PROFIT", "selected period")
        wrap = tk.Frame(top, bg=THEME.panel)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.top_tree = ttk.Treeview(
            wrap, columns=("commodity", "tons", "profit"), show="headings",
            height=7, style="Analytics.Treeview",
        )
        for key, label, width, anchor in (
            ("commodity", "Commodity", 280, "w"),
            ("tons", "Tons sold", 120, "e"),
            ("profit", "Profit", 160, "e"),
        ):
            self.top_tree.heading(key, text=label)
            self.top_tree.column(key, width=width, anchor=anchor)
        bar = scrollbar(wrap, orient=tk.VERTICAL, command=self.top_tree.yview, prefix="Analytics")
        self.top_tree.configure(yscrollcommand=bar.set)
        self.top_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(
            shell,
            text="Balance and trade history come from local journal events. Profit uses Elite's average-price-paid sale data; it is not gross revenue.",
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

    def _set_metric(self, mapping, key, text, colour=None):
        label = mapping[key]
        label.config(text=text, fg=colour or COLOR_TEXT)

    def _render_session(self):
        session = getattr(self.app, "trade_session", {}) or {}
        elapsed = max(0, time.time() - float(getattr(self.app, "session_start_ts", time.time()) or time.time()))
        profit = int(session.get("profit") or 0)
        hours = elapsed / 3600
        rate = profit / hours if hours > 0 else 0
        self.session_rate.config(text=f"{compact_credits(rate)} / HR", fg=THEME.green if rate >= 0 else THEME.red)
        values = {
            "DURATION": self._duration(elapsed),
            "JUMPS": f"{int(getattr(self.app, 'session_jump_count', 0) or 0):,}",
            "DISTANCE": self._number(getattr(self.app, "session_ly", 0), " ly"),
            "TRADE PROFIT": compact_credits(profit),
            "TONS SOLD": f"{int(session.get('sold_units') or 0):,} t",
            "TRANSACTIONS": f"{int(session.get('transactions') or 0):,}",
        }
        for key, value in values.items():
            colour = THEME.green if key == "TRADE PROFIT" and profit >= 0 else THEME.red if key == "TRADE PROFIT" else None
            self._set_metric(self.session_metrics, key, value, colour)

    def refresh(self):
        if not self.is_open():
            return
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None
        self._render_session()
        try:
            days = max(1, min(365, int(float(self.days.get() or 30))))
        except (TypeError, ValueError):
            days = 30
        self._request_id += 1
        request_id = self._request_id
        profile = self.config.get("active_commander_profile")
        self.status.config(text="LOADING LOCAL HISTORY…", fg=THEME.muted)

        def worker():
            try:
                data = marketdb.trade_analytics(days, profile_key=profile)
                self._post_ui(
                    lambda: self._render_history(data, days, request_id, profile),
                    key="analytics-history",
                )
            except Exception as exc:
                self._post_ui(
                    lambda: self._render_error(str(exc), request_id, profile),
                    key="analytics-history",
                )

        threading.Thread(target=worker, name="commander-analytics", daemon=True).start()

    def request_refresh(self, delay_ms=250):
        """Coalesce balance and market writes that arrive from one journal event."""
        if not self.is_open():
            return
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except Exception:
                pass
        self._refresh_job = self.win.after(max(0, int(delay_ms)), self.refresh)

    def _request_is_current(self, request_id, profile):
        return (
            self.is_open() and request_id == self._request_id
            and profile == self.config.get("active_commander_profile")
        )

    def _render_error(self, message, request_id, profile):
        if self._request_is_current(request_id, profile):
            self.status.config(text=f"ANALYTICS FAILED · {message}", fg=THEME.red)

    def _render_history(self, data, days, request_id, profile):
        if not self._request_is_current(request_id, profile):
            return
        today = data.get("today") or {}
        week = data.get("week") or {}
        period = data.get("period") or {}
        balance = data.get("balance") or []
        daily = data.get("daily") or []
        delta = int(balance[-1].get("balance") or 0) - int(balance[0].get("balance") or 0) if len(balance) >= 2 else 0
        metrics = {
            "PROFIT TODAY": int(today.get("profit") or 0),
            "PROFIT 7 DAYS": int(week.get("profit") or 0),
            "PROFIT PERIOD": int(period.get("profit") or 0),
            "TONS SOLD": int(period.get("tons") or 0),
            "BALANCE CHANGE": delta,
        }
        for key, value in metrics.items():
            text = f"{value:,} t" if key == "TONS SOLD" else compact_credits(value)
            colour = None if key == "TONS SOLD" else THEME.green if value >= 0 else THEME.red
            self._set_metric(self.period_metrics, key, text, colour)
        self.balance_chart.set_data(balance)
        self.daily_chart.set_data(daily)
        children = self.top_tree.get_children()
        if children:
            self.top_tree.delete(*children)
        for row in data.get("top") or []:
            profit = int(row.get("profit") or 0)
            tag = "profit" if profit >= 0 else "loss"
            self.top_tree.insert("", tk.END, values=(
                row.get("name") or row.get("symbol") or "—",
                f"{int(row.get('tons') or 0):,}", compact_credits(profit),
            ), tags=(tag,))
        self.top_tree.tag_configure("profit", foreground=THEME.green)
        self.top_tree.tag_configure("loss", foreground=THEME.red)
        self.status.config(
            text=f"{days} DAYS · {len(balance):,} BALANCE POINTS · {len(daily):,} TRADING DAYS",
            fg=THEME.muted,
        )
