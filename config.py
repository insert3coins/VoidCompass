import os
import json


def _get_config_file():
    # Always resolve config relative to current working directory.
    # This matches local Python runs and packaged EXE runs from dist/.
    return os.path.abspath(os.path.join(os.getcwd(), "config.json"))


CONFIG_FILE = _get_config_file()
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
def load_config():
    """Loads configuration from file or returns defaults."""
    defaults = {
        'journal_path': '',
        'overlay_enabled': True,
        'cargo_overlay_enabled': False,
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
        'main_geometry': '1000x700',
        'settings_geometry': '600x500',
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
        'edsm_cmdr_name': '',
        'edsm_api_key': '',
        'edsm_upload_enabled': False,
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
    return defaults
