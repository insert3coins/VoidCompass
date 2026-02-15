import os
import json
import threading
import math
import sqlite3
import logging
import time
import tkinter as tk
import webbrowser

from config import (
    load_config, CONFIG_FILE,
    COLOR_BG, COLOR_ACCENT, COLOR_TEXT
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
from dashboard_db_mixin import DashboardDBMixin
from dashboard_ui_mixin import DashboardUIMixin
from dashboard_scan_mixin import DashboardScanMixin


class MainDashboard(DashboardScanMixin, DashboardUIMixin, DashboardDBMixin):
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

    def _copy_waypoint_to_clipboard(self, waypoint_name, log_label="NEXT WAYPOINT"):
        if not waypoint_name:
            return False
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(waypoint_name)
            self.root.update()
            self.log(f"📋 COPIED {log_label}: {waypoint_name}")
            return True
        except Exception as e:
            self.log(f"❌ CLIPBOARD COPY FAILED: {e}")
            return False

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
        route_destination = None
        
        if self.waypoint_manager.waypoints:
            total_wp = len(self.waypoint_manager.waypoints)
            route_destination = self.waypoint_manager.waypoints[-1].get("name")
            
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
        hud_destination = route_destination if self.route_list else None
        self.root.after(0, lambda: self.hud.update(
            self.current_sys, self.dest_name, dist, 
            self.scanned, self.total, custom_r_pos, self.organic_count, self.system_traffic, game_r_pos,
            fss_summary, self.fss_summary_active, hud_destination
        ))
        self.update_scan_hud()

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
                    self._copy_waypoint_to_clipboard(next_wp, "NEXT WAYPOINT")

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
                copied_wp = next_wp
                log_label = "NEXT WAYPOINT"
                if not copied_wp and self.waypoint_manager.waypoints:
                    for wp in self.waypoint_manager.waypoints:
                        if not wp.get("visited", False):
                            copied_wp = wp.get("name")
                            log_label = "FIRST PENDING WAYPOINT (STARTUP)"
                            break
                if copied_wp:
                    self.root.after(0, lambda w=copied_wp, l=log_label: self._copy_waypoint_to_clipboard(w, l))

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
