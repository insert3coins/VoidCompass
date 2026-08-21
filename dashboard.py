import os
import gc
import json
import threading
import math
import sqlite3
import logging
import sys
import time
import traceback
import tkinter as tk
from tkinter import messagebox
import webbrowser
import shutil
from collections import deque
from datetime import datetime, timezone

from config import (
    load_config, CONFIG_FILE,
    COLOR_BG, COLOR_ACCENT, COLOR_TEXT,
    apply_profile_config, commander_profile_key, get_active_profile,
    get_profile_dir, get_profile_file, save_config, save_active_profile_config,
)
import themes
import overlay_chrome
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
from mining_data import MINING_MATERIALS
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
from html_canvas_overlay import attach_html_canvas_overlay
from html_survey_overlay import attach_html_survey_overlay
from overlay_input import set_mouse_passthrough
from runtime_trace import RuntimeTrace
from dashboard_db_mixin import DashboardDBMixin
from dashboard_ui_mixin import DashboardUIMixin
from dashboard_scan_mixin import DashboardScanMixin
from colonization_window import ColonizationWindow, save_colonisation_data, load_colonisation_data
from engineer_window import (
    EngineerWindow, load_engineer_materials,
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
from analytics_window import AnalyticsWindow
from trade.eddn_upload import UPLOADER as eddn_market_uploader
from achievement_engine import AchievementEngine
from achievement_window import AchievementWindow
from combat_awareness import CombatAwareness
from specialist_engine import SpecialistEngine
from specialists_window import SpecialistsWindow
from captains_log import CaptainsLog
from deep_survey import DeepSurveyTracker
from exploration_intelligence import build_intelligence, checkpoint_payload
from galactic_regions import find_region
from explorer_fieldcraft import (
    HIGH_VALUE_WORLDS, WHITE_DWARF_CLASSES, revisit_candidate,
    route_safety_forecast, surface_trail_snapshot,
)
from expedition_manager import ExpeditionManager
from diagnostic_logs import application_base_dir, resolve_log_path
from adaptive_command import (
    AdaptiveCommandDeck, AUTOMATIC_MODE_IDLE_S, FOCUSED_MODES, MODE_LABELS,
)
from diagnostic_bundle import create_support_bundle
from onboarding import should_show as should_show_onboarding, show_first_run
from onboarding_splash import show_startup_boot
from persistence_queue import flush_persistence, persistence_queue
from session_recovery import ProfileSessionGuard
from ui_dispatcher import TkDispatcher
from global_hotkeys import GlobalHotkeyManager, OVERLAY_HOTKEY_SPECS
from platform_support import default_screenshot_path, open_path
from overlay_layout import OverlayLayoutStudio
from ui_theme import apply_ui_scale
from profile_backups import automatic_backup


# One burst of journal events describes a single moment, so the shared
# exploration fact packet is reused for that long instead of being rebuilt
# for every event in the batch.
EXPLORATION_INTELLIGENCE_TTL_S = 0.5
# How long the Navigation HUD marks a freshly entered Codex region.
HUD_REGION_CROSSED_S = 45.0
# Sagittarius A* in Elite's Sol-centred X/Y/Z journal coordinate frame.  The
# X/Z plane is the galactic disc and Y is height above/below it.
GALACTIC_CENTRE_XZ = (25.21875, 25899.96875)


def _journal_epoch(value, default=None):
    """Return one journal ISO timestamp as Unix time without local-time drift."""
    try:
        return datetime.fromisoformat(
            str(value or "").replace("Z", "+00:00")
        ).timestamp()
    except (TypeError, ValueError):
        return default


def _galactic_vector_context(current_coords, next_coords):
    """Describe a route leg in galactocentric exploration language."""
    try:
        current = tuple(float(value) for value in current_coords[:3])
        target = tuple(float(value) for value in next_coords[:3])
    except (TypeError, ValueError, IndexError):
        return {}
    if len(current) < 3 or len(target) < 3:
        return {}
    dx, dy, dz = (
        target[0] - current[0],
        target[1] - current[1],
        target[2] - current[2],
    )
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    planar = math.hypot(dx, dz)
    if distance < 0.01 or planar < 0.01:
        return {}

    # The radial vector points from Sagittarius A* to the current system.
    # Clockwise travel viewed from galactic north is spinward; at Sol this is
    # approximately -X, matching the established explorer-map convention.
    radial_x = current[0] - GALACTIC_CENTRE_XZ[0]
    radial_z = current[2] - GALACTIC_CENTRE_XZ[1]
    radial_length = math.hypot(radial_x, radial_z)
    if radial_length < 1.0:
        radial_x, radial_z, radial_length = 0.0, -1.0, 1.0
    unit_x, unit_z = radial_x / radial_length, radial_z / radial_length
    coreward = -(dx * unit_x + dz * unit_z)
    spinward = dx * unit_z - dz * unit_x
    if abs(coreward) >= abs(spinward):
        direction = "COREWARD" if coreward >= 0 else "RIMWARD"
    else:
        direction = "SPINWARD" if spinward >= 0 else "TRAILING"

    target_height = target[1]
    if target_height >= 50.0:
        plane = f"ABOVE {abs(target_height):,.0f} LY"
    elif target_height <= -50.0:
        plane = f"BELOW {abs(target_height):,.0f} LY"
    else:
        plane = "GALACTIC PLANE"
    vertical = "ASCENDING" if dy > max(10.0, planar * 0.45) else (
        "DESCENDING" if dy < -max(10.0, planar * 0.45) else ""
    )
    return {
        "direction": direction,
        "plane": plane,
        "vertical": vertical,
        "distance_ly": distance,
        "label": " · ".join(part for part in (direction, plane) if part),
    }


def _preserve_unconfirmed_scan_total(startup_replay, event_data, incoming_system,
                                     current_system, current_confirmed,
                                     cached_loaded=False, cached_system=None,
                                     cached_confirmed=False):
    """Keep startup-only body floors from masquerading as confirmed totals.

    The final startup location seed deliberately repeats the newest arrival.
    If the only evidence since that arrival is an automatic primary-star Scan,
    SQLite contains 1/1 as a storage floor—not proof that the system has one
    body. A known revisit remains confirmed because ``current_confirmed`` was
    restored before the duplicate seed arrives.
    """
    if not startup_replay:
        return False
    seed_repeats_unconfirmed_arrival = bool(
        (event_data or {}).get("startup_location_seed")
        and incoming_system == current_system
        and not current_confirmed
    )
    cached_state_was_unconfirmed = bool(
        cached_loaded
        and incoming_system == cached_system
        and not cached_confirmed
    )
    return seed_repeats_unconfirmed_arrival or cached_state_was_unconfirmed


class StartupCancelled(Exception):
    """Internal clean-exit signal for an abandoned first commissioning."""


class MainDashboard(DashboardScanMixin, DashboardUIMixin, DashboardDBMixin):
    _SURVEY_REFRESH_EVENTS = frozenset({
        "Location", "FSDJump", "CarrierJump", "StartJump",
        "Docked", "Undocked", "ApproachBody", "LeaveBody",
        "FSSDiscoveryScan", "DiscoveryScan", "NavBeaconScan",
        "FSSAllBodiesFound", "FSSBodySignals", "SAASignalsFound",
        "SAAScanComplete", "Scan", "ScanOrganic",
    })

    # Short, live-only Navigation HUD animations. Tuple values are:
    # (motion kind, lane, theme tone, duration seconds, batch priority).
    _NAV_HUD_EVENT_SPECS = {
        "LoadGame": ("wake", "all", "accent", 1.6, 20),
        "NavRoute": ("route_set", "left", "orange", 1.4, 58),
        "NavRouteClear": ("route_clear", "left", "muted", 1.1, 58),
        "FSDTarget": ("route_target", "left", "orange", 1.0, 45),
        "StartJump": ("jump_charge", "all", "orange", 1.7, 90),
        "FSDJump": ("arrival", "all", "accent", 1.8, 95),
        "CarrierJump": ("carrier_arrival", "all", "accent", 2.8, 95),
        "SupercruiseEntry": ("supercruise_enter", "center", "orange", 1.2, 62),
        "SupercruiseExit": ("supercruise_exit", "center", "accent", 1.2, 62),
        "SupercruiseDestinationDrop": ("supercruise_drop", "center", "orange", 1.0, 61),
        "USSDrop": ("signal_drop", "center", "yellow", 1.4, 72),
        "Interdicted": ("interdiction", "all", "orange", 1.8, 99),
        "EscapeInterdiction": ("interdiction_clear", "all", "green", 1.5, 96),
        "DockingRequested": ("dock_request", "center", "green", 1.2, 60),
        "DockingGranted": ("dock_request", "center", "green", 1.2, 60),
        "DockingCancelled": ("dock_denied", "center", "yellow", 1.1, 65),
        "DockingDenied": ("dock_denied", "center", "orange", 1.3, 75),
        "DockingTimeout": ("dock_denied", "center", "yellow", 1.2, 70),
        "Docked": ("dock", "center", "accent", 1.5, 78),
        "Undocked": ("undock", "center", "accent", 1.3, 78),
        "Touchdown": ("touchdown", "center", "accent", 1.3, 68),
        "Liftoff": ("liftoff", "center", "orange", 1.3, 68),
        "ApproachBody": ("body_approach", "center", "accent", 1.1, 42),
        "LeaveBody": ("planet_clear", "all", "green", 2.0, 74),
        "LaunchSRV": ("vehicle_deploy", "center", "accent", 1.4, 68),
        "DockSRV": ("vehicle_board", "center", "accent", 1.4, 68),
        "LaunchFighter": ("vehicle_deploy", "center", "accent", 1.4, 68),
        "DockFighter": ("vehicle_board", "center", "accent", 1.4, 68),
        "FighterDestroyed": ("warning", "all", "orange", 1.6, 98),
        "SRVDestroyed": ("warning", "all", "orange", 1.6, 98),
        "VehicleSwitch": ("vehicle_switch", "center", "accent", 1.2, 64),
        "Embark": ("vehicle_board", "center", "accent", 1.3, 66),
        "Disembark": ("vehicle_deploy", "center", "accent", 1.3, 66),
        "JoinACrew": ("vehicle_board", "center", "accent", 1.3, 66),
        "QuitACrew": ("vehicle_switch", "center", "accent", 1.2, 64),
        "EndCrewSession": ("vehicle_switch", "center", "accent", 1.2, 64),
        "DiscoveryScan": ("honk", "right", "accent", 1.5, 52),
        "NavBeaconScan": ("honk", "right", "accent", 1.5, 52),
        "FSSDiscoveryScan": ("fss_progress", "right", "accent", 1.1, 54),
        "FSSSignalDiscovered": ("fss_signal", "right", "accent", 1.0, 44),
        "Scan": ("body_scan", "right", "accent", 1.1, 50),
        "ScanBaryCentre": ("body_scan", "right", "accent", 1.1, 50),
        "DatalinkScan": ("body_scan", "right", "accent", 1.1, 50),
        "DataScanned": ("body_scan", "right", "accent", 1.1, 50),
        "FSSBodySignals": ("signals", "right", "yellow", 1.3, 62),
        "SAASignalsFound": ("signals", "right", "yellow", 1.3, 62),
        "FSSAllBodiesFound": ("survey_complete", "right", "green", 1.9, 84),
        "SAAScanComplete": ("mapping_complete", "right", "green", 1.7, 82),
        "ScanOrganic": ("bio_sample", "right", "green", 1.6, 72),
        "CodexEntry": ("codex", "right", "yellow", 1.7, 76),
        "SellExplorationData": ("data_sale", "right", "green", 1.8, 80),
        "MultiSellExplorationData": ("data_sale", "right", "green", 1.8, 80),
        "SellOrganicData": ("data_sale", "right", "green", 1.8, 80),
        "ProspectedAsteroid": ("prospector_scan", "right", "yellow", 1.7, 62),
        "MiningRefined": ("mining_refined", "right", "green", 1.4, 60),
        "HeatWarning": ("warning", "all", "orange", 1.6, 100),
        "HeatDamage": ("warning", "all", "orange", 1.8, 100),
        "HullDamage": ("warning", "all", "orange", 1.6, 100),
        "CockpitBreached": ("warning", "all", "orange", 2.0, 100),
        "UnderAttack": ("warning", "all", "orange", 1.6, 100),
        "JetConeDamage": ("warning", "all", "orange", 1.6, 100),
        "SystemsShutdown": ("warning", "all", "orange", 2.0, 100),
        "SelfDestruct": ("warning", "all", "orange", 2.0, 100),
        "Died": ("warning", "all", "orange", 1.9, 100),
    }

    _COCKPIT_STATE_FILE = "last_cockpit_state.json"
    _COCKPIT_STATE_SCHEMA = 1
    _COCKPIT_STATE_FIELDS = (
        "current_sys", "_navigation_system_arrival_epoch",
        "previous_sys", "previous_coords",
        "current_system_address", "current_coords", "star_class",
        "scanned", "total", "scan_total_confirmed", "navigation_scan_progress",
        "navigation_scan_progress_source", "organic_count", "system_bio_signals",
        "system_traffic", "last_traffic_system", "valuable_system",
        "valuable_bodies", "body_signals", "belt_clusters", "system_undiscovered",
        "fss_all_bodies", "current_body_id", "current_body_name",
        "last_bio_scan", "bio_sampling", "bio_sample_points",
        "_survey_body_focus_suppressed",
        "cmdr_balance", "cmdr_loan", "cmdr_ranks", "cmdr_rank_progress",
        "cmdr_reputation", "cmdr_ship", "game_version", "game_build",
        "game_horizons", "game_odyssey", "current_station_name",
        "current_station_type", "current_station_market_id",
        "current_station_state",
        "current_station_economy", "current_station_economies",
        "current_station_government", "current_station_faction",
        "current_station_allegiance", "current_station_services",
        "current_station_dist_ls", "current_station_landing_pads",
        "current_docked", "hud_flight_state", "current_landed",
        "current_in_fighter", "current_in_srv", "current_on_foot",
        "current_in_taxi", "current_in_multicrew",
        "current_vehicle_id", "current_vehicle_name", "current_legal_state",
        "current_fuel_main", "current_fuel_reservoir", "fuel_capacity_main",
        "current_altitude_m", "current_landing_gear_down",
        "current_cargo_scoop_deployed", "current_analysis_mode",
        "current_scooping_fuel",
        "current_destination", "current_destination_details",
        "current_local_space_body_type", "current_local_space_name",
        "current_asteroid_field_kind",
        "neutron_boost_armed", "neutron_boost_value",
        "cargo_capacity", "current_cargo_tons",
        "current_cargo_inventory", "dest_coords", "dest_name", "route_list",
        "nav_route_entries", "current_latitude", "current_longitude",
        "current_heading", "current_planet_radius", "on_planet",
    )
    _COCKPIT_STATE_LIMITS = {
        "valuable_bodies": 64,
        "belt_clusters": 128,
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
    _HTML_CANVAS_OVERLAY_SPECS = {
        "cargo_hud": ("cargo", "Void Compass Cargo", "cargo_overlay_enabled"),
        "carrier_hud": ("carrier", "Void Compass Carrier", "carrier_overlay_enabled"),
        "prospector_hud": ("prospector", "Void Compass Prospector", "prospector_overlay_enabled"),
        "system_info_hud": ("system-info", "Void Compass System Intelligence", "system_info_enabled"),
        "gravity_warning_hud": ("gravity", "Void Compass Gravity Warning", "gravity_warning_overlay_enabled"),
        "station_info_hud": ("station", "Void Compass Station Link", "station_info_overlay_enabled"),
        "survey_status_hud": ("survey", "Void Compass Survey Operations", "survey_status_overlay_enabled"),
        "toast_hud": ("toast", "Void Compass Event Toast", "toast_overlay_enabled"),
        "heartbeat_hud": ("heartbeat", "Void Compass Journal Heartbeat", "heartbeat_overlay_enabled"),
        "colony_overlay": ("colony", "Void Compass Colony Logistics", "colony_overlay_enabled"),
    }

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

    def _bio_location_context(self):
        """Return ``(codex_region_id, coords)`` for the current system.

        Several published species requirements are bounded by galactic region
        or by distance to Guardian and Sinuous Tuber zones. Supplying the
        commander's position lets those be decided instead of reported as
        untested.
        """
        coords = getattr(self, "current_coords", None)
        try:
            position = tuple(float(value) for value in coords)[:3]
        except (TypeError, ValueError):
            return None, None
        if len(position) < 3:
            return None, None
        region = find_region(*position)
        return (region[0] if region else None), position

    def _bio_predictions_for_scan(self, scan_data):
        if not scan_data:
            return []
        region_id, coords = self._bio_location_context()
        return bio_values.predict_genera(
            scan_data.get("planet_class"),
            scan_data.get("atmosphere_type") or scan_data.get("atmosphere"),
            scan_data.get("surface_temp") or scan_data.get("temp_k"),
            scan_data.get("gravity_g") or self._gravity_to_g(scan_data.get("surface_gravity")),
            scan_data.get("volcanism"),
            scan_data.get("surface_pressure"),
            region_id,
            coords,
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

    def _scan_item_for_bio_body(self, body_id, body_name=""):
        """Return the persistent body row used by organic sample events.

        Startup hydration and older cache rows can leave the body index with a
        different key type even though the body is present in ``scan_items``.
        Resolve both forms, repair the index, and retain a minimal row as a
        final fallback so a valid ScanOrganic event is never presentation-only.
        """
        body_id = self._normalize_body_id(body_id)
        if body_id is None:
            return None

        item = self.scan_items_by_id.get(body_id)
        if item is None:
            item = self.scan_items_by_id.get(str(body_id))
        if item is None:
            item = next((
                candidate for candidate in self.scan_items
                if self._normalize_body_id(candidate.get("body_id")) == body_id
            ), None)
        if item is not None:
            self.scan_items_by_id[body_id] = item
            return item

        signals = (self.body_signals or {}).get(body_id, {})
        scan_data = (self.body_scan_data or {}).get(body_id, {})
        name = (
            body_name or signals.get("body_name")
            or scan_data.get("body_name") or f"Body {body_id}"
        )
        item = {
            "body_id": body_id,
            "name": name,
            "full_name": name,
            "planet_class": scan_data.get("planet_class") or "Unknown",
            "landable": bool(scan_data.get("landable", True)),
            "bio_count": int(signals.get("bio", 0) or 0),
            "geo_count": int(signals.get("geo", 0) or 0),
            "genuses": list(signals.get("genuses") or []),
            "dss_complete": bool(signals.get("dss_complete")),
            "organic_scans": {},
            "organic_complete_count": 0,
            "_ts": int(time.time()),
        }
        self._normalize_scan_item(item)
        self.scan_items.insert(0, item)
        self.scan_items = self.scan_items[:60]
        self.scan_items_by_id[body_id] = item
        return item

    def _persist_bio_scan_record(self, body_id, body_name, species_key, record):
        """Attach one organic step to its body and persist it atomically."""
        item = self._scan_item_for_bio_body(body_id, body_name)
        if item is None:
            return None
        organic_scans = item.setdefault("organic_scans", {})
        organic_scans[str(species_key)] = dict(record or {})
        item["organic_complete_count"] = sum(
            1 for scan in organic_scans.values()
            if isinstance(scan, dict) and scan.get("is_complete")
        )
        if item.get("_ts") is None:
            item["_ts"] = int(time.time())
        self.save_scan_item_to_db(self.current_sys, item)
        return item

    def _restore_current_system_bio_completions(self):
        """Repair completed biology omitted from the bounded startup replay."""
        watcher = getattr(self, "watcher", None)
        getter = getattr(watcher, "get_completed_organic_scans", None)
        if (not callable(getter) or not self.current_sys or self.current_sys == "---"
                or self.current_system_address is None):
            return 0
        try:
            raw_records = getter(self.current_system_address)
        except Exception as exc:
            logging.warning("Startup biology recovery failed: %s", exc)
            return 0

        restored = 0
        for raw in raw_records or ():
            try:
                normalized = watcher._normalize_event(raw)
                data = self._enrich_bio_event_context(normalized.get("data") or {})
                if not self._matches_current_system_address(data):
                    continue
                body_id = self._normalize_body_id(data.get("body_id"))
                if body_id is None:
                    continue
                item = self._scan_item_for_bio_body(body_id, data.get("body_name") or "")
                body_label = (
                    data.get("body_name") or (item or {}).get("name")
                    or f"Body {body_id}"
                )
                species = data.get("species") or data.get("genus") or "Organic"
                species_key = f"{body_id}|{species}"
                existing = self.last_bio_scan.get(species_key, {})
                max_samples = int(data.get("max_samples") or 3)
                record = {
                    "body_id": body_id,
                    "body_name": body_label,
                    "species": species,
                    "genus": data.get("genus"),
                    "variant": data.get("variant"),
                    "species_value": bio_values.species_value(species),
                    "genus_value": bio_values.genus_info(data.get("genus") or species),
                    "colony_m": bio_values.GENUS_COLONY_M.get(data.get("genus") or species),
                    "sample_idx": max_samples,
                    "max_samples": max_samples,
                    "scan_type": "Analyse",
                    "is_new_entry": bool(data.get("is_new_entry")),
                    "is_new_sample": False,
                    "is_complete": True,
                    "system_address": self.current_system_address,
                }
                self.last_bio_scan[species_key] = record
                body_records = (item or {}).get("organic_scans") or {}
                cached = body_records.get(species_key, {})
                if not (existing.get("is_complete") and cached.get("is_complete")):
                    self._persist_bio_scan_record(
                        body_id, body_label, species_key, record,
                    )
                    restored += 1
            except Exception as exc:
                logging.warning("Startup organic record recovery failed: %s", exc)

        if raw_records:
            self._rebuild_system_state_from_scan_items()
        return restored

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
        if "scan_total_confirmed" not in state:
            # Older snapshots could only express an inferred N/N body floor.
            # A partial system with a confirmed total is N/M, while explicit
            # completion leaves fss_all_bodies set.
            self.scan_total_confirmed = bool(
                self.fss_all_bodies
                or self.navigation_scan_progress_source == "fss"
                or int(self.total or 0) > int(self.scanned or 0)
            )
        self._cached_scan_total_confirmed = bool(self.scan_total_confirmed)
        self.body_signals = self._restore_int_key_dict(self.body_signals)
        if not isinstance(getattr(self, "belt_clusters", None), list):
            self.belt_clusters = []
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
        self._cached_cockpit_state_system = self.current_sys
        return bool(self.current_sys and self.current_sys != "---")

    def _hydrate_cached_system_scan_state(self):
        """Use the profile DB for body detail while the journal catches up."""
        if not getattr(self, "_cached_cockpit_state_loaded", False):
            return
        if not self.current_sys or self.current_sys in ("---", "Unknown"):
            return
        self.load_system_from_db(
            self.current_sys,
            preserve_total_confirmation=not bool(
                getattr(self, "_cached_scan_total_confirmed", False)
            ),
        )
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
                focused_body_id=(None if self._survey_body_focus_suppressed
                                 and not self.bio_sampling else self.current_body_id),
                focused_body_name=(None if self._survey_body_focus_suppressed
                                   and not self.bio_sampling else self.current_body_name),
                total_known=self.scan_total_confirmed,
                belt_clusters=list(self.belt_clusters),
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
        except Exception as exc:
            logging.warning("Could not apply profile theme %s: %s", theme_name, exc)
            return False

        success = True
        for attr in (
            "hud",
            "cargo_hud",
            "carrier_hud",
            "prospector_hud",
            "system_info_hud",
            "gravity_warning_hud",
            "station_info_hud",
            "survey_status_hud",
            "toast_hud",
            "heartbeat_hud",
            "colony_overlay",
        ):
            overlay = getattr(self, attr, None)
            apply_overlay_theme = getattr(overlay, "apply_theme", None)
            if not callable(apply_overlay_theme):
                continue
            try:
                apply_overlay_theme(palette)
            except Exception as exc:
                success = False
                logging.warning(
                    "Could not apply profile theme %s to %s: %s",
                    theme_name, attr, exc,
                )
        # The HTML Galactic Atlas consumes the same live palette as native
        # panels. Publishing a fresh immutable snapshot updates its CSS and
        # WebGL materials without reloading the browser page.
        map_view = getattr(
            getattr(self, "exploration_window", None),
            "expedition_map_view", None,
        )
        if map_view is not None:
            try:
                map_view.refresh()
            except Exception as exc:
                success = False
                logging.warning(
                    "Could not publish theme %s to Galactic Atlas: %s",
                    theme_name, exc,
                )
        return success

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
        # The Studio temporarily exposes hidden overlays and keeps references to
        # their windows. Close it while they still belong to the outgoing
        # commander, so positions/geometry are saved to the correct profile and
        # the new commander's visibility cannot inherit the old edit session.
        studio = getattr(self, "overlay_layout_studio", None)
        try:
            if studio and studio.is_open():
                studio.close()
        except Exception:
            try:
                win = getattr(studio, "win", None)
                if win and win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
        self.overlay_layout_studio = None
        try:
            self._capture_overlay_positions()
        except Exception:
            pass
        self._overlay_position_authority.clear()

        close_methods = {
            "carrier_window": "_on_close",
            "colonization_window": "_on_close",
            "engineer_window": "_on_close",
            "bgs_window": "_on_close",
            "commander_profile_window": "_on_close",
            "value_ledger_window": "_on_close",
            "colonisation_planner_window": "_on_close",
            "exploration_window": "_on_close",
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
        transition_job = getattr(self, "_navigation_transition_job", None)
        if transition_job is not None:
            try:
                self.root.after_cancel(transition_job)
            except Exception:
                pass
        self._navigation_transition_job = None
        self._hud_refresh_job = None
        self._hud_refresh_requested = False
        self._last_hud_refresh_ts = 0.0
        # No commander may read a fact packet built for the previous one.
        self._latest_exploration_intelligence = None
        self._invalidate_exploration_intelligence()
        self.current_sys = "---"
        self._navigation_system_arrival_epoch = None
        self.previous_sys = None
        self.previous_coords = None
        self.current_system_address = None
        self.current_coords = [0, 0, 0]
        self.star_class = ""
        self.scanned = 0
        self.total = 0
        self.scan_total_confirmed = False
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
        self.belt_clusters = []
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
        self._survey_body_focus_suppressed = False
        self._startup_bio_sampling_replay = None
        self._startup_bio_sampling_replay_seen = False
        self._sample_clear_announced = False
        self._stale_bio_warned = set()

        self.cmdr_name = commander_name or "CMDR"
        self.cmdr_fid = fid or ""
        self.cmdr_balance = None
        self.session_start_balance = None
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
        self.current_station_state = None
        self.current_station_economy = None
        self.current_station_economies = []
        self.current_station_government = None
        self.current_station_faction = None
        self.current_station_allegiance = None
        self.current_station_services = []
        self.current_station_dist_ls = None
        self.current_station_landing_pads = None
        self.current_colonisation_market = None
        self.current_docked = False

        self.hud_flight_state = "FLIGHT"
        self.current_landed = False
        self.current_in_fighter = False
        self.current_in_srv = False
        self.current_on_foot = False
        self.current_in_taxi = False
        self.current_in_multicrew = False
        self.current_vehicle_id = None
        self.current_vehicle_name = ""
        self._vehicle_name_by_id = {}
        self._last_surface_vehicle_name = ""
        self.current_music_track = ""
        self.current_music_mode = ""
        self.current_music_label = ""
        self.current_gui_focus = -1
        self._last_music_event_ts = 0.0
        self.current_fuel_main = None
        self.current_fuel_reservoir = None
        self.fuel_capacity_main = None
        self.current_hull_percent = None
        self._fuel_used_samples = deque(maxlen=8)
        self._fuel_advisory_signature = None
        self._low_fuel_warned = False
        self._toast_hull_thresholds_seen = set()
        self._toast_status_alerts = set()
        self._toast_status_last_emitted = {}
        self._toast_legal_state = None
        self._toast_shields_up = None
        self.current_legal_state = None
        self.current_destination = None
        self.current_destination_details = {}
        self.current_local_space_body_type = ""
        self.current_local_space_name = ""
        self.current_asteroid_field_kind = ""
        self.current_status_flags = 0
        self.current_status_flags2 = 0
        self.current_altitude_m = None
        self.current_landing_gear_down = False
        self.current_cargo_scoop_deployed = False
        self.current_analysis_mode = False
        self.current_scooping_fuel = False
        self.current_supercruise_overcharge = False
        self.current_glide_mode = False
        self.current_interdicted = False
        self._surface_departure_active = False
        self._surface_glide_guard_until = 0.0
        self._surface_climb_samples = 0
        self._surface_descent_samples = 0
        self._status_altitude_observed_monotonic = None
        self._surface_descent_mps = 0.0
        self._surface_hold_active = False
        self._surface_last_position = None
        self._surface_last_motion_monotonic = None
        self._surface_hold_job = None
        self.current_fsd_mass_locked = False
        self.current_fsd_charging = False
        self.current_fsd_hyperdrive_charging = False
        self.current_fsd_cooldown = False
        self.current_fsd_jumping = False
        self._navigation_jump_phase = ""
        self._navigation_jump_target = ""
        self._navigation_jump_charge_seen = False
        self._navigation_charge_resolution_pending = False
        self._navigation_jump_phase_started = 0.0
        self._navigation_selected_star = None
        self.neutron_boost_armed = False
        self.neutron_boost_value = None

        self.cargo_capacity = 0
        self.current_cargo_tons = 0
        self.current_cargo_inventory = []
        self.trade_session = self._new_trade_session()
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
        self.surface_trail = []
        self.surface_trail_body = ""
        self.surface_ship_position = None
        self._pending_status_data = None
        self._status_dispatch_scheduled = False

        self._rebuy_warning_level = 0
        self._data_risk_level = 0
        self._compass_advisor_last = {}
        self._compass_advisor_last_any = 0.0
        self._cockpit_docking_quiet_until = 0.0
        self._hud_balance_cache = {"ts": 0.0, "balance": None}
        self._hud_event_pulse = None
        self._hud_event_batch_priority = None
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
        if threading.current_thread() is not threading.main_thread():
            self._ui_post(
                self._refresh_tool_window, attr, method,
                key=f"tool-window:{attr}:{method}",
            )
            return
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        win = getattr(self, attr, None)
        try:
            if win and win.is_open():
                getattr(win, method)()
        except Exception:
            pass

    def _refresh_commander_profile_window(self):
        if threading.current_thread() is not threading.main_thread():
            self._ui_post(
                self._refresh_commander_profile_window,
                key="commander-profile-refresh",
            )
            return
        if getattr(self, "_startup_restore_active", False):
            self._startup_restore_ui_pending = True
            return
        window = getattr(self, "commander_profile_window", None)
        try:
            if not window or not window.is_open():
                return
            if getattr(self, "_active_page", None) == "PROFILE":
                window.refresh()
            else:
                window._refresh_pending = True
        except Exception:
            pass

    def _refresh_value_ledger_window(self):
        self._refresh_tool_window("value_ledger_window")

    def _refresh_colonisation_planner_window(self):
        self._refresh_tool_window("colonisation_planner_window")

    def _refresh_exploration_window(self):
        if threading.current_thread() is not threading.main_thread():
            self._ui_post(
                self._refresh_exploration_window,
                key="exploration-window-refresh",
            )
            return
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

    def _import_exploration_history(self, journal_path, logbook, tracker, commander=None, fid=None,
                                    scan_db_path=None, profile_key=None):
        """Read history sequentially so indexers never contend for the journal folder."""
        self._import_captains_log_history(journal_path, logbook, commander, fid)
        self._import_deep_survey_history(journal_path, tracker, commander, fid)
        try:
            repaired = self.import_scan_journal_history(
                journal_path, commander, fid, db_path=scan_db_path,
            )
            if repaired.get("files"):
                self.log(
                    f"Survey cache checked {repaired['files']:,} changed journal files; "
                    f"repaired {len(repaired['systems']):,} system records"
                )
            if repaired.get("systems"):
                self._ui_post(
                    self._apply_scan_history_repair, repaired, profile_key,
                    key=f"scan-history-repair:{profile_key or 'active'}",
                )
        except Exception as exc:
            logging.warning("Survey cache journal repair skipped: %s", exc)

    def _apply_scan_history_repair(self, repaired, profile_key=None):
        """Refresh every scan UI when a background journal repair affects this system."""
        if profile_key and profile_key != get_active_profile(self.config):
            return
        systems = set((repaired or {}).get("systems") or ())
        if self.current_sys not in systems:
            return
        self.load_system_from_db(self.current_sys)
        self._seed_navigation_scan_progress()
        self.update_dashboard_ui()
        self.update_hud()
        self._refresh_system_info_progress()
        self._refresh_exploration_window()

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
        generation = getattr(self, "_system_info_refresh_generation", 0)
        self._ui_post(
            self._schedule_system_info_refresh_ui,
            generation,
            key="system-info-progress-schedule",
        )

    def _schedule_system_info_refresh_ui(self, generation):
        """Debounce scan overlays on Tk's thread after journal state settles."""
        if generation != getattr(self, "_system_info_refresh_generation", 0):
            return
        if getattr(self, "_system_info_refresh_job", None) is not None:
            return

        def _run():
            self._system_info_refresh_job = None
            if generation != getattr(self, "_system_info_refresh_generation", 0):
                return
            if self.system_info_hud:
                self.system_info_hud.update_scan_progress(
                    self.scan_items, self.body_signals, self.total,
                    star_class=self.star_class, scanned_bodies=self.scanned,
                    total_known=self.scan_total_confirmed,
                )
            if self.survey_status_hud:
                if self.current_docked:
                    self.survey_status_hud.suppress()
                else:
                    self.survey_status_hud.update(
                        self.current_sys, self.scanned, self.total, self.scan_items,
                        self.body_signals, sampling=self._sampling_snapshot(),
                        focused_body_id=(None if self._survey_body_focus_suppressed
                                         and not self.bio_sampling else self.current_body_id),
                        focused_body_name=(None if self._survey_body_focus_suppressed
                                           and not self.bio_sampling else self.current_body_name),
                        total_known=self.scan_total_confirmed,
                        belt_clusters=list(self.belt_clusters),
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
            survey.suppress()
        self._system_info_refresh_generation = (
            getattr(self, "_system_info_refresh_generation", 0) + 1
        )

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
        taxi_value = data.get("in_taxi")
        if taxi_value is None:
            taxi_value = location.get("Taxi")
        multicrew_value = data.get("in_multicrew")
        if multicrew_value is None:
            multicrew_value = location.get("Multicrew")
        in_srv_value = data.get("in_srv")
        if in_srv_value is None:
            in_srv_value = location.get("InSRV")
        self.current_in_taxi = bool(taxi_value)
        self.current_in_multicrew = bool(multicrew_value)
        self.current_in_srv = bool(in_srv_value)
        if self.current_in_taxi or self.current_in_multicrew or self.current_in_srv:
            self.current_on_foot = False
        self.current_in_fighter = False
        self.current_vehicle_id = None
        if self.current_in_srv:
            remembered = str(getattr(self, "_last_surface_vehicle_name", "") or "").upper()
            self.current_vehicle_name = remembered if remembered in {"NOMAD", "SRV"} else "SRV"
        else:
            self.current_vehicle_name = ""
        if docked_value is not None or (self.current_on_foot and station_name):
            self.current_docked = bool(docked_value or (self.current_on_foot and station_name))
        if station_name:
            self.current_station_name = station_name
            self.current_station_type = data.get("station_type") or location.get("StationType") or None
            self.current_station_market_id = data.get("market_id") or location.get("MarketID")
            self.current_station_state = location.get("StationState")
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
            self.current_station_state = None
            self.current_station_economy = None
            self.current_station_economies = []
            self.current_station_government = None
            self.current_station_faction = None
            self.current_station_allegiance = None
            self.current_station_services = []
            self.current_station_dist_ls = None
            self.current_station_landing_pads = None
        self._sync_navigation_hud_flight_state(supercruise=False)

    def _start_eddn_market_upload(self):
        """Apply the independent visited-market EDDN integration setting."""
        eddn_market_uploader.set_enabled(
            bool(self.config.get("eddn_market_upload_enabled", True))
        )

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
        path = self.config.get("engineer_materials_file") or os.path.join(
            os.getcwd(), "engineer_materials.json",
        )
        payload = {
            key: value for key, value in (materials or {}).items()
            if not str(key).startswith("_")
        }
        try:
            persistence_queue().submit_json(path, payload, indent=2, delay_s=0.35)
            if isinstance(materials, dict):
                materials.pop("_save_error", None)
            return True
        except Exception as exc:
            if isinstance(materials, dict):
                materials["_save_error"] = str(exc)
            logging.warning("Could not queue engineering state: %s", exc)
            return False

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
        self._capture_dashboard_window_geometry()
        outgoing_engineer_path = self.config.get("engineer_materials_file")
        self._close_profile_surfaces()
        if outgoing_engineer_path:
            # A profile boundary is rare and worth a short durability wait;
            # it also ensures the unknown-profile migration below sees the
            # most recent Engineering Workshop state.
            if not persistence_queue().flush(outgoing_engineer_path, timeout=0.75):
                logging.warning(
                    "Engineering state was still pending during profile switch: %s",
                    outgoing_engineer_path,
                )
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
        self._apply_dashboard_window_geometry()
        self._sync_flight_log_shell_visibility()
        # These long-lived workers retain the same config object today, but
        # rebinding them makes the profile boundary explicit and future-proof.
        self.screenshots.config = self.config
        self.watcher.config = self.config
        self.voice_callouts = None
        self.cockpit_memory = None
        self.cockpit_brain = None
        self.compass_cognition = None
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
            self._adaptive_startup_synced = False
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
        carrier_window = getattr(self, "carrier_window", None)
        if carrier_window and carrier_window.is_open():
            carrier_window.on_profile_switched()
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
            args=(
                journal_path, self.captains_log, self.deep_survey,
                self.cmdr_name, self.cmdr_fid, self.db_path,
                get_active_profile(self.config),
            ),
            name="exploration-history", daemon=True,
        ).start()
        self._persist_config()
        self._apply_runtime_feature_toggles()
        self._start_eddn_market_upload()
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
        apply_ui_scale(self.root, self.config.get("ui_scale_percent", 100))
        self._prepare_commander_profile_from_journal()
        self._apply_active_profile_theme()
        first_run = should_show_onboarding(self.config)
        if first_run:
            self._show_bootstrap_onboarding()
            # The selected journal folder may identify a different commander
            # than the pre-wizard defaults. Establish that profile before any
            # profile-local state, overlay or journal watcher.
            self._prepare_commander_profile_from_journal()
            self._apply_active_profile_theme()
            save_config(self.config)
        previous_version = str(self.config.get("last_app_version") or "")
        if not first_run and previous_version != APP_VERSION:
            try:
                automatic_backup(
                    get_active_profile(self.config),
                    get_profile_dir(get_active_profile(self.config)),
                    reason=f"before_{APP_VERSION}", keep=5,
                )
            except Exception as exc:
                logging.warning("Automatic pre-upgrade profile backup skipped: %s", exc)
        if previous_version != APP_VERSION:
            self.config["last_app_version"] = APP_VERSION
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
        self.voice_callouts = None
        self.cockpit_memory = None
        self.cockpit_brain = None
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
        self._adaptive_startup_synced = False
        self.session_guard = ProfileSessionGuard(
            self._profile_path("session.active"), APP_VERSION,
        )
        self._startup_recovery_mode = bool(
            self.session_guard.unclean
            and self.config.get("recovery_safe_mode_enabled", True)
        )
        self.compass_cognition = None
        self.root.title(f"VOID COMPASS // v{APP_VERSION}")
        self._apply_dashboard_window_geometry()
        self.root.configure(bg=COLOR_BG)
        
        self.is_running = True
        self.is_first_load = True
        self._startup_history_pending = set()
        self._startup_live_tail_ready = False
        self._startup_presentation_ready = False
        self._startup_journal_events_loaded = 0
        self._startup_overlay_restore = set()
        self._startup_presentation_held = bool(
            getattr(self.root, "_voidcompass_startup_presentation_held", False)
        )
        self._startup_boot_handoff_job = None
        self._startup_boot_journal_timeout_job = None
        
        self.current_sys = "---"
        self._navigation_system_arrival_epoch = None
        self.previous_sys = None
        self.previous_coords = None
        self.current_system_address = None
        self.star_class = ""
        self.scanned = 0
        self.total = 0
        self.scan_total_confirmed = False
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
        self.belt_clusters = []
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
        self._survey_body_focus_suppressed = False
        self._startup_bio_sampling_replay = None
        self._startup_bio_sampling_replay_seen = False
        self._sample_clear_announced = False
        self._rebuy_warning_level = 0
        self._data_risk_level = 0
        self._compass_advisor_last = {}
        self._compass_advisor_last_any = 0.0
        self._cockpit_docking_quiet_until = 0.0
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
        self.current_station_state = None
        self.current_station_economy = None
        self.current_station_economies = []
        self.current_station_government = None
        self.current_station_faction = None
        self.current_station_allegiance = None
        self.current_station_services = []
        self.current_station_dist_ls = None
        self.current_station_landing_pads = None
        self.current_docked = False
        self.hud_flight_state = "FLIGHT"
        self.current_landed = False
        self.current_in_fighter = False
        self.current_in_srv = False
        self.current_on_foot = False
        self.current_in_taxi = False
        self.current_in_multicrew = False
        self.current_vehicle_id = None
        self.current_vehicle_name = ""
        self._vehicle_name_by_id = {}
        self._last_surface_vehicle_name = ""
        self.current_music_track = ""
        self.current_music_mode = ""
        self.current_music_label = ""
        self.current_gui_focus = -1
        self._last_music_event_ts = 0.0
        self.current_fuel_main = None
        self.current_fuel_reservoir = None
        self.fuel_capacity_main = None
        self._fuel_used_samples = deque(maxlen=8)
        self._fuel_advisory_signature = None
        self._low_fuel_warned = False
        self._toast_hull_thresholds_seen = set()
        self._toast_status_alerts = set()
        self._toast_status_last_emitted = {}
        self._toast_legal_state = None
        self._toast_shields_up = None
        self.current_legal_state = None
        self.current_destination = None
        self.current_destination_details = {}
        self.current_local_space_body_type = ""
        self.current_local_space_name = ""
        self.current_asteroid_field_kind = ""
        self.current_status_flags = 0
        self.current_status_flags2 = 0
        self.current_altitude_m = None
        self.current_landing_gear_down = False
        self.current_cargo_scoop_deployed = False
        self.current_analysis_mode = False
        self.current_scooping_fuel = False
        self.current_supercruise_overcharge = False
        self.current_glide_mode = False
        self.current_interdicted = False
        self._surface_departure_active = False
        self._surface_glide_guard_until = 0.0
        self._surface_climb_samples = 0
        self._surface_descent_samples = 0
        self._status_altitude_observed_monotonic = None
        self._surface_descent_mps = 0.0
        self._cancel_surface_hold_inference()
        self._surface_hold_active = False
        self._surface_last_position = None
        self._surface_last_motion_monotonic = None
        self.current_fsd_mass_locked = False
        self.current_fsd_charging = False
        self.current_fsd_hyperdrive_charging = False
        self.current_fsd_cooldown = False
        self.current_fsd_jumping = False
        self._navigation_jump_phase = ""
        self._navigation_jump_target = ""
        self._navigation_jump_charge_seen = False
        self._navigation_charge_resolution_pending = False
        self._navigation_jump_phase_started = 0.0
        self._navigation_selected_star = None
        self._navigation_transition_job = None
        self.neutron_boost_armed = False
        self.neutron_boost_value = None
        self.cargo_capacity = 0
        self.current_cargo_tons = 0
        self.current_cargo_inventory = []
        self.trade_session = self._new_trade_session()
        self.mining_ai_session = self._new_mining_ai_session()
        self.ai_operational_state = compass_operations.fresh_runtime_state()
        self.combat_awareness = CombatAwareness()
        self._hud_balance_cache = {"ts": 0.0, "balance": None}
        self.last_journal_event_ts = 0.0
        self._hud_event_sequence = 0
        self._hud_event_pulse = None
        self._hud_event_batch_priority = None
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
        self.current_hull_percent = None
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
        self.surface_trail = []
        self.surface_trail_body = ""
        self.surface_ship_position = None
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
        self._latest_exploration_intelligence = None
        self._exploration_intelligence_ts = 0.0
        self._overlay_pos_last_saved = {
            attr: None for attr, _x_key, _y_key in self._OVERLAY_POSITION_SPECS
        }
        # Short-lived Studio targets protect asynchronous Tk geometry changes
        # from the normal live-position capture loop. Without this guard a
        # stale winfo_x()/winfo_y() can overwrite the position just dragged.
        self._overlay_position_authority = {}
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
        self.session_start_balance = self.cmdr_balance
        
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
        eddn_market_uploader.set_log_callback(
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
        self.analytics_window = None
        self.achievement_window = None
        self.specialists_window = None
        self.overlay_layout_studio = None
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
                self.hud.win.geometry(overlay_chrome.position_geometry(hx, hy))
            except Exception:
                pass
        else:
            self.hud = None
            
        if self.config.get("cargo_overlay_enabled", False):
            self.cargo_hud = CargoHUD(self.root, self.config)
            try:
                cx = int(float(self.config.get("cargo_hud_x", self.cargo_hud.win.winfo_x())))
                cy = int(float(self.config.get("cargo_hud_y", self.cargo_hud.win.winfo_y())))
                self.cargo_hud.win.geometry(overlay_chrome.position_geometry(cx, cy))
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

        self._attach_html_overlay_renderers()

        # Capture each overlay's intended initial visibility and withdraw it
        # before database construction or any Tk idle processing can map a
        # transparent startup Toplevel. Journal catch-up may update these
        # hidden windows, but cannot expose them ahead of the final handoff.
        if self._startup_presentation_held:
            self._hold_startup_presentation()

        self._apply_overlay_mouse_passthrough()
        if not self._startup_recovery_mode:
            self._apply_adaptive_overlay_scene()

        self.db_lock = threading.RLock()
        self.batch_mode = False
        self._startup_restore_active = False
        self._startup_restore_ui_pending = False
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
        # Let Tk paint the cached cockpit and overlay windows before the
        # journal worker begins its potentially large startup replay.
        self.root.after(75, self.watcher.start)
        self._start_eddn_market_upload()
        self.cargo_capacity = self.watcher.get_latest_cargo_capacity()
        latest_fuel_capacity = self.watcher.get_latest_fuel_capacity()
        if latest_fuel_capacity > 0:
            self.fuel_capacity_main = latest_fuel_capacity
        self._refresh_cargo_consumers()

        self.watcher.force_check_nav()
        self.watcher.force_check_status()

        journal_path = self.config.get("journal_path") or getattr(self.watcher, "journal_path", None)
        self._startup_history_pending = {"carrier", "exploration"}
        threading.Thread(
            target=self._run_startup_history_phase,
            args=(
                "carrier", self.carrier_tracker.scan_journal_history,
                (journal_path, 10, self.cmdr_name, self.cmdr_fid),
            ),
            name="carrier-history",
            daemon=True,
        ).start()
        threading.Thread(
            target=self._run_startup_history_phase,
            args=(
                "exploration", self._import_exploration_history,
                (
                    journal_path, self.captains_log, self.deep_survey,
                    self.cmdr_name, self.cmdr_fid, self.db_path,
                    get_active_profile(self.config),
                ),
            ),
            name="exploration-history", daemon=True,
        ).start()

        if getattr(self.root, "_voidcompass_startup_splash", None) is not None:
            has_journal_path = bool(journal_path and os.path.isdir(journal_path))
            timeout_ms = 90_000 if has_journal_path else 3_000
            self._startup_boot_journal_timeout_job = self.root.after(
                timeout_ms, self._startup_journal_timeout,
            )

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
        self._start_ui_stall_sampler()
        self._tick_runtime_trace()
        self._tick_overlay_position_sync()
        self._tick_overlay_hotkey_guard()

    def _show_bootstrap_onboarding(self):
        """Block construction so first-run setup is the only visible window."""
        completed = {"value": False}

        def complete():
            completed["value"] = True
            save_config(self.config)

        window = show_first_run(
            self.root, self.config, complete, standalone=True,
        )
        self.root.wait_window(window)
        if not completed["value"]:
            # Closing the mandatory commissioning window means Exit, not
            # implicit acceptance of its defaults. Stop construction before
            # any second Toplevel or partially initialized Dashboard exists.
            raise StartupCancelled()
        # Continue to cover real cache/index restoration after commander setup;
        # the outer launcher will keep the Dashboard withdrawn until live.
        splash = show_startup_boot(
            self.root, self.config,
            lambda _window: self._maybe_complete_startup_presentation(),
        )
        self.root._voidcompass_startup_splash = splash
        splash.update_idletasks()

    def _startup_boot(self):
        splash = getattr(self.root, "_voidcompass_startup_splash", None)
        return getattr(splash, "_voidcompass_boot", None) if splash is not None else None

    def _startup_boot_update(self, status, detail="", progress=None):
        boot = self._startup_boot()
        if boot is not None:
            boot.set_runtime_status(status, detail, progress)

    def _hold_startup_presentation(self):
        """Keep Dashboard and enabled overlays behind the boot handoff."""
        splash = getattr(self.root, "_voidcompass_startup_splash", None)
        if splash is None:
            return
        self._startup_presentation_held = True
        self.root._voidcompass_startup_presentation_held = True
        for name, window in self._overlay_hotkey_window_items():
            try:
                if self._overlay_window_is_shown(window):
                    self._startup_overlay_restore.add(name)
                window.withdraw()
            except (AttributeError, tk.TclError):
                continue
        try:
            splash.deiconify()
            splash.attributes("-topmost", True)
            splash.lift()
        except tk.TclError:
            pass

    def _release_startup_overlay_curtain(self):
        """Make fully prepared overlays drawable without mapping them yet."""
        self._reapply_overlay_positions()
        for name, window in self._overlay_hotkey_window_items():
            try:
                if not window.winfo_exists():
                    continue
                attr = "hud" if name == "navigation" else name
                overlay = getattr(self, attr, None)
                html_ready = bool(getattr(overlay, "_html_ready", False))
                # With the WebView host deferred until handoff, readiness is
                # intentionally false here. Keep an active HTML proxy clear
                # while its browser surface starts; its bridge restores the
                # native renderer automatically if startup genuinely fails.
                html_pending = bool(getattr(overlay, "_html_bridge", None))
                canvas_bridge = getattr(overlay, "_html_canvas_bridge", None)
                survey_bridge = getattr(overlay, "_html_survey_bridge", None)
                html_pending = bool(
                    html_pending
                    or getattr(canvas_bridge, "surface", None) is not None
                    or getattr(survey_bridge, "surface", None) is not None
                )
                window.attributes(
                    "-alpha", 0.0 if html_ready or html_pending else 1.0,
                )
                window._voidcompass_startup_held = False
            except (AttributeError, tk.TclError):
                continue
        self._startup_presentation_held = False
        self.root._voidcompass_startup_presentation_held = False

    def _run_startup_history_phase(self, phase, target, args):
        try:
            target(*args)
        except Exception as exc:
            logging.warning("Startup %s history phase failed: %s", phase, exc)
        finally:
            self._ui_post(
                self._startup_history_phase_complete, phase,
                key=f"startup-history:{phase}",
            )

    def _startup_history_phase_complete(self, phase):
        self._startup_history_pending.discard(str(phase))
        if self._startup_history_pending:
            remaining = " and ".join(sorted(self._startup_history_pending))
            self._startup_boot_update(
                "INDEXING PAST JOURNALS",
                f"Waiting for {remaining} history",
                0.64,
            )
        else:
            self._startup_boot_update(
                "HISTORICAL INDEX READY",
                "Waiting for the active journal to reach its live tail",
                0.76,
            )
        self._maybe_complete_startup_presentation()

    def _startup_journal_timeout(self):
        self._startup_boot_journal_timeout_job = None
        if self._startup_live_tail_ready:
            return
        self._startup_live_tail_ready = True
        self._startup_presentation_ready = True
        self._startup_boot_update(
            "JOURNAL LINK OFFLINE",
            "No live tail was available; cached flight state is ready",
            0.90,
        )
        self._maybe_complete_startup_presentation()

    def _mark_startup_journal_live(self):
        self._startup_live_tail_ready = True
        timeout_job = getattr(self, "_startup_boot_journal_timeout_job", None)
        self._startup_boot_journal_timeout_job = None
        if timeout_job is not None:
            try:
                self.root.after_cancel(timeout_job)
            except tk.TclError:
                pass
        self._startup_boot_update(
            "LIVE JOURNAL TAIL REACHED",
            f"{self._startup_journal_events_loaded:,} recent events restored",
            0.88,
        )

    def _maybe_complete_startup_presentation(self):
        splash = getattr(self.root, "_voidcompass_startup_splash", None)
        if splash is None or getattr(self, "_startup_boot_handoff_job", None) is not None:
            return
        boot = self._startup_boot()
        if boot is not None and not getattr(boot, "_ready_emitted", False):
            return
        if not getattr(self, "_startup_live_tail_ready", False) or not getattr(
            self, "_startup_presentation_ready", False,
        ):
            return
        if getattr(self, "_startup_history_pending", set()):
            return
        self._startup_boot_update(
            "VOID COMPASS LIVE",
            "Journal, survey history and overlays are synchronized",
            1.0,
        )
        self._startup_boot_handoff_job = self.root.after(
            240, self._finish_startup_presentation,
        )

    def _finish_startup_presentation(self):
        self._startup_boot_handoff_job = None
        # One last curtain pass catches overlays whose final journal
        # reconciliation deliberately called show(). Restore their saved
        # coordinates while invisible, then permit mapping exactly once.
        self._hold_startup_presentation()
        restore = set(self._startup_overlay_restore)
        self._startup_overlay_restore.clear()
        self._release_startup_overlay_curtain()
        splash = getattr(self.root, "_voidcompass_startup_splash", None)
        boot = self._startup_boot()
        if boot is not None:
            boot.stop()
        if splash is not None:
            try:
                splash.destroy()
            except tk.TclError:
                pass
        self.root._voidcompass_startup_splash = None
        try:
            self.root.deiconify()
            self.root.lift()
        except tk.TclError:
            return
        self._restore_overlay_hotkey_windows(restore)
        self._apply_adaptive_overlay_scene()
        # HTML surfaces have collected their final models while the bootloader
        # was visible, but their shared WebView2 process remained dormant so
        # no native browser window could flash over journal recovery.  Launch
        # it only now, after the splash has gone and the live UI owns the
        # presentation.
        html_runtime = getattr(
            self.root, "_voidcompass_html_overlay_runtime", None,
        )
        release_html = getattr(html_runtime, "release_startup_hold", None)
        if callable(release_html):
            try:
                release_html()
            except Exception as exc:
                logging.warning("Deferred HTML overlay launch failed: %s", exc)
        try:
            self.root.after(80, self._reapply_overlay_positions)
        except tk.TclError:
            pass

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

    def _set_overlay_position(self, attr, x, y, authority_s=0.0):
        """Move one overlay and synchronize every source of its position."""
        spec = next(
            (item for item in self._OVERLAY_POSITION_SPECS if item[0] == attr),
            None,
        )
        if spec is None:
            raise KeyError(f"Unknown overlay: {attr}")
        _attr, x_key, y_key = spec
        x, y = int(round(float(x))), int(round(float(y)))
        self.config[x_key], self.config[y_key] = x, y
        overlay = getattr(self, attr, None)
        if overlay is not None and hasattr(overlay, "_desired_pos"):
            overlay._desired_pos = (x, y)
        window = getattr(overlay, "win", overlay)
        if window is not None:
            try:
                if window.winfo_exists():
                    window.geometry(overlay_chrome.position_geometry(x, y))
            except (AttributeError, tk.TclError):
                pass
        sync_html_window = getattr(overlay, "sync_html_window", None)
        if callable(sync_html_window):
            try:
                sync_html_window(x, y)
            except Exception:
                pass
        self._overlay_pos_last_saved[attr] = (x, y)
        if authority_s and authority_s > 0:
            authority = getattr(self, "_overlay_position_authority", None)
            if not isinstance(authority, dict):
                authority = self._overlay_position_authority = {}
            authority[attr] = {
                "position": (x, y),
                "until": time.time() + float(authority_s),
            }
        return x, y

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
                if hasattr(overlay, "_desired_pos"):
                    overlay._desired_pos = (x, y)
                # Position-only geometry preserves each HUD's current/dynamic size.
                win.geometry(overlay_chrome.position_geometry(x, y))
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
                    if attr == "ground_popup":
                        self._ground_popup_visible = True
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
            if not report.get("supported", True):
                self.add_event_feed_entry(
                    "SYSTEM",
                    "System-wide overlay hotkeys are available on Windows only",
                    severity="INFO",
                )
            elif registered:
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

    def _suspend_overlay_hotkeys_for_capture(self):
        """Prevent an existing app shortcut from firing inside its recorder."""
        manager = getattr(self, "overlay_hotkeys", None)
        self._overlay_hotkeys_capture_suspended = bool(manager is not None)
        if manager is not None:
            manager.stop()

    def _resume_overlay_hotkeys_after_capture(self):
        """Restore saved bindings; recorder edits remain pending until Save."""
        if not getattr(self, "_overlay_hotkeys_capture_suspended", False):
            return
        self._overlay_hotkeys_capture_suspended = False
        if getattr(self, "is_running", True):
            self._configure_overlay_hotkeys(announce=False)

    def _toggle_navigation_hud_layout(self, *, announce=True):
        """Switch the active commander's HUD between Standard and Expanded."""
        standard = not bool(self.config.get("hud_compact_mode", True))
        self.config["hud_compact_mode"] = standard
        save_config(self.config)
        self.update_hud()
        studio = getattr(self, "overlay_layout_studio", None)
        if studio and studio.is_open():
            studio.refresh()
        mode = "Standard" if standard else "Expanded"
        if announce:
            self.add_event_feed_entry(
                "SYSTEM", f"Navigation HUD layout: {mode}", severity="INFO",
            )
        return mode

    def _handle_overlay_hotkey(self, action):
        if not self.is_running:
            return
        spec = next((item for item in OVERLAY_HOTKEY_SPECS if item[0] == action), None)
        if spec is None:
            return
        _action, _key, label, attr = spec
        if action == "layout_studio":
            studio = getattr(self, "overlay_layout_studio", None)
            if studio and studio.is_open():
                studio.close()
                self.overlay_layout_studio = None
                message = "Overlay Layout Studio closed"
            else:
                self.open_overlay_layout_studio()
                message = "Overlay Layout Studio opened"
            self.add_event_feed_entry("SYSTEM", message, severity="INFO")
            return
        if action == "navigation_layout":
            self._toggle_navigation_hud_layout()
            return
        if action == "field_bookmark":
            self._field_bookmark()
            return
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
        now = time.time()
        authorities = getattr(self, "_overlay_position_authority", {})
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
                try:
                    window_is_shown = (
                        bool(win.winfo_viewable())
                        and str(win.state()) not in ("withdrawn", "iconic")
                    )
                except AttributeError:
                    # Lightweight diagnostic/test windows without Tk mapping
                    # APIs represent ordinary visible windows.
                    window_is_shown = True
                except tk.TclError:
                    window_is_shown = False
                authority = authorities.get(attr)
                if authority and now >= float(authority.get("until") or 0):
                    authorities.pop(attr, None)
                    authority = None
                if authority:
                    target = tuple(authority.get("position") or configured or pos)
                    target = (int(target[0]), int(target[1]))
                    if pos != target:
                        if hasattr(overlay, "_desired_pos"):
                            overlay._desired_pos = target
                        win.geometry(overlay_chrome.position_geometry(*target))
                    # A Studio move wins until Tk has delivered its Configure
                    # event; never copy the stale live coordinate back into the
                    # active commander's saved layout.
                    pos = configured = target
                elif not window_is_shown:
                    # A withdrawn Tk window can keep reporting the position at
                    # which it was last mapped even after Layout Studio moved
                    # it. Hidden overlays therefore have no trustworthy live
                    # geometry: the commander-profile coordinate is the source
                    # of truth until the window is shown again.
                    desired = getattr(overlay, "_desired_pos", None)
                    target = configured if configured is not None else desired
                    if target is not None:
                        pos = (int(target[0]), int(target[1]))
                        if hasattr(overlay, "_desired_pos"):
                            overlay._desired_pos = pos
                # Withdrawn or not-yet-mapped windows commonly report (0, 0).
                # Preserve a real configured position, and do not manufacture a
                # new (0, 0) value when an optional position has never been set.
                if pos == (0, 0):
                    if configured is None:
                        continue
                    if configured != (0, 0):
                        pos = configured
                # Keep timer-driven overlays aligned with the live window.
                # CarrierHUD and a few startup-safe HUDs retain a desired
                # position so redraws never need to trust withdrawn (0, 0)
                # coordinates.
                if hasattr(overlay, "_desired_pos"):
                    overlay._desired_pos = pos
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
        try:
            self.root.after(0, lambda: callback(*args, **kwargs))
            return True
        except Exception:
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

    def _freeze_startup_heap(self):
        """Exclude the loaded reference data from every later GC pass.

        Codex, engineering, region and bio tables are large, permanent and
        never become garbage, yet a full collection still had to walk them.
        Freezing them once catch-up finishes measured a full collection down
        from about 11 ms to nothing.
        """
        if getattr(self, "_startup_heap_frozen", False):
            return
        self._startup_heap_frozen = True
        try:
            gc.collect()
            gc.freeze()
            self._trace_bump("gc_frozen_objects", gc.get_freeze_count())
        except Exception as exc:
            logging.warning("Could not freeze the startup heap: %s", exc)

    def _start_ui_stall_sampler(self):
        """Capture what the main thread is doing while it is stalled.

        The existing watchdog measures how late a Tk callback fires, but by the
        time it runs the blocking work has already finished, so the trace only
        ever showed the stall's size and never its cause. This samples the main
        thread's stack from outside the main loop, while it is still stuck.
        """
        if not bool(self.config.get("ui_stall_sampler_enabled", True)):
            return
        main_thread = threading.main_thread().ident
        trigger_ms = max(80.0, float(self.config.get("ui_stall_sample_ms", 200.0)))

        def sample():
            while self.is_running:
                time.sleep(0.05)
                try:
                    blocked_ms = (time.perf_counter() - self._ui_watchdog_last_ts) * 1000.0
                    if blocked_ms < trigger_ms:
                        continue
                    frame = sys._current_frames().get(main_thread)
                    if frame is None:
                        continue
                    # Innermost frames are the useful ones; application code is
                    # kept in preference to the Tk and threading plumbing.
                    stack = traceback.extract_stack(frame)[-14:]
                    where = " < ".join(
                        f"{os.path.basename(entry.filename)}:{entry.lineno}:{entry.name}"
                        for entry in reversed(stack)
                    )
                    self._trace_record_ms("ui_stall_blocked", blocked_ms)
                    trace = getattr(self, "runtime_trace", None)
                    if trace is not None and getattr(trace, "enabled", False):
                        trace.bump(f"ui_stall_at:{where[:400]}")
                    # One sample per stall is enough to name the culprit.
                    while self.is_running and (
                        time.perf_counter() - self._ui_watchdog_last_ts
                    ) * 1000.0 >= trigger_ms:
                        time.sleep(0.05)
                except Exception:
                    continue

        thread = threading.Thread(
            target=sample, name="ui-stall-sampler", daemon=True,
        )
        self._ui_stall_sampler = thread
        thread.start()

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
        for resize_job_attr in (
            "_workspace_scroll_job", "_main_resize_settle_job",
            "_journal_history_resize_job", "_startup_boot_handoff_job",
            "_startup_boot_journal_timeout_job",
        ):
            resize_job = getattr(self, resize_job_attr, None)
            if resize_job is not None:
                try:
                    self.root.after_cancel(resize_job)
                except Exception:
                    pass
                setattr(self, resize_job_attr, None)
        studio = getattr(self, "overlay_layout_studio", None)
        try:
            if studio and studio.is_open():
                studio.close()
        except Exception:
            pass
        self.overlay_layout_studio = None
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
        # The HTML/WebView2 cockpit is a separate process. Begin its graceful
        # teardown now so it closes in parallel with the state durability work
        # below instead of adding a serial wait after Tk is destroyed.
        html_runtime = getattr(self.root, "_voidcompass_html_overlay_runtime", None)
        if html_runtime is not None:
            try:
                html_runtime.dispose()
            except Exception:
                pass
        if getattr(self, "watcher", None):
            self.watcher.stop()
        if getattr(self, "overlay_hotkeys", None):
            self.overlay_hotkeys.stop()
        if getattr(self, "ui_dispatcher", None):
            self.ui_dispatcher.stop()
        # This is intentionally the only write site for the last cockpit
        # snapshot. It provides a fast visual restore after a normal quit
        # without turning live journal traffic into continuous disk writes.
        self._save_profile_cockpit_state()
        self._save_exploration_checkpoint("app-close", immediate=True)

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
        self._capture_dashboard_window_geometry()
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

    def _record_surface_trail_point(self, kind="trail", label="", force=False):
        if (
            self.current_latitude is None or self.current_longitude is None
            or not self.current_planet_radius or self.current_planet_radius <= 0
        ):
            return False
        body = str(getattr(self, "current_body_name", "") or getattr(self, "current_body_id", "") or "")
        if self.surface_trail_body and body and body.casefold() != self.surface_trail_body.casefold():
            self.surface_trail = []
            self.surface_ship_position = None
        if body:
            self.surface_trail_body = body
        point = {
            "lat": float(self.current_latitude), "lon": float(self.current_longitude),
            "heading": self.current_heading, "kind": str(kind or "trail"),
            "label": str(label or ""), "timestamp": time.time(),
        }
        last = self.surface_trail[-1] if self.surface_trail else None
        if last and not force:
            distance = self._surface_distance_m(
                last["lat"], last["lon"], point["lat"], point["lon"],
                self.current_planet_radius,
            )
            if distance is not None and distance < 25.0:
                return False
        self.surface_trail.append(point)
        self.surface_trail = self.surface_trail[-600:]
        self._ground_ui_needs_update = True
        return True

    def _surface_trail_snapshot(self):
        pins = []
        specialist = getattr(self, "specialist_engine", None)
        if specialist:
            try:
                pins = (specialist.exobiology_snapshot().get("current_map") or {}).get("pins") or []
            except Exception:
                pins = []
        current = None
        if self.current_latitude is not None and self.current_longitude is not None:
            current = {"lat": self.current_latitude, "lon": self.current_longitude}
        return surface_trail_snapshot(
            self.surface_trail, current=current, ship=self.surface_ship_position,
            radius_m=self.current_planet_radius, sample_pins=pins,
        )

    def clear_surface_trail(self, quiet=False):
        self.surface_trail = []
        self.surface_trail_body = ""
        self.surface_ship_position = None
        self._ground_ui_needs_update = True
        if not quiet and not self.batch_mode:
            self.add_event_feed_entry("BIO", "Surface survey trail cleared", severity="INFO")
        try:
            self.update_ground_target_ui()
        except Exception:
            pass

    def _observe_surface_trail_event(self, ev, raw, startup_replay=False):
        raw = raw if isinstance(raw, dict) else {}
        if ev == "HullDamage":
            try:
                health = float(raw.get("Health"))
                self.current_hull_percent = max(0.0, min(100.0, health * 100 if health <= 1 else health))
            except (TypeError, ValueError):
                pass
            self._invalidate_exploration_intelligence()
        elif ev == "RepairAll":
            self.current_hull_percent = 100.0
            self._invalidate_exploration_intelligence()
        if startup_replay:
            return
        if ev == "Touchdown":
            self.surface_trail = []
            self.surface_trail_body = str(raw.get("Body") or raw.get("BodyName") or getattr(self, "current_body_name", "") or "")
            lat = raw.get("Latitude", self.current_latitude)
            lon = raw.get("Longitude", self.current_longitude)
            try:
                self.surface_ship_position = {"lat": float(lat), "lon": float(lon), "kind": "ship"}
            except (TypeError, ValueError):
                self.surface_ship_position = None
            if self.surface_ship_position:
                self.surface_trail.append({
                    **self.surface_ship_position, "heading": self.current_heading,
                    "label": "Landing site", "timestamp": time.time(),
                })
                self._ground_ui_needs_update = True
        elif ev == "ScanOrganic":
            label = raw.get("Species_Localised") or raw.get("Genus_Localised") or raw.get("Species") or "Biological sample"
            self._record_surface_trail_point("sample", label, force=True)
        elif ev in {"FSDJump", "CarrierJump", "LeaveBody", "Docked", "Died"} or (
            ev == "StartJump" and str(raw.get("JumpType") or "").casefold() == "hyperspace"
        ):
            self.clear_surface_trail(quiet=True)

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
            path = default_screenshot_path(self.config.get("journal_path"))
            
        if os.path.exists(path):
            if not open_path(path):
                self.log("❌ Could not open the screenshot folder with the desktop handler.")
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
            "safety": self._route_safety_snapshot(),
        }

    def _route_safety_snapshot(self):
        return route_safety_forecast(
            getattr(self, "nav_route_entries", None),
            getattr(self, "current_sys", None),
            getattr(self, "star_class", None),
            getattr(self, "current_fuel_main", None),
            getattr(self, "fuel_capacity_main", None),
            list(getattr(self, "_fuel_used_samples", ()) or ()),
        )

    def _record_departure_revisit(self, timestamp=None):
        tracker = getattr(self, "deep_survey", None)
        if tracker is None:
            return None
        system = getattr(self, "current_sys", "")
        candidate = revisit_candidate(
            system,
            getattr(self, "scan_items", None),
            getattr(self, "scanned", 0),
            getattr(self, "total", 0),
            position=getattr(self, "current_coords", None),
            timestamp=timestamp,
        )
        if candidate:
            tracker.record_revisit(candidate)
            self.add_event_feed_entry(
                "SURVEY", f"Revisit queued: {system} · {candidate['detail']}",
                severity="INFO", copy_text=system,
            )
            return candidate
        # Unknown 0/0 state is not proof that a retained opportunity is done.
        total = int(getattr(self, "total", 0) or 0)
        if total > 0 and int(getattr(self, "scanned", 0) or 0) >= total:
            tracker.dismiss_revisit(system)
        return None

    def _field_bookmark(self):
        system = str(getattr(self, "current_sys", "") or "").strip()
        if not system or system in {"---", "Unknown"}:
            self.add_event_feed_entry(
                "EXPEDITION", "Field bookmark unavailable until the current system is known",
                severity="WARN",
            )
            return None
        body = str(getattr(self, "current_body_name", "") or "").strip()
        title = body or system
        manager = getattr(self, "expedition_manager", None)
        if manager is None:
            return None
        bookmark = manager.add_bookmark(
            "Field Note", system=system, body=body, title=title,
            tags=["field", "quick"], source="field-hotkey",
            position=getattr(self, "current_coords", None),
        )
        self.add_event_feed_entry(
            "EXPEDITION", f"Field bookmark saved: {title}", severity="INFO",
            copy_text=system,
        )
        if getattr(self, "toast_hud", None):
            self.toast_hud.push(
                "FIELD BOOKMARK", title, severity="success", duration_s=8,
            )
        self._refresh_exploration_window()
        return bookmark

    def open_mining_window(self):
        """Open the focused Mining Operations workspace."""
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
        self.carrier_window = CarrierWindow(
            self.dashboard_host, self.config, self.carrier_tracker,
            embedded=True, specialist_engine=self.specialist_engine,
            ui_post=self._ui_post,
        )
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
            ui_post_callback=self._ui_post,
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
            ui_post_callback=self._ui_post,
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

    def open_bgs_window(self, section=None):
        if self.bgs_window and self.bgs_window.is_open():
            self._show_embedded_page("GALAXY", self.bgs_window.win)
            self.bgs_window.select_section(section)
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
        self.bgs_window.select_section(section)

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

    def open_galaxy_map_page(self):
        """Show the galaxy map as its own rail workspace.

        Explore owns the survey, ledger and route intelligence the map draws,
        so it is built first if the commander opens the map before Explore.
        """
        if not (self.exploration_window and self.exploration_window.is_open()):
            self.exploration_window = ExplorationWindow(self.dashboard_host, self, embedded=True)
        workspace = getattr(self.exploration_window, "map_workspace", None)
        if workspace is None:
            self.log("Galaxy map workspace unavailable")
            return
        self._show_embedded_page("MAP", workspace)
        self.exploration_window.on_map_shown()

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
            self._ui_post(self._refresh_command_dashboard, key="carrier-dashboard")
            if self.carrier_hud:
                self._ui_post(lambda d=dict(carrier_data): self.carrier_hud.update(d), key="carrier-hud")
            self._ui_post(
                lambda d=dict(carrier_data): self._sync_navigation_carrier_transit(d),
                key="carrier-navigation-transit",
            )
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
            self._sync_navigation_carrier_transit(self.carrier_tracker.carrier_data)
            self._carrier_panel_tick_job = self.root.after(1000, self._tick_carrier_panel)
        elif str(getattr(self, "_navigation_jump_phase", "") or "") == "carrier_transit":
            self._clear_navigation_jump_phase(refresh=True)
        # Ticker stops naturally when status is no longer jumping;
        # _on_carrier_panel_updated will have already refreshed the panel.

    def _commander_aboard_carrier(self, carrier_data):
        """Return True only when the active commander is aboard this carrier."""
        if not (
            getattr(self, "current_docked", False)
            or getattr(self, "current_on_foot", False)
        ):
            return False
        carrier_data = carrier_data if isinstance(carrier_data, dict) else {}
        carrier_id = carrier_data.get("carrier_id")
        station_id = getattr(self, "current_station_market_id", None)
        if carrier_id is not None and station_id is not None:
            return str(carrier_id) == str(station_id)
        station_type = (
            str(getattr(self, "current_station_type", "") or "")
            .replace(" ", "").replace("_", "").casefold()
        )
        if station_type != "fleetcarrier":
            return False
        station_name = str(getattr(self, "current_station_name", "") or "").strip().casefold()
        carrier_names = {
            str(carrier_data.get(key) or "").strip().casefold()
            for key in ("callsign", "name")
            if str(carrier_data.get(key) or "").strip()
        }
        return bool(station_name and station_name in carrier_names)

    def _sync_navigation_carrier_transit(self, carrier_data):
        """Start carrier transit at its scheduled departure while aboard.

        Frontier emits CarrierJump at arrival, but an owned/squadron carrier's
        CarrierJumpRequest supplies the departure time. The existing one-second
        carrier ticker bridges that gap without polling or guessing movement.
        """
        carrier_data = carrier_data if isinstance(carrier_data, dict) else {}
        current_phase = str(getattr(self, "_navigation_jump_phase", "") or "")
        active = (
            carrier_data.get("status") == "jumping"
            and self._commander_aboard_carrier(carrier_data)
        )
        departure_text = str(carrier_data.get("jump_departure_time") or "").strip()
        departed = False
        if active and departure_text:
            try:
                departure = datetime.fromisoformat(departure_text.replace("Z", "+00:00"))
                if departure.tzinfo is None:
                    departure = departure.replace(tzinfo=timezone.utc)
                departed = datetime.now(timezone.utc) >= departure.astimezone(timezone.utc)
            except (TypeError, ValueError):
                departed = False
        if active and departed:
            if current_phase != "carrier_transit":
                self._set_navigation_jump_phase(
                    "carrier_transit",
                    target=carrier_data.get("jump_destination"),
                    refresh=True,
                )
            return True
        if current_phase == "carrier_transit":
            self._clear_navigation_jump_phase(refresh=True)
        return False

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

    def _set_body_signals(self, body_id, bio_count=0, geo_count=0, genuses=None,
                          body_name=None, dss_complete=None):
        body_id = self._normalize_body_id(body_id)
        if body_id is None:
            return
        previous = self.body_signals.get(body_id, {})
        self.body_signals[body_id] = {
            "bio": int(bio_count or 0),
            "geo": int(geo_count or 0),
            "genuses": list(genuses) if genuses else list(previous.get("genuses") or []),
            "body_name": body_name or previous.get("body_name") or "",
            "dss_complete": (
                bool(dss_complete) if dss_complete is not None
                else bool(previous.get("dss_complete"))
            ),
        }
        self.system_bio_signals = sum(
            int(signals.get("bio", 0) or 0)
            for signals in self.body_signals.values()
        )

    def _record_belt_cluster(self, body_id, body_name, distance_ls=None,
                             was_discovered=None):
        """Retain a belt contact without adding it to the FSS body count."""
        name = str(body_name or "").strip()
        if not name:
            return False
        cluster = {
            "body_id": body_id,
            "name": name,
            "distance_ls": distance_ls,
            "was_discovered": was_discovered,
        }
        key = str(body_id) if body_id is not None else name.casefold()
        for index, existing in enumerate(self.belt_clusters):
            existing_key = (
                str(existing.get("body_id"))
                if existing.get("body_id") is not None
                else str(existing.get("name") or "").casefold()
            )
            if existing_key != key:
                continue
            if existing == cluster:
                return False
            self.belt_clusters[index] = cluster
            return True
        self.belt_clusters.append(cluster)
        return True

    def _mark_system_scan_complete(self, total=None):
        try:
            total = int(total or 0)
        except Exception:
            total = 0
        if total > 0:
            self.total = max(self.total, total)
        if self.total > 0:
            self.scan_total_confirmed = True
            self.scanned = self.total
            self.navigation_scan_progress = 1.0
            self.navigation_scan_progress_source = "bodies"
            self.db_update_system(self.current_sys, self.total, self.scanned)
            if not self.batch_mode:
                scan_text = self._scan_progress_count_text()
                self._ui_post(lambda value=scan_text: self.scan_stat.config(text=value), key="scan-progress-label")
                self.update_hud()
                self.schedule_dashboard_refresh()
                self._refresh_exploration_window()

    def _seed_navigation_scan_progress(self):
        """Seed the HUD from persisted body knowledge on entering a system."""
        if getattr(self, "scan_total_confirmed", True) is False:
            self.navigation_scan_progress = None
            self.navigation_scan_progress_source = "unknown"
        elif self.total > 0:
            self.navigation_scan_progress = max(0.0, min(1.0, self.scanned / self.total))
            self.navigation_scan_progress_source = "bodies"
        else:
            self.navigation_scan_progress = None
            self.navigation_scan_progress_source = "bodies"

    def _scan_progress_count_text(self, compact=False):
        separator = "/" if compact else " / "
        total = self.total if getattr(self, "scan_total_confirmed", True) else "?"
        return f"{self.scanned}{separator}{total}"

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
        self.scan_total_confirmed = True
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
            self.carrier_hud.show()
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
                if self.current_docked and self.current_station_name:
                    self.station_info_hud.on_docked(self)
        elif self.station_info_hud:
            try:
                self.station_info_hud.win.destroy()
            except Exception:
                pass
            self.station_info_hud = None

        if self.config.get("survey_status_overlay_enabled", True):
            if self.survey_status_hud is None:
                self.survey_status_hud = SurveyStatusHUD(self.root, self.config)
                if self.current_docked:
                    self.survey_status_hud.suppress()
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

        self._attach_html_overlay_renderers()
        self._apply_html_overlay_renderer()

        self._sync_cache_rebuild_edsm_option()
        self._apply_overlay_mouse_passthrough()
        self._apply_adaptive_overlay_scene()

    def _attach_html_overlay_renderers(self):
        """Give every managed Canvas overlay a surface in the shared host."""
        positions = {
            attr: (x_key, y_key) for attr, x_key, y_key in self._OVERLAY_POSITION_SPECS
        }
        for attr, (overlay_id, title, enabled_key) in self._HTML_CANVAS_OVERLAY_SPECS.items():
            overlay = getattr(self, attr, None)
            if overlay is None or not hasattr(overlay, "canvas"):
                continue
            x_key, y_key = positions[attr]
            if attr == "survey_status_hud":
                attach_html_survey_overlay(
                    overlay, overlay_id, title, enabled_key, x_key, y_key,
                )
            else:
                attach_html_canvas_overlay(
                    overlay, overlay_id, title, enabled_key, x_key, y_key,
                )

    def _apply_html_overlay_renderer(self):
        """Switch all overlay surfaces together; each retains native fallback."""
        enabled = bool(self.config.get("hud_html_renderer", False))
        for attr in ("hud", *self._HTML_CANVAS_OVERLAY_SPECS):
            overlay = getattr(self, attr, None)
            setter = getattr(overlay, "set_html_renderer", None)
            if callable(setter):
                setter(enabled)

    def open_settings(self):
        def on_save():
            self.log("Configuration saved successfully.")
            self._apply_active_profile_theme()
            self._apply_runtime_feature_toggles()
            self._configure_overlay_hotkeys()
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
                support_bundle_callback=self._create_support_bundle,
                rerun_setup_callback=self._rerun_first_run_onboarding,
                health_provider=self._adaptive_health_snapshot,
                ui_post_callback=self._ui_post,
                overlay_layout_callback=self.open_overlay_layout_studio,
                cache_rebuild_callback=self.scan_all_logs_threaded,
                cache_rebuild_button_register=(
                    lambda widget: setattr(self, "cache_rebuild_button", widget)
                ),
                hotkey_capture_begin_callback=self._suspend_overlay_hotkeys_for_capture,
                hotkey_capture_end_callback=self._resume_overlay_hotkeys_after_capture,
            )
        self._show_embedded_page("SETTINGS", self.settings_page)

    def open_overlay_layout_studio(self):
        studio = getattr(self, "overlay_layout_studio", None)
        if studio and studio.is_open():
            studio.lift()
            studio.refresh()
            return
        self.overlay_layout_studio = OverlayLayoutStudio(self.root, self)

    def fetch_system_traffic(self, system_name):
        self.last_edsm_request_ts = time.time()
        self._system_traffic_resolved = False
        def callback(traffic_data):
            def _apply():
                if self.current_sys != system_name:
                    return
                self._apply_system_traffic_context(system_name, traffic_data)
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
        return bool(
            system_name == self.current_sys
            and self._traffic_has_visits(self.system_traffic)
        )

    def _apply_system_traffic_context(self, system_name, traffic_data):
        """Share HUD traffic and resolve delayed discovery wording."""
        self._system_traffic_resolved = True
        if isinstance(traffic_data, dict):
            self.last_edsm_event_ts = time.time()
            self.system_traffic = self._normalize_system_traffic(traffic_data)

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

        return True

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
            scanned_bodies=self.scanned,
            total_known=self.scan_total_confirmed,
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

        # _perform_hud_update is already reached through the coalesced Tk
        # scheduler, so another after(0) only lengthens the queue during a
        # journal burst and permits stale frames to overtake newer state.
        if self.hud is target_hud:
            target_hud.update(*payload)
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
        return self._hud_balance_cache.get("balance")

    def _navigation_next_star_intelligence(self, next_name, hops, route_safety):
        """Describe only route facts Frontier supplies for the immediate leg."""
        first = next((hop for hop in (hops or ()) if hop.get("name") == next_name), None)
        if first is None and hops:
            first = hops[0]
        first = first or {}
        raw_star_class = str(first.get("star_class") or "").strip()
        star_class = raw_star_class.upper()
        scoopable = first.get("scoopable") if star_class else None
        dry_run = 0
        for hop in hops or ():
            if hop.get("scoopable") is False:
                dry_run += 1
            else:
                break
        safety = route_safety if isinstance(route_safety, dict) else {}
        endurance = safety.get("fuel_endurance_jumps")
        try:
            fuel_risk = "alert" if endurance is not None and float(endurance) <= 1.0 else (
                "warn" if endurance is not None and float(endurance) <= 2.0 else "ok"
            )
        except (TypeError, ValueError):
            fuel_risk = "alert" if safety.get("level") == "alert" else "ok"
        return {
            "name": next_name or "",
            "star_class": star_class,
            "star_label": star_type_label(raw_star_class) if star_class else "",
            "scoopable": scoopable,
            "consecutive_unscoopable": dry_run,
            "fuel_risk": fuel_risk,
        }

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

        selected_star = getattr(self, "_navigation_selected_star", None) or {}
        selected_name = str(selected_star.get("name") or "").strip()
        if not next_name and getattr(self, "target_waypoint", None):
            next_name = self.target_waypoint.get("name")
            next_coords = self.target_waypoint.get("coords")
        if (not next_name and selected_name
                and selected_name.casefold() != current.casefold()):
            next_name = selected_name
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
        route_track = route_strip.build_route_track(
            self.current_coords, route, entries, current,
            waypoint_manager=waypoint_manager,
        )
        if not hops and selected_name and selected_name == next_name:
            selected_class = str(selected_star.get("star_class") or "").strip()
            hops = [{
                "name": selected_name,
                "dist": None,
                "star_class": selected_class,
                "scoopable": (
                    selected_class.upper() in route_strip.SCOOPABLE_CLASSES
                    if selected_class else None
                ),
            }]

        if waypoint_manager and waypoint_manager.waypoints:
            route_mode = "WAYPOINT ROUTE"
        elif route:
            route_mode = "GAME ROUTE"
        elif selected_name:
            route_mode = "FSD TARGET"
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
        geo_signals = sum(
            int(signals.get("geo", 0) or 0)
            for signals in (getattr(self, "body_signals", None) or {}).values()
        )
        valuable_count = len(getattr(self, "valuable_bodies", None) or ())
        badges = []
        if self.system_undiscovered:
            badges.append(("UNDISC", "alert"))
        if valuable_count:
            badges.append((f"VALUE {valuable_count}", "info"))
        if self.system_bio_signals > self.organic_count:
            badges.append((f"BIO {self.organic_count}/{self.system_bio_signals}", "alert"))
        route_safety = self._route_safety_snapshot()
        next_star = self._navigation_next_star_intelligence(
            next_name, hops, route_safety,
        )
        fuel_percent = self._current_fuel_percent()
        fsd_readiness = self._navigation_fsd_readiness_context()
        local_target = self._navigation_local_target_context(next_name)
        galactic_vector = _galactic_vector_context(
            self.current_coords, next_coords,
        ) if next_name and next_coords else {}
        arrival_epoch = getattr(self, "_navigation_system_arrival_epoch", None)
        neutron_boost = {
            "armed": bool(getattr(self, "neutron_boost_armed", False)),
            "value": getattr(self, "neutron_boost_value", None),
        }
        altitude = getattr(self, "current_altitude_m", None)
        approach_body_known = getattr(self, "current_body_id", None) is not None
        glide_active = bool(getattr(self, "current_glide_mode", False))
        departure_active = bool(
            (approach_body_known or getattr(self, "on_planet", False))
            and not glide_active
            and getattr(self, "_surface_departure_active", False)
        )
        hold_active = bool(
            getattr(self, "on_planet", False)
            and not glide_active
            and getattr(self, "_surface_hold_active", False)
            and str(getattr(self, "hud_flight_state", "") or "").upper() == "FLIGHT"
        )
        if glide_active:
            approach_phase = "glide"
        elif hold_active:
            approach_phase = "hold"
        elif departure_active:
            approach_phase = (
                "orbital_departure"
                if str(getattr(self, "hud_flight_state", "") or "").upper() == "SUPERCRUISE"
                else "surface_departure"
            )
        elif str(getattr(self, "hud_flight_state", "") or "").upper() == "SUPERCRUISE":
            approach_phase = "orbital"
        else:
            approach_phase = "surface"
        surface_approach = {
            "active": bool(
                (approach_body_known or getattr(self, "on_planet", False))
                and not getattr(self, "current_landed", False)
                and not getattr(self, "current_docked", False)
                and not getattr(self, "current_on_foot", False)
                and not getattr(self, "current_in_srv", False)
                and not getattr(self, "current_in_fighter", False)
                and not getattr(self, "current_in_taxi", False)
                and not getattr(self, "current_in_multicrew", False)
            ),
            "phase": approach_phase,
            "body": getattr(self, "current_body_name", "") or "",
            "altitude_m": altitude,
            "descent_mps": (
                0.0 if hold_active else getattr(self, "_surface_descent_mps", 0.0)
            ),
            "departing": departure_active,
            "holding": hold_active,
        }
        ship_config = {
            "landing_gear": bool(getattr(self, "current_landing_gear_down", False)),
            "cargo_scoop": bool(getattr(self, "current_cargo_scoop_deployed", False)),
            "analysis_mode": bool(getattr(self, "current_analysis_mode", False)),
        }

        sampling = self._sampling_snapshot() if getattr(self, "bio_sampling", None) else None
        gravity_g = None
        body_id = self._normalize_body_id(getattr(self, "current_body_id", None))
        if body_id is not None:
            scan_data = (getattr(self, "body_scan_data", None) or {}).get(body_id, {})
            scan_item = (getattr(self, "scan_items_by_id", None) or {}).get(body_id, {})
            gravity_g = scan_data.get("gravity_g") or scan_item.get("gravity_g")
            if gravity_g is None:
                gravity_g = self._gravity_to_g(
                    scan_data.get("surface_gravity") or scan_item.get("surface_gravity")
                )

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
            "route_track": route_track,
            "total_distance_text": route_strip.total_distance_text(hops, hops_truncated),
            "cargo": f"{cargo_tons}/{cargo_cap}T" if cargo_cap else f"{cargo_tons}T",
            "credits": self._format_hud_credits(self._latest_hud_balance()),
            "station": self.current_station_name or "",
            "docked": bool(self.current_docked),
            "landed": bool(getattr(self, "current_landed", False)),
            "in_fighter": bool(getattr(self, "current_in_fighter", False)),
            "in_srv": bool(getattr(self, "current_in_srv", False)),
            "on_foot": bool(getattr(self, "current_on_foot", False)),
            "in_taxi": bool(getattr(self, "current_in_taxi", False)),
            "in_multicrew": bool(getattr(self, "current_in_multicrew", False)),
            "vehicle_name": getattr(self, "current_vehicle_name", ""),
            "in_fss": bool(getattr(self, "in_fss", False)),
            "flight_state": getattr(self, "hud_flight_state", "FLIGHT"),
            "music_mode": getattr(self, "current_music_mode", ""),
            "music_track": getattr(self, "current_music_track", ""),
            "gui_focus": getattr(self, "current_gui_focus", -1),
            "scan_progress": getattr(self, "navigation_scan_progress", None),
            "scan_progress_source": getattr(self, "navigation_scan_progress_source", "bodies"),
            "dss_complete": len(getattr(self, "body_dss_complete", None) or ()),
            "bio_complete": int(getattr(self, "organic_count", 0) or 0),
            "bio_signals": int(getattr(self, "system_bio_signals", 0) or 0),
            "geo_signals": geo_signals,
            "valuable_count": valuable_count,
            "undiscovered": bool(getattr(self, "system_undiscovered", False)),
            "body": getattr(self, "current_body_name", "") or "",
            "gravity_g": gravity_g,
            "sampling": sampling,
            "latitude": getattr(self, "current_latitude", None),
            "longitude": getattr(self, "current_longitude", None),
            "fuel_percent": fuel_percent,
            "fuel_scooping": bool(getattr(self, "current_scooping_fuel", False)),
            "supercruise_overcharge": bool(
                getattr(self, "current_supercruise_overcharge", False)
            ),
            "interdicted": bool(getattr(self, "current_interdicted", False)),
            "route_safety": route_safety,
            "next_star": next_star,
            "surface_approach": surface_approach,
            "ship_config": ship_config,
            "fsd_readiness": fsd_readiness,
            "local_target": local_target,
            "galactic_vector": galactic_vector,
            "system_arrival_epoch": arrival_epoch,
            "neutron_boost": neutron_boost,
            "region": self._navigation_region_context(),
            "journal_event": self._navigation_hud_event_context(),
            "badges": badges[:6],
        }

    def _navigation_region_context(self):
        """Return the current Codex region for the Navigation HUD.

        ``crossed`` stays true for a short spell after entering a new region so
        the HUD can mark the transition without spending a badge slot on it.
        Region changes are rare, so this settles to a stable value quickly and
        does not keep the render fingerprint churning.
        """
        coords = getattr(self, "current_coords", None)
        try:
            position = tuple(float(value) for value in coords)[:3]
        except (TypeError, ValueError):
            return {}
        if len(position) < 3:
            return {}
        region = find_region(*position)
        if not region:
            return {}
        region_id, name = region
        if region_id != getattr(self, "_hud_region_id", None):
            self._hud_region_id = region_id
            self._hud_region_since = time.monotonic()
        since = getattr(self, "_hud_region_since", 0.0)
        crossed = bool(since) and (time.monotonic() - since) < HUD_REGION_CROSSED_S
        return {"id": region_id, "name": name, "crossed": crossed}

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
        if key in ("supercruise", "destinationfromhyperspace"):
            return "SUPERCRUISE", label, False, "INFO"
        if key == "destinationfromsupercruise":
            return "MUSIC", label, False, "INFO"
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
        self._observe_navigation_music_transition(
            track, startup_replay=startup_replay,
        )
        previous_track = getattr(self, "current_music_track", "")
        if track == previous_track:
            return

        self.current_music_track = track
        self.current_music_mode = mode
        self.current_music_label = label
        self._last_music_event_ts = time.time()
        if mode == "ONFOOT":
            self.current_on_foot = True
        # The exact track matters to the HUD: GalaxyMap and SystemMap share the
        # MAP category, but must still repaint as distinct cockpit activities.
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

    def _navigation_vehicle_transition_label(self, event, raw, data):
        """Name a live vehicle hand-off without borrowing a ship-flight state."""
        event = str(event or "")
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        if event in {"LaunchSRV", "DockSRV"}:
            vehicle = self._srv_toast_vehicle_name(raw, data)
        elif event in {"LaunchFighter", "DockFighter"}:
            loadout = data.get("Loadout") or raw.get("Loadout")
            vehicle = "NOMAD" if str(loadout or "").casefold() == "galactic" else "FIGHTER"
        elif event in {"Embark", "Disembark"}:
            in_srv = bool(data.get("SRV") or raw.get("SRV"))
            taxi = bool(data.get("Taxi") or raw.get("Taxi"))
            multicrew = bool(data.get("Multicrew") or raw.get("Multicrew"))
            vehicle = (
                self._srv_toast_vehicle_name(raw, data) if in_srv
                else "TAXI" if taxi
                else "CREW SHIP" if multicrew
                else "SHIP"
            )
        elif event in {"JoinACrew", "QuitACrew", "EndCrewSession"}:
            if event == "JoinACrew":
                return "MULTICREW LINK"
            return "CREW RETURN"
        elif event == "VehicleSwitch":
            destination = str(data.get("To") or raw.get("To") or "").strip().casefold()
            if destination == "srv":
                vehicle = self._srv_toast_vehicle_name(raw, data)
            elif destination == "fighter":
                vehicle = "FIGHTER"
            elif destination == "mothership":
                vehicle = "MOTHERSHIP"
            else:
                vehicle = str(destination or "VEHICLE").upper()
        else:
            return ""

        if event.startswith("Launch"):
            return f"{vehicle} DEPLOY"
        if event.startswith("Dock"):
            return f"{vehicle} RECOVERY"
        if event == "Embark":
            return f"BOARDING {vehicle}"
        if event == "Disembark":
            return f"{vehicle} EGRESS"
        return f"{vehicle} CONTROL"

    def _observe_navigation_hud_event(self, event, raw, data, startup_replay=False):
        """Publish one compact, live-only event pulse to the Navigation HUD."""
        if (startup_replay or getattr(self, "_startup_restore_active", False)
                or not event):
            return False
        if event in {"FSSAllBodiesFound", "SAAScanComplete", "ScanOrganic"}:
            # Completion/sample state already has authoritative, persistent
            # presentation below the top instrument and in Survey Operations.
            # Do not resurrect the retired green survey channel as a short
            # journal pulse after the state-owned animation takes over.
            return False
        if event in {"Liftoff", "Touchdown"}:
            normalised = data if isinstance(data, dict) else {}
            payload = raw if isinstance(raw, dict) else {}
            player_controlled = normalised.get("player_controlled")
            if player_controlled is None:
                player_controlled = payload.get("PlayerControlled")
            remote_ship = player_controlled is False or any((
                getattr(self, "current_in_srv", False),
                getattr(self, "current_in_fighter", False),
                getattr(self, "current_on_foot", False),
                getattr(self, "current_in_taxi", False),
                getattr(self, "current_in_multicrew", False),
            ))
        else:
            remote_ship = False
        if remote_ship:
            # Empty or separately represented craft movement must not replace
            # the commander's active vehicle/passenger indicator with the
            # mothership's ascent or descent motion.
            return False
        spec = self._NAV_HUD_EVENT_SPECS.get(str(event))
        if not spec:
            return False

        kind, lane, tone, duration_s, priority = spec
        payload = raw if isinstance(raw, dict) else {}
        normalised = data if isinstance(data, dict) else {}
        if event == "CarrierJump" and not self._carrier_jump_presence(
            event, payload, normalised,
        )[0]:
            # An owner's remote carrier movement is operational data, not a
            # cockpit transition. Animate only when the commander moved too.
            return False

        # Enrich the generic event families with verified journal detail. The
        # HUD still receives a compact pulse, but it can now distinguish a
        # routine arrival/scan from a genuinely important exploration moment.
        if event == "FSDJump":
            star_class = str(
                payload.get("StarClass") or normalised.get("star_class") or ""
            ).strip().upper()
            if not star_class:
                arrived = str(
                    payload.get("StarSystem") or normalised.get("star_system") or ""
                ).strip().casefold()
                matching_entry = next(
                    (entry for entry in (getattr(self, "nav_route_entries", None) or ())
                     if str((entry or {}).get("StarSystem") or "").strip().casefold() == arrived),
                    {},
                )
                star_class = str(matching_entry.get("StarClass") or "").strip().upper()
            if star_class in {"N", "NS"}:
                kind, tone, duration_s = "arrival_neutron", "accent", 2.1
            elif star_class in WHITE_DWARF_CLASSES:
                kind, tone, duration_s = "arrival_white_dwarf", "yellow", 2.1
        elif event == "FSDTarget":
            selected = str(
                payload.get("Name") or payload.get("StarSystem")
                or normalised.get("name") or normalised.get("star_system") or ""
            ).strip()
            selected_class = str(
                payload.get("StarClass") or normalised.get("star_class") or ""
            ).strip()
            self._navigation_selected_star = {
                "name": selected,
                "star_class": selected_class,
                "remaining": payload.get("RemainingJumpsInRoute"),
            } if selected else None
            route = list(getattr(self, "route_list", None) or ())
            plotted = {str(name or "").strip().casefold() for name in route}
            # FSDTarget may name the final route destination rather than the
            # immediate hop. Only call it a diversion when it leaves the
            # plotted systems entirely.
            if selected and plotted and selected.casefold() not in plotted:
                kind, tone, duration_s, priority = "route_divert", "yellow", 1.5, 72
        elif event == "Scan":
            body_name = str(
                payload.get("BodyName") or normalised.get("body_name") or ""
            ).strip()
            planet_class = str(
                payload.get("PlanetClass") or normalised.get("planet_class") or ""
            ).strip()
            terraformable = str(
                payload.get("TerraformState") or normalised.get("terraform_state") or ""
            ).casefold() == "terraformable"
            first_discovery = (
                payload.get("WasDiscovered") is False
                or normalised.get("was_discovered") is False
            )
            first_footfall = bool(
                (payload.get("Landable") or normalised.get("landable"))
                and (payload.get("WasFootfalled") is False
                     or normalised.get("was_footfalled") is False)
            )
            if planet_class in HIGH_VALUE_WORLDS or terraformable:
                kind, tone, duration_s, priority = "valuable_discovery", "yellow", 2.0, 86
            elif first_discovery:
                kind, tone, duration_s, priority = "first_discovery", "green", 1.8, 78
            elif first_footfall:
                kind, tone, duration_s, priority = "footfall_candidate", "green", 1.7, 74
        elif event == "ProspectedAsteroid":
            materials = payload.get("Materials") or normalised.get("materials") or ()
            material_rows = [item for item in materials if isinstance(item, dict)]
            proportions = []
            for item in material_rows:
                try:
                    proportions.append(max(0.0, float(item.get("Proportion") or 0.0)))
                except (TypeError, ValueError):
                    continue
            best_proportion = max(proportions, default=0.0)
            content = str(
                payload.get("Content_Localised") or payload.get("Content")
                or normalised.get("content") or ""
            ).strip().casefold()
            motherlode = str(
                payload.get("MotherlodeMaterial_Localised")
                or payload.get("MotherlodeMaterial")
                or normalised.get("motherlode_material") or ""
            ).strip()
            if motherlode:
                kind, tone, duration_s, priority = "prospector_core", "green", 2.0, 82
            elif "high" in content or best_proportion >= 45.0:
                kind, tone, duration_s, priority = "prospector_rich", "yellow", 1.9, 72
        uss_threat = 0
        if event == "USSDrop":
            try:
                uss_threat = int(payload.get("USSThreat") or 0)
            except (TypeError, ValueError):
                uss_threat = 0
            if uss_threat >= 3:
                tone = "orange"
                priority = max(priority, 86 if uss_threat < 5 else 98)
        now = time.monotonic()
        previous = getattr(self, "_hud_event_pulse", None)
        recent = bool(previous and now - float(previous.get("observed", 0.0) or 0.0) < 0.55)

        # A live watcher batch often contains several descriptions of one
        # moment. Preserve its strongest cue; repeated scans of the same kind
        # are coalesced into a bounded count for the right-hand pulse train.
        batch_priority = getattr(self, "_hud_event_batch_priority", None)
        if (getattr(self, "batch_mode", False)
                and batch_priority is not None
                and previous.get("kind") != kind
                and int(batch_priority) > priority):
            return False

        count = 1
        if recent and previous.get("kind") == kind:
            count = min(3, int(previous.get("count", 1) or 1) + 1)

        detail = {}
        if kind in {"vehicle_deploy", "vehicle_board", "vehicle_switch"}:
            state_label = self._navigation_vehicle_transition_label(
                event, payload, normalised,
            )
            if state_label:
                detail["state_label"] = state_label
        if kind == "bio_sample":
            scan_type = str(
                normalised.get("scan_type") or payload.get("ScanType") or ""
            ).strip().casefold()
            detail["sample_step"] = 3 if scan_type == "analyse" else 1 if scan_type == "log" else 2
        elif kind == "fss_progress":
            progress = normalised.get("progress", payload.get("Progress"))
            try:
                detail["progress"] = max(0.0, min(1.0, float(progress)))
            except (TypeError, ValueError):
                pass
        elif kind == "honk":
            body_count = normalised.get("body_count", payload.get("BodyCount"))
            try:
                detail["body_count"] = max(0, int(body_count or 0))
            except (TypeError, ValueError):
                pass
        elif kind in {"valuable_discovery", "first_discovery", "footfall_candidate"}:
            detail["body_name"] = body_name
        elif kind in {"prospector_scan", "prospector_rich", "prospector_core"}:
            detail["material_count"] = min(3, len(material_rows))
            detail["max_proportion"] = best_proportion
            if motherlode:
                detail["motherlode_material"] = motherlode
        elif kind == "mining_refined":
            detail["material_name"] = str(
                payload.get("Type_Localised") or payload.get("Type")
                or normalised.get("type") or ""
            ).strip()
        elif event == "Interdicted":
            detail["state_label"] = "INTERDICTED"
        elif event == "EscapeInterdiction":
            detail["state_label"] = "INTERDICTION EVADED"
        elif event == "USSDrop":
            detail["state_label"] = "SIGNAL DROP"
            if uss_threat >= 3:
                detail["state_label"] = f"SIGNAL THREAT {uss_threat}"

        self._hud_event_sequence = int(getattr(self, "_hud_event_sequence", 0) or 0) + 1
        self._hud_event_pulse = {
            "seq": self._hud_event_sequence,
            "event": str(event),
            "kind": kind,
            "lane": lane,
            "tone": tone,
            "duration": float(duration_s),
            "priority": int(priority),
            "count": count,
            "observed": now,
            **detail,
        }
        if event in {"FSDJump", "CarrierJump", "NavRouteClear"}:
            self._navigation_selected_star = None
        if getattr(self, "batch_mode", False):
            self._hud_event_batch_priority = priority
        else:
            self.update_hud()
        return True

    def _promote_navigation_arrival_personality(self, event, startup_replay=False):
        """Promote an ordinary arrival after cached survey value is restored."""
        if startup_replay or event != "FSDJump" or not self.valuable_system:
            return False
        pulse = getattr(self, "_hud_event_pulse", None)
        if not isinstance(pulse, dict) or pulse.get("kind") != "arrival":
            # Compact-star and carrier signatures retain safety priority.
            return False
        self._hud_event_sequence = int(getattr(self, "_hud_event_sequence", 0) or 0) + 1
        promoted = dict(pulse)
        promoted.update({
            "seq": self._hud_event_sequence,
            "kind": "arrival_valuable",
            "tone": "yellow",
            "duration": 2.1,
            "priority": 96,
        })
        self._hud_event_pulse = promoted
        return True

    def _navigation_hud_event_context(self):
        pulse = getattr(self, "_hud_event_pulse", None)
        if not isinstance(pulse, dict):
            return None
        try:
            age = time.monotonic() - float(pulse.get("observed", 0.0))
            duration = float(pulse.get("duration", 0.0))
        except (TypeError, ValueError):
            return None
        if age < 0 or age > duration + 0.5:
            return None
        return dict(pulse)

    def _cancel_navigation_transition_job(self):
        job = getattr(self, "_navigation_transition_job", None)
        self._navigation_transition_job = None
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except Exception:
            pass

    def _expire_navigation_jump_phase(self, expected_phase):
        self._navigation_transition_job = None
        if str(getattr(self, "_navigation_jump_phase", "") or "") != expected_phase:
            return
        self._clear_navigation_jump_phase(refresh=True)

    def _schedule_navigation_jump_phase_expiry(self, phase):
        self._cancel_navigation_transition_job()
        root = getattr(self, "root", None)
        after = getattr(root, "after", None)
        if not callable(after):
            return
        delay_ms = {
            "charging": 12000,
            "hyperspace": 90000,
            "arrival": 1800,
            "carrier_transit": 180000,
            "carrier_arrival": 3200,
        }.get(phase)
        if delay_ms is None:
            return
        try:
            self._navigation_transition_job = after(
                delay_ms,
                lambda expected=phase: self._expire_navigation_jump_phase(expected),
            )
        except Exception:
            self._navigation_transition_job = None

    def _schedule_navigation_charge_resolution(self):
        """Resolve a possible cancelled charge without hiding a real jump."""
        if getattr(self, "_navigation_charge_resolution_pending", False):
            return
        self._navigation_charge_resolution_pending = True
        self._cancel_navigation_transition_job()
        root = getattr(self, "root", None)
        after = getattr(root, "after", None)
        if not callable(after):
            self._navigation_charge_resolution_pending = False
            return
        try:
            def resolve():
                self._navigation_charge_resolution_pending = False
                self._expire_navigation_jump_phase("charging")

            self._navigation_transition_job = after(
                1500, resolve,
            )
        except Exception:
            self._navigation_transition_job = None
            self._navigation_charge_resolution_pending = False

    def _set_navigation_jump_phase(
        self, phase, *, target=None, refresh=True, schedule=True,
    ):
        """Set one bounded ship/carrier transition without inventing events."""
        phase = str(phase or "").strip().casefold()
        if phase not in {
            "charging", "hyperspace", "arrival",
            "carrier_transit", "carrier_arrival",
        }:
            phase = ""
        previous = str(getattr(self, "_navigation_jump_phase", "") or "")
        previous_target = str(getattr(self, "_navigation_jump_target", "") or "")
        next_target = previous_target if target is None else str(target or "").strip()
        changed = phase != previous or next_target != previous_target
        self._navigation_jump_phase = phase
        self._navigation_jump_target = next_target
        self._navigation_jump_phase_started = time.monotonic() if phase else 0.0
        if phase != "charging" or previous != "charging":
            self._navigation_charge_resolution_pending = False
        if phase == "charging":
            self._navigation_jump_charge_seen = bool(
                getattr(self, "current_fsd_charging", False)
                and getattr(self, "current_fsd_hyperdrive_charging", False)
            )
        elif phase != "hyperspace":
            self._navigation_jump_charge_seen = False
        if schedule:
            if phase:
                self._schedule_navigation_jump_phase_expiry(phase)
            else:
                self._cancel_navigation_transition_job()
        if changed and refresh and not getattr(self, "batch_mode", False):
            self.update_hud()
        return changed

    def _clear_navigation_jump_phase(self, *, refresh=True):
        return self._set_navigation_jump_phase(
            "", target="", refresh=refresh, schedule=True,
        )

    def _observe_navigation_jump_event(self, event, raw, data, startup_replay=False):
        """Track ship and onboard carrier travel as distinct phases."""
        event = str(event or "")
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        if event == "StartJump":
            jump_type = str(
                raw.get("JumpType") or data.get("jump_type") or ""
            ).strip().casefold()
            if jump_type == "hyperspace":
                target = raw.get("StarSystem") or data.get("star_system")
                return self._set_navigation_jump_phase(
                    "charging", target=target,
                    refresh=not startup_replay,
                )
            if jump_type == "supercruise":
                return self._clear_navigation_jump_phase(refresh=not startup_replay)
        elif event == "FSDJump":
            self.current_fsd_jumping = False
            self.current_fsd_charging = False
            self.current_fsd_hyperdrive_charging = False
            if startup_replay:
                return self._clear_navigation_jump_phase(refresh=False)
            target = raw.get("StarSystem") or data.get("star_system")
            return self._set_navigation_jump_phase("arrival", target=target)
        elif event == "CarrierJump":
            self.current_fsd_jumping = False
            self.current_fsd_charging = False
            self.current_fsd_hyperdrive_charging = False
            if startup_replay:
                return self._clear_navigation_jump_phase(refresh=False)
            player_location, _docked, _on_foot = self._carrier_jump_presence(
                event, raw, data,
            )
            if player_location:
                target = raw.get("StarSystem") or data.get("star_system")
                return self._set_navigation_jump_phase(
                    "carrier_arrival", target=target,
                )
            if str(getattr(self, "_navigation_jump_phase", "") or "") == "carrier_transit":
                return self._clear_navigation_jump_phase()
        elif event in {
            "LoadGame", "Shutdown", "Died", "Resurrect",
            "ShipyardBuy", "ShipyardNew", "ShipyardSwap",
        }:
            self.current_fsd_jumping = False
            return self._clear_navigation_jump_phase(refresh=not startup_replay)
        return False

    def _observe_navigation_music_transition(self, track, startup_replay=False):
        """Use music moods only as scoped corroboration for live travel state."""
        key = str(track or "").replace(" ", "").replace("_", "").casefold()
        phase = str(getattr(self, "_navigation_jump_phase", "") or "")
        changed = False
        try:
            phase_age = time.monotonic() - float(
                getattr(self, "_navigation_jump_phase_started", 0.0) or 0.0
            )
        except (TypeError, ValueError):
            phase_age = 0.0
        if key == "notrack" and phase == "charging" and (
                getattr(self, "_navigation_jump_charge_seen", False)
                or getattr(self, "current_fsd_hyperdrive_charging", False)
                or phase_age >= 3.0):
            # Your live journal changes to NoTrack as the tunnel opens. The
            # official Status fsdJump bit remains primary; this covers a poll
            # that happens to miss that short-lived flag. The elapsed-countdown
            # guard prevents an unrelated immediate music stop becoming a jump.
            changed = self._set_navigation_jump_phase(
                "hyperspace", refresh=not startup_replay,
            )
        protected_state = any(getattr(self, attr, False) for attr in (
            "current_docked", "current_landed", "current_in_srv",
            "current_in_fighter", "current_on_foot", "current_in_taxi",
            "current_in_multicrew",
        ))
        if key in {"supercruise", "destinationfromhyperspace"} and not protected_state:
            if getattr(self, "hud_flight_state", "") != "SUPERCRUISE":
                self.hud_flight_state = "SUPERCRUISE"
                changed = True
                if not startup_replay and not getattr(self, "batch_mode", False):
                    self.update_hud()
        elif (key == "destinationfromsupercruise" and not protected_state
                and getattr(self, "hud_flight_state", "") == "SUPERCRUISE"):
            # This track is emitted after SupercruiseExit in the live journal.
            # It is an exit corroboration, never evidence that SC is active.
            self.hud_flight_state = "FLIGHT"
            changed = True
            if not startup_replay and not getattr(self, "batch_mode", False):
                self.update_hud()
        return changed

    def _observe_navigation_readiness_event(self, event, raw, data, startup_replay=False):
        """Maintain profile-safe neutron boost readiness from journal truth."""
        event = str(event or "")
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        was_armed = bool(getattr(self, "neutron_boost_armed", False))
        was_value = getattr(self, "neutron_boost_value", None)

        if event == "JetConeBoost":
            self.neutron_boost_armed = True
            value = raw.get("BoostValue", data.get("boost_value"))
            try:
                self.neutron_boost_value = float(value) if value is not None else None
            except (TypeError, ValueError):
                self.neutron_boost_value = None
        elif event in {
            "FSDJump", "Died", "Shutdown", "LoadGame",
            "ShipyardBuy", "ShipyardNew", "ShipyardSwap",
        }:
            self.neutron_boost_armed = False
            self.neutron_boost_value = None
        else:
            return False

        changed = (
            was_armed != bool(self.neutron_boost_armed)
            or was_value != self.neutron_boost_value
        )
        if changed and not startup_replay and not getattr(self, "batch_mode", False):
            self.update_hud()
        return changed

    @staticmethod
    def _navigation_destination_label(value):
        """Turn the Status destination token into a restrained HUD label."""
        text = str(value or "").strip()
        if not text:
            return ""
        if text.startswith("$"):
            text = text.strip("$;")
            text = text.split(":", 1)[0]
            for suffix in ("_Name_Localised", "_Name", "_Localised"):
                if text.casefold().endswith(suffix.casefold()):
                    text = text[:-len(suffix)]
                    break
            text = text.replace("_", " ")
        return " ".join(text.split())

    @staticmethod
    def _navigation_asteroid_field_kind(body_type):
        """Classify the normal-space destinations Frontier uses for rock fields."""
        key = "".join(
            char for char in str(body_type or "").casefold()
            if char.isalnum()
        )
        return {
            "planetaryring": "ring",
            "stellarring": "belt",
            "asteroidcluster": "cluster",
        }.get(key, "")

    def _capture_navigation_local_space(self, raw, data=None):
        """Remember the authoritative destination of a normal-space drop."""
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        body_type = (
            raw.get("BodyType") or data.get("BodyType")
            or data.get("body_type") or ""
        )
        body_name = (
            raw.get("Body") or data.get("Body")
            or data.get("body") or data.get("body_name") or ""
        )
        self.current_local_space_body_type = str(body_type or "").strip()
        self.current_local_space_name = str(body_name or "").strip()
        self.current_asteroid_field_kind = self._navigation_asteroid_field_kind(
            self.current_local_space_body_type
        )

    def _clear_navigation_local_space(self):
        self.current_local_space_body_type = ""
        self.current_local_space_name = ""
        self.current_asteroid_field_kind = ""

    def _navigation_fsd_readiness_context(self):
        phase = str(getattr(self, "_navigation_jump_phase", "") or "")
        jumping = bool(getattr(self, "current_fsd_jumping", False))
        hyperdrive = bool(getattr(self, "current_fsd_hyperdrive_charging", False))
        charging = bool(
            getattr(self, "current_fsd_charging", False)
            or hyperdrive
            or phase == "charging"
        )
        high_wake = bool(
            phase in {"charging", "hyperspace"}
            or getattr(self, "_navigation_jump_charge_seen", False)
            or hyperdrive
        )
        cooldown = bool(getattr(self, "current_fsd_cooldown", False))
        mass_locked = bool(getattr(self, "current_fsd_mass_locked", False))
        asteroid_kind = str(
            getattr(self, "current_asteroid_field_kind", "") or ""
        )
        if phase == "carrier_transit":
            state, label, tone = "carrier_transit", "CARRIER TRANSIT", "orange"
        elif phase == "carrier_arrival":
            state, label, tone = "carrier_arrival", "CARRIER ARRIVAL", "green"
        elif phase == "arrival":
            state, label, tone = "arrival", "ARRIVAL", "green"
        elif phase == "hyperspace" or (jumping and high_wake):
            state, label, tone = "hyperspace", "HYPERSPACE", "orange"
        elif jumping:
            # The same Status flag is raised for an in-system low wake. Keep
            # its identity and animation distinct from witch-space.
            state, label, tone = "supercruise_entry", "SUPERCRUISE", "orange"
        elif charging:
            state = "hyper_charge" if hyperdrive else "charge"
            if phase == "charging":
                state = "hyper_charge"
            label = "HYPER CHARGE" if hyperdrive else "FSD CHARGE"
            if state == "hyper_charge":
                label = "HYPER CHARGE"
            tone = "orange"
        elif cooldown:
            state, label, tone = "cooldown", "FSD COOLDOWN", "accent"
        elif asteroid_kind:
            # The Status mass-lock bit remains useful FSD information, but a
            # PlanetaryRing/StellarRing/AsteroidCluster drop is the more meaningful live
            # navigation state for the centre instrument.
            state, label, tone = "asteroid_field", "ASTEROID FIELD", "yellow"
        elif mass_locked:
            state, label, tone = "mass_lock", "MASS LOCK", "yellow"
        else:
            state, label, tone = "ready", "FSD READY", "green"
        return {
            "state": state,
            "label": label,
            "tone": tone,
            "mass_locked": mass_locked,
            "charging": charging,
            "hyperdrive": hyperdrive,
            "cooldown": cooldown,
            "jumping": jumping,
            "high_wake": high_wake,
            "phase": phase,
            "target": str(getattr(self, "_navigation_jump_target", "") or ""),
            "asteroid_kind": asteroid_kind,
            "local_space_type": str(
                getattr(self, "current_local_space_body_type", "") or ""
            ),
            "local_space_name": str(
                getattr(self, "current_local_space_name", "") or ""
            ),
        }

    def _navigation_local_target_context(self, next_system=None):
        details = getattr(self, "current_destination_details", None) or {}
        if not isinstance(details, dict):
            return None
        name = self._navigation_destination_label(details.get("Name"))
        if not name:
            return None
        duplicates = {
            str(value or "").strip().casefold()
            for value in (next_system, getattr(self, "dest_name", None))
            if str(value or "").strip()
        }
        if name.casefold() in duplicates:
            return None
        station = str(getattr(self, "current_station_name", "") or "").strip()
        if getattr(self, "current_docked", False) and station and name.casefold() == station.casefold():
            return None
        current_body = str(getattr(self, "current_body_name", "") or "").strip()
        return {
            "name": name,
            "system": details.get("System"),
            "body": details.get("Body"),
            "is_current_body": bool(current_body and name.casefold() == current_body.casefold()),
        }

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
            f"SCAN {self._scan_progress_count_text(compact=True)}",
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

    def _set_commander_balance(self, balance, loan=None, timestamp=None, log=True):
        try:
            balance = int(balance)
        except Exception:
            return False
        if self.session_start_balance is None:
            self.session_start_balance = balance
        changed = self.cmdr_balance != balance or (loan is not None and self.cmdr_loan != loan)
        self.cmdr_balance = balance
        self._hud_balance_cache = {"ts": time.time(), "balance": balance}
        if loan is not None:
            self.cmdr_loan = loan
        if changed:
            self._refresh_commander_profile_window()
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

    def _invalidate_exploration_intelligence(self):
        self._exploration_intelligence_ts = 0.0

    def _exploration_intelligence_snapshot(self, compact=False):
        # Rebuilding deep-copies the Codex, checkpoint and milestone state under
        # the tracker lock, and a burst of Scan events asked for it repeatedly
        # from the same drain. Reuse holds only for the length of one burst, so
        # the packet still reflects the batch being processed.
        now = time.monotonic()
        intelligence = getattr(self, "_latest_exploration_intelligence", None)
        fresh = (
            intelligence is not None
            and (now - getattr(self, "_exploration_intelligence_ts", 0.0))
            < EXPLORATION_INTELLIGENCE_TTL_S
        )
        if not fresh:
            try:
                intelligence = build_intelligence(self)
            except Exception as exc:
                logging.debug("Exploration intelligence snapshot skipped: %s", exc)
                return {}
            self._exploration_intelligence_ts = now
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
        # A checkpoint is the record a commander resumes from, so it always
        # rebuilds rather than accepting a packet cached during a burst. The
        # fresh packet is then reused by whatever reads it next.
        self._invalidate_exploration_intelligence()
        try:
            return tracker.update_checkpoint(
                checkpoint_payload(
                    self, reason,
                    intelligence=self._exploration_intelligence_snapshot(),
                ),
                immediate=immediate,
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
            "HullDamage", "RepairAll", "Loadout", "Synthesis", "JetConeBoost",
        }
        if ev not in relevant:
            return
        self._invalidate_exploration_intelligence()
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
        """Retain journal awareness without exposing a Trade workspace."""
        trade = getattr(self, "trade_session", {}) or {}
        events = list(trade.get("events") or [])
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
            "plan": None,
        }

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
        """Retained call-site shim; spoken cockpit feedback was retired in v5.3.6."""
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
        """Retire mode-based overlay hiding while preserving explicit controls.

        Module enable switches are now the single source of truth for overlay
        availability. Activity modes may still prioritise dashboard content,
        but cannot withdraw an enabled overlay. Restore anything hidden by an
        earlier adaptive scene, then reapply deliberate hotkey visibility.
        """
        hidden = getattr(self, "_adaptive_hidden_overlays", set())
        for attr in tuple(hidden):
            instance = getattr(self, attr, None)
            window = self._overlay_window(instance)
            if window is None:
                continue
            try:
                if attr == "carrier_hud" and hasattr(instance, "show"):
                    instance.show()
                else:
                    window.deiconify()
            except (AttributeError, tk.TclError):
                pass
        self._adaptive_hidden_overlays = set()
        self._enforce_overlay_hotkey_visibility()

    def _update_adaptive_command(self, event, raw, startup_replay=False):
        deck = getattr(self, "adaptive_command", None)
        if not deck or startup_replay:
            return
        if event == "Shutdown":
            deck.close_session("Session complete")
            return
        detected = self._detected_adaptive_mode()
        transition = deck.observe(event, detected, raw, historical=False)
        if not transition.get("changed"):
            return
        mode = transition.get("mode") or "general"
        self._apply_adaptive_overlay_scene(mode)
        self.schedule_dashboard_refresh(full=True)

    def _adaptive_startup_mode(self):
        if getattr(self, "_adaptive_startup_synced", False):
            return
        self._adaptive_startup_synced = True
        deck = getattr(self, "adaptive_command", None)
        if not deck or not self.config.get("adaptive_command_enabled", True):
            return
        detected = self._detected_adaptive_mode()
        if detected:
            deck.observe("StartupReady", detected, {}, historical=False)
        mode = deck.current_mode
        self._apply_adaptive_overlay_scene(mode)

    def _detected_adaptive_mode(self):
        """Return live activity, aging stale automatic evidence to general flight."""
        activity = (
            (getattr(self, "ai_operational_state", {}) or {}).get("activity") or {}
        )
        mode = activity.get("mode") or "general"
        if mode not in FOCUSED_MODES:
            mode = "general"
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
            exploration_focus=self.config.get("cockpit_exploration_focus_enabled", False),
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

    def _push_live_toast(self, title, message="", severity="info", duration_s=10,
                         voice_text=None, voice_category="safety", voice_key=None):
        toast = getattr(self, "toast_hud", None)
        if toast:
            toast.push(title, message, severity=severity, duration_s=duration_s)

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
        explicit_key = str(explicit or "").strip().casefold()
        if explicit_key:
            if "nomad" in explicit_key or explicit_key == "lander01":
                return "NOMAD"
            # A concrete Scarab/Scorpion identity beats an older remembered
            # Nomad, particularly when commanders swap bays between sorties.
            if any(token in explicit_key for token in (
                    "scarab", "scorpion", "testbuggy", "combat")):
                return "SRV"
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
            escaped = ev == "EscapeInterdiction"
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
            # ScanOrganic reaches this toast only after the main reducer has
            # stored the event. Display that exact index; adding one here made
            # a first Log toast claim 2/3 while the database correctly held 1.
            sample = existing.get("sample_idx") or (
                max_samples if complete else 1
            )
            detail = "Analysis complete" if complete else f"Sample {sample}/{max_samples}"
            self._push_live_toast(
                "BIO COMPLETE" if complete else "BIO SAMPLE", f"{species}: {detail}",
                "success" if complete else "info", 12,
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

    @staticmethod
    def _carrier_jump_presence(event, raw, data):
        """Resolve whether/how a CarrierJump moved the active commander."""
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        if event != "CarrierJump":
            return False, False, False
        docked = bool(data.get("docked") or raw.get("Docked"))
        on_foot = bool(data.get("on_foot") or raw.get("OnFoot"))
        player_location = bool(data.get("player_location") or docked or on_foot)
        return player_location, docked, on_foot

    @staticmethod
    def _navigation_passenger_flags(raw, data):
        """Return journal-backed Apex/dropship and multicrew ownership flags."""
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        taxi = data.get("in_taxi")
        if taxi is None:
            taxi = data.get("Taxi")
        if taxi is None:
            taxi = raw.get("Taxi")
        multicrew = data.get("in_multicrew")
        if multicrew is None:
            multicrew = data.get("Multicrew")
        if multicrew is None:
            multicrew = raw.get("Multicrew")
        return bool(taxi), bool(multicrew)

    def process_event(self, data):
        ev = data.get("type") or data.get("event")
        raw = data.get("raw", data)
        d = data.get("data", data)
        (
            carrier_jump_player_location,
            carrier_jump_docked,
            carrier_jump_on_foot,
        ) = self._carrier_jump_presence(
            ev, raw, d,
        )
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
        self._observe_navigation_jump_event(
            ev,
            raw if isinstance(raw, dict) else d,
            d,
            startup_replay=startup_replay,
        )
        self._observe_navigation_readiness_event(
            ev,
            raw if isinstance(raw, dict) else d,
            d,
            startup_replay=startup_replay,
        )
        self._observe_navigation_hud_event(
            ev,
            raw if isinstance(raw, dict) else d,
            d,
            startup_replay=startup_replay,
        )
        self._observe_surface_trail_event(
            ev, raw if isinstance(raw, dict) else d,
            startup_replay=startup_replay,
        )
        specialist_changed = False
        at_own_carrier = bool(
            getattr(self, "current_docked", False)
            and getattr(self, "current_station_market_id", None)
            and getattr(self.carrier_tracker, "carrier_data", {}).get("carrier_id")
            == getattr(self, "current_station_market_id", None)
        )
        try:
            specialist_engine = getattr(self, "specialist_engine", None)
            specialist_changed = bool(specialist_engine) and specialist_engine.observe_event(
                raw if isinstance(raw, dict) else d,
                event_uid=data.get("_journal_uid"),
                context={
                    "system": getattr(self, "current_sys", None),
                    "body": getattr(self, "current_body_name", None),
                    "historical": startup_replay,
                    "at_own_carrier": at_own_carrier,
                },
                defer_save=True,
            )
        except Exception as exc:
            logging.warning("Specialist workflow event failed [%s]: %s", ev, exc)
        if ev == "CargoTransfer" and at_own_carrier and not startup_replay:
            try:
                self.carrier_tracker.apply_observed_cargo_transfer(raw)
            except Exception as exc:
                logging.warning("Carrier cargo total update failed: %s", exc)
        if specialist_changed and not self.batch_mode:
            self._schedule_specialist_flush()
            window = getattr(self, "specialists_window", None)
            if window and window.is_open() and getattr(self, "_active_page", None) == "SPECIALISTS":
                self._ui_post(window.refresh, key="specialists-refresh")
            carrier_window = getattr(self, "carrier_window", None)
            if carrier_window and carrier_window.is_open():
                carrier_window.on_specialist_updated()
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
        # Apply personal-credit changes before toast and tool
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
                        "star_pos": list(getattr(self, "current_coords", None) or ()),
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
        # Biological toast text depends on the authoritative sample index that
        # is written in the main reducer below. Publish every other toast here,
        # then emit ScanOrganic only after that state has settled.
        if ev != "ScanOrganic":
            self._handle_live_journal_toast(
                ev, raw, d, startup_replay=startup_replay,
            )
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
            if not startup_replay:
                self._publish_expedition_resume_briefing()
        # ScanOrganic owns a strict presentation order: persist the body result
        # in the main reducer first, then advance/clear the sampler card.  Doing
        # this here used to clear Analyse before Survey Operations could see the
        # completed body, leaving body focus open without its three sample nodes.
        if ev != "ScanOrganic":
            self._process_companion_event(
                ev, raw if isinstance(raw, dict) else {}, d,
                startup_replay=startup_replay,
            )
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
            fuel_cap = d.get("fuel_capacity")
            if fuel_cap is None and isinstance(raw, dict):
                fuel_cap = raw.get("FuelCapacity")
            if isinstance(fuel_cap, dict):
                fuel_cap = fuel_cap.get("Main")
            try:
                if fuel_cap is not None and float(fuel_cap) > 0:
                    self.fuel_capacity_main = float(fuel_cap)
            except (TypeError, ValueError):
                pass
            self._low_fuel_warned = False
            self.cmdr_ship, _ = companion_features.update_active_ship(
                self.cmdr_ship, ev, raw
            )
            self.watcher.force_check_cargo()
            self._refresh_cargo_consumers()
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
                self.watcher.force_check_cargo()
                self._refresh_cargo_consumers()
            if ship_changed:
                self._refresh_commander_profile_window()
            # Buy is already queued by the shared credit-event path and New is
            # discarded by EDSM. Swap and naming events are accepted fleet
            # updates and must not be silently lost.
            if ev in ("ShipyardSwap", "SetUserShipName"):
                self._queue_edsm_upload(raw, allow_startup=True)

        elif ev == "StoredShips":
            # EDSM uses this authoritative shipyard snapshot to update every
            # stored ship, including a whole fleet parked aboard one carrier.
            self._queue_edsm_upload(raw, allow_startup=True, flush=True)

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
            self.edsm.sync_latest_fleet_snapshot(
                self.config.get("journal_path", ""),
            )
            self.cmdr_ship, _ = companion_features.update_active_ship(
                self.cmdr_ship, ev, raw
            )
            try:
                if d.get("fuel_level") is not None:
                    self.current_fuel_main = float(d.get("fuel_level"))
            except (TypeError, ValueError):
                pass
            fuel_capacity = d.get("fuel_capacity")
            if isinstance(fuel_capacity, dict):
                fuel_capacity = fuel_capacity.get("Main")
            try:
                if fuel_capacity is not None and float(fuel_capacity) > 0:
                    self.fuel_capacity_main = float(fuel_capacity)
            except (TypeError, ValueError):
                pass
            self._refresh_commander_profile_window()

        elif ev == "FuelScoop":
            # FuelScoop.Total is the journal-confirmed tank level after the
            # scoop. Status.json supplies the finer-grained readings while the
            # scoop is still running.
            total_fuel = raw.get("Total") if isinstance(raw, dict) else None
            if total_fuel is None and isinstance(d, dict):
                total_fuel = d.get("Total")
            try:
                if total_fuel is not None:
                    self.current_fuel_main = float(total_fuel)
            except (TypeError, ValueError):
                pass
            self.watcher.force_check_status()
            if not self.batch_mode:
                self.update_hud()

        elif ev in ("RefuelAll", "RefuelPartial"):
            # Refuel events report the amount purchased rather than a reliable
            # post-transaction main-tank level. Force an immediate Status.json
            # read and use the known full capacity for RefuelAll in the interim.
            if ev == "RefuelAll" and self.fuel_capacity_main:
                self.current_fuel_main = float(self.fuel_capacity_main)
            self.watcher.force_check_status()
            if not self.batch_mode:
                self.update_hud()

        elif ev == "ScanOrganic":
            # A live ScanOrganic event can only come from the commander's
            # present location and therefore repairs a stale cached address.
            # Startup history still needs the address guard because its bounded
            # replay may contain organisms from the previous system.
            if startup_replay and not self._matches_current_system_address(d):
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
            # Startup replay owns no immediate presentation, so reduce its
            # journal sequence first. This supplies an exact 1/3, 2/3 or 3/3
            # index even when the replay tail begins on Sample and the cached
            # body record already contains the final pre-restart step.
            if startup_replay:
                self._process_companion_event(
                    ev, raw if isinstance(raw, dict) else {}, d,
                    startup_replay=True,
                )
            # Live ScanOrganic events carry no Sample/IsNewSample field, so sample
            # progress has to be tracked locally from ScanType position (Log=1,
            # Sample=2, Sample=3, then Analyse completes without adding a sample).
            scan_type_norm = str(d.get("scan_type") or "").strip().casefold()
            max_samples = d.get("max_samples", 3)
            is_complete = bool(d.get("is_complete")) or scan_type_norm == "analyse"
            was_complete = bool(existing.get("is_complete"))
            is_new_sample = scan_type_norm in ("log", "sample")
            if scan_type_norm == "analyse":
                self._survey_body_focus_suppressed = True
            elif is_new_sample:
                self._survey_body_focus_suppressed = False
            if scan_type_norm == "log":
                # Log is always the first sample. Incrementing an existing
                # cached Log made a single journal event appear as 2/3.
                sample_idx = 1
            elif scan_type_norm == "sample" and startup_replay:
                replay_sample = getattr(self, "_startup_bio_sampling_replay", None) or {}
                same_replay = bool(
                    replay_sample.get("species") == species
                    and self._normalize_body_id(replay_sample.get("body")) == body_id
                )
                sample_idx = (
                    int(replay_sample.get("progress") or 2)
                    if same_replay else 2
                )
            elif is_new_sample:
                sample_idx = int(existing.get("sample_idx") or 0) + 1
            else:
                sample_idx = existing.get("sample_idx") or max_samples

            # Cached organic records are the final state of journal events we
            # may now be replaying.  Never let an earlier Log/Sample downgrade
            # a completed record, otherwise its later Analyse would count the
            # same organism a second time during startup catch-up.
            if startup_replay and was_complete:
                is_complete = True
                sample_idx = max(
                    int(existing.get("sample_idx") or 0),
                    int(max_samples or 3),
                )

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
                self._persist_bio_scan_record(
                    body_id, body_label, species_key,
                    self.last_bio_scan[species_key],
                )

            # Persist first, then publish sampler progress.  Log/Sample keeps
            # the three-node flightpath visible; Analyse clears it only after
            # organic_complete_count can move the overlay back to system mode.
            if not startup_replay:
                self._process_companion_event(
                    ev, raw if isinstance(raw, dict) else {}, d,
                    startup_replay=False,
                )
                self._handle_live_journal_toast(
                    ev, raw if isinstance(raw, dict) else {}, d,
                    startup_replay=False,
                )

            if not self.batch_mode:
                self.update_hud()
                self.schedule_dashboard_refresh()
                self._refresh_exploration_window()
                self._refresh_system_info_progress()

        elif ev in ("Location", "FSDJump", "StartJump") or carrier_jump_player_location:
            # Do not update HUDs during jump charge; wait for arrival.
            if ev == "StartJump":
                jump_type = d.get("jump_type") or (raw.get("JumpType") if isinstance(raw, dict) else "")
                jump_type = str(jump_type or "").lower()
                if jump_type != "supercruise":
                    if not startup_replay:
                        self._record_departure_revisit(raw.get("timestamp"))
                    self._save_exploration_checkpoint("departure")
                    self._hide_survey_status_for_jump()
                self.in_fss = False
                self.fss_summary_active = False
                # StartJump is the countdown for both low and high wake. Keep
                # the verified physical state underneath the charge cue until
                # Status' fsdJump bit or SupercruiseEntry confirms movement.
                self._sync_navigation_hud_flight_state(
                    supercruise=bool(
                        int(getattr(self, "current_status_flags", 0) or 0)
                        & self._STATUS_SUPERCRUISE
                    ),
                )
                self.update_hud()
                return

            # CarrierJump counts as a jump for the player while ship-docked or
            # walking on the carrier concourse.
            is_jump = ev in ("FSDJump", "CarrierJump")

            # A login while already docked normally emits Location, not a new
            # Docked event. Apply its state immediately so a profile switch
            # cannot retain the outgoing commander's HUD label or station.
            if ev == "Location":
                self._apply_location_navigation_state(raw, d)
                self._capture_navigation_local_space(raw, d)
                if self.station_info_hud and not self.batch_mode and not startup_replay:
                    self.station_info_hud.reconcile(self, present=True)

            # Reset FSS state on jump completion
            if is_jump:
                self._clear_navigation_local_space()
                self.in_fss = False
                self.fss_summary_active = False
                if ev == "CarrierJump":
                    self.current_docked = carrier_jump_docked
                    self.current_on_foot = carrier_jump_on_foot
                    self.current_in_taxi = False
                    self.current_in_multicrew = False
                    self.current_in_fighter = False
                    self.current_in_srv = False
                    self._sync_navigation_hud_flight_state(supercruise=False)
                else:
                    in_taxi, in_multicrew = self._navigation_passenger_flags(raw, d)
                    self.current_docked = False
                    self.current_on_foot = False
                    self.current_landed = False
                    self.current_in_taxi = in_taxi
                    self.current_in_multicrew = in_multicrew
                    self.current_in_fighter = False
                    self.current_in_srv = False
                    # A completed inter-system FSD jump arrives in
                    # supercruise. Taxi/multicrew ownership remains more
                    # specific than that transport's flight regime.
                    self._sync_navigation_hud_flight_state(supercruise=True)

            prev_coords = self.current_coords if isinstance(self.current_coords, list) else None

            # State reset for new system
            incoming_sys = d.get("star_system", "Unknown")
            previous_current_sys = self.current_sys
            preserve_unconfirmed_total = _preserve_unconfirmed_scan_total(
                startup_replay, data, incoming_sys, self.current_sys,
                getattr(self, "scan_total_confirmed", False),
                cached_loaded=getattr(self, "_cached_cockpit_state_loaded", False),
                cached_system=getattr(self, "_cached_cockpit_state_system", None),
                cached_confirmed=getattr(self, "_cached_scan_total_confirmed", False),
            )
            outgoing_sys = self.current_sys if self.current_sys not in ("---", "Unknown", incoming_sys) else None
            traffic_before_reset = dict(self.system_traffic or {})
            preserve_startup_traffic = (
                startup_replay
                and incoming_sys == self.last_traffic_system
                and traffic_before_reset
            )
            self.current_sys = incoming_sys
            if (is_jump
                    or self._navigation_system_arrival_epoch is None
                    or previous_current_sys in (None, "", "---", "Unknown")
                    or incoming_sys != previous_current_sys):
                event_timestamp = raw.get("timestamp") if isinstance(raw, dict) else None
                self._navigation_system_arrival_epoch = _journal_epoch(
                    event_timestamp, time.time(),
                )
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
            elif ev == "CarrierJump":
                # CarrierJump identifies the new system but omits StarClass;
                # never carry the departed system's primary-star class forward.
                self.star_class = ""

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
                except Exception:
                    pass
            
            # Load from history if available.  During startup, preserve an
            # explicitly unconfirmed cached total until a honk/completion
            # event in the replay supplies authoritative evidence.
            self.scan_total_confirmed = False
            self.load_system_from_db(
                self.current_sys,
                preserve_total_confirmation=preserve_unconfirmed_total,
            )

            self.organic_count = 0 # Reset bio count for new system
            self.system_bio_signals = 0
            self.belt_clusters = []
            self.last_scan_event = None
            self.last_bio_scan = {}
            self._stale_bio_warned = set()
            self.system_stars.clear()
            self.body_scan_data.clear()
            self.current_body_id   = None
            self.current_body_name = ""
            self._survey_body_focus_suppressed = False
            self.current_glide_mode = False
            self._surface_departure_active = False
            self._surface_glide_guard_until = 0.0
            self._surface_climb_samples = 0
            self._surface_descent_samples = 0
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
            self._promote_navigation_arrival_personality(
                ev, startup_replay=startup_replay,
            )

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
                self._ui_post(lambda value=sys_text: self.sys_stat.config(text=value), key="system-label")
                self.update_nav_label()
            # Bio logs hidden for now (counting disabled)
                scan_text = self._scan_progress_count_text()
                self._ui_post(lambda value=scan_text: self.scan_stat.config(text=value), key="scan-progress-label")
                self._ui_post(self.update_waypoint_display, key="waypoint-display")
                self.schedule_dashboard_refresh(full=True)
                self.update_hud()
                self.update_scan_hud()

            # Update Route Plotter UI if open
            if (not startup_replay and self.route_plotter
                    and self.route_plotter.win.winfo_exists()):
                s_sys = self.current_sys
                s_coords = self.current_coords
                self._ui_post(
                    lambda: self.route_plotter.update_current_system(s_sys, s_coords),
                    key="route-current-system",
                )

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
                _done = self.scanned
                _known = self.scan_total_confirmed
                self._ui_post(
                    lambda: self.system_info_hud.on_system_arrival(
                        _sys, _sc, _si, _bs, _tot,
                        scanned_bodies=_done, total_known=_known),
                    key="system-info-arrival",
                )
            if self.survey_status_hud:
                if self.current_docked:
                    self.survey_status_hud.suppress()
                else:
                    # The following update carries the arrived system, so do
                    # not briefly repaint the cached system we just departed.
                    self.survey_status_hud.resume(refresh=False)
                if not startup_replay:
                    self._ui_post(
                        lambda: self.survey_status_hud.update(
                            self.current_sys, self.scanned, self.total, self.scan_items,
                            self.body_signals, sampling=self._sampling_snapshot(),
                            focused_body_id=(None if self._survey_body_focus_suppressed
                                             and not self.bio_sampling else self.current_body_id),
                            focused_body_name=(None if self._survey_body_focus_suppressed
                                               and not self.bio_sampling else self.current_body_name),
                            total_known=self.scan_total_confirmed,
                            belt_clusters=list(self.belt_clusters)),
                        key="survey-status",
                    )
            self._refresh_exploration_window()

        elif ev == "Docked":
            station = d.get("StationName") or d.get("station_name", "Unknown")
            stype = d.get("StationType") or d.get("station_type", "")
            self.current_docked = True
            self.current_on_foot = False
            self.current_in_taxi = False
            self.current_in_multicrew = False
            self.current_in_fighter = False
            self.current_in_srv = False
            self._clear_navigation_local_space()
            self.hud_flight_state = "DOCKED"
            self.current_station_name = station
            self.current_station_type = stype or None
            self.current_station_market_id = d.get("MarketID") or d.get("market_id")
            self.current_station_state = d.get("StationState")
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
            if self.survey_status_hud:
                self.survey_status_hud.suppress()
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
            self.current_in_taxi = False
            self.current_in_multicrew = False
            self.current_in_fighter = False
            self.current_in_srv = False
            self.hud_flight_state = "FLIGHT"
            self.current_station_name = None
            self.current_station_type = None
            self.current_station_market_id = None
            self.current_station_state = None
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
            if self.survey_status_hud:
                self.survey_status_hud.resume()
                self._refresh_system_info_progress()
            if not self.batch_mode and not startup_replay:
                self.add_event_feed_entry("DOCK", f"Undocked: {station}", severity="INFO", copy_text=station)

        elif ev == "SupercruiseEntry":
            in_taxi, in_multicrew = self._navigation_passenger_flags(raw, d)
            self.current_docked = False
            self.current_on_foot = False
            self.current_landed = False
            self.current_in_taxi = in_taxi
            self.current_in_multicrew = in_multicrew
            self.current_in_fighter = False
            self.current_in_srv = False
            self._clear_navigation_local_space()
            self._sync_navigation_hud_flight_state(supercruise=True)
            # When a body is still tracked, entering supercruise is an
            # outbound orbital transition. Keep the Liftoff direction latched
            # until LeaveBody clears it instead of reverting to APPROACH.
            if getattr(self, "current_body_id", None) is not None:
                self._surface_departure_active = True
            self.update_hud()

        elif ev == "SupercruiseExit":
            in_taxi, in_multicrew = self._navigation_passenger_flags(raw, d)
            self.current_in_taxi = in_taxi
            self.current_in_multicrew = in_multicrew
            self.current_in_fighter = False
            self.current_in_srv = False
            self.current_on_foot = False
            self._capture_navigation_local_space(raw, d)
            self._sync_navigation_hud_flight_state(supercruise=False)
            self.update_hud()

        elif ev == "VehicleSwitch":
            self._apply_vehicle_switch(raw.get("To") or d.get("To"))

        elif ev == "JoinACrew":
            self.current_in_multicrew = True
            self.current_in_taxi = False
            self.current_on_foot = False
            self.current_in_fighter = False
            self.current_in_srv = False
            self.current_vehicle_id = None
            self.current_vehicle_name = ""
            self._sync_navigation_hud_flight_state(supercruise=False)
            self.update_hud()

        elif ev in ("QuitACrew", "EndCrewSession"):
            self.current_in_multicrew = False
            self.current_in_taxi = False
            self.current_in_fighter = False
            self.current_in_srv = False
            self.current_vehicle_id = None
            self.current_vehicle_name = ""
            self._sync_navigation_hud_flight_state(supercruise=False)
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
            self.current_in_taxi = False
            self.current_in_multicrew = False
            self.hud_flight_state = "ONFOOT"
            self._surface_departure_active = False
            self.update_hud()

        elif ev == "Embark":
            vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
            from_srv = bool(d.get("SRV") or (raw.get("SRV") if isinstance(raw, dict) else False))
            in_taxi, in_multicrew = self._navigation_passenger_flags(raw, d)
            self.current_on_foot = False
            self.current_in_taxi = in_taxi
            self.current_in_multicrew = in_multicrew
            if from_srv:
                self.current_in_taxi = False
                self.current_in_multicrew = False
                remembered_vehicle = self._vehicle_name_by_id.get(vehicle_id) if vehicle_id is not None else ""
                self.current_vehicle_id = vehicle_id
                self.current_vehicle_name = remembered_vehicle or self.current_vehicle_name or self._last_surface_vehicle_name or "SRV"
                self.current_in_srv = True
                self.current_in_fighter = False
                self.hud_flight_state = "NOMAD" if self.current_vehicle_name == "NOMAD" else "SRV"
            elif in_taxi or in_multicrew:
                self.current_vehicle_id = None
                self.current_vehicle_name = ""
                self.current_in_srv = False
                self.current_in_fighter = False
                self._sync_navigation_hud_flight_state(supercruise=False)
            elif self.current_docked:
                self.current_vehicle_id = None
                self.current_vehicle_name = ""
                self.current_in_srv = False
                self.current_in_fighter = False
                self.hud_flight_state = "DOCKED"
            elif self.current_landed:
                self.current_vehicle_id = None
                self.current_vehicle_name = ""
                self.current_in_srv = False
                self.current_in_fighter = False
                self.hud_flight_state = "LANDED"
            else:
                self.current_vehicle_id = None
                self.current_vehicle_name = ""
                self.current_in_srv = False
                self.current_in_fighter = False
                self.hud_flight_state = "FLIGHT"
            self._surface_departure_active = False
            self.update_hud()

        elif ev == "LaunchFighter":
            player_controlled = d.get("PlayerControlled")
            if player_controlled is None and isinstance(raw, dict):
                player_controlled = raw.get("PlayerControlled")
            if player_controlled is not False:
                self.current_in_fighter = True
                self.current_in_srv = False
                self.current_on_foot = False
                self.current_in_taxi = False
                vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
                loadout = d.get("Loadout") or (raw.get("Loadout") if isinstance(raw, dict) else "")
                loadout = str(loadout or "").lower()
                self.current_vehicle_name = "NOMAD" if loadout == "galactic" else "FIGHTER"
                self.current_vehicle_id = vehicle_id
                if vehicle_id is not None:
                    self._vehicle_name_by_id[vehicle_id] = self.current_vehicle_name
                self._last_surface_vehicle_name = self.current_vehicle_name
                self.hud_flight_state = self.current_vehicle_name
                # Elite exposes the Nomad as LaunchFighter/Loadout=galactic.
                # Both it and a commander-controlled SLF launch are vehicle
                # hand-offs, not evidence of mothership approach/departure.
                self._surface_departure_active = False
            self.update_hud()

        elif ev == "LaunchSRV":
            self.current_in_fighter = False
            self.current_in_srv = True
            self.current_on_foot = False
            self.current_in_taxi = False
            self.current_in_multicrew = False
            vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
            vehicle_name = self._srv_toast_vehicle_name(raw, d)
            self.current_vehicle_id = vehicle_id
            self.current_vehicle_name = vehicle_name
            if vehicle_id is not None:
                self._vehicle_name_by_id[vehicle_id] = vehicle_name
            self._last_surface_vehicle_name = vehicle_name
            self.hud_flight_state = vehicle_name
            self._surface_departure_active = False
            self.update_hud()

        elif ev in ("DockFighter", "FighterDestroyed"):
            self.current_in_fighter = False
            self.current_in_srv = False
            self.current_vehicle_id = None
            self.current_vehicle_name = ""
            self.current_in_taxi = False
            self._sync_navigation_hud_flight_state(supercruise=False)
            self._surface_departure_active = False
            self.update_hud()

        elif ev == "DockSRV":
            departure_active = bool(getattr(self, "_surface_departure_active", False))
            vehicle_id = d.get("ID") or (raw.get("ID") if isinstance(raw, dict) else None)
            vehicle_name = self._srv_toast_vehicle_name(raw, d)
            if vehicle_id is not None:
                self._vehicle_name_by_id[vehicle_id] = vehicle_name
            self.current_vehicle_name = ""
            self.current_in_fighter = False
            self.current_in_srv = False
            self.current_on_foot = False
            self.current_in_taxi = False
            self.current_in_multicrew = False
            self.current_vehicle_id = None
            self.hud_flight_state = "LANDED" if self.current_landed else "FLIGHT"
            # The Nomad reports its own Liftoff before docking back into the
            # mothership. Preserve that verified ascent until LeaveBody rather
            # than reverting to SURFACE APPROACH during the boarding gap.
            self._surface_departure_active = bool(
                departure_active
                and getattr(self, "current_body_id", None) is not None
                and not self.current_landed
            )
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
                self.scan_total_confirmed = True
                self._queue_edsm_upload(raw, startup_replay=startup_replay)
            progress = d.get("progress", raw.get("Progress") if isinstance(raw, dict) else None)
            try:
                progress = float(progress) if progress is not None else None
            except (TypeError, ValueError):
                progress = None
            if progress is not None and progress < 1.0:
                self.fss_all_bodies = False
            if progress is not None:
                self._record_navigation_fss_progress(progress)
            else:
                self._seed_navigation_scan_progress()
            if progress is not None and progress >= 1.0 and self.total > 0:
                # Frontier defines Progress as system-scan completion.  This
                # also covers pre-populated systems that may not replay each
                # individual Scan event on a return visit.
                self.fss_all_bodies = True
                self._mark_system_scan_complete(self.total)
            else:
                self.db_update_system(self.current_sys, self.total, self.scanned)
                if not self.batch_mode:
                    scan_text = self._scan_progress_count_text()
                    self._ui_post(lambda value=scan_text: self.scan_stat.config(text=value), key="scan-progress-label")
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
                    scan_text = self._scan_progress_count_text()
                    self._ui_post(lambda value=scan_text: self.scan_stat.config(text=value), key="scan-progress-label")
                    self.update_hud()
                    self.schedule_dashboard_refresh()
                    self._refresh_system_info_progress()

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
                self._set_body_signals(
                    body_id, bio_count, geo_count,
                    body_name=d.get("body_name"),
                )
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
                if not self.batch_mode:
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
                        body_name=d.get("body_name"), dss_complete=True,
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
                if not self.batch_mode:
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

            # Belt clusters are celestial Scan journal events and belong in
            # EDSM. Keep them outside VoidCompass's star/planet survey count,
            # and continue filtering mining ProspectedAsteroid events.
            if (
                not d.get("is_body_scan")
                and isinstance(body_name, str)
                and "belt cluster" in body_name.casefold()
            ):
                belt_changed = self._record_belt_cluster(
                    body_id, body_name,
                    distance_ls=d.get("distance_from_arrival_ls"),
                    was_discovered=d.get("was_discovered"),
                )
                self._queue_edsm_upload(raw, startup_replay=startup_replay)
                if belt_changed and not self.batch_mode:
                    self._refresh_system_info_progress()

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
                        scan_text = self._scan_progress_count_text()
                        self._ui_post(lambda value=scan_text: self.scan_stat.config(text=value), key="scan-progress-label")
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
                        self._set_body_signals(
                            body_id, d.get("bio_signals_count", 0),
                            self.body_signals.get(body_id, {}).get("geo", 0),
                            body_name=body_name,
                        )

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
        if ev == "ApproachBody":
            self.current_body_id   = self._normalize_body_id(d.get("body_id"))
            self.current_body_name = d.get("body_name") or ""
            self._survey_body_focus_suppressed = False
            self._surface_departure_active = False
            self._surface_glide_guard_until = 0.0
            self._surface_climb_samples = 0
            self._surface_descent_samples = 0
            if not self.batch_mode:
                self._refresh_gravity_warning(self.current_body_id, self.current_body_name)
                self._refresh_system_info_progress()
                self.update_hud()
        elif ev == "LeaveBody":
            if not self.batch_mode:
                self._check_stale_bio_scans(self.current_body_id)
            self.current_body_id   = None
            self.current_body_name = ""
            self.current_glide_mode = False
            self._surface_departure_active = False
            self._surface_glide_guard_until = 0.0
            self._surface_climb_samples = 0
            self._surface_descent_samples = 0
            if not self.batch_mode:
                if self.gravity_warning_hud:
                    self.gravity_warning_hud.clear()
                self._refresh_system_info_progress()
                self.update_hud()
        elif ev == "Liftoff":
            body_id = self._normalize_body_id(d.get("body_id"))
            body_name = (
                d.get("body_name") or d.get("body")
                or (raw.get("Body") if isinstance(raw, dict) else "") or ""
            )
            if body_id is not None:
                self.current_body_id = body_id
            if body_name:
                self.current_body_name = body_name
            self.current_landed = False
            player_controlled = d.get("player_controlled")
            if player_controlled is None and isinstance(raw, dict):
                player_controlled = raw.get("PlayerControlled")
            vehicle_active = bool(
                getattr(self, "current_in_srv", False)
                or getattr(self, "current_in_fighter", False)
                or getattr(self, "current_on_foot", False)
                or getattr(self, "current_in_taxi", False)
                or getattr(self, "current_in_multicrew", False)
            )
            if vehicle_active:
                # The mothership may launch/recall while its commander remains
                # in an SRV, Nomad, fighter or on foot. Keep that vehicle as
                # the indicator owner. A player-controlled Nomad Liftoff is a
                # genuine commander ascent, however, so retain its direction
                # for the later DockSRV hand-off into the mothership.
                self._surface_departure_active = bool(
                    player_controlled is True
                    and getattr(self, "current_body_id", None) is not None
                )
                self._sync_navigation_hud_flight_state(supercruise=False)
            elif player_controlled is False:
                # An empty recalled/dismissed ship must not take ownership of
                # the commander's active indicator when Status is late.
                self._surface_departure_active = False
            else:
                self.hud_flight_state = "FLIGHT"
                self._surface_departure_active = True
            if not self.batch_mode:
                self.update_hud()
        elif ev == "Touchdown":
            body_id = self._normalize_body_id(d.get("body_id"))
            body_name = (
                d.get("body_name") or d.get("body")
                or (raw.get("Body") if isinstance(raw, dict) else "") or ""
            )
            if body_id is not None:
                self.current_body_id = body_id
            if body_name:
                self.current_body_name = body_name
            self.current_landed = True
            self._surface_departure_active = False
            self._surface_glide_guard_until = 0.0
            self._surface_climb_samples = 0
            self._surface_descent_samples = 0
            player_controlled = d.get("player_controlled")
            if player_controlled is None and isinstance(raw, dict):
                player_controlled = raw.get("PlayerControlled")
            # Touchdown can describe the recalled mothership while the
            # commander remains outside it, so vehicle state retains priority.
            if player_controlled is not False or any((
                    getattr(self, "current_in_srv", False),
                    getattr(self, "current_in_fighter", False),
                    getattr(self, "current_on_foot", False),
                    getattr(self, "current_in_taxi", False),
                    getattr(self, "current_in_multicrew", False),
            )):
                self._sync_navigation_hud_flight_state(supercruise=False)
            if not self.batch_mode:
                self.update_hud()

        # ── Prospector overlay — live events only, skip journal replay on startup ──
        # Use startup_replay (not batch_mode) so rapid-fire limpets that land in
        # the same poll cycle still update the overlay.  batch_mode is True for
        # any multi-event poll, not just startup, which was silently dropping updates.
        if self.prospector_hud and not startup_replay:
            if ev == "ProspectedAsteroid":
                self._ui_post(lambda r=raw: self.prospector_hud.update(r), key="prospector-hud")
            elif ev == "MiningRefined":
                mat = raw.get("Type_Localised") or raw.get("Type") or ""
                self._ui_post(lambda m=mat: self.prospector_hud.add_refined(m))

        self._update_exploration_intelligence(
            ev, raw if isinstance(raw, dict) else d,
            startup_replay=startup_replay,
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
                station = getattr(self, "station_info_hud", None)
                if station and self.current_docked and self.current_station_name:
                    station.refresh(self)
            except Exception:
                pass
        try:
            self._companion_refresh_job = self.root.after(200, run)
        except Exception:
            self._companion_refresh_job = None

    def _toast_on_main(self, title, message, severity="info", duration=12,
                       voice_text=None, voice_category="safety", voice_key=None):
        if self.toast_hud:
            self._ui_post(lambda: self.toast_hud.push(
                title, message, severity=severity, duration_s=duration,
            ))

    def _clear_sold_data_warnings(self, biological=False):
        """Cancel risk output that became obsolete during a data sale."""
        toast = getattr(self, "toast_hud", None)
        if toast and hasattr(toast, "dismiss"):
            try:
                self._ui_post(
                    lambda target=toast: target.dismiss(title="DATA AT RISK"),
                    key="dismiss-data-risk-toast",
                )
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
            if (int(state.get("unsold_exploration_cr") or 0)
                    or int(state.get("unsold_bio_cr") or 0)):
                state["exploration_data_lost_at"] = raw.get("timestamp")
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

        if startup_replay:
            self._reduce_startup_sampling_event(ev, raw, data)
        else:
            if ev == "Scan":
                changed = self._record_unsold_scan(raw) or changed
            elif ev == "ScanOrganic":
                changed = self._process_sampling_event(raw, data) or changed
                if getattr(self, "cockpit_memory", None):
                    self.cockpit_memory.check_bio_sell_anticipation(state.get("unsold_bio_samples"))
            elif ev in ("SellExplorationData", "MultiSellExplorationData"):
                state["last_exploration_sale"] = {
                    "timestamp": raw.get("timestamp"),
                    "value": int(raw.get("TotalEarnings") or raw.get("TotalSale") or 0),
                    "system": getattr(self, "current_sys", ""),
                    "station": getattr(self, "current_station_name", ""),
                }
                state["unsold_exploration_cr"] = 0
                state["unsold_scan_keys"] = []
                self._data_risk_level = 0
                self._clear_sold_data_warnings()
                changed = True
            elif ev == "SellOrganicData":
                sold_count = int(state.get("unsold_bio_samples") or 0)
                sold_value = int(raw.get("TotalEarnings") or 0)
                if not sold_value:
                    sold_value = sum(
                        int(row.get("Value") or 0) + int(row.get("Bonus") or 0)
                        for row in (raw.get("BioData") or []) if isinstance(row, dict)
                    )
                state["last_bio_sale"] = {
                    "timestamp": raw.get("timestamp"), "value": sold_value,
                    "system": getattr(self, "current_sys", ""),
                    "station": getattr(self, "current_station_name", ""),
                }
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

    def _reduce_startup_sampling_event(self, event, raw, data):
        """Recover the active genetic-sampler step from journal catch-up.

        Startup replay must rebuild presentation state without replaying sale
        value, unsold-data counters, notifications or sample-clearance toasts.
        Elite records the complete Log → Sample → Sample → Analyse sequence,
        so the most recent unfinished sequence is authoritative after a crash.
        """
        event = str(event or "")
        raw = raw if isinstance(raw, dict) else {}
        data = data if isinstance(data, dict) else {}
        jump_type = str(data.get("jump_type") or raw.get("JumpType") or "").casefold()
        clears_sampling = (
            event in {"FSDJump", "CarrierJump", "LeaveBody", "Died"}
            or (event == "StartJump" and jump_type == "hyperspace")
        )
        if clears_sampling:
            self._startup_bio_sampling_replay = None
            self._startup_bio_sampling_replay_seen = True
            return
        if event != "ScanOrganic":
            return

        self._startup_bio_sampling_replay_seen = True
        scan_type = str(
            raw.get("ScanType") or data.get("scan_type") or ""
        ).strip().casefold()
        if scan_type == "analyse" or data.get("is_complete"):
            self._startup_bio_sampling_replay = None
            return
        if scan_type not in {"log", "sample"}:
            return

        species = (
            data.get("species") or raw.get("Species_Localised")
            or raw.get("Species") or "Organic"
        )
        genus = (
            data.get("genus") or raw.get("Genus_Localised")
            or raw.get("Genus") or str(species).split(" ")[0]
        )
        body = data.get("body_id")
        if body is None:
            body = raw.get("Body")
        body = self._normalize_body_id(body)
        system_address = data.get("system_address")
        if system_address is None:
            system_address = raw.get("SystemAddress")

        previous = self._startup_bio_sampling_replay or {}
        same_sequence = bool(
            previous
            and previous.get("species") == species
            and self._normalize_body_id(previous.get("body")) == body
            and str(previous.get("system_address") or "") == str(system_address or "")
        )
        if scan_type == "log":
            progress = 1
        elif same_sequence:
            progress = int(previous.get("progress") or 1) + 1
        else:
            # A replay window beginning on Sample has necessarily omitted Log;
            # Sample can never be the first genetic-sampler step.
            progress = 2
        progress = max(1, min(3, progress))
        self._startup_bio_sampling_replay = {
            "species": species,
            "genus": genus,
            "body": body,
            "progress": progress,
            "colony_m": bio_values.GENUS_COLONY_M.get(genus),
            "system_address": system_address,
            "timestamp": raw.get("timestamp"),
        }

    def _recover_active_sampling_from_journal(self):
        """Rebuild the sampler card when the cockpit snapshot omitted it."""
        watcher = getattr(self, "watcher", None)
        getter = getattr(watcher, "get_active_organic_sampling", None)
        if not callable(getter):
            return None
        try:
            recovered = getter(self.current_system_address, self.current_body_id)
        except Exception as exc:
            logging.warning("Startup active biology recovery failed: %s", exc)
            return None
        if not isinstance(recovered, dict):
            return None
        raw = recovered.get("raw")
        if not isinstance(raw, dict):
            return None
        try:
            normalized = watcher._normalize_event(raw)
            data = self._enrich_bio_event_context(normalized.get("data") or {})
        except Exception as exc:
            logging.warning("Startup active biology normalization failed: %s", exc)
            return None
        body = self._normalize_body_id(data.get("body_id"))
        address = data.get("system_address")
        if body is None or not self._matches_current_system_address(data):
            return None
        species = (
            data.get("species") or raw.get("Species_Localised")
            or raw.get("Species") or "Organic"
        )
        genus = (
            data.get("genus") or raw.get("Genus_Localised")
            or raw.get("Genus") or str(species).split(" ")[0]
        )
        return {
            "species": species,
            "genus": genus,
            "body": body,
            "progress": max(1, min(3, int(recovered.get("progress") or 1))),
            "colony_m": bio_values.GENUS_COLONY_M.get(genus),
            "system_address": address,
            "timestamp": raw.get("timestamp"),
        }

    def _finalize_startup_sampling_replay(self):
        """Publish replayed sampling only when it still matches our location."""
        replay_seen = bool(getattr(self, "_startup_bio_sampling_replay_seen", False))
        candidate = getattr(self, "_startup_bio_sampling_replay", None)
        active_sampling = getattr(self, "bio_sampling", None)
        existing = active_sampling if isinstance(active_sampling, dict) else None
        preserved_points = list(getattr(self, "bio_sample_points", None) or [])

        if not replay_seen:
            # A clean shutdown marker can start catch-up after the original Log
            # even though its body record was persisted. Recover the unfinished
            # sequence from the active journal so the three-node card does not
            # silently disappear on relaunch.
            candidate = self._recover_active_sampling_from_journal()
            if not candidate:
                return bool(existing)

        if candidate:
            candidate = dict(candidate)
            body = self._normalize_body_id(candidate.get("body"))
            current_body = self._normalize_body_id(self.current_body_id)
            address = candidate.get("system_address")
            current_address = self.current_system_address
            if current_body is not None and body is not None and body != current_body:
                candidate = None
            elif (address is not None and current_address is not None
                  and str(address) != str(current_address)):
                candidate = None

        if candidate and existing:
            same_sample = bool(
                existing.get("species") == candidate.get("species")
                and self._normalize_body_id(existing.get("body"))
                == self._normalize_body_id(candidate.get("body"))
            )
            if same_sample:
                candidate["progress"] = max(
                    int(candidate.get("progress") or 1),
                    int(existing.get("progress") or 1),
                )
            else:
                preserved_points = []
        elif not candidate:
            preserved_points = []

        self.bio_sampling = candidate
        self.bio_sample_points = preserved_points
        self._sample_clear_announced = False
        self._startup_bio_sampling_replay = None
        self._startup_bio_sampling_replay_seen = False
        return bool(candidate)

    def _process_sampling_event(self, raw, data):
        scan_type = str(raw.get("ScanType") or data.get("scan_type") or "").lower()
        species = data.get("species") or raw.get("Species_Localised") or raw.get("Species") or "Organic"
        genus = data.get("genus") or raw.get("Genus_Localised") or raw.get("Genus") or species.split(" ")[0]
        body = data.get("body_id") if data.get("body_id") is not None else raw.get("Body")
        point = None
        if self.current_latitude is not None and self.current_longitude is not None:
            point = {"lat": self.current_latitude, "lon": self.current_longitude, "body": body}
        if scan_type in ("log", "sample"):
            same_sample = bool(
                self.bio_sampling
                and self.bio_sampling.get("species") == species
                and self.bio_sampling.get("body") == body
            )
            if not same_sample:
                self.bio_sample_points = []
            if point:
                self.bio_sample_points.append(point)
            if scan_type == "log":
                progress = 1
            else:
                progress = int(self.bio_sampling.get("progress") or 0) + 1 if same_sample else 0
                body_key = self._normalize_body_id(body)
                species_key = f"{body_key}|{species}" if body_key is not None else species
                prior = self.last_bio_scan.get(species_key, {})
                # ``last_bio_scan`` has already reduced this same live event,
                # so its sample index is the current step—not the previous one.
                progress = max(progress, int(prior.get("sample_idx") or 0))
                progress = max(1, min(3, progress))
            self.bio_sampling = {
                "species": species, "genus": genus, "body": body,
                "progress": progress,
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
            self._ui_post(lambda s=sample: self.survey_status_hud.update(
                self.current_sys, self.scanned, self.total, self.scan_items, self.body_signals, sampling=s,
                focused_body_id=(None if self._survey_body_focus_suppressed
                                 and not s else self.current_body_id),
                focused_body_name=(None if self._survey_body_focus_suppressed
                                   and not s else self.current_body_name),
                total_known=self.scan_total_confirmed,
                belt_clusters=list(self.belt_clusters),
            ), key="survey-status")
        if getattr(self, "exploration_window", None) and self.exploration_window.is_open():
            self._ui_post(self.exploration_window._render_sampling, key="exploration-sampling")

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
            self._ui_post(self.engineer_window.refresh, key="engineer-refresh")

    def update_ship_locker(self, data):
        """Marshal ShipLocker.json updates from the watcher onto the Tk thread."""
        try:
            self._ui_post(
                self._apply_ship_locker, dict(data or {}), key="ship-locker",
            )
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
                quantity_badge = f" · {quantity} modules" if quantity > 1 else ""
                if self.toast_hud:
                    self._ui_post(lambda name=blueprint, target_grade=grade, qty_badge=quantity_badge: self.toast_hud.push(
                        "READY TO ENGINEER",
                        f"{name} G{target_grade} materials complete{qty_badge}",
                        severity="info",
                        duration_s=12,
                    ))

    def process_batch(self, events):
        startup_batch = any(
            bool(event.get("startup_catchup"))
            for event in events if isinstance(event, dict)
        )
        startup_final = any(
            bool(event.get("startup_catchup_final"))
            for event in events if isinstance(event, dict)
        )
        batch_event_types = {
            str(event.get("type") or event.get("event") or "")
            for event in events if isinstance(event, dict)
        }
        if startup_batch:
            self._startup_restore_active = True
            self._startup_restore_ui_pending = True
            self._startup_journal_events_loaded = int(
                getattr(self, "_startup_journal_events_loaded", 0) or 0
            ) + len(events)
            self._startup_boot_update(
                "RESTORING RECENT JOURNAL",
                f"Reduced {self._startup_journal_events_loaded:,} events toward the live tail",
                min(0.84, 0.72 + self._startup_journal_events_loaded / 10_000.0),
            )
        self._hud_event_batch_priority = None
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
            self._hud_event_batch_priority = None
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

        if startup_final:
            self._finalize_startup_sampling_replay()
            if self._restore_current_system_bio_completions():
                self._request_db_commit(reason="startup_biology_recovery")
            self._mark_startup_journal_live()

        # Docked/Location rendering is deliberately suppressed while a batch
        # is being reduced.  Reconcile once from the final state so Station
        # Link cannot remain withdrawn until its setting is toggled.  A carrier
        # jump refreshes an already-visible carrier card without reopening one
        # that auto-hide previously dismissed.
        station_transition = bool(
            batch_event_types.intersection({"Docked", "Undocked", "Location"})
        )
        station_refresh = station_transition or "CarrierJump" in batch_event_types
        startup_presentation = bool(startup_final or self.is_first_load)
        if self.station_info_hud and (startup_presentation or station_refresh):
            self.station_info_hud.reconcile(
                self,
                present=bool(startup_presentation or station_transition),
            )

        if startup_final or self.is_first_load:
            self._startup_restore_active = False
            self._startup_restore_ui_pending = False
            self._cached_cockpit_state_loaded = False
            self.dashboard_refresh_full_pending = False
            self.is_first_load = False
            self._startup_recovery_mode = False
            self._freeze_startup_heap()
            self._apply_adaptive_overlay_scene()
            self._adaptive_startup_mode()
            self._hold_startup_presentation()
            self._publish_expedition_resume_briefing()
            try:
                self._update_main_window_title()
            except Exception:
                pass
            # After startup batch: re-read DB so scan_stat always reflects the
            # committed authoritative values (fixes cases where in-memory state
            # diverged during batch processing).
            sys_snap = self.current_sys
            def _startup_sync():
                if sys_snap and sys_snap != "---":
                    preserve_unconfirmed = bool(
                        not getattr(self, "scan_total_confirmed", False)
                    )
                    self.load_system_from_db(
                        sys_snap,
                        preserve_total_confirmation=preserve_unconfirmed,
                    )
                self.update_dashboard_ui()
                self.update_hud()
                self._show_system_info_for_current_system()
                if self.current_sys and self.current_sys != "---":
                    self.last_traffic_system = self.current_sys
                    self.fetch_system_traffic(self.current_sys)
                self._startup_presentation_ready = True
                self._hold_startup_presentation()
                self._maybe_complete_startup_presentation()
            self._ui_post(_startup_sync, key="startup-ui-sync")
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
                    self._ui_post(
                        lambda w=copied_wp, l=log_label: self._copy_waypoint_to_clipboard(w, l),
                        key="startup-waypoint-copy",
                    )
        else:
            self._ui_post(self.update_dashboard_ui, key="dashboard-full-refresh")
            # Live journal polls commonly contain an FSDJump plus companion
            # events. Per-event HUD work is deliberately suppressed while the
            # batch is active, so publish the final combined state once here.
            # TacticalHUD's render fingerprint makes this a no-op when none of
            # the displayed navigation facts changed.
            self.update_hud()
        # Per-event scan-overlay redraws are suppressed while a batch is
        # active. Refresh once only when that batch actually changed survey
        # state; unrelated cargo, combat and status events must not churn the
        # persistent Survey Operations window.
        survey_changed = startup_final or any(
            (event.get("type") or event.get("event")) in self._SURVEY_REFRESH_EVENTS
            for event in events if isinstance(event, dict)
        )
        if survey_changed:
            self._refresh_system_info_progress()
        self._refresh_commander_profile_window()
        self._refresh_value_ledger_window()
        self._refresh_colonisation_planner_window()
        self._refresh_exploration_window()
        self._refresh_bgs_window()
        window = getattr(self, "specialists_window", None)
        if window and window.is_open() and getattr(self, "_active_page", None) == "SPECIALISTS":
            self._ui_post(window.refresh, key="specialists-refresh")

    def _refresh_cargo_consumers(self):
        """Publish inventory and hold capacity as one live ship snapshot."""
        if self.cargo_hud:
            cargo_hud = self.cargo_hud
            inventory = list(self.current_cargo_inventory)
            capacity = self.cargo_capacity
            self._ui_post(
                lambda hud=cargo_hud, inv=inventory, cap=capacity: hud.update(inv, cap),
                key="cargo-hud",
            )
        if self.colony_overlay:
            colony_overlay = self.colony_overlay
            self._ui_post(colony_overlay.update, key="colony-overlay")

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
        self._refresh_cargo_consumers()
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
        self.trade_session["events"].append(event)

    def _eddn_market_context(self, data):
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
            "commander_name": self.cmdr_name,
        }

    def update_market(self, data):
        if not isinstance(data, dict):
            return
        context = self._eddn_market_context(data)
        if not context.get("docked"):
            return
        eddn_market_uploader.set_enabled(
            bool(self.config.get("eddn_market_upload_enabled", True))
        )
        eddn_market_uploader.maybe_publish(
            dict(data), context.get("commander_name") or self.cmdr_name, context,
        )

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
            self._ui_post(self.route_plotter.update_navigation_state, key="route-navigation-state")
