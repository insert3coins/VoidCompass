import json
import os

CONFIG_FILE = "config.json"

# Theme Colors
COLOR_BG = "#050505"
COLOR_PANEL = "#111111"
COLOR_ACCENT = "#00d1ff"
COLOR_ORANGE = "#FF7100"
COLOR_TEXT = "#dddddd"
COLOR_GREEN = "#00ff00"

def load_config():
    """Load configuration from JSON file or return defaults."""
    defaults = {
        "main_geometry": "1000x700",
        "journal_path": "",
        "edsm_enabled": True,
        "edsm_cmdr_name": "",
        "edsm_api_key": "",
        "discord_enabled": False,
        "discord_webhook": "",
        "discord_msg_system": "",
        "screenshots_enabled": False,
        "screenshots_path": "",
        "overlay_enabled": True,
        "cargo_overlay_enabled": False,
        "hud_x": 100,
        "hud_y": 100,
        "auto_copy_waypoint": False,
        "route_plotter_geometry": "600x600",
        "edit_dialog_geometry": "300x150",
        "import_dialog_geometry": "400x500"
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
                defaults.update(user_config)
        except Exception:
            pass
            
    return defaults