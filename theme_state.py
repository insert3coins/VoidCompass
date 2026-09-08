"""Renderer-neutral palette selection and live model colour rebinding."""
from types import SimpleNamespace
import sys
import themes

THEME = SimpleNamespace(**themes.normalize_theme(themes.ACTIVE_PALETTE))

def apply_ui_scale(runtime, percent=100):
    percent = max(75, min(200, int(float(percent))))
    runtime.ui_scale_percent = percent
    return percent

def apply_theme_live(runtime, theme_name, palette):
    palette = themes.normalize_theme(palette)
    themes.ACTIVE_PALETTE = dict(palette)
    themes.ACTIVE_THEME_NAME = theme_name
    for key, value in palette.items():
        setattr(THEME, key, value)
    slots = {'COLOR_BG':'bg','COLOR_PANEL':'panel','COLOR_ACCENT':'accent',
             'COLOR_ORANGE':'orange','COLOR_TEXT':'text','COLOR_MUTED':'muted',
             'COLOR_GREEN':'green','COLOR_YELLOW':'yellow', 'COLOR_RED':'red'}
    for name in ('config','dashboard','dashboard_scan_mixin','dashboard_core_mixin','hud','route_strip'):
        module = sys.modules.get(name)
        if module:
            for attr, key in slots.items():
                if hasattr(module, attr):
                    setattr(module, attr, palette[key])
    app = getattr(runtime, '_voidcompass_app', None)
    if app:
        for attr in ('hud','cargo_hud','carrier_hud','prospector_hud','station_info_hud',
                     'survey_status_hud','toast_hud','heartbeat_hud','contact_scope_hud','gravity_warning_hud'):
            overlay = getattr(app, attr, None)
            if overlay is not None:
                overlay.apply_theme(palette)
    return palette
