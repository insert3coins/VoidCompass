import os
import json
import threading
import math
import sqlite3
import logging
import time
import tkinter as tk
from tkinter import messagebox
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
import themes
from ui_theme import apply_theme_live
from version import APP_VERSION
import bio_values
from hud import TacticalHUD
from cargo_hud import CargoHUD
from carrier_hud import CarrierHUD
from edsm_handler import EDSMHandler
from screenshot_handler import ScreenshotHandler
from settings_ui import open_settings
from waypoint_manager import WaypointManager
import route_strip
from journal_watcher import JournalWatcher
from mining_window import MINING_MATERIALS
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
from overlay_input import set_mouse_passthrough
from runtime_trace import RuntimeTrace
from dashboard_db_mixin import DashboardDBMixin
from dashboard_ui_mixin import DashboardUIMixin
from dashboard_scan_mixin import DashboardScanMixin
from colonization_window import ColonizationWindow, save_colonisation_data, load_colonisation_data
from engineer_window import (
    EngineerWindow, load_engineer_materials, save_engineer_materials,
    get_material_category,
)
from engineering_data import ready_blueprints
import companion_features
import compass_operations
from credit_events import authoritative_balance, credit_delta
from bgs_window import BGSWindow
from commander_profile_window import CommanderProfileWindow
from system_value_ledger import SystemValueLedger
from stellar_types import star_type_label
from colonisation_planner import ColonisationPlanner
from exploration_window import ExplorationWindow
from trade_window import TradeWindow
from analytics_window import AnalyticsWindow
from trade import marketdb as trade_marketdb
from trade import alerts as trade_alerts
from trade.eddn_upload import UPLOADER as trade_eddn_uploader
from achievement_engine import AchievementEngine
from achievement_window import AchievementWindow
from voice_callouts import VoiceCalloutManager, choose_line
from cockpit_ai_memory import CockpitMemory, ordinal
from cockpit_ai_brain import CockpitBrain
from compass_cognition import CompassCognition
from combat_awareness import CombatAwareness
from specialist_engine import SpecialistEngine
from specialists_window import SpecialistsWindow
import compass_personas
from captains_log import CaptainsLog
from deep_survey import DeepSurveyTracker
from exploration_intelligence import build_intelligence, checkpoint_payload
from expedition_manager import ExpeditionManager
from diagnostic_logs import application_base_dir, resolve_log_path
from adaptive_command import AdaptiveCommandDeck, AUTOMATIC_MODE_IDLE_S, MODE_LABELS
from diagnostic_bundle import create_support_bundle
from onboarding import should_show as should_show_onboarding, show_first_run
from persistence_queue import flush_persistence, persistence_queue
from session_recovery import ProfileSessionGuard
from ui_dispatcher import TkDispatcher
from global_hotkeys import GlobalHotkeyManager, OVERLAY_HOTKEY_SPECS


class MainDashboard(DashboardScanMixin, DashboardUIMixin, DashboardDBMixin):
    _COCKPIT_STATE_FILE = "last_cockpit_state.json"
    _COCKPIT_STATE_SCHEMA = 1
    _COCKPIT_STATE_FIELDS = (
        "current_sys", "previous_sys", "previous_coords",
        "current_system_address", "current_coords", "star_class",
        "scanned", "total", "navigation_scan_progress",
        "navigation_scan_progress_source", "organic_count", "system_bio_signals",
        "system_traffic", "last_traffic_system", "valuable_system",
        "valuable_bodies", "body_signals", "system_undiscovered",
        "fss_all_bodies", "current_body_id", "current_body_name",
        "last_bio_scan", "bio_sampling", "bio_sample_points",
        "cmdr_balance", "cmdr_loan", "cmdr_ranks", "cmdr_rank_progress",
        "cmdr_reputation", "cmdr_ship", "game_version", "game_build",
        "game_horizons", "game_odyssey", "current_station_name",
        "current_station_type", "current_station_market_id",
        "current_station_economy", "current_station_economies",
        "current_station_government", "current_station_faction",
        "current_station_allegiance", "current_station_services",
        "current_station_dist_ls", "current_station_landing_pads",
        "current_docked", "hud_flight_state", "current_landed",
        "current_in_fighter", "current_in_srv", "current_on_foot",
        "current_vehicle_id", "current_vehicle_name", "current_legal_state",
        "current_fuel_main", "current_fuel_reservoir", "fuel_capacity_main",
        "current_destination", "cargo_capacity", "current_cargo_tons",
        "current_cargo_inventory", "dest_coords", "dest_name", "route_list",
        "nav_route_entries", "current_latitude", "current_longitude",
        "current_heading", "current_planet_radius", "on_planet",
    )
    _COCKPIT_STATE_LIMITS = {
        "valuable_bodies": 64,
        "current_station_economies": 16,
        "current_station_services": 128,
        "current_cargo_inventory": 256,
        "route_list": 256,
        "nav_route_entries": 256,
        "bio_sample_points": 8,
    }
    _OVERLAY_POSITION_SPECS = (
        ("hud", "hud_x", "hud_y"),
        ("cargo_hud", "cargo_hud_x", "cargo_hud_y"),
        ("carrier_hud", "carrier_hud_x", "carrier_hud_y"),
        ("prospector_hud", "prospector_hud_x", "prospector_hud_y"),
        ("system_info_hud", "system_info_hud_x", "system_info_hud_y"),
        ("gravity_warning_hud", "gravity_warning_hud_x", "gravity_warning_hud_y"),
        ("station_info_hud", "station_info_hud_x", "station_info_hud_y"),
        ("survey_status_hud", "survey_status_hud_x", "survey_status_hud_y"),
        ("toast_hud", "toast_hud_x", "toast_hud_y"),
        ("heartbeat_hud", "heartbeat_hud_x", "heartbeat_hud_y"),
        ("colony_overlay", "colony_overlay_x", "colony_overlay_y"),
    )

    _COCKPIT_BRAIN_MILESTONES = {
        "systems": (10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
        "species": (10, 25, 50, 100, 250, 500, 1000, 2000),
        "memories": (10, 25, 50, 80, 100, 250, 500, 1000),
    }

    def _cockpit_memory_limits(self):
        return {
            "systems": self.config.get("cockpit_memory_system_limit", 300),
            "species": self.config.get("cockpit_memory_species_limit", 200),
            "ships": self.config.get("cockpit_memory_ship_limit", 30),
            "memories": self.config.get("cockpit_memory_episode_limit", 80),
        }

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

    def _enrich_bio_event_context(self, data):
        """Add the richer Survey Status context missing from ScanOrganic journals."""
        if not isinstance(data, dict):
            return data
        body_id = self._normalize_body_id(data.get("body_id"))
        scan_item = self.scan_items_by_id.get(body_id, {}) if body_id is not None else {}
        scan_data = self.body_scan_data.get(body_id, {}) if body_id is not None else {}
        body_name = data.get("body_name") or scan_item.get("name") or scan_data.get("body_name")
        if body_name:
            data["body_name"] = body_name
        genus = data.get("genus") or data.get("species")
        if data.get("species"):
            value = bio_values.species_value(data["species"])
            if value is not None:
                data["species_value"] = value
        if genus:
            genus_info = bio_values.genus_info(genus)
            if genus_info.get("min_value") is not None:
                data["genus_min_value"] = genus_info["min_value"]
            if genus_info.get("max_value") is not None:
                data["genus_max_value"] = genus_info["max_value"]
            if genus_info.get("colony_m") is not None:
                data["colony_m"] = genus_info["colony_m"]
        return data

    def _profile_path(self, filename):
        return get_profile_file(get_active_profile(self.config), filename)

    @classmethod
    def _cockpit_state_json_value(cls, value):
        """Return a bounded JSON-safe copy of simple runtime state."""
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, dict):
            return {
                str(key): cls._cockpit_state_json_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, deque)):
            return [cls._cockpit_state_json_value(item) for item in value]
        if isinstance(value, set):
            return [cls._cockpit_state_json_value(item) for item in sorted(value, key=str)]
        return None

    def _save_profile_cockpit_state(self):
        """Persist the active commander's last visible state on clean shutdown."""
        if getattr(self, "_startup_restore_active", False):
            # Never replace a known-good snapshot with a partially replayed
            # journal if the app is closed while recovery is still running.
            return False
        profile_key = get_active_profile(self.config)
        state = {}
        for field in self._COCKPIT_STATE_FIELDS:
            value = getattr(self, field, None)
            limit = self._COCKPIT_STATE_LIMITS.get(field)
            if limit is not None and isinstance(value, (list, tuple, deque)):
                value = list(value)[:limit]
            state[field] = self._cockpit_state_json_value(value)
        payload = {
            "schema": self._COCKPIT_STATE_SCHEMA,
            "saved_at": time.time(),
            "profile_key": profile_key,
            "commander": getattr(self, "cmdr_name", None),
            "fid": getattr(self, "cmdr_fid", None),
            "state": state,
        }
        path = self._profile_path(self._COCKPIT_STATE_FILE)
        temp_path = f"{path}.tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            os.replace(temp_path, path)
            return True
        except Exception as exc:
            logging.warning("Could not save profile cockpit state: %s", exc)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            return False

    @staticmethod
    def _restore_int_key_dict(value):
        if not isinstance(value, dict):
            return {}
        restored = {}
        for key, item in value.items():
            try:
                key = int(key)
            except (TypeError, ValueError):
                pass
            restored[key] = item
        return restored

    def _load_profile_cockpit_state(self):
        """Load only the active commander's graceful-shutdown snapshot."""
        path = self._profile_path(self._COCKPIT_STATE_FILE)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            return False
        if not isinstance(payload, dict):
            return False
        if payload.get("schema") != self._COCKPIT_STATE_SCHEMA:
            return False
        if payload.get("profile_key") != get_active_profile(self.config):
            return False
        saved_fid = str(payload.get("fid") or "")
        active_fid = str(self.config.get("active_commander_fid") or "")
        if saved_fid and active_fid and saved_fid != active_fid:
            return False
        state = payload.get("state")
        if not isinstance(state, dict):
            return False
        for field in self._COCKPIT_STATE_FIELDS:
            if field in state:
                setattr(self, field, state[field])
        self.body_signals = self._restore_int_key_dict(self.body_signals)
        if not isinstance(self.current_coords, list) or len(self.current_coords) != 3:
            self.current_coords = [0, 0, 0]
        if self.previous_coords is not None and (
                not isinstance(self.previous_coords, list) or len(self.previous_coords) != 3):
            self.previous_coords = None
        if self.dest_coords is not None and (
                not isinstance(self.dest_coords, list) or len(self.dest_coords) != 3):
            self.dest_coords = None
        try:
            self._cached_cockpit_state_saved_at = float(payload.get("saved_at") or 0.0)
        except (TypeError, ValueError):
            self._cached_cockpit_state_saved_at = 0.0
        return bool(self.current_sys and self.current_sys != "---")

    def _hydrate_cached_system_scan_state(self):
        """Use the profile DB for body detail while the journal catches up."""
        if not getattr(self, "_cached_cockpit_state_loaded", False):
            return
        if not self.current_sys or self.current_sys in ("---", "Unknown"):
            return
        self.load_system_from_db(self.current_sys)
        items = self.load_scan_items_from_db(self.current_sys)
        if items:
            self.scan_items = list(items)
            self.scan_items_by_id = {}
            for item in self.scan_items:
                self._normalize_scan_item(item)
                body_id = item.get("body_id")
                if body_id is not None:
                    self.scan_items_by_id[body_id] = item
            self._rebuild_system_state_from_scan_items()

    def _show_cached_cockpit_state(self):
        """Paint the last state once, then freeze redraws during catch-up."""
        if not getattr(self, "_cached_cockpit_state_loaded", False):
            return
        self.update_dashboard_ui()
        self._perform_hud_update()
        self._show_system_info_for_current_system()
        if self.survey_status_hud:
            self.survey_status_hud.update(
                self.current_sys, self.scanned, self.total, self.scan_items,
                self.body_signals, sampling=self._sampling_snapshot(),
                focused_body_id=self.current_body_id,
                focused_body_name=self.current_body_name,
            )
        if self.station_info_hud and self.current_docked and self.current_station_name:
            self.station_info_hud.on_docked(self)
        if self.cargo_hud:
            self.cargo_hud.update(self.current_cargo_inventory, self.cargo_capacity)
        self._refresh_gravity_warning(self.current_body_id, self.current_body_name)
        self.update_ground_target_ui()
        self.root.title(f"VOID COMPASS // v{APP_VERSION} // RESTORING JOURNAL")
        self._startup_restore_active = True
        self._startup_restore_ui_pending = False

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
        self.config["companion_state_file"] = self._copy_legacy_to_profile("companion_state.json")
        self.config["mining_db_file"] = self._copy_legacy_to_profile("mining_data.db")
        self.config["mining_sessions_file"] = self._copy_legacy_to_profile("mining_sessions.json")
        self.config["waypoints_file"] = self._copy_legacy_to_profile("waypoints.json")
        self.config["specialists_file"] = self._profile_path("specialists.json")
        self.config["adaptive_command_file"] = self._profile_path("adaptive_command.json")
        self.config["deep_survey_file"] = self._profile_path("deep_survey.json")
        self.config["expeditions_file"] = self._profile_path("expeditions.json")

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

    def _apply_active_profile_theme(self):
        """Apply the selected commander's theme to the running UI and HUDs."""
        custom_themes = self.config.get("ui_custom_themes")
        if not isinstance(custom_themes, dict):
            custom_themes = {}
            self.config["ui_custom_themes"] = custom_themes
        theme_name, palette = themes.resolve_theme(
            self.config.get("ui_theme_name"),
            custom_themes,
        )
        # Keep the runtime config canonical if a deleted or invalid custom
        # theme has fallen back to the built-in default.
        self.config["ui_theme_name"] = theme_name
        try:
            apply_theme_live(self.root, theme_name, palette)
            survey = getattr(self, "survey_status_hud", None)
            apply_survey_theme = getattr(survey, "apply_theme", None)
            if callable(apply_survey_theme):
                apply_survey_theme(palette)
            return True
        except Exception as exc:
            logging.warning("Could not apply profile theme %s: %s", theme_name, exc)
            return False

    @staticmethod
    def _new_trade_session():
        return {
            "bought_units": 0,
            "sold_units": 0,
            "spent": 0,
            "earned": 0,
            "profit": 0,
            "transactions": 0,
            "commodities_bought": {},
            "commodities_sold": {},
            "best_sale": None,
            "worst_sale": None,
            "events": deque(maxlen=100),
        }

    def _close_profile_surfaces(self):
        """Close every UI surface holding references to the outgoing profile."""
        try:
            self._capture_overlay_positions()
        except Exception:
            pass

        close_methods = {
            "carrier_window": "_on_close",
            "colonization_window": "_on_close",
            "engineer_window": "_on_close",
            "bgs_window": "_on_close",
            "commander_profile_window": "_on_close",
            "value_ledger_window": "_on_close",
            "colonisation_planner_window": "_on_close",
            "exploration_window": "_on_close",
            "trade_window": "_on_close",
            "analytics_window": "_on_close",
            "achievement_window": "_on_close",
            "specialists_window": "_on_close",
        }
        for attr, close_name in close_methods.items():
            surface = getattr(self, attr, None)
            try:
                if surface and surface.is_open():
                    getattr(surface, close_name)()
            except Exception:
                try:
                    win = getattr(surface, "win", None)
                    if win and win.winfo_exists():
                        win.destroy()
                except Exception:
                    pass
            setattr(self, attr, None)

        plotter = getattr(self, "route_plotter", None)
        try:
            if plotter and plotter.win.winfo_exists():
                plotter.on_close()
        except Exception:
            pass
        self.route_plotter = None

        settings_page = getattr(self, "settings_page", None)
        try:
            if settings_page is not None and settings_page.winfo_exists():
                settings_page.destroy()
        except Exception:
            pass
        self.settings_page = None

        ground_window = getattr(self, "ground_target_window", None)
        try:
            if ground_window and ground_window.winfo_exists():
                self.config["ground_target_window_geometry"] = ground_window.geometry()
                ground_window.destroy()
        except Exception:
            pass
        self.ground_target_window = None
        try:
            self._destroy_ground_popup()
        except Exception:
            pass

        for attr in (
            "hud", "cargo_hud", "carrier_hud", "prospector_hud",
            "system_info_hud", "gravity_warning_hud", "station_info_hud",
            "survey_status_hud", "toast_hud", "heartbeat_hud", "colony_overlay",
        ):
            overlay = getattr(self, attr, None)
            try:
                if overlay is not None and hasattr(overlay, "destroy"):
                    overlay.destroy()
                else:
                    win = getattr(overlay, "win", None)
                    if win and win.winfo_exists():
                        win.destroy()
            except Exception:
                pass
            setattr(self, attr, None)

    def _reset_profile_runtime_state(self, commander_name, fid=None):
        """Clear transient flight state so no commander can inherit another's session."""
        hud_job = getattr(self, "_hud_refresh_job", None)
        if hud_job is not None:
            try:
                self.root.after_cancel(hud_job)
            except Exception:
                pass
        self._hud_refresh_job = None
        self._hud_refresh_requested = False
        self._last_hud_refresh_ts = 0.0
        self.current_sys = "---"
        self.previous_sys = None
        self.previous_coords = None
        self.current_system_address = None
        self.current_coords = [0, 0, 0]
        self.star_class = ""
        self.scanned = 0
        self.total = 0
        self.navigation_scan_progress = None
        self.navigation_scan_progress_source = "bodies"
        self.organic_count = 0
        self.system_bio_signals = 0
        self.system_traffic = {"day": 0, "week": 0, "total": 0}
        self.last_traffic_system = None
        self._system_traffic_resolved = False
        self._pending_system_discovery = None
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
        self.system_stars = {}
        self.body_scan_data = {}
        self.current_body_id = None
        self.current_body_name = ""
        self.last_scan_event = None
        self.last_bio_scan = {}
        self.bio_sampling = None
        self.bio_sample_points = []
        self._sample_clear_announced = False
        self._stale_bio_warned = set()

        self.cmdr_name = commander_name or "CMDR"
        self.cmdr_fid = fid or ""
        self.cmdr_balance = None
        self.cmdr_loan = None
        self.cmdr_ranks = {}
        self.cmdr_rank_progress = {}
        self.cmdr_reputation = {}
        self.cmdr_ship = {}
        self.game_version = ""
        self.game_build = ""
        self.game_horizons = None
        self.game_odyssey = None

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
        self.current_colonisation_market = None
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
        self._fuel_used_samples = deque(maxlen=8)
        self._fuel_advisory_signature = None
        self._low_fuel_warned = False
        self._toast_hull_thresholds_seen = set()
        self._toast_status_alerts = set()
        self._toast_legal_state = None
        self._toast_shields_up = None
        self.current_legal_state = None
        self.current_destination = None

        self.cargo_capacity = 0
        self.current_cargo_tons = 0
        self.current_cargo_inventory = []
        self.trade_jump_history = deque(maxlen=20)
        self.trade_session = self._new_trade_session()
        self.trade_plan_context = None
        self.mining_ai_session = self._new_mining_ai_session()
        self.ai_operational_state = compass_operations.fresh_runtime_state()
        self.colonisation_projects = {}
        self.engineer_materials = {}
        self.companion_state = companion_features.fresh_state()
        if getattr(self, "combat_awareness", None):
            self.combat_awareness.reset()
        else:
            self.combat_awareness = CombatAwareness()

        self.dest_coords = None
        self.dest_name = None
        self.route_list = []
        self.nav_route_entries = []
        self.target_waypoint = None
        self.waypoint_cache = {}
        self.session_start_ts = time.time()
        self.session_jump_count = 0
        self.session_ly = 0.0
        self.session_systems = set()
        self._expedition_resume_brief_key = None

        self.target_lat = self._to_float(self.config.get("ground_target_lat"), 0.0)
        self.target_lon = self._to_float(self.config.get("ground_target_lon"), 0.0)
        self.target_latlon_active = bool(self.config.get("ground_target_active", False))
        self.current_latitude = None
        self.current_longitude = None
        self.current_heading = None
        self.current_planet_radius = None
        self.on_planet = False
        self._ground_last_on_planet = False
        self.ground_popup_enabled = bool(self.config.get("ground_popup_enabled", True))
        self._ground_ui_needs_update = True
        self._ground_last_status_key = None
        self._pending_status_data = None
        self._status_dispatch_scheduled = False

        self._rebuy_warning_level = 0
        self._data_risk_level = 0
        self._compass_advisor_last = {}
        self._compass_advisor_last_any = 0.0
        self._hud_balance_cache = {"ts": 0.0, "balance": None}
        self.last_journal_event_ts = 0.0
        self.last_logged_journal_file = None
        self.last_status_event_ts = 0.0
        self.last_nav_event_ts = 0.0
        self.last_cargo_event_ts = 0.0
        self.last_edsm_event_ts = 0.0
        self.last_edsm_request_ts = 0.0
        self._event_rate_ts = deque(maxlen=1200)

        self.log_entries = []
        self.event_feed_entries = []
        self.event_feed_view = []
        self.journal_history_entries = []
        lock = getattr(self, "_event_feed_pending_lock", None)
        if lock:
            with lock:
                self._event_feed_pending.clear()
                self._journal_history_pending.clear()
        self._event_feed_dirty = True
        self._journal_history_dirty = True

    def _persist_config(self):
        save_config(self.config)

    def _refresh_tool_window(self, attr, method="refresh"):
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        win = getattr(self, attr, None)
        try:
            if win and win.is_open():
                self.root.after(0, getattr(win, method))
        except Exception:
            pass

    def _refresh_commander_profile_window(self):
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        window = getattr(self, "commander_profile_window", None)
        try:
            if not window or not window.is_open():
                return
            if getattr(self, "_active_page", None) == "PROFILE":
                self.root.after(0, window.refresh)
            else:
                window._refresh_pending = True
        except Exception:
            pass

    def _refresh_value_ledger_window(self):
        self._refresh_tool_window("value_ledger_window")

    def _refresh_colonisation_planner_window(self):
        self._refresh_tool_window("colonisation_planner_window")

    def _refresh_exploration_window(self):
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        if getattr(self, "_exploration_refresh_job", None) is not None:
            return
        def _run():
            self._exploration_refresh_job = None
            self._refresh_tool_window("exploration_window")
        try:
            self._exploration_refresh_job = self.root.after(150, _run)
        except Exception:
            self._exploration_refresh_job = None

    def _import_captains_log_history(self, journal_path, logbook=None, commander=None, fid=None):
        logbook = logbook or self.captains_log
        try:
            imported = logbook.import_journals(journal_path, commander=commander, fid=fid)
            if imported and logbook is self.captains_log:
                self.log(f"Captain's Log imported {imported:,} journal highlights and session updates")
                self._refresh_exploration_window()
        except Exception as exc:
            logging.warning("Captain's Log history import skipped: %s", exc)

    def _import_deep_survey_history(self, journal_path, tracker=None, commander=None, fid=None):
        tracker = tracker or self.deep_survey
        try:
            imported = tracker.import_journals(journal_path, commander=commander, fid=fid)
            if imported and tracker is self.deep_survey:
                self.log(f"Deep Survey indexed {imported:,} exploration journal facts")
                self._refresh_exploration_window()
        except Exception as exc:
            logging.warning("Deep Survey history import skipped: %s", exc)

    def _import_exploration_history(self, journal_path, logbook, tracker, commander=None, fid=None):
        """Read history sequentially so two indexers never contend for the journal folder."""
        self._import_captains_log_history(journal_path, logbook, commander, fid)
        self._import_deep_survey_history(journal_path, tracker, commander, fid)

    def _refresh_bgs_window(self):
        self._refresh_tool_window("bgs_window", "refresh_current")

    def _schedule_specialist_flush(self):
        """Coalesce live specialist writes so rapid journal bursts stay cheap."""
        if self.batch_mode or getattr(self, "_specialist_flush_job", None) is not None:
            return

        def flush_later():
            self._specialist_flush_job = None
            engine = getattr(self, "specialist_engine", None)
            if engine:
                threading.Thread(target=engine.flush, daemon=True).start()

        try:
            self._specialist_flush_job = self.root.after(750, flush_later)
        except Exception:
            self._specialist_flush_job = None

    def _refresh_system_info_progress(self):
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        if not getattr(self, "system_info_hud", None) and not getattr(self, "survey_status_hud", None):
            return
        if getattr(self, "_system_info_refresh_job", None) is not None:
            return
        def _run():
            self._system_info_refresh_job = None
            if self.system_info_hud:
                self.system_info_hud.update_scan_progress(
                    self.scan_items, self.body_signals, self.total,
                    star_class=self.star_class,
                )
            if self.survey_status_hud:
                self.survey_status_hud.update(
                    self.current_sys, self.scanned, self.total, self.scan_items,
                    self.body_signals, sampling=self._sampling_snapshot(),
                    focused_body_id=self.current_body_id,
                    focused_body_name=self.current_body_name,
                )
        try:
            self._system_info_refresh_job = self.root.after(150, _run)
        except Exception:
            self._system_info_refresh_job = None

    def _hide_survey_status_for_jump(self):
        """Hide current-system survey data and prevent a queued stale redraw."""
        job = getattr(self, "_system_info_refresh_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._system_info_refresh_job = None
        survey = getattr(self, "survey_status_hud", None)
        if survey:
            survey.hide()

    def _apply_location_navigation_state(self, raw, data):
        """Seed navigation/station state from a Location login event."""
        location = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        station_name = data.get("station_name") or location.get("StationName")
        docked_value = data.get("docked")
        if docked_value is None:
            docked_value = location.get("Docked")
        on_foot_value = data.get("on_foot")
        if on_foot_value is None:
            on_foot_value = location.get("OnFoot")
        if on_foot_value is not None:
            self.current_on_foot = bool(on_foot_value)
        self.current_in_fighter = False
        self.current_in_srv = False
        self.current_vehicle_id = None
        self.current_vehicle_name = ""
        if docked_value is not None or (self.current_on_foot and station_name):
            self.current_docked = bool(docked_value or (self.current_on_foot and station_name))
        if station_name:
            self.current_station_name = station_name
            self.current_station_type = data.get("station_type") or location.get("StationType") or None
            self.current_station_market_id = data.get("market_id") or location.get("MarketID")
            self.current_station_economy = (
                location.get("StationEconomy_Localised") or location.get("StationEconomy")
            )
            self.current_station_economies = location.get("StationEconomies") or []
            faction = location.get("StationFaction") or {}
            self.current_station_government = (
                location.get("StationGovernment_Localised") or location.get("StationGovernment")
            )
            self.current_station_faction = {
                "name": faction.get("Name"), "state": faction.get("FactionState"),
            } if faction.get("Name") else None
            self.current_station_allegiance = location.get("StationAllegiance")
            self.current_station_services = location.get("StationServices") or []
            self.current_station_dist_ls = location.get("DistFromStarLS")
            self.current_station_landing_pads = location.get("LandingPads")
        else:
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
        self._sync_navigation_hud_flight_state(supercruise=False)

    def _start_trade_live_services(self):
        """Start the EDDN listener at app startup (not first Trade-window open,
        which let the market DB silently age) and surface fired trade-watch
        alerts as toasts instead of waiting for the Watchlist tab."""
        def _on_trade_alert(alert):
            toast = getattr(self, "toast_hud", None)
            if toast:
                # Called from the EDDN thread — hop through the shared Tk dispatcher.
                self._ui_post(lambda a=alert: toast.push(
                    "TRADE WATCH", a.get("text") or "", severity="warn", duration_s=15))
        try:
            trade_alerts.set_notify_callback(_on_trade_alert)
        except Exception:
            pass
        def _start_if_ready():
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

        threading.Thread(
            target=_start_if_ready, name="trade-live-startup", daemon=True,
        ).start()

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
        return save_engineer_materials(materials, self.config.get("engineer_materials_file"))

    def _save_companion_state(self):
        companion_features.save_state(self.config.get("companion_state_file"), self.companion_state)

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

        # Close and persist the outgoing commander's session while every live
        # fact and UI position still belongs to that profile.
        self._save_exploration_checkpoint("profile-change", immediate=True)
        if getattr(self, "cockpit_memory", None):
            insights = (
                self.compass_cognition.observe_session_close(
                    self._compass_gameplay_snapshot(), self.cockpit_memory,
                )
                if getattr(self, "compass_cognition", None) else []
            )
            self.cockpit_memory.session_debrief(
                "Profile changed", close=True, insights=insights,
            )
        self._close_profile_surfaces()
        try:
            self.voice_callouts.shutdown()
        except Exception:
            pass
        try:
            self.edsm.prepare_profile_switch()
        except Exception:
            pass
        if getattr(self, "overlay_hotkeys", None):
            self.overlay_hotkeys.stop()
        self._reset_overlay_hotkey_visibility(restore=True)
        self._stop_db_commit_worker(close=True, timeout=0.35)
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
                "specialists.json",
                "adaptive_command.json",
                "deep_survey.json",
                "expeditions.json",
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
        self._reset_profile_runtime_state(commander_name, self.config.get("active_commander_fid"))
        self._apply_active_profile_theme()
        # These long-lived workers retain the same config object today, but
        # rebinding them makes the profile boundary explicit and future-proof.
        self.screenshots.config = self.config
        self.watcher.config = self.config
        self.voice_callouts = VoiceCalloutManager(self.config)
        if getattr(self, "cockpit_memory", None):
            self.cockpit_memory.switch(
                get_profile_file(new_key, "cockpit_ai_memory.json"),
                limits=self._cockpit_memory_limits(),
            )
            if getattr(self, "cockpit_brain", None):
                self.cockpit_brain.switch(
                    get_profile_file(new_key, "cockpit_ai_brain.json")
                )
            self.compass_cognition = CompassCognition(self.cockpit_brain, self.config)
            self.cockpit_memory.begin_app_session()
            self._publish_cockpit_ai_online()
        self.captains_log = CaptainsLog(
            get_profile_file(new_key, "captains_log.json")
        )
        # Use a fresh tracker object: an outgoing profile may still be finishing
        # its background history index, and must never write into the new one.
        self.deep_survey = DeepSurveyTracker(
            get_profile_file(new_key, "deep_survey.json")
        )
        if getattr(self, "expedition_manager", None):
            self.expedition_manager.flush(wait=False)
        self.expedition_manager = ExpeditionManager(
            get_profile_file(new_key, "expeditions.json")
        )
        if getattr(self, "specialist_engine", None):
            self.specialist_engine.switch(self.config.get("specialists_file"))
        if getattr(self, "adaptive_command", None):
            self.adaptive_command.switch(
                self.config.get("adaptive_command_file"), self.config,
            )
            self._adaptive_startup_briefed = False
        if getattr(self, "session_guard", None):
            self.session_guard.switch(self._profile_path("session.active"))
            self._startup_recovery_mode = bool(
                self.session_guard.unclean
                and self.config.get("recovery_safe_mode_enabled", True)
            )
        if getattr(self, "achievement_engine", None):
            self.achievement_engine.switch_profile(
                self._profile_path("achievements_state.json"),
                enabled=self.config.get("achievements_enabled", True),
                disabled_categories=self.config.get("achievements_disabled_categories", []),
            )
        self.init_db()
        self.edsm.switch_profile(self.config, self.conn, self.db_lock)
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
        self.companion_state = companion_features.load_state(self.config.get("companion_state_file"))
        self.waypoint_manager = WaypointManager(self.config.get("waypoints_file"))
        journal_path = self.config.get("journal_path") or getattr(self.watcher, "journal_path", None)
        threading.Thread(
            target=self.carrier_tracker.scan_journal_history,
            args=(journal_path, 10, self.cmdr_name, self.cmdr_fid),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._import_exploration_history,
            args=(journal_path, self.captains_log, self.deep_survey, self.cmdr_name, self.cmdr_fid),
            name="exploration-history", daemon=True,
        ).start()
        self._persist_config()
        self._apply_runtime_feature_toggles()
        self._configure_overlay_hotkeys(announce=False)
        self._apply_navigation_group_state()
        self.show_dashboard_page()
        self.update_dashboard_ui()
        self.update_hud()
        self.update_carrier_panel()
        self.update_ground_target_ui()
        try:
            self.root.after(120, self._reapply_overlay_positions)
        except Exception:
            pass
        if getattr(self, "watcher", None):
            self.watcher.force_check_nav()
            self.watcher.force_check_status()
            self.watcher.force_check_cargo()
            self.watcher.force_check_market()
            self.watcher.force_check_ship_locker()
        self.add_event_feed_entry("PROFILE", f"Switched to commander profile: {commander_name}", severity="INFO")

    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self._prepare_commander_profile_from_journal()
        self._apply_active_profile_theme()
        if should_show_onboarding(self.config):
            self._show_bootstrap_onboarding()
            # The selected journal folder may identify a different commander
            # than the pre-wizard defaults. Establish that profile before any
            # profile-local state, voice worker, overlay or journal watcher.
            self._prepare_commander_profile_from_journal()
            self._apply_active_profile_theme()
            save_config(self.config)
        # This is the only cross-thread gateway into Tk. Background journal,
        # network and file workers enqueue bounded work here; Tk drains it in
        # short slices so flight controls and overlays remain responsive.
        self.ui_dispatcher = TkDispatcher(root)
        self._overlay_hotkey_global_hidden = False
        self._overlay_hotkey_hidden = set()
        self._overlay_hotkey_restore = set()
        self.overlay_hotkeys = GlobalHotkeyManager(
            lambda action: self.ui_dispatcher.post(
                self._handle_overlay_hotkey,
                action,
                key=f"overlay-hotkey:{action}",
            )
        )
        self.voice_callouts = VoiceCalloutManager(self.config)
        self.cockpit_memory = CockpitMemory(
            get_profile_file(get_active_profile(self.config), "cockpit_ai_memory.json"),
            limits=self._cockpit_memory_limits(),
        )
        self.cockpit_brain = CockpitBrain(
            get_profile_file(get_active_profile(self.config), "cockpit_ai_brain.json")
        )
        self.captains_log = CaptainsLog(
            get_profile_file(get_active_profile(self.config), "captains_log.json")
        )
        self.deep_survey = DeepSurveyTracker(
            get_profile_file(get_active_profile(self.config), "deep_survey.json")
        )
        self.expedition_manager = ExpeditionManager(
            get_profile_file(get_active_profile(self.config), "expeditions.json")
        )
        self.specialist_engine = SpecialistEngine(self.config.get("specialists_file"))
        self.adaptive_command = AdaptiveCommandDeck(
            self.config.get("adaptive_command_file"), self.config,
        )
        self._adaptive_startup_briefed = False
        self.session_guard = ProfileSessionGuard(
            self._profile_path("session.active"), APP_VERSION,
        )
        self._startup_recovery_mode = bool(
            self.session_guard.unclean
            and self.config.get("recovery_safe_mode_enabled", True)
        )
        self.compass_cognition = CompassCognition(self.cockpit_brain, self.config)
        self.cockpit_memory.begin_app_session()
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
        self.navigation_scan_progress = None
        self.navigation_scan_progress_source = "bodies"
        self.organic_count = 0
        self.system_bio_signals = 0
        self.system_traffic = {'day': 0, 'week': 0, 'total': 0}
        self.last_traffic_system = None
        self._system_traffic_resolved = False
        self._pending_system_discovery = None
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
        self.bio_sampling = None
        self.bio_sample_points = []
        self._sample_clear_announced = False
        self._rebuy_warning_level = 0
        self._data_risk_level = 0
        self._compass_advisor_last = {}
        self._compass_advisor_last_any = 0.0
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
        self._fuel_used_samples = deque(maxlen=8)
        self._fuel_advisory_signature = None
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
        self.trade_session = self._new_trade_session()
        self.trade_plan_context = None
        self.mining_ai_session = self._new_mining_ai_session()
        self.ai_operational_state = compass_operations.fresh_runtime_state()
        self.combat_awareness = CombatAwareness()
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
        self._expedition_resume_brief_key = None
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
        self._overlay_pos_last_saved = {
            attr: None for attr, _x_key, _y_key in self._OVERLAY_POSITION_SPECS
        }
        self._overlay_sync_grace_until = time.time() + 4.0
        trace_path = resolve_log_path(
            "runtime_trace.log",
            self.config.get("runtime_trace_path", "logs/runtime_trace.log"),
        )
        self.runtime_trace = RuntimeTrace(
            trace_path,
            enabled=bool(self.config.get("runtime_trace_enabled", True)),
            legacy_paths=(application_base_dir() / "runtime_trace.log",),
        )
        self.runtime_trace.start()
        self._cached_cockpit_state_saved_at = 0.0
        self._cached_cockpit_state_loaded = self._load_profile_cockpit_state()
        
        self.setup_layout()
        self.waypoint_manager = WaypointManager(self.config.get("waypoints_file"))
        self.route_plotter = None
        self.target_waypoint = None
        self.waypoint_cache = {}
        
        # Initialize Handlers
        self.edsm = EDSMHandler(self.config)
        self.edsm.set_log_callback(
            lambda tag, msg, sev: self._ui_post(
                self.add_event_feed_entry, tag, msg, severity=sev,
            )
        )
        trade_eddn_uploader.set_log_callback(
            lambda tag, msg, sev: self._ui_post(
                self.add_event_feed_entry, tag, msg, severity=sev,
            )
        )
        self.screenshots = ScreenshotHandler(
            self.config,
            lambda: self.current_sys,
            self.log,
            trace_callback=self._trace_record_ms,
        )
        self.carrier_window = None
        self.colonization_window = None
        self.engineer_window = None
        self.bgs_window = None
        self.commander_profile_window = None
        self.value_ledger_window = None
        self.colonisation_planner_window = None
        self.exploration_window = None
        self.trade_window = None
        self.analytics_window = None
        self.achievement_window = None
        self.specialists_window = None
        self._carrier_panel_tick_job = None
        self._specialist_flush_job = None
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

        self._apply_overlay_mouse_passthrough()
        if not self._startup_recovery_mode:
            self._apply_adaptive_overlay_scene()

        self.db_lock = threading.RLock()
        self.batch_mode = False
        self._startup_restore_active = False
        self._startup_restore_ui_pending = False
        self._publish_cockpit_ai_online()
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
        self.companion_state = companion_features.load_state(self.config.get("companion_state_file"))
        self.import_scan_cache_json()
        self._hydrate_cached_system_scan_state()
        self._show_cached_cockpit_state()
        
        self.watcher = JournalWatcher(
            self.config.get("journal_path"),
            trace_callback=self._trace_record_ms,
            config=self.config,
        )
        self.watcher.register_callback(
            event_cb=lambda event: self._ui_post(self.process_event, event),
            batch_cb=lambda events: self._ui_post(self.process_batch, list(events)),
            cargo_cb=lambda data, vessel="Ship": self._ui_post(
                self.update_cargo, data, vessel, key="watcher:cargo"
            ),
            nav_cb=lambda data: self._ui_post(self.update_nav_route, data, key="watcher:nav"),
            status_cb=lambda data: self._ui_post(self.update_status, data, key="watcher:status"),
            market_cb=lambda data: self._ui_post(self.update_market, data, key="watcher:market"),
            ship_locker_cb=lambda data: self._ui_post(
                self.update_ship_locker, data, key="watcher:ship-locker",
            ),
        )
        self.watcher.prime_market_file()
        self._start_market_import_worker()
        # Let Tk paint the cached cockpit and overlay windows before the
        # journal worker begins its potentially large startup replay.
        self.root.after(75, self.watcher.start)
        self._start_trade_live_services()
        self.cargo_capacity = self.watcher.get_latest_cargo_capacity()
        if self.colony_overlay:
            self.colony_overlay.update()

        self.watcher.force_check_nav()
        self.watcher.force_check_status()

        journal_path = self.config.get("journal_path") or getattr(self.watcher, "journal_path", None)
        threading.Thread(
            target=self.carrier_tracker.scan_journal_history,
            args=(journal_path, 10, self.cmdr_name, self.cmdr_fid),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._import_exploration_history,
            args=(journal_path, self.captains_log, self.deep_survey, self.cmdr_name, self.cmdr_fid),
            name="exploration-history", daemon=True,
        ).start()

        threading.Thread(target=self.check_updates, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._configure_overlay_hotkeys(announce=False)
        self.log(
            f"CONFIG FILE: {CONFIG_FILE} | HUD({self.config.get('hud_x')},{self.config.get('hud_y')}) "
            f"| CARGO({self.config.get('cargo_hud_x')},{self.config.get('cargo_hud_y')})"
        )
        if self._startup_recovery_mode:
            self.add_event_feed_entry(
                "SYSTEM",
                self.session_guard.description()
                + " Cached cockpit state is visible while the journal catches up.",
                severity="WARN",
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
        self._tick_overlay_hotkey_guard()
        self._tick_cockpit_ambient()

    def _show_bootstrap_onboarding(self):
        """Block construction so first-run setup is the only visible window."""
        def complete():
            save_config(self.config)

        window = show_first_run(
            self.root, self.config, complete, standalone=True,
        )
        self.root.wait_window(window)

    def _show_first_run_onboarding(self):
        if not self.is_running:
            return

        def complete():
            self._persist_config()
            if getattr(self, "watcher", None):
                self.watcher.journal_path = self.config.get("journal_path")
                self.watcher.last_journal = None
                self.watcher.file_pos = 0
            self._apply_runtime_feature_toggles()
            self._apply_adaptive_overlay_scene()
            self.schedule_dashboard_refresh(full=True)
            self.add_event_feed_entry(
                "SYSTEM", "First-run setup complete", severity="INFO",
            )

        show_first_run(self.root, self.config, complete)

    def _rerun_first_run_onboarding(self):
        self.config["onboarding_complete"] = False
        self._show_first_run_onboarding()

    def _create_support_bundle(self):
        def worker():
            try:
                path = create_support_bundle(
                    application_base_dir(), self.config, APP_VERSION,
                    health=self._adaptive_health_snapshot(),
                    profile_key=get_active_profile(self.config),
                )
                self._ui_post(
                    lambda: messagebox.showinfo(
                        "Support Bundle",
                        f"Privacy-redacted support bundle created:\n{path}",
                        parent=self.root,
                    )
                )
            except Exception as exc:
                self._ui_post(
                    lambda error=str(exc): messagebox.showerror(
                        "Support Bundle", f"Could not create support bundle:\n{error}",
                        parent=self.root,
                    )
                )

        threading.Thread(target=worker, name="support-bundle", daemon=True).start()

    def _reapply_overlay_positions(self):
        for attr, x_key, y_key in self._OVERLAY_POSITION_SPECS:
            overlay = getattr(self, attr, None)
            win = getattr(overlay, "win", None)
            if not win:
                continue
            try:
                if not win.winfo_exists() or x_key not in self.config or y_key not in self.config:
                    continue
                x = int(float(self.config[x_key]))
                y = int(float(self.config[y_key]))
                # Position-only geometry preserves each HUD's current/dynamic size.
                win.geometry(f"+{x}+{y}")
                self._overlay_pos_last_saved[attr] = (x, y)
            except (TypeError, ValueError, tk.TclError):
                continue
        self.root.after(250, self._log_applied_overlay_positions)

    def _apply_overlay_mouse_passthrough(self):
        """Apply the profile's input mode to every live native overlay."""
        enabled = bool(self.config.get("overlay_mouse_passthrough", True))
        windows = []
        for attr, _x_key, _y_key in self._OVERLAY_POSITION_SPECS:
            overlay = getattr(self, attr, None)
            window = getattr(overlay, "win", overlay)
            if window is not None:
                windows.append(window)
        ground_popup = getattr(self, "ground_popup", None)
        if ground_popup is not None:
            windows.append(ground_popup)

        applied = 0
        seen = set()
        for window in windows:
            marker = id(window)
            if marker in seen:
                continue
            seen.add(marker)
            try:
                if window.winfo_exists() and set_mouse_passthrough(window, enabled):
                    applied += 1
            except (AttributeError, tk.TclError):
                continue
        return applied

    def _overlay_hotkey_window_items(self):
        """Return unique live overlay windows, including the ground popup."""
        items = []
        seen = set()
        for attr, _x_key, _y_key in self._OVERLAY_POSITION_SPECS:
            window = self._overlay_window(getattr(self, attr, None))
            if window is None or id(window) in seen:
                continue
            seen.add(id(window))
            items.append((attr, window))
        popup = getattr(self, "ground_popup", None)
        if popup is not None and id(popup) not in seen:
            items.append(("ground_popup", popup))
        return items

    @staticmethod
    def _overlay_window_is_shown(window):
        try:
            return bool(window.winfo_exists()) and str(window.state()) not in ("withdrawn", "iconic")
        except (AttributeError, tk.TclError):
            return False

    def _restore_overlay_hotkey_windows(self, names):
        adaptive_hidden = set(getattr(self, "_adaptive_hidden_overlays", set()))
        individually_hidden = set(getattr(self, "_overlay_hotkey_hidden", set()))
        lookup = dict(self._overlay_hotkey_window_items())
        for attr in set(names or ()):
            if attr in adaptive_hidden or attr in individually_hidden:
                continue
            window = lookup.get(attr)
            if window is None:
                continue
            try:
                if window.winfo_exists():
                    window.deiconify()
                    window.attributes("-topmost", True)
                    window.lift()
            except (AttributeError, tk.TclError):
                continue

    def _reset_overlay_hotkey_visibility(self, restore=False):
        names = set(getattr(self, "_overlay_hotkey_restore", set()))
        names.update(getattr(self, "_overlay_hotkey_hidden", set()))
        self._overlay_hotkey_global_hidden = False
        self._overlay_hotkey_hidden = set()
        self._overlay_hotkey_restore = set()
        if restore:
            self._restore_overlay_hotkey_windows(names)

    def _configure_overlay_hotkeys(self, announce=True):
        manager = getattr(self, "overlay_hotkeys", None)
        if manager is None:
            return {"registered": {}, "errors": {"service": "not available"}}
        bindings = {
            action: self.config.get(key, "")
            for action, key, _label, _attr in OVERLAY_HOTKEY_SPECS
        }
        if not self.config.get("overlay_hotkeys_enabled", True):
            bindings = {}
        report = manager.configure(bindings)
        labels = {action: label for action, _key, label, _attr in OVERLAY_HOTKEY_SPECS}
        errors = report.get("errors") or {}
        registered = report.get("registered") or {}
        if errors:
            detail = "; ".join(
                f"{labels.get(action, action)} ({error})"
                for action, error in errors.items()
            )
            logging.warning("Overlay hotkey registration: %s", detail)
            if hasattr(self, "event_feed_entries"):
                self.add_event_feed_entry(
                    "SYSTEM", f"Overlay hotkey unavailable: {detail}", severity="WARN",
                )
        elif announce and hasattr(self, "event_feed_entries"):
            if registered:
                self.add_event_feed_entry(
                    "SYSTEM",
                    f"Overlay hotkeys updated: {len(registered)} active",
                    severity="INFO",
                )
            else:
                self.add_event_feed_entry(
                    "SYSTEM", "Overlay hotkeys disabled", severity="INFO",
                )
        return report

    def _handle_overlay_hotkey(self, action):
        if not self.is_running:
            return
        spec = next((item for item in OVERLAY_HOTKEY_SPECS if item[0] == action), None)
        if spec is None:
            return
        _action, _key, label, attr = spec
        if action == "toggle_all":
            if self._overlay_hotkey_global_hidden:
                self._overlay_hotkey_global_hidden = False
                restore = set(self._overlay_hotkey_restore)
                self._overlay_hotkey_restore.clear()
                self._restore_overlay_hotkey_windows(restore)
                self._apply_adaptive_overlay_scene()
                message = "Overlays restored"
            else:
                self._overlay_hotkey_global_hidden = True
                for name, window in self._overlay_hotkey_window_items():
                    try:
                        if self._overlay_window_is_shown(window):
                            if name not in self._overlay_hotkey_hidden:
                                self._overlay_hotkey_restore.add(name)
                            window.withdraw()
                    except (AttributeError, tk.TclError):
                        continue
                message = "Overlays hidden"
        else:
            if self._overlay_hotkey_global_hidden:
                self.add_event_feed_entry(
                    "SYSTEM",
                    f"{label} remains behind the all-overlay curtain; use the all-overlays shortcut first",
                    severity="INFO",
                )
                return
            window = self._overlay_window(getattr(self, attr, None))
            if window is None:
                self.add_event_feed_entry(
                    "SYSTEM", f"{label} is not enabled in Settings", severity="WARN",
                )
                return
            if attr in self._overlay_hotkey_hidden:
                self._overlay_hotkey_hidden.discard(attr)
                self._overlay_hotkey_restore.discard(attr)
                getattr(self, "_adaptive_hidden_overlays", set()).discard(attr)
                self._restore_overlay_hotkey_windows({attr})
                message = f"{label} shown"
            elif self._overlay_window_is_shown(window):
                self._overlay_hotkey_hidden.add(attr)
                self._overlay_hotkey_restore.add(attr)
                try:
                    window.withdraw()
                except (AttributeError, tk.TclError):
                    pass
                message = f"{label} hidden"
            else:
                getattr(self, "_adaptive_hidden_overlays", set()).discard(attr)
                self._restore_overlay_hotkey_windows({attr})
                message = f"{label} shown"
        self.add_event_feed_entry("SYSTEM", message, severity="INFO")

    def _enforce_overlay_hotkey_visibility(self):
        global_hidden = bool(getattr(self, "_overlay_hotkey_global_hidden", False))
        hidden = set(getattr(self, "_overlay_hotkey_hidden", set()))
        if not global_hidden and not hidden:
            return
        for attr, window in self._overlay_hotkey_window_items():
            if not global_hidden and attr not in hidden:
                continue
            try:
                if not self._overlay_window_is_shown(window):
                    continue
                if global_hidden and attr not in hidden:
                    self._overlay_hotkey_restore.add(attr)
                window.withdraw()
            except (AttributeError, tk.TclError):
                continue

    def _tick_overlay_hotkey_guard(self):
        if not self.is_running:
            return
        self._enforce_overlay_hotkey_visibility()
        active = bool(
            self._overlay_hotkey_global_hidden or self._overlay_hotkey_hidden
        )
        self.root.after(90 if active else 350, self._tick_overlay_hotkey_guard)

    def _log_applied_overlay_positions(self):
        try:
            positions = []
            for attr, _x_key, _y_key in self._OVERLAY_POSITION_SPECS:
                overlay = getattr(self, attr, None)
                win = getattr(overlay, "win", None)
                if win and win.winfo_exists():
                    positions.append(
                        f"{attr.upper()}({win.winfo_x()},{win.winfo_y()})"
                    )
            self.log("CONFIG FILE: APPLIED " + " | ".join(positions))
        except Exception:
            pass

    def _capture_overlay_positions(self):
        """Copy stable live HUD coordinates into config without writing it."""
        changed = False
        for attr, x_key, y_key in self._OVERLAY_POSITION_SPECS:
            overlay = getattr(self, attr, None)
            win = getattr(overlay, "win", None)
            if not win:
                continue
            try:
                if not win.winfo_exists():
                    continue
                pos = (int(win.winfo_x()), int(win.winfo_y()))
                configured = None
                if x_key in self.config and y_key in self.config:
                    configured = (
                        int(float(self.config[x_key])),
                        int(float(self.config[y_key])),
                    )
                # Withdrawn or not-yet-mapped windows commonly report (0, 0).
                # Preserve a real configured position, and do not manufacture a
                # new (0, 0) value when an optional position has never been set.
                if pos == (0, 0):
                    if configured is None:
                        continue
                    if configured != (0, 0):
                        pos = configured
                self._overlay_pos_last_saved[attr] = pos
                if configured != pos:
                    self.config[x_key], self.config[y_key] = pos
                    changed = True
            except (TypeError, ValueError, tk.TclError):
                continue
        return changed

    @staticmethod
    def _perf_start():
        return time.perf_counter()

    def _trace_record_ms(self, label, elapsed_ms):
        if self.runtime_trace:
            self.runtime_trace.record_ms(label, elapsed_ms)

    def _trace_bump(self, label, amount=1):
        if self.runtime_trace:
            self.runtime_trace.bump(label, amount)

    def _ui_post(self, callback, *args, key=None, **kwargs):
        dispatcher = getattr(self, "ui_dispatcher", None)
        if dispatcher:
            return dispatcher.post(callback, *args, key=key, **kwargs)
        return False

    def _tick_runtime_trace(self):
        if not self.is_running:
            return
        extra = {
            "route_waypoints": len(getattr(self.waypoint_manager, "waypoints", []) or []),
            "scan_items": len(getattr(self, "scan_items", []) or []),
            "log_entries": len(getattr(self, "log_entries", []) or []),
            "event_feed_entries": len(getattr(self, "event_feed_entries", []) or []),
            "ui_dispatch": getattr(self, "ui_dispatcher", None).stats()
            if getattr(self, "ui_dispatcher", None) else {},
            "persistence": persistence_queue().stats(),
        }
        if self.runtime_trace:
            self.runtime_trace.flush(extra=extra)
        self.root.after(1000, self._tick_runtime_trace)

    def _tick_cockpit_ambient(self):
        if not self.is_running:
            return
        self._maybe_speak_ambient_chatter()
        self.root.after(60000, self._tick_cockpit_ambient)

    def _maybe_speak_ambient_chatter(self):
        if (not self.config.get("cockpit_memory_enabled", True)
                or not self.config.get("cockpit_ambient_chatter_enabled", True)
                or not getattr(self, "cockpit_memory", None)):
            return
        if getattr(self, "hud_flight_state", None) not in ("FLIGHT", "SUPERCRUISE"):
            return
        last_event = getattr(self, "last_journal_event_ts", None)
        if not last_event or (time.time() - last_event) < 480:
            return
        if self.cockpit_memory.queue_ambient_remark():
            self._speak_pending_cockpit_remark()

    def _tick_overlay_position_sync(self):
        if not self.is_running:
            return
        now = time.time()
        if now < self._overlay_sync_grace_until:
            remaining_ms = int((self._overlay_sync_grace_until - now) * 1000) + 25
            self.root.after(max(100, min(700, remaining_ms)), self._tick_overlay_position_sync)
            return
        if self._capture_overlay_positions():
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
            self._last_ui_stall_ts = time.time()
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
        """Cancel live work, queue the final state and exit without waiting on speech."""
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self.is_running = False
        try:
            self.root.withdraw()
        except Exception:
            pass
        for attr in tuple(name for name, _x, _y in self._OVERLAY_POSITION_SPECS) + (
            "gravity_warning_hud", "toast_hud", "heartbeat_hud",
        ):
            window = self._overlay_window(getattr(self, attr, None))
            try:
                if window is not None:
                    window.withdraw()
            except Exception:
                pass
        if getattr(self, "watcher", None):
            self.watcher.stop()
        if getattr(self, "overlay_hotkeys", None):
            self.overlay_hotkeys.stop()
        if getattr(self, "ui_dispatcher", None):
            self.ui_dispatcher.stop()
        # Cancellation comes before any state work. Piper synthesis, playback
        # and queued callouts must never keep the application open.
        try:
            self.voice_callouts.stop()
        except Exception:
            pass
        # This is intentionally the only write site for the last cockpit
        # snapshot. It provides a fast visual restore after a normal quit
        # without turning live journal traffic into continuous disk writes.
        self._save_profile_cockpit_state()
        self._save_exploration_checkpoint("app-close", immediate=True)
        # Elite's Shutdown journal event owns the Compass debrief. Closing
        # only the companion leaves an in-progress game session intact and
        # avoids running another cognition pass during application teardown.
        
        if self.route_plotter and self.route_plotter.win.winfo_exists():
            self.route_plotter.on_close()
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
        if self.analytics_window and self.analytics_window.is_open():
            self.analytics_window._on_close()
        if self.specialists_window and self.specialists_window.is_open():
            self.specialists_window._on_close()
        try:
            self.specialist_engine.flush(wait=False)
        except Exception:
            pass
        if self.achievement_engine:
            self.achievement_engine.flush(wait=False)
        if getattr(self, "cockpit_memory", None):
            try:
                self.cockpit_memory.flush(wait=False)
            except Exception:
                pass
        if getattr(self, "adaptive_command", None):
            try:
                self.adaptive_command.flush(wait=False)
            except Exception:
                pass
        if getattr(self, "deep_survey", None):
            try:
                self.deep_survey.flush(wait=False)
            except Exception:
                pass
        if getattr(self, "expedition_manager", None):
            try:
                self.expedition_manager.flush(wait=False)
            except Exception:
                pass
            
        self._stop_market_import_worker()
        self.screenshots.stop()
        if time.time() >= self._overlay_sync_grace_until:
            self._capture_overlay_positions()
            try:
                if self.colony_overlay and self.colony_overlay.win and self.colony_overlay.win.winfo_exists():
                    w = int(self.colony_overlay.win.winfo_width())
                    h = int(self.colony_overlay.win.winfo_height())
                    if w > 0 and h > 0:
                        self.config["colony_overlay_w"], self.config["colony_overlay_h"] = w, h
            except Exception:
                pass
        self.config["main_geometry"] = self.root.geometry()
        self._persist_config()
        if hasattr(self, 'conn'):
            self._stop_db_commit_worker(close=True, timeout=0.35)
        if self.runtime_trace:
            try:
                self.runtime_trace.flush(extra={"shutdown": True})
                self.runtime_trace.close(wait=False)
            except Exception:
                pass
        # One short durability window replaces several sequential five-second
        # waits. All state was already coalesced onto the same writer.
        flush_persistence(timeout=1.0)
        if self.ground_target_window and self.ground_target_window.winfo_exists():
            try:
                self.config["ground_target_window_geometry"] = self.ground_target_window.geometry()
                self._persist_config()
            except Exception:
                pass
        self._destroy_ground_popup()
        if getattr(self, "session_guard", None):
            self.session_guard.close()
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
        self.open_exploration_window(section="route")

    def _route_panel_navigation_state(self):
        return {
            "current_system": self.current_sys,
            "destination": self.dest_name,
            "route": list(self.route_list or []),
            "entries": [dict(row) for row in (self.nav_route_entries or []) if isinstance(row, dict)],
        }

    def open_mining_window(self):
        """Open the authoritative elite-trader-style mining workflow."""
        self.open_specialists_window(section="mining")

    def open_analytics_window(self):
        if self.analytics_window and self.analytics_window.is_open():
            self._show_embedded_page("ANALYTICS", self.analytics_window.win)
            self.analytics_window.on_shown()
            return
        self.analytics_window = AnalyticsWindow(self.dashboard_host, self, embedded=True)
        self._show_embedded_page("ANALYTICS", self.analytics_window.win)
        self.analytics_window.on_shown()

    def open_carrier_window(self):
        if self.carrier_window and self.carrier_window.is_open():
            self._show_embedded_page("CARRIER", self.carrier_window.win)
            return
        self.carrier_window = CarrierWindow(self.dashboard_host, self.config, self.carrier_tracker, embedded=True)
        self._show_embedded_page("CARRIER", self.carrier_window.win)

    def open_specialists_window(self, section=None):
        if self.specialists_window and self.specialists_window.is_open():
            self._show_embedded_page("SPECIALISTS", self.specialists_window.win)
            if section:
                self.specialists_window.select_section(section)
            self.specialists_window.on_shown()
            return
        self.specialists_window = SpecialistsWindow(
            self.dashboard_host, self, self.specialist_engine, embedded=True,
        )
        self._show_embedded_page("SPECIALISTS", self.specialists_window.win)
        if section:
            self.specialists_window.select_section(section)
        self.specialists_window.on_shown()

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
            cargo_capacity_provider=lambda: self.cargo_capacity,
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
        self._apply_overlay_mouse_passthrough()
        self.config["colony_overlay_enabled"] = True
        self._save_config_file()

    def open_engineer_window(self):
        if self.engineer_window and self.engineer_window.is_open():
            self._show_embedded_page("ENGINEER", self.engineer_window.win)
            self.engineer_window.on_shown()
            return
        self.engineer_window = EngineerWindow(
            self.dashboard_host,
            self.config,
            self.engineer_materials,
            self._save_engineer_materials,
            get_current_system=lambda: self.current_sys if self.current_sys != "---" else "",
            get_current_coords=lambda: self.current_coords,
            plot_system_callback=self._route_engineering_system,
            is_active_callback=lambda: getattr(self, "_active_page", None) == "ENGINEER",
            embedded=True,
        )
        self._show_embedded_page("ENGINEER", self.engineer_window.win)
        self.engineer_window.on_shown()

    def _route_engineering_system(self, system, source="Engineering"):
        """Hand an external workspace destination to the existing route page."""
        if not system:
            return
        self.open_route_planner()
        try:
            self.route_plotter.tabs.select(2)
            entry = self.route_plotter.neutron_to_entry
            entry.delete(0, tk.END)
            entry.insert(0, system)
            entry.focus_set()
            self.route_plotter.neutron_status_lbl.config(
                text=f"Destination loaded from {source}: {system}. Check jump range, then PLOT."
            )
        except Exception:
            pass

    def open_bgs_window(self):
        if self.bgs_window and self.bgs_window.is_open():
            self._show_embedded_page("GALAXY", self.bgs_window.win)
            return
        self.bgs_window = BGSWindow(
            self.dashboard_host,
            self.config,
            self.db_load_bgs_systems,
            self.db_load_bgs_factions,
            self.db_delete_bgs_system,
            self.db_purge_bgs,
            self.db_purge_empty_bgs_systems,
            get_galaxy_state_cb=lambda: self.companion_state,
            toggle_faction_watch_cb=self._toggle_galaxy_faction_watch,
            get_carrier_state_cb=lambda: self.carrier_tracker.carrier_data if self.carrier_tracker else {},
            open_carrier_cb=self.open_carrier_window,
            embedded=True,
        )
        self._show_embedded_page("GALAXY", self.bgs_window.win)

    def open_commander_profile_window(self):
        if self.commander_profile_window and self.commander_profile_window.is_open():
            self.commander_profile_window.refresh()
            self.commander_profile_window._refresh_pending = False
            self._show_embedded_page("PROFILE", self.commander_profile_window.win)
            return
        self.commander_profile_window = CommanderProfileWindow(self.dashboard_host, self, embedded=True)
        self._show_embedded_page("PROFILE", self.commander_profile_window.win)

    def open_exploration_window(self, section=None):
        if self.exploration_window and self.exploration_window.is_open():
            self._show_embedded_page("EXPLORE", self.exploration_window.win)
            self.exploration_window.on_shown(section=section)
            return
        self.exploration_window = ExplorationWindow(self.dashboard_host, self, embedded=True)
        self._show_embedded_page("EXPLORE", self.exploration_window.win)
        self.exploration_window.on_shown(section=section)

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
                    f"{title}  //  +{points:,} pts",
                    severity="success",
                    duration_s=15,
                    icon=icon,
                )
            window = getattr(self, "achievement_window", None)
            if window and window.is_open() and getattr(self, "_active_page", None) == "ACHIEVE":
                window.refresh()
            self._refresh_commander_profile_window()

        try:
            self._ui_post(apply_unlock)
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
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
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
                self._ui_post(lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="INFO"))

            elif new_status == "cooldown":
                system = carrier_data.get("system") or "?"
                msg = f"FC {label}: arrived at {system}"
                self._ui_post(lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="INFO"))
                if self.toast_hud:
                    self._ui_post(lambda m=msg: self.toast_hud.push("CARRIER JUMPED", m, severity="success"))

            elif new_status == "cooldown_cancel":
                msg = f"FC {label}: jump cancelled"
                self._ui_post(lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="WARN"))

            elif old_status in ("cooldown", "cooldown_cancel") and new_status == "idle":
                system = carrier_data.get("system") or "?"
                msg = f"FC {label}: cooldown complete @ {system}"
                self._ui_post(lambda m=msg: self.add_event_feed_entry("CARRIER", m, severity="INFO"))
                if self.toast_hud:
                    self._ui_post(lambda m=msg: self.toast_hud.push("CARRIER READY", m, severity="success"))
        except Exception:
            pass

    def _on_carrier_panel_updated(self, carrier_data):
        """Fired by CarrierTracker whenever state changes (persistent hook)."""
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        try:
            self._ui_post(self.update_carrier_panel, key="carrier-panel")
            if self.carrier_hud:
                self._ui_post(lambda d=dict(carrier_data): self.carrier_hud.update(d), key="carrier-hud")
            if carrier_data.get("status") == "jumping":
                self._ui_post(self._ensure_carrier_panel_ticker, key="carrier-ticker")
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

    def _set_body_signals(self, body_id, bio_count=0, geo_count=0, genuses=None):
        body_id = self._normalize_body_id(body_id)
        if body_id is None:
            return
        previous = self.body_signals.get(body_id, {})
        self.body_signals[body_id] = {
            "bio": int(bio_count or 0),
            "geo": int(geo_count or 0),
            "genuses": list(genuses) if genuses else list(previous.get("genuses") or []),
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
            self.navigation_scan_progress = 1.0
            self.navigation_scan_progress_source = "bodies"
            self.db_update_system(self.current_sys, self.total, self.scanned)
            if not self.batch_mode:
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.update_hud()
                self.schedule_dashboard_refresh()
                self._refresh_exploration_window()

    def _seed_navigation_scan_progress(self):
        """Seed the HUD from persisted body knowledge on entering a system."""
        if self.total > 0:
            self.navigation_scan_progress = max(0.0, min(1.0, self.scanned / self.total))
        else:
            self.navigation_scan_progress = None
        self.navigation_scan_progress_source = "bodies"

    def _record_navigation_fss_progress(self, progress):
        """Keep Frontier's live FSS percentage without corrupting body counts.

        FSS ``Progress`` is not a body count: it can also reflect non-body
        signals.  Return visits may not replay every already-known ``Scan``
        event, however, so it is the best live source for the HUD progress bar.
        """
        try:
            progress = float(progress)
        except (TypeError, ValueError):
            return
        progress = max(0.0, min(1.0, progress))
        body_progress = (self.scanned / self.total) if self.total > 0 else 0.0
        current = self.navigation_scan_progress
        if current is None:
            current = 0.0
        self.navigation_scan_progress = max(progress, body_progress, current)
        self.navigation_scan_progress_source = "fss"

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

        self._apply_overlay_mouse_passthrough()
        self._apply_adaptive_overlay_scene()

    def open_settings(self):
        def on_save():
            self.log("Configuration saved successfully.")
            self._apply_active_profile_theme()
            self._apply_runtime_feature_toggles()
            self._configure_overlay_hotkeys()
            self._refresh_cockpit_brain(event="settings_saved")
            self._publish_cockpit_ai_changes()
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
                voice_manager=self.voice_callouts,
                cockpit_memory=self.cockpit_memory,
                cockpit_brain=self.cockpit_brain,
                cockpit_cognition=self.compass_cognition,
                support_bundle_callback=self._create_support_bundle,
                rerun_setup_callback=self._rerun_first_run_onboarding,
                health_provider=self._adaptive_health_snapshot,
                ui_post_callback=self._ui_post,
            )
        self._show_embedded_page("SETTINGS", self.settings_page)

    def fetch_system_traffic(self, system_name):
        self.last_edsm_request_ts = time.time()
        self._system_traffic_resolved = False
        def callback(traffic_data):
            def _apply():
                if self.current_sys != system_name:
                    return
                self._apply_system_traffic_context(system_name, traffic_data)
                self._process_compass_cognition(
                    "TrafficUpdate", traffic_data, traffic_data,
                    startup_replay=bool(getattr(self, "is_first_load", False)),
                )
                self.update_dashboard_ui()
                self.update_hud()
                if self.system_info_hud and isinstance(traffic_data, dict):
                    self.system_info_hud.update_traffic(self.system_traffic)
            self._ui_post(_apply, key="edsm-traffic")
        self.edsm.fetch_traffic(system_name, callback)

        if self.config.get("system_info_enabled", True):
            def details_callback(details):
                def _apply():
                    if self.current_sys != system_name:
                        return
                    if self.system_info_hud:
                        self.system_info_hud.update_edsm_details(details)
                self._ui_post(_apply, key="edsm-details")
            self.edsm.fetch_system_details(system_name, details_callback)

            sys_addr = self.current_system_address
            if sys_addr:
                def spansh_callback(data):
                    def _apply():
                        if self.current_sys != system_name:
                            return
                        if self.system_info_hud:
                            self.system_info_hud.update_spansh(data)
                    self._ui_post(_apply, key="spansh-details")
                self.edsm.fetch_spansh_system(sys_addr, spansh_callback)

    @staticmethod
    def _traffic_has_visits(traffic):
        if not isinstance(traffic, dict):
            return False
        for key in ("day", "week", "total"):
            try:
                if int(float(traffic.get(key) or 0)) > 0:
                    return True
            except (TypeError, ValueError):
                pass
        return False

    @staticmethod
    def _normalize_system_traffic(traffic):
        normalized = {}
        for key in ("day", "week", "total"):
            try:
                normalized[key] = max(0, int(float((traffic or {}).get(key) or 0)))
            except (AttributeError, TypeError, ValueError):
                normalized[key] = 0
        return normalized

    def _system_has_known_traffic(self, system_name=None):
        system_name = system_name or self.current_sys
        if system_name == self.current_sys and self._traffic_has_visits(self.system_traffic):
            return True
        memory = getattr(self, "cockpit_memory", None)
        return bool(memory and memory.system_has_traffic(system_name))

    def _apply_system_traffic_context(self, system_name, traffic_data):
        """Share HUD traffic with Compass and resolve delayed discovery wording."""
        self._system_traffic_resolved = True
        if isinstance(traffic_data, dict):
            self.last_edsm_event_ts = time.time()
            self.system_traffic = self._normalize_system_traffic(traffic_data)
            if (self.config.get("cockpit_memory_enabled", True)
                    and getattr(self, "cockpit_memory", None)):
                self.cockpit_memory.observe_system_traffic(system_name, self.system_traffic)

        pending = self._pending_system_discovery
        if pending and pending[0] == system_name:
            self._pending_system_discovery = None
            self._consider_system_undiscovered(startup_replay=pending[1], traffic_resolved=True)
        elif self._system_has_known_traffic(system_name):
            self.system_undiscovered = False

    def _consider_system_undiscovered(self, startup_replay=False, traffic_resolved=False):
        """Only describe the whole system as undiscovered after traffic is known."""
        if self._system_has_known_traffic(self.current_sys):
            self.system_undiscovered = False
            self._pending_system_discovery = None
            return False
        if not (traffic_resolved or self._system_traffic_resolved):
            self._pending_system_discovery = (self.current_sys, bool(startup_replay))
            return False

        self.system_undiscovered = True
        self.add_event_feed_entry(
            "ALERT", "Undiscovered system star scanned", severity="WARN", copy_text=self.current_sys
        )
        if startup_replay:
            return True

        discovery_voice = [
            f"First discovery. {self.current_sys} appears undiscovered.",
            f"I found no prior survey records or traffic for {self.current_sys}. This one may be ours.",
            f"Uncharted system confirmed. I am opening a new survey record for {self.current_sys}.",
            f"Interesting. Neither the Codex nor traffic records show a prior visit to {self.current_sys}.",
        ]
        if (self.config.get("cockpit_memory_enabled", True)
                and getattr(self, "cockpit_memory", None)):
            discoveries = self.cockpit_memory.count("first_discoveries")
            if self.cockpit_memory.should_reference_repeat(
                    discoveries, self.config.get("cockpit_personality_level", "Balanced")):
                discovery_voice.append(
                    f"Another uncharted system for our shared record. That makes {discoveries:,} first discoveries together."
                )
        self._speak(
            discovery_voice,
            category="exploration", cooldown_s=600,
            key=f"first-discovery:{self.current_sys}",
        )
        return True

    @staticmethod
    def _valuable_world_voice_lines(body_name, planet_class, terraformable=False):
        body_name = str(body_name or "this body")
        if planet_class == "Earthlike body":
            return (
                f"Earth-like world confirmed at {body_name}. That is a rare and valuable find.",
                f"Sensors identify {body_name} as an Earth-like world. This one deserves a full surface map.",
                f"Now that is worth slowing down for. Earth-like world at {body_name}.",
                f"A blue-green world in the black. {body_name} is Earth-like.",
            )
        if planet_class == "Water world":
            if terraformable:
                return (
                    f"Terraformable water world detected at {body_name}. High-value mapping target confirmed.",
                    f"Water world at {body_name}, and the atmosphere is suitable for terraforming. An excellent find.",
                    f"The survey just became profitable. {body_name} is a terraformable water world.",
                    f"Blue planet confirmed at {body_name}. Terraformable, valuable, and well worth mapping.",
                )
            return (
                f"Water world detected at {body_name}. High-value mapping target confirmed.",
                f"Sensors show a water world at {body_name}. Worth a closer look before we leave.",
                f"A valuable blue world at {body_name}. I have marked it for surface mapping.",
                f"Water world confirmed. {body_name} is a strong addition to our survey data.",
            )
        if planet_class == "Ammonia world":
            return (
                f"Ammonia world confirmed at {body_name}. A rare and valuable survey target.",
                f"Sensors identify an ammonia world at {body_name}. I recommend a full surface map.",
                f"Unusual chemistry at {body_name}. Ammonia world, and worth recording properly.",
                f"High-value ammonia world detected at {body_name}. The exploration ledger approves.",
            )
        return (
            f"Terraformable world detected at {body_name}. Worth mapping before we leave.",
            f"The survey data marks {body_name} as terraformable. That makes it a valuable target.",
            f"Promising world at {body_name}. Terraforming candidate confirmed.",
            f"{body_name} has long-term potential. I have flagged it as a high-value mapping target.",
        )

    @staticmethod
    def _valuable_body_is_tracked(rows, body_name):
        for row in rows or ():
            parts = str(row).split(" ", 2)
            if len(parts) == 3 and parts[2] == body_name:
                return True
        return False

    def _track_valuable_world(self, body_name, planet_class, terraformable=False,
                              startup_replay=False):
        if planet_class not in ("Earthlike body", "Water world", "Ammonia world") and not terraformable:
            return False
        body_name = body_name or "Unknown"
        if self._valuable_body_is_tracked(self.valuable_bodies, body_name):
            return False
        self.valuable_system = True
        icon = {
            "Earthlike body": "🌍",
            "Water world": "💧",
            "Ammonia world": "☣️",
        }.get(planet_class, "🛠️")
        self.valuable_bodies.append(f"- {icon} {body_name}")
        if not startup_replay:
            self.add_event_feed_entry(
                "VALUABLE", f"{icon} Valuable world: {body_name}",
                severity="WARN", copy_text=body_name,
            )
            self._speak(
                self._valuable_world_voice_lines(body_name, planet_class, terraformable),
                category="exploration", cooldown_s=86_400,
                key=f"valuable-world:{self.current_sys}:{body_name}",
            )
        return True

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
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            self._hud_refresh_requested = True
            return
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
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            self._hud_refresh_requested = True
            return
        if threading.current_thread() is not threading.main_thread():
            self._ui_post(self.update_hud, key="navigation-hud")
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

        target_hud = self.hud
        payload = (
            self.current_sys, self.dest_name, dist,
            self.scanned, self.total, custom_r_pos, self.system_traffic, game_r_pos,
            route_waypoint, route_counts, "OK", None, self._build_navigation_hud_context(),
        )

        def _draw_navigation_hud():
            if self.hud is target_hud:
                target_hud.update(*payload)

        self.root.after(0, _draw_navigation_hud)
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
            badges.append(("BIO", "ok" if self.organic_count >= self.system_bio_signals else "alert"))
        if self.total > 0:
            badges.append(("FSS", "ok" if self.scanned >= self.total else "info"))
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
            "scan_progress": getattr(self, "navigation_scan_progress", None),
            "scan_progress_source": getattr(self, "navigation_scan_progress_source", "bodies"),
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
                window = getattr(self, "analytics_window", None)
                if window and window.is_open() and getattr(self, "_active_page", None) == "ANALYTICS":
                    self.root.after(0, window.request_refresh)
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
            try:
                self.schedule_dashboard_refresh()
            except Exception:
                pass
            self.update_hud()
        return changed

    def _apply_credit_event(self, ev, raw, log=True):
        if not isinstance(raw, dict):
            return False
        timestamp = raw.get("timestamp")
        explicit = authoritative_balance(raw)
        if explicit is not None:
            return self._set_commander_balance(explicit, timestamp=timestamp, log=log)
        if self.cmdr_balance is None:
            return False
        delta = credit_delta(ev, raw)
        if not delta:
            return False
        return self._set_commander_balance(int(self.cmdr_balance or 0) + delta, timestamp=timestamp, log=log)

    def _exploration_intelligence_snapshot(self, compact=False):
        try:
            intelligence = build_intelligence(self)
        except Exception as exc:
            logging.debug("Exploration intelligence snapshot skipped: %s", exc)
            return {}
        self._latest_exploration_intelligence = intelligence
        if compact:
            intelligence = dict(intelligence)
            completion = dict(intelligence.get("completion") or {})
            completion.pop("body_rows", None)
            intelligence["completion"] = completion
            intelligence["actions"] = [
                dict(row) for row in list(intelligence.get("actions") or [])[:5]
            ]
            intelligence["milestones"] = [
                dict(row) for row in list(intelligence.get("milestones") or [])[-4:]
            ]
        return intelligence

    def _save_exploration_checkpoint(self, reason="app-close", immediate=False):
        tracker = getattr(self, "deep_survey", None)
        if not tracker:
            return {}
        try:
            return tracker.update_checkpoint(
                checkpoint_payload(self, reason), immediate=immediate,
            )
        except Exception as exc:
            logging.debug("Exploration checkpoint skipped [%s]: %s", reason, exc)
            return {}

    def _update_exploration_intelligence(self, ev, raw, startup_replay=False):
        tracker = getattr(self, "deep_survey", None)
        if not tracker:
            return
        relevant = {
            "LoadGame", "Location", "FSDJump", "CarrierJump", "Docked", "Shutdown",
            "FSSDiscoveryScan", "FSSAllBodiesFound", "Scan", "SAAScanComplete",
            "SAASignalsFound", "ScanOrganic", "CodexEntry", "Screenshot",
        }
        if ev not in relevant:
            return
        timestamp = raw.get("timestamp") if isinstance(raw, dict) else None
        try:
            milestones = tracker.evaluate_milestones(
                current_bodies=getattr(self, "scan_items", None) or (),
                timestamp=timestamp,
            )
        except Exception as exc:
            logging.debug("Exploration milestone evaluation skipped [%s]: %s", ev, exc)
            milestones = []
        intelligence = self._exploration_intelligence_snapshot()
        regions = intelligence.get("regions") or {}
        current_region = regions.get("current") or {}
        try:
            self.achievement_engine.process_event({
                "type": "VoidCompassRegionPassport",
                "event": "VoidCompassRegionPassport",
                "VisitedRegions": int(regions.get("visited") or 0),
                "RegionID": current_region.get("id"),
                "RegionName": current_region.get("name"),
            }, notify=not startup_replay, historical=startup_replay)
        except Exception:
            pass
        if ev in {"Docked", "Shutdown"}:
            self._save_exploration_checkpoint(ev.casefold(), immediate=ev == "Shutdown")
        if ev == "LoadGame" and not startup_replay:
            checkpoint = intelligence.get("checkpoint") or {}
            checkpoint_key = str(checkpoint.get("saved_at") or "")
            if checkpoint_key and checkpoint_key != getattr(self, "_exploration_resume_feed_key", None):
                self._exploration_resume_feed_key = checkpoint_key
                completion = checkpoint.get("completion") or {}
                next_waypoint = checkpoint.get("next_waypoint") or "no plotted waypoint"
                self.add_event_feed_entry(
                    "EXPEDITION",
                    f"Resume checkpoint: {checkpoint.get('system') or 'unknown system'} · "
                    f"{completion.get('summary') or 'survey state retained'} · next {next_waypoint}",
                    severity="INFO",
                )
        if not milestones or startup_replay:
            return
        for milestone in milestones:
            title = str(milestone.get("title") or "Exploration milestone")
            detail = str(milestone.get("detail") or "")
            self.add_event_feed_entry("MILESTONE", f"{title} · {detail}", severity="INFO")
            if ev != "Shutdown" and getattr(self, "captains_log", None):
                self.captains_log.add_manual_highlight("MILESTONE", title, detail)
        self._pulse_cockpit_ai()
        major = next((row for row in reversed(milestones) if int(row.get("level") or 0) >= 4), None)
        if major:
            title = major.get("title") or "Exploration milestone"
            self._speak((
                f"Milestone recorded. {title}.",
                f"Expedition log updated. {title}.",
                f"That is worth marking. {title}.",
            ), category="exploration", cooldown_s=5, key=f"milestone:{major.get('key')}")

    def _compass_gameplay_snapshot(self):
        """Return compact verified live facts for the local Compass brain."""
        def number(value, digits=1):
            try:
                return round(float(value), digits)
            except (TypeError, ValueError):
                return None

        memory = getattr(self, "cockpit_memory", None)
        state = getattr(self, "companion_state", {}) or {}
        current_system = getattr(self, "current_sys", None)
        route = list(getattr(self, "route_list", None) or [])
        route_index = next(
            (idx for idx, name in enumerate(route)
             if str(name).casefold() == str(current_system).casefold()),
            -1,
        )
        route_remaining = (
            max(0, len(route) - route_index - 1) if route_index >= 0 else len(route)
        )
        next_system = (
            route[route_index + 1] if 0 <= route_index < len(route) - 1
            else (route[0] if route and route_index < 0 else None)
        )

        fuel_main = getattr(self, "current_fuel_main", None)
        fuel_capacity = getattr(self, "fuel_capacity_main", None)
        fuel_percent = None
        try:
            if fuel_capacity and float(fuel_capacity) > 0 and fuel_main is not None:
                fuel_percent = round(float(fuel_main) * 100 / float(fuel_capacity))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        cargo_tons = int(getattr(self, "current_cargo_tons", 0) or 0)
        cargo_capacity = int(getattr(self, "cargo_capacity", 0) or 0)
        cargo_percent = round(cargo_tons * 100 / cargo_capacity) if cargo_capacity else None

        missions = state.get("missions") or {}
        mission_rows = list(missions.values()) if isinstance(missions, dict) else list(missions)
        mission_destinations = []
        for mission in mission_rows:
            if not isinstance(mission, dict):
                continue
            system = mission.get("destination_system")
            station = mission.get("destination_station")
            if system and not any(row.get("system") == system for row in mission_destinations):
                mission_destinations.append({"system": system, "station": station})

        valuable_names = []
        for row in getattr(self, "valuable_bodies", None) or ():
            parts = str(row).split(" ", 2)
            valuable_names.append(parts[2] if len(parts) == 3 else str(row).lstrip("- "))

        unsold_exploration = int(state.get("unsold_exploration_cr") or 0)
        unsold_biology = int(state.get("unsold_bio_cr") or 0)
        unsold_biology_potential = int(state.get("unsold_bio_bonus_potential_cr") or 0)
        trade = getattr(self, "trade_session", {}) or {}
        mining = self._compass_mining_snapshot(mission_rows)
        trade_context = self._compass_trade_snapshot()
        statistics = state.get("statistics") or {}
        combat_stats = statistics.get("Combat") or statistics.get("combat") or {}
        combat_lifetime = {
            "bounties_claimed": int(combat_stats.get("Bounties_Claimed") or 0),
            "bounty_profit_cr": int(combat_stats.get("Bounty_Hunting_Profit") or 0),
            "combat_bonds": int(combat_stats.get("Combat_Bonds") or 0),
            "combat_bond_profit_cr": int(combat_stats.get("Combat_Bond_Profits") or 0),
            "assassinations": int(combat_stats.get("Assassinations") or 0),
            "assassination_profit_cr": int(combat_stats.get("Assassination_Profits") or 0),
            "highest_reward_cr": int(combat_stats.get("Highest_Single_Reward") or 0),
            "conflict_zones": int(combat_stats.get("ConflictZone_Total") or 0),
            "conflict_zone_wins": int(combat_stats.get("ConflictZone_Total_Wins") or 0),
            "on_foot_combat_bonds": int(combat_stats.get("OnFoot_Combat_Bonds") or 0),
            "on_foot_combat_profit_cr": int(combat_stats.get("OnFoot_Combat_Bonds_Profits") or 0),
        }
        combat_tracker = getattr(self, "combat_awareness", None)
        combat = combat_tracker.snapshot(
            massacre_stacks=companion_features.massacre_stacks(state),
            lifetime=combat_lifetime,
        ) if combat_tracker else {}
        powerplay_state = state.get("powerplay") or {}
        powerplay_system = state.get("pp_system") or {}
        collected = dict(powerplay_state.get("commodities_collected") or {})
        delivered = dict(powerplay_state.get("commodities_delivered") or {})
        outstanding = {
            name: max(0, int(count or 0) - int(delivered.get(name) or 0))
            for name, count in collected.items()
            if max(0, int(count or 0) - int(delivered.get(name) or 0))
        }
        pledged_power = powerplay_state.get("power")
        controlling_power = powerplay_system.get("controlling")
        powers_present = list(powerplay_system.get("powers") or [])
        powerplay = {
            "pledged": bool(pledged_power),
            "power": pledged_power,
            "rank": powerplay_state.get("rank"),
            "merits": int(powerplay_state.get("merits") or 0),
            "time_pledged_s": int(powerplay_state.get("time_pledged_s") or 0),
            "session_merits": int(powerplay_state.get("session_merits") or 0),
            "session_collected": int(powerplay_state.get("session_collected") or 0),
            "session_delivered": int(powerplay_state.get("session_delivered") or 0),
            "session_fast_track_cr": int(powerplay_state.get("session_fast_track_cr") or 0),
            "session_salary_cr": int(powerplay_state.get("session_salary_cr") or 0),
            "commodities_collected": collected,
            "commodities_delivered": delivered,
            "outstanding": outstanding,
            "outstanding_units": sum(outstanding.values()),
            "last_action": dict(powerplay_state.get("last_action") or {}),
            "system": {
                "name": current_system,
                "controlling": controlling_power,
                "powers": powers_present,
                "state": powerplay_system.get("state"),
                "control_progress": powerplay_system.get("control_progress"),
                "reinforcement": powerplay_system.get("reinforcement"),
                "undermining": powerplay_system.get("undermining"),
                "contested": len(powers_present) > 1,
                "friendly_control": bool(
                    pledged_power and controlling_power
                    and str(pledged_power).casefold() == str(controlling_power).casefold()
                ),
                "pledged_power_present": bool(
                    pledged_power and (
                        str(pledged_power).casefold() == str(controlling_power).casefold()
                        or any(str(power).casefold() == str(pledged_power).casefold()
                               for power in powers_present)
                    )
                ),
            } if powerplay_system else None,
        }
        sample = self._sampling_snapshot() if getattr(self, "bio_sampling", None) else None
        snapshot = {
            "flight": {
                "state": getattr(self, "hud_flight_state", "FLIGHT"),
                "ship": (getattr(self, "cmdr_ship", {}) or {}).get("ship_name")
                        or (getattr(self, "cmdr_ship", {}) or {}).get("ship"),
                "fuel_percent": fuel_percent,
                "fuel_main_t": number(fuel_main),
                "fuel_capacity_t": number(fuel_capacity),
                "cargo_t": cargo_tons,
                "cargo_capacity_t": cargo_capacity,
                "cargo_percent": cargo_percent,
                "legal_state": getattr(self, "current_legal_state", None),
            },
            "navigation": {
                "current_system": current_system,
                "star_class": getattr(self, "star_class", None),
                "next_system": next_system,
                "final_destination": route[-1] if route else getattr(self, "dest_name", None),
                "remaining_jumps": route_remaining,
                "hud_destination": getattr(self, "current_destination", None),
            },
            "survey": {
                "scanned_bodies": int(getattr(self, "scanned", 0) or 0),
                "total_bodies": int(getattr(self, "total", 0) or 0),
                "system_undiscovered": bool(getattr(self, "system_undiscovered", False)),
                "valuable_bodies": valuable_names[:5],
                "biological_signals": int(getattr(self, "system_bio_signals", 0) or 0),
                "completed_biological_analyses": int(getattr(self, "organic_count", 0) or 0),
                "focused_body": getattr(self, "current_body_name", None),
            },
            "biology": dict(sample) if isinstance(sample, dict) else None,
            "objectives": {
                "active_missions": len(mission_rows),
                "mission_destinations": mission_destinations[:6],
                "unsold_exploration_cr": unsold_exploration,
                "unsold_biology_cr": unsold_biology,
                "unsold_biology_bonus_potential_cr": unsold_biology_potential,
                "unsold_data_total_cr": unsold_exploration + unsold_biology,
                "unsold_data_max_cr": (
                    unsold_exploration + unsold_biology + unsold_biology_potential
                ),
                "pinned_engineering": list(
                    (getattr(self, "engineer_materials", {}) or {}).get("pinned_blueprints") or []
                )[:5],
            },
            "station": {
                "name": getattr(self, "current_station_name", None),
                "services": list(getattr(self, "current_station_services", None) or [])[:20],
            } if getattr(self, "current_docked", False) else None,
            "traffic": {
                "day": int((getattr(self, "system_traffic", {}) or {}).get("day") or 0),
                "week": int((getattr(self, "system_traffic", {}) or {}).get("week") or 0),
                "total": int((getattr(self, "system_traffic", {}) or {}).get("total") or 0),
            },
            "mining": mining,
            "trade": trade_context,
            "combat": combat,
            "powerplay": powerplay,
            "session": {
                "jumps": int(getattr(self, "session_jump_count", 0) or 0),
                "distance_ly": number(getattr(self, "session_ly", 0)) or 0.0,
                "trade_profit_cr": int(trade.get("profit") or 0),
                "mined_units": int(mining.get("refined_tons") or 0),
            },
            "learned_gameplay": memory.gameplay_awareness() if memory else {},
            "exploration_intelligence": self._exploration_intelligence_snapshot(compact=True),
        }
        snapshot.update(compass_operations.build_snapshot(
            getattr(self, "ai_operational_state", None),
            companion_state=state,
            cargo_inventory=getattr(self, "current_cargo_inventory", None),
            engineer_materials=getattr(self, "engineer_materials", None),
            carrier_data=getattr(getattr(self, "carrier_tracker", None), "carrier_data", None),
            colonisation_projects=getattr(self, "colonisation_projects", None),
            current_system=current_system,
            legal_state=getattr(self, "current_legal_state", None),
        ))
        snapshot["objectives"]["active_missions"] = int(
            (snapshot.get("missions") or {}).get("active") or 0
        )
        active_destinations = []
        for mission in (snapshot.get("missions") or {}).get("rows") or []:
            system = mission.get("system") if isinstance(mission, dict) else None
            if system and not any(row.get("system") == system for row in active_destinations):
                active_destinations.append({
                    "system": system, "station": mission.get("station"),
                })
        snapshot["objectives"]["mission_destinations"] = active_destinations[:6]
        expedition_manager = getattr(self, "expedition_manager", None)
        if expedition_manager:
            next_waypoint = None
            try:
                next_waypoint = self.waypoint_manager.get_next_waypoint(current_system)
            except Exception:
                pass
            snapshot["expedition"] = expedition_manager.compass_snapshot(
                next_waypoint=next_waypoint,
            )
            if snapshot["expedition"].get("active"):
                snapshot["objectives"]["expedition"] = {
                    "name": snapshot["expedition"].get("name"),
                    "complete": snapshot["expedition"].get("objectives_complete"),
                    "total": snapshot["expedition"].get("objectives_total"),
                    "next": snapshot["expedition"].get("next_objective")
                            or snapshot["expedition"].get("next_waypoint"),
                }
        snapshot["fact_quality"] = self._compass_fact_quality(snapshot)
        return snapshot

    def _compass_fact_quality(self, snapshot=None):
        """Describe the age and confidence of facts used by Compass advice."""
        now = time.time()
        thresholds = {
            "journal": (30.0, 180.0, "last_journal_event_ts"),
            "status": (15.0, 60.0, "last_status_event_ts"),
            "navigation": (120.0, 600.0, "last_nav_event_ts"),
            "cargo": (180.0, 900.0, "last_cargo_event_ts"),
            "edsm": (300.0, 1800.0, "last_edsm_event_ts"),
        }
        sources = {}
        for name, (live_age, recent_age, attribute) in thresholds.items():
            observed_at = float(getattr(self, attribute, 0.0) or 0.0)
            age = max(0.0, now - observed_at) if observed_at else None
            if age is None:
                freshness, confidence = "unknown", 0.0
            elif age <= live_age:
                freshness, confidence = "live", 1.0
            elif age <= recent_age:
                freshness, confidence = "recent", 0.7
            else:
                freshness, confidence = "stale", 0.3
            sources[name] = {
                "freshness": freshness, "confidence": confidence,
                "age_seconds": round(age, 1) if age is not None else None,
                "observed_at": observed_at or None,
            }
        conflicts = []
        flight_state = str(
            ((snapshot or {}).get("flight") or {}).get("state")
            or getattr(self, "hud_flight_state", "") or ""
        ).upper()
        if getattr(self, "current_docked", False) and flight_state not in {"DOCKED", "ONFOOT"}:
            conflicts.append("docking-state")
        known = [row["confidence"] for row in sources.values() if row["freshness"] != "unknown"]
        return {
            "sources": sources,
            "overall": round(sum(known) / len(known), 2) if known else 0.0,
            "conflicts": conflicts,
            "updated_at": now,
        }

    @staticmethod
    def _new_mining_ai_session(previous=None):
        return {
            "active": False,
            "started_at": None,
            "system": None,
            "body": None,
            "prospected": 0,
            "cores_found": 0,
            "cores_cracked": 0,
            "refined_tons": 0,
            "refined_by_material": {},
            "best_material": None,
            "best_percent": 0.0,
            "last_materials": [],
            "limpets": None,
            "context_body": (previous or {}).get("context_body"),
            "last_summary": (previous or {}).get("last_summary"),
            "last_summary_pending": False,
        }

    @staticmethod
    def _journal_display_name(value, fallback="Commodity"):
        text = str(value or "").strip().strip("$;")
        if text.casefold().endswith("_name"):
            text = text[:-5]
        return text.replace("_", " ").strip().title() or fallback

    def _start_ai_mining_session(self):
        previous = getattr(self, "mining_ai_session", {}) or {}
        state = self._new_mining_ai_session(previous)
        state.update({
            "active": True,
            "started_at": time.time(),
            "system": getattr(self, "current_sys", None),
            "body": previous.get("context_body") or getattr(self, "current_body_name", None),
        })
        self.mining_ai_session = state
        return state

    def _finish_ai_mining_session(self, reason):
        state = getattr(self, "mining_ai_session", {}) or {}
        if not state.get("active"):
            return
        duration = max(0.0, time.time() - float(state.get("started_at") or time.time()))
        state["last_summary"] = {
            "reason": str(reason or "complete"),
            "system": state.get("system"),
            "body": state.get("body"),
            "duration_minutes": round(duration / 60.0, 1),
            "prospected": int(state.get("prospected") or 0),
            "cores_found": int(state.get("cores_found") or 0),
            "cores_cracked": int(state.get("cores_cracked") or 0),
            "refined_tons": int(state.get("refined_tons") or 0),
            "refined_by_material": dict(state.get("refined_by_material") or {}),
            "best_material": state.get("best_material"),
            "best_percent": float(state.get("best_percent") or 0),
        }
        state["last_summary_pending"] = True
        state["active"] = False
        state["context_body"] = None

    def _observe_ai_economy_event(self, event, raw, startup_replay=False):
        """Maintain panel-independent live mining facts for Compass."""
        if startup_replay or not isinstance(raw, dict):
            return
        state = getattr(self, "mining_ai_session", None)
        if not isinstance(state, dict):
            state = self._new_mining_ai_session()
            self.mining_ai_session = state

        if event == "LoadGame":
            self.mining_ai_session = self._new_mining_ai_session()
            return

        if event == "SAASignalsFound" and "ring" in str(raw.get("BodyName") or "").casefold():
            state["context_body"] = raw.get("BodyName")
        if event in ("ProspectedAsteroid", "MiningRefined", "AsteroidCracked") and not state.get("active"):
            state = self._start_ai_mining_session()

        if event == "ProspectedAsteroid":
            state["prospected"] = int(state.get("prospected") or 0) + 1
            state["last_core"] = None
            core = raw.get("MotherlodeMaterial_Localised") or raw.get("MotherlodeMaterial")
            if core:
                state["cores_found"] = int(state.get("cores_found") or 0) + 1
            materials = []
            for item in raw.get("Materials") or ():
                if not isinstance(item, dict):
                    continue
                name = self._journal_display_name(item.get("Name_Localised") or item.get("Name"), "Mineral")
                try:
                    percent = float(item.get("Proportion") if item.get("Proportion") is not None else item.get("Percent") or 0)
                except (TypeError, ValueError):
                    percent = 0.0
                if percent <= 1 and item.get("Proportion") is not None:
                    percent *= 100.0
                materials.append({"name": name, "percent": round(percent, 1)})
                if percent > float(state.get("best_percent") or 0):
                    state["best_percent"] = round(percent, 1)
                    state["best_material"] = name
            state["last_materials"] = sorted(materials, key=lambda row: row["percent"], reverse=True)[:5]
            if core:
                state["last_core"] = self._journal_display_name(core, "Core material")
        elif event == "AsteroidCracked":
            state["cores_cracked"] = int(state.get("cores_cracked") or 0) + 1
        elif event == "MiningRefined":
            material = self._journal_display_name(raw.get("Type_Localised") or raw.get("Type"), "Mineral")
            state["refined_tons"] = int(state.get("refined_tons") or 0) + 1
            refined = state.setdefault("refined_by_material", {})
            refined[material] = int(refined.get(material) or 0) + 1
        elif event == "Cargo":
            inventory = raw.get("Inventory") or ()
            if isinstance(inventory, list):
                state["limpets"] = sum(
                    int(item.get("Count") or 0) for item in inventory if isinstance(item, dict)
                    and "limpet" in str(item.get("Name_Localised") or item.get("Name") or "").casefold()
                )
        elif event in ("FSDJump", "CarrierJump", "Shutdown"):
            self._finish_ai_mining_session(event)

    def _compass_mining_snapshot(self, mission_rows):
        state = dict(getattr(self, "mining_ai_session", {}) or {})
        limpets = state.get("limpets")
        if limpets is None:
            inventory = list(getattr(self, "current_cargo_inventory", None) or ())
            if inventory or float(getattr(self, "last_cargo_event_ts", 0) or 0) > 0:
                limpets = sum(
                    int(item.get("Count", item.get("count", 0)) or 0)
                    for item in inventory if isinstance(item, dict)
                    and "limpet" in str(item.get("Name_Localised") or item.get("Name") or item.get("name") or "").casefold()
                )
        mining_names = {name.casefold() for name in MINING_MATERIALS}
        mining_missions = []
        for mission in mission_rows:
            if not isinstance(mission, dict):
                continue
            internal = str(mission.get("internal_name") or mission.get("name") or "")
            commodity = str(mission.get("commodity") or mission.get("commodity_symbol") or "")
            if "mining" not in internal.casefold() and commodity.casefold() not in mining_names:
                continue
            required = int(mission.get("to_deliver") or mission.get("count") or 0)
            delivered = int(mission.get("delivered") or 0)
            mining_missions.append({
                "commodity": commodity or "Mining commodity",
                "required": required,
                "delivered": delivered,
                "remaining": max(0, required - delivered),
                "destination": mission.get("destination_station") or mission.get("destination_system"),
            })
        started = state.get("started_at")
        duration_hours = max((time.time() - float(started or time.time())) / 3600.0, 1 / 3600.0)
        refined = int(state.get("refined_tons") or 0)
        return {
            "active": bool(state.get("active")),
            "system": state.get("system"),
            "body": state.get("body"),
            "duration_minutes": round(duration_hours * 60, 1) if state.get("active") else 0.0,
            "prospected": int(state.get("prospected") or 0),
            "cores_found": int(state.get("cores_found") or 0),
            "cores_cracked": int(state.get("cores_cracked") or 0),
            "refined_tons": refined,
            "yield_tph": round(refined / duration_hours, 1) if state.get("active") and refined else 0.0,
            "refined_by_material": dict(state.get("refined_by_material") or {}),
            "best_material": state.get("best_material"),
            "best_percent": float(state.get("best_percent") or 0),
            "last_materials": list(state.get("last_materials") or []),
            "last_core": state.get("last_core"),
            "limpets": int(limpets) if limpets is not None else None,
            "missions": mining_missions[:6],
            "last_summary": state.get("last_summary") if state.get("last_summary_pending") else None,
        }

    def _compass_trade_snapshot(self):
        trade = getattr(self, "trade_session", {}) or {}
        events = list(trade.get("events") or [])
        plan = dict(getattr(self, "trade_plan_context", None) or {}) or None
        if plan and time.time() - float(plan.get("_created_at") or time.time()) > 21600:
            self.trade_plan_context = None
            plan = None
        return {
            "transactions": int(trade.get("transactions") or len(events)),
            "bought_units": int(trade.get("bought_units") or 0),
            "sold_units": int(trade.get("sold_units") or 0),
            "spent_cr": int(trade.get("spent") or 0),
            "revenue_cr": int(trade.get("earned") or 0),
            "profit_cr": int(trade.get("profit") or 0),
            "commodities_bought": dict(trade.get("commodities_bought") or {}),
            "commodities_sold": dict(trade.get("commodities_sold") or {}),
            "best_sale": trade.get("best_sale"),
            "worst_sale": trade.get("worst_sale"),
            "last_transaction": dict(events[-1]) if events else None,
            "plan": plan,
        }

    def _set_compass_trade_plan(self, plan):
        """Share a verified Trade Command result with the working brain."""
        self.trade_plan_context = dict(plan or {}) or None
        if self.trade_plan_context:
            self.trade_plan_context["_created_at"] = time.time()
        self._refresh_cockpit_brain(
            purpose="trade-route",
            event=(
                f"trade-route:{self.trade_plan_context.get('kind') or 'plan'}"
                if self.trade_plan_context else "trade-route:cleared"
            ),
        )
        self._publish_cockpit_ai_changes()
        if self.trade_plan_context:
            self._pulse_cockpit_ai()

    def _refresh_cockpit_brain(self, purpose=None, event=None, gameplay=None):
        """Persist and return Compass's compact verified working state."""
        memory = getattr(self, "cockpit_memory", None)
        brain = getattr(self, "cockpit_brain", None)
        if not memory or not brain or not self.config.get("cockpit_memory_enabled", True):
            return {}
        try:
            return brain.update(
                memory,
                gameplay=(
                    gameplay if isinstance(gameplay, dict)
                    else self._compass_gameplay_snapshot()
                ),
                purpose=purpose,
                event=event,
                personality_level=self.config.get("cockpit_personality_level", "Balanced"),
                persona_name=self.config.get("cockpit_persona", "Compass"),
            )
        except Exception as exc:
            logging.debug("Cockpit working brain refresh skipped: %s", exc)
            return {}

    def _compass_advisor_intervals(self):
        level = str(self.config.get("cockpit_advisor_level", "Balanced")).casefold()
        return {
            "quiet": (900.0, 450.0),
            "proactive": (180.0, 90.0),
        }.get(level, (420.0, 210.0))

    def _compass_advisor_available(self, topic):
        if not self.config.get("cockpit_advisor_enabled", True):
            return False
        topic_gap, global_gap = self._compass_advisor_intervals()
        now = time.monotonic()
        last_topic = self._compass_advisor_last.get(topic)
        last_any = self._compass_advisor_last_any
        return (
            (last_topic is None or now - float(last_topic) >= topic_gap)
            and (not last_any or now - float(last_any) >= global_gap)
        )

    def _mark_compass_advisor(self, topic):
        if not topic:
            return
        now = time.monotonic()
        self._compass_advisor_last[topic] = now
        self._compass_advisor_last_any = now

    def _compass_advisory_point(self, snapshot, key):
        """Choose one learned, persona-weighted observation for an existing callout."""
        key_text = str(key or "")
        # A standalone adviser line has already passed cognitive selection.
        # Do not append a second observation or learn the same outcome twice.
        if key_text.startswith("advisor:"):
            return None
        cognition = getattr(self, "compass_cognition", None)
        memory = getattr(self, "cockpit_memory", None)
        if not cognition or not self._compass_advisor_available("contextual"):
            return None
        event = "FSDJump" if key_text.startswith((
            "system-arrival:", "route-arrival:", "route-waypoint:"
        )) else "callout"
        candidate = cognition.select(
            event, {}, snapshot, memory=memory, key=key, existing=True,
        )
        if candidate and not self._compass_advisor_available(candidate.get("topic")):
            return None
        return candidate

    def _speak(self, text, category="safety", cooldown_s=20, key=None):
        if getattr(self, "_closing", False):
            return False
        try:
            if (self.config.get("cockpit_memory_enabled", True)
                    and getattr(self, "cockpit_memory", None)):
                text = self.cockpit_memory.voice_pool(
                    text, key=key,
                    personality_level=self.config.get("cockpit_personality_level", "Balanced"),
                )
            text = choose_line(text, key=key)
            advice = None
            if (
                category in ("navigation", "exploration", "objectives", "ambient")
                and self.config.get("voice_callouts_enabled", False)
                and self.voice_callouts.can_say(category)
            ):
                advice = self._compass_advisory_point(
                    self._compass_gameplay_snapshot(), key,
                )
                if advice:
                    text = (
                        f"{str(text).rstrip('.!')}; "
                        f"{str(advice['line']).rstrip('.!')}."
                    )
            if category != "safety":
                text = compass_personas.style_line(
                    text, self.config.get("cockpit_persona", "Compass"), key=key,
                )
            spoken = self.voice_callouts.say(text, category=category, cooldown_s=cooldown_s, key=key)
            if spoken:
                if advice:
                    self._mark_compass_advisor(advice["topic"])
                    self.compass_cognition.record_spoken(advice, line=text)
                self._pulse_cockpit_ai()
            return spoken
        except Exception as exc:
            logging.debug("Voice callout skipped: %s", exc)
            return False

    def _speak_pending_cockpit_remark(self, force=False):
        if (not self.config.get("cockpit_memory_enabled", True)
                or not getattr(self, "cockpit_memory", None)):
            return False
        remark = self.cockpit_memory.pop_remark(
            self.config.get("cockpit_personality_level", "Balanced"), force=force,
        )
        if not remark:
            return False
        return self._speak(
            remark["lines"], category=remark["category"], cooldown_s=30,
            key=f"cockpit-context:{remark['topic']}",
        )

    def _maybe_speak_compass_advice(self, event, raw, data, startup_replay=False,
                                    snapshot=None):
        """Speak the highest-utility learned observation, or intentionally stay quiet."""
        cognition = getattr(self, "compass_cognition", None)
        if (startup_replay or getattr(self, "is_first_load", False) or not cognition
                or not self.config.get("cockpit_advisor_enabled", True)):
            return False
        snapshot = snapshot if isinstance(snapshot, dict) else self._compass_gameplay_snapshot()
        candidate = cognition.select(
            event, raw if isinstance(raw, dict) else data, snapshot,
            memory=getattr(self, "cockpit_memory", None),
        )
        if not candidate or not self._compass_advisor_available(candidate.get("topic")):
            return False
        key = f"advisor:{candidate['topic']}"
        spoken = self._speak(
            candidate["line"], category=candidate.get("category", "objectives"),
            cooldown_s=0, key=key,
        )
        if spoken:
            cognition.record_spoken(candidate, line=candidate["line"])
            self._mark_compass_advisor(candidate["topic"])
        return bool(spoken)

    def _process_compass_cognition(self, event, raw, data, startup_replay=False,
                                   snapshot=None):
        """Learn from the settled event state, publish sparse insights, then advise."""
        cognition = getattr(self, "compass_cognition", None)
        if not cognition or startup_replay:
            return False
        try:
            snapshot = snapshot if isinstance(snapshot, dict) else self._compass_gameplay_snapshot()
            notices = cognition.observe(
                event, snapshot, memory=getattr(self, "cockpit_memory", None),
                raw=raw, startup_replay=startup_replay,
            )
            self._publish_cockpit_ai_changes()
            for notice in notices:
                self.add_event_feed_entry("AI", notice, severity="INFO")
            if notices:
                self._pulse_cockpit_ai()
            spoken = self._maybe_speak_compass_advice(
                event, raw, data, startup_replay=startup_replay,
                snapshot=snapshot,
            )
            if event in ("FSDJump", "CarrierJump", "Shutdown"):
                mining_state = getattr(self, "mining_ai_session", {}) or {}
                mining_state["last_summary_pending"] = False
            if event in ("EscapeInterdiction", "StartJump", "FSDJump", "CarrierJump", "Docked", "Died", "Shutdown"):
                combat_tracker = getattr(self, "combat_awareness", None)
                if combat_tracker:
                    combat_tracker.consume_summary()
            return spoken
        except Exception as exc:
            logging.debug("Compass cognition event skipped [%s]: %s", event, exc)
            return False

    def _adaptive_health_snapshot(self):
        dispatch = self.ui_dispatcher.stats() if getattr(self, "ui_dispatcher", None) else {}
        persistence = persistence_queue().stats()
        journal_age = max(0.0, time.time() - float(self.last_journal_event_ts or 0.0)) \
            if self.last_journal_event_ts else None
        recent_stall = (
            time.time() - float(getattr(self, "_last_ui_stall_ts", 0.0) or 0.0)
        ) < 60.0
        stall_age = (
            max(0.0, time.time() - float(getattr(self, "_last_ui_stall_ts", 0.0)))
            if getattr(self, "_last_ui_stall_ts", 0.0) else None
        )
        if persistence.get("failures") or dispatch.get("failures"):
            level = "FAULT"
        elif recent_stall or dispatch.get("pending", 0) > 24 or persistence.get("pending", 0) > 5:
            level = "BUSY"
        else:
            level = "NOMINAL"
        return {
            "level": level,
            "ui_pending": int(dispatch.get("pending") or 0),
            "ui_max_lag_ms": float(dispatch.get("max_lag_ms") or 0.0),
            "writes_pending": int(persistence.get("pending") or 0),
            "last_write_ms": float(persistence.get("last_write_ms") or 0.0),
            "journal_age_s": round(journal_age, 1) if journal_age is not None else None,
            "last_ui_stall_age_s": round(stall_age, 1) if stall_age is not None else None,
            "ui": dispatch,
            "persistence": persistence,
        }

    @staticmethod
    def _overlay_window(instance):
        if instance is None:
            return None
        return getattr(instance, "win", instance)

    def _apply_adaptive_overlay_scene(self, mode=None):
        deck = getattr(self, "adaptive_command", None)
        if not deck:
            return
        hidden = getattr(self, "_adaptive_hidden_overlays", set())
        if (
            not self.config.get("adaptive_overlay_scenes_enabled", True)
            or not self.config.get("adaptive_command_enabled", True)
        ):
            for attr in tuple(hidden):
                window = self._overlay_window(getattr(self, attr, None))
                try:
                    if window is not None:
                        window.deiconify()
                except (AttributeError, tk.TclError):
                    pass
            self._adaptive_hidden_overlays = set()
            self._enforce_overlay_hotkey_visibility()
            return
        scene = deck.scene(mode)
        persistent = {"hud", "cargo_hud", "carrier_hud", "colony_overlay"}
        for attr, visible in scene.items():
            instance = getattr(self, attr, None)
            window = self._overlay_window(instance)
            if window is None:
                continue
            try:
                if not visible:
                    window.withdraw()
                    hidden.add(attr)
                elif attr in hidden:
                    hidden.discard(attr)
                    if attr in persistent:
                        window.deiconify()
            except (AttributeError, tk.TclError):
                pass
        self._adaptive_hidden_overlays = hidden
        # Safety feedback is never suppressed by an activity scene.
        for attr in ("toast_hud", "gravity_warning_hud", "heartbeat_hud"):
            hidden.discard(attr)
        self._enforce_overlay_hotkey_visibility()

    def _update_adaptive_command(self, event, raw, startup_replay=False):
        deck = getattr(self, "adaptive_command", None)
        if not deck or startup_replay:
            return
        if event == "Shutdown":
            summary = deck.close_session("Session complete")
            if summary and self.config.get("adaptive_debriefings_enabled", True):
                self.add_event_feed_entry("AI", summary, severity="INFO")
                # The established Compass shutdown summary owns TTS for this
                # boundary, avoiding two spoken debriefs for the same event.
            return
        detected = self._detected_adaptive_mode()
        transition = deck.observe(event, detected, raw, historical=False)
        if not transition.get("changed"):
            return
        mode = transition.get("mode") or "general"
        self._apply_adaptive_overlay_scene(mode)
        if transition.get("debrief") and self.config.get("adaptive_debriefings_enabled", True):
            self.add_event_feed_entry("AI", transition["debrief"], severity="INFO")
        briefing = transition.get("briefing")
        if briefing and self.config.get("adaptive_briefings_enabled", True):
            self.add_event_feed_entry(
                "AI", f"Command Deck: {briefing}", severity="INFO",
            )
            self._speak(
                briefing, category="objectives", cooldown_s=0,
                key=f"adaptive-mode:{mode}",
            )
        self.schedule_dashboard_refresh(full=True)

    def _adaptive_startup_briefing(self):
        if getattr(self, "_adaptive_startup_briefed", False):
            return
        self._adaptive_startup_briefed = True
        deck = getattr(self, "adaptive_command", None)
        if not deck or not self.config.get("adaptive_command_enabled", True):
            return
        detected = self._detected_adaptive_mode()
        if detected:
            deck.observe("StartupReady", detected, {}, historical=False)
        mode = deck.current_mode
        self._apply_adaptive_overlay_scene(mode)
        briefing = deck.briefing(mode)
        if self.config.get("adaptive_briefings_enabled", True):
            self.add_event_feed_entry(
                "AI", f"Command Deck ready: {briefing}", severity="INFO",
            )
            self._speak(
                briefing, category="objectives", cooldown_s=0,
                key=f"adaptive-startup:{mode}",
            )

    def _detected_adaptive_mode(self):
        """Return live activity, aging stale automatic evidence to general flight."""
        activity = (
            (getattr(self, "ai_operational_state", {}) or {}).get("activity") or {}
        )
        mode = activity.get("mode") or "general"
        observed_at = float(activity.get("last_event_at") or activity.get("since") or 0)
        if (
            mode != "general" and observed_at
            and time.time() - observed_at > AUTOMATIC_MODE_IDLE_S
        ):
            return "general"
        return mode

    def _adaptive_context(self, route_progress=None):
        route_progress = route_progress or self._current_route_progress()
        pinned = (getattr(self, "engineer_materials", {}) or {}).get("pinned_blueprints") or []
        return {
            "current_system": getattr(self, "current_sys", None),
            "survey_remaining": max(
                0, int(getattr(self, "total", 0) or 0) - int(getattr(self, "scanned", 0) or 0),
            ),
            "next_destination": self._dashboard_next_destination(),
            "route_text": route_progress.get("text"),
            "engineering_goals": list(pinned),
        }

    def _adaptive_toggle_lock(self):
        deck = getattr(self, "adaptive_command", None)
        if not deck:
            return
        self._adaptive_select_mode(deck.current_mode if deck.automatic else "auto")

    def _adaptive_select_mode(self, selected_mode):
        """Apply a manual Dashboard mode, or resynchronise Automatic immediately."""
        deck = getattr(self, "adaptive_command", None)
        if not deck:
            return
        selected_mode = str(selected_mode or "auto")
        mode = deck.set_lock(selected_mode)
        if selected_mode == "auto":
            detected = self._detected_adaptive_mode()
            deck.observe("ManualModeAuto", detected, {}, historical=False)
            mode = deck.current_mode
        self._persist_config()
        self._apply_adaptive_overlay_scene(mode)
        if deck.automatic:
            message = f"Command Deck returned to Automatic · {MODE_LABELS.get(mode, mode).title()} detected"
        else:
            message = f"Command Deck manually locked to {MODE_LABELS.get(mode, mode).title()}"
        self.add_event_feed_entry("SYSTEM", message, severity="INFO")
        self.schedule_dashboard_refresh(full=True)

    def _adaptive_open_primary(self):
        rows = getattr(self, "_operational_queue", None) or []
        if not rows:
            return False
        row = rows[0]
        section = None
        if row.get("id") == "mining":
            section = "mining"
        return self._adaptive_open_workspace(row.get("workspace"), section=section)

    def _adaptive_open_workspace(self, workspace, section=None):
        """Open one Command Deck destination with tracing and visible failures."""
        workspace = str(workspace or "").strip().upper()
        actions = {
            "DASHBOARD": self.show_dashboard_page,
            "PROFILE": self.open_commander_profile_window,
            "EXPLORE": lambda: self.open_exploration_window(section=section),
            "TRADE": self.open_trade_window,
            "SPECIALISTS": lambda: self.open_specialists_window(section=section),
            "CARRIER": self.open_carrier_window,
            "COLONY": self.open_colonization_window,
            "ENGINEER": self.open_engineer_window,
            "GROUND": self.open_ground_target_window,
            "GALAXY": self.open_bgs_window,
        }
        callback = actions.get(workspace)
        if callback is None:
            self.log(f"Command Deck has no workspace route for: {workspace or 'UNKNOWN'}")
            return False
        try:
            self._run_nav_command(f"mode-{workspace.lower()}", callback)
            return True
        except Exception as exc:
            self.log(f"Command Deck could not open {workspace}: {exc}")
            self.add_event_feed_entry(
                "SYSTEM", f"Command Deck could not open {workspace}: {exc}", severity="WARN",
            )
            return False

    def _adaptive_open_mode_workspace(self):
        deck = getattr(self, "adaptive_command", None)
        if not deck:
            return False
        status = deck.status()
        mode = str(status.get("mode") or "general")
        workspace = status.get("workspace")
        section = {
            "exploration": "survey",
            "mining": "mining",
            "combat": "combat",
        }.get(mode)

        # General and station activity deliberately live on Dashboard. When a
        # real objective exists, take the commander there instead of visibly
        # reopening the page that owns this button.
        if workspace == "DASHBOARD":
            rows = getattr(self, "_operational_queue", None) or []
            row = next(
                (item for item in rows if item.get("workspace") != "DASHBOARD"),
                None,
            )
            if row:
                row_section = "mining" if row.get("id") == "mining" else None
                return self._adaptive_open_workspace(
                    row.get("workspace"), section=row_section,
                )
            if hasattr(self, "dashboard_mode_detail"):
                self.dashboard_mode_detail.config(
                    text=f"{status.get('label') or 'GENERAL FLIGHT'} uses this Dashboard · no queued task to open"
                )
            return False

        return self._adaptive_open_workspace(workspace, section=section)

    def _sync_cockpit_intentions(self, snapshot=None):
        if (not self.config.get("cockpit_memory_enabled", True)
                or not getattr(self, "cockpit_memory", None)):
            return
        state = getattr(self, "companion_state", {}) or {}
        snapshot = snapshot if isinstance(snapshot, dict) else self._compass_gameplay_snapshot()
        intentions = {}
        route = list(getattr(self, "route_list", None) or [])
        if route:
            intentions["route"] = {
                "destination": route[-1],
                "remaining_systems": sum(
                    1 for name in route if str(name).casefold() != str(self.current_sys).casefold()
                ),
            }
        unsold = int(state.get("unsold_exploration_cr") or 0) + int(state.get("unsold_bio_cr") or 0)
        if unsold:
            intentions["unsold_data_cr"] = unsold
        sample = self._sampling_snapshot()
        if sample and str(getattr(self, "hud_flight_state", "")).upper() != "HYPERSPACE":
            intentions["biological_sampling"] = {
                "species": sample.get("species"), "progress": sample.get("progress"),
            }
        missions = snapshot.get("missions") or {}
        if int(missions.get("active") or 0):
            intentions["active_missions"] = {
                "count": int(missions.get("active") or 0),
                "urgent": len(missions.get("urgent") or []),
                "destinations": list(missions.get("grouped_destinations") or [])[:4],
            }
        pinned = (getattr(self, "engineer_materials", {}) or {}).get("pinned_blueprints") or []
        if pinned:
            intentions["engineering"] = [
                {"blueprint": row.get("name"),
                 "grade": row.get("target_grade", row.get("grade", 5)),
                 "quantity": row.get("quantity", 1)}
                for row in pinned[:5] if row.get("name")
            ]
        activity = snapshot.get("activity") or {}
        if activity.get("mode") and activity.get("mode") != "general":
            intentions["activity"] = {
                "mode": activity.get("mode"),
                "since": activity.get("since"),
            }
        rescue = snapshot.get("rescue_legal") or {}
        if int(rescue.get("rescue_units") or 0):
            intentions["rescue_cargo"] = int(rescue.get("rescue_units") or 0)
        if int(rescue.get("stolen_units") or 0):
            intentions["legal_cargo"] = int(rescue.get("stolen_units") or 0)
        trade_plan = (snapshot.get("trade") or {}).get("plan")
        if trade_plan:
            intentions["trade_plan"] = {
                key: trade_plan.get(key)
                for key in ("kind", "from_station", "to_station", "commodity")
                if trade_plan.get(key) is not None
            }
        strategy = snapshot.get("strategy") or {}
        carrier = strategy.get("carrier") or {}
        if carrier.get("jump_destination"):
            intentions["carrier_jump"] = carrier.get("jump_destination")
        matched = list(strategy.get("colonisation_matching_cargo") or [])
        if matched:
            intentions["colonisation_cargo_t"] = sum(
                int(row.get("aboard") or 0) for row in matched if isinstance(row, dict)
            )
        self.cockpit_memory.update_intentions(intentions)

    def _cockpit_ai_feed_snapshot(self):
        memory = getattr(self, "cockpit_memory", None)
        if not memory:
            return None
        mood = memory.current_mood()
        biology = memory.biology_awareness()
        cognition = (
            self.compass_cognition.status()
            if getattr(self, "compass_cognition", None) else {}
        )
        active = memory.state.get("active_expedition")
        return {
            "mood": str(mood.get("name") or "calm"),
            "mood_reason": str(mood.get("reason") or "systems nominal"),
            "voice_stage": memory.voice_stage(
                self.config.get("cockpit_personality_level", "Balanced")
            ),
            "persona": str(self.config.get("cockpit_persona") or "Compass"),
            "habits": tuple(memory.habits()),
            "systems": len(memory.state.get("systems", {})),
            "species": len(memory.state.get("species", {})),
            "ships": len(memory.state.get("ships", {})),
            "memories": len(memory.state.get("memories", [])),
            "honks": memory.count("system_honks"),
            "fss_completed": memory.count("fss_systems_completed"),
            "dss_maps": memory.count("dss_maps_completed"),
            "signal_bodies": memory.count("signal_bodies_found"),
            "bio_genera": biology["genera"],
            "bio_samples": biology["samples"],
            "bio_analyses": biology["analyses"],
            "bio_codex": biology["codex_entries"],
            "cognition_decisions": int(cognition.get("decisions") or 0),
            "cognition_predictions": len(cognition.get("predictions") or []),
            "cognition_goals": len(cognition.get("goals") or []),
            "cognition_learned_topics": len(cognition.get("learned_topics") or []),
            "awareness_domains": tuple(memory.knowledge_domains()),
            "limits": dict(memory.limits),
            "expedition_id": active.get("id") if isinstance(active, dict) else None,
            "expedition_name": active.get("name") if isinstance(active, dict) else None,
            "expedition_jumps": int(active.get("jumps") or 0) if isinstance(active, dict) else 0,
        }

    @classmethod
    def _cockpit_ai_state_events(cls, before, after):
        """Return sparse, meaningful feed messages for Compass state transitions."""
        if not before or not after:
            return []
        messages = []
        if after["mood"] != before["mood"]:
            messages.append(
                f"Mood changed: {after['mood'].title()} - {after['mood_reason']}"
            )
        if after["voice_stage"] != before["voice_stage"]:
            messages.append(
                f"Relationship evolved: {after['voice_stage'].title()} flight companion"
            )
        if after.get("persona") != before.get("persona"):
            messages.append(f"Persona selected: {after.get('persona') or 'Compass'}")
        learned = [habit for habit in after["habits"] if habit not in before["habits"]]
        if learned:
            messages.append(f"Learned flight habit: {', '.join(learned)}")
        new_domains = [
            domain for domain in after.get("awareness_domains", ())
            if domain not in before.get("awareness_domains", ())
        ]
        if new_domains:
            messages.append(f"New operational awareness: {', '.join(new_domains)}")

        growth = []
        for key, label in (("systems", "systems"), ("species", "species"), ("memories", "notable memories")):
            old_count = int(before.get(key) or 0)
            new_count = int(after.get(key) or 0)
            milestones = set(cls._COCKPIT_BRAIN_MILESTONES[key])
            limit = int((after.get("limits") or {}).get(key) or 0)
            if limit:
                milestones.add(limit)
            if any(old_count < mark <= new_count for mark in milestones):
                suffix = f"/{limit}" if limit else ""
                growth.append(f"{new_count:,}{suffix} {label}")
        if growth:
            messages.append(f"Memory growth: {' | '.join(growth)}")

        survey_growth = []
        for key, label, milestones in (
            ("honks", "system honks", (25, 100, 250, 500, 1000, 5000)),
            ("fss_completed", "full FSS surveys", (10, 25, 50, 100, 250, 500, 1000)),
            ("dss_maps", "DSS maps", (10, 25, 50, 100, 250, 500, 1000, 5000)),
            ("signal_bodies", "signal-bearing bodies", (10, 25, 50, 100, 250, 500, 1000)),
        ):
            old_count = int(before.get(key) or 0)
            new_count = int(after.get(key) or 0)
            if any(old_count < mark <= new_count for mark in milestones):
                survey_growth.append(f"{new_count:,} {label}")
        if survey_growth:
            messages.append(f"Survey awareness: {' | '.join(survey_growth)}")

        biology_growth = []
        for key, label, milestones in (
            ("bio_genera", "genera", (5, 10, 15, 20, 25)),
            ("bio_samples", "samples", (25, 100, 250, 500, 1000, 2500)),
            ("bio_analyses", "analyses", (10, 25, 50, 100, 250, 500, 1000)),
            ("bio_codex", "biological Codex entries", (10, 25, 50, 100, 250, 500)),
        ):
            old_count = int(before.get(key) or 0)
            new_count = int(after.get(key) or 0)
            if any(old_count < mark <= new_count for mark in milestones):
                biology_growth.append(f"{new_count:,} {label}")
        if biology_growth:
            messages.append(f"Biology awareness: {' | '.join(biology_growth)}")

        old_expedition = before.get("expedition_id")
        new_expedition = after.get("expedition_id")
        if new_expedition and new_expedition != old_expedition:
            messages.append(f"Expedition log opened: {after['expedition_name']}")
        elif old_expedition and not new_expedition:
            messages.append(f"Expedition archived: {before.get('expedition_name') or 'journey complete'}")
        elif new_expedition == old_expedition and new_expedition:
            old_jumps = int(before.get("expedition_jumps") or 0)
            new_jumps = int(after.get("expedition_jumps") or 0)
            if any(old_jumps < mark <= new_jumps for mark in (50, 100, 250, 500, 1000)):
                messages.append(
                    f"Expedition milestone: {after['expedition_name']} reached {new_jumps:,} jumps"
                )
        return messages

    def _publish_cockpit_ai_online(self):
        if not self.config.get("cockpit_memory_enabled", True):
            self._cockpit_feed_state = None
            return
        snapshot = self._cockpit_ai_feed_snapshot()
        self._cockpit_feed_state = snapshot
        if not snapshot:
            return
        limits = snapshot["limits"]
        self.add_event_feed_entry(
            "AI",
            (
                f"Compass online: {snapshot['voice_stage'].title()} | mood {snapshot['mood']} | "
                f"persona {snapshot['persona']} | "
                f"memory {snapshot['systems']:,}/{limits['systems']:,} systems, "
                f"{snapshot['species']:,}/{limits['species']:,} species, "
                f"{snapshot['memories']:,}/{limits['memories']:,} notable | "
                f"survey {snapshot['fss_completed']:,} FSS, {snapshot['dss_maps']:,} DSS | "
                f"biology {snapshot['bio_genera']:,} genera, {snapshot['bio_analyses']:,} analyses | "
                f"{len(snapshot['awareness_domains'])} gameplay domains | "
                f"cognition {snapshot['cognition_predictions']} predictions, "
                f"{snapshot['cognition_goals']} priorities | working brain ready"
            ),
            severity="INFO",
        )

    def _publish_cockpit_ai_changes(self):
        after = self._cockpit_ai_feed_snapshot()
        before = getattr(self, "_cockpit_feed_state", None)
        self._cockpit_feed_state = after
        for message in self._cockpit_ai_state_events(before, after):
            self.add_event_feed_entry("AI", message, severity="INFO")

    def _publish_expedition_resume_briefing(self):
        manager = getattr(self, "expedition_manager", None)
        if not manager:
            return False
        next_waypoint = None
        try:
            next_waypoint = self.waypoint_manager.get_next_waypoint(getattr(self, "current_sys", None))
        except Exception:
            pass
        snapshot = manager.compass_snapshot(next_waypoint=next_waypoint)
        if not snapshot.get("active"):
            return False
        brief_key = f"{snapshot.get('id')}:{snapshot.get('sessions')}"
        if getattr(self, "_expedition_resume_brief_key", None) == brief_key:
            return False
        self._expedition_resume_brief_key = brief_key
        line = manager.resume_briefing(next_waypoint=next_waypoint)
        if not line:
            return False
        self.add_event_feed_entry("EXPEDITION", line, severity="INFO")
        self._speak(
            line,
            category="exploration", cooldown_s=0,
            key=f"expedition-resume:{snapshot.get('id')}:{snapshot.get('jumps')}",
        )
        return True

    def _handle_cockpit_load_game(self, raw, data, startup_replay=False):
        """Use LoadGame as the preferred session start, retaining automatic fallback."""
        memory = getattr(self, "cockpit_memory", None)
        if not memory or not self.config.get("cockpit_memory_enabled", True):
            return False
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else raw
        was_active = bool(memory.state.get("current_session"))
        current_system = getattr(self, "current_sys", None)
        system = (
            data.get("star_system") or raw.get("StarSystem")
            or (current_system if current_system not in (None, "---", "Unknown") else None)
        )
        ship = (
            data.get("ship_name") or raw.get("ShipName")
            or data.get("ship_localised") or raw.get("Ship_Localised")
            or data.get("ship") or raw.get("Ship")
        )
        previous_updated_at = memory.state.get("updated_at")
        session = memory.start_session(system, ship)
        if was_active or startup_replay:
            return False
        detail = "Flight session started"
        if ship:
            detail += f" aboard {ship}"
        if system:
            detail += f" in {system}"
        self.add_event_feed_entry("AI", detail, severity="INFO")
        self._pulse_cockpit_ai()
        greeting_lines = (
            detail + ".",
            "Compass session initialized. I am ready.",
            "Cockpit intelligence online. The new flight record is open.",
            "Session telemetry synchronized. I am with you for the next leg.",
            "Flight systems and memory are online. We can begin when you are ready.",
            "A fresh session is active. Navigation and ship awareness are standing by.",
        )
        if self.config.get("cockpit_session_greetings_enabled", True):
            context = memory.session_open_context(previous_updated_at)
            if context == "long-absence":
                greeting_lines = (
                    "It has been some time since our last flight together. Systems are ready when you are.",
                    f"{detail}. Welcome back — I was beginning to wonder about you.",
                    "The cockpit has been quiet for a while. I am glad to have our flight record moving again.",
                    "A longer interval than usual, but every system has come back online cleanly. Welcome back.",
                    "Our shared log has been waiting. I have restored the last context and opened a new session.",
                    "You have been away long enough for the silence to become noticeable. Flight systems are ready.",
                )
            elif context == "new-day":
                greeting_lines = (
                    "A new day, a fresh flight log. Good to have you back in the seat.",
                    f"{detail}. Another day in the black together.",
                    "New-day session initialized. I have carried our previous context forward.",
                    "The date changed; the flight continues. Everything is ready for today's work.",
                    "Fresh session, familiar cockpit. I have navigation and memory synchronized.",
                    "Another day in our record begins now. Ship intelligence is standing by.",
                )
        self._speak(
            greeting_lines,
            category="navigation",
            cooldown_s=0,
            key=f"cockpit-loadgame-session:{session.get('id') or 'session'}",
        )
        return True

    def _handle_cockpit_shutdown(self):
        """Close the current session once at Elite's natural Shutdown boundary."""
        memory = getattr(self, "cockpit_memory", None)
        if not memory or not self.config.get("cockpit_memory_enabled", True):
            return False
        session = memory.state.get("current_session")
        if not session:
            return False
        session_id = session.get("id") or "session"
        insights = (
            self.compass_cognition.observe_session_close(
                self._compass_gameplay_snapshot(), memory,
            )
            if getattr(self, "compass_cognition", None) else []
        )
        summary = memory.session_debrief(
            "Shutdown summary", close=True, insights=insights,
        )
        self._cockpit_feed_state = self._cockpit_ai_feed_snapshot()
        if not summary:
            return False
        self.add_event_feed_entry("AI", summary, severity="INFO")
        self._pulse_cockpit_ai()
        self._speak(
            summary,
            category="navigation",
            cooldown_s=0,
            key=f"cockpit-shutdown-summary:{session_id}",
        )
        return True

    def _pulse_cockpit_ai(self):
        heartbeat = getattr(self, "heartbeat_hud", None)
        if heartbeat:
            heartbeat.pulse("ai")

    def _announce_system_arrival(self, system_name, startup_replay=False):
        """Announce a live jump once, preferring useful route context."""
        if startup_replay or not system_name or system_name in ("---", "Unknown"):
            return False
        route = list(getattr(self, "route_list", None) or [])
        route_index = next(
            (idx for idx, name in enumerate(route)
             if str(name).casefold() == str(system_name).casefold()),
            -1,
        )
        if route_index == len(route) - 1 and route:
            return self._speak(
                (
                    f"Navigation confirms our destination. Welcome to {system_name}.",
                    f"We have arrived at {system_name}. I am closing the active route now.",
                    f"Destination confirmed. {system_name}. Route objectives complete.",
                    f"Hyperspace transition stable. This is {system_name}, our final destination.",
                ), category="navigation",
                cooldown_s=300, key=f"route-arrival:{system_name}",
            )
        if route_index >= 0:
            next_system = route[route_index + 1]
            return self._speak(
                (
                    f"Waypoint {route_index + 1} of {len(route)} reached. Next, {next_system}.",
                    f"Navigation checkpoint confirmed. I have {next_system} queued as our next system.",
                    f"That is waypoint {route_index + 1}. Updating the flight plan for {next_system}.",
                    f"Route telemetry updated. Next jump target, {next_system}.",
                ),
                category="navigation", cooldown_s=300,
                key=f"route-waypoint:{system_name}",
            )
        if (self.config.get("cockpit_memory_enabled", True)
                and getattr(self, "cockpit_memory", None)):
            remembered = self.cockpit_memory.arrival_lines(
                system_name, self.config.get("cockpit_personality_level", "Balanced")
            )
            if remembered:
                return self._speak(
                    remembered, category="navigation", cooldown_s=20,
                    key=f"system-arrival:{system_name}",
                )
        return self._speak(
            (
                f"Entered system. {system_name}.",
                f"Welcome to {system_name}.",
                f"Hyperspace exit stable. We are now in {system_name}.",
                f"Jump complete. Navigation identifies this system as {system_name}.",
                f"Frame shift transition complete. Welcome to {system_name}.",
            ), category="navigation",
            cooldown_s=20, key=f"system-arrival:{system_name}",
        )

    def _push_live_toast(self, title, message="", severity="info", duration_s=10,
                         voice_text=None, voice_category="safety", voice_key=None):
        toast = getattr(self, "toast_hud", None)
        if toast:
            toast.push(title, message, severity=severity, duration_s=duration_s)
        if voice_text:
            self._speak(voice_text, category=voice_category, key=voice_key)

    def _srv_toast_vehicle_name(self, raw=None, data=None):
        """Return NOMAD when Elite's SRV-shaped events belong to the Nomad."""
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        vehicle_id = data.get("ID") or raw.get("ID")
        explicit = (
            data.get("SRVType_Localised") or data.get("SRVType")
            or raw.get("SRVType_Localised") or raw.get("SRVType")
            or data.get("VehicleType") or raw.get("VehicleType")
        )
        loadout = data.get("Loadout") or raw.get("Loadout")
        remembered = (
            (getattr(self, "_vehicle_name_by_id", {}) or {}).get(vehicle_id)
            if vehicle_id is not None else ""
        )
        candidates = (
            explicit,
            "NOMAD" if str(loadout or "").casefold() == "galactic" else "",
            remembered,
            getattr(self, "current_vehicle_name", ""),
            getattr(self, "_last_surface_vehicle_name", ""),
        )
        return "NOMAD" if any(
            str(value or "").strip().casefold() == "nomad"
            for value in candidates
        ) else "SRV"

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
            from_srv = bool(d.get("SRV") or raw.get("SRV"))
            vehicle = (
                self._srv_toast_vehicle_name(raw, d)
                if from_srv else (raw.get("Taxi") and "taxi") or "ship"
            )
            self._push_live_toast("EMBARKED", str(vehicle), "info")
        elif ev == "HeatWarning":
            self._push_live_toast("OVERHEATING", "Ship temperature critical", "warn", 15,
                                  ("Warning. Ship temperature critical.",
                                   "Thermal telemetry has entered the critical range.",
                                   "Thermal limits exceeded. I recommend immediate cooling."),
                                  voice_key="ship-overheat")
        elif ev == "HeatDamage":
            self._push_live_toast("HEAT DAMAGE", "Modules are taking heat damage", "fail", 15,
                                  ("Heat damage. Modules are taking damage.",
                                   "Critical heat exposure. I am detecting module damage.",
                                   "The ship is cooking. Internal systems are degrading."),
                                  voice_key="heat-damage")
        elif ev == "UnderAttack":
            target = raw.get("Target") or raw.get("Target_Localised") or "Hostile fire detected"
            self._push_live_toast("UNDER ATTACK", target, "fail", 15,
                                  ("Warning. We are under attack.",
                                   "Hostile fire incoming. Defensive telemetry is active.",
                                   "Weapons fire detected. It appears we have company."), voice_key="under-attack")
        elif ev == "ShieldState":
            shields_up = bool(raw.get("ShieldsUp"))
            if shields_up != self._toast_shields_up:
                self._toast_shields_up = shields_up
                self._push_live_toast(
                    "SHIELDS RESTORED" if shields_up else "SHIELDS OFFLINE", "",
                    "success" if shields_up else "fail", 12,
                    None if shields_up else (
                        "Warning. Shields offline.",
                        "Shields have collapsed. Hull telemetry is now primary.",
                        "Defensive field lost. I am monitoring the exposed hull.",
                    ), voice_key="shields-offline",
                )
        elif ev == "HullDamage":
            health = float(raw.get("Health", 1.0) or 0.0)
            if health > 0.80:
                self._toast_hull_thresholds_seen.clear()
            crossed = [n for n in (75, 50, 25, 10) if health * 100 <= n and n not in self._toast_hull_thresholds_seen]
            if crossed:
                self._toast_hull_thresholds_seen.update(crossed)
                threshold = min(crossed)
                self._push_live_toast(
                    "HULL CRITICAL" if threshold <= 25 else "HULL DAMAGE",
                    f"Integrity at {health * 100:.0f}%", "fail" if threshold <= 25 else "warn", 15,
                    ((f"Hull critical. Integrity at {health * 100:.0f} percent.",
                      f"Hull integrity is down to {health * 100:.0f} percent.",
                      f"Structural failure risk. My sensors show hull at {health * 100:.0f} percent.")) if threshold <= 25 else None,
                    voice_key=f"hull-{threshold}",
                )
        elif ev == "CockpitBreached":
            self._push_live_toast(
                "CANOPY BREACHED", "Emergency oxygen reserve active", "fail", 20,
                (
                    "Canopy breach confirmed. Life support reserve is now critical.",
                    "Cockpit pressure lost. I am tracking emergency oxygen and the nearest safe dock.",
                    "Canopy failure. Break contact and secure life support immediately.",
                ), voice_key="cockpit-breached",
            )
        elif ev in ("Interdicted", "EscapeInterdiction"):
            escaped = ev == "EscapeInterdiction" or bool(raw.get("Submitted") is False)
            actor = raw.get("Interdictor") or raw.get("Interdictor_Localised") or raw.get("InterdictorName") or "Unknown contact"
            self._push_live_toast(
                "INTERDICTION ESCAPED" if escaped else "INTERDICTED", actor,
                "success" if escaped else "warn", 15,
                None if escaped else (
                    "Warning. Interdiction detected.",
                    "Interdiction tether engaged. I am tracking the vector.",
                    "Someone wants us out of supercruise. I suggest we disappoint them.",
                ), voice_key="interdiction",
            )
        elif ev == "JetConeBoost":
            self._push_live_toast(
                "FSD SUPERCHARGED", "Jet-cone boost acquired", "success", 10,
            )
        elif ev == "JetConeDamage":
            self._push_live_toast("JET CONE DAMAGE", "Exit the cone immediately", "fail", 18,
                                  ("Jet cone damage. Exit immediately.",
                                   "Danger. The jet cone is damaging the ship. I need us clear now.",
                                   "Unstable cone exposure. Exit now. I cannot compensate for this."), voice_key="jet-cone-damage")
        elif ev in ("FighterDestroyed", "SRVDestroyed"):
            title = (
                "FIGHTER DESTROYED" if ev == "FighterDestroyed"
                else f"{self._srv_toast_vehicle_name(raw, d)} DESTROYED"
            )
            self._push_live_toast(title, "", "fail", 15)
        elif ev == "Died":
            killer = raw.get("KillerName_Localised") or raw.get("KillerName") or "Commander lost"
            self._push_live_toast("DESTRUCTION", killer, "fail", 20,
                                  ("Ship destroyed.", "Vessel lost. Initiating recovery protocols.",
                                   "Catastrophic failure. I am transferring control to emergency recovery."), voice_key="ship-destroyed")
        elif ev in ("MissionAccepted", "MissionCompleted", "MissionFailed", "MissionAbandoned"):
            name = raw.get("LocalisedName") or raw.get("Name_Localised") or raw.get("Name") or "Mission"
            titles = {"MissionAccepted": "MISSION ACCEPTED", "MissionCompleted": "MISSION COMPLETE", "MissionFailed": "MISSION FAILED", "MissionAbandoned": "MISSION ABANDONED"}
            sev = "success" if ev == "MissionCompleted" else ("fail" if ev in ("MissionFailed", "MissionAbandoned") else "info")
            self._push_live_toast(titles[ev], name, sev, 15)
        elif ev == "ScanOrganic":
            species = d.get("species") or d.get("genus") or "Organic"
            scan_type = str(d.get("scan_type") or raw.get("ScanType") or "").lower()
            complete = bool(d.get("is_complete")) or scan_type == "analyse"
            body_id = self._normalize_body_id(d.get("body_id"))
            species_key = f"{body_id}|{species}" if body_id is not None else species
            existing = self.last_bio_scan.get(species_key, {})
            max_samples = d.get("max_samples") or 3
            if scan_type in ("log", "sample"):
                sample = int(existing.get("sample_idx") or 0) + 1
            else:
                sample = existing.get("sample_idx") or max_samples
            detail = "Analysis complete" if complete else f"Sample {sample}/{max_samples}"
            bio_voice = None
            if complete:
                bio_voice = [
                    f"Biological analysis complete. {species}.",
                    f"Excellent work. My bio lab has completed the {species} analysis.",
                    f"Third sample confirmed. I have prepared {species} for Vista Genomics.",
                    f"Genetic sequence locked. {species} analysis is complete.",
                ]
                if (self.config.get("cockpit_memory_enabled", True)
                        and getattr(self, "cockpit_memory", None)):
                    previous = self.cockpit_memory.species_analyses(species)
                    completed = previous + 1
                    if self.cockpit_memory.should_reference_repeat(
                            completed, self.config.get("cockpit_personality_level", "Balanced")):
                        bio_voice.append(
                            f"I remember this species. This is our {ordinal(completed)} completed {species} analysis."
                        )
            self._push_live_toast(
                "BIO COMPLETE" if complete else "BIO SAMPLE", f"{species}: {detail}",
                "success" if complete else "info", 12,
                bio_voice,
                voice_category="exploration", voice_key=f"bio-complete:{species}",
            )
        elif ev == "CodexEntry":
            name = d.get("name") or raw.get("Name_Localised") or raw.get("Name") or "New Codex entry"
            category = d.get("category") or raw.get("Category_Localised") or "Discovery"
            self._push_live_toast("CODEX DISCOVERY", f"{category}: {name}", "success", 15,
                                  (f"Codex discovery. {name}.",
                                   f"A new Codex entry. I have identified {name}.",
                                   f"Discovery logged to the ship archive. {name}.",
                                   f"Our Codex just grew a little larger. {name}."), voice_category="exploration",
                                  voice_key=f"codex:{name}")
        elif ev in ("CommitCrime", "Bounty"):
            detail = raw.get("CrimeType_Localised") or raw.get("CrimeType") or raw.get("Victim") or raw.get("Target_Localised") or raw.get("Target") or "Legal status changed"
            self._push_live_toast("CRIME REPORTED" if ev == "CommitCrime" else "BOUNTY AWARDED", str(detail), "warn", 15)
        elif ev == "SystemsShutdown":
            self._push_live_toast(
                "SYSTEMS SHUTDOWN", "Ship systems have been forced offline", "fail", 18,
                (
                    "Warning. Ship systems have been forced offline.",
                    "Critical systems shutdown detected. Stand by for recovery.",
                    "All ship systems are offline. Monitoring recovery sequence.",
                    "Power loss across the ship. I am tracking the restart cycle.",
                ),
                voice_category="safety", voice_key="systems-shutdown",
            )
        elif ev == "USSDrop":
            threat = int(raw.get("USSThreat") or 0)
            if threat >= 3:
                signal = raw.get("USSType_Localised") or raw.get("USSType") or "Signal source"
                self._push_live_toast(
                    "SIGNAL THREAT", f"{signal} · threat {threat}",
                    "fail" if threat >= 5 else "warn", 14,
                )
        elif ev == "SelfDestruct":
            self._push_live_toast("SELF-DESTRUCT", "Self-destruct sequence initiated", "fail", 15)

    def process_event(self, data):
        ev = data.get("type") or data.get("event")
        raw = data.get("raw", data)
        d = data.get("data", data)
        startup_replay = bool(data.get("startup_catchup"))
        if startup_replay:
            self._startup_restore_active = True
            self._startup_restore_ui_pending = True
        if ev == "ScanOrganic":
            d = self._enrich_bio_event_context(d)
        if ev in ("Commander", "LoadGame"):
            commander = d.get("name") if ev == "Commander" else d.get("commander")
            fid = d.get("fid")
            if commander:
                self._switch_commander_profile(commander, fid)
        specialist_changed = False
        try:
            specialist_engine = getattr(self, "specialist_engine", None)
            specialist_changed = bool(specialist_engine) and specialist_engine.observe_event(
                raw if isinstance(raw, dict) else d,
                event_uid=data.get("_journal_uid"),
                context={
                    "system": getattr(self, "current_sys", None),
                    "body": getattr(self, "current_body_name", None),
                    "historical": startup_replay,
                    "at_own_carrier": bool(
                        getattr(self, "current_docked", False)
                        and getattr(self, "current_station_market_id", None)
                        and getattr(self.carrier_tracker, "carrier_data", {}).get("carrier_id")
                        == getattr(self, "current_station_market_id", None)
                    ),
                },
                defer_save=True,
            )
        except Exception as exc:
            logging.warning("Specialist workflow event failed [%s]: %s", ev, exc)
        if specialist_changed and not self.batch_mode:
            self._schedule_specialist_flush()
            window = getattr(self, "specialists_window", None)
            if window and window.is_open() and getattr(self, "_active_page", None) == "SPECIALISTS":
                self.root.after(0, window.refresh)
        try:
            self.achievement_engine.process_event(
                data,
                notify=not startup_replay,
                historical=startup_replay,
            )
        except Exception as exc:
            logging.warning(f"Achievement engine event error [{ev}]: {exc}")
        if not startup_replay:
            self._record_journal_event()
        # Apply personal-credit changes before optional AI, toast and tool
        # handlers. A failure in a secondary feature must never leave the HUD
        # balance behind a confirmed journal transaction.
        if ev != "LoadGame":
            try:
                self._apply_credit_event(
                    ev, raw if isinstance(raw, dict) else d,
                    log=not startup_replay,
                )
            except Exception as exc:
                logging.warning("Credit event failed [%s]: %s", ev, exc)
        if getattr(self, "captains_log", None):
            try:
                if self.captains_log.process_event(raw, context=d):
                    self._refresh_exploration_window()
                    self._refresh_commander_profile_window()
            except Exception as exc:
                logging.debug("Captain's Log event skipped [%s]: %s", ev, exc)
        if getattr(self, "deep_survey", None):
            try:
                survey_raw = raw if isinstance(raw, dict) else d
                if isinstance(survey_raw, dict) and not survey_raw.get("event"):
                    survey_raw = dict(survey_raw, event=ev)
                if self.deep_survey.observe_event(
                    survey_raw, context=d, event_uid=data.get("_journal_uid"),
                ):
                    self._refresh_exploration_window()
            except Exception as exc:
                logging.debug("Deep Survey event skipped [%s]: %s", ev, exc)
        expedition_result = None
        if getattr(self, "expedition_manager", None):
            try:
                expedition_raw = raw if isinstance(raw, dict) else d
                if isinstance(expedition_raw, dict) and not expedition_raw.get("event"):
                    expedition_raw = dict(expedition_raw, event=ev)
                expedition_result = self.expedition_manager.observe_event(
                    expedition_raw,
                    context={
                        "system": getattr(self, "current_sys", None),
                        "body": d.get("body_name") if isinstance(d, dict) else getattr(self, "current_body_name", None),
                    },
                    event_uid=data.get("_journal_uid"),
                    historical=startup_replay,
                )
                if expedition_result:
                    self._refresh_exploration_window()
            except Exception as exc:
                logging.debug("Expedition objective event skipped [%s]: %s", ev, exc)
        if expedition_result and expedition_result.get("completed") and not startup_replay:
            completed_titles = list(expedition_result.get("completed") or [])
            summary = completed_titles[0] if len(completed_titles) == 1 else f"{len(completed_titles)} objectives"
            self.add_event_feed_entry(
                "EXPEDITION", f"Objective complete: {summary}", severity="INFO",
            )
            if getattr(self, "captains_log", None):
                self.captains_log.add_manual_highlight(
                    "OBJECTIVE", f"Expedition objective complete: {summary}",
                )
            self._speak(
                (
                    f"Expedition objective complete. {summary}.",
                    f"Mission Control confirms completion of {summary}.",
                    f"Objective log updated. {summary} is complete.",
                ),
                category="objectives", cooldown_s=2,
                key=f"expedition-objective:{'|'.join(completed_titles)}",
            )
        self._handle_live_journal_toast(ev, raw, d, startup_replay=startup_replay)
        self._observe_ai_economy_event(
            ev, raw if isinstance(raw, dict) else d, startup_replay=startup_replay,
        )
        try:
            compass_operations.observe_event(
                self.ai_operational_state,
                ev,
                raw if isinstance(raw, dict) else d,
                current_system=getattr(self, "current_sys", None),
                historical=startup_replay,
            )
        except Exception as exc:
            logging.debug("Compass operational event skipped [%s]: %s", ev, exc)
        self._update_adaptive_command(
            ev, raw if isinstance(raw, dict) else d,
            startup_replay=startup_replay,
        )
        combat_tracker = getattr(self, "combat_awareness", None)
        if combat_tracker:
            combat_tracker.observe(
                ev, raw if isinstance(raw, dict) else d,
                system=getattr(self, "current_sys", None),
                startup_replay=startup_replay,
            )
        if ev == "LoadGame":
            self._handle_cockpit_load_game(raw, d, startup_replay=startup_replay)
            if not startup_replay:
                self._publish_expedition_resume_briefing()
        if (self.config.get("cockpit_memory_enabled", True)
                and getattr(self, "cockpit_memory", None)):
            try:
                self.cockpit_memory.set_current_system(getattr(self, "current_sys", None))
                self.cockpit_memory.memory_callbacks_enabled = self.config.get("cockpit_memory_callbacks_enabled", True)
                learned = self.cockpit_memory.observe(ev, raw, d, startup_replay=startup_replay)
                if not startup_replay:
                    self._publish_cockpit_ai_changes()
                    if learned:
                        self._pulse_cockpit_ai()
            except Exception as exc:
                logging.debug("Cockpit memory event skipped [%s]: %s", ev, exc)
        if ev == "Shutdown" and not startup_replay:
            self._handle_cockpit_shutdown()
        self._process_companion_event(ev, raw if isinstance(raw, dict) else {}, d,
                                      startup_replay=startup_replay)
        if ev != "LoadGame" and self.edsm.is_credit_event(ev):
            self._queue_edsm_upload(raw, flush=True, startup_replay=startup_replay)
        current_journal = getattr(self.watcher, "last_journal", None)
        if current_journal and current_journal != self.last_logged_journal_file:
            self.last_logged_journal_file = current_journal
            self.log(f"Journal file: {os.path.basename(current_journal)}")
        if ev and not startup_replay and not self._is_redundant_music_event(ev, raw if isinstance(raw, dict) else d):
            self.add_journal_history_entry(ev, raw if isinstance(raw, dict) else d)
        # Route carrier events defensively — a tracker failure must not cascade
        # into the main navigation if/elif chain (fix #2).
        carrier_context_events = {
            "SquadronStartup", "SquadronCreated", "JoinedSquadron",
            "SquadronPromotion", "SquadronDemotion", "LeftSquadron",
            "KickedFromSquadron", "DisbandedSquadron",
        }
        if ev and (ev.startswith("Carrier") or ev in carrier_context_events):
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
            self.cmdr_ship, _ = companion_features.update_active_ship(
                self.cmdr_ship, ev, raw
            )
            self.watcher.force_check_cargo()
            if self.colony_overlay:
                self.colony_overlay.update()
            self._queue_edsm_upload(raw, allow_startup=True)
            self._refresh_commander_profile_window()

        elif ev in ("ShipyardBuy", "ShipyardNew", "ShipyardSwap", "SetUserShipName"):
            self.cmdr_ship, ship_changed = companion_features.update_active_ship(
                self.cmdr_ship, ev, raw
            )
            if ev in companion_features.SHIP_CHANGE_EVENTS:
                self.cargo_capacity = 0
                self.fuel_capacity_main = None
                self._low_fuel_warned = False
            if ship_changed:
                self._refresh_commander_profile_window()

        elif ev == "Cargo":
            # Journal can emit Cargo before/without immediate file polling update.
            self.watcher.force_check_cargo()
            # EDSM cargo is sent from the complete Cargo.json snapshot by
            # update_cargo(); the journal notification often has no Inventory.

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

        elif ev == "EngineerProgress":
            self._process_engineer_progress(raw)

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
            self.cmdr_ship, _ = companion_features.update_active_ship(
                self.cmdr_ship, ev, raw
            )
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
            # Live ScanOrganic events carry no Sample/IsNewSample field, so sample
            # progress has to be tracked locally from ScanType position (Log=1,
            # Sample=2, Sample=3, then Analyse completes without adding a sample).
            scan_type_norm = str(d.get("scan_type") or "").strip().casefold()
            max_samples = d.get("max_samples", 3)
            is_complete = bool(d.get("is_complete")) or scan_type_norm == "analyse"
            was_complete = bool(existing.get("is_complete"))
            is_new_sample = scan_type_norm in ("log", "sample")
            if is_new_sample:
                sample_idx = int(existing.get("sample_idx") or 0) + 1
            else:
                sample_idx = existing.get("sample_idx") or max_samples

            self.last_bio_scan[species_key] = {
                "body_id":        body_id,
                "body_name":      body_label,
                "species":        species,
                "genus":          d.get("genus"),
                "variant":        d.get("variant"),
                "species_value":  bio_values.species_value(species),
                "genus_value":    bio_values.genus_info(d.get("genus") or species),
                "colony_m":       bio_values.GENUS_COLONY_M.get(d.get("genus") or species),
                "sample_idx":     sample_idx,
                "max_samples":    max_samples,
                "scan_type":      d.get("scan_type"),
                "is_new_entry":   bool(d.get("is_new_entry")),
                "is_new_sample":  is_new_sample,
                "is_complete":    is_complete,
                "system_address": self.current_system_address,
            }

            if is_complete and not was_complete:
                self.organic_count += 1
                if not startup_replay:
                    self.add_event_feed_entry("BIO", f"Organic complete: {species} ({body_label})", severity="INFO", copy_text=species)
            elif is_new_sample and not startup_replay:
                self.add_event_feed_entry("BIO", f"Organic sample {sample_idx}: {species} ({body_label})", severity="INFO", copy_text=species)

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
                self._refresh_system_info_progress()
                self._speak_pending_cockpit_remark()

        elif ev == "Location" or ev == "FSDJump" or ev == "StartJump" or (ev == "CarrierJump" and d.get("docked")):
            # Do not update HUDs during jump charge; wait for arrival.
            if ev == "StartJump":
                self._save_exploration_checkpoint("departure")
                self.in_fss = False
                self.fss_summary_active = False
                self._hide_survey_status_for_jump()
                jump_type = d.get("jump_type") or (raw.get("JumpType") if isinstance(raw, dict) else "")
                jump_type = str(jump_type or "").lower()
                self.hud_flight_state = "SUPERCRUISE" if jump_type == "supercruise" else "HYPERSPACE"
                self.update_hud()
                compass_snapshot = None
                if not startup_replay:
                    compass_snapshot = self._compass_gameplay_snapshot()
                    self._sync_cockpit_intentions(compass_snapshot)
                self._process_compass_cognition(
                    ev, raw, d, startup_replay=startup_replay,
                    snapshot=compass_snapshot,
                )
                return

            # CarrierJump counts as a jump for the player when they are docked on board.
            is_jump = ev in ("FSDJump", "CarrierJump")

            # A login while already docked normally emits Location, not a new
            # Docked event. Apply its state immediately so a profile switch
            # cannot retain the outgoing commander's HUD label or station.
            if ev == "Location":
                self._apply_location_navigation_state(raw, d)

            # Reset FSS state on jump completion
            if is_jump:
                self.in_fss = False
                self.fss_summary_active = False
                if ev == "CarrierJump" and d.get("docked"):
                    self.current_docked = True
                    self.hud_flight_state = "DOCKED"
                else:
                    self.current_docked = False
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

            if is_jump and isinstance(raw, dict):
                try:
                    fuel_used = float(raw.get("FuelUsed") or 0)
                    if fuel_used > 0:
                        self._fuel_used_samples.append(fuel_used)
                except (TypeError, ValueError):
                    pass
                try:
                    fuel_level = raw.get("FuelLevel")
                    if fuel_level is not None:
                        self.current_fuel_main = float(fuel_level)
                except (TypeError, ValueError):
                    pass

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
            self._system_traffic_resolved = bool(preserve_startup_traffic)
            self._pending_system_discovery = None
            self.scan_items = self.load_scan_items_from_db(self.current_sys)
            self.body_signals = {}
            self.body_dss_complete = set()
            self.system_undiscovered = False
            self.fss_all_bodies = False
            self.fss_summary_active = False
            self._rebuild_scan_index()
            self._rebuild_system_state_from_scan_items()
            self._seed_navigation_scan_progress()
            if is_jump:
                # Speak only after the incoming system's persisted scan state is
                # loaded; otherwise cognitive context can accidentally describe
                # unresolved bodies from the system we just left.
                self._announce_system_arrival(incoming_sys, startup_replay=startup_replay)
                if not startup_replay:
                    self._speak_pending_cockpit_remark()

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
            if not startup_replay:
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
                if self.star_class:
                    sys_text += f" [{star_type_label(self.star_class)}]"
                self.root.after(0, lambda: self.sys_stat.config(text=sys_text))
                self.update_nav_label()
            # Bio logs hidden for now (counting disabled)
                self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
                self.root.after(0, self.update_waypoint_display)
                self.schedule_dashboard_refresh(full=True)
                self.update_hud()
                self.update_scan_hud()

            # Update Route Plotter UI if open
            if (not startup_replay and self.route_plotter
                    and self.route_plotter.win.winfo_exists()):
                s_sys = self.current_sys
                s_coords = self.current_coords
                self.root.after(0, lambda: self.route_plotter.update_current_system(s_sys, s_coords))

            # Auto-copy next waypoint logic
            if not startup_replay and self.config.get("auto_copy_waypoint", False):
                next_wp = self.waypoint_manager.get_next_waypoint(self.current_sys)
                if next_wp:
                    self._copy_waypoint_to_clipboard(next_wp, "NEXT WAYPOINT")

            if not startup_replay and self.current_sys != self.last_traffic_system:
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
                    self.current_sys, self.scanned, self.total, self.scan_items,
                    self.body_signals, sampling=self._sampling_snapshot(),
                    focused_body_id=self.current_body_id,
                    focused_body_name=self.current_body_name))
            self._refresh_exploration_window()

        elif ev == "Docked":
            if not startup_replay:
                self._speak_pending_cockpit_remark()
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

        elif ev == "VehicleSwitch":
            self._apply_vehicle_switch(raw.get("To") or d.get("To"))

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
            self._record_navigation_fss_progress(progress)
            if progress is not None and progress >= 1.0 and self.total > 0:
                self._mark_system_scan_complete(self.total)
            else:
                self.db_update_system(self.current_sys, self.total, self.scanned)
                if not self.batch_mode:
                    self.root.after(0, lambda: self.scan_stat.config(text=f"{self.scanned} / {self.total}"))
            self.log(f"🔭 HONK: {self.total} bodies detected.")
            if not startup_replay:
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
                if not startup_replay:
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
                if not startup_replay:
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
                    self._set_body_signals(
                        body_id, bio_count, geo_count, genuses=d.get("genuses") or [],
                    )
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
                    if not startup_replay:
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
                if (not startup_replay
                        and self.config.get("cockpit_memory_enabled", True)
                        and getattr(self, "cockpit_memory", None)):
                    predictions_learned = self.cockpit_memory.observe_bio_predictions(
                        self.current_sys,
                        body_name or f"Body {body_id}",
                        self.body_scan_data[body_id]["predicted_genuses"],
                    )
                    if predictions_learned:
                        self._publish_cockpit_ai_changes()
                        self._pulse_cockpit_ai()
            
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
                        self._consider_system_undiscovered(startup_replay=startup_replay)
                    if not self.batch_mode:
                        self.update_hud()
                        self.schedule_dashboard_refresh()
                        self._refresh_system_info_progress()

                    body_label = body_name or "Unknown Body"
                    landable_marker = " 🚀" if d.get("landable") else ""
                    if not startup_replay:
                        self.add_event_feed_entry("SCAN", f"{body_label}{landable_marker}", severity="INFO", copy_text=body_label)

                    # Check for biological signals and update the system total
                    if d.get("bio_signals_count", 0):
                        self._set_body_signals(body_id, d.get("bio_signals_count", 0), self.body_signals.get(body_id, {}).get("geo", 0))

                    # Check for valuable bodies
                    p_class = d.get("planet_class", "")
                    terraformable = d.get("terraform_state") == "Terraformable"
                    self._track_valuable_world(
                        body_name, p_class, terraformable, startup_replay=startup_replay,
                    )
                else:
                    # Later detailed/nav-beacon scans can add fields missing from an initial basic scan.
                    self.last_scan_event = data
                    self.add_scan_item(raw)
                    self._queue_edsm_upload(raw, startup_replay=startup_replay)

                    p_class = d.get("planet_class", "")
                    terraformable = d.get("terraform_state") == "Terraformable"
                    self._track_valuable_world(
                        body_name, p_class, terraformable, startup_replay=startup_replay,
                    )

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
                was_failed = bool(_existing.get("failed"))
                self.colonisation_projects[mid] = {
                    "market_id":    mid,
                    "system_name":  d.get("system_name") or _existing.get("system_name") or self.current_sys or "",
                    "body_name":    d.get("body_name") or _existing.get("body_name") or "",
                    "progress":     d.get("progress", 0.0),
                    "complete":     d.get("complete", False),
                    "failed":       d.get("failed", False),
                    "resources":    d.get("resources", []),
                    "last_updated": time.time(),
                    "notes":        _existing.get("notes", ""),
                    "activity":     list(_existing.get("activity") or []),
                }
                old_progress = float(_existing.get("progress") or 0)
                new_progress = float(self.colonisation_projects[mid].get("progress") or 0)
                project_now = self.colonisation_projects[mid]
                if (new_progress != old_progress or project_now["complete"] != was_complete
                        or project_now["failed"] != was_failed):
                    activity = self.colonisation_projects[mid]["activity"]
                    activity_type = (
                        "COMPLETE" if project_now["complete"] else
                        "FAILED" if project_now["failed"] else "PROGRESS"
                    )
                    activity.append({
                        "timestamp": raw.get("timestamp") or time.time(),
                        "type": activity_type,
                        "detail": f"Depot progress {new_progress * 100:.1f}%",
                    })
                    self.colonisation_projects[mid]["activity"] = activity[-120:]
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
                proj["last_updated"] = time.time()
                contribs = {c["name"].lower(): c["count"] for c in (d.get("contributions") or [])}
                for r in proj.get("resources", []):
                    delta = contribs.get(r["name"].lower(), 0)
                    if delta:
                        r["provided"] = min(r["required"], r.get("provided", 0) + delta)
                delivered = sum(int(value or 0) for value in contribs.values())
                if delivered:
                    detail = ", ".join(
                        f"{name}: {int(count):,}" for name, count in contribs.items() if count
                    )
                    activity = proj.setdefault("activity", [])
                    activity.append({
                        "timestamp": raw.get("timestamp") or time.time(),
                        "type": "DELIVERY", "detail": detail,
                    })
                    proj["activity"] = activity[-120:]
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
            self._refresh_system_info_progress()
        elif ev == "LeaveBody" and not self.batch_mode:
            self._check_stale_bio_scans(self.current_body_id)
            self.current_body_id   = None
            self.current_body_name = ""
            if self.gravity_warning_hud:
                self.gravity_warning_hud.clear()
            self._refresh_system_info_progress()

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

        self._update_exploration_intelligence(
            ev, raw if isinstance(raw, dict) else d,
            startup_replay=startup_replay,
        )
        compass_snapshot = None
        if not startup_replay:
            compass_snapshot = self._compass_gameplay_snapshot()
            self._sync_cockpit_intentions(compass_snapshot)
        self._process_compass_cognition(
            ev, raw, d, startup_replay=startup_replay,
            snapshot=compass_snapshot,
        )

    # ── Companion feature state ───────────────────────────────────────────────

    @staticmethod
    def _companion_mission_key(mission_id):
        return str(mission_id) if mission_id is not None else None

    def _refresh_companion_surfaces(self):
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        if getattr(self, "_companion_refresh_job", None) is not None:
            return
        def run():
            self._companion_refresh_job = None
            try:
                self._refresh_commander_profile_window()
            except Exception:
                pass
            try:
                if self.bgs_window and self.bgs_window.is_open():
                    self.bgs_window.refresh_current()
            except Exception:
                pass
        try:
            self._companion_refresh_job = self.root.after(200, run)
        except Exception:
            self._companion_refresh_job = None

    def _toast_on_main(self, title, message, severity="info", duration=12,
                       voice_text=None, voice_category="safety", voice_key=None):
        if self.toast_hud:
            self.root.after(0, lambda: self.toast_hud.push(
                title, message, severity=severity, duration_s=duration,
            ))
        if voice_text:
            self._speak(voice_text, category=voice_category, key=voice_key)

    def _clear_sold_data_warnings(self, biological=False):
        """Cancel risk output that became obsolete during a data sale."""
        toast = getattr(self, "toast_hud", None)
        if toast and hasattr(toast, "dismiss"):
            try:
                self.root.after(0, lambda target=toast: target.dismiss(title="DATA AT RISK"))
            except Exception:
                pass
        voice = getattr(self, "voice_callouts", None)
        if voice and hasattr(voice, "cancel"):
            prefixes = ["data-risk", "advisor:unsold-data"]
            if biological:
                prefixes.append("cockpit-context:bio-sell-anticipation")
            try:
                voice.cancel(key_prefixes=prefixes)
            except Exception:
                pass
        if biological and getattr(self, "cockpit_memory", None):
            try:
                self.cockpit_memory.clear_pending_topics("bio-sell-anticipation")
            except Exception:
                pass

    def _toggle_galaxy_faction_watch(self, faction_name):
        enabled = companion_features.toggle_faction_watch(self.companion_state, faction_name)
        # Establish the current system as the baseline so enabling a watch never
        # creates an immediate false-positive alert.
        companion_features.update_faction_watch_snapshots(
            self.companion_state,
            self.companion_state.get("galaxy_system"),
            self.companion_state.get("factions") or [],
            self.companion_state.get("controlling_faction"),
            notify=False,
        )
        self._save_companion_state()
        self._refresh_companion_surfaces()
        return enabled

    def _process_companion_event(self, ev, raw, data, startup_replay=False):
        state = self.companion_state
        changed = False
        galaxy_changed = False

        if ev == "Loadout":
            state["loadout"] = dict(raw)
            changed = True

        elif ev in companion_features.SHIP_COMPANION_EVENTS:
            changed = companion_features.update_ship_companion_state(
                state, ev, raw
            ) or changed

        elif ev == "Statistics":
            # Statistics is Elite's lifetime commander record. Retain the most
            # recent complete snapshot per profile so Commander Record can use
            # it without rescanning journal history on every UI refresh.
            state["statistics"] = {
                key: value for key, value in raw.items()
                if key not in ("timestamp", "event")
            }
            state["statistics_updated"] = raw.get("timestamp")
            changed = True

        elif ev == "LoadGame":
            if state.get("powerplay"):
                state["powerplay"].update({
                    "session_merits": 0,
                    "session_collected": 0,
                    "session_delivered": 0,
                    "session_fast_track_cr": 0,
                    "session_salary_cr": 0,
                    "commodities_collected": {},
                    "commodities_delivered": {},
                    "activity": [],
                    "last_action": None,
                })
                changed = True

        elif ev == "StoredShips":
            state["stored_ships"] = {
                "station": raw.get("StationName"), "system": raw.get("StarSystem"),
                "here": [companion_features.normalise_stored_ship(row) for row in raw.get("ShipsHere") or []],
                "remote": [companion_features.normalise_stored_ship(row) for row in raw.get("ShipsRemote") or []],
                "updated": raw.get("timestamp"),
            }
            changed = True

        elif ev == "MissionAccepted":
            mission = companion_features.mission_from_event(raw)
            if mission:
                state.setdefault("missions", {})[self._companion_mission_key(mission["id"])] = mission
                changed = True

        elif ev in ("MissionCompleted", "MissionFailed", "MissionAbandoned"):
            key = self._companion_mission_key(raw.get("MissionID"))
            if key and state.setdefault("missions", {}).pop(key, None) is not None:
                changed = True
                self._prune_massacre_kills()

        elif ev == "Missions":
            active = {self._companion_mission_key(row.get("MissionID")) for row in raw.get("Active") or []}
            missions = state.setdefault("missions", {})
            reconciled = {key: row for key, row in missions.items() if key in active}
            if len(reconciled) != len(missions):
                state["missions"] = reconciled
                changed = True
                self._prune_massacre_kills()

        elif ev == "CargoDepot":
            mission = state.setdefault("missions", {}).get(self._companion_mission_key(raw.get("MissionID")))
            if mission:
                mission.update({
                    "collected": raw.get("ItemsCollected"), "delivered": raw.get("ItemsDelivered"),
                    "to_deliver": raw.get("TotalItemsToDeliver"),
                })
                changed = True

        elif ev == "MissionRedirected":
            mission = state.setdefault("missions", {}).get(self._companion_mission_key(raw.get("MissionID")))
            if mission:
                if raw.get("NewDestinationSystem"):
                    mission["destination_system"] = raw["NewDestinationSystem"]
                if raw.get("NewDestinationStation"):
                    mission["destination_station"] = raw["NewDestinationStation"]
                if raw.get("NewDestinationSettlement"):
                    mission["destination_settlement"] = raw["NewDestinationSettlement"]
                changed = True

        elif ev in ("Bounty", "FactionKillBond"):
            victim = raw.get("VictimFaction")
            active_targets = {row["faction"] for row in companion_features.massacre_stacks(state)}
            if victim and victim in active_targets and not startup_replay:
                before = next((row for row in companion_features.massacre_stacks(state)
                               if row["faction"] == victim), None)
                kills = state.setdefault("faction_kills", {})
                kills[victim] = int(kills.get(victim, 0)) + 1
                after = next((row for row in companion_features.massacre_stacks(state)
                              if row["faction"] == victim), None)
                changed = True
                if before and after and not before["complete"] and after["complete"]:
                    self._toast_on_main(
                        "STACK COMPLETE", f"All massacre missions against {victim} are ready", "success", 15,
                        (f"Massacre stack complete. All missions against {victim} are ready.",
                         f"Objectives complete. I have marked the full {victim} mission stack ready for collection.",
                         f"That was the last target. All missions against {victim} are complete.",
                         f"Combat tally reconciled. Every active {victim} contract is now complete."),
                        "objectives", f"massacre-complete:{victim}",
                    )

        elif ev in ("Powerplay", "PowerplayJoin", "PowerplayDefect", "PowerplayLeave",
                    "PowerplayRank", "PowerplayMerits", "PowerplayCollect",
                    "PowerplayDeliver", "PowerplayFastTrack", "PowerplaySalary",
                    "PowerplayVote", "PowerplayVoucher"):
            self._update_powerplay_state(ev, raw)
            changed = True
            galaxy_changed = True

        elif ev == "CommunityGoal":
            goals = {}
            for goal in raw.get("CurrentGoals") or []:
                if goal.get("CGID") is None:
                    continue
                goals[str(goal["CGID"])] = {
                    "title": goal.get("Title"), "system": goal.get("SystemName"),
                    "market": goal.get("MarketName"), "expiry": goal.get("Expiry"),
                    "complete": bool(goal.get("IsComplete")),
                    "current_total": goal.get("CurrentTotal"),
                    "contribution": goal.get("PlayerContribution"),
                    "contributors": goal.get("NumContributors"),
                    "percentile": goal.get("PlayerPercentileBand"),
                    "tier": (goal.get("TierReached") or "").replace("Tier ", "") or None,
                    "top_rank": bool(goal.get("PlayerInTopRank")),
                    "bonus": goal.get("Bonus"),
                }
            state["community_goals"] = goals
            changed = True
            galaxy_changed = True

        elif ev in ("SquadronStartup", "SquadronCreated", "JoinedSquadron"):
            previous = state.get("squadron") or {}
            squadron_name = raw.get("SquadronName") or previous.get("name")
            squadron_id = raw.get("SquadronID", previous.get("id"))
            same_squadron = bool(previous and (
                (squadron_id is not None and previous.get("id") == squadron_id)
                or (squadron_name and previous.get("name") == squadron_name)
            ))
            state["squadron"] = {
                "id": squadron_id,
                "name": squadron_name,
                "rank": raw.get("CurrentRank", previous.get("rank") if same_squadron else None),
                "rank_name": raw.get("CurrentRankName", previous.get("rank_name") if same_squadron else None),
                "joined_at": previous.get("joined_at") if same_squadron else raw.get("timestamp"),
                "updated": raw.get("timestamp"),
                "source": ev,
            }
            state["squadron_application"] = None
            state["squadron_invitation"] = None
            if ev != "SquadronStartup":
                detail = "Squadron created" if ev == "SquadronCreated" else "Squadron joined"
                companion_features.record_squadron_activity(
                    state, ev, squadron_name, raw.get("timestamp"), detail,
                )
            changed = True
            galaxy_changed = True

        elif ev == "CommunityGoalDiscard":
            goal_id = raw.get("CGID")
            goals = state.setdefault("community_goals", {})
            removed = goals.pop(str(goal_id), None) if goal_id is not None else None
            if removed is not None:
                changed = True
                galaxy_changed = True
        elif ev in ("SquadronPromotion", "SquadronDemotion"):
            previous = state.get("squadron") or {}
            state["squadron"] = {
                "id": raw.get("SquadronID", previous.get("id")),
                "name": raw.get("SquadronName") or previous.get("name"),
                "rank": raw.get("NewRank", previous.get("rank")),
                "rank_name": raw.get("NewRankName", previous.get("rank_name")),
                "joined_at": previous.get("joined_at"),
                "updated": raw.get("timestamp"),
                "source": ev,
            }
            old_rank = raw.get("OldRankName", raw.get("OldRank"))
            new_rank = raw.get("NewRankName", raw.get("NewRank"))
            detail = f"{old_rank} → {new_rank}" if old_rank is not None and new_rank is not None else None
            companion_features.record_squadron_activity(
                state, ev, raw.get("SquadronName") or previous.get("name"), raw.get("timestamp"), detail,
            )
            changed = True
            galaxy_changed = True
        elif ev in ("LeftSquadron", "KickedFromSquadron", "DisbandedSquadron"):
            previous = state.get("squadron") or {}
            squadron_name = raw.get("SquadronName") or previous.get("name")
            detail = {
                "LeftSquadron": "Squadron left",
                "KickedFromSquadron": "Removed from squadron",
                "DisbandedSquadron": "Squadron disbanded",
            }[ev]
            companion_features.record_squadron_activity(
                state, ev, squadron_name, raw.get("timestamp"), detail,
            )
            state["squadron"] = None
            changed = True
            galaxy_changed = True

        elif ev == "AppliedToSquadron":
            squadron_name = raw.get("SquadronName")
            state["squadron_application"] = {
                "id": raw.get("SquadronID"), "name": squadron_name,
                "timestamp": raw.get("timestamp"),
            }
            companion_features.record_squadron_activity(
                state, ev, squadron_name, raw.get("timestamp"), "Application submitted",
            )
            changed = True
            galaxy_changed = True

        elif ev in ("CancelledSquadronApplication", "SquadronApplicationApproved",
                    "SquadronApplicationRejected"):
            pending = state.get("squadron_application") or {}
            squadron_name = raw.get("SquadronName") or pending.get("name")
            detail = {
                "CancelledSquadronApplication": "Application cancelled",
                "SquadronApplicationApproved": "Application approved",
                "SquadronApplicationRejected": "Application rejected",
            }[ev]
            state["squadron_application"] = None
            companion_features.record_squadron_activity(
                state, ev, squadron_name, raw.get("timestamp"), detail,
            )
            changed = True
            galaxy_changed = True

        elif ev == "InvitedToSquadron":
            squadron_name = raw.get("SquadronName")
            state["squadron_invitation"] = {
                "id": raw.get("SquadronID"), "name": squadron_name,
                "timestamp": raw.get("timestamp"),
            }
            companion_features.record_squadron_activity(
                state, ev, squadron_name, raw.get("timestamp"), "Invitation received",
            )
            changed = True
            galaxy_changed = True

        elif ev == "SharedBookmarkToSquadron":
            squadron_name = raw.get("SquadronName") or (state.get("squadron") or {}).get("name")
            companion_features.record_squadron_item(
                state, "squadron_bookmarks", ev, squadron_name, raw.get("timestamp"),
                "Bookmark shared in Elite",
            )
            companion_features.record_squadron_activity(
                state, ev, squadron_name, raw.get("timestamp"), "Bookmark shared",
            )
            changed = True
            galaxy_changed = True

        elif ev == "WonATrophyForSquadron":
            squadron_name = raw.get("SquadronName") or (state.get("squadron") or {}).get("name")
            companion_features.record_squadron_item(
                state, "squadron_trophies", ev, squadron_name, raw.get("timestamp"),
                "Trophy win reported by the journal",
            )
            companion_features.record_squadron_activity(
                state, ev, squadron_name, raw.get("timestamp"), "Squadron trophy won",
            )
            changed = True
            galaxy_changed = True

        elif ev == "LeaveBody":
            self.bio_sampling = None
            self.bio_sample_points = []
            self._sample_clear_announced = False
            self._update_sampling_clearance()

        elif ev == "Died" and not startup_replay:
            state["unsold_exploration_cr"] = 0
            state["unsold_bio_cr"] = 0
            state["unsold_bio_bonus_potential_cr"] = 0
            state["unsold_scan_keys"] = []
            self._data_risk_level = 0
            changed = True

        if ev in ("Location", "FSDJump", "CarrierJump"):
            state["galaxy_system"] = raw.get("StarSystem") or self.current_sys
            state["controlling_faction"] = (raw.get("SystemFaction") or {}).get("Name")
            state["factions"] = self._normalise_galaxy_factions(raw.get("Factions") or [])
            state["conflicts"] = self._normalise_conflicts(raw.get("Conflicts") or [])
            if raw.get("ControllingPower") or raw.get("Powers"):
                state["pp_system"] = {
                    "controlling": raw.get("ControllingPower"), "powers": raw.get("Powers") or [],
                    "state": raw.get("PowerplayState"),
                    "control_progress": raw.get("PowerplayStateControlProgress"),
                    "reinforcement": raw.get("PowerplayStateReinforcement"),
                    "undermining": raw.get("PowerplayStateUndermining"),
                }
            else:
                state["pp_system"] = None
            state["galaxy_system_updated"] = raw.get("timestamp") or time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            state["galaxy_system_source"] = ev
            for faction_name, detail in companion_features.update_faction_watch_snapshots(
                    state, state["galaxy_system"], state["factions"],
                    state["controlling_faction"], notify=not startup_replay):
                self._toast_on_main("FACTION WATCH", f"{faction_name}: {detail}", "info", 14)
            changed = True
            galaxy_changed = True

        if galaxy_changed:
            state["galaxy_updated"] = raw.get("timestamp") or time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            state["galaxy_source"] = ev

        if not startup_replay:
            if ev == "Scan":
                changed = self._record_unsold_scan(raw) or changed
            elif ev == "ScanOrganic":
                changed = self._process_sampling_event(raw, data) or changed
                if getattr(self, "cockpit_memory", None):
                    self.cockpit_memory.check_bio_sell_anticipation(state.get("unsold_bio_samples"))
            elif ev in ("SellExplorationData", "MultiSellExplorationData"):
                state["unsold_exploration_cr"] = 0
                state["unsold_scan_keys"] = []
                self._data_risk_level = 0
                self._clear_sold_data_warnings()
                changed = True
            elif ev == "SellOrganicData":
                sold_count = int(state.get("unsold_bio_samples") or 0)
                if sold_count > 0 and getattr(self, "cockpit_memory", None):
                    self.cockpit_memory.record_bio_sale(sold_count)
                state["unsold_bio_cr"] = 0
                state["unsold_bio_bonus_potential_cr"] = 0
                state["unsold_bio_samples"] = 0
                self._data_risk_level = 0
                self._clear_sold_data_warnings(biological=True)
                changed = True

        if changed:
            self._save_companion_state()
            self._refresh_companion_surfaces()
        self._check_rebuy_warning(raw if ev in ("Loadout", "LoadGame") else None,
                                  notify=not startup_replay)
        sale_event = ev in (
            "SellExplorationData", "MultiSellExplorationData", "SellOrganicData",
        )
        # A sale may leave the other data category unsold. Recompute its level
        # silently; resetting to zero and notifying here made the sale itself
        # look like a fresh risk escalation.
        self._check_data_risk(notify=not startup_replay and not sale_event)

    def _prune_massacre_kills(self):
        active = {row["faction"] for row in companion_features.massacre_stacks(self.companion_state)}
        self.companion_state["faction_kills"] = {
            faction: count for faction, count in self.companion_state.get("faction_kills", {}).items()
            if faction in active
        }

    def _update_powerplay_state(self, ev, raw):
        if ev == "PowerplayLeave":
            self.companion_state["powerplay"] = None
            return
        current = dict(self.companion_state.get("powerplay") or {})
        defaults = {
            "session_merits": 0, "session_collected": 0, "session_delivered": 0,
            "session_fast_track_cr": 0, "session_salary_cr": 0,
            "commodities_collected": {}, "commodities_delivered": {}, "activity": [],
        }
        for name, value in defaults.items():
            current.setdefault(name, value.copy() if isinstance(value, (dict, list)) else value)

        def display_type():
            return self._journal_display_name(
                raw.get("Type_Localised") or raw.get("Type"), "Powerplay commodity"
            )

        def record(detail, **extra):
            action = {
                "event": ev,
                "timestamp": raw.get("timestamp"),
                "detail": detail,
                "power": raw.get("ToPower") or raw.get("Power") or current.get("power"),
                "system": getattr(self, "current_sys", None),
                **extra,
            }
            current["last_action"] = action
            current["activity"] = (list(current.get("activity") or []) + [action])[-30:]

        if ev == "Powerplay":
            current.update(power=raw.get("Power"), rank=raw.get("Rank"), merits=raw.get("Merits"),
                           time_pledged_s=raw.get("TimePledged"))
            record(f"Pledge status refreshed for {raw.get('Power') or 'current power'}")
        elif ev in ("PowerplayJoin", "PowerplayDefect"):
            current = {
                **defaults,
                "power": raw.get("ToPower") or raw.get("Power"), "rank": 0,
                "merits": 0, "time_pledged_s": 0,
            }
            transition = "Defected" if ev == "PowerplayDefect" else "Pledged"
            record(f"{transition} to {current.get('power') or 'a power'}",
                   from_power=raw.get("FromPower"))
        elif ev == "PowerplayRank":
            previous_rank = current.get("rank")
            current.update(power=raw.get("Power"), rank=raw.get("Rank"))
            record(f"Rank changed from {previous_rank} to {raw.get('Rank')}",
                   previous_rank=previous_rank, rank=raw.get("Rank"))
        elif ev == "PowerplayMerits":
            gained = int(raw.get("MeritsGained") or 0)
            current.update(power=raw.get("Power"), merits=raw.get("TotalMerits"),
                           session_merits=int(current.get("session_merits") or 0) + gained)
            record(f"Gained {gained:,} merits", count=gained,
                   total_merits=int(raw.get("TotalMerits") or 0))
        elif ev in ("PowerplayCollect", "PowerplayDeliver"):
            commodity = display_type()
            count = int(raw.get("Count") or 0)
            verb = "collected" if ev == "PowerplayCollect" else "delivered"
            field = "commodities_collected" if ev == "PowerplayCollect" else "commodities_delivered"
            session_field = "session_collected" if ev == "PowerplayCollect" else "session_delivered"
            values = dict(current.get(field) or {})
            values[commodity] = int(values.get(commodity) or 0) + count
            current[field] = values
            current[session_field] = int(current.get(session_field) or 0) + count
            record(f"{verb.title()} {count:,} {commodity}", commodity=commodity, count=count)
        elif ev == "PowerplayFastTrack":
            cost = int(raw.get("Cost") or 0)
            current["session_fast_track_cr"] = int(current.get("session_fast_track_cr") or 0) + cost
            record(f"Fast-tracked allocation for {cost:,} credits", amount_cr=cost)
        elif ev == "PowerplaySalary":
            amount = int(raw.get("Amount") or 0)
            current["session_salary_cr"] = int(current.get("session_salary_cr") or 0) + amount
            record(f"Received {amount:,} credits in Powerplay salary", amount_cr=amount)
        elif ev == "PowerplayVote":
            votes = int(raw.get("Votes") or 0)
            record(f"Cast {votes:,} consolidation votes", count=votes,
                   target_system=raw.get("System"))
        elif ev == "PowerplayVoucher":
            systems = list(raw.get("Systems") or [])
            record(f"Received Powerplay vouchers for {len(systems)} system(s)", systems=systems[:20])
        self.companion_state["powerplay"] = current

    @staticmethod
    def _normalise_galaxy_factions(factions):
        rows = []
        for faction in factions:
            rows.append({
                "name": faction.get("Name"), "state": faction.get("FactionState"),
                "government": faction.get("Government"), "influence": faction.get("Influence"),
                "allegiance": faction.get("Allegiance"), "my_reputation": faction.get("MyReputation"),
                "active_states": [row.get("State") for row in faction.get("ActiveStates") or []],
                "pending_states": [row.get("State") for row in faction.get("PendingStates") or []],
                "recovering_states": [row.get("State") for row in faction.get("RecoveringStates") or []],
            })
        return sorted(rows, key=lambda row: -(row.get("influence") or 0))

    @staticmethod
    def _normalise_conflicts(conflicts):
        def side(row):
            row = row or {}
            return {"name": row.get("Name"), "stake": row.get("Stake"), "won_days": row.get("WonDays")}
        return [{"war_type": row.get("WarType"), "status": row.get("Status"),
                 "faction1": side(row.get("Faction1")), "faction2": side(row.get("Faction2"))}
                for row in conflicts]

    def _record_unsold_scan(self, raw):
        body_id = raw.get("BodyID")
        key = f"{raw.get('SystemAddress')}:{body_id}"
        keys = self.companion_state.setdefault("unsold_scan_keys", [])
        if body_id is None or key in keys:
            return False
        planet_class = raw.get("PlanetClass")
        star_type = raw.get("StarType")
        terraformable = raw.get("TerraformState") == "Terraformable"
        mass = raw.get("MassEM") or raw.get("StellarMass") or 0
        value = self._get_body_value(
            planet_class, star_type, terraformable, mass,
            not bool(raw.get("WasDiscovered")), bool(raw.get("WasMapped")),
            not bool(raw.get("WasMapped")), True,
        )
        keys.append(key)
        self.companion_state["unsold_exploration_cr"] = int(self.companion_state.get("unsold_exploration_cr") or 0) + int(value or 0)
        return True

    def _process_sampling_event(self, raw, data):
        scan_type = str(raw.get("ScanType") or data.get("scan_type") or "").lower()
        species = data.get("species") or raw.get("Species_Localised") or raw.get("Species") or "Organic"
        genus = data.get("genus") or raw.get("Genus_Localised") or raw.get("Genus") or species.split(" ")[0]
        body = data.get("body_id") if data.get("body_id") is not None else raw.get("Body")
        point = None
        if self.current_latitude is not None and self.current_longitude is not None:
            point = {"lat": self.current_latitude, "lon": self.current_longitude, "body": body}
        if scan_type in ("log", "sample"):
            if not self.bio_sampling or self.bio_sampling.get("species") != species or self.bio_sampling.get("body") != body:
                self.bio_sample_points = []
            if point:
                self.bio_sample_points.append(point)
            self.bio_sampling = {
                "species": species, "genus": genus, "body": body,
                "progress": 1 if scan_type == "log" else 2,
                "colony_m": bio_values.GENUS_COLONY_M.get(genus),
            }
            self._sample_clear_announced = False
            self._update_sampling_clearance()
            return False
        if scan_type == "analyse" or data.get("is_complete"):
            body_item = self.scan_items_by_id.get(self._normalize_body_id(body), {})
            base_value = int(bio_values.species_value(species) or 0)
            self.companion_state["unsold_bio_cr"] = int(
                self.companion_state.get("unsold_bio_cr") or 0
            ) + base_value
            if body_item.get("first_footfall"):
                self.companion_state["unsold_bio_bonus_potential_cr"] = int(
                    self.companion_state.get("unsold_bio_bonus_potential_cr") or 0
                ) + base_value * 4
            self.companion_state["unsold_bio_samples"] = int(self.companion_state.get("unsold_bio_samples") or 0) + 1
            self.bio_sampling = None
            self.bio_sample_points = []
            self._sample_clear_announced = False
            self._update_sampling_clearance()
            return True
        return False

    def _sampling_snapshot(self):
        if not self.bio_sampling:
            return None
        snapshot = dict(self.bio_sampling)
        position = {
            "lat": self.current_latitude, "lon": self.current_longitude,
            "body": self.bio_sampling.get("body"), "radius_m": self.current_planet_radius,
        }
        clearance = companion_features.sample_clearance(
            self.bio_sample_points, position, snapshot.get("colony_m"),
        )
        if clearance:
            snapshot.update(clearance)
        return snapshot

    def _update_sampling_clearance(self):
        sample = self._sampling_snapshot()
        if (sample and sample.get("clear") and not self._sample_clear_announced
                and self.config.get("sample_clear_notifications_enabled", True)):
            self._sample_clear_announced = True
            self._toast_on_main(
                "CLEAR TO SAMPLE", f"{sample['species']} · {sample.get('min_distance_m', 0):,} m", "success", 10,
                (f"Clear to sample {sample['species']}.",
                 f"My bio sensors confirm colony spacing. You may sample {sample['species']} again.",
                 f"We are clear of the previous colony. I have authorized the next {sample['species']} sample.",
                 f"Sampling radius clear. The genetic sampler is ready for {sample['species']}."),
                "exploration", "clear-to-sample",
            )
        if self.survey_status_hud:
            self.root.after(0, lambda s=sample: self.survey_status_hud.update(
                self.current_sys, self.scanned, self.total, self.scan_items, self.body_signals, sampling=s,
                focused_body_id=self.current_body_id,
                focused_body_name=self.current_body_name,
            ))
        if getattr(self, "exploration_window", None) and self.exploration_window.is_open():
            self.root.after(0, self.exploration_window._render_sampling)

    def _check_rebuy_warning(self, event=None, notify=True):
        notify = bool(notify and self.config.get("rebuy_warnings_enabled", True))
        loadout = self.companion_state.get("loadout") or {}
        rebuy = (event or {}).get("Rebuy") or loadout.get("Rebuy") or self.cmdr_ship.get("rebuy")
        credits = (event or {}).get("Credits")
        if credits is None:
            credits = self.cmdr_balance
        if not rebuy or credits is None:
            return
        level = 2 if credits < rebuy else (1 if credits < rebuy * 2 else 0)
        if notify and level > self._rebuy_warning_level:
            if level == 2:
                self._toast_on_main(
                    "REBUY NOT COVERED", "Current balance cannot cover ship insurance", "fail", 18,
                    ("Warning. Current balance cannot cover ship insurance.",
                     "Our credit balance cannot cover a rebuy.",
                     "Insurance shortfall detected. I strongly recommend protecting the ship."), voice_key="rebuy-uncovered",
                )
            else:
                self._toast_on_main(
                    "LOW REBUY COVER", "Current balance is below two rebuys", "warn", 15,
                    ("Warning. Current balance is below two rebuys.",
                     "Our rebuy reserve is getting thin.",
                     "A little financial caution from your ship computer. We have less than two rebuys available."), voice_key="rebuy-low",
                )
        self._rebuy_warning_level = level

    def _check_data_risk(self, notify=True):
        notify = bool(notify and self.config.get("data_risk_warnings_enabled", True))
        loadout = self.companion_state.get("loadout") or {}
        rebuy = loadout.get("Rebuy") or self.cmdr_ship.get("rebuy")
        total = int(self.companion_state.get("unsold_exploration_cr") or 0) + int(self.companion_state.get("unsold_bio_cr") or 0)
        if not rebuy or total < 20_000_000:
            self._data_risk_level = 0 if total < 20_000_000 else self._data_risk_level
            return
        ratio = total / rebuy
        level = 3 if ratio >= 50 else 2 if ratio >= 25 else 1 if ratio >= 10 else 0
        if notify and level > self._data_risk_level:
            self._toast_on_main(
                "DATA AT RISK", f"Approximately {total / 1_000_000:.0f}M CR unsold · {ratio:.0f}× rebuy",
                "fail" if level == 3 else "warn", 18,
                ("Warning. Valuable exploration data is at risk.",
                 "My ledger shows a fortune in unsold survey data.",
                 "Our exploration data is worth far more than the ship. I recommend finding a buyer.",
                 "I would rather not lose this archive. We should sell our survey data."),
                voice_key=f"data-risk-{level}",
            )
        self._data_risk_level = level

    # ── Engineer material helpers ─────────────────────────────────────────────

    def _process_engineer_progress(self, raw: dict):
        """Persist EngineerProgress batch snapshots and live rank/access updates."""
        engineers = self.engineer_materials.setdefault("engineers", {})

        def entry(item):
            return {
                "progress": item.get("Progress"),
                "rank": item.get("Rank"),
                "rank_progress": item.get("RankProgress"),
            }

        if raw.get("Engineers") is not None:
            engineers.clear()
            engineers.update({
                item["Engineer"]: entry(item)
                for item in (raw.get("Engineers") or []) if item.get("Engineer")
            })
        elif raw.get("Engineer"):
            engineers[raw["Engineer"]] = entry(raw)
        else:
            return
        self._save_engineer_materials(self.engineer_materials)
        if self.engineer_window and self.engineer_window.is_open():
            self.root.after(0, self.engineer_window.refresh)

    def update_ship_locker(self, data):
        """Marshal ShipLocker.json updates from the watcher onto the Tk thread."""
        try:
            self.root.after(0, lambda payload=dict(data or {}): self._apply_ship_locker(payload))
        except Exception:
            pass

    def _apply_ship_locker(self, data: dict):
        groups = {"items": "Items", "components": "Components",
                  "data": "Data", "consumables": "Consumables"}
        locker = {}
        for out_key, source_key in groups.items():
            rows = data.get(source_key)
            if rows is None:
                return
            counts = {}
            for item in rows:
                name = item.get("Name_Localised") or (item.get("Name") or "").replace("_", " ").title()
                if name:
                    counts[name] = counts.get(name, 0) + int(item.get("Count") or 0)
            locker[out_key] = [
                {"name": name, "count": count}
                for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
            ]
        self.engineer_materials["ship_locker"] = locker
        self._save_engineer_materials(self.engineer_materials)
        if self.engineer_window and self.engineer_window.is_open():
            self.engineer_window.refresh()

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
        ready_before = ready_blueprints(self.engineer_materials) if ev == "MaterialCollected" else set()

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

        if ev == "MaterialCollected":
            for blueprint in sorted(ready_blueprints(self.engineer_materials) - ready_before):
                pin = next((row for row in self.engineer_materials.get("pinned_blueprints", [])
                            if row.get("name") == blueprint), {})
                grade = int(pin.get("target_grade", pin.get("grade", 5)))
                quantity = max(1, int(pin.get("quantity", 1)))
                quantity_text = f" for {quantity} modules" if quantity > 1 else ""
                quantity_badge = f" · {quantity} modules" if quantity > 1 else ""
                if self.toast_hud:
                    self.root.after(0, lambda name=blueprint, target_grade=grade, qty_badge=quantity_badge: self.toast_hud.push(
                        "READY TO ENGINEER",
                        f"{name} G{target_grade} materials complete{qty_badge}",
                        severity="info",
                        duration_s=12,
                    ))
                self._speak(
                    (f"Materials complete for {blueprint}, grade {grade}{quantity_text}.",
                     f"Engineering inventory reconciled. {blueprint}, grade {grade}{quantity_text}, is ready.",
                     f"I have confirmed every material for {blueprint}, grade {grade}{quantity_text}.",
                     f"Fabrication requirements satisfied. We can engineer {blueprint} to grade {grade}{quantity_text}."),
                    category="objectives", cooldown_s=300,
                    key=f"engineering-ready:{blueprint}:{grade}",
                )

    def process_batch(self, events):
        startup_batch = any(
            bool(event.get("startup_catchup"))
            for event in events if isinstance(event, dict)
        )
        startup_final = any(
            bool(event.get("startup_catchup_final"))
            for event in events if isinstance(event, dict)
        )
        if startup_batch:
            self._startup_restore_active = True
            self._startup_restore_ui_pending = True
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
                self._request_db_commit(reason="journal_batch")
        finally:
            self.batch_mode = False
        try:
            specialist_engine = getattr(self, "specialist_engine", None)
            if specialist_engine:
                specialist_engine.flush(wait=False)
        except Exception as exc:
            logging.warning("Specialist workflow batch flush failed: %s", exc)

        # Startup catch-up may span many watcher cycles. Keep every partial
        # batch silent and draw only after the watcher marks the final batch.
        if startup_batch and not startup_final:
            return

        if startup_final or self.is_first_load:
            self._startup_restore_active = False
            self._startup_restore_ui_pending = False
            self._cached_cockpit_state_loaded = False
            self.dashboard_refresh_full_pending = False
            self.is_first_load = False
            self._startup_recovery_mode = False
            self._apply_adaptive_overlay_scene()
            self._adaptive_startup_briefing()
            self._publish_expedition_resume_briefing()
            try:
                self.root.title(f"VOID COMPASS // v{APP_VERSION}")
            except Exception:
                pass
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
        # Journal events commonly arrive in batches.  Per-event Survey Status
        # redraws are deliberately suppressed while a batch is active, so
        # perform one coalesced refresh now that the committed scan totals are
        # authoritative (for example, after FSSAllBodiesFound changes 10/11 to
        # 11/11).
        self._refresh_system_info_progress()
        self._refresh_cockpit_brain(event="journal_batch")
        self._refresh_commander_profile_window()
        self._refresh_value_ledger_window()
        self._refresh_colonisation_planner_window()
        self._refresh_exploration_window()
        self._refresh_bgs_window()
        window = getattr(self, "specialists_window", None)
        if window and window.is_open() and getattr(self, "_active_page", None) == "SPECIALISTS":
            self.root.after(0, window.refresh)

    def update_cargo(self, inventory, vessel="Ship"):
        self.last_cargo_event_ts = time.time()
        self.current_cargo_inventory = list(inventory or [])
        self.edsm.queue_cargo_snapshot(self.current_cargo_inventory, vessel=vessel)
        try:
            specialist_engine = getattr(self, "specialist_engine", None)
            if specialist_engine:
                specialist_engine.update_cargo(self.current_cargo_inventory)
        except Exception as exc:
            logging.debug("Specialist cargo snapshot skipped: %s", exc)
        self.current_cargo_tons = sum(
            int(item.get("Count", item.get("count", 0)) or 0)
            for item in self.current_cargo_inventory
            if isinstance(item, dict)
        )
        if self.cargo_hud:
            inv = list(self.current_cargo_inventory)
            cap = self.cargo_capacity
            self.root.after(0, lambda: self.cargo_hud.update(inv, cap))
        if self.colony_overlay:
            self.root.after(0, self.colony_overlay.update)
        self._sync_cockpit_intentions()
        self._refresh_commander_profile_window()

    def _record_trade_session_event(self, ev, data):
        if not isinstance(data, dict):
            return
        commodity = data.get("Type_Localised") or data.get("Type") or data.get("commodity") or "Commodity"
        count = int(data.get("Count") or data.get("count") or 0)
        if count <= 0:
            return
        self.trade_session["transactions"] = int(self.trade_session.get("transactions") or 0) + 1
        if ev == "MarketBuy":
            price = int(data.get("BuyPrice") or data.get("Price") or 0)
            total = int(data.get("TotalCost") or (price * count))
            self.trade_session["bought_units"] += count
            self.trade_session["spent"] += total
            bought = self.trade_session.setdefault("commodities_bought", {})
            bought[commodity] = int(bought.get(commodity) or 0) + count
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
            sold = self.trade_session.setdefault("commodities_sold", {})
            sold[commodity] = int(sold.get(commodity) or 0) + count
            event = {
                "time": time.time(),
                "event": "SELL",
                "commodity": commodity,
                "count": count,
                "price": price,
                "profit": profit,
                "profit_per_ton": round(profit / count) if count else 0,
            }
            best = self.trade_session.get("best_sale")
            if not isinstance(best, dict) or profit > int(best.get("profit") or 0):
                self.trade_session["best_sale"] = dict(event)
            worst = self.trade_session.get("worst_sale")
            if not isinstance(worst, dict) or profit < int(worst.get("profit") or 0):
                self.trade_session["worst_sale"] = dict(event)
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
                window = getattr(self, "analytics_window", None)
                if window and window.is_open() and getattr(self, "_active_page", None) == "ANALYTICS":
                    self.root.after(0, window.request_refresh)
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
                self._ui_post(lambda e=exc: self.log(f"Trade market import failed: {e}"))
                continue

            if context.get("docked"):
                trade_eddn_uploader.set_enabled(bool(self.config.get("trade_eddn_upload_enabled", True)))
                trade_eddn_uploader.maybe_publish(data, self.cmdr_name, context)

            if not result.get("updated"):
                continue
            self._ui_post(
                lambda d=data, c=context, r=result: self._apply_market_import_result(d, c, r),
                key="market-import-result",
            )

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
        if self.route_plotter and self.route_plotter.win.winfo_exists():
            self.root.after(0, self.route_plotter.update_navigation_state)
