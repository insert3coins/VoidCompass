"""State and command boundary for the HTML Void Compass dashboard.

This mixin deliberately contains no browser or Tk rendering.  It serializes
the existing journal-owned state and validates the small command vocabulary
that the local dashboard is allowed to invoke.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import threading
import time
import webbrowser

import companion_features
import engineering_data
from explorer_decision_deck import (
    DOCTRINES,
    explorer_decision,
    personal_codex_hunt,
    route_horizon,
)
import themes
from config import get_active_profile, get_profile_dir
from deep_survey import recon_report
from diagnostic_logs import application_base_dir
from global_hotkeys import (
    DEFAULT_OVERLAY_HOTKEYS,
    OVERLAY_HOTKEY_SPECS,
    validate_hotkey_bindings,
)
from overlay_layout_model import (
    DEFAULT_POSITIONS,
    DEFAULT_SIZES,
    OVERLAY_CARD_LABELS,
    OVERLAY_ENABLE_KEYS,
    OVERLAY_LABELS,
)
from platform_support import open_path
from profile_backups import schedule_restore, snapshot_profile, validate_backup
from mining_data import (
    MINING_MATERIALS,
    MiningDataStore,
    normalize_material_name,
    search_spansh_buyers,
    search_spansh_rings,
)
from services.spansh import (
    SpanshError,
    fleet_carrier_job_id,
    fleet_carrier_route,
    import_fleet_carrier_route,
    neutron_route,
)
from stellar_cartography import (
    build_orrery,
    build_planetary_resources,
    build_region_passport,
    build_replay,
    build_science_lab,
    build_survey_queue,
    replay_export_html,
)
from ui_theme import apply_ui_scale


PROJECT_URL = "https://github.com/insert3coins/VoidCompass"
RELEASES_URL = f"{PROJECT_URL}/releases"
ISSUES_URL = f"{PROJECT_URL}/issues/new/choose"


_CORE_RANKS = {
    "Combat": ("Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Trade": ("Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant", "Broker", "Entrepreneur", "Tycoon", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Explore": ("Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer", "Pathfinder", "Ranger", "Pioneer", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "CQC": ("Helpless", "Mostly Helpless", "Amateur", "Semi Professional", "Professional", "Champion", "Hero", "Legend", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Soldier": ("Defenceless", "Mostly Defenceless", "Rookie", "Soldier", "Gunslinger", "Warrior", "Gladiator", "Deadeye", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Exobiologist": ("Directionless", "Mostly Directionless", "Compiler", "Collector", "Cataloguer", "Taxonomist", "Ecologist", "Geneticist", "Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V"),
    "Empire": ("None", "Outsider", "Serf", "Master", "Squire", "Knight", "Lord", "Baron", "Viscount", "Count", "Earl", "Marquis", "Duke", "Prince", "King"),
    "Federation": ("None", "Recruit", "Cadet", "Midshipman", "Petty Officer", "Chief Petty Officer", "Warrant Officer", "Ensign", "Lieutenant", "Lt Commander", "Post Commander", "Post Captain", "Rear Admiral", "Vice Admiral", "Admiral"),
}

_HTML_WORKSPACE_PAGES = {
    "explore", "profile", "analytics", "chronicle", "mission", "ground", "mining",
    "engineering", "carrier", "recon", "achievements", "ledger", "settings",
}


def _integer(value, default=0):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return default


def _number(value, default=None):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _text(value, limit=180):
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _local_departure_timestamp(value):
    """Parse the Carrier panel's optional local departure time."""
    text = str(value or "").strip()
    if not text:
        return None
    now = datetime.now()
    parsed = None
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            pass
    if parsed is None:
        match = re.fullmatch(
            r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", text,
        )
        if match:
            day, month, hour, minute, second = match.groups()
            try:
                parsed = datetime(
                    now.year, int(month), int(day), int(hour), int(minute),
                    int(second or 0),
                )
            except ValueError:
                parsed = None
    if parsed is None:
        match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
        if match:
            hour, minute, second = match.groups()
            try:
                parsed = datetime(
                    now.year, now.month, now.day, int(hour), int(minute),
                    int(second or 0),
                )
            except ValueError:
                parsed = None
    if parsed is None:
        raise ValueError(
            "Use HH:MM, DD/MM HH:MM, DD/MM/YYYY HH:MM or YYYY-MM-DD HH:MM."
        )
    return int(time.mktime(parsed.timetuple()))


class HtmlDashboardMixin:
    """Publish exploration state and accept private dashboard commands."""

    def start_html_dashboard_bridge(self):
        runtime = getattr(self.root, "_voidcompass_html_dashboard_runtime", None)
        if runtime is None:
            return False
        runtime.attach_app(self)
        self._html_dashboard_publish_job = None
        self._html_dashboard_last_payload = None
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _schedule_html_dashboard_publish(self, immediate=False):
        if not getattr(self, "is_running", False):
            return
        if getattr(self, "_html_dashboard_publish_job", None) is not None:
            return
        try:
            self._html_dashboard_publish_job = self.root.after(
                0 if immediate else 350,
                self._publish_html_dashboard,
            )
        except Exception:
            self._html_dashboard_publish_job = None

    def _publish_html_dashboard(self):
        self._html_dashboard_publish_job = None
        if not getattr(self, "is_running", False):
            return
        runtime = getattr(self.root, "_voidcompass_html_dashboard_runtime", None)
        if runtime is not None:
            try:
                runtime.publish_app(self.html_dashboard_snapshot())
            except Exception as exc:
                logging.debug("HTML dashboard publication skipped: %s", exc)
        self._schedule_html_dashboard_publish()

    def _html_dashboard_theme(self):
        name, palette = themes.resolve_theme(
            self.config.get("ui_theme_name"),
            self.config.get("ui_custom_themes") or {},
        )
        available = list(themes.BUILTIN_THEMES)
        for custom_name in (self.config.get("ui_custom_themes") or {}):
            if custom_name not in available:
                available.append(custom_name)
        return {"name": name, "palette": palette, "available": available}

    def _html_dashboard_sources(self):
        now = time.time()
        definitions = {
            "journal": (getattr(self, "last_journal_event_ts", 0), 30, 180),
            "status": (getattr(self, "last_status_event_ts", 0), 15, 60),
            "navigation": (getattr(self, "last_nav_event_ts", 0), 120, 600),
            "cargo": (getattr(self, "last_cargo_event_ts", 0), 180, 900),
        }
        sources = {}
        for name, (observed, live_age, recent_age) in definitions.items():
            age = now - float(observed or 0) if observed else None
            if age is None:
                state = "cached"
            elif age <= live_age:
                state = "live"
            elif age <= recent_age:
                state = "recent"
            else:
                state = "stale"
            sources[name] = state
        if sources["journal"] == "live" or sources["status"] == "live":
            sources["overall"] = "LIVE"
            sources["detail"] = "JOURNAL / STATUS LINKED"
        elif "recent" in sources.values():
            sources["overall"] = "RECENT"
            sources["detail"] = "GAME LINK QUIET"
        else:
            sources["overall"] = "CACHED"
            sources["detail"] = "WAITING FOR GAME"
        stall_age = (
            now - float(getattr(self, "_last_ui_stall_ts", 0.0) or 0.0)
            if getattr(self, "_last_ui_stall_ts", 0.0) else None
        )
        sources["ui"] = "warn" if stall_age is not None and stall_age < 30 else "live"
        heartbeat = getattr(getattr(self, "heartbeat_hud", None), "_html_render_model", None)
        sources["heartbeat"] = dict(heartbeat or {})
        return sources

    def _html_exploration_preflight(self, route, flight, sources):
        """Return compact departure readiness without repeating survey data."""
        checks = []

        def add(check_id, label, status, value, detail):
            checks.append({
                "id": check_id, "label": label, "status": status,
                "value": value, "detail": detail,
            })

        journal_path = str(self.config.get("journal_path") or "").strip()
        if journal_path and os.path.isdir(journal_path):
            link = str((sources or {}).get("overall") or "CACHED").upper()
            add("journal", "Journal link", "ready", link,
                "Elite journal folder linked" if link == "LIVE" else "Folder ready; waiting for live events")
        else:
            add("journal", "Journal link", "fail", "NOT LINKED", "Choose the Elite Dangerous journal folder")

        edsm_enabled = bool(self.config.get("edsm_upload_enabled"))
        edsm_configured = bool(
            str(self.config.get("edsm_cmdr_name") or "").strip()
            and str(self.config.get("edsm_api_key") or "").strip()
        )
        if edsm_enabled and edsm_configured:
            add("edsm", "EDSM relay", "ready", "ARMED", "Exploration events can upload")
        elif edsm_enabled:
            add("edsm", "EDSM relay", "fail", "INCOMPLETE", "Commander name or API key is missing")
        else:
            add("edsm", "EDSM relay", "optional", "OPTIONAL", "Uploads are disabled for this profile")

        runtime = getattr(self.root, "_voidcompass_html_overlay_runtime", None)
        master_enabled = bool(self.config.get("overlay_enabled", True))
        health = runtime.health_snapshot() if runtime is not None else {}
        if not master_enabled:
            add("overlays", "Cockpit overlays", "optional", "OFF", "Overlay master switch is disabled")
        elif health.get("recovering"):
            add("overlays", "Cockpit overlays", "warn", "RECOVERING", "HTML renderer watchdog is restoring surfaces")
        elif health.get("total") and health.get("ready") == health.get("total"):
            add("overlays", "Cockpit overlays", "ready", f"{health.get('total')} READY", "HTML surfaces are responding")
        elif health.get("total"):
            add("overlays", "Cockpit overlays", "warn", f"{health.get('ready', 0)}/{health.get('total')} LIVE", "HTML surface recovery pending")
        else:
            add("overlays", "Cockpit overlays", "warn", "STARTING", "Enabled overlays have not registered yet")

        commander = str(
            self.config.get("active_commander_name") or getattr(self, "cmdr_name", "") or ""
        ).strip()
        profile_key = str(self.config.get("active_commander_profile") or "").strip()
        profile_ready = bool(profile_key and commander and "unknown" not in commander.casefold())
        add("profile", "Commander profile", "ready" if profile_ready else "warn",
            commander.upper() if profile_ready else "UNRESOLVED",
            "Profile-local state active" if profile_ready else "Waiting for LoadGame commander identity")

        game_mode = str(getattr(self, "current_game_mode", None) or "").strip()
        if game_mode:
            main_mode = game_mode.casefold() == "maingame"
            add("game_mode", "Elite session", "ready" if main_mode else "warn",
                "MAIN GAME" if main_mode else game_mode.upper(),
                "Flight journals active" if main_mode else "Operations session context retained")

        hull = _number(getattr(self, "current_hull_percent", None))
        repair = (getattr(self, "maintenance_state", None) or {}).get("last_repair_drone") or {}
        if hull is not None:
            add("maintenance", "Hull condition",
                "fail" if hull < 30 else "warn" if hull < 70 else "ready",
                f"{hull:.0f}%", "Repair drone activity retained" if repair else "Live status telemetry")

        next_system = str((route or {}).get("next") or "").strip()
        if next_system:
            add("route", "Departure route", "ready", "PLOTTED", next_system)
        else:
            add("route", "Departure route", "optional", "STANDBY", "No next system is currently plotted")

        fuel = (flight or {}).get("fuel_percent")
        if fuel is None:
            add("fuel", "Fuel reserve", "warn", "UNKNOWN", "Loadout or status fuel telemetry is not available")
        elif fuel < 15:
            add("fuel", "Fuel reserve", "fail", f"{fuel:.0f}%", "Refuel before departure")
        elif fuel < 30:
            add("fuel", "Fuel reserve", "warn", f"{fuel:.0f}%", "Low reserve for an unplanned diversion")
        else:
            add("fuel", "Fuel reserve", "ready", f"{fuel:.0f}%", "Departure reserve is available")

        now = time.monotonic()
        disk_cache = getattr(self, "_html_preflight_disk_cache", None)
        if not isinstance(disk_cache, dict) or now - disk_cache.get("time", 0.0) > 30.0:
            paths = [get_profile_dir(get_active_profile(self.config))]
            screenshot_path = str(self.config.get("screenshots_path") or "").strip()
            if screenshot_path:
                paths.append(screenshot_path if os.path.exists(screenshot_path) else os.path.dirname(screenshot_path))
            free_values = []
            for path in paths:
                try:
                    free_values.append(shutil.disk_usage(path or application_base_dir()).free)
                except OSError:
                    continue
            disk_cache = {"time": now, "free": min(free_values) if free_values else None}
            self._html_preflight_disk_cache = disk_cache
        free = disk_cache.get("free")
        if free is None:
            add("storage", "Storage", "warn", "UNKNOWN", "Profile or screenshot storage could not be checked")
        else:
            free_gb = free / (1024 ** 3)
            status = "fail" if free_gb < 0.5 else "warn" if free_gb < 2.0 else "ready"
            add("storage", "Storage", status, f"{free_gb:.1f} GB FREE", "Profile and screenshot storage")

        blocking = sum(row["status"] == "fail" for row in checks)
        warnings = sum(row["status"] == "warn" for row in checks)
        return {
            "status": "BLOCKED" if blocking else "CHECK" if warnings else "READY",
            "summary": (
                f"{blocking} blocking · {warnings} caution"
                if blocking or warnings else "Departure systems nominal"
            ),
            "checks": checks,
        }

    def _html_dashboard_route(self):
        progress = dict(self._current_route_progress())
        destination = self._dashboard_next_destination()
        route = list(getattr(self, "route_list", None) or [])
        manager = getattr(self, "waypoint_manager", None)
        waypoints = list(getattr(manager, "waypoints", None) or [])
        current = str(getattr(self, "current_sys", "") or "")
        final = None
        source = "NAVIGATION"
        percent = 0.0
        if route:
            source = "ELITE NAV ROUTE"
            final = route[-1]
            try:
                index = route.index(current)
            except (ValueError, TypeError):
                index = -1
            if len(route) <= 1 and progress.get("remaining") == 0:
                percent = 100.0
            elif index >= 0 and len(route) > 1:
                percent = index * 100.0 / (len(route) - 1)
        elif waypoints:
            source = "MISSION WAYPOINTS"
            final = waypoints[-1].get("name")
            total = len(waypoints)
            visited = sum(bool(row.get("visited")) for row in waypoints)
            percent = visited * 100.0 / total if total else 0.0
        elif getattr(self, "dest_name", None):
            source = "NAV TARGET"
            final = self.dest_name

        target_coords = None
        for entry in getattr(self, "nav_route_entries", None) or ():
            if not isinstance(entry, dict):
                continue
            if str(entry.get("StarSystem") or "").casefold() == str(destination or "").casefold():
                target_coords = entry.get("StarPos")
                break
        if target_coords is None:
            for waypoint in waypoints:
                if str(waypoint.get("name") or "").casefold() == str(destination or "").casefold():
                    target_coords = waypoint.get("coords")
                    break
        distance_text = ""
        if target_coords and getattr(self, "current_coords", None) and manager:
            try:
                distance_text = f"{manager.get_distance(self.current_coords, target_coords):,.1f} LY"
            except (TypeError, ValueError):
                pass
        horizon = route_horizon(
            getattr(self, "nav_route_entries", None) or (),
            current_system=current,
            current_position=getattr(self, "current_coords", None),
        )
        return {
            **progress,
            "source": source,
            "next": destination,
            "final": final,
            "percent": round(max(0.0, min(100.0, percent)), 1),
            "distance_text": distance_text,
            "horizon": horizon,
        }

    @staticmethod
    def _html_dashboard_body_detail(item):
        details = []
        if item.get("_orrery_source") == "edsm":
            details.append("KNOWN-SYSTEM ARCHIVE")
        body_class = item.get("planet_class") or item.get("class") or item.get("star_type")
        if body_class:
            details.append(str(body_class))
        bio = _integer(item.get("bio_count"))
        geo = _integer(item.get("geo_count"))
        if bio:
            details.append(f"BIO {bio}")
        if geo:
            details.append(f"GEO {geo}")
        if item.get("terraformable"):
            details.append("TERRAFORMABLE")
        if item.get("dss_complete"):
            details.append("DSS COMPLETE")
        return " · ".join(details) or "BODY SCAN"

    @staticmethod
    def _html_dashboard_body_badge(item):
        if item.get("_orrery_source") == "edsm":
            return "KNOWN"
        bio = _integer(item.get("bio_count"))
        geo = _integer(item.get("geo_count"))
        body_class = str(item.get("planet_class") or item.get("class") or "")
        if bio and geo:
            return "BIO / GEO"
        if bio:
            return "BIO"
        if geo:
            return "GEO"
        if item.get("terraformable") or body_class in {
            "Earthlike body", "Water world", "Ammonia world",
        }:
            return "VALUABLE"
        if item.get("dss_complete"):
            return "MAPPED"
        return "SCANNED"

    def _html_dashboard_survey(self, intelligence):
        scanned = max(0, _integer(getattr(self, "scanned", 0)))
        total = max(0, _integer(getattr(self, "total", 0)))
        total_known = bool(getattr(self, "scan_total_confirmed", False) and total > 0)
        percent = min(100.0, scanned * 100.0 / total) if total_known else 0.0
        complete = bool(total_known and scanned >= total)
        completion = (intelligence or {}).get("completion") or {}
        bodies = []
        notables = []
        high_classes = {"Earthlike body", "Water world", "Ammonia world"}
        journal_rows = [
            row for row in (getattr(self, "scan_items", None) or [])
            if isinstance(row, dict)
        ]
        local_ids = {
            str(row.get("body_id")) for row in journal_rows
            if row.get("body_id") is not None
        }
        current_key = str(getattr(self, "current_sys", "") or "").casefold()
        archived_rows = [
            row for row in (
                getattr(self, "_edsm_orrery_bodies", {}).get(current_key, [])
                if current_key else []
            )
            if isinstance(row, dict)
            and row.get("body_id") is not None
            and str(row.get("body_id")) not in local_ids
        ]
        # The local journal remains authoritative. Public known-system bodies
        # only fill historical detail that this profile did not retain (for
        # example a visit made before Void Compass began caching Scan events).
        rows = [*journal_rows, *archived_rows]
        rows.sort(key=lambda row: (_integer(row.get("body_id"), 9999), _text(row.get("name"))))
        for row in rows:
            if row.get("is_star"):
                continue
            body_class = str(row.get("planet_class") or row.get("class") or "")
            priority = bool(
                _integer(row.get("bio_count"))
                or _integer(row.get("geo_count"))
                or row.get("terraformable")
                or body_class in high_classes
            )
            body_payload = {
                "name": _text(row.get("name") or f"Body {row.get('body_id', '?')}", 140),
                "body_id": _integer(row.get("body_id"), 0),
                "type": _text(body_class, 100),
                "detail": self._html_dashboard_body_detail(row),
                "badge": self._html_dashboard_body_badge(row),
                "priority": priority,
                "bio_count": max(0, _integer(row.get("bio_count"))),
                "geo_count": max(0, _integer(row.get("geo_count"))),
                "mapped": bool(row.get("dss_complete")),
                "terraformable": bool(row.get("terraformable")),
                "landable": (
                    bool(row.get("landable"))
                    if "landable" in row and row.get("landable") is not None
                    else None
                ),
                "archived": row.get("_orrery_source") == "edsm",
            }
            bodies.append(body_payload)
            if priority:
                notables.append(
                    f"{body_payload['name']} · {body_payload['badge']}"
                )
        if not notables:
            notables = [_text(row, 180) for row in (getattr(self, "valuable_bodies", None) or [])]
        star_class = _text(getattr(self, "star_class", ""), 50)
        if not star_class:
            star_class = next((
                _text(row.get("star_type"), 50) for row in rows
                if row.get("is_star") and row.get("star_type")
            ), "")
        known_valuable = sum(
            bool(
                row.get("terraformable")
                or str(row.get("planet_class") or row.get("class") or "") in high_classes
            )
            for row in rows if not row.get("is_star")
        )
        return {
            "scanned": scanned,
            "total": total,
            "total_known": total_known,
            "percent": round(percent, 1),
            "complete": complete,
            "undiscovered": bool(getattr(self, "system_undiscovered", False)),
            "star_class": star_class,
            "bio_signals": max(0, _integer(getattr(self, "system_bio_signals", 0))),
            "bio_complete": max(0, _integer(getattr(self, "organic_count", 0))),
            "geo_signals": sum(_integer(row.get("geo_count")) for row in rows),
            "valuable_count": max(
                len(getattr(self, "valuable_bodies", None) or []),
                known_valuable,
            ),
            "notables": notables[:8],
            "bodies": bodies[:28],
            "journal_bodies": len(journal_rows),
            "archive_bodies": len(archived_rows),
            "archive_loading": bool(
                current_key
                and current_key in getattr(self, "_edsm_orrery_pending", set())
            ),
            "summary": _text(completion.get("summary"), 180),
            "completion": {
                "unknown_bodies": max(0, _integer(completion.get("unknown_bodies"))),
                "dss_complete": max(0, _integer(completion.get("dss_complete"))),
                "dss_targets": max(0, _integer(completion.get("dss_targets"))),
                "bio_complete": max(0, _integer(completion.get("bio_complete"))),
                "bio_total": max(0, _integer(completion.get("bio_total"))),
                "geo_detected": max(0, _integer(completion.get("geo_detected"))),
            },
        }

    def _html_dashboard_intelligence(self, intelligence):
        intelligence = intelligence or {}
        completion = intelligence.get("completion") or {}
        regions = intelligence.get("regions") or {}
        region = regions.get("current") or {}
        return {
            "region": _text(region.get("name") or "Unknown", 90),
            "region_id": region.get("id"),
            "regions_visited": _integer(regions.get("visited")),
            "first_discoveries": _integer(completion.get("first_discoveries")),
            "first_footfalls": _integer(completion.get("first_footfalls")),
        }

    def _html_dashboard_priorities(self, intelligence, route, survey):
        output = []
        for row in (intelligence or {}).get("actions") or ():
            if not isinstance(row, dict):
                continue
            title = row.get("title") or row.get("label") or row.get("action")
            detail = row.get("detail") or row.get("reason") or row.get("summary")
            if title:
                output.append({
                    "title": _text(title, 120),
                    "detail": _text(detail or "Journal-backed exploration objective.", 220),
                    "severity": _text(row.get("severity") or "INFO", 12).upper(),
                })
        if not output and survey.get("bio_signals"):
            output.append({
                "title": "Resolve biological signals",
                "detail": f"{survey['bio_complete']} of {survey['bio_signals']} biological analyses complete in this system.",
                "severity": "INFO",
            })
        if not output and route.get("next"):
            output.append({
                "title": f"Continue to {route['next']}",
                "detail": route.get("text") or "The plotted route is ready.",
                "severity": "INFO",
            })
        return output[:4]

    def _html_dashboard_events(self):
        output = []
        for row in list(getattr(self, "event_feed_entries", None) or [])[:100]:
            if not isinstance(row, dict):
                continue
            timestamp = _number(row.get("ts"), 0) or 0
            try:
                time_text = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
            except (OSError, OverflowError, ValueError):
                time_text = "--:--:--"
            output.append({
                "ts": timestamp,
                "time": time_text,
                "tag": _text(row.get("tag") or "INFO", 18).upper(),
                "severity": _text(row.get("severity") or "INFO", 12).upper(),
                "message": _text(row.get("message"), 420),
            })
        return output

    def _html_dashboard_expedition(self):
        manager = getattr(self, "expedition_manager", None)
        if manager is None:
            return {"active": False}
        try:
            snapshot = manager.status_snapshot(
                next_waypoint=self._dashboard_next_destination(),
            )
        except Exception:
            return {"active": False}
        if not snapshot.get("active"):
            return {"active": False}
        complete = _integer(snapshot.get("objectives_complete"))
        total = _integer(snapshot.get("objectives_total"))
        next_step = snapshot.get("next_objective") or snapshot.get("next_waypoint")
        return {
            "active": True,
            "name": _text(snapshot.get("name") or "Named expedition", 140),
            "status": _text(snapshot.get("status") or "active", 30),
            "complete": complete,
            "total": total,
            "detail": _text(
                f"{complete}/{total} objectives · {_integer(snapshot.get('systems')):,} systems · "
                f"{_integer(snapshot.get('jumps')):,} jumps"
                + (f" · next {next_step}" if next_step else ""),
                240,
            ),
        }

    def _html_dashboard_session_pulse(self):
        """Return the current Captain's Log session without replay history."""
        fallback = {
            "elapsed": self._get_session_elapsed_text(),
            "jumps": _integer(getattr(self, "session_jump_count", 0)),
            "distance_ly": round(_number(getattr(self, "session_ly", 0), 0) or 0, 1),
            "systems": len(getattr(self, "session_systems", None) or set()),
            "codex": 0, "bio_analyses": 0, "fss_surveys": 0,
            "dss_maps": 0, "valuable_worlds": 0, "first_discoveries": 0,
            "highlights": [],
        }
        log = getattr(self, "captains_log", None)
        if log is None:
            return fallback
        try:
            sessions = log.sessions()
        except Exception:
            return fallback
        active = next((row for row in sessions if isinstance(row, dict) and not row.get("ended")), None)
        if active is None:
            return fallback
        result = dict(fallback)
        for key in (
            "jumps", "codex", "bio_analyses", "fss_surveys", "dss_maps",
            "valuable_worlds", "first_discoveries", "screenshots",
        ):
            result[key] = max(0, _integer(active.get(key)))
        result["distance_ly"] = round(max(0.0, _number(active.get("distance_ly"), 0) or 0), 1)
        result["start_system"] = _text(active.get("start_system"), 140)
        result["end_system"] = _text(active.get("end_system"), 140)
        result["highlights"] = [
            {
                "kind": _text(row.get("kind"), 30),
                "title": _text(row.get("title"), 140),
                "detail": _text(row.get("detail"), 220),
            }
            for row in reversed(active.get("highlights") or [])
            if isinstance(row, dict)
        ][:4]
        result["summary"] = _text(
            f"{result['jumps']} jumps · {result['distance_ly']:,.1f} ly · "
            f"{result['fss_surveys']} FSS · {result['dss_maps']} DSS · "
            f"{result['bio_analyses']} biology",
            220,
        )
        return result

    def _html_dashboard_codex_hunt(self, region_name):
        """Build a cached, profile-aware personal regional Codex comparison."""
        profile = get_active_profile(self.config)
        region_name = _text(region_name or "Unknown region", 90)
        now = time.monotonic()
        cached = getattr(self, "_html_codex_hunt_cache", None)
        if (
            isinstance(cached, dict)
            and cached.get("profile") == profile
            and cached.get("region") == region_name
            and now < float(cached.get("expires") or 0)
        ):
            return cached.get("value") or {}
        tracker = getattr(self, "deep_survey", None)
        try:
            rows = tracker.codex_state() if tracker and hasattr(tracker, "codex_state") else []
        except Exception:
            rows = []
        manager = getattr(self, "expedition_manager", None)
        try:
            active = manager.active() if manager else None
        except Exception:
            active = None
        value = personal_codex_hunt(rows, region_name, active_expedition=active)
        self._html_codex_hunt_cache = {
            "profile": profile, "region": region_name,
            "expires": now + 5.0, "value": value,
        }
        return value

    def _html_profile_transient(self, attribute, defaults):
        """Return profile-scoped, non-persistent HTML worker state."""
        profile = get_active_profile(self.config)
        state = getattr(self, attribute, None)
        if not isinstance(state, dict) or state.get("profile") != profile:
            state = {"profile": profile, **defaults}
            setattr(self, attribute, state)
        return state

    def _html_local_body_target(self):
        """Return Elite's selected body only when it resolves in this system."""
        details = getattr(self, "current_destination_details", None) or {}
        if not isinstance(details, dict) or not details:
            return None
        current_address = getattr(self, "current_system_address", None)
        target_address = details.get("System")
        if current_address is not None and target_address is not None:
            try:
                same_system = int(current_address) == int(target_address)
            except (TypeError, ValueError):
                same_system = str(current_address).strip() == str(target_address).strip()
            if not same_system:
                return None
        formatter = getattr(self, "_navigation_destination_label", None)
        name = formatter(details.get("Name")) if callable(formatter) else details.get("Name")
        name = _text(name, 180)
        if not name:
            return None
        body_id = details.get("Body")
        matched = None
        for row in (getattr(self, "scan_items", None) or []):
            if not isinstance(row, dict):
                continue
            names = {
                _text(row.get("name"), 180).casefold(),
                _text(row.get("full_name"), 180).casefold(),
            }
            if name.casefold() not in names:
                continue
            row_body_id = row.get("body_id")
            if body_id is not None and row_body_id is not None:
                try:
                    if int(body_id) != int(row_body_id):
                        continue
                except (TypeError, ValueError):
                    if str(body_id).strip() != str(row_body_id).strip():
                        continue
            matched = row
            break
        if matched is None:
            return None
        current_body_id = getattr(self, "current_body_id", None)
        is_current_body = False
        if current_body_id is not None and body_id is not None:
            try:
                is_current_body = int(current_body_id) == int(body_id)
            except (TypeError, ValueError):
                is_current_body = str(current_body_id).strip() == str(body_id).strip()
        if not is_current_body:
            current_body = _text(getattr(self, "current_body_name", None), 180).casefold()
            is_current_body = bool(current_body and current_body in {
                name.casefold(),
                _text(matched.get("name"), 180).casefold(),
                _text(matched.get("full_name"), 180).casefold(),
            })
        return {
            "name": name,
            "system": target_address,
            "body": body_id,
            "is_current_body": is_current_body,
            "source": "ELITE STATUS",
        }

    def _html_explore_workspace(self):
        manager = getattr(self, "waypoint_manager", None)
        waypoints = list(getattr(manager, "waypoints", None) or [])
        current = _text(getattr(self, "current_sys", None), 140)
        current_coords = getattr(self, "current_coords", None)

        rendered_waypoints = []
        previous_coords = current_coords
        for index, row in enumerate(waypoints[:500]):
            if not isinstance(row, dict):
                continue
            coords = row.get("coords")
            leg_distance = None
            if manager is not None and previous_coords and coords:
                try:
                    leg_distance = manager.get_distance(previous_coords, coords)
                except (KeyError, TypeError, ValueError):
                    leg_distance = None
            rendered_waypoints.append({
                "index": index,
                "name": _text(row.get("name"), 140),
                "visited": bool(row.get("visited")),
                "note": _text(row.get("note") or row.get("notes"), 500),
                "coords_known": bool(coords),
                "distance": _number(leg_distance),
            })
            if coords:
                previous_coords = coords

        nav_entries = []
        raw_route = [
            row for row in (getattr(self, "nav_route_entries", None) or [])
            if isinstance(row, dict)
        ]
        current_index = next((
            index for index, row in enumerate(raw_route)
            if str(row.get("StarSystem") or "").casefold() == current.casefold()
        ), -1)
        previous = current_coords
        for index, row in enumerate(raw_route[:500]):
            coords = row.get("StarPos")
            distance = None
            if manager is not None and previous and coords:
                try:
                    distance = manager.get_distance(previous, coords)
                except (KeyError, TypeError, ValueError):
                    distance = None
            nav_entries.append({
                "index": index,
                "system": _text(row.get("StarSystem"), 140),
                "star_class": _text(row.get("StarClass"), 30),
                "distance": _number(distance),
                "current": index == current_index,
                "passed": current_index >= 0 and index < current_index,
            })
            if coords:
                previous = coords

        tool = self._html_profile_transient(
            "_html_explore_tool_state",
            {"status": "ready", "detail": "Ready to plot a manual neutron route.", "route": None},
        )
        saved_form = self.config.get("system_plotter_form") or {}
        survey_states = self.config.get("stellar_survey_queue_state") or {}
        survey_state = survey_states.get(current.casefold()) or {}
        scan_items = [
            row for row in (getattr(self, "scan_items", None) or [])
            if isinstance(row, dict)
        ]
        body_target = self._html_local_body_target()
        local_ids = {
            str(row.get("body_id")) for row in scan_items
            if row.get("body_id") is not None
        }
        cached_edsm = (
            getattr(self, "_edsm_orrery_bodies", {})
            .get(current.casefold(), [])
        )
        external_items = [
            row for row in cached_edsm
            if isinstance(row, dict)
            and row.get("body_id") is not None
            and str(row.get("body_id")) not in local_ids
        ]
        orrery_items = [*scan_items, *external_items]
        orrery = build_orrery(
            orrery_items, body_target,
            getattr(self, "system_barycentres", None) or [],
        )
        orrery["loading"] = bool(
            not orrery_items
            and current.casefold() in getattr(self, "_edsm_orrery_pending", set())
        )
        if external_items:
            orrery["mode"] = (
                "EDSM KNOWN-SYSTEM ARCHITECTURE"
                if not scan_items else "JOURNAL + EDSM ARCHITECTURE"
            )
            orrery["external_bodies"] = len(external_items)
        return {
            "current": current,
            "destination": _text(getattr(self, "dest_name", None), 140),
            "nav_route": nav_entries,
            "waypoints": rendered_waypoints,
            "next_waypoint": _text(
                manager.get_next_waypoint(current) if manager is not None else "", 140,
            ),
            "auto_copy": bool(self.config.get("auto_copy_waypoint", False)),
            "cartography": {
                "system": current,
                "target": body_target,
                "orrery": orrery,
                "queue": build_survey_queue(scan_items, survey_state, body_target),
                "resources": build_planetary_resources(scan_items),
            },
            "plotter": {
                "from": _text(saved_form.get("from") or current, 140),
                "to": _text(saved_form.get("to"), 140),
                "range": _number(saved_form.get("range"), 30),
                "efficiency": _integer(saved_form.get("efficiency"), 60),
                "multiplier": _integer(saved_form.get("supercharge_multiplier"), 4),
                "status": _text(tool.get("status"), 30),
                "detail": _text(tool.get("detail"), 300),
                "result": tool.get("route"),
            },
        }

    @staticmethod
    def _html_rank_label(category, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return "—"
        labels = _CORE_RANKS.get(str(category))
        if not labels or value < 0:
            return str(value)
        return labels[value] if value < len(labels) else f"{labels[-1]} ({value})"

    @staticmethod
    def _html_stat_value(statistics, *names):
        wanted = {str(name).casefold() for name in names}
        pending = [statistics]
        while pending:
            current = pending.pop()
            if not isinstance(current, dict):
                continue
            for key, value in current.items():
                if str(key).casefold() in wanted and not isinstance(value, (dict, list)):
                    return value
                if isinstance(value, dict):
                    pending.append(value)
        return None

    @staticmethod
    def _html_expiry(value):
        if not value:
            return ""
        try:
            expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            remaining = int((expiry - datetime.now(timezone.utc)).total_seconds())
            if remaining <= 0:
                return "EXPIRED"
            hours, remainder = divmod(remaining, 3600)
            return f"{hours}h {remainder // 60}m left"
        except (TypeError, ValueError):
            return _text(value, 60)

    def _html_profile_workspace(self):
        companion = getattr(self, "companion_state", None) or {}
        ship = dict(getattr(self, "cmdr_ship", None) or {})
        ranks = dict(getattr(self, "cmdr_ranks", None) or {})
        progress = dict(getattr(self, "cmdr_rank_progress", None) or {})
        reputation = dict(getattr(self, "cmdr_reputation", None) or {})
        rank_rows = []
        for category in (
            "Combat", "Trade", "Explore", "Exobiologist", "Soldier",
            "Federation", "Empire", "CQC",
        ):
            if category not in ranks and category not in progress:
                continue
            rank_rows.append({
                "category": category,
                "rank": self._html_rank_label(category, ranks.get(category)),
                "progress": _number(progress.get(category)),
            })
        reputation_rows = [
            {"name": name, "value": _number(reputation.get(name))}
            for name in ("Federation", "Empire", "Alliance", "Independent")
            if name in reputation
        ]
        statistics = companion.get("statistics") or {}
        career = [
            {"label": "Systems visited", "value": self._html_stat_value(statistics, "Systems_Visited")},
            {"label": "Hyperspace jumps", "value": self._html_stat_value(statistics, "Total_Hyperspace_Jumps")},
            {"label": "Distance travelled", "value": self._html_stat_value(statistics, "Total_Hyperspace_Distance"), "suffix": " LY"},
            {"label": "Exploration profit", "value": self._html_stat_value(statistics, "Exploration_Profits"), "credits": True},
            {"label": "Organic data", "value": self._html_stat_value(statistics, "Organic_Data_Profits"), "credits": True},
            {"label": "Species encountered", "value": self._html_stat_value(statistics, "Organic_Species_Encountered")},
            {"label": "First footfalls", "value": self._html_stat_value(statistics, "First_Footfalls")},
            {"label": "Mining profit", "value": self._html_stat_value(statistics, "Mining_Profits"), "credits": True},
        ]
        achievement_snapshot = {}
        engine = getattr(self, "achievement_engine", None)
        if engine is not None:
            try:
                achievement_snapshot = engine.snapshot()
            except Exception:
                achievement_snapshot = {}
        sessions = []
        logbook = getattr(self, "captains_log", None)
        if logbook is not None:
            try:
                sessions = logbook.sessions()
            except Exception:
                sessions = []
        stored = companion.get("stored_ships") or {}
        stored_rows = list(stored.get("here") or []) + list(stored.get("remote") or [])
        carrier = dict(getattr(getattr(self, "carrier_tracker", None), "carrier_data", {}) or {})
        missions = list((companion.get("missions") or {}).values())
        profile_key = get_active_profile(self.config)
        session_distance = sum(float(row.get("distance_ly") or 0) for row in sessions)
        try:
            vehicles = self.specialist_engine.vehicle_snapshot()
        except Exception:
            vehicles = {}
        maintenance = dict(getattr(self, "maintenance_state", None) or {})
        return {
            "name": _text(getattr(self, "cmdr_name", None) or self.config.get("active_commander_name") or "Unknown Commander", 120),
            "fid": _text(getattr(self, "cmdr_fid", None) or self.config.get("active_commander_fid"), 120),
            "key": _text(profile_key, 120),
            "folder": _text(get_profile_dir(profile_key), 500),
            "balance": _number(getattr(self, "cmdr_balance", None)),
            "loan": _number(getattr(self, "cmdr_loan", None)),
            "session_credit_delta": (
                _number(getattr(self, "cmdr_balance", None)) - _number(getattr(self, "session_start_balance", None))
                if _number(getattr(self, "cmdr_balance", None)) is not None
                and _number(getattr(self, "session_start_balance", None)) is not None else None
            ),
            "ship": {
                "name": _text(ship.get("ship_name") or ship.get("user_ship_name") or ship.get("ship"), 120),
                "type": _text(ship.get("ship_localised") or ship.get("ship"), 120),
                "ident": _text(ship.get("ship_ident"), 60),
                "id": ship.get("ship_id"),
                "cargo": ship.get("cargo_capacity"),
                "jump_range": _number(ship.get("max_jump_range")),
                "rebuy": _number(ship.get("rebuy")),
                "hull": _number(ship.get("hull_health")),
                "mode": _text(ship.get("game_mode"), 50),
            },
            "ranks": rank_rows,
            "reputation": reputation_rows,
            "career": career,
            "achievements": {
                "unlocked": _integer(achievement_snapshot.get("unlocked")),
                "total": _integer(achievement_snapshot.get("total")),
                "points": _integer(achievement_snapshot.get("totalPoints")),
            },
            "log": {
                "sessions": len(sessions),
                "jumps": sum(_integer(row.get("jumps")) for row in sessions),
                "distance": round(session_distance, 1),
                "bio": sum(_integer(row.get("bio_analyses")) for row in sessions),
            },
            "fleet": [
                {
                    "name": _text(row.get("name") or row.get("type") or "Ship", 120),
                    "type": _text(row.get("type"), 100),
                    "system": _text(row.get("system") or stored.get("system") or stored.get("station") or "Local shipyard", 140),
                    "hot": bool(row.get("hot")),
                    "in_transit": bool(row.get("in_transit")),
                    "transfer_cr": _number(row.get("transfer_cr")),
                }
                for row in stored_rows[:80] if isinstance(row, dict)
            ],
            "carrier": {
                "name": _text(carrier.get("name") or carrier.get("callsign"), 120),
                "callsign": _text(carrier.get("callsign"), 40),
                "system": _text(carrier.get("system"), 140),
                "fuel": _number(carrier.get("fuel_level")),
                "status": _text(carrier.get("status") or "idle", 30),
            },
            "missions": [
                {
                    "name": _text(row.get("name") or row.get("kind") or "Mission", 160),
                    "kind": _text(row.get("kind"), 80),
                    "destination": _text(" · ".join(filter(None, (row.get("destination_system"), row.get("destination_station")))), 180),
                    "expiry": self._html_expiry(row.get("expiry")),
                    "reward": _number(row.get("reward")),
                }
                for row in missions[:80] if isinstance(row, dict)
            ],
            "surface_vehicles": [
                {
                    "name": _text(row.get("name") or "Surface vehicle", 120),
                    "symbol": _text(row.get("symbol"), 80),
                    "id": row.get("id"), "loadout": _text(row.get("loadout"), 80),
                    "launches": _integer(row.get("launches")),
                    "restocks": _integer(row.get("restocks")),
                    "destroyed": bool(row.get("destroyed")),
                    "last_event": _text(row.get("last_event"), 40),
                    "last_seen": row.get("last_seen_ts"),
                }
                for row in (vehicles.get("observed") or [])[:80] if isinstance(row, dict)
            ],
            "session": {
                "game_mode": _text(getattr(self, "current_game_mode", None) or "Unknown", 50),
                "repair_drone_events": _integer(maintenance.get("repair_drone_events")),
                "last_repair": maintenance.get("last_repair_drone") or {},
            },
            "loadout_ready": bool(companion.get("loadout")),
            "integrations": {
                "edsm": bool(self.config.get("edsm_upload_enabled")),
                "eddn": bool(self.config.get("eddn_market_upload_enabled", True)),
                "discord": bool(self.config.get("carrier_discord_webhook_url")),
            },
        }

    def _html_analytics_workspace(self, include_science=True):
        sessions = []
        logbook = getattr(self, "captains_log", None)
        if logbook is not None:
            try:
                sessions = logbook.sessions()
            except Exception:
                sessions = []
        session_rows = []
        for session in sessions[:120]:
            session_rows.append({
                "started": _text(session.get("started"), 40),
                "ended": _text(session.get("ended"), 40),
                "start_system": _text(session.get("start_system") or "—", 140),
                "end_system": _text(session.get("end_system") or session.get("start_system") or "—", 140),
                "jumps": _integer(session.get("jumps")),
                "distance": round(_number(session.get("distance_ly"), 0) or 0, 1),
                "fss": _integer(session.get("fss_surveys")),
                "dss": _integer(session.get("dss_maps")),
                "bio": _integer(session.get("bio_analyses")),
                "codex": _integer(session.get("codex")),
            })
        elapsed_provider = getattr(self, "_get_session_elapsed_text", None)
        base = {
            "current": {
                "elapsed": elapsed_provider() if callable(elapsed_provider) else "00:00:00",
                "jumps": _integer(getattr(self, "session_jump_count", 0)),
                "distance": round(_number(getattr(self, "session_ly", 0), 0) or 0, 1),
                "systems": len(getattr(self, "session_systems", None) or ()),
            },
            "sessions": session_rows,
        }
        if not include_science:
            return base
        profile = get_active_profile(self.config)
        now = time.monotonic()
        cache = getattr(self, "_html_science_lab_cache", None)
        if not isinstance(cache, dict) or cache.get("profile") != profile or now - _number(cache.get("time"), 0) > 6.0:
            scan_rows = []
            lock = getattr(self, "db_lock", None)
            acquired = bool(lock and lock.acquire(blocking=False))
            if acquired:
                try:
                    for system, payload in self.conn.execute(
                        "SELECT system_name, data_json FROM scan_hud_items"
                    ).fetchall():
                        try:
                            item = json.loads(payload)
                        except (TypeError, json.JSONDecodeError):
                            continue
                        if isinstance(item, dict):
                            scan_rows.append((system, item))
                except Exception:
                    scan_rows = []
                finally:
                    lock.release()
            elif isinstance(cache, dict):
                scan_rows = None
            deep = getattr(self, "deep_survey", None)
            try:
                region_state = deep.region_passport_state() if deep is not None else {}
            except Exception:
                region_state = {}
            if scan_rows is not None:
                cache = {
                    "profile": profile, "time": now,
                    "science": build_science_lab(scan_rows),
                    "passport": build_region_passport(region_state),
                }
                self._html_science_lab_cache = cache
        cache = cache if isinstance(cache, dict) else {
            "science": build_science_lab([]), "passport": build_region_passport({}),
        }
        return {
            **base,
            "science": cache.get("science") or build_science_lab([]),
            "passport": cache.get("passport") or build_region_passport({}),
        }

    def _html_chronicle_workspace(self):
        analytics = self._html_analytics_workspace(include_science=False)
        analytics.pop("current", None)
        logbook = getattr(self, "captains_log", None)
        sessions = []
        if logbook is not None:
            try:
                sessions = logbook.sessions()
            except Exception:
                sessions = []
        analytics["sessions"] = [
            {
                **analytics["sessions"][index],
                "highlights": [
                    {
                        "kind": _text(item.get("kind") or "LOG", 30),
                        "title": _text(item.get("title") or "Journal event", 180),
                        "detail": _text(item.get("detail"), 260),
                        "timestamp": _text(item.get("timestamp"), 40),
                    }
                    for item in (session.get("highlights") or [])[-24:] if isinstance(item, dict)
                ],
            }
            for index, session in enumerate(sessions[:120])
        ]
        deep = getattr(self, "deep_survey", None)
        try:
            replay_state = deep.replay_state() if deep is not None else {}
        except Exception:
            replay_state = {}
        analytics["replay"] = build_replay(sessions[:120], replay_state)
        try:
            discoveries = deep.discovery_state(160) if deep is not None else []
        except Exception:
            discoveries = []
        analytics["discoveries"] = [
            {
                "timestamp": _text(row.get("timestamp"), 40),
                "event": _text(row.get("event"), 40),
                "system": _text(row.get("system"), 140),
                "body": _text(row.get("body"), 160),
                "title": _text(row.get("title") or "Field discovery", 180),
                "detail": _text(row.get("detail"), 220),
                "value": _integer(row.get("value")),
            }
            for row in reversed(discoveries) if isinstance(row, dict)
        ]
        return analytics

    def _html_mission_workspace(self):
        manager = getattr(self, "expedition_manager", None)
        expeditions = []
        active_id = ""
        if manager is not None:
            try:
                active = manager.active() or {}
                active_id = _text(active.get("id"), 40)
                expeditions = manager.expeditions()
            except Exception:
                expeditions = []
        rendered = []
        for row in expeditions[:80]:
            if not isinstance(row, dict):
                continue
            stats = row.get("stats") or {}
            objectives = []
            for objective in row.get("objectives") or []:
                if not isinstance(objective, dict):
                    continue
                objectives.append({
                    "id": _text(objective.get("id"), 50),
                    "title": _text(objective.get("title") or objective.get("name") or objective.get("kind"), 180),
                    "detail": _text(objective.get("detail") or objective.get("description"), 260),
                    "complete": str(objective.get("status") or "").casefold() == "complete",
                    "kind": _text(objective.get("kind"), 40),
                })
            rendered.append({
                "id": _text(row.get("id"), 40),
                "name": _text(row.get("name") or "Expedition", 140),
                "description": _text(row.get("description"), 400),
                "status": _text(row.get("status") or "paused", 30),
                "started": _text(row.get("started"), 40),
                "destination": _text(row.get("destination"), 140),
                "return_system": _text(row.get("return_system"), 140),
                "objectives": objectives,
                "stats": {
                    "jumps": _integer(stats.get("jumps")),
                    "distance": round(_number(stats.get("distance_ly"), 0) or 0, 1),
                    "systems": len(stats.get("systems") or []),
                    "fss": _integer(stats.get("fss_scans")),
                    "dss": _integer(stats.get("dss_maps")),
                    "bio": _integer(stats.get("bio_analyses")),
                    "codex": _integer(stats.get("codex")),
                },
            })
        waypoint_manager = getattr(self, "waypoint_manager", None)
        return {
            "active_id": active_id,
            "expeditions": rendered,
            "route": [_text(item, 140) for item in (getattr(self, "route_list", None) or [])[:160]],
            "waypoints": [
                {
                    "name": _text(row.get("name"), 140),
                    "visited": bool(row.get("visited")),
                    "notes": _text(row.get("note") or row.get("notes"), 240),
                }
                for row in (getattr(waypoint_manager, "waypoints", None) or [])[:160]
                if isinstance(row, dict)
            ],
        }

    def _html_ground_workspace(self):
        try:
            target_configured = bool(self._ground_target_configured())
        except Exception:
            target_configured = False
        try:
            solution = self._ground_target_solution() or {}
        except Exception:
            solution = {}
        try:
            trail = self._surface_trail_snapshot() or {}
        except Exception:
            trail = {}
        specialist = getattr(self, "specialist_engine", None)
        try:
            exobiology = specialist.exobiology_snapshot() if specialist is not None else {}
        except Exception:
            exobiology = {}
        field_map = exobiology.get("current_map") or {}
        sampling = self._sampling_snapshot() if getattr(self, "bio_sampling", None) else None
        completed = []
        for row in (field_map.get("completed") or {}).values():
            if not isinstance(row, dict):
                continue
            completed.append({
                "genus": _text(row.get("genus"), 100),
                "species": _text(row.get("species"), 140),
                "variant": _text(row.get("variant"), 180),
                "count": _integer(row.get("count"), 1),
            })
        return {
            "system": _text(getattr(self, "current_sys", None), 140),
            "body": _text(getattr(self, "current_body_name", None), 140),
            "elite_target": self._html_local_body_target(),
            "on_planet": bool(getattr(self, "on_planet", False)),
            "position": {
                "lat": _number(getattr(self, "current_latitude", None)),
                "lon": _number(getattr(self, "current_longitude", None)),
                "heading": _number(getattr(self, "current_heading", None)),
                "altitude": _number(getattr(self, "current_altitude", None)),
            },
            "target": {
                "active": target_configured,
                "lat": _number(getattr(self, "target_lat", None)) if target_configured else None,
                "lon": _number(getattr(self, "target_lon", None)) if target_configured else None,
                "popup": bool(getattr(self, "ground_popup_enabled", True)),
                "state": _text(solution.get("state"), 30),
                "bearing": _number(solution.get("bearing")),
                "distance": _number(solution.get("distance_m")),
                "direction": _text(solution.get("direction"), 60),
                "heading_delta": _number(solution.get("heading_delta")),
            },
            "trail": {
                "travelled": _number(trail.get("travelled_m"), 0),
                "return_distance": _number(trail.get("return_distance_m")),
                "return_bearing": _number(trail.get("return_bearing_deg")),
                "points": [
                    {
                        "east": _number(row.get("east_m"), 0),
                        "north": _number(row.get("north_m"), 0),
                        "kind": _text(row.get("kind"), 30),
                        "label": _text(row.get("label"), 100),
                    }
                    for row in (trail.get("plot") or [])[-400:] if isinstance(row, dict)
                ],
            },
            "field_map": {
                "system": _text(field_map.get("system"), 140),
                "body": _text(field_map.get("body"), 180),
                "radius_m": _number(field_map.get("radius_m")),
                "heading": _number(getattr(self, "current_heading", None)),
                "signals": _integer(field_map.get("signal_count")),
                "genuses": [
                    _text(row.get("name") or row.get("symbol"), 120)
                    for row in (field_map.get("genuses") or []) if isinstance(row, dict)
                ],
                "completed": completed,
                "sampling": {
                    **dict(exobiology.get("sampling") or {}),
                    **dict(sampling or {}),
                },
                "pins": [
                    {
                        "id": _text(row.get("id"), 60),
                        "kind": _text(row.get("kind"), 40),
                        "label": _text(row.get("label"), 160),
                        "east": _number(row.get("east_m"), 0),
                        "north": _number(row.get("north_m"), 0),
                        "distance": _number(row.get("distance_m")),
                        "bearing": _number(row.get("bearing_deg")),
                        "source": _text(row.get("source"), 40),
                        "manual": str(row.get("source") or "").casefold() == "manual",
                        "metadata": {
                            "scan_type": _text((row.get("metadata") or {}).get("scan_type"), 30),
                            "progress": _integer((row.get("metadata") or {}).get("progress")),
                            "species": _text((row.get("metadata") or {}).get("species"), 140),
                            "sample_group": _text((row.get("metadata") or {}).get("sample_group"), 60),
                        },
                    }
                    for row in (field_map.get("pins") or [])[-300:] if isinstance(row, dict)
                ],
            },
        }

    def _html_mining_store(self):
        path = os.path.abspath(self.config.get("mining_db_file") or "mining_data.db")
        store = getattr(self, "_html_mining_data_store", None)
        if store is None or os.path.abspath(store.db_path) != path:
            store = MiningDataStore(path)
            self._html_mining_data_store = store
        return store

    def _record_mining_ring_signal(self, raw):
        """Persist a journal-confirmed ring hotspot in the active profile."""
        raw = raw if isinstance(raw, dict) else {}
        body = _text(raw.get("BodyName"), 180)
        if "ring" not in body.casefold():
            return False
        signals = [row for row in raw.get("Signals") or [] if isinstance(row, dict)]
        if not signals:
            return False
        coords = getattr(self, "current_coords", None) or ()
        if not isinstance(coords, (list, tuple)):
            coords = ()
        changed = False
        store = self._html_mining_store()
        for signal in signals:
            material = normalize_material_name(
                signal.get("Type_Localised") or signal.get("Type")
            )
            if not material or material.casefold() in {"biological", "geological", "human"}:
                continue
            store.upsert_hotspot({
                "system_name": getattr(self, "current_sys", None),
                "body_name": body, "material_name": material,
                "hotspot_count": _integer(signal.get("Count")),
                "x_coord": coords[0] if len(coords) >= 3 else None,
                "y_coord": coords[1] if len(coords) >= 3 else None,
                "z_coord": coords[2] if len(coords) >= 3 else None,
                "data_source": "Commander DSS",
                "scan_date": raw.get("timestamp"),
            })
            changed = True
        return changed

    @staticmethod
    def _html_mining_missions(companion):
        missions = (companion or {}).get("missions") or {}
        rows = missions.values() if isinstance(missions, dict) else missions
        mining_names = {name.casefold() for name in MINING_MATERIALS}
        result = []
        for mission in rows or []:
            if not isinstance(mission, dict):
                continue
            internal = str(mission.get("internal_name") or mission.get("name") or "")
            commodity = _text(
                mission.get("commodity") or mission.get("commodity_symbol"), 100,
            )
            if "mining" not in internal.casefold() and commodity.casefold() not in mining_names:
                continue
            required = _integer(mission.get("to_deliver") or mission.get("count"))
            delivered = _integer(mission.get("delivered"))
            result.append({
                "commodity": commodity or "Mining commodity",
                "required": required, "delivered": delivered,
                "remaining": max(0, required - delivered),
                "destination": _text(
                    mission.get("destination_station") or mission.get("destination_system"), 160,
                ),
                "expiry": mission.get("expiry"),
            })
        return result[:20]

    def _html_mining_workspace(self):
        engine = getattr(self, "specialist_engine", None)
        try:
            snapshot = engine.mining_snapshot() if engine is not None else {}
        except Exception:
            snapshot = {}
        session = snapshot.get("session") or {}
        plan = snapshot.get("plan") or {}
        readiness = snapshot.get("readiness") or {}
        current = session.get("current_prospect") or {}
        tool = self._html_profile_transient(
            "_html_mining_tool_state",
            {
                "ring_status": "ready", "ring_detail": "Search commander and Spansh ring intelligence.",
                "ring_results": [], "buyer_status": "ready",
                "buyer_detail": "Find a market for the planned mining haul.",
                "buyer_results": [],
            },
        )
        try:
            bookmarks = self._html_mining_store().list_bookmarks()
        except Exception:
            bookmarks = []
        companion = getattr(self, "companion_state", None) or {}
        return {
            "active": bool(snapshot.get("active")),
            "system": _text(getattr(self, "current_sys", None), 140),
            "materials": sorted(MINING_MATERIALS),
            "plan": {
                "target": _text(plan.get("target_material"), 100),
                "minimum": _number(plan.get("minimum_percent"), 20),
                "cargo_goal": _integer(plan.get("cargo_goal_t")),
                "method": _text(plan.get("method") or "auto", 30),
            },
            "readiness": {
                "ready": bool(readiness.get("ready")),
                "method": _text(readiness.get("method") or "auto", 30),
                "ship": _text(readiness.get("ship"), 100),
                "cargo_capacity": _integer(readiness.get("cargo_capacity")),
                "limpets": _integer(readiness.get("limpets")),
                "missing": [_text(row, 100) for row in readiness.get("missing") or []],
                "equipment": dict(readiness.get("equipment") or {}),
                "dss_recommended": bool(readiness.get("dss_recommended")),
                "surface_vehicle": bool(readiness.get("surface_vehicle")),
            },
            "session": {
                "mode": _text(session.get("mode") or "asteroid", 30),
                "vehicle": _text(session.get("vehicle"), 100),
                "vehicle_id": session.get("vehicle_id"),
                "cargo_capacity": _integer(session.get("cargo_capacity")),
                "started": session.get("started_ts"),
                "duration": _integer(session.get("duration_s")),
                "prospected": _integer(session.get("asteroids_prospected")),
                "cracked": _integer(session.get("asteroids_cracked")),
                "refined_t": _integer(session.get("refined_t")),
                "processing_events": _integer(session.get("processing_events")),
                "cargo_current_t": _integer(session.get("cargo_current_t")),
                "cargo_removed_t": _integer(session.get("cargo_removed_t")),
                "tons_per_hour": _number(session.get("tons_per_hour")),
                "tons_per_asteroid": _number(session.get("tons_per_asteroid")),
                "asteroids_per_hour": _number(session.get("asteroids_per_hour")),
                "revenue": _number(session.get("attributed_revenue_cr")),
                "net": _number(session.get("net_after_limpet_cash_cr")),
                "revenue_per_hour": _number(session.get("revenue_per_hour_cr")),
                "hit_rate": _number(session.get("target_hit_rate")),
                "qualified_rate": _number(session.get("qualified_rate")),
                "target_average": _number(session.get("target_average_pct")),
                "target_best": _number(session.get("target_best_pct"), 0),
                "cargo_goal": _integer(session.get("cargo_goal_t")),
                "cargo_goal_remaining": _integer(session.get("cargo_goal_remaining_t")),
                "cargo_goal_percent": _number(session.get("cargo_goal_percent")),
                "goal_minutes": _integer(session.get("estimated_goal_minutes")),
                "limpets": session.get("limpets") or {},
                "current": {
                    "decision": _text(current.get("decision") or "AWAITING", 30),
                    "target": _text(current.get("target"), 100),
                    "target_percent": _number(current.get("target_pct"), 0),
                    "content": _text(current.get("content"), 100),
                    "remaining": _number(current.get("remaining")),
                    "motherlode": _text(current.get("motherlode"), 100),
                    "refined_since_prospect": _integer(current.get("refined_since_prospect")),
                    "materials": [
                        {"name": _text(row.get("name"), 100), "percent": _number(row.get("percent"), 0)}
                        for row in current.get("materials") or [] if isinstance(row, dict)
                    ],
                },
                "prospects": [
                    {
                        "decision": _text(row.get("decision"), 30),
                        "target": _text(row.get("target"), 100),
                        "target_percent": _number(row.get("target_pct"), 0),
                        "motherlode": _text(row.get("motherlode"), 100),
                        "refined": _integer(row.get("refined_since_prospect")),
                        "timestamp": row.get("timestamp"),
                    }
                    for row in reversed((session.get("prospect_log") or [])[-20:])
                    if isinstance(row, dict)
                ],
                "materials": [
                    {
                        "name": _text(row.get("name") or row.get("symbol"), 100),
                        "sightings": _integer(row.get("sightings")),
                        "best": _number(row.get("best_pct"), 0),
                        "average": _number(row.get("average_pct"), 0),
                    }
                    for row in (session.get("prospected_materials") or [])[:80]
                ],
                "yield": [
                    {
                        "name": _text(row.get("name") or row.get("symbol"), 100),
                        "count": _integer(row.get("count")),
                        "cargo_delta": _integer(row.get("cargo_delta")),
                        "sold": _integer(row.get("sold_t")),
                    }
                    for row in (session.get("cargo_yield") or [])[:80]
                ],
            },
            "history": [
                {
                    "started": row.get("started_ts"),
                    "ended": row.get("ended_ts"),
                    "system": _text(row.get("system"), 140),
                    "refined": _integer(row.get("refined_t")),
                    "prospected": _integer(row.get("asteroids_prospected")),
                    "revenue": _number(row.get("attributed_revenue_cr")),
                    "duration": _integer(row.get("duration_s")),
                    "tons_per_hour": _number(row.get("tons_per_hour")),
                    "hit_rate": _number(row.get("target_hit_rate")),
                    "qualified_rate": _number(row.get("qualified_rate")),
                    "target_best": _number(row.get("target_best_pct"), 0),
                    "target": _text((row.get("plan") or {}).get("target_material"), 100),
                }
                for row in (snapshot.get("history") or [])[:80] if isinstance(row, dict)
            ],
            "ring_scans": [
                {
                    "system": _text(row.get("system"), 140),
                    "body": _text(row.get("body"), 180),
                    "timestamp": row.get("timestamp"),
                    "signals": [
                        {"name": _text(signal.get("name"), 100), "count": _integer(signal.get("count"))}
                        for signal in row.get("signals") or [] if isinstance(signal, dict)
                    ],
                }
                for row in (snapshot.get("ring_scans") or [])[:30] if isinstance(row, dict)
            ],
            "surface_scans": [
                {
                    "system": _text(row.get("system"), 140),
                    "body": _text(row.get("body"), 180),
                    "body_id": row.get("body_id"),
                    "timestamp": row.get("timestamp"),
                    "mining_locations": _integer(row.get("mining_locations")),
                    "signals": [
                        {"name": _text(signal.get("name"), 100), "count": _integer(signal.get("count"))}
                        for signal in row.get("signals") or [] if isinstance(signal, dict)
                    ],
                }
                for row in (snapshot.get("surface_scans") or [])[:30] if isinstance(row, dict)
            ],
            "bookmarks": [
                {
                    "id": _integer(row.get("id")), "system": _text(row.get("system_name"), 140),
                    "body": _text(row.get("body_name"), 180),
                    "material": _text(row.get("material_name"), 100),
                    "notes": _text(row.get("notes"), 500), "created": row.get("created_at"),
                }
                for row in bookmarks[:100] if isinstance(row, dict)
            ],
            "missions": self._html_mining_missions(companion),
            "tools": {
                "ring_status": _text(tool.get("ring_status") or "ready", 30),
                "ring_detail": _text(tool.get("ring_detail"), 500),
                "ring_results": list(tool.get("ring_results") or [])[:250],
                "buyer_status": _text(tool.get("buyer_status") or "ready", 30),
                "buyer_detail": _text(tool.get("buyer_detail"), 500),
                "buyer_results": list(tool.get("buyer_results") or [])[:250],
            },
        }

    def _html_engineering_workspace(self):
        state = getattr(self, "engineer_materials", None) or {}
        try:
            wishlist = engineering_data.wishlist_plan(state)
            pins = engineering_data.pinned_plans(state)
            priorities = engineering_data.collection_priorities(state, limit=40)
            odyssey = engineering_data.odyssey_wishlist_plan(state)
        except Exception:
            wishlist, pins, priorities, odyssey = {}, [], [], {}
        engineers = []
        for name, row in (state.get("engineers") or {}).items():
            if not isinstance(row, dict):
                row = {"rank": row}
            engineers.append({
                "name": _text(row.get("name") or name, 120),
                "rank": row.get("rank"),
                "progress": _text(row.get("progress"), 60),
                "system": _text(row.get("system"), 120),
            })
        inventory = []
        for category in ("raw", "manufactured", "encoded"):
            for symbol, row in (state.get(category) or {}).items():
                count = row.get("count") if isinstance(row, dict) else row
                info = engineering_data.material_info(symbol)
                inventory.append({
                    "category": category,
                    "symbol": _text(symbol, 80),
                    "name": _text(info.get("name") or symbol, 120),
                    "grade": _integer(info.get("grade")),
                    "count": _integer(count),
                    "capacity": _integer(info.get("capacity")),
                })
        raw_counts = {
            str(symbol).casefold(): _integer(row.get("count") if isinstance(row, dict) else row)
            for symbol, row in (state.get("raw") or {}).items()
        }
        try:
            synthesis = companion_features.fsd_injections(raw_counts)
        except Exception:
            synthesis = {"basic": 0, "standard": 0, "premium": 0}
        return {
            "last_updated": _text(state.get("last_updated"), 60),
            "pins": [
                {
                    "name": _text(row.get("blueprint"), 160),
                    "grade": _integer(row.get("grade")),
                    "current_grade": _integer(row.get("current_grade")),
                    "quantity": _integer(row.get("quantity"), 1),
                    "craftable": bool(row.get("craftable")),
                    "materials": row.get("materials") or [],
                }
                for row in pins[:60]
            ],
            "wishlist": {
                "pins": _integer(wishlist.get("pins")),
                "required": _integer(wishlist.get("required_units")),
                "missing": _integer(wishlist.get("missing_units")),
                "complete": bool(wishlist.get("complete")),
                "materials": (wishlist.get("materials") or [])[:120],
            },
            "priorities": priorities[:40],
            "odyssey": {
                "goals": (odyssey.get("goals") or [])[:50],
                "materials": (odyssey.get("materials") or [])[:120],
                "required": _integer(odyssey.get("required_units")),
                "missing": _integer(odyssey.get("missing_units")),
                "complete": bool(odyssey.get("complete")),
            },
            "engineers": engineers[:80],
            "inventory": inventory[:600],
            "synthesis": synthesis,
            "catalogue": [
                {"name": name, "grade": max(recipe) if recipe else 1}
                for name, recipe in sorted(engineering_data.BLUEPRINTS.items())
            ],
            "odyssey_catalogue": sorted(engineering_data.ODYSSEY_BLUEPRINTS),
        }

    def _html_carrier_workspace(self):
        tracker = getattr(self, "carrier_tracker", None)
        carrier = dict(getattr(tracker, "carrier_data", {}) or {})
        engine = getattr(self, "specialist_engine", None)
        try:
            specialist = engine.carrier_snapshot(carrier) if engine is not None else {}
        except Exception:
            specialist = {}
        route = []
        for index, row in enumerate(carrier.get("expedition_route") or []):
            if isinstance(row, str):
                row = {"system": row}
            if not isinstance(row, dict):
                continue
            route.append({
                "index": index,
                "system": _text(row.get("system"), 140),
                "visited": bool(row.get("visited")),
                "distance": _number(row.get("distance_ly")),
                "fuel": _number(row.get("tritium_t") or row.get("fuel_used_t")),
                "tank_after": _number(row.get("tank_after_t") or row.get("fuel_remaining_t")),
                "restock": _number(row.get("restock_t")),
                "body": _text(row.get("body"), 80),
            })
        tool = self._html_profile_transient(
            "_html_carrier_tool_state",
            {
                "route_status": "ready", "route_detail": "Carrier route service ready.",
                "tritium_status": "ready", "tritium_detail": "Search known community ring signals.",
                "tritium_results": [],
                "discord_status": "ready",
                "discord_detail": "Carrier Discord operations ready.",
            },
        )
        carrier_type = _text(carrier.get("carrier_type"), 80)
        is_squadron = carrier_type == "SquadronCarrier"
        discord_configured = bool(
            str(self.config.get("carrier_discord_webhook_url") or "").strip()
        )
        inventory = []
        for symbol, row in (specialist.get("inventory") or {}).items():
            if not isinstance(row, dict):
                row = {"count": row}
            inventory.append({
                "symbol": _text(symbol, 80),
                "name": _text(row.get("name") or symbol, 100),
                "count": _integer(row.get("count")),
            })
        inventory.sort(key=lambda row: (-row["count"], row["name"].casefold()))
        return {
            "carrier": {
                "id": carrier.get("carrier_id"),
                "type": carrier_type,
                "name": _text(carrier.get("name") or carrier.get("callsign"), 140),
                "callsign": _text(carrier.get("callsign"), 40),
                "system": _text(carrier.get("system"), 140),
                "body": _text(carrier.get("body"), 100),
                "status": _text(carrier.get("status") or "idle", 40),
                "fuel": _number(carrier.get("fuel_level")),
                "fuel_capacity": _number(carrier.get("fuel_capacity"), 1000),
                "jump_range": _number(carrier.get("jump_range_curr") or carrier.get("jump_range_max")),
                "destination": _text(carrier.get("jump_destination"), 140),
                "departure": _text(carrier.get("jump_departure_time"), 60),
                "balance": _number(carrier.get("balance")),
                "reserve": _number(carrier.get("reserve_balance")),
                "space_total": _number(carrier.get("space_total")),
                "space_cargo": _number(carrier.get("space_cargo")),
                "space_free": _number(carrier.get("space_free")),
                "access": _text(carrier.get("docking_access"), 80),
                "squadron": _text(carrier.get("squadron_name"), 120),
            },
            "expedition": {
                "name": _text(carrier.get("expedition_name") or "Carrier expedition", 140),
                "reserve": _integer(carrier.get("expedition_reserve_fuel"), 200),
                "route": route,
                "requested": [
                    _text(row, 140) for row in (carrier.get("expedition_requested_destinations") or [])
                    if _text(row, 140)
                ],
                "result_url": _text(carrier.get("expedition_spansh_url"), 500),
            },
            "readiness": specialist.get("route") or {},
            "inventory": inventory[:500],
            "inventory_source": _text(specialist.get("inventory_source"), 120),
            "upkeep": specialist.get("upkeep") or {},
            "orders": (specialist.get("orders") or {}).get("items") or [],
            "services": [
                {
                    "role": _text(row.get("CrewRole") or row.get("Role"), 80),
                    "name": _text(row.get("CrewName") or row.get("Name"), 100),
                    "active": bool(row.get("Activated")),
                    "enabled": bool(row.get("Enabled")),
                }
                for row in (carrier.get("crew") or []) if isinstance(row, dict)
            ],
            "jump_history": [
                {
                    "system": _text(row.get("system"), 140),
                    "timestamp": _text(row.get("timestamp"), 50),
                    "fuel": _number(row.get("fuel_used")),
                }
                for row in (carrier.get("jump_history") or [])[-80:] if isinstance(row, dict)
            ],
            "discord": {
                "configured": discord_configured,
                "carrier_kind": "SQUADRON CARRIER" if is_squadron else "PERSONAL FLEET CARRIER",
                "destination_note": _text(carrier.get("destination_note"), 240),
                "operator_note": _text(carrier.get("notes"), 500),
                "events": [
                    {
                        "label": label,
                        "enabled": bool(self.config.get(f"carrier_discord_{key}", True)),
                    }
                    for key, label in (
                        ("jump_plotted", "JUMP PLOTTED"),
                        ("jump_completed", "ARRIVAL"),
                        ("jump_cancelled", "CANCELLATION"),
                        ("cooldown_finished", "COOLDOWN READY"),
                    )
                ],
                "status": _text(tool.get("discord_status"), 30),
                "detail": _text(tool.get("discord_detail"), 400),
            },
            "tools": {
                "route_status": _text(tool.get("route_status"), 30),
                "route_detail": _text(tool.get("route_detail"), 400),
                "tritium_status": _text(tool.get("tritium_status"), 30),
                "tritium_detail": _text(tool.get("tritium_detail"), 400),
                "tritium_results": (tool.get("tritium_results") or [])[:200],
            },
        }

    def _html_recon_workspace(self):
        bodies = [row for row in (getattr(self, "scan_items", None) or []) if isinstance(row, dict)]
        try:
            report = recon_report(
                getattr(self, "current_sys", "Unknown"), bodies,
                _integer(getattr(self, "scanned", 0)),
                _integer(getattr(self, "total", 0)),
                getattr(self, "system_traffic", {}) or {},
            )
        except Exception:
            report = {"system": getattr(self, "current_sys", "Unknown"), "score": 0, "grade": "unknown", "gaps": []}
        deep = getattr(self, "deep_survey", None)
        try:
            stored = deep.snapshot() if deep is not None else {}
        except Exception:
            stored = {}
        return {
            "report": report,
            "candidates": (stored.get("candidates") or [])[-80:],
            "revisits": (stored.get("revisit_queue") or [])[-80:],
            "milestones": (stored.get("milestones") or [])[-80:],
        }

    def _html_achievements_workspace(self):
        engine = getattr(self, "achievement_engine", None)
        try:
            snapshot = engine.snapshot() if engine is not None else {}
        except Exception:
            snapshot = {}
        achievements = []
        for row in snapshot.get("achievements") or []:
            if not isinstance(row, dict):
                continue
            progress = row.get("progress") or {}
            achievements.append({
                "id": _text(row.get("id"), 100),
                "title": _text(row.get("title") or row.get("id"), 180),
                "description": _text(row.get("desc") or row.get("description"), 320),
                "category": _text(row.get("category"), 80),
                "points": _integer(row.get("points")),
                "unlocked": bool(row.get("unlocked")),
                "unlocked_at": _text(row.get("unlockedAt"), 50),
                "current": _number(progress.get("current")),
                "target": _number(progress.get("target")),
            })
        return {
            "enabled": bool(snapshot.get("enabled", True)),
            "notifications_enabled": bool(
                self.config.get("achievement_notifications_enabled", True)
            ),
            "unlocked": _integer(snapshot.get("unlocked")),
            "total": _integer(snapshot.get("total")),
            "points": _integer(snapshot.get("totalPoints")),
            "categories": snapshot.get("categories") or [],
            "achievements": achievements,
        }

    def _html_ledger_workspace(self):
        cached_at, cached_rows = getattr(self, "_html_ledger_cache", (0.0, []))
        if time.monotonic() - cached_at < 4.0:
            rows = cached_rows
        else:
            rows = cached_rows
            lock = getattr(self, "db_lock", None)
            acquired = bool(lock and lock.acquire(blocking=False))
            if acquired:
                try:
                    import json
                    fresh = []
                    for system, payload in self.conn.execute("SELECT system_name, data_json FROM scan_hud_items").fetchall():
                        try:
                            item = json.loads(payload)
                        except Exception:
                            continue
                        if not isinstance(item, dict) or item.get("is_star"):
                            continue
                        body_class = item.get("planet_class") or item.get("class") or ""
                        value = _integer(item.get("dss_reward") if item.get("dss_complete") else item.get("reward"))
                        valuable = bool(
                            item.get("terraformable")
                            or body_class in {"Earthlike body", "Water world", "Ammonia world"}
                            or value >= 500000
                        )
                        if not valuable:
                            continue
                        flags = []
                        if item.get("terraformable"):
                            flags.append("Terraformable")
                        if item.get("was_discovered") is False:
                            flags.append("First discovered")
                        if item.get("first_footfall"):
                            flags.append("First footfall available")
                        if item.get("landable"):
                            flags.append("Landable")
                        fresh.append({
                            "system": _text(system, 140),
                            "body": _text(item.get("full_name") or item.get("name"), 160),
                            "class": _text(body_class, 100),
                            "value": value,
                            "mapped": bool(item.get("dss_complete") or item.get("was_mapped")),
                            "flags": flags,
                        })
                    rows = sorted(fresh, key=lambda row: row["value"], reverse=True)[:800]
                    self._html_ledger_cache = (time.monotonic(), rows)
                except Exception:
                    pass
                finally:
                    lock.release()
        return {"rows": rows, "total": sum(_integer(row.get("value")) for row in rows)}

    def _html_settings_workspace(self):
        hotkeys = [
            {
                "action": action, "key": key, "label": label,
                "value": _text(self.config.get(key), 80),
                "default": _text(DEFAULT_OVERLAY_HOTKEYS.get(key), 80),
            }
            for action, key, label, _attr in OVERLAY_HOTKEY_SPECS
        ]
        try:
            health = self._adaptive_health_snapshot()
        except Exception:
            health = {}
        try:
            from services.eddn_upload import UPLOADER as eddn_market_uploader
            eddn = eddn_market_uploader.stats()
        except Exception:
            eddn = {}
        values = {}
        for key in (
            "journal_path", "screenshots_path", "screenshots_enabled",
            "ui_scale_percent", "reduced_motion_enabled", "hud_animation_intensity",
            "overlay_hotkeys_enabled",
            "edsm_cmdr_name", "edsm_api_key", "edsm_upload_enabled",
            "eddn_market_upload_enabled", "carrier_discord_webhook_url",
            "runtime_trace_enabled", "crash_reporting_enabled",
            "recovery_safe_mode_enabled", "edsm_backfill_on_cache_rebuild",
            "automatic_profile_backups_enabled",
            "galnet_enabled", "galnet_auto_rotate_enabled",
            "galnet_rotation_seconds", "galnet_refresh_minutes",
        ):
            value = self.config.get(key)
            values[key] = value if isinstance(value, (str, int, float, bool)) or value is None else str(value)
        theme_name, theme_palette = themes.resolve_theme(
            self.config.get("ui_theme_name"), self.config.get("ui_custom_themes") or {},
        )
        tools = self._html_profile_transient(
            "_html_settings_tool_state",
            {"status": "ready", "detail": "Integration tests have not run this session."},
        )
        return {
            "values": values, "hotkeys": hotkeys, "health": health, "eddn": eddn,
            "galnet": self._html_dashboard_galnet(),
            "theme_editor": {
                "name": theme_name,
                "palette": theme_palette,
                "custom": sorted((self.config.get("ui_custom_themes") or {}).keys()),
                "keys": list(themes.THEME_KEYS),
            },
            "tools": {
                "status": _text(tools.get("status"), 30),
                "detail": _text(tools.get("detail"), 500),
            },
        }

    def _html_workspace(self, page):
        builders = {
            "explore": self._html_explore_workspace,
            "profile": self._html_profile_workspace,
            "analytics": self._html_analytics_workspace,
            "chronicle": self._html_chronicle_workspace,
            "mission": self._html_mission_workspace,
            "ground": self._html_ground_workspace,
            "mining": self._html_mining_workspace,
            "engineering": self._html_engineering_workspace,
            "carrier": self._html_carrier_workspace,
            "recon": self._html_recon_workspace,
            "achievements": self._html_achievements_workspace,
            "ledger": self._html_ledger_workspace,
            "settings": self._html_settings_workspace,
        }
        builder = builders.get(page)
        if builder is None:
            return {"page": page, "ready": False}
        try:
            return {"page": page, "ready": True, "data": builder()}
        except Exception as exc:
            logging.exception("HTML workspace snapshot failed for %s", page)
            return {"page": page, "ready": False, "error": _text(exc, 240)}

    def _html_overlay_desktop(self):
        """Return the complete Windows virtual desktop in screen coordinates."""
        try:
            import ctypes

            user32 = ctypes.windll.user32
            left = int(user32.GetSystemMetrics(76))
            top = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
            primary_width = int(user32.GetSystemMetrics(0))
            primary_height = int(user32.GetSystemMetrics(1))
            if width > 0 and height > 0:
                return {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "primary": {
                        "left": 0, "top": 0,
                        "width": max(1, primary_width),
                        "height": max(1, primary_height),
                    },
                }
        except (AttributeError, OSError):
            pass
        try:
            width = max(1, int(self.root.winfo_screenwidth()))
            height = max(1, int(self.root.winfo_screenheight()))
        except Exception:
            width, height = 1920, 1080
        return {
            "left": 0, "top": 0, "width": width, "height": height,
            "primary": {"left": 0, "top": 0, "width": width, "height": height},
        }

    @staticmethod
    def _html_overlay_window_shown(window):
        try:
            return bool(window.winfo_viewable()) and str(window.state()) not in {
                "withdrawn", "iconic",
            }
        except Exception:
            return False

    def _html_overlay_records(self, *, live=True):
        records = []
        for attr, x_key, y_key in self._OVERLAY_POSITION_SPECS:
            default_x, default_y = DEFAULT_POSITIONS.get(attr, (30, 30))
            default_width, default_height = DEFAULT_SIZES.get(attr, (320, 160))
            x = _integer(self.config.get(x_key), default_x)
            y = _integer(self.config.get(y_key), default_y)
            width, height = default_width, default_height
            overlay = getattr(self, attr, None)
            window = getattr(overlay, "win", overlay)
            shown = self._html_overlay_window_shown(window) if live else False
            html_size = getattr(overlay, "_html_window_size", None)
            if html_ready := bool(getattr(overlay, "_html_ready", False)):
                if isinstance(html_size, (tuple, list)) and len(html_size) == 2:
                    width = max(24, _integer(html_size[0], default_width))
                    height = max(20, _integer(html_size[1], default_height))
            elif live and window is not None:
                try:
                    if window.winfo_exists():
                        if attr == "toast_hud" and not getattr(overlay, "_toasts", None):
                            # Keep a useful draggable footprint in Studio even
                            # while the transient notification queue is empty.
                            width, height = default_width, default_height
                        else:
                            width = max(24, int(window.winfo_width()), int(window.winfo_reqwidth()))
                            height = max(20, int(window.winfo_height()), int(window.winfo_reqheight()))
                except Exception:
                    pass
            enabled = bool(self.config.get(OVERLAY_ENABLE_KEYS.get(attr, ""), False))
            # This flag is ordinary Python state, so it is safe to expose even
            # while avoiding the higher-frequency Tk geometry calls off-page.
            html_ready = bool(getattr(overlay, "_html_ready", False))
            records.append({
                "id": attr,
                "label": OVERLAY_LABELS.get(attr, attr.replace("_", " ").title()),
                "short_label": OVERLAY_CARD_LABELS.get(attr, attr.upper()),
                "x": x, "y": y, "width": width, "height": height,
                "enabled": enabled,
                "shown": shown,
                "html_ready": html_ready,
                "state": (
                    "OFF" if not enabled else
                    "HTML" if html_ready else
                    "SHOWN" if shown else "READY"
                ),
            })
        return records

    def _html_overlay_studio(self):
        presets = self.config.get("overlay_layout_presets") or {}
        preset_names = sorted(
            (_text(name, 50) for name in presets if str(name).strip()),
            key=str.casefold,
        )
        try:
            ground_solution = self._ground_target_solution() or {}
            ground_configured = bool(self._ground_target_configured())
            ground_ready = bool(self._ground_target_should_show(ground_solution))
        except Exception:
            ground_solution = {}
            ground_configured = False
            ground_ready = False
        return {
            "desktop": self._html_overlay_desktop(),
            "overlays": self._html_overlay_records(
                live=getattr(self, "_html_dashboard_active_page", "") == "overlay-studio",
            ),
            "presets": preset_names,
            "ground_target": {
                "active": ground_configured,
                "lat": _number(getattr(self, "target_lat", None)) if ground_configured else None,
                "lon": _number(getattr(self, "target_lon", None)) if ground_configured else None,
                "on_planet": bool(getattr(self, "on_planet", False)),
                "navigation_ready": ground_ready,
                "state": _text(ground_solution.get("state") or "OFF", 30),
                "current_available": bool(
                    getattr(self, "current_latitude", None) is not None
                    and getattr(self, "current_longitude", None) is not None
                ),
            },
            "options": {
                "overlay_mouse_passthrough": bool(self.config.get("overlay_mouse_passthrough", True)),
                "hud_compact_mode": bool(self.config.get("hud_compact_mode", True)),
                "overlay_text_scale_percent": _integer(self.config.get("overlay_text_scale_percent"), 100),
                "overlay_opacity_percent": _integer(self.config.get("overlay_opacity_percent"), 100),
                "sample_clear_notifications_enabled": bool(self.config.get("sample_clear_notifications_enabled", True)),
                "rebuy_warnings_enabled": bool(self.config.get("rebuy_warnings_enabled", True)),
                "data_risk_warnings_enabled": bool(self.config.get("data_risk_warnings_enabled", True)),
                "prospector_hud_timeout_s": _integer(self.config.get("prospector_hud_timeout_s"), 45),
                "gravity_warning_hud_timeout_s": _integer(self.config.get("gravity_warning_hud_timeout_s"), 20),
                "station_info_auto_hide_enabled": bool(self.config.get("station_info_auto_hide_enabled", False)),
                "survey_status_show_all_bodies": bool(self.config.get("survey_status_show_all_bodies", False)),
                "station_info_timeout_s": _integer(self.config.get("station_info_timeout_s"), 30),
                "contact_scope_timeout_s": _integer(self.config.get("contact_scope_timeout_s"), 45),
                "gravity_warning_threshold_g": _number(self.config.get("gravity_warning_threshold_g"), 3.0),
                "hud_crt_enabled": bool(self.config.get("hud_crt_enabled", True)),
                "hud_crt_motion_enabled": bool(self.config.get("hud_crt_motion_enabled", True)),
                "hud_crt_intensity": _text(self.config.get("hud_crt_intensity") or "Subtle", 20).title(),
            },
        }

    def _request_html_dashboard_page(self, page):
        page = _text(page, 40).casefold()
        if page not in {
            "overview", "explore", "map", "records", "operations",
            "overlay-studio", "settings", "about", *_HTML_WORKSPACE_PAGES,
        }:
            return False
        self._html_dashboard_page_request_seq = (
            _integer(getattr(self, "_html_dashboard_page_request_seq", 0)) + 1
        )
        self._html_dashboard_page_request = page
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _html_overlay_row(self, overlay_id):
        overlay_id = _text(overlay_id, 50)
        spec = next(
            (item for item in self._OVERLAY_POSITION_SPECS if item[0] == overlay_id),
            None,
        )
        if spec is None:
            return None
        return spec

    def _html_overlay_position(self, overlay_id, x, y, *, persist=False, preview=False):
        spec = self._html_overlay_row(overlay_id)
        if spec is None:
            return False
        attr, _x_key, _y_key = spec
        records = {row["id"]: row for row in self._html_overlay_records()}
        record = records.get(attr) or {}
        desktop = self._html_overlay_desktop()
        width = max(20, _integer(record.get("width"), DEFAULT_SIZES.get(attr, (320, 160))[0]))
        height = max(20, _integer(record.get("height"), DEFAULT_SIZES.get(attr, (320, 160))[1]))
        left, top = desktop["left"], desktop["top"]
        right, bottom = left + desktop["width"], top + desktop["height"]
        x = max(left, min(_integer(x, left), right - width))
        y = max(top, min(_integer(y, top), bottom - height))
        # Geometry and the lightweight HTML-host window channel stay live
        # during the drag, but the expensive full Dashboard model and config
        # write are deferred until pointer-up.
        self._set_overlay_position(attr, x, y, authority_s=3.0)
        if persist:
            self._persist_config()
        if not preview or persist:
            self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _html_overlay_snap(self, overlay_id):
        records = {row["id"]: row for row in self._html_overlay_records()}
        selected = records.get(overlay_id)
        if selected is None:
            return False
        desktop = self._html_overlay_desktop()
        left, top = desktop["left"], desktop["top"]
        right, bottom = left + desktop["width"], top + desktop["height"]
        width, height = selected["width"], selected["height"]
        x, y = selected["x"], selected["y"]
        candidates_x = [left, max(left, right - width)]
        candidates_y = [top, max(top, bottom - height)]
        for attr, row in records.items():
            if attr == overlay_id:
                continue
            ox, oy, ow, oh = row["x"], row["y"], row["width"], row["height"]
            candidates_x.extend((ox, ox + ow, ox - width, ox + ow - width))
            candidates_y.extend((oy, oy + oh, oy - height, oy + oh - height))
        nearest_x = min(candidates_x, key=lambda value: abs(value - x))
        nearest_y = min(candidates_y, key=lambda value: abs(value - y))
        if abs(nearest_x - x) <= 20:
            x = nearest_x
        if abs(nearest_y - y) <= 20:
            y = nearest_y
        return self._html_overlay_position(overlay_id, x, y, persist=True)

    def _html_overlay_toggle(self, overlay_id):
        spec = self._html_overlay_row(overlay_id)
        key = OVERLAY_ENABLE_KEYS.get(overlay_id)
        if spec is None or not key:
            return False
        previous = bool(self.config.get(key, False))
        self.config[key] = not previous
        try:
            if overlay_id == "ground_popup":
                self.ground_popup_enabled = not previous
                self.update_ground_target_ui()
            self._apply_runtime_feature_toggles()
        except Exception:
            self.config[key] = previous
            if overlay_id == "ground_popup":
                self.ground_popup_enabled = previous
            return False
        self._persist_config()
        try:
            self.add_event_feed_entry(
                "SYSTEM",
                f"{OVERLAY_LABELS.get(overlay_id, overlay_id)} "
                f"{'enabled' if not previous else 'disabled'} in Overlay Studio",
                severity="INFO",
            )
        except Exception:
            pass
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _html_overlay_option_toggle(self, key, requested_value=None):
        allowed = {
            "overlay_mouse_passthrough", "hud_compact_mode",
            "sample_clear_notifications_enabled", "rebuy_warnings_enabled",
            "data_risk_warnings_enabled", "station_info_auto_hide_enabled",
            "survey_status_show_all_bodies",
            "hud_crt_enabled", "hud_crt_motion_enabled",
        }
        key = _text(key, 80)
        if key not in allowed:
            return False
        self.config[key] = (
            requested_value if isinstance(requested_value, bool)
            else not bool(self.config.get(key, False))
        )
        self._persist_config()
        if key == "overlay_mouse_passthrough":
            self._apply_overlay_mouse_passthrough()
        elif key in {"hud_compact_mode", "hud_crt_enabled", "hud_crt_motion_enabled"}:
            self.update_hud()
        elif key == "station_info_auto_hide_enabled":
            station = getattr(self, "station_info_hud", None)
            if station is not None:
                apply_setting = getattr(station, "apply_auto_hide_setting", None)
                if callable(apply_setting):
                    apply_setting(self, self.config[key])
                elif getattr(self, "current_docked", False) and getattr(self, "current_station_name", None):
                    station.on_docked(self)
                else:
                    station.hide()
        elif key == "survey_status_show_all_bodies":
            survey = getattr(self, "survey_status_hud", None)
            if survey is not None:
                survey._last_render_key = None
                if survey._last_update is not None:
                    survey.update(*survey._last_update)
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _html_overlay_settings_save(self, payload):
        numeric = {
            "overlay_text_scale_percent": (75.0, 200.0, 100.0, True),
            "overlay_opacity_percent": (40.0, 100.0, 100.0, True),
            "prospector_hud_timeout_s": (5.0, 3600.0, 45.0, True),
            "gravity_warning_hud_timeout_s": (5.0, 3600.0, 20.0, True),
            "station_info_timeout_s": (5.0, 3600.0, 30.0, True),
            "contact_scope_timeout_s": (0.0, 3600.0, 45.0, True),
            "gravity_warning_threshold_g": (0.5, 20.0, 3.0, False),
        }
        for key, (low, high, default, integer) in numeric.items():
            value = _number(payload.get(key), default)
            value = max(low, min(high, value if value is not None else default))
            self.config[key] = int(round(value)) if integer else round(value, 2)
        intensity = _text(payload.get("hud_crt_intensity") or "Subtle", 20).title()
        self.config["hud_crt_intensity"] = (
            intensity if intensity in {"Subtle", "Standard", "Strong"} else "Subtle"
        )
        self._persist_config()
        self.update_hud()
        station = getattr(self, "station_info_hud", None)
        if station is not None and getattr(self, "current_docked", False):
            station.on_docked(self)
        contact_scope = getattr(self, "contact_scope_hud", None)
        if contact_scope is not None:
            apply_timer = getattr(contact_scope, "apply_auto_hide_setting", None)
            if callable(apply_timer):
                apply_timer()
        self._schedule_html_dashboard_publish(immediate=True)
        return True

    def _handle_html_overlay_studio_command(self, payload):
        operation = _text(payload.get("operation"), 40).casefold()
        overlay_id = _text(payload.get("overlay_id"), 50)
        if operation == "move":
            sequence = max(0, _integer(payload.get("sequence"), 0))
            seen = getattr(self, "_html_overlay_move_sequences", None)
            if not isinstance(seen, dict):
                seen = self._html_overlay_move_sequences = {}
            if sequence and sequence < _integer(seen.get(overlay_id), 0):
                return True
            if sequence:
                seen[overlay_id] = sequence
            return self._html_overlay_position(
                overlay_id, payload.get("x"), payload.get("y"),
                persist=bool(payload.get("commit")),
                preview=not bool(payload.get("commit")),
            )
        if operation == "toggle":
            return self._html_overlay_toggle(overlay_id)
        if operation == "snap":
            return self._html_overlay_snap(overlay_id)
        if operation == "reset":
            x, y = DEFAULT_POSITIONS.get(overlay_id, (30, 30))
            return self._html_overlay_position(overlay_id, x, y, persist=True)
        if operation == "toggle_option":
            return self._html_overlay_option_toggle(
                payload.get("key"), payload.get("value"),
            )
        if operation == "save_settings":
            return self._html_overlay_settings_save(payload)
        if operation == "save_preset":
            name = _text(payload.get("name"), 50)
            if not name:
                return False
            presets = self.config.setdefault("overlay_layout_presets", {})
            presets[name] = {
                row["id"]: {"x": row["x"], "y": row["y"]}
                for row in self._html_overlay_records()
            }
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "apply_preset":
            name = _text(payload.get("name"), 50)
            preset = (self.config.get("overlay_layout_presets") or {}).get(name)
            if not isinstance(preset, dict):
                return False
            applied = False
            for attr, position in preset.items():
                if not isinstance(position, dict) or self._html_overlay_row(attr) is None:
                    continue
                applied = self._html_overlay_position(
                    attr, position.get("x"), position.get("y"), persist=False,
                ) or applied
            if applied:
                self._persist_config()
            return applied
        if operation == "delete_preset":
            name = _text(payload.get("name"), 50)
            presets = self.config.get("overlay_layout_presets") or {}
            if name not in presets:
                return False
            presets.pop(name, None)
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        return False

    def _html_dashboard_galnet(self):
        service = getattr(self, "galnet_feed", None)
        if service is None:
            return {
                "enabled": bool(self.config.get("galnet_enabled", True)),
                "auto_rotate": bool(self.config.get("galnet_auto_rotate_enabled", True)),
                "rotation_seconds": max(4, min(60, _integer(self.config.get("galnet_rotation_seconds"), 7))),
                "refresh_minutes": max(5, min(240, _integer(self.config.get("galnet_refresh_minutes"), 30))),
                "status": "waiting", "detail": "Awaiting Galnet relay",
                "busy": False, "source": "Frontier Galnet",
                "updated_at": "", "articles": [],
            }
        try:
            snapshot = service.snapshot()
        except Exception:
            return {
                "enabled": bool(self.config.get("galnet_enabled", True)),
                "auto_rotate": bool(self.config.get("galnet_auto_rotate_enabled", True)),
                "rotation_seconds": max(4, min(60, _integer(self.config.get("galnet_rotation_seconds"), 7))),
                "refresh_minutes": max(5, min(240, _integer(self.config.get("galnet_refresh_minutes"), 30))),
                "status": "error", "detail": "Galnet relay unavailable",
                "busy": False, "source": "Frontier Galnet",
                "updated_at": "", "articles": [],
            }
        articles = []
        for row in (snapshot.get("articles") or [])[:16]:
            if not isinstance(row, dict):
                continue
            articles.append({
                "id": _text(row.get("id"), 300),
                "title": _text(row.get("title"), 300),
                "body": _text(row.get("body"), 20_000),
                "published": _text(row.get("published"), 80),
                "stamp": _text(row.get("stamp"), 40),
            })
        return {
            "enabled": bool(self.config.get("galnet_enabled", True)),
            "auto_rotate": bool(self.config.get("galnet_auto_rotate_enabled", True)),
            "rotation_seconds": max(4, min(60, _integer(self.config.get("galnet_rotation_seconds"), 7))),
            "refresh_minutes": max(5, min(240, _integer(self.config.get("galnet_refresh_minutes"), 30))),
            "status": _text(snapshot.get("status") or "waiting", 30).casefold(),
            "detail": _text(snapshot.get("detail") or "Awaiting Galnet relay", 180),
            "busy": bool(snapshot.get("busy")),
            "source": "Frontier Galnet",
            "updated_at": _text(snapshot.get("updated_at"), 80),
            "articles": articles,
        }

    def html_dashboard_snapshot(self):
        """Return one JSON-safe immutable dashboard state."""
        # Relevant journal reducers already invalidate and rebuild this packet.
        # Reusing it here prevents a quiet dashboard from deep-copying the
        # Codex/checkpoint state several times per second merely to update its
        # session clock.
        intelligence = getattr(self, "_latest_exploration_intelligence", None)
        if intelligence is None:
            try:
                intelligence = self._exploration_intelligence_snapshot(compact=True)
            except Exception:
                intelligence = {}
        route = self._html_dashboard_route()
        survey = self._html_dashboard_survey(intelligence)
        companion = getattr(self, "companion_state", None) or {}
        unsold_exploration = _integer(companion.get("unsold_exploration_cr"))
        unsold_bio = _integer(companion.get("unsold_bio_cr"))
        fuel_main = _number(getattr(self, "current_fuel_main", None))
        fuel_capacity = _number(getattr(self, "fuel_capacity_main", None))
        fuel_percent = (
            max(0.0, min(100.0, fuel_main * 100.0 / fuel_capacity))
            if fuel_main is not None and fuel_capacity and fuel_capacity > 0 else None
        )
        flight_state = _text(getattr(self, "hud_flight_state", "FLIGHT"), 60) or "FLIGHT"
        ship = getattr(self, "cmdr_ship", None) or {}
        ship_name = ship.get("ship_name") or ship.get("user_ship_name") or ship.get("ship") or "SHIP"
        if getattr(self, "current_docked", False):
            context = f"DOCKED // {getattr(self, 'current_station_name', None) or 'STATION'}"
        elif getattr(self, "current_landed", False):
            context = f"SURFACE // {getattr(self, 'current_body_name', None) or 'PLANETARY BODY'}"
        else:
            context = flight_state
        profile_name = (
            getattr(self, "cmdr_name", None)
            or self.config.get("active_commander_name")
            or "UNKNOWN"
        )
        sources = self._html_dashboard_sources()
        map_view = getattr(
            getattr(self, "exploration_window", None),
            "expedition_map_view", None,
        )
        atlas_url = ""
        if map_view is not None:
            atlas_url = _text(getattr(map_view, "embedded_url", ""), 512)
        dashboard_runtime = getattr(
            self.root, "_voidcompass_html_dashboard_runtime", None,
        )
        boot_active = bool(
            getattr(dashboard_runtime, "_boot", {}).get("active", False)
        )
        active_page = _text(
            getattr(self, "_html_dashboard_active_page", "overview") or "overview", 40,
        ).casefold()
        deck = getattr(self, "adaptive_command", None)
        try:
            adaptive = deck.status() if deck is not None else {}
        except Exception:
            adaptive = {}
        flight = {
            "system": _text(getattr(self, "current_sys", None) or "---", 160),
            "state": flight_state,
            "context": _text(context, 180),
            "ship": _text(ship_name, 120),
            "fuel_percent": round(fuel_percent, 1) if fuel_percent is not None else None,
            "fuel_detail": (
                f"{fuel_main:.1f} / {fuel_capacity:.1f} T"
                if fuel_main is not None and fuel_capacity else "AWAITING LOADOUT"
            ),
            "docked": bool(getattr(self, "current_docked", False)),
            "landed": bool(getattr(self, "current_landed", False)),
            "on_foot": bool(getattr(self, "current_on_foot", False)),
        }
        data = {
            "unsold_exploration": unsold_exploration,
            "unsold_bio": unsold_bio,
            "unsold_total": unsold_exploration + unsold_bio,
        }
        session = self._html_dashboard_session_pulse()
        intelligence_summary = self._html_dashboard_intelligence(intelligence)
        codex_hunt = self._html_dashboard_codex_hunt(intelligence_summary.get("region"))
        doctrine = _text(self.config.get("exploration_doctrine") or "balanced", 30).casefold()
        decision = explorer_decision(
            doctrine, survey, route, (intelligence or {}).get("actions") or (),
            flight, data, codex_hunt, adaptive,
        )
        preflight = self._html_exploration_preflight(route, flight, sources)
        configurable_modules = ("route", "session", "priorities", "codex", "feed")
        configured_order = self.config.get("dashboard_module_order") or configurable_modules
        module_order = [
            str(name) for name in configured_order
            if str(name) in configurable_modules
        ]
        module_order.extend(name for name in configurable_modules if name not in module_order)
        hidden_modules = [
            str(name) for name in (self.config.get("dashboard_hidden_modules") or [])
            if str(name) in configurable_modules
        ]
        raw_page_layouts = self.config.get("dashboard_page_layouts") or {}
        page_layouts = {}
        if isinstance(raw_page_layouts, dict):
            for page, containers in list(raw_page_layouts.items())[:32]:
                if not isinstance(containers, dict):
                    continue
                clean_containers = {}
                for container, panels in list(containers.items())[:32]:
                    if not isinstance(panels, list):
                        continue
                    clean_panels = [
                        _text(panel, 100) for panel in panels[:100]
                        if _text(panel, 100)
                    ]
                    clean_containers[_text(container, 100)] = list(dict.fromkeys(clean_panels))
                page_layouts[_text(page, 40).casefold()] = clean_containers
        return {
            "app": {"renderer": "html-command-deck", "platform": "windows"},
            "profile": {
                "key": _text(self.config.get("active_commander_profile"), 120),
                "commander": _text(profile_name, 120),
                "profile_label": f"{profile_name} · profile-aware exploration state",
            },
            "theme": self._html_dashboard_theme(),
            "adaptive": {
                "enabled": bool(self.config.get("adaptive_command_enabled", True)),
                "mode": _text(adaptive.get("mode") or "general", 30),
                "label": _text(adaptive.get("label") or "GENERAL FLIGHT", 60),
                "automatic": bool(adaptive.get("automatic", True)),
                "workspace": _text(adaptive.get("workspace") or "DASHBOARD", 40),
                "session": adaptive.get("session") or {},
            },
            "flight": flight,
            "survey": survey,
            "route": route,
            "traffic": {
                key: _integer((getattr(self, "system_traffic", None) or {}).get(key))
                for key in ("day", "week", "total")
            },
            "session": session,
            "data": data,
            "intelligence": intelligence_summary,
            "decision": decision,
            "preflight": preflight,
            "codex_hunt": codex_hunt,
            "galnet": self._html_dashboard_galnet(),
            "dashboard_layout": {
                "module_order": module_order,
                "hidden_modules": hidden_modules,
                "available_modules": [
                    {"id": "route", "label": "Route Horizon"},
                    {"id": "session", "label": "Session Pulse"},
                    {"id": "priorities", "label": "Field Priorities"},
                    {"id": "codex", "label": "Regional Codex Hunt"},
                    {"id": "feed", "label": "Live Exploration Feed"},
                ],
                "doctrine": decision.get("doctrine"),
                "doctrines": [
                    {"id": key, "label": label} for key, label in DOCTRINES.items()
                ],
            },
            "page_layouts": page_layouts,
            "priorities": self._html_dashboard_priorities(intelligence, route, survey),
            "expedition": self._html_dashboard_expedition(),
            "atlas": {
                "url": atlas_url,
                "ready": bool(atlas_url),
                "embedded": True,
            },
            "sources": sources,
            "events": self._html_dashboard_events(),
            # Specialist workspaces are built only while visible. This keeps
            # profile databases, engineering inventories and long histories
            # completely out of the boot and ordinary dashboard hot paths.
            "workspace": (
                {"page": active_page, "ready": False, "deferred": True}
                if boot_active or active_page not in _HTML_WORKSPACE_PAGES
                else self._html_workspace(active_page)
            ),
            # The Studio is an on-demand workspace, not boot-critical state.
            # Deferring its desktop/overlay catalogue keeps startup snapshots
            # small and prevents geometry inspection from competing with the
            # final journal-to-dashboard handoff.
            "overlay_studio": (
                {"deferred": True, "desktop": {}, "overlays": [], "presets": [], "options": {}}
                if boot_active else self._html_overlay_studio()
            ),
            "ui": {
                "flight_log_mode": bool(self.config.get("flight_log_mode_enabled", False)),
                "reduced_motion": bool(self.config.get("reduced_motion_enabled", False)),
                "page_request": {
                    "id": _integer(getattr(self, "_html_dashboard_page_request_seq", 0)),
                    "page": _text(getattr(self, "_html_dashboard_page_request", ""), 40),
                },
            },
        }

    def _route_to_html_workspace(self, page):
        """Redirect legacy callbacks to the authoritative HTML command deck."""
        if not bool(getattr(self.root, "_voidcompass_html_dashboard_enabled", False)):
            return False
        if not self._request_html_dashboard_page(page):
            return False
        self.hide_native_dashboard_tool()
        return True

    def _html_copy_text(self, value):
        value = str(value or "")
        if not value:
            return False
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.root.update_idletasks()
            return True
        except Exception:
            return False

    def _handle_html_workspace_command(self, payload):
        """Validate and apply commands from fully HTML specialist pages."""
        page = _text(payload.get("page"), 40).casefold()
        operation = _text(payload.get("operation"), 60).casefold()
        if page not in _HTML_WORKSPACE_PAGES:
            return False
        changed = False

        if operation == "copy":
            return self._html_copy_text(_text(payload.get("text"), 20000))

        if page == "explore":
            if operation in {"survey_pin", "survey_skip", "survey_complete", "survey_reset"}:
                system = _text(payload.get("system") or getattr(self, "current_sys", ""), 140)
                if not system:
                    return False
                states = dict(self.config.get("stellar_survey_queue_state") or {})
                system_key = system.casefold()
                state = dict(states.get(system_key) or {})
                if operation == "survey_reset":
                    states.pop(system_key, None)
                else:
                    body_key = _text(payload.get("body_key"), 220)
                    if not body_key:
                        return False
                    buckets = {
                        name: {str(value) for value in state.get(name) or ()}
                        for name in ("pinned", "skipped", "completed")
                    }
                    target = {
                        "survey_pin": "pinned",
                        "survey_skip": "skipped",
                        "survey_complete": "completed",
                    }[operation]
                    enabled = body_key not in buckets[target]
                    for values in buckets.values():
                        values.discard(body_key)
                    if enabled:
                        buckets[target].add(body_key)
                    states[system_key] = {
                        name: sorted(values) for name, values in buckets.items()
                    }
                self.config["stellar_survey_queue_state"] = dict(list(states.items())[-50:])
                self._persist_config()
                self._schedule_html_dashboard_publish(immediate=True)
                return True
            manager = getattr(self, "waypoint_manager", None)
            if manager is None:
                return False
            index = _integer(payload.get("index"), -1)
            if operation == "copy_next":
                return self._html_copy_text(manager.get_next_waypoint(getattr(self, "current_sys", "")))
            if operation == "copy_waypoint":
                if not 0 <= index < len(manager.waypoints):
                    return False
                return self._html_copy_text(manager.waypoints[index].get("name"))
            if operation == "add_waypoint":
                name = _text(payload.get("name"), 140)
                if not name:
                    return False
                coords = getattr(self, "current_coords", None) if name.casefold() == str(getattr(self, "current_sys", "")).casefold() else None
                manager.add_waypoint(name, coords, _text(payload.get("note"), 1000) or None)
                changed = True
            elif operation == "edit_waypoint":
                if not 0 <= index < len(manager.waypoints):
                    return False
                current_row = manager.waypoints[index]
                name = _text(payload.get("name") or current_row.get("name"), 140)
                if not name:
                    return False
                changed = manager.edit_waypoint(
                    index, name, current_row.get("coords"),
                    _text(payload.get("note"), 1000) or None,
                )
            elif operation == "mark_waypoint":
                if not 0 <= index < len(manager.waypoints):
                    return False
                manager.waypoints[index]["visited"] = bool(payload.get("visited"))
                changed = manager.save()
            elif operation == "move_waypoint":
                offset = max(-1, min(1, _integer(payload.get("offset"))))
                changed = manager.move_up(index) if offset < 0 else manager.move_down(index)
            elif operation == "delete_waypoint":
                if not bool(payload.get("confirmed")) or not 0 <= index < len(manager.waypoints):
                    return False
                before = len(manager.waypoints)
                manager.remove_waypoint(index)
                changed = len(manager.waypoints) < before
            elif operation == "clear_waypoints":
                if not bool(payload.get("confirmed")):
                    return False
                manager.clear()
                changed = True
            elif operation == "set_auto_copy":
                self.config["auto_copy_waypoint"] = bool(payload.get("enabled"))
                self._persist_config()
                changed = True
            elif operation == "neutron_copy":
                tool = self._html_profile_transient("_html_explore_tool_state", {})
                names = [
                    _text(row.get("system"), 140) for row in ((tool.get("route") or {}).get("waypoints") or [])
                    if isinstance(row, dict) and _text(row.get("system"), 140)
                ]
                return self._html_copy_text("\n".join(names))
            elif operation == "neutron_clear":
                tool = self._html_profile_transient("_html_explore_tool_state", {})
                tool.update({"status": "ready", "detail": "Route result cleared.", "route": None})
                changed = True
            elif operation == "neutron_import":
                tool = self._html_profile_transient("_html_explore_tool_state", {})
                rows = (tool.get("route") or {}).get("waypoints") or []
                existing = {str(row.get("name") or "").casefold() for row in manager.waypoints}
                added = 0
                for row in rows:
                    name = _text(row.get("system") if isinstance(row, dict) else "", 140)
                    if not name or name.casefold() in existing:
                        continue
                    manager.waypoints.append({"name": name, "coords": None, "note": "Spansh neutron route"})
                    existing.add(name.casefold())
                    added += 1
                changed = bool(added and manager.save())
                if added:
                    tool["detail"] = f"Imported {added:,} new systems into the profile waypoint route."
            elif operation == "neutron_plot":
                from_system = _text(payload.get("from") or getattr(self, "current_sys", ""), 140)
                to_system = _text(payload.get("to"), 140)
                jump_range = _number(payload.get("range"))
                efficiency = max(1, min(100, _integer(payload.get("efficiency"), 60)))
                multiplier = 6 if _integer(payload.get("multiplier"), 4) == 6 else 4
                if not from_system or not to_system or jump_range is None or jump_range <= 0:
                    return False
                profile = get_active_profile(self.config)
                generation = time.time_ns()
                tool = self._html_profile_transient(
                    "_html_explore_tool_state", {"status": "ready", "detail": "", "route": None},
                )
                tool.update({
                    "generation": generation, "status": "working",
                    "detail": f"Spansh is plotting {from_system} to {to_system}…", "route": None,
                })
                self.config["system_plotter_form"] = {
                    "from": from_system, "to": to_system, "range": jump_range,
                    "efficiency": efficiency, "supercharge_multiplier": multiplier,
                }
                self._persist_config()
                self.add_event_feed_entry("ROUTE", f"Neutron plot started: {from_system} to {to_system}", severity="INFO")
                self._schedule_html_dashboard_publish(immediate=True)

                def worker():
                    try:
                        result = neutron_route(
                            from_system, to_system, jump_range, efficiency,
                            supercharge_multiplier=multiplier,
                        )
                        error = None
                    except Exception as exc:
                        result, error = None, exc

                    def finish():
                        active = self._html_profile_transient("_html_explore_tool_state", {})
                        if active.get("profile") != profile or active.get("generation") != generation:
                            return
                        if error is not None:
                            detail = str(error) if isinstance(error, SpanshError) else f"Unexpected route error: {error}"
                            active.update({"status": "failed", "detail": detail, "route": None})
                            self.add_event_feed_entry("ROUTE", f"Neutron plot failed: {detail}", severity="WARN")
                        else:
                            count = len(result.get("waypoints") or [])
                            active.update({"status": "ready", "detail": f"Route ready · {count:,} waypoints.", "route": result})
                            self.add_event_feed_entry("ROUTE", f"Neutron plot ready: {count:,} waypoints", severity="INFO")
                        self._schedule_html_dashboard_publish(immediate=True)

                    self._ui_post(finish, key="html-neutron-route")

                threading.Thread(target=worker, name="HtmlSpanshNeutron", daemon=True).start()
                return True

        elif page == "profile":
            companion = getattr(self, "companion_state", None) or {}
            if operation == "open_folder":
                return bool(open_path(get_profile_dir(get_active_profile(self.config))))
            if operation == "open_edsy":
                loadout = companion.get("loadout")
                if not loadout:
                    return False
                webbrowser.open_new_tab(companion_features.edsy_url(loadout))
                return True
            if operation == "copy_slef":
                loadout = companion.get("loadout")
                return bool(loadout and self._html_copy_text(companion_features.slef(loadout)))
            if operation == "backup":
                target = Path(str(payload.get("path") or "")).expanduser()
                if not target.is_dir():
                    return False
                profile_key = get_active_profile(self.config)
                destination = target / f"{profile_key}_{time.strftime('%Y%m%d_%H%M%S')}"
                snapshot_profile(get_profile_dir(profile_key), destination)
                self.add_event_feed_entry("PROFILE", f"Profile backup created: {destination.name}", severity="INFO")
                return True
            if operation == "restore":
                source = Path(str(payload.get("path") or "")).expanduser()
                valid, _detail = validate_backup(source)
                if not valid or not bool(payload.get("confirmed")):
                    return False
                schedule_restore(source, get_active_profile(self.config))
                self.add_event_feed_entry("PROFILE", "Profile restore scheduled for next start", severity="WARN")
                return True

        elif page == "chronicle":
            if operation != "export_replay":
                return False
            workspace = self._html_chronicle_workspace()
            sessions = workspace.get("sessions") or []
            replay = workspace.get("replay") or {}
            index = _integer(payload.get("session_index"), 0)
            if not 0 <= index < len(sessions):
                return False
            session = sessions[index]
            replay_session = (replay.get("sessions") or [{}])[index]
            title = _text(
                f"{session.get('start_system') or 'Expedition'} to "
                f"{session.get('end_system') or session.get('start_system') or 'Unknown'}",
                180,
            )
            try:
                from tkinter import filedialog
                default_day = str(session.get("started") or "expedition")[:10].replace("-", "")
                path = filedialog.asksaveasfilename(
                    parent=self.root,
                    title="Export Interactive Expedition Replay",
                    defaultextension=".html",
                    filetypes=[("Interactive HTML", "*.html")],
                    initialfile=f"VoidCompass-Replay-{default_day}.html",
                )
                if not path:
                    return True
                document = replay_export_html(
                    title,
                    getattr(self, "cmdr_name", None) or self.config.get("active_commander_name"),
                    replay,
                    replay_session,
                )
                Path(path).write_text(document, encoding="utf-8")
            except Exception as exc:
                logging.warning("Expedition replay export failed: %s", exc)
                return False
            self.add_event_feed_entry(
                "EXPEDITION", f"Interactive replay exported: {Path(path).name}", severity="INFO",
            )
            return True

        elif page == "mission":
            manager = getattr(self, "expedition_manager", None)
            if manager is None:
                return False
            expedition_id = _text(payload.get("expedition_id"), 50)
            if operation == "create":
                created = manager.create(
                    _text(payload.get("name"), 100),
                    description=_text(payload.get("description"), 1000),
                    start_system=_text(payload.get("start_system") or getattr(self, "current_sys", ""), 120),
                    destination=_text(payload.get("destination"), 120),
                    return_system=_text(payload.get("return_system"), 120),
                )
                changed = bool(created)
            elif operation == "status":
                changed = manager.set_status(expedition_id, payload.get("status"))
            elif operation == "delete":
                changed = bool(payload.get("confirmed") and manager.delete(expedition_id))
            elif operation == "add_objective":
                changed = bool(manager.add_objective(
                    expedition_id,
                    _text(payload.get("kind") or "manual", 50),
                    target=_text(payload.get("target"), 200),
                    system=_text(payload.get("system"), 120),
                    body=_text(payload.get("body"), 160),
                    count=max(1, _integer(payload.get("count"), 1)),
                    notes=_text(payload.get("notes"), 1000),
                ))
            elif operation == "toggle_objective":
                changed = manager.toggle_objective(expedition_id, _text(payload.get("objective_id"), 50))
            elif operation == "remove_objective":
                changed = bool(payload.get("confirmed") and manager.remove_objective(
                    expedition_id, _text(payload.get("objective_id"), 50),
                ))

        elif page == "ground":
            if operation == "set":
                lat = _number(payload.get("lat"))
                lon = _number(payload.get("lon"))
                if (
                    lat is None or lon is None
                    or not math.isfinite(lat) or not math.isfinite(lon)
                    or not -90 <= lat <= 90
                ):
                    return False
                normalizer = getattr(self, "_normalize_lon", None)
                lon = normalizer(lon) if callable(normalizer) else ((lon + 180) % 360) - 180
                self.target_lat = lat
                self.target_lon = lon
                self.target_latlon_active = True
                self.config.update({
                    "ground_target_active": True,
                    "ground_target_lat": lat,
                    "ground_target_lon": lon,
                })
                self._save_config_file()
                changed = True
            elif operation == "set_current":
                if getattr(self, "current_latitude", None) is None or getattr(self, "current_longitude", None) is None:
                    return False
                self.target_lat = float(self.current_latitude)
                self.target_lon = float(self.current_longitude)
                self.target_latlon_active = True
                self.config.update({
                    "ground_target_active": True,
                    "ground_target_lat": self.target_lat,
                    "ground_target_lon": self.target_lon,
                })
                self._save_config_file()
                changed = True
            elif operation == "return_ship":
                ship = getattr(self, "surface_ship_position", None)
                if not isinstance(ship, dict):
                    return False
                self.target_lat = float(ship["lat"])
                self.target_lon = float(ship["lon"])
                self.target_latlon_active = True
                self.config.update({
                    "ground_target_active": True,
                    "ground_target_lat": self.target_lat,
                    "ground_target_lon": self.target_lon,
                })
                self._save_config_file()
                changed = True
            elif operation == "clear":
                self.clear_ground_target()
                changed = True
            elif operation == "clear_trail":
                self.clear_surface_trail()
                changed = True
            elif operation == "toggle_popup":
                self.toggle_ground_popup()
                changed = True
            elif operation == "add_pin":
                specialist = getattr(self, "specialist_engine", None)
                if specialist is None:
                    return False
                try:
                    changed = bool(specialist.add_pin(
                        _text(payload.get("label") or "Field marker", 160), "waypoint",
                    ))
                except ValueError:
                    return False
            elif operation == "remove_pin":
                specialist = getattr(self, "specialist_engine", None)
                changed = bool(
                    specialist is not None
                    and specialist.remove_pin(_text(payload.get("pin_id"), 80))
                )
            if changed:
                self.update_ground_target_ui()

        elif page == "mining":
            engine = getattr(self, "specialist_engine", None)
            if engine is None:
                return False
            if operation == "save_plan":
                engine.configure_mining(
                    _text(payload.get("target"), 100),
                    _number(payload.get("minimum"), 20),
                    _integer(payload.get("cargo_goal")),
                    _text(payload.get("method") or "auto", 30),
                )
                changed = True
            elif operation == "start_run":
                changed = engine.start_mining({
                    "system": getattr(self, "current_sys", None),
                    "body": getattr(self, "current_body_name", None),
                })
            elif operation == "end_run":
                changed = engine.end_mining("manual")
            elif operation == "ring_search":
                reference = _text(payload.get("reference") or getattr(self, "current_sys", ""), 140)
                material = _text(payload.get("material"), 100)
                ring_type = _text(payload.get("ring_type"), 50)
                max_distance = max(1, min(5000, _integer(payload.get("range"), 300)))
                if not reference:
                    return False
                profile = get_active_profile(self.config)
                generation = time.time_ns()
                tool = self._html_profile_transient("_html_mining_tool_state", {})
                tool.update({
                    "ring_generation": generation, "ring_status": "working",
                    "ring_detail": f"Searching ring intelligence near {reference}…",
                    "ring_results": [],
                })
                self._schedule_html_dashboard_publish(immediate=True)

                def worker():
                    try:
                        store = self._html_mining_store()
                        current = str(getattr(self, "current_sys", "") or "")
                        coords = getattr(self, "current_coords", None) if reference.casefold() == current.casefold() else None
                        local_rows = store.search_hotspots(
                            material=material or None, ring_type=ring_type or None,
                            reference_coords=coords,
                            max_distance=max_distance if coords else None,
                            limit=250,
                        )
                        if not coords:
                            local_rows = [
                                row for row in local_rows
                                if str(row.get("system_name") or "").casefold() == reference.casefold()
                            ]
                        remote_rows = search_spansh_rings(
                            reference, material=material or None,
                            ring_type=ring_type or None, max_results=200,
                            max_distance=max_distance,
                        )
                        combined = []
                        seen = set()
                        for source, rows in (("COMMANDER DSS", local_rows), ("SPANSH", remote_rows)):
                            for row in rows:
                                if not isinstance(row, dict):
                                    continue
                                clean = {
                                    "system": _text(row.get("system_name"), 140),
                                    "body": _text(row.get("body_name"), 180),
                                    "material": _text(row.get("material_name") or material, 100),
                                    "hotspots": _integer(row.get("hotspot_count")),
                                    "ring_type": _text(row.get("ring_type"), 60),
                                    "distance": _number(row.get("distance_ly")),
                                    "arrival": _number(row.get("ls_distance")),
                                    "reserve": _text(row.get("reserve_level"), 60),
                                    "updated": row.get("updated_at") or row.get("scan_date"),
                                    "source": source,
                                    "body_id64": row.get("body_id64"),
                                }
                                key = (
                                    clean["system"].casefold(), clean["body"].casefold(),
                                    clean["material"].casefold(),
                                )
                                if not clean["system"] or key in seen:
                                    continue
                                seen.add(key)
                                combined.append(clean)
                        combined.sort(key=lambda row: (
                            row.get("distance") is None,
                            row.get("distance") if row.get("distance") is not None else 0,
                            -_integer(row.get("hotspots")),
                        ))
                        result, error = combined[:250], None
                    except Exception as exc:
                        result, error = [], exc

                    def finish():
                        active = self._html_profile_transient("_html_mining_tool_state", {})
                        if active.get("profile") != profile or active.get("ring_generation") != generation:
                            return
                        if error:
                            active.update({"ring_status": "failed", "ring_detail": str(error), "ring_results": []})
                        else:
                            active.update({
                                "ring_status": "ready", "ring_results": result,
                                "ring_detail": f"Found {len(result):,} ring records near {reference}.",
                            })
                        self._schedule_html_dashboard_publish(immediate=True)

                    self._ui_post(finish, key="html-mining-rings")

                threading.Thread(target=worker, name="HtmlMiningRings", daemon=True).start()
                return True
            elif operation == "buyer_search":
                reference = _text(payload.get("reference") or getattr(self, "current_sys", ""), 140)
                commodity = _text(payload.get("commodity"), 100)
                quantity = max(1, min(100000, _integer(payload.get("quantity"), 1)))
                max_distance = max(1, min(5000, _integer(payload.get("range"), 500)))
                max_ls = max(1, min(10000000, _integer(payload.get("max_ls"), 10000)))
                if not reference or not commodity:
                    return False
                profile = get_active_profile(self.config)
                generation = time.time_ns()
                tool = self._html_profile_transient("_html_mining_tool_state", {})
                tool.update({
                    "buyer_generation": generation, "buyer_status": "working",
                    "buyer_detail": f"Finding {commodity} demand around {reference}…",
                    "buyer_results": [],
                })
                self._schedule_html_dashboard_publish(immediate=True)

                def worker():
                    try:
                        rows = search_spansh_buyers(
                            commodity, reference_system=reference,
                            max_distance=max_distance, max_results=200,
                            exclude_carriers=bool(payload.get("exclude_carriers", True)),
                            quantity=quantity, large_pad=bool(payload.get("large_pad")),
                            max_ls=max_ls, min_demand=quantity,
                        )
                        result = [
                            {
                                "system": _text(row.get("system_name"), 140),
                                "station": _text(row.get("station_name"), 180),
                                "station_type": _text(row.get("station_type"), 80),
                                "distance": _number(row.get("distance_ly")),
                                "arrival": _number(row.get("ls_distance")),
                                "price": _integer(row.get("price")),
                                "demand": _integer(row.get("demand")),
                                "updated": row.get("updated_at"),
                                "large_pad": bool(row.get("large_pad")),
                                "planetary": bool(row.get("planetary")),
                                "market_id": row.get("market_id"),
                            }
                            for row in rows[:200] if isinstance(row, dict)
                        ]
                        error = None
                    except Exception as exc:
                        result, error = [], exc

                    def finish():
                        active = self._html_profile_transient("_html_mining_tool_state", {})
                        if active.get("profile") != profile or active.get("buyer_generation") != generation:
                            return
                        if error:
                            active.update({"buyer_status": "failed", "buyer_detail": str(error), "buyer_results": []})
                        else:
                            active.update({
                                "buyer_status": "ready", "buyer_results": result,
                                "buyer_detail": f"Found {len(result):,} markets with demand for {quantity:,} T of {commodity}.",
                            })
                        self._schedule_html_dashboard_publish(immediate=True)

                    self._ui_post(finish, key="html-mining-buyers")

                threading.Thread(target=worker, name="HtmlMiningBuyers", daemon=True).start()
                return True
            elif operation in {"ring_copy", "ring_open", "ring_bookmark"}:
                tool = self._html_profile_transient("_html_mining_tool_state", {})
                index = _integer(payload.get("result_index"), -1)
                rows = tool.get("ring_results") or []
                if not 0 <= index < len(rows):
                    return False
                row = rows[index]
                if operation == "ring_copy":
                    return self._html_copy_text(row.get("system"))
                if operation == "ring_open":
                    body_id64 = row.get("body_id64")
                    webbrowser.open_new_tab(
                        f"https://spansh.co.uk/body/{body_id64}" if body_id64 else "https://spansh.co.uk/bodies"
                    )
                    return True
                self._html_mining_store().add_bookmark(
                    row.get("system"), row.get("body"), row.get("material"),
                    f"{row.get('ring_type') or 'Ring'} · {row.get('reserve') or 'reserve unknown'}",
                )
                changed = True
            elif operation in {"buyer_copy", "buyer_open"}:
                tool = self._html_profile_transient("_html_mining_tool_state", {})
                index = _integer(payload.get("result_index"), -1)
                rows = tool.get("buyer_results") or []
                if not 0 <= index < len(rows):
                    return False
                row = rows[index]
                if operation == "buyer_copy":
                    return self._html_copy_text(row.get("system"))
                market_id = row.get("market_id")
                webbrowser.open_new_tab(
                    f"https://spansh.co.uk/station/{market_id}" if market_id else "https://spansh.co.uk/stations"
                )
                return True
            elif operation == "delete_bookmark":
                if not payload.get("confirmed"):
                    return False
                changed = self._html_mining_store().remove_bookmark(
                    _integer(payload.get("bookmark_id")),
                )

        elif page == "engineering":
            materials = getattr(self, "engineer_materials", None)
            if not isinstance(materials, dict):
                return False
            name = _text(payload.get("name"), 180)
            if operation == "pin" and name in engineering_data.BLUEPRINTS:
                grade = max(1, min(5, _integer(payload.get("grade"), 5)))
                current_grade = max(0, min(grade - 1, _integer(payload.get("current_grade"), 0)))
                quantity = max(1, min(99, _integer(payload.get("quantity"), 1)))
                pins = [row for row in (materials.get("pinned_blueprints") or []) if row.get("name") != name]
                pins.append({"name": name, "grade": grade, "target_grade": grade, "current_grade": current_grade, "quantity": quantity})
                materials["pinned_blueprints"] = pins
                changed = self._save_engineer_materials(materials)
            elif operation == "unpin":
                pins = list(materials.get("pinned_blueprints") or [])
                materials["pinned_blueprints"] = [row for row in pins if row.get("name") != name]
                changed = len(materials["pinned_blueprints"]) != len(pins) and self._save_engineer_materials(materials)
            elif operation == "odyssey_pin" and name in engineering_data.ODYSSEY_BLUEPRINTS:
                quantity = max(1, min(99, _integer(payload.get("quantity"), 1)))
                goals = [row for row in (materials.get("odyssey_goals") or []) if row.get("name") != name]
                goals.append({"name": name, "quantity": quantity})
                materials["odyssey_goals"] = goals
                changed = self._save_engineer_materials(materials)
            elif operation == "odyssey_unpin":
                goals = list(materials.get("odyssey_goals") or [])
                materials["odyssey_goals"] = [row for row in goals if row.get("name") != name]
                changed = len(materials["odyssey_goals"]) != len(goals) and self._save_engineer_materials(materials)

        elif page == "carrier":
            tracker = getattr(self, "carrier_tracker", None)
            if tracker is None:
                return False
            index = _integer(payload.get("index"), -1)
            if operation == "copy_next":
                row = tracker.next_expedition_stop()
                return bool(row and self._html_copy_text(row.get("system")))
            if operation == "mark":
                changed = tracker.set_expedition_stop_visited(index, bool(payload.get("visited")))
            elif operation == "delete_stop":
                changed = bool(payload.get("confirmed") and tracker.delete_expedition_stop(index))
            elif operation == "move_stop":
                changed = tracker.move_expedition_stop(index, max(-1, min(1, _integer(payload.get("offset")))))
            elif operation == "add_stop":
                changed = tracker.add_expedition_stop(_text(payload.get("system"), 140), index if index >= 0 else None)
            elif operation == "save_route":
                systems = [
                    _text(row, 140) for row in (payload.get("systems") or [])
                    if _text(row, 140)
                ]
                tracker.set_expedition(
                    _text(payload.get("name") or "Carrier expedition", 140),
                    systems,
                    reserve_fuel=max(0, min(25000, _integer(payload.get("reserve"), 200))),
                )
                changed = True
            elif operation == "update_route_details":
                tracker.update_expedition_details(
                    _text(payload.get("name") or "Carrier expedition", 140),
                    max(0, min(25000, _integer(payload.get("reserve"), 200))),
                )
                changed = True
            elif operation == "clear_route":
                if not bool(payload.get("confirmed")):
                    return False
                tracker.clear_expedition()
                tool = self._html_profile_transient("_html_carrier_tool_state", {})
                tool.update({"route_status": "ready", "route_detail": "Carrier route deleted."})
                changed = True
            elif operation in {"save_discord_details", "discord_status"}:
                destination = _text(payload.get("destination"), 240)
                note = _text(payload.get("note"), 500)
                tracker.set_destination_note(destination)
                tracker.set_note(note)
                tool = self._html_profile_transient("_html_carrier_tool_state", {})
                if operation == "save_discord_details":
                    tool.update({
                        "discord_status": "ready",
                        "discord_detail": "Discord destination and operator note saved.",
                    })
                    changed = True
                else:
                    try:
                        departure = _local_departure_timestamp(payload.get("departure"))
                    except ValueError as exc:
                        tool.update({"discord_status": "failed", "discord_detail": str(exc)})
                        self._schedule_html_dashboard_publish(immediate=True)
                        return False
                    result = tracker.send_status_update(departure_ts=departure)
                    if isinstance(result, tuple):
                        sent, error = bool(result[0]), result[1]
                    else:
                        sent, error = bool(result), None
                    detail = (
                        "Carrier status queued for Discord."
                        if sent else (error or "Carrier Discord webhook is not configured.")
                    )
                    tool.update({
                        "discord_status": "ready" if sent else "failed",
                        "discord_detail": detail,
                    })
                    self.add_event_feed_entry(
                        "CARRIER", detail, severity="INFO" if sent else "WARN",
                    )
                    self._schedule_html_dashboard_publish(immediate=True)
                    return sent
            elif operation == "open_spansh_result":
                url = str(tracker.carrier_data.get("expedition_spansh_url") or "").strip()
                if not url:
                    return False
                webbrowser.open_new_tab(url)
                return True
            elif operation in {"plot_route", "import_route"}:
                carrier = tracker.carrier_data
                profile = get_active_profile(self.config)
                generation = time.time_ns()
                name = _text(payload.get("name") or carrier.get("expedition_name") or "Carrier route", 140)
                reserve = max(0, min(25000, _integer(payload.get("reserve"), 200)))
                tool = self._html_profile_transient(
                    "_html_carrier_tool_state", {"route_status": "ready", "route_detail": ""},
                )
                tool.update({
                    "route_generation": generation, "route_status": "working",
                    "route_detail": "Spansh is resolving systems and calculating Carrier jumps…"
                    if operation == "plot_route" else "Importing the completed Spansh Carrier result…",
                })
                self._schedule_html_dashboard_publish(immediate=True)

                if operation == "plot_route":
                    source = _text(carrier.get("system"), 140)
                    destinations = [
                        _text(row, 140) for row in (payload.get("systems") or [])
                        if _text(row, 140) and _text(row, 140).casefold() != source.casefold()
                    ]
                    if not source or not destinations:
                        tool.update({"route_status": "failed", "route_detail": "Carrier location and at least one destination are required."})
                        self._schedule_html_dashboard_publish(immediate=True)
                        return False
                    total, free = carrier.get("space_total"), carrier.get("space_free")
                    try:
                        used = max(0, int(total) - int(free))
                    except (TypeError, ValueError):
                        used = 0
                    engine = getattr(self, "specialist_engine", None)
                    try:
                        specialist = engine.carrier_snapshot(carrier) if engine is not None else {}
                    except Exception:
                        specialist = {}
                    inventory = specialist.get("inventory") or {}
                    tritium = inventory.get("tritium") or {}
                    stored = _integer(tritium.get("count") if isinstance(tritium, dict) else tritium)
                    try:
                        tank = max(0, min(1000, int(carrier.get("fuel_level"))))
                    except (TypeError, ValueError):
                        tank = None
                    source_label = str(specialist.get("inventory_source") or "").casefold()
                    manifest_known = source_label not in {"", "not supplied", "no manifest baseline"}

                    def request():
                        return fleet_carrier_route(
                            source, destinations, source_id64=carrier.get("system_address"),
                            used_capacity=used, carrier_type=carrier.get("carrier_type") or "fleet",
                            calculate_starting_fuel=not (tank is not None and manifest_known),
                            tritium_fuel=tank or 0, tritium_stored=stored,
                        )
                else:
                    reference = _text(payload.get("reference"), 500)
                    job = fleet_carrier_job_id(reference)
                    if not job:
                        tool.update({"route_status": "failed", "route_detail": "Paste a completed Spansh Fleet Carrier result URL or UUID."})
                        self._schedule_html_dashboard_publish(immediate=True)
                        return False

                    def request():
                        return import_fleet_carrier_route(job)

                self.add_event_feed_entry("CARRIER", "Carrier route calculation started", severity="INFO")

                def worker():
                    try:
                        result, error = request(), None
                    except Exception as exc:
                        result, error = None, exc

                    def finish():
                        active = self._html_profile_transient("_html_carrier_tool_state", {})
                        if active.get("profile") != profile or active.get("route_generation") != generation:
                            return
                        if error is not None:
                            detail = str(error) if isinstance(error, SpanshError) else f"Unexpected route error: {error}"
                            active.update({"route_status": "failed", "route_detail": detail})
                            self.add_event_feed_entry("CARRIER", f"Carrier route failed: {detail}", severity="WARN")
                        else:
                            tracker.set_spansh_expedition(name, result, reserve)
                            jumps = max(0, len(result.get("jumps") or []) - 1)
                            active.update({
                                "route_status": "ready",
                                "route_detail": f"Route saved · {jumps:,} jumps · {_number(result.get('total_distance_ly'), 0):,.1f} LY · {_integer(result.get('fuel_required_t')):,} T.",
                            })
                            self.add_event_feed_entry("CARRIER", f"Carrier route ready: {jumps:,} jumps", severity="INFO")
                        self._schedule_html_dashboard_publish(immediate=True)

                    self._ui_post(finish, key="html-carrier-route")

                threading.Thread(target=worker, name="HtmlSpanshCarrier", daemon=True).start()
                return True
            elif operation == "tritium_search":
                reference = _text(payload.get("reference") or tracker.carrier_data.get("system"), 140)
                max_distance = _number(payload.get("range"), 300)
                if not reference or max_distance is None or max_distance <= 0:
                    return False
                profile = get_active_profile(self.config)
                generation = time.time_ns()
                tool = self._html_profile_transient("_html_carrier_tool_state", {})
                tool.update({
                    "tritium_generation": generation, "tritium_status": "working",
                    "tritium_detail": f"Searching known Tritium rings within {max_distance:,.0f} LY of {reference}…",
                    "tritium_results": [],
                })
                self._schedule_html_dashboard_publish(immediate=True)

                def worker():
                    try:
                        rows = search_spansh_rings(
                            reference, material="Tritium", max_results=200,
                            max_distance=max_distance,
                        )
                        error = None
                    except Exception as exc:
                        rows, error = [], exc

                    def finish():
                        active = self._html_profile_transient("_html_carrier_tool_state", {})
                        if active.get("profile") != profile or active.get("tritium_generation") != generation:
                            return
                        if error is not None:
                            active.update({"tritium_status": "failed", "tritium_detail": str(error), "tritium_results": []})
                        else:
                            clean = []
                            for row in rows:
                                if not isinstance(row, dict):
                                    continue
                                clean.append({
                                    "system": _text(row.get("system_name"), 140),
                                    "body": _text(row.get("body_name"), 160),
                                    "hotspots": _integer(row.get("hotspot_count")),
                                    "ring_type": _text(row.get("ring_type"), 60),
                                    "distance": _number(row.get("distance_ly")),
                                    "arrival": _number(row.get("ls_distance")),
                                    "reserve": _text(row.get("reserve_level"), 60),
                                    "body_id64": row.get("body_id64"),
                                })
                            active.update({
                                "tritium_status": "ready", "tritium_results": clean,
                                "tritium_detail": f"Found {len(clean):,} known Tritium ring signals near {reference}.",
                            })
                        self._schedule_html_dashboard_publish(immediate=True)

                    self._ui_post(finish, key="html-carrier-tritium")

                threading.Thread(target=worker, name="HtmlTritiumSearch", daemon=True).start()
                return True
            elif operation in {"tritium_copy", "tritium_add", "tritium_open"}:
                tool = self._html_profile_transient("_html_carrier_tool_state", {})
                result_index = _integer(payload.get("result_index"), -1)
                rows = tool.get("tritium_results") or []
                if not 0 <= result_index < len(rows):
                    return False
                row = rows[result_index]
                system = _text(row.get("system"), 140)
                if operation == "tritium_copy":
                    return self._html_copy_text(system)
                if operation == "tritium_add":
                    changed = tracker.add_expedition_stop(system)
                else:
                    body_id64 = row.get("body_id64")
                    webbrowser.open_new_tab(
                        f"https://spansh.co.uk/body/{body_id64}" if body_id64 is not None
                        else "https://spansh.co.uk/bodies"
                    )
                    return True

        elif page == "recon":
            deep = getattr(self, "deep_survey", None)
            if deep is None:
                return False
            if operation == "save":
                report = self._html_recon_workspace().get("report") or {}
                changed = bool(deep.save_candidate(report, notes=_text(payload.get("notes"), 1000)))
                if changed:
                    manager = getattr(self, "expedition_manager", None)
                    if manager is not None:
                        manager.observe_recon(report.get("system"), report.get("score"))
            elif operation == "dismiss_revisit":
                deep.dismiss_revisit(_text(payload.get("system"), 140))
                changed = True
            elif operation == "delete_candidate":
                changed = bool(payload.get("confirmed") and deep.remove_candidate(_text(payload.get("system"), 140)))
            elif operation == "copy_report":
                return self._html_copy_text(deep.recon_markdown(self._html_recon_workspace().get("report") or {}))

        elif page == "achievements":
            engine = getattr(self, "achievement_engine", None)
            if engine is None:
                return False
            achievement_id = _text(payload.get("achievement_id"), 100)
            if operation == "manual_unlock":
                changed = engine.manual_unlock(achievement_id)
            elif operation == "reset":
                changed = bool(payload.get("confirmed") and engine.reset_achievement(achievement_id))
            elif operation == "set_enabled":
                engine.set_options(enabled=bool(payload.get("enabled")))
                changed = True
            elif operation == "set_notifications":
                self.config["achievement_notifications_enabled"] = bool(
                    payload.get("enabled")
                )
                self._persist_config()
                changed = True

        elif page == "settings":
            if operation == "save_theme":
                name = _text(payload.get("name"), 80)
                if not name or name in themes.BUILTIN_THEMES:
                    return False
                current_name, current_palette = themes.resolve_theme(
                    self.config.get("ui_theme_name"), self.config.get("ui_custom_themes") or {},
                )
                supplied = payload.get("colors") or {}
                if not isinstance(supplied, dict):
                    return False
                palette = themes.normalize_theme(supplied, base=current_palette)
                custom = dict(self.config.get("ui_custom_themes") or {})
                custom[name] = palette
                self.config["ui_custom_themes"] = custom
                self.config["ui_theme_name"] = name
                self._persist_config()
                self._apply_active_profile_theme()
                changed = True
            elif operation == "delete_theme":
                name = _text(payload.get("name"), 80)
                custom = dict(self.config.get("ui_custom_themes") or {})
                if not bool(payload.get("confirmed")) or name not in custom:
                    return False
                custom.pop(name, None)
                self.config["ui_custom_themes"] = custom
                if self.config.get("ui_theme_name") == name:
                    self.config["ui_theme_name"] = themes.DEFAULT_THEME_NAME
                self._persist_config()
                self._apply_active_profile_theme()
                changed = True
            elif operation in {"test_edsm", "test_discord"}:
                profile = get_active_profile(self.config)
                generation = time.time_ns()
                tool = self._html_profile_transient("_html_settings_tool_state", {})
                label = "EDSM credentials" if operation == "test_edsm" else "Discord webhook"
                tool.update({"generation": generation, "status": "working", "detail": f"Testing {label}…"})
                self._schedule_html_dashboard_publish(immediate=True)

                def worker():
                    try:
                        if operation == "test_edsm":
                            import requests
                            from version import APP_VERSION
                            commander = _text(payload.get("commander"), 120)
                            api_key = _text(payload.get("api_key"), 300)
                            if not commander or not api_key:
                                raise ValueError("Enter an EDSM commander name and API key first.")
                            response = requests.get(
                                "https://www.edsm.net/api-commander-v1/get-ranks",
                                params={"commanderName": commander, "apiKey": api_key},
                                headers={"Accept": "application/json", "User-Agent": f"VoidCompass/{APP_VERSION}"},
                                timeout=10,
                            )
                            if not response.headers.get("content-type", "").casefold().startswith("application/json"):
                                raise RuntimeError(f"EDSM returned an unexpected response (HTTP {response.status_code}).")
                            body = response.json()
                            if body.get("msgnum") not in {100, 207}:
                                raise RuntimeError(f"EDSM [{body.get('msgnum')}]: {body.get('msg') or 'credentials rejected'}")
                            detail = "EDSM credentials accepted."
                            if body.get("msgnum") == 207:
                                detail += " No stored rank data was returned yet."
                        else:
                            tracker = getattr(self, "carrier_tracker", None)
                            url = _text(payload.get("url"), 1000)
                            if tracker is None or not url:
                                raise ValueError("Enter a Discord webhook URL first.")
                            ok, error = tracker.send_test_discord(url)
                            if not ok:
                                raise RuntimeError(error or "Discord rejected the preview.")
                            detail = "Discord accepted the themed Carrier preview."
                        error = None
                    except Exception as exc:
                        detail, error = str(exc), exc

                    def finish():
                        active = self._html_profile_transient("_html_settings_tool_state", {})
                        if active.get("profile") != profile or active.get("generation") != generation:
                            return
                        active.update({"status": "failed" if error else "ready", "detail": detail})
                        self.add_event_feed_entry(
                            "SYSTEM", detail, severity="WARN" if error else "INFO",
                        )
                        self._schedule_html_dashboard_publish(immediate=True)

                    self._ui_post(finish, key="html-settings-test")

                threading.Thread(target=worker, name="HtmlIntegrationTest", daemon=True).start()
                return True
            if operation == "capture_begin":
                self._suspend_overlay_hotkeys_for_capture()
                return True
            if operation == "capture_end":
                self._resume_overlay_hotkeys_after_capture()
                return True
            if operation == "support_bundle":
                self._create_support_bundle()
                return True
            if operation == "run_setup":
                self._rerun_first_run_onboarding()
                return True
            if operation == "save":
                values = payload.get("values") or {}
                allowed = {
                    "journal_path": str, "screenshots_path": str,
                    "screenshots_enabled": bool, "ui_scale_percent": int,
                    "reduced_motion_enabled": bool, "hud_animation_intensity": str,
                    "overlay_hotkeys_enabled": bool, "edsm_cmdr_name": str,
                    "edsm_api_key": str, "edsm_upload_enabled": bool,
                    "eddn_market_upload_enabled": bool,
                    "carrier_discord_webhook_url": str,
                    "runtime_trace_enabled": bool, "crash_reporting_enabled": bool,
                    "recovery_safe_mode_enabled": bool,
                    "edsm_backfill_on_cache_rebuild": bool,
                    "automatic_profile_backups_enabled": bool,
                    "galnet_enabled": bool,
                    "galnet_auto_rotate_enabled": bool,
                    "galnet_rotation_seconds": int,
                    "galnet_refresh_minutes": int,
                }
                for key, cast in allowed.items():
                    if key not in values:
                        continue
                    value = values[key]
                    if cast is bool:
                        self.config[key] = bool(value)
                    elif key == "galnet_rotation_seconds":
                        self.config[key] = max(4, min(60, _integer(value, 7)))
                    elif key == "galnet_refresh_minutes":
                        self.config[key] = max(5, min(240, _integer(value, 30)))
                    elif cast is int:
                        self.config[key] = max(75, min(200, _integer(value, 100)))
                    else:
                        self.config[key] = _text(value, 1000)
                raw_hotkeys = payload.get("hotkeys") or {}
                normalized, errors = validate_hotkey_bindings(raw_hotkeys)
                if errors:
                    return False
                for action, key, _label, _attr in OVERLAY_HOTKEY_SPECS:
                    self.config[key] = normalized.get(action, "")
                self._persist_config()
                try:
                    from services.eddn_upload import UPLOADER as eddn_market_uploader
                    eddn_market_uploader.set_enabled(bool(self.config.get("eddn_market_upload_enabled", True)))
                except Exception:
                    pass
                apply_ui_scale(self.root, self.config.get("ui_scale_percent", 100))
                self._apply_active_profile_theme()
                self._apply_runtime_feature_toggles()
                self._configure_overlay_hotkeys()
                self._restart_galnet_feed_schedule(delay_ms=250)
                changed = True
            elif operation == "rebuild_cache":
                self.config["edsm_backfill_on_cache_rebuild"] = bool(payload.get("upload_edsm"))
                self._persist_config()
                self.scan_all_logs_threaded()
                return True

        if changed:
            if page == "explore":
                # Waypoint edits are profile-local rather than journal
                # events, so explicitly republish the cockpit route instead
                # of waiting for the next Elite event to happen to refresh it.
                self.update_hud()
            self._schedule_html_dashboard_publish(immediate=True)
        return bool(changed)

    def hide_native_dashboard_tool(self):
        """Keep the internal Tk state host withdrawn behind the HTML deck."""
        try:
            self.root.withdraw()
        except Exception:
            pass

    def _open_html_dashboard_map(self):
        runtime = getattr(self.root, "_voidcompass_html_dashboard_runtime", None)
        parent_origin = getattr(runtime, "origin", "")
        self.open_galaxy_map_page(embedded_origin=parent_origin)
        view = getattr(
            getattr(self, "exploration_window", None),
            "expedition_map_view", None,
        )
        if view is not None and runtime is not None:
            runtime.allow_frame_source(view.server.origin)
        self._schedule_html_dashboard_publish(immediate=True)

    def handle_html_dashboard_command(self, payload):
        action = str((payload or {}).get("action") or "").strip().casefold()
        if action == "page_changed":
            page = _text(payload.get("page"), 40).casefold()
            if page not in {
                "overview", "explore", "map", "records", "operations",
                "overlay-studio", "settings", "about", *_HTML_WORKSPACE_PAGES,
            }:
                return False
            self._html_dashboard_active_page = page
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action == "overlay_studio":
            return self._handle_html_overlay_studio_command(payload)
        if action == "workspace":
            return self._handle_html_workspace_command(payload)
        if action == "quit":
            self.on_close()
            return True
        if action == "copy_next":
            self._dashboard_copy_next()
            return True
        if action == "refresh_galnet":
            self.refresh_galnet(force=True)
            return True
        if action == "clear_galnet_cache":
            service = getattr(self, "galnet_feed", None)
            if service is None or not service.clear_cache():
                return False
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action == "set_exploration_doctrine":
            doctrine = _text(payload.get("doctrine") or "balanced", 30).casefold()
            if doctrine not in DOCTRINES:
                return False
            self.config["exploration_doctrine"] = doctrine
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action == "save_dashboard_layout":
            available = ("route", "session", "priorities", "codex", "feed")
            raw_order = payload.get("module_order")
            raw_hidden = payload.get("hidden_modules")
            if not isinstance(raw_order, list) or not isinstance(raw_hidden, list):
                return False
            order = [str(name) for name in raw_order if str(name) in available]
            order.extend(name for name in available if name not in order)
            hidden = [str(name) for name in raw_hidden if str(name) in available]
            self.config["dashboard_module_order"] = order
            self.config["dashboard_hidden_modules"] = list(dict.fromkeys(hidden))
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action in {"save_page_layout", "reset_page_layout"}:
            page = _text(payload.get("page"), 40).casefold()
            allowed_pages = {
                "overview", "explore", "records", "operations", "profile",
                "analytics", "chronicle", "mission", "ground", "mining",
                "engineering", "carrier", "recon", "achievements", "ledger",
                "settings", "about",
            }
            if page not in allowed_pages:
                return False
            layouts = dict(self.config.get("dashboard_page_layouts") or {})
            if action == "reset_page_layout":
                layouts.pop(page, None)
            else:
                raw_containers = payload.get("containers")
                if not isinstance(raw_containers, dict) or len(raw_containers) > 32:
                    return False
                clean_containers = {}
                for container, panels in raw_containers.items():
                    container_key = _text(container, 100)
                    if not container_key or not isinstance(panels, list) or len(panels) > 100:
                        return False
                    clean_panels = [_text(panel, 100) for panel in panels]
                    if any(not panel for panel in clean_panels):
                        return False
                    clean_containers[container_key] = list(dict.fromkeys(clean_panels))
                layouts[page] = clean_containers
            self.config["dashboard_page_layouts"] = layouts
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action == "add_codex_objective":
            target = _text(payload.get("target"), 200)
            manager = getattr(self, "expedition_manager", None)
            try:
                active = manager.active() if manager else None
            except Exception:
                active = None
            if not target or not active:
                return False
            objective = manager.add_objective(
                active.get("id"), "codex_category", target=target,
                notes="Added from the Explorer Decision Deck personal regional Codex comparison.",
            )
            if not objective:
                return False
            self.add_event_feed_entry(
                "EXPEDITION", f"Codex objective added: {target}", severity="INFO",
            )
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action == "open_codex_atlas":
            self._open_html_dashboard_map()
            return self._request_html_dashboard_page("map")
        if action == "set_theme":
            name = _text(payload.get("name"), 120)
            custom = self.config.get("ui_custom_themes") or {}
            if name not in themes.BUILTIN_THEMES and name not in custom:
                return False
            self.config["ui_theme_name"] = name
            self._apply_active_profile_theme()
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action == "set_flight_log_mode":
            enabled = bool(payload.get("enabled"))
            if enabled == bool(self.config.get("flight_log_mode_enabled", False)):
                return True
            capture = getattr(self, "_capture_dashboard_window_geometry", None)
            if callable(capture):
                capture()
            self.config["flight_log_mode_enabled"] = enabled
            apply_geometry = getattr(self, "_apply_dashboard_window_geometry", None)
            if callable(apply_geometry):
                apply_geometry()
            self._persist_config()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if action == "rebuild_cache":
            self.scan_all_logs_threaded()
            return True
        if action == "open_screenshots":
            self.open_screenshots_folder()
            return True
        if action == "open_logs":
            path = application_base_dir() / "logs"
            path.mkdir(parents=True, exist_ok=True)
            open_path(path)
            return True
        if action != "open":
            return False

        target = str(payload.get("target") or "").strip().casefold()
        if target == "map":
            self._open_html_dashboard_map()
            return True
        if target == "overlay_studio":
            return self._request_html_dashboard_page("overlay-studio")
        if target in _HTML_WORKSPACE_PAGES or target in {"explore", "operations"}:
            return self._request_html_dashboard_page(target)
        urls = {
            "github": PROJECT_URL,
            "releases": RELEASES_URL,
            "issues": ISSUES_URL,
        }
        if target in urls:
            webbrowser.open_new_tab(urls[target])
            return True
        if target == "captains_log":
            return self._request_html_dashboard_page("chronicle")
        return False
