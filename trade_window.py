import threading
import time
import tkinter as tk
import webbrowser
import os
import subprocess
import sys
from pathlib import Path
from tkinter import ttk

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, save_config
from trade import eddn, marketdb, routes, seed, spansh


class TradeWindow:
    UI_BG = "#080a0d"
    UI_PANEL = "#12161b"
    UI_PANEL_2 = "#171d23"
    UI_BORDER = "#26313a"
    UI_MUTED = "#7d8891"
    UI_DIM = "#2a333b"
    UI_OK = "#21d189"
    UI_WARN = "#ff9a3c"
    UI_FAIL = "#ff5c5c"

    _eddn_started = False

    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.config = app.config
        self.route_rows = []
        self.route_detail_by_iid = {}
        self.commodity_names = []
        self._seed_poll_after = None
        self._seed_polling = False
        self._live_poll_after = None
        self._last_db_poll = 0
        self.market_sort = ("sell", -1)
        self.market_analysis = {}
        self.market_rows = {}
        self.commodity_rows = {}
        self.radar_rows = {}
        self.cargo_sell_rows = {}
        self.watchlist_rows = {}
        self.loop_mode = tk.StringVar(value="loop")
        self.search_mode = tk.StringVar(value="sell")
        self.allow_planetary_var = tk.BooleanVar(value=True)
        self.unique_route_var = tk.BooleanVar(value=False)
        self.include_carriers_var = tk.BooleanVar(value=False)
        self.radar_large_pad_var = tk.BooleanVar(value=False)
        self.radar_include_carriers_var = tk.BooleanVar(value=False)
        self.win = tk.Toplevel(root)
        self.win.title("Trade")
        self.win.geometry(self.config.get("trade_window_geometry", "1080x700"))
        self.win.configure(bg=self.UI_BG)
        self.win.minsize(900, 560)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self._start_eddn()
        self._seed_defaults()
        self.refresh_status()
        self._schedule_live_poll()

    def is_open(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False

    def lift(self):
        self.win.lift()
        self.win.focus_force()

    def _build(self):
        header = tk.Frame(self.win, bg="#0c1014", height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        title_box = tk.Frame(header, bg="#0c1014")
        title_box.pack(side=tk.LEFT, fill=tk.Y, padx=14)
        tk.Label(title_box, text="ELITE TRADER", font=("Segoe UI", 16, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(anchor="w", pady=(10, 0))
        self.subtitle = tk.Label(title_box, text="", font=("Consolas", 8), fg=self.UI_MUTED, bg="#0c1014")
        self.subtitle.pack(anchor="w", pady=(2, 0))
        self.db_badge = tk.Label(header, text="DB CHECKING", font=("Segoe UI", 8, "bold"), fg="black", bg=self.UI_DIM, padx=10, pady=4)
        self.db_badge.pack(side=tk.RIGHT, padx=14)
        self.commander_badge = tk.Label(header, text=getattr(self.app, "cmdr_name", "") or "CMDR", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT, bg="#0c1014")
        self.commander_badge.pack(side=tk.RIGHT, padx=(0, 8))

        self.banner = tk.Label(self.win, text="", bg="#4a2c00", fg=self.UI_WARN, font=("Segoe UI", 9), anchor="w", padx=14, pady=6)

        style = ttk.Style(self.win)
        style.theme_use("default")
        style.configure("Trade.TNotebook", background=self.UI_BG, borderwidth=0)
        style.configure("Trade.TNotebook.Tab", background=self.UI_PANEL, foreground=COLOR_TEXT, padding=(12, 7), borderwidth=0)
        style.map("Trade.TNotebook.Tab", background=[("selected", self.UI_PANEL_2)], foreground=[("selected", COLOR_ACCENT)])
        style.configure("Trade.Treeview", background="#0b0f13", foreground=COLOR_TEXT, fieldbackground="#0b0f13", rowheight=24, borderwidth=0)
        style.configure("Trade.Treeview.Heading", background=self.UI_PANEL, foreground=COLOR_ORANGE, relief="flat", font=("Segoe UI", 8, "bold"))
        style.map("Trade.Treeview", background=[("selected", "#12313c")], foreground=[("selected", COLOR_TEXT)])

        self.summary = tk.Frame(self.win, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1, bd=0)
        self.summary.pack(fill=tk.X, padx=10, pady=(10, 0))
        tk.Frame(self.summary, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        inner = tk.Frame(self.summary, bg=self.UI_PANEL)
        inner.pack(fill=tk.X, padx=12, pady=10)
        self.system_value = self._summary_stat(inner, "CURRENT SYSTEM", "---", COLOR_ACCENT)
        self.station_value = self._summary_stat(inner, "STATION", "---", COLOR_TEXT)
        self.credits_value = self._summary_stat(inner, "CREDITS", "---", COLOR_ORANGE)
        self.cargo_value = self._summary_stat(inner, "CARGO", "---", COLOR_TEXT)
        self.fuel_value = self._summary_stat(inner, "FUEL", "---", COLOR_TEXT)
        self.legal_value = self._summary_stat(inner, "LEGAL", "---", COLOR_TEXT)
        self.jump_value = self._summary_stat(inner, "JUMP", "---", COLOR_TEXT)
        self.destination_value = self._summary_stat(inner, "DESTINATION", "---", COLOR_TEXT)

        self.tabs = ttk.Notebook(self.win, style="Trade.TNotebook")
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._build_radar_tab()
        self._build_routes_tab()
        self._build_commodity_tab()
        self._build_local_tab()
        self._build_watchlist_tab()
        self._build_database_tab()
        self._build_footer()

    def _summary_stat(self, parent, label, value, fg):
        box = tk.Frame(parent, bg=self.UI_PANEL)
        box.pack(side=tk.LEFT, padx=(0, 28))
        tk.Label(box, text=label, fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        lbl = tk.Label(box, text=value, fg=fg, bg=self.UI_PANEL, font=("Segoe UI", 12, "bold"))
        lbl.pack(anchor="w")
        return lbl

    def _card(self, parent, title, subtitle=""):
        card = tk.Frame(parent, bg=self.UI_PANEL, highlightbackground=self.UI_BORDER, highlightthickness=1, bd=0)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        tk.Frame(card, bg=COLOR_ACCENT, height=2).pack(fill=tk.X)
        head = tk.Frame(card, bg=self.UI_PANEL)
        head.pack(fill=tk.X, padx=12, pady=(10, 4))
        text = title if not subtitle else f"{title}  {subtitle}"
        tk.Label(head, text=text, fg=COLOR_ORANGE, bg=self.UI_PANEL, font=("Segoe UI", 8, "bold"), anchor="w").pack(side=tk.LEFT)
        body = tk.Frame(card, bg=self.UI_PANEL)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        return body

    def _build_footer(self):
        footer = tk.Frame(self.win, bg=self.UI_BG)
        footer.pack(fill=tk.X, padx=10, pady=(0, 8))
        tk.Label(footer, text="External lookups:", fg=self.UI_MUTED, bg=self.UI_BG, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        for label, site in (
            ("Inara Routes", "inara_routes"),
            ("Inara Commodities", "inara_commodities"),
            ("Inara System", "inara_system"),
            ("EDSM", "edsm"),
            ("Spansh", "spansh"),
        ):
            self._button(footer, label, lambda s=site: self.open_external(s)).pack(side=tk.LEFT, padx=(6, 0))
        tk.Label(
            footer,
            text="Trade data: Spansh galaxy dump + EDDN + local journal Market.json",
            fg=self.UI_MUTED,
            bg=self.UI_BG,
            font=("Segoe UI", 8),
        ).pack(side=tk.RIGHT)

    def _button(self, parent, text, cmd, accent=False):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=COLOR_ACCENT if accent else self.UI_PANEL,
            fg="black" if accent else COLOR_TEXT,
            activebackground=COLOR_ACCENT if accent else self.UI_PANEL_2,
            activeforeground="black" if accent else COLOR_ACCENT,
            relief=tk.FLAT, bd=0, padx=10, pady=5,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )

    def _entry(self, parent, width=10):
        return tk.Entry(parent, width=width, bg=self.UI_PANEL_2, fg=COLOR_TEXT, insertbackground=COLOR_ACCENT, relief=tk.FLAT, highlightthickness=1, highlightbackground=self.UI_BORDER, highlightcolor=COLOR_ACCENT)

    def _label(self, parent, text):
        tk.Label(parent, text=text, fg=self.UI_MUTED, bg=parent.cget("bg"), font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(10, 4))

    def _field(self, parent, key, label, width=9):
        box = tk.Frame(parent, bg=parent.cget("bg"))
        box.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 6))
        lbl = tk.Label(box, text=label, fg=self.UI_MUTED, bg=parent.cget("bg"), font=("Segoe UI", 7, "bold"))
        lbl.pack(anchor="w")
        ent = self._entry(box, width)
        ent.pack(anchor="w")
        self.route_entries[key] = ent
        if not hasattr(self, "route_field_boxes"):
            self.route_field_boxes = {}
        self.route_field_boxes[key] = (box, lbl, ent)
        ent.bind("<FocusOut>", lambda _e: self._save_route_form())
        ent.bind("<Return>", lambda _e: self._save_route_form())
        return ent

    def _style_option(self, menu):
        menu.configure(bg=self.UI_PANEL_2, fg=COLOR_TEXT, activebackground=self.UI_PANEL_2, activeforeground=COLOR_ACCENT, relief=tk.FLAT, bd=0, highlightthickness=1, highlightbackground=self.UI_BORDER)
        try:
            menu["menu"].configure(bg=self.UI_PANEL_2, fg=COLOR_TEXT, activebackground=COLOR_ACCENT, activeforeground="black")
        except Exception:
            pass
        return menu

    def _tree(self, parent, cols, specs):
        wrap = tk.Frame(parent, bg=parent.cget("bg"))
        wrap.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(wrap, columns=cols, show="headings", style="Trade.Treeview")
        for col in cols:
            label, width, anchor = specs[col]
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._configure_tree_tags(tree)
        return tree

    def _configure_tree_tags(self, tree):
        tree.tag_configure("fresh", foreground=COLOR_TEXT)
        tree.tag_configure("stale", foreground=self.UI_WARN)
        tree.tag_configure("old", foreground=self.UI_FAIL)

    def _freshness_tag(self, epoch):
        try:
            age_days = (time.time() - float(epoch)) / 86400.0
            if age_days <= 2:
                return "fresh"
            if age_days <= 14:
                return "stale"
            return "old"
        except Exception:
            return ""

    def _copy_text(self, text, label="Copied"):
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(text))
            self._show_banner(f"{label} copied to clipboard.")
        except Exception as exc:
            self._show_banner(f"Copy failed: {exc}")

    def _copy_selected_tree(self, tree, row_map, label="Selection"):
        selected = tree.selection()
        if not selected:
            self._show_banner("Select a row first.")
            return
        row = row_map.get(selected[0])
        if isinstance(row, str):
            self._copy_text(row, label)
        elif row:
            self._copy_text(" | ".join(f"{k}: {v}" for k, v in row.items() if v not in (None, "")), label)

    def _copy_route_detail(self):
        selected = self.route_tree.selection()
        text = self.route_detail_by_iid.get(selected[0], "") if selected else self.route_detail.get("1.0", tk.END).strip()
        self._copy_text(text, "Route detail")

    def _build_radar_tab(self):
        frame = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(frame, text="Radar")
        wrap = tk.Frame(frame, bg=self.UI_BG)
        wrap.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(wrap, bg=self.UI_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        right = tk.Frame(wrap, bg=self.UI_BG)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        radar = self._card(left, "OPPORTUNITY RADAR", "profitable nearby station-to-station flows")
        controls = tk.Frame(radar, bg=self.UI_PANEL)
        controls.pack(fill=tk.X, pady=(0, 8))
        self.radar_radius = self._simple_field(controls, "RADIUS LY", 7)
        self.radar_min_profit = self._simple_field(controls, "MIN CR/T", 8)
        self.radar_min_units = self._simple_field(controls, "MIN UNITS", 7)
        self.radar_limit = self._simple_field(controls, "RESULTS", 6)
        tk.Checkbutton(controls, text="Large pad", variable=self.radar_large_pad_var, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL).pack(side=tk.LEFT, padx=8, pady=(12, 6))
        tk.Checkbutton(controls, text="Carriers", variable=self.radar_include_carriers_var, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL).pack(side=tk.LEFT, padx=8, pady=(12, 6))
        self._button(controls, "Scan", self.refresh_radar, accent=True).pack(side=tk.LEFT, padx=(8, 0), pady=(12, 6))
        self._button(controls, "Copy", lambda: self._copy_selected_tree(self.radar_tree, self.radar_rows, "Radar row")).pack(side=tk.LEFT, padx=(6, 0), pady=(12, 6))
        self.radar_status = tk.Label(radar, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 9), anchor="w")
        self.radar_status.pack(fill=tk.X, pady=(0, 6))
        self.radar_tree = self._tree(radar, ("commodity", "profit", "units", "from", "to", "dist", "age"), {
            "commodity": ("Commodity", 160, tk.W),
            "profit": ("Profit/t", 85, tk.E),
            "units": ("Units", 70, tk.E),
            "from": ("Buy From", 210, tk.W),
            "to": ("Sell To", 210, tk.W),
            "dist": ("Leg", 70, tk.E),
            "age": ("Age", 60, tk.E),
        })

        cargo = self._card(right, "CARGO SELL FINDER", "best nearby buyers for what is in your hold")
        row = tk.Frame(cargo, bg=self.UI_PANEL)
        row.pack(fill=tk.X, pady=(0, 8))
        self._button(row, "Find Buyers", self.refresh_cargo_sellers, accent=True).pack(side=tk.LEFT, pady=(0, 6))
        self._button(row, "Copy", lambda: self._copy_selected_tree(self.cargo_sell_tree, self.cargo_sell_rows, "Cargo sell row")).pack(side=tk.LEFT, padx=(6, 0), pady=(0, 6))
        self.cargo_sell_status = tk.Label(row, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 9), anchor="w")
        self.cargo_sell_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=(5, 0))
        self.cargo_sell_tree = self._tree(cargo, ("commodity", "count", "station", "system", "price", "sale", "jump", "age"), {
            "commodity": ("Cargo", 150, tk.W),
            "count": ("Tons", 55, tk.E),
            "station": ("Station", 180, tk.W),
            "system": ("System", 160, tk.W),
            "price": ("Sell", 80, tk.E),
            "sale": ("Est Sale", 90, tk.E),
            "jump": ("Jump", 65, tk.E),
            "age": ("Age", 55, tk.E),
        })

        session = self._card(right, "TRADE SESSION", "journal buy/sell events since app start")
        self.session_status = tk.Label(session, text="", fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Consolas", 10), justify=tk.LEFT, anchor="w")
        self.session_status.pack(fill=tk.X, pady=(0, 6))
        self.session_tree = self._tree(session, ("time", "event", "commodity", "count", "price", "profit"), {
            "time": ("Time", 70, tk.W),
            "event": ("Type", 55, tk.CENTER),
            "commodity": ("Commodity", 160, tk.W),
            "count": ("Tons", 55, tk.E),
            "price": ("Price", 80, tk.E),
            "profit": ("Profit", 90, tk.E),
        })

    def _build_routes_tab(self):
        frame = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(frame, text="Trade Routes")
        body = self._card(frame, "TRADE ROUTES", "computed locally, with Spansh fallback for chain routes")
        controls = tk.Frame(body, bg=self.UI_PANEL)
        controls.pack(fill=tk.X, pady=(0, 8))
        self.route_entries = {}
        type_box = tk.Frame(controls, bg=self.UI_PANEL)
        type_box.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 6))
        tk.Label(type_box, text="TYPE", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        self._style_option(tk.OptionMenu(type_box, self.loop_mode, "loop", "chain")).pack(anchor="w")
        self.loop_mode.trace_add("write", lambda *_: self._on_route_mode_changed())
        start = self._field(controls, "system", "START SYSTEM", 18)
        start.bind("<Return>", lambda _e: self.find_routes())
        self._button(controls, "Use Current", self.use_current_system).pack(side=tk.LEFT, padx=(0, 8), pady=(12, 6))
        for key, label, width in (
            ("capital", "CAPITAL", 10),
            ("cargo", "CARGO", 6),
            ("radius", "SEARCH LY", 7),
            ("max_leg", "MAX LEG", 7),
            ("jump", "JUMP LY", 7),
            ("results", "RESULTS", 6),
            ("hops", "HOPS", 5),
            ("min_units", "MIN UNITS", 7),
            ("max_ls", "MAX LS", 7),
            ("age", "AGE DAYS", 7),
        ):
            self._field(controls, key, label, width)
        self.large_pad_var = tk.BooleanVar(value=False)
        tk.Checkbutton(controls, text="Large pad", variable=self.large_pad_var, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL, command=self._save_route_form).pack(side=tk.LEFT, padx=8, pady=(12, 6))
        tk.Checkbutton(controls, text="Carriers", variable=self.include_carriers_var, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL, command=self._save_route_form).pack(side=tk.LEFT, padx=8, pady=(12, 6))
        self.allow_planetary_check = tk.Checkbutton(controls, text="Planetary", variable=self.allow_planetary_var, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL, command=self._save_route_form)
        self.allow_planetary_check.pack(side=tk.LEFT, padx=8, pady=(12, 6))
        self.unique_route_check = tk.Checkbutton(controls, text="Unique", variable=self.unique_route_var, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL, command=self._save_route_form)
        self.unique_route_check.pack(side=tk.LEFT, padx=8, pady=(12, 6))
        self._button(controls, "Find Routes", self.find_routes, accent=True).pack(side=tk.LEFT, padx=(8, 0), pady=(12, 6))
        self._button(controls, "Copy", self._copy_route_detail).pack(side=tk.LEFT, padx=(6, 0), pady=(12, 6))

        self.route_status = tk.Label(body, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 9), anchor="w")
        self.route_status.pack(fill=tk.X, pady=(0, 6))
        self.route_tree = self._tree(body, ("kind", "from", "to", "profit", "metric", "distance"), {
            "kind": ("Type", 80, tk.CENTER),
            "from": ("From", 250, tk.W),
            "to": ("To", 250, tk.W),
            "profit": ("Profit", 110, tk.E),
            "metric": ("Rate / Trip", 120, tk.E),
            "distance": ("Distance", 90, tk.E),
        })
        self.route_tree.bind("<<TreeviewSelect>>", self._on_route_selected)
        self.route_detail = tk.Text(body, height=9, bg="#0b0f13", fg=COLOR_TEXT, relief=tk.FLAT, padx=10, pady=8, font=("Consolas", 9), wrap=tk.WORD)
        self.route_detail.pack(fill=tk.X, pady=(8, 0))
        self.route_detail.configure(state=tk.DISABLED)

    def _build_commodity_tab(self):
        frame = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(frame, text="Commodities")
        body = self._card(frame, "COMMODITY SEARCH", "local database: where to buy or sell near you")
        controls = tk.Frame(body, bg=self.UI_PANEL)
        controls.pack(fill=tk.X, pady=(0, 8))
        combo_box = tk.Frame(controls, bg=self.UI_PANEL)
        combo_box.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 6))
        tk.Label(combo_box, text="COMMODITY", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        self.commodity_entry = ttk.Combobox(combo_box, width=24, values=[], state="normal")
        self.commodity_entry.pack(anchor="w")
        self.commodity_entry.bind("<Return>", lambda _e: self.search_commodity())
        mode_box = tk.Frame(controls, bg=self.UI_PANEL)
        mode_box.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 6))
        tk.Label(mode_box, text="I WANT TO", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        self._style_option(tk.OptionMenu(mode_box, self.search_mode, "sell", "buy")).pack(anchor="w")
        self.commodity_radius = self._simple_field(controls, "RADIUS LY", 7)
        self.commodity_min = self._simple_field(controls, "MIN UNITS", 7)
        self.commodity_limit = self._simple_field(controls, "RESULTS", 6)
        self.commodity_large_pad = tk.BooleanVar(value=False)
        self.commodity_include_carriers = tk.BooleanVar(value=False)
        tk.Checkbutton(controls, text="Large pad", variable=self.commodity_large_pad, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL).pack(side=tk.LEFT, padx=8, pady=(12, 6))
        tk.Checkbutton(controls, text="Carriers", variable=self.commodity_include_carriers, bg=self.UI_PANEL, fg=COLOR_TEXT, selectcolor=self.UI_PANEL_2, activebackground=self.UI_PANEL).pack(side=tk.LEFT, padx=8, pady=(12, 6))
        self._button(controls, "Search", self.search_commodity, accent=True).pack(side=tk.LEFT, padx=(8, 0), pady=(12, 6))
        self._button(controls, "Copy", lambda: self._copy_selected_tree(self.commodity_tree, getattr(self, "commodity_rows", {}), "Commodity row")).pack(side=tk.LEFT, padx=(6, 0), pady=(12, 6))
        self.commodity_status = tk.Label(body, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 9), anchor="w")
        self.commodity_status.pack(fill=tk.X, pady=(0, 6))
        self.commodity_tree = self._tree(body, ("station", "system", "price", "units", "jump", "ls", "age", "pad"), {
            "station": ("Station", 260, tk.W),
            "system": ("System", 220, tk.W),
            "price": ("Price", 90, tk.E),
            "units": ("Units", 90, tk.E),
            "jump": ("Jump", 80, tk.E),
            "ls": ("Star Dist", 90, tk.E),
            "age": ("Age", 70, tk.E),
            "pad": ("Pad", 50, tk.CENTER),
        })

    def _simple_field(self, parent, label, width=10):
        box = tk.Frame(parent, bg=parent.cget("bg"))
        box.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 6))
        tk.Label(box, text=label, fg=self.UI_MUTED, bg=parent.cget("bg"), font=("Segoe UI", 7, "bold")).pack(anchor="w")
        ent = self._entry(box, width)
        ent.pack(anchor="w")
        return ent

    def _build_local_tab(self):
        frame = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(frame, text="Local")
        wrap = tk.Frame(frame, bg=self.UI_BG)
        wrap.pack(fill=tk.BOTH, expand=True)
        left_col = tk.Frame(wrap, bg=self.UI_BG)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        right_col = tk.Frame(wrap, bg=self.UI_BG)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(5, 0))
        left = self._card(left_col, "STATION MARKET", "from Market.json after opening commodities")
        filter_row = tk.Frame(left, bg=self.UI_PANEL)
        filter_row.pack(fill=tk.X, pady=(0, 6))
        self.market_filter = self._simple_field(filter_row, "FILTER", 18)
        self.market_filter.bind("<KeyRelease>", lambda _e: self.refresh_local())
        self.local_market_status = tk.Label(filter_row, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 9), anchor="w")
        self.local_market_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=(13, 0))
        self.market_tree = self._tree(left, ("name", "sell", "buy", "demand", "stock", "signal", "note"), {
            "name": ("Commodity", 250, tk.W),
            "sell": ("Sell", 90, tk.E),
            "buy": ("Buy", 90, tk.E),
            "demand": ("Demand", 90, tk.E),
            "stock": ("Stock", 90, tk.E),
            "signal": ("Signal", 75, tk.CENTER),
            "note": ("Analyzer", 260, tk.W),
        })
        for col in ("name", "sell", "buy", "demand", "stock"):
            self.market_tree.heading(col, command=lambda c=col: self.sort_market(c))
        self._button(filter_row, "Analyze", self.analyze_local_market).pack(side=tk.LEFT, padx=(6, 0), pady=(10, 0))
        self._button(filter_row, "Copy", lambda: self._copy_selected_tree(self.market_tree, getattr(self, "market_rows", {}), "Market row")).pack(side=tk.LEFT, padx=(6, 0), pady=(10, 0))

        jumps = self._card(right_col, "JUMP HISTORY", "recent session jumps")
        self.jump_tree = self._tree(jumps, ("system", "distance", "age"), {
            "system": ("System", 220, tk.W),
            "distance": ("Dist", 80, tk.E),
            "age": ("When", 70, tk.E),
        })

        right = self._card(right_col, "CARGO HOLD", "current journal cargo")
        self.cargo_tree = self._tree(right, ("name", "count"), {
            "name": ("Commodity", 220, tk.W),
            "count": ("Units", 80, tk.E),
        })

    def _build_database_tab(self):
        frame = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(frame, text="Database")
        panel = self._card(frame, "MARKET DATABASE", "local trade data seeded from Spansh and updated by EDDN/journal markets")
        self.db_status = tk.Label(panel, text="", fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Consolas", 9), justify=tk.LEFT, anchor="w")
        self.db_status.pack(fill=tk.X, padx=12, pady=8)
        self.seed_progress = ttk.Progressbar(panel, mode="determinate", maximum=100)
        self.seed_progress.pack(fill=tk.X, padx=12, pady=(0, 10))
        self.seed_progress.pack_forget()
        row = tk.Frame(panel, bg=self.UI_PANEL)
        row.pack(fill=tk.X, padx=12, pady=(0, 12))
        self.seed_btn = self._button(row, "Open Market Builder", self.open_market_builder, accent=True)
        self.seed_btn.pack(side=tk.LEFT)
        self._button(row, "Refresh Status", self.refresh_status).pack(side=tk.LEFT)

    def _seed_defaults(self):
        defaults = {
            "system": self._current_system() or "",
            "capital": getattr(self.app, "cmdr_balance", None) or 1000000,
            "cargo": getattr(self.app, "cargo_capacity", None) or 64,
            "radius": 100,
            "max_leg": 80,
            "jump": ((getattr(self.app, "cmdr_ship", {}) or {}).get("max_jump_range") or 30),
            "results": 8,
            "hops": 4,
            "min_units": getattr(self.app, "cargo_capacity", None) or 64,
            "max_ls": 1000,
            "age": 30,
        }
        saved = self.config.get("trade_route_form") or {}
        defaults.update({k: v for k, v in saved.items() if k in defaults})
        if "mode" in saved:
            self.loop_mode.set(saved.get("mode") or "loop")
        if "large_pad" in saved:
            self.large_pad_var.set(bool(saved.get("large_pad")))
        if "include_carriers" in saved:
            self.include_carriers_var.set(bool(saved.get("include_carriers")))
        if "allow_planetary" in saved:
            self.allow_planetary_var.set(bool(saved.get("allow_planetary")))
        if "unique" in saved:
            self.unique_route_var.set(bool(saved.get("unique")))
        for key, value in defaults.items():
            self.route_entries[key].delete(0, tk.END)
            if isinstance(value, str):
                text = value
            else:
                text = str(int(value) if isinstance(value, int) or float(value).is_integer() else value)
            self.route_entries[key].insert(0, text)
        self.commodity_radius.insert(0, "50")
        self.commodity_min.insert(0, str(getattr(self.app, "cargo_capacity", None) or 64))
        self.commodity_limit.insert(0, "40")
        self.radar_radius.insert(0, "80")
        self.radar_min_profit.insert(0, "1000")
        self.radar_min_units.insert(0, str(getattr(self.app, "cargo_capacity", None) or 32))
        self.radar_limit.insert(0, "50")
        self.load_commodity_list()
        self.refresh_local()
        self.refresh_session()
        self.refresh_watchlist()
        self._on_route_mode_changed(save=False)

    def _save_route_form(self):
        form = {key: ent.get().strip() for key, ent in self.route_entries.items()}
        form.update({
            "mode": self.loop_mode.get(),
            "large_pad": self.large_pad_var.get(),
            "include_carriers": self.include_carriers_var.get(),
            "allow_planetary": self.allow_planetary_var.get(),
            "unique": self.unique_route_var.get(),
        })
        self.config["trade_route_form"] = form

    def _set_route_field_enabled(self, key, enabled):
        item = getattr(self, "route_field_boxes", {}).get(key)
        if not item:
            return
        _box, lbl, ent = item
        ent.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        lbl.configure(fg=self.UI_MUTED if enabled else self.UI_DIM)

    def _on_route_mode_changed(self, save=True):
        mode = self.loop_mode.get()
        for key in ("max_leg", "jump", "results"):
            self._set_route_field_enabled(key, mode == "loop")
        for key in ("hops",):
            self._set_route_field_enabled(key, mode == "chain")
        state = tk.NORMAL if mode == "chain" else tk.DISABLED
        self.allow_planetary_check.configure(state=state)
        self.unique_route_check.configure(state=state)
        if save:
            self._save_route_form()

    def use_current_system(self):
        current = self._current_system()
        if not current:
            self.route_status.config(text="No current system known yet.", fg=self.UI_WARN)
            return
        self.route_entries["system"].delete(0, tk.END)
        self.route_entries["system"].insert(0, current)

    def _start_eddn(self):
        if TradeWindow._eddn_started:
            return
        try:
            import zmq  # noqa: F401
            eddn.LISTENER.start()
            TradeWindow._eddn_started = True
        except Exception as exc:
            self._log(f"EDDN disabled: {exc}")

    def _current_system(self):
        system = getattr(self.app, "current_sys", None)
        return system if system and system not in ("---", "Unknown") else None

    def _current_coords(self):
        coords = getattr(self.app, "current_coords", None)
        return coords if isinstance(coords, (list, tuple)) and len(coords) >= 3 else None

    def _get_num(self, entries, key, default, cast=float):
        try:
            raw = entries[key].get().strip()
            if raw == "":
                return default
            return cast(float(raw)) if cast is int else cast(raw)
        except Exception:
            return default

    def refresh_status(self):
        self._refresh_summary()
        def worker():
            try:
                conn = marketdb.connect()
                try:
                    info = marketdb.status(conn)
                finally:
                    conn.close()
                eddn_stats = eddn.LISTENER.stats()
                seed_info = seed.SEEDER.progress()
                self.root.after(0, lambda: self._render_status(info, eddn_stats, seed_info))
            except Exception as exc:
                self.root.after(0, lambda: self._set_db_text(f"Database status failed: {exc}", self.UI_FAIL))
        threading.Thread(target=worker, daemon=True).start()

    def _schedule_live_poll(self, delay_ms=1500):
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
        self._refresh_summary()
        self.refresh_local()
        self.refresh_session()
        now = time.time()
        if now - self._last_db_poll >= 5.0:
            self._last_db_poll = now
            self.refresh_status()
        self._schedule_live_poll()

    def _render_status(self, info, eddn_stats, seed_info):
        ready = bool(info.get("ready"))
        self.db_badge.config(text="DB READY" if ready else "DB EMPTY", bg=self.UI_OK if ready else self.UI_WARN)
        self.subtitle.config(text=f"{self._current_system() or 'No current system'} | trade data: Spansh dump + EDDN + journal markets")
        phase = seed_info.get("phase")
        if phase in ("starting", "downloading", "importing"):
            self.seed_btn.config(state=tk.DISABLED)
            self._show_seed_progress()
        else:
            self.seed_btn.config(state=tk.NORMAL, text="Open Market Builder")
            if self.seed_progress.winfo_ismapped():
                self.seed_progress.pack_forget()
        eddn_txt = "connected" if eddn_stats.get("connected") else "offline/reconnecting"
        if phase == "starting":
            self.seed_progress.configure(mode="indeterminate")
            self.seed_progress.start(12)
            seed_txt = "Starting worker process"
            self.seed_btn.config(text="Starting...")
        elif phase == "downloading":
            total = seed_info.get("total_mb") or 0
            done = seed_info.get("downloaded_mb") or 0
            pct = int((done / total) * 100) if total else 0
            try:
                self.seed_progress.stop()
            except Exception:
                pass
            self.seed_progress.configure(mode="determinate", value=pct)
            seed_txt = f"Downloading Spansh dump: {done} / {total} MB ({pct}%)"
            self.seed_btn.config(text=f"Downloading {pct}%")
        elif phase == "importing":
            self.seed_progress.configure(mode="indeterminate")
            self.seed_progress.start(12)
            seed_txt = f"Importing: {seed_info.get('systems_done'):,} systems, {seed_info.get('stations_done'):,} stations"
            self.seed_btn.config(text=f"Importing {seed_info.get('stations_done'):,} markets")
        elif phase == "error":
            try:
                self.seed_progress.stop()
            except Exception:
                pass
            seed_txt = f"Seed error: {seed_info.get('error')}"
            self.seed_btn.config(text="Open Market Builder")
        else:
            try:
                self.seed_progress.stop()
            except Exception:
                pass
            seed_txt = f"Seeded: {info.get('seeded_at') or 'not yet'}"
        if phase in ("starting", "downloading", "importing"):
            mode_txt = "low impact" if seed_info.get("polite", True) else "fast"
            self._show_banner(f"{seed_txt} ({mode_txt} mode)")
        elif not ready:
            self._show_banner("Market database is empty. Chain routes can use Spansh, but loops and commodity search need the local database.")
        else:
            self._hide_banner()
        self._set_db_text(
            f"{info.get('stations', 0):,} stations | {info.get('commodity_rows', 0):,} price rows | {info.get('db_size_mb', 0)} MB\n"
            f"{seed_txt} | mode: {'low impact' if seed_info.get('polite', True) else 'fast'}\n"
            f"EDDN: {eddn_txt} | updated this session: {eddn_stats.get('markets_updated', 0):,} | skipped unknown: {eddn_stats.get('skipped_unknown', 0):,}\n"
            f"Journal markets: {info.get('journal_market_updated_at') or 'not yet'}\n"
            f"DB: {info.get('db_path')}",
            self.UI_MUTED if ready else self.UI_WARN,
        )
        if phase in ("starting", "downloading", "importing"):
            self.root.after(1600, self.refresh_status)

    def _set_db_text(self, text, fg=None):
        self.db_status.config(text=text, fg=fg or COLOR_TEXT)

    def _show_seed_progress(self):
        if not self.seed_progress.winfo_ismapped():
            self.seed_progress.pack(fill=tk.X, padx=12, pady=(0, 10))

    def _schedule_seed_poll(self, delay_ms=800):
        if not self.is_open():
            self._seed_polling = False
            return
        if self._seed_poll_after:
            try:
                self.root.after_cancel(self._seed_poll_after)
            except Exception:
                pass
        self._seed_polling = True
        self._seed_poll_after = self.root.after(delay_ms, self._seed_poll_tick)

    def _seed_poll_tick(self):
        self._seed_poll_after = None
        self.refresh_status()
        phase = seed.SEEDER.progress().get("phase")
        if phase in ("starting", "downloading", "importing", "idle"):
            self._schedule_seed_poll(1000)
        else:
            self._seed_polling = False

    def _show_banner(self, text):
        self.banner.config(text=text)
        if not self.banner.winfo_ismapped():
            self.banner.pack(fill=tk.X, before=self.summary)

    def _hide_banner(self):
        if self.banner.winfo_ismapped():
            self.banner.pack_forget()

    def open_external(self, site):
        system = self._current_system() or self.route_entries.get("system").get().strip()
        if not system:
            self._show_banner("No system known yet for external lookup.")
            return
        q = system.replace(" ", "+")
        urls = {
            "inara_routes": f"https://inara.cz/elite/market-traderoutes/?formbrief=1&ps1={q}",
            "inara_commodities": f"https://inara.cz/elite/commodities/?formbrief=1&ps1={q}",
            "inara_system": f"https://inara.cz/elite/starsystem/?search={q}",
            "edsm": f"https://www.edsm.net/en/system?systemName={q}",
            "spansh": "https://spansh.co.uk/trade",
        }
        webbrowser.open(urls[site])

    def _refresh_summary(self):
        self.system_value.config(text=self._current_system() or "---")
        station = getattr(self.app, "current_station_name", None) or "---"
        self.station_value.config(text=station)
        self.credits_value.config(text=self._credits(getattr(self.app, "cmdr_balance", None)) if getattr(self.app, "cmdr_balance", None) else "---")
        cargo_cap = getattr(self.app, "cargo_capacity", None) or 0
        cargo_now = getattr(self.app, "current_cargo_tons", None)
        if cargo_now is None:
            cargo_now = sum(int(i.get("Count", i.get("count", 0)) or 0) for i in getattr(self.app, "current_cargo_inventory", []) or [])
        self.cargo_value.config(text=f"{cargo_now}/{cargo_cap} t" if cargo_cap else f"{cargo_now} t")
        fuel = getattr(self.app, "current_fuel_main", None)
        reservoir = getattr(self.app, "current_fuel_reservoir", None)
        if fuel is not None:
            fuel_txt = f"{float(fuel):.1f}"
            if reservoir is not None:
                fuel_txt += f" + {float(reservoir):.1f}"
        else:
            fuel_txt = "---"
        self.fuel_value.config(text=fuel_txt)
        self.legal_value.config(text=getattr(self.app, "current_legal_state", None) or "---")
        jump = ((getattr(self.app, "cmdr_ship", {}) or {}).get("max_jump_range") or None)
        self.jump_value.config(text=f"{float(jump):.1f} ly" if jump else "---")
        self.destination_value.config(text=getattr(self.app, "current_destination", None) or "---")
        self.commander_badge.config(text=getattr(self.app, "cmdr_name", "") or "CMDR")

    def load_commodity_list(self):
        def worker():
            try:
                names = routes.list_commodities()
                self.root.after(0, lambda: self._render_commodity_names(names))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _render_commodity_names(self, names):
        self.commodity_names = list(names or [])
        try:
            self.commodity_entry.configure(values=[c.get("name") for c in self.commodity_names if c.get("name")])
        except Exception:
            pass
        if self.commodity_names and not self.commodity_entry.get().strip():
            self.commodity_status.config(text=f"{len(self.commodity_names):,} commodities loaded. Type a name, e.g. Gold.", fg=self.UI_MUTED)

    def refresh_local(self):
        if not hasattr(self, "market_tree"):
            return
        for tree in (self.market_tree, self.cargo_tree, self.jump_tree):
            for iid in tree.get_children():
                tree.delete(iid)
        self.market_rows = {}
        market = getattr(self.app, "current_trade_market", None) or {}
        items = list(market.get("items") or [])
        needle = (self.market_filter.get().strip().lower() if hasattr(self, "market_filter") else "")
        rows = []
        shown = 0
        for item in items:
            name = item.get("Name_Localised") or str(item.get("Name") or "").replace("_", " ").title()
            if needle and needle not in name.lower():
                continue
            analysis = self.market_analysis.get(name.lower(), {})
            rows.append({
                "name": name,
                "sell": int(item.get("SellPrice") or 0),
                "buy": int(item.get("BuyPrice") or 0),
                "demand": int(item.get("Demand") or 0),
                "stock": int(item.get("Stock") or 0),
                "signal": analysis.get("signal", ""),
                "note": analysis.get("note", ""),
            })
            shown += 1
        sort_key, sort_dir = self.market_sort
        rows.sort(key=lambda r: str(r[sort_key]).lower() if sort_key == "name" else r[sort_key], reverse=sort_dir < 0)
        for row in rows:
            iid = self.market_tree.insert("", tk.END, values=(
                row["name"],
                self._credits(row["sell"]),
                self._credits(row["buy"]),
                self._num(row["demand"]),
                self._num(row["stock"]),
                row["signal"],
                row["note"],
            ))
            self.market_rows[iid] = row
        if market:
            self.local_market_status.config(text=f"{shown}/{len(items)} commodities at {market.get('station') or '?'}")
        else:
            self.local_market_status.config(text="No market data yet. Open the commodity market at a station.")

        for jump in list(getattr(self.app, "trade_jump_history", []) or []):
            self.jump_tree.insert("", tk.END, values=(
                jump.get("system") or "?",
                f"{float(jump.get('distance') or 0):.1f} ly",
                self._age(jump.get("timestamp")),
            ))

        for item in getattr(self.app, "current_cargo_inventory", []) or []:
            name = item.get("Name_Localised") or item.get("name") or str(item.get("Name") or "").replace("_", " ").title()
            count = item.get("Count", item.get("count", 0))
            self.cargo_tree.insert("", tk.END, values=(name, self._num(count)))

    def _build_watchlist_tab(self):
        frame = tk.Frame(self.tabs, bg=self.UI_BG)
        self.tabs.add(frame, text="Watchlist")
        body = self._card(frame, "ROUTE WATCHLIST", "saved commodities, systems, and station pairs for quick checks")
        controls = tk.Frame(body, bg=self.UI_PANEL)
        controls.pack(fill=tk.X, pady=(0, 8))
        self.watch_commodity = self._simple_field(controls, "COMMODITY", 20)
        self.watch_note = self._simple_field(controls, "NOTE", 28)
        self._button(controls, "Add", self.add_watchlist_item, accent=True).pack(side=tk.LEFT, padx=(8, 0), pady=(12, 6))
        self._button(controls, "Remove", self.remove_watchlist_item).pack(side=tk.LEFT, padx=(6, 0), pady=(12, 6))
        self._button(controls, "Refresh", self.refresh_watchlist).pack(side=tk.LEFT, padx=(6, 0), pady=(12, 6))
        self._button(controls, "Copy", lambda: self._copy_selected_tree(self.watch_tree, self.watchlist_rows, "Watchlist row")).pack(side=tk.LEFT, padx=(6, 0), pady=(12, 6))
        self.watch_status = tk.Label(body, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 9), anchor="w")
        self.watch_status.pack(fill=tk.X, pady=(0, 6))
        self.watch_tree = self._tree(body, ("commodity", "note", "best_buy", "best_sell", "spread", "age"), {
            "commodity": ("Commodity", 170, tk.W),
            "note": ("Note", 220, tk.W),
            "best_buy": ("Best Buy", 220, tk.W),
            "best_sell": ("Best Sell", 220, tk.W),
            "spread": ("Spread", 90, tk.E),
            "age": ("Age", 60, tk.E),
        })

    def _watchlist(self):
        value = self.config.get("trade_watchlist")
        if not isinstance(value, list):
            value = []
            self.config["trade_watchlist"] = value
        return value

    def add_watchlist_item(self):
        commodity = self.watch_commodity.get().strip()
        if not commodity:
            self.watch_status.config(text="Enter a commodity name first.", fg=self.UI_WARN)
            return
        item = {"commodity": commodity, "note": self.watch_note.get().strip(), "created_at": time.time()}
        watch = self._watchlist()
        watch.append(item)
        save_config(self.config)
        self.watch_commodity.delete(0, tk.END)
        self.watch_note.delete(0, tk.END)
        self.refresh_watchlist()

    def remove_watchlist_item(self):
        selected = self.watch_tree.selection()
        if not selected:
            return
        idx = self.watch_tree.index(selected[0])
        watch = self._watchlist()
        if 0 <= idx < len(watch):
            watch.pop(idx)
            save_config(self.config)
        self.refresh_watchlist()

    def refresh_watchlist(self):
        if not hasattr(self, "watch_tree"):
            return
        for iid in self.watch_tree.get_children():
            self.watch_tree.delete(iid)
        self.watchlist_rows = {}
        watch = list(self._watchlist())
        if not watch:
            self.watch_status.config(text="No watchlist items yet.", fg=self.UI_MUTED)
            return
        self.watch_status.config(text="Refreshing watchlist prices...", fg=self.UI_MUTED)
        params = {
            "system": self._current_system(),
            "star_pos": self._current_coords(),
            "radius": self._entry_float(getattr(self, "radar_radius", None), 80.0),
            "min_units": self._entry_int(getattr(self, "radar_min_units", None), 1),
            "max_price_age_days": self._get_num(self.route_entries, "age", 30, int),
            "requires_large_pad": self.radar_large_pad_var.get(),
            "include_carriers": self.radar_include_carriers_var.get(),
            "limit": 8,
        }

        def worker():
            rows = []
            try:
                for item in watch:
                    buy = routes.search_commodity(item.get("commodity"), "buy", **params).get("results", [])
                    sell = routes.search_commodity(item.get("commodity"), "sell", **params).get("results", [])
                    rows.append((item, buy[0] if buy else None, sell[0] if sell else None))
                self.root.after(0, lambda: self._render_watchlist(rows))
            except Exception as exc:
                self.root.after(0, lambda: self.watch_status.config(text=str(exc), fg=self.UI_FAIL))
        threading.Thread(target=worker, daemon=True).start()

    def _render_watchlist(self, rows):
        for iid in self.watch_tree.get_children():
            self.watch_tree.delete(iid)
        self.watchlist_rows = {}
        for item, buy, sell in rows:
            spread = ""
            age_epoch = 0
            if buy and sell:
                spread = self._credits(int(sell.get("sell_price") or 0) - int(buy.get("buy_price") or 0))
                age_epoch = min(buy.get("updated_at") or 0, sell.get("updated_at") or 0)
            elif buy:
                age_epoch = buy.get("updated_at") or 0
            elif sell:
                age_epoch = sell.get("updated_at") or 0
            iid = self.watch_tree.insert("", tk.END, values=(
                item.get("commodity"),
                item.get("note", ""),
                self._station_label(buy, "buy"),
                self._station_label(sell, "sell"),
                spread or "-",
                self._age(age_epoch),
            ), tags=(self._freshness_tag(age_epoch),))
            self.watchlist_rows[iid] = {
                "commodity": item.get("commodity"),
                "best_buy": self._station_label(buy, "buy"),
                "best_sell": self._station_label(sell, "sell"),
                "spread": spread,
            }
        self.watch_status.config(text=f"{len(rows)} watchlist item(s).", fg=self.UI_MUTED)

    def _station_label(self, row, mode):
        if not row:
            return "-"
        price = row.get("buy_price") if mode == "buy" else row.get("sell_price")
        return f"{row.get('station')} / {row.get('system')} @ {self._credits(price)}"

    def refresh_radar(self):
        if not self._current_system():
            self.radar_status.config(text="No current system known yet.", fg=self.UI_WARN)
            return
        self.radar_status.config(text="Scanning local market opportunities...", fg=self.UI_MUTED)
        for iid in self.radar_tree.get_children():
            self.radar_tree.delete(iid)
        self.radar_rows = {}
        params = {
            "system": self._current_system(),
            "star_pos": self._current_coords(),
            "radius": self._entry_float(self.radar_radius, 80.0),
            "min_profit": self._entry_int(self.radar_min_profit, 1000),
            "min_units": self._entry_int(self.radar_min_units, 1),
            "max_price_age_days": self._get_num(self.route_entries, "age", 30, int),
            "requires_large_pad": self.radar_large_pad_var.get(),
            "include_carriers": self.radar_include_carriers_var.get(),
            "max_system_distance": self._get_num(self.route_entries, "max_ls", 1000, int),
            "limit": self._entry_int(self.radar_limit, 50),
        }

        def worker():
            try:
                rows = routes.find_opportunities(**params)
                self.root.after(0, lambda: self._render_radar(rows))
            except Exception as exc:
                self.root.after(0, lambda: self.radar_status.config(text=str(exc), fg=self.UI_FAIL))
        threading.Thread(target=worker, daemon=True).start()

    def _render_radar(self, rows):
        for row in rows:
            iid = self.radar_tree.insert("", tk.END, values=(
                row.get("commodity"),
                self._credits(row.get("profit_each")),
                self._num(row.get("units")),
                f"{row.get('from_station')} / {row.get('from_system')}",
                f"{row.get('to_station')} / {row.get('to_system')}",
                f"{float(row.get('distance') or 0):.1f} ly",
                self._age(row.get("updated_at")),
            ), tags=(self._freshness_tag(row.get("updated_at")),))
            self.radar_rows[iid] = row
        self.radar_status.config(text=f"{len(rows)} opportunity row(s), sorted by profit per ton.", fg=self.UI_MUTED)

    def refresh_cargo_sellers(self):
        cargo = list(getattr(self.app, "current_cargo_inventory", []) or [])
        if not cargo:
            self.cargo_sell_status.config(text="Cargo hold is empty or unavailable.", fg=self.UI_WARN)
            return
        self.cargo_sell_status.config(text="Finding cargo buyers...", fg=self.UI_MUTED)
        for iid in self.cargo_sell_tree.get_children():
            self.cargo_sell_tree.delete(iid)
        self.cargo_sell_rows = {}
        params = {
            "cargo_items": cargo,
            "system": self._current_system(),
            "star_pos": self._current_coords(),
            "radius": self._entry_float(self.radar_radius, 80.0),
            "max_price_age_days": self._get_num(self.route_entries, "age", 30, int),
            "requires_large_pad": self.radar_large_pad_var.get(),
            "include_carriers": self.radar_include_carriers_var.get(),
            "max_system_distance": self._get_num(self.route_entries, "max_ls", 1000, int),
            "limit_per_item": 5,
        }

        def worker():
            try:
                rows = routes.sell_cargo(**params)
                self.root.after(0, lambda: self._render_cargo_sellers(rows))
            except Exception as exc:
                self.root.after(0, lambda: self.cargo_sell_status.config(text=str(exc), fg=self.UI_FAIL))
        threading.Thread(target=worker, daemon=True).start()

    def _render_cargo_sellers(self, rows):
        for row in rows:
            iid = self.cargo_sell_tree.insert("", tk.END, values=(
                row.get("commodity"),
                self._num(row.get("count")),
                row.get("station"),
                row.get("system"),
                self._credits(row.get("sell_price")),
                self._credits(row.get("est_sale")),
                f"{float(row.get('distance') or 0):.1f} ly",
                self._age(row.get("updated_at")),
            ), tags=(self._freshness_tag(row.get("updated_at")),))
            self.cargo_sell_rows[iid] = row
        self.cargo_sell_status.config(text=f"{len(rows)} buyer row(s).", fg=self.UI_MUTED)

    def analyze_local_market(self):
        market = getattr(self.app, "current_trade_market", None) or {}
        items = list(market.get("items") or [])
        if not items:
            self.local_market_status.config(text="No market data to analyze.", fg=self.UI_WARN)
            return
        self.local_market_status.config(text="Analyzing station market...", fg=self.UI_MUTED)
        params = {
            "market_items": items,
            "system": self._current_system(),
            "star_pos": self._current_coords(),
            "radius": self._entry_float(self.radar_radius, 80.0),
            "max_price_age_days": self._get_num(self.route_entries, "age", 30, int),
            "requires_large_pad": self.radar_large_pad_var.get(),
            "include_carriers": self.radar_include_carriers_var.get(),
            "max_system_distance": self._get_num(self.route_entries, "max_ls", 1000, int),
        }

        def worker():
            try:
                result = routes.analyze_station_market(**params)
                self.root.after(0, lambda: self._render_market_analysis(result))
            except Exception as exc:
                self.root.after(0, lambda: self.local_market_status.config(text=str(exc), fg=self.UI_FAIL))
        threading.Thread(target=worker, daemon=True).start()

    def _render_market_analysis(self, result):
        self.market_analysis = result or {}
        self.refresh_local()
        self.local_market_status.config(text=f"{len(self.market_analysis)} market signal(s) found.", fg=self.UI_MUTED)

    def refresh_session(self):
        if not hasattr(self, "session_tree"):
            return
        session = getattr(self.app, "trade_session", {}) or {}
        self.session_status.config(text=(
            f"Bought: {self._num(session.get('bought_units', 0))} t / {self._credits(session.get('spent', 0))}   "
            f"Sold: {self._num(session.get('sold_units', 0))} t / {self._credits(session.get('earned', 0))}   "
            f"Est Profit: {self._credits(session.get('profit', 0))}"
        ))
        for iid in self.session_tree.get_children():
            self.session_tree.delete(iid)
        for event in list(session.get("events", []) or [])[-25:][::-1]:
            try:
                stamp = time.strftime("%H:%M", time.localtime(float(event.get("time") or time.time())))
            except Exception:
                stamp = "--:--"
            self.session_tree.insert("", tk.END, values=(
                stamp,
                event.get("event"),
                event.get("commodity"),
                self._num(event.get("count")),
                self._credits(event.get("price")),
                self._credits(event.get("profit")),
            ))

    def sort_market(self, key):
        current_key, current_dir = self.market_sort
        self.market_sort = (key, -current_dir if key == current_key else (1 if key == "name" else -1))
        self.refresh_local()

    def open_market_builder(self):
        try:
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).resolve().parent
                builder = exe_dir / "VoidCompassMarketBuilder.exe"
                if builder.exists():
                    subprocess.Popen([str(builder)], cwd=str(exe_dir))
                    return
            script = Path(__file__).resolve().parent / "market_builder.py"
            if script.exists():
                env = os.environ.copy()
                env["VC_TRADE_SEED_WORKER_SCRIPT"] = str(script)
                subprocess.Popen([sys.executable, str(script)], cwd=str(script.parent), env=env)
                return
            raise FileNotFoundError("market_builder.py not found")
        except Exception as exc:
            self._show_banner(f"Market Builder launch failed: {exc}")
            self._set_db_text(f"Market Builder launch failed: {exc}", self.UI_FAIL)

    def find_routes(self):
        self.route_status.config(text="Searching trade routes...", fg=self.UI_MUTED)
        self._clear_route_results()
        system_value = self.route_entries["system"].get().strip() or self._current_system()
        current = self._current_system()
        star_pos = self._current_coords() if current and system_value and system_value.lower() == current.lower() else None
        station_value = None
        if current and system_value and system_value.lower() == current.lower() and getattr(self.app, "current_docked", False):
            station_value = getattr(self.app, "current_station_name", None)
        params = {
            "system": system_value,
            "station": station_value,
            "star_pos": star_pos,
            "capital": self._get_num(self.route_entries, "capital", 1000000, int),
            "max_cargo": self._get_num(self.route_entries, "cargo", 64, int),
            "radius": self._get_num(self.route_entries, "radius", 100.0, float),
            "max_leg": self._get_num(self.route_entries, "max_leg", 80.0, float),
            "jump_range": self._get_num(self.route_entries, "jump", 30.0, float),
            "min_supply": self._get_num(self.route_entries, "min_units", 1, int),
            "max_price_age_days": self._get_num(self.route_entries, "age", 30, int),
            "requires_large_pad": self.large_pad_var.get(),
            "include_carriers": self.include_carriers_var.get(),
            "max_system_distance": self._get_num(self.route_entries, "max_ls", 1000, int),
            "top_n": self._get_num(self.route_entries, "results", 8, int),
            "max_hops": self._get_num(self.route_entries, "hops", 4, int),
        }
        mode = self.loop_mode.get()
        if not params["system"]:
            self.route_status.config(text="Enter a start system or wait for the journal to detect your current system.", fg=self.UI_WARN)
            return

        def worker():
            try:
                conn = marketdb.connect()
                try:
                    ready = marketdb.status(conn)["ready"]
                finally:
                    conn.close()
                if mode == "loop":
                    if not ready:
                        raise routes.RouteError("Loop routes need the local database. Build it from the Database tab first.")
                    result = routes.plan_loops(
                        system=params["system"],
                        star_pos=params["star_pos"],
                        capital=params["capital"],
                        max_cargo=params["max_cargo"],
                        radius=params["radius"],
                        max_system_distance=params["max_system_distance"],
                        max_price_age_days=params["max_price_age_days"],
                        requires_large_pad=params["requires_large_pad"],
                        include_carriers=params["include_carriers"],
                        min_supply=params["min_supply"],
                        jump_range=params["jump_range"],
                        max_leg=params["max_leg"],
                        top_n=params["top_n"],
                    )
                    self.root.after(0, lambda: self._render_loops(result))
                else:
                    if ready:
                        result = routes.plan_route_local(
                            system=params["system"],
                            station=params["station"],
                            star_pos=params["star_pos"],
                            capital=params["capital"],
                            max_cargo=params["max_cargo"],
                            max_hop_distance=params["radius"],
                            max_hops=params["max_hops"],
                            max_system_distance=params["max_system_distance"],
                            max_price_age_days=params["max_price_age_days"],
                            requires_large_pad=params["requires_large_pad"],
                            include_carriers=params["include_carriers"],
                            min_supply=params["min_supply"],
                        )
                        self.root.after(0, lambda: self._render_chain(result, "local database"))
                    else:
                        result = spansh.plan_route(
                            system=params["system"],
                            station=params["station"],
                            capital=params["capital"],
                            max_cargo=params["max_cargo"],
                            max_hop_distance=params["radius"],
                            max_hops=params["max_hops"],
                            max_system_distance=params["max_system_distance"],
                            max_price_age_days=params["max_price_age_days"],
                            requires_large_pad=params["requires_large_pad"],
                            allow_planetary=self.allow_planetary_var.get(),
                            unique=self.unique_route_var.get(),
                        )
                        self.root.after(0, lambda: self._render_chain(result, "Spansh API"))
            except Exception as exc:
                self.root.after(0, lambda: self.route_status.config(text=str(exc), fg=self.UI_FAIL))
        threading.Thread(target=worker, daemon=True).start()

    def _clear_route_results(self):
        for iid in self.route_tree.get_children():
            self.route_tree.delete(iid)
        self.route_detail_by_iid = {}
        self._set_route_detail("")

    def _render_loops(self, loops):
        self._clear_route_results()
        cards = []
        for idx, loop in enumerate(loops, 1):
            frm = f"{loop['a']['station']} / {loop['a']['system']}"
            to = f"{loop['b']['station']} / {loop['b']['system']}"
            iid = self.route_tree.insert("", tk.END, values=(
                f"Loop #{idx}", frm, to, self._credits(loop.get("profit")),
                f"{self._credits(loop.get('profit_per_hour'))}/hr", f"{loop.get('distance')} ly",
            ))
            self.route_detail_by_iid[iid] = self._loop_detail(loop)
            cards.append(f"LOOP #{idx}\n{self._loop_detail(loop)}")
        self.route_status.config(text=f"{len(loops)} loop route(s), ranked by estimated profit/hour.", fg=self.UI_MUTED)
        self._set_route_detail(("\n\n" + "-" * 72 + "\n\n").join(cards) if cards else "")

    def _render_chain(self, hops, source):
        self._clear_route_results()
        total = sum(int(h.get("profit") or 0) for h in hops)
        cards = []
        for idx, hop in enumerate(hops, 1):
            frm = f"{hop.get('from_station')} / {hop.get('from_system')}"
            to = f"{hop.get('to_station')} / {hop.get('to_system')}"
            iid = self.route_tree.insert("", tk.END, values=(
                f"Hop {idx}", frm, to, self._credits(hop.get("profit")),
                self._credits(hop.get("cumulative_profit")), f"{float(hop.get('distance') or 0):.1f} ly",
            ))
            self.route_detail_by_iid[iid] = self._hop_detail(hop)
            cards.append(f"HOP {idx}\n{self._hop_detail(hop)}")
        self.route_status.config(text=f"{len(hops)} hop(s) via {source} | total {self._credits(total)}", fg=self.UI_MUTED)
        self._set_route_detail(f"TOTAL {self._credits(total)} via {source}\n\n" + ("\n\n" + "-" * 72 + "\n\n").join(cards) if cards else "")

    def _on_route_selected(self, _event=None):
        selected = self.route_tree.selection()
        self._set_route_detail(self.route_detail_by_iid.get(selected[0], "") if selected else "")

    def _set_route_detail(self, text):
        self.route_detail.configure(state=tk.NORMAL)
        self.route_detail.delete("1.0", tk.END)
        self.route_detail.insert("1.0", text or "Select a route row to view commodities.")
        self.route_detail.configure(state=tk.DISABLED)

    def _loop_detail(self, loop):
        lines = [
            f"{loop['a']['station']} ({loop['a']['system']}) <-> {loop['b']['station']} ({loop['b']['system']})",
            f"Round trip: {self._credits(loop.get('profit'))} | {self._credits(loop.get('profit_per_hour'))}/hr | ~{loop.get('minutes_per_trip')} min",
            "",
            f"OUTBOUND +{self._credits(loop['outbound'].get('profit'))}",
        ]
        lines.extend(self._commodity_lines(loop["outbound"].get("commodities") or []))
        lines.append("")
        lines.append(f"RETURN +{self._credits(loop['inbound'].get('profit'))}")
        lines.extend(self._commodity_lines(loop["inbound"].get("commodities") or []))
        return "\n".join(lines)

    def _hop_detail(self, hop):
        lines = [
            f"{hop.get('from_station')} ({hop.get('from_system')}) -> {hop.get('to_station')} ({hop.get('to_system')})",
            f"Profit: {self._credits(hop.get('profit'))} | Distance: {float(hop.get('distance') or 0):.1f} ly | Station: {self._num(hop.get('to_dist_ls'))} ls",
            "",
        ]
        lines.extend(self._commodity_lines(hop.get("commodities") or []))
        return "\n".join(lines)

    def _commodity_lines(self, commodities):
        if not commodities:
            return ["- fly empty"]
        lines = []
        for c in commodities:
            amount = int(c.get("amount") or 0)
            profit = int(c.get("profit") or 0)
            per_ton = int(profit / amount) if amount else 0
            lines.append(
                f"- {c.get('name')} | {self._num(amount)} t | buy {self._credits(c.get('buy_price'))} | "
                f"sell {self._credits(c.get('sell_price'))} | profit {self._credits(profit)} | {self._credits(per_ton)}/t"
            )
        return lines

    def search_commodity(self):
        query = self.commodity_entry.get().strip()
        if not query:
            self.commodity_status.config(text="Enter a commodity name.", fg=self.UI_WARN)
            return
        self.commodity_status.config(text="Searching commodity markets...", fg=self.UI_MUTED)
        for iid in self.commodity_tree.get_children():
            self.commodity_tree.delete(iid)
        params = {
            "query": query,
            "mode": self.search_mode.get(),
            "system": self._current_system(),
            "star_pos": self._current_coords(),
            "radius": self._entry_float(self.commodity_radius, 50.0),
            "min_units": self._entry_int(self.commodity_min, 1),
            "requires_large_pad": self.commodity_large_pad.get(),
            "include_carriers": self.commodity_include_carriers.get(),
            "max_price_age_days": self._get_num(self.route_entries, "age", 30, int),
            "limit": self._entry_int(self.commodity_limit, 40),
        }

        def worker():
            try:
                result = routes.search_commodity(**params)
                self.root.after(0, lambda: self._render_commodity_result(result, params["mode"]))
            except Exception as exc:
                self.root.after(0, lambda: self.commodity_status.config(text=str(exc), fg=self.UI_FAIL))
        threading.Thread(target=worker, daemon=True).start()

    def _render_commodity_result(self, result, mode):
        self.commodity_rows = {}
        for row in result.get("results", []):
            price = row.get("buy_price") if mode == "buy" else row.get("sell_price")
            units = row.get("supply") if mode == "buy" else row.get("demand")
            iid = self.commodity_tree.insert("", tk.END, values=(
                row.get("station"), row.get("system"), self._credits(price), self._num(units),
                f"{float(row.get('distance') or 0):.1f} ly", f"{self._num(row.get('dist_ls'))} ls",
                self._age(row.get("updated_at")), "L" if row.get("large_pad") else "-",
            ), tags=(self._freshness_tag(row.get("updated_at")),))
            self.commodity_rows[iid] = row
        self.commodity_status.config(
            text=f"{len(result.get('results') or [])} station(s) for {result.get('commodity')}.",
            fg=self.UI_MUTED,
        )

    def _entry_float(self, entry, default):
        try:
            if entry is None:
                return default
            return float(entry.get().strip() or default)
        except Exception:
            return default

    def _entry_int(self, entry, default):
        try:
            if entry is None:
                return default
            return int(float(entry.get().strip() or default))
        except Exception:
            return default

    def _num(self, value):
        try:
            return f"{float(value):,.0f}"
        except Exception:
            return "?"

    def _credits(self, value):
        try:
            return f"{int(value):,} cr"
        except Exception:
            return "? cr"

    def _age(self, epoch):
        try:
            mins = max(0, (time.time() - float(epoch)) / 60.0)
            if mins < 60:
                return f"{int(mins)}m"
            if mins < 2880:
                return f"{int(mins / 60)}h"
            return f"{int(mins / 1440)}d"
        except Exception:
            return "?"

    def _log(self, msg):
        try:
            self.app.log(msg)
        except Exception:
            pass

    def _on_close(self):
        try:
            if self._seed_poll_after:
                self.root.after_cancel(self._seed_poll_after)
                self._seed_poll_after = None
            if self._live_poll_after:
                self.root.after_cancel(self._live_poll_after)
                self._live_poll_after = None
            self._save_route_form()
            self.config["trade_window_geometry"] = self.win.geometry()
            save_config(self.config)
        except Exception:
            pass
        self.win.destroy()
