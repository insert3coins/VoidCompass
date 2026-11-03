"""Companion identities and their profile-owned settings."""
from collections.abc import Mapping
import re

IDENTITIES = ("watcher", "aster")
NAMES = {"watcher": "The Watcher", "aster": "Aster"}
ASTER_KEYS = {"heartbeat_thoughts": "aster_thoughts", "watcher_voice_enabled": "aster_voice_enabled",
              "watcher_voice_volume": "aster_voice_volume", "watcher_voice_speed": "aster_voice_speed",
              "watcher_voice_level": "aster_voice_level"}


def identity(config):
    value = str((config or {}).get("companion_identity") or "watcher")
    return value if value in IDENTITIES else "watcher"


def name(config):
    return NAMES[identity(config)]


def key(config, setting):
    return ASTER_KEYS.get(setting, setting) if identity(config) == "aster" else setting


class Settings(Mapping):
    def __init__(self, source, selected):
        self.source, self.selected = source, selected

    def __getitem__(self, setting):
        if self.selected == "aster":
            if setting == "heartbeat_personality":
                return "stoic"
            setting = ASTER_KEYS.get(setting, setting)
        return self.source[setting]

    def __iter__(self):
        return iter(set(self.source) | set(ASTER_KEYS))

    def __len__(self):
        return len(set(self.source) | set(ASTER_KEYS))


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
