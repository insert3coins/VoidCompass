import os
import json
CONFIG_FILE = 'config.json'
EDSM_CACHE_FILE = 'edsm_cache.json'
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
        'edsm_cmdr_name': '',
        'edsm_api_key': '',
        'discord_webhook': '',
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
        'discord_msg_system': ''
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
