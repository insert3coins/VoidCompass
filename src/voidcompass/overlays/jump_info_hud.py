"""Jump Info: the system a hyperspace jump is heading for (5.5.1.5).

Shown while the frame shift drive charges and through witch space, as
SrvSurvey's jump panel does: the next system and its star, where the jump
sits on the plotted route, who discovered the system and when EDSM last
updated it, its traffic, bodies and ports, and the region being entered.
Everything comes from the journal, NavRoute.json or EDSM; nothing is guessed.
"""
from __future__ import annotations

import datetime as _datetime
import math

from voidcompass.core.application_runtime import OverlayWindowState
from voidcompass.core import themes
from voidcompass.overlays import overlay_chrome

WIDTH = 560
LINGER_CHOICES = (0, 5, 10, 20, 30)
_SCOOPABLE = frozenset("OBAFGKM")
_WHITE_DWARF_PREFIX = "D"


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def elite_date(value):
    """EDSM's '2022-04-04 12:00:00' (UTC) as Elite writes dates: 4 APR 3308.

    Returns ``(text, datetime)``; ``("", None)`` when the value is no date.
    """
    text = str(value or "").strip().replace("T", " ")
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            moment = _datetime.datetime.strptime(text[:length], fmt)
        except ValueError:
            continue
        return f"{moment.day} {moment.strftime('%b').upper()} {moment.year + 1286}", moment
    return "", None


def linger_seconds(config):
    """How long Jump Info stays up after arrival (0: it goes as you arrive)."""
    value = _integer((config or {}).get("jump_info_linger_s"), 0)
    return value if value in LINGER_CHOICES else 0


def star_kind(star_class):
    """``{'class', 'label', 'tone'}`` for a journal StarClass, or None."""
    code = str(star_class or "").strip()
    if not code:
        return None
    base = code.split("_", 1)[0]
    if base == "N":
        label, tone = "NEUTRON STAR", "accent"
    elif base == "H" or base == "SupermassiveBlackHole":
        label, tone = "BLACK HOLE", "red"
    elif base.startswith(_WHITE_DWARF_PREFIX):
        label, tone = "WHITE DWARF", "yellow"
    elif base in _SCOOPABLE:
        # One letter only: AeBe (Herbig) starts with A but is not scoopable.
        label, tone = "SCOOPABLE", "green"
    else:
        label, tone = "NOT SCOOPABLE", "orange"
    return {"class": code[:24], "label": label, "tone": tone}


def _position(entry):
    try:
        values = tuple(float(value) for value in (entry or {}).get("StarPos") or ())
    except (TypeError, ValueError):
        return None
    return values[:3] if len(values) >= 3 else None


def route_plan(entries, target_name, target_address=None):
    """Where the jump sits on the plotted route (NavRoute.json).

    The route's first entry is the system it was plotted from; each later
    entry is a hop. None when the target is not on the route.
    """
    entries = [entry for entry in entries or () if isinstance(entry, dict)]
    name = str(target_name or "").strip().casefold()
    index = next((
        number for number, entry in enumerate(entries)
        if number and (
            (target_address and entry.get("SystemAddress") == target_address)
            or (name and str(entry.get("StarSystem") or "").strip().casefold() == name))
    ), None)
    if index is None:
        return None
    segments = []
    total = 0.0
    for number in range(1, len(entries)):
        start, end = _position(entries[number - 1]), _position(entries[number])
        distance = math.dist(start, end) if start and end else None
        total += distance or 0.0
        kind = star_kind(entries[number].get("StarClass"))
        segments.append({
            "ly": None if distance is None else round(distance, 2),
            "scoop": bool(kind and kind["tone"] == "green"),
            "neutron": bool(kind and kind["label"] == "NEUTRON STAR"),
            "state": "behind" if number < index else "next" if number == index else "ahead",
        })
    jump = segments[index - 1]["ly"]
    return {
        "hop": index,
        "hops": len(entries) - 1,
        "remaining": len(entries) - 1 - index,
        "jump_ly": jump,
        "total_ly": round(total, 1),
        "destination": str(entries[-1].get("StarSystem") or ""),
        "segments": segments,
        "position": _position(entries[index]),
        "star_class": str(entries[index].get("StarClass") or ""),
    }


def _count(value, word, plural=None):
    return f"{value} {word if value == 1 else plural or word + 'S'}"


def intel_lines(intel):
    """EDSM's facts as display lines: ``[{key, tone, source, items}]``."""
    if intel is None:
        return [{"key": "edsm", "tone": "dim", "source": "", "items": [{"label": "EDSM", "value": "QUERYING..."}]}]
    if not intel.get("available", True):
        return [{"key": "edsm", "tone": "dim", "source": "", "items": [{"label": "EDSM", "value": "UNAVAILABLE"}]}]
    if not intel.get("known"):
        return [{"key": "edsm", "tone": "accent", "source": "EDSM",
                 "items": [{"label": "NOT LOGGED", "value": "NO COMMANDER HAS REPORTED IT"}]}]
    lines = []
    history = []
    commander = str(intel.get("discovered_by") or "").strip()
    discovered, discovered_at = elite_date(intel.get("discovered_at"))
    if commander:
        history.append({"label": "DISCOVERED BY", "value": commander.upper() + (f" · {discovered}" if discovered else "")})
    updated, updated_at = elite_date(intel.get("updated_at"))
    if updated and (discovered_at is None or updated_at > discovered_at):
        history.append({"label": "UPDATED", "value": updated})
    if history:
        lines.append({"key": "history", "tone": "text", "source": "EDSM", "items": history})
    traffic = intel.get("traffic") or {}
    if _integer(traffic.get("total")) > 0:
        lines.append({"key": "traffic", "tone": "text", "source": "EDSM", "items": [
            {"label": "TRAFFIC 24H", "value": f"{_integer(traffic.get('day')):,}"},
            {"label": "WEEK", "value": f"{_integer(traffic.get('week')):,}"},
            {"label": "EVER", "value": f"{_integer(traffic.get('total')):,}"},
        ]})
    body_count = _integer(intel.get("body_count"))
    if body_count:
        items = [{"label": "BODIES", "value": str(body_count)}]
        notable = intel.get("notable") or {}
        for key, label in (("earth_like", "EARTH-LIKE"), ("water", "WATER WORLD"), ("ammonia", "AMMONIA")):
            if _integer(notable.get(key)):
                items.append({"label": label, "value": str(_integer(notable[key]))})
        for key, label in (("terraformable", "TERRAFORMABLE"), ("landable", "LANDABLE")):
            if _integer(intel.get(key)):
                items.append({"label": label, "value": str(_integer(intel[key]))})
        lines.append({"key": "bodies", "tone": "text", "source": "EDSM", "items": items})
    ports = intel.get("ports") or {}
    port_items = [
        {"label": label, "value": str(_integer(ports.get(key)))}
        for key, label in (("starports", "STARPORTS"), ("outposts", "OUTPOSTS"),
                           ("settlements", "SETTLEMENTS"), ("carriers", "CARRIERS"))
        if _integer(ports.get(key))
    ]
    if port_items:
        lines.append({"key": "ports", "tone": "text", "source": "EDSM", "items": port_items})
    return lines


def build_jump_info_model(phase, target, route_entries=(), intel=None, current_region=None, find_region=None):
    """The renderer-neutral Jump Info model, or None without a target.

    ``target`` is ``{'name', 'address', 'star_class'}`` from the journal.
    ``find_region`` maps a StarPos to ``(id, name)`` (galactic_regions).
    """
    target = target or {}
    name = str(target.get("name") or "").strip()
    if not name:
        return None
    route = route_plan(route_entries, name, target.get("address"))
    star = star_kind(target.get("star_class") or (route or {}).get("star_class"))
    lines = intel_lines(intel)
    entering = ""
    position = (route or {}).get("position")
    if position and callable(find_region):
        region = find_region(*position)
        if region and region[1] and region[1] != current_region:
            entering = str(region[1])
    if entering:
        lines.append({"key": "entering", "tone": "accent", "source": "",
                      "items": [{"label": "NOW ENTERING", "value": entering.upper()}]})
    if route:
        route = {key: value for key, value in route.items() if key not in {"position", "star_class"}}
    return {
        "phase": str(phase or ""),
        "system": name,
        "star": star,
        "route": route,
        "lines": lines,
    }


class JumpInfoHUD:
    """Native window proxy for the semantic HTML Jump Info overlay."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self._palette = themes.normalize_theme(themes.ACTIVE_PALETTE)
        self._html_render_model = None
        self._visible = False
        self._startup_pending_visible = False
        self._hide_job = None
        self.win = OverlayWindowState(root)
        x = _integer(config.get("jump_info_hud_x"), 680)
        y = _integer(config.get("jump_info_hud_y"), 64)
        self.win.geometry(overlay_chrome.position_geometry(x, y))
        self.win.withdraw()

    @property
    def visible(self):
        return bool(self._visible)

    @property
    def lingering(self):
        return self._hide_job is not None

    def update(self, model):
        """Show ``model`` (a new jump, or new EDSM facts for this one)."""
        self._cancel_hide()
        self._html_render_model = model or None
        if not self._html_render_model:
            return self.hide()
        return self.show()

    def linger(self, model, seconds):
        """Arrived: keep the panel for ``seconds``, then let it go."""
        if not self._visible or seconds <= 0:
            return self.clear()
        self._html_render_model = model or self._html_render_model
        self._cancel_hide()
        try:
            self._hide_job = self.win.call_later(int(seconds * 1000), self._auto_hide)
        except Exception:
            self._hide_job = None
            return self.clear()
        return True

    def clear(self):
        self._html_render_model = None
        return self.hide()

    def show(self):
        if not self._html_render_model:
            return False
        if bool(getattr(self.root, "_voidcompass_startup_presentation_held", False)):
            self._startup_pending_visible = True
            try:
                self.win.withdraw()
            except Exception:
                pass
            return False
        if self._visible:
            return True
        try:
            x = _integer(self.config.get("jump_info_hud_x"), 680)
            y = _integer(self.config.get("jump_info_hud_y"), 64)
            self.win.geometry(overlay_chrome.position_geometry(x, y))
            self.win.deiconify()
            self._visible = True
            self._startup_pending_visible = False
            return True
        except Exception:
            return False

    def hide(self):
        self._cancel_hide()
        pending = self._startup_pending_visible
        self._startup_pending_visible = False
        if not self._visible:
            return bool(pending)
        try:
            self.win.withdraw()
        except Exception:
            return False
        self._visible = False
        return True

    def _cancel_hide(self):
        if self._hide_job is None:
            return
        try:
            self.win.cancel(self._hide_job)
        except Exception:
            pass
        self._hide_job = None

    def _auto_hide(self):
        self._hide_job = None
        self.clear()

    def release_startup_visibility(self):
        if not self._startup_pending_visible:
            return False
        self._startup_pending_visible = False
        return self.show()

    def apply_theme(self, palette=None):
        self._palette = themes.normalize_theme(palette or themes.ACTIVE_PALETTE)

    def destroy(self):
        self._cancel_hide()
        try:
            self.win.destroy()
        except Exception:
            pass
