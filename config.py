import os
import json
import re
from platform_support import application_dir, default_screenshot_path, detect_elite_journal_path


def _get_config_file():
    # Packaged Windows and Linux builds are portable and keep writable state
    # beside the executable. Source runs retain the existing working-directory
    # behaviour used by development and tests.
    return str(application_dir() / "config.json")


CONFIG_FILE = _get_config_file()
PROFILE_DIR = str(application_dir() / "profiles")
PROFILE_CONFIG_NAME = "config.json"
RETIRED_COMPASS_CONFIG_KEYS = (
    "voice_callouts_enabled",
    "voice_safety_enabled",
    "voice_exploration_enabled",
    "voice_navigation_enabled",
    "voice_objectives_enabled",
    "voice_cache_enabled",
    "voice_cache_auto_prune_enabled",
    "voice_cache_retention_days",
    "voice_name",
    "voice_volume",
    "cockpit_memory_enabled",
    "cockpit_ambient_chatter_enabled",
    "cockpit_session_greetings_enabled",
    "cockpit_memory_callbacks_enabled",
    "cockpit_advisor_enabled",
    "cockpit_advisor_level",
    "cockpit_cognition_enabled",
    "cockpit_cognition_learning_enabled",
    "cockpit_exploration_focus_enabled",
    "cockpit_personality_level",
    "cockpit_persona",
    "cockpit_memory_system_limit",
    "cockpit_memory_species_limit",
    "cockpit_memory_ship_limit",
    "cockpit_memory_episode_limit",
    "adaptive_briefings_enabled",
    "adaptive_debriefings_enabled",
)
DEPRECATED_CONFIG_KEYS = (
    'scan_overlay_enabled',
    'scan_hud_x',
    'scan_hud_y',
    'discord_webhook',
    'discord_enabled',
    'discord_live_enabled',
    'discord_fleet_enabled',
    'discord_msg_id',
    'discord_msg_system',
    'discord_fc_msg_id',
    'discord_fc_last_status_note',
    'discord_fc_last_state',
    'fc_watch_name',
    'fc_watch_status',
    'fc_watch_destination',
    'fc_watch_departure',
    'fc_watch_state',
    'fleet_carrier_watcher_geometry',
    'fc_discord_enabled',
    'fc_discord_webhook',
    'fc_discord_public_webhook',
    'fc_discord_user_id',
    'fc_discord_jump_plotted',
    'fc_discord_jump_plotted_ping',
    'fc_discord_jump_completed',
    'fc_discord_jump_completed_ping',
    'fc_discord_jump_cancelled',
    'fc_discord_jump_cancelled_ping',
    'fc_discord_cooldown_finished',
    'fc_discord_cooldown_finished_ping',
    'fc_notes',
    'bio_overlay_enabled',
    'bio_hud_x',
    'bio_hud_y',
    'cockpit_llm_enabled',
    'cockpit_llm_advisor_enabled',
    'cockpit_llm_auto_start',
    'cockpit_llm_unload_on_shutdown',
    'cockpit_llm_model',
    'cockpit_llm_inference_profile',
    'cockpit_llm_advisor_level',
    'cockpit_llm_timeout_s',
    'overlay_hotkey_trade',
    'trade_overlay_enabled',
    'trade_eddn_upload_enabled',
    'trade_log_auto_prune_enabled',
    'trade_hud_x',
    'trade_hud_y',
    'big_trade_profit_threshold',
    'trade_window_geometry',
    'trade_route_form',
    'trade_log_retention_days',
) + RETIRED_COMPASS_CONFIG_KEYS
# Overlay/HUD colors are seeded from the active theme at startup; the live
# theme bridge rebinds these module constants and repaints open overlays.
import themes as _themes

COLOR_BG = _themes.ACTIVE_PALETTE["bg"]
COLOR_PANEL = _themes.ACTIVE_PALETTE["panel"]
COLOR_ACCENT = _themes.ACTIVE_PALETTE["accent"]
COLOR_ORANGE = _themes.ACTIVE_PALETTE["orange"]
COLOR_TEXT = _themes.ACTIVE_PALETTE["text"]
COLOR_GREEN = _themes.ACTIVE_PALETTE["green"]
COLOR_MUTED = _themes.ACTIVE_PALETTE["muted"]
COLOR_YELLOW = _themes.ACTIVE_PALETTE["yellow"]


EXPLORATION_MINING_ACHIEVEMENT_CATEGORIES = {
    "Exploration", "Routes", "Exobiology", "Travel", "Places", "SRV",
    "Carrier", "Colonisation", "Mining",
}
NON_FOCUSED_ACHIEVEMENT_CATEGORIES = {
    "Combat", "Trading", "General", "Session", "Engineering", "Factions",
    "Odyssey", "Crime", "CQC", "Powerplay", "Ranks", "Passengers",
    "Operations", "Ships", "SLV", "Streamer",
}


PROFILE_TEXT_SETTINGS = (
    "edsm_cmdr_name",
    "edsm_api_key",
    "edsm_game_version",
    "edsm_game_build",
    "carrier_discord_webhook_url",
    "screenshots_path",
    "ui_theme_name",
    "hud_crt_intensity",
    "adaptive_mode_lock",
    "explore_active_page",
    "explore_survey_filter",
    "explore_discovery_filter",
    "explore_expedition_section",
    "explore_map_scope",
    "colony_overlay_sort_mode",
    "overlay_hotkey_layout_studio",
    "overlay_hotkey_toggle_all",
    "overlay_hotkey_navigation",
    "overlay_hotkey_navigation_layout",
    "overlay_hotkey_survey",
    "overlay_hotkey_system_info",
    "overlay_hotkey_station_info",
    "overlay_hotkey_cargo",
    "overlay_hotkey_carrier",
    "overlay_hotkey_prospector",
    "overlay_hotkey_colony",
    "overlay_hotkey_field_bookmark",
)

PROFILE_BOOL_SETTINGS = (
    "edsm_upload_enabled",
    "edsm_backfill_on_cache_rebuild",
    "eddn_market_upload_enabled",
    "overlay_enabled",
    "overlay_mouse_passthrough",
    "overlay_hotkeys_enabled",
    "dashboard_compact_mode",
    "hud_compact_mode",
    "cargo_overlay_enabled",
    "carrier_overlay_enabled",
    "colony_overlay_enabled",
    "colony_overlay_show_trips",
    "colony_overlay_site_only",
    "prospector_overlay_enabled",
    "system_info_enabled",
    "gravity_warning_overlay_enabled",
    "station_info_overlay_enabled",
    "station_info_auto_hide_enabled",
    "survey_status_overlay_enabled",
    "toast_overlay_enabled",
    "sample_clear_notifications_enabled",
    "rebuy_warnings_enabled",
    "data_risk_warnings_enabled",
    "heartbeat_overlay_enabled",
    "screenshots_enabled",
    "ground_popup_enabled",
    "ground_target_active",
    "auto_copy_waypoint",
    "route_auto_note_from_edsm",
    "achievements_enabled",
    "achievement_notifications_enabled",
    "hud_crt_enabled",
    "hud_crt_motion_enabled",
    "adaptive_command_enabled",
    "adaptive_overlay_scenes_enabled",
    "exploration_focus_enabled",
    "exploration_focus_migrated",
    "reduced_motion_enabled",
)

PROFILE_VALUE_SETTINGS = (
    "nav_collapsed_groups",
    "prospector_hud_timeout_s",
    "prospector_hud_x",
    "prospector_hud_y",
    "system_info_timeout_s",
    "system_info_hud_x",
    "system_info_hud_y",
    "hud_x",
    "hud_y",
    "cargo_hud_x",
    "cargo_hud_y",
    "carrier_hud_x",
    "carrier_hud_y",
    "colony_overlay_x",
    "colony_overlay_y",
    "colony_overlay_w",
    "colony_overlay_h",
    "colony_overlay_font_scale",
    "gravity_warning_hud_x",
    "gravity_warning_hud_y",
    "gravity_warning_hud_timeout_s",
    "gravity_warning_threshold_g",
    "station_info_hud_x",
    "station_info_hud_y",
    "station_info_timeout_s",
    "station_info_timeout_semantics_version",
    "survey_status_hud_x",
    "survey_status_hud_y",
    "toast_hud_x",
    "toast_hud_y",
    "heartbeat_hud_x",
    "heartbeat_hud_y",
    "low_fuel_threshold_pct",
    "ground_target_window_geometry",
    "ground_popup_geometry",
    "ground_target_lat",
    "ground_target_lon",
    "engineer_window_geometry",
    "bgs_window_geometry",
    "carrier_window_geometry",
    "colonisation_window_geometry",
    "mining_geometry",
    "route_plotter_geometry",
    "edit_dialog_geometry",
    "import_dialog_geometry",
    "profile_dashboard_geometry",
    "value_ledger_geometry",
    "colonisation_planner_geometry",
    "exploration_window_geometry",
    "system_plotter_form",
    "ui_custom_themes",
    "achievements_disabled_categories",
    "achievement_window_geometry",
    "adaptive_overlay_scenes",
    "ui_scale_percent",
    "overlay_text_scale_percent",
    "overlay_layout_presets",
    "overlay_layout_studio_geometry",
    "dashboard_compact_geometry",
    "dashboard_expanded_geometry",
    "dashboard_window_geometry_version",
    "explore_map_view_state",
    "explore_map_annotations",
    "explore_map_annotation_geometry",
)

PROFILE_SETTINGS = PROFILE_TEXT_SETTINGS + PROFILE_BOOL_SETTINGS + PROFILE_VALUE_SETTINGS
GLOBAL_ONLY_KEYS = (
    "journal_path",
    "main_geometry",
    "settings_geometry",
    "perf_spike_threshold_ms",
    "ui_watchdog_spike_ms",
    "ui_stall_sampler_enabled",
    "ui_stall_sample_ms",
    "db_commit_interval_ms",
    "screenshot_max_convert_per_cycle",
    "overlay_topmost_refresh_ms",
    "hud_anim_interval_ms",
    "hud_animation_cadence_version",
    "runtime_trace_enabled",
    "runtime_trace_path",
    "crash_reporting_enabled",
    "watcher_max_journal_lines_per_cycle",
    "watcher_startup_max_lines_per_cycle",
    "watcher_startup_tail_bytes",
    "watcher_special_file_settle_ms",
    "active_commander_profile",
    "active_commander_name",
    "active_commander_fid",
    "commander_profiles",
    "onboarding_complete",
    "recovery_safe_mode_enabled",
    "last_app_version",
)


def commander_profile_key(commander_name=None, fid=None):
    """Return a filesystem-safe stable profile key for a commander."""
    name = str(commander_name or "Unknown Commander").strip() or "Unknown Commander"
    fid_text = str(fid or "").strip()
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-").lower()
    if not base:
        base = "unknown_commander"
    if fid_text:
        fid_slug = re.sub(r"[^A-Za-z0-9._-]+", "_", fid_text).strip("._-").lower()
        if fid_slug:
            base = f"{base}_{fid_slug}"
    return base[:80]


def get_profile_dir(profile_key):
    key = commander_profile_key(profile_key or "Unknown Commander")
    path = os.path.abspath(os.path.join(PROFILE_DIR, key))
    os.makedirs(path, exist_ok=True)
    return path


def get_profile_file(profile_key, filename):
    return os.path.join(get_profile_dir(profile_key), filename)


def get_profile_config_file(profile_key):
    return get_profile_file(profile_key, PROFILE_CONFIG_NAME)


def get_active_profile(config):
    key = config.get("active_commander_profile") or commander_profile_key(
        config.get("active_commander_name") or "Unknown Commander",
        config.get("active_commander_fid"),
    )
    return key


def apply_profile_config(config, profile_key=None):
    """Overlay commander-specific settings onto the mutable runtime config."""
    key = profile_key or get_active_profile(config)
    profiles = config.setdefault("commander_profiles", {})
    profile = profiles.setdefault(key, {})
    profile_config_file = get_profile_config_file(key)
    profile_config_exists = os.path.exists(profile_config_file)
    if profile_config_exists:
        try:
            with open(profile_config_file, "r") as f:
                profile.update(json.load(f))
        except Exception:
            pass
    # Speech/persona settings were retired in v5.3.6. Memory and cached audio
    # files remain on disk for rollback, but their old switches are no longer
    # copied into the live profile or written back to configuration.
    for setting in RETIRED_COMPASS_CONFIG_KEYS:
        profile.pop(setting, None)
        config.pop(setting, None)
    # Trade Assist was retired, but its independent EDDN publisher remains.
    # Preserve each commander's previous upload preference under the clearer
    # integration-only setting name.
    if "eddn_market_upload_enabled" not in profile:
        profile["eddn_market_upload_enabled"] = bool(
            profile.get(
                "trade_eddn_upload_enabled",
                config.get("trade_eddn_upload_enabled", True),
            )
        )
    # v5.2.9.2 moved the three shipped shortcuts away from common game/GPU
    # bindings. Only migrate the exact retired defaults; commander-customised
    # assignments remain untouched.
    hotkey_default_migration = {
        "overlay_hotkey_layout_studio": ("Ctrl+Shift+L", "Ctrl+Alt+Shift+F10"),
        "overlay_hotkey_toggle_all": ("Ctrl+Shift+O", "Ctrl+Alt+Shift+F11"),
        "overlay_hotkey_field_bookmark": ("Ctrl+Shift+B", "Ctrl+Alt+Shift+F12"),
    }
    for setting, (retired, replacement) in hotkey_default_migration.items():
        for values in (profile, config):
            if str(values.get(setting) or "").casefold() == retired.casefold():
                values[setting] = replacement
    # v5.3.3.1 changed Station Link from a transient arrival card into docked
    # context. Migrate only the retired shipped 25-second default; commanders
    # can still select 25 (or any positive value) after this one-time step.
    try:
        station_timeout_semantics = int(
            profile.get("station_info_timeout_semantics_version") or 0
        )
    except (TypeError, ValueError):
        station_timeout_semantics = 0
    if station_timeout_semantics < 1:
        old_timeout = profile.get("station_info_timeout_s", config.get("station_info_timeout_s"))
        try:
            if int(float(old_timeout)) == 25:
                profile["station_info_timeout_s"] = 0
        except (TypeError, ValueError):
            pass
        profile["station_info_timeout_semantics_version"] = 1
    # Replace the implicit "0 means persistent" control with an explicit switch.
    # Existing positive timeouts remain enabled; persistent profiles remain
    # persistent and receive a useful delay ready for the switch to be turned on.
    if "station_info_auto_hide_enabled" not in profile:
        station_timeout = profile.get(
            "station_info_timeout_s", config.get("station_info_timeout_s", 30)
        )
        try:
            station_timeout = int(float(station_timeout))
        except (TypeError, ValueError):
            station_timeout = 30
        profile["station_info_auto_hide_enabled"] = station_timeout > 0
        if station_timeout <= 0:
            profile["station_info_timeout_s"] = 30
    # v5.3.6 narrows the visible product to exploration plus mining. Preserve
    # every stored achievement and legacy workspace setting, but disable broad
    # career packs and the retired colony-logistics overlay once per profile.
    if not profile.get("exploration_focus_migrated", False):
        disabled = set(
            profile.get(
                "achievements_disabled_categories",
                config.get("achievements_disabled_categories", []),
            ) or []
        )
        disabled.update(NON_FOCUSED_ACHIEVEMENT_CATEGORIES)
        profile["achievements_disabled_categories"] = sorted(disabled)
        profile["colony_overlay_enabled"] = False
        if str(profile.get("adaptive_mode_lock") or "auto") not in {
                "auto", "general", "exploration", "mining", "ground", "carrier", "station"}:
            profile["adaptive_mode_lock"] = "auto"
        profile["exploration_focus_enabled"] = True
        profile["exploration_focus_migrated"] = True
    is_initial_profile = len(profiles) <= 1
    # v5.3.7.5 gives Compact and Expanded independent window sizes. Preserve
    # the existing main-window geometry as this commander's first Expanded
    # size, while Compact starts smaller at the same screen position.
    base_geometry = str(
        config.get("main_geometry") or "1320x820"
    )
    position_match = re.search(r"([+-]-?\d+)([+-]-?\d+)$", base_geometry)
    position_suffix = position_match.group(0) if position_match else ""
    if "dashboard_expanded_geometry" not in profile:
        profile["dashboard_expanded_geometry"] = (
            base_geometry if is_initial_profile else f"1320x820{position_suffix}"
        )
    if "dashboard_compact_geometry" not in profile:
        profile["dashboard_compact_geometry"] = f"1120x680{position_suffix}"
    # The original Expanded target was only 1320px wide. Its three-column
    # briefing then wrapped heavily beneath the persistent 232px rail, making
    # the lower log/footer feel clipped even in a tall window. Grow that one
    # shipped footprint once; any size the commander chooses afterwards wins.
    try:
        dashboard_geometry_version = int(
            profile.get("dashboard_window_geometry_version") or 0
        )
    except (TypeError, ValueError):
        dashboard_geometry_version = 0
    if dashboard_geometry_version < 2:
        expanded = str(
            profile.get("dashboard_expanded_geometry") or "1720x1120"
        )
        expanded_match = re.fullmatch(
            r"(\d+)x(\d+)((?:[+-]-?\d+){2})?", expanded,
        )
        if expanded_match:
            expanded_width = max(1720, int(expanded_match.group(1)))
            expanded_height = max(1120, int(expanded_match.group(2)))
            expanded_position = expanded_match.group(3) or ""
            profile["dashboard_expanded_geometry"] = (
                f"{expanded_width}x{expanded_height}{expanded_position}"
            )
        else:
            profile["dashboard_expanded_geometry"] = "1720x1120"
        profile["dashboard_window_geometry_version"] = 2
    config["active_commander_profile"] = key
    config["active_commander_name"] = profile.get("commander_name", config.get("active_commander_name", "Unknown Commander"))
    config["active_commander_fid"] = profile.get("fid", config.get("active_commander_fid", ""))
    text_defaults = {
        "edsm_cmdr_name": profile.get("commander_name", ""),
        "edsm_api_key": "",
        "edsm_game_version": "",
        "edsm_game_build": "",
        "carrier_discord_webhook_url": "",
        "screenshots_path": default_screenshot_path(config.get("journal_path")),
        "ui_theme_name": _themes.DEFAULT_THEME_NAME,
        "hud_crt_intensity": "Subtle",
        "adaptive_mode_lock": "auto",
        "explore_active_page": "System Survey",
        "explore_survey_filter": "All bodies",
        "explore_discovery_filter": "All",
        "explore_expedition_section": "Overview",
        "explore_map_scope": "All History",
        "colony_overlay_sort_mode": "alpha",
        "overlay_hotkey_layout_studio": "Ctrl+Alt+Shift+F10",
        "overlay_hotkey_toggle_all": "Ctrl+Alt+Shift+F11",
        "overlay_hotkey_navigation": "",
        "overlay_hotkey_navigation_layout": "",
        "overlay_hotkey_survey": "",
        "overlay_hotkey_system_info": "",
        "overlay_hotkey_station_info": "",
        "overlay_hotkey_cargo": "",
        "overlay_hotkey_carrier": "",
        "overlay_hotkey_prospector": "",
        "overlay_hotkey_colony": "",
        "overlay_hotkey_field_bookmark": "Ctrl+Alt+Shift+F12",
    }
    bool_defaults = {
        "edsm_upload_enabled": False,
        "edsm_backfill_on_cache_rebuild": True,
        "eddn_market_upload_enabled": True,
        "overlay_enabled": True,
        "overlay_mouse_passthrough": os.name == "nt",
        "overlay_hotkeys_enabled": os.name == "nt",
        # The compact exploration deck is the everyday dashboard. The full
        # briefing remains one click away and the choice is commander-local.
        "dashboard_compact_mode": True,
        # Existing profile files without the old boolean retain Expanded;
        # genuinely new commander profiles begin with the everyday Standard
        # layout. Stored True/False choices remain authoritative either way.
        "hud_compact_mode": not profile_config_exists,
        "cargo_overlay_enabled": False,
        "carrier_overlay_enabled": False,
        "colony_overlay_enabled": False,
        "colony_overlay_show_trips": True,
        "colony_overlay_site_only": False,
        "prospector_overlay_enabled": True,
        "system_info_enabled": True,
        "gravity_warning_overlay_enabled": True,
        "station_info_overlay_enabled": True,
        "station_info_auto_hide_enabled": False,
        "survey_status_overlay_enabled": True,
        "toast_overlay_enabled": True,
        "sample_clear_notifications_enabled": True,
        "rebuy_warnings_enabled": True,
        "data_risk_warnings_enabled": True,
        "heartbeat_overlay_enabled": True,
        "screenshots_enabled": False,
        "ground_popup_enabled": True,
        "ground_target_active": False,
        "auto_copy_waypoint": False,
        "route_auto_note_from_edsm": True,
        "achievements_enabled": True,
        "achievement_notifications_enabled": True,
        "hud_crt_enabled": True,
        "hud_crt_motion_enabled": True,
        "adaptive_command_enabled": True,
        "adaptive_overlay_scenes_enabled": True,
        "exploration_focus_enabled": True,
        "exploration_focus_migrated": False,
        "reduced_motion_enabled": False,
    }
    for setting in PROFILE_TEXT_SETTINGS:
        if setting not in profile:
            profile[setting] = config.get(setting, text_defaults.get(setting, "")) if is_initial_profile else text_defaults.get(setting, "")
    for setting in PROFILE_BOOL_SETTINGS:
        if setting not in profile:
            profile[setting] = bool(config.get(setting, bool_defaults.get(setting, False))) if is_initial_profile else bool_defaults.get(setting, False)
    for setting in PROFILE_VALUE_SETTINGS:
        if setting not in profile and setting in config:
            profile_defaults = {
                "ui_custom_themes": {},
                "nav_collapsed_groups": [],
                "adaptive_overlay_scenes": {},
                "ui_scale_percent": 100,
                "overlay_text_scale_percent": 100,
                "overlay_layout_presets": {},
                "overlay_layout_studio_geometry": "1080x720",
                "dashboard_compact_geometry": "1120x680",
                "dashboard_expanded_geometry": "1720x1120",
                "dashboard_window_geometry_version": 2,
                "explore_map_view_state": {},
                "explore_map_annotations": [],
                "explore_map_annotation_geometry": "470x360",
                "colony_overlay_font_scale": 1.0,
            }
            profile[setting] = (
                profile_defaults[setting] if not is_initial_profile and setting in profile_defaults
                else config.get(setting)
            )
    for setting in PROFILE_TEXT_SETTINGS:
        config[setting] = profile.get(setting, "")
    for setting in PROFILE_BOOL_SETTINGS:
        config[setting] = bool(profile.get(setting, False))
    for setting in PROFILE_VALUE_SETTINGS:
        if setting in profile:
            config[setting] = profile.get(setting)
    return config


def save_active_profile_config(config):
    key = get_active_profile(config)
    profiles = config.setdefault("commander_profiles", {})
    profile = profiles.setdefault(key, {})
    profile["commander_name"] = config.get("active_commander_name", "Unknown Commander")
    profile["fid"] = config.get("active_commander_fid", "")
    for setting in PROFILE_TEXT_SETTINGS:
        profile[setting] = config.get(setting, "")
    for setting in PROFILE_BOOL_SETTINGS:
        profile[setting] = bool(config.get(setting, False))
    for setting in PROFILE_VALUE_SETTINGS:
        if setting in config:
            profile[setting] = config.get(setting)
    profile_payload = {k: profile.get(k) for k in ("commander_name", "fid") + PROFILE_SETTINGS if k in profile}
    try:
        with open(get_profile_config_file(key), "w") as f:
            json.dump(profile_payload, f, indent=4)
    except Exception:
        pass
    profiles[key] = {
        "commander_name": profile.get("commander_name", "Unknown Commander"),
        "fid": profile.get("fid", ""),
    }
    config["active_commander_profile"] = key
    return profile


def save_config(config):
    """Persist global config plus the active commander's profile config."""
    save_active_profile_config(config)
    root_payload = {}
    for key in GLOBAL_ONLY_KEYS:
        if key in config:
            root_payload[key] = config.get(key)
    profiles = {}
    for key, profile in config.get("commander_profiles", {}).items():
        profiles[key] = {
            "commander_name": profile.get("commander_name", "Unknown Commander"),
            "fid": profile.get("fid", ""),
        }
    root_payload["commander_profiles"] = profiles
    for key in DEPRECATED_CONFIG_KEYS:
        root_payload.pop(key, None)
    with open(CONFIG_FILE, "w") as f:
        json.dump(root_payload, f, indent=4)


def load_config():
    """Loads configuration from file or returns defaults."""
    # A restore is deliberately deferred until startup so no live SQLite
    # connection or persistence worker can be writing the profile being replaced.
    try:
        from profile_backups import apply_pending_restore
        apply_pending_restore(PROFILE_DIR)
    except Exception:
        pass
    config_existed = os.path.exists(CONFIG_FILE)
    detected_journal = detect_elite_journal_path()
    defaults = {
        'journal_path': '',
        'nav_collapsed_groups': [],
        'overlay_enabled': True,
        'overlay_mouse_passthrough': os.name == 'nt',
        'overlay_hotkeys_enabled': os.name == 'nt',
        'dashboard_compact_mode': True,
        'overlay_hotkey_layout_studio': 'Ctrl+Alt+Shift+F10',
        'overlay_hotkey_toggle_all': 'Ctrl+Alt+Shift+F11',
        'overlay_hotkey_navigation': '',
        'overlay_hotkey_navigation_layout': '',
        'overlay_hotkey_survey': '',
        'overlay_hotkey_system_info': '',
        'overlay_hotkey_station_info': '',
        'overlay_hotkey_cargo': '',
        'overlay_hotkey_carrier': '',
        'overlay_hotkey_prospector': '',
        'overlay_hotkey_colony': '',
        'overlay_hotkey_field_bookmark': 'Ctrl+Alt+Shift+F12',
        # New installs start with Standard. An older root config that somehow
        # lacks the setting keeps the historical Expanded default.
        'hud_compact_mode': not config_existed,
        'cargo_overlay_enabled': False,
        'carrier_overlay_enabled': False,
        'colony_overlay_enabled': False,
        'colony_overlay_show_trips': True,
        'colony_overlay_site_only': False,
        'colony_overlay_sort_mode': 'alpha',
        'prospector_overlay_enabled': True,
        'prospector_hud_timeout_s': 45,
        'prospector_hud_x': 30,
        'prospector_hud_y': 600,
        'system_info_enabled': True,
        'system_info_timeout_s': 30,
        'system_info_hud_x': 30,
        'system_info_hud_y': 30,
        'hud_x': 100,
        'hud_y': 100,
        'cargo_hud_x': 800,
        'cargo_hud_y': 400,
        'carrier_hud_x': 30,
        'carrier_hud_y': 180,
        'colony_overlay_x': 40,
        'colony_overlay_y': 40,
        'colony_overlay_w': 380,
        'colony_overlay_h': 260,
        'colony_overlay_font_scale': 1.0,
        # gravity_warning_hud_x intentionally omitted — defaults to a
        # screen-width-relative right-edge position computed in its own
        # constructor (matches toast_hud_x/_y).
        'gravity_warning_hud_y': 530,
        'gravity_warning_hud_timeout_s': 20,
        'gravity_warning_threshold_g': 3.0,
        'station_info_hud_x': 30,
        'station_info_hud_y': 380,
        'station_info_auto_hide_enabled': False,
        'station_info_timeout_s': 30,
        'station_info_timeout_semantics_version': 1,
        'survey_status_hud_x': 30,
        'survey_status_hud_y': 520,
        'low_fuel_threshold_pct': 0.25,
        'main_geometry': '1000x700',
        'dashboard_compact_geometry': '1120x680',
        'dashboard_expanded_geometry': '1720x1120',
        'dashboard_window_geometry_version': 2,
        'settings_geometry': '980x800',
        'ground_target_window_geometry': '430x230+1220+260',
        'ground_popup_geometry': '340x140+1320+160',
        'ground_popup_enabled': True,
        'ground_target_active': False,
        'ground_target_lat': 0.0,
        'ground_target_lon': 0.0,
        'perf_spike_threshold_ms': 45.0,
        'ui_watchdog_spike_ms': 120.0,
        'ui_stall_sampler_enabled': True,
        'ui_stall_sample_ms': 200.0,
        'db_commit_interval_ms': 250,
        'screenshot_max_convert_per_cycle': 2,
        'overlay_topmost_refresh_ms': 12000,
        'hud_anim_interval_ms': 33,
        'hud_animation_cadence_version': 2,
        'runtime_trace_enabled': True,
        'runtime_trace_path': 'logs/runtime_trace.log',
        'crash_reporting_enabled': True,
        'watcher_max_journal_lines_per_cycle': 40,
        'watcher_startup_max_lines_per_cycle': 20,
        'watcher_startup_tail_bytes': 131072,
        'watcher_special_file_settle_ms': 200,
        'screenshots_enabled': False,
        'screenshots_path': default_screenshot_path(detected_journal),
        'edsm_cmdr_name': '',
        'edsm_api_key': '',
        'edsm_upload_enabled': False,
        'edsm_backfill_on_cache_rebuild': True,
        'edsm_game_version': '',
        'edsm_game_build': '',
        'active_commander_profile': 'unknown_commander',
        'active_commander_name': 'Unknown Commander',
        'active_commander_fid': '',
        'commander_profiles': {},
        'engineer_window_geometry': '740x560',
        'bgs_window_geometry': '880x580',
        'carrier_window_geometry': '480x560',
        'colonisation_window_geometry': '740x560',
        'mining_geometry': '1050x660',
        'route_plotter_geometry': '920x700',
        'edit_dialog_geometry': '420x220',
        'import_dialog_geometry': '440x540',
        'profile_dashboard_geometry': '760x520',
        'value_ledger_geometry': '980x620',
        'colonisation_planner_geometry': '900x560',
        'exploration_window_geometry': '1040x680',
        'system_plotter_form': {},
        'route_auto_note_from_edsm': True,
        'auto_copy_waypoint': False,
        'eddn_market_upload_enabled': True,
        'achievements_enabled': True,
        'achievement_notifications_enabled': True,
        'achievements_disabled_categories': [],
        'achievement_window_geometry': '1080x700',
        'hud_crt_enabled': True,
        'hud_crt_motion_enabled': True,
        'hud_crt_intensity': 'Subtle',
        'adaptive_command_enabled': True,
        'adaptive_overlay_scenes_enabled': True,
        'exploration_focus_enabled': True,
        'exploration_focus_migrated': False,
        'adaptive_mode_lock': 'auto',
        'explore_active_page': 'System Survey',
        'explore_survey_filter': 'All bodies',
        'explore_discovery_filter': 'All',
        'explore_expedition_section': 'Overview',
        'explore_map_scope': 'All History',
        'explore_map_view_state': {},
        'explore_map_annotations': [],
        'explore_map_annotation_geometry': '470x360',
        'adaptive_overlay_scenes': {},
        'ui_scale_percent': 100,
        'overlay_text_scale_percent': 100,
        'overlay_layout_presets': {},
        'overlay_layout_studio_geometry': '1080x720',
        'reduced_motion_enabled': False,
        'ui_theme_name': _themes.DEFAULT_THEME_NAME,
        'ui_custom_themes': {},
        # Existing installations migrate silently; only a genuinely new
        # config receives the guided public-release setup.
        'onboarding_complete': bool(config_existed),
        'recovery_safe_mode_enabled': True,
        'last_app_version': '',
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                for key in DEPRECATED_CONFIG_KEYS:
                    data.pop(key, None)
                defaults.update(data)
                # Navigation animation originally shipped at 100 ms, then
                # 40 ms. Advance only exact shipped defaults through each
                # cadence generation; deliberate custom values stay intact.
                try:
                    cadence_version = int(data.get("hud_animation_cadence_version") or 0)
                except (TypeError, ValueError):
                    cadence_version = 0
                if cadence_version < 1:
                    try:
                        legacy_interval = int(float(data.get("hud_anim_interval_ms", 100)))
                    except (TypeError, ValueError):
                        legacy_interval = 100
                    if legacy_interval == 100:
                        defaults["hud_anim_interval_ms"] = 40
                    cadence_version = 1
                if cadence_version < 2:
                    try:
                        previous_interval = int(float(defaults.get("hud_anim_interval_ms", 40)))
                    except (TypeError, ValueError):
                        previous_interval = 40
                    if previous_interval == 40:
                        defaults["hud_anim_interval_ms"] = 33
                    cadence_version = 2
                defaults["hud_animation_cadence_version"] = cadence_version
        except Exception:
            pass
    if not defaults['journal_path']:
        defaults['journal_path'] = detected_journal
    apply_profile_config(defaults)
    return defaults
