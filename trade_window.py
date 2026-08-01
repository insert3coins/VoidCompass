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
        self.result_rows = {}

        saved = self.config.get("trade_route_form")
        self._saved_filters = saved if isinstance(saved, dict) else {}
        self.large_pad_var = tk.BooleanVar(
            value=bool(self._saved_filters.get("large_pad", False))
        )
        self.include_carriers_var = tk.BooleanVar(
            value=bool(self._saved_filters.get("include_carriers", False))
        )
        self.eddn_upload_var = tk.BooleanVar(
            value=bool(self.config.get("trade_eddn_upload_enabled", True))
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
        for column in range(3):
            action_row.grid_columnconfigure(column, weight=1, uniform="trade-actions")
        self._action_card(
            action_row, 0, "SELL MY CARGO",
            "Find the best nearby buyer for the tradeable cargo aboard.",
            self.find_cargo_buyers, self.UI_OK,
        )
        self._action_card(
            action_row, 1, "FIND A TRADE",
            "Show three profitable departures from the current station.",
            self.find_trade, COLOR_ACCENT,
        )
        self._action_card(
            action_row, 2, "CURRENT RUN",
            "Review the active destination, transactions and real profit.",
            self.show_current_run, COLOR_ORANGE,
        )

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

    def _action_card(self, parent, column, title, description, command, colour):
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
            font=("Segoe UI", 8), anchor="w",
        ).pack(fill=tk.X, padx=11)
        button(card, "GO", command, accent=(column == 0)).pack(
            anchor="w", padx=11, pady=(8, 10)
        )

    def _build_filters(self):
        panel = tk.Frame(
            self.win, bg=self.UI_PANEL,
            highlightbackground=self.UI_BORDER, highlightthickness=1,
        )
        panel.pack(fill=tk.X, padx=10, pady=(9, 0))
        tk.Label(
            panel, text="QUICK FILTERS", fg=COLOR_ORANGE, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(11, 8), pady=8)
        self.filter_entries = {}
        for key, label, width in (
            ("radius", "SEARCH LY", 7),
            ("max_ls", "MAX LS", 7),
            ("age", "AGE DAYS", 7),
            ("min_profit", "MIN CR/T", 8),
        ):
            box = tk.Frame(panel, bg=self.UI_PANEL)
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
        self._checkbutton(panel, "Large pad", self.large_pad_var).pack(
            side=tk.LEFT, padx=(4, 0), pady=(13, 5)
        )
        self._checkbutton(panel, "Carriers", self.include_carriers_var).pack(
            side=tk.LEFT, padx=(4, 0), pady=(13, 5)
        )
        tk.Label(
            panel, text="Cargo, capital and jump range come from the live ship.",
            fg=self.UI_DIM, bg=self.UI_PANEL, font=("Segoe UI", 7),
        ).pack(side=tk.RIGHT, padx=11)

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
        self.market_link_status = tk.Label(
            panel, text="ONLINE MARKET · CHECKING", fg=self.UI_MUTED,
            bg=self.UI_PANEL, font=("Consolas", 8, "bold"), anchor="w",
        )
        self.market_link_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(9, 6), pady=6)
        self._checkbutton(
            panel, "Upload visited markets to EDDN", self.eddn_upload_var,
            self._toggle_eddn_upload,
        ).pack(side=tk.LEFT, padx=(4, 8))
        button(panel, "REFRESH", lambda: self.refresh_status(force=True)).pack(
            side=tk.LEFT, padx=(0, 7), pady=4,
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
        }
        for key, value in defaults.items():
            entry = self.filter_entries[key]
            entry.delete(0, tk.END)
            entry.insert(0, str(value))

    def _save_filters(self):
        self.config["trade_route_form"] = {
            key: entry.get().strip() for key, entry in self.filter_entries.items()
        }
        self.config["trade_route_form"].update({
            "large_pad": bool(self.large_pad_var.get()),
            "include_carriers": bool(self.include_carriers_var.get()),
        })

    def _filter_number(self, key, default, cast=float):
        try:
            value = self.filter_entries[key].get().strip()
            return cast(float(value)) if cast is int else cast(value)
        except (KeyError, TypeError, ValueError):
            return default

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
                    return current
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
                "items": items,
            }
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _ship_jump_range(self):
        ship = getattr(self.app, "cmdr_ship", {}) or {}
        try:
            return max(1.0, float(ship.get("max_jump_range") or 1.0))
        except (TypeError, ValueError):
            return 1.0

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

    def find_cargo_buyers(self):
        self._save_filters()
        cargo, excluded = self._tradeable_cargo(
            list(getattr(self.app, "current_cargo_inventory", []) or [])
        )
        if not cargo:
            note = " Mission and stolen cargo are deliberately excluded." if excluded else ""
            self._set_view("cargo", "SELL MY CARGO", "No tradeable cargo is currently aboard." + note)
            return
        if not self._current_system():
            self._set_view("cargo", "SELL MY CARGO", "Current system is not known yet.", self.UI_WARN)
            return
        self._set_view("cargo", "SELL MY CARGO", "Finding nearby buyers…")
        token = self._next_search()
        params = {
            "cargo_items": cargo,
            "system": self._current_system(),
            "star_pos": self._current_coords(),
            "radius": self._filter_number("radius", 80.0),
            "max_price_age_days": self._filter_number("age", 30, int),
            "requires_large_pad": bool(self.large_pad_var.get()),
            "include_carriers": bool(self.include_carriers_var.get()),
            "max_system_distance": self._filter_number("max_ls", 1000.0),
            "limit": 10,
        }

        def worker():
            try:
                rows = routes.sell_cargo(**params)
                self._post_ui(
                    lambda: self._render_cargo_buyers(rows, excluded, token),
                    key="trade-assist-cargo",
                )
            except Exception as exc:
                self._post_ui(
                    lambda text=str(exc): self._search_failed("SELL MY CARGO", text, token),
                    key="trade-assist-cargo",
                )

        threading.Thread(target=worker, name="trade-cargo-buyers", daemon=True).start()

    def _render_cargo_buyers(self, rows, excluded, token):
        if token != self._search_generation or not self.is_open():
            return
        self._set_view("cargo", "SELL MY CARGO", "")
        for row in list(rows or [])[:3]:
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
                "from_system": self._current_system(),
                "from_station": getattr(self.app, "current_station_name", None),
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
                f"{min(3, len(rows or []))} best buyer(s){suffix}"
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
        system = self._current_system()
        station = getattr(self.app, "current_station_name", None)
        market_id = getattr(self.app, "current_station_market_id", None)
        if not system or not station or not market_id or not getattr(self.app, "current_docked", False):
            self._set_view(
                "trade", "FIND A TRADE",
                "Dock at a market station first so the departure is unambiguous.",
                self.UI_WARN,
            )
            return
        market = self._current_market_snapshot()
        if not market:
            self._set_view(
                "trade", "FIND A TRADE",
                "Open the station Commodities Market once so Elite writes the current departure prices.",
                self.UI_WARN,
            )
            return
        max_age_days = self._filter_number("age", 30, int)
        market_updated = marketdb.parse_update_time(market.get("timestamp"))
        if not market_updated or time.time() - market_updated > max(1, max_age_days) * 86400:
            self._set_view(
                "trade", "FIND A TRADE",
                "The departure prices are older than the selected age. Open the Commodities Market to refresh them.",
                self.UI_WARN,
            )
            return
        capacity = int(getattr(self.app, "cargo_capacity", 0) or 0)
        aboard = int(getattr(self.app, "current_cargo_tons", 0) or 0)
        free_hold = max(0, capacity - aboard)
        if capacity and free_hold <= 0:
            self._set_view(
                "trade", "FIND A TRADE",
                "The cargo hold is full. Sell or transfer cargo before planning a purchase.",
                self.UI_WARN,
            )
            return
        self._set_view("trade", "FIND A TRADE", f"Scanning departures from {station}…")
        token = self._next_search()
        params = {
            "system": system,
            "star_pos": self._current_coords(),
            "radius": self._filter_number("radius", 80.0),
            "min_profit": self._filter_number("min_profit", 1000, int),
            "min_units": 1,
            "max_price_age_days": max_age_days,
            "requires_large_pad": bool(self.large_pad_var.get()),
            "include_carriers": bool(self.include_carriers_var.get()),
            "max_system_distance": self._filter_number("max_ls", 1000.0),
            "source_market_id": int(market_id),
            "source_station": station,
            "market_items": list(market.get("items") or []),
            "limit": 18,
        }
        capital = int(getattr(self.app, "cmdr_balance", 0) or 0)
        free_hold = free_hold or capacity or 64
        jump_range = self._ship_jump_range()

        def worker():
            try:
                rows = routes.find_opportunities(**params)
                ranked = []
                for row in rows:
                    buy_price = max(0, int(row.get("buy_price") or 0))
                    affordable = capital // buy_price if buy_price and capital else free_hold
                    units = min(int(row.get("units") or 0), free_hold, affordable)
                    if units <= 0:
                        continue
                    copy = dict(row)
                    copy["trade_units"] = units
                    copy["projected_profit"] = units * int(row.get("profit_each") or 0)
                    copy["estimated_jumps"] = max(
                        1, math.ceil(float(row.get("distance") or 0) / jump_range),
                    )
                    copy["achievable_score"] = (
                        copy["projected_profit"] / copy["estimated_jumps"]
                    )
                    ranked.append(copy)
                ranked.sort(
                    key=lambda item: float(item.get("achievable_score") or 0),
                    reverse=True,
                )
                self._post_ui(
                    lambda: self._render_trade_results(ranked[:3], token),
                    key="trade-assist-route",
                )
            except Exception as exc:
                self._post_ui(
                    lambda text=str(exc): self._search_failed("FIND A TRADE", text, token),
                    key="trade-assist-route",
                )

        threading.Thread(target=worker, name="trade-quick-route", daemon=True).start()

    def _render_trade_results(self, rows, token):
        if token != self._search_generation or not self.is_open():
            return
        self._set_view("trade", "FIND A TRADE", "")
        for row in rows:
            units = int(row.get("trade_units") or 0)
            profit = int(row.get("projected_profit") or 0)
            destination = f"{row.get('to_station')} / {row.get('to_system')}"
            jumps = int(row.get("estimated_jumps") or 1)
            distance = (
                f"{float(row.get('distance') or 0):.1f} ly · "
                f"{jumps} jump{'s' if jumps != 1 else ''}"
            )
            if row.get("to_dist_ls") is not None:
                distance += f" · {self._num(row.get('to_dist_ls'))} ls"
            detail = (
                f"BUY {self._num(units)} t {row.get('commodity')} at "
                f"{row.get('from_station')} ({row.get('from_system')})\n"
                f"Buy {self._credits(row.get('buy_price'))}/t · sell "
                f"{self._credits(row.get('sell_price'))}/t at {row.get('to_station')} "
                f"({row.get('to_system')})\n"
                f"Projected profit {self._credits(profit)} · "
                f"{self._credits(row.get('profit_each'))}/t · quote age {self._age(row.get('updated_at'))}"
            )
            plan = {
                "kind": "quick-trade",
                "from_system": row.get("from_system"),
                "from_station": row.get("from_station"),
                "to_system": row.get("to_system"),
                "to_station": row.get("to_station"),
                "commodity": row.get("commodity"),
                "units": units,
                "profit_cr": profit,
                "distance_ly": float(row.get("distance") or 0),
            }
            self._insert_result(
                row.get("commodity"), destination,
                f"{self._credits(row.get('profit_each'))}/t · {self._credits(profit)}",
                f"{self._num(units)} t", distance, self._age(row.get("updated_at")),
                row, detail, plan,
            )
        self.result_status.config(
            text=(
                f"{len(rows)} departure option(s), ranked by achievable profit."
                if rows else "No profitable online departure matched the selected filters."
            ),
            fg=self.UI_MUTED if rows else self.UI_WARN,
        )
        self._select_best_result()

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
        self._set_view(
            "run", "CURRENT RUN",
            f"Bought {self._num(session.get('bought_units', 0))} t · "
            f"Sold {self._num(session.get('sold_units', 0))} t · "
            f"Profit {self._credits(session.get('profit', 0))} · {plan_text}",
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
            self._set_detail(
                f"ACTIVE PLAN\n{plan_text}\n"
                f"{plan.get('commodity') or plan.get('kind') or 'Trade'} · "
                f"expected {self._credits(plan.get('profit_cr')) if plan.get('profit_cr') is not None else 'sale destination'}"
            )
        elif not events:
            self._set_detail("No trade has been recorded in this application session.")
        if not events and load_history and not self._history_loading:
            self._history_loading = True
            token = self._search_generation

            def worker():
                try:
                    rows = marketdb.recent_trades(limit=18)
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
        }.get(view, ("ITEM", "DESTINATION", "VALUE", "CARGO", "TRAVEL", "AGE"))
        for column, label in zip(self.result_tree["columns"], headings):
            self.result_tree.heading(column, text=label)

    def _insert_result(self, primary, destination, value, cargo, distance, age,
                       raw, detail, plan, tag=None):
        row_tag = tag or self._freshness_tag((raw or {}).get("updated_at"))
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
