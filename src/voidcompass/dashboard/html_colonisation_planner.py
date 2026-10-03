"""The Colonisation tab's system planner (5.5.2.1): a system's sites from
Raven Colonial, edited here, with the website's economy, tier point, score
and unlock model (colonisation.planner) worked out as you change them.

The draft lives on this side (``_colony_ui_state()["planner"]``); the page
sends one change at a time and redraws from the snapshot. Nothing reaches
Raven Colonial until SAVE (or SAVE AS for a named copy), apart from body
features, which the website also saves at once. The station identifier
(colonisation.identifier) works on the same draft.
"""

from __future__ import annotations

import copy
import time
import webbrowser

from voidcompass.colonisation import identifier, planner
from voidcompass.services.raven_colonial import system_url

_SITE_FIELDS = {"name": 120, "bodyNum": None, "buildType": 60, "status": 20}
_TEXT_FIELDS = {"architect": 80, "nickname": 80, "notes": 4000}


def _text(value, limit=200):
    return str(value if value is not None else "").strip()[:limit]


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class HtmlColonisationPlannerMixin:
    # -- state -----------------------------------------------------------
    def _planner_state(self):
        return self._colony_ui_state().get("planner")

    def _planner_from_system(self, data, *, rev=None, save_name=None):
        """A fresh draft from a system the service returned."""
        data = copy.deepcopy(data if isinstance(data, dict) else {})
        sites = [dict(site) for site in data.get("sites") or () if isinstance(site, dict)]
        state = {
            "name": data.get("name") or "", "id64": data.get("id64"), "original": data,
            "sites": sites, "bodies": list(data.get("bodies") or ()), "slots": dict(data.get("slots") or {}),
            "dirty": set(), "deleted": [], "idx_calc_limit": data.get("idxCalcLimit"),
            "fields": {"architect": data.get("architect") or "", "reserveLevel": data.get("reserveLevel") or "",
                       "open": bool(data.get("open")), "nickname": data.get("nickname") or "",
                       "notes": data.get("notes") or ""},
            "revs": list(data.get("revs") or ()), "saved_names": list(data.get("savedNames") or ()),
            "rev": data.get("rev"), "viewing_rev": rev, "save_name": save_name or data.get("saveName"),
            "pop": data.get("pop"), "fav": None, "pop_history": None,
            "loaded_at": time.time(), "revision": 0, "identify": {"active": False},
        }
        if state["idx_calc_limit"] is None:
            state["idx_calc_limit"] = len(sites)
        return state

    def _planner_changed(self, state):
        state["revision"] += 1
        state.pop("_model", None)

    def _planner_system(self, state):
        """The draft as a system the planner model (and snapshot) takes."""
        system = dict(state["original"])
        system.update(sites=[dict(site) for site in state["sites"]], bodies=state["bodies"],
                      idxCalcLimit=state["idx_calc_limit"], architect=state["fields"]["architect"] or None,
                      reserveLevel=state["fields"]["reserveLevel"] or None)
        return system

    def _planner_model(self, state):
        cached = state.get("_model")
        options = (bool(self.config.get("colony_planner_include_planned", False)),
                   bool(self.config.get("colony_planner_buff_nerf", True)))
        if cached and cached[0] == (state["revision"], options):
            return cached[1]
        model = planner.build_model(self._planner_system(state), *options)
        state["_model"] = ((state["revision"], options), model)
        return model

    def _planner_can_edit(self, state):
        architect = state["fields"]["architect"] or state["original"].get("architect") or ""
        original_architect = state["original"].get("architect") or ""
        return bool(state["original"].get("open") or not original_architect
                    or original_architect.casefold() == self._colony_cmdr().casefold() or not architect)

    # -- snapshot --------------------------------------------------------
    def _planner_snapshot(self):
        ui = self._colony_ui_state()
        state = ui.get("planner")
        journal = getattr(self, "colony_journal", None)
        base = {"mine": ui.get("planner_mine"), "system_hint": ui.get("planner_system") or getattr(self, "current_sys", "") or ""}
        if not state:
            return {**base, "loaded": False}
        model = self._planner_model(state)
        types = []
        for row in planner.site_types():
            if row["buildClass"] == "unknown":
                continue
            validity = planner.type_validity(model, row)
            types.append({"name": row["displayName2"], "class": row["buildClass"], "tier": row["tier"],
                          "orbital": row["orbital"], "layouts": row["subTypes"], "needs": row["needs"],
                          "gives": row["gives"], "inf": row["inf"], "pad": row["padSize"],
                          "score": row.get("score", 0) or 0, "pre_req_ok": validity["valid"] or validity["message"].startswith("Not enough"),
                          "pre_req": validity["message"] if not validity["message"].startswith("Not enough") else "",
                          "unlocks": row.get("unlocks") or [], "effects": {k: v for k, v in (row.get("effects") or {}).items() if v}})
        bodies = []
        for body in model["bodies"]:
            slots = state["slots"].get(str(body["num"])) or state["slots"].get(body["num"]) or [-1, -1]
            raw = next((item for item in state["bodies"] if item.get("num") == body["num"]), {})
            bodies.append({**body, "type_name": planner.BODY_TYPE_NAMES.get(body["type"], body["type"]),
                           "slots": list(slots), "predicted_surface": planner.predict_surface_slots(raw),
                           "sites": sum(1 for site in model["sites"] if site["body_num"] == body["num"])})
        at_system = bool(journal and journal.address is not None and str(journal.address) == str(state["id64"]))
        projects = {project.get("buildId"): project for project in getattr(self.colony, "projects", ()) or ()}
        sites = []
        for index, site in enumerate(model["sites"]):
            build = projects.get(site["build_id"]) if site["build_id"] else None
            sites.append({**site, "index": index, "dirty": site["id"] in state["dirty"],
                          "project": {"name": build.get("buildName"), "remaining": sum(int(v or 0) for v in (build.get("commodities") or {}).values()),
                                      "max_need": int(build.get("maxNeed") or 0)} if build else None})
        planned = [site["build_type"] for site in model["sites"] if site["status"] in ("plan", "build") and site["build_type"]]
        return {
            **base, "loaded": True, "name": state["name"], "id64": state["id64"], "url": system_url(state["name"]),
            "fields": state["fields"], "can_edit": self._planner_can_edit(state),
            "dirty": bool(state["dirty"] or state["deleted"] or self._planner_fields_changed(state)),
            "idx_calc_limit": state["idx_calc_limit"], "revs": state["revs"][:12], "saved_names": state["saved_names"],
            "rev": state["rev"], "viewing_rev": state["viewing_rev"], "save_name": state["save_name"],
            "pop": state["pop"], "pop_history": state["pop_history"], "fav": state["fav"],
            "model": {key: model[key] for key in ("score", "tier_points", "tax_count", "effects", "economies", "unlocks",
                                                   "use_incomplete", "buff_nerf")},
            "unlock_info": planner.system_unlocks(), "effect_names": planner.EFFECT_NAMES, "economy_names": planner.ECONOMY_NAMES,
            "sites": sites, "bodies": bodies, "types": types, "statuses": list(planner.STATUSES),
            "reserves": list(planner.RESERVE_LEVELS), "features": list(planner.BODY_FEATURES),
            "haul_planned": planner.haul_estimate(planned),
            "journal": journal.status() if at_system else None,
            "identify": {key: value for key, value in (state.get("identify") or {}).items() if key != "pending"}
            | {"pending_name": next((site["name"] for site in state["sites"] if site["id"] == (state.get("identify") or {}).get("pending")), None)},
        }

    def _planner_fields_changed(self, state):
        original = state["original"]
        fields = state["fields"]
        return any(str(fields[key] or "") != str(original.get(key) or "") for key in ("architect", "reserveLevel", "nickname", "notes")) \
            or bool(fields["open"]) != bool(original.get("open"))

    # -- commands --------------------------------------------------------
    def _handle_planner_command(self, operation, payload, ui):
        raven = self.raven
        state = ui.get("planner")
        if operation == "planner_load":
            system = _text(payload.get("system"), 160) or getattr(self, "current_sys", "") or ""
            if not system:
                ui["error"] = "Enter a system name."
                return True
            ui["planner_system"] = system
            rev, save_name = payload.get("rev"), _text(payload.get("save_name"), 80)

            def fetch():
                if rev not in (None, ""):
                    return raven.system_revision(system, _integer(rev))
                if save_name:
                    return raven.system_named_save(system, save_name)
                return raven.system(system)

            def loaded(data):
                if not data:
                    ui["error"] = f"Raven Colonial has no plan for {system} yet: import its bodies to start one."
                    ui["planner"] = None
                    ui["planner_missing"] = system
                    return
                ui["planner"] = self._planner_from_system(data, rev=_integer(rev) if rev not in (None, "") else None,
                                                          save_name=save_name or None)
                self._planner_check_snapshot(ui["planner"])
            return self._raven_call(fetch, loaded, label="System plan")
        if operation == "planner_mine":
            def mine(rows):
                ui["planner_mine"] = sorted(({"name": row.get("name"), "id64": row.get("id64"), "score": row.get("score"),
                                              "nickname": row.get("nickname"), "fav": bool(row.get("fav")),
                                              "tier_points": row.get("tierPoints"), "stale": bool(row.get("stale"))}
                                             for row in rows or () if isinstance(row, dict)),
                                            key=lambda row: (not row["fav"], str(row["name"]).casefold()))
            return self._raven_call(raven.system_snapshots, mine, label="Your systems")
        if operation == "planner_import" and payload.get("system"):
            system = _text(payload.get("system"), 160)
            kind = "bodies" if payload.get("kind") == "bodies" else ""

            def imported(data):
                ui["planner"] = self._planner_from_system(data or {})
                ui["notice"] = "Imported from Spansh."
            return self._raven_call(lambda: raven.import_system(system, kind), imported, label="Import")
        if not state:
            return False
        if operation == "planner_site":
            site = next((row for row in state["sites"] if row.get("id") == payload.get("id")), None)
            field = payload.get("field")
            if site is None or field not in _SITE_FIELDS:
                return False
            value = payload.get("value")
            if field == "bodyNum":
                value = _integer(value, -1)
            elif field == "status":
                value = value if value in planner.STATUSES else "plan"
            elif field == "buildType":
                value = _text(value, 60).casefold()
            else:
                value = _text(value, _SITE_FIELDS[field])
            site[field] = value
            state["dirty"].add(site["id"])
            self._planner_changed(state)
            return True
        if operation == "planner_add":
            site = {"id": f"x{int(time.time() * 1000)}", "name": _text(payload.get("name"), 120) or f"Site {len(state['sites']) + 1}",
                    "bodyNum": _integer(payload.get("body_num"), -1), "buildType": _text(payload.get("build_type"), 60).casefold(),
                    "status": "plan", "buildId": None, "marketId": None}
            if not state["sites"]:
                site["name"] = _text(payload.get("name"), 120) or "Primary port"
            identifier._insert_site(state, site)
            self._planner_changed(state)
            return True
        if operation == "planner_remove":
            index = next((i for i, row in enumerate(state["sites"]) if row.get("id") == payload.get("id")), None)
            if index is None:
                return False
            site = state["sites"].pop(index)
            if any(row.get("id") == site["id"] for row in state["original"].get("sites") or ()):
                state["deleted"].append(site["id"])
            state["dirty"].discard(site["id"])
            if state["idx_calc_limit"] is not None and index < state["idx_calc_limit"]:
                state["idx_calc_limit"] -= 1
            self._planner_changed(state)
            return True
        if operation == "planner_move":
            index = next((i for i, row in enumerate(state["sites"]) if row.get("id") == payload.get("id")), None)
            if index is None:
                return False
            target = max(0, min(len(state["sites"]) - 1, _integer(payload.get("to"), index)))
            site = state["sites"].pop(index)
            state["sites"].insert(target, site)
            self._planner_changed(state)
            return True
        if operation == "planner_cut":
            state["idx_calc_limit"] = max(0, min(len(state["sites"]), _integer(payload.get("index"), len(state["sites"]))))
            self._planner_changed(state)
            return True
        if operation == "planner_field":
            field = payload.get("field")
            if field in _TEXT_FIELDS:
                state["fields"][field] = _text(payload.get("value"), _TEXT_FIELDS[field])
            elif field == "reserveLevel":
                value = _text(payload.get("value"), 20)
                state["fields"]["reserveLevel"] = value if value in planner.RESERVE_LEVELS else ""
            elif field == "open":
                state["fields"]["open"] = bool(payload.get("value"))
            else:
                return False
            self._planner_changed(state)
            return True
        if operation == "planner_option":
            key = {"use_incomplete": "colony_planner_include_planned", "buff_nerf": "colony_planner_buff_nerf"}.get(payload.get("field"))
            if not key:
                return False
            self.config[key] = bool(payload.get("value"))
            self._persist_config()
            return True
        if operation == "planner_discard":
            state_name = state["name"]
            return self._handle_planner_command("planner_load", {"system": state_name}, ui)
        if operation == "planner_save":
            return self._planner_save(state, ui, _text(payload.get("save_name"), 80) or None)
        if operation == "planner_delete_save":
            name = _text(payload.get("save_name"), 80)
            system = state["name"]

            def removed(_result):
                state["saved_names"] = [row for row in state["saved_names"] if row.get("name") != name]
                ui["notice"] = f"Deleted the named save '{name}'."
            return bool(name) and self._raven_call(lambda: raven.delete_system_named_save(system, name), removed, label="Delete save")
        if operation == "planner_body_features":
            num = _integer(payload.get("num"), -1)
            features = [item for item in payload.get("features") or () if item in planner.BODY_FEATURES]
            system = state["name"]

            def saved(bodies):
                if bodies:
                    state["bodies"] = bodies
                    self._planner_changed(state)
            return self._raven_call(lambda: raven.set_body_features(system, num, features), saved, label="Body features")
        if operation == "planner_slots":
            num = str(_integer(payload.get("num"), -1))
            orbital = _integer(payload.get("orbital"), -1)
            surface = _integer(payload.get("surface"), -1)
            state["slots"][num] = [orbital, surface]
            state["slots_changed"] = True
            self._planner_changed(state)
            return True
        if operation == "planner_upload_bodies":
            journal = getattr(self, "colony_journal", None)
            if not journal or str(journal.address) != str(state["id64"]) or not journal.ready_to_upload():
                ui["error"] = "Complete the FSS here (every body scanned) before sending your scans."
                return True
            bodies, address, system = journal.raven_bodies(), journal.address, state["name"]

            def uploaded(result):
                if result:
                    state["bodies"] = result
                    self._planner_changed(state)
                ui["notice"] = f"Sent {len(bodies)} bodies from your scans to Raven Colonial."
                identifier.step(state, journal)
            return self._raven_call(lambda: raven.update_system_bodies(address, bodies), uploaded, label="Upload bodies")
        if operation == "planner_pop":
            id64 = state["id64"]

            def got(result):
                if isinstance(result, dict) and "history" in result:
                    state["pop_history"] = [{"time": row.get("time"), "pop": _pop_of(row)} for row in result["history"]]
                if isinstance(result, dict) and result.get("pop"):
                    state["pop"] = result["pop"]

            def fetch():
                pop = raven.refresh_population(id64) if payload.get("refresh") else None
                return {"pop": pop, "history": raven.population_history(id64)}
            return self._raven_call(fetch, got, label="Population")
        if operation == "planner_fav":
            value, id64 = bool(payload.get("value")), state["id64"]

            def done(_result):
                state["fav"] = value
            return self._raven_call(lambda: raven.set_system_favourite(id64, value), done, label="Favourite")
        if operation == "planner_start_project":
            site = next((row for row in state["sites"] if row.get("id") == payload.get("id")), None)
            if site is None or site["id"].startswith(("x", "y")):
                ui["error"] = "Save the plan first, so the site exists on Raven Colonial."
                return True
            id64 = state["id64"]

            def created(project):
                if isinstance(project, dict) and project.get("buildId"):
                    ui["selected"] = project["buildId"]
                    ui["notice"] = f"Project started: {project.get('buildName')}."
                self._colony_refresh()
            return self._raven_call(lambda: raven.create_project_from_site(id64, site["id"], site.get("buildType") or ""),
                                    created, pending={}, label="Start project")
        if operation == "planner_open":
            webbrowser.open_new_tab(system_url(state["name"]))
            return True
        if operation == "planner_identify":
            action = payload.get("action")
            if action == "start":
                identifier.start(state)
                identifier.step(state, self.colony_journal)
            elif action == "finish":
                identifier.finish(state)
            else:
                identifier.stop(state)
            self._planner_changed(state)
            return True
        return False

    def _planner_save(self, state, ui, save_name):
        if not self._planner_can_edit(state) and not save_name:
            ui["error"] = "Only the architect can save this system: use SAVE AS for a named copy."
            return True
        raven = self.raven
        sites_by_id = {row["id"]: row for row in state["sites"]}
        put = {
            "update": [dict(sites_by_id[site_id]) for site_id in state["dirty"] if site_id in sites_by_id],
            "delete": list(state["deleted"]),
            "orderIDs": [row["id"] for row in state["sites"]],
            "idxCalcLimit": state["idx_calc_limit"],
            "notes": state["fields"]["notes"] or None,
            "saveName": save_name,
        }
        original = state["original"]
        for key in ("architect", "reserveLevel", "nickname"):
            if str(state["fields"][key] or "") != str(original.get(key) or ""):
                put[key] = state["fields"][key] or None
        if bool(state["fields"]["open"]) != bool(original.get("open")):
            put["open"] = bool(state["fields"]["open"])
        if state.get("slots_changed"):
            put["slots"] = state["slots"]
        if state["fields"]["architect"]:
            put["snapshot"] = planner.snapshot(self._planner_system(state), state.get("fav"))
        system = str(state["id64"] or state["name"])
        identify = state.get("identify")

        def saved(data):
            fresh = self._planner_from_system(data or {}, save_name=save_name)
            fresh["identify"] = identify or {"active": False}
            ui["planner"] = fresh
            ui["notice"] = f"Saved as '{save_name}'." if save_name else "System plan saved to Raven Colonial."
        return self._raven_call(lambda: raven.update_system(system, put), saved, label="Save system plan")

    def _planner_check_snapshot(self, state):
        """As the website does: keep the architect's snapshot current."""
        cmdr = self._colony_cmdr()
        architect = state["original"].get("architect") or ""
        if not self._raven_active() or not cmdr or architect.casefold() != cmdr.casefold() or state.get("viewing_rev") or state.get("save_name"):
            return
        raven, id64 = self.raven, state["id64"]
        fresh = planner.snapshot(state["original"])

        def check():
            try:
                current = raven.system_snapshot(id64, architect)
            except Exception:
                current = None
            stale = (not current or current.get("stale") or current.get("score") != fresh["score"]
                     or current.get("sumEffects") != fresh["sumEffects"])
            if current:
                fresh["fav"] = current.get("fav")
            if stale:
                raven.save_system_snapshot(id64, fresh)
            return current.get("fav") if current else None

        def done(fav):
            state["fav"] = fav
        self._raven_call(check, done, label="System snapshot")

    # -- the journal -----------------------------------------------------
    def _planner_on_journal(self, event, raw):
        state = self._planner_state()
        if not state or not (state.get("identify") or {}).get("active"):
            return
        journal = self.colony_journal
        if event == "Docked" and str(raw.get("SystemAddress")) == str(state["id64"]):
            identifier.apply_docked(state, raw)
        identifier.step(state, journal)
        self._planner_changed(state)
        self._schedule_html_dashboard_publish()

    def _planner_on_destination(self, destination):
        state = self._planner_state()
        if not state or not (state.get("identify") or {}).get("active"):
            return
        if identifier.on_destination(state, self.colony_journal, destination):
            identifier.step(state, self.colony_journal)
            self._planner_changed(state)
            self._schedule_html_dashboard_publish(immediate=True)


def _pop_of(row):
    import json as _json
    try:
        data = _json.loads(row.get("json") or "{}")
    except ValueError:
        return None
    return data.get("pop") if isinstance(data, dict) else data
