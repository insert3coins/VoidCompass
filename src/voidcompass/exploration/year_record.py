"""What the journals say about a year beyond where you flew (5.5.10), for
Void Wrapped: the fights (bounties, combat bonds, Thargoids, other pilots,
interdictions, who killed you) and the everyday things (missions, dockings,
landings, fuel scooped, engineering, ships bought, promotions).

Read straight from the journal files of that year, a file at a time, and
kept per file until it changes, so telling the year again (or refreshing it
as new journals arrive) only reads what's new. Each event is kept small:
``{"t": unix time, "e": event, "v": a number, "n": a name, "x": a detail}``.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import threading

from voidcompass.core.journal_files import journal_date
from voidcompass.exploration.travel_history import commander_matches

EVENTS = ("Bounty", "FactionKillBond", "CapShipBond", "PVPKill", "Died", "Interdicted", "EscapeInterdiction",
          "Interdiction", "RedeemVoucher", "MissionCompleted", "Docked", "Touchdown", "FuelScoop", "EngineerCraft",
          "ShipyardBuy", "Promotion")
MARKERS = tuple(marker for event in EVENTS + ("Commander", "LoadGame")
                for marker in (f'"event":"{event}"', f'"event": "{event}"'))
COMBAT_RANKS = ("Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly", "Elite",
                "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V")


def _epoch(stamp):
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _name(raw, *keys):
    for key in keys:
        value = raw.get(f"{key}_Localised") or raw.get(key)
        if value:
            return str(value).strip("$;").replace("_name", "")[:80]
    return ""


def compact(raw):
    """One journal event as a small row, or None when it isn't one kept."""
    event = raw.get("event")
    when = _epoch(raw.get("timestamp"))
    if event not in EVENTS or when is None:
        return None
    row = {"t": round(when), "e": event, "v": 0, "n": "", "x": ""}
    if event == "Bounty":
        reward = raw.get("TotalReward")
        if reward is None:
            reward = sum(int((item or {}).get("Reward") or 0) for item in raw.get("Rewards") or ())
        row.update(v=int(reward or 0), n=_name(raw, "Target"), x=_name(raw, "VictimFaction"))
    elif event == "FactionKillBond":
        victim = _name(raw, "VictimFaction")
        row.update(v=int(raw.get("Reward") or 0), n=victim, x="thargoid" if "thargoid" in str(raw.get("VictimFaction") or "").casefold() else "")
    elif event == "CapShipBond":
        row.update(v=int(raw.get("Reward") or 0), n=_name(raw, "VictimFaction"))
    elif event == "PVPKill":
        row.update(n=str(raw.get("Victim") or "")[:80], v=int(raw.get("CombatRank") or 0))
    elif event == "Died":
        killers = raw.get("Killers") or ()
        name = _name(raw, "KillerName") or (_name(killers[0], "Name") if killers and isinstance(killers[0], dict) else "")
        row.update(n=name, x=_name(raw, "KillerShip") or (_name(killers[0], "Ship") if killers and isinstance(killers[0], dict) else ""))
    elif event == "Interdicted":
        row.update(v=1 if raw.get("Submitted") else 0, n=_name(raw, "Interdictor"), x="player" if raw.get("IsPlayer") else "")
    elif event == "Interdiction":
        row.update(v=1 if raw.get("Success") else 0, n=_name(raw, "Interdicted"))
    elif event == "EscapeInterdiction":
        row.update(n=_name(raw, "Interdictor"))
    elif event == "RedeemVoucher":
        row.update(v=int(raw.get("Amount") or 0), n=str(raw.get("Type") or ""))
    elif event == "MissionCompleted":
        row.update(v=int(raw.get("Reward") or 0), n=_name(raw, "LocalisedName", "Name"))
    elif event == "Docked":
        row.update(n=str(raw.get("StationName") or "")[:80])
    elif event == "Touchdown":
        if raw.get("PlayerControlled") is False:
            return None
        row.update(n=str(raw.get("Body") or "")[:80])
    elif event == "FuelScoop":
        row.update(v=float(raw.get("Scooped") or 0))
    elif event == "EngineerCraft":
        row.update(n=str(raw.get("Engineer") or "")[:60], x=_name(raw, "BlueprintName"))
    elif event == "ShipyardBuy":
        row.update(v=int(raw.get("ShipPrice") or 0), n=_name(raw, "ShipType"))
    elif event == "Promotion":
        if raw.get("Combat") is None:
            return None
        rank = int(raw.get("Combat") or 0)
        row.update(v=rank, n=COMBAT_RANKS[rank] if 0 <= rank < len(COMBAT_RANKS) else str(rank))
    return row


class YearRecord:
    """The kept rows of every journal read, per file, for one commander."""

    def __init__(self):
        self.lock = threading.Lock()
        self._files = {}

    def events(self, journal_path, start, end, commander=None, fid=None):
        """Every kept event from ``start`` to ``end`` (unix times), oldest first."""
        if not journal_path or not os.path.isdir(journal_path):
            return []
        out = []
        for name in os.listdir(journal_path):
            if not (name.startswith("Journal.") and name.endswith(".log")):
                continue
            began = journal_date(name)
            # A journal begun more than a day before the year can't reach into it.
            if began is not None and not start - 86400 <= began.timestamp() < end:
                continue
            path = os.path.join(journal_path, name)
            try:
                signature = (os.path.getsize(path), int(os.path.getmtime(path)), commander or "", fid or "")
            except OSError:
                continue
            with self.lock:
                held = self._files.get(name)
            if held is None or held[0] != signature:
                held = (signature, self._read(path, commander, fid))
                with self.lock:
                    self._files[name] = held
            out.extend(row for row in held[1] if start <= row["t"] < end)
        out.sort(key=lambda row: row["t"])
        return out

    @staticmethod
    def _read(path, commander, fid):
        rows = []
        active = not bool(commander or fid)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not any(marker in line for marker in MARKERS):
                        continue
                    try:
                        raw = json.loads(line)
                    except ValueError:
                        continue
                    if raw.get("event") in ("Commander", "LoadGame"):
                        active = commander_matches(raw, commander, fid)
                        continue
                    if active:
                        row = compact(raw)
                        if row:
                            rows.append(row)
        except OSError:
            return []
        return rows
