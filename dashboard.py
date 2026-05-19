import os
import json
import threading
import math
import sqlite3
import logging
import time
import tkinter as tk
import webbrowser
from collections import deque

from config import (
    load_config, CONFIG_FILE,
    COLOR_BG, COLOR_ACCENT, COLOR_TEXT
)
from version import APP_VERSION
from hud import TacticalHUD
from cargo_hud import CargoHUD
from scan_hud import ScanHUD
from edsm_handler import EDSMHandler
from screenshot_handler import ScreenshotHandler
from settings_ui import open_settings
from route_plotter import RoutePlotter
from waypoint_manager import WaypointManager
from journal_watcher import JournalWatcher
from mining_window import MiningWindow
from runtime_trace import RuntimeTrace
from dashboard_db_mixin import DashboardDBMixin
from dashboard_ui_mixin import DashboardUIMixin
from dashboard_scan_mixin import DashboardScanMixin


class MainDashboard(DashboardScanMixin, DashboardUIMixin, DashboardDBMixin):
    @staticmethod
    def _to_float(value, default=None):
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

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
        self.last_bio_scan = {}
        self.cargo_capacity = 0
        self.last_journal_event_ts = 0.0
        self.last_logged_journal_file = None
        self.last_status_event_ts = 0.0
        self.last_nav_event_ts = 0.0
        self.last_cargo_event_ts = 0.0
        self.last_edsm_event_ts = 0.0
        self.last_edsm_request_ts = 0.0
        self._event_rate_ts = deque(maxlen=1200)
        # HUD source freshness thresholds (ok_age, warn_age) tuned for real flight cadence.
        self.hud_source_thresholds = {
            "J": (4.0, 20.0),    # Journal stream
            "S": (4.0, 20.0),    # Status.json stream
            "N": (20.0, 90.0),   # NavRoute.json updates are sparse
            "C": (25.0, 120.0),  # Cargo.json updates are sparse
            "E": (45.0, 180.0),  # EDSM network callbacks are slower and bursty
        }
        
        self.dest_coords = None
        self.current_coords = [0,0,0]
        self.dest_name = None
        self.route_list = []
        self.session_start_ts = time.time()
        self.session_jump_count = 0
        self.session_ly = 0.0
        self.target_lat = self._to_float(self.config.get("ground_target_lat"), 0.0)
        self.target_lon = self._to_float(self.config.get("ground_target_lon"), 0.0)
        self.target_latlon_active = bool(self.config.get("ground_target_active", False))
        self.current_latitude = None
        self.current_longitude = None
        self.current_heading = None
        self.current_planet_radius = None
        self.on_planet = False
        self._ground_last_on_planet = False
        self.ground_popup = None
        self.ground_popup_header = None
        self.ground_popup_line1 = None
        self.ground_popup_line2 = None
        self.ground_popup_canvas = None
        self.ground_popup_drag_origin = None
        self._ground_popup_visible = False
        self._ground_popup_compass_ids = None
        self.ground_popup_enabled = bool(self.config.get("ground_popup_enabled", True))
        self._ground_ui_needs_update = False
        self._ground_last_status_key = None
        self._pending_status_data = None
        self._status_dispatch_scheduled = False
        self.log_filter = "ALL"
        self.log_entries = []
        self.event_feed_entries = []
        self.event_feed_filter = "ALL"
        self.event_feed_view = []
        self.event_feed_max_entries = 150
        self.event_feed_display_limit = 80
        self.dashboard_refresh_job = None
        self.dashboard_refresh_full_pending = False
        self._hud_refresh_job = None
        self._hud_refresh_requested = False
        self._last_hud_refresh_ts = 0.0
        self._hud_refresh_interval_ms = 120
        self._perf_spike_threshold_ms = float(self.config.get("perf_spike_threshold_ms", 45.0))
        self._perf_emit_min_interval_s = 0.75
        self._perf_last_emit_ts = {}
        self._ui_watchdog_interval_ms = 50
        self._ui_watchdog_spike_ms = float(self.config.get("ui_watchdog_spike_ms", 120.0))
        self._ui_watchdog_last_ts = time.perf_counter()
        self._overlay_pos_last_saved = {"hud": None, "cargo": None, "scan": None}
        self._overlay_sync_grace_until = time.time() + 4.0
        self.runtime_trace = RuntimeTrace(
            self.config.get("runtime_trace_path", "runtime_trace.log"),
            enabled=bool(self.config.get("runtime_trace_enabled", True)),
        )
        self.runtime_trace.start()
        
        self.setup_layout()
        self.waypoint_manager = WaypointManager()
        self.route_plotter = None
        self.target_waypoint = None
        self.waypoint_cache = {}
        
        # Initialize Handlers
        self.edsm = EDSMHandler(self.config)
        self.screenshots = ScreenshotHandler(
            self.config,
            lambda: self.current_sys,
            self.log,
            trace_callback=self._trace_record_ms,
        )
        self.mining_window = None
        
        if self.config.get("overlay_enabled", True):
            self.hud = TacticalHUD(self.root, self.config, on_widget_click=self._on_hud_widget_click)
            try:
                hx = int(float(self.config.get("hud_x", 100)))
                hy = int(float(self.config.get("hud_y", 100)))
                self.hud.win.geometry(f"+{hx}+{hy}")
            except Exception:
                pass
        else:
            self.hud = None
            
        if self.config.get("cargo_overlay_enabled", False):
            self.cargo_hud = CargoHUD(self.root, self.config)
            try:
                cx = int(float(self.config.get("cargo_hud_x", self.cargo_hud.win.winfo_x())))
                cy = int(float(self.config.get("cargo_hud_y", self.cargo_hud.win.winfo_y())))
                self.cargo_hud.win.geometry(f"+{cx}+{cy}")
            except Exception:
                pass
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
        
        self.watcher = JournalWatcher(
            self.config.get("journal_path"),
            trace_callback=self._trace_record_ms,
            config=self.config,
        )
        self.watcher.register_callback(
            event_cb=self.process_event,
            batch_cb=self.process_batch,
            cargo_cb=self.update_cargo,
            nav_cb=self.update_nav_route,
            status_cb=self.update_status
        )
        self.watcher.start()
        self.cargo_capacity = self.watcher.get_latest_cargo_capacity()
        
        self.watcher.force_check_status()
        
        threading.Thread(target=self.check_updates, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log(
            f"CONFIG FILE: {CONFIG_FILE} | HUD({self.config.get('hud_x')},{self.config.get('hud_y')}) "
            f"| CARGO({self.config.get('cargo_hud_x')},{self.config.get('cargo_hud_y')})"
        )
        self.root.after(120, self._reapply_overlay_positions)
        self.update_hud()
        self.update_ground_target_ui()
        self._tick_ground_target()
        self._tick_session_clock()
        self._tick_ui_stall_watchdog()
        self._tick_runtime_trace()
        self._tick_overlay_position_sync()

    def _reapply_overlay_positions(self):
        try:
            if self.hud and self.hud.win and self.hud.win.winfo_exists():
                hx = int(float(self.config.get("hud_x", self.hud.win.winfo_x())))
                hy = int(float(self.config.get("hud_y", self.hud.win.winfo_y())))
                self.hud.win.geometry(f"460x180+{hx}+{hy}")
        except Exception:
            pass
        try:
            if self.cargo_hud and self.cargo_hud.win and self.cargo_hud.win.winfo_exists():
                cx = int(float(self.config.get("cargo_hud_x", self.cargo_hud.win.winfo_x())))
                cy = int(float(self.config.get("cargo_hud_y", self.cargo_hud.win.winfo_y())))
                self.cargo_hud.win.geometry(f"300x400+{cx}+{cy}")
        except Exception:
            pass
        self.root.after(250, self._log_applied_overlay_positions)

    def _log_applied_overlay_positions(self):
        try:
            hxy = "-"
            cxy = "-"
            if self.hud and self.hud.win and self.hud.win.winfo_exists():
                hxy = f"{self.hud.win.winfo_x()},{self.hud.win.winfo_y()}"
            if self.cargo_hud and self.cargo_hud.win and self.cargo_hud.win.winfo_exists():
                cxy = f"{self.cargo_hud.win.winfo_x()},{self.cargo_hud.win.winfo_y()}"
            self.log(f"CONFIG FILE: APPLIED HUD({hxy}) | CARGO({cxy})")
        except Exception:
            pass

    @staticmethod
    def _perf_start():
        return time.perf_counter()

    def _trace_record_ms(self, label, elapsed_ms):
        if self.runtime_trace:
            self.runtime_trace.record_ms(label, elapsed_ms)

    def _trace_bump(self, label, amount=1):
        if self.runtime_trace:
            self.runtime_trace.bump(label, amount)

    def _tick_runtime_trace(self):
        if not self.is_running:
            return
        extra = {
            "route_waypoints": len(getattr(self.waypoint_manager, "waypoints", []) or []),
            "scan_items": len(getattr(self, "scan_items", []) or []),
            "log_entries": len(getattr(self, "log_entries", []) or []),
            "event_feed_entries": len(getattr(self, "event_feed_entries", []) or []),
        }
        if self.runtime_trace:
            self.runtime_trace.flush(extra=extra)
        self.root.after(1000, self._tick_runtime_trace)

    def _tick_overlay_position_sync(self):
        if not self.is_running:
            return
        changed = False
        now = time.time()
        try:
            if self.hud and self.hud.win and self.hud.win.winfo_exists():
                pos = (int(self.hud.win.winfo_x()), int(self.hud.win.winfo_y()))
                cfg_pos = (
                    int(float(self.config.get("hud_x", pos[0]))),
                    int(float(self.config.get("hud_y", pos[1]))),
                )
                if now < self._overlay_sync_grace_until and pos == (0, 0) and cfg_pos != (0, 0):
                    pos = cfg_pos
                if self._overlay_pos_last_saved.get("hud") != pos:
                    self._overlay_pos_last_saved["hud"] = pos
                    self.config["hud_x"], self.config["hud_y"] = pos
                    changed = True
        except Exception:
            pass
        try:
            if self.cargo_hud and self.cargo_hud.win and self.cargo_hud.win.winfo_exists():
                pos = (int(self.cargo_hud.win.winfo_x()), int(self.cargo_hud.win.winfo_y()))
                cfg_pos = (
                    int(float(self.config.get("cargo_hud_x", pos[0]))),
                    int(float(self.config.get("cargo_hud_y", pos[1]))),
                )
                if now < self._overlay_sync_grace_until and pos == (0, 0) and cfg_pos != (0, 0):
                    pos = cfg_pos
                if self._overlay_pos_last_saved.get("cargo") != pos:
                    self._overlay_pos_last_saved["cargo"] = pos
                    self.config["cargo_hud_x"], self.config["cargo_hud_y"] = pos
                    changed = True
        except Exception:
            pass
        try:
            if self.scan_hud and self.scan_hud.win and self.scan_hud.win.winfo_exists():
                pos = (int(self.scan_hud.win.winfo_x()), int(self.scan_hud.win.winfo_y()))
                if self._overlay_pos_last_saved.get("scan") != pos:
                    self._overlay_pos_last_saved["scan"] = pos
                    self.config["scan_hud_x"], self.config["scan_hud_y"] = pos
                    changed = True
        except Exception:
            pass
        if changed:
            self._save_config_file()
        self.root.after(700, self._tick_overlay_position_sync)

    def _perf_spike(self, label, started_at, threshold_ms=None):
        threshold = self._perf_spike_threshold_ms if threshold_ms is None else float(threshold_ms)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        self._trace_record_ms(label, elapsed_ms)
        if elapsed_ms < threshold:
            return
        now = time.time()
        last = self._perf_last_emit_ts.get(label, 0.0)
        if (now - last) < self._perf_emit_min_interval_s:
            return
        self._perf_last_emit_ts[label] = now
        msg = f"PERF SPIKE [{label}] {elapsed_ms:.1f} ms"
        print(msg, flush=True)
        logging.warning(msg)
        self.log(msg)

    def _tick_ui_stall_watchdog(self):
        if not self.is_running:
            return
        now = time.perf_counter()
        delta_ms = (now - self._ui_watchdog_last_ts) * 1000.0
        self._ui_watchdog_last_ts = now
        overrun_ms = delta_ms - float(self._ui_watchdog_interval_ms)
        if overrun_ms >= self._ui_watchdog_spike_ms:
            now_ts = time.time()
            last = self._perf_last_emit_ts.get("UI_STALL", 0.0)
            if (now_ts - last) >= self._perf_emit_min_interval_s:
                self._perf_last_emit_ts["UI_STALL"] = now_ts
                msg = f"UI STALL [{delta_ms:.1f} ms tick, +{overrun_ms:.1f} ms overrun]"
                print(msg, flush=True)
                logging.warning(msg)
                self.log(msg)
                self._trace_record_ms("ui_stall_overrun", overrun_ms)
        self.root.after(self._ui_watchdog_interval_ms, self._tick_ui_stall_watchdog)

    def on_close(self):
        """Save state and exit."""
        self.is_running = False
        
        if self.route_plotter and self.route_plotter.win.winfo_exists():
            self.route_plotter.on_close()
        if self.mining_window and self.mining_window.is_open():
            self.mining_window.on_close()
            
        self.watcher.stop()
        self.screenshots.stop()
        try:
            if self.hud and self.hud.win and self.hud.win.winfo_exists():
                self.config["hud_x"] = int(self.hud.win.winfo_x())
                self.config["hud_y"] = int(self.hud.win.winfo_y())
        except Exception:
            pass
        try:
            if self.cargo_hud and self.cargo_hud.win and self.cargo_hud.win.winfo_exists():
                self.config["cargo_hud_x"] = int(self.cargo_hud.win.winfo_x())
                self.config["cargo_hud_y"] = int(self.cargo_hud.win.winfo_y())
        except Exception:
            pass
        try:
            if self.scan_hud and self.scan_hud.win and self.scan_hud.win.winfo_exists():
                self.config["scan_hud_x"] = int(self.scan_hud.win.winfo_x())
                self.config["scan_hud_y"] = int(self.scan_hud.win.winfo_y())
        except Exception:
            pass
        self.config["main_geometry"] = self.root.geometry()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        if hasattr(self, 'conn'):
            try:
                self.conn.commit()
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.conn.close()
            except: pass
        if self.runtime_trace:
            try:
                self.runtime_trace.flush(extra={"shutdown": True})
            except Exception:
                pass
        self._destroy_ground_popup()
        self.root.destroy()

    def _save_config_file(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    @staticmethod
    def _normalize_lon(delta):
        return ((delta + 180.0) % 360.0) - 180.0

    @staticmethod
    def _bearing_deg(lat1, lon1, lat2, lon2):
        lat1_r = math.radians(lat1)
        lon1_r = math.radians(lon1)
        lat2_r = math.radians(lat2)
        lon2_r = math.radians(lon2)
        x = math.cos(lat2_r) * math.sin(lon2_r - lon1_r)
        y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(lon2_r - lon1_r)
        bearing = math.degrees(math.atan2(x, y))
        if bearing < 0:
            bearing += 360.0
        return bearing

    @staticmethod
    def _surface_distance_m(lat1, lon1, lat2, lon2, radius_m):
        if radius_m is None or radius_m <= 0:
            return None
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlon_r = math.radians(lon2 - lon1)
        z = (math.sin(lat1_r) * math.sin(lat2_r)) + (math.cos(lat1_r) * math.cos(lat2_r) * math.cos(dlon_r))
        z = max(-1.0, min(1.0, z))
        return math.acos(z) * radius_m

    @staticmethod
    def _format_ground_distance(distance_m):
        if distance_m is None:
            return "---"
        if distance_m < 1000.0:
            return f"{distance_m:,.0f} m"
        return f"{distance_m / 1000.0:,.2f} km"

    @staticmethod
    def _format_direction(delta_deg):
        abs_delta = abs(delta_deg)
        if abs_delta <= 12:
            return "AHEAD"
        if abs_delta >= 168:
            return "BEHIND"
        return "RIGHT" if delta_deg > 0 else "LEFT"

    def _tick_ground_target(self):
        if not self.is_running:
            return
        if self._ground_ui_needs_update and not self.batch_mode:
            self._ground_ui_needs_update = False
            try:
                self.update_ground_target_ui()
            except Exception:
                pass
        self.root.after(220, self._tick_ground_target)

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
        self.route_plotter = RoutePlotter(
            self.root,
            self.edsm,
            self.current_coords,
            self.current_sys,
            self.config,
            self.waypoint_manager,
            on_change_callback=self.update_waypoint_display,
            event_callback=self._on_route_event,
        )

    def open_mining_window(self):
        if self.mining_window and self.mining_window.is_open():
            self.mining_window.lift()
            return
        self.mining_window = MiningWindow(
            self.root,
            self.config,
            get_current_system=lambda: self.current_sys,
            get_cargo_capacity=lambda: self.cargo_capacity,
            get_current_coords=lambda: self.current_coords,
        )
        try:
            self.watcher.force_check_cargo()
            self.watcher.force_check_status()
        except Exception:
            pass

    def _on_route_event(self, tag, message, severity="INFO", copy_text=None, system_name=None, pinned=False):
        if not message:
            return
        sev = str(severity or "INFO").upper()
        if sev == "FAIL":
            self.log(f"❌ ROUTE: {message}")
            return
        event_tag = (tag or "ROUTE").upper()
        sys_name = system_name or self.current_sys
        url = None
        if sys_name and sys_name not in ("---", "Unknown"):
            url = f"https://www.edsm.net/show-system?systemName={str(sys_name).replace(' ', '+')}"
        self.add_event_feed_entry(
            event_tag,
            message,
            severity=severity,
            copy_text=copy_text,
            url=url,
            pinned=pinned,
        )

    @staticmethod
    def _normalize_body_id(body_id):
        if body_id is None:
            return None
        try:
            return int(body_id)
        except Exception:
            return body_id

    def open_settings(self):
        def on_save():
            self.log("Configuration saved successfully.")

            # Live Update: Screenshots
            if self.config.get("screenshots_enabled", False):
                self.log("Screenshot Converter: ACTIVE")
            else:
                self.log("Screenshot Converter: DISABLED")

            # Live Toggle: Tactical HUD
            if self.config.get("overlay_enabled", True):
                if self.hud is None:
                    self.hud = TacticalHUD(self.root, self.config, on_widget_click=self._on_hud_widget_click)
                self.update_hud()
            else:
                if self.hud:
                    self.hud.win.destroy()
                    self.hud = None

            # Live Toggle: Cargo HUD
            if self.config.get("cargo_overlay_enabled", False):
                if self.cargo_hud is None:
                    self.cargo_hud = CargoHUD(self.root, self.config)
                    self.cargo_capacity = self.watcher.get_latest_cargo_capacity()
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

    def fetch_system_traffic(self, system_name):
        self.last_edsm_request_ts = time.time()
        def callback(traffic_data):
            def _apply():
                if self.current_sys != system_name:
                    return
                self.last_edsm_event_ts = time.time()
                self.system_traffic = traffic_data
                self.update_dashboard_ui()
                self.update_hud()
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
            self.add_event_feed_entry("ROUTE", f"Copied {log_label}: {waypoint_name}", severity="INFO", copy_text=waypoint_name)
            return True
        except Exception as e:
            self.log(f"❌ CLIPBOARD COPY FAILED: {e}")
            return False

    def _run_scheduled_hud_refresh(self):
        t0 = self._perf_start()
        self._hud_refresh_job = None
        if not self._hud_refresh_requested:
            return
        self._hud_refresh_requested = False
        self._last_hud_refresh_ts = time.time()
        self._perform_hud_update()
        # If additional requests came in while rendering, schedule one more pass.
        if self._hud_refresh_requested and self._hud_refresh_job is None:
            self._hud_refresh_job = self.root.after(self._hud_refresh_interval_ms, self._run_scheduled_hud_refresh)
        self._perf_spike("_run_scheduled_hud_refresh", t0, threshold_ms=35.0)

    def update_hud(self):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, self.update_hud)
            return
        self._hud_refresh_requested = True
        if self._hud_refresh_job is not None:
            return
        now = time.time()
        elapsed_ms = int((now - self._last_hud_refresh_ts) * 1000.0)
        delay = 0 if elapsed_ms >= self._hud_refresh_interval_ms else (self._hud_refresh_interval_ms - elapsed_ms)
        self._hud_refresh_job = self.root.after(delay, self._run_scheduled_hud_refresh)

    def _perform_hud_update(self):
        t0 = self._perf_start()
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
        route_counts = None
        
        if self.waypoint_manager.waypoints:
            total_wp = len(self.waypoint_manager.waypoints)
            route_destination = self.waypoint_manager.waypoints[-1].get("name")
            
            visited_count = sum(1 for wp in self.waypoint_manager.waypoints if wp.get('visited', False))
            route_counts = (visited_count, total_wp)
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

        hud_destination = route_destination if self.route_list else None
        hud_health = self._build_hud_health()
        hud_status = hud_health.get("status", "OK")
        if not self.is_running or not self.watcher or not self.watcher.is_running:
            hud_status = "FAIL"
        else:
            has_alerts = (
                self.system_undiscovered
                or self.system_bio_signals > 0
                or bool(self.valuable_bodies)
                or self.fss_summary_active
            )
            if has_alerts:
                hud_status = "ALERT"
        self.root.after(0, lambda: self.hud.update(
            self.current_sys, self.dest_name, dist, 
            self.scanned, self.total, custom_r_pos, self.organic_count, self.system_traffic, game_r_pos,
            hud_destination, route_counts, hud_status, hud_health
        ))
        self.update_scan_hud()
        self._perf_spike("_perform_hud_update", t0, threshold_ms=30.0)

    def _record_journal_event(self):
        now = time.time()
        self.last_journal_event_ts = now
        self._event_rate_ts.append(now)
        cutoff = now - 120
        while self._event_rate_ts and self._event_rate_ts[0] < cutoff:
            self._event_rate_ts.popleft()

    @staticmethod
    def _source_state_for_age(age_seconds, ok_age, warn_age, unknown_state="FAIL"):
        if age_seconds is None:
            return unknown_state
        if age_seconds <= ok_age:
            return "OK"
        if age_seconds <= warn_age:
            return "WARN"
        return "FAIL"

    def _build_event_rate_sparkline(self, width=16, bucket_seconds=2):
        now = time.time()
        buckets = [0] * width
        horizon = width * bucket_seconds
        cutoff = now - horizon
        for ts in self._event_rate_ts:
            if ts < cutoff:
                continue
            idx = int((now - ts) // bucket_seconds)
            if 0 <= idx < width:
                buckets[width - 1 - idx] += 1
        return buckets

    def _build_hud_health(self):
        now = time.time()
        watcher_alive = bool(self.watcher and self.watcher.is_running)

        def _age(ts):
            return (now - ts) if ts else None

        age_j = _age(self.last_journal_event_ts)
        age_s = _age(self.last_status_event_ts)
        age_n = _age(self.last_nav_event_ts)
        age_c = _age(self.last_cargo_event_ts)
        age_e = _age(self.last_edsm_event_ts)

        j_ok, j_warn = self.hud_source_thresholds["J"]
        s_ok, s_warn = self.hud_source_thresholds["S"]
        n_ok, n_warn = self.hud_source_thresholds["N"]
        c_ok, c_warn = self.hud_source_thresholds["C"]
        e_ok, e_warn = self.hud_source_thresholds["E"]
        source_states = {
            "J": "FAIL" if not watcher_alive else self._source_state_for_age(age_j, j_ok, j_warn, unknown_state="WARN"),
            "S": self._source_state_for_age(age_s, s_ok, s_warn, unknown_state="WARN"),
            # N/C/E can be legitimately idle for long periods; start in WARN until seen.
            "N": self._source_state_for_age(age_n, n_ok, n_warn, unknown_state="WARN"),
            "C": self._source_state_for_age(age_c, c_ok, c_warn, unknown_state="WARN"),
            "E": self._source_state_for_age(age_e, e_ok, e_warn, unknown_state="WARN"),
        }

        alert_reason = "OK"
        if not watcher_alive:
            alert_reason = "FAIL"
        elif self.system_undiscovered:
            alert_reason = "DISC"
        elif self.system_bio_signals > 0:
            alert_reason = "BIO"
        elif bool(self.valuable_bodies):
            alert_reason = "VAL"
        elif self.fss_summary_active:
            alert_reason = "FSS"
        elif source_states["E"] == "FAIL" and self.last_edsm_request_ts > 0 and (now - self.last_edsm_request_ts) > 60.0:
            alert_reason = "NET"

        # Confidence score (0-100) based on source health and watcher state.
        score = 100
        if not watcher_alive:
            score -= 35
        for key, weight in (("J", 25), ("S", 15), ("N", 10), ("C", 10), ("E", 15)):
            state = source_states.get(key, "FAIL")
            if state == "WARN":
                score -= int(weight * 0.5)
            elif state == "FAIL":
                score -= weight
        if alert_reason in ("BIO", "VAL", "FSS", "DISC", "NET", "FAIL"):
            score -= 8
        confidence = max(0, min(100, score))

        status = "OK"
        if alert_reason in ("BIO", "VAL", "FSS", "DISC", "NET"):
            status = "ALERT"
        if alert_reason == "FAIL":
            status = "FAIL"
        if not watcher_alive:
            status = "FAIL"

        mini_stats = [
            f"SCAN {self.scanned}/{self.total}",
            f"BIO {self.organic_count}",
            f"VAL {len(self.valuable_bodies)}",
            f"ROUTE {len(self.route_list)}",
            f"TRAF {self.system_traffic.get('day', 0)}/{self.system_traffic.get('week', 0)}",
            f"HLTH {confidence}%",
        ]

        return {
            "status": status,
            "reason": alert_reason,
            "confidence": confidence,
            "age_journal": age_j,
            "age_by_source": {
                "J": age_j,
                "S": age_s,
                "N": age_n,
                "C": age_c,
                "E": age_e,
            },
            "source_states": source_states,
            "spark": self._build_event_rate_sparkline(),
            "mini_stats": mini_stats,
        }

    def _on_hud_widget_click(self, payload):
        reason = None
        source = None
        if isinstance(payload, dict):
            reason = (payload.get("reason") or "").upper()
            source = (payload.get("source") or "").upper()

        if source == "E":
            self.set_event_feed_filter("SYSTEM")
        elif source == "N":
            self.set_event_feed_filter("ROUTE")
        elif source == "C":
            self.set_event_feed_filter("SYSTEM")
        elif reason == "VAL":
            self.set_event_feed_filter("VALUABLE")
        elif reason in ("BIO", "DISC"):
            self.set_event_feed_filter("ALERT")
        elif reason == "FSS":
            self.set_event_feed_filter("SCAN")
        else:
            self.set_event_feed_filter("ALL")
        self.root.after(0, self.root.lift)

    def process_event(self, data):
        ev = data.get("type") or data.get("event")
        raw = data.get("raw", data)
        d = data.get("data", data)
        self._record_journal_event()
        current_journal = getattr(self.watcher, "last_journal", None)
        if current_journal and current_journal != self.last_logged_journal_file:
            self.last_logged_journal_file = current_journal
            self.log(f"Journal file: {os.path.basename(current_journal)}")
        if self.mining_window and self.mining_window.is_open():
            self.mining_window.process_event(data)
        
        if ev in ("FileHeader", "Fileheader"):
            self.log(f"Game version detected: {d.get('gameversion')} ({d.get('build')})")

        elif ev == "Loadout":
            self.cargo_capacity = d.get("cargo_capacity", 0)
            self.watcher.force_check_cargo()

        elif ev == "Cargo":
            # Journal can emit Cargo before/without immediate file polling update.
            self.watcher.force_check_cargo()

        elif ev in ("NavRoute", "NavRouteClear"):
            # Nav route details live in NavRoute.json; trigger immediate refresh.
            self.watcher.force_check_nav()

        elif ev == "Commander":
            self.cmdr_name = d.get("name", "CMDR")

        elif ev == "LoadGame":
            self.cmdr_name = d.get("commander", "CMDR")
            game_version = d.get("gameversion")
            game_build = d.get("build")
            if game_version and game_build:
                self.log(f"Game version detected from LoadGame: {game_version} ({game_build})")

        elif ev == "ScanOrganic":
            body_id = self._normalize_body_id(d.get("body_id"))
            body_label = d.get("body_name") or (f"Body {body_id}" if body_id is not None else "Unknown Body")
            species = d.get("species") or d.get("genus") or "Organic"
            species_key = f"{body_id}|{species}" if body_id is not None else f"{body_label}|{species}"

            existing = self.last_bio_scan.get(species_key, {})
            is_complete = bool(d.get("is_complete"))
            was_complete = bool(existing.get("is_complete"))

            self.last_bio_scan[species_key] = {
                "body_id": body_id,
                "body_name": body_label,
                "species": species,
                "sample_idx": d.get("sample_idx"),
                "scan_type": d.get("scan_type"),
                "is_new_entry": bool(d.get("is_new_entry")),
                "is_new_sample": bool(d.get("is_new_sample")),
                "is_complete": is_complete,
            }

            if is_complete and not was_complete:
                self.organic_count += 1
                self.add_event_feed_entry("BIO", f"Organic complete: {species} ({body_label})", severity="INFO", copy_text=species)
            elif d.get("is_new_sample"):
                sample_idx = d.get("sample_idx")
                sample_txt = f" sample {sample_idx}" if sample_idx is not None else ""
                self.add_event_feed_entry("BIO", f"Organic{sample_txt}: {species} ({body_label})", severity="INFO", copy_text=species)

            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()

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
            evt_tag = "JUMP" if is_jump else "SYSTEM"
            evt_msg = f"{'Arrived' if is_jump else 'Location set'}: {self.current_sys}"
            self.add_event_feed_entry(evt_tag, evt_msg, severity="INFO", copy_text=self.current_sys, url=f"https://www.edsm.net/show-system?systemName={self.current_sys.replace(' ', '+')}")
            
            if not self.batch_mode:
                sys_text = self.current_sys.upper()
                if self.star_class: sys_text += f" [{self.star_class}]"
                self.root.after(0, lambda: self.sys_stat.config(text=sys_text))
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

            if self.current_sys != self.last_traffic_system:
                self.last_traffic_system = self.current_sys
                self.fetch_system_traffic(self.current_sys)

        elif ev == "FSSDiscoveryScan":
            if d.get("system_name") and d.get("system_name") != self.current_sys:
                return
            self.total = d.get("body_count", self.total)
            progress = d.get("progress")
            if isinstance(progress, (int, float)) and progress > 0 and self.total > 0:
                self.scanned = max(self.scanned, min(self.total, int(round(self.total * progress))))
            self.fss_all_bodies = False
            self.db_update_system(self.current_sys, self.total, self.scanned)
            if not self.batch_mode:
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.log(f"🔭 HONK: {self.total} bodies detected.")
            self.add_event_feed_entry("SCAN", f"Honk complete: {self.total} bodies", severity="INFO", copy_text=self.current_sys)
            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()

        elif ev == "DiscoveryScan":
            discovered = d.get("bodies", 0)
            if isinstance(discovered, int) and discovered > 0:
                self.total = max(self.total, self.scanned + discovered)
                self.db_update_system(self.current_sys, self.total, self.scanned)
                if not self.batch_mode:
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                    self.update_hud()
                    self.schedule_dashboard_refresh()

        elif ev == "NavBeaconScan":
            count = d.get("num_bodies", 0)
            if isinstance(count, int) and count > 0:
                self.total = max(self.total, count)
                self.db_update_system(self.current_sys, self.total, self.scanned)
                self.add_event_feed_entry("SCAN", f"Nav beacon scan: {count} bodies", severity="INFO", copy_text=self.current_sys)
                if not self.batch_mode:
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
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
                self.add_event_feed_entry("ALERT", "FSS complete: all bodies found", severity="WARN", copy_text=self.current_sys)
                if not self.batch_mode:
                    self.update_hud()
                    self.schedule_dashboard_refresh()
        
        elif ev == "FSSBodySignals":
            body_id = self._normalize_body_id(d.get("body_id"))
            if body_id is not None:
                bio_count = d.get("bio_count", 0)
                geo_count = d.get("geo_count", 0)
                self.body_signals[body_id] = {"bio": bio_count, "geo": geo_count}
                if bio_count:
                    self.system_bio_signals = max(self.system_bio_signals, bio_count)
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

        elif ev == "SAASignalsFound":
            body_id = self._normalize_body_id(d.get("body_id"))
            if body_id is not None:
                bio_count = d.get("bio_count", 0)
                geo_count = d.get("geo_count", 0)
                if bio_count or geo_count:
                    self.body_signals[body_id] = {"bio": bio_count, "geo": geo_count}
                    self.system_bio_signals = max(self.system_bio_signals, bio_count)
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
            body_id = self._normalize_body_id(d.get("body_id"))
            if body_id is not None:
                self.body_dss_complete.add(body_id)
                item = self.scan_items_by_id.get(body_id)
                if item:
                    item["dss_complete"] = True
                    if item.get("_ts") is None:
                        item["_ts"] = int(time.time())
                    self.save_scan_item_to_db(self.current_sys, item)
                    body_label = item.get("name") or f"Body {body_id}"
                    self.add_event_feed_entry("DSS", f"DSS complete: {body_label}", severity="INFO", copy_text=body_label)
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
        
        elif ev == "Scan":
            body_name = d.get("body_name", "")
            body_id = self._normalize_body_id(d.get("body_id"))
            if body_id is None:
                body_id = body_name

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

                    body_label = body_name or "Unknown Body"
                    landable_marker = " 🚀" if d.get("landable") else ""
                    self.add_event_feed_entry("SCAN", f"{body_label}{landable_marker}", severity="INFO", copy_text=body_label)

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
                        self.add_event_feed_entry("VALUABLE", f"{icon} Valuable world: {body_name_str}", severity="WARN", copy_text=body_name_str, pinned=True)
                    if is_system_star_scan and d.get("was_discovered") is False:
                        self.add_event_feed_entry("ALERT", "Undiscovered system star scanned", severity="WARN", copy_text=self.current_sys)

    def process_batch(self, events):
        self.batch_mode = True
        try:
            with self.db_lock:
                try:
                    self.conn.execute("BEGIN TRANSACTION")
                    in_transaction = True
                except Exception as e:
                    in_transaction = False
                    logging.warning(f"Batch transaction unavailable: {e}")
                for ev in events:
                    try:
                        self.process_event(ev)
                    except Exception as e:
                        ev_type = ev.get("type") if isinstance(ev, dict) else "UNKNOWN"
                        logging.warning(f"Batch event failed [{ev_type}]: {e}")
                if in_transaction:
                    try:
                        self.conn.commit()
                    except Exception as e:
                        logging.warning(f"Batch commit failed: {e}")
                        try:
                            self.conn.rollback()
                        except Exception:
                            pass
        finally:
            self.batch_mode = False
        self.root.after(0, self.update_dashboard_ui)
        self.root.after(0, self.update_hud)
        
        if self.is_first_load:
            self.is_first_load = False
            self.last_traffic_system = self.current_sys
            self.fetch_system_traffic(self.current_sys)
            self.update_hud()
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
        self.last_cargo_event_ts = time.time()
        if self.mining_window and self.mining_window.is_open():
            self.mining_window.update_cargo(inventory, self.cargo_capacity)
        if self.cargo_hud:
            self.root.after(0, lambda: self.cargo_hud.update(inventory, self.cargo_capacity))

    def update_nav_route(self, data):
        self.last_nav_event_ts = time.time()
        self.route_list = [r['StarSystem'] for r in data.get('Route', [])]
        if self.route_list:
            dest = data['Route'][-1]
            self.dest_coords = dest['StarPos']
            self.dest_name = dest['StarSystem']
            self.add_event_feed_entry("SYSTEM", f"Nav route loaded: {len(self.route_list)} jumps to {self.dest_name}", severity="INFO", copy_text=self.dest_name, url=f"https://www.edsm.net/show-system?systemName={self.dest_name.replace(' ', '+')}")
            self.update_nav_label()
            self.update_hud()
        else:
            self.dest_coords = None
            self.dest_name = None
            self.add_event_feed_entry("SYSTEM", "Nav route cleared", severity="INFO")
