"""The deck's Tools page (5.5.4): one place for everything you switch often,
for MainDashboard. Every switch here is the same setting as on its own page;
this page only gathers them."""
from __future__ import annotations

import time

from voidcompass.core.overlay_registry import OVERLAY_SPECS
from voidcompass.core.platform_support import open_path
from voidcompass.overlays import watcher_mind
from voidcompass.overlays.music_player_hud import _track
from voidcompass.voice import voice_assets

# Settings switches the Tools page may flip: (key, label, what it does, where it lives).
TOOL_SWITCHES = (
    ("edsm_upload_enabled", "EDSM uploads", "Send exploration to EDSM.", "integrations"),
    ("inara_upload_enabled", "Inara sync", "Keep your Inara profile up to date.", "integrations"),
    ("eddn_market_upload_enabled", "EDDN markets", "Share the markets you visit.", "integrations"),
    ("screenshots_enabled", "Screenshot converter", "Turn each new BMP into a PNG.", "journal"),
    ("galnet_enabled", "Galnet relay", "News for the deck and the ticker.", "galnet"),
    ("achievements_enabled", "Achievements", "Unlock achievements as you play.", "flight"),
    ("overlay_mouse_passthrough", "Click-through overlays", "Clicks pass through to the game.", "studio"),
    ("overlay_hide_on_maps", "Hide overlays on maps", "Out of the way on the galaxy and system maps.", "studio"),
    ("music_follow_game", "Music follows the game", "Playlists change with what you're doing.", "music"),
    ("reduced_motion_enabled", "Reduced motion", "Calmer animations everywhere.", "appearance"),
)
STUDIO_OPTIONS = {"overlay_mouse_passthrough", "overlay_hide_on_maps"}
# How the overlays are grouped on the page; anything new lands in "other".
OVERLAY_GROUPS = (
    ("flight", "Flight & navigation", ("hud", "jump_info_hud", "gravity_warning_hud", "station_info_hud",
                                       "galaxy_minimap_hud", "contact_scope_hud")),
    ("surface", "Exploration & surface", ("survey_status_hud", "planet_materials_hud", "ground_popup", "postcard_hud")),
    ("industry", "Industry & commerce", ("cargo_hud", "prospector_hud", "trade_route_hud", "colony_needs_hud",
                                         "carrier_hud", "powerplay_hud")),
    ("cockpit", "Cockpit & companion", ("toast_hud", "achievement_hud", "heartbeat_hud", "galnet_ticker_hud",
                                        "music_player_hud")),
)
GROUP_OF = {attr: group for group, _label, attrs in OVERLAY_GROUPS for attr in attrs}


class DashboardToolsMixin:
    def _html_tools_workspace(self):
        config = self.config
        overlays = [{"id": spec.attr, "label": spec.label, "card": spec.card_label,
                     "group": GROUP_OF.get(spec.attr, "other"),
                     "enabled": bool(config.get(spec.enabled_key, spec.default_enabled))}
                    for spec in OVERLAY_SPECS if spec.available]
        overlays.sort(key=lambda row: row["label"].casefold())
        states = getattr(self, "_html_service_states", None)
        return {
            "overlays": overlays,
            "groups": [{"id": group, "label": label} for group, label, _attrs in OVERLAY_GROUPS]
                      + [{"id": "other", "label": "Other"}],
            "services": states(time.time()) if callable(states) else {},
            "music": self._tools_music(),
            "switches": [{"key": key, "label": label, "detail": detail, "home": home,
                          "on": bool(config.get(key, key in {"overlay_mouse_passthrough", "overlay_hide_on_maps",
                                                             "galnet_enabled", "achievements_enabled",
                                                             "eddn_market_upload_enabled"}))}
                         for key, label, detail, home in TOOL_SWITCHES],
            "watcher": {"voice": bool(config.get("watcher_voice_enabled")), "installed": voice_assets.installed(),
                        "thoughts": watcher_mind.frequency(config),
                        "orb": getattr(self, "heartbeat_hud", None) is not None},
            "system": str(getattr(self, "current_sys", "") or ""),
            "body": str(getattr(self, "current_body_name", "") or ""),
            "on_planet": bool(getattr(self, "on_planet", False) or getattr(self, "current_latitude", None) is not None),
            "target": {"active": bool(getattr(self, "target_latlon_active", False)),
                       "lat": getattr(self, "target_lat", None), "lon": getattr(self, "target_lon", None),
                       "label": str(getattr(self, "ground_target_label", "") or "")},
        }

    def _tools_music(self):
        status = getattr(self, "_music_status", None) or {}
        library = self.music_library() if callable(getattr(self, "music_library", None)) else None
        track = _track(library, status.get("track_id"))
        if track is None:
            return {"state": "idle"}
        return {"state": "playing" if status.get("playing") else "paused",
                "title": track["title"], "artist": track["artist"]}

    def _handle_tools_command(self, operation, payload):
        payload = payload or {}
        if operation == "overlay":
            return bool(self._html_overlay_toggle(str(payload.get("id") or "")))
        if operation == "setting":
            key = str(payload.get("key") or "")
            if key not in {row[0] for row in TOOL_SWITCHES}:
                return False
            value = bool(payload.get("value"))
            if key in STUDIO_OPTIONS:
                return bool(self._html_overlay_option_toggle(key, value))
            if key == "music_follow_game":
                return bool(self._music_follow_set(key, value))
            self.config[key] = value
            self._persist_config()
            self._apply_settings_changes({key})
            return True
        if operation == "thoughts":
            return bool(self._handle_watcher_settings_command("settings", {"values": {"heartbeat_thoughts": payload.get("value")}}))
        if operation == "voice":
            return bool(self._handle_watcher_settings_command("voice_toggle", {"value": bool(payload.get("value"))}))
        if operation == "poke":
            self._watcher_poke()
            return True
        if operation == "music":
            action = str(payload.get("action") or "")
            return bool(self.music_remote(action)) if action in {"toggle", "next", "previous"} else False
        if operation == "copy_system":
            return bool(self._html_copy_text(getattr(self, "current_sys", "")))
        if operation == "open_journal":
            path = str(self.config.get("journal_path") or "")
            return bool(path) and open_path(path)
        if operation == "open_capsules":
            folder = self.capsule_folder()
            folder.mkdir(parents=True, exist_ok=True)
            return open_path(folder)
        return False
