"""The Colonisation tab (5.5.2): projects, the construction site you are
docked at, fleet carriers, system sites and the journal's own record.

Raven Colonial data comes from colonisation.colony (synced by
DashboardColonisationMixin); everything here also works from the journal
alone when no Raven Colonial key is set.
"""

from __future__ import annotations

import math
import time
import webbrowser

from voidcompass.colonisation import catalogue
from voidcompass.colonisation.views import project_rows
from voidcompass.services.raven_colonial import SITE_URL, project_url, system_url

_SITE_STATUSES = ("plan", "build", "complete", "demolish")
_RESERVE_LEVELS = ("", "depleted", "low", "common", "major", "pristine")


def _text(value, limit=200):
    return str(value if value is not None else "").strip()[:limit]


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class HtmlColonisationMixin:
    def _colony_ui_state(self):
        return self._html_profile_transient("_html_colonisation_state", {
            "selected": None, "site_plans": None, "site_plans_system": "",
            "architect": None, "architect_system": "", "notice": "", "error": "",
        })

    # -- snapshot --------------------------------------------------------
    def _html_colonisation_workspace(self):
        colony = getattr(self, "colony", None)
        ui = self._colony_ui_state()
        capacity = int(self._active_cargo_capacity() or 0)
        cmdr = self._colony_cmdr()
        has_key = bool(str(self.config.get("raven_api_key") or "").strip())
        data = {
            "raven": {
                "has_key": has_key, "sync": bool(self.config.get("raven_sync_enabled", True)),
                "active": self._raven_active(), "cmdr": cmdr, "site": SITE_URL,
                "synced_at": getattr(colony, "synced_at", 0) or 0,
                "error": getattr(colony, "sync_error", "") or "", "pending": bool(getattr(colony, "pending", 0)),
            },
            "capacity": capacity, "notice": ui.get("notice") or "", "error": ui.get("error") or "",
            "projects": [], "totals": {}, "selected": None, "site": None,
            "carriers": [], "local": self._colony_local_projects(),
            "build_types": [{"build_type": row.get("buildType"), "name": row.get("displayName"), "tier": row.get("tier"),
                             "location": row.get("location"), "layouts": list(row.get("layouts") or ())}
                            for row in catalogue.build_types()],
            "architect": ui.get("architect"), "architect_system": ui.get("architect_system") or getattr(self, "current_sys", "") or "",
        }
        if colony is None:
            return data
        rows = project_rows(colony, capacity)
        data["projects"] = rows
        remaining = sum(row["remaining"] for row in rows if row["visible"] and not row["complete"])
        data["totals"] = {"remaining": remaining, "trips": math.ceil(remaining / capacity) if capacity and remaining else None,
                          "visible": sum(1 for row in rows if row["visible"])}
        selected_id = ui.get("selected") or colony.primary_build_id or (rows[0]["build_id"] if rows else None)
        project = colony.project(selected_id)
        if project:
            data["selected"] = self._colony_project_detail(project, cmdr)
        data["carriers"] = [{
            "market_id": carrier.get("marketId"), "name": carrier.get("name") or "",
            "display_name": carrier.get("displayName") or "",
            "cargo_total": sum(int(value or 0) for value in (carrier.get("cargo") or {}).values()),
            "cargo": sorted(({"id": key, "name": catalogue.commodity_name(key), "count": int(value or 0)}
                             for key, value in (carrier.get("cargo") or {}).items() if int(value or 0)),
                            key=lambda item: item["name"].casefold()),
        } for carrier in colony.carriers.values()]
        data["site"] = self._colony_site_snapshot(ui)
        return data

    def _colony_project_detail(self, project, cmdr):
        colony = self.colony
        ship = {}
        for row in getattr(self, "current_cargo_inventory", None) or ():
            if isinstance(row, dict):
                name = catalogue.commodity_id(row.get("Name"))
                ship[name] = ship.get(name, 0) + int(row.get("Count") or 0)
        carrier_ids = {str(fc.get("marketId")) for fc in project.get("linkedFC") or ()}
        fc_cargo = colony.carrier_cargo(carrier_ids) if carrier_ids else {}
        needs = colony.needs([project], cmdr)
        commanders = project.get("commanders") or {}
        groups = {}
        for name, need in (project.get("commodities") or {}).items():
            name = catalogue.commodity_id(name)
            need = int(need or 0)
            if need <= 0:
                continue
            assigned = sorted(who for who, items in commanders.items()
                              if name in {catalogue.commodity_id(item) for item in items or ()})
            groups.setdefault(catalogue.commodity_category(name), []).append({
                "id": name, "name": catalogue.commodity_name(name), "need": need,
                "fc": fc_cargo.get(name, 0), "ship": ship.get(name, 0), "assigned": assigned,
                "mine": name in needs["assigned_me"], "ready": name in set(project.get("ready") or ()),
            })
        me = cmdr.casefold()
        return {
            "build_id": project.get("buildId"), "name": project.get("buildName") or "Project",
            "type": catalogue.build_type_label(project.get("buildType")), "build_type": project.get("buildType") or "",
            "system": project.get("systemName") or "", "body": project.get("bodyName") or "",
            "faction": project.get("factionName") or "", "architect": project.get("architectName") or "",
            "notes": project.get("notes") or "", "discord": project.get("discordLink") or "",
            "max_need": int(project.get("maxNeed") or 0),
            "remaining": sum(int(value or 0) for value in (project.get("commodities") or {}).values()),
            "complete": bool(project.get("complete")), "primary": project.get("buildId") == colony.primary_build_id,
            "visible": project.get("buildId") not in set(colony.hidden_ids),
            "url": project_url(project.get("buildId")), "system_url": system_url(project.get("systemName")),
            "groups": [{"name": name, "rows": sorted(rows, key=lambda row: row["name"].casefold())}
                       for name, rows in sorted(groups.items(), key=lambda item: item[0].casefold())],
            "commanders": [{"name": who, "assigned": [catalogue.commodity_name(item) for item in items or ()], "me": who.casefold() == me}
                           for who, items in sorted(commanders.items(), key=lambda item: item[0].casefold())],
            "member": any(who.casefold() == me for who in commanders),
            "carriers": [{"market_id": fc.get("marketId"), "name": fc.get("name") or "", "display_name": fc.get("displayName") or ""}
                         for fc in project.get("linkedFC") or ()],
        }

    def _colony_site_snapshot(self, ui):
        docked = getattr(self, "_colony_docked", None)
        if not docked:
            return None
        colony = self.colony
        at_site = catalogue.is_construction_site(docked["station_name"], docked["services"])
        at_carrier = str(docked.get("station_type") or "").casefold() == "fleetcarrier"
        if not at_site and not at_carrier:
            return None
        site = {"station": docked["station_name"], "system": docked["system_name"], "market_id": docked["market_id"],
                "at_site": at_site, "at_carrier": at_carrier,
                "carrier_linked": colony.has_carrier(docked["market_id"]) if at_carrier else False}
        if not at_site:
            return site
        project = colony.project_at(docked["system_address"], docked["market_id"])
        depot = colony.last_depot if colony.last_depot and str(colony.last_depot.get("MarketID")) == str(docked["market_id"]) else None
        site.update({
            "name": catalogue.default_project_name(docked["station_name"]),
            "primary_port": catalogue.is_primary_port_site(docked["station_name"]),
            "tracked": bool(project), "build_id": (project or {}).get("buildId"),
            "untracked": bool(colony.untracked_project), "untracked_name": (colony.untracked_project or {}).get("buildName") or "",
            "untracked_id": (colony.untracked_project or {}).get("buildId"),
            "depot_known": bool(depot),
            "needs": [{"id": key, "name": catalogue.commodity_name(key), "need": value}
                      for key, value in sorted(catalogue.depot_needs((depot or {}).get("ResourcesRequired")).items(),
                                               key=lambda item: catalogue.commodity_name(item[0]).casefold()) if value],
            "suggested_type": (catalogue.match_by_cargo(catalogue.depot_needs((depot or {}).get("ResourcesRequired"))) or {}).get("buildType") if depot else None,
            "orbital": not bool(getattr(self, "current_body_name", None)),
            "bodies": [{"id": item.get("body_id"), "name": item.get("name") or ""}
                       for item in getattr(self, "scan_items", None) or ()
                       if isinstance(item, dict) and item.get("body_id") is not None and not item.get("is_belt")],
            "body_id": getattr(self, "current_body_id", None),
            "architect": self._colony_cmdr(),
            "site_plans": [plan for plan in ui.get("site_plans") or () if plan.get("status") == "plan"]
            if ui.get("site_plans_system") == docked["system_name"] else None,
        })
        return site

    def _colony_local_projects(self):
        """Construction depots seen in this commander's journal."""
        rows = []
        for market_id, project in (getattr(self, "colonisation_projects", None) or {}).items():
            if not isinstance(project, dict):
                continue
            resources = []
            for row in project.get("resources") or ():
                required, provided = int(row.get("required") or 0), int(row.get("provided") or 0)
                resources.append({"id": catalogue.commodity_id(row.get("name")),
                                  "name": catalogue.commodity_name(row.get("name")),
                                  "required": required, "provided": provided, "need": max(0, required - provided)})
            rows.append({
                "market_id": market_id, "name": project.get("site_name") or project.get("body_name") or "Construction site",
                "system": project.get("system_name") or "", "progress": float(project.get("progress") or 0),
                "complete": bool(project.get("complete")), "failed": bool(project.get("failed")),
                "remaining": sum(row["need"] for row in resources),
                "resources": sorted(resources, key=lambda row: (not row["need"], row["name"].casefold())),
                "last_updated": project.get("last_updated") or 0,
                "activity": list(project.get("activity") or ())[-8:],
            })
        return sorted(rows, key=lambda row: (row["complete"], -float(row["last_updated"] or 0)))

    # -- commands --------------------------------------------------------
    def _handle_colonisation_command(self, operation, payload):
        ui = self._colony_ui_state()
        ui["notice"], ui["error"] = "", ""
        colony = getattr(self, "colony", None)
        if colony is None:
            return False
        cmdr = self._colony_cmdr()
        raven = self.raven
        build_id = _text(payload.get("build_id"), 80) or None
        if operation == "select":
            ui["selected"] = build_id
            return True
        if operation == "open_raven":
            webbrowser.open_new_tab(project_url(build_id) if build_id else SITE_URL)
            return True
        if operation == "open_system":
            webbrowser.open_new_tab(system_url(_text(payload.get("system"), 120)))
            return True
        if not self._raven_active():
            ui["error"] = "Add your Raven Colonial key in Settings > Integrations (and leave sync on) first."
            return True
        if operation == "refresh":
            return self._colony_refresh()
        if operation == "set_primary":
            primary = None if colony.primary_build_id == build_id else build_id
            return self._raven_call(lambda: raven.set_primary(cmdr, primary),
                                    lambda _r: (setattr(colony, "primary_build_id", primary), colony.save()), pending={})
        if operation == "toggle_visible" and build_id:
            hidden = set(colony.hidden_ids)
            hidden.symmetric_difference_update({build_id})
            return self._raven_call(lambda: raven.set_hidden_ids(cmdr, sorted(hidden)),
                                    lambda ids: colony.apply_sync(hidden=ids), pending={})
        if operation in {"assign", "unassign"} and build_id:
            commodity = catalogue.commodity_id(payload.get("commodity"))
            call = raven.assign if operation == "assign" else raven.unassign
            return self._raven_call(lambda: call(build_id, cmdr, commodity), lambda _r: self._colony_refresh(build_id), pending={})
        if operation in {"join", "leave"} and build_id:
            call = raven.link_commander if operation == "join" else raven.unlink_commander
            return self._raven_call(lambda: call(build_id, cmdr), lambda _r: self._colony_refresh(), pending={})
        if operation == "save_details" and build_id:
            fields = {key: _text(payload.get(source), limit) for key, source, limit in (
                ("buildName", "name", 120), ("notes", "notes", 2000), ("architectName", "architect", 80),
                ("factionName", "faction", 120)) if source in payload}
            return self._raven_call(lambda: raven.update_project(build_id, fields), colony.replace_project, pending={})
        if operation == "complete" and build_id and payload.get("confirmed"):
            return self._raven_call(lambda: raven.complete_project(build_id), lambda _r: self._colony_refresh(), pending={})
        if operation == "load_site_plans":
            system = _text(getattr(self, "_colony_docked", None) and self._colony_docked.get("system_name"), 160)
            if not system:
                return False

            def plans(sites):
                ui["site_plans"], ui["site_plans_system"] = list(sites or ()), system
            return self._raven_call(lambda: raven.system_sites(system), plans)
        if operation == "create_project":
            return self._colony_create_project(payload, ui)
        if operation == "link_carrier":
            return self._colony_link_docked_carrier(ui)
        if operation == "unlink_carrier":
            market_id = _integer(payload.get("market_id"), 0)
            return bool(market_id) and self._raven_call(lambda: raven.unlink_carrier(cmdr, market_id),
                                                        lambda _r: self._colony_refresh(), pending={})
        if operation == "link_project_carrier" and build_id:
            market_id = _integer(payload.get("market_id"), 0)
            return bool(market_id) and self._raven_call(lambda: raven.link_project_carrier(build_id, market_id),
                                                        lambda _r: self._colony_refresh(build_id), pending={})
        if operation == "architect_load":
            system = _text(payload.get("system"), 160) or getattr(self, "current_sys", "")
            ui["architect_system"] = system

            def loaded(data):
                ui["architect"] = self._colony_architect_model(data, system)
            return self._raven_call(lambda: raven.system(system), loaded, label="System sites")
        if operation == "architect_import_bodies":
            system = _text(payload.get("system"), 160) or ui.get("architect_system")

            def imported(data):
                ui["architect"] = self._colony_architect_model(data, system)
                ui["notice"] = "Bodies imported."
            return bool(system) and self._raven_call(lambda: raven.import_system_bodies(system), imported, label="Import bodies")
        if operation == "architect_save":
            return self._colony_architect_save(payload, ui)
        return False

    def _colony_create_project(self, payload, ui):
        docked = getattr(self, "_colony_docked", None)
        colony = self.colony
        depot = colony.last_depot
        if not docked or not catalogue.is_construction_site(docked["station_name"], docked["services"]):
            ui["error"] = "Dock at a construction site to create its project."
            return True
        if not depot or str(depot.get("MarketID")) != str(docked["market_id"]):
            ui["error"] = "Open Construction Services first, so the site's needs are known."
            return True
        layout = _text(payload.get("layout"), 60).casefold()
        if catalogue.build_type_for(layout) is None:
            ui["error"] = "Choose a build type."
            return True
        cmdr = self._colony_cmdr()
        body_id = payload.get("body_id")
        body_id = None if body_id in (None, "", "-1", -1) else _integer(body_id, None)
        body_name = next((item.get("name") for item in getattr(self, "scan_items", None) or ()
                          if isinstance(item, dict) and item.get("body_id") == body_id), None)
        coords = list(getattr(self, "current_coords", None) or ())[:3]
        project = {
            "buildType": layout, "buildName": _text(payload.get("name"), 120) or catalogue.default_project_name(docked["station_name"]),
            "architectName": _text(payload.get("architect"), 80) or cmdr, "factionName": docked.get("faction") or "",
            "notes": _text(payload.get("notes"), 2000), "isPrimaryPort": catalogue.is_primary_port_site(docked["station_name"]),
            "marketId": docked["market_id"], "systemAddress": docked["system_address"], "systemName": docked["system_name"],
            "starPos": coords, "bodyNum": body_id, "bodyName": body_name,
            "commanders": {cmdr: []}, "systemSiteId": _text(payload.get("site_id"), 80) or None,
            "commodities": catalogue.depot_needs(depot.get("ResourcesRequired")),
            "maxNeed": catalogue.depot_total(depot.get("ResourcesRequired")),
            "colonisationConstructionDepot": depot,
        }
        raven = self.raven

        def created(result):
            if isinstance(result, dict) and result.get("buildId"):
                ui["selected"] = result["buildId"]
                ui["notice"] = f"Project created: {result.get('buildName')}."
            self._colony_refresh()
        return self._raven_call(lambda: raven.create_project(project), created, pending={}, label="Create project")

    def _colony_link_docked_carrier(self, ui):
        docked = getattr(self, "_colony_docked", None)
        if not docked or str(docked.get("station_type") or "").casefold() != "fleetcarrier":
            ui["error"] = "Dock at the fleet carrier to link it."
            return True
        cmdr, raven = self._colony_cmdr(), self.raven
        carrier = {"marketId": docked["market_id"], "name": docked["station_name"],
                   "displayName": self._colony_carrier_display_name(docked["station_name"]), "cargo": None}

        def link():
            raven.publish_carrier(carrier)
            raven.link_carrier(cmdr, carrier["marketId"])
            return True
        return self._raven_call(link, lambda _r: self._colony_refresh(), pending={}, label="Link carrier")

    def _colony_carrier_display_name(self, callsign):
        """A carrier's name from what the journal heard (SrvSurvey's way):
        a ReceiveText from it, or its FSS signal."""
        for signal in reversed(list(getattr(self, "deep_space_contacts", None) or ())):
            name = str((signal or {}).get("name") or "")
            if name.endswith(callsign) and name != callsign:
                return name[: -len(callsign)].strip(" |")
        return ""

    def _colony_architect_model(self, data, system):
        data = data if isinstance(data, dict) else {}
        bodies = {int(body.get("num")): body.get("name") for body in data.get("bodies") or () if isinstance(body, dict) and body.get("num") is not None}
        return {
            "system": data.get("name") or system, "id64": data.get("id64"),
            "architect": data.get("architect") or "", "open": bool(data.get("open")),
            "reserve": data.get("reserveLevel") or "", "rev": data.get("rev"),
            "bodies": [{"num": num, "name": name} for num, name in sorted(bodies.items())],
            "sites": [{"id": site.get("id"), "name": site.get("name") or "", "body_num": site.get("bodyNum"),
                       "body": bodies.get(site.get("bodyNum"), ""), "build_type": site.get("buildType") or "",
                       "type_label": catalogue.build_type_label(site.get("buildType")) if site.get("buildType") else "",
                       "status": site.get("status") or "plan", "build_id": site.get("buildId")}
                      for site in data.get("sites") or () if isinstance(site, dict)],
            "statuses": list(_SITE_STATUSES), "reserves": list(_RESERVE_LEVELS), "loaded_at": time.time(),
        }

    def _colony_architect_save(self, payload, ui):
        model = ui.get("architect")
        if not model:
            ui["error"] = "Load the system first."
            return True
        system = model["system"]
        update, delete = [], [str(item) for item in payload.get("delete") or () if item]
        for row in payload.get("sites") or ():
            if not isinstance(row, dict):
                continue
            name = _text(row.get("name"), 120)
            if not name:
                continue
            status = _text(row.get("status"), 20)
            update.append({"id": _text(row.get("id"), 80) or f"x{int(time.time() * 1000) % 10**9}{len(update)}",
                           "name": name, "bodyNum": _integer(row.get("body_num"), -1),
                           "buildType": _text(row.get("build_type"), 60).casefold() or None,
                           "status": status if status in _SITE_STATUSES else "plan"})
        put = {"update": update, "delete": delete}
        if "architect" in payload:
            put["architect"] = _text(payload.get("architect"), 80) or None
        if "open" in payload:
            put["open"] = bool(payload.get("open"))
        reserve = _text(payload.get("reserve"), 20)
        if reserve in _RESERVE_LEVELS[1:]:
            put["reserveLevel"] = reserve
        raven = self.raven

        def saved(data):
            ui["architect"] = self._colony_architect_model(data or {}, system) if data else model
            ui["notice"] = "System sites saved to Raven Colonial."
        return self._raven_call(lambda: raven.update_system(system, put), saved, label="Save system sites")
