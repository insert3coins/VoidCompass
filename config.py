import os
import json
import re


def _get_config_file():
    # Always resolve config relative to current working directory.
    # This matches local Python runs and packaged EXE runs from dist/.
    return os.path.abspath(os.path.join(os.getcwd(), "config.json"))


CONFIG_FILE = _get_config_file()
PROFILE_DIR = os.path.abspath(os.path.join(os.getcwd(), "profiles"))
PROFILE_CONFIG_NAME = "config.json"
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
)
COLOR_BG = '#0b0b0b'
COLOR_PANEL = '#1e1e1e'
COLOR_ACCENT = '#00d1ff'
COLOR_ORANGE = '#FF7100'
COLOR_TEXT = '#e0e0e0'
COLOR_GREEN = '#00ff00'


PROFILE_TEXT_SETTINGS = (
    "edsm_cmdr_name",
    "edsm_api_key",
    "edsm_game_version",
    "edsm_game_build",
    "carrier_discord_webhook_url",
    "screenshots_path",
)

PROFILE_BOOL_SETTINGS = (
    "edsm_upload_enabled",
    "overlay_enabled",
    "hud_compact_mode",
    "cargo_overlay_enabled",
    "carrier_overlay_enabled",
    "colony_overlay_enabled",
    "prospector_overlay_enabled",
    "system_info_enabled",
    "screenshots_enabled",
    "ground_popup_enabled",
    "ground_target_active",
    "auto_copy_waypoint",
    "route_auto_note_from_edsm",
    "trade_eddn_upload_enabled",
)

PROFILE_VALUE_SETTINGS = (
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
    "trade_window_geometry",
    "trade_route_form",
    "system_plotter_form",
    "trade_watchlist",
)

PROFILE_SETTINGS = PROFILE_TEXT_SETTINGS + PROFILE_BOOL_SETTINGS + PROFILE_VALUE_SETTINGS
GLOBAL_ONLY_KEYS = (
    "journal_path",
    "main_geometry",
    "settings_geometry",
    "perf_spike_threshold_ms",
    "ui_watchdog_spike_ms",
    "db_commit_interval_ms",
    "screenshot_max_convert_per_cycle",
    "overlay_topmost_refresh_ms",
    "hud_anim_interval_ms",
    "runtime_trace_enabled",
    "runtime_trace_path",
    "watcher_max_journal_lines_per_cycle",
    "watcher_startup_max_lines_per_cycle",
    "watcher_startup_tail_bytes",
    "watcher_special_file_settle_ms",
    "active_commander_profile",
    "active_commander_name",
    "active_commander_fid",
    "commander_profiles",
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
    if os.path.exists(profile_config_file):
        try:
            with open(profile_config_file, "r") as f:
                profile.update(json.load(f))
        except Exception:
            pass
    is_initial_profile = len(profiles) <= 1
    config["active_commander_profile"] = key
    config["active_commander_name"] = profile.get("commander_name", config.get("active_commander_name", "Unknown Commander"))
    config["active_commander_fid"] = profile.get("fid", config.get("active_commander_fid", ""))
    text_defaults = {
        "edsm_cmdr_name": profile.get("commander_name", ""),
        "edsm_api_key": "",
        "edsm_game_version": "",
        "edsm_game_build": "",
        "carrier_discord_webhook_url": "",
        "screenshots_path": os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous"),
    }
    bool_defaults = {
        "edsm_upload_enabled": False,
        "overlay_enabled": True,
        "hud_compact_mode": False,
        "cargo_overlay_enabled": False,
        "carrier_overlay_enabled": False,
        "colony_overlay_enabled": False,
        "prospector_overlay_enabled": True,
        "system_info_enabled": True,
        "screenshots_enabled": False,
        "ground_popup_enabled": True,
        "ground_target_active": False,
        "auto_copy_waypoint": False,
        "route_auto_note_from_edsm": True,
        "trade_eddn_upload_enabled": True,
    }
    for setting in PROFILE_TEXT_SETTINGS:
        if setting not in profile:
            profile[setting] = config.get(setting, text_defaults.get(setting, "")) if is_initial_profile else text_defaults.get(setting, "")
    for setting in PROFILE_BOOL_SETTINGS:
        if setting not in profile:
            profile[setting] = bool(config.get(setting, bool_defaults.get(setting, False))) if is_initial_profile else bool_defaults.get(setting, False)
    for setting in PROFILE_VALUE_SETTINGS:
        if setting not in profile and setting in config:
            profile[setting] = config.get(setting)
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
    defaults = {
        'journal_path': '',
        'overlay_enabled': True,
        'hud_compact_mode': False,
        'cargo_overlay_enabled': False,
        'carrier_overlay_enabled': False,
        'colony_overlay_enabled': False,
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
        'colony_overlay_w': 300,
        'colony_overlay_h': 260,
        'main_geometry': '1000x700',
        'settings_geometry': '600x500',
        'ground_target_window_geometry': '430x230+1220+260',
        'ground_popup_geometry': '340x140+1320+160',
        'ground_popup_enabled': True,
        'ground_target_active': False,
        'ground_target_lat': 0.0,
        'ground_target_lon': 0.0,
        'perf_spike_threshold_ms': 45.0,
        'ui_watchdog_spike_ms': 120.0,
        'db_commit_interval_ms': 250,
        'screenshot_max_convert_per_cycle': 2,
        'overlay_topmost_refresh_ms': 12000,
        'hud_anim_interval_ms': 100,
        'runtime_trace_enabled': True,
        'runtime_trace_path': 'runtime_trace.log',
        'watcher_max_journal_lines_per_cycle': 40,
        'watcher_startup_max_lines_per_cycle': 20,
        'watcher_startup_tail_bytes': 131072,
        'watcher_special_file_settle_ms': 200,
        'screenshots_enabled': False,
        'screenshots_path': os.path.join(os.path.expanduser("~"), "Pictures", "Frontier Developments", "Elite Dangerous"),
        'edsm_cmdr_name': '',
        'edsm_api_key': '',
        'edsm_upload_enabled': False,
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
        'trade_window_geometry': '1080x700',
        'trade_route_form': {},
        'system_plotter_form': {},
        'trade_watchlist': [],
        'route_auto_note_from_edsm': True,
        'auto_copy_waypoint': False,
        'trade_eddn_upload_enabled': True,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                for key in DEPRECATED_CONFIG_KEYS:
                    data.pop(key, None)
                defaults.update(data)
        except Exception:
            pass
    if not defaults['journal_path']:
        user_profile = os.environ.get('USERPROFILE')
        if user_profile:
            default_path = os.path.join(user_profile, 'Saved Games', 'Frontier Developments', 'Elite Dangerous')
            if os.path.exists(default_path):
                defaults['journal_path'] = default_path
    apply_profile_config(defaults)
    return defaults
