"""Companion identities and their profile-owned settings."""
from collections.abc import Mapping
import re

PROFILES = {
    "watcher": {"name": "The Watcher", "role": "Journal companion", "description": "Patient company · an ancient eye", "story": True},
    "aster": {"name": "Aster", "role": "Manifest officer", "description": "Ship’s officer · precision and dry wit", "story": True},
    "axiom": {"name": "Axiom", "role": "Survey intelligence", "description": "Survey intelligence · precise and curious", "story": True},
    "meridian": {"name": "Meridian", "role": "Veteran navigator", "description": "Old navigator · measured and steady", "story": True},
}
IDENTITIES = tuple(PROFILES)
NEW_IDENTITIES = ("axiom", "meridian")
NAMES = {key: row["name"] for key, row in PROFILES.items()}
DISPLAY_SIZES = dict.fromkeys(IDENTITIES, (54, 72, 96, 144, 192, 256))
DISPLAY_DEFAULTS = {"watcher": 54, "aster": 144, "axiom": 144, "meridian": 144}
ASTER_KEYS = {"heartbeat_thoughts": "aster_thoughts", "watcher_voice_enabled": "aster_voice_enabled",
              "watcher_voice_volume": "aster_voice_volume", "watcher_voice_speed": "aster_voice_speed",
              "watcher_voice_level": "aster_voice_level"}


def aliases(selected):
    if selected == "watcher":
        return {}
    return {key: value.replace("aster_", selected + "_", 1) for key, value in ASTER_KEYS.items()}


def pending_story(config):
    return not PROFILES[identity(config)]["story"]


def humour_key(config):
    """The active persona's commentary setting (the Watcher uses its nature)."""
    selected = identity(config)
    return None if selected == "watcher" else f"{selected}_humour"


def new_defaults():
    values = {}
    for selected in NEW_IDENTITIES:
        values.update({f"{selected}_thoughts": "occasional", f"{selected}_hud_accent": "signature",
                       f"{selected}_hud_liveliness": "standard", f"{selected}_hud_focus": "tracking",
                       f"{selected}_voice_speed": "standard", f"{selected}_voice_level": "every",
                       f"{selected}_voice_enabled": False, f"{selected}_hud_motion": True,
                       f"{selected}_voice_volume": 80, f"{selected}_hud_size": 144,
                       f"{selected}_humour": "dry"})
    return values


NEW_TEXT_KEYS = tuple(key for key, value in new_defaults().items() if isinstance(value, str))
NEW_BOOL_KEYS = tuple(key for key, value in new_defaults().items() if isinstance(value, bool))
NEW_VALUE_KEYS = tuple(key for key, value in new_defaults().items() if type(value) is int)


def identity(config):
    value = str((config or {}).get("companion_identity") or "watcher")
    return value if value in IDENTITIES else "watcher"


def name(config):
    return NAMES[identity(config)]


def display_size(config):
    selected = identity(config)
    try:
        value = int(float(config.get(f"{selected}_hud_size" if selected != "watcher" else "heartbeat_orb_size", DISPLAY_DEFAULTS[selected])))
    except (TypeError, ValueError):
        value = DISPLAY_DEFAULTS[selected]
    return value if value in DISPLAY_SIZES[selected] else DISPLAY_DEFAULTS[selected]


def display_options(config):
    selected = identity(config)
    return {"companion_identity": selected, "companion_name": name(config), "companion_size": display_size(config),
            "companion_accent": display_accent(config),
            "companion_motion": bool(config.get(f"{selected}_hud_motion", True) if selected != "watcher" else config.get("heartbeat_idle_motion", True)),
            "companion_focus": _choice(config.get(f"{selected}_hud_focus" if selected != "watcher" else "heartbeat_focus_movement"),
                                       ("off", "tracking", "expressive"), "tracking"),
            "companion_liveliness": _choice(config.get(f"{selected}_hud_liveliness") if selected != "watcher" else config.get("heartbeat_liveliness"),
                                            ("calm", "standard", "alive"), "standard")}


def _choice(value, allowed, default):
    # Saved values from older or hand-edited configs fall back safely.
    return value if value in allowed else default


def accent_choices(selected):
    return ("theme", "cyan", "brass", "hal") if selected == "watcher" else ("signature", "theme", "cyan", "brass")


def normalize_accent(selected, value):
    # Legacy non-Watcher red selections now use the companion's own palette.
    if selected != "watcher" and value == "hal":
        value = "signature"
    return value if value in accent_choices(selected) else "theme" if selected == "watcher" else "signature"


def display_accent(config):
    selected = identity(config)
    key = "heartbeat_eye_color" if selected == "watcher" else f"{selected}_hud_accent"
    return normalize_accent(selected, config.get(key))


def display_key(config, setting):
    selected = identity(config)
    return {"companion_size": f"{selected}_hud_size" if selected != "watcher" else "heartbeat_orb_size",
            "companion_accent": f"{selected}_hud_accent" if selected != "watcher" else "heartbeat_eye_color",
            "companion_motion": f"{selected}_hud_motion" if selected != "watcher" else "heartbeat_idle_motion",
            "companion_focus": f"{selected}_hud_focus" if selected != "watcher" else "heartbeat_focus_movement",
            "companion_liveliness": f"{selected}_hud_liveliness" if selected != "watcher" else "heartbeat_liveliness"}[setting]


def key(config, setting):
    return aliases(identity(config)).get(setting, setting)


class Settings(Mapping):
    def __init__(self, source, selected):
        self.source, self.selected = source, selected

    def __getitem__(self, setting):
        if setting == "companion_identity":
            return self.selected
        if self.selected != "watcher":
            if setting == "heartbeat_personality":
                return "stoic"
            setting = aliases(self.selected).get(setting, setting)
        return self.source[setting]

    def __iter__(self):
        return iter(self._keys())

    def __len__(self):
        return len(self._keys())

    def _keys(self):
        keys = set(self.source) | {"companion_identity"}
        if self.selected != "watcher":
            keys.add("heartbeat_personality")
            for alias, physical in aliases(self.selected).items():
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
    if selected in IDENTITIES and selected != "watcher":
        address = re.escape(NAMES[selected])
        words = re.sub(r"^\s*(?:(?:hey|hello|hi)\s+)?" + address + r"\b\s*[,;:]?\s*", "", words, flags=re.I) if not re.match(r"^\s*(?:hello|hi|hey)\s+" + address + r"\s*[!?.]*$", words, re.I) else words
        if selected in NEW_IDENTITIES and re.fullmatch(r"\s*(?:hello|hi|hey)\s+" + address + r"\s*[!?.]*\s*", words, re.I):
            words = "hello"
    return words


def create_mind(path, config, **kwargs):
    if identity(config) in NEW_IDENTITIES:
        from voidcompass.overlays.crew_mind import CrewMind
        return CrewMind(path, config, **kwargs)
    if identity(config) == "aster":
        from voidcompass.overlays.aster_mind import AsterMind
        return AsterMind(path, config, **kwargs)
    from voidcompass.overlays.watcher_mind import WatcherMind
    return WatcherMind(path, config, **kwargs)
