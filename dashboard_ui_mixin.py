import time
import math
import tkinter as tk
import requests
import webbrowser
from datetime import datetime
from tkinter import scrolledtext

from config import COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT
from version import APP_VERSION


class DashboardUIMixin:
    UI_BG = "#080a0d"
    UI_PANEL = "#12161b"
    UI_PANEL_2 = "#171d23"
    UI_BORDER = "#26313a"
    UI_MUTED = "#7d8891"
    UI_DIM = "#4e5962"
    UI_FAIL = "#ff5c5c"
    UI_WARN = "#ff9a3c"
    UI_OK = "#21d189"
    UI_FONT = ("Segoe UI", 9)
    UI_FONT_BOLD = ("Segoe UI", 9, "bold")
    UI_FONT_TITLE = ("Segoe UI", 13, "bold")
    UI_MONO = ("Consolas", 9)
    UI_MONO_BOLD = ("Consolas", 10, "bold")

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
        return tk.Frame(
            parent,
            bg=bg or self.UI_PANEL,
            highlightbackground=border or self.UI_BORDER,
            highlightthickness=1,
            bd=0,
        )

    def _section_label(self, parent, text, fg=None, bg=None):
        return tk.Label(
            parent,
            text=text,
            font=self.UI_FONT_BOLD,
            fg=fg or COLOR_ORANGE,
            bg=bg or parent.cget("bg"),
            anchor="w",
        )

    def _action_button(self, parent, text, command, accent=False, muted=False):
        bg = COLOR_ACCENT if accent else parent.cget("bg")
        fg = "black" if accent else (self.UI_DIM if muted else COLOR_TEXT)
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=COLOR_ACCENT if accent else self.UI_PANEL_2,
            activeforeground="black" if accent else COLOR_TEXT,
            font=self.UI_FONT_BOLD,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
        )

    def setup_layout(self):
        self.root.configure(bg=self.UI_BG)

        self.nav = tk.Frame(self.root, bg="#0c1014", height=54)
        self.nav.pack(fill=tk.X, padx=12, pady=(12, 0))
        self.nav.pack_propagate(False)

        brand = tk.Frame(self.nav, bg="#0c1014")
        brand.pack(side=tk.LEFT, fill=tk.Y, padx=(14, 8))
        tk.Label(brand, text="VOID COMPASS", font=("Segoe UI", 15, "bold"), fg=COLOR_ACCENT, bg="#0c1014").pack(anchor="w", pady=(7, 0))
        tk.Label(brand, text=f"EXPLORATION COMMAND DECK  //  v{APP_VERSION}", font=("Segoe UI", 8, "bold"), fg=self.UI_MUTED, bg="#0c1014").pack(anchor="w")

        nav_actions = tk.Frame(self.nav, bg="#0c1014")
        nav_actions.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        self._action_button(nav_actions, "Configuration", self.open_settings, accent=True).pack(side=tk.RIGHT, padx=(6, 0), pady=10)
        self._action_button(nav_actions, "Screenshots", self.open_screenshots_folder).pack(side=tk.RIGHT, padx=(6, 0), pady=10)
        self._action_button(nav_actions, "Fleet Watcher", self.open_fleet_carrier_watcher).pack(side=tk.RIGHT, padx=(6, 0), pady=10)
        self._action_button(nav_actions, "Mining", self.open_mining_window).pack(side=tk.RIGHT, padx=(6, 0), pady=10)
        self._action_button(nav_actions, "Route Planner", self.open_route_planner).pack(side=tk.RIGHT, padx=(6, 0), pady=10)

        self.summary_bar = tk.Frame(self.root, bg=self.UI_BG)
        self.summary_bar.pack(fill=tk.X, padx=12, pady=(10, 0))

        def _summary_item(text, accent=False):
            wrap = tk.Frame(self.summary_bar, bg=self.UI_PANEL_2, highlightbackground=self.UI_BORDER, highlightthickness=1)
            wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
            lbl = tk.Label(
                wrap,
                text=text,
                font=self.UI_MONO_BOLD,
                fg=COLOR_ACCENT if accent else COLOR_TEXT,
                bg=self.UI_PANEL_2,
                anchor="w",
            )
            lbl.pack(fill=tk.X, padx=10, pady=7)
            return lbl

        self.summary_sys = _summary_item("SYS: ---", accent=True)
        self.summary_route = _summary_item("ROUTE: INACTIVE")
        self.summary_scan = _summary_item("SCAN: 0/0")
        self.summary_traffic = _summary_item("TRAFFIC: 0/0/0")
        self.summary_session = _summary_item("SESSION: 00:00:00")

        body = tk.Frame(self.root, bg=self.UI_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.side = tk.Frame(body, bg=self.UI_BG, width=310)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.side.pack_propagate(False)

        status_card = self._panel(self.side)
        status_card.pack(fill=tk.X, pady=(0, 10))
        self._section_label(status_card, "SHIP SYSTEMS").pack(anchor="w", padx=12, pady=(9, 0))
        self.integration_lbl = tk.Label(status_card, text="HUD: ON | SHOTS: OFF", font=self.UI_MONO, fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w")
        self.integration_lbl.pack(fill=tk.X, padx=12, pady=(3, 10))

        metrics_card = self._panel(self.side)
        metrics_card.pack(fill=tk.X, pady=(0, 10))
        self._section_label(metrics_card, "PRIMARY TELEMETRY").pack(anchor="w", padx=12, pady=(9, 0))
        self.sys_stat = self.create_stat(metrics_card, "CURRENT SYSTEM", "---")
        self.nav_stat = self.create_stat(metrics_card, "NAV TARGET", "---")
        self.scan_stat = self.create_stat(metrics_card, "SCAN PROGRESS", "0 / 0")

        self.ground_panel = self._panel(self.side)
        self.ground_panel.pack(fill=tk.X, pady=(0, 10))
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
        self.wp_panel.pack(fill=tk.X, pady=(0, 10))
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
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.alert_bar = self._panel(center, bg=self.UI_PANEL_2)
        self.alert_bar.pack(fill=tk.X, pady=(0, 10))
        tk.Label(self.alert_bar, text="ALERTS", font=self.UI_FONT_BOLD, fg=COLOR_ORANGE, bg=self.UI_PANEL_2).pack(side=tk.LEFT, padx=(12, 8), pady=8)
        self.alert_lbl = tk.Label(self.alert_bar, text="NONE", font=self.UI_MONO_BOLD, fg=self.UI_MUTED, bg=self.UI_PANEL_2, anchor="w")
        self.alert_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)

        ops = tk.Frame(center, bg=self.UI_BG)
        ops.pack(fill=tk.BOTH, expand=True)
        for col in range(2):
            ops.grid_columnconfigure(col, weight=1)
        for row in range(3):
            ops.grid_rowconfigure(row, weight=1)

        self.card_nav = self._build_ops_card(ops, "NAVIGATION", 0, 0)
        self.card_scan = self._build_ops_card(ops, "SCANNING", 0, 1)
        self.card_system = self._build_ops_card(ops, "SYSTEM INTEL", 1, 0)
        self.card_value = self._build_ops_card(ops, "ECONOMY", 1, 1)
        self.card_session = self._build_ops_card(ops, "SESSION", 2, 0)
        self.card_ops = self._build_ops_card(ops, "OPERATIONS", 2, 1)

        log_frame = self._panel(center)
        log_frame.pack(fill=tk.X, pady=(10, 0))
        log_toolbar = tk.Frame(log_frame, bg=self.UI_PANEL)
        log_toolbar.pack(fill=tk.X, padx=10, pady=(8, 2))
        self._section_label(log_toolbar, "DEBUG CONSOLE", fg=self.UI_MUTED).pack(side=tk.LEFT)
        self.log_box = scrolledtext.ScrolledText(log_frame, bg="#050607", fg="#62d66f", font=("Consolas", 8), borderwidth=0, height=5, relief=tk.FLAT)
        self.log_box.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.details_drawer = self._panel(body)
        self.details_drawer.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(0, 0))
        self.details_drawer.config(width=450)
        self.details_drawer.pack_propagate(False)
        feed_wrap = tk.Frame(self.details_drawer, bg=self.UI_PANEL)
        feed_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._section_label(feed_wrap, "LIVE EVENT TIMELINE").pack(anchor="w")
        self.event_filter_row = tk.Frame(feed_wrap, bg=self.UI_PANEL)
        self.event_filter_row.pack(fill=tk.X, pady=(6, 4))
        for col in range(3):
            self.event_filter_row.grid_columnconfigure(col, weight=1, uniform="event_filter")
        self.event_filter_buttons = {}
        event_filters = (
            ("ALL", "ALL"),
            ("VALUABLE", "VALUE"),
            ("SCAN", "SCAN"),
            ("ALERT", "ALERT"),
            ("JUMP", "JUMP"),
            ("ROUTE", "ROUTE"),
            ("SYSTEM", "SYSTEM"),
            ("DSS", "DSS"),
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
            btn.grid(row=idx // 3, column=idx % 3, sticky="ew", padx=2, pady=2)
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

    def create_stat(self, parent, label, val):
        tk.Label(parent, text=label, font=("Segoe UI", 8, "bold"), fg=self.UI_DIM, bg=parent.cget("bg")).pack(anchor="w", padx=12, pady=(8, 0))
        l = tk.Label(parent, text=val, font=self.UI_MONO_BOLD, fg=COLOR_TEXT, bg=parent.cget("bg"), anchor="w")
        l.pack(fill=tk.X, padx=12)
        return l

    def _build_ops_card(self, parent, title, row, col):
        card = self._panel(parent)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        tk.Label(card, text=title, font=self.UI_FONT_BOLD, fg=COLOR_ORANGE, bg=self.UI_PANEL).pack(anchor="w", padx=12, pady=(10, 0))
        line1 = tk.Label(card, text="-", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT, bg=self.UI_PANEL, anchor="w")
        line1.pack(fill=tk.X, padx=12, pady=(8, 0))
        line2 = tk.Label(card, text="-", font=self.UI_MONO, fg="#aab4bd", bg=self.UI_PANEL, anchor="w")
        line2.pack(fill=tk.X, padx=12, pady=(4, 0))
        line3 = tk.Label(card, text="-", font=self.UI_MONO, fg=self.UI_MUTED, bg=self.UI_PANEL, anchor="w")
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

    def add_event_feed_entry(self, tag, message, severity="INFO", copy_text=None, url=None, pinned=False):
        if not message:
            return
        if getattr(self, "batch_mode", False) and getattr(self, "is_first_load", False):
            return
        entry = {
            "ts": time.time(),
            "tag": (tag or "INFO").upper(),
            "severity": (severity or "INFO").upper(),
            "message": str(message),
            "copy_text": copy_text or str(message),
            "url": url,
            "pinned": bool(pinned),
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

    def _event_feed_matches_filter(self, entry):
        mode = getattr(self, "event_feed_filter", "ALL")
        if mode == "ALL":
            return True
        return entry.get("tag") == mode

    def _event_feed_row_color(self, entry):
        sev = entry.get("severity", "INFO")
        if sev == "FAIL":
            base = "#ff4d4d"
        elif sev == "WARN":
            base = COLOR_ORANGE
        else:
            base = COLOR_TEXT
        if entry.get("tag") == "VALUABLE":
            base = COLOR_ORANGE
        elif entry.get("tag") == "JUMP":
            base = COLOR_ACCENT
        elif entry.get("tag") == "INFO":
            base = "#aaa"
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
        pin_prefix = "PIN " if row.get("pinned") else ""
        return f"[{ts_txt}] {pin_prefix}[{row.get('tag', 'INFO')}] {row.get('message', '')}"

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
        pinned = [e for e in visible if e.get("pinned")]
        unpinned = [e for e in visible if not e.get("pinned")]
        rows = pinned + unpinned
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
            self.summary_session.config(text=f"SESSION: {self._get_session_elapsed_text()}")
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
        btn = self._action_button(self.nav, f"Update v{tag}", lambda: webbrowser.open(url), accent=True)
        btn.pack(side=tk.RIGHT, padx=8, pady=10)

    def update_nav_label(self):
        txt = "NO ROUTE"
        if self.dest_name:
            txt = self.dest_name
        
        if not self.batch_mode:
            self.root.after(0, lambda: self.nav_stat.config(text=txt))

    def set_ground_target_from_entries(self):
        try:
            lat = float(self.ground_lat_entry.get().strip())
            lon = float(self.ground_lon_entry.get().strip())
        except Exception:
            self.ground_status_lbl.config(text="Target: INVALID LAT/LON", fg="#ff7777")
            self.ground_detail_lbl.config(text="Use numeric values, e.g. 12.3456 and -98.7654", fg="#ff7777")
            return

        if lat < -90.0 or lat > 90.0:
            self.ground_status_lbl.config(text="Target: INVALID LAT", fg="#ff7777")
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
            self.ground_status_lbl.config(text="Target: NO PLANET POSITION", fg="#ff9a4d")
            self.ground_detail_lbl.config(text="Current latitude/longitude not available yet.", fg="#ff9a4d")
            return

        self.target_lat = float(self.current_latitude)
        self.target_lon = float(self.current_longitude)
        self.target_latlon_active = True
        self.config["ground_target_active"] = True
        self.config["ground_target_lat"] = self.target_lat
        self.config["ground_target_lon"] = self.target_lon
        self._save_config_file()
        self.ground_lat_entry.delete(0, tk.END)
        self.ground_lon_entry.delete(0, tk.END)
        self.ground_lat_entry.insert(0, f"{self.target_lat:.6f}")
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
        if hasattr(self, "ground_popup_toggle_btn"):
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
        if not hasattr(self, "ground_status_lbl"):
            self._perf_spike("update_ground_target_ui", t0, threshold_ms=18.0)
            return
        if hasattr(self, "ground_popup_toggle_btn"):
            self._config_label_if_changed(
                self.ground_popup_toggle_btn,
                text="Popup On" if self.ground_popup_enabled else "Popup Off",
                fg=COLOR_TEXT if self.ground_popup_enabled else self.UI_MUTED,
            )

        if not self.target_latlon_active:
            self._config_label_if_changed(self.ground_status_lbl, text="Target: OFF", fg="#888")
            self._config_label_if_changed(self.ground_detail_lbl, text="Set a lat/lon target to start tracking.", fg="#888")
            self._update_ground_popup(None)
            self._perf_spike("update_ground_target_ui", t0, threshold_ms=18.0)
            return

        solution = self._ground_target_solution()
        self._config_label_if_changed(
            self.ground_status_lbl,
            text=f"Target: {self.target_lat:.6f}, {self.target_lon:.6f}",
            fg=COLOR_ACCENT,
        )

        if not solution or solution.get("state") != "OK":
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
        next_waypoint_name = "NONE"
        if self.waypoint_manager.waypoints:
            route_total = len(self.waypoint_manager.waypoints)
            route_visited = sum(1 for wp in self.waypoint_manager.waypoints if wp.get("visited", False))
            route_text = f"{route_visited}/{route_total}"
            for wp in self.waypoint_manager.waypoints:
                if not wp.get("visited", False):
                    next_waypoint_name = wp.get("name", "UNKNOWN")
                    break

        traffic_day = self.system_traffic.get("day", 0)
        traffic_week = self.system_traffic.get("week", 0)
        traffic_total = self.system_traffic.get("total", 0)
        coords_text = "-"
        if isinstance(self.current_coords, (list, tuple)) and len(self.current_coords) == 3:
            try:
                coords_text = f"{self.current_coords[0]:,.0f},{self.current_coords[1]:,.0f},{self.current_coords[2]:,.0f}"
            except Exception:
                coords_text = str(self.current_coords)

        self.summary_sys.config(text=f"SYS: {self.current_sys}")
        self.summary_route.config(text=f"ROUTE: {route_text}")
        self.summary_scan.config(text=f"SCAN: {self.scanned}/{self.total}")
        self.summary_traffic.config(text=f"TRAFFIC: {traffic_day}/{traffic_week}/{traffic_total}")
        self.summary_session.config(text=f"SESSION: {self._get_session_elapsed_text()}")

        self.card_nav.line1.config(text=f"Target: {self.dest_name or 'NO ROUTE'}")
        self.card_nav.line2.config(text=f"Current: {self.current_sys}")
        gt = self._ground_target_solution()
        if gt and gt.get("state") == "OK":
            self.card_nav.line3.config(text=f"Ground: {gt['direction']} | {self._format_ground_distance(gt['distance_m'])}")
        else:
            self.card_nav.line3.config(text=f"Route Progress: {route_text}")

        scan_pct = int((self.scanned / self.total) * 100) if self.total > 0 else 0
        self.card_scan.line1.config(text=f"Scanned: {self.scanned}/{self.total} ({scan_pct}%)")
        self.card_scan.line2.config(text=f"Bodies Tracked: {len(self.scanned_bodies)}")
        self.card_scan.line3.config(text=f"FSS Summary: {'ACTIVE' if self.fss_summary_active else 'IDLE'}")

        self.card_system.line1.config(text=f"Star: {self.star_class or 'UNKNOWN'}")
        self.card_system.line2.config(text=f"System: {self.current_sys}")
        self.card_system.line3.config(text=f"Coords: {coords_text} | FSS: {'YES' if self.in_fss else 'NO'}")

        total_value = 0
        for item in self.scan_items:
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            if isinstance(reward, (int, float)):
                total_value += int(reward)
        self.card_value.line1.config(text=f"System Value Est: {self._format_credits(total_value)}")
        self.card_value.line2.config(text=f"Valuable Bodies: {len(self.valuable_bodies)}")
        self.card_value.line3.config(text=f"Bio Signals: {self.system_bio_signals}")

        self.card_session.line1.config(text=f"Jumps: {self.session_jump_count}")
        self.card_session.line2.config(text=f"Distance: {self.session_ly:,.1f} LY")
        avg_jump = (self.session_ly / self.session_jump_count) if self.session_jump_count else 0.0
        self.card_session.line3.config(text=f"Avg Jump: {avg_jump:,.1f} LY")

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

        planner_open = "YES" if (self.route_plotter and self.route_plotter.win.winfo_exists()) else "NO"
        auto_copy = "ON" if self.config.get("auto_copy_waypoint", False) else "OFF"
        self.card_ops.line1.config(text=f"Waypoints: {route_total} | Pending: {max(route_total - route_visited, 0)}")
        self.card_ops.line2.config(text=f"Next WP: {next_waypoint_name}")
        self.card_ops.line3.config(text=f"Auto-Copy: {auto_copy} | Planner Open: {planner_open}")

        self._refresh_event_feed()
        self._perf_spike("update_dashboard_panels", t0, threshold_ms=28.0)

    def update_dashboard_ui(self):
        """Force update full dashboard, including waypoint panel."""
        self.update_dashboard_panels()

        self.update_waypoint_display()

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

