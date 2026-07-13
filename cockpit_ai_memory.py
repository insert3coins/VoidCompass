"""Bounded, local autobiographical memory for the Compass cockpit persona."""

from datetime import datetime, timezone
import json
import os


SCHEMA_VERSION = 1
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
        "current_voice": None,
        "memories": [],
    }


class CockpitMemory:
    def __init__(self, path, limits=None):
        self.path = str(path)
        self.limits = self.normalize_limits(limits)
        self.state = _initial_state()
        self._load()
        self._apply_limits(save=True)

    def switch(self, path, limits=None):
        self.path = str(path)
        if limits is not None:
            self.limits = self.normalize_limits(limits)
        self.state = _initial_state()
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
                for key in ("counters", "systems", "species", "ships"):
                    if not isinstance(base.get(key), dict):
                        base[key] = {}
                if not isinstance(base.get("memories"), list):
                    base["memories"] = []
                self.state = base
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
        memories.sort(key=lambda row: (int(row.get("salience") or 0), row.get("timestamp") or ""))
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
            "kind": kind,
            "text": text,
            "salience": int(salience),
            "timestamp": timestamp or _now(),
        })
        self._trim_memories()

    def observe(self, event, raw=None, normalized=None, startup_replay=False):
        """Learn from one live journal event. Returns True when state changed."""
        if startup_replay or not event:
            return False
        raw = raw if isinstance(raw, dict) else {}
        data = normalized if isinstance(normalized, dict) else raw
        timestamp = raw.get("timestamp") or data.get("timestamp") or _now()
        changed = False

        def inc(key, amount=1):
            nonlocal changed
            changed = True
            return self._increment(key, amount)

        if event in ("FSDJump", "CarrierJump"):
            if event == "CarrierJump" and not (data.get("docked") or raw.get("Docked")):
                return False
            system = _safe_name(data.get("star_system") or raw.get("StarSystem"))
            visits = self.state["systems"].setdefault(system, {"count": 0, "first_seen": timestamp})
            visits["count"] = int(visits.get("count") or 0) + 1
            visits["last_seen"] = timestamp
            jump_count = inc("jumps")
            changed = True
            if visits["count"] in (5, 10, 25, 50, 100):
                self._remember("system", f"Visited {system} {visits['count']} times", 2, timestamp)
            if jump_count in (100, 500, 1000, 5000, 10000):
                self._remember("milestone", f"Completed {jump_count:,} jumps together", 4, timestamp)
            self._trim(self.state["systems"], self.limits["systems"])

        elif event == "Scan":
            scans = inc("scans")
            body = _safe_name(raw.get("BodyName") or data.get("body_name"), "a celestial body")
            if raw.get("WasDiscovered") is False or data.get("was_discovered") is False:
                discoveries = inc("first_discoveries")
                self._remember("discovery", f"First discovered {body}", 3, timestamp)
                if discoveries in (10, 50, 100, 500, 1000):
                    self._remember("milestone", f"Made {discoveries:,} first discoveries together", 4, timestamp)
            if scans in (100, 500, 1000, 5000):
                self._remember("milestone", f"Recorded {scans:,} body scans", 3, timestamp)

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
                elif event == "HeatWarning" and count in (10, 25, 50, 100):
                    self._remember("habit", f"Survived {count} critical heat warnings", 2, timestamp)

        if changed:
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
        return (self.count("jumps") + self.count("scans")
                + self.count("organic_analyses") * 3 + self.count("missions_completed") * 2)

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
        return tuple(available)

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
        scores = {
            "Explorer": int(c.get("scans") or 0) + int(c.get("first_discoveries") or 0) * 4,
            "Exobiologist": int(c.get("organic_analyses") or 0) * 5,
            "Trader": int(c.get("market_trades") or 0) * 2,
            "Mission Runner": int(c.get("missions_completed") or 0) * 2,
            "Miner": int(c.get("mining_refined") or 0) * 3,
            "Traveller": int(c.get("jumps") or 0),
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
            f"{info['memories']:,} notable memories"
        )

    def arrival_lines(self, system_name, level="Balanced"):
        visits = self.system_visits(system_name)
        if not self.should_reference_repeat(visits, level):
            return ()
        return (
            f"We are back in {system_name}. This is our {ordinal(visits)} recorded visit.",
            f"I remember {system_name}. We have passed through here {visits} times now.",
            f"A familiar system. My records show {visits} visits to {system_name}.",
        )
