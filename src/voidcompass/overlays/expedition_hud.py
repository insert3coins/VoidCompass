"""Expedition overlay (5.6.1): the trip at a glance in the cockpit. How far
along, the next stop (and, on its planet, which way to it), the data you're
carrying, the streak, and anything running low. It shows only while an
expedition is active.

The model is shared with the Navigation HUD's EXPEDITION page, which stands
in for this overlay when the HUD's pages are on: one model, so the page
never shows less than the overlay did.
"""
from __future__ import annotations

from voidcompass.overlays.colony_needs_hud import ColonyNeedsHUD, _integer

KIND_LABELS = {"stop": "STOP", "destination": "DESTINATION", "home": "HOME", "carrier": "CARRIER JUMP"}


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def leg_name(leg):
    """A stop on a planet goes by its place's name (or the body's); others by
    the system."""
    leg = leg or {}
    return str((leg.get("note") or leg.get("body")) if leg.get("body") else leg.get("system") or "")


def build_expedition_model(expedition, live):
    if not expedition:
        return None
    live = live or {}
    progress = live.get("progress") or {}
    risk = live.get("risk") or {}
    supplies = live.get("supplies") or {}
    upcoming = progress.get("next") or {}
    surface = live.get("surface") or None
    where = ""
    if upcoming.get("body"):
        where = upcoming["body"] if upcoming.get("note") else upcoming.get("system") or ""
    return {
        "name": str(expedition.get("name") or "Expedition"),
        "ironman": bool(expedition.get("ironman")),
        "share": _number(progress.get("share")),
        "done_ly": _number(progress.get("done_ly")),
        "to_go_ly": _number(progress.get("to_go_ly")),
        "next": {"name": leg_name(upcoming), "where": str(where), "kind": KIND_LABELS.get(upcoming.get("kind"), "STOP")}
        if upcoming.get("system") else None,
        "surface": {key: surface.get(key) for key in ("title", "body", "here", "on_body", "lat", "lon", "target", "altitude_m")}
        if surface else None,
        "risk": int(_number(risk.get("value")) or 0),
        "risk_over": bool(risk.get("over")),
        "hull": _number(risk.get("hull")),
        "streak": int(_number((live.get("streak") or {}).get("jumps")) or 0),
        "eta_hours": _number((live.get("eta") or {}).get("hours")),
        "low": [str(name) for name in supplies.get("low") or ()],
        "fuel_runs": [{"jumps": int(run.get("jumps") or 0), "from": str(run.get("from") or "")}
                      for run in (upcoming.get("fuel_runs") or ())[:2]],
    }


class ExpeditionHUD(ColonyNeedsHUD):
    """Native window proxy for the semantic HTML Expedition page; it shows
    while it has a model (an expedition is active), as Construction Needs does."""

    def _position(self):
        return (_integer(self.config.get("expedition_hud_x"), 40),
                _integer(self.config.get("expedition_hud_y"), 560))

    def update_expedition(self, model):
        return self.update(model)
