"""Canonical metadata for every managed cockpit overlay and its hotkeys."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlaySpec:
    attr: str
    overlay_id: str
    title: str
    enabled_key: str
    x_key: str
    y_key: str
    default_position: tuple[int, int]
    default_size: tuple[int, int]
    label: str
    card_label: str
    default_enabled: bool
    hotkey_action: str
    hotkey_key: str
    hotkey_label: str
    html_managed: bool = True


OVERLAY_SPECS = (
    OverlaySpec("hud", "navigation", "Void Compass Navigation HUD", "overlay_enabled", "hud_x", "hud_y", (100, 100), (430, 230), "Navigation HUD", "NAVIGATION", True, "navigation", "overlay_hotkey_navigation", "Navigation HUD", False),
    OverlaySpec("cargo_hud", "cargo", "Void Compass Cargo", "cargo_overlay_enabled", "cargo_hud_x", "cargo_hud_y", (800, 400), (410, 260), "Cargo Manifest", "CARGO", False, "cargo", "overlay_hotkey_cargo", "Cargo Manifest"),
    OverlaySpec("carrier_hud", "carrier", "Void Compass Carrier", "carrier_overlay_enabled", "carrier_hud_x", "carrier_hud_y", (30, 180), (430, 270), "Fleet / Squadron Carrier HUD", "CARRIER", False, "carrier", "overlay_hotkey_carrier", "Fleet Carrier"),
    OverlaySpec("prospector_hud", "prospector", "Void Compass Prospector", "prospector_overlay_enabled", "prospector_hud_x", "prospector_hud_y", (30, 600), (400, 250), "Prospector Analysis", "PROSPECTOR", True, "prospector", "overlay_hotkey_prospector", "Prospector Results"),
    OverlaySpec("planet_materials_hud", "planet-materials", "Void Compass Planet Materials", "planet_materials_overlay_enabled", "planet_materials_hud_x", "planet_materials_hud_y", (820, 80), (440, 390), "Planet Materials", "PLANET MATS", False, "planet_materials", "overlay_hotkey_planet_materials", "Planet Materials"),
    OverlaySpec("rhino_minimap_hud", "rhino-minimap", "Void Compass Rhino Coverage", "rhino_minimap_overlay_enabled", "rhino_minimap_hud_x", "rhino_minimap_hud_y", (30, 80), (360, 470), "Rhino Coverage Minimap", "RHINO MAP", True, "rhino_minimap", "overlay_hotkey_rhino_minimap", "Rhino Coverage Minimap"),
    OverlaySpec("powerplay_hud", "powerplay", "Void Compass Powerplay Operations", "powerplay_overlay_enabled", "powerplay_hud_x", "powerplay_hud_y", (820, 490), (430, 310), "Powerplay Operations", "POWERPLAY", False, "powerplay", "overlay_hotkey_powerplay", "Powerplay Operations"),
    OverlaySpec("gravity_warning_hud", "gravity", "Void Compass Gravity Warning", "gravity_warning_overlay_enabled", "gravity_warning_hud_x", "gravity_warning_hud_y", (1200, 530), (320, 106), "Gravity Warning", "GRAVITY", True, "gravity", "overlay_hotkey_gravity", "Gravity Warning"),
    OverlaySpec("station_info_hud", "station", "Void Compass Station Link", "station_info_overlay_enabled", "station_info_hud_x", "station_info_hud_y", (30, 380), (520, 442), "Station Information", "STATION", True, "station_info", "overlay_hotkey_station_info", "Station Info"),
    OverlaySpec("survey_status_hud", "survey", "Void Compass Survey Operations", "survey_status_overlay_enabled", "survey_status_hud_x", "survey_status_hud_y", (30, 520), (520, 340), "Survey Operations", "SURVEY", True, "survey", "overlay_hotkey_survey", "Survey Operations"),
    OverlaySpec("toast_hud", "toast", "Void Compass Cockpit Notifications", "toast_overlay_enabled", "toast_hud_x", "toast_hud_y", (1200, 80), (400, 94), "Cockpit Notifications", "NOTIFY", True, "notifications", "overlay_hotkey_notifications", "Cockpit Notifications"),
    OverlaySpec("heartbeat_hud", "heartbeat", "Void Compass Journal Heartbeat", "heartbeat_overlay_enabled", "heartbeat_hud_x", "heartbeat_hud_y", (24, 24), (54, 54), "Journal Heartbeat", "HEARTBEAT", True, "heartbeat", "overlay_hotkey_heartbeat", "Journal Heartbeat"),
    OverlaySpec("contact_scope_hud", "contact-scope", "Void Compass Deep Space Contacts", "contact_scope_overlay_enabled", "contact_scope_hud_x", "contact_scope_hud_y", (1180, 250), (480, 270), "Deep Space Contact Scope", "CONTACTS", True, "contact_scope", "overlay_hotkey_contact_scope", "Deep Space Contacts"),
    OverlaySpec("ground_popup", "ground-target", "Void Compass Planet Waypoint Navigation", "ground_popup_enabled", "ground_popup_x", "ground_popup_y", (1320, 160), (370, 154), "Planet Waypoint Navigation", "SURFACE NAV", True, "planet_waypoint", "overlay_hotkey_planet_waypoint", "Planet Waypoint Navigation"),
)

OVERLAY_SPEC_BY_ATTR = {spec.attr: spec for spec in OVERLAY_SPECS}
DEFAULT_POSITIONS = {spec.attr: spec.default_position for spec in OVERLAY_SPECS}
DEFAULT_SIZES = {spec.attr: spec.default_size for spec in OVERLAY_SPECS}
OVERLAY_LABELS = {spec.attr: spec.label for spec in OVERLAY_SPECS}
OVERLAY_CARD_LABELS = {spec.attr: spec.card_label for spec in OVERLAY_SPECS}
OVERLAY_ENABLE_KEYS = {spec.attr: spec.enabled_key for spec in OVERLAY_SPECS}
OVERLAY_ENABLE_DEFAULTS = {spec.enabled_key: spec.default_enabled for spec in OVERLAY_SPECS}
OVERLAY_POSITION_SPECS = tuple((spec.attr, spec.x_key, spec.y_key) for spec in OVERLAY_SPECS)
HTML_OVERLAY_SPECS = {
    spec.attr: (spec.overlay_id, spec.title, spec.enabled_key)
    for spec in OVERLAY_SPECS if spec.html_managed
}


def _overlay_hotkey(action: str) -> tuple[str, str, str, str]:
    spec = next(item for item in OVERLAY_SPECS if item.hotkey_action == action)
    return action, spec.hotkey_key, spec.hotkey_label, spec.attr


# Action ordering is presentation ordering in Settings. Overlay labels, keys,
# target attributes and enable defaults still come exclusively from OVERLAY_SPECS.
OVERLAY_HOTKEY_SPECS = (
    ("layout_studio", "overlay_hotkey_layout_studio", "Toggle Overlay Layout Studio", None),
    ("toggle_all", "overlay_hotkey_toggle_all", "Show / hide all overlays", None),
    _overlay_hotkey("navigation"),
    ("navigation_layout", "overlay_hotkey_navigation_layout", "Navigation HUD layout", None),
    _overlay_hotkey("survey"),
    _overlay_hotkey("contact_scope"),
    _overlay_hotkey("station_info"),
    _overlay_hotkey("cargo"),
    _overlay_hotkey("carrier"),
    _overlay_hotkey("prospector"),
    _overlay_hotkey("planet_materials"),
    _overlay_hotkey("rhino_minimap"),
    ("rhino_minimap_center", "overlay_hotkey_rhino_minimap_center", "Rhino Minimap: Set Center", None),
    ("rhino_minimap_border", "overlay_hotkey_rhino_minimap_border", "Rhino Minimap: Set Border", None),
    ("rhino_minimap_drill", "overlay_hotkey_rhino_minimap_drill", "Rhino Minimap: Mark Drill Here", None),
    ("rhino_minimap_reset", "overlay_hotkey_rhino_minimap_reset", "Rhino Minimap: Reset Current Map", None),
    _overlay_hotkey("powerplay"),
    _overlay_hotkey("gravity"),
    _overlay_hotkey("notifications"),
    _overlay_hotkey("heartbeat"),
    _overlay_hotkey("planet_waypoint"),
    ("field_bookmark", "overlay_hotkey_field_bookmark", "Save field bookmark", None),
)

DEFAULT_OVERLAY_HOTKEYS = {
    "overlay_hotkey_layout_studio": "Ctrl+Alt+Shift+F10",
    "overlay_hotkey_toggle_all": "Ctrl+Alt+Shift+F11",
    "overlay_hotkey_field_bookmark": "Ctrl+Alt+Shift+F12",
    "overlay_hotkey_rhino_minimap_center": "Ctrl+Alt+Z",
    "overlay_hotkey_rhino_minimap_border": "Ctrl+Alt+B",
    "overlay_hotkey_rhino_minimap_drill": "Ctrl+Alt+D",
    "overlay_hotkey_rhino_minimap_reset": "Ctrl+Alt+Shift+R",
}
