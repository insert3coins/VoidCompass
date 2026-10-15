"""Your own postcard themes (5.5.4).

A theme starts from one of the four looks (its frame: Polaroid, Airmail,
Holo, Vintage) and changes what you like: the paper, ink and lettering
colours, the lettering's font, a filter over the photo, the card's angle, and
what's behind the card (a colour, or a picture of your own). Saved by name in
the commander's settings and chosen like any style ("theme:<name>"). The
overlay and saved postcards both read the same parameters.
"""
from __future__ import annotations

import io
import re

from voidcompass.core.platform_support import application_dir

BASES = ("polaroid", "airmail", "holo", "vintage")
FONTS = ("hud", "serif", "hand")
FILTERS = ("none", "sepia", "mono", "vivid", "cool")
BACKGROUNDS = ("none", "colour", "image")
NOTE_MODES = ("watcher", "own", "none")
THEMES_MAX = 20
NAME_MAX = 30
ANGLE_LIMIT = 12.0
BACKGROUND_MAX_BYTES = 6 * 1024 * 1024
BACKGROUND_SIDE = 2560
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _colour(value):
    value = str(value or "").strip()
    return value.lower() if _HEX.match(value) else ""


def clean_name(name):
    return " ".join(str(name or "").split())[:NAME_MAX]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", clean_name(name).casefold()).strip("-") or "theme"


def normalize(params):
    """A theme's parameters, each kept to its choices ("" or None: as the base)."""
    params = params if isinstance(params, dict) else {}
    try:
        angle = float(params.get("angle"))
        angle = max(-ANGLE_LIMIT, min(ANGLE_LIMIT, round(angle, 1)))
    except (TypeError, ValueError):
        angle = None
    base = str(params.get("base") or "polaroid").casefold()
    font = str(params.get("font") or "").casefold()
    photo_filter = str(params.get("filter") or "none").casefold()
    background = str(params.get("background") or "none").casefold()
    image = re.sub(r"[^a-z0-9._-]", "", str(params.get("bg_image") or "").casefold())[:80]
    return {
        "base": base if base in BASES else "polaroid",
        "paper": _colour(params.get("paper")), "ink": _colour(params.get("ink")), "greet": _colour(params.get("greet")),
        "font": font if font in FONTS else "",
        "filter": photo_filter if photo_filter in FILTERS else "none",
        "angle": angle,
        "background": background if background in BACKGROUNDS else "none",
        "bg_colour": _colour(params.get("bg_colour")),
        "bg_image": image if image.endswith(".jpg") else "",
    }


def themes(config):
    """The commander's themes: {name: params}."""
    found = (config or {}).get("postcard_themes")
    if not isinstance(found, dict):
        return {}
    return {clean_name(name): normalize(params) for name, params in list(found.items())[:THEMES_MAX] if clean_name(name)}


def chosen(config):
    """(base style, theme params or None) for the style setting."""
    style = str((config or {}).get("postcard_style") or "polaroid")
    if style.casefold().startswith("theme:"):
        name = clean_name(style[6:])
        theme = themes(config).get(name)
        if theme:
            return theme["base"], {**theme, "name": name}
    style = style.casefold()
    return (style if style in BASES else "polaroid"), None


def folder():
    """Where theme background pictures are kept, beside Void Compass."""
    return application_dir() / "postcard_themes"


def background_path(theme):
    """The theme's background picture on disk, if it has one."""
    if not theme or theme.get("background") != "image" or not theme.get("bg_image"):
        return None
    path = folder() / theme["bg_image"]
    return path if path.is_file() else None


def save_background(name, data):
    """A picture you chose for a theme's background: checked, shrunk to at most
    BACKGROUND_SIDE and kept as a JPEG. Its file name, or None."""
    if not data or len(data) > BACKGROUND_MAX_BYTES:
        return None
    try:
        from PIL import Image
        picture = Image.open(io.BytesIO(data))
        picture.load()
        picture = picture.convert("RGB")
        picture.thumbnail((BACKGROUND_SIDE, BACKGROUND_SIDE))
        target = folder()
        target.mkdir(parents=True, exist_ok=True)
        filename = f"{slug(name)}.jpg"
        picture.save(target / filename, "JPEG", quality=90)
        return filename
    except Exception:
        return None
