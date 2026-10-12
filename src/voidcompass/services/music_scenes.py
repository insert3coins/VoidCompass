"""Music that flies with you (5.5.3.8): what the game is doing, as a scene
the Music player can pick a playlist for.

From Status.json's flags (and the population of the system you're in, from
the last jump): docked (in the ship or on foot in a station), on the surface
(landed, in an SRV, on foot on a planet), combat (in danger, or being
interdicted), deep space (flying where nobody lives) or space (flying
anywhere else). In hyperspace the music ducks instead of changing.
"""
from __future__ import annotations

SCENES = ("docked", "space", "deep", "surface", "combat")
SCENE_NAMES = {"docked": "Docked", "space": "Space", "deep": "Deep space", "surface": "Surface", "combat": "Combat"}

# Status.json Flags
DOCKED = 1 << 0
LANDED = 1 << 1
SUPERCRUISE = 1 << 4
IN_DANGER = 1 << 22
BEING_INTERDICTED = 1 << 23
IN_SRV = 1 << 26
FSD_JUMP = 1 << 30
# Status.json Flags2
ON_FOOT_IN_STATION = 1 << 3
ON_FOOT_ON_PLANET = 1 << 4
ON_FOOT_IN_HANGAR = 1 << 13
ON_FOOT_SOCIAL_SPACE = 1 << 14

FADES = (1, 2, 4, 6)


def scene_of(flags, flags2=0, population=None):
    """{"scene", "jumping"} for these flags; scene "" when the game says
    nothing yet (no Status.json)."""
    try:
        flags, flags2 = int(flags or 0), int(flags2 or 0)
    except (TypeError, ValueError):
        flags, flags2 = 0, 0
    jumping = bool(flags & FSD_JUMP)
    if not flags and not flags2:
        return {"scene": "", "jumping": False}
    if flags & (IN_DANGER | BEING_INTERDICTED):
        scene = "combat"
    elif flags & DOCKED or flags2 & (ON_FOOT_IN_STATION | ON_FOOT_IN_HANGAR | ON_FOOT_SOCIAL_SPACE):
        scene = "docked"
    elif flags & (LANDED | IN_SRV) or flags2 & ON_FOOT_ON_PLANET:
        scene = "surface"
    elif population is not None and _whole(population) == 0:
        scene = "deep"
    else:
        scene = "space"
    return {"scene": scene, "jumping": jumping}


def _whole(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def follow_settings(config):
    """The Music page's Follow the game settings."""
    config = config or {}
    chosen = config.get("music_scene_playlists")
    playlists = {scene: str(chosen.get(scene) or "")[:40] for scene in SCENES} if isinstance(chosen, dict) else {
        scene: "" for scene in SCENES}
    try:
        fade = int(float(config.get("music_follow_fade_s", 2)))
    except (TypeError, ValueError):
        fade = 2
    return {
        "on": bool(config.get("music_follow_game", False)),
        "playlists": playlists,
        "fade_s": fade if fade in FADES else 2,
        "duck": bool(config.get("music_jump_duck", True)),
    }
