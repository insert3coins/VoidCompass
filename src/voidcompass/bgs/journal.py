"""The BGS from the journal: faction snapshots on arrival, and your BGS work.

``BgsJournal.observe(raw)`` takes one raw journal event and returns what it
means for the BGS as a list of records:

* ``("snapshot", {...})`` - a system's factions, influence, states and
  conflicts, as FSDJump / Location / CarrierJump give them.
* ``("activity", {...})`` - something you did that moves a faction's
  influence: mission INF, failed missions, bounties and combat bonds handed
  in, trade profit and black market sales, cartographic and exobiology data,
  search and rescue, space and ground conflict zones won, capital ship bonds,
  and murders.
* ``("mission", {...})`` / ``("mission_done", id)`` - missions taken, so a
  failed mission can be put against the faction that gave it.

The same code reads the live journal and the whole history, so both count
the same. How work is counted follows BGS-Tally (MIT): mission INF from
FactionEffects, election and war missions with no INF counted as +1, trade
profit against the average price paid, a conflict zone counted once on its
first combat bond (ground zone size from the bond's value).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from voidcompass.bgs.states import HAPPINESS, STATES, clean

_ARRIVALS = ("FSDJump", "Location", "CarrierJump")
CZ_GROUND_LOW_CB_MAX = 5000
CZ_GROUND_MED_CB_MAX = 38000
CZ_WINDOW_S = 300
STATES_WAR = {"War", "CivilWar"}
MISSIONS_ELECTION = {
    "Mission_AltruismCredits_name", "Mission_Collect_name", "Mission_Collect_Industrial_name",
    "Mission_Courier_name", "Mission_Courier_Boom_name", "Mission_Courier_Democracy_name", "Mission_Courier_Elections_name",
    "Mission_Courier_Expansion_name", "Mission_Delivery_name", "Mission_Delivery_Agriculture_name", "Mission_Delivery_Boom_name",
    "Mission_Delivery_Confederacy_name", "Mission_Delivery_Democracy_name", "Mission_Mining_name", "Mission_Mining_Boom_name",
    "Mission_Mining_Expansion_name", "Mission_OnFoot_Collect_MB_name", "Mission_OnFoot_Salvage_MB_name",
    "Mission_OnFoot_Salvage_BS_MB_name", "Mission_PassengerBulk_name", "Mission_PassengerBulk_AIDWORKER_ARRIVING_name",
    "Mission_PassengerBulk_BUSINESS_ARRIVING_name", "Mission_PassengerBulk_POLITICIAN_ARRIVING_name",
    "Mission_PassengerBulk_SECURITY_ARRIVING_name", "Mission_PassengerVIP_name", "Mission_PassengerVIP_CEO_BOOM_name",
    "Mission_PassengerVIP_CEO_EXPANSION_name", "Mission_PassengerVIP_Explorer_EXPANSION_name",
    "Mission_PassengerVIP_Tourist_ELECTION_name", "Mission_PassengerVIP_Tourist_BOOM_name", "Mission_Rescue_Elections_name",
    "Mission_Salvage_name", "Mission_Salvage_Planet_name", "MISSION_Salvage_Refinery_name", "MISSION_Scan_name",
    "Mission_Sightseeing_name", "Mission_Sightseeing_Celebrity_ELECTION_name", "Mission_Sightseeing_Tourist_BOOM_name",
    "Chain_HelpFinishTheOrder_name",
}
MISSIONS_WAR = {
    "Mission_Assassinate_Legal_CivilWar_name", "Mission_Assassinate_Legal_War_name",
    "Mission_Massacre_Conflict_CivilWar_name", "Mission_Massacre_Conflict_War_name",
    "Mission_OnFoot_Assassination_Covert_MB_name", "Mission_OnFoot_Onslaught_Offline_MB_name",
}
SEARCH_RESCUE = {
    "damagedescapepod": "Escape pods", "occupiedcryopod": "Occupied escape pods", "thargoidpod": "Thargoid pods",
    "usscargoblackbox": "Black boxes", "wreckagecomponents": "Wreckage components", "personaleffects": "Personal effects",
    "politicalprisoner": "Political prisoners", "hostage": "Hostages",
}
KINDS = {
    "inf": "Mission influence", "inf_secondary": "Mission influence (other factions)", "mission_failed": "Missions failed",
    "bounties": "Bounties", "bonds": "Combat bonds", "trade_profit": "Trade profit", "trade_loss": "Trade at a loss",
    "trade_buy": "Trade bought", "black_market": "Black market", "cartography": "Cartographic data",
    "exobiology": "Exobiology data", "search_rescue": "Search and rescue", "space_cz": "Space conflict zones",
    "ground_cz": "Ground conflict zones", "capship": "Capital ship bonds", "murder": "Murders", "ground_murder": "On-foot murders",
}


def journal_time(timestamp):
    try:
        return datetime.strptime(str(timestamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def event_uid(raw):
    """The same event, live or read again from history, has the same id."""
    text = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


def snapshot_from(raw):
    """A system's BGS picture from an arrival event, or None (no factions)."""
    factions = [row for row in raw.get("Factions") or () if isinstance(row, dict) and row.get("Name")]
    if not factions or raw.get("SystemAddress") is None:
        return None

    def states(rows):
        return [{"state": str(item.get("State") or ""), "trend": item.get("Trend")} for item in rows or () if isinstance(item, dict)]

    controlling = (raw.get("SystemFaction") or {}).get("Name") if isinstance(raw.get("SystemFaction"), dict) else raw.get("SystemFaction")
    conflicts = []
    for row in raw.get("Conflicts") or ():
        if not isinstance(row, dict):
            continue
        sides = []
        for key in ("Faction1", "Faction2"):
            side = row.get(key) or {}
            sides.append({"name": side.get("Name") or "", "stake": side.get("Stake") or "", "won_days": int(side.get("WonDays") or 0)})
        conflicts.append({"type": str(row.get("WarType") or ""), "status": str(row.get("Status") or ""), "sides": sides})
    return {
        "ts": journal_time(raw.get("timestamp")), "system_address": raw.get("SystemAddress"), "system": raw.get("StarSystem") or "",
        "source": "journal", "controlling": controlling or "", "population": int(raw.get("Population") or 0),
        "security": clean(raw.get("SystemSecurity_Localised") or raw.get("SystemSecurity")),
        "economy": clean(raw.get("SystemEconomy_Localised") or raw.get("SystemEconomy")),
        "second_economy": clean(raw.get("SystemSecondEconomy_Localised") or raw.get("SystemSecondEconomy")),
        "government": clean(raw.get("SystemGovernment_Localised") or raw.get("SystemGovernment")),
        "allegiance": raw.get("SystemAllegiance") or "", "star_pos": raw.get("StarPos"),
        "powers": list(raw.get("Powers") or ()), "power_state": raw.get("PowerplayState") or "",
        "controlling_power": raw.get("ControllingPower") or "",
        "factions": [{
            "name": row["Name"], "influence": float(row.get("Influence") or 0), "state": str(row.get("FactionState") or "None"),
            "government": clean(row.get("Government")), "allegiance": row.get("Allegiance") or "",
            "happiness": row.get("Happiness_Localised") or HAPPINESS.get(row.get("Happiness"), ""),
            "reputation": row.get("MyReputation"), "squadron": bool(row.get("SquadronFaction")),
            "active": [item["state"] for item in states(row.get("ActiveStates"))],
            "pending": states(row.get("PendingStates")), "recovering": states(row.get("RecoveringStates")),
        } for row in factions],
        "conflicts": conflicts,
    }


class BgsJournal:
    """What happens in the journal, as BGS records."""

    def __init__(self, missions=None):
        self.system_address = None
        self.system = ""
        self.factions = set()
        self.faction_states = {}
        self.station_faction = ""
        self.station_type = ""
        self.settlement = None
        self.space_cz = None
        self.targets = {}
        self.missions = dict(missions or {})

    # -- the journal -----------------------------------------------------
    def observe(self, raw):
        event = raw.get("event") if isinstance(raw, dict) else None
        handler = getattr(self, f"_on_{event}", None) if event else None
        if handler is None:
            return []
        try:
            return handler(raw) or []
        except (KeyError, TypeError, ValueError):
            return []

    def _activity(self, raw, kind, faction, amount=0, count=1, detail="", system_address=None, system=None, suffix=""):
        if not faction:
            return None
        return ("activity", {
            "uid": f"{event_uid(raw)}{suffix}", "ts": journal_time(raw.get("timestamp")), "kind": kind, "faction": faction,
            "amount": amount, "count": count, "detail": detail,
            "system_address": self.system_address if system_address is None else system_address,
            "system": self.system if system is None else system,
        })

    def _arrive(self, raw):
        if raw.get("event") == "CarrierJump" and not raw.get("Docked") and not raw.get("OnFoot"):
            return []
        if raw.get("SystemAddress") != self.system_address:
            self.settlement = self.space_cz = None
            self.targets = {}
        self.system_address = raw.get("SystemAddress")
        self.system = raw.get("StarSystem") or ""
        self.station_faction = ((raw.get("StationFaction") or {}).get("Name") or "") if raw.get("Docked") else ""
        self.station_type = raw.get("StationType") or "" if raw.get("Docked") else ""
        snap = snapshot_from(raw)
        self.factions = {row["name"] for row in (snap or {}).get("factions", ())}
        self.faction_states = {row["name"]: row["state"] for row in (snap or {}).get("factions", ())}
        return [("snapshot", snap)] if snap else []

    _on_FSDJump = _on_Location = _on_CarrierJump = _arrive

    def _on_Docked(self, raw):
        self.station_faction = (raw.get("StationFaction") or {}).get("Name") or ""
        self.station_type = raw.get("StationType") or ""
        return []

    def _on_Undocked(self, raw):
        self.station_faction = self.station_type = ""
        return []

    def _on_SupercruiseEntry(self, raw):
        self.settlement = self.space_cz = None
        return []

    def _on_ApproachSettlement(self, raw):
        self.settlement = {"ts": journal_time(raw.get("timestamp")), "name": raw.get("Name_Localised") or raw.get("Name") or "", "size": None}
        self.space_cz = None
        return []

    def _on_SupercruiseDestinationDrop(self, raw):
        kind = str(raw.get("Type") or "").casefold()
        for prefix, size in (("$warzone_pointrace_low", "l"), ("$warzone_pointrace_med", "m"), ("$warzone_pointrace_high", "h")):
            if kind.startswith(prefix):
                self.space_cz = {"ts": journal_time(raw.get("timestamp")), "size": size, "counted": False}
                self.settlement = None
        return []

    def _on_ShipTargeted(self, raw):
        if raw.get("Faction") and raw.get("PilotName"):
            key = raw.get("PilotName") if str(raw.get("PilotName")).startswith("$ShipName_Police") else raw.get("PilotName_Localised")
            self.targets[key] = raw.get("Faction")
            if len(self.targets) > 64:
                self.targets.pop(next(iter(self.targets)))
        return []

    # -- missions --------------------------------------------------------
    def _on_MissionAccepted(self, raw):
        mission = {"mission_id": raw.get("MissionID"), "faction": raw.get("Faction") or "", "name": raw.get("Name") or "",
                   "target_faction": raw.get("TargetFaction") or "", "system": self.system, "system_address": self.system_address,
                   "ts": journal_time(raw.get("timestamp"))}
        self.missions[mission["mission_id"]] = mission
        return [("mission", mission)]

    def _on_MissionCompleted(self, raw):
        mission = self.missions.pop(raw.get("MissionID"), None) or {}
        out = []
        for index, effect in enumerate(raw.get("FactionEffects") or ()):
            faction = effect.get("Faction") or mission.get("target_faction") or ""
            primary = faction == raw.get("Faction")
            influence = [row for row in effect.get("Influence") or () if isinstance(row, dict)]
            for row_index, row in enumerate(influence):
                points = len(str(row.get("Influence") or ""))
                good = row.get("Trend") in ("UpGood", "DownGood")
                address = row.get("SystemAddress")
                system = self.system if address == self.system_address else mission.get("system") if address == mission.get("system_address") else ""
                record = self._activity(raw, "inf" if primary else "inf_secondary", faction, amount=points if good else -points,
                                        count=1, detail=raw.get("LocalisedName") or raw.get("Name") or "",
                                        system_address=address, system=system, suffix=f":{index}:{row_index}")
                if record:
                    out.append(record)
            if not influence and primary and mission.get("system"):
                state = self.faction_states.get(faction) if mission.get("system_address") == self.system_address else None
                bonus = 1 if raw.get("Name") in MISSIONS_ELECTION and state == "Election" else \
                    2 if raw.get("Name") in MISSIONS_WAR and state in STATES_WAR else 0
                if bonus:
                    record = self._activity(raw, "inf", faction, amount=bonus, detail=raw.get("LocalisedName") or raw.get("Name") or "",
                                            system_address=mission.get("system_address"), system=mission.get("system"), suffix=f":{index}")
                    if record:
                        out.append(record)
        return out + [("mission_done", raw.get("MissionID"))]

    def _on_MissionFailed(self, raw):
        mission = self.missions.pop(raw.get("MissionID"), None)
        out = [("mission_done", raw.get("MissionID"))]
        if mission:
            record = self._activity(raw, "mission_failed", mission["faction"], detail=raw.get("LocalisedName") or raw.get("Name") or "",
                                    system_address=mission.get("system_address"), system=mission.get("system"))
            if record:
                out.insert(0, record)
        return out

    def _on_MissionAbandoned(self, raw):
        self.missions.pop(raw.get("MissionID"), None)
        return [("mission_done", raw.get("MissionID"))]

    # -- vouchers, data, trade -------------------------------------------
    def _on_RedeemVoucher(self, raw):
        kind = str(raw.get("Type") or "").casefold()
        out = []
        if kind == "bounty":
            for index, row in enumerate(raw.get("Factions") or ()):
                amount = int(row.get("Amount") or 0)
                if self.station_type == "FleetCarrier":
                    amount //= 2  # a carrier's broker takes half to the faction
                record = self._activity(raw, "bounties", row.get("Faction") or "", amount=amount, suffix=f":{index}")
                if record and row.get("Faction") in self.factions:
                    out.append(record)
        elif kind == "combatbond":
            record = self._activity(raw, "bonds", raw.get("Faction") or "", amount=int(raw.get("Amount") or 0))
            if record and raw.get("Faction") in self.factions:
                out.append(record)
        return out

    def _on_SellExplorationData(self, raw):
        total = max(int(raw.get("TotalEarnings") or 0), int(raw.get("BaseValue") or 0) + int(raw.get("Bonus") or 0))
        record = self._activity(raw, "cartography", self.station_faction, amount=total)
        return [record] if record and total else []

    _on_MultiSellExplorationData = _on_SellExplorationData

    def _on_SellOrganicData(self, raw):
        total = sum(int(row.get("Value") or 0) + int(row.get("Bonus") or 0) for row in raw.get("BioData") or ())
        record = self._activity(raw, "exobiology", self.station_faction, amount=total)
        return [record] if record and total else []

    def _on_MarketBuy(self, raw):
        if self.station_type == "FleetCarrier":
            return []
        record = self._activity(raw, "trade_buy", self.station_faction, amount=int(raw.get("TotalCost") or 0),
                                count=int(raw.get("Count") or 0), detail=raw.get("Type_Localised") or raw.get("Type") or "")
        return [record] if record else []

    def _on_MarketSell(self, raw):
        if self.station_type == "FleetCarrier":
            return []
        profit = int(raw.get("TotalSale") or 0) - int(raw.get("Count") or 0) * int(raw.get("AvgPricePaid") or 0)
        kind = "black_market" if raw.get("BlackMarket") else "trade_profit" if profit >= 0 else "trade_loss"
        record = self._activity(raw, kind, self.station_faction, amount=profit, count=int(raw.get("Count") or 0),
                                detail=raw.get("Type_Localised") or raw.get("Type") or "")
        return [record] if record else []

    def _on_SearchAndRescue(self, raw):
        key = str(raw.get("Name") or "").casefold()
        if key not in SEARCH_RESCUE or not int(raw.get("Count") or 0):
            return []
        record = self._activity(raw, "search_rescue", self.station_faction, amount=int(raw.get("Reward") or 0),
                                count=int(raw.get("Count") or 0), detail=SEARCH_RESCUE[key])
        return [record] if record else []

    # -- combat ----------------------------------------------------------
    def _recent(self, place, raw):
        now = journal_time(raw.get("timestamp")) or 0
        if not place or now - (place.get("ts") or 0) > CZ_WINDOW_S:
            return False
        place["ts"] = now
        return True

    def _on_FactionKillBond(self, raw):
        faction = raw.get("AwardingFaction") or ""
        if str(raw.get("VictimFaction") or "").casefold() == "$faction_thargoid;" or faction not in self.factions:
            return []
        if self._recent(self.settlement, raw):
            reward = int(raw.get("Reward") or 0)
            size = "l" if reward < CZ_GROUND_LOW_CB_MAX else "m" if reward < CZ_GROUND_MED_CB_MAX else "h"
            order = "lmh"
            previous = self.settlement.get("size")
            if previous and order.index(size) <= order.index(previous):
                return []
            self.settlement["size"] = size
            # One zone per settlement visit: a bigger bond re-sizes it.
            record = self._activity(raw, "ground_cz", faction, detail=size,
                                    suffix=f":gcz:{self.settlement['name']}")
            record[1]["uid"] = f"gcz:{self.system_address}:{self.settlement['name']}:{int(self.settlement.get('start', self.settlement['ts']) // 60)}"
            self.settlement.setdefault("start", self.settlement["ts"])
            return [("activity_upsert", record[1])]
        if self._recent(self.space_cz, raw) and not self.space_cz.get("counted"):
            self.space_cz["counted"] = True
            record = self._activity(raw, "space_cz", faction, detail=self.space_cz["size"])
            return [record] if record else []
        return []

    def _on_CapShipBond(self, raw):
        if not self.space_cz:
            return []
        record = self._activity(raw, "capship", raw.get("AwardingFaction") or "", amount=int(raw.get("Reward") or 0))
        return [record] if record and raw.get("AwardingFaction") in self.factions else []

    def _on_CommitCrime(self, raw):
        kind = raw.get("CrimeType")
        if kind == "murder":
            faction = self.targets.pop(raw.get("Victim"), None)
            record = self._activity(raw, "murder", faction or "")
            return [record] if record and faction in self.factions else []
        if kind == "onFoot_murder":
            record = self._activity(raw, "ground_murder", raw.get("Faction") or "")
            return [record] if record and raw.get("Faction") in self.factions else []
        return []


def known_state(name):
    return name in STATES
