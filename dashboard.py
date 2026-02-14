import os
import json
import threading
import math
import sqlite3
import logging
import time
import tkinter as tk
import requests
import webbrowser
from datetime import datetime
from tkinter import scrolledtext

from config import (
    load_config, CONFIG_FILE,
    COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, COLOR_GREEN
)
from version import APP_VERSION
from hud import TacticalHUD
from cargo_hud import CargoHUD
from scan_hud import ScanHUD
from edsm_handler import EDSMHandler
from discord_handler import DiscordHandler
from screenshot_handler import ScreenshotHandler
from settings_ui import open_settings
from route_plotter import RoutePlotter
from waypoint_manager import WaypointManager
from journal_watcher import JournalWatcher

SCAN_HISTORY_FILE = "scan_history.json"
DB_FILE = "exploration_data.db"
SCAN_CACHE_FILE = "scan_cache.json"

class MainDashboard:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.root.title(f"VOID COMPASS // v{APP_VERSION}")
        self.root.geometry(self.config.get("main_geometry", "1000x700"))
        self.root.configure(bg=COLOR_BG)
        
        self.is_running = True
        self.is_first_load = True
        
        self.current_sys = "---"
        self.star_class = ""
        self.scanned = 0
        self.total = 0
        self.organic_count = 0
        self.system_bio_signals = 0
        self.system_traffic = {'day': 0, 'week': 0, 'total': 0}
        self.last_traffic_system = None
        self.valuable_system = False
        self.valuable_bodies = []
        self.scanned_bodies = set()
        self.scan_items = []
        self.scan_items_by_id = {}
        self.in_fss = False
        self.scan_hud_hide_job = None
        self.scan_hud_hide_delay_ms = 30000
        self.fss_summary_active = False
        self.body_signals = {}
        self.body_dss_complete = set()
        self.system_undiscovered = False
        self.fss_all_bodies = False
        self.cmdr_name = "CMDR"
        self.last_scan_event = None
        self.cargo_capacity = 0
        
        self.dest_coords = None
        self.current_coords = [0,0,0]
        self.dest_name = None
        self.route_list = []
        self.session_start_ts = time.time()
        self.session_jump_count = 0
        self.session_ly = 0.0
        self.log_filter = "ALL"
        self.log_entries = []
        self.details_visible = True
        self.dashboard_refresh_job = None
        self.dashboard_refresh_full_pending = False
        
        self.setup_layout()
        self.waypoint_manager = WaypointManager()
        self.route_plotter = None
        self.target_waypoint = None
        self.waypoint_cache = {}
        
        # Initialize Handlers
        self.edsm = EDSMHandler(self.config)
        self.discord = DiscordHandler(self.config, self.root)
        self.screenshots = ScreenshotHandler(self.config, lambda: self.current_sys, self.log)
        
        if self.config.get("overlay_enabled", True):
            self.hud = TacticalHUD(self.root, self.config)
        else:
            self.hud = None
            
        if self.config.get("cargo_overlay_enabled", False):
            self.cargo_hud = CargoHUD(self.root, self.config)
        else:
            self.cargo_hud = None

        if self.config.get("scan_overlay_enabled", True):
            self.scan_hud = ScanHUD(self.root, self.config)
            self.scan_hud.hide()
        else:
            self.scan_hud = None

        
        self.db_lock = threading.RLock()
        self.batch_mode = False
        self.init_db()
        self.import_scan_cache_json()
        
        self.watcher = JournalWatcher(self.config.get("journal_path"))
        self.watcher.register_callback(
            event_cb=self.process_event,
            batch_cb=self.process_batch,
            cargo_cb=self.update_cargo,
            nav_cb=self.update_nav_route,
            status_cb=self.update_status
        )
        self.watcher.start()
        
        self.watcher.force_check_status()
        
        threading.Thread(target=self.check_updates, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_hud()
        self._tick_session_clock()

    def init_db(self):
        """Initialize SQLite database and migrate JSON if needed."""
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        with self.db_lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous = FULL")
            self.conn.execute("CREATE TABLE IF NOT EXISTS systems (name TEXT PRIMARY KEY, total INTEGER, scanned_count INTEGER)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS bodies (system_name TEXT, body_id INTEGER, PRIMARY KEY (system_name, body_id))")
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS scan_hud_items (system_name TEXT, body_id INTEGER, data_json TEXT, ts INTEGER, PRIMARY KEY (system_name, body_id))"
            )
            self.conn.commit()
        
        if os.path.exists(SCAN_HISTORY_FILE):
            self.migrate_json_history()

    def import_scan_cache_json(self):
        if not os.path.exists(SCAN_CACHE_FILE):
            return
        try:
            with open(SCAN_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        now = int(time.time())
        with self.db_lock:
            try:
                self.conn.execute("BEGIN TRANSACTION")
                for system_name, items in data.items():
                    if not isinstance(items, list):
                        continue
                    for idx, item in enumerate(items):
                        if not isinstance(item, dict):
                            continue
                        body_id = item.get("body_id")
                        if body_id is None:
                            continue
                        ts = item.get("_ts")
                        if not isinstance(ts, int):
                            ts = now - idx
                            item["_ts"] = ts
                        payload = json.dumps(item)
                        self.conn.execute(
                            "INSERT OR REPLACE INTO scan_hud_items (system_name, body_id, data_json, ts) VALUES (?, ?, ?, ?)",
                            (system_name, int(body_id), payload, int(ts))
                        )
                self.conn.commit()
            except sqlite3.Error:
                self.conn.rollback()
                return

        try:
            os.rename(SCAN_CACHE_FILE, SCAN_CACHE_FILE + ".bak")
        except Exception:
            pass

    def load_scan_items_from_db(self, system_name):
        items = []
        with self.db_lock:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT data_json FROM scan_hud_items WHERE system_name=? ORDER BY ts DESC LIMIT 60",
                    (system_name,)
                )
                rows = cur.fetchall()
                for (data_json,) in rows:
                    try:
                        item = json.loads(data_json)
                        if isinstance(item, dict):
                            items.append(item)
                    except Exception:
                        pass
            except sqlite3.Error:
                return []
        return items

    def save_scan_item_to_db(self, system_name, item):
        try:
            body_id = item.get("body_id")
            ts = item.get("_ts")
            if body_id is None or ts is None:
                return
            payload = json.dumps(item)
            with self.db_lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO scan_hud_items (system_name, body_id, data_json, ts) VALUES (?, ?, ?, ?)",
                    (system_name, int(body_id), payload, int(ts))
                )
                if not self.batch_mode:
                    self.conn.commit()
        except sqlite3.Error:
            return

    def migrate_json_history(self):
        self.log("📦 MIGRATING HISTORY TO DATABASE...")
        try:
            with open(SCAN_HISTORY_FILE, 'r') as f:
                data = json.load(f)
            
            with self.db_lock:
                try:
                    self.conn.execute("BEGIN TRANSACTION")
                    for sys_name, info in data.items():
                        total = info.get("total", 0)
                        bodies = info.get("bodies", [])
                        scanned_count = info.get("scanned_count", len(bodies))
                        
                        self.conn.execute("INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)", (sys_name, total, scanned_count))
                        for bid in bodies:
                            self.conn.execute("INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)", (sys_name, bid))
                    self.conn.commit()
                except sqlite3.Error:
                    self.conn.rollback()
                    raise
            
            os.rename(SCAN_HISTORY_FILE, SCAN_HISTORY_FILE + ".bak")
            self.log("✅ MIGRATION COMPLETE.")
        except Exception as e:
            self.log(f"❌ MIGRATION FAILED: {e}")

    def setup_layout(self):
        self.nav = tk.Frame(self.root, bg=COLOR_PANEL, height=50, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        self.nav.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        tk.Label(self.nav, text=f" > VOID COMPASS // V{APP_VERSION}", font=("Courier", 11, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=15)
        
        btn_conf = tk.Button(self.nav, text="[ CONFIGURATION ]", command=self.open_settings, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_conf.pack(side=tk.RIGHT, padx=15)

        # Route Button
        btn_route = tk.Button(self.nav, text="[ ROUTE PLANNER ]", command=self.open_route_planner, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_route.pack(side=tk.RIGHT, padx=5)
        
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

        self.wp_panel = tk.Frame(self.side, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1, height=110)
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
            height=3
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

        self.details_toggle = tk.Button(center, text="[ DETAILS: VISIBLE ]", command=self.toggle_details, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 8, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_ACCENT)
        self.details_toggle.pack(anchor="w", pady=(10, 4))

        self.details_drawer = tk.Frame(center, bg=COLOR_PANEL, highlightbackground="#333", highlightthickness=1)
        self.details_drawer.pack(fill=tk.X, pady=(0, 8))
        self.details_drawer.grid_columnconfigure(0, weight=1)
        self.details_drawer.grid_columnconfigure(1, weight=1)

        vf_wrap = tk.Frame(self.details_drawer, bg=COLOR_PANEL)
        vf_wrap.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        tk.Label(vf_wrap, text="VALUABLE FINDS", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w")
        self.valuable_list = tk.Listbox(vf_wrap, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9), height=7, relief=tk.FLAT, highlightthickness=0, borderwidth=0)
        self.valuable_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        rd_wrap = tk.Frame(self.details_drawer, bg=COLOR_PANEL)
        rd_wrap.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        tk.Label(rd_wrap, text="RECENT DISCOVERIES", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(anchor="w")
        self.recent_list = tk.Listbox(rd_wrap, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9), height=7, relief=tk.FLAT, highlightthickness=0, borderwidth=0)
        self.recent_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        log_frame = tk.Frame(center, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_toolbar = tk.Frame(log_frame, bg=COLOR_PANEL)
        log_toolbar.pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(log_toolbar, text="ACTIVITY LOG", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT)
        for tag in ("ALL", "JUMP", "SCAN", "ALERT", "ERROR"):
            tk.Button(log_toolbar, text=f"[ {tag} ]", command=lambda t=tag: self.set_log_filter(t), bg=COLOR_PANEL, fg=COLOR_TEXT if tag == "ALL" else "#888", font=("Courier", 8, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_ACCENT).pack(side=tk.RIGHT, padx=2)
        self.log_box = scrolledtext.ScrolledText(log_frame, bg="#000", fg=COLOR_GREEN, font=("Courier", 10), borderwidth=0)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.log_entries.append(line)
        self.root.after(0, self._refresh_log_view)

    def toggle_details(self):
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.details_drawer.pack(fill=tk.X, pady=(0, 8))
            self.details_toggle.config(text="[ DETAILS: VISIBLE ]")
        else:
            self.details_drawer.pack_forget()
            self.details_toggle.config(text="[ DETAILS: HIDDEN ]")

    def schedule_dashboard_refresh(self, full=False):
        if full:
            self.dashboard_refresh_full_pending = True
        if self.dashboard_refresh_job is None:
            self.dashboard_refresh_job = self.root.after(120, self._run_scheduled_dashboard_refresh)

    def _run_scheduled_dashboard_refresh(self):
        self.dashboard_refresh_job = None
        if self.dashboard_refresh_full_pending:
            self.dashboard_refresh_full_pending = False
            self.update_dashboard_ui()
        else:
            self.update_dashboard_panels()

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

    def scan_all_logs_threaded(self):
        threading.Thread(target=self.scan_all_logs, daemon=True).start()

    def scan_all_logs(self):
        self.log("📚 STARTING HISTORY REBUILD...")
        
        new_history = self.watcher.scan_history(lambda p, t: self.log(f"⏳ Scanning... {int((p/t)*100)}%"))
        
        if not new_history:
            self.log("⚠️ No history found or scan failed.")
            return

        self.log("💾 Saving to database...")
        with self.db_lock:
            try:
                self.conn.execute("BEGIN TRANSACTION")
                for sys_name, data in new_history.items():
                    b_len = len(data.get("bodies", []))
                    if b_len > data.get("scanned_count", 0): data["scanned_count"] = b_len
                    if data.get("scanned_count", 0) > data.get("total", 0): data["total"] = data["scanned_count"]
                    
                    self.conn.execute("INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)", 
                                      (sys_name, data["total"], data["scanned_count"]))
                    for b in data.get("bodies", []):
                        self.conn.execute("INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)", (sys_name, b))
                self.conn.commit()
            except sqlite3.Error as e:
                self.conn.rollback()
                self.log(f"❌ DB ERROR (Rebuild): {e}")

        self.log(f"✅ CACHE REBUILD COMPLETE.")
        self.load_system_from_db(self.current_sys)
        self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
        self.update_hud()

    def load_system_from_db(self, sys_name):
        with self.db_lock:
            try:
                c = self.conn.cursor()
                c.execute("SELECT total, scanned_count FROM systems WHERE name=?", (sys_name,))
                row = c.fetchone()
                if row:
                    self.total = row[0]
                    c.execute("SELECT body_id FROM bodies WHERE system_name=?", (sys_name,))
                    self.scanned_bodies = set(r[0] for r in c.fetchall())
                    self.scanned = len(self.scanned_bodies)
                else:
                    self.total = 0
                    self.scanned = 0
                    self.scanned_bodies = set()
            except sqlite3.Error as e:
                self.log(f"❌ DB READ ERROR: {e}")
                self.total = 0
                self.scanned = 0
                self.scanned_bodies = set()

    def db_update_system(self, sys_name, total, scanned):
        with self.db_lock:
            try:
                self.conn.execute("INSERT OR REPLACE INTO systems (name, total, scanned_count) VALUES (?, ?, ?)", (sys_name, total, scanned))
                if not self.batch_mode:
                    self.conn.commit()
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (System): {e}")

    def db_add_body(self, sys_name, body_id):
        with self.db_lock:
            try:
                self.conn.execute("INSERT OR IGNORE INTO bodies (system_name, body_id) VALUES (?, ?)", (sys_name, body_id))
                if not self.batch_mode:
                    self.conn.commit()
            except sqlite3.Error as e:
                self.log(f"❌ DB ERROR (Body): {e}")

    def update_nav_label(self):
        txt = "NO ROUTE"
        if self.dest_name:
            txt = self.dest_name
        
        if not self.batch_mode:
            self.root.after(0, lambda: self.nav_stat.config(text=txt))

    def update_dashboard_panels(self):
        """Refresh dashboard cards/summary without waypoint recompute."""
        sys_text = self.current_sys.upper()
        if self.star_class: sys_text += f" [{self.star_class}]"
        
        self.sys_stat.config(text=sys_text)
        self.scan_stat.config(text=f"{self.scanned} / {self.total}")
        self.update_nav_label()

        route_text = "INACTIVE"
        if self.waypoint_manager.waypoints:
            total_wp = len(self.waypoint_manager.waypoints)
            visited = sum(1 for wp in self.waypoint_manager.waypoints if wp.get("visited", False))
            route_text = f"{visited}/{total_wp}"

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
        disc_on = "ON" if (self.config.get("discord_enabled", True) and self.config.get("discord_webhook")) else "OFF"
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

        self.card_ops.line1.config(text=f"Undiscovered System: {'YES' if self.system_undiscovered else 'NO'}")
        self.card_ops.line2.config(text=f"HUD: {hud_on} | DISCORD: {disc_on}")
        self.card_ops.line3.config(text=f"SHOTS: {shots_on} | Alerts: {len(alerts)}")

        self.valuable_list.delete(0, tk.END)
        for item in self.valuable_bodies:
            display_text = item[2:] if item.startswith("- ") else item
            self.valuable_list.insert(tk.END, display_text)

        self.recent_list.delete(0, tk.END)
        for item in self.scan_items[:10]:
            nm = item.get("name", "Unknown")
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            reward_txt = self._format_credits(reward, hide_units=True)
            self.recent_list.insert(tk.END, f"{nm}  [{reward_txt}]")

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
            for i in range(idx + 1):
                if not self.waypoint_manager.waypoints[i].get('visited', False):
                    self.waypoint_manager.waypoints[i]['visited'] = True
                    changed = True
            if changed:
                self.waypoint_manager.save()

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

    def on_close(self):
        """Save state and exit."""
        self.is_running = False
        
        if self.route_plotter and self.route_plotter.win.winfo_exists():
            self.route_plotter.on_close()
            
        self.watcher.stop()
        self.screenshots.stop()
        self.config["main_geometry"] = self.root.geometry()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        if hasattr(self, 'conn'):
            try:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.conn.close()
            except: pass
        self.root.destroy()

    def open_screenshots_folder(self):
        path = self.config.get("screenshots_path")
        if not path:
            path = os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous")
            
        if os.path.exists(path):
            try:
                os.startfile(path)
            except AttributeError:
                webbrowser.open(path)
            except Exception as e:
                self.log(f"❌ Error opening folder: {e}")
        else:
            self.log("⚠️ Screenshot folder not found.")

    def open_route_planner(self):
        if self.route_plotter and self.route_plotter.win.winfo_exists():
            self.route_plotter.win.lift()
            return
        self.route_plotter = RoutePlotter(self.root, self.edsm, self.current_coords, self.current_sys, self.config, self.waypoint_manager, on_change_callback=self.update_waypoint_display)

    def open_settings(self):
        def on_save():
            self.log("Configuration saved successfully.")

            # Live Update: Discord
            discord_active = self.config.get("discord_enabled", True) and self.config.get("discord_webhook")
            if discord_active:
                self.log("Discord Integration: ACTIVE")
            else:
                self.log("Discord Integration: DISABLED")

            # Live Update: Screenshots
            if self.config.get("screenshots_enabled", False):
                self.log("Screenshot Converter: ACTIVE")
            else:
                self.log("Screenshot Converter: DISABLED")

            # Live Toggle: Tactical HUD
            if self.config.get("overlay_enabled", True):
                if self.hud is None:
                    self.hud = TacticalHUD(self.root, self.config)
                self.update_hud()
            else:
                if self.hud:
                    self.hud.win.destroy()
                    self.hud = None

            # Live Toggle: Cargo HUD
            if self.config.get("cargo_overlay_enabled", False):
                if self.cargo_hud is None:
                    self.cargo_hud = CargoHUD(self.root, self.config)
                    self.watcher.force_check_cargo()
            else:
                if self.cargo_hud:
                    self.cargo_hud.win.destroy()
                    self.cargo_hud = None

            # Live Toggle: Scan HUD
            if self.config.get("scan_overlay_enabled", True):
                if self.scan_hud is None:
                    self.scan_hud = ScanHUD(self.root, self.config)
                self.update_scan_hud()
            else:
                if self.scan_hud:
                    self.scan_hud.win.destroy()
                    self.scan_hud = None

        
        open_settings(self.root, self.config, on_save)

    def update_live_discord(self, event_data=None):
        if self.is_first_load:
            return
        state = {
            "current_sys": self.current_sys,
            "star_class": self.star_class,
            "scanned": self.scanned,
            "total": self.total,
            "organic_count": self.organic_count,
            "valuable_bodies": self.valuable_bodies,
            "system_traffic": self.system_traffic,
            "dest_name": self.dest_name,
            "dest_coords": self.dest_coords,
            "current_coords": self.current_coords,
            "cmdr_name": self.cmdr_name,
            "valuable_system": self.valuable_system
        }
        self.discord.update_live(event_data, state)

    def fetch_system_traffic(self, system_name):
        def callback(traffic_data):
            def _apply():
                if self.current_sys != system_name:
                    return
                self.system_traffic = traffic_data
                self.update_dashboard_ui()
                self.update_hud()
                self.update_live_discord()
            self.root.after(0, _apply)
        
        self.edsm.fetch_traffic(system_name, callback)

    def update_hud(self):
        """Gathers all current state and sends it to the HUD for redrawing."""
        if not self.hud:
            self.update_scan_hud()
            return

        dist = "---"
        if self.dest_coords:
            try:
                d = math.sqrt(sum((a-b)**2 for a,b in zip(self.current_coords, self.dest_coords)))
                dist = f"{d:,.1f} LY"
            except Exception:
                pass
        
        custom_r_pos = None
        
        if self.waypoint_manager.waypoints:
            total_wp = len(self.waypoint_manager.waypoints)
            
            visited_count = sum(1 for wp in self.waypoint_manager.waypoints if wp.get('visited', False))
            step = visited_count + 1
            if step > total_wp: step = total_wp
            
            # Calculate remaining distance
            rem_dist = 0.0
            idx = -1
            for i, wp in enumerate(self.waypoint_manager.waypoints):
                if not wp.get('visited', False):
                    idx = i
                    break
            
            if idx != -1:
                next_wp = self.waypoint_manager.waypoints[idx]
                if self.current_coords and next_wp['coords']:
                    rem_dist += self.waypoint_manager.get_distance(self.current_coords, next_wp['coords'])
                
                prev_coords = next_wp['coords']
                for i in range(idx + 1, total_wp):
                    wp = self.waypoint_manager.waypoints[i]
                    if prev_coords and wp['coords']:
                        rem_dist += self.waypoint_manager.get_distance(prev_coords, wp['coords'])
                    prev_coords = wp['coords']
            
            custom_r_pos = (step, total_wp, f"{rem_dist:,.0f} LY")

        game_r_pos = None
        if self.route_list and self.current_sys in self.route_list:
            game_r_pos = (self.route_list.index(self.current_sys)+1, len(self.route_list))

        fss_summary = self._get_fss_summary()
        self.root.after(0, lambda: self.hud.update(
            self.current_sys, self.dest_name, dist, 
            self.scanned, self.total, custom_r_pos, self.organic_count, self.system_traffic, game_r_pos,
            fss_summary, self.fss_summary_active
        ))
        self.update_scan_hud()

    def update_scan_hud(self):
        if not self.scan_hud:
            return

        scanned_count = len(self.scan_items)
        total_value = 0
        for item in self.scan_items:
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            if isinstance(reward, (int, float)):
                total_value += int(reward)

        self.root.after(0, lambda: self.scan_hud.update(
            self.current_sys,
            self.system_undiscovered,
            self.fss_all_bodies,
            scanned_count,
            total_value,
            self.scan_items
        ))

    def _rebuild_scan_index(self):
        self.scan_items_by_id = {}
        for item in self.scan_items:
            self._normalize_scan_item(item)
            body_id = item.get("body_id")
            if body_id is not None:
                self.scan_items_by_id[body_id] = item
            self.save_scan_item_to_db(self.current_sys, item)

    def _format_credits(self, credits, hide_units=False):
        if credits is None:
            return ""
        try:
            credits = int(credits)
        except Exception:
            return ""

        if credits < 1_000:
            txt = f"{credits:,}"
        elif credits < 100_000:
            txt = f"{credits / 1_000:.2f} K"
        elif credits < 1_000_000:
            txt = f"{credits / 1_000:.0f} K"
        elif credits < 100_000_000:
            txt = f"{credits / 1_000_000:.2f} M"
        elif credits < 1_000_000_000:
            txt = f"{credits / 1_000_000:.0f} M"
        else:
            txt = f"{credits / 1_000_000_000:.3f} B"

        if not hide_units:
            txt += " CR"
        return txt

    def _get_fss_summary(self):
        if not self.scan_items:
            return None

        scanned_count = len(self.scan_items)
        total_value = 0
        for item in self.scan_items:
            reward = item.get("dss_reward") if item.get("dss_complete") else item.get("reward")
            if isinstance(reward, (int, float)):
                total_value += int(reward)

        last = self.scan_items[0]
        last_name = last.get("name") or ""
        last_class = last.get("class") or ""
        last_bio = last.get("bio_count", 0)
        last_reward = last.get("reward")
        last_dss = last.get("dss_reward")
        last_is_star = last.get("is_star", False)

        if last.get("dss_complete"):
            last_value = self._format_credits(last_reward, hide_units=True)
        else:
            last_value = self._format_credits(last_reward, hide_units=True)
            if not last_is_star and last_dss:
                last_value = f"{last_value} | {self._format_credits(last_dss, hide_units=True)}"

        high_value = []
        landable_count = 0
        remaining_count = max(self.total - self.scanned, 0) if self.total else 0
        for item in self.scan_items:
            planet_class = item.get("planet_class") or item.get("class") or ""
            terraformable = item.get("terraformable", False)
            icons = item.get("icons") or []
            if not terraformable and "🛠" in icons:
                terraformable = True
            is_high = terraformable or planet_class in ("Earthlike body", "Water world", "Ammonia world") or any(icon in icons for icon in ("🌍", "💧", "☣"))
            if not is_high:
                pass
            else:
                icon = ""
                if planet_class == "Earthlike body":
                    icon = "🌍"
                elif planet_class == "Water world":
                    icon = "💧"
                elif planet_class == "Ammonia world":
                    icon = "☣"
                elif terraformable:
                    icon = "🛠"
                label = item.get("full_name") or item.get("name") or ""
                if label and self.current_sys and self.current_sys not in label:
                    label = f"{self.current_sys} {label}"
                if not label:
                    label = item.get("class") or ""
                if not label:
                    body_id = item.get("body_id")
                    label = f"Body {body_id}" if body_id is not None else "Body"
                if planet_class == "Earthlike body":
                    class_label = "ELW"
                elif planet_class == "Water world":
                    class_label = "WW"
                elif planet_class == "Ammonia world":
                    class_label = "AW"
                elif terraformable:
                    class_label = "TF"
                else:
                    class_label = planet_class if planet_class else "HV"
                high_value.append(f"{icon} {class_label}: {label}".strip())

            if item.get("landable"):
                landable_count += 1

        high_value = high_value[:3]

        return {
            "count": scanned_count,
            "total": self._format_credits(total_value, hide_units=False),
            "high_value": high_value,
            "landable_count": landable_count,
            "remaining_count": remaining_count
        }

    def _get_body_k_value(self, planet_class, is_terraformable):
        if planet_class == "Metal rich body":
            k = 21790
        elif planet_class == "Ammonia world":
            k = 96932
        elif planet_class == "Sudarsky class I gas giant":
            k = 1656
        elif planet_class == "Sudarsky class II gas giant" or planet_class == "High metal content body":
            k = 9654
            if is_terraformable:
                k += 100677
        elif planet_class == "Water world":
            k = 64831
            if is_terraformable:
                k += 116295
        elif planet_class and planet_class.startswith("Earth"):
            k = 64831 + 116295
        else:
            k = 300
            if is_terraformable:
                k += 93328
        return k

    def _get_star_k_value(self, star_type):
        if star_type in ("NS", "BH", "SupermassiveBlackHole"):
            return 22628
        if star_type and star_type.startswith("W"):
            return 14057
        return 1200

    def _get_body_value(self, planet_class, star_type, is_terraformable, mass, is_first_discoverer, is_mapped, is_first_mapped, with_efficiency_bonus=True):
        is_star = False
        if star_type:
            is_star = True
        elif planet_class and (len(planet_class) < 8 or (len(planet_class) > 1 and planet_class[1] == '_') or planet_class in ("SupermassiveBlackHole", "Nebula", "StellarRemnantNebula")):
            is_star = True

        if is_star:
            kk = self._get_star_k_value(star_type or planet_class or "")
            star_value = kk + (mass * kk / 66.25)
            return int(round(star_value))

        k = self._get_body_k_value(planet_class or "", is_terraformable)

        q = 0.56591828
        mapping_multiplier = 1
        if is_mapped:
            if is_first_discoverer and is_first_mapped:
                mapping_multiplier = 3.699622554
            elif is_first_mapped:
                mapping_multiplier = 8.0956
            else:
                mapping_multiplier = 3.3333333333
        value = (k + k * q * pow(mass, 0.2)) * mapping_multiplier
        if is_mapped:
            value += max(value * 0.3, 555)
            if with_efficiency_bonus:
                value *= 1.25
        value = max(500, value)
        if is_first_discoverer:
            value *= 2.6
        return int(round(value))

    def _normalize_scan_item(self, item):
        if item.get("icons") is None:
            item["icons"] = []
        if item.get("body_id") is None:
            item["body_id"] = None

        name = item.get("name")
        if not name:
            fallback = item.get("class") or ""
            if not fallback:
                body_id = item.get("body_id")
                fallback = f"Body {body_id}" if body_id is not None else "Body"
            item["name"] = fallback
        if item.get("full_name") is None:
            item["full_name"] = item.get("name")

        body_class = item.get("class") or "Unknown"
        star_type = item.get("star_type")
        planet_class = item.get("planet_class")

        if not star_type and (body_class.lower().endswith("star") or body_class.lower().endswith(" star")):
            star_type = body_class.split()[0].upper()
        if not planet_class and not star_type:
            planet_class = body_class

        terraformable = item.get("terraformable")
        if terraformable is None:
            terraformable = "🛠" in item["icons"] or "🌍" in item["icons"]

        was_discovered = item.get("was_discovered")
        if was_discovered is None:
            was_discovered = "⚑" not in item["icons"]

        was_mapped = item.get("was_mapped")
        if was_mapped is None:
            was_mapped = False

        mass = item.get("mass")
        if mass is None:
            mass = 1.0

        reward = item.get("reward")
        dss_reward = item.get("dss_reward")
        if reward is None or dss_reward is None:
            is_first_discoverer = not was_discovered
            is_first_mapped = not was_mapped
            reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, False, is_first_mapped, True)
            dss_reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, True, is_first_mapped, True)

        dss_complete = item.get("dss_complete")
        if dss_complete is None:
            dss_complete = was_mapped

        bio_count = item.get("bio_count")
        if bio_count is None:
            bio_count = 0

        is_star = item.get("is_star")
        if is_star is None:
            is_star = bool(star_type)

        icons = item["icons"]
        if not was_discovered and "⚑" not in icons:
            icons.append("⚑")
        if terraformable and "🛠" not in icons:
            icons.append("🛠")
        if item.get("landable") and "🚀" not in icons:
            icons.append("🚀")
        if item.get("first_footfall") and "🦶" not in icons:
            icons.append("🦶")

        if not is_star:
            if planet_class == "Earthlike body" and "🌍" not in icons:
                icons.append("🌍")
            elif planet_class == "Water world" and "💧" not in icons:
                icons.append("💧")
            elif planet_class == "Ammonia world" and "☣" not in icons:
                icons.append("☣")

        highlight = (bio_count > 0) or (not is_star and dss_reward > reward)
        color = COLOR_ACCENT if highlight else COLOR_TEXT

        item.update({
            "star_type": star_type,
            "planet_class": planet_class,
            "terraformable": terraformable,
            "was_discovered": was_discovered,
            "was_mapped": was_mapped,
            "mass": mass,
            "reward": reward,
            "dss_reward": dss_reward,
            "dss_complete": dss_complete,
            "bio_count": bio_count,
            "is_star": is_star,
            "color": color,
            "icons": icons,
        })

        if item.get("_ts") is None:
            item["_ts"] = int(time.time())

    def update_status(self, data):
        gui_focus = data.get("GuiFocus", -1)
        in_fss = gui_focus == 9 or gui_focus == "FSS"
        if in_fss != self.in_fss:
            self.in_fss = in_fss
            if self.scan_hud:
                if self.in_fss:
                    if self.scan_hud_hide_job:
                        try:
                            self.root.after_cancel(self.scan_hud_hide_job)
                        except Exception:
                            pass
                        self.scan_hud_hide_job = None
                    self.scan_hud.show()
                else:
                    if self.scan_hud_hide_job:
                        return
                    self.scan_hud_hide_job = self.root.after(
                        self.scan_hud_hide_delay_ms,
                        self._hide_scan_hud_delayed
                    )
            if self.in_fss:
                self.fss_summary_active = False
            else:
                self.fss_summary_active = True
            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()

    def _hide_scan_hud_delayed(self):
        self.scan_hud_hide_job = None
        if self.scan_hud and not self.in_fss:
            self.scan_hud.hide()



    def add_scan_item(self, data):
        full_body_name = data.get("BodyName", "Unknown")
        body_name = full_body_name
        if body_name.startswith(self.current_sys):
            body_name = body_name.replace(self.current_sys, "").strip()
            if not body_name:
                body_name = self.current_sys

        star_type = data.get("StarType")
        planet_class = data.get("PlanetClass")
        is_star = bool(star_type)
        if is_star:
            body_class = f"{star_type} Star"
            icons = ["★"]
        else:
            body_class = planet_class or "Unknown"
            icons = []

        terraformable = data.get("TerraformState") == "Terraformable"
        landable = data.get("Landable", False)
        was_discovered = data.get("WasDiscovered", True)
        was_mapped = data.get("WasMapped", True)
        first_footfall = data.get("FirstFootfall", False)

        if not was_discovered:
            icons.append("⚑")

        # Planet/Body icons
        if body_class == "Earthlike body":
            icons.append("🌍")
        elif body_class == "Water world":
            icons.append("💧")
        elif body_class == "Ammonia world":
            icons.append("☣")
        elif "Gas giant" in body_class:
            icons.append("🌀")
        elif "Metal rich" in body_class:
            icons.append("⬢")
        elif "High metal content" in body_class:
            icons.append("⛰")
        elif "Rocky" in body_class:
            icons.append("🪨")

        if terraformable:
            icons.append("🛠")
        if landable:
            icons.append("🚀")
        if first_footfall:
            icons.append("🦶")

        body_id = data.get("BodyID")
        mass = data.get("MassEM") or data.get("StellarMass") or 0
        is_first_discoverer = not was_discovered
        is_first_mapped = not was_mapped
        reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, False, is_first_mapped, True)
        dss_reward = self._get_body_value(planet_class, star_type, terraformable, mass, is_first_discoverer, True, is_first_mapped, True)
        dss_complete = was_mapped or (body_id in self.body_dss_complete)

        bio_count = 0
        if "BioSignals" in data:
            for signal in data.get("BioSignals", []):
                if signal.get("Type_Localised") == "Biological":
                    bio_count += signal.get("Count", 0)
        elif body_id in self.body_signals:
            bio_count = self.body_signals[body_id].get("bio", 0)

        highlight = (bio_count > 0) or (not is_star and dss_reward > reward)
        color = COLOR_ACCENT if highlight else COLOR_TEXT

        ts = int(time.time())
        item = {
            "body_id": body_id,
            "name": body_name,
            "full_name": full_body_name,
            "class": body_class,
            "star_type": star_type,
            "planet_class": planet_class,
            "terraformable": terraformable,
            "landable": landable,
            "was_mapped": was_mapped,
            "mass": mass,
            "radius": data.get("Radius"),
            "surface_temp": data.get("SurfaceTemperature"),
            "surface_gravity": data.get("SurfaceGravity"),
            "atmosphere": data.get("Atmosphere") or data.get("AtmosphereType"),
            "volcanism": data.get("Volcanism"),
            "icons": icons,
            "color": color,
            "reward": reward,
            "dss_reward": dss_reward,
            "dss_complete": dss_complete,
            "bio_count": bio_count,
            "is_star": is_star,
            "was_discovered": was_discovered,
            "first_footfall": first_footfall,
            "_ts": ts
        }

        existing = None
        if body_id is not None:
            existing = self.scan_items_by_id.get(body_id)
        if existing:
            self.scan_items.remove(existing)
        self.scan_items.insert(0, item)
        self.scan_items = self.scan_items[:60]
        if body_id is not None:
            self.scan_items_by_id[body_id] = item
        self.save_scan_item_to_db(self.current_sys, item)

    def process_event(self, data):
        ev = data.get("type") or data.get("event")
        raw = data.get("raw", data)
        d = data.get("data", data)
        
        if ev == "Fileheader":
            self.log(f"Game version detected: {d.get('gameversion')} ({d.get('build')})")

        elif ev == "Loadout":
            self.cargo_capacity = d.get("cargo_capacity", 0)
            self.watcher.force_check_cargo()

        elif ev == "Commander":
            self.cmdr_name = d.get("name", "CMDR")

        elif ev == "LoadGame":
            self.cmdr_name = d.get("commander", "CMDR")
            game_version = d.get("gameversion")
            game_build = d.get("build")
            if game_version and game_build:
                self.log(f"Game version detected from LoadGame: {game_version} ({game_build})")

        elif ev == "ScanOrganic":
            # Bio counting is temporarily disabled.
            return

        elif ev == "Location" or ev == "FSDJump" or ev == "StartJump":
            # Do not update HUDs during jump charge; wait for arrival.
            if ev == "StartJump":
                if self.scan_hud:
                    self.scan_hud.hide()
                    self.in_fss = False
                    self.fss_summary_active = False
                return

            is_jump = ev == "FSDJump"
            
            # Hide scan HUD on jump completion
            if ev == "FSDJump" and self.scan_hud:
                self.scan_hud.hide()
                self.in_fss = False
                self.fss_summary_active = False

            prev_coords = self.current_coords if isinstance(self.current_coords, list) else None

            # State reset for new system
            self.current_sys = d.get("star_system", "Unknown")
            self.current_coords = d.get("star_pos", [0,0,0])
            # Preserve existing class when an event omits StarClass (common on some transitions).
            next_star_class = d.get("star_class")
            if not next_star_class:
                next_star_class = raw.get("StarClass") if isinstance(raw, dict) else None
            if next_star_class:
                self.star_class = next_star_class

            if is_jump and prev_coords and self.current_coords:
                try:
                    jump_ly = math.sqrt(sum((a - b) ** 2 for a, b in zip(prev_coords, self.current_coords)))
                    self.session_jump_count += 1
                    self.session_ly += jump_ly
                except Exception:
                    pass
            
            # Load from history if available
            self.load_system_from_db(self.current_sys)

            self.organic_count = 0 # Reset bio count for new system
            self.system_bio_signals = 0
            self.last_scan_event = None
            self.last_bio_scan = {}
            self.valuable_system = False
            self.valuable_bodies.clear()
            self.system_traffic = {'day': 0, 'week': 0, 'total': 0}
            self.scan_items = self.load_scan_items_from_db(self.current_sys)
            self.body_signals = {}
            self.body_dss_complete = set()
            self.system_undiscovered = False
            self.fss_all_bodies = False
            self.fss_summary_active = False
            self._rebuild_scan_index()

            log_msg = f"JUMP: {self.current_sys}" if is_jump else f"LOCATION: {self.current_sys}"
            self.log(log_msg)
            
            if not self.batch_mode:
                sys_text = self.current_sys.upper()
                if self.star_class: sys_text += f" [{self.star_class}]"
                self.root.after(0, lambda: self.sys_stat.config(text=sys_text))
                self.root.after(0, lambda: self.valuable_list.delete(0, tk.END))
                self.update_nav_label()
            # Bio logs hidden for now (counting disabled)
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.root.after(0, self.update_waypoint_display)
                self.schedule_dashboard_refresh(full=True)
                self.update_scan_hud()

            # Update Route Plotter UI if open
            if self.route_plotter and self.route_plotter.win.winfo_exists():
                s_sys = self.current_sys
                s_coords = self.current_coords
                self.root.after(0, lambda: self.route_plotter.update_current_system(s_sys, s_coords))

            # Auto-copy next waypoint logic
            if self.config.get("auto_copy_waypoint", False):
                next_wp = self.waypoint_manager.get_next_waypoint(self.current_sys)
                if next_wp:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(next_wp)
                    self.root.update()
                    self.log(f"📋 COPIED NEXT WAYPOINT: {next_wp}")

            if is_jump:
                # It's a new jump, so reset the Discord message for the new system.
                self.discord.reset_msg_id()
            self.update_live_discord(raw)
            
            if self.current_sys != self.last_traffic_system:
                self.last_traffic_system = self.current_sys
                self.fetch_system_traffic(self.current_sys)

        elif ev == "FSSDiscoveryScan":
            if d.get("system_name") and d.get("system_name") != self.current_sys:
                return
            self.total = d.get("body_count", self.total)
            self.fss_all_bodies = False
            self.db_update_system(self.current_sys, self.total, self.scanned)
            if not self.batch_mode:
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.log(f"🔭 HONK: {self.total} bodies detected.")
            self.update_live_discord(raw)
            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()

        elif ev == "FSSAllBodiesFound":
            if d.get("system_name") and d.get("system_name") == self.current_sys:
                self.total = d.get("count", self.total)
                self.scanned = self.total
                self.fss_all_bodies = True
                self.db_update_system(self.current_sys, self.total, self.scanned)
                if not self.batch_mode:
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.log("📡 SYSTEM SCAN COMPLETE: All bodies found.")
                if not self.batch_mode:
                    self.update_hud()
                    self.schedule_dashboard_refresh()
        
        elif ev == "FSSBodySignals":
            body_id = d.get("body_id")
            if body_id is not None:
                bio_count = d.get("bio_count", 0)
                geo_count = d.get("geo_count", 0)
                self.body_signals[body_id] = {"bio": bio_count, "geo": geo_count}
                item = self.scan_items_by_id.get(body_id)
                if item:
                    item["bio_count"] = bio_count
                    item["color"] = COLOR_ACCENT if (bio_count > 0 or (not item.get("is_star") and item.get("dss_reward", 0) > item.get("reward", 0))) else COLOR_TEXT
                    if item.get("_ts") is None:
                        item["_ts"] = int(time.time())
                    self.save_scan_item_to_db(self.current_sys, item)
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
        
        elif ev == "SAAScanComplete":
            body_id = d.get("body_id")
            if body_id is not None:
                self.body_dss_complete.add(body_id)
                item = self.scan_items_by_id.get(body_id)
                if item:
                    item["dss_complete"] = True
                    if item.get("_ts") is None:
                        item["_ts"] = int(time.time())
                    self.save_scan_item_to_db(self.current_sys, item)
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
        
        elif ev == "Scan":
            body_name = d.get("body_name", "")
            body_id = d.get("body_id", body_name)

            # Accept star class from system star scans even when this body is already known.
            star_type = d.get("star_type")
            is_system_star_scan = bool(star_type) and isinstance(body_name, str) and body_name.startswith(self.current_sys)
            if is_system_star_scan and self.star_class != star_type:
                self.star_class = star_type
                if not self.batch_mode:
                    self.schedule_dashboard_refresh()
                    self.update_hud()
            
            # Only count scans of stars or planets/moons, not belts.
            if d.get("is_body_scan"):
                # Ensure the scan belongs to the current system to prevent state corruption
                if d.get("star_system") and d.get("star_system") != self.current_sys:
                    return

                is_new_body_scan = body_id not in self.scanned_bodies
                
                if is_new_body_scan:
                    # --- State Updates for a new body ---
                    self.scanned_bodies.add(body_id)
                    self.scanned += 1
                    self.db_add_body(self.current_sys, body_id)
                    self.db_update_system(self.current_sys, self.total, self.scanned)
                    if not self.batch_mode:
                        self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                    self.last_scan_event = data
                    self.add_scan_item(raw)
                    if is_system_star_scan and d.get("was_discovered") is False:
                        self.system_undiscovered = True
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()

                    # Check for biological signals and update the system total
                    self.system_bio_signals += d.get("bio_signals_count", 0)

                    # Check for valuable bodies
                    p_class = d.get("planet_class", "")
                    terraformable = d.get("terraform_state") == "Terraformable"
                    if p_class in ["Earthlike body", "Water world", "Ammonia world"] or terraformable:
                        self.valuable_system = True
                        body_name_str = body_name or "Unknown"
                        icon = "✨"
                        if p_class == "Earthlike body": icon = "🌍"
                        elif p_class == "Water world": icon = "💧"
                        elif p_class == "Ammonia world": icon = "☣️"
                        elif terraformable: icon = "🛠️"
                        self.valuable_bodies.append(f"- {icon} {body_name_str}")
                        if not self.batch_mode:
                            self.root.after(0, lambda: self.valuable_list.insert(tk.END, f"{icon} {body_name_str}"))

                    # --- Notification Logic ---
                    # Since this is a new scan, we always update.
                    self.update_live_discord(raw)

    def process_batch(self, events):
        self.batch_mode = True
        with self.db_lock:
            self.conn.execute("BEGIN TRANSACTION")
            for ev in events:
                try:
                    self.process_event(ev)
                except: pass
            self.conn.commit()
        self.batch_mode = False
        self.root.after(0, self.update_dashboard_ui)
        self.root.after(0, self.update_hud)
        
        if self.is_first_load:
            self.is_first_load = False
            if self.config.get("discord_enabled", True) and self.config.get("discord_msg_system") != self.current_sys:
                self.log("Stale Discord message detected. A new message will be created.")
                self.discord.reset_msg_id()
            self.last_traffic_system = self.current_sys
            self.fetch_system_traffic(self.current_sys)
            self.update_hud()
            self.update_live_discord()
            self.root.after(0, self.update_waypoint_display)
            
            if self.config.get("auto_copy_waypoint", False):
                next_wp = self.waypoint_manager.get_next_waypoint(self.current_sys)
                if next_wp:
                    def _copy():
                        self.root.clipboard_clear()
                        self.root.clipboard_append(next_wp)
                        self.root.update()
                    self.root.after(0, _copy)
                    self.log(f"📋 COPIED NEXT WAYPOINT: {next_wp}")

    def update_cargo(self, inventory):
        if self.cargo_hud:
            self.root.after(0, lambda: self.cargo_hud.update(inventory, self.cargo_capacity))

    def update_nav_route(self, data):
        self.route_list = [r['StarSystem'] for r in data.get('Route', [])]
        if self.route_list:
            dest = data['Route'][-1]
            self.dest_coords = dest['StarPos']
            self.dest_name = dest['StarSystem']
            self.update_nav_label()
            self.update_hud()
