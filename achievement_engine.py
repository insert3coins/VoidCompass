from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from persistence_queue import persistence_queue
from typing import Any, Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_field(obj: Any, field: str | None) -> Any:
    if not field or obj is None:
        return None
    current = obj
    for key in str(field).split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _matches_value(value: Any, expected: Any, compare: str | None = None) -> bool:
    compare = compare or ("exists" if expected is None else "eq")
    if compare == "exists":
        return value is not None
    if value is None:
        return False
    if compare == "gte":
        return _number(value) >= _number(expected)
    if compare == "lte":
        return _number(value) <= _number(expected)
    if compare == "gt":
        return _number(value) > _number(expected)
    if compare == "lt":
        return _number(value) < _number(expected)
    if compare == "includes":
        return str(expected) in str(value)
    if compare == "startsWith":
        return str(value).startswith(str(expected))
    if compare == "regex":
        try:
            return re.search(str(expected), str(value), re.I) is not None
        except re.error:
            return False
    if compare == "oneOf":
        return isinstance(expected, list) and value in expected
    if isinstance(expected, list):
        return value in expected
    if isinstance(expected, str) and isinstance(value, str):
        return expected in value or value == expected
    return value == expected


class AchievementEngine:
    """Synchronous, thread-safe Elite journal achievement engine.

    Void Compass already owns journal tailing, commander profiles and cockpit
    notification rendering. This class deliberately owns only catalogue
    matching and per-commander progress so it can share those app services.
    """

    GLOBAL_TRIGGER_TYPES = {
        "creditcheck",
        "distance",
        "distance_traveled",
        "distance_return",
        "playtime",
        "multirank",
        "sessioncounter",
        "sessionsum",
        "sessionunique",
        "sessionstreak",
        "sessionunlocks",
    }

    def __init__(
        self,
        state_path: str | os.PathLike[str],
        *,
        catalogue_path: str | os.PathLike[str] | None = None,
        enabled: bool = True,
        disabled_categories: list[str] | None = None,
        on_unlock: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.catalogue_path = Path(catalogue_path) if catalogue_path else _resource_path("data", "achievements.json")
        self.state_path = Path(state_path)
        self.enabled = bool(enabled)
        self.disabled_categories = set(disabled_categories or [])
        self.on_unlock = on_unlock
        self.lock = threading.RLock()
        self.catalogue = self._load_catalogue()
        self.by_id = {str(item.get("id")): item for item in self.catalogue if item.get("id")}
        self.categories = sorted({str(item.get("category")) for item in self.catalogue if item.get("category")})
        self._by_event: dict[str, list[dict[str, Any]]] = {}
        self._global: list[dict[str, Any]] = []
        self._build_index()
        self.state = self._default_state()
        self.session = self._default_session()
        self._dirty = False
        self._last_save = 0.0
        self._last_playtime_tick = time.monotonic()
        self._rebuilding = False
        self._queued_live_events: list[tuple[dict[str, Any], bool, bool]] = []
        self._load_state()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "unlocked": {},
            "counters": {},
            "sumcounters": {},
            "uniquesets": {},
            "playtimeMinutes": 0,
            "credits": 0,
            "distanceLy": 0,
            "travelledLy": 0,
            "startCoords": None,
            "currentDistanceFromSol": 0,
            "maxDistanceFromSol": 0,
            "lastAchievement": None,
        }

    @staticmethod
    def _default_session() -> dict[str, Any]:
        return {
            "startedAt": _utc_now(),
            "counters": {},
            "sums": {},
            "uniques": {},
            "unlocks": 0,
            "firstLiveUnlock": False,
            "lastShip": None,
            "lastSystem": None,
            "routeProgress": {},
            "sinceDock": {
                "jumps": 0,
                "scans": 0,
                "marketSales": 0,
                "miningRefined": 0,
                "bounties": 0,
            },
        }

    def _load_catalogue(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self.catalogue_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    def _build_index(self) -> None:
        for achievement in self.catalogue:
            trigger = achievement.get("trigger") or {}
            event = trigger.get("event")
            if trigger.get("type") in self.GLOBAL_TRIGGER_TYPES or event is None:
                self._global.append(achievement)
            events = event if isinstance(event, list) else [event]
            for name in events:
                if name:
                    self._by_event.setdefault(str(name), []).append(achievement)

    def _load_state(self) -> None:
        with self.lock:
            merged = self._default_state()
            try:
                raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    merged.update(raw)
            except Exception:
                pass
            merged["unlocked"] = dict(merged.get("unlocked") or {})
            merged["counters"] = dict(merged.get("counters") or {})
            merged["sumcounters"] = dict(merged.get("sumcounters") or {})
            merged["uniquesets"] = {
                key: set(value if isinstance(value, list) else value or [])
                for key, value in (merged.get("uniquesets") or {}).items()
            }
            self.state = merged
            self._dirty = False

    def _serializable_state(self) -> dict[str, Any]:
        output = dict(self.state)
        output["uniquesets"] = {
            key: sorted(value) if isinstance(value, set) else value
            for key, value in (self.state.get("uniquesets") or {}).items()
        }
        return output

    def save(self, *, force: bool = False) -> None:
        with self.lock:
            if not self._dirty and not force:
                return
            now = time.monotonic()
            if not force and (now - self._last_save) < 1.5:
                return
            persistence_queue().submit_json(
                self.state_path,
                self._serializable_state(),
                indent=2,
                delay_s=0.0 if force else 1.5,
                immediate=force,
            )
            self._dirty = False
            self._last_save = now

    def flush(self, wait: bool = True) -> None:
        self.save(force=True)
        if wait:
            persistence_queue().flush(self.state_path, timeout=5.0)

    def switch_profile(
        self,
        state_path: str | os.PathLike[str],
        *,
        enabled: bool | None = None,
        disabled_categories: list[str] | None = None,
    ) -> None:
        self.flush()
        with self.lock:
            self.state_path = Path(state_path)
            if enabled is not None:
                self.enabled = bool(enabled)
            if disabled_categories is not None:
                self.disabled_categories = set(disabled_categories)
            self.session = self._default_session()
            self._last_playtime_tick = time.monotonic()
            self._load_state()

    def set_options(self, *, enabled: bool | None = None, disabled_categories: list[str] | None = None) -> None:
        with self.lock:
            if enabled is not None:
                self.enabled = bool(enabled)
            if disabled_categories is not None:
                self.disabled_categories = set(disabled_categories)

    @staticmethod
    def _event_name(data: dict[str, Any]) -> str:
        return str(data.get("type") or data.get("event") or "")

    @staticmethod
    def _event_payload(data: dict[str, Any]) -> dict[str, Any]:
        raw = data.get("raw")
        if isinstance(raw, dict):
            return dict(raw)
        return dict(data)

    @staticmethod
    def _event_signature(event: str, payload: dict[str, Any]) -> str:
        try:
            return event + "|" + json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        except Exception:
            return event + "|" + str(payload)

    def process_event(self, data: dict[str, Any], *, notify: bool = True, historical: bool = False) -> list[dict[str, Any]]:
        if not self.enabled or not isinstance(data, dict):
            return []
        with self.lock:
            if self._rebuilding:
                self._queued_live_events.append((dict(data), notify, historical))
                return []
            unlocks = self._process_event_locked(data, notify=notify, historical=historical)
            self.save(force=bool(unlocks))
        self._dispatch_unlocks(unlocks)
        return unlocks

    def _process_event_locked(
        self,
        data: dict[str, Any],
        *,
        notify: bool,
        historical: bool,
    ) -> list[dict[str, Any]]:
        event = self._event_name(data)
        if not event:
            return []
        payload = self._event_payload(data)
        payload.setdefault("event", event)

        if event == "LoadGame":
            self.state["credits"] = payload.get("Credits") or self.state.get("credits", 0)
        elif event == "FSDJump":
            self.state["travelledLy"] = self.state.get("travelledLy", 0) + _number(payload.get("JumpDist"))
            position = payload.get("StarPos")
            if isinstance(position, list) and len(position) >= 3:
                distance_from_sol = math.sqrt(sum(_number(position[i]) ** 2 for i in range(3)))
                self.state["currentDistanceFromSol"] = distance_from_sol
                self.state["maxDistanceFromSol"] = max(
                    _number(self.state.get("maxDistanceFromSol")), distance_from_sol
                )
                if not self.state.get("startCoords"):
                    self.state["startCoords"] = position[:3]
                else:
                    start = self.state["startCoords"]
                    self.state["distanceLy"] = math.sqrt(sum((position[i] - start[i]) ** 2 for i in range(3)))

        unlocks: list[dict[str, Any]] = []
        events = [(event, payload)]
        if event == "LaunchFighter" and str(payload.get("Loadout") or "").lower() == "galactic":
            synthetic = dict(payload)
            synthetic.update({"VehicleType": "Nomad", "SRVType": "lander01", "SRVType_Localised": "Nomad"})
            events.append(("LaunchNomad", synthetic))
        if event == "DockSRV" and (
            str(payload.get("SRVType") or "").lower() == "lander01"
            or str(payload.get("SRVType_Localised") or "").lower() == "nomad"
        ):
            synthetic = dict(payload)
            synthetic["VehicleType"] = "Nomad"
            events.append(("DockNomad", synthetic))
        if event == "ScanOrganic" and payload.get("Genus"):
            events.append(("ScanOrganicGenus", payload))

        for event_name, event_data in events:
            if not historical:
                self._update_session(event_name, event_data)
            unlocks.extend(self._evaluate_event(event_name, event_data, historical=historical))

        if unlocks and notify and not historical and not self.session.get("firstLiveUnlock"):
            self.session["firstLiveUnlock"] = True
            unlocks.extend(self._evaluate_event("_meta", {"event": "_meta", "action": "first_live_unlock"}, historical=False))
        unlocks.extend(self._evaluate_dependencies(historical=historical))
        self._dirty = True
        return unlocks if notify and not historical else []

    def _candidate_definitions(self, event: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        output: list[dict[str, Any]] = []
        for achievement in self._by_event.get(event, []) + self._global:
            achievement_id = str(achievement.get("id") or "")
            if achievement_id and achievement_id not in seen:
                seen.add(achievement_id)
                output.append(achievement)
        return output

    def _evaluate_event(self, event: str, data: dict[str, Any], *, historical: bool) -> list[dict[str, Any]]:
        unlocked: list[dict[str, Any]] = []
        for achievement in self._candidate_definitions(event):
            achievement_id = str(achievement.get("id") or "")
            if (
                not achievement_id
                or achievement_id in self.state["unlocked"]
                or achievement.get("category") in self.disabled_categories
            ):
                continue
            trigger = achievement.get("trigger") or {}
            trigger_type = trigger.get("type")
            fired = False

            if trigger_type == "flag":
                if self._matches_event(event, trigger.get("event")):
                    fired = trigger.get("field") is None or _matches_value(
                        _get_field(data, trigger.get("field")), trigger.get("value"), trigger.get("compare")
                    )
            elif trigger_type == "counter":
                if self._matches_event(event, trigger.get("event")) and self._matches_data(data, trigger):
                    self.state["counters"][achievement_id] = self.state["counters"].get(achievement_id, 0) + 1
                    fired = self.state["counters"][achievement_id] >= _number(trigger.get("target"))
            elif trigger_type == "sumcounter":
                if self._matches_event(event, trigger.get("event")) and self._matches_data(data, trigger):
                    amount = _get_field(data, trigger.get("field")) or 0
                    self.state["sumcounters"][achievement_id] = self.state["sumcounters"].get(achievement_id, 0) + _number(amount)
                    fired = self.state["sumcounters"][achievement_id] >= _number(trigger.get("target"))
            elif trigger_type in ("arraycounter", "arraysumcounter"):
                if self._matches_event(event, trigger.get("event")) and self._matches_data(data, trigger):
                    items = _get_field(data, trigger.get("arrayField"))
                    items = items if isinstance(items, list) else []
                    if trigger_type == "arraycounter":
                        amount = sum(
                            _number(_get_field(item, trigger.get("countField")) or 1)
                            for item in items if self._matches_item(item, trigger)
                        )
                    else:
                        fields = trigger.get("fields") or [trigger.get("field")]
                        amount = sum(
                            sum(_number(_get_field(item, field) or 0) for field in fields)
                            for item in items if self._matches_item(item, trigger)
                        )
                    self.state["sumcounters"][achievement_id] = self.state["sumcounters"].get(achievement_id, 0) + amount
                    fired = self.state["sumcounters"][achievement_id] >= _number(trigger.get("target"))
            elif trigger_type in ("uniquecounter", "uniquefromarray"):
                if self._matches_event(event, trigger.get("event")) and self._matches_data(data, trigger):
                    values = self.state["uniquesets"].setdefault(achievement_id, set())
                    if trigger_type == "uniquecounter":
                        value = _get_field(data, trigger.get("field"))
                        if value:
                            values.add(str(value))
                    else:
                        items = _get_field(data, trigger.get("arrayField"))
                        for item in items if isinstance(items, list) else []:
                            if self._matches_item(item, trigger):
                                value = _get_field(item, trigger.get("field"))
                                if value:
                                    values.add(str(value))
                    fired = len(values) >= _number(trigger.get("target"))
            elif trigger_type == "creditcheck":
                fired = event in ("LoadGame", "Missions") and self.state.get("credits", 0) >= _number(trigger.get("target"))
            elif trigger_type == "distance":
                fired = self.state.get("distanceLy", 0) >= _number(trigger.get("target"))
            elif trigger_type == "distance_traveled":
                fired = self.state.get("travelledLy", 0) >= _number(trigger.get("target"))
            elif trigger_type == "distance_return":
                fired = (
                    self.state.get("maxDistanceFromSol", 0) >= _number(trigger.get("target"))
                    and self.state.get("currentDistanceFromSol", 0) <= 500
                )
            elif trigger_type == "playtime":
                fired = self.state.get("playtimeMinutes", 0) >= _number(trigger.get("target"))
            elif trigger_type == "multirank":
                fired = all(rank in self.state["unlocked"] for rank in trigger.get("ranks", []))
            elif trigger_type == "sessioncounter" and not historical:
                fired = self.session["counters"].get(trigger.get("key"), 0) >= _number(trigger.get("target"))
            elif trigger_type == "sessionsum" and not historical:
                fired = self.session["sums"].get(trigger.get("key"), 0) >= _number(trigger.get("target"))
            elif trigger_type == "sessionunique" and not historical:
                fired = len(self.session["uniques"].get(trigger.get("key"), set())) >= _number(trigger.get("target"))
            elif trigger_type == "sessionstreak" and not historical:
                fired = self.session["sinceDock"].get(trigger.get("key"), 0) >= _number(trigger.get("target"))
            elif trigger_type == "sessionunlocks" and not historical:
                fired = self.session["unlocks"] >= _number(trigger.get("target"))
            elif trigger_type == "route" and event == "FSDJump":
                systems = trigger.get("systems") or []
                system = data.get("StarSystem")
                if systems and system:
                    index = self.session["routeProgress"].get(achievement_id, 0)
                    if index < len(systems) and system == systems[index]:
                        self.session["routeProgress"][achievement_id] = index + 1
                    elif system == systems[0]:
                        self.session["routeProgress"][achievement_id] = 1
                    fired = self.session["routeProgress"].get(achievement_id, 0) >= len(systems)

            if fired and self._unlock(achievement, historical=historical):
                unlocked.append(achievement)
        return unlocked

    def _evaluate_dependencies(self, *, historical: bool) -> list[dict[str, Any]]:
        unlocked: list[dict[str, Any]] = []
        for _ in range(3):
            before = len(unlocked)
            for achievement in self._global:
                trigger_type = (achievement.get("trigger") or {}).get("type")
                if trigger_type not in {"multirank", "sessionunlocks"}:
                    continue
                unlocked.extend(self._evaluate_event("_dependency", {}, historical=historical))
                break
            if len(unlocked) == before:
                break
        return unlocked

    def _unlock(self, achievement: dict[str, Any], *, historical: bool) -> bool:
        achievement_id = str(achievement.get("id") or "")
        if not achievement_id or achievement_id in self.state["unlocked"]:
            return False
        self.state["unlocked"][achievement_id] = {
            "unlockedAt": _utc_now(),
            "title": achievement.get("title"),
        }
        self.state["lastAchievement"] = achievement_id
        if not historical:
            self.session["unlocks"] += 1
        self._dirty = True
        return True

    @staticmethod
    def _matches_event(event: str, expected: Any) -> bool:
        return event in expected if isinstance(expected, list) else event == expected

    @staticmethod
    def _matches_data(data: dict[str, Any], trigger: dict[str, Any]) -> bool:
        for field, expected in (trigger.get("match") or {}).items():
            if not _matches_value(_get_field(data, field), expected):
                return False
        if trigger.get("matchField") and not _matches_value(
            _get_field(data, trigger.get("matchField")), trigger.get("matchValue"), trigger.get("compare")
        ):
            return False
        return True

    @staticmethod
    def _matches_item(item: Any, trigger: dict[str, Any]) -> bool:
        if not isinstance(item, dict):
            return False
        if trigger.get("itemMatchField"):
            return _matches_value(
                _get_field(item, trigger.get("itemMatchField")),
                trigger.get("itemMatchValue"),
                trigger.get("itemCompare"),
            )
        for field, expected in (trigger.get("itemMatch") or {}).items():
            if not _matches_value(_get_field(item, field), expected):
                return False
        return True

    def _update_session(self, event: str, data: dict[str, Any]) -> None:
        counters = self.session["counters"]
        sums = self.session["sums"]
        uniques = self.session["uniques"]
        since_dock = self.session["sinceDock"]
        counters["events"] = counters.get("events", 0) + 1

        def count(key: str, amount: int = 1) -> None:
            counters[key] = counters.get(key, 0) + amount

        def add(key: str, amount: Any) -> None:
            sums[key] = sums.get(key, 0) + _number(amount)

        def unique(key: str, value: Any) -> None:
            if value:
                uniques.setdefault(key, set()).add(str(value))

        if event == "FSDJump":
            count("jumps")
            since_dock["jumps"] += 1
            add("jumpLy", data.get("JumpDist"))
            unique("systems", data.get("StarSystem"))
            self.session["lastSystem"] = data.get("StarSystem") or self.session.get("lastSystem")
        elif event == "Scan":
            count("scans")
            since_dock["scans"] += 1
        elif event == "FSSDiscoveryScan":
            count("fss")
        elif event == "SAAScanComplete":
            count("dss")
        elif event == "Docked":
            count("dockings")
            unique("stations", data.get("StationName"))
            self.session["sinceDock"] = {key: 0 for key in since_dock}
        elif event == "MarketSell":
            count("marketSales")
            since_dock["marketSales"] += 1
            add("tradeCredits", data.get("TotalSale"))
        elif event == "MarketBuy":
            add("marketSpend", data.get("TotalCost"))
        elif event == "MiningRefined":
            count("miningRefined")
            since_dock["miningRefined"] += 1
        elif event == "Bounty":
            count("bounties")
            since_dock["bounties"] += 1
            add("bountyCredits", data.get("TotalReward"))
        elif event == "MissionCompleted":
            count("missions")
            add("missionCredits", data.get("Reward"))
        elif event in ("Interdicted", "Interdiction"):
            count("interdictions")
        elif event == "HeatDamage":
            count("heatDamage")
        elif event == "HullDamage":
            count("hullDamage")
        elif event == "SupercruiseExit":
            count("supercruiseExits")
        elif event == "LoadGame":
            self.session["lastShip"] = data.get("Ship") or self.session.get("lastShip")

    def _dispatch_unlocks(self, unlocks: list[dict[str, Any]]) -> None:
        if not callable(self.on_unlock):
            return
        for achievement in unlocks:
            try:
                self.on_unlock(dict(achievement))
            except Exception:
                pass

    def tick_playtime(self, active: bool = True) -> list[dict[str, Any]]:
        """Accrue playtime minutes.

        `active` must be True only while Elite Dangerous is actually running
        (the caller decides, from journal/Status.json freshness). The
        played_*_hours achievements measure time in the game, not time with
        VoidCompass open — so while the game is closed we park the baseline
        at `now`, which both stops accrual and prevents the idle gap from
        being banked the moment the game comes back.
        """
        if not self.enabled:
            return []
        now = time.monotonic()
        with self.lock:
            if self._rebuilding or not active:
                self._last_playtime_tick = now
                return []
        elapsed_minutes = int((now - self._last_playtime_tick) // 60)
        if elapsed_minutes <= 0:
            return []
        with self.lock:
            self._last_playtime_tick += elapsed_minutes * 60
            self.state["playtimeMinutes"] = self.state.get("playtimeMinutes", 0) + elapsed_minutes
            unlocks = self._evaluate_event("_playtime", {}, historical=False)
            unlocks.extend(self._evaluate_dependencies(historical=False))
            self._dirty = True
            self.save(force=bool(unlocks))
        self._dispatch_unlocks(unlocks)
        return unlocks

    def _progress_locked(self, achievement: dict[str, Any]) -> dict[str, Any] | None:
        trigger = achievement.get("trigger") or {}
        achievement_id = str(achievement.get("id") or "")
        trigger_type = trigger.get("type")
        if trigger_type == "counter":
            return {"current": self.state["counters"].get(achievement_id, 0), "target": trigger.get("target")}
        if trigger_type in ("sumcounter", "arraycounter", "arraysumcounter"):
            return {"current": self.state["sumcounters"].get(achievement_id, 0), "target": trigger.get("target")}
        if trigger_type in ("uniquecounter", "uniquefromarray"):
            return {"current": len(self.state["uniquesets"].get(achievement_id, set())), "target": trigger.get("target")}
        if trigger_type == "playtime":
            return {"current": self.state.get("playtimeMinutes", 0), "target": trigger.get("target")}
        if trigger_type == "creditcheck":
            return {"current": self.state.get("credits", 0), "target": trigger.get("target")}
        if trigger_type == "distance":
            return {"current": round(self.state.get("distanceLy", 0)), "target": trigger.get("target")}
        if trigger_type == "distance_traveled":
            return {"current": round(self.state.get("travelledLy", 0)), "target": trigger.get("target")}
        if trigger_type == "distance_return":
            return {"current": round(self.state.get("maxDistanceFromSol", 0)), "target": trigger.get("target")}
        if trigger_type == "sessioncounter":
            return {"current": self.session["counters"].get(trigger.get("key"), 0), "target": trigger.get("target")}
        if trigger_type == "sessionsum":
            return {"current": self.session["sums"].get(trigger.get("key"), 0), "target": trigger.get("target")}
        if trigger_type == "sessionunique":
            return {"current": len(self.session["uniques"].get(trigger.get("key"), set())), "target": trigger.get("target")}
        if trigger_type == "sessionstreak":
            return {"current": self.session["sinceDock"].get(trigger.get("key"), 0), "target": trigger.get("target")}
        if trigger_type == "sessionunlocks":
            return {"current": self.session["unlocks"], "target": trigger.get("target")}
        if trigger_type == "route":
            return {"current": self.session["routeProgress"].get(achievement_id, 0), "target": len(trigger.get("systems") or [])}
        return None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            achievements = []
            total_points = 0
            for achievement in self.catalogue:
                item = dict(achievement)
                achievement_id = str(item.get("id") or "")
                unlock = self.state["unlocked"].get(achievement_id) or {}
                item["unlocked"] = bool(unlock)
                item["unlockedAt"] = unlock.get("unlockedAt")
                item["disabled"] = item.get("category") in self.disabled_categories
                item["progress"] = self._progress_locked(item)
                achievements.append(item)
                if unlock:
                    total_points += int(item.get("points") or 0)
            unlocked = sum(1 for item in achievements if item["unlocked"])
            return {
                "achievements": achievements,
                "unlocked": unlocked,
                "total": len(achievements),
                "totalPoints": total_points,
                "categories": list(self.categories),
                "disabledCategories": sorted(self.disabled_categories),
                "enabled": self.enabled,
                "rebuilding": self._rebuilding,
            }

    def manual_unlock(self, achievement_id: str, *, notify: bool = True) -> bool:
        with self.lock:
            achievement = self.by_id.get(str(achievement_id))
            if not achievement or not self._unlock(achievement, historical=not notify):
                return False
            self.save(force=True)
        if notify:
            self._dispatch_unlocks([achievement])
        return True

    def reset_achievement(self, achievement_id: str) -> bool:
        with self.lock:
            achievement_id = str(achievement_id)
            existed = self.state["unlocked"].pop(achievement_id, None) is not None
            self.state["counters"].pop(achievement_id, None)
            self.state["sumcounters"].pop(achievement_id, None)
            self.state["uniquesets"].pop(achievement_id, None)
            # Route progress lives on the session, not the persisted state.
            # Leaving it behind kept a reset route achievement sitting at 100%,
            # so it re-fired on the very next jump.
            self.session["routeProgress"].pop(achievement_id, None)
            self._dirty = True
            self.save(force=True)
            return existed

    def reset_all(self) -> None:
        with self.lock:
            self.state = self._default_state()
            self.session = self._default_session()
            self._dirty = True
            self.save(force=True)

    def import_legacy_state(self, path: str | os.PathLike[str]) -> dict[str, int]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("The selected file is not an achievement state object.")
        with self.lock:
            imported_unlocked = raw.get("unlocked") or {}
            if isinstance(imported_unlocked, dict):
                self.state["unlocked"].update(imported_unlocked)
            for key in ("counters", "sumcounters"):
                for achievement_id, value in (raw.get(key) or {}).items():
                    self.state[key][achievement_id] = max(_number(self.state[key].get(achievement_id)), _number(value))
            for achievement_id, values in (raw.get("uniquesets") or {}).items():
                self.state["uniquesets"].setdefault(achievement_id, set()).update(values or [])
            for key in ("playtimeMinutes", "distanceLy", "travelledLy", "currentDistanceFromSol", "maxDistanceFromSol"):
                self.state[key] = max(_number(self.state.get(key)), _number(raw.get(key)))
            if raw.get("credits") is not None:
                self.state["credits"] = raw.get("credits")
            if not self.state.get("startCoords") and raw.get("startCoords"):
                self.state["startCoords"] = raw.get("startCoords")
            self._dirty = True
            self.save(force=True)
            return {
                "unlocked": len(imported_unlocked) if isinstance(imported_unlocked, dict) else 0,
                "totalUnlocked": len(self.state["unlocked"]),
            }

    def _merge_prior_progress(self, previous: dict[str, Any]) -> int:
        """Fold pre-rebuild progress back into the freshly-derived state.

        A rebuild can only recreate what the journals still on disk prove.
        Unlocks earned live months ago (or imported from the old app, or
        granted manually) are not re-derivable once those journals rotate
        away, so a bare re-scan silently destroyed them. Progress is treated
        as monotonic: we keep the better of the two everywhere, and prefer the
        ORIGINAL unlock records so their real timestamps survive (a rebuild
        re-stamps everything it re-derives with the time of the rebuild).

        Returns the number of unlocks that only the prior state knew about.
        """
        if not isinstance(previous, dict):
            return 0
        preserved = 0
        for achievement_id, record in (previous.get("unlocked") or {}).items():
            if achievement_id not in self.state["unlocked"]:
                preserved += 1
            # Prior record wins either way: it carries the true unlock time.
            self.state["unlocked"][achievement_id] = record
        for key in ("counters", "sumcounters"):
            for achievement_id, value in (previous.get(key) or {}).items():
                self.state[key][achievement_id] = max(
                    _number(self.state[key].get(achievement_id)), _number(value)
                )
        for achievement_id, values in (previous.get("uniquesets") or {}).items():
            self.state["uniquesets"].setdefault(achievement_id, set()).update(values or [])
        # Monotonic lifetime totals: never let a rebuild walk them backwards.
        for key in ("playtimeMinutes", "travelledLy", "maxDistanceFromSol"):
            self.state[key] = max(_number(self.state.get(key)), _number(previous.get(key)))
        # Point-in-time values: trust the rebuild, fall back to the old value.
        for key in ("credits", "distanceLy", "currentDistanceFromSol"):
            if not _number(self.state.get(key)) and previous.get(key) is not None:
                self.state[key] = previous.get(key)
        if not self.state.get("startCoords") and previous.get("startCoords"):
            self.state["startCoords"] = previous.get("startCoords")
        if not self.state.get("lastAchievement") and previous.get("lastAchievement"):
            self.state["lastAchievement"] = previous.get("lastAchievement")
        return preserved

    def rebuild_history(
        self,
        journal_dir: str | os.PathLike[str],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, int]:
        files = sorted(Path(journal_dir).glob("Journal.*.log"))
        snapshots: list[tuple[Path, int]] = []
        for path in files:
            try:
                snapshots.append((path, path.stat().st_size))
            except OSError:
                pass
        with self.lock:
            if self._rebuilding:
                raise RuntimeError("Achievement history rebuild is already running.")
            previous_state = self.state
            previous_session = self.session
            self._rebuilding = True
            self._queued_live_events = []
            self.state = self._default_state()
            self.session = self._default_session()
            self._dirty = True

        processed = 0
        preserved = 0
        queued_unlocks: list[dict[str, Any]] = []
        scanned_recent: deque[str] = deque(maxlen=6000)
        try:
            for file_index, (path, size) in enumerate(snapshots, 1):
                if callable(progress_callback):
                    progress_callback(file_index - 1, len(snapshots), path.name)
                try:
                    with path.open("rb") as handle:
                        raw_bytes = handle.read(size)
                    for raw_line in raw_bytes.decode("utf-8", errors="ignore").splitlines():
                        try:
                            event_data = json.loads(raw_line)
                        except Exception:
                            continue
                        if not isinstance(event_data, dict) or not event_data.get("event"):
                            continue
                        event = str(event_data.get("event"))
                        scanned_recent.append(self._event_signature(event, event_data))
                        with self.lock:
                            self._process_event_locked(event_data, notify=False, historical=True)
                        processed += 1
                except OSError:
                    continue
                if callable(progress_callback):
                    progress_callback(file_index, len(snapshots), path.name)

            recent_set = set(scanned_recent)
            with self.lock:
                # Carry forward anything the journals on disk can no longer
                # prove (imported/manual/long-ago unlocks) before we accept the
                # rebuilt state as the new truth.
                preserved = self._merge_prior_progress(previous_state)
                queued = list(self._queued_live_events)
                self._queued_live_events = []
                self._rebuilding = False
                for data, notify, historical in queued:
                    event = self._event_name(data)
                    payload = self._event_payload(data)
                    if self._event_signature(event, payload) in recent_set:
                        continue
                    queued_unlocks.extend(self._process_event_locked(data, notify=notify, historical=historical))
                self._dirty = True
                self.save(force=True)
        except Exception:
            with self.lock:
                queued = list(self._queued_live_events)
                self._queued_live_events = []
                self.state = previous_state
                self.session = previous_session
                self._rebuilding = False
                for data, notify, historical in queued:
                    queued_unlocks.extend(self._process_event_locked(data, notify=notify, historical=historical))
                self._dirty = True
                self.save(force=True)
            self._dispatch_unlocks(queued_unlocks)
            raise
        finally:
            with self.lock:
                self._rebuilding = False
        self._dispatch_unlocks(queued_unlocks)
        return {
            "files": len(snapshots),
            "events": processed,
            "unlocked": len(self.state["unlocked"]),
            "preserved": preserved,
        }
