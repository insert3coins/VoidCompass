"""Canonical metadata for every managed cockpit overlay and its hotkeys."""

from __future__ import annotations

from dataclasses import dataclass


# The Rhino coverage map (its minimap overlay, coverage maps, drill markers
# and map export) is switched off across the app until it is removed. Saved
# maps stay on disk untouched; nothing reads, paints or exports them.
RHINO_MAP_AVAILABLE = False


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
    available: bool = True


OVERLAY_SPECS = (
    OverlaySpec("hud", "navigation", "Void Compass Navigation HUD", "overlay_enabled", "hud_x", "hud_y", (100, 100), (430, 230), "Navigation HUD", "NAVIGATION", True, "navigation", "overlay_hotkey_navigation", "Navigation HUD", False),
    OverlaySpec("cargo_hud", "cargo", "Void Compass Cargo", "cargo_overlay_enabled", "cargo_hud_x", "cargo_hud_y", (800, 400), (410, 260), "Cargo Manifest", "CARGO", False, "cargo", "overlay_hotkey_cargo", "Cargo Manifest"),
    OverlaySpec("carrier_hud", "carrier", "Void Compass Carrier", "carrier_overlay_enabled", "carrier_hud_x", "carrier_hud_y", (30, 180), (430, 270), "Fleet / Squadron Carrier HUD", "CARRIER", False, "carrier", "overlay_hotkey_carrier", "Fleet Carrier"),
    OverlaySpec("prospector_hud", "prospector", "Void Compass Prospector", "prospector_overlay_enabled", "prospector_hud_x", "prospector_hud_y", (30, 600), (400, 250), "Prospector Analysis", "PROSPECTOR", True, "prospector", "overlay_hotkey_prospector", "Prospector Results"),
    OverlaySpec("planet_materials_hud", "planet-materials", "Void Compass Planet Materials", "planet_materials_overlay_enabled", "planet_materials_hud_x", "planet_materials_hud_y", (820, 80), (440, 390), "Planet Materials", "PLANET MATS", False, "planet_materials", "overlay_hotkey_planet_materials", "Planet Materials"),
    OverlaySpec("rhino_minimap_hud", "rhino-minimap", "Void Compass Rhino Coverage", "rhino_minimap_overlay_enabled", "rhino_minimap_hud_x", "rhino_minimap_hud_y", (30, 80), (360, 470), "Rhino Coverage Minimap", "RHINO MAP", False, "rhino_minimap", "overlay_hotkey_rhino_minimap", "Rhino Coverage Minimap", available=RHINO_MAP_AVAILABLE),
    OverlaySpec("powerplay_hud", "powerplay", "Void Compass Powerplay Operations", "powerplay_overlay_enabled", "powerplay_hud_x", "powerplay_hud_y", (820, 490), (430, 310), "Powerplay Operations", "POWERPLAY", False, "powerplay", "overlay_hotkey_powerplay", "Powerplay Operations"),
    OverlaySpec("gravity_warning_hud", "gravity", "Void Compass Gravity Warning", "gravity_warning_overlay_enabled", "gravity_warning_hud_x", "gravity_warning_hud_y", (1200, 530), (320, 106), "Gravity Warning", "GRAVITY", True, "gravity", "overlay_hotkey_gravity", "Gravity Warning"),
    OverlaySpec("station_info_hud", "station", "Void Compass Station Link", "station_info_overlay_enabled", "station_info_hud_x", "station_info_hud_y", (30, 380), (520, 442), "Station Information", "STATION", True, "station_info", "overlay_hotkey_station_info", "Station Info"),
    OverlaySpec("survey_status_hud", "survey", "Void Compass Survey Operations", "survey_status_overlay_enabled", "survey_status_hud_x", "survey_status_hud_y", (30, 520), (420, 340), "Survey Operations", "SURVEY", True, "survey", "overlay_hotkey_survey", "Survey Operations"),
    OverlaySpec("toast_hud", "toast", "Void Compass Cockpit Notifications", "toast_overlay_enabled", "toast_hud_x", "toast_hud_y", (1200, 80), (400, 94), "Cockpit Notifications", "NOTIFY", True, "notifications", "overlay_hotkey_notifications", "Cockpit Notifications"),
    OverlaySpec("galnet_ticker_hud", "galnet-ticker", "Void Compass Galnet Ticker", "galnet_ticker_overlay_enabled", "galnet_ticker_hud_x", "galnet_ticker_hud_y", (360, 12), (860, 34), "Galnet Ticker", "GALNET", False, "galnet_ticker", "overlay_hotkey_galnet_ticker", "Galnet Ticker"),
    OverlaySpec("music_player_hud", "music-player", "Void Compass Music Player", "music_player_overlay_enabled", "music_player_hud_x", "music_player_hud_y", (40, 880), (460, 154), "Music Player", "MUSIC", False, "music_player", "overlay_hotkey_music_player", "Music Player"),
    OverlaySpec("heartbeat_hud", "heartbeat", "Void Compass Journal Heartbeat", "heartbeat_overlay_enabled", "heartbeat_hud_x", "heartbeat_hud_y", (24, 24), (54, 54), "Journal Heartbeat", "HEARTBEAT", True, "heartbeat", "overlay_hotkey_heartbeat", "Journal Heartbeat"),
    OverlaySpec("contact_scope_hud", "contact-scope", "Void Compass Deep Space Contacts", "contact_scope_overlay_enabled", "contact_scope_hud_x", "contact_scope_hud_y", (1180, 250), (480, 270), "Deep Space Contact Scope", "CONTACTS", True, "contact_scope", "overlay_hotkey_contact_scope", "Deep Space Contacts"),
    # Shown only while the frame shift drive charges and in witch space.
    OverlaySpec("jump_info_hud", "jump-info", "Void Compass Jump Info", "jump_info_overlay_enabled", "jump_info_hud_x", "jump_info_hud_y", (680, 64), (560, 180), "Jump Info", "JUMP INFO", True, "jump_info", "overlay_hotkey_jump_info", "Jump Info"),
    # Colonisation (5.5.2): at construction sites, in station services, or on
    # the right-hand panel; after SrvSurvey's build commodities panel.
    OverlaySpec("colony_needs_hud", "colony-needs", "Void Compass Construction Needs", "colony_needs_overlay_enabled", "colony_needs_hud_x", "colony_needs_hud_y", (1520, 120), (360, 320), "Construction Needs", "COLONY", True, "colony_needs", "overlay_hotkey_colony_needs", "Construction Needs"),
    # Trading (5.5.2.6): only while a trade route is being followed.
    OverlaySpec("trade_route_hud", "trade-route", "Void Compass Trade Route", "trade_route_overlay_enabled", "trade_route_hud_x", "trade_route_hud_y", (1520, 480), (360, 150), "Trade Route", "TRADE", True, "trade_route", "overlay_hotkey_trade_route", "Trade Route"),
    OverlaySpec("ground_popup", "ground-target", "Void Compass Planet Waypoint Navigation", "ground_popup_enabled", "ground_popup_x", "ground_popup_y", (1320, 160), (420, 208), "Planet Waypoint Navigation", "SURFACE NAV", True, "planet_waypoint", "overlay_hotkey_planet_waypoint", "Planet Waypoint Navigation"),
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
    for spec in OVERLAY_SPECS if spec.html_managed and spec.available
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
    _overlay_hotkey("jump_info"),
    _overlay_hotkey("colony_needs"),
    _overlay_hotkey("trade_route"),
    ("colony_refresh", "overlay_hotkey_colony_refresh", "Construction Needs: refresh from Raven Colonial", None),
    ("colony_fold", "overlay_hotkey_colony_fold", "Construction Needs: fold / unfold covered groups", None),
    _overlay_hotkey("survey"),
    _overlay_hotkey("contact_scope"),
    _overlay_hotkey("station_info"),
    _overlay_hotkey("cargo"),
    _overlay_hotkey("carrier"),
    _overlay_hotkey("prospector"),
    _overlay_hotkey("planet_materials"),
    _overlay_hotkey("powerplay"),
    _overlay_hotkey("gravity"),
    _overlay_hotkey("notifications"),
    _overlay_hotkey("heartbeat"),
    _overlay_hotkey("galnet_ticker"),
    _overlay_hotkey("music_player"),
    # The player itself, from anywhere: in game, or with the deck on another screen.
    ("music_play_pause", "overlay_hotkey_music_play_pause", "Music: play / pause", None),
    ("music_next", "overlay_hotkey_music_next", "Music: next track", None),
    ("music_previous", "overlay_hotkey_music_previous", "Music: previous track", None),
    # Poke the Watcher: it looks up and answers (5.5.3.2).
    ("watcher_poke", "overlay_hotkey_watcher_poke", "The Watcher: poke", None),
    _overlay_hotkey("planet_waypoint"),
    ("field_bookmark", "overlay_hotkey_field_bookmark", "Save field bookmark", None),
)

DEFAULT_OVERLAY_HOTKEYS = {
    "overlay_hotkey_layout_studio": "Ctrl+Alt+Shift+F10",
    "overlay_hotkey_toggle_all": "Ctrl+Alt+Shift+F11",
    "overlay_hotkey_field_bookmark": "Ctrl+Alt+Shift+F12",
    "overlay_hotkey_watcher_poke": "Ctrl+Alt+Shift+F9",
}
