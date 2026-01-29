import os
import json
import threading
import math
import logging
import time
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext

from config import (
    load_config, CONFIG_FILE,
    COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_ORANGE, COLOR_TEXT, COLOR_GREEN
)
from hud import TacticalHUD
from edsm_handler import EDSMHandler
from discord_handler import DiscordHandler
from settings_ui import open_settings

class MainDashboard:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.root.title("SURVEY ANALYSIS // v1.30")
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
        
        self.dest_coords = None
        self.current_coords = [0,0,0]
        self.dest_name = None
        self.route_list = []
        
        self.setup_layout()
        
        # Initialize Handlers
        self.edsm = EDSMHandler(self.config, self.update_edsm_status, self.update_queue_count)
        self.discord = DiscordHandler(self.config, self.root)
        
        if self.config.get("overlay_enabled", True):
            self.hud = TacticalHUD(self.root, self.config)
        else:
            self.hud = None
        
        threading.Thread(target=self.threaded_poll_engine, daemon=True).start()
        
        self.root.after(2000, self.verify_link)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_layout(self):
        nav = tk.Frame(self.root, bg=COLOR_PANEL, height=50, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        nav.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        tk.Label(nav, text=" > SURVEY_LOGGER_OS // V1.30", font=("Courier", 11, "bold"), fg=COLOR_ACCENT, bg=COLOR_PANEL).pack(side=tk.LEFT, padx=15)
        
        btn = tk.Button(nav, text="[ CONFIGURATION ]", command=self.open_settings, bg=COLOR_PANEL, fg=COLOR_ORANGE, font=("Courier", 9, "bold"), relief=tk.FLAT)
        btn.pack(side=tk.RIGHT, padx=15)
        
        body = tk.Frame(self.root, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.side = tk.Frame(body, bg=COLOR_PANEL, width=280, highlightbackground="#333", highlightthickness=1)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.side.pack_propagate(False)
        
        self.sys_stat = self.create_stat("CURRENT_SYSTEM", "---")
        self.scan_stat = self.create_stat("SCAN_PROGRESS", "0 / 0")
        self.bio_stat = self.create_stat("ORGANIC_LOGS", "0")
        self.edsm_stat = self.create_stat("EDSM_STATUS", "DISABLED")
        if not (self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key")): self.edsm_stat.config(fg="#666")
        self.queue_stat = self.create_stat("UPLOAD_QUEUE", "0")
        
        console_frame = tk.Frame(body, bg=COLOR_PANEL, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        console_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.log_box = scrolledtext.ScrolledText(console_frame, bg="#000", fg=COLOR_GREEN, font=("Courier", 10), borderwidth=0)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_stat(self, label, val):
        tk.Label(self.side, text=label, font=("Courier", 8), fg="#666", bg=COLOR_PANEL).pack(anchor="w", padx=20, pady=(10,0))
        l = tk.Label(self.side, text=val, font=("Courier", 11, "bold"), fg=COLOR_TEXT, bg=COLOR_PANEL)
        l.pack(anchor="w", padx=20)
        return l

    def log(self, msg):
        self.root.after(0, lambda: (self.log_box.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

    def update_edsm_status(self, text, color):
        self.root.after(0, lambda: self.edsm_stat.config(text=text, fg=color))

    def update_queue_count(self, count):
        self.root.after(0, lambda: self.queue_stat.config(text=str(count)))

    def on_close(self):
        """Save state and exit."""
        self.is_running = False
        self.edsm.stop()
        self.config["main_geometry"] = self.root.geometry()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        self.root.destroy()

    def open_settings(self):
        def on_save():
            if self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key"):
                self.edsm.status = "STANDBY"
                self.edsm_stat.config(text="STANDBY", fg=COLOR_TEXT)
            else:
                self.edsm.status = "DISABLED"
                self.edsm_stat.config(text="DISABLED", fg="#666")
        
        open_settings(self.root, self.config, on_save)

    def verify_link(self):
        if self.config.get("edsm_cmdr_name") and self.config.get("edsm_api_key"):
            self.log("INITIATING EDSM HANDSHAKE...")
            self.edsm.enqueue({"event": "Music", "MusicTrack": "NoTrack"}, self.current_sys, self.current_coords)
        else:
            self.log("EDSM Integration: DISABLED (No Credentials)")

    def update_live_discord(self, event_data=None):
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
            self.system_traffic = traffic_data
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
        
        r_pos = None
        if self.route_list and self.current_sys in self.route_list:
            r_pos = (self.route_list.index(self.current_sys)+1, len(self.route_list))
            
        self.root.after(0, lambda: self.hud.update(
            self.current_sys, self.dest_name, dist, 
            self.scanned, self.total, self.edsm.status, r_pos, self.organic_count, self.system_traffic
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
            self.edsm.enqueue(data, self.current_sys, self.current_coords)
            self.update_live_discord(data)
            
            self.root.after(0, lambda: self.bio_stat.config(text=str(self.organic_count)))

        elif ev == "Location" or ev == "FSDJump":
            is_jump = ev == "FSDJump"
            
            # State reset for new system
            self.current_sys = data.get("StarSystem", "Unknown")
            self.current_coords = data.get("StarPos", [0,0,0])
            self.star_class = data.get("StarClass", "")
            self.scanned = 0
            self.total = 0
            self.organic_count = 0 # Reset bio count for new system
            self.system_bio_signals = 0
            self.last_scan_event = None
            self.scanned_bodies.clear()
            self.valuable_system = False
            self.valuable_bodies.clear()
            self.system_traffic = {'day': 0, 'week': 0, 'total': 0}

            log_msg = f"JUMP: {self.current_sys}" if is_jump else f"LOCATION: {self.current_sys}"
            self.log(log_msg)
            self.root.after(0, lambda: self.sys_stat.config(text=self.current_sys.upper()))
            self.root.after(0, lambda: self.bio_stat.config(text=str(self.organic_count)))

            was_enqueued = self.edsm.enqueue(data, self.current_sys, self.current_coords)
            if was_enqueued:
                if is_jump:
                    # It's a new jump, so reset the Discord message for the new system.
                    self.discord.reset_msg_id()
                self.update_live_discord(data)
            
            self.fetch_system_traffic(self.current_sys)

        elif ev == "FSSDiscoveryScan":
            if "SystemName" in data and data["SystemName"] != self.current_sys:
                return
            self.total = data.get("BodyCount", self.total)
            self.edsm.enqueue(data, self.current_sys, self.current_coords)
            self.update_live_discord(data)
        
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

                    # --- Notification Logic ---
                    # Since this is a new scan, we always update.
                    self.update_live_discord(data)

        if not self.is_first_load:
            self.update_hud()

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
            except: pass

        with open(self.last_journal, 'r', encoding='utf-8') as f:
            f.seek(self.file_pos)
            lines = f.readlines()
            
            for line in lines:
                try:
                    self.process_event(json.loads(line))
                except: pass
            
            if self.is_first_load and len(lines) > 0:
                self.is_first_load = False
                if self.config.get("discord_msg_system") != self.current_sys:
                    self.log("Stale Discord message detected. A new message will be created.")
                    self.discord.reset_msg_id()
                # Once initial load is done, update the HUD to the final state.
                self.update_hud()

            self.file_pos = f.tell()

    def threaded_poll_engine(self):
        while self.is_running:
            try:
                self.poll_engine()
            except Exception as e:
                logging.error(f"Poll Error: {e}")
            time.sleep(1)