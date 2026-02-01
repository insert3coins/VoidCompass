import os
import json
import threading
import math
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
from edsm_handler import EDSMHandler
from discord_handler import DiscordHandler
from settings_ui import open_settings
from route_plotter import RoutePlotter
from waypoint_manager import WaypointManager

SCAN_HISTORY_FILE = "scan_history.json"

class MainDashboard:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.root.title(f"SURVEY ANALYSIS // v{APP_VERSION}")
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
        self.cmdr_name = self.config.get("edsm_cmdr_name", "CMDR")
        self.last_scan_event = None
        self.scan_history = {}
        
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
        
        if self.config.get("overlay_enabled", True):
            self.hud = TacticalHUD(self.root, self.config)
        else:
            self.hud = None
            
        if self.config.get("cargo_overlay_enabled", False):
            self.cargo_hud = CargoHUD(self.root, self.config)
        else:
            self.cargo_hud = None
        
        self.load_history()
        threading.Thread(target=self.threaded_poll_engine, daemon=True).start()
        
        self.root.after(2000, self.verify_link)
        
        threading.Thread(target=self.check_updates, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_layout(self):
        self.nav = tk.Frame(self.root, bg=COLOR_PANEL, height=50, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        self.nav.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        tk.Label(self.nav, text=f" > SURVEY ANALYSIS // V{APP_VERSION}", font=("Courier", 11, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=15)
        
        btn_conf = tk.Button(self.nav, text="[ CONFIGURATION ]", command=self.open_settings, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_conf.pack(side=tk.RIGHT, padx=15)

        # Route Button
        btn_route = tk.Button(self.nav, text="[ ROUTE PLANNER ]", command=self.open_route_planner, bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn_route.pack(side=tk.RIGHT, padx=5)
        
        body = tk.Frame(self.root, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.side = tk.Frame(body, bg=COLOR_PANEL, width=280, highlightbackground="#333", highlightthickness=1)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.side.pack_propagate(False)
        
        self.sys_stat = self.create_stat("CURRENT_SYSTEM", "---")
        self.nav_stat = self.create_stat("NAVIGATION TARGET", "---")
        self.traffic_stat = self.create_stat("TRAFFIC (24H)", "---")
        self.scan_stat = self.create_stat("SCAN_PROGRESS", "0 / 0")
        self.bio_stat = self.create_stat("ORGANIC_LOGS", "0")
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
            url = "https://api.github.com/repos/insert3coins/SurveyAnalysis-Release/releases/latest"
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

    def load_history(self):
        if os.path.exists(SCAN_HISTORY_FILE):
            try:
                with open(SCAN_HISTORY_FILE, 'r') as f:
                    self.scan_history = json.load(f)
            except Exception:
                self.scan_history = {}

    def scan_all_logs_threaded(self):
        threading.Thread(target=self.scan_all_logs, daemon=True).start()

    def scan_all_logs(self):
        path = self.config.get("journal_path")
        if not path or not os.path.exists(path):
            self.log("❌ Journal path invalid.")
            return

        self.log("📚 STARTING HISTORY REBUILD...")
        
        try:
            files = sorted([os.path.join(path, f) for f in os.listdir(path) if f.startswith("Journal.") and f.endswith(".log")])
        except Exception as e:
            self.log(f"❌ Error listing files: {e}")
            return

        total_files = len(files)
        if total_files == 0:
            self.log("⚠️ No journal files found.")
            return

        new_history = self.scan_history.copy()
        processed = 0

        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    current_sys_context = None
                    for line in f:
                        try:
                            data = json.loads(line)
                            ev = data.get("event")

                            if ev in ["FSDJump", "Location"]:
                                sys_name = data.get("StarSystem")
                                current_sys_context = sys_name
                                if sys_name and sys_name not in new_history:
                                    new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}

                            elif ev == "FSSDiscoveryScan":
                                sys_name = data.get("SystemName", current_sys_context)
                                if sys_name:
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    count = data.get("BodyCount", 0)
                                    if count > new_history[sys_name]["total"]: new_history[sys_name]["total"] = count

                            elif ev == "FSSAllBodiesFound":
                                sys_name = data.get("SystemName", current_sys_context)
                                if sys_name:
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    count = data.get("Count", 0)
                                    new_history[sys_name]["total"] = count
                                    new_history[sys_name]["scanned_count"] = count

                            elif ev == "Scan":
                                sys_name = data.get("StarSystem", current_sys_context)
                                if sys_name and ("StarType" in data or "PlanetClass" in data):
                                    if sys_name not in new_history: new_history[sys_name] = {"total": 0, "bodies": [], "scanned_count": 0}
                                    body_id = data.get("BodyID")
                                    if body_id is not None:
                                        if "bodies" not in new_history[sys_name]: new_history[sys_name]["bodies"] = []
                                        if body_id not in new_history[sys_name]["bodies"]: new_history[sys_name]["bodies"].append(body_id)
                        except ValueError: continue
            except Exception: pass
            
            processed += 1
            if processed % 10 == 0: self.log(f"⏳ Scanning... {int((processed/total_files)*100)}%")

        for sys_name, data in new_history.items():
            if len(data.get("bodies", [])) > data.get("scanned_count", 0): data["scanned_count"] = len(data["bodies"])
            if data.get("scanned_count", 0) > data.get("total", 0): data["total"] = data["scanned_count"]

        self.scan_history = new_history
        self.save_history()
        self.log(f"✅ CACHE REBUILD COMPLETE. ({len(new_history)} Systems)")
        
        if self.current_sys in self.scan_history:
            h = self.scan_history[self.current_sys]
            self.total = h.get("total", 0)
            self.scanned_bodies = set(h.get("bodies", []))
            self.scanned = h.get("scanned_count", 0)
            self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.update_hud()

    def save_history(self):
        if not self.current_sys or self.current_sys == "---" or self.current_sys == "Unknown":
            return
        
        self.scan_history[self.current_sys] = {
            "total": self.total,
            "bodies": list(self.scanned_bodies),
            "scanned_count": self.scanned
        }
        try:
            with open(SCAN_HISTORY_FILE, 'w') as f:
                json.dump(self.scan_history, f, indent=4)
        except Exception:
            pass

    def update_edsm_status(self, text, color):
        self.root.after(0, lambda: self.edsm_stat.config(text=text, fg=color))

    def update_queue_count(self, count):
        self.root.after(0, lambda: self.queue_stat.config(text=str(count)))

    def update_nav_label(self):
        txt = "NO ROUTE"
        if self.dest_name:
            txt = self.dest_name
        
        self.root.after(0, lambda: self.nav_stat.config(text=txt))

    def update_waypoint_display(self):
        if not self.waypoint_manager.waypoints:
            self.target_waypoint = None
            self.wp_name_lbl.config(text="NO ACTIVE ROUTE")
            self.wp_dist_lbl.config(text="")
            self.wp_info_lbl.config(text="")
            return

        idx = self.waypoint_manager.get_waypoint_index(self.current_sys)
        
        if idx != -1:
            # We are at a waypoint, target the next one
            if idx + 1 < len(self.waypoint_manager.waypoints):
                self.target_waypoint = self.waypoint_manager.waypoints[idx+1]
            else:
                self.target_waypoint = None # End of route
                self.wp_name_lbl.config(text="ROUTE COMPLETE")
                self.wp_dist_lbl.config(text="")
                self.wp_info_lbl.config(text="")
                return
        elif self.target_waypoint is None:
             # Not at a waypoint, and no target set. Default to first.
             self.target_waypoint = self.waypoint_manager.waypoints[0]
        
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

    def on_close(self):
        """Save state and exit."""
        self.is_running = False
        
        if self.route_plotter and self.route_plotter.win.winfo_exists():
            self.route_plotter.on_close()
            
        self.edsm.stop()
        self.config["main_geometry"] = self.root.geometry()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        self.root.destroy()

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
                    # Force re-read of cargo file
                    if hasattr(self, 'last_cargo_mtime'):
                        del self.last_cargo_mtime
                    self.check_cargo_file()
            else:
                if self.cargo_hud:
                    self.cargo_hud.win.destroy()
                    self.cargo_hud = None
        
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
            # Check if we are at a waypoint
            idx = self.waypoint_manager.get_waypoint_index(self.current_sys)
            
            if idx != -1:
                # We are at waypoint (idx+1)
                custom_r_pos = (idx + 1, total_wp)
            elif self.target_waypoint:
                # We are navigating to target_waypoint
                t_idx = self.waypoint_manager.get_waypoint_index(self.target_waypoint['name'])
                if t_idx != -1:
                    custom_r_pos = (t_idx + 1, total_wp)
            else:
                custom_r_pos = (1, total_wp)

        game_r_pos = None
        if self.route_list and self.current_sys in self.route_list:
            game_r_pos = (self.route_list.index(self.current_sys)+1, len(self.route_list))

        self.root.after(0, lambda: self.hud.update(
            self.current_sys, self.dest_name, dist, 
            self.scanned, self.total, self.edsm.status, custom_r_pos, self.organic_count, self.system_traffic, game_r_pos
        ))

    def process_event(self, data):
        ev = data.get("event")
        
        if ev == "Fileheader":
            self.edsm.set_game_version(data.get("gameversion"), data.get("build"))
            self.log(f"Game version detected: {data.get('gameversion')} ({data.get('build')})")

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
            self.organic_count += 1
            genus = data.get("Genus_Localised", "Unknown")
            species = data.get("Species_Localised", "Unknown")
            
            self.log(f"🌱 BIO: {genus}")
            # Note: ScanOrganic is in EDSM's discarded events list, so we don't send it
            # self.edsm.enqueue(data, self.current_sys, self.current_coords)
            self.update_live_discord(data)
            
            self.root.after(0, lambda: self.bio_stat.config(text=str(self.organic_count)))

        elif ev == "Location" or ev == "FSDJump":
            is_jump = ev == "FSDJump"
            
            # State reset for new system
            self.current_sys = data.get("StarSystem", "Unknown")
            self.current_coords = data.get("StarPos", [0,0,0])
            self.star_class = data.get("StarClass", "")
            
            # Load from history if available
            if self.current_sys in self.scan_history:
                h = self.scan_history[self.current_sys]
                self.total = h.get("total", 0)
                self.scanned_bodies = set(h.get("bodies", []))
                self.scanned = len(self.scanned_bodies)
                if self.scanned == 0 and h.get("scanned_count", 0) > 0:
                     self.scanned = h.get("scanned_count", 0)
            else:
                self.scanned = 0
                self.total = 0
                self.scanned_bodies.clear()

            self.organic_count = 0 # Reset bio count for new system
            self.system_bio_signals = 0
            self.last_scan_event = None
            self.valuable_system = False
            self.valuable_bodies.clear()
            self.system_traffic = {'day': 0, 'week': 0, 'total': 0}

            log_msg = f"JUMP: {self.current_sys}" if is_jump else f"LOCATION: {self.current_sys}"
            self.log(log_msg)
            
            sys_text = self.current_sys.upper()
            if self.star_class: sys_text += f" [{self.star_class}]"
            self.root.after(0, lambda: self.sys_stat.config(text=sys_text))
            self.root.after(0, lambda: self.valuable_list.delete(0, tk.END))
            self.update_nav_label()
            self.root.after(0, lambda: self.bio_stat.config(text=str(self.organic_count)))
            self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.root.after(0, self.update_waypoint_display)

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
            self.save_history()
            self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.edsm.enqueue(data, self.current_sys, self.current_coords)
            self.log(f"🔭 HONK: {self.total} bodies detected.")
            self.update_live_discord(data)

        elif ev == "FSSAllBodiesFound":
            if "SystemName" in data and data["SystemName"] == self.current_sys:
                self.total = data.get("Count", self.total)
                self.scanned = self.total
                self.save_history()
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.edsm.enqueue(data, self.current_sys, self.current_coords)
                self.log("📡 SYSTEM SCAN COMPLETE: All bodies found.")
        
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
                    self.save_history()
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                    self.last_scan_event = data

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
                        self.root.after(0, lambda: self.valuable_list.insert(tk.END, f"{icon} {body_name_str}"))

                    # --- Notification Logic ---
                    # Since this is a new scan, we always update.
                    self.update_live_discord(data)

    def poll_engine(self):
        path = self.config["journal_path"]
        if not os.path.exists(path): return

        files = sorted([os.path.join(path, f) for f in os.listdir(path) if f.startswith("Journal.")])
        if not files: return
        
        latest = files[-1]
        
        if not hasattr(self, 'last_journal') or latest != self.last_journal:
            if hasattr(self, 'last_journal'): # Avoid logging on the initial first load
                self.log(f"New game session detected, switching to: {os.path.basename(latest)}")
            self.last_journal = latest
            self.file_pos = 0
        
        route_f = os.path.join(path, "NavRoute.json")
        if os.path.exists(route_f):
            try:
                with open(route_f, 'r') as f:
                    data = json.load(f)
                    self.route_list = [r['StarSystem'] for r in data.get('Route', [])]
                    if self.route_list:
                        dest = data['Route'][-1]
                        self.dest_coords = dest['StarPos']
                        self.dest_name = dest['StarSystem']
                        self.update_nav_label()
            except: pass

        with open(self.last_journal, 'r', encoding='utf-8') as f:
            f.seek(self.file_pos)
            lines = f.readlines()
            
            if lines:
                for line in lines:
                    try:
                        self.process_event(json.loads(line))
                    except: pass
                
                if not self.is_first_load:
                    self.update_hud()
            
            if self.is_first_load and len(lines) > 0:
                self.is_first_load = False
                if self.config.get("discord_msg_system") != self.current_sys:
                    self.log("Stale Discord message detected. A new message will be created.")
                    self.discord.reset_msg_id()
                self.fetch_system_traffic(self.current_sys)
                # Once initial load is done, update the HUD to the final state.
                self.update_hud()
                self.update_live_discord()

            self.file_pos = f.tell()

    def check_cargo_file(self):
        if not self.cargo_hud: return
        
        path = self.config.get("journal_path")
        if not path: return
        
        c_file = os.path.join(path, "Cargo.json")
        if not os.path.exists(c_file): return
        
        try:
            mtime = os.path.getmtime(c_file)
            if not hasattr(self, 'last_cargo_mtime') or mtime != self.last_cargo_mtime:
                self.last_cargo_mtime = mtime
                with open(c_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        inventory = data.get("Inventory", [])
                        self.root.after(0, lambda: self.cargo_hud.update(inventory))
        except Exception:
            pass

    def threaded_poll_engine(self):
        while self.is_running:
            try:
                self.poll_engine()
                self.check_cargo_file()
            except Exception as e:
                logging.error(f"Poll Error: {e}")
            time.sleep(1)