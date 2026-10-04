"""What the BGS tab shows, from the BGS record: plain data for the page."""

from __future__ import annotations

import json
import time

from voidcompass.bgs import ticks as tick_clock
from voidcompass.bgs.journal import KINDS
from voidcompass.bgs.states import (BAD_STATES, BIG_DROP, CLOSE_RACE, CONFLICT_STATES, RETREAT_DANGER,
                                    RETREAT_INFLUENCE, STATES, state_info)

# Influence kinds summed as credits, and kinds that are counts.
CREDIT_KINDS = {"bounties", "bonds", "trade_profit", "trade_loss", "trade_buy", "black_market", "cartography",
                "exobiology", "capship"}
COUNT_KINDS = {"mission_failed", "search_rescue", "space_cz", "ground_cz", "murder", "ground_murder"}
GOOD_KINDS = ("inf", "bounties", "bonds", "trade_profit", "cartography", "exobiology", "search_rescue", "space_cz", "ground_cz", "capship")
BAD_KINDS = ("mission_failed", "trade_loss", "black_market", "murder", "ground_murder")


def _states_of(faction):
    return {
        "state": faction.get("state") or "None",
        "active": [state_info(name) for name in faction.get("active") or () if name and name != "None"],
        "pending": [{**state_info(row.get("state")), "trend": row.get("trend")} for row in faction.get("pending") or ()],
        "recovering": [{**state_info(row.get("state")), "trend": row.get("trend")} for row in faction.get("recovering") or ()],
    }


def _previous_influence(snaps, latest):
    """Each faction's influence in the last snapshot that differs (the
    change since the tick before)."""
    now = {row["name"]: row["influence"] for row in latest.get("factions") or ()}
    for snap in reversed(snaps[:-1]):
        then = {row["name"]: row["influence"] for row in snap.get("factions") or ()}
        if any(abs(then.get(name, -1) - value) > 1e-6 for name, value in now.items()):
            return then, snap["ts"], snap.get("controlling")
    return {}, None, None


def system_picture(store, system_address, tracked=()):
    snaps = store.snapshots(system_address, limit=60)
    if not snaps:
        return None
    latest = snaps[-1]
    before, before_ts, before_controlling = _previous_influence(snaps, latest)
    tracked = set(tracked)
    factions = []
    for row in sorted(latest.get("factions") or (), key=lambda item: -item["influence"]):
        previous = before.get(row["name"])
        factions.append({
            "name": row["name"], "influence": row["influence"],
            "delta": (row["influence"] - previous) if previous is not None else None, "new": bool(before) and previous is None,
            "government": row.get("government") or "", "allegiance": row.get("allegiance") or "",
            "happiness": row.get("happiness") or "", "reputation": row.get("reputation"),
            "player": bool(row.get("player")), "squadron": bool(row.get("squadron")),
            "controlling": row["name"] == latest.get("controlling"), "tracked": row["name"] in tracked,
            **_states_of(row),
        })
    return {
        "system": latest["system"], "system_address": latest["system_address"], "ts": latest["ts"], "source": latest["source"],
        "controlling": latest.get("controlling") or "", "control_changed": bool(before_controlling and before_controlling != latest.get("controlling")),
        "previous_controlling": before_controlling or "", "since": before_ts,
        "population": latest.get("population") or 0, "allegiance": latest.get("allegiance") or "",
        "government": latest.get("government") or "", "economy": latest.get("economy") or "",
        "second_economy": latest.get("second_economy") or "", "security": latest.get("security") or "",
        "controlling_power": latest.get("controlling_power") or "", "powers": latest.get("powers") or [],
        "power_state": latest.get("power_state") or "",
        "factions": factions, "conflicts": latest.get("conflicts") or [],
        "tracked": str(latest["system_address"]) in {str(item) for item in store.tracked("system")},
        "url": latest.get("url") or "",
    }


def history(store, system_address, days=90):
    """Influence over time per faction: your visits plus EDSM's history."""
    since = time.time() - days * 86400
    series = {}
    for snap in store.snapshots(system_address, limit=400):
        if (snap.get("ts") or 0) < since:
            continue
        for row in snap.get("factions") or ():
            series.setdefault(row["name"], {})[snap["ts"]] = (row["influence"], row.get("state") or "None", snap["source"])
    for point in store.edsm_points(system_address):
        if point["ts"] >= since:
            # EDSM keeps a faction at 0 for the days it was not in the
            # system: a break in its line, not a plunge to zero.
            value = point["influence"] if (point["influence"] or 0) > 0 else None
            series.setdefault(point["faction"], {}).setdefault(point["ts"], (value, point["state"] or "", "edsm"))
    out = []
    for name, points in series.items():
        rows = [{"ts": ts, "influence": value[0], "state": value[1], "source": value[2]} for ts, value in sorted(points.items())]
        rows = rows[-240:]
        while rows and rows[0]["influence"] is None:
            rows.pop(0)
        present = [row["influence"] for row in rows if row["influence"] is not None]
        if present:
            out.append({"faction": name, "points": rows, "last": present[-1] if rows[-1]["influence"] is not None else 0})
    return sorted(out, key=lambda row: -row["last"])


def alerts(store, now=None):
    """What needs a tracked faction's attention, worst first."""
    now = now or time.time()
    tracked_factions = set(store.tracked("faction"))
    tracked_systems = {str(item) for item in store.tracked("system")}
    if not tracked_factions and not tracked_systems:
        return []
    out = []
    addresses = {row["system_address"] for row in store.query("SELECT system_address FROM presence WHERE faction IN (%s)"
                                                               % ",".join("?" * len(tracked_factions)), tuple(tracked_factions))} \
        if tracked_factions else set()
    addresses |= {int(item) for item in tracked_systems if str(item).lstrip("-").isdigit()}
    for address in addresses:
        picture = system_picture(store, address, tracked_factions)
        if not picture:
            continue
        system = picture["system"]
        ranked = picture["factions"]
        for index, row in enumerate(ranked):
            if row["name"] not in tracked_factions and str(address) not in tracked_systems:
                continue
            if row["name"] not in tracked_factions and not row["controlling"]:
                continue
            base = {"system": system, "system_address": address, "faction": row["name"], "ts": picture["ts"]}
            if row["influence"] < RETREAT_DANGER:
                out.append({**base, "level": "danger", "text": f"{row['influence'] * 100:.1f}% influence: at risk of retreat"})
            elif row["influence"] < RETREAT_INFLUENCE:
                out.append({**base, "level": "warn", "text": f"{row['influence'] * 100:.1f}% influence: below 5%"})
            if row["delta"] is not None and row["delta"] <= -BIG_DROP:
                out.append({**base, "level": "warn", "text": f"Influence fell {abs(row['delta']) * 100:.1f} points since {tick_clock.label(picture['since'])}"})
            for state in row["active"] + row["pending"]:
                pending = state in row["pending"]
                if state["name"] in CONFLICT_STATES | {"Retreat", "Expansion"}:
                    if state["name"] == "Expansion":
                        level = "info"
                    elif state["name"] == "Retreat" or (state["name"] in CONFLICT_STATES and row["controlling"]):
                        level = "danger" if not pending else "warn"
                    else:
                        level = "warn"
                    out.append({**base, "level": level, "text": f"{state['label']} {'pending' if pending else 'active'}"})
                elif state["name"] in BAD_STATES and not pending:
                    out.append({**base, "level": "info", "text": f"{state['label']} active"})
            if row["controlling"] and index + 1 < len(ranked) and row["influence"] - ranked[index + 1]["influence"] < CLOSE_RACE:
                out.append({**base, "level": "warn",
                            "text": f"Control at risk: {ranked[index + 1]['name']} is {abs(row['influence'] - ranked[index + 1]['influence']) * 100:.1f} points behind"})
            if not row["controlling"] and index == 1 and ranked[0]["influence"] - row["influence"] < CLOSE_RACE:
                out.append({**base, "level": "info", "text": f"{(ranked[0]['influence'] - row['influence']) * 100:.1f} points from taking control"})
        if picture["control_changed"] and (picture["controlling"] in tracked_factions or picture["previous_controlling"] in tracked_factions):
            lost = picture["previous_controlling"] in tracked_factions
            out.append({"system": system, "system_address": address, "ts": picture["ts"],
                        "faction": picture["previous_controlling"] if lost else picture["controlling"],
                        "level": "danger" if lost else "good",
                        "text": f"{'Lost control to' if lost else 'Took control from'} {picture['controlling'] if lost else picture['previous_controlling']}"})
    order = {"danger": 0, "warn": 1, "good": 2, "info": 3}
    return sorted(out, key=lambda row: (order.get(row["level"], 9), -(row["ts"] or 0)))[:80]


def factions_list(store, query="", limit=200):
    tracked = set(store.tracked("faction"))
    rows = store.query(
        "SELECT faction, COUNT(*) systems, SUM(controlling) controlled, MAX(influence) best, MAX(ts) seen "
        "FROM presence GROUP BY faction")
    text = str(query or "").strip().casefold()
    if text:
        rows = [row for row in rows if text in row["faction"].casefold()]
    out = []
    for row in rows:
        out.append({"name": row["faction"], "systems": row["systems"], "controlled": row["controlled"] or 0,
                    "best": row["best"], "seen": row["seen"], "tracked": row["faction"] in tracked})
    out.sort(key=lambda row: (not row["tracked"], -row["systems"], row["name"].casefold()))
    return out[:limit], len(rows)


def faction_detail(store, name, tick_start=None):
    rows = store.query("SELECT * FROM presence WHERE faction = ? ORDER BY influence DESC", (name,))
    if not rows:
        return None
    systems = []
    info = {}
    for row in rows:
        data = json.loads(row["data"])
        info = info or data
        picture = system_picture(store, row["system_address"])
        mine = next((item for item in (picture or {}).get("factions", ()) if item["name"] == name), None)
        conflicts = [conflict for conflict in (picture or {}).get("conflicts", ())
                     if any(side["name"] == name for side in conflict.get("sides") or ())]
        systems.append({
            "system": row["system"], "system_address": row["system_address"], "ts": row["ts"], "source": row["source"],
            "influence": row["influence"], "delta": (mine or {}).get("delta"), "controlling": bool(row["controlling"]),
            "rank": next((index + 1 for index, item in enumerate((picture or {}).get("factions", ())) if item["name"] == name), None),
            "factions": len((picture or {}).get("factions", ())), "conflicts": conflicts,
            **_states_of(data), "happiness": data.get("happiness") or "", "reputation": data.get("reputation"),
        })
    activity = store.query(
        "SELECT kind, SUM(amount) amount, SUM(count) count FROM activity WHERE faction = ? GROUP BY kind", (name,))
    recent = store.query(
        "SELECT kind, SUM(amount) amount, SUM(count) count FROM activity WHERE faction = ? AND ts >= ? GROUP BY kind",
        (name, tick_start or 0)) if tick_start else []
    reputation = next((row["reputation"] for row in systems if row["reputation"] is not None), None)
    return {
        "name": name, "government": info.get("government") or "", "allegiance": info.get("allegiance") or "",
        "player": bool(info.get("player")), "reputation": reputation, "tracked": name in set(store.tracked("faction")),
        "systems": systems, "controlled": sum(1 for row in systems if row["controlling"]),
        "activity": _kind_rows(activity), "activity_tick": _kind_rows(recent),
    }


def _kind_rows(rows):
    return [{"kind": row["kind"], "label": KINDS.get(row["kind"], row["kind"]), "amount": row["amount"] or 0,
             "count": row["count"] or 0, "credits": row["kind"] in CREDIT_KINDS, "bad": row["kind"] in BAD_KINDS}
            for row in sorted(rows, key=lambda row: (row["kind"] in BAD_KINDS, KINDS.get(row["kind"], row["kind"])))]


def systems_list(store, query="", only="", limit=250):
    tracked = {str(item) for item in store.tracked("system")}
    rows = store.query("SELECT * FROM systems ORDER BY ts DESC")
    text = str(query or "").strip().casefold()
    if text:
        rows = [row for row in rows if text in str(row["system"]).casefold() or text in str(row["controlling"]).casefold()]
    if only == "tracked":
        rows = [row for row in rows if str(row["system_address"]) in tracked]
    elif only == "conflicts":
        rows = [row for row in rows if row["conflicts"]]
    out = [{"system": row["system"], "system_address": row["system_address"], "controlling": row["controlling"],
            "population": row["population"], "allegiance": row["allegiance"], "government": row["government"],
            "economy": row["economy"], "factions": row["factions"], "conflicts": row["conflicts"], "ts": row["ts"],
            "visits": row["visits"], "source": row["source"], "tracked": str(row["system_address"]) in tracked}
           for row in rows]
    out.sort(key=lambda row: (not row["tracked"], -(row["ts"] or 0)))
    return out[:limit], len(rows)


def conflicts(store):
    tracked = set(store.tracked("faction"))
    out = []
    for row in store.query("SELECT system_address FROM systems WHERE conflicts > 0"):
        picture = system_picture(store, row["system_address"])
        if not picture:
            continue
        influence = {item["name"]: item["influence"] for item in picture["factions"]}
        for conflict in picture["conflicts"]:
            if conflict.get("status") not in ("active", "pending"):
                continue
            sides = [{**side, "influence": influence.get(side["name"]), "tracked": side["name"] in tracked}
                     for side in conflict.get("sides") or ()]
            out.append({"system": picture["system"], "system_address": picture["system_address"], "ts": picture["ts"],
                        "type": conflict.get("type") or "", "status": conflict.get("status") or "", "sides": sides,
                        "tracked": any(side["tracked"] for side in sides)})
    out.sort(key=lambda row: (not row["tracked"], row["status"] != "active", -(row["ts"] or 0)))
    return out


def activity(store, tick_start=None, ticks_known=()):
    """Your BGS work, per tick: the ticks with work, and one tick's detail."""
    known = sorted(ticks_known or ())
    rows = store.query("SELECT ts FROM activity ORDER BY ts DESC LIMIT 20000")
    periods = {}
    for row in rows:
        start, estimated = tick_clock.tick_for(row["ts"], known)
        if start is None:
            continue
        entry = periods.setdefault(start, {"start": start, "estimated": estimated, "events": 0})
        entry["events"] += 1
    period_list = sorted(periods.values(), key=lambda row: -row["start"])[:60]
    if tick_start is None and period_list:
        tick_start = period_list[0]["start"]
    detail = None
    if tick_start is not None:
        later = [row["start"] for row in period_list if row["start"] > tick_start]
        end = min(later) if later else tick_start + 10 * 86400
        if known:
            following = [tick for tick in known if tick > tick_start]
            if following:
                end = min(end, following[0])
        records = store.query("SELECT * FROM activity WHERE ts >= ? AND ts < ? ORDER BY ts", (tick_start, end))
        systems = {}
        for record in records:
            system = systems.setdefault(record["system_address"], {"system": record["system"] or "Unknown system",
                                                                     "system_address": record["system_address"], "factions": {}})
            if record["system"] and system["system"] == "Unknown system":
                system["system"] = record["system"]
            faction = system["factions"].setdefault(record["faction"], {"name": record["faction"], "kinds": {}, "cz": {"space": {}, "ground": {}}})
            kind = faction["kinds"].setdefault(record["kind"], {"kind": record["kind"], "label": KINDS.get(record["kind"], record["kind"]),
                                                                 "amount": 0, "count": 0, "credits": record["kind"] in CREDIT_KINDS,
                                                                 "bad": record["kind"] in BAD_KINDS})
            kind["amount"] += record["amount"] or 0
            kind["count"] += record["count"] or 0
            if record["kind"] in ("space_cz", "ground_cz"):
                bucket = faction["cz"]["space" if record["kind"] == "space_cz" else "ground"]
                bucket[record["detail"]] = bucket.get(record["detail"], 0) + 1
        detail = {"start": tick_start, "end": end, "label": tick_clock.label(tick_start),
                  "systems": [{**system, "factions": [{**faction, "kinds": sorted(faction["kinds"].values(), key=lambda kind: (kind["bad"], kind["label"]))}
                                                      for faction in sorted(system["factions"].values(), key=lambda item: item["name"].casefold())]}
                              for system in sorted(systems.values(), key=lambda item: item["system"].casefold())]}
        detail["report"] = report(detail)
    return {"periods": [{**row, "label": tick_clock.label(row["start"])} for row in period_list], "detail": detail}


def _credits(value):
    value = float(value or 0)
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            return f"{value / size:.1f}{suffix}"
    return f"{value:.0f}"


def report(detail):
    """A Discord-ready summary of one tick's work (BGS-Tally's layout)."""
    lines = [f"**BGS Report - Tick: {detail['label']}**", ""]
    for system in detail["systems"]:
        lines.append(f"**{system['system']}**")
        for faction in system["factions"]:
            parts = []
            for kind in faction["kinds"]:
                if kind["kind"] in ("space_cz", "ground_cz"):
                    sizes = faction["cz"]["space" if kind["kind"] == "space_cz" else "ground"]
                    text = " ".join(f"{count}{size.upper()}" for size, count in sorted(sizes.items(), key=lambda item: "lmh".index(item[0])))
                    parts.append(f"{'Space' if kind['kind'] == 'space_cz' else 'Ground'} CZ {text}")
                elif kind["kind"] in ("inf", "inf_secondary"):
                    parts.append(f"{'+' if kind['amount'] >= 0 else ''}{int(kind['amount'])} INF{'' if kind['kind'] == 'inf' else ' (secondary)'}")
                elif kind["credits"]:
                    parts.append(f"{kind['label']} {_credits(kind['amount'])}")
                else:
                    parts.append(f"{kind['label']} {int(kind['count'])}")
            lines.append(f"- {faction['name']}: " + ", ".join(parts))
        lines.append("")
    return "\n".join(lines).strip()


def state_catalogue():
    return [{"name": name, "label": row[0], "group": row[1], "tone": row[2], "text": row[3]}
            for name, row in STATES.items() if name != "None"]
