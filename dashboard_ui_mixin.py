import time
import math
import os
import sys
import threading
import tkinter as tk
import requests
import webbrowser
from datetime import datetime, timezone
from tkinter import scrolledtext

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, panel, section_label
from version import APP_VERSION

COLOR_ACCENT = THEME.accent
COLOR_ORANGE = THEME.orange
COLOR_TEXT = THEME.text

_FEED_TAG_COLORS = {
    "JUMP":    "#00d1ff",  # cyan   — hyperspace jumps
    "SCAN":    "#a5b4fc",  # indigo — passive body scans
    "DSS":     "#6ee7b7",  # mint   — mapped surface scans
    "BIO":     "#86efac",  # green  — organic life
    "SYSTEM":  "#93c5fd",  # blue   — system / nav info
    "ROUTE":   "#fde68a",  # gold   — waypoints / routing
    "CARRIER": "#d8b4fe",  # purple — carrier events
    "EDSM":    "#67e8f9",  # teal   — EDSM upload status
    "EDDN":    "#38bdf8",  # blue   — EDDN market upload status
    "MUSIC":   "#22d3ee",  # cyan   — music mood / soft state
    "VALUABLE":"#FF7100",  # orange — high-value worlds
    "ALERT":   "#FF7100",  # orange — system alerts
    "DOCK":    "#fb923c",  # amber  — docking / undocking
    "INFO":    "#888",     # gray   — generic info
}


def _carrier_countdown(dep_str):
    """Return a compact H:MM:SS / Mm SSs countdown for a departure ISO timestamp."""
    if not dep_str:
        return ""
    try:
        dt = datetime.fromisoformat(dep_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = (dt - datetime.now(timezone.utc)).total_seconds()
        if diff <= 0:
            return "JUMPING NOW"
        m, s = divmod(int(diff), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m:02d}m {s:02d}s"
        return f"{m}m {s:02d}s"
    except Exception:
        return ""


class DashboardUIMixin(ThemedWindowMixin):
    JOURNAL_HISTORY_LIMIT = 100
    def _config_label_if_changed(self, widget, text=None, fg=None):
        try:
            current_text = widget.cget("text")
        except Exception:
            current_text = None
        try:
            current_fg = widget.cget("fg")
        except Exception:
            current_fg = None

        kwargs = {}
        if text is not None and text != current_text:
            kwargs["text"] = text
        if fg is not None and fg != current_fg:
            kwargs["fg"] = fg
        if kwargs:
            widget.config(**kwargs)

    def _panel(self, parent, bg=None, border=None):
        return panel(parent, background=bg, border=border)

    def _section_label(self, parent, text, fg=None, bg=None):
        return section_label(parent, text, foreground=fg, background=bg)

    def _action_button(self, parent, text, command, accent=False, muted=False):
        return button(parent, text, command, accent=accent, muted=muted, pady=4)

    def setup_layout(self):
        apply_window(self.root)

        # Match the web console's defining composition: persistent navigation
        # rail at left, command strip above the working area, content at right.
        shell = tk.Frame(self.root, bg=self.UI_BG)
        shell.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.nav = tk.Frame(
            shell, bg=THEME.header, width=232,
            highlightbackground=self.UI_BORDER, highlightthickness=0,
        )
        self.nav.pack(side=tk.LEFT, fill=tk.Y)
        self.nav.pack_propagate(False)
        tk.Frame(shell, bg=self.UI_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        self.brand_row = tk.Frame(self.nav, bg=THEME.header)
        self.brand_row.pack(fill=tk.X, padx=12, pady=(18, 0))

        tk.Label(
            self.brand_row, text="VOID COMPASS", font=("Bahnschrift SemiCondensed", 17, "bold"),
            fg=THEME.accent, bg=THEME.header, anchor="w",
        ).pack(fill=tk.X, padx=8)
        tk.Label(
            self.brand_row, text="COMMANDER CONSOLE", font=("Cascadia Mono", 8, "bold"),
            fg=THEME.orange, bg=THEME.header, anchor="w",
        ).pack(fill=tk.X, padx=8, pady=(3, 14))
        tk.Frame(self.brand_row, bg=THEME.accent, height=1).pack(fill=tk.X, padx=8)

        nav_items = (
            ("⌖", "DASHBOARD", self.show_dashboard_page),
            ("◉", "PROFILE", self.open_commander_profile_window),
            ("✦", "EXPLORE", self.open_exploration_window),
            ("⇌", "TRADE", self.open_trade_window),
            ("◆", "MINING", self.open_mining_window),
            ("➤", "ROUTE", self.open_route_planner),
            ("⬢", "CARRIER", self.open_carrier_window),
            ("⌂", "COLONY", self.open_colonization_window),
            ("⚑", "BGS", self.open_bgs_window),
            ("⚙", "ENGINEER", self.open_engineer_window),
        )
        self.nav_buttons = {}
        self.nav_indicators = {}
        nav_list = tk.Frame(self.nav, bg=THEME.header)
        nav_list.pack(fill=tk.X, padx=12, pady=(18, 0))
        for icon, label, command in nav_items:
            active = label == "DASHBOARD"
            row = tk.Frame(nav_list, bg=THEME.panel_alt if active else THEME.header, height=34)
            row.pack(fill=tk.X, pady=1)
            row.pack_propagate(False)
            indicator = tk.Frame(row, bg=THEME.accent if active else row.cget("bg"), width=3)
            indicator.pack(side=tk.LEFT, fill=tk.Y)
            btn = tk.Button(
                row, text=f"{icon}   {label}", command=command,
                bg=row.cget("bg"), fg=THEME.accent if active else THEME.muted,
                activebackground=THEME.panel_alt, activeforeground=THEME.accent,
                font=("Bahnschrift SemiCondensed", 9, "bold"), anchor="w",
                relief=tk.FLAT, bd=0, padx=12, pady=7, cursor="arrow" if active else "hand2",
            )
            btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.nav_buttons[label] = btn
            self.nav_indicators[label] = indicator

        utilities = tk.Frame(self.nav, bg=THEME.header)
        self.nav_utilities = utilities
        utilities.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=14)
        settings_row = tk.Frame(utilities, bg=THEME.header, height=34)
        settings_row.pack(fill=tk.X, pady=(0, 4))
        settings_row.pack_propagate(False)
        self.settings_nav_indicator = tk.Frame(settings_row, bg=THEME.header, width=3)
        self.settings_nav_indicator.pack(side=tk.LEFT, fill=tk.Y)
        self.settings_nav_btn = self._action_button(settings_row, "≡   SETTINGS", self.open_settings)
        self.settings_nav_btn.configure(anchor="w")
        self.settings_nav_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        utility_row = tk.Frame(utilities, bg=THEME.header)
        utility_row.pack(fill=tk.X)
        self._action_button(utility_row, "GROUND", self.open_ground_target_window, muted=True).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._action_button(utility_row, "SHOTS", self.open_screenshots_folder, muted=True).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        tk.Label(
            utilities, text=f"v{APP_VERSION}  //  NATIVE", font=("Cascadia Mono", 7),
            fg=THEME.dim, bg=THEME.header, anchor="w",
        ).pack(fill=tk.X, pady=(10, 0))

        self.workspace = tk.Frame(shell, bg=self.UI_BG)
        self.workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── COMMAND STRIP ─────────────────────────────────────────────────
        cmd_strip = tk.Frame(self.workspace, bg=THEME.header, height=76)
        cmd_strip.pack(fill=tk.X)
        cmd_strip.pack_propagate(False)

        sys_zone = tk.Frame(cmd_strip, bg=THEME.header)
        sys_zone.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 12))
        self.summary_sys = tk.Label(sys_zone, text="---",
                                    font=("Segoe UI", 18, "bold"),
                                    fg=COLOR_ACCENT, bg=THEME.header, anchor="w")
        self.summary_sys.pack(anchor="w", pady=(3, 0))
        self.integration_lbl = tk.Label(sys_zone, text="HUD: ON | SHOTS: OFF",
                                        font=("Consolas", 8), fg=self.UI_DIM,
                                        bg=THEME.header, anchor="w")
        self.integration_lbl.pack(anchor="w")

        tk.Frame(cmd_strip, bg=self.UI_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6, padx=(0, 14))

        def _strip_stat(parent, label):
            f = tk.Frame(parent, bg=THEME.header)
            f.pack(side=tk.LEFT, padx=(0, 18), fill=tk.Y)
            tk.Label(f, text=label, font=("Segoe UI", 7, "bold"),
                     fg=self.UI_DIM, bg=THEME.header).pack(anchor="w", pady=(3, 0))
            lbl = tk.Label(f, text="—", font=self.UI_MONO_BOLD, fg=COLOR_TEXT, bg=THEME.header)
            lbl.pack(anchor="w")
            return lbl

        self.summary_scan    = _strip_stat(cmd_strip, "SCAN")
        self.summary_route   = _strip_stat(cmd_strip, "ROUTE")
        self.summary_traffic = _strip_stat(cmd_strip, "TRAFFIC")
        self.summary_session = _strip_stat(cmd_strip, "SESSION")

        tk.Frame(cmd_strip, bg=self.UI_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6, padx=(0, 14))

        alert_zone = tk.Frame(cmd_strip, bg=THEME.header)
        alert_zone.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(alert_zone, text="ALERTS", font=("Segoe UI", 7, "bold"),
                 fg=self.UI_DIM, bg=THEME.header).pack(anchor="w", pady=(3, 0))
        self.alert_lbl = tk.Label(alert_zone, text="NONE",
                                  font=self.UI_MONO_BOLD, fg=self.UI_MUTED,
                                  bg=THEME.header, anchor="w")
        self.alert_lbl.pack(anchor="w")

        cmdr_zone = tk.Frame(cmd_strip, bg=THEME.header)
        cmdr_zone.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 6))
        tk.Frame(cmd_strip, bg=self.UI_BORDER, width=1).pack(side=tk.RIGHT, fill=tk.Y, pady=6)
        tk.Label(cmdr_zone, text="CMDR", font=("Segoe UI", 7, "bold"),
                 fg=self.UI_DIM, bg=THEME.header).pack(anchor="e", pady=(3, 0))
        self.summary_cmdr = tk.Label(cmdr_zone, text="UNKNOWN",
                                     font=self.UI_MONO_BOLD, fg=COLOR_ACCENT,
                                     bg=THEME.header, anchor="e")
        self.summary_cmdr.pack(anchor="e")

        tk.Frame(self.workspace, bg=self.UI_BORDER, height=1).pack(fill=tk.X)

        self.dashboard_host = tk.Frame(self.workspace, bg=self.UI_BG)
        self.dashboard_host.pack(fill=tk.BOTH, expand=True)
        self._active_page = "DASHBOARD"

        self._build_companion_dashboard_body()
        return

        # ── BODY ──────────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # ── LEFT SIDEBAR (290px) ──────────────────────────────────────────
        self.side = tk.Frame(body, bg=self.UI_BG, width=290)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self.side.pack_propagate(False)

        metrics_card = self._panel(self.side)
        metrics_card.pack(fill=tk.X, pady=(0, 8))
        self._section_label(metrics_card, "PRIMARY TELEMETRY").pack(anchor="w", padx=12, pady=(9, 0))
        self.sys_stat = self.create_stat(metrics_card, "CURRENT SYSTEM", "---")
        self.nav_stat = self.create_stat(metrics_card, "NAV TARGET", "---")
        self.scan_stat = self.create_stat(metrics_card, "SCAN PROGRESS", "0 / 0")
        tk.Frame(metrics_card, bg=self.UI_PANEL, height=8).pack()

        # ── Fleet Carrier status panel ────────────────────────────────────
        self.carrier_panel = self._panel(self.side)
        self.carrier_panel.pack(fill=tk.X, pady=(0, 8))

        carrier_hdr = tk.Frame(self.carrier_panel, bg=self.UI_PANEL)
        carrier_hdr.pack(fill=tk.X, padx=12, pady=(9, 4))
        self._section_label(carrier_hdr, "FLEET CARRIER").pack(side=tk.LEFT)
        self.carrier_panel_badge = tk.Label(
            carrier_hdr, text="IDLE", fg="black", bg=self.UI_DIM,
            font=("Segoe UI", 7, "bold"), padx=6, pady=2,
        )
        self.carrier_panel_badge.pack(side=tk.RIGHT)

        self.carrier_panel_name = tk.Label(
            self.carrier_panel, text="Dock at your carrier to sync.",
            fg=self.UI_DIM, bg=self.UI_PANEL,
            font=self.UI_MONO_BOLD, anchor="w",
        )
        self.carrier_panel_name.pack(fill=tk.X, padx=12)

        self.carrier_panel_loc = tk.Label(
            self.carrier_panel, text="",
            fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=self.UI_MONO, anchor="w",
        )
        self.carrier_panel_loc.pack(fill=tk.X, padx=12, pady=(1, 0))

        self.carrier_panel_jump = tk.Label(
            self.carrier_panel, text="",
            fg=COLOR_ACCENT, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"), anchor="w",
        )
        self.carrier_panel_jump.pack(fill=tk.X, padx=12, pady=(1, 0))

        # Compact fuel bar
        _cfuel = tk.Frame(self.carrier_panel, bg=self.UI_PANEL)
        _cfuel.pack(fill=tk.X, padx=12, pady=(5, 9))
        self.carrier_fuel_bar_bg = tk.Frame(_cfuel, bg="#1a2430", height=6, width=240)
        self.carrier_fuel_bar_bg.pack(side=tk.LEFT)
        self.carrier_fuel_bar_bg.pack_propagate(False)
        self.carrier_fuel_fill = tk.Frame(self.carrier_fuel_bar_bg, bg=self.UI_OK, height=6)
        self.carrier_fuel_fill.place(x=0, y=0, relheight=1.0, width=0)
        self.carrier_fuel_txt = tk.Label(
            _cfuel, text="", fg=self.UI_DIM, bg=self.UI_PANEL,
            font=("Segoe UI", 7),
        )
        self.carrier_fuel_txt.pack(side=tk.LEFT, padx=(8, 0))
        # ── end carrier panel ─────────────────────────────────────────────

        self.ground_panel = self._panel(self.side)
        self.ground_panel.pack(fill=tk.X, pady=(0, 8))
        self._section_label(self.ground_panel, "GROUND TARGET").pack(anchor="w", padx=12, pady=(9, 3))
        input_row = tk.Frame(self.ground_panel, bg=self.UI_PANEL)
        input_row.pack(fill=tk.X, padx=12, pady=(0, 6))
        tk.Label(input_row, text="LAT", font=("Segoe UI", 8, "bold"), fg=self.UI_MUTED, bg=self.UI_PANEL).grid(row=0, column=0, sticky="w")
        tk.Label(input_row, text="LON", font=("Segoe UI", 8, "bold"), fg=self.UI_MUTED, bg=self.UI_PANEL).grid(row=0, column=2, sticky="w", padx=(8, 0))
        self.ground_lat_entry = tk.Entry(input_row, width=10, bg="#090c10", fg=COLOR_TEXT, font=self.UI_MONO, insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.ground_lat_entry.grid(row=1, column=0, sticky="ew")
        self.ground_lon_entry = tk.Entry(input_row, width=10, bg="#090c10", fg=COLOR_TEXT, font=self.UI_MONO, insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.ground_lon_entry.grid(row=1, column=2, sticky="ew", padx=(8, 0))
        input_row.grid_columnconfigure(0, weight=1)
        input_row.grid_columnconfigure(2, weight=1)

        btn_row = tk.Frame(self.ground_panel, bg=self.UI_PANEL)
        btn_row.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._action_button(btn_row, "Set", self.set_ground_target_from_entries, accent=True).pack(side=tk.LEFT)
        self._action_button(btn_row, "Here", self.set_ground_target_here).pack(side=tk.LEFT, padx=(6, 0))
        self._action_button(btn_row, "Clear", self.clear_ground_target, muted=True).pack(side=tk.LEFT, padx=(6, 0))
        self.ground_popup_toggle_btn = tk.Button(
            btn_row,
            text="Popup On" if getattr(self, "ground_popup_enabled", True) else "Popup Off",
            command=self.toggle_ground_popup,
            bg=self.UI_PANEL,
            fg=self.UI_MUTED,
            font=self.UI_FONT_BOLD,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
        )
        self.ground_popup_toggle_btn.pack(side=tk.RIGHT)
        self.ground_status_lbl = tk.Label(self.ground_panel, text="Target: OFF", font=self.UI_MONO_BOLD, fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w")
        self.ground_status_lbl.pack(fill=tk.X, padx=12, pady=(0, 2))
        self.ground_detail_lbl = tk.Label(self.ground_panel, text="Waiting for planetary coordinates.", font=self.UI_MONO, fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w")
        self.ground_detail_lbl.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.wp_panel = self._panel(self.side, border=COLOR_ACCENT)
        self.wp_panel.pack(fill=tk.X, pady=(0, 8))
        self.wp_panel.pack_propagate(False)
        self.wp_panel.config(height=170)
        header_row = tk.Frame(self.wp_panel, bg=self.UI_PANEL)
        header_row.pack(fill=tk.X, padx=12, pady=(9, 0))
        self._section_label(header_row, "ROUTE NOTES").pack(side=tk.LEFT)
        self.wp_dist_lbl = tk.Label(header_row, text="", font=self.UI_MONO_BOLD, fg=COLOR_ACCENT, bg=self.UI_PANEL)
        self.wp_dist_lbl.pack(side=tk.RIGHT)
        self.wp_name_lbl = tk.Label(self.wp_panel, text="NO ACTIVE ROUTE", font=("Segoe UI", 12, "bold"), fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w")
        self.wp_name_lbl.pack(fill=tk.X, padx=12, pady=(6, 0))
        self.wp_info_wrap = tk.Frame(self.wp_panel, bg=self.UI_PANEL)
        self.wp_info_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(2, 8))
        self.wp_info_scroll = tk.Scrollbar(self.wp_info_wrap, orient=tk.VERTICAL)
        self.wp_info_text = tk.Text(
            self.wp_info_wrap,
            bg=self.UI_PANEL,
            fg=self.UI_MUTED,
            font=self.UI_MONO,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.WORD,
            yscrollcommand=self.wp_info_scroll.set,
            height=7
        )
        self.wp_info_scroll.config(command=self.wp_info_text.yview)
        self.wp_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.wp_info_text.config(state=tk.DISABLED)
        self.wp_info_scroll_visible = False

        self.wp_info_text.bind("<Enter>", lambda e: self._toggle_wp_scrollbar(True))
        self.wp_info_text.bind("<Leave>", lambda e: self._toggle_wp_scrollbar(False))
        self.wp_info_text.bind("<MouseWheel>", self._on_wp_info_wheel)

        side_actions = tk.Frame(self.side, bg=self.UI_BG)
        side_actions.pack(side=tk.BOTTOM, fill=tk.X)
        self._action_button(side_actions, "Rebuild Cache", self.scan_all_logs_threaded, muted=True).pack(side=tk.LEFT)
        tk.Label(side_actions, text="2026 insert3coins", font=("Segoe UI", 8), fg=self.UI_DIM, bg=self.UI_BG).pack(side=tk.RIGHT, pady=6)

        center = tk.Frame(body, bg=self.UI_BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # 2×3 ops grid
        ops = tk.Frame(center, bg=self.UI_BG)
        ops.pack(fill=tk.BOTH, expand=True)
        ops.grid_columnconfigure(0, weight=1)
        ops.grid_columnconfigure(1, weight=1)
        ops.grid_rowconfigure(0, weight=1)
        ops.grid_rowconfigure(1, weight=1)
        ops.grid_rowconfigure(2, weight=1)

        self.card_nav     = self._build_ops_card(ops, "NAVIGATION",   0, 0)
        self.card_scan    = self._build_ops_card(ops, "SCAN INTEL",   0, 1)
        self.card_system  = self._build_ops_card(ops, "SYSTEM INTEL", 1, 0)
        self.card_value   = self._build_ops_card(ops, "ECONOMY",      1, 1)
        self.card_session = self._build_ops_card(ops, "SESSION",      2, 0)
        self.card_ops     = self._build_ops_card(ops, "OPERATIONS",   2, 1)

        # Debug console — collapsed by default
        self._console_visible = False
        _toggle_bar = tk.Frame(center, bg=self.UI_BG)
        _toggle_bar.pack(fill=tk.X, pady=(6, 0))
        self._console_toggle_btn = tk.Button(
            _toggle_bar, text="▶  DEBUG CONSOLE",
            command=self._toggle_console,
            bg=self.UI_BG, fg=self.UI_DIM,
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2", padx=0,
        )
        self._console_toggle_btn.pack(side=tk.LEFT)

        self._console_frame = self._panel(center)
        _log_hdr = tk.Frame(self._console_frame, bg=self.UI_PANEL)
        _log_hdr.pack(fill=tk.X, padx=10, pady=(8, 2))
        self._section_label(_log_hdr, "DEBUG CONSOLE", fg=self.UI_MUTED).pack(side=tk.LEFT)
        self.log_box = scrolledtext.ScrolledText(
            self._console_frame, bg="#050607", fg="#62d66f",
            font=("Consolas", 8), borderwidth=0, height=5, relief=tk.FLAT,
        )
        self.log_box.pack(fill=tk.X, padx=10, pady=(0, 10))
        # _console_frame is not packed — shown only when toggled

        self.details_drawer = self._panel(body)
        self.details_drawer.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.details_drawer.config(width=500)
        self.details_drawer.pack_propagate(False)

        # ── Live Event Timeline ───────────────────────────────────────────────
        feed_wrap = tk.Frame(self.details_drawer, bg=self.UI_PANEL)
        feed_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._section_label(feed_wrap, "LIVE EVENT TIMELINE").pack(anchor="w")
        self.event_filter_row = tk.Frame(feed_wrap, bg=self.UI_PANEL)
        self.event_filter_row.pack(fill=tk.X, pady=(6, 4))
        for col in range(5):
            self.event_filter_row.grid_columnconfigure(col, weight=1, uniform="event_filter")
        self.event_filter_buttons = {}
        event_filters = (
            ("ALL",     "ALL"),
            ("VALUABLE","VALUE"),
            ("SCAN",    "SCAN"),
            ("ALERT",   "ALERT"),
            ("JUMP",    "JUMP"),
            ("ROUTE",   "ROUTE"),
            ("SYSTEM",  "SYSTEM"),
            ("MUSIC",   "MUSIC"),
            ("DSS",     "DSS"),
            ("DOCK",    "DOCK"),
            ("INFO",    "INFO"),
        )
        for idx, (tag, label) in enumerate(event_filters):
            btn = tk.Button(
                self.event_filter_row,
                text=label,
                command=lambda t=tag: self.set_event_feed_filter(t),
                bg=self.UI_PANEL,
                fg=COLOR_TEXT if tag == "ALL" else "#888",
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT,
                bd=0,
                padx=5,
                pady=2,
                activebackground=self.UI_PANEL_2,
                activeforeground=COLOR_ACCENT,
            )
            btn.grid(row=idx // 5, column=idx % 5, sticky="ew", padx=2, pady=2)
            self.event_filter_buttons[tag] = btn
        event_text_wrap = tk.Frame(feed_wrap, bg="#0b0f13")
        event_text_wrap.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.event_feed_scroll = tk.Scrollbar(event_text_wrap, orient=tk.VERTICAL)
        self.event_feed_list = tk.Text(
            event_text_wrap,
            bg="#0b0f13",
            fg=COLOR_TEXT,
            font=self.UI_MONO,
            height=1,
            relief=tk.FLAT,
            highlightthickness=0,
            borderwidth=0,
            wrap=tk.WORD,
            padx=8,
            pady=6,
            yscrollcommand=self.event_feed_scroll.set,
        )
        self.event_feed_scroll.config(command=self.event_feed_list.yview)
        self.event_feed_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.event_feed_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.event_feed_list.config(state=tk.DISABLED)
        self.event_feed_list.bind("<Button-1>", self._select_event_feed_line)
        self.event_feed_list.bind("<Double-Button-1>", lambda e: self._open_selected_event_feed_link())

        self.ground_lat_entry.delete(0, tk.END)
        self.ground_lon_entry.delete(0, tk.END)
        self.ground_lat_entry.insert(0, f"{getattr(self, 'target_lat', 0.0):.6f}")
        self.ground_lon_entry.insert(0, f"{getattr(self, 'target_lon', 0.0):.6f}")

    def _build_companion_dashboard_body(self):
        body = tk.Frame(self.dashboard_host, bg=self.UI_BG)
        self.dashboard_page = body
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        flight_deck = tk.Frame(body, bg=self.UI_BG)
        flight_deck.pack(fill=tk.X, pady=(0, 8))
        flight_deck.grid_columnconfigure(0, weight=2, uniform="deck")
        flight_deck.grid_columnconfigure(1, weight=2, uniform="deck")
        flight_deck.grid_columnconfigure(2, weight=4, uniform="deck")

        flight_card = self._panel(flight_deck, border=COLOR_ACCENT)
        flight_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._section_label(flight_card, "CURRENT FLIGHT").pack(anchor="w", padx=12, pady=(10, 0))
        flight_stats = tk.Frame(flight_card, bg=self.UI_PANEL)
        flight_stats.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 8))
        self.sys_stat = self.create_stat(flight_stats, "CURRENT SYSTEM", "---")
        self.nav_stat = self.create_stat(flight_stats, "NAV TARGET", "---")
        self.scan_stat = self.create_stat(flight_stats, "SCAN PROGRESS", "0 / 0")
        self.flight_strip_canvas = tk.Canvas(
            flight_card,
            height=78,
            bg="#090d12",
            highlightthickness=0,
            bd=0,
        )
        self.flight_strip_canvas.pack(fill=tk.X, padx=12, pady=(0, 10))
        self.flight_strip_canvas.bind("<Configure>", self._draw_flight_strip)

        self.carrier_panel = self._panel(flight_deck)
        self.carrier_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        carrier_hdr = tk.Frame(self.carrier_panel, bg=self.UI_PANEL)
        carrier_hdr.pack(fill=tk.X, padx=12, pady=(10, 4))
        self._section_label(carrier_hdr, "FLEET CARRIER").pack(side=tk.LEFT)
        self.carrier_panel_badge = tk.Label(carrier_hdr, text="IDLE", fg="black", bg=self.UI_DIM, font=("Segoe UI", 7, "bold"), padx=6, pady=2)
        self.carrier_panel_badge.pack(side=tk.RIGHT)
        self.carrier_panel_name = tk.Label(self.carrier_panel, text="Dock at your carrier to sync.", fg=self.UI_DIM, bg=self.UI_PANEL, font=self.UI_MONO_BOLD, anchor="w")
        self.carrier_panel_name.pack(fill=tk.X, padx=12)
        self.carrier_panel_loc = tk.Label(self.carrier_panel, text="", fg=self.UI_MUTED, bg=self.UI_PANEL, font=self.UI_MONO, anchor="w")
        self.carrier_panel_loc.pack(fill=tk.X, padx=12, pady=(1, 0))
        self.carrier_panel_jump = tk.Label(self.carrier_panel, text="", fg=COLOR_ACCENT, bg=self.UI_PANEL, font=("Segoe UI", 8, "bold"), anchor="w")
        self.carrier_panel_jump.pack(fill=tk.X, padx=12, pady=(1, 0))
        fuel_row = tk.Frame(self.carrier_panel, bg=self.UI_PANEL)
        fuel_row.pack(fill=tk.X, padx=12, pady=(8, 10))
        self.carrier_fuel_bar_bg = tk.Frame(fuel_row, bg="#1a2430", height=7)
        self.carrier_fuel_bar_bg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.carrier_fuel_bar_bg.pack_propagate(False)
        self.carrier_fuel_fill = tk.Frame(self.carrier_fuel_bar_bg, bg=self.UI_OK, height=7)
        self.carrier_fuel_fill.place(x=0, y=0, relheight=1.0, width=0)
        self.carrier_fuel_txt = tk.Label(fuel_row, text="", fg=self.UI_DIM, bg=self.UI_PANEL, font=("Segoe UI", 7))
        self.carrier_fuel_txt.pack(side=tk.LEFT, padx=(8, 0))

        route_ground = tk.Frame(flight_deck, bg=self.UI_BG)
        route_ground.grid(row=0, column=2, sticky="nsew")
        route_ground.grid_columnconfigure(0, weight=1)
        route_ground.grid_rowconfigure(0, weight=1)

        self.wp_panel = self._panel(route_ground, border=COLOR_ACCENT)
        self.wp_panel.grid(row=0, column=0, sticky="nsew")
        wp_head = tk.Frame(self.wp_panel, bg=self.UI_PANEL)
        wp_head.pack(fill=tk.X, padx=12, pady=(10, 0))
        self._section_label(wp_head, "ROUTE NOTES").pack(side=tk.LEFT)
        self.wp_dist_lbl = tk.Label(wp_head, text="", font=self.UI_MONO_BOLD, fg=COLOR_ACCENT, bg=self.UI_PANEL)
        self.wp_dist_lbl.pack(side=tk.RIGHT)
        self.wp_name_lbl = tk.Label(self.wp_panel, text="NO ACTIVE ROUTE", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w")
        self.wp_name_lbl.pack(fill=tk.X, padx=12, pady=(6, 0))
        self.wp_info_wrap = tk.Frame(self.wp_panel, bg=self.UI_PANEL)
        self.wp_info_wrap.pack(fill=tk.X, padx=12, pady=(2, 8))
        self.wp_info_scroll = tk.Scrollbar(self.wp_info_wrap, orient=tk.VERTICAL)
        self.wp_info_text = tk.Text(
            self.wp_info_wrap,
            bg=self.UI_PANEL,
            fg=self.UI_MUTED,
            font=self.UI_MONO,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.WORD,
            yscrollcommand=self.wp_info_scroll.set,
            height=3,
        )
        self.wp_info_scroll.config(command=self.wp_info_text.yview)
        self.wp_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.wp_info_text.config(state=tk.DISABLED)
        self.wp_info_scroll_visible = False
        self.wp_info_text.bind("<Enter>", lambda e: self._toggle_wp_scrollbar(True))
        self.wp_info_text.bind("<Leave>", lambda e: self._toggle_wp_scrollbar(False))
        self.wp_info_text.bind("<MouseWheel>", self._on_wp_info_wheel)

        content = tk.Frame(body, bg=self.UI_BG)
        content.pack(fill=tk.BOTH, expand=True)
        content.grid_columnconfigure(0, weight=3, uniform="streams")
        content.grid_columnconfigure(1, weight=2, uniform="streams")
        content.grid_rowconfigure(0, weight=1)

        history_panel = self._panel(content, border=COLOR_ACCENT)
        history_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        history_header = tk.Frame(history_panel, bg=self.UI_PANEL)
        history_header.pack(fill=tk.X, padx=12, pady=(10, 6))
        self._section_label(history_header, "JOURNAL HISTORY").pack(side=tk.LEFT)
        self.journal_history_count_lbl = tk.Label(
            history_header,
            text="LIVE",
            fg=COLOR_ACCENT,
            bg=self.UI_PANEL,
            font=("Consolas", 8, "bold"),
        )
        self.journal_history_count_lbl.pack(side=tk.RIGHT)
        tk.Label(
            history_panel,
            text="Recent journal activity with event icons and compact context.",
            fg=self.UI_MUTED,
            bg=self.UI_PANEL,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 8))

        history_wrap = tk.Frame(history_panel, bg="#0b0f13")
        history_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.journal_history_canvas = tk.Canvas(
            history_wrap,
            bg="#0b0f13",
            highlightthickness=0,
            borderwidth=0,
        )
        self.journal_history_scroll = tk.Scrollbar(history_wrap, orient=tk.VERTICAL, command=self.journal_history_canvas.yview)
        self.journal_history_canvas.configure(yscrollcommand=self.journal_history_scroll.set)
        self.journal_history_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.journal_history_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.journal_history_canvas.bind("<Configure>", lambda _event: self._render_journal_history_canvas())
        self.journal_history_canvas.bind("<MouseWheel>", self._on_journal_history_wheel)
        self.journal_history_entries = []
        self._journal_icon_cache = {}
        self._render_journal_history_empty()

        self.details_drawer = self._panel(content)
        self.details_drawer.grid(row=0, column=1, sticky="nsew")
        self._build_live_event_timeline(self.details_drawer)

        footer = tk.Frame(body, bg=self.UI_BG)
        footer.pack(fill=tk.X, pady=(6, 0))
        self._action_button(footer, "Rebuild Cache", self.scan_all_logs_threaded, muted=True).pack(side=tk.LEFT)
        self._action_button(footer, "Ground Target", self.open_ground_target_window, muted=True).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(footer, text="2026 insert3coins", font=("Segoe UI", 8), fg=self.UI_DIM, bg=self.UI_BG).pack(side=tk.RIGHT, pady=6)
        self._console_toggle_btn = tk.Button(
            footer,
            text="▶  DEBUG CONSOLE",
            command=self._toggle_console,
            bg=self.UI_BG,
            fg=self.UI_DIM,
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=0,
        )
        self._console_toggle_btn.pack(side=tk.LEFT, padx=(10, 0))

        self._console_visible = False
        self._console_frame = self._panel(body)
        self.log_box = scrolledtext.ScrolledText(
            self._console_frame, bg="#050607", fg="#62d66f",
            font=("Consolas", 8), borderwidth=0, height=4, relief=tk.FLAT,
        )
        self.log_box.pack(fill=tk.X, padx=10, pady=10)

    def _show_embedded_page(self, label, page):
        """Display one native application page in the persistent workspace."""
        for child in self.dashboard_host.winfo_children():
            child.pack_forget()
        page.pack(fill=tk.BOTH, expand=True)
        page.tkraise()
        self._active_page = label
        for name, btn in self.nav_buttons.items():
            active = name == label
            bg = THEME.panel_alt if active else THEME.header
            btn.master.configure(bg=bg)
            btn.configure(bg=bg, fg=THEME.accent if active else THEME.muted)
            self.nav_indicators[name].configure(bg=THEME.accent if active else bg)
        if hasattr(self, "settings_nav_btn"):
            settings_active = label == "SETTINGS"
            settings_bg = THEME.panel_alt if settings_active else THEME.header
            self.settings_nav_btn.master.configure(bg=settings_bg)
            self.settings_nav_indicator.configure(bg=THEME.accent if settings_active else settings_bg)
            self.settings_nav_btn.configure(
                bg=settings_bg,
                fg=THEME.accent if settings_active else THEME.text,
            )

    def show_dashboard_page(self):
        self._show_embedded_page("DASHBOARD", self.dashboard_page)

    def _build_live_event_timeline(self, parent):
        feed_wrap = tk.Frame(parent, bg=self.UI_PANEL)
        feed_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._section_label(feed_wrap, "LIVE EVENT TIMELINE").pack(anchor="w")
        self.event_filter_row = tk.Frame(feed_wrap, bg=self.UI_PANEL)
        self.event_filter_row.pack(fill=tk.X, pady=(6, 4))
        for col in range(5):
            self.event_filter_row.grid_columnconfigure(col, weight=1, uniform="event_filter")
        self.event_filter_buttons = {}
        event_filters = (
            ("ALL", "ALL"), ("VALUABLE", "VALUE"), ("SCAN", "SCAN"), ("ALERT", "ALERT"), ("JUMP", "JUMP"),
            ("ROUTE", "ROUTE"), ("SYSTEM", "SYSTEM"), ("MUSIC", "MUSIC"), ("DSS", "DSS"), ("DOCK", "DOCK"),
            ("INFO", "INFO"),
        )
        for idx, (tag, label) in enumerate(event_filters):
            btn = tk.Button(
                self.event_filter_row,
                text=label,
                command=lambda t=tag: self.set_event_feed_filter(t),
                bg=self.UI_PANEL,
                fg=COLOR_TEXT if tag == "ALL" else "#888",
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT,
                bd=0,
                padx=5,
                pady=2,
                activebackground=self.UI_PANEL_2,
                activeforeground=COLOR_ACCENT,
            )
            btn.grid(row=idx // 5, column=idx % 5, sticky="ew", padx=2, pady=2)
            self.event_filter_buttons[tag] = btn
        event_text_wrap = tk.Frame(feed_wrap, bg="#0b0f13")
        event_text_wrap.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.event_feed_scroll = tk.Scrollbar(event_text_wrap, orient=tk.VERTICAL)
        self.event_feed_list = tk.Text(
            event_text_wrap,
            bg="#0b0f13",
            fg=COLOR_TEXT,
            font=self.UI_MONO,
            height=1,
            relief=tk.FLAT,
            highlightthickness=0,
            borderwidth=0,
            wrap=tk.WORD,
            padx=8,
            pady=6,
            yscrollcommand=self.event_feed_scroll.set,
        )
        self.event_feed_scroll.config(command=self.event_feed_list.yview)
        self.event_feed_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.event_feed_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.event_feed_list.config(state=tk.DISABLED)
        self.event_feed_list.bind("<Button-1>", self._select_event_feed_line)
        self.event_feed_list.bind("<Double-Button-1>", lambda e: self._open_selected_event_feed_link())

    def create_stat(self, parent, label, val):
        tk.Label(parent, text=label, font=("Segoe UI", 8, "bold"), fg=self.UI_DIM, bg=parent.cget("bg")).pack(anchor="w", padx=12, pady=(8, 0))
        l = tk.Label(parent, text=val, font=self.UI_MONO_BOLD, fg=COLOR_TEXT, bg=parent.cget("bg"), anchor="w")
        l.pack(fill=tk.X, padx=12)
        return l

    def _build_ops_card(self, parent, title, row, col):
        card = self._panel(parent)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        tk.Frame(card, bg=COLOR_ORANGE, width=3).pack(side=tk.LEFT, fill=tk.Y)
        inner = tk.Frame(card, bg=self.UI_PANEL)
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(inner, text=title, font=self.UI_FONT_BOLD, fg=COLOR_ORANGE, bg=self.UI_PANEL).pack(anchor="w", padx=12, pady=(10, 0))
        line1 = tk.Label(inner, text="-", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w")
        line1.pack(fill=tk.X, padx=12, pady=(8, 0))
        line2 = tk.Label(inner, text="-", font=self.UI_MONO, fg="#aab4bd", bg=self.UI_PANEL, anchor="w")
        line2.pack(fill=tk.X, padx=12, pady=(4, 0))
        line3 = tk.Label(inner, text="-", font=self.UI_MONO, fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w")
        line3.pack(fill=tk.X, padx=12, pady=(4, 10))
        card.line1 = line1
        card.line2 = line2
        card.line3 = line3
        return card

    def set_log_filter(self, mode):
        self.log_filter = mode
        self._refresh_log_view()

    def set_event_feed_filter(self, mode):
        self.event_feed_filter = mode
        if hasattr(self, "event_filter_buttons"):
            for tag, btn in self.event_filter_buttons.items():
                selected = tag == mode
                btn.config(
                    fg=COLOR_TEXT if selected else "#888",
                    bg=self.UI_PANEL_2 if selected else self.UI_PANEL,
                )
        self._refresh_event_feed()

    def _toggle_console(self):
        self._console_visible = not self._console_visible
        if self._console_visible:
            self._console_frame.pack(fill=tk.X, pady=(4, 0))
            self._console_toggle_btn.config(text="▼  DEBUG CONSOLE")
        else:
            self._console_frame.pack_forget()
            self._console_toggle_btn.config(text="▶  DEBUG CONSOLE")

    def add_event_feed_entry(self, tag, message, severity="INFO", copy_text=None, url=None):
        if threading.current_thread() is not threading.main_thread():
            try:
                with self._event_feed_pending_lock:
                    self._event_feed_pending.append((tag, message, severity, copy_text, url))
            except Exception:
                pass
            return
        if not message:
            return
        if getattr(self, "batch_mode", False) and getattr(self, "is_first_load", False):
            return
        msg_clean = str(message).replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
        sev = (severity or "INFO").upper()
        if sev == "ERROR":
            sev = "FAIL"
        entry = {
            "ts": time.time(),
            "tag": (tag or "INFO").upper(),
            "severity": sev,
            "message": msg_clean,
            "copy_text": copy_text or str(message),
            "url": url,
            "new_until": time.time() + 6.0,
        }
        if self.event_feed_entries:
            prev = self.event_feed_entries[0]
            if (
                prev.get("tag") == entry["tag"]
                and prev.get("message") == entry["message"]
                and abs(prev.get("ts", 0) - entry["ts"]) < 1.5
            ):
                return
        self.event_feed_entries.insert(0, entry)
        if len(self.event_feed_entries) > self.event_feed_max_entries:
            self.event_feed_entries = self.event_feed_entries[:self.event_feed_max_entries]
        self._refresh_event_feed()

    def _tick_event_feed_queue(self):
        if not getattr(self, "is_running", True):
            return
        pending = []
        history_pending = []
        try:
            with self._event_feed_pending_lock:
                while self._event_feed_pending and len(pending) < 50:
                    pending.append(self._event_feed_pending.popleft())
                while getattr(self, "_journal_history_pending", None) and len(history_pending) < 40:
                    history_pending.append(self._journal_history_pending.popleft())
        except Exception:
            pending = []
            history_pending = []
        for args in pending:
            try:
                self.add_event_feed_entry(*args)
            except Exception:
                pass
        for args in history_pending:
            try:
                self.add_journal_history_entry(*args)
            except Exception:
                pass
        try:
            self.root.after(100, self._tick_event_feed_queue)
        except Exception:
            pass

    def _resource_file(self, *parts):
        base = getattr(sys, "_MEIPASS", os.path.abspath("."))
        return os.path.join(base, *parts)

    def _journal_icon_for_event(self, event_name):
        event_name = event_name or "Unknown"
        cache_key = str(event_name)
        if cache_key in self._journal_icon_cache:
            return self._journal_icon_cache[cache_key]
        candidates = [
            self._resource_file("Images", "History", "Journal", f"{event_name}.png"),
            self._resource_file("Images", "History", "Journal", f"{event_name}.PNG"),
            self._resource_file("Images", "History", "Journal", "Unknown.png"),
        ]
        image = None
        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                image = tk.PhotoImage(file=path)
                if image.width() > 34 or image.height() > 34:
                    factor = max(1, int(math.ceil(max(image.width() / 34, image.height() / 34))))
                    image = image.subsample(factor, factor)
                break
            except Exception:
                image = None
        self._journal_icon_cache[cache_key] = image
        return image

    def _render_journal_history_empty(self):
        if not hasattr(self, "journal_history_canvas"):
            return
        canvas = self.journal_history_canvas
        canvas.delete("all")
        canvas.configure(scrollregion=(0, 0, max(canvas.winfo_width(), 1), max(canvas.winfo_height(), 1)))
        canvas.create_text(
            16, 20,
            text="Waiting for live journal events",
            fill=self.UI_MUTED,
            font=("Segoe UI", 10, "bold"),
            anchor="nw",
        )
        canvas.create_text(
            16, 46,
            text="Events will appear here as Elite Dangerous writes the journal.",
            fill=self.UI_DIM,
            font=("Segoe UI", 8),
            anchor="nw",
        )

    def _journal_history_text(self, event_name, payload):
        payload = payload if isinstance(payload, dict) else {}
        title = str(event_name or "Journal")
        detail = ""
        if event_name in ("FSDJump", "CarrierJump", "Location"):
            title = payload.get("StarSystem") or payload.get("star_system") or title
            detail = event_name
        elif event_name == "StartJump":
            title = payload.get("StarSystem") or payload.get("star_system") or "Hyperspace"
            detail = "Jump charging"
        elif event_name == "Scan":
            title = payload.get("BodyName") or payload.get("body_name") or "Body scan"
            detail = payload.get("PlanetClass") or payload.get("StarType") or payload.get("planet_class") or payload.get("star_type") or "Scan"
        elif event_name in ("FSSDiscoveryScan", "DiscoveryScan"):
            count = payload.get("BodyCount") or payload.get("body_count") or payload.get("Bodies") or payload.get("bodies")
            title = "Discovery scan"
            detail = f"{count} bodies detected" if count else "System honk"
        elif event_name in ("SAAScanComplete", "SAASignalsFound", "FSSBodySignals"):
            title = payload.get("BodyName") or payload.get("body_name") or event_name
            bio = payload.get("Signals", {}).get("$SAA_SignalType_Biological;") if isinstance(payload.get("Signals"), dict) else None
            bio = bio if bio is not None else payload.get("bio_count")
            detail = f"Bio signals: {bio}" if bio else event_name
        elif event_name == "ScanOrganic":
            title = payload.get("Species_Localised") or payload.get("Species") or payload.get("species") or "Organic scan"
            sample = payload.get("ScanType") or payload.get("scan_type") or ""
            detail = f"{sample} sample".strip()
        elif event_name in ("Docked", "Undocked"):
            title = payload.get("StationName") or payload.get("station_name") or event_name
            detail = event_name
        elif event_name == "LoadGame":
            title = payload.get("Commander") or payload.get("commander") or "Commander loaded"
            detail = payload.get("Ship_Localised") or payload.get("Ship") or payload.get("ship") or ""
        elif event_name == "Commander":
            title = payload.get("Name") or payload.get("name") or "Commander"
            detail = payload.get("FID") or payload.get("fid") or ""
        elif event_name == "Music":
            track = payload.get("MusicTrack") or payload.get("music_track") or "No Track"
            title = str(track).replace("_", " ")
            detail = "Music mood"
        elif event_name in ("MaterialCollected", "MaterialDiscarded", "MiningRefined", "CollectCargo", "EjectCargo"):
            title = payload.get("Name_Localised") or payload.get("Name") or payload.get("name") or event_name
            count = payload.get("Count") or payload.get("count")
            detail = f"{event_name} x{count}" if count else event_name
        else:
            system = payload.get("StarSystem") or payload.get("star_system")
            body = payload.get("BodyName") or payload.get("body_name")
            station = payload.get("StationName") or payload.get("station_name")
            detail = system or body or station or ""
        return title, detail

    def add_journal_history_entry(self, event_name, payload=None):
        if threading.current_thread() is not threading.main_thread():
            try:
                with self._event_feed_pending_lock:
                    self._journal_history_pending.append((event_name, payload))
            except Exception:
                pass
            return
        if not hasattr(self, "journal_history_canvas") or not event_name:
            return
        title, detail = self._journal_history_text(event_name, payload)
        entry = {
            "ts": time.time(),
            "event": str(event_name),
            "title": title,
            "detail": detail,
        }
        if self.journal_history_entries:
            prev = self.journal_history_entries[0]
            if prev.get("event") == entry["event"] and prev.get("title") == entry["title"] and abs(prev.get("ts", 0) - entry["ts"]) < 1.0:
                return
        self.journal_history_entries.insert(0, entry)
        self.journal_history_entries = self.journal_history_entries[:self.JOURNAL_HISTORY_LIMIT]
        self._render_journal_history_canvas()
        if hasattr(self, "journal_history_count_lbl"):
            self.journal_history_count_lbl.config(text=f"{len(self.journal_history_entries)} EVENTS")

    def _render_journal_history_canvas(self):
        if not hasattr(self, "journal_history_canvas"):
            return
        entries = getattr(self, "journal_history_entries", []) or []
        if not entries:
            self._render_journal_history_empty()
            return

        canvas = self.journal_history_canvas
        width = max(canvas.winfo_width(), 320)
        row_h = 62
        pad = 8
        canvas.delete("all")
        for idx, entry in enumerate(entries[:self.JOURNAL_HISTORY_LIMIT]):
            y = pad + idx * row_h
            canvas.create_rectangle(
                pad, y, width - pad, y + row_h - 6,
                fill="#0d1318",
                outline=self.UI_BORDER,
            )
            icon = self._journal_icon_for_event(entry.get("event"))
            if icon:
                canvas.create_image(pad + 23, y + 28, image=icon)
            else:
                canvas.create_text(pad + 23, y + 28, text="J", fill=COLOR_ACCENT, font=("Segoe UI", 12, "bold"))

            text_x = pad + 50
            event_name = entry.get("event", "Journal")
            ts_txt = datetime.fromtimestamp(entry.get("ts", time.time())).strftime("%H:%M:%S")
            canvas.create_text(text_x, y + 9, text=event_name, fill=COLOR_ORANGE, font=("Segoe UI", 8, "bold"), anchor="nw")
            canvas.create_text(width - pad - 10, y + 9, text=ts_txt, fill=self.UI_DIM, font=("Consolas", 8), anchor="ne")
            canvas.create_text(
                text_x, y + 27,
                text=str(entry.get("title", ""))[:90],
                fill=COLOR_TEXT,
                font=("Segoe UI", 10, "bold"),
                anchor="nw",
            )
            detail = str(entry.get("detail") or "")
            if detail:
                canvas.create_text(
                    text_x, y + 46,
                    text=detail[:110],
                    fill=self.UI_MUTED,
                    font=("Consolas", 8),
                    anchor="nw",
                )
        total_h = pad + len(entries[:self.JOURNAL_HISTORY_LIMIT]) * row_h + pad
        canvas.configure(scrollregion=(0, 0, width, total_h))

    def _on_journal_history_wheel(self, event):
        try:
            direction = -1 if event.delta > 0 else 1
            self.journal_history_canvas.yview_scroll(direction * 4, "units")
            return "break"
        except Exception:
            return None

    def _event_feed_matches_filter(self, entry):
        mode = getattr(self, "event_feed_filter", "ALL")
        if mode == "ALL":
            return True
        return entry.get("tag") == mode

    def _event_feed_row_color(self, entry):
        sev = entry.get("severity", "INFO")
        tag = entry.get("tag", "INFO")
        if sev == "FAIL":
            base = "#ff4d4d"
        elif sev == "WARN":
            base = COLOR_ORANGE
        else:
            base = _FEED_TAG_COLORS.get(tag, COLOR_TEXT)
        if time.time() <= entry.get("new_until", 0):
            if sev == "FAIL":
                return "#ff7f7f"
            if sev == "WARN":
                return "#ff9a4d"
            return "#d7f4ff"
        return base

    @staticmethod
    def _event_feed_row_text(row):
        ts_txt = datetime.fromtimestamp(row.get("ts", time.time())).strftime("%H:%M:%S")
        return f"[{ts_txt}] [{row.get('tag', 'INFO')}] {row.get('message', '')}"

    def _recolor_event_feed_rows(self):
        if not hasattr(self, "event_feed_list"):
            return
        self.event_feed_list.config(state=tk.NORMAL)
        for idx in range(max(self.event_feed_display_limit, len(getattr(self, "event_feed_view", []))) + 1):
            self.event_feed_list.tag_remove(f"event_row_{idx}", "1.0", tk.END)
        for idx, row in enumerate(getattr(self, "event_feed_view", [])):
            tag = f"event_row_{idx}"
            self.event_feed_list.tag_add(tag, f"{idx + 1}.0", f"{idx + 2}.0")
            self.event_feed_list.tag_config(tag, foreground=self._event_feed_row_color(row))
        self.event_feed_list.config(state=tk.DISABLED)

    def _event_feed_delete_rows(self, start_idx, end_idx):
        if end_idx <= start_idx:
            return
        self.event_feed_list.delete(f"{start_idx + 1}.0", f"{end_idx + 1}.0")

    def _event_feed_insert_rows(self, start_idx, lines):
        for offset, line in enumerate(lines):
            self.event_feed_list.insert(f"{start_idx + offset + 1}.0", line + "\n")

    def _refresh_event_feed(self):
        if not hasattr(self, "event_feed_list"):
            return

        visible = [e for e in self.event_feed_entries if self._event_feed_matches_filter(e)]
        rows = visible
        rows = rows[:self.event_feed_display_limit]
        lines = [self._event_feed_row_text(row) for row in rows]
        old_lines = getattr(self, "_event_feed_render_lines", [])

        if old_lines == lines:
            self.event_feed_view = rows
            self._recolor_event_feed_rows()
            return

        self.event_feed_list.config(state=tk.NORMAL)
        # Common live path: a new event appears at the top and older rows shift down.
        if lines and old_lines and lines[1:] == old_lines[: len(lines) - 1]:
            self.event_feed_list.insert("1.0", lines[0] + "\n")
            if len(old_lines) >= len(lines):
                self._event_feed_delete_rows(len(lines), len(old_lines) + 1)
        else:
            prefix = 0
            max_prefix = min(len(old_lines), len(lines))
            while prefix < max_prefix and old_lines[prefix] == lines[prefix]:
                prefix += 1

            suffix = 0
            while (
                suffix < (len(old_lines) - prefix)
                and suffix < (len(lines) - prefix)
                and old_lines[len(old_lines) - 1 - suffix] == lines[len(lines) - 1 - suffix]
            ):
                suffix += 1

            old_end = len(old_lines) - suffix
            new_end = len(lines) - suffix
            if prefix < old_end:
                self._event_feed_delete_rows(prefix, old_end)
            self._event_feed_insert_rows(prefix, lines[prefix:new_end])

        self.event_feed_view = rows
        self._event_feed_render_lines = lines
        self._recolor_event_feed_rows()

    def _select_event_feed_line(self, event):
        if not hasattr(self, "event_feed_list"):
            return None
        try:
            idx = int(self.event_feed_list.index(f"@{event.x},{event.y}").split(".")[0]) - 1
        except Exception:
            idx = 0
        self.event_feed_selected_idx = idx if 0 <= idx < len(self.event_feed_view) else None
        return None

    def _copy_selected_event_feed(self):
        if not hasattr(self, "event_feed_list"):
            return
        idx = getattr(self, "event_feed_selected_idx", None)
        if idx is None:
            return
        if idx >= len(self.event_feed_view):
            return
        payload = self.event_feed_view[idx].get("copy_text")
        if not payload:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(payload))
        self.root.update()

    def _open_selected_event_feed_link(self):
        if not hasattr(self, "event_feed_list"):
            return
        idx = getattr(self, "event_feed_selected_idx", None)
        if idx is None:
            return
        if idx >= len(self.event_feed_view):
            return
        link = self.event_feed_view[idx].get("url")
        if link:
            webbrowser.open(link)

    def _matches_log_filter(self, text):
        t = text.upper()
        if self.log_filter == "ALL":
            return True
        if self.log_filter == "JUMP":
            return "JUMP" in t or "LOCATION" in t
        if self.log_filter == "SCAN":
            return "SCAN" in t or "HONK" in t or "FSS" in t
        if self.log_filter == "ALERT":
            return "BIO" in t or "VALUABLE" in t or "SYSTEM SCAN COMPLETE" in t
        if self.log_filter == "ERROR":
            return "ERROR" in t or "FAILED" in t or "ERR" in t
        return True

    def _refresh_log_view(self):
        if not hasattr(self, "log_box"):
            return
        self.log_box.delete("1.0", tk.END)
        for line in self.log_entries[-500:]:
            if self._matches_log_filter(line):
                self.log_box.insert(tk.END, line + "\n")
        self.log_box.see(tk.END)

    def log(self, msg):
        # Curated operational stream; Event Feed handles high-volume gameplay events.
        if not isinstance(msg, str):
            return
        upper = msg.upper()
        is_game_version = msg.startswith("Game version detected")
        is_config_debug = msg.startswith("CONFIG FILE:")
        is_journal_change = msg.startswith("Journal file:")
        is_settings = (
            "CONFIGURATION SAVED" in upper
            or "SCREENSHOT CONVERTER" in upper
            or "SETTINGS" in upper
        )
        is_error = ("ERROR" in upper) or ("FAILED" in upper) or ("ERR" in upper) or ("❌" in msg)
        is_cache_or_maint = (
            "REBUILD" in upper
            or "MIGRAT" in upper
            or "SCANNING..." in upper
            or "CACHE" in upper
            or "UPDATE AVAILABLE" in upper
            or "PERF SPIKE" in upper
            or "UI STALL" in upper
        )
        is_screenshot_event = (
            "SCREENSHOT SAVED" in upper
            or "CONVERTED SCREENSHOT" in upper
            or ("SCREENSHOT" in upper and "SAVED" in upper)
        )
        if not (is_game_version or is_config_debug or is_journal_change or is_settings or is_error or is_cache_or_maint or is_screenshot_event):
            return
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.log_entries.append(line)
        if len(self.log_entries) > 2000:
            self.log_entries = self.log_entries[-2000:]
        self.root.after(0, self._refresh_log_view)

    def schedule_dashboard_refresh(self, full=False):
        if full:
            self.dashboard_refresh_full_pending = True
        if self.dashboard_refresh_job is None:
            self.dashboard_refresh_job = self.root.after(120, self._run_scheduled_dashboard_refresh)

    def _run_scheduled_dashboard_refresh(self):
        t0 = self._perf_start()
        self.dashboard_refresh_job = None
        if self.dashboard_refresh_full_pending:
            self.dashboard_refresh_full_pending = False
            self.update_dashboard_ui()
        else:
            self.update_dashboard_panels()
        self._perf_spike("_run_scheduled_dashboard_refresh", t0, threshold_ms=35.0)

    def _get_session_elapsed_text(self):
        elapsed = max(int(time.time() - self.session_start_ts), 0)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def _tick_session_clock(self):
        if not self.is_running:
            return
        if hasattr(self, "summary_session"):
            self.summary_session.config(text=self._get_session_elapsed_text())
        self._recolor_event_feed_rows()
        self.root.after(1000, self._tick_session_clock)

    def _toggle_wp_scrollbar(self, show):
        if show and not self.wp_info_scroll_visible:
            self.wp_info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            self.wp_info_scroll_visible = True
        elif not show and self.wp_info_scroll_visible:
            self.wp_info_scroll.pack_forget()
            self.wp_info_scroll_visible = False

    def _on_wp_info_wheel(self, event):
        try:
            self.wp_info_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        except Exception:
            return None

    def _set_wp_info_text(self, text):
        self.wp_info_text.config(state=tk.NORMAL)
        self.wp_info_text.delete("1.0", tk.END)
        self.wp_info_text.insert("1.0", text or "")
        self.wp_info_text.config(state=tk.DISABLED)
        self.wp_info_text.yview_moveto(0.0)

    @staticmethod
    def _widget_alive(widget):
        try:
            return bool(widget and widget.winfo_exists())
        except Exception:
            return False

    def open_ground_target_window(self):
        if self._widget_alive(getattr(self, "ground_target_window", None)):
            self.ground_target_window.lift()
            self.ground_target_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.ground_target_window = win
        win.title("Ground Target")
        win.geometry(self.config.get("ground_target_window_geometry", "430x230+1220+260"))
        win.configure(bg=self.UI_BG)
        win.minsize(390, 210)

        def _close():
            try:
                self.config["ground_target_window_geometry"] = win.geometry()
                self._save_config_file()
            except Exception:
                pass
            self.ground_target_window = None
            for attr in ("ground_lat_entry", "ground_lon_entry", "ground_status_lbl", "ground_detail_lbl", "ground_popup_toggle_btn"):
                try:
                    setattr(self, attr, None)
                except Exception:
                    pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _close)

        panel = self._panel(win, border=COLOR_ACCENT)
        panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        header = tk.Frame(panel, bg=self.UI_PANEL)
        header.pack(fill=tk.X, padx=12, pady=(10, 4))
        self._section_label(header, "GROUND TARGET").pack(side=tk.LEFT)
        self.ground_popup_toggle_btn = tk.Button(
            header,
            text="Popup On" if getattr(self, "ground_popup_enabled", True) else "Popup Off",
            command=self.toggle_ground_popup,
            bg=self.UI_PANEL,
            fg=COLOR_TEXT if getattr(self, "ground_popup_enabled", True) else self.UI_MUTED,
            font=self.UI_FONT_BOLD,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
        )
        self.ground_popup_toggle_btn.pack(side=tk.RIGHT)

        input_row = tk.Frame(panel, bg=self.UI_PANEL)
        input_row.pack(fill=tk.X, padx=12, pady=(8, 8))
        tk.Label(input_row, text="LATITUDE", font=("Segoe UI", 8, "bold"), fg=self.UI_MUTED, bg=self.UI_PANEL).grid(row=0, column=0, sticky="w")
        tk.Label(input_row, text="LONGITUDE", font=("Segoe UI", 8, "bold"), fg=self.UI_MUTED, bg=self.UI_PANEL).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.ground_lat_entry = tk.Entry(input_row, bg="#090c10", fg=COLOR_TEXT, font=self.UI_MONO, insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.ground_lon_entry = tk.Entry(input_row, bg="#090c10", fg=COLOR_TEXT, font=self.UI_MONO, insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.ground_lat_entry.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        self.ground_lon_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(3, 0))
        input_row.grid_columnconfigure(0, weight=1)
        input_row.grid_columnconfigure(1, weight=1)
        self.ground_lat_entry.insert(0, f"{getattr(self, 'target_lat', 0.0):.6f}")
        self.ground_lon_entry.insert(0, f"{getattr(self, 'target_lon', 0.0):.6f}")

        btn_row = tk.Frame(panel, bg=self.UI_PANEL)
        btn_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        self._action_button(btn_row, "Set Target", self.set_ground_target_from_entries, accent=True).pack(side=tk.LEFT)
        self._action_button(btn_row, "Use Current Position", self.set_ground_target_here).pack(side=tk.LEFT, padx=(8, 0))
        self._action_button(btn_row, "Clear", self.clear_ground_target, muted=True).pack(side=tk.LEFT, padx=(8, 0))

        self.ground_status_lbl = tk.Label(panel, text="Target: OFF", font=self.UI_MONO_BOLD, fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w")
        self.ground_status_lbl.pack(fill=tk.X, padx=12)
        self.ground_detail_lbl = tk.Label(panel, text="Set a lat/lon target to start tracking.", font=self.UI_MONO, fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w")
        self.ground_detail_lbl.pack(fill=tk.X, padx=12, pady=(3, 12))
        self.update_ground_target_ui()

    def check_updates(self):
        try:
            url = "https://api.github.com/repos/insert3coins/VoidCompass-Release/releases/latest"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                tag = data.get("tag_name", "").lstrip("v")
                html_url = data.get("html_url", "")
                
                current_v = [int(x) for x in APP_VERSION.split('.')]
                remote_v = [int(x) for x in tag.split('.')]
                
                if remote_v > current_v:
                    self.root.after(0, lambda: self.show_update_btn(html_url, tag))
        except Exception:
            pass

    def show_update_btn(self, url, tag):
        self.log(f"✨ UPDATE AVAILABLE: v{tag}")
        target = getattr(self, "nav_utilities", self.nav)
        btn = self._action_button(target, f"Update v{tag}", lambda: webbrowser.open(url), accent=True)
        btn.pack(fill=tk.X, pady=(6, 0))

    def update_nav_label(self):
        txt = "NO ROUTE"
        if self.dest_name:
            txt = self.dest_name
        
        if not self.batch_mode:
            self.root.after(0, lambda: self.nav_stat.config(text=txt))

    def _flight_strip_context(self):
        current = self.current_sys if self.current_sys and self.current_sys != "---" else "---"
        previous = getattr(self, "previous_sys", None)
        previous_coords = getattr(self, "previous_coords", None)
        next_name = None
        next_coords = None
        route_position = None

        route = list(getattr(self, "route_list", None) or [])
        entries = getattr(self, "nav_route_entries", None) or []
        route_idx = -1
        if current != "---":
            try:
                route_idx = route.index(current)
            except ValueError:
                route_idx = -1

        if route:
            if route_idx > 0:
                previous = route[route_idx - 1]
                if route_idx - 1 < len(entries):
                    previous_coords = entries[route_idx - 1].get("StarPos") or previous_coords
            if route_idx >= 0:
                route_position = (route_idx + 1, len(route))
                if route_idx + 1 < len(route):
                    next_name = route[route_idx + 1]
                    if route_idx + 1 < len(entries):
                        next_coords = entries[route_idx + 1].get("StarPos")
            else:
                # Elite's NavRoute.json usually lists upcoming hops only, so the
                # first entry is the real next jump when current is not present.
                route_position = (0, len(route))
                next_name = route[0]
                if entries:
                    next_coords = entries[0].get("StarPos")

        if not next_name:
            target_wp = getattr(self, "target_waypoint", None)
            if target_wp and target_wp.get("name"):
                next_name = target_wp.get("name")
                next_coords = target_wp.get("coords")

        if not next_name:
            next_name = getattr(self, "dest_name", None)
        if next_name and not next_coords:
            for entry in getattr(self, "nav_route_entries", None) or []:
                if entry.get("StarSystem") == next_name:
                    next_coords = entry.get("StarPos")
                    break

        prev_distance_txt = "--"
        next_distance_txt = "--"
        current_coords = getattr(self, "current_coords", None)
        if current_coords and previous_coords:
            try:
                dist = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(previous_coords, current_coords)))
                prev_distance_txt = f"{dist:,.1f} LY"
            except Exception:
                prev_distance_txt = "--"
        if current_coords and next_coords:
            try:
                dist = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(current_coords, next_coords)))
                next_distance_txt = f"{dist:,.1f} LY"
            except Exception:
                next_distance_txt = "--"

        if route_position and route_position[0] > 0:
            route_txt = f"ROUTE {route_position[0]}/{route_position[1]}"
        elif route:
            route_txt = f"ROUTE {len(route)} JUMPS"
        else:
            route_txt = "NO NAV ROUTE"

        return {
            "previous": previous or "---",
            "current": current,
            "next": next_name or "---",
            "route": route_txt,
            "prev_distance": prev_distance_txt,
            "next_distance": next_distance_txt,
            "has_route": bool(route or next_name),
        }

    def _draw_flight_strip(self, event=None):
        canvas = getattr(self, "flight_strip_canvas", None)
        if not self._widget_alive(canvas):
            return
        try:
            w = max(canvas.winfo_width(), 260)
            h = max(canvas.winfo_height(), 72)
            canvas.delete("all")

            ctx = self._flight_strip_context()
            spine_y = 34
            left_x = 34
            center_x = w // 2
            right_x = max(w - 34, center_x + 34)

            canvas.create_rectangle(0, 0, w, h, fill="#090d12", outline="")
            canvas.create_line(left_x, spine_y, right_x, spine_y, fill=self.UI_BORDER, width=2)
            canvas.create_line(left_x, spine_y, center_x, spine_y, fill=COLOR_ACCENT, width=3)
            if ctx["has_route"]:
                canvas.create_line(center_x, spine_y, right_x, spine_y, fill=COLOR_ORANGE, width=2, dash=(5, 5))

            nodes = [
                (left_x, "PREV", ctx["previous"], self.UI_MUTED, 5),
                (center_x, "CURRENT", ctx["current"], COLOR_ACCENT, 7),
                (right_x, "NEXT", ctx["next"], COLOR_ORANGE if ctx["has_route"] else self.UI_DIM, 5),
            ]
            for x, label, name, color, radius in nodes:
                canvas.create_oval(x - radius, spine_y - radius, x + radius, spine_y + radius, outline=color, width=2, fill="#090d12")
                canvas.create_text(x, 14, text=label, fill=color if name != "---" else self.UI_DIM, font=("Segoe UI", 7, "bold"))

            canvas.create_text((left_x + center_x) // 2, spine_y - 12, text=ctx["prev_distance"], fill=self.UI_MUTED, font=("Consolas", 8, "bold"))
            canvas.create_text((center_x + right_x) // 2, spine_y - 12, text=ctx["next_distance"], fill=COLOR_ORANGE if ctx["has_route"] else self.UI_MUTED, font=("Consolas", 8, "bold"))

            footer = ctx["route"]
            canvas.create_text(w // 2, h - 16, text=footer, fill=self.UI_MUTED, font=("Consolas", 8))
        except Exception as exc:
            try:
                canvas.delete("all")
                canvas.create_text(8, 12, anchor="nw", text=f"Flight strip unavailable: {exc}", fill=self.UI_FAIL, font=("Consolas", 8))
            except Exception:
                pass

    def set_ground_target_from_entries(self):
        if not (self._widget_alive(getattr(self, "ground_lat_entry", None)) and self._widget_alive(getattr(self, "ground_lon_entry", None))):
            self.open_ground_target_window()
            return
        try:
            lat = float(self.ground_lat_entry.get().strip())
            lon = float(self.ground_lon_entry.get().strip())
        except Exception:
            if self._widget_alive(getattr(self, "ground_status_lbl", None)):
                self.ground_status_lbl.config(text="Target: INVALID LAT/LON", fg="#ff7777")
            if self._widget_alive(getattr(self, "ground_detail_lbl", None)):
                self.ground_detail_lbl.config(text="Use numeric values, e.g. 12.3456 and -98.7654", fg="#ff7777")
            return

        if lat < -90.0 or lat > 90.0:
            if self._widget_alive(getattr(self, "ground_status_lbl", None)):
                self.ground_status_lbl.config(text="Target: INVALID LAT", fg="#ff7777")
            if self._widget_alive(getattr(self, "ground_detail_lbl", None)):
                self.ground_detail_lbl.config(text="Latitude must be between -90 and +90.", fg="#ff7777")
            return
        lon = self._normalize_lon(lon)

        self.target_lat = lat
        self.target_lon = lon
        self.target_latlon_active = True
        self.config["ground_target_active"] = True
        self.config["ground_target_lat"] = lat
        self.config["ground_target_lon"] = lon
        self._save_config_file()
        self.update_ground_target_ui()
        self.add_event_feed_entry("SYSTEM", f"Ground target set: {lat:.6f}, {lon:.6f}", severity="INFO", copy_text=f"{lat:.6f}, {lon:.6f}")

    def set_ground_target_here(self):
        if self.current_latitude is None or self.current_longitude is None:
            if self._widget_alive(getattr(self, "ground_status_lbl", None)):
                self.ground_status_lbl.config(text="Target: NO PLANET POSITION", fg="#ff9a4d")
            if self._widget_alive(getattr(self, "ground_detail_lbl", None)):
                self.ground_detail_lbl.config(text="Current latitude/longitude not available yet.", fg="#ff9a4d")
            return

        self.target_lat = float(self.current_latitude)
        self.target_lon = float(self.current_longitude)
        self.target_latlon_active = True
        self.config["ground_target_active"] = True
        self.config["ground_target_lat"] = self.target_lat
        self.config["ground_target_lon"] = self.target_lon
        self._save_config_file()
        if self._widget_alive(getattr(self, "ground_lat_entry", None)):
            self.ground_lat_entry.delete(0, tk.END)
            self.ground_lat_entry.insert(0, f"{self.target_lat:.6f}")
        if self._widget_alive(getattr(self, "ground_lon_entry", None)):
            self.ground_lon_entry.delete(0, tk.END)
            self.ground_lon_entry.insert(0, f"{self.target_lon:.6f}")
        self.update_ground_target_ui()
        self.add_event_feed_entry("SYSTEM", "Ground target set to current position", severity="INFO")

    def clear_ground_target(self):
        self.target_latlon_active = False
        self.config["ground_target_active"] = False
        self._save_config_file()
        self.update_ground_target_ui()
        self.add_event_feed_entry("SYSTEM", "Ground target cleared", severity="INFO")

    def toggle_ground_popup(self):
        self.ground_popup_enabled = not bool(self.ground_popup_enabled)
        self.config["ground_popup_enabled"] = bool(self.ground_popup_enabled)
        self._save_config_file()
        if self._widget_alive(getattr(self, "ground_popup_toggle_btn", None)):
            self.ground_popup_toggle_btn.config(
                text="Popup On" if self.ground_popup_enabled else "Popup Off",
                fg=COLOR_TEXT if self.ground_popup_enabled else self.UI_MUTED,
            )
        if not self.ground_popup_enabled and self.ground_popup and self.ground_popup.winfo_exists():
            self.ground_popup.withdraw()
            self._ground_popup_visible = False
        self.update_ground_target_ui()

    def _on_ground_popup_press(self, event):
        try:
            if not self.ground_popup or not self.ground_popup.winfo_exists():
                self.ground_popup_drag_origin = None
                return
            self.ground_popup_drag_origin = (
                event.x_root,
                event.y_root,
                self.ground_popup.winfo_x(),
                self.ground_popup.winfo_y(),
            )
        except Exception:
            self.ground_popup_drag_origin = None

    def _on_ground_popup_drag(self, event):
        if not self.ground_popup or not self.ground_popup.winfo_exists():
            return
        if not self.ground_popup_drag_origin:
            return
        ox, oy, wx, wy = self.ground_popup_drag_origin
        dx = event.x_root - ox
        dy = event.y_root - oy
        nx = wx + dx
        ny = wy + dy
        self.ground_popup.geometry(f"+{nx}+{ny}")

    def _on_ground_popup_release(self, _event):
        self.ground_popup_drag_origin = None
        if self.ground_popup and self.ground_popup.winfo_exists():
            w = self.ground_popup.winfo_width()
            h = self.ground_popup.winfo_height()
            x = self.ground_popup.winfo_x()
            y = self.ground_popup.winfo_y()
            self.config["ground_popup_geometry"] = f"{w}x{h}+{x}+{y}"
            self._save_config_file()

    def _ensure_ground_popup(self):
        if self.ground_popup and self.ground_popup.winfo_exists():
            return
        self.ground_popup = tk.Toplevel(self.root)
        self.ground_popup.withdraw()
        self._ground_popup_visible = False
        self.ground_popup.overrideredirect(True)
        self.ground_popup.attributes("-topmost", True)
        self.ground_popup.configure(bg=self.UI_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        self.ground_popup.geometry(self.config.get("ground_popup_geometry", "340x140+1320+160"))
        self.ground_popup.minsize(300, 132)

        title = tk.Frame(self.ground_popup, bg="#0c1014", height=24)
        title.pack(fill=tk.X)
        title.pack_propagate(False)
        self.ground_popup_header = tk.Label(title, text="GROUND TARGET", font=self.UI_FONT_BOLD, fg=COLOR_ORANGE, bg="#0c1014", anchor="w")
        self.ground_popup_header.pack(fill=tk.BOTH, expand=True, padx=8)

        frame = tk.Frame(self.ground_popup, bg=self.UI_PANEL)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 6))

        left = tk.Frame(frame, bg=self.UI_PANEL, width=96, height=96)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        self.ground_popup_canvas = tk.Canvas(left, width=96, height=96, bg=self.UI_PANEL, highlightthickness=0, bd=0)
        self.ground_popup_canvas.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(frame, bg=self.UI_PANEL)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        self.ground_popup_line1 = tk.Label(right, text="-", font=self.UI_MONO_BOLD, fg=COLOR_ACCENT, bg=self.UI_PANEL, anchor="w")
        self.ground_popup_line1.pack(fill=tk.X, pady=(2, 0))
        self.ground_popup_line2 = tk.Label(right, text="-", font=self.UI_MONO, fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w")
        self.ground_popup_line2.pack(fill=tk.X, pady=(6, 0))

        for widget in (self.ground_popup, title, self.ground_popup_header, frame, left, self.ground_popup_canvas, right, self.ground_popup_line1, self.ground_popup_line2):
            widget.bind("<ButtonPress-1>", self._on_ground_popup_press)
            widget.bind("<B1-Motion>", self._on_ground_popup_drag)
            widget.bind("<ButtonRelease-1>", self._on_ground_popup_release)

    def _destroy_ground_popup(self):
        if self.ground_popup and self.ground_popup.winfo_exists():
            try:
                self.ground_popup.destroy()
            except Exception:
                pass
        self.ground_popup = None
        self.ground_popup_header = None
        self.ground_popup_line1 = None
        self.ground_popup_line2 = None
        self.ground_popup_canvas = None
        self._ground_popup_visible = False
        self._ground_popup_last_render_key = None
        self._ground_popup_compass_ids = None

    def _draw_ground_popup_compass(self, solution):
        canvas = self.ground_popup_canvas
        if not canvas:
            return
        try:
            w = int(canvas.cget("width"))
            h = int(canvas.cget("height"))
        except Exception:
            w = 96
            h = 96
        cx = w // 2
        cy = h // 2
        r = min(w, h) // 2 - 8

        ids = getattr(self, "_ground_popup_compass_ids", None)
        if not ids or ids.get("canvas") is not canvas:
            canvas.delete("all")
            ring = canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#555", width=1)
            n = canvas.create_text(cx, cy - r - 4, text="N", fill="#999", font=("Consolas", 8, "bold"))
            e = canvas.create_text(cx + r + 5, cy, text="E", fill="#666", font=("Consolas", 7))
            s = canvas.create_text(cx, cy + r + 6, text="S", fill="#666", font=("Consolas", 7))
            w_txt = canvas.create_text(cx - r - 5, cy, text="W", fill="#666", font=("Consolas", 7))
            # Ship forward marker is always up in this relative compass.
            ship = canvas.create_line(cx, cy + 2, cx, cy - r + 8, fill="#777", width=2)
            needle = canvas.create_line(cx, cy, cx, cy, fill=COLOR_ACCENT, width=3)
            dot = canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
            unknown = canvas.create_text(cx, cy, text="?", fill="#888", font=("Consolas", 14, "bold"), state="hidden")
            ids = {
                "canvas": canvas,
                "ring": ring,
                "n": n,
                "e": e,
                "s": s,
                "w": w_txt,
                "ship": ship,
                "needle": needle,
                "dot": dot,
                "unknown": unknown,
            }
            self._ground_popup_compass_ids = ids
        else:
            # Keep static geometry aligned even if popup scales.
            canvas.coords(ids["ring"], cx - r, cy - r, cx + r, cy + r)
            canvas.coords(ids["n"], cx, cy - r - 4)
            canvas.coords(ids["e"], cx + r + 5, cy)
            canvas.coords(ids["s"], cx, cy + r + 6)
            canvas.coords(ids["w"], cx - r - 5, cy)
            canvas.coords(ids["ship"], cx, cy + 2, cx, cy - r + 8)

        rel = solution.get("heading_delta")
        if rel is None:
            canvas.itemconfig(ids["unknown"], state="normal")
            canvas.itemconfig(ids["needle"], state="hidden")
            canvas.itemconfig(ids["dot"], state="hidden")
            return

        canvas.itemconfig(ids["unknown"], state="hidden")
        canvas.itemconfig(ids["needle"], state="normal")
        canvas.itemconfig(ids["dot"], state="normal")
        rad = math.radians(rel)
        tx = cx + math.sin(rad) * (r - 10)
        ty = cy - math.cos(rad) * (r - 10)
        color = COLOR_ACCENT if abs(rel) > 12 else "#00ff99"
        canvas.coords(ids["needle"], cx, cy, tx, ty)
        canvas.itemconfig(ids["needle"], fill=color)
        canvas.coords(ids["dot"], tx - 3, ty - 3, tx + 3, ty + 3)
        canvas.itemconfig(ids["dot"], fill=color, outline=color)

    def _update_ground_popup(self, solution):
        t0 = self._perf_start()
        if not bool(getattr(self, "ground_popup_enabled", True)):
            if self.ground_popup and self.ground_popup.winfo_exists():
                if getattr(self, "_ground_popup_visible", False):
                    self.ground_popup.withdraw()
                    self._ground_popup_visible = False
            self._ground_popup_last_render_key = None
            self._perf_spike("_update_ground_popup", t0, threshold_ms=22.0)
            return
        should_show = bool(self.target_latlon_active and self.on_planet and solution and solution.get("state") == "OK")
        if not should_show:
            if self.ground_popup and self.ground_popup.winfo_exists():
                if getattr(self, "_ground_popup_visible", False):
                    self.ground_popup.withdraw()
                    self._ground_popup_visible = False
            self._ground_popup_last_render_key = None
            self._perf_spike("_update_ground_popup", t0, threshold_ms=22.0)
            return

        self._ensure_ground_popup()
        if not (self.ground_popup and self.ground_popup.winfo_exists()):
            self._perf_spike("_update_ground_popup", t0, threshold_ms=22.0)
            return

        bearing = solution["bearing"]
        distance_txt = self._format_ground_distance(solution["distance_m"])
        direction = solution["direction"]
        if solution["heading_delta"] is None:
            turn_txt = "HEADING N/A"
        else:
            side = "R" if solution["heading_delta"] > 0 else "L"
            turn_txt = f"{side} {abs(solution['heading_delta']):.0f} deg"

        render_key = (
            int(round(bearing)),
            int(round((solution.get("distance_m") or 0.0) / 10.0)),
            None if solution.get("heading_delta") is None else int(round(solution["heading_delta"])),
            direction,
            distance_txt,
            turn_txt,
        )
        if getattr(self, "_ground_popup_last_render_key", None) != render_key:
            self._ground_popup_last_render_key = render_key
            self._config_label_if_changed(self.ground_popup_line1, text=f"{direction} | {distance_txt}")
            self._config_label_if_changed(self.ground_popup_line2, text=f"Bearing {bearing:03.0f} deg | Turn {turn_txt}")
            self._draw_ground_popup_compass(solution)
        if not getattr(self, "_ground_popup_visible", False):
            self.ground_popup.deiconify()
            self._ground_popup_visible = True
        self._perf_spike("_update_ground_popup", t0, threshold_ms=22.0)

    def _ground_target_solution(self):
        if not getattr(self, "target_latlon_active", False):
            return None
        if self.current_latitude is None or self.current_longitude is None:
            return {"state": "WAIT_POS"}

        bearing = self._bearing_deg(self.current_latitude, self.current_longitude, self.target_lat, self.target_lon)
        distance = self._surface_distance_m(
            self.current_latitude,
            self.current_longitude,
            self.target_lat,
            self.target_lon,
            self.current_planet_radius,
        )
        if self.current_heading is None:
            heading_delta = None
            direction = "HEADING N/A"
        else:
            heading_delta = ((bearing - self.current_heading + 540.0) % 360.0) - 180.0
            direction = self._format_direction(heading_delta)
        return {
            "state": "OK",
            "bearing": bearing,
            "distance_m": distance,
            "direction": direction,
            "heading_delta": heading_delta,
        }

    def update_ground_target_ui(self):
        t0 = self._perf_start()
        has_status = self._widget_alive(getattr(self, "ground_status_lbl", None))
        has_detail = self._widget_alive(getattr(self, "ground_detail_lbl", None))
        if self._widget_alive(getattr(self, "ground_popup_toggle_btn", None)):
            self._config_label_if_changed(
                self.ground_popup_toggle_btn,
                text="Popup On" if self.ground_popup_enabled else "Popup Off",
                fg=COLOR_TEXT if self.ground_popup_enabled else self.UI_MUTED,
            )

        if not self.target_latlon_active:
            if has_status:
                self._config_label_if_changed(self.ground_status_lbl, text="Target: OFF", fg="#888")
            if has_detail:
                self._config_label_if_changed(self.ground_detail_lbl, text="Set a lat/lon target to start tracking.", fg="#888")
            self._update_ground_popup(None)
            self._perf_spike("update_ground_target_ui", t0, threshold_ms=18.0)
            return

        solution = self._ground_target_solution()
        if has_status:
            self._config_label_if_changed(
                self.ground_status_lbl,
                text=f"Target: {self.target_lat:.6f}, {self.target_lon:.6f}",
                fg=COLOR_ACCENT,
            )

        if not solution or solution.get("state") != "OK":
            if has_detail:
                self._config_label_if_changed(self.ground_detail_lbl, text="Awaiting live planetary coordinates...", fg="#ff9a4d")
            self._update_ground_popup(solution)
            self._perf_spike("update_ground_target_ui", t0, threshold_ms=18.0)
            return

        bearing = solution["bearing"]
        distance_txt = self._format_ground_distance(solution["distance_m"])
        direction = solution["direction"]
        if solution["heading_delta"] is None:
            detail = f"Bearing {bearing:03.0f}° | Distance {distance_txt} | {direction}"
        else:
            detail = f"Bearing {bearing:03.0f}° | Distance {distance_txt} | {direction} {abs(solution['heading_delta']):.0f}°"
        if has_detail:
            self._config_label_if_changed(self.ground_detail_lbl, text=detail, fg=COLOR_TEXT)
        self._update_ground_popup(solution)
        self._perf_spike("update_ground_target_ui", t0, threshold_ms=18.0)

    def update_dashboard_panels(self):
        t0 = self._perf_start()
        """Refresh dashboard cards/summary without waypoint recompute."""
        sys_text = self.current_sys.upper()
        if self.star_class: sys_text += f" [{self.star_class}]"
        
        self.sys_stat.config(text=sys_text)
        self.scan_stat.config(text=f"{self.scanned} / {self.total}")
        self.update_nav_label()

        route_text = "INACTIVE"
        route_total = 0
        route_visited = 0
        if self.waypoint_manager.waypoints:
            route_total = len(self.waypoint_manager.waypoints)
            route_visited = sum(1 for wp in self.waypoint_manager.waypoints if wp.get("visited", False))
            route_text = f"{route_visited}/{route_total}"

        traffic_day = self.system_traffic.get("day", 0)
        traffic_week = self.system_traffic.get("week", 0)
        traffic_total = self.system_traffic.get("total", 0)

        self.summary_sys.config(text=self.current_sys or "---")
        self.summary_route.config(text=route_text)
        self.summary_scan.config(text=f"{self.scanned}/{self.total}")
        self.summary_traffic.config(text=f"{traffic_day}/{traffic_week}/{traffic_total}")
        self.summary_session.config(text=self._get_session_elapsed_text())
        cmdr_text = (
            getattr(self, "cmdr_name", None)
            or self.config.get("active_commander_name")
            or "UNKNOWN"
        )
        self.summary_cmdr.config(text=str(cmdr_text).upper())

        hud_on = "ON" if self.hud else "OFF"
        shots_on = "ON" if self.config.get("screenshots_enabled", False) else "OFF"
        self.integration_lbl.config(text=f"HUD: {hud_on} | SHOTS: {shots_on}")

        alerts = []
        if self.system_undiscovered:
            alerts.append("UNDISCOVERED SYSTEM")
        if self.system_bio_signals > 0:
            alerts.append(f"BIO SIGNALS: {self.system_bio_signals}")
        if self.valuable_bodies:
            alerts.append(f"VALUABLE FINDS: {len(self.valuable_bodies)}")
        if self.fss_summary_active:
            alerts.append("FSS SUMMARY ACTIVE")
        alert_text = " | ".join(alerts) if alerts else "NONE"
        alert_fg = COLOR_ORANGE if alerts else self.UI_MUTED
        if self.system_undiscovered or self.valuable_bodies:
            alert_fg = self.UI_WARN
        self.alert_lbl.config(text=alert_text, fg=alert_fg)

        self._draw_flight_strip()
        self._refresh_event_feed()
        self._perf_spike("update_dashboard_panels", t0, threshold_ms=28.0)

    def update_dashboard_ui(self):
        """Force update full dashboard, including waypoint panel."""
        self.update_dashboard_panels()
        try:
            self.update_carrier_panel()
        except Exception as _cp_err:
            import logging
            logging.warning(f"update_carrier_panel error: {_cp_err}")
        self.update_waypoint_display()

    def update_carrier_panel(self):
        """Refresh the sidebar Fleet Carrier status panel from carrier_tracker data."""
        if not hasattr(self, "carrier_panel") or not hasattr(self, "carrier_tracker"):
            return
        cd = self.carrier_tracker.carrier_data
        name     = cd.get("name")
        callsign = cd.get("callsign") or ""
        system   = cd.get("system") or ""
        status   = cd.get("status", "idle")

        _badge_color = {
            "idle":            self.UI_OK,
            "jumping":         COLOR_ACCENT,
            "cooldown":        self.UI_WARN,
            "cooldown_cancel": self.UI_FAIL,
        }
        _badge_text = {
            "idle":            "IDLE",
            "jumping":         "JUMPING",
            "cooldown":        "COOLDOWN",
            "cooldown_cancel": "CANCELLED",
        }

        self.carrier_panel_badge.config(
            text=_badge_text.get(status, status.upper()),
            bg=_badge_color.get(status, self.UI_DIM),
        )

        if name:
            name_txt = f"{name}  ({callsign})" if callsign else name
            self._config_label_if_changed(self.carrier_panel_name, text=name_txt, fg=COLOR_TEXT)
        else:
            self._config_label_if_changed(
                self.carrier_panel_name,
                text="Dock at your carrier to sync.",
                fg=self.UI_DIM,
            )

        self._config_label_if_changed(self.carrier_panel_loc, text=system, fg=self.UI_MUTED)

        dest = cd.get("jump_destination")
        dep  = cd.get("jump_departure_time")
        if status == "jumping" and dest:
            ct = _carrier_countdown(dep)
            jump_txt = f"→ {dest}   {ct}" if ct else f"→ {dest}"
            self._config_label_if_changed(self.carrier_panel_jump, text=jump_txt, fg=COLOR_ACCENT)
        elif status == "cooldown":
            self._config_label_if_changed(
                self.carrier_panel_jump,
                text="Jump complete — cooling down",
                fg=self.UI_WARN,
            )
        elif status == "cooldown_cancel":
            self._config_label_if_changed(
                self.carrier_panel_jump,
                text="Jump cancelled — cooling down",
                fg=self.UI_FAIL,
            )
        else:
            self._config_label_if_changed(self.carrier_panel_jump, text="", fg=self.UI_DIM)

        fuel = cd.get("fuel_level")
        cap  = cd.get("fuel_capacity") or 1000
        if fuel is not None:
            pct   = max(0.0, min(1.0, fuel / cap))
            bar_base_w = self.carrier_fuel_bar_bg.winfo_width() or 240
            bar_w = int(bar_base_w * pct)
            color = self.UI_OK if pct > 0.4 else (self.UI_WARN if pct > 0.15 else self.UI_FAIL)
            self.carrier_fuel_fill.place(x=0, y=0, relheight=1.0, width=bar_w)
            self.carrier_fuel_fill.config(bg=color)
            self._config_label_if_changed(
                self.carrier_fuel_txt,
                text=f"{fuel:,} / {cap:,} T",
                fg=self.UI_MUTED,
            )
        else:
            self.carrier_fuel_fill.place(x=0, y=0, relheight=1.0, width=0)
            self._config_label_if_changed(self.carrier_fuel_txt, text="", fg=self.UI_DIM)

    def update_waypoint_display(self):
        if not self.waypoint_manager.waypoints:
            self.target_waypoint = None
            self.wp_name_lbl.config(text="NO ACTIVE ROUTE")
            self.wp_dist_lbl.config(text="")
            self._set_wp_info_text("")
            self.update_hud()
            return

        # Auto-mark visited based on location
        idx = self.waypoint_manager.get_waypoint_index(self.current_sys)
        if idx != -1:
            changed = False
            visited_now = []
            for i in range(idx + 1):
                if not self.waypoint_manager.waypoints[i].get('visited', False):
                    self.waypoint_manager.waypoints[i]['visited'] = True
                    changed = True
                    visited_now.append(self.waypoint_manager.waypoints[i].get("name", f"Waypoint {i+1}"))
            if changed:
                self.waypoint_manager.save()
                for wp_name in visited_now:
                    self.add_event_feed_entry("ROUTE", f"Waypoint visited: {wp_name}", severity="INFO", copy_text=wp_name)

        # Find next target (first unvisited)
        self.target_waypoint = None
        for wp in self.waypoint_manager.waypoints:
            if not wp.get('visited', False):
                self.target_waypoint = wp
                break
        
        if self.target_waypoint is None:
             self.wp_name_lbl.config(text="ROUTE COMPLETE")
             self.wp_dist_lbl.config(text="")
             self._set_wp_info_text("")
             self.update_hud()
             return
        
        if self.target_waypoint:
            name = self.target_waypoint['name']
            coords = self.target_waypoint['coords']
            note = self.target_waypoint.get('note')
            dist_str = ""
            if coords and self.current_coords:
                d = self.waypoint_manager.get_distance(self.current_coords, coords)
                dist_str = f"({d:,.1f} LY)"

            # Fetch EDSM Info if not cached
            if name not in self.waypoint_cache:
                self.waypoint_cache[name] = {"fetching": True}
                def cb(data):
                    if data:
                        self.waypoint_cache[name] = data
                    else:
                        self.waypoint_cache[name] = {"error": True}
                    self.root.after(0, self.update_waypoint_display)
                self.edsm.fetch_system_details(name, cb)
            
            # Format Info String
            info_text = "Fetching data..."
            cached = self.waypoint_cache.get(name)
            if cached and not cached.get("fetching"):
                if cached.get("error"):
                    info_text = "EDSM Data Unavailable"
                else:
                    p_star = cached.get("primaryStar", {}).get("type", "Unknown Star")
                    if "Main Sequence" in p_star: p_star = p_star.replace(" Main Sequence Star", "")
                    
                    info = cached.get("information", {})
                    gov = info.get("government", "None")
                    alg = info.get("allegiance", "Independent")
                    
                    info_text = f"⭐ {p_star}  🏛️ {gov}  🚩 {alg}"
            
            if note:
                if info_text == "Fetching data..." or info_text == "EDSM Data Unavailable":
                     info_text = f"📝 {note}"
                else:
                     info_text = f"📝 {note}  {info_text}"

            self.wp_name_lbl.config(text=name)
            self.wp_dist_lbl.config(text=dist_str)
            self._set_wp_info_text(info_text)
            self.update_hud()

