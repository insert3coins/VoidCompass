"""What the Watcher has seen you do, and its diary (5.7.1, with its own words).

Every live journal event worth remembering becomes one plain line of fact
("Jumped to Achenar, 12.3 light years.") kept in its memory with the session
it happened in: the last HAPPENINGS_KEPT. It learns them whether or not its
own words are on.

With its own words on, the model writes a short diary entry about a finished
session from those lines alone (checked like everything else it writes). The
entries are what it remembers of you: brought up in its own thoughts and
when you talk to it. Its story is never part of this; that stays as written.
"""
from __future__ import annotations

from voidcompass.core import ranks
from voidcompass.overlays import watcher_world

HAPPENINGS_KEPT = 80
DIARY_KEPT = 60
# A session needs this much in it to be worth a diary entry.
DIARY_MINIMUM = 3
DIARY_TRIES = 3
VALUABLE = {"Earthlike body": "an Earth-like world", "Water world": "a water world", "Ammonia world": "an ammonia world"}


def _credits(value):
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return ""


def _name(raw, key):
    return str(raw.get(f"{key}_Localised") or raw.get(key) or "").strip()


def happening(event, raw):
    """A journal event as one plain line of fact, or "" when it isn't worth keeping."""
    raw = raw if isinstance(raw, dict) else {}
    if event == "FSDJump" and raw.get("StarSystem"):
        try:
            far = f", {float(raw.get('JumpDist')):.1f} light years"
        except (TypeError, ValueError):
            far = ""
        return f"Jumped to {raw['StarSystem']}{far}."
    if event == "CarrierJump" and raw.get("StarSystem"):
        return f"Rode the carrier to {raw['StarSystem']}."
    if event == "Docked" and raw.get("StationName"):
        system = f" in {raw['StarSystem']}" if raw.get("StarSystem") else ""
        return f"Docked at {_name(raw, 'StationName')}{system}."
    if event == "Touchdown" and raw.get("Body") and raw.get("PlayerControlled", True):
        return f"Landed on {raw['Body']}."
    if event == "Disembark" and raw.get("OnPlanet") and raw.get("Body"):
        return f"Stepped out onto {raw['Body']}."
    if event == "LaunchSRV":
        return "Took the SRV out."
    if event == "Scan" and raw.get("BodyName"):
        body = raw["BodyName"]
        planet = str(raw.get("PlanetClass") or "")
        star = str(raw.get("StarType") or "")
        first = raw.get("WasDiscovered") is False
        if planet in VALUABLE:
            return f"Scanned {body}, {VALUABLE[planet]}{', and nobody had before' if first else ''}."
        if star in {"N", "H"}:
            return f"Scanned {body}, a {'neutron star' if star == 'N' else 'black hole'}."
        if raw.get("TerraformState") == "Terraformable" and first:
            return f"Scanned {body}, a terraformable world nobody had found before."
        return ""
    if event == "FSSAllBodiesFound" and raw.get("SystemName"):
        return f"Found every body in {raw['SystemName']}."
    if event == "SAAScanComplete" and raw.get("BodyName"):
        return f"Mapped {raw['BodyName']}."
    if event == "SAASignalsFound" and raw.get("BodyName"):
        life = sum(int(row.get("Count") or 0) for row in raw.get("Signals") or []
                   if isinstance(row, dict) and "Biological" in str(row.get("Type") or ""))
        return f"Found {life} kinds of life on {raw['BodyName']}." if life else ""
    if event == "ScanOrganic" and raw.get("ScanType") == "Analyse":
        species = _name(raw, "Species")
        return f"Logged {species} in the genetic sampler." if species else ""
    if event == "CodexEntry" and raw.get("IsNewEntry"):
        entry = _name(raw, "Name")
        return f"Logged a new Codex entry: {entry}." if entry else ""
    if event == "SellOrganicData":
        total = sum(int(row.get("Value") or 0) + int(row.get("Bonus") or 0) for row in raw.get("BioData") or [] if isinstance(row, dict))
        return f"Sold exobiology data for {total:,} credits." if total else ""
    if event in {"MultiSellExplorationData", "SellExplorationData"}:
        total = _credits(raw.get("TotalEarnings") or raw.get("BaseValue"))
        return f"Sold exploration data for {total} credits." if total and total != "0" else ""
    if event == "MarketSell" and raw.get("TotalSale"):
        try:
            if int(raw["TotalSale"]) < 100_000:
                return ""
        except (TypeError, ValueError):
            return ""
        return f"Sold {raw.get('Count')} tonnes of {_name(raw, 'Type')} for {_credits(raw['TotalSale'])} credits."
    if event == "MissionCompleted" and raw.get("LocalisedName"):
        return f"Completed a mission: {str(raw['LocalisedName'])[:70]}."
    if event == "Died":
        killer = _name(raw, "KillerName")
        return f"The ship was destroyed{f' by {killer}' if killer else ''}."
    if event == "Interdicted":
        return "Pulled out of supercruise by an interdiction."
    if event == "EscapeInterdiction":
        return "Escaped an interdiction."
    if event == "Promotion":
        for key, value in raw.items():
            said = ranks.said(key, value)
            if said:
                return f"Promoted: {said}."
        return ""
    if event in {"ShipyardSwap", "ShipyardBuy"}:
        ship = watcher_world.ship_name(raw.get("ShipType")) or _name(raw, "ShipType")
        return f"{'Bought' if event == 'ShipyardBuy' else 'Switched to'} a {ship}." if ship else ""
    if event == "Shutdown":
        return "Shut the game down for the day."
    return ""


def record(memory, event, raw, session, now):
    """Keep what a journal event says, if it says something. True when kept."""
    text = happening(event, raw)
    if not text:
        return False
    rows = memory.setdefault("happened", [])
    if rows and rows[-1].get("text") == text:
        return False
    rows.append({"t": round(float(now), 1), "s": session, "text": text})
    del rows[:-HAPPENINGS_KEPT]
    return True


def recent(memory, limit=8, session=None):
    rows = [row for row in memory.get("happened") or [] if isinstance(row, dict)]
    if session is not None:
        rows = [row for row in rows if row.get("s") == session]
    return [str(row.get("text") or "") for row in rows[-limit:]]


def diary_due(memory, current_session):
    """(session, lines) of the oldest finished session still without a diary
    entry, or None."""
    written = {row.get("s") for row in memory.get("diary") or [] if isinstance(row, dict)}
    tried = memory.get("diary_tried") or {}
    sessions = []
    for row in memory.get("happened") or []:
        session = row.get("s") if isinstance(row, dict) else None
        if session is not None and session != current_session and session not in sessions:
            sessions.append(session)
    for session in sessions:
        if session in written or int(tried.get(str(session), 0)) >= DIARY_TRIES:
            continue
        lines = recent(memory, HAPPENINGS_KEPT, session)
        if len(lines) >= DIARY_MINIMUM:
            return session, lines
    return None


def tried(memory, session):
    attempts = memory.setdefault("diary_tried", {})
    attempts[str(session)] = int(attempts.get(str(session), 0)) + 1
    for key in list(attempts)[:-40]:
        attempts.pop(key, None)


def add_diary(memory, session, text, when):
    rows = memory.setdefault("diary", [])
    rows.append({"s": session, "at": round(float(when), 1), "text": str(text)})
    del rows[:-DIARY_KEPT]


def diary(memory, limit=3):
    return [str(row.get("text") or "") for row in (memory.get("diary") or [])[-limit:] if isinstance(row, dict)]
