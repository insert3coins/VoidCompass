"""Profile-local, journal-aware expedition missions for VoidCompass."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import math
import os
import threading
import uuid

from galactic_regions import find_region
from persistence_queue import persistence_queue


MAX_EXPEDITIONS = 60
MAX_OBJECTIVES = 250
MAX_BOOKMARKS = 600
MAX_EVENTS = 1200
MAX_SEEN = 15000
MAX_FACTS_PER_KIND = 5000

OBJECTIVE_KINDS = {
    "reach_system": "Reach system",
    "fss_system": "Complete system FSS",
    "sector_fss_count": "Complete FSS surveys inside expedition sector",
    "dss_body": "Map body with DSS",
    "dss_count": "Map bodies with DSS",
    "bio_species": "Analyse biological species",
    "bio_genus": "Complete biological genus",
    "bio_count": "Complete biological analyses",
    "codex_category": "Record Codex category",
    "codex_count": "Record Codex entries",
    "screenshot_system": "Capture system screenshot",
    "screenshot_count": "Capture screenshots",
    "visit_region": "Record galactic region",
    "region_count": "Visit distinct galactic regions",
    "valuable_count": "Find valuable worlds",
    "first_discovery_count": "Find undiscovered bodies",
    "recon_system": "Complete system recon",
    "manual": "Manual objective",
}

OBJECTIVE_TEMPLATES = {
    "regional_passport": {
        "name": "Galactic Region Passport",
        "description": "Visit all 42 Universal Cartographics regions using journal-confirmed arrivals.",
        "objectives": (("region_count", "", 42),),
    },
    "valuable_worlds": {
        "name": "Valuable Worlds Survey",
        "description": "Record ten valuable or terraformable worlds.",
        "objectives": (("valuable_count", "", 10),),
    },
    "biology_collection": {
        "name": "Odyssey Genus Collection",
        "description": "Complete one analysis from each major Odyssey biological genus.",
        "objectives": tuple(
            ("bio_genus", genus, 1) for genus in (
                "Aleoida", "Bacterium", "Cactoida", "Clypeus", "Concha",
                "Electricae", "Fonticulua", "Frutexa", "Fumerola", "Fungoida",
                "Osseus", "Recepta", "Stratum", "Tubus", "Tussock",
            )
        ),
    },
    "sector_survey": {
        "name": "Local Sector Survey",
        "description": "Complete the FSS survey in twenty-five systems inside a chosen sector.",
        "objectives": (("sector_fss_count", "", 25),),
    },
    "codex_fieldwork": {
        "name": "Codex Fieldwork",
        "description": "Record twenty-five distinct Codex entries.",
        "objectives": (("codex_count", "", 25),),
    },
    "photo_chronicle": {
        "name": "Expedition Photo Chronicle",
        "description": "Capture twenty-five journal-confirmed expedition screenshots.",
        "objectives": (("screenshot_count", "", 25),),
    },
    "deep_survey": {
        "name": "Deep Survey",
        "description": "Combine complete systems, DSS mappings, biology and valuable discoveries.",
        "objectives": (
            ("fss_system", "", 20), ("dss_count", "", 20),
            ("bio_count", "", 10), ("valuable_count", "", 5),
        ),
    },
}

SUPPORTED_EVENTS = frozenset({
    "LoadGame", "Shutdown", "Location", "FSDJump", "CarrierJump",
    "FSSDiscoveryScan", "FSSAllBodiesFound", "Scan", "SAAScanComplete", "ScanOrganic",
    "CodexEntry", "FSSSignalDiscovered", "Screenshot",
})

HIGH_VALUE_WORLDS = {"earthlike body", "earth-like world", "water world", "ammonia world"}


def _stamp(raw=None):
    return str((raw or {}).get("timestamp") or datetime.now(timezone.utc).isoformat(timespec="seconds"))


def _epoch(value):
    if isinstance(value, (int, float)):
        return float(value)
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _same(left, right):
    return bool(left and right and str(left).strip().casefold() == str(right).strip().casefold())


def _localized(raw, key, default=""):
    return str(raw.get(f"{key}_Localised") or raw.get(key) or default)


class ExpeditionManager:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self._save_timer = None
        self.data = self._empty()
        self._seen = set()
        self.load()

    @staticmethod
    def _empty():
        return {
            "schema": 1,
            "active_id": None,
            "expeditions": [],
            "bookmarks": [],
            "seen": [],
        }

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return
            with self.lock:
                self.data.update({key: payload.get(key, self.data[key]) for key in self.data})
                self.data["expeditions"] = [
                    self._bounded_expedition(row)
                    for row in (self.data.get("expeditions") or []) if isinstance(row, dict)
                ][-MAX_EXPEDITIONS:]
                self.data["bookmarks"] = [
                    row for row in (self.data.get("bookmarks") or []) if isinstance(row, dict)
                ][-MAX_BOOKMARKS:]
                self.data["seen"] = list(self.data.get("seen") or [])[-MAX_SEEN:]
                self._seen = set(self.data["seen"])
        except (OSError, ValueError, TypeError):
            return

    def _bounded_stats(self, source):
        source = source if isinstance(source, dict) else {}
        clean = self._stats()
        for key in clean:
            if key in {"systems", "facts"}:
                continue
            if key == "distance_ly":
                clean[key] = round(max(0.0, _number(source.get(key))), 2)
            else:
                clean[key] = max(0, _integer(source.get(key)))
        systems = []
        seen_systems = set()
        source_systems = source.get("systems") if isinstance(source.get("systems"), list) else []
        for value in source_systems:
            value = str(value or "").strip()[:120]
            folded = value.casefold()
            if value and folded not in seen_systems:
                systems.append(value)
                seen_systems.add(folded)
        clean["systems"] = systems[-5000:]
        facts = {}
        source_facts = source.get("facts") if isinstance(source.get("facts"), dict) else {}
        for raw_kind, raw_bucket in list(source_facts.items())[:32]:
            kind = str(raw_kind or "fact")[:50]
            if isinstance(raw_bucket, dict):
                items = list(raw_bucket.items())
            elif isinstance(raw_bucket, list):
                items = [(value, True) for value in raw_bucket]
            else:
                items = []
            facts[kind] = {
                str(key or "")[:400].casefold(): True
                for key, _value in items[-MAX_FACTS_PER_KIND:] if str(key or "").strip()
            }
        clean["facts"] = facts
        return clean

    def _bounded_expedition(self, row):
        row = copy.deepcopy(row)
        row["objectives"] = [
            objective for objective in (row.get("objectives") or [])
            if isinstance(objective, dict)
        ][-MAX_OBJECTIVES:]
        for objective in row["objectives"]:
            objective["evidence"] = [
                evidence for evidence in (objective.get("evidence") or [])
                if isinstance(evidence, dict)
            ][-12:]
        row["events"] = [
            event for event in (row.get("events") or []) if isinstance(event, dict)
        ][-MAX_EVENTS:]
        row["stats"] = self._bounded_stats(row.get("stats"))
        plan = row.get("sector_plan")
        if isinstance(plan, dict) and isinstance(plan.get("center"), (list, tuple)):
            try:
                row["sector_plan"] = {
                    "name": str(plan.get("name") or "Expedition sector")[:100],
                    "center": [round(float(plan["center"][index]), 5) for index in range(3)],
                    "radius_ly": max(25.0, min(5000.0, _number(plan.get("radius_ly"), 500))),
                    "cell_size_ly": max(10.0, min(1000.0, _number(plan.get("cell_size_ly"), 100))),
                    "updated": str(plan.get("updated") or _stamp()),
                }
            except (IndexError, TypeError, ValueError):
                row["sector_plan"] = None
        else:
            row["sector_plan"] = None
        return row

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def save(self, immediate=False):
        if not self.path:
            return
        if not immediate:
            with self.lock:
                if self._save_timer is None:
                    self._save_timer = threading.Timer(0.5, self._save_due)
                    self._save_timer.name = "expedition-save"
                    self._save_timer.daemon = True
                    self._save_timer.start()
            return
        persistence_queue().submit_json(
            self.path, self.snapshot(), indent=2, delay_s=0.1, immediate=True,
        )

    def _save_due(self):
        with self.lock:
            self._save_timer = None
        persistence_queue().submit_json(
            self.path, indent=2, delay_s=0.2, source=self.snapshot,
        )

    def flush(self, wait=False):
        with self.lock:
            timer = self._save_timer
            self._save_timer = None
            if timer:
                timer.cancel()
        self.save(immediate=True)
        if wait and self.path:
            persistence_queue().flush(self.path, timeout=1.0)

    def _find_ref(self, expedition_id):
        for row in self.data.get("expeditions") or []:
            if row.get("id") == expedition_id:
                return row
        return None

    def active(self):
        with self.lock:
            row = self._find_ref(self.data.get("active_id"))
            return copy.deepcopy(row) if row else None

    def get(self, expedition_id):
        with self.lock:
            row = self._find_ref(expedition_id)
            return copy.deepcopy(row) if row else None

    def expeditions(self):
        with self.lock:
            return list(reversed(copy.deepcopy(self.data.get("expeditions") or [])))

    @staticmethod
    def _stats():
        return {
            "jumps": 0, "distance_ly": 0.0, "systems": [], "sessions": 0,
            "fss_scans": 0, "bodies_reported": 0, "dss_maps": 0,
            "dss_efficient": 0, "bio_analyses": 0, "codex": 0,
            "signals": 0, "screenshots": 0, "valuable_worlds": 0,
            "first_discoveries": 0, "recon": 0,
            "regions": 0,
            "facts": {},
        }

    def create(self, name, description="", start_system="", destination="", return_system=""):
        name = str(name or "").strip() or f"Expedition {datetime.now().strftime('%Y-%m-%d')}"
        with self.lock:
            active = self._find_ref(self.data.get("active_id"))
            if active and active.get("status") == "active":
                active["status"] = "paused"
                active["updated"] = _stamp()
            expedition = {
                "id": uuid.uuid4().hex[:12], "name": name[:100],
                "description": str(description or "").strip()[:1000],
                "status": "active", "started": _stamp(), "ended": None,
                "updated": _stamp(), "start_system": str(start_system or "")[:120],
                "end_system": str(start_system or "")[:120],
                "destination": str(destination or "")[:120],
                "return_system": str(return_system or "")[:120],
                "objectives": [], "events": [], "stats": self._stats(),
                "sector_plan": None,
            }
            # A named expedition is always created during an active
            # VoidCompass session. Future LoadGame records count subsequent
            # Elite sessions without requiring synthetic journal evidence.
            expedition["stats"]["sessions"] = 1
            if start_system:
                expedition["stats"]["systems"] = [str(start_system)]
            rows = self.data.setdefault("expeditions", [])
            rows.append(expedition)
            self.data["expeditions"] = rows[-MAX_EXPEDITIONS:]
            self.data["active_id"] = expedition["id"]
        self.save()
        return copy.deepcopy(expedition)

    def set_status(self, expedition_id, status):
        status = str(status or "").casefold()
        if status not in {"active", "paused", "completed"}:
            return False
        with self.lock:
            row = self._find_ref(expedition_id)
            if not row:
                return False
            if status == "active":
                other = self._find_ref(self.data.get("active_id"))
                if other and other is not row and other.get("status") == "active":
                    other["status"] = "paused"
                self.data["active_id"] = expedition_id
                row["ended"] = None
            elif self.data.get("active_id") == expedition_id:
                self.data["active_id"] = None
            row["status"] = status
            row["updated"] = _stamp()
            if status == "completed":
                row["ended"] = _stamp()
        self.save()
        return True

    def delete(self, expedition_id):
        with self.lock:
            before = len(self.data.get("expeditions") or [])
            self.data["expeditions"] = [
                row for row in self.data.get("expeditions") or [] if row.get("id") != expedition_id
            ]
            self.data["bookmarks"] = [
                row for row in self.data.get("bookmarks") or [] if row.get("expedition_id") != expedition_id
            ]
            if self.data.get("active_id") == expedition_id:
                self.data["active_id"] = None
            changed = len(self.data["expeditions"]) != before
        if changed:
            self.save()
        return changed

    @staticmethod
    def _objective_title(kind, target, count):
        label = OBJECTIVE_KINDS.get(kind, "Objective")
        if target:
            return f"{label}: {target}"
        if _integer(count, 1) > 1:
            return f"{label}: {_integer(count, 1)}"
        return label

    def add_objective(self, expedition_id, kind, target="", system="", body="", count=1, notes=""):
        kind = kind if kind in OBJECTIVE_KINDS else "manual"
        count = max(1, min(100000, _integer(count, 1)))
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return None
            rows = expedition.setdefault("objectives", [])
            objective = {
                "id": uuid.uuid4().hex[:10], "kind": kind,
                "title": self._objective_title(kind, str(target or "").strip(), count),
                "target": str(target or "").strip()[:200],
                "system": str(system or "").strip()[:120],
                "body": str(body or "").strip()[:160],
                "count": count, "progress": 0, "status": "pending",
                "automatic": kind != "manual", "notes": str(notes or "").strip()[:1000],
                "created": _stamp(), "completed": None, "evidence": [],
            }
            rows.append(objective)
            expedition["objectives"] = rows[-MAX_OBJECTIVES:]
            expedition["updated"] = _stamp()
        self.save()
        return copy.deepcopy(objective)

    def apply_objective_template(self, expedition_id, template_key):
        template = OBJECTIVE_TEMPLATES.get(str(template_key or ""))
        if not template:
            return []
        added = []
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return []
            rows = expedition.setdefault("objectives", [])
            existing = {
                (str(row.get("kind") or ""), str(row.get("target") or "").casefold())
                for row in rows
            }
            for kind, target, count in template["objectives"]:
                identity = (kind, str(target or "").casefold())
                if identity in existing:
                    continue
                objective = {
                    "id": uuid.uuid4().hex[:10], "kind": kind,
                    "title": self._objective_title(kind, target, count),
                    "target": str(target or "")[:200], "system": "", "body": "",
                    "count": max(1, _integer(count, 1)), "progress": 0,
                    "status": "pending", "automatic": True,
                    "notes": f"Template: {template['name']}",
                    "created": _stamp(), "completed": None, "evidence": [],
                }
                rows.append(objective)
                added.append(copy.deepcopy(objective))
                existing.add(identity)
            expedition["objectives"] = rows[-MAX_OBJECTIVES:]
            expedition["updated"] = _stamp()
        if added:
            self.save()
        return added

    def set_sector_plan(self, expedition_id, center, radius_ly=500, cell_size_ly=100,
                        name="Expedition sector"):
        if not isinstance(center, (list, tuple)) or len(center) < 3:
            raise ValueError("A three-coordinate sector centre is required")
        plan = {
            "name": str(name or "Expedition sector").strip()[:100],
            "center": [round(float(center[index]), 5) for index in range(3)],
            "radius_ly": max(25.0, min(5000.0, _number(radius_ly, 500))),
            "cell_size_ly": max(10.0, min(1000.0, _number(cell_size_ly, 100))),
            "updated": _stamp(),
        }
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return None
            expedition["sector_plan"] = plan
            expedition["updated"] = _stamp()
        self.save()
        return copy.deepcopy(plan)

    def clear_sector_plan(self, expedition_id):
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return False
            expedition["sector_plan"] = None
            expedition["updated"] = _stamp()
        self.save()
        return True

    def set_return_system(self, expedition_id, system):
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return False
            expedition["return_system"] = str(system or "").strip()[:120]
            expedition["updated"] = _stamp()
        self.save()
        return True

    def toggle_objective(self, expedition_id, objective_id):
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return False
            objective = next((row for row in expedition.get("objectives") or [] if row.get("id") == objective_id), None)
            if not objective:
                return False
            if objective.get("status") == "complete":
                objective["status"] = "pending"
                objective["progress"] = 0
                objective["completed"] = None
            else:
                objective["status"] = "complete"
                objective["progress"] = max(1, _integer(objective.get("count"), 1))
                objective["completed"] = _stamp()
            expedition["updated"] = _stamp()
        self.save()
        return True

    def remove_objective(self, expedition_id, objective_id):
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return False
            before = len(expedition.get("objectives") or [])
            expedition["objectives"] = [
                row for row in expedition.get("objectives") or [] if row.get("id") != objective_id
            ]
            changed = len(expedition["objectives"]) != before
        if changed:
            self.save()
        return changed

    def add_bookmark(self, kind, system="", body="", title="", priority="Normal", tags=None,
                     notes="", position=None, source="", expedition_id=None):
        kind = str(kind or "POI").strip()[:40]
        system = str(system or "").strip()[:120]
        body = str(body or "").strip()[:160]
        title = str(title or body or system or kind).strip()[:200]
        expedition_id = expedition_id or self.data.get("active_id")
        tag_rows = [str(tag).strip()[:40] for tag in (tags or []) if str(tag).strip()][:12]
        pos = None
        if isinstance(position, (list, tuple)) and len(position) >= 3:
            try:
                pos = [round(float(position[index]), 5) for index in range(3)]
            except (TypeError, ValueError):
                pos = None
        with self.lock:
            duplicate = next((
                row for row in self.data.get("bookmarks") or []
                if row.get("expedition_id") == expedition_id and _same(row.get("system"), system)
                and _same(row.get("body") or "-", body or "-") and _same(row.get("title"), title)
            ), None)
            if duplicate:
                duplicate.update({
                    "priority": str(priority or "Normal").title(), "tags": tag_rows,
                    "notes": str(notes or duplicate.get("notes") or "")[:1000],
                    "position": pos or duplicate.get("position"), "updated": _stamp(),
                })
                bookmark = duplicate
            else:
                bookmark = {
                    "id": uuid.uuid4().hex[:10], "expedition_id": expedition_id,
                    "kind": kind, "system": system, "body": body, "title": title,
                    "priority": str(priority or "Normal").title(), "tags": tag_rows,
                    "notes": str(notes or "").strip()[:1000], "position": pos,
                    "source": str(source or "")[:80], "status": "pending",
                    "created": _stamp(), "updated": _stamp(), "visited": None,
                }
                rows = self.data.setdefault("bookmarks", [])
                rows.append(bookmark)
                self.data["bookmarks"] = rows[-MAX_BOOKMARKS:]
        self.save()
        return copy.deepcopy(bookmark)

    def bookmarks(self, expedition_id=None):
        with self.lock:
            rows = copy.deepcopy(self.data.get("bookmarks") or [])
        if expedition_id is not None:
            rows = [row for row in rows if row.get("expedition_id") == expedition_id]
        return list(reversed(rows))

    def update_bookmark(self, bookmark_id, **updates):
        allowed = {"priority", "tags", "notes", "status", "title"}
        with self.lock:
            bookmark = next((row for row in self.data.get("bookmarks") or [] if row.get("id") == bookmark_id), None)
            if not bookmark:
                return False
            for key, value in updates.items():
                if key not in allowed:
                    continue
                if key == "tags":
                    value = [str(tag).strip()[:40] for tag in (value or []) if str(tag).strip()][:12]
                elif key == "priority":
                    value = str(value or "Normal").title()
                else:
                    value = str(value or "").strip()[:1000]
                bookmark[key] = value
            bookmark["updated"] = _stamp()
            if bookmark.get("status") == "visited" and not bookmark.get("visited"):
                bookmark["visited"] = _stamp()
            elif bookmark.get("status") != "visited":
                bookmark["visited"] = None
        self.save()
        return True

    def remove_bookmark(self, bookmark_id):
        with self.lock:
            before = len(self.data.get("bookmarks") or [])
            self.data["bookmarks"] = [row for row in self.data.get("bookmarks") or [] if row.get("id") != bookmark_id]
            changed = len(self.data["bookmarks"]) != before
        if changed:
            self.save()
        return changed

    @staticmethod
    def _event_key(raw, event_uid=None):
        if event_uid:
            return str(event_uid)
        return "|".join(str(raw.get(key) or "") for key in (
            "timestamp", "event", "StarSystem", "SystemAddress", "BodyName",
            "BodyID", "Species", "EntryID", "Filename",
        ))

    @staticmethod
    def _context(raw, context=None):
        context = context if isinstance(context, dict) else {}
        raw_body = raw.get("BodyName")
        generic_body = raw.get("Body")
        if not raw_body and isinstance(generic_body, str) and not generic_body.isdigit():
            raw_body = generic_body
        return {
            "system": (
                raw.get("StarSystem") or raw.get("SystemName") or raw.get("System")
                or context.get("system") or ""
            ),
            # ScanOrganic reports a numeric Body ID, while Screenshot reports a
            # body name in the same field. Prefer the normalized live body name
            # for numeric records so body-scoped objectives remain usable.
            "body": (
                raw_body or context.get("body") or context.get("body_name")
                or generic_body or ""
            ),
            "position": raw.get("StarPos") or context.get("star_pos") or context.get("position"),
        }

    @staticmethod
    def _new_fact(stats, kind, key):
        """Record one semantic fact so repeated scans cannot inflate goals."""
        key = str(key or "").strip().casefold()
        if not key:
            return True
        facts = stats.setdefault("facts", {})
        bucket = facts.get(kind)
        if isinstance(bucket, list):
            bucket = {str(value).casefold(): True for value in bucket[-MAX_FACTS_PER_KIND:]}
        elif not isinstance(bucket, dict):
            bucket = {}
        facts[kind] = bucket
        if key in bucket:
            return False
        bucket[key] = True
        while len(bucket) > MAX_FACTS_PER_KIND:
            bucket.pop(next(iter(bucket)))
        return True

    @staticmethod
    def _body_fact_key(raw, system, body, suffix=""):
        system_key = raw.get("SystemAddress") or system
        body_key = raw.get("BodyID")
        if body_key is None:
            body_key = raw.get("Body") if isinstance(raw.get("Body"), (int, float)) else body
        return f"{system_key}|{body_key}|{suffix}"

    @staticmethod
    def _record(expedition, raw, kind, title, detail=""):
        rows = expedition.setdefault("events", [])
        rows.append({
            "timestamp": _stamp(raw), "kind": str(kind or "LOG"),
            "title": str(title or "Expedition event")[:240], "detail": str(detail or "")[:500],
        })
        expedition["events"] = rows[-MAX_EVENTS:]

    @staticmethod
    def _add_system(stats, system):
        if system and system not in stats.setdefault("systems", []):
            stats["systems"].append(system)
            stats["systems"] = stats["systems"][-5000:]

    @staticmethod
    def _objective_matches_context(objective, system, body):
        return (
            (not objective.get("system") or _same(objective.get("system"), system))
            and (not objective.get("body") or _same(objective.get("body"), body))
        )

    def _advance(self, expedition, raw, kind, match, evidence, amount=1):
        completed = []
        for objective in expedition.get("objectives") or []:
            if objective.get("status") == "complete" or objective.get("kind") != kind:
                continue
            if not match(objective):
                continue
            count = max(1, _integer(objective.get("count"), 1))
            objective["progress"] = min(count, _integer(objective.get("progress")) + max(1, amount))
            objective.setdefault("evidence", []).append({"timestamp": _stamp(raw), "detail": evidence})
            objective["evidence"] = objective["evidence"][-12:]
            if objective["progress"] >= count:
                objective["status"] = "complete"
                objective["completed"] = _stamp(raw)
                completed.append(objective.get("title") or OBJECTIVE_KINDS.get(kind, kind))
        return completed

    def _visit_bookmarks(self, system, body="", raw=None):
        visited = []
        event_epoch = _epoch((raw or {}).get("timestamp"))
        for bookmark in self.data.get("bookmarks") or []:
            if bookmark.get("status") == "visited" or not _same(bookmark.get("system"), system):
                continue
            if bookmark.get("body") and not _same(bookmark.get("body"), body):
                continue
            if event_epoch and event_epoch < _epoch(bookmark.get("created")):
                continue
            bookmark["status"] = "visited"
            bookmark["visited"] = _stamp(raw)
            visited.append(bookmark.get("title") or bookmark.get("kind") or "Bookmark")
        return visited

    def observe_event(self, raw, context=None, event_uid=None, historical=False):
        if not isinstance(raw, dict):
            return None
        event = raw.get("event")
        if event not in SUPPORTED_EVENTS:
            return None
        with self.lock:
            expedition = self._find_ref(self.data.get("active_id"))
            key = self._event_key(raw, event_uid)
            if key in self._seen:
                return None
            facts = self._context(raw, context)
            system, body = facts["system"], facts["body"]
            bookmark_visited = []
            if event in {"Location", "FSDJump", "CarrierJump"}:
                bookmark_visited = self._visit_bookmarks(system, raw=raw)
            elif event in {"Scan", "SAAScanComplete", "ScanOrganic", "CodexEntry", "Screenshot"}:
                bookmark_visited = self._visit_bookmarks(system, body, raw=raw)
            if not expedition or expedition.get("status") != "active":
                if bookmark_visited:
                    self.save()
                    return {"changed": True, "completed": [], "bookmarks_visited": bookmark_visited,
                            "historical": bool(historical)}
                return None
            if _epoch(raw.get("timestamp")) and _epoch(raw.get("timestamp")) < _epoch(expedition.get("started")):
                if bookmark_visited:
                    self.save()
                    return {"changed": True, "completed": [], "bookmarks_visited": bookmark_visited,
                            "historical": bool(historical)}
                return None
            self._seen.add(key)
            seen = self.data.setdefault("seen", [])
            seen.append(key)
            if len(seen) > MAX_SEEN:
                expired = seen[:-MAX_SEEN]
                self.data["seen"] = seen[-MAX_SEEN:]
                for old in expired:
                    self._seen.discard(old)

            stats = expedition.setdefault("stats", self._stats())
            completed = []
            changed = bool(bookmark_visited)
            if event == "LoadGame":
                stats["sessions"] = _integer(stats.get("sessions")) + 1
                self._record(expedition, raw, "SESSION", "Expedition session resumed", system)
                changed = True
            elif event == "Shutdown":
                self._record(expedition, raw, "SESSION", "Expedition session closed", expedition.get("end_system") or system)
                changed = True
            elif event in {"Location", "FSDJump", "CarrierJump"}:
                self._add_system(stats, system)
                expedition["end_system"] = system or expedition.get("end_system")
                if event in {"FSDJump", "CarrierJump"}:
                    stats["jumps"] = _integer(stats.get("jumps")) + 1
                    stats["distance_ly"] = round(_number(stats.get("distance_ly")) + _number(raw.get("JumpDist")), 2)
                    self._record(expedition, raw, "JUMP", f"Arrived in {system or 'Unknown'}", f"{_number(raw.get('JumpDist')):.1f} ly")
                completed += self._advance(
                    expedition, raw, "reach_system",
                    lambda objective: _same(objective.get("target") or objective.get("system"), system),
                    f"Arrived in {system}",
                )
                position = facts.get("position")
                region = None
                if isinstance(position, (list, tuple)) and len(position) >= 3:
                    try:
                        region = find_region(*(float(position[index]) for index in range(3)))
                    except (TypeError, ValueError):
                        region = None
                if region and self._new_fact(stats, "regions", region[0]):
                    stats["regions"] = _integer(stats.get("regions")) + 1
                    completed += self._advance(
                        expedition, raw, "region_count", lambda _objective: True,
                        f"Entered region {region[0]:02d} {region[1]}",
                    )
                    completed += self._advance(
                        expedition, raw, "visit_region",
                        lambda objective: _same(objective.get("target"), region[1])
                        or _same(objective.get("target"), str(region[0])),
                        f"Entered region {region[0]:02d} {region[1]}",
                    )
                changed = True
            elif event == "FSSDiscoveryScan":
                fact = raw.get("SystemAddress") or system
                if self._new_fact(stats, "honks", fact):
                    stats["bodies_reported"] = _integer(stats.get("bodies_reported")) + _integer(raw.get("BodyCount"))
                    changed = True
            elif event == "FSSAllBodiesFound":
                fact = raw.get("SystemAddress") or system
                if self._new_fact(stats, "fss_systems", fact):
                    stats["fss_scans"] = _integer(stats.get("fss_scans")) + 1
                    completed += self._advance(
                        expedition, raw, "fss_system",
                        lambda objective: (not objective.get("target") or _same(objective.get("target"), system))
                        and self._objective_matches_context(objective, system, body),
                        f"FSS identified all {_integer(raw.get('Count'))} bodies in {system}",
                    )
                    plan = expedition.get("sector_plan") or {}
                    position = facts.get("position")
                    inside_sector = False
                    if (
                        isinstance(position, (list, tuple)) and len(position) >= 3
                        and isinstance(plan.get("center"), (list, tuple))
                        and len(plan["center"]) >= 3
                    ):
                        try:
                            dx = float(position[0]) - float(plan["center"][0])
                            dz = float(position[2]) - float(plan["center"][2])
                            inside_sector = math.hypot(dx, dz) <= float(plan.get("radius_ly") or 0)
                        except (TypeError, ValueError):
                            inside_sector = False
                    if inside_sector:
                        completed += self._advance(
                            expedition, raw, "sector_fss_count", lambda _objective: True,
                            f"Completed sector FSS survey in {system}",
                        )
                    changed = True
            elif event == "Scan":
                planet_class = _localized(raw, "PlanetClass").casefold()
                terraformable = str(raw.get("TerraformState") or "").casefold() == "terraformable"
                valuable = terraformable or planet_class in HIGH_VALUE_WORLDS
                first = raw.get("WasDiscovered") is False
                body_fact = self._body_fact_key(raw, system, body)
                if valuable and self._new_fact(stats, "valuable_bodies", body_fact):
                    stats["valuable_worlds"] = _integer(stats.get("valuable_worlds")) + 1
                    completed += self._advance(
                        expedition, raw, "valuable_count", lambda _objective: True,
                        f"{body or planet_class} in {system}",
                    )
                if first and self._new_fact(stats, "first_bodies", body_fact):
                    stats["first_discoveries"] = _integer(stats.get("first_discoveries")) + 1
                    completed += self._advance(
                        expedition, raw, "first_discovery_count", lambda _objective: True,
                        f"Undiscovered body {body or raw.get('BodyID')} in {system}",
                    )
                changed = valuable or first or changed
            elif event == "SAAScanComplete":
                fact = self._body_fact_key(raw, system, body)
                if self._new_fact(stats, "dss_bodies", fact):
                    stats["dss_maps"] = _integer(stats.get("dss_maps")) + 1
                    probes, target = _integer(raw.get("ProbesUsed")), _integer(raw.get("EfficiencyTarget"))
                    if target and probes and probes <= target:
                        stats["dss_efficient"] = _integer(stats.get("dss_efficient")) + 1
                    completed += self._advance(
                        expedition, raw, "dss_body",
                        lambda objective: _same(objective.get("target") or objective.get("body"), body)
                        and self._objective_matches_context(objective, system, body),
                        f"Mapped {body or raw.get('BodyID')} in {system}",
                    )
                    completed += self._advance(expedition, raw, "dss_count", lambda _objective: True, f"Mapped {body} in {system}")
                    changed = True
            elif event == "ScanOrganic" and str(raw.get("ScanType") or "").casefold() == "analyse":
                species = _localized(raw, "Species") or _localized(raw, "Genus")
                genus = _localized(raw, "Genus") or str(species).split(" ", 1)[0]
                fact = self._body_fact_key(raw, system, body, species)
                if self._new_fact(stats, "bio_analyses", fact):
                    stats["bio_analyses"] = _integer(stats.get("bio_analyses")) + 1
                    completed += self._advance(
                        expedition, raw, "bio_species",
                        lambda objective: _same(objective.get("target"), species)
                        and self._objective_matches_context(objective, system, body),
                        f"Analysed {species} on {body or system}",
                    )
                    completed += self._advance(
                        expedition, raw, "bio_genus",
                        lambda objective: _same(objective.get("target"), genus),
                        f"Completed genus {genus} on {body or system}",
                    )
                    completed += self._advance(expedition, raw, "bio_count", lambda _objective: True, f"Analysed {species}")
                    changed = True
            elif event == "CodexEntry":
                category = _localized(raw, "Category") or _localized(raw, "SubCategory")
                region = _localized(raw, "Region")
                fact = raw.get("EntryID") or self._body_fact_key(raw, system, body, _localized(raw, "Name"))
                if self._new_fact(stats, "codex_entries", fact):
                    stats["codex"] = _integer(stats.get("codex")) + 1
                    completed += self._advance(
                        expedition, raw, "codex_category",
                        lambda objective: _same(objective.get("target"), category),
                        f"{_localized(raw, 'Name', 'Codex entry')} · {category}",
                    )
                    completed += self._advance(expedition, raw, "codex_count", lambda _objective: True, _localized(raw, "Name", "Codex entry"))
                    completed += self._advance(
                        expedition, raw, "visit_region",
                        lambda objective: _same(objective.get("target"), region),
                        f"Codex region fact: {region}",
                    )
                    changed = True
            elif event == "FSSSignalDiscovered":
                stats["signals"] = _integer(stats.get("signals")) + 1
                changed = True
            elif event == "Screenshot":
                fact = raw.get("Filename") or self._body_fact_key(raw, system, body, raw.get("timestamp"))
                if self._new_fact(stats, "screenshots", fact):
                    stats["screenshots"] = _integer(stats.get("screenshots")) + 1
                    completed += self._advance(
                        expedition, raw, "screenshot_system",
                        lambda objective: _same(objective.get("target") or objective.get("system"), system),
                        f"Screenshot in {system}",
                    )
                    completed += self._advance(expedition, raw, "screenshot_count", lambda _objective: True, f"Screenshot in {system}")
                    changed = True

            if completed:
                for title in completed:
                    self._record(expedition, raw, "OBJECTIVE", f"Objective complete: {title}")
                changed = True
            if changed:
                expedition["updated"] = _stamp(raw)
        if changed:
            self.save()
            return {
                "changed": True, "completed": completed,
                "bookmarks_visited": bookmark_visited, "historical": bool(historical),
            }
        return None

    def observe_recon(self, system, score=0):
        with self.lock:
            expedition = self._find_ref(self.data.get("active_id"))
            if not expedition or expedition.get("status") != "active":
                return []
            raw = {"timestamp": _stamp(), "event": "VoidCompassRecon"}
            stats = expedition.setdefault("stats", self._stats())
            if not self._new_fact(stats, "recon_systems", system):
                return []
            stats["recon"] = _integer(stats.get("recon")) + 1
            completed = self._advance(
                expedition, raw, "recon_system",
                lambda objective: _same(objective.get("target") or objective.get("system"), system),
                f"Recon {score}/100 for {system}",
            )
            self._record(expedition, raw, "RECON", f"Recon saved for {system}", f"{_integer(score)}/100")
            expedition["updated"] = _stamp()
        self.save()
        return completed

    @staticmethod
    def progress(expedition):
        objectives = list((expedition or {}).get("objectives") or [])
        complete = sum(1 for row in objectives if row.get("status") == "complete")
        return complete, len(objectives)

    def compass_snapshot(self, next_waypoint=None):
        expedition = self.active()
        if not expedition:
            return {"active": False}
        complete, total = self.progress(expedition)
        pending = next((row for row in expedition.get("objectives") or [] if row.get("status") != "complete"), None)
        stats = expedition.get("stats") or {}
        return {
            "active": True, "id": expedition.get("id"), "name": expedition.get("name"),
            "status": expedition.get("status"), "destination": expedition.get("destination"),
            "return_system": expedition.get("return_system"), "objectives_complete": complete,
            "objectives_total": total, "next_objective": pending.get("title") if pending else None,
            "next_waypoint": next_waypoint, "jumps": _integer(stats.get("jumps")),
            "distance_ly": round(_number(stats.get("distance_ly")), 1),
            "systems": len(stats.get("systems") or []),
            "sessions": _integer(stats.get("sessions")),
        }

    def resume_briefing(self, next_waypoint=None):
        snapshot = self.compass_snapshot(next_waypoint=next_waypoint)
        if not snapshot.get("active"):
            return None
        progress = f"{snapshot['objectives_complete']} of {snapshot['objectives_total']} objectives complete"
        next_action = snapshot.get("next_objective") or (
            f"Next waypoint {snapshot['next_waypoint']}" if snapshot.get("next_waypoint") else "No pending objective"
        )
        return (
            f"Expedition {snapshot['name']} resumed. {progress}. "
            f"{next_action}. {snapshot['systems']} systems and {snapshot['distance_ly']:.1f} light years recorded."
        )

    def export_payload(self, expedition_id):
        with self.lock:
            expedition = self._find_ref(expedition_id)
            if not expedition:
                return None
            bookmarks = [
                row for row in self.data.get("bookmarks") or []
                if row.get("expedition_id") == expedition_id
            ]
            return {
                "format": "voidcompass-expedition", "schema": 1,
                "exported": _stamp(), "expedition": copy.deepcopy(expedition),
                "bookmarks": copy.deepcopy(bookmarks),
            }

    def import_payload(self, payload):
        if not isinstance(payload, dict) or payload.get("format") != "voidcompass-expedition":
            raise ValueError("Not a VoidCompass expedition export")
        source = payload.get("expedition")
        if not isinstance(source, dict):
            raise ValueError("Expedition record is missing")
        expedition = copy.deepcopy(source)
        old_id = expedition.get("id")
        expedition["id"] = uuid.uuid4().hex[:12]
        expedition["name"] = str(expedition.get("name") or "Imported expedition")[:100]
        expedition["description"] = str(expedition.get("description") or "")[:1000]
        expedition["status"] = "paused"
        expedition["ended"] = None
        expedition["updated"] = _stamp()
        expedition = self._bounded_expedition(expedition)
        with self.lock:
            self.data.setdefault("expeditions", []).append(expedition)
            self.data["expeditions"] = self.data["expeditions"][-MAX_EXPEDITIONS:]
            for source_bookmark in payload.get("bookmarks") or []:
                if not isinstance(source_bookmark, dict):
                    continue
                bookmark = copy.deepcopy(source_bookmark)
                bookmark["id"] = uuid.uuid4().hex[:10]
                bookmark["expedition_id"] = expedition["id"]
                bookmark["source"] = f"import:{old_id or 'unknown'}"
                self.data.setdefault("bookmarks", []).append(bookmark)
            self.data["bookmarks"] = self.data["bookmarks"][-MAX_BOOKMARKS:]
        self.save()
        return copy.deepcopy(expedition)

    def waypoint_lines(self, expedition_id):
        expedition = self.get(expedition_id)
        if not expedition:
            return []
        names = []
        for name in (expedition.get("start_system"), expedition.get("destination"), expedition.get("return_system")):
            if name and name not in names:
                names.append(name)
        for objective in expedition.get("objectives") or []:
            name = objective.get("system") or (objective.get("target") if objective.get("kind") == "reach_system" else None)
            if name and name not in names:
                names.append(name)
        for bookmark in reversed(self.bookmarks(expedition_id)):
            name = bookmark.get("system")
            if name and name not in names:
                names.append(name)
        return names

    def report_session(self, expedition):
        expedition = expedition or {}
        stats = expedition.get("stats") or {}
        return {
            "started": expedition.get("started"), "ended": expedition.get("ended"),
            "start_system": expedition.get("start_system"),
            "end_system": expedition.get("end_system"), "jumps": _integer(stats.get("jumps")),
            "distance_ly": _number(stats.get("distance_ly")),
            "fss_surveys": _integer(stats.get("fss_scans")),
            "dss_maps": _integer(stats.get("dss_maps")),
            "bio_analyses": _integer(stats.get("bio_analyses")),
            "codex": _integer(stats.get("codex")),
            "screenshots": _integer(stats.get("screenshots")),
            "highlights": copy.deepcopy(expedition.get("events") or []),
        }

    def markdown_appendix(self, expedition):
        expedition = expedition or {}
        complete, total = self.progress(expedition)
        stats = expedition.get("stats") or {}
        lines = [
            "", "## Expedition Mission Control", "",
            f"- Expedition: {expedition.get('name') or 'Unnamed'}",
            f"- Status: {str(expedition.get('status') or 'unknown').title()}",
            f"- Objective progress: {complete}/{total}",
            f"- Sessions: {_integer(stats.get('sessions'))}",
        ]
        if expedition.get("description"):
            lines.append(f"- Purpose: {expedition['description']}")
        objectives = expedition.get("objectives") or []
        if objectives:
            lines.extend(["", "### Objectives", ""])
            for row in objectives:
                marker = "x" if row.get("status") == "complete" else " "
                progress = f" ({_integer(row.get('progress'))}/{max(1, _integer(row.get('count'), 1))})"
                lines.append(f"- [{marker}] {row.get('title') or 'Objective'}{progress}")
        bookmarks = list(reversed(self.bookmarks(expedition.get("id"))))
        if bookmarks:
            lines.extend(["", "### Bookmarks and revisit targets", ""])
            for row in bookmarks:
                location = " · ".join(filter(None, (row.get("system"), row.get("body"))))
                tags = f" [{', '.join(row.get('tags') or [])}]" if row.get("tags") else ""
                lines.append(
                    f"- {row.get('priority') or 'Normal'} · {row.get('title') or row.get('kind')}"
                    f" — {location or 'Location unspecified'}{tags}"
                )
        return "\n".join(lines)
