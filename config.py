import os
import json


def _get_config_file():
    # Always resolve config relative to current working directory.
    # This matches local Python runs and packaged EXE runs from dist/.
    return os.path.abspath(os.path.join(os.getcwd(), "config.json"))


CONFIG_FILE = _get_config_file()
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
        'discord_webhook': '',
        'discord_enabled': True,
        'discord_live_enabled': True,
        'discord_fleet_enabled': True,
        'overlay_enabled': True,
        'cargo_overlay_enabled': False,
        'scan_overlay_enabled': True,
        'hud_x': 100,
        'hud_y': 100,
        'cargo_hud_x': 800,
        'cargo_hud_y': 400,
        'scan_hud_x': 1000,
        'scan_hud_y': 150,
        'main_geometry': '1000x700',
        'settings_geometry': '600x500',
        'ground_popup_geometry': '340x140+1320+160',
        'ground_popup_enabled': True,
        'bio_estimate_popup_enabled': True,
        'bio_estimate_popup_geometry': '300x340+1450+180',
        'discord_msg_system': '',
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
        'watcher_special_file_settle_ms': 200
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
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
