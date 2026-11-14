"""Color themes for VoidCompass.

Standalone (stdlib-only) so both config.py and ui_theme.py can import it
without cycles. The active theme is resolved ONCE at import time, before any
UI module binds its color constants. The live theme bridge rebinds loaded
modules and explicitly repaints open overlays when Settings is saved.

Profile-aware: the theme name and any custom themes live in the active
commander profile's config (profiles/<key>/config.json), so each commander
keeps their own look. The root config.json only tells us which profile is
active.
"""

import json
import re
from pathlib import Path
from voidcompass.core.platform_support import application_dir

# Every color slot a theme defines. The first group feeds ui_theme.Palette;
# bg/panel/accent/orange/text/green also feed config.COLOR_* (overlays).
THEME_KEYS = (
    "bg", "panel", "panel_alt", "panel_raised", "header", "input", "inset",
    "border", "border_soft", "selection", "accent", "orange", "text",
    "muted", "dim", "green", "yellow", "red",
)

DEFAULT_THEME_NAME = "Void Cyan"

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def is_hex_color(value):
    return bool(_HEX_RE.match(str(value or "")))


def _lerp(a, b, t):
    """Blend two #rrggbb colors."""
    ar, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    br, bg_, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(
        round(ar + (br - ar) * t), round(ag + (bg_ - ag) * t), round(ab + (bb - ab) * t)
    )


def _derive(bg, accent, orange, text, green, yellow, red):
    """Build a full palette from seven seed colors: the neutral shades are
    blends of bg->text, selection is a bg->accent tint. Keeps the built-in
    definitions compact while staying tonally coherent per theme."""
    return {
        "bg": bg,
        "panel": _lerp(bg, text, 0.035),
        "panel_alt": _lerp(bg, text, 0.065),
        "panel_raised": _lerp(bg, text, 0.10),
        "header": _lerp(bg, text, 0.018),
        "input": _lerp(bg, text, 0.028),
        "inset": _lerp(bg, text, 0.032),
        "border": _lerp(bg, text, 0.22),
        "border_soft": _lerp(bg, text, 0.13),
        "selection": _lerp(bg, accent, 0.20),
        "accent": accent,
        "orange": orange,
        "text": text,
        "muted": _lerp(bg, text, 0.62),
        "dim": _lerp(bg, text, 0.42),
        "green": green,
        "yellow": yellow,
        "red": red,
    }


BUILTIN_THEMES = {
    # The default is the app's original hand-tuned palette, kept exactly.
    "Void Cyan": {
        "bg": "#070b10", "panel": "#0d141c", "panel_alt": "#111b25",
        "panel_raised": "#16222d", "header": "#0a1017", "input": "#091018",
        "inset": "#0a1118", "border": "#243746", "border_soft": "#192a36",
        "selection": "#12313c", "accent": "#00d1ff", "orange": "#ff8a3d",
        "text": "#dcebf3", "muted": "#91a8b7", "dim": "#607584",
        "green": "#54e39a", "yellow": "#f5c76d", "red": "#ff6b70",
    },
    "Elite Orange": _derive("#100b06", "#ff7100", "#ffb000", "#f2e6d8", "#7ddb6f", "#ffd166", "#ff5c5c"),
    "Emerald": _derive("#06100a", "#00e88a", "#b8e04d", "#dcf3e6", "#54e39a", "#e0d84d", "#ff6b70"),
    "Amber Terminal": _derive("#0f0c05", "#ffbf00", "#ff8a3d", "#f0e6d2", "#a8d84d", "#ffd166", "#ff5c5c"),
    "Ice": _derive("#0a0e14", "#a8d8ff", "#6ea8dc", "#e6f0f8", "#8fd8b8", "#e8d8a0", "#ff8a90"),
    "Synthwave": _derive("#120718", "#ff4fd8", "#00e5ff", "#f0dcf3", "#54e39a", "#f5c76d", "#ff5c7a"),
    "Crimson": _derive("#120709", "#ff4757", "#ff9f43", "#f3dcdf", "#6fdb8f", "#ffd166", "#ff6b70"),
    "Solar Gold": _derive("#0f0d06", "#ffd166", "#ef8354", "#f2ecd8", "#a8d84d", "#ffe08a", "#ff6b70"),
    "Nebula Purple": _derive("#0c0714", "#b388ff", "#ff8ad8", "#e8dcf3", "#7fe0a8", "#e8cf8a", "#ff6b8a"),
    "Graphite": _derive("#0b0d0f", "#c8d6e5", "#8395a7", "#e4e9ee", "#8fd8a8", "#d8cfa0", "#e58f95"),
}


def _skinned(bg, panel, line, text, muted, accent, orange, green, yellow, red):
    """A skin's palette in our slots, from its own panel and line colours."""
    return {
        "bg": bg, "panel": panel, "panel_alt": _lerp(panel, line, 0.25), "panel_raised": _lerp(panel, line, 0.45),
        "header": _lerp(bg, panel, 0.5), "input": _lerp(bg, panel, 0.7), "inset": _lerp(bg, panel, 0.8),
        "border": line, "border_soft": _lerp(bg, line, 0.6), "selection": _lerp(bg, accent, 0.20),
        "accent": accent, "orange": orange, "text": text, "muted": muted, "dim": _lerp(bg, muted, 0.6),
        "green": green, "yellow": yellow, "red": red,
    }


# Skins (5.8.1): a palette and a whole look besides, its own fonts, case and
# corner shapes (web/assets/skins/). Theme name -> skin id.
SKIN_THEMES = {
    "Cockpit HUD": ("cockpit", _skinned("#000000", "#120a02", "#5a3000", "#ffa040", "#c8732a", "#ff7a00", "#ffa040", "#3fc8f4", "#ffc400", "#ff3b30")),
    "Starliner": ("starliner", _skinned("#000000", "#120e1a", "#2a2238", "#f4e9da", "#b9a6c6", "#ff9933", "#ffcc99", "#99dd99", "#ffb000", "#ff6666")),
    "Station Blue": ("station", _skinned("#050b14", "#0b1726", "#22405f", "#d8e6f2", "#8fa3b8", "#6fd3ff", "#ffb020", "#7fe0b0", "#ffb020", "#ff6b5e")),
    "Imperial Gold": ("imperial", _skinned("#12080f", "#22101c", "#4a2440", "#f3e6c8", "#c2a98a", "#d4af37", "#f0c14b", "#b8d88a", "#f0c14b", "#ff6f7f")),
    "Crystal": ("crystal", _skinned("#0f0c1c", "#1a1630", "#3a3260", "#ece7f6", "#a79fc4", "#b7a3e6", "#7fd1c4", "#7fd1c4", "#f2c46d", "#ff8fa3")),
    "Ember": ("ember", _skinned("#120806", "#22100b", "#4e2216", "#e8c9a0", "#b8957a", "#e0a040", "#ffc24b", "#c8d27a", "#ffc24b", "#ff7a5c")),
    "Umbral": ("umbral", _skinned("#060409", "#140b20", "#2f1d4a", "#d6d3dd", "#9c95aa", "#a57be6", "#cdbdf2", "#8fd6a8", "#f0b44c", "#ff6b7d")),
    "Obsidian Red": ("obsidian", _skinned("#000000", "#0a0a0b", "#2a2d33", "#c9ced6", "#8b919b", "#e8e8e8", "#ff4255", "#9fd4c0", "#ffb000", "#ff5a6a")),
    "Verdigris": ("verdigris", _skinned("#06110d", "#0d1e18", "#22453a", "#e2efe6", "#93b3a5", "#e6cf6a", "#5fb596", "#8edba8", "#e6cf6a", "#ff8c7a")),
    "Ochre Squadron": ("ochre", _skinned("#0b0f14", "#141a22", "#2a3442", "#f2ebdd", "#a9a08a", "#f28c28", "#f2c94c", "#8fd08a", "#f2c94c", "#f05a4e")),
    "Midnight": ("midnight", _skinned("#121417", "#1c1f24", "#2e333b", "#e6e8eb", "#9aa3ae", "#4f8cff", "#f5b94a", "#3dd68c", "#f5b94a", "#ff6b6b")),
}
BUILTIN_THEMES.update({name: palette for name, (_skin, palette) in SKIN_THEMES.items()})


def theme_skin(theme_name):
    """The skin a theme carries ("" for a palette-only theme, custom ones included)."""
    entry = SKIN_THEMES.get(str(theme_name or ""))
    return entry[0] if entry else ""


def normalize_theme(colors, base=None):
    """Return a full valid palette: unknown/invalid slots fall back to `base`
    (default: the Void Cyan builtin)."""
    fallback = dict(base or BUILTIN_THEMES[DEFAULT_THEME_NAME])
    out = {}
    colors = colors or {}
    for key in THEME_KEYS:
        value = colors.get(key)
        out[key] = value if is_hex_color(value) else fallback[key]
    return out


def resolve_theme(theme_name=None, custom_themes=None):
    """Return a valid theme name and palette from one profile's settings."""
    name = str(theme_name or DEFAULT_THEME_NAME)
    custom = custom_themes if isinstance(custom_themes, dict) else {}
    if name in BUILTIN_THEMES:
        return name, dict(BUILTIN_THEMES[name])
    if name in custom and isinstance(custom.get(name), dict):
        return name, normalize_theme(custom[name])
    return DEFAULT_THEME_NAME, dict(BUILTIN_THEMES[DEFAULT_THEME_NAME])


# ---------- startup resolution (profile-aware, no app imports) ----------


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def resolve_startup_theme():
    """(name, palette) for the active commander profile, resolved from disk.

    Mirrors config.py's file layout without importing it: root config.json
    holds active_commander_profile; the profile's own config.json holds
    ui_theme_name and ui_custom_themes.
    """
    base = application_dir()
    root_cfg = _read_json(base / "config.json")
    profile_key = str(root_cfg.get("active_commander_profile") or "").strip()
    profile_cfg = _read_json(base / "profiles" / profile_key / "config.json") if profile_key else {}

    name = profile_cfg.get("ui_theme_name") or root_cfg.get("ui_theme_name") or DEFAULT_THEME_NAME
    custom = profile_cfg.get("ui_custom_themes") or root_cfg.get("ui_custom_themes") or {}

    return resolve_theme(name, custom)


ACTIVE_THEME_NAME, ACTIVE_PALETTE = resolve_startup_theme()
