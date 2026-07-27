import time
import math
import os
import sys
import threading
import tkinter as tk
import requests
import webbrowser
import re
from datetime import datetime, timezone
from tkinter import scrolledtext

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from ui_theme import THEME, ThemedWindowMixin, apply_window, button, panel, scrollbar, section_label
from version import APP_VERSION
from overlay_input import set_mouse_passthrough
from adaptive_command import AUTOMATIC_MODE_IDLE_S
from stellar_types import star_type_label
import route_strip

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
    "AI":      "#c084fc",  # violet — Compass mood / memory evolution
    "EXPEDITION":"#d8b4fe", # purple — named expedition progress
    "MILESTONE":"#facc15", # gold — durable exploration milestones
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


# How stale the journal/Status.json streams may get before we treat Elite as
# closed for playtime-accrual purposes. Generous: the watcher only fires on
# file changes, so an idle docked commander can be quiet for a while.
GAME_ACTIVE_GRACE_S = 300.0

PROJECT_URL = "https://github.com/insert3coins/VoidCompass"
RELEASES_URL = f"{PROJECT_URL}/releases"
RELEASES_API_URL = "https://api.github.com/repos/insert3coins/VoidCompass/releases/latest"
ISSUES_URL = f"{PROJECT_URL}/issues/new/choose"
WIKI_URL = f"{PROJECT_URL}/wiki"
LICENSE_URL = f"{PROJECT_URL}/blob/master/LICENSE"
FRONTIER_COMMUNITY_URL = "https://www.elitedangerous.com/community"


def _version_key(value):
    """Return a comparable release tuple from tags such as v5.0.1."""
    match = re.search(r"\d+(?:\.\d+)*", str(value or ""))
    if not match:
        return ()
    return tuple(int(part) for part in match.group(0).split("."))


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
            self.brand_row, text="EXPLORATION CONSOLE", font=("Cascadia Mono", 8, "bold"),
            fg=THEME.orange, bg=THEME.header, anchor="w",
        ).pack(fill=tk.X, padx=8, pady=(3, 14))
        tk.Frame(self.brand_row, bg=THEME.accent, height=1).pack(fill=tk.X, padx=8)

        nav_groups = (
            ("CORE", (
                ("⌖", "DASHBOARD", "DASHBOARD", self.show_dashboard_page),
                ("◉", "PROFILE", "PROFILE", self.open_commander_profile_window),
            )),
            ("EXPLORE", (
                ("✦", "EXPLORE", "EXPLORE", self.open_exploration_window),
                ("⚑", "GALAXY", "GALAXY", self.open_bgs_window),
            )),
            ("EXPEDITION", (
                ("⬢", "EXPEDITION", "OVERVIEW", self.show_expedition_page),
                ("∿", "ANALYTICS", "ANALYTICS", self.open_analytics_window),
                ("★", "ACHIEVE", "ACHIEVEMENTS", self.open_achievement_window),
                ("⬢", "CARRIER", "CARRIER", self.open_carrier_window),
                ("⌂", "COLONY", "COLONY", self.open_colonization_window),
            )),
            ("OPERATIONS", (
                ("▦", "OPERATIONS", "OVERVIEW", self.show_operations_page),
                ("⇌", "TRADE", "TRADE", self.open_trade_window),
                ("▦", "SPECIALISTS", "SPECIALISTS", self.open_specialists_window),
            )),
            ("SYSTEM", (
                ("⚙", "ENGINEER", "ENGINEER", self.open_engineer_window),
                ("ⓘ", "ABOUT", "ABOUT", self.show_about_page),
            )),
        )
        self.nav_buttons = {}
        self.nav_indicators = {}
        self.nav_group_bodies = {}
        self.nav_group_buttons = {}

        nav_view = tk.Frame(self.nav, bg=THEME.header)
        nav_view.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(8, 0))
        self.nav_canvas = tk.Canvas(
            nav_view, bg=THEME.header, highlightthickness=0, bd=0,
        )
        self.nav_scrollbar = scrollbar(
            nav_view, orient=tk.VERTICAL, command=self.nav_canvas.yview,
        )
        self.nav_canvas.configure(yscrollcommand=self.nav_scrollbar.set)
        self.nav_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.nav_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        nav_list = tk.Frame(self.nav_canvas, bg=THEME.header)
        nav_window = self.nav_canvas.create_window((0, 0), window=nav_list, anchor="nw")

        def fit_nav(_event=None):
            try:
                self.nav_canvas.itemconfigure(nav_window, width=max(1, self.nav_canvas.winfo_width()))
                self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
            except tk.TclError:
                pass

        def scroll_nav(event):
            if not event.delta:
                return None
            self.nav_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        nav_list.bind("<Configure>", fit_nav, add="+")
        self.nav_canvas.bind("<Configure>", fit_nav, add="+")
        self.nav_canvas.bind("<MouseWheel>", scroll_nav, add="+")
        nav_list.bind("<MouseWheel>", scroll_nav, add="+")

        for group_name, items in nav_groups:
            group = tk.Frame(nav_list, bg=THEME.header)
            group.pack(fill=tk.X, padx=10, pady=(3, 1))
            group_header = tk.Button(
                group, text=f"▾  {group_name}",
                command=lambda name=group_name: self._toggle_navigation_group(name),
                bg=THEME.header, fg=THEME.dim,
                activebackground=THEME.header, activeforeground=THEME.accent,
                font=("Cascadia Mono", 7, "bold"), anchor="w",
                relief=tk.FLAT, bd=0, padx=6, pady=3, cursor="hand2",
            )
            group_header.pack(fill=tk.X)
            group_header.bind("<MouseWheel>", scroll_nav, add="+")
            body = tk.Frame(group, bg=THEME.header)
            body.pack(fill=tk.X)
            self.nav_group_bodies[group_name] = body
            self.nav_group_buttons[group_name] = group_header
            for icon, label, display, command in items:
                active = label == "DASHBOARD"
                row = tk.Frame(body, bg=THEME.panel_alt if active else THEME.header, height=31)
                row.pack(fill=tk.X, pady=1)
                row.pack_propagate(False)
                indicator = tk.Frame(row, bg=THEME.accent if active else row.cget("bg"), width=3)
                indicator.pack(side=tk.LEFT, fill=tk.Y)
                btn = tk.Button(
                    row,
                    text=f"{icon}   {display}",
                    command=lambda name=label, callback=command: self._run_nav_command(name, callback),
                    bg=row.cget("bg"), fg=THEME.accent if active else THEME.muted,
                    activebackground=THEME.panel_alt, activeforeground=THEME.accent,
                    font=("Bahnschrift SemiCondensed", 9, "bold"), anchor="w",
                    relief=tk.FLAT, bd=0, padx=10, pady=5, cursor="arrow" if active else "hand2",
                )
                btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                btn.bind("<MouseWheel>", scroll_nav, add="+")
                row.bind("<MouseWheel>", scroll_nav, add="+")
                self.nav_buttons[label] = btn
                self.nav_indicators[label] = indicator

        self._apply_navigation_group_state()

        utilities = tk.Frame(self.nav, bg=THEME.header)
        self.nav_utilities = utilities
        utilities.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=14)
        settings_row = tk.Frame(utilities, bg=THEME.header, height=34)
        settings_row.pack(fill=tk.X, pady=(0, 4))
        settings_row.pack_propagate(False)
        self.settings_nav_indicator = tk.Frame(settings_row, bg=THEME.header, width=3)
        self.settings_nav_indicator.pack(side=tk.LEFT, fill=tk.Y)
        self.settings_nav_btn = self._action_button(
            settings_row,
            "≡   SETTINGS",
            lambda: self._run_nav_command("SETTINGS", self.open_settings),
        )
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

        # Every embedded workspace can outgrow the window after a resize.
        # Keep one persistent outer viewport so pages that do not own a
        # specialised scroller remain reachable without changing their UI.
        workspace_view = tk.Frame(self.workspace, bg=self.UI_BG)
        workspace_view.pack(fill=tk.BOTH, expand=True)
        workspace_view.grid_rowconfigure(0, weight=1)
        workspace_view.grid_columnconfigure(0, weight=1)
        self.workspace_canvas = tk.Canvas(
            workspace_view, bg=self.UI_BG, highlightthickness=0, bd=0,
        )
        self.workspace_vscroll = scrollbar(
            workspace_view, orient=tk.VERTICAL, command=self.workspace_canvas.yview,
        )
        self.workspace_canvas.configure(
            yscrollcommand=self.workspace_vscroll.set,
        )
        self.workspace_canvas.grid(row=0, column=0, sticky="nsew")
        self.workspace_vscroll.grid(row=0, column=1, sticky="ns")

        self.dashboard_host = tk.Frame(self.workspace_canvas, bg=self.UI_BG)
        self._workspace_window_id = self.workspace_canvas.create_window(
            (0, 0), window=self.dashboard_host, anchor="nw",
        )
        self._workspace_scroll_job = None
        self.workspace_canvas.bind("<Configure>", self._schedule_workspace_scrollregion, add="+")
        self.dashboard_host.bind("<Configure>", self._schedule_workspace_scrollregion, add="+")
        self.root.bind("<MouseWheel>", self._on_workspace_mousewheel, add="+")
        self._active_page = "DASHBOARD"

        self._build_command_dashboard_body()
        self._build_workspace_hubs()
        self._build_about_page()
        self._schedule_workspace_scrollregion()
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
        self.wp_info_scroll = scrollbar(self.wp_info_wrap, orient=tk.VERTICAL)
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
            ("AI",      "AI"),
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
        self.event_feed_scroll = scrollbar(event_text_wrap, orient=tk.VERTICAL)
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

    def _build_command_dashboard_body(self):
        """Build the exploration-first command dashboard."""
        body = tk.Frame(self.dashboard_host, bg=self.UI_BG)
        self.dashboard_page = body
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        mode_bar = self._panel(body, border=COLOR_ACCENT)
        mode_bar.pack(fill=tk.X, pady=(0, 8))
        self.dashboard_deck_heading = tk.Label(
            mode_bar, text="EXPLORATION COMMAND DECK", fg=self.UI_DIM,
            bg=self.UI_PANEL, font=("Segoe UI", 7, "bold"),
        )
        self.dashboard_deck_heading.pack(side=tk.LEFT, padx=(12, 8), pady=8)
        self.dashboard_mode_badge = tk.Label(
            mode_bar, text="GENERAL FLIGHT", fg="black", bg=COLOR_ACCENT,
            font=("Segoe UI", 8, "bold"), padx=8, pady=3,
        )
        self.dashboard_mode_badge.pack(side=tk.LEFT, pady=7)
        self.dashboard_mode_detail = tk.Label(
            mode_bar, text="AUTOMATIC · awaiting journal activity", fg=COLOR_TEXT,
            bg=self.UI_PANEL, font=self.UI_MONO, anchor="w",
        )
        self.dashboard_mode_detail.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.dashboard_health_badge = tk.Label(
            mode_bar, text="NOMINAL", fg="black", bg=self.UI_OK,
            font=("Segoe UI", 7, "bold"), padx=7, pady=2,
        )
        self.dashboard_health_badge.pack(side=tk.RIGHT, padx=(5, 12))
        self.dashboard_mode_lock_btn = self._action_button(
            mode_bar, "MODE · AUTO", self._show_adaptive_mode_menu, muted=True,
        )
        self.dashboard_mode_lock_btn.pack(side=tk.RIGHT, padx=(5, 0), pady=5)
        self.dashboard_mode_open_btn = self._action_button(
            mode_bar, "OPEN MODE", self._adaptive_open_mode_workspace,
        )
        self.dashboard_mode_open_btn.pack(side=tk.RIGHT, padx=(5, 0), pady=5)

        # Hero row: the current system and route own the dashboard's strongest
        # visual weight. Everything below supports these two exploration jobs.
        hero = tk.Frame(body, bg=self.UI_BG)
        hero.pack(fill=tk.X, pady=(0, 8))
        hero.grid_columnconfigure(0, weight=6, uniform="hero")
        hero.grid_columnconfigure(1, weight=4, uniform="hero")
        hero.grid_rowconfigure(0, weight=1)

        system_card = self._panel(hero, border=COLOR_ACCENT)
        system_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        system_head = tk.Frame(system_card, bg=self.UI_PANEL)
        system_head.pack(fill=tk.X, padx=14, pady=(11, 0))
        self.dashboard_context_heading = self._section_label(system_head, "CURRENT SYSTEM")
        self.dashboard_context_heading.pack(side=tk.LEFT)
        self.dashboard_survey_badge = tk.Label(
            system_head, text="AWAITING", fg="black", bg=self.UI_DIM,
            font=("Segoe UI", 7, "bold"), padx=7, pady=2,
        )
        self.dashboard_survey_badge.pack(side=tk.RIGHT)
        self.dashboard_survey_name = tk.Label(
            system_card, text="NO SYSTEM DATA", fg=COLOR_ACCENT, bg=self.UI_PANEL,
            font=("Bahnschrift SemiCondensed", 17, "bold"), anchor="w",
        )
        self.dashboard_survey_name.pack(fill=tk.X, padx=14, pady=(5, 1))
        self.dashboard_survey_detail = tk.Label(
            system_card, text="Scan telemetry will appear here.", fg=COLOR_TEXT,
            bg=self.UI_PANEL, font=("Consolas", 9), anchor="nw", justify=tk.LEFT,
            wraplength=610,
        )
        self.dashboard_survey_detail.pack(fill=tk.X, padx=14, pady=(0, 2))
        self.dashboard_survey_value = tk.Label(
            system_card, text="", fg=COLOR_ORANGE, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"), anchor="w",
        )
        self.dashboard_survey_value.pack(fill=tk.X, padx=14, pady=(1, 5))
        self.dashboard_survey_progress_bg = tk.Frame(
            system_card, bg=self.UI_PANEL_2, height=5,
        )
        self.dashboard_survey_progress_bg.pack(fill=tk.X, padx=14, pady=(0, 8))
        self.dashboard_survey_progress_fill = tk.Frame(
            self.dashboard_survey_progress_bg, bg=COLOR_ACCENT, height=5,
        )
        self.dashboard_survey_progress_fill.place(
            x=0, y=0, relheight=1.0, relwidth=0.0,
        )
        tk.Frame(system_card, bg=self.UI_BORDER, height=1).pack(fill=tk.X, padx=14)

        flight_stats = tk.Frame(system_card, bg=self.UI_PANEL)
        flight_stats.pack(fill=tk.X, padx=2, pady=(0, 2))
        stat_zones = []
        for _index in range(4):
            zone = tk.Frame(flight_stats, bg=self.UI_PANEL)
            zone.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            stat_zones.append(zone)

        self.dashboard_stat_labels = []
        self.dashboard_stat_values = []
        for zone, label, value in zip(
            stat_zones,
            ("SHIP / STATE", "NAVIGATION", "ROUTE", "SURVEY"),
            ("AWAITING LOADOUT", "NO TARGET", "NO ACTIVE ROUTE", "0 / 0"),
        ):
            label_widget = tk.Label(
                zone, text=label, font=("Segoe UI", 8, "bold"),
                fg=self.UI_DIM, bg=self.UI_PANEL, anchor="w",
            )
            label_widget.pack(fill=tk.X, padx=12, pady=(8, 0))
            value_widget = tk.Label(
                zone, text=value, font=self.UI_MONO_BOLD, fg=COLOR_TEXT,
                bg=self.UI_PANEL, anchor="w",
            )
            value_widget.pack(fill=tk.X, padx=12)
            self.dashboard_stat_labels.append(label_widget)
            self.dashboard_stat_values.append(value_widget)
        self.sys_stat, self.nav_stat, self.route_progress_stat, self.scan_stat = self.dashboard_stat_values
        self.dashboard_flight_meta = tk.Label(
            system_card, text="", fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=("Consolas", 8), anchor="w",
        )
        self.dashboard_flight_meta.pack(fill=tk.X, padx=14, pady=(4, 10))
        self.flight_strip_canvas = None

        self.wp_panel = self._panel(hero, border=COLOR_ACCENT)
        self.wp_panel.grid(row=0, column=1, sticky="nsew")
        wp_head = tk.Frame(self.wp_panel, bg=self.UI_PANEL)
        wp_head.pack(fill=tk.X, padx=14, pady=(11, 0))
        self.dashboard_destination_heading = self._section_label(wp_head, "NEXT DESTINATION")
        self.dashboard_destination_heading.pack(side=tk.LEFT)
        self.wp_dist_lbl = tk.Label(wp_head, text="", font=self.UI_MONO_BOLD,
                                    fg=COLOR_ACCENT, bg=self.UI_PANEL)
        self.wp_dist_lbl.pack(side=tk.RIGHT)
        self.wp_name_lbl = tk.Label(
            self.wp_panel, text="NO ACTIVE ROUTE", font=("Bahnschrift SemiCondensed", 15, "bold"),
            fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w",
        )
        self.wp_name_lbl.pack(fill=tk.X, padx=14, pady=(6, 0))
        self.wp_info_wrap = tk.Frame(self.wp_panel, bg=self.UI_PANEL)
        self.wp_info_wrap.pack(fill=tk.BOTH, expand=True, padx=14, pady=(3, 4))
        self.wp_info_scroll = scrollbar(self.wp_info_wrap, orient=tk.VERTICAL)
        self.wp_info_text = tk.Text(
            self.wp_info_wrap, bg=self.UI_PANEL, fg=self.UI_MUTED, font=self.UI_MONO,
            relief=tk.FLAT, borderwidth=0, highlightthickness=0, wrap=tk.WORD,
            yscrollcommand=self.wp_info_scroll.set, height=6,
        )
        self.wp_info_scroll.config(command=self.wp_info_text.yview)
        self.wp_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.wp_info_text.config(state=tk.DISABLED)
        self.wp_info_scroll_visible = False
        self.wp_info_text.bind("<Enter>", lambda _e: self._toggle_wp_scrollbar(True))
        self.wp_info_text.bind("<Leave>", lambda _e: self._toggle_wp_scrollbar(False))
        self.wp_info_text.bind("<MouseWheel>", self._on_wp_info_wheel)
        route_actions = tk.Frame(self.wp_panel, bg=self.UI_PANEL)
        route_actions.pack(fill=tk.X, padx=14, pady=(0, 10))
        self._action_button(route_actions, "COPY NEXT", self._dashboard_copy_next, accent=True).pack(side=tk.LEFT)
        self._action_button(route_actions, "OPEN EXPLORE", self.open_exploration_window).pack(side=tk.LEFT, padx=(6, 0))

        # Supporting row: one next action, the local companion, and expedition
        # logistics. These remain secondary to the system and route above.
        active_row = tk.Frame(body, bg=self.UI_BG)
        active_row.pack(fill=tk.X, pady=(0, 8))
        active_row.grid_columnconfigure(0, weight=4, uniform="active")
        active_row.grid_columnconfigure(1, weight=3, uniform="active")
        active_row.grid_columnconfigure(2, weight=3, uniform="active")
        active_row.grid_rowconfigure(0, weight=1)

        objective_card = self._panel(active_row, border=COLOR_ACCENT)
        objective_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.dashboard_objective_heading = self._section_label(
            objective_card, "EXPLORATION PRIORITY",
        )
        self.dashboard_objective_heading.pack(anchor="w", padx=12, pady=(9, 0))
        self.dashboard_objective_primary = tk.Label(
            objective_card, text="No urgent objective", fg=COLOR_TEXT, bg=self.UI_PANEL,
            font=("Segoe UI", 11, "bold"), anchor="w",
        )
        self.dashboard_objective_primary.pack(fill=tk.X, padx=12, pady=(7, 2))
        self.dashboard_objective_detail = tk.Label(
            objective_card, text="Compass will promote verified exploration work as the situation changes.",
            fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Consolas", 8), anchor="nw",
            justify=tk.LEFT, wraplength=390,
        )
        self.dashboard_objective_detail.pack(fill=tk.X, padx=12, pady=(0, 8))
        objective_actions = tk.Frame(objective_card, bg=self.UI_PANEL)
        objective_actions.pack(fill=tk.X, padx=12, pady=(0, 9))
        self.dashboard_primary_action_btn = self._action_button(
            objective_actions, "OPEN EXPLORE", self.open_exploration_window, accent=True,
        )
        self.dashboard_primary_action_btn.pack(side=tk.LEFT)
        self.dashboard_copy_action_btn = self._action_button(
            objective_actions, "COPY NEXT", self._dashboard_copy_next,
        )
        self.dashboard_copy_action_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.dashboard_explore_action_btn = self._action_button(
            objective_actions, "GALAXY", self.open_bgs_window, muted=True,
        )
        self.dashboard_explore_action_btn.pack(side=tk.LEFT, padx=(6, 0))

        compass_card = self._panel(active_row)
        compass_card.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        compass_head = tk.Frame(compass_card, bg=self.UI_PANEL)
        compass_head.pack(fill=tk.X, padx=12, pady=(9, 0))
        self._section_label(compass_head, "COMPASS").pack(side=tk.LEFT)
        self.dashboard_compass_badge = tk.Label(
            compass_head, text="CALM", fg="black", bg=self.UI_OK,
            font=("Segoe UI", 7, "bold"), padx=6, pady=2,
        )
        self.dashboard_compass_badge.pack(side=tk.RIGHT)
        self.dashboard_compass_identity = tk.Label(
            compass_card, text="Compass · Newly activated", fg=COLOR_ACCENT,
            bg=self.UI_PANEL, font=("Segoe UI", 10, "bold"), anchor="w",
        )
        self.dashboard_compass_identity.pack(fill=tk.X, padx=12, pady=(8, 3))
        self.dashboard_compass_advice = tk.Label(
            compass_card, text="Standing by for verified flight context.", fg=COLOR_TEXT,
            bg=self.UI_PANEL, font=("Segoe UI", 9), anchor="nw", justify=tk.LEFT,
            wraplength=300,
        )
        self.dashboard_compass_advice.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))
        self.dashboard_compass_meta = tk.Label(
            compass_card, text="", fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=("Consolas", 8), anchor="w",
        )
        self.dashboard_compass_meta.pack(fill=tk.X, padx=12, pady=(2, 9))

        self.carrier_panel = self._panel(active_row)
        self.carrier_panel.grid(row=0, column=2, sticky="nsew")
        carrier_hdr = tk.Frame(self.carrier_panel, bg=self.UI_PANEL)
        carrier_hdr.pack(fill=tk.X, padx=12, pady=(9, 4))
        self.dashboard_support_heading = self._section_label(carrier_hdr, "EXPEDITION SUPPORT")
        self.dashboard_support_heading.pack(side=tk.LEFT)
        self.carrier_panel_badge = tk.Label(
            carrier_hdr, text="IDLE", fg="black", bg=self.UI_DIM,
            font=("Segoe UI", 7, "bold"), padx=6, pady=2,
        )
        self.carrier_panel_badge.pack(side=tk.RIGHT)
        self.carrier_panel_name = tk.Label(
            self.carrier_panel, text="Dock at your carrier to sync.", fg=self.UI_DIM,
            bg=self.UI_PANEL, font=self.UI_MONO_BOLD, anchor="w",
        )
        self.carrier_panel_name.pack(fill=tk.X, padx=12)
        self.carrier_panel_loc = tk.Label(
            self.carrier_panel, text="", fg=self.UI_MUTED, bg=self.UI_PANEL,
            font=self.UI_MONO, anchor="w",
        )
        self.carrier_panel_loc.pack(fill=tk.X, padx=12, pady=(1, 0))
        self.carrier_panel_jump = tk.Label(
            self.carrier_panel, text="", fg=COLOR_ACCENT, bg=self.UI_PANEL,
            font=("Segoe UI", 8, "bold"), anchor="w",
        )
        self.carrier_panel_jump.pack(fill=tk.X, padx=12, pady=(1, 0))
        fuel_row = tk.Frame(self.carrier_panel, bg=self.UI_PANEL)
        fuel_row.pack(fill=tk.X, padx=12, pady=(7, 9))
        self.carrier_fuel_bar_bg = tk.Frame(fuel_row, bg="#1a2430", height=7)
        self.carrier_fuel_bar_bg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.carrier_fuel_fill = tk.Frame(self.carrier_fuel_bar_bg, bg=self.UI_OK, height=7)
        self.carrier_fuel_fill.place(x=0, y=0, relheight=1.0, width=0)
        self.carrier_fuel_txt = tk.Label(fuel_row, text="", fg=self.UI_DIM,
                                         bg=self.UI_PANEL, font=("Segoe UI", 7))
        self.carrier_fuel_txt.pack(side=tk.LEFT, padx=(8, 0))

        # Optional workspaces remain available, but no longer compete with the
        # primary exploration briefing.
        addon_strip = self._panel(body)
        addon_strip.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            addon_strip, text="ADD-ON ACTIVITY", fg=self.UI_DIM, bg=self.UI_PANEL,
            font=("Segoe UI", 7, "bold"),
        ).pack(side=tk.LEFT, padx=(12, 8), pady=8)
        self.dashboard_operations_text = tk.Label(
            addon_strip, text="No active add-on work", fg=self.UI_MUTED,
            bg=self.UI_PANEL, font=("Consolas", 8), anchor="w",
        )
        self.dashboard_operations_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._action_button(
            addon_strip, "OPEN ADD-ONS", self.show_operations_page, muted=True,
        ).pack(side=tk.RIGHT, padx=10, pady=5)

        # Exploration log: a curated flight record by default, with the raw
        # Frontier journal kept deliberately secondary for diagnostics.
        stream_shell = self._panel(body, border=COLOR_ACCENT)
        stream_shell.pack(fill=tk.BOTH, expand=True)
        stream_head = tk.Frame(stream_shell, bg=self.UI_PANEL)
        stream_head.pack(fill=tk.X, padx=12, pady=(9, 7))
        stream_title = tk.Frame(stream_head, bg=self.UI_PANEL)
        stream_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.dashboard_stream_heading = self._section_label(stream_title, "EXPLORATION LOG")
        self.dashboard_stream_heading.pack(anchor="w")
        self.dashboard_stream_subtitle = tk.Label(
            stream_title,
            text="Curated discoveries, navigation and Compass activity",
            fg=self.UI_DIM, bg=self.UI_PANEL, font=("Segoe UI", 8), anchor="w",
        )
        self.dashboard_stream_subtitle.pack(anchor="w", pady=(2, 0))
        self.dashboard_stream_buttons = {}
        for name, label in (("live", "FLIGHT LOG"), ("raw", "JOURNAL")):
            btn = self._action_button(
                stream_head, label, lambda selected=name: self._show_dashboard_stream(selected),
                accent=(name == "live"), muted=(name != "live"),
            )
            btn.pack(side=tk.RIGHT, padx=(5, 0))
            self.dashboard_stream_buttons[name] = btn
        self.dashboard_stream_host = tk.Frame(stream_shell, bg=self.UI_PANEL)
        self.dashboard_stream_host.pack(fill=tk.BOTH, expand=True)

        self.details_drawer = tk.Frame(self.dashboard_stream_host, bg=self.UI_PANEL)
        self._build_live_event_timeline(self.details_drawer)

        self.dashboard_raw_stream = tk.Frame(self.dashboard_stream_host, bg=self.UI_PANEL)
        raw_header = tk.Frame(self.dashboard_raw_stream, bg=self.UI_PANEL)
        raw_header.pack(fill=tk.X, padx=12, pady=(9, 7))
        raw_copy = tk.Frame(raw_header, bg=self.UI_PANEL)
        raw_copy.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            raw_copy, text="RAW JOURNAL DIAGNOSTICS", fg=COLOR_ORANGE,
            bg=self.UI_PANEL, font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(anchor="w")
        tk.Label(
            raw_copy,
            text="Unfiltered Frontier events for troubleshooting and verification",
            fg=self.UI_DIM, bg=self.UI_PANEL, font=("Segoe UI", 8), anchor="w",
        ).pack(anchor="w", pady=(2, 0))
        self.journal_history_count_lbl = tk.Label(
            raw_header, text="0 EVENTS", fg="black", bg=COLOR_ORANGE,
            font=("Consolas", 8, "bold"), padx=7, pady=3,
        )
        self.journal_history_count_lbl.pack(side=tk.RIGHT)
        history_wrap = tk.Frame(self.dashboard_raw_stream, bg="#0b0f13")
        history_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.journal_history_canvas = tk.Canvas(
            history_wrap, bg="#0b0f13", highlightthickness=0, borderwidth=0,
        )
        self.journal_history_scroll = scrollbar(
            history_wrap, orient=tk.VERTICAL, command=self.journal_history_canvas.yview,
        )
        self.journal_history_canvas.configure(yscrollcommand=self.journal_history_scroll.set)
        self.journal_history_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.journal_history_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.journal_history_canvas.bind("<Configure>", lambda _event: self._render_journal_history_canvas())
        self.journal_history_canvas.bind("<MouseWheel>", self._on_journal_history_wheel)
        self.journal_history_entries = []
        self._journal_icon_cache = {}
        self._render_journal_history_empty()
        self._show_dashboard_stream("live")

        footer = tk.Frame(body, bg=self.UI_BG)
        footer.pack(fill=tk.X, pady=(5, 0))
        self._action_button(footer, "Rebuild Cache", self.scan_all_logs_threaded, muted=True).pack(side=tk.LEFT)
        self._action_button(footer, "Screenshots", self.open_screenshots_folder, muted=True).pack(side=tk.LEFT, padx=(6, 0))
        self._console_toggle_btn = tk.Button(
            footer, text="▶  DIAGNOSTICS", command=self._toggle_console,
            bg=self.UI_BG, fg=self.UI_DIM, font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, bd=0, cursor="hand2", padx=0,
        )
        self._console_toggle_btn.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(footer, text="2026 insert3coins", font=("Segoe UI", 8),
                 fg=self.UI_DIM, bg=self.UI_BG).pack(side=tk.RIGHT, pady=5)
        self._console_visible = False
        self._console_frame = self._panel(body)
        self.log_box = scrolledtext.ScrolledText(
            self._console_frame, bg="#050607", fg="#62d66f", font=("Consolas", 8),
            borderwidth=0, height=4, relief=tk.FLAT,
        )
        self.log_box.pack(fill=tk.X, padx=10, pady=10)

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
        self.route_progress_stat = self.create_stat(flight_stats, "ROUTE PROGRESS", "NO ACTIVE ROUTE")
        self.scan_stat = self.create_stat(flight_stats, "SCAN PROGRESS", "0 / 0")
        self.flight_strip_canvas = None

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
        self.wp_info_scroll = scrollbar(self.wp_info_wrap, orient=tk.VERTICAL)
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
        self.journal_history_scroll = scrollbar(history_wrap, orient=tk.VERTICAL, command=self.journal_history_canvas.yview)
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

    def _show_dashboard_stream(self, name):
        if not hasattr(self, "dashboard_stream_host"):
            return
        for frame in (getattr(self, "details_drawer", None), getattr(self, "dashboard_raw_stream", None)):
            if frame is not None:
                frame.pack_forget()
        target = self.dashboard_raw_stream if name == "raw" else self.details_drawer
        target.pack(fill=tk.BOTH, expand=True)
        self.dashboard_stream_mode = "raw" if name == "raw" else "live"
        for key, btn in getattr(self, "dashboard_stream_buttons", {}).items():
            selected = key == name
            bg = self.UI_PANEL_2 if selected else self.UI_PANEL
            fg = COLOR_ACCENT if selected else self.UI_MUTED
            btn.configure(bg=bg, fg=fg)
            btn._theme_resting_bg = bg
            btn._theme_resting_fg = fg
        if name == "raw":
            self._refresh_journal_history_view()
            self._journal_history_dirty = False
        else:
            self._refresh_event_feed()
            self._event_feed_dirty = False

    def _dashboard_next_destination(self):
        route = list(getattr(self, "route_list", None) or [])
        current = getattr(self, "current_sys", None)
        if route:
            try:
                index = route.index(current)
            except (ValueError, TypeError):
                index = -1
            if 0 <= index < len(route) - 1:
                return route[index + 1]
            if index < 0:
                return route[0]
        manager = getattr(self, "waypoint_manager", None)
        waypoints = list(getattr(manager, "waypoints", None) or [])
        if manager and current:
            next_name = manager.get_next_waypoint(current)
            if next_name:
                return next_name
        for waypoint in waypoints:
            if not waypoint.get("visited") and waypoint.get("name"):
                return waypoint["name"]
        return None

    def _dashboard_copy_next(self):
        rows = getattr(self, "_operational_queue", None) or []
        destination = rows[0].get("copy_text") if rows else None
        destination = destination or self._dashboard_next_destination()
        if destination:
            self._copy_waypoint_to_clipboard(destination, "NEXT DESTINATION")
            self.dashboard_objective_detail.config(text=f"Copied {destination} to the clipboard.")
        else:
            self.dashboard_objective_detail.config(text="No pending route or waypoint is available to copy.")

    @staticmethod
    def _dashboard_credits(value):
        value = int(value or 0)
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.1f}B cr"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M cr"
        if value >= 1_000:
            return f"{value / 1_000:.0f}K cr"
        return f"{value:,} cr"

    @staticmethod
    def _dashboard_number(value, default=0):
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return default

    def _dashboard_activity_context(self, mode, snapshot, queue_rows=None):
        """Build one verified, display-only context for an adaptive add-on mode."""
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        queue_rows = list(queue_rows or [])
        flight = snapshot.get("flight") or {}
        navigation = snapshot.get("navigation") or {}
        current_system = navigation.get("current_system") or getattr(self, "current_sys", None) or "UNKNOWN SYSTEM"
        cargo = self._dashboard_number(flight.get("cargo_t"))
        cargo_cap = self._dashboard_number(flight.get("cargo_capacity_t"))
        cargo_ratio = min(1.0, cargo / cargo_cap) if cargo_cap else 0.0
        next_system = navigation.get("next_system") or navigation.get("final_destination") or "NO DESTINATION"
        mode_labels = {
            "trade": "TRADE", "mining": "MINING", "combat": "COMBAT",
            "ground": "GROUND OPS", "engineering": "ENGINEERING",
            "carrier": "CARRIER OPS", "colony": "ARCHITECT",
            "station": "STATION OPS", "powerplay": "POWERPLAY",
        }
        label = mode_labels.get(mode, str(mode or "ACTIVITY").upper())
        context = {
            "deck": f"{label} COMMAND DECK",
            "heading": f"{label} ACTIVITY",
            "badge": "ACTIVE",
            "badge_colour": COLOR_ACCENT,
            "title": current_system,
            "detail": f"Verified {label.casefold()} context is active in {current_system}.",
            "value": "LIVE JOURNAL CONTEXT",
            "progress": cargo_ratio,
            "progress_colour": COLOR_ACCENT,
            "stats": [
                ("SHIP / STATE", f"{flight.get('ship') or 'SHIP'} · {flight.get('state') or 'FLIGHT'}"),
                ("NAVIGATION", next_system),
                ("CARGO", f"{cargo}/{cargo_cap} T" if cargo_cap else f"{cargo} T"),
                ("LEGAL", flight.get("legal_state") or "CLEAN"),
            ],
            "priority": f"Continue {label.casefold()} activity",
            "priority_detail": "Open the active workspace for its complete controls and verified detail.",
            "support_heading": f"{label} SUPPORT",
            "support_badge": "READY",
            "support_colour": self.UI_OK,
            "support_name": next_system,
            "support_detail": current_system,
            "support_meta": "Context follows live journal activity",
            "support_progress": cargo_ratio,
            "support_progress_text": f"{cargo}/{cargo_cap} T" if cargo_cap else "",
            "action": f"OPEN {label}",
        }

        if mode == "trade":
            trade = snapshot.get("trade") or {}
            plan = trade.get("plan") or {}
            last = trade.get("last_transaction") or {}
            commodity = (
                last.get("commodity") or plan.get("commodity")
                or next(iter((trade.get("commodities_bought") or {}).keys()), None)
                or next(iter((trade.get("commodities_sold") or {}).keys()), None)
                or "TRADE RUN"
            )
            destination = plan.get("to_station") or plan.get("to_system") or next_system
            origin = plan.get("from_station") or plan.get("from_system") or current_system
            profit = self._dashboard_number(trade.get("profit_cr"))
            expected = self._dashboard_number(plan.get("profit_cr"))
            context.update({
                "heading": "TRADE RUN", "badge": "PLANNED" if plan else "ACTIVE",
                "title": str(commodity),
                "detail": f"{origin}  →  {destination}" if plan else f"Market activity in {current_system}",
                "value": f"SESSION PROFIT {self._dashboard_credits(profit)}" + (
                    f"  ·  PLAN {self._dashboard_credits(expected)}" if expected else ""
                ),
                "stats": [
                    ("CARGO", f"{cargo}/{cargo_cap} T" if cargo_cap else f"{cargo} T"),
                    ("BOUGHT", f"{self._dashboard_number(trade.get('bought_units')):,} T"),
                    ("SOLD", f"{self._dashboard_number(trade.get('sold_units')):,} T"),
                    ("PROFIT", self._dashboard_credits(profit)),
                ],
                "priority": f"Deliver trade plan to {destination}" if plan else "Review the next profitable market",
                "priority_detail": (
                    f"The active plan runs from {origin} to {destination}."
                    if plan else "No planned market destination is currently recorded."
                ),
                "support_heading": "MARKET SUPPORT", "support_badge": "PLAN" if plan else "LIVE",
                "support_name": destination, "support_detail": f"FROM {origin}",
                "support_meta": f"EXPECTED {self._dashboard_credits(expected)}" if expected else "EDDN market services remain automatic",
                "action": "OPEN TRADE",
            })
        elif mode == "mining":
            mining = snapshot.get("mining") or {}
            body = mining.get("body") or mining.get("system") or current_system
            refined = self._dashboard_number(mining.get("refined_tons"))
            best = mining.get("best_material") or "No confirmed mineral yet"
            best_pct = float(mining.get("best_percent") or 0)
            context.update({
                "heading": "MINING RUN", "title": body,
                "detail": f"Best prospect: {best}" + (f" at {best_pct:.1f}%" if best_pct else ""),
                "value": f"{refined:,} T REFINED  ·  {float(mining.get('yield_tph') or 0):.1f} T/H",
                "stats": [
                    ("PROSPECTED", f"{self._dashboard_number(mining.get('prospected')):,}"),
                    ("CORES", f"{self._dashboard_number(mining.get('cores_found')):,} FOUND"),
                    ("REFINED", f"{refined:,} T"),
                    ("LIMPETS", str(mining.get("limpets") if mining.get("limpets") is not None else "UNKNOWN")),
                ],
                "priority": "Continue the active mining run" if mining.get("active") else "Prepare the next mining run",
                "priority_detail": f"Refinery has confirmed {refined:,} tonnes during this session.",
                "support_heading": "PROSPECTOR SUPPORT", "support_name": str(best),
                "support_detail": f"BEST CONTENT {best_pct:.1f}%" if best_pct else "Awaiting prospector result",
                "support_meta": f"{self._dashboard_number(mining.get('cores_cracked')):,} cores cracked",
                "action": "OPEN MINING",
            })
        elif mode == "combat":
            combat = snapshot.get("combat") or {}
            target = combat.get("current_target") or {}
            target_name = target.get("name") or target.get("ship") or "COMBAT SORTIE"
            hull = combat.get("hull_percent")
            hull_ratio = min(1.0, max(0.0, float(hull) / 100.0)) if hull is not None else 0.0
            reward = self._dashboard_number(combat.get("unclaimed_reward_cr"))
            context.update({
                "heading": "COMBAT SORTIE", "badge": "DANGER" if combat.get("in_danger") else "ACTIVE",
                "badge_colour": self.UI_FAIL if combat.get("in_danger") else COLOR_ACCENT,
                "title": target_name, "detail": f"Combat activity in {current_system}",
                "value": f"UNCLAIMED {self._dashboard_credits(reward)}",
                "progress": hull_ratio, "progress_colour": self.UI_OK if hull_ratio >= 0.5 else self.UI_WARN,
                "stats": [
                    ("HULL", f"{float(hull):.0f}%" if hull is not None else "UNKNOWN"),
                    ("SHIELDS", "UP" if combat.get("shields_up") else "DOWN"),
                    ("VICTORIES", f"{self._dashboard_number(combat.get('victories')):,}"),
                    ("CLAIMS", f"{self._dashboard_number(combat.get('bounties')) + self._dashboard_number(combat.get('combat_bonds')):,}"),
                ],
                "priority": "Stabilise the ship" if combat.get("in_danger") else "Continue the combat sortie",
                "priority_detail": f"{self._dashboard_number(combat.get('attacks')):,} hostile engagements observed this sortie.",
                "support_heading": "COMBAT READINESS", "support_badge": "DANGER" if combat.get("in_danger") else "READY",
                "support_colour": self.UI_FAIL if combat.get("in_danger") else self.UI_OK,
                "support_name": f"HULL {float(hull):.0f}%" if hull is not None else "Hull state unknown",
                "support_detail": "SHIELDS UP" if combat.get("shields_up") else "SHIELDS DOWN",
                "support_meta": f"{self._dashboard_credits(reward)} awaiting redemption",
                "support_progress": hull_ratio, "support_progress_text": f"{float(hull):.0f}%" if hull is not None else "",
                "action": "OPEN COMBAT",
            })
        elif mode == "ground":
            ground = snapshot.get("ground_operations") or {}
            biology = snapshot.get("biology") or {}
            sample_progress = self._dashboard_number(biology.get("progress") or biology.get("sample_idx"))
            sample_ratio = min(1.0, sample_progress / 3.0) if sample_progress else 0.0
            place = ground.get("settlement") or biology.get("body") or (snapshot.get("survey") or {}).get("focused_body") or current_system
            suit = ground.get("suit") or ground.get("loadout") or "GROUND LOADOUT"
            context.update({
                "heading": "GROUND OPERATIONS", "title": place,
                "detail": f"{suit}  ·  {ground.get('vehicle_control') or 'On foot'}",
                "value": f"BIO SAMPLE {sample_progress}/3" if sample_progress else f"BACKPACK {self._dashboard_number(ground.get('backpack_units'))} ITEMS",
                "progress": sample_ratio,
                "stats": [
                    ("HEALTH", f"{float(ground.get('health_percent')):.0f}%" if ground.get("health_percent") is not None else "UNKNOWN"),
                    ("OXYGEN", f"{float(ground.get('oxygen_percent')):.0f}%" if ground.get("oxygen_percent") is not None else "UNKNOWN"),
                    ("MEDKITS", str(self._dashboard_number(ground.get("medkits")))),
                    ("ENERGY", str(self._dashboard_number(ground.get("energy_cells")))),
                ],
                "priority": f"Continue {biology.get('species') or biology.get('genus')} sampling" if biology else "Continue surface operations",
                "priority_detail": f"Current surface context: {place}.",
                "support_heading": "SURFACE SUPPORT", "support_name": suit,
                "support_detail": f"GRAVITY {float(ground.get('gravity_g')):.2f} G" if ground.get("gravity_g") is not None else "Local gravity awaiting telemetry",
                "support_meta": f"{self._dashboard_number(ground.get('backpack_units'))} backpack items",
                "support_progress": sample_ratio, "support_progress_text": f"{sample_progress}/3" if sample_progress else "",
                "action": "OPEN GROUND",
            })
        elif mode == "engineering":
            pins = list((snapshot.get("objectives") or {}).get("pinned_engineering") or [])
            first = pins[0] if pins else {}
            name = first.get("name") if isinstance(first, dict) else str(first or "")
            grade = self._dashboard_number(first.get("target_grade", first.get("grade", 0))) if isinstance(first, dict) else 0
            context.update({
                "heading": "ENGINEERING GOALS", "badge": "PINNED" if pins else "READY",
                "title": name or "NO PINNED BLUEPRINT",
                "detail": f"{len(pins)} pinned blueprint{'s' if len(pins) != 1 else ''} tracked from local inventory.",
                "value": f"TARGET GRADE {grade}" if grade else "MATERIAL INVENTORY READY",
                "progress": min(1.0, len(pins) / 5.0) if pins else 0.0,
                "stats": [
                    ("PINNED", str(len(pins))),
                    ("TARGET", f"G{grade}" if grade else "NONE"),
                    ("CARGO", f"{cargo}/{cargo_cap} T" if cargo_cap else f"{cargo} T"),
                    ("SYSTEM", current_system),
                ],
                "priority": f"Advance {name}" if name else "Pin an engineering goal",
                "priority_detail": "Engineering Command holds grade-aware material shortages and trader alternatives.",
                "support_heading": "MATERIAL SUPPORT", "support_name": f"{len(pins)} PINNED GOALS",
                "support_detail": name or "No blueprint selected", "support_meta": f"TARGET G{grade}" if grade else "Open Engineering Command to plan",
                "support_progress": min(1.0, len(pins) / 5.0) if pins else 0.0,
                "support_progress_text": f"{len(pins)} GOALS", "action": "OPEN ENGINEER",
            })
        elif mode == "powerplay":
            pp = snapshot.get("powerplay") or {}
            system = pp.get("system") or {}
            outstanding = self._dashboard_number(pp.get("outstanding_units"))
            context.update({
                "heading": "POWERPLAY OPERATIONS", "title": pp.get("power") or "NO PLEDGE RECORDED",
                "detail": f"{current_system}  ·  {system.get('state') or 'regional state unknown'}",
                "value": f"{self._dashboard_number(pp.get('merits')):,} MERITS  ·  {outstanding:,} UNITS OUTSTANDING",
                "progress": min(1.0, self._dashboard_number(pp.get("session_delivered")) / max(1, self._dashboard_number(pp.get("session_collected")))) if pp.get("session_collected") else 0.0,
                "stats": [
                    ("RANK", str(pp.get("rank") or "—")),
                    ("MERITS", f"{self._dashboard_number(pp.get('merits')):,}"),
                    ("COLLECTED", f"{self._dashboard_number(pp.get('session_collected')):,}"),
                    ("DELIVERED", f"{self._dashboard_number(pp.get('session_delivered')):,}"),
                ],
                "priority": "Deliver Powerplay commodities" if outstanding else "Review regional Powerplay strategy",
                "priority_detail": f"{outstanding:,} collected units remain outstanding." if outstanding else f"Current controlling power: {system.get('controlling') or 'unknown'}.",
                "support_heading": "REGIONAL STATUS", "support_name": system.get("controlling") or current_system,
                "support_detail": "CONTESTED" if system.get("contested") else "STABLE",
                "support_meta": f"{len(system.get('powers') or [])} powers present", "action": "OPEN POWERPLAY",
            })
        elif mode in ("carrier", "colony"):
            strategy = snapshot.get("strategy") or {}
            carrier = strategy.get("carrier") or {}
            projects = list(strategy.get("colonisation_projects") or [])
            if mode == "carrier":
                fuel = self._dashboard_number(carrier.get("fuel_level"))
                capacity = self._dashboard_number(carrier.get("fuel_capacity"))
                fuel_ratio = min(1.0, fuel / capacity) if capacity else 0.0
                context.update({
                    "heading": "FLEET CARRIER OPERATIONS", "title": carrier.get("name") or "NO CARRIER SYNC",
                    "detail": f"{carrier.get('system') or current_system}  →  {carrier.get('jump_destination') or 'NO JUMP PLOTTED'}",
                    "value": f"TRITIUM {fuel:,}/{capacity:,} T" if capacity else "Carrier fuel awaiting sync",
                    "progress": fuel_ratio,
                    "stats": [
                        ("STATUS", str(carrier.get("status") or "IDLE").upper()),
                        ("FUEL", f"{fuel}/{capacity} T" if capacity else "UNKNOWN"),
                        ("ORDERS", str(self._dashboard_number(carrier.get("trade_orders")))),
                        ("DESTINATION", carrier.get("jump_destination") or "NONE"),
                    ],
                    "priority": f"Prepare jump to {carrier.get('jump_destination')}" if carrier.get("jump_destination") else "Review carrier expedition logistics",
                    "priority_detail": "Carrier Command holds route, fuel, service and inventory planning.",
                    "action": "OPEN CARRIER",
                })
            else:
                project = projects[0] if projects else {}
                remaining = sum(self._dashboard_number(row.get("remaining_units")) for row in projects if isinstance(row, dict))
                progress = float(project.get("progress") or 0) if isinstance(project, dict) else 0.0
                progress = progress / 100.0 if progress > 1 else progress
                context.update({
                    "heading": "ARCHITECT COMMAND", "badge": "BUILDING" if projects else "READY",
                    "title": project.get("system") or "NO ACTIVE CONSTRUCTION SITE",
                    "detail": f"{project.get('body') or current_system}  ·  {len(projects)} active site{'s' if len(projects) != 1 else ''}",
                    "value": f"{remaining:,} UNITS REMAINING", "progress": min(1.0, max(0.0, progress)),
                    "stats": [
                        ("SITES", str(len(projects))),
                        ("REMAINING", f"{remaining:,} T"),
                        ("MATCHED", str(len(strategy.get("colonisation_matching_cargo") or []))),
                        ("CARGO", f"{cargo}/{cargo_cap} T" if cargo_cap else f"{cargo} T"),
                    ],
                    "priority": f"Supply {project.get('system')}" if project else "Select a construction project",
                    "priority_detail": f"{remaining:,} journal-confirmed units remain across active sites.",
                    "support_heading": "CONSTRUCTION SUPPORT", "support_name": project.get("body") or "No active site",
                    "support_detail": f"{remaining:,} UNITS REQUIRED", "support_meta": f"{len(strategy.get('colonisation_matching_cargo') or [])} cargo matches aboard",
                    "support_progress": min(1.0, max(0.0, progress)), "support_progress_text": f"{progress * 100:.0f}%",
                    "action": "OPEN COLONY",
                })
        elif mode == "station":
            station = snapshot.get("station") or {}
            missions = snapshot.get("missions") or {}
            services = list(station.get("services") or [])
            context.update({
                "heading": "STATION OPERATIONS", "title": station.get("name") or "DOCKED",
                "detail": f"{current_system}  ·  {len(services)} services available",
                "value": f"{self._dashboard_number(missions.get('active'))} ACTIVE MISSIONS",
                "stats": [
                    ("SERVICES", str(len(services))),
                    ("MISSIONS", str(self._dashboard_number(missions.get("active")))),
                    ("CARGO", f"{cargo}/{cargo_cap} T" if cargo_cap else f"{cargo} T"),
                    ("BALANCE", self._dashboard_credits(getattr(self, "cmdr_balance", 0))),
                ],
                "priority": "Review station services and outstanding work",
                "priority_detail": ", ".join(str(item) for item in services[:5]) or "Station service list is awaiting journal state.",
                "support_heading": "STATION SUPPORT", "support_name": station.get("name") or current_system,
                "support_detail": f"{len(services)} SERVICES", "support_meta": f"{cargo} tonnes aboard",
                "action": "OPEN NEXT TASK",
            })

        if queue_rows:
            context["priority"] = queue_rows[0].get("label") or context["priority"]
            context["priority_detail"] = queue_rows[0].get("detail") or context["priority_detail"]
        return context

    def _apply_dashboard_activity_context(self, mode, context=None):
        """Apply an adaptive mode without rebuilding or replacing dashboard widgets."""
        exploration = mode in ("general", "exploration", None)
        if exploration:
            previous_mode = getattr(self, "_dashboard_render_mode", None)
            self.dashboard_deck_heading.config(text="EXPLORATION COMMAND DECK")
            self.dashboard_context_heading.config(text="ARRIVAL INTELLIGENCE")
            self.dashboard_destination_heading.config(text="NEXT DESTINATION")
            self.dashboard_objective_heading.config(text="EXPLORATION PRIORITY")
            for widget, text_value in zip(
                self.dashboard_stat_labels, ("SHIP / STATE", "NAVIGATION", "ROUTE", "SURVEY"),
            ):
                widget.config(text=text_value)
            self.dashboard_support_heading.config(text="EXPEDITION SUPPORT")
            self.dashboard_stream_heading.config(text="EXPLORATION LOG")
            self.dashboard_stream_subtitle.config(
                text="Curated discoveries, navigation and Compass activity"
            )
            self.dashboard_primary_action_btn.config(
                text="OPEN EXPLORE", command=self.open_exploration_window,
            )
            self.dashboard_copy_action_btn.config(text="COPY NEXT", command=self._dashboard_copy_next)
            self.dashboard_explore_action_btn.config(text="GALAXY", command=self.open_bgs_window)
            self._dashboard_render_mode = "exploration"
            if previous_mode not in (None, "exploration"):
                try:
                    self.update_carrier_panel(force=True)
                except Exception:
                    pass
            return
        if not context:
            return
        self.dashboard_deck_heading.config(text=context["deck"])
        self.dashboard_context_heading.config(text=context["heading"])
        self.dashboard_destination_heading.config(text="NAVIGATION / DESTINATION")
        self.dashboard_objective_heading.config(text=f"{str(mode).upper()} PRIORITY")
        activity_label = context["deck"].replace(" COMMAND DECK", "")
        self.dashboard_stream_heading.config(text=f"{activity_label} ACTIVITY LOG")
        self.dashboard_stream_subtitle.config(
            text="Curated mode events, navigation, Compass decisions and support services"
        )
        self.dashboard_survey_badge.config(
            text=context["badge"], bg=context.get("badge_colour") or COLOR_ACCENT,
        )
        self.dashboard_survey_name.config(text=str(context["title"]).upper())
        self.dashboard_survey_detail.config(text=context["detail"])
        self.dashboard_survey_value.config(text=context["value"])
        ratio = min(1.0, max(0.0, float(context.get("progress") or 0)))
        self.dashboard_survey_progress_fill.config(
            bg=context.get("progress_colour") or COLOR_ACCENT,
        )
        self.dashboard_survey_progress_fill.place_configure(relwidth=ratio)
        for index, (label, value) in enumerate(context["stats"][:4]):
            self.dashboard_stat_labels[index].config(text=label)
            self.dashboard_stat_values[index].config(text=str(value).upper())
        self.dashboard_flight_meta.config(
            text=f"Adaptive mode · verified from live journal state · {context['detail']}"
        )
        self.dashboard_objective_primary.config(text=context["priority"])
        self.dashboard_objective_detail.config(text=context["priority_detail"])
        self.dashboard_support_heading.config(text=context["support_heading"])
        self.carrier_panel_badge.config(
            text=context["support_badge"], bg=context.get("support_colour") or self.UI_OK,
        )
        self._config_label_if_changed(self.carrier_panel_name, text=context["support_name"], fg=COLOR_TEXT)
        self._config_label_if_changed(self.carrier_panel_loc, text=context["support_detail"], fg=self.UI_MUTED)
        self._config_label_if_changed(self.carrier_panel_jump, text=context["support_meta"], fg=COLOR_ACCENT)
        support_ratio = min(1.0, max(0.0, float(context.get("support_progress") or 0)))
        self.carrier_fuel_fill.place(x=0, y=0, relheight=1.0, relwidth=support_ratio)
        self.carrier_fuel_fill.config(bg=context.get("progress_colour") or COLOR_ACCENT)
        self._config_label_if_changed(
            self.carrier_fuel_txt, text=context.get("support_progress_text") or "", fg=self.UI_MUTED,
        )
        self.dashboard_primary_action_btn.config(
            text=context["action"], command=self._adaptive_open_mode_workspace,
        )
        self.dashboard_copy_action_btn.config(text="COPY NEXT", command=self._dashboard_copy_next)
        self.dashboard_explore_action_btn.config(text="EXPLORATION", command=self.open_exploration_window)
        self._dashboard_render_mode = mode

    def _refresh_adaptive_mode_open_button(self, deck_status, queue_rows=None):
        button_widget = getattr(self, "dashboard_mode_open_btn", None)
        if not self._widget_alive(button_widget):
            return
        mode = str((deck_status or {}).get("mode") or "general")
        mode_actions = {
            "exploration": "OPEN EXPLORE",
            "mining": "OPEN MINING",
            "trade": "OPEN TRADE",
            "combat": "OPEN COMBAT",
            "ground": "OPEN GROUND",
            "engineering": "OPEN ENGINEER",
            "carrier": "OPEN CARRIER",
            "colony": "OPEN COLONY",
            "powerplay": "OPEN POWERPLAY",
        }
        open_text = mode_actions.get(mode)
        open_state = tk.NORMAL
        if not open_text:
            rows = queue_rows if queue_rows is not None else (
                getattr(self, "_operational_queue", None) or []
            )
            actionable = any(row.get("workspace") != "DASHBOARD" for row in rows)
            open_text = "OPEN NEXT TASK" if actionable else "DASHBOARD ACTIVE"
            open_state = tk.NORMAL if actionable else tk.DISABLED
        button_widget.config(text=open_text, state=open_state)

    def _show_adaptive_mode_menu(self):
        """Show the themed manual/automatic Dashboard mode selector."""
        deck = getattr(self, "adaptive_command", None)
        button_widget = getattr(self, "dashboard_mode_lock_btn", None)
        if not deck or not self._widget_alive(button_widget):
            return
        selected = deck.locked_mode if not deck.automatic else "auto"
        self._adaptive_mode_menu_var = tk.StringVar(value=selected)
        menu = tk.Menu(
            self.root, tearoff=False, bg=self.UI_PANEL, fg=COLOR_TEXT,
            activebackground=COLOR_ACCENT, activeforeground="black",
            selectcolor=COLOR_ACCENT, relief=tk.FLAT, bd=1,
            font=("Segoe UI", 9),
        )
        options = (
            ("auto", "Automatic · follow journal activity"),
            ("exploration", "Exploration"),
            ("trade", "Trade"),
            ("mining", "Mining"),
            ("combat", "Combat / AX"),
            ("ground", "Ground Operations"),
            ("engineering", "Engineering"),
            ("powerplay", "Powerplay"),
            ("carrier", "Fleet Carrier"),
            ("colony", "Colony / Architect"),
            ("station", "Station Operations"),
        )
        for index, (mode, label) in enumerate(options):
            if index == 1:
                menu.add_separator()
            menu.add_radiobutton(
                label=label, value=mode, variable=self._adaptive_mode_menu_var,
                command=lambda value=mode: self._adaptive_select_mode(value),
            )
        try:
            menu.tk_popup(
                button_widget.winfo_rootx(),
                button_widget.winfo_rooty() + button_widget.winfo_height(),
            )
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass

    def _refresh_command_dashboard(self, route_progress=None):
        """Refresh briefing cards from already-cached live state only."""
        if not hasattr(self, "dashboard_objective_primary"):
            return
        route_progress = route_progress or self._current_route_progress()
        deck = getattr(self, "adaptive_command", None)
        if deck and hasattr(self, "dashboard_mode_badge"):
            deck_status = deck.status()
            health = self._adaptive_health_snapshot()
            self.dashboard_mode_badge.config(text=deck_status.get("label") or "GENERAL FLIGHT")
            session = deck_status.get("session") or {}
            event_count = int(session.get("events") or 0)
            control = "AUTO" if deck_status.get("automatic") else "LOCKED"
            self.dashboard_mode_detail.config(
                text=f"{control} · {event_count:,} mode event{'s' if event_count != 1 else ''} · {len(getattr(self, '_operational_queue', []) or [])} queued objectives"
            )
            level = health.get("level") or "NOMINAL"
            colour = self.UI_OK if level == "NOMINAL" else self.UI_WARN if level == "BUSY" else self.UI_FAIL
            self.dashboard_health_badge.config(
                text=f"{level} · UI {health.get('ui_pending', 0)} · IO {health.get('writes_pending', 0)}",
                bg=colour,
            )
            selected_label = str(deck_status.get("label") or "MODE")
            self.dashboard_mode_lock_btn.config(
                text="MODE · AUTO" if deck_status.get("automatic") else f"MODE · {selected_label}",
            )
            self._refresh_adaptive_mode_open_button(deck_status)
        state = getattr(self, "companion_state", {}) or {}
        fuel = getattr(self, "current_fuel_main", None)
        fuel_cap = getattr(self, "fuel_capacity_main", None)
        fuel_pct = None
        try:
            if fuel is not None and fuel_cap and float(fuel_cap) > 0:
                fuel_pct = round(float(fuel) * 100 / float(fuel_cap))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        cargo = int(getattr(self, "current_cargo_tons", 0) or 0)
        cargo_cap = int(getattr(self, "cargo_capacity", 0) or 0)
        unsold = int(state.get("unsold_exploration_cr") or 0) + int(state.get("unsold_bio_cr") or 0)
        potential_bonus = int(state.get("unsold_bio_bonus_potential_cr") or 0)
        flight_bits = []
        if fuel_pct is not None:
            flight_bits.append(f"fuel {fuel_pct}%")
        if cargo_cap:
            flight_bits.append(f"cargo {cargo}/{cargo_cap} T")
        if unsold:
            value = self._dashboard_credits(unsold)
            if potential_bonus:
                value = f"{value}–{self._dashboard_credits(unsold + potential_bonus)} est."
            flight_bits.append(f"data {value}")
        legal = getattr(self, "current_legal_state", None)
        if legal and str(legal).casefold() not in ("clean", "none"):
            flight_bits.append(str(legal))
        self.dashboard_flight_meta.config(text="  ·  ".join(flight_bits) or "Ship telemetry awaiting journal state")

        # Compass identity and latest verified decision.
        memory = getattr(self, "cockpit_memory", None)
        cognition = getattr(self, "compass_cognition", None)
        persona = str(self.config.get("cockpit_persona") or "Compass")
        mood = {"name": "calm", "reason": "systems nominal"}
        summary = {}
        if memory:
            try:
                mood = memory.current_mood()
                summary = memory.summary()
            except Exception:
                pass
        mood_name = str(mood.get("name") or "calm")
        mood_colour = self.UI_WARN if mood_name in ("alert", "shaken") else self.UI_OK
        self.dashboard_compass_badge.config(text=mood_name.upper(), bg=mood_colour)
        relationship = summary.get("relationship") or "Local flight companion"
        self.dashboard_compass_identity.config(text=f"{persona} · {relationship}")
        cognition_state = cognition.status() if cognition else {}
        decision = cognition_state.get("last_decision") or {}
        advice = decision.get("line")
        if advice:
            advice_text = advice
        elif decision.get("action") == "silence":
            advice_text = "Standing by. No observation currently clears the usefulness threshold."
        elif cognition_state.get("goals"):
            goal = cognition_state["goals"][0]
            advice_text = str(goal.get("detail") or goal.get("label") or goal.get("topic") or "Monitoring active objectives.")
        else:
            advice_text = "Monitoring verified flight context and active objectives."
        self.dashboard_compass_advice.config(text=advice_text)
        self.dashboard_compass_meta.config(text=(
            f"{summary.get('systems', 0):,} systems · {summary.get('memories', 0):,} memories · "
            f"{int(cognition_state.get('decisions') or 0):,} decisions"
        ))

        # Choose one truthful exploration priority instead of allowing optional
        # workspaces to displace the app's primary purpose.
        primary = "No urgent objective"
        detail = "Flight state is stable. Continue surveying or follow the current route."
        intelligence = self._exploration_intelligence_snapshot()
        exploration_actions = list(intelligence.get("actions") or [])
        if exploration_actions:
            primary = str(exploration_actions[0].get("title") or primary)
            detail = str(exploration_actions[0].get("detail") or detail)
        sample = getattr(self, "bio_sampling", None)
        remaining_bodies = max(0, int(getattr(self, "total", 0) or 0) - int(getattr(self, "scanned", 0) or 0))
        missions = state.get("missions") or {}
        mission_rows = list(missions.values()) if isinstance(missions, dict) else list(missions)
        next_destination = self._dashboard_next_destination()
        if isinstance(sample, dict):
            species = sample.get("species") or sample.get("genus") or "biological sample"
            progress = int(sample.get("sample_idx") or sample.get("progress") or 1)
            primary = f"Continue {species} sampling"
            detail = f"Active biological analysis is at sample {progress}/3 on {sample.get('body') or 'the current body'}."
        elif unsold >= 20_000_000:
            primary = "Secure valuable survey data"
            detail = f"Approximately {self._dashboard_credits(unsold)} remains unsold and is currently at risk."
        elif remaining_bodies and not exploration_actions:
            primary = "Complete the current system survey"
            detail = f"{remaining_bodies} bod{'ies remain' if remaining_bodies != 1 else 'y remains'} unresolved in {getattr(self, 'current_sys', 'this system')}."
        elif route_progress.get("remaining") and next_destination:
            primary = f"Continue to {next_destination}"
            detail = route_progress.get("text") or "A navigation route remains active."
        self.dashboard_objective_primary.config(text=primary)
        self.dashboard_objective_detail.config(text=detail)

        # Current-system survey intelligence stays visible even when the
        # transient survey overlay is hidden or the activity stream moves on.
        if hasattr(self, "dashboard_survey_name"):
            completion = intelligence.get("completion") or {}
            arrival = intelligence.get("arrival") or {}
            system_name = str(getattr(self, "current_sys", None) or "NO SYSTEM DATA")
            scanned = max(0, int(getattr(self, "scanned", 0) or 0))
            total = max(0, int(getattr(self, "total", 0) or 0))
            bio_signals = max(0, int(getattr(self, "system_bio_signals", 0) or 0))
            geo_signals = 0
            for signals in (getattr(self, "body_signals", {}) or {}).values():
                if isinstance(signals, dict):
                    geo_signals += max(0, int(signals.get("geo") or 0))
            notable = len(getattr(self, "valuable_bodies", None) or ())
            if completion.get("complete"):
                survey_state, survey_colour = "COMPLETE", self.UI_OK
            elif completion.get("state") == "PARTIAL":
                survey_state, survey_colour = "PARTIAL", COLOR_ACCENT
            elif scanned or total:
                survey_state, survey_colour = "SCANNING", COLOR_ACCENT
            else:
                survey_state, survey_colour = "AWAITING", self.UI_DIM
            if getattr(self, "system_undiscovered", False):
                survey_state, survey_colour = "FIRST DISCOVERY", self.UI_WARN
            self.dashboard_survey_badge.config(text=survey_state, bg=survey_colour)
            survey_ratio = min(1.0, max(0.0, float(completion.get("percent") or 0) / 100.0))
            self.dashboard_survey_progress_fill.config(
                bg=self.UI_OK if completion.get("complete") else COLOR_ACCENT,
            )
            self.dashboard_survey_progress_fill.place_configure(relwidth=survey_ratio)
            self.dashboard_survey_name.config(text=system_name.upper())
            signal_bits = [completion.get("summary") or (f"FSS {scanned}/{total}" if total else f"FSS {scanned}")]
            if bio_signals and not completion:
                signal_bits.append(f"BIO {bio_signals}")
            if geo_signals and not completion:
                signal_bits.append(f"GEO {geo_signals}")
            if notable and not completion:
                signal_bits.append(f"NOTABLE {notable}")
            survey_summary = None
            try:
                survey_summary = self._get_fss_summary()
            except Exception:
                pass
            high_value = list((survey_summary or {}).get("high_value") or [])
            detail_lines = ["  ·  ".join(signal_bits)]
            if arrival.get("region"):
                detail_lines.append(
                    f"ARRIVAL · {arrival.get('star') or 'Unknown star'} · {arrival['region'].get('name')}"
                )
            if high_value:
                detail_lines.append("Notable: " + " · ".join(high_value[:2]))
            reasons = list(completion.get("reasons") or [])
            if reasons:
                detail_lines.append("Remaining: " + " · ".join(reasons[:2]))
            self.dashboard_survey_detail.config(text="\n".join(detail_lines))
            value_bits = []
            if survey_summary and survey_summary.get("total"):
                value_bits.append(f"SCANNED VALUE {survey_summary['total']}")
            traffic = getattr(self, "system_traffic", {}) or {}
            value_bits.append(
                f"TRAFFIC {int(traffic.get('day') or 0)}/{int(traffic.get('week') or 0)}/{int(traffic.get('total') or 0)}"
            )
            self.dashboard_survey_value.config(text="  ·  ".join(value_bits))

        # Active operation roll-up; omit inactive/noise rows.
        operations = []
        active_colonies = [
            project for project in (getattr(self, "colonisation_projects", {}) or {}).values()
            if not project.get("complete") and not project.get("failed")
        ]
        colony_remaining = sum(
            max(0, int(resource.get("required") or 0) - int(resource.get("provided") or 0))
            for project in active_colonies for resource in (project.get("resources") or [])
        )
        if active_colonies:
            operations.append(f"ARCHITECT  {len(active_colonies)} site{'s' if len(active_colonies) != 1 else ''} · {colony_remaining:,} T remaining")
        if mission_rows:
            operations.append(f"MISSIONS   {len(mission_rows)} active")
        trade = getattr(self, "trade_session", {}) or {}
        trade_profit = int(trade.get("profit") or 0)
        if cargo or trade_profit:
            operations.append(f"TRADE      {cargo:,} T aboard · {self._dashboard_credits(trade_profit)} session")
        specialist_engine = getattr(self, "specialist_engine", None)
        if specialist_engine and specialist_engine.mining_active():
            operations.append("MINING     session active")
        self.dashboard_operations_text.config(
            text="  ·  ".join(operations[:3]) or "No active add-on work · optional workspaces remain ready"
        )

        # The operational queue still drives adaptive mode actions, but only
        # non-exploration rows are summarised in the add-on strip. It no longer
        # replaces the exploration priority above.
        command_snapshot = {}
        if deck:
            try:
                command_snapshot = self._compass_gameplay_snapshot()
                self._operational_queue = deck.build_queue(
                    command_snapshot, self._adaptive_context(route_progress),
                )
            except Exception:
                self._operational_queue = []
            rows = self._operational_queue
            exploration_ids = {"biology", "survey-data", "survey", "route", "carrier"}
            addon_rows = [row for row in rows if row.get("id") not in exploration_ids]
            if addon_rows:
                queue_text = "  ·  ".join(row["label"] for row in addon_rows[:3])
                self.dashboard_operations_text.config(text=queue_text)
            # Refresh the mode strip once more now that the current queue is known.
            if hasattr(self, "dashboard_mode_detail"):
                deck_status = deck.status()
                control = "AUTO" if deck_status.get("automatic") else "LOCKED"
                session_events = int((deck_status.get("session") or {}).get("events") or 0)
                self.dashboard_mode_detail.config(
                    text=f"{control} · {session_events:,} context event{'s' if session_events != 1 else ''} · {len(addon_rows)} active add-on{'s' if len(addon_rows) != 1 else ''}"
                )
                self._refresh_adaptive_mode_open_button(deck_status, rows)

            render_mode = str(deck_status.get("mode") or "general")
            sensed_mode = str((command_snapshot.get("activity") or {}).get("mode") or "general")
            adaptive_enabled = self.config.get("adaptive_command_enabled", True)
            if not adaptive_enabled or (deck.automatic and sensed_mode == "general"):
                render_mode = "general"
                if str(deck_status.get("mode") or "general") not in ("general", "exploration"):
                    self.dashboard_mode_badge.config(text="EXPLORATION", bg=COLOR_ACCENT)
                    self.dashboard_mode_detail.config(
                        text=(
                            "ADAPTIVE OFF · exploration context active"
                            if not adaptive_enabled
                            else "AUTO · add-on activity idle · exploration context restored"
                        )
                    )
            queue_ids_by_mode = {
                "trade": {"trade-plan"}, "mining": {"mining"},
                "ground": {"biology"}, "engineering": {"engineering"},
                "carrier": {"carrier"}, "colony": {"colony"},
                "powerplay": {"powerplay", "powerplay-delivery"},
            }
            expected_ids = queue_ids_by_mode.get(render_mode, set())
            mode_rows = (
                [row for row in rows if row.get("id") in expected_ids]
                if expected_ids else []
            )
            activity_context = (
                self._dashboard_activity_context(render_mode, command_snapshot, mode_rows)
                if render_mode not in ("general", "exploration") else None
            )
            self._apply_dashboard_activity_context(render_mode, activity_context)
        else:
            self._apply_dashboard_activity_context("exploration")

    def _run_nav_command(self, label, command):
        """Run a page action and add its full open/switch cost to runtime tracing."""
        started = time.perf_counter()
        try:
            return command()
        finally:
            recorder = getattr(self, "_trace_record_ms", None)
            if callable(recorder):
                try:
                    recorder(f"page_open:{str(label).lower()}", (time.perf_counter() - started) * 1000.0)
                except Exception:
                    pass

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
        self.workspace_canvas.yview_moveto(0.0)
        self._schedule_workspace_scrollregion()
        self._schedule_overlay_z_order_restore()

    def _toggle_navigation_group(self, group_name):
        collapsed = {
            str(name).upper()
            for name in (self.config.get("nav_collapsed_groups") or [])
        }
        name = str(group_name or "").upper()
        if name in collapsed:
            collapsed.remove(name)
        else:
            collapsed.add(name)
        self.config["nav_collapsed_groups"] = sorted(collapsed)
        self._apply_navigation_group_state()
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()

    def _apply_navigation_group_state(self):
        """Restore expanded/collapsed sidebar groups for the active profile."""
        bodies = getattr(self, "nav_group_bodies", {})
        buttons = getattr(self, "nav_group_buttons", {})
        if not bodies:
            return
        collapsed = {
            str(name).upper()
            for name in (self.config.get("nav_collapsed_groups") or [])
        }
        for name, body in bodies.items():
            is_collapsed = str(name).upper() in collapsed
            try:
                if is_collapsed:
                    body.pack_forget()
                elif not body.winfo_manager():
                    body.pack(fill=tk.X)
                buttons[name].configure(
                    text=f"{'▸' if is_collapsed else '▾'}  {name}"
                )
            except tk.TclError:
                continue

    def _workspace_hub_card(self, parent, row, column, title, description, action, button_text):
        card = self._panel(parent)
        card.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)
        tk.Label(
            card, text=title, fg=COLOR_ORANGE, bg=self.UI_PANEL,
            font=("Bahnschrift SemiCondensed", 13, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(13, 4))
        tk.Label(
            card, text=description, fg=COLOR_TEXT, bg=self.UI_PANEL,
            font=("Segoe UI", 9), justify=tk.LEFT, anchor="nw", wraplength=420,
        ).pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        self._action_button(card, button_text, action, accent=True).pack(
            anchor="w", padx=14, pady=(0, 13)
        )

    def _build_workspace_hubs(self):
        """Build small launch pages while leaving full tools first-open lazy."""
        self.expedition_page = tk.Frame(self.dashboard_host, bg=self.UI_BG)
        self.operations_page = tk.Frame(self.dashboard_host, bg=self.UI_BG)

        def hero(page, title, subtitle):
            panel = self._panel(page, border=COLOR_ACCENT)
            panel.pack(fill=tk.X, padx=14, pady=(12, 6))
            tk.Label(
                panel, text=title, fg=COLOR_ACCENT, bg=self.UI_PANEL,
                font=("Bahnschrift SemiCondensed", 20, "bold"), anchor="w",
            ).pack(fill=tk.X, padx=16, pady=(13, 2))
            tk.Label(
                panel, text=subtitle, fg=self.UI_MUTED, bg=self.UI_PANEL,
                font=self.UI_MONO, anchor="w",
            ).pack(fill=tk.X, padx=16, pady=(0, 13))

        hero(
            self.expedition_page,
            "EXPEDITION COMMAND",
            "Long-range planning and commander progress · every tool remains directly available",
        )
        expedition_grid = tk.Frame(self.expedition_page, bg=self.UI_BG)
        expedition_grid.pack(fill=tk.BOTH, expand=True, padx=9, pady=(0, 10))
        for column in range(2):
            expedition_grid.grid_columnconfigure(column, weight=1, uniform="expedition")
        for row in range(2):
            expedition_grid.grid_rowconfigure(row, weight=1)
        self._workspace_hub_card(
            expedition_grid, 0, 0, "FLEET CARRIER",
            "Personal and Squadron Carrier jumps, fuel, finance, services and expedition route.",
            self.open_carrier_window, "OPEN CARRIER",
        )
        self._workspace_hub_card(
            expedition_grid, 0, 1, "COLONY LOGISTICS",
            "Architect projects, construction requirements, contributions and cargo planning.",
            self.open_colonization_window, "OPEN COLONY",
        )
        self._workspace_hub_card(
            expedition_grid, 1, 0, "ANALYTICS",
            "Session pace, exploration history, balances and local performance trends.",
            self.open_analytics_window, "OPEN ANALYTICS",
        )
        self._workspace_hub_card(
            expedition_grid, 1, 1, "ACHIEVEMENTS",
            "Journal-driven progress across exploration, travel and the wider commander career.",
            self.open_achievement_window, "OPEN ACHIEVEMENTS",
        )

        hero(
            self.operations_page,
            "OPERATIONS",
            "Optional roles kept together without hiding their direct navigation shortcuts",
        )
        operations_grid = tk.Frame(self.operations_page, bg=self.UI_BG)
        operations_grid.pack(fill=tk.BOTH, expand=True, padx=9, pady=(0, 10))
        for column in range(2):
            operations_grid.grid_columnconfigure(column, weight=1, uniform="operations")
        for row in range(2):
            operations_grid.grid_rowconfigure(row, weight=1)
        self._workspace_hub_card(
            operations_grid, 0, 0, "SIMPLE TRADE",
            "Cargo selling, routes and EDDN status first; detailed market tools remain one click away.",
            self.open_trade_window, "OPEN TRADE",
        )
        self._workspace_hub_card(
            operations_grid, 0, 1, "MINING",
            "Mining runs, prospecting quality, refinery yield, cargo economics and history.",
            self.open_mining_window, "OPEN MINING",
        )
        self._workspace_hub_card(
            operations_grid, 1, 0, "COMBAT / AX",
            "Observed readiness, ammunition, claims, damage, synthesis and sortie history.",
            lambda: self.open_specialists_window(section="combat"), "OPEN COMBAT / AX",
        )
        self._workspace_hub_card(
            operations_grid, 1, 1, "SPECIALIST CONSOLE",
            "Mining, Combat/AX, Carrier logistics and Exobiology role workflows in one place.",
            self.open_specialists_window, "OPEN SPECIALISTS",
        )

    def show_expedition_page(self):
        self._show_embedded_page("EXPEDITION", self.expedition_page)

    def show_operations_page(self):
        self._show_embedded_page("OPERATIONS", self.operations_page)

    def _schedule_workspace_scrollregion(self, _event=None):
        if getattr(self, "_workspace_scroll_job", None) is not None:
            return
        try:
            self._workspace_scroll_job = self.root.after_idle(
                self._refresh_workspace_scrollregion
            )
        except Exception:
            self._workspace_scroll_job = None

    def _refresh_workspace_scrollregion(self):
        self._workspace_scroll_job = None
        canvas = getattr(self, "workspace_canvas", None)
        host = getattr(self, "dashboard_host", None)
        item = getattr(self, "_workspace_window_id", None)
        if canvas is None or host is None or item is None:
            return
        try:
            active_children = [
                child for child in host.winfo_children()
                if child.winfo_manager()
            ]
            requested_h = max(
                host.winfo_reqheight(),
                max((child.winfo_reqheight() for child in active_children), default=1),
            )
            # Keep the page responsive horizontally, as it was before the
            # outer viewport existed; only vertical overflow is scrollable.
            width = max(1, canvas.winfo_width())
            height = max(1, canvas.winfo_height(), requested_h)
            canvas.itemconfigure(item, width=width, height=height)
            canvas.configure(scrollregion=(0, 0, width, height))
        except tk.TclError:
            return

    @staticmethod
    def _scroll_view_can_move(widget, delta, horizontal=False):
        try:
            view = widget.xview() if horizontal else widget.yview()
            first, last = float(view[0]), float(view[1])
        except (AttributeError, TypeError, ValueError, tk.TclError):
            return False
        if last - first >= 0.999:
            return False
        return first > 0.0001 if delta > 0 else last < 0.9999

    def _nested_scrollable_can_move(self, widget, delta, horizontal=False):
        """Let the control under the pointer consume its own wheel first."""
        current = widget
        host = getattr(self, "dashboard_host", None)
        outer = getattr(self, "workspace_canvas", None)
        while current is not None and current is not host:
            if current is not outer and self._scroll_view_can_move(
                current, delta, horizontal=horizontal,
            ):
                return True
            try:
                parent_name = current.winfo_parent()
                current = current.nametowidget(parent_name) if parent_name else None
            except (AttributeError, KeyError, tk.TclError):
                break
        return False

    def _scroll_workspace(self, event, horizontal=False):
        canvas = getattr(self, "workspace_canvas", None)
        delta = int(getattr(event, "delta", 0) or 0)
        if canvas is None or not delta:
            return None
        widget = getattr(event, "widget", None)
        if widget is not None and self._nested_scrollable_can_move(
            widget, delta, horizontal=horizontal,
        ):
            return None
        if not self._scroll_view_can_move(canvas, delta, horizontal=horizontal):
            return None
        steps = max(1, abs(delta) // 120)
        direction = -steps if delta > 0 else steps
        if horizontal:
            canvas.xview_scroll(direction, "units")
        else:
            canvas.yview_scroll(direction, "units")
        return "break"

    def _on_workspace_mousewheel(self, event):
        return self._scroll_workspace(event, horizontal=False)

    def _schedule_overlay_z_order_restore(self):
        """Keep visible native overlays above the dashboard after page changes."""
        try:
            # The idle pass covers normal Tk stacking; the short delayed pass
            # covers Windows applying the clicked page's z-order afterward.
            self.root.after_idle(self._restore_overlay_z_order)
            self.root.after(120, self._restore_overlay_z_order)
        except Exception:
            pass

    def _restore_overlay_z_order(self):
        overlay_attrs = (
            "hud",
            "cargo_hud",
            "carrier_hud",
            "colony_overlay",
            "heartbeat_hud",
            "prospector_hud",
            "system_info_hud",
            "gravity_warning_hud",
            "station_info_hud",
            "survey_status_hud",
            "toast_hud",
            "ground_popup",
        )
        for attr in overlay_attrs:
            overlay = getattr(self, attr, None)
            window = getattr(overlay, "win", overlay)
            if window is None:
                continue
            try:
                if not window.winfo_exists():
                    continue
                # Do not reveal context-sensitive overlays that deliberately
                # hide themselves until their next relevant game event.
                if str(window.state()).lower() in ("withdrawn", "iconic"):
                    continue
                window.attributes("-topmost", True)
                window.lift()
            except Exception:
                continue

    def _build_about_page(self):
        """Build the project, support, privacy and update workspace."""
        body = tk.Frame(self.dashboard_host, bg=self.UI_BG)
        self.about_page = body

        hero = self._panel(body, border=COLOR_ACCENT)
        hero.pack(fill=tk.X, padx=14, pady=(12, 8))
        hero_text = tk.Frame(hero, bg=self.UI_PANEL)
        hero_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=14)
        tk.Label(
            hero_text, text="VOID COMPASS", fg=COLOR_ACCENT, bg=self.UI_PANEL,
            font=("Bahnschrift SemiCondensed", 22, "bold"), anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            hero_text,
            text="A native Windows command companion for Elite Dangerous",
            fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Segoe UI", 10), anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            hero, text=f"v{APP_VERSION}\nGPL-3.0", fg="black", bg=COLOR_ACCENT,
            font=("Cascadia Mono", 9, "bold"), justify=tk.CENTER, padx=15, pady=10,
        ).pack(side=tk.RIGHT, padx=14, pady=14)

        update_panel = self._panel(body)
        update_panel.pack(fill=tk.X, padx=14, pady=(0, 8))
        update_copy = tk.Frame(update_panel, bg=self.UI_PANEL)
        update_copy.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=14, pady=11)
        self._section_label(update_copy, "RELEASE STATUS").pack(anchor="w")
        self.about_update_status = tk.Label(
            update_copy, text=f"Installed version: v{APP_VERSION}",
            fg=self.UI_MUTED, bg=self.UI_PANEL, font=self.UI_MONO,
            anchor="w", justify=tk.LEFT,
        )
        self.about_update_status.pack(fill=tk.X, pady=(4, 0))
        update_actions = tk.Frame(update_panel, bg=self.UI_PANEL)
        update_actions.pack(side=tk.RIGHT, padx=14, pady=11)
        self.about_update_btn = self._action_button(
            update_actions, "CHECK FOR UPDATES", self._start_manual_update_check,
            accent=True,
        )
        self.about_update_btn.pack(side=tk.LEFT)
        self._action_button(
            update_actions, "OPEN RELEASES",
            lambda: webbrowser.open_new_tab(RELEASES_URL), muted=True,
        ).pack(side=tk.LEFT, padx=(6, 0))

        cards = tk.Frame(body, bg=self.UI_BG)
        cards.pack(fill=tk.BOTH, expand=True, padx=14)
        cards.grid_columnconfigure(0, weight=1, uniform="about")
        cards.grid_columnconfigure(1, weight=1, uniform="about")

        privacy = self._panel(cards)
        privacy.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 8))
        self._section_label(privacy, "PRIVACY SUMMARY").pack(anchor="w", padx=14, pady=(12, 5))
        tk.Label(
            privacy,
            text=(
                "Void Compass reads Elite's journal and companion files and stores commander "
                "profiles locally. It needs no Void Compass account or cloud database. At startup "
                "it asks GitHub Releases for the latest version. EDSM, EDDN, Spansh and Discord "
                "features only connect when enabled or requested. Support bundles are privacy-redacted."
            ),
            fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Segoe UI", 9),
            justify=tk.LEFT, anchor="nw", wraplength=480,
        ).pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 13))

        licence = self._panel(cards)
        licence.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 8))
        self._section_label(licence, "GPL-3.0 ONLY").pack(anchor="w", padx=14, pady=(12, 5))
        tk.Label(
            licence,
            text=(
                "Void Compass is free software. You may use, study, modify and redistribute it "
                "under GNU GPL v3.0. Distributions must keep the licence and provide corresponding "
                "source as required by its terms."
            ),
            fg=COLOR_TEXT, bg=self.UI_PANEL, font=("Segoe UI", 9),
            justify=tk.LEFT, anchor="nw", wraplength=480,
        ).pack(fill=tk.X, padx=14)
        self._action_button(
            licence, "READ FULL LICENCE", lambda: webbrowser.open_new_tab(LICENSE_URL), muted=True,
        ).pack(anchor="w", padx=14, pady=(10, 13))

        disclaimer = self._panel(cards)
        disclaimer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._section_label(disclaimer, "FRONTIER DISCLAIMER").pack(anchor="w", padx=14, pady=(12, 5))
        tk.Label(
            disclaimer,
            text=(
                "Void Compass is an independent community project and is not affiliated with or "
                "endorsed by Frontier Developments. Elite Dangerous and its related marks belong "
                "to their respective owners."
            ),
            fg=self.UI_MUTED, bg=self.UI_PANEL, font=("Segoe UI", 9),
            justify=tk.LEFT, anchor="w", wraplength=980,
        ).pack(fill=tk.X, padx=14, pady=(0, 13))

        links = self._panel(cards)
        links.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._section_label(links, "PROJECT & COMMUNITY").pack(anchor="w", padx=14, pady=(12, 7))
        link_row = tk.Frame(links, bg=self.UI_PANEL)
        link_row.pack(fill=tk.X, padx=14, pady=(0, 8))
        for label, url in (
            ("GITHUB", PROJECT_URL),
            ("RELEASES", RELEASES_URL),
            ("REPORT AN ISSUE", ISSUES_URL),
            ("WIKI", WIKI_URL),
            ("FRONTIER COMMUNITY", FRONTIER_COMMUNITY_URL),
        ):
            self._action_button(
                link_row, label, lambda target=url: webbrowser.open_new_tab(target), muted=True,
            ).pack(side=tk.LEFT, padx=(0, 6), pady=(0, 4))

        support = tk.Frame(links, bg=self.UI_PANEL)
        support.pack(fill=tk.X, padx=14, pady=(0, 12))
        tk.Label(
            support,
            text="Support: GitHub Issues only.\nAttach a redacted bundle when reporting a fault.",
            fg=self.UI_DIM, bg=self.UI_PANEL, font=self.UI_MONO,
            anchor="w", justify=tk.LEFT,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._action_button(
            support, "OPEN LOGS", self._open_about_logs, muted=True,
        ).pack(side=tk.RIGHT)
        self._action_button(
            support, "CREATE SUPPORT BUNDLE", self._create_support_bundle, accent=True,
        ).pack(side=tk.RIGHT, padx=(0, 6))

    def _open_about_logs(self):
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
        path = os.path.join(base, "logs")
        os.makedirs(path, exist_ok=True)
        try:
            os.startfile(path)
        except (AttributeError, OSError):
            webbrowser.open(path)

    def show_about_page(self):
        self._show_embedded_page("ABOUT", self.about_page)

    def show_dashboard_page(self):
        self._show_embedded_page("DASHBOARD", self.dashboard_page)
        if hasattr(self, "summary_session"):
            self.summary_session.config(text=self._get_session_elapsed_text())
        # Hidden pages already mark these views dirty as new events arrive.
        # Avoid rebuilding both timelines on every unchanged dashboard return.
        self._flush_dashboard_stream_views()
        self._refresh_command_dashboard()

    def _build_live_event_timeline(self, parent):
        feed_wrap = tk.Frame(parent, bg=self.UI_PANEL)
        feed_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(7, 12))

        feed_status = tk.Frame(feed_wrap, bg=self.UI_PANEL)
        feed_status.pack(fill=tk.X, pady=(0, 5))
        self.event_feed_live_badge = tk.Label(
            feed_status, text="● LIVE", fg="black", bg=self.UI_OK,
            font=("Segoe UI", 7, "bold"), padx=7, pady=2,
        )
        self.event_feed_live_badge.pack(side=tk.LEFT)
        self.event_feed_count_lbl = tk.Label(
            feed_status, text="0 CURATED EVENTS", fg=COLOR_TEXT,
            bg=self.UI_PANEL, font=("Consolas", 8, "bold"),
        )
        self.event_feed_count_lbl.pack(side=tk.LEFT, padx=(8, 0))
        self.event_feed_filter_lbl = tk.Label(
            feed_status, text="ALL ACTIVITY", fg=self.UI_DIM,
            bg=self.UI_PANEL, font=("Segoe UI", 7, "bold"),
        )
        self.event_feed_filter_lbl.pack(side=tk.RIGHT)

        self.event_filter_row = tk.Frame(feed_wrap, bg=self.UI_PANEL)
        self.event_filter_row.pack(fill=tk.X, pady=(6, 4))
        for col in range(6):
            self.event_filter_row.grid_columnconfigure(col, weight=1, uniform="event_filter")
        self.event_filter_buttons = {}
        event_filters = (
            ("ALL", "ALL"),
            ("DISCOVERY", "DISCOVERIES"),
            ("NAVIGATION", "NAVIGATION"),
            ("COMPASS", "COMPASS"),
            ("ALERTS", "ALERTS"),
            ("OPERATIONS", "OPERATIONS"),
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
            btn.grid(row=0, column=idx, sticky="ew", padx=2, pady=2)
            self.event_filter_buttons[tag] = btn
        event_text_wrap = tk.Frame(feed_wrap, bg="#0b0f13")
        event_text_wrap.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.event_feed_scroll = scrollbar(event_text_wrap, orient=tk.VERTICAL)
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
            padx=10,
            pady=8,
            spacing1=2,
            spacing3=2,
            yscrollcommand=self.event_feed_scroll.set,
        )
        self.event_feed_scroll.config(command=self.event_feed_list.yview)
        self.event_feed_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.event_feed_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.event_feed_list.config(state=tk.DISABLED)
        self.event_feed_list.bind("<Button-1>", self._select_event_feed_line)
        self.event_feed_list.bind("<Double-Button-1>", lambda e: self._open_selected_event_feed_link())

        selection_bar = tk.Frame(feed_wrap, bg=self.UI_PANEL)
        selection_bar.pack(fill=tk.X, pady=(6, 0))
        self.event_feed_selection_lbl = tk.Label(
            selection_bar,
            text="Select an event to copy its system, body or useful detail",
            fg=self.UI_DIM, bg=self.UI_PANEL, font=("Segoe UI", 8), anchor="w",
        )
        self.event_feed_selection_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.event_feed_copy_btn = self._action_button(
            selection_bar, "COPY SELECTED", self._copy_selected_event_feed, muted=True,
        )
        self.event_feed_copy_btn.config(state=tk.DISABLED)
        self.event_feed_copy_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.event_feed_source_btn = self._action_button(
            selection_bar, "OPEN SOURCE", self._open_selected_event_feed_link, muted=True,
        )
        self.event_feed_source_btn.config(state=tk.DISABLED)
        self.event_feed_source_btn.pack(side=tk.RIGHT)

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
        self.event_feed_selected_idx = None
        if hasattr(self, "event_filter_buttons"):
            for tag, btn in self.event_filter_buttons.items():
                selected = tag == mode
                btn.config(
                    fg=COLOR_TEXT if selected else "#888",
                    bg=self.UI_PANEL_2 if selected else self.UI_PANEL,
                )
        if hasattr(self, "event_feed_filter_lbl"):
            labels = {
                "ALL": "ALL ACTIVITY",
                "DISCOVERY": "DISCOVERIES & SURVEYS",
                "NAVIGATION": "ROUTE & FLIGHT",
                "COMPASS": "COMPASS ACTIVITY",
                "ALERTS": "WARNINGS & FAILURES",
                "OPERATIONS": "OPERATIONS & SERVICES",
            }
            self.event_feed_filter_lbl.config(text=labels.get(mode, str(mode)))
        if hasattr(self, "event_feed_selection_lbl"):
            self.event_feed_selection_lbl.config(
                text="Select an event to copy its system, body or useful detail"
            )
        for widget_name in ("event_feed_copy_btn", "event_feed_source_btn"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.config(state=tk.DISABLED)
        self._refresh_event_feed()

    def _toggle_console(self):
        self._console_visible = not self._console_visible
        if self._console_visible:
            self._console_frame.pack(fill=tk.X, pady=(4, 0))
            self._console_toggle_btn.config(text="▼  DIAGNOSTICS")
        else:
            self._console_frame.pack_forget()
            self._console_toggle_btn.config(text="▶  DIAGNOSTICS")

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
        # Do not let a live insertion move the selection highlight onto a
        # different event while the commander is reaching for Copy/Open.
        self.event_feed_selected_idx = None
        if hasattr(self, "event_feed_selection_lbl"):
            self.event_feed_selection_lbl.config(
                text="Select an event to copy its system, body or useful detail"
            )
        for widget_name in ("event_feed_copy_btn", "event_feed_source_btn"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.config(state=tk.DISABLED)
        self.event_feed_entries.insert(0, entry)
        if len(self.event_feed_entries) > self.event_feed_max_entries:
            self.event_feed_entries = self.event_feed_entries[:self.event_feed_max_entries]
        self._event_feed_dirty = True
        if (self._dashboard_stream_visible("live")
                and not getattr(self, "_defer_dashboard_stream_render", False)):
            self._refresh_event_feed()
            self._event_feed_dirty = False

        toast_hud = getattr(self, "toast_hud", None)
        if toast_hud and sev in ("WARN", "FAIL"):
            toast_hud.push(entry["tag"], msg_clean, severity=sev.lower())

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
        self._defer_dashboard_stream_render = True
        try:
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
        finally:
            self._defer_dashboard_stream_render = False
        if pending or history_pending:
            self._flush_dashboard_stream_views()
        more_pending = False
        try:
            with self._event_feed_pending_lock:
                more_pending = bool(self._event_feed_pending or self._journal_history_pending)
        except Exception:
            pass
        try:
            self.root.after(50 if more_pending else 200, self._tick_event_feed_queue)
        except Exception:
            pass

    def _dashboard_streams_visible(self):
        return getattr(self, "_active_page", "DASHBOARD") == "DASHBOARD"

    def _dashboard_stream_visible(self, name):
        return (
            self._dashboard_streams_visible()
            and getattr(self, "dashboard_stream_mode", "live") == name
        )

    def _refresh_journal_history_view(self):
        self._render_journal_history_canvas()
        if hasattr(self, "journal_history_count_lbl"):
            self.journal_history_count_lbl.config(text=f"{len(self.journal_history_entries)} EVENTS")

    def _flush_dashboard_stream_views(self, force=False):
        if not force and not self._dashboard_streams_visible():
            return
        show_live = force or self._dashboard_stream_visible("live")
        show_raw = force or self._dashboard_stream_visible("raw")
        if show_live and (force or getattr(self, "_event_feed_dirty", False)):
            self._refresh_event_feed()
            self._event_feed_dirty = False
        if show_raw and (force or getattr(self, "_journal_history_dirty", False)):
            self._refresh_journal_history_view()
            self._journal_history_dirty = False

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
            planet_class = payload.get("PlanetClass") or payload.get("planet_class")
            star_type = payload.get("StarType") or payload.get("star_type")
            detail = planet_class or star_type_label(star_type, "Scan")
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
        self._journal_history_dirty = True
        if (self._dashboard_stream_visible("raw")
                and not getattr(self, "_defer_dashboard_stream_render", False)):
            self._refresh_journal_history_view()
            self._journal_history_dirty = False

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
        tag = entry.get("tag")
        groups = {
            "DISCOVERY": {"VALUABLE", "SCAN", "DSS", "BIO", "MILESTONE", "EXPEDITION"},
            "NAVIGATION": {"JUMP", "ROUTE", "SYSTEM", "DOCK"},
            "COMPASS": {"AI", "MUSIC"},
            "OPERATIONS": {
                "TRADE", "CARRIER", "EDSM", "EDDN", "ACHIEVEMENT",
                "PROFILE", "INFO",
            },
        }
        if mode == "ALERTS":
            return tag == "ALERT" or entry.get("severity") in ("WARN", "FAIL")
        if mode in groups:
            return tag in groups[mode]
        return tag == mode

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
        return f"{ts_txt}   {row.get('tag', 'INFO'):<9}  {row.get('message', '')}"

    def _recolor_event_feed_rows(self):
        if not hasattr(self, "event_feed_list"):
            return
        self.event_feed_list.config(state=tk.NORMAL)
        for idx in range(max(self.event_feed_display_limit, len(getattr(self, "event_feed_view", []))) + 1):
            self.event_feed_list.tag_remove(f"event_row_{idx}", "1.0", tk.END)
        for idx, row in enumerate(getattr(self, "event_feed_view", [])):
            tag = f"event_row_{idx}"
            self.event_feed_list.tag_add(tag, f"{idx + 1}.0", f"{idx + 2}.0")
            selected = idx == getattr(self, "event_feed_selected_idx", None)
            self.event_feed_list.tag_config(
                tag,
                foreground=self._event_feed_row_color(row),
                background=self.UI_PANEL_2 if selected else "#0b0f13",
            )
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
        if hasattr(self, "event_feed_count_lbl"):
            total = len(self.event_feed_entries)
            shown = len(visible)
            count_text = f"{total} CURATED EVENT{'S' if total != 1 else ''}"
            if shown != total:
                count_text += f" · {shown} MATCH"
            self.event_feed_count_lbl.config(text=count_text)
        lines = [self._event_feed_row_text(row) for row in rows]
        if not lines:
            if self.event_feed_entries:
                lines = ["No events match this exploration-log filter."]
            else:
                lines = ["Waiting for live exploration activity from Elite Dangerous..."]
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
        if self.event_feed_selected_idx is not None:
            row = self.event_feed_view[self.event_feed_selected_idx]
            if hasattr(self, "event_feed_selection_lbl"):
                action = "double-click or open source" if row.get("url") else "ready to copy"
                self.event_feed_selection_lbl.config(
                    text=f"{row.get('tag', 'INFO')} selected · {action}"
                )
            if hasattr(self, "event_feed_copy_btn"):
                self.event_feed_copy_btn.config(
                    state=tk.NORMAL if row.get("copy_text") else tk.DISABLED,
                )
            if hasattr(self, "event_feed_source_btn"):
                self.event_feed_source_btn.config(
                    state=tk.NORMAL if row.get("url") else tk.DISABLED,
                )
        self._recolor_event_feed_rows()
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
        if hasattr(self, "event_feed_selection_lbl"):
            self.event_feed_selection_lbl.config(text="Selected event detail copied to clipboard")

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
        dispatcher = getattr(self, "_ui_post", None)
        if callable(dispatcher):
            dispatcher(self._refresh_log_view, key="debug-log-view")
        else:
            self.root.after(0, self._refresh_log_view)

    def schedule_dashboard_refresh(self, full=False):
        if full:
            self.dashboard_refresh_full_pending = True
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        if self.dashboard_refresh_job is None:
            self.dashboard_refresh_job = self.root.after(120, self._run_scheduled_dashboard_refresh)

    def _run_scheduled_dashboard_refresh(self):
        t0 = self._perf_start()
        self.dashboard_refresh_job = None
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
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

    def _game_is_active(self):
        """True while Elite Dangerous looks like it is actually running.

        Status.json and the journal are only written by the live game, so
        recent activity on either is our "game is up" signal. The window is
        generous because the watcher only fires on file changes, and a docked
        or menu-idle commander can go a while without producing either.
        """
        newest = max(
            float(getattr(self, "last_status_event_ts", 0) or 0),
            float(getattr(self, "last_journal_event_ts", 0) or 0),
        )
        if not newest:
            return False
        return (time.time() - newest) <= GAME_ACTIVE_GRACE_S

    def _tick_session_clock(self):
        if not self.is_running:
            return
        achievement_engine = getattr(self, "achievement_engine", None)
        if achievement_engine:
            try:
                achievement_engine.tick_playtime(active=self._game_is_active())
            except Exception:
                pass
        if self._dashboard_streams_visible():
            if hasattr(self, "summary_session"):
                self.summary_session.config(text=self._get_session_elapsed_text())
            newest_until = max(
                (row.get("new_until", 0) for row in getattr(self, "event_feed_view", [])),
                default=0,
            )
            if time.time() <= newest_until + 1.1:
                self._recolor_event_feed_rows()
            deck = getattr(self, "adaptive_command", None)
            if (
                deck and deck.automatic
                and getattr(self, "_dashboard_render_mode", "exploration") != "exploration"
            ):
                activity = (
                    (getattr(self, "ai_operational_state", {}) or {}).get("activity") or {}
                )
                observed_at = float(activity.get("last_event_at") or activity.get("since") or 0)
                if observed_at and time.time() - observed_at > AUTOMATIC_MODE_IDLE_S:
                    self.schedule_dashboard_refresh()
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

    def _post_update_result(self, callback):
        try:
            dispatcher = getattr(self, "_ui_post", None)
            if callable(dispatcher):
                dispatcher(callback)
            else:
                self.root.after(0, callback)
        except Exception:
            pass

    def _set_about_update_status(self, text, fg=None):
        label = getattr(self, "about_update_status", None)
        if self._widget_alive(label):
            label.config(text=text, fg=fg or self.UI_MUTED)
        button_widget = getattr(self, "about_update_btn", None)
        if self._widget_alive(button_widget):
            button_widget.config(state=tk.NORMAL)

    def _start_manual_update_check(self):
        if getattr(self, "_update_check_running", False):
            return
        self._update_check_running = True
        self._set_about_update_status("Checking GitHub Releases…", COLOR_ACCENT)
        if self._widget_alive(getattr(self, "about_update_btn", None)):
            self.about_update_btn.config(state=tk.DISABLED)
        threading.Thread(
            target=self.check_updates, args=(True,), name="release-check", daemon=True,
        ).start()

    def check_updates(self, manual=False):
        """Check the public VoidCompass GitHub releases without blocking Tk."""
        try:
            response = requests.get(
                RELEASES_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"VoidCompass/{APP_VERSION}",
                },
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            tag = str(data.get("tag_name") or "").lstrip("vV")
            html_url = str(data.get("html_url") or RELEASES_URL)
            current_v = _version_key(APP_VERSION)
            remote_v = _version_key(tag)
            if not remote_v:
                raise ValueError("latest release has no valid version tag")

            if remote_v > current_v:
                self._post_update_result(lambda: self.show_update_btn(html_url, tag))
            elif manual:
                if remote_v == current_v:
                    message = f"Up to date — v{APP_VERSION} is the latest public release."
                else:
                    message = f"This build is newer than the latest public release (v{tag})."
                self._post_update_result(
                    lambda text=message: self._set_about_update_status(text, self.UI_OK)
                )
        except Exception as exc:
            if manual:
                message = f"Could not check GitHub Releases: {exc}"
                self._post_update_result(
                    lambda text=message: self._set_about_update_status(text, self.UI_FAIL)
                )
        finally:
            self._update_check_running = False

    def show_update_btn(self, url, tag):
        self.log(f"✨ UPDATE AVAILABLE: v{tag}")
        self._set_about_update_status(
            f"Update available — v{tag}", self.UI_WARN,
        )
        existing = getattr(self, "_release_update_nav_btn", None)
        if self._widget_alive(existing):
            existing.config(text=f"Update v{tag}", command=lambda: webbrowser.open_new_tab(url))
            return
        target = getattr(self, "nav_utilities", self.nav)
        btn = self._action_button(
            target, f"Update v{tag}", lambda: webbrowser.open_new_tab(url), accent=True,
        )
        btn.pack(fill=tk.X, pady=(6, 0))
        self._release_update_nav_btn = btn

    def update_nav_label(self):
        txt = "NO ROUTE"
        if self.dest_name:
            txt = self.dest_name
        
        if not self.batch_mode and self._widget_alive(getattr(self, "nav_stat", None)):
            self.root.after(0, lambda: self.nav_stat.config(text=txt))

    def _current_route_progress(self):
        """Return compact, truthful progress for the live route or saved waypoints."""
        route = list(getattr(self, "route_list", None) or [])
        current = getattr(self, "current_sys", None)
        if route:
            try:
                current_index = route.index(current)
            except (ValueError, TypeError):
                current_index = -1
            remaining = max(0, len(route) - current_index - 1) if current_index >= 0 else len(route)
            if remaining <= 0:
                return {
                    "mode": "game", "remaining": 0,
                    "text": "NAV ROUTE · COMPLETE", "summary": "COMPLETE",
                }
            noun = "JUMP" if remaining == 1 else "JUMPS"
            return {
                "mode": "game", "remaining": remaining,
                "text": f"NAV ROUTE · {remaining} {noun} LEFT",
                "summary": f"{remaining} LEFT",
            }

        waypoint_manager = getattr(self, "waypoint_manager", None)
        waypoints = list(getattr(waypoint_manager, "waypoints", None) or [])
        if waypoints:
            total = len(waypoints)
            visited = sum(1 for waypoint in waypoints if waypoint.get("visited", False))
            remaining = max(0, total - visited)
            if remaining <= 0:
                return {
                    "mode": "waypoints", "visited": visited, "total": total, "remaining": 0,
                    "text": f"WAYPOINTS · {visited}/{total} · COMPLETE", "summary": "COMPLETE",
                }
            return {
                "mode": "waypoints", "visited": visited, "total": total, "remaining": remaining,
                "text": f"WAYPOINTS · {visited}/{total} · {remaining} LEFT",
                "summary": f"{visited}/{total}",
            }

        return {
            "mode": "none", "remaining": 0,
            "text": "NO ACTIVE ROUTE", "summary": "INACTIVE",
        }

    def _refresh_route_progress_labels(self):
        progress = self._current_route_progress()
        route_progress_stat = getattr(self, "route_progress_stat", None)
        if self._widget_alive(route_progress_stat):
            self._config_label_if_changed(route_progress_stat, text=progress["text"])
        summary_route = getattr(self, "summary_route", None)
        if self._widget_alive(summary_route):
            self._config_label_if_changed(summary_route, text=progress["summary"])
        return progress

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

        hops, hops_truncated = route_strip.build_route_hops(
            current_coords, route, entries, current, waypoint_manager=getattr(self, "waypoint_manager", None), max_hops=10
        )

        return {
            "previous": previous or "---",
            "current": current,
            "next": next_name or "---",
            "route": route_txt,
            "prev_distance": prev_distance_txt,
            "next_distance": next_distance_txt,
            "has_route": bool(route or next_name),
            "hops": hops,
            "hops_truncated": hops_truncated,
            "total_distance_text": route_strip.total_distance_text(hops, hops_truncated),
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
            right_x = max(w - 34, left_x + 34)
            hops = ctx.get("hops") or []

            canvas.create_rectangle(0, 0, w, h, fill="#090d12", outline="")
            canvas.create_line(left_x, spine_y, right_x, spine_y, fill=self.UI_BORDER, width=2)

            theme = {"accent": COLOR_ACCENT, "orange": COLOR_ORANGE}
            if hops:
                route_strip.draw_pip_line(canvas, left_x, right_x, spine_y, hops, theme, dot_radius=4, bg="#090d12")

            current_radius = 6
            canvas.create_oval(
                left_x - current_radius, spine_y - current_radius, left_x + current_radius, spine_y + current_radius,
                outline=COLOR_ACCENT, width=2, fill="#090d12",
            )
            canvas.create_text(left_x, 14, text="CURRENT", fill=COLOR_ACCENT, font=("Segoe UI", 7, "bold"))
            dest_label = "DEST" if hops else "---"
            dest_color = COLOR_ORANGE if hops else self.UI_DIM
            canvas.create_text(right_x, 14, text=dest_label, fill=dest_color, font=("Segoe UI", 7, "bold"))

            canvas.create_text((left_x + right_x) // 2, spine_y - 12, text=ctx["next_distance"], fill=COLOR_ORANGE if ctx["has_route"] else self.UI_MUTED, font=("Consolas", 8, "bold"))

            footer = ctx["route"]
            total_txt = ctx.get("total_distance_text")
            if total_txt:
                footer = f"{footer}  •  {total_txt}"
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
        set_mouse_passthrough(
            self.ground_popup,
            bool(self.config.get("overlay_mouse_passthrough", True)),
        )

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
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        ship = (getattr(self, "cmdr_ship", {}) or {}).get("ship_name") or (getattr(self, "cmdr_ship", {}) or {}).get("ship")
        flight_state = str(getattr(self, "hud_flight_state", "FLIGHT") or "FLIGHT")
        sys_text = f"{ship or 'SHIP'} · {flight_state}".upper()
        
        self.sys_stat.config(text=sys_text)
        self.scan_stat.config(text=f"{self.scanned} / {self.total}")
        self.update_nav_label()

        route_progress = self._refresh_route_progress_labels()

        traffic_day = self.system_traffic.get("day", 0)
        traffic_week = self.system_traffic.get("week", 0)
        traffic_total = self.system_traffic.get("total", 0)

        self.summary_sys.config(text=self.current_sys or "---")
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
        self._refresh_command_dashboard(route_progress)
        self._perf_spike("update_dashboard_panels", t0, threshold_ms=28.0)

    def update_dashboard_ui(self):
        """Force update full dashboard, including waypoint panel."""
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            self.dashboard_refresh_full_pending = True
            return
        self.update_dashboard_panels()
        try:
            self.update_carrier_panel()
        except Exception as _cp_err:
            import logging
            logging.warning(f"update_carrier_panel error: {_cp_err}")
        self.update_waypoint_display()

    def update_carrier_panel(self, force=False):
        """Refresh the sidebar Fleet Carrier status panel from carrier_tracker data."""
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        if not hasattr(self, "carrier_panel") or not hasattr(self, "carrier_tracker"):
            return
        deck = getattr(self, "adaptive_command", None)
        render_mode = str(deck.current_mode if deck else "exploration")
        if not force and render_mode not in ("general", "exploration", "carrier"):
            # In add-on modes this physical card is intentionally reused for
            # mode-specific support; a carrier refresh must not overwrite it.
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
        # Route Plotter uses this same manager and callback. Refresh the
        # Dashboard progress immediately as routes are imported, edited, or cleared.
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        self._refresh_route_progress_labels()
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
                    
                    info_text = f"STAR {p_star}  //  GOV {gov}  //  ALLEGIANCE {alg}"
            
            if note:
                if info_text == "Fetching data..." or info_text == "EDSM Data Unavailable":
                     info_text = f"NOTE // {note}"
                else:
                     info_text = f"NOTE // {note}  //  {info_text}"

            self.wp_name_lbl.config(text=name)
            self.wp_dist_lbl.config(text=dist_str)
            self._set_wp_info_text(info_text)
            self.update_hud()

