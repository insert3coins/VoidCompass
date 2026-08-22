"""Renderer-neutral catalogue and defaults for managed cockpit overlays."""

DEFAULT_POSITIONS = {
    "hud": (100, 100), "cargo_hud": (800, 400),
    "carrier_hud": (30, 180),
    "prospector_hud": (30, 600), "system_info_hud": (30, 30),
    "gravity_warning_hud": (1200, 530), "station_info_hud": (30, 380),
    "survey_status_hud": (30, 520), "toast_hud": (1200, 80),
    "heartbeat_hud": (24, 24), "colony_overlay": (40, 40),
}

DEFAULT_SIZES = {
    "hud": (430, 230), "cargo_hud": (360, 220),
    "carrier_hud": (430, 270),
    "prospector_hud": (380, 220), "system_info_hud": (560, 386),
    "gravity_warning_hud": (280, 90), "station_info_hud": (520, 442),
    "survey_status_hud": (520, 340), "toast_hud": (340, 110),
    "heartbeat_hud": (42, 42), "colony_overlay": (380, 220),
}

OVERLAY_LABELS = {
    "hud": "Navigation HUD",
    "cargo_hud": "Cargo HUD",
    "carrier_hud": "Fleet / Squadron Carrier HUD",
    "prospector_hud": "Prospector Analysis",
    "system_info_hud": "System Intelligence",
    "gravity_warning_hud": "Gravity Warning",
    "station_info_hud": "Station Information",
    "survey_status_hud": "Survey Operations",
    "toast_hud": "Event Toast",
    "heartbeat_hud": "Journal Heartbeat",
    "colony_overlay": "Colony Logistics",
}

OVERLAY_CARD_LABELS = {
    "hud": "NAVIGATION",
    "cargo_hud": "CARGO",
    "carrier_hud": "CARRIER",
    "prospector_hud": "PROSPECTOR",
    "system_info_hud": "SYS INTEL",
    "gravity_warning_hud": "GRAVITY",
    "station_info_hud": "STATION",
    "survey_status_hud": "SURVEY",
    "toast_hud": "TOASTS",
    "heartbeat_hud": "HEARTBEAT",
    "colony_overlay": "COLONY",
}

OVERLAY_ENABLE_KEYS = {
    "hud": "overlay_enabled",
    "cargo_hud": "cargo_overlay_enabled",
    "carrier_hud": "carrier_overlay_enabled",
    "prospector_hud": "prospector_overlay_enabled",
    "system_info_hud": "system_info_enabled",
    "gravity_warning_hud": "gravity_warning_overlay_enabled",
    "station_info_hud": "station_info_overlay_enabled",
    "survey_status_hud": "survey_status_overlay_enabled",
    "toast_hud": "toast_overlay_enabled",
    "heartbeat_hud": "heartbeat_overlay_enabled",
    "colony_overlay": "colony_overlay_enabled",
}

# Kept readable for old profiles without exposing the retired feature.
HIDDEN_LEGACY_OVERLAYS = {"colony_overlay"}

