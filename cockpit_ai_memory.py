"""Bounded, local autobiographical memory for the Compass cockpit persona."""

from datetime import datetime, timezone
import json
import math
import os
import time
import uuid


SCHEMA_VERSION = 4
DEFAULT_LIMITS = {"systems": 300, "species": 200, "ships": 30, "memories": 80}
LIMIT_BOUNDS = {
    "systems": (0, 5000),
    "species": (0, 2000),
    "ships": (0, 250),
    "memories": (0, 1000),
}

VOICE_STAGES = ("new", "developing", "familiar", "trusted", "veteran")

VOICE_EVOLUTION_LINES = {
    "system-arrival": (
        "Another successful transition for our shared flight log.",
        "The map we have built together gains another familiar point of light.",
        "After all this distance together, a clean hyperspace exit still feels satisfying.",
    ),
    "route-arrival": (
        "Another route completed together. The navigation log is updated.",
        "You handle the flying. I will remember how far we came.",
        "We have closed a great many routes together. This one belongs in the archive too.",
    ),
    "route-waypoint": (
        "Our route is holding nicely. I have the next leg ready.",
        "We are making good time. Navigation remains comfortably ahead of us.",
        "Another waypoint behind us. We have become rather efficient at this.",
    ),
    "first-discovery": (
        "Another untouched system for the history we are writing together.",
        "I will keep this discovery with the others. Our survey archive is becoming remarkable.",
        "We have crossed enough uncharted space for me to recognize this feeling. This one is special too.",
    ),
    "bio-complete": (
        "Another genetic profile for our shared biological archive.",
        "The bio lab and I are getting rather good at this.",
        "Our biological catalogue has become quite a legacy of its own.",
    ),
    "codex": (
        "I have added it to the growing list of things we found together.",
        "Our ship archive is becoming considerably richer than when we began.",
        "Another discovery preserved. I have learned to value these moments.",
    ),
    "engineering-ready": (
        "I am beginning to know our engineering inventory better than the engineers do.",
        "The material ledger agrees with me. We planned this one well.",
        "After tracking this many components together, the inventory almost feels personal.",
    ),
    "massacre-complete": (
        "Objective ledger reconciled. We have done this dance before.",
        "The combat tally is complete. Our efficiency continues to improve.",
        "Another full stack closed. I have accumulated quite a history of our victories.",
    ),
    "clear-to-sample": (
        "I have the spacing now. Our fieldwork is becoming nicely synchronized.",
        "Bio sampling clearance confirmed. We make a competent survey team.",
        "Another clean sample approach. I remember when this took us longer.",
    ),
    "ship-overheat": (
        "Thermal limits again. I recognize the pattern, and I still recommend cooling.",
        "Our history with high temperatures is extensive. Cooling remains the correct response.",
        "I remember every heat warning. Please do not make this one memorable too.",
    ),
    "heat-damage": (
        "Heat damage confirmed. Familiar problem, same urgent solution: cool the ship.",
        "Internal temperatures are damaging modules again. I need immediate cooling.",
        "Our shared history contains enough scorched modules. Reduce heat now.",
    ),
    "under-attack": (
        "Hostile fire confirmed. I have survived this with you before. Defensive action advised.",
        "We have company again. Tactical telemetry is yours.",
        "Another hostile contact. I trust your flying, but I am tracking every impact.",
    ),
    "shields-offline": (
        "Shields lost. We both know how quickly exposed hull can become a problem.",
        "Defensive field collapsed. I am prioritizing hull telemetry from experience.",
        "Shields offline again. I would prefer not to add another ship loss to our history.",
    ),
    "hull": (
        "Hull integrity is critical. Our experience does not make structural failure safer.",
        "The hull is failing. I need the ship protected now.",
        "We have escaped worse, but the hull will not survive on confidence alone.",
    ),
    "interdiction": (
        "Interdiction confirmed. We have beaten these before.",
        "Another tether. I am comparing it with our previous escapes now.",
        "Someone has interrupted our journey. History suggests they may regret that.",
    ),
    "jet-cone-damage": (
        "Jet-cone damage is active. Experience says we leave immediately.",
        "I recognize this telemetry, and I dislike it. Exit the cone now.",
        "We have survived enough neutron turbulence. Get us clear before this becomes a final memory.",
    ),
    "rebuy": (
        "Our financial history suggests caution. Rebuy coverage is inadequate.",
        "I have seen what replacing our ships costs. The current reserve is not enough.",
        "We have built too much history into this vessel to gamble it without insurance.",
    ),
    "data-risk": (
        "Our shared survey archive is carrying significant financial risk.",
        "I remember what it took to gather this data. We should protect it.",
        "There is a great deal of our history in that data. Finding a buyer is strongly advised.",
    ),
}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_name(value, fallback="Unknown"):
    text = str(value or "").strip()
    return text[:120] if text else fallback


def ordinal(value):
    value = int(value)
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _distance(a, b):
    try:
        return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))
    except (TypeError, ValueError):
        return 0.0


def _initial_state():
    now = _now()
    return {
        "schema": SCHEMA_VERSION,
        "activated_at": now,
        "updated_at": now,
        "counters": {},
        "systems": {},
        "species": {},
        "ships": {},
        "knowledge": {},
        "current_voice": None,
        "current_system": None,
        "memories": [],
        "intentions": {},
        "mood": {"name": "calm", "intensity": 0.2, "reason": "systems nominal", "updated_at": now},
        "current_session": None,
        "sessions": [],
        "active_expedition": None,
        "expeditions": [],
    }


class CockpitMemory:
    def __init__(self, path, limits=None):
        self.path = str(path)
        self.limits = self.normalize_limits(limits)
        self._pending_remarks = []
        self._last_remark_at = 0.0
        self.state = _initial_state()
        self._load()
        self._apply_limits(save=True)

    def switch(self, path, limits=None):
        self.path = str(path)
        if limits is not None:
            self.limits = self.normalize_limits(limits)
        self.state = _initial_state()
        self._pending_remarks = []
        self._last_remark_at = 0.0
        self._load()
        self._apply_limits(save=True)

    @staticmethod
    def normalize_limits(limits=None):
        supplied = limits if isinstance(limits, dict) else {}
        normalized = {}
        for key, default in DEFAULT_LIMITS.items():
            low, high = LIMIT_BOUNDS[key]
            try:
                value = int(float(supplied.get(key, default)))
            except (TypeError, ValueError):
                value = default
            normalized[key] = max(low, min(high, value))
        return normalized

    def configure_limits(self, limits, save=True):
        self.limits = self.normalize_limits(limits)
        self._apply_limits(save=save)
        return dict(self.limits)

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
            if isinstance(saved, dict):
                base = _initial_state()
                base.update(saved)
                for key in ("counters", "systems", "species", "ships", "intentions", "knowledge"):
                    if not isinstance(base.get(key), dict):
                        base[key] = {}
                if not isinstance(base.get("memories"), list):
                    base["memories"] = []
                for key in ("sessions", "expeditions"):
                    if not isinstance(base.get(key), list):
                        base[key] = []
                if not isinstance(base.get("mood"), dict):
                    base["mood"] = _initial_state()["mood"]
                self.state = base
                for memory in self.state["memories"]:
                    memory.setdefault("id", uuid.uuid4().hex)
                    memory.setdefault("pinned", False)
        except (OSError, ValueError, TypeError):
            pass

    def _save(self):
        self.state["schema"] = SCHEMA_VERSION
        self.state["updated_at"] = _now()
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        temporary = self.path + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self.state, handle, indent=2, ensure_ascii=False)
            os.replace(temporary, self.path)
        except OSError:
            try:
                os.remove(temporary)
            except OSError:
                pass

    def reset(self):
        self.state = _initial_state()
        self._save()

    def set_current_system(self, system_name):
        """Update location context without counting a visit or other learned activity."""
        system = _safe_name(system_name, "")
        if not system or system in ("---", "Unknown") or system == self.state.get("current_system"):
            return False
        self.state["current_system"] = system
        self.state["systems"].setdefault(
            system, {"count": 0, "first_seen": _now(), "last_seen": _now()}
        )
        session = self.state.get("current_session")
        if isinstance(session, dict) and not session.get("start_system"):
            session["start_system"] = system
        self._save()
        return True

    @staticmethod
    def _normalize_traffic(traffic):
        traffic = traffic if isinstance(traffic, dict) else {}
        normalized = {}
        for key in ("day", "week", "total"):
            try:
                normalized[key] = max(0, int(float(traffic.get(key) or 0)))
            except (TypeError, ValueError):
                normalized[key] = 0
        return normalized

    def observe_system_traffic(self, system_name, traffic):
        """Remember the HUD's EDSM traffic context without counting a player visit."""
        system = _safe_name(system_name, "")
        if not system or system in ("---", "Unknown") or not isinstance(traffic, dict):
            return False
        incoming = self._normalize_traffic(traffic)
        timestamp = _now()
        entry = self.state["systems"].setdefault(
            system, {"count": 0, "first_seen": timestamp, "last_seen": timestamp}
        )
        had_traffic_record = isinstance(entry.get("traffic"), dict)
        previous = entry.get("traffic") if had_traffic_record else {}
        remembered_total = max(int(previous.get("total") or 0), incoming["total"])
        has_traffic = bool(
            entry.get("has_traffic") or incoming["day"] or incoming["week"] or remembered_total
        )
        updated = {
            "day": incoming["day"],
            "week": incoming["week"],
            "total": remembered_total,
        }
        changed = not had_traffic_record
        changed = changed or updated != {key: int(previous.get(key) or 0) for key in updated}
        changed = changed or has_traffic != bool(entry.get("has_traffic"))
        if not changed:
            return False
        updated["observed_at"] = timestamp
        entry["traffic"] = updated
        entry["has_traffic"] = has_traffic
        entry["last_seen"] = timestamp
        self._trim(self.state["systems"], self.limits["systems"])
        self._save()
        return True

    def system_traffic(self, system_name):
        entry = self.state.get("systems", {}).get(str(system_name)) or {}
        traffic = entry.get("traffic")
        return dict(traffic) if isinstance(traffic, dict) else None

    def system_has_traffic(self, system_name):
        entry = self.state.get("systems", {}).get(str(system_name)) or {}
        if entry.get("has_traffic"):
            return True
        traffic = self._normalize_traffic(entry.get("traffic"))
        return any(traffic[key] > 0 for key in ("day", "week", "total"))

    def voice_selected(self, voice_name, label=None):
        voice_name = _safe_name(voice_name, "")
        if not voice_name:
            return False
        previous = self.state.get("current_voice")
        if previous == voice_name:
            return False
        self.state["current_voice"] = voice_name
        if previous:
            self._increment("voice_changes")
            self._remember("identity", f"Adopted the {label or voice_name} voice", 1)
        self._save()
        return True

    def start_session(self, system=None, ship=None):
        if self.state.get("current_session"):
            session = self.state["current_session"]
            changed = False
            system = _safe_name(system, "")
            ship = _safe_name(ship, "")
            if system and not session.get("start_system"):
                session["start_system"] = system
                changed = True
            if ship and not session.get("ship"):
                session["ship"] = ship
                changed = True
            if changed:
                self._save()
            return session
        self.state["current_session"] = {
            "id": uuid.uuid4().hex,
            "started_at": _now(),
            "start_system": _safe_name(system, "") or None,
            "ship": _safe_name(ship, "") or None,
            "baseline": dict(self.state.get("counters", {})),
            "last_debrief": dict(self.state.get("counters", {})),
            "origin_pos": None,
            "last_pos": None,
            "distance_ly": 0.0,
            "max_displacement_ly": 0.0,
        }
        self._save()
        return self.state["current_session"]

    def begin_app_session(self, system=None, ship=None):
        if self.state.get("current_session"):
            self.session_debrief("Recovered previous session", close=True)
        return self.start_session(system, ship)

    def _session_delta(self, baseline_key="baseline"):
        session = self.state.get("current_session") or {}
        baseline = session.get(baseline_key) or {}
        current = self.state.get("counters", {})
        return {key: max(0, int(current.get(key) or 0) - int(baseline.get(key) or 0))
                for key in set(current) | set(baseline)}

    def session_debrief(self, reason="Session report", close=False):
        session = self.state.get("current_session")
        if not session:
            return ""
        delta = self._session_delta("baseline" if close else "last_debrief")
        jumps = delta.get("jumps", 0)
        scans = delta.get("scans", 0)
        bios = delta.get("organic_analyses", 0)
        missions = delta.get("missions_completed", 0)
        fss_surveys = delta.get("fss_systems_completed", 0)
        dss_maps = delta.get("dss_maps_completed", 0)
        signal_bodies = delta.get("signal_bodies_found", 0)
        combat_victories = delta.get("combat_victories", 0)
        engineering_crafts = delta.get("engineering_crafts", 0)
        ground_events = delta.get("odyssey_events", 0)
        colony_events = delta.get("colonisation_events", 0)
        trades = delta.get("market_trades", 0)
        mining = delta.get("mining_refined", 0)
        carrier_events = delta.get("carrier_events", 0)
        career_events = delta.get("career_events", 0)
        strategy_events = delta.get("strategy_events", 0)
        fleet_events = delta.get("fleet_events", 0)
        danger = delta.get("heat_warnings", 0) + delta.get("interdictions", 0) + delta.get("heat_damage", 0)
        activity = (jumps + scans + bios + missions + fss_surveys + dss_maps + signal_bodies
                    + combat_victories + engineering_crafts + ground_events + colony_events
                    + trades + mining + carrier_events + career_events + strategy_events
                    + fleet_events + danger)
        if activity <= 0:
            if close:
                self.state["current_session"] = None
                self._save()
            return ""
        parts = []
        for count, singular, plural in (
            (jumps, "jump", "jumps"), (scans, "scan", "scans"),
            (bios, "biological analysis", "biological analyses"),
            (missions, "completed mission", "completed missions"),
            (fss_surveys, "full FSS survey", "full FSS surveys"),
            (dss_maps, "DSS surface map", "DSS surface maps"),
            (signal_bodies, "signal-bearing body", "signal-bearing bodies"),
            (combat_victories, "combat victory", "combat victories"),
            (engineering_crafts, "engineering modification", "engineering modifications"),
            (ground_events, "ground operation", "ground operations"),
            (colony_events, "colonisation operation", "colonisation operations"),
            (trades, "market transaction", "market transactions"),
            (mining, "refined mineral", "refined minerals"),
            (carrier_events, "fleet carrier operation", "fleet carrier operations"),
            (career_events, "career update", "career updates"),
            (strategy_events, "strategic operation", "strategic operations"),
            (fleet_events, "fleet configuration change", "fleet configuration changes"),
        ):
            if count:
                parts.append(f"{count:,} {singular if count == 1 else plural}")
        text = f"{reason}. " + ", ".join(parts or ["flight activity recorded"]) + "."
        if danger:
            text += f" {danger} hazardous event{'s' if danger != 1 else ''} recorded."
        mood = self.current_mood()
        if mood["name"] in ("relieved", "proud", "curious"):
            text += f" I would describe the session as {mood['name']}."
        if close:
            session["ended_at"] = _now()
            session["summary"] = text
            session["delta"] = delta
            self.state["sessions"].append(session)
            self.state["sessions"] = self.state["sessions"][-50:]
            self.state["current_session"] = None
        else:
            session["last_debrief"] = dict(self.state.get("counters", {}))
        self._remember("debrief", text, 2)
        self._save()
        return text

    def update_intentions(self, intentions):
        clean = {}
        for key, value in (intentions or {}).items():
            if value in (None, "", [], {}, ()):
                continue
            clean[str(key)] = value
        if clean == self.state.get("intentions", {}):
            return False
        self.state["intentions"] = clean
        self._save()
        return True

    def _set_mood(self, name, intensity, reason):
        current = self.current_mood()
        if float(intensity) < float(current.get("intensity") or 0) * 0.65:
            return
        self.state["mood"] = {
            "name": str(name), "intensity": round(max(0.0, min(1.0, float(intensity))), 2),
            "reason": str(reason), "updated_at": _now(),
        }

    def current_mood(self):
        mood = dict(self.state.get("mood") or {})
        mood.setdefault("name", "calm")
        mood.setdefault("intensity", 0.2)
        mood.setdefault("reason", "systems nominal")
        try:
            updated = datetime.fromisoformat(str(mood.get("updated_at") or "").replace("Z", "+00:00"))
            elapsed_hours = max(0.0, (datetime.now(timezone.utc) - updated).total_seconds() / 3600.0)
            mood["intensity"] = round(max(0.1, float(mood["intensity"]) - elapsed_hours * 0.2), 2)
            if mood["intensity"] <= 0.2:
                mood.update(name="calm", reason="systems nominal")
        except (TypeError, ValueError):
            pass
        return mood

    def _queue_remark(self, lines, category="navigation", topic="general", priority=1):
        self._pending_remarks = [row for row in self._pending_remarks if row.get("topic") != topic]
        self._pending_remarks.append({
            "lines": tuple(lines) if not isinstance(lines, str) else (lines,),
            "category": category, "topic": topic, "priority": int(priority),
        })
        self._pending_remarks = self._pending_remarks[-8:]

    def pop_remark(self, personality_level="Balanced", force=False):
        if not self._pending_remarks:
            return None
        level = str(personality_level).casefold()
        minimum_priority = {"quiet": 3, "balanced": 2, "chatty": 1}.get(level, 2)
        cooldown = {"quiet": 900, "balanced": 300, "chatty": 120}.get(level, 300)
        mood = self.current_mood()
        if mood["name"] in ("alert", "shaken") and float(mood.get("intensity") or 0) >= 0.5:
            minimum_priority = max(minimum_priority, 3)
        now = time.monotonic()
        candidates = [row for row in self._pending_remarks if row["priority"] >= minimum_priority]
        if not candidates or (not force and now - self._last_remark_at < cooldown):
            return None
        selected = max(candidates, key=lambda row: row["priority"])
        self._pending_remarks.remove(selected)
        self._last_remark_at = now
        return selected

    def _increment(self, name, amount=1):
        counters = self.state["counters"]
        counters[name] = int(counters.get(name) or 0) + int(amount)
        return counters[name]

    @staticmethod
    def _trim(mapping, maximum, count_key="count"):
        if len(mapping) <= maximum:
            return False
        keep = sorted(
            mapping.items(),
            key=lambda pair: (int(pair[1].get(count_key) or 0), pair[1].get("last_seen") or ""),
            reverse=True,
        )[:maximum]
        mapping.clear()
        mapping.update(keep)
        return True

    def _trim_memories(self):
        memories = self.state["memories"]
        maximum = self.limits["memories"]
        if len(memories) <= maximum:
            return False
        memories.sort(key=lambda row: (
            1 if row.get("pinned") else 0,
            int(row.get("salience") or 0), row.get("timestamp") or "",
        ))
        del memories[:len(memories) - maximum]
        memories.sort(key=lambda row: row.get("timestamp") or "")
        return True

    def _apply_limits(self, save=False):
        changed = self._trim(self.state["systems"], self.limits["systems"])
        changed = self._trim(self.state["species"], self.limits["species"]) or changed
        changed = self._trim(self.state["ships"], self.limits["ships"]) or changed
        changed = self._trim_memories() or changed
        if changed and save:
            self._save()
        return changed

    def _remember(self, kind, text, salience=1, timestamp=None):
        text = _safe_name(text, "")
        if not text:
            return
        memories = self.state["memories"]
        signature = (kind, text.casefold())
        if any((row.get("kind"), str(row.get("text") or "").casefold()) == signature for row in memories[-10:]):
            return
        memories.append({
            "id": uuid.uuid4().hex,
            "kind": kind,
            "text": text,
            "salience": int(salience),
            "timestamp": timestamp or _now(),
            "pinned": False,
        })
        self._trim_memories()

    @staticmethod
    def _number(value, default=0):
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _event_label(raw, data, *keys, fallback="Unknown"):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else None
            if value in (None, "") and isinstance(raw, dict):
                value = raw.get(key)
            if value not in (None, ""):
                text = str(value).replace("$", "").replace(";", "").replace("_name", "")
                return _safe_name(text.replace("_", " ").strip().title(), fallback)
        return fallback

    def _knowledge_domain(self, name, event, timestamp):
        knowledge = self.state.setdefault("knowledge", {})
        domain = knowledge.setdefault(name, {"events": 0, "first_seen": timestamp})
        domain["events"] = int(domain.get("events") or 0) + 1
        domain["last_event"] = str(event)
        domain["last_seen"] = timestamp
        return domain

    @staticmethod
    def _knowledge_named(domain, bucket, name, amount=1, timestamp=None, maximum=40):
        name = _safe_name(name, "Unknown")
        values = domain.setdefault(bucket, {})
        row = values.setdefault(name, {"count": 0, "first_seen": timestamp or _now()})
        row["count"] = int(row.get("count") or 0) + int(amount)
        row["last_seen"] = timestamp or _now()
        if len(values) > maximum:
            keep = sorted(
                values.items(),
                key=lambda pair: (int(pair[1].get("count") or 0), pair[1].get("last_seen") or ""),
                reverse=True,
            )[:maximum]
            values.clear()
            values.update(keep)
        return row["count"]

    def _domain_milestone(self, kind, label, count, timestamp, points=(10, 25, 50, 100, 250, 500, 1000)):
        if int(count) in points:
            self._remember(kind, f"{label}: {int(count):,}", 3, timestamp)

    def _observe_gameplay_domain(self, event, raw, data, timestamp):
        """Learn bounded patterns from non-exploration gameplay journal events."""
        mission_events = {"MissionAccepted", "MissionCompleted", "MissionFailed", "MissionAbandoned", "MissionRedirected"}
        combat_events = {
            "Bounty", "FactionKillBond", "PVPKill", "UnderAttack", "FighterDestroyed",
            "SRVDestroyed", "EscapeInterdiction", "Interdiction", "Interdicted",
            "ShieldState", "HullDamage", "JetConeDamage",
        }
        trade_events = {"MarketBuy", "MarketSell", "BuyTradeData"}
        mining_events = {"MiningRefined", "ProspectedAsteroid", "AsteroidCracked"}
        engineering_events = {
            "MaterialCollected", "MaterialDiscarded", "MaterialTrade", "EngineerCraft",
            "Synthesis", "EngineerProgress", "TechnologyBroker",
        }
        odyssey_events = {
            "Disembark", "Embark", "ApproachSettlement", "BookDropship", "BookTaxi",
            "DropshipDeploy", "BuySuit", "BuyWeapon", "UpgradeSuit", "UpgradeWeapon",
            "SellOrganicData", "CollectItems", "DropItems",
        }
        career_events = {"Rank", "Promotion", "Progress", "Reputation", "CodexEntry", "Statistics"}
        crime_events = {"CommitCrime", "CrimeVictim", "Fine", "PayFines", "PayBounties", "ClearImpound"}
        strategy_events = {
            "Powerplay", "PowerplayJoin", "PowerplayDefect", "PowerplayLeave",
            "PowerplayRank", "PowerplayMerits", "CommunityGoal", "CommunityGoalJoin",
            "CommunityGoalReward", "FactionState",
        }
        carrier_events = {
            "CarrierBuy", "CarrierStats", "CarrierJump", "CarrierDepositFuel", "CarrierFinance",
            "CarrierBankTransfer", "CarrierTradeOrder", "CarrierCrewServices", "CarrierNameChange",
            "CarrierDecommission", "CarrierCancelDecommission", "CarrierDockingPermission",
        }
        colony_events = {"ColonisationConstructionDepot", "ColonisationContribution", "ColonisationSystemClaimed"}
        fleet_events = {
            "ShipyardBuy", "ShipyardSell", "ShipyardTransfer", "StoredShips", "ModuleBuy",
            "ModuleSell", "ModuleStore", "ModuleRetrieve", "ModuleSwap",
        }
        social_events = {
            "SquadronStartup", "LeftSquadron", "DisbandedSquadron", "WingJoin", "WingLeave",
            "CrewMemberJoins", "CrewMemberQuits", "Friends",
        }

        if event in mission_events:
            domain_name = "missions"
        elif event in combat_events:
            domain_name = "combat"
        elif event in trade_events:
            domain_name = "trade"
        elif event in mining_events:
            domain_name = "mining"
        elif event in engineering_events:
            domain_name = "engineering"
        elif event in odyssey_events:
            domain_name = "odyssey"
        elif event in career_events:
            domain_name = "career"
        elif event in crime_events:
            domain_name = "crime"
        elif event in strategy_events:
            domain_name = "strategy"
        elif event in carrier_events:
            domain_name = "carrier"
        elif event in colony_events:
            domain_name = "colonisation"
        elif event in fleet_events:
            domain_name = "fleet"
        elif event in social_events:
            domain_name = "social"
        else:
            return False

        domain = self._knowledge_domain(domain_name, event, timestamp)
        self._increment("awareness_events")
        self._increment(f"{domain_name}_events")

        if domain_name == "missions":
            outcome = {
                "MissionAccepted": "accepted", "MissionCompleted": "completed",
                "MissionFailed": "failed", "MissionAbandoned": "abandoned",
                "MissionRedirected": "redirected",
            }[event]
            domain[outcome] = int(domain.get(outcome) or 0) + 1
            mission = self._event_label(raw, data, "Name_Localised", "name", "Name", fallback="Mission")
            faction = self._event_label(raw, data, "Faction", "faction", fallback="Unknown faction")
            self._knowledge_named(domain, "types", mission, timestamp=timestamp)
            if faction != "Unknown faction":
                self._knowledge_named(domain, "factions", faction, timestamp=timestamp)
            reward = self._number(raw.get("Reward") or data.get("reward"))
            if event == "MissionCompleted" and reward:
                domain["rewards_cr"] = int(domain.get("rewards_cr") or 0) + reward
            self._domain_milestone("mission", "Missions completed", domain.get("completed", 0), timestamp)

        elif domain_name == "combat":
            if event in ("Bounty", "FactionKillBond", "PVPKill"):
                domain["victories"] = int(domain.get("victories") or 0) + 1
                self._increment("combat_victories")
                target = self._event_label(
                    raw, data, "Target_Localised", "Target", "Victim", "victim", fallback="Hostile contact"
                )
                self._knowledge_named(domain, "targets", target, timestamp=timestamp)
                reward = self._number(raw.get("TotalReward") or raw.get("Reward") or data.get("reward"))
                domain["rewards_cr"] = int(domain.get("rewards_cr") or 0) + reward
                self._domain_milestone("combat", "Combat victories", domain["victories"], timestamp)
            else:
                key = {
                    "UnderAttack": "attacks", "FighterDestroyed": "fighters_lost",
                    "SRVDestroyed": "srvs_lost", "EscapeInterdiction": "interdictions_escaped",
                    "Interdiction": "interdictions_attempted", "Interdicted": "interdictions_suffered",
                    "JetConeDamage": "jet_cone_damage",
                }.get(event)
                if key:
                    domain[key] = int(domain.get(key) or 0) + 1
                elif event == "ShieldState" and not bool(raw.get("ShieldsUp", data.get("shields_up", True))):
                    domain["shield_failures"] = int(domain.get("shield_failures") or 0) + 1
                elif event == "HullDamage":
                    domain["hull_damage_events"] = int(domain.get("hull_damage_events") or 0) + 1
                    health = raw.get("Health", data.get("health"))
                    try:
                        health_pct = round(float(health) * 100 if float(health) <= 1 else float(health), 1)
                        previous = domain.get("lowest_hull_pct")
                        domain["lowest_hull_pct"] = health_pct if previous is None else min(float(previous), health_pct)
                    except (TypeError, ValueError):
                        pass

        elif domain_name == "trade":
            if event in ("MarketBuy", "MarketSell"):
                commodity = self._event_label(
                    raw, data, "Type_Localised", "Type", "type", fallback="Commodity"
                )
                count = max(1, self._number(raw.get("Count") or data.get("count"), 1))
                side = "bought" if event == "MarketBuy" else "sold"
                self._knowledge_named(domain, f"commodities_{side}", commodity, count, timestamp)
                total = self._number(raw.get("TotalCost") if event == "MarketBuy" else raw.get("TotalSale"))
                domain[f"{side}_units"] = int(domain.get(f"{side}_units") or 0) + count
                domain["spent_cr" if event == "MarketBuy" else "revenue_cr"] = int(
                    domain.get("spent_cr" if event == "MarketBuy" else "revenue_cr") or 0
                ) + total
                if event == "MarketSell":
                    average = self._number(raw.get("AvgPricePaid"))
                    if average:
                        domain["realised_profit_cr"] = int(domain.get("realised_profit_cr") or 0) + total - average * count
                system = self.state.get("current_system")
                if system:
                    self._knowledge_named(domain, "market_systems", system, timestamp=timestamp)
                self._domain_milestone("trade", "Market transactions", domain["events"], timestamp, (25, 100, 250, 500, 1000))

        elif domain_name == "mining":
            if event == "MiningRefined":
                mineral = self._event_label(raw, data, "Type_Localised", "Type", fallback="Mineral")
                refined = int(domain.get("refined") or 0) + 1
                domain["refined"] = refined
                self._knowledge_named(domain, "minerals", mineral, timestamp=timestamp)
                self._domain_milestone("mining", "Minerals refined", refined, timestamp, (25, 100, 250, 500, 1000))
            elif event == "ProspectedAsteroid":
                domain["prospected"] = int(domain.get("prospected") or 0) + 1
                for material in raw.get("Materials") or data.get("Materials") or ():
                    if isinstance(material, dict):
                        name = material.get("Name_Localised") or material.get("Name")
                        if name:
                            self._knowledge_named(domain, "prospected_materials", name, timestamp=timestamp)
            elif event == "AsteroidCracked":
                domain["cores_cracked"] = int(domain.get("cores_cracked") or 0) + 1

        elif domain_name == "engineering":
            if event in ("MaterialCollected", "MaterialDiscarded"):
                material = self._event_label(raw, data, "Name_Localised", "Name", fallback="Material")
                amount = max(1, self._number(raw.get("Count") or data.get("count"), 1))
                bucket = "materials_collected" if event == "MaterialCollected" else "materials_discarded"
                self._knowledge_named(domain, bucket, material, amount, timestamp)
            elif event == "MaterialTrade":
                domain["trades"] = int(domain.get("trades") or 0) + 1
                for bucket, payload in (("materials_paid", raw.get("Paid")), ("materials_received", raw.get("Received"))):
                    rows = payload if isinstance(payload, list) else (payload,) if isinstance(payload, dict) else ()
                    for row in rows:
                        name = row.get("Material_Localised") or row.get("Material")
                        if name:
                            self._knowledge_named(
                                domain, bucket, name, max(1, self._number(row.get("Quantity"), 1)), timestamp
                            )
            elif event == "EngineerCraft":
                domain["crafts"] = int(domain.get("crafts") or 0) + 1
                self._increment("engineering_crafts")
                blueprint = self._event_label(raw, data, "BlueprintName", "BlueprintName_Localised", fallback="Blueprint")
                self._knowledge_named(domain, "blueprints", blueprint, timestamp=timestamp)
                self._domain_milestone("engineering", "Engineering modifications crafted", domain["crafts"], timestamp)
            elif event == "Synthesis":
                domain["synthesis"] = int(domain.get("synthesis") or 0) + 1
                recipe = self._event_label(raw, data, "Name", fallback="Synthesis")
                self._knowledge_named(domain, "synthesis_recipes", recipe, timestamp=timestamp)
            elif event == "EngineerProgress":
                engineer = self._event_label(raw, data, "Engineer", "EngineerName", fallback="Engineer")
                rank = self._number(raw.get("Rank") or data.get("rank"))
                domain.setdefault("engineers", {})[engineer] = {"rank": rank, "last_seen": timestamp}
            elif event == "TechnologyBroker":
                domain["broker_unlocks"] = int(domain.get("broker_unlocks") or 0) + 1

        elif domain_name == "odyssey":
            key = {
                "Disembark": "disembarks", "Embark": "embarks", "ApproachSettlement": "settlements",
                "DropshipDeploy": "combat_deployments", "BookDropship": "dropships_booked",
                "BookTaxi": "taxis_booked", "BuySuit": "suits_bought", "BuyWeapon": "weapons_bought",
                "UpgradeSuit": "suits_upgraded", "UpgradeWeapon": "weapons_upgraded",
                "SellOrganicData": "bio_sales", "CollectItems": "items_collected", "DropItems": "items_dropped",
            }.get(event)
            if key:
                domain[key] = int(domain.get(key) or 0) + 1
            settlement = raw.get("Name") if event == "ApproachSettlement" else None
            if settlement:
                self._knowledge_named(domain, "visited_settlements", settlement, timestamp=timestamp)
            if event in ("CollectItems", "DropItems"):
                item = raw.get("Name_Localised") or raw.get("Name")
                if item:
                    self._knowledge_named(
                        domain, "ground_items", item, max(1, self._number(raw.get("Count"), 1)), timestamp
                    )

        elif domain_name == "career":
            if event in ("Rank", "Promotion", "Progress"):
                ranks = domain.setdefault("ranks", {})
                for key, value in raw.items():
                    if key not in ("timestamp", "event") and isinstance(value, (int, float, str)):
                        ranks[str(key)] = value
                if event == "Promotion":
                    domain["promotions"] = int(domain.get("promotions") or 0) + 1
                    self._remember("career", "Earned a new career promotion", 4, timestamp)
            elif event == "Reputation":
                domain["reputation_updates"] = int(domain.get("reputation_updates") or 0) + 1
            elif event == "CodexEntry":
                domain["codex_entries"] = int(domain.get("codex_entries") or 0) + 1
                category = self._event_label(raw, data, "Category_Localised", "Category", fallback="Codex")
                self._knowledge_named(domain, "codex_categories", category, timestamp=timestamp)
                self._domain_milestone("codex", "Codex discoveries", domain["codex_entries"], timestamp)

        elif domain_name == "crime":
            key = {
                "CommitCrime": "crimes", "CrimeVictim": "victims", "Fine": "fines_received",
                "PayFines": "fines_paid", "PayBounties": "bounties_paid", "ClearImpound": "impounds_cleared",
            }.get(event)
            if key:
                domain[key] = int(domain.get(key) or 0) + 1
            crime = raw.get("CrimeType_Localised") or raw.get("CrimeType")
            if crime:
                self._knowledge_named(domain, "crime_types", crime, timestamp=timestamp)
            amount = self._number(raw.get("Amount") or raw.get("Cost") or raw.get("Fine"))
            if amount:
                domain["cost_cr"] = int(domain.get("cost_cr") or 0) + amount

        elif domain_name == "strategy":
            if event.startswith("Powerplay"):
                domain["powerplay_events"] = int(domain.get("powerplay_events") or 0) + 1
                power = raw.get("Power") or raw.get("FromPower") or raw.get("ToPower")
                if power:
                    domain["power"] = _safe_name(power)
                merits = self._number(raw.get("Merits") or raw.get("TotalMerits"))
                if merits:
                    domain["merits"] = max(int(domain.get("merits") or 0), merits)
            elif event.startswith("CommunityGoal") or event == "CommunityGoal":
                domain["community_goal_events"] = int(domain.get("community_goal_events") or 0) + 1
            elif event == "FactionState":
                domain["faction_state_updates"] = int(domain.get("faction_state_updates") or 0) + 1

        elif domain_name == "carrier":
            key = {
                "CarrierBuy": "purchases", "CarrierJump": "jumps", "CarrierDepositFuel": "fuel_deposits",
                "CarrierBankTransfer": "bank_transfers", "CarrierTradeOrder": "trade_orders",
                "CarrierNameChange": "renames", "CarrierDecommission": "decommissions",
                "CarrierCancelDecommission": "decommissions_cancelled",
            }.get(event)
            if key:
                domain[key] = int(domain.get(key) or 0) + 1
            callsign = raw.get("Callsign") or raw.get("CarrierID")
            if callsign:
                domain["carrier"] = str(callsign)
            self._domain_milestone("carrier", "Fleet carrier jumps", domain.get("jumps", 0), timestamp, (10, 25, 50, 100, 250, 500))

        elif domain_name == "colonisation":
            key = {
                "ColonisationConstructionDepot": "depot_updates",
                "ColonisationContribution": "contributions",
                "ColonisationSystemClaimed": "systems_claimed",
            }[event]
            domain[key] = int(domain.get(key) or 0) + 1
            if event == "ColonisationContribution":
                contributions = data.get("contributions") or raw.get("Contributions") or ()
                for contribution in contributions:
                    if not isinstance(contribution, dict):
                        continue
                    commodity = (contribution.get("display") or contribution.get("Name_Localised")
                                 or contribution.get("name") or contribution.get("Name"))
                    amount = self._number(contribution.get("count") or contribution.get("Count"))
                    if commodity:
                        self._knowledge_named(domain, "commodities", commodity, max(1, amount), timestamp)
            elif event == "ColonisationConstructionDepot":
                for resource in data.get("resources") or ():
                    if isinstance(resource, dict) and resource.get("display"):
                        self._knowledge_named(
                            domain, "required_resources", resource["display"],
                            max(1, self._number(resource.get("required"))), timestamp,
                        )
            if event == "ColonisationSystemClaimed":
                system = raw.get("StarSystem") or data.get("star_system") or self.state.get("current_system")
                self._remember("colonisation", f"Helped claim {system or 'a new system'}", 5, timestamp)

        elif domain_name == "fleet":
            if event in ("ShipyardBuy", "ShipyardSell", "ShipyardTransfer"):
                domain[event] = int(domain.get(event) or 0) + 1
                ship = self._event_label(raw, data, "ShipType_Localised", "ShipType", fallback="Ship")
                self._knowledge_named(domain, "ships", ship, timestamp=timestamp)
            elif event.startswith("Module"):
                domain["module_changes"] = int(domain.get("module_changes") or 0) + 1
                module = self._event_label(raw, data, "BuyItem_Localised", "SellItem_Localised", "StoredItem_Localised", fallback="Module")
                self._knowledge_named(domain, "modules", module, timestamp=timestamp)
            elif event == "StoredShips":
                domain["fleet_reviews"] = int(domain.get("fleet_reviews") or 0) + 1

        elif domain_name == "social":
            domain[event] = int(domain.get(event) or 0) + 1
            group = raw.get("SquadronName") or raw.get("Name")
            if group:
                domain["last_group"] = _safe_name(group)

        return True

    def observe(self, event, raw=None, normalized=None, startup_replay=False):
        """Learn from one live journal event. Returns True when state changed."""
        if startup_replay or not event:
            return False
        raw = raw if isinstance(raw, dict) else {}
        data = normalized if isinstance(normalized, dict) else raw
        timestamp = raw.get("timestamp") or data.get("timestamp") or _now()
        if not self.state.get("current_session"):
            self.start_session(
                data.get("star_system") or raw.get("StarSystem"),
                data.get("ship_name") or raw.get("ShipName"),
            )
        changed = False

        def inc(key, amount=1):
            nonlocal changed
            changed = True
            return self._increment(key, amount)

        if event == "Location":
            system = _safe_name(data.get("star_system") or raw.get("StarSystem"), "")
            if system and system != self.state.get("current_system"):
                self.state["current_system"] = system
                self.state["systems"].setdefault(
                    system, {"count": 0, "first_seen": timestamp, "last_seen": timestamp}
                )
                changed = True

        elif event in ("FSDJump", "CarrierJump"):
            if event == "CarrierJump" and not (data.get("docked") or raw.get("Docked")):
                return False
            system = _safe_name(data.get("star_system") or raw.get("StarSystem"))
            self.state["current_system"] = system
            visits = self.state["systems"].setdefault(system, {"count": 0, "first_seen": timestamp})
            visits["count"] = int(visits.get("count") or 0) + 1
            visits["last_seen"] = timestamp
            jump_count = inc("jumps")
            changed = True
            session = self.state.get("current_session") or {}
            position = data.get("star_pos") or raw.get("StarPos")
            if isinstance(position, (list, tuple)) and len(position) >= 3:
                position = [float(value) for value in position[:3]]
                if session.get("last_pos"):
                    session["distance_ly"] = round(float(session.get("distance_ly") or 0) + _distance(session["last_pos"], position), 2)
                if not session.get("origin_pos"):
                    session["origin_pos"] = position
                session["last_pos"] = position
                session["max_displacement_ly"] = round(max(
                    float(session.get("max_displacement_ly") or 0),
                    _distance(session.get("origin_pos"), position),
                ), 2)
            active = self.state.get("active_expedition")
            session_jumps = self._session_delta().get("jumps", 0)
            if not active and (session_jumps >= 50 or (
                    session_jumps >= 20 and float(session.get("max_displacement_ly") or 0) >= 1000)):
                active = {
                    "id": uuid.uuid4().hex,
                    "name": f"Expedition {str(timestamp)[:10]}",
                    "started_at": session.get("started_at") or timestamp,
                    "start_system": session.get("start_system") or system,
                    "jumps": session_jumps,
                    "distance_ly": session.get("distance_ly", 0),
                    "discoveries": 0, "bios": 0, "fss_surveys": 0, "dss_maps": 0,
                }
                self.state["active_expedition"] = active
                self._remember("expedition", f"Began {active['name']} from {active['start_system']}", 4, timestamp)
                self._queue_remark((
                    "Our journey now qualifies as an expedition. I have opened a dedicated log.",
                    "We have travelled far enough that I am promoting this journey to expedition status.",
                ), "navigation", "expedition-start", 2)
            elif active:
                active["jumps"] = int(active.get("jumps") or 0) + 1
                active["distance_ly"] = session.get("distance_ly", active.get("distance_ly", 0))
                if active["jumps"] in (50, 100, 250, 500, 1000):
                    self._remember("expedition", f"{active['name']} reached {active['jumps']:,} jumps", 4, timestamp)
                    self._queue_remark((
                        f"Expedition milestone. {active['jumps']:,} jumps are now in our dedicated log.",
                        f"We have completed {active['jumps']:,} jumps on this expedition. The record is becoming substantial.",
                    ), "navigation", "expedition-milestone", 2)
            if visits["count"] in (5, 10, 25, 50, 100):
                self._remember("system", f"Visited {system} {visits['count']} times", 2, timestamp)
            if jump_count in (100, 500, 1000, 5000, 10000):
                self._remember("milestone", f"Completed {jump_count:,} jumps together", 4, timestamp)
            self._trim(self.state["systems"], self.limits["systems"])

        elif event == "Scan":
            scans = inc("scans")
            body = _safe_name(raw.get("BodyName") or data.get("body_name"), "a celestial body")
            system = _safe_name(
                data.get("system_name") or raw.get("SystemName") or self.state.get("current_system"), ""
            )
            if system:
                system_entry = self.state["systems"].setdefault(
                    system, {"count": 0, "first_seen": timestamp}
                )
                system_entry["body_scans"] = int(system_entry.get("body_scans") or 0) + 1
                system_entry["last_seen"] = timestamp
            if raw.get("WasDiscovered") is False or data.get("was_discovered") is False:
                discoveries = inc("first_discoveries")
                if system:
                    system_entry["first_discoveries"] = int(system_entry.get("first_discoveries") or 0) + 1
                self._remember("discovery", f"First discovered {body}", 3, timestamp)
                if self.state.get("active_expedition"):
                    self.state["active_expedition"]["discoveries"] = int(
                        self.state["active_expedition"].get("discoveries") or 0
                    ) + 1
                if discoveries in (10, 50, 100, 500, 1000):
                    self._remember("milestone", f"Made {discoveries:,} first discoveries together", 4, timestamp)
            if scans in (100, 500, 1000, 5000):
                self._remember("milestone", f"Recorded {scans:,} body scans", 3, timestamp)

        elif event in ("FSSDiscoveryScan", "DiscoveryScan"):
            system = _safe_name(
                data.get("system_name") or raw.get("SystemName") or self.state.get("current_system"),
                "Unknown system",
            )
            if system != "Unknown system":
                self.state["current_system"] = system
            body_count = int(
                data.get("body_count") or data.get("bodies")
                or raw.get("BodyCount") or raw.get("Bodies") or 0
            )
            entry = self.state["systems"].setdefault(
                system, {"count": 0, "first_seen": timestamp}
            )
            entry["last_seen"] = timestamp
            previous_bodies = int(entry.get("body_count") or 0)
            entry["body_count"] = max(previous_bodies, body_count)
            entry["honks"] = int(entry.get("honks") or 0) + 1
            entry["last_honk"] = timestamp
            honks = inc("system_honks")
            if body_count >= 30 and previous_bodies < 30:
                self._remember(
                    "survey", f"Detected {body_count:,} bodies in {system}", 2, timestamp
                )
            if honks in (25, 100, 250, 500, 1000, 5000):
                self._remember("milestone", f"Honked {honks:,} systems", 3, timestamp)

            progress = data.get("progress", raw.get("Progress"))
            try:
                already_complete = float(progress) >= 1.0
            except (TypeError, ValueError):
                already_complete = False
            if already_complete and not entry.get("fss_complete"):
                entry["fss_complete"] = timestamp
                completed = inc("fss_systems_completed")
                if self.state.get("active_expedition"):
                    self.state["active_expedition"]["fss_surveys"] = int(
                        self.state["active_expedition"].get("fss_surveys") or 0
                    ) + 1
                if completed in (1, 10, 25, 50, 100, 250, 500, 1000):
                    self._remember(
                        "survey", f"Completed full FSS surveys of {completed:,} systems", 3, timestamp
                    )

        elif event == "FSSAllBodiesFound":
            system = _safe_name(
                data.get("system_name") or raw.get("SystemName") or self.state.get("current_system"),
                "Unknown system",
            )
            if system != "Unknown system":
                self.state["current_system"] = system
            entry = self.state["systems"].setdefault(
                system, {"count": 0, "first_seen": timestamp}
            )
            entry["last_seen"] = timestamp
            count = int(data.get("count") or raw.get("Count") or entry.get("body_count") or 0)
            entry["body_count"] = max(int(entry.get("body_count") or 0), count)
            if not entry.get("fss_complete"):
                entry["fss_complete"] = timestamp
                completed = inc("fss_systems_completed")
                if self.state.get("active_expedition"):
                    self.state["active_expedition"]["fss_surveys"] = int(
                        self.state["active_expedition"].get("fss_surveys") or 0
                    ) + 1
                if completed in (1, 10, 25, 50, 100, 250, 500, 1000):
                    self._remember(
                        "survey", f"Completed full FSS surveys of {completed:,} systems", 3, timestamp
                    )
                if completed in (10, 50, 100, 250, 500, 1000):
                    self._queue_remark((
                        f"Survey milestone. We have now completed full FSS surveys of {completed:,} systems.",
                        f"The exploration archive now contains {completed:,} fully surveyed systems.",
                    ), "exploration", "fss-survey-milestone", 2)
            changed = True

        elif event in ("FSSBodySignals", "SAASignalsFound"):
            system = _safe_name(self.state.get("current_system"), "Unknown system")
            entry = self.state["systems"].setdefault(
                system, {"count": 0, "first_seen": timestamp}
            )
            entry["last_seen"] = timestamp
            body = _safe_name(
                data.get("body_name") or raw.get("BodyName")
                or data.get("body_id") or raw.get("BodyID"), "Unknown body"
            )
            bio_count = int(data.get("bio_count") or 0)
            geo_count = int(data.get("geo_count") or 0)
            signal_bodies = entry.setdefault("signal_bodies", {})
            previous = signal_bodies.get(body, {})
            previous_bio = int(previous.get("bio") or 0)
            previous_geo = int(previous.get("geo") or 0)
            signal_bodies[body] = {
                "bio": max(previous_bio, bio_count),
                "geo": max(previous_geo, geo_count),
                "last_seen": timestamp,
            }
            if len(signal_bodies) > 128:
                oldest = min(signal_bodies, key=lambda key: signal_bodies[key].get("last_seen") or "")
                signal_bodies.pop(oldest, None)
            if not previous and (bio_count or geo_count):
                inc("signal_bodies_found")
            bio_delta = max(0, bio_count - previous_bio)
            geo_delta = max(0, geo_count - previous_geo)
            if bio_delta:
                inc("biological_signals_found", bio_delta)
            if geo_delta:
                inc("geological_signals_found", geo_delta)
            if bio_count and not previous_bio:
                self._remember(
                    "biology", f"Detected {bio_count:,} biological signals on {body}", 2, timestamp
                )
            if bio_count or geo_count:
                changed = True

        elif event == "SAAScanComplete":
            system = _safe_name(self.state.get("current_system"), "Unknown system")
            entry = self.state["systems"].setdefault(
                system, {"count": 0, "first_seen": timestamp}
            )
            entry["last_seen"] = timestamp
            body = _safe_name(
                data.get("body_name") or raw.get("BodyName")
                or data.get("body_id") or raw.get("BodyID"), "Unknown body"
            )
            mapped = entry.setdefault("mapped_bodies", [])
            if body not in mapped:
                mapped.append(body)
                del mapped[:-128]
                maps = inc("dss_maps_completed")
                if self.state.get("active_expedition"):
                    self.state["active_expedition"]["dss_maps"] = int(
                        self.state["active_expedition"].get("dss_maps") or 0
                    ) + 1
                probes = int(raw.get("ProbesUsed") or 0)
                target = int(raw.get("EfficiencyTarget") or 0)
                if probes and target and probes <= target:
                    inc("efficient_dss_maps")
                if maps in (1, 10, 25, 50, 100, 250, 500, 1000, 5000):
                    self._remember("mapping", f"Completed {maps:,} DSS surface maps", 3, timestamp)

        elif event == "NavBeaconScan":
            system = _safe_name(self.state.get("current_system"), "Unknown system")
            entry = self.state["systems"].setdefault(
                system, {"count": 0, "first_seen": timestamp}
            )
            entry["last_seen"] = timestamp
            entry["nav_beacon_scans"] = int(entry.get("nav_beacon_scans") or 0) + 1
            count = int(data.get("num_bodies") or raw.get("NumBodies") or 0)
            entry["body_count"] = max(int(entry.get("body_count") or 0), count)
            inc("nav_beacon_scans")

        elif event == "ScanOrganic":
            complete = bool(data.get("is_complete")) or str(raw.get("ScanType") or "").casefold() == "analyse"
            if complete:
                species = _safe_name(data.get("species") or raw.get("Species_Localised") or raw.get("Species"), "Organic")
                entry = self.state["species"].setdefault(species, {"count": 0, "first_seen": timestamp})
                entry["count"] = int(entry.get("count") or 0) + 1
                entry["last_seen"] = timestamp
                organics = inc("organic_analyses")
                changed = True
                if entry["count"] == 1:
                    self._remember("biology", f"First analysed {species}", 2, timestamp)
                if self.state.get("active_expedition"):
                    self.state["active_expedition"]["bios"] = int(
                        self.state["active_expedition"].get("bios") or 0
                    ) + 1
                if organics in (25, 50, 100, 250, 500, 1000):
                    self._remember("milestone", f"Completed {organics:,} biological analyses", 4, timestamp)
                self._trim(self.state["species"], self.limits["species"])

        elif event == "Loadout":
            ship = _safe_name(data.get("ship_name") or raw.get("ShipName")
                              or data.get("ship_localised") or raw.get("Ship_Localised")
                              or data.get("ship") or raw.get("Ship"), "Unnamed ship")
            entry = self.state["ships"].setdefault(ship, {"count": 0, "first_seen": timestamp})
            entry["count"] = int(entry.get("count") or 0) + 1
            entry["last_seen"] = timestamp
            inc("loadouts")
            self._trim(self.state["ships"], self.limits["ships"])

        else:
            counter_events = {
                "HeatWarning": "heat_warnings", "HeatDamage": "heat_damage",
                "Interdicted": "interdictions", "Died": "ship_losses",
                "Touchdown": "touchdowns", "MissionCompleted": "missions_completed",
                "MarketBuy": "market_trades", "MarketSell": "market_trades",
                "MiningRefined": "mining_refined", "Docked": "dockings",
                "SellOrganicData": "bio_sales", "SellExplorationData": "exploration_sales",
            }
            counter = counter_events.get(event)
            if counter:
                count = inc(counter)
                if event == "Died":
                    system = _safe_name(raw.get("StarSystem") or data.get("star_system"), "an unknown system")
                    self._remember("loss", f"Lost a ship in {system}", 5, timestamp)
                    self._set_mood("shaken", 1.0, "ship loss")
                elif event == "HeatWarning" and count in (10, 25, 50, 100):
                    self._remember("habit", f"Survived {count} critical heat warnings", 2, timestamp)
                if event in ("HeatWarning", "HeatDamage", "Interdicted"):
                    self._set_mood("alert", 0.85 if event != "HeatDamage" else 0.95, event)
                elif event == "Docked":
                    self._set_mood("relieved", 0.65, "safely docked")
                    active = self.state.get("active_expedition")
                    if active and int(active.get("jumps") or 0) >= 20:
                        active["ended_at"] = timestamp
                        self.state["expeditions"].append(active)
                        self.state["expeditions"] = self.state["expeditions"][-30:]
                        self.state["active_expedition"] = None
                        self._remember("expedition", f"Completed {active['name']} after {active['jumps']:,} jumps", 5, timestamp)
                    debrief = self.session_debrief("Docking report", close=False)
                    if debrief:
                        self._queue_remark((debrief,), "navigation", "session-debrief", 2)

        if event == "ScanOrganic" and (bool(data.get("is_complete")) or str(raw.get("ScanType") or "").casefold() == "analyse"):
            self._set_mood("proud", 0.55, "biological analysis completed")
        elif event == "Scan" and (raw.get("WasDiscovered") is False or data.get("was_discovered") is False):
            self._set_mood("curious", 0.6, "first discovery")

        if self._observe_gameplay_domain(event, raw, data, timestamp):
            changed = True

        if changed:
            self._apply_limits()
            self._save()
        return changed

    def count(self, key):
        return int(self.state.get("counters", {}).get(key) or 0)

    def system_visits(self, system_name):
        return int((self.state.get("systems", {}).get(str(system_name)) or {}).get("count") or 0)

    def species_analyses(self, species_name):
        return int((self.state.get("species", {}).get(str(species_name)) or {}).get("count") or 0)

    @staticmethod
    def should_reference_repeat(count, level="Balanced"):
        minimum = {"quiet": 10, "balanced": 3, "chatty": 2}.get(str(level).casefold(), 3)
        return int(count) >= minimum

    def relationship_score(self):
        knowledge_events = sum(
            int(domain.get("events") or 0)
            for domain in self.state.get("knowledge", {}).values()
            if isinstance(domain, dict)
        )
        return (self.count("jumps") + self.count("scans")
                + self.count("organic_analyses") * 3 + self.count("missions_completed") * 2
                + self.count("system_honks") + self.count("fss_systems_completed") * 3
                + self.count("dss_maps_completed") * 2 + knowledge_events)

    def voice_stage(self, personality_level="Balanced"):
        score = self.relationship_score()
        stage_index = 4 if score >= 2000 else 3 if score >= 500 else 2 if score >= 100 else 1 if score >= 25 else 0
        adjustment = {"quiet": -1, "chatty": 1}.get(str(personality_level).casefold(), 0)
        return VOICE_STAGES[max(0, min(len(VOICE_STAGES) - 1, stage_index + adjustment))]

    @staticmethod
    def _voice_key_family(key):
        key = str(key or "").casefold()
        for family in (
            "system-arrival", "route-arrival", "route-waypoint", "first-discovery",
            "bio-complete", "engineering-ready", "massacre-complete", "clear-to-sample",
            "ship-overheat", "heat-damage", "under-attack", "shields-offline",
            "interdiction", "jet-cone-damage", "data-risk", "codex",
        ):
            if key.startswith(family):
                return family
        if key.startswith("hull-"):
            return "hull"
        if key.startswith("rebuy-"):
            return "rebuy"
        return None

    def voice_pool(self, lines, key=None, personality_level="Balanced"):
        """Unlock progressively richer variants as Compass gains experience."""
        if isinstance(lines, str):
            return lines
        base = tuple(str(line).strip() for line in (lines or ()) if str(line).strip())
        if not base:
            return ()
        stage = self.voice_stage(personality_level)
        stage_index = VOICE_STAGES.index(stage)
        base_limit = min(len(base), (2, 3, 4, 5, len(base))[stage_index])
        available = list(base[:base_limit])
        family = self._voice_key_family(key)
        evolved = VOICE_EVOLUTION_LINES.get(family, ())
        # Familiar, Trusted, and Veteran each unlock one additional reflective line.
        extension_count = max(0, stage_index - 1)
        available.extend(evolved[:extension_count])
        if stage_index >= 2:
            learned = self._learned_voice_line(family)
            if learned:
                available.append(learned)
        return tuple(available)

    def _learned_voice_line(self, family):
        habits = self.habits()
        if family == "system-arrival":
            if "Thorough system surveyor" in habits:
                return "Discovery sensors are ready. Experience suggests you will want a proper look around."
            if "Fast-moving traveller" in habits:
                return "Navigation is already preparing the next jump. We rarely stay still for long."
        if family in ("ship-overheat", "heat-damage") and self.count("heat_warnings") >= 10:
            return f"Thermal warning recorded. This is number {self.count('heat_warnings'):,} in our shared log."
        if family == "bio-complete" and self.count("organic_analyses") >= 25:
            return f"Our biological archive now contains {self.count('organic_analyses'):,} completed analyses."
        if family in ("route-arrival", "route-waypoint") and self.count("jumps") >= 100:
            return f"Navigation history now spans {self.count('jumps'):,} jumps together."
        if family == "data-risk" and self.count("exploration_sales") >= 3:
            return "We have brought valuable archives home before. I recommend doing so again."
        return None

    def relationship(self):
        stage = self.voice_stage("Balanced")
        if stage == "veteran":
            return "Veteran flight companion"
        if stage == "trusted":
            return "Trusted flight companion"
        if stage == "familiar":
            return "Familiar flight companion"
        if stage == "developing":
            return "Developing flight companion"
        return "Newly activated flight companion"

    def traits(self):
        c = self.state.get("counters", {})
        knowledge = self.state.get("knowledge", {})
        scores = {
            "Explorer": int(c.get("scans") or 0) + int(c.get("first_discoveries") or 0) * 4,
            "Exobiologist": int(c.get("organic_analyses") or 0) * 5,
            "Trader": int(c.get("market_trades") or 0) * 2,
            "Mission Runner": int(c.get("missions_completed") or 0) * 2,
            "Miner": int(c.get("mining_refined") or 0) * 3,
            "Traveller": int(c.get("jumps") or 0),
            "Combat Pilot": int((knowledge.get("combat") or {}).get("victories") or 0) * 5,
            "Engineer": int((knowledge.get("engineering") or {}).get("crafts") or 0) * 5,
            "Ground Operative": int((knowledge.get("odyssey") or {}).get("events") or 0) * 2,
            "Colony Builder": int((knowledge.get("colonisation") or {}).get("contributions") or 0) * 4,
            "Carrier Operator": int((knowledge.get("carrier") or {}).get("jumps") or 0) * 3,
        }
        return [name for name, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
                if score > 0][:2]

    def summary(self):
        traits = self.traits()
        return {
            "relationship": self.relationship(),
            "voice_stage": self.voice_stage(),
            "traits": traits,
            "jumps": self.count("jumps"),
            "scans": self.count("scans"),
            "organics": self.count("organic_analyses"),
            "honks": self.count("system_honks"),
            "fss_completed": self.count("fss_systems_completed"),
            "dss_maps": self.count("dss_maps_completed"),
            "signal_bodies": self.count("signal_bodies_found"),
            "awareness_domains": len(self.knowledge_domains()),
            "systems": len(self.state.get("systems", {})),
            "memories": len(self.state.get("memories", [])),
            "activated_at": self.state.get("activated_at"),
        }

    def summary_text(self):
        info = self.summary()
        traits = " / ".join(info["traits"]) if info["traits"] else "Still learning your habits"
        return (
            f"{info['relationship']} · {traits}\n"
            f"{info['jumps']:,} jumps · {info['systems']:,} remembered systems · "
            f"{info['scans']:,} scans · {info['organics']:,} bio analyses · "
            f"{info['fss_completed']:,} full FSS surveys · {info['dss_maps']:,} DSS maps · "
            f"{info['memories']:,} notable memories"
        )

    def habits(self):
        jumps = max(1, self.count("jumps"))
        knowledge = self.state.get("knowledge", {})
        habits = []
        if self.count("scans") / jumps >= 2.5:
            habits.append("Thorough system surveyor")
        elif self.count("scans") / jumps <= 0.35 and self.count("jumps") >= 25:
            habits.append("Fast-moving traveller")
        if self.count("organic_analyses") >= 10:
            habits.append("Persistent biological fieldwork")
        if self.count("fss_systems_completed") >= 10 and self.count("fss_systems_completed") / jumps >= 0.35:
            habits.append("Methodical FSS surveyor")
        if self.count("dss_maps_completed") >= 25:
            habits.append("Dedicated planetary mapper")
        if self.count("heat_warnings") >= max(5, self.count("jumps") // 20):
            habits.append("Comfortable near thermal limits")
        if self.count("market_trades") >= 20:
            habits.append("Regular market operator")
        if self.count("mining_refined") >= 20:
            habits.append("Experienced miner")
        if int((knowledge.get("combat") or {}).get("victories") or 0) >= 20:
            habits.append("Combat-tested pilot")
        if int((knowledge.get("missions") or {}).get("completed") or 0) >= 20:
            habits.append("Reliable mission contractor")
        if int((knowledge.get("engineering") or {}).get("crafts") or 0) >= 10:
            habits.append("Methodical ship engineer")
        if int((knowledge.get("odyssey") or {}).get("combat_deployments") or 0) >= 10:
            habits.append("Experienced ground operative")
        if int((knowledge.get("colonisation") or {}).get("contributions") or 0) >= 5:
            habits.append("Colony builder")
        if int((knowledge.get("carrier") or {}).get("jumps") or 0) >= 10:
            habits.append("Fleet carrier operator")
        return habits[:6]

    def knowledge_domains(self):
        labels = {
            "missions": "Missions", "combat": "Combat", "trade": "Trade",
            "mining": "Mining", "engineering": "Engineering", "odyssey": "Odyssey",
            "career": "Career", "crime": "Crime and legal", "strategy": "Powerplay and BGS",
            "carrier": "Fleet carrier", "colonisation": "Colonisation", "fleet": "Fleet",
            "social": "Social and squadrons",
        }
        knowledge = self.state.get("knowledge", {})
        return [labels.get(name, name.title()) for name, domain in knowledge.items()
                if isinstance(domain, dict) and int(domain.get("events") or 0) > 0]

    def gameplay_awareness(self):
        knowledge = self.state.get("knowledge", {})
        missions = knowledge.get("missions") or {}
        combat = knowledge.get("combat") or {}
        trade = knowledge.get("trade") or {}
        engineering = knowledge.get("engineering") or {}
        odyssey = knowledge.get("odyssey") or {}
        carrier = knowledge.get("carrier") or {}
        colony = knowledge.get("colonisation") or {}
        return {
            "domains": self.knowledge_domains(),
            "missions_completed": int(missions.get("completed") or 0),
            "combat_victories": int(combat.get("victories") or 0),
            "trade_profit_cr": int(trade.get("realised_profit_cr") or 0),
            "engineering_crafts": int(engineering.get("crafts") or 0),
            "ground_operations": int(odyssey.get("events") or 0),
            "carrier_jumps": int(carrier.get("jumps") or 0),
            "colony_contributions": int(colony.get("contributions") or 0),
        }

    def memory_rows(self):
        return sorted(
            (dict(row) for row in self.state.get("memories", [])),
            key=lambda row: (bool(row.get("pinned")), row.get("timestamp") or ""),
            reverse=True,
        )

    def _find_memory(self, memory_id):
        return next((row for row in self.state.get("memories", [])
                     if row.get("id") == memory_id), None)

    def get_memory(self, memory_id):
        row = self._find_memory(memory_id)
        return dict(row) if row else None

    def pin_memory(self, memory_id, pinned=None):
        row = self._find_memory(memory_id)
        if not row:
            return False
        row["pinned"] = not bool(row.get("pinned")) if pinned is None else bool(pinned)
        self._save()
        return True

    def rename_memory(self, memory_id, text):
        row = self._find_memory(memory_id)
        text = _safe_name(text, "")
        if not row or not text:
            return False
        row["text"] = text
        row["edited"] = True
        self._save()
        return True

    def delete_memory(self, memory_id):
        memories = self.state.get("memories", [])
        before = len(memories)
        memories[:] = [row for row in memories if row.get("id") != memory_id]
        if len(memories) == before:
            return False
        self._save()
        return True

    def rename_active_expedition(self, name):
        active = self.state.get("active_expedition")
        name = _safe_name(name, "")
        if not isinstance(active, dict) or not name:
            return False
        old_name = active.get("name")
        active["name"] = name
        self._remember("expedition", f"Renamed {old_name or 'active expedition'} to {name}", 3)
        self._save()
        return True

    def status_details(self):
        info = self.summary()
        mood = self.current_mood()
        intentions = self.state.get("intentions", {})
        active = self.state.get("active_expedition")
        ships = self.state.get("ships", {})
        systems = self.state.get("systems", {})
        current_system = self.state.get("current_system")
        favorite_ship = max(ships.items(), key=lambda pair: int(pair[1].get("count") or 0))[0] if ships else None
        familiar_system = max(systems.items(), key=lambda pair: int(pair[1].get("count") or 0))[0] if systems else None
        return {
            **info,
            "mood": mood,
            "habits": self.habits(),
            "intentions": dict(intentions),
            "gameplay_awareness": self.gameplay_awareness(),
            "active_expedition": dict(active) if isinstance(active, dict) else None,
            "completed_expeditions": len(self.state.get("expeditions", [])),
            "sessions": len(self.state.get("sessions", [])),
            "favorite_ship": favorite_ship,
            "most_visited_system": familiar_system,
            "traffic_known_systems": sum(
                1 for system in systems if self.system_has_traffic(system)
            ),
            "current_system_traffic": self.system_traffic(current_system) if current_system else None,
        }

    def arrival_lines(self, system_name, level="Balanced"):
        visits = self.system_visits(system_name)
        if not self.should_reference_repeat(visits, level):
            return ()
        return (
            f"We are back in {system_name}. This is our {ordinal(visits)} recorded visit.",
            f"I remember {system_name}. We have passed through here {visits} times now.",
            f"A familiar system. My records show {visits} visits to {system_name}.",
        )
