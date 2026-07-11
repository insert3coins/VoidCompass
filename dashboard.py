import os
import threading
import math
import sqlite3
import logging
import time
import tkinter as tk
import webbrowser
import shutil
import queue
from collections import deque

from config import (
    load_config, CONFIG_FILE,
    COLOR_BG, COLOR_ACCENT, COLOR_TEXT,
    apply_profile_config, commander_profile_key, get_active_profile,
    get_profile_file, save_config, save_active_profile_config,
)
from version import APP_VERSION
import bio_values
from hud import TacticalHUD
from cargo_hud import CargoHUD
from carrier_hud import CarrierHUD
from edsm_handler import EDSMHandler
from screenshot_handler import ScreenshotHandler
from settings_ui import open_settings
from route_plotter import RoutePlotter
from waypoint_manager import WaypointManager
import route_strip
from journal_watcher import JournalWatcher
from mining_window import MiningWindow
from carrier_tracker import CarrierTracker
from carrier_window import CarrierWindow
from prospector_hud import ProspectorHUD
from system_info_hud import SystemInfoHUD
from colony_overlay import ColonyOverlay
from gravity_warning_hud import GravityWarningHUD
from station_info_hud import StationInfoHUD
from survey_status_hud import SurveyStatusHUD
from toast_hud import ToastHUD
from heartbeat_hud import HeartbeatHUD
from runtime_trace import RuntimeTrace
from dashboard_db_mixin import DashboardDBMixin
from dashboard_ui_mixin import DashboardUIMixin
from dashboard_scan_mixin import DashboardScanMixin
from colonization_window import ColonizationWindow, save_colonisation_data, load_colonisation_data
from engineer_window import (
    EngineerWindow, load_engineer_materials, save_engineer_materials,
    get_material_category,
)
from bgs_window import BGSWindow
from commander_profile_window import CommanderProfileWindow
from system_value_ledger import SystemValueLedger
from colonisation_planner import ColonisationPlanner
from exploration_window import ExplorationWindow
from trade_window import TradeWindow
from trade import marketdb as trade_marketdb
from trade import alerts as trade_alerts
from trade.eddn_upload import UPLOADER as trade_eddn_uploader
from achievement_engine import AchievementEngine
from achievement_window import AchievementWindow


class MainDashboard(DashboardScanMixin, DashboardUIMixin, DashboardDBMixin):
    @staticmethod
    def _to_float(value, default=None):
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _gravity_to_g(value):
        try:
            g = float(value)
            return round(g / 9.80665, 2) if g > 5 else round(g, 2)
        except Exception:
            return None

    def _bio_predictions_for_scan(self, scan_data):
        if not scan_data:
            return []
        return bio_values.predict_genera(
            scan_data.get("planet_class"),
            scan_data.get("atmosphere_type") or scan_data.get("atmosphere"),
            scan_data.get("surface_temp") or scan_data.get("temp_k"),
            scan_data.get("gravity_g") or self._gravity_to_g(scan_data.get("surface_gravity")),
            scan_data.get("volcanism"),
        )

    def _profile_path(self, filename):
        return get_profile_file(get_active_profile(self.config), filename)

    def _copy_legacy_to_profile(self, filename):
        src = os.path.abspath(filename)
        dst = self._profile_path(filename)
        if os.path.exists(dst) or not os.path.exists(src):
            return dst
        if len(self.config.get("commander_profiles", {})) > 1:
            return dst
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass
        return dst

    def _refresh_profile_paths(self):
        self.config["carrier_state_file"] = self._copy_legacy_to_profile("carrier_state.json")
        self.config["colonisation_data_file"] = self._copy_legacy_to_profile("colonisation_data.json")
        self.config["engineer_materials_file"] = self._copy_legacy_to_profile("engineer_materials.json")
        self.config["mining_db_file"] = self._copy_legacy_to_profile("mining_data.db")
        self.config["mining_sessions_file"] = self._copy_legacy_to_profile("mining_sessions.json")
        self.config["waypoints_file"] = self._copy_legacy_to_profile("waypoints.json")

    def _prepare_commander_profile_from_journal(self):
        detected = JournalWatcher.detect_latest_commander(self.config.get("journal_path"))
        if detected:
            name = detected.get("commander") or "Unknown Commander"
            fid = detected.get("fid") or ""
            key = commander_profile_key(name, fid)
            profiles = self.config.setdefault("commander_profiles", {})
            profile = profiles.setdefault(key, {})
            profile["commander_name"] = name
            profile["fid"] = fid
            if not profile.get("edsm_cmdr_name"):
                profile["edsm_cmdr_name"] = name
            self.config["active_commander_profile"] = key
            self.config["active_commander_name"] = name
            self.config["active_commander_fid"] = fid
        apply_profile_config(self.config)
        self._refresh_profile_paths()

    def _persist_config(self):
        save_config(self.config)

    def _refresh_tool_window(self, attr, method="refresh"):
        win = getattr(self, attr, None)
        try:
            if win and win.is_open():
                self.root.after(0, getattr(win, method))
        except Exception:
            pass

    def _refresh_commander_profile_window(self):
        self._refresh_tool_window("commander_profile_window")

    def _refresh_value_ledger_window(self):
        self._refresh_tool_window("value_ledger_window")

    def _refresh_colonisation_planner_window(self):
        self._refresh_tool_window("colonisation_planner_window")

    def _refresh_exploration_window(self):
        if getattr(self, "_exploration_refresh_job", None) is not None:
            return
        def _run():
            self._exploration_refresh_job = None
            self._refresh_tool_window("exploration_window")
        try:
            self._exploration_refresh_job = self.root.after(150, _run)
        except Exception:
            self._exploration_refresh_job = None

    def _refresh_bgs_window(self):
        self._refresh_tool_window("bgs_window", "refresh_current")

    def _refresh_system_info_progress(self):
        if not getattr(self, "system_info_hud", None) and not getattr(self, "survey_status_hud", None):
            return
        if getattr(self, "_system_info_refresh_job", None) is not None:
            return
        def _run():
            self._system_info_refresh_job = None
            if self.system_info_hud:
                self.system_info_hud.update_scan_progress(self.scan_items, self.body_signals, self.total)
            if self.survey_status_hud:
                self.survey_status_hud.update(self.current_sys, self.scanned, self.total, self.scan_items, self.body_signals)
        try:
            self._system_info_refresh_job = self.root.after(150, _run)
        except Exception:
            self._system_info_refresh_job = None

    def _start_trade_live_services(self):
        """Start the EDDN listener at app startup (not first Trade-window open,
        which let the market DB silently age) and surface fired trade-watch
        alerts as toasts instead of waiting for the Watchlist tab."""
        def _on_trade_alert(alert):
            toast = getattr(self, "toast_hud", None)
            if toast:
                # Called from the EDDN thread — hop to the Tk main loop.
                self.root.after(0, lambda a=alert: toast.push(
                    "TRADE WATCH", a.get("text") or "", severity="warn", duration_s=15))
        try:
            trade_alerts.set_notify_callback(_on_trade_alert)
        except Exception:
            pass
        try:
            conn = trade_marketdb.connect()
            try:
                seeded = trade_marketdb.is_ready(conn)
            finally:
                conn.close()
            if seeded:
                from trade import eddn as trade_eddn
                trade_eddn.LISTENER.start()
        except Exception:
            pass  # no zmq / no DB yet — Trade window can still start it later

    def _refresh_gravity_warning(self, body_id, body_name=None):
        if not getattr(self, "gravity_warning_hud", None) or body_id is None:
            return
        item = self.scan_items_by_id.get(body_id)
        gravity_g = item.get("gravity_g") if item else None
        name = body_name or (item.get("name") if item else None)
        self.gravity_warning_hud.check_body(name, gravity_g)

    def _check_stale_bio_scans(self, body_id):
        """Warn if we're leaving a body with an in-progress (not yet 3-sample
        complete) organic scan sequence still on it — those samples are lost
        once you leave the body's vicinity, same warning SrvSurvey gives."""
        if body_id is None or not getattr(self, "toast_hud", None):
            return
        warned = getattr(self, "_stale_bio_warned", None)
        if warned is None:
            warned = self._stale_bio_warned = set()
        for key, entry in self.last_bio_scan.items():
            if entry.get("body_id") != body_id or entry.get("is_complete"):
                continue
            if key in warned:
                continue
            warned.add(key)
            species = entry.get("species") or "Organic"
            sample_idx = entry.get("sample_idx")
            max_samples = entry.get("max_samples") or 3
            body_label = entry.get("body_name") or "this body"
            progress = f"{sample_idx}/{max_samples}" if sample_idx is not None else "in progress"
            self.toast_hud.push(
                "STALE SAMPLE",
                f"{species} ({progress}) left behind on {body_label}",
                severity="warn",
                duration_s=15,
            )

    def _save_colonisation_data(self, projects):
        save_colonisation_data(projects, self.config.get("colonisation_data_file"))

    def _save_engineer_materials(self, materials):
        save_engineer_materials(materials, self.config.get("engineer_materials_file"))

    def _switch_commander_profile(self, commander_name, fid=None):
        if not commander_name:
            return
        new_key = commander_profile_key(commander_name, fid)
        old_key = get_active_profile(self.config)
        if new_key == old_key:
            self.config["active_commander_name"] = commander_name
            self.config["active_commander_fid"] = fid or self.config.get("active_commander_fid", "")
            save_active_profile_config(self.config)
            try:
                if hasattr(self, "summary_cmdr"):
                    self.summary_cmdr.config(text=str(commander_name).upper())
            except Exception:
                pass
            self._refresh_commander_profile_window()
            self._refresh_exploration_window()
            return

        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

        save_active_profile_config(self.config)
        profiles = self.config.setdefault("commander_profiles", {})
        profile = profiles.setdefault(new_key, {})
        profile["commander_name"] = commander_name
        profile["fid"] = fid or profile.get("fid", "")
        if not profile.get("edsm_cmdr_name"):
            profile["edsm_cmdr_name"] = commander_name
        if old_key == "unknown_commander":
            for filename in (
                "exploration_data.db",
                "carrier_state.json",
                "colonisation_data.json",
                "engineer_materials.json",
                "mining_data.db",
                "mining_sessions.json",
                "waypoints.json",
            ):
                src = get_profile_file(old_key, filename)
                dst = get_profile_file(new_key, filename)
                if os.path.exists(src) and not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
        self.config["active_commander_profile"] = new_key
        self.config["active_commander_name"] = commander_name
        self.config["active_commander_fid"] = fid or profile.get("fid", "")
        apply_profile_config(self.config, new_key)
        self._refresh_profile_paths()
        if getattr(self, "achievement_engine", None):
            self.achievement_engine.switch_profile(
                self._profile_path("achievements_state.json"),
                enabled=self.config.get("achievements_enabled", True),
                disabled_categories=self.config.get("achievements_disabled_categories", []),
            )
        self.init_db()
        self.edsm.config = self.config
        self.edsm.set_db(self.conn, self.db_lock)
        self.carrier_tracker.set_config(self.config)
        self.colonisation_projects = self.db_load_colonisation_projects()
        for mid, jp in load_colonisation_data(self.config.get("colonisation_data_file")).items():
            if mid in self.colonisation_projects:
                for k, v in jp.items():
                    if k not in self.colonisation_projects[mid] or not self.colonisation_projects[mid].get(k):
                        self.colonisation_projects[mid][k] = v
            else:
                self.colonisation_projects[mid] = jp
        self.engineer_materials = load_engineer_materials(self.config.get("engineer_materials_file"))
        self.waypoint_manager = WaypointManager(self.config.get("waypoints_file"))
        for attr in (
            "mining_window",
            "colonization_window",
            "engineer_window",
            "bgs_window",
            "commander_profile_window",
            "value_ledger_window",
            "colonisation_planner_window",
            "exploration_window",
            "achievement_window",
        ):
            win = getattr(self, attr, None)
            try:
                if win and win.is_open():
                    if hasattr(win, "win"):
                        win.win.destroy()
                    else:
                        win.destroy()
            except Exception:
                pass
            setattr(self, attr, None)
        try:
            if self.route_plotter and self.route_plotter.win.winfo_exists():
                self.route_plotter.on_close()
        except Exception:
            pass
        self.route_plotter = None
        try:
            if self.carrier_window and self.carrier_window.is_open():
                self.carrier_window.refresh()
        except Exception:
            pass
        self._refresh_commander_profile_window()
        self._persist_config()
        self.load_system_from_db(self.current_sys)
        self.update_dashboard_ui()
        self.update_hud()
        self.update_carrier_panel()
        self._apply_runtime_feature_toggles()
        self.add_event_feed_entry("PROFILE", f"Switched to commander profile: {commander_name}", severity="INFO")

    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self._prepare_commander_profile_from_journal()
        self.root.title(f"VOID COMPASS // v{APP_VERSION}")
        self.root.geometry(self.config.get("main_geometry", "1320x820"))
        self.root.minsize(1080, 700)
        self.root.configure(bg=COLOR_BG)
        
        self.is_running = True
        self.is_first_load = True
        
        self.current_sys = "---"
        self.previous_sys = None
        self.previous_coords = None
        self.current_system_address = None
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
        self.fss_summary_active = False
        self.body_signals = {}
        self.body_dss_complete = set()
        self.system_undiscovered = False
        self.fss_all_bodies = False
        self.cmdr_name = self.config.get("active_commander_name") or "CMDR"
        self.cmdr_fid = self.config.get("active_commander_fid") or ""
        self.cmdr_balance = None
        self.cmdr_loan = None
        self.game_version = ""
        self.game_build = ""
        self.game_horizons = None
        self.game_odyssey = None
        self.cmdr_ranks = {}
        self.cmdr_rank_progress = {}
        self.cmdr_reputation = {}
        self.cmdr_ship = {}
        self.last_scan_event = None
        self.last_bio_scan = {}
        self._stale_bio_warned = set()
        # Bio tracking: star/body scan conditions for prediction
        self.system_stars: dict  = {}   # body_id → star_type str
        self.body_scan_data: dict = {}  # body_id → conditions dict
        self.current_body_id    = None  # from ApproachBody
        self.current_body_name  = ""
        # Colonization tracking
        self.colonisation_projects: dict = {}  # market_id → project dict
        self.current_colonisation_market: int | None = None
        self.current_station_name = None
        self.current_station_type = None
        self.current_station_market_id = None
        self.current_station_economy = None
        self.current_station_economies = []
        self.current_station_government = None
        self.current_station_faction = None
        self.current_station_allegiance = None
        self.current_station_services = []
        self.current_station_dist_ls = None
        self.current_station_landing_pads = None
        self.current_trade_market = None
        self.current_docked = False
        self.hud_flight_state = "FLIGHT"
        self.current_landed = False
        self.current_in_fighter = False
        self.current_in_srv = False
        self.current_on_foot = False
        self.current_vehicle_id = None
        self.current_vehicle_name = ""
        self._vehicle_name_by_id = {}
        self._last_surface_vehicle_name = ""
        self.current_music_track = ""
        self.current_music_mode = ""
        self.current_music_label = ""
        self._last_music_event_ts = 0.0
        self.current_fuel_main = None
        self.current_fuel_reservoir = None
        self.fuel_capacity_main = None
        self._low_fuel_warned = False
        self._toast_hull_thresholds_seen = set()
        self._toast_status_alerts = set()
        self._toast_legal_state = None
        self._toast_shields_up = None
        self.current_legal_state = None
        self.current_destination = None
        self.trade_jump_history = deque(maxlen=20)
        self.cargo_capacity = 0
        self.current_cargo_tons = 0
        self.current_cargo_inventory = []
        self.trade_session = {
            "bought_units": 0,
            "sold_units": 0,
            "spent": 0,
            "earned": 0,
            "profit": 0,
            "events": deque(maxlen=100),
        }
        self._hud_balance_cache = {"ts": 0.0, "balance": None}
        self._market_import_queue = queue.Queue(maxsize=1)
        self._market_import_stop = threading.Event()
        self._market_import_thread = None
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
        self.nav_route_entries = []
        self.session_start_ts = time.time()
        self.session_jump_count = 0
        self.session_ly = 0.0
        self.session_systems = set()
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
        self.ground_target_window = None
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
        self._event_feed_pending = deque()
        self._journal_history_pending = deque()
        self._event_feed_pending_lock = threading.Lock()
        self._event_feed_dirty = False
        self._journal_history_dirty = False
        self._defer_dashboard_stream_render = False
        self.event_feed_max_entries = 150
        self.event_feed_display_limit = 80
        self.dashboard_refresh_job = None
        self._exploration_refresh_job = None
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
        self._overlay_pos_last_saved = {"hud": None, "cargo": None, "carrier": None, "scan": None, "system_info": None, "colony": None}
        self._overlay_sync_grace_until = time.time() + 4.0
        self.runtime_trace = RuntimeTrace(
            self.config.get("runtime_trace_path", "runtime_trace.log"),
            enabled=bool(self.config.get("runtime_trace_enabled", True)),
        )
        self.runtime_trace.start()
        
        self.setup_layout()
        self.waypoint_manager = WaypointManager(self.config.get("waypoints_file"))
        self.route_plotter = None
        self.target_waypoint = None
        self.waypoint_cache = {}
        
        # Initialize Handlers
        self.edsm = EDSMHandler(self.config)
        self.edsm.set_log_callback(
            lambda tag, msg, sev: self.root.after(0, lambda: self.add_event_feed_entry(tag, msg, severity=sev))
        )
        trade_eddn_uploader.set_log_callback(
            lambda tag, msg, sev: self.root.after(0, lambda: self.add_event_feed_entry(tag, msg, severity=sev))
        )
        self.screenshots = ScreenshotHandler(
            self.config,
            lambda: self.current_sys,
            self.log,
            trace_callback=self._trace_record_ms,
        )
        self.mining_window = None
        self.carrier_window = None
        self.colonization_window = None
        self.engineer_window = None
        self.bgs_window = None
        self.commander_profile_window = None
        self.value_ledger_window = None
        self.colonisation_planner_window = None
        self.exploration_window = None
        self.trade_window = None
        self.achievement_window = None
        self._carrier_panel_tick_job = None
        self.carrier_tracker = CarrierTracker()
        self._refresh_profile_paths()
        self.carrier_tracker.set_config(self.config)
        self.carrier_tracker.on_panel_updated = self._on_carrier_panel_updated
        self.carrier_tracker.on_status_changed = self._on_carrier_status_changed
        self.achievement_engine = AchievementEngine(
            self._profile_path("achievements_state.json"),
            enabled=self.config.get("achievements_enabled", True),
            disabled_categories=self.config.get("achievements_disabled_categories", []),
            on_unlock=self._on_achievement_unlocked,
        )

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
            try:
                self.cargo_hud.update(self.current_cargo_inventory, self.cargo_capacity)
                self.cargo_hud.win.deiconify()
                self.cargo_hud.win.attributes("-topmost", True)
                self.cargo_hud.win.lift()
            except Exception:
                pass
        else:
            self.cargo_hud = None

        if self.config.get("carrier_overlay_enabled", False):
            self.carrier_hud = CarrierHUD(self.root, self.config, self.carrier_tracker)
        else:
            self.carrier_hud = None

        if self.config.get("prospector_overlay_enabled", True):
            self.prospector_hud = ProspectorHUD(self.root, self.config)
        else:
            self.prospector_hud = None

        if self.config.get("system_info_enabled", True):
            self.system_info_hud = SystemInfoHUD(self.root, self.config)
        else:
            self.system_info_hud = None

        if self.config.get("gravity_warning_overlay_enabled", True):
            self.gravity_warning_hud = GravityWarningHUD(self.root, self.config)
        else:
            self.gravity_warning_hud = None

        if self.config.get("station_info_overlay_enabled", True):
            self.station_info_hud = StationInfoHUD(self.root, self.config)
        else:
            self.station_info_hud = None

        if self.config.get("survey_status_overlay_enabled", True):
            self.survey_status_hud = SurveyStatusHUD(self.root, self.config)
        else:
            self.survey_status_hud = None

        if self.config.get("toast_overlay_enabled", True):
            self.toast_hud = ToastHUD(self.root, self.config)
        else:
            self.toast_hud = None

        if self.config.get("heartbeat_overlay_enabled", True):
            self.heartbeat_hud = HeartbeatHUD(self.root, self.config)
        else:
            self.heartbeat_hud = None

        if self.config.get("colony_overlay_enabled", False):
            self.colony_overlay = ColonyOverlay(
                self.root,
                self.config,
                lambda: self.colonisation_projects,
                lambda: self.current_cargo_inventory,
                lambda: self.cargo_capacity,
                lambda: self.current_colonisation_market,
            )
        else:
            self.colony_overlay = None

        self.db_lock = threading.RLock()
        self.batch_mode = False
        self.init_db()
        self.edsm.set_db(self.conn, self.db_lock)
        self.colonisation_projects = self.db_load_colonisation_projects()
        # Merge JSON store (carries notes and any extra fields the DB doesn't have)
        _json_projects = load_colonisation_data(self.config.get("colonisation_data_file"))
        for mid, jp in _json_projects.items():
            if mid in self.colonisation_projects:
                # Copy over fields present in JSON but absent in DB (e.g. notes)
                for k, v in jp.items():
                    if k not in self.colonisation_projects[mid] or not self.colonisation_projects[mid].get(k):
                        self.colonisation_projects[mid][k] = v
            else:
                self.colonisation_projects[mid] = jp
        self.engineer_materials = load_engineer_materials(self.config.get("engineer_materials_file"))
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
            status_cb=self.update_status,
            market_cb=self.update_market
        )
        self.watcher.prime_market_file()
        self._start_market_import_worker()
        self.watcher.start()
        self._start_trade_live_services()
        self.cargo_capacity = self.watcher.get_latest_cargo_capacity()
        if self.colony_overlay:
            self.colony_overlay.update()

        self.watcher.force_check_nav()
        self.watcher.force_check_status()

        journal_path = self.config.get("journal_path") or getattr(self.watcher, "journal_path", None)
        threading.Thread(
            target=self.carrier_tracker.scan_journal_history,
            args=(journal_path,),
            daemon=True,
        ).start()

        threading.Thread(target=self.check_updates, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log(
            f"CONFIG FILE: {CONFIG_FILE} | HUD({self.config.get('hud_x')},{self.config.get('hud_y')}) "
            f"| CARGO({self.config.get('cargo_hud_x')},{self.config.get('cargo_hud_y')})"
        )
        self.root.after(120, self._reapply_overlay_positions)
        self.update_hud()
        self.update_ground_target_ui()
        self.update_carrier_panel()
        self._tick_ground_target()
        self._tick_session_clock()
        self._tick_event_feed_queue()
        self._tick_ui_stall_watchdog()
        self._tick_runtime_trace()
        self._tick_overlay_position_sync()

    def _reapply_overlay_positions(self):
        try:
            if self.hud and self.hud.win and self.hud.win.winfo_exists():
                hx = int(float(self.config.get("hud_x", self.hud.win.winfo_x())))
                hy = int(float(self.config.get("hud_y", self.hud.win.winfo_y())))
                self.hud.win.geometry(f"{self.hud.width}x{self.hud.base_height}+{hx}+{hy}")
        except Exception:
            pass
        try:
            if self.cargo_hud and self.cargo_hud.win and self.cargo_hud.win.winfo_exists():
                cx = int(float(self.config.get("cargo_hud_x", self.cargo_hud.win.winfo_x())))
                cy = int(float(self.config.get("cargo_hud_y", self.cargo_hud.win.winfo_y())))
                self.cargo_hud.win.geometry(f"300x400+{cx}+{cy}")
        except Exception:
            pass
        try:
            if self.carrier_hud and self.carrier_hud.win and self.carrier_hud.win.winfo_exists():
                fx = int(float(self.config.get("carrier_hud_x", self.carrier_hud.win.winfo_x())))
                fy = int(float(self.config.get("carrier_hud_y", self.carrier_hud.win.winfo_y())))
                self.carrier_hud.win.geometry(f"+{fx}+{fy}")
        except Exception:
            pass
        self.root.after(250, self._log_applied_overlay_positions)

    def _log_applied_overlay_positions(self):
        try:
            hxy = "-"
            cxy = "-"
            fxy = "-"
            if self.hud and self.hud.win and self.hud.win.winfo_exists():
                hxy = f"{self.hud.win.winfo_x()},{self.hud.win.winfo_y()}"
            if self.cargo_hud and self.cargo_hud.win and self.cargo_hud.win.winfo_exists():
                cxy = f"{self.cargo_hud.win.winfo_x()},{self.cargo_hud.win.winfo_y()}"
            if self.carrier_hud and self.carrier_hud.win and self.carrier_hud.win.winfo_exists():
                fxy = f"{self.carrier_hud.win.winfo_x()},{self.carrier_hud.win.winfo_y()}"
            self.log(f"CONFIG FILE: APPLIED HUD({hxy}) | CARGO({cxy}) | CARRIER({fxy})")
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
                # Never trust a (0,0) reading — it means the window is minimised,
                # hidden, or the WM hasn't placed it yet. Keep the last good position.
                if pos == (0, 0) and cfg_pos != (0, 0):
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
                if pos == (0, 0) and cfg_pos != (0, 0):
                    pos = cfg_pos
                if self._overlay_pos_last_saved.get("cargo") != pos:
                    self._overlay_pos_last_saved["cargo"] = pos
                    self.config["cargo_hud_x"], self.config["cargo_hud_y"] = pos
                    changed = True
        except Exception:
            pass
        try:
            if self.carrier_hud and self.carrier_hud.win and self.carrier_hud.win.winfo_exists():
                pos = (int(self.carrier_hud.win.winfo_x()), int(self.carrier_hud.win.winfo_y()))
                cfg_pos = (
                    int(float(self.config.get("carrier_hud_x", pos[0]))),
                    int(float(self.config.get("carrier_hud_y", pos[1]))),
                )
                if pos == (0, 0) and cfg_pos != (0, 0):
                    pos = cfg_pos
                if self._overlay_pos_last_saved.get("carrier") != pos:
                    self._overlay_pos_last_saved["carrier"] = pos
                    self.config["carrier_hud_x"], self.config["carrier_hud_y"] = pos
                    changed = True
        except Exception:
            pass
        try:
            if self.system_info_hud and self.system_info_hud.win and self.system_info_hud.win.winfo_exists():
                pos = (int(self.system_info_hud.win.winfo_x()), int(self.system_info_hud.win.winfo_y()))
                cfg_pos = (
                    int(float(self.config.get("system_info_hud_x", pos[0]))),
                    int(float(self.config.get("system_info_hud_y", pos[1]))),
                )
                if pos == (0, 0) and cfg_pos != (0, 0):
                    pos = cfg_pos
                if self._overlay_pos_last_saved.get("system_info") != pos:
                    self._overlay_pos_last_saved["system_info"] = pos
                    self.config["system_info_hud_x"], self.config["system_info_hud_y"] = pos
                    changed = True
        except Exception:
            pass
        try:
            if self.colony_overlay and self.colony_overlay.win and self.colony_overlay.win.winfo_exists():
                pos = (int(self.colony_overlay.win.winfo_x()), int(self.colony_overlay.win.winfo_y()))
                cfg_pos = (
                    int(float(self.config.get("colony_overlay_x", pos[0]))),
                    int(float(self.config.get("colony_overlay_y", pos[1]))),
                )
                if pos == (0, 0) and cfg_pos != (0, 0):
                    pos = cfg_pos
                if self._overlay_pos_last_saved.get("colony") != pos:
                    self._overlay_pos_last_saved["colony"] = pos
                    self.config["colony_overlay_x"], self.config["colony_overlay_y"] = pos
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
        if self.colonization_window and self.colonization_window.is_open():
            self.colonization_window._on_close()
        if self.engineer_window and self.engineer_window.is_open():
            self.engineer_window._on_close()
        if self.bgs_window and self.bgs_window.is_open():
            self.bgs_window._on_close()
        if self.exploration_window and self.exploration_window.is_open():
            self.exploration_window._on_close()
        if self.trade_window and self.trade_window.is_open():
            self.trade_window._on_close()
        if self.achievement_engine:
            self.achievement_engine.flush()
            
        self._stop_market_import_worker()
        self.watcher.stop()
        self.screenshots.stop()
        try:
            if self.hud and self.hud.win and self.hud.win.winfo_exists():
                x, y = int(self.hud.win.winfo_x()), int(self.hud.win.winfo_y())
                if x != 0 or y != 0:
                    self.config["hud_x"], self.config["hud_y"] = x, y
        except Exception:
            pass
        try:
            if self.cargo_hud and self.cargo_hud.win and self.cargo_hud.win.winfo_exists():
                x, y = int(self.cargo_hud.win.winfo_x()), int(self.cargo_hud.win.winfo_y())
                if x != 0 or y != 0:
                    self.config["cargo_hud_x"], self.config["cargo_hud_y"] = x, y
        except Exception:
            pass
        try:
            if self.carrier_hud and self.carrier_hud.win and self.carrier_hud.win.winfo_exists():
                x, y = int(self.carrier_hud.win.winfo_x()), int(self.carrier_hud.win.winfo_y())
                if x != 0 or y != 0:
                    self.config["carrier_hud_x"], self.config["carrier_hud_y"] = x, y
        except Exception:
            pass
        try:
            if self.colony_overlay and self.colony_overlay.win and self.colony_overlay.win.winfo_exists():
                x, y = int(self.colony_overlay.win.winfo_x()), int(self.colony_overlay.win.winfo_y())
                w, h = int(self.colony_overlay.win.winfo_width()), int(self.colony_overlay.win.winfo_height())
                if x != 0 or y != 0:
                    self.config["colony_overlay_x"], self.config["colony_overlay_y"] = x, y
                if w > 0 and h > 0:
                    self.config["colony_overlay_w"], self.config["colony_overlay_h"] = w, h
        except Exception:
            pass
        self.config["main_geometry"] = self.root.geometry()
        self._persist_config()
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
        if self.ground_target_window and self.ground_target_window.winfo_exists():
            try:
                self.config["ground_target_window_geometry"] = self.ground_target_window.geometry()
                self._persist_config()
            except Exception:
                pass
        self._destroy_ground_popup()
        self.root.destroy()

    def _save_config_file(self):
        try:
            self._persist_config()
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
            self._show_embedded_page("ROUTE", self.route_plotter.win)
            return
        self.route_plotter = RoutePlotter(
            self.dashboard_host,
            self.edsm,
            self.current_coords,
            self.current_sys,
            self.config,
            self.waypoint_manager,
            on_change_callback=self.update_waypoint_display,
            event_callback=self._on_route_event,
            embedded=True,
        )
        self._show_embedded_page("ROUTE", self.route_plotter.win)

    def open_mining_window(self):
        if self.mining_window and self.mining_window.is_open():
            self._show_embedded_page("MINING", self.mining_window.win)
            self.mining_window.on_shown()
            return
        self.mining_window = MiningWindow(
            self.dashboard_host,
            self.config,
            get_current_system=lambda: self.current_sys,
            get_cargo_capacity=lambda: self.cargo_capacity,
            get_current_coords=lambda: self.current_coords,
            embedded=True,
            is_active_callback=lambda: getattr(self, "_active_page", None) == "MINING",
        )
        self._show_embedded_page("MINING", self.mining_window.win)
        self.mining_window.on_shown()
        try:
            self.watcher.force_check_cargo()
            self.watcher.force_check_status()
        except Exception:
            pass

    def open_carrier_window(self):
        if self.carrier_window and self.carrier_window.is_open():
            self._show_embedded_page("CARRIER", self.carrier_window.win)
            return
        self.carrier_window = CarrierWindow(self.dashboard_host, self.config, self.carrier_tracker, embedded=True)
        self._show_embedded_page("CARRIER", self.carrier_window.win)

    def open_colonization_window(self):
        if self.colonization_window and self.colonization_window.is_open():
            self._show_embedded_page("COLONY", self.colonization_window.win)
            return
        self.colonization_window = ColonizationWindow(
            self.dashboard_host,
            self.config,
            self.colonisation_projects,
            self._save_colonisation_data,
            overlay_callback=self.toggle_colony_overlay,
            embedded=True,
        )
        self._show_embedded_page("COLONY", self.colonization_window.win)

    def toggle_colony_overlay(self):
        try:
            if self.colony_overlay and self.colony_overlay.is_open():
                self.colony_overlay.win.destroy()
                self.colony_overlay = None
                self.config["colony_overlay_enabled"] = False
                self._save_config_file()
                return
        except Exception:
            self.colony_overlay = None
        self.colony_overlay = ColonyOverlay(
            self.root,
            self.config,
            lambda: self.colonisation_projects,
            lambda: self.current_cargo_inventory,
            lambda: self.cargo_capacity,
            lambda: self.current_colonisation_market,
        )
        self.config["colony_overlay_enabled"] = True
        self._save_config_file()

    def open_engineer_window(self):
        if self.engineer_window and self.engineer_window.is_open():
            self._show_embedded_page("ENGINEER", self.engineer_window.win)
            return
        self.engineer_window = EngineerWindow(
            self.dashboard_host,
            self.config,
            self.engineer_materials,
            self._save_engineer_materials,
            embedded=True,
        )
        self._show_embedded_page("ENGINEER", self.engineer_window.win)

    def open_bgs_window(self):
        if self.bgs_window and self.bgs_window.is_open():
            self._show_embedded_page("BGS", self.bgs_window.win)
            return
        self.bgs_window = BGSWindow(
            self.dashboard_host,
            self.config,
            self.db_load_bgs_systems,
            self.db_load_bgs_factions,
            embedded=True,
        )
        self._show_embedded_page("BGS", self.bgs_window.win)

    def open_commander_profile_window(self):
        if self.commander_profile_window and self.commander_profile_window.is_open():
            self._show_embedded_page("PROFILE", self.commander_profile_window.win)
            return
        self.commander_profile_window = CommanderProfileWindow(self.dashboard_host, self, embedded=True)
        self._show_embedded_page("PROFILE", self.commander_profile_window.win)

    def open_exploration_window(self):
        if self.exploration_window and self.exploration_window.is_open():
            self._show_embedded_page("EXPLORE", self.exploration_window.win)
            return
        self.exploration_window = ExplorationWindow(self.dashboard_host, self, embedded=True)
        self._show_embedded_page("EXPLORE", self.exploration_window.win)

    def open_trade_window(self):
        if self.trade_window and self.trade_window.is_open():
            self._show_embedded_page("TRADE", self.trade_window.win)
            self.trade_window.on_shown()
            return
        try:
            self.trade_window = TradeWindow(self.dashboard_host, self, embedded=True)
            self._show_embedded_page("TRADE", self.trade_window.win)
            self.trade_window.on_shown()
        except Exception as exc:
            self.trade_window = None
            self.log(f"Trade window failed to open: {exc}")
            self.add_event_feed_entry("TRADE", f"Trade window failed: {exc}", severity="WARN")

    def open_achievement_window(self):
        if self.achievement_window and self.achievement_window.is_open():
            self.achievement_window.refresh()
            self._show_embedded_page("ACHIEVE", self.achievement_window.win)
            return
        self.achievement_window = AchievementWindow(
            self.dashboard_host,
            self,
            self.achievement_engine,
            embedded=True,
        )
        self._show_embedded_page("ACHIEVE", self.achievement_window.win)

    def _on_achievement_unlocked(self, achievement):
        def apply_unlock():
            title = achievement.get("title") or achievement.get("id") or "Achievement"
            icon = achievement.get("icon") or "★"
            points = int(achievement.get("points") or 0)
            self.add_event_feed_entry(
                "ACHIEVEMENT",
                f"Unlocked: {title} (+{points:,} pts)",
                severity="INFO",
            )
            if self.config.get("achievement_notifications_enabled", True) and self.toast_hud:
                self.toast_hud.push(
                    "ACHIEVEMENT UNLOCKED",
                    f"{icon} {title}  //  +{points:,} pts",
                    severity="success",
                    duration_s=15,
                )
            window = getattr(self, "achievement_window", None)
            if window and window.is_open() and getattr(self, "_active_page", None) == "ACHIEVE":
                window.refresh()

        try:
            self.root.after(0, apply_unlock)
        except Exception:
            pass

    def open_value_ledger_window(self):
        if self.value_ledger_window and self.value_ledger_window.is_open():
            self.value_ledger_window.lift()
            return
        self.value_ledger_window = SystemValueLedger(self.root, self)

    def open_colonisation_planner_window(self):
        if self.colonisation_planner_window and self.colonisation_planner_window.is_open():
            self.colonisation_planner_window.lift()
            return
        self.colonisation_planner_window = ColonisationPlanner(self.root, self)

    # ------------------------------------------------------------------
    # Carrier dashboard panel + event-feed callbacks
    # ------------------------------------------------------------------

    def _on_carrier_status_changed(self, old_status, new_status, carrier_data):
        """Push carrier status transitions into the dashboard Live Event Timeline."""
        try:
            name     = carrier_data.get("name") or "Fleet Carrier"
            callsign = carrier_data.get("callsign") or ""
            label    = f"{name} ({callsign})" if callsign else name

            if new_status == "jumping":
                dest = carrier_data.get("jump_destination") or "?"
                dep  = carrier_data.get("jump_departure_time") or ""
                dep_txt = ""
                if dep:
                    try:
                        from datetime import datetime, timezone
                        dt = datetime.fromisoformat(dep.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        dep_txt = f"  dep {dt.astimezone().strftime('%H:%M')}"
                    except Exception:
                        pass
                msg = f"FC {label}: jump plotted → {dest}{dep_txt}"
                self.root.after(0, lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="INFO"))

            elif new_status == "cooldown":
                system = carrier_data.get("system") or "?"
                msg = f"FC {label}: arrived at {system}"
                self.root.after(0, lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="INFO"))
                if self.toast_hud:
                    self.root.after(0, lambda m=msg: self.toast_hud.push("CARRIER JUMPED", m, severity="success"))

            elif new_status == "cooldown_cancel":
                msg = f"FC {label}: jump cancelled"
                self.root.after(0, lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="WARN"))

            elif old_status in ("cooldown", "cooldown_cancel") and new_status == "idle":
                system = carrier_data.get("system") or "?"
                msg = f"FC {label}: cooldown complete @ {system}"
                self.root.after(0, lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="INFO"))
                if self.toast_hud:
                    self.root.after(0, lambda m=msg: self.toast_hud.push("CARRIER READY", m, severity="success"))
        except Exception:
            pass

    def _on_carrier_panel_updated(self, carrier_data):
        """Fired by CarrierTracker whenever state changes (persistent hook)."""
        try:
            self.root.after(0, self.update_carrier_panel)
            if self.carrier_hud:
                self.root.after(0, lambda d=dict(carrier_data): self.carrier_hud.update(d))
            if carrier_data.get("status") == "jumping":
                self.root.after(0, self._ensure_carrier_panel_ticker)
        except Exception:
            pass

    def _ensure_carrier_panel_ticker(self):
        """Start the 1-second countdown ticker if not already running."""
        if self._carrier_panel_tick_job is not None:
            return
        self._tick_carrier_panel()

    def _tick_carrier_panel(self):
        """Refresh the carrier panel every second while the carrier is jumping."""
        self._carrier_panel_tick_job = None
        if not self.is_running:
            return
        status = self.carrier_tracker.carrier_data.get("status", "idle")
        if status == "jumping":
            self.update_carrier_panel()
            if self.carrier_hud:
                self.carrier_hud.update()
            self._carrier_panel_tick_job = self.root.after(1000, self._tick_carrier_panel)
        # Ticker stops naturally when status is no longer jumping;
        # _on_carrier_panel_updated will have already refreshed the panel.

    def _on_route_event(self, tag, message, severity="INFO", copy_text=None, system_name=None):
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
        )

    @staticmethod
    def _normalize_body_id(body_id):
        if body_id is None:
            return None
        try:
            return int(body_id)
        except Exception:
            return body_id

    @staticmethod
    def _normalize_system_address(system_address):
        if system_address is None:
            return None
        try:
            return int(system_address)
        except Exception:
            return system_address

    def _matches_current_system_address(self, data):
        event_address = self._normalize_system_address(data.get("system_address"))
        current_address = self._normalize_system_address(self.current_system_address)
        return event_address is None or current_address is None or event_address == current_address

    def _set_body_signals(self, body_id, bio_count=0, geo_count=0):
        body_id = self._normalize_body_id(body_id)
        if body_id is None:
            return
        self.body_signals[body_id] = {
            "bio": int(bio_count or 0),
            "geo": int(geo_count or 0),
        }
        self.system_bio_signals = sum(
            int(signals.get("bio", 0) or 0)
            for signals in self.body_signals.values()
        )

    def _mark_system_scan_complete(self, total=None):
        try:
            total = int(total or 0)
        except Exception:
            total = 0
        if total > 0:
            self.total = max(self.total, total)
        if self.total > 0:
            self.scanned = self.total
            self.db_update_system(self.current_sys, self.total, self.scanned)
            if not self.batch_mode:
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.update_hud()
                self.schedule_dashboard_refresh()
                self._refresh_exploration_window()

    def _apply_runtime_feature_toggles(self):
        if self.config.get("screenshots_enabled", False):
            self.log("Screenshot Converter: ACTIVE")
        else:
            self.log("Screenshot Converter: DISABLED")

        if self.config.get("overlay_enabled", True):
            if self.hud is None:
                self.hud = TacticalHUD(self.root, self.config, on_widget_click=self._on_hud_widget_click)
            self.update_hud()
        elif self.hud:
            self.hud.win.destroy()
            self.hud = None

        if self.config.get("cargo_overlay_enabled", False):
            if self.cargo_hud is None:
                self.cargo_hud = CargoHUD(self.root, self.config)
                self.cargo_capacity = self.watcher.get_latest_cargo_capacity()
                self.watcher.force_check_cargo()
            self.cargo_hud.update(self.current_cargo_inventory, self.cargo_capacity)
            try:
                self.cargo_hud.win.deiconify()
                self.cargo_hud.win.attributes("-topmost", True)
                self.cargo_hud.win.lift()
            except Exception:
                pass
        elif self.cargo_hud:
            self.cargo_hud.win.destroy()
            self.cargo_hud = None

        if self.config.get("carrier_overlay_enabled", False):
            if self.carrier_hud is None:
                self.carrier_hud = CarrierHUD(self.root, self.config, self.carrier_tracker)
            else:
                self.carrier_hud.update()
        elif self.carrier_hud:
            self.carrier_hud.destroy()
            self.carrier_hud = None

        if self.config.get("prospector_overlay_enabled", True):
            if self.prospector_hud is None:
                self.prospector_hud = ProspectorHUD(self.root, self.config)
        elif self.prospector_hud:
            try:
                self.prospector_hud.win.destroy()
            except Exception:
                pass
            self.prospector_hud = None

        if self.config.get("system_info_enabled", True):
            if self.system_info_hud is None:
                self.system_info_hud = SystemInfoHUD(self.root, self.config)
        elif self.system_info_hud:
            try:
                self.system_info_hud.win.destroy()
            except Exception:
                pass
            self.system_info_hud = None

        if self.config.get("gravity_warning_overlay_enabled", True):
            if self.gravity_warning_hud is None:
                self.gravity_warning_hud = GravityWarningHUD(self.root, self.config)
        elif self.gravity_warning_hud:
            try:
                self.gravity_warning_hud.win.destroy()
            except Exception:
                pass
            self.gravity_warning_hud = None

        if self.config.get("station_info_overlay_enabled", True):
            if self.station_info_hud is None:
                self.station_info_hud = StationInfoHUD(self.root, self.config)
        elif self.station_info_hud:
            try:
                self.station_info_hud.win.destroy()
            except Exception:
                pass
            self.station_info_hud = None

        if self.config.get("survey_status_overlay_enabled", True):
            if self.survey_status_hud is None:
                self.survey_status_hud = SurveyStatusHUD(self.root, self.config)
        elif self.survey_status_hud:
            try:
                self.survey_status_hud.win.destroy()
            except Exception:
                pass
            self.survey_status_hud = None

        if self.config.get("toast_overlay_enabled", True):
            if self.toast_hud is None:
                self.toast_hud = ToastHUD(self.root, self.config)
        elif self.toast_hud:
            try:
                self.toast_hud.win.destroy()
            except Exception:
                pass
            self.toast_hud = None

        if self.config.get("heartbeat_overlay_enabled", True):
            if self.heartbeat_hud is None:
                self.heartbeat_hud = HeartbeatHUD(self.root, self.config)
        elif self.heartbeat_hud:
            self.heartbeat_hud.destroy()
            self.heartbeat_hud = None

        if self.config.get("colony_overlay_enabled", False):
            if self.colony_overlay is None or not self.colony_overlay.is_open():
                self.colony_overlay = ColonyOverlay(
                    self.root,
                    self.config,
                    lambda: self.colonisation_projects,
                    lambda: self.current_cargo_inventory,
                    lambda: self.cargo_capacity,
                    lambda: self.current_colonisation_market,
                )
            else:
                self.colony_overlay.update()
        else:
            if self.colony_overlay and self.colony_overlay.is_open():
                self.colony_overlay.win.destroy()
            self.colony_overlay = None

    def open_settings(self):
        def on_save():
            self.log("Configuration saved successfully.")
            self._apply_runtime_feature_toggles()
            self.show_dashboard_page()

        page = getattr(self, "settings_page", None)
        if page is None or not page.winfo_exists():
            self.settings_page = open_settings(
                self.dashboard_host,
                self.config,
                on_save,
                carrier_tracker=self.carrier_tracker,
                embedded=True,
                on_close_callback=self.show_dashboard_page,
            )
        self._show_embedded_page("SETTINGS", self.settings_page)

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
                if self.system_info_hud:
                    self.system_info_hud.update_traffic(traffic_data)
            self.root.after(0, _apply)
        self.edsm.fetch_traffic(system_name, callback)

        if self.config.get("system_info_enabled", True):
            def details_callback(details):
                def _apply():
                    if self.current_sys != system_name:
                        return
                    if self.system_info_hud:
                        self.system_info_hud.update_edsm_details(details)
                self.root.after(0, _apply)
            self.edsm.fetch_system_details(system_name, details_callback)

            sys_addr = self.current_system_address
            if sys_addr:
                def spansh_callback(data):
                    def _apply():
                        if self.current_sys != system_name:
                            return
                        if self.system_info_hud:
                            self.system_info_hud.update_spansh(data)
                    self.root.after(0, _apply)
                self.edsm.fetch_spansh_system(sys_addr, spansh_callback)

    def _show_system_info_for_current_system(self):
        if not self.system_info_hud:
            return
        if not self.current_sys or self.current_sys in ("---", "Unknown"):
            return
        self.system_info_hud.on_system_arrival(
            self.current_sys,
            self.star_class,
            list(self.scan_items),
            dict(self.body_signals),
            self.total,
        )

    def _copy_waypoint_to_clipboard(self, waypoint_name, log_label="NEXT WAYPOINT"):
        if not waypoint_name:
            return False
        if threading.current_thread() is not threading.main_thread():
            # Journal batches run on the watcher thread. Tk clipboard work
            # must remain on the UI thread; the old nested root.update() call
            # could freeze startup while replay callbacks accumulated.
            self.root.after(
                0,
                lambda name=waypoint_name, label=log_label: self._copy_waypoint_to_clipboard(name, label),
            )
            return True
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(waypoint_name)
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
        route_waypoint = None
        route_counts = None
        
        if self.waypoint_manager.waypoints:
            total_wp = len(self.waypoint_manager.waypoints)
            
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
                route_waypoint = next_wp.get("name")
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
            self.scanned, self.total, custom_r_pos, self.organic_count, self.system_traffic, game_r_pos,
            route_waypoint, route_counts, "OK", None, self._build_navigation_hud_context()
        ))
        self.update_scan_hud()
        self._perf_spike("_perform_hud_update", t0, threshold_ms=30.0)

    @staticmethod
    def _format_hud_credits(value):
        try:
            value = int(value or 0)
        except Exception:
            return "---"
        sign = "-" if value < 0 else ""
        value = abs(value)
        for suffix, divisor in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
            if value >= divisor:
                return f"{sign}{value / divisor:.1f}{suffix} CR"
        return f"{sign}{value:,} CR"

    @staticmethod
    def _format_hud_distance(coords_a, coords_b):
        if not coords_a or not coords_b:
            return "--"
        try:
            dist = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(coords_a, coords_b)))
            return f"{dist:,.1f} LY"
        except Exception:
            return "--"

    def _latest_hud_balance(self):
        if self.cmdr_balance is not None:
            self._hud_balance_cache = {"ts": time.time(), "balance": self.cmdr_balance}
            return self.cmdr_balance
        now = time.time()
        if now - float(self._hud_balance_cache.get("ts") or 0) < 5.0:
            return self._hud_balance_cache.get("balance")
        balance = None
        try:
            conn = trade_marketdb.connect()
            try:
                row = conn.execute("SELECT balance FROM balance_log ORDER BY ts DESC LIMIT 1").fetchone()
            finally:
                conn.close()
            if row:
                balance = row[0]
        except Exception:
            balance = None
        self._hud_balance_cache = {"ts": now, "balance": balance}
        return balance

    def _build_navigation_hud_context(self):
        current = self.current_sys if self.current_sys and self.current_sys != "---" else "---"
        previous = getattr(self, "previous_sys", None) or "---"
        previous_coords = getattr(self, "previous_coords", None)
        next_name = None
        next_coords = None
        route = list(getattr(self, "route_list", None) or [])
        entries = getattr(self, "nav_route_entries", None) or []
        route_idx = -1
        route_remaining = None

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
                route_remaining = max(0, len(route) - route_idx - 1)
                if route_idx + 1 < len(route):
                    next_name = route[route_idx + 1]
                    if route_idx + 1 < len(entries):
                        next_coords = entries[route_idx + 1].get("StarPos")
            else:
                route_remaining = len(route)
                next_name = route[0]
                if entries:
                    next_coords = entries[0].get("StarPos")

        if not next_name and getattr(self, "target_waypoint", None):
            next_name = self.target_waypoint.get("name")
            next_coords = self.target_waypoint.get("coords")
        if not next_name:
            next_name = self.dest_name
        if next_name and not next_coords:
            for entry in entries:
                if entry.get("StarSystem") == next_name:
                    next_coords = entry.get("StarPos")
                    break

        waypoint_manager = getattr(self, "waypoint_manager", None)
        hops, hops_truncated = route_strip.build_route_hops(
            self.current_coords, route, entries, current, waypoint_manager=waypoint_manager
        )

        if waypoint_manager and waypoint_manager.waypoints:
            route_mode = "WAYPOINTS"
        elif route:
            route_mode = "GAME NAV ROUTE"
        elif self.dest_name:
            route_mode = "VOID ROUTE"
        else:
            route_mode = "NO ROUTE"

        cargo_tons = int(getattr(self, "current_cargo_tons", 0) or 0)
        if not cargo_tons and getattr(self, "current_cargo_inventory", None):
            try:
                cargo_tons = sum(int(item.get("Count", item.get("count", 0)) or 0) for item in self.current_cargo_inventory)
            except Exception:
                cargo_tons = 0
        cargo_cap = int(getattr(self, "cargo_capacity", 0) or 0)
        trade_profit = int((getattr(self, "trade_session", {}) or {}).get("profit", 0) or 0)
        badges = []
        if self.system_undiscovered:
            badges.append(("UNDISC", "alert"))
        if self.system_bio_signals > 0:
            badges.append((f"BIO {self.system_bio_signals}", "alert"))
        elif self.organic_count:
            badges.append((f"BIO {self.organic_count}", "ok"))
        if self.valuable_bodies:
            badges.append((f"VALUE {len(self.valuable_bodies)}", "alert"))
        if self.fss_summary_active:
            badges.append(("FSS", "alert"))
        if self.current_docked:
            badges.append(("DOCKED", "ok"))
        if not badges:
            badges.append(("CLEAR", "muted"))

        return {
            "route_mode": route_mode,
            "previous": previous,
            "current": current,
            "next": next_name or "---",
            "prev_distance": self._format_hud_distance(previous_coords, self.current_coords),
            "next_distance": self._format_hud_distance(self.current_coords, next_coords),
            "route_remaining": route_remaining,
            "hops": hops,
            "hops_truncated": hops_truncated,
            "total_distance_text": route_strip.total_distance_text(hops, hops_truncated),
            "cargo": f"{cargo_tons}/{cargo_cap}T" if cargo_cap else f"{cargo_tons}T",
            "trade_profit": self._format_hud_credits(trade_profit),
            "credits": self._format_hud_credits(self._latest_hud_balance()),
            "station": self.current_station_name or "",
            "docked": bool(self.current_docked),
            "landed": bool(getattr(self, "current_landed", False)),
            "in_fighter": bool(getattr(self, "current_in_fighter", False)),
            "in_srv": bool(getattr(self, "current_in_srv", False)),
            "on_foot": bool(getattr(self, "current_on_foot", False)),
            "vehicle_name": getattr(self, "current_vehicle_name", ""),
            "in_fss": bool(getattr(self, "in_fss", False)),
            "flight_state": getattr(self, "hud_flight_state", "FLIGHT"),
            "music_mode": getattr(self, "current_music_mode", ""),
            "music_track": getattr(self, "current_music_track", ""),
            "badges": badges[:6],
        }

    @staticmethod
    def _classify_music_track(track):
        raw = str(track or "").strip()
        key = raw.replace(" ", "").replace("-", "_").lower()
        label = raw.replace("_", " ").strip() or "No Track"
        if not key or key == "notrack":
            return "", "No Track", False, "INFO"
        if key == "onfoot":
            return "ONFOOT", "On Foot", True, "INFO"
        if key in ("galaxymap", "systemmap", "galacticpowers"):
            return "MAP", label, True, "INFO"
        if key in ("supercruise", "destinationfromsupercruise", "destinationfromhyperspace"):
            return "SUPERCRUISE", label, False, "INFO"
        if key in ("starport", "dockingcomputer"):
            return "STATION", label, True, "INFO"
        if key in ("exploration", "unknown_exploration"):
            return "EXPLORATION", label, True, "INFO"
        if "combat" in key or key in ("capitalship", "unknown_encounter"):
            severity = "WARN" if key in ("capitalship", "unknown_encounter") else "INFO"
            return "COMBAT", label, True, severity
        return "MUSIC", label, False, "INFO"

    def _is_redundant_music_event(self, event_name, payload):
        if event_name != "Music":
            return False
        payload = payload if isinstance(payload, dict) else {}
        track = str(payload.get("MusicTrack") or payload.get("music_track") or "").strip()
        if not track:
            return True
        return track == getattr(self, "current_music_track", "")

    def _handle_music_event(self, payload, startup_replay=False):
        payload = payload if isinstance(payload, dict) else {}
        track = str(payload.get("MusicTrack") or payload.get("music_track") or "").strip()
        mode, label, visible, severity = self._classify_music_track(track)
        if not track:
            return
        previous_track = getattr(self, "current_music_track", "")
        previous_mode = getattr(self, "current_music_mode", "")
        if track == previous_track:
            return

        self.current_music_track = track
        self.current_music_mode = mode
        self.current_music_label = label
        self._last_music_event_ts = time.time()
        if mode == "ONFOOT":
            self.current_on_foot = True
        if mode != previous_mode:
            self.update_hud()

        if visible and not self.batch_mode and not startup_replay:
            self.add_event_feed_entry("MUSIC", f"{mode.title()}: {label}", severity=severity, copy_text=track)

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

    def _queue_edsm_upload(self, raw_event, allow_startup=False, flush=False, startup_replay=False):
        """Queue accepted live journal events for EDSM without replaying startup history."""
        if ((self.is_first_load or startup_replay) and not allow_startup) or not isinstance(raw_event, dict):
            return False
        self.edsm.queue_journal_event(
            raw_event,
            system_name=self.current_sys,
            system_coords=self.current_coords if isinstance(self.current_coords, list) else None,
            system_address=self.current_system_address,
        )
        if flush:
            self.edsm.flush_upload_queue()
        self._refresh_commander_profile_window()
        return True

    def _log_balance_async(self, timestamp, balance):
        if balance is None:
            return
        ts = trade_marketdb.parse_update_time(timestamp) or trade_marketdb.now_epoch()

        def worker():
            try:
                trade_marketdb.log_balance(ts, balance)
            except Exception:
                pass

        threading.Thread(target=worker, name="trade-balance-log", daemon=True).start()

    def _set_commander_balance(self, balance, loan=None, timestamp=None, log=True):
        try:
            balance = int(balance)
        except Exception:
            return False
        changed = self.cmdr_balance != balance or (loan is not None and self.cmdr_loan != loan)
        self.cmdr_balance = balance
        self._hud_balance_cache = {"ts": time.time(), "balance": balance}
        if loan is not None:
            self.cmdr_loan = loan
        if log:
            self._log_balance_async(timestamp, balance)
        if changed:
            self._refresh_commander_profile_window()
            if self.trade_window and self.trade_window.is_open():
                self.root.after(0, self.trade_window._refresh_summary)
            self.update_hud()
        return changed

    def _apply_credit_event(self, ev, raw, log=True):
        if not isinstance(raw, dict):
            return False
        timestamp = raw.get("timestamp")
        for key in ("Credits", "Balance"):
            if raw.get(key) is not None:
                return self._set_commander_balance(raw.get(key), timestamp=timestamp, log=log)
        if self.cmdr_balance is None:
            return False

        delta = 0
        if ev == "MarketBuy":
            delta -= int(raw.get("TotalCost") or ((raw.get("BuyPrice") or raw.get("Price") or 0) * (raw.get("Count") or 0)) or 0)
        elif ev == "MarketSell":
            delta += int(raw.get("TotalSale") or ((raw.get("SellPrice") or raw.get("Price") or 0) * (raw.get("Count") or 0)) or 0)
        elif ev == "MissionCompleted":
            delta += int(raw.get("Reward") or 0)
        elif ev in ("RedeemVoucher", "SellExplorationData", "MultiSellExplorationData"):
            delta += int(raw.get("Amount") or raw.get("TotalEarnings") or raw.get("TotalSale") or 0)
        elif ev == "SellOrganicData":
            delta += int(raw.get("TotalSale") or raw.get("TotalValue") or 0)
            if not delta:
                for sample in raw.get("BioData") or ():
                    if not isinstance(sample, dict):
                        continue
                    delta += int(sample.get("Value") or 0)
                    delta += int(sample.get("Bonus") or 0)
        elif ev in ("PayFines", "PayBounties", "BuyExplorationData", "BuyTradeData", "RefuelAll", "RefuelPartial", "Repair", "RepairAll", "BuyAmmo"):
            delta -= int(raw.get("Amount") or raw.get("Cost") or 0)
        elif ev in ("ModuleBuy", "ShipyardBuy"):
            delta -= int(raw.get("BuyPrice") or raw.get("ShipPrice") or raw.get("Price") or 0)
        elif ev in ("ModuleSell", "ShipyardSell"):
            delta += int(raw.get("SellPrice") or raw.get("ShipPrice") or raw.get("Price") or 0)
        if not delta:
            return False
        return self._set_commander_balance(int(self.cmdr_balance or 0) + delta, timestamp=timestamp, log=log)

    def _push_live_toast(self, title, message="", severity="info", duration_s=10):
        toast = getattr(self, "toast_hud", None)
        if toast:
            toast.push(title, message, severity=severity, duration_s=duration_s)

    def _handle_live_journal_toast(self, ev, raw, d, startup_replay=False):
        """Surface selected, actionable journal events without replay noise."""
        if startup_replay or getattr(self, "is_first_load", False):
            return
        raw = raw if isinstance(raw, dict) else {}
        d = d if isinstance(d, dict) else raw

        if ev in ("Touchdown", "Liftoff"):
            body = d.get("body") or raw.get("Body") or "surface"
            coords = ""
            lat, lon = d.get("latitude"), d.get("longitude")
            if lat is not None and lon is not None:
                coords = f"  {float(lat):.4f}, {float(lon):.4f}"
            self._push_live_toast(ev.upper(), f"{body}{coords}", "success" if ev == "Touchdown" else "info")
        elif ev == "Disembark":
            where = raw.get("Body") or raw.get("StationName") or raw.get("SettlementName") or "On foot"
            self._push_live_toast("ON FOOT", where, "info")
        elif ev == "Embark":
            vehicle = "SRV" if raw.get("SRV") else (raw.get("Taxi") and "taxi") or "ship"
            self._push_live_toast("EMBARKED", str(vehicle), "info")
        elif ev == "HeatWarning":
            self._push_live_toast("OVERHEATING", "Ship temperature critical", "warn", 15)
        elif ev == "HeatDamage":
            self._push_live_toast("HEAT DAMAGE", "Modules are taking heat damage", "fail", 15)
        elif ev == "UnderAttack":
            target = raw.get("Target") or raw.get("Target_Localised") or "Hostile fire detected"
            self._push_live_toast("UNDER ATTACK", target, "fail", 15)
        elif ev == "ShieldState":
            shields_up = bool(raw.get("ShieldsUp"))
            if shields_up != self._toast_shields_up:
                self._toast_shields_up = shields_up
                self._push_live_toast("SHIELDS RESTORED" if shields_up else "SHIELDS OFFLINE", "", "success" if shields_up else "fail", 12)
        elif ev == "HullDamage":
            health = float(raw.get("Health", 1.0) or 0.0)
            if health > 0.80:
                self._toast_hull_thresholds_seen.clear()
            crossed = [n for n in (75, 50, 25, 10) if health * 100 <= n and n not in self._toast_hull_thresholds_seen]
            if crossed:
                self._toast_hull_thresholds_seen.update(crossed)
                threshold = min(crossed)
                self._push_live_toast("HULL CRITICAL" if threshold <= 25 else "HULL DAMAGE", f"Integrity at {health * 100:.0f}%", "fail" if threshold <= 25 else "warn", 15)
        elif ev in ("Interdicted", "EscapeInterdiction"):
            escaped = ev == "EscapeInterdiction" or bool(raw.get("Submitted") is False)
            actor = raw.get("Interdictor") or raw.get("Interdictor_Localised") or raw.get("InterdictorName") or "Unknown contact"
            self._push_live_toast("INTERDICTION ESCAPED" if escaped else "INTERDICTED", actor, "success" if escaped else "warn", 15)
        elif ev == "JetConeBoost":
            self._push_live_toast("FSD SUPERCHARGED", "Jet-cone boost acquired", "success", 10)
        elif ev == "JetConeDamage":
            self._push_live_toast("JET CONE DAMAGE", "Exit the cone immediately", "fail", 18)
        elif ev in ("FighterDestroyed", "SRVDestroyed"):
            self._push_live_toast("FIGHTER DESTROYED" if ev == "FighterDestroyed" else "SRV DESTROYED", "", "fail", 15)
        elif ev == "Died":
            killer = raw.get("KillerName_Localised") or raw.get("KillerName") or "Commander lost"
            self._push_live_toast("DESTRUCTION", killer, "fail", 20)
        elif ev in ("MissionAccepted", "MissionCompleted", "MissionFailed", "MissionAbandoned"):
            name = raw.get("LocalisedName") or raw.get("Name_Localised") or raw.get("Name") or "Mission"
            titles = {"MissionAccepted": "MISSION ACCEPTED", "MissionCompleted": "MISSION COMPLETE", "MissionFailed": "MISSION FAILED", "MissionAbandoned": "MISSION ABANDONED"}
            sev = "success" if ev == "MissionCompleted" else ("fail" if ev in ("MissionFailed", "MissionAbandoned") else "info")
            self._push_live_toast(titles[ev], name, sev, 15)
        elif ev == "ScanOrganic":
            species = d.get("species") or d.get("genus") or "Organic"
            scan_type = str(d.get("scan_type") or raw.get("ScanType") or "").lower()
            complete = bool(d.get("is_complete")) or scan_type == "analyse"
            sample = d.get("sample_idx")
            max_samples = d.get("max_samples") or 3
            detail = "Analysis complete" if complete else (f"Sample {sample}/{max_samples}" if sample else "Sample registered")
            self._push_live_toast("BIO COMPLETE" if complete else "BIO SAMPLE", f"{species}: {detail}", "success" if complete else "info", 12)
        elif ev == "CodexEntry":
            name = d.get("name") or raw.get("Name_Localised") or raw.get("Name") or "New Codex entry"
            category = d.get("category") or raw.get("Category_Localised") or "Discovery"
            self._push_live_toast("CODEX DISCOVERY", f"{category}: {name}", "success", 15)
        elif ev in ("CommitCrime", "Bounty"):
            detail = raw.get("CrimeType_Localised") or raw.get("CrimeType") or raw.get("Victim") or raw.get("Target_Localised") or raw.get("Target") or "Legal status changed"
            self._push_live_toast("CRIME REPORTED" if ev == "CommitCrime" else "BOUNTY AWARDED", str(detail), "warn", 15)

    def process_event(self, data):
        ev = data.get("type") or data.get("event")
        raw = data.get("raw", data)
        d = data.get("data", data)
        startup_replay = bool(data.get("startup_catchup"))
        if ev in ("Commander", "LoadGame"):
            commander = d.get("name") if ev == "Commander" else d.get("commander")
            fid = d.get("fid")
            if commander:
                self._switch_commander_profile(commander, fid)
        try:
            self.achievement_engine.process_event(
                data,
                notify=not startup_replay,
                historical=startup_replay,
            )
        except Exception as exc:
            logging.warning(f"Achievement engine event error [{ev}]: {exc}")
        self._record_journal_event()
        self._handle_live_journal_toast(ev, raw, d, startup_replay=startup_replay)
        if ev != "LoadGame":
            self._apply_credit_event(ev, raw if isinstance(raw, dict) else d, log=not startup_replay)
        if ev != "LoadGame" and self.edsm.is_credit_event(ev):
            self._queue_edsm_upload(raw, flush=True, startup_replay=startup_replay)
        current_journal = getattr(self.watcher, "last_journal", None)
        if current_journal and current_journal != self.last_logged_journal_file:
            self.last_logged_journal_file = current_journal
            self.log(f"Journal file: {os.path.basename(current_journal)}")
        if ev and not startup_replay and not self._is_redundant_music_event(ev, raw if isinstance(raw, dict) else d):
            self.add_journal_history_entry(ev, raw if isinstance(raw, dict) else d)
        if self.mining_window and self.mining_window.is_open():
            self.mining_window.process_event(data)

        # Route carrier events defensively — a tracker failure must not cascade
        # into the main navigation if/elif chain (fix #2).
        if ev and ev.startswith("Carrier"):
            try:
                self.carrier_tracker.process_event(raw)
            except Exception as _ct_err:
                logging.warning(f"CarrierTracker.process_event error [{ev}]: {_ct_err}")

        if ev in ("FileHeader", "Fileheader"):
            game_version = d.get("gameversion")
            game_build = d.get("build")
            self.game_version = game_version or self.game_version
            self.game_build = game_build if game_build is not None else self.game_build
            if game_version and game_build:
                self.edsm.set_game_version(game_version, game_build)
            self.log(f"Game version detected: {game_version} ({game_build})")

        elif ev == "Loadout":
            self.cargo_capacity = d.get("cargo_capacity", 0)
            fuel_cap = (raw.get("FuelCapacity") or {}) if isinstance(raw, dict) else {}
            self.fuel_capacity_main = fuel_cap.get("Main")
            self._low_fuel_warned = False
            self.cmdr_ship.update({
                "ship": d.get("ship") or self.cmdr_ship.get("ship"),
                "ship_id": d.get("ship_id") or self.cmdr_ship.get("ship_id"),
                "ship_name": d.get("ship_name") or self.cmdr_ship.get("ship_name"),
                "ship_ident": d.get("ship_ident") or self.cmdr_ship.get("ship_ident"),
                "modules_value": d.get("modules_value"),
                "hull_health": d.get("hull_health"),
                "max_jump_range": d.get("max_jump_range"),
                "rebuy": d.get("rebuy"),
                "cargo_capacity": self.cargo_capacity,
            })
            self.watcher.force_check_cargo()
            if self.colony_overlay:
                self.colony_overlay.update()
            self._queue_edsm_upload(raw, allow_startup=True)
            self._refresh_commander_profile_window()

        elif ev == "Cargo":
            # Journal can emit Cargo before/without immediate file polling update.
            self.watcher.force_check_cargo()
            self._queue_edsm_upload(raw, allow_startup=True)

        elif ev == "CargoDepot":
            self._queue_edsm_upload(raw, startup_replay=startup_replay)

        elif ev in ("MarketBuy", "MarketSell"):
            if not startup_replay:
                self._record_trade_session_event(ev, raw if isinstance(raw, dict) else d)
            self._queue_edsm_upload(raw, startup_replay=startup_replay)

        elif ev in ("NavRoute", "NavRouteClear"):
            # Nav route details live in NavRoute.json; trigger immediate refresh.
            self.watcher.force_check_nav()

        elif ev == "Commander":
            self.cmdr_name = d.get("name", "CMDR")
            self.cmdr_fid = d.get("fid") or self.cmdr_fid
            self._queue_edsm_upload(raw, allow_startup=True)

        elif ev == "Rank":
            self.cmdr_ranks.update(d)
            self._queue_edsm_upload(raw, allow_startup=True)
            self._refresh_commander_profile_window()

        elif ev == "Progress":
            self.cmdr_rank_progress.update(d)
            self._queue_edsm_upload(raw, allow_startup=True)
            self._refresh_commander_profile_window()

        elif ev == "Reputation":
            self.cmdr_reputation.update(d)
            self._queue_edsm_upload(raw, allow_startup=True)
            self._refresh_commander_profile_window()

        elif ev == "Statistics":
            self._queue_edsm_upload(raw, allow_startup=True)

        elif ev == "Materials":
            self._queue_edsm_upload(raw, allow_startup=True)
            self._sync_materials_full(
                raw.get("Raw") or [],
                raw.get("Manufactured") or [],
                raw.get("Encoded") or [],
            )

        elif ev in ("MaterialCollected", "MaterialDiscarded", "MaterialTrade",
                    "EngineerCraft", "Synthesis", "TechnologyBroker"):
            self._queue_edsm_upload(raw, startup_replay=startup_replay)
            if not startup_replay:
                self._process_material_change(ev, raw)

        elif ev == "LoadGame":
            self.cmdr_name = d.get("commander", "CMDR")
            self.cmdr_fid = d.get("fid") or self.cmdr_fid
            game_version = d.get("gameversion")
            game_build = d.get("build")
            self.game_version = game_version or self.game_version
            self.game_build = game_build if game_build is not None else self.game_build
            if d.get("horizons") is not None:
                self.game_horizons = bool(d.get("horizons"))
            if d.get("odyssey") is not None:
                self.game_odyssey = bool(d.get("odyssey"))
            if game_version and game_build:
                self.edsm.set_game_version(game_version, game_build)
                self.log(f"Game version detected from LoadGame: {game_version} ({game_build})")
            credits = d.get("credits")
            loan = d.get("loan")
            if credits is not None:
                self._set_commander_balance(credits, loan=loan, timestamp=raw.get("timestamp"))
                self._queue_edsm_upload(raw, allow_startup=True, flush=True)
            self.cmdr_ship.update({
                "ship": d.get("ship") or self.cmdr_ship.get("ship"),
                "ship_localised": d.get("ship_localised") or self.cmdr_ship.get("ship_localised"),
                "ship_id": d.get("ship_id") or self.cmdr_ship.get("ship_id"),
                "ship_name": d.get("ship_name") or self.cmdr_ship.get("ship_name"),
                "ship_ident": d.get("ship_ident") or self.cmdr_ship.get("ship_ident"),
                "fuel_level": d.get("fuel_level"),
                "fuel_capacity": d.get("fuel_capacity"),
                "game_mode": d.get("game_mode"),
                "group": d.get("group"),
            })
            self._refresh_commander_profile_window()

        elif ev == "ScanOrganic":
            if not self._matches_current_system_address(d):
                return
            body_id = self._normalize_body_id(d.get("body_id"))
            # ScanOrganic doesn't include BodyName — look it up from the Scan
            # event cache (scan_items_by_id) which does have it.
            _scan_item = self.scan_items_by_id.get(body_id, {}) if body_id is not None else {}
            body_label = (d.get("body_name")
                          or _scan_item.get("name")
                          or (f"Body {body_id}" if body_id is not None else "Unknown Body"))
            species = d.get("species") or d.get("genus") or "Organic"
            species_key = f"{body_id}|{species}" if body_id is not None else f"{body_label}|{species}"

            existing = self.last_bio_scan.get(species_key, {})
            is_complete = bool(d.get("is_complete"))
            was_complete = bool(existing.get("is_complete"))

            self.last_bio_scan[species_key] = {
                "body_id":        body_id,
                "body_name":      body_label,
                "species":        species,
                "genus":          d.get("genus"),
                "species_value":  bio_values.species_value(species),
                "genus_value":    bio_values.genus_info(d.get("genus") or species),
                "colony_m":       bio_values.GENUS_COLONY_M.get(d.get("genus") or species),
                "sample_idx":     d.get("sample_idx"),
                "max_samples":    d.get("max_samples", 3),
                "scan_type":      d.get("scan_type"),
                "is_new_entry":   bool(d.get("is_new_entry")),
                "is_new_sample":  bool(d.get("is_new_sample")),
                "is_complete":    is_complete,
                "system_address": self.current_system_address,
            }

            if is_complete and not was_complete:
                self.organic_count += 1
                self.add_event_feed_entry("BIO", f"Organic complete: {species} ({body_label})", severity="INFO", copy_text=species)
            elif d.get("is_new_sample"):
                sample_idx = d.get("sample_idx")
                sample_txt = f" sample {sample_idx}" if sample_idx is not None else ""
                self.add_event_feed_entry("BIO", f"Organic{sample_txt}: {species} ({body_label})", severity="INFO", copy_text=species)

            if body_id is not None:
                item = self.scan_items_by_id.get(body_id)
                if item:
                    organic_scans = item.setdefault("organic_scans", {})
                    organic_scans[species_key] = dict(self.last_bio_scan[species_key])
                    item["organic_complete_count"] = sum(1 for scan in organic_scans.values() if scan.get("is_complete"))
                    if item.get("_ts") is None:
                        item["_ts"] = int(time.time())
                    self.save_scan_item_to_db(self.current_sys, item)

            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()
                self._refresh_exploration_window()

        elif ev == "Location" or ev == "FSDJump" or ev == "StartJump" or (ev == "CarrierJump" and d.get("docked")):
            # Do not update HUDs during jump charge; wait for arrival.
            if ev == "StartJump":
                self.in_fss = False
                self.fss_summary_active = False
                jump_type = d.get("jump_type") or (raw.get("JumpType") if isinstance(raw, dict) else "")
                jump_type = str(jump_type or "").lower()
                self.hud_flight_state = "SUPERCRUISE" if jump_type == "supercruise" else "HYPERSPACE"
                self.update_hud()
                return

            # CarrierJump counts as a jump for the player when they are docked on board.
            is_jump = ev in ("FSDJump", "CarrierJump")

            # Reset FSS state on jump completion
            if is_jump:
                self.in_fss = False
                self.fss_summary_active = False
                self.hud_flight_state = "FLIGHT"

            prev_coords = self.current_coords if isinstance(self.current_coords, list) else None

            # State reset for new system
            incoming_sys = d.get("star_system", "Unknown")
            outgoing_sys = self.current_sys if self.current_sys not in ("---", "Unknown", incoming_sys) else None
            traffic_before_reset = dict(self.system_traffic or {})
            preserve_startup_traffic = (
                startup_replay
                and incoming_sys == self.last_traffic_system
                and traffic_before_reset
            )
            self.current_sys = incoming_sys
            if outgoing_sys:
                self.previous_sys = outgoing_sys
                self.previous_coords = prev_coords
            if self.current_sys and self.current_sys not in ("---", "Unknown"):
                self.session_systems.add(self.current_sys)
            self.current_system_address = self._normalize_system_address(d.get("system_address"))
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
                    self.trade_jump_history.appendleft({
                        "system": self.current_sys,
                        "distance": jump_ly,
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass
            
            # Load from history if available
            self.load_system_from_db(self.current_sys)

            self.organic_count = 0 # Reset bio count for new system
            self.system_bio_signals = 0
            self.last_scan_event = None
            self.last_bio_scan = {}
            self._stale_bio_warned = set()
            self.system_stars.clear()
            self.body_scan_data.clear()
            self.current_body_id   = None
            self.current_body_name = ""
            self.valuable_system = False
            self.valuable_bodies.clear()
            self.system_traffic = (
                traffic_before_reset
                if preserve_startup_traffic
                else {'day': 0, 'week': 0, 'total': 0}
            )
            self.scan_items = self.load_scan_items_from_db(self.current_sys)
            self.body_signals = {}
            self.body_dss_complete = set()
            self.system_undiscovered = False
            self.fss_all_bodies = False
            self.fss_summary_active = False
            self._rebuild_scan_index()
            self._rebuild_system_state_from_scan_items()

            if ev == "CarrierJump":
                log_msg = f"CARRIER JUMP: {self.current_sys}"
                evt_tag = "FC JUMP"
                evt_msg = f"Carrier arrived: {self.current_sys}"
            elif is_jump:
                log_msg = f"JUMP: {self.current_sys}"
                evt_tag = "JUMP"
                evt_msg = f"Arrived: {self.current_sys}"
            else:
                log_msg = f"LOCATION: {self.current_sys}"
                evt_tag = "SYSTEM"
                evt_msg = f"Location set: {self.current_sys}"
            self.log(log_msg)
            self.add_event_feed_entry(evt_tag, evt_msg, severity="INFO", copy_text=self.current_sys, url=f"https://www.edsm.net/show-system?systemName={self.current_sys.replace(' ', '+')}")
            if is_jump:
                self._queue_edsm_upload(raw, startup_replay=startup_replay)
                self.edsm.flush_upload_queue()
            elif ev == "Location":
                self._queue_edsm_upload(raw, allow_startup=True)

            # Track every visited system so the BGS window shows a full history.
            self.db_record_visit(self.current_sys, self.current_system_address)

            # BGS snapshot — uses the journal event timestamp as a dedup key so
            # startup replay never creates duplicate rows.
            _factions = raw.get("Factions") if isinstance(raw, dict) else None
            if _factions and self.current_sys and self.current_sys not in ("---", "Unknown"):
                _event_ts = raw.get("timestamp") if isinstance(raw, dict) else None
                self.db_save_bgs_snapshot(
                    self.current_sys, self.current_system_address,
                    _factions, _event_ts,
                )
            if not self.batch_mode and self.bgs_window and self.bgs_window.is_open():
                self.bgs_window.refresh_current()
            
            if not self.batch_mode:
                sys_text = self.current_sys.upper()
                if self.star_class: sys_text += f" [{self.star_class}]"
                self.root.after(0, lambda: self.sys_stat.config(text=sys_text))
                self.update_nav_label()
            # Bio logs hidden for now (counting disabled)
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.root.after(0, self.update_waypoint_display)
                self.schedule_dashboard_refresh(full=True)
                self.update_hud()
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

            # Show system info overlay for live arrivals and the immediate
            # startup location seed, but not for replayed startup history.
            # Gate on startup_replay (not batch_mode) so it still fires when
            # FSDJump arrives in the same read cycle as FSSDiscoveryScan and
            # the watcher promotes them into a batch with batch_mode=True.
            if self.system_info_hud and not startup_replay:
                _sys  = self.current_sys
                _sc   = self.star_class
                _si   = list(self.scan_items)
                _bs   = dict(self.body_signals)
                _tot  = self.total
                self.root.after(0, lambda: self.system_info_hud.on_system_arrival(
                    _sys, _sc, _si, _bs, _tot))
            if self.survey_status_hud and not startup_replay:
                self.root.after(0, lambda: self.survey_status_hud.update(
                    self.current_sys, self.scanned, self.total, self.scan_items, self.body_signals))
            self._refresh_exploration_window()

        elif ev == "Docked":
            station = d.get("StationName") or d.get("station_name", "Unknown")
            stype = d.get("StationType") or d.get("station_type", "")
            self.current_docked = True
            self.current_on_foot = False
            self.hud_flight_state = "DOCKED"
            self.current_station_name = station
            self.current_station_type = stype or None
            self.current_station_market_id = d.get("MarketID") or d.get("market_id")
            # Docked has no dedicated journal_watcher normalization, so `d` here
            # is the raw ED journal dict — these fields are already present on it.
            self.current_station_economy = d.get("StationEconomy_Localised") or d.get("StationEconomy")
            self.current_station_economies = d.get("StationEconomies") or []
            faction = d.get("StationFaction") or {}
            self.current_station_government = d.get("StationGovernment_Localised") or d.get("StationGovernment")
            self.current_station_faction = {
                "name": faction.get("Name"),
                "state": faction.get("FactionState"),
            } if faction.get("Name") else None
            self.current_station_allegiance = d.get("StationAllegiance")
            self.current_station_services = d.get("StationServices") or []
            self.current_station_dist_ls = d.get("DistFromStarLS")
            self.current_station_landing_pads = d.get("LandingPads")
            label = f"{station} ({stype})" if stype else station
            self._queue_edsm_upload(raw, startup_replay=startup_replay)
            self.update_hud()
            if self.station_info_hud and not self.batch_mode and not startup_replay:
                self.station_info_hud.on_docked(self)
            if not self.batch_mode and not startup_replay:
                self.add_event_feed_entry("DOCK", f"Docked: {label}", severity="INFO", copy_text=station)

        elif ev == "Undocked":
            station = d.get("StationName") or d.get("station_name", "")
            self.current_docked = False
            self.current_on_foot = False
            self.hud_flight_state = "FLIGHT"
            self.current_station_name = None
            self.current_station_type = None
            self.current_station_market_id = None
            self.current_station_economy = None
            self.current_station_economies = []
            self.current_station_government = None
            self.current_station_faction = None
            self.current_station_allegiance = None
            self.current_station_services = []
            self.current_station_dist_ls = None
            self.current_station_landing_pads = None
            self._queue_edsm_upload(raw, startup_replay=startup_replay)
            self.update_hud()
            if self.station_info_hud:
                self.station_info_hud.hide()
            if not self.batch_mode and not startup_replay:
                self.add_event_feed_entry("DOCK", f"Undocked: {station}", severity="INFO", copy_text=station)

        elif ev == "SupercruiseEntry":
            self.hud_flight_state = "SUPERCRUISE"
            self.current_docked = False
            self.current_on_foot = False
            self.update_hud()

        elif ev == "SupercruiseExit":
            self.hud_flight_state = "FLIGHT"
            self.update_hud()

        elif ev == "Music":
            self._handle_music_event(raw if isinstance(raw, dict) else d, startup_replay=startup_replay)

        elif ev == "Disembark":
            vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
            if vehicle_id is not None and self.current_vehicle_name:
                self._vehicle_name_by_id[vehicle_id] = self.current_vehicle_name
            if self.current_vehicle_name:
                self._last_surface_vehicle_name = self.current_vehicle_name
            self.current_on_foot = True
            self.current_in_srv = False
            self.current_in_fighter = False
            self.hud_flight_state = "ONFOOT"
            self.update_hud()

        elif ev == "Embark":
            vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
            from_srv = bool(d.get("SRV") or (raw.get("SRV") if isinstance(raw, dict) else False))
            self.current_on_foot = False
            if from_srv:
                remembered_vehicle = self._vehicle_name_by_id.get(vehicle_id) if vehicle_id is not None else ""
                self.current_vehicle_id = vehicle_id
                self.current_vehicle_name = remembered_vehicle or self.current_vehicle_name or self._last_surface_vehicle_name or "SRV"
                self.current_in_srv = True
                self.current_in_fighter = False
                self.hud_flight_state = "NOMAD" if self.current_vehicle_name == "NOMAD" else "SRV"
            elif self.current_docked:
                self.current_vehicle_id = None
                self.current_vehicle_name = ""
                self.hud_flight_state = "DOCKED"
            elif self.current_landed:
                self.current_vehicle_id = None
                self.current_vehicle_name = ""
                self.hud_flight_state = "LANDED"
            else:
                self.current_vehicle_id = None
                self.current_vehicle_name = ""
                self.hud_flight_state = "FLIGHT"
            self.update_hud()

        elif ev == "LaunchFighter":
            self.current_in_fighter = True
            self.current_on_foot = False
            vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
            loadout = d.get("Loadout") or (raw.get("Loadout") if isinstance(raw, dict) else "")
            loadout = str(loadout or "").lower()
            self.current_vehicle_name = "NOMAD" if loadout == "galactic" else "FIGHTER"
            self.current_vehicle_id = vehicle_id
            if vehicle_id is not None:
                self._vehicle_name_by_id[vehicle_id] = self.current_vehicle_name
            self._last_surface_vehicle_name = self.current_vehicle_name
            self.hud_flight_state = self.current_vehicle_name
            self.update_hud()

        elif ev in ("DockFighter", "FighterDestroyed"):
            self.current_in_fighter = False
            self.current_vehicle_id = None
            self.current_vehicle_name = ""
            self.hud_flight_state = "LANDED" if self.current_landed else "FLIGHT"
            self.update_hud()

        elif ev == "DockSRV":
            vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
            vehicle_name = d.get("SRVType_Localised") or d.get("SRVType") or (raw.get("SRVType_Localised") if isinstance(raw, dict) else "")
            is_nomad = str(vehicle_name).lower() == "nomad"
            if vehicle_id is not None:
                self._vehicle_name_by_id[vehicle_id] = "NOMAD" if is_nomad else "SRV"
            if is_nomad:
                self.current_vehicle_name = ""
                self.current_in_fighter = False
            self.current_on_foot = False
            self.current_vehicle_id = None
            self.hud_flight_state = "LANDED" if self.current_landed else "FLIGHT"
            self.update_hud()

        elif ev == "FSSDiscoveryScan":
            if not self._matches_current_system_address(d):
                return
            if d.get("system_name") and d.get("system_name") != self.current_sys:
                return
            body_count = int(d.get("body_count") or 0)
            # Only advance total — never let a missing/zero BodyCount wipe a
            # value that load_system_from_db already restored from the DB.
            if body_count > 0:
                self.total = max(body_count, self.total)
                self._queue_edsm_upload(raw, startup_replay=startup_replay)
            self.fss_all_bodies = False
            # Progress=1.0 means every body in this system is already known/discovered
            # (e.g. Sol and other pre-populated systems). Treat it as fully scanned so
            # the HUD shows 100% without requiring individual FSS body scans.
            progress = d.get("progress", raw.get("Progress") if isinstance(raw, dict) else None)
            try:
                progress = float(progress) if progress is not None else None
            except (TypeError, ValueError):
                progress = None
            if progress is not None and progress >= 1.0 and self.total > 0:
                self._mark_system_scan_complete(self.total)
            else:
                self.db_update_system(self.current_sys, self.total, self.scanned)
                if not self.batch_mode:
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.log(f"🔭 HONK: {self.total} bodies detected.")
            self.add_event_feed_entry("SCAN", f"Honk complete: {self.total} bodies", severity="INFO", copy_text=self.current_sys)
            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()
                self._refresh_exploration_window()
                self._refresh_system_info_progress()

        elif ev == "DiscoveryScan":
            if not self._matches_current_system_address(d):
                return
            discovered = d.get("bodies", 0)
            if isinstance(discovered, int) and discovered > 0:
                self.total = max(self.total, self.scanned + discovered)
                self.db_update_system(self.current_sys, self.total, self.scanned)
                if not self.batch_mode:
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                    self.update_hud()
                    self.schedule_dashboard_refresh()

        elif ev == "NavBeaconScan":
            if not self._matches_current_system_address(d):
                return
            count = d.get("num_bodies", 0)
            if isinstance(count, int) and count > 0:
                self._mark_system_scan_complete(count)
                self.add_event_feed_entry("SCAN", f"Nav beacon scan: {count} bodies", severity="INFO", copy_text=self.current_sys)
                if not self.batch_mode:
                    self._refresh_system_info_progress()

        elif ev == "FSSAllBodiesFound":
            if not self._matches_current_system_address(d):
                return
            if not d.get("system_name") or d.get("system_name") == self.current_sys:
                count = d.get("count", self.total)
                if count:
                    self._queue_edsm_upload(raw, startup_replay=startup_replay)
                # Persist all scan_item body IDs we have so return visits restore correctly.
                for item in self.scan_items:
                    bid = item.get("body_id")
                    if bid is not None and bid not in self.scanned_bodies:
                        self.scanned_bodies.add(bid)
                        self.db_add_body(self.current_sys, bid)
                self.fss_all_bodies = True
                self._mark_system_scan_complete(count)
                self.log("📡 SYSTEM SCAN COMPLETE: All bodies found.")
                self.add_event_feed_entry("ALERT", "FSS complete: all bodies found", severity="WARN", copy_text=self.current_sys)
                if not self.batch_mode:
                    self._refresh_system_info_progress()

        elif ev == "FSSBodySignals":
            if not self._matches_current_system_address(d):
                return
            body_id = self._normalize_body_id(d.get("body_id"))
            if body_id is not None:
                bio_count = d.get("bio_count", 0)
                geo_count = d.get("geo_count", 0)
                if not startup_replay and (bio_count or geo_count):
                    body = d.get("body_name") or f"Body {body_id}"
                    parts = []
                    if bio_count:
                        parts.append(f"{bio_count} biological")
                    if geo_count:
                        parts.append(f"{geo_count} geological")
                    self._push_live_toast("SURFACE SIGNALS", f"{body}: {', '.join(parts)}", "success", 12)
                self._set_body_signals(body_id, bio_count, geo_count)
                item = self.scan_items_by_id.get(body_id)
                if item:
                    item["bio_count"] = bio_count
                    item["geo_count"] = geo_count
                    item["color"] = COLOR_ACCENT if (bio_count > 0 or (not item.get("is_star") and item.get("dss_reward", 0) > item.get("reward", 0))) else COLOR_TEXT
                    if item.get("_ts") is None:
                        item["_ts"] = int(time.time())
                    self.save_scan_item_to_db(self.current_sys, item)
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
                        self._refresh_exploration_window()
                        self._refresh_system_info_progress()

        elif ev == "SAASignalsFound":
            if not self._matches_current_system_address(d):
                return
            body_id = self._normalize_body_id(d.get("body_id"))
            if body_id is not None:
                bio_count = d.get("bio_count", 0)
                geo_count = d.get("geo_count", 0)
                if not startup_replay and (bio_count or geo_count):
                    body = d.get("body_name") or f"Body {body_id}"
                    parts = []
                    if bio_count:
                        parts.append(f"{bio_count} biological")
                    if geo_count:
                        parts.append(f"{geo_count} geological")
                    self._push_live_toast("DSS SIGNALS", f"{body}: {', '.join(parts)}", "success", 12)
                if bio_count or geo_count:
                    self._set_body_signals(body_id, bio_count, geo_count)
                item = self.scan_items_by_id.get(body_id)
                if item:
                    item["bio_count"] = bio_count
                    item["geo_count"] = geo_count
                    item["genuses"] = d.get("genuses") or item.get("genuses") or []
                    item["color"] = COLOR_ACCENT if (bio_count > 0 or (not item.get("is_star") and item.get("dss_reward", 0) > item.get("reward", 0))) else COLOR_TEXT
                    if item.get("_ts") is None:
                        item["_ts"] = int(time.time())
                    self.save_scan_item_to_db(self.current_sys, item)
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
                        self._refresh_exploration_window()
                        self._refresh_system_info_progress()

        elif ev == "SAAScanComplete":
            if not self._matches_current_system_address(d):
                return
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
                    self._queue_edsm_upload(raw, startup_replay=startup_replay)
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
                        self._refresh_system_info_progress()

        elif ev == "Scan":
            if not self._matches_current_system_address(d):
                return
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

            # Track star types for bio prediction: build parent-star lookup
            if star_type:
                self.system_stars[body_id] = star_type

            # Store planet conditions for bio prediction when we have a planet scan
            if d.get("planet_class") and body_id is not None:
                self.body_scan_data[body_id] = {
                    "body_name":        body_name,
                    "planet_class":     d.get("planet_class", ""),
                    "landable":         bool(d.get("landable")),
                    "surface_gravity":  d.get("surface_gravity"),
                    "gravity_g":        self._gravity_to_g(d.get("surface_gravity")),
                    "surface_temp":     d.get("surface_temp"),
                    "surface_pressure": d.get("surface_pressure"),
                    "atmosphere_type":  d.get("atmosphere_type", ""),
                    "volcanism":        d.get("volcanism", ""),
                    "materials":        d.get("materials") or {},
                    "atmos_comp":       d.get("atmos_comp") or {},
                    "parents":          d.get("parents") or [],
                    "bio_signals_count": d.get("bio_signals_count", 0),
                }
                self.body_scan_data[body_id]["predicted_genuses"] = self._bio_predictions_for_scan(self.body_scan_data[body_id])
            
            # Only count scans of stars or planets/moons, not belts.
            if d.get("is_body_scan"):
                # Ensure the scan belongs to the current system to prevent state corruption
                if d.get("star_system") and d.get("star_system") != self.current_sys:
                    return

                is_new_body_scan = body_id not in self.scanned_bodies
                
                if is_new_body_scan:
                    # --- State Updates for a new body ---
                    self.scanned_bodies.add(body_id)
                    self.db_add_body(self.current_sys, body_id)
                    # Derive scanned from len(scanned_bodies) rather than a raw increment.
                    # This prevents double-counting when scanned was pre-loaded from
                    # systems.scanned_count (e.g. after FSSAllBodiesFound) without having
                    # the individual body IDs in the bodies table.
                    new_count = len(self.scanned_bodies)
                    if new_count > self.scanned:
                        self.scanned = new_count
                    self.db_update_system(self.current_sys, self.total, self.scanned)
                    if not self.batch_mode:
                        self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                    self.last_scan_event = data
                    self.add_scan_item(raw)
                    self._queue_edsm_upload(raw, startup_replay=startup_replay)
                    if is_system_star_scan and d.get("was_discovered") is False:
                        self.system_undiscovered = True
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
                        self._refresh_system_info_progress()

                    body_label = body_name or "Unknown Body"
                    landable_marker = " 🚀" if d.get("landable") else ""
                    self.add_event_feed_entry("SCAN", f"{body_label}{landable_marker}", severity="INFO", copy_text=body_label)

                    # Check for biological signals and update the system total
                    if d.get("bio_signals_count", 0):
                        self._set_body_signals(body_id, d.get("bio_signals_count", 0), self.body_signals.get(body_id, {}).get("geo", 0))

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
                        self.add_event_feed_entry("VALUABLE", f"{icon} Valuable world: {body_name_str}", severity="WARN", copy_text=body_name_str)
                    if is_system_star_scan and d.get("was_discovered") is False:
                        self.add_event_feed_entry("ALERT", "Undiscovered system star scanned", severity="WARN", copy_text=self.current_sys)
                else:
                    # Later detailed/nav-beacon scans can add fields missing from an initial basic scan.
                    self.last_scan_event = data
                    self.add_scan_item(raw)
                    self._queue_edsm_upload(raw, startup_replay=startup_replay)

                    p_class = d.get("planet_class", "")
                    terraformable = d.get("terraform_state") == "Terraformable"
                    if p_class in ["Earthlike body", "Water world", "Ammonia world"] or terraformable:
                        body_name_str = body_name or "Unknown"
                        already_tracked = any(body_name_str in body for body in self.valuable_bodies)
                        if not already_tracked:
                            self.valuable_system = True
                            icon = "✨"
                            if p_class == "Earthlike body": icon = "🌍"
                            elif p_class == "Water world": icon = "💧"
                            elif p_class == "Ammonia world": icon = "☣️"
                            elif terraformable: icon = "🛠️"
                            self.valuable_bodies.append(f"- {icon} {body_name_str}")
                            self.add_event_feed_entry("VALUABLE", f"{icon} Valuable world: {body_name_str}", severity="WARN", copy_text=body_name_str)

                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
                        self._refresh_system_info_progress()

        # ── Colonization ──────────────────────────────────────────────────────────
        if ev == "ColonisationConstructionDepot":
            mid = d.get("market_id")
            if mid is not None:
                self.current_colonisation_market = mid
                # Preserve existing notes when refreshing from depot event
                _existing = self.colonisation_projects.get(mid, {})
                was_complete = bool(_existing.get("complete"))
                self.colonisation_projects[mid] = {
                    "market_id":    mid,
                    "system_name":  d.get("system_name", ""),
                    "body_name":    d.get("body_name", ""),
                    "progress":     d.get("progress", 0.0),
                    "complete":     d.get("complete", False),
                    "failed":       d.get("failed", False),
                    "resources":    d.get("resources", []),
                    "last_updated": time.time(),
                    "notes":        _existing.get("notes", ""),
                }
                self.db_save_colonisation_project(self.colonisation_projects[mid])
                if not self.batch_mode:
                    self._save_colonisation_data(self.colonisation_projects)
                    if self.colonization_window and self.colonization_window.is_open():
                        self.colonization_window.refresh()
                    self._refresh_colonisation_planner_window()
                    if self.colony_overlay:
                        self.colony_overlay.update()
                    if not was_complete and self.colonisation_projects[mid]["complete"] and self.toast_hud:
                        site = d.get("body_name") or d.get("system_name") or "construction site"
                        self.toast_hud.push("CONSTRUCTION COMPLETE", site, severity="success", duration_s=15)

        elif ev == "ColonisationContribution":
            mid = d.get("market_id")
            if mid in self.colonisation_projects:
                proj = self.colonisation_projects[mid]
                proj["progress"] = d.get("progress", proj.get("progress", 0))
                proj["last_updated"] = time.time()
                contribs = {c["name"].lower(): c["count"] for c in (d.get("contributions") or [])}
                for r in proj.get("resources", []):
                    delta = contribs.get(r["name"].lower(), 0)
                    if delta:
                        r["provided"] = min(r["required"], r.get("provided", 0) + delta)
                self.db_save_colonisation_project(proj)
                if not self.batch_mode:
                    self._save_colonisation_data(self.colonisation_projects)
                    if self.colonization_window and self.colonization_window.is_open():
                        self.colonization_window.refresh()
                    self._refresh_colonisation_planner_window()
                    if self.colony_overlay:
                        self.colony_overlay.update()

        # ── ApproachBody / LeaveBody ──────────────────────────────────────────────
        if ev == "ApproachBody" and not self.batch_mode:
            self.current_body_id   = self._normalize_body_id(d.get("body_id"))
            self.current_body_name = d.get("body_name") or ""
            self._refresh_gravity_warning(self.current_body_id, self.current_body_name)
        elif ev == "LeaveBody" and not self.batch_mode:
            self._check_stale_bio_scans(self.current_body_id)
            self.current_body_id   = None
            self.current_body_name = ""
            if self.gravity_warning_hud:
                self.gravity_warning_hud.clear()

        # ── Prospector overlay — live events only, skip journal replay on startup ──
        # Use startup_replay (not batch_mode) so rapid-fire limpets that land in
        # the same poll cycle still update the overlay.  batch_mode is True for
        # any multi-event poll, not just startup, which was silently dropping updates.
        if self.prospector_hud and not startup_replay:
            if ev == "ProspectedAsteroid":
                self.root.after(0, lambda r=raw: self.prospector_hud.update(r))
            elif ev == "MiningRefined":
                mat = raw.get("Type_Localised") or raw.get("Type") or ""
                self.root.after(0, lambda m=mat: self.prospector_hud.add_refined(m))

    # ── Engineer material helpers ─────────────────────────────────────────────

    def _sync_materials_full(self, raw_list: list, mfg_list: list, enc_list: list):
        """Rebuild engineer_materials from a Materials journal event (complete snapshot)."""
        mats = self.engineer_materials
        for cat_key, items in [("raw", raw_list), ("manufactured", mfg_list), ("encoded", enc_list)]:
            mats[cat_key] = {}
            for item in items:
                key   = (item.get("Name") or "").lower()
                name  = item.get("Name_Localised") or item.get("Name") or key.title()
                count = int(item.get("Count") or 0)
                if key:
                    mats[cat_key][key] = {"name": name, "count": count}
        mats["last_updated"] = time.time()
        self._save_engineer_materials(mats)
        if self.engineer_window and self.engineer_window.is_open():
            self.engineer_window.refresh()

    def _adjust_material(self, cat: str, key: str, name: str, delta: int):
        """Adjust a single material count by delta, persist, and refresh the window."""
        if not key or not cat:
            return
        cat_data = self.engineer_materials.setdefault(cat, {})
        entry = cat_data.get(key)
        if entry:
            entry["count"] = max(0, int(entry.get("count", 0)) + delta)
        elif delta > 0:
            cat_data[key] = {"name": name or key.title(), "count": delta}
        self.engineer_materials["last_updated"] = time.time()
        self._save_engineer_materials(self.engineer_materials)
        if self.engineer_window and self.engineer_window.is_open():
            self.engineer_window.refresh()

    def _process_material_change(self, ev: str, raw: dict):
        """Apply live material collection/consumption events to engineer_materials."""
        def _cat(s: str) -> str:
            s = s.lower()
            if s.startswith("enc"):
                return "encoded"
            if s.startswith("man"):
                return "manufactured"
            return "raw"

        if ev == "MaterialCollected":
            self._adjust_material(
                _cat(raw.get("Category") or "raw"),
                (raw.get("Name") or "").lower(),
                raw.get("Name_Localised") or raw.get("Name") or "",
                int(raw.get("Count") or 1),
            )

        elif ev == "MaterialDiscarded":
            self._adjust_material(
                _cat(raw.get("Category") or "raw"),
                (raw.get("Name") or "").lower(),
                raw.get("Name_Localised") or raw.get("Name") or "",
                -int(raw.get("Count") or 1),
            )

        elif ev == "MaterialTrade":
            paid = raw.get("Paid") or {}
            recv = raw.get("Received") or {}
            self._adjust_material(
                _cat(paid.get("Category") or "raw"),
                (paid.get("Material") or "").lower(),
                paid.get("Material_Localised") or paid.get("Material") or "",
                -int(paid.get("Quantity") or 0),
            )
            self._adjust_material(
                _cat(recv.get("Category") or "raw"),
                (recv.get("Material") or "").lower(),
                recv.get("Material_Localised") or recv.get("Material") or "",
                int(recv.get("Quantity") or 0),
            )

        elif ev in ("EngineerCraft", "Synthesis"):
            ingredients = raw.get("Ingredients") or raw.get("Materials") or []
            for ing in ingredients:
                key = (ing.get("Name") or "").lower()
                self._adjust_material(
                    get_material_category(key),
                    key,
                    ing.get("Name_Localised") or ing.get("Name") or "",
                    -int(ing.get("Count") or 0),
                )

        elif ev == "TechnologyBroker":
            for mat in (raw.get("Materials") or []):
                key = (mat.get("Name") or "").lower()
                self._adjust_material(
                    _cat(mat.get("Category") or get_material_category(key)),
                    key,
                    mat.get("Name_Localised") or mat.get("Name") or "",
                    -int(mat.get("Quantity") or mat.get("Count") or 0),
                )

    def process_batch(self, events):
        self.batch_mode = True
        try:
            with self.db_lock:
                # Let Python's sqlite3 implicit transaction management handle
                # BEGIN automatically — explicit BEGIN here conflicts with any
                # implicit transaction already open (e.g. from the startup seed).
                for ev in events:
                    try:
                        self.process_event(ev)
                    except Exception as e:
                        ev_type = ev.get("type") if isinstance(ev, dict) else "UNKNOWN"
                        logging.warning(f"Batch event failed [{ev_type}]: {e}")
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

        if self.is_first_load:
            self.is_first_load = False
            # After startup batch: re-read DB so scan_stat always reflects the
            # committed authoritative values (fixes cases where in-memory state
            # diverged during batch processing).
            sys_snap = self.current_sys
            def _startup_sync():
                if sys_snap and sys_snap != "---":
                    self.load_system_from_db(sys_snap)
                self.update_dashboard_ui()
                self._show_system_info_for_current_system()
                if self.current_sys and self.current_sys != "---":
                    self.last_traffic_system = self.current_sys
                    self.fetch_system_traffic(self.current_sys)
            self.root.after(0, _startup_sync)
            self.root.after(0, self.update_hud)
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
        else:
            self.root.after(0, self.update_dashboard_ui)
            self.root.after(0, self.update_hud)
        self._refresh_commander_profile_window()
        self._refresh_value_ledger_window()
        self._refresh_colonisation_planner_window()
        self._refresh_exploration_window()
        self._refresh_bgs_window()

    def update_cargo(self, inventory):
        self.last_cargo_event_ts = time.time()
        self.current_cargo_inventory = list(inventory or [])
        self.current_cargo_tons = sum(
            int(item.get("Count", item.get("count", 0)) or 0)
            for item in self.current_cargo_inventory
            if isinstance(item, dict)
        )
        if self.mining_window and self.mining_window.is_open():
            self.mining_window.update_cargo(self.current_cargo_inventory, self.cargo_capacity)
        if self.cargo_hud:
            inv = list(self.current_cargo_inventory)
            cap = self.cargo_capacity
            self.root.after(0, lambda: self.cargo_hud.update(inv, cap))
        if self.colony_overlay:
            self.root.after(0, self.colony_overlay.update)
        self._refresh_commander_profile_window()

    def _record_trade_session_event(self, ev, data):
        if not isinstance(data, dict):
            return
        commodity = data.get("Type_Localised") or data.get("Type") or data.get("commodity") or "Commodity"
        count = int(data.get("Count") or data.get("count") or 0)
        if count <= 0:
            return
        if ev == "MarketBuy":
            price = int(data.get("BuyPrice") or data.get("Price") or 0)
            total = int(data.get("TotalCost") or (price * count))
            self.trade_session["bought_units"] += count
            self.trade_session["spent"] += total
            event = {
                "time": time.time(),
                "event": "BUY",
                "commodity": commodity,
                "count": count,
                "price": price,
                "profit": -total,
            }
        else:
            price = int(data.get("SellPrice") or data.get("Price") or 0)
            total = int(data.get("TotalSale") or (price * count))
            avg_paid = int(data.get("AvgPricePaid") or 0)
            profit = (price - avg_paid) * count if avg_paid else total
            self.trade_session["sold_units"] += count
            self.trade_session["earned"] += total
            self.trade_session["profit"] += profit
            event = {
                "time": time.time(),
                "event": "SELL",
                "commodity": commodity,
                "count": count,
                "price": price,
                "profit": profit,
            }
            big_trade_threshold = int(self.config.get("big_trade_profit_threshold", 1_000_000) or 1_000_000)
            if profit >= big_trade_threshold and self.toast_hud:
                self.toast_hud.push(
                    "BIG TRADE",
                    f"{commodity} x{count}  +{profit:,} CR",
                    severity="success",
                    duration_s=12,
                )
        self.trade_session["events"].append(event)
        ts = trade_marketdb.parse_update_time(data.get("timestamp")) or int(time.time())
        symbol = trade_marketdb.clean_commodity_symbol(data.get("Type") or commodity)
        log_event = "buy" if ev == "MarketBuy" else "sell"
        profit = event["profit"] if ev == "MarketSell" else None

        def worker():
            try:
                trade_marketdb.log_trade(ts, log_event, symbol, commodity, count, price, total, profit)
            except Exception:
                pass

        threading.Thread(target=worker, name="trade-log", daemon=True).start()
        if self.trade_window and self.trade_window.is_open():
            self.root.after(0, self.trade_window.refresh_session)
            self.root.after(0, self.trade_window.refresh_analytics)

    def _market_import_context(self, data):
        return {
            "system_name": data.get("StarSystem") or self.current_sys,
            "system_address": self.current_system_address,
            "star_pos": self.current_coords,
            "station_name": data.get("StationName") or self.current_station_name,
            "station_type": self.current_station_type,
            "gameversion": self.game_version or "",
            "gamebuild": self.game_build or "",
            "horizons": self.game_horizons,
            "odyssey": self.game_odyssey,
            "docked": bool(self.current_docked),
        }

    def _start_market_import_worker(self):
        if self._market_import_thread and self._market_import_thread.is_alive():
            return
        self._market_import_stop.clear()
        self._market_import_thread = threading.Thread(
            target=self._market_import_worker,
            name="trade-market-import",
            daemon=True,
        )
        self._market_import_thread.start()

    def _stop_market_import_worker(self):
        try:
            self._market_import_stop.set()
            self._market_import_queue.put_nowait(None)
        except Exception:
            pass

    def _enqueue_market_import(self, snapshot):
        try:
            self._market_import_queue.put_nowait(snapshot)
            return
        except queue.Full:
            pass
        try:
            self._market_import_queue.get_nowait()
        except Exception:
            pass
        try:
            self._market_import_queue.put_nowait(snapshot)
        except Exception:
            pass

    def _market_import_worker(self):
        while not self._market_import_stop.is_set():
            try:
                item = self._market_import_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                continue
            data, context = item
            try:
                conn = trade_marketdb.connect()
                try:
                    result = trade_marketdb.import_market_json(conn, data, context)
                finally:
                    conn.close()
            except Exception as exc:
                self.root.after(0, lambda e=exc: self.log(f"Trade market import failed: {e}"))
                continue

            if context.get("docked"):
                trade_eddn_uploader.set_enabled(bool(self.config.get("trade_eddn_upload_enabled", True)))
                trade_eddn_uploader.maybe_publish(data, self.cmdr_name, context)

            if not result.get("updated"):
                continue
            self.root.after(0, lambda d=data, c=context, r=result: self._apply_market_import_result(d, c, r))

    def _apply_market_import_result(self, data, context, result):
        self.current_trade_market = {
            "market_id": result.get("market_id"),
            "station": result.get("station") or context.get("station_name"),
            "system": result.get("system") or context.get("system_name"),
            "timestamp": data.get("timestamp"),
            "items": list(data.get("Items") or []),
        }
        station = result.get("station") or context.get("station_name") or "market"
        system = result.get("system") or context.get("system_name") or self.current_sys
        count = result.get("commodities", 0)
        self.add_event_feed_entry(
            "TRADE",
            f"Market updated: {station} ({count} commodities)",
            severity="INFO",
            copy_text=system,
        )
        if self.trade_window and self.trade_window.is_open():
            self.trade_window.refresh_status()
            self.trade_window.refresh_local()

    def update_market(self, data):
        if not isinstance(data, dict):
            return
        context = self._market_import_context(data)
        self.current_trade_market = {
            "market_id": data.get("MarketID"),
            "station": data.get("StationName") or context.get("station_name"),
            "system": data.get("StarSystem") or context.get("system_name"),
            "timestamp": data.get("timestamp"),
            "items": list(data.get("Items") or []),
        }
        if self.trade_window and self.trade_window.is_open():
            self.root.after(0, self.trade_window.refresh_local)
        self._enqueue_market_import((dict(data), dict(context)))

    def update_nav_route(self, data):
        self.last_nav_event_ts = time.time()
        self.nav_route_entries = list(data.get('Route', []) or [])
        self.route_list = [r['StarSystem'] for r in self.nav_route_entries if r.get('StarSystem')]
        if self.route_list:
            dest = self.nav_route_entries[-1]
            self.dest_coords = dest.get('StarPos')
            self.dest_name = dest.get('StarSystem')
            dest_url_name = (self.dest_name or "").replace(" ", "+")
            self.add_event_feed_entry("SYSTEM", f"Nav route loaded: {len(self.route_list)} jumps to {self.dest_name}", severity="INFO", copy_text=self.dest_name, url=f"https://www.edsm.net/show-system?systemName={dest_url_name}")
            self.update_nav_label()
            self.schedule_dashboard_refresh()
            self.update_hud()
            self._refresh_commander_profile_window()
            self._refresh_exploration_window()
        else:
            self.nav_route_entries = []
            self.dest_coords = None
            self.dest_name = None
            self.add_event_feed_entry("SYSTEM", "Nav route cleared", severity="INFO")
            self.update_nav_label()
            self.schedule_dashboard_refresh()
            self.update_hud()
            self._refresh_commander_profile_window()
            self._refresh_exploration_window()
