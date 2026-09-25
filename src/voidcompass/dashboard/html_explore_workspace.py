"""Explore workspace model and command controller for the HTML dashboard."""

from __future__ import annotations

import threading
import time
from urllib.parse import quote
import webbrowser

from voidcompass.core.config import get_active_profile
from voidcompass.dashboard.html_workspace_support import (
    integer as _integer,
    number as _number,
    text as _text,
)
from voidcompass.exploration.exploration_intelligence import system_completion
from voidcompass.exploration.exploration_scout import (
    SCOUT_MODES,
    normalise_scout_form,
    normalise_value_route,
    scout_mode,
    system_audit,
)
from voidcompass.exploration.galactic_regions import find_region
from voidcompass.exploration.return_later import (
    dismiss_entry as dismiss_return_later_entry,
    empty_state as empty_return_later_state,
    read_state as read_return_later_state,
    reconcile_state as reconcile_return_later_state,
    write_state as write_return_later_state,
)
from voidcompass.exploration.stellar_cartography import (
    build_orrery,
    build_planetary_resources,
    build_survey_queue,
)
from voidcompass.services.spansh import (
    SpanshError,
    exploration_body_search,
    neutron_route,
    riches_route,
)


class HtmlExploreWorkspaceMixin:
    # Journal reductions can arrive off the UI thread while a scheduled HTML
    # snapshot is rendering.  Keep the profile cache and atomic file writes in
    # one short critical section so neither view loses the other's update.
    _return_later_lock = threading.RLock()

    def _return_later_state(self):
        """Keep the small board cached, invalidating it at profile boundaries."""
        with self._return_later_lock:
            profile = get_active_profile(self.config)
            cached = getattr(self, "_return_later_cache", None)
            if isinstance(cached, dict) and cached.get("profile") == profile:
                return cached["state"]
            path = self._profile_path("return_later.json") if hasattr(self, "_profile_path") else None
            state = read_return_later_state(path) if path else empty_return_later_state()
            self._return_later_cache = {"profile": profile, "path": path, "state": state}
            return state

    def _save_return_later_state(self, state):
        with self._return_later_lock:
            cache = getattr(self, "_return_later_cache", None)
            if not isinstance(cache, dict) or cache.get("profile") != get_active_profile(self.config):
                self._return_later_state()
                cache = self._return_later_cache
            path = cache.get("path")
            if not path or not write_return_later_state(path, state):
                return False
            cache["state"] = state
            return True

    def _reconcile_return_later(self, *, visited_at=None, departure=False):
        with self._return_later_lock:
            state = self._return_later_state()
            system = _text(getattr(self, "current_sys", None), 140)
            survey_states = self.config.get("stellar_survey_queue_state") or {}
            survey_state = survey_states.get(system.casefold()) or {}
            updated = reconcile_return_later_state(
                state, system, getattr(self, "scan_items", None) or (), survey_state,
                scanned=getattr(self, "scanned", 0), total=getattr(self, "total", 0),
                total_confirmed=bool(getattr(self, "scan_total_confirmed", False)),
                fss_all_bodies=bool(getattr(self, "fss_all_bodies", False)),
                visited_at=visited_at, coords=getattr(self, "current_coords", None),
                departure=departure,
                body_signals=getattr(self, "body_signals", None) or {},
            )
            if updated != state and self._save_return_later_state(updated):
                return updated
            return state

    def _html_explore_workspace(self, intelligence=None):
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
        survey_queue = build_survey_queue(scan_items, survey_state, body_target)
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
        scout = self._html_profile_transient(
            "_html_exploration_scout_state",
            {
                "status": "ready",
                "detail": "Choose a prospect type and search the known community catalogue.",
                "results": [],
                "source": "",
                "evidence_note": "",
                "searched_at": "",
                "catalogue_count": 0,
            },
        )
        scout_form = normalise_scout_form(
            self.config.get("exploration_scout_form"), current_system=current,
        )
        completion = (
            intelligence.get("completion")
            if isinstance(intelligence, dict) else None
        )
        if not isinstance(completion, dict):
            completion = system_completion(
                scan_items,
                getattr(self, "scanned", 0), getattr(self, "total", 0),
                fss_complete=bool(getattr(self, "fss_all_bodies", False)),
                current_system=current,
            )
        region = find_region(*current_coords) if current_coords else None
        codex = self._html_dashboard_codex_hunt(region[1] if region else "Unknown region")
        return_later_state = self._reconcile_return_later()
        return_later_entries = [
            {
                "id": _text(row.get("id"), 300),
                "system": _text(row.get("system"), 140),
                "body": _text(row.get("body"), 180),
                "reasons": [_text(reason, 180) for reason in (row.get("reasons") or [])[:5]],
                "last_visited": _text(row.get("last_visited"), 40),
                "source": _text(row.get("source"), 30),
                "current": str(row.get("system") or "").casefold() == current.casefold(),
            }
            for row in return_later_state.get("entries") or ()
            if isinstance(row, dict)
        ]
        return {
            "current": current,
            "destination": _text(getattr(self, "dest_name", None), 140),
            "nav_route": nav_entries,
            "waypoints": rendered_waypoints,
            "next_waypoint": _text(
                manager.get_next_waypoint(current) if manager is not None else "", 140,
            ),
            "auto_copy": bool(self.config.get("auto_copy_waypoint", False)),
            "return_later": {
                "entries": return_later_entries,
                "count": len(return_later_entries),
            },
            "cartography": {
                "system": current,
                "target": body_target,
                "orrery": orrery,
                "queue": survey_queue,
                "resources": build_planetary_resources(scan_items),
            },
            "scout": {
                "reference": scout_form["reference"],
                "mode": scout_form["mode"],
                "modes": SCOUT_MODES,
                "radius": scout_form["radius"],
                "min_signals": scout_form["min_signals"],
                "min_value": scout_form["min_value"],
                "max_results": scout_form["max_results"],
                "jump_range": scout_form["jump_range"],
                "status": _text(scout.get("status"), 30),
                "detail": _text(scout.get("detail"), 400),
                "results": list(scout.get("results") or [])[:100],
                "source": _text(scout.get("source"), 100),
                "evidence_note": _text(scout.get("evidence_note"), 300),
                "searched_at": _text(scout.get("searched_at"), 40),
                "catalogue_count": max(0, _integer(scout.get("catalogue_count"))),
                "audit": system_audit(completion, survey_queue),
                "codex": codex,
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


    def _handle_html_explore_command(self, payload):
        operation = _text(payload.get("operation"), 60).casefold()
        changed = False
        if operation in {"return_later_copy", "return_later_waypoint", "return_later_dismiss"}:
            entry_id = _text(payload.get("id"), 300)
            with self._return_later_lock:
                state = self._return_later_state()
                entry = next((
                    row for row in state.get("entries") or ()
                    if isinstance(row, dict) and row.get("id") == entry_id
                ), None)
                if entry is None:
                    return False
                if operation == "return_later_dismiss":
                    updated = dismiss_return_later_entry(state, entry_id)
                    if updated == state or not self._save_return_later_state(updated):
                        return False
                    self._schedule_html_dashboard_publish(immediate=True)
                    return True
            system = _text(entry.get("system"), 140)
            if operation == "return_later_copy":
                return self._html_copy_text(system)
            manager = getattr(self, "waypoint_manager", None)
            if manager is None or not system:
                return False
            if any(str(row.get("name") or "").casefold() == system.casefold()
                   for row in getattr(manager, "waypoints", ()) if isinstance(row, dict)):
                return True
            coords = entry.get("coords")
            if not isinstance(coords, list) or len(coords) != 3:
                coords = None
            body = _text(entry.get("body"), 180)
            reasons = "; ".join(_text(reason, 180) for reason in (entry.get("reasons") or [])[:5])
            route_row = {
                "name": system, "coords": coords,
                "note": _text(f"Return Later · {body or 'system survey'} · {reasons}", 1000),
            }
            manager.waypoints.append(route_row)
            if not manager.save():
                manager.waypoints.pop()
                return False
            self.update_hud()
            self._schedule_html_dashboard_publish(immediate=True)
            return True
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
        if operation.startswith("scout_"):
            scout = self._html_profile_transient(
                "_html_exploration_scout_state",
                {"status": "ready", "detail": "", "results": []},
            )
            if operation == "scout_search":
                scout_form = normalise_scout_form(
                    payload, current_system=getattr(self, "current_sys", ""),
                )
                reference = scout_form["reference"]
                mode = scout_form["mode"]
                radius = scout_form["radius"]
                min_signals = scout_form["min_signals"]
                min_value = scout_form["min_value"]
                max_results = scout_form["max_results"]
                jump_range = scout_form["jump_range"]
                if not reference:
                    return False
                profile = get_active_profile(self.config)
                generation = time.time_ns()
                scout.update({
                    "generation": generation,
                    "mode": mode,
                    "status": "working",
                    "detail": f"Searching known {SCOUT_MODES[mode].lower()} near {reference}…",
                    "results": [], "source": "", "evidence_note": "",
                    "searched_at": "", "catalogue_count": 0,
                })
                self.config["exploration_scout_form"] = scout_form
                self._persist_config()
                self.add_event_feed_entry(
                    "SCOUT", f"Prospect search started near {reference}: {SCOUT_MODES[mode]}",
                    severity="INFO",
                )
                self._schedule_html_dashboard_publish(immediate=True)

                def worker():
                    try:
                        if mode == "value":
                            systems = riches_route(
                                reference, jump_range=jump_range, radius=radius,
                                max_results=max_results,
                                max_distance=max(radius, radius * max_results),
                                min_value=min_value, loop=True,
                            )
                            result = normalise_value_route(systems, reference=reference)
                        else:
                            result = exploration_body_search(
                                reference, mode, max_distance=radius,
                                min_signals=min_signals, max_results=max_results,
                            )
                        error = None
                    except Exception as exc:
                        result, error = None, exc

                    def finish():
                        active = self._html_profile_transient(
                            "_html_exploration_scout_state", {},
                        )
                        if active.get("profile") != profile or active.get("generation") != generation:
                            return
                        if error is not None:
                            detail = (
                                str(error) if isinstance(error, SpanshError)
                                else f"Unexpected Exploration Scout error: {error}"
                            )
                            active.update({
                                "status": "failed", "detail": detail, "results": [],
                                "source": "", "evidence_note": "", "searched_at": "",
                                "catalogue_count": 0,
                            })
                            self.add_event_feed_entry(
                                "SCOUT", f"Prospect search failed: {detail}", severity="WARN",
                            )
                        else:
                            rows = list(result.get("results") or [])
                            active.update({
                                "status": "ready",
                                "mode": mode,
                                "detail": f"{len(rows):,} prospects ranked near {result.get('reference') or reference}.",
                                "results": rows,
                                "source": result.get("source") or "Spansh",
                                "evidence_note": result.get("evidence_note") or "",
                                "searched_at": result.get("searched_at") or "",
                                "catalogue_count": result.get("catalogue_count") or 0,
                            })
                            self.add_event_feed_entry(
                                "SCOUT", f"Prospect search ready: {len(rows):,} results",
                                severity="INFO",
                            )
                        self._schedule_html_dashboard_publish(immediate=True)

                    self._ui_post(finish, key="html-exploration-scout")

                threading.Thread(
                    target=worker, name="HtmlExplorationScout", daemon=True,
                ).start()
                return True

            if operation == "scout_clear":
                scout.update({
                    "status": "ready", "detail": "Prospect results cleared.",
                    "results": [], "source": "", "evidence_note": "",
                    "searched_at": "", "catalogue_count": 0,
                })
                self._schedule_html_dashboard_publish(immediate=True)
                return True

            result_index = _integer(payload.get("result_index"), -1)
            results = scout.get("results") or []
            if not 0 <= result_index < len(results) or not isinstance(results[result_index], dict):
                return False
            result = results[result_index]
            system = _text(result.get("system"), 140)
            body = _text(result.get("body"), 180)
            if not system:
                return False
            if operation == "scout_copy":
                return self._html_copy_text(system)
            if operation == "scout_open":
                target = result.get("system_id64") or quote(system, safe="")
                webbrowser.open_new_tab(f"https://spansh.co.uk/system/{target}")
                return True
            if operation == "scout_add_waypoint":
                manager = getattr(self, "waypoint_manager", None)
                if manager is None:
                    return False
                coords = result.get("coords")
                if not isinstance(coords, list) or len(coords) != 3 or any(value is None for value in coords):
                    coords = None
                reasons = "; ".join(result.get("reasons") or [])
                manager.add_waypoint(
                    system, coords,
                    _text(f"Exploration Scout · {body or SCOUT_MODES.get(scout_mode(scout.get('mode')), 'prospect')} · {reasons}", 1000),
                )
                self.add_event_feed_entry("SCOUT", f"Added route prospect: {system}", severity="INFO")
                self.update_hud()
                self._schedule_html_dashboard_publish(immediate=True)
                return True
            if operation == "scout_add_objective":
                expedition_manager = getattr(self, "expedition_manager", None)
                active = expedition_manager.active() if expedition_manager is not None else None
                if not active:
                    return False
                objective = expedition_manager.add_objective(
                    active.get("id"), "destination", target=body or system,
                    system=system, body=body, count=1,
                    notes=_text(
                        "Exploration Scout · " + "; ".join(result.get("reasons") or []),
                        1000,
                    ),
                )
                if not objective:
                    return False
                self.add_event_feed_entry(
                    "EXPEDITION", f"Scout objective added: {body or system}", severity="INFO",
                )
                self._schedule_html_dashboard_publish(immediate=True)
                return True
            return False
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

        if changed:
            # Waypoint edits are profile-local rather than journal events, so
            # explicitly republish the cockpit route immediately.
            self.update_hud()
            self._schedule_html_dashboard_publish(immediate=True)
        return bool(changed)
