"""The Colonisation tab (5.5.2): projects, the construction site you are
docked at, fleet carriers, system sites and the journal's own record.

Raven Colonial data comes from colonisation.colony (synced by
DashboardColonisationMixin); everything here also works from the journal
alone when no Raven Colonial key is set.
"""

from __future__ import annotations

import math
import webbrowser

from voidcompass.colonisation import catalogue
from voidcompass.colonisation.views import project_rows
from voidcompass.dashboard.html_colonisation_planner import HtmlColonisationPlannerMixin
from voidcompass.services.raven_colonial import SITE_URL, nexus_url, project_url, system_url

# The market finder's limits (the website's).
_MAX_MARKET_DISTANCE = 1000
_MAX_MARKET_ARRIVAL = 250_000
_SHIP_SIZES = ("large", "medium", "small")
# Old ids kept so older projects resolve; not offered when editing cargo.
_RETIRED_COMMODITIES = {"microbialfurnaces", "landenrichmentsystems", "muonimager", "combatstabilizers"}


def _text(value, limit=200):
    return str(value if value is not None else "").strip()[:limit]


def _integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class HtmlColonisationMixin(HtmlColonisationPlannerMixin):
    def _colony_ui_state(self):
        return self._html_profile_transient("_html_colonisation_state", {
            "selected": None, "site_plans": None, "site_plans_system": "",
            "planner": None, "planner_system": "", "planner_mine": None, "notice": "", "error": "",
            "stats": {}, "markets": None, "carrier_search": None, "global_stats": None,
            "nexuses": None, "nexus": None,
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
            "planner": self._planner_snapshot(),
            "stats": ui.get("stats") or {}, "markets": ui.get("markets"), "carrier_search": ui.get("carrier_search"),
            "global_stats": ui.get("global_stats"), "nexuses": ui.get("nexuses"), "nexus": self._colony_nexus_snapshot(ui.get("nexus")),
            "assignments": [], "current_system": getattr(self, "current_sys", "") or "",
            "build_commodities": sorted(({"id": key, "name": row["name"]} for key, row in catalogue.commodities().items()
                                         if key not in _RETIRED_COMMODITIES), key=lambda row: row["name"].casefold()),
            "market_limits": {"distance": _MAX_MARKET_DISTANCE, "arrival": _MAX_MARKET_ARRIVAL, "sizes": list(_SHIP_SIZES)},
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
        data["assignments"] = self._colony_assignments(cmdr)
        data["carriers"] = [{
            "market_id": carrier.get("marketId"), "name": carrier.get("name") or "",
            "display_name": carrier.get("displayName") or "", "system": carrier.get("systemName") or "",
            "access": carrier.get("access") or "", "last_refresh": carrier.get("lastRefresh"),
            "sales": [{"id": catalogue.commodity_id(row.get("name")), "name": catalogue.commodity_name(row.get("name")),
                       "price": row.get("price"), "total": row.get("total"), "outstanding": row.get("outstanding")}
                      for row in carrier.get("sales") or () if isinstance(row, dict)],
            "purchases": [{"id": catalogue.commodity_id(row.get("name")), "name": catalogue.commodity_name(row.get("name")),
                           "price": row.get("price"), "total": row.get("total"), "outstanding": row.get("outstanding")}
                          for row in carrier.get("purchases") or () if isinstance(row, dict)],
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
            "ready": [catalogue.commodity_id(item) for item in project.get("ready") or ()],
            "loading": str(project.get("buildType") or "").casefold() == catalogue.FC_LOADING,
            "architect_is_me": str(project.get("architectName") or "").casefold() == cmdr.casefold(),
            "time_due": project.get("timeDue"), "time_started": project.get("timestarted") or project.get("timeStarted"),
            "stats": None,
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
        if operation == "open_link":
            url = _text(payload.get("url"), 400)
            if url.startswith(("https://", "http://")):
                webbrowser.open_new_tab(url)
            return True
        if operation == "open_system":
            webbrowser.open_new_tab(system_url(_text(payload.get("system"), 120)))
            return True
        if not self._raven_active():
            ui["error"] = "Add your Raven Colonial key in Settings > Integrations (and leave sync on) first."
            return True
        if operation.startswith("planner_"):
            return self._handle_planner_command(operation, payload, ui)
        if operation.startswith(("nexus_", "carrier_", "project_", "markets_", "stats_")):
            return self._handle_colonisation_extra(operation, payload, ui, cmdr, build_id)
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
                ("factionName", "faction", 120), ("discordLink", "discord", 300)) if source in payload}
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
        return False

    # -- projects, carriers, markets, stats, nexus -----------------------
    def _colony_assignments(self, cmdr):
        """Everything assigned to this commander, across their projects."""
        me = cmdr.casefold()
        rows = []
        for project in self.colony.projects:
            mine = next((items for who, items in (project.get("commanders") or {}).items() if who.casefold() == me), None)
            needs = {catalogue.commodity_id(key): int(value or 0) for key, value in (project.get("commodities") or {}).items()}
            for item in mine or ():
                commodity = catalogue.commodity_id(item)
                if needs.get(commodity, 0) > 0:
                    rows.append({"build_id": project.get("buildId"), "project": project.get("buildName") or "",
                                 "system": project.get("systemName") or "", "id": commodity,
                                 "name": catalogue.commodity_name(commodity), "need": needs[commodity]})
        return sorted(rows, key=lambda row: (row["name"].casefold(), row["project"].casefold()))

    def _colony_nexus_snapshot(self, nexus):
        if not isinstance(nexus, dict):
            return None
        systems = []
        for row in nexus.get("systems") or ():
            if isinstance(row, dict):
                total, progress = int(row.get("total") or 0), int(row.get("progress") or 0)
                systems.append({"name": row.get("name"), "nickname": row.get("nickname") or "", "id64": row.get("id64"),
                                "type": row.get("type") or "", "total": total, "progress": progress,
                                "builds": len(row.get("builds") or ()), "fcs": list(row.get("fcs") or ()),
                                "url": system_url(row.get("name"))})
        return {"id": nexus.get("id"), "name": nexus.get("name") or "", "open": bool(nexus.get("open")),
                "owner": nexus.get("owner") or "", "notes": nexus.get("notes") or "", "cmdrs": list(nexus.get("cmdrs") or ()),
                "fcs": [{"market_id": fc.get("marketId"), "name": fc.get("name"), "display_name": fc.get("displayName") or ""}
                        for fc in nexus.get("fcs") or () if isinstance(fc, dict)],
                "systems": systems, "url": nexus_url(nexus.get("id")),
                "mine": str(nexus.get("owner") or "").casefold() == self._colony_cmdr().casefold()}

    def _handle_colonisation_extra(self, operation, payload, ui, cmdr, build_id):
        colony, raven = self.colony, self.raven
        if operation == "project_delete" and build_id and payload.get("confirmed"):
            def deleted(_result):
                ui["selected"] = None
                ui["notice"] = "Project deleted."
                self._colony_refresh()
            return self._raven_call(lambda: raven.delete_project(build_id), deleted, pending={}, label="Delete project")
        if operation == "project_stats" and build_id:
            def got(stats):
                ui.setdefault("stats", {})[build_id] = _stats_summary(stats or {})
            return self._raven_call(lambda: raven.project_stats(build_id), got, label="Project stats")
        if operation == "project_ready" and build_id:
            commodity = catalogue.commodity_id(payload.get("commodity"))
            ready = bool(payload.get("ready"))
            return bool(commodity) and self._raven_call(lambda: raven.set_ready(build_id, [commodity], ready),
                                                        lambda _r: self._colony_refresh(build_id), pending={}, label="Ready")
        if operation == "project_fc_loading":
            name = _text(payload.get("name"), 120)
            if not name:
                ui["error"] = "Name the loading project."
                return True

            def created(project):
                if isinstance(project, dict) and project.get("buildId"):
                    ui["selected"] = project["buildId"]
                    ui["notice"] = f"Fleet carrier loading project created: {name}."
                self._colony_refresh()
            return self._raven_call(lambda: raven.create_fc_loading_project(name), created, pending={}, label="Create loading project")
        if operation == "markets_find":
            project = colony.project(build_id) if build_id else None
            needs = {catalogue.commodity_id(key): int(value or 0) for key, value in ((project or {}).get("commodities") or {}).items()} \
                if project else dict(colony.needs(colony.visible_projects(), cmdr)["commodities"])
            needs = {key: value for key, value in needs.items() if value > 0}
            if not needs:
                ui["error"] = "Nothing left to buy."
                return True
            size = _text(payload.get("ship_size"), 10)
            options = {
                "refSystem": _text(payload.get("ref_system"), 160) or getattr(self, "current_sys", "") or (project or {}).get("systemName") or "Sol",
                "maxDistance": max(0, min(_MAX_MARKET_DISTANCE, _integer(payload.get("max_distance"), 100))),
                "maxArrival": max(0, min(_MAX_MARKET_ARRIVAL, _integer(payload.get("max_arrival"), 10000))),
                "shipSize": size if size in _SHIP_SIZES else "large",
                "noSurface": bool(payload.get("no_surface")), "noFC": bool(payload.get("no_fc")),
                "requireNeed": bool(payload.get("require_need")), "hasShipyard": bool(payload.get("has_shipyard")),
                "commodities": needs,
            }

            def found(result):
                ui["markets"] = _markets_summary(result or {}, needs, options, build_id)
            return self._raven_call(lambda: raven.find_markets(options), found, label="Find markets")
        if operation == "markets_clear":
            ui["markets"] = None
            return True
        if operation == "carrier_cargo":
            market_id = _integer(payload.get("market_id"), 0)
            cargo = {catalogue.commodity_id(key): max(0, _integer(value, 0)) for key, value in (payload.get("cargo") or {}).items()
                     if catalogue.commodity_id(key)}
            return bool(market_id) and self._raven_call(lambda: raven.set_carrier_cargo(market_id, cargo),
                                                        lambda result: colony.apply_carrier_cargo(market_id, result),
                                                        pending={}, label="Carrier cargo")
        if operation == "carrier_rename":
            market_id = _integer(payload.get("market_id"), 0)
            name = _text(payload.get("display_name"), 80)
            return bool(market_id) and self._raven_call(lambda: raven.rename_carrier(market_id, name),
                                                        lambda _r: self._colony_refresh(), label="Rename carrier")
        if operation == "carrier_search":
            name = _text(payload.get("name"), 60)
            if len(name) < 3:
                ui["error"] = "Type at least 3 characters of the carrier's callsign or name."
                return True

            def found(rows):
                ui["carrier_search"] = {"query": name, "results": [
                    {"market_id": row.get("market_id"), "name": row.get("name") or "", "carrier_name": row.get("carrier_name") or "",
                     "linked": colony.has_carrier(row.get("market_id"))} for row in rows or () if isinstance(row, dict)][:25]}
            return self._raven_call(lambda: raven.find_carriers(name), found, label="Find carrier")
        if operation == "carrier_link_found":
            market_id = _integer(payload.get("market_id"), 0)

            def link():
                if not raven.carrier(market_id):
                    raven.check_carrier(market_id)
                raven.link_carrier(cmdr, market_id)
                return True

            def linked(_result):
                ui["carrier_search"] = None
                ui["notice"] = "Fleet carrier linked."
                self._colony_refresh()
            return bool(market_id) and self._raven_call(link, linked, pending={}, label="Link carrier")
        if operation == "carrier_refresh":
            market_id = _integer(payload.get("market_id"), 0)
            return bool(market_id) and self._raven_call(lambda: raven.refresh_carrier(market_id),
                                                        lambda _r: self._colony_refresh(), label="Refresh carrier")
        if operation == "stats_load":
            def got(stats):
                ui["global_stats"] = _global_stats(stats or {})
            return self._raven_call(raven.global_stats, got, label="Raven statistics")
        if operation == "nexus_list":
            def got(rows):
                ui["nexuses"] = [{"id": row.get("id"), "name": row.get("name"), "open": bool(row.get("open")),
                                  "owner": row.get("owner"), "destination": row.get("destination")}
                                 for row in rows or () if isinstance(row, dict)]
            return self._raven_call(raven.my_nexuses, got, label="Your nexuses")
        if operation == "nexus_open":
            nexus_id = _text(payload.get("id"), 80)

            def got(nexus):
                ui["nexus"] = nexus
            return bool(nexus_id) and self._raven_call(lambda: raven.nexus(nexus_id), got, label="Nexus")
        if operation == "nexus_close":
            ui["nexus"] = None
            return True
        if operation == "nexus_create":
            name = _text(payload.get("name"), 80)
            if not name:
                ui["error"] = "Name the nexus."
                return True

            def created(nexus):
                ui["nexus"] = nexus
                ui["nexuses"] = None
            return self._raven_call(lambda: raven.create_nexus(name), created, label="Create nexus")
        if operation == "nexus_delete" and payload.get("confirmed"):
            nexus_id = _text(payload.get("id"), 80)

            def deleted(_result):
                ui["nexus"], ui["nexuses"] = None, None
                ui["notice"] = "Nexus deleted."
            return bool(nexus_id) and self._raven_call(lambda: raven.delete_nexus(nexus_id), deleted, label="Delete nexus")
        if operation == "nexus_set":
            nexus = ui.get("nexus") or {}
            nexus_id = nexus.get("id")
            field = payload.get("field")
            if not nexus_id:
                return False
            if field == "name":
                call = ("setName", _text(payload.get("value"), 80))
            elif field == "notes":
                call = ("setNotes", _text(payload.get("value"), 4000))
            elif field == "open":
                call = ("setPrivate", bool(payload.get("value")))
            elif field == "systems":
                call = ("setSystems", [_text(item, 160) for item in payload.get("value") or () if _text(item, 160)][:200])
            elif field == "cmdrs":
                call = ("setCmdrs", [_text(item, 80) for item in payload.get("value") or () if _text(item, 80)][:100])
            elif field == "fcs":
                call = ("setFCs", [_integer(item, 0) for item in payload.get("value") or () if _integer(item, 0)][:50])
            else:
                return False

            def saved(result):
                if isinstance(result, dict):
                    ui["nexus"] = result
            return self._raven_call(lambda: raven.update_nexus(nexus_id, *call), saved, label="Nexus")
        if operation == "nexus_open_raven":
            webbrowser.open_new_tab(nexus_url((ui.get("nexus") or {}).get("id")))
            return True
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


def _stats_summary(stats):
    """A project's deliveries: per commander and over time."""
    cmdrs = stats.get("cmdrs") or {}
    timeline = []
    for row in stats.get("stats") or ():
        if isinstance(row, dict):
            timeline.append({"time": row.get("time"), "cargo": int(row.get("countCargo") or 0),
                             "deliveries": int(row.get("countDeliveries") or 0)})
    return {"total_cargo": int(stats.get("totalCargo") or 0), "total_deliveries": int(stats.get("totalDeliveries") or 0),
            "start": stats.get("start"), "end": stats.get("end"),
            "cmdrs": sorted(({"name": name, "cargo": int(value or 0)} for name, value in cmdrs.items()),
                            key=lambda row: -row["cargo"]),
            "timeline": timeline[-60:]}


def _markets_summary(result, needs, options, build_id):
    rows = []
    for market in result.get("markets") or ():
        if not isinstance(market, dict):
            continue
        supplies = {catalogue.commodity_id(key): int(value or 0) for key, value in (market.get("supplies") or {}).items()}
        covers = [{"id": key, "name": catalogue.commodity_name(key), "stock": supplies[key], "need": need}
                  for key, need in needs.items() if supplies.get(key)]
        rows.append({"station": market.get("stationName") or "", "system": market.get("systemName") or "",
                     "body": market.get("bodyName") or "", "type": market.get("type") or "", "economy": market.get("economy") or "",
                     "distance": market.get("distance"), "arrival": market.get("distanceToArrival"),
                     "pad": market.get("padSize") or "", "surface": bool(market.get("surface")),
                     "updated": market.get("updatedAt"), "covers": sorted(covers, key=lambda row: row["name"].casefold()),
                     "covered": sum(1 for row in covers if row["stock"] >= row["need"])})
    rows.sort(key=lambda row: (-row["covered"], -len(row["covers"]), float(row["distance"] or 0)))
    return {"build_id": build_id, "options": options, "prepared_at": result.get("preparedAt"), "markets": rows[:40],
            "needs": [{"id": key, "name": catalogue.commodity_name(key), "need": value}
                      for key, value in sorted(needs.items(), key=lambda item: catalogue.commodity_name(item[0]).casefold())]}


def _global_stats(stats):
    def ranked(mapping, limit=10):
        return [{"name": name, "value": value} for name, value in sorted((mapping or {}).items(), key=lambda item: -float(item[1] or 0))][:limit]
    top_systems = []
    for score, row in sorted(((int(key), value) for key, value in (stats.get("topSystemScores") or {}).items()
                              if str(key).lstrip("-").isdigit()), reverse=True)[:10]:
        for system, architect in (row or {}).items():
            top_systems.append({"score": score, "system": system, "architect": architect})
    return {
        "at": stats.get("timeStamp"),
        "totals": {key: stats.get(key) for key in ("activeProjects", "completeProjects", "commanders", "commanders7d",
                                                   "fleetCarriers", "countDeliveries7d", "totalDelivered7d",
                                                   "countDeliveriesEver", "totalDeliveredEver", "totalArchitects",
                                                   "totalPlannedSystems")},
        "contributors": ranked(stats.get("topContributors7d")), "helpers": ranked(stats.get("topHelpers7d")),
        "architects": ranked(stats.get("topArchitects")), "systems": top_systems[:10],
    }
