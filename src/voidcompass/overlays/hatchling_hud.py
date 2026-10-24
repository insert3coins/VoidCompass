"""Hatchling overlay (5.6.3): the Games page's pocket pet in a corner of the
screen while you fly. Its face, its mood, its five needs and what it wants.
It shows while there is a pet aboard (an egg counts).
"""
from __future__ import annotations

from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer

# How long a reaction (a fright, a treat) stays on its face, and a log line under it.
REACTION_S = 90
LINE_S = 600


def build_hatchling_model(view, now):
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
    }


class HatchlingHUD(ColonyNeedsHUD):
    """Native window proxy for the HTML Hatchling page; it shows while it
    has a model (a pet is aboard), as Construction Needs does."""

    def _position(self):
        return (_integer(self.config.get("hatchling_hud_x"), 1660),
                _integer(self.config.get("hatchling_hud_y"), 860))

    def update_hatchling(self, model):
        return self.update(model)
