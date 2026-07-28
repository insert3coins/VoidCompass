"""Profile-local specialist workflow reducers for Void Compass.

The workflows mirror the useful local-only roles from elite-trader: mining
analytics, Combat/AX readiness, carrier planning, and exobiology surface pins.
No network service or account is required.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import threading
import time
import uuid

from persistence_queue import persistence_queue
from datetime import datetime

import bio_values


MINING_EVENTS = {
    "AsteroidCracked", "BuyDrones", "Cargo", "CollectCargo", "Died",
    "EjectCargo", "LaunchDrone", "MarketSell", "MiningRefined",
    "ProspectedAsteroid", "SellDrones", "Shutdown",
}
COMBAT_EVENTS = {
    "Bounty", "CapShipBond", "Cargo", "Died", "Docked",
    "FactionKillBond", "FighterDestroyed", "HeatDamage", "HullDamage",
    "Loadout", "Materials", "PVPKill", "RedeemVoucher", "ShipTargeted",
    "Shutdown", "Synthesis", "UnderAttack",
}
EXOBIO_EVENTS = {
    "ApproachBody", "CodexEntry", "Died", "FSDJump", "Location",
    "SAASignalsFound", "Scan", "ScanOrganic", "SellOrganicData", "Touchdown",
}


def _symbol(value):
    text = str(value or "").strip().strip("$;").lower()
    return text[:-5] if text.endswith("_name") else text


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _epoch_ms(value=None):
    if isinstance(value, (int, float)):
        return int(value if value > 10_000_000_000 else value * 1000)
    if isinstance(value, str) and value:
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            pass
    return int(time.time() * 1000)


def _inventory(event):
    result = {}
    for item in event.get("Inventory") or []:
        symbol = _symbol(item.get("Name") or item.get("Type"))
        if symbol:
            result[symbol] = {
                "name": item.get("Name_Localised") or symbol.replace("_", " ").title(),
                "count": _int(item.get("Count")),
                "stolen": _int(item.get("Stolen")),
            }
    return result


def _named_increment(bucket, symbol, name, count):
    if not symbol or not count:
        return
    row = bucket.setdefault(symbol, {
        "name": name or symbol.replace("_", " ").title(), "count": 0,
    })
    row["count"] += count
    if name:
        row["name"] = name


def _new_mining_session(ts, context=None):
    context = context or {}
    return {
        "session_key": f"{ts}-{uuid.uuid4().hex[:10]}", "active": True,
        "started_ts": ts, "last_event_ts": ts, "ended_ts": None,
        "end_reason": None, "system": context.get("system"),
        "body": context.get("body"), "asteroids_prospected": 0,
        "asteroids_cracked": 0, "prospector_limpets": 0,
        "collector_limpets": 0, "other_limpets": 0, "limpets_bought": 0,
        "limpets_sold": 0, "limpet_buy_cost_cr": 0, "limpet_sale_cr": 0,
        "cargo_start": {}, "cargo_current": {}, "collected": {},
        "jettisoned": {}, "refined": {}, "prospected_materials": {},
        "motherlodes": {}, "sales": {}, "attributed_revenue_cr": 0,
    }


def _new_combat_session(ts):
    return {
        "session_key": f"{ts}-{uuid.uuid4().hex[:10]}", "active": True,
        "started_ts": ts, "last_event_ts": ts, "ended_ts": None,
        "end_reason": None, "kills": 0, "pvp_kills": 0, "ax_kills": 0,
        "ax_kills_by_type": {}, "bounty_cr": 0, "bond_cr": 0,
        "redeemed_cr": 0, "damage_events": 0, "deaths": 0,
        "fighter_losses": 0, "synthesis": {}, "synthesis_materials": {},
        "ammo_start": None, "ammo_latest": None,
    }


def _defaults():
    return {
        "version": 1,
        "seen": [],
        "mining": {"last_cargo": {}, "session": None, "history": []},
        "combat": {
            "loadout": None, "cargo": {}, "materials": {}, "target": None,
            "synthesis_lifetime": {}, "session": None, "history": [],
        },
        "carrier": {
            "weekly_upkeep_cr": None, "reserve_target_weeks": 8,
            "tritium_per_jump_t": None, "tritium_reserve_t": 0,
            "inventory": {}, "inventory_source": "not supplied", "route": [],
        },
        "exobiology": {
            "system": None, "system_address": None, "body_ids": {},
            "surveys": {}, "sampling": None, "last_sale_ts": None,
        },
    }


class SpecialistEngine:
    """Thread-safe JSON-backed reducer scoped to one commander profile."""

    def __init__(self, path):
        self._lock = threading.RLock()
        self.path = path
        self.position = None
        self.state = _defaults()
        self._dirty = False
        self._load()

    def switch(self, path):
        with self._lock:
            if self._dirty:
                self._save()
            self.path = path
            self.position = None
            self.state = _defaults()
            self._dirty = False
            self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            if isinstance(value, dict):
                base = _defaults()
                for key in ("seen", "mining", "combat", "carrier", "exobiology"):
                    if isinstance(value.get(key), type(base[key])):
                        if isinstance(base[key], dict):
                            base[key].update(value[key])
                        else:
                            base[key] = value[key]
                self.state = base
        except (OSError, ValueError, TypeError):
            self.state = _defaults()

    def _save(self, immediate=False):
        persistence_queue().submit_json(
            self.path, self.state, indent=2, delay_s=0.75, immediate=immediate,
        )
        self._dirty = False

    def flush(self, wait=True):
        with self._lock:
            if self._dirty:
                self._save(immediate=wait)
        if wait:
            persistence_queue().flush(self.path, timeout=5.0)

    @staticmethod
    def _fallback_uid(event):
        raw = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def observe_event(self, event, event_uid=None, context=None, defer_save=False):
        if not isinstance(event, dict) or not event.get("event"):
            return False
        kind = event["event"]
        relevant = kind in MINING_EVENTS or kind in COMBAT_EVENTS or kind in EXOBIO_EVENTS or kind == "CargoTransfer"
        if not relevant:
            return False
        uid = str(event_uid or self._fallback_uid(event))
        with self._lock:
            if uid in self.state["seen"]:
                return False
            changed = False
            ts = _epoch_ms(event.get("timestamp"))
            if kind in MINING_EVENTS:
                changed |= self._observe_mining(event, ts, context or {})
            if kind in COMBAT_EVENTS:
                changed |= self._observe_combat(event, ts)
            if kind in EXOBIO_EVENTS:
                changed |= self._observe_exobiology(event, ts, context or {})
            if kind == "CargoTransfer" and (context or {}).get("at_own_carrier"):
                changed |= self._observe_carrier_transfer(event)
            if changed:
                self.state["seen"].append(uid)
                self.state["seen"] = self.state["seen"][-8000:]
                if defer_save:
                    self._dirty = True
                else:
                    self._save()
            return changed

    def update_cargo(self, inventory):
        event = {"Inventory": list(inventory or [])}
        with self._lock:
            cargo = _inventory(event)
            self.state["mining"]["last_cargo"] = cargo
            self.state["combat"]["cargo"] = cargo
            session = self.state["mining"].get("session")
            if session and session.get("active"):
                session["cargo_current"] = copy.deepcopy(cargo)
            self._save()

    def update_position(self, position):
        lat = _float((position or {}).get("lat"))
        lon = _float((position or {}).get("lon"))
        radius = _float((position or {}).get("radius_m"))
        if lat is None or lon is None or not radius or radius <= 0:
            self.position = None
            return
        self.position = {
            "lat": lat, "lon": ((lon + 180) % 360) - 180,
            "radius_m": radius, "heading": _float((position or {}).get("heading")),
            "alt_m": _float((position or {}).get("alt_m")),
            "body": (position or {}).get("body"),
        }

    # Mining ---------------------------------------------------------
    def _ensure_mining(self, ts, context):
        state = self.state["mining"]
        session = state.get("session")
        if not session or not session.get("active"):
            session = _new_mining_session(ts, context)
            session["cargo_start"] = copy.deepcopy(state.get("last_cargo") or {})
            session["cargo_current"] = copy.deepcopy(state.get("last_cargo") or {})
            state["session"] = session
        session["last_event_ts"] = max(session.get("last_event_ts") or ts, ts)
        return session

    def _archive(self, workflow, reason, ts):
        state = self.state[workflow]
        session = state.get("session")
        if not session or not session.get("active"):
            return False
        session.update(active=False, ended_ts=ts, last_event_ts=ts, end_reason=str(reason))
        state["history"].insert(0, copy.deepcopy(session))
        state["history"] = state["history"][:30]
        return True

    def start_mining(self, context=None):
        with self._lock:
            if (self.state["mining"].get("session") or {}).get("active"):
                return False
            self._ensure_mining(_epoch_ms(), context or {})
            self._save()
            return True

    def end_mining(self, reason="manual"):
        with self._lock:
            changed = self._archive("mining", reason, _epoch_ms())
            if changed:
                self._save()
            return changed

    def mining_active(self):
        with self._lock:
            session = self.state.get("mining", {}).get("session") or {}
            return bool(session.get("active"))

    def _observe_mining(self, event, ts, context):
        state = self.state["mining"]
        kind = event["event"]
        if kind == "Cargo":
            cargo = _inventory(event)
            state["last_cargo"] = cargo
            if state.get("session") and state["session"].get("active"):
                state["session"]["cargo_current"] = copy.deepcopy(cargo)
                state["session"]["last_event_ts"] = ts
            return True
        if kind in {"Died", "Shutdown"}:
            return self._archive("mining", kind.lower(), ts)
        session = state.get("session")
        if kind == "LaunchDrone":
            drone = str(event.get("Type") or "").casefold()
            if drone not in {"prospector", "collection"} and not session:
                return False
            session = self._ensure_mining(ts, context)
            key = "prospector_limpets" if drone == "prospector" else "collector_limpets" if drone == "collection" else "other_limpets"
            session[key] += 1
            return True
        if kind in {"ProspectedAsteroid", "MiningRefined", "AsteroidCracked", "BuyDrones"}:
            session = self._ensure_mining(ts, context)
        elif not session or not session.get("active"):
            return False
        else:
            session["last_event_ts"] = max(session.get("last_event_ts") or ts, ts)
        if kind == "BuyDrones":
            count = _int(event.get("Count"))
            session["limpets_bought"] += count
            session["limpet_buy_cost_cr"] += _int(event.get("TotalCost"), count * _int(event.get("BuyPrice")))
        elif kind == "SellDrones":
            count = _int(event.get("Count"))
            session["limpets_sold"] += count
            session["limpet_sale_cr"] += _int(event.get("TotalSale"), count * _int(event.get("SellPrice")))
        elif kind == "ProspectedAsteroid":
            session["asteroids_prospected"] += 1
            motherlode = _symbol(event.get("MotherlodeMaterial"))
            _named_increment(session["motherlodes"], motherlode, event.get("MotherlodeMaterial_Localised"), 1)
            for item in event.get("Materials") or []:
                symbol = _symbol(item.get("Name"))
                if not symbol:
                    continue
                row = session["prospected_materials"].setdefault(symbol, {
                    "name": item.get("Name_Localised") or item.get("Name") or symbol,
                    "sightings": 0, "total_pct": 0.0, "best_pct": 0.0,
                })
                pct = max(0.0, _float(item.get("Proportion"), 0.0))
                row["sightings"] += 1
                row["total_pct"] += pct
                row["best_pct"] = max(row["best_pct"], pct)
        elif kind == "AsteroidCracked":
            session["asteroids_cracked"] += 1
        elif kind == "MiningRefined":
            symbol = _symbol(event.get("Type"))
            _named_increment(session["refined"], symbol, event.get("Type_Localised") or event.get("Type"), max(1, _int(event.get("Count"), 1)))
        elif kind in {"CollectCargo", "EjectCargo"}:
            bucket = session["collected"] if kind == "CollectCargo" else session["jettisoned"]
            symbol = _symbol(event.get("Type"))
            _named_increment(bucket, symbol, event.get("Type_Localised") or event.get("Type"), max(1, _int(event.get("Count"), 1)))
        elif kind == "MarketSell":
            symbol = _symbol(event.get("Type"))
            refined = (session["refined"].get(symbol) or {}).get("count", 0)
            previous = (session["sales"].get(symbol) or {}).get("count", 0)
            sold = max(0, _int(event.get("Count")))
            attributable = min(max(0, refined - previous), sold)
            if attributable:
                total = _int(event.get("TotalSale"), sold * _int(event.get("SellPrice")))
                revenue = round(total * attributable / max(1, sold))
                _named_increment(session["sales"], symbol, event.get("Type_Localised") or event.get("Type"), attributable)
                session["sales"][symbol]["revenue_cr"] = session["sales"][symbol].get("revenue_cr", 0) + revenue
                session["attributed_revenue_cr"] += revenue
        return True

    # Combat ---------------------------------------------------------
    @staticmethod
    def _ammo_total(loadout):
        if not loadout:
            return None
        return sum(_int(row.get("AmmoInClip")) + _int(row.get("AmmoInHopper")) for row in loadout.get("Modules") or [] if row.get("AmmoInClip") is not None or row.get("AmmoInHopper") is not None)

    def _ensure_combat(self, ts):
        state = self.state["combat"]
        session = state.get("session")
        if not session or not session.get("active"):
            session = _new_combat_session(ts)
            ammo = self._ammo_total(state.get("loadout"))
            session.update(ammo_start=ammo, ammo_latest=ammo)
            state["session"] = session
        session["last_event_ts"] = max(session.get("last_event_ts") or ts, ts)
        return session

    def start_combat(self):
        with self._lock:
            if (self.state["combat"].get("session") or {}).get("active"):
                return False
            self._ensure_combat(_epoch_ms())
            self._save()
            return True

    def end_combat(self, reason="manual"):
        with self._lock:
            changed = self._archive("combat", reason, _epoch_ms())
            if changed:
                self._save()
            return changed

    @staticmethod
    def _is_thargoid(*values):
        text = " ".join(str(value or "") for value in values).casefold()
        return "thargoid" in text or "xeno" in text

    def _observe_combat(self, event, ts):
        state = self.state["combat"]
        kind = event["event"]
        if kind == "Loadout":
            state["loadout"] = copy.deepcopy(event)
            session = state.get("session")
            if session and session.get("active"):
                ammo = self._ammo_total(event)
                session["ammo_latest"] = ammo
                session["ammo_start"] = ammo if session.get("ammo_start") is None else session["ammo_start"]
            return True
        if kind == "Cargo":
            state["cargo"] = _inventory(event)
            return True
        if kind == "Materials":
            state["materials"] = {key: copy.deepcopy(event.get(key) or []) for key in ("Raw", "Manufactured", "Encoded")}
            return True
        if kind == "ShipTargeted":
            state["target"] = None if event.get("TargetLocked") is False else {
                "ship": event.get("Ship_Localised") or event.get("Ship"),
                "pilot": event.get("PilotName_Localised") or event.get("PilotName"),
                "faction": event.get("Faction"), "legal_status": event.get("LegalStatus"),
                "is_thargoid": self._is_thargoid(event.get("Faction"), event.get("Ship"), event.get("PilotName")),
            }
            return True
        if kind in {"Docked", "Shutdown"}:
            return self._archive("combat", kind.lower(), ts)
        if kind == "Died":
            session = state.get("session")
            if not session or not session.get("active"):
                return False
            session["deaths"] += 1
            return self._archive("combat", "died", ts)
        if kind == "Synthesis":
            name = _symbol(event.get("Name")) or "unknown"
            state["synthesis_lifetime"][name] = state["synthesis_lifetime"].get(name, 0) + 1
            session = state.get("session")
            if session and session.get("active"):
                session["synthesis"][name] = session["synthesis"].get(name, 0) + 1
                for item in event.get("Materials") or []:
                    material = _symbol(item.get("Name"))
                    if material:
                        session["synthesis_materials"][material] = session["synthesis_materials"].get(material, 0) + _int(item.get("Count"))
            return True
        starts = {"Bounty", "FactionKillBond", "CapShipBond", "PVPKill", "UnderAttack", "HeatDamage", "HullDamage", "FighterDestroyed"}
        if kind in starts:
            session = self._ensure_combat(ts)
        else:
            session = state.get("session")
            if not session or not session.get("active"):
                return False
        if kind in {"Bounty", "FactionKillBond"}:
            target = state.get("target") or {}
            session["kills"] += 1
            if kind == "Bounty":
                reward = event.get("TotalReward")
                if reward is None:
                    reward = sum(_int(row.get("Reward")) for row in event.get("Rewards") or [])
                session["bounty_cr"] += _int(reward)
            else:
                session["bond_cr"] += _int(event.get("Reward"))
            if self._is_thargoid(event.get("VictimFaction")) or target.get("is_thargoid"):
                session["ax_kills"] += 1
                ship = target.get("ship") or "Unknown Thargoid"
                session["ax_kills_by_type"][ship] = session["ax_kills_by_type"].get(ship, 0) + 1
            state["target"] = None
        elif kind == "CapShipBond":
            session["bond_cr"] += _int(event.get("Reward"))
        elif kind == "PVPKill":
            session["pvp_kills"] += 1
        elif kind in {"HeatDamage", "HullDamage"}:
            session["damage_events"] += 1
        elif kind == "FighterDestroyed":
            session["fighter_losses"] += 1
        elif kind == "RedeemVoucher":
            session["redeemed_cr"] += _int(event.get("Amount"))
        return True

    # Carrier explicit planning -------------------------------------
    def configure_carrier(self, weekly_upkeep_cr, target_weeks):
        with self._lock:
            plan = self.state["carrier"]
            plan["weekly_upkeep_cr"] = max(0, _int(weekly_upkeep_cr))
            plan["reserve_target_weeks"] = max(0, min(520, _int(target_weeks, 8)))
            self._save()

    def set_carrier_inventory(self, rows, source="commander inventory input"):
        inventory = {}
        for row in rows or []:
            name = str(row.get("name") or row.get("symbol") or "").strip()
            symbol = _symbol(row.get("symbol") or name.replace(" ", "_"))
            if symbol:
                inventory[symbol] = {"symbol": symbol, "name": name or symbol.title(), "count": max(0, _int(row.get("count")))}
        with self._lock:
            self.state["carrier"]["inventory"] = inventory
            self.state["carrier"]["inventory_source"] = source
            self._save()

    def plan_carrier_route(self, legs, per_jump=None, reserve=0):
        clean = []
        for row in legs or []:
            system = str(row.get("system") or "").strip()
            distance = _float(row.get("distance_ly"))
            fuel = _float(row.get("tritium_t"))
            if system or distance is not None or fuel is not None:
                clean.append({"system": system, "distance_ly": distance, "tritium_t": fuel})
        with self._lock:
            plan = self.state["carrier"]
            plan["route"] = clean
            plan["tritium_per_jump_t"] = _float(per_jump)
            plan["tritium_reserve_t"] = max(0, _int(reserve))
            self._save()

    def _observe_carrier_transfer(self, event):
        inventory = self.state["carrier"]["inventory"]
        changed = False
        for row in event.get("Transfers") or []:
            symbol = _symbol(row.get("Type"))
            if not symbol:
                continue
            count = _int(row.get("Count"))
            direction = str(row.get("Direction") or "").casefold()
            delta = count if direction == "tocarrier" else -count if direction == "toship" else 0
            current = inventory.setdefault(symbol, {"symbol": symbol, "name": row.get("Type_Localised") or symbol.title(), "count": 0})
            current["count"] = max(0, _int(current.get("count")) + delta)
            changed = changed or bool(delta)
        if changed:
            self.state["carrier"]["inventory_source"] = "commander input plus own-carrier CargoTransfer deltas"
        return changed

    # Exobiology -----------------------------------------------------
    @staticmethod
    def _survey_key(system_address, system, body):
        return f"{system_address if system_address is not None else system or 'unknown'}|{body or 'Unknown body'}"

    def _survey(self, body, radius=None, body_id=None):
        state = self.state["exobiology"]
        body = body or "Unknown body"
        key = self._survey_key(state.get("system_address"), state.get("system"), body)
        survey = state["surveys"].setdefault(key, {
            "key": key, "system": state.get("system"), "system_address": state.get("system_address"),
            "body": body, "body_id": body_id, "radius_m": radius,
            "signal_count": None, "genuses": [], "pins": [], "completed": {}, "updated_ts": None,
        })
        if radius:
            survey["radius_m"] = radius
        if body_id is not None:
            survey["body_id"] = body_id
        return survey

    def _body_name(self, event, context):
        explicit = event.get("BodyName")
        if explicit:
            return explicit
        body = event.get("Body")
        if isinstance(body, str):
            return body
        mapped = self.state["exobiology"].get("body_ids", {}).get(str(body))
        return (mapped or {}).get("name") or context.get("body") or (self.position or {}).get("body")

    def _add_surface_pin(self, survey, kind, label, ts, source, metadata=None, position=None):
        point = position or self.position
        if not point:
            return None
        pin = {
            "id": uuid.uuid4().hex, "kind": kind, "label": label,
            "lat": point["lat"], "lon": point["lon"], "heading": point.get("heading"),
            "alt_m": point.get("alt_m"), "timestamp": ts, "source": source,
            "metadata": metadata or {},
        }
        survey["pins"].append(pin)
        survey["pins"] = survey["pins"][-500:]
        survey["updated_ts"] = ts
        return pin

    def _observe_exobiology(self, event, ts, context):
        state = self.state["exobiology"]
        kind = event["event"]
        if kind in {"Location", "FSDJump"}:
            old = state.get("system_address")
            state["system"] = event.get("StarSystem") or event.get("SystemName")
            state["system_address"] = event.get("SystemAddress")
            if old is not None and old != state["system_address"]:
                state["body_ids"] = {}
                state["sampling"] = None
            return True
        if kind == "ApproachBody":
            self._survey(self._body_name(event, context), body_id=event.get("BodyID"))["updated_ts"] = ts
            return True
        if kind == "Scan":
            body = self._body_name(event, context)
            body_id = event.get("BodyID")
            radius = _float(event.get("Radius"))
            if body_id is not None and body:
                state["body_ids"][str(body_id)] = {"name": body, "radius_m": radius}
            self._survey(body, radius, body_id)["updated_ts"] = ts
            return True
        if kind == "SAASignalsFound":
            survey = self._survey(self._body_name(event, context), body_id=event.get("BodyID"))
            for row in event.get("Signals") or []:
                if "biological" in str(row.get("Type") or "").casefold():
                    survey["signal_count"] = _int(row.get("Count"))
            survey["genuses"] = [{"symbol": row.get("Genus"), "name": row.get("Genus_Localised") or row.get("Genus")} for row in event.get("Genuses") or [] if row.get("Genus")]
            survey["updated_ts"] = ts
            return True
        if kind == "ScanOrganic":
            body = self._body_name(event, context)
            body_id = event.get("Body") if not isinstance(event.get("Body"), str) else None
            mapped = state["body_ids"].get(str(body_id)) if body_id is not None else None
            radius = (self.position or {}).get("radius_m") or (mapped or {}).get("radius_m")
            survey = self._survey(body, radius, body_id)
            scan_type = event.get("ScanType")
            genus = event.get("Genus_Localised") or event.get("Genus")
            species = event.get("Species_Localised") or event.get("Species")
            variant = event.get("Variant_Localised") or event.get("Variant")
            previous = state.get("sampling") or {}
            same = previous.get("species") == species and previous.get("survey_key") == survey["key"]
            group = previous.get("sample_group") if same else uuid.uuid4().hex
            progress = 3 if scan_type == "Analyse" else 1 if scan_type == "Log" or not same else min(3, _int(previous.get("progress"), 1) + 1)
            # Startup catch-up has no trustworthy historic Status position. Keep
            # the sample/completion record, but never pin it at today's location.
            if not context.get("historical"):
                self._add_surface_pin(survey, "organic_sample", variant or species or genus or "Organic sample", ts, "ScanOrganic", {
                    "scan_type": scan_type, "sample_group": group, "progress": progress,
                    "genus": genus, "species": species, "variant": variant,
                })
            if scan_type == "Analyse":
                key = str(species or genus or "unknown")
                completed = survey["completed"].setdefault(key, {"genus": genus, "species": species, "variant": variant, "count": 0})
                completed["count"] += 1
                completed["last_completed_ts"] = ts
                state["sampling"] = None
            else:
                state["sampling"] = {
                    "survey_key": survey["key"], "body": survey["body"],
                    "sample_group": group, "genus": genus, "species": species,
                    "variant": variant, "progress": progress,
                    "colony_m": bio_values.GENUS_COLONY_M.get(genus),
                }
            return True
        if kind in {"Touchdown", "CodexEntry"}:
            if context.get("historical") or not self.position:
                return False
            survey = self._survey(self._body_name(event, context), self.position.get("radius_m"))
            label = "Landing site" if kind == "Touchdown" else event.get("Name_Localised") or event.get("Name") or "Codex discovery"
            self._add_surface_pin(survey, "landing" if kind == "Touchdown" else "codex", label, ts, kind)
            return True
        if kind == "Died":
            state["sampling"] = None
            return True
        if kind == "SellOrganicData":
            state["last_sale_ts"] = ts
            return True
        return False

    def add_pin(self, label, kind="waypoint"):
        with self._lock:
            if not self.position:
                raise ValueError("A live surface position is required")
            survey = self._survey(self.position.get("body"), self.position.get("radius_m"))
            pin = self._add_surface_pin(survey, str(kind), str(label or "Waypoint"), _epoch_ms(), "manual")
            self._save()
            return pin

    def remove_pin(self, pin_id):
        with self._lock:
            for survey in self.state["exobiology"]["surveys"].values():
                before = len(survey.get("pins") or [])
                survey["pins"] = [row for row in survey.get("pins") or [] if row.get("id") != pin_id or row.get("source") != "manual"]
                if len(survey["pins"]) != before:
                    self._save()
                    return True
            return False

    @staticmethod
    def _surface_vector(origin, destination, radius):
        if not origin or not radius:
            return {"distance_m": None, "bearing_deg": None, "east_m": None, "north_m": None}
        lat1, lon1 = math.radians(origin["lat"]), math.radians(origin["lon"])
        lat2, lon2 = math.radians(destination["lat"]), math.radians(destination["lon"])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance = radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(y, x)) % 360
        return {"distance_m": round(distance, 1), "bearing_deg": round(bearing, 1), "east_m": round(distance * math.sin(math.radians(bearing)), 1), "north_m": round(distance * math.cos(math.radians(bearing)), 1)}

    # Presentation ---------------------------------------------------
    def _mining_snapshot(self):
        state = self.state["mining"]
        session = copy.deepcopy(state.get("session"))
        if not session:
            return {"active": False, "session": None, "history": copy.deepcopy(state["history"])}
        refined = [{"symbol": key, **row} for key, row in session["refined"].items()]
        refined.sort(key=lambda row: (-row["count"], row["name"]))
        refined_t = sum(row["count"] for row in refined)
        targets = []
        for key, row in session["prospected_materials"].items():
            sightings = row.get("sightings") or 0
            targets.append({"symbol": key, "name": row.get("name") or key, "sightings": sightings, "best_pct": round(row.get("best_pct") or 0, 2), "average_pct": round((row.get("total_pct") or 0) / sightings, 2) if sightings else 0})
        targets.sort(key=lambda row: (-row["best_pct"], row["name"]))
        duration = max(0, (session.get("ended_ts") or session.get("last_event_ts") or _epoch_ms()) - session["started_ts"]) / 1000
        if session.get("active"):
            duration = max(duration, (_epoch_ms() - session["started_ts"]) / 1000)
        prospectors = max(session["asteroids_prospected"], session["prospector_limpets"])
        start_limpets = (session["cargo_start"].get("drones") or {}).get("count")
        current_limpets = (session["cargo_current"].get("drones") or {}).get("count")
        inventory_used = None if start_limpets is None or current_limpets is None else max(0, start_limpets + session["limpets_bought"] - session["limpets_sold"] - current_limpets)
        deployed = prospectors + session["collector_limpets"] + session["other_limpets"]
        used = max(deployed, inventory_used or 0)
        avg_buy = session["limpet_buy_cost_cr"] / session["limpets_bought"] if session["limpets_bought"] else None
        consumed_cost = round(used * avg_buy) if avg_buy is not None else None
        cash_cost = session["limpet_buy_cost_cr"] - session["limpet_sale_cr"]
        cargo_yield = []
        for row in refined:
            key = row["symbol"]
            cargo_yield.append({**row, "cargo_delta": (session["cargo_current"].get(key) or {}).get("count", 0) - (session["cargo_start"].get(key) or {}).get("count", 0), "sold_t": (session["sales"].get(key) or {}).get("count", 0)})
        session.update(duration_s=round(duration), refined_t=refined_t, refined=refined, cargo_yield=cargo_yield, prospected_materials=targets, tons_per_hour=round(refined_t / (duration / 3600), 2) if duration else None, tons_per_asteroid=round(refined_t / prospectors, 2) if prospectors else None, attributed_revenue_cr=session["attributed_revenue_cr"], net_after_limpet_cash_cr=session["attributed_revenue_cr"] - cash_cost, limpets={"prospectors_used": prospectors, "collectors_launched": session["collector_limpets"], "other_launched": session["other_limpets"], "estimated_used": used, "inventory_accounting": inventory_used, "bought": session["limpets_bought"], "sold": session["limpets_sold"], "remaining": current_limpets, "cash_net_cost_cr": cash_cost, "estimated_consumed_cost_cr": consumed_cost, "cost_source": "observed purchase price" if avg_buy is not None else "unknown", "limpets_per_tonne": round(used / refined_t, 2) if refined_t else None, "cost_per_tonne_cr": round(consumed_cost / refined_t) if consumed_cost is not None and refined_t else None})
        return {"active": bool(session.get("active")), "session": session, "history": copy.deepcopy(state["history"])}

    @staticmethod
    def _ax_readiness(loadout, materials, cargo):
        groups = {key: [] for key in ("ax_weapons", "flak", "xeno_scanners", "shutdown_neutralisers", "caustic_sinks", "heat_sinks", "repair_or_decon", "hull_reinforcement", "module_reinforcement")}
        ammo = []
        for module in (loadout or {}).get("Modules") or []:
            item = _symbol(module.get("Item"))
            row = {"slot": module.get("Slot"), "item": item, "clip": _int(module.get("AmmoInClip")), "hopper": _int(module.get("AmmoInHopper"))}
            row["total"] = row["clip"] + row["hopper"]
            is_ax = any(value in item for value in ("guardian_gauss", "guardian_shard", "guardian_plasma", "ax_multicannon", "ax_missile", "xenokinetic", "causticmissile", "guardian_nanite"))
            checks = (("ax_weapons", is_ax), ("flak", "flakmortar" in item), ("xeno_scanners", "xenoscanner" in item), ("shutdown_neutralisers", any(v in item for v in ("shutdownfieldneutral", "antiunknownshutdown"))), ("caustic_sinks", "causticsink" in item), ("heat_sinks", "heatsinklauncher" in item), ("repair_or_decon", any(v in item for v in ("dronecontrol_repair", "dronecontrol_decontamination", "multidronecontrol_xeno"))), ("hull_reinforcement", "hullreinforcement" in item), ("module_reinforcement", "modulereinforcement" in item))
            for key, present in checks:
                if present:
                    groups[key].append(row)
            if is_ax or any(value in item for value in ("flakmortar", "heatsinklauncher", "causticsink")):
                ammo.append(row)
        present = {key: bool(value) for key, value in groups.items()}
        limpets = _int((cargo.get("drones") or {}).get("count")) if isinstance(cargo, dict) else 0
        score = 35 * present["ax_weapons"] + 15 * present["heat_sinks"] + 10 * present["xeno_scanners"] + 10 * present["flak"] + 10 * present["shutdown_neutralisers"] + 5 * present["hull_reinforcement"] + 5 * present["module_reinforcement"] + 5 * present["caustic_sinks"] + 3 * present["repair_or_decon"] + 2 * bool(limpets)
        level = "not_ax_equipped" if not present["ax_weapons"] else "limited" if not present["heat_sinks"] else "interceptor_tooling_present" if present["flak"] and present["xeno_scanners"] and present["shutdown_neutralisers"] else "scout_or_support_ready"
        raw_materials = (materials or {}).get("Raw") or []
        raw_units = sum(_int(row.get("Count", row.get("count"))) for row in raw_materials if isinstance(row, dict))
        return {"level": level, "score": score, "checklist": present, "modules": groups, "ammo": {"observed_total": sum(row["total"] for row in ammo), "by_module": ammo, "precision": "latest Loadout snapshot; weapon firing is not journaled"}, "cargo_limpets": limpets, "raw_material_units": raw_units}

    def _combat_snapshot(self):
        state = self.state["combat"]
        session = copy.deepcopy(state.get("session"))
        if session:
            stopped = session.get("ended_ts") or session.get("last_event_ts") or _epoch_ms()
            if session.get("active"):
                stopped = _epoch_ms()
            session["duration_s"] = round(max(0, stopped - session["started_ts"]) / 1000)
        return {"active": bool(session and session.get("active")), "session": session, "target": copy.deepcopy(state.get("target")), "readiness": self._ax_readiness(state.get("loadout"), state.get("materials"), state.get("cargo")), "synthesis_lifetime": copy.deepcopy(state.get("synthesis_lifetime")), "history": copy.deepcopy(state["history"])}

    def _carrier_snapshot(self, carrier_data):
        cd = copy.deepcopy(carrier_data or {})
        plan = copy.deepcopy(self.state["carrier"])
        weekly, reserve = plan.get("weekly_upkeep_cr"), cd.get("reserve_balance")
        target = max(0, _int(plan.get("reserve_target_weeks"), 8))
        runway = round(reserve / weekly, 1) if reserve is not None and weekly else None
        shortfall = max(0, weekly * target - reserve) if reserve is not None and weekly else None
        max_range = _float(cd.get("jump_range_curr")) or _float(cd.get("jump_range_max"), 500.0) or 500.0
        issues, rendered, total_distance, total_fuel, fuel_known = [], [], 0.0, 0.0, True
        fuel_sources = set()
        for idx, row in enumerate(plan.get("route") or []):
            distance, fuel = _float(row.get("distance_ly")), _float(row.get("tritium_t"))
            if distance is None or distance <= 0:
                issues.append({"leg": idx + 1, "reason": "distance must be positive"})
            else:
                total_distance += distance
                if distance > max_range:
                    issues.append({"leg": idx + 1, "reason": f"distance exceeds observed {max_range:g} ly range"})
            if fuel is None:
                fuel = _float(plan.get("tritium_per_jump_t"))
                if fuel is not None:
                    fuel_sources.add("configured per-jump estimate")
            else:
                fuel_sources.add("per-leg input")
            if fuel is None:
                fuel_known = False
            else:
                total_fuel += max(0, fuel)
            rendered.append({**row, "distance_ly": distance, "tritium_t": fuel})
        tank = _int(cd.get("fuel_level")) if cd.get("fuel_level") is not None else None
        cargo_tritium = _int((plan["inventory"].get("tritium") or {}).get("count"))
        available = tank + cargo_tritium if tank is not None else None
        required = round(total_fuel, 2) if fuel_known else None
        route_reserve = _int(plan.get("tritium_reserve_t"))
        deficit = max(0, round(required + route_reserve - available, 2)) if required is not None and available is not None else None
        orders = []
        exposure = 0
        for row in cd.get("trade_orders") or []:
            side = str(row.get("type") or "").casefold()
            quantity, price = _int(row.get("amount")), _int(row.get("price"))
            orders.append({"name": row.get("commodity"), "side": side, "quantity": quantity, "price_cr": price, "black_market": bool(row.get("black_market"))})
            if side == "buy":
                exposure += quantity * price
        return {"carrier": cd, "upkeep": {"weekly_cr": weekly, "reserve_weeks": runway, "target_weeks": target, "target_shortfall_cr": shortfall}, "inventory": plan["inventory"], "inventory_source": plan["inventory_source"], "route": {"legs": rendered, "leg_count": len(rendered), "total_distance_ly": round(total_distance, 2), "tritium_required_t": required, "tritium_per_jump_t": plan.get("tritium_per_jump_t"), "tritium_source": ", ".join(sorted(fuel_sources)) if fuel_sources else "unknown; supply per-leg or per-jump input", "tank_t": tank, "cargo_tritium_t": cargo_tritium, "available_t": available, "reserve_t": route_reserve, "deficit_t": deficit, "valid": not issues and (required is not None or not rendered), "issues": issues}, "orders": {"items": orders, "buy_order_exposure_cr": exposure}}

    def _exobio_snapshot(self):
        state = copy.deepcopy(self.state["exobiology"])
        surveys = state.get("surveys") or {}
        chosen = None
        body = (self.position or {}).get("body")
        if body:
            matches = [row for row in surveys.values() if row.get("body") == body]
            chosen = max(matches, key=lambda row: row.get("updated_ts") or 0, default=None)
        if chosen is None and state.get("sampling"):
            chosen = surveys.get(state["sampling"].get("survey_key"))
        if chosen is None and surveys:
            chosen = max(surveys.values(), key=lambda row: row.get("updated_ts") or 0)
        rendered = None
        if chosen:
            rendered = copy.deepcopy(chosen)
            radius = (self.position or {}).get("radius_m") or chosen.get("radius_m")
            center = self.position if self.position and (not self.position.get("body") or self.position.get("body") == chosen.get("body")) else None
            if center is None and chosen.get("pins"):
                first = chosen["pins"][0]
                center = {"lat": first["lat"], "lon": first["lon"], "radius_m": radius}
            pins = []
            for pin in chosen.get("pins") or []:
                vector = self._surface_vector(center, pin, radius)
                relative = None
                if center and center.get("heading") is not None and vector["bearing_deg"] is not None:
                    relative = round((vector["bearing_deg"] - center["heading"] + 540) % 360 - 180, 1)
                pins.append({**pin, **vector, "relative_bearing_deg": relative})
            rendered.update(radius_m=radius, center=center, pins=pins, pins_total=len(pins))
        index = [{"key": row["key"], "system": row.get("system"), "body": row.get("body"), "pins": len(row.get("pins") or []), "completed": len(row.get("completed") or {}), "updated_ts": row.get("updated_ts")} for row in surveys.values()]
        index.sort(key=lambda row: row.get("updated_ts") or 0, reverse=True)
        return {"system": state.get("system"), "system_address": state.get("system_address"), "position": copy.deepcopy(self.position), "sampling": state.get("sampling"), "current_map": rendered, "surveys": index[:50], "last_sale_ts": state.get("last_sale_ts")}

    def snapshot(self, carrier_data=None):
        with self._lock:
            return {"mining": self._mining_snapshot(), "combat": self._combat_snapshot(), "carrier": self._carrier_snapshot(carrier_data), "exobiology": self._exobio_snapshot()}

    def carrier_snapshot(self, carrier_data=None):
        """Return only Carrier workflow state without rebuilding every Specialist view."""
        with self._lock:
            return self._carrier_snapshot(carrier_data)

    def geojson(self):
        current = self.snapshot().get("exobiology", {}).get("current_map") or {}
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]}, "properties": {key: row.get(key) for key in ("id", "kind", "label", "timestamp", "source", "heading", "alt_m")}} for row in current.get("pins") or []], "properties": {"system": current.get("system"), "body": current.get("body"), "radius_m": current.get("radius_m")}}
