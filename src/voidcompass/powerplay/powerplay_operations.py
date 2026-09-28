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

# Frontier's Powerplay 2.0 rank curve: ranks 1-5 need these merit totals, and
# every rank after 5 needs another 8,000. The journal reports the rank itself;
# the curve only says how far the next one is.
RANK_CURVE = (0, 2_000, 5_000, 9_000, 15_000)
RANK_STEP = 8_000

# Controlled systems climb these tiers. Anything else the journal reports
# (Unoccupied, Contested, Expansion...) is territory still being fought over.
CONTROL_TIERS = ("Exploited", "Fortified", "Stronghold")
_TIER_BY_KEY = {name.casefold(): index + 1 for index, name in enumerate(CONTROL_TIERS)}
SYSTEM_INTEL_LIMIT = 150
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
        "selected_dossier": "", "last_updated": None, "system_intel": [],
    }


def _number(value):
    """A journal fraction or count, or None when the journal gave none."""
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


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
                       ("cycles", 26), ("objectives", 100),
                       ("system_intel", SYSTEM_INTEL_LIMIT)):
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


def _conflict(raw):
    """PowerplayConflictProgress: each power's share of an acquisition fight."""
    rows = []
    for row in raw.get("PowerplayConflictProgress") or []:
        if not isinstance(row, dict):
            continue
        power = _text(row.get("Power"), 100)
        progress = _number(row.get("ConflictProgress"))
        if power and progress is not None:
            rows.append({"power": power, "progress": progress})
    return sorted(rows, key=lambda row: -row["progress"])[:12]


def _system_snapshot(raw, timestamp):
    return {
        "system": _text(raw.get("StarSystem"), 140),
        "controlling_power": _text(raw.get("ControllingPower"), 100),
        "powers": [_text(name, 100) for name in raw.get("Powers") or [] if _text(name, 100)][:12],
        "state": _text(raw.get("PowerplayState"), 60),
        "control_progress": _number(raw.get("PowerplayStateControlProgress")),
        "reinforcement": _number(raw.get("PowerplayStateReinforcement")),
        "undermining": _number(raw.get("PowerplayStateUndermining")),
        "conflict": _conflict(raw),
        "updated": _iso(timestamp),
    }


_INTEL_FIELDS = ("controlling_power", "powers", "state", "control_progress",
                 "reinforcement", "undermining", "conflict")


def _has_powerplay(snapshot):
    return bool(snapshot.get("controlling_power") or snapshot.get("powers")
                or snapshot.get("state") or snapshot.get("conflict"))


def _record_intel(state, snapshot):
    """Log what the journal said about a Powerplay system on arrival.

    One row per system, newest first. When a revisit shows different numbers
    the old reading moves to ``previous`` so the page can show the change;
    a revisit with the same numbers only counts the visit. A reading older
    than the one kept (a journal replayed at start-up) changes nothing.
    """
    name = snapshot.get("system")
    if not name or not _has_powerplay(snapshot):
        return
    stamp = _timestamp(snapshot["updated"])
    rows = list(state.get("system_intel") or [])
    key = name.casefold()
    existing = next((row for row in rows if _text(row.get("system"), 140).casefold() == key), None)
    if existing is not None and _timestamp(existing.get("updated")) >= stamp:
        return
    row = {**snapshot, "cycle_id": cycle_window(stamp)["id"], "visits": 1,
           "first_seen": snapshot["updated"], "previous": {}}
    if existing is not None:
        rows.remove(existing)
        row["visits"] = max(1, _integer(existing.get("visits"), 1)) + 1
        row["first_seen"] = existing.get("first_seen") or existing.get("updated")
        changed = any(existing.get(field) != snapshot.get(field) for field in _INTEL_FIELDS)
        row["previous"] = (
            {field: existing.get(field) for field in (*_INTEL_FIELDS, "updated", "cycle_id")}
            if changed else dict(existing.get("previous") or {})
        )
    rows.insert(0, row)
    state["system_intel"] = rows[:SYSTEM_INTEL_LIMIT]


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
        state["location"] = _system_snapshot(raw, timestamp)
        _record_intel(state, state["location"])

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


def change_objective(value, objective_id, operation, *, now=None, step=0):
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
    elif operation == "step_objective":
        goal = max(1, _integer(target.get("target"), 1))
        step = max(-goal, min(goal, _integer(step, 0)))
        if not step:
            return state, False
        target["current"] = max(0, min(goal, _integer(target.get("current")) + step))
        target["complete"] = target["current"] >= goal
        target["updated"] = _iso(now)
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


def rank_threshold(rank):
    """Total merits Powerplay 2.0 asks for *rank*."""
    rank = max(1, _integer(rank, 1))
    if rank <= len(RANK_CURVE):
        return RANK_CURVE[rank - 1]
    return RANK_CURVE[-1] + RANK_STEP * (rank - len(RANK_CURVE))


def rank_progress(rank, merits):
    """How far the journal's merit total is between this rank and the next.

    ``consistent`` is False when the total sits outside the rank's band (a
    defection or an old save can leave them apart); the page then shows the
    journal's rank without a bar rather than a bar it can't vouch for.
    """
    if rank is None or merits is None or _integer(rank) < 1:
        return {}
    rank, merits = _integer(rank), max(0, _integer(merits))
    floor, target = rank_threshold(rank), rank_threshold(rank + 1)
    return {
        "rank": rank, "next_rank": rank + 1, "floor": floor, "next": target,
        "to_go": max(0, target - merits),
        "fraction": max(0.0, min(1.0, (merits - floor) / max(1, target - floor))),
        "consistent": floor <= merits < target,
    }


def control_tier(state_name):
    """1-3 for Exploited, Fortified, Stronghold; 0 for anything else."""
    return _TIER_BY_KEY.get(_text(state_name, 60).casefold(), 0)


def system_relation(snapshot, power):
    """What a system is to the pledged power: ours, hostile, up for grabs."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    if not _has_powerplay(snapshot):
        return "none"
    power_key = _text(power, 100).casefold()
    if not power_key:
        return "unaligned"
    controller = _text(snapshot.get("controlling_power"), 100).casefold()
    if controller:
        return "ours" if controller == power_key else "hostile"
    present = {_text(name, 100).casefold() for name in snapshot.get("powers") or []}
    present |= {_text(row.get("power"), 100).casefold()
                for row in snapshot.get("conflict") or [] if isinstance(row, dict)}
    return "acquisition" if power_key in present else "out_of_reach"


# The Powerplay action each relation calls for, and which ethos bonus it uses.
_RELATION_ACTION = {
    "ours": ("REINFORCE", "reinforcement"),
    "hostile": ("UNDERMINE", "undermining"),
    "acquisition": ("ACQUIRE", "acquisition"),
}


def _merits_here(cycle, system):
    key = _text(system, 140).casefold()
    return sum(_integer(value) for name, value in (cycle.get("systems") or {}).items()
               if name.casefold() == key)


def _system_view(snapshot, power, cycle, pledged):
    """A logged or current system dressed for the page."""
    relation = system_relation(snapshot, power)
    action, ethos_key = _RELATION_ACTION.get(relation, ("", ""))
    controller = dossier_for(snapshot.get("controlling_power"))
    view = {
        **deepcopy(snapshot),
        "relation": relation, "action": action,
        "ethos": (pledged.get("ethos") or {}).get(ethos_key, "") if ethos_key else "",
        "tier": control_tier(snapshot.get("state")),
        "controller_portrait": controller.get("portrait", ""),
        "merits_here": _merits_here(cycle, snapshot.get("system")),
        "stale": bool(snapshot.get("cycle_id")) and snapshot.get("cycle_id") != cycle.get("id"),
        "progress_delta": None,
    }
    previous = snapshot.get("previous") or {}
    now_progress = _number(snapshot.get("control_progress"))
    then_progress = _number(previous.get("control_progress"))
    # Progress is only comparable inside one cycle: the Thursday tick
    # recalculates every system.
    if (now_progress is not None and then_progress is not None
            and previous.get("cycle_id") == snapshot.get("cycle_id")):
        view["progress_delta"] = now_progress - then_progress
    return view


_DAY_NAMES = ("THU", "FRI", "SAT", "SUN", "MON", "TUE", "WED")


def _cycle_days(cycle, history):
    """Merits earned on each of the cycle's seven days (days start 07:00 UTC)."""
    start = _timestamp(cycle.get("started"))
    power = _text(cycle.get("power"), 100).casefold()
    days = [{"label": _DAY_NAMES[index],
             "date": (start + timedelta(days=index)).date().isoformat(),
             "merits": 0} for index in range(7)]
    for row in history:
        delta = max(0, _integer(row.get("delta")))
        if not delta or (power and _text(row.get("power"), 100).casefold() not in {"", power}):
            continue
        offset = (_timestamp(row.get("timestamp")) - start).total_seconds()
        if 0 <= offset < 7 * 86400:
            days[int(offset // 86400)]["merits"] += delta
    return days


def _cycle_compare(cycles):
    closed = [max(0, _integer(row.get("merits_gained"))) for row in cycles if row.get("id")]
    if not closed:
        return {"count": 0, "last": None, "best": None, "average": None}
    return {"count": len(closed), "last": closed[-1], "best": max(closed),
            "average": round(sum(closed) / len(closed))}


def _merit_series(history, limit=240):
    rows = [{"timestamp": row.get("timestamp"), "total": max(0, _integer(row.get("total"))),
             "delta": max(0, _integer(row.get("delta")))}
            for row in history if row.get("timestamp") and row.get("total") is not None]
    return rows[-limit:]


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
    pledged = dossier_for(state.get("power"))
    power = state.get("power") if state.get("pledged") else ""
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
    intel = [_system_view(row, power, cycle, pledged) for row in state.get("system_intel") or []]
    location = dict(state.get("location") or {})
    location_view = {}
    if location.get("system"):
        # The system you are in is usually the newest intel row: use it, so
        # the card shows the change since the last reading too.
        location_view = next((
            dict(row) for row in intel
            if _text(row.get("system"), 140).casefold() == _text(location.get("system"), 140).casefold()
            and row.get("updated") == location.get("updated")
        ), None) or _system_view(
            {**location, "cycle_id": cycle_window(location.get("updated"))["id"]
             if location.get("updated") else cycle.get("id")},
            power, cycle, pledged,
        )
    intel_counts = {key: 0 for key in ("ours", "hostile", "acquisition", "out_of_reach", "unaligned", "stale")}
    for row in intel:
        intel_counts[row["relation"]] = intel_counts.get(row["relation"], 0) + 1
        intel_counts["stale"] += int(row["stale"])
    # How many systems each power was seen holding this cycle.
    held = {}
    for row in intel:
        if not row["stale"] and row.get("controlling_power"):
            slug = power_slug(row["controlling_power"])
            held[slug] = held.get(slug, 0) + 1
    dossiers = [{**deepcopy(row), "seen_controlled": held.get(row["slug"], 0)} for row in POWER_DOSSIERS]
    return {
        "powerplay": state,
        "dossiers": dossiers,
        "selected_dossier": {**deepcopy(_DOSSIER_BY_SLUG[selected_slug]),
                             "seen_controlled": held.get(selected_slug, 0)},
        "pledged_dossier": pledged,
        "rank": rank_progress(state.get("rank"), state.get("merits")) if state.get("pledged") else {},
        "cycle": {**cycle, "system_rows": system_rows[:20]},
        "cycle_days": _cycle_days(cycle, state.get("merit_history") or []),
        "cycle_compare": _cycle_compare(state.get("cycles") or []),
        "session_merits": session_merits,
        "cycle_history": list(reversed(state.get("cycles") or []))[:12],
        "objectives": list(reversed(state.get("objectives") or [])),
        "active_objective": deepcopy(selected or {}),
        "merit_history": list(reversed(state.get("merit_history") or []))[:100],
        "merit_series": _merit_series(state.get("merit_history") or []),
        "cargo_history": list(reversed(state.get("cargo_history") or []))[:100],
        "location": location_view,
        "intel": intel,
        "intel_counts": intel_counts,
    }
