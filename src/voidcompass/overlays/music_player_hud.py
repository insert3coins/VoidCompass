"""MusicPlayerHUD — what is playing, shown in the cockpit.

The dashboard page plays the music and reports what it is doing; this class
keeps the overlay's model: the track and its tags, what comes next, where it
is and whether it is playing, and the options chosen in Overlay Studio. The
overlay only shows the music; it never plays it. web/music_player draws it,
its visualizer fed live levels from the playing page.
"""

import time

from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.core import themes
from voidcompass.overlays import overlay_chrome

# Card: the cover beside the track, the visualizer and progress beneath.
# Strip: one slim line for the top or bottom edge of the screen.
MUSIC_LAYOUTS = {"card": (460, 136), "strip": (580, 44)}
# Skins (5.5.3.3): ten looks for the card, each its own size (design px,
# before the up-next line). On the slim strip a skin sets its colours.
MUSIC_SKINS = {
    "deck": ("Command Deck", (460, 136)),
    "glass": ("Glass", (460, 140)),
    "vinyl": ("Vinyl", (480, 140)),
    "cassette": ("Cassette", (400, 196)),
    "cockpit": ("Cockpit HUD", (480, 132)),
    "terminal": ("Terminal", (470, 150)),
    "orb": ("Orb", (440, 156)),
    "radio": ("Radio dial", (480, 150)),
    "minimal": ("Minimal", (440, 84)),
    "neon": ("Neon", (470, 148)),
}
MUSIC_VISUALIZERS = ("bars", "mirror", "wave", "off")
MUSIC_COLOURS = ("theme", "warm", "spectrum")
# Seconds paused before the overlay hides itself; 0 keeps it up.
MUSIC_AUTO_HIDE = (0, 10, 30, 120)
NEXT_LINE = 18


def _integer(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def music_overlay_options(config):
    """The overlay's Overlay Studio options, each within its allowed values."""
    config = config or {}
    layout = str(config.get("music_player_layout") or "card").casefold()
    visualizer = str(config.get("music_player_visualizer") or "bars").casefold()
    colour = str(config.get("music_player_colour") or "theme").casefold()
    hide = _integer(config.get("music_player_auto_hide"), 0)
    skin = str(config.get("music_player_skin") or "deck").casefold()
    text_scale = _integer(config.get("music_player_text_scale_percent"), 0)
    return {
        "layout": layout if layout in MUSIC_LAYOUTS else "card",
        "skin": skin if skin in MUSIC_SKINS else "deck",
        "visualizer": visualizer if visualizer in MUSIC_VISUALIZERS else "bars",
        "colour": colour if colour in MUSIC_COLOURS else "theme",
        "show_art": bool(config.get("music_player_show_art", True)),
        "show_details": bool(config.get("music_player_show_details", True)),
        "show_next": bool(config.get("music_player_show_next", True)),
        "auto_hide": hide if hide in MUSIC_AUTO_HIDE else 0,
        # The overlay's own text size; 0 follows the size set for all overlays.
        "text_scale_percent": 0 if text_scale <= 0 else max(75, min(200, text_scale)),
    }


def music_text_scale(config):
    """The overlay's text size as a factor: its own, else all overlays' size."""
    own = music_overlay_options(config)["text_scale_percent"]
    chosen = own if own > 0 else _integer((config or {}).get("overlay_text_scale_percent"), 100)
    return max(75, min(200, chosen)) / 100.0


def music_overlay_size(config):
    """The window: its layout's size, the card taller for its up-next line."""
    options = music_overlay_options(config)
    width, height = MUSIC_LAYOUTS[options["layout"]]
    if options["layout"] == "card":
        width, height = MUSIC_SKINS[options["skin"]][1]
    if options["layout"] == "card" and options["show_next"]:
        height += NEXT_LINE
    scale = music_text_scale(config)
    return round(width * scale), round(height * scale)


def _track(library, identifier):
    track = library.track(identifier) if library is not None and identifier else None
    if not track:
        return None
    fields = ("title", "artist", "album", "year", "genre", "format")
    return {"id": str(identifier), "duration": float(track.get("duration") or 0),
            **{field: str(track.get(field) or "")[:200] for field in fields}}


class MusicPlayerHUD:

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._status = {}
        self._library = None
        self._idle_since = time.monotonic()
        self._html_render_model = {}
        self._rebuild()
        self.win = OverlayWindowState(root)
        x = self._safe_int(config.get("music_player_hud_x"), 40)
        y = self._safe_int(config.get("music_player_hud_y"), 880)
        self.win.geometry(overlay_chrome.position_geometry(x, y))

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(float(value))
        except Exception:
            return int(default)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass

    def update(self, status, library):
        """The player's latest report, and the library to name its tracks from."""
        was_playing = bool(self._status.get("playing"))
        self._status = dict(status or {})
        self._library = library
        if was_playing and not self._status.get("playing"):
            self._idle_since = time.monotonic()
        self._rebuild()

    def apply_settings(self):
        """Overlay Studio changed the overlay's options."""
        self._rebuild()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)

    def hidden_while_idle(self):
        """True once the music has been paused longer than the auto-hide."""
        wait = music_overlay_options(self.config)["auto_hide"]
        if not wait or self._status.get("playing"):
            return False
        return time.monotonic() - self._idle_since >= wait

    def _rebuild(self):
        options = music_overlay_options(self.config)
        status, library = self._status, self._library
        track = _track(library, status.get("track_id"))
        following = _track(library, status.get("next_id")) if options["show_next"] else None
        playlist = library.playlist(status.get("playlist_id")) if library is not None else None
        if track is None:
            state = "idle"
        elif status.get("blocked"):
            state = "blocked"
        else:
            state = "playing" if status.get("playing") else "paused"
        if track and not track["duration"]:
            track["duration"] = float(status.get("duration") or 0)
        self._html_render_model = {
            "state": state,
            "track": track,
            "next": {"title": following["title"], "artist": following["artist"]} if following else None,
            "playlist": str((playlist or {}).get("name") or "")[:80],
            "position": max(0.0, float(status.get("position") or 0)),
            "reported_at": float(status.get("reported_at") or 0),
            "shuffle": bool(status.get("shuffle")),
            "repeat": str(status.get("repeat") or "all"),
            "art": library.overlay_art(track["id"]) if track and options["show_art"] and library else "",
            "options": options,
        }
