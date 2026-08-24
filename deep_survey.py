"""Profile-local deep exploration intelligence derived from Elite journals.

The journal is the authority.  This module deliberately stores compact facts,
not copies of whole journal events, and keeps every collection bounded so a
long-running commander profile remains cheap to load and save.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import math
import os
import threading

from persistence_queue import persistence_queue
from galactic_regions import find_region
from stellar_types import star_type_label


LIMITS = {
    "route_points": 5000,
    "codex": 1500,
    "signals": 2000,
    "dss": 2000,
    "screenshots": 1000,
    "candidates": 250,
    "revisit_queue": 250,
    "milestones": 250,
    "milestone_keys": 1200,
    "seen": 12000,
    "imported_files": 400,
}

HIGH_VALUE_WORLDS = {"Earthlike body", "Water world", "Ammonia world"}
EXOTIC_STARS = {
    "N": "Neutron star",
    "NS": "Neutron star",
    "H": "Black hole",
    "BH": "Black hole",
    "SupermassiveBlackHole": "Supermassive black hole",
}
TRACKED_EVENTS = frozenset({
    "FSDJump", "CarrierJump", "Location", "CodexEntry",
    "FSSSignalDiscovered", "SAAScanComplete", "Screenshot", "Scan",
    "SAASignalsFound", "FSSDiscoveryScan", "FSSAllBodiesFound", "NavBeaconScan",
    "ScanOrganic",
})
IMPORT_EVENTS = TRACKED_EVENTS | {"Commander", "LoadGame"}
IMPORT_MARKERS = tuple(
    marker
    for event in IMPORT_EVENTS
    for marker in (f'"event":"{event}"', f'"event": "{event}"')
)


def _stamp(raw):
    return str((raw or {}).get("timestamp") or datetime.now(timezone.utc).isoformat(timespec="seconds"))


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _position(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return [round(float(value[index]), 5) for index in range(3)]
    except (TypeError, ValueError):
        return None


def _localized(raw, field, default=""):
    return str(raw.get(field + "_Localised") or raw.get(field) or default)


def _event_key(raw, uid=None):
    key = "|".join(str(raw.get(field) or "") for field in (
        "timestamp", "event", "StarSystem", "SystemAddress", "BodyName",
        "BodyID", "EntryID", "SignalName", "Filename",
    ))
    return key if key.strip("|") else str(uid or "")


def item_value(item):
    try:
        if item.get("dss_complete"):
            return int(item.get("dss_reward") or item.get("reward") or 0)
        return int(item.get("reward") or 0)
    except (TypeError, ValueError):
        return 0


def wonder_rows(items):
    """Return measured, explainable stellar/body curiosities for one system."""
    rows = []
    seen = set()

    def add(item, kind, detail, rank=1):
        name = item.get("full_name") or item.get("name") or "Unknown body"
        key = (str(name), kind, detail)
        if key in seen:
            return
        seen.add(key)
        rows.append({"body": name, "kind": kind, "detail": detail, "rank": rank})

    for item in items or []:
        if not isinstance(item, dict):
            continue
        star_type = str(item.get("star_type") or "")
        star_label = star_type_label(star_type, star_type or "Unknown")
        body_class = str(item.get("planet_class") or item.get("class") or "")
        if star_type in EXOTIC_STARS:
            add(item, "Exotic star", EXOTIC_STARS[star_type], 5)
        elif "Wolf-Rayet" in star_label or "Carbon" in star_label:
            add(item, "Rare star", star_label, 4)
        elif "Giant" in star_label or "Supergiant" in star_label:
            add(item, "Giant star", star_label, 3)
        if body_class in HIGH_VALUE_WORLDS:
            add(item, "Notable world", body_class, 4 if body_class == "Earthlike body" else 3)
        if item.get("terraformable"):
            add(item, "Terraform candidate", body_class or "Planet", 3)
        if item.get("was_discovered") is False:
            add(item, "First discovery", "Previously undiscovered body", 3)
        if item.get("first_footfall"):
            add(item, "First footfall", "Landable and not previously footfalled", 3)
        bio = _integer(item.get("bio_count"))
        if bio >= 4:
            add(item, "Biological richness", f"{bio} biological signals", min(5, 2 + bio // 3))
        gravity = _number(item.get("gravity_g"), -1)
        if not item.get("is_star") and gravity >= 2.5:
            add(item, "High gravity", f"{gravity:.2f} g", min(5, int(gravity)))
        temperature = _number(item.get("surface_temp"), -1)
        if not item.get("is_star") and temperature >= 1000:
            add(item, "Extreme heat", f"{temperature:,.0f} K", 3)
        elif not item.get("is_star") and 0 <= temperature <= 40:
            add(item, "Extreme cold", f"{temperature:,.0f} K", 2)
        eccentricity = _number(item.get("eccentricity"), -1)
        if eccentricity >= 0.75:
            add(item, "Eccentric orbit", f"e = {eccentricity:.3f}", 3)
        tilt = abs(_number(item.get("axial_tilt"), 0))
        if tilt >= math.pi / 2:
            add(item, "Extreme axial tilt", f"{math.degrees(tilt):.1f}°", 2)
        rings = item.get("rings") or []
        if rings and item.get("landable"):
            add(item, "Ringed landable", f"{len(rings)} ring record(s)", 3)
        elif rings and item.get("is_star"):
            add(item, "Ringed star", f"{len(rings)} ring record(s)", 4)
        semi_major = _number(item.get("semi_major_axis"), 0)
        if semi_major and semi_major < 1_500_000_000 and not item.get("is_star"):
            add(item, "Close orbit", f"Semi-major axis {semi_major / 1_000_000:.1f} Mm", 2)
    return sorted(rows, key=lambda row: (-row["rank"], row["body"], row["kind"]))


def survey_plan(items):
    """Build a priority-ordered, conservative survey plan from known facts."""
    rows = []
    for item in items or []:
        if (not isinstance(item, dict) or item.get("is_star")
                or not item.get("planet_class")):
            continue
        body = item.get("name") or item.get("full_name") or "Unknown body"
        value = item_value(item)
        bio = _integer(item.get("bio_count"))
        geo = _integer(item.get("geo_count"))
        mapped = bool(item.get("dss_complete") or item.get("was_mapped"))
        organic_done = _integer(item.get("organic_complete_count"))
        action = "Observe"
        reason = "Survey record complete"
        score = 5
        if bio > organic_done:
            action = "Map + sample" if not mapped else "Land + sample"
            reason = f"{bio} biological signal(s), {organic_done} analysis complete"
            score = 100 + bio * 8
        elif bio:
            action = "Review biology"
            reason = f"All {bio} recorded biological signal(s) analysed"
            score = 35
        elif not mapped and (item.get("terraformable") or value >= 250000 or item.get("planet_class") in HIGH_VALUE_WORLDS):
            action = "DSS map"
            reason = "High-value mapping target"
            score = 85 + min(20, value // 250000)
        elif not mapped and item.get("was_discovered") is False:
            action = "DSS map"
            reason = "First-discovery mapping opportunity"
            score = 78
        elif geo and item.get("landable"):
            action = "Surface survey"
            reason = f"{geo} geological signal(s)"
            score = 62 + min(15, geo * 3)
        elif not mapped and item.get("landable"):
            action = "Optional DSS"
            reason = "Landable body; mapping improves surface record"
            score = 38
        elif not mapped:
            action = "Optional DSS"
            reason = "Unmapped body"
            score = 25
        if item.get("first_footfall"):
            score += 12
            reason += "; first-footfall opportunity"
        rows.append({
            "body": body,
            "class": item.get("planet_class") or item.get("class") or "Unknown",
            "action": action,
            "reason": reason,
            "score": score,
            "value": value,
            "bio": bio,
            "geo": geo,
            "distance_ls": _number(item.get("distance_to_arrival"), 0),
            "mapped": mapped,
        })
    return sorted(rows, key=lambda row: (-row["score"], row["distance_ls"], row["body"]))


def architecture_rows(items):
    """Return a journal-parent hierarchy without inventing missing ancestry."""
    bodies = [item for item in (items or []) if isinstance(item, dict)]
    by_id = {str(item.get("body_id")): item for item in bodies if item.get("body_id") is not None}
    children = {key: [] for key in by_id}
    roots = []
    for item in bodies:
        body_id = str(item.get("body_id")) if item.get("body_id") is not None else ""
        parent_id = None
        # Frontier orders Parents nearest-first. Ring/Null references do not
        # identify a scanned body and must not be mistaken for a matching ID.
        for parent in item.get("parents") or []:
            if not isinstance(parent, dict):
                continue
            for kind, value in parent.items():
                if kind not in ("Star", "Planet"):
                    continue
                candidate = str(value)
                if candidate != body_id and candidate in by_id:
                    parent_id = candidate
                    break
            if parent_id is not None:
                break
        if parent_id is not None:
            children.setdefault(parent_id, []).append(item)
        else:
            roots.append(item)

    output = []
    visited = set()

    def walk(item, depth):
        ident = str(item.get("body_id")) if item.get("body_id") is not None else f"name:{item.get('name')}"
        if ident in visited:
            return
        visited.add(ident)
        output.append({"item": item, "depth": depth, "parent_known": depth > 0})
        for child in sorted(children.get(str(item.get("body_id")), []), key=lambda row: _integer(row.get("body_id"), 999999)):
            walk(child, depth + 1)

    for root in sorted(roots, key=lambda row: _integer(row.get("body_id"), 999999)):
        walk(root, 0)
    for item in bodies:
        if (str(item.get("body_id")) if item.get("body_id") is not None else f"name:{item.get('name')}") not in visited:
            walk(item, 0)
    return output


def recon_report(system, items, scanned=0, total=0, traffic=None):
    """Score survey completeness, never legal colonisation eligibility."""
    items = [row for row in (items or []) if isinstance(row, dict)]
    traffic = traffic or {}
    planets = [row for row in items if not row.get("is_star") and row.get("planet_class")]
    mapped = sum(1 for row in planets if row.get("dss_complete") or row.get("was_mapped"))
    landable = sum(1 for row in planets if row.get("landable"))
    bio = sum(_integer(row.get("bio_count")) for row in planets)
    valuable = sum(1 for row in planets if row.get("terraformable") or row.get("planet_class") in HIGH_VALUE_WORLDS)
    completion = (float(scanned) / total) if total else (1.0 if items else 0.0)
    mapping = (float(mapped) / len(planets)) if planets else 0.0
    score = round(min(100.0, completion * 45 + mapping * 25 + min(12, landable * 2) + min(10, bio) + min(8, valuable * 2)))
    gaps = []
    if total and scanned < total:
        gaps.append(f"complete FSS ({scanned}/{total})")
    if planets and mapped < len(planets):
        gaps.append(f"map {len(planets) - mapped} remaining planet(s)")
    if not items:
        gaps.append("scan system bodies")
    return {
        "system": system or "Unknown",
        "score": score,
        "grade": "Comprehensive" if score >= 85 else "Strong" if score >= 65 else "Developing" if score >= 40 else "Preliminary",
        "scanned": scanned,
        "total": total,
        "mapped": mapped,
        "planets": len(planets),
        "landable": landable,
        "bio": bio,
        "valuable": valuable,
        "traffic": {key: _integer(traffic.get(key)) for key in ("day", "week", "total")},
        "gaps": gaps,
        "wonders": wonder_rows(items)[:12],
    }


def _timestamp_epoch(value):
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return 0.0


def expedition_report_markdown(
    *, snapshot=None, session=None, current_system="", current_scan=None,
    system_rows=None, value_rows=None, wonders=None, session_systems=None,
):
    """Build a shareable report from already-retained, journal-backed facts."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    session = session if isinstance(session, dict) else {}
    current_scan = current_scan if isinstance(current_scan, dict) else {}
    system_rows = [row for row in (system_rows or []) if isinstance(row, dict)]
    value_rows = [row for row in (value_rows or []) if isinstance(row, dict)]
    wonders = [row for row in (wonders or []) if isinstance(row, dict)]
    start_epoch = _timestamp_epoch(session.get("started"))
    end_epoch = _timestamp_epoch(session.get("ended")) or float("inf")

    def scoped(key):
        rows = [row for row in (snapshot.get(key) or []) if isinstance(row, dict)]
        if not start_epoch:
            return rows
        return [
            row for row in rows
            if start_epoch <= _timestamp_epoch(row.get("timestamp")) <= end_epoch
        ]

    route_points = scoped("route_points")
    codex = scoped("codex")
    signals = scoped("signals")
    dss = scoped("dss")
    screenshots = scoped("screenshots")
    systems = list(dict.fromkeys(
        str(name) for name in (session_systems or []) if str(name or "").strip()
    ))
    if not systems:
        systems = list(dict.fromkeys(
            str(row.get("system")) for row in route_points if row.get("system")
        ))
    surveyed_systems = system_rows
    if start_epoch:
        surveyed_systems = [
            row for row in surveyed_systems
            if start_epoch <= _timestamp_epoch(row.get("last_seen_ts")) <= end_epoch
        ]

    start_system = session.get("start_system") or (route_points[0].get("system") if route_points else "")
    end_system = (
        session.get("end_system") or current_system
        or (route_points[-1].get("system") if route_points else "")
    )
    jumps = _integer(session.get("jumps"), max(0, len(route_points) - 1))
    distance = _number(session.get("distance_ly"))
    if not distance:
        distance = sum(_number(row.get("jump_dist")) for row in route_points)
    scan_value = sum(_integer(row.get("estimated_value")) for row in surveyed_systems)
    scanned_bodies = sum(_integer(row.get("scanned_bodies")) for row in surveyed_systems)
    efficient_dss = sum(1 for row in dss if row.get("efficient"))
    candidates = [row for row in (snapshot.get("candidates") or []) if isinstance(row, dict)]
    report_date = str(session.get("started") or datetime.now(timezone.utc).isoformat())[:10]

    lines = [
        f"# VoidCompass Expedition Report — {report_date}", "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
        "## Route", "",
        f"- Route: {start_system or 'Unknown'} → {end_system or 'Unknown'}",
        f"- Travel: {jumps:,} jumps · {distance:,.1f} ly",
        f"- Systems represented: {len(systems):,}",
        f"- Current system: {current_system or end_system or 'Unknown'}", "",
        "## Survey", "",
        f"- Current system FSS: {_integer(current_scan.get('scanned'))}/{_integer(current_scan.get('total'))}",
        f"- Current system estimated value: {_integer(current_scan.get('value')):,} cr",
        f"- Session systems in survey archive: {len(surveyed_systems):,}",
        f"- Bodies represented in survey archive: {scanned_bodies:,}",
        f"- Estimated scan value represented: {scan_value:,} cr", "",
        "## Discoveries", "",
        f"- Codex entries: {len(codex):,}",
        f"- Biological analyses: {_integer(session.get('bio_analyses')):,}",
        f"- DSS mappings: {len(dss):,} ({efficient_dss:,} efficiency targets met)",
        f"- Signals recorded: {len(signals):,}",
        f"- Screenshots: {len(screenshots):,}",
    ]
    if codex:
        lines.extend(["", "### Codex highlights", ""])
        for row in codex[-12:]:
            detail = " · ".join(filter(None, (row.get("system"), row.get("category"))))
            lines.append(f"- {row.get('name') or 'Codex entry'}{f' — {detail}' if detail else ''}")
    if value_rows:
        lines.extend(["", "## Top valuable worlds retained for this commander", ""])
        for row in sorted(value_rows, key=lambda item: _integer(item.get("value")), reverse=True)[:12]:
            system = row.get("system") or "Unknown system"
            body = row.get("body") or "Unknown body"
            body_class = row.get("class") or "Unknown class"
            lines.append(f"- {system} · {body} — {body_class}, {_integer(row.get('value')):,} cr")
    if wonders:
        lines.extend(["", f"## Current-system wonders — {current_system or 'Unknown'}", ""])
        for row in wonders[:12]:
            lines.append(f"- {row.get('body') or 'Body'}: {row.get('kind') or 'Notable'} — {row.get('detail') or ''}")
    if candidates:
        lines.extend(["", "## Saved reconnaissance candidates", ""])
        for row in candidates[-12:]:
            lines.append(
                f"- {row.get('system') or 'Unknown'} — "
                f"{_integer(row.get('score'))}/100 {row.get('grade') or 'Preliminary'}"
            )
    highlights = [row for row in (session.get("highlights") or []) if isinstance(row, dict)]
    if highlights:
        lines.extend(["", "## Captain's Log highlights", ""])
        for row in highlights[-30:]:
            detail = f" — {row.get('detail')}" if row.get("detail") else ""
            lines.append(
                f"- {str(row.get('timestamp') or '')[11:19]} "
                f"[{row.get('kind') or 'LOG'}] {row.get('title') or 'Log entry'}{detail}"
            )
    exploration_sales = _integer(session.get("exploration_sales"))
    biology_sales = _integer(session.get("biology_sales"))
    if exploration_sales or biology_sales:
        lines.extend([
            "", "## Data sales", "",
            f"- Exploration data: {exploration_sales:,} cr",
            f"- Biological data: {biology_sales:,} cr",
        ])
    lines.extend([
        "", "---", "",
        "Generated locally by VoidCompass from retained Elite Dangerous journal facts.",
    ])
    return "\n".join(lines)


class DeepSurveyTracker:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.data = self._empty()
        self._seen = set()
        self._milestone_furthest = None
        self._milestone_route_count = 0
        self._milestone_last_route_key = None
        self.load()

    @staticmethod
    def _empty():
        return {
            "schema": 3, "route_points": [], "codex": [], "signals": [],
            "dss": [], "screenshots": [], "candidates": [], "revisit_queue": [], "seen": [],
            "imported_files": {}, "region_stats": {}, "checkpoint": {},
            "last_departure": {}, "milestones": [], "milestone_keys": [],
            "milestones_initialized": False,
        }

    def switch(self, path):
        with self.lock:
            self.path = path
            self.data = self._empty()
            self._seen = set()
            self._milestone_furthest = None
            self._milestone_route_count = 0
            self._milestone_last_route_key = None
            self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                upgrading = _integer(loaded.get("schema"), 1) < 2
                for key in self.data:
                    if key in loaded:
                        self.data[key] = loaded[key]
                self.data["schema"] = 3
                if upgrading:
                    # Re-index journals once in the existing background import.
                    # The retained seen set deduplicates old facts, while newly
                    # tracked FSS/biology events fill the 5.2.5 region passport.
                    self.data["imported_files"] = {}
                self._seen = set(self.data.get("seen") or [])
                if not self.data.get("region_stats") and self.data.get("route_points"):
                    self._rebuild_region_stats()
        except Exception:
            return

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def intelligence_state(self, current_system=""):
        """Return only the small subset needed by the live decision model."""
        wanted = str(current_system or "").casefold()
        with self.lock:
            return {
                "codex": [
                    copy.deepcopy(row) for row in self.data.get("codex") or []
                    if not wanted or str(row.get("system") or "").casefold() == wanted
                ],
                "region_stats": {
                    str(key): {
                        "id": row.get("id"), "name": row.get("name"),
                        "visits": _integer(row.get("visits")),
                    }
                    for key, row in (self.data.get("region_stats") or {}).items()
                    if isinstance(row, dict)
                },
                "checkpoint": copy.deepcopy(self.data.get("checkpoint") or {}),
                "last_departure": copy.deepcopy(self.data.get("last_departure") or {}),
                "milestones": copy.deepcopy((self.data.get("milestones") or [])[-8:]),
                "revisit_queue": copy.deepcopy((self.data.get("revisit_queue") or [])[-8:]),
            }

    def region_passport_state(self):
        """Return the complete 42-region ledger without copying route history."""
        with self.lock:
            return copy.deepcopy(self.data.get("region_stats") or {})

    def codex_state(self):
        """Return the bounded personal Codex ledger for regional gap analysis.

        The live exploration intelligence path intentionally scopes Codex rows
        to the current system.  The Decision Deck needs the commander's wider
        personal history, but none of the much larger route/replay collections.
        """
        with self.lock:
            return copy.deepcopy(self.data.get("codex") or [])

    def replay_state(self, max_points=1200, max_screenshots=240):
        """Return bounded timeline evidence for the interactive chronicle."""
        try:
            point_limit = max(100, min(LIMITS["route_points"], int(max_points)))
            screenshot_limit = max(20, min(LIMITS["screenshots"], int(max_screenshots)))
        except (TypeError, ValueError):
            point_limit, screenshot_limit = 1200, 240
        with self.lock:
            return {
                "route_points": copy.deepcopy((self.data.get("route_points") or [])[-point_limit:]),
                "screenshots": copy.deepcopy((self.data.get("screenshots") or [])[-screenshot_limit:]),
            }

    def save(self, immediate=False):
        if not self.path:
            return
        # This runs on the Tk thread for every journal event. Starting a timer
        # thread here blocked the interface waiting for the new thread to come
        # up, so the persistence queue's own delay does the debouncing instead.
        self._submit_snapshot(immediate=immediate)

    def _submit_snapshot(self, immediate=False):
        with self.lock:
            path = self.path
        if path:
            # snapshot() already deep-copies under this tracker's lock, so
            # handing it over as the producer avoids copying the whole survey
            # twice, and once per coalesced write rather than once per event.
            persistence_queue().submit_json(
                path, indent=2, source=self.snapshot,
                delay_s=0.25 if immediate else 1.0, immediate=immediate,
            )

    def flush(self, wait=False):
        with self.lock:
            path = self.path
        self._submit_snapshot(immediate=True)
        if wait and path:
            persistence_queue().flush(path, timeout=1.0)

    def _append(self, key, row):
        rows = self.data.setdefault(key, [])
        rows.append(row)
        self.data[key] = rows[-LIMITS[key]:]

    def _touch_route(self, raw, **updates):
        system = raw.get("StarSystem") or raw.get("System") or raw.get("SystemName")
        address = raw.get("SystemAddress")
        for row in reversed(self.data.get("route_points") or []):
            if (address is not None and str(row.get("address")) == str(address)) or (system and row.get("system") == system):
                for key, value in updates.items():
                    if isinstance(value, bool):
                        row[key] = value
                    elif isinstance(value, int):
                        row[key] = _integer(row.get(key)) + value
                    elif value not in (None, ""):
                        row[key] = value
                return

    def _set_route(self, raw, **updates):
        system = raw.get("StarSystem") or raw.get("System") or raw.get("SystemName")
        address = raw.get("SystemAddress")
        for row in reversed(self.data.get("route_points") or []):
            if ((address is not None and str(row.get("address")) == str(address))
                    or (system and row.get("system") == system)):
                for key, value in updates.items():
                    if value not in (None, ""):
                        row[key] = value
                return

    def _system_position(self, system):
        if not system:
            return None
        wanted = str(system).casefold()
        for row in reversed(self.data.get("route_points") or []):
            if str(row.get("system") or "").casefold() == wanted:
                return _position(row.get("pos"))
        return None

    def _region_row(self, position, timestamp="", system="", visit=False, jump_dist=0.0):
        position = _position(position)
        region = find_region(*position) if position else None
        if not region:
            return None
        key = str(region[0])
        stats = self.data.setdefault("region_stats", {})
        row = stats.setdefault(key, {
            "id": region[0], "name": region[1], "visits": 0,
            "systems": [], "distance_ly": 0.0, "fss": 0, "dss": 0,
            "biology": 0, "codex": 0, "screenshots": 0, "notable": 0,
            "first_visit": "", "last_visit": "", "last_system": "",
            "last_photo": "",
        })
        if visit:
            row["visits"] = _integer(row.get("visits")) + 1
            row["distance_ly"] = round(
                _number(row.get("distance_ly")) + max(0.0, _number(jump_dist)), 2,
            )
        system = str(system or "")
        if system:
            systems = list(row.get("systems") or [])
            if not any(str(name).casefold() == system.casefold() for name in systems):
                systems.append(system)
                row["systems"] = systems[-LIMITS["route_points"]:]
            row["last_system"] = system
        timestamp = str(timestamp or "")
        if timestamp:
            row["first_visit"] = row.get("first_visit") or timestamp
            if timestamp >= str(row.get("last_visit") or ""):
                row["last_visit"] = timestamp
        return row

    def _touch_region(self, system, metric=None, amount=1, timestamp="", **updates):
        row = self._region_row(
            self._system_position(system), timestamp=timestamp, system=system,
        )
        if not row:
            return
        if metric:
            row[metric] = _integer(row.get(metric)) + _integer(amount, 1)
        for key, value in updates.items():
            if value not in (None, ""):
                row[key] = value

    def _rebuild_region_stats(self):
        self.data["region_stats"] = {}
        positions = {}
        for row in self.data.get("route_points") or []:
            region_row = self._region_row(
                row.get("pos"), row.get("timestamp"), row.get("system"),
                visit=True, jump_dist=row.get("jump_dist"),
            )
            system = str(row.get("system") or "")
            if system:
                positions[system.casefold()] = row.get("pos")
            if region_row is not None and row.get("fss_complete"):
                region_row["fss"] = _integer(region_row.get("fss")) + 1
        for key, metric in (("codex", "codex"), ("dss", "dss"), ("screenshots", "screenshots")):
            for row in self.data.get(key) or []:
                system = str(row.get("system") or "")
                region_row = self._region_row(
                    positions.get(system.casefold()), timestamp=row.get("timestamp"),
                    system=system,
                )
                if region_row is not None:
                    region_row[metric] = _integer(region_row.get(metric)) + 1
                    if metric == "screenshots" and row.get("filename"):
                        region_row["last_photo"] = row.get("filename")

    def _system_name(self, raw, context=None):
        context = context if isinstance(context, dict) else {}
        direct = (raw.get("StarSystem") or raw.get("System") or raw.get("SystemName")
                  or context.get("star_system") or context.get("system"))
        if direct:
            return str(direct)
        address = raw.get("SystemAddress") or context.get("system_address")
        if address is not None:
            for row in reversed(self.data.get("route_points") or []):
                if str(row.get("address")) == str(address):
                    return str(row.get("system") or "")
        return ""

    def observe_event(self, raw, context=None, event_uid=None, save=True):
        if not isinstance(raw, dict):
            return False
        event = raw.get("event")
        if event not in TRACKED_EVENTS:
            return False
        key = _event_key(raw, event_uid)
        with self.lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            seen_rows = self.data.setdefault("seen", [])
            seen_rows.append(key)
            if len(seen_rows) > LIMITS["seen"]:
                overflow = len(seen_rows) - LIMITS["seen"]
                expired = seen_rows[:overflow]
                del seen_rows[:overflow]
                for expired_key in expired:
                    self._seen.discard(expired_key)
            changed = True
            if event in {"FSDJump", "CarrierJump", "Location"}:
                pos = _position(raw.get("StarPos"))
                if pos:
                    row = {
                        "timestamp": _stamp(raw), "event": event,
                        "system": raw.get("StarSystem") or "Unknown",
                        "address": raw.get("SystemAddress"), "pos": pos,
                        "jump_dist": round(_number(raw.get("JumpDist")), 2),
                        "star_class": raw.get("StarClass") or "",
                        "discoveries": 0, "codex": 0, "signals": 0,
                        "screenshots": 0,
                    }
                    points = self.data.setdefault("route_points", [])
                    duplicate = points and points[-1].get("system") == row["system"] and points[-1].get("timestamp") == row["timestamp"]
                    if not duplicate:
                        self._append("route_points", row)
                        self._region_row(
                            pos, row["timestamp"], row["system"], visit=True,
                            jump_dist=row.get("jump_dist"),
                        )
            elif event == "CodexEntry":
                self._append("codex", {
                    "timestamp": _stamp(raw), "system": self._system_name(raw, context),
                    "address": raw.get("SystemAddress"), "body_id": raw.get("BodyID"),
                    "entry_id": raw.get("EntryID"), "name": _localized(raw, "Name", "Codex entry"),
                    "category": _localized(raw, "Category"), "subcategory": _localized(raw, "SubCategory"),
                    "region": _localized(raw, "Region"), "new": bool(raw.get("IsNewEntry")),
                    "voucher": _integer(raw.get("VoucherAmount")), "latitude": raw.get("Latitude"),
                    "longitude": raw.get("Longitude"), "traits": list(raw.get("Traits") or []),
                })
                self._touch_route(raw, codex=1, discoveries=1)
                self._touch_region(
                    self._system_name(raw, context), "codex", timestamp=_stamp(raw),
                )
            elif event == "FSSSignalDiscovered":
                self._append("signals", {
                    "timestamp": _stamp(raw), "system": self._system_name(raw, context),
                    "address": raw.get("SystemAddress"), "name": _localized(raw, "SignalName", "Signal"),
                    "type": raw.get("SignalType") or raw.get("USSType") or "",
                    "threat": _integer(raw.get("ThreatLevel")),
                    "time_remaining": _number(raw.get("TimeRemaining")),
                    "station": bool(raw.get("IsStation")),
                })
                self._touch_route(raw, signals=1)
            elif event == "SAAScanComplete":
                probes = _integer(raw.get("ProbesUsed"))
                target = _integer(raw.get("EfficiencyTarget"))
                self._append("dss", {
                    "timestamp": _stamp(raw), "system": self._system_name(raw, context),
                    "address": raw.get("SystemAddress"), "body": raw.get("BodyName") or "",
                    "body_id": raw.get("BodyID"), "probes": probes, "target": target,
                    "efficient": bool(target and probes and probes <= target),
                })
                self._touch_region(
                    self._system_name(raw, context), "dss", timestamp=_stamp(raw),
                )
            elif event == "Screenshot":
                self._append("screenshots", {
                    "timestamp": _stamp(raw), "filename": raw.get("Filename") or "",
                    "system": self._system_name(raw, context),
                    "body": raw.get("Body") or raw.get("BodyName") or "",
                    "latitude": raw.get("Latitude"), "longitude": raw.get("Longitude"),
                    "altitude": raw.get("Altitude"), "heading": raw.get("Heading"),
                    "width": raw.get("Width"), "height": raw.get("Height"),
                })
                self._touch_route(raw, screenshots=1)
                self._touch_region(
                    self._system_name(raw, context), "screenshots",
                    timestamp=_stamp(raw), last_photo=raw.get("Filename") or "",
                )
            elif event == "Scan":
                self._touch_route(
                    raw,
                    discoveries=1 if raw.get("WasDiscovered") is False else 0,
                    star_class=raw.get("StarType"),
                )
                planet_class = str(raw.get("PlanetClass") or "")
                if planet_class in HIGH_VALUE_WORLDS or str(raw.get("TerraformState") or "") == "Terraformable":
                    self._touch_region(
                        self._system_name(raw, context), "notable", timestamp=_stamp(raw),
                    )
            elif event == "SAASignalsFound":
                self._touch_route(raw, discoveries=1 if (raw.get("Signals") or raw.get("Genuses")) else 0)
            elif event == "FSSDiscoveryScan":
                updates = {"body_count": _integer(raw.get("BodyCount"))}
                try:
                    if float(raw.get("Progress")) >= 1.0:
                        updates["fss_complete"] = True
                except (TypeError, ValueError):
                    pass
                self._set_route(raw, **updates)
            elif event == "NavBeaconScan":
                self._set_route(
                    raw, fss_complete=True,
                    body_count=_integer(raw.get("NumBodies")),
                )
            elif event == "FSSAllBodiesFound":
                self._set_route(
                    raw, fss_complete=True,
                    body_count=_integer(raw.get("Count") or raw.get("BodyCount")),
                )
                self._touch_region(
                    self._system_name(raw, context), "fss", timestamp=_stamp(raw),
                )
            elif event == "ScanOrganic" and str(raw.get("ScanType") or "").casefold() == "analyse":
                self._touch_region(
                    self._system_name(raw, context), "biology", timestamp=_stamp(raw),
                )
        if changed and save:
            self.save()
        return changed

    @staticmethod
    def _commander_matches(raw, commander=None, fid=None):
        event = raw.get("event")
        if event == "Commander":
            name, event_fid = raw.get("Name"), raw.get("FID")
        elif event == "LoadGame":
            name, event_fid = raw.get("Commander"), raw.get("FID")
        else:
            return True
        if fid and event_fid:
            return str(fid).casefold() == str(event_fid).casefold()
        if commander and name:
            return str(commander).casefold() == str(name).casefold()
        return not bool(commander or fid)

    def import_journals(self, journal_path, commander=None, fid=None):
        if not journal_path or not os.path.isdir(journal_path):
            return 0
        count = 0
        imported = dict(self.data.get("imported_files") or {})
        files = sorted(os.path.join(journal_path, name) for name in os.listdir(journal_path)
                       if name.startswith("Journal.") and name.endswith(".log"))
        for path in files:
            try:
                signature = f"{os.path.getsize(path)}:{int(os.path.getmtime(path))}"
            except OSError:
                continue
            name = os.path.basename(path)
            if imported.get(name) == signature:
                continue
            active = not bool(commander or fid)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        if not any(marker in line for marker in IMPORT_MARKERS):
                            continue
                        try:
                            raw = json.loads(line)
                        except Exception:
                            continue
                        if raw.get("event") in ("Commander", "LoadGame"):
                            active = self._commander_matches(raw, commander, fid)
                        if active and self.observe_event(raw, save=False):
                            count += 1
            except OSError:
                continue
            imported[name] = signature
        with self.lock:
            self.data["imported_files"] = dict(list(imported.items())[-LIMITS["imported_files"]:])
            for key in ("route_points", "codex", "signals", "dss", "screenshots"):
                self.data[key] = sorted(
                    self.data.get(key) or [], key=lambda row: str(row.get("timestamp") or "")
                )[-LIMITS[key]:]
        self.save()
        return count

    def save_candidate(self, report, notes=""):
        row = dict(report or {})
        row["saved"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        row["notes"] = str(notes or "").strip()
        system = row.get("system")
        with self.lock:
            candidates = [entry for entry in self.data.get("candidates") or [] if entry.get("system") != system]
            candidates.append(row)
            self.data["candidates"] = candidates[-LIMITS["candidates"]:]
        self.save()
        return row

    def record_revisit(self, candidate):
        """Add or update one bounded, profile-local missed-opportunity row."""
        row = copy.deepcopy(candidate) if isinstance(candidate, dict) else {}
        system = str(row.get("system") or "").strip()
        if not system:
            return None
        row["system"] = system
        with self.lock:
            rows = [
                entry for entry in self.data.get("revisit_queue") or []
                if str(entry.get("system") or "").casefold() != system.casefold()
            ]
            rows.append(row)
            self.data["revisit_queue"] = rows[-LIMITS["revisit_queue"]:]
        self.save()
        return copy.deepcopy(row)

    def revisit_queue(self, limit=30):
        """Return only revisit rows so live Explore refreshes avoid copying the full archive."""
        try:
            limit = max(1, min(LIMITS["revisit_queue"], int(limit)))
        except (TypeError, ValueError):
            limit = 30
        with self.lock:
            return copy.deepcopy((self.data.get("revisit_queue") or [])[-limit:])

    def dismiss_revisit(self, system):
        system_key = str(system or "").strip().casefold()
        if not system_key:
            return False
        with self.lock:
            before = len(self.data.get("revisit_queue") or [])
            self.data["revisit_queue"] = [
                row for row in self.data.get("revisit_queue") or []
                if str(row.get("system") or "").casefold() != system_key
            ]
            changed = len(self.data["revisit_queue"]) != before
        if changed:
            self.save()
        return changed

    def update_checkpoint(self, payload, immediate=False):
        row = copy.deepcopy(payload) if isinstance(payload, dict) else {}
        with self.lock:
            self.data["checkpoint"] = row
            if str(row.get("reason") or "").casefold() in {"departure", "startjump"}:
                self.data["last_departure"] = copy.deepcopy(row)
        self.save(immediate=immediate)
        return copy.deepcopy(row)

    def checkpoint(self):
        with self.lock:
            return copy.deepcopy(self.data.get("checkpoint") or {})

    def evaluate_milestones(self, current_bodies=None, timestamp=None):
        """Record bounded, meaningful exploration milestones and return new rows."""
        timestamp = str(timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"))
        with self.lock:
            route = list(self.data.get("route_points") or [])
            regions = self.data.get("region_stats") or {}
            region_rows = [row for row in regions.values() if isinstance(row, dict)]

            # Region passport rows already maintain the same cumulative values.
            # Reading at most 42 regions avoids rescanning up to 5,000 route
            # points for every Scan/FSS journal event. Distance from Sol is
            # monotonic for milestone purposes, so only newly appended/current
            # route points need to be considered after the first evaluation.
            region_systems = sum(len(row.get("systems") or []) for row in region_rows)
            region_distance = sum(max(0.0, _number(row.get("distance_ly"))) for row in region_rows)
            region_fss = sum(max(0, _integer(row.get("fss"))) for row in region_rows)
            if not region_rows:
                region_systems = len({
                    str(row.get("system") or "").casefold()
                    for row in route if row.get("system")
                })
                region_distance = sum(max(0.0, _number(row.get("jump_dist"))) for row in route)
                region_fss = sum(1 for row in route if row.get("fss_complete"))

            last_route_key = None
            if route:
                last = route[-1]
                last_route_key = (
                    last.get("timestamp"), last.get("system"),
                    tuple(_position(last.get("pos")) or ()),
                )
            if self._milestone_furthest is None:
                distance_rows = route
                self._milestone_furthest = 0.0
            elif len(route) > self._milestone_route_count:
                distance_rows = route[self._milestone_route_count:]
            elif last_route_key != self._milestone_last_route_key:
                # The bounded route may have rotated at 5,000 entries or the
                # current row may have gained coordinates after arrival.
                distance_rows = route[-1:]
            else:
                distance_rows = ()
            for row in distance_rows:
                pos = _position(row.get("pos"))
                if pos:
                    self._milestone_furthest = max(
                        self._milestone_furthest,
                        math.sqrt(sum(value * value for value in pos)),
                    )
            self._milestone_route_count = len(route)
            self._milestone_last_route_key = last_route_key
            metrics = {
                "systems": region_systems,
                "distance": region_distance,
                "regions": len([row for row in region_rows if _integer(row.get("visits"))]),
                "fss": region_fss,
                "dss": len(self.data.get("dss") or []),
                "biology": sum(_integer(row.get("biology")) for row in region_rows),
                "codex": len(self.data.get("codex") or []),
                "photos": len(self.data.get("screenshots") or []),
                "furthest": self._milestone_furthest,
            }
            definitions = (
                ("systems", "Systems visited", (100, 250, 500, 1000, 2500, 5000)),
                ("distance", "Light-years journalled", (1000, 5000, 10000, 25000, 50000, 100000)),
                ("regions", "Galactic regions visited", (1, 5, 10, 21, 42)),
                ("fss", "Complete system surveys", (10, 25, 50, 100, 250, 500)),
                ("dss", "Bodies mapped", (10, 25, 50, 100, 250, 500, 1000)),
                ("biology", "Biological analyses", (5, 10, 25, 50, 100, 250)),
                ("codex", "Codex discoveries", (10, 25, 50, 100, 250, 500)),
                ("photos", "Expedition photographs", (10, 25, 50, 100, 250)),
                ("furthest", "Distance from Sol", (1000, 5000, 10000, 25000, 50000, 65000)),
            )
            key_order = list(dict.fromkeys(self.data.get("milestone_keys") or []))
            known = set(key_order)
            added = []
            initializing = not bool(self.data.get("milestones_initialized"))
            baseline_existing = bool(
                len(route) > 1 or self.data.get("dss") or self.data.get("codex")
                or self.data.get("screenshots")
            )

            def add(key, kind, title, detail, level=2, system=""):
                if key in known:
                    return
                known.add(key)
                key_order.append(key)
                row = {
                    "key": key, "timestamp": timestamp, "kind": kind,
                    "title": title, "detail": detail, "level": level,
                    "system": system,
                }
                added.append(row)
                self._append("milestones", row)

            for metric, label, thresholds in definitions:
                value = metrics[metric]
                for threshold in thresholds:
                    if value >= threshold:
                        key = f"{metric}:{threshold}"
                        if initializing and baseline_existing:
                            if key not in known:
                                known.add(key)
                                key_order.append(key)
                            continue
                        suffix = " ly" if metric in {"distance", "furthest"} else ""
                        add(
                            key, metric,
                            f"{label}: {threshold:,}{suffix}",
                            f"Verified total is now {value:,.1f}{suffix}" if suffix else f"Verified total is now {int(value):,}",
                            4 if threshold == thresholds[-1] else 3 if threshold >= thresholds[len(thresholds) // 2] else 2,
                        )
            current_system = ""
            if route:
                current_system = str(route[-1].get("system") or "")
            for item in current_bodies or []:
                if not isinstance(item, dict):
                    continue
                body = item.get("full_name") or item.get("name") or "Unknown body"
                planet_class = str(item.get("planet_class") or item.get("class") or "")
                if planet_class in {"Earthlike body", "Ammonia world"}:
                    add(
                        f"world:{current_system.casefold()}:{str(body).casefold()}:{planet_class}",
                        "notable-world", f"{planet_class} recorded", str(body),
                        4, current_system,
                    )
                for scan in (item.get("organic_scans") or {}).values():
                    if not isinstance(scan, dict) or not scan.get("is_complete"):
                        continue
                    value = _integer(scan.get("species_value"))
                    if value >= 15_000_000:
                        species = scan.get("species") or scan.get("genus") or "Rare biology"
                        add(
                            f"rare-bio:{current_system.casefold()}:{str(body).casefold()}:{str(species).casefold()}",
                            "rare-biology", f"Rare biology analysed: {species}",
                            f"{body} · base value {value:,} cr", 4, current_system,
                        )
            self.data["milestone_keys"] = key_order[-LIMITS["milestone_keys"]:]
            self.data["milestones_initialized"] = True
        if added or initializing:
            self.save()
        return copy.deepcopy(added)

    def remove_candidate(self, system):
        with self.lock:
            before = len(self.data.get("candidates") or [])
            self.data["candidates"] = [row for row in self.data.get("candidates") or [] if row.get("system") != system]
            changed = len(self.data["candidates"]) != before
        if changed:
            self.save()
        return changed

    @staticmethod
    def recon_markdown(report):
        report = report or {}
        traffic = report.get("traffic") or {}
        lines = [
            f"# Colonisation Recon — {report.get('system') or 'Unknown'}", "",
            f"Survey readiness: {report.get('score', 0)}/100 ({report.get('grade', 'Preliminary')})",
            f"Bodies: {report.get('scanned', 0)}/{report.get('total', 0)} scanned; {report.get('mapped', 0)}/{report.get('planets', 0)} planets mapped",
            f"Surface: {report.get('landable', 0)} landable; {report.get('bio', 0)} biological signals; {report.get('valuable', 0)} notable worlds",
            f"Traffic: {traffic.get('day', 0)}/{traffic.get('week', 0)}/{traffic.get('total', 0)} (day/week/all-time)", "",
            "This is a journal-derived survey dossier, not a guarantee of colonisation eligibility.",
        ]
        if report.get("gaps"):
            lines.extend(["", "## Remaining survey work"] + [f"- {gap}" for gap in report["gaps"]])
        if report.get("wonders"):
            lines.extend(["", "## Notable findings"] + [f"- {row['body']}: {row['kind']} — {row['detail']}" for row in report["wonders"]])
        return "\n".join(lines)
