"""The Local API's records (5.5.7): everything Void Compass keeps, each with a
shape of its own, never the deck's page as it happens to be showing.

Exploration history (bodies scanned, systems visited, the route, regions),
the Codex, the Captain's log, game statistics, contacts, missions, the fleet,
trading, colonisation, carriers, mining, combat, engineering, powerplay,
achievements, route and waypoints, time capsules; and the few actions that
go with them. Nothing here reaches outside the PC: searches that ask Spansh
stay on the deck.
"""

from __future__ import annotations

import json
import sqlite3
import time

from voidcompass.core import companion_features
from voidcompass.exploration import bio_reference, galactic_regions
from voidcompass.services.local_api import ApiError

# A body search reads at most this many saved bodies, newest first, so a
# huge history still answers well inside the API's few seconds.
BODY_SCAN_LIMIT = 25_000
# A sealed capsule keeps its note to itself until it opens.
CAPSULE_FIELDS = ("id", "system", "left_at", "left_from", "opened_at", "not_before", "kind", "target")


def _plain(value):
    return json.loads(json.dumps(value, default=lambda item: sorted(item) if isinstance(item, (set, frozenset))
                                 else str(item)))


def _flag(value):
    """A query flag: None (either way), True or False."""
    if value in (None, ""):
        return None
    return str(value).casefold() in ("1", "true", "yes", "on")


class ApiRecordsMixin:
    # -- shared --------------------------------------------------------------
    def _api_need(self, name, where):
        value = getattr(self, name, None)
        if value is None:
            raise ApiError(409, f"{where} isn't ready yet")
        return value

    def _api_companion(self):
        return getattr(self, "companion_state", None) or {}

    def _api_refresh_deck(self):
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)

    # -- exploration -----------------------------------------------------------
    def api_exploration(self):
        state = self._api_companion()
        history = getattr(self, "travel_history", None)
        records = history.records() if history is not None else {}
        engine = getattr(self, "specialist_engine", None)
        bio_cr = int(state.get("unsold_bio_cr") or 0)
        return _plain({
            "unsold": {
                "cartographic_cr": int(state.get("unsold_exploration_cr") or 0),
                "bio_cr": bio_cr,
                # Certain on first-footfall bodies, so counted in the total.
                "bio_bonus_cr": int(state.get("unsold_bio_bonus_potential_cr") or 0),
                "bio_total_cr": companion_features.unsold_bio_value(state),
                "bio_samples": len(state.get("unsold_bio_samples") or []),
            },
            "last_sales": {"cartographic": state.get("last_exploration_sale"), "bio": state.get("last_bio_sale")},
            "data_lost_at": state.get("exploration_data_lost_at"),
            "records": {"furthest_from_sol_ly": round(float(records.get("far") or 0), 2),
                        "longest_jump_ly": round(float(records.get("jump") or 0), 2),
                        "systems_visited": int(records.get("systems") or 0),
                        "first_arrival": records.get("first")},
            "sampling": engine.exobiology_snapshot() if engine is not None else None,
        })

    @staticmethod
    def _api_body(system, item):
        return {
            "system": system, "body": item.get("name") or "", "body_id": item.get("body_id"),
            "class": item.get("class") or "", "star": bool(item.get("is_star")),
            "distance_ls": item.get("distance_to_arrival"),
            "landable": bool(item.get("landable")), "terraformable": bool(item.get("terraformable")),
            "first_discovery": item.get("was_discovered") is False,
            "first_footfall": bool(item.get("first_footfall")),
            "mapped": bool(item.get("dss_complete")),
            "value": item.get("reward"), "mapped_value": item.get("dss_reward"),
            "bio_signals": int(item.get("bio_count") or 0), "geo_signals": int(item.get("geo_count") or 0),
            "genera": list(item.get("genuses") or []),
            "gravity_g": item.get("gravity_g"), "temperature_k": item.get("surface_temp"),
            "atmosphere": item.get("atmosphere") or "",
            "scanned_at": item.get("_ts"),
        }

    def api_exploration_bodies(self, system="", first=None, landable=None, bio=None, footfall=None,
                               min_value=0, limit=100):
        conn = self._api_need("conn", "The exploration record")
        sql, params = "SELECT system_name, data_json FROM scan_hud_items", ()
        if system:
            sql, params = sql + " WHERE system_name = ? COLLATE NOCASE", (system,)
        sql += " ORDER BY ts DESC LIMIT ?"
        found, searched = [], 0
        with self.db_lock:
            try:
                # Read row by row and stop at enough: each body is a few KB of JSON.
                for name, data_json in conn.execute(sql, params + (BODY_SCAN_LIMIT,)):
                    searched += 1
                    try:
                        item = json.loads(data_json)
                    except ValueError:
                        continue
                    body = self._api_body(name, item)
                    if first is not None and body["first_discovery"] != first:
                        continue
                    if landable is not None and body["landable"] != landable:
                        continue
                    if footfall is not None and body["first_footfall"] != footfall:
                        continue
                    if bio is not None and (body["bio_signals"] > 0) != bio:
                        continue
                    if min_value and (body["mapped_value"] or body["value"] or 0) < min_value:
                        continue
                    found.append(body)
                    if len(found) >= limit:
                        break
            except sqlite3.Error as exc:
                raise ApiError(503, f"The exploration record couldn't be read ({exc})")
        return _plain({"bodies": found, "searched": searched,
                       "more": len(found) >= limit or searched >= BODY_SCAN_LIMIT})

    def _api_travel_rows(self):
        history = self._api_need("travel_history", "Your travel history")
        with history.lock:
            return list(history.rows)

    def api_exploration_systems(self, query="", limit=100):
        visits = {}
        for row in self._api_travel_rows():
            key = str(row[1]).casefold()
            seen = visits.get(key)
            if seen is None:
                visits[key] = seen = {"system": row[1], "visits": 0, "first": row[0], "last": row[0],
                                      "position": [row[2], row[3], row[4]], "star_class": row[5] or ""}
            seen["visits"] += 1
            seen["last"] = max(seen["last"], row[0])
            seen["first"] = min(seen["first"], row[0])
            if row[5]:
                seen["star_class"] = row[5]
        text = str(query or "").strip().casefold()
        rows = [row for key, row in visits.items() if not text or text in key]
        rows.sort(key=lambda row: row["last"], reverse=True)
        rows = rows[:limit]
        # Scan progress for the ones shown: bodies found of the system's total.
        conn = getattr(self, "conn", None)
        if conn is not None and rows:
            with self.db_lock:
                try:
                    found = {str(name).casefold(): (total, scanned) for name, total, scanned in conn.execute(
                        "SELECT name, total, scanned_count FROM systems WHERE name IN (%s)" % ",".join("?" * len(rows)),
                        tuple(row["system"] for row in rows)).fetchall()}
                except sqlite3.Error:
                    found = {}
            for row in rows:
                total, scanned = found.get(row["system"].casefold(), (None, None))
                row["bodies"], row["bodies_scanned"] = total, scanned
        return _plain({"systems": rows, "total": len(visits) if not text else len(rows), "query": query})

    def api_exploration_route(self, limit=100):
        arrivals = self._api_travel_rows()
        kinds = {"C": "carrier", "L": "location", "": "jump"}
        rows = [{"timestamp": row[0], "system": row[1], "position": [row[2], row[3], row[4]],
                 "star_class": row[5] or "", "jump_ly": row[6], "kind": kinds.get(row[7] if len(row) > 7 else "", "jump")}
                for row in reversed(arrivals[-limit:])]
        return _plain({"arrivals": rows, "total": len(arrivals)})

    def api_exploration_regions(self):
        arrivals = self._api_travel_rows()
        cache = getattr(self, "_api_regions_cache", None)
        key = (len(arrivals), arrivals[-1][0] if arrivals else "")
        if cache and cache[0] == key:
            return cache[1]
        regions = {}
        for row in arrivals:
            found = galactic_regions.find_region(row[2], row[3], row[4])
            if not found:
                continue
            region_id, name = found
            seen = regions.setdefault(region_id, {"id": region_id, "region": name, "arrivals": 0,
                                                  "first": row[0], "last": row[0]})
            seen["arrivals"] += 1
            seen["last"] = max(seen["last"], row[0])
        visited = sorted(regions.values(), key=lambda row: row["first"])
        result = {"regions": visited, "visited": len(visited), "of": len(galactic_regions.region_names())}
        self._api_regions_cache = (key, result)
        return result

    # -- the Codex -------------------------------------------------------------
    def api_codex(self, region=""):
        index = self._api_need("codex_index", "Your Codex record")
        names = galactic_regions.region_names()
        with index.lock:
            rows = list(index.rows)
        entries = {}
        for timestamp, entry, region_id, address, body_id in (row[:5] for row in rows):
            try:
                region_name = names[int(region_id) - 1] if region_id else ""
            except (TypeError, ValueError, IndexError):
                region_name = ""
            if region and region.casefold() not in region_name.casefold():
                continue
            seen = entries.setdefault(entry, {"entry": entry, "name": bio_reference.english_name(entry) or entry,
                                              "logged": 0, "first": timestamp, "last": timestamp, "regions": set()})
            seen["logged"] += 1
            seen["first"], seen["last"] = min(seen["first"], timestamp), max(seen["last"], timestamp)
            if region_name:
                seen["regions"].add(region_name)
        listed = sorted(entries.values(), key=lambda row: row["last"], reverse=True)
        for row in listed:
            row["regions"] = sorted(row["regions"])
        return _plain({"entries": listed, "total": len(listed), "region": region})

    # -- the Captain's log ---------------------------------------------------
    def api_log(self, limit=20):
        log = self._api_need("captains_log", "The Captain's log")
        return _plain({"sessions": log.sessions()[:limit]})

    def api_add_log(self, title, detail=""):
        log = self._api_need("captains_log", "The Captain's log")
        log.add_manual_highlight("NOTE", title, detail)
        self._api_refresh_deck()
        return {"added": True, "title": title, "detail": detail}

    # -- the commander's records ---------------------------------------------
    def api_statistics(self):
        state = self._api_companion()
        if not state.get("statistics"):
            raise ApiError(404, "No game statistics yet: the game writes them when you log in")
        return _plain({"statistics": state.get("statistics"), "updated": state.get("statistics_updated")})

    def api_contacts(self):
        ledger = getattr(self, "contact_ledger", None)
        model = ledger.model(max_rows=500, carrier_names=100) if ledger is not None else None
        return _plain(model or {"contacts": [], "counts": {}})

    def api_missions(self):
        missions = self._api_companion().get("missions") or {}
        rows = list(missions.values()) if isinstance(missions, dict) else list(missions)
        return _plain({"missions": rows, "total": len(rows)})

    def api_fleet(self):
        state = self._api_companion()
        return _plain({"stored": state.get("stored_ships") or {}, "loadouts": state.get("fleet_loadouts") or {},
                       "current": state.get("loadout")})

    def api_achievements(self):
        return _plain(self._api_need("achievement_engine", "Achievements").snapshot())

    # -- trading, colonisation, carriers -------------------------------------
    def api_trading(self, days=30):
        from voidcompass.trading import route as trade_route
        from voidcompass.trading import views as trade_views

        store = self._api_need("trading_store", "The trading record")
        summary = trade_views.summary(store, getattr(self, "trading_names", None) or {}, days)
        return _plain({"summary": summary, "route": trade_route.next_step(getattr(self, "trading_route", None))})

    def api_colonisation(self):
        from voidcompass.colonisation.views import project_rows

        colony = self._api_need("colony", "Colonisation")
        capacity_of = getattr(self, "_active_cargo_capacity", None)
        capacity = capacity_of() if callable(capacity_of) else 0
        return _plain({"projects": project_rows(colony, capacity or 0), "carrier_cargo": colony.carrier_cargo()})

    def api_carriers(self):
        return _plain({"carriers": self._api_need("carrier_tracker", "Carriers").carriers()})

    # -- mining, combat, engineering, powerplay -----------------------------
    def api_mining(self):
        return _plain(self._api_need("specialist_engine", "Mining").mining_snapshot())

    def api_mining_run(self, action):
        engine = self._api_need("specialist_engine", "Mining")
        if action == "start":
            changed = engine.start_mining({"system": getattr(self, "current_sys", None),
                                           "body": getattr(self, "current_body_name", None)})
        else:
            changed = engine.end_mining("manual")
        self._api_refresh_deck()
        return {"changed": bool(changed), "active": bool(engine.mining_active())}

    def api_combat(self):
        return _plain(self._api_need("specialist_engine", "Combat").combat_snapshot())

    def api_engineering(self):
        materials = getattr(self, "engineer_materials", None) or {}
        keys = ("raw", "manufactured", "encoded", "engineers", "pinned_blueprints", "odyssey_goals", "ship_locker",
                "last_updated")
        return _plain({**{key: materials.get(key) for key in keys},
                       "plans": materials.get("build_planner_builds") or []})

    def api_powerplay(self):
        state = dict(self._api_companion().get("powerplay") or {})
        for key in ("selected_objective_id", "selected_dossier"):
            state.pop(key, None)  # the deck's own selection, not yours
        return _plain(state)

    # -- route and waypoints -------------------------------------------------
    def api_route(self):
        expeditions = getattr(self, "expedition_manager", None)
        next_of = getattr(self, "_dashboard_next_destination", None)
        manager = getattr(self, "waypoint_manager", None)
        return _plain({"next": (next_of() if callable(next_of) else None) or None,
                       "waypoints": self._api_waypoints() if manager is not None else [],
                       "expedition": expeditions.active() if expeditions is not None else None})

    # The ROUTE tab's own buttons do the work, so the deck and the HUD follow at once.
    def _api_explore(self, operation, **payload):
        handle = getattr(self, "_handle_html_explore_command", None)
        if not callable(handle):
            raise ApiError(409, "Explore & Survey isn't ready yet")
        return bool(handle({"operation": operation, **payload}))

    def _api_waypoints(self):
        manager = self._api_need("waypoint_manager", "Waypoints")
        return [{"index": index, "name": row.get("name") or "", "note": row.get("note") or "",
                 "visited": bool(row.get("visited")), "coords": row.get("coords"),
                 **{key: row[key] for key in ("neutron", "jumps") if key in row}}
                for index, row in enumerate(manager.waypoints) if isinstance(row, dict)]

    def _api_waypoint(self, index):
        manager = self._api_need("waypoint_manager", "Waypoints")
        if not 0 <= index < len(manager.waypoints):
            raise ApiError(404, f"There's no waypoint {index} (you have {len(manager.waypoints)}, from 0)")
        return manager.waypoints[index]

    def api_add_waypoint(self, name, note=""):
        if not self._api_explore("add_waypoint", name=name, note=note):
            raise ApiError(409, "The waypoint couldn't be added")
        return {"added": name, "waypoints": self._api_waypoints()}

    def api_change_waypoint(self, index, changes):
        row = self._api_waypoint(index)
        if "name" in changes or "note" in changes:
            # Editing replaces the note, so an unchanged one is passed on as it was.
            self._api_explore("edit_waypoint", index=index, name=changes.get("name") or row.get("name"),
                              note=changes["note"] if "note" in changes else row.get("note") or "")
        if "visited" in changes:
            self._api_explore("mark_waypoint", index=index, visited=bool(changes["visited"]))
        if changes.get("move") in ("up", "down"):
            self._api_explore("move_waypoint", index=index, offset=-1 if changes["move"] == "up" else 1)
        return {"waypoints": self._api_waypoints()}

    def api_delete_waypoint(self, index):
        removed = self._api_waypoint(index).get("name") or ""
        if not self._api_explore("delete_waypoint", index=index, confirmed=True):
            raise ApiError(409, "The waypoint couldn't be removed")
        return {"removed": removed, "waypoints": self._api_waypoints()}

    def api_clear_waypoints(self):
        self._api_need("waypoint_manager", "Waypoints")
        self._api_explore("clear_waypoints", confirmed=True)
        return {"waypoints": self._api_waypoints()}

    def api_return_later(self):
        state_of = getattr(self, "_return_later_state", None)
        if not callable(state_of):
            raise ApiError(409, "Return later isn't ready yet")
        state = state_of() or {}
        dismissed = set(state.get("dismissed") or ())
        return _plain({"places": [row for row in state.get("entries") or ()
                                  if isinstance(row, dict) and row.get("id") not in dismissed]})

    def api_return_later_action(self, action, entry_id):
        known = {row["id"] for row in self.api_return_later()["places"]}
        if entry_id not in known:
            raise ApiError(404, f"Nothing called {entry_id} to return to (see /api/v1/route/return-later)")
        operation = "return_later_waypoint" if action == "waypoint" else "return_later_dismiss"
        if not self._api_explore(operation, id=entry_id):
            raise ApiError(409, "That couldn't be done")
        return {"done": action, "id": entry_id, "waypoints": self._api_waypoints()}

    def api_neutron_route(self):
        transient = getattr(self, "_html_profile_transient", None)
        tool = transient("_html_explore_tool_state", {}) if callable(transient) else {}
        route = tool.get("route") or None
        return _plain({"status": tool.get("status") or "ready", "detail": tool.get("detail") or "", "route": route})

    def api_import_neutron_route(self):
        if not (self.api_neutron_route()["route"] or {}).get("waypoints"):
            raise ApiError(409, "No neutron route has been plotted: plot one on Explore & Survey › ROUTE")
        before = len(self._api_waypoints())
        self._api_explore("neutron_import")
        after = self._api_waypoints()
        return {"imported": len(after) - before, "waypoints": after}

    def api_copy_next(self):
        next_of = getattr(self, "_dashboard_next_destination", None)
        system = next_of() if callable(next_of) else None
        if not system:
            raise ApiError(409, "There's no next system: plot a route or add a waypoint")
        return {"copied": bool(self._html_copy_text(system)), "system": system}

    # -- the BGS, from outside -------------------------------------------------
    def api_bgs_track(self, name, tracked=True):
        store = self._api_need("bgs_store", "The BGS record (the BGS page)")
        store.set_tracked("faction", name, bool(tracked))
        self._api_refresh_deck()
        return {"faction": name, "tracked": bool(tracked), "tracked_factions": store.tracked("faction")}

    # -- time capsules ---------------------------------------------------------
    def api_capsules(self):
        store_of = getattr(self, "capsule_store", None)
        store = store_of() if callable(store_of) else None
        if store is None:
            raise ApiError(409, "Time capsules aren't ready yet")
        rows = []
        for row in store.rows():
            shown = {key: row.get(key) for key in CAPSULE_FIELDS}
            shown["sealed"] = not row.get("opened_at")
            if not shown["sealed"]:
                shown["note"] = row.get("note") or ""
            rows.append(shown)
        return _plain({"capsules": rows, "now": time.time()})

    def api_leave_capsule(self, note, system="", wait="none"):
        handle = getattr(self, "_handle_capsules_command", None)
        if not callable(handle) or not handle("leave", {"note": note, "system": system, "wait": wait}):
            raise ApiError(409, "The capsule couldn't be sealed (too many waiting, or no system yet)")
        newest = (self.capsule_store().rows() or [{}])[0]
        return {"sealed": True, "id": newest.get("id"), "system": newest.get("system"),
                "not_before": newest.get("not_before")}
