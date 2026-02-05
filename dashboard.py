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
        self.valuable_system = False
        self.valuable_bodies = []
        self.scanned_bodies = set()
        self.scan_items = []
        self.scan_items_by_id = {}
        self.in_fss = False
        self.scan_hud_hide_job = None
        self.scan_hud_hide_delay_ms = 60000
        self.body_signals = {}
        self.body_dss_complete = set()
        self.system_undiscovered = False
        self.fss_all_bodies = False
        self.cmdr_name = self.config.get("edsm_cmdr_name", "CMDR")
        self.last_scan_event = None
        self.cargo_capacity = 0
        
        self.dest_coords = None
        self.current_coords = [0,0,0]
        self.dest_name = None
        self.route_list = []
        
        self.setup_layout()
        self.waypoint_manager = WaypointManager()
        self.route_plotter = None
        self.target_waypoint = None
        self.waypoint_cache = {}
        
        # Initialize Handlers
        self.edsm = EDSMHandler(self.config, self.update_edsm_status, self.update_queue_count)
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
        
        self.root.after(2000, self.verify_link)
        self.watcher.force_check_status()
        
        threading.Thread(target=self.check_updates, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

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
        
        body = tk.Frame(self.root, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.side = tk.Frame(body, bg=COLOR_PANEL, width=280, highlightbackground="#333", highlightthickness=1)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.side.pack_propagate(False)
        
        self.sys_stat = self.create_stat("CURRENT_SYSTEM", "---")
        self.nav_stat = self.create_stat("NAVIGATION TARGET", "---")
        self.traffic_stat = self.create_stat("TRAFFIC (24H)", "---")
        self.scan_stat = self.create_stat("SCAN_PROGRESS", "0 / 0")
        # Bio logs hidden for now (counting disabled)
        self.edsm_stat = self.create_stat("EDSM_STATUS", "DISABLED")
        if not (self.config.get("edsm_enabled", True) and self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key")): self.edsm_stat.config(fg="#666")
        self.queue_stat = self.create_stat("UPLOAD_QUEUE", "0")
        
        tk.Label(self.side, text="VALUABLE FINDS", font=("Courier", 8), fg="#666", bg=COLOR_PANEL).pack(anchor="w", padx=20, pady=(15,0))
        self.valuable_list = tk.Listbox(self.side, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9), height=6, relief=tk.FLAT, highlightthickness=0, borderwidth=0)
        self.valuable_list.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(self.side, text="© 2026 insert3coins", font=("Courier", 8), fg="#444", bg=COLOR_PANEL).pack(side=tk.BOTTOM, anchor="w", padx=20, pady=10)
        
        btn_scan = tk.Button(self.side, text="[ REBUILD CACHE ]", command=self.scan_all_logs_threaded, bg=COLOR_PANEL, fg="#555", font=("Courier", 8, "bold"), relief=tk.FLAT, activebackground=COLOR_PANEL, activeforeground=COLOR_TEXT)
        btn_scan.pack(side=tk.BOTTOM, anchor="w", padx=20, pady=(0, 5))
        
        # Right Column (Waypoint Info + Log)
        right_col = tk.Frame(body, bg=COLOR_BG)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Waypoint Info Panel
        self.wp_panel = tk.Frame(right_col, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1, height=80)
        self.wp_panel.pack(fill=tk.X, pady=(0, 10))
        self.wp_panel.pack_propagate(False)

        # Header Row
        header_row = tk.Frame(self.wp_panel, bg=COLOR_PANEL)
        header_row.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(header_row, text="NEXT WAYPOINT:", font=("Courier", 9, "bold"), fg=COLOR_ORANGE, bg=COLOR_PANEL).pack(side=tk.LEFT)
        self.wp_dist_lbl = tk.Label(header_row, text="", font=("Courier", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL)
        self.wp_dist_lbl.pack(side=tk.RIGHT)

        self.wp_name_lbl = tk.Label(self.wp_panel, text="NO ACTIVE ROUTE", font=("Courier", 16, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL)
        self.wp_name_lbl.pack(anchor="w", padx=10)
        
        self.wp_info_lbl = tk.Label(self.wp_panel, text="", font=("Courier", 9), fg="#aaa", bg=COLOR_PANEL)
        self.wp_info_lbl.pack(anchor="w", padx=10)

        # Log Panel
        log_frame = tk.Frame(right_col, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_box = scrolledtext.ScrolledText(log_frame, bg="#000", fg=COLOR_GREEN, font=("Courier", 10), borderwidth=0)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_stat(self, label, val):
        tk.Label(self.side, text=label, font=("Courier", 8), fg="#666", bg=COLOR_PANEL).pack(anchor="w", padx=20, pady=(10,0))
        l = tk.Label(self.side, text=val, font=("Courier", 11, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL)
        l.pack(anchor="w", padx=20)
        return l

    def log(self, msg):
        self.root.after(0, lambda: (self.log_box.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

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

    def update_edsm_status(self, text, color):
        def _apply():
            self.edsm_stat.config(text=text, fg=color)
            self.update_hud()
        self.root.after(0, _apply)

    def update_queue_count(self, count):
        self.root.after(0, lambda: self.queue_stat.config(text=str(count)))

    def update_nav_label(self):
        txt = "NO ROUTE"
        if self.dest_name:
            txt = self.dest_name
        
        if not self.batch_mode:
            self.root.after(0, lambda: self.nav_stat.config(text=txt))

    def update_dashboard_ui(self):
        """Force update all dashboard labels from current state."""
        sys_text = self.current_sys.upper()
        if self.star_class: sys_text += f" [{self.star_class}]"
        
        self.sys_stat.config(text=sys_text)
        self.scan_stat.config(text=f"{self.scanned} / {self.total}")
        # Bio logs hidden for now (counting disabled)
        self.traffic_stat.config(text=str(self.system_traffic.get('day', 0)))
        self.update_nav_label()
        
        self.valuable_list.delete(0, tk.END)
        for item in self.valuable_bodies:
            # item is stored as "- 🌍 Earthlike...", listbox needs just "🌍 Earthlike..."
            # The storage format in process_event is "- {icon} {name}"
            # The listbox insert in process_event is "{icon} {name}"
            # Let's just strip the leading "- " if present
            display_text = item[2:] if item.startswith("- ") else item
            self.valuable_list.insert(tk.END, display_text)
        self.update_waypoint_display()

    def update_waypoint_display(self):
        if not self.waypoint_manager.waypoints:
            self.target_waypoint = None
            self.wp_name_lbl.config(text="NO ACTIVE ROUTE")
            self.wp_dist_lbl.config(text="")
            self.wp_info_lbl.config(text="")
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
             self.wp_info_lbl.config(text="")
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
            self.wp_info_lbl.config(text=info_text)
            self.update_hud()

    def on_close(self):
        """Save state and exit."""
        self.is_running = False
        
        if self.route_plotter and self.route_plotter.win.winfo_exists():
            self.route_plotter.on_close()
            
        self.watcher.stop()
        self.edsm.stop()
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
            
            # Live Update: EDSM
            edsm_active = self.config.get("edsm_enabled", True) and self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key")
            
            if edsm_active:
                self.edsm.status = "STANDBY"
                self.edsm_stat.config(text="STANDBY", fg=COLOR_TEXT)
                self.verify_link()
            else:
                self.edsm.status = "DISABLED"
                self.edsm_stat.config(text="DISABLED", fg="#666")
                self.verify_link()
            
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

    def verify_link(self):
        if self.config.get("edsm_enabled", True) and self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key"):
            self.log("INITIATING EDSM HANDSHAKE...")
            self.edsm.enqueue({"event": "Music", "MusicTrack": "NoTrack"}, self.current_sys, self.current_coords)
        else:
            if not self.config.get("edsm_enabled", True):
                self.log("EDSM Integration: DISABLED (User Setting)")
            else:
                self.log("EDSM Integration: DISABLED (No Credentials)")

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
            if self.current_sys != system_name:
                return
            self.system_traffic = traffic_data
            self.root.after(0, lambda: self.traffic_stat.config(text=str(traffic_data.get('day', 0))))
            # Always update the HUD to reflect the new (or reset) traffic data.
            self.update_hud()
            self.update_live_discord()
        
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

        self.root.after(0, lambda: self.hud.update(
            self.current_sys, self.dest_name, dist, 
            self.scanned, self.total, self.edsm.status, custom_r_pos, self.organic_count, self.system_traffic, game_r_pos
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

    def _hide_scan_hud_delayed(self):
        self.scan_hud_hide_job = None
        if self.scan_hud and not self.in_fss:
            self.scan_hud.hide()

    def add_scan_item(self, data):
        body_name = data.get("BodyName", "Unknown")
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
            "class": body_class,
            "star_type": star_type,
            "planet_class": planet_class,
            "terraformable": terraformable,
            "landable": landable,
            "was_mapped": was_mapped,
            "mass": mass,
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
        ev = data.get("event")
        
        if ev == "Fileheader":
            self.edsm.set_game_version(data.get("gameversion"), data.get("build"))
            self.log(f"Game version detected: {data.get('gameversion')} ({data.get('build')})")

        elif ev == "Loadout":
            self.cargo_capacity = data.get("CargoCapacity", 0)
            self.watcher.force_check_cargo()

        elif ev == "Commander":
            self.cmdr_name = data.get("Name", "CMDR")
            if not self.config.get("edsm_cmdr_name"):
                self.config["edsm_cmdr_name"] = self.cmdr_name

        elif ev == "LoadGame":
            self.cmdr_name = data.get("Commander", "CMDR")
            game_version = data.get("gameversion")
            game_build = data.get("build")
            if game_version and game_build:
                self.edsm.set_game_version(game_version, game_build)
                self.log(f"Game version detected from LoadGame: {game_version} ({game_build})")

        elif ev == "ScanOrganic":
            # Bio counting is temporarily disabled.
            return

        elif ev == "Location" or ev == "FSDJump":
            is_jump = ev == "FSDJump"
            
            # State reset for new system
            self.current_sys = data.get("StarSystem", "Unknown")
            self.current_coords = data.get("StarPos", [0,0,0])
            self.star_class = data.get("StarClass", "")
            
            # Load from history if available
            self.load_system_from_db(self.current_sys)

            self.organic_count = 0 # Reset bio count for new system
            self.system_bio_signals = 0
            self.last_scan_event = None
            self.valuable_system = False
            self.valuable_bodies.clear()
            self.system_traffic = {'day': 0, 'week': 0, 'total': 0}
            self.scan_items = self.load_scan_items_from_db(self.current_sys)
            self.body_signals = {}
            self.body_dss_complete = set()
            self.system_undiscovered = False
            self.fss_all_bodies = False
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

            was_enqueued = self.edsm.enqueue(data, self.current_sys, self.current_coords)
            if was_enqueued:
                if is_jump:
                    # It's a new jump, so reset the Discord message for the new system.
                    self.discord.reset_msg_id()
                self.update_live_discord(data)
            
            if not self.is_first_load:
                self.fetch_system_traffic(self.current_sys)

        elif ev == "FSSDiscoveryScan":
            if "SystemName" in data and data["SystemName"] != self.current_sys:
                return
            self.total = data.get("BodyCount", self.total)
            self.fss_all_bodies = False
            self.db_update_system(self.current_sys, self.total, self.scanned)
            if not self.batch_mode:
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.edsm.enqueue(data, self.current_sys, self.current_coords)
            self.log(f"🔭 HONK: {self.total} bodies detected.")
            self.update_live_discord(data)
            if not self.batch_mode:
                self.update_hud()

        elif ev == "FSSAllBodiesFound":
            if "SystemName" in data and data["SystemName"] == self.current_sys:
                self.total = data.get("Count", self.total)
                self.scanned = self.total
                self.fss_all_bodies = True
                self.db_update_system(self.current_sys, self.total, self.scanned)
                if not self.batch_mode:
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.edsm.enqueue(data, self.current_sys, self.current_coords)
                self.log("📡 SYSTEM SCAN COMPLETE: All bodies found.")
                if not self.batch_mode:
                    self.update_hud()
        
        elif ev == "FSSBodySignals":
            body_id = data.get("BodyID")
            if body_id is not None:
                bio_count = 0
                geo_count = 0
                for signal in data.get("Signals", []):
                    if signal.get("Type") == "$SAA_SignalType_Biological;":
                        bio_count = signal.get("Count", 0)
                    elif signal.get("Type") == "$SAA_SignalType_Geological;":
                        geo_count = signal.get("Count", 0)
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
        
        elif ev == "SAAScanComplete":
            body_id = data.get("BodyID")
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
        
        elif ev == "Scan":
            body_name = data.get("BodyName", "")
            body_id = data.get("BodyID", body_name)
            
            self.edsm.enqueue(data, self.current_sys, self.current_coords)
            
            # Only count scans of stars or planets/moons, not belts.
            if 'StarType' in data or 'PlanetClass' in data:
                # Ensure the scan belongs to the current system to prevent state corruption
                if "StarSystem" in data and data["StarSystem"] != self.current_sys:
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
                    self.add_scan_item(data)
                    if "StarType" in data and data.get("BodyName") == self.current_sys and data.get("WasDiscovered") is False:
                        self.system_undiscovered = True
                    if not self.batch_mode:
                        self.update_hud()

                    # Check for biological signals and update the system total
                    if "BioSignals" in data:
                        for signal in data.get("BioSignals", []):
                            if signal.get("Type_Localised") == "Biological":
                                self.system_bio_signals += signal.get("Count", 0)

                    # Check for valuable bodies
                    p_class = data.get("PlanetClass", "")
                    terraformable = data.get("TerraformState") == "Terraformable"
                    if p_class in ["Earthlike body", "Water world", "Ammonia world"] or terraformable:
                        self.valuable_system = True
                        body_name_str = data.get("BodyName", "Unknown")
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
                    self.update_live_discord(data)

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
