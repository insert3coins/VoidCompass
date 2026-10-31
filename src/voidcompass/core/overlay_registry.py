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
    available: bool = True


OVERLAY_SPECS = (
    OverlaySpec("hud", "navigation", "Void Compass Navigation HUD", "overlay_enabled", "hud_x", "hud_y", (100, 100), (430, 230), "Navigation HUD", "NAVIGATION", True, "navigation", "overlay_hotkey_navigation", "Navigation HUD", False),
    OverlaySpec("cargo_hud", "cargo", "Void Compass Cargo", "cargo_overlay_enabled", "cargo_hud_x", "cargo_hud_y", (800, 400), (410, 260), "Cargo Manifest", "CARGO", False, "cargo", "overlay_hotkey_cargo", "Cargo Manifest"),
    OverlaySpec("carrier_hud", "carrier", "Void Compass Carrier", "carrier_overlay_enabled", "carrier_hud_x", "carrier_hud_y", (30, 180), (430, 270), "Fleet / Squadron Carrier HUD", "CARRIER", False, "carrier", "overlay_hotkey_carrier", "Fleet Carrier"),
    OverlaySpec("prospector_hud", "prospector", "Void Compass Prospector", "prospector_overlay_enabled", "prospector_hud_x", "prospector_hud_y", (30, 600), (400, 250), "Prospector Analysis", "PROSPECTOR", True, "prospector", "overlay_hotkey_prospector", "Prospector Results"),
    OverlaySpec("planet_materials_hud", "planet-materials", "Void Compass Planet Materials", "planet_materials_overlay_enabled", "planet_materials_hud_x", "planet_materials_hud_y", (820, 80), (440, 390), "Planet Materials", "PLANET MATS", False, "planet_materials", "overlay_hotkey_planet_materials", "Planet Materials"),
    OverlaySpec("powerplay_hud", "powerplay", "Void Compass Powerplay Operations", "powerplay_overlay_enabled", "powerplay_hud_x", "powerplay_hud_y", (820, 490), (430, 310), "Powerplay Operations", "POWERPLAY", False, "powerplay", "overlay_hotkey_powerplay", "Powerplay Operations"),
    OverlaySpec("gravity_warning_hud", "gravity", "Void Compass Gravity Warning", "gravity_warning_overlay_enabled", "gravity_warning_hud_x", "gravity_warning_hud_y", (1200, 530), (320, 106), "Gravity Warning", "GRAVITY", True, "gravity", "overlay_hotkey_gravity", "Gravity Warning"),
    OverlaySpec("station_info_hud", "station", "Void Compass Station Link", "station_info_overlay_enabled", "station_info_hud_x", "station_info_hud_y", (30, 380), (520, 442), "Station Information", "STATION", True, "station_info", "overlay_hotkey_station_info", "Station Info"),
    OverlaySpec("survey_status_hud", "survey", "Void Compass Survey Operations", "survey_status_overlay_enabled", "survey_status_hud_x", "survey_status_hud_y", (30, 520), (420, 340), "Survey Operations", "SURVEY", True, "survey", "overlay_hotkey_survey", "Survey Operations"),
    OverlaySpec("toast_hud", "toast", "Void Compass Cockpit Notifications", "toast_overlay_enabled", "toast_hud_x", "toast_hud_y", (1200, 80), (400, 94), "Cockpit Notifications", "NOTIFY", True, "notifications", "overlay_hotkey_notifications", "Cockpit Notifications"),
    # 5.5.4: achievements in their own window, on or off apart from notifications.
    OverlaySpec("achievement_hud", "achievements", "Void Compass Achievements", "achievement_overlay_enabled", "achievement_hud_x", "achievement_hud_y", (1200, 230), (420, 120), "Achievements", "ACHIEVE", True, "achievements", "overlay_hotkey_achievements", "Achievements"),
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
    # 5.6.1: an expedition at a glance; the HUD's EXPEDITION page stands in for it.
    OverlaySpec("expedition_hud", "expedition", "Void Compass Expedition", "expedition_overlay_enabled", "expedition_hud_x", "expedition_hud_y", (40, 560), (380, 220), "Expedition", "EXPEDITION", True, "expedition", "overlay_hotkey_expedition", "Expedition"),
    # 5.6.3: the Games page's pocket pet, where you can see it while you fly.
    OverlaySpec("hatchling_hud", "hatchling", "Void Compass Hatchling", "hatchling_overlay_enabled", "hatchling_hud_x", "hatchling_hud_y", (1660, 860), (250, 132), "Hatchling", "HATCHLING", False, "hatchling", "overlay_hotkey_hatchling", "Hatchling"),
    OverlaySpec("trade_route_hud", "trade-route", "Void Compass Trade Route", "trade_route_overlay_enabled", "trade_route_hud_x", "trade_route_hud_y", (1520, 480), (360, 150), "Trade Route", "TRADE", True, "trade_route", "overlay_hotkey_trade_route", "Trade Route"),
    # 5.5.3.7: the Milky Way in a corner, with you on it; and a Polaroid of
    # each screenshot taken in game.
    OverlaySpec("galaxy_minimap_hud", "galaxy-minimap", "Void Compass Galaxy Minimap", "galaxy_minimap_overlay_enabled", "galaxy_minimap_hud_x", "galaxy_minimap_hud_y", (40, 600), (240, 280), "Galaxy Minimap", "MINIMAP", False, "galaxy_minimap", "overlay_hotkey_galaxy_minimap", "Galaxy Minimap"),
    # 5.5.18: the ground round you in the Rhino, apart from the minimap.
    OverlaySpec("rhino_map_hud", "rhino-map", "Void Compass Rhino Map", "rhino_map_overlay_enabled", "rhino_map_hud_x", "rhino_map_hud_y", (300, 600), (240, 280), "Rhino Map", "RHINO MAP", True, "rhino_map", "overlay_hotkey_rhino_map", "Rhino Map"),
    OverlaySpec("postcard_hud", "postcards", "Void Compass Postcards", "postcard_overlay_enabled", "postcard_hud_x", "postcard_hud_y", (1700, 640), (380, 330), "Postcards", "POSTCARDS", True, "postcards", "overlay_hotkey_postcards", "Postcards"),
    # Rhino mining (5.5.10): the rigs you've set down, after SrvSurvey's rig tracker.
    OverlaySpec("rig_tracker_hud", "rig-tracker", "Void Compass Rig Tracker", "rig_tracker_overlay_enabled", "rig_tracker_hud_x", "rig_tracker_hud_y", (1320, 400), (420, 155), "Rig Tracker", "RIGS", True, "rig_tracker", "overlay_hotkey_rig_tracker", "Rig Tracker"),
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
    # The HUD's pages (5.5.17): follow what you're doing or choose, and the next page.
    ("hud_pages_mode", "overlay_hotkey_hud_pages_mode", "Navigation HUD: page mode (auto / manual)", None),
    ("hud_page_next", "overlay_hotkey_hud_page_next", "Navigation HUD: next page", None),
    _overlay_hotkey("jump_info"),
    _overlay_hotkey("colony_needs"),
    _overlay_hotkey("trade_route"),
    _overlay_hotkey("expedition"),
    ("colony_refresh", "overlay_hotkey_colony_refresh", "Construction Needs: refresh from Raven Colonial", None),
    ("colony_fold", "overlay_hotkey_colony_fold", "Construction Needs: fold / unfold covered groups", None),
    _overlay_hotkey("survey"),
    _overlay_hotkey("contact_scope"),
    _overlay_hotkey("station_info"),
    _overlay_hotkey("cargo"),
    _overlay_hotkey("carrier"),
    _overlay_hotkey("prospector"),
    _overlay_hotkey("rig_tracker"),
    # The game logs nothing when a rig goes down: its key marks it where you stand.
    *((f"rig_{n}", f"overlay_hotkey_rig_{n}", f"Rig Tracker: rig {n} deployed / collected", None) for n in range(1, 7)),
    ("rig_clear", "overlay_hotkey_rig_clear", "Rig Tracker: forget the rigs on this planet", None),
    _overlay_hotkey("planet_materials"),
    _overlay_hotkey("powerplay"),
    _overlay_hotkey("gravity"),
    _overlay_hotkey("notifications"),
    _overlay_hotkey("achievements"),
    _overlay_hotkey("heartbeat"),
    _overlay_hotkey("galnet_ticker"),
    _overlay_hotkey("galaxy_minimap"),
    ("galaxy_minimap_view", "overlay_hotkey_galaxy_minimap_view", "Galaxy Minimap: change the view", None),
    _overlay_hotkey("rhino_map"),
    ("rhino_map_range", "overlay_hotkey_rhino_map_range", "Rhino Map: range", None),
    _overlay_hotkey("postcards"),
    _overlay_hotkey("music_player"),
    _overlay_hotkey("hatchling"),
    # The player itself, from anywhere: in game, or with the deck on another screen.
    ("music_play_pause", "overlay_hotkey_music_play_pause", "Music: play / pause", None),
    ("music_next", "overlay_hotkey_music_next", "Music: next track", None),
    ("music_previous", "overlay_hotkey_music_previous", "Music: previous track", None),
    # Poke the Watcher: it looks up and answers (5.5.3.2).
    ("watcher_poke", "overlay_hotkey_watcher_poke", "The Watcher: poke", None),
    # 5.6.1: answering its questions.
    ("watcher_answer_1", "overlay_hotkey_watcher_answer_1", "The Watcher: answer 1", None),
    ("watcher_answer_2", "overlay_hotkey_watcher_answer_2", "The Watcher: answer 2", None),
    ("watcher_answer_3", "overlay_hotkey_watcher_answer_3", "The Watcher: answer 3", None),
    # 5.7.1: talk to it by voice (hold or tap, chosen on the MIND page).
    ("watcher_talk", "overlay_hotkey_watcher_talk", "The Watcher: talk (push to talk)", None),
    _overlay_hotkey("planet_waypoint"),
    # 5.6.1: marks the spot as one of the expedition's places.
    ("field_bookmark", "overlay_hotkey_field_bookmark", "Expedition: mark this place", None),
)

DEFAULT_OVERLAY_HOTKEYS = {
    "overlay_hotkey_layout_studio": "Ctrl+Alt+Shift+F10",
    "overlay_hotkey_toggle_all": "Ctrl+Alt+Shift+F11",
    "overlay_hotkey_field_bookmark": "Ctrl+Alt+Shift+F12",
    "overlay_hotkey_watcher_poke": "Ctrl+Alt+Shift+F9",
    "overlay_hotkey_watcher_talk": "Ctrl+Alt+Shift+F8",
    **{f"overlay_hotkey_rig_{n}": f"Ctrl+Alt+{n}" for n in range(1, 7)},
}

# Each overlay's own text size (5.5.4), chosen from a list in Overlay Studio:
# 0 follows the text size for all overlays. The first six had keys before.
TEXT_SIZES = (0, 75, 85, 100, 110, 125, 150, 175, 200)
TEXT_SIZE_KEYS = {
    "hud": "hud_text_scale_percent",
    "survey_status_hud": "survey_text_scale_percent",
    "music_player_hud": "music_player_text_scale_percent",
    "galnet_ticker_hud": "galnet_ticker_text_scale_percent",
    "galaxy_minimap_hud": "galaxy_minimap_text_scale_percent",
    "heartbeat_hud": "heartbeat_text_scale_percent",
    "cargo_hud": "cargo_text_scale_percent",
    "carrier_hud": "carrier_text_scale_percent",
    "prospector_hud": "prospector_text_scale_percent",
    "planet_materials_hud": "planet_materials_text_scale_percent",
    "powerplay_hud": "powerplay_text_scale_percent",
    "gravity_warning_hud": "gravity_text_scale_percent",
    "station_info_hud": "station_text_scale_percent",
    "toast_hud": "toast_text_scale_percent",
    "achievement_hud": "achievement_text_scale_percent",
    "contact_scope_hud": "contact_scope_text_scale_percent",
    "jump_info_hud": "jump_info_text_scale_percent",
    "colony_needs_hud": "colony_needs_text_scale_percent",
    "trade_route_hud": "trade_route_text_scale_percent",
    "expedition_hud": "expedition_text_scale_percent",
    "hatchling_hud": "hatchling_text_scale_percent",
    "rig_tracker_hud": "rig_tracker_text_scale_percent",
    "rhino_map_hud": "rhino_map_text_scale_percent",
    "postcard_hud": "postcard_text_scale_percent",
    "ground_popup": "ground_text_scale_percent",
}
OVERLAY_ATTR_BY_ENABLED = {spec.enabled_key: spec.attr for spec in OVERLAY_SPECS}


def text_size_choice(value):
    """The nearest of TEXT_SIZES (0, or anything below 75, stays 0). A number
    field saved on every arrow step, so it settled on odd values; this list
    is what Overlay Studio offers now."""
    try:
        value = int(float(value))
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return min(TEXT_SIZES[1:], key=lambda size: (abs(size - value), size))


def overlay_text_percent(config, attr):
    """An overlay's text size, 75-200: its own, or the one for all overlays."""
    config = config or {}
    own = text_size_choice(config.get(TEXT_SIZE_KEYS.get(attr, "")))
    if own:
        return own
    try:
        every = int(float(config.get("overlay_text_scale_percent", 100)))
    except (TypeError, ValueError):
        every = 100
    return max(75, min(200, every))


def overlay_text_scale(config, attr):
    return overlay_text_percent(config, attr) / 100.0
