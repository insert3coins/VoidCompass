"""Lightweight, journal-aware online trading assistance for VoidCompass.

Ardent lookups run only for requested searches. Opening or closing this page
never controls independent visited-market EDDN uploads.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import tkinter as tk
from tkinter import ttk

from config import save_config
from trade import ardent, eddn_upload, marketdb, routes
from ui_theme import (
    THEME,
    ThemedWindowMixin,
    apply_window,
    button,
    configure_ttk,
    scrollbar,
    window_surface,
)


COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text

RANK_OPTIONS = (
    "Profit / trip",
    "Profit / hour",
    "Shortest travel",
    "Freshest quotes",
)
RESULT_COUNTS = ("3", "10", "25")


class TradeWindow(ThemedWindowMixin):
    """One-page Trade Assist: sell cargo, find one trade, or inspect the run."""

    def __init__(self, root, app, embedded=False):
        self.root = root
        self.app = app
        self.config = app.config
        self.embedded = bool(embedded)
        self._live_poll_after = None
        self._status_refresh_running = False
        self._search_generation = 0
        self._history_loading = False
        self._current_view = "run"
        self._last_session_signature = None
        self._last_cargo_signature = None
        self._cargo_refresh_pending = False
        self.result_rows = {}

        saved = self.config.get("trade_route_form")
        self._saved_filters = saved if isinstance(saved, dict) else {}
        self.large_pad_var = tk.BooleanVar(
            value=bool(self._saved_filters.get("large_pad", False))
        )
        self.include_carriers_var = tk.BooleanVar(
            value=bool(self._saved_filters.get("include_carriers", False))
        )
        self.orbital_only_var = tk.BooleanVar(
            value=bool(self._saved_filters.get("orbital_only", False))
        )
        self.full_load_var = tk.BooleanVar(
            value=bool(self._saved_filters.get("full_load", False))
        )
        self.round_trip_var = tk.BooleanVar(
            value=bool(self._saved_filters.get("round_trip", False))
        )
        saved_rank = str(self._saved_filters.get("rank", RANK_OPTIONS[0]))
        self.rank_var = tk.StringVar(
            value=saved_rank if saved_rank in RANK_OPTIONS else RANK_OPTIONS[0]
        )
        saved_count = str(self._saved_filters.get("result_count", RESULT_COUNTS[0]))
        self.result_count_var = tk.StringVar(
            value=saved_count if saved_count in RESULT_COUNTS else RESULT_COUNTS[0]
        )
        self.eddn_upload_var = tk.BooleanVar(
            value=bool(self.config.get("trade_eddn_upload_enabled", True))
        )
        self.trade_log_auto_prune_var = tk.BooleanVar(
            value=bool(self.config.get("trade_log_auto_prune_enabled", True))
        )
        saved_retention = str(self.config.get("trade_log_retention_days", 180))
        self.trade_log_retention_var = tk.StringVar(
            value=saved_retention if saved_retention in ("30", "90", "180", "365") else "180"
        )

        self.win = window_surface(root, embedded=self.embedded)
        self.win.title("Trade Assist")
        self.win.geometry(self.config.get("trade_window_geometry", "1080x700"))
        self.win.minsize(900, 560)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        apply_window(self.win)

        self._build()
        self._load_filter_values()
        self._start_market_services()
        self._refresh_summary()
        self.show_current_run()
        self.refresh_status()
        self._schedule_live_poll()

    # ------------------------------------------------------------------
    # Window and shared UI
    # ------------------------------------------------------------------

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        self.win.lift()
        self.win.focus_force()

    def on_shown(self):
        self._refresh_summary()
        self.refresh_session()
        if self._current_view == "log":
            self.refresh_trade_log()
        if self._cargo_refresh_pending and self._current_view == "cargo":
            self._cargo_refresh_pending = False
            self.find_cargo_buyers()
        self.refresh_status()
        self._schedule_live_poll()

    def _post_ui(self, callback, key=None):
        poster = getattr(self.app, "_ui_post", None)
        if callable(poster):
            return poster(callback, key=key)
        return self.root.after(0, callback)

    def _is_active_view(self):
        return not self.embedded or getattr(self.app, "_active_page", None) == "TRADE"

    def _build(self):
        style = configure_ttk(self.win, "TradeAssist")
        style.configure(
            "TradeAssist.Treeview",
            background=THEME.input,
            foreground=COLOR_TEXT,
            fieldbackground=THEME.input,
            rowheight=25,
            borderwidth=0,
        )
        style.configure(
            "TradeAssist.Treeview.Heading",
            background=self.UI_PANEL_2,
            foreground=COLOR_ORANGE,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "TradeAssist.Treeview",
            background=[("selected", THEME.selection)],
            foreground=[("selected", COLOR_TEXT)],
        )
        style.configure(
            "TradeAssist.Horizontal.TProgressbar",
            background=COLOR_ACCENT,
            troughcolor=self.UI_BG,
            bordercolor=self.UI_BG,
            lightcolor=COLOR_ACCENT,
            darkcolor=COLOR_ACCENT,
            thickness=8,
        )

        header = tk.Frame(self.win, bg=THEME.header, height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        titles = tk.Frame(header, bg=THEME.header)
        titles.pack(side=tk.LEFT, fill=tk.Y, padx=14)
        tk.Label(
            titles, text="TRADE ASSIST", fg=COLOR_ACCENT, bg=THEME.header,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(9, 0))
        self.subtitle = tk.Label(
            titles,
            text="One useful decision at a time · online prices only when requested",
            fg=self.UI_MUTED, bg=THEME.header, font=("Consolas", 8),
        )
        self.subtitle.pack(anchor="w", pady=(2, 0))
        self.db_badge = tk.Label(
            header, text="ONLINE CHECKING", fg="black", bg=self.UI_DIM,
            font=("Segoe UI", 8, "bold"), padx=10, pady=4,
        )
        self.db_badge.pack(side=tk.RIGHT, padx=14)

        self.banner = tk.Label(
            self.win, text="", bg=THEME.selection, fg=self.UI_WARN,
            font=("Segoe UI", 9), anchor="w", padx=14, pady=6,
        )

        self.summary = tk.Frame(
            self.win, bg=self.UI_PANEL,
            highlightbackground=self.UI_BORDER, highlightthickness=1,
        )
        self.summary.pack(fill=tk.X, padx=10, pady=(10, 0))
        tk.Frame(self.summary, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        summary_inner = tk.Frame(self.summary, bg=self.UI_PANEL)
        summary_inner.pack(fill=tk.X, padx=12, pady=9)
        self.system_value = self._summary_stat(summary_inner, "LOCATION", "---", COLOR_ACCENT)
        self.credits_value = self._summary_stat(summary_inner, "CREDITS", "---", COLOR_ORANGE)
        self.cargo_value = self._summary_stat(summary_inner, "CARGO", "---", COLOR_TEXT)
        self.profit_value = self._summary_stat(summary_inner, "RUN PROFIT", "---", self.UI_OK)
        self.plan_value = self._summary_stat(summary_inner, "ACTIVE PLAN", "NONE", COLOR_TEXT)

        action_row = tk.Frame(self.win, bg=self.UI_BG)
        action_row.pack(fill=tk.X, padx=10, pady=(9, 0))
        for column in range(4):
            action_row.grid_columnconfigure(column, weight=1, uniform="trade-actions")
        self._action_card(
            action_row, 0, "SELL MY CARGO",
            "Find buyers around the selected start system for cargo aboard.",
            self.find_cargo_buyers, self.UI_OK, "FIND BUYERS",
        )
        self._action_card(
            action_row, 1, "FIND A TRADE",
            "Plan from the selected station with an empty or available hold.",
            self.find_trade, COLOR_ACCENT, "FIND NOW",
        )
        self._action_card(
            action_row, 2, "CURRENT RUN",
            "Review the active destination, transactions and real profit.",
            self.show_current_run, COLOR_ORANGE, "OPEN",
        )
        self._action_card(
            action_row, 3, "TRADE LOG",
            "Review profile-local journal buys, sales and route context.",
            self.show_trade_log, self.UI_MUTED, "HISTORY",
        )

        self._build_origin()
        self._build_filters()
        self._build_results()
        self._build_market_link()

    def _summary_stat(self, parent, label, value, colour):
        box = tk.Frame(parent, bg=self.UI_PANEL)
        box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 18))
        tk.Label(
            box, text=label, fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=("Segoe UI", 7, "bold"),
        ).pack(anchor="w")
        widget = tk.Label(
            box, text=value, fg=colour, bg=self.UI_PANEL,
            font=("Segoe UI", 11, "bold"), anchor="w",
        )
        widget.pack(fill=tk.X)
        return widget

    def _action_card(self, parent, column, title, description, command, colour, action_text="GO"):
        card = tk.Frame(
            parent, bg=self.UI_PANEL,
            highlightbackground=self.UI_BORDER, highlightthickness=1,
        )
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0))
        tk.Frame(card, bg=colour, height=3).pack(fill=tk.X)
        tk.Label(
            card, text=title, fg=colour, bg=self.UI_PANEL,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=11, pady=(9, 2))
        tk.Label(
            card, text=description, fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=("Segoe UI", 8), anchor="w", justify=tk.LEFT, wraplength=215,
        ).pack(fill=tk.X, padx=11)
        button(card, action_text, command, accent=(column == 0)).pack(
            anchor="w", padx=11, pady=(8, 10)
        )

    def _build_origin(self):
        panel = tk.Frame(
            self.win, bg=self.UI_PANEL,
            highlightbackground=self.UI_BORDER, highlightthickness=1,
        )
        panel.pack(fill=tk.X, padx=10, pady=(9, 0))
        tk.Label(
            panel, text="START FROM", fg=COLOR_ORANGE, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(11, 10), pady=9)
        self.origin_entries = {}
        for key, label, width in (
            ("origin_system", "SYSTEM", 27),
            ("origin_station", "STATION · BLANK = AUTO", 30),
        ):
            box = tk.Frame(panel, bg=self.UI_PANEL)
            box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 9), pady=5)
            tk.Label(
                box, text=label, fg=self.UI_DIM, bg=self.UI_PANEL,
                font=("Segoe UI", 6, "bold"),
            ).pack(anchor="w")
            entry = tk.Entry(
                box, width=width, bg=self.UI_PANEL_2, fg=COLOR_TEXT,
                insertbackground=COLOR_ACCENT, relief=tk.FLAT,
                highlightthickness=1, highlightbackground=self.UI_BORDER,
                highlightcolor=COLOR_ACCENT,
            )
            entry.pack(fill=tk.X)
            entry.bind("<FocusOut>", lambda _event: self._save_filters())
            entry.bind("<Return>", lambda _event: self.find_trade())
            self.origin_entries[key] = entry
        button(panel, "USE CURRENT", self._use_current_origin).pack(
            side=tk.LEFT, padx=(0, 6), pady=(13, 5),
        )
        button(panel, "FIND NOW", self.find_trade, accent=True).pack(
            side=tk.LEFT, padx=(0, 9), pady=(13, 5),
        )

    def _build_filters(self):
        panel = tk.Frame(
            self.win, bg=self.UI_PANEL,
            highlightbackground=self.UI_BORDER, highlightthickness=1,
        )
        panel.pack(fill=tk.X, padx=10, pady=(9, 0))
        top = tk.Frame(panel, bg=self.UI_PANEL)
        top.pack(fill=tk.X, padx=10, pady=(4, 0))
        tk.Label(
            top, text="QUICK FILTERS", fg=COLOR_ORANGE, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8), pady=8)
        self.filter_entries = {}
        for key, label, width in (
            ("radius", "RANGE LY", 7),
            ("max_ls", "MAX ARRIVAL LS", 9),
            ("age", "AGE DAYS", 7),
            ("min_profit", "MIN CR/T", 8),
            ("cargo_override", "LOAD T · AUTO", 8),
        ):
            box = tk.Frame(top, bg=self.UI_PANEL)
            box.pack(side=tk.LEFT, padx=(0, 8), pady=5)
            tk.Label(
                box, text=label, fg=self.UI_DIM, bg=self.UI_PANEL,
                font=("Segoe UI", 6, "bold"),
            ).pack(anchor="w")
            entry = tk.Entry(
                box, width=width, bg=self.UI_PANEL_2, fg=COLOR_TEXT,
                insertbackground=COLOR_ACCENT, relief=tk.FLAT,
                highlightthickness=1, highlightbackground=self.UI_BORDER,
                highlightcolor=COLOR_ACCENT,
            )
            entry.pack(anchor="w")
            entry.bind("<FocusOut>", lambda _event: self._save_filters())
            entry.bind("<Return>", lambda _event: self._save_filters())
            self.filter_entries[key] = entry
        tk.Label(
            top, text="Blank load uses live free hold.",
            fg=self.UI_DIM, bg=self.UI_PANEL, font=("Segoe UI", 7),
        ).pack(side=tk.RIGHT, padx=11)

        bottom = tk.Frame(panel, bg=self.UI_PANEL)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 5))
        for label, variable in (
            ("Large pad", self.large_pad_var),
            ("Carriers", self.include_carriers_var),
            ("Orbital only", self.orbital_only_var),
            ("Full load", self.full_load_var),
            ("Round trip", self.round_trip_var),
        ):
            self._checkbutton(
                bottom, label, variable, self._save_filters,
            ).pack(side=tk.LEFT, padx=(0, 7), pady=4)

        for label, variable, values, width in (
            ("RANK", self.rank_var, RANK_OPTIONS, 16),
            ("RESULTS", self.result_count_var, RESULT_COUNTS, 4),
        ):
            tk.Label(
                bottom, text=label, fg=self.UI_DIM, bg=self.UI_PANEL,
                font=("Segoe UI", 6, "bold"),
            ).pack(side=tk.LEFT, padx=(8, 4))
            combo = ttk.Combobox(
                bottom, textvariable=variable, values=values,
                state="readonly", width=width,
            )
            combo.pack(side=tk.LEFT, pady=4)
            combo.bind("<<ComboboxSelected>>", lambda _event: self._save_filters())

    def _checkbutton(self, parent, text, variable, command=None):
        return tk.Checkbutton(
            parent, text=text, variable=variable, command=command,
            bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2,
            activebackground=self.UI_PANEL, activeforeground=COLOR_ACCENT,
            highlightthickness=0, font=("Segoe UI", 8),
        )

    def _build_results(self):
        panel = tk.Frame(
            self.win, bg=self.UI_PANEL,
            highlightbackground=self.UI_BORDER, highlightthickness=1,
        )
        panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=(9, 0))
        head = tk.Frame(panel, bg=self.UI_PANEL)
        head.pack(fill=tk.X, padx=11, pady=(9, 5))
        self.result_title = tk.Label(
            head, text="CURRENT RUN", fg=COLOR_ORANGE, bg=self.UI_PANEL,
            font=("Segoe UI", 9, "bold"), anchor="w",
        )
        self.result_title.pack(side=tk.LEFT)
        self.result_status = tk.Label(
            head, text="", fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=("Consolas", 8), anchor="e",
        )
        self.result_status.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        tree_wrap = tk.Frame(panel, bg=self.UI_PANEL)
        tree_wrap.pack(fill=tk.BOTH, expand=True, padx=11)
        columns = ("primary", "destination", "value", "cargo", "distance", "age")
        self.result_tree = ttk.Treeview(
            tree_wrap, columns=columns, show="headings",
            style="TradeAssist.Treeview", selectmode="browse", height=8,
        )
        widths = {
            "primary": (170, tk.W), "destination": (285, tk.W),
            "value": (155, tk.E), "cargo": (85, tk.E),
            "distance": (120, tk.E), "age": (70, tk.E),
        }
        for name, (width, anchor) in widths.items():
            self.result_tree.heading(name, text=name.upper())
            self.result_tree.column(name, width=width, anchor=anchor, stretch=name in ("primary", "destination"))
        ybar = scrollbar(
            tree_wrap, orient=tk.VERTICAL, command=self.result_tree.yview,
            prefix="TradeAssist",
        )
        xbar = scrollbar(
            tree_wrap, orient=tk.HORIZONTAL, command=self.result_tree.xview,
            prefix="TradeAssist",
        )
        self.result_tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)
        self.result_tree.tag_configure("fresh", foreground=self.UI_OK)
        self.result_tree.tag_configure("aging", foreground=self.UI_WARN)
        self.result_tree.tag_configure("history", foreground=self.UI_MUTED)
        self.result_tree.bind("<<TreeviewSelect>>", self._on_result_selected)
        self.result_tree.bind("<Double-1>", lambda _event: self.use_selected_result())

        self.detail = tk.Text(
            panel, height=4, bg=THEME.input, fg=COLOR_TEXT,
            insertbackground=COLOR_ACCENT, relief=tk.FLAT, padx=9, pady=7,
            font=("Consolas", 8), wrap=tk.WORD,
        )
        self.detail.pack(fill=tk.X, padx=11, pady=(7, 5))
        self.detail.configure(state=tk.DISABLED)

        actions = tk.Frame(panel, bg=self.UI_PANEL)
        actions.pack(fill=tk.X, padx=11, pady=(0, 9))
        button(actions, "USE SELECTED", self.use_selected_result, accent=True).pack(side=tk.LEFT)
        button(actions, "COPY DESTINATION", self.copy_selected_destination).pack(side=tk.LEFT, padx=(6, 0))
        button(actions, "COPY DETAILS", self.copy_selected_details).pack(side=tk.LEFT, padx=(6, 0))

    def _build_market_link(self):
        panel = tk.Frame(self.win, bg=self.UI_PANEL)
        panel.pack(fill=tk.X, padx=10, pady=(7, 8))
        market_row = tk.Frame(panel, bg=self.UI_PANEL)
        market_row.pack(fill=tk.X)
        self.market_link_status = tk.Label(
            market_row, text="ONLINE MARKET · CHECKING", fg=self.UI_MUTED,
            bg=self.UI_PANEL, font=("Consolas", 8, "bold"), anchor="w",
        )
        self.market_link_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(9, 6), pady=6)
        self._checkbutton(
            market_row, "Upload visited markets to EDDN", self.eddn_upload_var,
            self._toggle_eddn_upload,
        ).pack(side=tk.LEFT, padx=(4, 8))
        button(market_row, "REFRESH", lambda: self.refresh_status(force=True)).pack(
            side=tk.LEFT, padx=(0, 7), pady=4,
        )

        history_row = tk.Frame(panel, bg=self.UI_PANEL)
        history_row.pack(fill=tk.X, padx=9, pady=(0, 6))
        self._checkbutton(
            history_row, "Auto-prune trade log", self.trade_log_auto_prune_var,
            self._save_trade_log_settings,
        ).pack(side=tk.LEFT)
        tk.Label(
            history_row, text="KEEP", fg=self.UI_DIM, bg=self.UI_PANEL,
            font=("Segoe UI", 6, "bold"),
        ).pack(side=tk.LEFT, padx=(12, 4))
        self.trade_log_retention_combo = ttk.Combobox(
            history_row, textvariable=self.trade_log_retention_var,
            values=("30", "90", "180", "365"), state="readonly", width=5,
        )
        self.trade_log_retention_combo.pack(side=tk.LEFT)
        self.trade_log_retention_combo.bind(
            "<<ComboboxSelected>>", lambda _event: self._save_trade_log_settings(),
        )
        tk.Label(
            history_row, text="DAYS · commander profile only", fg=self.UI_DIM,
            bg=self.UI_PANEL, font=("Segoe UI", 7),
        ).pack(side=tk.LEFT, padx=(4, 0))
        button(history_row, "PRUNE NOW", self.prune_trade_log_now).pack(side=tk.RIGHT)
        button(history_row, "OPEN LOG", self.show_trade_log).pack(
            side=tk.RIGHT, padx=(0, 6),
        )

    # ------------------------------------------------------------------
    # Filter and live state
    # ------------------------------------------------------------------

    def _load_filter_values(self):
        defaults = {
            "radius": self._saved_filters.get("radius", 80),
            "max_ls": self._saved_filters.get("max_ls", 1000),
            "age": self._saved_filters.get("age", 30),
            "min_profit": self._saved_filters.get("min_profit", 1000),
            "cargo_override": self._saved_filters.get("cargo_override", ""),
        }
        for key, value in defaults.items():
            entry = self.filter_entries[key]
            entry.delete(0, tk.END)
            entry.insert(0, str(value))
        origin_defaults = {
            "origin_system": self._saved_filters.get(
                "origin_system", self._current_system() or "",
            ),
            "origin_station": (
                self._saved_filters.get(
                    "origin_station",
                    getattr(self.app, "current_station_name", None) or "",
                )
            ),
        }
        for key, value in origin_defaults.items():
            entry = self.origin_entries[key]
            entry.delete(0, tk.END)
            entry.insert(0, str(value))

    def _save_filters(self):
        self.config["trade_route_form"] = {
            key: entry.get().strip() for key, entry in self.filter_entries.items()
        }
        self.config["trade_route_form"].update({
            key: entry.get().strip() for key, entry in self.origin_entries.items()
        })
        self.config["trade_route_form"].update({
            "large_pad": bool(self.large_pad_var.get()),
            "include_carriers": bool(self.include_carriers_var.get()),
            "orbital_only": bool(self.orbital_only_var.get()),
            "full_load": bool(self.full_load_var.get()),
            "round_trip": bool(self.round_trip_var.get()),
            "rank": self.rank_var.get(),
            "result_count": self.result_count_var.get(),
        })

    def _filter_number(self, key, default, cast=float):
        try:
            value = self.filter_entries[key].get().strip()
            return cast(float(value)) if cast is int else cast(value)
        except (KeyError, TypeError, ValueError):
            return default

    def _origin_values(self):
        return (
            self.origin_entries["origin_system"].get().strip(),
            self.origin_entries["origin_station"].get().strip(),
        )

    def _result_count(self):
        try:
            value = str(self.result_count_var.get())
            return int(value) if value in RESULT_COUNTS else 3
        except (AttributeError, TypeError, ValueError):
            return 3

    def _planned_load_capacity(self):
        override = self._filter_number("cargo_override", 0, int)
        if override > 0:
            return override, True
        capacity = max(0, int(getattr(self.app, "cargo_capacity", 0) or 0))
        aboard = max(0, int(getattr(self.app, "current_cargo_tons", 0) or 0))
        if capacity:
            return max(0, capacity - aboard), False
        return 64, False

    def _use_current_origin(self):
        system = self._current_system() or ""
        station = getattr(self.app, "current_station_name", None) or ""
        for key, value in (("origin_system", system), ("origin_station", station)):
            entry = self.origin_entries[key]
            entry.delete(0, tk.END)
            entry.insert(0, value)
        self._save_filters()
        self.result_status.config(
            text=(
                f"Start set to {station} / {system}" if station
                else f"Start system set to {system}; station will be selected automatically."
            ),
            fg=self.UI_OK if system else self.UI_WARN,
        )

    def _current_system(self):
        system = getattr(self.app, "current_sys", None)
        return system if system and system not in ("---", "Unknown") else None

    def _current_coords(self):
        coords = getattr(self.app, "current_coords", None)
        return coords if isinstance(coords, (list, tuple)) and len(coords) >= 3 else None

    def _current_market_snapshot(self):
        """Return the matching live Market.json without publishing an old file."""
        expected = getattr(self.app, "current_station_market_id", None)
        current = getattr(self.app, "current_trade_market", None)
        if isinstance(current, dict) and current.get("items"):
            try:
                if expected is None or int(current.get("market_id")) == int(expected):
                    snapshot = dict(current)
                    snapshot.setdefault("station_type", getattr(self.app, "current_station_type", None))
                    snapshot.setdefault("dist_ls", getattr(self.app, "current_station_dist_ls", None))
                    snapshot.setdefault("large_pad", self._current_station_has_large_pad())
                    return snapshot
            except (TypeError, ValueError):
                pass
        journal_path = self.config.get("journal_path") or ""
        market_path = os.path.join(journal_path, "Market.json")
        try:
            with open(market_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if expected is not None and int(data.get("MarketID")) != int(expected):
                return None
            items = list(data.get("Items") or [])
            if not items:
                return None
            return {
                "market_id": data.get("MarketID"),
                "station": data.get("StationName") or getattr(self.app, "current_station_name", None),
                "system": data.get("StarSystem") or self._current_system(),
                "timestamp": data.get("timestamp"),
                "station_type": getattr(self.app, "current_station_type", None),
                "dist_ls": getattr(self.app, "current_station_dist_ls", None),
                "large_pad": self._current_station_has_large_pad(),
                "items": items,
            }
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _current_station_has_large_pad(self):
        pads = getattr(self.app, "current_station_landing_pads", None)
        if isinstance(pads, dict):
            try:
                return int(pads.get("Large") or pads.get("large") or 0) > 0
            except (TypeError, ValueError):
                return False
        return None

    def _ship_jump_range(self):
        ship = getattr(self.app, "cmdr_ship", {}) or {}
        try:
            return max(1.0, float(ship.get("max_jump_range") or 1.0))
        except (TypeError, ValueError):
            return 1.0

    @staticmethod
    def _estimated_jumps(distance_ly, jump_range):
        try:
            distance = max(0.0, float(distance_ly or 0))
            jump = max(1.0, float(jump_range or 1))
        except (TypeError, ValueError):
            return 0
        return int(math.ceil(distance / jump)) if distance else 0

    @staticmethod
    def _leg_time_seconds(distance_ly, distance_ls, jump_range):
        jumps = TradeWindow._estimated_jumps(distance_ly, jump_range)
        try:
            arrival = max(0.0, float(distance_ls))
        except (TypeError, ValueError):
            arrival = 1000.0
        supercruise = 60.0 + 170.0 * ((arrival / 1000.0) ** 0.35)
        return int(jumps * 50 + supercruise + 180)

    @staticmethod
    def _duration(seconds):
        try:
            total = max(0, int(seconds))
        except (TypeError, ValueError):
            return "?"
        if total < 3600:
            minutes = max(1, int(round(total / 60.0)))
            return f"{minutes}m"
        hours, remainder = divmod(total, 3600)
        minutes = int(round(remainder / 60.0))
        return f"{hours}h {minutes:02d}m"

    @staticmethod
    def _route_confidence(row, planned_load, max_age_days, round_trip=False):
        epochs = [
            row.get("source_updated_at"), row.get("updated_at"),
        ]
        if round_trip:
            epochs.append(row.get("return_updated_at"))
        usable_epochs = [float(value) for value in epochs if value]
        oldest = min(usable_epochs) if usable_epochs else None
        if oldest:
            age_days = max(0.0, (time.time() - oldest) / 86400.0)
            freshness = max(0.0, 1.0 - age_days / max(1.0, float(max_age_days)))
        else:
            freshness = 0.25
        load = max(1, int(planned_load or 1))
        outbound_cover = min(
            int(row.get("supply") or 0), int(row.get("demand") or 0), load,
        ) / load
        coverage = outbound_cover
        if round_trip:
            return_cover = min(
                int(row.get("return_supply") or 0),
                int(row.get("return_demand") or 0), load,
            ) / load
            coverage = min(coverage, return_cover)
        score = max(0.0, min(1.0, freshness * 0.55 + coverage * 0.45))
        label = "HIGH" if score >= 0.8 else ("MEDIUM" if score >= 0.55 else "LOW")
        return label, score, oldest

    def _refresh_summary(self):
        if not self.is_open():
            return
        system = self._current_system() or "---"
        station = getattr(self.app, "current_station_name", None)
        self.system_value.config(text=self._truncate(f"{system} / {station}" if station else system, 34))
        balance = getattr(self.app, "cmdr_balance", None)
        self.credits_value.config(text=self._credits(balance) if balance is not None else "---")
        cargo = int(getattr(self.app, "current_cargo_tons", 0) or 0)
        capacity = int(getattr(self.app, "cargo_capacity", 0) or 0)
        self.cargo_value.config(text=f"{cargo}/{capacity} t" if capacity else f"{cargo} t")
        session = getattr(self.app, "trade_session", {}) or {}
        self.profit_value.config(text=self._credits(session.get("profit", 0)))
        plan = getattr(self.app, "trade_plan_context", None) or {}
        destination = plan.get("to_system") or plan.get("destination") or "NONE"
        self.plan_value.config(text=self._truncate(str(destination).upper(), 22))

    def refresh_local(self):
        """Dashboard compatibility hook; market ingest itself stays independent."""
        self._refresh_summary()

    def on_cargo_updated(self):
        """Refresh an open cargo search when Elite changes the hold snapshot."""
        signature = self._cargo_signature()
        changed = signature != self._last_cargo_signature
        self._last_cargo_signature = signature
        self._refresh_summary()
        if not changed or self._current_view != "cargo":
            return
        if self._is_active_view():
            self._cargo_refresh_pending = False
            self.find_cargo_buyers()
        else:
            self._cargo_refresh_pending = True

    def refresh_session(self):
        self._refresh_summary()
        if self._current_view == "run":
            self._render_current_session(load_history=False)

    def refresh_analytics(self):
        """Trade events used to refresh an advanced analytics tab."""
        self.refresh_session()

    def _schedule_live_poll(self, delay_ms=2000):
        if not self.is_open():
            return
        if self._live_poll_after:
            try:
                self.root.after_cancel(self._live_poll_after)
            except Exception:
                pass
        self._live_poll_after = self.root.after(delay_ms, self._live_poll_tick)

    def _live_poll_tick(self):
        self._live_poll_after = None
        if not self.is_open():
            return
        if self._is_active_view():
            self._refresh_summary()
            if self._current_view == "run":
                self._render_current_session(load_history=False)
            if time.monotonic() - getattr(self, "_last_status_poll", 0.0) >= 60.0:
                self.refresh_status()
        self._schedule_live_poll(2000 if self._is_active_view() else 5000)

    # ------------------------------------------------------------------
    # Sell cargo
    # ------------------------------------------------------------------

    @staticmethod
    def _tradeable_cargo(items):
        usable = []
        excluded = 0
        for item in items or []:
            if not isinstance(item, dict):
                continue
            mission = item.get("MissionID") or item.get("mission_id")
            try:
                stolen = int(item.get("Stolen") or item.get("stolen") or 0)
            except (TypeError, ValueError):
                stolen = 0
            if mission or stolen:
                excluded += int(item.get("Count") or item.get("count") or 0)
                continue
            usable.append(item)
        return usable, excluded

    def _cargo_signature(self):
        rows = []
        for item in list(getattr(self.app, "current_cargo_inventory", []) or []):
            if not isinstance(item, dict):
                continue
            name = item.get("Name") or item.get("name") or item.get("Name_Localised") or ""
            try:
                count = int(item.get("Count", item.get("count", 0)) or 0)
                stolen = int(item.get("Stolen", item.get("stolen", 0)) or 0)
            except (TypeError, ValueError):
                count, stolen = 0, 0
            rows.append((
                str(name).casefold(), count,
                str(item.get("MissionID") or item.get("mission_id") or ""), stolen,
            ))
        return tuple(sorted(rows))

    def find_cargo_buyers(self):
        self._cargo_refresh_pending = False
        self._last_cargo_signature = self._cargo_signature()
        self._save_filters()
        cargo, excluded = self._tradeable_cargo(
            list(getattr(self.app, "current_cargo_inventory", []) or [])
        )
        if not cargo:
            note = " Mission and stolen cargo are deliberately excluded." if excluded else ""
            self._set_view("cargo", "SELL MY CARGO", "No tradeable cargo is currently aboard." + note)
            return
        origin_system, origin_station = self._origin_values()
        if not origin_system:
            self._set_view(
                "cargo", "SELL MY CARGO",
                "Enter a start system or choose USE CURRENT.", self.UI_WARN,
            )
            return
        self._set_view(
            "cargo", "SELL MY CARGO", f"Finding buyers around {origin_system}…",
        )
        token = self._next_search()
        params = {
            "cargo_items": cargo,
            "system": origin_system,
            "star_pos": None,
            "radius": self._filter_number("radius", 80.0),
            "max_price_age_days": self._filter_number("age", 30, int),
            "requires_large_pad": bool(self.large_pad_var.get()),
            "include_carriers": bool(self.include_carriers_var.get()),
            "max_system_distance": self._filter_number("max_ls", 1000.0),
            "orbital_only": bool(self.orbital_only_var.get()),
            "limit": self._result_count(),
        }

        def worker():
            try:
                rows = routes.sell_cargo(**params)
                self._post_ui(
                    lambda: self._render_cargo_buyers(
                        rows, excluded, token, origin_system, origin_station,
                    ),
                    key="trade-assist-cargo",
                )
            except Exception as exc:
                self._post_ui(
                    lambda text=str(exc): self._search_failed("SELL MY CARGO", text, token),
                    key="trade-assist-cargo",
                )

        threading.Thread(target=worker, name="trade-cargo-buyers", daemon=True).start()

    def _render_cargo_buyers(self, rows, excluded, token, origin_system=None,
                             origin_station=None):
        if token != self._search_generation or not self.is_open():
            return
        self._set_view("cargo", "SELL MY CARGO", "")
        result_count = self._result_count()
        shown_rows = list(rows or [])[:result_count]
        for row in shown_rows:
            items = list(row.get("items") or [])
            cargo_text = ", ".join(
                f"{item.get('name')} {self._num(item.get('units'))}t"
                for item in items[:3]
            )
            if len(items) > 3:
                cargo_text += f" +{len(items) - 3} more"
            destination = f"{row.get('station')} / {row.get('system')}"
            distance_ly = float(row.get("distance") or 0)
            jumps = max(1, math.ceil(distance_ly / self._ship_jump_range()))
            distance = f"{distance_ly:.1f} ly · {jumps} jump{'s' if jumps != 1 else ''}"
            if row.get("dist_ls") is not None:
                distance += f" · {self._num(row.get('dist_ls'))} ls"
            detail_lines = [
                f"SELL AT {row.get('station')} ({row.get('system')})",
                f"Estimated gross sale: {self._credits(row.get('total'))}. This is revenue, not profit.",
            ]
            for item in items:
                detail_lines.append(
                    f"• {item.get('name')} · {self._num(item.get('units'))} t "
                    f"at {self._credits(item.get('sell_price'))}/t · {self._credits(item.get('payout'))}"
                )
            plan = {
                "kind": "sell-cargo",
                "from_system": origin_system or self._current_system(),
                "from_station": origin_station or None,
                "to_system": row.get("system"),
                "to_station": row.get("station"),
                "revenue_cr": int(row.get("total") or 0),
                "distance_ly": float(row.get("distance") or 0),
            }
            self._insert_result(
                row.get("station"), row.get("system"), self._credits(row.get("total")),
                cargo_text, distance, self._age(row.get("updated_at")),
                row, "\n".join(detail_lines), plan,
            )
        suffix = f" · {excluded:,} t mission/stolen cargo excluded" if excluded else ""
        self.result_status.config(
            text=(
                f"{len(shown_rows)} best buyer(s) around {origin_system}{suffix}"
                if rows else f"No online buyers matched the selected filters{suffix}."
            ),
            fg=self.UI_MUTED if rows else self.UI_WARN,
        )
        self._select_best_result()

    # ------------------------------------------------------------------
    # One-click departure trade
    # ------------------------------------------------------------------

    def find_trade(self):
        self._save_filters()
        system, station = self._origin_values()
        if not system:
            self._set_view(
                "trade", "FIND A TRADE",
                "Enter a start system or choose USE CURRENT.",
                self.UI_WARN,
            )
            return
        max_age_days = self._filter_number("age", 30, int)
        result_count = self._result_count()
        round_trip = bool(self.round_trip_var.get())
        full_load = bool(self.full_load_var.get())
        orbital_only = bool(self.orbital_only_var.get())
        planned_load, load_overridden = self._planned_load_capacity()
        if planned_load <= 0:
            self._set_view(
                "trade", "FIND A TRADE",
                "The cargo hold is full. Set a planned load or free cargo space before searching.",
                self.UI_WARN,
            )
            return
        current_system = self._current_system()
        current_station = getattr(self.app, "current_station_name", None)
        current_market_id = getattr(self.app, "current_station_market_id", None)
        use_live_market = bool(
            station and current_system and current_station and current_market_id
            and getattr(self.app, "current_docked", False)
            and system.casefold() == current_system.casefold()
            and station.casefold() == str(current_station).casefold()
        )
        market = self._current_market_snapshot() if use_live_market else None
        if market:
            market_updated = marketdb.parse_update_time(market.get("timestamp"))
            if (
                not market_updated
                or time.time() - market_updated > max(1, max_age_days) * 86400
            ):
                market = None
            elif self.large_pad_var.get() and market.get("large_pad") is not True:
                market = None
            elif orbital_only and routes.is_surface_station(market.get("station_type")):
                market = None
            elif (
                not self.include_carriers_var.get()
                and "carrier" in str(market.get("station_type") or "").casefold()
            ):
                market = None
        origin_label = f"{station} / {system}" if station else f"an automatically selected market in {system}"
        self._set_view("trade", "FIND A TRADE", f"Resolving {origin_label}…")
        token = self._next_search()
        filters = {
            "radius": self._filter_number("radius", 80.0),
            "min_profit": self._filter_number("min_profit", 1000, int),
            "max_price_age_days": max_age_days,
            "requires_large_pad": bool(self.large_pad_var.get()),
            "include_carriers": bool(self.include_carriers_var.get()),
            "max_system_distance": self._filter_number("max_ls", 1000.0),
            "orbital_only": orbital_only,
        }
        balance = getattr(self.app, "cmdr_balance", None)
        capital = int(balance) if balance is not None else None
        jump_range = self._ship_jump_range()
        rank_mode = self.rank_var.get()

        def worker():
            try:
                source = market or routes.resolve_market_origin(
                    system, station,
                    max_price_age_days=filters["max_price_age_days"],
                    requires_large_pad=filters["requires_large_pad"],
                    include_carriers=filters["include_carriers"],
                    orbital_only=filters["orbital_only"],
                )
                self._post_ui(
                    lambda resolved=source: self._render_origin_resolved(resolved, token),
                    key="trade-assist-origin",
                )
                params = {
                    "system": source.get("system") or system,
                    "star_pos": None,
                    "radius": filters["radius"],
                    "min_profit": filters["min_profit"],
                    "min_units": planned_load if full_load else 1,
                    "max_price_age_days": filters["max_price_age_days"],
                    "requires_large_pad": filters["requires_large_pad"],
                    "include_carriers": filters["include_carriers"],
                    "max_system_distance": filters["max_system_distance"],
                    "orbital_only": filters["orbital_only"],
                    "source_updated_at": source.get("timestamp"),
                    "source_market_id": int(source.get("market_id")),
                    "source_station": source.get("station") or station,
                    "market_items": list(source.get("items") or []),
                    "limit": min(75, max(30, result_count * 3)),
                }
                rows = routes.find_opportunities(**params)
                ranked = []
                for row in rows:
                    buy_price = max(0, int(row.get("buy_price") or 0))
                    affordable = (
                        capital // buy_price
                        if buy_price and capital is not None else planned_load
                    )
                    units = min(int(row.get("units") or 0), planned_load, affordable)
                    if units <= 0:
                        continue
                    if full_load and units < planned_load:
                        continue
                    copy = dict(row)
                    copy["trade_units"] = units
                    copy["projected_profit"] = units * int(row.get("profit_each") or 0)
                    copy["estimated_jumps"] = self._estimated_jumps(
                        row.get("distance"), jump_range,
                    )
                    copy["outbound_time_s"] = self._leg_time_seconds(
                        row.get("distance"), row.get("to_dist_ls"), jump_range,
                    )
                    copy["from_dist_ls"] = source.get("dist_ls")
                    ranked.append(copy)
                ranked.sort(
                    key=lambda item: int(item.get("projected_profit") or 0),
                    reverse=True,
                )
                if round_trip and ranked:
                    candidate_count = min(
                        len(ranked), max(result_count, min(36, result_count + 10)),
                    )
                    ranked = ranked[:candidate_count]
                    self._post_ui(
                        lambda count=candidate_count: self._render_return_progress(count, token),
                        key="trade-assist-return-progress",
                    )
                    ranked = routes.attach_return_trades(
                        ranked, list(source.get("items") or []),
                        cargo_units=planned_load, capital=capital,
                        source_updated_at=source.get("timestamp"),
                        max_price_age_days=filters["max_price_age_days"],
                    )
                    if full_load:
                        ranked = [
                            row for row in ranked
                            if int(row.get("return_units") or 0) >= planned_load
                        ]

                final_rows = []
                for row in ranked:
                    copy = dict(row)
                    return_profit = int(copy.get("return_profit") or 0) if round_trip else 0
                    total_profit = int(copy.get("projected_profit") or 0) + return_profit
                    return_time = (
                        self._leg_time_seconds(
                            copy.get("distance"), source.get("dist_ls"), jump_range,
                        ) if round_trip else 0
                    )
                    total_time = int(copy.get("outbound_time_s") or 0) + return_time
                    confidence, confidence_score, quote_epoch = self._route_confidence(
                        copy, planned_load, filters["max_price_age_days"], round_trip,
                    )
                    copy.update({
                        "round_trip": round_trip,
                        "total_profit": total_profit,
                        "total_time_s": total_time,
                        "profit_per_hour": int(total_profit * 3600 / max(1, total_time)),
                        "confidence": confidence,
                        "confidence_score": confidence_score,
                        "quote_epoch": quote_epoch,
                        "planned_load": planned_load,
                        "load_overridden": load_overridden,
                    })
                    final_rows.append(copy)

                if rank_mode == "Profit / hour":
                    rank_key = lambda item: float(item.get("profit_per_hour") or 0)
                    reverse = True
                elif rank_mode == "Shortest travel":
                    rank_key = lambda item: float(item.get("total_time_s") or float("inf"))
                    reverse = False
                elif rank_mode == "Freshest quotes":
                    rank_key = lambda item: float(item.get("quote_epoch") or 0)
                    reverse = True
                else:
                    rank_key = lambda item: float(item.get("total_profit") or 0)
                    reverse = True
                final_rows.sort(key=rank_key, reverse=reverse)
                self._post_ui(
                    lambda: self._render_trade_results(
                        final_rows[:result_count], token, source, rank_mode,
                    ),
                    key="trade-assist-route",
                )
            except Exception as exc:
                self._post_ui(
                    lambda text=str(exc): self._search_failed("FIND A TRADE", text, token),
                    key="trade-assist-route",
                )

        threading.Thread(target=worker, name="trade-quick-route", daemon=True).start()

    def _render_return_progress(self, count, token):
        if token != self._search_generation or not self.is_open():
            return
        self.result_status.config(
            text=f"Checking real return cargo for {count} candidate route(s)…",
            fg=self.UI_MUTED,
        )

    def _render_origin_resolved(self, source, token):
        if token != self._search_generation or not self.is_open():
            return
        station = source.get("station") or "selected market"
        system = source.get("system") or "selected system"
        self.result_status.config(
            text=f"Scanning departures from {station} / {system}…",
            fg=self.UI_MUTED,
        )

    def _render_trade_results(self, rows, token, source=None, rank_mode="Profit / trip"):
        if token != self._search_generation or not self.is_open():
            return
        if source and source.get("online"):
            for key, value in (
                ("origin_system", source.get("system")),
                ("origin_station", source.get("station")),
            ):
                if value:
                    entry = self.origin_entries[key]
                    entry.delete(0, tk.END)
                    entry.insert(0, value)
            self._save_filters()
        self._set_view("trade", "FIND A TRADE", "")
        for row in rows:
            units = int(row.get("trade_units") or 0)
            outbound_profit = int(row.get("projected_profit") or 0)
            total_profit = int(row.get("total_profit") or outbound_profit)
            profit_per_hour = int(row.get("profit_per_hour") or 0)
            is_loop = bool(row.get("round_trip"))
            destination = f"{row.get('to_station')} / {row.get('to_system')}"
            jumps = int(row.get("estimated_jumps") or 0)
            total_jumps = jumps * (2 if is_loop else 1)
            distance = (
                f"{self._duration(row.get('total_time_s'))} · "
                f"{total_jumps} jump{'s' if total_jumps != 1 else ''}"
            )
            detail_lines = [
                f"BUY {self._num(units)} t {row.get('commodity')} at "
                f"{row.get('from_station')} ({row.get('from_system')})",
                f"Buy {self._credits(row.get('buy_price'))}/t · sell "
                f"{self._credits(row.get('sell_price'))}/t at {row.get('to_station')} "
                f"({row.get('to_system')})",
                f"Outbound {self._credits(outbound_profit)} · "
                f"{self._credits(row.get('profit_each'))}/t · "
                f"supply {self._num(row.get('supply'))} / demand {self._num(row.get('demand'))}",
                f"TRAVEL {float(row.get('distance') or 0):.1f} ly · "
                f"{jumps} jump{'s' if jumps != 1 else ''} · destination arrival "
                f"{self._num(row.get('to_dist_ls')) if row.get('to_dist_ls') is not None else '?'} ls"
                f" · {row.get('to_type') or 'station type unknown'}",
            ]
            if is_loop:
                detail_lines.extend([
                    f"RETURN WITH {self._num(row.get('return_units'))} t "
                    f"{row.get('return_commodity')}",
                    f"Buy {self._credits(row.get('return_buy_price'))}/t at "
                    f"{row.get('to_station')} · sell {self._credits(row.get('return_sell_price'))}/t "
                    f"at {row.get('from_station')}",
                    f"Return {self._credits(row.get('return_profit'))} · "
                    f"{self._credits(row.get('return_profit_each'))}/t · "
                    f"supply {self._num(row.get('return_supply'))} / demand {self._num(row.get('return_demand'))}",
                ])
            detail_lines.append(
                f"TOTAL {self._credits(total_profit)} · {self._credits(profit_per_hour)}/hour · "
                f"about {self._duration(row.get('total_time_s'))} · "
                f"{float(row.get('distance') or 0):.1f} ly each way · "
                f"confidence {row.get('confidence')} · oldest quote {self._age(row.get('quote_epoch'))}"
            )
            plan = {
                "kind": "round-trip" if is_loop else "quick-trade",
                "from_system": row.get("from_system"),
                "from_station": row.get("from_station"),
                "to_system": row.get("to_system"),
                "to_station": row.get("to_station"),
                "commodity": row.get("commodity"),
                "symbol": row.get("symbol"),
                "units": units,
                "return_commodity": row.get("return_commodity") if is_loop else None,
                "return_symbol": row.get("return_symbol") if is_loop else None,
                "return_units": int(row.get("return_units") or 0) if is_loop else 0,
                "profit_cr": total_profit,
                "profit_per_hour": profit_per_hour,
                "estimated_seconds": int(row.get("total_time_s") or 0),
                "confidence": row.get("confidence"),
                "distance_ly": float(row.get("distance") or 0),
            }
            cargo_text = f"{self._num(units)} t"
            if is_loop:
                cargo_text += f" + {self._num(row.get('return_units'))} t"
            self._insert_result(
                row.get("commodity"), destination,
                f"{self._credits(total_profit)} · {self._credits(profit_per_hour)}/h",
                cargo_text, distance,
                f"{row.get('confidence')} · {self._age(row.get('quote_epoch'))}",
                row, "\n".join(detail_lines), plan,
            )
        self.result_status.config(
            text=(
                f"{len(rows)} {'round-trip' if rows and rows[0].get('round_trip') else 'one-way'} option(s) "
                f"from {(source or {}).get('station') or 'the selected market'} · ranked by {rank_mode.lower()}."
                if rows else (
                    f"No profitable {'round trip' if self.round_trip_var.get() else 'departure'} from "
                    f"{(source or {}).get('station') or 'the selected market'} "
                    "matched the selected filters."
                )
            ),
            fg=self.UI_MUTED if rows else self.UI_WARN,
        )
        self._select_best_result()

    # ------------------------------------------------------------------
    # Persistent trade log
    # ------------------------------------------------------------------

    def show_trade_log(self):
        self._current_view = "log"
        self._set_view("log", "TRADE LOG", "Loading this commander's journal trades…")
        token = self._next_search()
        profile = self.config.get("active_commander_profile")

        def worker():
            try:
                rows = marketdb.recent_trades(limit=500, profile_key=profile)
                stats = marketdb.trade_history_stats(profile_key=profile)
                self._post_ui(
                    lambda: self._render_trade_log(rows, stats, token, profile),
                    key="trade-log-history",
                )
            except Exception as exc:
                self._post_ui(
                    lambda text=str(exc): self._search_failed("TRADE LOG", text, token),
                    key="trade-log-history",
                )

        threading.Thread(target=worker, name="trade-log-history", daemon=True).start()

    def refresh_trade_log(self):
        if self._current_view == "log" and self.is_open():
            self.show_trade_log()

    def _render_trade_log(self, rows, stats, token, profile):
        if (
            token != self._search_generation or not self.is_open()
            or self._current_view != "log"
            or profile != self.config.get("active_commander_profile")
        ):
            return
        self._set_view("log", "TRADE LOG", "")
        rows = list(rows or [])
        if not rows:
            self._finish_trade_log(rows, stats, token, profile)
            return

        self.result_status.config(
            text=f"Loading {len(rows):,} journal trade(s)…",
            fg=self.UI_MUTED,
        )

        def insert_batch(offset=0):
            if (
                token != self._search_generation or not self.is_open()
                or self._current_view != "log"
                or profile != self.config.get("active_commander_profile")
            ):
                return
            stop = min(offset + 50, len(rows))
            for row in rows[offset:stop]:
                self._insert_trade_log_row(row)
            if stop < len(rows):
                self.root.after(1, lambda: insert_batch(stop))
            else:
                self._finish_trade_log(rows, stats, token, profile)

        insert_batch()

    def _insert_trade_log_row(self, row):
        event = str(row.get("event") or "trade").upper()
        profit = row.get("profit")
        if event == "BUY":
            value = -int(row.get("total") or 0)
        else:
            value = int(profit if profit is not None else row.get("total") or 0)
        location = " / ".join(
            str(item) for item in (row.get("station"), row.get("system")) if item
        ) or "Location unavailable"
        try:
            stamp = time.strftime(
                "%d %b %Y %H:%M", time.localtime(int(row.get("ts") or 0)),
            )
        except (TypeError, ValueError, OSError):
            stamp = "Unknown time"
        detail_lines = [
            f"{event} {self._num(row.get('count'))} t {row.get('name') or row.get('symbol')}",
            f"{location} · {self._credits(row.get('price'))}/t · "
            f"total {self._credits(row.get('total'))}",
            f"Journal time {stamp}",
        ]
        if row.get("plan_kind"):
            route = " → ".join(
                str(item) for item in (row.get("plan_from"), row.get("plan_to")) if item
            )
            detail_lines.append(
                f"PLAN {str(row.get('plan_kind')).upper()} · {route or 'route context unavailable'}"
            )
            if row.get("expected_profit") is not None:
                detail_lines.append(
                    f"Planned route profit {self._credits(row.get('expected_profit'))}"
                )
        self._insert_result(
            event, row.get("name") or row.get("symbol"), self._credits(value),
            f"{self._num(row.get('count'))} t", self._truncate(location, 28),
            stamp, row, "\n".join(detail_lines), None, tag="history",
        )

    def _finish_trade_log(self, rows, stats, token, profile):
        if (
            token != self._search_generation or not self.is_open()
            or self._current_view != "log"
            or profile != self.config.get("active_commander_profile")
        ):
            return
        count = int((stats or {}).get("count") or 0)
        oldest = (stats or {}).get("oldest")
        oldest_text = self._age(oldest) if oldest else "none"
        self.result_status.config(
            text=(
                f"Showing {len(rows or []):,} newest of {count:,} transaction(s) · "
                f"oldest {oldest_text} · local to this commander."
                if rows else "No journal-confirmed trades are stored for this commander yet."
            ),
            fg=self.UI_MUTED if rows else self.UI_WARN,
        )
        children = self.result_tree.get_children()
        if children:
            iid = children[0]
            self.result_tree.selection_set(iid)
            self.result_tree.focus(iid)
            self._on_result_selected()
        else:
            self._set_detail("MarketBuy and MarketSell journal events will appear here.")

    # ------------------------------------------------------------------
    # Current run and recent activity
    # ------------------------------------------------------------------

    def show_current_run(self):
        self._next_search()
        self._current_view = "run"
        self._render_current_session(load_history=True)

    def _render_current_session(self, load_history=False):
        if not self.is_open() or self._current_view != "run":
            return
        session = getattr(self.app, "trade_session", {}) or {}
        events = list(session.get("events") or [])
        plan = getattr(self.app, "trade_plan_context", None) or {}
        signature = (
            int(session.get("bought_units") or 0),
            int(session.get("sold_units") or 0),
            int(session.get("profit") or 0),
            tuple(
                (
                    event.get("time"), event.get("event"), event.get("commodity"),
                    event.get("count"), event.get("profit"),
                )
                for event in events[-25:]
                if isinstance(event, dict)
            ),
            plan.get("kind"), plan.get("from_system"), plan.get("from_station"),
            plan.get("to_system"), plan.get("to_station"), plan.get("profit_cr"),
            plan.get("_created_at"), plan.get("_session_profit_start"),
        )
        if not load_history and signature == self._last_session_signature:
            return
        self._last_session_signature = signature
        plan_text = "No destination selected"
        if plan:
            plan_text = (
                f"{plan.get('from_station') or plan.get('from_system') or '?'} → "
                f"{plan.get('to_station') or plan.get('to_system') or '?'}"
            )
        realized_profit = int(session.get("profit") or 0) - int(
            plan.get("_session_profit_start") or 0
        ) if plan else 0
        realized_transactions = int(session.get("transactions") or 0) - int(
            plan.get("_session_transactions_start") or 0
        ) if plan else 0
        plan_progress = ""
        if plan and plan.get("profit_cr") is not None:
            plan_progress = (
                f" · Expected {self._credits(plan.get('profit_cr'))} · "
                f"realized {self._credits(realized_profit)} in {max(0, realized_transactions)} trade(s)"
            )
        self._set_view(
            "run", "CURRENT RUN",
            f"Bought {self._num(session.get('bought_units', 0))} t · "
            f"Sold {self._num(session.get('sold_units', 0))} t · "
            f"Profit {self._credits(session.get('profit', 0))} · {plan_text}{plan_progress}",
        )
        for event in events[-25:][::-1]:
            try:
                stamp = time.strftime("%H:%M", time.localtime(float(event.get("time") or time.time())))
            except (TypeError, ValueError, OSError):
                stamp = "--:--"
            profit = int(event.get("profit") or 0)
            detail = (
                f"{event.get('event')} {event.get('commodity')} · {self._num(event.get('count'))} t\n"
                f"Price {self._credits(event.get('price'))}/t · value/profit {self._credits(profit)}"
            )
            self._insert_result(
                event.get("event"), event.get("commodity"), self._credits(profit),
                f"{self._num(event.get('count'))} t", self._credits(event.get("price")),
                stamp, event, detail, None, tag="history",
            )
        if plan:
            cargo_label = plan.get('commodity') or plan.get('kind') or 'Trade'
            if plan.get("return_commodity"):
                cargo_label += f" out · {plan.get('return_commodity')} back"
            detail_lines = [
                f"ACTIVE PLAN\n{plan_text}\n"
                f"{cargo_label} · "
                f"expected {self._credits(plan.get('profit_cr')) if plan.get('profit_cr') is not None else 'sale destination'}"
            ]
            if plan.get("profit_cr") is not None:
                variance = realized_profit - int(plan.get("profit_cr") or 0)
                detail_lines.append(
                    f"REALIZED SINCE PLAN · {self._credits(realized_profit)} across "
                    f"{max(0, realized_transactions)} trade(s) · "
                    f"variance {variance:+,} cr"
                )
            self._set_detail("\n".join(detail_lines))
        elif not events:
            self._set_detail("No trade has been recorded in this application session.")
        if not events and load_history and not self._history_loading:
            self._history_loading = True
            token = self._search_generation

            def worker():
                try:
                    rows = marketdb.recent_trades(
                        limit=18,
                        profile_key=self.config.get("active_commander_profile"),
                    )
                except Exception:
                    rows = []
                self._post_ui(
                    lambda: self._render_recent_history(rows, token),
                    key="trade-assist-history",
                )

            threading.Thread(target=worker, name="trade-recent-history", daemon=True).start()

    def _render_recent_history(self, rows, token):
        self._history_loading = False
        if token != self._search_generation or self._current_view != "run" or not self.is_open():
            return
        if (getattr(self.app, "trade_session", {}) or {}).get("events"):
            return
        for row in rows:
            stamp = time.strftime("%d %b %H:%M", time.localtime(int(row.get("ts") or 0)))
            value = row.get("profit") if row.get("profit") is not None else row.get("total")
            detail = (
                f"RECENT {str(row.get('event') or '').upper()} · {row.get('name') or row.get('symbol')}\n"
                f"{self._num(row.get('count'))} t at {self._credits(row.get('price'))}/t · "
                f"{self._credits(value)}"
            )
            self._insert_result(
                str(row.get("event") or "").upper(), row.get("name") or row.get("symbol"),
                self._credits(value), f"{self._num(row.get('count'))} t",
                self._credits(row.get("price")), stamp,
                row, detail, None, tag="history",
            )
        if rows:
            self.result_status.config(text=f"Recent history · {len(rows)} transaction(s)")

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------

    def _next_search(self):
        self._search_generation += 1
        return self._search_generation

    def _set_view(self, view, title, status="", colour=None):
        self._current_view = view
        self.result_title.config(text=title)
        self.result_status.config(text=status, fg=colour or self.UI_MUTED)
        for iid in self.result_tree.get_children():
            self.result_tree.delete(iid)
        self.result_rows = {}
        self._set_detail("")
        headings = {
            "cargo": ("BUYER", "SYSTEM", "EST. SALE", "ACCEPTED", "TRAVEL", "AGE"),
            "trade": ("COMMODITY", "DESTINATION", "PROFIT", "LOAD", "TRAVEL", "AGE"),
            "run": ("TYPE", "COMMODITY", "VALUE / PROFIT", "TONS", "PRICE", "WHEN"),
            "log": ("TYPE", "COMMODITY", "VALUE / PROFIT", "TONS", "LOCATION", "WHEN"),
        }.get(view, ("ITEM", "DESTINATION", "VALUE", "CARGO", "TRAVEL", "AGE"))
        for column, label in zip(self.result_tree["columns"], headings):
            self.result_tree.heading(column, text=label)

    def _insert_result(self, primary, destination, value, cargo, distance, age,
                       raw, detail, plan, tag=None):
        row_tag = tag or self._freshness_tag(
            (raw or {}).get("quote_epoch") or (raw or {}).get("updated_at")
        )
        iid = self.result_tree.insert(
            "", tk.END,
            values=(primary or "---", destination or "---", value or "---",
                    cargo or "---", distance or "---", age or "---"),
            tags=(row_tag,) if row_tag else (),
        )
        self.result_rows[iid] = {
            "raw": raw or {}, "detail": detail or "", "plan": plan,
            "destination": (plan or {}).get("to_system") if plan else None,
        }
        return iid

    def _select_best_result(self):
        children = self.result_tree.get_children()
        if not children:
            self._set_detail("No result matched the current filters.")
            setter = getattr(self.app, "_set_compass_trade_plan", None)
            if callable(setter):
                setter(None)
            return
        iid = children[0]
        self.result_tree.selection_set(iid)
        self.result_tree.focus(iid)
        self.result_tree.see(iid)
        self._on_result_selected()
        plan = self.result_rows.get(iid, {}).get("plan")
        setter = getattr(self.app, "_set_compass_trade_plan", None)
        if plan and callable(setter):
            setter(plan)
        self._refresh_summary()

    def _on_result_selected(self, _event=None):
        selected = self.result_tree.selection()
        row = self.result_rows.get(selected[0]) if selected else None
        self._set_detail((row or {}).get("detail") or "Select a result to see its details.")

    def use_selected_result(self):
        selected = self.result_tree.selection()
        row = self.result_rows.get(selected[0]) if selected else None
        if not row or not row.get("plan"):
            self.result_status.config(text="Select a cargo buyer or trade first.", fg=self.UI_WARN)
            return
        setter = getattr(self.app, "_set_compass_trade_plan", None)
        if callable(setter):
            setter(row["plan"])
        destination = row.get("destination")
        if destination:
            self._copy_text(destination)
            self.result_status.config(text=f"Active plan set · copied {destination}", fg=self.UI_OK)
        self._refresh_summary()

    def copy_selected_destination(self):
        selected = self.result_tree.selection()
        row = self.result_rows.get(selected[0]) if selected else None
        destination = (row or {}).get("destination")
        if not destination:
            self.result_status.config(text="This row has no destination to copy.", fg=self.UI_WARN)
            return
        self._copy_text(destination)
        self.result_status.config(text=f"Copied destination · {destination}", fg=self.UI_OK)

    def copy_selected_details(self):
        selected = self.result_tree.selection()
        row = self.result_rows.get(selected[0]) if selected else None
        detail = (row or {}).get("detail")
        if not detail:
            self.result_status.config(text="Select a result first.", fg=self.UI_WARN)
            return
        self._copy_text(detail)
        self.result_status.config(text="Copied trade details.", fg=self.UI_OK)

    def _copy_text(self, text):
        self.win.clipboard_clear()
        self.win.clipboard_append(str(text))
        self.win.update_idletasks()

    def _set_detail(self, text):
        self.detail.configure(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        if text:
            self.detail.insert("1.0", text)
        self.detail.configure(state=tk.DISABLED)

    def _search_failed(self, title, message, token):
        if token != self._search_generation or not self.is_open():
            return
        self._set_view(self._current_view, title, message, self.UI_FAIL)
        self._log(f"Trade Assist search failed: {message}")

    # ------------------------------------------------------------------
    # Online market / independent EDDN upload status
    # ------------------------------------------------------------------

    def _start_market_services(self):
        eddn_upload.UPLOADER.set_enabled(bool(self.config.get("trade_eddn_upload_enabled", True)))

    def _toggle_eddn_upload(self):
        enabled = bool(self.eddn_upload_var.get())
        self.config["trade_eddn_upload_enabled"] = enabled
        eddn_upload.UPLOADER.set_enabled(enabled)
        save_config(self.config)
        self.refresh_status()

    def _save_trade_log_settings(self):
        try:
            retention = int(self.trade_log_retention_var.get())
        except (TypeError, ValueError):
            retention = 180
        retention = min(365, max(30, retention))
        self.trade_log_retention_var.set(str(retention))
        self.config["trade_log_auto_prune_enabled"] = bool(
            self.trade_log_auto_prune_var.get()
        )
        self.config["trade_log_retention_days"] = retention
        save_config(self.config)
        if self.trade_log_auto_prune_var.get():
            maintainer = getattr(self.app, "_schedule_trade_history_maintenance", None)
            if callable(maintainer):
                maintainer()

    def prune_trade_log_now(self):
        self._save_trade_log_settings()
        profile = self.config.get("active_commander_profile")
        retention = int(self.trade_log_retention_var.get() or 180)
        self.result_status.config(
            text=f"Pruning this commander's trade log beyond {retention} days…",
            fg=self.UI_MUTED,
        )

        def worker():
            try:
                removed = marketdb.prune_trade_history(
                    retention, profile_key=profile,
                )
                self._post_ui(
                    lambda: self._trade_log_pruned(removed, profile),
                    key="trade-log-prune",
                )
            except Exception as exc:
                self._post_ui(
                    lambda text=str(exc): self._trade_log_prune_failed(text, profile),
                    key="trade-log-prune",
                )

        threading.Thread(target=worker, name="trade-log-prune", daemon=True).start()

    def _trade_log_pruned(self, removed, profile):
        if not self.is_open() or profile != self.config.get("active_commander_profile"):
            return
        if self._current_view == "log":
            self.show_trade_log()
        else:
            self.result_status.config(
                text=f"Trade log pruned · {int(removed or 0):,} old transaction(s) removed.",
                fg=self.UI_OK,
            )

    def _trade_log_prune_failed(self, message, profile):
        if self.is_open() and profile == self.config.get("active_commander_profile"):
            self.result_status.config(text=f"Trade log prune failed: {message}", fg=self.UI_FAIL)

    def refresh_status(self, force=False):
        self._refresh_summary()
        if self._status_refresh_running:
            return
        self._status_refresh_running = True
        self._last_status_poll = time.monotonic()

        def worker():
            try:
                online = ardent.service_status(force=force)
                uploaded = eddn_upload.UPLOADER.stats()
                self._post_ui(
                    lambda: self._render_market_status(online, uploaded),
                    key="trade-assist-status",
                )
            except Exception as exc:
                self._post_ui(
                    lambda text=str(exc): self._render_status_error(text),
                    key="trade-assist-status",
                )
            finally:
                self._status_refresh_running = False

        threading.Thread(target=worker, name="trade-market-status", daemon=True).start()

    def _render_market_status(self, online, uploaded):
        if not self.is_open():
            return
        ready = bool(online.get("online"))
        self.db_badge.config(
            text="ONLINE READY" if ready else "ONLINE OFFLINE",
            bg=self.UI_OK if ready else self.UI_FAIL,
        )
        upload_text = "ON" if uploaded.get("enabled") else "OFF"
        provider = f"ARDENT {online.get('version')}" if ready else "ARDENT UNAVAILABLE"
        cache_entries = int(online.get("cache_entries") or 0)
        self.market_link_status.config(
            text=(
                f"{provider} · {cache_entries} temporary result(s) · "
                f"EDDN UPLOAD {upload_text} · {int(uploaded.get('uploads') or 0):,} sent"
            ),
            fg=self.UI_OK if ready else self.UI_FAIL,
        )
        self.eddn_upload_var.set(bool(uploaded.get("enabled")))
        if ready:
            self._hide_banner()
        else:
            self._show_banner(
                online.get("last_error")
                or "Online market service is unavailable. EDDN uploads remain independent."
            )

    def _render_status_error(self, message):
        if not self.is_open():
            return
        self.market_link_status.config(text=f"MARKET LINK ERROR · {message}", fg=self.UI_FAIL)

    def _show_banner(self, text):
        self.banner.config(text=text)
        if not self.banner.winfo_ismapped():
            self.banner.pack(fill=tk.X, before=self.summary)

    def _hide_banner(self):
        if self.banner.winfo_ismapped():
            self.banner.pack_forget()

    # ------------------------------------------------------------------
    # Formatting and teardown
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(value, limit):
        text = str(value or "")
        return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"

    @staticmethod
    def _num(value):
        try:
            return f"{float(value):,.0f}"
        except (TypeError, ValueError):
            return "?"

    @staticmethod
    def _credits(value):
        try:
            return f"{int(value):,} cr"
        except (TypeError, ValueError):
            return "? cr"

    @staticmethod
    def _age(epoch):
        try:
            minutes = max(0.0, (time.time() - float(epoch)) / 60.0)
        except (TypeError, ValueError):
            return "?"
        if minutes < 60:
            return f"{int(minutes)}m"
        if minutes < 2880:
            return f"{int(minutes / 60)}h"
        return f"{int(minutes / 1440)}d"

    def _freshness_tag(self, epoch):
        try:
            age_days = max(0.0, (time.time() - float(epoch)) / 86400.0)
        except (TypeError, ValueError):
            return ""
        return "fresh" if age_days <= 1 else ("aging" if age_days >= 7 else "")

    def _log(self, message):
        try:
            self.app.log(message)
        except Exception:
            pass

    def _on_close(self):
        try:
            if self._live_poll_after:
                self.root.after_cancel(self._live_poll_after)
                self._live_poll_after = None
            self._save_filters()
            self.config["trade_window_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        self.win.destroy()
