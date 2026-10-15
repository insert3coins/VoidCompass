"""Your home system (5.5.4): Sol unless you set another in Settings.

Distances "from home" (the Watcher's remarks, the Galaxy Minimap's strip and
marker) are measured from here. The system's coordinates are looked up once
when it's set: from your own travel history first, else EDSM.
"""
from __future__ import annotations

import math

SOL = "Sol"


def _position(value):
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return [float(value[0]), float(value[1]), float(value[2])]
        except (TypeError, ValueError):
            return None
    return None


def home(config):
    """{"name", "pos", "custom"}: the home you set once its coordinates are
    known, otherwise Sol."""
    config = config or {}
    name = str(config.get("home_system") or "").strip()
    pos = _position(config.get("home_system_pos"))
    if name and name.casefold() != SOL.casefold() and pos is not None:
        return {"name": name, "pos": pos, "custom": True}
    return {"name": SOL, "pos": [0.0, 0.0, 0.0], "custom": False}


def distance(position, config):
    """Light years from home to ``position`` ([x, y, z]), or None."""
    here = _position(position)
    if here is None:
        return None
    anchor = home(config)["pos"]
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(here, anchor)))


def from_history(rows, name):
    """A system's coordinates from your own travel history rows
    ([timestamp, system, x, y, z, ...]), newest first, or None."""
    wanted = str(name or "").strip().casefold()
    if not wanted:
        return None
    for row in reversed(list(rows or ())):
        try:
            if str(row[1]).casefold() == wanted:
                return _position(row[2:5])
        except (IndexError, TypeError):
            continue
    return None
