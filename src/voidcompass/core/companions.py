"""Companion identities and their profile-owned settings."""
from collections.abc import Mapping
import re

IDENTITIES = ("watcher", "aster")
NAMES = {"watcher": "The Watcher", "aster": "Aster"}
DISPLAY_SIZES = dict.fromkeys(IDENTITIES, (54, 72, 96, 144, 192, 256))
DISPLAY_DEFAULTS = {"watcher": 54, "aster": 144}
ASTER_KEYS = {"heartbeat_thoughts": "aster_thoughts", "watcher_voice_enabled": "aster_voice_enabled",
              "watcher_voice_volume": "aster_voice_volume", "watcher_voice_speed": "aster_voice_speed",
              "watcher_voice_level": "aster_voice_level"}


def identity(config):
    value = str((config or {}).get("companion_identity") or "watcher")
    return value if value in IDENTITIES else "watcher"


def name(config):
    return NAMES[identity(config)]


def display_size(config):
    selected = identity(config)
    try:
        value = int(float(config.get("aster_hud_size" if selected == "aster" else "heartbeat_orb_size", DISPLAY_DEFAULTS[selected])))
    except (TypeError, ValueError):
        value = DISPLAY_DEFAULTS[selected]
    return value if value in DISPLAY_SIZES[selected] else DISPLAY_DEFAULTS[selected]


def display_options(config):
    selected = identity(config)
    return {"companion_identity": selected, "companion_name": name(config), "companion_size": display_size(config),
            "companion_accent": config.get("aster_hud_accent", "theme") if selected == "aster" else config.get("heartbeat_eye_color", "theme"),
            "companion_motion": bool(config.get("aster_hud_motion", True) if selected == "aster" else config.get("heartbeat_idle_motion", True)),
            "companion_focus": config.get("aster_hud_focus" if selected == "aster" else "heartbeat_focus_movement", "tracking"),
            "companion_liveliness": config.get("aster_hud_liveliness", "standard") if selected == "aster" else config.get("heartbeat_liveliness", "standard")}


def display_key(config, setting):
    selected = identity(config)
    return {"companion_size": "aster_hud_size" if selected == "aster" else "heartbeat_orb_size",
            "companion_accent": "aster_hud_accent" if selected == "aster" else "heartbeat_eye_color",
            "companion_motion": "aster_hud_motion" if selected == "aster" else "heartbeat_idle_motion",
            "companion_focus": "aster_hud_focus" if selected == "aster" else "heartbeat_focus_movement",
            "companion_liveliness": "aster_hud_liveliness" if selected == "aster" else "heartbeat_liveliness"}[setting]


def key(config, setting):
    return ASTER_KEYS.get(setting, setting) if identity(config) == "aster" else setting


class Settings(Mapping):
    def __init__(self, source, selected):
        self.source, self.selected = source, selected

    def __getitem__(self, setting):
        if setting == "companion_identity":
            return self.selected
        if self.selected == "aster":
            if setting == "heartbeat_personality":
                return "stoic"
            setting = ASTER_KEYS.get(setting, setting)
        return self.source[setting]

    def __iter__(self):
        return iter(self._keys())

    def __len__(self):
        return len(self._keys())

    def _keys(self):
        keys = set(self.source) | {"companion_identity"}
        if self.selected == "aster":
            keys.add("heartbeat_personality")
            for alias, physical in ASTER_KEYS.items():
                if physical in self.source:
                    keys.add(alias)
                else:
                    keys.discard(alias)
        return keys


def settings(config, selected=None):
    return Settings(config, selected or identity(config))


def addressed(text, selected):
    """Use the existing command grammar after an active companion's address."""
    words = str(text or "")
    if selected == "aster":
        words = re.sub(r"^\s*(?:(?:hey|hello|hi)\s+)?aster\b\s*[,;:]?\s*", "", words, flags=re.I) if not re.match(r"^\s*(?:hello|hi|hey)\s+aster\s*[!?.]*$", words, re.I) else words
    return words


def create_mind(path, config, **kwargs):
    if identity(config) == "aster":
        from voidcompass.overlays.aster_mind import AsterMind
        return AsterMind(path, config, **kwargs)
    from voidcompass.overlays.watcher_mind import WatcherMind
    return WatcherMind(path, config, **kwargs)
