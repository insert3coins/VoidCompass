"""Explore & Survey's tables (5.7.8): Nearby and the body table.

Nearby is every known system round a centre (you, your destination, your
next stop, a locked system or one you name), from Spansh's systems search,
with your own scans and visits laid over it. The nearest systems' dumps are
fetched one at a time in the background, which brings their landable worlds,
rings and biology signals. Spansh is asked when the centre changes or you
press refresh; never on a timer. The lists are too big for the snapshot, so
the page asks for them by name (/api/data/explore-nearby, explore-system) and
the snapshot carries only a revision for each.

Modelled on ED-Outrider's Overview (github.com/weslocke/ED-Outrider, GPLv3).
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import time

from voidcompass.core.config import get_active_profile
from voidcompass.exploration import nearby, system_table
from voidcompass.exploration.galactic_regions import find_region
from voidcompass.services import spansh

logger = logging.getLogger(__name__)

CENTRE_KINDS = ("here", "destination", "next_stop", "carrier", "lock", "system")
DUMPS_AHEAD = 40        # the nearest systems whose dumps are fetched in the background
DUMPS_KEPT = 400
WATCH_S = 600           # Nearby follows your jumps while the page asked for it this recently
NOT_ON_SPANSH = "not on Spansh"  # a system nobody has reported yet: no error to show
BOOKMARKS_FILE = "explore_bookmarks.json"


def _text(value, limit=140):
    return " ".join(str(value or "").split())[:limit]


class DashboardSurveyMixin:

    # -- shared state -------------------------------------------------------------------------------
    def _survey(self):
        state = self._html_profile_transient("_survey_state", {
            "nearby": {"status": "idle", "detail": "Open Explore & Survey to look round you.", "results": [],
                       "centre": {"kind": "here", "name": "", "coords": None}, "radius": None,
                       "updated": None, "count": 0, "complete": True, "rev": 0, "generation": 0},
            "dumps": {}, "dump_queue": [], "dump_busy": False, "dump_failed": set(),
            "systems": {}, "seen_at": 0.0, "rev": 0,
        })
        return state

    def _survey_bump(self):
        state = self._survey()
        state["rev"] = int(state.get("rev") or 0) + 1
        state.pop("rows_cache", None)
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)

    def _survey_task(self, name, work, done):
        """One Spansh request off the UI thread; ``done(result, error)`` runs on it."""
        profile = get_active_profile(self.config)

        def run():
            result, error = None, ""
            try:
                result = work()
            except spansh.SpanshNotFound:
                error = NOT_ON_SPANSH
            except spansh.SpanshError as exc:
                error = str(exc)
            except Exception as exc:
                logger.exception("Explore & Survey %s failed", name)
                error = f"Spansh request failed: {exc}"

            def finish():
                if get_active_profile(self.config) != profile:
                    return
                done(result, error)
            self._ui_post(finish, key=f"survey-{name}-{time.time_ns()}")

        threading.Thread(target=run, name=f"Survey-{name}", daemon=True).start()

    def _survey_jump_range(self):
        try:
            value = float(self._expedition_jump_range())
        except Exception:
            value = 0.0
        return value if value > 0 else None

    def _survey_radius(self):
        try:
            radius = int(self.config.get("explore_nearby_radius") or nearby.DEFAULT_RADIUS)
        except (TypeError, ValueError):
            radius = nearby.DEFAULT_RADIUS
        return radius if radius in nearby.RADII else nearby.DEFAULT_RADIUS

    # -- what you know of places ---------------------------------------------------------------------
    def _survey_visits(self):
        history = getattr(self, "travel_history", None)
        if history is None:
            return {}
        with history.lock:
            history._ensure_index()
            return {key: value[0] for key, value in history._visits.items()}

    def _survey_coords_of(self, name):
        """A system's position from your own journey, else None."""
        history = getattr(self, "travel_history", None)
        key = str(name or "").casefold()
        if key and key == str(getattr(self, "current_sys", "") or "").casefold() and getattr(self, "current_coords", None):
            return list(self.current_coords)
        if history is None or not key:
            return None
        with history.lock:
            for row in reversed(history.rows):
                if str(row[1]).casefold() == key:
                    return [row[2], row[3], row[4]]
        return None

    def _survey_own_items(self, names):
        """Your scans of each named system, from the profile's scan cache (the
        system you're in from the live list)."""
        wanted = {str(name).casefold(): str(name) for name in names if name}
        out = {}
        current = str(getattr(self, "current_sys", "") or "").casefold()
        if current in wanted:
            out[current] = [row for row in getattr(self, "scan_items", None) or () if isinstance(row, dict)]
        rest = [wanted[key] for key in wanted if key != current]
        conn, lock = getattr(self, "conn", None), getattr(self, "db_lock", None)
        if not rest or conn is None or lock is None:
            return out
        try:
            with lock:
                for start in range(0, len(rest), 400):
                    chunk = rest[start:start + 400]
                    marks = ",".join("?" * len(chunk))
                    for system, data in conn.execute(
                            f"SELECT system_name, data_json FROM scan_hud_items WHERE system_name IN ({marks}) COLLATE NOCASE",
                            chunk):
                        try:
                            item = json.loads(data)
                        except ValueError:
                            continue
                        if isinstance(item, dict):
                            out.setdefault(str(system).casefold(), []).append(item)
        except sqlite3.Error as exc:
            logger.debug("Survey scan lookup failed: %s", exc)
        return out

    def _survey_first_systems(self):
        """Systems where you were first to discover something, from your scans."""
        conn, lock = getattr(self, "conn", None), getattr(self, "db_lock", None)
        if conn is None or lock is None:
            return set()
        try:
            with lock:
                count = conn.execute("SELECT COUNT(*) FROM scan_hud_items").fetchone()[0]
                cached = getattr(self, "_survey_firsts_cache", None)
                if cached and cached[0] == count:
                    return cached[1]
                rows = conn.execute("SELECT system_name FROM scan_hud_items WHERE data_json LIKE '%\"was_discovered\": false%'").fetchall()
        except sqlite3.Error:
            return set()
        firsts = {str(row[0]).casefold() for row in rows}
        self._survey_firsts_cache = (count, firsts)
        return firsts

    # -- bookmarks ------------------------------------------------------------------------------------
    def _survey_bookmarks(self):
        path = self._profile_path(BOOKMARKS_FILE)
        cached = getattr(self, "_survey_bookmarks_cache", None)
        if cached and cached[0] == path:
            return cached[1]
        try:
            with open(path, encoding="utf-8") as handle:
                rows = json.load(handle)
        except (OSError, ValueError):
            rows = []
        rows = [row for row in rows if isinstance(row, dict) and row.get("name")] if isinstance(rows, list) else []
        self._survey_bookmarks_cache = (path, rows)
        return rows

    def _survey_save_bookmarks(self, rows):
        path = self._profile_path(BOOKMARKS_FILE)
        temp = f"{path}.tmp"
        try:
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(rows, handle, indent=1)
            os.replace(temp, path)
        except OSError as exc:
            logger.warning("Bookmarks not saved: %s", exc)
            return False
        self._survey_bookmarks_cache = (path, rows)
        return True

    def _survey_toggle_bookmark(self, name, coords=None, id64=None, note=""):
        rows = list(self._survey_bookmarks())
        key = str(name).casefold()
        if any(str(row.get("name")).casefold() == key for row in rows):
            rows = [row for row in rows if str(row.get("name")).casefold() != key]
        else:
            rows.append({"name": name, "coords": coords or self._survey_coords_of(name), "id64": id64 or None,
                         "note": _text(note, 300), "added": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        self._survey_save_bookmarks(rows)
        self._survey_bump()
        return True

    # -- the centre -----------------------------------------------------------------------------------
    def _survey_centre(self, kind, name=""):
        """{kind, name, coords} for a centre, or {kind, name, error}."""
        kind = kind if kind in CENTRE_KINDS else "here"
        if kind == "here":
            name = str(getattr(self, "current_sys", "") or "")
        elif kind == "destination":
            details = getattr(self, "current_destination_details", None) or {}
            name = str(getattr(self, "current_destination", "") or "")
            # A body or station target in this system: its system is here.
            if details.get("System") is not None and str(details.get("System")) == str(getattr(self, "current_system_address", "")):
                name = str(getattr(self, "current_sys", "") or "")
            route = [row for row in getattr(self, "nav_route_entries", None) or () if isinstance(row, dict)]
            if route:
                name = str(route[-1].get("StarSystem") or name)
                coords = route[-1].get("StarPos")
                if coords:
                    return {"kind": kind, "name": name, "coords": list(coords)}
        elif kind == "next_stop":
            route = [row for row in getattr(self, "nav_route_entries", None) or () if isinstance(row, dict)]
            current = str(getattr(self, "current_sys", "") or "").casefold()
            index = next((i for i, row in enumerate(route) if str(row.get("StarSystem") or "").casefold() == current), -1)
            if 0 <= index + 1 < len(route):
                row = route[index + 1]
                return {"kind": kind, "name": str(row.get("StarSystem") or ""), "coords": list(row.get("StarPos") or []) or None}
            manager = getattr(self, "waypoint_manager", None)
            name = manager.get_next_waypoint(getattr(self, "current_sys", "")) if manager else ""
            for row in getattr(manager, "waypoints", None) or ():
                if str(row.get("name") or "").casefold() == str(name or "").casefold() and row.get("coords"):
                    return {"kind": kind, "name": name, "coords": list(row["coords"])}
        elif kind == "carrier":
            tracker = getattr(self, "carrier_tracker", None)
            carrier = tracker.display_carrier() if tracker is not None and hasattr(tracker, "display_carrier") else None
            name = str((carrier or {}).get("system") or "")
        name = _text(name)
        if not name:
            return {"kind": kind, "name": "", "error": {
                "here": "No system yet: the journal hasn't said where you are.",
                "destination": "No destination: plot a route or target a system in the galaxy map.",
                "next_stop": "No next stop: plot one on the Route page, or add waypoints on the Expeditions page.",
                "carrier": "No carrier known.", "lock": "Nothing locked yet.",
                "system": "Type a system name."}[kind]}
        coords = self._survey_coords_of(name)
        return {"kind": kind, "name": name, "coords": coords}

    # -- Nearby ---------------------------------------------------------------------------------------
    def _survey_nearby_refresh(self, kind=None, name="", radius=None):
        state = self._survey()
        near = state["nearby"]
        kind = kind or near["centre"].get("kind") or "here"
        if kind == "lock":
            name = name or near["centre"].get("name") or ""
            centre = {"kind": "lock", "name": name, "coords": self._survey_coords_of(name) if name else None}
            if not name:
                centre["error"] = "Nothing locked yet."
        else:
            centre = self._survey_centre(kind, name)
        if radius is not None:
            try:
                radius = int(radius)
            except (TypeError, ValueError):
                radius = None
            if radius in nearby.RADII:
                self.config["explore_nearby_radius"] = radius
                self._persist_config()
        radius = self._survey_radius()
        generation = int(near.get("generation") or 0) + 1
        near.update(centre={k: centre.get(k) for k in ("kind", "name", "coords")}, radius=radius, generation=generation)
        if centre.get("error"):
            near.update(status="failed", detail=centre["error"])
            self._survey_bump()
            return False
        near.update(status="working", detail=f"Asking Spansh what's within {radius} ly of {centre['name']}…")
        self._survey_bump()

        def work():
            coords = centre.get("coords")
            if not coords:
                found = spansh.system_lookup(centre["name"])
                coords = found.get("coords")
                if not coords:
                    raise spansh.SpanshError(f"Spansh doesn't know where {centre['name']} is.")
            return {"coords": coords, **spansh.systems_sphere(coords, radius)}

        def done(result, error):
            if near.get("generation") != generation:
                return
            if error:
                near.update(status="failed", detail=error)
            else:
                near["centre"]["coords"] = result["coords"]
                results = result.get("results") or []
                near.update(status="ready", results=results, count=len(results), complete=bool(result.get("complete")),
                            updated=time.time(),
                            detail=f"{len(results):,} known systems within {radius} ly of {centre['name']}"
                                   + ("" if result.get("complete") else " (Spansh stopped short: the nearest are listed)"))
                self._survey_queue_dumps([row for row in results[:DUMPS_AHEAD] if row.get("id64")])
            self._survey_bump()

        self._survey_task("nearby", work, done)
        return True

    def _survey_queue_dumps(self, rows, front=False):
        state = self._survey()
        queue = state["dump_queue"]
        have = set(state["dumps"]) | set(queue) | state["dump_failed"]
        new = [str(row.get("id64")) for row in rows if str(row.get("id64")) not in have]
        state["dump_queue"] = new + queue if front else queue + new
        self._survey_pump_dumps()

    def _survey_pump_dumps(self):
        state = self._survey()
        if state.get("dump_busy") or not state["dump_queue"]:
            return
        id64 = state["dump_queue"].pop(0)
        state["dump_busy"] = True

        def done(result, error):
            state["dump_busy"] = False
            if error or not isinstance(result, dict):
                state["dump_failed"].add(id64)
            else:
                state["dumps"][id64] = result
                while len(state["dumps"]) > DUMPS_KEPT:
                    state["dumps"].pop(next(iter(state["dumps"])))
                self._survey_bump()
            self._survey_pump_dumps()

        self._survey_task("dump", lambda: spansh.system_dump_full(int(id64)), done)

    def _survey_on_arrival(self):
        """A jump: Nearby follows you when it's centred on you and the page looked at it lately."""
        self._phenomena_on_arrival()
        state = self._survey()
        if time.time() - float(state.get("seen_at") or 0) > WATCH_S:
            return
        if (state["nearby"]["centre"].get("kind") or "here") == "here":
            self._survey_nearby_refresh("here")
        else:
            self._survey_bump()

    def _phenomena_on_arrival(self):
        """5.7.8, after ED-Outrider: Canonn's reports of what's found in space
        here (notable stellar phenomena), the ones not yet in your Codex for this
        region, said by the officer on watch. Only the system's name is sent."""
        if not self.config.get("canonn_reports", True):
            return
        system = str(getattr(self, "current_sys", "") or "")
        if not system or system == "---":
            return
        from voidcompass.outrider import canonn_sites
        self._phenomena_asked = system

        def work():
            reply = spansh.http().get(canonn_sites.POI_URL, params={"system": system, "odyssey": "Y"}, timeout=15)
            poi = reply.json() if reply.status_code < 400 else {}
            return canonn_sites.space_entries(poi), canonn_sites.space_names(poi)

        def done(result, error):
            if error or not result or getattr(self, "_phenomena_asked", None) != system:
                return
            if str(getattr(self, "current_sys", "") or "") != system:
                return   # you've moved on
            ids, names = result
            codex = getattr(self, "codex_index", None)
            coords = getattr(self, "current_coords", None)
            region = find_region(*coords) if coords else None
            region = region[0] if region else None
            fresh, new = [], []
            for entry in ids:
                state = codex.type_state(entry, region) if codex is not None else "region"
                if state:
                    name = names.get(entry) or f"entry {entry}"
                    fresh.append(name)
                    if state == "new":
                        new.append(name)
            if not fresh:
                return
            listed = ", ".join(fresh[:4]) + (f" and {len(fresh) - 4} more" if len(fresh) > 4 else "")
            text = f"Canonn has reports of {listed} in space here."
            if new:
                text += " New to your Codex." if len(new) == len(fresh) else f" {', '.join(new[:3])} would be new to your Codex."
            else:
                text += " Not yet logged in this region."
            mind = getattr(self, "_orders_mind", lambda: None)()
            if mind is not None and hasattr(mind, "crew_say"):
                try:
                    from voidcompass.core import companions
                    mind.crew_say(companions.identity(self.config), text, heading="PHENOMENA", topic="phenomena_reported",
                                  converse=False)
                except Exception:
                    logger.debug("Phenomena line not said", exc_info=True)

        self._survey_task("phenomena", work, done)

    def _survey_nearby_rows(self):
        """Nearby as rows, built when anything they show changed."""
        state = self._survey()
        near = state["nearby"]
        results = list(near.get("results") or ())
        visits = self._survey_visits()
        bookmarks = self._survey_bookmarks()
        current = str(getattr(self, "current_sys", "") or "")
        key = (near.get("generation"), len(results), len(state["dumps"]), len(visits), len(bookmarks),
               current, len(getattr(self, "scan_items", None) or ()), self._survey_jump_range())
        cached = state.get("rows_cache")
        if cached and cached[0] == key:
            return cached[1]
        own = self._survey_own_items([row.get("name") for row in results])
        coords = near["centre"].get("coords")
        region = find_region(*coords) if coords else None
        rows = nearby.nearby_rows(results, dumps=dict(state["dumps"]), own=own, visits=visits,
                                  bookmarks=[row["name"] for row in bookmarks], firsts=self._survey_first_systems(),
                                  jump_range=self._survey_jump_range(), region_id=region[0] if region else None,
                                  codex=getattr(self, "codex_index", None))
        for row in rows:
            row["here"] = row["name"].casefold() == current.casefold()
        state["rows_cache"] = (key, rows)
        return rows

    def _survey_nearby_payload(self):
        state = self._survey()
        state["seen_at"] = time.time()
        near = state["nearby"]
        if near.get("status") == "idle":
            # The first look: ask now (the page asked, so Spansh may be asked).
            self._ui_post(lambda: self._survey_nearby_refresh("here"), key="survey-nearby-first")
        rows = self._survey_nearby_rows() if near.get("results") else []
        visited = sum(1 for row in rows if row["visited"])
        return {
            "status": near.get("status"), "detail": near.get("detail"), "centre": near.get("centre"),
            "radius": near.get("radius") or self._survey_radius(), "radii": list(nearby.RADII),
            "updated": near.get("updated"), "complete": near.get("complete"), "rev": state.get("rev"),
            "rows": rows, "count": len(rows), "not_visited": len(rows) - visited,
            "dumps_left": len(state["dump_queue"]) + (1 if state.get("dump_busy") else 0),
            "jump_range": self._survey_jump_range(), "here": str(getattr(self, "current_sys", "") or ""),
            "bookmarks": self._survey_bookmarks(),
        }

    # -- the route ahead ------------------------------------------------------------------------------
    def _survey_ahead_names(self):
        """The systems ahead: your followed route's, else the in-game route's."""
        route = self._route() if hasattr(self, "_route") else None
        if route and route.get("rows"):
            at = route.get("at")
            return [row["system"] for row in route["rows"][(at + 1 if at is not None else 0):]][:60], route.get("label") or "Route"
        nav = [row for row in getattr(self, "nav_route_entries", None) or () if isinstance(row, dict)]
        current = str(getattr(self, "current_sys", "") or "").casefold()
        index = next((i for i, row in enumerate(nav) if str(row.get("StarSystem") or "").casefold() == current), -1)
        return [str(row.get("StarSystem") or "") for row in nav[index + 1:]][:60], "In-game route"

    def _survey_ahead_payload(self):
        state = self._survey()
        names, label = self._survey_ahead_names()
        if not names:
            return {"label": label, "rows": [], "status": "empty"}
        key = tuple(names)
        ahead = state.setdefault("ahead", {"key": None, "results": [], "status": "idle"})
        if ahead["key"] != key and ahead["status"] != "working":
            ahead.update(key=key, status="working")

            def done(result, error):
                ahead.update(results=result or [], status="failed" if error else "ready", error=error)
                self._survey_bump()

            self._ui_post(lambda: self._survey_task("ahead", lambda: spansh.systems_by_name(list(key)), done), key="survey-ahead")
        order = {name.casefold(): index for index, name in enumerate(names)}
        found = {str(row.get("name") or "").casefold() for row in ahead["results"]}
        results = list(ahead["results"]) + [{"name": name, "id64": "", "distance": None} for name in names
                                              if name.casefold() not in found and ahead["status"] == "ready"]
        here = getattr(self, "current_coords", None)
        for row in results:
            if here and row.get("x") is not None:

                row["distance"] = round(math.dist(here, (row["x"], row["y"], row["z"])), 2)
        own = self._survey_own_items([row.get("name") for row in results])
        rows = nearby.nearby_rows(results, dumps=dict(state["dumps"]), own=own, visits=self._survey_visits(),
                                  bookmarks=[row["name"] for row in self._survey_bookmarks()],
                                  firsts=self._survey_first_systems(), jump_range=self._survey_jump_range(),
                                  codex=getattr(self, "codex_index", None))
        rows.sort(key=lambda row: order.get(row["name"].casefold(), 999))
        for index, row in enumerate(rows):
            row["stop"] = order.get(row["name"].casefold(), index) + 1
        return {"label": label, "rows": rows, "status": ahead["status"]}

    # -- one system's bodies ------------------------------------------------------------------------
    def _survey_find_id64(self, name):
        """id64 of a system from Nearby's results, your current system, or None."""
        key = str(name or "").casefold()
        if key == str(getattr(self, "current_sys", "") or "").casefold() and getattr(self, "current_system_address", None):
            return str(self.current_system_address)
        for row in self._survey()["nearby"].get("results") or ():
            if str(row.get("name") or "").casefold() == key and row.get("id64"):
                return str(row["id64"])
        return None

    def _survey_system_payload(self, name, id64=None, fetch=True):
        """The body table for one system: yours at once; Spansh's dump fetched
        when the page asks and it isn't known yet (``working`` until it is).
        ``fetch=False``: only what's already here (no Spansh request)."""
        state = self._survey()
        name = _text(name) or str(getattr(self, "current_sys", "") or "")
        if not name:
            return {"system": "", "rows": [], "meta": {}, "legend": [], "status": "empty"}
        id64 = str(id64 or "") or self._survey_find_id64(name)
        systems = state["systems"]
        entry = systems.get(name.casefold()) or {}
        dump = state["dumps"].get(id64) if id64 else None
        if dump is None and entry.get("dump") is not None:
            dump = entry["dump"]
        status = "ready"
        if dump is None and not entry.get("asked") and fetch:
            entry = systems[name.casefold()] = {"asked": True, "dump": None, "error": ""}
            status = "working"

            def work():
                wanted = id64
                if not wanted:
                    _exact, wanted = spansh.system_id64(name)
                return spansh.system_dump_full(int(wanted))

            def done(result, error):
                entry.update(dump=result if isinstance(result, dict) else None, error=error)
                if isinstance(result, dict) and result.get("id64"):
                    state["dumps"][str(result["id64"])] = result
                self._survey_bump()
                # The Survey overlay shows the system you're in from this table too.
                if name.casefold() == str(getattr(self, "current_sys", "") or "").casefold():
                    getattr(self, "_refresh_survey_status_progress", lambda: None)()

            self._ui_post(lambda: self._survey_task("system", work, done), key=f"survey-system-{name}")
        elif dump is None and entry.get("asked") and entry.get("dump") is None and not entry.get("error"):
            status = "working"
        own = self._survey_own_items([name]).get(name.casefold(), [])
        search_values = {}
        for row in state["nearby"].get("results") or ():
            if str(row.get("name") or "").casefold() == name.casefold():
                search_values = {item["name"].casefold(): item.get("value") for item in nearby.search_bodies(row)}
                break
        coords = self._survey_coords_of(name) or ([dump.get("coords", {}).get(axis) for axis in ("x", "y", "z")]
                                                   if dump and isinstance(dump.get("coords"), dict) else None)
        region = find_region(*coords) if coords and None not in coords else None
        rows, meta = system_table.body_rows(
            name, own, dump, search_values=search_values, codex=getattr(self, "codex_index", None),
            region_id=region[0] if region else None, coords=coords, records=self._survey_record_keys(),
            barycentres=(getattr(self, "system_barycentres", None) if name.casefold() == str(getattr(self, "current_sys", "") or "").casefold()
                         else (self.load_barycentres_from_db(name) if hasattr(self, "load_barycentres_from_db") else [])))
        # A system nobody has reported is simply yours, not an error (5.7.9).
        error = str(entry.get("error") or "")
        meta.update(spansh_known=dump is not None, spansh_error="" if error == NOT_ON_SPANSH else error)
        current = name.casefold() == str(getattr(self, "current_sys", "") or "").casefold()
        if current:
            meta["body_count"] = meta.get("body_count") or (int(getattr(self, "total", 0) or 0) or None)
        return {"system": name, "id64": id64 or (str(dump.get("id64")) if dump and dump.get("id64") else ""),
                "here": current, "region": region[1] if region else "", "status": status, "rows": rows, "meta": meta,
                "legend": system_table.legend(rows), "bookmarked": any(str(row.get("name")).casefold() == name.casefold()
                                                                         for row in self._survey_bookmarks()),
                "summary": system_table.summary_markdown(name, rows, meta)}

    def _survey_overlay_explore(self, system):
        """Explore & Survey's body table for the system you're in, for the
        Survey overlay (5.7.8): one set of facts for both. Spansh is asked on
        arrival unless the overlay's "Spansh bodies" option is off."""
        if not system or str(system).casefold() != str(getattr(self, "current_sys", "") or "").casefold():
            return None
        fetch = bool(self.config.get("survey_spansh_bodies", True))
        try:
            payload = self._survey_system_payload(system, fetch=fetch)
        except Exception:
            logger.debug("Survey overlay: no Explore table", exc_info=True)
            return None
        rows = payload.get("rows") or []
        if not fetch:
            rows = [row for row in rows if row.get("own")]
        return {"rows": rows, "meta": payload.get("meta") or {}, "status": payload.get("status")}

    def _survey_record_keys(self):
        """{(system, body): label} for your records (filled by the FIRSTS tab's records)."""
        records = getattr(self, "_survey_records_cache", None)
        if not records:
            return {}
        return {(str(row.get("system") or "").casefold(), str(row.get("body_short") or row.get("body") or "").casefold()): row["label"]
                for row in records[1] if row.get("body")}

    # -- the snapshot's share -------------------------------------------------------------------------
    def _survey_snapshot(self):
        state = self._survey()
        near = state["nearby"]
        return {"rev": state.get("rev"), "nearby_status": near.get("status"), "nearby_detail": near.get("detail"),
                "centre": {k: near["centre"].get(k) for k in ("kind", "name")}, "radius": near.get("radius") or self._survey_radius()}

    # -- commands -------------------------------------------------------------------------------------
    def _survey_command(self, operation, payload):
        name = _text(payload.get("name") or payload.get("system"))
        if operation == "nearby_refresh":
            return self._survey_nearby_refresh(_text(payload.get("centre"), 20) or None, name,
                                               payload.get("radius"))
        if operation == "nearby_lock":
            return self._survey_nearby_refresh("lock", name or str(getattr(self, "current_sys", "") or ""))
        if operation == "bookmark":
            if not name:
                return False
            coords = payload.get("coords") if isinstance(payload.get("coords"), list) else None
            return self._survey_toggle_bookmark(name, coords, _text(payload.get("id64"), 30), payload.get("note") or "")
        if operation == "copy_system":
            return self._html_copy_text(name, "system")
        if operation == "target_system":
            if not self._html_copy_text(name):
                return False
            if hasattr(self, "_watcher_ship"):
                try:
                    self._watcher_ship("open the galaxy map")
                except Exception:
                    logger.debug("Galaxy map not opened", exc_info=True)
            feed = getattr(self, "add_event_feed_entry", None)
            if callable(feed):
                feed("ROUTE", f"{name} copied: paste it into the galaxy map's search", severity="INFO")
            return True
        if operation == "add_route":
            manager = getattr(self, "waypoint_manager", None)
            if manager is None or not name:
                return False
            if any(str(row.get("name") or "").casefold() == name.casefold() for row in manager.waypoints):
                return True
            coords = payload.get("coords") if isinstance(payload.get("coords"), list) else self._survey_coords_of(name)
            manager.add_waypoint(name, coords, _text(payload.get("note") or "Explore & Survey", 300))
            self.update_hud()
            getattr(self, "_update_galaxy_minimap_safely", lambda: None)()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
        if operation == "system_open":
            # Fetch its dump first: the page will ask for the table.
            id64 = _text(payload.get("id64"), 30)
            if id64:
                self._survey_queue_dumps([{"id64": id64}], front=True)
            return True
        if operation == "system_summary":
            table = self._survey_system_payload(name or str(getattr(self, "current_sys", "") or ""))
            return self._html_copy_text(table.get("summary") or "", "system summary")
        if operation == "system_refresh":
            state = self._survey()
            state["systems"].pop((name or "").casefold(), None)
            id64 = self._survey_find_id64(name)
            if id64:
                state["dumps"].pop(id64, None)
                state["dump_failed"].discard(id64)
            self._survey_bump()
            return True
        handler = getattr(self, "_survey_more_command", None)
        return bool(handler(operation, payload)) if callable(handler) else False

    def _survey_data(self, name, query):
        """/api/data/explore-*: the big lists, asked for by the page."""
        if name == "explore-nearby":
            return self._survey_nearby_payload()
        if name == "explore-system":
            return self._survey_system_payload(query.get("name") or "", query.get("id64"))
        if name == "explore-ahead":
            return self._survey_ahead_payload()
        more = getattr(self, "_survey_more_data", None)
        return more(name, query) if callable(more) else None
