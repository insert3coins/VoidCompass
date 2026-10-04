"""EDSM's faction picture of any system: for a system you look up, and the
history behind the charts (EDSM collects it from players' journals)."""

from __future__ import annotations

from voidcompass.bgs.states import STATES

URL = "https://www.edsm.net/api-system-v1/factions"
_ALIASES = {"terroristattack": "Terrorism", "terrorism": "Terrorism"}


def state_key(text):
    """EDSM's "Civil war" / "Pirate attack" -> the journal's CivilWar / PirateAttack."""
    folded = "".join(str(text or "").split()).casefold()
    if not folded:
        return "None"
    if folded in _ALIASES:
        return _ALIASES[folded]
    return next((key for key in STATES if key.casefold() == folded), str(text))


def _states(rows):
    return [{"state": state_key(row.get("state")), "trend": row.get("trend")} for row in rows or () if isinstance(row, dict)]


def from_edsm(data):
    """``(snapshot, points)`` from EDSM's factions reply (showHistory=1)."""
    if not isinstance(data, dict) or not data.get("factions"):
        return None, []
    address = data.get("id64")
    factions, points, latest = [], [], 0
    for row in data.get("factions") or ():
        if not isinstance(row, dict) or not row.get("name"):
            continue
        influence = float(row.get("influence") or 0)
        if influence <= 0:
            continue  # EDSM keeps factions that have left, at 0
        latest = max(latest, int(row.get("lastUpdate") or 0))
        factions.append({
            "name": row["name"], "influence": influence, "state": state_key(row.get("state")),
            "government": row.get("government") or "", "allegiance": row.get("allegiance") or "",
            "happiness": row.get("happiness") or "", "reputation": None, "squadron": False, "player": bool(row.get("isPlayer")),
            "active": [item["state"] for item in _states(row.get("activeStates"))],
            "pending": _states(row.get("pendingStates")), "recovering": _states(row.get("recoveringStates")),
        })
        states = {int(ts): state_key(value) for ts, value in (row.get("stateHistory") or {}).items() if str(ts).isdigit()}
        for ts, value in (row.get("influenceHistory") or {}).items():
            if str(ts).isdigit():
                at = int(ts)
                state = states.get(at) or next((states[t] for t in sorted(states, reverse=True) if t <= at), "")
                points.append((row["name"], float(at), float(value or 0), state))
    if not factions or address is None:
        return None, points
    controlling = (data.get("controllingFaction") or {}).get("name") or ""
    snapshot = {
        "ts": float(latest), "system_address": address, "system": data.get("name") or "", "source": "edsm",
        "controlling": controlling, "population": 0, "security": "", "economy": "", "second_economy": "",
        "government": (data.get("controllingFaction") or {}).get("government") or "",
        "allegiance": (data.get("controllingFaction") or {}).get("allegiance") or "", "star_pos": None,
        "powers": [], "power_state": "", "controlling_power": "",
        "factions": sorted(factions, key=lambda row: -row["influence"]), "conflicts": [],
        "url": data.get("url") or "",
    }
    return snapshot, points
