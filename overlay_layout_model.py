"""Renderer-neutral catalogue and defaults for managed cockpit overlays."""

DEFAULT_POSITIONS = {
    "hud": (100, 100), "cargo_hud": (800, 400),
    "carrier_hud": (30, 180),
    "prospector_hud": (30, 600),
    "gravity_warning_hud": (1200, 530), "station_info_hud": (30, 380),
    "survey_status_hud": (30, 520), "toast_hud": (1200, 80),
    "heartbeat_hud": (24, 24), "ground_popup": (1320, 160),
}

DEFAULT_SIZES = {
    "hud": (430, 230), "cargo_hud": (360, 220),
    "carrier_hud": (430, 270),
    "prospector_hud": (380, 220),
    "gravity_warning_hud": (320, 106), "station_info_hud": (520, 442),
    "survey_status_hud": (520, 340), "toast_hud": (400, 94),
    "heartbeat_hud": (42, 42), "ground_popup": (370, 154),
}

OVERLAY_LABELS = {
    "hud": "Navigation HUD",
    "cargo_hud": "Cargo HUD",
    "carrier_hud": "Fleet / Squadron Carrier HUD",
    "prospector_hud": "Prospector Analysis",
    "gravity_warning_hud": "Gravity Warning",
    "station_info_hud": "Station Information",
    "survey_status_hud": "Survey Operations",
    "toast_hud": "Cockpit Notifications",
    "heartbeat_hud": "Journal Heartbeat",
    "ground_popup": "Planet Waypoint Navigation",
}

OVERLAY_CARD_LABELS = {
    "hud": "NAVIGATION",
    "cargo_hud": "CARGO",
    "carrier_hud": "CARRIER",
    "prospector_hud": "PROSPECTOR",
    "gravity_warning_hud": "GRAVITY",
    "station_info_hud": "STATION",
    "survey_status_hud": "SURVEY",
    "toast_hud": "NOTIFY",
    "heartbeat_hud": "HEARTBEAT",
    "ground_popup": "SURFACE NAV",
}

OVERLAY_ENABLE_KEYS = {
    "hud": "overlay_enabled",
    "cargo_hud": "cargo_overlay_enabled",
    "carrier_hud": "carrier_overlay_enabled",
    "prospector_hud": "prospector_overlay_enabled",
    "gravity_warning_hud": "gravity_warning_overlay_enabled",
    "station_info_hud": "station_info_overlay_enabled",
    "survey_status_hud": "survey_status_overlay_enabled",
    "toast_hud": "toast_overlay_enabled",
    "heartbeat_hud": "heartbeat_overlay_enabled",
    "ground_popup": "ground_popup_enabled",
}
