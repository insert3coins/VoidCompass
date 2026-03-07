import time
import math
import tkinter as tk
import requests
import webbrowser
from datetime import datetime
from tkinter import scrolledtext

from config import COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, COLOR_GREEN
from srvsurvey_rewards import load_bio_reward_catalog
from version import APP_VERSION


class DashboardUIMixin:
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

    def setup_layout(self):
        self.nav = tk.Frame(self.root, bg=COLOR_PANEL, height=50, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        self.nav.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        tk.Label(self.nav, text=f" > VOID COMPASS // V{APP_VERSION}", font=("Courier", 11, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=15)
        
        btn_conf = tk.Button(self.nav, text="[ CONFIGURATION ]", command=self.open_settings, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_conf.pack(side=tk.RIGHT, padx=15)

        # Route Button
        btn_route = tk.Button(self.nav, text="[ ROUTE PLANNER ]", command=self.open_route_planner, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_route.pack(side=tk.RIGHT, padx=5)

        # Fleet Carrier Watcher Button
        btn_fc = tk.Button(self.nav, text="[ FLEET CARRIER WATCHER ]", command=self.open_fleet_carrier_watcher, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_fc.pack(side=tk.RIGHT, padx=5)
        
        # Screenshot Button
        btn_ss = tk.Button(self.nav, text="[ SCREENSHOTS ]", command=self.open_screenshots_folder, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_ss.pack(side=tk.RIGHT, padx=5)

        self.summary_bar = tk.Frame(self.root, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1, height=34)
        self.summary_bar.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.summary_bar.pack_propagate(False)

        def _summary_item(text):
            lbl = tk.Label(self.summary_bar, text=text, font=("Courier", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL)
            lbl.pack(side=tk.LEFT, padx=14)
            return lbl

        self.summary_sys = _summary_item("SYS: ---")
        self.summary_route = _summary_item("ROUTE: INACTIVE")
        self.summary_scan = _summary_item("SCAN: 0/0")
        self.summary_traffic = _summary_item("TRAFFIC: 0/0/0")
        self.summary_session = _summary_item("SESSION: 00:00:00")

        self.alert_bar = tk.Frame(self.root, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1, height=30)
        self.alert_bar.pack(fill=tk.X, padx=10, pady=(6, 0))
        self.alert_bar.pack_propagate(False)
        tk.Label(self.alert_bar, text="ALERTS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=(10, 8))
        self.alert_lbl = tk.Label(self.alert_bar, text="NONE", font=("Courier", 9), fg="#888", bg=COLOR_PANEL, anchor="w")
        self.alert_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        body = tk.Frame(self.root, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.side = tk.Frame(body, bg=COLOR_PANEL, width=320, highlightbackground="#333", highlightthickness=1)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.side.pack_propagate(False)

        status_card = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        status_card.pack(fill=tk.X, padx=10, pady=(10, 8))
        tk.Label(status_card, text="STATUS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 0))
        self.integration_lbl = tk.Label(status_card, text="HUD: ON | DISCORD: OFF | SHOTS: OFF", font=("Courier", 8), fg="#999", bg=COLOR_PANEL, anchor="w")
        self.integration_lbl.pack(fill=tk.X, padx=10, pady=(2, 8))

        metrics_card = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        metrics_card.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(metrics_card, text="PINNED METRICS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 0))
        self.sys_stat = self.create_stat(metrics_card, "CURRENT SYSTEM", "---")
        self.nav_stat = self.create_stat(metrics_card, "NAV TARGET", "---")
        self.scan_stat = self.create_stat(metrics_card, "SCAN PROGRESS", "0 / 0")

        self.ground_panel = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        self.ground_panel.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(self.ground_panel, text="GROUND TARGET", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 2))
        input_row = tk.Frame(self.ground_panel, bg=COLOR_PANEL)
        input_row.pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Label(input_row, text="LAT", font=("Courier", 8), fg="#999", bg=COLOR_PANEL).grid(row=0, column=0, sticky="w")
        tk.Label(input_row, text="LON", font=("Courier", 8), fg="#999", bg=COLOR_PANEL).grid(row=0, column=2, sticky="w", padx=(8, 0))
        self.ground_lat_entry = tk.Entry(input_row, width=10, bg="#111", fg=COLOR_TEXT, font=("Courier", 9), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.ground_lat_entry.grid(row=1, column=0, sticky="ew")
        self.ground_lon_entry = tk.Entry(input_row, width=10, bg="#111", fg=COLOR_TEXT, font=("Courier", 9), insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.ground_lon_entry.grid(row=1, column=2, sticky="ew", padx=(8, 0))
        input_row.grid_columnconfigure(0, weight=1)
        input_row.grid_columnconfigure(2, weight=1)

        btn_row = tk.Frame(self.ground_panel, bg=COLOR_PANEL)
        btn_row.pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Button(btn_row, text="[ SET ]", command=self.set_ground_target_from_entries, bg=COLOR_ACCENT, fg="black", font=("Courier", 8, "bold"), relief=tk.FLAT).pack(side=tk.LEFT)
        tk.Button(btn_row, text="[ HERE ]", command=self.set_ground_target_here, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 8, "bold"), relief=tk.FLAT).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(btn_row, text="[ CLEAR ]", command=self.clear_ground_target, bg=COLOR_PANEL, fg="#aaa", font=("Courier", 8, "bold"), relief=tk.FLAT).pack(side=tk.LEFT, padx=(6, 0))
        self.ground_popup_toggle_btn = tk.Button(
            btn_row,
            text="[ POPUP: ON ]" if getattr(self, "ground_popup_enabled", True) else "[ POPUP: OFF ]",
            command=self.toggle_ground_popup,
            bg=COLOR_PANEL,
            fg="#aaa",
            font=("Courier", 8, "bold"),
            relief=tk.FLAT,
        )
        self.ground_popup_toggle_btn.pack(side=tk.RIGHT)
        overlay_row = tk.Frame(self.ground_panel, bg=COLOR_PANEL)
        overlay_row.pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Label(overlay_row, text="BIO OVERLAY", font=("Courier", 8), fg="#999", bg=COLOR_PANEL).pack(side=tk.LEFT)
        self.bio_popup_toggle_btn = tk.Button(
            overlay_row,
            text="[ ON ]" if bool(self.config.get("bio_estimate_popup_enabled", True)) else "[ OFF ]",
            command=self.toggle_bio_estimate_popup,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT if bool(self.config.get("bio_estimate_popup_enabled", True)) else "#888",
            font=("Courier", 8, "bold"),
            relief=tk.FLAT,
        )
        self.bio_popup_toggle_btn.pack(side=tk.RIGHT)
        self.ground_status_lbl = tk.Label(self.ground_panel, text="Target: OFF", font=("Courier", 8, "bold"), fg="#888", bg=COLOR_PANEL, anchor="w")
        self.ground_status_lbl.pack(fill=tk.X, padx=10, pady=(0, 2))
        self.ground_detail_lbl = tk.Label(self.ground_panel, text="Waiting for planetary coordinates.", font=("Courier", 8), fg="#888", bg=COLOR_PANEL, anchor="w")
        self.ground_detail_lbl.pack(fill=tk.X, padx=10, pady=(0, 8))

        self.wp_panel = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1, height=180)
        self.wp_panel.pack(fill=tk.X, padx=10, pady=8)
        self.wp_panel.pack_propagate(False)
        header_row = tk.Frame(self.wp_panel, bg=COLOR_PANEL)
        header_row.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(header_row, text="ROUTE NOTES", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT)
        self.wp_dist_lbl = tk.Label(header_row, text="", font=("Courier", 9, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL)
        self.wp_dist_lbl.pack(side=tk.RIGHT)
        self.wp_name_lbl = tk.Label(self.wp_panel, text="NO ACTIVE ROUTE", font=("Courier", 12, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
        self.wp_name_lbl.pack(fill=tk.X, padx=10, pady=(6, 0))
        self.wp_info_wrap = tk.Frame(self.wp_panel, bg=COLOR_PANEL)
        self.wp_info_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 6))
        self.wp_info_scroll = tk.Scrollbar(self.wp_info_wrap, orient=tk.VERTICAL)
        self.wp_info_text = tk.Text(
            self.wp_info_wrap,
            bg=COLOR_PANEL,
            fg="#aaa",
            font=("Courier", 8),
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

        side_actions = tk.Frame(self.side, bg=COLOR_PANEL)
        side_actions.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        tk.Button(side_actions, text="[ REBUILD CACHE ]", command=self.scan_all_logs_threaded, bg=COLOR_PANEL, fg="#777", font=("Courier", 8, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_TEXT).pack(side=tk.LEFT)
        tk.Label(side_actions, text="© 2026 insert3coins", font=("Courier", 8), fg="#444", bg=COLOR_PANEL).pack(side=tk.RIGHT)

        center = tk.Frame(body, bg=COLOR_BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ops = tk.Frame(center, bg=COLOR_BG)
        ops.pack(fill=tk.X)
        for col in range(3):
            ops.grid_columnconfigure(col, weight=1)

        self.card_nav = self._build_ops_card(ops, "NAVIGATION", 0, 0)
        self.card_scan = self._build_ops_card(ops, "SCANNING", 0, 1)
        self.card_system = self._build_ops_card(ops, "SYSTEM INTEL", 0, 2)
        self.card_value = self._build_ops_card(ops, "ECONOMY", 1, 0)
        self.card_session = self._build_ops_card(ops, "SESSION", 1, 1)
        self.card_ops = self._build_ops_card(ops, "OPERATIONS", 1, 2)

        self.details_drawer = tk.Frame(center, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        self.details_drawer.pack(fill=tk.X, pady=(10, 8))
        feed_wrap = tk.Frame(self.details_drawer, bg=COLOR_PANEL)
        feed_wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        tk.Label(feed_wrap, text="EVENT FEED", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w")
        self.event_filter_row = tk.Frame(feed_wrap, bg=COLOR_PANEL)
        self.event_filter_row.pack(fill=tk.X, pady=(4, 2))
        self.event_filter_buttons = {}
        for tag in ("ALL", "VALUABLE", "SCAN", "ALERT", "JUMP", "ROUTE", "SYSTEM", "DSS", "INFO"):
            btn = tk.Button(
                self.event_filter_row,
                text=f"[ {tag} ]",
                command=lambda t=tag: self.set_event_feed_filter(t),
                bg=COLOR_PANEL,
                fg=COLOR_TEXT if tag == "ALL" else "#888",
                font=("Courier", 8, "bold"),
                relief=tk.FLAT,
                activebackground=COLOR_PANEL,
                activeforeground=COLOR_ACCENT,
            )
            btn.pack(side=tk.LEFT, padx=(0, 2))
            self.event_filter_buttons[tag] = btn
        self.event_feed_list = tk.Listbox(
            feed_wrap,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            font=("Courier", 9),
            height=8,
            relief=tk.FLAT,
            highlightthickness=0,
            borderwidth=0,
        )
        self.event_feed_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.event_feed_list.bind("<Button-1>", lambda e: "break")
        self.event_feed_list.bind("<Double-Button-1>", lambda e: "break")

        log_frame = tk.Frame(center, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_toolbar = tk.Frame(log_frame, bg=COLOR_PANEL)
        log_toolbar.pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(log_toolbar, text="CONSOLE LOG", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT)
        self.log_box = scrolledtext.ScrolledText(log_frame, bg="#000", fg=COLOR_GREEN, font=("Courier", 10), borderwidth=0)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.ground_lat_entry.delete(0, tk.END)
        self.ground_lon_entry.delete(0, tk.END)
        self.ground_lat_entry.insert(0, f"{getattr(self, 'target_lat', 0.0):.6f}")
        self.ground_lon_entry.insert(0, f"{getattr(self, 'target_lon', 0.0):.6f}")

    def create_stat(self, parent, label, val):
        tk.Label(parent, text=label, font=("Courier", 8), fg="#666", bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(8, 0))
        l = tk.Label(parent, text=val, font=("Courier", 10, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL)
        l.pack(anchor="w", padx=10)
        return l

    def _build_ops_card(self, parent, title, row, col):
        card = tk.Frame(parent, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        tk.Label(card, text=title, font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 0))
        line1 = tk.Label(card, text="-", font=("Courier", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
        line1.pack(fill=tk.X, padx=10, pady=(4, 0))
        line2 = tk.Label(card, text="-", font=("Courier", 8), fg="#aaa", bg=COLOR_PANEL, anchor="w")
        line2.pack(fill=tk.X, padx=10, pady=(2, 0))
        line3 = tk.Label(card, text="-", font=("Courier", 8), fg="#888", bg=COLOR_PANEL, anchor="w")
        line3.pack(fill=tk.X, padx=10, pady=(2, 8))
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
                btn.config(fg=COLOR_TEXT if tag == mode else "#888")
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

    def _refresh_event_feed(self):
        if not hasattr(self, "event_feed_list"):
            return

        visible = [e for e in self.event_feed_entries if self._event_feed_matches_filter(e)]
        pinned = [e for e in visible if e.get("pinned")]
        unpinned = [e for e in visible if not e.get("pinned")]
        rows = pinned + unpinned
        rows = rows[:self.event_feed_display_limit]
        self.event_feed_view = rows

        self.event_feed_list.delete(0, tk.END)
        for row in rows:
            ts_txt = datetime.fromtimestamp(row.get("ts", time.time())).strftime("%H:%M:%S")
            pin_prefix = "📌 " if row.get("pinned") else ""
            line = f"[{ts_txt}] {pin_prefix}[{row.get('tag', 'INFO')}] {row.get('message', '')}"
            self.event_feed_list.insert(tk.END, line)
            idx = self.event_feed_list.size() - 1
            self.event_feed_list.itemconfig(idx, fg=self._event_feed_row_color(row))

    def _copy_selected_event_feed(self):
        if not hasattr(self, "event_feed_list"):
            return
        sel = self.event_feed_list.curselection()
        if not sel:
            return
        idx = sel[0]
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
        sel = self.event_feed_list.curselection()
        if not sel:
            return
        idx = sel[0]
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
            or "DISCORD INTEGRATION" in upper
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
            or "STALE DISCORD MESSAGE" in upper
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
        self._refresh_event_feed()
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
        btn = tk.Button(self.nav, text="[ UPDATE AVAILABLE ]", command=lambda: webbrowser.open(url), bg=COLOR_PANEL, fg=COLOR_GREEN, font=("Courier", 9, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_GREEN)
        btn.pack(side=tk.RIGHT, padx=5)

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
                text="[ POPUP: ON ]" if self.ground_popup_enabled else "[ POPUP: OFF ]",
                fg=COLOR_TEXT if self.ground_popup_enabled else "#888",
            )
        if not self.ground_popup_enabled and self.ground_popup and self.ground_popup.winfo_exists():
            self.ground_popup.withdraw()
            self._ground_popup_visible = False
        self.update_ground_target_ui()

    def toggle_bio_estimate_popup(self):
        enabled = not bool(self.config.get("bio_estimate_popup_enabled", True))
        self.config["bio_estimate_popup_enabled"] = enabled
        if hasattr(self, "bio_popup") and self.bio_popup:
            self.bio_popup.set_enabled(enabled)
        self._save_config_file()
        if hasattr(self, "bio_popup_toggle_btn"):
            self.bio_popup_toggle_btn.config(
                text="[ ON ]" if enabled else "[ OFF ]",
                fg=COLOR_TEXT if enabled else "#888",
            )
        self.update_bio_estimate_popup()

    def _build_bio_estimate_model(self):
        # SrvSurvey-style values: use Codex reward tables instead of user-entered knobs.
        reward_catalog = load_bio_reward_catalog()
        ff_mult = 5.0

        species_by_body = {}
        completed_by_body = {}
        for entry in getattr(self, "last_bio_scan", {}).values():
            body_label = entry.get("body_name") or (f"Body {entry.get('body_id')}" if entry.get("body_id") is not None else "Body")
            species_name = entry.get("species") or "Organic"
            genus_name = entry.get("genus")
            is_complete = bool(entry.get("is_complete"))
            reward = entry.get("reward")
            if not isinstance(reward, (int, float)):
                reward = 0
            reward = int(reward)

            body_species = species_by_body.setdefault(body_label, {})
            current = body_species.get(species_name)
            # Keep the highest-value snapshot for a species in case of repeat events.
            if current is None or reward >= int(current.get("actual", 0)):
                body_species[species_name] = {
                    "name": species_name,
                    "genus": genus_name,
                    "is_complete": is_complete,
                    "actual": reward if is_complete else 0,
                    "reward_hint": reward if reward > 0 else int(current.get("reward_hint", 0) if current else 0),
                }

            if is_complete:
                payload = completed_by_body.setdefault(body_label, {"count": 0, "actual": 0})
                payload["count"] += 1
                payload["actual"] += reward

        bodies = []
        total_signals = 0
        scanned_signals = 0
        actual_value = 0
        est_min = 0
        est_max = 0
        est_ff_min = 0
        est_ff_max = 0
        for item in getattr(self, "scan_items", []) or []:
            signals = int(item.get("bio_count", 0) or 0)
            if signals <= 0:
                continue
            full_name = item.get("full_name") or ""
            short_name = item.get("name") or ""
            body_name = full_name or short_name or f"Body {item.get('body_id')}"
            first_footfall = bool(item.get("first_footfall", False))
            done = (
                completed_by_body.get(body_name)
                or completed_by_body.get(short_name)
                or completed_by_body.get(full_name)
                or {"count": 0, "actual": 0}
            )
            body_species_rows = (
                species_by_body.get(body_name)
                or species_by_body.get(short_name)
                or species_by_body.get(full_name)
                or {}
            )
            known_slots = min(signals, len(body_species_rows))
            scanned = min(signals, int(done.get("count", 0)))
            pending = max(signals - known_slots, 0)
            body_actual = int(done.get("actual", 0))
            body_est_min = 0
            body_est_max = 0
            body_est_min_ff = 0
            body_est_max_ff = 0

            total_signals += signals
            scanned_signals += scanned
            actual_value += body_actual

            species_rows = []
            for sp in sorted(body_species_rows.values(), key=lambda x: x.get("name", "")):
                sp_actual = int(sp.get("actual", 0) or 0)
                sp_is_complete = bool(sp.get("is_complete"))
                sp_name = sp.get("name", "Species")
                sp_genus = sp.get("genus")
                sp_hint = int(sp.get("reward_hint", 0) or 0)
                if sp_is_complete:
                    sp_est_min = sp_actual
                    sp_est_max = sp_actual
                    sp_est_min_ff = sp_actual
                    sp_est_max_ff = sp_actual
                elif sp_hint > 0:
                    sp_est_min = sp_hint
                    sp_est_max = sp_hint
                    if first_footfall:
                        sp_est_min_ff = int(sp_hint * ff_mult)
                        sp_est_max_ff = int(sp_hint * ff_mult)
                    else:
                        sp_est_min_ff = sp_hint
                        sp_est_max_ff = sp_hint
                else:
                    sp_est_min, sp_est_max = reward_catalog.species_range(sp_name, sp_genus)
                    if first_footfall:
                        sp_est_min_ff = int(sp_est_min * ff_mult)
                        sp_est_max_ff = int(sp_est_max * ff_mult)
                    else:
                        sp_est_min_ff = sp_est_min
                        sp_est_max_ff = sp_est_max
                body_est_min += sp_est_min
                body_est_max += sp_est_max
                body_est_min_ff += sp_est_min_ff
                body_est_max_ff += sp_est_max_ff
                species_rows.append(
                    {
                        "name": sp_name,
                        "is_complete": sp_is_complete,
                        "actual": sp_actual,
                        "est_min": sp_est_min,
                        "est_max": sp_est_max,
                        "est_min_ff": sp_est_min_ff,
                        "est_max_ff": sp_est_max_ff,
                    }
                )

            if pending > 0:
                genus_hints = item.get("bio_genuses") or []
                if genus_hints:
                    # Use SrvSurvey genus reward bands when DSS provides genus list.
                    ranges = [reward_catalog.genus_range(g) for g in genus_hints]
                    unk_min = min(r[0] for r in ranges)
                    unk_max = max(r[1] for r in ranges)
                else:
                    unk_min, unk_max = reward_catalog.genus_range(None)
                body_est_min += pending * unk_min
                body_est_max += pending * unk_max
                if first_footfall:
                    body_est_min_ff += int(pending * unk_min * ff_mult)
                    body_est_max_ff += int(pending * unk_max * ff_mult)
                else:
                    body_est_min_ff += pending * unk_min
                    body_est_max_ff += pending * unk_max

            est_min += body_est_min
            est_max += body_est_max
            est_ff_min += body_est_min_ff
            est_ff_max += body_est_max_ff

            bodies.append(
                {
                    "body_id": item.get("body_id"),
                    "name": body_name,
                    "signals": signals,
                    "scanned": scanned,
                    "actual": body_actual,
                    "est_min": body_est_min,
                    "est_max": body_est_max,
                    "est_min_ff": body_est_min_ff,
                    "est_max_ff": body_est_max_ff,
                    "first_footfall": first_footfall,
                    "species": species_rows,
                }
            )
        return {
            "system_name": self.current_sys,
            "signals_scanned": scanned_signals,
            "total_signals": total_signals,
            "actual_value": actual_value,
            "est_min": est_min,
            "est_max": est_max,
            "est_ff_min": est_ff_min,
            "est_ff_max": est_ff_max,
            "bodies": bodies,
        }

    def update_bio_estimate_popup(self):
        if not hasattr(self, "bio_popup") or not self.bio_popup:
            return
        if not bool(self.config.get("bio_estimate_popup_enabled", True)):
            self.bio_popup.hide()
            return
        model = self._build_bio_estimate_model()
        if not self._bio_popup_allowed(model):
            self.bio_popup.hide()
            return
        self.bio_popup.update(model)

    def _bio_popup_allowed(self, model):
        # Approximate SrvSurvey PlotBioSystem.allowed(...) using our available status fields.
        if not model or int(model.get("total_signals", 0) or 0) <= 0:
            return False

        flags = int(getattr(self, "last_status_flags", 0) or 0)
        flags2 = int(getattr(self, "last_status_flags2", 0) or 0)
        gui_focus = getattr(self, "last_gui_focus", -1)

        # Status flags (Elite Dangerous Status.json)
        is_in_taxi = bool(flags2 & (1 << 1))
        on_foot_in_station = bool(flags2 & (1 << 3))
        on_foot_in_hangar = bool(flags2 & (1 << 13))
        on_foot_social = bool(flags2 & (1 << 14))
        is_docked = bool(flags & (1 << 0))
        in_supercruise = bool(flags & (1 << 4))

        if is_in_taxi:
            return False

        # Identify if the current body has bio signals (SrvSurvey target-body behavior).
        current_body = (getattr(self, "current_body_name", None) or "").strip()
        current_has_bio = False
        if current_body:
            for body in model.get("bodies", []):
                body_name = str(body.get("name", "") or "").strip()
                if body_name == current_body or body_name.endswith(current_body) or current_body.endswith(body_name):
                    if int(body.get("signals", 0) or 0) > 0:
                        current_has_bio = True
                        break

        # GUI focus values: we only explicitly know FSS=9.
        in_fss = bool(getattr(self, "in_fss", False)) or gui_focus == 9 or gui_focus == "FSS"
        in_map_like = gui_focus in (2, 3, 4, 7, 8, 10)

        # Closest practical mapping to SrvSurvey:
        # show in SC/FSS/map-like contexts, or when on/near a target body with bio signals.
        if in_supercruise or in_fss or in_map_like:
            return True

        if current_has_bio:
            return True

        # Suppress while effectively in station/social spaces.
        if is_docked or on_foot_in_station or on_foot_in_hangar or on_foot_social:
            return False

        # Fallback: if on planet with target/body context, allow.
        if bool(getattr(self, "on_planet", False)):
            return current_has_bio

        return True

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
        self.ground_popup.configure(bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        self.ground_popup.geometry(self.config.get("ground_popup_geometry", "340x140+1320+160"))
        self.ground_popup.minsize(300, 132)

        title = tk.Frame(self.ground_popup, bg="#171717", height=22)
        title.pack(fill=tk.X)
        title.pack_propagate(False)
        self.ground_popup_header = tk.Label(title, text="GROUND TARGET  [DRAG]", font=("Courier", 8, "bold"), fg=COLOR_ORANGE, bg="#171717", anchor="w")
        self.ground_popup_header.pack(fill=tk.BOTH, expand=True, padx=8)

        frame = tk.Frame(self.ground_popup, bg=COLOR_PANEL)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 6))

        left = tk.Frame(frame, bg=COLOR_PANEL, width=96, height=96)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        self.ground_popup_canvas = tk.Canvas(left, width=96, height=96, bg=COLOR_PANEL, highlightthickness=0, bd=0)
        self.ground_popup_canvas.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(frame, bg=COLOR_PANEL)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        self.ground_popup_line1 = tk.Label(right, text="-", font=("Courier", 11, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL, anchor="w")
        self.ground_popup_line1.pack(fill=tk.X, pady=(2, 0))
        self.ground_popup_line2 = tk.Label(right, text="-", font=("Courier", 9), fg=COLOR_TEXT, bg=COLOR_PANEL, anchor="w")
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
            n = canvas.create_text(cx, cy - r - 4, text="N", fill="#999", font=("Courier", 8, "bold"))
            e = canvas.create_text(cx + r + 5, cy, text="E", fill="#666", font=("Courier", 7))
            s = canvas.create_text(cx, cy + r + 6, text="S", fill="#666", font=("Courier", 7))
            w_txt = canvas.create_text(cx - r - 5, cy, text="W", fill="#666", font=("Courier", 7))
            # Ship forward marker is always up in this relative compass.
            ship = canvas.create_line(cx, cy + 2, cx, cy - r + 8, fill="#777", width=2)
            needle = canvas.create_line(cx, cy, cx, cy, fill=COLOR_ACCENT, width=3)
            dot = canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
            unknown = canvas.create_text(cx, cy, text="?", fill="#888", font=("Courier", 14, "bold"), state="hidden")
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
                text="[ POPUP: ON ]" if self.ground_popup_enabled else "[ POPUP: OFF ]",
                fg=COLOR_TEXT if self.ground_popup_enabled else "#888",
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
        discord_master = self.config.get("discord_enabled", True) and self.config.get("discord_webhook")
        any_discord_channel = self.config.get("discord_live_enabled", True) or self.config.get("discord_fleet_enabled", True)
        disc_on = "ON" if (discord_master and any_discord_channel) else "OFF"
        shots_on = "ON" if self.config.get("screenshots_enabled", False) else "OFF"
        self.integration_lbl.config(text=f"HUD: {hud_on} | DISCORD: {disc_on} | SHOTS: {shots_on}")

        alerts = []
        if self.system_undiscovered:
            alerts.append("UNDISCOVERED SYSTEM")
        if self.system_bio_signals > 0:
            alerts.append(f"BIO SIGNALS: {self.system_bio_signals}")
        if self.valuable_bodies:
            alerts.append(f"VALUABLE FINDS: {len(self.valuable_bodies)}")
        if self.fss_summary_active:
            alerts.append("FSS SUMMARY ACTIVE")
        self.alert_lbl.config(text=" | ".join(alerts) if alerts else "NONE")

        planner_open = "YES" if (self.route_plotter and self.route_plotter.win.winfo_exists()) else "NO"
        auto_copy = "ON" if self.config.get("auto_copy_waypoint", False) else "OFF"
        self.card_ops.line1.config(text=f"Waypoints: {route_total} | Pending: {max(route_total - route_visited, 0)}")
        self.card_ops.line2.config(text=f"Next WP: {next_waypoint_name}")
        self.card_ops.line3.config(text=f"Auto-Copy: {auto_copy} | Planner Open: {planner_open}")

        self.update_bio_estimate_popup()
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

