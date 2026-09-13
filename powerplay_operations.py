"""Powerplay 2.0 state, journal reduction, dossiers and commander objectives.

The module deliberately has no dashboard or overlay dependencies.  It keeps
the journal-owned facts separate from commander-entered plans and provides one
bounded, profile-safe model to every renderer.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
import time


POWERPLAY_EVENTS = {
    "Powerplay", "PowerplayJoin", "PowerplayLeave", "PowerplayDefect",
    "PowerplayRank", "PowerplayMerits", "PowerplaySalary",
    "PowerplayDeliver", "PowerplayCollect", "Location", "FSDJump",
    "CarrierJump",
}


def _dossier(name, slug, portrait, allegiance, headquarters, reinforcement,
             acquisition, undermining, role):
    return {
        "name": name, "slug": slug, "portrait": portrait,
        "allegiance": allegiance, "headquarters": headquarters,
        "ethos": {
            "reinforcement": reinforcement,
            "acquisition": acquisition,
            "undermining": undermining,
        },
        "role": role,
    }


POWER_DOSSIERS = (
    _dossier("Aisling Duval", "aisling_duval", "aisling_duval.jpg", "Empire", "Cubeo",
             "Finance", "Social", "Social", "Imperial princess and reform advocate"),
    _dossier("Archon Delaine", "archon_delaine", "archon_delaine.png", "Independent", "Harma",
             "Combat", "Combat", "Combat", "Pirate lord of the Kumo Crew"),
    _dossier("Arissa Lavigny-Duval", "arissa_lavigny_duval", "arissa_lavigny_duval.png", "Empire", "Kamadhenu",
             "Combat", "Social", "Combat", "Emperor of the Empire"),
    _dossier("Denton Patreus", "denton_patreus", "denton_patreus.jpg", "Empire", "Eotienses",
             "Combat", "Finance", "Combat", "Imperial senator and fleet admiral"),
    _dossier("Edmund Mahon", "edmund_mahon", "edmund_mahon.png", "Alliance", "Gateway",
             "Finance", "Finance", "Combat", "Alliance prime minister"),
    _dossier("Felicia Winters", "felicia_winters", "felicia_winters.png", "Federation", "Rhea",
             "Finance", "Social", "Finance", "Federal liberal leader"),
    _dossier("Jerome Archer", "jerome_archer", "jerome_archer.webp", "Federation", "Nanomam",
             "Combat", "Combat", "Covert", "Federal security hardliner"),
    _dossier("Li Yong-Rui", "li_yong_rui", "li_yong_rui.png", "Independent", "Lembava",
             "Finance", "Social", "Finance", "Sirius Corporation chief executive"),
    _dossier("Nakato Kaine", "nakato_kaine", "nakato_kaine.webp", "Alliance", "Tionisla",
             "Covert", "Social", "Social", "Alliance Assembly councillor"),
    _dossier("Pranav Antal", "pranav_antal", "pranav_antal.png", "Independent", "Polevnic",
             "Covert", "Social", "Social", "Leader of the Utopia movement"),
    _dossier("Yuri Grom", "yuri_grom", "yuri_grom.webp", "Independent", "Clayakarma",
             "Combat", "Covert", "Covert", "Leader of the EG Union"),
    _dossier("Zemina Torval", "zemina_torval", "zemina_torval.png", "Empire", "Synteini",
             "Covert", "Finance", "Finance", "Imperial senator and industrialist"),
)

_DOSSIER_BY_SLUG = {row["slug"]: row for row in POWER_DOSSIERS}
_DOSSIER_ALIASES = {
    "a lavigny duval": "arissa_lavigny_duval",
    "arissa lavigny duval": "arissa_lavigny_duval",
    "li yong rui": "li_yong_rui",
}


def fresh_powerplay_state():
    return {
        "pledged": False, "power": "", "rank": None, "merits": None,
        "time_pledged": None, "salary": None, "location": {},
        "cargo_history": [], "merit_history": [], "cycles": [],
        "current_cycle": {}, "objectives": [], "selected_objective_id": "",
        "selected_dossier": "", "last_updated": None,
    }


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _text(value, limit=240):
    return str(value or "").strip()[:limit]


def _timestamp(value=None):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, timezone.utc)
    else:
        raw = _text(value, 80)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value=None):
    return _timestamp(value).isoformat().replace("+00:00", "Z")


def power_slug(value):
    key = re.sub(r"[^a-z0-9]+", " ", _text(value, 100).casefold()).strip()
    return _DOSSIER_ALIASES.get(key, key.replace(" ", "_"))


def dossier_for(value):
    return deepcopy(_DOSSIER_BY_SLUG.get(power_slug(value), {}))


def cycle_window(value=None):
    """Return the Thursday 07:00 UTC Powerplay cycle containing *value*."""
    moment = _timestamp(value)
    shifted = moment - timedelta(hours=7)
    days_since_thursday = (shifted.weekday() - 3) % 7
    start_date = (shifted - timedelta(days=days_since_thursday)).date()
    start = datetime.combine(start_date, datetime.min.time(), timezone.utc) + timedelta(hours=7)
    end = start + timedelta(days=7)
    return {
        "id": start.date().isoformat(),
        "started": start.isoformat().replace("+00:00", "Z"),
        "ends": end.isoformat().replace("+00:00", "Z"),
    }


def _new_cycle(value=None, power=""):
    window = cycle_window(value)
    return {
        **window, "power": _text(power, 100), "merits_gained": 0,
        "cargo_collected": 0, "cargo_delivered": 0, "event_count": 0,
        "systems": {}, "closed": None,
    }


def normalise_state(value):
    source = value if isinstance(value, dict) else {}
    state = fresh_powerplay_state()
    state.update(source)
    for key in ("location", "current_cycle"):
        state[key] = dict(state.get(key) or {})
    for key, limit in (("cargo_history", 100), ("merit_history", 500),
                       ("cycles", 26), ("objectives", 100)):
        state[key] = [dict(row) for row in (state.get(key) or []) if isinstance(row, dict)][-limit:]
    state["selected_objective_id"] = _text(state.get("selected_objective_id"), 80)
    state["selected_dossier"] = _text(state.get("selected_dossier"), 80)
    return state


def _archive_cycle(state, closed_at):
    current = dict(state.get("current_cycle") or {})
    if not current or not current.get("id"):
        return
    current["closed"] = _iso(closed_at)
    cycles = [
        row for row in state.get("cycles") or []
        if not (
            row.get("id") == current.get("id")
            and _text(row.get("power"), 100).casefold()
            == _text(current.get("power"), 100).casefold()
        )
    ]
    cycles.append(current)
    state["cycles"] = cycles[-26:]


def ensure_cycle(state, value=None, power=None, force=False):
    state.update(normalise_state(state))
    window = cycle_window(value)
    current = dict(state.get("current_cycle") or {})
    requested_power = _text(power if power is not None else state.get("power"), 100)
    rollover = bool(
        current and current.get("id") and (
            force or current.get("id") != window["id"]
            or (_text(current.get("power"), 100)
                and _text(current.get("power"), 100).casefold()
                != requested_power.casefold() and requested_power)
        )
    )
    if rollover:
        _archive_cycle(state, value)
        current = {}
    if not current:
        current = _new_cycle(value, requested_power)
    elif requested_power and not current.get("power"):
        current["power"] = requested_power
    state["current_cycle"] = current
    return current


def _system_name(raw, fallback=""):
    return _text(raw.get("StarSystem") or raw.get("System") or fallback, 140)


def _commodity(raw):
    value = raw.get("Type_Localised") or raw.get("Commodity_Localised")
    value = value or raw.get("Type") or raw.get("Commodity")
    value = _text(value, 160).strip("$;")
    return value.removesuffix("_Name").removesuffix("_name")


def _objective_progress(state, direction, commodity, count, system, timestamp):
    changed = False
    for objective in state.get("objectives") or []:
        if objective.get("complete"):
            continue
        kind = _text(objective.get("kind"), 30).casefold()
        if kind not in {"cargo", direction.casefold()}:
            continue
        wanted_commodity = _text(objective.get("commodity"), 160).casefold()
        wanted_system = _text(objective.get("system"), 140).casefold()
        if wanted_commodity and wanted_commodity != commodity.casefold():
            continue
        if wanted_system and wanted_system != system.casefold():
            continue
        target = max(1, _integer(objective.get("target"), 1))
        objective["current"] = min(target, max(0, _integer(objective.get("current"))) + count)
        objective["complete"] = objective["current"] >= target
        objective["updated"] = _iso(timestamp)
        changed = True
    return changed


def reduce_event(value, event_name, raw, *, current_system=""):
    """Apply one Journal event and return a normalized Powerplay state."""
    state = normalise_state(value)
    if event_name not in POWERPLAY_EVENTS or not isinstance(raw, dict):
        return state
    timestamp = raw.get("timestamp")
    old_power = _text(state.get("power"), 100)
    incoming_power = _text(raw.get("ToPower") or raw.get("Power") or old_power, 100)
    cycle = ensure_cycle(state, timestamp, old_power)

    if event_name == "PowerplayLeave":
        state.update({"pledged": False, "power": "", "rank": None,
                      "merits": None, "time_pledged": None})
    elif event_name == "PowerplayDefect" and incoming_power:
        cycle = ensure_cycle(state, timestamp, incoming_power, force=bool(
            old_power and old_power.casefold() != incoming_power.casefold()
        ))
        state.update({"pledged": True, "power": incoming_power,
                      "rank": None, "merits": None, "time_pledged": None,
                      "pledge_started": _iso(timestamp)})
    elif event_name in {"PowerplayJoin", "Powerplay", "PowerplayRank", "PowerplayMerits"} and incoming_power:
        if old_power.casefold() != incoming_power.casefold():
            cycle = ensure_cycle(state, timestamp, incoming_power, force=bool(old_power))
        state.update({"pledged": True, "power": incoming_power})
        if event_name == "PowerplayJoin":
            state["pledge_started"] = _iso(timestamp)

    if event_name in {"Powerplay", "PowerplayRank"} and raw.get("Rank") is not None:
        state["rank"] = max(0, _integer(raw.get("Rank")))
    previous_merits = state.get("merits")
    total_merits = None
    if event_name == "Powerplay" and raw.get("Merits") is not None:
        total_merits = max(0, _integer(raw.get("Merits")))
    elif event_name == "PowerplayMerits" and raw.get("TotalMerits") is not None:
        total_merits = max(0, _integer(raw.get("TotalMerits")))
    if total_merits is not None:
        supplied_delta = (
            next((raw.get(key) for key in ("MeritsGained", "Amount")
                  if raw.get(key) is not None), None)
            if event_name == "PowerplayMerits" else None
        )
        delta = max(0, _integer(supplied_delta)) if supplied_delta is not None else 0
        if not delta and previous_merits is not None:
            delta = max(0, total_merits - _integer(previous_merits))
        state["merits"] = total_merits
        history = list(state.get("merit_history") or [])
        system = _system_name(raw, current_system)
        merit_row = {
                "timestamp": _iso(timestamp), "total": total_merits,
                "delta": delta, "power": state.get("power"), "system": system,
        }
        duplicate = any(
            all(existing.get(key) == merit_row.get(key) for key in merit_row)
            for existing in history[-500:]
        )
        if not duplicate and (delta or not history or history[-1].get("total") != total_merits):
            history.append(merit_row)
            state["merit_history"] = history[-500:]
            cycle["merits_gained"] = max(0, _integer(cycle.get("merits_gained"))) + delta
            cycle["event_count"] = max(0, _integer(cycle.get("event_count"))) + 1
            if system and delta:
                systems = dict(cycle.get("systems") or {})
                systems[system] = max(0, _integer(systems.get(system))) + delta
                cycle["systems"] = systems
    if event_name == "Powerplay" and raw.get("TimePledged") is not None:
        state["time_pledged"] = max(0, _integer(raw.get("TimePledged")))
    if event_name == "PowerplaySalary" and raw.get("Amount") is not None:
        state["salary"] = max(0, _integer(raw.get("Amount")))

    if event_name in {"Location", "FSDJump", "CarrierJump"}:
        state["location"] = {
            "system": raw.get("StarSystem"),
            "controlling_power": raw.get("ControllingPower"),
            "powers": list(raw.get("Powers") or []),
            "state": raw.get("PowerplayState"),
            "control_progress": raw.get("PowerplayStateControlProgress"),
            "reinforcement": raw.get("PowerplayStateReinforcement"),
            "undermining": raw.get("PowerplayStateUndermining"),
            "updated": _iso(timestamp),
        }

    if event_name in {"PowerplayDeliver", "PowerplayCollect"}:
        direction = "DELIVER" if event_name == "PowerplayDeliver" else "COLLECT"
        count = max(0, _integer(raw.get("Count")))
        commodity = _commodity(raw)
        system = _system_name(raw, current_system)
        row = {
            "direction": direction, "type": commodity, "count": count,
            "system": system, "timestamp": _iso(timestamp),
        }
        cargo_history = list(state.get("cargo_history") or [])
        duplicate = any(
            all(existing.get(key) == row.get(key) for key in row)
            for existing in cargo_history[-100:]
        )
        if not duplicate:
            state["cargo_history"] = (cargo_history + [row])[-100:]
            cycle_key = "cargo_delivered" if direction == "DELIVER" else "cargo_collected"
            cycle[cycle_key] = max(0, _integer(cycle.get(cycle_key))) + count
            cycle["event_count"] = max(0, _integer(cycle.get("event_count"))) + 1
            _objective_progress(state, direction, commodity, count, system, timestamp)

    state["current_cycle"] = cycle
    state["last_updated"] = _iso(timestamp)
    return state


def add_objective(value, payload, *, now=None):
    state = normalise_state(value)
    title = _text(payload.get("title") or payload.get("name"), 160)
    kind = _text(payload.get("kind") or "general", 30).casefold()
    if not title or kind not in {"general", "system", "cargo", "collect", "deliver"}:
        return state, False
    stamp = _iso(now)
    objective_id = f"pp-{time.time_ns()}"
    objective = {
        "id": objective_id, "title": title, "kind": kind,
        "system": _text(payload.get("system"), 140),
        "commodity": _text(payload.get("commodity"), 160),
        "target": max(1, min(1_000_000, _integer(payload.get("target"), 1))),
        "current": max(0, _integer(payload.get("current"))),
        "notes": _text(payload.get("notes"), 500),
        "complete": False, "created": stamp, "updated": stamp,
    }
    objective["current"] = min(objective["target"], objective["current"])
    objective["complete"] = objective["current"] >= objective["target"]
    state["objectives"] = (list(state.get("objectives") or []) + [objective])[-100:]
    state["selected_objective_id"] = objective_id
    return state, True


def change_objective(value, objective_id, operation, *, now=None):
    state = normalise_state(value)
    objective_id = _text(objective_id, 80)
    rows = list(state.get("objectives") or [])
    target = next((row for row in rows if _text(row.get("id"), 80) == objective_id), None)
    if operation == "delete_objective":
        filtered = [row for row in rows if _text(row.get("id"), 80) != objective_id]
        if len(filtered) == len(rows):
            return state, False
        state["objectives"] = filtered
        if state.get("selected_objective_id") == objective_id:
            state["selected_objective_id"] = ""
        return state, True
    if target is None:
        return state, False
    if operation == "select_objective":
        state["selected_objective_id"] = objective_id
    elif operation == "toggle_objective":
        target["complete"] = not bool(target.get("complete"))
        if target["complete"]:
            target["current"] = max(_integer(target.get("current")), _integer(target.get("target"), 1))
        else:
            target["current"] = 0
        target["updated"] = _iso(now)
    else:
        return state, False
    return state, True


def select_dossier(value, slug):
    state = normalise_state(value)
    slug = power_slug(slug)
    if slug not in _DOSSIER_BY_SLUG:
        return state, False
    state["selected_dossier"] = slug
    return state, True


def build_workspace(value, *, now=None, session_started=None):
    state = normalise_state(value)
    cycle = ensure_cycle(state, now, state.get("power"))
    active = [row for row in state.get("objectives") or [] if not row.get("complete")]
    selected_id = state.get("selected_objective_id")
    selected = next((row for row in active if row.get("id") == selected_id), None)
    if selected is None and active:
        selected = active[0]
    pledged_slug = power_slug(state.get("power"))
    selected_slug = state.get("selected_dossier") or pledged_slug
    if selected_slug not in _DOSSIER_BY_SLUG:
        selected_slug = POWER_DOSSIERS[0]["slug"]
    location = dict(state.get("location") or {})
    system_rows = [
        {"system": name, "merits": merits}
        for name, merits in sorted(
            (cycle.get("systems") or {}).items(), key=lambda item: (-_integer(item[1]), item[0].casefold())
        )
    ]
    session_merits = 0
    if session_started is not None:
        session_floor = _timestamp(session_started)
        session_merits = sum(
            max(0, _integer(row.get("delta")))
            for row in state.get("merit_history") or []
            if _timestamp(row.get("timestamp")) >= session_floor
        )
    return {
        "powerplay": state,
        "dossiers": deepcopy(list(POWER_DOSSIERS)),
        "selected_dossier": deepcopy(_DOSSIER_BY_SLUG[selected_slug]),
        "pledged_dossier": dossier_for(state.get("power")),
        "cycle": {**cycle, "system_rows": system_rows[:20]},
        "session_merits": session_merits,
        "cycle_history": list(reversed(state.get("cycles") or []))[:12],
        "objectives": list(reversed(state.get("objectives") or [])),
        "active_objective": deepcopy(selected or {}),
        "merit_history": list(reversed(state.get("merit_history") or []))[:100],
        "cargo_history": list(reversed(state.get("cargo_history") or []))[:100],
        "location": location,
    }
