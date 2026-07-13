"""Bounded, local autobiographical memory for the Compass cockpit persona."""

from collections import Counter
from datetime import datetime, timezone
import json
import os


SCHEMA_VERSION = 1
MAX_SYSTEMS = 300
MAX_SPECIES = 200
MAX_SHIPS = 30
MAX_MEMORIES = 80


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
    def __init__(self, path):
        self.path = str(path)
        self.state = _initial_state()
        self._load()

    def switch(self, path):
        self.path = str(path)
        self.state = _initial_state()
        self._load()

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
            return
        keep = sorted(
            mapping.items(),
            key=lambda pair: (int(pair[1].get(count_key) or 0), pair[1].get("last_seen") or ""),
            reverse=True,
        )[:maximum]
        mapping.clear()
        mapping.update(keep)

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
        if len(memories) > MAX_MEMORIES:
            memories.sort(key=lambda row: (int(row.get("salience") or 0), row.get("timestamp") or ""))
            del memories[:len(memories) - MAX_MEMORIES]
            memories.sort(key=lambda row: row.get("timestamp") or "")

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
            self._trim(self.state["systems"], MAX_SYSTEMS)

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
                self._trim(self.state["species"], MAX_SPECIES)

        elif event == "Loadout":
            ship = _safe_name(data.get("ship_name") or raw.get("ShipName")
                              or data.get("ship_localised") or raw.get("Ship_Localised")
                              or data.get("ship") or raw.get("Ship"), "Unnamed ship")
            entry = self.state["ships"].setdefault(ship, {"count": 0, "first_seen": timestamp})
            entry["count"] = int(entry.get("count") or 0) + 1
            entry["last_seen"] = timestamp
            inc("loadouts")
            self._trim(self.state["ships"], MAX_SHIPS)

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

    def relationship(self):
        score = (self.count("jumps") + self.count("scans")
                 + self.count("organic_analyses") * 3 + self.count("missions_completed") * 2)
        if score >= 2000:
            return "Veteran flight companion"
        if score >= 500:
            return "Trusted flight companion"
        if score >= 100:
            return "Familiar flight companion"
        if score >= 25:
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
            f"We are back in {system_name}, Commander. This is our {ordinal(visits)} recorded visit.",
            f"I remember {system_name}. We have passed through here {visits} times now.",
            f"A familiar system, Commander. My records show {visits} visits to {system_name}.",
        )
