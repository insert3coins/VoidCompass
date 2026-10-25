"""Hatchling overlay (5.6.3): the Games page's pocket pet in a corner of the
screen while you fly. Its face, its mood, its five needs and what it wants.
It shows while there is a pet aboard (an egg counts).
"""
from __future__ import annotations

from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer

# How long a reaction (a fright, a treat) stays on its face, and a log line under it.
REACTION_S = 90
LINE_S = 600

# Its look (5.6.4): the panel, or the pet on its own on a see-through strip.
LOOKS = ("panel", "pet")
PET_SIZES = {"small": 64, "medium": 92, "large": 132}
ROAMS = {"still": 1.7, "short": 3.2, "wide": 6.0}
NEEDS_SHOWN = ("always", "low", "never")
# How often it chatters (5.6.4): never, now and then, or more.
CHATTER = ("off", "quiet", "chatty")


def hatchling_frame_rate(overall):
    """The pet's overlay draws at most 30 frames a second (5.6.4), even when
    All overlays is set higher or unlimited (0)."""
    try:
        overall = int(overall)
    except (TypeError, ValueError):
        overall = 30
    return 30 if overall <= 0 or overall > 30 else overall


def hatchling_overlay_options(config):
    config = config or {}

    def choice(key, choices, default):
        value = str(config.get(key) or default).casefold()
        return value if value in choices else default

    return {
        "look": choice("hatchling_look", LOOKS, "panel"),
        "size": choice("hatchling_pet_size", PET_SIZES, "medium"),
        "roam": choice("hatchling_roam", ROAMS, "short"),
        "needs": choice("hatchling_needs", NEEDS_SHOWN, "low"),
        "chatter": choice("hatchling_chatter", CHATTER, "quiet"),
        "speech": bool(config.get("hatchling_speech", True)),
        "glow": bool(config.get("hatchling_glow", True)),
        "sounds": bool(config.get("hatchling_sounds", False)),
    }


def hatchling_pet_window(config):
    """The pet-only window: wide enough to roam, tall enough for its bubbles.
    None for the panel, which sizes itself to its content."""
    options = hatchling_overlay_options(config)
    if options["look"] != "pet":
        return None
    pet = PET_SIZES[options["size"]]
    return round(pet * ROAMS[options["roam"]]), round(pet * 1.7)


def build_hatchling_model(view, now, music=False, options=None, watcher=None):
    pet = (view or {}).get("pet")
    if not pet:
        return None
    reaction_at = float(pet.get("reaction_at") or 0)
    latest = (pet.get("log") or [None])[0] or {}
    fresh_line = latest.get("text") if now - float(latest.get("at") or 0) < LINE_S else ""
    return {
        "name": str(pet.get("name") or ""),
        "species": pet.get("species"), "kind": pet.get("kind") or "", "stage": pet.get("stage"), "form": pet.get("form") or "",
        "title": str(pet.get("form_name") or pet.get("kind_name") or pet.get("species_name") or "").upper(),
        "mood_word": pet.get("mood_word") or "", "wants": pet.get("wants") or "",
        "needs": dict(pet.get("needs") or {}), "food_label": pet.get("food_label") or "HUNGER",
        "asleep": bool(pet.get("asleep")), "sick": bool(pet.get("sick")), "dormant": bool(pet.get("dormant")),
        "mess": int(pet.get("mess") or 0), "hatch_minutes": int(pet.get("hatch_minutes") or 0),
        "reaction": pet.get("reaction") if now - reaction_at < REACTION_S else "",
        "line": str(fresh_line or ""),
        # Its life on its own (5.6.4): what to act out, its toys and tricks, its dreams, your music.
        "cue": pet.get("cue"), "place": pet.get("place") or "space", "low_fuel": bool(pet.get("low_fuel")),
        "trait": pet.get("trait") or "", "traits": dict(pet.get("traits") or {}),
        "toys": list(pet.get("toys") or []), "tricks": list(pet.get("tricks") or []),
        "dreams": list(pet.get("dreams") or []), "music": bool(music),
        "world": pet.get("world"), "welcome": pet.get("welcome"), "outfit": pet.get("outfit") or "", "chat": pet.get("chat"),
        "options": dict(options or hatchling_overlay_options({})), "watcher": watcher,
    }


class HatchlingHUD(ColonyNeedsHUD):
    """Native window proxy for the HTML Hatchling page; it shows while it
    has a model (a pet is aboard), as Construction Needs does."""

    def _position(self):
        return (_integer(self.config.get("hatchling_hud_x"), 1660),
                _integer(self.config.get("hatchling_hud_y"), 860))

    def update_hatchling(self, model):
        return self.update(model)
